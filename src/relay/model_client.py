"""One async interface to chat models, with all retry logic in one place.

    stream = client.stream_chat(model, messages, max_tokens, reasoning_effort, timeout)
    async for token in stream:      # visible content tokens, as they arrive
        ...
    rec = stream.record             # CallRecord: timings, status, headers, usage, retries
    # or: rec = await stream.collect()

Clients:
    GroqClient   real Groq API (streamed SSE), adapted from scripts/calibrate.py Runner.call
    FakeClient   scripted replies, delays, failures and 429s, for tests; never touches the network

Retry policy (docs/DECISIONS.md, "Retry policy" and "Retries (Step 5b)"), implemented ONLY in ModelClient._run:
    * retries happen only before any token was received, and never past the call's timeout;
    * 429 with body error.type "requests": wait retry-after measured from the LAST ACCEPTED request to
      that model (the request window refills from accepted requests; a 429 consumes nothing);
      with no accepted request yet, from now;
    * 429 with body error.type "tokens" (or any other/unknown type): wait retry-after measured from now
      (the token bucket refills continuously);
    * jitter is uniform in [0, jitter_s] and only ever ADDED on top of a wait, never subtracted;
    * a 429 wait is shared per model (RateGate): every call to that model holds until the gate opens;
    * at most max_retries (3) retries for 429s;
    * 500/502/503/498: retry once, after the same jitter only;
    * a client timeout is never retried; nor are network errors, errors inside a stream, or other statuses.

Timing split of one call (all from the call's start, monotonic clock):
    wait_ms   held by the rate gate before the first attempt
    retry_ms  from the first attempt's start to the final attempt's start (failed attempts + retry waits)
    work_ms   the final attempt (request sent -> last byte)
    so wait_ms + retry_ms + work_ms == total_ms (up to scheduling noise).

The Groq key is read only from .env (GROQ_API_KEY) and is never printed, logged or stored in a record.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Callable, Sequence

ROOT = Path(__file__).resolve().parents[2]
API_URL = "https://api.groq.com/openai/v1/chat/completions"
M120 = "openai/gpt-oss-120b"
M20 = "openai/gpt-oss-20b"


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ------------------------------------------------------------------ records ---

@dataclass
class Attempt:
    n: int
    start_ms: float              # from the call's start
    duration_ms: float
    status: int | None
    retry_after_s: float | None = None
    error: str | None = None
    limit_type: str | None = None


@dataclass
class CallRecord:
    model: str
    max_tokens: int
    reasoning_effort: str | None
    start_time: str                       # UTC ISO, call start
    outcome: str = "pending"              # ok | rate_limited | http_error | network_error | timeout | stream_error
    status: int | None = None             # HTTP status of the final attempt
    retries: int = 0
    wait_ms: float = 0.0
    retry_ms: float = 0.0
    work_ms: float = 0.0
    total_ms: float = 0.0
    first_token_ms: float | None = None   # first visible content token, from the call's start
    first_reasoning_ms: float | None = None
    finish_reason: str | None = None
    text: str = ""
    tokens_in: int | None = None
    tokens_out: int | None = None
    reasoning_tokens: int | None = None
    usage: dict | None = None
    server_timings_s: dict | None = None  # Groq usage queue_time / prompt_time / completion_time / total_time
    headers: dict = field(default_factory=dict)   # x-ratelimit-* and retry-after of the final attempt
    attempts: list[Attempt] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"

    def to_dict(self, include_text: bool = True) -> dict:
        d = asdict(self)
        if not include_text:
            d.pop("text")
        return d


@dataclass
class AttemptResult:
    """What one attempt (one HTTP request) produced; filled by a client's _attempt."""
    status: int | None = None
    headers: dict = field(default_factory=dict)
    retry_after_s: float | None = None
    finish_reason: str | None = None
    usage: dict | None = None
    error: str | None = None
    outcome: str = "ok"
    first_reasoning_s: float | None = None   # perf_counter time of the first reasoning token
    limit_type: str | None = None            # 429 body error.type: "requests" or "tokens"


# ------------------------------------------------------------- retry policy ---

SERVER_ERRORS = frozenset({500, 502, 503, 498})


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3                   # 429 retries per call
    server_error_retries: int = 1          # 500/502/503/498: retry once
    jitter_s: float = 0.25                 # uniform [0, jitter_s], added on top only
    default_retry_after_s: float = 2.0     # a 429 without retry-after: the measured RPM refill (1 per 2.0 s)


class RateGate:
    """Per-model shared state: when the last accepted request started, and when calls may go again."""

    def __init__(self) -> None:
        self.last_accepted: float | None = None
        self.not_before: float = 0.0

    def accepted(self, t: float) -> None:
        self.last_accepted = t if self.last_accepted is None else max(self.last_accepted, t)

    def rate_limited(self, retry_after_s: float, now: float, from_last_accepted: bool) -> None:
        base = self.last_accepted if from_last_accepted and self.last_accepted is not None else now
        self.not_before = max(self.not_before, base + retry_after_s)


class ChatStream:
    """Async iterator over content tokens; .record holds the CallRecord once iteration ends."""

    def __init__(self, gen: AsyncIterator[str], record: CallRecord):
        self._gen, self.record = gen, record

    def __aiter__(self) -> AsyncIterator[str]:
        return self._gen

    async def collect(self) -> CallRecord:
        async for _ in self._gen:
            pass
        return self.record


class ModelClient:
    """Base class. Subclasses implement _attempt (one request, no retries); retries live in _run only."""

    source = "base"
    is_fake = False

    def __init__(self, policy: RetryPolicy = RetryPolicy(), clock: Callable[[], float] = time.perf_counter,
                 sleep: Callable[[float], "asyncio.Future"] = asyncio.sleep, rng: Callable[[], float] = random.random):
        self.policy, self.clock, self.sleep, self.rng = policy, clock, sleep, rng
        self.gates: dict[str, RateGate] = defaultdict(RateGate)

    def stream_chat(self, model: str, messages: Sequence[dict], max_tokens: int,
                    reasoning_effort: str | None = "low", timeout: float = 60.0) -> ChatStream:
        rec = CallRecord(model=model, max_tokens=max_tokens, reasoning_effort=reasoning_effort, start_time=utc_iso())
        return ChatStream(self._run(rec, list(messages), timeout), rec)

    async def _run(self, rec: CallRecord, messages: list[dict], timeout: float) -> AsyncIterator[str]:
        """The one and only retry loop."""
        t0 = self.clock()
        deadline = t0 + timeout
        gate = self.gates[rec.model]
        first_start: float | None = None
        ms = lambda t: round((t - t0) * 1000, 1)  # noqa: E731
        server_retries = 0
        own_wake: float | None = None      # this call's own wait after a server error (not shared)
        while True:
            now = self.clock()
            wake = None
            if gate.not_before > now:
                wake = gate.not_before + self.rng() * self.policy.jitter_s   # jitter on top only
            if own_wake is not None:
                wake = max(wake or 0.0, own_wake)
                own_wake = None
            if wake is not None and wake > now:
                if wake >= deadline:  # give up: waiting would pass the call's timeout
                    last = rec.attempts[-1] if rec.attempts else None
                    rec.outcome = "rate_limited" if last is None or last.status == 429 else "http_error"
                    rec.error = f"next attempt {wake - now:.2f} s from now, past the {timeout:g} s timeout"
                    if last is not None:
                        rec.status, rec.work_ms = last.status, last.duration_ms
                        rec.retry_ms = round((now - first_start) * 1000 - last.duration_ms, 1)
                    else:
                        rec.wait_ms = ms(now)
                    break
                # "at least": the event loop's timer is coarse on Windows (~15.6 ms) and can wake early,
                # so sleep again until the precise clock has really passed the wake time
                while self.clock() < wake:
                    await self.sleep(max(wake - self.clock(), 0.001))
            t_att = self.clock()
            if first_start is None:
                first_start = t_att
                rec.wait_ms = ms(t_att)
            res = AttemptResult()
            got_token = False
            async for tok in self._attempt(rec.model, messages, rec.max_tokens, rec.reasoning_effort, deadline, res):
                if not got_token:
                    got_token = True
                    rec.first_token_ms = ms(self.clock())
                rec.text += tok
                yield tok
            t_end = self.clock()
            rec.attempts.append(Attempt(len(rec.attempts) + 1, ms(t_att), round((t_end - t_att) * 1000, 1),
                                        res.status, res.retry_after_s, res.error, res.limit_type))
            if res.status == 200:
                gate.accepted(t_att)
            rate_retries = rec.retries - server_retries
            if (res.status == 429 and not got_token and rate_retries < self.policy.max_retries
                    and self.clock() < deadline):
                ra = res.retry_after_s if res.retry_after_s is not None else self.policy.default_retry_after_s
                # "requests" limit: the window refills from accepted requests -> measure from the last one.
                # "tokens" limit (or unknown type): the token bucket refills continuously -> measure from now.
                gate.rate_limited(ra, self.clock(), from_last_accepted=(res.limit_type == "requests"))
                rec.retries += 1
                continue
            if (res.status in SERVER_ERRORS and not got_token and server_retries < self.policy.server_error_retries
                    and self.clock() < deadline):
                own_wake = self.clock() + self.rng() * self.policy.jitter_s   # same jitter, nothing else
                server_retries += 1
                rec.retries += 1
                continue
            # anything else is final: 200, 4xx, a client timeout (never retried), a network/stream error
            # final attempt
            rec.status, rec.headers, rec.finish_reason = res.status, res.headers, res.finish_reason
            rec.outcome = "rate_limited" if res.status == 429 else res.outcome
            rec.error = res.error
            rec.work_ms = round((t_end - t_att) * 1000, 1)
            rec.retry_ms = round((t_att - first_start) * 1000, 1)
            if res.first_reasoning_s is not None:
                rec.first_reasoning_ms = ms(res.first_reasoning_s)
            if res.usage:
                rec.usage = res.usage
                rec.tokens_in = res.usage.get("prompt_tokens")
                rec.tokens_out = res.usage.get("completion_tokens")
                rec.reasoning_tokens = (res.usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
                rec.server_timings_s = {k: res.usage[k] for k in
                                        ("queue_time", "prompt_time", "completion_time", "total_time")
                                        if k in res.usage} or None
            break
        rec.total_ms = ms(self.clock())

    async def _attempt(self, model: str, messages: list[dict], max_tokens: int, reasoning_effort: str | None,
                       deadline: float, res: AttemptResult) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""  # pragma: no cover

    async def aclose(self) -> None:
        pass


def _retry_after(headers: dict) -> float | None:
    v = headers.get("retry-after")
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


# --------------------------------------------------------------------- Groq ---

def load_key(env_path: Path = ROOT / ".env") -> str:
    if not env_path.exists():
        raise SystemExit("No .env file in the repo root (key not found; nothing was sent).")
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("GROQ_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if value:
                return value
    raise SystemExit("GROQ_API_KEY is missing or empty in .env (nothing was sent).")


class GroqClient(ModelClient):
    """Real Groq calls. Same request body and SSE parsing as scripts/calibrate.py (temperature 0,
    stream, max_completion_tokens, reasoning_effort; usage read from x_groq)."""

    source = "real"

    def __init__(self, key: str | None = None, temperature: float = 0.0, **kw):
        super().__init__(**kw)
        self._key = key or load_key()
        self.temperature = temperature
        self._http = None

    def __repr__(self) -> str:  # never show the key
        return f"GroqClient(temperature={self.temperature})"

    async def _client(self):
        import httpx
        if self._http is None:
            self._http = httpx.AsyncClient(http2=False)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _attempt(self, model, messages, max_tokens, reasoning_effort, deadline, res):
        import httpx
        body = {"model": model, "messages": messages, "stream": True, "max_completion_tokens": max_tokens,
                "temperature": self.temperature}
        if reasoning_effort:
            body["reasoning_effort"] = reasoning_effort
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                   "User-Agent": "relay/0.1"}
        remaining = max(0.1, deadline - self.clock())
        http = await self._client()
        try:
            async with http.stream("POST", API_URL, json=body, headers=headers,
                                   timeout=httpx.Timeout(remaining, connect=min(10.0, remaining))) as r:
                res.status = r.status_code
                res.headers = {k.lower(): v for k, v in r.headers.items()
                               if k.lower().startswith("x-ratelimit-") or k.lower() == "retry-after"}
                res.retry_after_s = _retry_after(res.headers)
                if r.status_code != 200:
                    raw = (await r.aread()).decode("utf-8", errors="replace")
                    res.outcome = "http_error"
                    res.error = re.sub(r"org_[A-Za-z0-9]+", "org_REDACTED", raw)[:500]
                    try:
                        res.limit_type = (json.loads(raw).get("error") or {}).get("type")
                    except (ValueError, AttributeError):
                        res.limit_type = None
                    return
                async for line in r.aiter_lines():
                    if self.clock() > deadline:
                        res.outcome, res.error = "timeout", "call timeout while streaming"
                        return
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    if "error" in chunk:
                        res.outcome, res.error = "stream_error", json.dumps(chunk["error"])[:500]
                    for ch in chunk.get("choices", []):
                        d = ch.get("delta") or {}
                        if (d.get("reasoning") or d.get("reasoning_content")) and res.first_reasoning_s is None:
                            res.first_reasoning_s = self.clock()
                        if d.get("content"):
                            yield d["content"]
                        if ch.get("finish_reason"):
                            res.finish_reason = ch["finish_reason"]
                    if chunk.get("usage"):
                        res.usage = chunk["usage"]
                    xg = chunk.get("x_groq") or {}
                    if xg.get("usage"):
                        res.usage = xg["usage"]
        except httpx.TimeoutException as e:
            res.outcome, res.error = "timeout", f"{type(e).__name__}"
        except httpx.HTTPError as e:
            res.outcome, res.error = "network_error", f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------- Fake ---

@dataclass
class FakeReply:
    """One scripted attempt. Delays are real asyncio sleeps (keep them small in tests)."""
    text: str = ""
    status: int = 200
    retry_after_s: float | None = None
    headers_delay_s: float = 0.0     # before the response starts (queue + prefill)
    token_delay_s: float = 0.0       # between content tokens
    finish_reason: str = "stop"
    tokens_in: int = 100
    reasoning_tokens: int = 0
    queue_time_s: float = 0.0
    stall: bool = False              # never responds: the call times out
    network_error: bool = False
    limit_type: str = "requests"     # 429 body error.type: "requests" or "tokens"


class FakeClient(ModelClient):
    """Scripted model. `script` maps model -> list of FakeReply, consumed one per attempt
    (a 429 retry consumes the next reply), or is a callable (model, messages, attempt_index) -> FakeReply.

    `source` must be a valid results.csv source label ("real" or "stand-in"); there is no "fake" value.
    Pipeline refuses to write a FakeClient run to any results file inside the repo's results/ directory,
    so fake rows only ever land in a temporary directory (tests)."""

    is_fake = True

    def __init__(self, script: dict[str, list[FakeReply]] | Callable[[str, list, int], FakeReply],
                 source: str = "stand-in", **kw):
        super().__init__(**kw)
        self.source = source
        self.script = script
        self.calls: list[dict] = []   # every attempt: model, messages, max_tokens, reasoning_effort

    def _next(self, model: str, messages: list) -> FakeReply:
        n = sum(1 for c in self.calls if c["model"] == model)
        if callable(self.script):
            return self.script(model, messages, n)
        replies = self.script.get(model) or []
        if n >= len(replies):
            raise AssertionError(f"FakeClient: no scripted reply #{n + 1} for {model}")
        return replies[n]

    async def _attempt(self, model, messages, max_tokens, reasoning_effort, deadline, res):
        reply = self._next(model, messages)
        self.calls.append({"model": model, "messages": messages, "max_tokens": max_tokens,
                           "reasoning_effort": reasoning_effort})

        async def wait(s: float) -> bool:
            """Sleep s seconds unless that passes the deadline; False means timed out."""
            left = deadline - self.clock()
            if s >= left:
                await self.sleep(max(0.0, left))
                res.outcome, res.error = "timeout", "call timeout (fake)"
                return False
            await self.sleep(s)
            return True

        if reply.stall:
            await wait(float("inf"))
            return
        if reply.network_error:
            res.outcome, res.error = "network_error", "ConnectError: scripted"
            return
        if not await wait(reply.headers_delay_s):
            return
        res.status = reply.status
        res.headers = {"x-ratelimit-remaining-requests": "999", "x-ratelimit-remaining-tokens": "7000"}
        if reply.status != 200:
            if reply.retry_after_s is not None:
                res.headers["retry-after"] = str(reply.retry_after_s)
            res.retry_after_s = reply.retry_after_s
            res.outcome = "http_error"
            res.error = f"scripted HTTP {reply.status}"
            if reply.status == 429:
                res.limit_type = reply.limit_type
            return
        pieces = re.findall(r"\S+\s*", reply.text)
        if reply.reasoning_tokens:
            res.first_reasoning_s = self.clock()
        for i, p in enumerate(pieces):
            if i and reply.token_delay_s and not await wait(reply.token_delay_s):
                return
            yield p
        res.finish_reason = reply.finish_reason
        out = len(pieces) + reply.reasoning_tokens
        res.usage = {"prompt_tokens": reply.tokens_in, "completion_tokens": out,
                     "total_tokens": reply.tokens_in + out, "queue_time": reply.queue_time_s,
                     "completion_tokens_details": {"reasoning_tokens": reply.reasoning_tokens}}
