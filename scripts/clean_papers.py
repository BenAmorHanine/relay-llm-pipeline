"""Clean extraction of the library PDFs (span level), fixing docs/retriever_pitfalls.md.

Usage (from the repo root, cmd):
    .venv\\Scripts\\python.exe scripts\\clean_papers.py

Reads data/papers/<id>vN.pdf again with PyMuPDF ("rawdict": spans with font,
size, flags, baseline and per-character boxes) and writes
data/papers/clean/<id>vN.jsonl. data/papers/extracted/ is never touched.

One JSON object per output block:
    block_id        "<paper>-p<page>-<n>" (n = order on the page)
    paper_id, page  page = number printed on the page (equal to the PDF page index
                    for these three PDFs; checked in Step 4), pdf_page kept too
    bbox            union of the source blocks, PDF points, top-left origin
    kind            body | reference | table | figure_text | equation | header_footer | page_number
    caption         "Table 2" / "Figure 1" when the block is a caption, else null
    section, section_path, section_number
    text            rendered text: ^ superscripts, _ subscripts, hyphenation joined,
                    table rows one per line with " | " between cells, fractions as (a)/(b)
    normalized      NFKC(text), U+2212 minus -> "-", private-use glyphs dropped, spaces collapsed
    raw_text        the original PyMuPDF text of the source block(s), unchanged
    source_blocks   PyMuPDF block numbers this block was built from
    fixes           pitfall numbers (docs/retriever_pitfalls.md) that changed this block

Fix tags:
    1  section from text-detected "Abstract" / "References" / appendix headings
    2  superscript/subscript rendering from span size, baseline and flags
    3  table regions rendered row by row
    4  equation fragments merged, fractions rebuilt, CMEX glyphs mapped, NFKC normalization
    5  figure text tagged (inside drawing/image regions, or rotated)
    6  running headers/footers, arXiv stamp and page numbers tagged
    7  table/figure captions and tables moved to the section that first mentions them
    8  section number added from the heading block
    9  words split by line-end hyphens joined (keeps real compounds seen elsewhere)
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
PAPERS = ROOT / "data" / "papers"
OUT = PAPERS / "clean"

MATH_FONT = re.compile(r"CMMI|CMSY|CMEX|MSBM|MSAM|CMBSY|EUFM|EUSM|rsfs|Math|STIX", re.I)
CMEX_MAP = {"P": "∑", "X": "∑", "Q": "∏", "Y": "∏", "R": "∫", "Z": "∫"}
CAPTION = re.compile(r"^\s*(Table|Figure|Fig\.)\s*(\d+)\s*[:.]")
SECNUM = re.compile(r"^\s*(?:Appendix\s+)?((?:[A-Z]|\d+)(?:\.\d+)*)\.?\s+(?=\S)")
ARXIV_STAMP = re.compile(r"arXiv:\d{4}\.\d{4,5}v\d+\s+\[[a-z\-]+\.[A-Za-z]{2}\]")
WORD = re.compile(r"[A-Za-z][A-Za-z\-]*[A-Za-z]")


# ------------------------------------------------------------------ helpers ---

def is_pua(ch: str) -> bool:
    return 0xE000 <= ord(ch) <= 0xF8FF


def is_math_char(ch: str, font: str) -> bool:
    return bool(MATH_FONT.search(font)) or 0x1D400 <= ord(ch) <= 0x1D7FF or ch in "√∑∏∫≤≥∈≈∞→←⊙⊗∀∃∂∇"


SPACING_ACCENT = {"´": "́", "`": "̀", "¨": "̈", "˜": "̃",
                  "ˇ": "̌", "¸": "̧"}


def normalize(text: str) -> str:
    # LaTeX-style spacing accent before its letter ("D´efossez") -> composed letter ("Défossez")
    t = re.sub(r"([´`¨˜ˇ¸])\s?([A-Za-z])",
               lambda m: m.group(2) + SPACING_ACCENT[m.group(1)], text)
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("−", "-")
    t = "".join(c for c in t if not is_pua(c) and (c == "\n" or unicodedata.category(c) != "Cc"))
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" *\n *", "\n", t)
    return t.strip()


def span_text(span: dict) -> str:
    s = "".join(c["c"] for c in span["chars"])
    if "CMEX" in span["font"]:
        s = "".join(CMEX_MAP.get(c, c) for c in s)
    return s


def overlap_frac(a, b) -> float:
    """Fraction of rect a's area that lies inside rect b."""
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    area = max((a[2] - a[0]) * (a[3] - a[1]), 1e-6)
    return (x1 - x0) * (y1 - y0) / area


def union(rects):
    return [min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects)]


# ------------------------------------------------------------- span scripts ---

def line_scripts(line: dict) -> list[str]:
    """'sup' / 'sub' / '' per span, from size relative to the line's dominant size and baseline."""
    spans = line["spans"]
    alnum = [round(s["size"], 1) for s in spans if any(c["c"].isalnum() for c in s["chars"])]
    dom = max(alnum) if alnum else max(round(s["size"], 1) for s in spans)
    bases = sorted(s["origin"][1] for s in spans if round(s["size"], 1) == dom)
    base = bases[len(bases) // 2]
    out = []
    for s in spans:
        small = s["size"] <= 0.85 * dom
        if small and (s["origin"][1] < base - 0.8 or (s["flags"] & 1 and s["origin"][1] <= base)):
            out.append("sup")
        elif small and s["origin"][1] > base + 0.5:
            out.append("sub")
        else:
            out.append("")
    return out


def render_line(line: dict) -> tuple[str, bool]:
    """Line text with ^/_ markers. Returns (text, used_script_markers)."""
    parts, used, prev_sc = [], False, ""
    for s, sc in zip(line["spans"], line_scripts(line)):
        t = span_text(s)
        if sc and t.strip():
            lead = t[: len(t) - len(t.lstrip())]
            cont = sc == prev_sc and not lead and parts and not parts[-1].endswith(" ")
            parts.append(lead + ("" if cont else ("^" if sc == "sup" else "_")) + t.strip())
            used = True
            prev_sc = sc
        else:
            parts.append(t)
            if t.strip():
                prev_sc = ""
    return "".join(parts), used


# -------------------------------------------------------------- hyphenation ---

def build_vocab(doc) -> Counter:
    """Words as they appear inside lines (not split at a line end), with and without hyphens."""
    vocab = Counter()
    for page in doc:
        for line in page.get_text("text").splitlines():
            toks = WORD.findall(line)
            if line.rstrip().endswith("-") and toks:
                toks = toks[:-1]
            vocab.update(t.lower() for t in toks)
    return vocab


def join_lines(lines: list[str], vocab: Counter) -> tuple[str, int]:
    """Join a block's lines with spaces; undo line-end hyphenation. Returns (text, joins)."""
    out, joins = "", 0
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if not out:
            out = ln
            continue
        m_left = re.search(r"([A-Za-z]+)-$", out)
        m_right = re.match(r"([a-z]+)", ln)
        if m_left and m_right:
            left, right = m_left.group(1).lower(), m_right.group(1)
            joined, hyph = left + right, f"{left}-{right}"
            if vocab[hyph] > vocab[joined]:
                out = out + ln  # keep the hyphen: a real compound seen elsewhere in the paper
            else:
                out = out[:-1] + ln
                joins += 1
            continue
        out = out + " " + ln
    return out, joins


# --------------------------------------------------------- equation render ---

def render_equation(blocks: list[dict], bars: list) -> str:
    """Char-level rendering of a group of display-math blocks: rows by baseline, fractions as (a)/(b)."""
    chars = []
    for b in blocks:
        for line in b["lines"]:
            for s, sc in zip(line["spans"], line_scripts(line)):
                for c in s["chars"]:
                    ch = c["c"]
                    if "CMEX" in s["font"]:
                        ch = CMEX_MAP.get(ch, ch)
                    if is_pua(ch):
                        continue
                    x0, y0, x1, y1 = c["bbox"]
                    chars.append({"c": ch, "x": (x0 + x1) / 2, "x0": x0, "x1": x1, "yc": (y0 + y1) / 2,
                                  "y0": y0, "y1": y1,
                                  "base": s["origin"][1], "size": s["size"], "sc": sc})
    if not chars:
        return ""
    gb = union([b["bbox"] for b in blocks])
    big = max(c["size"] for c in chars)

    # fractions: widest bars first; a bar needs characters both above and below it
    tokens = []
    used = set()
    for bar in sorted((r for r in bars if gb[1] - 4 <= r.y0 <= gb[3] + 4 and r.x0 >= gb[0] - 4 and r.x1 <= gb[2] + 4),
                      key=lambda r: -r.width):
        above = [i for i, c in enumerate(chars) if i not in used and bar.x0 - 1 <= c["x"] <= bar.x1 + 1
                 and bar.y0 - 1.6 * big <= c["base"] <= bar.y0 + 1.0]
        below = [i for i, c in enumerate(chars) if i not in used and bar.x0 - 1 <= c["x"] <= bar.x1 + 1
                 and bar.y1 < c["base"] <= bar.y1 + 1.6 * big]
        if above and below:
            used.update(above + below)
            num = _render_run([chars[i] for i in above])
            den = _render_run([chars[i] for i in below])
            tokens.append({"x": bar.x0, "x1": bar.x1, "base": bar.y0 + 2.5, "text": f"({num})/({den})"})

    rest = [c for i, c in enumerate(chars) if i not in used]
    # rows: baselines of full-size characters
    row_bases = []
    for c in sorted(rest, key=lambda c: c["base"]):
        if c["sc"]:
            continue
        if not row_bases or c["base"] - row_bases[-1] > 3.0:
            row_bases.append(c["base"])
    if not row_bases:
        row_bases = [rest[0]["base"]] if rest else [tokens[0]["base"]]
    rows = defaultdict(list)
    for c in rest:
        r = min(range(len(row_bases)), key=lambda i: abs(row_bases[i] - c["base"]))
        rows[r].append(c)
    for t in tokens:
        r = min(range(len(row_bases)), key=lambda i: abs(row_bases[i] - t["base"]))
        rows[r].append({"c": t["text"], "x": t["x"], "x0": t["x"], "x1": t["x1"], "sc": "", "size": big, "tok": True})
    out_rows = []
    for r in sorted(rows):
        out_rows.append(_render_run(sorted(rows[r], key=lambda c: c["x0"])))
    return " ; ".join(x for x in out_rows if x)


def _render_run(cs: list[dict]) -> str:
    cs = sorted(cs, key=lambda c: c["x0"])
    # group into runs: consecutive script characters (sup and sub together) form one run
    runs, cur = [], []
    for c in cs:
        if cur and bool(cur[-1]["sc"]) != bool(c["sc"]):
            runs.append(cur); cur = []
        cur.append(c)
    if cur:
        runs.append(cur)
    out, prev_x1 = "", None
    for run in runs:
        if prev_x1 is not None and run[0]["x0"] - prev_x1 > 0.25 * run[0]["size"] and not out.endswith(" "):
            out += " "
        if run[0]["sc"]:
            subs = "".join(c["c"] for c in run if c["sc"] == "sub")
            sups = "".join(c["c"] for c in run if c["sc"] == "sup")
            out += (f"_{subs}" if subs else "") + (f"^{sups}" if sups else "")
        else:
            seg, px = "", None
            for c in run:
                if c["c"].isspace():
                    if not seg.endswith(" "):
                        seg += " "
                    continue
                if px is not None and c["x0"] - px > 0.25 * c["size"] and not seg.endswith(" "):
                    seg += " "
                seg += c["c"]
                px = c["x1"]
            out += seg
        prev_x1 = max(c["x1"] for c in run)
    return out.strip()


# ------------------------------------------------------------- table render ---

def render_table(region, page_blocks: list[dict]) -> str:
    """Rows by baseline across all lines inside the region; ' | ' between cells (large x gaps)."""
    spans = []
    for b in page_blocks:
        for line in b["lines"]:
            lb = line["bbox"]
            if overlap_frac(lb, region) < 0.5:
                continue
            for s, sc in zip(line["spans"], line_scripts(line)):
                t = span_text(s)
                if not t.strip():
                    continue
                spans.append({"t": t, "x0": s["bbox"][0], "x1": s["bbox"][2], "base": s["origin"][1],
                              "size": s["size"], "sc": sc})
    rows: list[list[dict]] = []
    for s in sorted((s for s in spans if not s["sc"]), key=lambda s: s["base"]):
        if rows and abs(s["base"] - rows[-1][0]["base"]) <= 2.5:
            rows[-1].append(s)
        else:
            rows.append([s])
    for s in (s for s in spans if s["sc"]):
        if rows:
            min(rows, key=lambda r: abs(r[0]["base"] - s["base"])).append(s)
    lines = []
    for r in rows:
        r.sort(key=lambda s: s["x0"])
        txt, prev = "", None
        for s in r:
            t = s["t"]
            mark = ("^" if s["sc"] == "sup" else "_") if s["sc"] else ""
            if prev is not None:
                gap = s["x0"] - prev["x1"]
                if gap > 6:
                    txt = txt.rstrip() + " | "
                    t = t.lstrip()
                elif gap > 1.5 and not txt.endswith(" ") and not t.startswith(" ") and not mark:
                    txt += " "
            txt += (mark + t.strip()) if mark else t
            prev = s
        lines.append(re.sub(r"\s+", " ", txt).strip())
    return "\n".join(l for l in lines if l)


# ----------------------------------------------------------------- headings ---

@dataclass
class Heading:
    pdf_page: int        # 0-based
    y: float
    level: int
    title: str
    number: str | None = None
    source: str = "toc"  # toc | text


def block_text_plain(b: dict) -> str:
    return "\n".join("".join(span_text(s) for s in l["spans"]) for l in b["lines"])


def is_bold(b: dict) -> bool:
    fonts = [s["font"] for l in b["lines"] for s in l["spans"] if span_text(s).strip()]
    return bool(fonts) and all(("Bold" in f or "CMBX" in f or "Medi" in f or ".B" in f or "Bd" in f) for f in fonts)


# --------------------------------------------------------------------- main ---

@dataclass
class Out:
    pdf_page: int
    order: float
    bbox: list
    kind: str
    text: str
    raw_text: str
    source_blocks: list
    fixes: set = field(default_factory=set)
    caption: str | None = None
    heading_title: str | None = None


def clean_paper(pdf: Path) -> tuple[list[dict], dict]:
    doc = pymupdf.open(pdf)
    paper_id = pdf.stem
    vocab = build_vocab(doc)
    stats = Counter()

    # ---- pass 1: per-page raw blocks, regions
    pages = []
    for page in doc:
        rd = page.get_text("rawdict")
        blocks = [b for b in rd["blocks"] if b["type"] == 0 and any(span_text(s).strip() for l in b["lines"] for s in l["spans"])]
        try:
            tables = [list(t.bbox) for t in page.find_tables(strategy="lines").tables]
        except Exception:
            tables = []
        figs = []
        try:
            figs += [list(r) for r in page.cluster_drawings() if r.width >= 60 and r.height >= 40]
        except Exception:
            pass
        figs += [list(i["bbox"]) for i in page.get_image_info() if (i["bbox"][2] - i["bbox"][0]) >= 40]
        figs = [f for f in figs if not any(overlap_frac(f, t) > 0.5 for t in tables)]
        bars = [d["rect"] for d in page.get_drawings() if d["rect"].height < 1.5 and 3 < d["rect"].width < 220]
        pages.append({"page": page, "blocks": blocks, "tables": tables, "figs": figs, "bars": bars,
                      "H": page.rect.height, "W": page.rect.width})

    # ---- running header/footer texts: margin blocks repeated on >= 3 pages
    margin_counts = Counter()
    for p in pages:
        for b in p["blocks"]:
            if b["bbox"][3] < 0.08 * p["H"] or b["bbox"][1] > 0.92 * p["H"]:
                margin_counts[re.sub(r"\d+", "#", block_text_plain(b).strip())] += 1

    # ---- pass 2: classify / merge per page
    outs: list[Out] = []
    for p in pages:
        pg, H = p["page"], p["H"]
        consumed = set()
        # tables
        for ti, region in enumerate(p["tables"]):
            members = [b for b in p["blocks"] if overlap_frac(b["bbox"], region) > 0.5
                       and not _is_prose(b)]
            if not members:
                continue
            text = render_table(region, members)
            consumed.update(id(b) for b in members)
            outs.append(Out(pg.number, min(b["number"] for b in members), union([b["bbox"] for b in members]),
                            "table", text, "\n".join(block_text_plain(b) for b in members),
                            [b["number"] for b in members], {3, 2} if "^" in text or "_" in text else {3}))
        # equations: candidates, then merge vertically overlapping ones
        cands = []
        for b in p["blocks"]:
            if id(b) in consumed:
                continue
            chars = [(c["c"], s["font"]) for l in b["lines"] for s in l["spans"] for c in s["chars"] if not c["c"].isspace()]
            if not chars:
                continue
            math = sum(1 for ch, f in chars if is_math_char(ch, f) or is_pua(ch)) / len(chars)
            plain = block_text_plain(b).strip()
            in_fig = any(overlap_frac(b["bbox"], f) > 0.6 for f in p["figs"])
            if not in_fig and len(chars) <= 400 and (math >= 0.35 or re.fullmatch(r"\(\d+\)", plain)):
                cands.append(b)
        groups: list[list[dict]] = []
        for b in sorted(cands, key=lambda b: b["bbox"][1]):
            for g in groups:
                gb = union([x["bbox"] for x in g])
                if b["bbox"][1] <= gb[3] + 3 and b["bbox"][3] >= gb[1] - 3:
                    g.append(b)
                    break
            else:
                groups.append([b])
        for g in groups:
            # pull in short neighbours on the same band (e.g. ")V", "(1)")
            gb = union([x["bbox"] for x in g])
            for b in p["blocks"]:
                if id(b) in consumed or b in g:
                    continue
                t = block_text_plain(b).strip()
                near = b["bbox"][0] - gb[2] < 30 and gb[0] - b["bbox"][2] < 30
                same_band = b["bbox"][1] <= gb[3] + 1 and b["bbox"][3] >= gb[1] - 1
                short = len(t) <= 20 or (len(b["lines"]) == 1 and len(t) <= 80)
                if same_band and near and short:
                    g.append(b)
                    gb = union([x["bbox"] for x in g])
            text = render_equation(g, p["bars"])
            consumed.update(id(b) for b in g)
            fixes = {4}
            if "^" in text or "_" in text:
                fixes.add(2)
            outs.append(Out(pg.number, min(b["number"] for b in g), union([b["bbox"] for b in g]), "equation",
                            text, "\n".join(block_text_plain(b) for b in sorted(g, key=lambda b: b["number"])),
                            sorted(b["number"] for b in g), fixes))
        # everything else
        for b in p["blocks"]:
            if id(b) in consumed:
                continue
            plain = block_text_plain(b)
            stripped = plain.strip()
            x0, y0, x1, y1 = b["bbox"]
            fixes = set()
            rotated = any(abs(l["dir"][1]) > 0.5 for l in b["lines"])
            if re.fullmatch(r"\d{1,3}", stripped) and (y0 > 0.88 * H or y1 < 0.08 * H):
                kind = "page_number"; fixes.add(6)
            elif ARXIV_STAMP.search(stripped) or ((y1 < 0.08 * H or y0 > 0.92 * H)
                                                   and margin_counts[re.sub(r"\d+", "#", stripped)] >= 3):
                kind = "header_footer"; fixes.add(6)
            elif rotated:
                kind = "figure_text"; fixes.add(5)
            elif any(overlap_frac(b["bbox"], f) > 0.6 for f in p["figs"]) and not _is_prose(b) and not CAPTION.match(stripped):
                kind = "figure_text"; fixes.add(5)
            else:
                kind = "body"
            lines, used = [], False
            for l in b["lines"]:
                t, u = render_line(l)
                lines.append(t)
                used |= u
            if used:
                fixes.add(2)
            if kind in ("body",):
                text, joins = join_lines(lines, vocab)
                if joins:
                    fixes.add(9)
                    stats["hyphen_joins"] += joins
            else:
                text = " ".join(x.strip() for x in lines if x.strip())
            cap = CAPTION.match(stripped)
            o = Out(pg.number, b["number"], list(b["bbox"]), kind, text, plain, [b["number"]], fixes,
                    caption=(f"{'Figure' if cap.group(1).startswith('Fig') else cap.group(1)} {cap.group(2)}" if cap else None))
            if cap and cap.group(1) == "Table":
                o.kind = "table"
            o.heading_title = stripped if (len(b["lines"]) <= 2 and len(stripped) <= 90) else None
            o.bold = is_bold(b)
            outs.append(o)

    outs.sort(key=lambda o: (o.pdf_page, o.order))

    # ---- headings: outline (TOC) + text-detected Abstract / References / appendix headings
    heads: list[Heading] = []
    for level, title, page_no, dest in doc.get_toc(simple=False):
        if page_no < 1:
            continue
        to = dest.get("to")
        y = pages[page_no - 1]["H"] - to.y if to is not None else 0.0
        heads.append(Heading(page_no - 1, y, level, title.strip()))
    toc_titles = {h.title.lower() for h in heads}
    ref_head = None
    for o in outs:
        t = (o.heading_title or "").strip()
        if o.kind != "body" or not t:
            continue
        bare = SECNUM.sub("", t).strip()
        if re.fullmatch(r"Abstract", bare, re.I) and not any(h.title.lower() == "abstract" for h in heads):
            heads.append(Heading(o.pdf_page, o.bbox[1], 1, "Abstract", None, "text"))
        elif re.fullmatch(r"(References|Bibliography)", bare, re.I) and ref_head is None:
            ref_head = Heading(o.pdf_page, o.bbox[1], 1, "References", None, "text")
            heads.append(ref_head)
    if ref_head:
        # appendix headings after the references that the outline does not list
        for o in outs:
            if (o.pdf_page, o.bbox[1]) <= (ref_head.pdf_page, ref_head.y) or o.kind != "body" or not o.heading_title:
                continue
            t = o.heading_title.strip()
            if getattr(o, "bold", False) and "\n" not in t and len(t) <= 80 and SECNUM.sub("", t).lower() not in toc_titles \
                    and not t.endswith(".") and not re.match(r"^\[?\d+\]", t):
                m = SECNUM.match(t)
                lvl = (m.group(1).count(".") + 1) if m else 1
                heads.append(Heading(o.pdf_page, o.bbox[1], lvl, SECNUM.sub("", t).strip(), m.group(1) if m else None, "text"))
    heads.sort(key=lambda h: (h.pdf_page, h.y))

    # section numbers from the heading block near each outline anchor
    for h in heads:
        if h.number:
            continue
        for o in outs:
            if o.pdf_page != h.pdf_page or abs(o.bbox[1] - h.y) > 25 or o.kind not in ("body",):
                continue
            first = re.sub(r"\s+", " ", o.raw_text).strip()
            if h.title.lower()[:15] in first.lower():
                m = SECNUM.match(first)
                if m and m.group(1).lower() != h.title.lower()[:1]:
                    h.number = m.group(1)
                break

    # ---- assign sections in reading order
    hi, stack = -1, []
    in_refs = False
    for o in outs:
        while hi + 1 < len(heads) and (heads[hi + 1].pdf_page < o.pdf_page or
                                       (heads[hi + 1].pdf_page == o.pdf_page and heads[hi + 1].y <= o.bbox[1] + 2)):
            hi += 1
            h = heads[hi]
            while stack and stack[-1].level >= h.level:
                stack.pop()
            stack.append(h)
            in_refs = h is ref_head
        o.section_path = [h.title for h in stack] or ["(front matter)"]
        o.section = o.section_path[-1]
        o.section_number = next((h.number for h in reversed(stack) if h.number), None) if stack and stack[-1].number else None
        if stack and stack[-1].number:
            o.fixes.add(8)
        if any(h.source == "text" for h in stack):
            o.fixes.add(1)
        if in_refs and o.kind == "body":
            o.kind = "reference"
            o.fixes.add(1)

    # ---- pitfall 7: tables and captions go to the section that first mentions them
    first_mention: dict[str, tuple] = {}
    for o in outs:
        if o.kind != "body" or o.caption:
            continue
        for m in re.finditer(r"\b(Table|Figure|Fig\.)\s+(\d+)", o.text):
            key = f"{'Figure' if m.group(1).startswith('Fig') else 'Table'} {m.group(2)}"
            first_mention.setdefault(key, (o.section, o.section_path, o.section_number))
    for i, o in enumerate(outs):
        if not o.caption or o.caption not in first_mention:
            continue
        sec = first_mention[o.caption]
        targets = [o]
        if o.caption.startswith("Table"):
            # the table body nearest to the caption on the same page
            near = [x for x in outs if x.pdf_page == o.pdf_page and x.kind == "table" and not x.caption]
            if near:
                targets.append(min(near, key=lambda x: min(abs(x.bbox[1] - o.bbox[3]), abs(o.bbox[1] - x.bbox[3]))))
        for t in targets:
            if t.section_path != sec[1]:
                t.section, t.section_path, t.section_number = sec
                t.fixes.add(7)

    # ---- emit
    rows, per_page = [], Counter()
    for o in outs:
        per_page[o.pdf_page] += 1
        norm = normalize(o.text)
        if norm != o.text.strip() and (unicodedata.normalize("NFKC", o.text) != o.text or any(is_pua(c) for c in o.text)):
            o.fixes.add(4)
        rows.append({
            "block_id": f"{paper_id}-p{o.pdf_page + 1}-{per_page[o.pdf_page]:03d}",
            "paper_id": paper_id,
            "page": o.pdf_page + 1,
            "pdf_page": o.pdf_page + 1,
            "bbox": [round(v, 1) for v in o.bbox],
            "kind": o.kind,
            "caption": o.caption,
            "section": o.section,
            "section_path": o.section_path,
            "section_number": o.section_number,
            "text": o.text,
            "normalized": norm,
            "raw_text": o.raw_text,
            "source_blocks": o.source_blocks,
            "fixes": sorted(o.fixes),
        })
    stats["headings_text_detected"] = sum(1 for h in heads if h.source == "text")
    stats["headings_with_number"] = sum(1 for h in heads if h.number)
    stats["headings_total"] = len(heads)
    return rows, dict(stats)


def _is_prose(b: dict) -> bool:
    """Long running text (keeps paragraphs inside framed boxes from becoming table/figure text)."""
    lines = [("".join(span_text(s) for s in l["spans"])).strip() for l in b["lines"]]
    lines = [l for l in lines if l]
    if len(lines) < 2:
        return len(lines) == 1 and len(lines[0]) > 90
    avg = sum(len(l) for l in lines) / len(lines)
    words = sum(len(l.split()) for l in lines)
    nums = sum(1 for l in lines for w in l.split() if re.fullmatch(r"[\d.,%±×x()\-–]+", w))
    return avg > 60 and nums / max(words, 1) < 0.3


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(PAPERS.glob("*.pdf")):
        rows, stats = clean_paper(pdf)
        out = OUT / f"{pdf.stem}.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        kinds = Counter(r["kind"] for r in rows)
        print(f"{pdf.stem}: {len(rows)} blocks -> {out.relative_to(ROOT)}  kinds={dict(kinds)}  {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
