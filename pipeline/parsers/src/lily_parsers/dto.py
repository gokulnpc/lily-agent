"""Parser output DTOs — framework-agnostic plain data (CLAUDE.md: domain code
has no framework types). The ETL step maps these to Aurora rows."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedPart:
    ps_number: str
    name: str
    appliance_type: str
    mfr_part_number: str | None = None
    brand: str | None = None
    price_usd: float | None = None
    stock_status: str | None = None
    in_stock: bool | None = None
    install_difficulty: str | None = None
    install_time: str | None = None
    install_video_url: str | None = None
    rating_avg: float | None = None
    review_count: int | None = None
    image_url: str | None = None
    symptoms_fixed: list[str] = field(default_factory=list)
    # Discovery hint only — NOT authoritative compatibility (A9 model-canonical).
    compatible_model_urls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedModel:
    model_number: str
    brand: str
    appliance_type: str
    name: str | None = None
    # The robots-clean completeness path; ETL enqueues these (cap-governed).
    section_urls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CompatPair:
    ps_number: str
    part_name: str


@dataclass(frozen=True)
class ParsedSection:
    """Authoritative compatibility source (A9): every part in this section fits
    this model."""

    model_number: str
    parts: list[CompatPair] = field(default_factory=list)


@dataclass(frozen=True)
class SymptomRef:
    name: str
    url: str
    reported_by_pct: float | None


@dataclass(frozen=True)
class ParsedSymptomIndex:
    appliance_type: str
    symptoms: list[SymptomRef] = field(default_factory=list)
