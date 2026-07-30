from __future__ import annotations

from pathlib import Path

import pytest

from core import project_state as state


SOURCE = "01-literature-review"
TARGET = state.METHOD_DEVELOPMENT_PHASE
DEPENDENCIES = {SOURCE: [], TARGET: [SOURCE]}


def _completed_run(run_id: str, *, current_updated: bool) -> dict:
    return {
        "run_id": run_id,
        "status": "completed",
        "submitted_at": "2026-07-29T00:00:00+00:00",
        "final_summary": f"phase-summaries/{run_id}.html",
        "decision_record": {
            "data": {
                "scientific_outcome": "Complete",
            }
        },
        "phase_record": {
            "schema_version": 1,
            "source_run_id": run_id,
            "scientific_outcome": "Complete",
            "current_updated": current_updated,
        },
    }


def _data() -> dict:
    current = _completed_run("run-current", current_updated=True)
    newer_history = _completed_run("run-newer-history", current_updated=False)
    return {
        "phases": {
            SOURCE: {
                "runs": [current, newer_history],
                "current_run": current["run_id"],
                "approved_run": current["run_id"],
                "stale": False,
                "status": "completed",
                "publication_readiness": "ready",
            },
            TARGET: {"runs": []},
        }
    }


def _trust_integrity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        state,
        "_validate_run_integrity",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        state,
        "_validate_recorded_manifest",
        lambda *_args, **_kwargs: {"schema_version": 12},
    )


def test_current_record_policy_uses_pointer_not_newest_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _trust_integrity(monkeypatch)

    report = state._current_record_report_from_data(
        _data(),
        TARGET,
        DEPENDENCIES,
        tmp_path,
    )

    assert report["policy"] == "current_records"
    assert report["satisfied"] is True
    assert report["requirements"][0]["current_run"] == "run-current"
    assert report["requirements"][0]["reason"] == (
        "current, completed, and intact"
    )


def test_current_record_policy_rejects_stale_current_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _trust_integrity(monkeypatch)
    data = _data()
    data["phases"][SOURCE]["stale"] = True

    report = state._current_record_report_from_data(
        data,
        TARGET,
        DEPENDENCIES,
        tmp_path,
    )

    assert report["satisfied"] is False
    assert report["blockers"] == [SOURCE]
    assert report["requirements"][0]["reason"] == "the current result is stale"


def test_current_record_policy_rejects_unpromoted_current_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _trust_integrity(monkeypatch)
    data = _data()
    phase = data["phases"][SOURCE]
    phase["current_run"] = "run-newer-history"
    phase["approved_run"] = "run-newer-history"

    report = state._current_record_report_from_data(
        data,
        TARGET,
        DEPENDENCIES,
        tmp_path,
    )

    assert report["satisfied"] is False
    assert report["requirements"][0]["reason"] == (
        "the current run has no verified promoted record"
    )


def test_active_run_context_compares_current_pointer_not_legacy_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _trust_integrity(monkeypatch)
    data = _data()
    data["phases"][SOURCE]["approved_run"] = "legacy-approved-run"
    run = {
        "prerequisite_snapshot": {
            "policy": "current_records",
            "requirements": [
                {
                    "phase": SOURCE,
                    "satisfied": True,
                    "current_run": "run-current",
                    "completed_run": "run-current",
                    "approved_run": "legacy-approved-run",
                    "stale": False,
                }
            ],
        },
        "context_inputs": [],
        "override_metadata": None,
    }

    report = state._approval_context_report_from_data(
        data,
        TARGET,
        run,
        DEPENDENCIES,
        tmp_path,
    )

    assert report["requires_acknowledgement"] is False
    assert report["changed_sources"] == []


def test_active_run_context_reports_changed_current_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _trust_integrity(monkeypatch)
    data = _data()
    newer = data["phases"][SOURCE]["runs"][1]
    newer["phase_record"]["current_updated"] = True
    data["phases"][SOURCE]["current_run"] = "run-newer-history"
    run = {
        "prerequisite_snapshot": {
            "policy": "current_records",
            "requirements": [
                {
                    "phase": SOURCE,
                    "satisfied": True,
                    "current_run": "run-current",
                    "completed_run": "run-current",
                }
            ],
        },
        "context_inputs": [],
        "override_metadata": None,
    }

    report = state._approval_context_report_from_data(
        data,
        TARGET,
        run,
        DEPENDENCIES,
        tmp_path,
    )

    assert report["requires_acknowledgement"] is True
    assert report["changed_sources"] == [{
        "phase": SOURCE,
        "launch_run": "run-current",
        "current_run": "run-newer-history",
        "reason": "the current prerequisite result changed after launch",
    }]


def test_active_run_context_reports_stale_current_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _trust_integrity(monkeypatch)
    data = _data()
    data["phases"][SOURCE]["stale"] = True
    run = {
        "prerequisite_snapshot": {
            "policy": "current_records",
            "requirements": [
                {
                    "phase": SOURCE,
                    "satisfied": True,
                    "current_run": "run-current",
                    "completed_run": "run-current",
                }
            ],
        },
        "context_inputs": [],
        "override_metadata": None,
    }

    report = state._approval_context_report_from_data(
        data,
        TARGET,
        run,
        DEPENDENCIES,
        tmp_path,
    )

    assert report["requires_acknowledgement"] is True
    assert report["changed_sources"][0]["launch_run"] == "run-current"
    assert report["changed_sources"][0]["current_run"] == "run-current"
    assert "missing, stale, or changed" in report["changed_sources"][0]["reason"]




def test_current_record_policy_keeps_partial_phase_two_visible_as_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _trust_integrity(monkeypatch)
    data = _data()
    data["phases"][state.METHOD_DEVELOPMENT_PHASE] = {
        **data["phases"].pop(SOURCE),
        "publication_readiness": "partial",
    }
    target = state.IDEA_EVALUATION_PHASE
    dependencies = {
        state.METHOD_DEVELOPMENT_PHASE: [],
        target: [state.METHOD_DEVELOPMENT_PHASE],
    }

    report = state._current_record_report_from_data(
        data,
        target,
        dependencies,
        tmp_path,
    )

    assert report["satisfied"] is False
    assert "scientifically partial" in report["requirements"][0]["reason"]
