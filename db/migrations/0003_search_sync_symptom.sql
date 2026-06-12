-- 0003: add 'symptom' to the search_sync entity_type vocabulary.
-- Symptom entries (name + description from the repair index) are a retrieval
-- corpus (retrieval-symptoms) for RAG diagnosis, alongside guides/qna/reviews/parts.

ALTER TABLE ingestion.search_sync
    DROP CONSTRAINT search_sync_entity_type_check,
    ADD CONSTRAINT search_sync_entity_type_check
        CHECK (entity_type IN ('guide', 'qna', 'review', 'part', 'symptom'));
