DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_inspection_task_runs_langgraph_thread_identity'
          AND conrelid = 'public.inspection_task_runs'::regclass
    ) THEN
        ALTER TABLE public.inspection_task_runs
            ADD CONSTRAINT ck_inspection_task_runs_langgraph_thread_identity
            CHECK (
                workflow_runtime <> 'langgraph'
                OR checkpoint_thread_id = run_id
            ) NOT VALID;
    END IF;

    ALTER TABLE public.inspection_task_runs
        VALIDATE CONSTRAINT ck_inspection_task_runs_langgraph_thread_identity;
END
$$;
