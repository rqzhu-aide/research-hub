from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from core import phase_records, project_state, promotion_journal


PHASE = phase_records.LITERATURE_PHASE


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    return project


def _bound_intent(
    phase_slug: str,
    run_id: str,
    planned: dict[str, Any],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "method_phase_directory_promotion_intent",
        "operation_id": promotion_journal.operation_id(
            phase_slug,
            run_id,
        ),
        "phase_slug": phase_slug,
        "source_run_id": run_id,
        "method_identity": {
            "stable_id": "method-a",
            "version": "v1",
            "definition_sha256": "a" * 64,
        },
        "planned_promotion": planned,
        **extra,
    }


def _state_with_run(
    run_id: str,
    *,
    status: str,
    current: bool,
) -> dict[str, Any]:
    return {
        "phases": {
            PHASE: {
                "current_run": run_id if current else None,
                "approved_run": run_id if current else None,
                "current_runs": {},
                "runs": [
                    {
                        "run_id": run_id,
                        "status": status,
                        "phase_record": {
                            "source_run_id": run_id,
                            "current_updated": True,
                        },
                    }
                ],
            }
        }
    }


def test_promotion_journal_prepare_record_read_and_remove(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-journal-lifecycle"
    promotion = {
        "kind": "test-promotion",
        "generation": 2,
        "nested": {"digest": "a" * 64},
    }

    prepared = promotion_journal.prepare(
        control,
        project,
        PHASE,
        run_id,
    )
    path = promotion_journal.journal_path(control, run_id)

    assert prepared == {
        "schema_version": promotion_journal.SCHEMA_VERSION,
        "kind": promotion_journal.KIND,
        "project_root": str(project.resolve()),
        "phase_slug": PHASE,
        "run_id": run_id,
        "operation_id": promotion_journal.operation_id(PHASE, run_id),
        "status": "prepared",
        "intent": None,
        "promotion": None,
    }
    assert promotion_journal.read(path) == prepared
    assert promotion_journal.read_all(control) == [prepared]

    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="already exists",
    ):
        promotion_journal.prepare(control, project, PHASE, run_id)

    promoted = promotion_journal.record_promotion(
        control,
        run_id,
        promotion,
    )
    assert promoted["status"] == "promoted"
    assert promoted["promotion"] == promotion
    assert promotion_journal.read(path) == promoted
    assert promotion_journal.read_all(control) == [promoted]

    promotion_journal.remove(control, run_id)
    assert not path.exists()
    assert promotion_journal.read_all(control) == []

    promotion_journal.remove(control, run_id)


def test_reconciliation_commits_promotion_already_current_in_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-current"
    promotion = {"kind": "test-promotion", "generation": 3}
    promotion_journal.prepare(control, project, PHASE, run_id)
    promotion_journal.record_promotion(control, run_id, promotion)
    calls: list[tuple[str, Path, str, dict[str, Any]]] = []

    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda project_dir, phase_slug, value: calls.append(
            ("commit", Path(project_dir), phase_slug, dict(value))
        ),
    )
    monkeypatch.setattr(
        phase_records,
        "rollback_promotion",
        lambda project_dir, phase_slug, value: calls.append(
            ("rollback", Path(project_dir), phase_slug, dict(value))
        ),
    )

    project_state._reconcile_promotion_journals_unlocked(
        project,
        _state_with_run(run_id, status="completed", current=True),
    )

    assert calls == [("commit", project, PHASE, promotion)]
    assert promotion_journal.read_all(control) == []


def test_reconciliation_rolls_back_promotion_not_committed_to_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-uncommitted"
    promotion = {"kind": "test-promotion", "generation": 4}
    promotion_journal.prepare(control, project, PHASE, run_id)
    promotion_journal.record_promotion(control, run_id, promotion)
    calls: list[tuple[str, Path, str, dict[str, Any]]] = []

    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda project_dir, phase_slug, value: calls.append(
            ("commit", Path(project_dir), phase_slug, dict(value))
        ),
    )
    monkeypatch.setattr(
        phase_records,
        "rollback_promotion",
        lambda project_dir, phase_slug, value: calls.append(
            ("rollback", Path(project_dir), phase_slug, dict(value))
        ),
    )

    project_state._reconcile_promotion_journals_unlocked(
        project,
        _state_with_run(run_id, status="submitting", current=False),
    )

    assert calls == [("rollback", project, PHASE, promotion)]
    assert promotion_journal.read_all(control) == []


def test_reconciliation_blocks_on_prepared_journal_without_mutating_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-prepared-only"
    prepared = promotion_journal.prepare(
        control,
        project,
        PHASE,
        run_id,
    )
    calls: list[str] = []

    monkeypatch.setattr(
        phase_records,
        "commit_promotion",
        lambda *_args, **_kwargs: calls.append("commit"),
    )
    monkeypatch.setattr(
        phase_records,
        "rollback_promotion",
        lambda *_args, **_kwargs: calls.append("rollback"),
    )

    with pytest.raises(
        project_state.StateValidationError,
        match="interrupted before its rollback metadata was durable",
    ):
        project_state._reconcile_promotion_journals_unlocked(
            project,
            _state_with_run(run_id, status="submitting", current=False),
        )

    assert calls == []
    assert promotion_journal.read_all(control) == [prepared]

def test_operation_id_is_deterministic_and_phase_bound() -> None:
    run_id = "run-operation-id"
    expected = hashlib.sha256(
        f"{PHASE}\x00{run_id}".encode("utf-8")
    ).hexdigest()

    assert promotion_journal.operation_id(PHASE, run_id) == expected
    assert promotion_journal.operation_id(PHASE, run_id) == expected
    assert (
        promotion_journal.operation_id("03-idea-evaluation", run_id)
        != expected
    )


def test_intent_is_retained_and_binds_the_recorded_promotion(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-bound-intent"
    planned = {
        "kind": "theory-promotion",
        "generation": 2,
        "nested": {"digest": "b" * 64},
    }
    intent = _bound_intent(
        "03-idea-evaluation",
        run_id,
        planned,
    )
    prepared = promotion_journal.prepare(
        control,
        project,
        "03-idea-evaluation",
        run_id,
        intent=intent,
    )

    assert prepared["intent"] == intent
    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="does not match the prepared intent",
    ):
        promotion_journal.record_promotion(
            control,
            run_id,
            {**planned, "generation": 3},
        )
    assert promotion_journal.read(
        promotion_journal.journal_path(control, run_id)
    )["status"] == "prepared"

    promoted = promotion_journal.record_promotion(control, run_id, planned)
    assert promoted["intent"] == intent
    assert promoted["promotion"] == planned


def test_schema_one_journals_remain_readable_and_distinguishable(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    prepared_run = "legacy-prepared"
    prepared_path = promotion_journal.journal_path(control, prepared_run)
    legacy_prepared = {
        "schema_version": promotion_journal.LEGACY_SCHEMA_VERSION,
        "kind": promotion_journal.KIND,
        "project_root": str(project.resolve()),
        "phase_slug": PHASE,
        "run_id": prepared_run,
        "status": "prepared",
        "promotion": None,
    }
    prepared_path.write_text(
        json.dumps(legacy_prepared), encoding="utf-8"
    )

    loaded = promotion_journal.read(prepared_path)
    assert loaded == legacy_prepared
    assert "operation_id" not in loaded
    assert "intent" not in loaded
    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="legacy prepared promotion journal",
    ):
        promotion_journal.record_promotion(
            control,
            prepared_run,
            {"kind": "legacy-promotion"},
        )

    promoted_run = "legacy-promoted"
    promoted_path = promotion_journal.journal_path(control, promoted_run)
    legacy_promoted = {
        **legacy_prepared,
        "run_id": promoted_run,
        "status": "promoted",
        "promotion": {"kind": "legacy-promotion"},
    }
    promoted_path.write_text(
        json.dumps(legacy_promoted), encoding="utf-8"
    )
    assert promotion_journal.read(promoted_path) == legacy_promoted


def test_schema_two_rejects_unknown_duplicate_and_inconsistent_fields(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-malformed-envelope"
    prepared = promotion_journal.prepare(control, project, PHASE, run_id)
    path = promotion_journal.journal_path(control, run_id)

    unknown = {**prepared, "unexpected": True}
    path.write_text(json.dumps(unknown), encoding="utf-8")
    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="unsupported structure",
    ):
        promotion_journal.read(path)

    wrong_operation = {**prepared, "operation_id": "0" * 64}
    path.write_text(json.dumps(wrong_operation), encoding="utf-8")
    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="operation ID does not match",
    ):
        promotion_journal.read(path)

    canonical = json.dumps(prepared, sort_keys=True, separators=(",", ":"))
    duplicate = canonical.replace(
        '"kind":',
        f'"kind":"{promotion_journal.KIND}","kind":',
        1,
    )
    path.write_text(duplicate, encoding="utf-8")
    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="duplicate field 'kind'",
    ):
        promotion_journal.read(path)

    invalid_intent = {**prepared, "intent": "not-an-object"}
    path.write_text(json.dumps(invalid_intent), encoding="utf-8")
    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="intent must be an object",
    ):
        promotion_journal.read(path)


def test_oversized_intent_is_rejected_without_a_journal(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-oversized-intent"

    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="journal exceeds",
    ):
        promotion_journal.prepare(
            control,
            project,
            PHASE,
            run_id,
            intent=_bound_intent(
                PHASE,
                run_id,
                {"kind": "oversized"},
                payload="x" * promotion_journal.MAX_JOURNAL_BYTES,
            ),
        )
    assert not promotion_journal.journal_path(control, run_id).exists()


def test_non_finite_json_numbers_are_rejected_on_write_and_read(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    numbers = (float("nan"), float("inf"), float("-inf"))

    for index, number in enumerate(numbers):
        run_id = f"run-non-finite-write-{index}"
        with pytest.raises(
            promotion_journal.PromotionJournalError,
            match="not JSON serializable",
        ):
            promotion_journal.prepare(
                control,
                project,
                PHASE,
                run_id,
                intent=_bound_intent(
                    PHASE,
                    run_id,
                    {"kind": "non-finite"},
                    value=number,
                ),
            )
        assert not promotion_journal.journal_path(control, run_id).exists()

    run_id = "run-non-finite-read"
    prepared = promotion_journal.prepare(control, project, PHASE, run_id)
    path = promotion_journal.journal_path(control, run_id)
    canonical = json.dumps(
        prepared,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert '"intent":null' in canonical
    for token in ("NaN", "Infinity", "-Infinity"):
        malformed_intent = _bound_intent(
            PHASE,
            run_id,
            {"kind": "non-finite"},
            value=None,
        )
        encoded = json.dumps(
            malformed_intent,
            sort_keys=True,
            separators=(",", ":"),
        ).replace('"value":null', f'"value":{token}')
        malformed = canonical.replace(
            '"intent":null',
            f'"intent":{encoded}',
        )
        path.write_text(malformed, encoding="utf-8")
        with pytest.raises(
            promotion_journal.PromotionJournalError,
            match="non-finite JSON number",
        ):
            promotion_journal.read(path)


def test_remove_syncs_the_journal_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-remove-sync"
    promotion_journal.prepare(control, project, PHASE, run_id)
    path = promotion_journal.journal_path(control, run_id)
    synced: list[Path] = []
    monkeypatch.setattr(
        promotion_journal,
        "_sync_directory",
        lambda directory: synced.append(Path(directory)),
    )

    promotion_journal.remove(control, run_id)

    assert synced == [path.parent]
    assert not path.exists()


def test_remove_retry_resyncs_an_already_absent_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-remove-retry"
    promotion_journal.prepare(control, project, PHASE, run_id)
    path = promotion_journal.journal_path(control, run_id)
    calls: list[Path] = []

    def fail_once(directory: Path) -> None:
        calls.append(Path(directory))
        if len(calls) == 1:
            raise OSError("simulated journal directory sync failure")

    monkeypatch.setattr(
        promotion_journal,
        "_sync_directory",
        fail_once,
    )

    with pytest.raises(OSError, match="simulated journal directory"):
        promotion_journal.remove(control, run_id)
    assert not path.exists()
    promotion_journal.remove(control, run_id)
    assert calls == [path.parent, path.parent]


def test_read_all_rejects_a_dangling_journal_directory_link(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    control.mkdir(parents=True)
    directory = control / promotion_journal.DIRECTORY_NAME
    try:
        directory.symlink_to(
            control / "missing-journal-target",
            target_is_directory=True,
        )
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="plain directory",
    ):
        promotion_journal.read_all(control)


def test_prepare_rejects_a_dangling_journal_path(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    control = project_state.state_dir(project)
    run_id = "run-dangling-path"
    path = promotion_journal.journal_path(control, run_id)
    try:
        path.symlink_to(path.parent / "missing-journal.json")
    except OSError as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")

    with pytest.raises(
        promotion_journal.PromotionJournalError,
        match="already exists",
    ):
        promotion_journal.prepare(
            control,
            project,
            PHASE,
            run_id,
        )
    assert path.is_symlink()
