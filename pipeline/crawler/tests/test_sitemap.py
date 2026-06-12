"""Sitemap selection — fully offline; the fetch and robots check are injected."""

from __future__ import annotations

from collections.abc import Callable

from lily_crawler.sitemap import (
    child_sitemaps_for,
    parse_locs,
    select_seed_urls,
)

MASTER = """<?xml version="1.0"?>
<sitemapindex>
  <sitemap><loc>https://x/sitemaps/PartSelect.com_Sitemap_PartDetail_1.xml.gz</loc></sitemap>
  <sitemap><loc>https://x/sitemaps/PartSelect.com_Sitemap_Models_1.xml.gz</loc></sitemap>
  <sitemap><loc>https://x/sitemaps/PartSelect.com_Sitemap_Repairs.xml.gz</loc></sitemap>
  <sitemap><loc>https://x/sitemaps/PartSelect.com_Sitemap_Blogs.xml.gz</loc></sitemap>
</sitemapindex>"""

PARTS = """<urlset>
  <url><loc>https://x/PS11752778-Whirlpool-WPW10321304-Refrigerator-Door-Shelf-Bin.htm</loc></url>
  <url><loc>https://x/PS11746591-Whirlpool-WPW10348269-Dishwasher-Door-Balance-Link-Kit.htm</loc></url>
  <url><loc>https://x/PS99-Whirlpool-Range-Burner.htm</loc></url>
</urlset>"""

REPAIRS = """<urlset>
  <url><loc>https://x/Repair/Refrigerator/Leaking/</loc></url>
  <url><loc>https://x/Repair/Microwave/Sparking/</loc></url>
</urlset>"""

MODELS = """<urlset>
  <url><loc>https://x/Models/WRS325FDAM04/</loc></url>
</urlset>"""


def make_fetch() -> Callable[[str], str]:
    pages = {
        "https://x/sitemaps/PartSelect.com_Sitemap_PartDetail_1.xml.gz": PARTS,
        "https://x/sitemaps/PartSelect.com_Sitemap_Models_1.xml.gz": MODELS,
        "https://x/sitemaps/PartSelect.com_Sitemap_Repairs.xml.gz": REPAIRS,
        "MASTER": MASTER,
    }
    return lambda url: pages.get(url, MASTER)


def test_parse_locs() -> None:
    assert len(parse_locs(MASTER)) == 4
    assert parse_locs(PARTS)[0].endswith("Door-Shelf-Bin.htm")


def test_selects_appliance_parts_and_symptoms_only() -> None:
    seeds, dropped = select_seed_urls(
        master_url="MASTER",
        fetch=make_fetch(),
        robots_allowed=lambda _u: True,
        child_filter=child_sitemaps_for(("PartDetail", "Repairs", "Models")),
    )
    urls = {s.url for s in seeds}
    types = {s.page_type for s in seeds}
    # fridge + dishwasher parts kept; range part dropped (no appliance in slug)
    assert any("Refrigerator-Door-Shelf-Bin" in u for u in urls)
    assert any("Dishwasher-Door-Balance" in u for u in urls)
    assert not any("Range-Burner" in u for u in urls)
    # fridge symptom kept; microwave dropped
    assert any("Repair/Refrigerator/Leaking" in u for u in urls)
    assert not any("Microwave" in u for u in urls)
    # models are NOT seeded here (discovered downstream)
    assert "model" not in types
    assert dropped == 0


def test_blogs_child_excluded_by_filter() -> None:
    seeds, _ = select_seed_urls(
        master_url="MASTER",
        fetch=make_fetch(),
        robots_allowed=lambda _u: True,
        child_filter=child_sitemaps_for(("PartDetail",)),
    )
    assert all(s.page_type == "part" for s in seeds)


def test_robots_filter_excludes_disallowed() -> None:
    seeds, _ = select_seed_urls(
        master_url="MASTER",
        fetch=make_fetch(),
        robots_allowed=lambda url: "Dishwasher" not in url,
        child_filter=child_sitemaps_for(("PartDetail",)),
    )
    assert not any("Dishwasher" in s.url for s in seeds)


def test_cap_is_hard_stop_and_reports_drops() -> None:
    seeds, dropped = select_seed_urls(
        master_url="MASTER",
        fetch=make_fetch(),
        robots_allowed=lambda _u: True,
        cap=1,
        child_filter=child_sitemaps_for(("PartDetail", "Repairs")),
    )
    assert len(seeds) == 1
    assert dropped >= 1  # truncation is reported, not silent
