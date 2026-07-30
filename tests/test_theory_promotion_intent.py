"""Focused tests for deterministic Phase 3 promotion intents."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from core import knowledge_event_schema as event_schema
from core import knowledge_fragments as fragments
from core import theory_promotion as promotion
from core import theory_records as theory


def _identity(
    *,
    version: str = "v1",
    digest_seed: str | None = None,
) -> dict[str, str]:
    seed = digest_seed or version
    return {
        "stable_id": "method-a",
        "version": version,
        "definition_sha256": hashlib.sha256(
            f"method-a:{seed}".encode("utf-8")
        ).hexdigest(),
    }


def _operation_id(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()

def _fragment(
    identity: dict[str, str],
    run_id: str,
    generation: int,
    *,
    wording: str,
) -> dict[str, Any]:
    return {
        "schema_version": fragments.SCHEMA_VERSION,
        "kind": fragments.THEORY_KIND,
        "semantics": fragments.THEORY_SEMANTICS,
        "coverage": "complete",
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "statements": [{
            "statement_id": "main-claim",
            "statement_type": "Mathematical statement",
            "wording": wording,
            "scope": "The model and regularity conditions in the manuscript.",
            "formulation_state": "Current",
            "assessment_status": "Supported",
            "evidential_basis": ["The complete proof in the manuscript."],
            "source_provenance": ["theory-manuscript.md"],
            "assumptions": ["The stated regularity conditions hold."],
            "uncertainty": ["Finite-sample behavior remains open."],
            "logical_status": "proved",
            "mathematical_result_type": (
                "asymptotic limit, rate, or distribution"
            ),
        }],
        "dependencies": [],
        "lead_summary": {
            "fundamental_points": [
                "The main result has a complete proof."
            ],
            "decision_relevant_changes": [
                f"The current theory package is {run_id}."
            ],
            "unresolved_questions": [
                "Finite-sample behavior remains open."
            ],
        },
    }


def _stage(
    project: Path,
    run_id: str,
    *,
    identity: dict[str, str],
    wording: str,
) -> tuple[Path, dict[str, Any]]:
    output = project / "runs" / run_id
    output.mkdir(parents=True)
    (output / theory.THEORY_FILENAME).write_text(
        f"# Theory\n\n{wording}\n",
        encoding="utf-8",
    )
    current = theory.load_current_theory(project, identity["stable_id"])
    generation = (
        1 if current is None else int(current["generation"]) + 1
    )
    (output / theory.KNOWLEDGE_FILENAME).write_text(
        json.dumps(
            _fragment(
                identity,
                run_id,
                generation,
                wording=wording,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    seal = theory.seal_staged_theory(
        project,
        output,
        method_identity=identity,
        source_run_id=run_id,
        scientific_outcome="Complete",
    )
    return output, seal


def _plan(
    project: Path,
    output: Path,
    seal: dict[str, Any],
    identity: dict[str, str],
    operation_id: str,
) -> dict[str, Any]:
    return theory.plan_staged_theory_promotion(
        project,
        output,
        seal,
        expected_method_identity=identity,
        operation_id=operation_id,
    )


def _promote_direct(
    project: Path,
    run_id: str = "run-001",
    *,
    identity: dict[str, str] | None = None,
) -> tuple[dict[str, str], Path, dict[str, Any], dict[str, Any]]:
    selected = identity or _identity()
    output, seal = _stage(
        project,
        run_id,
        identity=selected,
        wording=f"Complete proof for {run_id}.",
    )
    record = theory.promote_staged_theory(
        project,
        output,
        seal,
        expected_method_identity=selected,
    )
    return selected, output, seal, record


def _runtime_paths(
    project: Path,
    intent: dict[str, Any],
) -> dict[str, Path]:
    return {
        field: project / relative
        for field, relative in intent["paths"].items()
    }


def _prepare_planned_package(
    project: Path,
    output: Path,
    intent: dict[str, Any],
) -> dict[str, Path]:
    paths = _runtime_paths(project, intent)
    prepared = paths["prepared"]
    prepared.mkdir(parents=True)
    shutil.copy2(
        output / theory.THEORY_FILENAME,
        prepared / theory.THEORY_FILENAME,
    )
    shutil.copy2(
        output / theory.KNOWLEDGE_FILENAME,
        prepared / theory.KNOWLEDGE_FILENAME,
    )
    record = {
        key: value
        for key, value in intent["planned_promotion"].items()
        if key != "_promotion_transaction"
    }
    (prepared / theory.RECORD_FILENAME).write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return paths


def _replacement_plan(
    project: Path,
    *,
    operation_id: str,
) -> tuple[
    dict[str, str],
    dict[str, Any],
    Path,
    dict[str, Any],
    dict[str, Path],
]:
    identity, _, _, previous = _promote_direct(project)
    output, seal = _stage(
        project,
        "run-002",
        identity=identity,
        wording="The repaired complete proof.",
    )
    intent = _plan(
        project, output, seal, identity, operation_id
    )
    paths = _prepare_planned_package(project, output, intent)
    return identity, previous, output, intent, paths


def _current_run(project: Path) -> str | None:
    current = theory.load_current_theory(project, "method-a")
    return None if current is None else str(current["source_run_id"])


def test_plan_is_read_only_and_contains_real_first_event(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )

    intent = _plan(
        project, output, seal, identity, _operation_id("operation-first")
    )

    assert intent["schema_version"] == 1
    assert intent["kind"] == "method_phase_directory_promotion_intent"
    assert intent["phase_slug"] == theory.THEORY_PHASE_SLUG
    assert intent["method_identity"] == identity
    assert intent["source_run_id"] == "run-001"
    assert intent["previous_checkpoint_sha256"] is None
    assert intent["knowledge_event"]["previous_baseline_status"] == "absent"
    assert intent["knowledge_event"]["statement_changes"] == [{
        "statement_id": "main-claim",
        "change_type": "added",
        "changed_fields": [],
    }]
    assert theory.load_current_theory(project, "method-a") is None
    assert all(
        not path.exists()
        for path in _runtime_paths(project, intent).values()
    )


def test_planned_first_and_replacement_promotions_return_exact_plan(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    first_output, first_seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )
    first_intent = _plan(
        project,
        first_output,
        first_seal,
        identity,
        _operation_id("operation-first"),
    )

    first = theory.promote_staged_theory(
        project,
        first_output,
        first_seal,
        expected_method_identity=identity,
        retain_backup=True,
        promotion_intent=first_intent,
    )

    assert first == first_intent["planned_promotion"]
    assert _current_run(project) == "run-001"
    second_output, second_seal = _stage(
        project,
        "run-002",
        identity=identity,
        wording="The repaired complete proof.",
    )
    second_intent = _plan(
        project,
        second_output,
        second_seal,
        identity,
        _operation_id("operation-second"),
    )
    second = theory.promote_staged_theory(
        project,
        second_output,
        second_seal,
        expected_method_identity=identity,
        retain_backup=True,
        promotion_intent=second_intent,
    )

    assert second == second_intent["planned_promotion"]
    assert _current_run(project) == "run-002"
    backup = _runtime_paths(project, second_intent)["backup"]
    assert backup.is_dir()
    assert second_intent["knowledge_event"]["statement_changes"] == [{
        "statement_id": "main-claim",
        "change_type": "revised",
        "changed_fields": ["wording"],
    }]
    theory.commit_theory_promotion(project, second)
    assert not backup.exists()


def test_planned_no_change_has_no_event_or_mutation(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity, output, seal, current = _promote_direct(project)
    intent = _plan(
        project, output, seal, identity, _operation_id("operation-no-change")
    )

    result = theory.promote_staged_theory(
        project,
        output,
        seal,
        expected_method_identity=identity,
        retain_backup=True,
        promotion_intent=intent,
    )

    assert intent["knowledge_event"] is None
    assert intent["planned_promotion"][
        "_promotion_transaction"
    ]["changed"] is False
    assert result == intent["planned_promotion"]
    assert theory.load_current_theory(project, "method-a") == current
    assert all(
        not path.exists()
        for field, path in _runtime_paths(project, intent).items()
        if field != "canonical"
    )


@pytest.mark.parametrize("partial_state", ["before-swap", "after-backup"])
def test_rollback_recovery_before_new_install_is_idempotent(
    tmp_path: Path,
    partial_state: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, previous, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id(f"operation-{partial_state}"),
    )
    if partial_state == "after-backup":
        os.replace(paths["canonical"], paths["backup"])

    theory.recover_theory_promotion_intent(
        project, intent, make_current=False
    )
    theory.recover_theory_promotion_intent(
        project, intent, make_current=False
    )

    assert theory.load_current_theory(project, "method-a") == previous
    assert not paths["prepared"].exists()
    assert not paths["backup"].exists()
    assert not paths["rejected"].exists()


def test_rollback_recovery_after_new_install_restores_old(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, previous, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id("operation-installed"),
    )
    os.replace(paths["canonical"], paths["backup"])
    os.replace(paths["prepared"], paths["canonical"])

    theory.recover_theory_promotion_intent(
        project, intent, make_current=False
    )

    assert theory.load_current_theory(project, "method-a") == previous
    assert not paths["backup"].exists()
    assert not paths["rejected"].exists()


@pytest.mark.parametrize("installed", [False, True])
def test_first_install_rollback_recovery(
    tmp_path: Path,
    installed: bool,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )
    intent = _plan(
        project,
        output,
        seal,
        identity,
        _operation_id(f"operation-first-{installed}"),
    )
    paths = _prepare_planned_package(project, output, intent)
    if installed:
        os.replace(paths["prepared"], paths["canonical"])

    theory.recover_theory_promotion_intent(
        project, intent, make_current=False
    )

    assert theory.load_current_theory(project, "method-a") is None
    assert not paths["prepared"].exists()
    assert not paths["rejected"].exists()


def test_forward_recovery_installs_new_and_preserves_backup(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id("operation-forward"),
    )
    os.replace(paths["canonical"], paths["backup"])

    recovered = theory.recover_theory_promotion_intent(
        project, intent, make_current=True
    )
    repeated = theory.recover_theory_promotion_intent(
        project, intent, make_current=True
    )

    assert recovered == intent["planned_promotion"]
    assert repeated == intent["planned_promotion"]
    assert _current_run(project) == "run-002"
    assert paths["backup"].is_dir()
    theory.commit_theory_promotion(project, recovered)
    assert not paths["backup"].exists()
    assert theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=True,
    ) == intent["planned_promotion"]
    with pytest.raises(
        theory.TheoryStageChanged,
        match="ambiguous partial-swap",
    ):
        theory.recover_theory_promotion_intent(
            project,
            intent,
            make_current=False,
        )


def test_recovery_rejects_tampered_path_current_and_backup(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id("operation-tamper"),
    )
    changed_path = deepcopy(intent)
    changed_path["paths"]["prepared"] = "branches/method-a/wrong"
    with pytest.raises(theory.TheoryValidationError, match="paths"):
        theory.recover_theory_promotion_intent(
            project, changed_path, make_current=False
        )

    (paths["canonical"] / theory.THEORY_FILENAME).write_text(
        "# Tampered\n",
        encoding="utf-8",
    )
    with pytest.raises(theory.TheoryRecordError):
        theory.recover_theory_promotion_intent(
            project, intent, make_current=False
        )

    project_two = tmp_path / "project-two"
    project_two.mkdir()
    _, _, _, intent_two, paths_two = _replacement_plan(
        project_two,
        operation_id=_operation_id("operation-tamper-backup"),
    )
    os.replace(paths_two["canonical"], paths_two["backup"])
    (paths_two["backup"] / theory.THEORY_FILENAME).write_text(
        "# Tampered backup\n",
        encoding="utf-8",
    )
    with pytest.raises(theory.TheoryRecordError):
        theory.recover_theory_promotion_intent(
            project_two, intent_two, make_current=False
        )


@pytest.mark.parametrize("stop_after", [1, 2, 3])
def test_hard_exit_during_prepared_write_rolls_back_and_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stop_after: int,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )
    intent = _plan(
        project,
        output,
        seal,
        identity,
        _operation_id(f"hard-exit-{stop_after}"),
    )
    paths = _runtime_paths(project, intent)
    durable_write = promotion._write_durable_prepared_file
    calls = 0

    def stop_after_durable_write(path: Path, payload: bytes) -> None:
        nonlocal calls
        durable_write(path, payload)
        calls += 1
        if calls == stop_after:
            raise SystemExit("simulated hard exit")

    monkeypatch.setattr(
        promotion,
        "_write_durable_prepared_file",
        stop_after_durable_write,
    )
    with pytest.raises(SystemExit, match="simulated hard exit"):
        theory.promote_staged_theory(
            project,
            output,
            seal,
            expected_method_identity=identity,
            retain_backup=True,
            promotion_intent=intent,
        )
    assert paths["prepared"].is_dir()
    if stop_after < 3:
        with pytest.raises(theory.TheoryStageChanged, match="ambiguous"):
            theory.recover_theory_promotion_intent(
                project,
                intent,
                make_current=True,
            )

    monkeypatch.setattr(
        promotion,
        "_write_durable_prepared_file",
        durable_write,
    )
    theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=False,
    )
    theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=False,
    )
    result = theory.promote_staged_theory(
        project,
        output,
        seal,
        expected_method_identity=identity,
        retain_backup=True,
        promotion_intent=intent,
    )
    assert result == intent["planned_promotion"]
    assert _current_run(project) == "run-001"


@pytest.mark.parametrize("all_names", [False, True])
def test_rollback_removes_bounded_zero_byte_prepared_state(
    tmp_path: Path,
    all_names: bool,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )
    intent = _plan(
        project,
        output,
        seal,
        identity,
        _operation_id(f"zero-byte-{all_names}"),
    )
    prepared = _runtime_paths(project, intent)["prepared"]
    prepared.mkdir(parents=True)
    if all_names:
        shutil.copy2(
            output / theory.THEORY_FILENAME,
            prepared / theory.THEORY_FILENAME,
        )
        shutil.copy2(
            output / theory.KNOWLEDGE_FILENAME,
            prepared / theory.KNOWLEDGE_FILENAME,
        )
        (prepared / theory.RECORD_FILENAME).write_bytes(b"")
    else:
        (prepared / theory.THEORY_FILENAME).write_bytes(b"")

    with pytest.raises(theory.TheoryStageChanged, match="ambiguous"):
        theory.recover_theory_promotion_intent(
            project,
            intent,
            make_current=True,
        )
    theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=False,
    )
    assert not prepared.exists()


def test_incomplete_prepared_rejects_unexpected_entries(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )
    intent = _plan(
        project,
        output,
        seal,
        identity,
        _operation_id("unexpected-entry"),
    )
    prepared = _runtime_paths(project, intent)["prepared"]
    prepared.mkdir(parents=True)
    (prepared / theory.THEORY_FILENAME).write_text(
        "# Partial prepared theory\n",
        encoding="utf-8",
    )
    (prepared / "unexpected.txt").write_text(
        "unknown data\n",
        encoding="utf-8",
    )

    with pytest.raises(theory.TheoryRecordError):
        theory.recover_theory_promotion_intent(
            project,
            intent,
            make_current=False,
        )
    assert prepared.is_dir()
    assert (prepared / "unexpected.txt").is_file()


def test_transaction_parent_is_synced_after_each_directory_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )
    intent = _plan(
        project,
        output,
        seal,
        identity,
        _operation_id("sync-first-install"),
    )
    parent = _runtime_paths(project, intent)["canonical"].parent
    synced: list[Path] = []
    monkeypatch.setattr(
        promotion,
        "_sync_transaction_parent",
        lambda path: synced.append(path),
    )

    theory.promote_staged_theory(
        project,
        output,
        seal,
        expected_method_identity=identity,
        retain_backup=True,
        promotion_intent=intent,
    )
    assert synced == [parent, parent]

    project_two = tmp_path / "project-two"
    project_two.mkdir()
    _, _, _, second_intent, paths = _replacement_plan(
        project_two,
        operation_id=_operation_id("sync-rollback"),
    )
    os.replace(paths["canonical"], paths["backup"])
    os.replace(paths["prepared"], paths["canonical"])
    synced.clear()

    theory.recover_theory_promotion_intent(
        project_two,
        second_intent,
        make_current=False,
    )
    assert synced == [paths["canonical"].parent] * 4


def test_completed_recovery_retries_parent_sync_after_sync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id("completed-sync-retry"),
    )
    calls = 0

    def fail_final_sync(parent: Path) -> None:
        nonlocal calls
        assert parent == paths["canonical"].parent
        calls += 1
        if calls == 2:
            raise OSError("simulated directory sync failure")

    monkeypatch.setattr(
        promotion,
        "_sync_transaction_parent",
        fail_final_sync,
    )
    with pytest.raises(OSError, match="directory sync failure"):
        theory.recover_theory_promotion_intent(
            project,
            intent,
            make_current=True,
        )
    assert _current_run(project) == "run-002"
    assert paths["backup"].is_dir()

    synced: list[Path] = []
    monkeypatch.setattr(
        promotion,
        "_sync_transaction_parent",
        lambda parent: synced.append(parent),
    )
    result = theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=True,
    )
    assert result == intent["planned_promotion"]
    assert synced == [paths["canonical"].parent]

def test_dangling_transaction_link_is_rejected_without_deletion(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )
    intent = _plan(
        project,
        output,
        seal,
        identity,
        _operation_id("dangling-link"),
    )
    prepared = _runtime_paths(project, intent)["prepared"]
    prepared.parent.mkdir(parents=True)
    try:
        prepared.symlink_to(
            prepared.parent / "missing-target",
            target_is_directory=True,
        )
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    with pytest.raises(theory.TheoryRecordError):
        theory.recover_theory_promotion_intent(
            project,
            intent,
            make_current=False,
        )
    with pytest.raises(theory.TheoryRecordCorrupt, match="symbolic link"):
        theory._remove_internal_tree(prepared)
    assert os.path.lexists(prepared)


def test_complete_prepared_package_with_extra_entry_is_preserved(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id("complete-extra-entry"),
    )
    extra = paths["prepared"] / "unexpected.txt"
    extra.write_text("unrecognized data\n", encoding="utf-8")

    with pytest.raises(theory.TheoryRecordError, match="unexpected entries"):
        theory.recover_theory_promotion_intent(
            project,
            intent,
            make_current=False,
        )
    assert extra.read_text(encoding="utf-8") == "unrecognized data\n"
    assert paths["prepared"].is_dir()


def test_interrupted_rejected_cleanup_is_restart_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id("interrupted-rejected-cleanup"),
    )
    theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=True,
    )
    real_remove = promotion._remove_internal_tree

    def interrupt_rejected_cleanup(path: Path) -> None:
        if path == paths["rejected"]:
            (path / theory.RECORD_FILENAME).unlink()
            raise SystemExit("simulated cleanup interruption")
        real_remove(path)

    monkeypatch.setattr(
        promotion,
        "_remove_internal_tree",
        interrupt_rejected_cleanup,
    )
    with pytest.raises(SystemExit, match="cleanup interruption"):
        theory.recover_theory_promotion_intent(
            project,
            intent,
            make_current=False,
        )
    assert paths["rejected"].is_dir()
    assert not (paths["rejected"] / theory.RECORD_FILENAME).exists()

    monkeypatch.setattr(promotion, "_remove_internal_tree", real_remove)
    theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=False,
    )
    theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=False,
    )
    assert _current_run(project) == "run-001"
    assert not paths["rejected"].exists()


def test_commit_rejects_extra_backup_entries_and_syncs_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id("commit-backup-cleanup"),
    )
    promotion_result = theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=True,
    )
    assert promotion_result is not None
    extra = paths["backup"] / "unexpected.txt"
    extra.write_text("preserve me\n", encoding="utf-8")

    with pytest.raises(theory.TheoryRecordError, match="unexpected entries"):
        theory.commit_theory_promotion(project, promotion_result)
    assert extra.read_text(encoding="utf-8") == "preserve me\n"

    extra.unlink()
    synced: list[Path] = []
    monkeypatch.setattr(
        promotion.project_state,
        "_sync_state_directory",
        lambda path: synced.append(path),
    )
    theory.commit_theory_promotion(project, promotion_result)
    assert not paths["backup"].exists()
    assert synced == [paths["backup"].parent]

def test_commit_retry_syncs_already_removed_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(
        project,
        operation_id=_operation_id("commit-sync-retry"),
    )
    promotion_result = theory.recover_theory_promotion_intent(
        project,
        intent,
        make_current=True,
    )
    assert promotion_result is not None

    def fail_sync(parent: Path) -> None:
        assert parent == paths["backup"].parent
        raise OSError("simulated commit sync failure")

    monkeypatch.setattr(
        promotion.project_state,
        "_sync_state_directory",
        fail_sync,
    )
    with pytest.raises(OSError, match="commit sync failure"):
        theory.commit_theory_promotion(project, promotion_result)
    assert not paths["backup"].exists()

    synced: list[Path] = []
    monkeypatch.setattr(
        promotion.project_state,
        "_sync_state_directory",
        lambda parent: synced.append(parent),
    )
    theory.commit_theory_promotion(project, promotion_result)
    assert synced == [paths["backup"].parent]

def test_operation_id_must_match_journal_digest_shape(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-001",
        identity=identity,
        wording="The first complete proof.",
    )

    for invalid in ("operation-first", "A" * 64, "a" * 63):
        with pytest.raises(
            theory.TheoryValidationError,
            match="64 lowercase hex",
        ):
            _plan(project, output, seal, identity, invalid)


def _write_legacy_current(
    project: Path,
    identity: dict[str, str],
) -> dict[str, Any]:
    current = theory.current_theory_directory(project, "method-a")
    current.mkdir(parents=True)
    manuscript = b"# Legacy theory\n\nA complete legacy proof.\n"
    (current / theory.THEORY_FILENAME).write_bytes(manuscript)
    record = {
        "schema_version": theory.LEGACY_SCHEMA_VERSION,
        "method_identity": identity,
        "source_run_id": "legacy-run",
        "scientific_outcome": "Complete",
        "structurally_self_contained": False,
        "generation": 3,
        "manuscript_file": theory.THEORY_FILENAME,
        "manuscript_sha256": hashlib.sha256(manuscript).hexdigest(),
        "manuscript_size": len(manuscript),
    }
    (current / theory.RECORD_FILENAME).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert theory.load_current_theory(project, "method-a") == record
    return record


def test_legacy_prior_package_produces_bounded_real_event(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    previous_identity = _identity(version="v1")
    previous = _write_legacy_current(project, previous_identity)
    current_identity = _identity(version="v2")
    output, seal = _stage(
        project,
        "run-004",
        identity=current_identity,
        wording="The current replacement proof.",
    )

    intent = _plan(
        project,
        output,
        seal,
        current_identity,
        _operation_id("operation-legacy"),
    )
    event = intent["knowledge_event"]

    assert event["previous_baseline_status"] == "legacy_unavailable"
    assert event["previous_method_identity"] == previous_identity
    assert event["current_method_identity"] == current_identity
    assert event["previous_generation"] == previous["generation"]
    assert event["current_generation"] == previous["generation"] + 1
    assert event["previous_fragment_sha256"] is None
    assert event["statement_changes"] == []
    assert event["dependency_changes"] == []
    assert event["evidence_binding_changes"] == []

    tampered = deepcopy(intent)
    unsealed_event = {
        key: value
        for key, value in tampered["knowledge_event"].items()
        if key != "event_sha256"
    }
    unsealed_event["statement_changes"] = [{
        "statement_id": "main-claim",
        "change_type": "added",
        "changed_fields": [],
    }]
    with pytest.raises(
        event_schema.KnowledgeEventValidationError,
        match="legacy unavailable",
    ):
        event_schema.seal_event(unsealed_event)
