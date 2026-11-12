# CLAUDE.md

Hard rules for this project:

- Never print, log or commit the Groq key; read it only from .env.
- The Groq free-tier daily budget is shared by everything I run. Never make a real Groq call without first telling me how many requests and roughly how many tokens it will use, and waiting for my OK.
- results.csv must have exactly these columns, in this order: request_id, scenario, source, start_time, first_token_ms, total_ms, status, retries, tokens_in, tokens_out, retrieval_setting, answer_grade. Every number in the write-up must be recomputable from it.
- Answers come only from the 3 papers at the exact arXiv versions in the brief, always cited; if the papers don't say, refuse instead of guessing.
- Raw results are append-only; never overwrite or "clean" them.
- When I give numbered items, end every reply with each item number marked done / not done.
- If a prompt from me looks truncated or contradicts an earlier rule, stop and ask before acting.
- I am on Windows, using cmd (Command Prompt), not PowerShell. Give me cmd commands and paths that work there.
