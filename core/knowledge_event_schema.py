"""Strict schema and canonical encoding for knowledge mutation events."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from core import knowledge_fragments, knowledge_schema


SCHEMA_VERSION = 1
EVENT_KIND = "knowledge_mutation_event"
THEORY_PHASE = "03-idea-evaluation"
EMPIRICAL_PHASE = "04-draft-assembly"
SUPPORTED_PHASES = frozenset({THEORY_PHASE, EMPIRICAL_PHASE})
BASELINE_STATUSES = frozenset({
    "absent",
    "available",
    "legacy_unavailable",
})

MAX_EVENT_BYTES = 4 * 1024 * 1024
MAX_STATEMENT_CHANGES = 2 * knowledge_fragments.MAX_STATEMENTS
MAX_DEPENDENCY_CHANGES = 2 * knowledge_fragments.MAX_DEPENDENCIES
MAX_EVIDENCE_BINDING_CHANGES = (
    2 * knowledge_fragments.MAX_EVIDENCE_BINDINGS
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_CHANGE_TYPES = frozenset({"added", "revised", "removed"})
_SUMMARY_FIELDS = frozenset({
    "fundamental_points",
    "decision_relevant_changes",
    "unresolved_questions",
})
STATEMENT_FIELDS = frozenset({
    "statement_type",
    "wording",
    "scope",
    "formulation_state",
    "assessment_status",
    "evidential_basis",
    "source_provenance",
    "assumptions",
    "uncertainty",
    "logical_status",
    "mathematical_result_type",
})
DEPENDENCY_FIELDS = frozenset({"reason"})
EVIDENCE_BINDING_FIELDS = frozenset({
    "evidence_status",
    "role",
    "assessments",
})
_UNSEALED_FIELDS = frozenset({
    "schema_version",
    "kind",
    "event_id",
    "phase_slug",
    "branch_key",
    "previous_baseline_status",
    "previous_method_identity",
    "current_method_identity",
    "source_run_id",
    "previous_generation",
    "current_generation",
    "previous_fragment_sha256",
    "current_fragment_sha256",
    "statement_changes",
    "dependency_changes",
    "evidence_binding_changes",
    "lead_summary",
})
_SEALED_FIELDS = _UNSEALED_FIELDS | {"event_sha256"}


class KnowledgeEventError(ValueError):
    """Base class for invalid or unsafe knowledge mutation events."""


class KnowledgeEventValidationError(KnowledgeEventError):
    """An event or source transition violates the bounded contract."""


class KnowledgeEventConflict(KnowledgeEventError):
    """An immutable event path already contains different bytes."""


def fail(message: str, exc: BaseException | None = None) -> None:
    """Raise one stable schema error, optionally preserving its cause."""

    if exc is None:
        raise KnowledgeEventValidationError(message)
    raise KnowledgeEventValidationError(message) from exc


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        fail(f"{label} must be an object with text field names")
    return value


def _exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    actual = frozenset(value)
    if actual == expected:
        return
    missing = sorted(expected.difference(actual))
    extra = sorted(actual.difference(expected))
    details: list[str] = []
    if missing:
        details.append(f"missing {', '.join(missing)}")
    if extra:
        details.append(f"unexpected {', '.join(extra)}")
    fail(f"{label} has invalid fields: {'; '.join(details)}")


def _text(
    value: Any,
    *,
    label: str,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if type(value) is not str:
        fail(f"{label} must be text")
    if not value.strip() or len(value) > maximum or "\x00" in value:
        fail(f"{label} must contain between 1 and {maximum} safe characters")
    if pattern is not None and pattern.fullmatch(value) is None:
        fail(f"{label} has an invalid format")
    return value


def normalize_digest(value: Any, *, label: str) -> str:
    """Normalize one lowercase SHA-256 digest."""

    return _text(value, label=label, maximum=64, pattern=_SHA256_RE)


def normalize_phase_slug(value: Any) -> str:
    """Accept only the two phases that own knowledge mutation events."""

    if value not in SUPPORTED_PHASES:
        fail(
            "phase_slug must be "
            f"{THEORY_PHASE!r} or {EMPIRICAL_PHASE!r}"
        )
    return str(value)


def _generation(value: Any, *, label: str) -> int:
    if type(value) is not int or not 1 <= value <= 2_147_483_647:
        fail(f"{label} must be a positive 32-bit integer")
    return value


def _method(value: Any, *, label: str) -> dict[str, str]:
    try:
        return knowledge_schema.normalize_method_identity(value)
    except (knowledge_schema.KnowledgeSchemaError, ValueError) as exc:
        fail(f"{label} is invalid: {exc}", exc)


def canonical_fingerprint(value: Any) -> str:
    """Return the SHA-256 digest of canonical compact JSON."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _summary(value: Any) -> dict[str, list[str]]:
    source = _mapping(value, label="knowledge event lead_summary")
    _exact_fields(
        source,
        _SUMMARY_FIELDS,
        label="knowledge event lead_summary",
    )
    result: dict[str, list[str]] = {}
    for field in sorted(_SUMMARY_FIELDS):
        items = source[field]
        if (
            not isinstance(items, list)
            or len(items) > knowledge_fragments.MAX_SUMMARY_ITEMS
        ):
            fail(
                f"knowledge event lead_summary {field} must be a bounded list"
            )
        normalized = [
            _text(
                item,
                label=f"knowledge event lead_summary {field}[{number}]",
                maximum=knowledge_fragments.MAX_LIST_TEXT_LENGTH,
            )
            for number, item in enumerate(items)
        ]
        if len(set(normalized)) != len(normalized):
            fail(
                f"knowledge event lead_summary {field} has duplicate items"
            )
        result[field] = normalized
    return result


def _identifier(value: Any, *, label: str) -> str:
    return _text(
        value,
        label=label,
        maximum=knowledge_fragments.MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_RE,
    )


def _change_type(value: Any, *, label: str) -> str:
    if value not in _CHANGE_TYPES:
        fail(f"{label} has an unsupported change_type")
    return str(value)


def _changed_fields(
    value: Any,
    *,
    label: str,
    allowed: frozenset[str],
    change_type: str,
) -> list[str]:
    if not isinstance(value, list) or any(
        type(item) is not str for item in value
    ):
        fail(f"{label} changed_fields must be a list of field names")
    normalized = sorted(value)
    if normalized != value or len(set(normalized)) != len(normalized):
        fail(f"{label} changed_fields must be sorted and unique")
    extra = sorted(set(normalized).difference(allowed))
    if extra:
        fail(
            f"{label} changed_fields has unsupported fields: "
            + ", ".join(extra)
        )
    if change_type == "revised" and not normalized:
        fail(f"{label} revised change must name a changed field")
    if change_type != "revised" and normalized:
        fail(f"{label} added or removed change cannot name changed fields")
    return normalized


def _simple_changes(
    value: Any,
    *,
    collection_label: str,
    item_label: str,
    key_field: str,
    allowed_fields: frozenset[str],
    maximum: int,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > maximum:
        fail(f"{collection_label} must contain at most {maximum} items")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected = frozenset({key_field, "change_type", "changed_fields"})
    for number, item in enumerate(value, start=1):
        label = f"{item_label} {number}"
        source = _mapping(item, label=label)
        _exact_fields(source, expected, label=label)
        identity = _identifier(
            source[key_field], label=f"{label} {key_field}"
        )
        if identity in seen:
            fail(f"duplicate {item_label} for {identity!r}")
        seen.add(identity)
        change_type = _change_type(source["change_type"], label=label)
        result.append({
            key_field: identity,
            "change_type": change_type,
            "changed_fields": _changed_fields(
                source["changed_fields"],
                label=label,
                allowed=allowed_fields,
                change_type=change_type,
            ),
        })
    result.sort(key=lambda item: item[key_field])
    if result != value:
        fail(f"{collection_label} must use canonical key order")
    return result


def _statement_changes(value: Any) -> list[dict[str, Any]]:
    return _simple_changes(
        value,
        collection_label="statement_changes",
        item_label="statement change",
        key_field="statement_id",
        allowed_fields=STATEMENT_FIELDS,
        maximum=MAX_STATEMENT_CHANGES,
    )


def _evidence_changes(value: Any) -> list[dict[str, Any]]:
    return _simple_changes(
        value,
        collection_label="evidence_binding_changes",
        item_label="evidence binding change",
        key_field="evidence_id",
        allowed_fields=EVIDENCE_BINDING_FIELDS,
        maximum=MAX_EVIDENCE_BINDING_CHANGES,
    )


def _dependency_changes(value: Any) -> list[dict[str, Any]]:
    if (
        not isinstance(value, list)
        or len(value) > MAX_DEPENDENCY_CHANGES
    ):
        fail(
            f"dependency_changes must contain at most "
            f"{MAX_DEPENDENCY_CHANGES} items"
        )
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    expected = frozenset({
        "source_statement_id",
        "relation",
        "target_statement_id",
        "change_type",
        "changed_fields",
    })
    for number, item in enumerate(value, start=1):
        label = f"dependency change {number}"
        source = _mapping(item, label=label)
        _exact_fields(source, expected, label=label)
        source_id = _identifier(
            source["source_statement_id"],
            label=f"{label} source_statement_id",
        )
        relation = _text(
            source["relation"], label=f"{label} relation", maximum=50
        )
        if relation not in knowledge_fragments.DEPENDENCY_RELATIONS:
            fail(f"{label} relation is unsupported")
        target_id = _identifier(
            source["target_statement_id"],
            label=f"{label} target_statement_id",
        )
        identity = (source_id, relation, target_id)
        if identity in seen:
            fail(f"duplicate dependency change for {identity!r}")
        seen.add(identity)
        change_type = _change_type(source["change_type"], label=label)
        result.append({
            "source_statement_id": source_id,
            "relation": relation,
            "target_statement_id": target_id,
            "change_type": change_type,
            "changed_fields": _changed_fields(
                source["changed_fields"],
                label=label,
                allowed=DEPENDENCY_FIELDS,
                change_type=change_type,
            ),
        })
    result.sort(
        key=lambda item: (
            item["source_statement_id"],
            item["relation"],
            item["target_statement_id"],
        )
    )
    if result != value:
        fail("dependency_changes must use canonical key order")
    return result


_IDENTITY_FIELDS = (
    "schema_version",
    "kind",
    "phase_slug",
    "branch_key",
    "previous_baseline_status",
    "previous_method_identity",
    "current_method_identity",
    "source_run_id",
    "previous_generation",
    "current_generation",
    "previous_fragment_sha256",
    "current_fragment_sha256",
)


def event_id_from_transition(value: Mapping[str, Any]) -> str:
    """Derive the deterministic ID from immutable transition identity."""

    return canonical_fingerprint({
        key: value[key] for key in _IDENTITY_FIELDS
    })


def _normalize_unsealed(value: Any) -> dict[str, Any]:
    source = _mapping(value, label="knowledge event")
    _exact_fields(source, _UNSEALED_FIELDS, label="knowledge event")
    if (
        type(source["schema_version"]) is not int
        or source["schema_version"] != SCHEMA_VERSION
    ):
        fail(f"knowledge event schema_version must be {SCHEMA_VERSION}")
    if source["kind"] != EVENT_KIND:
        fail(f"knowledge event kind must be {EVENT_KIND!r}")

    phase_slug = normalize_phase_slug(source["phase_slug"])
    current_method = _method(
        source["current_method_identity"],
        label="current method identity",
    )
    previous_raw = source["previous_method_identity"]
    previous_method = (
        None
        if previous_raw is None
        else _method(previous_raw, label="previous method identity")
    )
    branch_key = normalize_digest(
        source["branch_key"], label="knowledge event branch_key"
    )
    if branch_key != knowledge_schema.branch_key(
        current_method["stable_id"]
    ):
        fail("knowledge event branch_key does not match the current method")

    baseline_status = source["previous_baseline_status"]
    if baseline_status not in BASELINE_STATUSES:
        fail("previous_baseline_status is unsupported")
    baseline_status = str(baseline_status)
    current_generation = _generation(
        source["current_generation"], label="current_generation"
    )
    previous_generation = source["previous_generation"]
    previous_fragment = source["previous_fragment_sha256"]
    if baseline_status == "absent":
        if (
            previous_generation is not None
            or previous_method is not None
            or previous_fragment is not None
        ):
            fail("absent baseline cannot define previous record fields")
        if current_generation != 1:
            fail("absent baseline requires current_generation 1")
    else:
        previous_generation = _generation(
            previous_generation, label="previous_generation"
        )
        if previous_method is None:
            fail("later event must define previous method identity")
        if previous_method["stable_id"] != current_method["stable_id"]:
            fail("knowledge event cannot change the stable method ID")
        if current_generation != previous_generation + 1:
            fail("event generation must advance by exactly one")
        if baseline_status == "available":
            if previous_fragment is None:
                fail("available baseline must define previous fragment digest")
            previous_fragment = normalize_digest(
                previous_fragment,
                label="previous_fragment_sha256",
            )
        elif previous_fragment is not None:
            fail("legacy unavailable baseline cannot define a fragment digest")

    normalized = {
        "schema_version": SCHEMA_VERSION,
        "kind": EVENT_KIND,
        "event_id": normalize_digest(source["event_id"], label="event_id"),
        "phase_slug": phase_slug,
        "branch_key": branch_key,
        "previous_baseline_status": baseline_status,
        "previous_method_identity": previous_method,
        "current_method_identity": current_method,
        "source_run_id": _identifier(
            source["source_run_id"], label="source_run_id"
        ),
        "previous_generation": previous_generation,
        "current_generation": current_generation,
        "previous_fragment_sha256": previous_fragment,
        "current_fragment_sha256": normalize_digest(
            source["current_fragment_sha256"],
            label="current_fragment_sha256",
        ),
        "statement_changes": _statement_changes(
            source["statement_changes"]
        ),
        "dependency_changes": _dependency_changes(
            source["dependency_changes"]
        ),
        "evidence_binding_changes": _evidence_changes(
            source["evidence_binding_changes"]
        ),
        "lead_summary": _summary(source["lead_summary"]),
    }
    if baseline_status == "legacy_unavailable" and any((
        normalized["statement_changes"],
        normalized["dependency_changes"],
        normalized["evidence_binding_changes"],
    )):
        fail(
            "legacy unavailable baseline cannot claim item-level changes"
        )
    if phase_slug == THEORY_PHASE and normalized[
        "evidence_binding_changes"
    ]:
        fail("Phase 3 events cannot contain evidence binding changes")
    expected_id = event_id_from_transition(normalized)
    if not hmac.compare_digest(normalized["event_id"], expected_id):
        fail("event_id does not match the transition identity")
    return normalized


def seal_event(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an unsealed event and add its deterministic fingerprint."""

    normalized = _normalize_unsealed(value)
    return {
        **normalized,
        "event_sha256": canonical_fingerprint(normalized),
    }


def validate_event(value: Any) -> dict[str, Any]:
    """Validate and normalize one sealed event."""

    source = _mapping(value, label="knowledge event")
    _exact_fields(source, _SEALED_FIELDS, label="knowledge event")
    supplied = normalize_digest(
        source["event_sha256"], label="event_sha256"
    )
    normalized = _normalize_unsealed({
        key: item for key, item in source.items() if key != "event_sha256"
    })
    expected = canonical_fingerprint(normalized)
    if not hmac.compare_digest(supplied, expected):
        fail("event_sha256 does not match the event content")
    return {**normalized, "event_sha256": expected}


def event_bytes(value: Any) -> bytes:
    """Return deterministic bounded JSON bytes for one sealed event."""

    normalized = validate_event(value)
    payload = (
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_EVENT_BYTES:
        fail(f"knowledge event exceeds {MAX_EVENT_BYTES} bytes")
    return payload


def _unique_object(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in pairs:
        if key in result:
            fail(f"knowledge event contains duplicate field {key!r}")
        result[key] = item
    return result


def parse_event_bytes(payload: bytes) -> dict[str, Any]:
    """Parse bounded UTF-8 JSON and validate one sealed event."""

    if type(payload) is not bytes:
        fail("knowledge event payload must be bytes")
    if not payload or len(payload) > MAX_EVENT_BYTES:
        fail(f"knowledge event must contain 1 to {MAX_EVENT_BYTES} bytes")
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("knowledge event is not valid UTF-8", exc)
    try:
        value = json.loads(
            source,
            object_pairs_hook=_unique_object,
            parse_constant=lambda constant: fail(
                f"knowledge event has invalid numeric value {constant!r}"
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, KnowledgeEventError):
            raise
        fail(f"knowledge event is not valid JSON: {exc}", exc)
    return validate_event(value)
