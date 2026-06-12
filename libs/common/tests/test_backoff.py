from __future__ import annotations

import pytest

from lily_common.backoff import backoff_delay


def test_exponential_ceiling_with_unit_jitter() -> None:
    # default jitter=1.0 -> deterministic ceiling: base*2^(n-1)
    assert backoff_delay(1, base=1.0) == 1.0
    assert backoff_delay(2, base=1.0) == 2.0
    assert backoff_delay(3, base=1.0) == 4.0
    assert backoff_delay(4, base=1.0) == 8.0


def test_capped() -> None:
    assert backoff_delay(10, base=1.0, cap=30.0) == 30.0


def test_full_jitter_scales_ceiling() -> None:
    assert backoff_delay(3, base=1.0, jitter=lambda: 0.5) == 2.0  # 0.5 * 4
    assert backoff_delay(3, base=1.0, jitter=lambda: 0.0) == 0.0


def test_attempt_must_be_positive() -> None:
    with pytest.raises(ValueError):
        backoff_delay(0)
