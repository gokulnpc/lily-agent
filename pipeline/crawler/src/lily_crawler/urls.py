"""PartSelect URL classification and section-URL parsing.

Pure helpers (no network) so discovery and the model parser agree on what a URL
is and which appliance it belongs to.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

APPLIANCES = ("Refrigerator", "Dishwasher")
_APPLIANCE_RX = re.compile(r"/Repair/(Refrigerator|Dishwasher)/", re.IGNORECASE)
_PART_RX = re.compile(r"/PS\d+", re.IGNORECASE)
_MODEL_RX = re.compile(r"/Models/[^/]+/?$", re.IGNORECASE)
_SECTION_RX = re.compile(r"/Models/[^/]+/Sections/[^/]+/?", re.IGNORECASE)
_REPAIR_INDEX_RX = re.compile(r"/Repair/(Refrigerator|Dishwasher)/?$", re.IGNORECASE)
_SYMPTOM_RX = re.compile(r"/Repair/(Refrigerator|Dishwasher)/[^/]+/?$", re.IGNORECASE)


def classify(url: str) -> str:
    """Map a URL to a source_pages.page_type, or 'other' if unrecognized."""
    path = urlsplit(url).path
    if _PART_RX.search(path):
        return "part"
    if _SECTION_RX.search(path):
        return "section"
    if _MODEL_RX.search(path):
        return "model"
    if _REPAIR_INDEX_RX.search(path):
        return "category"  # the symptom-list index page
    if _SYMPTOM_RX.search(path):
        return "symptom"
    return "other"


def in_scope_appliance(url: str) -> bool:
    """Symptom/repair URLs scoped to refrigerator or dishwasher only (PRD non-goal)."""
    return bool(_APPLIANCE_RX.search(url))
