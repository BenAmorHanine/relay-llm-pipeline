"""Suggest a grade for every answer in an eval run. No model calls, nothing in results/ is changed.

    .venv\\Scripts\\python.exe scripts\\pregrade.py results\\raw\\run_eval_medium_<UTC>.csv

Reads the run CSV and its traces (results/raw/traces_eval_<setting>_<UTC>.jsonl) and writes
eval/grades_<run>.csv with columns:
    qid, question, answer, citations, suggested_grade, reason, final_grade (empty: for you to fill)

Rules (suggestions only; you decide in final_grade):
    unanswerable question  -> refused_correctly if the answer refuses, else wrong
    answerable question    -> refused_wrongly if the answer refuses;
                              correct if every FACTS string (scripts/eval_retrieval.py) appears in the
                              answer AND at least one citation points to a gold paper + page; else wrong
    row status not ok      -> no suggestion (empty), the reason says why
"Refuses" = the pipeline outcome in the trace is refused, refused_out_of_scope or refused_check_failed.
The file is written with a UTF-8 BOM so Excel opens it correctly. An existing grades file is never
overwritten (it may already hold your final grades) unless --force.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from eval_retrieval import FACTS  # noqa: E402
from relay.textnorm import match_norm, number_values  # noqa: E402

GRADE_COLUMNS = ["qid", "question", "answer", "citations", "suggested_grade", "reason", "final_grade"]
REFUSALS = {"refused", "refused_out_of_scope", "refused_check_failed"}


def traces_for(run_csv: Path) -> Path:
    return run_csv.with_name(run_csv.name.replace("run_", "traces_", 1)).with_suffix(".jsonl")


def grades_path(run_csv: Path) -> Path:
    return ROOT / "eval" / f"grades_{run_csv.stem}.csv"


def suggest(q: dict, row: dict, tr: dict) -> tuple[str, str, str, str]:
    """(answer, citations, suggested_grade, reason) for one question."""
    steps = {s["step"]: s for s in tr["steps"]}       # later steps (recheck) overwrite earlier (check)
    answer = steps.get("stream", {}).get("answer", "")
    hits = {h["n"]: h for h in steps.get("retrieve", {}).get("hits", [])}
    final_check = steps.get("recheck") or steps.get("check") or {}
    cited = final_check.get("cited", []) if tr.get("outcome") == "answered" else []
    cites = [hits[n] for n in cited if n in hits]
    citations = "; ".join(f"[{h['n']}] {h['paper']} p.{h['page_start']}"
                          + (f"-{h['page_end']}" if h["page_end"] != h["page_start"] else "") for h in cites)
    outcome = tr.get("outcome")
    if row["status"] != "ok":
        return answer, citations, "", f"no answer: status {row['status']} ({outcome})"
    refuses = outcome in REFUSALS
    if q["should_refuse"]:
        return (answer, citations, "refused_correctly", f"unanswerable and refused ({outcome})") if refuses \
            else (answer, citations, "wrong", "unanswerable but answered")
    if refuses:
        return answer, citations, "refused_wrongly", f"answerable but refused ({outcome})"
    body = match_norm(answer.split("\n\nSources:")[0])
    facts = [s for f in FACTS.get(q["id"], []) if f for s in [f[1]]]
    raw_body = answer.split("\n\nSources:")[0]
    vals = number_values(raw_body)
    squash = body.replace(" ", "")

    def present(fact: str) -> bool:
        """String match, ignoring spaces (12.5 Hz = 12.5Hz), or for a fact with numbers: all its values are in
        the answer, compared like the check (10⁻⁹ = 10^-9, 6.25 × 10⁻⁴ = 6.25e-4, 30 billion ~ 30B -> 30)."""
        f = match_norm(fact)
        if f in body or f.replace(" ", "") in squash:
            return True
        fv = number_values(fact)
        return bool(fv) and fv <= vals

    missing = [s for s in facts if not present(s)]
    gold = [(g["paper"], g["page"]) for g in q["gold"]]
    gold_cited = any(h["paper"] == p and h["page_start"] <= pg <= h["page_end"] for h in cites for p, pg in gold)
    if not facts:
        return answer, citations, "wrong", "no FACTS entry for this question: grade by hand"
    if not missing and gold_cited:
        return answer, citations, "correct", "all facts present; cites a gold paper+page"
    why = []
    if missing:
        why.append(f"missing facts {missing}")
    if not gold_cited:
        why.append("no citation on a gold paper+page")
    return answer, citations, "wrong", "; ".join(why)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_csv", type=Path)
    ap.add_argument("--force", action="store_true", help="overwrite an existing grades file")
    args = ap.parse_args()
    run_csv = args.run_csv if args.run_csv.is_absolute() else ROOT / args.run_csv
    out = grades_path(run_csv)
    if out.exists() and not args.force:
        raise SystemExit(f"{out.relative_to(ROOT)} exists (it may hold your final grades); use --force to overwrite")
    qs = {q["id"]: q for f in ("questions.yaml", "heldout.yaml") if (ROOT / "eval" / f).exists()
          for q in yaml.safe_load((ROOT / "eval" / f).read_text(encoding="utf-8"))}
    traces: dict[str, dict] = {}
    for line in traces_for(run_csv).read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec.get("type") == "step":
            traces.setdefault(rec["request_id"], {"steps": []})["steps"].append(rec)
        elif rec.get("type") == "request":
            traces.setdefault(rec["request_id"], {"steps": []})["outcome"] = rec.get("outcome")
    with run_csv.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    counts: dict[str, int] = {}
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=GRADE_COLUMNS)
        w.writeheader()
        for row in rows:
            qid = row["request_id"].rsplit("-", 1)[-1]
            answer, citations, grade, reason = suggest(qs[qid], row, traces.get(row["request_id"], {"steps": []}))
            counts[grade or "(none)"] = counts.get(grade or "(none)", 0) + 1
            w.writerow({"qid": qid, "question": qs[qid]["question"], "answer": answer, "citations": citations,
                        "suggested_grade": grade, "reason": reason, "final_grade": ""})
    print(f"Wrote {out.relative_to(ROOT)}: {len(rows)} answers; suggested {counts}")
    print("Fill final_grade where you disagree (or everywhere); empty final_grade = accept the suggestion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
