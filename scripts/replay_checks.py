"""Replay every recorded real-eval draft through the check: the label rule used until 2026-11-19 against the
current one (which also treats arXiv ids such as "Paper 1706.03762v7" as labels).

No model calls. Rebuilds each draft's retrieved passages from the chunk ids in the raw traces and prints the
checks that flip (fail -> pass, pass -> fail). Evidence for the arXiv-id label fix (docs/DECISIONS.md).
    .venv\\Scripts\\python.exe scripts\\replay_checks.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import relay.pipeline as P  # noqa: E402
from relay.chunking import ChunkConfig, build_chunks, load_blocks  # noqa: E402
from relay.retrieval import Hit  # noqa: E402

OLD_LABEL = re.compile(r"\b(?:paper|passage)s?\s+\d+\b", re.I)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cmd uses cp1252
    chunks = {}
    for s, (size, overlap, _k) in P.RETRIEVAL_SETTINGS.items():
        for p in P.PAPERS:
            for c in build_chunks(load_blocks(P.CLEAN_DIR / f"{p}.jsonl"), ChunkConfig(size, overlap, section_aware=True)):
                chunks[(s, c.chunk_id)] = c
    new_label = P._LABEL_NUM
    to_pass, to_fail, n = [], [], 0
    try:
        for f in sorted((ROOT / "results" / "raw").glob("traces_eval_*.jsonl")):
            if "standin" in f.name:
                continue
            hits_of = {}
            for line in f.read_text(encoding="utf-8").splitlines():
                d = json.loads(line)
                if d.get("type") != "step":
                    continue
                rid = d["request_id"]
                if d["step"] == "retrieve":
                    hits_of[rid] = d.get("hits", [])
                elif d["step"] in ("draft", "redraft") and rid in hits_of and d.get("text") is not None:
                    setting = next((s for s in P.RETRIEVAL_SETTINGS if f"-{s}-" in rid), "medium")
                    hits = [Hit(chunks[(setting, h["chunk_id"])], h["score"], h["n"], "bm25") for h in hits_of[rid]]
                    P._LABEL_NUM = OLD_LABEL
                    before = P.check_answer(d["text"], hits, d.get("finish_reason"))
                    P._LABEL_NUM = new_label
                    after = P.check_answer(d["text"], hits, d.get("finish_reason"))
                    n += 1
                    if not before.ok and after.ok:
                        to_pass.append(f"{rid} {d['step']}")
                    if before.ok and not after.ok:
                        to_fail.append(f"{rid} {d['step']}: {after.errors}")
    finally:
        P._LABEL_NUM = new_label
    print(f"{n} recorded checks replayed")
    print(f"fail -> pass: {len(to_pass)}", *[f"  {x}" for x in to_pass], sep="\n")
    print(f"pass -> fail: {len(to_fail)}", *[f"  {x}" for x in to_fail], sep="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
