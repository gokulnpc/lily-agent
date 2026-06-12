"""Typed I/O for the retrieval tools (pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SearchRequest(BaseModel):
    text: str
    appliance_type: str | None = None  # "refrigerator" | "dishwasher" filter


class PartHit(_Frozen):
    ps_number: str
    name: str
    score: float
    price_usd: float | None = None
    in_stock: bool | None = None
    image_url: str | None = None
    source_url: str | None = None


class DiagnoseRequest(BaseModel):
    text: str
    appliance_type: str | None = None
    model_number: str | None = None  # when known, ranked parts are model-filtered


class LikelyPart(_Frozen):
    ps_number: str
    name: str
    fix_percentage: float | None = None


class SymptomMatch(_Frozen):
    name: str
    score: float
    description: str | None = None
    source_url: str | None = None
    # Ranked parts that fix this symptom. EMPTY until catalog.symptom_parts is
    # populated by ETL (see Diagnosis.note).
    likely_parts: list[LikelyPart] = []


class Diagnosis(_Frozen):
    symptoms: list[SymptomMatch] = []
    note: str | None = None
