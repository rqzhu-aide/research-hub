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


def _read_profile_config(profile_name: str) -> dict:
    """Read a Hermes profile's actual config.yaml and extract model info.

    Returns dict with: model, provider, base_url, config_exists.
    This reads what Hermes will *actually* use for that profile — independent
    of what research-hub's config.yaml claims.
    """
    import yaml
    cfg_path = Path.home() / ".hermes" / "profiles" / profile_name / "config.yaml"
    if not cfg_path.exists():
        return {"model": None, "provider": None, "base_url": None,
                "config_exists": False}
    try:
        data = yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        return {"model": None, "provider": None, "base_url": None,
                "config_exists": True, "config_error": True}
    m = (data.get("model") or {})
    # fallback_providers is a JSON string in the profile config; surface the
    # primary provider names so the user can see the chain at a glance.
    fallbacks = []
    fp = data.get("fallback_providers")
    if isinstance(fp, str) and fp.strip().startswith("["):
        try:
            import json
            for item in json.loads(fp):
                if isinstance(item, dict):
                    fb_provider = item.get("provider") or item.get("base_url") or "?"
                    fb_model = item.get("model")
                    fallbacks.append({"provider": fb_provider, "model": fb_model})
        except Exception:
            pass
    return {
        "model": m.get("default"),
        "provider": m.get("provider"),
        "base_url": m.get("base_url"),
        "config_exists": True,
        "fallbacks": fallbacks,
    }


# ── Routes ────────────────────────────────────────────────────────────────────


def list_hermes_profiles() -> list[str]:
    """All available Hermes profile names (dirs with a config.yaml under ~/.hermes/profiles/)."""
    profiles_dir = Path.home() / ".hermes" / "profiles"
    if not profiles_dir.is_dir():
        return []
    return sorted(
        entry.name for entry in profiles_dir.iterdir()
        if entry.is_dir() and (entry / "config.yaml").exists()
    )


def _set_agent_profile(agent_id: str, new_profile: str) -> bool:
    """Reassign an agent role to a different Hermes profile in config.yaml.

    Uses ruamel round-trip so comments and formatting are preserved.
    Returns True if the agent was found and updated.
    """
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.preserve_quotes = True
    path = hub.CONFIG_PATH
    data = yaml.load(path.read_text())
    found = False
    for agent in data.get("agents", []):
        if agent.get("id") == agent_id:
            agent["profile"] = new_profile
            found = True
            break
    if not found:
        return False
    import io
    buf = io.StringIO()
    yaml.dump(data, buf)
    path.write_text(buf.getvalue())
    return True


def _enrich_agent(a: dict) -> None:
    """Attach memory + live runtime config to an agent dict (in place)."""
    home = Path.home()
    mem = home / ".hermes" / "profiles" / a["profile"] / "memories" / "MEMORY.md"
    a["memory_exists"] = mem.exists()
    a["memory_size"] = mem.stat().st_size if mem.exists() else 0
    rc = _read_profile_config(a["profile"])
    a["runtime_model"] = rc["model"]
    a["runtime_provider"] = rc["provider"]
    a["runtime_base_url"] = rc["base_url"]
    a["config_exists"] = rc["config_exists"]
    a["config_error"] = rc.get("config_error", False)
    a["fallbacks"] = rc.get("fallbacks", [])


@app.route("/")
def index():
    projects = hub.list_projects()
    if projects:
        first = dict(projects[0])
        return redirect(url_for("project_view", project_id=first["id"]))
    return render_template("index.html", projects=[], profiles=_profiles())


@app.route("/project/new", methods=["GET", "POST"])
def new_project():
    """Create a new project via web form."""
    if request.method == "GET":
        return render_template("new_project.html", projects=[dict(p) for p in hub.list_projects()])

    # POST: create the project
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    brief = request.form.get("brief", "").strip()

    if not name:
        flash("Project name is required.", "error")
        return redirect(url_for("new_project"))
    if not brief:
        flash("Project description is required.", "error")
        return redirect(url_for("new_project"))

    try:
        pid = hub.create_project(name, description, brief)
        flash(f"Project '{name}' created (#{pid}).", "success")
        return redirect(url_for("project_view", project_id=pid))
    except Exception as e:
        traceback.print_exc()
        flash(f"Failed to create project: {e}", "error")
        return redirect(url_for("new_project"))


@app.route("/settings")
def hub_settings():
    """Hub settings: view/change workspace directory."""
    cfg = hub.load_config()
    ws_dir = hub.get_workspace_dir()
    projects = [dict(p) for p in hub.list_projects()]
    return render_template("hub_settings.html",
                           workspace_dir=str(ws_dir),
                           projects_dir=str(hub.get_projects_dir()),
                           db_path=str(hub.get_db_path()),
                           hub_config=cfg.get("hub", {}),
                           projects=projects,
                           project_count=len(projects))


@app.route("/settings/workspace", methods=["POST"])
def change_workspace():
    """Change the workspace directory."""
    new_ws = request.form.get("workspace_dir", "").strip()
    if not new_ws:
        flash("Workspace directory cannot be empty.", "error")
        return redirect(url_for("hub_settings"))
    try:
        # Update config.yaml
        import yaml
        cfg_path = hub.CONFIG_PATH
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        cfg.setdefault("hub", {})["workspace_dir"] = new_ws
        with open(cfg_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        flash(f"Workspace changed to {new_ws}. Restart the server to pick up the change.", "success")
    except Exception as e:
        traceback.print_exc()
        flash(f"Failed to change workspace: {e}", "error")
    return redirect(url_for("hub_settings"))


@app.route("/project/<int:project_id>")
def project_view(project_id: int, tab: str = "overview"):
    """Project page shell — renders the tab bar + the requested tab content.
    The default tab is 'overview'. Phase tabs use their slug (e.g. '01-ideation').
    """
    tab = request.args.get("tab", "overview")
    proj = hub.get_project(project_id)
    if not proj:
        flash(f"Project #{project_id} not found", "error")
        return redirect(url_for("index"))
    proj = dict(proj)
    projects = [dict(p) for p in hub.list_projects()]
    cfg = hub.load_config()
    phase_configs = hub.get_phases_config(cfg)

    # Project directory path + setting.md content
    proj_dir = hub.get_project_dir(project_id)
    proj_dir_str = str(proj_dir) if proj_dir else "(not found)"
    settings_content = ""
    settings_html = ""
    if proj_dir:
        s = proj_dir / "setting.md"
        if s.exists():
            settings_content = s.read_text()
            try:
                import markdown as md
                settings_html = md.markdown(settings_content, extensions=["extra", "sane_lists"])
            except Exception:
                settings_html = ""

    # All phase summaries (for overview) + phase status for phase tabs
    phase_summaries = hub.get_all_phase_summaries(project_id)

    # If a phase tab is requested, load its full status
    phase_status = None
    phase_cfg = None
    if tab != "overview":
        phase_cfg = hub.get_phase_config(cfg, tab)
        if phase_cfg:
            phase_status = hub.get_phase_status(project_id, tab)

    ctx = dict(
        project=proj,
        projects=projects,
        phase_configs=phase_configs,
        phase_summaries=phase_summaries,
        active_tab=tab,
        settings_content=settings_content,
        settings_html=settings_html,
        proj_dir=proj_dir_str,
        phase_cfg=phase_cfg,
        phase_status=phase_status,
        profiles=_profiles(),
    )
    # HTMX tab clicks return just the tab content partial
    if request.headers.get("HX-Request") == "true":
        return render_template("_project_tabs.html", **ctx)
    return render_template("project.html", **ctx)


@app.route("/project/<int:project_id>/phase/<phase_slug>")
def phase_view(project_id: int, phase_slug: str):
    """View a specific phase with its pattern, participants, and task status."""
    proj = hub.get_project(project_id)
    if not proj:
        flash(f"Project #{project_id} not found", "error")
        return redirect(url_for("index"))
    proj = dict(proj)
    projects = [dict(p) for p in hub.list_projects()]

    cfg = hub.load_config()
    phase_cfg = hub.get_phase_config(cfg, phase_slug)
    if not phase_cfg:
        flash(f"Phase '{phase_slug}' not found in config", "error")
        return redirect(url_for("project_view", project_id=project_id))

    phase_status = hub.get_phase_status(project_id, phase_slug)
    proj_dir = hub.get_project_dir(project_id)
    settings_content = ""
    if proj_dir:
        s = proj_dir / "setting.md"
        if s.exists():
            settings_content = s.read_text()

    return render_template(
        "phase_view.html",
        project=proj,
        projects=projects,
        phase_cfg=phase_cfg,
        phase_status=phase_status,
        settings_content=settings_content,
        all_phases=hub.get_phases_config(cfg),
    )


@app.route("/project/<int:project_id>/phase/<phase_slug>/start", methods=["POST"])
def start_phase(project_id: int, phase_slug: str):
    """Start a phase — creates task chain via setup_phase()."""
    try:
        phase_id = hub.setup_phase(project_id, phase_slug)
        flash(f"Phase started (phase #{phase_id}). Task chain created on kanban.", "success")
    except Exception as e:
        traceback.print_exc()
        flash(f"Phase setup failed: {e}", "error")
    return redirect(url_for("phase_view", project_id=project_id, phase_slug=phase_slug))


@app.route("/project/<int:project_id>/phase/<phase_slug>/progress")
def phase_progress(project_id: int, phase_slug: str):
    """HTMX-polled partial: phase task status."""
    hub.poll_phase(project_id, phase_slug)
    phase_status = hub.get_phase_status(project_id, phase_slug)
    return render_template("_phase_progress.html",
                           phase_status=phase_status, project_id=project_id,
                           phase_slug=phase_slug)


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


@app.route("/project/<int:project_id>/open-folder", methods=["POST"])
def open_folder(project_id: int):
    """Open the project directory in the host OS file browser."""
    import subprocess
    proj_dir = hub.get_project_dir(project_id)
    if not proj_dir or not proj_dir.exists():
        return "project directory not found", 404
    try:
        # xdg-open is the standard Linux way; macOS would use "open", Windows "explorer"
        subprocess.Popen(["xdg-open", str(proj_dir)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "", 204
    except FileNotFoundError:
        return "xdg-open not found (this needs a desktop environment)", 500
    except Exception as e:
        return str(e), 500


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
    for a in agents:
        _enrich_agent(a)
    return render_template("profiles.html", agents=agents,
                           all_profiles=list_hermes_profiles())


@app.route("/agent/<agent_id>/profile", methods=["POST"])
def assign_agent_profile(agent_id: str):
    """Reassign an agent role to a different Hermes profile (saved to config.yaml),
    then return the refreshed card so HTMX can swap it in."""
    new_profile = (request.form.get("profile") or "").strip()
    if not new_profile:
        return "missing profile", 400
    if new_profile not in list_hermes_profiles():
        return "unknown profile", 400
    if not _set_agent_profile(agent_id, new_profile):
        return "unknown agent", 400
    cfg = hub.load_config()
    agent = hub.get_agent(cfg, agent_id)
    if not agent:
        return "agent vanished", 404
    agent = dict(agent)
    _enrich_agent(agent)
    return render_template("_profile_card.html", a=agent,
                           all_profiles=list_hermes_profiles())


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
