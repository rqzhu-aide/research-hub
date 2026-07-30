"""Rollback boundaries for phase-specific current-record promotions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core import empirical_records
from core import knowledge_basis
from core import literature_records
from core import manuscript_records
from core import theory_records


def _digest(value: str | bytes) -> str:
    payload = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _method_identity() -> dict[str, str]:
    return {
        "stable_id": "method-a",
        "version": "v1",
        "definition_sha256": _digest("method-a:v1"),
    }


def _complete_theory_fragment(output: Path) -> None:
    path = output / theory_records.KNOWLEDGE_FILENAME
    fragment = json.loads(path.read_text(encoding="utf-8"))
    statement_id = (
        f"S-P03-{fragment['source_run_id']}-research_lead-001"
    )
    fragment["coverage"] = "complete"
    fragment["statements"] = [
        {
            "statement_id": statement_id,
            "statement_type": "Mathematical statement",
            "wording": "The current method has a complete proof.",
            "scope": "The assumptions stated in the theory manuscript.",
            "formulation_state": "Current",
            "assessment_status": "Supported",
            "evidential_basis": ["The complete theory manuscript."],
            "source_provenance": ["theory-manuscript.md"],
            "assumptions": ["The stated regularity conditions."],
            "uncertainty": ["Finite-sample behavior remains open."],
            "logical_status": "proved",
            "mathematical_result_type": (
                "asymptotic limit, rate, or distribution"
            ),
        }
    ]
    fragment["dependencies"] = []
    fragment["lead_summary"] = {
        "fundamental_points": ["The principal result has a complete proof."],
        "decision_relevant_changes": [],
        "unresolved_questions": ["Finite-sample behavior remains open."],
    }
    path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _theory_stage(
    project: Path,
    run_id: str,
    text: str,
) -> tuple[Path, dict[str, object]]:
    output = project / "runs" / run_id
    output.mkdir(parents=True, exist_ok=True)
    theory_records.prepare_staged_theory(
        project,
        output,
        _method_identity(),
        source_run_id=run_id,
    )
    (output / theory_records.THEORY_FILENAME).write_text(text, encoding="utf-8")
    _complete_theory_fragment(output)
    seal = theory_records.seal_staged_theory(
        project,
        output,
        method_identity=_method_identity(),
        source_run_id=run_id,
        scientific_outcome="Complete",
    )
    return output, seal


def test_theory_transaction_rolls_back_first_and_replacement_promotions(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method_identity()
    first_output, first_seal = _theory_stage(
        project, "theory-1", "# Theory\n\nFirst complete proof.\n"
    )

    first_transaction = theory_records.promote_staged_theory(
        project,
        first_output,
        first_seal,
        expected_method_identity=identity,
        retain_backup=True,
    )
    theory_records.rollback_theory_promotion(project, first_transaction)
    assert theory_records.load_current_theory(project, "method-a") is None

    first = theory_records.promote_staged_theory(
        project,
        first_output,
        first_seal,
        expected_method_identity=identity,
    )
    second_output, second_seal = _theory_stage(
        project, "theory-2", "# Theory\n\nRepaired complete proof.\n"
    )
    replacement = theory_records.promote_staged_theory(
        project,
        second_output,
        second_seal,
        expected_method_identity=identity,
        retain_backup=True,
    )
    backup = project / replacement["_promotion_transaction"]["backup_path"]
    assert backup.is_dir()

    theory_records.rollback_theory_promotion(project, replacement)
    assert theory_records.load_current_theory(project, "method-a") == first
    assert not backup.exists()

    committed = theory_records.promote_staged_theory(
        project,
        second_output,
        second_seal,
        expected_method_identity=identity,
        retain_backup=True,
    )
    committed_backup = project / committed["_promotion_transaction"]["backup_path"]
    theory_records.commit_theory_promotion(project, committed)
    assert theory_records.load_current_theory(project, "method-a")[
        "source_run_id"
    ] == "theory-2"
    assert not committed_backup.exists()


def _manuscript_basis(
    identity: dict[str, str],
) -> dict[str, dict[str, object]]:
    return {
        "p1_synthesis": {
            "identity": "literature-synthesis",
            "sha256": _digest("p1"),
            "generation": 1,
        },
        "p1_collection": {
            "identity": "reference-card-collection",
            "sha256": _digest("p1-collection"),
            "generation": 1,
        },
        "p2_definition": {
            "identity": identity,
            "sha256": identity["definition_sha256"],
            "generation": None,
        },
        "p3_record": {
            "identity": "method-a:theory",
            "sha256": _digest("p3"),
            "generation": 1,
        },
        "p4_synthesis": {
            "identity": "method-a:empirical-synthesis",
            "sha256": _digest("p4-synthesis"),
            "generation": 1,
        },
        "p4_index": {
            "identity": "method-a:evidence-index",
            "sha256": _digest("p4-index"),
            "generation": 1,
        },
    }


def _manuscript_stage(
    project: Path,
    run_id: str,
    text: str,
) -> tuple[Path, dict[str, object]]:
    identity = _method_identity()
    output = project / "runs" / run_id
    output.mkdir(parents=True, exist_ok=True)
    (output / manuscript_records.MANUSCRIPT_FILENAME).write_text(
        text, encoding="utf-8"
    )
    seal = manuscript_records.seal_staged_manuscript(
        project,
        output,
        method_identity=identity,
        upstream_basis=_manuscript_basis(identity),
        source_run_id=run_id,
        scientific_outcome="Complete",
    )
    return output, seal


def test_manuscript_transaction_restores_absence_and_previous_draft(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method_identity()
    basis = _manuscript_basis(identity)
    first_output, first_seal = _manuscript_stage(
        project, "draft-1", "# Manuscript\n\nFirst complete draft.\n"
    )
    first_transaction = manuscript_records.promote_staged_manuscript(
        project,
        first_output,
        first_seal,
        expected_method_identity=identity,
        expected_upstream_basis=basis,
        retain_backup=True,
    )
    manuscript_records.rollback_manuscript_promotion(
        project, first_transaction
    )
    assert manuscript_records.load_current_manuscript(project, "method-a") is None

    first = manuscript_records.promote_staged_manuscript(
        project,
        first_output,
        first_seal,
        expected_method_identity=identity,
        expected_upstream_basis=basis,
    )
    second_output, second_seal = _manuscript_stage(
        project, "draft-2", "# Manuscript\n\nUpdated complete draft.\n"
    )
    replacement = manuscript_records.promote_staged_manuscript(
        project,
        second_output,
        second_seal,
        expected_method_identity=identity,
        expected_upstream_basis=basis,
        retain_backup=True,
    )
    manuscript_records.rollback_manuscript_promotion(project, replacement)
    assert manuscript_records.load_current_manuscript(project, "method-a") == first


def _literature_card(title: str, arxiv_id: str, run_id: str) -> str:
    return (
        "---\n"
        f"arxiv_id: {json.dumps(arxiv_id)}\n"
        f"title: {json.dumps(title)}\n"
        'authors: ["First Author", "Second Author"]\n'
        "year: 2025\n"
        'venue: "Journal of Careful Tests"\n'
        'relation: "direct prior work"\n'
        f"found_in_run: {json.dumps(run_id)}\n"
        'found_by_role: "research_lead"\n'
        "also_found_in: []\n"
        "---\n\n"
        f"# {title}\n\nA precise assessment.\n"
    )


def _literature_stage(
    project: Path,
    run_id: str,
    cards: dict[str, str],
) -> tuple[Path, dict[str, object]]:
    output = project / "runs" / run_id
    literature_records.prepare_reference_delta(
        project, output, source_run_id=run_id
    )
    delta = output / literature_records.STAGED_DELTA_DIRNAME
    papers = delta / literature_records.STAGED_PAPERS_DIRNAME
    for filename, text in cards.items():
        (papers / filename).write_text(text, encoding="utf-8", newline="")
    (delta / literature_records.STAGED_SUMMARY_FILENAME).write_text(
        f"# Literature summary\n\nCurrent through {run_id}.\n",
        encoding="utf-8",
        newline="",
    )
    return output, literature_records.seal_reference_delta(project, output)


def _literature_bytes(project: Path) -> dict[str, bytes]:
    references = project / literature_records.REFERENCE_DIR
    result: dict[str, bytes] = {}
    papers = project / literature_records.PAPERS_DIR
    if papers.exists():
        for path in sorted(papers.iterdir()):
            result[f"papers/{path.name}"] = path.read_bytes()
    for filename in (
        literature_records.REFERENCE_INDEX.name,
        literature_records.LITERATURE_SUMMARY.name,
    ):
        path = references / filename
        if path.exists():
            result[filename] = path.read_bytes()
    return result


def test_literature_transaction_restores_empty_and_previous_libraries(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first_output, first_seal = _literature_stage(
        project,
        "literature-1",
        {
            "paper-a.md": _literature_card(
                "First paper", "2501.00001", "literature-1"
            )
        },
    )
    first_transaction = literature_records.promote_reference_delta(
        project, first_output, first_seal, retain_backup=True
    )
    literature_records.rollback_reference_delta_promotion(
        project, first_transaction
    )
    literature_records.rollback_reference_delta_promotion(
        project, first_transaction
    )
    assert literature_records.load_current_literature_record(project) is None
    assert _literature_bytes(project) == {}

    literature_records.promote_reference_delta(project, first_output, first_seal)
    before = _literature_bytes(project)
    second_output, second_seal = _literature_stage(
        project,
        "literature-2",
        {
            "paper-b.md": _literature_card(
                "Second paper", "2501.00002", "literature-2"
            )
        },
    )
    replacement = literature_records.promote_reference_delta(
        project, second_output, second_seal, retain_backup=True
    )
    literature_records.rollback_reference_delta_promotion(project, replacement)
    literature_records.rollback_reference_delta_promotion(project, replacement)
    assert _literature_bytes(project) == before


def test_literature_transaction_handles_preexisting_empty_papers_directory(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    papers = project / literature_records.PAPERS_DIR
    papers.mkdir(parents=True)
    output, seal = _literature_stage(
        project,
        "literature-empty-baseline",
        {
            "paper-a.md": _literature_card(
                "First paper",
                "2501.00001",
                "literature-empty-baseline",
            )
        },
    )

    rollback_transaction = literature_records.promote_reference_delta(
        project,
        output,
        seal,
        retain_backup=True,
    )
    rollback_backup = project / rollback_transaction[
        "_promotion_transaction"
    ]["backup_path"]
    assert rollback_backup.is_dir()
    literature_records.rollback_reference_delta_promotion(
        project,
        rollback_transaction,
    )
    assert papers.is_dir()
    assert list(papers.iterdir()) == []

    commit_transaction = literature_records.promote_reference_delta(
        project,
        output,
        seal,
        retain_backup=True,
    )
    commit_backup = project / commit_transaction[
        "_promotion_transaction"
    ]["backup_path"]
    literature_records.commit_reference_delta_promotion(
        project,
        commit_transaction,
    )
    assert not commit_backup.exists()
    current = literature_records.load_current_literature_record(project)
    assert current is not None
    assert current["source_run_id"] == "literature-empty-baseline"


def _complete_empirical_fragment(index: dict) -> dict:
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
                "statement_id": (
                    f"S-P04-{index['source_run_id']}-research_lead-001"
                ),
                "statement_type": "Empirical statement",
                "wording": (
                    "The synthesis reports the current empirical record."
                ),
                "scope": "The simulations and analyses in the evidence index.",
                "formulation_state": "Current",
                "assessment_status": "Supported",
                "evidential_basis": [
                    "The empirical synthesis and evidence index."
                ],
                "source_provenance": [
                    empirical_records.SYNTHESIS_FILENAME
                ],
                "assumptions": [
                    "The recorded analyses completed as described."
                ],
                "uncertainty": [
                    "Limitations remain stated in the synthesis."
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
                "The synthesis records the current empirical evidence."
            ],
            "decision_relevant_changes": [],
            "unresolved_questions": [],
        },
    }
def _write_empirical_stage(
    project: Path,
    run_id: str,
    generation: int,
) -> Path:
    output = project / "runs" / run_id
    output.mkdir(parents=True, exist_ok=True)
    synthesis = output / empirical_records.SYNTHESIS_FILENAME
    synthesis.write_text(
        f"# Empirical synthesis\n\nResults through {run_id}.\n",
        encoding="utf-8",
    )
    index = {
        "schema_version": empirical_records.INDEX_SCHEMA_VERSION,
        "kind": empirical_records.INDEX_KIND,
        "method": _method_identity(),
        "generation": generation,
        "source_run_id": run_id,
        "synthesis": {
            "path": empirical_records.SYNTHESIS_FILENAME,
            "sha256": _digest(synthesis.read_bytes()),
            "size": synthesis.stat().st_size,
        },
        "entries": [],
        "counterpart_basis": knowledge_basis.unknown_legacy_basis(
            phase_slug=knowledge_basis.THEORY_PHASE,
        ),
    }
    (output / empirical_records.INDEX_FILENAME).write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    (output / empirical_records.KNOWLEDGE_FILENAME).write_text(
        json.dumps(
            _complete_empirical_fragment(index),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def test_empirical_transaction_rolls_back_first_and_replacement_packages(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    first_output = _write_empirical_stage(project, "empirical-1", 1)
    first_transaction = empirical_records.promote_staged_package(
        project, first_output, retain_backup=True
    )
    empirical_records.rollback_empirical_package_promotion(
        project, first_transaction
    )
    assert empirical_records.load_current_package(project, "method-a") is None

    empirical_records.promote_staged_package(project, first_output)
    second_output = _write_empirical_stage(project, "empirical-2", 2)
    replacement = empirical_records.promote_staged_package(
        project, second_output, retain_backup=True
    )
    backup = project / replacement["_promotion_transaction"]["backup_path"]
    assert backup.is_dir()
    empirical_records.rollback_empirical_package_promotion(project, replacement)
    restored = empirical_records.load_current_package(project, "method-a")
    assert restored is not None and restored["source_run_id"] == "empirical-1"
    assert not backup.exists()

    committed = empirical_records.promote_staged_package(
        project, second_output, retain_backup=True
    )
    committed_backup = project / committed["_promotion_transaction"]["backup_path"]
    empirical_records.commit_empirical_package_promotion(project, committed)
    current = empirical_records.load_current_package(project, "method-a")
    assert current is not None and current["source_run_id"] == "empirical-2"
    assert not committed_backup.exists()
