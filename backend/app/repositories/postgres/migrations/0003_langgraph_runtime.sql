ALTER TABLE inspection_task_runs
    ADD COLUMN IF NOT EXISTS workflow_runtime TEXT NOT NULL DEFAULT 'legacy',
    ADD COLUMN IF NOT EXISTS checkpoint_thread_id TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_workflow_runtime'
          AND conrelid = 'public.inspection_task_runs'::regclass
    ) THEN
        ALTER TABLE inspection_task_runs
            ADD CONSTRAINT ck_inspection_task_runs_workflow_runtime
            CHECK (workflow_runtime IN ('legacy', 'langgraph'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_checkpoint_thread_nonblank'
          AND conrelid = 'public.inspection_task_runs'::regclass
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
          AND conrelid = 'public.inspection_task_runs'::regclass
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

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class AS index_relation
        JOIN pg_index AS index_definition
            ON index_definition.indexrelid = index_relation.oid
        JOIN pg_attribute AS key_attribute
            ON key_attribute.attrelid = index_definition.indrelid
           AND key_attribute.attnum = index_definition.indkey[0]
        WHERE index_relation.relname = 'uq_inspection_task_runs_checkpoint_thread'
          AND index_relation.relnamespace = 'public'::regnamespace
          AND index_definition.indrelid = 'public.inspection_task_runs'::regclass
          AND index_definition.indisunique
          AND index_definition.indnkeyatts = 1
          AND index_definition.indnatts = 1
          AND key_attribute.attname = 'checkpoint_thread_id'
          AND pg_get_expr(
              index_definition.indpred,
              index_definition.indrelid
          ) = '(checkpoint_thread_id IS NOT NULL)'
    ) THEN
        IF EXISTS (
            SELECT 1
            FROM pg_class AS index_relation
            WHERE index_relation.relname = 'uq_inspection_task_runs_checkpoint_thread'
              AND index_relation.relnamespace = 'public'::regnamespace
        ) THEN
            RAISE EXCEPTION
                'Index uq_inspection_task_runs_checkpoint_thread is incompatible with the required unique partial index'
                USING ERRCODE = '42P07';
        END IF;
        CREATE UNIQUE INDEX uq_inspection_task_runs_checkpoint_thread
            ON inspection_task_runs (checkpoint_thread_id)
            WHERE checkpoint_thread_id IS NOT NULL;
    END IF;
END
$$;
