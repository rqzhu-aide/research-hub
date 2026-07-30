from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import phase_records


def test_method_identity_accepts_catalog_digest() -> None:
    identity = phase_records.method_identity(
        {
            "stable_id": "method-a",
            "version": "v2",
            "sha256": "a" * 64,
        }
    )
    assert identity == {
        "stable_id": "method-a",
        "version": "v2",
        "definition_sha256": "a" * 64,
    }


def test_method_identity_rejects_an_incomplete_branch() -> None:
    with pytest.raises(phase_records.PhaseRecordError, match="incomplete"):
        phase_records.method_identity(
            {"stable_id": "method-a", "version": "v1"}
        )


def test_manifest_method_identity_uses_frozen_definition_digest() -> None:
    digest = hashlib.sha256(b"method").hexdigest()
    manifest = {
        "method_selection": {
            "stable_id": "method-a",
            "version": "v1",
        },
        "snapshots": {
            "selected_method": {
                "sha256": digest,
            }
        },
    }
    assert phase_records.manifest_method_identity(manifest)[
        "definition_sha256"
    ] == digest


def test_phase_two_literature_basis_uses_exact_frozen_phase_one_files() -> None:
    summary_bytes = b"# Frozen literature synthesis\n"
    summary_sha256 = hashlib.sha256(summary_bytes).hexdigest()
    papers_sha256 = "b" * 64
    index_bytes = json.dumps(
        {
            "schema_version": (
                phase_records.literature_records.REFERENCE_INDEX_SCHEMA_VERSION
            ),
            "kind": "reference_index",
            "source_run_id": "p1-frozen-run",
            "generation": 3,
            "summary_sha256": summary_sha256,
            "papers_sha256": papers_sha256,
            "entries": [],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    frozen = {
        "generation": 3,
        "source_run_id": "p1-frozen-run",
        "summary_bytes": summary_bytes,
        "summary_sha256": summary_sha256,
        "index_bytes": index_bytes,
        "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
    }

    basis = phase_records.phase_two_literature_basis(frozen)

    assert basis == {
        "schema_version": (
            phase_records.method_menu.LITERATURE_BASIS_SCHEMA_VERSION
        ),
        "availability": "available",
        "source_run_id": "p1-frozen-run",
        "generation": 3,
        "synthesis_sha256": summary_sha256,
        "collection_sha256": papers_sha256,
    }
    manifest = {
        "schema_version": 13,
        "phase_slug": phase_records.METHOD_PHASE,
        "phase_two_literature_basis": basis,
    }
    assert phase_records.manifest_phase_two_literature_basis(manifest) == basis


def test_phase_two_seal_passes_only_the_manifest_frozen_literature_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_basis = {
        "schema_version": (
            phase_records.method_menu.LITERATURE_BASIS_SCHEMA_VERSION
        ),
        "availability": "available",
        "source_run_id": "p1-frozen-run",
        "generation": 4,
        "synthesis_sha256": "a" * 64,
        "collection_sha256": "b" * 64,
    }
    captured: dict[str, object] = {}

    def apply_provenance(*_args: object, **kwargs: object) -> dict:
        captured["provenance"] = kwargs
        return {}

    def seal_menu(
        *_args: object,
        **kwargs: object,
    ) -> dict[str, object]:
        captured["seal"] = kwargs
        return {"catalog_sha256": "c" * 64}

    monkeypatch.setattr(
        phase_records.method_menu,
        "apply_run_provenance",
        apply_provenance,
    )
    monkeypatch.setattr(
        phase_records.method_menu,
        "seal_staged_menu",
        seal_menu,
    )
    manifest = {
        "schema_version": 13,
        "phase_slug": phase_records.METHOD_PHASE,
        "knowledge_heads": None,
        "method_catalog_basis": {
            "schema_version": 1,
            "sha256": "d" * 64,
        },
        "phase_two_literature_basis": frozen_basis,
        "run_scope": {
            "scope": "focused_method",
            "focused_method_id": "method-a",
        },
    }

    seal = phase_records.seal_output(
        tmp_path,
        phase_records.METHOD_PHASE,
        tmp_path / "run",
        run_id="p2-run",
        scientific_outcome="Complete",
        manifest=manifest,
    )

    assert captured["provenance"] == {
        "run_id": "p2-run",
        "scientific_outcome": "Complete",
        "review_scope": "focused_method",
        "literature_basis": frozen_basis,
        "focused_method_id": "method-a",
    }
    assert captured["seal"] == {
        "expected_published_catalog_sha256": "d" * 64,
    }
    assert seal["kind"] == "method_catalog"
    assert seal["eligible"] is True


def test_prepare_theory_uses_the_reserved_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def prepare(*_args: object, **kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"source_run_id": kwargs["source_run_id"]}

    monkeypatch.setattr(
        phase_records.theory_records,
        "prepare_staged_theory",
        prepare,
    )
    result = phase_records.prepare_output(
        tmp_path,
        phase_records.THEORY_PHASE,
        tmp_path / "runs" / "01",
        run_id="reserved-run-id",
        method={
            "stable_id": "method-a",
            "version": "v1",
            "definition_sha256": "a" * 64,
        },
    )

    assert captured["source_run_id"] == "reserved-run-id"
    assert result == {"source_run_id": "reserved-run-id"}


def test_empirical_seal_binds_the_complete_knowledge_fragment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    output = project / "runs" / "p4-run"
    output.mkdir(parents=True)
    (output / phase_records.empirical_records.SYNTHESIS_FILENAME).write_text(
        "# Empirical synthesis\n",
        encoding="utf-8",
    )
    (output / phase_records.empirical_records.INDEX_FILENAME).write_text(
        "{}\n",
        encoding="utf-8",
    )
    knowledge = output / phase_records.empirical_records.KNOWLEDGE_FILENAME
    knowledge.write_text('{"coverage":"complete"}\n', encoding="utf-8")
    monkeypatch.setattr(
        phase_records.empirical_records,
        "validate_staged_package",
        lambda *_args, **_kwargs: {"generation": 1},
    )

    first = phase_records._empirical_seal(project, output)
    assert first["knowledge_fragment"]["sha256"] == hashlib.sha256(
        knowledge.read_bytes()
    ).hexdigest()
    assert first["knowledge_fragment"]["size"] == knowledge.stat().st_size

    knowledge.write_text('{"coverage":"complete","changed":true}\n', encoding="utf-8")
    second = phase_records._empirical_seal(project, output)
    assert second["knowledge_fragment"] != first["knowledge_fragment"]
    with pytest.raises(
        phase_records.PhaseRecordError,
        match="changed after submission",
    ):
        phase_records._verify_empirical_seal(project, output, first)


def test_current_context_includes_current_knowledge_fragments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = {
        "stable_id": "method-a",
        "version": "v1",
        "definition_sha256": "a" * 64,
    }
    theory_dir = project / "theory-current"
    empirical_dir = project / "empirical-current"
    theory_dir.mkdir()
    empirical_dir.mkdir()
    for directory, names in (
        (
            theory_dir,
            (
                phase_records.theory_records.THEORY_FILENAME,
                phase_records.theory_records.RECORD_FILENAME,
                phase_records.theory_records.KNOWLEDGE_FILENAME,
            ),
        ),
        (
            empirical_dir,
            (
                phase_records.empirical_records.SYNTHESIS_FILENAME,
                phase_records.empirical_records.INDEX_FILENAME,
                phase_records.empirical_records.KNOWLEDGE_FILENAME,
            ),
        ),
    ):
        for name in names:
            (directory / name).write_text(f"current {name}\n", encoding="utf-8")

    theory_record = {
        "schema_version": phase_records.theory_records.SCHEMA_VERSION,
        "method_identity": identity,
        "source_run_id": "p3-run",
        "generation": 2,
        "knowledge_file": phase_records.theory_records.KNOWLEDGE_FILENAME,
    }
    empirical_record = {
        "method": identity,
        "source_run_id": "p4-run",
        "generation": 3,
    }
    monkeypatch.setattr(phase_records, "_literature_record", lambda _root: None)
    monkeypatch.setattr(
        phase_records.theory_records,
        "load_current_theory",
        lambda *_args: theory_record,
    )
    monkeypatch.setattr(
        phase_records.theory_records,
        "current_theory_directory",
        lambda *_args: theory_dir,
    )
    monkeypatch.setattr(
        phase_records.empirical_records,
        "load_current_package",
        lambda *_args: empirical_record,
    )
    monkeypatch.setattr(
        phase_records.empirical_records,
        "canonical_package_dir",
        lambda *_args: empirical_dir,
    )

    records = phase_records.current_context_records(project, method=identity)
    by_key = {record["key"]: record for record in records}
    theory_names = {
        Path(file_record["path"]).name
        for file_record in by_key["p3_theory"]["files"]
    }
    empirical_names = {
        Path(file_record["path"]).name
        for file_record in by_key["p4_empirical"]["files"]
    }
    assert theory_names == {
        phase_records.theory_records.THEORY_FILENAME,
        phase_records.theory_records.RECORD_FILENAME,
        phase_records.theory_records.KNOWLEDGE_FILENAME,
    }
    assert empirical_names == {
        phase_records.empirical_records.SYNTHESIS_FILENAME,
        phase_records.empirical_records.INDEX_FILENAME,
        phase_records.empirical_records.KNOWLEDGE_FILENAME,
    }

    theory_record.pop("knowledge_file")
    (empirical_dir / phase_records.empirical_records.KNOWLEDGE_FILENAME).unlink()
    legacy = phase_records.current_context_records(project, method=identity)
    legacy_by_key = {record["key"]: record for record in legacy}
    assert len(legacy_by_key["p3_theory"]["files"]) == 2
    assert len(legacy_by_key["p4_empirical"]["files"]) == 2


def test_current_context_rejects_literature_changed_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    summary = project / phase_records.literature_records.LITERATURE_SUMMARY
    index = project / phase_records.literature_records.REFERENCE_INDEX
    summary.parent.mkdir(parents=True)
    summary.write_text(
        "# Literature synthesis\n\nValidated content.\n",
        encoding="utf-8",
    )
    index.write_text('{"validated": true}\n', encoding="utf-8")
    validated = {
        "generation": 1,
        "source_run_id": "p1-run",
        "summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
        "index_sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        "papers_sha256": "a" * 64,
    }
    monkeypatch.setattr(
        phase_records,
        "_literature_record",
        lambda _root: dict(validated),
    )
    original = phase_records._relative_file_record
    changed = False

    def mutate_then_record(
        root: Path,
        path: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal changed
        if path == summary and not changed:
            changed = True
            summary.write_text(
                "# Literature synthesis\n\nChanged content.\n",
                encoding="utf-8",
            )
        return original(root, path, **kwargs)

    monkeypatch.setattr(
        phase_records,
        "_relative_file_record",
        mutate_then_record,
    )

    with pytest.raises(
        phase_records.PhaseRecordError,
        match="changed after its current record was validated",
    ):
        phase_records.current_context_records(project)


def test_theory_seal_accepts_partial_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Partial Phase 3 outcome seals and promotes a theory record.

    Policy change (ISSUES.md #12): the theory seal gate uses the same
    Complete-or-Partial eligibility as every other phase.
    """

    captured: dict[str, object] = {}

    def seal_theory(
        *_args: object, **kwargs: object
    ) -> dict[str, object]:
        captured.update(kwargs)
        return {"record": "sealed-partial-theory"}

    monkeypatch.setattr(
        phase_records.theory_records,
        "seal_staged_theory",
        seal_theory,
    )
    manifest = {
        "schema_version": 13,
        "phase_slug": phase_records.THEORY_PHASE,
        "knowledge_heads": None,
        "method_selection": {
            "kind": "method",
            "stable_id": "method-a",
            "version": "v1",
            "definition_sha256": "a" * 64,
        },
        "method_catalog_basis": None,
        "counterpart_basis": None,
        "snapshots": {
            "selected_method": {
                "stable_id": "method-a",
                "version": "v1",
                "sha256": "a" * 64,
            }
        },
    }

    seal = phase_records.seal_output(
        tmp_path,
        phase_records.THEORY_PHASE,
        tmp_path / "run",
        run_id="p3-run",
        scientific_outcome="Partial",
        manifest=manifest,
    )

    assert seal["kind"] == "theory"
    assert seal["eligible"] is True
    assert seal["data"] == {"record": "sealed-partial-theory"}
    assert captured["scientific_outcome"] == "Partial"
    assert captured["source_run_id"] == "p3-run"


def test_theory_seal_still_rejects_failed_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def seal_theory(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("Failed outcome must not reach theory sealing")

    monkeypatch.setattr(
        phase_records.theory_records,
        "seal_staged_theory",
        seal_theory,
    )
    manifest = {
        "schema_version": 13,
        "phase_slug": phase_records.THEORY_PHASE,
        "knowledge_heads": None,
        "method_selection": {
            "kind": "method",
            "stable_id": "method-a",
            "version": "v1",
            "definition_sha256": "a" * 64,
        },
        "method_catalog_basis": None,
        "counterpart_basis": None,
        "snapshots": {
            "selected_method": {
                "stable_id": "method-a",
                "version": "v1",
                "sha256": "a" * 64,
            }
        },
    }

    seal = phase_records.seal_output(
        tmp_path,
        phase_records.THEORY_PHASE,
        tmp_path / "run",
        run_id="p3-run",
        scientific_outcome="Failed",
        manifest=manifest,
    )

    assert seal["kind"] == "none"
    assert seal["eligible"] is False
    assert seal["data"] is None
