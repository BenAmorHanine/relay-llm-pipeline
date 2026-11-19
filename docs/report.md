# The Relay: cited answers from three papers under real rate limits

Every number here is recomputable from `results/results.csv` (tables in `docs/tables.md`, built by `scripts/make_tables.py`) or from the raw files named. Decisions and their evidence are in `docs/DECISIONS.md`.

## 1. What it does
The pipeline answers engineers' questions **only** from three arXiv papers at pinned versions: "Attention Is All You Need" v7, Moshi v1 and H-Net / Dynamic Chunking v2. It always cites paper, section and page, and refuses when the papers don't say.

1. **Route** (gpt-oss-20b, 200 tokens): JSON `in_scope`. A deterministic guard keeps any question that names a paper term in scope. The router's keywords are logged, not used.
2. **Retrieve**: BM25 over cleaned, section-aware chunks (a tool call with a timeout), top 5, plus the best chunk of any paper the question calls for that is missing from them (the paper cover, section 9).
   - Cleaning keeps superscripts and subscripts (`10^-9`), joins hyphenated words, rebuilds tables and fixes sections.
   - Each table's caption and header are repeated in every chunk that holds its rows.
3. **Draft** (gpt-oss-120b, low reasoning effort, 500 tokens): every claim cites a numbered passage `[n]`, or the draft gives one fixed refusal sentence. When passages come from several papers, each statement names its paper, each paper asked about is covered, and differing values or meanings are given side by side.
4. **Check** (deterministic, no model):
   - every `[n]` exists;
   - every number in a sentence is in a passage that sentence cites, compared by value (`3.3 × 10¹⁸` = `3.3 · 10^18`, `100 000` = `100,000`);
   - a number without a citation fails;
   - labels are not numbers: "Paper 1", "passage 3" and arXiv ids such as "2410.00037v1".

   On failure there is **one** redraft; if that also fails, the reply refuses and shows the passages.
5. **Stream** the checked answer with its sources.

**The decision that shaped it:** draft fully, check, then stream. A wrong number never reaches the reader, at the price that time to first token (TTFT) ≈ the whole latency.

## 2. The real service (Groq free tier, measured)
145 calibration requests (2026-11-12), plus 7 real eval runs (156 questions, 2026-11-17 to 2026-11-19):
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

## 4. Answer quality (real Groq, q01–q26)
| Run | System | Correct and cited [95% CI] | Wrong | Correctly refused | Refused wrongly | Tokens per question | First token p50 / p95 |
|---|---|---|---|---|---|---|---|
| medium (256 tokens × 5), 2026-11-19 | **final** | 42.3% [25.5, 61.1] | 15.4% | 15.4% (4/4) | 26.9% | 2,524 | 1,338 / 3,618 ms |
| large (512 tokens × 3), 2026-11-18 | day-1 fixes, before paper cover | 46.2% [28.8, 64.5] | 26.9% | 15.4% (4/4) | 11.5% | 1,993 | 1,800 / 3,244 ms |
| medium (256 tokens × 5), 2026-11-18 | day-1 fixes, before paper cover | 38.5% [22.4, 57.5] | 30.8% | 15.4% (4/4) | 15.4% | 1,934 | 1,676 / 2,925 ms |
| medium, 2026-11-17 | before day-1 fixes | 46.2% [28.8, 64.5] | 19.2% | 15.4% (4/4) | 19.2% | 1,872 | 9,546 / 22,574 ms |
| small (128 tokens × 8), 2026-11-17 | before day-1 fixes | 42.3% [25.5, 61.1] | 11.5% | 15.4% (4/4) | 30.8% | 1,843 | 9,870 / 22,728 ms |

Runs `run_eval_medium_20261119T064116Z`, `run_eval_large_20261118T091718Z`, `run_eval_medium_20261118T092253Z`, `run_eval_medium_20261117T102821Z` and `run_eval_small_20261117T103158Z`. Each run is its own row (Table 3 in `docs/tables.md`); runs are never pooled across system versions. The held-out questions and the final verdict on the day-2 changes are in section 9.

- **The 26 questions:** written and verified in the PDFs by hand. 9 single-fact, 5 table-number, 3 explanation, 3 cross-paper, 2 term traps, 4 unanswerable.
- **Grading:** `pregrade.py` suggests a grade from a key-fact rubric plus a gold page+citation check, and every doubtful answer was reviewed, with the same rule for the same question across runs. The reason for every grade is in `eval/grades_*.csv`.
- **The grades were checked by a second, blind grader.** An independent agent regraded the 52 day-2 answers without seeing the first grades, using the same written rules, and a fresh one regraded the 52 answers of 2026-11-19 without seeing the first grades or which run each answer came from.
  - Day 2: it agreed on 50 of 52 (96.2%, 95% CI 87.0–98.9; Cohen's κ 0.94). 2026-11-19: 52 of 52. Pooled: 102/104 (98.1%, κ 0.97).
  - Both disagreements were q05: the answers give only the 160 ms theoretical latency, while the key facts also require the 200 ms reached in practice. The second grader was right; the rubric's fact string had checked only "160ms".
  - q05 was corrected to wrong in all four runs (append-only, `results/raw/regrades_20261118T110500Z.csv`), and the rubric string fixed.
  - After that correction, the rubric agrees with the final grade on 126 of 156 answers (80.8%, 95% CI 73.9–86.2).
  - Caveat: both graders are LLM-based (the same model family). The agreement shows the grading rules are applied consistently, not that an outside human grader would agree.
- **Unanswerable questions:** all were refused in every run: 20/20 on q01–q26 over five runs, and 4/4 on the held-out q38 and q39 over two runs. No run invented an answer to them.
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
  - **2026-11-19:** 7 more drafts (4 questions). The new draft rule makes the model name papers by arXiv id, and the check read "1706.03762v7" as the numbers 1706, 3762 and 7 (section 9).
  - All are fixed and frozen as regression tests (55 tests in total). `scripts/replay_checks.py` re-checks all 183 recorded real drafts: the last fix turns 7 fails into passes and no pass into a fail. The recorded runs are left as measured.
- **Latency on the real service:** with paced questions, first token p50 was 1.7–1.8 s and p95 2.9–3.2 s on day 2 (zero 429s in 104 calls), and 1.0–1.3 s / 2.8–3.6 s on 2026-11-19 (zero 429s in 113 calls). Day 1 ran questions back to back and spent 184–234 s per run waiting on token-limit 429s, so its 9.5–9.9 s p50 measures the eval's own throttling, not the pipeline.

## 5. Under load (stand-in, 10 min × 3 seeds per scenario)
| Scenario | Offered (per min) | Requests | Succeeded [95% CI] | Gave up | Rate-limited | First token p50 / p95 (ms) | Peak queue |
|---|---|---|---|---|---|---|---|
| steady | 3.0 | 84 | 100.0% [95.6, 100] | 0.0% | 0.0% | 1,252 / 2,717 | 2 |
| burst (40 requests in 20 s) | 6.3 | 146 | 24.7% [18.4, 32.2] | 75.3% | 0.0% | 1,443 / 7,822 | 46 |
| sustained overload | 20.7 | 616 | 19.2% [16.2, 22.5] | 80.8% | 0.0% | 9,341 / 14,818 | 13 |
| RPM halved (15) | 20.1 | 598 | 20.7% [17.7, 24.2] | 79.3% | 0.0% | 10,330 / 14,673 | 14 |
| daily budget exhausted | 10.7 | 316 | 32.0% [27.1, 37.3] | 40.5% | 27.5% | 1,243 / 12,591 | 7 |

- **Setup:** the final system (paper cover, draft rules, draft `max_tokens` 500, arXiv-id check fix), stand-in calibration v2, medium retrieval, run on 2026-11-19. Each user gives up after 15 s without a first token. Each scenario ran 600 s with 3 seeds, pooled; the seeds agree within 0–16 points on success (spread in `docs/tables.md`). The largest gap between queue snapshots was 2.4 s, so no run stalled.
- **Where the first token comes from:** at steady load p50 is 1,252 ms; the real service on 2026-11-17 measured 432 ms router + 530 ms draft model first tokens.
- **Against the campaign before the paper cover** (2026-11-17, same seeds and arrivals, excluded from the tables with that reason): steady is unchanged (100%), but sustained overload fell from 23.4% [20.2, 26.9] to 19.2% [16.2, 22.5] and burst from 27.4% to 24.7%. Each draft now reserves 100 more tokens (`max_tokens` 500) and carries longer prompts (the extra chunk), so fewer drafts fit in the 120b's 8,000 tokens a minute. The intervals overlap slightly, so this is a likely cost, not a proven one.

- **What happens at the per-minute limit:** a rate gate per model holds requests until the wait has passed (retry-after plus jitter). Everyone waits in arrival order: nobody is shed, and nobody gets a weaker answer. People who see no first token within 15 s give up.
- **The cheap router saturates first:** each route reserves about 600 tokens (prompt 396 + `max_tokens` 200), so 20b admits only about 13 routes a minute.
  - In sustained overload, 954 of the 1,205 429s recorded in the traces came from the router's token limit (`traces_sustained_overload_s*_20261119T07*.jsonl`, per-attempt status and limit type).
  - With requests-per-minute halved to 15, **not one** 429 was a request-limit 429. Success was 20.7% [17.7, 24.2], against 19.2% [16.2, 22.5] with the full limit: no measurable difference.
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
- **End to end, day-1 fixes, before the paper cover (2026-11-18, same day, same questions):**
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

## 9. Changes after day 2, and what they did
Day 2 showed where the wrong answers come from (section 4): answers that cover one paper when the question involves two, one value where the paper gives two, and details attached to the wrong paper. Two changes target these.

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

- **The baseline:** the held-out questions had never run on the system before the changes, so `run_eval.py --baseline` re-creates it (plain top-5, the old prompt, 400 tokens) and runs them on the same day (scenario `eval_heldout_baseline`).

**The measurement (2026-11-19):** one paced real run each, graded by the rubric, then reviewed with the day-2 rules, then by a blind second grader who saw neither the first grades nor which run an answer came from (52/52 agreement). A second repetition was skipped to stay under the daily token budget.

| | Correct | Wrong | Correctly refused | Refused wrongly |
|---|---|---|---|---|
| q01–q26, before (2026-11-18) | 10 | 8 | 4 | 4 |
| q01–q26, final | 11 | 4 | 4 | 7 |
| held-out q27–q39, before (baseline re-run) | 4 | 4 | 2 | 3 |
| held-out q27–q39, final | 4 | 3 | 2 | 4 |

Runs `run_eval_medium_20261118T092253Z`, `run_eval_medium_20261119T064116Z`, `run_eval_heldout_baseline_medium_20261119T065033Z` and `run_eval_heldout_medium_20261119T064735Z` (Table 3).

- **The rule was fixed before the runs: the changes count as helping only if both sets improve. They do not.** Paired by question, q01–q26 is 2 against 1 (exact McNemar p = 1.0) and the held-out set 1 against 1 (p = 1.0).
- **What changed is the kind of failure.** Over both sets, wrong answers fell from 12 to 7 and wrong refusals rose from 7 to 11. The held-out set shows the intended effect on q30 (both F1 values, where the baseline gave only one). It also shows the cost: q32, which the baseline answered, was refused.

**Most of the extra refusals were a check bug.** The new rule makes the draft name papers by arXiv id ("Paper 1706.03762v7"). The check read the id as the numbers 1706, 3762 and 7, which the cited passage doesn't contain, and refused q03, q18 and q19 and held-out q36. arXiv ids are now treated as labels, like "Paper 1". Re-checking all 183 recorded real drafts turns exactly those 7 drafts from fail to pass and no pass into a fail.

This fix was made after the held-out results were seen, so the recorded runs and the verdict stay as measured. **A replay (not a measurement)** grades what the fixed pipeline would have streamed, with the second grader agreeing on 4/4 (`results/raw/replay_grades_20261119T090000Z.csv`):
- q03 and q18 become correct; q19 (false claims about which parts are Transformers) and q36 (one paper of three) are wrong.
- q01–q26 would be 13 correct, against 10 before (4 against 1, p = 0.375). The held-out set stays at 4 against 4.

**What is kept, and what is claimed.** The final system keeps both changes with the check fix: fewer wrong answers, no measured loss of correct ones. The claim is only that. Higher accuracy is not shown, and 13 held-out questions could only show a large gain. Section 5 measures this final configuration.

## 10. Limits and open questions
- **Least certain assumption:** how the real service slows under concurrency. The free tier never allowed more than 5 requests in flight, so the stand-in's +10% per request is a guess. If the real slowdown is steeper, the overload results are optimistic.
- **Not measured:** the real tokens-per-day limit (documented as 200K), and any concurrency cap.
- **Small question set:** 26 questions give wide intervals (about ±18 points on correct %), 13 held-out questions about ±22; a difference of a few questions between settings or systems is within noise.
- **One run per setting and system:** the model gives different answers on different runs (medium q03 changed between days), so a single run per setting undercounts that variation. Small and large were not re-run on the final system.
- **The check fix is measured only by replay:** no real run has used it yet. The replay grades what the pipeline would have streamed; a real run could differ, for example by answering differently from the start.
- **The held-out set is now used:** its results were seen before the arXiv-id fix, so a future change needs new held-out questions.
- **Strict grading:** more than half of the "wrong" answers (8 of 15) are incomplete rather than false (section 4). A lenient grader would report higher accuracy from the same answers; the per-answer reasons in `eval/grades_*.csv` allow regrading.
- **Not built:** embeddings or re-ranking (measured and rejected), and streaming while checking (it could show a wrong number).
