"""Stable semantic references for current Phase 3 and Phase 4 knowledge.

The reference identifies scientific content, not a particular run or file.
Callers pass mappings that have already been normalized by the phase package
validators. This module revalidates the bounded scientific contracts before
constructing a deterministic projection.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from core import empirical_schema, knowledge_fragments


SCHEMA_VERSION = 1
THEORY_PHASE = "03-idea-evaluation"
EMPIRICAL_PHASE = "04-draft-assembly"
SUPPORTED_PHASES = frozenset({THEORY_PHASE, EMPIRICAL_PHASE})
MAX_CANONICAL_BYTES = (
    knowledge_fragments.MAX_KNOWLEDGE_BYTES
    + empirical_schema.MAX_INDEX_BYTES
)

_REFERENCE_KEYS = frozenset({"schema_version", "sha256"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SET_LIKE_STATEMENT_FIELDS = frozenset({
    "assumptions",
    "evidential_basis",
    "source_provenance",
    "uncertainty",
})


class KnowledgeContentError(ValueError):
    """Base class for an invalid semantic content reference or source."""


class KnowledgeContentValidationError(KnowledgeContentError):
    """A source or reference violates the bounded semantic contract."""


def _fail(message: str, exc: BaseException | None = None) -> None:
    if exc is None:
        raise KnowledgeContentValidationError(message)
    raise KnowledgeContentValidationError(message) from exc


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        _fail(f"{label} must be an object with text field names")
    return value


def _exact_keys(
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
    _fail(f"{label} has invalid fields: {'; '.join(details)}")


def _without_counterpart_basis(
    value: Any,
    *,
    label: str,
) -> dict[str, Any]:
    """Exclude the reserved cross-phase basis metadata from the projection."""

    source = _mapping(value, label=label)
    return {
        key: item
        for key, item in source.items()
        if key != "counterpart_basis"
    }


def validate_content_reference(value: Any) -> dict[str, Any]:
    """Validate and normalize one versioned semantic content reference."""

    reference = _mapping(value, label="knowledge content reference")
    _exact_keys(
        reference,
        _REFERENCE_KEYS,
        label="knowledge content reference",
    )
    if (
        type(reference["schema_version"]) is not int
        or reference["schema_version"] != SCHEMA_VERSION
    ):
        _fail(
            "knowledge content reference schema_version must be "
            f"{SCHEMA_VERSION}"
        )
    digest = reference["sha256"]
    if type(digest) is not str or _SHA256_RE.fullmatch(digest) is None:
        _fail(
            "knowledge content reference sha256 must be a lowercase "
            "SHA-256 digest"
        )
    return {"schema_version": SCHEMA_VERSION, "sha256": digest}


def _statement_projection(statement: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(statement)
    for field in _SET_LIKE_STATEMENT_FIELDS:
        result[field] = sorted(result[field])
    return result


def _common_projection(fragment: Mapping[str, Any]) -> dict[str, Any]:
    statements = sorted(
        (
            _statement_projection(statement)
            for statement in fragment["statements"]
        ),
        key=lambda item: item["statement_id"],
    )
    dependencies = sorted(
        (dict(dependency) for dependency in fragment["dependencies"]),
        key=lambda item: (
            item["source_statement_id"],
            item["relation"],
            item["target_statement_id"],
        ),
    )
    return {
        "method": dict(fragment["method"]),
        "statements": statements,
        "dependencies": dependencies,
    }


def _validate_empirical_index(
    value: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Validate normalized index shape and return its material entries."""

    index = _without_counterpart_basis(
        value,
        label="normalized empirical evidence index",
    )
    try:
        empirical_schema.exact_keys(
            index,
            empirical_schema.LEGACY_INDEX_KEYS,
            label="normalized empirical evidence index",
        )
        if (
            type(index["schema_version"]) is not int
            or index["schema_version"]
            not in {
                empirical_schema.LEGACY_INDEX_SCHEMA_VERSION,
                empirical_schema.COUNTERPART_INDEX_SCHEMA_VERSION,
                empirical_schema.INDEX_SCHEMA_VERSION,
            }
        ):
            empirical_schema.fail(
                "normalized empirical evidence index schema_version is "
                "unsupported"
            )
        if index["kind"] != empirical_schema.INDEX_KIND:
            empirical_schema.fail(
                "normalized empirical evidence index kind must be "
                f"{empirical_schema.INDEX_KIND!r}"
            )

        synthesis = empirical_schema.mapping(
            index["synthesis"],
            label="normalized empirical evidence index synthesis",
        )
        empirical_schema.exact_keys(
            synthesis,
            empirical_schema.SYNTHESIS_KEYS,
            label="normalized empirical evidence index synthesis",
        )
        if synthesis["path"] != empirical_schema.SYNTHESIS_FILENAME:
            empirical_schema.fail(
                "normalized empirical evidence index synthesis path is invalid"
            )
        empirical_schema.sha256(
            synthesis["sha256"],
            label="normalized empirical evidence index synthesis sha256",
        )
        empirical_schema.integer(
            synthesis["size"],
            label="normalized empirical evidence index synthesis size",
            minimum=1,
            maximum=empirical_schema.MAX_SYNTHESIS_BYTES,
        )

        raw_entries = index["entries"]
        if (
            not isinstance(raw_entries, list)
            or len(raw_entries) > empirical_schema.MAX_EVIDENCE_ENTRIES
        ):
            empirical_schema.fail(
                "normalized empirical evidence index entries must be a "
                "bounded list"
            )
        entries: list[dict[str, Any]] = []
        normalized_entries: list[dict[str, Any]] = []
        for number, raw_entry in enumerate(raw_entries, start=1):
            label = f"normalized empirical evidence entry {number}"
            entry = empirical_schema.mapping(raw_entry, label=label)
            entry_fields = frozenset(entry)
            if entry_fields not in {
                empirical_schema.ENTRY_KEYS,
                empirical_schema.NORMALIZED_ENTRY_KEYS,
            }:
                empirical_schema.fail(f"{label} has invalid fields")
            evidence_id = empirical_schema.text(
                entry["evidence_id"],
                label=f"{label} evidence_id",
                maximum=200,
                pattern=empirical_schema.IDENTIFIER_RE,
            )
            evidence_type = empirical_schema.text(
                entry["type"],
                label=f"{label} type",
                maximum=50,
            )
            if evidence_type not in empirical_schema.EVIDENCE_TYPES:
                empirical_schema.fail(f"{label} type is unsupported")
            empirical_schema.text(
                entry["path"],
                label=f"{label} path",
                maximum=empirical_schema.MAX_PATH_LENGTH,
            )
            artifact_sha256 = empirical_schema.sha256(
                entry["sha256"],
                label=f"{label} sha256",
            )
            empirical_schema.integer(
                entry["size"],
                label=f"{label} size",
                minimum=0,
                maximum=empirical_schema.MAX_CURRENT_ARTIFACT_BYTES,
            )
            empirical_schema.text(
                entry["source_run_id"],
                label=f"{label} source_run_id",
                maximum=200,
                pattern=empirical_schema.IDENTIFIER_RE,
            )
            run_scope = empirical_schema.text(
                entry["run_scope"],
                label=f"{label} run_scope",
                maximum=20,
            )
            if run_scope not in empirical_schema.RUN_SCOPES:
                empirical_schema.fail(f"{label} run_scope is unsupported")
            status = empirical_schema.text(
                entry["status"],
                label=f"{label} status",
                maximum=20,
            )
            if status not in empirical_schema.EVIDENCE_STATUSES:
                empirical_schema.fail(f"{label} status is unsupported")
            status_reason = empirical_schema.text(
                entry["status_reason"],
                label=f"{label} status_reason",
                maximum=empirical_schema.MAX_REASON_LENGTH,
            )
            method_dependent = entry["method_dependent"]
            if type(method_dependent) is not bool:
                empirical_schema.fail(
                    f"{label} method_dependent must be true or false"
                )
            if (
                index["schema_version"] == empirical_schema.INDEX_SCHEMA_VERSION
                and evidence_type in empirical_schema.VERSION_BOUND_TYPES
                and method_dependent is False
            ):
                empirical_schema.fail(
                    f"{label} must be bound to the exact method version"
                )
            effective_method_dependent = (
                method_dependent
                or evidence_type in empirical_schema.VERSION_BOUND_TYPES
            )
            applicability = empirical_schema.derived_entry_applicability({
                "type": evidence_type,
                "status": status,
                "method_dependent": effective_method_dependent,
            })
            if entry_fields == empirical_schema.NORMALIZED_ENTRY_KEYS and any(
                entry[field] != value
                for field, value in applicability.items()
            ):
                empirical_schema.fail(
                    f"{label} applicability fields are inconsistent"
                )
            normalized_entry = dict(entry)
            normalized_entry["method_dependent"] = effective_method_dependent
            normalized_entry.update(applicability)
            normalized_entries.append(normalized_entry)
            entries.append({
                "evidence_id": evidence_id,
                "type": evidence_type,
                "sha256": artifact_sha256,
                "run_scope": run_scope,
                "status": status,
                "status_reason": status_reason,
                "method_dependent": effective_method_dependent,
            })
        index["entries"] = normalized_entries
        return index, entries
    except empirical_schema.EmpiricalRecordError as exc:
        _fail(str(exc), exc)
    raise AssertionError("unreachable")


def _empirical_projection(
    fragment: Mapping[str, Any],
    evidence_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    result = _common_projection(fragment)
    result["evidence_bindings"] = sorted(
        (
            {
                "evidence_id": binding["evidence_id"],
                "evidence_status": binding["evidence_status"],
                "role": binding["role"],
                "assessments": sorted(
                    (dict(item) for item in binding["assessments"]),
                    key=lambda item: (
                        item["statement_id"],
                        item["relation"],
                    ),
                ),
            }
            for binding in fragment["evidence_bindings"]
        ),
        key=lambda item: item["evidence_id"],
    )
    result["evidence_entries"] = sorted(
        evidence_entries,
        key=lambda item: item["evidence_id"],
    )
    return result


def _canonical_digest(value: Mapping[str, Any]) -> str:
    try:
        payload = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail(f"knowledge content is not canonical JSON: {exc}", exc)
    if not 1 <= len(payload) <= MAX_CANONICAL_BYTES:
        _fail(
            "canonical knowledge content exceeds the bounded byte limit"
        )
    return hashlib.sha256(payload).hexdigest()


def build_content_reference(
    *,
    phase_slug: str,
    fragment: Mapping[str, Any],
    evidence_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable reference to the supplied scientific content."""

    if type(phase_slug) is not str or phase_slug not in SUPPORTED_PHASES:
        _fail(
            "phase_slug must be "
            f"{THEORY_PHASE!r} or {EMPIRICAL_PHASE!r}"
        )
    source = _without_counterpart_basis(
        fragment,
        label="normalized knowledge fragment",
    )
    expected_kind = (
        knowledge_fragments.THEORY_KIND
        if phase_slug == THEORY_PHASE
        else knowledge_fragments.EMPIRICAL_KIND
    )
    if source.get("kind") != expected_kind:
        _fail(
            f"{phase_slug} knowledge fragment kind must be "
            f"{expected_kind!r}"
        )
    try:
        if phase_slug == THEORY_PHASE:
            if evidence_index is not None:
                _fail("Phase 3 content must not include an evidence index")
            normalized = knowledge_fragments.validate_theory_fragment(
                source,
                require_complete=False,
            )
            projection = _common_projection(normalized)
        else:
            if evidence_index is None:
                _fail("Phase 4 content requires an evidence index")
            normalized_index, evidence_entries = _validate_empirical_index(
                evidence_index
            )
            normalized = knowledge_fragments.validate_empirical_fragment(
                source,
                normalized_index,
                require_complete=False,
            )
            projection = _empirical_projection(
                normalized,
                evidence_entries,
            )
    except knowledge_fragments.KnowledgeFragmentError as exc:
        _fail(str(exc), exc)

    return {
        "schema_version": SCHEMA_VERSION,
        "sha256": _canonical_digest(projection),
    }
