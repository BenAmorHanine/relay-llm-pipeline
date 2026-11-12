"""Extract text blocks from the library PDFs with PyMuPDF.

Usage (from the repo root, cmd):
    .\\.venv\\Scripts\\python.exe scripts\\extract_papers.py

For each data/papers/<id>vN.pdf writes data/papers/extracted/<id>vN.jsonl,
one JSON object per PyMuPDF text block:

    paper_id      e.g. "1706.03762v7"
    page          1-based page number as printed by a PDF viewer
    block_no      PyMuPDF block number on that page (reading order PyMuPDF gives)
    bbox          [x0, y0, x1, y1] in PDF points, origin top-left
    section       title of the nearest preceding section heading
    section_path  list of titles from top-level section down to `section`
    text          block text, exactly as PyMuPDF returned it

Section headings come from the PDF outline (hyperref bookmarks), which gives
each heading's page and vertical position. A block belongs to the last heading
at or above its top edge. Blocks before the first heading get section
"(front matter)". This is extraction only: nothing is cleaned or filtered.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = ROOT / "data" / "papers"
OUT_DIR = PAPERS_DIR / "extracted"


def outline_headings(doc: pymupdf.Document) -> list[tuple[int, float, int, str]]:
    """Return (page_index, y_top, level, title), sorted by position in the doc."""
    heads = []
    for level, title, page_no, dest in doc.get_toc(simple=False):
        if page_no < 1:
            continue
        page = doc[page_no - 1]
        to = dest.get("to")
        # Outline destinations are in PDF space (origin bottom-left);
        # convert to PyMuPDF's top-left origin to compare with block bboxes.
        y_top = page.rect.height - to.y if to is not None else 0.0
        heads.append((page_no - 1, y_top, level, title.strip()))
    heads.sort(key=lambda h: (h[0], h[1]))
    return heads


def extract(pdf: Path) -> list[dict]:
    doc = pymupdf.open(pdf)
    paper_id = pdf.stem
    heads = outline_headings(doc)
    rows = []
    h_idx = -1
    path: list[tuple[int, str]] = []  # (level, title) stack

    for page in doc:
        for x0, y0, x1, y1, text, block_no, block_type in page.get_text("blocks", sort=False):
            if block_type != 0:  # 1 = image block
                continue
            # Advance through headings that start at or above this block's top
            # (2pt tolerance: outline anchors sit slightly above the heading text).
            while h_idx + 1 < len(heads) and (
                heads[h_idx + 1][0] < page.number
                or (heads[h_idx + 1][0] == page.number and heads[h_idx + 1][1] <= y0 + 2)
            ):
                h_idx += 1
                _, _, level, title = heads[h_idx]
                while path and path[-1][0] >= level:
                    path.pop()
                path.append((level, title))
            rows.append(
                {
                    "paper_id": paper_id,
                    "page": page.number + 1,
                    "block_no": block_no,
                    "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
                    "section": path[-1][1] if path else "(front matter)",
                    "section_path": [t for _, t in path] or ["(front matter)"],
                    "text": text,
                }
            )
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(PAPERS_DIR.glob("*.pdf"))
    if not pdfs:
        print("No PDFs in data/papers; run scripts/fetch_papers.py first.")
        return 1
    for pdf in pdfs:
        rows = extract(pdf)
        out = OUT_DIR / f"{pdf.stem}.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{pdf.stem}: {len(rows)} blocks -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
