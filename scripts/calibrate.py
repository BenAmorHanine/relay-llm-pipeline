"""Calibration run against the real Groq API.

Usage (from the repo root, cmd):
    .\\.venv\\Scripts\\python.exe scripts\\calibrate.py          # dry run: print plan, make NO calls
    .\\.venv\\Scripts\\python.exe scripts\\calibrate.py --go     # real run

Every request is streamed. One JSON line per request is appended (and fsynced)
to results/raw/calibration_<UTC timestamp>.jsonl as soon as it finishes, plus
a "run_start" line with the plan and a "run_end" line with the stop reason.

Parts (see docs/WORKLOG.md, Step 3):
    a   both models  baseline, sequential, one start every --a-spacing s:
                     5 small (~150 in, <=128 out) + 5 retrieval-sized (~1.5K in, <=300 out)
    b1  120b         tiny requests spread over ~15 s, stop launching at the first 429
    b3  20b          ONE tiny request: are limits per model or shared? (timing: see --b3-after-b2)
    b2  120b         after the first 429, one tiny request every 5 s until a 200
    b4  120b         after a 60 s cooldown, 5 requests of ~2K tokens at once
    c   120b         after a 60 s cooldown, 4 retrieval-sized requests, reasoning_effort=medium

Hard stops (the run ends, a "run_end" record says why):
    * any HTTP status other than 200 or 429, a network error/timeout, or an error inside a 200 stream
    * x-ratelimit-remaining-requests < MARGIN_REMAINING_REQUESTS (per docs: the daily request count)
    * x-ratelimit-remaining-tokens < MARGIN_REMAINING_TOKENS, checked only in parts a, b3 and c
      (per docs this header is the per-minute token window; parts b1/b2/b4 hit limits on purpose)
    * the next request would exceed CAP_REQUESTS or CAP_TOKENS for the whole run

Every prompt starts with a unique random marker (first line of the first
message) so no request can be served from Groq's prompt cache; the marker is
stored in each record as prompt_marker.

The Groq key is read from .env (GROQ_API_KEY) and is never printed or written.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACTED = ROOT / "data" / "papers" / "extracted"
RAW_DIR = ROOT / "results" / "raw"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

M120 = "openai/gpt-oss-120b"
M20 = "openai/gpt-oss-20b"

CAP_REQUESTS = 110
CAP_TOKENS = 43_000
MARGIN_REMAINING_REQUESTS = 800   # keep >= 80% of a 1K/day request budget untouched
MARGIN_REMAINING_TOKENS = 500     # per-minute window; below this a non-limit part is misbehaving
TEMPLATE_OVERHEAD = 60            # estimated tokens the chat template adds per request
REQUEST_TIMEOUT_S = 60

B1_MAX = 35
B1_WINDOW_S = 15.0
B2_INTERVAL_S = 5.0
B2_MAX = 12
COOLDOWN_S = 60.0
C_SPACING_S = 4.0

SYSTEM = (
    "Answer only from the context. Cite every claim as [paper p.N §section]. "
    "If the context does not answer the question, reply exactly: Not in the provided papers."
)

# (paper file stem, section title, question) - real questions over real passages.
QUESTIONS = [
    ("1706.03762v7", "Scaled Dot-Product Attention",
     "Why does the paper scale the dot products by 1/sqrt(d_k)?"),
    ("1706.03762v7", "Positional Encoding",
     "Why did the authors choose sinusoidal positional encodings instead of learned ones?"),
    ("2410.00037v1", "Inner Monologue",
     "What is the Inner Monologue in Moshi and what does it improve?"),
    ("2410.00037v1", "Multi-stream modeling",
     "How does Moshi model the user's and its own speech at the same time?"),
    ("2507.07955v2", "Ratio Loss",
     "What does the ratio loss in H-Net encourage, and why is it needed?"),
]

# ---------------------------------------------------------------- tokens ---

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("o200k_harmony")  # gpt-oss tokenizer

    def ntok(s: str) -> int:
        return len(_ENC.encode(s))

    TOKENIZER = "tiktoken o200k_harmony"
except Exception:  # pragma: no cover - fallback if tiktoken is unavailable
    def ntok(s: str) -> int:
        return max(1, len(s) // 4)

    TOKENIZER = "chars/4 (tiktoken unavailable)"


def truncate_tokens(text: str, n: int) -> str:
    words, out = text.split(), []
    for w in words:
        if ntok(" ".join(out + [w])) > n:
            break
        out.append(w)
    return " ".join(out)


# --------------------------------------------------------------- prompts ---

_blocks_cache: dict[str, list[dict]] = {}


def blocks(stem: str) -> list[dict]:
    if stem not in _blocks_cache:
        with (EXTRACTED / f"{stem}.jsonl").open(encoding="utf-8") as f:
            _blocks_cache[stem] = [json.loads(line) for line in f]
    return _blocks_cache[stem]


def context(stem: str, section: str, target_tokens: int) -> str:
    """Contiguous real text starting at `section`, block by block, up to target_tokens."""
    rows = blocks(stem)
    start = next(i for i, r in enumerate(rows) if r["section"] == section)
    parts: list[str] = []
    used = 0
    for r in rows[start:]:
        text = " ".join(r["text"].split())
        if len(text) < 80:  # skip page numbers, figure labels, equation fragments
            continue
        piece = f"[{stem} p.{r['page']} §{r['section']}] {text}"
        t = ntok(piece) + 1
        if used + t > target_tokens:
            rest = target_tokens - used
            if rest > 30:
                parts.append(truncate_tokens(piece, rest))
            break
        parts.append(piece)
        used += t
    return "\n".join(parts)


def marker() -> str:
    """Unique random prefix so no two requests share a prompt prefix (defeats prompt caching)."""
    return f"[run-marker {secrets.token_hex(8)}]\n"


def qa_messages(stem: str, section: str, question: str, total_in: int) -> list[dict]:
    m = marker()
    fixed = (ntok(m + SYSTEM) + ntok(question) + ntok("Context:\n\n\nQuestion: ")
             + TEMPLATE_OVERHEAD)
    ctx = context(stem, section, max(40, total_in - fixed))
    return [
        {"role": "system", "content": m + SYSTEM},
        {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {question}"},
    ]


def tiny_messages() -> list[dict]:
    return [{"role": "user", "content": marker() + "Reply with the single word OK."}]


def est_in(messages: list[dict]) -> int:
    return sum(ntok(m["content"]) for m in messages) + TEMPLATE_OVERHEAD


# ------------------------------------------------------------------ plan ---

@dataclass
class Step:
    part: str
    model: str
    kind: str                # small | retrieval | tiny | big
    messages: list[dict]
    max_out: int
    effort: str = "low"
    guard_tokens: bool = False
    est_in: int = field(init=False)

    def __post_init__(self) -> None:
        self.est_in = est_in(self.messages)

    @property
    def est_total(self) -> int:
        return self.est_in + self.max_out


def build_plan() -> dict[str, list[Step]]:
    plan: dict[str, list[Step]] = {}
    for model in (M120, M20):
        steps = [Step("a", model, "small", qa_messages(s, sec, q, 150), 128, guard_tokens=True)
                 for s, sec, q in QUESTIONS]
        steps += [Step("a", model, "retrieval", qa_messages(s, sec, q, 1500), 300, guard_tokens=True)
                  for s, sec, q in QUESTIONS]
        plan[f"a:{model}"] = steps
    plan["b1"] = [Step("b1", M120, "tiny", tiny_messages(), 16) for _ in range(B1_MAX)]
    plan["b3"] = [Step("b3_shared_check", M20, "tiny", tiny_messages(), 16, guard_tokens=True)]
    plan["b2"] = [Step("b2", M120, "tiny", tiny_messages(), 16) for _ in range(B2_MAX)]
    # b4: ~2K tokens each, different questions so nothing can be served from a prompt cache
    plan["b4"] = [Step("b4", M120, "big", qa_messages(s, sec, q, 2000), 16) for s, sec, q in QUESTIONS]
    plan["c"] = [Step("c", M120, "retrieval", qa_messages(s, sec, q, 1500), 300,
                      effort="medium", guard_tokens=True) for s, sec, q in QUESTIONS[:4]]
    return plan


def print_dry_run(plan: dict[str, list[Step]], a_spacing: float, b3_after_b2: bool) -> None:
    print(f"Calibration plan (DRY RUN - no API calls). Token estimates: {TOKENIZER} "
          f"+ {TEMPLATE_OVERHEAD} template tokens per request.\n")
    hdr = f"{'part':<16}{'model':<22}{'requests (max)':>15}{'est. in':>10}{'max out':>10}{'upper bound':>13}"
    print(hdr)
    print("-" * len(hdr))
    tot_r = tot_t = 0
    per_model: dict[str, list[int]] = {}
    for key, steps in plan.items():
        n = len(steps)
        tin = sum(s.est_in for s in steps)
        tout = sum(s.max_out for s in steps)
        model = steps[0].model
        print(f"{steps[0].part:<16}{model:<22}{n:>15}{tin:>10}{tout:>10}{tin + tout:>13}")
        tot_r += n
        tot_t += tin + tout
        pm = per_model.setdefault(model, [0, 0])
        pm[0] += n
        pm[1] += tin + tout
    print("-" * len(hdr))
    for model, (r, t) in per_model.items():
        print(f"{'subtotal':<16}{model:<22}{r:>15}{'':>10}{'':>10}{t:>13}")
    print(f"{'TOTAL':<16}{'':<22}{tot_r:>15}{'':>10}{'':>10}{tot_t:>13}")
    print(f"\nCaps: {CAP_REQUESTS} requests, {CAP_TOKENS} tokens. "
          f"Upper bound is {'WITHIN' if tot_r <= CAP_REQUESTS and tot_t <= CAP_TOKENS else 'OVER'} the caps "
          f"(requests {tot_r}/{CAP_REQUESTS}, tokens {tot_t}/{CAP_TOKENS}).")
    print("The script enforces the caps before every request, so an over-budget plan stops early, "
          "it never exceeds them.")

    # Per-minute token pressure in part a (sequential, one start every a_spacing seconds).
    a = plan[f"a:{M120}"]
    span = a_spacing * (len(a) - 1)
    burst = sum(s.est_total for s in a)
    print(f"\nPart a token pressure: {len(a)} requests per model start within {span:.0f} s, "
          f"~{burst} tokens (in + max out) per model. Docs say TPM = 8,000 per model.")
    retr = [s for s in a if s.kind == "retrieval"]
    print(f"  The {len(retr)} retrieval-sized requests alone: ~{sum(s.est_total for s in retr)} tokens "
          f"in {a_spacing * (len(retr) - 1):.0f} s.")
    print(f"b3 timing: {'after b2 recovers (literal spec)' if b3_after_b2 else 'right after the first 429 in b1, while 120b is limited'}.")
    print("Sequence: a(120b) -> a(20b) -> 60 s cooldown -> b1 [+b3] -> b2 -> 60 s cooldown -> b4 "
          "-> 60 s cooldown -> c")
    print("\nNothing was sent. Re-run with --go to make real calls.")


# ------------------------------------------------------------------- run ---

class Abort(Exception):
    pass


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_key() -> str:
    env = ROOT / ".env"
    if not env.exists():
        raise SystemExit("No .env file in the repo root (key not found; nothing was sent).")
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("GROQ_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value
    raise SystemExit("GROQ_API_KEY is missing or empty in .env (nothing was sent).")


def to_int(v: str | None) -> int | None:
    try:
        return int(float(v)) if v is not None else None
    except ValueError:
        return None


class Runner:
    def __init__(self, key: str, out: Path, plan: dict[str, list[Step]]):
        self.key = key
        self.out = out
        self.plan = plan
        self.fh = out.open("a", encoding="utf-8")
        self.seq = 0
        self.requests_sent = 0
        self.tokens_used = 0
        self.t0 = time.perf_counter()

    def write(self, rec: dict) -> None:
        self.fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.fh.flush()
        os.fsync(self.fh.fileno())

    def close(self) -> None:
        self.fh.close()

    async def call(self, client, step: Step) -> dict:
        import httpx

        if self.requests_sent + 1 > CAP_REQUESTS:
            raise Abort(f"request cap {CAP_REQUESTS} reached")
        if self.tokens_used + step.est_total > CAP_TOKENS:
            raise Abort(f"token cap {CAP_TOKENS} would be exceeded "
                        f"(used {self.tokens_used}, next up to {step.est_total})")
        self.requests_sent += 1
        self.seq += 1
        rec: dict = {
            "type": "request",
            "request_id": f"cal-{self.seq:03d}",
            "part": step.part,
            "model": step.model,
            "kind": step.kind,
            "reasoning_effort": step.effort,
            "max_completion_tokens": step.max_out,
            "est_tokens_in": step.est_in,
            "prompt_marker": step.messages[0]["content"].split("\n", 1)[0],
            "start_time": utc_iso(),
            "t_since_run_start_ms": round((time.perf_counter() - self.t0) * 1000, 1),
        }
        body = {
            "model": step.model,
            "messages": step.messages,
            "stream": True,
            "reasoning_effort": step.effort,
            "max_completion_tokens": step.max_out,
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                   "User-Agent": "relay-calibrate/0.1"}
        t_start = time.perf_counter()
        ms = lambda t: None if t is None else round((t - t_start) * 1000, 1)  # noqa: E731
        t_headers = t_reason = t_visible = None
        usage = x_groq = stream_error = None
        finish_reason = None
        delta_keys: set[str] = set()
        visible_chars = reasoning_chars = 0
        status = None
        try:
            async with client.stream("POST", API_URL, json=body, headers=headers,
                                     timeout=httpx.Timeout(REQUEST_TIMEOUT_S, connect=10)) as r:
                t_headers = time.perf_counter()
                status = r.status_code
                rec["status"] = status
                rec["ratelimit_headers"] = {k: v for k, v in r.headers.items()
                                            if k.lower().startswith("x-ratelimit-") or k.lower() == "retry-after"}
                if status != 200:
                    raw = (await r.aread()).decode("utf-8", errors="replace")
                    rec["error_body"] = raw
                    rec["all_response_headers"] = dict(r.headers)
                else:
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        if "error" in chunk:
                            stream_error = chunk["error"]
                        for ch in chunk.get("choices", []):
                            d = ch.get("delta") or {}
                            delta_keys.update(d.keys())
                            rtext = d.get("reasoning") or d.get("reasoning_content")
                            if rtext:
                                reasoning_chars += len(rtext)
                                if t_reason is None:
                                    t_reason = time.perf_counter()
                            if d.get("content"):
                                visible_chars += len(d["content"])
                                if t_visible is None:
                                    t_visible = time.perf_counter()
                            if ch.get("finish_reason"):
                                finish_reason = ch["finish_reason"]
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                        if chunk.get("x_groq"):
                            x_groq = {**(x_groq or {}), **chunk["x_groq"]}
                            if chunk["x_groq"].get("usage"):
                                usage = chunk["x_groq"]["usage"]
        except httpx.HTTPError as e:
            rec["status"] = None
            rec["network_error"] = f"{type(e).__name__}: {e}"
        t_end = time.perf_counter()

        rec.update({
            "time_to_headers_ms": ms(t_headers),
            "time_to_first_reasoning_ms": ms(t_reason),
            "time_to_first_visible_ms": ms(t_visible),
            "total_ms": ms(t_end),
            "finish_reason": finish_reason,
            "visible_chars": visible_chars,
            "reasoning_chars": reasoning_chars,
            "delta_keys_seen": sorted(delta_keys),
            "stream_error": stream_error,
            "usage": usage,
            "x_groq": x_groq,
        })
        if usage:
            rec["tokens_in"] = usage.get("prompt_tokens")
            rec["tokens_out"] = usage.get("completion_tokens")
            details = usage.get("completion_tokens_details") or {}
            rec["reasoning_tokens"] = details.get("reasoning_tokens")
            rec["server_timings_s"] = {k: usage[k] for k in
                                       ("queue_time", "prompt_time", "completion_time", "total_time")
                                       if k in usage}
            self.tokens_used += (usage.get("total_tokens")
                                 or (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0))
        elif status == 200:
            self.tokens_used += step.est_total  # no usage reported: count the upper bound
        rec["run_tokens_used_after"] = self.tokens_used
        rec["run_requests_sent_after"] = self.requests_sent
        self.write(rec)

        hdr = rec.get("ratelimit_headers") or {}
        rem_req = to_int(hdr.get("x-ratelimit-remaining-requests"))
        rem_tok = to_int(hdr.get("x-ratelimit-remaining-tokens"))
        if rec.get("status") not in (200, 429):
            raise Abort(f"{rec['request_id']}: status {rec.get('status')} "
                        f"{rec.get('network_error') or ''}".strip())
        if stream_error:
            raise Abort(f"{rec['request_id']}: error inside stream")
        if rem_req is not None and rem_req < MARGIN_REMAINING_REQUESTS:
            raise Abort(f"{rec['request_id']}: remaining-requests {rem_req} < {MARGIN_REMAINING_REQUESTS}")
        if step.guard_tokens and rem_tok is not None and rem_tok < MARGIN_REMAINING_TOKENS:
            raise Abort(f"{rec['request_id']}: remaining-tokens {rem_tok} < {MARGIN_REMAINING_TOKENS} "
                        f"in part {step.part}")
        print(f"  {rec['request_id']} {step.part:<16} {step.model:<20} status={rec['status']} "
              f"total={rec['total_ms']}ms tokens={rec.get('tokens_in')}/{rec.get('tokens_out')} "
              f"rem_req={rem_req} rem_tok={rem_tok}")
        return rec

    async def sequential(self, client, steps: list[Step], spacing: float) -> None:
        next_start = time.perf_counter()
        for s in steps:
            await asyncio.sleep(max(0.0, next_start - time.perf_counter()))
            started = time.perf_counter()
            await self.call(client, s)
            next_start = started + spacing

    async def cooldown(self, label: str) -> None:
        print(f"-- cooldown {COOLDOWN_S:.0f} s before {label}")
        await asyncio.sleep(COOLDOWN_S)

    async def run(self, a_spacing: float, b3_after_b2: bool) -> None:
        import httpx

        async with httpx.AsyncClient(http2=False) as client:
            for model in (M120, M20):
                print(f"-- part a on {model}")
                await self.sequential(client, self.plan[f"a:{model}"], a_spacing)

            await self.cooldown("b1")
            print("-- part b1 (120b) until first 429")
            first_429 = asyncio.Event()
            first_429_at: list[float] = []
            b3_tasks: list[asyncio.Task] = []

            async def b1_one(step: Step) -> None:
                rec = await self.call(client, step)
                if rec.get("status") == 429 and not first_429.is_set():
                    first_429_at.append(time.perf_counter())
                    first_429.set()
                    if not b3_after_b2:
                        print("-- part b3_shared_check (20b), right after first 429")
                        b3_tasks.append(asyncio.create_task(self.call(client, self.plan["b3"][0])))

            tasks = []
            interval = B1_WINDOW_S / B1_MAX
            for step in self.plan["b1"]:
                if first_429.is_set():
                    break
                tasks.append(asyncio.create_task(b1_one(step)))
                try:
                    await asyncio.wait_for(first_429.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
            await _gather_or_abort(tasks + b3_tasks)
            if b3_tasks:
                await _gather_or_abort(b3_tasks)
            if not first_429_at:
                print("-- b1 finished without a 429; skipping b2 (nothing to recover from)")
            else:
                print("-- part b2 (120b) every 5 s until 200")
                next_start = first_429_at[0] + B2_INTERVAL_S
                for step in self.plan["b2"]:
                    await asyncio.sleep(max(0.0, next_start - time.perf_counter()))
                    next_start = time.perf_counter() + B2_INTERVAL_S
                    rec = await self.call(client, step)
                    if rec.get("status") == 200:
                        break
            if b3_after_b2 or not first_429_at:
                print("-- part b3_shared_check (20b), after b2")
                await self.call(client, self.plan["b3"][0])

            await self.cooldown("b4")
            print("-- part b4 (120b) 5 x ~2K tokens at once")
            await _gather_or_abort([asyncio.create_task(self.call(client, s)) for s in self.plan["b4"]])

            await self.cooldown("c")
            print("-- part c (120b) reasoning_effort=medium")
            await self.sequential(client, self.plan["c"], C_SPACING_S)


async def _gather_or_abort(tasks: list[asyncio.Task]) -> None:
    """Wait for tasks; if one aborts, cancel the rest and re-raise."""
    try:
        await asyncio.gather(*tasks)
    except BaseException:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true", help="make real API calls (default: dry run only)")
    ap.add_argument("--a-spacing", type=float, default=15.0,
                    help="seconds between request starts in part a (default 15: fits the documented 8K TPM)")
    ap.add_argument("--b3-after-b2", action="store_true",
                    help="send b3 after b2 recovers (literal spec) instead of right after the first 429")
    args = ap.parse_args()

    plan = build_plan()
    if not args.go:
        print_dry_run(plan, args.a_spacing, args.b3_after_b2)
        return 0

    key = load_key()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"calibration_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    runner = Runner(key, out, plan)
    runner.write({
        "type": "run_start", "time": utc_iso(), "script": "scripts/calibrate.py",
        "args": vars(args), "tokenizer": TOKENIZER,
        "caps": {"requests": CAP_REQUESTS, "tokens": CAP_TOKENS},
        "margins": {"remaining_requests": MARGIN_REMAINING_REQUESTS,
                    "remaining_tokens": MARGIN_REMAINING_TOKENS},
        "plan": {k: [{"part": s.part, "model": s.model, "kind": s.kind, "est_in": s.est_in,
                      "max_out": s.max_out, "effort": s.effort} for s in v] for k, v in plan.items()},
    })
    print(f"Writing to {out.relative_to(ROOT)}")
    reason = "completed"
    try:
        asyncio.run(runner.run(args.a_spacing, args.b3_after_b2))
    except Abort as e:
        reason = f"aborted: {e}"
    except KeyboardInterrupt:
        reason = "aborted: interrupted by user"
    finally:
        runner.write({"type": "run_end", "time": utc_iso(), "reason": reason,
                      "requests_sent": runner.requests_sent, "tokens_used": runner.tokens_used})
        runner.close()
    print(f"Run {reason}. Requests sent: {runner.requests_sent}, tokens used: {runner.tokens_used}.")
    return 0 if reason == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
