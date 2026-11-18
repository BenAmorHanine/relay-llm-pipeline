"""Rebuild results/results.csv from every raw run file results/raw/run_*.csv.

results.csv is derived: never edit it by hand, re-run this script. Raw run files are only read.
Rows are sorted by start_time (UTC ISO, so text order = time order), then request_id.
answer_grade is filled from results/raw/grades_<run>.csv (scripts/apply_grades.py); run files keep it empty.
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
from relay.recording import GRADES, RESULTS_COLUMNS, validate_row  # noqa: E402


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
    # grades: results/raw/grades_<run>.csv (scripts/apply_grades.py) fill answer_grade; raw run files untouched
    grade_of: dict[str, tuple[str, str]] = {}
    for gf in sorted(Path(raw_dir).glob("grades_*.csv")):
        with gf.open(encoding="utf-8", newline="") as fh:
            for i, g in enumerate(csv.DictReader(fh), 2):
                rid = g["request_id"]
                if rid in grade_of:
                    problems.append(f"{gf.name}:{i}: request_id {rid} already graded in {grade_of[rid][1]}")
                if g["answer_grade"] not in GRADES - {""}:
                    problems.append(f"{gf.name}:{i}: grade {g['answer_grade']!r}")
                if rid not in seen:
                    problems.append(f"{gf.name}:{i}: request_id {rid} is in no run file")
                grade_of[rid] = (g["answer_grade"], gf.name)
    # regrades: results/raw/regrades_<UTC>.csv (request_id, previous_grade, answer_grade, grade_from, reason), applied
    # in file order after the grades files; append-only corrections with an audit trail. Each line must name the
    # grade it replaces, so a regrade can never silently apply to the wrong grade.
    for rf in sorted(Path(raw_dir).glob("regrades_*.csv")):
        with rf.open(encoding="utf-8", newline="") as fh:
            for i, g in enumerate(csv.DictReader(fh), 2):
                rid = g["request_id"]
                cur = grade_of.get(rid, ("", ""))[0]
                if cur != g["previous_grade"]:
                    problems.append(f"{rf.name}:{i}: {rid} is graded {cur!r}, regrade says previous {g['previous_grade']!r}")
                if g["answer_grade"] not in GRADES - {""}:
                    problems.append(f"{rf.name}:{i}: grade {g['answer_grade']!r}")
                grade_of[rid] = (g["answer_grade"], rf.name)
    for row in rows:
        if row["request_id"] in grade_of:
            g = grade_of[row["request_id"]][0]
            if row["answer_grade"] and row["answer_grade"] != g:
                problems.append(f"{row['request_id']}: run file says {row['answer_grade']!r}, grades file {g!r}")
            row["answer_grade"] = g
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
