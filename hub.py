#!/usr/bin/env python3
"""
Research Hub — data-access layer for webapp.py.

Originally this module orchestrated multi-agent research workflows directly
(the Python engine: setup_phase / poll_phase / advance_workflow / run_step,
and the earlier 2-role idea-phase system: setup_idea_phase / poll_idea_phase).
That orchestration has moved to launch_run.py, which spawns a research_lead
agent that drives the phases via the kanban CLI.

hub.py is now retained solely as the data-access backend for the Flask web UI
(webapp.py): it loads config.yaml, manages project records in SQLite, and
reports phase status/summaries for display.
"""

import sqlite3
import yaml
from pathlib import Path
from typing import List, Optional

HUB_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = HUB_DIR / "config.yaml"
SCHEMA_PATH = HUB_DIR / "schema.sql"

# Workspace paths resolved from config.yaml (hub.workspace_dir).
# Defaults to the app dir for backward compatibility.

_workspace_cache: Optional[Path] = None


def _resolve_workspace() -> Path:
    """Resolve workspace_dir from config. Cached after first access."""
    global _workspace_cache
    if _workspace_cache is not None:
        return _workspace_cache
    try:
        with open(CONFIG_PATH) as f:
            cfg = yaml.safe_load(f)
        ws = (cfg or {}).get("hub", {}).get("workspace_dir")
        if ws:
            _workspace_cache = Path(ws).expanduser().resolve()
        else:
            _workspace_cache = HUB_DIR
    except Exception:
        _workspace_cache = HUB_DIR
    return _workspace_cache


def get_workspace_dir() -> Path:
    """Root directory for projects + DB. Set via config.yaml hub.workspace_dir."""
    return _resolve_workspace()


def get_db_path() -> Path:
    return get_workspace_dir() / "hub.db"


def get_projects_dir() -> Path:
    return get_workspace_dir() / "projects"


# ── DB helpers ───────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        schema = SCHEMA_PATH.read_text()
        conn.executescript(schema)
    print(f"[hub] Database initialized at {get_db_path()}")


# ── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def get_agents(cfg: dict) -> List[dict]:
    return cfg.get("agents", [])


def get_agent(cfg: dict, agent_id: str) -> Optional[dict]:
    for a in get_agents(cfg):
        if a["id"] == agent_id:
            return a
    return None


# ── Phase config helpers ─────────────────────────────────────────────────────

def get_phases_config(cfg: dict) -> List[dict]:
    """Return the phases config list (pattern-based)."""
    return cfg.get("phases", [])


def get_phase_config(cfg: dict, slug: str) -> Optional[dict]:
    """Return the config for a specific phase slug."""
    for p in get_phases_config(cfg):
        if p["slug"] == slug:
            return p
    return None


# ── Project lifecycle ────────────────────────────────────────────────────────

def create_project(name: str, description: str = "", brief: str = "",
                   max_iterations: int = 10) -> int:
    """
    Create a new project with a clean folder structure.

    Folder layout created:
        <workspace>/projects/project-NNN-<slug>/
        ├── setting.md          ← project brief (what/domain/priorities/constraints)
        ├── references/         ← seed papers, literature, prior work
        ├── ideas/              ← brainstorming, explorations
        ├── draft/              ← paper drafts, writing deliverables
        ├── numerical/          ← experiments, code outputs, data, figures
        └── logs/               ← phase transcripts, agent activity logs

    Phase folders (phases/01-.../) are created just-in-time by the
    research_lead agent when each phase starts, not upfront here.
    """
    # Ensure workspace + projects dir exist
    get_projects_dir().mkdir(parents=True, exist_ok=True)

    # Ensure DB exists
    init_db()

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, description, goal, max_iterations) VALUES (?, ?, ?, ?)",
            (name, description, brief, max_iterations)
        )
        project_id = cur.lastrowid

    # Create clean project folder
    slug = name.replace(" ", "_").replace("/", "-").lower()
    proj_dir = get_projects_dir() / f"project-{project_id:03d}-{slug}"
    proj_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("references", "ideas", "draft", "numerical", "logs"):
        (proj_dir / sub).mkdir(exist_ok=True)

    # Generate setting.md from the project brief
    setting_content = _build_setting_md(name, description, brief)
    (proj_dir / "setting.md").write_text(setting_content)

    print(f"[hub] Created project #{project_id}: {name}")
    print(f"      Folder: {proj_dir}")
    return project_id


def _build_setting_md(name: str, description: str, brief: str) -> str:
    """Generate setting.md from the user-provided project description.

    The description is written through largely as-is (the user owns its structure),
    wrapped with a title and the one-line summary if provided.
    """
    parts = [f"# {name}\n"]
    if description:
        parts.append(f"_{description}_\n")
    parts.append("## Project Description\n")
    parts.append(brief.strip() or "[Describe what this project is about, the focused domain, priorities, and any constraints.]")
    parts.append("")
    return "\n".join(parts)


def list_projects() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()


def get_project(project_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return row


# ── Phase records ────────────────────────────────────────────────────────────

def get_phase(project_id: int, slug: str) -> Optional[sqlite3.Row]:
    """Look up a phase record by project + slug. Used by get_phase_status."""
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM phases WHERE project_id = ? AND slug = ?",
            (project_id, slug)
        ).fetchone()


# ── Project Directory ────────────────────────────────────────────────────────

def get_project_dir(project_id: int) -> Optional[Path]:
    """Find the project workspace directory."""
    pattern = f"project-{project_id:03d}-*"
    matches = list(get_projects_dir().glob(pattern))
    if matches:
        return matches[0]
    return None


# ── Phase status & summary (read-only, for display) ──────────────────────────

def get_phase_status(project_id: int, phase_slug: str) -> Optional[dict]:
    """Get full status of a phase for display."""
    phase = get_phase(project_id, phase_slug)
    if not phase:
        return None
    with get_db() as conn:
        tasks = conn.execute(
            "SELECT * FROM phase_tasks WHERE phase_id = ? ORDER BY round_num, sequence_order, id",
            (phase["id"],)
        ).fetchall()
    cfg = load_config()
    phase_cfg = get_phase_config(cfg, phase_slug) or {}
    return {
        "phase": dict(phase),
        "phase_cfg": phase_cfg,
        "tasks": [dict(t) for t in tasks],
        "pattern": phase_cfg.get("pattern", "debate"),
    }


def get_phase_summary(project_id: int, phase_slug: str) -> dict:
    """Lightweight summary for the overview — always returns a dict, even if
    the phase has not been started yet (status 'pending', zero counts).

    Fields:
        slug, name, pattern, status, tasks_total, tasks_completed,
        tasks_running, tasks_failed, current_round, max_rounds,
        started (bool), started_at, completed_at
    """
    cfg = load_config()
    phase_cfg = get_phase_config(cfg, phase_slug) or {}
    base = {
        "slug": phase_slug,
        "name": phase_cfg.get("name", phase_slug),
        "pattern": phase_cfg.get("pattern", "?"),
        "description": phase_cfg.get("description", ""),
        "status": "pending",
        "tasks_total": 0,
        "tasks_completed": 0,
        "tasks_running": 0,
        "tasks_failed": 0,
        "current_round": 0,
        "max_rounds": phase_cfg.get("rounds", 1),
        "started": False,
        "started_at": None,
        "completed_at": None,
    }
    st = get_phase_status(project_id, phase_slug)
    if not st or not st.get("phase"):
        return base
    ph = st["phase"]
    tasks = st.get("tasks", [])
    completed = [t for t in tasks if t["status"] == "completed"]
    running = [t for t in tasks if t["status"] == "running"]
    failed = [t for t in tasks if t["status"] == "failed"]
    rounds_seen = [t["round_num"] for t in tasks if t.get("round_num")]
    base.update({
        "status": ph.get("status", "pending"),
        "tasks_total": len(tasks),
        "tasks_completed": len(completed),
        "tasks_running": len(running),
        "tasks_failed": len(failed),
        "current_round": max(rounds_seen) if rounds_seen else ph.get("current_round", 0),
        "max_rounds": ph.get("max_rounds", base["max_rounds"]),
        "started": True,
        "started_at": ph.get("created_at"),
        "completed_at": ph.get("updated_at") if ph.get("status") == "completed" else None,
    })
    return base
