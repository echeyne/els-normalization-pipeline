-- Add description columns to hierarchy tables and age_band to indicators.
-- These store the descriptive text extracted by the parser for each hierarchy level,
-- and the per-indicator age band from the parsed data.

ALTER TABLE domains ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE strands ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE sub_strands ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS age_band VARCHAR(20);
