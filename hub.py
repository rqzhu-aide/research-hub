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

HUB_DIR = Path(__file__).parent.resolve()
DB_PATH = HUB_DIR / "hub.db"
CONFIG_PATH = HUB_DIR / "config.yaml"
PROJECTS_DIR = HUB_DIR / "projects"

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

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: init, create, list, status, step, advance, summary")

if __name__ == "__main__":
    main()
