-- 008_drop_prompt_stack.sql
-- Demolish the prompt tool stack. Apps + Skills are the only artifacts left.
-- Pre-demolition state is preserved at git tag `pre-prompt-demolition`.
-- Order matters: drop dependent tables (which also drops their FK constraints)
-- BEFORE deleting prompt rows from tools.

-- 1. Drop tables that hang off tools via FK (CASCADE kills the FK constraints)
DROP TABLE IF EXISTS agent_reviews CASCADE;
DROP TABLE IF EXISTS tool_versions CASCADE;
DROP TABLE IF EXISTS runs CASCADE;

-- 2. Orphan any eval_runs pointers to prompt-era tools (column is not FK-enforced)
UPDATE eval_runs SET tool_id = NULL
WHERE tool_id IN (SELECT id FROM tools WHERE app_type IS NULL OR app_type != 'app');

-- 2b. Clean up app_data / announcements rows that point to prompt tools (FK-enforced)
--     app_data rows pointing to prompt tools are orphan test data from earlier smoke tests.
DELETE FROM app_data
WHERE tool_id IN (SELECT id FROM tools WHERE app_type IS NULL OR app_type != 'app');
DELETE FROM announcements
WHERE tool_id IN (SELECT id FROM tools WHERE app_type IS NULL OR app_type != 'app');

-- 2c. Clean up forge_data_reads rows pointing to prompt tools (column is not FK-enforced,
--     but we don't want orphan audit rows either).
UPDATE forge_data_reads SET tool_id = NULL
WHERE tool_id IN (SELECT id FROM tools WHERE app_type IS NULL OR app_type != 'app');

-- 3. Delete prompt tool rows
DELETE FROM tools WHERE app_type IS NULL OR app_type != 'app';

-- 4. Drop prompt-definition columns
ALTER TABLE tools DROP COLUMN IF EXISTS system_prompt;
ALTER TABLE tools DROP COLUMN IF EXISTS hardened_prompt;
ALTER TABLE tools DROP COLUMN IF EXISTS prompt_diff;
ALTER TABLE tools DROP COLUMN IF EXISTS input_schema;
ALTER TABLE tools DROP COLUMN IF EXISTS model;
ALTER TABLE tools DROP COLUMN IF EXISTS max_tokens;
ALTER TABLE tools DROP COLUMN IF EXISTS temperature;

-- 5. Drop prompt-output classification columns
ALTER TABLE tools DROP COLUMN IF EXISTS output_type;
ALTER TABLE tools DROP COLUMN IF EXISTS output_classification;
ALTER TABLE tools DROP COLUMN IF EXISTS output_format;

-- 6. Drop agent-pipeline governance scores
ALTER TABLE tools DROP COLUMN IF EXISTS reliability_score;
ALTER TABLE tools DROP COLUMN IF EXISTS safety_score;
ALTER TABLE tools DROP COLUMN IF EXISTS complexity_score;
ALTER TABLE tools DROP COLUMN IF EXISTS verified_score;
ALTER TABLE tools DROP COLUMN IF EXISTS data_sensitivity;

-- 7. Drop redundant/prompt-era metadata
ALTER TABLE tools DROP COLUMN IF EXISTS tool_type;
ALTER TABLE tools DROP COLUMN IF EXISTS workflow_steps;
ALTER TABLE tools DROP COLUMN IF EXISTS last_run_at;
