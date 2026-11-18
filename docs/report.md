# The Relay: cited answers from three papers under real rate limits

Every number here is recomputable from `results/results.csv` (tables in `docs/tables.md`, built by `scripts/make_tables.py`) or from the raw files named. Decisions and their evidence are in `docs/DECISIONS.md`.

## 1. What it does
The pipeline answers engineers' questions **only** from three arXiv papers at pinned versions: "Attention Is All You Need" v7, Moshi v1 and H-Net / Dynamic Chunking v2. It always cites paper, section and page, and refuses when the papers don't say.

1. **Route** (gpt-oss-20b, 200 tokens): JSON `in_scope`. A deterministic guard keeps any question that names a paper term in scope. The router's keywords are logged, not used.
2. **Retrieve**: BM25 over cleaned, section-aware chunks (a tool call with a timeout).
   - Cleaning keeps superscripts and subscripts (`10^-9`), joins hyphenated words, rebuilds tables and fixes sections.
   - Each table's caption and header are repeated in every chunk that holds its rows.
3. **Draft** (gpt-oss-120b, low reasoning effort, 400 tokens): every claim cites a numbered passage `[n]`, or the draft gives one fixed refusal sentence.
4. **Check** (deterministic, no model):
   - every `[n]` exists;
   - every number in a sentence is in a passage that sentence cites, compared by value (`3.3 × 10¹⁸` = `3.3 · 10^18`, `100 000` = `100,000`);
   - a number without a citation fails.

   On failure there is **one** redraft; if that also fails, the reply refuses and shows the passages.
5. **Stream** the checked answer with its sources.

**The decision that shaped it:** draft fully, check, then stream. A wrong number never reaches the reader, at the price that time to first token (TTFT) ≈ the whole latency.

## 2. The real service (Groq free tier, measured)
145 calibration requests (2026-11-12), plus 104 real pipeline runs over two days:
- **Requests per minute:** 30 per model as a burst; after it, one request per 2.0 s measured from the last *accepted* request (passes at ≥ 2.009 s, failures at ≤ 1.996 s). A 429 consumes nothing.
- **Tokens per minute:** 8,000 per model, charged up front as prompt + `max_tokens`. **`max_tokens` is a throughput knob, not just a length cap.**
- **Requests per day:** 1,000, refilled one per 86.4 s, in whole periods only.
- **Per model:** each model has its own limits.
- **The daily-limit 429 looks like the per-minute one:** both have `error.type` "requests"; only the message says "per day".
- **Latency changes over time:** the median 20b first token for small requests was 715 ms on 2026-11-12; the median router first token was 421–432 ms on 2026-11-17.

## 3. The stand-in and how far to trust it
`standin/server.py` is a Groq-compatible streaming server, so the pipeline uses the same client.
- **Behaviour:** it resamples whole measured calls and enforces the measured requests-per-minute, tokens-per-minute and per-day rules, with identical headers and 429 bodies.
- **Assumptions:** slowdown under load (+10% per request in flight), a 1% 5xx rate and a 3% slow tail.

**Validation:** the same 26 questions, real against stand-in (`docs/standin.md`).
- The first calibration (2026-11-12 data only) was **1.6–1.9× too slow**.
- Calibration v2 adds the real medium-eval calls. **On the held-out small run** it is within 1.18× (router) and 1.09× (draft) of the real medians, with KS distance 0.37–0.42.
- Its p90 is heavier than real, and it never redrafts. All load results below use v2.

## 4. Answer quality (real Groq, 26 questions per setting)
| Setting | Correct and cited | Wrong | Correctly refused | Refused wrongly | Tokens per question |
|---|---|---|---|---|---|
| medium (256 tokens × 5) | 50.0% | 15.4% | 15.4% (4/4 unanswerable) | 19.2% | 1,872 |
| small (128 tokens × 8) | 46.2% | 7.7% | 15.4% (4/4 unanswerable) | 30.8% | 1,843 |

Real Groq, day 1 (2026-11-17): runs `run_eval_medium_20261117T102821Z` and `run_eval_small_20261117T103158Z`. These measure the system **before** the fixes below. The day-2 runs (large, plus medium on the current system) will be added as new rows.

- **The 26 questions:** written and verified in the PDFs by hand. 9 single-fact, 5 table-number, 3 explanation, 3 cross-paper, 2 term traps, 4 unanswerable.
- **Grading:** `pregrade.py` suggests a grade from a key-fact rubric plus a gold page+citation check, and every doubtful answer was reviewed. The rubric agreed with the final grade on 82.7% of day-1 answers (95% CI 70.3–90.6).
- **Day 1 measured the system before its fixes:**
  - 8 correct drafts were wrongly failed. The check misread `[0,1]` as a citation, a space-separated thousands number, superscript decimals, and "Paper 1". All four are fixed and frozen as regression tests.
  - The router refused an H-Net question as out of scope; a guard now prevents that.
- **What the check cannot catch:** one wrong answer passed (medium q19, "Helium is not a Transformer"). The check verifies citations and numbers, not claims made in words.
- **Unanswerable questions:** all 4 were refused in both settings.

## 5. Under load (stand-in, 10 min × 3 seeds per scenario)
| Scenario | Offered (per min) | Requests | Succeeded [95% CI] | Gave up | Rate-limited | First token p50 / p95 (ms) | Peak queue |
|---|---|---|---|---|---|---|---|
| steady | 3.0 | 84 | 100.0% [95.6, 100] | 0.0% | 0.0% | 1,208 / 2,702 | 2 |
| burst (40 requests in 20 s) | 6.3 | 146 | 27.4% [20.8, 35.1] | 72.6% | 0.0% | 1,413 / 10,697 | 46 |
| sustained overload | 20.7 | 616 | 23.4% [20.2, 26.9] | 76.6% | 0.0% | 9,983 / 14,646 | 12 |
| RPM halved (15) | 20.1 | 598 | 24.7% [21.5, 28.4] | 75.3% | 0.0% | 9,355 / 14,406 | 13 |
| daily budget exhausted | 10.7 | 316 | 32.9% [28.0, 38.3] | 28.5% | 38.6% | 543 / 12,767 | 6 |

- **Setup:** stand-in calibration v2, medium retrieval. Each user gives up after 15 s without a first token. Each scenario ran 600 s with 3 seeds, pooled; the seeds agree within 0.3–19 points on success (spread in `docs/tables.md`).
- **Where the first token comes from:** at steady load p50 is 1,208 ms; the real service on 2026-11-17 measured 432 ms router + 530 ms draft model first tokens.
- **Minor stalls:** three of the 15 runs had a 2–4 s stall (visible as gaps in their queue files), from CPU contention with 15 processes running at once.

- **What happens at the per-minute limit:** a rate gate per model holds requests until the wait has passed (retry-after plus jitter). Everyone waits in arrival order: nobody is shed, and nobody gets a weaker answer. People who see no first token within 15 s give up.
- **The cheap router saturates first:** each route reserves about 600 tokens (prompt 396 + `max_tokens` 200), so 20b admits only about 13 routes a minute.
  - In sustained overload, 975 of 1,257 429s came from the router's token limit.
  - With requests-per-minute halved to 15, **not one** 429 was a request-limit 429. Success was 24.7% [21.5, 28.4], against 23.4% [20.2, 26.9] with the full limit: no measurable difference.
  - The lever is the router's token reservation (a shorter prompt, a smaller `max_tokens`), not the request limit.
- **Daily limit:** never retried. The person immediately gets "Today's answer budget is used up… frees up again in about …", plus the retrieved passages marked as not checked by a model.

## 6. Retries
**Policy:**
- Retries happen only before the first token, and never past the call's timeout.
- A request-limit 429 waits retry-after measured from the last accepted request; a token-limit 429 waits it from now. Jitter is only ever added on top. At most 3 retries.
- 500/502/503/498 are retried once. Timeouts and daily limits are never retried.

**Two cases where retrying made things worse:**
1. Measured from an old accepted request, a daily-limit wait was already in the past, so the client fired 3 useless retries (fixed by recognising "per day").
2. Running real questions back to back, every draft after the first ~6 waited 7–12 s on token-limit 429s. The eval's latency measured its own throttling, so real evals are now paced.

## 7. Retrieval: quality versus cost
- **Settings:** three sizes, with no re-ranking: small (128 tokens × 8), medium (256 × 5) and large (512 × 3).
- **Re-ranking was measured and rejected:**
  - Embeddings were worse than BM25 at every size.
  - A MiniLM cross-encoder re-rank added about 1 s to first-token time and lowered fact hit.
  - TinyBERT gained 6.9 points only at medium, for a 1 GB dependency (`embed_bench_20261112T155413Z`).
- **Retrieval-only:** repeating each table's caption and header raised fact hit at medium from 67.0% to 75.0%.
- **End to end, day 1 (26 questions each):**
  - Medium answered more correctly (50.0% vs 46.2%) but also more wrongly (15.4% vs 7.7%).
  - Small refused more answerable questions (30.8% vs 19.2%).
  - With 26 questions, these differences are 1–3 questions, which is within noise.
  - Large and a medium re-run on the current system come on day 2. Until then medium stays the default: it ties with small on retrieval-only recall (90.9%; large 81.8%, `retrieval_eval_20261112T221926Z`), and it is what the load tests use.

## 8. How this library misleads a naive retriever
1. **Flattened exponents change numbers.** Naive extraction turns `3.3 · 10^18` FLOPs into `3.3 · 1018`. q10 (training cost) hits the right page and gets the wrong number, and q03 and q11 fail the same way in every naive setting.
2. **Table headers and rows end up in different chunks.** At 128/256 tokens, BM25 matched Table 2's "Training Cost (FLOPs)" header but never retrieved the base-model row, so q10's fact hit was 0 until the header was repeated in every chunk.
3. **The same word means different things in different papers.** "Smoothing" (label smoothing vs H-Net's smoothing module) and "chunking" pull passages from the wrong paper; the live system still fails the q21 term trap. Reference lists also match almost every keyword, and the PDF bookmarks label them "Conclusion".

## 9. Limits and open questions
- **Least certain assumption:** how the real service slows under concurrency. The free tier never allowed more than 5 requests in flight, so the stand-in's +10% per request is a guess. If the real slowdown is steeper, the overload results are optimistic.
- **Not measured:** the real tokens-per-day limit (documented as 200K), and any concurrency cap.
- **Small question set:** 26 questions give wide intervals; a difference of a few questions between settings is within noise.
- **Not built:** embeddings or re-ranking (measured and rejected), and streaming while checking (it could show a wrong number).
