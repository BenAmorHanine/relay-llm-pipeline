"""Download the three library papers at their exact arXiv versions.

Usage (from the repo root, cmd):
    python scripts\\fetch_papers.py

Writes data/papers/<id>v<N>.pdf and appends a row per download to
data/papers/MANIFEST.md (SHA-256, size, UTC download time, final URL).
Existing PDFs are not re-downloaded; their hash is re-checked against the
manifest instead.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAPERS = [
    ("1706.03762", 7, "Attention Is All You Need"),
    ("2410.00037", 1, "Moshi: a speech-text foundation model for real-time dialogue"),
    ("2507.07955", 2, "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling"),
]

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "papers"
MANIFEST = OUT_DIR / "MANIFEST.md"
USER_AGENT = "relay-fetch/0.1 (python urllib)"

HEADER = (
    "# Paper manifest\n\n"
    "Written by `scripts/fetch_papers.py`. Do not edit by hand.\n\n"
    "| File | arXiv id | Version | Title | SHA-256 | Bytes | Downloaded (UTC) | Final URL |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        ctype = resp.headers.get("Content-Type", "")
        data = resp.read()
        final_url = resp.geturl()
    if not data.startswith(b"%PDF"):
        raise RuntimeError(f"{url} did not return a PDF (Content-Type: {ctype})")
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return final_url


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST.exists():
        MANIFEST.write_text(HEADER, encoding="utf-8")
    manifest_text = MANIFEST.read_text(encoding="utf-8")

    for arxiv_id, version, title in PAPERS:
        name = f"{arxiv_id}v{version}.pdf"
        dest = OUT_DIR / name
        url = f"https://arxiv.org/pdf/{arxiv_id}v{version}"
        if dest.exists():
            digest = sha256(dest)
            status = "matches manifest" if digest in manifest_text else "NOT IN MANIFEST"
            print(f"{name}: already present, sha256={digest} ({status})")
            continue
        print(f"{name}: downloading {url}")
        final_url = download(url, dest)
        digest = sha256(dest)
        when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = (
            f"| {name} | {arxiv_id} | v{version} | {title} | `{digest}` | "
            f"{dest.stat().st_size} | {when} | {final_url} |\n"
        )
        with MANIFEST.open("a", encoding="utf-8") as f:
            f.write(row)
        print(f"{name}: sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
