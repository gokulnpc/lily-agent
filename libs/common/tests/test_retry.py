"""Retry logic, fully offline — sleep is recorded, jitter is deterministic."""

from __future__ import annotations

import pytest

from lily_common.retry import (
    call_with_retry,
    is_aurora_transient,
    is_bedrock_transient,
    with_retry,
)


class Transient(Exception):
    pass


class Fatal(Exception):
    pass


def _retryable(exc: BaseException) -> bool:
    return isinstance(exc, Transient)


class Recorder:
    def __init__(self) -> None:
        self.slept: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.slept.append(seconds)


def test_succeeds_after_transient_failures() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise Transient("resuming")
        return "ok"

    sleep = Recorder()
    result = call_with_retry(flaky, retryable=_retryable, sleep=sleep, jitter=lambda: 1.0, base=2.0)
    assert result == "ok"
    assert calls["n"] == 3
    # Two backoffs before the 3rd success: base*2^0, base*2^1 = 2, 4 (jitter=1.0).
    assert sleep.slept == [2.0, 4.0]


def test_non_retryable_fails_fast() -> None:
    sleep = Recorder()

    def boom() -> None:
        raise Fatal("nope")

    with pytest.raises(Fatal):
        call_with_retry(boom, retryable=_retryable, sleep=sleep)
    assert sleep.slept == []  # never retried, never slept


def test_exhausted_reraises_last() -> None:
    sleep = Recorder()
    calls = {"n": 0}

    def always() -> None:
        calls["n"] += 1
        raise Transient(f"attempt {calls['n']}")

    with pytest.raises(Transient, match="attempt 3"):
        call_with_retry(
            always, retryable=_retryable, max_attempts=3, sleep=sleep, jitter=lambda: 1.0
        )
    assert calls["n"] == 3
    assert len(sleep.slept) == 2  # slept between the 3 attempts, not after the last


def test_decorator_form() -> None:
    sleep = Recorder()
    state = {"n": 0}

    @with_retry(retryable=_retryable, sleep=sleep, jitter=lambda: 0.0)
    def flaky(x: int) -> int:
        state["n"] += 1
        if state["n"] < 2:
            raise Transient("once")
        return x * 2

    assert flaky(21) == 42
    assert state["n"] == 2


# ---- predicates ------------------------------------------------------------


def test_aurora_predicate() -> None:
    import psycopg

    assert is_aurora_transient(psycopg.OperationalError("the database system is starting up"))
    assert not is_aurora_transient(ValueError("unrelated"))
    assert not is_aurora_transient(psycopg.ProgrammingError("bad sql"))


def test_bedrock_predicate() -> None:
    class ClientError(Exception):
        def __init__(self, response: dict[str, object]) -> None:
            self.response = response

    throttle = ClientError({"Error": {"Code": "ThrottlingException"}})
    server = ClientError({"ResponseMetadata": {"HTTPStatusCode": 503}})
    validation = ClientError({"Error": {"Code": "ValidationException"}})
    assert is_bedrock_transient(throttle)
    assert is_bedrock_transient(server)
    assert not is_bedrock_transient(validation)
    assert not is_bedrock_transient(ValueError("no response attr"))
