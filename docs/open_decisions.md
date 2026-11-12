## 4b) Open decisions (options only, no recommendation)

**Model and service**
1. **Groq model(s)**
   - A small fast model: higher limits and lower latency, but weaker reasoning and citations.
   - A large model: better answers, but much lower limits, so you hit them sooner.
   - Mixed per step (small for routing and checking, large for drafting): best fit, but two sets of limits to track and calibrate.
2. **How you split the daily request budget** (calibration, then eval, then retrieval experiments, then real load runs)
   - Fixed shares up front: predictable, but rigid if one phase needs more.
   - Calibrate first, then plan: better informed, but risks burning budget early.
   - Deliberately exhaust it once to observe the per-day limit: you get a real Table 1 value and a real "budget exhausted" row, but lose the rest of that day.

**What "fast" means**

3. **Definition of TTFT for a multi-step pipeline**
   - First token of the final answer the user sees: honest, but includes all earlier steps.
   - First token of any model call: flattering and less meaningful.
   - First user-visible byte, including a progress message: measures what the user feels, but is easy to game.
4. **The "fast" target**
   - A TTFT target only: favours streaming.
   - A total-time target: favours fewer steps.
   - Both, plus a give-up deadline: most complete, but more numbers to defend.

**Pipeline shape**

5. **Check step versus streaming.** This is the likeliest "one decision that shaped it most".
   - Buffer the draft, check it, then send: safe, but TTFT becomes nearly the total time.
   - Stream the draft while checking in parallel, and retract if it fails: fast, but a wrong answer may already have been seen.
   - Check each sentence or citation as it streams: a middle ground, but more complex and more calls.
6. **Number of model calls**
   - One call per stage (understand, decide, draft, check): clear structure, but more requests per minute and more tokens.
   - Merge understand and decide into one call: fewer requests, but harder to branch on.
   - Deterministic routing with no model: cheapest, but brittle on question types it wasn't written for.
7. **The tool or tools**
   - Retrieval exposed as a model-called tool: natural fit, but adds a round trip.
   - A citation or quote verifier tool: directly serves the "no wrong answers" goal.
   - A section or page lookup tool: helps multi-hop questions, but adds steps.
8. **The branch or loop**
   - Refuse when retrieval confidence is low: cheap and serves the refusal requirement, but the threshold needs tuning.
   - Redraft when the check fails, with a bounded loop: better quality, but this is where "a few loop" costs you.
   - Retrieve again with a rewritten query: better recall, but more tokens and more latency.

**Library and retrieval**

9. **Paper source**
   - PDF text extraction: gives page numbers for citations, but extraction is messy (equations, two columns).
   - arXiv LaTeX source: clean sections, but harder to parse and has no page numbers.
   - arXiv HTML render: easy to parse with structure, but not available for every version and less canonical.
10. **Citation granularity**
    - Paper plus section: robust, but coarse.
    - Paper plus page: easy to verify, but tied to the PDF.
    - Paper plus section plus quoted span: the strongest evidence, but needs a span check.
11. **Chunking**
    - Fixed token windows with overlap: simple, but splits tables and equations.
    - Section- or paragraph-aware: semantically clean, but chunk sizes vary.
    - Several sizes compared as the Table 3 settings: answers the brief directly, but costs eval budget.
12. **Retrieval method**
    - BM25: no extra libraries, runs on CPU, easy to explain, but misses paraphrases.
    - Local embeddings: better semantic recall, but a heavy dependency on Windows.
    - Hybrid: best recall, but more to tune and defend.
13. **Re-ranking**
    - None: cheapest.
    - A local cross-encoder: better precision, but adds CPU latency.
    - An LLM re-rank: strong, but spends requests and tokens you're short of.
14. **Retrieval near the limit**
    - Fetch fewer chunks: tokens drop, but so does quality.
    - Skip re-ranking: lower latency, slightly worse precision.
    - Fall back to a passages-only reply with no model call: no spend, but no synthesized answer.

**Load and limits**

15. **Behaviour at the per-minute limit**
    - Queue with a deadline: delays everyone, and some give up.
    - Shed new arrivals immediately: fast refusals, but people are turned away.
    - Degrade (smaller model, skip the check): serves more people, but risks quality.
16. **Behaviour at the per-day limit**
    - A clear refusal with a retry time: honest, but nobody gets an answer.
    - Passages only with citations: some value without the model, but not an answer.
    - Reserve a slice of the budget for priority users: fairness questions.
17. **Retry policy**
    - Exponential backoff with jitter that honours `retry-after`: standard, but adds tail latency.
    - Bounded retries plus a per-request retry budget: caps amplification, but more failures.
    - Hedged requests for slow calls: better tail latency, but doubles spend on a free tier.
18. **Where retries live**
    - Per model call: fine-grained, but retries multiply across steps.
    - Per whole request: simple, but redoes work that already succeeded.
    - A global retry budget: prevents retry storms, but needs shared state.
19. **Load generator**
    - Open loop (Poisson or scheduled arrivals): realistic for bursts and exposes queueing.
    - Closed loop (N concurrent users): simpler, but hides overload.
    - Open loop with simulated users who give up: matches the brief's "people give up", but you have to pick a patience distribution.
20. **Patience and give-up model**
    - A fixed deadline: simple to report.
    - A distribution (e.g. lognormal): more realistic, but harder to defend without data.
    - Separate deadlines before and after the first token: captures "people wait longer once text appears".

**Stand-in**

21. **Stand-in interface**
    - An HTTP server compatible with Groq's API: the same client code path, so most faithful.
    - An in-process fake: easy, but skips network effects.
    - An HTTP server with its own simplified API: middle ground.
22. **Stand-in latency model**
    - Resample measured latencies directly: faithful to the data, but limited by sample size.
    - A fitted distribution (e.g. lognormal plus a slow tail): smooth, but adds an assumption.
    - Queueing-based slowdown (latency grows with concurrency): models "slower under load", but needs a calibration point you may not reach on the free tier.

**Evaluation and reporting**

23. **Grading the 15+ questions**
    - Manual grading: credible but slow.
    - An LLM judge: scales, but spends budget and needs validating.
    - A rubric of key facts plus a citation match: deterministic, but brittle on phrasing.
24. **Question mix**
    - The ratio of answerable, unanswerable, multi-paper and trap questions (for example, ones that confuse "chunking" across papers): drives what Wrong % and Correctly refused % mean.
25. **Cost per 1,000 answers on a free tier**
    - $0, stated literally: true but uninformative.
    - Groq's paid list price for the same model: meaningful, but hypothetical.
    - Tokens only, with the price as a formula: transparent, but leaves the arithmetic to the reader.
26. **How raw results flow into `results.csv`**
    - Every run appends to one file: simple, append-only.
    - Per-run files merged by a script: cleaner provenance, but you have to defend the merge step.
    - Both, with the merged file regenerated and never hand-edited.
