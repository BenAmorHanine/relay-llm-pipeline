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
- What Claude did: Read all 4 pages of the brief. Created src/relay/, standin/, loadtest/, eval/, data/papers/ and results/raw/, each with a .gitkeep so git tracks it. Wrote a short README.md (purpose, layout table, Windows venv setup), a .gitignore (.env, .venv, __pycache__, tool caches, data/cache/, OS/editor files; data/papers/ and results/raw/ deliberately left tracked) and a .env.example containing only `GROQ_API_KEY=`. Did not add pyproject.toml, requirements.txt or `__init__.py` files (left as design decisions). Nothing committed.
- What I checked and how: I compared Claude's reply against my numbered prompt item by item. The skeleton (folders, .gitignore, .env.example, README) matched item 1, and I confirmed .env is ignored while data/papers/ and results/raw/ stay tracked, since reviewers need the raw results. But WORKLOG.md, CLAUDE.md and the brief checklist were missing, so I sent a follow-up (Step 1b) assuming Claude had skipped items 2–4. Claude then showed that the prompt it received ended after item 1: my paste was truncated. I checked my own message and confirmed it.
- What was wrong / what I caught: The prompt was truncated after item 1. The assistant did item 1 and did not flag that the list looked incomplete.
- Decision I made (and if I overruled Claude, why): Kept the skeleton as built. Added a rule to CLAUDE.md: "If a prompt from me looks truncated or contradicts an earlier rule, stop and ask before acting," and another requiring every reply to end with each numbered item marked done / not done, so a missing item is visible immediately. From then on I paste each prompt as one complete block.

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
- What Claude did: Pointed out that the previous prompt contained only item 1 (no WORKLOG template, no hard rules), so items 2 and 3 could not be done "exactly as written" without inventing text. Did not create WORKLOG.md or CLAUDE.md; asked for the missing content. Proposed a more accurate "What was wrong" wording for Step 1. Delivered 4a (full checklist of hard requirements) and 4b (26 open decisions with options and trade-offs, no recommendations) in the reply. Ended with item status: 2 not done, 3 not done, 4a done, 4b done.
- What I checked and how:
- What was wrong / what I caught: My follow-up wrongly assumed the assistant had skipped items 2–4; they were never in the prompt it received because my paste was truncated.
- Decision I made (and if I overruled Claude, why):

## 2026-11-12 – Step 1c – Missing content: WORKLOG, CLAUDE.md, checklists
- Prompt (verbatim):

  ```text
  You're right, my previous prompt was truncated. Here is the missing content in full.

  1. Create docs/WORKLOG.md with this template:

     ## <date> – Step N – <title>
     - Prompt (verbatim):
     - What Claude did:
     - What I checked and how:
     - What was wrong / what I caught:
     - Decision I made (and if I overruled Claude, why):

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
- What Claude did: Created docs/WORKLOG.md with entries for Steps 1, 1b and 1c using the template; created CLAUDE.md with the eight rules exactly as given; saved the 4a checklist to docs/brief_checklist.md and the 4b decision list to docs/open_decisions.md, word for word from the previous reply.
- What I checked and how:
- What was wrong / what I caught:
- Decision I made (and if I overruled Claude, why):

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
- What Claude did:
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
- What I checked and how:
- What was wrong / what I caught:
- Decision I made (and if I overruled Claude, why):

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
- What Claude did:
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
- What I checked and how:
- What was wrong / what I caught:
- Decision I made (and if I overruled Claude, why):

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
- What Claude did:
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
- What I checked and how:
- What was wrong / what I caught:
- Decision I made (and if I overruled Claude, why):

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
- What Claude did:
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
- What I checked and how:
- What was wrong / what I caught:
- Decision I made (and if I overruled Claude, why):
