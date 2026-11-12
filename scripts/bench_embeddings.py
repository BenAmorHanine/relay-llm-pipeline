"""Benchmark local embeddings and cross-encoder re-ranking (CPU), outside the project's environment.

NOT part of the project's requirements. Runs only in a throwaway venv, e.g. (cmd):
    py -3.12 -m venv %TEMP%\\relay_embed_bench\\venv
    %TEMP%\\relay_embed_bench\\venv\\Scripts\\python.exe -m pip install sentence-transformers tiktoken==0.14.0 pyyaml==6.0.3
    set HF_HOME=%TEMP%\\relay_embed_bench\\hf
    %TEMP%\\relay_embed_bench\\venv\\Scripts\\python.exe scripts\\bench_embeddings.py

Reads the project's clean chunks and questions (read-only) and writes one raw file
results/raw/embed_bench_<UTC>.jsonl with timings and per-question retrieval results.

Timings (20 runs each, after one warm-up call):
    corpus_embed_<setting>   embed all clean_sec chunks of that setting once (all-MiniLM-L6-v2)
    query_embed              embed one question
    rerank_<model>           cross-encoder scores for 20 BM25 candidates of one question
Quality on eval/questions.yaml (clean_sec, same k as the BM25 settings):
    emb                      embeddings alone (cosine)
    rrf_bm25_emb             reciprocal-rank fusion of BM25 and embeddings
    bm25_ce_<model>          BM25 top-20 re-ranked by the cross-encoder, keep k
"""

from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from sentence_transformers import CrossEncoder, SentenceTransformer  # noqa: E402

import eval_retrieval as ev  # noqa: E402
from relay.retrieval import BM25Retriever, FusionRetriever, Hit, RetrievalPipeline  # noqa: E402

EMB = "sentence-transformers/all-MiniLM-L6-v2"
CES = {"minilm_l6": "cross-encoder/ms-marco-MiniLM-L-6-v2", "tinybert_l2": "cross-encoder/ms-marco-TinyBERT-L-2-v2"}
RUNS = 20
FETCH = 20


def p50_p95(ms):
    """Nearest-rank percentiles, as in the other summaries."""
    import math
    s = sorted(ms)
    return s[math.ceil(0.5 * len(s)) - 1], s[math.ceil(0.95 * len(s)) - 1]


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


class EmbeddingRetriever:
    def __init__(self, model, chunks, emb_matrix):
        self.name, self.model, self.chunks, self.E = "emb", model, chunks, emb_matrix

    def search(self, query: str, k: int) -> list[Hit]:
        qv = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
        sims = self.E @ qv
        idx = np.argsort(-sims)[:k]
        return [Hit(self.chunks[i], float(sims[i]), r + 1, self.name) for r, i in enumerate(idx)]


class CrossEncoderReranker:
    def __init__(self, model, name):
        self.model, self.name = model, name

    def rerank(self, query: str, hits: list[Hit], k: int) -> list[Hit]:
        scores = self.model.predict([(query, h.chunk.text) for h in hits], batch_size=32)
        order = np.argsort(-np.asarray(scores))[:k]
        return [Hit(hits[i].chunk, float(scores[i]), r + 1, self.name) for r, i in enumerate(order)]


def main() -> int:
    out = ROOT / "results" / "raw" / f"embed_bench_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    fh = out.open("a", encoding="utf-8")

    def write(rec):
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()

    venv = Path(sys.prefix)
    hf = Path(os.environ.get("HF_HOME", ""))
    import sentence_transformers
    import transformers
    meta = {"type": "run_start", "time": datetime.now(timezone.utc).isoformat(), "script": "scripts/bench_embeddings.py",
            "python": sys.version.split()[0], "platform": platform.platform(), "processor": platform.processor(),
            "cpu_count": os.cpu_count(), "torch": torch.__version__, "torch_threads": torch.get_num_threads(),
            "sentence_transformers": sentence_transformers.__version__, "transformers": transformers.__version__,
            "venv": str(venv), "hf_home": str(hf), "runs": RUNS, "fetch_for_rerank": FETCH}
    write(meta)
    print(json.dumps(meta, indent=1))

    questions = ev.load_questions()
    chunks = {s: ev.corpus_chunks("clean_sec", s) for s in ev.SETTINGS}

    t = time.perf_counter()
    emb = SentenceTransformer(EMB, device="cpu")
    ces = {k: CrossEncoder(v, device="cpu") for k, v in CES.items()}
    load_s = time.perf_counter() - t
    print(f"models loaded in {load_s:.1f} s (includes download on first run); emb max_seq_length={emb.max_seq_length}")
    write({"type": "load", "seconds": round(load_s, 2), "emb_max_seq_length": emb.max_seq_length,
           "ce_max_length": {k: getattr(m, "max_length", None) for k, m in ces.items()}})

    timings = {}

    def timed(name, fn, n=RUNS):
        fn()  # warm-up
        ms = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn()
            ms.append((time.perf_counter() - t0) * 1000)
        p50, p95 = p50_p95(ms)
        timings[name] = {"n": n, "p50_ms": round(p50, 1), "p95_ms": round(p95, 1), "all_ms": [round(x, 1) for x in ms]}
        write({"type": "timing", "name": name, **timings[name]})
        print(f"  {name:<28} n={n} p50={p50:9.1f} ms  p95={p95:9.1f} ms")

    print("Timings:")
    E = {}
    for s, ch in chunks.items():
        texts = [c.text for c in ch]
        timed(f"corpus_embed_{s}({len(ch)} chunks)", lambda texts=texts: emb.encode(texts, batch_size=32,
                                                                                normalize_embeddings=True))
        E[s] = emb.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
    qtexts = [q["question"] for q in questions][:RUNS]
    it = iter(range(10 ** 9))
    timed("query_embed", lambda: emb.encode([qtexts[next(it) % len(qtexts)]], normalize_embeddings=True))
    bm25_med = BM25Retriever(chunks["medium"])
    cand = [bm25_med.search(q, FETCH) for q in qtexts]
    for name, ce in ces.items():
        it2 = iter(range(10 ** 9))

        def run(ce=ce):
            i = next(it2) % len(qtexts)
            ce.predict([(qtexts[i], h.chunk.text) for h in cand[i]], batch_size=32)
        timed(f"rerank_{name}(20 x medium)", run)

    print("\nQuality (clean_sec):")
    summary = []
    for s, (size, overlap, k, _) in ev.SETTINGS.items():
        bm25 = BM25Retriever(chunks[s])
        er = EmbeddingRetriever(emb, chunks[s], E[s])
        variants = {
            "bm25": RetrievalPipeline(bm25, final_k=k),
            "emb": RetrievalPipeline(er, final_k=k),
            "rrf_bm25_emb": RetrievalPipeline(FusionRetriever([bm25, er]), final_k=k),
        }
        for name, ce in ces.items():
            variants[f"bm25_ce_{name}"] = RetrievalPipeline(bm25, final_k=k, fetch_k=FETCH,
                                                            reranker=CrossEncoderReranker(ce, name))
        for vname, pipe in variants.items():
            label = f"clean_sec/{s}/{vname}"
            rows = []
            for q in questions:
                hits = pipe.search(q["question"])
                rec = {"type": "result", "setting": label, "variant": vname, "piece_tokens": size,
                       "pieces_fetched": k, "qid": q["id"], "qtype": q["type"], "should_refuse": q["should_refuse"],
                       **ev.score_question(q, hits)}
                write(rec)
                rows.append(rec)
            summary.append(ev.summarize(label, rows, len(chunks[s])))
    ev.print_summary(summary)

    sizes = {"venv_bytes": dir_size(venv), "hf_cache_bytes": dir_size(hf) if hf.exists() else None}
    try:
        sizes["torch_pkg_bytes"] = dir_size(Path(torch.__file__).parent)
    except Exception:
        pass
    write({"type": "disk", **sizes})
    print("\nDisk: " + ", ".join(f"{k}={v / 1e6:.0f} MB" for k, v in sizes.items() if v))
    write({"type": "run_end", "time": datetime.now(timezone.utc).isoformat()})
    fh.close()
    print(f"\nWrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
