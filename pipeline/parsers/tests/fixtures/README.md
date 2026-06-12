# Parser test fixtures — real PartSelect HTML

Captured real pages, kept in git as **parser unit-test input** and the
**schema-drift baseline** (a parser contract test that stops matching these is
the first signal PartSelect changed its markup — PRD §8 risk).

| Fixture | Page type | URL captured |
|---|---|---|
| `part-fridge.html` | part | `/PS11752778-…-Refrigerator-Door-Shelf-Bin.htm` |
| `part-dishwasher.html` | part | `/PS11746591-…-Dishwasher-Door-Balance-Link-Kit.htm` |
| `model-fridge.html` | model | `/Models/WRS325FDAM04/` |
| `model-dishwasher.html` | model | `/Models/WDT780SAEM1/` |
| `repair-index-fridge.html` | repair index | `/Repair/Refrigerator/` (symptom list) |
| `symptom-fridge.html` | symptom | `/Repair/Refrigerator/Door-Sweating/` |
| `robots.html` | robots.txt | `/robots.txt` (rendered in a `<pre>`) |

These resolved schema assumption **A9** (compatibility directionality →
model-canonical; see docs/DECISIONS.md) and exercise A1–A8.

## Refreshing

```sh
uv run python -m lily_crawler.tools.capture_fixtures
```

Polite (long delays, robots-allowed paths, stops on repeated denials) and uses
the real Chrome channel — headless and plain HTTP are Akamai-403'd. Re-capture
when a drift alert fires, then re-baseline the parser contract tests against the
new HTML.
