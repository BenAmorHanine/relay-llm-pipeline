"""Append-only writers: one results row per request, and per-step trace lines.

Columns are fixed by CLAUDE.md, in this order; the allowed values follow the brief:
    status        ok | rate_limited | timeout | error
    source        real | stand-in
    answer_grade  correct | wrong | refused_correctly | refused_wrongly | empty (not graded yet)

Each run appends to its own raw file results/raw/run_<scenario>_<UTC>.csv (header written once).
results/results.csv is never written here: scripts/build_results.py rebuilds it from all raw run
files. Traces go to results/raw/traces_<UTC>.jsonl.
"""

from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

RESULTS_COLUMNS = ["request_id", "scenario", "source", "start_time", "first_token_ms", "total_ms", "status",
                   "retries", "tokens_in", "tokens_out", "retrieval_setting", "answer_grade"]
STATUSES = frozenset({"ok", "rate_limited", "timeout", "error"})
SOURCES = frozenset({"real", "stand-in"})
GRADES = frozenset({"correct", "wrong", "refused_correctly", "refused_wrongly", ""})
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def traces_path(raw_dir: Path) -> Path:
    return Path(raw_dir) / f"traces_{_utc()}.jsonl"


def run_path(raw_dir: Path, scenario: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", scenario).strip("-") or "run"
    return Path(raw_dir) / f"run_{safe}_{_utc()}.csv"


def validate_row(row: dict) -> list[str]:
    """Problems with one results row (values as written to CSV, i.e. strings, or Python values)."""
    errs = []
    if list(row) != RESULTS_COLUMNS and set(row) != set(RESULTS_COLUMNS):
        return [f"columns {list(row)} != {RESULTS_COLUMNS}"]
    v = {k: "" if row[k] is None else str(row[k]) for k in RESULTS_COLUMNS}
    if v["status"] not in STATUSES:
        errs.append(f"status {v['status']!r} not in {sorted(STATUSES)}")
    if v["source"] not in SOURCES:
        errs.append(f"source {v['source']!r} not in {sorted(SOURCES)}")
    if v["answer_grade"] not in GRADES:
        errs.append(f"answer_grade {v['answer_grade']!r} not in {sorted(GRADES - {''})} or empty")
    if not v["request_id"]:
        errs.append("empty request_id")
    if not _ISO.fullmatch(v["start_time"]):
        errs.append(f"start_time {v['start_time']!r} is not UTC ISO with milliseconds")
    for k in ("first_token_ms", "total_ms"):
        if v[k]:
            try:
                float(v[k])
            except ValueError:
                errs.append(f"{k} {v[k]!r} is not a number")
    for k in ("retries", "tokens_in", "tokens_out"):
        if not v[k].isdigit():
            errs.append(f"{k} {v[k]!r} is not a non-negative integer")
    return errs


class ResultsWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size > 0:
            with self.path.open(encoding="utf-8", newline="") as f:
                header = next(csv.reader(f), None)
            if header != RESULTS_COLUMNS:
                raise ValueError(f"{self.path} has header {header}, expected {RESULTS_COLUMNS}; not appending")

    def write(self, row: dict) -> None:
        errs = validate_row(row)
        if errs:
            raise ValueError("invalid results row: " + "; ".join(errs))
        new = not self.path.exists() or self.path.stat().st_size == 0
        with self.path.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=RESULTS_COLUMNS)
            if new:
                w.writeheader()
            w.writerow({k: "" if row[k] is None else row[k] for k in RESULTS_COLUMNS})
            f.flush()
            os.fsync(f.fileno())


class TraceWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, rec: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
