"""Route a fetched page to its parser by source_pages.page_type.

The ETL worker pulls (url, page_type, raw HTML from S3) and calls parse(); the
returned DTO is mapped to Aurora rows. Parsers never fetch — input is the stored
S3 body, so a parser fix re-runs over the corpus with no re-crawl.
"""

from __future__ import annotations

from lily_parsers.dto import (
    ParsedModel,
    ParsedPart,
    ParsedSection,
    ParsedSymptomIndex,
)
from lily_parsers.model import parse_model
from lily_parsers.part import parse_part
from lily_parsers.section import parse_section
from lily_parsers.symptom import parse_symptom_index

ParsedPage = ParsedPart | ParsedModel | ParsedSection | ParsedSymptomIndex


def parse(page_type: str, html: str, url: str) -> ParsedPage:
    if page_type == "part":
        return parse_part(html, url)
    if page_type == "model":
        return parse_model(html, url)
    if page_type == "section":
        return parse_section(html, url)
    if page_type == "category":  # repair index
        return parse_symptom_index(html, url)
    raise ValueError(f"no parser for page_type {page_type!r}")
