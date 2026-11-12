"""Rebuild results/results.csv from every raw run file results/raw/run_*.csv.

results.csv is derived: never edit it by hand, re-run this script. Raw run files are only read.
Rows are sorted by start_time (UTC ISO, so text order = time order), then request_id.
The script refuses to write anything if a raw file has the wrong header, a row has a value
outside the brief's sets (relay.recording.validate_row), or a request_id appears twice.

Usage (cmd):
    .venv\\Scripts\\python.exe scripts\\build_results.py
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from relay.recording import RESULTS_COLUMNS, validate_row  # noqa: E402


def build(raw_dir: Path, out: Path) -> tuple[int, int]:
    files = sorted(Path(raw_dir).glob("run_*.csv"))
    rows, problems, seen = [], [], {}
    for f in files:
        with f.open(encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                continue
            if header != RESULTS_COLUMNS:
                problems.append(f"{f.name}: header {header}")
                continue
            for i, values in enumerate(reader, 2):
                row = dict(zip(header, values))
                if len(values) != len(header):
                    problems.append(f"{f.name}:{i}: {len(values)} values for {len(header)} columns")
                    continue
                problems += [f"{f.name}:{i}: {e}" for e in validate_row(row)]
                rid = row["request_id"]
                if rid in seen:
                    problems.append(f"{f.name}:{i}: request_id {rid} already in {seen[rid]}")
                seen[rid] = f"{f.name}:{i}"
                rows.append(row)
    if problems:
        raise SystemExit("Not writing results.csv:\n  " + "\n  ".join(problems))
    rows.sort(key=lambda r: (r["start_time"], r["request_id"]))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=RESULTS_COLUMNS)
        w.writeheader()
        w.writerows(rows)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, out)
    return len(files), len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", type=Path, default=ROOT / "results" / "raw")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "results.csv")
    args = ap.parse_args()
    n_files, n_rows = build(args.raw_dir, args.out)
    print(f"Rebuilt {args.out} from {n_files} raw run file(s): {n_rows} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
