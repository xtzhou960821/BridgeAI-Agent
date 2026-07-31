-- BridgeAI-Agent V0.2 skeleton migration.
-- This migration creates a minimal task table for local development smoke tests.

CREATE TABLE IF NOT EXISTS inspection_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
