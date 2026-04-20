-- Migration 023: Add config_schema column to tools table
-- Stores the YAML schema defining a tool's configuration surface.

ALTER TABLE tools ADD COLUMN IF NOT EXISTS config_schema TEXT;
