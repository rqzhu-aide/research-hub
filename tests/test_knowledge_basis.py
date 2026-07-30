"""Comprehensive tests for pure cross-phase knowledge basis values."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from core import knowledge_basis as basis


def _method(
    *,
    stable_id: str = "method-a",
    version: str = "v1",
    digest: str = "a" * 64,
) -> dict[str, str]:
    return {
        "stable_id": stable_id,
        "version": version,
        "definition_sha256": digest,
    }


def _reference(digest: str = "b" * 64) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "sha256": digest,
    }


def _available(
    *,
    phase_slug: str = basis.THEORY_PHASE,
    method: dict[str, str] | None = None,
    reference: dict[str, Any] | None = None,
    generation: int = 3,
    run_id: str = "run-003",
) -> dict[str, Any]:
    return basis.available_basis(
        phase_slug=phase_slug,
        method_identity=method or _method(),
        content_reference=reference or _reference(),
        generation=generation,
        source_run_id=run_id,
    )


def test_available_constructor_has_exact_normalized_shape() -> None:
    method = _method()
    reference = _reference()
    result = basis.available_basis(
        phase_slug=basis.THEORY_PHASE,
        method_identity=method,
        content_reference=reference,
        generation=3,
        source_run_id="run-003",
    )

    assert list(result) == [
        "schema_version",
        "phase_slug",
        "state",
        "method_identity",
        "content_reference",
        "generation",
        "source_run_id",
    ]
    assert result == {
        "schema_version": 1,
        "phase_slug": basis.THEORY_PHASE,
        "state": "available",
        "method_identity": method,
        "content_reference": reference,
        "generation": 3,
        "source_run_id": "run-003",
    }
    assert result["method_identity"] is not method
    assert result["content_reference"] is not reference
    assert basis.validate_basis(result) == result


@pytest.mark.parametrize(
    "phase_slug",
    [basis.THEORY_PHASE, basis.EMPIRICAL_PHASE],
)
def test_all_constructors_support_only_the_two_knowledge_phases(
    phase_slug: str,
) -> None:
    assert _available(phase_slug=phase_slug)["phase_slug"] == phase_slug
    assert basis.unknown_legacy_basis(
        phase_slug=phase_slug,
    )["phase_slug"] == phase_slug
    assert basis.absent_basis(
        phase_slug=phase_slug,
    )["phase_slug"] == phase_slug


def test_unknown_legacy_accepts_known_or_unavailable_provenance() -> None:
    known = basis.unknown_legacy_basis(
        phase_slug=basis.THEORY_PHASE,
        method_identity=_method(),
        generation=4,
        source_run_id="legacy-run-004",
    )
    unavailable = basis.unknown_legacy_basis(
        phase_slug=basis.EMPIRICAL_PHASE,
    )

    assert known == {
        "schema_version": 1,
        "phase_slug": basis.THEORY_PHASE,
        "state": "unknown_legacy",
        "method_identity": _method(),
        "content_reference": None,
        "generation": 4,
        "source_run_id": "legacy-run-004",
    }
    assert unavailable == {
        "schema_version": 1,
        "phase_slug": basis.EMPIRICAL_PHASE,
        "state": "unknown_legacy",
        "method_identity": None,
        "content_reference": None,
        "generation": None,
        "source_run_id": None,
    }


def test_absent_constructor_has_no_provenance() -> None:
    assert basis.absent_basis(
        phase_slug=basis.THEORY_PHASE,
    ) == {
        "schema_version": 1,
        "phase_slug": basis.THEORY_PHASE,
        "state": "absent",
        "method_identity": None,
        "content_reference": None,
        "generation": None,
        "source_run_id": None,
    }


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.pop("state"),
        lambda value: value.update(extra=True),
        lambda value: value.update(schema_version=True),
        lambda value: value.update(schema_version=2),
        lambda value: value.update(phase_slug="02-method-development"),
        lambda value: value.update(phase_slug=True),
        lambda value: value.update(state="current"),
        lambda value: value.update(state=True),
    ],
)
def test_basis_rejects_bad_envelope_fields(
    mutate: Any,
) -> None:
    value = _available()
    mutate(value)

    with pytest.raises(basis.KnowledgeBasisValidationError):
        basis.validate_basis(value)


@pytest.mark.parametrize(
    "method",
    [
        {
            "stable_id": "bad id",
            "version": "v1",
            "definition_sha256": "a" * 64,
        },
        {
            "stable_id": "method-a",
            "version": "bad version!",
            "definition_sha256": "a" * 64,
        },
        {
            "stable_id": "method-a",
            "version": "v1",
            "definition_sha256": "A" * 64,
        },
        {
            "stable_id": "method-a",
            "version": "v1",
            "definition_sha256": "a" * 63,
        },
        {
            "stable_id": "method-a",
            "version": "v1",
            "definition_sha256": "a" * 64,
            "extra": "field",
        },
        {
            "stable_id": "method-a",
            "definition_sha256": "a" * 64,
        },
    ],
)
def test_available_rejects_bad_method_identity(
    method: dict[str, Any],
) -> None:
    value = _available()
    value["method_identity"] = method

    with pytest.raises(
        basis.KnowledgeBasisValidationError,
        match="method_identity",
    ):
        basis.validate_basis(value)


@pytest.mark.parametrize(
    "reference",
    [
        {"schema_version": True, "sha256": "b" * 64},
        {"schema_version": 2, "sha256": "b" * 64},
        {"schema_version": 1, "sha256": "B" * 64},
        {"schema_version": 1, "sha256": "b" * 63},
        {"schema_version": 1, "sha256": "b" * 64, "extra": True},
        {"schema_version": 1},
        "not-a-reference",
    ],
)
def test_available_rejects_bad_content_reference(
    reference: Any,
) -> None:
    value = _available()
    value["content_reference"] = reference

    with pytest.raises(
        basis.KnowledgeBasisValidationError,
        match="content_reference",
    ):
        basis.validate_basis(value)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("method_identity", None),
        ("content_reference", None),
        ("generation", None),
        ("source_run_id", None),
        ("generation", True),
        ("generation", 0),
        ("generation", -1),
        ("generation", basis.MAX_GENERATION + 1),
        ("source_run_id", ""),
        ("source_run_id", " run-003"),
        ("source_run_id", "run/003"),
        ("source_run_id", True),
        ("source_run_id", "r" * (basis.MAX_RUN_ID_LENGTH + 1)),
    ],
)
def test_available_requires_complete_bounded_provenance(
    field: str,
    invalid: Any,
) -> None:
    value = _available()
    value[field] = invalid

    with pytest.raises(basis.KnowledgeBasisValidationError):
        basis.validate_basis(value)


def test_maximum_length_run_id_is_valid() -> None:
    run_id = "r" * basis.MAX_RUN_ID_LENGTH

    assert _available(run_id=run_id)["source_run_id"] == run_id


@pytest.mark.parametrize(
    ("method", "generation", "run_id"),
    [
        (_method(), None, None),
        (None, 2, None),
        (None, None, "legacy-run"),
        (_method(), 2, None),
        (_method(), None, "legacy-run"),
        (None, 2, "legacy-run"),
    ],
)
def test_unknown_legacy_rejects_partial_provenance(
    method: dict[str, str] | None,
    generation: int | None,
    run_id: str | None,
) -> None:
    with pytest.raises(
        basis.KnowledgeBasisValidationError,
        match="all present or all null",
    ):
        basis.unknown_legacy_basis(
            phase_slug=basis.THEORY_PHASE,
            method_identity=method,
            generation=generation,
            source_run_id=run_id,
        )


def test_unknown_legacy_rejects_a_content_reference() -> None:
    value = basis.unknown_legacy_basis(
        phase_slug=basis.THEORY_PHASE,
    )
    value["content_reference"] = _reference()

    with pytest.raises(
        basis.KnowledgeBasisValidationError,
        match="must not have a content reference",
    ):
        basis.validate_basis(value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("method_identity", _method()),
        ("content_reference", _reference()),
        ("generation", 1),
        ("source_run_id", "run-001"),
    ],
)
def test_absent_rejects_any_provenance(
    field: str,
    value: Any,
) -> None:
    absent = basis.absent_basis(phase_slug=basis.THEORY_PHASE)
    absent[field] = value

    with pytest.raises(
        basis.KnowledgeBasisValidationError,
        match="must not contain provenance",
    ):
        basis.validate_basis(absent)


def test_semantic_alignment_distinguishes_absence_from_record_existence() -> None:
    source_absent = basis.absent_basis(phase_slug=basis.THEORY_PHASE)
    stored_absent = basis.absent_basis(phase_slug=basis.THEORY_PHASE)
    available = _available()

    assert (
        basis.semantic_alignment(source_absent, stored_absent)
        == "exact_match"
    )
    assert (
        basis.semantic_alignment(source_absent, available)
        == "review_required"
    )
    assert (
        basis.semantic_alignment(available, stored_absent)
        == "review_required"
    )


def test_semantic_alignment_rejects_different_basis_phases() -> None:
    source = _available(phase_slug=basis.THEORY_PHASE)
    target = _available(phase_slug=basis.EMPIRICAL_PHASE)

    with pytest.raises(
        basis.KnowledgeBasisValidationError,
        match="matching phase_slug",
    ):
        basis.semantic_alignment(source, target)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (
            basis.unknown_legacy_basis(
                phase_slug=basis.THEORY_PHASE,
            ),
            _available(),
        ),
        (
            _available(),
            basis.unknown_legacy_basis(
                phase_slug=basis.THEORY_PHASE,
                method_identity=_method(),
                generation=2,
                source_run_id="legacy-run",
            ),
        ),
        (
            basis.unknown_legacy_basis(
                phase_slug=basis.THEORY_PHASE,
            ),
            basis.unknown_legacy_basis(
                phase_slug=basis.THEORY_PHASE,
            ),
        ),
    ],
)
def test_any_unknown_legacy_basis_requires_review(
    source: dict[str, Any],
    target: dict[str, Any],
) -> None:
    assert basis.semantic_alignment(source, target) == "review_required"


def test_available_alignment_ignores_run_and_generation_only() -> None:
    source = _available(
        phase_slug=basis.THEORY_PHASE,
        generation=2,
        run_id="theory-run-002",
    )
    target = _available(
        phase_slug=basis.THEORY_PHASE,
        generation=99,
        run_id="empirical-run-099",
    )

    assert basis.semantic_alignment(source, target) == "exact_match"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["method_identity"].update(
            stable_id="method-b"
        ),
        lambda value: value["method_identity"].update(version="v2"),
        lambda value: value["method_identity"].update(
            definition_sha256="c" * 64
        ),
        lambda value: value["content_reference"].update(
            sha256="d" * 64
        ),
    ],
)
def test_available_alignment_requires_full_identity_and_content(
    mutate: Any,
) -> None:
    source = _available()
    target = copy.deepcopy(source)
    mutate(target)

    assert basis.semantic_alignment(source, target) == "review_required"


@pytest.mark.parametrize(
    ("source_state", "target_state", "expected"),
    [
        ("present", "absent", "not_available"),
        ("absent", "absent", "not_available"),
        ("invalid", "absent", "not_available"),
        ("present", "invalid", "blocked"),
        ("absent", "invalid", "blocked"),
        ("invalid", "invalid", "blocked"),
        ("absent", "present", "review_required"),
        ("invalid", "present", "blocked"),
    ],
)
def test_contextual_alignment_uses_explicit_record_state(
    source_state: str,
    target_state: str,
    expected: str,
) -> None:
    source = _available() if source_state == "present" else None
    target = _available() if target_state == "present" else None

    assert basis.contextual_alignment(
        source,
        target,
        source_record_state=source_state,
        target_record_state=target_state,
    ) == expected


def test_absent_source_is_derived_or_accepted_for_a_present_target() -> None:
    stored_absent = basis.absent_basis(
        phase_slug=basis.THEORY_PHASE,
    )
    explicit_absent = basis.absent_basis(
        phase_slug=basis.THEORY_PHASE,
    )
    stored_available = _available()

    assert basis.contextual_alignment(
        None,
        stored_absent,
        source_record_state="absent",
        target_record_state="present",
    ) == "exact_match"
    assert basis.contextual_alignment(
        explicit_absent,
        stored_absent,
        source_record_state="absent",
        target_record_state="present",
    ) == "exact_match"
    assert basis.contextual_alignment(
        None,
        stored_available,
        source_record_state="absent",
        target_record_state="present",
    ) == "review_required"


def test_present_source_cannot_claim_an_absent_basis() -> None:
    with pytest.raises(
        basis.KnowledgeBasisValidationError,
        match="present source record cannot have an absent basis",
    ):
        basis.contextual_alignment(
            basis.absent_basis(phase_slug=basis.THEORY_PHASE),
            basis.absent_basis(phase_slug=basis.THEORY_PHASE),
            source_record_state="present",
            target_record_state="present",
        )


def test_contextual_alignment_delegates_when_both_records_are_present() -> None:
    source = _available()
    target = _available(
        phase_slug=basis.THEORY_PHASE,
        generation=7,
        run_id="run-007",
    )

    assert basis.contextual_alignment(
        source,
        target,
        source_record_state="present",
        target_record_state="present",
    ) == "exact_match"
    target["content_reference"] = _reference("e" * 64)
    assert basis.contextual_alignment(
        source,
        target,
        source_record_state="present",
        target_record_state="present",
    ) == "review_required"


@pytest.mark.parametrize(
    ("source", "target", "source_state", "target_state"),
    [
        (None, _available(), "present", "present"),
        (_available(), None, "present", "present"),
        (_available(), None, "absent", "absent"),
        (_available(), _available(), "absent", "present"),
        (_available(), _available(), "invalid", "present"),
        (None, None, True, "absent"),
        (None, None, "absent", "missing"),
    ],
)
def test_contextual_alignment_rejects_inconsistent_context(
    source: dict[str, Any] | None,
    target: dict[str, Any] | None,
    source_state: Any,
    target_state: Any,
) -> None:
    with pytest.raises(basis.KnowledgeBasisValidationError):
        basis.contextual_alignment(
            source,
            target,
            source_record_state=source_state,
            target_record_state=target_state,
        )


def test_module_does_not_expose_phase_storage_modules() -> None:
    assert "theory_records" not in basis.__dict__
    assert "empirical_records" not in basis.__dict__
