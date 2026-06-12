-- 0001_init: catalog / commerce / ingestion schemas per the approved Phase 1 design.
-- Conventions: surrogate IDENTITY PKs (composite PKs on pure join tables),
-- TEXT + CHECK over enums, TIMESTAMPTZ, NUMERIC(10,2) money, generated *_norm
-- lookup columns via catalog.norm_id(). updated_at is app-maintained.
-- Aurora role GRANTs are provisioned with the Aurora Terraform module, not here.

CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS commerce;
CREATE SCHEMA IF NOT EXISTS ingestion;

-- One normalization for every natural-key lookup; mirrored in Python tool code.
CREATE FUNCTION catalog.norm_id(raw text) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE RETURNS NULL ON NULL INPUT
AS $$ SELECT upper(regexp_replace(raw, '[^A-Za-z0-9]', '', 'g')) $$;

-- ---------------------------------------------------------------------------
-- ingestion: D12 crawl bookkeeping (created first — catalog FKs point here)
-- ---------------------------------------------------------------------------

CREATE TABLE ingestion.source_pages (
    source_page_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url                 text NOT NULL,
    page_type           text NOT NULL
        CHECK (page_type IN ('part', 'model', 'symptom', 'guide', 'category', 'other')),
    -- sha256 of raw body; the change-detection key (unchanged => skip downstream)
    content_hash        text,
    s3_key              text,
    http_status         smallint,
    last_fetched_at     timestamptz,
    last_changed_at     timestamptz,
    last_parsed_at      timestamptz,
    parse_status        text NOT NULL DEFAULT 'pending'
        CHECK (parse_status IN ('pending', 'parsed', 'failed', 'skipped')),
    parse_error         text,
    fetch_failure_count integer NOT NULL DEFAULT 0,
    -- 404/410 pages are flagged, never deleted (provenance anchors)
    is_active           boolean NOT NULL DEFAULT true,
    discovered_at       timestamptz NOT NULL DEFAULT now(),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_source_pages_url UNIQUE (url)
);

CREATE INDEX ix_source_pages_type_fetched ON ingestion.source_pages (page_type, last_fetched_at);
CREATE INDEX ix_source_pages_failed ON ingestion.source_pages (source_page_id)
    WHERE parse_status = 'failed';

CREATE TABLE ingestion.crawl_runs (
    crawl_run_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind          text NOT NULL CHECK (kind IN ('seed', 'nightly', 'backfill')),
    status        text NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'succeeded', 'failed', 'aborted')),
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    pages_fetched integer NOT NULL DEFAULT 0,
    pages_changed integer NOT NULL DEFAULT 0,
    pages_failed  integer NOT NULL DEFAULT 0,
    notes         text
);

-- ---------------------------------------------------------------------------
-- catalog
-- ---------------------------------------------------------------------------

CREATE TABLE catalog.parts (
    part_id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ps_number            text NOT NULL,
    ps_number_norm       text GENERATED ALWAYS AS (catalog.norm_id(ps_number)) STORED NOT NULL,
    mfr_part_number      text,
    mfr_part_number_norm text GENERATED ALWAYS AS (catalog.norm_id(mfr_part_number)) STORED,
    name                 text NOT NULL,
    description          text,
    brand                text,
    appliance_type       text NOT NULL
        CHECK (appliance_type IN ('refrigerator', 'dishwasher')),
    part_category        text,
    price_usd            numeric(10, 2),
    list_price_usd       numeric(10, 2),
    stock_status         text,    -- raw label as scraped (A6); display only
    in_stock             boolean, -- parser-derived; what tools branch on
    install_difficulty   text,    -- raw label, no CHECK (A3); never branch on this
    install_time         text,    -- raw label, no CHECK (A3)
    install_video_url    text,    -- singular (A4); multiples => additive part_videos table
    rating_avg           numeric(3, 2),
    review_count         integer,
    image_url            text,
    source_url           text NOT NULL,
    source_page_id       bigint REFERENCES ingestion.source_pages (source_page_id),
    scraped_at           timestamptz NOT NULL,
    first_seen_at        timestamptz NOT NULL DEFAULT now(),
    last_seen_at         timestamptz NOT NULL DEFAULT now(),
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_parts_ps_number_norm UNIQUE (ps_number_norm)
);

-- Non-unique on purpose: MPN uniqueness scope unverified (A1); lookups may
-- return multiple candidates and the agent disambiguates.
CREATE INDEX ix_parts_mfr_norm ON catalog.parts (mfr_part_number_norm);
CREATE INDEX ix_parts_brand_type ON catalog.parts (brand, appliance_type);
CREATE INDEX ix_parts_category ON catalog.parts (part_category);

CREATE TABLE catalog.models (
    model_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_number      text NOT NULL,
    model_number_norm text GENERATED ALWAYS AS (catalog.norm_id(model_number)) STORED NOT NULL,
    brand             text NOT NULL,
    name              text,
    appliance_type    text NOT NULL
        CHECK (appliance_type IN ('refrigerator', 'dishwasher')),
    source_url        text NOT NULL,
    source_page_id    bigint REFERENCES ingestion.source_pages (source_page_id),
    scraped_at        timestamptz NOT NULL,
    first_seen_at     timestamptz NOT NULL DEFAULT now(),
    last_seen_at      timestamptz NOT NULL DEFAULT now(),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    -- Global uniqueness assumed (A2); ETL logs conflicting-brand upserts as
    -- schema drift. Fallback migration: UNIQUE (brand, model_number_norm).
    CONSTRAINT uq_models_number_norm UNIQUE (model_number_norm)
);

CREATE INDEX ix_models_brand_type ON catalog.models (brand, appliance_type);

-- The hot table: FR-13 compatibility verdicts come from here, never the LLM.
CREATE TABLE catalog.part_model_compatibility (
    part_id        bigint NOT NULL REFERENCES catalog.parts (part_id) ON DELETE CASCADE,
    model_id       bigint NOT NULL REFERENCES catalog.models (model_id) ON DELETE CASCADE,
    source_url     text NOT NULL,
    source_page_id bigint REFERENCES ingestion.source_pages (source_page_id),
    first_seen_at  timestamptz NOT NULL DEFAULT now(),
    -- Upsert bumps this; the janitor deletes per-page rows older than that
    -- page's successful parse start — a failed crawl can never mass-delete.
    last_seen_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (part_id, model_id)
);

-- Reverse probe: all compatible parts for a model (FR-14), index-only scan.
CREATE INDEX ix_compat_model_part ON catalog.part_model_compatibility (model_id, part_id);
CREATE INDEX ix_compat_source_page ON catalog.part_model_compatibility (source_page_id);

CREATE TABLE catalog.symptoms (
    symptom_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    appliance_type  text NOT NULL
        CHECK (appliance_type IN ('refrigerator', 'dishwasher')),
    name            text NOT NULL,
    description     text,
    reported_by_pct numeric(5, 2), -- nullable (A5)
    source_url      text NOT NULL,
    source_page_id  bigint REFERENCES ingestion.source_pages (source_page_id),
    scraped_at      timestamptz NOT NULL,
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_symptoms_type_name UNIQUE (appliance_type, name)
);

-- Deterministic half of FR-17 diagnosis: symptom -> ranked likely-failed parts.
CREATE TABLE catalog.symptom_parts (
    symptom_id     bigint NOT NULL REFERENCES catalog.symptoms (symptom_id) ON DELETE CASCADE,
    part_id        bigint NOT NULL REFERENCES catalog.parts (part_id) ON DELETE CASCADE,
    fix_percentage numeric(5, 2), -- nullable (A5)
    display_rank   integer,       -- on-page order; ranking fallback when fix % absent
    source_url     text NOT NULL,
    source_page_id bigint REFERENCES ingestion.source_pages (source_page_id),
    scraped_at     timestamptz NOT NULL,
    last_seen_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symptom_id, part_id)
);

CREATE INDEX ix_symptom_parts_part ON catalog.symptom_parts (part_id);

CREATE TABLE catalog.repair_guides (
    guide_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title          text NOT NULL,
    appliance_type text
        CHECK (appliance_type IN ('refrigerator', 'dishwasher')),
    symptom_id     bigint REFERENCES catalog.symptoms (symptom_id) ON DELETE SET NULL,
    part_id        bigint REFERENCES catalog.parts (part_id) ON DELETE SET NULL,
    body_text      text NOT NULL,
    difficulty     text, -- raw label (A3)
    est_time       text, -- raw label (A3)
    video_url      text,
    content_hash   text NOT NULL, -- sha256(body_text); drives re-embedding
    source_url     text NOT NULL,
    source_page_id bigint REFERENCES ingestion.source_pages (source_page_id),
    scraped_at     timestamptz NOT NULL,
    first_seen_at  timestamptz NOT NULL DEFAULT now(),
    last_seen_at   timestamptz NOT NULL DEFAULT now(),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_repair_guides_source_url UNIQUE (source_url)
);

CREATE INDEX ix_repair_guides_symptom ON catalog.repair_guides (symptom_id);
CREATE INDEX ix_repair_guides_part ON catalog.repair_guides (part_id);

CREATE TABLE catalog.qna (
    qna_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    part_id          bigint NOT NULL REFERENCES catalog.parts (part_id) ON DELETE CASCADE,
    question         text NOT NULL,
    answer           text, -- unanswered questions exist (A7)
    asked_at         date,
    model_number_raw text, -- verbatim model the asker mentioned
    model_id         bigint REFERENCES catalog.models (model_id) ON DELETE SET NULL,
    helpful_count    integer,
    -- sha256(question || answer); no stable scrape IDs (A7) — idempotent re-ingest
    content_hash     text NOT NULL,
    source_url       text NOT NULL,
    source_page_id   bigint REFERENCES ingestion.source_pages (source_page_id),
    scraped_at       timestamptz NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_qna_part_hash UNIQUE (part_id, content_hash)
);

CREATE INDEX ix_qna_part ON catalog.qna (part_id);
CREATE INDEX ix_qna_model ON catalog.qna (model_id);

CREATE TABLE catalog.reviews (
    review_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    part_id        bigint NOT NULL REFERENCES catalog.parts (part_id) ON DELETE CASCADE,
    rating         smallint CHECK (rating BETWEEN 1 AND 5), -- nullable (A7)
    title          text,
    body           text,
    reviewer_name  text,
    reviewed_at    date,
    content_hash   text NOT NULL,
    source_url     text NOT NULL,
    source_page_id bigint REFERENCES ingestion.source_pages (source_page_id),
    scraped_at     timestamptz NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_reviews_part_hash UNIQUE (part_id, content_hash)
);

CREATE INDEX ix_reviews_part ON catalog.reviews (part_id);

-- ---------------------------------------------------------------------------
-- commerce: mock orders (D18 — no real payments)
-- ---------------------------------------------------------------------------

CREATE TABLE commerce.orders (
    order_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_number      text NOT NULL,
    order_number_norm text GENERATED ALWAYS AS (catalog.norm_id(order_number)) STORED NOT NULL,
    email             text NOT NULL,
    -- CHECK is right here (unlike scraped fields): we control this vocabulary.
    status            text NOT NULL CHECK (status IN (
        'placed', 'processing', 'shipped', 'out_for_delivery', 'delivered',
        'cancelled', 'return_requested', 'returned', 'refunded')),
    placed_at         timestamptz NOT NULL,
    carrier           text,
    tracking_number   text,
    -- city/region only, no street address (NFR-13 PII minimization)
    shipping_city     text,
    shipping_region   text,
    total_usd         numeric(10, 2) NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_orders_number_norm UNIQUE (order_number_norm)
);
-- Lookup: WHERE order_number_norm = $1 AND lower(email) = lower($2).
-- One uniform ORDER_NOT_FOUND for no-such-order and wrong-email alike
-- (prevents order-number enumeration).

CREATE TABLE commerce.order_items (
    order_item_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id       bigint NOT NULL REFERENCES commerce.orders (order_id) ON DELETE CASCADE,
    -- Soft link: survives catalog re-scrapes; snapshots below are canonical.
    part_id        bigint REFERENCES catalog.parts (part_id) ON DELETE SET NULL,
    ps_number      text NOT NULL,
    name           text NOT NULL,
    unit_price_usd numeric(10, 2) NOT NULL,
    quantity       integer NOT NULL CHECK (quantity > 0)
);

CREATE INDEX ix_order_items_order ON commerce.order_items (order_id);

CREATE TABLE commerce.order_events (
    order_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id       bigint NOT NULL REFERENCES commerce.orders (order_id) ON DELETE CASCADE,
    event_type     text NOT NULL,
    occurred_at    timestamptz NOT NULL,
    description    text
);

CREATE INDEX ix_order_events_order_time ON commerce.order_events (order_id, occurred_at);

CREATE TABLE commerce.returns (
    return_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reference     text NOT NULL, -- e.g. RMA-2026-000123
    order_id      bigint NOT NULL REFERENCES commerce.orders (order_id),
    order_item_id bigint REFERENCES commerce.order_items (order_item_id),
    reason        text NOT NULL,
    status        text NOT NULL DEFAULT 'requested' CHECK (status IN (
        'requested', 'approved', 'received', 'refunded', 'rejected')),
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_returns_reference UNIQUE (reference)
);

CREATE INDEX ix_returns_order ON commerce.returns (order_id);

-- ---------------------------------------------------------------------------
-- ingestion.search_sync: OpenSearch stays fully derivable from Aurora;
-- the embed job anti-joins on content_hash so unchanged rows never re-embed.
-- ---------------------------------------------------------------------------

CREATE TABLE ingestion.search_sync (
    entity_type  text NOT NULL CHECK (entity_type IN ('guide', 'qna', 'review', 'part')),
    entity_id    bigint NOT NULL,
    index_name   text NOT NULL,
    content_hash text NOT NULL,
    indexed_at   timestamptz NOT NULL,
    status       text NOT NULL DEFAULT 'indexed'
        CHECK (status IN ('indexed', 'stale', 'failed')),
    PRIMARY KEY (entity_type, entity_id, index_name)
);
