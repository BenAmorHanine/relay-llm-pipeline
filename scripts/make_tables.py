"""Tables 2a, 2b and 3 of the brief, computed only from results/results.csv -> docs/tables.md.

    .venv\\Scripts\\python.exe scripts\\make_tables.py

One row per scenario: all kept runs (not in results/excluded_runs.csv) of a scenario are pooled; a run is the
(seed and) YYYYMMDDTHHMMSSZ part of request_id. Definitions (also printed under the tables):
    Requests sent        rows in the group
    Duration (s)         per run: last (start_time + total_ms) minus first start_time; summed over runs
    Offered rate         requests / (sum over runs of last start - first start) x 60 (arrivals per minute)
    First token p50/95/99  nearest-rank percentiles of first_token_ms over rows that have one
    Total time p50/95/99   nearest-rank percentiles of total_ms over status ok rows
    Succeeded / Rate-limited / Timed out or given up %   status ok / rate_limited / timeout over all rows
    Retries per request  mean of retries
    Peak queue length    max number of requests waiting for their first token at the same moment:
                         each row waits from start_time to start_time + (first_token_ms or total_ms)
    Tokens per answer    (sum tokens_in + tokens_out over all rows) / ok rows  (Table 3: / questions asked)
    Cost per 1,000 answers  list prices, tokens split by model with the assumption ROUTER_IN / ROUTER_OUT below
    Table 3 %            share of questions asked (graded rows only; "not measured" if none graded)
"""

from __future__ import annotations

import csv
import math
import random
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from relay.pipeline import RETRIEVAL_SETTINGS  # noqa: E402

# $ per million tokens (list prices given in Step 7)
PRICE = {"120b": (0.15, 0.60), "20b": (0.075, 0.30)}
# Split assumption: per request, the first ROUTER_IN input and ROUTER_OUT output tokens are the router (20b),
# the rest is 120b. ROUTER_IN = current router prompt mean incl. 60 template tokens (scripts/run_eval.py dry run);
# ROUTER_OUT = median completion tokens (75.5) of the 14 real router calls in traces_eval_medium_20261112T225309Z.
ROUTER_IN, ROUTER_OUT = 396, 76
STAMP = re.compile(r"\d{8}T\d{6}Z")
# Eval runs stamped at or after this were made with the check fixes and router guard of 2026-11-17
# (made after the day-1 runs 102821Z / 103158Z, before any later eval run).
FIXES_STAMP = "20261117T110000Z"
# Runs from this stamp on use the paper cover and draft rules 5-8 (docs/DECISIONS.md, "Paper cover"); the last
# run before the change is 20261118T092938Z. Scenarios ending in _baseline re-run the earlier system on purpose.
COVER_STAMP = "20261118T100000Z"


def pct(values: list[float], p: float):
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(p / 100 * len(s)) - 1)]


def fmt_ms(v) -> str:
    return "not measured" if v is None else f"{v:,.0f}"


def triple(vals, ps=(50, 95, 99)) -> str:
    return "not measured" if not vals else " / ".join(fmt_ms(pct(vals, p)) for p in ps)


def ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def cost(rows) -> float:
    c = 0.0
    for r in rows:
        ti, to = int(r["tokens_in"]), int(r["tokens_out"])
        ri, ro = min(ti, ROUTER_IN), min(to, ROUTER_OUT)
        c += (ri * PRICE["20b"][0] + ro * PRICE["20b"][1] + (ti - ri) * PRICE["120b"][0] + (to - ro) * PRICE["120b"][1]) / 1e6
    return c


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion, in percent."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def ci_text(vals: list[float], p: float, reps: int = 2000) -> str:
    """Nearest-rank percentile with a 95% bootstrap interval (seeded, so reproducible)."""
    if len(vals) < 2:
        return "not measured"
    rng = random.Random(0)
    boots = sorted(pct([rng.choice(vals) for _ in vals], p) for _ in range(reps))
    return f"{pct(vals, p):,.0f} [{boots[int(0.025 * reps)]:,.0f}, {boots[int(0.975 * reps) - 1]:,.0f}]"


def peak_queue(rows) -> int:
    ev = []
    for r in rows:
        s = ts(r["start_time"])
        wait = float(r["first_token_ms"] or r["total_ms"] or 0) / 1000
        ev += [(s, 1), (s + wait, -1)]
    cur = best = 0
    for _, d in sorted(ev, key=lambda e: (e[0], e[1])):
        cur += d
        best = max(best, cur)
    return best


def grader_agreement() -> list[str]:
    """How often the rubric's suggested grade matched the final (human-reviewed) grade, from results/raw/grades_*.csv."""
    rows = []
    for gf in sorted((ROOT / "results" / "raw").glob("grades_*.csv")):
        rows += [g for g in csv.DictReader(gf.open(encoding="utf-8", newline="")) if g.get("suggested_grade")]
    if not rows:
        return ["Grader agreement: not measured (no graded runs)."]
    first = {g["request_id"]: g["answer_grade"] for g in rows}          # reviewed grades, before any regrade
    regrades = []
    for rf in sorted((ROOT / "results" / "raw").glob("regrades_*.csv")):
        regrades += list(csv.DictReader(rf.open(encoding="utf-8", newline="")))
    final = dict(first)
    for g in regrades:
        final[g["request_id"]] = g["answer_grade"]
    for g in rows:
        g["answer_grade"] = final[g["request_id"]]
    out = []
    second = []
    for sf in sorted((ROOT / "results" / "raw").glob("second_grades_*.csv")):
        second += list(csv.DictReader(sf.open(encoding="utf-8", newline="")))
    if second:
        n2 = len(second)
        agree = sum(first[s["request_id"]] == s["answer_grade"] for s in second)
        cats = {first[s["request_id"]] for s in second} | {s["answer_grade"] for s in second}
        pe = sum(sum(first[s["request_id"]] == c for s in second) * sum(s["answer_grade"] == c for s in second)
                 for c in cats) / n2 / n2
        kappa = (agree / n2 - pe) / (1 - pe)
        lo2, hi2 = wilson(agree, n2)
        out.append(f"Second grader: an independent agent, blind to the first grades and given the same written rules, "
                   f"regraded {n2} answers (results/raw/second_grades_*.csv). It agreed with the first reviewed grade on "
                   f"{agree}/{n2} ({100 * agree / n2:.1f}%, 95% CI {lo2:.1f}-{hi2:.1f}; Cohen's kappa {kappa:.2f}). "
                   f"Disagreements were re-examined; {len(regrades)} grades were corrected in results/raw/regrades_*.csv "
                   f"(reasons there), and the tables use the corrected grades.")
    same = sum(g["answer_grade"] == g["suggested_grade"] for g in rows)
    lo, hi = wilson(same, len(rows))
    changed = sorted({f"{g['suggested_grade']} -> {g['answer_grade']}" for g in rows
                      if g["answer_grade"] != g["suggested_grade"]})
    return [f"Grader agreement: the rubric (scripts/pregrade.py) matched the final grade on {same}/{len(rows)} answers "
            f"({100 * same / len(rows):.1f}%, 95% CI {lo:.1f}-{hi:.1f}); "
            f"{sum(g.get('grade_from') == 'final' for g in rows)} final grades typed by hand, the rest accepted as "
            f"suggested. Changes: {', '.join(changed) or 'none'}."] + out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cmd uses cp1252
    rows = list(csv.DictReader((ROOT / "results" / "results.csv").open(encoding="utf-8", newline="")))
    # optional, maintained by hand: results/excluded_runs.csv with columns run_stamp, scenario, reason
    excl_path = ROOT / "results" / "excluded_runs.csv"
    excluded = {(e["run_stamp"], e["scenario"]): e["reason"]
                for e in csv.DictReader(excl_path.open(encoding="utf-8", newline=""))} if excl_path.exists() else {}
    runs: dict = {}
    for r in rows:
        m = STAMP.search(r["request_id"])
        stamp = m.group(0) if m else "-"
        if (stamp, r["scenario"]) in excluded:
            continue
        seed = re.search(r"-(s\d+)-\d{8}T", r["request_id"])
        run_id = (seed.group(1) + "-" if seed else "") + stamp
        runs.setdefault((r["scenario"], r["source"], run_id), []).append(r)
    groups: dict = {}       # (scenario, source) -> {run_id: rows}: all kept runs of a scenario are pooled
    for (sc, src, rid), g in runs.items():
        groups.setdefault((sc, src), {})[rid] = g
    order = ["steady", "burst", "sustained_overload", "rpm_halved", "daily_exhausted"]
    keys = sorted(groups, key=lambda k: (order.index(k[0]) if k[0] in order else 99, k[0]))

    a, b, u = [], [], []
    for k in keys:
        per_run = groups[k]
        g = [r for rr in per_run.values() for r in rr]
        n = len(g)
        dur = span = 0.0
        for rr in per_run.values():
            st = [ts(r["start_time"]) for r in rr]
            en = [ts(r["start_time"]) + float(r["total_ms"] or 0) / 1000 for r in rr]
            dur += max(en) - min(st)
            span += max(st) - min(st)
        rate = n / span * 60 if span > 0 else float("nan")
        ok = [r for r in g if r["status"] == "ok"]
        ft = [float(r["first_token_ms"]) for r in g if r["first_token_ms"]]
        tt = [float(r["total_ms"]) for r in ok]
        label = f"{k[0]} ({len(per_run)} run{'s' if len(per_run) > 1 else ''})"
        a.append(f"| {label} | {k[1]} | {n} | {dur:.1f} | {rate:.1f} | {triple(ft)} | {triple(tt)} |")
        share = lambda s_: f"{100 * sum(r['status'] == s_ for r in g) / n:.1f}"  # noqa: E731
        toks = sum(int(r["tokens_in"]) + int(r["tokens_out"]) for r in g)
        tpa = f"{toks / len(ok):,.0f}" if ok else "not measured"
        cpk = f"${cost(g) / len(ok) * 1000:.2f}" if ok else "not measured"
        err = sum(r["status"] == "error" for r in g)
        b.append(f"| {label} | {share('ok')} | {share('rate_limited')} | {share('timeout')} | "
                 f"{sum(int(r['retries']) for r in g) / n:.2f} | {max(peak_queue(rr) for rr in per_run.values())} | "
                 f"{tpa} | {cpk} |" + (f" <!-- {err} error rows -->" if err else ""))
        lo, hi = wilson(len(ok), n)
        seeds = [100 * sum(r["status"] == "ok" for r in rr) / len(rr) for rr in per_run.values()]
        spread = f"{min(seeds):.1f}–{max(seeds):.1f}" if len(seeds) > 1 else "one run"
        u.append(f"| {label} | {n} | {100 * len(ok) / n:.1f} [{lo:.1f}, {hi:.1f}] | {spread} | "
                 f"{ci_text(ft, 50)} | {ci_text(ft, 95)} |")

    # One row per real eval run, never pooled across runs: the pipeline changed between eval days, so runs
    # before FIXES_STAMP measure the earlier system (see docs/DECISIONS.md, "check fixes" and "router guard").
    t3 = []
    for k in keys:
        if k[0] not in ("eval", "eval_heldout", "eval_heldout_baseline"):
            continue
        for rid, gs in sorted(groups[k].items(), key=lambda kv: (kv[0] < FIXES_STAMP, kv[0]), reverse=True):
            s_ = gs[0]["retrieval_setting"]
            size, overlap, kk = RETRIEVAL_SETTINGS[s_]
            graded = [r for r in gs if r["answer_grade"]]
            n = len(gs)
            sh = (lambda gr: f"{100 * sum(r['answer_grade'] == gr for r in gs) / n:.1f}") if graded \
                else (lambda gr: "not measured (not graded)")
            nc = sum(r["answer_grade"] == "correct" for r in gs)
            lo, hi = wilson(nc, n)
            ok = [r for r in gs if r["status"] == "ok"]
            ft = [float(r["first_token_ms"]) for r in gs if r["first_token_ms"]]
            tt = [float(r["total_ms"]) for r in ok]
            toks = sum(int(r["tokens_in"]) + int(r["tokens_out"]) for r in gs)
            system = ("before paper cover (baseline re-run)" if k[0].endswith("_baseline")
                      else "final system" if rid >= COVER_STAMP
                      else "day-1 fixes, before paper cover" if rid >= FIXES_STAMP else "before day-1 fixes")
            day = f"{rid[:4]}-{rid[4:6]}-{rid[6:8]}"
            qset = "held-out q27-q39" if k[0].startswith("eval_heldout") else "q01-q26"
            t3.append(f"| {s_}: {size} tokens, {kk} pieces, no re-rank | {day}, {system}, {qset} ({k[1]}, {rid}) | {n} | "
                      f"{sh('correct')}" + (f" [{lo:.1f}, {hi:.1f}]" if graded else "") + f" | "
                      f"{sh('wrong')} | {sh('refused_correctly')} | {sh('refused_wrongly')} | {toks / n:,.0f} | {triple(ft, (50, 95))} | "
                      f"{triple(tt, (50, 95))} |")

    t1_src = (ROOT / "docs" / "table1_draft.md").read_text(encoding="utf-8").splitlines()
    t1_start = next(i for i, ln in enumerate(t1_src) if ln.startswith("| Limit"))
    t1 = []
    for ln in t1_src[t1_start:]:
        if not ln.startswith("|"):
            break
        t1.append(ln)
    out = ["# Results tables", "", f"Generated by scripts/make_tables.py from results/results.csv ({len(rows)} rows). "
           "Times in milliseconds, percentages with one decimal, nearest-rank percentiles.", "",
           "## Table 1: Limits found in the real service", "",
           "From the real-service raw files (results/raw/calibration_20261112T141038Z.jsonl, "
           "retry_20261112T145223Z.jsonl), not from results.csv; notes and evidence in docs/table1_draft.md.", "",
           *t1, "",
           "## Table 2a: Latency", "",
           "| Scenario (runs pooled) | Real or stand-in | Requests sent | Duration (s) | Offered rate (per min) | "
           "First token p50 / p95 / p99 (ms) | Total time p50 / p95 / p99 (ms) |",
           "|---|---|---|---|---|---|---|", *a, "",
           "## Table 2b: Outcomes", "",
           "| Scenario (runs pooled) | Succeeded % | Rate-limited % | Timed out or given up % | Retries per request | "
           "Peak queue length | Tokens per answer | Cost per 1,000 answers |",
           "|---|---|---|---|---|---|---|---|", *b, "",
           "## Uncertainty (not in the brief's tables)", "",
           "Pooled over the kept runs of each scenario. Success: 95% Wilson interval. First token: nearest-rank "
           "percentile with a 95% bootstrap interval over requests (2,000 resamples, seed 0). Seed spread: success % "
           "of the lowest and highest run.", "",
           "| Scenario | Requests | Succeeded % [95% CI] | Succeeded % across runs | First token p50 [95% CI] (ms) | "
           "First token p95 [95% CI] (ms) |",
           "|---|---|---|---|---|---|", *u, "",
           "## Table 3: Retrieval settings", "",
           "One row per real eval run (not pooled: the pipeline changed after the 2026-11-17 runs). "
           "Correct % with a Wilson 95% interval.", "",
           "| Setting (piece size, pieces fetched, re-rank) | Run | Questions asked | Correct and cited % [95% CI] | Wrong % | "
           "Correctly refused % | Refused wrongly % | Tokens per answer | First token p50 / p95 (ms) | Total time p50 / p95 (ms) |",
           "|---|---|---|---|---|---|---|---|---|---|", *(t3 or ["| not measured | | | | | | | | | |"]), "",
           "## How each number is computed", "", __doc__.split("Definitions (also printed under the tables):")[1].strip(),
           "", f"Prices: gpt-oss-120b ${PRICE['120b'][0]}/${PRICE['120b'][1]}, gpt-oss-20b ${PRICE['20b'][0]}/"
           f"${PRICE['20b'][1]} per million input/output tokens. Split assumption: the first {ROUTER_IN} input and "
           f"{ROUTER_OUT} output tokens of each request are the router (20b), the rest is the 120b draft (and redraft). "
           f"ROUTER_IN = current router prompt mean incl. template; ROUTER_OUT = median (75.5, rounded up) of the 14 real router calls "
           "(traces_eval_medium_20261112T225309Z).", "",
           *grader_agreement(), "",
           "Runs excluded from these tables (results/excluded_runs.csv; their rows stay in results.csv):",
           *([f"- {s} ({st}): {why}" for (st, s), why in sorted(excluded.items())] or ["- none"]), ""]
    (ROOT / "docs" / "tables.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out[:out.index("## How each number is computed")]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
