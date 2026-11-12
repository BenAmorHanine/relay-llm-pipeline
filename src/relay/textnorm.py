"""Text normalisation shared by the fact-hit metric (scripts/eval_retrieval.py) and the
deterministic answer check (relay.pipeline), so both compare strings the same way."""

from __future__ import annotations

import re
import unicodedata

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*(?:\^-?\d+)?")
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+")


def match_norm(s: str) -> str:
    """NFKC, unicode minus -> '-', lowercase, whitespace collapsed, no spaces around ^ × ·."""
    s = unicodedata.normalize("NFKC", s).replace("−", "-").lower()
    s = re.sub(r"\s+", " ", s)
    return re.sub(r"\s*([\^×·])\s*", r"\1", s)


def numbers(s: str) -> list[str]:
    """Number tokens of match_norm(s): "3.3 · 10^18" -> ["3.3", "10^18"], "1,000" -> ["1000"],
    "65%" -> ["65"], "10^-9" -> ["10^-9"]. A trailing sentence period is not part of a number."""
    out = []
    for m in _NUMBER.finditer(match_norm(s)):
        tok = m.group(0)
        if _THOUSANDS.fullmatch(tok):
            tok = tok.replace(",", "")
        elif "," in tok:  # "1, 2, 3" lists rendered without spaces: split them
            out.extend(t for t in tok.split(",") if t)
            continue
        out.append(tok)
    return out
