-- 0004: persist the part page's source-attested "This part fixes the following
-- symptoms" list. Resolves the A14 gap (symptoms_fixed was parsed but dropped by
-- upsert_part — no column existed). These raw phrases are the source for the
-- curated symptoms_fixed -> catalog.symptoms vocab map that backfills
-- catalog.symptom_parts (FR-17). Verbatim site phrasing, kept as a text[].

ALTER TABLE catalog.parts
    ADD COLUMN symptoms_fixed text[] NOT NULL DEFAULT '{}';
