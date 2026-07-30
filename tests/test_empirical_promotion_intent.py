"""Focused tests for deterministic Phase 4 promotion intents."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from core import empirical_records as records
from core import knowledge_basis
from core import knowledge_event_schema as event_schema
from core import project_state


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


def _operation(run_id: str) -> str:
    value = f"{records.EMPIRICAL_PHASE_SLUG}\x00{run_id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fragment(
    identity: dict[str, str],
    run_id: str,
    generation: int,
    *,
    wording: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "empirical_knowledge_fragment",
        "semantics": "cumulative_evidence",
        "coverage": "complete",
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "statements": [{
            "statement_id": "empirical-main",
            "statement_type": "Empirical statement",
            "wording": wording,
            "scope": "The simulations represented by the current package.",
            "formulation_state": "Current",
            "assessment_status": "Supported",
            "evidential_basis": ["The current empirical synthesis."],
            "source_provenance": ["empirical-synthesis.md"],
            "assumptions": ["The recorded computation completed."],
            "uncertainty": ["Further stress tests remain useful."],
            "logical_status": "Not applicable",
            "mathematical_result_type": "Not applicable",
        }],
        "dependencies": [],
        "evidence_bindings": [],
        "lead_summary": {
            "fundamental_points": [wording],
            "decision_relevant_changes": [f"Current run: {run_id}."],
            "unresolved_questions": ["Further stress tests remain useful."],
        },
    }


def _write_package(
    directory: Path,
    *,
    identity: dict[str, str],
    run_id: str,
    generation: int,
    wording: str,
    include_knowledge: bool = True,
    index_schema_version: int = records.INDEX_SCHEMA_VERSION,
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    synthesis = directory / records.SYNTHESIS_FILENAME
    synthesis.write_text(
        f"# Empirical synthesis\n\n{wording}\n",
        encoding="utf-8",
    )
    synthesis_bytes = synthesis.read_bytes()
    index = {
        "schema_version": index_schema_version,
        "kind": records.INDEX_KIND,
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "synthesis": {
            "path": records.SYNTHESIS_FILENAME,
            "sha256": hashlib.sha256(synthesis_bytes).hexdigest(),
            "size": len(synthesis_bytes),
        },
        "entries": [],
    }
    if index_schema_version >= records.COUNTERPART_INDEX_SCHEMA_VERSION:
        index["counterpart_basis"] = knowledge_basis.unknown_legacy_basis(
            phase_slug=knowledge_basis.THEORY_PHASE,
        )
    (directory / records.INDEX_FILENAME).write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if include_knowledge:
        (directory / records.KNOWLEDGE_FILENAME).write_text(
            json.dumps(
                _fragment(
                    identity,
                    run_id,
                    generation,
                    wording=wording,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return index


def _stage(
    project: Path,
    run_id: str,
    *,
    identity: dict[str, str],
    generation: int,
    wording: str,
) -> Path:
    output = project / "runs" / run_id
    _write_package(
        output,
        identity=identity,
        run_id=run_id,
        generation=generation,
        wording=wording,
    )
    return output


def _plan(
    project: Path,
    output: Path,
    identity: dict[str, str],
    run_id: str,
    *,
    lock_held: bool = False,
) -> dict[str, Any]:
    return records.plan_staged_package_promotion(
        project,
        output,
        operation_id=_operation(run_id),
        expected_method_identity=identity,
        lock_held=lock_held,
    )


def _runtime_paths(
    project: Path,
    intent: dict[str, Any],
) -> dict[str, Path]:
    return {
        field: project / relative
        for field, relative in intent["paths"].items()
    }


def _prepare_planned_package(
    output: Path,
    paths: dict[str, Path],
) -> None:
    paths["prepared"].mkdir(parents=True)
    for filename in (
        records.SYNTHESIS_FILENAME,
        records.INDEX_FILENAME,
        records.KNOWLEDGE_FILENAME,
    ):
        shutil.copy2(output / filename, paths["prepared"] / filename)


def _promote_direct(
    project: Path,
    *,
    identity: dict[str, str] | None = None,
) -> tuple[dict[str, str], Path, dict[str, Any]]:
    selected = identity or _identity()
    output = _stage(
        project,
        "run-001",
        identity=selected,
        generation=1,
        wording="The first simulation supports the method.",
    )
    promotion = records.promote_staged_package(project, output)
    return selected, output, promotion


def _replacement_plan(
    project: Path,
) -> tuple[
    dict[str, str],
    dict[str, Any],
    Path,
    dict[str, Any],
    dict[str, Path],
]:
    identity, _, _ = _promote_direct(project)
    previous = records.load_current_package(project, "method-a")
    assert previous is not None
    output = _stage(
        project,
        "run-002",
        identity=identity,
        generation=2,
        wording="The repaired simulation strengthens the evidence.",
    )
    intent = _plan(project, output, identity, "run-002")
    paths = _runtime_paths(project, intent)
    _prepare_planned_package(output, paths)
    return identity, previous, output, intent, paths


def _current_run(project: Path) -> str | None:
    current = records.load_current_package(project, "method-a")
    return None if current is None else str(current["source_run_id"])


def test_plan_is_read_only_deterministic_and_contains_real_first_event(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )

    intent = _plan(project, output, identity, "run-001")
    repeated = _plan(project, output, identity, "run-001")

    assert intent == repeated
    assert intent["schema_version"] == 1
    assert intent["kind"] == "method_phase_directory_promotion_intent"
    assert intent["phase_slug"] == records.EMPIRICAL_PHASE_SLUG
    assert intent["method_identity"] == identity
    assert intent["source_run_id"] == "run-001"
    assert intent["previous_checkpoint_sha256"] is None
    assert intent["knowledge_event"]["previous_baseline_status"] == "absent"
    assert intent["knowledge_event"]["statement_changes"] == [{
        "statement_id": "empirical-main",
        "change_type": "added",
        "changed_fields": [],
    }]
    assert records.load_current_package(project, "method-a") is None
    assert all(
        not path.exists()
        for path in _runtime_paths(project, intent).values()
    )
    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="lowercase SHA-256",
    ):
        records.plan_staged_package_promotion(
            project,
            output,
            operation_id="not-a-journal-operation",
            expected_method_identity=identity,
        )


def test_planned_first_and_replacement_execution_return_exact_plan(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    first_output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )
    first_intent = _plan(project, first_output, identity, "run-001")

    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="requires retain_backup",
    ):
        records.promote_staged_package(
            project,
            first_output,
            promotion_intent=first_intent,
        )
    first = records.promote_staged_package(
        project,
        first_output,
        retain_backup=True,
        promotion_intent=first_intent,
    )

    assert first == first_intent["planned_promotion"]
    assert _current_run(project) == "run-001"
    second_output = _stage(
        project,
        "run-002",
        identity=identity,
        generation=2,
        wording="The repaired simulation strengthens the evidence.",
    )
    second_intent = _plan(project, second_output, identity, "run-002")
    second = records.promote_staged_package(
        project,
        second_output,
        retain_backup=True,
        promotion_intent=second_intent,
    )

    assert second == second_intent["planned_promotion"]
    assert _current_run(project) == "run-002"
    backup = _runtime_paths(project, second_intent)["backup"]
    assert backup.is_dir()
    assert second_intent["knowledge_event"]["statement_changes"] == [{
        "statement_id": "empirical-main",
        "change_type": "revised",
        "changed_fields": ["wording"],
    }]
    records.commit_empirical_package_promotion(project, second)
    assert not backup.exists()
@pytest.mark.parametrize("partial_state", ["before-swap", "after-backup"])
def test_replacement_rollback_before_install_is_restart_idempotent(
    tmp_path: Path,
    partial_state: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, previous, _, intent, paths = _replacement_plan(project)
    if partial_state == "after-backup":
        os.replace(paths["canonical"], paths["backup"])

    records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
    )
    records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
    )

    assert records.load_current_package(project, "method-a") == previous
    assert not paths["prepared"].exists()
    assert not paths["backup"].exists()
    assert not paths["rejected"].exists()


def test_replacement_rollback_after_install_restores_old(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, previous, _, intent, paths = _replacement_plan(project)
    os.replace(paths["canonical"], paths["backup"])
    os.replace(paths["prepared"], paths["canonical"])

    records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
    )

    assert records.load_current_package(project, "method-a") == previous
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
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )
    intent = _plan(project, output, identity, "run-001")
    paths = _runtime_paths(project, intent)
    _prepare_planned_package(output, paths)
    if installed:
        os.replace(paths["prepared"], paths["canonical"])

    records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
    )

    assert records.load_current_package(project, "method-a") is None
    assert not paths["prepared"].exists()
    assert not paths["rejected"].exists()


def test_replacement_forward_recovery_preserves_backup_and_is_idempotent(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(project)
    os.replace(paths["canonical"], paths["backup"])

    recovered = records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=True,
    )
    repeated = records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=True,
    )

    assert recovered == intent["planned_promotion"]
    assert repeated == intent["planned_promotion"]
    assert _current_run(project) == "run-002"
    assert paths["backup"].is_dir()
    records.commit_empirical_package_promotion(project, recovered)
    assert not paths["backup"].exists()
    assert records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=True,
    ) == intent["planned_promotion"]
    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="ambiguous partial-swap",
    ):
        records.recover_empirical_promotion_intent(
            project,
            intent,
            make_current=False,
        )


def test_first_forward_recovery_installs_planned_package(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )
    intent = _plan(project, output, identity, "run-001")
    paths = _runtime_paths(project, intent)
    _prepare_planned_package(output, paths)

    recovered = records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=True,
    )

    assert recovered == intent["planned_promotion"]
    assert _current_run(project) == "run-001"
    assert not paths["prepared"].exists()


@pytest.mark.parametrize("partial_kind", ["zero-byte", "partial-all"])
def test_incomplete_prepared_rolls_back_safely_but_cannot_move_forward(
    tmp_path: Path,
    partial_kind: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, previous, output, intent, paths = _replacement_plan(project)
    shutil.rmtree(paths["prepared"])
    paths["prepared"].mkdir()
    if partial_kind == "zero-byte":
        (paths["prepared"] / records.SYNTHESIS_FILENAME).write_bytes(b"")
    else:
        shutil.copy2(
            output / records.SYNTHESIS_FILENAME,
            paths["prepared"] / records.SYNTHESIS_FILENAME,
        )
        shutil.copy2(
            output / records.INDEX_FILENAME,
            paths["prepared"] / records.INDEX_FILENAME,
        )
        (paths["prepared"] / records.KNOWLEDGE_FILENAME).write_bytes(
            b'{"schema_version":'
        )

    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="cannot be recovered forward",
    ):
        records.recover_empirical_promotion_intent(
            project,
            intent,
            make_current=True,
        )
    assert paths["prepared"].is_dir()

    records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
    )

    assert records.load_current_package(project, "method-a") == previous
    assert not paths["prepared"].exists()


def test_incomplete_prepared_with_unexpected_content_is_not_removed(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(project)
    shutil.rmtree(paths["prepared"])
    paths["prepared"].mkdir()
    unexpected = paths["prepared"] / "unrelated.txt"
    unexpected.write_text("do not remove\n", encoding="utf-8")

    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="unexpected content",
    ):
        records.recover_empirical_promotion_intent(
            project,
            intent,
            make_current=False,
        )

    assert unexpected.read_text(encoding="utf-8") == "do not remove\n"
def test_recovery_rejects_tampered_path_current_backup_and_ambiguity(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(project)
    changed_path = deepcopy(intent)
    changed_path["paths"]["prepared"] = "branches/method-a/wrong"
    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="paths",
    ):
        records.recover_empirical_promotion_intent(
            project,
            changed_path,
            make_current=False,
        )

    (paths["canonical"] / records.SYNTHESIS_FILENAME).write_text(
        "# Tampered current\n",
        encoding="utf-8",
    )
    with pytest.raises(records.EmpiricalRecordError):
        records.recover_empirical_promotion_intent(
            project,
            intent,
            make_current=False,
        )

    project_two = tmp_path / "project-two"
    project_two.mkdir()
    _, _, _, intent_two, paths_two = _replacement_plan(project_two)
    os.replace(paths_two["canonical"], paths_two["backup"])
    (paths_two["backup"] / records.SYNTHESIS_FILENAME).write_text(
        "# Tampered backup\n",
        encoding="utf-8",
    )
    with pytest.raises(records.EmpiricalRecordError):
        records.recover_empirical_promotion_intent(
            project_two,
            intent_two,
            make_current=False,
        )

    project_three = tmp_path / "project-three"
    project_three.mkdir()
    _, _, _, intent_three, paths_three = _replacement_plan(project_three)
    shutil.copytree(paths_three["prepared"], paths_three["rejected"])
    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="ambiguous",
    ):
        records.recover_empirical_promotion_intent(
            project_three,
            intent_three,
            make_current=False,
        )


def test_available_event_is_rebuilt_from_exact_transaction_packages(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, _ = _replacement_plan(project)
    tampered = deepcopy(intent)
    unsealed = {
        key: value
        for key, value in tampered["knowledge_event"].items()
        if key != "event_sha256"
    }
    unsealed["statement_changes"] = [{
        "statement_id": "empirical-main",
        "change_type": "removed",
        "changed_fields": [],
    }]
    tampered["knowledge_event"] = event_schema.seal_event(unsealed)

    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="event does not match",
    ):
        records.recover_empirical_promotion_intent(
            project,
            tampered,
            make_current=False,
        )


def test_legacy_prior_package_produces_bounded_real_event(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    old_identity = _identity(version="v1")
    current = records.canonical_package_dir(project, "method-a")
    previous = _write_package(
        current,
        identity=old_identity,
        run_id="legacy-run",
        generation=3,
        wording="A legacy synthesis remains readable.",
        include_knowledge=False,
        index_schema_version=1,
    )
    new_identity = _identity(version="v2")
    output = _stage(
        project,
        "run-004",
        identity=new_identity,
        generation=4,
        wording="The current empirical package has structured knowledge.",
    )

    intent = _plan(project, output, new_identity, "run-004")
    event = intent["knowledge_event"]

    assert event["previous_baseline_status"] == "legacy_unavailable"
    assert event["previous_method_identity"] == old_identity
    assert event["current_method_identity"] == new_identity
    assert event["previous_generation"] == previous["generation"]
    assert event["current_generation"] == previous["generation"] + 1
    assert event["previous_fragment_sha256"] is None
    assert event["statement_changes"] == []
    assert event["dependency_changes"] == []
    assert event["evidence_binding_changes"] == []

    unsealed = {
        key: value
        for key, value in event.items()
        if key != "event_sha256"
    }
    unsealed["statement_changes"] = [{
        "statement_id": "empirical-main",
        "change_type": "added",
        "changed_fields": [],
    }]
    with pytest.raises(
        event_schema.KnowledgeEventValidationError,
        match=(
            "legacy unavailable baseline cannot claim item-level changes"
        ),
    ):
        event_schema.seal_event(unsealed)


def test_planned_execution_rejects_stale_staged_content_and_wrong_identity(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )
    intent = _plan(project, output, identity, "run-001")
    wrong_identity = _identity(version="v2")
    with pytest.raises(
        records.EmpiricalRecordContinuityError,
        match="selected method",
    ):
        records.plan_staged_package_promotion(
            project,
            output,
            operation_id=_operation("run-001"),
            expected_method_identity=wrong_identity,
        )

    (output / records.SYNTHESIS_FILENAME).write_text(
        "# Changed after planning\n",
        encoding="utf-8",
    )
    with pytest.raises(records.EmpiricalRecordError):
        records.promote_staged_package(
            project,
            output,
            retain_backup=True,
            promotion_intent=intent,
        )
    assert records.load_current_package(project, "method-a") is None


def test_lock_held_paths_do_not_reacquire_project_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )

    def unexpected_lock(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("lock_held operation reacquired the project lock")

    monkeypatch.setattr(project_state, "_project_lock", unexpected_lock)
    intent = _plan(
        project,
        output,
        identity,
        "run-001",
        lock_held=True,
    )
    assert records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
        lock_held=True,
    ) is None


def test_planned_execution_fsyncs_files_and_transaction_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )
    intent = _plan(project, output, identity, "run-001")
    paths = _runtime_paths(project, intent)
    file_syncs: list[int] = []
    directory_syncs: list[Path] = []
    monkeypatch.setattr(records.os, "fsync", file_syncs.append)
    monkeypatch.setattr(
        project_state,
        "_sync_state_directory",
        lambda directory: directory_syncs.append(Path(directory)),
    )

    records.promote_staged_package(
        project,
        output,
        lock_held=True,
        retain_backup=True,
        promotion_intent=intent,
    )

    parent = paths["canonical"].parent
    assert len(file_syncs) == 3
    assert directory_syncs[0] == parent
    assert paths["prepared"] in directory_syncs
    assert directory_syncs[-1] == parent
    assert directory_syncs.count(parent) >= 2


def test_dangling_transaction_symlink_is_never_classified_as_absent(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )
    intent = _plan(project, output, identity, "run-001")
    prepared = _runtime_paths(project, intent)["prepared"]
    prepared.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(
            prepared.parent / "missing-target",
            prepared,
            target_is_directory=True,
        )
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(records.EmpiricalRecordError, match="symbolic link"):
        records.recover_empirical_promotion_intent(
            project,
            intent,
            make_current=False,
        )

    assert os.path.lexists(prepared)


def test_complete_checkpoint_directories_with_extras_are_blocked(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, _, _, intent, paths = _replacement_plan(project)
    canonical_extra = paths["canonical"] / "unexpected.txt"
    canonical_extra.write_text("preserve\n", encoding="utf-8")

    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="unexpected content",
    ):
        records.recover_empirical_promotion_intent(
            project,
            intent,
            make_current=False,
        )
    assert canonical_extra.read_text(encoding="utf-8") == "preserve\n"

    project_two = tmp_path / "project-two"
    project_two.mkdir()
    _, _, _, intent_two, paths_two = _replacement_plan(project_two)
    prepared_extra = paths_two["prepared"] / "unexpected.txt"
    prepared_extra.write_text("preserve\n", encoding="utf-8")

    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="unexpected content",
    ):
        records.recover_empirical_promotion_intent(
            project_two,
            intent_two,
            make_current=False,
        )
    assert prepared_extra.read_text(encoding="utf-8") == "preserve\n"


def test_interrupted_rejected_cleanup_resumes_without_deleting_extras(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _, previous, _, intent, paths = _replacement_plan(project)
    os.replace(paths["canonical"], paths["backup"])
    os.replace(paths["prepared"], paths["canonical"])
    os.replace(paths["canonical"], paths["rejected"])
    os.replace(paths["backup"], paths["canonical"])
    (paths["rejected"] / records.KNOWLEDGE_FILENAME).unlink()

    records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
    )
    records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
    )

    assert records.load_current_package(project, "method-a") == previous
    assert not paths["rejected"].exists()

    project_two = tmp_path / "project-two"
    project_two.mkdir()
    _, _, _, intent_two, paths_two = _replacement_plan(project_two)
    os.replace(paths_two["canonical"], paths_two["backup"])
    os.replace(paths_two["prepared"], paths_two["canonical"])
    os.replace(paths_two["canonical"], paths_two["rejected"])
    os.replace(paths_two["backup"], paths_two["canonical"])
    unexpected = paths_two["rejected"] / "unexpected.txt"
    unexpected.write_text("preserve\n", encoding="utf-8")

    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="unexpected content",
    ):
        records.recover_empirical_promotion_intent(
            project_two,
            intent_two,
            make_current=False,
        )
    assert unexpected.read_text(encoding="utf-8") == "preserve\n"


def test_real_hard_exit_leaves_bounded_prepared_package_for_rollback(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )
    intent = _plan(project, output, identity, "run-001")
    intent_path = project / "promotion-intent.json"
    intent_path.write_text(
        json.dumps(intent, sort_keys=True),
        encoding="utf-8",
    )
    script = (
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "from core import empirical_records as records\n"
        "project = Path(sys.argv[1])\n"
        "output = Path(sys.argv[2])\n"
        "intent = json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))\n"
        "original = records._write_prepared_file\n"
        "calls = {'count': 0}\n"
        "def crash_write(path, payload):\n"
        "    calls['count'] += 1\n"
        "    if calls['count'] == 3:\n"
        "        with path.open('xb') as handle:\n"
        "            handle.write(payload[:17])\n"
        "            handle.flush()\n"
        "            os.fsync(handle.fileno())\n"
        "        os._exit(37)\n"
        "    original(path, payload)\n"
        "records._write_prepared_file = crash_write\n"
        "records.promote_staged_package(project, output, lock_held=True, "
        "retain_backup=True, promotion_intent=intent)\n"
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path.cwd())

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(project),
            str(output),
            str(intent_path),
        ],
        cwd=Path.cwd(),
        env=environment,
        check=False,
    )

    assert completed.returncode == 37
    prepared = _runtime_paths(project, intent)["prepared"]
    assert {
        path.name for path in prepared.iterdir()
    } == {
        records.SYNTHESIS_FILENAME,
        records.INDEX_FILENAME,
        records.KNOWLEDGE_FILENAME,
    }
    records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=False,
    )
    assert records.load_current_package(project, "method-a") is None
    assert not prepared.exists()


def test_normal_commit_fsyncs_backup_removal_and_preserves_extras(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity, _, _ = _promote_direct(project)
    output = _stage(
        project,
        "run-002",
        identity=identity,
        generation=2,
        wording="The repaired simulation strengthens the evidence.",
    )
    intent = _plan(project, output, identity, "run-002")
    promotion = records.promote_staged_package(
        project,
        output,
        retain_backup=True,
        promotion_intent=intent,
    )
    backup = _runtime_paths(project, intent)["backup"]
    unexpected = backup / "unexpected.txt"
    unexpected.write_text("preserve\n", encoding="utf-8")

    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="unexpected content",
    ):
        records.commit_empirical_package_promotion(project, promotion)
    assert unexpected.read_text(encoding="utf-8") == "preserve\n"

    unexpected.unlink()
    synced: list[Path] = []
    monkeypatch.setattr(
        project_state,
        "_sync_state_directory",
        lambda directory: synced.append(Path(directory)),
    )
    records.commit_empirical_package_promotion(project, promotion)

    assert not backup.exists()
    assert synced == [backup.parent]


@pytest.mark.parametrize("make_current", [False, True])
def test_recovery_retry_syncs_completed_state_after_first_sync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_current: bool,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = _stage(
        project,
        "run-001",
        identity=identity,
        generation=1,
        wording="The first simulation supports the method.",
    )
    intent = _plan(project, output, identity, "run-001")
    paths = _runtime_paths(project, intent)
    _prepare_planned_package(output, paths)
    parent = paths["canonical"].parent
    syncs: list[Path] = []

    def fail_first_sync(directory: Path) -> None:
        syncs.append(Path(directory))
        if len(syncs) == 1:
            raise OSError("simulated first directory sync failure")

    monkeypatch.setattr(
        project_state,
        "_sync_state_directory",
        fail_first_sync,
    )
    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="could not be synchronized",
    ):
        records.recover_empirical_promotion_intent(
            project,
            intent,
            make_current=make_current,
        )

    if make_current:
        assert _current_run(project) == "run-001"
    else:
        assert records.load_current_package(project, "method-a") is None
    result = records.recover_empirical_promotion_intent(
        project,
        intent,
        make_current=make_current,
    )

    assert syncs == [parent, parent]
    assert result == (
        intent["planned_promotion"] if make_current else None
    )


def test_commit_retry_syncs_parent_after_backup_removal_sync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity, _, _ = _promote_direct(project)
    output = _stage(
        project,
        "run-002",
        identity=identity,
        generation=2,
        wording="The repaired simulation strengthens the evidence.",
    )
    intent = _plan(project, output, identity, "run-002")
    promotion = records.promote_staged_package(
        project,
        output,
        retain_backup=True,
        promotion_intent=intent,
    )
    backup = _runtime_paths(project, intent)["backup"]
    syncs: list[Path] = []

    def fail_first_sync(directory: Path) -> None:
        syncs.append(Path(directory))
        if len(syncs) == 1:
            raise OSError("simulated first directory sync failure")

    monkeypatch.setattr(
        project_state,
        "_sync_state_directory",
        fail_first_sync,
    )
    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="could not be synchronized",
    ):
        records.commit_empirical_package_promotion(project, promotion)
    assert not backup.exists()

    records.commit_empirical_package_promotion(project, promotion)

    assert syncs == [backup.parent, backup.parent]
