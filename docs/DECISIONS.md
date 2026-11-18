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

### Grades
Grades go to results/raw/grades_<run>.csv (scripts/apply_grades.py; grade_from records "final" or "suggested"). scripts/build_results.py fills answer_grade in results/results.csv from them. Raw run files are never edited. Decided by me, 2026-11-12.

### q01 retrieval miss
Keep q01's retrieval miss as it is (medium setting: the raw question does not retrieve the "h = 8" passage): it is a real finding. Decided by me, 2026-11-12.

### Cut for time
Cut for time: the daily-budget-exhausted scenario runs on the stand-in only; retrieval settings 2 and 3 are evaluated on 15 questions, setting 1 on all 26. Decided by me, 2026-11-12.

### User give-up
A user give-up is recorded as status timeout, like a tool timeout. Decided by me, 2026-11-12.

## Decided by Claude, authorised by me on 2026-11-17

On 2026-11-17 I told Claude: "you are free to finish and take decisions by yourself". Each entry below is Claude's choice; I can defend it or overrule it.

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

On 2026-11-17 I said: "this project is no longer an assignment, it is now a personal project that I aim to present. I no longer need How I worked with the assistant and so on, I want the project to be valid and well evaluated." Claude takes the decisions below under the same authorisation as above.

### What is presented
A project report (docs/report.md) and the tables (docs/tables.md). There are no assignment-only sections (assistant conversation, Vaani feedback, 2-page limit).

### Real evaluation: all 26 questions on all three settings
This supersedes "Cut for time": all 26 questions run on each setting (78 pipeline runs). The 120b reserved tokens (130.5K–305K) can exceed the documented 200K/day, so the runs are split over two days: medium + small on day 1, large on day 2. Every real run still needs my OK.

### Load tests: 10 minutes × 3 seeds per scenario
The 150 s single runs had 7–60 requests, so p95 = p99 = one request, and the success intervals overlapped (sustained 27.3% [17.3, 40.2] against RPM-halved 21.7% [13.1, 33.6]). Each scenario now runs for 600 s with seeds 1, 2 and 3, and the runs are pooled. docs/tables.md adds an uncertainty table: 95% Wilson intervals for success, 95% bootstrap intervals for first-token p50/p95, and the spread across seeds. The superseded short runs are listed in results/excluded_runs.csv.

### Stand-in validation
The stand-in is checked against the real service on the same workload: `run_eval.py --standin` runs the real-eval questions against the stand-in, and scripts/compare_standin.py writes docs/standin_validation.md (per-step medians, p90, Kolmogorov-Smirnov distance).

### Grading validity
The raw grades files keep the rubric's suggested grade next to the final grade. docs/tables.md reports how often they agree, and how many final grades were typed by hand.

### Day 1 real eval (2026-11-17, medium + small, all 26 questions, my OK)
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
The rubric now compares numeric facts by value, like the check. Claude reviewed every answer the rubric marked wrong, and spot-checked the rest. 9 of 52 grades changed, all from wrong to correct, for paraphrased facts. Every change has its reason in eval/grades_*.csv. Where a question's key facts list context the question doesn't ask for (q04 codebook size, q09 other models), the answer is graded on what was asked. Where the author's rubric demands more (q13: both 41.8 and 41.0), it is applied as written.

### Stand-in calibration v2
Validation showed calibration v1 (2026-11-12 data only) was 1.6–1.9× slower than the real service on 2026-11-17. v2 adds the real medium eval's calls; it was validated on the held-out small eval (router 1.18×, draft 1.09×, KS 0.37–0.42). The load campaign was re-run on v2; the v1 campaign is excluded with this reason.

## Still open

None from `docs/open_decisions.md`.
