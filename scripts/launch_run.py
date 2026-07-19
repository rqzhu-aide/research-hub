#!/usr/bin/env python3
"""
Thin launcher for research-hub phase runs.

The research_lead is the real orchestrator — this module only:
  1. Verifies gating
  2. Ensures project state is initialized
  3. Creates / reuses the project's kanban board
  4. Records the run envelope in .log/project.yaml
  5. Assembles the lead's invocation prompt
  6. Spawns research_lead as a detached background process
  7. (On completion) records the run as done

Usage from webapp:
    from scripts.launch_run import launch_run
    run_index = launch_run(project_dir, project_id, phase_slug,
                           user_feedback, rounds_requested)

Usage from CLI (lead calls this when done):
    python3 scripts/launch_run.py complete \\
        --project-dir ... --phase ... --run-index 0 \\
        --summary phase-summaries/01-literature-review.html
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

# Ensure we can import sibling module
sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_state import (
    load, init, start_run, complete_run, can_run, state_file, state_dir,
)


# ---------------------------------------------------------------------------
# Config helpers (lightweight — reads hub config.yaml)
# ---------------------------------------------------------------------------

_HUB_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
_PHASES_DIR = Path(__file__).resolve().parent.parent / "config" / "phases"


def _load_hub_config() -> dict:
    with open(_HUB_CONFIG, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _get_phase_config(phase_slug: str) -> Optional[dict]:
    cfg = _load_hub_config()
    for p in cfg.get("phases", []):
        if p.get("slug") == phase_slug:
            return p
    return None


def _get_gating() -> dict[str, list[str]]:
    cfg = _load_hub_config()
    return {p["slug"]: p.get("gated_by", []) for p in cfg.get("phases", [])}


def _get_all_phase_slugs() -> list[str]:
    cfg = _load_hub_config()
    return [p["slug"] for p in cfg.get("phases", [])]


# ---------------------------------------------------------------------------
# Kanban board management
# ---------------------------------------------------------------------------

def _ensure_board(board_slug: str, display_name: str) -> None:
    """Create the project's kanban board if it doesn't exist."""
    result = subprocess.run(
        ["hermes", "kanban", "boards", "list", "--json"],
        capture_output=True, text=True, timeout=15,
    )
    existing = []
    try:
        data = json.loads(result.stdout)
        existing = [b.get("slug", "") for b in data] if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        pass  # fall through to create attempt

    if board_slug in existing:
        return

    subprocess.run(
        ["hermes", "kanban", "boards", "create", board_slug,
         "--name", display_name],
        capture_output=True, text=True, timeout=15,
    )


# ---------------------------------------------------------------------------
# Cross-phase context
# ---------------------------------------------------------------------------

def _existing_summaries(project_dir: Path) -> list[str]:
    """Return relative paths of existing phase summaries."""
    summaries_dir = project_dir / "phase-summaries"
    if not summaries_dir.exists():
        return []
    return sorted(
        f"phase-summaries/{f.name}"
        for f in summaries_dir.glob("*.html")
        if f.is_file()
    )


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def _build_lead_prompt(
    project_dir: Path,
    project_id: int,
    phase_slug: str,
    phase_cfg: dict,
    board_slug: str,
    run_index: int,
    rounds_requested: int,
    user_feedback: str,
) -> str:
    """Assemble the full invocation prompt for the research_lead."""
    members = phase_cfg.get("members", [])
    pattern = phase_cfg.get("pattern", "parallel")
    folder = phase_cfg.get("folder", "")
    phase_name = phase_cfg.get("name", phase_slug)

    # Determine run number for folder naming (1-based)
    run_n = run_index + 1

    # Build members section
    member_lines = []
    for m in members:
        role = m if isinstance(m, str) else m.get("role", m)
        task_file = f"config/phases/{phase_slug}/{role}.md"
        member_lines.append(f"  - **{role}** → task file: `{task_file}`")
    members_block = "\n".join(member_lines)

    # Cross-phase summaries
    summaries = _existing_summaries(project_dir)
    if summaries:
        summaries_block = "\n".join(f"  - `{s}`" for s in summaries)
    else:
        summaries_block = "  (none yet — this is the first phase to run)"

    # Completion command
    launcher = Path(__file__).resolve()
    complete_cmd = (
        f"python3 {launcher} complete"
        f" --project-dir {project_dir}"
        f" --phase {phase_slug}"
        f" --run-index {run_index}"
        f" --summary phase-summaries/{phase_slug}.html"
    )

    prompt = f"""# You are the Research Lead orchestrating: {phase_name}

## Step 0 — Set up your environment
```bash
cd {project_dir}
hermes kanban boards switch {board_slug}
```

## Step 1 — Read your playbook (REQUIRED before doing anything)
Read these files carefully — they ARE your instructions:
- `config/phases/{phase_slug}/_lead.md` — how to orchestrate THIS phase
- `config/phases/{phase_slug}/_phase.md` — phase overview, folder, pattern
- `setting.md` — the project goal and constraints

## Step 2 — Read cross-phase context
Prior phase summaries (if any):
{summaries_block}

These tell you what has been done in earlier phases. Use them to steer
your team's work in THIS phase.

## Step 3 — Run the phase
- **Pattern:** {pattern}
  {"(members work independently in parallel — create all their tasks at once)" if pattern == "parallel" else "(pipeline — each member takes the previous one's output)" if pattern == "sequential" else "(owner proposes, critics critique, iterate)"}
- **Rounds requested:** {rounds_requested}
- **User feedback:** {user_feedback if user_feedback else "(none provided)"}

### Your team
{members_block}

For each member, create a kanban task:
```bash
hermes kanban create \\
  --assignee <profile-name> \\
  --title "<phase> — Round N — <role>" \\
  --body "Read your task file: config/phases/{phase_slug}/<role>.md

Additional directive for this round: <your specific twist here>

Write your output to: {folder}run/{run_n:02d}/round-NN/<role>.md

Cross-phase context: read phase-summaries/*.html for what prior phases found."
```

Wait for all member tasks to complete before starting the next round.
Check with: `hermes kanban list --status done`

### Between rounds
Read all member outputs from the round. Identify gaps. Compose new
directives for the next round that fill those gaps. Be specific.

## Step 4 — Write the phase summary
When all rounds are complete, write/update the phase summary:
- **File:** `phase-summaries/{phase_slug}.html` (overwrite if exists)
- **Format:** HTML, max 3 pages, self-contained styling
- **Contents:**
  1. Brief summary of current findings / literature / state
  2. Where the project's goal positions relative to the above
  3. Suggested directions (more review? start method development? etc.)

The user reads this in a browser to decide what to do next.

## Step 5 — Signal completion
When the summary is written, run:
```bash
{complete_cmd}
```
Then you are finished. Do not do anything else after this.
"""
    return prompt


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

def launch_run(
    project_dir: str | Path,
    project_id: int,
    phase_slug: str,
    user_feedback: str = "",
    rounds_requested: int = 1,
) -> dict:
    """
    Launch a phase run. Spawns research_lead as a detached background process.
    Returns a dict with run_index, board_slug, and pid.

    Raises RuntimeError if the phase is gated or project state is missing.
    """
    project_dir = Path(project_dir).resolve()

    # 1. Get phase config
    phase_cfg = _get_phase_config(phase_slug)
    if not phase_cfg:
        raise RuntimeError(f"Phase '{phase_slug}' not found in config.yaml")

    # 2. Verify gating
    gating = _get_gating()
    ok, why = can_run(project_dir, phase_slug, gating)
    if not ok:
        raise RuntimeError(f"Phase '{phase_slug}' is gated: {why}")

    # 3. Ensure project state initialized
    state = load(project_dir)
    if not state.get("project"):
        # Need project metadata — derive from directory name
        dir_name = project_dir.name  # project-NNN-<slug>
        parts = dir_name.split("-", 2)
        slug = parts[2] if len(parts) >= 3 else dir_name
        init(project_dir, f"project-{project_id:03d}", slug, slug,
             phase_slugs=_get_all_phase_slugs())

    # 4. Ensure no run already in progress for this project
    phases = state.get("phases", {})
    for slug, info in phases.items():
        if info.get("status") == "running":
            raise RuntimeError(
                f"Project already has a running phase: {slug}. "
                f"One run at a time."
            )

    # 5. Create / reuse kanban board
    board_slug = f"rhub-p{project_id}"
    project_name = state.get("project", {}).get("name", board_slug)
    _ensure_board(board_slug, project_name)

    # 6. Record run envelope
    run_index = start_run(
        project_dir, phase_slug,
        mode="initial survey",  # freeform label; lead may reinterpret
        rounds_requested=rounds_requested,
        user_feedback=user_feedback,
    )

    # 7. Assemble prompt
    prompt = _build_lead_prompt(
        project_dir, project_id, phase_slug, phase_cfg,
        board_slug, run_index, rounds_requested, user_feedback,
    )

    # 8. Write prompt to file (for debugging + to avoid arg-length issues)
    prompt_file = state_dir(project_dir) / f"run-{run_index}-prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt, encoding="utf-8")

    # 9. Spawn research_lead as detached background process
    log_file = state_dir(project_dir) / f"run-{run_index}-lead.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [
            "hermes", "--profile", "research_lead",
            "chat", "-q", prompt,
            "--yolo",
        ],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # detach from parent (survives webapp restart)
        cwd=str(project_dir),
    )

    # 10. Record PID in state for monitoring
    state = load(project_dir)
    state["_active_run"] = {
        "phase": phase_slug,
        "run_index": run_index,
        "pid": proc.pid,
        "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    state_file(project_dir).write_text(
        yaml.safe_dump(state, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    return {
        "run_index": run_index,
        "board_slug": board_slug,
        "pid": proc.pid,
        "prompt_file": str(prompt_file),
        "log_file": str(log_file),
    }


# ---------------------------------------------------------------------------
# Completion (called by the lead when done)
# ---------------------------------------------------------------------------

def _complete(
    project_dir: str | Path,
    phase_slug: str,
    run_index: int,
    summary_path: str,
    status: str = "completed",
) -> None:
    """Record run completion. Called by the lead via CLI."""
    project_dir = Path(project_dir).resolve()
    complete_run(
        project_dir, phase_slug, run_index,
        final_summary=summary_path,
        status=status,
    )

    # Clear active run marker
    state = load(project_dir)
    state.pop("_active_run", None)
    state_file(project_dir).write_text(
        yaml.safe_dump(state, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    print(f"[launch_run] Run {run_index} of '{phase_slug}' marked {status}.")
    print(f"  Summary: {summary_path}")


# ---------------------------------------------------------------------------
# Status query (for webapp polling)
# ---------------------------------------------------------------------------

def get_run_status(project_dir: str | Path) -> dict:
    """
    Return current run status for the webapp's progress view.
    Returns {active: False} if no run is in progress.
    """
    project_dir = Path(project_dir).resolve()
    state = load(project_dir)
    active = state.get("_active_run")
    if not active:
        return {"active": False}

    phase = active["phase"]
    run_idx = active["run_index"]
    phases = state.get("phases", {})
    phase_info = phases.get(phase, {})
    runs = phase_info.get("runs", [])
    run = runs[run_idx] if run_idx < len(runs) else {}

    return {
        "active": True,
        "phase": phase,
        "run_index": run_idx,
        "pid": active.get("pid"),
        "started": active.get("started"),
        "rounds_requested": run.get("rounds_requested", 1),
        "rounds_completed": len(run.get("rounds", [])),
        "status": phase_info.get("status", "running"),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Research-hub run launcher")
    sub = parser.add_subparsers(dest="command")

    # complete subcommand (called by the lead)
    p_complete = sub.add_parser("complete", help="Mark a run complete")
    p_complete.add_argument("--project-dir", required=True)
    p_complete.add_argument("--phase", required=True)
    p_complete.add_argument("--run-index", type=int, required=True)
    p_complete.add_argument("--summary", required=True)
    p_complete.add_argument("--status", default="completed")

    # status subcommand (for debugging / webapp)
    p_status = sub.add_parser("status", help="Show current run status")
    p_status.add_argument("--project-dir", required=True)

    args = parser.parse_args()

    if args.command == "complete":
        _complete(args.project_dir, args.phase, args.run_index,
                  args.summary, args.status)
    elif args.command == "status":
        info = get_run_status(args.project_dir)
        print(json.dumps(info, indent=2))
    else:
        parser.print_help()
