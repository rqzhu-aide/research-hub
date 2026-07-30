"""Strict schema tests for Phase 3 and Phase 4 knowledge fragments."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from core import knowledge_fragments as fragments


def _method() -> dict[str, str]:
    return {
        "stable_id": "method-a",
        "version": "v1",
        "definition_sha256": "a" * 64,
    }


def _statement(
    statement_id: str = "S-P03-R001-summary-research_lead-001",
    *,
    formulation_state: str = "Current",
) -> dict[str, object]:
    return {
        "statement_id": statement_id,
        "statement_type": "Mathematical statement",
        "wording": "The estimator is consistent under assumptions A and B.",
        "scope": "The stated asymptotic regime.",
        "formulation_state": formulation_state,
        "assessment_status": "Supported",
        "evidential_basis": ["Theorem 1 and its complete proof."],
        "source_provenance": ["theory-manuscript.md, Theorem 1"],
        "assumptions": ["Assumptions A and B."],
        "uncertainty": ["No finite-sample error bound is claimed."],
        "logical_status": "proved",
        "mathematical_result_type": "asymptotic limit, rate, or distribution",
    }


def _summary() -> dict[str, list[str]]:
    return {
        "fundamental_points": ["The estimator is consistent."],
        "decision_relevant_changes": ["The proof now covers regime B."],
        "unresolved_questions": ["Finite-sample behavior remains open."],
    }


def _theory_fragment(*, coverage: str = "complete") -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "theory_knowledge_fragment",
        "semantics": "complete_replacement",
        "coverage": coverage,
        "method": _method(),
        "generation": 1,
        "source_run_id": "run-001",
        "statements": [_statement()],
        "dependencies": [],
        "lead_summary": _summary(),
    }


def _evidence_index() -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "empirical_evidence_index",
        "method": _method(),
        "generation": 2,
        "source_run_id": "run-002",
        "synthesis": {
            "path": "empirical-synthesis.md",
            "sha256": "b" * 64,
            "size": 120,
        },
        "entries": [
            {
                "evidence_id": "pilot",
                "type": "result",
                "path": "runs/run-001/pilot.json",
                "sha256": "c" * 64,
                "size": 25,
                "source_run_id": "run-001",
                "run_scope": "preliminary",
                "status": "outdated",
                "status_reason": "The method definition changed.",
                "method_dependent": True,
            },
            {
                "evidence_id": "current-study",
                "type": "result",
                "path": "runs/run-002/current.json",
                "sha256": "d" * 64,
                "size": 30,
                "source_run_id": "run-002",
                "run_scope": "comprehensive",
                "status": "current",
                "status_reason": "Validated under the current definition.",
                "method_dependent": True,
            },
        ],
    }


def _empirical_fragment(*, coverage: str = "complete") -> dict[str, object]:
    empirical_statement = _statement(
        "S-P04-R002-summary-research_lead-001"
    )
    empirical_statement["statement_type"] = "Empirical statement"
    empirical_statement["logical_status"] = "Not applicable"
    empirical_statement["mathematical_result_type"] = "Not applicable"
    return {
        "schema_version": 1,
        "kind": "empirical_knowledge_fragment",
        "semantics": "cumulative_evidence",
        "coverage": coverage,
        "method": _method(),
        "generation": 2,
        "source_run_id": "run-002",
        "statements": [empirical_statement],
        "dependencies": [
            {
                "source_statement_id": empirical_statement["statement_id"],
                "relation": "tests",
                "target_statement_id": (
                    "S-P03-R001-summary-research_lead-001"
                ),
                "reason": "The simulation evaluates the theoretical prediction.",
            }
        ],
        "evidence_bindings": [
            {
                "evidence_id": "pilot",
                "evidence_status": "outdated",
                "role": "scientific_result",
                "assessments": [],
            },
            {
                "evidence_id": "current-study",
                "evidence_status": "current",
                "role": "scientific_result",
                "assessments": [
                    {
                        "statement_id": empirical_statement["statement_id"],
                        "relation": "supports",
                        "interpretation": (
                            "The comprehensive study supports the empirical claim."
                        ),
                    }
                ],
            },
        ],
        "lead_summary": _summary(),
    }


def test_complete_theory_fragment_normalizes_existing_scientific_vocabulary() -> None:
    fragment = _theory_fragment()

    normalized = fragments.validate_theory_fragment(
        fragment,
        expected_method=_method(),
        expected_generation=1,
        expected_source_run_id="run-001",
    )

    assert normalized["kind"] == fragments.THEORY_KIND
    assert normalized["statements"][0]["logical_status"] == "proved"
    assert normalized["lead_summary"]["fundamental_points"]


def test_theory_fragment_rejects_extra_fields_and_duplicate_statement_ids() -> None:
    extra = _theory_fragment()
    extra["unexpected"] = True
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="unexpected unexpected",
    ):
        fragments.validate_theory_fragment(extra)

    duplicate = _theory_fragment()
    duplicate["statements"].append(copy.deepcopy(duplicate["statements"][0]))
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="duplicate knowledge statement_id",
    ):
        fragments.validate_theory_fragment(duplicate)


def test_draft_theory_allows_proposed_statements_but_complete_does_not() -> None:
    fragment = _theory_fragment(coverage="draft")
    fragment["statements"][0]["formulation_state"] = "Proposed"

    normalized = fragments.validate_theory_fragment(
        fragment, require_complete=False
    )
    assert normalized["coverage"] == "draft"

    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="coverage must be complete",
    ):
        fragments.validate_theory_fragment(fragment)

    invalid_complete = copy.deepcopy(fragment)
    invalid_complete["coverage"] = "complete"
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="formulation_state Current",
    ):
        fragments.validate_theory_fragment(invalid_complete)


def test_complete_fragment_requires_content_but_draft_may_be_empty() -> None:
    draft = _theory_fragment(coverage="draft")
    draft["statements"] = []
    draft["lead_summary"]["fundamental_points"] = []

    normalized = fragments.validate_theory_fragment(
        draft, require_complete=False
    )

    assert normalized["statements"] == []
    assert normalized["lead_summary"]["fundamental_points"] == []

    empty_statements = copy.deepcopy(draft)
    empty_statements["coverage"] = "complete"
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="at least one current statement",
    ):
        fragments.validate_theory_fragment(empty_statements)

    empty_summary = _theory_fragment()
    empty_summary["lead_summary"]["fundamental_points"] = []
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="at least one fundamental_points entry",
    ):
        fragments.validate_theory_fragment(empty_summary)


def test_dependency_source_must_be_local_but_target_may_be_cross_phase() -> None:
    fragment = _theory_fragment()
    fragment["dependencies"] = [
        {
            "source_statement_id": fragment["statements"][0]["statement_id"],
            "relation": "qualifies",
            "target_statement_id": "S-P04-external-001",
            "reason": "The theorem is qualified by an empirical discrepancy.",
        }
    ]
    normalized = fragments.validate_theory_fragment(fragment)
    assert normalized["dependencies"][0]["target_statement_id"].startswith(
        "S-P04"
    )

    fragment["dependencies"][0]["source_statement_id"] = "S-P03-unknown"
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="source_statement_id is not defined",
    ):
        fragments.validate_theory_fragment(fragment)


def test_empirical_fragment_requires_exact_evidence_binding_coverage() -> None:
    normalized = fragments.validate_empirical_fragment(
        _empirical_fragment(), _evidence_index()
    )
    assert {
        item["evidence_id"] for item in normalized["evidence_bindings"]
    } == {"pilot", "current-study"}

    missing = _empirical_fragment()
    missing["evidence_bindings"] = missing["evidence_bindings"][1:]
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="omits evidence IDs: pilot",
    ):
        fragments.validate_empirical_fragment(missing, _evidence_index())


def test_draft_empirical_fragment_may_have_partial_known_bindings() -> None:
    fragment = _empirical_fragment(coverage="draft")
    fragment["evidence_bindings"] = fragment["evidence_bindings"][1:]

    normalized = fragments.validate_empirical_fragment(
        fragment, _evidence_index(), require_complete=False
    )
    assert [
        item["evidence_id"] for item in normalized["evidence_bindings"]
    ] == ["current-study"]

    fragment["evidence_bindings"][0]["evidence_id"] = "unknown"
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="unknown evidence_id",
    ):
        fragments.validate_empirical_fragment(
            fragment, _evidence_index(), require_complete=False
        )


def test_empirical_fragment_rejects_status_and_basis_mismatches() -> None:
    wrong_status = _empirical_fragment()
    wrong_status["evidence_bindings"][0]["evidence_status"] = "current"
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="does not match evidence-index status",
    ):
        fragments.validate_empirical_fragment(
            wrong_status, _evidence_index()
        )

    wrong_generation = _empirical_fragment()
    wrong_generation["generation"] = 3
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="generation does not match",
    ):
        fragments.validate_empirical_fragment(
            wrong_generation, _evidence_index()
        )

    wrong_method = _empirical_fragment()
    wrong_method["method"]["version"] = "v2"
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="method does not match",
    ):
        fragments.validate_empirical_fragment(
            wrong_method, _evidence_index()
        )


def test_empirical_assessment_must_name_a_local_statement() -> None:
    fragment = _empirical_fragment()
    fragment["evidence_bindings"][1]["assessments"][0][
        "statement_id"
    ] = "S-P04-unknown"

    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="statement_id is not defined in this fragment",
    ):
        fragments.validate_empirical_fragment(fragment, _evidence_index())


def test_noncurrent_evidence_cannot_assess_a_current_statement() -> None:
    index = _evidence_index()
    index["schema_version"] = 3
    index["entries"][0]["applicability_state"] = "attention"
    index["entries"][1]["applicability_state"] = "active_current_method"
    fragment = _empirical_fragment()
    fragment["evidence_bindings"][0]["assessments"] = [
        copy.deepcopy(
            fragment["evidence_bindings"][1]["assessments"][0]
        )
    ]

    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="cannot use noncurrent evidence for a Current statement",
    ):
        fragments.validate_empirical_fragment(fragment, index)


def test_empirical_fragment_rejects_duplicate_binding_and_assessment() -> None:
    duplicate_binding = _empirical_fragment()
    duplicate_binding["evidence_bindings"].append(
        copy.deepcopy(duplicate_binding["evidence_bindings"][0])
    )
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="duplicate evidence binding",
    ):
        fragments.validate_empirical_fragment(
            duplicate_binding, _evidence_index()
        )

    duplicate_assessment = _empirical_fragment()
    assessments = duplicate_assessment["evidence_bindings"][1]["assessments"]
    assessments.append(copy.deepcopy(assessments[0]))
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="duplicate evidence assessment",
    ):
        fragments.validate_empirical_fragment(
            duplicate_assessment, _evidence_index()
        )


def test_parse_fragment_rejects_duplicate_fields_and_nonfinite_values() -> None:
    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="duplicate field 'kind'",
    ):
        fragments.parse_fragment(b'{"kind":"a","kind":"b"}')

    with pytest.raises(
        fragments.KnowledgeFragmentValidationError,
        match="invalid numeric value",
    ):
        fragments.parse_fragment(b'{"value":NaN}')


def test_read_fragment_reads_regular_utf8_json(tmp_path: Path) -> None:
    path = tmp_path / fragments.KNOWLEDGE_FILENAME
    payload = (
        json.dumps(_theory_fragment(), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    path.write_bytes(payload)

    parsed, actual = fragments.read_fragment(path)

    assert parsed["kind"] == fragments.THEORY_KIND
    assert actual == payload
