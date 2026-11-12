"""Retry experiment: does the per-minute request limit only refill during gaps >= 2 s?

Usage (from the repo root, cmd):
    .venv\\Scripts\\python.exe scripts\\retry_experiment.py          # dry run: plan + predictions, NO calls
    .venv\\Scripts\\python.exe scripts\\retry_experiment.py --go     # real run

Model: openai/gpt-oss-120b. Every request is a streamed tiny request
(unique random marker first, "Reply with the single word OK.", max 16 output
tokens, reasoning_effort low, temperature 0). Records use the same format as
scripts/calibrate.py and are appended + fsynced to
results/raw/retry_<UTC timestamp>.jsonl.

Phases
    a_burst       one request every 0.43 s (as in calibration b1) until the first 429 (max 35)
    a_aggressive  starting 1.0 s after that 429 ends: one request every 1.0 s for 20 s (20 requests),
                  regardless of what comes back
    (60 s cooldown)
    b_burst       same as a_burst
    b_polite      after each 429: wait retry-after (header; 2 s if absent) + uniform 0-300 ms jitter,
                  then retry; stop at the first 200 (max 10 retries)

Caps (checked before every request; the run stops rather than exceed them):
    100 requests; 12,000 tokens counted the way Groq's TPM check charges: prompt + max output.
    Every SENT request is counted (prompt from usage when reported, otherwise the estimate),
    including 429s, so the count is an upper bound on what Groq charged.
Hard stops: status other than 200/429, network error, error inside a stream,
x-ratelimit-remaining-requests < 800.
The Groq key is read from .env and never printed or written.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibrate import (  # noqa: E402  (shared helpers; calibrate.py runs nothing on import)
    API_URL, M120, MARGIN_REMAINING_REQUESTS, RAW_DIR, REQUEST_TIMEOUT_S, ROOT, TOKENIZER,
    est_in, load_key, tiny_messages, to_int, utc_iso,
)

CAP_REQUESTS = 100
CAP_TOKENS = 12_000
MAX_OUT = 16
BURST_INTERVAL_S = 0.43
BURST_MAX = 35
AGGR_INTERVAL_S = 1.0
AGGR_COUNT = 20
COOLDOWN_S = 60.0
POLITE_MAX = 10
JITTER_MAX_S = 0.300
RETRY_AFTER_DEFAULT_S = 2.0

PREDICTIONS = """
Predictions (written before running; the burst count is ~30 in every case except H3)

  H1  whole 2 s refill intervals only, and EVERY request (429s included) restarts the gap clock
      (my hypothesis from calibration):
        a_burst       30 x 200, then 429
        a_aggressive  0 of 20 return 200 (every gap is 1 s, so nothing ever refills)
        b_polite      first retry (~2.0-2.3 s after the 429) returns 200
  H2  whole 2 s refill intervals, but only ACCEPTED requests restart the clock:
        a_burst       30 x 200, then 429
        a_aggressive  first 200 ~2 s after the last accepted request, then roughly every
                      2nd retry succeeds (~9-10 of 20)
        b_polite      first retry returns 200
  H3  continuous bucket, 30 capacity, refilling 0.5 request/s (fractions kept):
        a_burst       ~35-36 x 200 before the 429 (refill during the ~13-15 s burst)
                      (calibration b1 already saw exactly 30, so H3 is unlikely)
        a_aggressive  ~every 2nd retry succeeds (~10 of 20), first within ~2 s
        b_polite      first retry returns 200
  H4  60 s sliding window:
        a_burst       30 x 200, then 429
        a_aggressive  0 of 20 (the window frees ~47 s after the 429, after this phase ends)
        b_polite      no 200 within 10 retries (~23 s) - the run reports "no recovery"
                      (calibration cal-053 already got a 200 5 s after a 429, so H4 is unlikely)

  What separates them: a_aggressive splits {H1, H4} (0 successes) from {H2, H3} (~10);
  b_polite then splits H1 (immediate) from H4 (none); the a_burst count splits H3 from the rest.
"""


class Abort(Exception):
    pass


class Runner:
    def __init__(self, key: str, out):
        self.key = key
        self.fh = out.open("a", encoding="utf-8")
        self.seq = 0
        self.requests_sent = 0
        self.tokens_charged = 0
        self.t0 = time.perf_counter()

    def write(self, rec: dict) -> None:
        self.fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.fh.flush()
        os.fsync(self.fh.fileno())

    def close(self) -> None:
        self.fh.close()

    async def call(self, client, part: str, ref_t: float | None = None) -> dict:
        import httpx

        messages = tiny_messages()
        est = est_in(messages)
        if self.requests_sent + 1 > CAP_REQUESTS:
            raise Abort(f"request cap {CAP_REQUESTS} reached")
        if self.tokens_charged + est + MAX_OUT > CAP_TOKENS:
            raise Abort(f"token cap {CAP_TOKENS} would be exceeded (charged {self.tokens_charged})")
        self.requests_sent += 1
        self.seq += 1
        t_start = time.perf_counter()
        rec: dict = {
            "type": "request",
            "request_id": f"rty-{self.seq:03d}",
            "part": part,
            "model": M120,
            "kind": "tiny",
            "reasoning_effort": "low",
            "max_completion_tokens": MAX_OUT,
            "est_tokens_in": est,
            "prompt_marker": messages[0]["content"].split("\n", 1)[0],
            "start_time": utc_iso(),
            "t_since_run_start_ms": round((t_start - self.t0) * 1000, 1),
            "t_since_phase_429_end_ms": None if ref_t is None else round((t_start - ref_t) * 1000, 1),
        }
        body = {"model": M120, "messages": messages, "stream": True, "reasoning_effort": "low",
                "max_completion_tokens": MAX_OUT, "temperature": 0}
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                   "User-Agent": "relay-calibrate/0.1"}
        ms = lambda t: None if t is None else round((t - t_start) * 1000, 1)  # noqa: E731
        t_headers = t_reason = t_visible = None
        usage = x_groq = stream_error = finish_reason = None
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
                    rec["error_body"] = (await r.aread()).decode("utf-8", errors="replace")
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
                                t_reason = t_reason or time.perf_counter()
                            if d.get("content"):
                                visible_chars += len(d["content"])
                                t_visible = t_visible or time.perf_counter()
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
        prompt = est
        if usage:
            rec["tokens_in"] = usage.get("prompt_tokens")
            rec["tokens_out"] = usage.get("completion_tokens")
            rec["reasoning_tokens"] = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            rec["server_timings_s"] = {k: usage[k] for k in
                                       ("queue_time", "prompt_time", "completion_time", "total_time") if k in usage}
            prompt = usage.get("prompt_tokens") or est
        self.tokens_charged += prompt + MAX_OUT
        rec["run_tokens_charged_after"] = self.tokens_charged
        rec["run_requests_sent_after"] = self.requests_sent
        self.write(rec)

        rem_req = to_int((rec.get("ratelimit_headers") or {}).get("x-ratelimit-remaining-requests"))
        if rec.get("status") not in (200, 429):
            raise Abort(f"{rec['request_id']}: status {rec.get('status')} {rec.get('network_error') or ''}".strip())
        if stream_error:
            raise Abort(f"{rec['request_id']}: error inside stream")
        if rem_req is not None and rem_req < MARGIN_REMAINING_REQUESTS:
            raise Abort(f"{rec['request_id']}: remaining-requests {rem_req} < {MARGIN_REMAINING_REQUESTS}")
        rel = "" if ref_t is None else f" t+{(t_start - ref_t):6.3f}s"
        print(f"  {rec['request_id']} {part:<13}{rel} status={rec['status']} total={rec['total_ms']}ms "
              f"retry-after={(rec.get('ratelimit_headers') or {}).get('retry-after')} rem_req={rem_req}")
        rec["_t_end"] = t_end  # in-memory only (not written)
        return rec

    async def burst(self, client, part: str) -> dict | None:
        """Launch every BURST_INTERVAL_S until the first 429 returns; return that 429 record."""
        first: list[dict] = []
        got = asyncio.Event()

        async def one():
            rec = await self.call(client, part)
            if rec.get("status") == 429 and not got.is_set():
                first.append(rec)
                got.set()

        tasks = []
        for _ in range(BURST_MAX):
            if got.is_set():
                break
            tasks.append(asyncio.create_task(one()))
            try:
                await asyncio.wait_for(got.wait(), timeout=BURST_INTERVAL_S)
            except asyncio.TimeoutError:
                pass
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return first[0] if first else None

    async def run(self) -> None:
        import httpx

        async with httpx.AsyncClient() as client:
            print("-- a_burst")
            r429 = await self.burst(client, "a_burst")
            if r429 is None:
                raise Abort("a_burst ended without a 429; experiment not meaningful")
            ref = r429["_t_end"]
            print(f"-- a_aggressive: one request every {AGGR_INTERVAL_S} s for {AGGR_COUNT} s")
            for i in range(1, AGGR_COUNT + 1):
                await asyncio.sleep(max(0.0, ref + i * AGGR_INTERVAL_S - time.perf_counter()))
                await self.call(client, "a_aggressive", ref)

            print(f"-- cooldown {COOLDOWN_S:.0f} s")
            await asyncio.sleep(COOLDOWN_S)

            print("-- b_burst")
            r429 = await self.burst(client, "b_burst")
            if r429 is None:
                raise Abort("b_burst ended without a 429; experiment not meaningful")
            ref = r429["_t_end"]
            last = r429
            print("-- b_polite: wait retry-after + 0-300 ms jitter")
            for _ in range(POLITE_MAX):
                ra = to_int((last.get("ratelimit_headers") or {}).get("retry-after"))
                wait = (ra if ra is not None else RETRY_AFTER_DEFAULT_S) + random.uniform(0, JITTER_MAX_S)
                await asyncio.sleep(max(0.0, last["_t_end"] + wait - time.perf_counter()))
                last = await self.call(client, "b_polite", ref)
                if last.get("status") == 200:
                    break
            else:
                print("-- b_polite: no 200 within the retry limit")


def print_dry_run() -> None:
    est = est_in(tiny_messages())
    per = est + MAX_OUT
    rows = [("a_burst", BURST_MAX, "until first 429; ~31 expected"),
            ("a_aggressive", AGGR_COUNT, "fixed: 1 per second for 20 s"),
            ("b_burst", BURST_MAX, "until first 429; ~31 expected"),
            ("b_polite", POLITE_MAX, "until first 200; 1 expected if H1")]
    print(f"Retry experiment (DRY RUN - no API calls). Model {M120}. Token estimates: {TOKENIZER} + template.")
    print(f"Charged per request (prompt + max output): ~{est} + {MAX_OUT} = ~{per} tokens\n")
    print(f"{'phase':<14}{'max requests':>13}{'max tokens':>12}  note")
    tot_r = 0
    for name, n, note in rows:
        print(f"{name:<14}{n:>13}{n * per:>12}  {note}")
        tot_r += n
    print(f"{'TOTAL (max)':<14}{tot_r:>13}{tot_r * per:>12}")
    exp = 31 + AGGR_COUNT + 31 + 1
    print(f"{'expected (H1)':<14}{exp:>13}{exp * per:>12}")
    print(f"\nCaps: {CAP_REQUESTS} requests, {CAP_TOKENS} tokens -> worst case "
          f"{'WITHIN' if tot_r <= CAP_REQUESTS and tot_r * per <= CAP_TOKENS else 'OVER'} the caps.")
    print("Sequence: a_burst -> a_aggressive (20 s) -> 60 s cooldown -> b_burst -> b_polite. ~2 minutes.")
    print("Note: the per-minute window must be idle when this starts; run it >= 60 s after any other 120b call.")
    print(PREDICTIONS)
    print("Nothing was sent. Re-run with --go to make real calls.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true", help="make real API calls (default: dry run only)")
    args = ap.parse_args()
    if not args.go:
        print_dry_run()
        return 0
    key = load_key()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"retry_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    runner = Runner(key, out)
    runner.write({"type": "run_start", "time": utc_iso(), "script": "scripts/retry_experiment.py",
                  "tokenizer": TOKENIZER, "caps": {"requests": CAP_REQUESTS, "tokens_prompt_plus_max_out": CAP_TOKENS},
                  "params": {"burst_interval_s": BURST_INTERVAL_S, "burst_max": BURST_MAX,
                             "aggr_interval_s": AGGR_INTERVAL_S, "aggr_count": AGGR_COUNT,
                             "cooldown_s": COOLDOWN_S, "polite_max": POLITE_MAX, "jitter_max_s": JITTER_MAX_S,
                             "max_out": MAX_OUT}})
    print(f"Writing to {out.relative_to(ROOT)}")
    reason = "completed"
    try:
        asyncio.run(runner.run())
    except Abort as e:
        reason = f"aborted: {e}"
    except KeyboardInterrupt:
        reason = "aborted: interrupted by user"
    finally:
        runner.write({"type": "run_end", "time": utc_iso(), "reason": reason,
                      "requests_sent": runner.requests_sent, "tokens_charged": runner.tokens_charged})
        runner.close()
    print(f"Run {reason}. Requests sent: {runner.requests_sent}, tokens charged (prompt + max out): "
          f"{runner.tokens_charged}.")
    return 0 if reason == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
