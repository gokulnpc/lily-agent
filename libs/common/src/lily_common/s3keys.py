"""Raw-HTML S3 key scheme (D12). The contract between fetcher (write) and parser
(read) — both derive the same key from (page_type, url, date), so neither hard-
codes paths. Bucket versioning preserves history per key.

    raw/{page_type}/dt={YYYY-MM-DD}/{sha256(url)}.html
"""

from __future__ import annotations

import hashlib
from datetime import date

PAGE_TYPES = frozenset({"part", "model", "section", "symptom", "guide", "category", "other"})


def url_digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def raw_key(page_type: str, url: str, fetched_on: date) -> str:
    if page_type not in PAGE_TYPES:
        raise ValueError(f"unknown page_type {page_type!r}")
    return f"raw/{page_type}/dt={fetched_on.isoformat()}/{url_digest(url)}.html"
