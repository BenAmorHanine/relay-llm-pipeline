"""Turn your reviewed grades into a raw grades file; results/results.csv picks them up on rebuild.

    .venv\\Scripts\\python.exe scripts\\apply_grades.py eval\\grades_run_eval_medium_<UTC>.csv

Reads eval/grades_<run>.csv (from scripts/pregrade.py, after you filled final_grade) and the run
file results/raw/<run>.csv, and writes results/raw/grades_<run>.csv with columns
    request_id, qid, answer_grade, grade_from, suggested_grade
grade_from = "final" (your final_grade) or "suggested" (final_grade left empty, suggestion used).
Rows with neither (status not ok) get no grade. Raw run files are never modified (append-only rule);
scripts/build_results.py fills answer_grade in results/results.csv from the grades files.
An existing raw grades file is never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw"
sys.path.insert(0, str(ROOT / "src"))
from relay.recording import GRADES  # noqa: E402

GRADES_RAW_COLUMNS = ["request_id", "qid", "answer_grade", "grade_from", "suggested_grade"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("grades_csv", type=Path)
    args = ap.parse_args()
    g = args.grades_csv if args.grades_csv.is_absolute() else ROOT / args.grades_csv
    run_stem = g.stem.removeprefix("grades_")
    run_csv = RAW / f"{run_stem}.csv"
    out = RAW / f"grades_{run_stem}.csv"
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} already exists; raw files are never overwritten")
    with run_csv.open(encoding="utf-8", newline="") as f:
        rid_by_qid = {r["request_id"].rsplit("-", 1)[-1]: r["request_id"] for r in csv.DictReader(f)}
    rows, problems, counts = [], [], {"final": 0, "suggested": 0, "ungraded": 0}
    with g.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            final, sugg = r["final_grade"].strip(), r["suggested_grade"].strip()
            grade, src = (final, "final") if final else (sugg, "suggested")
            if not grade:
                counts["ungraded"] += 1
                continue
            if grade not in GRADES:
                problems.append(f"{r['qid']}: grade {grade!r} not in {sorted(GRADES - {''})}")
            if r["qid"] not in rid_by_qid:
                problems.append(f"{r['qid']}: not in {run_csv.name}")
                continue
            counts[src] += 1
            rows.append({"request_id": rid_by_qid[r["qid"]], "qid": r["qid"], "answer_grade": grade, "grade_from": src,
                         "suggested_grade": sugg})
    if problems:
        raise SystemExit("Nothing written:\n  " + "\n  ".join(problems))
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=GRADES_RAW_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out.relative_to(ROOT)}: {counts}. Now run scripts\\build_results.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
