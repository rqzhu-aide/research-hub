"""Focused tests for schema 12 and 13 Phase 5 frozen-source projection."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from core import (
    empirical_records,
    empirical_schema,
    literature_records,
    manuscript_records,
    phase5_projection,
    phase_records,
    project_state,
    theory_records,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _method(
    *,
    version: str = "v2",
    digest_label: str = "selected-method-v2",
) -> dict[str, str]:
    return {
        "stable_id": "method-a",
        "version": version,
        "definition_sha256": _digest(digest_label),
    }


def _upstream_basis(
    method: dict[str, str],
    *,
    label: str,
) -> dict[str, dict[str, Any]]:
    return manuscript_records.normalize_upstream_basis(
        {
            "p1_synthesis": {
                "identity": "literature-synthesis",
                "sha256": _digest(f"{label}-p1"),
                "generation": 1,
            },
            "p1_collection": {
                "identity": "reference-card-collection",
                "sha256": _digest(f"{label}-p1-collection"),
                "generation": 1,
            },
            "p2_definition": {
                "identity": method,
                "sha256": method["definition_sha256"],
                "generation": None,
            },
            "p3_record": {
                "identity": f"{method['stable_id']}:theory",
                "sha256": _digest(f"{label}-p3"),
                "generation": 1,
            },
            "p4_synthesis": {
                "identity": f"{method['stable_id']}:empirical-synthesis",
                "sha256": _digest(f"{label}-p4-synthesis"),
                "generation": 1,
            },
            "p4_index": {
                "identity": f"{method['stable_id']}:evidence-index",
                "sha256": _digest(f"{label}-p4-index"),
                "generation": 1,
            },
        },
        method_identity=method,
    )


def _publish_current_manuscript(
    project: Path,
    method: dict[str, str],
    *,
    run_id: str = "old-p5-run",
    text: str = "# Existing manuscript\n\nExact frozen source.\n",
) -> dict[str, Any]:
    output = project / "runs" / run_id
    output.mkdir(parents=True)
    (output / manuscript_records.MANUSCRIPT_FILENAME).write_text(
        text,
        encoding="utf-8",
    )
    basis = _upstream_basis(method, label=run_id)
    seal = manuscript_records.seal_staged_manuscript(
        project,
        output,
        method_identity=method,
        upstream_basis=basis,
        source_run_id=run_id,
        scientific_outcome="Complete",
    )
    return manuscript_records.promote_staged_manuscript(
        project,
        output,
        seal,
        expected_method_identity=method,
        expected_upstream_basis=basis,
    )


def _frozen_file(
    context: Path,
    *,
    name: str,
    source_path: str,
    payload: bytes,
) -> dict[str, Any]:
    path = context / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "source_path": source_path,
        "size": len(payload),
    }


def _frozen_record(
    *,
    key: str,
    kind: str,
    generation: int,
    files: list[dict[str, Any]],
    method: dict[str, str] | None,
    source_run_id: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "kind": kind,
        "source_run_id": source_run_id,
        "generation": generation,
        "method_identity": method,
        "files": files,
    }


def _manifest(
    project: Path,
    method: dict[str, str],
    *,
    include_current_manuscript: bool,
    run_id: str = "p5-launch",
) -> tuple[dict[str, Any], dict[str, bytes]]:
    context = (
        project_state.state_dir(project)
        / "runs"
        / phase_records.MANUSCRIPT_PHASE
        / f"{run_id}.context"
    )
    context.mkdir(parents=True)
    payloads = {
        "method": b"# Selected method\n\nExact definition.\n",
        "p1": b"# Literature synthesis\n\nFrozen literature.\n",
        "p3_manuscript": b"# Theory\n\nFrozen complete proof.\n",
        "p4_synthesis": b"# Empirical synthesis\n\nFrozen evidence.\n",
    }
    p1_collection_digest = _digest("frozen-p1-reference-collection")
    payloads["p1_index"] = (
        json.dumps(
            {
                "schema_version": 2,
                "kind": "reference_index",
                "source_run_id": "p1-current",
                "generation": 3,
                "summary_sha256": hashlib.sha256(payloads["p1"]).hexdigest(),
                "papers_sha256": p1_collection_digest,
                "entries": [],
            },
            sort_keys=True,
        ) + "\n"
    ).encode("utf-8")
    method["definition_sha256"] = hashlib.sha256(payloads["method"]).hexdigest()
    payloads["p3"] = (
        json.dumps(
            {
                "schema_version": theory_records.LEGACY_SCHEMA_VERSION,
                "method_identity": method,
                "source_run_id": "p3-current",
                "scientific_outcome": "Complete",
                "structurally_self_contained": True,
                "manuscript_sha256": hashlib.sha256(
                    payloads["p3_manuscript"]
                ).hexdigest(),
                "manuscript_size": len(payloads["p3_manuscript"]),
                "generation": 5,
                "manuscript_file": theory_records.THEORY_FILENAME,
            },
            sort_keys=True,
        ) + "\n"
    ).encode("utf-8")
    payloads["p4_index"] = (
        json.dumps(
            {
                "schema_version": empirical_schema.LEGACY_INDEX_SCHEMA_VERSION,
                "kind": empirical_records.INDEX_KIND,
                "method": method,
                "generation": 7,
                "source_run_id": "p4-current",
                "synthesis": {
                    "path": empirical_records.SYNTHESIS_FILENAME,
                    "sha256": hashlib.sha256(
                        payloads["p4_synthesis"]
                    ).hexdigest(),
                    "size": len(payloads["p4_synthesis"]),
                },
                "entries": [],
            },
            sort_keys=True,
        ) + "\n"
    ).encode("utf-8")
    selected_path = context / "methods" / "selected-method.md"
    selected_path.parent.mkdir(parents=True)
    selected_path.write_bytes(payloads["method"])

    theory_directory = theory_records.current_theory_directory(
        project, method["stable_id"]
    ).relative_to(project).as_posix()
    empirical_directory = empirical_records.canonical_package_dir(
        project, method["stable_id"]
    ).relative_to(project).as_posix()
    records = [
        _frozen_record(
            key=phase5_projection.P1_KEY,
            kind="current_literature",
            generation=3,
            source_run_id="p1-current",
            method=None,
            files=[
                _frozen_file(
                    context,
                    name="current/p1/literature-summary.md",
                    source_path=Path(
                        literature_records.LITERATURE_SUMMARY
                    ).as_posix(),
                    payload=payloads["p1"],
                ),
                _frozen_file(
                    context,
                    name="current/p1/reference-index.json",
                    source_path=Path(
                        literature_records.REFERENCE_INDEX
                    ).as_posix(),
                    payload=payloads["p1_index"],
                ),
            ],
        ),
        _frozen_record(
            key=phase5_projection.P3_KEY,
            kind="current_theory",
            generation=5,
            source_run_id="p3-current",
            method=method,
            files=[
                _frozen_file(
                    context,
                    name="current/p3/theory-manuscript.md",
                    source_path=(
                        f"{theory_directory}/{theory_records.THEORY_FILENAME}"
                    ),
                    payload=payloads["p3_manuscript"],
                ),
                _frozen_file(
                    context,
                    name="current/p3/record.json",
                    source_path=(
                        f"{theory_directory}/{theory_records.RECORD_FILENAME}"
                    ),
                    payload=payloads["p3"],
                ),
            ],
        ),
        _frozen_record(
            key=phase5_projection.P4_KEY,
            kind="current_empirical",
            generation=7,
            source_run_id="p4-current",
            method=method,
            files=[
                _frozen_file(
                    context,
                    name="current/p4/synthesis.md",
                    source_path=(
                        f"{empirical_directory}/"
                        f"{empirical_records.SYNTHESIS_FILENAME}"
                    ),
                    payload=payloads["p4_synthesis"],
                ),
                _frozen_file(
                    context,
                    name="current/p4/index.json",
                    source_path=(
                        f"{empirical_directory}/{empirical_records.INDEX_FILENAME}"
                    ),
                    payload=payloads["p4_index"],
                ),
            ],
        ),
    ]
    if include_current_manuscript:
        current = manuscript_records.load_current_manuscript(
            project, method["stable_id"]
        )
        assert current is not None
        directory = manuscript_records.current_manuscript_directory(
            project, method["stable_id"]
        )
        relative = directory.relative_to(project).as_posix()
        records.append(
            _frozen_record(
                key=phase5_projection.P5_KEY,
                kind="current_manuscript",
                generation=current["generation"],
                source_run_id=current["source_run_id"],
                method=None,
                files=[
                    _frozen_file(
                        context,
                        name="current/p5/manuscript.md",
                        source_path=(
                            f"{relative}/{manuscript_records.MANUSCRIPT_FILENAME}"
                        ),
                        payload=(
                            directory / manuscript_records.MANUSCRIPT_FILENAME
                        ).read_bytes(),
                    ),
                    _frozen_file(
                        context,
                        name="current/p5/record.json",
                        source_path=(
                            f"{relative}/{manuscript_records.RECORD_FILENAME}"
                        ),
                        payload=(
                            directory / manuscript_records.RECORD_FILENAME
                        ).read_bytes(),
                    ),
                ],
            )
        )
    manifest = {
        "schema_version": 13,
        "phase_slug": phase_records.MANUSCRIPT_PHASE,
        "run_id": run_id,
        "method_catalog_basis": None,
        "method_selection": {
            "stable_id": method["stable_id"],
            "version": method["version"],
        },
        "snapshots": {
            "selected_method": {
                "path": str(selected_path),
                "sha256": method["definition_sha256"],
                "stable_id": method["stable_id"],
                "version": method["version"],
                "label": method["stable_id"],
                "catalog_path": f"methods/{method['stable_id']}.md",
            },
            "current_records": records,
        },
    }
    return manifest, payloads


def test_projection_derives_exact_basis_and_frozen_current_manuscript(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    _publish_current_manuscript(project, method)
    manifest, payloads = _manifest(
        project,
        method,
        include_current_manuscript=True,
    )

    state = phase5_projection.derive_frozen_phase5_state(
        project, manifest, method
    )

    assert state["upstream_basis"] == {
        "p1_synthesis": {
            "identity": "literature-synthesis",
            "sha256": hashlib.sha256(payloads["p1"]).hexdigest(),
            "generation": 3,
        },
        "p1_collection": {
            "identity": "reference-card-collection",
            "sha256": json.loads(payloads["p1_index"])["papers_sha256"],
            "generation": 3,
        },
        "p2_definition": {
            "identity": method,
            "sha256": method["definition_sha256"],
            "generation": None,
        },
        "p3_record": {
            "identity": "method-a:theory",
            "sha256": hashlib.sha256(payloads["p3"]).hexdigest(),
            "generation": 5,
        },
        "p4_synthesis": {
            "identity": "method-a:empirical-synthesis",
            "sha256": hashlib.sha256(payloads["p4_synthesis"]).hexdigest(),
            "generation": 7,
        },
        "p4_index": {
            "identity": "method-a:evidence-index",
            "sha256": hashlib.sha256(payloads["p4_index"]).hexdigest(),
            "generation": 7,
        },
    }
    assert state["p5_manuscript"] is not None
    assert state["p5_manuscript"]["record"]["generation"] == 1
    assert state["p5_manuscript"]["manuscript_bytes"].startswith(
        b"# Existing manuscript"
    )


def test_projection_rejects_internally_inconsistent_reference_index(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    manifest, _ = _manifest(
        project,
        method,
        include_current_manuscript=False,
    )
    p1_record = next(
        record
        for record in manifest["snapshots"]["current_records"]
        if record["key"] == phase5_projection.P1_KEY
    )
    index_file = next(
        file_record
        for file_record in p1_record["files"]
        if file_record["source_path"]
        == Path(literature_records.REFERENCE_INDEX).as_posix()
    )
    index_path = Path(index_file["path"])
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["summary_sha256"] = _digest("another-summary")
    payload = (
        json.dumps(index, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    index_path.write_bytes(payload)
    index_file["sha256"] = hashlib.sha256(payload).hexdigest()
    index_file["size"] = len(payload)

    with pytest.raises(
        phase5_projection.Phase5ProjectionError,
        match="frozen reference index does not match its launch inventory",
    ):
        phase5_projection.derive_frozen_phase5_state(
            project,
            manifest,
            method,
        )


def test_explicit_absence_uses_template_even_if_live_manuscript_appears(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    manifest, _ = _manifest(
        project,
        method,
        include_current_manuscript=False,
    )
    _publish_current_manuscript(
        project,
        method,
        text="# Later live manuscript\n\nThis appeared after launch.\n",
    )
    state = phase_records.frozen_phase5_state(project, manifest, method)
    output = project / "runs" / "assembly"

    prepared = phase_records.prepare_output(
        project,
        phase_records.MANUSCRIPT_PHASE,
        output,
        run_id="assembly",
        method=method,
        run_mode="assembly",
        frozen_current_records=state,
    )

    assert prepared is not None
    assert prepared["source"] == "template"
    assert prepared["reason"] == "no_current"
    assert b"Later live manuscript" not in (
        output / manuscript_records.MANUSCRIPT_FILENAME
    ).read_bytes()


def test_review_revision_requires_exact_frozen_current_manuscript(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    manifest, _ = _manifest(
        project,
        method,
        include_current_manuscript=False,
    )
    state = phase_records.frozen_phase5_state(project, manifest, method)

    with pytest.raises(
        manuscript_records.ManuscriptValidationError,
        match="review-revision requires a current manuscript frozen at launch",
    ):
        phase_records.prepare_output(
            project,
            phase_records.MANUSCRIPT_PHASE,
            project / "runs" / "review",
            run_id="review",
            method=method,
            run_mode="review-revision",
            frozen_current_records=state,
        )


def test_assembly_accepts_old_method_seed_but_review_revision_rejects_it(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    old_method = _method(version="v1", digest_label="old-method")
    _publish_current_manuscript(project, old_method)
    selected_method = _method()
    manifest, _ = _manifest(
        project,
        selected_method,
        include_current_manuscript=True,
    )
    state = phase_records.frozen_phase5_state(
        project, manifest, selected_method
    )

    prepared = phase_records.prepare_output(
        project,
        phase_records.MANUSCRIPT_PHASE,
        project / "runs" / "assembly",
        run_id="assembly",
        method=selected_method,
        run_mode="assembly",
        frozen_current_records=state,
    )
    assert prepared is not None
    assert prepared["source"] == "current"
    assert prepared["reason"] == "method_revision_pending"

    with pytest.raises(
        manuscript_records.ManuscriptValidationError,
        match="exact selected method",
    ):
        phase_records.prepare_output(
            project,
            phase_records.MANUSCRIPT_PHASE,
            project / "runs" / "review",
            run_id="review",
            method=selected_method,
            run_mode="review-revision",
            frozen_current_records=state,
        )


def test_frozen_file_tampering_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    manifest, _ = _manifest(
        project,
        method,
        include_current_manuscript=False,
    )
    p3_record = next(
        record
        for record in manifest["snapshots"]["current_records"]
        if record["key"] == phase5_projection.P3_KEY
    )
    p3_theory_record = next(
        file
        for file in p3_record["files"]
        if file["source_path"].endswith(f"/{theory_records.RECORD_FILENAME}")
    )
    Path(p3_theory_record["path"]).write_text(
        '{"record": "tampered"}\n',
        encoding="utf-8",
    )

    with pytest.raises(
        phase5_projection.Phase5ProjectionError,
        match="does not match the sealed launch inventory",
    ):
        phase5_projection.derive_frozen_phase5_state(
            project, manifest, method
        )


def test_seal_and_promotion_use_frozen_basis_after_live_inputs_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    manifest, _ = _manifest(
        project,
        method,
        include_current_manuscript=False,
    )
    state = phase_records.frozen_phase5_state(project, manifest, method)
    output = project / "runs" / "assembly"
    phase_records.prepare_output(
        project,
        phase_records.MANUSCRIPT_PHASE,
        output,
        run_id="assembly",
        method=method,
        run_mode="assembly",
        frozen_current_records=state,
    )
    (output / manuscript_records.MANUSCRIPT_FILENAME).write_text(
        "# New manuscript\n\nBuilt from the frozen launch basis.\n",
        encoding="utf-8",
    )

    def changed_live_basis(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("schema 13 Phase 5 consulted live upstream records")

    monkeypatch.setattr(
        phase_records,
        "current_upstream_basis",
        changed_live_basis,
    )
    seal = phase_records.seal_output(
        project,
        phase_records.MANUSCRIPT_PHASE,
        output,
        run_id="assembly",
        scientific_outcome="Complete",
        manifest=manifest,
    )
    published = phase_records.promote_output(
        project,
        phase_records.MANUSCRIPT_PHASE,
        output,
        seal,
        manifest=manifest,
    )

    assert published is not None
    assert published["upstream_basis"] == state["upstream_basis"]
    assert manuscript_records.load_current_manuscript(
        project, method["stable_id"]
    )["upstream_basis"] == state["upstream_basis"]


def test_schema_12_manifest_uses_only_its_frozen_upstream_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    manifest, payloads = _manifest(
        project,
        method,
        include_current_manuscript=False,
        run_id="schema-12-launch",
    )
    manifest["schema_version"] = 12
    for record in manifest["snapshots"]["current_records"]:
        record.pop("method_identity")

    def reject_live_read(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("schema 12 Phase 5 consulted live upstream records")

    monkeypatch.setattr(
        phase_records,
        "current_upstream_basis",
        reject_live_read,
    )

    basis = phase_records.manifest_upstream_basis(project, manifest)

    assert basis["p1_synthesis"]["sha256"] == hashlib.sha256(
        payloads["p1"]
    ).hexdigest()
    assert basis["p1_collection"]["sha256"] == json.loads(
        payloads["p1_index"]
    )["papers_sha256"]
    assert basis["p3_record"]["sha256"] == hashlib.sha256(
        payloads["p3"]
    ).hexdigest()
    assert basis["p4_synthesis"]["sha256"] == hashlib.sha256(
        payloads["p4_synthesis"]
    ).hexdigest()
    assert basis["p4_index"]["sha256"] == hashlib.sha256(
        payloads["p4_index"]
    ).hexdigest()


def test_pre_schema_12_manifest_cannot_attach_live_inputs(
    tmp_path: Path,
) -> None:
    method = _method()
    manifest = {
        "schema_version": 11,
        "method_selection": {
            "stable_id": method["stable_id"],
            "version": method["version"],
        },
        "snapshots": {
            "selected_method": {
                "sha256": method["definition_sha256"],
            },
        },
    }

    with pytest.raises(
        phase_records.PhaseRecordError,
        match="no exact frozen scientific basis",
    ):
        phase_records.manifest_upstream_basis(tmp_path, manifest)


def test_frozen_reference_index_rejects_duplicate_json_fields(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    manifest, _ = _manifest(
        project,
        method,
        include_current_manuscript=False,
    )
    p1_record = next(
        record
        for record in manifest["snapshots"]["current_records"]
        if record["key"] == phase5_projection.P1_KEY
    )
    index_file = next(
        file
        for file in p1_record["files"]
        if file["source_path"]
        == Path(literature_records.REFERENCE_INDEX).as_posix()
    )
    index_path = Path(index_file["path"])
    payload = index_path.read_bytes().replace(
        b"{",
        b'{"schema_version":2,',
        1,
    )
    index_path.write_bytes(payload)
    index_file["sha256"] = hashlib.sha256(payload).hexdigest()
    index_file["size"] = len(payload)

    with pytest.raises(
        phase5_projection.Phase5ProjectionError,
        match="duplicate field 'schema_version'",
    ):
        phase5_projection.derive_frozen_phase5_state(
            project,
            manifest,
            method,
        )


def test_frozen_manuscript_record_rejects_duplicate_json_fields(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _method()
    _publish_current_manuscript(project, method)
    manifest, _ = _manifest(
        project,
        method,
        include_current_manuscript=True,
    )
    p5_record = next(
        record
        for record in manifest["snapshots"]["current_records"]
        if record["key"] == phase5_projection.P5_KEY
    )
    record_file = next(
        file
        for file in p5_record["files"]
        if file["source_path"].endswith(
            f"/{manuscript_records.RECORD_FILENAME}"
        )
    )
    record_path = Path(record_file["path"])
    payload = record_path.read_bytes().replace(
        b"{",
        b'{"schema_version":2,',
        1,
    )
    record_path.write_bytes(payload)
    record_file["sha256"] = hashlib.sha256(payload).hexdigest()
    record_file["size"] = len(payload)

    with pytest.raises(
        phase5_projection.Phase5ProjectionError,
        match="duplicate field 'schema_version'",
    ):
        phase5_projection.derive_frozen_phase5_state(
            project,
            manifest,
            method,
        )
