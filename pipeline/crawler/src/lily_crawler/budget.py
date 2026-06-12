"""Crawl budget — intentional per-category allocation of the ~500-page cap
across the two-hop, model-canonical crawl (D13 scope control).

The crawl fans out: seed part+symptom pages → discover models → section pages →
their parts. Without per-category sub-budgets, "whatever fits first" would spend
the whole cap on one category. Instead we reserve a slice per category so the
seed set is deliberate: COMPLETE coverage of a small number of models (every
section, every part) rather than partial coverage of many.

Per-category enqueue checks its own sub-budget; reaching it is a hard stop that
reports the drop (never silent truncation, NFR-18 visibility).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CrawlBudget:
    """Sub-budgets per source_pages page_type. Defaults sum to ~500 and target
    full coverage of `target_models` models (their sections + parts) plus
    appliance symptom coverage."""

    target_models: int = 4  # 2 fridge + 2 dishwasher, fully covered

    # 1 model page each.
    models: int = 4
    # ~14 sections/model — the robots-clean completeness path.
    sections: int = 60
    # part pages (attributes); deduped across models. The bulk of the budget.
    parts: int = 400
    # repair indexes (2) + symptom detail pages (~12 fridge + ~12 dishwasher).
    symptoms: int = 36

    _spent: dict[str, int] = field(default_factory=dict)

    @staticmethod
    def _bucket(page_type: str) -> str:
        # The repair index and its symptom detail pages share one slice.
        return "symptom" if page_type == "category" else page_type

    def cap_for(self, page_type: str) -> int:
        return {
            "model": self.models,
            "section": self.sections,
            "part": self.parts,
            "symptom": self.symptoms,
        }.get(self._bucket(page_type), 0)

    def total(self) -> int:
        return self.models + self.sections + self.parts + self.symptoms

    def try_spend(self, page_type: str) -> bool:
        """Reserve one fetch of this type; False (a reportable drop) if its
        sub-budget is exhausted."""
        bucket = self._bucket(page_type)
        spent = self._spent.get(bucket, 0)
        if spent >= self.cap_for(bucket):
            return False
        self._spent[bucket] = spent + 1
        return True

    def spent(self, page_type: str) -> int:
        return self._spent.get(self._bucket(page_type), 0)
