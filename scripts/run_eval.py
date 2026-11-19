"""Run the pipeline on eval/questions.yaml against the REAL Groq API, one question at a time.

Dry run by default: prints requests and reserved tokens per model, makes NO calls.
    .venv\\Scripts\\python.exe scripts\\run_eval.py --setting medium
    .venv\\Scripts\\python.exe scripts\\run_eval.py --setting large --questions q01,q05,q12
    .venv\\Scripts\\python.exe scripts\\run_eval.py --setting medium --go      # real calls

A --go run writes (append-only):
    results/raw/run_eval_<setting>_<UTC>.csv      one results row per question (scenario "eval")
    results/raw/traces_eval_<setting>_<UTC>.jsonl per-step traces (answers, citations, timings)
--heldout adds _heldout and --baseline adds _baseline to the scenario (eval_heldout_baseline).
request_id = eval-<setting>-<UTC>-<qid> (eval-heldout-baseline-<setting>-... etc.), so scripts/pregrade.py can match rows, traces and questions.

Safety: the run stops early if 3 requests in a row end with status rate_limited or error
(the budget is shared; better to stop and look than to burn it).
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from relay.chunking import count_tokens  # noqa: E402
from relay.pipeline import (DRAFT_SYSTEM_BEFORE_COVER, RETRIEVAL_SETTINGS, BM25Tool, Pipeline,  # noqa: E402
                            PipelineConfig, draft_messages, redraft_messages, router_messages)
from relay.recording import ResultsWriter, TraceWriter  # noqa: E402

RAW = ROOT / "results" / "raw"
TEMPLATE_OVERHEAD = 60      # chat-template tokens per request (scripts/calibrate.py)
FEEDBACK_TOKENS = 120       # check errors in a redraft message (estimate)
STOP_AFTER_BAD = 3


def load_questions(selected: str | None, heldout: bool = False) -> list[dict]:
    qs = yaml.safe_load((ROOT / "eval" / ("heldout.yaml" if heldout else "questions.yaml")).read_text(encoding="utf-8"))
    if selected:
        want = [x.strip() for x in selected.split(",") if x.strip()]
        unknown = sorted(set(want) - {q["id"] for q in qs})
        if unknown:
            raise SystemExit(f"unknown question ids: {unknown}")
        qs = [q for q in qs if q["id"] in want]
    return qs


def ptok(messages: list[dict]) -> int:
    return sum(count_tokens(m["content"]) for m in messages) + TEMPLATE_OVERHEAD


def dry_run(questions: list[dict], tool: BM25Tool, cfg: PipelineConfig) -> None:
    r_in = [ptok(router_messages(q["question"])) for q in questions]
    d_in, rd_in = [], []
    for q in questions:
        hits = tool.search(q["question"])
        d_in.append(ptok(draft_messages(q["question"], hits, cfg.draft_system)))
        rd_in.append(ptok(redraft_messages(q["question"], hits, "", [], cfg.draft_system)) + cfg.draft_max_tokens + FEEDBACK_TOKENS)
    n = len(questions)
    r_res = sum(r_in) + n * cfg.router_max_tokens
    d_res = sum(d_in) + n * cfg.draft_max_tokens
    rd_res = sum(rd_in) + n * cfg.draft_max_tokens
    print(f"DRY RUN (no API calls). setting={tool.setting} ({tool.n_chunks} chunks, k={tool.k}"
          f"{', paper cover' if tool.cover else ', NO paper cover (baseline)'}), "
          f"{n} question(s): {', '.join(q['id'] for q in questions)}")
    print(f"router {cfg.router_model} max_tokens={cfg.router_max_tokens}; "
          f"draft {cfg.draft_model} max_tokens={cfg.draft_max_tokens}, effort {cfg.draft_effort}\n")
    print(f"{'model':<26}{'requests':>14}{'reserved tokens (prompt + max_tokens)':>40}")
    print(f"{cfg.router_model:<26}{n:>8} - {n:<4}{r_res:>18,} - {r_res:<,}")
    print(f"{cfg.draft_model:<26}{n:>8} - {2 * n:<4}{d_res:>18,} - {d_res + rd_res:<,}")
    print(f"{'TOTAL':<26}{2 * n:>8} - {3 * n:<4}{r_res + d_res:>18,} - {r_res + d_res + rd_res:<,}")
    print(f"\nlow = no redraft, high = every question redrafts. Draft prompt mean {statistics.mean(d_in):.0f} "
          f"tokens (min {min(d_in)}, max {max(d_in)}); router prompt mean {statistics.mean(r_in):.0f}.")
    print(f"At 8K tokens/min per model (bucket starts full): 120b needs about "
          f"{max(0, d_res - 8000) / (8000 / 60) / 60:.1f}-{max(0, d_res + rd_res - 8000) / (8000 / 60) / 60:.1f} min "
          f"of token budget; sequential calls take ~2-4 s each.")
    print("Retrieval uses the question as is. Out-of-scope routes skip the draft (fewer calls than shown).")
    print("\nNothing was sent. Re-run with --go to make real calls.")


async def go(questions: list[dict], tool: BM25Tool, cfg: PipelineConfig, standin: bool = False,
             pace: bool = True, heldout: bool = False, baseline: bool = False) -> int:
    from relay.model_client import GroqClient
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scenario = ("eval_heldout" if heldout else "eval") + ("_baseline" if baseline else "") + ("_standin" if standin else "")
    run_csv = RAW / f"run_{scenario}_{tool.setting}_{stamp}.csv"
    traces = RAW / f"traces_{scenario}_{tool.setting}_{stamp}.jsonl"
    server = None
    if standin:   # same workload against the stand-in, to validate it against the real runs (no Groq calls)
        sys.path.insert(0, str(ROOT / "standin"))
        from server import Standin, StandinConfig
        server = Standin(StandinConfig(seed=1))
        await server.start(port=8899)
        client = GroqClient(key="standin", api_url="http://127.0.0.1:8899/openai/v1/chat/completions",
                            source="stand-in")
    else:
        client = GroqClient()
    pipe = Pipeline(client, tool, ResultsWriter(run_csv), TraceWriter(traces), cfg)
    print(f"Writing {run_csv.relative_to(ROOT)} and {traces.relative_to(ROOT)}")
    bad = 0
    try:
        next_start = 0.0
        for i, q in enumerate(questions, 1):
            if pace:   # let the 120b token bucket (8,000/min) refill for this question's reservation first
                await asyncio.sleep(max(0.0, next_start - time.perf_counter()))
                reserve = ptok(draft_messages(q["question"], tool.search(q["question"]), cfg.draft_system)) + cfg.draft_max_tokens
                next_start = time.perf_counter() + reserve / (8000 / 60)
            res = await pipe.answer(q["question"], f"{scenario.replace('_', '-')}-{tool.setting}-{stamp}-{q['id']}", scenario)
            row = res["row"]
            print(f"  [{i}/{len(questions)}] {q['id']} {row['status']:<12} {res['outcome']:<22} "
                  f"ttft={row['first_token_ms']}ms total={row['total_ms']}ms retries={row['retries']} "
                  f"tokens={row['tokens_in']}/{row['tokens_out']}")
            bad = bad + 1 if row["status"] in ("rate_limited", "error") else 0
            if bad >= STOP_AFTER_BAD:
                print(f"Stopping: {STOP_AFTER_BAD} requests in a row ended rate_limited/error.")
                return 2
    except KeyboardInterrupt:
        print("Interrupted.")
        return 2
    finally:
        await client.aclose()
        if server:
            await server.stop()
    print(f"Done. Next: .venv\\Scripts\\python.exe scripts\\pregrade.py {run_csv.relative_to(ROOT)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setting", choices=list(RETRIEVAL_SETTINGS), default="medium")
    ap.add_argument("--questions", help="comma-separated ids, e.g. q01,q02 (default: all)")
    ap.add_argument("--heldout", action="store_true",
                    help="use eval/heldout.yaml (q27-q39, written after the 2026-11-18 changes; scenario eval_heldout)")
    ap.add_argument("--baseline", action="store_true",
                    help="run the system as it was before the 2026-11-18 changes (no paper cover, draft rules 1-4, "
                         "draft max_tokens 400), to compare with on the held-out set; scenario gets _baseline")
    ap.add_argument("--go", action="store_true", help="make real Groq calls (default: dry run)")
    ap.add_argument("--standin", action="store_true", help="run against the stand-in instead (no Groq calls)")
    ap.add_argument("--no-pace", action="store_true",
                    help="run questions back to back (default: wait for the 120b token bucket to refill between "
                         "questions, so latency is measured on an unloaded service)")
    args = ap.parse_args()
    questions = load_questions(args.questions, args.heldout)
    tool = BM25Tool(args.setting, cover=not args.baseline)
    cfg = (PipelineConfig(draft_max_tokens=400, draft_system=DRAFT_SYSTEM_BEFORE_COVER) if args.baseline
           else PipelineConfig())
    if not args.go and not args.standin:
        dry_run(questions, tool, cfg)
        return 0
    return asyncio.run(go(questions, tool, cfg, standin=args.standin, pace=not args.no_pace, heldout=args.heldout,
                            baseline=args.baseline))


if __name__ == "__main__":
    sys.exit(main())
