"""The Relay pipeline: route -> retrieve -> draft -> check (-> one redraft) -> stream.

    a) route     one call to gpt-oss-20b (max_tokens 200), JSON {keywords, papers, in_scope}.
                 Out of scope -> refuse immediately (branch). Only in_scope is used; keywords and
                 papers are logged in the trace.
    b) retrieve  BM25 tool call on the user's question as is, over clean, section-aware chunks,
                 wrapped in a timeout.
    c) draft     one call to gpt-oss-120b, reasoning_effort low, numbered passages, a [n] citation
                 after every claim, or the exact refusal sentence if the passages do not answer.
    d) check     deterministic (check_answer): every [n] exists; every number in a cited sentence
                 appears in a cited passage (normalised as in the fact-hit metric); a sentence with
                 a number but no citation fails; a refusal passes.
                 On failure: ONE redraft with the check's errors, re-checked; if that fails too,
                 refuse and show the retrieved passages. Never more than one redraft.
    e) stream    the checked answer is streamed to the user; time to first token = first token of
                 this final answer, measured from the request's start (docs/DECISIONS.md).

Every request appends exactly one row (columns in CLAUDE.md, values validated against the brief)
to the run's raw file results/raw/run_<scenario>_<UTC>.csv, and one trace line per step plus a
closing "request" line to results/raw/traces_<UTC>.jsonl. results/results.csv is rebuilt from the
raw run files by scripts/build_results.py. The detailed outcome (answered, refused, refused_out_of_scope,
refused_check_failed, tool_timeout, model_timeout, rate_limited, model_error, error) is in the trace;
the row carries the brief's status (OUTCOME_TO_STATUS).
Each step records wait_ms (rate gate before the first attempt), retry_ms (retries) and
work_ms (the useful work); local steps only have work_ms.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from .chunking import ChunkConfig, build_chunks, load_blocks
from .model_client import DAILY, M120, M20, CallRecord, ModelClient, utc_iso
from .recording import ResultsWriter, TraceWriter
from .retrieval import BM25Retriever, Hit, PaperCover
from decimal import Decimal

from .textnorm import match_norm, number_values

ROOT = Path(__file__).resolve().parents[2]
CLEAN_DIR = ROOT / "data" / "papers" / "clean"

PAPERS = {
    "1706.03762v7": "Attention Is All You Need (the Transformer)",
    "2410.00037v1": "Moshi: a speech-text foundation model for real-time dialogue",
    "2507.07955v2": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling (H-Net)",
}
# setting -> (chunk target tokens, overlap tokens, chunks retrieved); same as scripts/eval_retrieval.py
RETRIEVAL_SETTINGS = {"small": (128, 16, 8), "medium": (256, 32, 5), "large": (512, 64, 3)}

REFUSAL = "The three papers do not answer this question."
OUT_OF_SCOPE = ("That question is outside what I can answer: I only answer from three papers "
                "(Attention Is All You Need, Moshi, H-Net).")
NO_VERIFIED_ANSWER = "I could not produce an answer I can verify against the papers. These are the passages I found:"
SERVICE_PROBLEM = "The model service did not answer ({why}). Please try again later."
DAILY_BUDGET = ("Today's answer budget is used up, so I can't write and check an answer right now. It frees up "
                "again in about {reset}. Meanwhile, these are the passages from the papers that best match your "
                "question (not checked by a model):")
SEARCH_PROBLEM = "The paper search did not finish in time, so I cannot answer from the papers. Please try again."

PAPER_TOPICS = {
    "1706.03762v7": ('"Attention Is All You Need"',
                     "the Transformer: an encoder-decoder built only from attention (scaled dot-product, multi-head), "
                     "positional encodings, WMT 2014 English-German/French translation, BLEU, training cost, "
                     "constituency parsing."),
    "2410.00037v1": ('"Moshi: a speech-text foundation model for real-time dialogue"',
                     "Moshi, a full-duplex spoken dialogue model: the Helium text language model, the Mimi neural "
                     "audio codec, the RQ/Depth Transformer, Inner Monologue, multi-stream audio, latency, "
                     "speech and text benchmarks."),
    "2507.07955v2": ('"Dynamic Chunking for End-to-End Hierarchical Sequence Modeling"',
                     "H-Net, a tokenizer-free byte-level model that learns dynamic chunking (routing module, "
                     "smoothing, ratio loss), compared with BPE Transformers, Mamba-2 and SpaceByte."),
}

# Names and terms that only make sense for these three papers. If the router says "out of scope" but the
# question contains one of them, the pipeline keeps it in scope (real failure: q14 "How much more data-efficient
# is H-Net than isotropic models on DNA?" was routed out of scope on 2026-11-17, in both settings).
_PAPER_TOPIC = re.compile(
    r"\b(transformers?|attention|self-attention|multi-head|positional encoding|bleu|wmt|moshi|mimi|helium|"
    r"inner monologue|depth transformer|rq-transformer|h-?net|dynamic chunking|chunk(?:s|ing)?|spacebyte|"
    r"mamba-?2?|byte-?level|byte-pair|bpe|tokeni[sz](?:er|ation)s?|tokenizer-free)\b", re.I)


def names_paper_topic(question: str) -> bool:
    return bool(_PAPER_TOPIC.search(question))


# Terms that belong to ONE paper (not shared words like "Transformer" or "chunk"): naming one asks for that paper.
PAPER_TERMS = {
    "1706.03762v7": re.compile(r"attention is all you need|\bbleu\b|\bwmt\b|positional encodings?|"
                               r"label smoothing|english-(?:german|french)", re.I),
    "2410.00037v1": re.compile(r"\bmoshi\b|\bmimi\b|\bhelium\b|inner monologue|depth transformer|"
                               r"rq-transformer", re.I),
    "2507.07955v2": re.compile(r"\bh-?net\b|dynamic chunking|spacebyte|routing module|ratio loss", re.I),
}
# Questions about all the papers at once.
ASKS_ALL_PAPERS = re.compile(r"\b(?:(?:the|all|each of the) (?:three|3) papers|each (?:of the )?papers?|"
                             r"the other two|both papers|all three)\b", re.I)


ROUTER_SYSTEM = (
    "You route questions for a question-answering system that can only use these three arXiv papers:\n"
    + "\n".join(f"- {k} {title}: {topic}" for k, (title, topic) in PAPER_TOPICS.items()) + "\n"
    'Reply with JSON only, no other text: {"keywords": [up to 6 search terms for the question], '
    '"papers": [ids of the papers likely to contain the answer], "in_scope": true or false}.\n'
    "Set in_scope to false ONLY when the question is clearly unrelated to all three papers (for example "
    "weather, sports, cooking). A question that names a model, component, method, dataset or number from "
    "any of these papers is in scope, even if it does not name the paper. When unsure, set in_scope to true."
)

DRAFT_SYSTEM = (
    "You answer questions about three arXiv papers using ONLY the numbered passages you are given.\n"
    "Rules:\n"
    "1. After every sentence that states something from the passages, put the number of the passage it "
    "comes from in square brackets, e.g. [2] or [1][3].\n"
    "2. Write numbers exactly as the passage writes them.\n"
    "3. Do not use anything that is not in the passages.\n"
    f"4. If the passages do not answer the question, reply with exactly this sentence and nothing else: {REFUSAL}\n"
    "5. Each passage starts with its paper id. When passages come from more than one paper, say which paper each "
    "statement is about, and never attach a detail from one paper to another paper's model.\n"
    "6. If the question asks about several papers, answer for each paper the passages cover, and say which "
    "paper the passages do not cover.\n"
    "7. If a term in the question means different things in different papers' passages, give each meaning with "
    "its paper.\n"
    "8. If passages give different values for the same thing, report each value with its citation and say "
    "that they differ.\n"
    "9. Be brief: at most 6 sentences."
)


# ---------------------------------------------------------------- the tool ---

class SearchTool(Protocol):
    name: str
    setting: str

    def search(self, query: str) -> list[Hit]: ...


class BM25Tool:
    """BM25 over clean, section-aware chunks with table context, top-k plus the best chunk of any other paper
    the question calls for (PaperCover; see docs/DECISIONS.md "Paper cover")."""

    name = "bm25"

    def __init__(self, setting: str = "medium", papers_dir: Path = CLEAN_DIR):
        size, overlap, k = RETRIEVAL_SETTINGS[setting]
        cfg = ChunkConfig(size, overlap, section_aware=True)
        chunks = [c for p in PAPERS for c in build_chunks(load_blocks(Path(papers_dir) / f"{p}.jsonl"), cfg)]
        self.setting, self.k, self.n_chunks = setting, k, len(chunks)
        self._pipe = PaperCover(BM25Retriever(chunks), k=k, papers=PAPERS, named=PAPER_TERMS,
                                ask_all=ASKS_ALL_PAPERS, ratio=0.7)

    def search(self, query: str) -> list[Hit]:
        return self._pipe.search(query)


# ---------------------------------------------------------------- prompts ---

def router_messages(question: str) -> list[dict]:
    return [{"role": "system", "content": ROUTER_SYSTEM}, {"role": "user", "content": question}]


def parse_router(text: str) -> dict | None:
    """The router's JSON, or None if it is not usable."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or not isinstance(d.get("in_scope"), bool):
        return None
    kw = d.get("keywords") if isinstance(d.get("keywords"), list) else []
    papers = d.get("papers") if isinstance(d.get("papers"), list) else []
    return {"keywords": [str(k) for k in kw][:6], "papers": [str(p) for p in papers if str(p) in PAPERS],
            "in_scope": d["in_scope"]}


def format_passages(hits: Sequence[Hit]) -> str:
    return "\n\n".join(f"[{i}] {h.chunk.citation()}\n{h.chunk.text}" for i, h in enumerate(hits, 1))


def draft_messages(question: str, hits: Sequence[Hit]) -> list[dict]:
    return [{"role": "system", "content": DRAFT_SYSTEM},
            {"role": "user", "content": f"Passages:\n\n{format_passages(hits)}\n\nQuestion: {question}"}]


def redraft_messages(question: str, hits: Sequence[Hit], draft: str, errors: Sequence[str]) -> list[dict]:
    feedback = ("Your answer failed the citation check:\n" + "\n".join(f"- {e}" for e in errors) +
                "\nWrite the answer again, following the rules. Leave out anything you cannot support with a "
                f"passage; if nothing is supported, reply with exactly: {REFUSAL}")
    return draft_messages(question, hits) + [{"role": "assistant", "content": draft},
                                             {"role": "user", "content": feedback}]


# ------------------------------------------------------------------ check ---

# [n] or [n, m]; not maths: a group containing 0 (passages start at 1) or followed by ^ _ { is an interval
# such as "p ∈ [0,1]^{L_s}" (real draft, q22 day 1), not a citation
_CITE = re.compile(r"\[(?![^\]]*\b0\b)(\d+(?:\s*,\s*\d+)*)\](?![\^_{])")
# "Paper 1", "passage 3": labels, not facts from the passages
_LABEL_NUM = re.compile(r"\b(?:paper|passage)s?\s+\d+\b", re.I)
_LEADING_CITES = re.compile(r"^((?:\[\d+(?:\s*,\s*\d+)*\]\s*)+)(.*)$", re.S)


# gpt-oss often writes citations as 【1】 or 【1†L3】 (its native style) or full-width ［1］: same as [1]
_ALT_CITE = re.compile(r"[【［]\s*(\d+(?:\s*[,，]\s*\d+)*)[^】］]*[】］]")


def normalize_citations(text: str) -> str:
    """【1】, 【1】【2】, 【1, 2】, ［1］, 【1†L3-L5】 -> [1], [1][2], [1, 2], [1], [1]."""
    return _ALT_CITE.sub(lambda m: "[" + re.sub(r"\s*[,，]\s*", ", ", m.group(1)) + "]", text)


def _show(v: str) -> str:
    d = Decimal(v)
    return format(d, "f") if abs(d.adjusted()) <= 6 else str(d)


def citations(text: str) -> list[int]:
    return [int(n) for g in _CITE.findall(text) for n in re.split(r"\s*,\s*", g)]


def split_sentences(text: str) -> list[str]:
    """Sentences; citations written after the full stop ("... heads. [1]") stay with their sentence."""
    out: list[str] = []
    for line in text.split("\n"):
        for piece in re.split(r"(?<=[.!?])\s+", line.strip()):
            m = _LEADING_CITES.match(piece)
            if m and out:
                out[-1] += " " + m.group(1).strip()
                piece = m.group(2)
            if piece.strip():
                out.append(piece.strip())
    return out


@dataclass
class CheckResult:
    ok: bool
    refusal: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cited: list[int] = field(default_factory=list)


def check_answer(answer: str, hits: Sequence[Hit], finish_reason: str | None = None) -> CheckResult:
    """Deterministic: no model, same input -> same result."""
    text = normalize_citations(answer or "").strip()
    if not text:
        return CheckResult(False, False, ["the answer is empty"])
    errors: list[str] = []
    warnings: list[str] = []
    if finish_reason == "length":
        errors.append("the answer was cut off by the token limit; write a shorter answer")
    cited = citations(text)
    k = len(hits)
    refusal = match_norm(REFUSAL) in match_norm(text)
    if refusal and not cited:
        return CheckResult(not errors, True, errors, warnings, [])
    if not cited:
        errors.append("the answer has no [n] citation")
    for n in sorted(set(cited)):
        if not 1 <= n <= k:
            errors.append(f"[{n}] does not exist: there are only passages [1] to [{k}]")
    pnums = {i: number_values(f"{h.chunk.citation()}\n{h.chunk.text}", with_parts=True)
             for i, h in enumerate(hits, 1)}
    for si, sent in enumerate(split_sentences(text), 1):
        sc = [n for n in citations(sent) if 1 <= n <= k]
        body = _LABEL_NUM.sub(" ", _CITE.sub(" ", sent))
        nums = sorted(number_values(body))    # values, so equivalent notations compare equal
        if not citations(sent):
            if nums:  # decided in Step 5b: a number without a citation fails the check
                errors.append(f"sentence {si} has the number(s) {', '.join(_show(v) for v in nums)} but no "
                              f"citation: \"{sent[:100]}\"")
            continue
        pool = set().union(*(pnums[n] for n in sc)) if sc else set()
        missing = [_show(x) for x in nums if x not in pool]
        if sc and missing:
            errors.append(f"sentence {si} cites {''.join(f'[{n}]' for n in sc)} but "
                          f"{', '.join(missing)} {'does' if len(missing) == 1 else 'do'} not appear there: "
                          f"\"{sent[:100]}\"")
    return CheckResult(not errors, refusal, errors, warnings, sorted(set(cited)))


def render_answer(answer: str, hits: Sequence[Hit], cited: Sequence[int]) -> str:
    """The text the user sees: the answer plus the paper/section/page of every cited passage."""
    answer = normalize_citations(answer)
    srcs = "\n".join(f"[{n}] {hits[n - 1].chunk.citation()}" for n in cited if 1 <= n <= len(hits))
    return f"{answer.strip()}\n\nSources:\n{srcs}" if srcs else answer.strip()


def render_passages(hits: Sequence[Hit], chars: int = 300, header: bool = True) -> str:
    lines = [NO_VERIFIED_ANSWER] if header else []
    for i, h in enumerate(hits, 1):
        t = " ".join(h.chunk.text.split())
        lines.append(f"[{i}] {h.chunk.citation()} {t[:chars]}{'...' if len(t) > chars else ''}")
    return "\n".join(lines)


# --------------------------------------------------------------- pipeline ---

# What happened in the pipeline (kept in the trace) -> results.csv status (the brief's four values).
# Every refusal is a completed request: status "ok", with the refusal kind recorded in the trace.
OUTCOME_TO_STATUS = {
    "answered": "ok",
    "refused": "ok",                    # the model said the passages do not answer
    "refused_out_of_scope": "ok",       # the router said out of scope
    "refused_check_failed": "ok",       # check failed twice: refusal with the passages shown
    "tool_timeout": "timeout",          # the BM25 tool call timed out
    "model_timeout": "timeout",         # a model call hit the client timeout (never retried)
    "rate_limited": "rate_limited",     # a model call still got 429 after its retries
    "rate_limited_daily": "rate_limited",  # daily budget used up: passages shown, no model answer
    "model_error": "error",             # HTTP error (after the one 5xx retry), network or stream error
    "error": "error",                   # unexpected exception in the pipeline
    "user_gave_up": "timeout",          # the (simulated) user stopped waiting; set by the load generator
}


def call_failure_outcome(call: CallRecord) -> str:
    if call.outcome == "rate_limited" and call.attempts and call.attempts[-1].limit_type == DAILY:
        return "rate_limited_daily"
    return {"rate_limited": "rate_limited", "timeout": "model_timeout"}.get(call.outcome, "model_error")


def failure_reply(call: CallRecord, hits: Sequence[Hit] | None) -> str:
    """What the person sees when the model call failed."""
    outcome = call_failure_outcome(call)
    if outcome == "rate_limited_daily":
        reset = call.headers.get("x-ratelimit-reset-requests", "a few minutes")
        return DAILY_BUDGET.format(reset=reset) + ("\n" + render_passages(hits, header=False) if hits else "")
    if hits is not None:
        return render_passages(hits)
    return SERVICE_PROBLEM.format(why=outcome.replace("_", " "))


@dataclass(frozen=True)
class PipelineConfig:
    router_model: str = M20
    router_max_tokens: int = 200         # decided: 2/5 small 20b calls hit 128 in calibration
    router_effort: str = "low"
    draft_model: str = M120
    draft_max_tokens: int = 500          # 400 until 2026-11-18 (real drafts max 366/400); +100 for the multi-paper rules 6-8
    draft_effort: str = "low"
    retrieval_timeout_s: float = 2.0
    call_timeout_s: float = 60.0
    stream_delay_s: float = 0.0          # pause between streamed words (0: as fast as the sink takes them)


Sink = Callable[[str], Any]


class Pipeline:
    """Retrieval always uses the user's question as is: the router only decides in/out of scope;
    its keywords and papers are logged in the trace, not used (the retrieval eval measured the raw question)."""

    def __init__(self, client: ModelClient, tool: SearchTool, results: ResultsWriter, traces: TraceWriter,
                 config: PipelineConfig = PipelineConfig(), clock: Callable[[], float] = time.perf_counter):
        if getattr(client, "is_fake", False):
            repo_results = (ROOT / "results").resolve()
            for p in (results.path, traces.path):
                if Path(p).resolve().is_relative_to(repo_results):
                    raise ValueError(f"a FakeClient run must not write inside {repo_results} (got {p}); "
                                     "use a temporary directory")
        self.client, self.tool, self.results, self.traces = client, tool, results, traces
        self.cfg, self.clock = config, clock

    async def answer(self, question: str, request_id: str | None = None, scenario: str = "adhoc",
                     sink: Sink | None = None, give_up_s: float | None = None) -> dict:
        """give_up_s: a simulated user who stops waiting if no first token arrives in time
        (outcome user_gave_up -> status timeout; still exactly one row)."""
        rid = request_id or f"req-{uuid.uuid4().hex[:10]}"
        t0, start_time = self.clock(), utc_iso()
        ms = lambda t: round((t - t0) * 1000, 1)  # noqa: E731
        calls: list[CallRecord] = []
        in_progress: dict = {}           # the model call running now, traced as cancelled if the user gives up
        steps: list[dict] = []
        out = {"outcome": "error", "text": "", "first_token_ms": None, "total_ms": None}

        def trace(step: str, t_start: float, t_end: float, call: CallRecord | None = None, **details) -> None:
            rec = {"type": "step", "request_id": rid, "step": step, "start_ms": ms(t_start), "end_ms": ms(t_end),
                   "duration_ms": round((t_end - t_start) * 1000, 1)}
            if call is not None:
                rec.update(wait_ms=call.wait_ms, retry_ms=call.retry_ms, work_ms=call.work_ms,
                           model=call.model, outcome=call.outcome, status=call.status, retries=call.retries,
                           max_tokens=call.max_tokens, reasoning_effort=call.reasoning_effort,
                           tokens_in=call.tokens_in, tokens_out=call.tokens_out,
                           reasoning_tokens=call.reasoning_tokens, finish_reason=call.finish_reason,
                           model_first_token_ms=call.first_token_ms, server_timings_s=call.server_timings_s,
                           ratelimit_headers=call.headers, attempts=[asdict(a) for a in call.attempts],
                           error=call.error)
            else:
                rec.update(wait_ms=0.0, retry_ms=0.0, work_ms=rec["duration_ms"])
            rec.update(details)
            steps.append(rec)
            self.traces.write(rec)

        async def model_step(step: str, model: str, messages: list[dict], max_tokens: int, effort: str,
                             details_fn: Callable[[CallRecord], dict] | None = None):
            ts = self.clock()
            stream = self.client.stream_chat(model, messages, max_tokens, effort, self.cfg.call_timeout_s)
            in_progress.update(step=step, ts=ts, record=stream.record)
            call = await stream.collect()     # drafts are buffered: nothing reaches the user before the check
            in_progress.clear()
            calls.append(call)
            te = self.clock()
            extra = details_fn(call) if details_fn else {}   # computed before the trace line is written
            trace(step, ts, te, call, prompt_chars=sum(len(m["content"]) for m in messages),
                  text=call.text, **extra)
            return call

        async def stream_to_user(text: str, outcome: str) -> None:
            ts = self.clock()
            first = None
            for piece in re.findall(r"\S+\s*", text):
                if first is None:
                    first = self.clock()
                if sink is not None:
                    r = sink(piece)
                    if inspect.isawaitable(r):
                        await r
                if self.cfg.stream_delay_s:
                    await asyncio.sleep(self.cfg.stream_delay_s)
            te = self.clock()
            out.update(outcome=outcome, text=text, first_token_ms=ms(first) if first is not None else None,
                       total_ms=ms(te))
            trace("stream", ts, te, outcome=outcome, status=OUTCOME_TO_STATUS[outcome], chars=len(text),
                  first_token_ms=out["first_token_ms"], answer=text)

        def done(route=None) -> dict:
            return self._finish(rid, scenario, start_time, calls, steps, out, route=route)

        async def body() -> dict:
            try:
                # a) route: decides in/out of scope only
                def route_details(c: CallRecord) -> dict:
                    parsed = parse_router(c.text) if c.ok else None
                    # router unusable (error, 429 or bad JSON): carry on as in scope
                    route = parsed or {"keywords": [], "papers": [], "in_scope": True}
                    overridden = False
                    if not route["in_scope"] and names_paper_topic(question):
                        route = {**route, "in_scope": True}      # deterministic guard over the 20b router
                        overridden = True
                    return {"route": route, "router_fallback": parsed is None,
                            "router_overridden": overridden}     # keywords and papers: logged, not used

                await model_step("route", self.cfg.router_model, router_messages(question),
                                 self.cfg.router_max_tokens, self.cfg.router_effort, details_fn=route_details)
                route = steps[-1]["route"]
                if not route["in_scope"]:
                    await stream_to_user(OUT_OF_SCOPE, "refused_out_of_scope")
                    return done(route)

                # b) retrieve: BM25 tool call on the question as is, with a timeout
                ts = self.clock()
                try:
                    hits = await asyncio.wait_for(asyncio.to_thread(self.tool.search, question),
                                                  timeout=self.cfg.retrieval_timeout_s)
                except asyncio.TimeoutError:
                    trace("retrieve", ts, self.clock(), tool=self.tool.name, setting=self.tool.setting, query=question,
                          timed_out=True, timeout_s=self.cfg.retrieval_timeout_s)
                    await stream_to_user(SEARCH_PROBLEM, "tool_timeout")
                    return done(route)
                trace("retrieve", ts, self.clock(), tool=self.tool.name, setting=self.tool.setting, query=question,
                      timed_out=False, hits=[{"n": i, "chunk_id": h.chunk.chunk_id, "citation": h.chunk.citation(),
                                              "paper": h.chunk.paper_id, "page_start": h.chunk.page_start,
                                              "page_end": h.chunk.page_end,
                                              "score": round(h.score, 3), "tokens": h.chunk.n_tokens}
                                             for i, h in enumerate(hits, 1)])

                # c) draft
                call = await model_step("draft", self.cfg.draft_model, draft_messages(question, hits),
                                        self.cfg.draft_max_tokens, self.cfg.draft_effort)
                if not call.ok:
                    outcome = call_failure_outcome(call)
                    await stream_to_user(failure_reply(call, hits if outcome == "rate_limited_daily" else None),
                                         outcome)
                    return done(route)

                # d) check, at most one redraft
                ts = self.clock()
                chk = check_answer(call.text, hits, call.finish_reason)
                trace("check", ts, self.clock(), **asdict(chk))
                if not chk.ok:
                    call = await model_step("redraft", self.cfg.draft_model,
                                            redraft_messages(question, hits, call.text, chk.errors),
                                            self.cfg.draft_max_tokens, self.cfg.draft_effort)
                    if not call.ok:
                        await stream_to_user(failure_reply(call, hits), call_failure_outcome(call))
                        return done(route)
                    ts = self.clock()
                    chk = check_answer(call.text, hits, call.finish_reason)
                    trace("recheck", ts, self.clock(), **asdict(chk))
                    if not chk.ok:
                        await stream_to_user(render_passages(hits), "refused_check_failed")
                        return done(route)

                # e) stream the checked answer
                if chk.refusal and not chk.cited:
                    await stream_to_user(REFUSAL, "refused")
                else:
                    await stream_to_user(render_answer(call.text, hits, chk.cited), "answered")
                return done(route)
            except Exception as e:  # still exactly one row per request
                self.traces.write({"type": "note", "request_id": rid, "note": f"exception: {type(e).__name__}: {e}"})
                if out["first_token_ms"] is None:
                    try:
                        await stream_to_user(SERVICE_PROBLEM.format(why="internal error"), "error")
                    except Exception:
                        pass
                out["outcome"] = "error"
                return done()

        if give_up_s is None:
            return await body()
        try:
            return await asyncio.wait_for(body(), give_up_s)
        except asyncio.TimeoutError:
            # the user stopped waiting before the first token: work in progress is cancelled
            out.update(outcome="user_gave_up", text="", first_token_ms=None, total_ms=ms(self.clock()))
            self.traces.write({"type": "note", "request_id": rid, "step": "give_up",
                               "note": f"user gave up: no first token within {give_up_s:g} s",
                               "at_ms": out["total_ms"]})
            if in_progress:   # the call the user gave up on: its attempts so far (429s, waits) still go to the trace
                rec = in_progress["record"]
                rec.outcome = "cancelled"
                trace(in_progress["step"], in_progress["ts"], self.clock(), rec, cancelled=True,
                      attempts_so_far=len(rec.attempts))
                calls.append(rec)   # its retries count; tokens are unknown (None -> 0)
            route = next((st.get("route") for st in steps if st["step"] == "route"), None)
            return done(route)

    def _finish(self, rid: str, scenario: str, start_time: str, calls: list[CallRecord], steps: list[dict],
                out: dict, route: dict | None = None) -> dict:
        status = OUTCOME_TO_STATUS[out["outcome"]]
        row = {
            "request_id": rid, "scenario": scenario, "source": self.client.source, "start_time": start_time,
            "first_token_ms": out["first_token_ms"], "total_ms": out["total_ms"], "status": status,
            "retries": sum(c.retries for c in calls),
            "tokens_in": sum(c.tokens_in or 0 for c in calls), "tokens_out": sum(c.tokens_out or 0 for c in calls),
            "retrieval_setting": self.tool.setting, "answer_grade": "",
        }
        self.results.write(row)
        by_step = {s["step"]: s for s in steps}
        self.traces.write({"type": "request", "request_id": rid, "scenario": scenario, "row": row,
                           "outcome": out["outcome"], "route": route, "steps": [s["step"] for s in steps],
                           "time_split_ms": {k: round(sum(s[k] for s in steps), 1)
                                             for k in ("wait_ms", "retry_ms", "work_ms")},
                           "step_ms": {k: v["duration_ms"] for k, v in by_step.items()}})
        return {"request_id": rid, "status": status, "outcome": out["outcome"], "answer": out["text"],
                "row": row, "calls": calls}
