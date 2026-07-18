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
TEMPLATES_DIR = HUB_DIR / "exploration-templates"

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
    return load_template("setting-template.md")

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
