from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import launch_run as launcher


def test_launch_run_revalidates_the_project_inside_the_operation_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hub

    requested = (tmp_path / "requested-project").resolve()
    replacement = (tmp_path / "replacement-project").resolve()
    requested.mkdir()
    replacement.mkdir()
    launched: list[Path] = []

    monkeypatch.setattr(hub, "operation_lock", lambda: nullcontext())
    monkeypatch.setattr(hub, "get_workspace_dir", lambda: tmp_path)
    monkeypatch.setattr(
        hub,
        "get_project",
        lambda _project_id: {"directory_name": replacement.name},
    )
    monkeypatch.setattr(hub, "get_project_dir", lambda _project_id: replacement)
    monkeypatch.setattr(
        launcher,
        "_launch_run_locked",
        lambda project_dir, *_args, **_kwargs: launched.append(Path(project_dir))
        or {"run_id": "unexpected"},
    )

    with pytest.raises(launcher.LaunchError, match="changed before launch"):
        launcher.launch_run(requested, 7, "01-literature-review")
    assert launched == []

    monkeypatch.setattr(hub, "get_project_dir", lambda _project_id: None)
    with pytest.raises(launcher.LaunchError, match="no longer present"):
        launcher.launch_run(requested, 7, "01-literature-review")
    assert launched == []

    monkeypatch.setattr(hub, "get_project_dir", lambda _project_id: requested)
    result = launcher.launch_run(requested, 7, "01-literature-review")
    assert result == {"run_id": "unexpected"}
    assert launched == [requested]

    launched.clear()
    monkeypatch.setattr(
        hub,
        "get_project",
        lambda _project_id: {"directory_name": requested.name},
    )
    with pytest.raises(launcher.LaunchError, match="changed after this page"):
        launcher.launch_run(
            requested,
            7,
            "01-literature-review",
            expected_workspace_path=str(tmp_path.resolve()),
            expected_project_directory_name="stale-project-name",
            expected_project_path=str(requested),
        )
    assert launched == []

    result = launcher.launch_run(
        requested,
        7,
        "01-literature-review",
        expected_workspace_path=str(tmp_path.resolve()),
        expected_project_directory_name=requested.name,
        expected_project_path=str(requested),
    )
    assert result == {"run_id": "unexpected"}
    assert launched == [requested]


def _completed(payload: object, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["hermes"],
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr="",
    )


def _valid_decision_record() -> dict[str, object]:
    return {
        "schema_version": 1,
        "scientific_outcome": "Complete",
        "decision_requested": "Decide whether to accept the stated baseline.",
        "recommended_user_action": "approve",
        "recommendation": "Accept the qualified result.",
        "main_evidence": ["The sealed source report supports STMT-1."],
        "principal_risk": "The result has not been tested outside its stated scope.",
        "smallest_decision_changer": "A counterexample within the stated scope.",
        "option_consequences": {
            "approve": "Accept the proposed baseline.",
            "approve_with_limitations": "Accept it with the stated limitation.",
            "request_revision": "Request a bounded correction.",
            "rerun": "Test the same question with a changed design.",
            "defer": "Leave the current baseline unchanged.",
        },
        "rerun_question": "Does STMT-1 hold under the same assumptions?",
        "rerun_comparison": "This is the source run.",
        "proposed_baseline": "STMT-1 holds under assumptions A and B.",
        "scientific_record_changes": [],
    }


def _source_submission(
    project: Path,
    phase_slug: str,
    run_id: str,
    *,
    status: str = "approved",
) -> tuple[dict[str, object], Path, Path]:
    summary = project / "phase-summaries" / phase_slug / f"{run_id}.html"
    decision = summary.with_suffix(".decision.json")
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        "<h1>Source baseline</h1><p id='STMT-1'>STMT-1 holds under A and B.</p>",
        encoding="utf-8",
    )
    decision_data = _valid_decision_record()
    decision.write_text(json.dumps(decision_data, indent=2), encoding="utf-8")
    run = {
        "run_id": run_id,
        "status": status,
        "submitted_at": "2026-07-21T00:00:00+00:00",
        "final_summary": summary.relative_to(project).as_posix(),
        "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
        "decision_record": {
            "path": decision.relative_to(project).as_posix(),
            "sha256": hashlib.sha256(decision.read_bytes()).hexdigest(),
            "size": len(decision.read_bytes()),
            "schema_version": 1,
            "data": launcher.project_state.validate_decision_record(decision_data),
        },
    }
    return run, summary, decision


def _schema_v2_manifest() -> dict[str, object]:
    def leaf(name: str) -> dict[str, str]:
        return {"path": f"/frozen/{name}", "sha256": "a" * 64}

    return {
        "schema_version": 2,
        "phase": {"members": ["theorist"]},
        "snapshots": {
            "setting": leaf("setting.md"),
            "team": {
                "charter": leaf("charter.md"),
                "norms": leaf("norms.md"),
            },
            "souls": {
                "research_lead": leaf("research_lead.md"),
                "theorist": leaf("theorist.md"),
            },
            "playbooks": {
                "_lead.md": leaf("_lead.md"),
                "_phase.md": leaf("_phase.md"),
                "theorist.md": leaf("theorist-playbook.md"),
            },
            "summaries": [
                {
                    **leaf("summary.html"),
                    "phase": "01-literature",
                    "run_id": "approved-run",
                }
            ],
        },
    }


def _approved_method_snapshots() -> dict[str, object]:
    return {
        "summaries": [
            {
                "phase": launcher.project_state.METHOD_DEVELOPMENT_PHASE,
                "run_id": "phase-02-approved",
                "trusted": True,
                "decision_record": {
                    "path": (
                        "decisions/02-method-development-phase-02-approved.json"
                    ),
                    "sha256": "b" * 64,
                    "schema_version": 2,
                    "selected_scientific_object": {
                        "kind": "method",
                        "stable_id": "adaptive-score-test",
                        "version": "v1.2",
                    },
                },
            }
        ]
    }


def test_launch_plan_version_tracks_phase_config_and_instructions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub_dir = tmp_path / "hub"
    team_dir = hub_dir / "config" / "team"
    souls_dir = hub_dir / "config" / "souls"
    phases_dir = hub_dir / "config" / "phases"
    phase_dir = phases_dir / launcher.THEORETICAL_ANALYSIS_PHASE
    for directory in (team_dir, souls_dir, phase_dir):
        directory.mkdir(parents=True, exist_ok=True)

    instructions = {
        team_dir / "charter.md": "Team charter\n",
        team_dir / "norms.md": "Team norms\n",
        souls_dir / "research_lead.md": "Lead instructions\n",
        souls_dir / "theorist.md": "Theorist instructions\n",
        phase_dir / "_lead.md": "Phase lead instructions\n",
        phase_dir / "_phase.md": "Phase instructions\n",
        phase_dir / "theorist.md": "Phase theorist instructions\n",
    }
    for path, content in instructions.items():
        path.write_text(content, encoding="utf-8")

    monkeypatch.setattr(launcher, "HUB_DIR", hub_dir)
    monkeypatch.setattr(launcher, "TEAM_DIR", team_dir)
    monkeypatch.setattr(launcher, "SOULS_DIR", souls_dir)
    monkeypatch.setattr(launcher, "PHASES_DIR", phases_dir)
    config = {
        "hub": {
            "allow_unattended_tools": False,
            "run_timeout_minutes": 120,
        },
        "agents": [
            {"id": "research_lead", "profile": "lead-profile"},
            {"id": "theorist", "profile": "theory-profile"},
        ],
        "phases": [
            {
                "slug": launcher.THEORETICAL_ANALYSIS_PHASE,
                "members": ["theorist"],
                "rounds": {"min": 1, "default": 2, "max": 4},
            }
        ],
    }

    original = launcher.launch_plan_version(
        config, launcher.THEORETICAL_ANALYSIS_PHASE
    )
    changed_config = json.loads(json.dumps(config))
    changed_config["phases"][0]["rounds"]["default"] = 3
    assert (
        launcher.launch_plan_version(
            changed_config, launcher.THEORETICAL_ANALYSIS_PHASE
        )
        != original
    )

    phase_instruction = phase_dir / "theorist.md"
    phase_instruction.write_text("Revised phase theorist instructions\n", encoding="utf-8")
    assert (
        launcher.launch_plan_version(
            config, launcher.THEORETICAL_ANALYSIS_PHASE
        )
        != original
    )


def test_locked_launch_rejects_a_stale_phase_plan_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    phase_slug = "01-literature-review"
    config = {"phases": [{"slug": phase_slug}]}
    monkeypatch.setattr(launcher, "_load_hub_config", lambda: config)
    monkeypatch.setattr(launcher, "launch_plan_version", lambda *_args: "a" * 64)

    with pytest.raises(launcher.LaunchError, match="instructions changed"):
        launcher._launch_run_locked(
            tmp_path,
            1,
            phase_slug,
            expected_phase_plan_version="b" * 64,
        )


def test_method_selection_freezes_the_approved_phase_two_decision() -> None:
    selection = launcher._method_selection_for_run(
        {"slug": launcher.THEORETICAL_ANALYSIS_PHASE},
        _approved_method_snapshots(),
        "",
        "",
    )

    assert selection == {
        "kind": "method",
        "stable_id": "adaptive-score-test",
        "version": "v1.2",
        "source": "approved_phase_02_selection",
        "source_phase": launcher.project_state.METHOD_DEVELOPMENT_PHASE,
        "source_run_id": "phase-02-approved",
        "decision_record": {
            "path": "decisions/02-method-development-phase-02-approved.json",
            "sha256": "b" * 64,
            "schema_version": 2,
        },
    }


def test_run_specific_method_identity_overrides_the_approved_selection() -> None:
    selection = launcher._method_selection_for_run(
        {"slug": launcher.NUMERICAL_VALIDATION_PHASE},
        _approved_method_snapshots(),
        "user-selected-method",
        "2026.07",
    )

    assert selection == {
        "kind": "method",
        "stable_id": "user-selected-method",
        "version": "2026.07",
        "source": "run_specific_user_selection",
        "source_phase": None,
        "source_run_id": None,
        "decision_record": None,
    }


@pytest.mark.parametrize(
    "phase_slug",
    [
        launcher.THEORETICAL_ANALYSIS_PHASE,
        launcher.NUMERICAL_VALIDATION_PHASE,
    ],
)
def test_standard_method_phases_reject_a_missing_method_identity(
    phase_slug: str,
) -> None:
    with pytest.raises(launcher.LaunchError, match="exact method identity"):
        launcher._method_selection_for_run(
            {"slug": phase_slug},
            {"summaries": []},
            "",
            "",
        )


def test_audit_only_phase_three_requires_no_method_selection() -> None:
    phase = {
        "slug": launcher.THEORETICAL_ANALYSIS_PHASE,
        "audit_only": True,
    }

    assert launcher._method_selection_for_run(
        phase, {"summaries": []}, "", ""
    ) is None
    assert launcher._validated_manifest_method_selection({
        "phase_slug": launcher.THEORETICAL_ANALYSIS_PHASE,
        "phase": phase,
        "method_selection": None,
    }) is None
    with pytest.raises(launcher.LaunchError, match="audit-only"):
        launcher._method_selection_for_run(
            phase,
            {"summaries": []},
            "method-that-must-not-be-used",
            "v1",
        )


@pytest.mark.parametrize("field", ["path", "sha256"])
def test_manifest_method_selection_rejects_decision_provenance_mismatch(
    field: str,
) -> None:
    snapshots = _approved_method_snapshots()
    selection = launcher._method_selection_for_run(
        {"slug": launcher.THEORETICAL_ANALYSIS_PHASE},
        snapshots,
        "",
        "",
    )
    assert selection is not None
    mismatched = json.loads(json.dumps(selection))
    mismatched["decision_record"][field] = (
        "decisions/a-different-decision.json" if field == "path" else "c" * 64
    )
    manifest = {
        "phase_slug": launcher.THEORETICAL_ANALYSIS_PHASE,
        "phase": {"slug": launcher.THEORETICAL_ANALYSIS_PHASE},
        "snapshots": snapshots,
        "method_selection": mismatched,
    }

    with pytest.raises(launcher.LaunchError, match="frozen decision record"):
        launcher._validated_manifest_method_selection(manifest)


def test_shell_join_quotes_a_windows_ampersand_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher.os, "name", "nt")

    command = launcher._shell_join(
        [r"C:\Research & Analysis\python.exe", "argument with spaces", "O'Brien"]
    )

    assert command == (
        r"& 'C:\Research & Analysis\python.exe' "
        r"'argument with spaces' 'O''Brien'"
    )
    assert command.count("&") == 2


def test_shell_join_uses_posix_quoting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(launcher.os, "name", "posix")

    command = launcher._shell_join(["python3", "/tmp/research & analysis/run.py"])

    assert command == "python3 '/tmp/research & analysis/run.py'"


def test_windows_command_guard_counts_utf16_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(launcher.os, "name", "nt")

    with pytest.raises(launcher.LaunchError, match="command-line length"):
        launcher._guard_command_length(["U0001f600" * 15_001])


def test_sealed_manifest_rejects_post_launch_changes(tmp_path: Path) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    phase_slug = "01-literature"
    launcher.project_state.init(
        project,
        "project-001",
        "project",
        "Project",
        phase_slugs=[phase_slug],
        dependencies={phase_slug: []},
    )
    run_id = launcher.project_state.reserve_run(project, phase_slug, "test")
    manifest_file = launcher.run_manifest_path(project, phase_slug, run_id)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "phase_slug": phase_slug,
        "timeout_minutes": 10,
        "value": "original",
    }
    manifest_file.write_text(json.dumps(payload), encoding="utf-8")
    launcher.project_state.seal_run_manifest(
        project, phase_slug, run_id, manifest_file
    )

    assert launcher._read_manifest(project, phase_slug, run_id)["value"] == "original"
    payload["value"] = "modified"
    manifest_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(launcher.LaunchError, match="changed after launch"):
        launcher._read_manifest(project, phase_slug, run_id)


def test_v2_snapshot_schema_requires_complete_hashed_inputs() -> None:
    manifest = _schema_v2_manifest()
    launcher._validate_manifest_snapshot_schema(manifest)

    missing_setting_hash = _schema_v2_manifest()
    del missing_setting_hash["snapshots"]["setting"]["sha256"]
    with pytest.raises(launcher.LaunchError, match="path and sha256"):
        launcher._validate_manifest_snapshot_schema(missing_setting_hash)

    missing_team_path = _schema_v2_manifest()
    del missing_team_path["snapshots"]["team"]["norms"]["path"]
    with pytest.raises(launcher.LaunchError, match="path and sha256"):
        launcher._validate_manifest_snapshot_schema(missing_team_path)

    missing_soul = _schema_v2_manifest()
    del missing_soul["snapshots"]["souls"]["theorist"]
    with pytest.raises(launcher.LaunchError, match="souls must contain exactly"):
        launcher._validate_manifest_snapshot_schema(missing_soul)

    missing_soul_hash = _schema_v2_manifest()
    del missing_soul_hash["snapshots"]["souls"]["theorist"]["sha256"]
    with pytest.raises(launcher.LaunchError, match="path and sha256"):
        launcher._validate_manifest_snapshot_schema(missing_soul_hash)

    missing_playbook_hash = _schema_v2_manifest()
    del missing_playbook_hash["snapshots"]["playbooks"]["theorist.md"]["sha256"]
    with pytest.raises(launcher.LaunchError, match="path and sha256"):
        launcher._validate_manifest_snapshot_schema(missing_playbook_hash)

    missing_summary_path = _schema_v2_manifest()
    del missing_summary_path["snapshots"]["summaries"][0]["path"]
    with pytest.raises(launcher.LaunchError, match="path and sha256"):
        launcher._validate_manifest_snapshot_schema(missing_summary_path)


def test_v1_manifest_retains_legacy_snapshot_read_behavior() -> None:
    launcher._validate_manifest_snapshot_schema(
        {"schema_version": 1, "snapshots": {"legacy": "shape"}}
    )


def test_v3_manifest_seals_exact_phase_six_submission_outputs(tmp_path: Path) -> None:
    manifest = _schema_v2_manifest()
    manifest["schema_version"] = 3
    manifest["phase_slug"] = launcher.PAPER_WRITING_PHASE
    manifest["output_root"] = str(tmp_path / "draft" / "run" / "01")
    manifest["paper_review"] = {"kind": "full"}
    paths = launcher._paper_manuscript_paths(manifest["output_root"])
    manifest["submission_outputs"] = {
        "post_review_manuscript": {
            "path": str(paths["post_review"]),
            "allow_empty": False,
        },
        "review_diff": {"path": str(paths["diff"]), "allow_empty": True},
    }

    launcher._validate_manifest_snapshot_schema(manifest)

    missing = dict(manifest)
    missing["submission_outputs"] = {
        "post_review_manuscript": manifest["submission_outputs"][
            "post_review_manuscript"
        ]
    }
    with pytest.raises(launcher.LaunchError, match="selected run variant"):
        launcher._validate_manifest_snapshot_schema(missing)

    escaped = json.loads(json.dumps(manifest))
    escaped["submission_outputs"]["review_diff"]["path"] = str(
        tmp_path / "other.diff"
    )
    with pytest.raises(launcher.LaunchError, match="does not match"):
        launcher._validate_manifest_snapshot_schema(escaped)


def test_v4_manifest_requires_decision_record_beside_summary(tmp_path: Path) -> None:
    manifest = _schema_v2_manifest()
    manifest.update({
        "schema_version": 4,
        "phase_slug": "01-literature",
        "submission_outputs": {},
        "summary_path": str(tmp_path / "phase-summaries" / "run.html"),
        "decision_path": str(tmp_path / "phase-summaries" / "run.decision.json"),
    })

    launcher._validate_manifest_snapshot_schema(manifest)

    missing = dict(manifest)
    missing.pop("decision_path")
    with pytest.raises(launcher.LaunchError, match="decision_path"):
        launcher._validate_manifest_snapshot_schema(missing)

    mismatched = dict(manifest)
    mismatched["decision_path"] = str(tmp_path / "other.json")
    with pytest.raises(launcher.LaunchError, match="beside the immutable summary"):
        launcher._validate_manifest_snapshot_schema(mismatched)


def test_v5_phase_four_manifest_requires_exact_protocol_checkpoint(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "project").resolve()
    output_root = project / "numerical" / "run" / "01"
    summary = project / "phase-summaries" / "04-numerical-validation" / "run.html"
    manifest = _schema_v2_manifest()
    manifest.update({
        "schema_version": 5,
        "project_dir": str(project),
        "phase_slug": launcher.NUMERICAL_VALIDATION_PHASE,
        "output_root": str(output_root),
        "submission_outputs": {},
        "summary_path": str(summary),
        "decision_path": str(summary.with_suffix(".decision.json")),
        "protocol_checkpoint": {
            "schema_version": (
                launcher.project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION
            ),
            "path": str(output_root / "protocol-checkpoint.json"),
            "max_bytes": launcher.project_state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        },
    })

    launcher._validate_manifest_snapshot_schema(manifest)

    for field, value, message in (
        ("path", str(output_root / "other.json"), "does not match"),
        ("schema_version", 99, "schema is invalid"),
        ("max_bytes", 1, "size policy is invalid"),
    ):
        invalid = json.loads(json.dumps(manifest))
        invalid["protocol_checkpoint"][field] = value
        with pytest.raises(launcher.LaunchError, match=message):
            launcher._validate_manifest_snapshot_schema(invalid)

    missing = dict(manifest)
    missing.pop("protocol_checkpoint")
    with pytest.raises(launcher.LaunchError, match="manifest schema"):
        launcher._validate_manifest_snapshot_schema(missing)

    extra = json.loads(json.dumps(manifest))
    extra["protocol_checkpoint"]["unexpected"] = True
    with pytest.raises(launcher.LaunchError, match="manifest schema"):
        launcher._validate_manifest_snapshot_schema(extra)

    other_phase = json.loads(json.dumps(manifest))
    other_phase["phase_slug"] = "01-literature"
    with pytest.raises(launcher.LaunchError, match="only for Phase 04"):
        launcher._validate_manifest_snapshot_schema(other_phase)

    legacy = dict(manifest)
    legacy["schema_version"] = 4
    legacy.pop("protocol_checkpoint")
    launcher._validate_manifest_snapshot_schema(legacy)


def test_v6_phase_four_manifest_fixes_a_run_scoped_protocol_directory(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "project").resolve()
    output_root = project / "numerical" / "run" / "01"
    summary = project / "phase-summaries" / "04-numerical-validation" / "run.html"
    manifest = _schema_v2_manifest()
    manifest.update({
        "schema_version": 6,
        "project_dir": str(project),
        "phase_slug": launcher.NUMERICAL_VALIDATION_PHASE,
        "output_root": str(output_root),
        "submission_outputs": {},
        "summary_path": str(summary),
        "decision_path": str(summary.with_suffix(".decision.json")),
        "protocol_checkpoint": {
            "schema_version": launcher.project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "path": str(output_root / "protocol-checkpoint.json"),
            "protocol_root": str(output_root / "protocol"),
            "max_bytes": launcher.project_state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        },
    })

    launcher._validate_manifest_snapshot_schema(manifest)

    missing = json.loads(json.dumps(manifest))
    missing["protocol_checkpoint"].pop("protocol_root")
    with pytest.raises(launcher.LaunchError, match="manifest schema"):
        launcher._validate_manifest_snapshot_schema(missing)

    escaped = json.loads(json.dumps(manifest))
    escaped["protocol_checkpoint"]["protocol_root"] = str(project.parent / "protocol")
    with pytest.raises(launcher.LaunchError, match="escaped"):
        launcher._validate_manifest_snapshot_schema(escaped)

def test_planned_roles_follow_the_frozen_phase_pattern() -> None:
    sequential = {
        "rounds_requested": 2,
        "phase": {
            "pattern": "sequential",
            "stages": [
                {"role": "theorist", "name": "Draft"},
                {"role": "research_lead", "name": "Audit"},
            ],
            "members": ["research_lead", "theorist"],
        },
    }
    parallel = {
        "rounds_requested": 3,
        "phase": {
            "pattern": "parallel",
            "members": ["data_scientist", "paper_reviewer"],
        },
    }

    assert launcher._planned_roles(sequential, 1) == ["theorist"]
    assert launcher._planned_roles(sequential, 2) == ["research_lead"]
    assert launcher._planned_roles(parallel, 1) == [
        "data_scientist",
        "paper_reviewer",
    ]
    assert launcher._planned_roles(parallel, 3) == [
        "data_scientist",
        "paper_reviewer",
    ]
    with pytest.raises(launcher.LaunchError, match="sequential stage"):
        launcher._planned_roles(sequential, 3)
    with pytest.raises(launcher.LaunchError, match="configured round"):
        launcher._planned_roles(parallel, 4)


def test_trusted_context_includes_baseline_and_optional_but_not_stale_nonself(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    phase_slugs = ["01-literature", "02-method", "03-data", "04-old-context"]
    run_ids = {slug: f"{index:08d}-approved" for index, slug in enumerate(phase_slugs, 1)}
    runs: dict[tuple[str, str], dict[str, object]] = {}
    phases: dict[str, dict[str, object]] = {}
    for slug in phase_slugs:
        summary = project / "summaries" / f"{slug}.html"
        summary.parent.mkdir(exist_ok=True)
        summary.write_text(f"<h1>{slug}</h1>", encoding="utf-8")
        run_id = run_ids[slug]
        runs[(slug, run_id)] = {
            "run_id": run_id,
            "status": "approved",
            "final_summary": summary.relative_to(project).as_posix(),
        }
        phases[slug] = {
            "approved_run": run_id,
            "stale": slug in {"02-method", "04-old-context"},
        }
    config = {
        "phases": [
            {"slug": "01-literature", "gated_by": []},
            {
                "slug": "02-method",
                "gated_by": ["01-literature"],
                "context_from": ["03-data", "04-old-context"],
            },
            {"slug": "03-data", "gated_by": []},
            {"slug": "04-old-context", "gated_by": []},
        ]
    }
    monkeypatch.setattr(
        launcher.project_state,
        "load",
        lambda _project: {"phases": phases},
    )
    monkeypatch.setattr(
        launcher.project_state,
        "get_run",
        lambda _project, phase, run_id: runs[(phase, run_id)],
    )
    monkeypatch.setattr(
        launcher.project_state,
        "run_integrity_report",
        lambda *_args: {"ok": True, "reason": ""},
    )

    context = launcher._trusted_context(project, "02-method", config)

    by_phase = {entry["phase"]: entry for entry in context}
    assert set(by_phase) == {"01-literature", "02-method", "03-data"}
    assert by_phase["01-literature"]["kind"] == "prerequisite"
    assert by_phase["03-data"]["kind"] == "optional_approved_context"
    assert by_phase["02-method"]["kind"] == "prior_phase_baseline"
    assert by_phase["02-method"]["trusted"] is False
    assert "04-old-context" not in by_phase
    for entry in context:
        summary = project / str(entry["summary"])
        assert entry["sha256"] == hashlib.sha256(summary.read_bytes()).hexdigest()


def test_context_snapshot_rejects_a_source_changed_during_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / "setting.md").write_text("project", encoding="utf-8")
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    (team_dir / "charter.md").write_text("charter", encoding="utf-8")
    (team_dir / "norms.md").write_text("norms", encoding="utf-8")
    souls_dir = tmp_path / "souls"
    souls_dir.mkdir()
    (souls_dir / "research_lead.md").write_text("lead soul", encoding="utf-8")
    (souls_dir / "theorist.md").write_text("theorist soul", encoding="utf-8")
    phases_dir = tmp_path / "phases"
    phase_dir = phases_dir / "02-method"
    phase_dir.mkdir(parents=True)
    for name in ("_lead.md", "_phase.md", "theorist.md"):
        (phase_dir / name).write_text(name, encoding="utf-8")
    source = project / "source.html"
    source.write_text("trusted context", encoding="utf-8")
    expected_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    original_write = launcher._write_bytes_atomic

    def change_before_write(path: Path, payload: bytes) -> None:
        if Path(path).name == "01-literature-approved-run.html":
            source.write_text("changed during copy", encoding="utf-8")
        original_write(path, payload)

    monkeypatch.setattr(launcher, "TEAM_DIR", team_dir)
    monkeypatch.setattr(launcher, "SOULS_DIR", souls_dir)
    monkeypatch.setattr(launcher, "PHASES_DIR", phases_dir)
    monkeypatch.setattr(launcher, "_write_bytes_atomic", change_before_write)

    with pytest.raises(launcher.LaunchError, match="changed while the run was being frozen"):
        launcher._snapshot_run_inputs(
            project,
            {"slug": "02-method", "members": ["theorist"]},
            "copy-race",
            [{
                "phase": "01-literature",
                "run_id": "approved-run",
                "summary": "source.html",
                "sha256": expected_digest,
            }],
        )


def test_snapshot_rejects_a_soul_changed_during_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / "setting.md").write_text("project", encoding="utf-8")
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    (team_dir / "charter.md").write_text("charter", encoding="utf-8")
    (team_dir / "norms.md").write_text("norms", encoding="utf-8")
    souls_dir = tmp_path / "souls"
    souls_dir.mkdir()
    lead_soul = souls_dir / "research_lead.md"
    lead_soul.write_text("lead soul before", encoding="utf-8")
    (souls_dir / "theorist.md").write_text("theorist soul", encoding="utf-8")
    phases_dir = tmp_path / "phases"
    phase_dir = phases_dir / "02-method"
    phase_dir.mkdir(parents=True)
    for name in ("_lead.md", "_phase.md", "theorist.md"):
        (phase_dir / name).write_text(name, encoding="utf-8")
    original_write = launcher._write_bytes_atomic

    def change_before_write(path: Path, payload: bytes) -> None:
        candidate = Path(path)
        if candidate.name == "research_lead.md" and candidate.parent.name == "souls":
            lead_soul.write_text("lead soul after", encoding="utf-8")
        original_write(path, payload)

    monkeypatch.setattr(launcher, "TEAM_DIR", team_dir)
    monkeypatch.setattr(launcher, "SOULS_DIR", souls_dir)
    monkeypatch.setattr(launcher, "PHASES_DIR", phases_dir)
    monkeypatch.setattr(launcher, "_write_bytes_atomic", change_before_write)

    with pytest.raises(launcher.LaunchError, match="changed while the run was being frozen"):
        launcher._snapshot_run_inputs(
            project,
            {"slug": "02-method", "members": ["theorist"]},
            "soul-copy-race",
            [],
        )


def test_snapshot_freezes_member_and_research_lead_souls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / "setting.md").write_text("project", encoding="utf-8")
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    (team_dir / "charter.md").write_text("charter", encoding="utf-8")
    (team_dir / "norms.md").write_text("norms", encoding="utf-8")
    souls_dir = tmp_path / "souls"
    souls_dir.mkdir()
    (souls_dir / "research_lead.md").write_text("lead soul", encoding="utf-8")
    (souls_dir / "theorist.md").write_text("theorist soul", encoding="utf-8")
    phases_dir = tmp_path / "phases"
    phase_dir = phases_dir / "02-method"
    phase_dir.mkdir(parents=True)
    for name in ("_lead.md", "_phase.md", "theorist.md"):
        (phase_dir / name).write_text(name, encoding="utf-8")
    monkeypatch.setattr(launcher, "TEAM_DIR", team_dir)
    monkeypatch.setattr(launcher, "SOULS_DIR", souls_dir)
    monkeypatch.setattr(launcher, "PHASES_DIR", phases_dir)

    snapshots = launcher._snapshot_run_inputs(
        project,
        {"slug": "02-method", "members": ["theorist"]},
        "soul-freeze",
        [],
    )

    assert set(snapshots["souls"]) == {"research_lead", "theorist"}
    assert Path(snapshots["souls"]["research_lead"]["path"]).read_text(
        encoding="utf-8"
    ) == "lead soul"
    assert Path(snapshots["souls"]["theorist"]["path"]).read_text(
        encoding="utf-8"
    ) == "theorist soul"
    for role in ("research_lead", "theorist"):
        frozen = Path(snapshots["souls"][role]["path"])
        assert snapshots["souls"][role]["sha256"] == hashlib.sha256(
            frozen.read_bytes()
        ).hexdigest()
    launcher._validate_manifest_snapshot_schema({
        "schema_version": 2,
        "phase": {"members": ["theorist"]},
        "snapshots": snapshots,
    })


def test_frozen_soul_text_rejects_post_snapshot_mutation(tmp_path: Path) -> None:
    soul = tmp_path / "theorist.md"
    soul.write_text("original soul", encoding="utf-8")
    snapshot = {
        "path": str(soul),
        "sha256": hashlib.sha256(soul.read_bytes()).hexdigest(),
    }
    soul.write_text("mutated soul", encoding="utf-8")

    with pytest.raises(launcher.LaunchError, match="changed after launch preparation"):
        launcher._frozen_snapshot_text(snapshot, "souls.theorist")


def test_frozen_soul_text_rejects_invalid_utf8_and_oversized_content(
    tmp_path: Path,
) -> None:
    soul = tmp_path / "theorist.md"
    soul.write_bytes(b"\xff")
    invalid_snapshot = {
        "path": str(soul),
        "sha256": hashlib.sha256(soul.read_bytes()).hexdigest(),
    }
    with pytest.raises(launcher.LaunchError, match="valid UTF-8"):
        launcher._frozen_snapshot_text(invalid_snapshot, "souls.theorist")

    soul.write_text("sixsix", encoding="utf-8")
    oversized_snapshot = {
        "path": str(soul),
        "sha256": hashlib.sha256(soul.read_bytes()).hexdigest(),
    }
    with pytest.raises(launcher.LaunchError, match="safety limit"):
        launcher._frozen_snapshot_text(
            oversized_snapshot, "souls.theorist", max_bytes=5
        )


def test_phase_six_reviewer_brief_seals_exact_review_manuscript(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "draft" / "run" / "01"
    output_root.mkdir(parents=True)
    manuscript = output_root / "manuscript-review.md"
    manuscript.write_text("# Paper\n\nExact reviewed text.\n", encoding="utf-8")
    digest = hashlib.sha256(manuscript.read_bytes()).hexdigest()
    manifest = {
        "phase_slug": "06-paper-writing",
        "output_root": str(output_root),
    }

    block = launcher._paper_review_manuscript_block(
        manifest, "paper_reviewer", tmp_path / "paper_reviewer.md"
    )

    assert "BEGIN SEALED REVIEW MANUSCRIPT" in block
    assert "Exact reviewed text." in block
    assert str(manuscript.resolve()) in block
    assert digest in block
    assert launcher._paper_review_manuscript_block(
        manifest, "theorist", tmp_path / "theorist.md"
    ) == ""


def test_phase_six_reviewer_requires_review_manuscript(tmp_path: Path) -> None:
    manifest = {
        "phase_slug": "06-paper-writing",
        "output_root": str(tmp_path / "draft" / "run" / "01"),
    }

    with pytest.raises(launcher.LaunchError, match="review manuscript is missing"):
        launcher._paper_review_manuscript_block(
            manifest, "paper_reviewer", tmp_path / "paper_reviewer.md"
        )


def test_review_copy_rejects_a_symlinked_destination_directory(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = project / "selected-manuscript.md"
    source.write_text("# Selected manuscript\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_parent = project / "draft"
    try:
        linked_parent.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available in this test environment")

    with pytest.raises(launcher.LaunchError, match="symbolic links"):
        launcher._copy_paper_review_source(
            project,
            source,
            linked_parent / "run" / "01" / "manuscript-review.md",
            hashlib.sha256(source.read_bytes()).hexdigest(),
        )

    assert not (outside / "run" / "01" / "manuscript-review.md").exists()


def test_phase_six_plan_variants_separate_review_substages() -> None:
    full = {
        "slug": launcher.PAPER_WRITING_PHASE,
        "members": ["research_lead", "theorist", "data_scientist", "paper_reviewer"],
        "stages": [
            {"role": "research_lead"},
            {"role": "theorist"},
            {"role": "data_scientist"},
            {"role": "paper_reviewer"},
            {"role": "paper_reviewer"},
        ],
    }
    manifest = {"phase_slug": launcher.PAPER_WRITING_PHASE, "phase": full}

    assert launcher._paper_reviewer_substage(manifest, 4) == "independent"
    assert launcher._paper_reviewer_substage(manifest, 5) == "contextual"
    review_only = launcher._paper_review_only_phase(full)
    assert review_only["members"] == ["paper_reviewer"]
    assert [stage["role"] for stage in review_only["stages"]] == [
        "paper_reviewer",
        "paper_reviewer",
    ]
    assert review_only["rounds"] == {"min": 2, "default": 2, "max": 2}


def test_exact_rerun_options_recovers_phase_three_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    manifest = {
        "phase": {
            "slug": launcher.THEORETICAL_ANALYSIS_PHASE,
            "run_plan": launcher.THEORY_PLAN_STANDARD_WITH_AUDIT,
        }
    }
    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)

    assert launcher.exact_rerun_options(
        project, launcher.THEORETICAL_ANALYSIS_PHASE, "prior-run"
    ) == {
        "kind": "theory",
        "theory_plan": launcher.THEORY_PLAN_STANDARD_WITH_AUDIT,
    }

    target_digest = "a" * 64
    manifest["phase"]["run_plan"] = launcher.THEORY_PLAN_AUDIT_ONLY
    frozen_source = {
        "run_id": "source-run",
        "target": {"sha256": target_digest},
    }
    monkeypatch.setattr(
        launcher,
        "_verified_frozen_theory_audit_source",
        lambda *_args: frozen_source,
    )
    monkeypatch.setattr(
        launcher,
        "_resolve_theory_audit_source",
        lambda *_args: {
            "run_id": "source-run",
            "target": {"sha256": target_digest},
        },
    )

    assert launcher.exact_rerun_options(
        project, launcher.THEORETICAL_ANALYSIS_PHASE, "prior-audit"
    ) == {
        "kind": "theory",
        "theory_plan": launcher.THEORY_PLAN_AUDIT_ONLY,
        "proof_audit_source_run_id": "source-run",
        "source_sha256": target_digest,
    }


def test_exact_audit_rerun_rejects_changed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(
        launcher,
        "_read_manifest",
        lambda *_args: {
            "phase": {
                "slug": launcher.THEORETICAL_ANALYSIS_PHASE,
                "run_plan": launcher.THEORY_PLAN_AUDIT_ONLY,
            }
        },
    )
    monkeypatch.setattr(
        launcher,
        "_verified_frozen_theory_audit_source",
        lambda *_args: {
            "run_id": "source-run",
            "target": {"sha256": "a" * 64},
        },
    )
    monkeypatch.setattr(
        launcher,
        "_resolve_theory_audit_source",
        lambda *_args: {"target": {"sha256": "b" * 64}},
    )

    with pytest.raises(launcher.LaunchError, match="source changed"):
        launcher.exact_rerun_options(
            project, launcher.THEORETICAL_ANALYSIS_PHASE, "prior-audit"
        )


def test_exact_rerun_options_recovers_review_only_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    source = project / "draft" / "run" / "01" / "manuscript-post-review.md"
    source.parent.mkdir(parents=True)
    source.write_text("manuscript", encoding="utf-8")
    digest = "c" * 64
    manifest = {
        "phase": {"slug": launcher.PAPER_WRITING_PHASE},
        "paper_review": {
            "kind": "review_only",
            "source_path": str(source),
            "source_sha256": digest,
        },
    }
    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(
        launcher,
        "_resolve_paper_review_source",
        lambda *_args: (source.resolve(), digest, {"run_id": "source-run"}),
    )

    assert launcher.exact_rerun_options(
        project, launcher.PAPER_WRITING_PHASE, "prior-review"
    ) == {
        "kind": "paper_review_only",
        "review_target": "draft/run/01/manuscript-post-review.md",
        "review_target_sha256": digest,
    }

    manifest["paper_review"] = {"kind": "full"}
    assert launcher.exact_rerun_options(
        project, launcher.PAPER_WRITING_PHASE, "prior-full"
    ) == {"kind": "paper_full"}


def test_phase_three_plan_variants_have_exact_user_selected_stages() -> None:
    phase = {
        "slug": launcher.THEORETICAL_ANALYSIS_PHASE,
        "members": ["theorist", "research_lead"],
        "available_run_plans": [
            launcher.THEORY_PLAN_STANDARD,
            launcher.THEORY_PLAN_STANDARD_WITH_AUDIT,
            launcher.THEORY_PLAN_AUDIT_ONLY,
        ],
        "stages": [
            {"role": "theorist"},
            {"role": "research_lead"},
            {"role": "theorist"},
        ],
        "rounds": {"min": 3, "default": 3, "max": 3},
    }

    standard = launcher._phase_for_theory_plan(
        phase, launcher.THEORY_PLAN_STANDARD
    )
    standard_with_audit = launcher._phase_for_theory_plan(
        phase, launcher.THEORY_PLAN_STANDARD_WITH_AUDIT
    )
    audit_only = launcher._phase_for_theory_plan(
        phase, launcher.THEORY_PLAN_AUDIT_ONLY
    )

    assert [stage["role"] for stage in standard["stages"]] == [
        "theorist",
        "research_lead",
        "theorist",
    ]
    assert standard["rounds"] == {"min": 3, "default": 3, "max": 3}
    assert standard["proof_audit"] is False
    assert [stage["role"] for stage in standard_with_audit["stages"]] == [
        "theorist",
        "research_lead",
        "theorist",
        "paper_reviewer",
    ]
    assert standard_with_audit["rounds"] == {
        "min": 4,
        "default": 4,
        "max": 4,
    }
    assert audit_only["members"] == ["paper_reviewer"]
    assert [stage["role"] for stage in audit_only["stages"]] == [
        "paper_reviewer"
    ]
    assert audit_only["rounds"] == {"min": 1, "default": 1, "max": 1}
    assert audit_only["audit_only"] is True


def test_phase_six_initial_reviewer_brief_excludes_internal_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    output_root = project / "draft" / "run" / "01"
    manuscript = output_root / "manuscript-review.md"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("# Paper\n\nReader-visible text.", encoding="utf-8")
    directive = output_root / ".directives" / "round-04.md"
    directive.parent.mkdir()
    directive.write_text("SECRET_INTERNAL_DIRECTIVE", encoding="utf-8")
    soul = tmp_path / "paper-reviewer-soul.md"
    soul.write_text("Read critically.", encoding="utf-8")
    protocol = tmp_path / "paper-reviewer.md"
    protocol.write_text("Record an independent first reading.", encoding="utf-8")
    manifest = {
        "run_id": "paper-run",
        "phase_slug": launcher.PAPER_WRITING_PHASE,
        "run_number": 1,
        "rounds_requested": 5,
        "phase": {
            "name": "Paper Writing",
            "pattern": "sequential",
            "folder": "draft",
            "members": ["paper_reviewer"],
            "stages": [
                {"role": "research_lead"},
                {"role": "theorist"},
                {"role": "data_scientist"},
                {"role": "paper_reviewer"},
                {"role": "paper_reviewer"},
            ],
        },
        "profiles": {"paper_reviewer": "review-profile"},
        "hermes_executable": "hermes",
        "board_slug": "paper-board",
        "timeout_minutes": 30,
        "user_feedback": "SECRET_USER_DIRECTION",
        "output_root": str(output_root),
        "snapshots": {
            "setting": {"path": "SECRET_PROJECT_BRIEF"},
            "team": {
                "charter": {"path": "SECRET_CHARTER"},
                "norms": {"path": "SECRET_NORMS"},
            },
            "souls": {
                "paper_reviewer": {
                    "path": str(soul),
                    "sha256": hashlib.sha256(soul.read_bytes()).hexdigest(),
                }
            },
            "playbooks": {
                "paper_reviewer.md": {
                    "path": str(protocol),
                    "sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
                }
            },
            "summaries": [{"phase": "05-analysis", "path": "SECRET_SUMMARY"}],
        },
    }
    run = {
        "run_id": "paper-run",
        "status": "running",
        "rounds": [
            {"n": 1, "completed": "now", "outputs": [], "artifacts": [], "tasks": []},
            {"n": 2, "completed": "now", "outputs": [], "artifacts": [], "tasks": []},
            {"n": 3, "completed": "now", "outputs": [], "artifacts": [], "tasks": []},
            {
                "n": 4,
                "completed": None,
                "agents": ["paper_reviewer"],
                "tasks": [],
                "lead_directive": "SECRET_INTERNAL_DIRECTIVE",
            },
        ],
    }
    recorded: dict[str, object] = {}
    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(launcher, "_verify_frozen_inputs", lambda *_args: None)
    monkeypatch.setattr(launcher.project_state, "get_run", lambda *_args: run)
    monkeypatch.setattr(launcher.project_state, "seal_review_target", lambda *_args: {})
    monkeypatch.setattr(
        launcher.project_state,
        "record_task",
        lambda *args, **kwargs: recorded.update(args=args, kwargs=kwargs),
    )
    commands: list[list[str]] = []

    def create_review_task(command, **_kwargs):
        commands.append(list(command))
        return _completed({"task": {"id": "review-task"}})

    monkeypatch.setattr(launcher, "_run_command", create_review_task)

    launcher._dispatch_task(
        project,
        launcher.PAPER_WRITING_PHASE,
        "paper-run",
        4,
        "paper_reviewer",
        directive,
    )

    brief = Path(recorded["kwargs"]["brief_path"]).read_text(encoding="utf-8")
    bundle_record = recorded["kwargs"]["review_bundle"]
    bundle_root = Path(bundle_record["root"])
    bundle = json.loads(Path(bundle_record["manifest_path"]).read_text(encoding="utf-8"))
    assert bundle["subtype"] == "independent_manuscript_reading"
    assert len(bundle["inputs"]) == 1
    assert (bundle_root / bundle["inputs"][0]["path"]).read_bytes() == manuscript.read_bytes()
    workspace_index = commands[0].index("--workspace") + 1
    assert commands[0][workspace_index] == f"dir:{bundle_root}"
    assert commands[0][workspace_index] != f"dir:{project}"
    assert "sealed-context reviewer task" in brief
    assert "`task.md`, `bundle.json`" in brief
    assert "Reader-visible text." not in brief
    for secret in (
        "SECRET_INTERNAL_DIRECTIVE",
        "SECRET_USER_DIRECTION",
        "SECRET_PROJECT_BRIEF",
        "SECRET_CHARTER",
        "SECRET_NORMS",
        "SECRET_SUMMARY",
    ):
        assert all(
            secret not in path.read_text(encoding="utf-8")
            for path in bundle_root.rglob("*")
            if path.is_file()
        )


def test_sealed_reviewer_report_is_verified_and_imported_without_overwrite(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    output_root = project / "draft" / "run" / "01"
    manuscript = output_root / "manuscript-review.md"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("# Exact manuscript\n", encoding="utf-8")
    digest = hashlib.sha256(manuscript.read_bytes()).hexdigest()
    manifest = {
        "phase_slug": launcher.PAPER_WRITING_PHASE,
        "run_id": "paper-run",
        "output_root": str(output_root),
        "user_feedback": "not authorized for the first reading",
    }
    run = {"run_id": "paper-run", "rounds": []}
    root, task_path, task_hash, bundle_record = launcher._prepare_review_bundle(
        project,
        manifest,
        run,
        1,
        reviewer_substage="independent",
        proof_audit_stage=False,
        review_snapshot=(
            manuscript.resolve(),
            manuscript.read_text(encoding="utf-8"),
            digest,
        ),
        soul_text="Read as a critical first-time reader.",
        soul_digest="a" * 64,
        protocol_text="Assess claims against the manuscript.",
        protocol_digest="b" * 64,
    )
    task = {
        "role": launcher.PAPER_REVIEWER_ROLE,
        "brief_path": str(task_path),
        "brief_sha256": task_hash,
        "review_bundle": bundle_record,
    }
    report = root / "output" / "report.md"
    report.write_text(
        "Scientific completion outcome: Complete\n\nIndependent assessment.\n",
        encoding="utf-8",
    )

    imported = launcher._import_review_bundle_output(project, manifest, task, 1)
    assert imported == launcher._planned_output(
        manifest, 1, launcher.PAPER_REVIEWER_ROLE
    ).resolve()
    assert imported.read_bytes() == report.read_bytes()
    assert launcher._import_review_bundle_output(project, manifest, task, 1) == imported

    imported.write_text("different preexisting content", encoding="utf-8")
    with pytest.raises(launcher.LaunchError, match="different content"):
        launcher._import_review_bundle_output(project, manifest, task, 1)


def test_changed_reviewer_bundle_input_blocks_report_import(tmp_path: Path) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    output_root = project / "draft" / "run" / "01"
    manuscript = output_root / "manuscript-review.md"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("# Exact manuscript\n", encoding="utf-8")
    digest = hashlib.sha256(manuscript.read_bytes()).hexdigest()
    manifest = {
        "phase_slug": launcher.PAPER_WRITING_PHASE,
        "run_id": "paper-run",
        "output_root": str(output_root),
    }
    root, task_path, task_hash, bundle_record = launcher._prepare_review_bundle(
        project,
        manifest,
        {"run_id": "paper-run", "rounds": []},
        1,
        reviewer_substage="independent",
        proof_audit_stage=False,
        review_snapshot=(manuscript.resolve(), "# Exact manuscript\n", digest),
        soul_text="Review independently.",
        soul_digest="a" * 64,
        protocol_text="Check the manuscript.",
        protocol_digest="b" * 64,
    )
    bundle = json.loads(Path(bundle_record["manifest_path"]).read_text(encoding="utf-8"))
    (root / bundle["inputs"][0]["path"]).write_text("tampered", encoding="utf-8")
    (root / "output" / "report.md").write_text("valid report", encoding="utf-8")
    task = {
        "role": launcher.PAPER_REVIEWER_ROLE,
        "brief_path": str(task_path),
        "brief_sha256": task_hash,
        "review_bundle": bundle_record,
    }

    with pytest.raises(launcher.LaunchError, match="input changed"):
        launcher._import_review_bundle_output(project, manifest, task, 1)


def test_review_source_must_belong_to_recorded_phase_six_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    source = project / "draft" / "run" / "03" / "manuscript-post-review.md"
    source.parent.mkdir(parents=True)
    source.write_text("selected manuscript", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    submission, _summary, _decision = _source_submission(
        project, launcher.PAPER_WRITING_PHASE, "paper-run"
    )
    recorded = {
        **submission,
        "submission_artifacts": {
            "post_review_manuscript": {
                "path": source.relative_to(project).as_posix(),
                "sha256": digest,
                "size": len(source.read_bytes()),
            }
        },
    }
    monkeypatch.setattr(
        launcher.project_state,
        "get_runs",
        lambda *_args: [recorded],
    )
    monkeypatch.setattr(
        launcher,
        "_read_manifest",
        lambda *_args: {
            "phase_slug": launcher.PAPER_WRITING_PHASE,
            "run_id": "paper-run",
            "output_root": str(source.parent),
            "paper_review": {"kind": "full"},
        },
    )
    monkeypatch.setattr(
        launcher.project_state,
        "run_integrity_report",
        lambda *_args: {"ok": True, "reason": ""},
    )

    resolved, resolved_digest, source_baseline = launcher._resolve_paper_review_source(
        project, source.relative_to(project), digest
    )
    assert resolved == source.resolve()
    assert resolved_digest == digest
    assert source_baseline["run_id"] == "paper-run"
    assert source_baseline["source_baseline_status"] == "accepted"

    arbitrary = project / "notes" / "manuscript-post-review.md"
    arbitrary.parent.mkdir()
    arbitrary.write_text("not a recorded output", encoding="utf-8")
    with pytest.raises(launcher.LaunchError, match="not a sealed post-review output"):
        launcher._resolve_paper_review_source(
            project,
            arbitrary,
            hashlib.sha256(arbitrary.read_bytes()).hexdigest(),
        )


def test_source_baseline_requires_eligible_submitted_integrity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = (tmp_path / "project").resolve()
    failed, _summary, _decision = _source_submission(
        project, launcher.PAPER_WRITING_PHASE, "failed-run", status="failed"
    )
    with pytest.raises(launcher.LaunchError, match="status is not eligible"):
        launcher._source_baseline_from_run(
            project, launcher.PAPER_WRITING_PHASE, failed
        )

    historical, _summary, _decision = _source_submission(
        project,
        launcher.PAPER_WRITING_PHASE,
        "historical-run",
        status="superseded",
    )
    monkeypatch.setattr(
        launcher.project_state,
        "run_integrity_report",
        lambda *_args: {"ok": True, "reason": ""},
    )
    baseline = launcher._source_baseline_from_run(
        project, launcher.PAPER_WRITING_PHASE, historical
    )
    assert baseline["source_baseline_status"] == "historical"

    monkeypatch.setattr(
        launcher.project_state,
        "run_integrity_report",
        lambda *_args: {"ok": False, "reason": "sealed summary changed"},
    )
    with pytest.raises(launcher.LaunchError, match="sealed summary changed"):
        launcher._source_baseline_from_run(
            project, launcher.PAPER_WRITING_PHASE, historical
        )


def test_audit_only_source_is_resolved_from_sealed_run_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = (tmp_path / "project").resolve()
    output_root = project / "draft" / "theory" / "run" / "01"
    initial = output_root / "round-01" / "theorist.md"
    lead = output_root / "round-02" / "research_lead.md"
    final = output_root / "round-03" / "theorist.md"
    for path, text in (
        (initial, "Initial proof plan."),
        (lead, "Prefer the central theorem."),
        (final, "# Final theory\n\nExact theorem and proof."),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    records = {
        path: {
            "path": path.relative_to(project).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": len(path.read_bytes()),
        }
        for path in (initial, lead, final)
    }
    manifest = {
        "phase_slug": launcher.THEORETICAL_ANALYSIS_PHASE,
        "run_id": "opaque-source-id",
        "output_root": str(output_root),
        "phase": {
            "pattern": "sequential",
            "stages": [
                {"role": "theorist"},
                {"role": "research_lead"},
                {"role": "theorist"},
            ],
        },
        "snapshots": {"summaries": []},
    }
    submission, _summary, _decision = _source_submission(
        project,
        launcher.THEORETICAL_ANALYSIS_PHASE,
        "opaque-source-id",
        status="revision_requested",
    )
    source_run = {
        **submission,
        "rounds": [
            {"n": 1, "completed": "now", "artifacts": [records[initial]]},
            {"n": 2, "completed": "now", "artifacts": [records[lead]]},
            {"n": 3, "completed": "now", "artifacts": [records[final]]},
        ],
    }
    seen: list[str] = []

    def get_run(_project: Path, phase_slug: str, run_id: str) -> dict:
        assert phase_slug == launcher.THEORETICAL_ANALYSIS_PHASE
        seen.append(run_id)
        return source_run

    monkeypatch.setattr(launcher.project_state, "get_run", get_run)
    monkeypatch.setattr(
        launcher.project_state,
        "run_integrity_report",
        lambda *_args: {"ok": True, "reason": ""},
    )
    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(launcher, "_verify_frozen_inputs", lambda *_args: None)

    source = launcher._resolve_theory_audit_source(
        project, "opaque-source-id"
    )

    assert seen == ["opaque-source-id"]
    assert source["target"]["source_path"] == records[final]["path"]
    assert source["target"]["sha256"] == records[final]["sha256"]
    assert source["source_baseline"]["source_baseline_status"] == "proposed"
    assert [item["source"] for item in source["evidence"]] == [
        initial.resolve()
    ]
    assert all(item["source"] != lead.resolve() for item in source["evidence"])

    final.write_text("Changed after sealing.", encoding="utf-8")
    with pytest.raises(launcher.LaunchError, match="changed before bundling"):
        launcher._resolve_theory_audit_source(project, "opaque-source-id")


def test_audit_only_bundle_uses_frozen_target_without_lead_preference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    source_target = project / "source-theory.md"
    source_evidence = project / "source-evidence.md"
    lead_preference = project / "lead-preference.html"
    source_target.write_text("Final theorem and proof.", encoding="utf-8")
    source_evidence.write_text("Earlier mathematical derivation.", encoding="utf-8")
    lead_preference.write_text("Preferred conclusion.", encoding="utf-8")
    run_id = "audit-only-run"
    launcher.run_context_dir(
        project, launcher.THEORETICAL_ANALYSIS_PHASE, run_id
    ).mkdir(parents=True)
    submission, source_summary, source_decision = _source_submission(
        project, launcher.THEORETICAL_ANALYSIS_PHASE, "opaque-source-id"
    )
    monkeypatch.setattr(
        launcher.project_state,
        "run_integrity_report",
        lambda *_args: {"ok": True, "reason": ""},
    )
    source_baseline = launcher._source_baseline_from_run(
        project, launcher.THEORETICAL_ANALYSIS_PHASE, submission
    )
    source = {
        "run_id": "opaque-source-id",
        "target": {
            "source": source_target,
            "source_path": "draft/theory/run/01/round-03/theorist.md",
            "source_round": 3,
            "source_role": "theorist",
            "sha256": hashlib.sha256(source_target.read_bytes()).hexdigest(),
            "size": len(source_target.read_bytes()),
            "purpose": "Exact final theoretical analysis selected for audit",
        },
        "evidence": [{
            "source": source_evidence,
            "sha256": hashlib.sha256(source_evidence.read_bytes()).hexdigest(),
            "size": len(source_evidence.read_bytes()),
            "purpose": "Sealed theorist report from source round 1",
        }],
        "source_baseline": source_baseline,
    }
    frozen = launcher._freeze_theory_audit_source(project, run_id, source)
    assert frozen["source_baseline"]["source_baseline_status"] == "accepted"
    assert Path(frozen["source_baseline"]["summary"]["path"]).read_bytes() == (
        source_summary.read_bytes()
    )
    assert Path(
        frozen["source_baseline"]["decision_record"]["path"]
    ).read_bytes() == source_decision.read_bytes()
    manifest = {
        "run_id": run_id,
        "phase_slug": launcher.THEORETICAL_ANALYSIS_PHASE,
        "phase": {
            "audit_only": True,
            "proof_audit": True,
            "stages": [{"role": "paper_reviewer"}],
        },
        "proof_audit_source": frozen,
        "snapshots": {
            "summaries": [{
                "path": str(lead_preference),
                "sha256": hashlib.sha256(lead_preference.read_bytes()).hexdigest(),
                "phase": launcher.THEORETICAL_ANALYSIS_PHASE,
            }]
        },
    }

    subtype, sources = launcher._review_bundle_sources(
        project,
        manifest,
        {"rounds": [{"n": 1, "artifacts": []}]},
        1,
        reviewer_substage=None,
        proof_audit_stage=True,
        review_snapshot=None,
    )

    assert subtype == "proof_audit"
    assert [path["source"].read_text(encoding="utf-8") for path in sources] == [
        "Final theorem and proof.",
        "Earlier mathematical derivation.",
    ]
    assert all(path["source"] != lead_preference for path in sources)
    assert all(path["source"] not in {source_summary, source_decision} for path in sources)
    frozen_baseline_paths = {
        Path(frozen["source_baseline"]["summary"]["path"]).resolve(),
        Path(frozen["source_baseline"]["decision_record"]["path"]).resolve(),
    }
    assert all(path["source"] not in frozen_baseline_paths for path in sources)


def test_review_only_baseline_is_hidden_from_first_read_and_added_contextually(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = (tmp_path / "project").resolve()
    run_id = "review-only-run"
    context = launcher.run_context_dir(
        project, launcher.PAPER_WRITING_PHASE, run_id
    )
    context.mkdir(parents=True)
    source_run, _summary, _decision = _source_submission(
        project,
        launcher.PAPER_WRITING_PHASE,
        "superseded-source",
        status="superseded",
    )
    monkeypatch.setattr(
        launcher.project_state,
        "run_integrity_report",
        lambda *_args: {"ok": True, "reason": ""},
    )
    source_baseline = launcher._source_baseline_from_run(
        project, launcher.PAPER_WRITING_PHASE, source_run
    )
    frozen = launcher._freeze_source_baseline(
        project,
        context / "paper-review" / "source-baseline",
        source_baseline,
    )
    lead_block = launcher._source_baseline_lead_block(frozen)
    assert "every unaffected material statement and its stable statement ID" in lead_block
    assert "historical, not as the current accepted result" in lead_block
    manuscript = project / "draft" / "run" / "02" / "manuscript-review.md"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("# Exact manuscript\n", encoding="utf-8")
    manuscript_digest = hashlib.sha256(manuscript.read_bytes()).hexdigest()
    first_read = project / "draft" / "run" / "02" / "round-01" / "paper_reviewer.md"
    first_read.parent.mkdir()
    first_read.write_text("Independent first reading.", encoding="utf-8")
    first_read_digest = hashlib.sha256(first_read.read_bytes()).hexdigest()
    manifest = {
        "run_id": run_id,
        "phase_slug": launcher.PAPER_WRITING_PHASE,
        "phase": {
            "stages": [
                {"role": launcher.PAPER_REVIEWER_ROLE},
                {"role": launcher.PAPER_REVIEWER_ROLE},
            ]
        },
        "paper_review": {
            "schema_version": 2,
            "kind": "review_only",
            "source_baseline": frozen,
        },
        "snapshots": {"team": {}, "summaries": []},
    }
    run = {
        "rounds": [{
            "n": 1,
            "completed": "now",
            "artifacts": [{
                "path": first_read.relative_to(project).as_posix(),
                "sha256": first_read_digest,
                "size": len(first_read.read_bytes()),
            }],
        }]
    }
    review_snapshot = (
        manuscript.resolve(),
        manuscript.read_text(encoding="utf-8"),
        manuscript_digest,
    )

    _, independent_sources = launcher._review_bundle_sources(
        project,
        manifest,
        run,
        1,
        reviewer_substage="independent",
        proof_audit_stage=False,
        review_snapshot=review_snapshot,
    )
    assert [item["source"] for item in independent_sources] == [manuscript.resolve()]

    _, contextual_sources = launcher._review_bundle_sources(
        project,
        manifest,
        run,
        2,
        reviewer_substage="contextual",
        proof_audit_stage=False,
        review_snapshot=review_snapshot,
    )
    contextual_paths = {item["source"] for item in contextual_sources}
    assert Path(frozen["summary"]["path"]).resolve() in contextual_paths
    assert Path(frozen["decision_record"]["path"]).resolve() in contextual_paths
    assert first_read.resolve() in contextual_paths
    assert any("historical structured source record" in item["purpose"] for item in contextual_sources)


def test_proof_audit_block_seals_final_theory_and_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    target = project / "draft" / "theory" / "run" / "01" / "round-03" / "theorist.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Theorem\n\nThe central proof.", encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    earlier_theory = target.parents[1] / "round-01" / "theorist.md"
    earlier_theory.parent.mkdir()
    earlier_theory.write_text("Initial assumptions and proof plan.", encoding="utf-8")
    earlier_digest = hashlib.sha256(earlier_theory.read_bytes()).hexdigest()
    prior = target.parents[1] / "round-02" / "research_lead.md"
    prior.parent.mkdir()
    prior.write_text("Check the central lemma.", encoding="utf-8")
    prior_digest = hashlib.sha256(prior.read_bytes()).hexdigest()
    summary_path = project / "frozen-phase-02.html"
    summary_digest = "a" * 64
    phase = launcher._phase_with_proof_audit(
        {
            "slug": launcher.THEORETICAL_ANALYSIS_PHASE,
            "folder": "draft/theory",
            "members": ["theorist", "research_lead"],
            "stages": [
                {"role": "theorist"},
                {"role": "research_lead"},
                {"role": "theorist"},
            ],
        }
    )
    manifest = {
        "phase_slug": launcher.THEORETICAL_ANALYSIS_PHASE,
        "output_root": str(target.parents[1]),
        "phase": phase,
        "snapshots": {
            "summaries": [
                {
                    "path": str(summary_path),
                    "phase": "02-method-development",
                    "sha256": summary_digest,
                }
            ]
        },
    }
    run = {
        "rounds": [
            {
                "n": 1,
                "completed": "now",
                "artifacts": [
                    {
                        "path": earlier_theory.relative_to(project).as_posix(),
                        "sha256": earlier_digest,
                        "size": len(earlier_theory.read_bytes()),
                    }
                ],
            },
            {
                "n": 2,
                "completed": "now",
                "artifacts": [
                    {
                        "path": prior.relative_to(project).as_posix(),
                        "sha256": prior_digest,
                        "size": len(prior.read_bytes()),
                    }
                ],
            },
            {
                "n": 3,
                "completed": "now",
                "artifacts": [
                    {
                        "path": target.relative_to(project).as_posix(),
                        "sha256": digest,
                        "size": len(target.read_bytes()),
                    }
                ],
            },
        ]
    }

    block = launcher._proof_audit_material_block(project, manifest, run, 4)

    assert "BEGIN SEALED FINAL THEORY ARTIFACT" in block
    assert "The central proof." in block
    assert digest in block
    assert str(earlier_theory) in block
    assert earlier_digest in block
    assert prior_digest not in block
    assert "research_lead.md" not in block
    assert "Check the central lemma." not in block
    assert str(summary_path) in block
    assert summary_digest in block
    assert "02-method-development" in block


def test_proof_audit_task_receives_sealed_scope_and_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = (tmp_path / "project").resolve()
    target = project / "draft" / "theory" / "run" / "01" / "round-03" / "theorist.md"
    target.parent.mkdir(parents=True)
    target.write_text("# STMT-1\n\nProof text.", encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    output_root = target.parents[1]
    directive = output_root / ".directives" / "round-04.md"
    directive.parent.mkdir()
    directive.write_text("Audit STMT-1 and its central lemma.", encoding="utf-8")
    soul = tmp_path / "reviewer-soul.md"
    soul.write_text("Check proofs independently.", encoding="utf-8")
    protocol = tmp_path / "proof-audit.md"
    protocol.write_text("Reconstruct the dependency graph.", encoding="utf-8")
    charter = tmp_path / "charter.md"
    charter.write_text("Maintain independent scientific judgment.", encoding="utf-8")
    norms = tmp_path / "norms.md"
    norms.write_text("Check each claim against sealed evidence.", encoding="utf-8")
    phase = launcher._phase_with_proof_audit(
        {
            "slug": launcher.THEORETICAL_ANALYSIS_PHASE,
            "name": "Theoretical Analysis",
            "pattern": "sequential",
            "folder": "draft/theory",
            "members": ["theorist", "research_lead"],
            "stages": [
                {"role": "theorist"},
                {"role": "research_lead"},
                {"role": "theorist"},
            ],
        }
    )
    manifest = {
        "run_id": "theory-run",
        "phase_slug": launcher.THEORETICAL_ANALYSIS_PHASE,
        "run_number": 1,
        "rounds_requested": 4,
        "phase": phase,
        "profiles": {"paper_reviewer": "review-profile"},
        "hermes_executable": "hermes",
        "board_slug": "theory-board",
        "timeout_minutes": 30,
        "user_feedback": "User selected STMT-1 for audit.",
        "output_root": str(output_root),
        "snapshots": {
            "setting": {"path": str(tmp_path / "setting.md")},
            "team": {
                "charter": {
                    "path": str(charter),
                    "sha256": hashlib.sha256(charter.read_bytes()).hexdigest(),
                },
                "norms": {
                    "path": str(norms),
                    "sha256": hashlib.sha256(norms.read_bytes()).hexdigest(),
                },
            },
            "souls": {
                "paper_reviewer": {
                    "path": str(soul),
                    "sha256": hashlib.sha256(soul.read_bytes()).hexdigest(),
                }
            },
            "playbooks": {
                "paper_reviewer.md": {
                    "path": str(protocol),
                    "sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
                }
            },
            "summaries": [],
        },
    }
    run = {
        "run_id": "theory-run",
        "status": "running",
        "rounds": [
            {"n": 1, "completed": "now", "outputs": [], "artifacts": [], "tasks": []},
            {"n": 2, "completed": "now", "outputs": [], "artifacts": [], "tasks": []},
            {
                "n": 3,
                "completed": "now",
                "outputs": [target.relative_to(project).as_posix()],
                "artifacts": [
                    {
                        "path": target.relative_to(project).as_posix(),
                        "sha256": digest,
                        "size": len(target.read_bytes()),
                    }
                ],
                "tasks": [],
            },
            {
                "n": 4,
                "completed": None,
                "agents": ["paper_reviewer"],
                "tasks": [],
                "lead_directive": "Audit STMT-1 and its central lemma.",
            },
        ],
    }
    recorded: dict[str, object] = {}
    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(launcher, "_verify_frozen_inputs", lambda *_args: None)
    monkeypatch.setattr(launcher.project_state, "get_run", lambda *_args: run)
    monkeypatch.setattr(
        launcher.project_state,
        "record_task",
        lambda *args, **kwargs: recorded.update(args=args, kwargs=kwargs),
    )
    monkeypatch.setattr(
        launcher,
        "_run_command",
        lambda *_args, **_kwargs: _completed({"task": {"id": "audit-task"}}),
    )

    launcher._dispatch_task(
        project,
        launcher.THEORETICAL_ANALYSIS_PHASE,
        "theory-run",
        4,
        "paper_reviewer",
        directive,
    )

    brief = Path(recorded["kwargs"]["brief_path"]).read_text(encoding="utf-8")
    assert "User selected STMT-1 for audit." in brief
    assert "Prespecified audit scope" in brief
    assert "Audit STMT-1 and its central lemma." in brief
    bundle_record = recorded["kwargs"]["review_bundle"]
    bundle_root = Path(bundle_record["root"])
    bundle = json.loads(Path(bundle_record["manifest_path"]).read_text(encoding="utf-8"))
    assert bundle["subtype"] == "proof_audit"
    assert any(
        (bundle_root / item["path"]).read_bytes() == target.read_bytes()
        and item["sha256"] == digest
        for item in bundle["inputs"]
    )


def test_lead_prompt_embeds_frozen_research_lead_soul(tmp_path: Path) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    lead_soul = tmp_path / "research_lead.md"
    lead_soul.write_text("Lead with the research question.", encoding="utf-8")
    lead_digest = hashlib.sha256(lead_soul.read_bytes()).hexdigest()
    snapshots = {
        "setting": {"path": str(tmp_path / "setting.md")},
        "team": {
            "charter": {"path": str(tmp_path / "charter.md")},
            "norms": {"path": str(tmp_path / "norms.md")},
        },
        "souls": {
            "research_lead": {"path": str(lead_soul), "sha256": lead_digest}
        },
        "playbooks": {
            "_lead.md": {"path": str(tmp_path / "_lead.md")},
            "_phase.md": {"path": str(tmp_path / "_phase.md")},
        },
        "summaries": [],
    }
    phase = {
        "slug": "06-paper-writing",
        "name": "Paper Writing",
        "pattern": "sequential",
        "folder": "draft",
        "members": ["research_lead"],
        "stages": [
            {
                "role": "research_lead",
                "name": "Frame",
                "description": "Frame the paper.",
            }
        ],
    }

    prompt = launcher._build_lead_prompt(
        project,
        phase,
        {"research_lead": "lead-profile"},
        "board",
        "run-id",
        1,
        1,
        "",
        {"blockers": []},
        snapshots,
        project / "phase-summaries" / "06-paper-writing" / "run-id.html",
    )

    assert "Lead with the research question." in prompt
    assert lead_digest in prompt
    assert str(lead_soul) in prompt
    assert prompt.index("BEGIN FROZEN RESEARCH LEAD SOUL") < prompt.index(
        "## Read before dispatching"
    )
    assert str(project / "draft" / "run" / "01" / "manuscript-review.md") in prompt
    assert str(
        project / "draft" / "run" / "01" / "manuscript-post-review.md"
    ) in prompt
    assert str(
        project / "draft" / "run" / "01" / "manuscript-post-review.diff"
    ) in prompt
    assert "copy the review\nmanuscript byte for byte" in prompt
    assert "write an empty diff" in prompt
    assert "run-id.decision.json" in prompt
    assert '"scientific_outcome": "Complete"' in prompt
    decision_example = json.loads(
        prompt.split("```json\n", 1)[1].split("\n```", 1)[0]
    )
    launcher.project_state.validate_decision_record(decision_example)
    assert decision_example["scientific_record_changes"][0]["proposed_values"] == {
        "statement_type": "Empirical statement",
        "wording": "State one material scientific statement exactly.",
        "scope": "State the population, regime, or conditions covered.",
        "formulation_state": "Proposed",
        "assessment_status": "Untested",
        "evidential_basis": [
            "Name the supporting theorem, calculation, numerical result, or source."
        ],
        "source_provenance": ["Identify the exact project path or external source."],
        "assumptions": ["State the assumptions needed for this statement."],
        "uncertainty": ["State the material uncertainty or limitation."],
        "logical_status": "Not applicable",
        "mathematical_result_type": "Not applicable",
    }
    assert "--decision-record" in prompt
    assert "The scientific outcome describes completion" in prompt


def test_completed_round_artifact_is_revalidated_before_a_later_round(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    artifact = project / "round-01.md"
    artifact.write_text("original evidence", encoding="utf-8")
    original = artifact.read_bytes()
    run = {
        "rounds": [{
            "n": 1,
            "completed": "2026-07-20T00:00:00Z",
            "outputs": ["round-01.md"],
            "artifacts": [{
                "path": "round-01.md",
                "sha256": hashlib.sha256(original).hexdigest(),
                "size": len(original),
            }],
        }],
    }
    artifact.write_text("changed evidence", encoding="utf-8")

    with pytest.raises(launcher.LaunchError, match="changed after completion"):
        launcher._verify_completed_round_artifacts(project, run, before_round=2)


def test_dispatch_task_builds_full_context_and_records_exact_task_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    frozen_dir = project / "frozen"
    frozen_dir.mkdir()
    theorist_soul = frozen_dir / "theorist-soul.md"
    theorist_soul.write_text(
        "Name every assumption and its role.", encoding="utf-8"
    )
    theorist_soul_digest = hashlib.sha256(theorist_soul.read_bytes()).hexdigest()
    phase_slug = "02-method"
    run_id = "12345678-run"
    output_root = project / "method" / "run" / "01"
    directive = output_root / ".directives" / "round-02.md"
    directive.parent.mkdir(parents=True)
    directive.write_text("Stress-test the estimator under misspecification.", encoding="utf-8")
    prior_output = output_root / "round-01" / "theorist.md"
    prior_output.parent.mkdir(parents=True)
    prior_output.write_text("prior round evidence", encoding="utf-8")
    manifest = {
        "run_id": run_id,
        "phase_slug": phase_slug,
        "rounds_requested": 2,
            "phase": {
                "name": "Method Development",
                "pattern": "parallel",
                "folder": "method",
                "members": ["theorist"],
            },
            "run_number": 1,
        "profiles": {"theorist": "theory-profile"},
        "hermes_executable": "hermes",
        "board_slug": "project-board",
        "timeout_minutes": 45,
        "user_feedback": "Prioritize robustness over novelty.",
        "output_root": str(output_root),
        "snapshots": {
            "setting": {"path": str(project / "frozen" / "setting.md")},
            "team": {
                "charter": {"path": str(project / "frozen" / "charter.md")},
                "norms": {"path": str(project / "frozen" / "norms.md")},
            },
            "souls": {
                "theorist": {
                    "path": str(theorist_soul),
                    "sha256": theorist_soul_digest,
                },
            },
            "playbooks": {
                "theorist.md": {"path": str(project / "frozen" / "theorist.md")},
            },
            "summaries": [
                {
                    "phase": "01-literature",
                    "run_id": "lit-approved",
                    "path": str(project / "frozen" / "literature.html"),
                    "trusted": True,
                },
                {
                    "phase": phase_slug,
                    "run_id": "method-prior",
                    "path": str(project / "frozen" / "method-prior.html"),
                    "trusted": False,
                },
            ],
        },
    }
    run = {
        "run_id": run_id,
        "status": "running",
        "rounds": [
            {
                "n": 1,
                "agents": ["theorist"],
                "tasks": [{"role": "theorist", "task_id": "prior-task"}],
                "outputs": ["method/run/01/round-01/theorist.md"],
                "artifacts": [{
                    "path": "method/run/01/round-01/theorist.md",
                    "sha256": hashlib.sha256(prior_output.read_bytes()).hexdigest(),
                    "size": len(prior_output.read_bytes()),
                }],
                "completed": "2026-07-20T00:00:00Z",
            },
            {
                "n": 2,
                "agents": ["theorist"],
                "tasks": [],
                "outputs": [],
                "completed": None,
                "lead_directive": "Stress-test the estimator under misspecification.",
            },
        ],
    }
    recorded: dict[str, object] = {}
    commands: list[list[str]] = []

    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(launcher, "_verify_frozen_inputs", lambda *_args: None)
    monkeypatch.setattr(launcher.project_state, "get_run", lambda *_args: run)

    def record_task(*args, **kwargs) -> None:
        recorded["args"] = args
        recorded["kwargs"] = kwargs

    def run_command(arguments, **_kwargs):
        commands.append(list(arguments))
        return _completed({"task": {"id": "hermes-task-409"}})

    monkeypatch.setattr(launcher.project_state, "record_task", record_task)
    monkeypatch.setattr(launcher, "_run_command", run_command)

    task_id = launcher._dispatch_task(
        project,
        phase_slug,
        run_id,
        2,
        "theorist",
        directive,
    )

    assert task_id == "hermes-task-409"
    assert recorded["args"] == (project, phase_slug, run_id, 2)
    assert recorded["kwargs"]["task_id"] == "hermes-task-409"
    assert recorded["kwargs"]["role"] == "theorist"
    command = commands[0]
    assert command[:4] == ["hermes", "kanban", "--board", "project-board"]
    assert command[command.index("--assignee") + 1] == "theory-profile"
    assert command[command.index("--idempotency-key") + 1] == (
        f"research-hub:{run_id}:2:theorist"
    )
    body = command[command.index("--body") + 1]
    brief_path = Path(recorded["kwargs"]["brief_path"])
    brief = brief_path.read_text(encoding="utf-8")
    assert str(brief_path) in body
    assert recorded["kwargs"]["brief_sha256"] in body
    assert len(subprocess.list2cmdline(command)) < 30_000
    assert "Prioritize robustness over novelty." in brief
    assert "Stress-test the estimator under misspecification." in brief
    assert str(project / "frozen" / "setting.md") in brief
    assert str(project / "frozen" / "charter.md") in brief
    assert str(project / "frozen" / "norms.md") in brief
    assert str(project / "frozen" / "theorist.md") in brief
    assert str(theorist_soul) in brief
    assert "Name every assumption and its role." in brief
    assert theorist_soul_digest in brief
    assert "01-literature run lit-approved (trusted current input)" in brief
    assert "02-method run method-prior (historical baseline)" in brief
    assert str(project / "method" / "run" / "01" / "round-01" / "theorist.md") in brief
    assert str(output_root / "round-02" / "theorist.md") in brief


def test_dispatch_archives_a_created_task_when_state_recording_loses_a_race(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    theorist_soul = project / "theorist-soul.md"
    theorist_soul.write_text("theorist soul", encoding="utf-8")
    theorist_soul_digest = hashlib.sha256(theorist_soul.read_bytes()).hexdigest()
    phase_slug = "02-method"
    run_id = "record-race"
    output_root = project / "method" / "run" / "01"
    directive = output_root / ".directives" / "round-01.md"
    directive.parent.mkdir(parents=True)
    directive.write_text("Develop the method.", encoding="utf-8")
    manifest = {
        "run_id": run_id,
        "phase_slug": phase_slug,
        "rounds_requested": 1,
        "phase": {
            "name": "Method Development",
            "pattern": "parallel",
            "folder": "method",
            "members": ["theorist"],
        },
        "profiles": {"theorist": "theory-profile"},
        "hermes_executable": "hermes",
        "board_slug": "project-board",
        "timeout_minutes": 45,
        "user_feedback": "",
        "output_root": str(output_root),
        "snapshots": {
            "setting": {"path": str(project / "setting.md")},
            "team": {
                "charter": {"path": str(project / "charter.md")},
                "norms": {"path": str(project / "norms.md")},
            },
            "souls": {
                "theorist": {
                    "path": str(theorist_soul),
                    "sha256": theorist_soul_digest,
                },
            },
            "playbooks": {
                "theorist.md": {"path": str(project / "theorist.md")},
            },
            "summaries": [],
        },
    }
    run = {
        "run_id": run_id,
        "status": "running",
        "rounds": [{
            "n": 1,
            "agents": ["theorist"],
            "tasks": [],
            "outputs": [],
            "completed": None,
            "lead_directive": "Develop the method.",
        }],
    }
    archived: list[str] = []

    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(launcher, "_verify_frozen_inputs", lambda *_args: None)
    monkeypatch.setattr(launcher.project_state, "get_run", lambda *_args: run)
    monkeypatch.setattr(
        launcher.project_state,
        "record_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            launcher.project_state.StateConflict("state recording race")
        ),
    )
    monkeypatch.setattr(
        launcher,
        "_run_command",
        lambda *_args, **_kwargs: _completed({"task": {"id": "orphan-task"}}),
    )
    monkeypatch.setattr(
        launcher,
        "_archive_external_task",
        lambda _manifest, task_id: archived.append(task_id) or None,
    )

    with pytest.raises(launcher.project_state.StateConflict, match="recording race"):
        launcher._dispatch_task(
            project,
            phase_slug,
            run_id,
            1,
            "theorist",
            directive,
        )
    assert archived == ["orphan-task"]


def test_complete_round_requires_done_tasks_and_exact_planned_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    phase_slug = "05-analysis"
    run_id = "87654321-run"
    output_root = project / "analysis" / "run" / "01"
    manifest = {
        "run_id": run_id,
        "rounds_requested": 1,
        "output_root": str(output_root),
        "phase": {
            "pattern": "parallel",
            "members": ["data_scientist", "paper_reviewer"],
        },
    }
    brief_root = launcher.project_state.state_dir(project) / "runs" / phase_slug
    brief_root.mkdir(parents=True)
    data_brief = brief_root / "data.task.md"
    review_brief = brief_root / "review.task.md"
    data_brief.write_text("data task", encoding="utf-8")
    review_brief.write_text("review task", encoding="utf-8")
    run = {
        "run_id": run_id,
        "status": "running",
        "rounds": [
            {
                "n": 1,
                "agents": ["data_scientist", "paper_reviewer"],
                "tasks": [
                    {
                        "role": "data_scientist",
                        "task_id": "task-data",
                        "brief_path": str(data_brief),
                        "brief_sha256": hashlib.sha256(data_brief.read_bytes()).hexdigest(),
                    },
                    {
                        "role": "paper_reviewer",
                        "task_id": "task-review",
                        "brief_path": str(review_brief),
                        "brief_sha256": hashlib.sha256(review_brief.read_bytes()).hexdigest(),
                    },
                ],
            }
        ],
    }
    expected = [
        output_root / "round-01" / "data_scientist.md",
        output_root / "round-01" / "paper_reviewer.md",
    ]
    completed: list[tuple] = []
    statuses = {"task-data": "done", "task-review": "running"}

    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(launcher, "_verify_frozen_inputs", lambda *_args: None)
    monkeypatch.setattr(launcher.project_state, "get_run", lambda *_args: run)
    monkeypatch.setattr(
        launcher,
        "_show_task",
        lambda _manifest, task_id: {"status": statuses[task_id]},
    )
    monkeypatch.setattr(
        launcher.project_state,
        "complete_round",
        lambda *args: completed.append(args),
    )

    with pytest.raises(launcher.LaunchError, match="not done"):
        launcher._complete_round_checked(
            project, phase_slug, run_id, 1, expected
        )
    assert completed == []

    statuses["task-review"] = "done"
    with pytest.raises(launcher.LaunchError, match="frozen role output plan"):
        launcher._complete_round_checked(
            project, phase_slug, run_id, 1, [expected[0], project / "wrong.md"]
        )
    assert completed == []

    launcher._complete_round_checked(project, phase_slug, run_id, 1, expected)
    assert completed == [(project, phase_slug, run_id, 1, expected)]


def test_reconciliation_preserves_a_racing_terminal_state_before_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    phase_slug = "03-theory"
    run_id = "race-run"
    active = {"phase_slug": phase_slug, "run_id": run_id}
    terminal = {"status": "awaiting_review"}
    active_reads = iter([active, None])
    begin_calls: list[tuple] = []
    cleanup_calls: list[tuple] = []

    monkeypatch.setattr(
        launcher.project_state,
        "get_active_run",
        lambda _project: next(active_reads),
    )
    monkeypatch.setattr(
        launcher.project_state,
        "get_run",
        lambda *_args: {
            "status": "running",
            "started": datetime.now(timezone.utc).isoformat(),
            "process_pid": 4242,
        },
    )
    monkeypatch.setattr(
        launcher,
        "_load_hub_config",
        lambda: {"hub": {"run_timeout_minutes": 120}},
    )
    monkeypatch.setattr(launcher, "_pid_is_alive", lambda _pid, _identity=None: False)

    def begin_cleanup(*args, **kwargs) -> bool:
        begin_calls.append((args, kwargs))
        # Model a concurrent successful submission that won the state lock.
        assert terminal["status"] == "awaiting_review"
        return False

    monkeypatch.setattr(
        launcher.project_state,
        "begin_run_cleanup",
        begin_cleanup,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "finalize_run_cleanup",
        lambda *_args, **_kwargs: pytest.fail("cleanup must not finalize after losing the race"),
    )
    monkeypatch.setattr(
        launcher,
        "_stop_external_tasks",
        lambda *args, **kwargs: cleanup_calls.append((args, kwargs)),
    )

    result = launcher.reconcile_active_run(project)

    assert result is None
    assert terminal["status"] == "awaiting_review"
    assert len(begin_calls) == 1
    assert begin_calls[0][1]["expected_pid"] == 4242
    assert cleanup_calls == []


def test_reconciliation_preserves_an_active_run_when_identity_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    phase_slug = "03-theory"
    run_id = "identity-unavailable-run"
    active = {"phase_slug": phase_slug, "run_id": run_id}

    monkeypatch.setattr(
        launcher.project_state,
        "get_active_run",
        lambda _project: active,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "get_run",
        lambda *_args: {
            "status": "running",
            "started": datetime.now(timezone.utc).isoformat(),
            "process_pid": 4243,
            "process_identity": "recorded-worker-4243",
        },
    )
    monkeypatch.setattr(
        launcher,
        "_load_hub_config",
        lambda: {"hub": {"run_timeout_minutes": 120}},
    )
    monkeypatch.setattr(launcher.os, "kill", lambda _pid, _signal: None)
    monkeypatch.setattr(launcher, "_process_identity", lambda _pid: None)
    monkeypatch.setattr(
        launcher.project_state,
        "begin_run_cleanup",
        lambda *_args, **_kwargs: pytest.fail(
            "identity uncertainty must not begin cleanup"
        ),
    )
    monkeypatch.setattr(
        launcher,
        "_stop_external_tasks",
        lambda *_args, **_kwargs: pytest.fail(
            "identity uncertainty must not archive external tasks"
        ),
    )

    assert launcher.reconcile_active_run(project) == active


def test_cleanup_does_not_kill_an_unverified_legacy_pid_or_release_the_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    finalize_calls: list[tuple] = []

    monkeypatch.setattr(
        launcher.project_state,
        "begin_run_cleanup",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "get_run",
        lambda *_args: {"process_pid": 9191, "process_identity": None},
    )
    monkeypatch.setattr(
        launcher,
        "_terminate_pid_tree",
        lambda *_args, **_kwargs: pytest.fail("an unverified PID must not be terminated"),
    )
    monkeypatch.setattr(launcher, "_pid_is_alive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(launcher, "_stop_external_tasks", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        launcher.project_state,
        "finalize_run_cleanup",
        lambda *args, **kwargs: finalize_calls.append((args, kwargs)) or True,
    )

    began, warnings = launcher._cleanup_run_execution(
        project,
        "01-literature",
        "legacy-run",
        outcome="cancelled",
        reason="user requested cancellation",
        terminate_worker=True,
    )

    assert began is True
    assert any("unverified legacy process PID 9191" in warning for warning in warnings)
    assert finalize_calls == []


def test_cleanup_does_not_archive_tasks_when_process_identity_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    archived: list[tuple] = []

    monkeypatch.setattr(
        launcher.project_state,
        "begin_run_cleanup",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "get_run",
        lambda *_args: {
            "process_pid": 9194,
            "process_identity": "recorded-worker-9194",
        },
    )
    monkeypatch.setattr(launcher, "_pid_is_alive", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(launcher, "_process_identity", lambda _pid: None)
    monkeypatch.setattr(
        launcher,
        "_terminate_pid_tree",
        lambda *_args, **_kwargs: pytest.fail(
            "a PID with unverifiable identity must not be terminated"
        ),
    )
    monkeypatch.setattr(
        launcher,
        "_stop_external_tasks",
        lambda *args, **kwargs: archived.append((args, kwargs)) or [],
    )
    monkeypatch.setattr(
        launcher.project_state,
        "finalize_run_cleanup",
        lambda *_args, **_kwargs: pytest.fail(
            "identity uncertainty must keep cleanup pending"
        ),
    )

    began, warnings = launcher._cleanup_run_execution(
        project,
        "01-literature",
        "identity-unavailable-run",
        outcome="cancelled",
        reason="user requested cancellation",
        terminate_worker=True,
    )

    assert began is True
    assert any("Could not verify the recorded identity" in item for item in warnings)
    assert archived == []


def test_cleanup_releases_legacy_pid_lease_when_the_process_is_gone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    finalize_calls: list[tuple] = []

    monkeypatch.setattr(
        launcher.project_state,
        "begin_run_cleanup",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "get_run",
        lambda *_args: {"process_pid": 9192, "process_identity": None},
    )
    monkeypatch.setattr(launcher, "_pid_is_alive", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        launcher,
        "_terminate_pid_tree",
        lambda *_args, **_kwargs: pytest.fail("a dead PID must not be terminated"),
    )
    monkeypatch.setattr(launcher, "_stop_external_tasks", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        launcher.project_state,
        "finalize_run_cleanup",
        lambda *args, **kwargs: finalize_calls.append((args, kwargs)) or True,
    )

    began, warnings = launcher._cleanup_run_execution(
        project,
        "01-literature",
        "legacy-run",
        outcome="cancelled",
        reason="user requested cancellation",
        terminate_worker=True,
    )

    assert began is True
    assert warnings == []
    assert len(finalize_calls) == 1


def test_retry_run_cleanup_finalizes_the_exact_stopping_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    launcher.project_state.init(
        project,
        "project-001",
        "project",
        "Project",
        phase_slugs=["01-literature"],
        dependencies={"01-literature": []},
    )
    run_id = launcher.project_state.reserve_run(project, "01-literature", "retry cleanup")
    launcher.project_state.set_process_pid(
        project,
        "01-literature",
        run_id,
        9193,
        process_identity="worker-9193",
    )
    launcher.project_state.begin_run_cleanup(
        project,
        "01-literature",
        run_id,
        "cancelled",
        "User requested cancellation.",
        expected_pid=9193,
    )
    monkeypatch.setattr(launcher, "_pid_is_alive", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(launcher, "_stop_external_tasks", lambda *_args, **_kwargs: [])

    result = launcher.retry_run_cleanup(project, "01-literature", run_id)

    assert result["run_id"] == run_id
    assert result["status"] == "cancelled"
    assert launcher.project_state.get_active_run(project) is None


def test_phase_four_round_one_task_receives_exact_pre_result_checkpoint_command(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "project").resolve()
    checkpoint = project / "numerical" / "run" / "01" / "protocol-checkpoint.json"
    protocol_root = checkpoint.parent / "protocol"
    manifest = {
        "schema_version": 6,
        "phase_slug": launcher.NUMERICAL_VALIDATION_PHASE,
        "run_id": "phase-four-run",
        "protocol_checkpoint": {
            "schema_version": (
                launcher.project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION
            ),
            "path": str(checkpoint),
            "protocol_root": str(protocol_root),
            "max_bytes": launcher.project_state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        },
    }

    block = launcher._phase_four_protocol_checkpoint_block(
        project, manifest, {}, 1, "data_scientist", "protocol"
    )

    assert "Mandatory Phase 04 protocol checkpoint" in block
    assert str(checkpoint) in block
    assert '"main_results_generated": false' in block
    assert '"protocol_files"' in block
    assert "protocol-seal" in block
    assert str(protocol_root) in block
    assert block.index("protocol-seal") < block.index("finish this protocol-only task")
    assert "Do not generate any main result" in block
    assert launcher._phase_four_protocol_checkpoint_block(
        project, manifest, {}, 3, "data_scientist", "protocol"
    ) == ""
    assert launcher._phase_four_protocol_checkpoint_block(
        project, manifest, {}, 1, "theorist", "standard"
    ) == ""


def test_later_phase_four_tasks_receive_the_verified_protocol_identity(
    tmp_path: Path,
) -> None:
    project = (tmp_path / "project").resolve()
    checkpoint = project / "numerical" / "run" / "01" / "protocol-checkpoint.json"
    protocol_root = checkpoint.parent / "protocol"
    protocol_path = protocol_root / "study-design.yaml"
    manifest = {
        "schema_version": 6,
        "phase_slug": launcher.NUMERICAL_VALIDATION_PHASE,
        "run_id": "phase-four-run",
        "protocol_checkpoint": {
            "schema_version": (
                launcher.project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION
            ),
            "path": str(checkpoint),
            "protocol_root": str(protocol_root),
            "max_bytes": launcher.project_state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        },
    }
    run = {
        "protocol_checkpoint": {
            "path": checkpoint.relative_to(project).as_posix(),
            "sha256": "a" * 64,
            "sealed_at": "2026-07-20T00:00:00Z",
            "data": {
                "protocol_files": [{
                    "path": protocol_path.relative_to(project).as_posix(),
                    "sha256": "b" * 64,
                    "size": 512,
                    "purpose": "Fix the study regimes and primary metric.",
                }]
            },
        }
    }

    block = launcher._phase_four_protocol_checkpoint_block(
        project, manifest, run, 2, "theorist", "standard"
    )

    assert "Mechanically verified prespecification boundary" in block
    assert checkpoint.relative_to(project).as_posix() in block
    assert "a" * 64 in block
    assert protocol_path.relative_to(project).as_posix() in block
    assert "b" * 64 in block
    assert "512 bytes" in block
    assert "sealed design and protocol" in block


def test_phase_four_dispatch_isolates_protocol_then_seals_before_results(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    output_root = project / "numerical" / "run" / "01"
    protocol_root = output_root / "protocol"
    checkpoint = protocol_root / "protocol-checkpoint.json"
    directive = output_root / ".directives" / "round-01.md"
    directive.parent.mkdir(parents=True)
    directive.write_text("Prespecify the study, then generate results.", encoding="utf-8")
    soul = project / "data-scientist-soul.md"
    soul.write_text("Prespecify the numerical study.", encoding="utf-8")
    playbook = project / "phase-data-scientist.md"
    playbook.write_text("Separate design from result generation.", encoding="utf-8")
    soul_digest = hashlib.sha256(soul.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 8,
        "run_id": "phase-four-run",
        "phase_slug": launcher.NUMERICAL_VALIDATION_PHASE,
        "run_number": 1,
        "rounds_requested": 1,
        "phase": {
            "name": "Numerical Validation",
            "pattern": "parallel",
            "folder": "numerical",
            "members": ["data_scientist"],
        },
        "profiles": {"data_scientist": "data-profile"},
        "hermes_executable": "hermes",
        "board_slug": "numerical-board",
        "timeout_minutes": 30,
        "user_feedback": "Keep design and analysis separate.",
        "output_root": str(output_root),
        "protocol_checkpoint": {
            "schema_version": (
                launcher.project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION
            ),
            "path": str(checkpoint),
            "protocol_root": str(protocol_root),
            "max_bytes": launcher.project_state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        },
        "method_selection": {
            "kind": "method",
            "stable_id": "adaptive-score-test",
            "version": "v1.2",
            "source": "run_specific_user_selection",
            "source_phase": None,
            "source_run_id": None,
            "decision_record": None,
        },
        "snapshots": {
            "setting": {"path": str(project / "setting.md")},
            "team": {
                "charter": {"path": str(project / "charter.md")},
                "norms": {"path": str(project / "norms.md")},
            },
            "souls": {
                "data_scientist": {
                    "path": str(soul),
                    "sha256": soul_digest,
                }
            },
            "playbooks": {
                "data_scientist.md": {"path": str(playbook)},
            },
            "summaries": [],
        },
    }
    run = {
        "run_id": "phase-four-run",
        "status": "running",
        "rounds": [{
            "n": 1,
            "agents": ["data_scientist"],
            "tasks": [],
            "outputs": [],
            "completed": None,
            "lead_directive": "Prespecify the study, then generate results.",
        }],
    }
    created_commands: list[list[str]] = []
    seal_calls: list[tuple[Path, str, str, str, bool]] = []

    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(launcher, "_verify_frozen_inputs", lambda *_args: None)
    monkeypatch.setattr(launcher.project_state, "get_run", lambda *_args: run)

    def record_task(*_args, **kwargs) -> None:
        run["rounds"][0]["tasks"].append({
            "task_id": kwargs["task_id"],
            "role": kwargs["role"],
            "task_kind": kwargs["task_kind"],
            "brief_path": str(kwargs["brief_path"]),
            "brief_sha256": kwargs["brief_sha256"],
            "workspace_path": str(kwargs["workspace_path"]),
        })

    def run_command(arguments, **_kwargs):
        command = list(arguments)
        if "show" in command:
            return _completed({"task": {"status": "done"}})
        created_commands.append(command)
        task_id = "protocol-task" if len(created_commands) == 1 else "result-task"
        return _completed({"task": {"id": task_id}})

    def seal_protocol(
        root: Path,
        phase: str,
        run_id: str,
        checkpoint_path: str,
        *,
        isolated_task_completed: bool = False,
    ) -> dict[str, object]:
        seal_calls.append(
            (root, phase, run_id, checkpoint_path, isolated_task_completed)
        )
        record = {
            "path": checkpoint.relative_to(project).as_posix(),
            "sha256": "a" * 64,
            "sealed_at": "2026-07-20T00:00:00Z",
            "data": {
                "protocol_files": [{
                    "path": (protocol_root / "study-design.yaml")
                    .relative_to(project)
                    .as_posix(),
                    "sha256": "b" * 64,
                    "size": 512,
                    "purpose": "Fix the numerical design before result generation.",
                }]
            },
        }
        run["protocol_checkpoint"] = record
        return record

    monkeypatch.setattr(launcher.project_state, "record_task", record_task)
    monkeypatch.setattr(launcher, "_run_command", run_command)
    monkeypatch.setattr(
        launcher.project_state, "seal_protocol_checkpoint", seal_protocol
    )
    monkeypatch.setattr(
        launcher.project_state,
        "require_protocol_checkpoint",
        lambda *_args: run["protocol_checkpoint"],
    )

    protocol_task = launcher._dispatch_task(
        project,
        launcher.NUMERICAL_VALIDATION_PHASE,
        "phase-four-run",
        1,
        "data_scientist",
        directive,
        "protocol",
    )
    result_task = launcher._dispatch_task(
        project,
        launcher.NUMERICAL_VALIDATION_PHASE,
        "phase-four-run",
        1,
        "data_scientist",
        directive,
        "result",
    )

    assert protocol_task == "protocol-task"
    assert result_task == "result-task"
    assert created_commands[0][created_commands[0].index("--workspace") + 1] == (
        f"dir:{protocol_root}"
    )
    result_workspace = output_root / "round-01"
    assert created_commands[1][created_commands[1].index("--workspace") + 1] == (
        f"dir:{result_workspace}"
    )
    assert seal_calls == [(
        project,
        launcher.NUMERICAL_VALIDATION_PHASE,
        "phase-four-run",
        str(checkpoint),
        True,
    )]
    protocol_brief = Path(run["rounds"][0]["tasks"][0]["brief_path"])
    result_brief = Path(run["rounds"][0]["tasks"][1]["brief_path"])
    assert protocol_brief.is_file()
    assert result_brief.is_file()
    assert "protocol-only task" in protocol_brief.read_text(encoding="utf-8")
    assert "Mechanically verified prespecification boundary" in (
        result_brief.read_text(encoding="utf-8")
    )


def test_protocol_seal_cli_verifies_manifest_and_delegates_exact_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = (tmp_path / "project").resolve()
    checkpoint = project / "numerical" / "run" / "01" / "protocol-checkpoint.json"
    manifest = {"run_id": "run-04", "phase_slug": launcher.NUMERICAL_VALIDATION_PHASE}
    verified: list[tuple[Path, str, str, object]] = []
    sealed: list[tuple[Path, str, str, str]] = []
    monkeypatch.setattr(
        launcher.project_state,
        "get_run",
        lambda *_args: {"run_id": "run-04"},
    )
    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(
        launcher,
        "_verify_frozen_inputs",
        lambda root, phase, run_id, frozen: verified.append(
            (root, phase, run_id, frozen)
        ),
    )

    def seal(root: Path, phase: str, run_id: str, path: str) -> dict[str, object]:
        sealed.append((root, phase, run_id, path))
        return {
            "sealed_at": "2026-07-20T00:00:00Z",
            "sha256": "a" * 64,
            "data": {"protocol_files": [{"path": "protocol.yaml"}]},
        }

    monkeypatch.setattr(launcher.project_state, "seal_protocol_checkpoint", seal)

    result = launcher.main([
        "protocol-seal",
        "--project-dir",
        str(project),
        "--phase",
        launcher.NUMERICAL_VALIDATION_PHASE,
        "--run-id",
        "run-04",
        "--checkpoint",
        str(checkpoint),
    ])

    assert result == 0
    assert verified == [
        (project, launcher.NUMERICAL_VALIDATION_PHASE, "run-04", manifest)
    ]
    assert sealed == [
        (
            project,
            launcher.NUMERICAL_VALIDATION_PHASE,
            "run-04",
            str(checkpoint),
        )
    ]
    output = capsys.readouterr().out
    assert "1 file" in output
    assert "Main-result work may begin" in output


def test_public_cli_does_not_expose_unsealed_task_recording() -> None:
    assert "record-task" not in launcher._build_parser().format_help()


def test_run_command_rejects_output_above_its_combined_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(launcher, "MAX_COMMAND_OUTPUT_BYTES", 1_024)

    with pytest.raises(
        launcher._ProcessOutputLimitExceeded,
        match="output exceeded the 1,024-byte safety limit",
    ):
        launcher._run_command(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'x' * 4096); sys.stdout.flush()",
            ]
        )


def test_process_timeout_terminates_descendants_holding_output_pipes() -> None:
    child_code = "import time; time.sleep(20)"
    parent_code = (
        "import subprocess, sys, time\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "print(child.pid, flush=True)\n"
        "time.sleep(20)\n"
    )
    started = time.monotonic()

    with pytest.raises(subprocess.TimeoutExpired) as caught:
        launcher._run_process_with_bounded_output(
            [sys.executable, "-c", parent_code],
            timeout=0.5,
            max_output_bytes=1_024,
        )

    assert time.monotonic() - started < 10
    child_pid = int(str(caught.value.output).strip().splitlines()[0])
    deadline = time.monotonic() + 5
    while launcher._pid_is_alive(child_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not launcher._pid_is_alive(child_pid)


def test_process_output_overflow_terminates_descendants(
    tmp_path: Path,
) -> None:
    child_pid_path = tmp_path / "child.pid"
    gate_path = tmp_path / "emit-output"
    child_code = (
        "import sys, time\n"
        "from pathlib import Path\n"
        f"gate = Path({str(gate_path)!r})\n"
        "while not gate.exists():\n"
        "    time.sleep(0.01)\n"
        "sys.stdout.buffer.write(b'x' * 65536)\n"
        "sys.stdout.flush()\n"
        "time.sleep(20)\n"
    )
    parent_code = (
        "import subprocess, sys, time\n"
        "from pathlib import Path\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        f"Path({str(child_pid_path)!r}).write_text(str(child.pid), encoding='ascii')\n"
        f"Path({str(gate_path)!r}).write_text('go', encoding='ascii')\n"
        "time.sleep(20)\n"
    )
    started = time.monotonic()

    with pytest.raises(launcher._ProcessOutputLimitExceeded):
        launcher._run_process_with_bounded_output(
            [sys.executable, "-c", parent_code],
            timeout=10,
            max_output_bytes=1_024,
        )

    assert time.monotonic() - started < 10
    child_pid = int(child_pid_path.read_text(encoding="ascii"))
    deadline = time.monotonic() + 5
    while launcher._pid_is_alive(child_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not launcher._pid_is_alive(child_pid)


def test_logged_command_stops_at_the_remaining_run_log_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    phase_slug = "01-literature"
    run_id = "bounded-log"
    log_path = launcher.run_log_path(project, phase_slug, run_id)
    log_path.parent.mkdir(parents=True)
    prefix = b"existing log\n"
    log_path.write_bytes(prefix)
    monkeypatch.setattr(launcher, "MAX_RUN_LOG_BYTES", 2_048)
    with log_path.open("ab", buffering=0) as log_handle:
        descriptor = log_handle.fileno()
        monkeypatch.setattr(
            launcher, "_worker_log_descriptor", lambda: descriptor
        )

        def write_output(payload: bytes, *, descriptor: int | None = None) -> None:
            assert descriptor == log_handle.fileno()
            log_handle.write(payload)

        monkeypatch.setattr(launcher, "_write_worker_output", write_output)
        with pytest.raises(
            launcher._ProcessOutputLimitExceeded,
            match="run-log safety limit",
        ):
            launcher._run_logged_command(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.buffer.write(b'x' * 8192); sys.stdout.flush()",
                ],
                timeout=10,
                project_dir=project,
                phase_slug=phase_slug,
                run_id=run_id,
            )

    payload = log_path.read_bytes()
    assert payload.endswith(launcher.RUN_LOG_LIMIT_MARKER)
    assert len(payload) == launcher.MAX_RUN_LOG_BYTES


def test_run_log_is_truncated_to_its_persistent_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_path = tmp_path / "run.log"
    log_path.write_bytes(b"x" * 1_024)
    monkeypatch.setattr(launcher, "MAX_RUN_LOG_BYTES", 256)

    with log_path.open("r+b", buffering=0) as log_handle:
        launcher._truncate_run_log(log_path, descriptor=log_handle.fileno())

    payload = log_path.read_bytes()
    assert len(payload) == 256
    assert payload.endswith(launcher.RUN_LOG_LIMIT_MARKER)


@pytest.mark.parametrize("path_state", ["missing", "replacement"])
def test_run_log_cap_uses_the_bound_descriptor_when_its_path_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path_state: str,
) -> None:
    inherited_path = tmp_path / "inherited-run.log"
    inherited_path.write_bytes(b"x" * 1_024)
    named_path = tmp_path / "run.log"
    replacement = b"replacement must remain unchanged\n"
    if path_state == "replacement":
        named_path.write_bytes(replacement)
    monkeypatch.setattr(launcher, "MAX_RUN_LOG_BYTES", 256)

    with inherited_path.open("r+b", buffering=0) as log_handle:
        with pytest.raises(
            launcher.LaunchError,
            match="no longer identifies the inherited worker output",
        ):
            launcher._truncate_run_log(
                named_path,
                descriptor=log_handle.fileno(),
            )

    inherited = inherited_path.read_bytes()
    assert len(inherited) == launcher.MAX_RUN_LOG_BYTES
    assert inherited.endswith(launcher.RUN_LOG_LIMIT_MARKER)
    if path_state == "replacement":
        assert named_path.read_bytes() == replacement
    else:
        assert not named_path.exists()


def test_logged_command_rejects_a_path_replacement_before_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    log_path = launcher.run_log_path(project, "01-literature", "replaced-log")
    log_path.parent.mkdir(parents=True)
    log_path.write_bytes(b"replacement\n")
    inherited_path = tmp_path / "original-run.log"
    inherited_path.write_bytes(b"original\n")
    monkeypatch.setattr(
        launcher,
        "_run_process_with_bounded_output",
        lambda *_args, **_kwargs: pytest.fail("a mismatched log must fail before execution"),
    )

    with inherited_path.open("ab", buffering=0) as log_handle:
        monkeypatch.setattr(
            launcher,
            "_worker_log_descriptor",
            lambda: log_handle.fileno(),
        )
        with pytest.raises(
            launcher.LaunchError,
            match="no longer identifies the inherited worker output",
        ):
            launcher._run_logged_command(
                [sys.executable, "-c", "print('must not run')"],
                timeout=10,
                project_dir=project,
                phase_slug="01-literature",
                run_id="replaced-log",
            )

    assert inherited_path.read_bytes() == b"original\n"
    assert log_path.read_bytes() == b"replacement\n"


def test_worker_cli_caps_the_log_after_recording_an_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    phase_slug = "01-literature"
    run_id = "worker-error"
    log_path = launcher.run_log_path(project, phase_slug, run_id)
    log_path.parent.mkdir(parents=True)
    log_path.write_bytes(b"x" * 1_024)
    monkeypatch.setattr(launcher, "MAX_RUN_LOG_BYTES", 256)
    monkeypatch.setattr(
        launcher,
        "_worker",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            launcher.LaunchError("worker failed")
        ),
    )

    with log_path.open("a", encoding="utf-8", buffering=1) as log_handle:
        monkeypatch.setattr(launcher.sys, "stdout", log_handle)
        monkeypatch.setattr(launcher.sys, "stderr", log_handle)
        result = launcher.main([
            "worker",
            "--project-dir",
            str(project),
            "--phase",
            phase_slug,
            "--run-id",
            run_id,
            "--manifest",
            str(tmp_path / "unused-manifest.json"),
        ])

    payload = log_path.read_bytes()
    assert result == 1
    assert len(payload) == launcher.MAX_RUN_LOG_BYTES
    assert payload.endswith(launcher.RUN_LOG_LIMIT_MARKER)


def test_new_run_log_is_created_exclusively_and_never_reuses_a_path(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "run.log"
    with launcher._open_new_run_log(log_path) as handle:
        handle.write("worker started\n")

    assert log_path.read_text(encoding="utf-8") == "worker started\n"
    with pytest.raises(launcher.LaunchError, match="refusing to reuse"):
        launcher._open_new_run_log(log_path)
    assert log_path.read_text(encoding="utf-8") == "worker started\n"


def test_worker_passes_a_short_bootstrap_instead_of_the_full_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    phase_slug = "01-literature"
    run_id = "worker-run"
    manifest_file = launcher.run_manifest_path(project, phase_slug, run_id)
    manifest_file.parent.mkdir(parents=True)
    prompt_file = launcher.prompt_path(project, phase_slug, run_id)
    unique_prompt_text = "FULL_PROMPT_SENTINEL\n" + ("research evidence\n" * 20_000)
    prompt_file.write_text(unique_prompt_text, encoding="utf-8")
    manifest = {
        "hermes_executable": "hermes",
        "lead_profile": "lead-profile",
        "timeout_minutes": 1,
        "prompt_path": str(prompt_file),
        "prompt_sha256": hashlib.sha256(prompt_file.read_bytes()).hexdigest(),
    }
    commands: list[list[str]] = []
    pid_calls: list[tuple] = []
    failure_calls: list[tuple] = []

    monkeypatch.setattr(
        launcher,
        "run_manifest_path",
        lambda *_args: manifest_file,
    )
    monkeypatch.setattr(launcher, "_read_manifest", lambda *_args: manifest)
    monkeypatch.setattr(launcher, "_verify_frozen_inputs", lambda *_args: None)
    monkeypatch.setattr(launcher, "_process_identity", lambda _pid: "test-process")
    monkeypatch.setattr(
        launcher.project_state,
        "set_process_pid",
        lambda *args, **kwargs: pid_calls.append((args, kwargs)),
    )

    def run_command(arguments, **_kwargs):
        commands.append(list(arguments))
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(launcher, "_run_logged_command", run_command)
    monkeypatch.setattr(
        launcher.project_state,
        "fail_run_if_active",
        lambda *args, **kwargs: failure_calls.append((args, kwargs)) or False,
    )
    monkeypatch.setattr(
        launcher.project_state,
        "finalize_run_submission",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        launcher,
        "_stop_external_tasks",
        lambda *_args, **_kwargs: pytest.fail("terminal cleanup should not run"),
    )

    result = launcher._worker(
        str(project), phase_slug, run_id, str(manifest_file)
    )

    assert result == 0
    assert len(pid_calls) == 1
    assert len(commands) == 1
    command = commands[0]
    bootstrap = command[command.index("-q") + 1]
    assert str(prompt_file) in bootstrap
    assert run_id in bootstrap
    assert len(bootstrap) < 500
    assert "FULL_PROMPT_SENTINEL" not in bootstrap
    assert all(unique_prompt_text not in argument for argument in command)
    assert failure_calls == []
    assert pid_calls[0][1]["process_identity"] == "test-process"
