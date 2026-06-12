-- 0006: vocab map additions from the phase-2 part-enrichment harvest (769 parts).
-- Owner-reviewed 2026-06-12 (round 2). Phrases are normalized (lower, trimmed,
-- straight apostrophe) to match the upsert's translate(curly -> straight). Three
-- of these fill canonical symptoms that had NO part-page phrase until phase 2
-- (Not drying dishes properly, Freezer too cold) or are clean contractions/
-- synonyms of mapped ones.

INSERT INTO catalog.symptom_vocab (phrase, symptom_name, note) VALUES
    ('not drying dishes properly', 'Not drying dishes properly', 'fills a canonical with no phrase until phase 2'),
    ('won''t start',              'Will not start',             'contraction of "will not start"'),
    ('freezer too cold',          'Freezer too cold',           'fills a canonical with no phrase until phase 2'),
    ('leaks water',               'Leaking',                    'synonym (owner-approved)'),
    ('doesn''t stop running',     'Fridge runs too long',       'true synonym (owner-approved)')
ON CONFLICT (phrase) DO NOTHING;

-- Still UNMATCHED after round-2 review (logged, deliberately not mapped):
--   'too warm' (6)                      ambiguous: fridge-only vs freezer-only vs both — wrong-part risk
--   'ice maker dispenses too much ice'  no canonical (ice-dispensing family, see DECISIONS backlog)
-- The ice-DISPENSING cluster (won't dispense ice 26 + too little 6 + too much 1 =
-- 33) is a Phase-5 backlog item: a curated parts-only canonical symptom is
-- defensible (the part->symptom linkage is source-attested) but is a Phase-5
-- decision, not now. See DECISIONS.md.
