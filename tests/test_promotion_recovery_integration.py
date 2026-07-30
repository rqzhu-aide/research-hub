"""Focused integration tests for promotion post-state side effects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core import (
    knowledge_events,
    knowledge_graph,
    phase_records,
    project_state,
    promotion_journal,
    promotion_recovery,
)


PHASE = phase_records.THEORY_PHASE
IDENTITY = {
    "stable_id": "method-a",
    "version": "v1",
    "definition_sha256": "a" * 64,
}


def _intent(run_id: str) -> dict[str, Any]:
    operation = promotion_journal.operation_id(PHASE, run_id)
    event = {
        "phase_slug": PHASE,
        "event_id": "b" * 64,
        "event_sha256": "c" * 64,
        "current_method_identity": dict(IDENTITY),
    }
    return {
        "schema_version": 1,
        "kind": "method_phase_directory_promotion_intent",
        "operation_id": operation,
        "phase_slug": PHASE,
        "source_run_id": run_id,
        "method_identity": dict(IDENTITY),
        "planned_promotion": {
            "kind": "test-promotion",
            "generation": 2,
        },
        "knowledge_event": event,
    }


def _journal(
    project: Path,
    run_id: str,
    *,
    promoted: bool,
) -> tuple[Path, dict[str, Any]]:
    control = project_state.state_dir(project)
    intent = _intent(run_id)
    journal = promotion_journal.prepare(
        control,
        project,
        PHASE,
        run_id,
        intent=intent,
    )
    if promoted:
        journal = promotion_journal.record_promotion(
            control,
            run_id,
            intent["planned_promotion"],
        )
    return control, journal


def _manifest(output: Path) -> dict[str, Any]:
    return {
        "output_root": str(output),
        "method_selection": {
            "stable_id": IDENTITY["stable_id"],
            "version": IDENTITY["version"],
        },
        "snapshots": {
            "selected_method": {
                "sha256": IDENTITY["definition_sha256"],
            }
        },
    }


def test_current_completion_orders_event_graph_commit_and_real_control_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    control, journal = _journal(project, "run-order", promoted=True)
    calls: list[tuple[str, Any]] = []

    monkeypatch.setattr(
        knowledge_events,
        "_write_event_unlocked",
        lambda _project, _event: calls.append(("event", None)),
    )
    monkeypatch.setattr(
        knowledge_graph,
        "refresh_shadow_graph_unlocked",
        lambda _project, stable_id: calls.append(("graph", stable_id)),
    )
    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda _project, _phase, value: calls.append(
            ("commit", dict(value))
        ),
    )
    monkeypatch.setattr(
        promotion_journal,
        "remove",
        lambda supplied, run_id: calls.append(
            ("remove", (Path(supplied), run_id))
        ),
    )

    promotion_recovery.complete_after_state_decision(
        project,
        control,
        journal,
        make_current=True,
        recover_filesystem=False,
    )

    assert [name for name, _ in calls] == [
        "event",
        "graph",
        "commit",
        "remove",
    ]
    assert calls[-1][1] == (control, "run-order")


def test_prepared_rollback_removes_only_the_exact_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    control, journal = _journal(project, "run-rollback", promoted=False)
    calls: list[tuple[str, Any]] = []

    monkeypatch.setattr(
        phase_records,
        "recover_prepared_promotion",
        lambda *_args, **kwargs: (
            calls.append(("recover", kwargs["make_current"])),
            None,
        )[1],
    )
    monkeypatch.setattr(
        knowledge_events,
        "_remove_event_unlocked",
        lambda _project, stable_id, phase, event_id, **kwargs: calls.append(
            (
                "remove-event",
                (
                    stable_id,
                    phase,
                    event_id,
                    kwargs["expected_event_sha256"],
                ),
            )
        ),
    )
    monkeypatch.setattr(
        knowledge_graph,
        "refresh_shadow_graph_unlocked",
        lambda *_args: calls.append(("graph", None)),
    )
    monkeypatch.setattr(
        promotion_journal,
        "remove",
        lambda *_args: calls.append(("remove-journal", None)),
    )

    promotion_recovery.complete_after_state_decision(
        project,
        control,
        journal,
        make_current=False,
        recover_filesystem=True,
    )

    assert calls == [
        ("recover", False),
        (
            "remove-event",
            ("method-a", PHASE, "b" * 64, "c" * 64),
        ),
        ("graph", None),
        ("remove-journal", None),
    ]


def test_event_conflict_retains_journal_and_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    control, journal = _journal(project, "run-conflict", promoted=True)
    committed: list[bool] = []
    monkeypatch.setattr(
        knowledge_events,
        "_write_event_unlocked",
        lambda *_args: (_ for _ in ()).throw(ValueError("event conflict")),
    )
    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda *_args: committed.append(True),
    )

    with pytest.raises(ValueError, match="event conflict"):
        promotion_recovery.complete_after_state_decision(
            project,
            control,
            journal,
            make_current=True,
            recover_filesystem=False,
        )

    assert committed == []
    assert promotion_journal.read_all(control) == [journal]


def test_graph_failure_invalidates_then_completes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    control, journal = _journal(project, "run-invalidate", promoted=True)
    calls: list[str] = []
    monkeypatch.setattr(
        knowledge_events,
        "_write_event_unlocked",
        lambda *_args: calls.append("event"),
    )
    monkeypatch.setattr(
        knowledge_graph,
        "refresh_shadow_graph_unlocked",
        lambda *_args: (_ for _ in ()).throw(ValueError("refresh failed")),
    )
    monkeypatch.setattr(
        knowledge_graph,
        "invalidate_shadow_graph_unlocked",
        lambda *_args: calls.append("invalidate"),
    )
    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda *_args: calls.append("commit"),
    )

    promotion_recovery.complete_after_state_decision(
        project,
        control,
        journal,
        make_current=True,
        recover_filesystem=False,
    )

    assert calls == ["event", "invalidate", "commit"]
    assert promotion_journal.read_all(control) == []


def test_graph_refresh_and_invalidation_failure_retains_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    control, journal = _journal(project, "run-graph-pending", promoted=True)
    committed: list[bool] = []
    monkeypatch.setattr(
        knowledge_events,
        "_write_event_unlocked",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        knowledge_graph,
        "refresh_shadow_graph_unlocked",
        lambda *_args: (_ for _ in ()).throw(ValueError("refresh failed")),
    )
    monkeypatch.setattr(
        knowledge_graph,
        "invalidate_shadow_graph_unlocked",
        lambda *_args: (_ for _ in ()).throw(ValueError("invalidate failed")),
    )
    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda *_args: committed.append(True),
    )

    with pytest.raises(
        promotion_recovery.PromotionRecoveryError,
        match="recovery remains pending",
    ):
        promotion_recovery.complete_after_state_decision(
            project,
            control,
            journal,
            make_current=True,
            recover_filesystem=False,
        )

    assert committed == []
    assert promotion_journal.read_all(control) == [journal]


@pytest.mark.parametrize("make_current", [False, True])
def test_reconciliation_uses_durable_state_for_prepared_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_current: bool,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    run_id = f"run-choice-{make_current}"
    _, journal = _journal(project, run_id, promoted=False)
    run = {
        "run_id": run_id,
        "status": "completed" if make_current else "submitting",
        "phase_record": {
            "source_run_id": run_id,
            "current_updated": make_current,
            "method_identity": dict(IDENTITY),
        },
    }
    phase = {
        "runs": [run],
        "current_run": run_id if make_current else None,
        "current_runs": (
            {"method-a": run_id} if make_current else {}
        ),
    }
    choices: list[tuple[bool, bool]] = []
    monkeypatch.setattr(
        project_state,
        "_validate_recorded_manifest",
        lambda *_args: _manifest(project / "output"),
    )
    monkeypatch.setattr(
        promotion_recovery,
        "complete_after_state_decision",
        lambda _project, _control, supplied, **kwargs: choices.append(
            (
                kwargs["make_current"],
                kwargs["recover_filesystem"],
            )
        ),
    )

    project_state._reconcile_promotion_journals_unlocked(
        project,
        {"phases": {PHASE: phase}},
    )

    assert choices == [(make_current, True)]
    assert journal["status"] == "prepared"
