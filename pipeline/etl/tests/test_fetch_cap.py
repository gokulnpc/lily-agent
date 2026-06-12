"""The crawl budget must bind at FETCH time, not just at seed time — a regression
guard for the approved-80 / fetched-240 overshoot. _under_fetch_cap is the gate
fetch() consults before every live session.fetch()."""

from __future__ import annotations

from lily_crawler.budget import CrawlBudget
from lily_etl.tools.seed_crawl import _under_fetch_cap


def test_fetch_cap_binds_even_when_overseeded() -> None:
    # 240 part pages pending (the over-seed incident), budget caps parts at 80.
    budget = CrawlBudget(target_models=5, models=5, sections=50, parts=80, symptoms=4)
    fetched: dict[str, int] = {}
    hits = 0
    for _ in range(240):
        if _under_fetch_cap(fetched, "part", budget):
            fetched["part"] = fetched.get("part", 0) + 1
            hits += 1
    assert hits == 80  # exactly the budget is fetched; the other 160 stay pending


def test_fetch_cap_is_per_type() -> None:
    budget = CrawlBudget(target_models=5, models=5, sections=50, parts=80, symptoms=4)
    fetched = {"part": 80}  # parts exhausted...
    assert not _under_fetch_cap(fetched, "part", budget)
    assert _under_fetch_cap(fetched, "model", budget)  # ...models unaffected
    assert _under_fetch_cap(fetched, "section", budget)
