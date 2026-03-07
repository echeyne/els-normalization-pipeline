-- Add title column to indicators table.
-- The title stores the indicator's name (e.g. "Curiosity and Interest"),
-- while description stores the longer explanatory text.

ALTER TABLE indicators ADD COLUMN IF NOT EXISTS title TEXT;
