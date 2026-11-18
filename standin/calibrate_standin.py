"""Build standin/calibration.json from the real-service raw files (read-only):
results/raw/calibration_*.jsonl and results/raw/retry_*.jsonl.

For every accepted (HTTP 200) streamed request it keeps one sample, so the stand-in resamples whole
measured requests (keeping the correlation between queueing, first token and speed):
    request_id, model, kind, prompt_tokens, headers_ms (time to response headers),
    ttft_ms (first visible content token), reasoning_tokens, speed_tok_s (completion_tokens /
    server completion_time), queue_s (server queue_time)
Pools per model: "small" (prompt < 600 tokens: tiny/small requests) and "large" (retrieval/big).
Also: the median time a 429 took to come back, per model.

--traces adds real pipeline calls from eval traces (accepted route/draft calls; for a call that retried, the final
attempt: first token minus wait_ms and retry_ms). Traces have
no time-to-headers, so those samples use first token x the median headers/first-token ratio of the calibration
samples (stated in calibration.json).

    .venv\\Scripts\\python.exe standin\\calibrate_standin.py
"""

from __future__ import annotations

import glob
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "calibration.json"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", nargs="*", default=[],
                    help="also sample real pipeline calls from these trace files (globs, relative to the repo root)")
    args = ap.parse_args()
    files = sorted(glob.glob(str(ROOT / "results" / "raw" / "calibration_*.jsonl"))) + \
        sorted(glob.glob(str(ROOT / "results" / "raw" / "retry_*.jsonl")))
    pools: dict = {}
    r429: dict = {}
    for f in files:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if r.get("type") != "request":
                continue
            m = r["model"]
            if r.get("status") == 429:
                r429.setdefault(m, []).append(r["total_ms"])
                continue
            u = r.get("usage") or {}
            if r.get("status") != 200 or not u.get("completion_time") or r.get("time_to_first_visible_ms") is None:
                continue
            pt = u.get("prompt_tokens") or r.get("tokens_in") or 0
            s = {"request_id": r["request_id"], "file": Path(f).name, "kind": r["kind"], "prompt_tokens": pt,
                 "headers_ms": r["time_to_headers_ms"], "ttft_ms": r["time_to_first_visible_ms"],
                 "reasoning_tokens": r.get("reasoning_tokens") or 0,
                 "speed_tok_s": round(u["completion_tokens"] / u["completion_time"], 1),
                 "queue_s": u.get("queue_time", 0.0)}
            pools.setdefault(m, {"small": [], "large": []})["small" if pt < 600 else "large"].append(s)
    # real pipeline calls from eval traces (first attempt, accepted): the right prompt sizes, and a second day
    hdr_ratio = statistics.median(x["headers_ms"] / x["ttft_ms"] for pl in pools.values() for v in pl.values()
                                  for x in v if x["ttft_ms"])
    trace_files = [f for pat in args.traces for f in sorted(glob.glob(str(ROOT / pat)))]
    for f in trace_files:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            st = r.get("server_timings_s") or {}
            if (r.get("type") != "step" or r.get("step") not in ("route", "draft", "redraft") or r.get("outcome") != "ok"
                    or r.get("model_first_token_ms") is None or not st.get("completion_time")):
                continue
            # first token inside the final (accepted) attempt: remove the rate-gate wait and the 429 retries
            ttft = r["model_first_token_ms"] - (r.get("wait_ms") or 0) - (r.get("retry_ms") or 0)
            if ttft <= 0:
                continue
            m, pt = r["model"], r.get("tokens_in") or 0
            s = {"request_id": r["request_id"] + ":" + r["step"], "file": Path(f).name, "kind": r["step"],
                 "prompt_tokens": pt, "headers_ms": round(ttft * hdr_ratio, 1),
                 "ttft_ms": round(ttft, 1), "reasoning_tokens": r.get("reasoning_tokens") or 0,
                 "speed_tok_s": round((r.get("tokens_out") or 0) / st["completion_time"], 1),
                 "queue_s": st.get("queue_time", 0.0)}
            pools.setdefault(m, {"small": [], "large": []})["small" if pt < 600 else "large"].append(s)
    summary = {}
    for m, p in pools.items():
        summary[m] = {k: {"n": len(v), "ttft_ms_p50": statistics.median(x["ttft_ms"] for x in v) if v else None,
                          "speed_tok_s_p50": statistics.median(x["speed_tok_s"] for x in v) if v else None}
                      for k, v in p.items()}
    out = {"sources": [Path(f).name for f in files] + [Path(f).name for f in trace_files],
           "headers_to_first_token_ratio_for_trace_samples": round(hdr_ratio, 3), "pools": pools,
           "rate_limited_ms_p50": {m: statistics.median(v) for m, v in r429.items()}, "summary": summary}
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"summary": summary, "rate_limited_ms_p50": out["rate_limited_ms_p50"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
