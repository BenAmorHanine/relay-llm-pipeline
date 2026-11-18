"""Text normalisation shared by the fact-hit metric (scripts/eval_retrieval.py) and the
deterministic answer check (relay.pipeline), so both compare strings the same way."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*(?:\^-?\d+)?")
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+")

_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_SUP_RUN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+(?:·[⁰¹²³⁴⁵⁶⁷⁸⁹]+)?")     # also d⁻⁰·⁵ (superscript decimal)
# 100 000 written with a narrow no-break / thin / no-break space as thousands separator (real draft, q02)
_SPACE_THOUSANDS = re.compile(r"(?<=\d)[   ](?=\d{3}(?!\d))")
_WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
_WORDS.pop("zero")

# value patterns, applied in this order; each match is blanked so it is not counted twice
_SCI_TIMES = re.compile(r"(\d+(?:\.\d+)?)\s*[×x*·]\s*10\s*\^?\s*([-+]?\d+)")      # 3.3 × 10^18, 6.25×10-4
_SCI_E = re.compile(r"(?<![a-z\d.])(\d+(?:\.\d+)?)e([-+]?\d+)(?![a-z\d])")           # 6.25e-4
_POW10 = re.compile(r"(?<![\d.])10\^([-+]?\d+)")                                      # 10^-9
_PLAIN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")                   # 100,000  12.5 (also in 12.5hz)
_WORD = re.compile(r"\b(" + "|".join(_WORDS) + r")\b")
# LaTeX fractions as drafts write them: \frac{1}{2}, \tfrac12, \dfrac{1}{2} (a digit or a {group} per argument)
_TEX_FRAC = re.compile(r"\\[dt]?frac\s*(?:\{\s*(\d+)\s*\}|(\d))\s*(?:\{\s*(\d+)\s*\}|(\d))")
# Fractions in words ("one-third", "two thirds", "one half"): read as number words they would give 1 or 2
_WORD_FRACTION = re.compile(r"\b(?:" + "|".join(_WORDS) + r")[-\s]+(?:half|halves|thirds?|quarters?|fourths?|fifths?"
                            r"|sixths?|sevenths?|eighths?|ninths?|tenths?)\b")


def match_norm(s: str) -> str:
    """NFKC, unicode minus -> '-', lowercase, whitespace collapsed, no spaces around ^ × ·."""
    s = unicodedata.normalize("NFKC", s).replace("−", "-").lower()
    s = re.sub(r"\s+", " ", s)
    return re.sub(r"\s*([\^×·])\s*", r"\1", s)


def numbers(s: str) -> list[str]:
    """Number tokens of match_norm(s): "3.3 · 10^18" -> ["3.3", "10^18"], "1,000" -> ["1000"],
    "65%" -> ["65"], "10^-9" -> ["10^-9"]. A trailing sentence period is not part of a number.
    (Used by the fact-hit metric; the answer check uses number_values.)"""
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


def _canon(mantissa: str, exp: int = 0) -> str:
    try:
        return str((Decimal(mantissa.replace(",", "")) * (Decimal(10) ** exp)).normalize())
    except InvalidOperation:
        return mantissa


def number_values(s: str, with_parts: bool = False) -> set[str]:
    """Numeric VALUES in s, so equivalent notations compare equal:
        3.3 × 10^18 = 3.3·10¹⁸ = 3.3 x 10^18 = 3.3*10^18 = 3.3e18     (×, ·, x, *, superscripts, e-notation)
        6.25 × 10^-4 = 6.25 × 10−4 = 6.25×10⁻⁴ = 6.25e-4               (caret, unicode minus, superscript minus)
        100,000 = 100000;  6.0 = 6;  eight = 8 (number words one..twelve);  12.5Hz -> 12.5;  160ms -> 160
    with_parts=True also adds the parts of a scientific number (3.3 and 10^18): used for the passage
    side, so an answer may quote either the whole value or a part of it. Different numbers stay different."""
    t = _SPACE_THOUSANDS.sub("", s)                                        # 100 000 -> 100000
    t = _SUP_RUN.sub(lambda m: "^" + m.group(0).translate(_SUP).replace("·", "."), t)   # 10⁻⁹ -> 10^-9
    t = unicodedata.normalize("NFKC", t).replace("−", "-").replace("‐", "-").lower()   # NFKC maps U+2011 to U+2010
    t = _TEX_FRAC.sub(lambda m: f" {m.group(1) or m.group(2)}/{m.group(3) or m.group(4)} ", t)   # \tfrac12 -> 1/2
    vals: set[str] = set()

    def blank(m: re.Match) -> str:
        return " " * (m.end() - m.start())

    def sci(m: re.Match) -> str:
        vals.add(_canon(m.group(1), int(m.group(2))))
        if with_parts:
            vals.add(_canon(m.group(1)))
            vals.add(_canon("1", int(m.group(2))))
        return blank(m)

    t = _SCI_TIMES.sub(sci, t)
    t = _SCI_E.sub(sci, t)

    def pow10(m: re.Match) -> str:
        vals.add(_canon("1", int(m.group(1))))
        return blank(m)

    t = _POW10.sub(pow10, t)

    def plain(m: re.Match) -> str:
        vals.add(_canon(m.group(0)))
        return blank(m)

    t = _PLAIN.sub(plain, t)
    t = _WORD_FRACTION.sub(blank, t)       # "one-third": a paraphrased ratio, not a quoted number (not checked)
    for w in _WORD.findall(t):
        vals.add(str(_WORDS[w]))
    return vals
