"""Build retrieval chunks from extracted or cleaned paper blocks.

Input: the JSONL block files written by scripts/extract_papers.py (naive) or
scripts/clean_papers.py (clean). Clean blocks carry `kind` and `normalized`;
naive blocks have neither, so every naive block is treated as kind "body" and
its raw `text` is used.

Parameters (ChunkConfig):
    target_tokens   upper bound on chunk size (gpt-oss tokenizer, o200k_harmony)
    overlap_tokens  trailing units of the previous chunk repeated at the start of the next
                    (never across a section boundary when section_aware is on)
    section_aware   True: a chunk never spans two sections; False: only papers are boundaries
    include_kinds   block kinds to keep; default drops reference, page_number,
                    header_footer and figure_text

Every chunk carries paper_id, section_path, section_number and page_start/page_end
(printed page numbers) so the drafting step can cite "paper, section, page".
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("o200k_harmony")

    def count_tokens(text: str) -> int:
        # disallowed_special=(): the papers contain literal strings like "<|endoftext|>"
        return len(_ENC.encode(text, disallowed_special=()))
except Exception:  # pragma: no cover
    def count_tokens(text: str) -> int:
        return max(1, len(text) // 4)

ALL_KINDS = frozenset({"body", "reference", "table", "figure_text", "equation", "header_footer", "page_number"})
DEFAULT_EXCLUDE = frozenset({"reference", "page_number", "header_footer", "figure_text"})
DEFAULT_KINDS = ALL_KINDS - DEFAULT_EXCLUDE

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


@dataclass(frozen=True)
class ChunkConfig:
    target_tokens: int = 256
    overlap_tokens: int = 32
    section_aware: bool = True
    include_kinds: frozenset = DEFAULT_KINDS

    def label(self) -> str:
        return f"t{self.target_tokens}-o{self.overlap_tokens}-{'sec' if self.section_aware else 'flat'}"


@dataclass
class Chunk:
    chunk_id: str
    paper_id: str
    section_path: list[str]
    section_number: str | None
    page_start: int
    page_end: int
    text: str
    n_tokens: int
    kinds: list[str]
    block_ids: list[str] = field(default_factory=list)

    def covers(self, paper_id: str, page: int) -> bool:
        return self.paper_id == paper_id and self.page_start <= page <= self.page_end

    def citation(self) -> str:
        sec = " ".join(x for x in (self.section_number, self.section_path[-1] if self.section_path else None) if x)
        pages = f"p.{self.page_start}" if self.page_start == self.page_end else f"pp.{self.page_start}-{self.page_end}"
        return f"[{self.paper_id}, {sec}, {pages}]"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class _Unit:
    text: str
    tokens: int
    page: int
    block_id: str
    kind: str
    paper_id: str
    section_path: tuple
    section_number: str | None


def load_blocks(path: str | Path) -> list[dict]:
    """Read a block JSONL file and normalise naive/clean records to one shape."""
    out = []
    with Path(path).open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            b = json.loads(line)
            clean = "kind" in b
            out.append({
                "block_id": b.get("block_id") or f"{b['paper_id']}-p{b['page']}-b{b.get('block_no', i)}",
                "paper_id": b["paper_id"],
                "page": b["page"],
                "kind": b["kind"] if clean else "body",
                "section_path": tuple(b.get("section_path") or [b.get("section", "")]),
                "section_number": b.get("section_number"),
                "text": b["normalized"] if clean else b["text"],
            })
    return out


def _split_block(text: str, kind: str, limit: int) -> list[str]:
    """Pieces of one block, each <= limit tokens: table rows / sentences / word windows."""
    text = text.strip()
    if not text:
        return []
    if count_tokens(text) <= limit:
        return [text]
    pieces = text.split("\n") if kind == "table" else _SENT.split(text)
    out: list[str] = []
    for p in pieces:
        p = p.strip()
        if not p:
            continue
        if count_tokens(p) <= limit:
            out.append(p)
            continue
        words, cur = p.split(), []
        for w in words:
            if cur and count_tokens(" ".join(cur + [w])) > limit:
                out.append(" ".join(cur))
                cur = []
            cur.append(w)
        if cur:
            out.append(" ".join(cur))
    return out


def build_chunks(blocks: list[dict], cfg: ChunkConfig = ChunkConfig()) -> list[Chunk]:
    units: list[_Unit] = []
    for b in blocks:
        if b["kind"] not in cfg.include_kinds:
            continue
        for piece in _split_block(b["text"], b["kind"], cfg.target_tokens):
            # +1: the separator ("\n" or " ") added when units are joined into a chunk
            units.append(_Unit(piece, count_tokens(piece) + 1, b["page"], b["block_id"], b["kind"], b["paper_id"],
                               b["section_path"], b["section_number"]))

    chunks: list[Chunk] = []
    cur: list[_Unit] = []

    def key(u: _Unit):
        return (u.paper_id, u.section_path) if cfg.section_aware else (u.paper_id,)

    def emit(us: list[_Unit]) -> None:
        if not us:
            return
        parts, prev = [], None
        for u in us:
            parts.append(("\n" if prev is not None and prev.block_id != u.block_id else " " if prev else "") + u.text)
            prev = u
        text = "".join(parts).strip()
        first = us[0]
        pid = first.paper_id
        n = sum(1 for c in chunks if c.paper_id == pid)
        chunks.append(Chunk(
            chunk_id=f"{pid}:{n:04d}",
            paper_id=pid,
            section_path=list(first.section_path),
            section_number=first.section_number,
            page_start=min(u.page for u in us),
            page_end=max(u.page for u in us),
            text=text,
            n_tokens=count_tokens(text),
            kinds=sorted({u.kind for u in us}),
            block_ids=list(dict.fromkeys(u.block_id for u in us)),
        ))

    def overlap_tail(us: list[_Unit]) -> list[_Unit]:
        tail, total = [], 0
        for u in reversed(us):
            if total + u.tokens > cfg.overlap_tokens:
                break
            tail.insert(0, u)
            total += u.tokens
        return tail

    for u in units:
        if cur and key(u) != key(cur[0]):
            emit(cur)
            cur = []
        if cur and sum(x.tokens for x in cur) + u.tokens > cfg.target_tokens:
            emit(cur)
            cur = overlap_tail(cur)
            # the overlap must leave room for the new unit
            while cur and sum(x.tokens for x in cur) + u.tokens > cfg.target_tokens:
                cur.pop(0)
        cur.append(u)
    emit(cur)
    return chunks
