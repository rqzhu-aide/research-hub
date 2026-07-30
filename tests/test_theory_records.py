"""Behavioral tests for compact Phase 3 replacement packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from core import knowledge_basis
from core import knowledge_fragments as fragments
from core import theory_records as theory


def _identity(stable_id: str = "method-a", version: str = "v1") -> dict[str, str]:
    return {
        "stable_id": stable_id,
        "version": version,
        "definition_sha256": hashlib.sha256(
            f"{stable_id}:{version}".encode()
        ).hexdigest(),
    }


def _p4_basis(identity: dict[str, str]) -> dict[str, object]:
    return knowledge_basis.available_basis(
        phase_slug=knowledge_basis.EMPIRICAL_PHASE,
        method_identity=identity,
        content_reference={"schema_version": 1, "sha256": "e" * 64},
        generation=4,
        source_run_id="p4-run-004",
    )


def _complete_fragment(
    identity: dict[str, str],
    run_id: str,
    generation: int,
) -> dict[str, object]:
    statement_id = f"S-P03-{run_id}-research_lead-001"
    return {
        "schema_version": fragments.SCHEMA_VERSION,
        "kind": fragments.THEORY_KIND,
        "semantics": fragments.THEORY_SEMANTICS,
        "coverage": "complete",
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "statements": [
            {
                "statement_id": statement_id,
                "statement_type": "Mathematical statement",
                "wording": (
                    "The stated estimator is consistent under the listed "
                    "assumptions."
                ),
                "scope": (
                    "The asymptotic regime specified in the theory manuscript."
                ),
                "formulation_state": "Current",
                "assessment_status": "Supported",
                "evidential_basis": [
                    "The complete proof in the theory manuscript."
                ],
                "source_provenance": [
                    "theory-manuscript.md, main result"
                ],
                "assumptions": [
                    "The regularity conditions stated in the manuscript."
                ],
                "uncertainty": [
                    "Finite-sample behavior remains to be established."
                ],
                "logical_status": "proved",
                "mathematical_result_type": (
                    "asymptotic limit, rate, or distribution"
                ),
            }
        ],
        "dependencies": [],
        "lead_summary": {
            "fundamental_points": [
                "The main consistency result has a complete proof."
            ],
            "decision_relevant_changes": [
                "The current package replaces the prior proof."
            ],
            "unresolved_questions": [
                "Finite-sample behavior remains open."
            ],
        },
    }


def _write_complete_fragment(
    project: Path,
    output: Path,
    identity: dict[str, str],
    run_id: str,
) -> None:
    current = theory.load_current_theory(project, identity["stable_id"])
    generation = (
        1
        if current is None
        else int(current["generation"])
        if current["source_run_id"] == run_id
        else int(current["generation"]) + 1
    )
    (output / theory.KNOWLEDGE_FILENAME).write_text(
        json.dumps(
            _complete_fragment(identity, run_id, generation),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _stage(
    project: Path,
    run_name: str,
    content: str,
    *,
    identity: dict[str, str],
    outcome: str = "Complete",
    self_contained: bool = False,
    counterpart_basis: dict[str, object] | None = None,
) -> tuple[Path, dict[str, object]]:
    output = project / "runs" / run_name
    output.mkdir(parents=True)
    (output / theory.THEORY_FILENAME).write_text(content, encoding="utf-8")
    _write_complete_fragment(project, output, identity, run_name)
    seal = theory.seal_staged_theory(
        project,
        output,
        method_identity=identity,
        source_run_id=run_name,
        scientific_outcome=outcome,
        structurally_self_contained=self_contained,
        counterpart_basis=counterpart_basis,
    )
    return output, seal


def test_initial_and_update_promotion_replace_the_complete_package(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()

    first_output, first_seal = _stage(
        project, "run-1", "# Theory\n\nFirst complete proof.", identity=identity
    )
    first = theory.promote_staged_theory(
        project,
        first_output,
        first_seal,
        expected_method_identity=identity,
    )
    assert first["generation"] == 1
    assert first["source_run_id"] == "run-1"
    assert first["counterpart_basis"] == knowledge_basis.unknown_legacy_basis(
        phase_slug=knowledge_basis.EMPIRICAL_PHASE,
    )

    explicit_basis = _p4_basis(identity)
    second_output, second_seal = _stage(
        project,
        "run-2",
        "# Theory\n\nRepaired complete proof.",
        identity=identity,
        counterpart_basis=explicit_basis,
    )
    second = theory.promote_staged_theory(
        project,
        second_output,
        second_seal,
        expected_method_identity=identity,
    )
    assert second["generation"] == 2
    assert second["source_run_id"] == "run-2"
    assert second["counterpart_basis"] == explicit_basis
    current_dir = theory.current_theory_directory(project, "method-a")
    assert (current_dir / theory.THEORY_FILENAME).read_text(
        encoding="utf-8"
    ).endswith("Repaired complete proof.")
    assert second["schema_version"] == theory.SCHEMA_VERSION
    assert second["knowledge_file"] == theory.KNOWLEDGE_FILENAME
    fragment = json.loads(
        (current_dir / theory.KNOWLEDGE_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    assert fragment["coverage"] == "complete"
    assert fragment["generation"] == 2
    assert fragment["source_run_id"] == "run-2"
    assert theory.load_current_theory(project, "method-a") == second


def test_partial_requires_a_self_contained_replacement(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = project / "runs" / "partial"
    output.mkdir(parents=True)
    (output / theory.THEORY_FILENAME).write_text(
        "# Theory\n\nComplete statements with one unresolved conjecture.",
        encoding="utf-8",
    )
    _write_complete_fragment(project, output, identity, "partial")

    with pytest.raises(theory.TheoryValidationError, match="self-contained"):
        theory.seal_staged_theory(
            project,
            output,
            method_identity=identity,
            source_run_id="partial",
            scientific_outcome="Partial",
        )

    seal = theory.seal_staged_theory(
        project,
        output,
        method_identity=identity,
        source_run_id="partial",
        scientific_outcome="Partial",
        structurally_self_contained=True,
    )
    record = theory.promote_staged_theory(
        project, output, seal, expected_method_identity=identity
    )
    assert record["scientific_outcome"] == "Partial"
    assert record["structurally_self_contained"] is True


def test_seal_requires_a_complete_knowledge_fragment(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = project / "runs" / "run-1"
    output.mkdir(parents=True)
    (output / theory.THEORY_FILENAME).write_text(
        "# Theory\n\nComplete proof.",
        encoding="utf-8",
    )

    with pytest.raises(
        theory.TheoryValidationError,
        match="knowledge fragment",
    ):
        theory.seal_staged_theory(
            project,
            output,
            method_identity=identity,
            source_run_id="run-1",
            scientific_outcome="Complete",
        )

    theory.prepare_staged_theory(
        project,
        output,
        identity,
        source_run_id="run-1",
    )
    with pytest.raises(
        theory.TheoryValidationError,
        match="coverage must be complete",
    ):
        theory.seal_staged_theory(
            project,
            output,
            method_identity=identity,
            source_run_id="run-1",
            scientific_outcome="Complete",
        )


def test_fragment_change_after_sealing_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-1",
        "# Theory\n\nComplete proof.",
        identity=identity,
    )
    fragment_path = output / theory.KNOWLEDGE_FILENAME
    fragment_path.write_bytes(fragment_path.read_bytes() + b"\n")

    with pytest.raises(
        theory.TheoryStageChanged,
        match="knowledge fragment changed",
    ):
        theory.promote_staged_theory(
            project,
            output,
            seal,
            expected_method_identity=identity,
        )
    assert theory.load_current_theory(project, "method-a") is None


def test_failed_or_changed_rerun_leaves_prior_package_current(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    prior_output, prior_seal = _stage(
        project, "run-good", "# Theory\n\nVerified result.", identity=identity
    )
    prior = theory.promote_staged_theory(
        project, prior_output, prior_seal, expected_method_identity=identity
    )

    failed_output = project / "runs" / "run-failed"
    failed_output.mkdir(parents=True)
    (failed_output / theory.THEORY_FILENAME).write_text(
        "# Theory\n\nBroken attempt.", encoding="utf-8"
    )
    with pytest.raises(theory.TheoryValidationError, match="Complete"):
        theory.seal_staged_theory(
            project,
            failed_output,
            method_identity=identity,
            source_run_id="run-failed",
            scientific_outcome="Failed",
        )
    assert theory.load_current_theory(project, "method-a") == prior

    changed_output, changed_seal = _stage(
        project, "run-changed", "# Theory\n\nCandidate repair.", identity=identity
    )
    (changed_output / theory.THEORY_FILENAME).write_text(
        "# Theory\n\nChanged after sealing.", encoding="utf-8"
    )
    with pytest.raises(theory.TheoryStageChanged):
        theory.promote_staged_theory(
            project,
            changed_output,
            changed_seal,
            expected_method_identity=identity,
        )
    assert theory.load_current_theory(project, "method-a") == prior


def test_method_mismatch_is_rejected_before_replacement(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    original = _identity(version="v1")
    prior_output, prior_seal = _stage(
        project, "run-1", "# Theory\n\nVersion one.", identity=original
    )
    prior = theory.promote_staged_theory(
        project, prior_output, prior_seal, expected_method_identity=original
    )

    output, seal = _stage(
        project, "run-2", "# Theory\n\nUnfrozen method.", identity=original
    )
    revised = _identity(version="v2")
    with pytest.raises(theory.TheoryStageChanged, match="method identity"):
        theory.promote_staged_theory(
            project, output, seal, expected_method_identity=revised
        )
    assert theory.load_current_theory(project, "method-a") == prior


def test_method_branches_are_independent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity_a = _identity("method-a")
    identity_b = _identity("method-b")
    output_a, seal_a = _stage(
        project, "run-a1", "# Theory A\n\nA1.", identity=identity_a
    )
    output_b, seal_b = _stage(
        project, "run-b1", "# Theory B\n\nB1.", identity=identity_b
    )
    theory.promote_staged_theory(
        project, output_a, seal_a, expected_method_identity=identity_a
    )
    record_b = theory.promote_staged_theory(
        project, output_b, seal_b, expected_method_identity=identity_b
    )

    output_a2, seal_a2 = _stage(
        project, "run-a2", "# Theory A\n\nA2.", identity=identity_a
    )
    theory.promote_staged_theory(
        project, output_a2, seal_a2, expected_method_identity=identity_a
    )
    assert theory.load_current_theory(project, "method-a")["generation"] == 2
    assert theory.load_current_theory(project, "method-b") == record_b


def test_swap_failure_restores_the_previous_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    first_output, first_seal = _stage(
        project, "run-1", "# Theory\n\nStable.", identity=identity
    )
    prior = theory.promote_staged_theory(
        project, first_output, first_seal, expected_method_identity=identity
    )
    current_dir = theory.current_theory_directory(project, "method-a")
    prior_fragment = (current_dir / theory.KNOWLEDGE_FILENAME).read_bytes()
    second_output, second_seal = _stage(
        project, "run-2", "# Theory\n\nReplacement.", identity=identity
    )

    real_replace = theory.os.replace

    def fail_install(source: object, destination: object) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            source_path.name.startswith(".current-prepared-")
            and destination_path.name == "current"
        ):
            raise OSError("injected install failure")
        real_replace(source, destination)

    monkeypatch.setattr(theory.os, "replace", fail_install)
    with pytest.raises(OSError, match="injected"):
        theory.promote_staged_theory(
            project,
            second_output,
            second_seal,
            expected_method_identity=identity,
        )
    assert theory.load_current_theory(project, "method-a") == prior
    assert (
        current_dir / theory.KNOWLEDGE_FILENAME
    ).read_bytes() == prior_fragment


def test_prepare_theory_uses_template_without_an_exact_current_package(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = project / "runs" / "new-run"

    prepared = theory.prepare_staged_theory(project, output, identity)
    payload = (output / theory.THEORY_FILENAME).read_bytes()
    knowledge_path = output / theory.KNOWLEDGE_FILENAME
    draft = json.loads(knowledge_path.read_text(encoding="utf-8"))
    assert prepared["source"] == "template"
    assert prepared["reason"] == "no_current"
    assert prepared["source_generation"] is None
    assert prepared["target_generation"] == 1
    assert prepared["knowledge_path"] == knowledge_path
    assert prepared["sha256"] == hashlib.sha256(payload).hexdigest()
    assert draft["coverage"] == "draft"
    assert draft["generation"] == 1
    assert draft["source_run_id"] == "new-run"
    assert draft["statements"] == []
    assert b"complete replacement manuscript" in payload
    assert identity["definition_sha256"].encode() in payload


def test_prepare_theory_copies_only_an_exact_current_package(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    current_content = "# Theory\n\nExact current proof package."
    current_output, seal = _stage(
        project, "run-current", current_content, identity=identity
    )
    _promoted = theory.promote_staged_theory(
        project, current_output, seal, expected_method_identity=identity
    )
    canonical_bytes = (
        theory.current_theory_directory(project, "method-a")
        / theory.THEORY_FILENAME
    ).read_bytes()

    exact_output = project / "runs" / "run-exact"
    exact = theory.prepare_staged_theory(project, exact_output, identity)
    exact_fragment = json.loads(
        (exact_output / theory.KNOWLEDGE_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    assert exact["source"] == "current"
    assert exact["reason"] == "exact_method_match"
    assert exact["source_generation"] == 1
    assert exact_fragment["coverage"] == "draft"
    assert exact_fragment["generation"] == 2
    assert exact_fragment["source_run_id"] == "run-exact"
    assert exact_fragment["statements"]
    assert (exact_output / theory.THEORY_FILENAME).read_bytes() == canonical_bytes

    revised = _identity(version="v2")
    revised_output = project / "runs" / "run-revised"
    changed = theory.prepare_staged_theory(project, revised_output, revised)
    revised_bytes = (revised_output / theory.THEORY_FILENAME).read_bytes()
    revised_fragment = json.loads(
        (revised_output / theory.KNOWLEDGE_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    assert changed["source"] == "template"
    assert changed["reason"] == "method_revised"
    assert revised_fragment["generation"] == 2
    assert revised_fragment["method"] == revised
    assert revised_fragment["statements"] == []
    assert revised_bytes != canonical_bytes
    assert revised["definition_sha256"].encode() in revised_bytes


def test_schema_one_current_package_remains_readable(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    current = theory.current_theory_directory(project, "method-a")
    current.mkdir(parents=True)
    manuscript = b"# Theory\n\nLegacy complete proof.\n"
    (current / theory.THEORY_FILENAME).write_bytes(manuscript)
    record = {
        "schema_version": theory.LEGACY_SCHEMA_VERSION,
        "method_identity": identity,
        "source_run_id": "legacy-run",
        "scientific_outcome": "Complete",
        "structurally_self_contained": False,
        "generation": 4,
        "manuscript_file": theory.THEORY_FILENAME,
        "manuscript_sha256": hashlib.sha256(manuscript).hexdigest(),
        "manuscript_size": len(manuscript),
    }
    (current / theory.RECORD_FILENAME).write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    loaded = theory.load_current_theory(project, "method-a")

    assert loaded == record
    assert "knowledge_file" not in loaded


def test_schema_two_current_package_requires_untampered_fragment(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output, seal = _stage(
        project,
        "run-1",
        "# Theory\n\nComplete proof.",
        identity=identity,
    )
    theory.promote_staged_theory(
        project,
        output,
        seal,
        expected_method_identity=identity,
    )
    current = theory.current_theory_directory(project, "method-a")
    (current / theory.KNOWLEDGE_FILENAME).unlink()

    with pytest.raises(
        theory.TheoryRecordCorrupt,
        match="knowledge fragment",
    ):
        theory.load_current_theory(project, "method-a")


def test_prepare_theory_rejects_corrupt_current_without_touching_stage(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    current_output, seal = _stage(
        project, "run-current", "# Theory\n\nIntact.", identity=identity
    )
    theory.promote_staged_theory(
        project, current_output, seal, expected_method_identity=identity
    )
    canonical = theory.current_theory_directory(project, "method-a")
    (canonical / theory.THEORY_FILENAME).write_text(
        "# Theory\n\nTampered.", encoding="utf-8"
    )
    output = project / "runs" / "new-run"
    output.mkdir(parents=True)
    staged = output / theory.THEORY_FILENAME
    staged.write_bytes(b"existing staged work")

    with pytest.raises(theory.TheoryRecordCorrupt, match="does not match"):
        theory.prepare_staged_theory(project, output, identity)
    assert staged.read_bytes() == b"existing staged work"


def test_prepare_theory_write_is_atomic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _identity()
    output = project / "runs" / "new-run"
    output.mkdir(parents=True)
    staged = output / theory.THEORY_FILENAME
    staged.write_bytes(b"existing staged work")
    staged_knowledge = output / theory.KNOWLEDGE_FILENAME
    staged_knowledge.write_bytes(b"existing staged knowledge")
    real_replace = theory.os.replace

    def fail_stage_install(source: object, destination: object) -> None:
        if Path(destination) == staged and Path(source).suffix == ".tmp":
            raise OSError("injected staging failure")
        real_replace(source, destination)

    monkeypatch.setattr(theory.os, "replace", fail_stage_install)
    with pytest.raises(OSError, match="injected staging"):
        theory.prepare_staged_theory(project, output, identity)
    assert staged.read_bytes() == b"existing staged work"
    assert staged_knowledge.read_bytes() == b"existing staged knowledge"
    assert not list(output.glob(".*.tmp"))
    assert not list(output.glob(".*.backup"))
