"""Typed I/O contracts for the catalog tools (pydantic v2). Framework-agnostic —
no LangGraph types; these are the agent's tool schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Verdict = Literal["YES", "NO", "MODEL_NOT_FOUND", "PART_NOT_FOUND"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class CompatibilityRequest(BaseModel):
    part: str  # PS number or raw user text
    model: str  # model number or raw user text


class PartSummary(_Frozen):
    ps_number: str
    name: str
    part_category: str | None = None
    price_usd: float | None = None
    in_stock: bool | None = None
    image_url: str | None = None
    source_url: str | None = None


class CompatibilityResult(_Frozen):
    verdict: Verdict
    ps_number: str | None = None
    part_name: str | None = None
    model_number: str | None = None
    brand: str | None = None
    citation_url: str | None = None  # the section page that attests the pair (YES)
    # On NO: the equivalent parts that DO fit this model (FR-14).
    alternatives: list[PartSummary] = []


class PartDetails(_Frozen):
    ps_number: str
    name: str
    appliance_type: str
    mfr_part_number: str | None = None
    brand: str | None = None
    part_category: str | None = None
    price_usd: float | None = None
    stock_status: str | None = None
    in_stock: bool | None = None
    install_difficulty: str | None = None
    install_time: str | None = None
    install_video_url: str | None = None
    rating_avg: float | None = None
    review_count: int | None = None
    image_url: str | None = None
    source_url: str


class InstallInfo(_Frozen):
    """Install-focused projection of a part (FR-18): difficulty, time, and video,
    for the Repair specialist's install path. No step text — PartSelect part pages
    carry these attributes, not prose steps (DECISIONS: install→repair gap close)."""

    ps_number: str
    name: str
    install_difficulty: str | None = None
    install_time: str | None = None
    install_video_url: str | None = None
    source_url: str


class ModelSummary(_Frozen):
    model_number: str
    brand: str
    appliance_type: str
    name: str | None = None
    source_url: str | None = None
