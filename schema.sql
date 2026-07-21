-- Research Hub SQLite schema
--
-- SQLite is only the project registry. Phase and run state are stored in a
-- matching .research-hub-control directory outside the agent workspace.

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK(status IN ('active', 'paused', 'completed', 'archived')),
    workflow_name TEXT NOT NULL DEFAULT 'default',
    current_iteration INTEGER NOT NULL DEFAULT 0,
    max_iterations INTEGER NOT NULL DEFAULT 10,
    directory_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- The directory-name index is created by the additive migration in hub.py.
-- Keeping it there lets older databases gain the column before it is indexed.
