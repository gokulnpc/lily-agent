"""Section page parser — the authoritative compatibility source (A9). Every
part in this section fits the section's model: each yields a (part, model) pair."""

from __future__ import annotations

import re

from lily_parsers import _html
from lily_parsers.contract import require
from lily_parsers.dto import CompatPair, ParsedSection

_PT = "section"
_PS_RX = re.compile(r"/(PS\d+)-", re.IGNORECASE)


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

    # A section with zero parts is a drift signal (the block selector broke),
    # not a legitimately empty section.
    require(pairs or None, page_type=_PT, field="parts", url=url)
    return ParsedSection(model_number=model_number, parts=pairs)
