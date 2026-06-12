-- 0002: add 'section' to the source_pages page_type vocabulary.
-- Model-canonical completeness (A9) reads the full parts list from a model's
-- per-section pages (/Models/{n}/Sections/{s}/) rather than the robots-
-- discouraged /Parts/ mega-list. Section pages are a distinct parser dispatch,
-- so they get their own page_type.

ALTER TABLE ingestion.source_pages
    DROP CONSTRAINT source_pages_page_type_check,
    ADD CONSTRAINT source_pages_page_type_check
        CHECK (page_type IN ('part', 'model', 'section', 'symptom', 'guide', 'category', 'other'));
