from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import project_state as state


DEPENDENCIES = {
    "01-literature": [],
    "02-method": ["01-literature"],
    "03-analysis": ["02-method"],
}


def _create_windows_directory_junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            "could not create a Windows directory junction for the test: "
            + (result.stderr or result.stdout).strip()
        )


def _reserve_worker(project: str, phase: str, ready, go, results) -> None:
    ready.put(phase)
    go.wait(10)
    try:
        run_id = state.reserve_run(
            project,
            phase,
            "concurrent",
            override_metadata=(
                {"reason": "Concurrency test explicitly accepts missing prerequisites"}
                if phase != "01-literature"
                else None
            ),
        )
    except state.StateConflict as exc:
        results.put(("conflict", phase, str(exc)))
    else:
        results.put(("reserved", phase, run_id))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    state.init(
        root,
        "project-001",
        "example",
        "Example",
        phase_slugs=list(DEPENDENCIES),
        dependencies=DEPENDENCIES,
    )
    return root


def test_project_lock_rechecks_file_identity_after_waiting(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_samestat = state.os.path.samestat
    calls = 0

    def changed_after_lock(left: os.stat_result, right: os.stat_result) -> bool:
        nonlocal calls
        calls += 1
        if calls == 2:
            return False
        return original_samestat(left, right)

    monkeypatch.setattr(state.os.path, "samestat", changed_after_lock)

    with pytest.raises(state.StateValidationError, match="changed while"):
        with state._project_lock(project):
            pytest.fail("a replaced lock path must never guard state access")


def finish_for_review(
    project: Path,
    phase: str,
    *,
    dependencies: dict[str, list[str]] = DEPENDENCIES,
    override_metadata: dict | None = None,
    label: str = "run",
) -> str:
    run_id = state.reserve_run(
        project,
        phase,
        mode=label,
        rounds_requested=1,
        dependencies=dependencies,
        override_metadata=override_metadata,
    )
    state.set_process_pid(project, phase, run_id, 1000 + len(state.get_runs(project, phase)))
    state.start_round(project, phase, run_id, "do the work", ["lead"], round_n=1)
    output = project / "artifacts" / f"{phase}-{run_id}.txt"
    output.parent.mkdir(exist_ok=True)
    output.write_text("evidence", encoding="utf-8")
    state.complete_round(project, phase, run_id, 1, [output])
    summary = project / "summaries" / f"{phase}-{run_id}.md"
    summary.parent.mkdir(exist_ok=True)
    summary.write_text("# Result\n\nSupported by evidence.\n", encoding="utf-8")
    state.submit_run_for_review(project, phase, run_id, summary)
    return run_id


def approve_phase(project: Path, phase: str, **kwargs) -> str:
    run_id = finish_for_review(project, phase, **kwargs)
    state.approve_run(
        project,
        phase,
        run_id,
        approval_kind="approve",
        dependencies=DEPENDENCIES,
    )
    return run_id


def prepare_phase_six_full_run(project: Path) -> tuple[str, Path, Path, Path, Path]:
    phase = state.PAPER_WRITING_PHASE
    dependencies = {**DEPENDENCIES, phase: []}
    run_id = state.reserve_run(
        project,
        phase,
        mode="full manuscript",
        rounds_requested=1,
        dependencies=dependencies,
    )
    output_root = project / "draft" / "run" / "01"
    output_root.mkdir(parents=True)
    review = output_root / "manuscript-review.md"
    review.write_text("# Reviewed manuscript\n", encoding="utf-8")
    post_review = output_root / "manuscript-post-review.md"
    diff = output_root / "manuscript-post-review.diff"
    manifest = {
        "schema_version": 3,
        "run_id": run_id,
        "phase_slug": phase,
        "timeout_minutes": 30,
        "output_root": str(output_root),
        "paper_review": {"kind": "full", "review_path": str(review)},
        "submission_outputs": {
            "post_review_manuscript": {
                "path": str(post_review),
                "allow_empty": False,
            },
            "review_diff": {"path": str(diff), "allow_empty": True},
        },
    }
    manifest_path = state.state_dir(project) / "runs" / phase / f"{run_id}.manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state.seal_run_manifest(project, phase, run_id, manifest_path)
    state.set_process_pid(project, phase, run_id, 901)
    state.seal_review_target(
        project, phase, run_id, review, hashlib.sha256(review.read_bytes()).hexdigest()
    )
    state.start_round(project, phase, run_id, "complete the paper", ["lead"], 1)
    report = output_root / "round-01-report.md"
    report.write_text("Scientific completion outcome: Complete\n", encoding="utf-8")
    state.complete_round(project, phase, run_id, 1, [report])
    summary = project / "phase-summaries" / phase / f"{run_id}.html"
    summary.parent.mkdir(parents=True)
    summary.write_text("<h1>Decision brief</h1>", encoding="utf-8")
    return run_id, review, post_review, diff, summary


def decision_payload(
    outcome: str = "Partial",
    *,
    phase: str = "01-literature",
    run: str = "test-run",
) -> dict:
    return {
        "schema_version": 1,
        "scientific_outcome": outcome,
        "decision_requested": "Decide whether this qualified result should become the phase baseline.",
        "recommended_user_action": "approve_with_limitations",
        "recommendation": "Accept the negative result with the stated scope limitation.",
        "main_evidence": ["The prespecified comparison is recorded in artifacts/result.txt."],
        "principal_risk": "The boundary regime was not assessed.",
        "smallest_decision_changer": "A boundary-regime result with the opposite ordering.",
        "option_consequences": {
            "approve": "Accept the qualified conclusion as the phase baseline.",
            "approve_with_limitations": "Accept the whole qualified baseline and carry the untested boundary regime forward explicitly.",
            "request_revision": "Add the missing boundary analysis before deciding.",
            "rerun": "Run the prespecified boundary comparison.",
            "defer": "Keep the current accepted baseline while this result remains unapproved.",
        },
        "rerun_question": "Does the ordering reverse in the boundary regime?",
        "rerun_comparison": "This initial run has no earlier approved comparison.",
        "proposed_baseline": "Under the assessed regimes, the methods are empirically indistinguishable; the boundary regime remains untested.",
        "scientific_record_changes": [
            {
                "statement_id": "S-P01-R001-summary-research_lead-001",
                "operation": "add",
                "changed_fields": [
                    "statement_type",
                    "wording",
                    "scope",
                    "formulation_state",
                    "assessment_status",
                    "evidential_basis",
                    "source_provenance",
                    "assumptions",
                    "uncertainty",
                    "logical_status",
                    "mathematical_result_type",
                ],
                "proposed_values": {
                    "statement_type": "Empirical statement",
                    "wording": "The methods are empirically indistinguishable in the assessed regimes.",
                    "scope": "The assessed regimes only",
                    "formulation_state": "Proposed",
                    "assessment_status": "Partially supported",
                    "evidential_basis": ["The prespecified comparison"],
                    "source_provenance": ["artifacts/result.txt"],
                    "assumptions": ["The saved comparison follows the prespecified protocol."],
                    "uncertainty": ["The boundary regime was not assessed."],
                    "logical_status": "Not applicable",
                    "mathematical_result_type": "Not applicable",
                },
                "evidential_basis": ["artifacts/result.txt"],
                "reason": "The completed comparison supports this qualified empirical statement.",
                "parent_statement_id": None,
                "change_origin": {
                    "phase": phase,
                    "run": run,
                    "round_or_stage": "summary",
                    "role": "research_lead",
                },
            }
        ],
    }


def prepare_modern_decision_run(
    project: Path, *, outcome: str = "Partial"
) -> tuple[str, Path, Path]:
    phase = "01-literature"
    run_id = state.reserve_run(project, phase, mode="structured decision")
    summary = project / "phase-summaries" / phase / f"{run_id}.html"
    decision = summary.with_suffix(".decision.json")
    manifest = {
        "schema_version": 4,
        "run_id": run_id,
        "phase_slug": phase,
        "timeout_minutes": 30,
        "summary_path": str(summary),
        "decision_path": str(decision),
    }
    manifest_path = state.state_dir(project) / "runs" / phase / f"{run_id}.manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state.seal_run_manifest(project, phase, run_id, manifest_path)
    state.set_process_pid(project, phase, run_id, 1901)
    state.start_round(project, phase, run_id, "record the evidence", ["lead"], 1)
    artifact = project / "artifacts" / "result.txt"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text("qualified negative result", encoding="utf-8")
    state.complete_round(project, phase, run_id, 1, [artifact])
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text("<h1>User decision brief</h1>", encoding="utf-8")
    decision.write_text(
        json.dumps(decision_payload(outcome, phase=phase, run=run_id)),
        encoding="utf-8",
    )
    return run_id, summary, decision


def test_rerun_keeps_prior_approval_until_replacement_is_approved(project: Path) -> None:
    first = approve_phase(project, "01-literature", label="first")
    rerun = state.reserve_run(project, "01-literature", "rerun", 1)

    phase = state.get_phase_status(project, "01-literature")
    assert phase["approved_run"] == first
    assert phase["latest_run"] == rerun
    assert state.get_run_status(project, "01-literature", first) == "approved"
    assert phase["stale"] is False

    state.cancel_run(project, "01-literature", rerun, "user changed direction")
    phase = state.get_phase_status(project, "01-literature")
    assert phase["status"] == "approved"
    assert phase["approved_run"] == first


def test_modern_submission_requires_valid_structured_decision_record(
    project: Path,
) -> None:
    run_id, summary, decision = prepare_modern_decision_run(project)

    with pytest.raises(state.StateValidationError, match="requires a structured"):
        state.stage_run_submission(project, "01-literature", run_id, summary)

    invalid = decision_payload(phase="01-literature", run=run_id)
    invalid.pop("principal_risk")
    decision.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(state.StateValidationError, match="fields are invalid"):
        state.stage_run_submission(
            project, "01-literature", run_id, summary, decision
        )

    decision.write_text(
        json.dumps(decision_payload(phase="01-literature", run=run_id)),
        encoding="utf-8",
    )
    state.stage_run_submission(project, "01-literature", run_id, summary, decision)
    recorded = state.get_run(project, "01-literature", run_id)["decision_record"]
    assert recorded["data"]["scientific_outcome"] == "Partial"
    assert recorded["data"]["recommended_user_action"] == "approve_with_limitations"


def test_decision_record_allows_a_broad_set_of_statement_changes() -> None:
    payload = decision_payload()
    change = payload["scientific_record_changes"][0]
    payload["scientific_record_changes"] = [
        {**change, "statement_id": f"S{index}"}
        for index in range(1, 21)
    ]

    validated = state.validate_decision_record(payload)

    assert len(validated["scientific_record_changes"]) == 20


def test_decision_record_schema_two_accepts_a_selected_method_identity() -> None:
    payload = decision_payload()
    selected_method = {
        "kind": "method",
        "stable_id": "METHOD-robust-score",
        "version": "v2.1/finite-sample",
    }
    payload.update({
        "schema_version": 2,
        "selected_scientific_object": selected_method,
        "decision_requested": (
            "Decide whether METHOD-robust-score version v2.1/finite-sample "
            "should become the selected method."
        ),
    })

    validated = state.validate_decision_record(payload)

    assert validated["schema_version"] == 2
    assert validated["selected_scientific_object"] == selected_method


@pytest.mark.parametrize(
    ("selected_method", "message"),
    [
        (
            {"kind": "model", "stable_id": "METHOD-1", "version": "v1"},
            "kind must be method",
        ),
        (
            {"kind": "method", "stable_id": "METHOD 1", "version": "v1"},
            "stable_id must use ASCII",
        ),
        (
            {"kind": "method", "stable_id": "METHOD-1", "version": "v1?"},
            "version must use ASCII",
        ),
        (
            {"kind": "method", "stable_id": "METHOD-1"},
            "contain exactly kind, stable_id, and version",
        ),
    ],
)
def test_decision_record_schema_two_rejects_malformed_selected_method_identities(
    selected_method: dict[str, str],
    message: str,
) -> None:
    payload = decision_payload()
    payload["schema_version"] = 2
    payload["selected_scientific_object"] = selected_method

    with pytest.raises(state.StateValidationError, match=message):
        state.validate_decision_record(payload)


@pytest.mark.parametrize(
    ("selected_method", "decision_requested", "message"),
    [
        (
            None,
            "Decide whether to select the proposed method.",
            "must name one selected method ID and version",
        ),
        (
            {"kind": "method", "stable_id": "METHOD-42", "version": "v3"},
            "Decide whether METHOD-42 should become the selected method.",
            "must repeat the selected method ID and version",
        ),
        (
            {"kind": "method", "stable_id": "METHOD-42", "version": "v3"},
            "Decide whether version v3 should become the selected method.",
            "must repeat the selected method ID and version",
        ),
    ],
)
def test_schema_seven_phase_two_binds_the_decision_to_the_selected_method(
    selected_method: dict[str, str] | None,
    decision_requested: str,
    message: str,
) -> None:
    run_id = "run-method-selection"
    payload = decision_payload(
        phase=state.METHOD_DEVELOPMENT_PHASE,
        run=run_id,
    )
    payload.update({
        "schema_version": 2,
        "selected_scientific_object": selected_method,
        "decision_requested": decision_requested,
    })
    normalized = state.validate_decision_record(payload)
    manifest = {
        "schema_version": 7,
        "phase_slug": state.METHOD_DEVELOPMENT_PHASE,
        "run_id": run_id,
        "rounds_requested": 1,
        "phase": {
            "pattern": "iterative",
            "members": ["research_lead"],
        },
    }

    with pytest.raises(state.StateValidationError, match=message):
        state._validate_decision_record_context(normalized, manifest)


def test_decision_record_requires_new_identity_for_wording_and_explicit_withdrawal() -> None:
    payload = decision_payload()
    change = payload["scientific_record_changes"][0]
    payload["scientific_record_changes"] = [{
        **change,
        "operation": "revise",
        "changed_fields": ["wording"],
        "proposed_values": {"wording": "Materially different statement."},
        "parent_statement_id": None,
    }]
    with pytest.raises(state.StateValidationError, match="new statement ID"):
        state.validate_decision_record(payload)

    payload = decision_payload()
    change = payload["scientific_record_changes"][0]
    payload["scientific_record_changes"] = [{
        **change,
        "operation": "withdraw",
        "changed_fields": ["assessment_status"],
        "proposed_values": {"assessment_status": "Contradicted"},
        "parent_statement_id": None,
    }]
    with pytest.raises(state.StateValidationError, match="Withdrawn"):
        state.validate_decision_record(payload)

    payload = decision_payload()
    payload["scientific_record_changes"][0]["proposed_values"][
        "assessment_status"
    ] = "State one of the allowed assessment values."
    with pytest.raises(state.StateValidationError, match="assessment_status"):
        state.validate_decision_record(payload)

    payload = decision_payload()
    change = payload["scientific_record_changes"][0]
    payload["scientific_record_changes"] = [change, dict(change)]
    with pytest.raises(state.StateValidationError, match="one consolidated change"):
        state.validate_decision_record(payload)

    payload = decision_payload()
    payload["scientific_record_changes"][0]["proposed_values"][
        "formulation_state"
    ] = "Current"
    with pytest.raises(state.StateValidationError, match="must set formulation_state to Proposed"):
        state.validate_decision_record(payload)

    payload = decision_payload()
    change = payload["scientific_record_changes"][0]
    payload["scientific_record_changes"] = [{
        **change,
        "operation": "revise",
        "changed_fields": ["formulation_state"],
        "proposed_values": {"formulation_state": "Withdrawn"},
    }]
    with pytest.raises(state.StateValidationError, match="must use the withdraw operation"):
        state.validate_decision_record(payload)

    payload = decision_payload()
    payload["scientific_record_changes"][0]["parent_statement_id"] = "bad parent"
    with pytest.raises(state.StateValidationError, match="parent_statement_id must use ASCII"):
        state.validate_decision_record(payload)

    payload = decision_payload()
    change = payload["scientific_record_changes"][0]
    change["parent_statement_id"] = change["statement_id"]
    with pytest.raises(state.StateValidationError, match="own statement_id"):
        state.validate_decision_record(payload)


def test_decision_record_origin_matches_the_frozen_stage_plan() -> None:
    payload = decision_payload(phase="03-theory", run="run-001")
    change = payload["scientific_record_changes"][0]
    change["change_origin"] = {
        "phase": "03-theory",
        "run": "run-001",
        "round_or_stage": "round 2",
        "role": "theorist",
    }
    normalized = state.validate_decision_record(payload)
    manifest = {
        "schema_version": 5,
        "phase_slug": "03-theory",
        "run_id": "run-001",
        "rounds_requested": 2,
        "phase": {
            "pattern": "sequential",
            "members": ["theorist", "research_lead"],
            "stages": [
                {"role": "theorist"},
                {"role": "research_lead"},
            ],
        },
    }

    with pytest.raises(state.StateValidationError, match="does not match"):
        state._validate_decision_record_context(normalized, manifest)

    normalized["scientific_record_changes"][0]["change_origin"][
        "round_or_stage"
    ] = "round 1"
    state._validate_decision_record_context(normalized, manifest)


def test_decision_record_is_integrity_checked_and_bound_to_explicit_approval(
    project: Path,
) -> None:
    run_id, summary, decision = prepare_modern_decision_run(project, outcome="Failed")
    state.submit_run_for_review(
        project, "01-literature", run_id, summary, decision
    )
    record = state.get_run(project, "01-literature", run_id)["decision_record"]

    with pytest.raises(state.StateValidationError, match="approval kind"):
        state.approve_run(
            project,
            "01-literature",
            run_id,
            approval_kind="",
            dependencies=DEPENDENCIES,
        )
    with pytest.raises(state.StateConflict, match="explicitly accept"):
        state.approve_run(
            project,
            "01-literature",
            run_id,
            approval_kind="approve",
            dependencies=DEPENDENCIES,
        )
    with pytest.raises(state.StateConflict, match="changed after"):
        state.approve_run(
            project,
            "01-literature",
            run_id,
            approval_kind="approve",
            dependencies=DEPENDENCIES,
            baseline_acknowledgement="accepted",
            expected_decision_record_version="0" * 64,
        )

    state.approve_run(
        project,
        "01-literature",
        run_id,
        approval_kind="approve_with_limitations",
        dependencies=DEPENDENCIES,
        baseline_acknowledgement="accepted as the scientific baseline",
        expected_decision_record_version=record["sha256"],
    )
    approved = state.get_run(project, "01-literature", run_id)
    assert approved["status"] == "approved"
    assert approved["decision_record"]["data"]["scientific_outcome"] == "Failed"
    assert approved["approval_baseline_acknowledgement"][
        "decision_record_sha256"
    ] == record["sha256"]
    assert approved["approval_kind"] == "approve_with_limitations"
    assert approved["approval_baseline_acknowledgement"]["approval_kind"] == (
        "approve_with_limitations"
    )

    decision.write_text(
        json.dumps(
            decision_payload(
                "Complete", phase="01-literature", run=run_id
            )
        ),
        encoding="utf-8",
    )
    report = state.run_integrity_report(project, "01-literature", run_id)
    assert report["ok"] is False
    assert "decision record changed" in report["reason"]


def test_sealed_review_target_must_remain_unchanged_at_submission(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "paper review", 1)
    state.start_round(project, "01-literature", run_id, "review", ["lead"], 1)
    reviewed = project / "draft" / "manuscript-review.md"
    reviewed.parent.mkdir()
    reviewed.write_text("exact reviewed text", encoding="utf-8")
    digest = hashlib.sha256(reviewed.read_bytes()).hexdigest()

    first = state.seal_review_target(
        project, "01-literature", run_id, reviewed, digest
    )
    second = state.seal_review_target(
        project, "01-literature", run_id, reviewed, digest
    )
    assert first == second

    output = project / "review.md"
    output.write_text("review report", encoding="utf-8")
    state.complete_round(project, "01-literature", run_id, 1, [output])
    summary = project / "summary.md"
    summary.write_text("summary", encoding="utf-8")
    reviewed.write_text("changed after dispatch", encoding="utf-8")

    with pytest.raises(state.StateValidationError, match="review target changed"):
        state.stage_run_submission(project, "01-literature", run_id, summary)


def test_explicit_rerun_replaces_a_run_awaiting_review(project: Path) -> None:
    awaiting = finish_for_review(project, "01-literature")
    replacement = state.reserve_run(
        project,
        "01-literature",
        "replacement",
        replace_awaiting_review_note="The user wants a broader search.",
        replace_awaiting_review_run_id=awaiting,
    )

    prior = state.get_run(project, "01-literature", awaiting)
    pending = state.get_run(project, "01-literature", replacement)
    assert prior["status"] == "awaiting_review"
    assert pending["replacement_request"]["run_id"] == awaiting
    assert pending["replacement_request"]["committed_at"] is None

    state.set_process_pid(project, "01-literature", replacement, 1200)
    prior = state.get_run(project, "01-literature", awaiting)
    assert prior["status"] == "revision_requested"
    assert prior["decision_by"] == "user"
    assert prior["replaced_by_rerun"] is True
    assert prior["replaced_by_run"] == replacement
    assert replacement != awaiting


def test_failed_replacement_before_worker_registration_preserves_review_choice(
    project: Path,
) -> None:
    awaiting = finish_for_review(project, "01-literature")
    replacement = state.reserve_run(
        project,
        "01-literature",
        "replacement",
        replace_awaiting_review_note="Try a different scientific direction.",
        replace_awaiting_review_run_id=awaiting,
    )

    assert state.fail_run_if_active(
        project, "01-literature", replacement, "launch preparation failed"
    ) is True
    assert state.get_run_status(project, "01-literature", awaiting) == "awaiting_review"
    assert state.get_run_status(project, "01-literature", replacement) == "failed"


def test_replacement_confirmation_is_bound_to_the_exact_awaiting_run(
    project: Path,
) -> None:
    awaiting = finish_for_review(project, "01-literature")

    with pytest.raises(state.StateConflict, match="changed after"):
        state.reserve_run(
            project,
            "01-literature",
            "replacement",
            replace_awaiting_review_note="Try a narrower question.",
            replace_awaiting_review_run_id="a-different-run",
        )

    assert state.get_run_status(project, "01-literature", awaiting) == "awaiting_review"
    assert state.get_active_run(project) is None


def test_approval_supersedes_old_run_and_stales_all_approved_descendants(project: Path) -> None:
    first_literature = approve_phase(project, "01-literature")
    approve_phase(project, "02-method")
    approve_phase(project, "03-analysis")

    replacement = finish_for_review(project, "01-literature", label="replacement")
    # Merely executing and submitting a rerun does not stale downstream work.
    assert state.get_phase_status(project, "02-method")["stale"] is False
    assert state.get_phase_status(project, "03-analysis")["stale"] is False

    staled = state.approve_run(
        project,
        "01-literature",
        replacement,
        approval_kind="approve",
        dependencies=DEPENDENCIES,
        reviewer="researcher",
    )

    assert staled == ["02-method", "03-analysis"]
    assert state.get_run_status(project, "01-literature", first_literature) == "superseded"
    assert state.get_phase_status(project, "02-method")["status"] == "stale"
    assert state.get_phase_status(project, "03-analysis")["status"] == "stale"
    report = state.prerequisite_report(project, "03-analysis", DEPENDENCIES)
    assert report["satisfied"] is False
    assert report["blockers"] == ["02-method"]


def test_blocked_phase_requires_and_records_explicit_override(project: Path) -> None:
    with pytest.raises(state.StateConflict, match="prerequisites"):
        state.reserve_run(project, "02-method", "early")

    run_id = state.reserve_run(
        project,
        "02-method",
        "early",
        override_metadata={"reason": "User wants an exploratory method sketch", "actor": "alice"},
    )
    run = state.get_run(project, "02-method", run_id)
    assert run["override_metadata"]["actor"] == "alice"
    assert run["override_metadata"]["blockers"] == ["01-literature"]
    assert run["prerequisite_snapshot"]["satisfied"] is False


def test_submit_rejects_incomplete_rounds_and_counts_only_completed(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "two rounds", 2)
    state.set_process_pid(project, "01-literature", run_id, 222)
    state.start_round(project, "01-literature", run_id, "round one", ["lead"], round_n=1)
    artifact = project / "artifact.txt"
    artifact.write_text("result", encoding="utf-8")
    state.complete_round(project, "01-literature", run_id, 1, [artifact])
    state.start_round(project, "01-literature", run_id, "round two", ["critic"], round_n=2)
    summary = project / "summary.md"
    summary.write_text("not ready", encoding="utf-8")

    assert state.completed_round_count(project, "01-literature", run_id) == 1
    with pytest.raises(state.StateValidationError, match="only 1"):
        state.submit_run_for_review(project, "01-literature", run_id, summary)


def test_external_task_ids_are_attached_to_only_the_open_round(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "tasks")
    state.set_process_pid(project, "01-literature", run_id, 223)
    state.start_round(project, "01-literature", run_id, "work", ["lead"])
    brief = state.state_dir(project) / "runs" / "01-literature" / "task.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("# Frozen task\n", encoding="utf-8")
    brief_hash = hashlib.sha256(brief.read_bytes()).hexdigest()
    with pytest.raises(state.StateValidationError, match="brief path and sha256"):
        state.record_task(
            project,
            "01-literature",
            run_id,
            1,
            role="lead",
            task_id="unsealed-task",
            title="Unsealed task",
        )
    state.record_task(
        project,
        "01-literature",
        run_id,
        1,
        role="lead",
        task_id="hermes-123",
        title="Literature scan",
        brief_path=brief,
        brief_sha256=brief_hash,
    )
    task = state.get_run(project, "01-literature", run_id)["rounds"][0]["tasks"][0]
    assert task["task_id"] == "hermes-123"
    with pytest.raises(state.StateConflict, match="already recorded"):
        state.record_task(
            project,
            "01-literature",
            run_id,
            1,
            role="lead",
            task_id="hermes-123",
            title="Duplicate",
            brief_path=brief,
            brief_sha256=brief_hash,
        )


def test_changed_sealed_reviewer_workspace_blocks_submission(project: Path) -> None:
    phase = "01-literature"
    run_id = state.reserve_run(project, phase, "sealed reviewer workspace")
    state.set_process_pid(project, phase, run_id, 224)
    state.start_round(project, phase, run_id, "review", ["paper_reviewer"], 1)
    root = (
        state.state_dir(project)
        / "review-workspaces"
        / phase
        / run_id
        / "round-01-paper_reviewer"
    )
    task_path = root / "task.md"
    input_path = root / "inputs" / "input-01.md"
    task_path.parent.mkdir(parents=True)
    input_path.parent.mkdir()
    task_path.write_text("# Sealed reviewer task\n", encoding="utf-8")
    input_path.write_text("# Sealed manuscript\n", encoding="utf-8")
    task_bytes = task_path.read_bytes()
    input_bytes = input_path.read_bytes()
    bundle = {
        "schema_version": state.REVIEW_BUNDLE_SCHEMA_VERSION,
        "phase_slug": phase,
        "run_id": run_id,
        "round": 1,
        "role": "paper_reviewer",
        "subtype": "independent_manuscript_reading",
        "task": {
            "path": "task.md",
            "sha256": hashlib.sha256(task_bytes).hexdigest(),
            "size": len(task_bytes),
        },
        "inputs": [{
            "path": "inputs/input-01.md",
            "sha256": hashlib.sha256(input_bytes).hexdigest(),
            "size": len(input_bytes),
            "purpose": "Exact manuscript under review",
        }],
        "output": {
            "path": "output/report.md",
            "max_bytes": state.MAX_REVIEW_OUTPUT_BYTES,
        },
    }
    bundle_path = root / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    state.record_task(
        project,
        phase,
        run_id,
        1,
        role="paper_reviewer",
        task_id="review-task",
        title="Independent review",
        brief_path=task_path,
        brief_sha256=hashlib.sha256(task_bytes).hexdigest(),
        review_bundle={
            "root": str(root),
            "manifest_path": str(bundle_path),
            "manifest_sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
        },
    )
    report = project / "review-report.md"
    report.write_text("Scientific completion outcome: Complete\n", encoding="utf-8")
    state.complete_round(project, phase, run_id, 1, [report])
    summary = project / "summary.md"
    summary.write_text("# Summary\n", encoding="utf-8")
    input_path.write_text("changed reviewer input", encoding="utf-8")

    with pytest.raises(state.StateValidationError, match="input changed"):
        state.stage_run_submission(project, phase, run_id, summary)


def test_run_context_is_hash_checked_and_immutable(project: Path) -> None:
    source = approve_phase(project, "01-literature")
    source_run = state.get_run(project, "01-literature", source)
    summary = project / source_run["final_summary"]
    digest = hashlib.sha256(summary.read_bytes()).hexdigest()
    target = state.reserve_run(project, "02-method", "uses literature")
    context = [{
        "phase": "01-literature",
        "run_id": source,
        "summary": source_run["final_summary"],
        "sha256": digest,
    }]
    state.set_run_context(project, "02-method", target, context)
    state.set_run_context(project, "02-method", target, context)  # idempotent
    stored = state.get_run(project, "02-method", target)["context_inputs"]
    assert stored == context
    with pytest.raises(state.StateConflict, match="already frozen"):
        state.set_run_context(project, "02-method", target, [])


def test_tampered_approved_summary_cannot_become_downstream_context(project: Path) -> None:
    source = approve_phase(project, "01-literature")
    source_run = state.get_run(project, "01-literature", source)
    summary = project / source_run["final_summary"]
    summary.write_text("# Altered after approval\n", encoding="utf-8")
    report = state.prerequisite_report(project, "02-method", DEPENDENCIES)
    assert report["satisfied"] is False
    assert report["requirements"][0]["reason"] == "approved evidence is missing or changed"
    target = state.reserve_run(
        project,
        "02-method",
        "uses literature",
        override_metadata={"reason": "User is testing the integrity guard"},
    )
    digest = hashlib.sha256(summary.read_bytes()).hexdigest()

    with pytest.raises(state.StateValidationError, match="changed after approval"):
        state.set_run_context(project, "02-method", target, [{
            "phase": "01-literature",
            "run_id": source,
            "summary": source_run["final_summary"],
            "sha256": digest,
        }])


def test_approval_requires_acknowledgement_when_upstream_context_changed(project: Path) -> None:
    first_source = approve_phase(project, "01-literature", label="source one")
    downstream = finish_for_review(project, "02-method", label="downstream on source one")
    replacement = finish_for_review(project, "01-literature", label="source two")
    state.approve_run(
        project,
        "01-literature",
        replacement,
        approval_kind="approve",
        dependencies=DEPENDENCIES,
    )

    report = state.approval_context_report(
        project, "02-method", downstream, DEPENDENCIES
    )
    assert report["requires_acknowledgement"] is True
    assert report["changed_sources"] == [{
        "phase": "01-literature",
        "launch_run": first_source,
        "current_run": replacement,
        "reason": "the approved prerequisite run changed after launch",
    }]
    with pytest.raises(state.StateConflict, match="explicitly acknowledge"):
        state.approve_run(
            project,
            "02-method",
            downstream,
            approval_kind="approve",
            dependencies=DEPENDENCIES,
        )

    state.approve_run(
        project,
        "02-method",
        downstream,
        approval_kind="approve",
        dependencies=DEPENDENCIES,
        context_acknowledgement="User accepts the older literature baseline for this result.",
    )
    approved = state.get_run(project, "02-method", downstream)
    assert approved["status"] == "approved"
    assert approved["approval_context_acknowledgement"]["report"][
        "requires_acknowledgement"
    ] is True


def test_locked_transitions_reject_changed_decision_report_versions(project: Path) -> None:
    blocked = state.prerequisite_report(project, "02-method", DEPENDENCIES)
    blocked_version = state.decision_report_version("prerequisite", blocked)
    approve_phase(project, "01-literature")

    with pytest.raises(state.StateConflict, match="prerequisite status changed"):
        state.reserve_run(
            project,
            "02-method",
            "stale page",
            dependencies=DEPENDENCIES,
            override_metadata={"reason": "Use the earlier warning"},
            expected_prerequisite_report_version=blocked_version,
        )

    downstream = finish_for_review(project, "02-method")
    context = state.approval_context_report(
        project, "02-method", downstream, DEPENDENCIES
    )
    context_version = state.decision_report_version("approval_context", context)
    replacement = finish_for_review(project, "01-literature", label="new source")
    state.approve_run(
        project,
        "01-literature",
        replacement,
        approval_kind="approve",
        dependencies=DEPENDENCIES,
    )

    with pytest.raises(state.StateConflict, match="approval context changed"):
        state.approve_run(
            project,
            "02-method",
            downstream,
            approval_kind="approve",
            dependencies=DEPENDENCIES,
            context_acknowledgement="Accept the changed context.",
            expected_context_report_version=context_version,
        )


def test_reserve_run_rejects_a_stale_satisfied_prerequisite_report(
    project: Path,
) -> None:
    approve_phase(project, "01-literature", label="first accepted source")
    reviewed = state.prerequisite_report(project, "02-method", DEPENDENCIES)
    reviewed_version = state.decision_report_version("prerequisite", reviewed)
    assert reviewed["satisfied"] is True

    replacement = finish_for_review(
        project,
        "01-literature",
        label="replacement accepted source",
    )
    state.approve_run(
        project,
        "01-literature",
        replacement,
        approval_kind="approve",
        dependencies=DEPENDENCIES,
    )
    current = state.prerequisite_report(project, "02-method", DEPENDENCIES)
    assert current["satisfied"] is True
    assert state.decision_report_version("prerequisite", current) != reviewed_version

    with pytest.raises(state.StateConflict, match="prerequisite status changed"):
        state.reserve_run(
            project,
            "02-method",
            "stale satisfied prerequisite page",
            dependencies=DEPENDENCIES,
            expected_prerequisite_report_version=reviewed_version,
        )


def test_optional_context_digest_change_requires_approval_acknowledgement(
    project: Path,
) -> None:
    source = approve_phase(project, "01-literature", label="optional source")
    source_run = state.get_run(project, "01-literature", source)
    source_summary = project / source_run["final_summary"]
    no_gates = {phase: [] for phase in DEPENDENCIES}
    target = state.reserve_run(
        project, "03-analysis", "optional context", dependencies=no_gates
    )
    state.set_run_context(project, "03-analysis", target, [{
        "phase": "01-literature",
        "run_id": source,
        "summary": source_run["final_summary"],
        "sha256": hashlib.sha256(source_summary.read_bytes()).hexdigest(),
    }])
    state.set_process_pid(project, "03-analysis", target, 614)
    state.start_round(project, "03-analysis", target, "analyze", ["lead"])
    artifact = project / "optional-analysis.md"
    artifact.write_text("analysis", encoding="utf-8")
    state.complete_round(project, "03-analysis", target, 1, [artifact])
    summary = project / "optional-summary.md"
    summary.write_text("# Optional-context result\n", encoding="utf-8")
    state.submit_run_for_review(project, "03-analysis", target, summary)

    source_summary.write_text("# Changed optional evidence\n", encoding="utf-8")
    report = state.approval_context_report(
        project, "03-analysis", target, no_gates
    )

    assert report["requires_acknowledgement"] is True
    assert report["changed_sources"][0]["reason"] == (
        "approved context-source evidence is missing or changed"
    )


def test_staged_submission_remains_cancellable_until_worker_exit(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "staged submission")
    state.set_process_pid(
        project,
        "01-literature",
        run_id,
        777,
        process_identity="worker-birth-token",
    )
    state.start_round(project, "01-literature", run_id, "work", ["lead"])
    artifact = project / "staged-artifact.md"
    artifact.write_text("evidence", encoding="utf-8")
    state.complete_round(project, "01-literature", run_id, 1, [artifact])
    summary = project / "staged-summary.md"
    summary.write_text("# Summary\n", encoding="utf-8")

    state.stage_run_submission(project, "01-literature", run_id, summary)
    assert state.get_run_status(project, "01-literature", run_id) == "submitting"
    assert state.get_active_run(project)["run_id"] == run_id
    assert state.cancel_run_if_active(
        project, "01-literature", run_id, "user stopped finalization", expected_pid=777
    ) is True
    assert state.get_run_status(project, "01-literature", run_id) == "cancelled"


def test_artifact_and_summary_paths_must_exist_inside_project(project: Path, tmp_path: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "paths")
    state.set_process_pid(project, "01-literature", run_id, 333)
    state.start_round(project, "01-literature", run_id, "work", ["lead"])
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    with pytest.raises(state.StateValidationError, match="inside"):
        state.complete_round(project, "01-literature", run_id, 1, [outside])

    inside = project / "inside.txt"
    inside.write_text("inside", encoding="utf-8")
    state.complete_round(project, "01-literature", run_id, 1, [inside])
    artifact_record = state.get_run(project, "01-literature", run_id)["rounds"][0]["artifacts"][0]
    assert artifact_record["path"] == "inside.txt"
    assert artifact_record["sha256"] == hashlib.sha256(b"inside").hexdigest()
    empty = project / "empty.md"
    empty.write_text("   \n", encoding="utf-8")
    with pytest.raises(state.StateValidationError, match="empty"):
        state.submit_run_for_review(project, "01-literature", run_id, empty)
    with pytest.raises(state.StateValidationError, match="inside"):
        state.submit_run_for_review(project, "01-literature", run_id, outside)


def test_only_one_active_run_can_be_reserved_atomically(project: Path) -> None:
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    go = context.Event()
    results = context.Queue()
    processes = [
        context.Process(
            target=_reserve_worker,
            args=(str(project), phase, ready, go, results),
        )
        for phase in ("01-literature", "02-method")
    ]
    for process in processes:
        process.start()
    assert {ready.get(timeout=10), ready.get(timeout=10)} == {"01-literature", "02-method"}
    go.set()
    outcomes = [results.get(timeout=10), results.get(timeout=10)]
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    assert sorted(outcome[0] for outcome in outcomes) == ["conflict", "reserved"]
    assert sum(len(state.get_runs(project, phase)) for phase in DEPENDENCIES) == 1
    assert state.get_active_run(project)["run_id"] == next(
        outcome[2] for outcome in outcomes if outcome[0] == "reserved"
    )


def test_failed_rerun_falls_back_to_prior_approval(project: Path) -> None:
    approved = approve_phase(project, "01-literature")
    rerun = state.reserve_run(project, "01-literature", "risky rerun")
    state.set_process_pid(project, "01-literature", rerun, 444)
    state.fail_run(project, "01-literature", rerun, "worker exited")

    phase = state.get_phase_status(project, "01-literature")
    assert phase["status"] == "approved"
    assert phase["approved_run"] == approved
    assert phase["latest_run"] == rerun
    assert phase["latest_run_status"] == "failed"
    assert state.prerequisite_report(project, "02-method", DEPENDENCIES)["satisfied"] is True


def test_conditional_failure_matches_pid_and_is_idempotent(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "supervised")
    state.set_process_pid(project, "01-literature", run_id, 501)

    assert state.fail_run_if_active(
        project, "01-literature", run_id, "wrong worker", expected_pid=999
    ) is False
    assert state.get_run_status(project, "01-literature", run_id) == "running"
    assert state.fail_run_if_active(
        project, "01-literature", run_id, "worker exited", expected_pid=501
    ) is True
    assert state.fail_run_if_active(
        project, "01-literature", run_id, "late reconciliation", expected_pid=501
    ) is False
    assert state.get_run(project, "01-literature", run_id)["error"] == "worker exited"


def test_conditional_cancel_wins_without_late_failure_overwrite(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "cancel")
    state.set_process_pid(project, "01-literature", run_id, 502)

    assert state.cancel_run_if_active(
        project, "01-literature", run_id, "user stopped it", expected_pid=502
    ) is True
    assert state.fail_run_if_active(
        project, "01-literature", run_id, "late worker exit", expected_pid=502
    ) is False
    run = state.get_run(project, "01-literature", run_id)
    assert run["status"] == "cancelled"
    assert run["cancel_reason"] == "user stopped it"
    assert run["error"] is None


def test_stopping_run_holds_active_lease_until_cleanup_finalizes(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "cancel safely")
    state.set_process_pid(
        project,
        "01-literature",
        run_id,
        611,
        process_identity="birth-611",
    )

    assert state.begin_run_cleanup(
        project,
        "01-literature",
        run_id,
        "cancelled",
        "user requested cancellation",
        expected_pid=611,
    ) is True
    assert state.get_run_status(project, "01-literature", run_id) == "stopping"
    assert state.get_active_run(project)["run_id"] == run_id
    with pytest.raises(state.StateConflict, match="active run"):
        state.reserve_run(project, "02-method", "must wait")

    assert state.finalize_run_cleanup(
        project, "01-literature", run_id, expected_pid=611
    ) is True
    assert state.get_active_run(project) is None
    assert state.get_run_status(project, "01-literature", run_id) == "cancelled"


def test_unconfirmed_cleanup_requires_explicit_recovery_note(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "legacy cleanup")
    state.set_process_pid(project, "01-literature", run_id, 612)
    state.begin_run_cleanup(
        project, "01-literature", run_id, "failed", "worker identity unavailable"
    )

    with pytest.raises(state.StateConflict, match="explicit recovery note"):
        state.finalize_run_cleanup(
            project,
            "01-literature",
            run_id,
            cleanup_confirmed=False,
        )
    assert state.get_run_status(project, "01-literature", run_id) == "stopping"
    assert state.recover_run_cleanup(
        project,
        "01-literature",
        run_id,
        "User inspected the process table and confirmed no worker remains.",
    ) is True
    recovered = state.get_run(project, "01-literature", run_id)
    assert recovered["status"] == "failed"
    assert recovered["cleanup_recovery_note"].startswith("User inspected")


def test_submission_rejects_changed_round_artifact(project: Path) -> None:
    run_id = state.reserve_run(project, "01-literature", "artifact integrity")
    state.set_process_pid(project, "01-literature", run_id, 613)
    state.start_round(project, "01-literature", run_id, "work", ["lead"])
    artifact = project / "mutable-evidence.md"
    artifact.write_text("original evidence", encoding="utf-8")
    state.complete_round(project, "01-literature", run_id, 1, [artifact])
    artifact.write_text("changed evidence", encoding="utf-8")
    summary = project / "artifact-summary.md"
    summary.write_text("# Summary\n", encoding="utf-8")

    with pytest.raises(state.StateValidationError, match="changed after completion"):
        state.stage_run_submission(project, "01-literature", run_id, summary)


def test_approval_rejects_artifact_changed_after_submission(project: Path) -> None:
    run_id = finish_for_review(project, "01-literature")
    run = state.get_run(project, "01-literature", run_id)
    artifact = project / run["rounds"][0]["outputs"][0]
    artifact.write_text("changed after submission", encoding="utf-8")

    with pytest.raises(state.StateValidationError, match="changed after completion"):
        state.approve_run(
            project,
            "01-literature",
            run_id,
            approval_kind="approve",
            dependencies=DEPENDENCIES,
        )
    assert state.get_run_status(project, "01-literature", run_id) == "awaiting_review"


def test_phase_six_submission_requires_and_seals_exact_post_review_outputs(
    project: Path,
) -> None:
    run_id, _review, post_review, diff, summary = prepare_phase_six_full_run(project)

    with pytest.raises(state.StateValidationError, match="artifact does not exist"):
        state.stage_run_submission(
            project, state.PAPER_WRITING_PHASE, run_id, summary
        )

    post_review.write_text("# Final manuscript\n", encoding="utf-8")
    diff.write_bytes(b"")
    state.submit_run_for_review(
        project, state.PAPER_WRITING_PHASE, run_id, summary
    )
    run = state.get_run(project, state.PAPER_WRITING_PHASE, run_id)
    assert run["submission_artifacts"]["post_review_manuscript"] == {
        "path": post_review.relative_to(project).as_posix(),
        "sha256": hashlib.sha256(post_review.read_bytes()).hexdigest(),
        "size": len(post_review.read_bytes()),
    }
    assert run["submission_artifacts"]["review_diff"]["size"] == 0

    post_review.write_text("# Changed after submission\n", encoding="utf-8")
    with pytest.raises(state.StateValidationError, match="changed after submission"):
        state.approve_run(
            project,
            state.PAPER_WRITING_PHASE,
            run_id,
            approval_kind="approve",
            dependencies={**DEPENDENCIES, state.PAPER_WRITING_PHASE: []},
        )


def test_prerequisite_integrity_checks_all_approved_evidence(project: Path) -> None:
    run_id = approve_phase(project, "01-literature")
    run = state.get_run(project, "01-literature", run_id)
    artifact = project / run["rounds"][0]["artifacts"][0]["path"]
    artifact.write_text("changed after approval", encoding="utf-8")

    report = state.prerequisite_report(project, "02-method", DEPENDENCIES)
    assert report["satisfied"] is False
    assert report["requirements"][0]["reason"] == (
        "approved evidence is missing or changed"
    )
    assert "changed after completion" in report["requirements"][0]["integrity_detail"]


def test_failure_cannot_overwrite_a_successful_submission(project: Path) -> None:
    run_id = finish_for_review(project, "01-literature")

    assert state.fail_run_if_active(
        project, "01-literature", run_id, "late worker exit"
    ) is False
    with pytest.raises(state.StateConflict, match="cannot fail"):
        state.fail_run(project, "01-literature", run_id, "late worker exit")
    assert state.get_run_status(project, "01-literature", run_id) == "awaiting_review"


def test_load_migrates_legacy_state_without_discarding_unknown_data(tmp_path: Path) -> None:
    project = tmp_path / "legacy"
    log = project / ".log"
    log.mkdir(parents=True)
    legacy = {
        "project": {"id": "old", "custom": "keep me"},
        "phases": {
            "01-literature": {
                "status": "completed",
                "custom_phase": 42,
                "runs": [{
                    "mode": "legacy",
                    "rounds_requested": 1,
                    "started": "2026-01-01T00:00:00Z",
                    "completed": "2026-01-01T00:01:00Z",
                    "rounds": [],
                    "final_summary": "old.md",
                    "custom_run": ["keep"],
                }],
            }
        },
        "custom_root": {"keep": True},
    }
    (log / "project.yaml").write_text(yaml.safe_dump(legacy), encoding="utf-8")

    migrated = state.load(project)
    run = migrated["phases"]["01-literature"]["runs"][0]
    assert migrated["schema_version"] == state.SCHEMA_VERSION
    assert migrated["custom_root"] == {"keep": True}
    assert migrated["project"]["custom"] == "keep me"
    assert migrated["phases"]["01-literature"]["custom_phase"] == 42
    assert run["custom_run"] == ["keep"]
    assert run["status"] == "approved"
    assert migrated["phases"]["01-literature"]["approved_run"] == run["run_id"]
    assert state.load(project)["phases"]["01-literature"]["runs"][0]["run_id"] == run["run_id"]


def test_load_preserves_a_valid_legacy_active_pid_as_unverified_metadata(
    tmp_path: Path,
) -> None:
    project = tmp_path / "legacy-active"
    log = project / ".log"
    log.mkdir(parents=True)
    started = "2026-01-01T00:00:00Z"
    legacy = {
        "project": {"id": "old"},
        "phases": {
            "01-literature": {
                "status": "running",
                "runs": [{
                    "mode": "legacy",
                    "rounds_requested": 1,
                    "started": started,
                    "rounds": [],
                }],
            }
        },
        "_active_run": {
            "phase": "01-literature",
            "run_index": 0,
            "pid": 43_210,
            "started": started,
            "process_identity": "untrusted-legacy-marker-value",
        },
    }
    (log / "project.yaml").write_text(yaml.safe_dump(legacy), encoding="utf-8")

    migrated = state.load(project)
    run = migrated["phases"]["01-literature"]["runs"][0]
    active = migrated["active_run"]

    assert run["status"] == "running"
    assert run["process_pid"] == 43_210
    assert run["process_identity"] is None
    assert active["run_id"] == run["run_id"]
    assert active["pid"] == 43_210
    assert active["process_identity"] is None
    assert state.get_active_run(project) == active
    assert state.get_run(project, "01-literature", run["run_id"])[
        "process_pid"
    ] == 43_210


@pytest.mark.parametrize(
    "marker",
    [
        {"phase": "missing-phase", "run_index": 0, "pid": 43_211},
        {"phase": "01-literature", "run_index": 1, "pid": 43_211},
        {"phase": "01-literature", "run_index": 0, "pid": True},
        {"phase": "01-literature", "run_index": 0, "pid": "43211"},
        {"phase": "01-literature", "run_index": 0, "pid": 1 << 31},
    ],
)
def test_load_does_not_attach_an_invalid_legacy_active_pid(
    tmp_path: Path,
    marker: dict[str, object],
) -> None:
    project = tmp_path / "legacy-invalid-active"
    log = project / ".log"
    log.mkdir(parents=True)
    legacy = {
        "project": {"id": "old"},
        "phases": {
            "01-literature": {
                "status": "running",
                "runs": [{
                    "mode": "legacy",
                    "rounds_requested": 1,
                    "started": "2026-01-01T00:00:00Z",
                    "rounds": [],
                }],
            }
        },
        "_active_run": marker,
    }
    (log / "project.yaml").write_text(yaml.safe_dump(legacy), encoding="utf-8")

    migrated = state.load(project)
    run = migrated["phases"]["01-literature"]["runs"][0]

    assert run["status"] == "running"
    assert run["process_pid"] is None
    assert migrated["active_run"]["pid"] is None


def test_load_seals_a_safe_legacy_approved_summary(tmp_path: Path) -> None:
    project = tmp_path / "legacy"
    log = project / ".log"
    log.mkdir(parents=True)
    summary = project / "old.md"
    summary.write_text("# Legacy accepted result\n", encoding="utf-8")
    legacy = {
        "project": {"id": "old"},
        "phases": {
            "01-literature": {
                "status": "completed",
                "runs": [{
                    "mode": "legacy",
                    "rounds_requested": 1,
                    "completed": "2026-01-01T00:01:00Z",
                    "rounds": [],
                    "final_summary": "old.md",
                }],
            }
        },
    }
    (log / "project.yaml").write_text(yaml.safe_dump(legacy), encoding="utf-8")

    migrated = state.load(project)
    run = migrated["phases"]["01-literature"]["runs"][0]

    assert run["summary_sha256"] == hashlib.sha256(summary.read_bytes()).hexdigest()
    report = state.prerequisite_report(
        project, "02-method", {"02-method": ["01-literature"]}
    )
    assert report["satisfied"] is True


def test_legacy_migration_rejects_links_in_control_history(tmp_path: Path) -> None:
    project = tmp_path / "legacy"
    log = project / ".log"
    runs = log / "runs"
    runs.mkdir(parents=True)
    (log / "project.yaml").write_text("project: {}\nphases: {}\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        (runs / "linked.log").symlink_to(outside)
    except OSError:
        pytest.skip("symbolic links are not available in this test environment")

    with pytest.raises(state.StateValidationError, match="symbolic link"):
        state.load(project)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_legacy_migration_rejects_a_windows_source_junction(tmp_path: Path) -> None:
    project = tmp_path / "legacy"
    log = project / ".log"
    runs = log / "runs"
    runs.mkdir(parents=True)
    (log / "project.yaml").write_text("project: {}\nphases: {}\n", encoding="utf-8")
    outside = tmp_path / "source-outside"
    outside.mkdir()
    (outside / "outside.log").write_text("outside", encoding="utf-8")
    junction = runs / "linked"
    _create_windows_directory_junction(junction, outside)

    try:
        with pytest.raises(state.StateValidationError, match="reparse point"):
            state.load(project)
    finally:
        if junction.exists():
            junction.rmdir()

    assert not state.state_file(project).exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_legacy_migration_rejects_a_windows_destination_junction(
    tmp_path: Path,
) -> None:
    project = tmp_path / "legacy"
    runs = project / ".log" / "runs"
    runs.mkdir(parents=True)
    (project / ".log" / "project.yaml").write_text(
        "project: {}\nphases: {}\n", encoding="utf-8"
    )
    (runs / "run.log").write_text("legacy run", encoding="utf-8")
    control = state.state_dir(project)
    control.mkdir(parents=True)
    outside = tmp_path / "destination-outside"
    outside.mkdir()
    junction = control / "runs"
    _create_windows_directory_junction(junction, outside)

    try:
        with pytest.raises(state.StateValidationError, match="reparse point"):
            state.load(project)
    finally:
        if junction.exists():
            junction.rmdir()

    assert not (outside / "run.log").exists()
    assert not state.state_file(project).exists()


def test_project_state_yaml_read_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "bounded-state"
    project.mkdir()
    control = state.state_dir(project)
    control.mkdir(parents=True)
    state.state_file(project).write_text(
        "project: {}\nphases: {}\n", encoding="utf-8"
    )
    monkeypatch.setattr(state, "MAX_STATE_FILE_BYTES", 8)

    with pytest.raises(state.StateValidationError, match="safety limit"):
        state.load(project)


def test_round_artifacts_are_rejected_above_the_safety_limit(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = state.reserve_run(
        project, "01-literature", "bounded artifact", rounds_requested=1
    )
    state.set_process_pid(project, "01-literature", run_id, 8123)
    state.start_round(project, "01-literature", run_id, "bounded", ["lead"], 1)
    artifact = project / "oversized.txt"
    artifact.write_bytes(b"12345")
    monkeypatch.setattr(state, "MAX_RUN_ARTIFACT_BYTES", 4)

    with pytest.raises(state.StateValidationError, match="safety limit"):
        state.complete_round(project, "01-literature", run_id, 1, [artifact])


def test_phase_four_requires_and_preserves_a_pre_result_protocol_checkpoint(
    project: Path,
) -> None:
    phase = state.NUMERICAL_VALIDATION_PHASE
    dependencies = {**DEPENDENCIES, phase: []}
    state.init(
        project,
        "project-001",
        "example",
        "Example",
        phase_slugs=[*DEPENDENCIES, phase],
        dependencies=dependencies,
    )
    run_id = state.reserve_run(
        project,
        phase,
        "numerical validation",
        rounds_requested=4,
        dependencies=dependencies,
    )
    output_root = project / "numerical" / "run" / "01"
    output_root.mkdir(parents=True)
    checkpoint = output_root / "protocol-checkpoint.json"
    manifest = {
        "schema_version": 5,
        "run_id": run_id,
        "phase_slug": phase,
        "timeout_minutes": 30,
        "output_root": str(output_root),
        "protocol_checkpoint": {
            "schema_version": state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "path": str(checkpoint),
            "max_bytes": state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        },
    }
    manifest_path = state.state_dir(project) / "runs" / phase / f"{run_id}.manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state.seal_run_manifest(project, phase, run_id, manifest_path)
    state.set_process_pid(project, phase, run_id, 9901)
    state.start_round(project, phase, run_id, "Prespecify the study", ["data_scientist"], 1)
    report = output_root / "round-01" / "data_scientist.md"
    report.parent.mkdir()
    report.write_text("Scientific completion outcome: Complete\n", encoding="utf-8")

    with pytest.raises(state.StateValidationError, match="was not sealed"):
        state.complete_round(project, phase, run_id, 1, [report])

    protocol = output_root / "study-config.yaml"
    protocol.write_text("replications: 200\nseed: 42\n", encoding="utf-8")
    payload = protocol.read_bytes()
    checkpoint.write_text(
        json.dumps({
            "schema_version": state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "phase_slug": phase,
            "run_id": run_id,
            "main_results_generated": False,
            "protocol_files": [{
                "path": protocol.relative_to(project).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
                "purpose": "Executable numerical study configuration",
            }],
        }),
        encoding="utf-8",
    )
    record = state.seal_protocol_checkpoint(project, phase, run_id, checkpoint)
    assert record["data"]["main_results_generated"] is False
    assert record["data"]["protocol_files"][0]["path"] == (
        protocol.relative_to(project).as_posix()
    )

    protocol.write_text("replications: 20\nseed: 42\n", encoding="utf-8")
    with pytest.raises(state.StateValidationError, match="does not match"):
        state.complete_round(project, phase, run_id, 1, [report])
    protocol.write_bytes(payload)
    state.complete_round(project, phase, run_id, 1, [report])

    assert state.get_run(project, phase, run_id)["protocol_checkpoint"]["sealed_at"]


def test_modern_phase_four_separates_protocol_and_result_tasks(
    project: Path,
) -> None:
    phase = state.NUMERICAL_VALIDATION_PHASE
    dependencies = {**DEPENDENCIES, phase: []}
    state.init(
        project,
        "project-001",
        "example",
        "Example",
        phase_slugs=[*DEPENDENCIES, phase],
        dependencies=dependencies,
    )
    run_id = state.reserve_run(
        project,
        phase,
        "separate protocol stage",
        rounds_requested=4,
        dependencies=dependencies,
    )
    output_root = project / "numerical" / "run" / "01"
    protocol_root = output_root / "protocol"
    protocol_root.mkdir(parents=True)
    checkpoint = output_root / "protocol-checkpoint.json"
    manifest = {
        "schema_version": 6,
        "run_id": run_id,
        "phase_slug": phase,
        "timeout_minutes": 30,
        "output_root": str(output_root),
        "protocol_checkpoint": {
            "schema_version": state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "path": str(checkpoint),
            "protocol_root": str(protocol_root),
            "max_bytes": state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        },
    }
    manifest_path = (
        state.state_dir(project) / "runs" / phase / f"{run_id}.manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state.seal_run_manifest(project, phase, run_id, manifest_path)
    state.set_process_pid(project, phase, run_id, 9902)
    state.start_round(
        project, phase, run_id, "Prespecify, then test", ["data_scientist"], 1
    )

    protocol_brief = manifest_path.with_name(f"{run_id}.protocol.task.md")
    protocol_brief.write_text("Write and seal only the protocol.", encoding="utf-8")
    protocol_digest = hashlib.sha256(protocol_brief.read_bytes()).hexdigest()
    result_brief = manifest_path.with_name(f"{run_id}.result.task.md")
    result_brief.write_text("Run only the sealed protocol.", encoding="utf-8")
    result_digest = hashlib.sha256(result_brief.read_bytes()).hexdigest()

    with pytest.raises(state.StateConflict, match="single run-scoped protocol task"):
        state.seal_protocol_checkpoint(project, phase, run_id, checkpoint)

    state.record_task(
        project,
        phase,
        run_id,
        1,
        role="data_scientist",
        task_id="protocol-task",
        title="Protocol",
        task_kind="protocol",
        brief_path=protocol_brief,
        brief_sha256=protocol_digest,
    )
    with pytest.raises(state.StateValidationError, match="was not sealed"):
        state.record_task(
            project,
            phase,
            run_id,
            1,
            role="data_scientist",
            task_id="result-task-early",
            title="Result",
            task_kind="result",
            brief_path=result_brief,
            brief_sha256=result_digest,
        )

    outside_protocol = output_root / "unscoped-config.yaml"
    outside_protocol.write_text("replications: 20\n", encoding="utf-8")

    def write_checkpoint(protocol_file: Path) -> None:
        payload = protocol_file.read_bytes()
        checkpoint.write_text(
            json.dumps({
                "schema_version": state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
                "phase_slug": phase,
                "run_id": run_id,
                "main_results_generated": False,
                "protocol_files": [{
                    "path": protocol_file.relative_to(project).as_posix(),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size": len(payload),
                    "purpose": "Executable numerical study configuration",
                }],
            }),
            encoding="utf-8",
        )

    write_checkpoint(outside_protocol)
    with pytest.raises(state.StateValidationError, match="run-scoped protocol"):
        state.seal_protocol_checkpoint(project, phase, run_id, checkpoint)

    protocol = protocol_root / "study-config.yaml"
    protocol.write_text("replications: 200\nseed: 42\n", encoding="utf-8")
    write_checkpoint(protocol)
    state.seal_protocol_checkpoint(project, phase, run_id, checkpoint)
    state.record_task(
        project,
        phase,
        run_id,
        1,
        role="data_scientist",
        task_id="result-task",
        title="Result",
        task_kind="result",
        brief_path=result_brief,
        brief_sha256=result_digest,
    )
    sealed_again = state.seal_protocol_checkpoint(
        project, phase, run_id, checkpoint
    )

    tasks = state.get_run(project, phase, run_id)["rounds"][0]["tasks"]
    assert [task["task_kind"] for task in tasks] == ["protocol", "result"]
    assert sealed_again["sha256"] == hashlib.sha256(
        checkpoint.read_bytes()
    ).hexdigest()


def test_schema_seven_phase_four_seals_an_isolated_protocol_workspace(
    project: Path,
) -> None:
    phase = state.NUMERICAL_VALIDATION_PHASE
    dependencies = {**DEPENDENCIES, phase: []}
    state.init(
        project,
        "project-001",
        "example",
        "Example",
        phase_slugs=[*DEPENDENCIES, phase],
        dependencies=dependencies,
    )
    run_id = state.reserve_run(
        project,
        phase,
        "isolated protocol stage",
        rounds_requested=1,
        dependencies=dependencies,
    )
    output_root = project / "numerical" / "run" / "01"
    protocol_root = output_root / "protocol"
    result_root = output_root / "round-01"
    protocol_root.mkdir(parents=True)
    result_root.mkdir()
    checkpoint = protocol_root / "protocol-checkpoint.json"
    summary = project / "phase-summaries" / phase / f"{run_id}.html"
    decision = summary.with_suffix(".decision.json")
    manifest = {
        "schema_version": 7,
        "run_id": run_id,
        "phase_slug": phase,
        "rounds_requested": 1,
        "timeout_minutes": 30,
        "output_root": str(output_root),
        "summary_path": str(summary),
        "decision_path": str(decision),
        "phase": {
            "pattern": "sequential",
            "stages": [{"role": "data_scientist"}],
        },
        "protocol_checkpoint": {
            "schema_version": state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "path": str(checkpoint),
            "protocol_root": str(protocol_root),
            "max_bytes": state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        },
    }
    manifest_path = (
        state.state_dir(project) / "runs" / phase / f"{run_id}.manifest.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    state.seal_run_manifest(project, phase, run_id, manifest_path)
    state.start_round(
        project, phase, run_id, "Prespecify, then test", ["data_scientist"], 1
    )

    protocol_brief = manifest_path.with_name(f"{run_id}.protocol.task.md")
    protocol_brief.write_text("Write only the protocol.", encoding="utf-8")
    result_brief = manifest_path.with_name(f"{run_id}.result.task.md")
    result_brief.write_text("Run the sealed protocol.", encoding="utf-8")
    state.record_task(
        project,
        phase,
        run_id,
        1,
        role="data_scientist",
        task_id="protocol-task",
        title="Protocol",
        task_kind="protocol",
        brief_path=protocol_brief,
        brief_sha256=hashlib.sha256(protocol_brief.read_bytes()).hexdigest(),
        workspace_path=protocol_root,
    )

    protocol = protocol_root / "study-design.yaml"
    protocol.write_text("replications: 200\nseed: 42\n", encoding="utf-8")
    protocol_payload = protocol.read_bytes()
    checkpoint.write_text(
        json.dumps({
            "schema_version": state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "phase_slug": phase,
            "run_id": run_id,
            "main_results_generated": False,
            "protocol_files": [{
                "path": protocol.relative_to(project).as_posix(),
                "sha256": hashlib.sha256(protocol_payload).hexdigest(),
                "size": len(protocol_payload),
                "purpose": "Fix the replication count and random seed.",
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(state.StateConflict, match="isolated protocol task"):
        state.seal_protocol_checkpoint(project, phase, run_id, checkpoint)
    with pytest.raises(state.StateValidationError, match="protocol-stage report"):
        state.seal_protocol_checkpoint(
            project,
            phase,
            run_id,
            checkpoint,
            isolated_task_completed=True,
        )

    protocol_report = protocol_root / "protocol-stage.md"
    protocol_report.write_text(
        "Scientific completion outcome: Complete\n\n## Protocol checkpoint\nReady.\n",
        encoding="utf-8",
    )
    undeclared_result = protocol_root / "premature-results.csv"
    undeclared_result.write_text("estimate\n1.0\n", encoding="utf-8")
    with pytest.raises(state.StateValidationError, match="unlisted file"):
        state.seal_protocol_checkpoint(
            project,
            phase,
            run_id,
            checkpoint,
            isolated_task_completed=True,
        )
    undeclared_result.unlink()

    sealed = state.seal_protocol_checkpoint(
        project,
        phase,
        run_id,
        checkpoint,
        isolated_task_completed=True,
    )
    assert sealed["protocol_report"]["scientific_outcome"] == "Complete"
    assert sealed["protocol_report"]["path"].endswith("protocol/protocol-stage.md")

    state.record_task(
        project,
        phase,
        run_id,
        1,
        role="data_scientist",
        task_id="result-task",
        title="Result",
        task_kind="result",
        brief_path=result_brief,
        brief_sha256=hashlib.sha256(result_brief.read_bytes()).hexdigest(),
        workspace_path=result_root,
    )
    result_report = result_root / "data_scientist.md"
    result_report.write_text(
        "Scientific completion outcome: Complete\n", encoding="utf-8"
    )
    state.complete_round(project, phase, run_id, 1, [result_report])

    summary.parent.mkdir(parents=True)
    summary.write_text("<h1>Numerical validation</h1>", encoding="utf-8")
    phase_four_decision = decision_payload("Complete", phase=phase, run=run_id)
    phase_four_decision["schema_version"] = 2
    phase_four_decision["selected_scientific_object"] = None
    decision.write_text(json.dumps(phase_four_decision), encoding="utf-8")
    protocol.write_text("replications: 20\nseed: 42\n", encoding="utf-8")
    with pytest.raises(state.StateValidationError, match="does not match"):
        state.stage_run_submission(project, phase, run_id, summary, decision)
    protocol.write_bytes(protocol_payload)
    state.stage_run_submission(project, phase, run_id, summary, decision)

    protocol_report.write_text(
        "Scientific completion outcome: Partial\n", encoding="utf-8"
    )
    with pytest.raises(state.StateValidationError, match="protocol-stage report"):
        state.finalize_run_submission(project, phase, run_id)
