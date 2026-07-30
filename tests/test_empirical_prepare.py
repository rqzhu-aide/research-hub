"""Tests for preparing Phase 04 cumulative state before agent work."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from core import empirical_records as records
from core import knowledge_basis


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _method(version: str, digest: str) -> dict[str, str]:
    return {
        "stable_id": "method-a",
        "version": version,
        "definition_sha256": digest,
    }


def _output(project: Path, number: int) -> Path:
    return project / "branches" / "method-a" / "draft" / "run" / f"{number:02d}"


def _read_index(output: Path) -> dict[str, Any]:
    return json.loads(
        (output / records.INDEX_FILENAME).read_text(encoding="utf-8")
    )


def _write_index(output: Path, index: dict[str, Any]) -> None:
    (output / records.INDEX_FILENAME).write_text(
        json.dumps(index, indent=2) + "\n",
        encoding="utf-8",
    )


def _complete_fragment(output: Path) -> None:
    index = _read_index(output)
    path = output / records.KNOWLEDGE_FILENAME
    fragment = json.loads(path.read_text(encoding="utf-8"))
    statement_id = (
        f"S-P04-{index['source_run_id']}-research_lead-001"
    )
    fragment["coverage"] = "complete"
    fragment["statements"] = [
        {
            "statement_id": statement_id,
            "statement_type": "Empirical statement",
            "wording": "The current synthesis reports the indexed results.",
            "scope": "The analyses represented in the evidence index.",
            "formulation_state": "Current",
            "assessment_status": "Supported",
            "evidential_basis": ["The indexed artifacts and synthesis."],
            "source_provenance": ["empirical-synthesis.md"],
            "assumptions": ["The recorded analyses completed as described."],
            "uncertainty": ["The synthesis states unresolved limitations."],
            "logical_status": "Not applicable",
            "mathematical_result_type": "Not applicable",
        }
    ]
    fragment["dependencies"] = []
    existing = {
        item["evidence_id"]: item
        for item in fragment["evidence_bindings"]
    }
    fragment["evidence_bindings"] = [
        {
            **existing.get(
                entry["evidence_id"],
                {
                    "evidence_id": entry["evidence_id"],
                    "role": "scientific_result",
                    "assessments": [],
                },
            ),
            "evidence_status": entry["status"],
        }
        for entry in index["entries"]
    ]
    fragment["lead_summary"] = {
        "fundamental_points": ["The empirical record has a current synthesis."],
        "decision_relevant_changes": [],
        "unresolved_questions": [],
    }
    path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _add_current_evidence(
    project: Path,
    output: Path,
    *,
    evidence_id: str,
    method_dependent: bool,
    evidence_type: str = "result",
) -> dict[str, Any]:
    artifact = output / "results" / f"{evidence_id}.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text('{"validated": true}\n', encoding="utf-8")
    return {
        "evidence_id": evidence_id,
        "type": evidence_type,
        "path": artifact.relative_to(project).as_posix(),
        "sha256": _digest(artifact),
        "size": artifact.stat().st_size,
        "source_run_id": "run-001",
        "run_scope": "preliminary",
        "status": "current",
        "status_reason": "Validated in the preliminary study.",
        "method_dependent": method_dependent,
    }


def test_prepare_first_run_creates_valid_empty_skeleton(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _output(project, 1)

    prepared = records.prepare_staged_package(
        project,
        output,
        _method("v1", "a" * 64),
        "run-001",
        "preliminary",
    )

    knowledge_path = output / records.KNOWLEDGE_FILENAME
    draft = json.loads(knowledge_path.read_text(encoding="utf-8"))
    assert prepared["generation"] == 1
    assert prepared["entries"] == []
    assert prepared["counterpart_basis"] == (
        knowledge_basis.unknown_legacy_basis(
            phase_slug=knowledge_basis.THEORY_PHASE,
        )
    )
    assert draft["coverage"] == "draft"
    assert draft["method"] == prepared["method"]
    assert draft["generation"] == 1
    assert draft["source_run_id"] == "run-001"
    assert draft["evidence_bindings"] == []
    assert records.validate_staged_package(
        project,
        output,
        require_complete_knowledge=False,
    ) == prepared
    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="coverage must be complete",
    ):
        records.validate_staged_package(project, output)
    synthesis = (output / records.SYNTHESIS_FILENAME).read_text(encoding="utf-8")
    assert "preliminary scope" in synthesis
    assert "Replace these instructions" in synthesis


def test_prepare_after_method_change_reconciles_prior_evidence(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first = _output(project, 1)
    records.prepare_staged_package(
        project,
        first,
        _method("v1", "a" * 64),
        "run-001",
        "preliminary",
    )
    index = _read_index(first)
    index["entries"] = [
        _add_current_evidence(
            project,
            first,
            evidence_id="method-result",
            method_dependent=True,
        ),
        _add_current_evidence(
            project,
            first,
            evidence_id="cohort-description",
            method_dependent=False,
            evidence_type="data",
        ),
    ]
    synthesis_path = first / records.SYNTHESIS_FILENAME
    synthesis_path.write_text(
        "# Empirical synthesis\n\nBoth evidence items are current.\n",
        encoding="utf-8",
    )
    index["synthesis"]["sha256"] = _digest(synthesis_path)
    index["synthesis"]["size"] = synthesis_path.stat().st_size
    _write_index(first, index)
    _complete_fragment(first)
    records.promote_staged_package(project, first)

    second = _output(project, 2)
    prepared = records.prepare_staged_package(
        project,
        second,
        _method("v2", "b" * 64),
        "run-002",
        "comprehensive",
    )

    by_id = {item["evidence_id"]: item for item in prepared["entries"]}
    assert prepared["generation"] == 2
    assert by_id["method-result"]["status"] == "outdated"
    assert by_id["cohort-description"]["status"] == "current"
    draft = json.loads(
        (second / records.KNOWLEDGE_FILENAME).read_text(encoding="utf-8")
    )
    binding_status = {
        item["evidence_id"]: item["evidence_status"]
        for item in draft["evidence_bindings"]
    }
    assert binding_status["method-result"] == "outdated"
    assert binding_status["cohort-description"] == "current"
    synthesis = (second / records.SYNTHESIS_FILENAME).read_text(encoding="utf-8")
    assert "comprehensive scope" in synthesis
    assert "method version changed" in synthesis.lower()
    assert "Both evidence items are current." in synthesis


def test_promote_can_reuse_a_lock_held_by_finalization(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _output(project, 1)
    records.prepare_staged_package(
        project,
        output,
        _method("v1", "a" * 64),
        "run-001",
        "preliminary",
    )
    _complete_fragment(output)

    def nested_lock_would_fail(*args, **kwargs):
        raise AssertionError("promotion tried to reacquire the project lock")

    monkeypatch.setattr(
        records.project_state,
        "_project_lock",
        nested_lock_would_fail,
    )
    promotion = records.promote_staged_package(
        project,
        output,
        lock_held=True,
    )

    assert promotion["generation"] == 1

def test_unfinished_prepared_draft_cannot_mutate_current(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _output(project, 1)
    records.prepare_staged_package(
        project,
        output,
        _method("v1", "a" * 64),
        "run-001",
        "preliminary",
    )

    with pytest.raises(
        records.EmpiricalRecordValidationError,
        match="coverage must be complete",
    ):
        records.promote_staged_package(project, output)
    assert records.load_current_package(project, "method-a") is None



def test_prepared_counterpart_basis_is_exact_and_tamper_checked(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    output = _output(project, 1)
    method = _method("v1", "a" * 64)
    basis = knowledge_basis.available_basis(
        phase_slug=knowledge_basis.THEORY_PHASE,
        method_identity=method,
        content_reference={"schema_version": 1, "sha256": "b" * 64},
        generation=3,
        source_run_id="p3-run-003",
    )

    prepared = records.prepare_staged_package(
        project,
        output,
        method,
        "run-001",
        "preliminary",
        counterpart_basis=basis,
    )
    assert prepared["counterpart_basis"] == basis
    assert records.validate_staged_package(
        project,
        output,
        require_complete_knowledge=False,
        counterpart_basis=basis,
    )["counterpart_basis"] == basis

    tampered = _read_index(output)
    tampered["counterpart_basis"] = knowledge_basis.absent_basis(
        phase_slug=knowledge_basis.THEORY_PHASE,
    )
    _write_index(output, tampered)
    with pytest.raises(
        records.EmpiricalRecordContinuityError,
        match="counterpart basis does not match",
    ):
        records.validate_staged_package(
            project,
            output,
            require_complete_knowledge=False,
            counterpart_basis=basis,
        )
