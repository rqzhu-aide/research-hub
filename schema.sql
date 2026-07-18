-- Research Hub SQLite Schema

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    goal TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'paused', 'completed', 'archived')),
    workflow_name TEXT DEFAULT 'default',
    current_iteration INTEGER DEFAULT 0,
    max_iterations INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks within a project
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'blocked', 'completed', 'failed')),
    depends_on TEXT, -- comma-separated task IDs
    input_dir TEXT,  -- path to input files for this task
    output_dir TEXT, -- path where agent writes results
    result_summary TEXT,
    error_log TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Iteration tracking
CREATE TABLE IF NOT EXISTS iterations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    status TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed')),
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Agent assignments per project
CREATE TABLE IF NOT EXISTS project_agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    profile TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);

-- Project phases (ordered workflow stages)
CREATE TABLE IF NOT EXISTS phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    slug TEXT NOT NULL,
    name TEXT,
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'running', 'completed', 'failed')),
    current_round INTEGER DEFAULT 0,
    max_rounds INTEGER DEFAULT 3,
    output_path TEXT,
    config_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, slug)
);

-- Rounds within a phase (for idea phase round-robin)
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    proposer_status TEXT DEFAULT 'pending' CHECK(proposer_status IN ('pending', 'running', 'completed', 'failed', 'blocked')),
    proposer_kanban_id TEXT,
    proposer_started_at TIMESTAMP,
    proposer_completed_at TIMESTAMP,
    proposer_duration INTEGER,
    proposer_output TEXT,
    proposer_error TEXT,
    critic_status TEXT DEFAULT 'pending' CHECK(critic_status IN ('pending', 'running', 'completed', 'failed', 'blocked')),
    critic_kanban_id TEXT,
    critic_started_at TIMESTAMP,
    critic_completed_at TIMESTAMP,
    critic_duration INTEGER,
    critic_output TEXT,
    critic_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unified phase task table (handles parallel / sequential / debate patterns)
-- Replaces the rigid rounds table for new phases. Old rounds table kept for back-compat.
CREATE TABLE IF NOT EXISTS phase_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    -- What kind of task this is within the pattern:
    --   parallel_member  - independent exploration in a parallel phase
    --   synthesis        - merges parallel members' outputs
    --   sequential_step  - one step in a sequential pipeline
    --   debate_proposal  - owner's proposal in a debate round
    --   debate_critique  - a critic's response in a debate round
    task_type TEXT NOT NULL CHECK(task_type IN (
        'parallel_member', 'synthesis', 'sequential_step',
        'debate_proposal', 'debate_critique'
    )),
    role TEXT NOT NULL,              -- 'lead', 'statistician', 'programmer'
    profile TEXT NOT NULL,           -- actual hermes profile name
    round_num INTEGER DEFAULT 1,     -- debate round (1-based); 1 for non-debate
    sequence_order INTEGER DEFAULT 0,-- step order in sequential pipelines
    lens TEXT,                       -- what this task should focus on
    title TEXT,                      -- kanban task title
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'blocked', 'running', 'completed', 'failed')),
    kanban_id TEXT,                  -- hermes kanban task id
    kanban_parent_id TEXT,           -- linked parent task (for gating)
    depends_on_ids TEXT,             -- comma-separated phase_task ids that must complete first
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    output_path TEXT,                -- relative path within project dir
    result_summary TEXT,
    error_log TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_phase_tasks_phase ON phase_tasks(phase_id);
CREATE INDEX IF NOT EXISTS idx_phase_tasks_project ON phase_tasks(project_id);

-- User dashboard state
CREATE TABLE IF NOT EXISTS dashboard_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
