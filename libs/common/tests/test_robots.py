"""Robots compliance, fully offline — the fetch is mocked with a string."""

from __future__ import annotations

import pytest

from lily_common.robots import RobotsCache

# Trimmed real PartSelect robots.txt: the `*` group is all prefix/exact rules
# (the only wildcard rule, /Models/*/Parts/, lives under named-bot groups, which
# don't apply to us — we cover it via the glob denylist instead).
ROBOTS = """
User-agent: *
Disallow: /search/
Disallow: /shopping-cart/
Disallow: /MultiModels.aspx
"""


def cache(body: str = ROBOTS, ua: str = "LilyResearchBot") -> RobotsCache:
    calls: list[str] = []

    def fetcher(url: str) -> str:
        calls.append(url)
        return body

    c = RobotsCache(fetcher=fetcher, user_agent=ua)
    c._calls = calls  # type: ignore[attr-defined]
    return c


def test_allows_part_and_model_pages() -> None:
    c = cache()
    assert c.allowed("https://www.partselect.com/PS11752778-Door-Bin.htm")
    assert c.allowed("https://www.partselect.com/Models/WDT780SAEM1/")


def test_blocks_disallowed_paths() -> None:
    c = cache()
    assert not c.allowed("https://www.partselect.com/search/foo")
    assert not c.allowed("https://www.partselect.com/shopping-cart/")
    assert not c.allowed("https://www.partselect.com/MultiModels.aspx")


def test_glob_denylist_blocks_models_parts() -> None:
    # Mid-path wildcard the stdlib parser can't honor — covered by the glob
    # denylist (default includes */Models/*/Parts/*).
    c = cache()
    assert not c.allowed("https://www.partselect.com/Models/WDT780SAEM1/Parts/")
    # A custom denylist also works and is checked before the network fetch.
    c2 = RobotsCache(
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError("should not fetch")),
        user_agent="Bot",
        extra_disallow_globs=("*/secret/*",),
    )
    assert not c2.allowed("https://www.partselect.com/secret/x")


def test_robots_fetched_once_per_host() -> None:
    c = cache()
    c.allowed("https://www.partselect.com/PS1.htm")
    c.allowed("https://www.partselect.com/PS2.htm")
    assert c._calls == ["https://www.partselect.com/robots.txt"]  # type: ignore[attr-defined]


def test_missing_robots_allows_all() -> None:
    c = cache(body="")  # 404 -> empty body -> permissive
    assert c.allowed("https://www.partselect.com/anything")


def test_transient_failure_propagates() -> None:
    def boom(url: str) -> str:
        raise ConnectionError("5xx")

    c = RobotsCache(fetcher=boom, user_agent="LilyResearchBot")
    with pytest.raises(ConnectionError):
        c.allowed("https://www.partselect.com/PS1.htm")
