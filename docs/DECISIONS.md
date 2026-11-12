# Decisions

Numbers in brackets refer to `docs/open_decisions.md`.

## Decided

### Language
Python, using asyncio for concurrency and streaming.
*Decided by me, 2026-11-12.*

### Paper source [9]
PDF text extracted with PyMuPDF. The versioned PDF is the only format guaranteed to exist at the exact arXiv version, and it gives page numbers.
*Decided by me, 2026-11-12.*

### Citation format [10]
Paper + section + page.
*Decided by me, 2026-11-12.*

### Groq budget [2]
Calibrate first with a small number of requests. Hit the per-minute limit early, because it is cheap and recovers fast. Exhaust the per-day limit only once, on my last day of real runs, after all other real data is collected.
*Decided by me, 2026-11-12.*

### Extracted file naming
Files named <id>vN.jsonl, so the version travels with the data. Decided by me, 2026-11-12.

### Calibration run settings (scripts/calibrate.py)
- Total token cap raised from 35K to 42K (request cap stays 110). Decided by me, 2026-11-12.
- Total token cap raised from 42K to 43K. Reason: upper bound 42,662; I'd rather not lose a part-c request. Decided by me, 2026-11-12.
- Part a spacing: one request start every 15 s by default (`--a-spacing 15`), so the baseline fits the documented 8K TPM. Decided by me, 2026-11-12.
- b3 sent right after the first 429 in b1, while 120b is still limited, instead of after b2 recovers (which could not distinguish per-model from shared limits). b3 timing corrected by Claude, accepted by me, 2026-11-12.
- Safety margins: abort if x-ratelimit-remaining-requests < 800; abort if x-ratelimit-remaining-tokens < 500, checked only in parts a, b3 and c (b1, b2, b4 hit limits on purpose). Proposed by Claude, accepted by me, 2026-11-12.
- Keep the 60 s cooldowns (before b1, b4 and c) and temperature 0. Decided by me, 2026-11-12.
- A unique random marker at the start of every prompt in every part, so no request hits the prompt cache. Decided by me, 2026-11-12.
- Part a small requests: max output raised from 64 to 128 tokens. Decided by me, 2026-11-12.

### Environment
My terminal is cmd (Command Prompt), not PowerShell. Decided by me, 2026-11-12.

## Still open

From `docs/open_decisions.md`: 1, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26.
