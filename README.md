# The Relay

A multi-step question-answering pipeline that answers only from three arXiv papers, always with citations,
and refuses when the papers don't say. It is measured against Groq's free tier (real limits, real latency) and a
stand-in model service calibrated from those measurements, under five load shapes.

- Report: `docs/report.md`; tables: `docs/tables.md`; stand-in and its validation: `docs/standin.md`
- Decisions and their evidence: `docs/DECISIONS.md`; step-by-step log: `docs/WORKLOG.md`
- Origin: started from the brief in `docs/The_Relay_Assignment_Brief.pdf`; now a personal project.

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

## Run it (Windows cmd, from the repo root)

Papers and retrieval (no model calls):

```bat
.venv\Scripts\python.exe scripts\fetch_papers.py
.venv\Scripts\python.exe scripts\extract_papers.py
.venv\Scripts\python.exe scripts\clean_papers.py
.venv\Scripts\python.exe scripts\eval_retrieval.py
```

Tests (FakeClient only, no network):

```bat
.venv\Scripts\python.exe -m unittest -v tests.test_pipeline
```

Real evaluation on Groq (dry run by default; `--go` makes real calls and spends the shared daily budget):

```bat
.venv\Scripts\python.exe scripts\run_eval.py --setting medium
.venv\Scripts\python.exe scripts\run_eval.py --setting medium --go
.venv\Scripts\python.exe scripts\pregrade.py results\raw\run_eval_medium_<UTC>.csv
rem review eval\grades_run_eval_medium_<UTC>.csv, fill final_grade where you disagree, then:
.venv\Scripts\python.exe scripts\apply_grades.py eval\grades_run_eval_medium_<UTC>.csv
rem repeat for --setting small and --setting large
```

Stand-in validation (the same questions against the stand-in, then compared with the real runs):

```bat
.venv\Scripts\python.exe scripts\run_eval.py --setting medium --standin
.venv\Scripts\python.exe scripts\compare_standin.py
```

Load tests against the stand-in (never touch Groq):

```bat
.venv\Scripts\python.exe standin\calibrate_standin.py
.venv\Scripts\python.exe loadtest\run_load.py --all --seeds 1,2,3
```

Results and tables:

```bat
.venv\Scripts\python.exe scripts\build_results.py
.venv\Scripts\python.exe scripts\make_tables.py
.venv\Scripts\python.exe scripts\make_submission_copy.py
```

`results/results.csv` is rebuilt from the raw run files and never edited by hand. Raw files are append-only. Runs left out of the tables are listed with reasons in `results/excluded_runs.csv`. Decisions and their evidence are in `docs/DECISIONS.md`; every step is in `docs/WORKLOG.md`.
