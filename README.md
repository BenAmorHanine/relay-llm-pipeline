# The Relay

Take-home assignment: a multi-step, cited Q&A pipeline over three arXiv papers,
measured against Groq's free tier and a controllable stand-in model service.
See `docs/The_Relay_Assignment_Brief.pdf`.

## Layout

| Path            | Purpose                                                    |
|-----------------|------------------------------------------------------------|
| `src/relay/`    | The pipeline                                               |
| `standin/`      | Stand-in (fake) model service                              |
| `loadtest/`     | Load shapes                                                |
| `eval/`         | Evaluation questions and grading                           |
| `data/papers/`  | The three arXiv papers at the pinned versions              |
| `results/raw/`  | Raw measurements, written by code only, never hand-edited  |
| `docs/`         | Brief, write-up, worklog, exported assistant conversations |

## Setup (Windows cmd, Python 3.11+)

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
rem then put your Groq key in .env
```
