-- 011_source_column.sql
-- Distinguish external open-source apps from internal employee-built apps.
-- Both coexist in the catalog; both get governance, different kinds.
ALTER TABLE tools ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'internal';
  -- 'internal' = built by an employee at the company
  -- 'external' = curated from open-source / third-party
ALTER TABLE tools ADD COLUMN IF NOT EXISTS github_stars INTEGER;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS github_license TEXT;
ALTER TABLE tools ADD COLUMN IF NOT EXISTS github_last_commit TEXT;
