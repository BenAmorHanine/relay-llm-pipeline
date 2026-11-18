"""Open-loop load test of the real pipeline against the stand-in (never the real Groq API).

    .venv\\Scripts\\python.exe loadtest\\run_load.py --scenario steady
    .venv\\Scripts\\python.exe loadtest\\run_load.py --all          # all five, in parallel processes

Each scenario starts its own stand-in (standin/server.py) on its own port, with fresh limits, and a
GroqClient pointed at it (source="stand-in"): the same client code, but no state shared with any real
client. Arrivals are Poisson (seeded); each simulated user asks a random question from
eval/questions.yaml and gives up if no first token arrives within GIVE_UP_S (status timeout).
Retrieval is the real local BM25 (medium).

Writes (append-only), per scenario:
    results/raw/run_<scenario>_<UTC>.csv     one results row per request
    results/raw/traces_<scenario>_<UTC>.jsonl
    results/raw/queue_<scenario>_<UTC>.csv   every 0.5 s: requests in the system, waiting for a first
                                             token, and in flight at the stand-in (cross-check only:
                                             the tables recompute peak queue from results.csv)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "standin"))
from relay.model_client import GroqClient  # noqa: E402
from relay.pipeline import BM25Tool, Pipeline  # noqa: E402
from relay.recording import ResultsWriter, TraceWriter  # noqa: E402
from server import Standin, StandinConfig  # noqa: E402

RAW = ROOT / "results" / "raw"
GIVE_UP_S = 15.0
FAIL_RATE, SLOW_RATE = 0.01, 0.03      # assumptions (no 5xx seen in the real runs); see docs/standin.md

# name -> (duration s, rate segments [(from_s, to_s, arrivals per minute)], stand-in overrides, port)
# 10-minute scenarios, run with several seeds (2026-11-17). The earlier 150 s versions are recorded in the
# "scenario" line of their own trace files (runs 20261113T*).
SCENARIOS = {
    "steady":             (600, [(0, 600, 3)], {}, 1),
    "burst":              (600, [(0, 120, 1), (120, 140, 120), (140, 600, 1)], {}, 2),
    "sustained_overload": (600, [(0, 600, 20)], {}, 3),
    "rpm_halved":         (600, [(0, 600, 20)], {"rpm": 15}, 4),
    "daily_exhausted":    (600, [(0, 600, 10)], {"rpd": 30}, 5),
}


def arrivals(segments, rng: random.Random) -> list[float]:
    out = []
    for a, b, per_min in segments:
        t = a
        while True:
            t += rng.expovariate(per_min / 60)
            if t >= b:
                break
            out.append(t)
    return out


async def run(name: str, run_seed: int = 1) -> None:
    duration, segments, overrides, slot = SCENARIOS[name]
    port = 8800 + 10 * run_seed + slot          # own port per (scenario, seed): no shared state
    seed = sum(map(ord, name)) * 1000 + run_seed
    rng = random.Random(seed)
    cfg = StandinConfig(fail_rate=FAIL_RATE, slow_rate=SLOW_RATE, seed=seed, **overrides)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"s{run_seed}_{stamp}"
    run_csv, traces = RAW / f"run_{name}_{tag}.csv", RAW / f"traces_{name}_{tag}.jsonl"
    queue_csv = RAW / f"queue_{name}_{tag}.csv"
    questions = yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))
    plan = arrivals(segments, rng)
    picks = [rng.choice(questions) for _ in plan]

    standin = Standin(cfg)
    await standin.start(port=port)
    client = GroqClient(key="standin", api_url=f"http://127.0.0.1:{port}/openai/v1/chat/completions",
                        source="stand-in")
    pipe = Pipeline(client, BM25Tool("medium"), ResultsWriter(run_csv), TraceWriter(traces))
    TraceWriter(traces).write({"type": "scenario", "scenario": name, "duration_s": duration, "segments": segments,
                               "standin_config": {k: v for k, v in cfg.__dict__.items()}, "give_up_s": GIVE_UP_S,
                               "seed": seed, "run_seed": run_seed, "planned_arrivals": len(plan),
                               "calibration_sha256": hashlib.sha256((ROOT / "standin" / "calibration.json")
                                                                    .read_bytes()).hexdigest(),
                               "calibration_sources": json.loads((ROOT / "standin" / "calibration.json")
                                                                 .read_text(encoding="utf-8"))["sources"]})
    state = {"in_system": 0, "waiting": 0}
    t0 = time.perf_counter()

    async def user(i: int, at: float, q: dict) -> None:
        await asyncio.sleep(max(0.0, at - (time.perf_counter() - t0)))
        state["in_system"] += 1
        state["waiting"] += 1
        got = {"first": False}

        def sink(_piece: str) -> None:
            if not got["first"]:
                got["first"] = True
                state["waiting"] -= 1
        try:
            await pipe.answer(q["question"], f"{name}-s{run_seed}-{stamp}-{i:04d}", name, sink=sink, give_up_s=GIVE_UP_S)
        finally:
            if not got["first"]:
                state["waiting"] -= 1
            state["in_system"] -= 1

    async def sampler(stop: asyncio.Event) -> None:
        with queue_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "in_system", "waiting_first_token", "standin_in_flight"])
            while not stop.is_set():
                w.writerow([round(time.perf_counter() - t0, 2), state["in_system"], state["waiting"], standin.in_flight])
                f.flush()
                try:
                    await asyncio.wait_for(stop.wait(), 0.5)
                except asyncio.TimeoutError:
                    pass

    stop = asyncio.Event()
    samp = asyncio.create_task(sampler(stop))
    print(f"[{name}] {len(plan)} arrivals over {duration} s, stand-in {overrides or 'defaults'} on port {port}")
    await asyncio.gather(*(user(i, at, q) for i, (at, q) in enumerate(zip(plan, picks))))
    stop.set()
    await samp
    await client.aclose()
    await standin.stop()
    TraceWriter(traces).write({"type": "scenario_end", "scenario": name, "standin_counts": standin.counts,
                               "standin_max_in_flight": standin.max_in_flight,
                               "elapsed_s": round(time.perf_counter() - t0, 1)})
    rows = list(csv.DictReader(run_csv.open(encoding="utf-8")))
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"[{name}] done: {len(rows)} rows {by}; stand-in {standin.counts}; wrote {run_csv.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=list(SCENARIOS))
    ap.add_argument("--all", action="store_true", help="run all scenarios in parallel processes")
    ap.add_argument("--seeds", default="1", help="comma-separated run seeds, e.g. 1,2,3 (one process each)")
    args = ap.parse_args()
    if args.all:
        procs = [subprocess.Popen([sys.executable, __file__, "--scenario", s, "--seeds", seed])
                 for s in SCENARIOS for seed in args.seeds.split(",")]
        return max(p.wait() for p in procs)
    if not args.scenario:
        ap.error("--scenario or --all")
    for seed in args.seeds.split(","):
        asyncio.run(run(args.scenario, int(seed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
