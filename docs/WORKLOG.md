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
- What I checked and how: I re-read the message I had actually sent and confirmed Claude was right: it ended after item 1. I compared Claude's 4a checklist with the brief, page by page. It included the two extra headings after heading 5, the Vaani section, "How I worked with the assistant", all four tables with their columns, the minimum rows of Table 2a, the results.csv columns, and the formatting rules (milliseconds, one decimal, "not measured").
- What was wrong / what I caught: My follow-up wrongly assumed the assistant had skipped items 2–4; they were never in the prompt it received because my paste was truncated.
- Decision I made (and if I overruled Claude, why): Accepted Claude's more accurate wording for the Step 1 "What was wrong" field instead of my own, because mine blamed the assistant for something that was my mistake. Also noted as good behaviour: it refused to invent rules "exactly as I wrote them" when it had never seen them. Re-sent the full content as one complete block (Step 1c).

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
- What I checked and how: Opened CLAUDE.md and compared it with my eight rules. Read the Step 1 entry in WORKLOG.md and confirmed my prompt was copied verbatim. Read the Step 1b "What was wrong" text Claude wrote for me (it had no text from me for that field) and kept it because it is accurate.
- What was wrong / what I caught: My own rule was wrong: I wrote "I am on Windows (PowerShell)" but my terminal is cmd. I found out in Step 3 when `Copy-Item` failed in cmd. Corrected in CLAUDE.md in Step 3b.
- Decision I made (and if I overruled Claude, why): Keep the brief checklist and the 26 open decisions as files in docs/, so every later decision can be traced back to its number in open_decisions.md.

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
- What I checked and how: I opened data/papers/MANIFEST.md and checked that the three files are 1706.03762v7, 2410.00037v1 and 2507.07955v2. I read the 10 extraction problems and recognised three of them as material for the "naive retriever" section (references labelled as Conclusion, flattened superscripts such as 10^20 → 1020, repeated section names). I noted that Claude read Groq's docs through a summarising fetch tool and that the page does not say which plan the table belongs to, so every limit had to be verified by real calls, not trusted. I have a free Groq account, so the "Free Plan" values are the ones that apply to me.
- What was wrong / what I caught: The calibration plan used about 25% of the documented daily tokens (~49K of 200K) while staying under 10% of requests. Tokens, not requests, are my scarce resource (about 35 full answers per model per day at 200K tokens), so the plan was optimising the wrong limit.
- Decision I made (and if I overruled Claude, why): Accepted file names with the version (<id>vN.jsonl) instead of my <id>.jsonl, so the version travels with the data. Rejected the 25%-token plan: merged the latency baseline and the TTFT measurement into one set of streamed requests, kept reasoning_effort low by default, and decided to calibrate both gpt-oss-120b and gpt-oss-20b, because if limits are per model, two models double the daily budget. Final model choice left open until I have quality measurements.

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
- What I checked and how: Read the dry-run table and saw the upper bound (41,149) was over my 35K cap. Checked the b3 argument myself: after b2 recovers, 120b is no longer limited, so a 200 from 20b would prove nothing. Claude was right. Created .env myself in cmd (`copy .env.example .env`, then `notepad .env`), checked with `dir /a` that it is .env and not .env.txt, and with `git status` that it is not tracked. Created a dedicated key for this project in the Groq console instead of reusing my other project's key, since limits are per organisation anyway and a separate key can be revoked after submission.
- What was wrong / what I caught: My own b3 design was wrong (sending to 20b after recovery cannot distinguish per-model from shared limits); Claude Code caught it, and I accepted the correction. My 4 s spacing for part a would have hit the 8K tokens-per-minute limit in the middle of the baseline; also caught by Claude Code. And my CLAUDE.md said PowerShell: `Copy-Item` failed because I use cmd.
- Decision I made (and if I overruled Claude, why): Decided in Step 3b (see there).

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
- What I checked and how: Read the new dry run: 77 requests (under 110) but 42,662 tokens, over the 42K cap. Re-ran the dry run myself in cmd after raising the cap and checked it printed "Caps: 110 requests, 43000 tokens" and "WITHIN the caps". Then ran `--go` myself (not Claude): 62 requests sent, 36,397 tokens used, completed without a hard stop. Saved the console output next to the raw file.
- What was wrong / what I caught: The random markers and the larger 128-token allowance pushed the upper bound 662 tokens over my 42K cap. Claude reported it rather than silently going over.
- Decision I made (and if I overruled Claude, why): Raised the cap to 43K rather than cutting part c, because the cap is checked before each request and the run would have dropped part-c requests, and part c has only 4 (losing one would cost a quarter of the reasoning-effort comparison). The markers go at the START of every prompt, because prompt caching works on the beginning of the prompt. I ran the real calls myself so the measurements are mine.

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
- What I checked and how: Before reading Claude's summary, I read the console output myself: 30 successes in b1 then a 429 on cal-051; rem_req was 962 both before and after the 429 (so a rejected request does not use daily budget); 20b answered 200 with its own counter (989) while 120b was blocked; in b4, 3 of 5 ~2K-token requests passed. Then I recomputed one claim by hand on a real record: on the 429 (cal-051), x-ratelimit-remaining-requests = 962, so 1000 − 962 = 38 used, and 38 × 86.4 s = 3,283.2 s = 54 min 43.2 s, which matches the header x-ratelimit-reset-requests: 54m43.2s exactly. This confirms the daily limit refills at 1 request per 86.4 s (1000 per day). I renamed the console file to remove the double extension (contents unchanged). : I took screenshots of the Groq console Usage page (Cost/Activity) into docs/evidence/.
- What was wrong / what I caught: My hypothesis (f) said the daily counter "refills gradually"; the data showed it refills only in whole 86.4 s periods between requests, so under continuous load it never refills. My plan also gave tiny requests a 16-token output budget, which reasoning used up entirely: 20 of 59 successful requests produced no visible text.
- Decision I made (and if I overruled Claude, why): Treat "the daily quota never refills under continuous load" as a hypothesis until tested, because it rests on one run. Design around reserved tokens (prompt + max output), not used tokens, since Groq charges the full output allowance up front against the per-minute limit: every pipeline step gets a tight max_tokens, and reasoning_effort stays low. Test whether fast retries prevent recovery (Step 3d) before using it in the Retries section.

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
- What Claude did:
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
- Decision I made (and if I overruled Claude, why): Run the experiment on 120b only, with tiny requests, to keep the cost low (8,784 tokens charged). Keep raw files untouched and submit a redacted copy (org ID) produced by a script, so reviewers can see exactly what was changed and why.

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
- What Claude did:
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
- Decision I made (and if I overruled Claude, why): Retry policy: wait at least retry-after measured from the last accepted request, jitter only added on top. Evidence: retrying every 1 s got 7 of 20 through (65.0% wasted, 0.35/s) vs 9–10 with 2 s spacing; a 5 ms shortfall (1.995 s instead of 2.0 s) turned a retry into a rejection. Open issues noted for later: with several requests in flight, "last accepted" is known late (0.2–0.8 s after sending), and token-limit 429s behave differently (steady refill, retry-after rounded up from 90 ms to 1 s).
- Note: I renamed results/raw/calibration_20261112T141038Z_console.txt.txt to remove a double extension added by Notepad. Contents unchanged.

## 2026-11-12 – Step Q – Evaluation questions
- Prompt (verbatim): Not a Claude Code step. Drafted with Claude (claude.ai) from the three PDFs I uploaded; the draft is in that conversation's history. I edited it in place into eval/questions.yaml (only change: verified: true on each question).
- What I did: Verified every question in the PDFs and set verified: true on each. Final set in eval/questions.yaml.  kept 26 of 26.
- What I checked and how: For each question, Ctrl+F in the PDF on a key fact (e.g. "4000", "0.03", "65%") and checked the page number printed at the bottom of the page. For the 4 refusal questions, searched each PDF for the key terms ("Japanese", "3-stage", "French", "SoundStorm") to confirm the papers do not answer them.
- What I found: While drafting, Claude (claude.ai) noticed that two papers contradict themselves. I verified both in the PDFs: Attention gives EN-FR BLEU as 41.8 (abstract, Table 2) but 41.0 (section 6.1, page 8); Dynamic Chunking gives DNA data efficiency as "nearly 4×" (abstract) but 3.6× (pages 4 and 17). Kept as q13/q14: a naive retriever cites whichever chunk it finds first, with full confidence, which gives a fourth failure mode for the naive-retriever section.
- What was wrong / what I caught: Nothing wrong found during verification: all 26 answers and page numbers matched the PDFs.
- Decision I made (and if I overruled Claude, why): Kept all 26 drafted questions unchanged, because every one verified and the set already covers the failure types I want to measure (single facts, exponents in tables, explanations, cross-paper, terminology traps, refusals including a references trap). The question set is assistant-drafted; my contribution here is verification.
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
- What Claude did:
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
- Decision I made (and if I overruled Claude, why):

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
- What Claude did:
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
- Decision I made (and if I overruled Claude, why):
