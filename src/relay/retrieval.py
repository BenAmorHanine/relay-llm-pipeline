"""Retrieval over chunks: BM25 now, with slots for an embedding retriever and a re-ranker.

Why our own BM25 instead of a library (rank_bm25, bm25s, Pyserini):
    * ~60 lines, no dependency, and the scoring is Okapi BM25 exactly as written below,
      which is easy to explain and to change (tokenizer, k1, b) in a live session.
    * The corpus is ~1-3K chunks, so a pure-Python inverted index answers in a few ms.
    * We need to control tokenization for this library (keeping "d_k", "10^20" and
      "gpt-2" style tokens and their parts), which libraries leave to the caller anyway.

Extension points (not implemented yet, nothing extra installed):
    * Any object with `name` and `search(query, k) -> list[Hit]` is a Retriever.
      A local-embedding retriever (e.g. sentence-transformers all-MiniLM-L6-v2) only
      needs to implement that; FusionRetriever combines several by reciprocal rank fusion.
    * Any object with `name` and `rerank(query, hits, k) -> list[Hit]` is a Reranker
      (e.g. a cross-encoder). RetrievalPipeline fetches `fetch_k`, re-ranks, keeps `final_k`.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from typing import Protocol, Sequence

from .chunking import Chunk

STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have how i if in into is it its
of on or our over so such than that the their them then there these they this to under up was we were what
when where which while who why will with within would you your between each other both also more most
""".split())

_TOKEN = re.compile(r"[a-z0-9]+(?:[._^\-][a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    """Lowercase NFKC tokens; compound tokens (d_k, 10^20, gpt-2) also emit their parts."""
    t = unicodedata.normalize("NFKC", text).lower().replace("−", "-")
    out = []
    for tok in _TOKEN.findall(t):
        parts = re.split(r"[._^\-]", tok) if re.search(r"[._^\-]", tok) else []
        for w in [tok] + [p for p in parts if p]:
            if w in STOPWORDS or (len(w) == 1 and w.isalpha()):
                continue  # single letters only survive inside compounds such as "d_k"
            if len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
                w = w[:-1]  # light plural folding: "heads" -> "head"
            out.append(w)
    return out


@dataclass
class Hit:
    chunk: Chunk
    score: float
    rank: int
    retriever: str


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int) -> list[Hit]: ...


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, hits: list[Hit], k: int) -> list[Hit]: ...


class BM25Retriever:
    """Okapi BM25: score = sum_t idf(t) * tf*(k1+1) / (tf + k1*(1 - b + b*len/avglen)),
    idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5))  (always positive)."""

    def __init__(self, chunks: Sequence[Chunk], k1: float = 1.5, b: float = 0.75, name: str = "bm25"):
        self.name, self.k1, self.b = name, k1, b
        self.chunks = list(chunks)
        self.doc_len = []
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, c in enumerate(self.chunks):
            tf = Counter(tokenize(c.text))
            self.doc_len.append(sum(tf.values()))
            for term, n in tf.items():
                self.postings[term].append((i, n))
        self.N = len(self.chunks)
        self.avg_len = sum(self.doc_len) / max(self.N, 1)
        self.idf = {t: math.log(1 + (self.N - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

    def search(self, query: str, k: int) -> list[Hit]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in self.postings[term]:
                norm = self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avg_len)
                scores[i] += idf * tf * (self.k1 + 1) / (tf + norm)
        top = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:k]
        return [Hit(self.chunks[i], s, r + 1, self.name) for r, (i, s) in enumerate(top)]


class FusionRetriever:
    """Reciprocal rank fusion of several retrievers (e.g. BM25 + embeddings): score = sum 1/(c + rank)."""

    def __init__(self, retrievers: Sequence[Retriever], c: int = 60, per_retriever_k: int = 50):
        self.retrievers, self.c, self.per_k = list(retrievers), c, per_retriever_k
        self.name = "rrf(" + "+".join(r.name for r in self.retrievers) + ")"

    def search(self, query: str, k: int) -> list[Hit]:
        fused: dict[str, float] = defaultdict(float)
        by_id: dict[str, Chunk] = {}
        for r in self.retrievers:
            for h in r.search(query, self.per_k):
                fused[h.chunk.chunk_id] += 1.0 / (self.c + h.rank)
                by_id[h.chunk.chunk_id] = h.chunk
        top = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [Hit(by_id[cid], s, i + 1, self.name) for i, (cid, s) in enumerate(top)]


class PerPaperQuota:
    """Global top-k from a retriever, plus the top-q chunks of each paper, duplicates removed.
    Guarantees every paper a voice (cross-paper and term-trap questions) at the cost of context tokens.
    Order: the global top-k first, then the per-paper extras by score."""

    def __init__(self, retriever: Retriever, k: int, q: int, papers: Sequence[str], pool: int = 200):
        self.retriever, self.k, self.q, self.papers, self.pool = retriever, k, q, list(papers), pool
        self.name = f"{retriever.name}+quota{q}"

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        ranked = self.retriever.search(query, self.pool)
        chosen = ranked[: (k or self.k)]
        seen = {h.chunk.chunk_id for h in chosen}
        extras = []
        for p in self.papers:
            for h in [h for h in ranked if h.chunk.paper_id == p][: self.q]:
                if h.chunk.chunk_id not in seen:
                    extras.append(h)
                    seen.add(h.chunk.chunk_id)
        extras.sort(key=lambda h: -h.score)
        return [replace(h, rank=i + 1) for i, h in enumerate(chosen + extras)]


class RetrievalPipeline:
    """fetch_k candidates from the retriever, optional re-rank, keep final_k."""

    def __init__(self, retriever: Retriever, final_k: int, fetch_k: int | None = None,
                 reranker: Reranker | None = None):
        self.retriever, self.reranker = retriever, reranker
        self.final_k = final_k
        self.fetch_k = fetch_k or final_k

    def search(self, query: str) -> list[Hit]:
        hits = self.retriever.search(query, self.fetch_k if self.reranker else self.final_k)
        if self.reranker:
            hits = self.reranker.rerank(query, hits, self.final_k)
        return [replace(h, rank=i + 1) for i, h in enumerate(hits[: self.final_k])]
