"""Typed UI cards (Phase 3) carried on the SSE `message.structured` array. Built
STRUCTURALLY from tool results — never parsed from prose (same discipline as
citations). The frontend renders these; it never re-derives facts.

Card fields are uniform (a ProductCard is a ProductCard regardless of which tool
produced it), so the specialist enriches partial sources (compatibility
alternatives, repair likely-parts) via a deterministic get_part_details lookup —
that enrichment lives in specialists.py; the builders here are pure mappers.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from lily_catalog.models import PartDetails, PartSummary
from lily_orders.models import OrderResult
from lily_retrieval.models import LikelyPart, PartHit


class ProductCard(BaseModel):
    kind: Literal["product"] = "product"
    ps_number: str
    name: str
    price_usd: float | None = None
    in_stock: bool | None = None
    image_url: str | None = None
    url: str | None = None
    install_difficulty: str | None = None
    rating_avg: float | None = None
    review_count: int | None = None
    fix_percentage: float | None = None  # set only when sourced from a repair likely-part


class ComparisonCard(BaseModel):
    kind: Literal["comparison"] = "comparison"
    parts: list[ProductCard]  # 2-3 (FR-11)


class OrderCard(BaseModel):
    kind: Literal["order"] = "order"
    order_number: str | None = None
    order_status: str | None = None
    placed_at: str | None = None  # ISO-8601
    carrier: str | None = None
    tracking_number: str | None = None
    total_usd: float | None = None
    items: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []


def product_from_details(
    details: PartDetails, *, fix_percentage: float | None = None
) -> ProductCard:
    return ProductCard(
        ps_number=details.ps_number,
        name=details.name,
        price_usd=details.price_usd,
        in_stock=details.in_stock,
        image_url=details.image_url,
        url=details.source_url,
        install_difficulty=details.install_difficulty,
        rating_avg=details.rating_avg,
        review_count=details.review_count,
        fix_percentage=fix_percentage,
    )


def product_from_summary(summary: PartSummary) -> ProductCard:
    # Compatibility alternatives carry no install_difficulty/rating — those stay
    # None unless the specialist enriches via get_part_details.
    return ProductCard(
        ps_number=summary.ps_number,
        name=summary.name,
        price_usd=summary.price_usd,
        in_stock=summary.in_stock,
        image_url=summary.image_url,
        url=summary.source_url,
    )


def product_from_hit(hit: PartHit) -> ProductCard:
    return ProductCard(
        ps_number=hit.ps_number,
        name=hit.name,
        price_usd=hit.price_usd,
        in_stock=hit.in_stock,
        image_url=hit.image_url,
        url=hit.source_url,
    )


def product_from_likely(part: LikelyPart) -> ProductCard:
    # A repair likely-part is just ps/name/fix% until enriched.
    return ProductCard(ps_number=part.ps_number, name=part.name, fix_percentage=part.fix_percentage)


def order_card(result: OrderResult) -> OrderCard:
    return OrderCard(
        order_number=result.order_number,
        order_status=result.order_status,
        placed_at=result.placed_at.isoformat() if result.placed_at else None,
        carrier=result.carrier,
        tracking_number=result.tracking_number,
        total_usd=result.total_usd,
        items=[i.model_dump() for i in result.items],
        timeline=[
            {**e.model_dump(exclude={"occurred_at"}), "occurred_at": e.occurred_at.isoformat()}
            for e in result.timeline
        ],
    )
