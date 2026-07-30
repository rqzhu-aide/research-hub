from __future__ import annotations

from pathlib import Path

import pytest

from core import launch_run as launcher


@pytest.mark.parametrize(
    ("changed_context", "error_pattern"),
    [
        ("knowledge_heads", "Phase 3 or Phase 4 records changed"),
        (
            "phase_two_review",
            "Phase 2 literature-review status changed",
        ),
    ],
)
def test_locked_launch_rechecks_branch_after_snapshot_before_worker_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_context: str,
    error_pattern: str,
) -> None:
    project = tmp_path / "project"
    method_dir = project / "ideas" / "methods"
    method_dir.mkdir(parents=True)
    method_file = method_dir / "method-a.md"
    method_file.write_text(
        "---\n"
        "stable_id: method-a\n"
        "version: v1\n"
        "label: Method A\n"
        "status: recommended\n"
        "number: 1\n"
        "---\n\n"
        "# Method A\n\nExact definition.\n",
        encoding="utf-8",
    )
    method, error = launcher.method_menu.find_selectable_entry(
        project,
        "method-a",
    )
    assert error is None and method is not None

    phase = {
        "slug": launcher.DRAFT_ASSEMBLY_PHASE,
        "name": "Implementation and experiments",
        "pattern": "sequential",
        "method_binding": True,
        "gated_by": [],
        "folder": "numerical/",
        "members": ["research_lead"],
        "stages": [{"role": "research_lead"}],
    }
    config = {"hub": {}, "agents": [], "phases": [phase]}
    hermes_root = tmp_path / "hermes"
    head_version = {"value": "a" * 64}
    phase_two_version = {"value": "b" * 64}
    events: list[str] = []
    worker_started = False

    monkeypatch.setattr(
        launcher.launch_plans,
        "_load_hub_config",
        lambda: config,
    )
    monkeypatch.setattr(
        launcher.profile_skills,
        "resolve_hermes_root",
        lambda: hermes_root,
    )
    monkeypatch.setattr(
        launcher.launch_plans,
        "_recommended_skills_snapshot",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        launcher.launch_plans,
        "launch_plan_version",
        lambda *_args, **_kwargs: "f" * 64,
    )
    monkeypatch.setattr(
        launcher.launch_plans,
        "_role_profiles",
        lambda _config: {"research_lead": "lead"},
    )
    monkeypatch.setattr(
        launcher,
        "_preflight",
        lambda *_args, **_kwargs: ("hermes", hermes_root),
    )
    monkeypatch.setattr(
        launcher.launch_plans,
        "_dependencies",
        lambda _config: {launcher.DRAFT_ASSEMBLY_PHASE: []},
    )
    monkeypatch.setattr(
        launcher.project_state,
        "load",
        lambda _project: {"project": {"name": "Project"}},
    )
    monkeypatch.setattr(
        launcher,
        "_workspace_board_slug",
        lambda *_args: "board",
    )
    monkeypatch.setattr(
        launcher,
        "_ensure_board",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "prerequisite_report",
        lambda *_args, **_kwargs: {
            "satisfied": True,
            "blockers": [],
            "requirements": [],
        },
    )
    monkeypatch.setattr(
        launcher.project_state,
        "decision_report_version",
        lambda *_args: "d" * 64,
    )
    monkeypatch.setattr(
        launcher.launch_prompts,
        "_has_prior_method_run",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        launcher.knowledge_heads,
        "derive_live_heads",
        lambda *_args: {"verified": True},
    )
    monkeypatch.setattr(
        launcher.knowledge_heads,
        "heads_version",
        lambda _heads: head_version["value"],
    )
    monkeypatch.setattr(
        launcher.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: {"projection": True},
    )
    monkeypatch.setattr(
        launcher.knowledge_graph,
        "phase_two_review_projection_version",
        lambda _graph: phase_two_version["value"],
    )

    def reserve(*_args, **_kwargs) -> str:
        events.append("reserve")
        return "race-run"

    def snapshot(*_args, **_kwargs) -> dict[str, object]:
        assert events == ["reserve"]
        events.append("snapshot")
        if changed_context == "knowledge_heads":
            head_version["value"] = "c" * 64
        else:
            phase_two_version["value"] = "d" * 64
        return {}

    def start_worker(*_args, **_kwargs):
        nonlocal worker_started
        worker_started = True
        pytest.fail("A stale launch must fail before worker start")

    monkeypatch.setattr(launcher.project_state, "reserve_run", reserve)
    monkeypatch.setattr(launcher.launch_common, "_run_index", lambda *_args: 0)
    monkeypatch.setattr(
        launcher.phase_records,
        "current_context_records",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        launcher.launch_prompts,
        "_trusted_context",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        launcher.project_state,
        "set_run_context",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        launcher.launch_prompts,
        "_snapshot_run_inputs",
        snapshot,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "begin_run_cleanup",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "finalize_run_cleanup",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(launcher.subprocess, "Popen", start_worker)

    with pytest.raises(
        launcher.LaunchError, match=error_pattern
    ):
        launcher._launch_run_locked(
            project,
            1,
            launcher.DRAFT_ASSEMBLY_PHASE,
            run_specific_method_id="method-a",
            run_specific_method_version="v1",
            run_specific_method_sha256=str(method["sha256"]),
            expected_method_menu_version=(
                launcher.method_menu.catalog_version(project)
            ),
            expected_knowledge_heads_version="a" * 64,
            expected_phase_two_review_version="b" * 64,
        )

    assert events == ["reserve", "snapshot"]
    assert worker_started is False
