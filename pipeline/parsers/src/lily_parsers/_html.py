"""Small shared HTML/text helpers for the parsers."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from selectolax.parser import HTMLParser, Node

# Re-exported alias so parsers annotate the tree type from one place.
Tree = HTMLParser

_APPLIANCE_FROM_SLUG = re.compile(r"-(Refrigerator|Dishwasher)-", re.IGNORECASE)
_APPLIANCE_FROM_PATH = re.compile(r"/(Refrigerator|Dishwasher)/", re.IGNORECASE)
_MODEL_FROM_PATH = re.compile(r"/Models/([^/]+)/", re.IGNORECASE)


def parse(html: str) -> HTMLParser:
    return HTMLParser(html)


def text(node: Node | None) -> str | None:
    if node is None:
        return None
    value = node.text(strip=True)
    return value or None


def attr(node: Node | None, name: str) -> str | None:
    if node is None:
        return None
    value = node.attributes.get(name)
    return value or None


def first_text(tree: HTMLParser, selector: str) -> str | None:
    return text(tree.css_first(selector))


def appliance_from_url(url: str) -> str | None:
    m = _APPLIANCE_FROM_SLUG.search(url) or _APPLIANCE_FROM_PATH.search(url)
    return m.group(1).lower() if m else None


def model_from_url(url: str) -> str | None:
    m = _MODEL_FROM_PATH.search(urlsplit(url).path)
    return m.group(1) if m else None


def to_float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def to_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None
