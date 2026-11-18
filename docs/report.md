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
145 calibration requests (2026-11-12), plus 4 real eval runs (104 questions, 2026-11-17 and 2026-11-18):
- **Requests per minute:** 30 per model as a burst; after it, one request per 2.0 s measured from the last *accepted* request (passes at ≥ 2.009 s, failures at ≤ 1.996 s). A 429 consumes nothing.
- **Tokens per minute:** 8,000 per model, charged up front as prompt + `max_tokens`. **`max_tokens` is a throughput knob, not just a length cap.**
- **Requests per day:** 1,000, refilled one per 86.4 s, in whole periods only.
- **Per model:** each model has its own limits.
- **The daily-limit 429 looks like the per-minute one:** both have `error.type` "requests"; only the message says "per day".
- **Latency changes over time:** the median 20b first token for small requests was 715 ms on 2026-11-12. The median router first token was 421–432 ms on 2026-11-17 and 606–677 ms on 2026-11-18; draft first token was 530–591 ms, then 811–830 ms. Day to day, the same calls moved by 1.4–1.6×.

## 3. The stand-in and how far to trust it
`standin/server.py` is a Groq-compatible streaming server, so the pipeline uses the same client.
- **Behaviour:** it resamples whole measured calls and enforces the measured requests-per-minute, tokens-per-minute and per-day rules, with identical headers and 429 bodies.
- **Assumptions:** slowdown under load (+10% per request in flight), a 1% 5xx rate and a 3% slow tail.

**Validation:** the same 26 questions, real against stand-in (`docs/standin.md`).
- The first calibration (2026-11-12 data only) was **1.6–1.9× too slow**.
- Calibration v2 adds the real medium-eval calls of 2026-11-17. It was tested on two runs it never saw:
  - **small, same day:** 1.18× (router) and 1.09× (draft) of the real medians, KS distance 0.37–0.42.
  - **large, the next day (2026-11-18):** 0.71× (router) and 0.80× (draft), KS distance 0.38–0.46. That day the real service itself was 1.4–1.6× slower than on the calibration day.
- **How far to trust it:** within 0.7–1.2× of the real model-call medians, about as far as the real service drifts between days. Read the load-test latencies as ±40%, not exact. The stand-in never redrafts. All load results below use v2.

## 4. Answer quality (real Groq, 26 questions per run)
| Run | System | Correct and cited [95% CI] | Wrong | Correctly refused | Refused wrongly | Tokens per question | First token p50 / p95 |
|---|---|---|---|---|---|---|---|
| large (512 tokens × 3), 2026-11-18 | current | 46.2% [28.8, 64.5] | 26.9% | 15.4% (4/4) | 11.5% | 1,993 | 1,800 / 3,244 ms |
| medium (256 tokens × 5), 2026-11-18 | current | 38.5% [22.4, 57.5] | 30.8% | 15.4% (4/4) | 15.4% | 1,934 | 1,676 / 2,925 ms |
| medium, 2026-11-17 | before day-1 fixes | 46.2% [28.8, 64.5] | 19.2% | 15.4% (4/4) | 19.2% | 1,872 | 9,546 / 22,574 ms |
| small (128 tokens × 8), 2026-11-17 | before day-1 fixes | 42.3% [25.5, 61.1] | 11.5% | 15.4% (4/4) | 30.8% | 1,843 | 9,870 / 22,728 ms |

Runs `run_eval_large_20261118T091718Z`, `run_eval_medium_20261118T092253Z`, `run_eval_medium_20261117T102821Z` and `run_eval_small_20261117T103158Z`. Each run is its own row (Table 3 in `docs/tables.md`); runs are never pooled across system versions.

- **The 26 questions:** written and verified in the PDFs by hand. 9 single-fact, 5 table-number, 3 explanation, 3 cross-paper, 2 term traps, 4 unanswerable.
- **Grading:** `pregrade.py` suggests a grade from a key-fact rubric plus a gold page+citation check, and every doubtful answer was reviewed, with the same rule for the same question across runs. The reason for every grade is in `eval/grades_*.csv`.
- **The grades were checked by a second, blind grader.** An independent agent regraded the 52 day-2 answers without seeing the first grades, using the same written rules.
  - It agreed on 50 of 52 (96.2%, 95% CI 87.0–98.9; Cohen's κ 0.94).
  - Both disagreements were q05: the answers give only the 160 ms theoretical latency, while the key facts also require the 200 ms reached in practice. The second grader was right; the rubric's fact string had checked only "160ms".
  - q05 was corrected to wrong in all four runs (append-only, `results/raw/regrades_20261118T110500Z.csv`), and the rubric string fixed.
  - After that correction, the rubric agrees with the final grade on 77.9% of the 104 answers (95% CI 69.0–84.8).
  - Caveat: both graders are LLM-based (the same model family). The agreement shows the grading rules are applied consistently, not that an outside human grader would agree.
- **Unanswerable questions:** all 4 were refused in every run (16/16). No run invented an answer to them.
- **What "wrong" means here.** The rubric is strict. Of the 15 wrong answers on 2026-11-18:
  - **3 are false claims made in words:** both runs' q19 (which parts of Moshi and H-Net are Transformers), and medium q03, which attributes Moshi's AdamW to the Transformer's training. The check verifies citations and numbers, so it cannot catch these.
  - **4 are term traps:** q21 and q22 in both runs. The answer covers one paper's meaning of "smoothing" or "chunking" and ignores the other's.
  - **8 are incomplete:** a required fact or paper is missing. One example is q13: the paper itself gives 41.8 and 41.0 BLEU, and the answer reports only one of them. Another is q05 (160 ms without the 200 ms in practice).
- **Day 1 against day 2, medium:** 4 of 26 questions changed.
  - q14 and q22 were refused before and are now answered. Both are graded wrong: q14 by the strict rule above (3.6× is the paper's body value; the abstract says "nearly 4×"), q22 as a term trap.
  - q03 went from correct to wrong (the AdamW mix-up): the model gives different answers on different runs.
  - q17 went from correct to refused, because of a new false check failure (below).

  The fixes turned wrong refusals into answers (refused wrongly: 19.2% → 15.4%), but those answers were mostly ones the strict rubric fails.
- **False check failures, found and fixed:**
  - **Day 1:** 8 correct drafts were failed. The check misread `[0,1]` as a citation, a space-separated thousands number, superscript decimals, and "Paper 1".
  - **Day 2:** 2 more. LaTeX `\tfrac12` was read as 12 (medium q17), and "one‑third" was read as the number word "one" (large q14). The second happened because NFKC turns the non-breaking hyphen U+2011 into U+2010, which the code did not map to "-".
  - All are fixed and frozen as regression tests (47 tests). Re-checking all 96 recorded first-draft checks with the fixed check turns no pass into a fail. The recorded runs are left as measured.
- **Latency on the real service:** with paced questions (day 2), first token p50 was 1.7–1.8 s and p95 2.9–3.2 s, with zero 429s in 104 calls. Day 1 ran questions back to back and spent 184–234 s per run waiting on token-limit 429s, so its 9.5–9.9 s p50 measures the eval's own throttling, not the pipeline.

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
2. Running real questions back to back, every draft after the first ~6 waited 7–12 s on token-limit 429s. The eval's latency measured its own throttling, so real evals are now paced. The paced day-2 runs had zero 429s in 104 calls, and first-token p50 fell from 9.5–9.9 s to 1.7–1.8 s.

## 7. Retrieval: quality versus cost
- **Settings:** three sizes, with no re-ranking: small (128 tokens × 8), medium (256 × 5) and large (512 × 3).
- **Re-ranking was measured and rejected:**
  - Embeddings were worse than BM25 at every size.
  - A MiniLM cross-encoder re-rank added about 1 s to first-token time and lowered fact hit.
  - TinyBERT gained 6.9 points only at medium, for a 1 GB dependency (`embed_bench_20261112T155413Z`).
- **Retrieval-only:** repeating each table's caption and header raised fact hit at medium from 67.0% to 75.0%.
- **End to end, current system (2026-11-18, same day, same questions):**
  - Large was correct on 12/26, medium on 10/26.
  - Paired by question, large was correct on 3 questions medium missed and medium on 1 that large missed (exact McNemar p = 0.63). That is no measurable difference.
  - Large costs about 3% more tokens per question (1,993 vs 1,934) and refused fewer answerable questions (11.5% vs 15.4%, one question).
- **End to end, before the fixes (2026-11-17):** medium and small were also within 1–3 questions of each other.
- **Decision: medium stays the default.**
  - No setting is measurably better end to end with 26 questions.
  - Medium ties with small on retrieval-only recall (90.9%; large 81.8%, `retrieval_eval_20261112T221926Z`).
  - The whole load campaign is measured on medium. Switching to large would mean re-running it, for a gain that cannot be told apart from noise.

## 8. How this library misleads a naive retriever
1. **Flattened exponents change numbers.** Naive extraction turns `3.3 · 10^18` FLOPs into `3.3 · 1018`. q10 (training cost) hits the right page and gets the wrong number, and q03 and q11 fail the same way in every naive setting.
2. **Table headers and rows end up in different chunks.** At 128/256 tokens, BM25 matched Table 2's "Training Cost (FLOPs)" header but never retrieved the base-model row, so q10's fact hit was 0 until the header was repeated in every chunk.
3. **The same word means different things in different papers.** "Smoothing" (label smoothing vs H-Net's smoothing module) and "chunking" pull passages from the wrong paper; the live system still fails the q21 term trap. Reference lists also match almost every keyword, and the PDF bookmarks label them "Conclusion".

## 9. Changes after day 2, and how they are measured
Day 2 showed where the wrong answers come from (section 4): answers that cover one paper when the question involves two, one value where the paper gives two, and details attached to the wrong paper. Two changes target these. Both are in the code, measured offline only so far.

1. **Paper cover (retrieval).** BM25 keeps its top-k. Then the best chunk of a missing paper is appended when the question:
   - names one of that paper's own terms, or
   - asks about all the papers, or
   - matches that paper's best chunk at ≥ 0.7 × the top score.

   Offline (`retrieval_eval_20261118T103625Z`), medium: fact hit 75.0% → 78.8%, recall unchanged at 90.9%, mean context +4.6%. Only 5 of 26 questions get an extra chunk; single-paper questions keep their passages. The blanket per-paper quota measured earlier gained as much for +30% context on every question.
2. **Draft rules.** The draft now has to:
   - name the paper for each statement and never attach one paper's detail to another's model;
   - answer for each paper asked about, and say which one the passages don't cover;
   - give each paper's meaning of a term the papers use differently;
   - report differing values side by side.

   Answers may run to 6 sentences, so `max_tokens` went from 400 to 500. Real drafts had reached 366 tokens, and a cut-off answer fails the check.

**Why a held-out set.** Both changes were designed from failures on q01–q26, so a gain measured on those questions alone would be optimistic.
- **The set:** 13 new questions, q27–q39 (`eval/heldout.yaml`), were written after the changes, checked against the PDF pages, and frozen by hash (`docs/DECISIONS.md`) before any run.
- **The kinds:** the same as q01–q26, including the three trap kinds the changes target: differing values (q29–q31), cross-paper (q35, q36) and a term trap (q37). Two are unanswerable (q38, q39).
- **How they run:** as their own scenario (`eval_heldout`), never pooled with q01–q26, and never used for tuning.

**The measurement:** two real runs of medium on q01–q26 plus q27–q39, graded by the rubric, then a reviewed grade, then the blind second grader.
- **The changes count as helping only if both sets improve.** If q01–q26 improve and the held-out set does not, that is reported as overfitting, not as a gain.
- Two runs show how much answers vary from run to run.
- After that measurement fixes the final configuration, the stand-in load campaign is re-run (section 5 describes the configuration before these changes).

## 10. Limits and open questions
- **Least certain assumption:** how the real service slows under concurrency. The free tier never allowed more than 5 requests in flight, so the stand-in's +10% per request is a guess. If the real slowdown is steeper, the overload results are optimistic.
- **Not measured:** the real tokens-per-day limit (documented as 200K), and any concurrency cap.
- **Small question set:** 26 questions give wide intervals (about ±18 points on correct %); a difference of a few questions between settings is within noise.
- **One run per setting and system:** the model gives different answers on different runs (medium q03 changed between days), so a single run per setting undercounts that variation. Small was not re-run on the current system.
- **Strict grading:** more than half of the "wrong" answers (8 of 15) are incomplete rather than false (section 4). A lenient grader would report higher accuracy from the same answers; the per-answer reasons in `eval/grades_*.csv` allow regrading.
- **Not built:** embeddings or re-ranking (measured and rejected), and streaming while checking (it could show a wrong number).
