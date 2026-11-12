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
    table_context   True: every chunk holding rows of a table starts with that table's
                    caption title (the caption's first sentence, e.g. "Table 2: The Transformer
                    achieves better BLEU scores ...") and header lines (see table_header below),
                    so a row such as "Transformer (base model) | 27.3 | 38.1 | 3.3 · 10^18" is
                    never retrieved without the column names that say what the numbers are.
                    The full caption block stays in the corpus once, as a normal unit.

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

# A table cell that is a value, not a label: "27.3", "65.9±1.7", "23.3%", "100K", "3.3 · 10^18", "12.5Hz".
_NUM_CELL = re.compile(r"[~∼≈<>]?[-+]?\d[\d.,]*\s*(?:%|[kKMBG]|s|ms|Hz|kHz|kbps|GB|×)?"
                       r"(?:\s*±\s*[\d.]+)?(?:\s*[·×]\s*10\^-?\d+)?")
_CAPTION = re.compile(r"^Table \d+\b")
HEADER_MAX_LINES = 4
HEADER_SCAN_LINES = 6


def table_header(text: str) -> list[str]:
    """Header lines of a rendered table: the lines before the first line with a numeric cell
    (at most HEADER_MAX_LINES). If no numeric line is found in the first HEADER_SCAN_LINES lines,
    or the first line is already numeric, only the first line is used."""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    for i, ln in enumerate(lines[:HEADER_SCAN_LINES]):
        if any(_NUM_CELL.fullmatch(c.strip()) for c in ln.split(" | ")):
            return lines[:min(i, HEADER_MAX_LINES)] if i > 0 else lines[:1]
    return lines[:1]


def caption_title(caption: str) -> str:
    """First sentence of a caption: "Table 3: Variations on the Transformer architecture." """
    c = " ".join(caption.split())
    return re.split(r"(?<=[.!?])\s+(?=[A-Z(])", c, maxsplit=1)[0]


def pair_table_captions(blocks: list[dict]) -> dict[str, str]:
    """caption block_id -> table body block_id. A caption is a one-line kind=table block starting
    "Table N"; its body is the nearest uncaptioned kind=table block within 2 positions on the same
    page of the same paper, looking forward first (captions above the table), then backward."""
    pairs: dict[str, str] = {}
    claimed: set[str] = set()
    for i, b in enumerate(blocks):
        t = b["text"].strip()
        if b["kind"] != "table" or not _CAPTION.match(t) or "\n" in t:
            continue
        for j in (i + 1, i + 2, i - 1, i - 2):
            if 0 <= j < len(blocks):
                o = blocks[j]
                if (o["kind"] == "table" and o["page"] == b["page"] and o["paper_id"] == b["paper_id"]
                        and not _CAPTION.match(o["text"].strip()) and o["block_id"] not in claimed):
                    pairs[b["block_id"]] = o["block_id"]
                    claimed.add(o["block_id"])
                    break
    return pairs


@dataclass(frozen=True)
class ChunkConfig:
    target_tokens: int = 256
    overlap_tokens: int = 32
    section_aware: bool = True
    include_kinds: frozenset = DEFAULT_KINDS
    table_context: bool = True

    def label(self) -> str:
        return (f"t{self.target_tokens}-o{self.overlap_tokens}-{'sec' if self.section_aware else 'flat'}"
                f"{'' if self.table_context else '-notablectx'}")


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
    ctx: str | None = None   # table caption + header repeated at the top of the chunk


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
                "caption": b.get("caption"),
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
    pairs = pair_table_captions(blocks) if cfg.table_context and "table" in cfg.include_kinds else {}
    by_id = {b["block_id"]: b for b in blocks}
    caption_of = {body: caption_title(by_id[cap]["text"]) for cap, body in pairs.items()}
    for b in blocks:
        if b["kind"] not in cfg.include_kinds:
            continue
        ctx, text = None, b["text"]
        if cfg.table_context and b["kind"] == "table" and not _CAPTION.match(text.strip()):
            header = table_header(text)
            rows = [ln for ln in text.split("\n") if ln.strip()][len(header):]
            ctx = "\n".join(([caption_of[b["block_id"]]] if b["block_id"] in caption_of else []) + header)
            if not rows:  # header only (one-line table): keep it as a plain unit
                ctx, text = None, ctx
            else:
                text = "\n".join(rows)
        ctx_cost = count_tokens(ctx) + 2 if ctx else 0
        for piece in _split_block(text, b["kind"], max(16, cfg.target_tokens - ctx_cost)):
            # +1: the separator ("\n" or " ") added when units are joined into a chunk
            units.append(_Unit(piece, count_tokens(piece) + 1, b["page"], b["block_id"], b["kind"], b["paper_id"],
                               b["section_path"], b["section_number"], ctx))

    chunks: list[Chunk] = []
    cur: list[_Unit] = []

    def key(u: _Unit):
        return (u.paper_id, u.section_path) if cfg.section_aware else (u.paper_id,)

    def cost(us: list[_Unit]) -> int:
        """Tokens of the units plus each distinct table context they will carry."""
        ctxs = dict.fromkeys(u.ctx for u in us if u.ctx)
        return sum(x.tokens for x in us) + sum(count_tokens(c) + 2 for c in ctxs)

    def emit(us: list[_Unit]) -> None:
        if not us:
            return
        parts, prev, shown = [], None, set()
        for u in us:
            new_line = prev is not None and (prev.block_id != u.block_id or u.kind == "table")
            sep = "\n" if new_line else " " if prev else ""  # table rows stay one per line
            if u.ctx and u.ctx not in shown:
                parts.append(("\n" if prev is not None else "") + u.ctx)
                shown.add(u.ctx)
                sep = "\n"
            parts.append(sep + u.text)
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
        if cur and cost(cur + [u]) > cfg.target_tokens:
            emit(cur)
            cur = overlap_tail(cur)
            # the overlap must leave room for the new unit
            while cur and cost(cur + [u]) > cfg.target_tokens:
                cur.pop(0)
        cur.append(u)
    emit(cur)
    return chunks
