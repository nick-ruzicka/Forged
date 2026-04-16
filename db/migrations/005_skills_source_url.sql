-- Adds source_url (GitHub link) to skills so the library can point back to
-- the canonical repo, and lets the frontend construct an install command.

ALTER TABLE skills ADD COLUMN IF NOT EXISTS source_url TEXT;
