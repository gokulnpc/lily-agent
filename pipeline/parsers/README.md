# parsers

Parse raw HTML from S3 (**NEVER fetch**). Re-parseable from the S3 corpus when
source markup drifts; contract assertions guard schema drift. **Phase 1.**

## Parsers (one per page type)

| Parser | Input page | Output | Key fields |
|---|---|---|---|
| `part.py` | `/PS…htm` | `ParsedPart` | PS#, MPN, brand, price, stock, difficulty/time, video, rating, symptoms-fixed; model-cross-ref as **discovery hint only** (A9) |
| `model.py` | `/Models/{n}/` | `ParsedModel` | model#, brand, appliance; **section URLs** (the completeness path) |
| `section.py` | `/Models/{n}/Sections/{s}/` | `ParsedSection` | **authoritative compat pairs** — every part fits this model (A9) |
| `symptom.py` | `/Repair/{appliance}/` | `ParsedSymptomIndex` | symptom list + reported-by % |

`dispatch.parse(page_type, html, url)` routes by `source_pages.page_type`. Output
DTOs (`dto.py`) are framework-agnostic plain data; the ETL maps them to Aurora.

## Drift detection (fails loud, never silent)

`contract.require(...)` raises `SchemaDriftError` when a required field is
missing — a PartSelect markup change becomes a failed parse + alert
(`parse_status='failed'`, NFR-18), not a quietly empty row. Raw HTML stays in S3,
so a selector fix re-parses with no re-crawl. The fixtures in `tests/fixtures/`
are the drift baseline; `broken-part.html` (productID removed) proves the
contract fires.

## Compatibility direction (A9)

Compat pairs come **only** from section pages. Part pages contribute attributes;
their model cross-reference is a discovery hint, never written as authoritative
pairs (it's paginated/incomplete). See docs/DECISIONS.md A9.
