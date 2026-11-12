"""Validate eval/questions.yaml against eval/SCHEMA.md (read-only; never edits the file).

Usage (from the repo root, cmd):
    .venv\\Scripts\\python.exe scripts\\validate_questions.py [eval\\questions.yaml]

Errors break the schema. Warnings are consistency checks against the clean
extraction (data/papers/clean): a gold section number that does not exist in
that paper, or whose pages do not include the gold page.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TYPES = {"single_fact", "table_number", "explanation", "cross_paper", "term_trap", "unanswerable"}
PAPERS = {"1706.03762v7": 15, "2410.00037v1": 66, "2507.07955v2": 39}
REQUIRED = {"id": str, "type": str, "question": str, "should_refuse": bool, "key_facts": list, "gold": list,
            "verified": bool}
OPTIONAL = {"note": str}


def section_pages() -> dict[tuple[str, str], set[int]]:
    """(paper, section_number) -> pages where clean blocks carry that number or a sub-number of it."""
    out: dict[tuple[str, str], set[int]] = defaultdict(set)
    for f in (ROOT / "data" / "papers" / "clean").glob("*.jsonl"):
        for line in f.open(encoding="utf-8"):
            b = json.loads(line)
            n = b.get("section_number")
            if not n:
                continue
            parts = n.split(".")
            for i in range(1, len(parts) + 1):
                out[(b["paper_id"], ".".join(parts[:i]))].add(b["page"])
    return out


def main(path: Path) -> int:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors, warnings = [], []
    if not isinstance(data, list):
        print("ERROR: top level is not a list")
        return 1
    secs = section_pages()
    ids = Counter()
    for i, q in enumerate(data):
        qid = q.get("id", f"#{i + 1}") if isinstance(q, dict) else f"#{i + 1}"
        if not isinstance(q, dict):
            errors.append(f"{qid}: not a mapping")
            continue
        ids[qid] += 1
        for k, t in REQUIRED.items():
            if k not in q:
                errors.append(f"{qid}: missing required field '{k}'")
            elif not isinstance(q[k], t):
                errors.append(f"{qid}: '{k}' should be {t.__name__}, is {type(q[k]).__name__}")
        for k in q:
            if k not in REQUIRED and k not in OPTIONAL:
                errors.append(f"{qid}: unknown field '{k}'")
        if "note" in q and not isinstance(q["note"], str):
            errors.append(f"{qid}: 'note' should be str")
        if not re.fullmatch(r"q\d{2}", str(qid)):
            errors.append(f"{qid}: id does not match q + two digits")
        if q.get("type") not in TYPES:
            errors.append(f"{qid}: type '{q.get('type')}' not in {sorted(TYPES)}")
        if isinstance(q.get("question"), str) and not q["question"].strip():
            errors.append(f"{qid}: empty question")
        if isinstance(q.get("should_refuse"), bool) and q.get("type") in TYPES:
            if q["should_refuse"] != (q["type"] == "unanswerable"):
                errors.append(f"{qid}: should_refuse={q['should_refuse']} but type={q['type']}")
        kf = q.get("key_facts")
        if isinstance(kf, list) and (not kf or not all(isinstance(x, str) and x.strip() for x in kf)):
            errors.append(f"{qid}: key_facts must be a non-empty list of non-empty strings")
        gold = q.get("gold")
        if isinstance(gold, list):
            if isinstance(q.get("should_refuse"), bool) and (len(gold) == 0) != q["should_refuse"]:
                errors.append(f"{qid}: gold has {len(gold)} items but should_refuse={q['should_refuse']}")
            for j, g in enumerate(gold):
                if not isinstance(g, dict) or set(g) != {"paper", "section", "page"}:
                    errors.append(f"{qid}: gold[{j}] must have exactly paper, section, page (has {g})")
                    continue
                if g["paper"] not in PAPERS:
                    errors.append(f"{qid}: gold[{j}] unknown paper '{g['paper']}'")
                    continue
                if not isinstance(g["page"], int) or not 1 <= g["page"] <= PAPERS[g["paper"]]:
                    errors.append(f"{qid}: gold[{j}] page {g['page']} outside 1..{PAPERS[g['paper']]}")
                    continue
                if not isinstance(g["section"], str) or not g["section"].strip():
                    errors.append(f"{qid}: gold[{j}] empty section")
                    continue
                m = re.match(r"^((?:[A-Z]|\d+)(?:\.\d+)*)\s", g["section"])
                if m:
                    pages = secs.get((g["paper"], m.group(1)))
                    if not pages:
                        warnings.append(f"{qid}: gold[{j}] section number {m.group(1)} not found in clean {g['paper']}")
                    elif g["page"] not in pages:
                        warnings.append(f"{qid}: gold[{j}] section {m.group(1)} spans pages "
                                        f"{min(pages)}-{max(pages)} in clean extraction; gold page is {g['page']}")
    for qid, n in ids.items():
        if n > 1:
            errors.append(f"{qid}: duplicate id ({n}x)")

    types = Counter(q.get("type") for q in data if isinstance(q, dict))
    print(f"{path}: {len(data)} questions; by type {dict(types)}; "
          f"should_refuse=true: {sum(1 for q in data if isinstance(q, dict) and q.get('should_refuse') is True)}")
    print(f"\nERRORS ({len(errors)}):")
    grouped = defaultdict(list)
    for e in errors:
        qid, msg = e.split(": ", 1)
        grouped[msg].append(qid)
    for msg, qids in grouped.items():
        print(f"  {msg}: {', '.join(qids) if len(qids) < 30 else f'{len(qids)} questions'}")
    print(f"\nWARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  {w}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "eval" / "questions.yaml"))
