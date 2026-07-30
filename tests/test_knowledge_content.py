"""Tests for stable semantic knowledge content references."""

from __future__ import annotations

import copy
import json
import math
from typing import Any, Callable

import pytest

from core import empirical_schema
from core import knowledge_content as content


def _method() -> dict[str, str]:
    return {
        "stable_id": "method-a",
        "version": "v1",
        "definition_sha256": "a" * 64,
    }


def _statement(
    statement_id: str,
    *,
    wording: str,
    empirical: bool = False,
) -> dict[str, Any]:
    return {
        "statement_id": statement_id,
        "statement_type": (
            "Empirical statement"
            if empirical
            else "Mathematical statement"
        ),
        "wording": wording,
        "scope": "The stated model and regularity conditions.",
        "formulation_state": "Current",
        "assessment_status": "Supported",
        "evidential_basis": [
            "The current canonical package.",
            "The stated derivation.",
        ],
        "source_provenance": [
            "knowledge-fragment.json",
            "The canonical manuscript.",
        ],
        "assumptions": [
            "The sampling assumptions hold.",
            "The parameter lies in the stated space.",
        ],
        "uncertainty": [
            "Finite-sample behavior remains open.",
            "The boundary regime remains open.",
        ],
        "logical_status": "Not applicable" if empirical else "proved",
        "mathematical_result_type": (
            "Not applicable"
            if empirical
            else "asymptotic limit, rate, or distribution"
        ),
    }


def _summary(point: str = "The current result is useful.") -> dict[str, Any]:
    return {
        "fundamental_points": [point],
        "decision_relevant_changes": ["The current run repaired the claim."],
        "unresolved_questions": ["The boundary case remains open."],
    }


def _theory_fragment() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "theory_knowledge_fragment",
        "semantics": "complete_replacement",
        "coverage": "complete",
        "method": _method(),
        "generation": 3,
        "source_run_id": "run-003",
        "statements": [
            _statement("claim-b", wording="The auxiliary rate holds."),
            _statement("claim-a", wording="The main limit law holds."),
        ],
        "dependencies": [{
            "source_statement_id": "claim-a",
            "relation": "depends_on",
            "target_statement_id": "claim-b",
            "reason": "The main argument invokes the auxiliary rate.",
        }],
        "lead_summary": _summary(),
    }


def _evidence_entry(
    evidence_id: str,
    *,
    artifact_digest: str,
    status: str = "current",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "type": "result",
        "path": f"runs/run-004/{evidence_id}.json",
        "sha256": artifact_digest,
        "size": 42,
        "source_run_id": "run-004",
        "run_scope": "comprehensive",
        "status": status,
        "status_reason": "Validated under the current method definition.",
        "method_dependent": True,
    }


def _empirical_sources() -> tuple[dict[str, Any], dict[str, Any]]:
    statements = [
        _statement(
            "finding-b",
            wording="The diagnostic remains stable.",
            empirical=True,
        ),
        _statement(
            "finding-a",
            wording="The simulation supports the predicted rate.",
            empirical=True,
        ),
    ]
    fragment = {
        "schema_version": 1,
        "kind": "empirical_knowledge_fragment",
        "semantics": "cumulative_evidence",
        "coverage": "complete",
        "method": _method(),
        "generation": 4,
        "source_run_id": "run-004",
        "statements": statements,
        "dependencies": [{
            "source_statement_id": "finding-a",
            "relation": "tests",
            "target_statement_id": "claim-a",
            "reason": "The simulation evaluates the theoretical prediction.",
        }],
        "evidence_bindings": [
            {
                "evidence_id": "simulation",
                "evidence_status": "current",
                "role": "scientific_result",
                "assessments": [
                    {
                        "statement_id": "finding-b",
                        "relation": "qualifies",
                        "interpretation": "The diagnostic limits the scope.",
                    },
                    {
                        "statement_id": "finding-a",
                        "relation": "supports",
                        "interpretation": "The observed rate supports the claim.",
                    },
                ],
            },
            {
                "evidence_id": "implementation",
                "evidence_status": "current",
                "role": "implementation",
                "assessments": [{
                    "statement_id": "finding-a",
                    "relation": "implements",
                    "interpretation": "The code implements the stated design.",
                }],
            },
        ],
        "lead_summary": _summary("The evidence supports the predicted rate."),
    }
    index = {
        "schema_version": 1,
        "kind": "empirical_evidence_index",
        "method": _method(),
        "generation": 4,
        "source_run_id": "run-004",
        "synthesis": {
            "path": "empirical-synthesis.md",
            "sha256": "b" * 64,
            "size": 120,
        },
        "entries": [
            _evidence_entry(
                "simulation",
                artifact_digest="c" * 64,
            ),
            {
                **_evidence_entry(
                    "implementation",
                    artifact_digest="d" * 64,
                ),
                "type": "code",
            },
        ],
    }
    return fragment, index


def _reference(
    phase_slug: str,
    fragment: dict[str, Any],
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return content.build_content_reference(
        phase_slug=phase_slug,
        fragment=fragment,
        evidence_index=index,
    )


def test_reference_has_exact_versioned_shape_and_strict_validation() -> None:
    reference = _reference(content.THEORY_PHASE, _theory_fragment())

    assert set(reference) == {"schema_version", "sha256"}
    assert reference["schema_version"] == 1
    assert len(reference["sha256"]) == 64
    assert content.validate_content_reference(reference) == reference

    for invalid in (
        {"schema_version": True, "sha256": "a" * 64},
        {"schema_version": 1, "sha256": "A" * 64},
        {"schema_version": 1, "sha256": "a" * 64, "extra": True},
        {"schema_version": 1},
        ["not", "an", "object"],
    ):
        with pytest.raises(content.KnowledgeContentValidationError):
            content.validate_content_reference(invalid)


def test_theory_reference_ignores_run_and_presentation_metadata() -> None:
    original = _theory_fragment()
    changed = json.loads(
        json.dumps(
            original,
            ensure_ascii=False,
            indent=4,
            sort_keys=False,
        )
    )
    changed["generation"] = 99
    changed["source_run_id"] = "run-099"
    changed["coverage"] = "draft"
    changed["lead_summary"] = _summary("A different compact summary.")
    changed["counterpart_basis"] = {
        "generation": 21,
        "sha256": "f" * 64,
    }
    changed["statements"].reverse()
    changed["dependencies"].reverse()
    for statement in changed["statements"]:
        for field in (
            "assumptions",
            "evidential_basis",
            "source_provenance",
            "uncertainty",
        ):
            statement[field].reverse()
    changed = dict(reversed(list(changed.items())))

    assert _reference(
        content.THEORY_PHASE,
        changed,
    ) == _reference(content.THEORY_PHASE, original)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["method"].update(version="v2"),
        lambda value: value["method"].update(
            definition_sha256="e" * 64
        ),
        lambda value: (
            value["statements"][0].update(statement_id="claim-renamed"),
            value["dependencies"][0].update(
                target_statement_id="claim-renamed"
            ),
        ),
        lambda value: value["statements"][0].update(
            statement_type="Definition or methodological statement"
        ),
        lambda value: value["statements"][0].update(
            wording="A materially different auxiliary rate holds."
        ),
        lambda value: value["statements"][0].update(
            scope="A different asymptotic regime."
        ),
        lambda value: (
            value.update(coverage="draft"),
            value["statements"][0].update(
                formulation_state="Proposed"
            ),
        ),
        lambda value: value["statements"][0].update(
            assessment_status="Partially supported"
        ),
        lambda value: value["statements"][0]["evidential_basis"].append(
            "A new scientific result supports the claim."
        ),
        lambda value: value["statements"][0]["source_provenance"].append(
            "A new canonical scientific source."
        ),
        lambda value: value["statements"][0]["assumptions"].append(
            "A new scientific assumption holds."
        ),
        lambda value: value["statements"][0]["uncertainty"].append(
            "A new limitation remains."
        ),
        lambda value: value["statements"][0].update(
            logical_status="conjectured"
        ),
        lambda value: value["statements"][0].update(
            mathematical_result_type="inequality or bound"
        ),
        lambda value: value["dependencies"][0].update(
            reason="A different proof step creates the dependence."
        ),
        lambda value: value["dependencies"][0].update(relation="assumes"),
    ],
)
def test_theory_reference_changes_for_material_scientific_content(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    original = _theory_fragment()
    changed = copy.deepcopy(original)
    mutate(changed)

    assert _reference(
        content.THEORY_PHASE,
        changed,
    ) != _reference(content.THEORY_PHASE, original)


def test_empirical_reference_ignores_file_and_run_metadata() -> None:
    fragment, index = _empirical_sources()
    changed_fragment = copy.deepcopy(fragment)
    changed_index = copy.deepcopy(index)

    changed_fragment["generation"] = 8
    changed_fragment["source_run_id"] = "run-008"
    changed_fragment["coverage"] = "draft"
    changed_fragment["lead_summary"] = _summary("Different summary prose.")
    changed_fragment["counterpart_basis"] = {"phase": content.THEORY_PHASE}
    changed_fragment["statements"].reverse()
    changed_fragment["dependencies"].reverse()
    changed_fragment["evidence_bindings"].reverse()
    for statement in changed_fragment["statements"]:
        for field in (
            "assumptions",
            "evidential_basis",
            "source_provenance",
            "uncertainty",
        ):
            statement[field].reverse()
    for binding in changed_fragment["evidence_bindings"]:
        binding["assessments"].reverse()

    changed_index["generation"] = 8
    changed_index["source_run_id"] = "run-008"
    changed_index["synthesis"]["sha256"] = "9" * 64
    changed_index["synthesis"]["size"] = 999
    changed_index["counterpart_basis"] = {"phase": content.THEORY_PHASE}
    changed_index["entries"].reverse()
    for number, entry in enumerate(changed_index["entries"], start=1):
        entry["path"] = f"runs/run-008/reformatted-{number}.json"
        entry["size"] = 1000 + number
        entry["source_run_id"] = "run-008"

    assert _reference(
        content.EMPIRICAL_PHASE,
        changed_fragment,
        changed_index,
    ) == _reference(content.EMPIRICAL_PHASE, fragment, index)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda fragment, index: (
            fragment["method"].update(version="v2"),
            index["method"].update(version="v2"),
        ),
        lambda fragment, index: (
            fragment["method"].update(stable_id="method-b"),
            index["method"].update(stable_id="method-b"),
        ),
        lambda fragment, index: (
            fragment["method"].update(definition_sha256="f" * 64),
            index["method"].update(definition_sha256="f" * 64),
        ),
        lambda fragment, index: fragment["statements"][0].update(
            wording="The diagnostic now has a different scientific result."
        ),
        lambda fragment, index: fragment["dependencies"][0].update(
            reason="A different experiment evaluates the theoretical claim."
        ),
        lambda fragment, index: fragment["evidence_bindings"][0].update(
            role="diagnostic"
        ),
        lambda fragment, index: fragment["evidence_bindings"][0][
            "assessments"
        ][0].update(
            interpretation="The diagnostic supports a different scope."
        ),
        lambda fragment, index: fragment["evidence_bindings"][0][
            "assessments"
        ][0].update(
            relation="supports"
        ),
        lambda fragment, index: index["entries"][0].update(type="figure"),
        lambda fragment, index: index["entries"][0].update(
            sha256="e" * 64
        ),
        lambda fragment, index: index["entries"][0].update(
            run_scope="preliminary"
        ),
        lambda fragment, index: index["entries"][0].update(
            status_reason="The result has a different scientific status."
        ),
    ],
)
def test_empirical_reference_changes_for_material_scientific_content(
    mutate: Callable[[dict[str, Any], dict[str, Any]], Any],
) -> None:
    fragment, index = _empirical_sources()
    changed_fragment = copy.deepcopy(fragment)
    changed_index = copy.deepcopy(index)
    mutate(changed_fragment, changed_index)

    assert _reference(
        content.EMPIRICAL_PHASE,
        changed_fragment,
        changed_index,
    ) != _reference(content.EMPIRICAL_PHASE, fragment, index)


def test_legacy_false_result_is_normalized_as_exact_method_evidence() -> None:
    fragment, index = _empirical_sources()
    legacy_false = copy.deepcopy(index)
    legacy_false["entries"][0]["method_dependent"] = False

    assert _reference(
        content.EMPIRICAL_PHASE,
        fragment,
        legacy_false,
    ) == _reference(content.EMPIRICAL_PHASE, fragment, index)


def test_raw_and_normalized_empirical_indexes_have_same_semantic_hash() -> None:
    fragment, raw_index = _empirical_sources()
    normalized_index = copy.deepcopy(raw_index)
    for entry in normalized_index["entries"]:
        entry.update(empirical_schema.derived_entry_applicability(entry))

    assert _reference(
        content.EMPIRICAL_PHASE,
        fragment,
        normalized_index,
    ) == _reference(content.EMPIRICAL_PHASE, fragment, raw_index)


def test_empirical_status_and_identity_are_material_when_consistent() -> None:
    fragment, index = _empirical_sources()
    changed_fragment = copy.deepcopy(fragment)
    changed_index = copy.deepcopy(index)

    changed_index["entries"][0]["status"] = "outdated"
    changed_fragment["evidence_bindings"][0]["evidence_status"] = "outdated"

    assert _reference(
        content.EMPIRICAL_PHASE,
        changed_fragment,
        changed_index,
    ) != _reference(content.EMPIRICAL_PHASE, fragment, index)

    renamed_fragment = copy.deepcopy(fragment)
    renamed_index = copy.deepcopy(index)
    renamed_index["entries"][0]["evidence_id"] = "simulation-renamed"
    renamed_fragment["evidence_bindings"][0][
        "evidence_id"
    ] = "simulation-renamed"
    assert _reference(
        content.EMPIRICAL_PHASE,
        renamed_fragment,
        renamed_index,
    ) != _reference(content.EMPIRICAL_PHASE, fragment, index)


def test_phase_kind_and_evidence_index_contracts_are_strict() -> None:
    theory = _theory_fragment()
    empirical, index = _empirical_sources()

    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="phase_slug",
    ):
        _reference(["not", "a", "phase"], theory)  # type: ignore[arg-type]
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="phase_slug",
    ):
        _reference("02-method-development", theory)
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="must not include an evidence index",
    ):
        _reference(content.THEORY_PHASE, theory, index)
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="requires an evidence index",
    ):
        _reference(content.EMPIRICAL_PHASE, empirical)
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="kind",
    ):
        _reference(content.THEORY_PHASE, empirical)
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="kind",
    ):
        _reference(content.EMPIRICAL_PHASE, theory, index)


def test_existing_validators_reject_duplicate_semantic_identities() -> None:
    theory = _theory_fragment()
    theory["statements"].append(copy.deepcopy(theory["statements"][0]))
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="duplicate knowledge statement_id",
    ):
        _reference(content.THEORY_PHASE, theory)

    fragment, index = _empirical_sources()
    index["entries"].append(copy.deepcopy(index["entries"][0]))
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="duplicate normalized evidence_id",
    ):
        _reference(content.EMPIRICAL_PHASE, fragment, index)

    fragment, index = _empirical_sources()
    fragment["evidence_bindings"].append(
        copy.deepcopy(fragment["evidence_bindings"][0])
    )
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="duplicate evidence binding",
    ):
        _reference(content.EMPIRICAL_PHASE, fragment, index)

    fragment, index = _empirical_sources()
    fragment["evidence_bindings"][0]["assessments"].append(
        copy.deepcopy(
            fragment["evidence_bindings"][0]["assessments"][0]
        )
    )
    with pytest.raises(
        content.KnowledgeContentValidationError,
        match="duplicate evidence assessment",
    ):
        _reference(content.EMPIRICAL_PHASE, fragment, index)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda fragment, index: index.update(kind="wrong_kind"),
        lambda fragment, index: index["entries"][0].pop("type"),
        lambda fragment, index: index["entries"][0].update(
            sha256="not-a-digest"
        ),
        lambda fragment, index: index["entries"][0].update(
            method_dependent=1
        ),
        lambda fragment, index: index["entries"][0].update(
            status_reason=math.nan
        ),
        lambda fragment, index: index["entries"][0].update(
            unexpected=True
        ),
    ],
)
def test_malformed_empirical_inputs_are_rejected(
    mutate: Callable[[dict[str, Any], dict[str, Any]], Any],
) -> None:
    fragment, index = _empirical_sources()
    mutate(fragment, index)

    with pytest.raises(content.KnowledgeContentValidationError):
        _reference(content.EMPIRICAL_PHASE, fragment, index)
