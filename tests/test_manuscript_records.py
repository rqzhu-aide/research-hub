"""Behavioral tests for the canonical Phase 5 working manuscript."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core import manuscript_records as manuscripts


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _identity(stable_id: str = "method-a", version: str = "v1") -> dict[str, str]:
    return {
        "stable_id": stable_id,
        "version": version,
        "definition_sha256": _digest(f"{stable_id}:{version}"),
    }


def _basis(
    identity: dict[str, str],
    *,
    p1: str = "p1-a",
    p1_collection: str = "p1-collection-a",
    p3: str = "p3-a",
    p4: str = "p4-a",
    p3_generation: int = 1,
    p4_generation: int = 1,
) -> dict[str, dict[str, object]]:
    return {
        "p1_synthesis": {
            "identity": "literature-synthesis",
            "sha256": _digest(p1),
            "generation": 1,
        },
        "p1_collection": {
            "identity": "reference-card-collection",
            "sha256": _digest(p1_collection),
            "generation": 1,
        },
        "p2_definition": {
            "identity": identity,
            "sha256": identity["definition_sha256"],
            "generation": 1,
        },
        "p3_record": {
            "identity": f"{identity['stable_id']}:theory",
            "sha256": _digest(p3),
            "generation": p3_generation,
        },
        "p4_synthesis": {
            "identity": f"{identity['stable_id']}:empirical-synthesis",
            "sha256": _digest(p4),
            "generation": p4_generation,
        },
        "p4_index": {
            "identity": f"{identity['stable_id']}:evidence-index",
            "sha256": _digest(f"{p4}:index"),
            "generation": p4_generation,
        },
    }


def _stage(
    project: Path,
    run_name: str,
    content: str,
    *,
    identity: dict[str, str],
    basis: dict[str, dict[str, object]],
    outcome: str = "Complete",
) -> tuple[Path, dict[str, object]]:
    output = project / "runs" / run_name
    output.mkdir(parents=True)
    (output / manuscripts.MANUSCRIPT_FILENAME).write_text(
        content, encoding="utf-8"
    )
    seal = manuscripts.seal_staged_manuscript(
        project,
        output,
        method_identity=identity,
        upstream_basis=basis,
        source_run_id=run_name,
        scientific_outcome=outcome,
    )
    return output, seal


def _promote(
    project: Path,
    output: Path,
    seal: dict[str, object],
    identity: dict[str, str],
    basis: dict[str, dict[str, object]],
) -> dict[str, object]:
    return manuscripts.promote_staged_manuscript(
        project,
        output,
        seal,
        expected_method_identity=identity,
        expected_upstream_basis=basis,
    )


def test_initial_and_update_promotion_keep_one_working_draft(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    first_output, first_seal = _stage(
        project,
        "run-1",
        "# Manuscript\n\nInitial complete draft.",
        identity=identity,
        basis=basis,
    )
    first = _promote(project, first_output, first_seal, identity, basis)
    assert first["generation"] == 1

    second_output, second_seal = _stage(
        project,
        "run-2",
        "# Manuscript\n\nRevised complete draft.",
        identity=identity,
        basis=basis,
    )
    second = _promote(project, second_output, second_seal, identity, basis)
    assert second["generation"] == 2
    assert manuscripts.load_current_manuscript(project, "method-a") == second
    current_dir = manuscripts.current_manuscript_directory(project, "method-a")
    assert sorted(path.name for path in current_dir.iterdir()) == [
        manuscripts.MANUSCRIPT_FILENAME,
        manuscripts.RECORD_FILENAME,
    ]
    assert "Revised complete draft" in (
        current_dir / manuscripts.MANUSCRIPT_FILENAME
    ).read_text(encoding="utf-8")


def test_failed_or_stale_attempt_leaves_current_draft_unchanged(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    output, seal = _stage(
        project,
        "run-good",
        "# Manuscript\n\nCurrent draft.",
        identity=identity,
        basis=basis,
    )
    prior = _promote(project, output, seal, identity, basis)

    failed = project / "runs" / "run-failed"
    failed.mkdir(parents=True)
    (failed / manuscripts.MANUSCRIPT_FILENAME).write_text(
        "# Manuscript\n\nFailed revision.", encoding="utf-8"
    )
    with pytest.raises(manuscripts.ManuscriptValidationError, match="Complete"):
        manuscripts.seal_staged_manuscript(
            project,
            failed,
            method_identity=identity,
            upstream_basis=basis,
            source_run_id="run-failed",
            scientific_outcome="Failed",
        )

    stale_output, stale_seal = _stage(
        project,
        "run-stale",
        "# Manuscript\n\nDraft from old inputs.",
        identity=identity,
        basis=basis,
    )
    changed_basis = _basis(identity, p3="p3-new", p3_generation=2)
    with pytest.raises(manuscripts.ManuscriptStageChanged, match="basis"):
        _promote(project, stale_output, stale_seal, identity, changed_basis)
    assert manuscripts.load_current_manuscript(project, "method-a") == prior


def test_method_mismatch_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    original = _identity(version="v1")
    original_basis = _basis(original)
    output, seal = _stage(
        project,
        "run-1",
        "# Manuscript\n\nVersion one.",
        identity=original,
        basis=original_basis,
    )
    prior = _promote(project, output, seal, original, original_basis)

    candidate_output, candidate_seal = _stage(
        project,
        "run-2",
        "# Manuscript\n\nCandidate.",
        identity=original,
        basis=original_basis,
    )
    revised = _identity(version="v2")
    with pytest.raises(manuscripts.ManuscriptStageChanged, match="method identity"):
        _promote(
            project,
            candidate_output,
            candidate_seal,
            revised,
            _basis(revised),
        )
    assert manuscripts.load_current_manuscript(project, "method-a") == prior


def test_upstream_comparison_identifies_only_changed_inputs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    output, seal = _stage(
        project,
        "run-1",
        "# Manuscript\n\nCurrent.",
        identity=identity,
        basis=basis,
    )
    record = _promote(project, output, seal, identity, basis)
    current = manuscripts.compare_manuscript_basis(
        record, method_identity=identity, upstream_basis=basis
    )
    assert current == {
        "status": "current",
        "changed_inputs": [],
        "changed_input_labels": [],
    }

    changed = _basis(
        identity,
        p1="p1-new",
        p4="p4-new",
        p4_generation=2,
    )
    assessment = manuscripts.assess_current_manuscript(
        project,
        "method-a",
        method_identity=identity,
        upstream_basis=changed,
    )
    assert assessment["status"] == "update_needed"
    assert assessment["changed_inputs"] == [
        "p1_synthesis",
        "p4_synthesis",
        "p4_index",
    ]
    assert assessment["changed_input_labels"] == [
        "Phase 1 literature synthesis",
        "Phase 4 empirical synthesis",
        "Phase 4 evidence index",
    ]


def test_reference_collection_change_is_independent_of_synthesis(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    output, seal = _stage(
        project,
        "run-1",
        "# Manuscript\n\nCurrent.",
        identity=identity,
        basis=basis,
    )
    _promote(project, output, seal, identity, basis)

    changed = _basis(identity, p1_collection="p1-collection-new")
    assessment = manuscripts.assess_current_manuscript(
        project,
        "method-a",
        method_identity=identity,
        upstream_basis=changed,
    )

    assert assessment["status"] == "update_needed"
    assert assessment["changed_inputs"] == ["p1_collection"]
    assert assessment["changed_input_labels"] == [
        "Phase 1 reference collection"
    ]


def test_legacy_seal_remains_promotable_and_requires_collection_review(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    output, seal = _stage(
        project,
        "legacy-run",
        "# Manuscript\n\nLegacy complete draft.",
        identity=identity,
        basis=basis,
    )
    legacy_seal = {
        **seal,
        "schema_version": manuscripts.LEGACY_SCHEMA_VERSION,
        "upstream_basis": {
            key: value
            for key, value in seal["upstream_basis"].items()
            if key != "p1_collection"
        },
    }

    promoted = _promote(
        project,
        output,
        legacy_seal,
        identity,
        basis,
    )
    loaded = manuscripts.load_current_manuscript(project, "method-a")
    comparison = manuscripts.compare_manuscript_basis(
        loaded,
        method_identity=identity,
        upstream_basis=basis,
    )

    assert promoted["schema_version"] == manuscripts.LEGACY_SCHEMA_VERSION
    assert loaded == promoted
    assert "p1_collection" not in loaded["upstream_basis"]
    assert comparison == {
        "status": "update_needed",
        "changed_inputs": ["p1_collection"],
        "changed_input_labels": ["Phase 1 reference collection"],
    }

    replacement_output, replacement_seal = _stage(
        project,
        "current-run",
        "# Manuscript\n\nCurrent complete draft.",
        identity=identity,
        basis=basis,
    )
    replacement = manuscripts.promote_staged_manuscript(
        project,
        replacement_output,
        replacement_seal,
        expected_method_identity=identity,
        expected_upstream_basis=basis,
        retain_backup=True,
    )
    assert manuscripts.load_current_manuscript(
        project, "method-a"
    )["schema_version"] == manuscripts.SCHEMA_VERSION

    manuscripts.rollback_manuscript_promotion(project, replacement)
    assert manuscripts.load_current_manuscript(
        project, "method-a"
    ) == promoted


def test_legacy_seal_cannot_replace_a_schema_two_manuscript(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    current_output, current_seal = _stage(
        project,
        "current-run",
        "# Manuscript\n\nCurrent schema 2 draft.",
        identity=identity,
        basis=basis,
    )
    current = _promote(
        project,
        current_output,
        current_seal,
        identity,
        basis,
    )
    legacy_output, seal = _stage(
        project,
        "late-legacy-run",
        "# Manuscript\n\nLate legacy draft.",
        identity=identity,
        basis=basis,
    )
    legacy_seal = {
        **seal,
        "schema_version": manuscripts.LEGACY_SCHEMA_VERSION,
        "upstream_basis": {
            key: value
            for key, value in seal["upstream_basis"].items()
            if key != "p1_collection"
        },
    }

    with pytest.raises(
        manuscripts.ManuscriptStageChanged,
        match="legacy manuscript cannot replace",
    ):
        _promote(project, legacy_output, legacy_seal, identity, basis)

    assert manuscripts.load_current_manuscript(project, "method-a") == current


def test_method_branches_are_independent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity_a = _identity("method-a")
    identity_b = _identity("method-b")
    basis_a = _basis(identity_a)
    basis_b = _basis(identity_b)
    output_a, seal_a = _stage(
        project,
        "run-a1",
        "# Manuscript A\n\nA1.",
        identity=identity_a,
        basis=basis_a,
    )
    output_b, seal_b = _stage(
        project,
        "run-b1",
        "# Manuscript B\n\nB1.",
        identity=identity_b,
        basis=basis_b,
    )
    _promote(project, output_a, seal_a, identity_a, basis_a)
    record_b = _promote(project, output_b, seal_b, identity_b, basis_b)

    output_a2, seal_a2 = _stage(
        project,
        "run-a2",
        "# Manuscript A\n\nA2.",
        identity=identity_a,
        basis=basis_a,
    )
    _promote(project, output_a2, seal_a2, identity_a, basis_a)
    assert manuscripts.load_current_manuscript(project, "method-a")[
        "generation"
    ] == 2
    assert manuscripts.load_current_manuscript(project, "method-b") == record_b


def test_review_snapshot_deduplicates_and_detects_tampering(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    output, seal = _stage(
        project,
        "run-1",
        "# Manuscript\n\nExact reviewed bytes.\n",
        identity=identity,
        basis=basis,
    )
    _promote(project, output, seal, identity, basis)

    first = manuscripts.preserve_current_for_review(project, "method-a")
    second = manuscripts.preserve_current_for_review(project, "method-a")
    assert first == second
    current_bytes = (
        manuscripts.current_manuscript_directory(project, "method-a")
        / manuscripts.MANUSCRIPT_FILENAME
    ).read_bytes()
    assert (
        manuscripts.read_review_snapshot(project, first["sha256"])
        == current_bytes
    )

    from core.project_state import state_dir

    snapshot_path = state_dir(project) / first["path"]
    snapshot_path.write_bytes(b"tampered")
    with pytest.raises(manuscripts.ManuscriptRecordCorrupt, match="content address"):
        manuscripts.read_review_snapshot(project, first["sha256"])
    with pytest.raises(manuscripts.ManuscriptRecordCorrupt, match="content address"):
        manuscripts.preserve_current_for_review(project, "method-a")


def test_prepare_manuscript_uses_template_for_the_first_branch_draft(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = project / "runs" / "new-run"

    prepared = manuscripts.prepare_staged_manuscript(project, output, identity)
    payload = (output / manuscripts.MANUSCRIPT_FILENAME).read_bytes()
    assert prepared["source"] == "template"
    assert prepared["reason"] == "no_current"
    assert prepared["source_generation"] is None
    assert prepared["source_method_identity"] is None
    assert prepared["sha256"] == hashlib.sha256(payload).hexdigest()
    assert b"first complete draft" in payload
    assert identity["definition_sha256"].encode() in payload


def test_prepare_manuscript_preserves_the_branch_draft_for_revision(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    current_output, seal = _stage(
        project,
        "run-current",
        "# Manuscript\n\nCurrent working draft.",
        identity=identity,
        basis=basis,
    )
    _promote(project, current_output, seal, identity, basis)
    canonical_bytes = (
        manuscripts.current_manuscript_directory(project, "method-a")
        / manuscripts.MANUSCRIPT_FILENAME
    ).read_bytes()

    exact_output = project / "runs" / "run-exact"
    exact = manuscripts.prepare_staged_manuscript(project, exact_output, identity)
    assert exact["source"] == "current"
    assert exact["reason"] == "exact_method_match"
    assert exact["source_generation"] == 1
    assert (exact_output / manuscripts.MANUSCRIPT_FILENAME).read_bytes() == canonical_bytes

    revised = _identity(version="v2")
    revised_output = project / "runs" / "run-revised"
    changed = manuscripts.prepare_staged_manuscript(
        project, revised_output, revised
    )
    assert changed["source"] == "current"
    assert changed["reason"] == "method_revision_pending"
    assert changed["source_method_identity"] == identity
    assert (
        revised_output / manuscripts.MANUSCRIPT_FILENAME
    ).read_bytes() == canonical_bytes


def test_prepare_manuscript_rejects_corrupt_current_without_touching_stage(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    current_output, seal = _stage(
        project,
        "run-current",
        "# Manuscript\n\nIntact.",
        identity=identity,
        basis=basis,
    )
    _promote(project, current_output, seal, identity, basis)
    canonical = manuscripts.current_manuscript_directory(project, "method-a")
    (canonical / manuscripts.MANUSCRIPT_FILENAME).write_text(
        "# Manuscript\n\nTampered.", encoding="utf-8"
    )
    output = project / "runs" / "new-run"
    output.mkdir(parents=True)
    staged = output / manuscripts.MANUSCRIPT_FILENAME
    staged.write_bytes(b"existing staged work")

    with pytest.raises(manuscripts.ManuscriptRecordCorrupt, match="does not match"):
        manuscripts.prepare_staged_manuscript(project, output, identity)
    assert staged.read_bytes() == b"existing staged work"


def test_prepare_manuscript_write_is_atomic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = project / "runs" / "new-run"
    output.mkdir(parents=True)
    staged = output / manuscripts.MANUSCRIPT_FILENAME
    staged.write_bytes(b"existing staged work")
    real_replace = manuscripts.os.replace

    def fail_stage_install(source: object, destination: object) -> None:
        if Path(destination) == staged:
            raise OSError("injected staging failure")
        real_replace(source, destination)

    monkeypatch.setattr(manuscripts.os, "replace", fail_stage_install)
    with pytest.raises(OSError, match="injected staging"):
        manuscripts.prepare_staged_manuscript(project, output, identity)
    assert staged.read_bytes() == b"existing staged work"
    assert not list(output.glob(".*.tmp"))


def test_current_manuscript_record_rejects_duplicate_json_fields(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    basis = _basis(identity)
    output, seal = _stage(
        project,
        "run-1",
        "# Manuscript\n\nCurrent complete draft.",
        identity=identity,
        basis=basis,
    )
    _promote(project, output, seal, identity, basis)
    record_path = (
        manuscripts.current_manuscript_directory(project, "method-a")
        / manuscripts.RECORD_FILENAME
    )
    original = record_path.read_text(encoding="utf-8")
    record_path.write_text(
        original.replace("{", '{\n  "schema_version": 2,', 1),
        encoding="utf-8",
    )

    with pytest.raises(
        manuscripts.ManuscriptRecordCorrupt,
        match="duplicate field 'schema_version'",
    ):
        manuscripts.load_current_manuscript(project, "method-a")
