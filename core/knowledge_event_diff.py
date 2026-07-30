"""Build compact knowledge mutation events from validated phase fragments."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from core import (
    knowledge_event_schema as event_schema,
    knowledge_fragments,
    knowledge_schema,
)


def _fail(message: str, exc: BaseException | None = None) -> None:
    event_schema.fail(message, exc)


def _validated_fragment(
    phase_slug: str,
    payload: bytes,
    evidence_index: Mapping[str, Any] | None,
    *,
    label: str,
) -> dict[str, Any]:
    try:
        raw = knowledge_fragments.parse_fragment(payload, label=label)
        if phase_slug == event_schema.THEORY_PHASE:
            if evidence_index is not None:
                _fail("Phase 3 events do not accept evidence indexes")
            return knowledge_fragments.validate_theory_fragment(
                raw, require_complete=True
            )
        if evidence_index is None:
            _fail("Phase 4 events require an evidence index")
        return knowledge_fragments.validate_empirical_fragment(
            raw, evidence_index, require_complete=True
        )
    except event_schema.KnowledgeEventError:
        raise
    except knowledge_fragments.KnowledgeFragmentError as exc:
        _fail(f"{label} is invalid: {exc}", exc)


def _method_identity(
    value: Mapping[str, Any] | None,
    *,
    label: str,
) -> dict[str, str] | None:
    if value is None:
        return None
    try:
        return knowledge_schema.normalize_method_identity(value)
    except (knowledge_schema.KnowledgeSchemaError, ValueError) as exc:
        _fail(f"{label} is invalid: {exc}", exc)


def _generation(value: int | None, *, label: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= 2_147_483_647:
        _fail(f"{label} must be a positive 32-bit integer")
    return value


def _field_changes(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
    fields: frozenset[str],
) -> list[str]:
    return sorted(
        field for field in fields if previous[field] != current[field]
    )


def _keyed_changes(
    previous_items: Sequence[Mapping[str, Any]],
    current_items: Sequence[Mapping[str, Any]],
    *,
    key_fields: tuple[str, ...],
    comparable_fields: frozenset[str],
) -> list[dict[str, Any]]:
    previous = {
        tuple(str(item[field]) for field in key_fields): item
        for item in previous_items
    }
    current = {
        tuple(str(item[field]) for field in key_fields): item
        for item in current_items
    }
    result: list[dict[str, Any]] = []
    for key in sorted(set(previous) | set(current)):
        identity = dict(zip(key_fields, key))
        if key not in previous:
            result.append({
                **identity,
                "change_type": "added",
                "changed_fields": [],
            })
        elif key not in current:
            result.append({
                **identity,
                "change_type": "removed",
                "changed_fields": [],
            })
        else:
            changed = _field_changes(
                previous[key], current[key], comparable_fields
            )
            if changed:
                result.append({
                    **identity,
                    "change_type": "revised",
                    "changed_fields": changed,
                })
    return result


def _baseline_status(
    supplied: str | None,
    previous_fragment_bytes: bytes | None,
) -> str:
    if supplied is None:
        return (
            "available"
            if previous_fragment_bytes is not None
            else "absent"
        )
    if supplied not in event_schema.BASELINE_STATUSES:
        _fail("previous_baseline_status is unsupported")
    return supplied


def _validate_index_inputs(
    phase_slug: str,
    baseline_status: str,
    previous_evidence_index: Mapping[str, Any] | None,
    current_evidence_index: Mapping[str, Any] | None,
) -> None:
    if phase_slug == event_schema.THEORY_PHASE:
        if (
            previous_evidence_index is not None
            or current_evidence_index is not None
        ):
            _fail("Phase 3 events do not accept evidence indexes")
        return
    if current_evidence_index is None:
        _fail("Phase 4 events require the current evidence index")
    if baseline_status == "available":
        if previous_evidence_index is None:
            _fail("available Phase 4 baseline requires its evidence index")
    elif previous_evidence_index is not None:
        _fail(
            "absent or legacy Phase 4 baseline cannot have an evidence index"
        )


def build_event(
    *,
    phase_slug: str,
    previous_fragment_bytes: bytes | None,
    current_fragment_bytes: bytes,
    previous_evidence_index: Mapping[str, Any] | None = None,
    current_evidence_index: Mapping[str, Any] | None = None,
    previous_baseline_status: str | None = None,
    previous_method_identity: Mapping[str, Any] | None = None,
    previous_generation: int | None = None,
) -> dict[str, Any]:
    """Build one sealed event from exact complete fragment bytes.

    ``legacy_unavailable`` represents a prior canonical package that predates
    structured fragments. Its method identity and generation remain known, but
    no item-level changes are inferred from the unavailable baseline.
    """

    phase_slug = event_schema.normalize_phase_slug(phase_slug)
    if type(current_fragment_bytes) is not bytes:
        _fail("current fragment payload must be bytes")
    if (
        previous_fragment_bytes is not None
        and type(previous_fragment_bytes) is not bytes
    ):
        _fail("previous fragment payload must be bytes or null")
    baseline_status = _baseline_status(
        previous_baseline_status,
        previous_fragment_bytes,
    )
    if baseline_status == "available" and previous_fragment_bytes is None:
        _fail("available baseline requires previous fragment bytes")
    if baseline_status != "available" and previous_fragment_bytes is not None:
        _fail(
            "only an available baseline may provide previous fragment bytes"
        )
    _validate_index_inputs(
        phase_slug,
        baseline_status,
        previous_evidence_index,
        current_evidence_index,
    )

    current = _validated_fragment(
        phase_slug,
        current_fragment_bytes,
        current_evidence_index,
        label="current knowledge fragment",
    )
    previous = (
        _validated_fragment(
            phase_slug,
            previous_fragment_bytes,
            previous_evidence_index,
            label="previous knowledge fragment",
        )
        if baseline_status == "available"
        else None
    )
    supplied_previous_method = _method_identity(
        previous_method_identity,
        label="previous method identity",
    )
    supplied_previous_generation = _generation(
        previous_generation,
        label="previous generation",
    )
    if baseline_status == "absent":
        if (
            supplied_previous_method is not None
            or supplied_previous_generation is not None
        ):
            _fail("absent baseline cannot define previous record fields")
        resolved_previous_method = None
        resolved_previous_generation = None
    elif baseline_status == "available":
        resolved_previous_method = previous["method"]
        resolved_previous_generation = previous["generation"]
        if (
            supplied_previous_method is not None
            and supplied_previous_method != resolved_previous_method
        ):
            _fail(
                "supplied previous method does not match previous fragment"
            )
        if (
            supplied_previous_generation is not None
            and supplied_previous_generation
            != resolved_previous_generation
        ):
            _fail(
                "supplied previous generation does not match previous fragment"
            )
    else:
        if (
            supplied_previous_method is None
            or supplied_previous_generation is None
        ):
            _fail(
                "legacy unavailable baseline requires previous method and "
                "generation"
            )
        resolved_previous_method = supplied_previous_method
        resolved_previous_generation = supplied_previous_generation

    current_method = current["method"]
    current_generation = current["generation"]
    if baseline_status == "absent":
        if current_generation != 1:
            _fail("absent baseline requires current generation 1")
    else:
        if (
            resolved_previous_method["stable_id"]
            != current_method["stable_id"]
        ):
            _fail("knowledge event cannot change the stable method ID")
        if current_generation != resolved_previous_generation + 1:
            _fail("event generation must advance by exactly one")

    statement_changes: list[dict[str, Any]] = []
    dependency_changes: list[dict[str, Any]] = []
    evidence_binding_changes: list[dict[str, Any]] = []
    if baseline_status != "legacy_unavailable":
        statement_changes = _keyed_changes(
            previous["statements"] if previous is not None else [],
            current["statements"],
            key_fields=("statement_id",),
            comparable_fields=event_schema.STATEMENT_FIELDS,
        )
        dependency_changes = _keyed_changes(
            previous["dependencies"] if previous is not None else [],
            current["dependencies"],
            key_fields=(
                "source_statement_id",
                "relation",
                "target_statement_id",
            ),
            comparable_fields=event_schema.DEPENDENCY_FIELDS,
        )
        if phase_slug == event_schema.EMPIRICAL_PHASE:
            evidence_binding_changes = _keyed_changes(
                (
                    previous["evidence_bindings"]
                    if previous is not None
                    else []
                ),
                current["evidence_bindings"],
                key_fields=("evidence_id",),
                comparable_fields=event_schema.EVIDENCE_BINDING_FIELDS,
            )

    unsealed: dict[str, Any] = {
        "schema_version": event_schema.SCHEMA_VERSION,
        "kind": event_schema.EVENT_KIND,
        "event_id": "0" * 64,
        "phase_slug": phase_slug,
        "branch_key": knowledge_schema.branch_key(
            current_method["stable_id"]
        ),
        "previous_baseline_status": baseline_status,
        "previous_method_identity": resolved_previous_method,
        "current_method_identity": current_method,
        "source_run_id": current["source_run_id"],
        "previous_generation": resolved_previous_generation,
        "current_generation": current_generation,
        "previous_fragment_sha256": (
            hashlib.sha256(previous_fragment_bytes).hexdigest()
            if previous_fragment_bytes is not None
            else None
        ),
        "current_fragment_sha256": hashlib.sha256(
            current_fragment_bytes
        ).hexdigest(),
        "statement_changes": statement_changes,
        "dependency_changes": dependency_changes,
        "evidence_binding_changes": evidence_binding_changes,
        "lead_summary": current["lead_summary"],
    }
    unsealed["event_id"] = event_schema.event_id_from_transition(unsealed)
    return event_schema.seal_event(unsealed)
