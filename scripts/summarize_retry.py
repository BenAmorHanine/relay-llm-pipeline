"""Summarize the retry experiment. Every number is computed from the raw files.

Usage (from the repo root, cmd):
    .venv\\Scripts\\python.exe scripts\\summarize_retry.py results\\raw\\retry_<UTC>.jsonl [results\\raw\\calibration_<UTC>.jsonl]

All gaps are computed from the recorded start_time values (local clock, ms
resolution), never from the printed t+ values. "Accepted" means HTTP 200.
The optional calibration file is used only for the daily-refill check, which
needs the 120b history before the retry run.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

PERIOD_DAILY_S = 86.4
MODEL = "openai/gpt-oss-120b"


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.open(encoding="utf-8")]


def rem(r: dict) -> int | None:
    v = (r.get("ratelimit_headers") or {}).get("x-ratelimit-remaining-requests")
    return int(v) if v is not None else None


def main(retry_path: Path, cal_path: Path | None) -> int:
    lines = load(retry_path)
    reqs = sorted((r for r in lines if r.get("type") == "request"), key=lambda r: ts(r["start_time"]))
    end = next((r for r in lines if r.get("type") == "run_end"), {})
    print(f"File: {retry_path}")
    print(f"run_end: {end}")
    for part in ("a_burst", "a_aggressive", "b_burst", "b_polite"):
        rs = [r for r in reqs if r["part"] == part]
        print(f"  {part:<13} n={len(rs):>3}  200={sum(r['status'] == 200 for r in rs):>3}  "
              f"429={sum(r['status'] == 429 for r in rs):>3}")

    # first 429 of each burst, by start time
    def first_429(part):
        return next(r for r in reqs if r["part"] == part and r["status"] == 429)

    # ------------------------------------------------ item 1: gaps table ---
    print("\nGaps for every a_aggressive and b_polite request (seconds, start-to-start):")
    print(f"  {'id':<9}{'part':<14}{'start (UTC)':<15}{'since 429 end':>14}{'since last 200':>16}"
          f"{'since last any':>16}  status")
    rows = []
    for i, r in enumerate(reqs):
        if r["part"] not in ("a_aggressive", "b_polite"):
            continue
        prev = reqs[:i]
        last_ok = max((p for p in prev if p["status"] == 200), key=lambda p: ts(p["start_time"]))
        last_any = max(prev, key=lambda p: ts(p["start_time"]))
        burst = "a_burst" if r["part"] == "a_aggressive" else "b_burst"
        f429 = first_429(burst)
        f429_end = ts(f429["start_time"]) + timedelta(milliseconds=f429["total_ms"])
        g_ok = (ts(r["start_time"]) - ts(last_ok["start_time"])).total_seconds()
        g_any = (ts(r["start_time"]) - ts(last_any["start_time"])).total_seconds()
        g_429 = (ts(r["start_time"]) - f429_end).total_seconds()
        rows.append((r, g_ok, g_any, last_ok["request_id"]))
        print(f"  {r['request_id']:<9}{r['part']:<14}{r['start_time'][11:23]:<15}{g_429:>14.3f}"
              f"{g_ok:>10.3f} ({last_ok['request_id'][-3:]}){g_any:>16.3f}  {r['status']}")

    # ------------------------------------------------ item 2: rule test ---
    print("\nRule: 'passes only if >= 2.0 s since the last ACCEPTED request; rejections do not reset the clock'")
    passed = [(r, g) for r, g, _, _ in rows if r["status"] == 200]
    failed = [(r, g) for r, g, _, _ in rows if r["status"] == 429]
    min_pass = min(passed, key=lambda x: x[1])
    max_fail = max(failed, key=lambda x: x[1])
    print(f"  smallest gap (since last 200) that PASSED: {min_pass[1]:.3f} s ({min_pass[0]['request_id']})")
    print(f"  largest  gap (since last 200) that FAILED: {max_fail[1]:.3f} s ({max_fail[0]['request_id']})")
    viol = [(r["request_id"], g) for r, g, _, _ in rows if (g >= 2.0) != (r["status"] == 200)]
    print(f"  requests contradicting a 2.0 s threshold: {viol if viol else 'none'}")
    any_lt2_pass = [r["request_id"] for r, _, ga, _ in rows if r["status"] == 200 and ga < 2.0]
    print(f"  passes whose gap since the last request of ANY kind was < 2.0 s: {len(any_lt2_pass)} "
          f"({', '.join(any_lt2_pass)})  -> rejections do not reset the clock")
    for part in ("a_burst", "b_burst"):
        rs = [r for r in reqs if r["part"] == part]
        ok_before = [r for r in rs if r["status"] == 200 and ts(r["start_time"]) < ts(first_429(part)["start_time"])]
        span = (ts(ok_before[-1]["start_time"]) - ts(ok_before[0]["start_time"])).total_seconds()
        print(f"  {part}: {len(ok_before)} accepted before the first 429 ({first_429(part)['request_id']}), "
              f"starts spanning {span:.3f} s; a continuous 0.5/s refill would have added ~{span * 0.5:.1f}")

    # ------------------------------------------------ item 3: throughput ---
    print("\nThroughput in a_aggressive:")
    ag = [r for r in reqs if r["part"] == "a_aggressive"]
    f429 = first_429("a_burst")
    t0 = ts(f429["start_time"]) + timedelta(milliseconds=f429["total_ms"])
    t_last = ts(ag[-1]["start_time"])
    window = (t_last - t0).total_seconds()
    ok = sum(r["status"] == 200 for r in ag)
    print(f"  window: 429 end -> last aggressive start = {window:.3f} s; requests {len(ag)}; accepted {ok}; "
          f"rejected {len(ag) - ok}")
    print(f"  accepted per second: {ok / window:.3f}")
    best = math.floor(window / 2.0)
    print(f"  best possible with 2.0 s spacing from the 429 end in the same window: {best} "
          f"({best / window:.3f}/s), all accepted, 0 wasted")
    last_ok_before = max((r for r in reqs if r["part"] == "a_burst" and r["status"] == 200),
                         key=lambda r: ts(r["start_time"]))
    first_allowed = ts(last_ok_before["start_time"]) + timedelta(seconds=2.0)
    best_srv = math.floor((t_last - first_allowed).total_seconds() / 2.0) + 1
    print(f"  best possible under the server's rule (first slot = last accepted {last_ok_before['request_id']} "
          f"start + 2.0 s = {(first_allowed - t0).total_seconds():.3f} s after the 429 end, then every 2.0 s, "
          f"up to the last aggressive start): {best_srv}")
    print(f"  wasted requests: {len(ag) - ok}/{len(ag)} = {(len(ag) - ok) / len(ag) * 100:.1f}%")
    print(f"  accepted vs best: {ok}/{best} = {ok / best * 100:.1f}%")
    po = [r for r in reqs if r["part"] == "b_polite"]
    f429b = first_429("b_burst")
    t0b = ts(f429b["start_time"]) + timedelta(milliseconds=f429b["total_ms"])
    first_ok = next(r for r in po if r["status"] == 200)
    print(f"  b_polite: retry-after on {f429b['request_id']} = "
          f"{(f429b.get('ratelimit_headers') or {}).get('retry-after')} s; first 200 {first_ok['request_id']} "
          f"started {(ts(first_ok['start_time']) - t0b).total_seconds():.3f} s and ended "
          f"{(ts(first_ok['start_time']) + timedelta(milliseconds=first_ok['total_ms']) - t0b).total_seconds():.3f} s "
          f"after the 429 ended; requests used {len(po)}, wasted {sum(r['status'] != 200 for r in po)}")

    # ------------------------------------------------ item 4: daily refill ---
    print("\nDaily request counter (120b), whole 86.4 s periods credited per gap vs continuous refill:")
    hist = []
    if cal_path:
        hist = [r for r in load(cal_path) if r.get("type") == "request" and r["model"] == MODEL]
    seq = sorted([r for r in hist + reqs if r.get("model") == MODEL and r["status"] == 200],
                 key=lambda r: ts(r["start_time"]))
    lvl_w = lvl_c = 1000.0
    prev = None
    mw = mc = 0
    mism = []
    for r in seq:
        t = ts(r["start_time"])
        if prev is not None:
            g = (t - prev).total_seconds()
            lvl_w = min(1000.0, lvl_w + math.floor(g / PERIOD_DAILY_S))
            lvl_c = min(1000.0, lvl_c + g / PERIOD_DAILY_S)
        lvl_w -= 1
        lvl_c -= 1
        obs = rem(r)
        mw += obs == math.floor(lvl_w)
        mc += obs == math.floor(lvl_c)
        if obs != math.floor(lvl_w):
            mism.append(f"{r['request_id']} observed {obs} whole-periods {math.floor(lvl_w)}")
        prev = t
    print(f"  {len(seq)} accepted 120b records across both files: whole-periods matches {mw}, continuous matches {mc}")
    for m in mism:
        print(f"    mismatch: {m}")
    if hist:
        last_cal = max((r for r in hist if r["status"] == 200), key=lambda r: ts(r["start_time"]))
        first = seq[[r["request_id"] for r in seq].index(reqs[0]["request_id"])] if reqs else None
        g = (ts(first["start_time"]) - ts(last_cal["start_time"])).total_seconds()
        print(f"  {last_cal['request_id']} start {last_cal['start_time']} remaining {rem(last_cal)} -> "
              f"{first['request_id']} start {first['start_time']} remaining {rem(first)}")
        print(f"  gap {g:.3f} s = {g / 60:.2f} min = {g / PERIOD_DAILY_S:.3f} periods -> whole-periods predicts "
              f"{rem(last_cal)} + {math.floor(g / PERIOD_DAILY_S)} - 1 = {rem(last_cal) + math.floor(g / PERIOD_DAILY_S) - 1}; "
              f"35 min would give {rem(last_cal) + math.floor(35 * 60 / PERIOD_DAILY_S) - 1}")
        print(f"  reset-requests on {first['request_id']}: {(first.get('ratelimit_headers') or {}).get('x-ratelimit-reset-requests')} "
              f"= (1000 - {rem(first)}) x 86.4 s = {(1000 - rem(first)) * PERIOD_DAILY_S:.1f} s")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        sys.exit(1)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else None))
