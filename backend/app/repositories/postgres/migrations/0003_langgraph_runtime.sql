ALTER TABLE inspection_task_runs
    ADD COLUMN IF NOT EXISTS workflow_runtime TEXT NOT NULL DEFAULT 'legacy',
    ADD COLUMN IF NOT EXISTS checkpoint_thread_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_workflow_runtime'
    ) THEN
        ALTER TABLE inspection_task_runs
            ADD CONSTRAINT ck_inspection_task_runs_workflow_runtime
            CHECK (workflow_runtime IN ('legacy', 'langgraph'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_checkpoint_thread_nonblank'
    ) THEN
        ALTER TABLE inspection_task_runs
            ADD CONSTRAINT ck_inspection_task_runs_checkpoint_thread_nonblank
            CHECK (
                checkpoint_thread_id IS NULL
                OR btrim(checkpoint_thread_id) <> ''
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_runtime_thread'
    ) THEN
        ALTER TABLE inspection_task_runs
            ADD CONSTRAINT ck_inspection_task_runs_runtime_thread
            CHECK (
                (workflow_runtime = 'legacy' AND checkpoint_thread_id IS NULL)
                OR
                (workflow_runtime = 'langgraph' AND checkpoint_thread_id IS NOT NULL)
            );
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_inspection_task_runs_checkpoint_thread
    ON inspection_task_runs (checkpoint_thread_id)
    WHERE checkpoint_thread_id IS NOT NULL;
