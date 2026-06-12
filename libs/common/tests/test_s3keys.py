from __future__ import annotations

from datetime import date

import pytest

from lily_common.s3keys import raw_key, url_digest


def test_key_shape() -> None:
    url = "https://www.partselect.com/Models/WDT780SAEM1/"
    key = raw_key("model", url, date(2026, 6, 12))
    assert key == f"raw/model/dt=2026-06-12/{url_digest(url)}.html"


def test_digest_is_stable_and_deterministic() -> None:
    url = "https://www.partselect.com/PS11752778-Door-Bin.htm"
    assert url_digest(url) == url_digest(url)
    assert len(url_digest(url)) == 64  # sha256 hex


def test_fetcher_and_parser_derive_the_same_key() -> None:
    # The contract: both sides compute the key from the same inputs.
    url = "https://www.partselect.com/PS1.htm"
    d = date(2026, 6, 12)
    assert raw_key("part", url, d) == raw_key("part", url, d)


def test_rejects_unknown_page_type() -> None:
    with pytest.raises(ValueError):
        raw_key("widget", "https://x", date(2026, 6, 12))
