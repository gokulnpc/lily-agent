-- 0005: curated symptoms_fixed -> catalog.symptoms vocabulary map (A14 / FR-17).
-- The one human-judgment artifact in the symptom_parts chain: part-page symptom
-- phrasing differs from the canonical repair-index names (curly apostrophes,
-- "won't" vs "Will not", and near-synonyms), so a reviewed map — NOT an auto-join
-- — is the source of truth. Phrases are normalized (lower, trimmed, straight
-- apostrophe); the upsert applies the same normalization to part phrases. The
-- part's appliance_type resolves which symptom row a both-appliance name hits.
-- Reviewed and ruled by the owner 2026-06-12 (phase-1 harvest of 25 phrases).

CREATE TABLE catalog.symptom_vocab (
    phrase       text PRIMARY KEY,  -- normalized part-page phrase
    symptom_name text NOT NULL,     -- -> catalog.symptoms.name (appliance via the part)
    note         text
);

-- 16 confident maps + 3 owner-approved near-synonyms (door open/close -> latch
-- failure; clicking sound -> noisy).
INSERT INTO catalog.symptom_vocab (phrase, symptom_name, note) VALUES
    ('leaking',                          'Leaking',                          NULL),
    ('not cleaning dishes properly',     'Not cleaning dishes properly',     NULL),
    ('noisy',                            'Noisy',                            NULL),
    ('fridge too warm',                  'Fridge too warm',                  NULL),
    ('not draining',                     'Not draining',                     NULL),
    ('door latch failure',               'Door latch failure',               NULL),
    ('will not start',                   'Will not start',                   NULL),
    ('fridge and freezer are too warm',  'Fridge and Freezer are too warm',  NULL),
    ('door sweating',                    'Door Sweating',                    NULL),
    ('fridge too cold',                  'Fridge too cold',                  NULL),
    ('ice maker not making ice',         'Ice maker not making ice',         NULL),
    ('light not working',                'Light not working',                NULL),
    ('not dispensing water',             'Not dispensing water',             NULL),
    ('will not fill with water',         'Will not fill with water',         NULL),
    ('fridge runs too long',             'Fridge runs too long',             NULL),
    ('will not dispense detergent',      'Will not dispense detergent',      NULL),
    ('door won''t open or close',        'Door latch failure',               'near-synonym (owner-approved): same root-cause family'),
    ('door won''t close',                'Door latch failure',               'near-synonym (owner-approved)'),
    ('clicking sound',                   'Noisy',                            'near-synonym (owner-approved): a clicking report belongs under noise');

-- UNMATCHED (logged, deliberately NOT mapped — would surface wrong parts):
--   'freezer section too warm'           (2)  freezer-only warm != both-too-warm (diagnostically different)
--   'ice maker won''t dispense ice'      (4)  no canonical "dispense ice" symptom; dispensing != making
--   'ice maker dispenses too little ice' (1)  same gap as above
--   'freezer not defrosting'             (1)  no canonical symptom
--   'frost buildup'                      (1)  no canonical symptom
--   'touchpad does not respond'          (1)  no canonical symptom
-- NOTE (owner-flagged): the 4 "ice maker won't dispense ice" occurrences suggest
-- the 21-row canonical symptom list may be MISSING a real PartSelect symptom page
-- (ice dispensing) — a candidate for a future symptom-index widening, NOT a
-- force-match. The map only grows through review.
