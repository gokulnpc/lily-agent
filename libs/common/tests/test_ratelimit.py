"""Token bucket with a fake clock — no sleeping."""

from __future__ import annotations

import pytest

from lily_common.ratelimit import TokenBucket


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_initial_capacity_grants_immediately() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate_per_sec=0.2, capacity=2, clock=clock)
    assert bucket.take() == 0.0
    assert bucket.take() == 0.0  # capacity = 2


def test_third_take_must_wait_for_refill() -> None:
    clock = FakeClock()
    # 0.2/s => one token every 5s
    bucket = TokenBucket(rate_per_sec=0.2, capacity=2, clock=clock)
    bucket.take()
    bucket.take()
    wait = bucket.take()
    assert wait == pytest.approx(5.0)


def test_refill_after_elapsed_time() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate_per_sec=1.0, capacity=1, clock=clock)
    assert bucket.take() == 0.0
    clock.advance(1.0)  # one token refilled
    assert bucket.take() == 0.0


def test_refill_capped_at_capacity() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate_per_sec=1.0, capacity=2, clock=clock)
    clock.advance(100.0)  # would overflow without the cap
    assert bucket.take() == 0.0
    assert bucket.take() == 0.0
    assert bucket.take() == pytest.approx(1.0)  # only 2 accrued


def test_rejects_nonpositive_params() -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=0, capacity=1, clock=FakeClock())
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=1, capacity=0, clock=FakeClock())
