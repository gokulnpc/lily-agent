"""Repair index parser: the symptom list for an appliance, each with its
'reported by' frequency. Symptom→part detail comes from the detail pages."""

from __future__ import annotations

import re

from lily_parsers import _html
from lily_parsers.contract import require
from lily_parsers.dto import ParsedSymptomIndex, SymptomRef

_PT = "category"  # the repair index is classified 'category'
_SYMPTOM_HREF = re.compile(r"^/Repair/(Refrigerator|Dishwasher)/[^/]+/$", re.IGNORECASE)


def parse_symptom_index(html: str, url: str) -> ParsedSymptomIndex:
    tree = _html.parse(html)
    appliance_type = require(
        _html.appliance_from_url(url), page_type=_PT, field="appliance_type", url=url
    )

    symptoms: list[SymptomRef] = []
    seen: set[str] = set()
    for a in tree.css('a[href*="/Repair/"]'):
        href = _html.attr(a, "href")
        if not href or not _SYMPTOM_HREF.match(href) or href in seen:
            continue
        title = _html.text(a.css_first(".title-md"))
        if not title:
            continue
        seen.add(href)
        pct_node = a.css_first(".symptom-list__reported-by")
        pct = _html.to_float(pct_node.text()) if pct_node else None
        symptoms.append(SymptomRef(name=title, url=href, reported_by_pct=pct))

    require(symptoms or None, page_type=_PT, field="symptoms", url=url)
    return ParsedSymptomIndex(appliance_type=appliance_type, symptoms=symptoms)
