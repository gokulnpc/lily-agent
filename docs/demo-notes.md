# Demo / Loom notes (Phase 3)

Live stack: `https://app.dev.lily-agent.com` (frontend) → in-cluster gateway
(embedded orchestrator) → Aurora + OpenSearch + Bedrock.

## Canonical flows (PRD §10) and which data showcases each

| Flow | Demo input | Notes |
|---|---|---|
| **Install** | "How can I install part number **PS11752778**?" | PS11752778 (Door Shelf Bin) **is enriched** in the live catalog — difficulty "Really Easy", time "<15 min", and a YouTube install video — so it renders the full enriched install card. This is the install showcase part. (Fallback parts — found but not enriched — give an honest "see the part page" answer; not needed for the demo since the canonical part works.) |
| **Compatibility** | "Is PS11752778 compatible with my **WDT780SAEM1**?" | NO verdict + correct dishwasher alternatives as product cards. This turn also sets the **session model chip** (FR-5) to WDT780SAEM1 — use it to show "turn sets a model, badge appears." |
| **Diagnosis** | "The ice maker on my Whirlpool fridge is not working." | Ranked likely-part cards. **See the ranking note below.** |
| **Comparison** | "Compare PS7784018 and PS12364147" | Renders the ComparisonCard (difficulty, time, video, rating). |
| **Quick-reply** | click the "How do I install PS…?" chip | Chip carries a PS number, so clicking it resolves the part and lands the install path. |
| **Order** | "Where is my order LILY-1001, email demo@lily.test?" | Seeded demo order → OrderCard (status, timeline, tracking). Other demo pairs in `db/migrations/0007_demo_orders.sql`. |

## The ice-maker ranking artifact — NARRATE it (integrity story)

In the ice-maker diagnosis, the **Crisper Drawer card can lead** the list. That is
**not a bug to hide** — it's the honest fallback ranking on record (FR-17). PartSelect
part pages carry **no per-part fix percentages**, so `diagnose_symptom` ranks likely
parts by an honest signal (**review count / in-stock**), never a fabricated fix %.
The high-review Crisper Drawer outranks more topically-relevant ice parts because the
catalog has no symptom→section relevance signal yet.

**Tell this as the integrity story:** "LLM narrates, database decides" — we'd rather
show an honest, slightly-imperfect ranking than invent a fix-% the source doesn't have.
The Phase-5 fix direction is **on record** (DECISIONS.md "Repair likely-parts ranking"):
a curated symptom→schematic-section relevance re-rank (a new gated human-judgment table
+ a `display_rank` re-backfill) — deferred because it is *not* a cheap join.
