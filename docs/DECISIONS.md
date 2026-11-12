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

### Retry policy
Retry policy: wait at least retry-after measured from the last accepted request; jitter only added on top, never subtracted. Decided by me from retry_20261112T145223Z, 2026-11-12.

### Refusal
Refusal is not decided by retrieval score: near-miss unanswerable questions (q23, q25) score higher than the answerable median. Refusal comes from the model reading the passages and from the check step. Decided by me from retrieval_eval_20261112T154135Z, 2026-11-12.

### Raw results and submission
Keep raw files untouched; submit a redacted copy produced by make_submission_copy.py. Decided by me, 2026-11-12.

### Environment
My terminal is cmd (Command Prompt), not PowerShell. Decided by me, 2026-11-12.

### Retrieval [12, 13]
BM25 on clean, section-aware chunks; no embeddings or cross-encoder in the project. Embeddings are worse than BM25 everywhere. MiniLM re-rank adds about 1 s to TTFT and lowers fact hit. TinyBERT gains +6.9 points only at medium, for a 1 GB dependency.
Evidence: results/raw/embed_bench_20261112T155413Z.jsonl. Decided by me, 2026-11-12.

### Time to first token [3]
Time to first token = first token of the final answer the user sees.
Evidence file: none (a definition, not a measurement). Decided by me, 2026-11-12.

### Check versus streaming [5]
The answer is drafted fully, checked, then streamed. The check is deterministic.
Evidence file: none. Decided by me, 2026-11-12.

### Failed check [8]
On a failed check: one redraft, then refuse and show the retrieved passages. Never loop more.
Evidence file: none. Decided by me, 2026-11-12.

### Models [1]
Router on openai/gpt-oss-20b, drafting on openai/gpt-oss-120b (limits are per model: cal-052).
Evidence: results/raw/calibration_20261112T141038Z.jsonl, record cal-052. Decided by me, 2026-11-12.

### Refusal (restated in Step 5)
Refusal is decided by the model and the check, not by a retrieval score (same decision as "Refusal" above).
Evidence: results/raw/retrieval_eval_20261112T154135Z.jsonl. Decided by me, 2026-11-12.

### Draft max_tokens
Draft max_tokens = 400.
Evidence: results/raw/calibration_20261112T141038Z.jsonl, cal-006..010 (120b, low effort, ~1.5K tokens in): 118–300 output tokens, 1/5 hit the 300 cap. Decided by me, 2026-11-12.

### Router max_tokens
Router max_tokens = 200.
Evidence: results/raw/calibration_20261112T141038Z.jsonl, 2/5 small 20b calls hit 128 (cal-014, cal-015). Decided by me, 2026-11-12.

### Router use and retrieval query
Retrieval uses the user's question as is. The router only decides in/out of scope; its keywords and papers are logged, not used. Reason: the retrieval evaluation measured the raw question. Decided by me, 2026-11-12.

### Retries (Step 5b) [17]
- Request-limit 429 (body type "requests"): wait retry-after measured from the last accepted request, jitter on top.
- Token-limit 429 (body type "tokens"): wait retry-after measured from now, jitter on top.
- Evidence: results/raw/retry_20261112T145223Z.jsonl, plus cal-056/057 in results/raw/calibration_20261112T141038Z.jsonl.
- 500/502/503/498: retry once, with the same jitter.
- A client timeout is never retried.

Decided by me, 2026-11-12.

### Check: numbers need citations
A sentence containing a number without a citation fails the check. Decided by me, 2026-11-12.

### How raw results flow into results.csv [26]
Each run writes results/raw/run_<scenario>_<UTC>.csv. scripts/build_results.py rebuilds results/results.csv from all raw run files, sorted by start_time, never edited by hand. Decided by me, 2026-11-12.

## Still open

From `docs/open_decisions.md`: 4, 6, 7, 11, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25.
- 6: the pipeline now makes 2 model calls per request (router, draft), plus at most one redraft. Not recorded as a decision yet.
- 18: the code retries per model call. Not recorded as a decision yet.
- 11 is partly settled: section-aware chunking is decided, but the sizes are still the three Table 3 settings.
- 17 is partly settled: the retry waits and the 5xx rule are decided. Still open:
  - the 429 retry count (code: 3);
  - the jitter size (code: 0–0.25 s);
  - the wait when a 429 has no retry-after (code: 2.0 s);
  - what an unknown 429 type does (code: measured from now).
