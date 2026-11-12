"""Estimate (NO API calls) the real end-to-end evaluation: every question in eval/questions.yaml
x the 3 retrieval settings, through relay.pipeline.

Builds the exact router and draft prompts the pipeline would send (BM25 on the question alone:
router keywords are unknown before running) and counts them with the gpt-oss tokenizer
(o200k_harmony) + 60 template tokens per request, the overhead used in scripts/calibrate.py
(calibration part a: estimate within 0.1-1% of Groq's prompt_tokens).

Groq reserves prompt + max_tokens per request against the per-minute token limit (calibration),
so "reserved" = prompt + max_tokens. Daily limits from docs/table1_draft.md: 1,000 requests per
model per day (measured), 200K tokens per model per day (docs value, not verified).

Usage (cmd):
    .venv\\Scripts\\python.exe scripts\\estimate_eval.py
    .venv\\Scripts\\python.exe scripts\\estimate_eval.py --draft-max-tokens 500
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from relay.chunking import count_tokens  # noqa: E402
from relay.pipeline import (RETRIEVAL_SETTINGS, BM25Tool, PipelineConfig, draft_messages,  # noqa: E402
                            redraft_messages, router_messages)

TEMPLATE_OVERHEAD = 60
TPM, RPM, RPD, TPD = 8000, 30, 1000, 200_000
REFILL_PER_S = TPM / 60
FEEDBACK_TOKENS = 120   # check errors in the redraft message (estimate)


def prompt_tokens(messages: list[dict]) -> int:
    return sum(count_tokens(m["content"]) for m in messages) + TEMPLATE_OVERHEAD


def minutes_at_tpm(reserved: int, requests: int) -> float:
    """Seconds to push `reserved` tokens through an 8K bucket that starts full and refills
    continuously; also never faster than RPM (burst 30, then 1 per 2 s). Returned in minutes."""
    by_tokens = max(0.0, reserved - TPM) / REFILL_PER_S
    by_requests = max(0, requests - RPM) * 2.0
    return max(by_tokens, by_requests) / 60


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft-max-tokens", type=int, default=PipelineConfig().draft_max_tokens)
    ap.add_argument("--router-max-tokens", type=int, default=PipelineConfig().router_max_tokens)
    ap.add_argument("--setting", choices=[*RETRIEVAL_SETTINGS, "all"], default="all",
                    help="one retrieval setting (26 runs) or all three (78 runs)")
    args = ap.parse_args()
    questions = yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))
    cfg = PipelineConfig(draft_max_tokens=args.draft_max_tokens, router_max_tokens=args.router_max_tokens)

    router_in = [prompt_tokens(router_messages(q["question"])) for q in questions]
    per_setting = {}
    chosen = list(RETRIEVAL_SETTINGS) if args.setting == "all" else [args.setting]
    for s in chosen:
        tool = BM25Tool(s)
        d_in, rd_in = [], []
        for q in questions:
            hits = tool.search(q["question"])
            d_in.append(prompt_tokens(draft_messages(q["question"], hits)))
            # worst case redraft: same prompt + a full-length previous draft + the check's feedback
            rd_in.append(prompt_tokens(redraft_messages(q["question"], hits, "", [])) + cfg.draft_max_tokens
                         + FEEDBACK_TOKENS)
        per_setting[s] = (d_in, rd_in)

    n_q, n_s = len(questions), len(chosen)
    runs = n_q * n_s
    print(f"{n_q} questions x {n_s} setting(s) {chosen} = {runs} pipeline runs. router max_tokens={cfg.router_max_tokens}, "
          f"draft max_tokens={cfg.draft_max_tokens}\n")
    print(f"{'setting':<8}{'draft prompt mean':>18}{'min':>6}{'max':>6}{'reserved/draft':>16}")
    for s, (d_in, _) in per_setting.items():
        print(f"{s:<8}{statistics.mean(d_in):>18.0f}{min(d_in):>6}{max(d_in):>6}"
              f"{statistics.mean(d_in) + cfg.draft_max_tokens:>16.0f}")
    print(f"router prompt mean {statistics.mean(router_in):.0f} (min {min(router_in)}, max {max(router_in)}), "
          f"reserved/route {statistics.mean(router_in) + cfg.router_max_tokens:.0f}\n")

    r20_req = runs
    r20_res = n_s * sum(router_in) + runs * cfg.router_max_tokens
    d_req = runs
    d_res = sum(sum(d) for d, _ in per_setting.values()) + runs * cfg.draft_max_tokens
    rd_res = sum(sum(r) for _, r in per_setting.values()) + runs * cfg.draft_max_tokens

    rows = [
        ("gpt-oss-20b  (route)", r20_req, r20_req, r20_res, r20_res),
        ("gpt-oss-120b (draft)", d_req, d_req + runs, d_res, d_res + rd_res),
    ]
    print(f"{'model':<22}{'requests':>16}{'reserved tokens':>22}{'minutes at 8K TPM':>20}"
          f"{'% of 1K RPD':>13}{'% of 200K TPD':>16}")
    for name, req_lo, req_hi, tok_lo, tok_hi in rows:
        print(f"{name:<22}{req_lo:>7} - {req_hi:<6}{tok_lo:>10,} - {tok_hi:<9,}"
              f"{minutes_at_tpm(tok_lo, req_lo):>8.1f} - {minutes_at_tpm(tok_hi, req_hi):<9.1f}"
              f"{req_lo / RPD * 100:>5.1f} - {req_hi / RPD * 100:<5.1f}"
              f"{tok_lo / TPD * 100:>6.0f} - {tok_hi / TPD * 100:<6.0f}")
    print("\nLow end: no redrafts. High end: every run redrafts (upper bound). Reserved = prompt + max_tokens;")
    print("TPD may count tokens actually used (smaller: outputs were 118-300 of 300 in calibration), not reserved.")
    print("Retrieval uses the question as is (router keywords are logged, not used).")
    print("Models have separate limits (cal-052), so the 20b and 120b streams run side by side;")
    print("the wall-clock time is the slower (120b) stream.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
