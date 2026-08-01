-- Persist V0.2 task definitions and every Agent execution.

ALTER TABLE inspection_tasks
    ADD COLUMN IF NOT EXISTS title TEXT,
    ADD COLUMN IF NOT EXISTS artifact_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

UPDATE inspection_tasks
SET title = COALESCE(NULLIF(btrim(title), ''), objective)
WHERE title IS NULL OR btrim(title) = '';

UPDATE inspection_tasks
SET status = 'draft'
WHERE status NOT IN ('draft', 'running', 'completed', 'failed');

ALTER TABLE inspection_tasks
    ALTER COLUMN title SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_tasks_title_nonblank'
    ) THEN
        ALTER TABLE inspection_tasks
            ADD CONSTRAINT ck_inspection_tasks_title_nonblank
            CHECK (btrim(title) <> '');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_tasks_type_nonblank'
    ) THEN
        ALTER TABLE inspection_tasks
            ADD CONSTRAINT ck_inspection_tasks_type_nonblank
            CHECK (btrim(task_type) <> '');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_tasks_objective_nonblank'
    ) THEN
        ALTER TABLE inspection_tasks
            ADD CONSTRAINT ck_inspection_tasks_objective_nonblank
            CHECK (btrim(objective) <> '');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_tasks_artifact_ids_array'
    ) THEN
        ALTER TABLE inspection_tasks
            ADD CONSTRAINT ck_inspection_tasks_artifact_ids_array
            CHECK (jsonb_typeof(artifact_ids) = 'array');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_tasks_status'
    ) THEN
        ALTER TABLE inspection_tasks
            ADD CONSTRAINT ck_inspection_tasks_status
            CHECK (status IN ('draft', 'running', 'completed', 'failed'));
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_tasks_idempotency
    ON inspection_tasks (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_inspection_tasks_updated
    ON inspection_tasks (updated_at DESC, task_id DESC);

CREATE TABLE IF NOT EXISTS inspection_task_runs (
    run_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES inspection_tasks(task_id) ON DELETE RESTRICT,
    run_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    agent_model JSONB NOT NULL DEFAULT '{}'::jsonb,
    workflow JSONB NOT NULL DEFAULT '{}'::jsonb,
    tool_results JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CONSTRAINT uq_inspection_task_runs_number UNIQUE (task_id, run_number),
    CONSTRAINT ck_inspection_task_runs_number CHECK (run_number > 0),
    CONSTRAINT ck_inspection_task_runs_status CHECK (
        status IN ('running', 'completed', 'failed')
    ),
    CONSTRAINT ck_inspection_task_runs_agent_model CHECK (
        jsonb_typeof(agent_model) = 'object'
    ),
    CONSTRAINT ck_inspection_task_runs_workflow CHECK (
        jsonb_typeof(workflow) = 'object'
    ),
    CONSTRAINT ck_inspection_task_runs_tool_results CHECK (
        jsonb_typeof(tool_results) = 'array'
    ),
    CONSTRAINT ck_inspection_task_runs_terminal_time CHECK (
        (status = 'running' AND completed_at IS NULL)
        OR (status IN ('completed', 'failed') AND completed_at IS NOT NULL)
    ),
    CONSTRAINT ck_inspection_task_runs_error CHECK (
        (status = 'failed' AND error_message IS NOT NULL AND btrim(error_message) <> '')
        OR (status IN ('running', 'completed') AND error_message IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS ix_inspection_task_runs_history
    ON inspection_task_runs (task_id, run_number DESC);
