"""
Bridge between project_state.py, config.yaml, and the webapp templates.

Prepares rich phase data that templates can render directly — no logic in Jinja.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import yaml
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_state import load, can_run, get_run, all_phases


_HUB_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def _load_hub_config() -> dict:
    with open(_HUB_CONFIG, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _get_gating(phases_cfg: list[dict]) -> dict[str, list[str]]:
    return {p["slug"]: p.get("gated_by", []) for p in phases_cfg}


def _summary_exists(project_dir: Path, phase_slug: str) -> bool:
    return (project_dir / "phase-summaries" / f"{phase_slug}.html").exists()


def _summary_path(project_dir: Path, phase_slug: str) -> Optional[str]:
    p = project_dir / "phase-summaries" / f"{phase_slug}.html"
    if p.exists():
        return f"phase-summaries/{phase_slug}.html"
    return None


def prepare_phase_data(
    project_dir: Path,
    project_id: int,
    phase_cfg: dict,
    phases_cfg: list[dict],
) -> dict:
    """
    Build the data dict a phase tab needs to render.

    Returns:
        {
            phase_cfg: {...},            # from config.yaml
            state: {...} | None,         # from .log/project.yaml
            can_run: bool,
            gating_reason: str,
            run_active: bool,
            run_status: {...} | None,    # current run live status
            summary_path: str | None,    # path to HTML summary if exists
            run_history: [...],          # all past runs (compressed for display)
        }
    """
    phase_slug = phase_cfg["slug"]
    state = load(project_dir)
    phases_state = state.get("phases", {})
    phase_state = phases_state.get(phase_slug, {"status": "pending", "runs": []})

    # Gating
    gating = _get_gating(phases_cfg)
    ok, why = can_run(project_dir, phase_slug, gating)

    # Active run?
    active = state.get("_active_run", {})
    run_active = (
        active.get("phase") == phase_slug
        and active.get("run_index") is not None
    )

    run_status = None
    if run_active:
        run_idx = active["run_index"]
        runs = phase_state.get("runs", [])
        if run_idx < len(runs):
            run = runs[run_idx]
            run_status = {
                "run_index": run_idx,
                "run_number": run_idx + 1,
                "rounds_requested": run.get("rounds_requested", 1),
                "rounds_completed": len(run.get("rounds", [])),
                "user_feedback": run.get("user_feedback", ""),
                "started": run.get("started"),
                "mode": run.get("mode", ""),
            }

    # Run history (compressed — just key facts for display)
    run_history = []
    for idx, run in enumerate(phase_state.get("runs", [])):
        run_history.append({
            "number": idx + 1,
            "mode": run.get("mode", ""),
            "rounds_requested": run.get("rounds_requested", 1),
            "rounds_completed": len(run.get("rounds", [])),
            "started": run.get("started"),
            "completed": run.get("completed"),
            "final_summary": run.get("final_summary"),
        })

    return {
        "phase_cfg": phase_cfg,
        "state": phase_state,
        "can_run": ok,
        "gating_reason": why,
        "run_active": run_active,
        "run_status": run_status,
        "summary_path": _summary_path(project_dir, phase_slug),
        "run_history": run_history,
    }


def prepare_overview_data(
    project_dir: Path,
    phases_cfg: list[dict],
) -> list[dict]:
    """
    Build phase summary cards for the overview page.
    Each card shows: number, name, status, pattern, rounds, summary link.
    """
    state = load(project_dir)
    phases_state = state.get("phases", {})
    gating = _get_gating(phases_cfg)

    cards = []
    for idx, pc in enumerate(phases_cfg, 1):
        slug = pc["slug"]
        ps = phases_state.get(slug, {"status": "pending", "runs": []})
        runs = ps.get("runs", [])
        last_run = runs[-1] if runs else None

        # Is this phase currently the active run?
        active = state.get("_active_run", {})
        is_active = active.get("phase") == slug

        # Can it run? (gating check)
        ok, _ = can_run(project_dir, slug, gating)

        cards.append({
            "number": idx,
            "slug": slug,
            "name": pc.get("name", slug),
            "pattern": pc.get("pattern", ""),
            "description": pc.get("description", ""),
            "gated_by": pc.get("gated_by", []),
            "folder": pc.get("folder", ""),
            "members": pc.get("members", []),
            "status": "running" if is_active else ps.get("status", "pending"),
            "run_count": len(runs),
            "last_run_started": last_run.get("started") if last_run else None,
            "last_run_completed": last_run.get("completed") if last_run else None,
            "last_run_rounds": (
                f"{len(last_run.get('rounds', []))}/{last_run.get('rounds_requested', 1)}"
                if last_run else None
            ),
            "summary_path": _summary_path(project_dir, slug),
            "can_run": ok,
            "is_active": is_active,
        })

    return cards
