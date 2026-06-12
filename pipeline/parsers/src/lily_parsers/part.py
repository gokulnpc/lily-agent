"""Part page parser. Attributes only — compatibility comes from section pages
(A9 model-canonical). The model cross-reference here is a discovery hint."""

from __future__ import annotations

import json
import re

from lily_parsers import _html
from lily_parsers.contract import require
from lily_parsers.dto import ParsedPart

_PT = "part"
_YT = "https://www.youtube.com/watch?v={}"
_SYMPTOM_HEADER = "fixes the following symptoms"
_APPLIANCES = {"refrigerator", "dishwasher"}


def parse_part(html: str, url: str) -> ParsedPart:
    tree = _html.parse(html)

    ps_number = require(
        _html.first_text(tree, '[itemprop="productID"]'), page_type=_PT, field="ps_number", url=url
    )
    name = require(
        _html.first_text(tree, "h1") or _html.first_text(tree, '[itemprop="name"]'),
        page_type=_PT,
        field="name",
        url=url,
    )
    # appliance_type is NOT reliably in the URL slug — only ~11% of part names
    # contain "Refrigerator"/"Dishwasher" (the live crawl drifted on 214/240).
    # The authoritative source is the structured breadcrumb (position 1); the URL
    # slug is a fallback.
    appliance_type = require(
        _appliance_from_breadcrumb(tree) or _html.appliance_from_url(url),
        page_type=_PT,
        field="appliance_type",
        url=url,
    )

    price_node = tree.css_first('[itemprop="price"]')
    price = _html.to_float(_html.attr(price_node, "content") or _html.text(price_node))

    availability = _html.first_text(tree, '[itemprop="availability"]')
    in_stock = ("in stock" in availability.lower()) if availability else None

    video_id = _html.attr(tree.css_first("[data-yt-init]"), "data-yt-init")

    rating_node = tree.css_first('[itemprop="ratingValue"]')
    rating = _html.to_float(_html.attr(rating_node, "content") or _html.text(rating_node))
    review_node = tree.css_first('[itemprop="reviewCount"]')
    review_count = _html.to_int(_html.attr(review_node, "content") or _html.text(review_node))

    difficulty, install_time = _parse_repair_rating(tree)

    return ParsedPart(
        ps_number=ps_number,
        name=name,
        appliance_type=appliance_type,
        mfr_part_number=_html.first_text(tree, '[itemprop="mpn"]'),
        brand=_html.first_text(tree, '[itemprop="brand"] [itemprop="name"]'),
        price_usd=price,
        stock_status=availability,
        in_stock=in_stock,
        install_difficulty=difficulty,
        install_time=install_time,
        install_video_url=_YT.format(video_id) if video_id else None,
        rating_avg=rating,
        review_count=review_count,
        image_url=_html.attr(tree.css_first('[itemprop="image"]'), "src"),
        symptoms_fixed=_parse_symptoms(tree),
        compatible_model_urls=_model_hints(tree),
    )


def _appliance_from_breadcrumb(tree: _html.Tree) -> str | None:
    # The `js-breadcrumb-data` hidden div carries the canonical breadcrumb as
    # JSON: position 1 is the appliance (e.g. {"position":1,"name":"Dishwasher",
    # ...}). This is unambiguous even when the page links to the other appliance's
    # parts for cross-sell. Verified across GE/Frigidaire/Whirlpool part pages.
    raw = _html.text(tree.css_first(".js-breadcrumb-data"))
    if not raw:
        return None
    try:
        crumbs = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    for crumb in crumbs:
        if crumb.get("position") == 1:
            name = (crumb.get("name") or "").strip().lower()
            return name if name in _APPLIANCES else None
    return None


def _parse_repair_rating(tree: _html.Tree) -> tuple[str | None, str | None]:
    node = tree.css_first(".pd__repair-rating__container")
    if node is None:
        return None, None
    raw = re.sub(r"\s+", " ", node.text(separator=" ", strip=True))
    # e.g. "Really Easy  Less than 15 mins  Rated by verified customers"
    difficulty = re.search(r"(Very Easy|Really Easy|Easy|Difficult|Very Difficult)", raw)
    time_ = re.search(r"((?:Less than\s*)?\d+\s*-?\s*\d*\s*mins?)", raw)
    return (difficulty.group(1) if difficulty else None, time_.group(1).strip() if time_ else None)


def _parse_symptoms(tree: _html.Tree) -> list[str]:
    # "<div class='bold'>This part fixes the following symptoms:</div><ul><li>…"
    for head in tree.css("div.bold"):
        if _SYMPTOM_HEADER in head.text().lower():
            ul = head.next
            while ul is not None and ul.tag != "ul":
                ul = ul.next
            if ul is not None:
                return [t for li in ul.css("li") if (t := _html.text(li))]
    return []


def _model_hints(tree: _html.Tree) -> list[str]:
    urls = []
    seen = set()
    for a in tree.css('a[href*="/Models/"]'):
        href = _html.attr(a, "href")
        if href and "/Models/" in href and href not in seen:
            seen.add(href)
            urls.append(href.split("?")[0])
    return urls
