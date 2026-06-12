"""Model page parser. Identity + the section-page URLs that lead to the
complete, authoritative parts list (A9 model-canonical completeness)."""

from __future__ import annotations

import re

from lily_parsers import _html
from lily_parsers.contract import require
from lily_parsers.dto import ParsedModel

_PT = "model"
# "Whirlpool Refrigerator WRS325FDAM04 - OEM Parts & Repair Help - PartSelect.com"
_TITLE_RX = re.compile(r"^(.*?)\s+(Refrigerator|Dishwasher)\s+(\S+)\s*-", re.IGNORECASE)


def parse_model(html: str, url: str) -> ParsedModel:
    tree = _html.parse(html)

    model_number = require(_html.model_from_url(url), page_type=_PT, field="model_number", url=url)
    title = require(_html.first_text(tree, "title"), page_type=_PT, field="title", url=url)
    m = _TITLE_RX.match(title)
    brand = require(m.group(1).strip() if m else None, page_type=_PT, field="brand", url=url)
    appliance_type = m.group(2).lower() if m else None
    appliance_type = require(appliance_type, page_type=_PT, field="appliance_type", url=url)

    sections = _section_urls(tree)
    require(sections or None, page_type=_PT, field="section_urls", url=url)

    return ParsedModel(
        model_number=model_number,
        brand=brand,
        appliance_type=appliance_type,
        name=f"{brand} {appliance_type.capitalize()}",
        section_urls=sections,
    )


def _section_urls(tree: _html.Tree) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for a in tree.css('a[href*="/Sections/"]'):
        href = _html.attr(a, "href")
        if href and "/Sections/" in href and href not in seen:
            seen.add(href)
            urls.append(href)  # keep query string — sections 500 without it
    return urls
