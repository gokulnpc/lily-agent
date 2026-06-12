"""Sitemap-driven seed discovery (D13 scope control).

Discovery is anchored to the published sitemap, never link-walking, so the
crawler cannot wander. The selector is pure (the sitemap fetch and robots check
are injected) and enforces the seed cap as a hard stop — reaching it logs what
was dropped rather than silently truncating.

Model sitemap URLs are not appliance-tagged (`/Models/{n}/` reveals nothing),
so models are NOT seeded here; they are discovered downstream from the
compatible-model references on seeded part pages (bounded, same-appliance,
counted against the same cap). Part URLs ARE appliance-classifiable from their
slug, and repair/symptom URLs from their path — those are what we seed.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from lily_crawler.urls import classify, in_scope_appliance

_LOC_RX = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)

# A part slug names its appliance, e.g. PS…-Refrigerator-Door-Shelf-Bin.htm
_PART_APPLIANCE_RX = re.compile(r"-(Refrigerator|Dishwasher)-", re.IGNORECASE)

SitemapFetcher = Callable[[str], str]  # returns decompressed XML text
RobotsAllowed = Callable[[str], bool]


@dataclass(frozen=True)
class SeedUrl:
    url: str
    page_type: str


def parse_locs(xml: str) -> list[str]:
    """Extract <loc> entries — works for both a sitemap index and a urlset."""
    return [m.group(1) for m in _LOC_RX.finditer(xml)]


def _appliance_scoped(url: str, page_type: str) -> bool:
    if page_type == "part":
        return bool(_PART_APPLIANCE_RX.search(url))
    if page_type in ("symptom", "category"):
        return in_scope_appliance(url)
    return False


def select_seed_urls(
    *,
    master_url: str,
    fetch: SitemapFetcher,
    robots_allowed: RobotsAllowed,
    cap: int = 500,
    child_filter: Callable[[str], bool] = lambda _u: True,
) -> tuple[list[SeedUrl], int]:
    """Walk the sitemap index → child sitemaps → page URLs.

    Returns (seeds, dropped_for_cap). Each URL is kept only if it is an
    appliance-scoped part/symptom/category page AND robots-allowed. Stops
    fetching children once the cap is reached.
    """
    children = [c for c in parse_locs(fetch(master_url)) if child_filter(c)]
    seeds: list[SeedUrl] = []
    seen: set[str] = set()
    dropped = 0

    for child in children:
        if len(seeds) >= cap:
            dropped += 1  # at least one child sitemap left unprocessed
            continue
        for url in parse_locs(fetch(child)):
            if url in seen:
                continue
            page_type = classify(url)
            if not _appliance_scoped(url, page_type):
                continue
            if not robots_allowed(url):
                continue
            seen.add(url)
            if len(seeds) >= cap:
                dropped += 1
                continue
            seeds.append(SeedUrl(url=url, page_type=page_type))

    return seeds, dropped


def child_sitemaps_for(names: Iterable[str]) -> Callable[[str], bool]:
    """A child_filter keeping only sitemaps whose URL contains one of `names`
    (e.g. {"PartDetail", "Repairs"})."""
    wanted = tuple(names)
    return lambda url: any(name in url for name in wanted)
