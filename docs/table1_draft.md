# Table 1 draft: limits found in the real service

Source: `results/raw/calibration_20261112T141038Z.jsonl` (62 requests, 2026-11-12, free tier), summarized by `scripts/summarize_calibration.py`. Record ids are `cal-NNN`. Limits apply per model; values below are for `openai/gpt-oss-120b` unless stated, and `openai/gpt-oss-20b` showed the same header limits.

| Limit | Value you found | How you found it | Confidence (high, medium, low) |
|---|---|---|---|
| Requests per minute | 30 per model | Burst of tiny requests 0.43 s apart: 30 × 200 (cal-021..cal-050, started within 12.582 s), then 429 on cal-051, 13.031 s after the first. 429 message: "requests per minute (RPM): Limit 30, Used 30, Requested 1". No header reports RPM. | high |
| Tokens per minute | 8,000 per model | `x-ratelimit-limit-tokens: 8000` on all 61 records that carry the token headers (both models). 5 concurrent ~2K-token requests: 3 × 200 (cal-054, cal-055, cal-058), 2 × 429 (cal-056, cal-057) with "tokens per minute (TPM): Limit 8000, Used 5989/5990, Requested 2023/2022". | high |
| Requests per day | 1,000 per model | `x-ratelimit-limit-requests: 1000` on all 62 records. `reset-requests` = (1000 − remaining) × 86.4 s on every record (86.4 s = 86,400 s / 1,000). Never reached: lowest remaining seen was 954 (cal-062). | medium (header and arithmetic only; limit not reached) |
| Tokens per day | not measured | No header reports it, and the run used 36,397 tokens in total, far below the docs' 200K/model/day. Docs value unverified. | not measured |
| Requests in flight at once | not measured | No concurrency limit was observed. The maximum overlap was 5 requests in flight on 120b (b4), and the 2 rejected there were refused by the TPM limit, not by concurrency. | not measured |
| What it returns when a limit is hit | HTTP 429 with `retry-after` (whole seconds) and a JSON body `{"error":{"message":…,"type":"requests" or "tokens","code":"rate_limit_exceeded"}}` | Captured on cal-051 (RPM) and cal-056/057 (TPM). An RPM 429 carries only the request headers (`limit/remaining/reset-requests`). A TPM 429 also carries `limit/remaining/reset-tokens`. A 429 does not decrease `remaining-requests` (cal-050 962, then cal-051 962, then cal-053 961; b4 went 961 → 958 for 3 successes + 2 × 429). Any other status would have stopped the run; none occurred. | high |
| Time until it recovers | RPM: one request is admitted once ≥ 2.0 s have passed since the last *accepted* request; rejected requests do not reset that clock (retry-after said 2 s). TPM: continuous refill at 8,000/60 ≈ 133.3 tokens/s. RPD: one request per 86.4 s, credited only for whole 86.4 s gaps. | RPM (`results/raw/retry_20261112T145223Z.jsonl`, gaps from recorded start times): after the 429 (rty-031), 20 retries 1.0 s apart gave 7 × 200 and 13 × 429. Every pass had ≥ 2.0 s since the last 200 (smallest 2.009 s, rty-044). Every failure had < 2.0 s (largest 1.996 s, rty-035). No exceptions. All 7 passes came only ~1.0 s after a rejected request. Polite retry after `retry-after` + jitter: rty-083 got 200 2.247 s after the 429 (rty-082) ended. Both bursts again stopped at exactly 30 accepted (rty-001..030, rty-052..081, starts spanning 12.7 s), so there is no refill while requests keep arriving < 2 s apart. Calibration agrees (cal-051 → cal-053: 200 after 5.0 s). TPM: `reset-tokens` = (8000 − remaining) × 60 / 8000 exactly (cal-056: 44.917 s; cal-057: 44.925 s), and the message said "try again in 90ms" for a 12-token shortfall. RPD: whole-period model matches 46/48 120b and 11/11 20b records; continuous refill matches 7/48. | RPM high (20 retries + 1 polite, threshold between 1.996 s and 2.009 s); TPM high; RPD medium-high (whole-period rule matches 114/116 accepted 120b records across both runs; the 2 misses are an ordering swap within concurrent b4) |

## Notes

- **Max output is reserved up front against TPM.** Each request is charged prompt + `max_completion_tokens` at admission, not the tokens it actually produces:
  - cal-001: 8000 − 7690 = 310 = 182 prompt + 128 max output (actual use: 206).
  - cal-021: 109 = 93 + 16.
  - The 429s' "Requested 2022/2023" equals prompt + 16.

  Whether unused output tokens are refunded later is not established.
- **`retry-after` is rounded up to whole seconds.** cal-056/057 said `retry-after: 1` while the message said "Please try again in 90ms". cal-051 (RPM) said 2, matching its message "2s".
- **Daily refill rule: 86.4 s per request, whole periods only.** `reset-requests` always equals (1000 − remaining) × 86.4 s. The remaining count goes up only by floor(gap / 86.4 s) between consecutive requests, and fractions appear to be dropped:
  - cal-010 → cal-021: gap 197.6 s, +2.
  - Part a's 15 s gaps produced no refill at all (cal-007 shows 993, where continuous refill predicts 994).

  Consequence: under continuous load the daily budget does not refill.
- **Limits are per model.** cal-052 (20b) returned 200 while 120b was blocked by its RPM 429 (cal-051, 0.001 s earlier). 20b reported its own remaining-requests (989, continuing from cal-020's 990) and remaining-tokens (7,893). Per-day token limits per model were not tested.
- **Clock skew.** The local clock was 2.2–3.2 s ahead of Groq's `Date` header (cal-051, cal-056, cal-057; `Date` has 1 s resolution). `start_time` values are local-clock timestamps; durations are unaffected.
- **How the RPM refill works (retry_20261112T145223Z).**
  - Burst capacity is 30.
  - After that, one request per 2.0 s, measured from the last accepted request. Rejections don't reset the clock, and partial intervals don't accumulate while requests keep arriving faster.
  - **Retrying faster than 2 s wastes requests and loses throughput.** 1 s retries: 7 of 20 accepted (0.350/s), 65.0% wasted. A client spaced at 2.0 s from the 429 would have had 9 accepted, 0 wasted, in the same 19.997 s.
  - The second 1 s retry after each success landed at 1.990–1.996 s, just under the threshold, so only every 3rd retry passed.
- **The daily refill rule holds across both runs.**
  - cal-062 (954, 14:18:43.189) → rty-001 (14:52:24.294): 2,021.1 s = 23.39 periods. Predicted 954 + 23 − 1 = 976; observed 976.
  - `reset-requests` on rty-001 = 34m33.6s = 24 × 86.4 s.
