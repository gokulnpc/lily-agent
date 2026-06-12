"""Drift-detection contract.

Every parser asserts the page still carries the fields we depend on. A missing
required field raises `SchemaDriftError` — loud, not a silent empty row — so a
PartSelect markup change surfaces as a failed parse + alert (PRD §8 risk,
NFR-18) rather than quietly corrupting the catalog. The raw HTML stays in S3, so
fixing the selector and re-parsing needs no re-crawl.
"""

from __future__ import annotations


class SchemaDriftError(Exception):
    """A required field could not be extracted — the page shape changed."""

    def __init__(self, page_type: str, field: str, url: str = "") -> None:
        self.page_type = page_type
        self.field = field
        self.url = url
        super().__init__(
            f"schema drift on {page_type} page: required field {field!r} missing"
            + (f" ({url})" if url else "")
        )


def require[T](value: T | None, *, page_type: str, field: str, url: str = "") -> T:
    """Return value, or raise SchemaDriftError if it is None/empty."""
    if value is None or (isinstance(value, str) and not value.strip()):
        raise SchemaDriftError(page_type, field, url)
    return value
