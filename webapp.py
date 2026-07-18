#!/usr/bin/env python3
"""
Research Hub — Web UI
Flask presentation layer over hub.py backend.
Run: python webapp.py  →  http://localhost:5055
"""

from __future__ import annotations
import sys
import traceback
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash, Response

# Import the existing backend (same directory)
sys.path.insert(0, str(Path(__file__).parent.resolve()))
import hub

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "research-hub-dev"  # local-only; fine for now


def _profiles() -> list[dict]:
    """Agent roster from config.yaml."""
    cfg = hub.load_config()
    return hub.get_agents(cfg)


def _profile_names() -> list[str]:
    return [a["profile"] for a in _profiles()]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    projects = hub.list_projects()
    if projects:
        first = dict(projects[0])
        return redirect(url_for("project_view", project_id=first["id"]))
    return render_template("index.html", projects=[], profiles=_profiles())


@app.route("/project/<int:project_id>")
def project_view(project_id: int):
    proj = hub.get_project(project_id)
    if not proj:
        flash(f"Project #{project_id} not found", "error")
        return redirect(url_for("index"))
    proj = dict(proj)
    projects = [dict(p) for p in hub.list_projects()]
    idea_status = hub.get_idea_status(project_id)
    phases = [dict(p) for p in hub.get_phases(project_id)]

    # Read setting.md if it exists
    proj_dir = hub.get_project_dir(project_id)
    settings_content = ""
    if proj_dir:
        s = proj_dir / "setting.md"
        if s.exists():
            settings_content = s.read_text()

    return render_template(
        "project.html",
        project=proj,
        projects=projects,
        phases=phases,
        idea_status=idea_status,
        settings_content=settings_content,
        profiles=_profiles(),
    )


@app.route("/project/<int:project_id>/settings", methods=["POST"])
def save_settings(project_id: int):
    content = request.form.get("settings_content", "")
    proj_dir = hub.get_project_dir(project_id)
    if not proj_dir:
        flash("Project directory not found", "error")
        return redirect(url_for("project_view", project_id=project_id))
    (proj_dir / "setting.md").write_text(content)
    flash("Settings saved.", "success")
    return redirect(url_for("project_view", project_id=project_id))


@app.route("/project/<int:project_id>/agents", methods=["POST"])
def setup_agents(project_id: int):
    proposer = request.form.get("proposer", "").strip()
    critic = request.form.get("critic", "").strip()
    manager = request.form.get("manager", "").strip()
    try:
        max_rounds = int(request.form.get("max_rounds", "3"))
    except ValueError:
        max_rounds = 3

    if not proposer or not critic:
        flash("Proposer and Critic profiles are required.", "error")
        return redirect(url_for("project_view", project_id=project_id))

    try:
        phase_id = hub.setup_idea_phase(project_id, proposer, critic, manager, max_rounds)
        flash(f"Idea phase set up (phase #{phase_id}). Kanban board + task chain created.", "success")
    except Exception as e:
        traceback.print_exc()
        flash(f"Setup failed: {e}", "error")
    return redirect(url_for("project_view", project_id=project_id))


@app.route("/project/<int:project_id>/progress")
def progress_panel(project_id: int):
    """HTMX-polled partial: rounds table."""
    idea_status = hub.poll_idea_phase(project_id)
    return render_template("_progress_panel.html", idea_status=idea_status, project_id=project_id)


@app.route("/project/<int:project_id>/activity")
def activity_panel(project_id: int):
    """HTMX-polled partial: activity log derived from rounds."""
    idea_status = hub.get_idea_status(project_id)
    events = []
    if idea_status:
        for r in idea_status.get("rounds", []):
            for role in ("proposer", "critic"):
                status = r.get(f"{role}_status", "pending")
                completed = r.get(f"{role}_completed_at")
                started = r.get(f"{role}_started_at")
                if status == "completed" and completed:
                    events.append({
                        "ts": completed,
                        "round": r["round_number"],
                        "role": role,
                        "msg": f"Round {r['round_number']} {role} completed",
                    })
                elif status == "running" and started:
                    events.append({
                        "ts": started,
                        "round": r["round_number"],
                        "role": role,
                        "msg": f"Round {r['round_number']} {role} started",
                    })
        events.sort(key=lambda e: e["ts"], reverse=True)
    return render_template("_activity_panel.html", events=events[:20])


@app.route("/profiles")
def profiles_view():
    agents = _profiles()
    # Attach memory preview if it exists
    home = Path.home()
    for a in agents:
        mem = home / ".hermes" / "profiles" / a["profile"] / "memories" / "MEMORY.md"
        a["memory_exists"] = mem.exists()
        a["memory_size"] = mem.stat().st_size if mem.exists() else 0
    return render_template("profiles.html", agents=agents)


@app.route("/profiles/<name>/memory")
def profile_memory(name: str):
    mem = Path.home() / ".hermes" / "profiles" / name / "memories" / "MEMORY.md"
    content = mem.read_text() if mem.exists() else f"(No MEMORY.md found for profile '{name}')"
    return render_template("profile_memory.html", name=name, content=content)


@app.route("/project/<int:project_id>/round/<int:round_num>/<role>")
def round_output(project_id: int, round_num: int, role: str):
    content = hub.view_round_output(project_id, round_num, role) or "(No output yet)"
    return render_template("round_output.html",
                           project_id=project_id, round_num=round_num,
                           role=role, content=content)


if __name__ == "__main__":
    print("[webapp] Research Hub Web UI → http://localhost:5055")
    app.run(host="127.0.0.1", port=5055, debug=True)
