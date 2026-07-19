"""
Backend-only project state management.

Reads and writes <project_dir>/.log/project.yaml — the research-hub system's
private record of project progression. The research team (agents) never sees
or touches this file; it is not mentioned in any task prompt. All updates go
through the functions in this module.

File layout (produced and maintained here):
    <project_dir>/.log/
        project.yaml       ← this module's file
        runs.log           ← append-only audit trail (optional)

YAML schema (kept deliberately simple — pure state, no rules):
    project:
      id: project-002
      slug: efficient_llm_fine-tuning
      name: "Efficient LLM Fine-tuning"
      created: 2026-07-18T14:30:00Z
    phases:
      01-literature-review:
        status: completed              # pending | running | completed | failed
        runs:
          - mode: run                  # phase-specific (e.g. run | deep_run)
            started:  2026-07-18T15:00:00Z
            completed: 2026-07-18T15:12:34Z
            agents: [research_lead, theorist, data_scientist]
          - mode: deep_run
            started:  2026-07-18T18:00:00Z
            completed: 2026-07-18T18:08:21Z
            agents: [research_lead, theorist, data_scientist]
      02-method-development:
        status: pending
        runs: []

Gating rules are NOT stored here — they live in config.yaml's phases section.
This file only records what happened. The can_run() helper takes the gating
rules as an argument so the two concerns stay separate.

Timestamps are ISO 8601 UTC (Z suffix). Callers may pass naive datetimes;
they are converted to UTC on write.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def state_dir(project_dir: str | Path) -> Path:
    """Return the hidden .log/ directory inside a project."""
    return Path(project_dir) / ".log"


def state_file(project_dir: str | Path) -> Path:
    """Return the path to project.yaml for a project."""
    return state_dir(project_dir) / "project.yaml"


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Current UTC time as ISO 8601 with Z suffix, e.g. 2026-07-18T15:00:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_iso(dt: datetime | str | None) -> str | None:
    """Coerce a datetime or string into the canonical ISO-Z form."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Load / init
# ---------------------------------------------------------------------------

def load(project_dir: str | Path) -> dict:
    """Load the project's state. Returns an empty skeleton if not yet initialised."""
    path = state_file(project_dir)
    if not path.exists():
        return {"project": {}, "phases": {}}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    data.setdefault("project", {})
    data.setdefault("phases", {})
    return data


def _save(project_dir: str | Path, data: dict) -> None:
    """Write state atomically (temp file + rename)."""
    sdir = state_dir(project_dir)
    sdir.mkdir(parents=True, exist_ok=True)
    path = state_file(project_dir)
    tmp = path.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data, fh,
            sort_keys=False,            # preserve insertion order
            default_flow_style=False,   # block style for readability
            allow_unicode=True,
            width=100,
        )
    tmp.replace(path)


def init(
    project_dir: str | Path,
    project_id: str,
    slug: str,
    name: str,
    phase_slugs: list[str] | None = None,
) -> dict:
    """
    Create .log/project.yaml for a new project. Each known phase starts in
    `pending` with an empty runs list. Safe to call on an already-initialised
    project (preserves existing state, only fills missing fields).
    """
    data = load(project_dir)
    data["project"] = {
        "id": project_id,
        "slug": slug,
        "name": name,
        "created": data.get("project", {}).get("created") or _now_iso(),
    }
    phases = data.get("phases", {})
    for slug_ in (phase_slugs or []):
        phases.setdefault(slug_, {"status": "pending", "runs": []})
    data["phases"] = phases
    _save(project_dir, data)
    return data


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

def start_run(
    project_dir: str | Path,
    phase_slug: str,
    mode: str,
    agents: list[str],
) -> int:
    """
    Begin a new run of a phase. Appends a run entry with `started` set and
    `completed` null, marks the phase `running`, and returns the run's index
    (0-based) so the caller can later call complete_run() with it.
    """
    data = load(project_dir)
    phase = data["phases"].setdefault(phase_slug, {"status": "pending", "runs": []})
    run = {
        "mode": mode,
        "started": _now_iso(),
        "completed": None,
        "agents": list(agents),
    }
    phase["runs"].append(run)
    phase["status"] = "running"
    _save(project_dir, data)
    return len(phase["runs"]) - 1


def complete_run(
    project_dir: str | Path,
    phase_slug: str,
    run_index: int,
    status: str = "completed",
) -> None:
    """
    Mark a run finished: sets `completed`, and updates the phase status to
    `status` (default 'completed'; pass 'failed' if the run errored out).
    """
    data = load(project_dir)
    phase = data["phases"].get(phase_slug)
    if not phase or run_index >= len(phase["runs"]):
        raise KeyError(f"phase {phase_slug!r} has no run index {run_index}")
    phase["runs"][run_index]["completed"] = _now_iso()
    phase["status"] = status
    _save(project_dir, data)


# ---------------------------------------------------------------------------
# Read-only queries
# ---------------------------------------------------------------------------

def get_status(project_dir: str | Path, phase_slug: str) -> str:
    """Return the current status of a phase, or 'pending' if unknown."""
    data = load(project_dir)
    return data.get("phases", {}).get(phase_slug, {}).get("status", "pending")


def get_runs(project_dir: str | Path, phase_slug: str) -> list[dict]:
    """Return the full run history for a phase (oldest first)."""
    data = load(project_dir)
    return data.get("phases", {}).get(phase_slug, {}).get("runs", [])


def last_run(project_dir: str | Path, phase_slug: str) -> dict | None:
    """Return the most recent run for a phase, or None if it has never run."""
    runs = get_runs(project_dir, phase_slug)
    return runs[-1] if runs else None


def all_phases(project_dir: str | Path) -> dict:
    """Return the full {phase_slug: {status, runs}} mapping."""
    return load(project_dir).get("phases", {})


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------

def can_run(
    project_dir: str | Path,
    phase_slug: str,
    gating: dict[str, list[str]],
) -> tuple[bool, str]:
    """
    Check whether a phase may be started, given gating rules.

    `gating` maps phase_slug → list of prerequisite phase slugs. A phase may
    run iff every prerequisite has status 'completed'. Phases with no entry in
    `gating`, or an empty prereq list, are always runnable.

    Returns (allowed, reason). reason is '' when allowed, otherwise a short
    human-readable explanation naming the blocking prerequisite(s).
    """
    prereqs = gating.get(phase_slug, [])
    if not prereqs:
        return True, ""
    phases = all_phases(project_dir)
    blockers = [
        p for p in prereqs
        if phases.get(p, {}).get("status") != "completed"
    ]
    if blockers:
        return False, f"Waiting on: {', '.join(blockers)}"
    return True, ""


# ---------------------------------------------------------------------------
# Convenience: build a one-line summary for UI / logs
# ---------------------------------------------------------------------------

def summary(project_dir: str | Path) -> str:
    """One-line digest of project state, e.g. for logging."""
    data = load(project_dir)
    proj = data.get("project", {})
    phases = data.get("phases", {})
    counts = {}
    for slug, info in phases.items():
        counts.setdefault(info.get("status", "pending"), []).append(slug.split("-", 1)[-1])
    parts = [f"{n}: {', '.join(s)}" for n, s in counts.items() if s]
    return f"[{proj.get('id','?')}] {proj.get('name','?')} — {' | '.join(parts)}"
