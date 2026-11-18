# The stand-in model service

Code: `standin/server.py`. Calibration extractor: `standin/calibrate_standin.py`, which writes `standin/calibration.json`. Load runner: `loadtest/run_load.py`.

The stand-in is an OpenAI/Groq-compatible HTTP server: `POST /openai/v1/chat/completions` with streaming SSE. The pipeline reaches it with the same `GroqClient` class as the real service, pointed at another URL with `source="stand-in"`. Each load scenario starts its own stand-in on its own port (8801–8805), with fresh limit state and a separate client instance. Nothing is shared with a real client.

## Parameters and where they come from

| Parameter | Value | Source (raw records) |
|---|---|---|
| Time to response headers, time to first visible token, reasoning tokens, generation speed, server queue time | resampled from whole measured requests (one sample = one real request or pipeline call) | **Calibration v2** (`standin/calibrate_standin.py --traces results/raw/traces_eval_medium_20261117T102821Z.jsonl`): every HTTP 200 in `calibration_20261112T141038Z.jsonl` and `retry_20261112T145223Z.jsonl`, plus every accepted route/draft call of the real medium eval of 2026-11-17 (final attempt; rate-gate waits and 429 retries removed). Trace samples have no time-to-headers, so they use first token × the median headers/first-token ratio of the calibration samples. Pools: 120b small 39, large 34; 20b small 32, large 5. Prompt < 600 tokens uses the small pool. |
| Generation speed | completion_tokens / server completion_time of the sampled request | same records (median about 475 tok/s on 120b, 890 on 20b) |
| Time a 429 takes | median of real 429s (197 ms on 120b), ×0.7–1.3 | same files, the 429 records |
| RPM | 30 per model: burst 30, refill 0.5/s, so after the burst one request per 2.0 s since the last accepted one; a rejection consumes nothing | retry run rty-031..051 (passes ≥ 2.009 s, failures ≤ 1.996 s after the last 200); bursts stopped at exactly 30 (rty-001..030, rty-052..081); limits per model: cal-052 |
| TPM | 8,000 per model, charged prompt + max_tokens at admission, steady refill 133.3/s | cal-056/057 (reset-tokens = deficit × 60 / 8000; "type": "tokens") |
| RPD | 1,000 per model (configurable); +1 per whole 86.4 s since the last credit, fraction dropped | daily rule check cal-062 → rty-001 (whole-period model matched 114/116 accepted 120b records) |
| 429 response | same headers (`x-ratelimit-limit/remaining/reset-requests` = daily, `…-tokens` = per minute, `retry-after` rounded up to whole seconds) and body `{"error": {"message", "type": "requests" or "tokens", "code": "rate_limit_exceeded"}}` | 429 bodies in both files (1 + 15 "requests", 2 "tokens") |
| Slower under load | every delay × (1 + 0.10 × (requests in flight − 1)) | **not measured.** The real runs never had more than 5 requests in flight (b4), and those returned no visible tokens. 0.10 is an assumption. |
| Failures | 1% of accepted requests return HTTP 503 after 0.2 s (load test setting) | **not measured.** There were 0 server errors in the 145 real requests (127 × 200, 18 × 429); the rate is an assumption so the 5xx path is exercised. |
| Slow-success tail | 3% of replies are 5× slower (load test setting) | **not measured as such.** The real tail exists (cal-012: 2.19 s to first token against a 0.6 s median), but resampling already reproduces the measured tail; this adds a heavier one. |
| Reply content | router (20b): `{"keywords": [], "papers": [], "in_scope": true}`. Draft (120b): one sentence copied from passage [1] + " [1]". | designed to pass the pipeline's check, so load runs measure timing and limits, not answer quality |

## Validation against the real service

The same 26 questions and retrieval setting, run against the real service and against the stand-in (`run_eval.py --standin`), compared by `scripts/compare_standin.py`. Model-call measures use the final, accepted attempt. D is the Kolmogorov-Smirnov distance.

| Calibration | Held out? | Router first token, median (real / stand-in) | Router D | Draft first token, median (real / stand-in) | Draft D |
|---|---|---|---|---|---|
| v1 (2026-11-12 data only), medium | yes | 421 / 778 ms (1.85×) | 0.85 | 584 / 949 ms (1.63×, first attempts only) | 0.83 |
| v1, small | yes | 432 / 785 ms (1.82×) | 0.85 | not measured | — |
| **v2 (+ real medium eval), small** | **yes (calibrated on medium, tested on small)** | **432 / 512 ms (1.18×)** | **0.42** | **530 / 576 ms (1.09×)** | **0.37** |

- Runs: real `run_eval_small_20261117T103158Z` and `run_eval_medium_20261117T102821Z`. Stand-in, v1: `run_eval_standin_medium_20261117T104108Z` and `run_eval_standin_small_20261117T104539Z`. Stand-in, v2: `run_eval_standin_small_20261117T105108Z`.
- v1 made every load-test latency 1.6–1.9× too pessimistic. The load campaign was re-run on v2; the v1 campaign is listed in `results/excluded_runs.csv`.
- **Remaining gaps:** the stand-in's p90 is heavier (router 1,425 vs 822 ms). The stand-in never needs a redraft, so its end-to-end p90 is lower than real (12.7 s vs 20.1 s).

## Where it is least like the real service

1. **Behaviour under concurrency.** The slowdown law is invented, because the free tier could not be pushed past 5 requests in flight inside its limits. If the real service queues internally (as its queue_time suggests: 28.6% of the time on 120b, 60.7% on 20b), its slowdown may be far steeper or far flatter than 10% per request.
2. **Two days, few samples.** The pools mix 2026-11-12 (slower: 20b spent 60.7% of its time queued) and 2026-11-17. The real service's latency changed about 1.7× between those days, so any single calibration is a snapshot. The stand-in's p90 is heavier than the real 2026-11-17 p90 (validation below).
3. **The answers.** The stand-in copies a sentence instead of reasoning. Its output length (reasoning tokens from the sample + one sentence) is shorter than real drafts (118–300 tokens). So it generates for less time, holds TPM for the same reservation, and almost never triggers a redraft.
4. **Hidden limits.** It enforces only the measured RPM/TPM/RPD rules. The real service may have others (tokens per day, concurrency caps, per-organization queues) that the free tier never showed.
5. **Clock and network.** It runs on localhost, so there is no internet round trip (the real time to headers includes about 100–300 ms of network); real clocks were skewed 2.2–3.2 s.
