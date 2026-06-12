"""Section page parser — the authoritative compatibility source (A9). Every
part in this section fits the section's model: each yields a (part, model) pair."""

from __future__ import annotations

import re

from lily_parsers import _html
from lily_parsers.contract import require
from lily_parsers.dto import CompatPair, ParsedSection

_PT = "section"
_PS_RX = re.compile(r"/(PS\d+)-", re.IGNORECASE)
_SECTION_SLUG_RX = re.compile(r"/Sections/([^/?]+)", re.IGNORECASE)

# Sections that are schematic/overview pages with no parts list — confirmed
# against the first live crawl. Treated as legitimately empty (no compat pairs),
# NOT drift. Genuine parts sections with a broken selector still alert.
KNOWN_EMPTY_SECTIONS = frozenset({"cover-sheet"})


def _section_slug(url: str) -> str | None:
    m = _SECTION_SLUG_RX.search(url)
    return m.group(1).lower() if m else None


def parse_section(html: str, url: str) -> ParsedSection:
    tree = _html.parse(html)

    model_number = require(_html.model_from_url(url), page_type=_PT, field="model_number", url=url)

    pairs: list[CompatPair] = []
    seen: set[str] = set()
    for block in tree.css(".js-mega-m-part"):
        link = block.css_first('a[href*="/PS"]')
        href = _html.attr(link, "href")
        if not href:
            continue
        m = _PS_RX.search(href)
        if not m:
            continue
        ps = m.group(1).upper()
        if ps in seen:
            continue
        seen.add(ps)
        pairs.append(CompatPair(ps_number=ps, part_name=_html.attr(block, "data-name") or ""))

    # A zero-part section is drift (the block selector broke) UNLESS it's a
    # known schematic/overview section (e.g. Cover-Sheet) that legitimately
    # lists no parts. Drift detection stays strict for genuine parts sections.
    if _section_slug(url) not in KNOWN_EMPTY_SECTIONS:
        require(pairs or None, page_type=_PT, field="parts", url=url)
    return ParsedSection(model_number=model_number, parts=pairs)
