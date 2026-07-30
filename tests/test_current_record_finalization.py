from __future__ import annotations

import copy
from pathlib import Path

import pytest

from core import phase_records
from core import project_state as state
from core import promotion_journal
from core import promotion_recovery


PHASE = phase_records.THEORY_PHASE
METHOD_IDENTITY = {
    "stable_id": "method-a",
    "version": "v1",
    "definition_sha256": "a" * 64,
}


def _manifest(output_root: Path, identity: dict | None = None) -> dict:
    method = dict(identity or METHOD_IDENTITY)
    return {
        "output_root": str(output_root),
        "method_selection": {
            "stable_id": method["stable_id"],
            "version": method["version"],
        },
        "snapshots": {
            "selected_method": {
                "sha256": method["definition_sha256"],
            }
        },
    }




def _run(run_id: str, outcome: str, *, status: str) -> dict:
    return {
        "run_id": run_id,
        "status": status,
        "decision_record": {
            "data": {
                "scientific_outcome": outcome,
            }
        },
        "phase_record_seal": {
            "schema_version": 1,
            "phase_slug": PHASE,
            "scientific_outcome": outcome,
            "eligible": outcome == "Complete",
            "kind": "theory" if outcome == "Complete" else "none",
            "data": {} if outcome == "Complete" else None,
        },
    }


def _state_with_current(rerun: dict) -> tuple[dict, dict]:
    previous = {
        "run_id": "run-current",
        "status": "completed",
        "phase_record": {
            "schema_version": 1,
            "source_run_id": "run-current",
            "scientific_outcome": "Complete",
            "current_updated": True,
            "method_identity": dict(METHOD_IDENTITY),
        },
    }
    phase = {
        "runs": [previous, rerun],
        "current_run": previous["run_id"],
        "current_runs": {METHOD_IDENTITY["stable_id"]: previous["run_id"]},
        "approved_run": previous["run_id"],
        "publication_readiness": "ready",
        "stale": False,
    }
    data = {
        "schema_version": state.SCHEMA_VERSION,
        "project": {"id": "project-test"},
        "dependencies": {PHASE: []},
        "phases": {PHASE: phase},
        "active_run": None,
    }
    return data, phase


@pytest.fixture(autouse=True)
def _synthetic_runs_have_no_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        phase_records,
        "plan_output_promotion",
        lambda *_args, **_kwargs: None,
    )


def test_incomplete_rerun_keeps_prior_current_record_and_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rerun = _run("run-partial", "Partial", status="submitting")
    data, phase = _state_with_current(rerun)
    saved: dict = {}

    monkeypatch.setattr(
        phase_records,
        "promote_output",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        state,
        "_save_unlocked",
        lambda _project, payload: saved.update(data=copy.deepcopy(payload)),
    )

    state._finalize_current_record_submission_unlocked(
        tmp_path,
        data,
        PHASE,
        phase,
        rerun,
        _manifest(tmp_path / "run-partial"),
        "2026-07-29T00:00:00+00:00",
    )

    assert phase["current_run"] == "run-current"
    assert phase["approved_run"] == "run-current"
    assert phase["publication_readiness"] == "ready"
    assert phase["runs"][0]["status"] == "completed"
    assert rerun["status"] == "completed"
    assert rerun["publication_readiness"] == "partial"
    assert rerun["phase_record"]["current_updated"] is False
    assert saved["data"]["phases"][PHASE]["current_run"] == "run-current"


def test_state_save_failure_rolls_back_canonical_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rerun = _run("run-replacement", "Complete", status="submitting")
    data, phase = _state_with_current(rerun)
    promotion = {
        "generation": 2,
        "method_identity": dict(METHOD_IDENTITY),
        "_promotion_transaction": {"token": "t"},
    }
    rolled_back: list[dict] = []
    committed: list[dict] = []

    monkeypatch.setattr(
        phase_records,
        "promote_output",
        lambda *_args, **_kwargs: promotion,
    )
    monkeypatch.setattr(
        phase_records,
        "rollback_promotion",
        lambda _project, _phase, value: rolled_back.append(dict(value)),
    )
    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda _project, _phase, value: committed.append(dict(value)),
    )

    def fail_save(_project: Path, _payload: dict) -> None:
        raise OSError("simulated state write failure")

    monkeypatch.setattr(state, "_save_unlocked", fail_save)

    with pytest.raises(OSError, match="simulated state write failure"):
        state._finalize_current_record_submission_unlocked(
            tmp_path,
            data,
            PHASE,
            phase,
            rerun,
            _manifest(tmp_path / "run-replacement"),
            "2026-07-29T00:00:00+00:00",
        )

    assert rolled_back == [promotion]
    assert committed == []


def test_state_save_reports_uncertain_commit_after_directory_sync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    payload = {
        "schema_version": state.SCHEMA_VERSION,
        "project": {"id": "project-test"},
        "phases": {},
    }

    def fail_directory_sync(_directory: Path) -> None:
        raise OSError("simulated directory sync failure")

    monkeypatch.setattr(state, "_sync_state_directory", fail_directory_sync)

    with pytest.raises(
        state.StateCommitUncertain,
        match="project state was replaced",
    ):
        state._save_unlocked(project, payload)

    assert state._read_unlocked(project) == payload


def test_uncertain_state_commit_keeps_promotion_and_recovery_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rerun = _run("run-replacement", "Complete", status="submitting")
    data, phase = _state_with_current(rerun)
    promotion = {
        "generation": 2,
        "method_identity": dict(METHOD_IDENTITY),
        "_promotion_transaction": {"token": "t"},
    }
    rolled_back: list[dict] = []
    committed: list[dict] = []

    monkeypatch.setattr(
        phase_records,
        "promote_output",
        lambda *_args, **_kwargs: promotion,
    )
    monkeypatch.setattr(
        phase_records,
        "rollback_promotion",
        lambda _project, _phase, value: rolled_back.append(dict(value)),
    )
    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda _project, _phase, value: committed.append(dict(value)),
    )

    def fail_after_state_replace(*_args: object) -> None:
        raise state.StateCommitUncertain("simulated uncertain commit")

    monkeypatch.setattr(state, "_save_unlocked", fail_after_state_replace)

    with pytest.raises(state.StateCommitUncertain):
        state._finalize_current_record_submission_unlocked(
            tmp_path,
            data,
            PHASE,
            phase,
            rerun,
            _manifest(tmp_path / "run-replacement"),
            "2026-07-29T00:00:00+00:00",
        )

    assert rolled_back == []
    assert committed == []
    journals = promotion_journal.read_all(state.state_dir(tmp_path))
    assert len(journals) == 1
    assert journals[0]["status"] == "promoted"
    assert journals[0]["promotion"] == promotion


def test_successful_state_save_commits_canonical_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rerun = _run("run-replacement", "Complete", status="submitting")
    data, phase = _state_with_current(rerun)
    promotion = {
        "generation": 2,
        "method_identity": dict(METHOD_IDENTITY),
        "_promotion_transaction": {"token": "t"},
    }
    committed: list[dict] = []

    monkeypatch.setattr(
        phase_records,
        "promote_output",
        lambda *_args, **_kwargs: promotion,
    )
    monkeypatch.setattr(state, "_save_unlocked", lambda *_args: None)
    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda _project, _phase, value: committed.append(dict(value)),
    )

    state._finalize_current_record_submission_unlocked(
        tmp_path,
        data,
        PHASE,
        phase,
        rerun,
        _manifest(tmp_path / "run-replacement"),
        "2026-07-29T00:00:00+00:00",
    )

    assert committed == [promotion]
    assert phase["current_run"] == "run-replacement"
    assert phase["runs"][0]["status"] == "superseded"
    assert rerun["status"] == "completed"
    assert rerun["phase_record"]["current_updated"] is True
    assert phase["current_runs"] == {"method-a": "run-replacement"}


def test_method_branches_keep_independent_current_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity_b = {
        "stable_id": "method-b",
        "version": "v1",
        "definition_sha256": "b" * 64,
    }
    run_b = _run("run-b", "Complete", status="submitting")
    data, phase = _state_with_current(run_b)

    def promotion_for_manifest(*_args, **kwargs) -> dict:
        return {
            "generation": 1,
            "method_identity": phase_records.manifest_method_identity(
                kwargs["manifest"]
            ),
        }

    monkeypatch.setattr(
        phase_records,
        "promote_output",
        promotion_for_manifest,
    )
    monkeypatch.setattr(state, "_save_unlocked", lambda *_args: None)
    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda *_args: None,
    )

    state._finalize_current_record_submission_unlocked(
        tmp_path,
        data,
        PHASE,
        phase,
        run_b,
        _manifest(tmp_path / "run-b", identity_b),
        "2026-07-29T00:00:00+00:00",
    )

    assert phase["runs"][0]["status"] == "completed"
    assert phase["current_runs"] == {
        "method-a": "run-current",
        "method-b": "run-b",
    }

    run_a2 = _run("run-a2", "Complete", status="submitting")
    phase["runs"].append(run_a2)
    state._finalize_current_record_submission_unlocked(
        tmp_path,
        data,
        PHASE,
        phase,
        run_a2,
        _manifest(tmp_path / "run-a2"),
        "2026-07-29T01:00:00+00:00",
    )

    assert phase["runs"][0]["status"] == "superseded"
    assert run_b["status"] == "completed"
    assert phase["current_runs"] == {
        "method-a": "run-a2",
        "method-b": "run-b",
    }

def test_compact_phase_record_keeps_the_published_knowledge_digest() -> None:
    digest = "d" * 64

    record = state._compact_phase_record_state(
        {"run_id": "run-current"},
        "Complete",
        {
            "generation": 2,
            "knowledge_sha256": digest,
            "knowledge_size": 512,
        },
    )
    assert record["knowledge_sha256"] == digest
    assert "knowledge_size" not in record



def test_finalization_orders_plan_journal_state_and_post_state_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rerun = _run("run-ordered", "Complete", status="submitting")
    data, phase = _state_with_current(rerun)
    operation = promotion_journal.operation_id(PHASE, "run-ordered")
    promotion = {
        "kind": "test-promotion",
        "generation": 2,
        "method_identity": dict(METHOD_IDENTITY),
    }
    intent = {
        "schema_version": 1,
        "kind": "method_phase_directory_promotion_intent",
        "operation_id": operation,
        "phase_slug": PHASE,
        "source_run_id": "run-ordered",
        "method_identity": dict(METHOD_IDENTITY),
        "planned_promotion": promotion,
        "knowledge_event": None,
    }
    prepared = {
        "phase_slug": PHASE,
        "run_id": "run-ordered",
        "operation_id": operation,
        "status": "prepared",
        "intent": intent,
        "promotion": None,
    }
    promoted = {
        **prepared,
        "status": "promoted",
        "promotion": promotion,
    }
    calls: list[str] = []

    monkeypatch.setattr(
        phase_records,
        "plan_output_promotion",
        lambda *_args, **_kwargs: (
            calls.append("plan"),
            intent,
        )[1],
    )
    monkeypatch.setattr(
        phase_records,
        "validate_promotion_intent",
        lambda *_args, **_kwargs: (
            calls.append("validate"),
            intent,
        )[1],
    )
    monkeypatch.setattr(
        promotion_journal,
        "prepare",
        lambda *_args, **_kwargs: (
            calls.append("prepare"),
            prepared,
        )[1],
    )
    monkeypatch.setattr(
        phase_records,
        "promote_output",
        lambda *_args, **_kwargs: (
            calls.append("execute"),
            promotion,
        )[1],
    )
    monkeypatch.setattr(
        promotion_journal,
        "record_promotion",
        lambda *_args, **_kwargs: (
            calls.append("record"),
            promoted,
        )[1],
    )
    monkeypatch.setattr(
        state,
        "_save_unlocked",
        lambda *_args, **_kwargs: calls.append("save"),
    )
    monkeypatch.setattr(
        promotion_recovery,
        "complete_after_state_decision",
        lambda *_args, **_kwargs: calls.append("post-state"),
    )

    state._finalize_current_record_submission_unlocked(
        tmp_path,
        data,
        PHASE,
        phase,
        rerun,
        _manifest(tmp_path / "run-ordered"),
        "2026-07-29T00:00:00+00:00",
    )

    assert calls == [
        "plan",
        "validate",
        "prepare",
        "execute",
        "record",
        "save",
        "post-state",
    ]
