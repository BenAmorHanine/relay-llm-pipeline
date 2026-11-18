# Worklog

## 2026-11-12 – Step 1 – Skeleton
- Prompt (verbatim):

  ```text
  Read docs/The_Relay_Assignment_Brief.pdf completely before doing anything. This is a take-home assignment; I will defend every choice in a live interview, so do not make design decisions for me yet.

  Do NOT write any pipeline code in this step. Only:

  1. Create the project skeleton inside E:\vaani (Python 3.11+, asyncio-friendly; I am on Windows, so use paths and commands that work there):
     - src/relay/        (pipeline, later)
     - standin/          (fake model service, later)
     - loadtest/         (load shapes, later)
     - eval/             (my 15+ questions and grading, later)
     - data/papers/      (the 3 arXiv papers, later)
     - results/raw/      (raw measurements, never edited by hand)
     - docs/             (already contains The_Relay_Assignment_Brief.pdf; also the write-up, worklog, exported conversations)
     - README.md (short), .gitignore (.env, .venv, __pycache__, large caches), .env.example with GROQ_API_KEY= only
  ```
- What was done: Read all 4 pages of the brief. Created src/relay/, standin/, loadtest/, eval/, data/papers/ and results/raw/, each with a .gitkeep so git tracks it. Wrote a short README.md (purpose, layout table, Windows venv setup), a .gitignore (.env, .venv, __pycache__, tool caches, data/cache/, OS/editor files; data/papers/ and results/raw/ deliberately left tracked) and a .env.example containing only `GROQ_API_KEY=`. Did not add pyproject.toml, requirements.txt or `__init__.py` files (left as design decisions). Nothing committed.
- What I checked and how: I compared Claude's reply against my numbered prompt item by item. The skeleton (folders, .gitignore, .env.example, README) matched item 1, and I confirmed .env is ignored while data/papers/ and results/raw/ stay tracked, since reviewers need the raw results. But WORKLOG.md, CLAUDE.md and the brief checklist were missing, so I sent a follow-up (Step 1b) assuming Claude had skipped items 2–4. Claude then showed that the prompt it received ended after item 1: my paste was truncated. I checked my own message and confirmed it.
- What was wrong / what I caught: The prompt was truncated after item 1. The assistant did item 1 and did not flag that the list looked incomplete.
- Decision I made: Kept the skeleton as built. Added a rule to CLAUDE.md: "If a prompt from me looks truncated or contradicts an earlier rule, stop and ask before acting," and another requiring every reply to end with each numbered item marked done / not done, so a missing item is visible immediately. From then on I paste each prompt as one complete block.

## 2026-11-12 – Step 1b – Follow-up on "missing" items 2–4
- Prompt (verbatim):

  ```text
  You only did item 1 of my 4 numbered items. Items 2, 3 and 4 are missing, and your summary didn't say so. From now on, when I give numbered items, end your reply with each item number marked done / not done.

  Now do the missing ones:

  2. Create docs/WORKLOG.md with the template from my previous message. Add two entries:
     - Step 1 (skeleton): include my prompt verbatim, and under "What was wrong" write that you completed only item 1 and reported the step as done.
     - Step 1b (this fix).
     Leave "What I checked and how" and "Decision I made" empty for me to fill in.

  3. Create CLAUDE.md with the hard rules from my previous message, exactly as I wrote them (Groq key, budget confirmation before any real call, the exact results.csv columns in order, answers only from the 3 papers at exact versions with citations or refusal, raw results append-only). Add one more rule: "When I give numbered items, end every reply with each item number marked done / not done."

  4. In your reply only (not a file):
     a) The full checklist of hard requirements from the brief: what to build, what to run, all required headings in their exact order (including the two extra headings after heading 5, the Vaani feedback section, and "How I worked with the assistant"), the 3 tables with every column, the minimum rows of Table 2a, the results.csv columns, the formatting rules (milliseconds, one decimal for percentages, "not measured"), and the ground rules.
     b) The open decisions I must make, each with 2–3 options and a one-line trade-off. Do not choose for me.
  ```
- What was done: Pointed out that the previous prompt contained only item 1 (no WORKLOG template, no hard rules), so items 2 and 3 could not be done "exactly as written" without inventing text. Did not create WORKLOG.md or CLAUDE.md; asked for the missing content. Proposed a more accurate "What was wrong" wording for Step 1. Delivered 4a (full checklist of hard requirements) and 4b (26 open decisions with options and trade-offs, no recommendations) in the reply. Ended with item status: 2 not done, 3 not done, 4a done, 4b done.
- What I checked and how: I re-read the message I had actually sent and confirmed Claude was right: it ended after item 1. I compared Claude's 4a checklist with the brief, page by page. It included the two extra headings after heading 5, the Vaani section, "How I worked with the assistant", all four tables with their columns, the minimum rows of Table 2a, the results.csv columns, and the formatting rules (milliseconds, one decimal, "not measured").
- What was wrong / what I caught: My follow-up wrongly assumed the assistant had skipped items 2–4; they were never in the prompt it received because my paste was truncated.
- Decision I made: Accepted Claude's more accurate wording for the Step 1 "What was wrong" field instead of my own, because mine blamed the assistant for something that was my mistake. Also noted as good behaviour: it refused to invent rules "exactly as I wrote them" when it had never seen them. Re-sent the full content as one complete block (Step 1c).

## 2026-11-12 – Step 1c – Missing content: WORKLOG, CLAUDE.md, checklists
- Prompt (verbatim):

  ```text
  You're right, my previous prompt was truncated. Here is the missing content in full.

  1. Create docs/WORKLOG.md with this template:

     ## <date> – Step N – <title>
     - Prompt (verbatim):
     - What was done:
     - What I checked and how:
     - What was wrong / what I caught:
     - Decision I made:

     Add entries for Step 1 (skeleton), Step 1b (my follow-up, which wrongly assumed you skipped items) and Step 1c (this one). For Step 1, under "What was wrong" write: "The prompt was truncated after item 1. The assistant did item 1 and did not flag that the list looked incomplete." Put my prompts verbatim. Leave "What I checked and how" and "Decision I made" empty for me.

  2. Create CLAUDE.md with exactly these rules:
     - Never print, log or commit the Groq key; read it only from .env.
     - The Groq free-tier daily budget is shared by everything I run. Never make a real Groq call without first telling me how many requests and roughly how many tokens it will use, and waiting for my OK.
     - results.csv must have exactly these columns, in this order: request_id, scenario, source, start_time, first_token_ms, total_ms, status, retries, tokens_in, tokens_out, retrieval_setting, answer_grade. Every number in the write-up must be recomputable from it.
     - Answers come only from the 3 papers at the exact arXiv versions in the brief, always cited; if the papers don't say, refuse instead of guessing.
     - Raw results are append-only; never overwrite or "clean" them.
     - When I give numbered items, end every reply with each item number marked done / not done.
     - If a prompt from me looks truncated or contradicts an earlier rule, stop and ask before acting.
     - I am on Windows (PowerShell). Use commands and paths that work there.

  3. Save your 4a checklist and 4b decision list from your last reply into docs/brief_checklist.md and docs/open_decisions.md, word for word.
  ```
- What was done: Created docs/WORKLOG.md with entries for Steps 1, 1b and 1c using the template; created CLAUDE.md with the eight rules exactly as given; saved the 4a checklist to docs/brief_checklist.md and the 4b decision list to docs/open_decisions.md, word for word from the previous reply.
- What I checked and how: Opened CLAUDE.md and compared it with my eight rules. Read the Step 1 entry in WORKLOG.md and confirmed my prompt was copied verbatim. Read the Step 1b "What was wrong" text Claude wrote for me (it had no text from me for that field) and kept it because it is accurate.
- What was wrong / what I caught: My own rule was wrong: I wrote "I am on Windows (PowerShell)" but my terminal is cmd. I found out in Step 3 when `Copy-Item` failed in cmd. Corrected in CLAUDE.md in Step 3b.
- Decision I made: Keep the brief checklist and the 26 open decisions as files in docs/, so every later decision can be traced back to its number in open_decisions.md.

## 2026-11-12 – Step 2 – Decisions, papers, extraction, Groq docs, calibration plan
- Prompt (verbatim):

  ```text
  Step 2. Numbered items:

  0. Create docs/DECISIONS.md and record these decisions I made (mark each "decided by me, 2026-11-12"):
     - Language: Python (asyncio for concurrency and streaming).
     - Paper source: PDF text extracted with PyMuPDF, because the versioned PDF is the only format guaranteed at the exact arXiv version and it gives page numbers.
     - Citation format: paper + section + page.
     - Groq budget: calibrate first with a small number of requests. Hit the per-minute limit early (cheap, recovers fast). Exhaust the per-day limit only once, on my last day of real runs, after all other real data is collected.
     Leave a section "Still open" listing the other decisions from docs/open_decisions.md by number.

  1. Write a script (scripts/fetch_papers.py) that downloads exactly these PDFs into data/papers/ using the versioned URLs (https://arxiv.org/pdf/<id>v<N>):
     1706.03762v7, 2410.00037v1, 2507.07955v2.
     Record each file's SHA-256 and download time in data/papers/MANIFEST.md. Run it.

  2. Extract text with PyMuPDF, keeping for each block: paper id, page number, and the nearest section heading. Save to data/papers/extracted/<id>.jsonl. Then show me, for each paper: page count, number of blocks, 3 random blocks, and any problems you see (broken equations, two-column order mixing, headers/footers repeated, references section, tables). Don't fix anything yet, just report.

  3. Read Groq's official rate-limit documentation (console.groq.com/docs/rate-limits) and its API/error docs. Give me a table of the free-tier limits per model (RPM, RPD, TPM, TPD), which response headers report remaining quota and reset time, and what an HTTP 429 looks like. Mark everything as "from docs, not yet verified". Make NO API calls.

  4. Propose (don't run) a calibration plan for the real API: total requests and tokens, split into (a) latency baseline, (b) deliberately hitting the per-minute limit, (c) streaming TTFT measurement. Keep the total under 10% of the daily request limit of the model I'd most likely use. Say which model you'd suggest for drafting and for routing/checking, and the trade-off, but I decide.

  5. Add a WORKLOG entry for Step 2 (my prompt verbatim, what you did), leaving my two fields empty.
  ```
- What was done:
  - Wrote docs/DECISIONS.md: language, paper source [9], citation format [10] and Groq budget [2] recorded as decided by me, plus a "Still open" list.
  - Wrote scripts/fetch_papers.py (standard library only). Ran it: the three versioned PDFs are in data/papers/, with SHA-256 hashes and UTC download times in data/papers/MANIFEST.md.
  - Created .venv (Python 3.12.4), installed PyMuPDF 2.1, and added requirements.txt pinning it.
  - Wrote scripts/extract_papers.py: one JSON line per PyMuPDF text block, with paper_id, page, block_no, bbox, section and section_path. Sections come from each PDF's outline bookmarks plus the heading's position on the page. Ran it: 539, 1062 and 865 blocks.
  - Reported the extraction problems without fixing them.
  - Fetched Groq's rate-limit, errors and models docs (no API calls) and reported limits, headers and the 429 format, all marked "from docs, not yet verified".
  - Proposed a calibration plan (not run) and suggested models.
  - Things the docs don't settle:
    - which plan the rate-limit table belongs to
    - whether limits are per model or shared across models
    - that the llama models are now listed as enterprise-only
- What I checked and how: I opened data/papers/MANIFEST.md and checked that the three files are 1706.03762v7, 2410.00037v1 and 2507.07955v2. I read the 10 extraction problems and recognised three of them as material for the "naive retriever" section (references labelled as Conclusion, flattened superscripts such as 10^20 → 1020, repeated section names). I noted that Claude read Groq's docs through a summarising fetch tool and that the page does not say which plan the table belongs to, so every limit had to be verified by real calls, not trusted. I have a free Groq account, so the "Free Plan" values are the ones that apply to me.
- What was wrong / what I caught: The calibration plan used about 25% of the documented daily tokens (~49K of 200K) while staying under 10% of requests. Tokens, not requests, are my scarce resource (about 35 full answers per model per day at 200K tokens), so the plan was optimising the wrong limit.
- Decision I made: Accepted file names with the version (<id>vN.jsonl) instead of my <id>.jsonl, so the version travels with the data. Rejected the 25%-token plan: merged the latency baseline and the TTFT measurement into one set of streamed requests, kept reasoning_effort low by default, and decided to calibrate both gpt-oss-120b and gpt-oss-20b, because if limits are per model, two models double the daily budget. Final model choice left open until I have quality measurements.

## 2026-11-12 – Step 3 – Calibration script (dry run only)
- Prompt (verbatim):

  ```text
  Step 3. Numbered items. I have a free Groq account and my key is already in .env. Do not ask me for the key. If docs/evidence/ contains a screenshot of my account's Limits page, use it as a source; otherwise the limits come from the docs (Free Plan) and must be verified by this calibration.

  0. Save the 10 extraction problems from your Step 2 report into docs/retriever_pitfalls.md, word for word, with their examples. I will use them for the "naive retriever" section. Also add to docs/DECISIONS.md: "Files named <id>vN.jsonl, so the version travels with the data. Decided by me, 2026-11-12."

  1. Write scripts/calibrate.py with these rules:
     - Every request is streamed. For each request, record in results/raw/calibration_<UTC timestamp>.jsonl: model, part, start time (UTC ISO), time to response headers, time to first reasoning token, time to first visible token, total time, HTTP status, all x-ratelimit-* headers and retry-after, the full error body if not 200, tokens in/out, reasoning tokens if reported, and any server-side timings in the response (e.g. queue time, prompt time, completion time) if present.
     - reasoning_effort = "low" unless the part says otherwise.
     - Hard stops: abort the whole run on any status other than 200/429, or if x-ratelimit-remaining-tokens or remaining-requests drop below a safety margin you define, or if my total caps below are reached.
     - Write each record immediately (append), so a crash loses nothing.
     - Print a dry-run summary (requests and estimated tokens per part, per model) and exit unless run with --go.

  2. Parts, run on BOTH openai/gpt-oss-120b and openai/gpt-oss-20b unless noted:
     a) Baseline, streamed, sequential, one every 4 s: 5 small requests (~150 in, ≤64 out) and 5 retrieval-sized (~1.5K in, ≤300 out). Use real text from data/papers/extracted as the context, with a real question.
     b1) 120b only: ~35 tiny requests within ~15 s until the first 429. Capture everything about the 429.
     b2) 120b only: after the first 429, one tiny request every 5 s until a 200.
     b3) Right after b2, send ONE tiny request to 20b. This tells us whether the limits are per model or shared. Record it as part "b3_shared_check".
     b4) 120b only, after a 60 s cooldown: 5 requests of ~2K tokens at once, to find the tokens-per-minute behaviour.
     c) 120b only: 4 retrieval-sized streamed requests with reasoning_effort "medium", to compare against the "low" ones in (a).
     Caps for the whole run: at most 110 requests and 35K tokens in total across both models. Show me the dry run first and wait for my OK.

  3. After I run it with --go, write scripts/summarize_calibration.py that reads the raw file and prints, per model and part: count, p50/p95 of each timing, statuses, the observed 429 point, recovery time, whether a 429 decreased remaining-requests, and the per-model-or-shared result. Every number must come from the raw file.

  4. Add a WORKLOG entry for Step 3 (my prompt verbatim, what you did), leaving my two fields empty.
  ```
- What was done:
  - docs/evidence/ does not exist, so the limits are still from the docs only.
  - **There is no .env in E:\vaani** (only .env.example), so `--go` would stop before sending anything.
  - Saved the 10 extraction problems word for word to docs/retriever_pitfalls.md, and added the file-naming decision to DECISIONS.md.
  - Wrote scripts/calibrate.py:
    - Uses httpx streaming and SSE parsing, with tiktoken o200k_harmony for estimates. Both are added to requirements.txt.
    - Appends and fsyncs one record per request, plus run_start and run_end records.
    - Hard stops: any status other than 200/429, network errors, errors inside the stream, the caps, and two margins: remaining-requests < 800, and remaining-tokens < 500 checked only in parts a, b3 and c.
    - Prompts use real extracted blocks from all 3 papers with 5 real questions.
  - Ran the dry run only: 77 requests max, upper bound 41,149 tokens, which is **over the 35K cap**.
  - Raised these for decision before `--go`:
    - the token cap overrun
    - part a's 4 s spacing exceeds the documented 8K TPM (~8.9K tokens in 16 s for the retrieval requests)
    - b3 moved to right after the first 429, because after b2 recovers it can't tell per-model from shared; `--b3-after-b2` gives the literal spec
    - 60 s cooldowns added before b1 and c
    - temperature 0
    - prompt caching may confound the a-vs-c comparison
    - tiny max_out with reasoning may yield no visible token
  - Item 3 not started (it waits for the real run).
- What I checked and how: Read the dry-run table and saw the upper bound (41,149) was over my 35K cap. Checked the b3 argument myself: after b2 recovers, 120b is no longer limited, so a 200 from 20b would prove nothing. Claude was right. Created .env myself in cmd (`copy .env.example .env`, then `notepad .env`), checked with `dir /a` that it is .env and not .env.txt, and with `git status` that it is not tracked. Created a dedicated key for this project in the Groq console instead of reusing my other project's key, since limits are per organisation anyway and a separate key can be revoked after submission.
- What was wrong / what I caught: My own b3 design was wrong (sending to 20b after recovery cannot distinguish per-model from shared limits); Claude Code caught it, and I accepted the correction. My 4 s spacing for part a would have hit the 8K tokens-per-minute limit in the middle of the baseline; also caught by Claude Code. And my CLAUDE.md said PowerShell: `Copy-Item` failed because I use cmd.
- Decision I made: Decided in Step 3b (see there).

## 2026-11-12 – Step 3b – Calibration decisions, cmd, cache markers
- Prompt (verbatim):

  ```text
  Correction: my terminal is cmd (Command Prompt), not PowerShell. Update CLAUDE.md and give me cmd commands from now on.

  Step 3b. The key is now in E:\vaani\.env (check the file exists without printing it). My decisions:

  1. Raise the total token cap to 42K.
  2. Use --a-spacing 15 as the default for part a.
  3. I accept your change: b3 is sent right after the first 429 in b1, while 120b is still limited. You were right that my original timing would prove nothing. Record this in docs/DECISIONS.md as "b3 timing corrected by Claude, accepted by me".
  4. I accept your safety margins as described.
  5. Keep the cooldowns and temperature 0. Add a unique random marker at the START of every prompt in every part, so no request hits the prompt cache. Raise max output for part a's small requests from 64 to 128.

  Then:
  - Rerun the dry run with these settings and show it.
  - Add the decisions above to docs/DECISIONS.md, and a Step 3b entry to docs/WORKLOG.md (my prompt verbatim).
  - Do NOT run --go. I will run it myself.

  End with the status of items 1–5.
  ```
- What was done:
  - Confirmed E:\vaani\.env exists, contains a non-empty GROQ_API_KEY line and is git-ignored, without printing it.
  - Updated the CLAUDE.md Windows rule to cmd. Changed the README setup and the script usage notes to cmd syntax. A first scripted README edit garbled `\activate.bat` into a control character; caught it in the output and rewrote the section.
  - calibrate.py changes:
    - CAP_TOKENS raised to 42,000.
    - `--a-spacing` default set to 15.
    - Part a small requests now allow up to 128 output tokens.
    - Every prompt starts with a unique `[run-marker <16 hex>]` line, stored per record as `prompt_marker`. Verified 77/77 unique.
  - A first patch attempt failed on an assertion and changed nothing; redone with direct edits.
  - Reran the dry run: 77 requests max, upper bound 42,662 tokens. That is 662 over the new 42K cap, because the markers and 128-token outputs add tokens. Reported, not changed.
  - Recorded the decisions in DECISIONS.md. Did not run `--go`.
- What I checked and how: Read the new dry run: 77 requests (under 110) but 42,662 tokens, over the 42K cap. Re-ran the dry run myself in cmd after raising the cap and checked it printed "Caps: 110 requests, 43000 tokens" and "WITHIN the caps". Then ran `--go` myself (not Claude): 62 requests sent, 36,397 tokens used, completed without a hard stop. Saved the console output next to the raw file.
- What was wrong / what I caught: The random markers and the larger 128-token allowance pushed the upper bound 662 tokens over my 42K cap. Claude reported it rather than silently going over.
- Decision I made: Raised the cap to 43K rather than cutting part c, because the cap is checked before each request and the run would have dropped part-c requests, and part c has only 4 (losing one would cost a quarter of the reasoning-effort comparison). The markers go at the START of every prompt, because prompt caching works on the beginning of the prompt. I ran the real calls myself so the measurements are mine.

## 2026-11-12 – Step 3c – Calibration summary and hypotheses
- Prompt (verbatim):

  ```text
  Step 3c. The --go run finished: results/raw/calibration_20261112T141038Z.jsonl (console output saved next to it as _console.txt). Do item 3 from Step 3:

  1. Write scripts/summarize_calibration.py and run it on that file. Print, per model and part: count, p50/p95 of time to headers, first reasoning token, first visible token and total time; statuses; tokens in/out and reasoning tokens. Every number must come from the raw file.

  2. Then test these hypotheses from the raw records and say for each: confirmed / rejected / unclear, with the record ids that prove it:
     a) RPM is 30: first 429 in b1 came after exactly 30 successes; give the elapsed time from the first b1 request to the 429.
     b) A 429 does not decrease remaining-requests.
     c) Limits are per model: 20b returned 200 while 120b was limited, with its own counter.
     d) Recovery after the RPM 429: exact time from the 429 to the next 200, and what retry-after said.
     e) TPM is 8K: what happened in b4, and what remaining-tokens and retry-after said on the two 429s.
     f) The daily request counter refills gradually: 120b ended part a at remaining=990 but b1 started at 991. Compute the refill rate from all 120b records and compare with 1000/86400 s.
     g) Server-side timings: were queue time / prompt time / completion time present? If so, what share of total time was queueing?
     h) Reasoning effort: compare first-visible-token and total time for part c (medium) vs part a's retrieval-sized requests on 120b (low), and the reasoning tokens used.
     Show me the exact 429 response body and headers once.

  3. Add a Step 3c entry to docs/WORKLOG.md (my prompt verbatim).

  End with the status of items 1–3.
  ```
- What was done:
  - Wrote scripts/summarize_calibration.py and ran it on the raw file. It is read-only: it uses nearest-rank percentiles over HTTP 200s and prints n on every row.
  - Raw run: 62 requests (59× 200, 3× 429), 36,397 tokens, completed.
  - Hypothesis results:
    - (a) confirmed: 30 successes (cal-021..050) then a 429 (cal-051) 13.031 s after the first b1 start.
    - (b) confirmed (cal-050/051/053; b4: 961 → 958 over 3 successes + 2× 429, then cal-059 at 957).
    - (c) confirmed for request limits (cal-052 on 20b got a 200 with remaining 989 while 120b was limited at 962).
    - (d) recovery ≤ 5.0 s (probe interval), retry-after 2.
    - (e) confirmed TPM 8,000. Found that the TPM check reserves prompt tokens + max_completion_tokens up front (cal-001: 310 = 182 + 128; b4 "Requested 2022/2023").
    - (f) reset-requests = (1000 − remaining) × 86.4 s on all 62 records. Continuous refill rejected (120b: 7/48 matches). "Whole 86.4 s periods credited per gap, fraction dropped" matches 46/48; the 2 misses are ordering among the concurrent b4 requests.
    - (g) server timings present on 59/59. Queue share of client total: 28.6% (120b), 60.7% (20b).
    - (h) medium uses 3–4× the reasoning tokens and hit the 300-token cap 3 of 4 times; the latency difference is unclear at n = 4/5.
  - Flagged:
    - The console file is actually named `_console.txt.txt` (left as is).
    - The 429 error bodies in the raw file contain the Groq organization ID.
    - The local clock is 2.2–3.2 s ahead of Groq's Date header.
    - 20 of the 59 200s produced no visible token because max_out 16 went entirely to reasoning.
    - The RPM refill behaviour fits neither a 60 s sliding window nor a continuous bucket.
- What I checked and how: Before reading Claude's summary, I read the console output myself: 30 successes in b1 then a 429 on cal-051; rem_req was 962 both before and after the 429 (so a rejected request does not use daily budget); 20b answered 200 with its own counter (989) while 120b was blocked; in b4, 3 of 5 ~2K-token requests passed. Then I recomputed one claim by hand on a real record: on the 429 (cal-051), x-ratelimit-remaining-requests = 962, so 1000 − 962 = 38 used, and 38 × 86.4 s = 3,283.2 s = 54 min 43.2 s, which matches the header x-ratelimit-reset-requests: 54m43.2s exactly. This confirms the daily limit refills at 1 request per 86.4 s (1000 per day). I renamed the console file to remove the double extension (contents unchanged). : I took screenshots of the Groq console Usage page (Cost/Activity) into docs/evidence/.
- What was wrong / what I caught: My hypothesis (f) said the daily counter "refills gradually"; the data showed it refills only in whole 86.4 s periods between requests, so under continuous load it never refills. My plan also gave tiny requests a 16-token output budget, which reasoning used up entirely: 20 of 59 successful requests produced no visible text.
- Decision I made: Treat "the daily quota never refills under continuous load" as a hypothesis until tested, because it rests on one run. Design around reserved tokens (prompt + max output), not used tokens, since Groq charges the full output allowance up front against the per-minute limit: every pipeline step gets a tight max_tokens, and reasoning_effort stays low. Test whether fast retries prevent recovery (Step 3d) before using it in the Retries section.

## 2026-11-12 – Step 3d – Retry experiment (dry run), redaction script, Table 1 draft
- Prompt (verbatim):

  ```text
  Step 3d. Numbered items.

  1. Write scripts/retry_experiment.py (same recording format, append-only, dry run unless --go) to test your hypothesis that the per-minute request limit only refills during gaps of at least 2 s. On openai/gpt-oss-120b, tiny requests (≤16 output tokens, reasoning_effort low, unique marker at the start):
     a) Burst until the first 429. Then AGGRESSIVE retry: one request every 1.0 s for 20 s. Record whether any 200 comes back and when.
     b) 60 s cooldown. Burst again until the first 429. Then POLITE retry: wait exactly retry-after (plus 0–300 ms random jitter) before each retry. Record time from the 429 to the first 200.
     Caps: 100 requests and 12K tokens in total (counted the same way Groq charges: prompt + max output). Show me the dry run and wait for my OK. Predict, before running, what each phase should show if your hypothesis is right and if it is wrong.

  2. Write scripts/make_submission_copy.py: copies results/raw/*.jsonl into results/submission/ with the organization ID replaced by "org_REDACTED", and writes results/submission/REDACTION.md listing exactly what was replaced and in which records. Never modify results/raw/. Don't run it yet.

  3. Draft docs/table1_draft.md: Table 1 from the brief (Limit | Value you found | How you found it | Confidence), filled only from the calibration evidence, citing record ids. Write "not measured" where we didn't measure (e.g. tokens per day, requests in flight at once). Add a short "Notes" list: the up-front reservation of max output tokens, retry-after rounding up, the 86.4 s daily refill rule, per-model limits, and the 2.2–3.2 s clock skew.

  4. Add to docs/DECISIONS.md: "Keep raw files untouched; submit a redacted copy produced by make_submission_copy.py. Decided by me, 2026-11-12." Add a Step 3d entry to docs/WORKLOG.md (my prompt verbatim).

  End with the status of items 1–4.
  ```
- What was done:
  - Wrote scripts/retry_experiment.py:
    - Reuses calibrate.py's helpers; records have the same fields plus `t_since_phase_429_end_ms`.
    - Writes results/raw/retry_<UTC>.jsonl.
    - Phases: a_burst, a_aggressive (20 × 1 s), 60 s cooldown, b_burst, b_polite (retry-after + 0–300 ms jitter, max 10).
    - Caps: 100 requests and 12K tokens, counted as prompt + max output for every sent request, 429s included.
  - Dry run: worst case 100 requests / ~9.5K estimated tokens; expected under H1 83 requests.
  - Wrote predictions for four hypotheses before running:
    - H1: whole intervals, every request resets the clock
    - H2: only accepted requests reset it
    - H3: continuous bucket
    - H4: 60 s sliding window
  - Wrote scripts/make_submission_copy.py: regex `org_…` → `org_REDACTED`. It checks that each raw file's SHA-256 is unchanged and that no ID remains in the copy, and writes REDACTION.md with file / line / record / JSON path. Only compiled, not run. A grep found one distinct org ID, 3 occurrences, all in the calibration file.
  - Drafted docs/table1_draft.md from calibration records only, with the notes requested. Tokens per day and requests in flight are marked "not measured"; the maximum overlap seen was 5.
  - Added the redaction decision to DECISIONS.md.
- What I checked and how: Before running, I checked that Claude Code wrote its predictions for H1–H4 BEFORE the run, so the result could not be fitted afterwards. I checked the dry run stayed under my caps (100 requests, 12K tokens) and waited more than 60 s after the last 120b call before running `--go` myself. After the run, I read the console output myself and noticed the aggressive retries succeeded every 3rd attempt: not never (H1) and not every 2nd (H2's prediction).
- What was wrong / what I caught: Nothing wrong in this step's code. The surprise was in the result: none of the four written predictions matched the aggressive phase exactly, which led to Step 3e.
- Decision I made: Run the experiment on 120b only, with tiny requests, to keep the cost low (8,784 tokens charged). Keep raw files untouched and submit a redacted copy (org ID) produced by a script, so reviewers can see exactly what was changed and why.

## 2026-11-12 – Step 3e – Retry experiment analysis
- Prompt (verbatim):

  ```text
  Step 3e. The retry experiment ran: results/raw/retry_20261112T145223Z.jsonl. Numbered items:

  1. Write scripts/summarize_retry.py and run it. Using the exact start times in the raw file (not the printed t+ values), for every aggressive-phase request compute the gap since the last ACCEPTED request and since the last request of any kind. Print a table with id, both gaps, status.

  2. Test my reading: "a request passes only if at least 2.0 s have passed since the last accepted request; rejected requests do not reset the clock." Say confirmed / rejected, with the smallest gap that passed and the largest gap that failed. Compare with your 4 written predictions (H1-H4): which held, and why H2's 'every 2nd retry' became every 3rd.

  3. Compute throughput: successes per second in the aggressive phase vs the best possible with polite 2.0 s spacing, and the share of wasted requests. This is my "retrying made things worse" case.

  4. Check the daily refill rule: your model predicts rem_req = 977 on rty-001 (954 at end of calibration, about 35 min idle). It shows 976. Recompute from exact timestamps across both raw files and explain the difference, or say the rule needs correcting.

  5. Update docs/table1_draft.md: the "Time until it recovers" row for requests per minute, with this evidence. Add to docs/DECISIONS.md: "Retry policy: wait at least retry-after measured from the last accepted request; jitter only added on top, never subtracted. Decided by me from retry_20261112T145223Z, 2026-11-12."

  6. Add a Step 3e entry to docs/WORKLOG.md (my prompt verbatim).

  End with the status of items 1-6.
  ```
- What was done:
  - Wrote scripts/summarize_retry.py. It reads the retry file plus the calibration file and computes every gap from recorded start times.
  - Raw: 83 requests (a_burst 30 + 1 × 429, a_aggressive 7/20, b_burst 30 + 1 × 429, b_polite 1/1), 8,784 tokens charged.
  - Your reading: confirmed. Smallest passing gap 2.009 s (rty-044), largest failing 1.996 s (rty-035), no exceptions. All 7 passes came ~1.0 s after a rejected request.
  - Predictions: H2 held. H1 rejected (7 passes, not 0). H3 rejected (bursts stopped at 30 twice). H4 rejected (passes during aggressive; polite passed at 2.247 s).
  - Why every 3rd retry instead of every 2nd: the 2nd retry after a success landed at 1.990–1.996 s (scheduler timing), just under 2.0 s, in 5 of 6 cases.
  - Throughput: 7 accepted in 19.997 s = 0.350/s; 65.0% wasted. A client spacing 2.0 s from the 429 end gets 9 in the same window (10 if timed from the last accepted request).
  - Daily rule: the user's 977 came from "about 35 min". The exact gap cal-062 → rty-001 is 2,021.1 s = 33.69 min = 23.39 periods, giving 954 + 23 − 1 = 976 = observed. The rule matches 114/116 accepted 120b records across both files; the 2 misses are the concurrent b4 swap.
  - Updated table1_draft.md: RPM recovery row, confidence, and notes. Added the retry-policy decision to DECISIONS.md.
- What I checked and how: From the console output I computed by hand the gap between each aggressive retry and the last accepted request, and saw that every rejection was at 1.995–1.996 s and every success at ≥ 2.0 s. I formulated the rule ("2.0 s since the last accepted request; rejections don't reset the clock") myself and asked Claude Code to test it from exact timestamps: confirmed, smallest gap that passed 2.009 s (rty-044), largest that failed 1.996 s (rty-035).
- What was wrong / what I caught: My planning assistant (Claude in claude.ai) estimated the idle gap as "about 35 minutes" and predicted rem_req = 977 on rty-001, against 976 observed. Claude Code recomputed from exact timestamps: 2,021.1 s = 23.39 periods of 86.4 s, so 954 + 23 − 1 = 976. The rule was right; the rounding was wrong. Lesson: check predictions against exact timestamps, never rounded times.
- Decision I made: Retry policy: wait at least retry-after measured from the last accepted request, jitter only added on top. Evidence: retrying every 1 s got 7 of 20 through (65.0% wasted, 0.35/s) vs 9–10 with 2 s spacing; a 5 ms shortfall (1.995 s instead of 2.0 s) turned a retry into a rejection. Open issues noted for later: with several requests in flight, "last accepted" is known late (0.2–0.8 s after sending), and token-limit 429s behave differently (steady refill, retry-after rounded up from 90 ms to 1 s).
- Note: I renamed results/raw/calibration_20261112T141038Z_console.txt.txt to remove a double extension added by Notepad. Contents unchanged.

## 2026-11-12 – Step Q – Evaluation questions
- Prompt (verbatim): Not a Claude Code step. Drafted with Claude (claude.ai) from the three PDFs I uploaded; the draft is in that conversation's history. I edited it in place into eval/questions.yaml (only change: verified: true on each question).
- What I did: Verified every question in the PDFs and set verified: true on each. Final set in eval/questions.yaml.  kept 26 of 26.
- What I checked and how: For each question, Ctrl+F in the PDF on a key fact (e.g. "4000", "0.03", "65%") and checked the page number printed at the bottom of the page. For the 4 refusal questions, searched each PDF for the key terms ("Japanese", "3-stage", "French", "SoundStorm") to confirm the papers do not answer them.
- What I found: While drafting, Claude (claude.ai) noticed that two papers contradict themselves. I verified both in the PDFs: Attention gives EN-FR BLEU as 41.8 (abstract, Table 2) but 41.0 (section 6.1, page 8); Dynamic Chunking gives DNA data efficiency as "nearly 4×" (abstract) but 3.6× (pages 4 and 17). Kept as q13/q14: a naive retriever cites whichever chunk it finds first, with full confidence, which gives a fourth failure mode for the naive-retriever section.
- What was wrong / what I caught: Nothing wrong found during verification: all 26 answers and page numbers matched the PDFs.
- Decision I made: Kept all 26 drafted questions unchanged, because every one verified and the set already covers the failure types I want to measure (single facts, exponents in tables, explanations, cross-paper, terminology traps, refusals including a references trap). The question set is assistant-drafted; my contribution here is verification.
## 2026-11-12 – Step 4 – Clean extraction, chunking, BM25, question schema, retrieval eval
- Prompt (verbatim):

  ```text
  Step 4. Numbered items. No API calls in this step. My verified questions are in eval/questions.yaml (do not modify it).

  1. Write scripts/clean_papers.py. It reads the PDFs again with PyMuPDF (span-level, so you can see font size and superscript flags) and writes data/papers/clean/<id>vN.jsonl. Never modify data/papers/extracted/. Fix the problems from docs/retriever_pitfalls.md and tag each fix with its pitfall number:
     - Detect "References" and appendix headings from the text itself, and give those blocks the right section instead of "Conclusion".
     - Tag every block with a kind: body, reference, table, figure_text, equation, header_footer, page_number.
     - Render superscripts as ^ (e.g. 10^20) and subscripts as _ (d_k) using span flags and size.
     - Join words split by hyphens at line breaks.
     - Keep the original text in a raw_text field and add a normalized field (NFKC, so mathematical italic letters become plain letters).
     - Keep section_path and add the section number when the heading block has one.
     Then show me before/after counts per kind and per paper, and 2 concrete before/after examples for each fix, including Attention's Table 2 FLOPs (3.3 · 10^18), Eq. 1, and H-Net's learning rates (6.25 × 10^-4).

  2. Write src/relay/chunking.py: builds chunks from the clean blocks with parameters: target size in tokens, overlap, section-aware or not, and which kinds to include (by default exclude reference, page_number, header_footer, figure_text). Every chunk carries paper id, section_path, section number, and page range, for citations.

  3. Write src/relay/retrieval.py with BM25 (explain which library or why your own). Design it so a second retriever (local embeddings) and an optional re-ranker can be plugged in later, but don't install those yet. Instead, tell me the install size and CPU speed on Windows of sentence-transformers with all-MiniLM-L6-v2 and a small cross-encoder, so I can decide.

  4. Write eval/SCHEMA.md describing the format of eval/questions.yaml as it is now: id, type (single_fact | table_number | explanation | cross_paper | term_trap | unanswerable), question, should_refuse, key_facts, gold (list of paper, section, page), note, verified. Validate my file against it and report any problems, without editing it.

  5. Write scripts/eval_retrieval.py: for each question in eval/questions.yaml and each retrieval setting in a small config (piece size, pieces fetched, re-rank yes/no), report whether a gold page was retrieved (recall@k, a hit if any retrieved chunk's page range covers a gold page of the right paper), the rank of the first gold hit, and the context size in tokens that would be sent to the model. Unanswerable questions: report the top score, so we can later choose a refusal threshold. Run it with 3 BM25 settings of your choice (small, medium, large pieces) on BOTH data/papers/extracted (the naive baseline) and data/papers/clean. Output to results/raw/retrieval_eval_<UTC>.jsonl plus a printed table, and list the questions that fail in every setting.

  6. Add a Step 4 entry to docs/WORKLOG.md (my prompt verbatim).

  End with the status of items 1-6.
  ```
- What was done:
  - **Page check.** Printed page numbers equal the PDF page index in all three papers, so gold pages map directly.
  - **scripts/clean_papers.py**
    - Reads rawdict spans and chars, writes data/papers/clean/. data/papers/extracted/ is untouched.
    - Blocks: 539/1062/865 extracted → 513/989/786 clean.
    - Blocks labelled "Conclusion": 378/254/26 → 6/8/6.
    - Table regions come from find_tables(lines) and are rendered row by row with " | ".
    - Equations are merged at char level, with fraction bars from page drawings.
    - Figure text comes from cluster_drawings + images + rotated lines.
    - Headers/footers are repeated margin text; the arXiv stamp regex was narrowed after it also matched reference entries.
    - Hyphen joins use the paper's own vocabulary, keeping compounds seen elsewhere (13 kept).
    - Pitfall 7: tables and captions are moved to the section of their first mention.
    - Several iterations, all caught in output:
      - Eq. 1 lost its left half
      - stacked sub/sup interleaved
      - `10^-^4` double marker
      - wrong reference size in small-exponent lines
      - `<|endoftext|>` crashing tiktoken
      - a heredoc patch that broke a string literal
    - Known leftovers: display math with large operators (H-Net eqs 8–11, Attention's inline 1/√d_k fraction) is still garbled. Moshi's p19 prompt templates (framed boxes) are tagged figure_text.
  - **src/relay/chunking.py**: target / overlap / section_aware / include_kinds; each chunk has a citation (paper, section number + title, pages). Separator tokens counted, so no chunk exceeds its target.
  - **src/relay/retrieval.py**: own BM25 (Okapi, k1 1.5, b 0.75), Retriever/Reranker protocols, RRF fusion, a fetch_k → rerank → final_k pipeline.
  - **Embedding/re-ranker sizes** (from the PyPI and Hugging Face APIs, nothing installed): about 210 MB of Windows wheels (torch 2.15.0 is 126.7 MB); models are 90.9 MB (MiniLM-L6, MiniLM cross-encoder) and 17.6 MB (TinyBERT-L2 cross-encoder). CPU speeds are estimates only, not measured.
  - **Schema**: eval/SCHEMA.md and scripts/validate_questions.py (read-only; SHA-256 unchanged before and after).
    - 26 questions.
    - The only error: `verified` is missing on all 26.
    - 0 warnings: every numbered gold section contains its gold page in the clean extraction.
  - **Retrieval eval**: scripts/eval_retrieval.py over 3 corpora (naive, clean_flat, clean_sec) × 3 BM25 settings (128/16/k8, 256/32/k5, 512/64/k3). Output: results/raw/retrieval_eval_20261112T154135Z.jsonl.
    - Recall@k 81.8–90.9% everywhere.
    - q22 fails in every setting.
    - The unanswerable near-misses q23/q25 get top scores (17–25) above the answerable median (~17), so a BM25 score threshold cannot drive refusals.
    - Naive retrieval returns the Moshi reference list (labelled "Conclusion") for q26.
  - Added pyyaml 6.0.3 to requirements.txt; added src/relay/__init__.py.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-12 – Step 4b – verified flags, fact hit, per-paper quota, embedding benchmark
- Prompt (verbatim):

  ```text
  Step 4b. Numbered items. No Groq API calls.

  1. I verified all 26 questions in the PDFs on 2026-11-12, but the verified flags were not saved in eval/questions.yaml. I authorise you to make exactly one change to that file: add "verified: true" as the last field of each of the 26 questions. Change nothing else. Show me the diff, then re-run scripts/validate_questions.py.

  2. Add a stricter metric to scripts/eval_retrieval.py: "fact hit" = for each answerable question, the share of its key_facts whose essential number or term appears in the retrieved context (normalize both sides: NFKC, unicode minus to "-", ignore spaces around ^, ×, ·). For each question, define the essential string(s) in a small explicit table in the script (e.g. q10: "3.3 · 10^18"), and show me that table so I can check it. Re-run on naive, clean_flat and clean_sec, and list the questions where naive hits the page but misses the fact.

  3. Add a retrieval variant "per_paper_quota": top-q chunks from each paper (try q=1 and q=2) merged with the global top-k, duplicates removed. Report recall, fact hit, cross-paper "all gold papers retrieved", and context tokens, against the plain BM25 settings.

  4. Benchmark embeddings and re-ranking for real, OUTSIDE the project: create a throwaway venv in %TEMP%, install sentence-transformers there, and time on my CPU: embedding all clean chunks once (all-MiniLM-L6-v2), one query embedding, and cross-encoder re-ranking of 20 candidates with ms-marco-MiniLM-L-6-v2 and ms-marco-TinyBERT-L-2-v2. Report p50/p95 over 20 runs, install size on disk, and recall/fact hit on my questions for: embeddings alone, BM25+embeddings fusion, BM25 + cross-encoder re-rank. Do not add anything to the project's requirements.txt. Delete nothing in the project.

  5. Add a Step 4b entry to docs/WORKLOG.md (my prompt verbatim). Also add to docs/DECISIONS.md: "Refusal is not decided by retrieval score: near-miss unanswerable questions (q23, q25) score higher than the answerable median. Refusal comes from the model reading the passages and from the check step. Decided by me from retrieval_eval_20261112T154135Z, 2026-11-12."

  End with the status of items 1-5.
  ```
- What was done:
  - **Item 1:** added 26 × `  verified: true` after each question's last field. CRLF preserved; diff shows 26 insertions and 0 other changes; the validator reports 0 errors and 0 warnings. A later repeat of the same request was not applied twice; the existing diff was shown instead.
  - **Item 2:** added a FACTS table (one essential string per key fact, tied to a paper; q21's third fact marked not retrievable) and `--facts`, which checks every string exists in its paper's clean text.
    - All strings found; all on a gold page except q22's byte-pair, whose paper has no gold page in q22.
    - Naive hits the page but misses the fact for q03 (10^-9), q10 (3.3 · 10^18) and q11 (6.25/5.0 × 10^-4) in every setting, plus q06/q14/q17/q18/q19/q21 in some.
    - Clean small/medium also miss q10's number: the table's header row and the base-model row land in different small chunks.
  - **Item 3:** added `PerPaperQuota` to src/relay/retrieval.py. Run file: results/raw/retrieval_eval_20261112T154833Z.jsonl.
    - Quota raises fact hit and "all papers" modestly at +15–120% context tokens.
    - clean_sec/large/quota_q2: recall 86.4%, fact hit 86.4%, all papers 2/5, 2,271 tokens on average (plain: 81.8%, 79.5%, 0/5, 1,049).
  - **Item 4:** throwaway venv at %TEMP%\relay_embed_bench (sentence-transformers 6.3.0, torch 2.15.0+cpu, 4 threads, Intel Family 6 Model 140, 8 logical CPUs). Script: scripts/bench_embeddings.py (runs only there). Raw: results/raw/embed_bench_20261112T155413Z.jsonl.
    - Timings, p50/p95 over 20 runs:

      | What | p50 | p95 |
      |---|---|---|
      | Corpus embedding, 762 / 403 / 233 chunks | 26.2 / 15.1 / 8.6 s | 37.1 / 24.8 / 9.2 s |
      | Query embedding | 9.7 ms | 17.9 ms |
      | MiniLM-L6 re-rank of 20 | 944 ms | 983 ms |
      | TinyBERT-L2 re-rank of 20 | 62 ms | 78 ms |

    - Disk: venv 1,078 MB (torch 539 MB); model cache 191 MB by `du`. The script's 603 MB double-counted the cache's snapshot links.
    - Embeddings alone are worse than BM25 everywhere, but they find q22's gold page. RRF fusion never improves recall and lowers fact hit. TinyBERT re-rank helps only at medium (fact hit 67.0 → 73.9%); MiniLM re-rank is worse and costs about 1 s.
    - Caveat: MiniLM's max_seq_length is 256 wordpieces, so medium and large chunks are truncated when embedded.
    - Nothing was added to requirements.txt and nothing in the project was deleted.
  - **Item 5:** added the refusal decision to DECISIONS.md.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-12 – Step 5 – Decisions, table-context chunking, model client, pipeline, fake tests, eval estimate
- Prompt (verbatim):
  ```text
  Step 5. Numbered items. NO Groq API calls in this step.

  0. Record in docs/DECISIONS.md (decided by me, 2026-11-12), with the evidence file for each:
     - Retrieval: BM25 on clean, section-aware chunks; no embeddings or cross-encoder in the project. Evidence: embed_bench_20261112T155413Z (embeddings worse than BM25 everywhere; MiniLM re-rank +~1 s TTFT and lower fact hit; TinyBERT +6.9 points only at medium, for a 1 GB dependency).
     - Time to first token = first token of the final answer the user sees.
     - The answer is drafted fully, checked, then streamed. The check is deterministic.
     - On a failed check: one redraft, then refuse and show the retrieved passages. Never loop more.
     - Router on openai/gpt-oss-20b, drafting on openai/gpt-oss-120b (limits are per model: cal-052).
     - Refusal is decided by the model and the check, not by a retrieval score.

  1. Chunking fix: in src/relay/chunking.py, repeat the table caption and header row at the top of every chunk that contains table rows. Re-run scripts/eval_retrieval.py and show me fact hit before/after, especially q10. In the FACTS table, change q20's essential string from "end-to-end" to "tokenizer-free".

  2. Write src/relay/model_client.py: one async interface ModelClient.stream_chat(model, messages, max_tokens, reasoning_effort, timeout) that yields tokens and returns a final record (timings, status, headers, usage, retries). Implement GroqClient (reusing the calibration code) and FakeClient (scripted replies, delays, failures, 429s) for tests. All retry logic lives in ONE place and follows my policy in docs/DECISIONS.md (wait at least retry-after from the last accepted request, jitter only added on top).

  3. Write src/relay/pipeline.py with these steps, each timed separately (waiting, working, retrying):
     a) route: one call to gpt-oss-20b, max_tokens <= 150, JSON output: keywords, likely papers, in_scope (bool). If out of scope: refuse immediately (branch).
     b) retrieve: BM25 tool call, wrapped with a timeout.
     c) draft: one call to gpt-oss-120b, reasoning_effort low, tight max_tokens (propose a value from our calibration and say why). The prompt requires a [n] citation after every claim, referring to numbered passages, and a refusal sentence if the passages do not answer.
     d) check: a deterministic tool: every [n] exists; every number in a cited sentence appears in passage n (normalized as in the fact-hit metric); a refusal is allowed. On failure: one redraft with the check's error message, then refuse with the passages.
     e) stream the checked answer to the user, recording time to first token and total time.
     Every request produces exactly one results.csv row with the columns in CLAUDE.md, plus a separate per-step trace file (results/raw/traces_<UTC>.jsonl) for the "where the time goes" section.

  4. Tests with FakeClient only: a normal answer, a refusal, a check failure that is fixed by the redraft, a check failure that ends in refusal, a 429 on the draft call, a tool timeout. Show me the test output and one full trace.

  5. Estimate (do not run) the real end-to-end evaluation: my 26 questions x 3 retrieval settings. Give requests and reserved tokens per model (charged as prompt + max_tokens), the expected duration at 8K tokens/minute, and whether it fits in one day's budget per model.

  6. Add a Step 5 entry to docs/WORKLOG.md (my prompt verbatim).

  End with the status of items 0-6.
  ```
- What was done:
  - No Groq calls were made in this step.
  - **Item 0:** added Retrieval [12, 13], Time to first token [3], Check versus streaming [5], Failed check [8], Models [1] and Refusal (restated) to DECISIONS.md, each with its evidence file. TTFT, check-then-stream and the failed-check rule have no evidence file ("none"). The "Still open" list was updated; 11 and 17 are marked as partly settled.
  - **Item 1:** `ChunkConfig.table_context` (on by default). Every chunk holding table rows now starts with the caption's first sentence plus the table's header lines.
    - Header = the lines before the first line with a numeric cell, at most 4. The full caption block stays in the corpus once.
    - Captions are paired with their table (same page, within 2 blocks, forward first): 31/31 tables in the three papers paired correctly, including the captions placed below their tables (H-Net Tables 5 and 7, Moshi Table 18).
    - The full caption was not repeated: captions run up to 185 tokens, against first sentences of at most 42.
    - Table rows now stay one per line inside chunks; before, they were joined with spaces.
    - q20's essential string changed to "tokenizer-free". `match_norm` moved to src/relay/textnorm.py, shared by the eval and the check.
    - Raw files:
      - before (`--no-table-context`): results/raw/retrieval_eval_20261112T221922Z.jsonl
      - after: results/raw/retrieval_eval_20261112T221926Z.jsonl
    - Fact hit, plain BM25, before → after:

      | Setting | Fact hit |
      |---|---|
      | clean_sec small | 70.1 → 75.8% |
      | clean_sec medium | 67.0 → 75.0% |
      | clean_sec large | 79.5 → 79.5% |
      | clean_flat small | 67.8 → 75.8% |
      | clean_flat medium | 73.5 → 80.3% |
      | clean_flat large | 82.6 → 80.3% |

    - Recall is unchanged everywhere.
    - q10 is now found at small and medium (0 → 1). q12 too (0.25 → 1).
    - Regressions, from shifted chunk boundaries:
      - clean_sec small: q14 loses "nearly 4", and q21 loses its second paper (all papers 2/5 → 1/5).
      - clean_flat large: q08 loses "6.0 bytes per chunk".
    - Chunk count: small 762 → 918, medium 403 → 424, large 233 → 237. No chunk exceeds its target.
  - **Item 2:** src/relay/model_client.py.
    - `stream_chat` returns a `ChatStream`: async-iterate it for tokens; `.record` (or `await .collect()`) gives the CallRecord: wait/retry/work/total ms, first-token ms, status, outcome, rate-limit headers, usage and server timings, retries, and every attempt.
    - The only retry loop is `ModelClient._run`:
      - Only 429s are retried, and only before any token arrives.
      - The wait runs until last accepted request to that model + retry-after (from now if none yet), plus uniform jitter added on top.
      - The wait is shared per model, through a RateGate. At most 3 retries, and never past the call timeout.
    - Fixed during testing: on Windows the event-loop timer can wake about 16 ms early, so the gate re-sleeps until the precise clock has really passed the wait.
    - GroqClient uses the same body and SSE parsing as calibrate.py; the key comes from .env and is never shown (`__repr__` hides it). FakeClient plays scripted replies, delays, 429s, stalls and network errors.
  - **Item 3:** src/relay/pipeline.py and src/relay/recording.py: route → retrieve (BM25Tool, `asyncio.wait_for`) → draft → check (→ one redraft → recheck) → stream.
    - Every step writes a trace line with wait_ms/retry_ms/work_ms, plus a closing "request" line. Exactly one results.csv row per request, including on exceptions; the CSV header is validated before appending.
    - Statuses: answered, refused, refused_out_of_scope, refused_check_failed, tool_timeout, rate_limited, model_error, error.
    - Proposed draft max_tokens is 400 (see the Step 5 report).
  - **Item 4:** tests/test_pipeline.py (stdlib unittest, FakeClient only): 19 tests, all passing, stable over 3 more runs.
    - The six requested scenarios, plus out-of-scope, exhausted 429 retries, router bad JSON, one row per request under concurrency, the retry-policy timing, jitter only added, per-model gates, timeouts, and check unit tests.
    - The demo trace (real BM25 medium, fake models, 429 on the draft) was written to the scratchpad, not results/.
  - **Item 5:** scripts/estimate_eval.py builds the exact prompts and makes no calls. 78 runs.
    - 20b: 78 requests, 30,288 reserved tokens, about 2.8 min of the 8K TPM, 15% of 200K TPD.
    - 120b: 78–156 requests, 130,521 (no redrafts) to 305,034 (every run redrafts) reserved tokens, about 15–37 min, 65–153% of 200K TPD.
    - Requests are at most 15.6% of 1K RPD.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-12 – Step 5b – Brief-exact results values, my pipeline decisions applied, one-setting estimate
- Prompt (verbatim):
  ```text
  Step 5b. Numbered items. NO Groq API calls.

  1. Fix results.csv values to match the brief exactly: status only in {ok, rate_limited, timeout, error}; source only in {real, stand-in}; answer_grade only in {correct, wrong, refused_correctly, refused_wrongly} or empty until graded. Map pipeline outcomes explicitly (e.g. answered -> ok, a refusal by the model -> ok with the refusal recorded in the trace, tool timeout -> timeout). FakeClient runs must not write source=fake to any results.csv: tests write only to a temp directory. Add a test that rejects any other value.

  2. Apply my decisions and record them in docs/DECISIONS.md (decided by me, 2026-11-12):
     - Draft max_tokens = 400 (evidence: cal-006..010, 118-300 output tokens, 1/5 hit 300).
     - Router max_tokens = 200 (evidence: 2/5 small 20b calls hit 128 in calibration).
     - Retrieval uses the user's question as is; the router only decides in/out of scope, and its keywords and papers are logged, not used. Reason: the retrieval evaluation measured the raw question.
     - Request-limit 429 (body type "requests"): wait retry-after measured from the last accepted request, jitter on top. Token-limit 429 (body type "tokens"): wait retry-after measured from now, jitter on top. Evidence: retry_20261112T145223Z and cal-056/057.
     - 500/502/503/498: retry once, with the same jitter. A client timeout is never retried.
     - A sentence containing a number without a citation fails the check.
     - Each run writes results/raw/run_<scenario>_<UTC>.csv; scripts/build_results.py rebuilds results/results.csv from all raw run files, sorted by start_time, never edited by hand.
     Update the tests to cover each of these rules and show me the test output.

  3. Re-run scripts/estimate_eval.py for ONE retrieval setting (26 questions) with these settings: requests and reserved tokens per model, low (no redraft) and high (all redraft).

  4. Add a Step 5b entry to docs/WORKLOG.md (my prompt verbatim).

  End with the status of items 1-4.
  ```
- What was done:
  - No Groq calls were made in this step.
  - **Item 1:** src/relay/recording.py now defines the allowed sets and `validate_row`. ResultsWriter rejects any other status, source or answer_grade value, and also checks start_time format and integer counts.
    - The pipeline keeps a detailed outcome in the trace and maps it with `OUTCOME_TO_STATUS`:
      - **ok:** answered, refused, refused_out_of_scope, refused_check_failed
      - **timeout:** tool_timeout, model_timeout
      - **rate_limited:** rate_limited
      - **error:** model_error, error
    - Sources: GroqClient writes "real". FakeClient has no "fake" value: it takes a valid label (default "stand-in"), and Pipeline raises if a FakeClient run would write its results or trace file anywhere under the repo's results/. Tests use a temporary directory only.
  - **Item 2:** all seven decisions applied and recorded in DECISIONS.md.
    - Draft max_tokens 400 and router max_tokens 200. The router's 128-token hits are cal-014 and cal-015.
    - Retrieval now always uses the question as is. The route step's trace line logs keywords, papers and router_fallback.
    - Fixed while testing: those route details used to be added after the trace line was written, so they never reached the file. The same was true of router_fallback in Step 5.
    - 429 wait by body `error.type`. Calibration and the retry run show exactly "requests" and "tokens". An unknown type is measured from now (my choice, listed as open).
    - 500/502/503/498 retried once after the jitter only. Timeouts, network errors, stream errors and other statuses are not retried.
    - An uncited sentence with a number is now an error.
    - `relay.recording.run_path` and the new scripts/build_results.py (refuses to write on a bad header, a bad value or a duplicate request_id; writes atomically).
    - Open-decision bookkeeping: 26 is removed from "Still open". 6 and 18 stay open with notes, because they are only implied by the code.
  - **Item 2 tests:** tests/test_pipeline.py now has 33 tests, all passing, stable over 3 more runs.
  - **Item 3:** scripts/estimate_eval.py gained `--setting`; run once per setting (26 runs each). See the Step 5b report for the table.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-12 – Step 6 – Eval runner, pre-grading, cut for time
- Prompt (verbatim):
  ```text
  Step 6. We are short on time: I submit in under 5 hours. Work fast, keep scope tight, numbered items, end with status. No real Groq call without my explicit OK.

  1. Fix results.csv values to match the brief exactly: status only {ok, rate_limited, timeout, error}; source only {real, stand-in}; answer_grade only {correct, wrong, refused_correctly, refused_wrongly} or empty until graded. A model refusal is status ok. Tool timeout and user give-up are status timeout. Tests write only to a temp dir and never write source=fake into results. Add a test rejecting any other value.

  2. Apply and record in docs/DECISIONS.md (decided by me, 2026-11-12): draft max_tokens 400 (cal-006..010); router max_tokens 200 (2/5 small 20b calls hit 128); retrieval uses the raw question, router only decides in/out of scope; request-429: wait retry-after from the last accepted request, token-429: wait retry-after from now, jitter on top in both; 500/502/503/498 retried once; client timeouts never retried; an uncited number fails the check; each run writes results/raw/run_<scenario>_<UTC>.csv and scripts/build_results.py rebuilds results/results.csv. Also record: "Cut for time: the daily-budget-exhausted scenario runs on the stand-in only; retrieval settings 2 and 3 are evaluated on 15 questions, setting 1 on all 26."

  3. Write scripts/run_eval.py: runs the pipeline on eval/questions.yaml (option --setting, option --questions q01,q02,...), real Groq, sequential, writes results/raw/run_eval_<setting>_<UTC>.csv and traces. Dry run by default (requests and reserved tokens per model); --go to run.

  4. Write scripts/pregrade.py: for each answer in a run, suggest a grade: unanswerable question → refused_correctly if the answer refuses, else wrong; answerable → refused_wrongly if it refuses; correct if all its FACTS strings appear in the answer and at least one citation points to a gold paper+page, else wrong. Write eval/grades_<run>.csv with columns qid, question, answer, citations, suggested_grade, reason, final_grade (empty). Then scripts/apply_grades.py copies final_grade (or suggested_grade if I leave final empty, and record which) into the run CSV's answer_grade.

  5. Show me the dry run of run_eval.py for setting "medium" on all 26 questions, and wait for my OK. I will run --go myself.

  6. Short Step 6 entry in docs/WORKLOG.md (prompt verbatim).
  ```
- What was done:
  - **Items 1–2:** already done in Step 5b. New this step:
    - outcome `user_gave_up` maps to timeout (with a test);
    - retrieve traces now carry each hit's paper and pages, for grading;
    - DECISIONS.md gains "Cut for time" (verbatim) and "User give-up".
  - **Item 3:** scripts/run_eval.py.
    - Dry run by default; `--go` uses GroqClient, runs sequentially, and writes run_eval_<setting>_<UTC>.csv plus traces_eval_<setting>_<UTC>.jsonl.
    - request_id is `eval-<setting>-<UTC>-<qid>`.
    - It stops after 3 rate_limited/error rows in a row.
  - **Item 4:** scripts/pregrade.py written and smoke-tested on a fake run in the scratchpad (correct, wrong, refused_wrongly, refused_correctly and status-not-ok paths). Rows whose status is not ok get no suggestion.
    - scripts/apply_grades.py was NOT written: it would rewrite answer_grade inside raw run files, against the CLAUDE.md rule "Raw results are append-only". Claude asked how to proceed.
  - **Item 5:** dry run, medium, 26 questions:
    - 20b: 26 requests, 11,396 reserved tokens.
    - 120b: 26–52 requests, 43,578–101,820 reserved tokens.
    - Total: 52–78 requests, 54,974–113,216 reserved tokens.
  - Found while smoke-testing: in the medium setting, the raw q01 question does not retrieve the "h = 8" passage.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-13 – Step 6b – Partial real run stopped: check and router fixes
Partial run stopped after 11 questions: over-strict check refused correct answers and its redrafts doubled token use (TTFT up to 23 s).
- Prompt (verbatim):
  ```text
  URGENT, before continuing Step 7. I stopped results/raw/run_eval_medium_20261112T225309Z after 11 questions: 5 refused_check_failed (q02, q03, q08, q10, q11), q04 refused as out of scope (it is about Mimi, clearly in scope), q01/q06/q09 refused by the model. Do not modify that partial run file.

  1. From its traces, show me for q02, q03, q08, q10, q11: the draft and the exact check error, in one short table.
  2. Fix the number check so equivalent notations match (× · x *, 10^-4 / 10−4 / e-4, thousands separators, number words one to twelve, numbers attached to units like 12.5Hz or 160ms), but still fail on a genuinely different number. Add tests built from these real failures.
  3. Router: put the three paper titles and a one-line topic for each in its prompt. Refuse as out of scope only when the question is clearly unrelated to all three papers; when unsure, in scope. Show me the new prompt.
  4. From the traces of q06 and q09, say whether a gold page was among the retrieved passages.
  5. Show the dry run again. Add a WORKLOG entry: "Partial run stopped after 11 questions: over-strict check refused correct answers and its redrafts doubled token use (TTFT up to 23 s)."
  Then continue Step 7.
  ```
- What was done:
  - The partial run files were only read, never modified. The run CSV holds 13 rows (q01–q13). Max first_token_ms is 22,973 (q08).
  - **Main cause:** gpt-oss wrote citations as 【1】 / 【1†L4-L5】, not [1]. The check saw "no [n] citation" and counted the citation digits as uncited numbers. Second cause: superscript exponents (10⁻⁹, 10¹⁸) were read as "10", "9" / "1018".
  - **Fix:**
    - `normalize_citations` maps 【n】, ［n］ and 【n†…】 to [n] in the check and in the shown answer.
    - `textnorm.number_values` compares numeric values. It handles × · x *, ^ / unicode minus / superscripts / e-notation, thousands separators, number words one–twelve, and units attached (12.5Hz, 160ms). The passage side also counts the parts of a scientific number.
  - **Replay:** all 10 real drafts and redrafts of q02/q03/q08/q10/q11 now pass. q13's real redraft still fails, correctly: it cites [1] for 41.8, which is only in [2]/[3].
  - **Tests:** verbatim real drafts pass; the same drafts with one number changed fail; the q13 wrong source fails; notation-equivalence tests. 39 tests total, all pass.
  - **Router prompt:** now has titles plus a one-line topic per paper; out of scope only when clearly unrelated to all three, in scope when unsure. About 319 tokens; 20b reserved for 26 questions goes from 11,396 to 15,504.
  - **q06 / q09:** a gold page WAS retrieved for both (q06 gold p.16: passage [2] §3.4.4 pp.16-17; q09 gold p.12: passages [1], [3], [4]). The model refused anyway.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-13 – Step 7 – Grades option A, stand-in, load tests, tables
- Prompt (verbatim):
  ```text
  Choose A for apply_grades.py: grades go to results/raw/grades_<run>.csv, build_results.py fills answer_grade in results/results.csv. Record it in DECISIONS.md. Keep q01's retrieval miss as it is: it is a real finding.

  Then Step 7. Short on time. Numbered items, end with status. No real Groq calls in this step (I am running the real eval myself in another window right now, so do not touch results/raw/run_eval_*).

  1. Build the stand-in in standin/: an OpenAI-compatible HTTP server (/v1/chat/completions, streaming SSE, same response headers x-ratelimit-* and retry-after, same 429 JSON bodies with type "requests" or "tokens") so the pipeline uses the same client code. Calibrate from results/raw/calibration_*.jsonl and retry_*.jsonl: resample measured queue time, time to first token and generation speed per model; RPM 30 with the measured rule (admit only if >= 2.0 s since the last accepted request once the burst of 30 is used; rejections don't reset the clock); TPM 8000 charged as prompt + max_tokens, refilling steadily; RPD with the measured 86.4 s whole-period refill (configurable, so a scenario can set a small daily budget); slower under load (service time grows with requests in flight, parameter documented); configurable failure rate (5xx) and slow-success tail. Write docs/standin.md: each parameter, which raw records it comes from, and where the stand-in is least like the real service.

  2. Build loadtest/run_load.py: open-loop arrivals (Poisson), simulated users who give up if no first token within 15 s (status timeout), pipeline pointed at the stand-in, retrieval real (local), results to results/raw/run_<scenario>_<UTC>.csv with source=stand-in plus traces. Scenarios, about 2-3 minutes each: steady (below the limits), burst (sudden spike after a quiet start), sustained_overload (well above the limits), rpm_halved (stand-in RPM set to 15), daily_exhausted (daily budget small enough to run out mid-run). Record queue length over time for the peak queue column. Use a different port and do not share any rate-limit state with the real GroqClient.

  3. Write scripts/make_tables.py: from results/results.csv, produce Tables 2a, 2b and 3 exactly as in the brief (milliseconds, one decimal for percentages, "not measured" where not measured, p50/p95/p99), plus tokens per answer and cost per 1,000 answers from list prices (gpt-oss-120b $0.15/$0.60, gpt-oss-20b $0.075/$0.30 per million in/out; state the assumption used to split tokens by model). Output docs/tables.md.

  4. Run all five scenarios against the stand-in, rebuild results.csv, run make_tables.py and show me the tables.

  5. Short Step 7 entry in docs/WORKLOG.md (prompt verbatim).
  ```
- What was done:
  - **Option A:** scripts/apply_grades.py writes results/raw/grades_<run>.csv (request_id, qid, answer_grade, grade_from = final or suggested). build_results.py fills answer_grade from it. Recorded in DECISIONS.md, together with keeping q01's retrieval miss.
  - **Item 1:** standin/server.py (asyncio HTTP, SSE, Groq-style headers and 429 bodies) and standin/calibrate_standin.py, which writes standin/calibration.json from the 127 accepted / 18 rate-limited real requests. docs/standin.md lists every parameter and its source, and where the stand-in is least like the real service. The load slowdown, 5xx rate and slow tail are assumptions, not measurements.
  - **Item 2:** loadtest/run_load.py: Poisson arrivals, give-up after 15 s, one stand-in per scenario on its own port.
    - Pipeline changes: give_up_s (outcome user_gave_up maps to timeout), and a call cancelled by the give-up is still traced with its attempts.
    - The stand-in counts 429s per model and type.
    - 40 tests pass.
  - **Item 3:** scripts/make_tables.py writes docs/tables.md. Rows are one per run (scenario, source, run stamp). It supports an optional, hand-kept results/excluded_runs.csv. Router/draft split for cost: the first 396 input and 76 output tokens of each request are the router.
  - **Item 4, runs:**
    - First run of all 5 scenarios: 20261113T073115Z. daily_exhausted with rpd 20 never ran out.
    - Re-runs (daily with rpd 8; overload scenarios with the cancelled-call tracing) 073425Z / 0735xxZ hit a 359 s freeze of every process at 07:36:04–07:42:03 UTC. Their latency is invalid.
    - Clean re-runs: 20261113T080028Z. Every run stays in raw.
  - Found:
    - Under overload most 429s are token-limit 429s on the 20b router: each route reserves about 600 tokens.
    - A daily-limit 429 is type "requests". When the last accepted request was more than 87 s ago, the decided rule computes a wait that has already passed, so the client retried at once, three times (traces daily_exhausted 073425Z, requests 0013/0015).
    - Halving RPM to 15 changed little (success 21.7% against 27.3% in sustained_overload, run 080028Z): TPM binds first.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-17 – Step 8 – Finishing: daily-limit fix, decisions, exclusions, README, submission copy, write-up draft
- Prompt (verbatim):
  ```text
  what else is remaining  to do ? you are free to finish and take decisions by yourself
  ```
- What was done (no Groq calls):
  - **Daily-limit fix:** `limit_kind` reads the 429 body. A daily-limit 429 ("requests" type, message "per day (RPD)") becomes "requests_per_day" and is never retried. The person gets the budget message, the reset time and the passages. Outcome rate_limited_daily, status rate_limited. 42 tests pass.
  - **Stand-in re-run of daily_exhausted:** run 20261117T101038Z. 0 retries (3 useless ones before), 43.8% rate-limited with passages shown, 0% given up (18.8% before).
  - **DECISIONS.md:** a section for the decisions of 2026-11-17, covering open decisions 4, 6, 7, 11, 14–25, the tables' exclusions and the 15-question subset. Nothing is left open.
  - **results/excluded_runs.csv:** 10 runs, each with its reason (superseded, the 359 s freeze, the never-exhausted daily run, the stopped partial eval). make_tables.py lists them under the tables, and their rows stay in results.csv.
  - **make_tables.py** now also writes Table 1 (from docs/table1_draft.md). docs/tables.md is regenerated.
  - **make_submission_copy.py** now copies every raw .jsonl/.csv/.txt. Ran it: 52 files plus REDACTION.md in results/submission/; no organization ID is left.
  - **README.md** gained a "Run it" section (cmd).
  - **docs/writeup.md:** a draft in the brief's heading order. ⟦FILL⟧ marks numbers from the real eval; ⟦YOURS⟧ marks the personal sections.
  - **Proposed real eval:** medium on all 26 questions; small and large on the 15-question subset.
    - 20b: 56 requests, 33,408 reserved tokens.
    - 120b: 56–112 requests, 93,545–218,674 reserved tokens.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-17 – Step 9 – Personal project: validity work, day-1 real eval, stand-in validation
- Prompt (verbatim):
  ```text
  ok, here are the changes , this project is no longer an assignment , it is now a personal project that i aim to present. i no loger need How I worked with the assistant and so on , i want the project to be valid and well evaluated and so on .
  ```
  Then: "the free tier is refilled every day isnt it ?", "ok go ahead" (OK for day 1: medium + small, 26 questions each), "how is the eval going?".
- What was done:
  - **Load tests at a size you can trust:** 10 minutes × 3 seeds per scenario. make_tables pools the runs of each scenario and adds an uncertainty table (Wilson and bootstrap 95% intervals, spread across seeds). The old short runs are excluded with reasons.
  - **Day-1 real eval:** run_eval_medium_20261117T102821Z and run_eval_small_20261117T103158Z, no failures.
    - Graded with the improved rubric (numeric facts compared by value), plus a review of every doubtful answer. 9 of 52 grades changed; the rubric agreed on 82.7%.
    - medium: 50.0% correct and cited, 15.4% wrong, 4/4 unanswerable refused. small: 46.2%, 7.7%, 4/4.
  - **Found in the day-1 traces, fixed for future runs:**
    - 8 false check failures: `[0,1]` read as a citation, thousands written with a narrow no-break space, superscript decimals, "Paper N". Frozen as a test fixture.
    - The router refused q14 as out of scope; a deterministic guard now prevents that.
    - Back-to-back evals throttle themselves on token-limit 429s, so real evals are paced by default.
    - 45 tests pass.
  - **Stand-in validation** (run_eval --standin, scripts/compare_standin.py): calibration v1 was 1.6–1.9× slower than the real service. Calibration v2 (adds the real medium-eval calls) is within 1.18× (router) and 1.09× (draft) on the held-out small run. The campaign was re-run on v2.
  - **v2 campaign:**
    - steady: 100% succeeded, first token p50 1,208 ms.
    - sustained: 23.4% [20.2, 26.9] against RPM-halved 24.7% [21.5, 28.4].
    - RPM-halved runs had zero request-limit 429s: the 20b router's token limit binds first.
  - **docs/report.md** written (it replaces docs/writeup.md; no assignment-only sections). docs/standin.md gained a validation section; README reframed as a project.
  - Next: day 2 (large + a medium re-run on the current system, paced). 20b: 52 requests, ~31K reserved tokens. 120b: 52–104 requests, 89K–207K reserved tokens.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-18 – Step 10 – Day-2 real eval (large + medium re-run), check fixes, retrieval decision
- Prompt (verbatim):
  ```text
  go ahead
  ```
  (Day 2 as announced: 20b 52 requests, ~31K reserved tokens; 120b 52–104 requests, 89K–207K reserved tokens; plus a commit of the earlier work.)
- What was done:
  - Committed all earlier work (42e6f5e) after scanning for keys and org ids.
  - **Day-2 real eval, paced:** run_eval_large_20261118T091718Z and run_eval_medium_20261118T092253Z. All 52 requests ok, zero 429s. First token p50 1.7–1.8 s, against 9.5–9.9 s on unpaced day 1.
  - **Graded with the day-1 rules:** rubric suggestion, then every doubtful answer was reviewed and the rest skimmed. 10 of 52 grades changed. Notably, medium q03 is marked wrong because it attributes Moshi's AdamW to the Transformer, and q14 needs both values under the q13 rule.
    - large: 50.0% correct [32.1, 67.9], 23.1% wrong.
    - medium: 42.3% [25.5, 61.1], 26.9% wrong.
    - 4/4 unanswerable questions refused in both runs.
    - Rubric agreement over all 104 answers: 81.7%.
  - **Two new false check failures, fixed:** LaTeX `\tfrac12` was read as 12 (medium q17), and "one‑third" was read as "one" (large q14; NFKC maps U+2011 to U+2010, which was not normalised). Frozen in tests/fixtures/day2_false_check_failures.json. 47 tests pass. Re-checking 96 recorded first-draft checks turns no pass into a fail.
  - **Table 3 is now one row per eval run,** labelled with the system version, with a Wilson interval on correct %. Before this, it pooled day-1 and day-2 medium.
  - make_tables.py and compare_standin.py crashed on cmd's cp1252 console; they now print UTF-8.
  - **Stand-in held-out check on large, next day:** router 0.71×, draft 0.80× of real. The real service was 1.4–1.6× slower than on the calibration day, so stand-in latencies are good to about ±40%.
  - **Retrieval stays medium:** large against medium is 3 vs 1 questions paired (McNemar p = 0.63), no measurable difference, and the load campaign is on medium.
  - Updated report.md (sections 2, 3, 4, 6, 7, 9), standin.md, DECISIONS.md, tables.md and standin_validation.md; rebuilt results.csv (4,217 rows).
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-18 – Step 11 – Answer-quality improvements (offline): paper cover, multi-paper draft rules
- Prompt (verbatim):
  ```text
  what is this ? Grade spot-check (optional) + the results are acceptable ? if not, do you require any improvement ?
  ```
  then:
  ```text
  go ahead + how long this project in total will still take ?
  ```
- What was done:
  - **Retrieval, paper cover** (`PaperCover` in src/relay/retrieval.py, used by BM25Tool): adds another paper's best chunk only when the question names that paper's terms, asks about all papers, or the chunk scores ≥ 0.7 × top. Medium fact hit 75.0% → 78.8% for +4.6% context; recorded in retrieval_eval_20261118T103625Z.
  - **Draft prompt:** four new rules (attribute each statement to its paper; cover each paper asked about; give each meaning of a shared term; report differing values side by side). 6 sentences, `draft_max_tokens` 400 → 500.
  - 4 new tests for the cover; 51 tests pass.
  - New medium dry run: 20b 26 requests, 15.5K reserved tokens; 120b 26–52 requests, 50K–118K reserved tokens.
  - Not yet measured on the real service. These changes were designed from failures on the eval questions, so they need a held-out check (DECISIONS.md).
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-18 – Step 12 – Held-out question set
- Prompt (verbatim):
  ```text
  go ahead
  ```
- What was done:
  - Wrote 13 held-out questions, q27–q39, in eval/heldout.yaml. Each fact was found in data/papers/clean and checked to be on its gold page. The two unanswerable questions were checked to be absent from all three papers.
  - Added `run_eval.py --heldout` (scenario eval_heldout). pregrade loads both question files, Table 3 lists held-out runs separately, and the FACTS rubric strings for q27–q37 were added.
  - Validator: 0 errors, 0 warnings. 51 tests pass.
  - Held-out medium dry run: 20b 13 requests, 7.7K reserved tokens; 120b 13–26 requests, 25K–58K reserved tokens.
  - Next: check q27–q39 in the PDFs (set `verified: true`), then freeze the hash.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:

## 2026-11-18 – Step 13 – Held-out questions checked in the PDFs, blind second grader
- Prompt (verbatim):
  ```text
  you can verify at my place and eval and grade check too
  ```
  Then (mid-task): "tomorrow will be the last day of work ?"
- What was done:
  - Checked q27–q39 against the rendered PDF pages: no fact was wrong, and q36 was widened (Mimi's batch also counts). Marked verified. Frozen (sha256 in DECISIONS.md).
  - Did not run the real eval today: today's runs already used about 100K tokens. It runs tomorrow, announced with its cost first.
  - **Blind second grader:** agreed on 50/52 day-2 grades (96.2%, κ 0.94). It found that q05 needs the 200 ms latency achieved in practice; regraded wrong in all 4 runs via the new append-only regrades file.
  - Corrected numbers:
    - large 46.2% correct, 26.9% wrong;
    - medium (current) 38.5%, 30.8%;
    - medium (day 1) 46.2%, 19.2%;
    - small (day 1) 42.3%, 11.5%;
    - rubric agreement 77.9%.
  - Report, tables, DECISIONS updated; 51 tests pass.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made:
