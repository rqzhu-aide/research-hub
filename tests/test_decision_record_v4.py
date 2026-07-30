from __future__ import annotations

import copy

import pytest

from core import project_state


def _record() -> dict[str, object]:
    return {
        "schema_version": 4,
        "scientific_outcome": "Complete",
        "decision_requested": (
            "Decide whether to proceed, rerun, run a related phase, or defer."
        ),
        "selected_scientific_object": None,
        "recommended_user_action": "proceed",
        "recommendation": "Proceed using the current result within its stated scope.",
        "main_evidence": ["The sealed theorem and numerical report support the result."],
        "principal_risk": "Performance outside the evaluated regime remains unknown.",
        "smallest_decision_changer": "A counterexample in the evaluated regime.",
        "option_consequences": {
            "proceed": "Use this current phase record in later work.",
            "rerun": "Repeat this phase with a changed scientific question.",
            "run_related_phase": "Run another available phase first.",
            "defer": "Keep the current record without starting another run.",
        },
        "rerun_question": "Does the result hold under a wider signal regime?",
        "rerun_comparison": "This is the initial current record.",
        "current_record_summary": (
            "The result holds under assumptions A and B in the evaluated regime."
        ),
        "scientific_record_changes": [],
    }


def _addition() -> dict[str, object]:
    return {
        "statement_id": "S-P03-R001-summary-research_lead-001",
        "operation": "add",
        "changed_fields": sorted(project_state.SCIENTIFIC_RECORD_FIELDS),
        "current_values": {
            "statement_type": "Mathematical statement",
            "wording": "The estimator is consistent under assumptions A and B.",
            "scope": "The stated asymptotic regime.",
            "formulation_state": "Current",
            "assessment_status": "Supported",
            "evidential_basis": ["Theorem 1 and its complete proof."],
            "source_provenance": ["theory-manuscript.md, Theorem 1"],
            "assumptions": ["Assumptions A and B."],
            "uncertainty": ["No finite-sample error bound is claimed."],
            "logical_status": "proved",
            "mathematical_result_type": "asymptotic limit, rate, or distribution",
        },
        "evidential_basis": ["Theorem 1 and its complete proof."],
        "reason": "The completed theory run establishes this statement.",
        "parent_statement_id": None,
        "change_origin": {
            "phase": "03-idea-evaluation",
            "run": "run-001",
            "round_or_stage": "summary",
            "role": "research_lead",
        },
    }


def test_schema_four_uses_future_run_choices_and_current_summary() -> None:
    normalized = project_state.validate_decision_record(_record())

    assert normalized["recommended_user_action"] == "proceed"
    assert normalized["current_record_summary"].startswith("The result holds")
    assert "proposed_baseline" not in normalized


def test_schema_four_additions_use_current_values() -> None:
    record = _record()
    record["scientific_record_changes"] = [_addition()]

    normalized = project_state.validate_decision_record(record)

    change = normalized["scientific_record_changes"][0]
    assert change["current_values"]["formulation_state"] == "Current"
    assert "proposed_values" not in change

    invalid = copy.deepcopy(record)
    invalid["scientific_record_changes"][0]["current_values"][
        "formulation_state"
    ] = "Proposed"
    with pytest.raises(
        project_state.StateValidationError,
        match="formulation_state to Current",
    ):
        project_state.validate_decision_record(invalid)
