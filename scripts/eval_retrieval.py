"""Retrieval-only evaluation over eval/questions.yaml (no model calls).

Usage (from the repo root, cmd):
    .venv\\Scripts\\python.exe scripts\\eval_retrieval.py            # run, write raw file, print summary
    .venv\\Scripts\\python.exe scripts\\eval_retrieval.py --facts    # print the essential-facts table and check it
    .venv\\Scripts\\python.exe scripts\\eval_retrieval.py --no-table-context   # chunks without repeated table caption/header

Metrics per (setting, question):
    hit / first_gold_rank   a retrieved chunk from the gold paper whose page range covers a gold page
    gold coverage           share of gold (paper, page) items covered
    all gold papers         every gold paper has at least one covering chunk (cross-paper questions)
    fact hit                share of the question's key facts whose essential string (FACTS below)
                            appears in the retrieved context of that fact's paper, after
                            normalising both sides with match_norm()
    context_tokens          tokens that would be sent to the model
    top_score               top retrieval score (unanswerable questions: for a refusal threshold)

Retrieval variants:
    plain              global top-k
    quota_q1/quota_q2  global top-k, plus the top-q chunks of each paper, duplicates removed

Writes one JSON line per (variant, question) to a new results/raw/retrieval_eval_<UTC>.jsonl.
The functions here are also imported by scripts/bench_embeddings.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from relay.chunking import ALL_KINDS, DEFAULT_KINDS, ChunkConfig, build_chunks, load_blocks  # noqa: E402
from relay.retrieval import BM25Retriever, Hit, PerPaperQuota, RetrievalPipeline  # noqa: E402
from relay.textnorm import match_norm  # noqa: E402,F401  (shared with the pipeline's check)

PAPERS = ["1706.03762v7", "2410.00037v1", "2507.07955v2"]
A, M, H = PAPERS

# corpus name -> (block directory, section_aware, kinds)
CORPORA = {
    "naive": ("extracted", False, ALL_KINDS),
    "clean_flat": ("clean", False, DEFAULT_KINDS),
    "clean_sec": ("clean", True, DEFAULT_KINDS),
}
# setting name -> (piece size tokens, overlap tokens, pieces fetched, re-rank)
SETTINGS = {
    "small": (128, 16, 8, False),
    "medium": (256, 32, 5, False),
    "large": (512, 64, 3, False),
}

# Essential string per key fact, in the order of key_facts in eval/questions.yaml.
# (paper, string): the string must appear in retrieved chunks from that paper.
# None: the key fact is about how the answer is phrased, not something retrieval can contain.
FACTS: dict[str, list[tuple[str, str] | None]] = {
    "q01": [(A, "h = 8"), (A, "/h = 64")],
    "q02": [(A, "P100"), (A, "12 hours"), (A, "3.5 days")],
    "q03": [(A, "4000"), (A, "10^-9"), (A, "inverse square root")],
    "q04": [(M, "12.5Hz"), (M, "2048"), (M, "1.1kbps")],
    "q05": [(M, "160ms"), (M, "delay of 1")],
    "q06": [(M, "65%"), (M, "EPAD")],
    "q07": [(H, "0.03"), (H, "compression ratio")],
    "q08": [(H, "4.5-5 bytes"), (H, "6.0 bytes per chunk")],
    "q09": [(H, "30B"), (H, "200B")],
    "q10": [(A, "3.3 · 10^18")],
    "q11": [(H, "6.25 × 10^-4"), (H, "5.0 × 10^-4")],
    "q12": [(M, "26.6"), (M, "62.3"), (M, "22.8"), (M, "tripling")],
    "q13": [(A, "41.8"), (A, "41.0")],
    "q14": [(H, "3.6×"), (H, "nearly 4")],
    "q15": [(A, "grow large in magnitude"), (A, "small gradients"), (A, "variance d")],
    "q16": [(M, "WavLM"), (M, "7 levels"), (M, "57.8")],
    "q17": [(H, "cosine similarity"), (H, "≥0.5"), (H, "semantic shift")],
    "q18": [(A, "LayerNorm(x + Sublayer(x))"), (M, "RMS normalization"), (H, "RMSNorm")],
    "q19": [(M, "Depth Transformer"), (H, "Mamba-2")],
    "q20": [(H, "tokenizer-free"), (A, "byte-pair"), (M, "SentencePiece")],
    "q21": [(A, "ls = 0.1"), (H, "smoothing module"), None],
    "q22": [(H, "routing module"), (M, "80ms"), (A, "byte-pair")],
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_questions() -> list[dict]:
    return yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))


def corpus_chunks(corpus: str, setting: str, table_context: bool = True):
    d, sec_aware, kinds = CORPORA[corpus]
    size, overlap, _, _ = SETTINGS[setting]
    cfg = ChunkConfig(size, overlap, sec_aware, kinds, table_context)
    return [c for p in PAPERS for c in build_chunks(load_blocks(ROOT / "data" / "papers" / d / f"{p}.jsonl"), cfg)]


def score_question(q: dict, hits: list[Hit]) -> dict:
    gold = [(g["paper"], g["page"]) for g in q["gold"]]
    gold_hit = [any(h.chunk.covers(p, pg) for h in hits) for p, pg in gold]
    first = next((h.rank for h in hits if any(h.chunk.covers(p, pg) for p, pg in gold)), None)
    gpapers = sorted({p for p, _ in gold})
    papers_hit = sum(1 for p in gpapers if any(h.chunk.covers(p, pg) for h in hits for pp, pg in gold if pp == p))
    facts = FACTS.get(q["id"], [])
    checkable = [f for f in facts if f]
    ctx_by_paper = {p: match_norm("\n".join(h.chunk.text for h in hits if h.chunk.paper_id == p)) for p in PAPERS}
    fact_found = [match_norm(s) in ctx_by_paper[p] for p, s in checkable]
    return {
        "hit": bool(first) if gold else None,
        "first_gold_rank": first,
        "gold_items": len(gold), "gold_items_hit": sum(gold_hit),
        "gold_papers": len(gpapers), "gold_papers_hit": papers_hit,
        "facts_checkable": len(checkable), "facts_found": sum(fact_found),
        "fact_hit": (sum(fact_found) / len(checkable)) if checkable else None,
        "facts_missing": [s for (p, s), ok in zip(checkable, fact_found) if not ok],
        "context_tokens": sum(h.chunk.n_tokens for h in hits),
        "top_score": round(hits[0].score, 4) if hits else None,
        "retrieved": [{"chunk_id": h.chunk.chunk_id, "paper": h.chunk.paper_id,
                       "pages": [h.chunk.page_start, h.chunk.page_end],
                       "section": h.chunk.section_number or h.chunk.section_path[-1],
                       "kinds": h.chunk.kinds, "score": round(h.score, 4)} for h in hits],
    }


def summarize(label: str, rows: list[dict], n_chunks: int | None = None) -> dict:
    ans = [r for r in rows if not r["should_refuse"]]
    una = [r for r in rows if r["should_refuse"]]
    cross = [r for r in ans if r["gold_papers"] > 1]
    return {
        "setting": label, "chunks": n_chunks,
        "recall": sum(r["hit"] for r in ans) / len(ans),
        "mrr": sum(1 / r["first_gold_rank"] for r in ans if r["first_gold_rank"]) / len(ans),
        "fact_hit": statistics.mean(r["fact_hit"] for r in ans if r["fact_hit"] is not None),
        "all_papers": sum(1 for r in cross if r["gold_papers_hit"] == r["gold_papers"]),
        "multi_n": len(cross),
        "ctx_mean": statistics.mean(r["context_tokens"] for r in rows),
        "ctx_max": max(r["context_tokens"] for r in rows),
        "una_top": [r["top_score"] for r in una],
        "ans_top_med": statistics.median(r["top_score"] for r in ans),
    }


def print_summary(summary: list[dict]) -> None:
    print(f"{'setting':<28}{'chunks':>7}{'recall':>8}{'MRR':>7}{'fact hit':>9}{'all papers':>11}"
          f"{'ctx mean':>9}{'ctx max':>8}{'ans top med':>12}  unanswerable top scores")
    for s in summary:
        print(f"{s['setting']:<28}{s['chunks'] if s['chunks'] is not None else '-':>7}{s['recall'] * 100:>7.1f}%"
              f"{s['mrr']:>7.3f}{s['fact_hit'] * 100:>8.1f}%{str(s['all_papers']) + '/' + str(s['multi_n']):>11}"
              f"{s['ctx_mean']:>9.0f}{s['ctx_max']:>8}{s['ans_top_med']:>12.3f}  {[round(x, 3) for x in s['una_top']]}")
    print("recall / MRR / fact hit over answerable questions; all papers = multi-paper questions "
          "(gold in >1 paper) where every gold paper was retrieved.")


def check_facts_table() -> int:
    """Print the essential-facts table and verify each string exists in the clean text of its paper."""
    qs = {q["id"]: q for q in load_questions()}
    clean = {p: [json.loads(l) for l in (ROOT / "data" / "papers" / "clean" / f"{p}.jsonl").open(encoding="utf-8")]
             for p in PAPERS}
    naive = {p: [json.loads(l) for l in (ROOT / "data" / "papers" / "extracted" / f"{p}.jsonl").open(encoding="utf-8")]
             for p in PAPERS}
    bad = 0
    print(f"{'qid':<5}{'key fact':<58}{'paper':<14}{'essential':<28}{'gold page':>10}  clean pages / naive pages")
    for qid, facts in FACTS.items():
        q = qs[qid]
        gold_pages = {(g["paper"], g["page"]) for g in q["gold"]}
        if len(facts) != len(q["key_facts"]):
            print(f"{qid}: {len(facts)} essentials for {len(q['key_facts'])} key facts")
            bad += 1
        for kf, f in zip(q["key_facts"], facts):
            if f is None:
                print(f"{qid:<5}{kf[:56]:<58}{'-':<14}{'(not retrievable)':<28}")
                continue
            p, s = f
            cp = sorted({b["page"] for b in clean[p] if b["kind"] in DEFAULT_KINDS and match_norm(s) in match_norm(b["normalized"])})
            npg = sorted({b["page"] for b in naive[p] if match_norm(s) in match_norm(b["text"])})
            on_gold = any((p, pg) in gold_pages for pg in cp)
            bad += not cp
            print(f"{qid:<5}{kf[:56]:<58}{p:<14}{s:<28}{'yes' if on_gold else 'no':>10}  {cp[:8]} / {npg[:8]}")
    print(f"\n{bad} problem(s)")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts", action="store_true", help="print and check the essential-facts table only")
    ap.add_argument("--no-table-context", action="store_true",
                    help="do not repeat table caption title + header in chunks (the pre-Step-5 chunking)")
    args = ap.parse_args()
    if args.facts:
        return check_facts_table()

    questions = load_questions()
    qpath = ROOT / "eval" / "questions.yaml"
    out = ROOT / "results" / "raw" / f"retrieval_eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    fh = out.open("a", encoding="utf-8")

    def write(rec):
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()

    write({"type": "run_start", "time": datetime.now(timezone.utc).isoformat(), "script": "scripts/eval_retrieval.py",
           "table_context": not args.no_table_context, "questions_sha256": sha(qpath), "corpora": {k: [v[0], v[1], sorted(v[2])] for k, v in CORPORA.items()},
           "settings": SETTINGS, "variants": ["plain", "quota_q1", "quota_q2"],
           "retriever": "BM25 k1=1.5 b=0.75 (src/relay/retrieval.py)", "facts": FACTS,
           "inputs_sha256": {f"{d}/{p}.jsonl": sha(ROOT / "data" / "papers" / d / f"{p}.jsonl")
                             for d in ("extracted", "clean") for p in PAPERS}})

    summary, by_label = [], {}
    for corpus in CORPORA:
        for setting, (size, overlap, k, rerank) in SETTINGS.items():
            chunks = corpus_chunks(corpus, setting, not args.no_table_context)
            bm25 = BM25Retriever(chunks)
            variants = {"plain": RetrievalPipeline(bm25, final_k=k),
                        "quota_q1": PerPaperQuota(bm25, k=k, q=1, papers=PAPERS),
                        "quota_q2": PerPaperQuota(bm25, k=k, q=2, papers=PAPERS)}
            for vname, pipe in variants.items():
                label = f"{corpus}/{setting}/{vname}"
                rows = []
                for q in questions:
                    hits = pipe.search(q["question"])
                    rec = {"type": "result", "setting": label, "corpus": corpus, "piece_tokens": size,
                           "overlap_tokens": overlap, "section_aware": CORPORA[corpus][1], "pieces_fetched": k,
                           "variant": vname, "rerank": rerank,
                           "table_context": not args.no_table_context, "n_chunks": len(chunks), "qid": q["id"],
                           "qtype": q["type"], "should_refuse": q["should_refuse"], **score_question(q, hits)}
                    write(rec)
                    rows.append(rec)
                by_label[label] = rows
                summary.append(summarize(label, rows, len(chunks)))
    fh.close()
    print(f"Wrote {out.relative_to(ROOT)}\n")
    print_summary(summary)

    # questions where naive hits a gold page but misses the fact (plain variant)
    print("\nNaive hits a gold page but misses at least one essential fact that the same clean_sec setting finds:")
    for setting in SETTINGS:
        nv = {r["qid"]: r for r in by_label[f"naive/{setting}/plain"]}
        cs = {r["qid"]: r for r in by_label[f"clean_sec/{setting}/plain"]}
        for qid, r in nv.items():
            if r["hit"] and r["fact_hit"] is not None and r["fact_hit"] < 1:
                missing = r["facts_missing"]
                clean_found = [m for m in missing if m not in cs[qid]["facts_missing"]]
                print(f"  {setting:<7}{qid}: naive fact hit {r['fact_hit'] * 100:.0f}% missing {missing}"
                      f"{'  <- clean_sec finds ' + str(clean_found) if clean_found else ''}")
    labels = [s["setting"] for s in summary if s["setting"].endswith("/plain")]
    fail = [q["id"] for q in questions if not q["should_refuse"]
            and all(not next(r for r in by_label[l] if r["qid"] == q["id"])["hit"] for l in labels)]
    print(f"\nFail (no gold page) in every plain setting: {fail or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
