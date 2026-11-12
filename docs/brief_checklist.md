## 4a) Hard requirements from the brief

**What to build**
- Language: Python, C++ or Go.
- At least 4 steps, at least 1 tool call, and at least 1 branch or loop.
- One step must retrieve passages from the library.
- The library is exactly three papers, which you fetch yourself:
  - 1706.03762 **v7** (Attention Is All You Need)
  - 2410.00037 **v1** (Moshi)
  - 2507.07955 **v2** (Dynamic Chunking)
- Every answer cites where in the papers it came from. If the papers don't say, the assistant says so instead of guessing.
- Model calls go to a real hosted model on Groq's free tier, with your own account and key. You find its limits from the docs and from what it returns when you hit one.
- A stand-in model service you control. It must be able to:
  - be slow
  - fail
  - refuse because a limit was reached
  - get slower under load
  - stream its reply a piece at a time
- The stand-in is calibrated from real measurements, and the write-up says where it is least like the real service.

**What to run**
- A modest number of real requests to learn the real service: latency spread, limits, and what it does at a limit.
- At least 3 load shapes of your own design. Use the stand-in for loads the real service can't take.
- Keep the raw results for both real and stand-in runs.
- Answer quality on at least 15 questions you wrote yourself, plus tokens used per answer.
- At least 3 retrieval settings.

**Headings, in this exact order**
1. **What I built and why**: the design, and the one decision that shaped it most.
2. **The real service and my stand-in**: the limits you found and how; how the stand-in behaves; how you calibrated it; where it differs most.
3. **Results**:
   - TTFT and total time, at p50 and at the slow end (say which percentiles and how many requests)
   - failures and given-up requests, per load shape
   - which runs were real and which used the stand-in
   - every number in the tables, including one number nobody could have guessed without running it
   - answer quality on at least 15 questions, and tokens per answer
4. **Where the time goes**: for one slow request, split its latency into waiting, working and retrying; say whether the delay came before or after the first token; show how you know.
5. **When a limit is hit**: what happens at the per-minute limit and at the per-day limit; who is delayed, who is dropped, who gets a weaker answer, and why.
   - **Retrieval: quality versus cost**: at least 3 settings (piece size, pieces fetched, re-rank or not); quality, tokens per answer and TTFT for each; pick one and say why; say what retrieval does when the limit is close.
   - **How this library will mislead a naive retriever**: three ways, each with an example question.
6. **Retries**: your policy, and one case where retrying made things worse.
7. **What the person sees**: the reply a waiting person gets at 3pm when the daily budget is gone.
8. **What I'm unsure about, what I left out, what I learned**:
   - your least certain assumption, and what breaks if it's wrong
   - two things you deliberately didn't build
   - one thing that was new to you, explained in your own words

- **Your feedback on Vaani**: visit vaani.dev; what stood out, what confused you, one thing you'd change. The brief doesn't say where this goes, only that it comes before the last section. After 8 is the natural spot.
- **How I worked with the assistant** (last section):
  - the real, uncleaned conversation history (or the prompts, if the tool can't export)
  - half a page on: the 3 prompts that mattered most and why, one thing it got wrong that you caught and how, and one decision where you overruled it
  - what in the submission is distinctly yours

**Table 1: Limits you found in the real service**
- Columns: Limit | Value you found | How you found it | Confidence (high, medium, low)
- Rows:
  - Requests per minute
  - Tokens per minute
  - Requests per day
  - Tokens per day
  - Requests in flight at once
  - What it returns when a limit is hit
  - Time until it recovers

**Table 2a: Latency**
- Columns: Scenario | Real or stand-in | Requests sent | Duration (s) | Offered rate (per min) | First token p50 / p95 / p99 (ms) | Total time p50 / p95 / p99 (ms)
- Minimum rows: **steady, burst, sustained overload, per-minute limit halved, daily budget exhausted**. The template draws 6 rows, so there's room for one more.

**Table 2b: Outcomes** (same rows as 2a)
- Columns: Scenario | Succeeded % | Rate-limited % | Timed out or given up % | Retries per request | Peak queue length | Tokens per answer | Cost per 1,000 answers

**Table 3: Retrieval settings** (at least 3 rows)
- Columns: Setting (piece size, pieces fetched, re-rank yes or no) | Questions asked | Correct and cited % | Wrong % | Correctly refused % | Tokens per answer | First token p50 / p95 (ms) | Total time p50 / p95 (ms)

**`results.csv`**
- One file, one row per request.
- Columns in this order: `request_id, scenario, source, start_time, first_token_ms, total_ms, status, retries, tokens_in, tokens_out, retrieval_setting, answer_grade`
- Allowed values:
  - `source`: `real` or `stand-in`
  - `status`: `ok`, `rate_limited`, `timeout`, `error`
  - `answer_grade`: `correct`, `wrong`, `refused_correctly`, `refused_wrongly`
- Every figure in the tables must be computable from this file. Reviewers recompute them, so they must match.

**Formatting rules**
- Time in milliseconds.
- Percentages to one decimal place.
- Fill every cell; write "not measured" where you didn't measure something.
- Copy the tables into the write-up.

**Ground rules**
- Submit within 4 days of receiving the brief.
- At most 2 pages of writing, plus code, raw results and the conversation history.
- Use your own free account, and leave the key out of the submission.
- One daily limit covers everything you run; running out is part of the problem.
- Stay within Groq's terms: no extra accounts and no tricks around the limits.
- Using an AI assistant is welcome. They judge how you frame the problem, check its output and overrule it, plus choices and measurements that are clearly yours.
- A live session follows where you explain your results and change your system, so only submit what you can defend.
- Pick a few techniques that matter for your measurements and go deep.

**Tension to plan for:** 12 headings and 4 tables in 2 pages. The tables alone will take most of a page.
