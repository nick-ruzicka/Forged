-- Forge Platform — Migration 003: Tool Composability v1
-- Adds workflow_steps column to tools for chained tool workflows.
--
-- workflow_steps stores a JSON array of step descriptors, e.g.:
--   [
--     {"step_order": 1, "tool_id": 42, "input_mappings": {}},
--     {"step_order": 2, "tool_id": 77, "input_mappings": {"topic": "{{step1.output}}"}}
--   ]
--
-- Nullable TEXT so legacy tools without workflows stay untouched.

ALTER TABLE tools ADD COLUMN IF NOT EXISTS workflow_steps TEXT;
