"""Stand-in model service: an OpenAI/Groq-compatible HTTP server for load tests.

    POST /openai/v1/chat/completions   (also /v1/chat/completions), streaming SSE only

The pipeline talks to it with the SAME client code as the real service:
    GroqClient(key="standin", api_url="http://127.0.0.1:8765/openai/v1/chat/completions", source="stand-in")

Behaviour (parameters in StandinConfig; sources in docs/standin.md):
    timing     resamples whole measured requests from standin/calibration.json (built from
               results/raw/calibration_*.jsonl and retry_*.jsonl): time to headers, time to first
               visible token, reasoning tokens, generation speed, server queue time; pool by prompt size
    RPM        per model, burst capacity = rpm, refill rpm/60 per second (rpm 30: after the burst one
               request per 2.0 s since the last accepted one; rejections consume nothing)
    TPM        per model, bucket of tpm tokens, charged prompt + max_tokens at admission, refills steadily
    RPD        per model, daily budget rpd, +1 per whole rpd_period_s (86.4 s) since the last credit,
               fractions dropped (as measured); set rpd small to exhaust it in a scenario
    429        same headers (x-ratelimit-*, retry-after rounded up to whole seconds) and JSON body
               {"error": {"message", "type": "requests"|"tokens", "code": "rate_limit_exceeded"}}
    load       every delay x (1 + load_alpha * (requests in flight - 1))  (assumption, not measured)
    failures   fail_rate: HTTP 503 after a short delay; slow_rate: the reply is slow_factor x slower
    content    20b (router): the JSON {"keywords": [], "papers": [], "in_scope": true}
               120b (draft): one sentence copied from passage [1] + " [1]" (passes the pipeline's check)

Run standalone:  .venv\\Scripts\\python.exe standin\\server.py --port 8765 [--rpm 15] [--rpd 20]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from relay.chunking import count_tokens  # noqa: E402

CALIBRATION = Path(__file__).resolve().parent / "calibration.json"
TEMPLATE_OVERHEAD = 60


@dataclass
class StandinConfig:
    rpm: int = 30
    tpm: int = 8000
    rpd: int = 1000
    rpd_period_s: float = 86.4
    load_alpha: float = 0.10
    fail_rate: float = 0.0
    slow_rate: float = 0.0
    slow_factor: float = 5.0
    seed: int = 1
    models: tuple = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")


def _dur(s: float) -> str:
    """Groq-style duration: 2.5s, 1m26.4s."""
    m, sec = divmod(max(0.0, s), 60)
    return f"{int(m)}m{sec:.2f}s" if m else f"{sec:.2f}s"


@dataclass
class Limits:
    cfg: StandinConfig
    now: float
    req_credits: float = 0.0
    tok_credits: float = 0.0
    day_left: int = 0
    day_mark: float = 0.0
    last_t: float = 0.0

    def __post_init__(self):
        self.req_credits, self.tok_credits, self.day_left = float(self.cfg.rpm), float(self.cfg.tpm), self.cfg.rpd
        self.last_t = self.day_mark = self.now

    def _refill(self, now: float) -> None:
        dt = now - self.last_t
        self.req_credits = min(self.cfg.rpm, self.req_credits + dt * self.cfg.rpm / 60)
        self.tok_credits = min(self.cfg.tpm, self.tok_credits + dt * self.cfg.tpm / 60)
        self.last_t = now
        k = int((now - self.day_mark) // self.cfg.rpd_period_s)   # whole periods only
        if k:
            self.day_left = min(self.cfg.rpd, self.day_left + k)
            self.day_mark = now                                    # fraction dropped (measured rule)

    def admit(self, cost: int, now: float):
        """None if admitted, else (type, limit_name, retry_after_s, used)."""
        self._refill(now)
        if self.day_left < 1:
            wait = self.cfg.rpd_period_s - (now - self.day_mark)
            return ("requests", f"requests per day (RPD): Limit {self.cfg.rpd}, Used {self.cfg.rpd}", wait)
        if self.req_credits < 1:
            wait = (1 - self.req_credits) * 60 / self.cfg.rpm
            return ("requests", f"requests per minute (RPM): Limit {self.cfg.rpm}, Used {self.cfg.rpm}", wait)
        if self.tok_credits < cost:
            wait = (cost - self.tok_credits) * 60 / self.cfg.tpm
            used = int(self.cfg.tpm - self.tok_credits)
            return ("tokens", f"tokens per minute (TPM): Limit {self.cfg.tpm}, Used {used}, Requested {cost}", wait)
        self.req_credits -= 1
        self.tok_credits -= cost
        self.day_left -= 1
        return None

    def headers(self, now: float) -> dict:
        return {"x-ratelimit-limit-requests": str(self.cfg.rpd),
                "x-ratelimit-remaining-requests": str(self.day_left),
                "x-ratelimit-reset-requests": _dur(self.cfg.rpd_period_s - (now - self.day_mark)),
                "x-ratelimit-limit-tokens": str(self.cfg.tpm),
                "x-ratelimit-remaining-tokens": str(max(0, int(self.tok_credits))),
                "x-ratelimit-reset-tokens": _dur((self.cfg.tpm - self.tok_credits) * 60 / self.cfg.tpm)}


class Standin:
    def __init__(self, cfg: StandinConfig = StandinConfig(), clock=time.perf_counter):
        self.cfg, self.clock = cfg, clock
        self.rng = random.Random(cfg.seed)
        cal = json.loads(CALIBRATION.read_text(encoding="utf-8"))
        self.pools = cal["pools"]
        self.r429_ms = cal["rate_limited_ms_p50"]
        self.limits = {m: Limits(cfg, clock()) for m in cfg.models}
        self.in_flight = 0
        self.max_in_flight = 0
        self.counts = {"accepted": 0, "rate_limited": 0, "failed": 0}
        self.server = None

    # ---------------------------------------------------------------- content
    @staticmethod
    def _content(model: str, messages: list[dict]) -> str:
        if model.endswith("-20b"):
            return '{"keywords": [], "papers": [], "in_scope": true}'
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        m = re.search(r"\[1\] \[[^\]]*\]\n(.*?)(?:\n\n\[2\] |\n\nQuestion:)", user, re.S)
        passage = m.group(1) if m else ""
        for sent in re.split(r"(?<=[.!?])\s+", " ".join(passage.split())):
            sent = re.sub(r"\[\d+(?:,\s*\d+)*\]", "", sent).strip()
            if len(sent) > 40 and sent.endswith((".", "!", "?")) and "|" not in sent:
                return f"{sent[:-1]} [1]."
        return "The three papers do not answer this question."

    # ------------------------------------------------------------------- HTTP
    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            lines = head.decode("latin-1").split("\r\n")
            method, path, _ = lines[0].split(" ", 2)
            hdrs = {k.strip().lower(): v.strip() for k, v in (ln.split(":", 1) for ln in lines[1:] if ":" in ln)}
            body = json.loads(await reader.readexactly(int(hdrs.get("content-length", "0"))) or b"{}")
            if method != "POST" or not path.endswith("/v1/chat/completions"):
                await self._send_json(writer, 404, {"error": {"message": "not found"}}, {})
                return
            await self._complete(body, writer)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _send_json(self, writer, status: int, obj: dict, headers: dict) -> None:
        data = json.dumps(obj).encode()
        reason = {200: "OK", 404: "Not Found", 429: "Too Many Requests", 503: "Service Unavailable"}[status]
        h = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
        writer.write(f"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\n"
                     f"Connection: close\r\n{h}\r\n".encode() + data)
        await writer.drain()

    async def _complete(self, body: dict, writer) -> None:
        model, messages = body.get("model"), body.get("messages", [])
        max_tokens = int(body.get("max_completion_tokens") or body.get("max_tokens") or 1024)
        prompt = sum(count_tokens(m.get("content", "")) for m in messages) + TEMPLATE_OVERHEAD
        lim = self.limits.get(model)
        if lim is None:
            await self._send_json(writer, 404, {"error": {"message": f"model {model} not found"}}, {})
            return
        now = self.clock()
        refused = lim.admit(prompt + max_tokens, now)
        if refused:
            kind, what, wait = refused
            self.counts["rate_limited"] += 1
            key = f"429_{model.rsplit('-', 1)[-1]}_{kind}"
            self.counts[key] = self.counts.get(key, 0) + 1
            await asyncio.sleep(self.r429_ms.get(model, 200.0) / 1000 * self.rng.uniform(0.7, 1.3))
            ra = max(1, math.ceil(wait))
            msg = (f"Rate limit reached for model `{model}` in organization `org_standin` service tier `on_demand` "
                   f"on {what}. Please try again in {wait:.3f}s.")
            await self._send_json(writer, 429, {"error": {"message": msg, "type": kind, "code": "rate_limit_exceeded"}},
                                  {**lim.headers(self.clock()), "retry-after": str(ra)})
            return
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            load = 1 + self.cfg.load_alpha * (self.in_flight - 1)
            slow = self.cfg.slow_factor if self.rng.random() < self.cfg.slow_rate else 1.0
            if self.rng.random() < self.cfg.fail_rate:
                self.counts["failed"] += 1
                await asyncio.sleep(0.2 * load)
                await self._send_json(writer, 503, {"error": {"message": "Service Unavailable", "type": "internal_server_error"}},
                                      lim.headers(self.clock()))
                return
            pool = self.pools[model]["small" if prompt < 600 else "large"] or self.pools[model]["small"]
            s = self.rng.choice(pool)
            k = load * slow
            await asyncio.sleep(s["headers_ms"] / 1000 * k)
            h = "".join(f"{a}: {b}\r\n" for a, b in lim.headers(self.clock()).items())
            writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\n"
                         f"Connection: close\r\n{h}\r\n".encode())
            await writer.drain()
            await asyncio.sleep(max(0.0, s["ttft_ms"] - s["headers_ms"]) / 1000 * k)
            text = self._content(model, messages)
            pieces = re.findall(r"\S+\s*", text)
            n_vis = count_tokens(text)
            per_piece = (n_vis / max(1, len(pieces))) / s["speed_tok_s"] * k
            cid = f"chatcmpl-standin-{self.rng.getrandbits(48):x}"
            for i, p in enumerate(pieces):
                if i:
                    await asyncio.sleep(per_piece)
                chunk = {"id": cid, "object": "chat.completion.chunk", "model": model,
                         "choices": [{"index": 0, "delta": {"content": p}, "finish_reason": None}]}
                writer.write(f"data: {json.dumps(chunk)}\n\n".encode())
                await writer.drain()
            out = s["reasoning_tokens"] + n_vis
            usage = {"prompt_tokens": prompt, "completion_tokens": out, "total_tokens": prompt + out,
                     "queue_time": round(s["queue_s"] * k, 4), "completion_time": round(out / s["speed_tok_s"] * k, 4),
                     "completion_tokens_details": {"reasoning_tokens": s["reasoning_tokens"]},
                     "standin_sample": s["request_id"], "standin_load_factor": round(load, 2), "standin_slow": slow > 1}
            final = {"id": cid, "object": "chat.completion.chunk", "model": model,
                     "choices": [{"index": 0, "delta": {}, "finish_reason": "stop" if out <= max_tokens else "length"}],
                     "x_groq": {"id": cid, "usage": usage}}
            writer.write(f"data: {json.dumps(final)}\n\ndata: [DONE]\n\n".encode())
            await writer.drain()
            self.counts["accepted"] += 1
        finally:
            self.in_flight -= 1

    async def start(self, host: str = "127.0.0.1", port: int = 8765):
        self.server = await asyncio.start_server(self.handle, host, port, limit=2 ** 20)
        return self.server

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()


async def _main(args) -> None:
    cfg = StandinConfig(rpm=args.rpm, tpm=args.tpm, rpd=args.rpd, rpd_period_s=args.rpd_period,
                        load_alpha=args.load_alpha, fail_rate=args.fail_rate, slow_rate=args.slow_rate)
    s = Standin(cfg)
    await s.start(port=args.port)
    print(f"stand-in on http://127.0.0.1:{args.port}/openai/v1/chat/completions {asdict(cfg)}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--rpm", type=int, default=30)
    ap.add_argument("--tpm", type=int, default=8000)
    ap.add_argument("--rpd", type=int, default=1000)
    ap.add_argument("--rpd-period", type=float, default=86.4)
    ap.add_argument("--load-alpha", type=float, default=0.10)
    ap.add_argument("--fail-rate", type=float, default=0.0)
    ap.add_argument("--slow-rate", type=float, default=0.0)
    asyncio.run(_main(ap.parse_args()))
