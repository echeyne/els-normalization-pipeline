-- Add human verification and audit tracking columns to hierarchy tables.
-- These support the human-in-the-loop validation workflow where editors
-- can verify extracted data against source PDFs and track all modifications.

-- Domains
ALTER TABLE domains ADD COLUMN IF NOT EXISTS human_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS verified_by VARCHAR(255);
ALTER TABLE domains ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;
ALTER TABLE domains ADD COLUMN IF NOT EXISTS edited_by VARCHAR(255);

-- Strands
ALTER TABLE strands ADD COLUMN IF NOT EXISTS human_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE strands ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;
ALTER TABLE strands ADD COLUMN IF NOT EXISTS verified_by VARCHAR(255);
ALTER TABLE strands ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;
ALTER TABLE strands ADD COLUMN IF NOT EXISTS edited_by VARCHAR(255);

-- Sub-strands
ALTER TABLE sub_strands ADD COLUMN IF NOT EXISTS human_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE sub_strands ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;
ALTER TABLE sub_strands ADD COLUMN IF NOT EXISTS verified_by VARCHAR(255);
ALTER TABLE sub_strands ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;
ALTER TABLE sub_strands ADD COLUMN IF NOT EXISTS edited_by VARCHAR(255);

-- Indicators
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS human_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS verified_by VARCHAR(255);
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP;
ALTER TABLE indicators ADD COLUMN IF NOT EXISTS edited_by VARCHAR(255);
