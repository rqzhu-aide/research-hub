"""Tests for cumulative per-method Phase 04 empirical records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from core import empirical_schema as schema
from core import empirical_records as records
from core import knowledge_basis


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry(
    project: Path,
    artifact: Path,
    *,
    evidence_id: str,
    source_run_id: str,
    method_dependent: bool = True,
    evidence_type: str = "result",
    status: str = "current",
    status_reason: str = "Validated in the recorded study.",
    run_scope: str = "preliminary",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "type": evidence_type,
        "path": artifact.relative_to(project).as_posix(),
        "sha256": _digest(artifact),
        "size": artifact.stat().st_size,
        "source_run_id": source_run_id,
        "run_scope": run_scope,
        "status": status,
        "status_reason": status_reason,
        "method_dependent": method_dependent,
    }


def _complete_fragment(index: dict[str, Any]) -> dict[str, Any]:
    statement_id = (
        f"S-P04-{index['source_run_id']}-research_lead-001"
    )
    return {
        "schema_version": 1,
        "kind": "empirical_knowledge_fragment",
        "semantics": "cumulative_evidence",
        "coverage": "complete",
        "method": index["method"],
        "generation": index["generation"],
        "source_run_id": index["source_run_id"],
        "statements": [
            {
                "statement_id": statement_id,
                "statement_type": "Empirical statement",
                "wording": (
                    "The current synthesis reports the indexed empirical results."
                ),
                "scope": "The simulations and data analyses in the index.",
                "formulation_state": "Current",
                "assessment_status": "Supported",
                "evidential_basis": [
                    "The indexed artifacts and empirical synthesis."
                ],
                "source_provenance": ["empirical-synthesis.md"],
                "assumptions": ["The recorded analyses completed as described."],
                "uncertainty": [
                    "Unresolved limitations remain stated in the synthesis."
                ],
                "logical_status": "Not applicable",
                "mathematical_result_type": "Not applicable",
            }
        ],
        "dependencies": [],
        "evidence_bindings": [
            {
                "evidence_id": entry["evidence_id"],
                "evidence_status": entry["status"],
                "role": "scientific_result",
                "assessments": [],
            }
            for entry in index["entries"]
        ],
        "lead_summary": {
            "fundamental_points": [
                "The current empirical record is summarized in the synthesis."
            ],
            "decision_relevant_changes": [],
            "unresolved_questions": [],
        },
    }


def _write_staged_package(
    output_root: Path,
    *,
    stable_id: str,
    version: str,
    definition_sha256: str,
    generation: int,
    source_run_id: str,
    entries: list[dict[str, Any]],
    synthesis: str,
    include_knowledge: bool = True,
    index_schema_version: int = records.INDEX_SCHEMA_VERSION,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    synthesis_path = output_root / records.SYNTHESIS_FILENAME
    synthesis_path.write_text(synthesis, encoding="utf-8")
    index = {
        "schema_version": index_schema_version,
        "kind": records.INDEX_KIND,
        "method": {
            "stable_id": stable_id,
            "version": version,
            "definition_sha256": definition_sha256,
        },
        "generation": generation,
        "source_run_id": source_run_id,
        "synthesis": {
            "path": records.SYNTHESIS_FILENAME,
            "sha256": _digest(synthesis_path),
            "size": synthesis_path.stat().st_size,
        },
        "entries": entries,
    }
    if index_schema_version >= records.COUNTERPART_INDEX_SCHEMA_VERSION:
        index["counterpart_basis"] = knowledge_basis.unknown_legacy_basis(
            phase_slug=knowledge_basis.THEORY_PHASE,
        )
    (output_root / records.INDEX_FILENAME).write_text(
        json.dumps(index, indent=2) + "\n",
        encoding="utf-8",
    )
    if include_knowledge:
        (output_root / records.KNOWLEDGE_FILENAME).write_text(
            json.dumps(_complete_fragment(index), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    return index


def _run_root(project: Path, stable_id: str, number: int) -> Path:
    return (
        project
        / "branches"
        / stable_id
        / "draft"
        / "run"
        / f"{number:02d}"
    )


def test_initial_package_is_promoted_to_the_method_current_directory(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _run_root(project, "method-a", 1)
    artifact = output / "results" / "primary.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"estimate": 1.5}\n', encoding="utf-8")
    entry = _entry(
        project,
        artifact,
        evidence_id="primary-simulation",
        source_run_id="run-001",
    )
    _write_staged_package(
        output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[entry],
        synthesis="# Empirical synthesis\n\nThe primary simulation completed.\n",
    )

    promotion = records.promote_staged_package(project, output)

    current = records.canonical_package_dir(project, "method-a")
    assert promotion["generation"] == 1
    assert promotion["previous_generation"] is None
    assert (current / records.SYNTHESIS_FILENAME).read_bytes() == (
        output / records.SYNTHESIS_FILENAME
    ).read_bytes()
    assert (current / records.KNOWLEDGE_FILENAME).read_bytes() == (
        output / records.KNOWLEDGE_FILENAME
    ).read_bytes()
    loaded = records.load_current_package(project, "method-a")
    assert loaded is not None
    loaded_entry = loaded["entries"][0]
    assert {
        key: loaded_entry[key] for key in entry
    } == entry
    assert loaded_entry["evidence_class"] == "scientific_result"
    assert loaded_entry["applicability_scope"] == "exact_method"
    assert loaded_entry["applicability_state"] == "active_current_method"


def test_later_package_retains_prior_evidence_and_appends_new_evidence(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first_output = _run_root(project, "method-a", 1)
    first_artifact = first_output / "results" / "pilot.json"
    first_artifact.parent.mkdir(parents=True)
    first_artifact.write_text('{"pilot": true}\n', encoding="utf-8")
    first_entry = _entry(
        project,
        first_artifact,
        evidence_id="pilot",
        source_run_id="run-001",
    )
    _write_staged_package(
        first_output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[first_entry],
        synthesis="# Synthesis\n\nPilot evidence is current.\n",
    )
    records.promote_staged_package(project, first_output)

    second_output = _run_root(project, "method-a", 2)
    second_artifact = second_output / "results" / "benchmark.json"
    second_artifact.parent.mkdir(parents=True)
    second_artifact.write_text('{"benchmark": true}\n', encoding="utf-8")
    second_entry = _entry(
        project,
        second_artifact,
        evidence_id="benchmark",
        source_run_id="run-002",
        run_scope="comprehensive",
    )
    _write_staged_package(
        second_output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=2,
        source_run_id="run-002",
        entries=[first_entry, second_entry],
        synthesis="# Synthesis\n\nPilot and benchmark evidence are current.\n",
    )

    records.promote_staged_package(project, second_output)

    loaded = records.load_current_package(project, "method-a")
    assert loaded is not None
    assert loaded["generation"] == 2
    assert [item["evidence_id"] for item in loaded["entries"]] == [
        "pilot",
        "benchmark",
    ]


def test_later_package_cannot_omit_prior_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first_output = _run_root(project, "method-a", 1)
    artifact = first_output / "results" / "pilot.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"pilot": true}\n', encoding="utf-8")
    entry = _entry(
        project,
        artifact,
        evidence_id="pilot",
        source_run_id="run-001",
    )
    _write_staged_package(
        first_output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[entry],
        synthesis="# Synthesis\n\nPilot evidence is current.\n",
    )
    records.promote_staged_package(project, first_output)
    current = records.canonical_package_dir(project, "method-a")
    old_index = (current / records.INDEX_FILENAME).read_bytes()

    second_output = _run_root(project, "method-a", 2)
    _write_staged_package(
        second_output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=2,
        source_run_id="run-002",
        entries=[],
        synthesis="# Synthesis\n\nNo retained evidence.\n",
    )

    with pytest.raises(
        records.EmpiricalRecordContinuityError,
        match="omits prior evidence IDs: pilot",
    ):
        records.promote_staged_package(project, second_output)

    assert (current / records.INDEX_FILENAME).read_bytes() == old_index


def test_revalidation_appends_new_evidence_instead_of_reactivating_old_id(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first_output = _run_root(project, "method-a", 1)
    old_artifact = first_output / "results" / "method-result-v1.json"
    old_artifact.parent.mkdir(parents=True)
    old_artifact.write_text('{"estimate": 1.0}\n', encoding="utf-8")
    old_entry = _entry(
        project,
        old_artifact,
        evidence_id="method-result-v1",
        source_run_id="run-001",
        status="outdated",
        status_reason="The method definition changed before this result was used.",
    )
    _write_staged_package(
        first_output,
        stable_id="method-a",
        version="v2",
        definition_sha256="b" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[old_entry],
        synthesis="# Synthesis\n\nThe earlier result is outdated.\n",
    )
    records.promote_staged_package(project, first_output)

    second_output = _run_root(project, "method-a", 2)
    reactivated = {
        **old_entry,
        "status": "current",
        "status_reason": "Reactivated without a new artifact.",
    }
    _write_staged_package(
        second_output,
        stable_id="method-a",
        version="v2",
        definition_sha256="b" * 64,
        generation=2,
        source_run_id="run-002",
        entries=[reactivated],
        synthesis="# Synthesis\n\nAttempted reactivation.\n",
    )

    with pytest.raises(
        records.EmpiricalRecordContinuityError,
        match="cannot return to current status",
    ):
        records.promote_staged_package(project, second_output)

    replacement_artifact = second_output / "results" / "method-result-v2.json"
    replacement_artifact.parent.mkdir(parents=True, exist_ok=True)
    replacement_artifact.write_text('{"estimate": 1.1}\n', encoding="utf-8")
    replacement = _entry(
        project,
        replacement_artifact,
        evidence_id="method-result-v2",
        source_run_id="run-002",
        status="current",
        status_reason="Revalidated under method version v2.",
    )
    superseded = {
        **old_entry,
        "status": "superseded",
        "status_reason": "Replaced by method-result-v2 in run-002.",
    }
    _write_staged_package(
        second_output,
        stable_id="method-a",
        version="v2",
        definition_sha256="b" * 64,
        generation=2,
        source_run_id="run-002",
        entries=[superseded, replacement],
        synthesis="# Synthesis\n\nThe method result was revalidated.\n",
    )

    records.promote_staged_package(project, second_output)

    current = records.load_current_package(project, "method-a")
    assert current is not None
    by_id = {entry["evidence_id"]: entry for entry in current["entries"]}
    assert by_id["method-result-v1"]["status"] == "superseded"
    assert by_id["method-result-v2"]["status"] == "current"
    assert by_id["method-result-v2"]["source_run_id"] == "run-002"


def test_method_change_invalidates_exact_method_evidence_but_keeps_raw_data(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first_output = _run_root(project, "method-a", 1)
    dependent_artifact = first_output / "results" / "method-result.json"
    independent_artifact = first_output / "data" / "cohort-summary.csv"
    dependent_artifact.parent.mkdir(parents=True)
    independent_artifact.parent.mkdir(parents=True)
    dependent_artifact.write_text('{"risk": 0.3}\n', encoding="utf-8")
    independent_artifact.write_text("group,n\nA,20\n", encoding="utf-8")
    dependent = _entry(
        project,
        dependent_artifact,
        evidence_id="method-result",
        source_run_id="run-001",
        method_dependent=True,
    )
    independent = _entry(
        project,
        independent_artifact,
        evidence_id="cohort-summary",
        source_run_id="run-001",
        method_dependent=False,
        evidence_type="data",
    )
    _write_staged_package(
        first_output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[dependent, independent],
        synthesis="# Synthesis\n\nTwo evidence items are current.\n",
    )
    records.promote_staged_package(project, first_output)
    previous = records.load_current_package(project, "method-a")
    assert previous is not None

    second_output = _run_root(project, "method-a", 2)
    second_output.mkdir(parents=True)
    summary = second_output / records.SYNTHESIS_FILENAME
    summary.write_text(
        "# Synthesis\n\nThe method result awaits revalidation.\n",
        encoding="utf-8",
    )
    reconciled = records.reconcile_method_change(
        previous,
        method_version="v2",
        method_definition_sha256="b" * 64,
        source_run_id="run-002",
        synthesis_sha256=_digest(summary),
        synthesis_size=summary.stat().st_size,
    )
    (second_output / records.INDEX_FILENAME).write_text(
        json.dumps(reconciled, indent=2) + "\n",
        encoding="utf-8",
    )
    (second_output / records.KNOWLEDGE_FILENAME).write_text(
        json.dumps(_complete_fragment(reconciled), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    records.promote_staged_package(project, second_output)

    loaded = records.load_current_package(project, "method-a")
    assert loaded is not None
    by_id = {item["evidence_id"]: item for item in loaded["entries"]}
    assert by_id["method-result"]["status"] == "outdated"
    assert "previous method version" in by_id["method-result"]["status_reason"]
    assert by_id["cohort-summary"]["status"] == "current"


@pytest.mark.parametrize("evidence_type", sorted(records.VERSION_BOUND_TYPES))
def test_schema_three_rejects_false_method_dependency_for_version_bound_evidence(
    tmp_path: Path,
    evidence_type: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _run_root(project, "method-a", 1)
    artifact = output / "artifacts" / f"{evidence_type}.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"current evidence\n")
    entry = _entry(
        project,
        artifact,
        evidence_id=f"current-{evidence_type}",
        source_run_id="run-001",
        evidence_type=evidence_type,
        method_dependent=False,
    )
    _write_staged_package(
        output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[entry],
        synthesis="# Synthesis\n\nThe evidence was produced.\n",
    )

    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="must be bound to the exact method version",
    ):
        records.validate_staged_package(project, output)


def test_schema_three_allows_reusable_data_and_infrastructure(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _run_root(project, "method-a", 1)
    expected_classes = {
        "data": "input",
        "log": "infrastructure",
        "protocol": "infrastructure",
        "other": "infrastructure",
    }
    entries = []
    for evidence_type in expected_classes:
        artifact = output / "artifacts" / f"{evidence_type}.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(f"{evidence_type}\n", encoding="utf-8")
        entries.append(_entry(
            project,
            artifact,
            evidence_id=f"reusable-{evidence_type}",
            source_run_id="run-001",
            evidence_type=evidence_type,
            method_dependent=False,
        ))
    _write_staged_package(
        output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=entries,
        synthesis="# Synthesis\n\nReusable inputs and records are indexed.\n",
    )

    normalized = records.validate_staged_package(project, output)

    by_type = {entry["type"]: entry for entry in normalized["entries"]}
    for evidence_type, evidence_class in expected_classes.items():
        entry = by_type[evidence_type]
        assert entry["method_dependent"] is False
        assert entry["evidence_class"] == evidence_class
        assert entry["applicability_scope"] == "reusable"
        assert entry["applicability_state"] == "active_reusable"


def test_legacy_false_result_and_code_are_normalized_and_invalidated(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    current = records.canonical_package_dir(project, "method-a")
    entries = []
    for evidence_type in ("result", "code"):
        artifact = current / "legacy" / f"{evidence_type}.txt"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(f"legacy {evidence_type}\n", encoding="utf-8")
        entries.append(_entry(
            project,
            artifact,
            evidence_id=f"legacy-{evidence_type}",
            source_run_id="legacy-run",
            evidence_type=evidence_type,
            method_dependent=False,
        ))
    _write_staged_package(
        current,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="legacy-run",
        entries=entries,
        synthesis="# Synthesis\n\nLegacy evidence.\n",
        include_knowledge=False,
        index_schema_version=schema.LEGACY_INDEX_SCHEMA_VERSION,
    )

    loaded = records.load_current_package(project, "method-a")
    assert loaded is not None
    for entry in loaded["entries"]:
        assert entry["method_dependent"] is True
        assert entry["applicability_scope"] == "exact_method"
        assert entry["applicability_state"] == "active_current_method"

    reconciled = records.reconcile_method_change(
        loaded,
        method_version="v2",
        method_definition_sha256="b" * 64,
        source_run_id="run-002",
        synthesis_sha256="c" * 64,
        synthesis_size=100,
    )

    assert reconciled["schema_version"] == records.INDEX_SCHEMA_VERSION
    for entry in reconciled["entries"]:
        assert entry["method_dependent"] is True
        assert entry["status"] == "outdated"
        assert "previous method version" in entry["status_reason"]


def test_tampered_current_artifact_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _run_root(project, "method-a", 1)
    artifact = output / "results" / "primary.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"estimate": 1.5}\n', encoding="utf-8")
    entry = _entry(
        project,
        artifact,
        evidence_id="primary",
        source_run_id="run-001",
    )
    _write_staged_package(
        output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[entry],
        synthesis="# Synthesis\n\nThe primary estimate is recorded.\n",
    )
    artifact.write_text('{"estimate": 9.9}\n', encoding="utf-8")

    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="does not match its recorded size and SHA-256",
    ):
        records.promote_staged_package(project, output)

    assert records.load_current_package(project, "method-a") is None


def test_promotion_failure_restores_exact_prior_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first_output = _run_root(project, "method-a", 1)
    first_artifact = first_output / "results" / "pilot.json"
    first_artifact.parent.mkdir(parents=True)
    first_artifact.write_text('{"pilot": true}\n', encoding="utf-8")
    first_entry = _entry(
        project,
        first_artifact,
        evidence_id="pilot",
        source_run_id="run-001",
    )
    _write_staged_package(
        first_output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[first_entry],
        synthesis="# Synthesis\n\nPilot evidence is current.\n",
    )
    records.promote_staged_package(project, first_output)
    current = records.canonical_package_dir(project, "method-a")
    prior_synthesis = (current / records.SYNTHESIS_FILENAME).read_bytes()
    prior_index = (current / records.INDEX_FILENAME).read_bytes()
    prior_knowledge = (current / records.KNOWLEDGE_FILENAME).read_bytes()

    second_output = _run_root(project, "method-a", 2)
    second_artifact = second_output / "results" / "benchmark.json"
    second_artifact.parent.mkdir(parents=True)
    second_artifact.write_text('{"benchmark": true}\n', encoding="utf-8")
    second_entry = _entry(
        project,
        second_artifact,
        evidence_id="benchmark",
        source_run_id="run-002",
    )
    _write_staged_package(
        second_output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=2,
        source_run_id="run-002",
        entries=[first_entry, second_entry],
        synthesis="# Synthesis\n\nA replacement synthesis.\n",
    )

    original_replace = records.os.replace

    def fail_package_install(source: object, destination: object) -> None:
        if (
            Path(source).name.startswith(".empirical-package-prepared-")
            and Path(destination) == current
        ):
            raise OSError("simulated package installation failure")
        original_replace(source, destination)

    monkeypatch.setattr(records.os, "replace", fail_package_install)

    with pytest.raises(
        records.EmpiricalRecordPromotionError,
        match="prior package was restored",
    ):
        records.promote_staged_package(project, second_output)

    assert (current / records.SYNTHESIS_FILENAME).read_bytes() == prior_synthesis
    assert (current / records.INDEX_FILENAME).read_bytes() == prior_index
    assert (current / records.KNOWLEDGE_FILENAME).read_bytes() == prior_knowledge
    loaded = records.load_current_package(project, "method-a")
    assert loaded is not None
    assert loaded["generation"] == 1


def test_new_evidence_must_be_stored_in_its_exact_run_directory(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _run_root(project, "method-a", 1)
    external_artifact = project / "shared" / "mutable-result.json"
    external_artifact.parent.mkdir(parents=True)
    external_artifact.write_text('{"estimate": 1.5}\n', encoding="utf-8")
    entry = _entry(
        project,
        external_artifact,
        evidence_id="external-result",
        source_run_id="run-001",
    )
    _write_staged_package(
        output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[entry],
        synthesis="# Synthesis\n\nAttempted external evidence.\n",
    )

    with pytest.raises(
        records.EmpiricalRecordContinuityError,
        match="must be stored under the current Phase 4 run directory",
    ):
        records.promote_staged_package(project, output)

    assert records.load_current_package(project, "method-a") is None

def test_promotion_requires_a_complete_knowledge_fragment(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _run_root(project, "method-a", 1)
    _write_staged_package(
        output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[],
        synthesis="# Synthesis\n\nNo complete fragment was produced.\n",
        include_knowledge=False,
    )

    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="knowledge-fragment.json is required",
    ):
        records.promote_staged_package(project, output)
    assert records.load_current_package(project, "method-a") is None


def test_complete_fragment_must_bind_every_indexed_evidence_item(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _run_root(project, "method-a", 1)
    artifact = output / "results" / "primary.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"estimate": 1.5}\n', encoding="utf-8")
    entry = _entry(
        project,
        artifact,
        evidence_id="primary",
        source_run_id="run-001",
    )
    _write_staged_package(
        output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[entry],
        synthesis="# Synthesis\n\nThe primary estimate is recorded.\n",
    )
    fragment_path = output / records.KNOWLEDGE_FILENAME
    fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
    fragment["evidence_bindings"] = []
    fragment_path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="omits evidence IDs: primary",
    ):
        records.promote_staged_package(project, output)
    assert records.load_current_package(project, "method-a") is None


def test_legacy_two_file_current_package_remains_readable(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    current = records.canonical_package_dir(project, "method-a")
    index = _write_staged_package(
        current,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=3,
        source_run_id="legacy-run",
        entries=[],
        synthesis="# Synthesis\n\nLegacy empirical summary.\n",
        include_knowledge=False,
        index_schema_version=1,
    )

    loaded = records.load_current_package(project, "method-a")

    assert loaded == index
    assert not (current / records.KNOWLEDGE_FILENAME).exists()


def test_new_retained_transaction_binds_the_knowledge_fragment(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _run_root(project, "method-a", 1)
    _write_staged_package(
        output,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="run-001",
        entries=[],
        synthesis="# Synthesis\n\nCurrent empirical summary.\n",
    )
    promotion = records.promote_staged_package(
        project,
        output,
        retain_backup=True,
    )
    transaction = promotion["_promotion_transaction"]

    assert (
        transaction["schema_version"]
        == records.PROMOTION_TRANSACTION_SCHEMA_VERSION
    )
    published = transaction["published_snapshot"]
    assert published["knowledge_sha256"]
    assert published["knowledge_size"] > 0
    assert promotion["knowledge_sha256"] == published["knowledge_sha256"]
    assert promotion["knowledge_size"] == published["knowledge_size"]

    records.rollback_empirical_package_promotion(project, promotion)
    assert records.load_current_package(project, "method-a") is None


def test_schema_one_first_promotion_journal_remains_recoverable(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    current = records.canonical_package_dir(project, "method-a")
    index = _write_staged_package(
        current,
        stable_id="method-a",
        version="v1",
        definition_sha256="a" * 64,
        generation=1,
        source_run_id="legacy-run",
        entries=[],
        synthesis="# Synthesis\n\nLegacy empirical summary.\n",
        include_knowledge=False,
        index_schema_version=1,
    )
    synthesis_bytes = (current / records.SYNTHESIS_FILENAME).read_bytes()
    index_bytes = (current / records.INDEX_FILENAME).read_bytes()
    published_snapshot = {
        "method": index["method"],
        "generation": index["generation"],
        "source_run_id": index["source_run_id"],
        "synthesis_sha256": hashlib.sha256(synthesis_bytes).hexdigest(),
        "synthesis_size": len(synthesis_bytes),
        "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "index_size": len(index_bytes),
    }
    promotion = {
        "schema_version": 1,
        "kind": "empirical_package_promotion",
        "method": index["method"],
        "generation": index["generation"],
        "source_run_id": index["source_run_id"],
        "current_directory": current.relative_to(project).as_posix(),
        "previous_generation": None,
        "_promotion_transaction": {
            "schema_version": 1,
            "kind": "empirical_promotion_transaction",
            "project_root": str(project.resolve()),
            "published_path": current.relative_to(project).as_posix(),
            "backup_path": None,
            "previous_snapshot": None,
            "published_snapshot": published_snapshot,
        },
    }

    records.rollback_empirical_package_promotion(project, promotion)

    assert records.load_current_package(project, "method-a") is None
