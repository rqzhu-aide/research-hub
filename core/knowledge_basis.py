"""Strict pure values for cross-phase semantic knowledge alignment.

A basis describes whether one current Phase 3 or Phase 4 package exposes a
stable semantic content reference. It contains no filesystem paths and does
not inspect canonical phase storage.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from core import knowledge_content, knowledge_schema


SCHEMA_VERSION = 1
THEORY_PHASE = knowledge_content.THEORY_PHASE
EMPIRICAL_PHASE = knowledge_content.EMPIRICAL_PHASE
SUPPORTED_PHASES = frozenset({THEORY_PHASE, EMPIRICAL_PHASE})
STATES = frozenset({"available", "absent", "unknown_legacy"})
ALIGNMENT_STATUSES = frozenset({
    "exact_match",
    "review_required",
    "not_available",
    "blocked",
})
RECORD_STATES = frozenset({"present", "absent", "invalid"})
MAX_GENERATION = 2_147_483_647
MAX_RUN_ID_LENGTH = 300

_RUN_ID_RE = re.compile(
    rf"^[A-Za-z0-9][A-Za-z0-9._:-]{{0,{MAX_RUN_ID_LENGTH - 1}}}$"
)
_FIELDS = frozenset({
    "schema_version",
    "phase_slug",
    "state",
    "method_identity",
    "content_reference",
    "generation",
    "source_run_id",
})


class KnowledgeBasisError(ValueError):
    """Base class for an invalid semantic knowledge basis."""


class KnowledgeBasisValidationError(KnowledgeBasisError):
    """A basis or alignment input violates the strict value contract."""


def _fail(message: str, exc: BaseException | None = None) -> None:
    if exc is None:
        raise KnowledgeBasisValidationError(message)
    raise KnowledgeBasisValidationError(message) from exc


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be an object with text field names")
    return value


def _exact_fields(
    value: Mapping[str, Any],
    *,
    label: str,
) -> None:
    actual = frozenset(value)
    if actual == _FIELDS:
        return
    missing = sorted(_FIELDS.difference(actual))
    extra = sorted(actual.difference(_FIELDS))
    details: list[str] = []
    if missing:
        details.append(f"missing {', '.join(missing)}")
    if extra:
        details.append(f"unexpected {', '.join(extra)}")
    _fail(f"{label} has invalid fields: {'; '.join(details)}")


def _phase(value: Any) -> str:
    if type(value) is not str or value not in SUPPORTED_PHASES:
        _fail(
            "phase_slug must be "
            f"{THEORY_PHASE!r} or {EMPIRICAL_PHASE!r}"
        )
    return value


def _method(value: Any) -> dict[str, str]:
    try:
        return knowledge_schema.normalize_method_identity(value)
    except knowledge_schema.KnowledgeSchemaError as exc:
        _fail(f"method_identity is invalid: {exc}", exc)
    raise AssertionError("unreachable")


def _content_reference(value: Any) -> dict[str, Any]:
    try:
        return knowledge_content.validate_content_reference(value)
    except knowledge_content.KnowledgeContentError as exc:
        _fail(f"content_reference is invalid: {exc}", exc)
    raise AssertionError("unreachable")


def _generation(value: Any) -> int:
    if (
        type(value) is not int
        or not 1 <= value <= MAX_GENERATION
    ):
        _fail(
            "generation must be a positive 32-bit integer"
        )
    return value


def _run_id(value: Any) -> str:
    if type(value) is not str or _RUN_ID_RE.fullmatch(value) is None:
        _fail(
            "source_run_id must be a bounded safe identifier"
        )
    return value


def _present_provenance(
    method_identity: Any,
    generation: Any,
    source_run_id: Any,
) -> tuple[dict[str, str], int, str]:
    return (
        _method(method_identity),
        _generation(generation),
        _run_id(source_run_id),
    )


def validate_basis(value: Any) -> dict[str, Any]:
    """Validate and normalize one Phase 3 or Phase 4 basis value."""

    basis = _mapping(value, label="knowledge basis")
    _exact_fields(basis, label="knowledge basis")
    if (
        type(basis["schema_version"]) is not int
        or basis["schema_version"] != SCHEMA_VERSION
    ):
        _fail(
            f"schema_version must be {SCHEMA_VERSION}"
        )
    phase_slug = _phase(basis["phase_slug"])
    state = basis["state"]
    if type(state) is not str or state not in STATES:
        _fail("state is unsupported")

    method_identity = basis["method_identity"]
    content_reference = basis["content_reference"]
    generation = basis["generation"]
    source_run_id = basis["source_run_id"]

    if state == "available":
        if any(
            item is None
            for item in (
                method_identity,
                content_reference,
                generation,
                source_run_id,
            )
        ):
            _fail("available basis requires complete provenance")
        method, normalized_generation, run_id = _present_provenance(
            method_identity,
            generation,
            source_run_id,
        )
        reference = _content_reference(content_reference)
    elif state == "unknown_legacy":
        if content_reference is not None:
            _fail(
                "unknown_legacy basis must not have a content reference"
            )
        provenance = (
            method_identity,
            generation,
            source_run_id,
        )
        present = tuple(item is not None for item in provenance)
        if any(present) and not all(present):
            _fail(
                "unknown_legacy provenance must be all present or all null"
            )
        if all(present):
            method, normalized_generation, run_id = _present_provenance(
                method_identity,
                generation,
                source_run_id,
            )
        else:
            method = None
            normalized_generation = None
            run_id = None
        reference = None
    else:
        if any(
            item is not None
            for item in (
                method_identity,
                content_reference,
                generation,
                source_run_id,
            )
        ):
            _fail("absent basis must not contain provenance")
        method = None
        reference = None
        normalized_generation = None
        run_id = None

    return {
        "schema_version": SCHEMA_VERSION,
        "phase_slug": phase_slug,
        "state": state,
        "method_identity": method,
        "content_reference": reference,
        "generation": normalized_generation,
        "source_run_id": run_id,
    }


def available_basis(
    *,
    phase_slug: str,
    method_identity: Mapping[str, Any],
    content_reference: Mapping[str, Any],
    generation: int,
    source_run_id: str,
) -> dict[str, Any]:
    """Construct an available basis with complete current provenance."""

    return validate_basis({
        "schema_version": SCHEMA_VERSION,
        "phase_slug": phase_slug,
        "state": "available",
        "method_identity": method_identity,
        "content_reference": content_reference,
        "generation": generation,
        "source_run_id": source_run_id,
    })


def unknown_legacy_basis(
    *,
    phase_slug: str,
    method_identity: Mapping[str, Any] | None = None,
    generation: int | None = None,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    """Construct a legacy basis with known or unavailable provenance."""

    return validate_basis({
        "schema_version": SCHEMA_VERSION,
        "phase_slug": phase_slug,
        "state": "unknown_legacy",
        "method_identity": method_identity,
        "content_reference": None,
        "generation": generation,
        "source_run_id": source_run_id,
    })


def absent_basis(*, phase_slug: str) -> dict[str, Any]:
    """Construct a basis that explicitly records no counterpart value."""

    return validate_basis({
        "schema_version": SCHEMA_VERSION,
        "phase_slug": phase_slug,
        "state": "absent",
        "method_identity": None,
        "content_reference": None,
        "generation": None,
        "source_run_id": None,
    })


def semantic_alignment(
    source_basis: Mapping[str, Any],
    target_basis: Mapping[str, Any],
) -> str:
    """Compare two valid basis values without record-existence inference."""

    source = validate_basis(source_basis)
    target = validate_basis(target_basis)
    if source["phase_slug"] != target["phase_slug"]:
        _fail("semantic alignment requires matching phase_slug values")
    if "unknown_legacy" in {source["state"], target["state"]}:
        return "review_required"
    if source["state"] == "absent" and target["state"] == "absent":
        return "exact_match"
    if source["state"] == "absent" or target["state"] == "absent":
        return "review_required"
    if (
        source["method_identity"] == target["method_identity"]
        and source["content_reference"] == target["content_reference"]
    ):
        return "exact_match"
    return "review_required"


def contextual_alignment(
    source_basis: Mapping[str, Any] | None,
    target_basis: Mapping[str, Any] | None,
    *,
    source_record_state: str,
    target_record_state: str,
) -> str:
    """Add explicit record existence and validity to semantic alignment."""

    if (
        type(source_record_state) is not str
        or source_record_state not in RECORD_STATES
        or type(target_record_state) is not str
        or target_record_state not in RECORD_STATES
    ):
        _fail("record state must be present, absent, or invalid")
    if target_record_state == "present":
        if target_basis is None:
            _fail("present target record requires a basis")
        target = validate_basis(target_basis)
    else:
        if target_basis is not None:
            _fail("nonpresent target record must not provide a basis")
        target = None

    if source_record_state == "present":
        if source_basis is None:
            _fail("present source record requires a basis")
        source = validate_basis(source_basis)
        if source["state"] == "absent":
            _fail("present source record cannot have an absent basis")
    elif source_record_state == "invalid":
        if source_basis is not None:
            _fail("invalid source record must not provide a basis")
        source = None
    elif source_basis is None:
        source = (
            absent_basis(phase_slug=target["phase_slug"])
            if target is not None
            else None
        )
    else:
        source = validate_basis(source_basis)
        if source["state"] != "absent":
            _fail("absent source record requires an absent basis")

    if target_record_state == "absent":
        return "not_available"
    if target_record_state == "invalid":
        return "blocked"
    if source_record_state == "invalid":
        return "blocked"
    assert source is not None and target is not None
    return semantic_alignment(source, target)
