# Decisions

Numbers in brackets refer to `docs/open_decisions.md`.

## Decided

### Language
Python, using asyncio for concurrency and streaming.
*Decided on 2026-11-12.*

### Paper source [9]
PDF text extracted with PyMuPDF. The versioned PDF is the only format guaranteed to exist at the exact arXiv version, and it gives page numbers.
*Decided on 2026-11-12.*

### Citation format [10]
Paper + section + page.
*Decided on 2026-11-12.*

### Groq budget [2]
Calibrate first with a small number of requests. Hit the per-minute limit early, because it is cheap and recovers fast. Exhaust the per-day limit only once, on the last day of real runs, after all other real data is collected.
*Decided on 2026-11-12.*

### Extracted file naming
Files named <id>vN.jsonl, so the version travels with the data. Decided on 2026-11-12.

### Calibration run settings (scripts/calibrate.py)
- Total token cap raised from 35K to 42K (request cap stays 110). Decided on 2026-11-12.
- Total token cap raised from 42K to 43K. Reason: upper bound 42,662; I'd rather not lose a part-c request. Decided on 2026-11-12.
- Part a spacing: one request start every 15 s by default (`--a-spacing 15`), so the baseline fits the documented 8K TPM. Decided on 2026-11-12.
- b3 sent right after the first 429 in b1, while 120b is still limited, instead of after b2 recovers (which could not distinguish per-model from shared limits). b3 timing corrected on 2026-11-12.
- Safety margins: abort if x-ratelimit-remaining-requests < 800; abort if x-ratelimit-remaining-tokens < 500, checked only in parts a, b3 and c (b1, b2, b4 hit limits on purpose). Set on 2026-11-12.
- Keep the 60 s cooldowns (before b1, b4 and c) and temperature 0. Decided on 2026-11-12.
- A unique random marker at the start of every prompt in every part, so no request hits the prompt cache. Decided on 2026-11-12.
- Part a small requests: max output raised from 64 to 128 tokens. Decided on 2026-11-12.

### Retry policy
Retry policy: wait at least retry-after measured from the last accepted request; jitter only added on top, never subtracted. Decided from retry_20261112T145223Z, 2026-11-12.

### Refusal
Refusal is not decided by retrieval score: near-miss unanswerable questions (q23, q25) score higher than the answerable median. Refusal comes from the model reading the passages and from the check step. Decided from retrieval_eval_20261112T154135Z, 2026-11-12.

### Raw results and submission
Keep raw files untouched; submit a redacted copy produced by make_submission_copy.py. Decided on 2026-11-12.

### Environment
My terminal is cmd (Command Prompt), not PowerShell. Decided on 2026-11-12.

### Retrieval [12, 13]
BM25 on clean, section-aware chunks; no embeddings or cross-encoder in the project. Embeddings are worse than BM25 everywhere. MiniLM re-rank adds about 1 s to TTFT and lowers fact hit. TinyBERT gains +6.9 points only at medium, for a 1 GB dependency.
Evidence: results/raw/embed_bench_20261112T155413Z.jsonl. Decided on 2026-11-12.

### Time to first token [3]
Time to first token = first token of the final answer the user sees.
Evidence file: none (a definition, not a measurement). Decided on 2026-11-12.

### Check versus streaming [5]
The answer is drafted fully, checked, then streamed. The check is deterministic.
Evidence file: none. Decided on 2026-11-12.

### Failed check [8]
On a failed check: one redraft, then refuse and show the retrieved passages. Never loop more.
Evidence file: none. Decided on 2026-11-12.

### Models [1]
Router on openai/gpt-oss-20b, drafting on openai/gpt-oss-120b (limits are per model: cal-052).
Evidence: results/raw/calibration_20261112T141038Z.jsonl, record cal-052. Decided on 2026-11-12.

### Refusal (restated in Step 5)
Refusal is decided by the model and the check, not by a retrieval score (same decision as "Refusal" above).
Evidence: results/raw/retrieval_eval_20261112T154135Z.jsonl. Decided on 2026-11-12.

### Draft max_tokens
Draft max_tokens = 400.
Evidence: results/raw/calibration_20261112T141038Z.jsonl, cal-006..010 (120b, low effort, ~1.5K tokens in): 118–300 output tokens, 1/5 hit the 300 cap. Decided on 2026-11-12.

### Router max_tokens
Router max_tokens = 200.
Evidence: results/raw/calibration_20261112T141038Z.jsonl, 2/5 small 20b calls hit 128 (cal-014, cal-015). Decided on 2026-11-12.

### Router use and retrieval query
Retrieval uses the user's question as is. The router only decides in/out of scope; its keywords and papers are logged, not used. Reason: the retrieval evaluation measured the raw question. Decided on 2026-11-12.

### Retries (Step 5b) [17]
- Request-limit 429 (body type "requests"): wait retry-after measured from the last accepted request, jitter on top.
- Token-limit 429 (body type "tokens"): wait retry-after measured from now, jitter on top.
- Evidence: results/raw/retry_20261112T145223Z.jsonl, plus cal-056/057 in results/raw/calibration_20261112T141038Z.jsonl.
- 500/502/503/498: retry once, with the same jitter.
- A client timeout is never retried.

Decided on 2026-11-12.

### Check: numbers need citations
A sentence containing a number without a citation fails the check. Decided on 2026-11-12.

### How raw results flow into results.csv [26]
Each run writes results/raw/run_<scenario>_<UTC>.csv. scripts/build_results.py rebuilds results/results.csv from all raw run files, sorted by start_time, never edited by hand. Decided on 2026-11-12.

### Grades
Grades go to results/raw/grades_<run>.csv (scripts/apply_grades.py; grade_from records "final" or "suggested"). scripts/build_results.py fills answer_grade in results/results.csv from them. Raw run files are never edited. Decided on 2026-11-12.

### q01 retrieval miss
Keep q01's retrieval miss as it is (medium setting: the raw question does not retrieve the "h = 8" passage): it is a real finding. Decided on 2026-11-12.

### Cut for time
Cut for time: the daily-budget-exhausted scenario runs on the stand-in only; retrieval settings 2 and 3 are evaluated on 15 questions, setting 1 on all 26. Decided on 2026-11-12.

### User give-up
A user give-up is recorded as status timeout, like a tool timeout. Decided on 2026-11-12.

## Decisions of 2026-11-17 (finishing the pipeline)


### Daily limit [16]
A daily-limit 429 is never retried. Groq labels it "requests"; only the message says "per day (RPD)". The person gets "Today's answer budget is used up…", the reset time from x-ratelimit-reset-requests, and the retrieved passages (marked as not checked by a model). Status: rate_limited.
Evidence: traces_daily_exhausted_20261113T073425Z (requests 0013/0015: 3 immediate useless retries under the earlier rule).

### Per-minute limit [15]
Requests queue behind the per-model rate gate and wait. Nobody is shed and the answer is never weakened. A person waits until their first token, or gives up after 15 s.
Evidence: run_sustained_overload_20261113T080028Z (72.7% gave up, 27.3% succeeded).

### Pipeline shape [6, 7]
- Two model calls per request (20b router, 120b draft), plus at most one redraft.
- Tools: BM25 retrieval (with a timeout) and the deterministic citation/number check.

### Retry details [17, 18]
- Retries happen per model call.
- At most 3 retries for 429s, with jitter 0–0.25 s.
- A 429 without retry-after waits 2.0 s.
- An unknown 429 type is measured from now.

### Chunking settings [11]
Section-aware chunks with the three Table 3 settings: small (128 tokens, 8 pieces), medium (256, 5) and large (512, 3), no re-rank. Medium is the main setting, used for load tests and the full 26-question eval.

### Retrieval near the limit [14]
Nothing changes near the limit: same k, same prompt. The 120b draft prompt dominates reserved tokens, and the check needs the passages it cites.

### Load generator and patience [19, 20]
- Open-loop Poisson arrivals (seeded).
- Fixed patience: a person gives up if no first token arrives within 15 s.

### Stand-in [21, 22]
- An HTTP server compatible with Groq's API, so the client code is the same.
- Latency resampled from whole measured requests.
- Slowdown under load, the 5xx rate and the slow tail are assumptions (docs/standin.md).

### Grading [23]
scripts/pregrade.py suggests a grade from a key-fact rubric plus a gold-citation match; a human sets final_grade.

### Question mix [24]
The 26 questions in eval/questions.yaml as written (4 unanswerable, 2 term traps, 3 cross-paper).

### Cost [25]
Groq list prices with the router/draft token split stated in docs/tables.md.

### The fast target [4]
At steady load, 95% of people get a first token before they would give up (15 s).

### Tables
One row per scenario. Superseded or invalid runs are listed with their reasons in results/excluded_runs.csv; their rows stay in results.csv.

### 15-question subset (cut for time)
Small and large are evaluated on q01, q03, q04, q07, q08, q10, q12, q14, q15, q16, q18, q20, q21, q23, q25. That is the same type mix as the 26 (5 single-fact, 3 table, 2 explanation, 2 cross-paper, 1 term trap, 2 unanswerable), and q23/q25 are the near-miss unanswerables. Medium is "setting 1", with all 26.

## Personal project phase (from 2026-11-17)

On 2026-11-17 the project became a personal project to present. The goal from here is a valid, well-evaluated system, not an assignment submission.

### What is presented
A project report (docs/report.md) and the tables (docs/tables.md). There are no assignment-only sections (conversation export, feedback section, 2-page limit).

### Real evaluation: all 26 questions on all three settings
This supersedes "Cut for time": all 26 questions run on each setting (78 pipeline runs). The 120b reserved tokens (130.5K–305K) can exceed the documented 200K/day, so the runs are split over two days: medium + small on day 1, large on day 2. Every real run is announced with its request and token cost before it starts (CLAUDE.md).

### Load tests: 10 minutes × 3 seeds per scenario
The 150 s single runs had 7–60 requests, so p95 = p99 = one request, and the success intervals overlapped (sustained 27.3% [17.3, 40.2] against RPM-halved 21.7% [13.1, 33.6]). Each scenario now runs for 600 s with seeds 1, 2 and 3, and the runs are pooled. docs/tables.md adds an uncertainty table: 95% Wilson intervals for success, 95% bootstrap intervals for first-token p50/p95, and the spread across seeds. The superseded short runs are listed in results/excluded_runs.csv.

### Stand-in validation
The stand-in is checked against the real service on the same workload: `run_eval.py --standin` runs the real-eval questions against the stand-in, and scripts/compare_standin.py writes docs/standin_validation.md (per-step medians, p90, Kolmogorov-Smirnov distance).

### Grading validity
The raw grades files keep the rubric's suggested grade next to the final grade. docs/tables.md reports how often they agree, and how many final grades were typed by hand.

### Day 1 real eval (2026-11-17, medium + small, all 26 questions)
Runs run_eval_medium_20261117T102821Z and run_eval_small_20261117T103158Z are kept as recorded: they measure the system before the fixes below.

### Check fixes from real day-1 drafts
Eight real drafts were wrongly failed. The fixes, frozen with those drafts in tests/fixtures/day1_false_check_failures.json:
- an interval `[0,1]^{…}` is not a citation (a bracket containing 0, or followed by ^ _ {, is maths);
- a narrow no-break, thin or no-break space between digit groups is a thousands separator;
- superscript decimals (`⁻⁰·⁵`) are read as one number;
- "Paper N" / "passage N" are labels, not facts.

Replaying all day-1 drafts: those 8 now pass, and no answer that passed now fails.

### Router guard
The 20b router refused q14 ("…H-Net…on DNA?") in both settings. An out-of-scope verdict is now overruled when the question names a term from the papers (`names_paper_topic`; the trace shows `router_overridden`). The router keeps the final say on everything else.

### Paced real evals
Back to back, every draft after the first ~6 hit a token-limit 429 (median retry wait 9.2 s), so first-token time measured the eval's own throttling. run_eval.py now waits, between questions, for the 120b token bucket to refill for the next reservation (`--no-pace` turns it off). Load is measured by the stand-in tests, not the eval.

### Grading of day 1
The rubric now compares numeric facts by value, like the check. Every answer the rubric marked wrong was reviewed by hand, and the rest spot-checked. 9 of 52 grades changed, all from wrong to correct, for paraphrased facts. Every change has its reason in eval/grades_*.csv. Where a question's key facts list context the question doesn't ask for (q04 codebook size, q09 other models), the answer is graded on what was asked. Where the author's rubric demands more (q13: both 41.8 and 41.0), it is applied as written.

### Stand-in calibration v2
Validation showed calibration v1 (2026-11-12 data only) was 1.6–1.9× slower than the real service on 2026-11-17. v2 adds the real medium eval's calls; it was validated on the held-out small eval (router 1.18×, draft 1.09×, KS 0.37–0.42). The load campaign was re-run on v2; the v1 campaign is excluded with this reason.

### Day 2 real eval (2026-11-18, large + medium re-run, current system)
Runs run_eval_large_20261118T091718Z and run_eval_medium_20261118T092253Z, paced, with zero 429s. Kept as recorded.

### Check fixes from real day-2 drafts
Two real drafts were wrongly failed (medium q17's redraft, and large q14's draft and redraft). The fixes, frozen in tests/fixtures/day2_false_check_failures.json:
- LaTeX fractions (`\frac{1}{2}`, `\tfrac12`) are read as their two numbers, not as "12".
- NFKC turns the non-breaking hyphen U+2011 into U+2010; U+2010 is now mapped to "-", as U+2011 was meant to be.
- **Fractions written in words ("one-third", "two thirds", "one half") are not checked.** They are paraphrased ratios, not quoted numbers; read as number words they gave a false "1". The cost: a wrong word fraction is not caught, like any other claim made in words.

Re-checking all 96 recorded first-draft checks with the new code turns no pass into a fail.

### Grading of day 2
Same rule as day 1, applied to the same questions: q04, q09, q12, q15 and q16 paraphrases are correct, as on day 1, and q13 needs both values.
- q14 now needs both values too: 3.6× and the abstract's "nearly 4×". This is the same written rule as q13, applied even though 3.6× is right.
- medium q03 is marked wrong although every key fact is present: it attributes Moshi's AdamW to the Transformer's training.
- 10 of 52 grades changed from the suggestion.

### Table 3 per run, never pooled
The pipeline changed between eval days, so pooling medium's two runs would average two systems. Each eval run is its own row, labelled with date and system version (FIXES_STAMP in make_tables.py). Correct % carries a Wilson 95% interval.

### Retrieval setting stays medium
- On the current system, large was 12/26 correct and medium 10/26 (after the q05 regrade; 13 and 11 before). Paired by question that is 3 against 1 (exact McNemar p = 0.63), so no measurable difference.
- Medium ties on retrieval-only recall, and the whole load campaign is measured on it.
- Switching would need a new load campaign, for a gain that cannot be told apart from noise.

### Paper cover (2026-11-18, not yet measured on the real service)
Retrieval keeps the BM25 top-k. It then appends the best chunk of a paper missing from that top-k, when the question:
- names one of that paper's own terms (PAPER_TERMS in pipeline.py), or
- asks about all the papers (ASKS_ALL_PAPERS), or
- matches that paper's best chunk at ≥ 0.7 × the top score.

`retrieval_eval_20261118T103625Z`, medium: fact hit 75.0% → 78.8%, recall unchanged at 90.9%, all gold papers 0/5 → 1/5. Mean context is 948 → 992 tokens; 5 of 26 questions get an extra chunk. Large: fact hit 79.5% → 83.3%, recall 81.8% → 86.4%. Small: no change.

The blanket per-paper quota (Step 4b) gains about as much at medium (80.3%) for +30% context on every question, so it stays rejected.

Ratio 0.7 was picked on the eval questions: 0.6 gives the same result with more context, 0.8 less gain.

### Draft rules for multi-paper answers, draft max_tokens 500 (2026-11-18, not yet measured)
New rules in DRAFT_SYSTEM, each aimed at a failure kind seen on day 2, written generally rather than per question:
- name the paper for each statement, and never attach one paper's detail to another's model (medium q03);
- answer for each paper the question asks about, and say which paper the passages don't cover (q18, q19);
- give each meaning of a term that differs between papers (q21, q22);
- report differing values side by side (q13, q14).

At most 6 sentences instead of 5. Real drafts reached 366 of 400 tokens, so `max_tokens` went to 500 to keep longer answers from being cut off (a cut-off answer fails the check). That reserves about 6% more tokens per draft.

**Validity caveat:** these changes were designed from failures on the same 26 questions that will re-measure them, so a gain on those questions is optimistic. A held-out question set, written before the re-run, is what can show the gain is real.

### The v2 load campaign describes the system before these changes
After the real re-measure fixes the final configuration, the stand-in load campaign is re-run (free, about 12 minutes) and the v2 campaign excluded with that reason.

## Still open

None from `docs/open_decisions.md`.

### Held-out questions q27–q39 (2026-11-18)
13 new questions in `eval/heldout.yaml`, written after the paper-cover and draft-rule changes and never used to tune them. Mix: 3 single-fact, 3 table-number, 2 explanation, 2 cross-paper, 1 term trap, 2 unanswerable. Three of them carry a differing-values trap: q29, q30 and q31.
- Every key fact was checked against the clean extraction and is on its gold page (`eval_retrieval.py --facts`: 0 problems).
- `verified: false` until checked in the PDFs by hand.
- **Frozen before any run on them.** The drafted file's sha256 is eef4b5069ccd947544adb134b4d54ee2021dc4f7acc0808f719359066b8a97fc. After the hand check, only `verified` flags and corrections of real errors may change, and the final hash is recorded here before the first run.
- Run with `run_eval.py --heldout`, as scenario `eval_heldout`, so they are never mixed into the q01–q26 numbers. Table 3 shows them as separate rows.
- **Checked and frozen (2026-11-18).** Every key fact, gold page and both absences were re-checked against the rendered PDF pages, not the extraction the questions were drafted from.
  - No fact was wrong. q36 now also accepts Mimi's own batch (128 windows of 12 s, Moshi p.11).
  - **Final sha256: 01892d550524d62eea2e13f2d0085761218033cc9b6045f50cca9e77d7156988** (the header comment was reworded once, before any run; 73c6eabf… before that). Any later change to eval/heldout.yaml invalidates its held-out status.
  - Caveat: the questions were written and checked within the project, not by an outside reviewer.

### Second, blind grader and append-only regrades (2026-11-18)
A second grader (a separate LLM agent) regraded the 52 day-2 answers blind to the first grades, with the same written rules (`results/raw/second_grades_20261118T110000Z.csv`).
- It agreed on 50/52 (κ 0.94). The 2 disagreements (q05) went to the second grader: the key facts require 200 ms in practice, and the rubric string checked only "160ms".
- q05 was regraded wrong in all four runs, including day 1, for consistency.
- **How grades are corrected now:** in `results/raw/regrades_*.csv`, append-only. Each line names the grade it replaces and why. build_results applies regrades after the original grades and refuses any line whose `previous_grade` doesn't match. The original grade files are untouched.
- The rubric string for q05 is now "200ms".
