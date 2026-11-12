"""Summarize a calibration run. Every number printed is computed from the raw file.

Usage (from the repo root, cmd):
    .venv\\Scripts\\python.exe scripts\\summarize_calibration.py results\\raw\\calibration_<UTC>.jsonl

Percentiles use the nearest-rank method on successful (HTTP 200) requests only:
p50 = value at rank ceil(0.50 * n), p95 = value at rank ceil(0.95 * n).
With n < 20, p95 is simply the maximum; n is printed next to every row.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RPD_LIMIT_HEADER = "x-ratelimit-limit-requests"
TIMINGS = [
    ("time_to_headers_ms", "headers"),
    ("time_to_first_reasoning_ms", "1st reasoning"),
    ("time_to_first_visible_ms", "1st visible"),
    ("total_ms", "total"),
]


def pct(values: list[float], p: float) -> float | None:
    v = sorted(x for x in values if x is not None)
    if not v:
        return None
    return v[max(0, math.ceil(p * len(v)) - 1)]


def fmt(x, nd=0) -> str:
    if x is None:
        return "-"
    return f"{x:.{nd}f}"


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def end_ts(r: dict) -> datetime:
    return parse_ts(r["start_time"]) + timedelta(milliseconds=r["total_ms"])


def parse_dur(s: str | None) -> float | None:
    """Groq duration strings like '1h0m28.8s', '54m43.2s', '2.325s', '90ms' -> seconds."""
    if not s:
        return None
    total, found = 0.0, False
    for num, unit in re.findall(r"([\d.]+)(ms|h|m|s)", s):
        found = True
        total += float(num) * {"h": 3600, "m": 60, "s": 1, "ms": 0.001}[unit]
    return total if found else None


def hdr(r: dict, name: str):
    return (r.get("ratelimit_headers") or {}).get(name)


def hint(r: dict, name: str) -> int | None:
    v = hdr(r, name)
    return int(float(v)) if v is not None else None


def short(model: str) -> str:
    return model.split("/")[-1]


def main(path: Path) -> int:
    lines = [json.loads(l) for l in path.open(encoding="utf-8")]
    reqs = [r for r in lines if r.get("type") == "request"]
    start = next((r for r in lines if r.get("type") == "run_start"), {})
    end = next((r for r in lines if r.get("type") == "run_end"), {})
    by_id = {r["request_id"]: r for r in reqs}

    print(f"File: {path}")
    print(f"run_start {start.get('time')}  args={start.get('args')}")
    print(f"run_end   {end.get('time')}  reason={end.get('reason')!r}  "
          f"requests_sent={end.get('requests_sent')}  tokens_used={end.get('tokens_used')}")
    print(f"request records: {len(reqs)}; statuses: {dict(Counter(r.get('status') for r in reqs))}")
    print(f"tokens (sum of usage.total_tokens): "
          f"{sum((r.get('usage') or {}).get('total_tokens') or 0 for r in reqs)}\n")

    # ------------------------------------------------------------ table ---
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in reqs:
        groups[(short(r["model"]), r["part"], r["kind"], r["reasoning_effort"])].append(r)

    print("Per model / part / kind. Timings in ms, p50 / p95 over HTTP 200 only (nearest rank).")
    head = (f"{'model':<13}{'part':<16}{'kind':<10}{'eff':<7}{'n':>3} {'statuses':<14}"
            + "".join(f"{lbl + ' p50/p95':>22}" for _, lbl in TIMINGS)
            + f"{'in p50':>8}{'out p50':>8}{'reas p50':>9}{'in sum':>8}{'out sum':>8}{'reas sum':>9}{'len-cut':>8}")
    print(head)
    print("-" * len(head))
    for key in sorted(groups, key=lambda k: min(r["request_id"] for r in groups[k])):
        rs = groups[key]
        ok = [r for r in rs if r.get("status") == 200]
        st = ",".join(f"{s}x{c}" for s, c in sorted(Counter(r.get("status") for r in rs).items()))
        cells = ""
        for f, _ in TIMINGS:
            vals = [r.get(f) for r in ok]
            cells += f"{fmt(pct(vals, .5)) + ' / ' + fmt(pct(vals, .95)):>22}"
        tin = [r.get("tokens_in") for r in ok]
        tout = [r.get("tokens_out") for r in ok]
        reas = [r.get("reasoning_tokens") for r in ok]
        cut = sum(1 for r in ok if r.get("finish_reason") == "length")
        print(f"{key[0]:<13}{key[1]:<16}{key[2]:<10}{key[3]:<7}{len(rs):>3} {st:<14}{cells}"
              f"{fmt(pct(tin, .5)):>8}{fmt(pct(tout, .5)):>8}{fmt(pct(reas, .5)):>9}"
              f"{sum(x or 0 for x in tin):>8}{sum(x or 0 for x in tout):>8}{sum(x or 0 for x in reas):>9}"
              f"{cut:>8}")
    print("len-cut = responses that ended with finish_reason 'length' (hit max_completion_tokens).")
    no_vis = [r["request_id"] for r in reqs if r.get("status") == 200 and r.get("time_to_first_visible_ms") is None]
    print(f"200s with NO visible token (all output went to reasoning): {len(no_vis)}: {', '.join(no_vis)}\n")

    # ------------------------------------------------------- hypotheses ---
    print("=" * 100)
    b1 = sorted((r for r in reqs if r["part"] == "b1"), key=lambda r: r["start_time"])
    first429 = next((r for r in b1 if r.get("status") == 429), None)

    print("(a) RPM = 30")
    if first429:
        before = [r for r in b1 if parse_ts(r["start_time"]) < parse_ts(first429["start_time"])]
        succ = [r for r in before if r.get("status") == 200]
        el = (parse_ts(first429["start_time"]) - parse_ts(b1[0]["start_time"])).total_seconds()
        print(f"    b1 successes before first 429: {len(succ)} ({succ[0]['request_id']}..{succ[-1]['request_id']}); "
              f"first 429: {first429['request_id']}")
        print(f"    elapsed first b1 start ({b1[0]['request_id']} {b1[0]['start_time']}) -> 429 start "
              f"({first429['start_time']}): {el:.3f} s")
        print(f"    span of the 30 successful starts: "
              f"{(parse_ts(succ[-1]['start_time']) - parse_ts(succ[0]['start_time'])).total_seconds():.3f} s")
        prev_120 = [r for r in reqs if r["model"] == first429["model"] and r["part"] != "b1"
                    and parse_ts(r["start_time"]) < parse_ts(b1[0]["start_time"])]
        if prev_120:
            gap = (parse_ts(b1[0]["start_time"]) - end_ts(prev_120[-1])).total_seconds()
            print(f"    previous {short(first429['model'])} request {prev_120[-1]['request_id']} ended {gap:.1f} s "
                  f"before b1 began (outside any 60 s window)")
        print(f"    429 message: {json.loads(first429['error_body'])['error']['message'].split(' Please')[0]}")

    print("\n(b) A 429 does not decrease remaining-requests")
    for r429 in sorted((r for r in reqs if r.get("status") == 429), key=lambda r: r["request_id"]):
        same = sorted((r for r in reqs if r["model"] == r429["model"]), key=lambda r: end_ts(r))
        i = same.index(r429)
        prev_ok = next((r for r in reversed(same[:i]) if r.get("status") == 200), None)
        next_ok = next((r for r in same[i + 1:] if r.get("status") == 200), None)
        print(f"    {r429['request_id']} 429 remaining={hint(r429, 'x-ratelimit-remaining-requests')} | "
              f"last 200 before (by end time) {prev_ok and prev_ok['request_id']} remaining="
              f"{prev_ok and hint(prev_ok, 'x-ratelimit-remaining-requests')} | next 200 "
              f"{next_ok and next_ok['request_id']} remaining={next_ok and hint(next_ok, 'x-ratelimit-remaining-requests')}")

    print("\n(c) Limits per model or shared")
    b3 = next((r for r in reqs if r["part"] == "b3_shared_check"), None)
    if b3 and first429:
        dt = (parse_ts(b3["start_time"]) - end_ts(first429)).total_seconds()
        later_ok = next((r for r in sorted(reqs, key=lambda r: r["start_time"])
                         if r["model"] == first429["model"] and r.get("status") == 200
                         and parse_ts(r["start_time"]) > parse_ts(first429["start_time"])), None)
        prev20 = [r for r in reqs if r["model"] == b3["model"] and r["start_time"] < b3["start_time"]]
        print(f"    {b3['request_id']} ({short(b3['model'])}) sent {dt:.3f} s after {first429['request_id']}'s 429 ended, "
              f"before the next {short(first429['model'])} 200 ({later_ok and later_ok['request_id']} at "
              f"{later_ok and later_ok['start_time']})")
        print(f"    status={b3['status']}  its remaining-requests={hint(b3, 'x-ratelimit-remaining-requests')} "
              f"remaining-tokens={hint(b3, 'x-ratelimit-remaining-tokens')}  vs 120b at the 429: "
              f"remaining-requests={hint(first429, 'x-ratelimit-remaining-requests')}")
        if prev20:
            print(f"    previous {short(b3['model'])} record {prev20[-1]['request_id']}: remaining-requests="
                  f"{hint(prev20[-1], 'x-ratelimit-remaining-requests')}")

    print("\n(d) Recovery after the RPM 429")
    if first429:
        after = sorted((r for r in reqs if r["model"] == first429["model"]
                        and parse_ts(r["start_time"]) > parse_ts(first429["start_time"])),
                       key=lambda r: r["start_time"])
        nxt = after[0] if after else None
        nxt_ok = next((r for r in after if r.get("status") == 200), None)
        print(f"    retry-after on {first429['request_id']}: {hdr(first429, 'retry-after')} s; message: "
              f"{re.search(r'Please try again in [^.]+', json.loads(first429['error_body'])['error']['message']).group(0)}")
        if nxt_ok:
            print(f"    next {short(first429['model'])} request {nxt['request_id']} status={nxt['status']}; first 200: {nxt_ok['request_id']}")
            print(f"    429 end -> next 200 start: {(parse_ts(nxt_ok['start_time']) - end_ts(first429)).total_seconds():.3f} s; "
                  f"429 end -> next 200 end: {(end_ts(nxt_ok) - end_ts(first429)).total_seconds():.3f} s")
            print("    (probe interval was 5 s, so this is an upper bound on recovery, not the recovery time)")

    print("\n(e) TPM = 8,000 (part b4)")
    b4 = sorted((r for r in reqs if r["part"] == "b4"), key=lambda r: r["request_id"])
    for r in b4:
        line = (f"    {r['request_id']} status={r['status']} tokens_in={r.get('tokens_in')} est_in={r['est_tokens_in']} "
                f"max_out={r['max_completion_tokens']} limit-tokens={hdr(r, 'x-ratelimit-limit-tokens')} "
                f"remaining-tokens={hdr(r, 'x-ratelimit-remaining-tokens')} reset-tokens={hdr(r, 'x-ratelimit-reset-tokens')} "
                f"retry-after={hdr(r, 'retry-after')}")
        print(line)
        if r.get("status") == 429:
            m = json.loads(r["error_body"])["error"]["message"]
            print(f"        message: {re.search(r'on tokens.*?Please try again in [^.]+', m).group(0)}")
    ok4 = [r for r in b4 if r.get("status") == 200]
    if ok4:
        offs = [r["tokens_in"] - r["est_tokens_in"] for r in ok4]
        print(f"    tokens_in - est_in on the 200s: {offs} -> applied to the 429s gives prompt tokens "
              f"{[r['est_tokens_in'] + round(sum(offs) / len(offs)) for r in b4 if r.get('status') == 429]}; "
              f"plus max_out {b4[0]['max_completion_tokens']} = "
              f"{[r['est_tokens_in'] + round(sum(offs) / len(offs)) + r['max_completion_tokens'] for r in b4 if r.get('status') == 429]}")
        print(f"    sum over the 200s of tokens_in + max_out: {sum(r['tokens_in'] + r['max_completion_tokens'] for r in ok4)}")
    for rid in ("cal-001", "cal-021"):
        r = by_id.get(rid)
        if r:
            print(f"    reservation check {rid}: 8000 - remaining-tokens = {8000 - hint(r, 'x-ratelimit-remaining-tokens')}; "
                  f"tokens_in + max_out = {r['tokens_in'] + r['max_completion_tokens']}; "
                  f"tokens_in + tokens_out = {r['tokens_in'] + r['tokens_out']}")
    for r in [x for x in reqs if hdr(x, "x-ratelimit-reset-tokens") and hint(x, "x-ratelimit-remaining-tokens") is not None][:0]:
        pass
    sample = [r for r in reqs if r.get("status") == 429 and hdr(r, "x-ratelimit-reset-tokens")]
    for r in sample:
        used = 8000 - hint(r, "x-ratelimit-remaining-tokens")
        print(f"    {r['request_id']}: reset-tokens {parse_dur(hdr(r, 'x-ratelimit-reset-tokens'))} s vs "
              f"(8000 - remaining) * 60 / 8000 = {used * 60 / 8000:.3f} s")

    print("\n(f) Daily request counter refill")
    print("    reset-requests / (1000 - remaining) for every record with both headers:")
    for model in sorted({r["model"] for r in reqs}):
        ratios = []
        for r in reqs:
            if r["model"] != model:
                continue
            rem, rst = hint(r, "x-ratelimit-remaining-requests"), parse_dur(hdr(r, "x-ratelimit-reset-requests"))
            lim = hint(r, RPD_LIMIT_HEADER)
            if rem is not None and rst is not None and lim and lim > rem:
                ratios.append(rst / (lim - rem))
        print(f"      {short(model)}: n={len(ratios)} min={min(ratios):.3f} s max={max(ratios):.3f} s "
              f"(1000/86400 s => one request per {86400 / 1000:.1f} s)")
    print("    120b sequence of 200s: remaining observed vs two refill models")
    print("      continuous: level refills at 1/86.4 per s, fractions carried over")
    print("      whole-periods: only floor(gap / 86.4 s) requests are credited per gap, fraction dropped")
    for model in sorted({r["model"] for r in reqs}):
        ok = sorted((r for r in reqs if r["model"] == model and r.get("status") == 200), key=lambda r: r["start_time"])
        lvl_c = lvl_w = 1000.0
        prev_t = None
        match_c = match_w = 0
        rows = []
        for r in ok:
            t = parse_ts(r["start_time"])
            if prev_t is not None:
                gap = (t - prev_t).total_seconds()
                lvl_c = min(1000.0, lvl_c + gap / 86.4)
                lvl_w = min(1000.0, lvl_w + math.floor(gap / 86.4))
            lvl_c -= 1
            lvl_w -= 1
            prev_t = t
            obs = hint(r, "x-ratelimit-remaining-requests")
            pc, pw = math.floor(lvl_c), math.floor(lvl_w)
            match_c += obs == pc
            match_w += obs == pw
            if obs != pc or obs != pw:
                rows.append(f"{r['request_id']}: observed {obs}, continuous {pc}, whole-periods {pw}")
        print(f"      {short(model)}: {len(ok)} records; continuous matches {match_c}, whole-periods matches {match_w}")
        for row in rows:
            print(f"        {row}")
    a120 = [r for r in reqs if r["part"] == "a" and "120b" in r["model"]]
    if a120 and b1:
        gap = (parse_ts(b1[0]["start_time"]) - parse_ts(a120[-1]["start_time"])).total_seconds()
        print(f"    {a120[-1]['request_id']} (remaining {hint(a120[-1], 'x-ratelimit-remaining-requests')}) -> "
              f"{b1[0]['request_id']} (remaining {hint(b1[0], 'x-ratelimit-remaining-requests')}, after consuming 1): "
              f"gap {gap:.1f} s = {gap / 86.4:.2f} periods of 86.4 s")

    print("\n(g) Server-side timings")
    ok = [r for r in reqs if r.get("status") == 200]
    have = [r for r in ok if r.get("server_timings_s")]
    print(f"    present on {len(have)}/{len(ok)} successful records; fields: "
          f"{sorted({k for r in have for k in r['server_timings_s']})}")
    for model in sorted({r["model"] for r in have}):
        rs = [r for r in have if r["model"] == model]
        q_share = [r["server_timings_s"]["queue_time"] * 1000 / r["total_ms"] for r in rs]
        q_ms = [r["server_timings_s"]["queue_time"] * 1000 for r in rs]
        srv = [r["server_timings_s"]["total_time"] * 1000 for r in rs]
        rest = [r["total_ms"] - (r["server_timings_s"]["queue_time"] + r["server_timings_s"]["total_time"]) * 1000
                for r in rs]
        print(f"    {short(model)} n={len(rs)}: queue p50/p95 {fmt(pct(q_ms, .5))}/{fmt(pct(q_ms, .95))} ms; "
              f"queue share of client total p50/p95 {fmt(pct(q_share, .5) * 100, 1)}%/{fmt(pct(q_share, .95) * 100, 1)}%; "
              f"server total_time (prompt+completion) p50 {fmt(pct(srv, .5))} ms; "
              f"client total - queue - server total p50 {fmt(pct(rest, .5))} ms")
        tot_q = sum(q_ms)
        tot = sum(r["total_ms"] for r in rs)
        print(f"      sum of queue / sum of client total: {tot_q / tot * 100:.1f}%")
    worst = max(have, key=lambda r: r["server_timings_s"]["queue_time"])
    print(f"    largest queue_time: {worst['request_id']} {worst['server_timings_s']['queue_time'] * 1000:.0f} ms "
          f"of {worst['total_ms']:.0f} ms total")

    print("\n(h) Reasoning effort on 120b retrieval-sized requests")
    for label, sel in (("a low", lambda r: r["part"] == "a" and r["kind"] == "retrieval" and "120b" in r["model"]),
                       ("c medium", lambda r: r["part"] == "c")):
        rs = [r for r in reqs if sel(r) and r.get("status") == 200]
        print(f"    {label:<9} n={len(rs)} ids={rs[0]['request_id']}..{rs[-1]['request_id']}  "
              f"1st visible p50/p95 {fmt(pct([r['time_to_first_visible_ms'] for r in rs], .5))}/"
              f"{fmt(pct([r['time_to_first_visible_ms'] for r in rs], .95))} ms  "
              f"total p50/p95 {fmt(pct([r['total_ms'] for r in rs], .5))}/{fmt(pct([r['total_ms'] for r in rs], .95))} ms  "
              f"reasoning tokens {[r['reasoning_tokens'] for r in rs]}  out {[r['tokens_out'] for r in rs]}  "
              f"finish {[r['finish_reason'] for r in rs]}  visible chars {[r['visible_chars'] for r in rs]}")

    print("\nClock check (local start_time vs server Date header, 1 s resolution):")
    for r in reqs:
        d = (r.get("all_response_headers") or {}).get("date")
        if d:
            srv = parsedate_to_datetime(d).astimezone(timezone.utc)
            local_resp = parse_ts(r["start_time"]) + timedelta(milliseconds=r["time_to_headers_ms"])
            skew = (local_resp - srv).total_seconds()
            print(f"    {r['request_id']}: local response time - server Date = {skew:.3f} s "
                  f"(true skew in [{skew - 1:.3f}, {skew:.3f}] s)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(Path(sys.argv[1])))
