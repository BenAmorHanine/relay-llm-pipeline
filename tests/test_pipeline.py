"""Pipeline tests with FakeClient only (no network, no Groq). Every file is written to a temporary
directory; Pipeline refuses to let a FakeClient write inside the repo's results/ directory.

Run from the repo root (cmd):
    .venv\\Scripts\\python.exe -m unittest -v tests.test_pipeline
"""

from __future__ import annotations

import asyncio
import csv
import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from relay.chunking import Chunk  # noqa: E402
from relay.model_client import M20, M120, FakeClient, FakeReply, RetryPolicy  # noqa: E402
from relay.pipeline import (NO_VERIFIED_ANSWER, OUT_OF_SCOPE, OUTCOME_TO_STATUS, REFUSAL,  # noqa: E402
                            RETRIEVAL_SETTINGS, SEARCH_PROBLEM, Pipeline, PipelineConfig, check_answer)
from relay.recording import (GRADES, RESULTS_COLUMNS, SOURCES, STATUSES, ResultsWriter, TraceWriter,  # noqa: E402
                             run_path, validate_row)
from relay.retrieval import Hit  # noqa: E402

A = "1706.03762v7"


def chunk(i: int, section: str, page: int, text: str) -> Chunk:
    number, title = section.split(" ", 1)
    return Chunk(f"{A}:{i:04d}", A, [title], number, page, page, text, len(text.split()), ["body"])


HITS = [
    Hit(chunk(10, "3.2.2 Multi-Head Attention", 5,
              "In this work we employ h = 8 parallel attention layers, or heads. For each of these we use "
              "d_k = d_v = d_model/h = 64."), 9.1, 1, "bm25"),
    Hit(chunk(30, "5.3 Optimizer", 7, "We used warmup_steps = 4000. We used the Adam optimizer with "
                                      "β1 = 0.9, β2 = 0.98 and ϵ = 10^-9."), 7.2, 2, "bm25"),
    Hit(chunk(31, "6.1 Machine Translation", 8, "Table 2: The Transformer achieves better BLEU scores.\n"
                                                "Transformer (base model) | 27.3 | 38.1 | 3.3 · 10^18"), 5.0, 3, "bm25"),
]

ROUTE_OK = '{"keywords": ["attention heads", "multi-head"], "papers": ["1706.03762v7"], "in_scope": true}'
ROUTE_OUT = '{"keywords": [], "papers": [], "in_scope": false}'
GOOD = "The Transformer uses 8 attention heads [1]."


def valid_row(**over) -> dict:
    row = {"request_id": "r-1", "scenario": "test", "source": "stand-in", "start_time": "2026-11-12T10:00:00.000Z",
           "first_token_ms": 1200.5, "total_ms": 1300.0, "status": "ok", "retries": 0, "tokens_in": 100,
           "tokens_out": 50, "retrieval_setting": "medium", "answer_grade": ""}
    row.update(over)
    return row


class FakeTool:
    name = "fake_bm25"
    setting = "medium"

    def __init__(self, delay_s: float = 0.0):
        self.delay_s, self.queries = delay_s, []

    def search(self, query: str):
        self.queries.append(query)
        if self.delay_s:
            time.sleep(self.delay_s)
        return list(HITS)


class Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.csv_path, self.trace_path = self.dir / "run_test.csv", self.dir / "traces_test.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, script, tool=None, policy=RetryPolicy(jitter_s=0.0), **cfg):
        self.client = FakeClient(script, policy=policy)
        self.tool = tool or FakeTool()
        return Pipeline(self.client, self.tool, ResultsWriter(self.csv_path), TraceWriter(self.trace_path),
                        PipelineConfig(**cfg))

    def rows(self):
        with self.csv_path.open(encoding="utf-8", newline="") as f:
            r = list(csv.reader(f))
        self.assertEqual(r[0], RESULTS_COLUMNS)
        rows = [dict(zip(r[0], x)) for x in r[1:]]
        for row in rows:
            self.assertEqual(validate_row(row), [])
        return rows

    def traces(self):
        return [json.loads(line) for line in self.trace_path.read_text(encoding="utf-8").splitlines()]

    def steps(self):
        return [t["step"] for t in self.traces() if t["type"] == "step"]

    def step(self, name):
        return next(t for t in self.traces() if t.get("step") == name and t["type"] == "step")

    def n_calls(self, model):
        return sum(1 for c in self.client.calls if c["model"] == model)

    def assert_result(self, res, status, outcome):
        self.assertEqual((res["status"], res["outcome"]), (status, outcome))
        (row,) = self.rows()
        self.assertEqual(row["status"], status)
        self.assertEqual(self.step("stream")["outcome"], outcome)   # the detail lives in the trace
        return row


class TestPipeline(Base):
    async def test_normal_answer(self):
        p = self.make({M20: [FakeReply(ROUTE_OK, tokens_in=180, reasoning_tokens=20)],
                       M120: [FakeReply("The Transformer uses 8 attention heads [1]. "
                                        "Each head has dimension 64 [1].", tokens_in=1500, reasoning_tokens=30)]})
        seen = []
        q = "How many attention heads does the base Transformer use?"
        res = await p.answer(q, "t-normal", "test", sink=seen.append)
        row = self.assert_result(res, "ok", "answered")
        self.assertIn("Sources:\n[1] [1706.03762v7, 3.2.2 Multi-Head Attention, p.5]", res["answer"])
        self.assertEqual("".join(seen), res["answer"])
        self.assertEqual(self.steps(), ["route", "retrieve", "draft", "check", "stream"])
        self.assertEqual((row["retries"], row["source"], row["retrieval_setting"], row["answer_grade"]),
                         ("0", "stand-in", "medium", ""))
        self.assertEqual(int(row["tokens_in"]), 180 + 1500)
        # fake tokens = whitespace pieces + reasoning tokens: router 8 + 20, draft 13 + 30
        self.assertEqual(int(row["tokens_out"]), (8 + 20) + (13 + 30))
        self.assertLessEqual(float(row["first_token_ms"]), float(row["total_ms"]))
        self.assertEqual(self.client.calls[1]["max_tokens"], 500)
        self.assertEqual(self.client.calls[1]["reasoning_effort"], "low")

    async def test_router_max_tokens_200_and_keywords_only_logged(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)], M120: [FakeReply(GOOD)]})
        q = "How many attention heads does the base Transformer use?"
        await p.answer(q, "t-route", "test")
        self.assertEqual(self.client.calls[0]["max_tokens"], 200)
        self.assertEqual(self.tool.queries, [q])                       # the question as is, no keywords
        self.assertEqual(self.step("retrieve")["query"], q)
        self.assertEqual(self.step("route")["route"]["keywords"], ["attention heads", "multi-head"])
        self.assertEqual(self.step("route")["route"]["papers"], [A])

    async def test_refusal_from_model(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)], M120: [FakeReply(REFUSAL)]})
        res = await p.answer("What batch size did Moshi use for fine-tuning on Fisher?", "t-refuse", "test")
        self.assert_result(res, "ok", "refused")
        self.assertEqual(res["answer"], REFUSAL)
        self.assertEqual(self.steps(), ["route", "retrieve", "draft", "check", "stream"])

    async def test_out_of_scope_branch(self):
        p = self.make({M20: [FakeReply(ROUTE_OUT)], M120: []})
        res = await p.answer("What will the weather be in Paris tomorrow?", "t-oos", "test")
        self.assert_result(res, "ok", "refused_out_of_scope")
        self.assertEqual(res["answer"], OUT_OF_SCOPE)
        self.assertEqual(self.n_calls(M120), 0)
        self.assertEqual(self.tool.queries, [])
        self.assertEqual(self.steps(), ["route", "stream"])

    async def test_check_failure_fixed_by_redraft(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)],
                       M120: [FakeReply("The Transformer uses 16 attention heads [1]."), FakeReply(GOOD)]})
        res = await p.answer("How many heads?", "t-redraft", "test")
        self.assert_result(res, "ok", "answered")
        self.assertEqual(self.n_calls(M120), 2)
        self.assertIn("16 does not appear there", self.client.calls[2]["messages"][-1]["content"])
        self.assertEqual(self.steps(), ["route", "retrieve", "draft", "check", "redraft", "recheck", "stream"])

    async def test_uncited_number_triggers_redraft(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)],
                       M120: [FakeReply("The Transformer uses 8 attention heads. They run in parallel [1]."),
                              FakeReply(GOOD)]})
        res = await p.answer("How many heads?", "t-uncited", "test")
        self.assert_result(res, "ok", "answered")
        self.assertIn("has the number(s) 8 but no citation", self.step("check")["errors"][0])

    async def test_check_failure_ends_in_refusal(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)],
                       M120: [FakeReply("Warmup took 4000 steps [7]."), FakeReply("Warmup took 5000 steps [2].")]})
        res = await p.answer("How many warmup steps?", "t-checkfail", "test")
        self.assert_result(res, "ok", "refused_check_failed")
        self.assertTrue(res["answer"].startswith(NO_VERIFIED_ANSWER))
        self.assertIn("[2] [1706.03762v7, 5.3 Optimizer, p.7]", res["answer"])
        self.assertEqual(self.n_calls(M120), 2)                         # one redraft, never more
        self.assertIn("[7] does not exist", self.step("check")["errors"][0])
        self.assertIn("5000", self.step("recheck")["errors"][0])

    async def test_429_on_draft_is_retried(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)],
                       M120: [FakeReply(status=429, retry_after_s=0.15), FakeReply(GOOD)]})
        res = await p.answer("How many heads?", "t-429", "test")
        row = self.assert_result(res, "ok", "answered")
        self.assertEqual(row["retries"], "1")
        draft = self.step("draft")
        self.assertEqual([a["status"] for a in draft["attempts"]], [429, 200])
        self.assertEqual(draft["attempts"][0]["limit_type"], "requests")
        self.assertGreaterEqual(draft["retry_ms"], 150)                 # no 120b request accepted yet: from now
        self.assertAlmostEqual(draft["wait_ms"] + draft["retry_ms"] + draft["work_ms"], draft["duration_ms"],
                               delta=15)

    async def test_429_retries_exhausted(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)], M120: [FakeReply(status=429, retry_after_s=0.01)] * 4})
        res = await p.answer("How many heads?", "t-429x", "test")
        row = self.assert_result(res, "rate_limited", "rate_limited")
        self.assertEqual(row["retries"], "3")
        self.assertEqual(self.n_calls(M120), 4)

    async def test_tool_timeout(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)], M120: []}, tool=FakeTool(delay_s=0.5), retrieval_timeout_s=0.05)
        res = await p.answer("How many heads?", "t-tooltimeout", "test")
        self.assert_result(res, "timeout", "tool_timeout")
        self.assertEqual(res["answer"], SEARCH_PROBLEM)
        self.assertEqual(self.n_calls(M120), 0)
        self.assertTrue(self.step("retrieve")["timed_out"])
        self.assertLess(self.step("retrieve")["duration_ms"], 400)

    async def test_draft_client_timeout_not_retried(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)], M120: [FakeReply(stall=True), FakeReply(GOOD)]},
                      call_timeout_s=0.1)
        res = await p.answer("How many heads?", "t-modeltimeout", "test")
        row = self.assert_result(res, "timeout", "model_timeout")
        self.assertEqual(self.n_calls(M120), 1)
        self.assertEqual(row["retries"], "0")

    async def test_server_error_on_draft_twice_is_error(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)], M120: [FakeReply(status=500), FakeReply(status=500)]})
        res = await p.answer("How many heads?", "t-500", "test")
        row = self.assert_result(res, "error", "model_error")
        self.assertEqual((self.n_calls(M120), row["retries"]), (2, "1"))

    async def test_user_gives_up_before_first_token(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)], M120: [FakeReply(GOOD, headers_delay_s=0.5)]})
        res = await p.answer("How many heads?", "t-giveup", "test", give_up_s=0.2)
        self.assertEqual((res["status"], res["outcome"]), ("timeout", "user_gave_up"))
        (row,) = self.rows()
        self.assertEqual((row["status"], row["first_token_ms"]), ("timeout", ""))
        self.assertAlmostEqual(float(row["total_ms"]), 200, delta=40)
        self.assertTrue(self.step("draft")["cancelled"])            # the abandoned call is still traced

    async def test_give_up_keeps_429_attempts_in_trace(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)],
                       M120: [FakeReply(status=429, retry_after_s=1.0, limit_type="tokens"), FakeReply(GOOD)]})
        res = await p.answer("How many heads?", "t-giveup429", "test", give_up_s=0.3)
        self.assertEqual(res["outcome"], "user_gave_up")
        draft = self.step("draft")
        self.assertEqual([a["status"] for a in draft["attempts"]], [429])
        self.assertEqual(draft["attempts"][0]["limit_type"], "tokens")
        self.assertEqual(self.rows()[0]["retries"], "1")

    async def test_daily_limit_not_retried_and_shows_passages(self):
        p = self.make({M20: [FakeReply(ROUTE_OK)],
                       M120: [FakeReply(status=429, retry_after_s=86, limit_type="requests_per_day"), FakeReply(GOOD)]})
        res = await p.answer("How many heads?", "t-daily", "test")
        self.assertEqual((res["status"], res["outcome"]), ("rate_limited", "rate_limited_daily"))
        self.assertEqual(self.n_calls(M120), 1)                         # never retried
        self.assertTrue(res["answer"].startswith("Today's answer budget is used up"))
        self.assertIn("[1] [1706.03762v7, 3.2.2 Multi-Head Attention, p.5]", res["answer"])
        self.assertEqual(self.rows()[0]["retries"], "0")

    async def test_router_out_of_scope_overridden_when_paper_named(self):
        p = self.make({M20: [FakeReply(ROUTE_OUT)], M120: [FakeReply(GOOD)]})
        res = await p.answer("How much more data-efficient is H-Net than isotropic models on DNA?", "t-guard", "test")
        self.assertEqual(res["outcome"], "answered")
        self.assertTrue(self.step("route")["router_overridden"])

    async def test_router_bad_json_falls_back(self):
        p = self.make({M20: [FakeReply("sure! the answer is", finish_reason="length")], M120: [FakeReply(GOOD)]})
        res = await p.answer("How many heads?", "t-router-bad", "test")
        self.assert_result(res, "ok", "answered")
        self.assertTrue(self.step("route")["router_fallback"])

    async def test_one_row_per_request(self):
        p = self.make(lambda model, msgs, n: FakeReply(ROUTE_OK) if model == M20 else FakeReply(GOOD))
        await asyncio.gather(*(p.answer("How many heads?", f"t-{i}", "test") for i in range(5)))
        self.assertEqual(sorted(r["request_id"] for r in self.rows()), [f"t-{i}" for i in range(5)])


class TestResultsValues(Base):
    def test_mapping_targets_are_brief_statuses(self):
        self.assertEqual(set(OUTCOME_TO_STATUS.values()), STATUSES)
        self.assertEqual(OUTCOME_TO_STATUS["refused"], "ok")              # a model refusal is ok
        self.assertEqual(OUTCOME_TO_STATUS["tool_timeout"], "timeout")
        self.assertEqual(OUTCOME_TO_STATUS["user_gave_up"], "timeout")
        self.assertEqual(STATUSES, {"ok", "rate_limited", "timeout", "error"})
        self.assertEqual(SOURCES, {"real", "stand-in"})
        self.assertEqual(GRADES, {"correct", "wrong", "refused_correctly", "refused_wrongly", ""})

    def test_writer_rejects_any_other_value(self):
        w = ResultsWriter(self.csv_path)
        w.write(valid_row())
        for g in ("correct", "wrong", "refused_correctly", "refused_wrongly"):
            w.write(valid_row(request_id=f"r-{g}", answer_grade=g, source="real"))
        bad = [{"status": "answered"}, {"status": "refused"}, {"status": "tool_timeout"}, {"status": "OK"},
               {"source": "fake"}, {"source": "groq"}, {"source": "standin"},
               {"answer_grade": "maybe"}, {"answer_grade": "refused"}, {"retries": -1}, {"tokens_in": "1.5"},
               {"start_time": "2026-11-12 10:00:00"}]
        for over in bad:
            with self.subTest(**{k: str(v) for k, v in over.items()}):
                with self.assertRaises(ValueError):
                    w.write(valid_row(request_id="r-bad", **over))
        self.assertEqual(len(self.rows()), 5)                          # nothing invalid was appended

    def test_fake_client_cannot_write_into_repo_results(self):
        with self.assertRaises(ValueError):
            Pipeline(FakeClient({}), FakeTool(), ResultsWriter(ROOT / "results" / "raw" / "run_guard.csv"),
                     TraceWriter(self.trace_path))
        with self.assertRaises(ValueError):
            Pipeline(FakeClient({}), FakeTool(), ResultsWriter(self.csv_path),
                     TraceWriter(ROOT / "results" / "raw" / "traces_guard.jsonl"))
        self.assertFalse((ROOT / "results" / "raw" / "run_guard.csv").exists())

    def test_run_path_name(self):
        p = run_path(self.dir, "eval medium")
        self.assertRegex(p.name, r"^run_eval-medium_\d{8}T\d{6}Z\.csv$")


class TestBuildResults(Base):
    def write_run(self, name, rows):
        w = ResultsWriter(self.dir / "raw" / name)
        for r in rows:
            w.write(r)

    def test_rebuild_sorted_by_start_time(self):
        import build_results
        self.write_run("run_b_20261112T120000Z.csv", [valid_row(request_id="b-1", start_time="2026-11-12T12:00:01.000Z"),
                                                      valid_row(request_id="b-2", start_time="2026-11-12T09:00:00.000Z")])
        self.write_run("run_a_20261112T100000Z.csv", [valid_row(request_id="a-1", start_time="2026-11-12T10:00:00.000Z")])
        out = self.dir / "results.csv"
        self.assertEqual(build_results.build(self.dir / "raw", out), (2, 3))
        with out.open(encoding="utf-8", newline="") as f:
            r = list(csv.reader(f))
        self.assertEqual(r[0], RESULTS_COLUMNS)
        self.assertEqual([x[0] for x in r[1:]], ["b-2", "a-1", "b-1"])

    def test_rebuild_refuses_bad_or_duplicate_rows(self):
        import build_results
        self.write_run("run_a_20261112T100000Z.csv", [valid_row(request_id="a-1")])
        self.write_run("run_b_20261112T110000Z.csv", [valid_row(request_id="a-1")])       # duplicate id
        out = self.dir / "results.csv"
        with self.assertRaises(SystemExit) as cm:
            build_results.build(self.dir / "raw", out)
        self.assertIn("already in", str(cm.exception))
        self.assertFalse(out.exists())
        # a raw file edited to hold a value outside the brief's sets
        bad = self.dir / "raw2" / "run_c_20261112T120000Z.csv"
        bad.parent.mkdir()
        bad.write_text(",".join(RESULTS_COLUMNS) + "\n" + "c-1,test,fake,2026-11-12T10:00:00.000Z,1,2,answered,0,1,1,"
                       "medium,\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            build_results.build(bad.parent, out)
        self.assertIn("source 'fake'", str(cm.exception))
        self.assertIn("status 'answered'", str(cm.exception))


class TestRetryPolicy(Base):
    async def test_requests_429_waits_from_last_accepted_request(self):
        client = FakeClient({M120: [FakeReply("ok", headers_delay_s=0.2),
                                    FakeReply(status=429, retry_after_s=0.3, limit_type="requests"),
                                    FakeReply("ok")]}, policy=RetryPolicy(jitter_s=0.0))
        r1 = await client.stream_chat(M120, [], 10).collect()          # accepted at ~t, finishes at ~t+0.2
        r2 = await client.stream_chat(M120, [], 10).collect()          # 429 at ~t+0.2, retry-after 0.3
        self.assertEqual((r1.status, r2.status, r2.retries), (200, 200, 1))
        gap = r2.attempts[1].start_ms - r2.attempts[0].start_ms
        # retry at t+0.3 (from the accepted request), i.e. ~0.1 s after the 429, not 0.3 s after it
        self.assertGreater(gap, 50)
        self.assertLess(gap, 250)

    async def test_tokens_429_waits_from_now(self):
        client = FakeClient({M120: [FakeReply("ok", headers_delay_s=0.2),
                                    FakeReply(status=429, retry_after_s=0.3, limit_type="tokens"),
                                    FakeReply("ok")]}, policy=RetryPolicy(jitter_s=0.0))
        await client.stream_chat(M120, [], 10).collect()
        r2 = await client.stream_chat(M120, [], 10).collect()
        gap = r2.attempts[1].start_ms - r2.attempts[0].start_ms
        self.assertGreaterEqual(gap, 300)                               # the full 0.3 s after the 429

    async def test_jitter_only_added(self):
        for limit_type in ("requests", "tokens"):
            with self.subTest(limit_type=limit_type):
                client = FakeClient({M120: [FakeReply(status=429, retry_after_s=0.1, limit_type=limit_type),
                                            FakeReply("ok")]}, policy=RetryPolicy(jitter_s=0.1), rng=lambda: 1.0)
                r = await client.stream_chat(M120, [], 10).collect()
                self.assertGreaterEqual(r.attempts[1].start_ms - r.attempts[0].start_ms, 200)   # 0.1 + 0.1 jitter

    async def test_server_errors_retried_once_with_jitter(self):
        for status in (500, 502, 503, 498):
            with self.subTest(status=status):
                client = FakeClient({M120: [FakeReply(status=status), FakeReply("ok")]},
                                    policy=RetryPolicy(jitter_s=0.1), rng=lambda: 1.0)
                r = await client.stream_chat(M120, [], 10).collect()
                self.assertEqual((r.outcome, r.retries, [a.status for a in r.attempts]), ("ok", 1, [status, 200]))
                self.assertGreaterEqual(r.attempts[1].start_ms - r.attempts[0].start_ms, 100)  # the jitter
                client = FakeClient({M120: [FakeReply(status=status)] * 3}, policy=RetryPolicy(jitter_s=0.0))
                r = await client.stream_chat(M120, [], 10).collect()
                self.assertEqual((r.outcome, r.retries, len(r.attempts)), ("http_error", 1, 2))  # once only

    async def test_other_errors_not_retried(self):
        for reply in (FakeReply(status=400), FakeReply(status=401), FakeReply(network_error=True)):
            with self.subTest(reply=str(reply.status) + (" network" if reply.network_error else "")):
                client = FakeClient({M120: [reply, FakeReply("ok")]})
                r = await client.stream_chat(M120, [], 10).collect()
                self.assertEqual((r.retries, len(r.attempts)), (0, 1))

    def test_limit_kind_from_real_bodies(self):
        from relay.model_client import limit_kind
        rpm = ('{"error":{"message":"Rate limit reached for model `openai/gpt-oss-120b` in organization `org_X` '
               'service tier `on_demand` on requests per minute (RPM): Limit 30, Used 30, Requested 1. Please try '
               'again in 2s.","type":"requests","code":"rate_limit_exceeded"}}')
        self.assertEqual(limit_kind(rpm), "requests")
        self.assertEqual(limit_kind(rpm.replace("requests per minute (RPM)", "requests per day (RPD)")),
                         "requests_per_day")
        self.assertEqual(limit_kind(rpm.replace('"type":"requests"', '"type":"tokens"')), "tokens")
        self.assertIsNone(limit_kind("not json"))

    async def test_client_timeout_never_retried(self):
        client = FakeClient({M120: [FakeReply(stall=True), FakeReply("ok")]})
        r = await client.stream_chat(M120, [], 10, timeout=0.1).collect()
        self.assertEqual((r.outcome, r.retries, len(r.attempts)), ("timeout", 0, 1))

    async def test_gate_is_shared_per_model(self):
        client = FakeClient({M120: [FakeReply(status=429, retry_after_s=0.2), FakeReply("a")],
                             M20: [FakeReply("c")]}, policy=RetryPolicy(jitter_s=0.0))
        r1 = await client.stream_chat(M120, [], 10).collect()
        self.assertEqual(r1.retries, 1)
        r3 = await client.stream_chat(M20, [], 10).collect()            # 20b is not held by 120b's gate
        self.assertLess(r3.wait_ms, 20)


class TestRealFailures(unittest.TestCase):
    """Drafts copied verbatim from results/raw/traces_eval_medium_20261112T225309Z.jsonl (the stopped
    real run), checked against the same BM25 medium passages. All were refused by the old check."""

    @classmethod
    def setUpClass(cls):
        import yaml
        from relay.pipeline import BM25Tool
        cls.qs = {q["id"]: q for q in yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text(encoding="utf-8"))}
        cls.tool = BM25Tool("medium")

    def hits(self, qid):
        return self.tool.search(self.qs[qid]["question"])

    REAL = {
        "q02": "The base Transformer models were trained for a total of 100,000 steps, which took about 12 hours "
               "on a machine with 8 NVIDIA P100 GPUs【1】.  \nThe big Transformer models were trained for 300,000 "
               "steps, which required 3.5 days on 8 NVIDIA P100 GPUs【1】【2】.",
        "q03": "The training used the Adam optimizer with β₁ = 0.9, β₂ = 0.98 and ε = 10⁻⁹ [1]. In the "
               "audio‑codec model AdamW was used, applying weight decay only to Transformer parameters (weight 5 × 10⁻²), "
               "a momentum decay of 0.5 and a decay of the squared gradient of 0.9 [5].",
        "q08": "H‑Net’s dynamic chunking compresses data to roughly 4.5–5 bytes per chunk, whereas SpaceByte’s "
               "spacelike delimiter heuristic averages about 6.0 bytes per chunk【2】【1】",
        "q10": "The base Transformer required 3.3 × 10¹⁸ FLOPs of training cost for the English‑German task【1】.",
        "q11": "The experiments used peak learning rates of 6.25 × 10⁻⁴ for the Large‑scale H‑Net models and 5.0"
               " × 10⁻⁴ for the XL‑scale H‑Net models【3】.",
        "q13": "The big Transformer achieved a BLEU score of 41.8 on the WMT 2014 English‑to‑French translation "
               "task【1†L4-L5】【2†L7-L9】",
    }

    def test_real_drafts_now_pass(self):
        for qid, draft in self.REAL.items():
            with self.subTest(qid=qid):
                r = check_answer(draft, self.hits(qid))
                self.assertTrue(r.ok, r.errors)
                self.assertTrue(r.cited)

    def test_real_drafts_with_a_different_number_fail(self):
        changed = {"q02": ("12 hours", "13 hours"), "q03": ("10⁻⁹", "10⁻⁸"), "q08": ("6.0", "6.5"),
                   "q10": ("10¹⁸", "10¹⁹"), "q11": ("6.25", "6.5"), "q13": ("41.8", "41.9")}
        for qid, (a, b) in changed.items():
            with self.subTest(qid=qid):
                self.assertIn(a, self.REAL[qid])
                self.assertFalse(check_answer(self.REAL[qid].replace(a, b, 1), self.hits(qid)).ok)

    def test_day1_false_failures_now_pass(self):
        from relay.pipeline import BM25Tool
        fx = json.loads((ROOT / "tests" / "fixtures" / "day1_false_check_failures.json").read_text(encoding="utf-8"))
        tools = {s: BM25Tool(s) for s in {d["setting"] for d in fx["drafts"]}}
        self.assertEqual(len(fx["drafts"]), 8)
        for d in fx["drafts"]:
            with self.subTest(qid=d["qid"], setting=d["setting"], step=d["step"]):
                hits = tools[d["setting"]].search(self.qs[d["qid"]]["question"])
                r = check_answer(d["text"], hits)
                self.assertTrue(r.ok, r.errors)

    def test_day2_false_failures_now_pass(self):
        from relay.pipeline import BM25Tool, normalize_citations
        fx = json.loads((ROOT / "tests" / "fixtures" / "day2_false_check_failures.json").read_text(encoding="utf-8"))
        self.assertEqual(len(fx["drafts"]), 3)
        tools = {s: BM25Tool(s) for s in {d["setting"] for d in fx["drafts"]}}
        for d in fx["drafts"]:
            with self.subTest(qid=d["qid"], setting=d["setting"], step=d["step"]):
                hits = tools[d["setting"]].search(self.qs[d["qid"]]["question"])
                r = check_answer(normalize_citations(d["text"]), hits)   # as the pipeline does
                self.assertTrue(r.ok, r.errors)

    def test_day2_patterns_still_catch_wrong_numbers(self):
        from relay.textnorm import number_values
        self.assertEqual(number_values(r"p = \tfrac12 and \frac{3}{4}"), {"1", "2", "3", "4"})
        self.assertEqual(number_values("about one‑third of the data, one half, two thirds"), set())
        self.assertEqual(number_values("eight heads, k_{t‑1}"), {"8", "1"})
        hits = self.hits("q14")
        self.assertFalse(check_answer("H‑Net is about 4.6× more data‑efficient [3].", hits).ok)

    def test_day1_patterns_still_fail_on_wrong_numbers(self):
        hits = self.hits("q02")
        ok = "The base Transformer models were trained for 100 000 steps, which took about 12 hours [1]."
        self.assertTrue(check_answer(ok, hits).ok, check_answer(ok, hits).errors)
        self.assertFalse(check_answer(ok.replace("100 000", "200 000"), hits).ok)
        q22 = "Each token gets a confidence p^s ∈[0,1]^{L_s} from the routing module [2]."
        self.assertEqual(check_answer(q22, self.tool.search(self.qs["q22"]["question"])).cited, [2])

    def test_real_wrong_source_still_fails(self):
        # q13's real redraft: 41.8 is in passages [2] and [3], not in the cited [1]
        redraft = ("The big Transformer reached a BLEU score of 41.8 on the WMT 2014 English‑to‑French "
                   "translation task【1†L4-L5】")
        r = check_answer(redraft, self.hits("q13"))
        self.assertFalse(r.ok)
        self.assertIn("41.8 does not appear", r.errors[0])


class TestNumberValues(unittest.TestCase):
    def test_equivalent_notations(self):
        from relay.textnorm import number_values as nv
        same = [("3.3 × 10^18", "3.3·10¹⁸", "3.3 x 10^18", "3.3*10^18", "3.3e18", "3.3 · 10^18"),
                ("6.25 × 10^-4", "6.25 × 10−4", "6.25×10⁻⁴", "6.25e-4", "6.25 x 10^-4"),
                ("10^-9", "10⁻⁹", "1e-9"),
                ("100,000 steps", "100000 steps"),
                ("eight heads", "8 heads"), ("twelve hours", "12 hours"),
                ("12.5Hz", "12.5 Hz"), ("160ms", "160 ms"), ("6.0 bytes", "6 bytes")]
        for group in same:
            with self.subTest(group=group[0]):
                self.assertEqual(len({frozenset(nv(x)) for x in group}), 1, [nv(x) for x in group])
        different = [("3.3 × 10^18", "3.3 × 10^19"), ("6.25e-4", "6.25e-5"), ("100,000", "10,000"),
                     ("12.5Hz", "12.6Hz"), ("eight", "nine"), ("41.8", "41.08")]
        for a, b in different:
            with self.subTest(pair=a):
                self.assertNotEqual(nv(a), nv(b))

    def test_brackets(self):
        from relay.pipeline import normalize_citations
        self.assertEqual(normalize_citations("x【1】【2】 y【1, 3】 z［2］ w【4†L3-L5】"), "x[1][2] y[1, 3] z[2] w[4]")


class TestCheck(unittest.TestCase):
    def test_number_normalisation(self):
        self.assertTrue(check_answer("Training cost 3.3 × 10^18 FLOPs [3].", HITS).ok)
        self.assertTrue(check_answer("Training cost 3.3·10^18 FLOPs. [3]", HITS).ok)
        self.assertFalse(check_answer("Training cost 3.3 × 10^19 FLOPs [3].", HITS).ok)

    def test_number_must_be_in_cited_passage(self):
        self.assertFalse(check_answer("Warmup used 4000 steps [1].", HITS).ok)   # 4000 is in passage 2
        self.assertTrue(check_answer("Warmup used 4000 steps [1, 2].", HITS).ok)

    def test_no_partial_number_match(self):
        self.assertFalse(check_answer("It uses 6 heads [1].", HITS).ok)   # "6" must not match inside "64"

    def test_uncited_number_fails(self):
        r = check_answer("The base model has 8 heads [1]. It trains with 4000 warmup steps.", HITS)
        self.assertFalse(r.ok)
        self.assertIn("4000", r.errors[0])
        self.assertTrue(check_answer("Heads run in parallel [1]. This makes training fast.", HITS).ok)  # no number

    def test_refusal_and_uncited(self):
        self.assertTrue(check_answer(REFUSAL, HITS).ok)
        self.assertTrue(check_answer(REFUSAL, HITS).refusal)
        self.assertFalse(check_answer("The model uses attention.", HITS).ok)   # no citation at all
        self.assertFalse(check_answer("8 heads [1].", HITS, finish_reason="length").ok)

    def test_settings_match_eval(self):
        import eval_retrieval as ev
        self.assertEqual(RETRIEVAL_SETTINGS, {k: (v[0], v[1], v[2]) for k, v in ev.SETTINGS.items()})


class TestPaperCover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from relay.pipeline import BM25Tool
        from relay.retrieval import RetrievalPipeline
        cls.tool = BM25Tool("medium")
        cls.plain = RetrievalPipeline(cls.tool._pipe.retriever, final_k=cls.tool.k)

    def ids(self, hits):
        return [h.chunk.chunk_id for h in hits]

    def test_top_k_is_never_replaced(self):
        for q in ("Where does each of the three papers put normalization layers, and of what kind?",
                  "What BLEU score did the big Transformer reach on WMT 2014 English-to-French?"):
            with self.subTest(q=q):
                self.assertEqual(self.ids(self.tool.search(q))[: self.tool.k], self.ids(self.plain.search(q)))

    def test_single_paper_question_gets_no_extra(self):
        q = "What is the frame rate and bitrate of the Mimi codec, and how many quantizers does it use?"
        self.assertEqual(len(self.tool.search(q)), self.tool.k)

    def test_all_papers_question_covers_every_paper(self):
        hits = self.tool.search("Where does each of the three papers put normalization layers, and of what kind?")
        self.assertEqual({h.chunk.paper_id for h in hits}, {"1706.03762v7", "2410.00037v1", "2507.07955v2"})
        self.assertLessEqual(len(hits), self.tool.k + 2)

    def test_named_paper_is_covered(self):
        hits = self.tool.search("Does Moshi use the label smoothing of the original Transformer?")
        self.assertIn("2410.00037v1", {h.chunk.paper_id for h in hits})
        self.assertIn("1706.03762v7", {h.chunk.paper_id for h in hits})


if __name__ == "__main__":
    unittest.main()
