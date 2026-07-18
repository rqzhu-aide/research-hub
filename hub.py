#!/usr/bin/env python3
"""
Research Hub Orchestrator
Manages multi-agent workflows across user-defined Hermes profiles.
"""

import sqlite3
import yaml
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import subprocess
import re

HUB_DIR = Path(__file__).parent.resolve()
DB_PATH = HUB_DIR / "hub.db"
CONFIG_PATH = HUB_DIR / "config.yaml"
PROJECTS_DIR = HUB_DIR / "projects"
TEMPLATES_DIR = HUB_DIR / "exploration-templates"   # legacy
CONFIG_DIR = HUB_DIR / "config"                     # new: souls, phases, team

# ── DB helpers ───────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        schema = (HUB_DIR / "schema.sql").read_text()
        conn.executescript(schema)
    print("[hub] Database initialized.")

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

def get_workflow(cfg: dict, name: str = "default") -> List[dict]:
    return cfg.get("workflows", {}).get(name, [])

# ── Phase config helpers (new pattern-based system) ──────────────────────────

def get_phases_config(cfg: dict) -> List[dict]:
    """Return the new-style phases config list (pattern-based)."""
    return cfg.get("phases", [])

def get_phase_config(cfg: dict, slug: str) -> Optional[dict]:
    """Return the config for a specific phase slug."""
    for p in get_phases_config(cfg):
        if p["slug"] == slug:
            return p
    return None

def get_agent_by_id(cfg: dict, agent_id: str) -> Optional[dict]:
    """Look up an agent by its id (e.g. 'lead', 'statistician')."""
    for a in get_agents(cfg):
        if a["id"] == agent_id:
            return a
    return None

def get_agent_profile(cfg: dict, agent_id: str) -> Optional[str]:
    """Resolve an agent_id to its Hermes profile name."""
    a = get_agent_by_id(cfg, agent_id)
    return a["profile"] if a else None

def get_agent_display_name(cfg: dict, agent_id: str) -> str:
    """Resolve an agent_id to its display name."""
    a = get_agent_by_id(cfg, agent_id)
    return a["name"] if a else agent_id

# ── Project lifecycle ────────────────────────────────────────────────────────

def create_project(name: str, description: str = "", goal: str = "",
                   workflow: str = "default", max_iterations: int = 10) -> int:
    cfg = load_config()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, description, goal, workflow_name, max_iterations) VALUES (?, ?, ?, ?, ?)",
            (name, description, goal, workflow, max_iterations)
        )
        project_id = cur.lastrowid

        # Assign agents from config to this project
        for agent in get_agents(cfg):
            conn.execute(
                "INSERT INTO project_agents (project_id, agent_id, profile) VALUES (?, ?, ?)",
                (project_id, agent["id"], agent["profile"])
            )

        # Create project workspace
        proj_dir = PROJECTS_DIR / f"project-{project_id:03d}-{name.replace(' ', '_').lower()}"
        proj_dir.mkdir(parents=True, exist_ok=True)
        (proj_dir / "inputs").mkdir(exist_ok=True)
        (proj_dir / "outputs").mkdir(exist_ok=True)
        (proj_dir / "logs").mkdir(exist_ok=True)

        # Create workflow tasks
        stages = get_workflow(cfg, workflow)
        for i, stage in enumerate(stages):
            task_dir = proj_dir / f"stage-{i:02d}-{stage['stage']}"
            task_dir.mkdir(exist_ok=True)
            depends = stage.get("depends_on", [])
            depends_str = ",".join(depends) if isinstance(depends, list) else depends
            conn.execute(
                """INSERT INTO tasks (project_id, stage, agent_id, description, depends_on, input_dir, output_dir)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (project_id, stage["stage"], stage["agent"], stage.get("description", ""),
                 depends_str, str(task_dir / "inputs"), str(task_dir / "outputs"))
            )

    print(f"[hub] Created project #{project_id}: {name}")
    return project_id

def list_projects() -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()

def get_project(project_id: int) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return row

def get_project_tasks(project_id: int) -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()

# ── Task execution ───────────────────────────────────────────────────────────

def get_ready_tasks(project_id: int) -> List[sqlite3.Row]:
    """Tasks that are pending and have all dependencies completed."""
    with get_db() as conn:
        tasks = conn.execute(
            "SELECT * FROM tasks WHERE project_id = ? AND status = 'pending'", (project_id,)
        ).fetchall()
    ready = []
    for t in tasks:
        deps = t["depends_on"]
        if not deps:
            ready.append(t)
            continue
        dep_stages = [d.strip() for d in deps.split(",")]
        with get_db() as conn:
            dep_tasks = conn.execute(
                "SELECT status FROM tasks WHERE project_id = ? AND stage IN ({})".format(
                    ",".join("?" * len(dep_stages))
                ),
                (project_id, *dep_stages)
            ).fetchall()
        if all(d["status"] == "completed" for d in dep_tasks):
            ready.append(t)
    return ready

def start_task(task_id: int):
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'running', started_at = ? WHERE id = ?",
            (datetime.now().isoformat(), task_id)
        )

def complete_task(task_id: int, summary: str = ""):
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ?, result_summary = ? WHERE id = ?",
            (datetime.now().isoformat(), summary, task_id)
        )

def fail_task(task_id: int, error: str = ""):
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'failed', error_log = ? WHERE id = ?",
            (error, task_id)
        )

# ── Iteration loop ───────────────────────────────────────────────────────────

def start_iteration(project_id: int) -> int:
    proj = get_project(project_id)
    if not proj:
        raise ValueError(f"Project {project_id} not found")
    next_iter = proj["current_iteration"] + 1
    with get_db() as conn:
        conn.execute(
            "INSERT INTO iterations (project_id, iteration_number, status) VALUES (?, ?, 'running')",
            (project_id, next_iter)
        )
        conn.execute(
            "UPDATE projects SET current_iteration = ?, updated_at = ? WHERE id = ?",
            (next_iter, datetime.now().isoformat(), project_id)
        )
    print(f"[hub] Started iteration {next_iter} for project #{project_id}")
    return next_iter

def advance_workflow(project_id: int) -> Dict:
    """Check ready tasks, advance state. Returns status dict."""
    ready = get_ready_tasks(project_id)
    running = get_project_tasks(project_id)
    running_count = sum(1 for t in running if t["status"] == "running")
    completed_count = sum(1 for t in running if t["status"] == "completed")
    failed_count = sum(1 for t in running if t["status"] == "failed")
    total = len(running)

    status = {
        "project_id": project_id,
        "ready_tasks": [dict(r) for r in ready],
        "running": running_count,
        "completed": completed_count,
        "failed": failed_count,
        "total": total,
        "is_complete": completed_count == total,
        "has_failure": failed_count > 0
    }
    return status

def run_step(project_id: int, task_id: Optional[int] = None) -> Dict:
    """Run one ready task (or a specific one if given). Returns dispatch info."""
    cfg = load_config()
    if task_id:
        with get_db() as conn:
            task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    else:
        ready = get_ready_tasks(project_id)
        if not ready:
            return {"status": "no_ready_tasks", "project_id": project_id}
        task = ready[0]

    agent = get_agent(cfg, task["agent_id"])
    if not agent:
        fail_task(task["id"], f"Agent profile '{task['agent_id']}' not found in config")
        return {"status": "agent_not_found", "task_id": task["id"]}

    start_task(task["id"])

    # Here we would dispatch to Hermes — for now, log the intent
    dispatch = {
        "status": "dispatched",
        "task_id": task["id"],
        "stage": task["stage"],
        "agent_id": agent["id"],
        "profile": agent["profile"],
        "input_dir": task["input_dir"],
        "output_dir": task["output_dir"],
        "command": f"hermes run --profile {agent['profile']} --task-dir {task['output_dir']}"
    }

    log_path = Path(task["output_dir"]).parent / "logs" / f"{task['stage']}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(dispatch, indent=2))

    return dispatch

# ── Summary ──────────────────────────────────────────────────────────────────

def project_summary(project_id: int) -> str:
    proj = get_project(project_id)
    if not proj:
        return f"Project {project_id} not found."
    tasks = get_project_tasks(project_id)
    lines = [
        f"# Project: {proj['name']} (#{project_id})",
        f"Status: {proj['status']} | Iteration: {proj['current_iteration']}/{proj['max_iterations']}",
        f"Goal: {proj['goal']}",
        "",
        "## Tasks",
    ]
    for t in tasks:
        icon = {"pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌", "blocked": "🚫"}
        lines.append(f"{icon.get(t['status'], '?')} {t['stage']:20} | {t['agent_id']:15} | {t['status']}")
    return "\n".join(lines)

# ── Phase Management ─────────────────────────────────────────────────────────

def init_phase(project_id: int, slug: str, name: Optional[str] = None,
               description: str = "", max_rounds: int = 3) -> int:
    """Create a phase record for a project."""
    name = name or slug.replace("-", " ").title()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO phases (project_id, slug, name, description, max_rounds)
               VALUES (?, ?, ?, ?, ?)""",
            (project_id, slug, name, description, max_rounds)
        )
        phase_id = cur.lastrowid
    return phase_id

def get_phase(project_id: int, slug: str) -> Optional[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM phases WHERE project_id = ? AND slug = ?",
            (project_id, slug)
        ).fetchone()

def get_phases(project_id: int) -> List[sqlite3.Row]:
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM phases WHERE project_id = ? ORDER BY id",
            (project_id,)
        ).fetchall()

# ── Project Directory ────────────────────────────────────────────────────────

def get_project_dir(project_id: int) -> Optional[Path]:
    """Find the project workspace directory."""
    pattern = f"project-{project_id:03d}-*"
    matches = list(PROJECTS_DIR.glob(pattern))
    if matches:
        return matches[0]
    return None

# ── Template Loading ──────────────────────────────────────────────────────────

def load_template(rel_path: str) -> str:
    """Load a template file from exploration-templates/. Raises if missing."""
    tpl_path = TEMPLATES_DIR / rel_path
    if not tpl_path.exists():
        raise FileNotFoundError(
            f"Template not found: {tpl_path}\n"
            f"Ensure exploration-templates/ is populated."
        )
    return tpl_path.read_text()

def fill_template(text: str, variables: dict) -> str:
    """Replace {{key}} placeholders with values. Leaves unknown keys as-is."""
    for key, value in variables.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))
    return text

def get_round_position(round_num: int, max_rounds: int) -> str:
    """Determine template suffix for a round: 'r1', 'rmid', or 'rfinal'."""
    if max_rounds <= 1:
        return "rfinal"
    if round_num == 1:
        return "r1"
    if round_num == max_rounds:
        return "rfinal"
    return "rmid"

def load_setting_template() -> str:
    """Load the default setting.md scaffold."""
    new_path = CONFIG_DIR / "projects" / "setting-template.md"
    if new_path.exists():
        return new_path.read_text()
    # Legacy fallback
    return load_template("setting-template.md")


# ── Layered memory composition (new) ─────────────────────────────────────────

def _read_config_file(rel_path: str) -> str:
    """Read a file from config/, returning empty string if missing."""
    p = CONFIG_DIR / rel_path
    return p.read_text() if p.exists() else ""


def _load_soul(role_id: str) -> str:
    """Load the soul markdown for a role. Returns empty string if missing."""
    return _read_config_file(f"souls/{role_id}.md")


def _load_team_shared() -> str:
    """Load the shared team charter + norms."""
    charter = _read_config_file("team/charter.md")
    norms = _read_config_file("team/norms.md")
    parts = []
    if charter:
        parts.append(charter)
    if norms:
        parts.append(norms)
    return "\n\n---\n\n".join(parts)


def _load_phase_overview(phase_slug: str) -> str:
    """Load the phase's _phase.md shared overview."""
    return _read_config_file(f"phases/{phase_slug}/_phase.md")


def _compose_memory_entry(project_id: int, role_id: str, phase_cfg: dict,
                          settings_content: str, proj_dir: Path,
                          project_name: str) -> str:
    """
    Compose the full MEMORY.md entry by stacking layers:
        team shared + soul + phase overview + role lens + project context
    """
    phase_slug = phase_cfg["slug"]
    phase_name = phase_cfg.get("name", phase_slug)
    pattern = phase_cfg.get("pattern", "")

    team_shared = _load_team_shared()
    soul = _load_soul(role_id)
    phase_overview = _load_phase_overview(phase_slug)
    lens = _get_role_lens(phase_cfg, role_id)

    parts = [f"# Research Hub — Project {project_id} Phase {phase_slug}\n"]
    parts.append(f"**Project:** {project_name}")
    parts.append(f"**Phase:** {phase_name} ({pattern})")
    parts.append(f"**Your role:** {role_id}")
    if lens:
        parts.append(f"**Your specific lens this phase:** {lens}")
    parts.append(f"**Project dir:** {proj_dir}\n")

    if team_shared:
        parts.append("\n## Team Context\n" + team_shared)
    if soul:
        parts.append("\n## Your Soul (stable identity)\n" + soul)
    if phase_overview:
        parts.append(f"\n## Phase Overview: {phase_name}\n" + phase_overview)
    if settings_content:
        parts.append("\n## Project Settings\n" + settings_content)

    return "\n".join(parts)

def write_agent_memory(project_id: int, profile: str, role: str,
                       settings_content: str, proj_dir: Path,
                       project_name: str = "", collaborator_profile: str = "",
                       max_rounds: int = 3):
    """Append a research-hub memory entry to a profile's MEMORY.md."""
    memory_dir = Path.home() / ".hermes" / "profiles" / profile / "memories"
    if not memory_dir.exists():
        raise ValueError(f"Profile '{profile}' not found or has no memories directory")

    template = load_template(f"{role}-memory.md")
    entry = fill_template(template, {
        "project_id": project_id,
        "project_name": project_name,
        "settings_content": settings_content,
        "project_dir": str(proj_dir),
        "collaborator_profile": collaborator_profile,
        "max_rounds": max_rounds,
    })

    memory_file = memory_dir / "MEMORY.md"
    with open(memory_file, "a") as f:
        if memory_file.stat().st_size > 0:
            f.write("\n§\n")
        f.write(entry)

def _clean_agent_memory(project_id: int, profile: str):
    """Remove existing Research Hub entries for this project from a profile's MEMORY.md."""
    memory_dir = Path.home() / ".hermes" / "profiles" / profile / "memories"
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        return

    content = memory_file.read_text()
    marker = f"# Research Hub — Project {project_id}"
    sections = content.split("\n§\n")
    # Keep sections that don't contain this project's marker
    kept = [s for s in sections if marker not in s]
    if len(kept) == len(sections):
        return  # nothing to remove
    memory_file.write_text("\n§\n".join(kept))

# ── Kanban Integration ───────────────────────────────────────────────────────

def create_kanban_board(board_slug: str, project_name: str) -> str:
    """Create a kanban board. Idempotent — returns existing slug if already present."""
    result = subprocess.run(
        ["hermes", "kanban", "boards", "create", "--name", f"RHUB {project_name}", board_slug],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # May already exist
        if "already exists" in result.stderr or "already exists" in result.stdout:
            return board_slug
        raise RuntimeError(f"Failed to create kanban board: {result.stderr}")
    return board_slug

def create_kanban_task(board_slug: str, title: str, body: str,
                       assignee: str, parent: Optional[str] = None,
                       workspace: str = "scratch") -> str:
    """Create a kanban task and return its ID."""
    cmd = [
        "hermes", "kanban", "--board", board_slug,
        "create", "--assignee", assignee,
        "--body", body,
        "--workspace", workspace,
        title
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create kanban task: {result.stderr}")

    output = result.stdout.strip()
    match = re.search(r'Created (t_[a-f0-9]+)', output)
    if not match:
        raise RuntimeError(f"Could not parse kanban task ID from: {output}")
    task_id = match.group(1)

    if parent:
        link_result = subprocess.run(
            ["hermes", "kanban", "--board", board_slug, "link", parent, task_id],
            capture_output=True, text=True
        )
        if link_result.returncode != 0:
            raise RuntimeError(f"Failed to link kanban tasks: {link_result.stderr}")

    return task_id

def store_kanban_task(project_id: int, phase_id: int, round_id: Optional[int],
                      kanban_id: str, board_slug: str, role: str, round_num: int):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO kanban_tasks
               (project_id, phase_id, round_id, kanban_id, board_slug, role, round_number)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (project_id, phase_id, round_id, kanban_id, board_slug, role, round_num)
        )

def build_task_body(role: str, round_num: int, max_rounds: int, proj_dir: Path) -> str:
    """Build the kanban task body for a specific role and round position."""
    position = get_round_position(round_num, max_rounds)
    template = load_template(f"task-bodies/{role}-{position}.md")

    variables = {
        "round_num": round_num,
        "max_rounds": max_rounds,
        "output_path": f"phases/00-idea/{role}/round-{round_num:02d}.md",
    }

    # Proposer rounds >1 reference the previous critique
    if role == "proposer" and round_num > 1:
        variables["prev_critique_path"] = (
            f"phases/00-idea/critic/round-{round_num - 1:02d}.md"
        )

    # Critic always references the current proposal
    if role == "critic":
        variables["proposal_path"] = (
            f"phases/00-idea/proposer/round-{round_num:02d}.md"
        )

    return fill_template(template, variables)

# ── Idea Phase Setup ─────────────────────────────────────────────────────────

def setup_idea_phase(project_id: int, proposer_profile: str, critic_profile: str,
                     manager_profile: str = "",
                     max_rounds: int = 3) -> int:
    """Full setup: memory files, kanban board, task chain. Idempotent for re-runs."""
    proj = get_project(project_id)
    if not proj:
        raise ValueError(f"Project {project_id} not found")

    proj_dir = get_project_dir(project_id)
    if not proj_dir:
        raise ValueError(f"Project directory not found for project {project_id}")

    settings_path = proj_dir / "setting.md"
    if not settings_path.exists():
        settings_path.write_text(load_setting_template())

    # ── Guard: if phase already exists with existing rounds, clean up first ──
    existing_phase = get_phase(project_id, "00-idea")
    if existing_phase and existing_phase["status"] != "pending":
        # Delete old rounds so we don't duplicate the task chain
        with get_db() as conn:
            old_rounds = conn.execute(
                "SELECT id FROM rounds WHERE phase_id = ?", (existing_phase["id"],)
            ).fetchall()
            for r in old_rounds:
                conn.execute("DELETE FROM rounds WHERE id = ?", (r["id"],))
                conn.execute("DELETE FROM kanban_tasks WHERE round_id = ?", (r["id"],))
        # Also clean up old memory entries to avoid duplicates
        _clean_agent_memory(project_id, proposer_profile)
        _clean_agent_memory(project_id, critic_profile)
        # Reset phase to pending for re-setup
        with get_db() as conn:
            conn.execute(
                "UPDATE phases SET status='pending', config_json=NULL WHERE id=?",
                (existing_phase["id"],)
            )

    # Create / update phase record
    phase = get_phase(project_id, "00-idea")
    if phase:
        with get_db() as conn:
            conn.execute(
                "UPDATE phases SET status='active', max_rounds=? WHERE id=?",
                (max_rounds, phase["id"])
            )
        phase_id = phase["id"]
    else:
        phase_id = init_phase(
            project_id, "00-idea", "Idea Formation",
            "Literature research and idea proposal", max_rounds
        )

    # Create directory structure
    idea_dir = proj_dir / "phases" / "00-idea"
    (idea_dir / "proposer").mkdir(parents=True, exist_ok=True)
    (idea_dir / "critic").mkdir(parents=True, exist_ok=True)

    # Write memory files
    settings_content = settings_path.read_text()
    write_agent_memory(project_id, proposer_profile, "proposer", settings_content, proj_dir,
                       proj["name"], critic_profile, max_rounds)
    write_agent_memory(project_id, critic_profile, "critic", settings_content, proj_dir,
                       proj["name"], proposer_profile, max_rounds)

    # Create kanban board
    board_slug = f"rhub-p{project_id}"
    create_kanban_board(board_slug, proj["name"])

    # Create task chain
    create_idea_task_chain(
        board_slug, proj_dir, max_rounds,
        proposer_profile, critic_profile,
        project_id, phase_id
    )

    # Update phase
    with get_db() as conn:
        conn.execute(
            "UPDATE phases SET status='running', config_json=? WHERE id=?",
            (json.dumps({"proposer": proposer_profile, "critic": critic_profile,
                        "manager": manager_profile}), phase_id)
        )

    return phase_id

def create_idea_task_chain(board_slug: str, proj_dir: Path, max_rounds: int,
                           proposer_profile: str, critic_profile: str,
                           project_id: int, phase_id: int):
    """Create the round-robin task chain on kanban."""
    prev_kanban_id = None

    for round_num in range(1, max_rounds + 1):
        # Proposer task
        proposer_body = build_task_body("proposer", round_num, max_rounds, proj_dir)
        proposer_kid = create_kanban_task(
            board_slug, f"Idea Proposer Round {round_num}",
            proposer_body, proposer_profile,
            parent=prev_kanban_id,
            workspace=f"dir:{proj_dir}"
        )
        prev_kanban_id = proposer_kid

        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO rounds (phase_id, round_number, proposer_kanban_id) VALUES (?, ?, ?)",
                (phase_id, round_num, proposer_kid)
            )
            round_id = cur.lastrowid or 0

        store_kanban_task(project_id, phase_id, round_id, proposer_kid,
                          board_slug, "proposer", round_num)

        # Critic task
        critic_body = build_task_body("critic", round_num, max_rounds, proj_dir)
        critic_kid = create_kanban_task(
            board_slug, f"Idea Critic Round {round_num}",
            critic_body, critic_profile,
            parent=prev_kanban_id,
            workspace=f"dir:{proj_dir}"
        )
        prev_kanban_id = critic_kid

        with get_db() as conn:
            conn.execute(
                "UPDATE rounds SET critic_kanban_id = ? WHERE id = ?",
                (critic_kid, round_id)
            )

        store_kanban_task(project_id, phase_id, round_id, critic_kid,
                          board_slug, "critic", round_num)

# ── Status Polling ───────────────────────────────────────────────────────────

def parse_kanban_list(output: str) -> Dict[str, str]:
    """Parse `hermes kanban list` output into {task_id: status}."""
    statuses = {}
    for line in output.splitlines():
        match = re.search(r'[✓●◻▶]\s+(t_[a-f0-9]+)\s+(\w+)', line)
        if match:
            statuses[match.group(1)] = match.group(2)
    return statuses

_KANBAN_STATUS_MAP = {
    "ready": "pending",
    "todo": "pending",
    "running": "running",
    "done": "completed",
    "blocked": "blocked",
    "failed": "failed",
}

def poll_idea_phase(project_id: int) -> Optional[Dict]:
    """Poll kanban for latest task statuses and update DB."""
    phase = get_phase(project_id, "00-idea")
    if not phase:
        return None

    board_slug = f"rhub-p{project_id}"
    result = subprocess.run(
        ["hermes", "kanban", "--board", board_slug, "list"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return get_idea_status(project_id)

    kanban_statuses = parse_kanban_list(result.stdout)

    with get_db() as conn:
        rounds = conn.execute(
            "SELECT * FROM rounds WHERE phase_id = ? ORDER BY round_number",
            (phase["id"],)
        ).fetchall()

        any_running = False
        any_failed = False
        all_complete = True

        for r in rounds:
            # Proposer
            pk = r["proposer_kanban_id"]
            if pk and pk in kanban_statuses:
                new_status = _KANBAN_STATUS_MAP.get(kanban_statuses[pk], "pending")
                if new_status != r["proposer_status"]:
                    conn.execute(
                        "UPDATE rounds SET proposer_status = ? WHERE id = ?",
                        (new_status, r["id"])
                    )
                    if new_status == "running" and not r["proposer_started_at"]:
                        conn.execute(
                            "UPDATE rounds SET proposer_started_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), r["id"])
                        )
                    if new_status in ("completed", "failed"):
                        conn.execute(
                            "UPDATE rounds SET proposer_completed_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), r["id"])
                        )

            # Critic
            ck = r["critic_kanban_id"]
            if ck and ck in kanban_statuses:
                new_status = _KANBAN_STATUS_MAP.get(kanban_statuses[ck], "pending")
                if new_status != r["critic_status"]:
                    conn.execute(
                        "UPDATE rounds SET critic_status = ? WHERE id = ?",
                        (new_status, r["id"])
                    )
                    if new_status == "running" and not r["critic_started_at"]:
                        conn.execute(
                            "UPDATE rounds SET critic_started_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), r["id"])
                        )
                    if new_status in ("completed", "failed"):
                        conn.execute(
                            "UPDATE rounds SET critic_completed_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), r["id"])
                        )

            # Re-fetch for aggregate check
            fresh = conn.execute(
                "SELECT proposer_status, critic_status FROM rounds WHERE id = ?",
                (r["id"],)
            ).fetchone()
            if fresh["critic_status"] != "completed":
                all_complete = False
            if fresh["proposer_status"] == "running" or fresh["critic_status"] == "running":
                any_running = True
            if fresh["proposer_status"] == "failed" or fresh["critic_status"] == "failed":
                any_failed = True

        # Update phase status
        new_phase_status = "running"
        if all_complete:
            new_phase_status = "completed"
        elif any_failed:
            new_phase_status = "failed"
        elif not any_running:
            new_phase_status = "active"

        conn.execute(
            "UPDATE phases SET status = ? WHERE id = ?",
            (new_phase_status, phase["id"])
        )

    return get_idea_status(project_id)

def get_idea_status(project_id: int) -> Optional[Dict]:
    """Get full idea phase status for display."""
    phase = get_phase(project_id, "00-idea")
    if not phase:
        return None

    with get_db() as conn:
        rounds = conn.execute(
            "SELECT * FROM rounds WHERE phase_id = ? ORDER BY round_number",
            (phase["id"],)
        ).fetchall()

    config = json.loads(phase["config_json"] or "{}")
    return {
        "phase": dict(phase),
        "rounds": [dict(r) for r in rounds],
        "proposer_profile": config.get("proposer"),
        "critic_profile": config.get("critic"),
        "manager_profile": config.get("manager"),
    }

def view_round_output(project_id: int, round_num: int, role: str) -> Optional[str]:
    """Read the output file for a specific round/role."""
    proj_dir = get_project_dir(project_id)
    if not proj_dir:
        return None
    file_path = proj_dir / "phases" / "00-idea" / role / f"round-{round_num:02d}.md"
    if file_path.exists():
        return file_path.read_text()
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# NEW PATTERN-BASED PHASE ENGINE (parallel / sequential / debate)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_or_create_phase(project_id: int, slug: str, name: str,
                         description: str, max_rounds: int = 1) -> int:
    """Idempotent: reset existing phase to fresh state, or create new."""
    existing = get_phase(project_id, slug)
    if existing:
        # Wipe old phase_tasks for a clean re-setup
        with get_db() as conn:
            conn.execute("DELETE FROM phase_tasks WHERE phase_id = ?", (existing["id"],))
            conn.execute(
                "UPDATE phases SET status='active', name=?, description=?, max_rounds=? WHERE id=?",
                (name, description, max_rounds, existing["id"])
            )
        return existing["id"]
    return init_phase(project_id, slug, name, description, max_rounds)


def _create_phase_task(phase_id: int, project_id: int, task_type: str,
                       role: str, profile: str, title: str,
                       lens: str = "", output_path: str = "",
                       round_num: int = 1, sequence_order: int = 0,
                       depends_on_ids: str = "", kanban_id: str = "",
                       kanban_parent_id: str = "") -> int:
    """Insert a phase_tasks row."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO phase_tasks
               (phase_id, project_id, task_type, role, profile, title, lens,
                output_path, round_num, sequence_order, depends_on_ids,
                kanban_id, kanban_parent_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (phase_id, project_id, task_type, role, profile, title, lens,
             output_path, round_num, sequence_order, depends_on_ids,
             kanban_id, kanban_parent_id,
             "blocked" if depends_on_ids else "pending")
        )
        return cur.lastrowid


def _setup_parallel(phase_id: int, project_id: int, phase_cfg: dict,
                    proj_dir: Path, board_slug: str) -> None:
    """Parallel pattern: N independent members + 1 synthesis (gated on all members)."""
    members = phase_cfg.get("members", [])
    synth = phase_cfg.get("synthesis", {})
    member_task_ids = []
    member_kanban_ids = []

    # 1. Create one task per member — all start immediately (no deps)
    for m in members:
        role = m["role"]
        profile = get_agent_profile(load_config(), role)
        if not profile:
            raise ValueError(f"Agent '{role}' not found in config.yaml")
        title = f"[{phase_cfg['name']}] {role} exploration"
        body = _build_pattern_task_body(
            phase_cfg, role, "parallel_member",
            output_path=m.get("output", "")
        )
        kid = create_kanban_task(board_slug, title, body,
                                 profile, workspace=f"dir:{proj_dir}")
        tid = _create_phase_task(
            phase_id, project_id, "parallel_member", role, profile,
            title, lens=m.get("lens", ""), output_path=m.get("output", ""),
            kanban_id=kid
        )
        member_task_ids.append(tid)
        member_kanban_ids.append(kid)

    # 2. Create synthesis task — blocked until ALL members complete
    if synth:
        synth_role = synth.get("owner", "lead")
        synth_profile = get_agent_profile(load_config(), synth_role)
        deps = ",".join(str(t) for t in member_task_ids)
        # Link synthesis to last member in kanban (visual chain; gating is via depends_on_ids)
        parent = member_kanban_ids[-1] if member_kanban_ids else None
        synth_body = _build_pattern_task_body(
            phase_cfg, synth_role, "synthesis",
            output_path=synth.get("output", "")
        )
        kid = create_kanban_task(
            board_slug,
            f"[{phase_cfg['name']}] Synthesis ({synth_role})",
            synth_body,
            synth_profile,
            parent=parent,
            workspace=f"dir:{proj_dir}"
        )
        _create_phase_task(
            phase_id, project_id, "synthesis", synth_role, synth_profile,
            f"[{phase_cfg['name']}] Synthesis",
            lens=synth.get("task", ""),
            output_path=synth.get("output", ""),
            depends_on_ids=deps,
            kanban_id=kid,
            kanban_parent_id=parent
        )


def _setup_sequential(phase_id: int, project_id: int, phase_cfg: dict,
                      proj_dir: Path, board_slug: str) -> None:
    """Sequential pattern: A→B→C pipeline, each step depends on the prior."""
    steps = phase_cfg.get("steps", [])
    prev_task_id = None
    prev_kanban_id = None

    for i, step in enumerate(steps):
        role = step["role"]
        profile = get_agent_profile(load_config(), role)
        if not profile:
            raise ValueError(f"Agent '{role}' not found in config.yaml")
        title = f"[{phase_cfg['name']}] Step {i+1}: {role}"
        deps = str(prev_task_id) if prev_task_id else ""
        parent = prev_kanban_id

        body = _build_pattern_task_body(
            phase_cfg, role, "sequential_step",
            output_path=step.get("output", "")
        )
        kid = create_kanban_task(
            board_slug, title,
            body,
            profile,
            parent=parent,
            workspace=f"dir:{proj_dir}"
        )
        prev_task_id = _create_phase_task(
            phase_id, project_id, "sequential_step", role, profile,
            title, lens=step.get("lens", ""),
            output_path=step.get("output", ""),
            sequence_order=i + 1,
            depends_on_ids=deps,
            kanban_id=kid,
            kanban_parent_id=parent
        )
        prev_kanban_id = kid


def _setup_debate(phase_id: int, project_id: int, phase_cfg: dict,
                  proj_dir: Path, board_slug: str) -> None:
    """Debate pattern: per round — owner proposes, critics critique. Repeat max_rounds."""
    owner_role = phase_cfg["owner"]
    critic_roles = phase_cfg.get("critics", [])
    max_rounds = phase_cfg.get("max_rounds", 3)
    cfg = load_config()
    owner_profile = get_agent_profile(cfg, owner_role)

    prev_kanban_id = None
    for round_num in range(1, max_rounds + 1):
        # Owner proposal
        position = get_round_position(round_num, max_rounds)
        owner_lens = phase_cfg.get("owner_lens", "")
        title = f"[{phase_cfg['name']}] Round {round_num} — {owner_role} proposal"
        body = _build_debate_body("proposal", owner_role, position, round_num, max_rounds, owner_lens, phase_cfg["slug"])
        kid = create_kanban_task(board_slug, title, body, owner_profile,
                                 parent=prev_kanban_id, workspace=f"dir:{proj_dir}")
        proposal_tid = _create_phase_task(
            phase_id, project_id, "debate_proposal", owner_role, owner_profile,
            title, lens=owner_lens, round_num=round_num,
            output_path=f"phases/{phase_cfg['slug']}/{owner_role}/round-{round_num:02d}.md",
            kanban_id=kid
        )
        prev_kanban_id = kid

        # Critics (depend on proposal)
        for crole in critic_roles:
            cprofile = get_agent_profile(cfg, crole)
            if not cprofile:
                raise ValueError(f"Agent '{crole}' not found in config.yaml")
            clens = phase_cfg.get("critic_lenses", {}).get(crole, "")
            ctitle = f"[{phase_cfg['name']}] Round {round_num} — {crole} critique"
            cbody = _build_debate_body("critique", crole, position, round_num, max_rounds, clens, phase_cfg["slug"])
            ckid = create_kanban_task(board_slug, ctitle, cbody, cprofile,
                                      parent=kid, workspace=f"dir:{proj_dir}")
            _create_phase_task(
                phase_id, project_id, "debate_critique", crole, cprofile,
                ctitle, lens=clens, round_num=round_num,
                depends_on_ids=str(proposal_tid),
                output_path=f"phases/{phase_cfg['slug']}/{crole}/round-{round_num:02d}.md",
                kanban_id=ckid, kanban_parent_id=kid
            )
            prev_kanban_id = ckid


def _build_debate_body(side: str, role: str, position: str, round_num: int,
                       max_rounds: int, lens: str, phase_slug: str = "") -> str:
    """Build a debate task body. Loads from config/phases/<slug>/{proposal,critique}.md."""
    # Try pattern-specific templates from config/phases/
    if phase_slug:
        tpl_path = CONFIG_DIR / "phases" / phase_slug / f"{side}.md"
        if tpl_path.exists():
            position_hint = {
                "r1": "Cold-start — this is the first proposal. Establish the baseline method.",
                "rmid": "Middle round — revise based on prior critiques. Address each concern.",
                "rfinal": "Final round — converge. Lock in the method; resolve any open issues.",
            }.get(position, "")
            return fill_template(tpl_path.read_text(), {
                "role": role, "round_num": round_num, "max_rounds": max_rounds,
                "lens": lens, "position": position,
                "position_hint": position_hint,
                "prev_round": round_num - 1,
                "output_path": f"phases/{phase_slug}/{role}/round-{round_num:02d}.md",
            })
    # Legacy fallback (patterns/ in exploration-templates)
    tpl_candidates = [
        f"patterns/debate-{side}-{position}.md",
        f"patterns/debate-{side}.md",
    ]
    for tpl in tpl_candidates:
        tpl_path = TEMPLATES_DIR / tpl
        if tpl_path.exists():
            return fill_template(tpl_path.read_text(), {
                "role": role, "round_num": round_num, "max_rounds": max_rounds,
                "lens": lens, "position": position,
            })
    # Inline fallback
    action = "propose" if side == "proposal" else "critique"
    return (f"# {action.capitalize()} — Round {round_num}/{max_rounds} ({position})\n\n"
            f"**Your role:** {role}\n**Your lens:** {lens}\n\n"
            f"Write your {action} to the current proposal.")


def _build_pattern_task_body(phase_cfg: dict, role: str, task_type: str,
                              output_path: str = "", **extra) -> str:
    """Build a task body for parallel/sequential patterns from config/phases/."""
    slug = phase_cfg.get("slug", "")
    # Try role-specific file first (e.g. lead-exploration.md, synthesis.md)
    candidates = []
    if task_type == "parallel_member":
        candidates.append(f"phases/{slug}/{role}-exploration.md")
    elif task_type == "synthesis":
        candidates.append(f"phases/{slug}/synthesis.md")
    elif task_type == "sequential_step":
        candidates.append(f"phases/{slug}/{role}-step.md")

    for rel in candidates:
        p = CONFIG_DIR / rel
        if p.exists():
            variables = {"role": role, "output_path": output_path, **extra}
            return fill_template(p.read_text(), variables)

    # Inline fallback — use the lens from config
    lens = _get_role_lens(phase_cfg, role) or ""
    return f"# Task: {task_type} ({role})\n\n**Lens:** {lens}\n**Output:** {output_path}"


def setup_phase(project_id: int, phase_slug: str) -> int:
    """
    Dispatcher: read phase config, route to the right pattern setup.
    This is the main entry point for starting any of the 5 phases.
    """
    cfg = load_config()
    phase_cfg = get_phase_config(cfg, phase_slug)
    if not phase_cfg:
        raise ValueError(f"Phase '{phase_slug}' not found in config.yaml")

    proj = get_project(project_id)
    if not proj:
        raise ValueError(f"Project {project_id} not found")
    proj_dir = get_project_dir(project_id)
    if not proj_dir:
        raise ValueError(f"Project directory not found for project {project_id}")

    pattern = phase_cfg.get("pattern", "debate")
    slug = phase_cfg["slug"]
    name = phase_cfg.get("name", slug)
    description = phase_cfg.get("description", "")
    max_rounds = phase_cfg.get("max_rounds", 1)

    phase_id = _get_or_create_phase(project_id, slug, name, description, max_rounds)

    # Create phase output directory
    phase_dir = proj_dir / "phases" / slug
    phase_dir.mkdir(parents=True, exist_ok=True)

    # Ensure setting.md exists
    settings_path = proj_dir / "setting.md"
    if not settings_path.exists():
        settings_path.write_text(load_setting_template())

    # Create / reuse kanban board
    board_slug = f"rhub-p{project_id}"
    create_kanban_board(board_slug, proj["name"])

    # Write memory entries for each participant in this phase
    settings_content = settings_path.read_text()
    participants = _phase_participants(phase_cfg)
    for role_id in participants:
        profile = get_agent_profile(cfg, role_id)
        if profile:
            _write_phase_memory(project_id, profile, role_id, phase_cfg,
                                settings_content, proj_dir, proj["name"])

    # Route to pattern-specific setup
    if pattern == "parallel":
        _setup_parallel(phase_id, project_id, phase_cfg, proj_dir, board_slug)
    elif pattern == "sequential":
        _setup_sequential(phase_id, project_id, phase_cfg, proj_dir, board_slug)
    elif pattern == "debate":
        _setup_debate(phase_id, project_id, phase_cfg, proj_dir, board_slug)
    else:
        raise ValueError(f"Unknown pattern: {pattern}")

    # Mark phase running
    with get_db() as conn:
        conn.execute(
            "UPDATE phases SET status='running', config_json=? WHERE id=?",
            (json.dumps({"pattern": pattern, "slug": slug}), phase_id)
        )

    print(f"[hub] Phase '{slug}' ({pattern}) set up for project #{project_id}")
    return phase_id


def _phase_participants(phase_cfg: dict) -> list:
    """Return all agent_ids involved in a phase (for memory writes)."""
    pattern = phase_cfg.get("pattern", "debate")
    if pattern == "parallel":
        return [m["role"] for m in phase_cfg.get("members", [])] + \
               [phase_cfg.get("synthesis", {}).get("owner", "lead")]
    elif pattern == "sequential":
        return [s["role"] for s in phase_cfg.get("steps", [])]
    elif pattern == "debate":
        return [phase_cfg.get("owner")] + phase_cfg.get("critics", [])
    return []


def _write_phase_memory(project_id: int, profile: str, role_id: str,
                        phase_cfg: dict, settings_content: str,
                        proj_dir: Path, project_name: str) -> None:
    """Write/update memory for a participant in this phase. Skips gracefully if profile missing."""
    memory_dir = Path.home() / ".hermes" / "profiles" / profile / "memories"
    if not memory_dir.exists():
        print(f"[hub] WARNING: Profile '{profile}' has no memories dir — skipping memory write. "
              f"Create it with: hermes profile create {profile}")
        return

    # Clean old entries for this project+phase
    slug = phase_cfg["slug"]
    memory_file = memory_dir / "MEMORY.md"
    if memory_file.exists():
        content = memory_file.read_text()
        marker = f"# Research Hub — Project {project_id} Phase {slug}"
        sections = content.split("\n§\n")
        kept = [s for s in sections if marker not in s]
        if len(kept) != len(sections):
            memory_file.write_text("\n§\n".join(kept))

    # Compose the full layered entry
    entry = _compose_memory_entry(project_id, role_id, phase_cfg,
                                   settings_content, proj_dir, project_name)
    with open(memory_file, "a") as f:
        if memory_file.stat().st_size > 0:
            f.write("\n§\n")
        f.write(entry)


def _get_role_lens(phase_cfg: dict, role_id: str) -> str:
    """Extract the specific lens for a role in a phase."""
    pattern = phase_cfg.get("pattern", "debate")
    if pattern == "parallel":
        for m in phase_cfg.get("members", []):
            if m["role"] == role_id:
                return m.get("lens", "")
        if phase_cfg.get("synthesis", {}).get("owner") == role_id:
            return phase_cfg.get("synthesis", {}).get("task", "")
    elif pattern == "sequential":
        for s in phase_cfg.get("steps", []):
            if s["role"] == role_id:
                return s.get("lens", "")
    elif pattern == "debate":
        if phase_cfg.get("owner") == role_id:
            return phase_cfg.get("owner_lens", "")
        return phase_cfg.get("critic_lenses", {}).get(role_id, "")
    return ""


# ── Phase polling & status (uniform across patterns) ─────────────────────────

def poll_phase(project_id: int, phase_slug: str) -> Optional[dict]:
    """
    Poll kanban for all tasks in a phase, update phase_tasks status,
    promote blocked tasks when their deps complete.
    Returns the phase status dict.
    """
    phase = get_phase(project_id, phase_slug)
    if not phase:
        return None

    cfg = load_config()
    phase_cfg = get_phase_config(cfg, phase_slug)
    if not phase_cfg:
        return None

    board_slug = f"rhub-p{project_id}"
    result = subprocess.run(
        ["hermes", "kanban", "--board", board_slug, "list"],
        capture_output=True, text=True
    )
    kanban_statuses = parse_kanban_list(result.stdout) if result.returncode == 0 else {}

    with get_db() as conn:
        tasks = conn.execute(
            "SELECT * FROM phase_tasks WHERE phase_id = ? ORDER BY id",
            (phase["id"],)
        ).fetchall()

        any_running = False
        any_failed = False
        all_complete = True
        updates = []

        for t in tasks:
            new_status = t["status"]
            # Update from kanban if we have a mapping
            if t["kanban_id"] and t["kanban_id"] in kanban_statuses:
                ks = kanban_statuses[t["kanban_id"]]
                mapped = _KANBAN_STATUS_MAP.get(ks, t["status"])
                if mapped != t["status"]:
                    new_status = mapped

            # Check if blocked tasks can be unblocked
            if new_status == "blocked" and t["depends_on_ids"]:
                dep_ids = [int(x) for x in t["depends_on_ids"].split(",") if x.strip()]
                deps_done = True
                for dep_id in dep_ids:
                    dep = conn.execute(
                        "SELECT status FROM phase_tasks WHERE id = ?", (dep_id,)
                    ).fetchone()
                    if not dep or dep["status"] != "completed":
                        deps_done = False
                        break
                if deps_done:
                    new_status = "pending"  # ready to be picked up

            if new_status != t["status"]:
                updates.append((new_status, t["id"]))
                if new_status == "running" and not t["started_at"]:
                    updates.append((datetime.now().isoformat(), t["id"], "started_at"))
                if new_status in ("completed", "failed") and not t["completed_at"]:
                    updates.append((datetime.now().isoformat(), t["id"], "completed_at"))

            if new_status == "running":
                any_running = True
            if new_status == "failed":
                any_failed = True
            if new_status != "completed":
                all_complete = False

        # Apply updates
        for u in updates:
            if len(u) == 2:
                conn.execute("UPDATE phase_tasks SET status = ? WHERE id = ?", u)
            elif len(u) == 3:
                conn.execute(f"UPDATE phase_tasks SET {u[2]} = ? WHERE id = ?", (u[0], u[1]))

        # Aggregate phase status
        new_phase_status = "running"
        if all_complete:
            new_phase_status = "completed"
        elif any_failed:
            new_phase_status = "failed"
        elif not any_running:
            new_phase_status = "active"

        conn.execute("UPDATE phases SET status = ? WHERE id = ?",
                     (new_phase_status, phase["id"]))

    return get_phase_status(project_id, phase_slug)


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

# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: hub.py <init|create|list|status|step|summary|advance>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        init_db()

    elif cmd == "create":
        if len(sys.argv) < 3:
            print("Usage: hub.py create <name> [description] [goal]")
            sys.exit(1)
        name = sys.argv[2]
        desc = sys.argv[3] if len(sys.argv) > 3 else ""
        goal = sys.argv[4] if len(sys.argv) > 4 else ""
        create_project(name, desc, goal)

    elif cmd == "list":
        for p in list_projects():
            print(f"#{p['id']:03d} [{p['status']:10}] {p['name']} (iter {p['current_iteration']}/{p['max_iterations']})")

    elif cmd == "status":
        if len(sys.argv) < 3:
            print("Usage: hub.py status <project_id>")
            sys.exit(1)
        pid = int(sys.argv[2])
        print(project_summary(pid))

    elif cmd == "advance":
        if len(sys.argv) < 3:
            print("Usage: hub.py advance <project_id>")
            sys.exit(1)
        pid = int(sys.argv[2])
        st = advance_workflow(pid)
        print(json.dumps(st, indent=2, default=str))

    elif cmd == "step":
        if len(sys.argv) < 3:
            print("Usage: hub.py step <project_id> [task_id]")
            sys.exit(1)
        pid = int(sys.argv[2])
        tid = int(sys.argv[3]) if len(sys.argv) > 3 else None
        result = run_step(pid, tid)
        print(json.dumps(result, indent=2, default=str))

    elif cmd == "summary":
        if len(sys.argv) < 3:
            print("Usage: hub.py summary <project_id>")
            sys.exit(1)
        pid = int(sys.argv[2])
        print(project_summary(pid))

    elif cmd == "phase-init":
        if len(sys.argv) < 4:
            print("Usage: hub.py phase-init <project_id> <slug> [name]")
            sys.exit(1)
        pid = int(sys.argv[2])
        slug = sys.argv[3]
        name = sys.argv[4] if len(sys.argv) > 4 else None
        phase_id = init_phase(pid, slug, name)
        print(f"[hub] Phase '{slug}' created: #{phase_id}")

    elif cmd == "idea-setup":
        if len(sys.argv) < 6:
            print("Usage: hub.py idea-setup <project_id> <proposer_profile> <critic_profile> <manager_profile> [max_rounds]")
            sys.exit(1)
        pid = int(sys.argv[2])
        proposer = sys.argv[3]
        critic = sys.argv[4]
        manager = sys.argv[5]
        max_r = int(sys.argv[6]) if len(sys.argv) > 6 else 3
        phase_id = setup_idea_phase(pid, proposer, critic, manager, max_r)
        print(f"[hub] Idea phase setup complete: phase #{phase_id}")

    elif cmd == "idea-status":
        if len(sys.argv) < 3:
            print("Usage: hub.py idea-status <project_id>")
            sys.exit(1)
        pid = int(sys.argv[2])
        st = poll_idea_phase(pid)
        print(json.dumps(st, indent=2, default=str))

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: init, create, list, status, step, advance, summary, phase-init, idea-setup, idea-status")

if __name__ == "__main__":
    main()
