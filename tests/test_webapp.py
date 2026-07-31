from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

import webapp
from core import web_phase_data


PROJECT_ID = 1
DISCOVERY = "01-discovery"
VALIDATION = "02-validation"


def _test_phases() -> list[dict]:
    return [
        {
            "slug": DISCOVERY,
            "name": "Discovery",
            "description": "Explore the research question.",
            "pattern": "parallel",
            "rounds": {"min": 1, "default": 2, "max": 4},
            "gated_by": [],
            "folder": "references/",
            "members": ["lead", "analyst"],
        },
        {
            "slug": VALIDATION,
            "name": "Validation",
            "description": "Validate the proposed result.",
            "pattern": "sequential",
            "rounds": {"min": 2, "default": 2, "max": 2},
            "gated_by": [DISCOVERY],
            "folder": "draft/validation/",
            "members": ["analyst", "lead"],
            "stages": [
                {
                    "role": "analyst",
                    "name": "Build",
                    "description": "Build the validation artifact.",
                },
                {
                    "role": "lead",
                    "name": "Review",
                    "description": "Review the complete artifact.",
                },
            ],
        },
    ]


@pytest.fixture
def web_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    project_dir = tmp_path / "workspace" / "projects" / "project-001-test"
    project_dir.mkdir(parents=True)
    (project_dir / "setting.md").write_text(
        "# Test brief\n\nAssess the evidence.", encoding="utf-8"
    )
    project = {
        "id": PROJECT_ID,
        "name": "Test Project",
        "description": "A temporary research project",
        "status": "active",
        "directory_name": project_dir.name,
    }
    phases = _test_phases()
    config = {
        "hub": {"name": "Test Hub", "workspace_dir": str(tmp_path / "workspace")},
        "agents": [],
        "phases": phases,
    }

    monkeypatch.setattr(
        webapp.hub,
        "get_project",
        lambda project_id: project if project_id == PROJECT_ID else None,
    )
    monkeypatch.setattr(
        webapp.hub,
        "get_project_dir",
        lambda project_id: project_dir if project_id == PROJECT_ID else None,
    )
    monkeypatch.setattr(webapp.hub, "list_projects", lambda: [project])
    monkeypatch.setattr(webapp.hub, "load_config", lambda: config)
    monkeypatch.setattr(
        webapp.hub, "get_workspace_dir", lambda: tmp_path / "workspace"
    )
    monkeypatch.setattr(webapp, "_profiles", lambda: [])
    monkeypatch.setattr(webapp, "reconcile_active_run", lambda _project_dir: None)
    monkeypatch.setitem(webapp.app.config, "TESTING", True)
    monkeypatch.setitem(webapp.app.config, "SECRET_KEY", "test-only-secret")

    with webapp.app.test_client() as client:
        yield {
            "client": client,
            "project": project,
            "project_dir": project_dir,
            "config": config,
            "phases": phases,
        }


@pytest.fixture
def profile_web_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    hermes_root = tmp_path / "hermes"
    profile_name = "lead-profile"
    profile_home = hermes_root / "profiles" / profile_name
    profile_home.mkdir(parents=True)
    (profile_home / "config.yaml").write_text(
        "model:\n  default: test-model\n  provider: test-provider\n",
        encoding="utf-8",
    )
    agent = {
        "id": "research_lead",
        "profile": profile_name,
        "name": "Research Lead",
        "role": "scientific framing and synthesis",
    }
    config = {
        "hub": {"name": "Test Hub", "workspace_dir": str(tmp_path / "workspace")},
        "agents": [agent],
        "phases": [],
    }

    monkeypatch.setenv("RESEARCH_HUB_HERMES_ROOT", str(hermes_root))
    monkeypatch.setattr(webapp.hub, "load_config", lambda: config)
    monkeypatch.setattr(webapp.hub, "list_projects", lambda: [])
    monkeypatch.setattr(webapp.hub, "get_project_dir", lambda _project_id: None)
    monkeypatch.setattr(webapp, "_profiles", lambda: [agent])
    monkeypatch.setitem(webapp.app.config, "TESTING", True)
    monkeypatch.setitem(webapp.app.config, "SECRET_KEY", "test-only-secret")

    with webapp.app.test_client() as client:
        yield {
            "client": client,
            "config": config,
            "agent": agent,
            "hermes_root": hermes_root,
            "profile_home": profile_home,
        }


def _csrf(client) -> str:
    token = "csrf-token-for-tests"
    with client.session_transaction() as session:
        session["csrf_token"] = token
    return token


def _project_identity(web_env: dict) -> str:
    return webapp._make_project_identity_token(
        PROJECT_ID, web_env["project"], web_env["project_dir"]
    )


def _skill_action_token(
    profile_web_env: dict,
    skill_name: str = "stat-paper-writing",
) -> str:
    agent = profile_web_env["agent"]
    status = webapp.profile_skills.skill_status(str(agent["profile"]), skill_name)
    return webapp._make_skill_action_token(str(agent["id"]), status)


def _ready_prerequisites(*_args, **_kwargs) -> dict:
    return {"satisfied": True, "blockers": [], "requirements": []}


def _ready_phase_five_branch(_project: Path, method: dict) -> dict:
    method_id = str(method["stable_id"])
    method_version = str(method["version"])
    method_sha256 = str(method["sha256"])
    requirements = []
    for phase_slug, label, run_id, branch_specific in (
        (
            "01-literature-review",
            "Phase 1 literature review",
            "literature-ready",
            False,
        ),
        (
            webapp.project_state.METHOD_DEVELOPMENT_PHASE,
            "Phase 2 method development",
            "method-menu-ready",
            False,
        ),
        (
            "03-idea-evaluation",
            "Phase 3 theoretical development",
            "theory-ready",
            True,
        ),
        (
            "04-draft-assembly",
            "Phase 4 implementation and experiments",
            "experiment-ready",
            True,
        ),
    ):
        result = {
            "phase": phase_slug,
            "run_id": run_id,
            "status": "awaiting_review",
            "scientific_outcome": "Complete",
        }
        if branch_specific:
            result.update({
                "method_id": method_id,
                "method_version": method_version,
                "method_sha256": method_sha256,
            })
        requirements.append({
            "phase": phase_slug,
            "label": label,
            "satisfied": True,
            "result": result,
        })
    return {
        "ready": True,
        "method_id": method_id,
        "method_version": method_version,
        "method_sha256": method_sha256,
        "requirements": requirements,
        "blockers": [],
    }


def _launch_tokens(
    web_env: dict,
    phase_slug: str,
    report: dict | None = None,
    *,
    effective_phase: dict | None = None,
) -> dict[str, str]:
    prerequisite_report = report if report is not None else _ready_prerequisites()
    tokens = {
        "phase_plan_version": webapp.launch_plan_version(
            web_env["config"], phase_slug, effective_phase=effective_phase
        ),
        "prerequisite_report_version": webapp.decision_report_version(
            "prerequisite", prerequisite_report
        ),
    }
    configured_phase = effective_phase or next(
        phase
        for phase in web_env["config"]["phases"]
        if phase["slug"] == phase_slug
    )
    uses_catalog_method = webapp.phase_uses_catalog_method_selection(
        configured_phase
    )
    if (
        phase_slug == webapp.project_state.METHOD_DEVELOPMENT_PHASE
        or uses_catalog_method
    ):
        tokens["method_menu_version"] = webapp.method_menu.catalog_version(
            web_env["project_dir"]
        )
    if uses_catalog_method:
        tokens["knowledge_heads_version"] = "a" * 64
        if phase_slug in {
            webapp.IDEA_EVALUATION_PHASE,
            webapp.DRAFT_ASSEMBLY_PHASE,
        }:
            tokens["phase_two_review_version"] = "c" * 64
        if phase_slug == webapp.PAPER_WRITING_PHASE:
            tokens["branch_graph_version"] = "b" * 64
    return tokens


def test_empty_workspace_get_renders_onboarding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webapp.hub, "list_projects", lambda: [])
    monkeypatch.setattr(webapp, "_profiles", lambda: [])
    monkeypatch.setitem(webapp.app.config, "TESTING", True)
    monkeypatch.setitem(webapp.app.config, "SECRET_KEY", "test-only-secret")

    with webapp.app.test_client() as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "No projects" in response.get_data(as_text=True)
    assert 'href="/project/new"' in response.get_data(as_text=True)


def test_profiles_status_is_read_only_and_explains_explicit_install(
    profile_web_env: dict,
) -> None:
    root = profile_web_env["hermes_root"]
    before = sorted(
        (str(path.relative_to(root)), path.read_bytes() if path.is_file() else None)
        for path in root.rglob("*")
    )

    response = profile_web_env["client"].get("/profiles")

    after = sorted(
        (str(path.relative_to(root)), path.read_bytes() if path.is_file() else None)
        for path in root.rglob("*")
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert before == after
    assert "stat-paper-writing" in body
    assert "Not installed" in body
    assert "Install recommended skill" in body
    assert (
        'aria-label="Install stat-paper-writing in profile lead-profile '
        'for Research Lead"' in body
    )
    assert 'name="skill_action_token"' in body
    assert "Status checks are read-only" in body


def test_profile_options_preserve_outside_reviewer_independence() -> None:
    agents = [
        {"id": "research_lead", "profile": "lead-profile"},
        {"id": "theorist", "profile": "shared-profile"},
        {"id": "data_scientist", "profile": "shared-profile"},
        {"id": "paper_reviewer", "profile": "review-profile"},
    ]
    available = [
        "lead-profile",
        "shared-profile",
        "review-profile",
        "unused-profile",
    ]

    assert webapp._profile_options_for_agent(
        agents[0], agents, available
    ) == ["lead-profile", "shared-profile", "unused-profile"]
    assert webapp._profile_options_for_agent(
        agents[3], agents, available
    ) == ["review-profile", "unused-profile"]


def test_profile_listing_uses_only_the_root_default_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "hermes"
    (root / "profiles" / "default").mkdir(parents=True)
    (root / "profiles" / "named-profile").mkdir()
    (root / "config.yaml").write_text("model: root-model\n", encoding="utf-8")
    (root / "profiles" / "default" / "config.yaml").write_text(
        "model: wrong-default\n", encoding="utf-8"
    )
    (root / "profiles" / "named-profile" / "config.yaml").write_text(
        "model: named-model\n", encoding="utf-8"
    )
    monkeypatch.setenv("RESEARCH_HUB_HERMES_ROOT", str(root))

    assert webapp.list_hermes_profiles() == ["default", "named-profile"]


def test_profile_skill_install_is_explicit_and_idempotent(
    profile_web_env: dict,
) -> None:
    client = profile_web_env["client"]
    profile_home = profile_web_env["profile_home"]
    payload = {
        "csrf_token": _csrf(client),
        "skill_action_token": _skill_action_token(profile_web_env),
    }

    first = client.post(
        "/agent/research_lead/skills/install",
        data=payload,
        follow_redirects=True,
    )
    installed = profile_home / "skills" / "stat-paper-writing"
    assert first.status_code == 200
    assert "Installed stat-paper-writing" in first.get_data(as_text=True)
    assert (installed / "SKILL.md").is_file()
    assert (installed / "LICENSE").read_bytes() == (
        webapp.profile_skills.APP_ROOT / "bundled_skills" / "LICENSE"
    ).read_bytes()
    first_digest = webapp.profile_skills.bundle_digest(installed)

    second = client.post(
        "/agent/research_lead/skills/install",
        data={
            "csrf_token": _csrf(client),
            "skill_action_token": _skill_action_token(profile_web_env),
        },
        follow_redirects=True,
    )
    assert second.status_code == 200
    assert "already current" in second.get_data(as_text=True)
    assert webapp.profile_skills.bundle_digest(installed) == first_digest


def test_profile_assignment_does_not_install_or_move_skills(
    profile_web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = profile_web_env["client"]
    root = profile_web_env["hermes_root"]
    other_home = root / "profiles" / "other-profile"
    other_home.mkdir(parents=True)
    (other_home / "config.yaml").write_text("model: other\n", encoding="utf-8")

    def mutate_config(mutator):
        mutator(profile_web_env["config"])
        return "", ""

    monkeypatch.setattr(webapp, "_mutate_config", mutate_config)
    response = client.post(
        "/agent/research_lead/profile",
        data={"csrf_token": _csrf(client), "profile": "other-profile"},
    )

    assert response.status_code == 302
    assert profile_web_env["agent"]["profile"] == "other-profile"
    assert not (profile_web_env["profile_home"] / "skills").exists()
    assert not (other_home / "skills").exists()


def test_profile_skill_conflict_requires_confirmed_replacement(
    profile_web_env: dict,
) -> None:
    client = profile_web_env["client"]
    profile_home = profile_web_env["profile_home"]
    installed = profile_home / "skills" / "stat-paper-writing"
    installed.mkdir(parents=True)
    local_file = installed / "SKILL.md"
    local_file.write_text("local skill\n", encoding="utf-8")
    payload = {
        "csrf_token": _csrf(client),
        "skill_action_token": _skill_action_token(profile_web_env),
    }

    status_page = client.get("/profiles")
    body = status_page.get_data(as_text=True)
    assert "Different local copy" in body
    assert "Replace with bundled copy" in body

    refused = client.post(
        "/agent/research_lead/skills/install",
        data=payload,
        follow_redirects=True,
    )
    assert "explicit replacement is required" in refused.get_data(as_text=True)
    assert local_file.read_text(encoding="utf-8") == "local skill\n"

    replaced = client.post(
        "/agent/research_lead/skills/install",
        data={**payload, "replace": "1"},
        follow_redirects=True,
    )
    assert replaced.status_code == 200
    assert "Replaced stat-paper-writing" in replaced.get_data(as_text=True)
    assert local_file.read_text(encoding="utf-8") != "local skill\n"
    backups = [
        path
        for path in profile_home.rglob("stat-paper-writing*")
        if path != installed and path.is_dir()
    ]
    assert len(backups) == 1
    assert (backups[0] / "SKILL.md").read_text(encoding="utf-8") == "local skill\n"


def test_profile_skill_install_rejects_stale_profile_and_active_run(
    profile_web_env: dict, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = profile_web_env["client"]
    profile_home = profile_web_env["profile_home"]
    expected = profile_web_env["agent"]["profile"]
    stale_action = _skill_action_token(profile_web_env)
    profile_web_env["agent"]["profile"] = "other-profile"

    stale = client.post(
        "/agent/research_lead/skills/install",
        data={"csrf_token": _csrf(client), "skill_action_token": stale_action},
        follow_redirects=True,
    )
    assert "profile assignment changed" in stale.get_data(as_text=True)
    assert not (profile_home / "skills").exists()

    profile_web_env["agent"]["profile"] = expected
    project_dir = tmp_path / "active-project"
    project_dir.mkdir()
    monkeypatch.setattr(
        webapp.hub, "list_projects", lambda: [{"id": 7, "name": "Active study"}]
    )
    monkeypatch.setattr(webapp.hub, "get_project_dir", lambda _project_id: project_dir)
    monkeypatch.setattr(
        webapp.project_state, "get_active_run", lambda _project_dir: {"run_id": "run-1"}
    )
    blocked = client.post(
        "/agent/research_lead/skills/install",
        data={
            "csrf_token": _csrf(client),
            "skill_action_token": _skill_action_token(profile_web_env),
        },
        follow_redirects=True,
    )
    assert "Stop the active run for Active study" in blocked.get_data(as_text=True)
    assert not (profile_home / "skills").exists()


def test_profile_skill_install_requires_csrf(profile_web_env: dict) -> None:
    response = profile_web_env["client"].post(
        "/agent/research_lead/skills/install",
        data={"skill_action_token": _skill_action_token(profile_web_env)},
    )
    assert response.status_code == 400


def test_profile_skill_action_requires_valid_signature_and_role_scope(
    profile_web_env: dict,
) -> None:
    client = profile_web_env["client"]
    writing_token = _skill_action_token(profile_web_env)
    replacement = "0" if writing_token[-1] != "0" else "1"
    tampered = client.post(
        "/agent/research_lead/skills/install",
        data={
            "csrf_token": _csrf(client),
            "skill_action_token": writing_token[:-1] + replacement,
        },
        follow_redirects=True,
    )
    assert "skill action is missing or invalid" in tampered.get_data(as_text=True)

    agent = profile_web_env["agent"]
    reviewer_status = webapp.profile_skills.skill_status(
        str(agent["profile"]), "stat-paper-reviewer"
    )
    wrong_skill_token = webapp._make_skill_action_token(
        str(agent["id"]), reviewer_status
    )
    wrong_skill = client.post(
        "/agent/research_lead/skills/install",
        data={
            "csrf_token": _csrf(client),
            "skill_action_token": wrong_skill_token,
        },
        follow_redirects=True,
    )
    assert "not recommended for this research role" in wrong_skill.get_data(
        as_text=True
    )
    assert not (profile_web_env["profile_home"] / "skills").exists()


def test_profile_skill_replacement_rejects_changed_reviewed_copy(
    profile_web_env: dict,
) -> None:
    client = profile_web_env["client"]
    installed = (
        profile_web_env["profile_home"] / "skills" / "stat-paper-writing"
    )
    installed.mkdir(parents=True)
    local_file = installed / "SKILL.md"
    local_file.write_text("first local copy\n", encoding="utf-8")
    reviewed_action = _skill_action_token(profile_web_env)

    local_file.write_text("changed after review\n", encoding="utf-8")
    response = client.post(
        "/agent/research_lead/skills/install",
        data={
            "csrf_token": _csrf(client),
            "skill_action_token": reviewed_action,
            "replace": "1",
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "skill status changed" in body
    assert local_file.read_text(encoding="utf-8") == "changed after review\n"
    assert not (profile_web_env["profile_home"] / ".research-hub-skill-backups").exists()


def test_profile_skill_replacement_rechecks_state_under_profile_lock(
    profile_web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = profile_web_env["client"]
    installed = (
        profile_web_env["profile_home"] / "skills" / "stat-paper-writing"
    )
    installed.mkdir(parents=True)
    local_file = installed / "SKILL.md"
    local_file.write_text("reviewed local copy\n", encoding="utf-8")
    reviewed_action = _skill_action_token(profile_web_env)
    provision_skill = webapp.profile_skills.provision_skill

    def change_before_profile_lock(*args, **kwargs):
        local_file.write_text("changed before profile lock\n", encoding="utf-8")
        return provision_skill(*args, **kwargs)

    monkeypatch.setattr(
        webapp.profile_skills,
        "provision_skill",
        change_before_profile_lock,
    )
    response = client.post(
        "/agent/research_lead/skills/install",
        data={
            "csrf_token": _csrf(client),
            "skill_action_token": reviewed_action,
            "replace": "1",
        },
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "changed after the installation was reviewed" in body
    assert local_file.read_text(encoding="utf-8") == "changed before profile lock\n"
    assert not (profile_web_env["profile_home"] / ".research-hub-skill-backups").exists()


def test_failed_workspace_change_restores_previous_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yaml"
    original = "hub:\n  workspace_dir: original-workspace\n"
    config_path.write_text(original, encoding="utf-8")

    monkeypatch.setattr(webapp.hub, "CONFIG_PATH", config_path)
    monkeypatch.setattr(webapp.hub, "list_projects", lambda: [])
    monkeypatch.setattr(
        webapp,
        "_mutate_config",
        lambda _mutator: config_path.write_text(
            "hub:\n  workspace_dir: unavailable-workspace\n", encoding="utf-8"
        ),
    )
    monkeypatch.setattr(
        webapp.hub,
        "init_db",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("workspace unavailable")),
    )
    monkeypatch.setitem(webapp.app.config, "TESTING", True)
    monkeypatch.setitem(webapp.app.config, "SECRET_KEY", "test-only-secret")

    with webapp.app.test_client() as client:
        response = client.post(
            "/settings/workspace",
            data={
                "csrf_token": _csrf(client),
                "workspace_dir": str(tmp_path / "unavailable-workspace"),
            },
        )

    assert response.status_code == 302
    assert config_path.read_text(encoding="utf-8") == original


def test_configuration_lock_rejects_a_nonregular_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("hub: {}\n", encoding="utf-8")
    monkeypatch.setattr(webapp.hub, "CONFIG_PATH", config_path)
    config_path.with_suffix(".yaml.lock").mkdir()

    with pytest.raises(RuntimeError, match="hub configuration lock is unavailable"):
        with webapp._config_file_lock():
            pytest.fail("a directory must never be used as the configuration lock")


@pytest.mark.skipif(os.name == "nt", reason="POSIX symbolic-link behavior")
def test_configuration_lock_rejects_a_symbolic_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("hub: {}\n", encoding="utf-8")
    monkeypatch.setattr(webapp.hub, "CONFIG_PATH", config_path)
    target = tmp_path / "unrelated-empty-file"
    target.write_bytes(b"")
    config_path.with_suffix(".yaml.lock").symlink_to(target)

    with pytest.raises(RuntimeError, match="hub configuration lock is unavailable"):
        with webapp._config_file_lock():
            pytest.fail("a linked lock file must never be acquired")
    assert target.read_bytes() == b""


def test_project_and_phase_pages_render_manual_control_contract(web_env: dict) -> None:
    client = web_env["client"]

    overview = client.get(f"/project/{PROJECT_ID}")
    assert overview.status_code == 200
    overview_html = overview.get_data(as_text=True)
    assert "Research progress" in overview_html
    assert f'href="/project/{PROJECT_ID}?tab={DISCOVERY}"' in overview_html

    phase = client.get(f"/project/{PROJECT_ID}?tab={VALIDATION}")
    assert phase.status_code == 200
    phase_html = phase.get_data(as_text=True)
    # Simplified UI: launch form is present, prerequisite override is surfaced only when needed
    assert f'action="/project/{PROJECT_ID}/phase/{VALIDATION}/start"' in phase_html
    assert 'name="prerequisite_report_version"' in phase_html
    assert "phase-status-upper" in phase_html  # simplified phase header

    partial = client.get(
        f"/project/{PROJECT_ID}?tab={DISCOVERY}", headers={"HX-Request": "true"}
    )
    assert partial.status_code == 200
    partial_html = partial.get_data(as_text=True)
    assert '<section id="project-tabs"' in partial_html
    assert "<!DOCTYPE html>" not in partial_html


def test_ready_launch_form_contains_both_current_decision_tokens(
    web_env: dict,
) -> None:
    project_dir = web_env["project_dir"]
    config = web_env["config"]
    report = webapp.project_state.prerequisite_report(
        project_dir,
        DISCOVERY,
        {DISCOVERY: [], VALIDATION: [DISCOVERY]},
        current_records=True,
    )
    assert report["satisfied"] is True
    phase_plan_version = webapp.launch_plan_version(config, DISCOVERY)
    prerequisite_report_version = webapp.decision_report_version(
        "prerequisite", report
    )

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={DISCOVERY}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    launch_action = f'action="/project/{PROJECT_ID}/phase/{DISCOVERY}/start"'
    launch_form_count = body.count(launch_action)
    assert launch_form_count >= 1
    assert (
        f'name="phase_plan_version" value="{phase_plan_version}"'
        in body
    )
    assert (
        'name="prerequisite_report_version" '
        f'value="{prerequisite_report_version}"'
        in body
    )
    assert body.count('name="phase_plan_version"') == launch_form_count
    assert body.count('name="prerequisite_report_version"') == launch_form_count


def test_paper_page_prepares_only_the_active_phase_plan_token(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    paper_slug = "05-review-revision"
    paper_phase = {
        "slug": paper_slug,
        "name": "Paper Writing",
        "description": "Write and review the paper.",
        "pattern": "sequential",
        "rounds": {"min": 5, "default": 5, "max": 5},
        "gated_by": [],
        "folder": "draft/",
        "members": [
            "research_lead",
            "theorist",
            "data_scientist",
            "paper_reviewer",
        ],
        "stages": [
            {"role": "research_lead", "name": f"Stage {number}"}
            for number in range(1, 6)
        ],
    }
    web_env["config"]["phases"].append(paper_phase)
    captured: dict = {}

    def capture_template(_name: str, **context):
        captured.update(context)
        return "captured"

    monkeypatch.setattr(webapp, "render_template", capture_template)
    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={paper_slug}"
    )

    expected_full = webapp.launch_plan_version(web_env["config"], paper_slug)
    assert response.status_code == 200
    assert captured["phase_data"]["phase_plan_version"] == expected_full
    assert "review_phase_plan_version" not in captured["phase_data"]


def test_csrf_rejects_missing_token_and_accepts_valid_start(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    project_dir = web_env["project_dir"]
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 3})
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    monkeypatch.setattr(
        webapp.project_state,
        "approval_context_report",
        lambda *_args, **_kwargs: {
            "requires_acknowledgement": False,
            "changed_sources": [],
        },
    )
    run_scan = Mock(side_effect=AssertionError("ordinary launch must not scan for a replacement"))
    monkeypatch.setattr(webapp.project_state, "get_runs", run_scan)

    rejected = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/start",
        data={"rounds": "3", "feedback": "Check robustness."},
    )
    assert rejected.status_code == 400
    launched.assert_not_called()

    token = _csrf(client)
    identity = _project_identity(web_env)
    accepted = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, DISCOVERY),
            "rounds": "3",
            "feedback": "Check robustness.",
        },
    )
    assert accepted.status_code == 302
    assert accepted.headers["Location"].endswith(
        f"/project/{PROJECT_ID}?tab={DISCOVERY}"
    )
    launched.assert_called_once_with(
        project_dir.resolve(),
        PROJECT_ID,
        DISCOVERY,
        "Check robustness.",
        3,
        prerequisite_override_reason="",
        prerequisite_report_version=webapp.decision_report_version(
            "prerequisite", _ready_prerequisites()
        ),
        replace_awaiting_review_note=None,
        run_specific_method_id="",
        run_specific_method_version="",
        expected_phase_plan_version=webapp.launch_plan_version(
            web_env["config"], DISCOVERY
        ),
        expected_workspace_path=str(web_env["project_dir"].parents[1].resolve()),
        expected_project_directory_name=web_env["project_dir"].name,
        expected_project_path=str(web_env["project_dir"].resolve()),
        include_downstream=False,
    )
    run_scan.assert_not_called()


def test_launch_rejects_a_missing_or_stale_phase_plan_version(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = web_env["client"]
    token = _csrf(client)
    identity = _project_identity(web_env)
    actual_launch = webapp.launch_run
    launched = Mock(wraps=actual_launch)
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state,
        "prerequisite_report",
        _ready_prerequisites,
    )
    common = {
        "csrf_token": token,
        "project_identity": identity,
        "prerequisite_report_version": webapp.decision_report_version(
            "prerequisite", _ready_prerequisites()
        ),
        "rounds": "2",
    }

    missing = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/start",
        data=common,
        follow_redirects=True,
    )

    assert missing.status_code == 200
    assert "Phase Plan Version is required" in missing.get_data(as_text=True)
    launched.assert_not_called()

    stale = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/start",
        data={**common, "phase_plan_version": "0" * 64},
        follow_redirects=True,
    )

    assert stale.status_code == 200
    assert "phase plan or scientific instructions changed" in (
        stale.get_data(as_text=True)
    )
    assert launched.call_count == 1
    assert webapp.project_state.get_active_run(web_env["project_dir"]) is None


def test_project_mutations_reject_an_identity_from_the_previous_workspace(
    web_env: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = web_env["client"]
    csrf = _csrf(client)
    stale_identity = _project_identity(web_env)
    new_workspace = tmp_path / "replacement-workspace"
    new_project_dir = new_workspace / "projects" / web_env["project_dir"].name
    new_project_dir.mkdir(parents=True)
    new_setting = new_project_dir / "setting.md"
    new_setting.write_text("# Replacement project\n", encoding="utf-8")
    monkeypatch.setattr(webapp.hub, "get_workspace_dir", lambda: new_workspace)
    monkeypatch.setattr(
        webapp.hub,
        "get_project_dir",
        lambda project_id: new_project_dir if project_id == PROJECT_ID else None,
    )
    launched = Mock()
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    launch_response = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/start",
        data={
            "csrf_token": csrf,
            "project_identity": stale_identity,
            "rounds": "2",
        },
    )
    settings_response = client.post(
        f"/project/{PROJECT_ID}/settings",
        data={
            "csrf_token": csrf,
            "project_identity": stale_identity,
            "settings_content": "# Wrong project\n",
        },
    )
    progress_response = client.get(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/progress",
        query_string={"project_identity": stale_identity},
    )

    assert launch_response.status_code == 302
    assert settings_response.status_code == 302
    assert progress_response.status_code == 409
    assert "workspace or project changed" in progress_response.get_data(
        as_text=True
    ).lower()
    launched.assert_not_called()
    assert new_setting.read_text(encoding="utf-8") == "# Replacement project\n"

    current_identity = webapp._make_project_identity_token(
        PROJECT_ID, web_env["project"], new_project_dir
    )
    accepted = client.post(
        f"/project/{PROJECT_ID}/settings",
        data={
            "csrf_token": csrf,
            "project_identity": current_identity,
            "settings_content": "# Current project\n",
        },
    )
    assert accepted.status_code == 302
    assert new_setting.read_text(encoding="utf-8") == "# Current project"


def test_phase_three_proof_audit_and_legacy_review_target_is_rejected(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    project_dir = web_env["project_dir"].resolve()
    phase_three = {
        "slug": "03-idea-evaluation",
        "name": "Theoretical Analysis",
        "description": "Develop the theory.",
        "pattern": "sequential",
        "rounds": {"min": 3, "default": 3, "max": 3},
        "gated_by": [],
        "folder": "draft/theory/",
        "members": ["theorist", "research_lead", "paper_reviewer"],
        "proof_audit": {
            "plans": ["standard", "standard_with_audit", "audit_only"],
            "stage": {
                "role": "paper_reviewer",
                "name": "Independent proof audit",
                "description": "Audit the exact final theory artifact.",
            },
        },
        "stages": [
            {"role": "theorist", "name": "Draft", "description": "Draft."},
            {"role": "research_lead", "name": "Assess", "description": "Assess."},
            {"role": "theorist", "name": "Revise", "description": "Revise."},
        ],
    }
    phase_six = {
        "slug": "05-review-revision",
        "name": "Paper Writing",
        "description": "Write and review the paper.",
        "pattern": "sequential",
        "method_binding": True,
        "rounds": {"min": 5, "default": 5, "max": 5},
        "gated_by": [],
        "folder": "draft/",
        "members": ["research_lead", "theorist", "data_scientist", "paper_reviewer"],
        "stages": [
            {"role": "research_lead", "name": "Frame", "description": "Frame."},
            {"role": "theorist", "name": "Theory", "description": "Theory."},
            {"role": "data_scientist", "name": "Results", "description": "Results."},
            {"role": "paper_reviewer", "name": "Read", "description": "Read."},
            {"role": "paper_reviewer", "name": "Assess", "description": "Assess."},
        ],
    }
    web_env["config"]["phases"].extend([phase_three, phase_six])
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 4})
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    monkeypatch.setattr(
        webapp,
        "phase_five_branch_readiness",
        _ready_phase_five_branch,
    )
    monkeypatch.setattr(
        web_phase_data,
        "phase_five_branch_readiness",
        _ready_phase_five_branch,
    )
    _write_menu_file(project_dir, "proof-method", "recommended")
    monkeypatch.setattr(
        webapp,
        "theory_audit_source_options",
        lambda _project: [{
            "run_id": "opaque-source-run-id",
            "run_number": 1,
            "status": "approved",
            "source_round": 3,
            "sha256": "b" * 64,
        }],
    )
    token = _csrf(client)
    identity = _project_identity(web_env)

    proof_page = client.get(
        f"/project/{PROJECT_ID}?tab=03-idea-evaluation"
    )
    assert proof_page.status_code == 200
    proof_html = proof_page.get_data(as_text=True)
    assert 'name="theory_plan"' in proof_html
    assert 'value="standard"' in proof_html
    assert 'value="standard_with_audit"' in proof_html
    assert 'value="audit_only"' in proof_html
    assert 'name="proof_audit_source_run_id"' in proof_html
    assert 'value="opaque-source-run-id"' in proof_html
    assert "Choose a prior theory artifact" in proof_html
    assert 'type="hidden" name="proof_audit_source_run_id"' not in proof_html
    assert "proof_audit_source_path" not in proof_html

    proof_response = client.post(
        f"/project/{PROJECT_ID}/phase/03-idea-evaluation/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, "03-idea-evaluation"),
            "theory_plan": "standard_with_audit",
            "method_branch": "proof-method",
        },
    )
    assert proof_response.status_code == 302
    proof_call = launched.call_args
    assert proof_call.args[:5] == (
        project_dir,
        PROJECT_ID,
        "03-idea-evaluation",
        "",
        4,
    )
    assert proof_call.kwargs["theory_plan"] == "standard_with_audit"

    launched.reset_mock(return_value=True)
    launched.return_value = {"run_number": 2, "rounds_requested": 1}
    audit_only_response = client.post(
        f"/project/{PROJECT_ID}/phase/03-idea-evaluation/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, "03-idea-evaluation"),
            "theory_plan": "audit_only",
            "proof_audit_source_run_id": "opaque-source-run-id",
        },
    )
    assert audit_only_response.status_code == 302
    audit_only_call = launched.call_args
    assert audit_only_call.args[:5] == (
        project_dir,
        PROJECT_ID,
        "03-idea-evaluation",
        "",
        1,
    )
    assert audit_only_call.kwargs["theory_plan"] == "audit_only"
    assert "expected_knowledge_heads_version" not in audit_only_call.kwargs
    assert "expected_branch_graph_version" not in audit_only_call.kwargs
    assert (
        audit_only_call.kwargs["proof_audit_source_run_id"]
        == "opaque-source-run-id"
    )

    launched.reset_mock(return_value=True)
    missing_source = client.post(
        f"/project/{PROJECT_ID}/phase/03-idea-evaluation/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, "03-idea-evaluation"),
            "theory_plan": "audit_only",
        },
    )
    assert missing_source.status_code == 302
    assert launched.call_count == 0

    source_on_standard = client.post(
        f"/project/{PROJECT_ID}/phase/03-idea-evaluation/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, "03-idea-evaluation"),
            "theory_plan": "standard",
            "proof_audit_source_run_id": "opaque-source-run-id",
        },
    )
    assert source_on_standard.status_code == 302
    assert launched.call_count == 0

    launched.reset_mock()
    review_response = client.post(
        f"/project/{PROJECT_ID}/phase/05-review-revision/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, "05-review-revision"),
            "review_target": "draft/run/01/manuscript-post-review.md",
            "review_target_sha256": "a" * 64,
            "method_branch": "proof-method",
        },
    )
    assert review_response.status_code == 302
    launched.assert_not_called()


def test_legacy_phase_two_selection_remains_visible_for_schema_seven_projects(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Preserve read-only compatibility with projects created before schema 9.
    method_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    theory_slug = "03-idea-evaluation"
    numerical_slug = "04-draft-assembly"
    web_env["config"]["phases"].extend([
        {
            "slug": method_slug,
            "name": "Method Development",
            "description": "Develop and select the method.",
            "pattern": "sequential",
            "rounds": {"min": 1, "default": 1, "max": 1},
            "gated_by": [],
            "folder": "draft/method/",
            "members": ["research_lead"],
            "stages": [{"role": "research_lead"}],
        },
        {
            "slug": theory_slug,
            "name": "Theoretical Analysis",
            "description": "Develop the theory.",
            "pattern": "sequential",
            "rounds": {"min": 1, "default": 1, "max": 1},
            "gated_by": [],
            "folder": "draft/theory/",
            "members": ["theorist"],
            "stages": [
                {
                    "role": "theorist",
                    "name": "Establish the result",
                    "description": "State and justify the result.",
                }
            ],
        },
        {
            "slug": numerical_slug,
            "name": "Numerical Validation",
            "description": "Assess the method numerically.",
            "pattern": "sequential",
            "rounds": {"min": 1, "default": 1, "max": 1},
            "gated_by": [],
            "folder": "numerical/",
            "members": ["data_scientist"],
            "stages": [
                {
                    "role": "data_scientist",
                    "name": "Run the study",
                    "description": "Apply the prespecified design.",
                }
            ],
        },
    ])
    approved_method = {
        "kind": "method",
        "stable_id": "METHOD-robust-score",
        "version": "v2.1/finite-sample",
        "source_run_id": "phase-two-approved-run",
        "decision_sha256": "c" * 64,
    }
    state_data = webapp.project_state.load(web_env["project_dir"])
    state_data["phases"][method_slug] = {
        "status": "approved",
        "approved_run": approved_method["source_run_id"],
        "runs": [{
            "run_id": approved_method["source_run_id"],
            "status": "approved",
            "mode": "method selection",
            "rounds": [],
            "decision_record": {
                "sha256": approved_method["decision_sha256"],
                "data": {
                    "selected_scientific_object": {
                        "kind": approved_method["kind"],
                        "stable_id": approved_method["stable_id"],
                        "version": approved_method["version"],
                    }
                },
            },
        }],
    }
    webapp.project_state._save(web_env["project_dir"], state_data)
    monkeypatch.setattr(
        webapp.project_state,
        "run_integrity_report",
        lambda *_args, **_kwargs: {"ok": True},
    )
    monkeypatch.setattr(webapp, "theory_audit_source_options", lambda _project: [])

    for phase_slug in (theory_slug, numerical_slug):
        response = web_env["client"].get(
            f"/project/{PROJECT_ID}?tab={phase_slug}"
        )
        body = response.get_data(as_text=True)

        assert response.status_code == 200
        # Simplified UI: method appears in context chip and hidden field
        assert approved_method["stable_id"] in body

    state_data = webapp.project_state.load(web_env["project_dir"])
    state_data["phases"][method_slug]["stale"] = True
    state_data["phases"][method_slug]["stale_reason"] = (
        "The approved literature baseline changed."
    )
    webapp.project_state._save(web_env["project_dir"], state_data)

    stale_data = web_phase_data.prepare_phase_data(
        web_env["project_dir"],
        PROJECT_ID,
        next(phase for phase in web_env["config"]["phases"] if phase["slug"] == theory_slug),
        web_env["config"]["phases"],
    )
    assert stale_data["approved_method_selection"] is None

    stale_response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={theory_slug}"
    )
    stale_body = stale_response.get_data(as_text=True)
    assert stale_response.status_code == 200
    assert "Current approved Phase 02 selection" not in stale_body
    # Simplified UI: when method is stale, the approved method tag is absent from the launch form
    assert "approved-method-tag" not in stale_body


def _theory_phase_config() -> dict:
    return {
        "slug": "03-idea-evaluation",
        "name": "Theoretical Analysis",
        "description": "Develop the theory.",
        "pattern": "sequential",
        "rounds": {"min": 1, "default": 1, "max": 1},
        "gated_by": [],
        "folder": "draft/theory/",
        "members": ["theorist"],
        "stages": [
            {"role": "theorist", "name": "Establish", "description": "State it."}
        ],
    }


def _method_phase_config() -> dict:
    return {
        "slug": webapp.project_state.METHOD_DEVELOPMENT_PHASE,
        "name": "Method Development",
        "description": "Develop and maintain the candidate method menu.",
        "pattern": "debate",
        "rounds": {"min": 1, "default": 2, "max": 4},
        "gated_by": [],
        "folder": "ideas/",
        "members": ["research_lead", "theorist", "data_scientist"],
    }


def _write_menu_file(
    project_dir: Path,
    stable_id: str,
    status: str,
    *,
    number: int | None = None,
    body: str = "A precise method definition.",
) -> None:
    menu_dir = project_dir / "ideas" / "methods"
    menu_dir.mkdir(parents=True, exist_ok=True)
    if number is None:
        number = len(list(menu_dir.glob("*.md"))) + 1
    number_line = f"number: {number}\n"
    (menu_dir / f"{stable_id}.md").write_text(
        "---\n"
        f"stable_id: {stable_id}\n"
        "version: v1\n"
        f"label: {stable_id.replace('-', ' ').title()}\n"
        f"status: {status}\n"
        f"{number_line}"
        "---\n\n"
        f"# {stable_id}\n\n{body}\n",
        encoding="utf-8",
    )


def _retirement_fields(project_dir: Path, stable_id: str) -> dict[str, str]:
    entry = next(
        item
        for item in webapp.method_menu.load_method_menu(project_dir)["entries"]
        if item["stable_id"] == stable_id
    )
    return {
        "stable_id": stable_id,
        "method_version": str(entry["version"]),
        "method_sha256": str(entry["sha256"]),
    }


def test_phase_two_page_always_shows_an_empty_method_menu_and_run_panel(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={phase_slug}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Current methods" in body
    assert "No methods have been produced yet" in body
    assert "Your direction" in body
    assert "Launch Method Development" in body
    assert "Use for following phases" not in body
    assert 'name="replace_awaiting_review"' not in body
    assert "accept_selected_scientific_object" not in body


def test_phase_two_page_uses_method_files_without_a_run_summary(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    _write_menu_file(
        web_env["project_dir"],
        "spectral-graph-coupling",
        "recommended",
        number=2,
    )
    _write_menu_file(
        web_env["project_dir"],
        "old-method",
        "retired",
        number=5,
    )
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={phase_slug}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Spectral Graph Coupling" in body
    assert "Old Method" in body
    assert "#2 Spectral Graph Coupling" in body
    assert "#5 Old Method" in body
    assert body.count('class="btn btn-xs btn-retire-method"') == 1
    assert "method-status-retired" in body
    assert "Use for following phases" not in body


def test_phase_two_published_catalog_and_rerun_form_launch_without_approval(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    web_env["config"]["hub"]["allow_unattended_tools"] = True
    _write_menu_file(
        web_env["project_dir"],
        "existing-method",
        "recommended",
        number=1,
    )
    webapp.project_state.init(
        web_env["project_dir"],
        "project-001",
        "test",
        "Test Project",
        phase_slugs=[phase_slug],
        dependencies={phase_slug: []},
    )
    run_id = "published-phase-two-run"
    state_data = webapp.project_state.load(web_env["project_dir"])
    phase_state = state_data["phases"][phase_slug]
    phase_state.update({
        "status": "approved",
        "approved_run": run_id,
        "latest_run": run_id,
        "publication_readiness": "ready",
        "runs": [{
            "run_id": run_id,
            "number": 1,
            "status": "approved",
            "mode": "initial method catalog",
            "rounds_requested": 2,
            "rounds": [],
            "publication_kind": "method_menu",
            "publication_outcome": "Complete",
            "publication_readiness": "ready",
            "published_at": "2026-07-27T00:00:00+00:00",
        }],
    })
    webapp.project_state._save(web_env["project_dir"], state_data)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    client = web_env["client"]
    response = client.get(f"/project/{PROJECT_ID}?tab={phase_slug}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Current methods" in body
    assert "Existing Method" in body
    assert "Rerun Phase 2" in body
    assert "Your direction" in body
    assert 'name="replace_awaiting_review"' not in body
    assert 'name="approval_kind"' not in body
    assert "accept_selected_scientific_object" not in body
    rerun_button = re.search(
        r'<button type="submit" class="btn btn-primary btn-large"([^>]*)>'
        r"\s*Rerun Method Development",
        body,
    )
    assert rerun_button is not None
    assert "disabled" not in rerun_button.group(1)

    launched = Mock(return_value={"run_number": 2, "rounds_requested": 2})
    monkeypatch.setattr(webapp, "launch_run", launched)
    accepted = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/start",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            **_launch_tokens(web_env, phase_slug),
            "rounds": "2",
            "feedback": "Retain the strong method and reassess the alternatives.",
        },
    )

    assert accepted.status_code == 302
    call = launched.call_args
    assert call.args[:5] == (
        web_env["project_dir"].resolve(),
        PROJECT_ID,
        phase_slug,
        "Retain the strong method and reassess the alternatives.",
        2,
    )
    assert call.kwargs["replace_awaiting_review_note"] is None
    assert "replace_awaiting_review_run_id" not in call.kwargs
    assert call.kwargs["run_specific_method_id"] == ""
    assert call.kwargs["run_specific_method_version"] == ""


def test_phase_two_focused_scope_is_explicit_and_passed_to_launcher(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    web_env["config"]["hub"]["allow_unattended_tools"] = True
    _write_menu_file(
        web_env["project_dir"],
        "focused-method",
        "recommended",
        number=1,
    )
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    client = web_env["client"]
    response = client.get(f"/project/{PROJECT_ID}?tab={phase_slug}")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'name="method_catalog_scope" value="full_catalog" checked' in body
    assert 'name="method_catalog_scope" value="focused_method"' in body
    assert 'name="focused_method_id"' in body
    assert 'name="method_menu_version"' in body
    assert "Focus on one method" in body

    launched = Mock(return_value={"run_number": 1, "rounds_requested": 2})
    monkeypatch.setattr(webapp, "launch_run", launched)
    accepted = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/start",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            **_launch_tokens(web_env, phase_slug),
            "method_catalog_scope": "focused_method",
            "focused_method_id": "focused-method",
            "rounds": "2",
            "feedback": "Tighten only this method.",
        },
    )

    assert accepted.status_code == 302
    launched.assert_called_once()
    call = launched.call_args
    assert call.kwargs["method_catalog_scope"] == "focused_method"
    assert call.kwargs["focused_method_id"] == "focused-method"
    assert call.kwargs["expected_method_menu_version"] == (
        webapp.method_menu.catalog_version(web_env["project_dir"])
    )


def test_phase_two_focus_is_disabled_before_any_method_exists(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    body = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={phase_slug}"
    ).get_data(as_text=True)
    assert re.search(
        r'name="method_catalog_scope" value="focused_method"[\s\S]*?disabled',
        body,
    )
    assert "Focused runs become available after Phase 2 has produced an active method" in body


def test_phase_two_table_and_launch_controls_remain_visible_during_a_run(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    _write_menu_file(
        web_env["project_dir"],
        "active-method",
        "viable",
        number=1,
    )
    webapp.project_state.init(
        web_env["project_dir"],
        "project-001",
        "test",
        "Test Project",
        phase_slugs=[phase_slug],
        dependencies={phase_slug: []},
    )
    webapp.project_state.reserve_run(
        web_env["project_dir"],
        phase_slug,
        mode="active menu update",
        rounds_requested=1,
        dependencies={phase_slug: []},
    )
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={phase_slug}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Current methods" in body
    assert "Active Method" in body
    assert "Your direction" in body
    assert "This run is already in progress" in body
    assert "Wait for the active project run to finish" in body
    assert re.search(
        r'class="btn btn-xs btn-retire-method"[\s\S]*?disabled aria-disabled="true"',
        body,
    )
    assert 'btn btn-primary btn-large" disabled' in body


def test_phase_two_retirement_is_disabled_while_another_phase_runs(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    theory = _theory_phase_config()
    web_env["config"]["phases"].extend([_method_phase_config(), theory])
    _write_menu_file(
        web_env["project_dir"],
        "active-method",
        "viable",
        number=1,
    )
    dependencies = {phase_slug: [], theory["slug"]: []}
    webapp.project_state.init(
        web_env["project_dir"],
        "project-001",
        "test",
        "Test Project",
        phase_slugs=list(dependencies),
        dependencies=dependencies,
    )
    webapp.project_state.reserve_run(
        web_env["project_dir"],
        theory["slug"],
        mode="active theory run",
        rounds_requested=1,
        dependencies=dependencies,
    )
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={phase_slug}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Current methods" in body
    assert "Active Method" in body
    assert "Another phase is currently running" in body
    assert re.search(
        r'class="btn btn-xs btn-retire-method"[\s\S]*?disabled aria-disabled="true"'
        r'[\s\S]*?title="Wait for the active project run to finish"',
        body,
    )


def test_method_panel_uses_authoritative_current_record_status(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    theory_slug = "03-idea-evaluation"
    web_env["config"]["phases"].append(_theory_phase_config())
    _write_menu_file(
        web_env["project_dir"],
        "recorded-method",
        "recommended",
        number=1,
    )
    status_module = web_phase_data.web_branch_status
    monkeypatch.setattr(
        status_module,
        "method_record_statuses",
        lambda *_args: [{
            "has_theory_history": True,
            "knowledge_heads_version": "h" * 64,
            "phase_two_review_version": "d" * 64,
            "branch_graph_version": "g" * 64,
            "launch_context_error": "",
            "record_status": {
                "theory": {
                    "state": "update_needed",
                    "label": "Theory requires re-evaluation",
                    "reason": (
                        "The Phase 3 theory record was produced for an "
                        "earlier Phase 2 method definition."
                    ),
                    "generation": 3,
                    "source_run_id": "theory-current",
                },
                "empirical": {
                    "state": "update_needed",
                    "label": "Empirical evidence requires re-evaluation",
                    "reason": (
                        "The evidence index contains 1 outdated and 0 "
                        "unresolved entries."
                    ),
                    "generation": 4,
                    "source_run_id": "empirical-current",
                    "current_evidence_count": None,
                    "outdated_evidence_count": 1,
                    "unresolved_evidence_count": 0,
                },
                "manuscript": {
                    "state": "current",
                    "label": "Manuscript is aligned",
                    "reason": "The manuscript inputs are aligned.",
                    "generation": 2,
                    "source_run_id": "manuscript-current",
                },
            },
        }],
    )
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    monkeypatch.setattr(webapp, "theory_audit_source_options", lambda _project: [])

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={theory_slug}"
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "P3: Theory requires re-evaluation" in body
    assert "P4: Empirical evidence requires re-evaluation" in body
    assert "Phase 3: Theory requires re-evaluation" in body
    theory_reason = (
        "The Phase 3 theory record was produced for an earlier Phase 2 "
        "method definition."
    )
    empirical_reason = (
        "The evidence index contains 1 outdated and 0 unresolved entries."
    )
    assert body.count(theory_reason) == 2
    assert body.count(empirical_reason) == 2
    # Reasons now live in the detail panel and rail tooltips; the compact
    # status rail replaced the verbose per-option status spans.
    assert body.count('class="record-status-reason"') >= 2
    assert 'class="status-rail"' in body
    assert f'data-knowledge-heads-version="{"h" * 64}"' in body
    assert f'data-phase-two-review-version="{"d" * 64}"' in body
    assert 'name="phase_two_review_version" value=""' in body
    assert 'name="knowledge_heads_version" value=""' in body
    assert "branch_graph_version" not in body
    assert "generation 3" not in body
    assert "Aligned" in body
    assert "Review needed" in body
    assert "Cannot verify" in body
    assert "Alignment does not assess scientific correctness or evidential strength" in body
    assert "JavaScript is required to verify current method records" in body
    assert "Later project changes cannot silently alter an active run" in body
    assert 'data-has-theory-history="true"' in body


def test_method_context_derivation_failure_is_visibly_unavailable(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    theory_slug = "03-idea-evaluation"
    web_env["config"]["phases"].append(_theory_phase_config())
    _write_menu_file(
        web_env["project_dir"],
        "recorded-method",
        "recommended",
        number=1,
    )
    monkeypatch.setattr(
        web_phase_data.web_branch_status,
        "method_record_statuses",
        lambda *_args: [{
            "has_theory_history": False,
            "knowledge_heads_version": None,
            "branch_graph_version": "b" * 64,
            "launch_context_error": (
                "The current Phase 3 and Phase 4 records cannot be verified for "
                "a new run."
            ),
            "record_status": {
                "theory": {"state": "not_run", "label": "Theory not run"},
                "empirical": {
                    "state": "not_run",
                    "label": "Empirical work not run",
                },
                "manuscript": {
                    "state": "not_run",
                    "label": "No manuscript draft",
                },
            },
        }],
    )
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    monkeypatch.setattr(webapp, "theory_audit_source_options", lambda _project: [])

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={theory_slug}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Unavailable for a new run." in body
    assert "The current Phase 3 and Phase 4 records cannot be verified" in body
    assert 'name="method_branch" value="recorded-method"' not in body

def test_method_menu_branch_selection_drives_run_specific_identity(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    theory_slug = "03-idea-evaluation"
    web_env["config"]["phases"].append(_theory_phase_config())
    _write_menu_file(
        web_env["project_dir"],
        "spectral-graph-coupling",
        "recommended",
        body=(
            "## Statistical target\nEstimate $\\theta$ under a sparse graph model.\n\n"
            "## Mathematical definition\nUse $\\hat{\\theta}=A^{-1}b$."
        ),
    )
    _write_menu_file(web_env["project_dir"], "old-idea", "retired")
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    monkeypatch.setattr(webapp, "theory_audit_source_options", lambda _project: [])

    client = web_env["client"]
    response = client.get(f"/project/{PROJECT_ID}?tab={theory_slug}")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "launch-form-lower" in body
    assert 'name="method_branch"' in body
    assert 'type="radio"' in body
    assert 'name="method_menu_version"' in body
    assert 'name="theory_context_policy" value="current_only"' in body
    assert 'value="include_archived_summaries"' in body
    assert 'data-has-theory-history="false"' in body
    assert "Phase 2 method catalog" in body
    assert "Spectral Graph Coupling" in body
    assert "Mathematical definition" in body
    assert "A^{-1}b" in body
    assert "data-mathjax-required" in body
    assert 'value="old-idea"' not in body
    assert 'name="method_branch" value="spectral-graph-coupling" checked' not in body
    assert "btn-retire-method" not in body

    launched = Mock(return_value={"run_number": 1, "rounds_requested": 1})
    monkeypatch.setattr(webapp, "launch_run", launched)
    token = _csrf(client)
    identity = _project_identity(web_env)

    accepted = client.post(
        f"/project/{PROJECT_ID}/phase/{theory_slug}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, theory_slug),
            "method_branch": "spectral-graph-coupling",
            "feedback": "Evaluate this branch.",
        },
    )
    assert accepted.status_code == 302
    launched.assert_called_once()
    assert (
        launched.call_args.kwargs["run_specific_method_id"]
        == "spectral-graph-coupling"
    )
    assert launched.call_args.kwargs["run_specific_method_version"] == "v1"
    assert (
        launched.call_args.kwargs["theory_context_policy"] == "current_only"
    )
    assert len(launched.call_args.kwargs["run_specific_method_sha256"]) == 64
    assert (
        launched.call_args.kwargs["expected_method_menu_version"]
        == webapp.method_menu.catalog_version(web_env["project_dir"])
    )
    assert (
        launched.call_args.kwargs["expected_knowledge_heads_version"] == "a" * 64
    )

    assert (
        launched.call_args.kwargs["expected_phase_two_review_version"] == "c" * 64
    )
    launched.reset_mock()
    missing_version_tokens = _launch_tokens(web_env, theory_slug)
    missing_version_tokens.pop("knowledge_heads_version")
    missing_version = client.post(
        f"/project/{PROJECT_ID}/phase/{theory_slug}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **missing_version_tokens,
            "method_branch": "spectral-graph-coupling",
        },
        follow_redirects=True,
    )
    assert missing_version.status_code == 200
    assert "selected method context cannot be verified" in (
        missing_version.get_data(as_text=True).lower()
    )
    launched.assert_not_called()


    launched.reset_mock()
    missing_review_tokens = _launch_tokens(web_env, theory_slug)
    missing_review_tokens.pop("phase_two_review_version")
    missing_review_version = client.post(
        f"/project/{PROJECT_ID}/phase/{theory_slug}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **missing_review_tokens,
            "method_branch": "spectral-graph-coupling",
        },
        follow_redirects=True,
    )
    assert missing_review_version.status_code == 200
    assert "phase 2 literature-review status cannot be verified" in (
        missing_review_version.get_data(as_text=True).lower()
    )
    launched.assert_not_called()
    launched.reset_mock()
    missing_choice = client.post(
        f"/project/{PROJECT_ID}/phase/{theory_slug}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, theory_slug),
        },
        follow_redirects=True,
    )
    assert missing_choice.status_code == 200
    assert "Choose an active method" in missing_choice.get_data(as_text=True)
    launched.assert_not_called()

    reviewed_tokens = _launch_tokens(web_env, theory_slug)
    _write_menu_file(
        web_env["project_dir"],
        "spectral-graph-coupling",
        "recommended",
        number=1,
        body="## Mathematical definition\nA changed definition with the same version.",
    )
    changed_catalog = client.post(
        f"/project/{PROJECT_ID}/phase/{theory_slug}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **reviewed_tokens,
            "method_branch": "spectral-graph-coupling",
        },
        follow_redirects=True,
    )
    assert changed_catalog.status_code == 200
    assert "catalog changed since this page was shown" in changed_catalog.get_data(
        as_text=True
    )
    launched.assert_not_called()

    for payload, fragment in [
        ({"method_branch": "old-idea"}, "retired"),
        ({"method_branch": "ghost-branch"}, "no method menu file"),
    ]:
        launched.reset_mock()
        rejected = client.post(
            f"/project/{PROJECT_ID}/phase/{theory_slug}/start",
            data={
                "csrf_token": token,
                "project_identity": identity,
                **_launch_tokens(web_env, theory_slug),
                **payload,
            },
            follow_redirects=True,
        )
        assert rejected.status_code == 200
        assert fragment in rejected.get_data(as_text=True)
        launched.assert_not_called()


def test_phase_three_disables_selection_when_catalog_cannot_be_fingerprinted(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    theory_slug = "03-idea-evaluation"
    web_env["config"]["phases"].append(_theory_phase_config())
    _write_menu_file(web_env["project_dir"], "active-method", "recommended")
    (web_env["project_dir"] / "ideas" / "methods" / "notes.txt").write_text(
        "unsupported catalog child",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    monkeypatch.setattr(webapp, "theory_audit_source_options", lambda _project: [])

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={theory_slug}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "The method catalog cannot be verified" in body
    assert 'data-method-selectable="true"' not in body
    assert 'name="method_menu_version" value=""' in body
    assert 'data-method-launch data-base-blocked="true"' in body


def test_quick_rerun_recovers_theory_plan_but_rejects_legacy_paper_review(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    project_dir = web_env["project_dir"].resolve()
    theory_slug = "03-idea-evaluation"
    paper_slug = "05-review-revision"
    web_env["config"]["phases"].extend(
        [
            {
                "slug": theory_slug,
                "name": "Theoretical Analysis",
                "description": "Develop the theory.",
                "pattern": "sequential",
                "rounds": {"min": 3, "default": 3, "max": 3},
                "gated_by": [],
                "folder": "draft/theory/",
                "members": ["theorist", "research_lead"],
                "available_run_plans": [
                    "standard",
                    "standard_with_audit",
                    "audit_only",
                ],
                "stages": [
                    {"role": "theorist"},
                    {"role": "research_lead"},
                    {"role": "theorist"},
                ],
            },
            {
                "slug": paper_slug,
                "name": "Paper Writing",
                "description": "Write and review the paper.",
                "pattern": "sequential",
                "method_binding": True,
                "rounds": {"min": 5, "default": 5, "max": 5},
                "gated_by": [],
                "folder": "draft/",
                "members": ["research_lead", "paper_reviewer"],
                "stages": [{"role": "research_lead"}] * 5,
            },
        ]
    )
    launched = Mock(return_value={"run_number": 2, "rounds_requested": 1})
    exact = Mock(
        side_effect=[
            {
                "kind": "theory",
                "theory_plan": "audit_only",
                "proof_audit_source_run_id": "sealed-source",
            },
            {
                "kind": "paper_review_only",
                "review_target": "draft/run/01/manuscript-post-review.md",
                "review_target_sha256": "a" * 64,
            },
        ]
    )
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(webapp, "exact_rerun_options", exact)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    _write_menu_file(project_dir, "paper-method", "recommended")
    monkeypatch.setattr(
        webapp,
        "phase_five_branch_readiness",
        _ready_phase_five_branch,
    )
    monkeypatch.setattr(
        web_phase_data,
        "phase_five_branch_readiness",
        _ready_phase_five_branch,
    )
    monkeypatch.setattr(
        webapp.project_state,
        "get_run",
        lambda *_args, **_kwargs: {"status": "approved"},
    )
    token = _csrf(client)
    identity = _project_identity(web_env)

    theory_response = client.post(
        f"/project/{PROJECT_ID}/phase/{theory_slug}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, theory_slug),
            "rerun_from": "prior-audit",
            "preserve_frozen_plan": "1",
            "feedback": "Check Lemma 2 under the stated moment condition.",
        },
    )
    assert theory_response.status_code == 302
    theory_call = launched.call_args
    assert theory_call.args[:5] == (
        project_dir,
        PROJECT_ID,
        theory_slug,
        "Check Lemma 2 under the stated moment condition.",
        1,
    )
    assert theory_call.kwargs["theory_plan"] == "audit_only"
    assert theory_call.kwargs["proof_audit_source_run_id"] == "sealed-source"

    launched.reset_mock()
    launched.return_value = {"run_number": 3, "rounds_requested": 2}
    paper_response = client.post(
        f"/project/{PROJECT_ID}/phase/{paper_slug}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, paper_slug),
            "rerun_from": "prior-review",
            "preserve_frozen_plan": "1",
            "method_branch": "paper-method",
        },
    )
    assert paper_response.status_code == 302
    launched.assert_not_called()
    assert exact.call_args_list[0].args == (project_dir, theory_slug, "prior-audit")
    assert exact.call_args_list[1].args == (project_dir, paper_slug, "prior-review")


def test_phase_six_history_exposes_only_bounded_manifest_owned_review_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    output_root = project / "draft" / "run" / "01"
    target = output_root / "manuscript-post-review.md"
    target.parent.mkdir(parents=True)
    target.write_text("post-review manuscript", encoding="utf-8")
    manifest = {
        "phase_slug": "05-review-revision",
        "run_id": "paper-run",
        "output_root": str(output_root),
        "paper_review": {"kind": "full"},
        "phase": {
            "slug": "05-review-revision",
            "pattern": "sequential",
            "folder": "draft/",
            "members": ["research_lead", "paper_reviewer"],
            "stages": [
                {"role": "research_lead", "name": "Draft"},
                {"role": "paper_reviewer", "name": "Read"},
                {"role": "paper_reviewer", "name": "Assess"},
            ]
        },
    }
    manifest_path = tmp_path / "paper-run.manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    run = {
        "run_id": "paper-run",
        "status": "approved",
        "submitted_at": "2026-07-20T00:00:00Z",
        "final_summary": "phase-summaries/05-review-revision/paper-run.html",
        "decision_record": {"data": {"proposed_baseline": "Complete baseline"}},
        "rounds_requested": 3,
        "rounds": [],
        "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "submission_artifacts": {
            "post_review_manuscript": {
                "path": target.relative_to(project).as_posix(),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "size": len(target.read_bytes()),
            }
        },
    }

    selected = web_phase_data._phase_six_post_review_target(
        project, "05-review-revision", run, {"ok": True}
    )
    assert selected == {
        "path": "draft/run/01/manuscript-post-review.md",
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "source_status": "approved",
        "source_run_id": "paper-run",
        "source_baseline_status": "accepted",
    }
    monkeypatch.setattr(
        web_phase_data.project_state,
        "run_integrity_report",
        lambda *_args, **_kwargs: {"ok": True, "reason": ""},
    )
    view = web_phase_data._run_view(project, "05-review-revision", run, 1)
    assert view["stages_requested"] == 3
    assert len(view["plan_stages"]) == 3
    assert view["plan_variant"] == "Full manuscript writing and independent review"
    assert view["frozen_plan"] == {
        "available": True,
        "variant": "Full manuscript writing and independent review",
        "pattern": "sequential",
        "folder": "draft/",
        "members": ["research_lead", "paper_reviewer"],
        "stages": manifest["phase"]["stages"],
        "run_plan": None,
    }

    monkeypatch.setattr(web_phase_data, "MAX_REVIEW_TARGET_BYTES", 4)
    assert web_phase_data._phase_six_post_review_target(
        project, "05-review-revision", run, {"ok": True}
    ) is None


def test_derivative_runs_expose_the_complete_sealed_source_identity(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    baseline = {
        "schema_version": 2,
        "run_id": "source-run",
        "status_at_selection": "revision_requested",
        "source_baseline_status": "proposed",
    }
    digest = "a" * 64
    paper_manifest = {
        "paper_review": {
            "kind": "review_only",
            "run_id": "source-run",
            "source_path": "draft/run/01/manuscript-post-review.md",
            "source_sha256": digest,
            "review_sha256": digest,
            "source_baseline": baseline,
        }
    }
    paper = web_phase_data._source_descriptor(
        project, "05-review-revision", paper_manifest
    )
    assert paper == {
        "kind": "manuscript_review",
        "source_run_id": "source-run",
        "source_path": "draft/run/01/manuscript-post-review.md",
        "source_sha256": digest,
        "status_at_selection": "revision_requested",
        "source_baseline_status": "proposed",
        "source_round": None,
    }

    theory_manifest = {
        "proof_audit_source": {
            "run_id": "source-run",
            "target": {
                "source_path": "draft/theory/run/01/round-03/theorist.md",
                "sha256": digest,
                "source_round": 3,
            },
            "source_baseline": baseline,
        }
    }
    theory = web_phase_data._source_descriptor(
        project, "03-idea-evaluation", theory_manifest
    )
    assert theory is not None
    assert theory["source_round"] == 3
    assert theory["source_run_id"] == "source-run"
    assert theory["source_sha256"] == digest


def test_legacy_derivative_runs_keep_their_sealed_source_identity(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    digest = "b" * 64

    paper = web_phase_data._source_descriptor(
        project,
        "05-review-revision",
        {
            "paper_review": {
                "schema_version": 1,
                "kind": "review_only",
                "source_path": "draft/run/01/manuscript-post-review.md",
                "source_sha256": digest,
                "review_sha256": digest,
            }
        },
    )
    assert paper is not None
    assert paper["source_run_id"] == "not recorded in legacy manifest"
    assert paper["source_sha256"] == digest
    assert paper["source_baseline_status"] == "not recorded in legacy manifest"

    theory = web_phase_data._source_descriptor(
        project,
        "03-idea-evaluation",
        {
            "proof_audit_source": {
                "schema_version": 1,
                "run_id": "legacy-theory-run",
                "target": {
                    "source_path": "draft/theory/run/01/round-03/theorist.md",
                    "sha256": digest,
                    "source_round": 3,
                },
            }
        },
    )
    assert theory is not None
    assert theory["source_run_id"] == "legacy-theory-run"
    assert theory["source_round"] == 3


def test_run_view_exposes_scientific_outcome_separately_from_technical_status(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    run = {
        "run_id": "decision-run",
        "status": "awaiting_review",
        "rounds_requested": 1,
        "rounds": [],
        "decision_record": {
            "sha256": "a" * 64,
            "data": {
                "scientific_outcome": "Failed",
                "recommended_user_action": "rerun",
                "recommendation": "Retain the diagnostic evidence and rerun the failed comparison.",
            },
        },
    }

    view = web_phase_data._run_view(project, DISCOVERY, run, 1)

    assert view["status"] == "awaiting_review"
    assert view["scientific_outcome"] == "Failed"
    assert view["recommended_user_action_label"] == "Rerun"
    assert view["decision_record_version"] == "a" * 64


def test_failed_run_with_summary_remains_technically_failed(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    summary = project / "phase-summaries" / DISCOVERY / "failed-summary.html"
    summary.parent.mkdir(parents=True)
    summary.write_text("<p>Inspectable lead summary</p>", encoding="utf-8")
    run = {
        "run_id": "failed-summary",
        "status": "failed",
        "rounds_requested": 1,
        "rounds": [],
    }

    view = web_phase_data._run_view(project, DISCOVERY, run, 1)

    assert view is not None
    assert view["summary_available"] is True
    assert str(view["summary_path"]).replace("\\", "/") == (
        "phase-summaries/01-discovery/failed-summary.html"
    )
    assert view["display_status"] == "failed"
    assert view["status_label"] == "Failed"
    assert web_phase_data._decision_state(
        {"current_run": None, "stale": False}, view
    ) == "failed"

def test_completed_unpromoted_run_is_not_labeled_as_current(
    web_env: dict,
) -> None:
    phase = {
        "slug": "03-idea-evaluation",
        "name": "Theoretical Analysis",
        "description": "Develop the current theory package.",
        "pattern": "sequential",
        "rounds": {"min": 1, "default": 1, "max": 1},
        "gated_by": [],
        "folder": "draft/theory/",
        "members": [],
        "stages": [],
    }
    run = {
        "run_id": "partial-run",
        "status": "completed",
        "rounds_requested": 1,
        "rounds": [],
        "phase_record": {"current_updated": False},
        "decision_record": {
            "sha256": "p" * 64,
            "data": {"scientific_outcome": "Partial"},
        },
    }

    view = web_phase_data._run_view(
        web_env["project_dir"], phase["slug"], run, 1
    )

    assert view is not None
    assert view["current_updated"] is False
    assert web_phase_data._decision_label(
        {"stale": False}, view
    ) == "Run complete; current result unchanged"

    phase_data = {
        "phase_cfg": phase,
        "state": {"status": "completed"},
        "run_history": [
            view,
            {
                **view,
                "id": "older-complete",
                "run_id": "older-complete",
                "number": 0,
                "scientific_outcome": "Complete",
            },
        ],
        "latest_run": view,
        "approved_run": None,
        "run_active": False,
        "active_elsewhere": False,
        "can_start": False,
        "prerequisite_report": _ready_prerequisites(),
        "rounds_policy": phase["rounds"],
        "stages": phase["stages"],
        "plan_view": {},
        "decision_state": "completed",
        "recovery_only": False,
        "method_menu": {"entries": [], "warnings": []},
        "method_details": [],
        "method_ranking_table": [],
        "catalog_method_selection": False,
    }
    with webapp.app.test_request_context("/"):
        rendered = webapp.render_template(
            "_tab_phase.html",
            phase_data=phase_data,
            project=web_env["project"],
            project_identity="sealed-project-identity",
            run_permissions={"unattended_tools": True},
        )

    assert "Run complete; current result unchanged" in rendered
    assert ">Current result</span>" not in rendered
    assert rendered.count("Scientific outcome: Partial") == 2


def test_phase_tab_separates_scientific_outcomes_and_latest_attempt(
    web_env: dict,
) -> None:
    phase = {
        "slug": DISCOVERY,
        "name": "Discovery",
        "description": "Establish the research basis.",
        "pattern": "parallel",
        "rounds": {"min": 1, "default": 1, "max": 1},
        "gated_by": [],
        "folder": "discovery/",
        "members": [],
        "stages": [],
    }
    current = {
        "id": "current-run",
        "run_id": "current-run",
        "number": 2,
        "status": "completed",
        "status_label": "Completed",
        "scientific_outcome": "Complete",
        "summary_available": False,
        "log_available": False,
    }
    latest_attempt = {
        "id": "failed-rerun",
        "run_id": "failed-rerun",
        "number": 3,
        "status": "failed",
        "status_label": "Failed",
        "scientific_outcome": "Failed",
        "summary_available": False,
        "log_available": False,
    }
    partial = {
        "id": "partial-run",
        "run_id": "partial-run",
        "number": 1,
        "status": "completed",
        "scientific_outcome": "Partial",
        "summary_available": False,
        "log_available": False,
    }
    phase_data = {
        "phase_cfg": phase,
        "state": {"status": "completed"},
        "run_history": [latest_attempt, current, partial],
        "latest_attempt": latest_attempt,
        "latest_run": current,
        "current_run": current,
        "run_active": False,
        "active_elsewhere": False,
        "can_start": False,
        "prerequisite_report": _ready_prerequisites(),
        "rounds_policy": phase["rounds"],
        "stages": phase["stages"],
        "plan_view": {},
        "decision_state": "completed",
        "recovery_only": False,
        "method_menu": {"entries": [], "warnings": []},
        "method_details": [],
        "method_ranking_table": [],
        "catalog_method_selection": False,
    }

    with webapp.app.test_request_context("/"):
        rendered = webapp.render_template(
            "_tab_phase.html",
            phase_data=phase_data,
            project=web_env["project"],
            project_identity="sealed-project-identity",
            run_permissions={"unattended_tools": True},
        )

    assert "Current record:" in rendered
    assert "Run 2" in rendered
    assert "Latest attempt:" in rendered
    assert "Run 3" in rendered
    assert "run-outcome-complete" in rendered
    assert "Scientific outcome: Partial" in rendered
    assert "run-outcome-failed" in rendered


def test_phase_four_run_view_distinguishes_pending_and_sealed_protocols(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    run = {
        "run_id": "numerical-run",
        "status": "running",
        "rounds_requested": 4,
        "rounds": [],
    }
    manifest = {
        "phase_slug": "04-draft-assembly",
        "phase": {
            "slug": "04-draft-assembly",
            "pattern": "sequential",
            "members": ["data_scientist"],
            "stages": [],
        },
        "protocol_checkpoint": {
            "schema_version": 1,
            "path": str(project / "numerical" / "protocol-checkpoint.json"),
            "max_bytes": 256 * 1024,
        },
    }
    monkeypatch.setattr(
        web_phase_data,
        "_sealed_run_manifest",
        lambda *_args: manifest,
    )

    pending = web_phase_data._run_view(
        project, "04-draft-assembly", run, 1
    )
    assert pending["protocol_checkpoint_required"] is True
    assert pending["protocol_checkpoint"] is None

    run["protocol_checkpoint"] = {
        "sealed_at": "2026-07-20T00:00:00Z",
        "data": {"protocol_files": [{"path": "protocol.yaml"}]},
    }
    sealed = web_phase_data._run_view(
        project, "04-draft-assembly", run, 1
    )
    assert sealed["protocol_checkpoint_required"] is True
    assert sealed["protocol_checkpoint"]["data"]["protocol_files"] == [
        {"path": "protocol.yaml"}
    ]


def test_protocol_checkpoint_disclosure_renders_exact_sealed_record() -> None:
    checkpoint_digest = "a" * 64
    protocol_digest = "b" * 64
    checkpoint = {
        "path": "numerical/run-01/protocol-checkpoint.json",
        "sha256": checkpoint_digest,
        "sealed_at": "2026-07-20T00:00:00Z",
        "data": {
            "protocol_files": [
                {
                    "path": "numerical/run-01/protocol.yaml",
                    "sha256": protocol_digest,
                    "size": 1234,
                    "purpose": "Fix the primary estimand and simulation grid.",
                }
            ]
        },
    }

    with webapp.app.test_request_context("/"):
        rendered = webapp.render_template(
            "_protocol_checkpoint.html", protocol_checkpoint=checkpoint
        )

    assert "Inspect sealed protocol checkpoint" in rendered
    assert checkpoint["path"] in rendered
    assert checkpoint_digest in rendered
    assert checkpoint["data"]["protocol_files"][0]["path"] in rendered
    assert protocol_digest in rendered
    assert "Fix the primary estimand and simulation grid." in rendered


@pytest.mark.parametrize(
    ("checkpoint", "expected_state", "expected_text"),
    [
        (None, "pending", "Phase 4 protocol checkpoint pending"),
        (
            {
                "path": "numerical/run-01/protocol-checkpoint.json",
                "sha256": "c" * 64,
                "sealed_at": "2026-07-20T00:00:00Z",
                "data": {
                    "protocol_files": [
                        {
                            "path": "numerical/run-01/protocol.yaml",
                            "sha256": "d" * 64,
                            "size": 32,
                            "purpose": "Fix the primary analysis.",
                        }
                    ]
                },
            },
            "sealed",
            "Phase 4 protocol checkpoint sealed",
        ),
    ],
)
def test_run_progress_renders_checkpoint_accessible_state_and_focus_key(
    web_env: dict,
    checkpoint: dict | None,
    expected_state: str,
    expected_text: str,
) -> None:
    current = {
        "id": "numerical-run",
        "number": 1,
        "status": "running",
        "rounds_requested": 4,
        "rounds_completed": 1,
        "rounds": [],
        "protocol_checkpoint_required": True,
        "protocol_checkpoint": checkpoint,
        "frozen_plan": {"run_plan": "preliminary"},
    }
    phase_data = {
        "latest_run": current,
        "phase_cfg": {
            "slug": "04-draft-assembly",
            "pattern": "parallel",
        },
        "run_active": True,
        "approval_context_report": {},
    }

    with webapp.app.test_request_context("/"):
        rendered = webapp.render_template(
            "_run_progress.html",
            phase_data=phase_data,
            project=web_env["project"],
            project_identity="sealed-project-identity",
        )

    assert f"|{expected_state}|" in rendered
    assert expected_text in rendered
    assert 'data-progress-announcement' in rendered
    assert 'data-progress-focus="live-log"' in rendered
    assert "project_identity=sealed-project-identity" in rendered
    if checkpoint:
        assert checkpoint["sha256"] in rendered
        assert checkpoint["data"]["protocol_files"][0]["path"] in rendered


def test_project_history_chips_are_not_presented_as_selected_run_context(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archived_phase = {
        "slug": "03-analysis",
        "name": "Analysis",
        "description": "Analyze the result.",
        "pattern": "parallel",
        "rounds": {"min": 1, "default": 1, "max": 1},
        "gated_by": [],
        "folder": "analysis/",
        "members": ["analyst"],
    }
    phases = [web_env["phases"][0], web_env["phases"][1], archived_phase]
    state_data = {
        "phases": {
            DISCOVERY: {
                "approved_run": None,
                "latest_run": "discovery-result",
                "runs": [{
                    "run_id": "discovery-result",
                    "run_number": 2,
                    "status": "awaiting_review",
                }],
            },
            VALIDATION: {"runs": []},
            archived_phase["slug"]: {"runs": []},
        }
    }
    monkeypatch.setattr(
        web_phase_data.project_state,
        "load",
        lambda _project: state_data,
    )
    chips = web_phase_data._cross_phase_context(
        web_env["project_dir"],
        VALIDATION,
        phases,
    )
    discovery_chip = next(chip for chip in chips if chip["slug"] == DISCOVERY)
    assert discovery_chip["status"] == "awaiting_review"
    assert discovery_chip["run_number"] == "2"

    phase = web_env["phases"][1]
    phase_data = {
        "phase_cfg": phase,
        "state": {"status": "pending"},
        "run_history": [],
        "latest_run": None,
        "approved_run": None,
        "run_active": False,
        "active_elsewhere": False,
        "can_start": False,
        "prerequisite_report": _ready_prerequisites(),
        "rounds_policy": phase["rounds"],
        "stages": phase["stages"],
        "plan_view": {},
        "decision_state": "pending",
        "recovery_only": False,
        "cross_phase_context": chips,
    }
    monkeypatch.setattr(webapp, "_phase_catalog", lambda *_args: phases)
    monkeypatch.setattr(webapp, "prepare_overview_data", lambda *_args: [])
    monkeypatch.setattr(webapp, "prepare_phase_data", lambda *_args: phase_data)

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={VALIDATION}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<span class="context-chips-label">Project history:</span>' in body
    assert "awaiting review" in body
    assert "not run" in body
    assert "These chips show project-wide history, not the inputs for this run" in body
    assert '<span class="context-chips-label">Context:</span>' not in body

def test_run_history_is_focusable_and_progressively_discloses_older_runs(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase = web_env["phases"][1]
    runs = [
        {
            "id": f"history-run-{index}",
            "run_id": f"history-run-{index}",
            "number": index,
            "status": "cancelled",
            "rounds_requested": 2,
            "rounds_completed": 1,
            "frozen_plan": {"available": False, "pattern": "sequential"},
            "summary_available": False,
            "log_available": False,
            "integrity_error": False,
        }
        for index in range(12, 0, -1)
    ]
    phase_data = {
        "phase_cfg": phase,
        "state": {"status": "cancelled"},
        "run_history": runs,
        "latest_run": runs[0],
        "approved_run": None,
        "run_active": False,
        "active_elsewhere": False,
        "can_start": False,
        "prerequisite_report": _ready_prerequisites(),
        "rounds_policy": phase["rounds"],
        "stages": phase["stages"],
        "plan_view": {},
        "decision_state": "cancelled",
        "recovery_only": True,
        "recovery_source": "test record",
    }
    monkeypatch.setattr(webapp, "_phase_catalog", lambda *_args: web_env["phases"])
    monkeypatch.setattr(webapp, "prepare_overview_data", lambda *_args: [])
    monkeypatch.setattr(webapp, "prepare_phase_data", lambda *_args: phase_data)

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={VALIDATION}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<details class="run-history">' in body
    assert "<summary>Run history</summary>" in body
    assert "Run 12: cancelled" in body
    assert "Run 1: cancelled" in body
    assert "run-selector-dropdown" not in body
    assert "run-switcher" not in body


def test_project_markdown_is_rendered_without_executable_html(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = web_env["project_dir"]
    (project_dir / "setting.md").write_text(
        "# Brief\n\n**Safe evidence**\n\n"
        "<script>owned_marker()</script>\n\n"
        "[unsafe link](javascript:alert(99))\n\n"
        "[source](https://example.test/paper)",
        encoding="utf-8",
    )

    def render_markdown(source: str, **_kwargs) -> str:
        # The renderer receives raw (unescaped) source.  The sanitizer alone
        # must defend against dangerous HTML emitted by a renderer extension.
        assert "<script>owned_marker()</script>" in source
        return (
            "<h1>Brief</h1><p><strong>Safe evidence</strong></p>"
            "<script>owned_marker()</script>"
            '<p><a href="javascript:alert(99)">unsafe link</a> '
            '<a href="https://example.test/paper">source</a></p>'
        )

    monkeypatch.setitem(
        sys.modules, "markdown", SimpleNamespace(markdown=render_markdown)
    )

    response = web_env["client"].get(f"/project/{PROJECT_ID}")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "<strong>Safe evidence</strong>" in body
    assert "<script>owned_marker()</script>" not in body
    assert "owned_marker()" in body
    assert 'href="javascript:alert(99)"' not in body
    assert 'href="https://example.test/paper"' in body
    assert 'rel="noopener noreferrer"' in body


def test_missing_prerequisites_require_explicit_override(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 2})
    report = {
        "policy": "current_records",
        "satisfied": False,
        "blockers": [DISCOVERY],
        "requirements": [
            {
                "phase": DISCOVERY,
                "satisfied": False,
                "reason": "no current result",
            }
        ],
    }
    prerequisite_report = Mock(return_value=report)
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", prerequisite_report
    )
    token = _csrf(client)
    identity = _project_identity(web_env)

    blocked = client.post(
        f"/project/{PROJECT_ID}/phase/{VALIDATION}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, VALIDATION, report),
            "feedback": "Exploratory check",
        },
        follow_redirects=True,
    )
    assert blocked.status_code == 200
    blocked_body = blocked.get_data(as_text=True)
    assert "Scientific context is incomplete" in blocked_body
    assert (
        "Some expected prior phase results are unavailable, outdated, or not intact"
        in blocked_body
    )
    assert "continue without every expected current result" in blocked_body
    launched.assert_not_called()

    allowed = client.post(
        f"/project/{PROJECT_ID}/phase/{VALIDATION}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, VALIDATION, report),
            "feedback": "Exploratory check",
            "override_prerequisites": "1",
            "prerequisite_report_version": webapp.decision_report_version(
                "prerequisite", report
            ),
        },
    )
    assert allowed.status_code == 302
    call = launched.call_args
    assert call.args[:5] == (
        web_env["project_dir"].resolve(),
        PROJECT_ID,
        VALIDATION,
        "Exploratory check",
        2,
    )
    assert DISCOVERY in call.kwargs["prerequisite_override_reason"]
    assert call.kwargs["prerequisite_report_version"] == (
        webapp.decision_report_version("prerequisite", report)
    )
    assert prerequisite_report.call_count >= 2
    assert all(
        report_call.kwargs == {"current_records": True}
        for report_call in prerequisite_report.call_args_list
    )


def test_decision_rerun_and_cancel_routes_delegate_to_lifecycle(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    project_dir = web_env["project_dir"].resolve()
    token = _csrf(client)
    identity = _project_identity(web_env)
    approved = Mock(return_value=[VALIDATION])
    revision = Mock()
    cancelled = Mock()
    launched = Mock(return_value={"run_number": 4, "rounds_requested": 3})
    decision_digest = "d" * 64
    monkeypatch.setattr(webapp.project_state, "approve_run", approved)
    monkeypatch.setattr(webapp.project_state, "request_revision", revision)
    monkeypatch.setattr(webapp, "cancel_active_run", cancelled)
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    monkeypatch.setattr(
        webapp.project_state,
        "approval_context_report",
        lambda *_args, **_kwargs: {
            "requires_acknowledgement": False,
            "changed_sources": [],
        },
    )
    monkeypatch.setattr(
        webapp.project_state,
        "get_run",
        lambda *_args, **_kwargs: {
            "run_id": "run-review",
            "status": "awaiting_review",
            "decision_record": {
                "sha256": decision_digest,
                "data": {"scientific_outcome": "Partial"},
            },
        },
    )

    approve_response = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/run-review/approve",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "accept_proposed_baseline": "1",
            "decision_record_version": decision_digest,
            "approval_kind": "approve_with_limitations",
        },
    )
    assert approve_response.status_code == 302
    approved.assert_called_once_with(
        project_dir,
        DISCOVERY,
        "run-review",
        approval_kind="approve_with_limitations",
        dependencies={DISCOVERY: [], VALIDATION: [DISCOVERY]},
        reviewer="user",
        note="",
        baseline_acknowledgement=(
            "The user reviewed the sealed summary and structured decision record "
            "and accepted the proposed scientific baseline as a whole, choosing to "
            "approve with limitations."
        ),
        expected_decision_record_version=decision_digest,
        context_acknowledgement="",
        expected_context_report_version=None,
    )

    revision_response = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/run-review/revision",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "feedback": "Add the missing comparison.",
        },
    )
    assert revision_response.status_code == 302
    revision.assert_called_once_with(
        project_dir,
        DISCOVERY,
        "run-review",
        "Add the missing comparison.",
        reviewer="user",
    )

    blocked_rerun = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, DISCOVERY),
            "rounds": "3",
            "feedback": "Focus the rerun.",
            "rerun_from": "run-review",
        },
        follow_redirects=True,
    )
    assert "Explicitly confirm" in blocked_rerun.get_data(as_text=True)
    launched.assert_not_called()

    rerun_response = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, DISCOVERY),
            "rounds": "3",
            "feedback": "Focus the rerun.",
            "rerun_from": "run-review",
            "replace_awaiting_review": "1",
        },
    )
    assert rerun_response.status_code == 302
    rerun_call = launched.call_args
    assert rerun_call.args[:5] == (
        project_dir,
        PROJECT_ID,
        DISCOVERY,
        "Focus the rerun.",
        3,
    )
    assert "explicitly chose" in rerun_call.kwargs["replace_awaiting_review_note"]
    assert rerun_call.kwargs["replace_awaiting_review_run_id"] == "run-review"

    cancel_response = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/run-live/cancel",
        data={"csrf_token": token, "project_identity": identity},
    )
    assert cancel_response.status_code == 302
    cancelled.assert_called_once_with(project_dir, DISCOVERY, "run-live")


def test_failed_replacement_keeps_prior_result_as_the_decision_subject(
    web_env: dict,
) -> None:
    project_dir = web_env["project_dir"]
    dependencies = {DISCOVERY: [], VALIDATION: [DISCOVERY]}
    webapp.project_state.init(
        project_dir,
        "project-001",
        "test",
        "Test",
        phase_slugs=[DISCOVERY, VALIDATION],
        dependencies=dependencies,
    )
    prior = webapp.project_state.reserve_run(project_dir, DISCOVERY, "first")
    webapp.project_state.set_process_pid(project_dir, DISCOVERY, prior, 14001)
    webapp.project_state.start_round(project_dir, DISCOVERY, prior, "work", ["lead"])
    artifact = project_dir / "prior.md"
    artifact.write_text("evidence", encoding="utf-8")
    webapp.project_state.complete_round(project_dir, DISCOVERY, prior, 1, [artifact])
    summary = project_dir / "prior-summary.md"
    summary.write_text("# Prior result\n", encoding="utf-8")
    webapp.project_state.submit_run_for_review(project_dir, DISCOVERY, prior, summary)
    replacement = webapp.project_state.reserve_run(
        project_dir,
        DISCOVERY,
        "replacement",
        replace_awaiting_review_note="Try a narrower question.",
        replace_awaiting_review_run_id=prior,
    )
    webapp.project_state.fail_run_if_active(
        project_dir, DISCOVERY, replacement, "startup failed"
    )

    data = web_phase_data.prepare_phase_data(
        project_dir,
        PROJECT_ID,
        web_env["phases"][0],
        web_env["phases"],
    )
    assert data["latest_run"]["run_id"] == prior
    assert data["latest_run"]["status"] == "awaiting_review"
    assert data["latest_attempt"]["run_id"] == replacement
    assert data["latest_attempt"]["status"] == "failed"


def test_client_controls_preserve_dirty_forms_and_mobile_focus_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "static" / "app.js").read_text(encoding="utf-8")
    phase_template = (root / "templates" / "_tab_phase.html").read_text(
        encoding="utf-8"
    )

    assert "hasDirtyFormWithin(target)" in script
    assert "plainCurrentWindowNavigation" in script
    assert "window.history.go(delta)" in script
    assert 'sidebar.setAttribute("aria-hidden", "true")' in script
    assert "restoreDraftsAfterError()" in script
    assert "form.dataset.draftKey" in script
    assert 'control.type !== "hidden"' in script
    assert "control.value === item.value" in script
    assert "new AbortController()" in script
    assert "requestToken !== projectRequestToken" in script
    assert "guardedFormsChanged(target, formSnapshot)" in script
    assert "focusChangedWithinTarget" in script
    assert "mutableProgressControl(target)" in script
    assert "restoreProgressDetails(replacement, openDetails)" in script
    assert "restoreProgressFocus(replacement, focusKey)" in script
    assert "nextStatusSignature !== priorStatusSignature" in script
    assert "}, 3000);" in script
    # Simplified UI: launch form with unsaved guard
    assert 'class="launch-form-lower"' in phase_template and 'data-unsaved-guard' in phase_template
    assert 'name="rounds"' in phase_template
    run_progress_template = (root / "templates" / "_run_progress.html").read_text(
        encoding="utf-8"
    )
    assert "Protocol checkpoint pending" in run_progress_template
    assert "Research Hub then verifies and seals" in run_progress_template
    assert "data analyst must seal" not in run_progress_template
    assert "data-progress-status-signature" in run_progress_template
    assert "data-progress-announcement" in run_progress_template
    assert 'data-progress-focus="live-log"' in run_progress_template
    assert "_protocol_checkpoint.html" in run_progress_template
    assert 'class="run-history"' in phase_template
    assert "<summary>Run history</summary>" in phase_template
    assert "run-selector-dropdown" not in phase_template
    for template_name in (
        "_tab_phase.html",
        "_tab_overview.html",
        "_run_progress.html",
    ):
        template = (root / "templates" / template_name).read_text(encoding="utf-8")
        assert template.count('name="csrf_token"') > 0
        assert template.count('name="project_identity"') == template.count(
            'name="csrf_token"'
        )
    project_template = (root / "templates" / "project.html").read_text(
        encoding="utf-8"
    )
    assert 'data-project-identity="{{ project_identity }}"' in project_template
    for template_name in (
        "_tab_phase.html",
        "_tab_overview.html",
        "_run_progress.html",
        "hub_settings.html",
        "new_project.html",
    ):
        template = (root / "templates" / template_name).read_text(encoding="utf-8")
        assert template.count("data-draft-key=") == template.count(
            "data-unsaved-guard"
        )


def test_cleanup_recovery_routes_require_an_explicit_verification(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    project_dir = web_env["project_dir"].resolve()
    token = _csrf(client)
    identity = _project_identity(web_env)
    retried = Mock(return_value={"status": "cancelled"})
    recovered = Mock(return_value=True)
    monkeypatch.setattr(webapp, "retry_run_cleanup", retried)
    monkeypatch.setattr(webapp.project_state, "recover_run_cleanup", recovered)

    retry_response = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/run-stopping/retry-cleanup",
        data={"csrf_token": token, "project_identity": identity},
    )
    assert retry_response.status_code == 302
    retried.assert_called_once_with(project_dir, DISCOVERY, "run-stopping")

    missing_confirmation = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/run-stopping/recover-cleanup",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "recovery_note": "Inspected the worker and board.",
        },
    )
    assert missing_confirmation.status_code == 302
    recovered.assert_not_called()

    confirmed = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/run-stopping/recover-cleanup",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "recovery_note": "Inspected the process table and Hermes board; no task remains active.",
            "confirm_external_stopped": "1",
        },
    )
    assert confirmed.status_code == 302
    recovered.assert_called_once_with(
        project_dir,
        DISCOVERY,
        "run-stopping",
        "Inspected the process table and Hermes board; no task remains active.",
    )


def test_stopping_run_explains_the_lock_and_recovery_choices(web_env: dict) -> None:
    project_dir = web_env["project_dir"]
    dependencies = {DISCOVERY: [], VALIDATION: [DISCOVERY]}
    webapp.project_state.init(
        project_dir,
        "project-001",
        "test",
        "Test Project",
        phase_slugs=[DISCOVERY, VALIDATION],
        dependencies=dependencies,
    )
    run_id = webapp.project_state.reserve_run(
        project_dir, DISCOVERY, "cleanup test", dependencies=dependencies
    )
    webapp.project_state.set_process_pid(
        project_dir,
        DISCOVERY,
        run_id,
        12003,
        process_identity="cleanup-test-worker",
    )
    webapp.project_state.begin_run_cleanup(
        project_dir,
        DISCOVERY,
        run_id,
        "cancelled",
        "User requested cancellation.",
        expected_pid=12003,
    )

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={DISCOVERY}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "cleanup is pending" in body
    assert "The project launch lock is still held" in body
    assert "User requested cancellation" in body
    assert f'/run/{run_id}/retry-cleanup"' in body
    assert f'/run/{run_id}/recover-cleanup"' in body
    assert 'name="confirm_external_stopped"' in body
    assert "Release after manual verification" in body
    assert "Cancel run" not in body

    note = "Checked the process table and Hermes board; all work has stopped."
    assert webapp.project_state.recover_run_cleanup(
        project_dir, DISCOVERY, run_id, note
    ) is True
    recovered_body = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={DISCOVERY}"
    ).get_data(as_text=True)
    # Simplified UI: recovery note is surfaced in a notice
    assert note in recovered_body


def test_prerequisite_override_rejects_a_report_changed_after_render(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    token = _csrf(client)
    identity = _project_identity(web_env)
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 2})
    shown_report = {
        "phase": VALIDATION,
        "satisfied": False,
        "blockers": [DISCOVERY],
        "requirements": [
            {
                "phase": DISCOVERY,
                "satisfied": False,
                "completed_run": None,
                "stale": False,
                "phase_status": "pending",
                "reason": "no current result",
            }
        ],
        "checked_at": "2026-07-20T00:00:00Z",
    }
    changed_report = copy.deepcopy(shown_report)
    changed_report["requirements"][0]["reason"] = (
        "current summary is missing or changed"
    )
    changed_report["checked_at"] = "2026-07-20T00:01:00Z"
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state,
        "prerequisite_report",
        lambda *_args, **_kwargs: changed_report,
    )

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{VALIDATION}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "phase_plan_version": webapp.launch_plan_version(
                web_env["config"], VALIDATION
            ),
            "override_prerequisites": "1",
            "prerequisite_report_version": webapp.decision_report_version(
                "prerequisite", shown_report
            ),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Prerequisite status changed since this page was shown" in response.get_data(
        as_text=True
    )
    launched.assert_not_called()


def test_structured_baseline_requires_explicit_version_bound_approval(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    token = _csrf(client)
    identity = _project_identity(web_env)
    digest = "b" * 64
    approved = Mock(return_value=[])
    monkeypatch.setattr(
        webapp.project_state,
        "get_run",
        lambda *_args, **_kwargs: {
            "run_id": "structured-run",
            "status": "awaiting_review",
            "decision_record": {"sha256": digest, "data": {"scientific_outcome": "Failed"}},
        },
    )
    monkeypatch.setattr(
        webapp.project_state,
        "approval_context_report",
        lambda *_args, **_kwargs: {
            "requires_acknowledgement": False,
            "changed_sources": [],
        },
    )
    monkeypatch.setattr(webapp.project_state, "approve_run", approved)

    blocked = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/structured-run/approve",
        data={"csrf_token": token, "project_identity": identity},
    )
    assert blocked.status_code == 302
    approved.assert_not_called()

    missing_kind = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/structured-run/approve",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "accept_proposed_baseline": "1",
            "decision_record_version": digest,
        },
        follow_redirects=True,
    )
    assert missing_kind.status_code == 200
    assert "Choose whether to approve or approve with limitations" in (
        missing_kind.get_data(as_text=True)
    )
    approved.assert_not_called()

    accepted = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/structured-run/approve",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "accept_proposed_baseline": "1",
            "decision_record_version": digest,
            "approval_kind": "approve",
            "approval_note": "Accept the qualified negative result.",
        },
    )
    assert accepted.status_code == 302
    call = approved.call_args
    assert call.kwargs["expected_decision_record_version"] == digest
    assert call.kwargs["approval_kind"] == "approve"
    assert "as a whole" in call.kwargs["baseline_acknowledgement"]
    assert call.kwargs["note"] == "Accept the qualified negative result."


def test_phase_two_has_no_approval_route(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    approved = Mock(return_value=[])
    monkeypatch.setattr(webapp.project_state, "approve_run", approved)
    client = web_env["client"]

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/run/phase-two-run/approve",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
        },
    )

    assert response.status_code == 409
    assert "publish the method menu automatically" in response.get_data(
        as_text=True
    )
    approved.assert_not_called()

def test_legacy_result_without_structured_baseline_cannot_be_approved(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    identity = _project_identity(web_env)
    approved = Mock(return_value=[])
    monkeypatch.setattr(
        webapp.project_state,
        "get_run",
        lambda *_args, **_kwargs: {
            "run_id": "legacy-run",
            "status": "awaiting_review",
        },
    )
    monkeypatch.setattr(webapp.project_state, "approve_run", approved)

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/legacy-run/approve",
        data={
            "csrf_token": _csrf(client),
            "project_identity": identity,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "legacy run has no structured scientific baseline" in response.get_data(
        as_text=True
    )
    approved.assert_not_called()


def test_approval_with_changed_context_requires_explicit_checkbox(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    token = _csrf(client)
    identity = _project_identity(web_env)
    digest = "c" * 64
    approved = Mock(return_value=[])
    report = {
        "requires_acknowledgement": True,
        "changed_sources": [
            {
                "phase": DISCOVERY,
                "launch_run": "source-one",
                "current_run": "source-two",
                "reason": "the approved prerequisite run changed after launch",
            }
        ],
    }
    monkeypatch.setattr(webapp.project_state, "approval_context_report", lambda *_a, **_k: report)
    monkeypatch.setattr(webapp.project_state, "approve_run", approved)
    monkeypatch.setattr(
        webapp.project_state,
        "get_run",
        lambda *_args, **_kwargs: {
            "run_id": "downstream",
            "status": "awaiting_review",
            "decision_record": {
                "sha256": digest,
                "data": {"scientific_outcome": "Complete"},
            },
        },
    )

    blocked = client.post(
        f"/project/{PROJECT_ID}/phase/{VALIDATION}/run/downstream/approve",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "accept_proposed_baseline": "1",
            "decision_record_version": digest,
            "approval_kind": "approve",
        },
    )
    assert blocked.status_code == 302
    approved.assert_not_called()

    accepted = client.post(
        f"/project/{PROJECT_ID}/phase/{VALIDATION}/run/downstream/approve",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "accept_proposed_baseline": "1",
            "decision_record_version": digest,
            "approval_kind": "approve_with_limitations",
            "acknowledge_context": "1",
            "approval_context_report_version": webapp.decision_report_version(
                "approval_context", report
            ),
        },
    )
    assert accepted.status_code == 302
    call = approved.call_args
    assert DISCOVERY in call.kwargs["context_acknowledgement"]
    assert call.kwargs["expected_context_report_version"] == (
        webapp.decision_report_version("approval_context", report)
    )


def test_approval_rejects_context_changed_after_render(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = web_env["client"]
    token = _csrf(client)
    identity = _project_identity(web_env)
    digest = "e" * 64
    approved = Mock(return_value=[])
    shown_report = {
        "requires_acknowledgement": True,
        "changed_sources": [
            {
                "phase": DISCOVERY,
                "launch_run": "source-one",
                "current_run": "source-two",
                "reason": "the approved prerequisite run changed after launch",
            }
        ],
        "launch_override": None,
        "reasons": ["the approved prerequisite run changed after launch"],
        "checked_at": "2026-07-20T00:00:00Z",
    }
    changed_report = copy.deepcopy(shown_report)
    changed_report["changed_sources"][0]["current_run"] = "source-three"
    changed_report["checked_at"] = "2026-07-20T00:01:00Z"
    monkeypatch.setattr(
        webapp.project_state,
        "approval_context_report",
        lambda *_args, **_kwargs: changed_report,
    )
    monkeypatch.setattr(webapp.project_state, "approve_run", approved)
    monkeypatch.setattr(
        webapp.project_state,
        "get_run",
        lambda *_args, **_kwargs: {
            "run_id": "downstream",
            "status": "awaiting_review",
            "decision_record": {
                "sha256": digest,
                "data": {"scientific_outcome": "Complete"},
            },
        },
    )

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{VALIDATION}/run/downstream/approve",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "accept_proposed_baseline": "1",
            "decision_record_version": digest,
            "approval_kind": "approve",
            "acknowledge_context": "1",
            "approval_context_report_version": webapp.decision_report_version(
                "approval_context", shown_report
            ),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Approval context changed since this page was shown" in response.get_data(
        as_text=True
    )
    approved.assert_not_called()


def test_legacy_multi_active_conflict_exposes_phase_cancellation(
    web_env: dict,
) -> None:
    project_dir = web_env["project_dir"]
    dependencies = {DISCOVERY: [], VALIDATION: [DISCOVERY]}
    webapp.project_state.init(
        project_dir,
        "project-001",
        "test",
        "Test Project",
        phase_slugs=[DISCOVERY, VALIDATION],
        dependencies=dependencies,
    )
    first_id = webapp.project_state.reserve_run(
        project_dir,
        DISCOVERY,
        "legacy",
        dependencies=dependencies,
    )
    raw_state = webapp.project_state.load(project_dir)
    first_run = webapp.project_state.get_run(project_dir, DISCOVERY, first_id)
    second_run = copy.deepcopy(first_run)
    second_run["run_id"] = "legacy-validation-run"
    second_run["mode"] = "legacy conflict"
    raw_state["phases"][VALIDATION]["runs"].append(second_run)
    webapp.project_state.state_file(project_dir).write_text(
        yaml.safe_dump(raw_state, sort_keys=False), encoding="utf-8"
    )

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={VALIDATION}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Multiple legacy runs are marked active" in body
    assert (
        f'action="/project/{PROJECT_ID}/phase/{VALIDATION}/run/'
        'legacy-validation-run/cancel"'
    ) in body
    assert "Cancel run" in body


def test_removed_phase_keeps_recovery_history_and_cancel_without_launch(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_dir = web_env["project_dir"]
    removed = "03-legacy-synthesis"
    dependencies = {DISCOVERY: [], VALIDATION: [DISCOVERY], removed: []}
    webapp.project_state.init(
        project_dir,
        "project-001",
        "test",
        "Test Project",
        phase_slugs=[DISCOVERY, VALIDATION, removed],
        dependencies=dependencies,
    )

    prior_id = webapp.project_state.reserve_run(
        project_dir, removed, "legacy baseline", dependencies=dependencies
    )
    webapp.project_state.set_process_pid(project_dir, removed, prior_id, 12001)
    webapp.project_state.start_round(
        project_dir, removed, prior_id, "Synthesize prior evidence", ["lead"], round_n=1
    )
    output = project_dir / "legacy" / "run" / "01" / "round-01" / "lead.md"
    output.parent.mkdir(parents=True)
    output.write_text("legacy evidence", encoding="utf-8")
    webapp.project_state.complete_round(project_dir, removed, prior_id, 1, [output])
    summary = project_dir / "phase-summaries" / removed / f"{prior_id}.html"
    summary.parent.mkdir(parents=True)
    summary.write_text("<h1>Legacy summary</h1>", encoding="utf-8")
    webapp.project_state.submit_run_for_review(project_dir, removed, prior_id, summary)
    webapp.project_state.approve_run(
        project_dir,
        removed,
        prior_id,
        approval_kind="approve",
        dependencies=dependencies,
    )

    active_id = webapp.project_state.reserve_run(
        project_dir, removed, "legacy rerun", dependencies=dependencies
    )
    manifest_path = (
        webapp.project_state.state_dir(project_dir)
        / "runs"
        / removed
        / f"{active_id}.manifest.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps({
            "run_id": active_id,
            "phase_slug": removed,
            "timeout_minutes": 30,
            "phase": {
                "slug": removed,
                "name": "Legacy Synthesis",
                "description": "Recover the plan that was actually launched.",
                "pattern": "sequential",
                "rounds": {"min": 1, "default": 1, "max": 1},
                "gated_by": [],
                "context_from": [],
                "folder": "legacy/",
                "members": ["lead"],
                "stages": [
                    {
                        "role": "lead",
                        "name": "Synthesis",
                        "description": "Consolidate the evidence.",
                    }
                ],
            },
        }),
        encoding="utf-8",
    )
    webapp.project_state.seal_run_manifest(
        project_dir, removed, active_id, manifest_path
    )
    webapp.project_state.set_process_pid(
        project_dir,
        removed,
        active_id,
        12002,
        process_identity="removed-phase-worker",
    )
    log_file = webapp.run_log_path(project_dir, removed, active_id)
    log_file.write_text("recovery log", encoding="utf-8")

    cancelled = Mock()
    launched = Mock()
    monkeypatch.setattr(webapp, "cancel_active_run", cancelled)
    monkeypatch.setattr(webapp, "launch_run", launched)
    client = web_env["client"]

    overview = client.get(f"/project/{PROJECT_ID}")
    phase = client.get(f"/project/{PROJECT_ID}?tab={removed}")
    body = phase.get_data(as_text=True)

    assert overview.status_code == 200
    assert "Legacy Synthesis" in overview.get_data(as_text=True)
    assert "(removed)" in overview.get_data(as_text=True)
    assert phase.status_code == 200
    assert "This phase is no longer in the current configuration" in body
    assert "Legacy Synthesis" in body
    assert f'/phase/{removed}/run/{active_id}/cancel"' in body
    assert f'/phase/{removed}/start"' not in body
    assert "Rerun this phase" not in body

    summary_response = client.get(
        f"/project/{PROJECT_ID}/phase/{removed}/run/{prior_id}/summary"
    )
    log_response = client.get(
        f"/project/{PROJECT_ID}/phase/{removed}/run/{active_id}/log"
    )
    assert summary_response.status_code == 200
    assert b"Legacy summary" in summary_response.data
    assert log_response.status_code == 200
    assert b"recovery log" in log_response.data

    token = _csrf(client)
    identity = _project_identity(web_env)
    start_response = client.post(
        f"/project/{PROJECT_ID}/phase/{removed}/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            "rounds": "1",
        },
    )
    cancel_response = client.post(
        f"/project/{PROJECT_ID}/phase/{removed}/run/{active_id}/cancel",
        data={"csrf_token": token, "project_identity": identity},
    )
    assert start_response.status_code == 404
    launched.assert_not_called()
    assert cancel_response.status_code == 302
    cancelled.assert_called_once_with(project_dir.resolve(), removed, active_id)


def test_tampered_approved_summary_is_not_presented_as_a_current_baseline(
    web_env: dict,
) -> None:
    project_dir = web_env["project_dir"]
    dependencies = {DISCOVERY: [], VALIDATION: [DISCOVERY]}
    webapp.project_state.init(
        project_dir,
        "project-001",
        "test",
        "Test Project",
        phase_slugs=[DISCOVERY, VALIDATION],
        dependencies=dependencies,
    )
    run_id = webapp.project_state.reserve_run(
        project_dir,
        DISCOVERY,
        "baseline",
        dependencies=dependencies,
    )
    webapp.project_state.set_process_pid(project_dir, DISCOVERY, run_id, 12001)
    webapp.project_state.start_round(
        project_dir, DISCOVERY, run_id, "Review the evidence", ["lead"], round_n=1
    )
    output = project_dir / "artifacts" / "discovery.txt"
    output.parent.mkdir()
    output.write_text("evidence", encoding="utf-8")
    webapp.project_state.complete_round(
        project_dir, DISCOVERY, run_id, 1, [output]
    )
    summary = project_dir / "summaries" / "discovery.html"
    summary.parent.mkdir()
    summary.write_text("<h1>Accepted result</h1>", encoding="utf-8")
    webapp.project_state.submit_run_for_review(
        project_dir, DISCOVERY, run_id, summary
    )
    webapp.project_state.approve_run(
        project_dir,
        DISCOVERY,
        run_id,
        approval_kind="approve",
        dependencies=dependencies,
    )
    summary.write_text("<h1>Tampered result</h1>", encoding="utf-8")

    overview = web_env["client"].get(f"/project/{PROJECT_ID}")
    overview_body = overview.get_data(as_text=True)
    phase = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={DISCOVERY}"
    )
    phase_body = phase.get_data(as_text=True)

    assert overview.status_code == 200
    # Simplified overview: integrity issues shown in phase detail
    assert "Research progress" in overview_body
    assert phase.status_code == 200
    # Simplified UI: integrity errors shown as inline-error in status panel
    assert "integrity" in phase_body.lower()
    assert "downstream phases should treat as accepted" not in phase_body


def test_summary_is_contained_and_served_with_a_sandboxed_csp(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = web_env["project_dir"]
    summary = project_dir / "phase-summaries" / DISCOVERY / "safe.html"
    summary.parent.mkdir(parents=True)
    summary.write_text(
        "<html><style>body{color:#fff}</style><body>Trusted report</body></html>",
        encoding="utf-8",
    )
    summary_hash = hashlib.sha256(summary.read_bytes()).hexdigest()
    outside = project_dir.parent / "outside.html"
    outside.write_text("outside secret", encoding="utf-8")

    def get_run(_project_dir, _phase_slug, run_id):
        if run_id == "safe":
            return {
                "run_id": run_id,
                "final_summary": summary.relative_to(project_dir),
                "summary_sha256": summary_hash,
            }
        if run_id == "escape":
            return {"run_id": run_id, "final_summary": "../outside.html"}
        raise KeyError(run_id)

    monkeypatch.setattr(webapp.project_state, "get_run", get_run)

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/safe/summary"
    )
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"Trusted report" in response.data
    csp = response.headers["Content-Security-Policy"]
    assert "sandbox" in csp
    assert "default-src 'none'" in csp
    assert "form-action 'none'" in csp
    assert response.headers["Cache-Control"] == "no-store"

    summary.write_text("<body>modified after submission</body>", encoding="utf-8")
    tampered = web_env["client"].get(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/safe/summary"
    )
    assert tampered.status_code == 409
    assert b"modified after submission" not in tampered.data

    escaped = web_env["client"].get(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/escape/summary"
    )
    assert escaped.status_code == 404
    assert b"outside secret" not in escaped.data


def test_run_log_is_contained_and_served_only_as_plain_text(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_dir = web_env["project_dir"]
    log_file = webapp.run_log_path(project_dir, DISCOVERY, "safe")
    log_file.parent.mkdir(parents=True)
    log_file.write_text("<script>not executable</script>\nround complete", encoding="utf-8")
    outside = project_dir.parent / "outside.log"
    outside.write_text("outside secret", encoding="utf-8")
    monkeypatch.setattr(
        webapp.project_state,
        "get_run",
        lambda _project_dir, _phase_slug, run_id: {"run_id": run_id},
    )

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/safe/log"
    )
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert b"<script>not executable</script>" in response.data
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"

    monkeypatch.setattr(webapp, "run_log_path", lambda *_args: outside)
    escaped = web_env["client"].get(
        f"/project/{PROJECT_ID}/phase/{DISCOVERY}/run/escape/log"
    )
    assert escaped.status_code == 404
    assert b"outside secret" not in escaped.data


# ---------------------------------------------------------------------------
# Branch retirement (Stage 3c)
# ---------------------------------------------------------------------------

def test_phase_two_retire_keeps_the_method_visible_as_history(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    _write_menu_file(
        web_env["project_dir"],
        "spectral-graph-coupling",
        "recommended",
        number=1,
    )
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    staled = Mock(return_value=[])
    monkeypatch.setattr(
        webapp.project_state, "mark_method_dependents_stale", staled
    )
    client = web_env["client"]

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/branch/retire",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            **_retirement_fields(
                web_env["project_dir"], "spectral-graph-coupling"
            ),
        },
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "remains visible as history" in body
    assert "Spectral Graph Coupling" in body
    assert "method-status-retired" in body
    assert 'name="stable_id" value="spectral-graph-coupling"' not in body
    staled.assert_called_once_with(
        web_env["project_dir"],
        "spectral-graph-coupling",
        reason="method spectral-graph-coupling was retired by the user",
    )


def test_phase_two_retire_rejects_a_stale_method_form(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    stable_id = "spectral-graph-coupling"
    _write_menu_file(
        web_env["project_dir"], stable_id, "recommended", number=1
    )
    submitted = _retirement_fields(web_env["project_dir"], stable_id)
    path = web_env["project_dir"] / "ideas" / "methods" / f"{stable_id}.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("version: v1", "version: v2"),
        encoding="utf-8",
    )
    staled = Mock(return_value=[])
    monkeypatch.setattr(
        webapp.project_state, "mark_method_dependents_stale", staled
    )
    client = web_env["client"]

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/branch/retire",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            **submitted,
        },
    )

    assert response.status_code == 409
    assert "changed after this page was shown" in response.get_data(as_text=True)
    entry, error = webapp.method_menu.find_selectable_entry(
        web_env["project_dir"], stable_id
    )
    assert error is None
    assert entry is not None
    assert entry["version"] == "v2"
    assert entry["status"] == "recommended"
    staled.assert_not_called()


def test_phase_two_retire_unknown_method_returns_404(
    web_env: dict,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    client = web_env["client"]

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/branch/retire",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            "stable_id": "ghost",
            "method_version": "v1",
            "method_sha256": "0" * 64,
        },
    )

    assert response.status_code == 404


def test_phase_two_retire_already_retired_returns_409(
    web_env: dict,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    _write_menu_file(web_env["project_dir"], "old-idea", "retired")
    client = web_env["client"]

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/branch/retire",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            **_retirement_fields(web_env["project_dir"], "old-idea"),
        },
    )

    assert response.status_code == 409


def test_consumer_phase_cannot_retire_a_method(
    web_env: dict,
) -> None:
    theory_slug = "03-idea-evaluation"
    web_env["config"]["phases"].append(_theory_phase_config())
    _write_menu_file(web_env["project_dir"], "active-method", "viable")
    client = web_env["client"]

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{theory_slug}/branch/retire",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            "stable_id": "active-method",
        },
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "active_phase",
    [webapp.project_state.METHOD_DEVELOPMENT_PHASE, "03-idea-evaluation"],
)
def test_phase_two_retirement_is_blocked_during_any_active_project_run(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
    active_phase: str,
) -> None:
    phase_slug = webapp.project_state.METHOD_DEVELOPMENT_PHASE
    web_env["config"]["phases"].append(_method_phase_config())
    _write_menu_file(web_env["project_dir"], "active-method", "viable")
    monkeypatch.setattr(
        webapp.project_state,
        "get_active_run",
        lambda _project: {
            "phase_slug": active_phase,
            "run_id": "active-run",
        },
    )
    client = web_env["client"]

    response = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/branch/retire",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            "stable_id": "active-method",
        },
    )

    assert response.status_code == 409
    assert "active project run" in response.get_data(as_text=True)
    entry, error = webapp.method_menu.find_selectable_entry(
        web_env["project_dir"], "active-method"
    )
    assert error is None
    assert entry is not None and entry["status"] == "viable"

# Phase 04 run modes (preliminary vs comprehensive)
# ──────────────────────────────────────────────────────────────────────────

def _phase_four_with_run_modes() -> dict:
    return {
        "slug": "04-draft-assembly",
        "name": "Implementation & Experiments",
        "description": "Implement and test.",
        "pattern": "sequential",
        "method_binding": True,
        "protocol_checkpoint": True,
        "run_modes": {
            "plans": ["preliminary", "comprehensive"],
            "default": "preliminary",
        },
        "gated_by": ["02-method-development"],
        "context_from": ["03-idea-evaluation"],
        "folder": "draft/sections/",
        "members": ["data_scientist", "theorist", "research_lead"],
        "rounds": {"min": 3, "default": 3, "max": 3},
        "stages": [
            {
                "role": "data_scientist",
                "name": "Implement and evaluate",
                "description": "Implement the selected scope.",
            },
            {
                "role": "theorist",
                "name": "Audit the evidence",
                "description": "Audit fidelity and interpretation.",
            },
            {
                "role": "research_lead",
                "name": "Synthesize the record",
                "description": "Summarize findings and disagreements.",
            },
        ],
    }


def test_phase_four_frozen_scope_is_visible_for_active_latest_and_history(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase = _phase_four_with_run_modes()
    web_env["config"]["phases"].append(phase)
    manifests = {
        "preliminary-run": {
            "phase_slug": phase["slug"],
            "run_id": "preliminary-run",
            "phase": {**phase, "run_plan": "preliminary"},
        },
        "comprehensive-run": {
            "phase_slug": phase["slug"],
            "run_id": "comprehensive-run",
            "phase": {**phase, "run_plan": "comprehensive"},
        },
    }
    monkeypatch.setattr(
        web_phase_data,
        "_sealed_run_manifest",
        lambda run, _phase: manifests[str(run["run_id"])],
    )
    monkeypatch.setattr(
        web_phase_data.project_state,
        "run_integrity_report",
        lambda *_args, **_kwargs: {"ok": True, "reason": ""},
    )
    preliminary = web_phase_data._run_view(
        web_env["project_dir"],
        phase["slug"],
        {
            "run_id": "preliminary-run",
            "status": "running",
            "rounds_requested": 3,
            "rounds": [],
        },
        1,
    )
    comprehensive = web_phase_data._run_view(
        web_env["project_dir"],
        phase["slug"],
        {
            "run_id": "comprehensive-run",
            "status": "awaiting_review",
            "rounds_requested": 3,
            "rounds": [],
        },
        2,
    )
    assert preliminary is not None and comprehensive is not None
    assert preliminary["frozen_plan"]["run_plan"] == "preliminary"
    assert preliminary["frozen_plan"]["variant"] == "Preliminary scope"
    assert comprehensive["frozen_plan"]["run_plan"] == "comprehensive"
    assert comprehensive["frozen_plan"]["variant"] == "Comprehensive scope"

    with webapp.app.test_request_context("/"):
        active_html = webapp.render_template(
            "_run_progress.html",
            phase_data={
                "latest_run": preliminary,
                "phase_cfg": phase,
                "run_active": True,
                "stages": phase["stages"],
            },
            project=web_env["project"],
            project_identity="sealed-project-identity",
        )
    assert '<span class="run-mode-badge">preliminary</span>' in active_html

    phase_data = {
        "phase_cfg": phase,
        "state": {"status": "awaiting_review"},
        "run_history": [comprehensive, preliminary],
        "latest_run": comprehensive,
        "approved_run": None,
        "run_active": False,
        "active_elsewhere": False,
        "can_start": False,
        "prerequisite_report": _ready_prerequisites(),
        "rounds_policy": phase["rounds"],
        "stages": phase["stages"],
        "plan_view": {},
        "decision_state": "awaiting_review",
        "recovery_only": False,
        "method_menu": {"entries": [], "warnings": []},
        "method_details": [],
        "catalog_method_selection": True,
    }
    monkeypatch.setattr(webapp, "_phase_catalog", lambda *_args: [phase])
    monkeypatch.setattr(webapp, "prepare_overview_data", lambda *_args: [])
    monkeypatch.setattr(webapp, "prepare_phase_data", lambda *_args: phase_data)

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={phase['slug']}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<span class="run-mode-badge">Comprehensive scope</span>' in body
    assert "Run 2: awaiting review" in body
    assert "Run 1: running" in body
    assert body.count("Comprehensive scope") >= 2
    assert "Preliminary scope" in body

def test_phase_four_renders_the_explicit_method_chooser_and_scope_selector(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = web_env["client"]
    web_env["config"]["phases"].append(_phase_four_with_run_modes())
    _write_menu_file(
        web_env["project_dir"],
        "active-method",
        "recommended",
        body=(
            "## Mathematical definition\n"
            "Evaluate $T_n = n^{-1/2}\\sum_i X_i$ under the stated model."
        ),
    )
    _write_menu_file(web_env["project_dir"], "retired-method", "retired")
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    page = client.get(f"/project/{PROJECT_ID}?tab=04-draft-assembly")

    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'name="method_menu_version"' in html
    assert 'name="method_branch"' in html
    assert "Phase 2 method catalog" in html
    assert 'name="phase_two_review_version" value=""' in html
    assert "Active Method" in html
    assert "Mathematical definition" in html
    assert "T_n" in html
    assert "data-mathjax-required" in html
    assert 'value="retired-method"' not in html
    radio = re.search(
        r'<input[^>]+name="method_branch"[^>]+value="active-method"[^>]*>',
        html,
    )
    assert radio is not None
    assert "checked" not in radio.group(0)
    assert "data-method-launch" in html
    assert "data-phase3-launch" not in html
    assert 'name="run_mode"' in html
    assert 'value="preliminary"' in html
    assert 'value="comprehensive"' in html
    assert "Either scope can be launched directly" in html
    preliminary = html[html.index('value="preliminary"'):]
    assert "selected" in preliminary[:200]


def test_phase_four_renders_method_basis_and_attention_as_separate_signals(
    web_env: dict,
) -> None:
    phase = _phase_four_with_run_modes()
    method = {
        "stable_id": "active-method",
        "label": "Active Method",
        "status": "recommended",
        "version": "v2",
        "launchable": True,
        "body_html": "<p>Current method definition.</p>",
        "record_status": {
            "method": {"state": "current", "label": "Current method"},
            "theory": {"state": "current", "label": "Current theory"},
            "empirical": {
                "state": "update_needed",
                "label": "Composite status retained for compatibility",
                "method_applicability": {
                    "state": "valid_current_version",
                    "label": "Valid for method v2",
                    "reason": "The record uses the current mathematical definition.",
                },
                "sibling_basis": {
                    "state": "changed",
                    "label": "Phase 3 basis changed",
                    "reason": "Decision-relevant theory changed after this run.",
                },
                "research_attention": {
                    "state": "required",
                    "indexed_count": 7,
                    "outdated_count": 2,
                    "unresolved_count": 1,
                    "label": "Three evidence entries require attention",
                    "reasons": ["Two results require revalidation"],
                },
            },
        },
    }
    phase_data = {
        "phase_cfg": phase,
        "state": {"status": "pending"},
        "run_history": [],
        "latest_run": None,
        "current_run": None,
        "run_active": False,
        "active_elsewhere": False,
        "can_start": True,
        "prerequisite_report": _ready_prerequisites(),
        "rounds_policy": phase["rounds"],
        "stages": phase["stages"],
        "plan_view": {},
        "decision_state": "pending",
        "recovery_only": False,
        "method_menu": {"entries": [method], "warnings": []},
        "method_details": [method],
        "method_ranking_table": [],
        "catalog_method_selection": True,
    }

    with webapp.app.test_request_context("/"):
        rendered = webapp.render_template(
            "_tab_phase.html",
            phase_data=phase_data,
            project=web_env["project"],
            project_identity="sealed-project-identity",
            run_permissions={"unattended_tools": True},
        )

    assert "Method version:" in rendered
    assert "Valid for method v2" in rendered
    assert "Phase 3 basis:" in rendered
    assert "Phase 3 basis changed" in rendered
    assert "Evidence requiring attention:" in rendered
    assert "Indexed 7," in rendered
    assert "outdated 2," in rendered
    assert "unresolved 1" in rendered
    assert "not scientific strength" in rendered
    assert 'data-state="valid_current_version"' in rendered
    assert 'data-state="changed"' in rendered
    assert 'data-state="required"' in rendered
    assert "Composite status retained for compatibility" not in rendered


@pytest.mark.parametrize("run_mode", ["preliminary", "comprehensive"])
def test_phase_four_scope_launches_all_three_stages(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
    run_mode: str,
) -> None:
    client = web_env["client"]
    web_env["config"]["phases"].append(_phase_four_with_run_modes())
    _write_menu_file(web_env["project_dir"], "active-method", "recommended")
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 3})
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    response = client.post(
        f"/project/{PROJECT_ID}/phase/04-draft-assembly/start",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            **_launch_tokens(web_env, "04-draft-assembly"),
            "method_branch": "active-method",
            "run_mode": run_mode,
        },
    )

    assert response.status_code == 302
    call = launched.call_args
    assert call.args[4] == 3
    assert call.kwargs["run_mode"] == run_mode
    assert call.kwargs["run_specific_method_id"] == "active-method"
    assert call.kwargs["expected_knowledge_heads_version"] == "a" * 64
    assert call.kwargs["expected_method_menu_version"] == (
        webapp.method_menu.catalog_version(web_env["project_dir"])
    )
    assert call.kwargs["expected_phase_two_review_version"] == "c" * 64


def test_phase_four_defaults_to_preliminary_with_all_three_stages(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = web_env["client"]
    web_env["config"]["phases"].append(_phase_four_with_run_modes())
    _write_menu_file(web_env["project_dir"], "active-method", "recommended")
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 3})
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )

    response = client.post(
        f"/project/{PROJECT_ID}/phase/04-draft-assembly/start",
        data={
            "csrf_token": _csrf(client),
            "project_identity": _project_identity(web_env),
            **_launch_tokens(web_env, "04-draft-assembly"),
            "method_branch": "active-method",
        },
    )

    assert response.status_code == 302
    call = launched.call_args
    assert call.args[4] == 3
    assert call.kwargs["run_mode"] == "preliminary"


def test_phase_four_rejects_missing_retired_and_stale_method_choices(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = web_env["client"]
    phase_slug = "04-draft-assembly"
    web_env["config"]["phases"].append(_phase_four_with_run_modes())
    _write_menu_file(web_env["project_dir"], "active-method", "recommended")
    _write_menu_file(web_env["project_dir"], "retired-method", "retired")
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 3})
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    common = {
        "csrf_token": _csrf(client),
        "project_identity": _project_identity(web_env),
        "run_mode": "preliminary",
    }

    missing = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/start",
        data={**common, **_launch_tokens(web_env, phase_slug)},
        follow_redirects=True,
    )
    assert "Choose an active method" in missing.get_data(as_text=True)

    retired = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/start",
        data={
            **common,
            **_launch_tokens(web_env, phase_slug),
            "method_branch": "retired-method",
        },
        follow_redirects=True,
    )
    assert "retired" in retired.get_data(as_text=True)

    reviewed_tokens = _launch_tokens(web_env, phase_slug)
    _write_menu_file(
        web_env["project_dir"],
        "active-method",
        "recommended",
        number=1,
        body="A changed definition with the same version.",
    )
    stale = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/start",
        data={
            **common,
            **reviewed_tokens,
            "method_branch": "active-method",
        },
        follow_redirects=True,
    )
    assert "catalog changed since this page was shown" in stale.get_data(
        as_text=True
    )
    launched.assert_not_called()

def _phase_five_config() -> dict:
    return {
        "slug": "05-review-revision",
        "name": "Paper Assembly & Review",
        "description": "Assemble and review the paper.",
        "pattern": "sequential",
        "method_binding": True,
        "gated_by": ["03-idea-evaluation", "04-draft-assembly"],
        "folder": "draft/revised/",
        "members": ["paper_reviewer", "research_lead"],
        "run_modes": {
            "plans": ["assembly", "review_revision"],
            "default": "assembly",
        },
        "stages": [{
            "role": "research_lead",
            "name": "Assemble",
            "description": "Assemble the verified branch record.",
        }],
    }


def test_phase_five_shows_collection_review_without_starting_a_run(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = "05-review-revision"
    web_env["config"]["phases"].append(_phase_five_config())
    _write_menu_file(
        web_env["project_dir"],
        "active-method",
        "recommended",
    )
    reason = (
        "The Phase 1 reference collection has changed since the manuscript "
        "was generated."
    )
    monkeypatch.setattr(
        web_phase_data.web_branch_status,
        "method_record_statuses",
        lambda *_args: [{
            "has_theory_history": True,
            "knowledge_heads_version": "a" * 64,
            "branch_graph_version": "b" * 64,
            "launch_context_error": "",
            "record_status": {
                "theory": {
                    "state": "current",
                    "label": "Theory is aligned",
                    "reason": "The theory package matches the current method.",
                },
                "empirical": {
                    "state": "current",
                    "label": "Empirical evidence is aligned",
                    "reason": (
                        "The empirical package matches the current method."
                    ),
                },
                "manuscript": {
                    "state": "update_needed",
                    "label": "Manuscript inputs need review",
                    "reason": reason,
                    "changed_input_labels": [
                        "Phase 1 reference collection"
                    ],
                },
            },
        }],
    )
    monkeypatch.setattr(
        web_phase_data,
        "phase_five_branch_readiness",
        _ready_phase_five_branch,
    )
    monkeypatch.setattr(
        webapp,
        "phase_five_branch_readiness",
        _ready_phase_five_branch,
    )
    monkeypatch.setattr(
        webapp.project_state,
        "prerequisite_report",
        _ready_prerequisites,
    )
    launched = Mock()
    monkeypatch.setattr(webapp, "launch_run", launched)

    response = web_env["client"].get(
        f"/project/{PROJECT_ID}?tab={phase_slug}"
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "P5: Manuscript inputs need review" in body
    assert body.count(reason) == 2
    assert 'name="method_branch" value="active-method"' in body
    assert "Manuscript requires revision" not in body
    launched.assert_not_called()


def test_phase_five_chooser_and_launch_require_all_exact_branch_results(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = web_env["client"]
    phase_slug = "05-review-revision"
    web_env["config"]["phases"].append(_phase_five_config())
    _write_menu_file(web_env["project_dir"], "active-method", "recommended")
    ready = False
    checked_methods: list[tuple[str, str, str]] = []
    required_completed_runs = {
        "01-literature-review": "literature-ready",
        webapp.project_state.METHOD_DEVELOPMENT_PHASE: "method-menu-ready",
        "03-idea-evaluation": "theory-ready",
        "04-draft-assembly": "experiment-ready",
    }

    def branch_readiness(_project: Path, method: dict) -> dict:
        checked_methods.append((
            str(method["stable_id"]),
            str(method["version"]),
            str(method["sha256"]),
        ))
        requirements = []
        if ready:
            for required_phase, label, branch_specific in (
                (
                    "01-literature-review",
                    "Phase 1 literature review",
                    False,
                ),
                (
                    webapp.project_state.METHOD_DEVELOPMENT_PHASE,
                    "Phase 2 method development",
                    False,
                ),
                (
                    "03-idea-evaluation",
                    "Phase 3 theoretical development",
                    True,
                ),
                (
                    "04-draft-assembly",
                    "Phase 4 implementation and experiments",
                    True,
                ),
            ):
                result = {
                    "phase": required_phase,
                    "run_id": required_completed_runs[required_phase],
                    "status": "awaiting_review",
                    "scientific_outcome": "Complete",
                }
                if branch_specific:
                    result.update({
                        "method_id": str(method["stable_id"]),
                        "method_version": str(method["version"]),
                        "method_sha256": str(method["sha256"]),
                    })
                requirements.append({
                    "phase": required_phase,
                    "label": label,
                    "satisfied": True,
                    "result": result,
                })
        return {
            "ready": ready,
            "method_id": str(method["stable_id"]),
            "method_version": str(method["version"]),
            "method_sha256": str(method["sha256"]),
            "requirements": requirements,
            "blockers": (
                []
                if ready
                else ["Phase 4 implementation and experiments"]
            ),
        }

    monkeypatch.setattr(
        web_phase_data,
        "phase_five_branch_readiness",
        branch_readiness,
    )
    monkeypatch.setattr(webapp, "phase_five_branch_readiness", branch_readiness)
    prerequisite_report = Mock(side_effect=_ready_prerequisites)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", prerequisite_report
    )
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 1})
    monkeypatch.setattr(webapp, "launch_run", launched)

    blocked_page = client.get(f"/project/{PROJECT_ID}?tab={phase_slug}")
    blocked_html = blocked_page.get_data(as_text=True)
    assert blocked_page.status_code == 200
    assert 'name="method_menu_version"' in blocked_html
    assert "Active Method" in blocked_html
    assert "Phase 4 implementation and experiments" in blocked_html
    assert 'value="active-method"' not in blocked_html

    common = {
        "csrf_token": _csrf(client),
        "project_identity": _project_identity(web_env),
        "run_mode": "assembly",
        "method_branch": "active-method",
    }
    blocked_launch = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/start",
        data={**common, **_launch_tokens(web_env, phase_slug)},
        follow_redirects=True,
    )
    assert "Phase 5 is not ready" in blocked_launch.get_data(as_text=True)
    launched.assert_not_called()

    ready = True
    ready_page = client.get(f"/project/{PROJECT_ID}?tab={phase_slug}")
    ready_html = ready_page.get_data(as_text=True)
    radio = re.search(
        r'<input[^>]+name="method_branch"[^>]+value="active-method"[^>]*>',
        ready_html,
    )
    assert radio is not None
    assert "checked" not in radio.group(0)
    assert re.search(r'data-knowledge-heads-version="[0-9a-f]{64}"', radio.group(0))
    assert re.search(r'data-branch-graph-version="[0-9a-f]{64}"', radio.group(0))
    assert 'name="knowledge_heads_version" value=""' in ready_html
    assert 'name="branch_graph_version" value=""' in ready_html
    assert "data-method-launch" in ready_html
    assert 'name="run_mode"' in ready_html
    assert 'value="assembly"' in ready_html
    assert 'value="review_revision"' in ready_html
    assert 'name="review_target"' not in ready_html

    legacy_launch = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/start",
        data={
            **common,
            **_launch_tokens(web_env, phase_slug),
            "review_target": "draft/run/01/manuscript-post-review.md",
        },
    )
    assert legacy_launch.status_code == 302
    launched.assert_not_called()

    accepted = client.post(
        f"/project/{PROJECT_ID}/phase/{phase_slug}/start",
        data={**common, **_launch_tokens(web_env, phase_slug)},
    )

    assert accepted.status_code == 302
    launched.assert_called_once()
    call = launched.call_args
    assert call.args[4] == 1
    assert call.kwargs["run_mode"] == "assembly"
    assert call.kwargs["run_specific_method_id"] == "active-method"
    assert call.kwargs["run_specific_method_version"] == "v1"
    assert len(call.kwargs["run_specific_method_sha256"]) == 64
    assert call.kwargs["expected_knowledge_heads_version"] == "a" * 64
    assert call.kwargs["expected_branch_graph_version"] == "b" * 64
    phase_five_calls = [
        report_call
        for report_call in prerequisite_report.call_args_list
        if report_call.args[1] == phase_slug
    ]
    assert len(phase_five_calls) == 1
    assert phase_five_calls[0].kwargs == {
        "required_completed_runs": required_completed_runs,
        "required_method_id": "active-method",
    }
    assert checked_methods
    assert all(identity[:2] == ("active-method", "v1") for identity in checked_methods)


def test_phase_five_does_not_claim_ready_when_every_method_is_baseline_blocked(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = "05-review-revision"
    phase_cfg = _phase_five_config()
    web_env["config"]["phases"].append(phase_cfg)
    _write_menu_file(web_env["project_dir"], "method-a", "recommended")
    _write_menu_file(web_env["project_dir"], "method-b", "recommended")
    blockers = ["Phase 1 literature review", "Phase 2 method development"]

    def branch_readiness(_project: Path, method: dict) -> dict:
        return {
            "ready": False,
            "method_id": method["stable_id"],
            "requirements": [
                {
                    "phase": "01-literature-review",
                    "satisfied": False,
                    "result": None,
                },
                {
                    "phase": "02-method-development",
                    "satisfied": False,
                    "result": None,
                },
            ],
            "blockers": blockers,
        }

    monkeypatch.setattr(
        web_phase_data,
        "phase_five_branch_readiness",
        branch_readiness,
    )
    monkeypatch.setattr(webapp, "phase_five_branch_readiness", branch_readiness)
    monkeypatch.setattr(
        webapp.project_state,
        "prerequisite_report",
        _ready_prerequisites,
    )

    phase_data = web_phase_data.prepare_phase_data(
        web_env["project_dir"],
        PROJECT_ID,
        phase_cfg,
        web_env["config"]["phases"],
    )
    assert phase_data["can_run"] is False
    assert phase_data["prerequisite_report"]["satisfied"] is False
    assert "No active method has usable current results" in phase_data["gating_reason"]

    response = web_env["client"].get(f"/project/{PROJECT_ID}?tab={phase_slug}")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert all(blocker in body for blocker in blockers)
    assert "Choose a method above before launch." not in body
    assert "Produce usable current results in Phases 1 through 4" in body


def test_phase_four_rejects_invalid_run_mode(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid run_mode value is rejected; the launcher is never called."""
    client = web_env["client"]
    web_env["config"]["phases"].append(_phase_four_with_run_modes())
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 1})
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    token = _csrf(client)
    identity = _project_identity(web_env)
    response = client.post(
        f"/project/{PROJECT_ID}/phase/04-draft-assembly/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, "04-draft-assembly"),
            "run_mode": "bogus",
        },
    )
    # Validation error → redirect back with flash; launcher never called
    launched.assert_not_called()


def test_phase_four_run_mode_rejected_on_unconfigured_phase(
    web_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Phase 04 WITHOUT run_modes config rejects a run_mode form value."""
    client = web_env["client"]
    phase = _phase_four_with_run_modes()
    del phase["run_modes"]
    web_env["config"]["phases"].append(phase)
    launched = Mock(return_value={"run_number": 1, "rounds_requested": 1})
    monkeypatch.setattr(webapp, "launch_run", launched)
    monkeypatch.setattr(
        webapp.project_state, "prerequisite_report", _ready_prerequisites
    )
    token = _csrf(client)
    identity = _project_identity(web_env)
    response = client.post(
        f"/project/{PROJECT_ID}/phase/04-draft-assembly/start",
        data={
            "csrf_token": token,
            "project_identity": identity,
            **_launch_tokens(web_env, "04-draft-assembly"),
            "run_mode": "preliminary",
        },
    )
    launched.assert_not_called()


def test_run_modes_config_validation_only_on_phase_four(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_modes is rejected on a phase other than 04-draft-assembly."""
    import hub as hub_module
    config = {
        "hub": {"name": "T", "workspace_dir": str(tmp_path)},
        "agents": [{"id": "research_lead", "profile": "p", "name": "L", "role": "r"}],
        "phases": [
            {
                "slug": "03-idea-evaluation",
                "name": "Theory",
                "description": "d",
                "pattern": "parallel",
                "gated_by": [],
                "folder": "f/",
                "members": ["research_lead"],
                "rounds": {"min": 1, "default": 1, "max": 2},
                "run_modes": {"plans": ["preliminary", "comprehensive"], "default": "preliminary"},
            }
        ],
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    # Playbook root is CONFIG_PATH.parent / "config" / "phases"
    playbook_root = config_path.parent / "config" / "phases" / "03-idea-evaluation"
    playbook_root.mkdir(parents=True)
    for fname in ("_lead.md", "_phase.md", "research_lead.md"):
        (playbook_root / fname).write_text("# x\n", encoding="utf-8")
    # Agent soul files
    soul_root = config_path.parent / "config" / "souls"
    soul_root.mkdir(parents=True, exist_ok=True)
    (soul_root / "research_lead.md").write_text("# soul\n", encoding="utf-8")
    monkeypatch.setattr(hub_module, "CONFIG_PATH", config_path)
    with pytest.raises(hub_module.ConfigurationError, match="run_modes is only valid for Phase 04 or Phase 05"):
        hub_module.load_config()


def test_run_modes_rejects_wrong_plans_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_modes.plans must be exactly ['preliminary', 'comprehensive'] in that order."""
    import hub as hub_module
    config = {
        "hub": {"name": "T", "workspace_dir": str(tmp_path)},
        "agents": [{"id": "research_lead", "profile": "p", "name": "L", "role": "r"}],
        "phases": [
            {
                "slug": "04-draft-assembly",
                "name": "Experiments",
                "description": "d",
                "pattern": "parallel",
                "gated_by": [],
                "folder": "f/",
                "members": ["research_lead"],
                "rounds": {"min": 1, "default": 2, "max": 2},
                "run_modes": {"plans": ["comprehensive", "preliminary"], "default": "preliminary"},
            }
        ],
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")
    playbook_root = config_path.parent / "config" / "phases" / "04-draft-assembly"
    playbook_root.mkdir(parents=True)
    for fname in ("_lead.md", "_phase.md", "research_lead.md"):
        (playbook_root / fname).write_text("# x\n", encoding="utf-8")
    # Agent soul files
    soul_root = config_path.parent / "config" / "souls"
    soul_root.mkdir(parents=True, exist_ok=True)
    (soul_root / "research_lead.md").write_text("# soul\n", encoding="utf-8")
    monkeypatch.setattr(hub_module, "CONFIG_PATH", config_path)
    with pytest.raises(hub_module.ConfigurationError, match="plans must contain"):
        hub_module.load_config()



def test_index_skips_projects_with_missing_workspace(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(webapp.hub, "get_project_dir", lambda _pid: None)
    client = web_env["client"]

    response = client.get("/")
    assert response.status_code == 200
    assert "missing or unreadable" in response.get_data(as_text=True)

    response = client.get(f"/project/{PROJECT_ID}")
    assert response.status_code == 200
    assert "workspace" in response.get_data(as_text=True)
    assert "stale registry entry" in response.get_data(as_text=True)


def test_project_view_renders_state_error_page(
    web_env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise webapp.project_state.StateValidationError(
            "project state is not valid UTF-8 YAML"
        )

    monkeypatch.setattr(webapp, "prepare_overview_data", broken)
    response = web_env["client"].get(f"/project/{PROJECT_ID}")
    body = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "control state could not be read" in body
    assert "not valid UTF-8 YAML" in body
