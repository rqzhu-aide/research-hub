"""Strict schemas for phase-owned scientific knowledge fragments.

Knowledge fragments are small structured companions to the canonical Phase 3
and Phase 4 scientific packages.  They do not replace those packages.  This
module validates only the fragment contract and, for Phase 4, its exact
relationship to an already normalized empirical evidence index.

The import of ``project_state`` is deliberately lazy.  Its controlled
scientific-record vocabulary remains authoritative without making this schema
module part of project-state initialization.
"""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.filesystem_utils import metadata_is_link_or_reparse


KNOWLEDGE_FILENAME = "knowledge-fragment.json"
SCHEMA_VERSION = 1

THEORY_KIND = "theory_knowledge_fragment"
THEORY_SEMANTICS = "complete_replacement"
EMPIRICAL_KIND = "empirical_knowledge_fragment"
EMPIRICAL_SEMANTICS = "cumulative_evidence"

COVERAGE_VALUES = frozenset({"draft", "complete"})
DEPENDENCY_RELATIONS = frozenset({
    "assumes",
    "contradicts",
    "depends_on",
    "implies",
    "qualifies",
    "tests",
})
EVIDENCE_ROLES = frozenset({
    "diagnostic",
    "documentation",
    "implementation",
    "protocol",
    "scientific_result",
})
EVIDENCE_RELATIONS = frozenset({
    "contradicts",
    "implements",
    "qualifies",
    "supports",
    "tests",
})
EVIDENCE_STATUSES = frozenset({
    "current",
    "outdated",
    "superseded",
    "unresolved",
    "withdrawn",
})

MAX_KNOWLEDGE_BYTES = 4 * 1024 * 1024
MAX_STATEMENTS = 500
MAX_DEPENDENCIES = 2_000
MAX_EVIDENCE_BINDINGS = 2_000
MAX_ASSESSMENTS_PER_EVIDENCE = 50
MAX_SUMMARY_ITEMS = 20
MAX_LIST_ITEMS = 12
MAX_IDENTIFIER_LENGTH = 200
MAX_TEXT_LENGTH = 4_000
MAX_LIST_TEXT_LENGTH = 2_000

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_METHOD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,199}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_METHOD_KEYS = frozenset({"stable_id", "version", "definition_sha256"})
_SUMMARY_KEYS = frozenset({
    "fundamental_points",
    "decision_relevant_changes",
    "unresolved_questions",
})
_STATEMENT_KEYS = frozenset({
    "statement_id",
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
_LIST_STATEMENT_FIELDS = frozenset({
    "evidential_basis",
    "source_provenance",
    "assumptions",
    "uncertainty",
})
_DEPENDENCY_KEYS = frozenset({
    "source_statement_id",
    "relation",
    "target_statement_id",
    "reason",
})
_ASSESSMENT_KEYS = frozenset({
    "statement_id",
    "relation",
    "interpretation",
})
_EVIDENCE_BINDING_KEYS = frozenset({
    "evidence_id",
    "evidence_status",
    "role",
    "assessments",
})
_COMMON_KEYS = frozenset({
    "schema_version",
    "kind",
    "semantics",
    "coverage",
    "method",
    "generation",
    "source_run_id",
    "statements",
    "dependencies",
    "lead_summary",
})
_THEORY_KEYS = _COMMON_KEYS
_EMPIRICAL_KEYS = _COMMON_KEYS | {"evidence_bindings"}


class KnowledgeFragmentError(ValueError):
    """Base class for an unsafe or invalid scientific knowledge fragment."""


class KnowledgeFragmentValidationError(KnowledgeFragmentError):
    """A knowledge fragment does not satisfy its bounded schema."""


def _fail(message: str, exc: BaseException | None = None) -> None:
    if exc is None:
        raise KnowledgeFragmentValidationError(message)
    raise KnowledgeFragmentValidationError(message) from exc


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


def _text(
    value: Any,
    *,
    label: str,
    maximum: int = MAX_TEXT_LENGTH,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if type(value) is not str:
        _fail(f"{label} must be text")
    if not value.strip() or len(value) > maximum or "\x00" in value:
        _fail(f"{label} must contain between 1 and {maximum} safe characters")
    if pattern is not None and pattern.fullmatch(value) is None:
        _fail(f"{label} has an invalid format")
    return value


def _identifier(value: Any, *, label: str) -> str:
    return _text(
        value,
        label=label,
        maximum=MAX_IDENTIFIER_LENGTH,
        pattern=_IDENTIFIER_RE,
    )


def _integer(value: Any, *, label: str) -> int:
    if (
        type(value) is not int
        or value < 1
        or value > 2_147_483_647
    ):
        _fail(f"{label} must be a positive 32-bit integer")
    return value


def _string_list(
    value: Any,
    *,
    label: str,
    maximum_items: int,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(value, list):
        _fail(f"{label} must be a list")
    minimum = 0 if allow_empty else 1
    if not minimum <= len(value) <= maximum_items:
        _fail(
            f"{label} must contain {minimum} to {maximum_items} items"
        )
    normalized = [
        _text(
            item,
            label=f"{label}[{index}]",
            maximum=MAX_LIST_TEXT_LENGTH,
        )
        for index, item in enumerate(value)
    ]
    if len(set(normalized)) != len(normalized):
        _fail(f"{label} must not contain duplicate items")
    return normalized


def _normalize_method(value: Any, *, label: str) -> dict[str, str]:
    method = _mapping(value, label=label)
    _exact_keys(method, _METHOD_KEYS, label=label)
    digest = _text(
        method["definition_sha256"],
        label=f"{label} definition_sha256",
        maximum=64,
        pattern=_SHA256_RE,
    )
    return {
        "stable_id": _text(
            method["stable_id"],
            label=f"{label} stable_id",
            maximum=MAX_IDENTIFIER_LENGTH,
            pattern=_METHOD_ID_RE,
        ),
        "version": _text(
            method["version"],
            label=f"{label} version",
            maximum=MAX_IDENTIFIER_LENGTH,
            pattern=_VERSION_RE,
        ),
        "definition_sha256": digest,
    }


def _scientific_vocabularies() -> dict[str, frozenset[str]]:
    """Load the existing controlled vocabulary without an import-time cycle."""

    from core import project_state

    return {
        "statement_type": project_state.STATEMENT_TYPES,
        "formulation_state": project_state.FORMULATION_STATES,
        "assessment_status": project_state.ASSESSMENT_STATUSES,
        "logical_status": project_state.LOGICAL_STATUSES,
        "mathematical_result_type": project_state.MATHEMATICAL_RESULT_TYPES,
    }


def _normalize_statement(
    value: Any,
    *,
    number: int,
    complete: bool,
) -> dict[str, Any]:
    label = f"knowledge statement {number}"
    statement = _mapping(value, label=label)
    _exact_keys(statement, _STATEMENT_KEYS, label=label)
    vocabularies = _scientific_vocabularies()

    normalized: dict[str, Any] = {
        "statement_id": _identifier(
            statement["statement_id"], label=f"{label} statement_id"
        )
    }
    for field in (
        "statement_type",
        "wording",
        "scope",
        "formulation_state",
        "assessment_status",
        "logical_status",
        "mathematical_result_type",
    ):
        normalized[field] = _text(
            statement[field], label=f"{label} {field}"
        )
    for field in _LIST_STATEMENT_FIELDS:
        normalized[field] = _string_list(
            statement[field],
            label=f"{label} {field}",
            maximum_items=MAX_LIST_ITEMS,
            allow_empty=False,
        )

    for field, allowed in vocabularies.items():
        if normalized[field] not in allowed:
            _fail(
                f"{label} {field} must be one of "
                + ", ".join(sorted(allowed))
            )
    if complete and normalized["formulation_state"] != "Current":
        _fail(
            f"{label} in a complete fragment must have formulation_state Current"
        )
    return normalized


def _normalize_statements(
    value: Any,
    *,
    complete: bool,
) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(value, list) or len(value) > MAX_STATEMENTS:
        _fail(
            f"knowledge fragment statements must be a list with at most "
            f"{MAX_STATEMENTS} items"
        )
    if complete and not value:
        _fail(
            "complete knowledge fragment must contain at least one current statement"
        )
    normalized: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for number, raw_statement in enumerate(value, start=1):
        statement = _normalize_statement(
            raw_statement, number=number, complete=complete
        )
        statement_id = statement["statement_id"]
        if statement_id in identifiers:
            _fail(f"duplicate knowledge statement_id {statement_id!r}")
        identifiers.add(statement_id)
        normalized.append(statement)
    return normalized, identifiers


def _normalize_dependencies(
    value: Any,
    *,
    local_statement_ids: set[str],
) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > MAX_DEPENDENCIES:
        _fail(
            f"knowledge fragment dependencies must be a list with at most "
            f"{MAX_DEPENDENCIES} items"
        )
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for number, raw_dependency in enumerate(value, start=1):
        label = f"knowledge dependency {number}"
        dependency = _mapping(raw_dependency, label=label)
        _exact_keys(dependency, _DEPENDENCY_KEYS, label=label)
        source = _identifier(
            dependency["source_statement_id"],
            label=f"{label} source_statement_id",
        )
        target = _identifier(
            dependency["target_statement_id"],
            label=f"{label} target_statement_id",
        )
        relation = _text(
            dependency["relation"], label=f"{label} relation", maximum=50
        )
        if source not in local_statement_ids:
            _fail(f"{label} source_statement_id is not defined in this fragment")
        if source == target:
            _fail(f"{label} must not be a self-edge")
        if relation not in DEPENDENCY_RELATIONS:
            _fail(
                f"{label} relation must be one of "
                + ", ".join(sorted(DEPENDENCY_RELATIONS))
            )
        identity = (source, relation, target)
        if identity in seen:
            _fail(f"duplicate knowledge dependency {identity!r}")
        seen.add(identity)
        normalized.append({
            "source_statement_id": source,
            "relation": relation,
            "target_statement_id": target,
            "reason": _text(
                dependency["reason"], label=f"{label} reason"
            ),
        })
    return normalized


def _normalize_lead_summary(
    value: Any,
    *,
    complete: bool,
) -> dict[str, list[str]]:
    summary = _mapping(value, label="knowledge lead_summary")
    _exact_keys(summary, _SUMMARY_KEYS, label="knowledge lead_summary")
    normalized = {
        field: _string_list(
            summary[field],
            label=f"knowledge lead_summary {field}",
            maximum_items=MAX_SUMMARY_ITEMS,
            allow_empty=True,
        )
        for field in sorted(_SUMMARY_KEYS)
    }
    if complete and not normalized["fundamental_points"]:
        _fail(
            "complete knowledge fragment lead_summary must contain at least "
            "one fundamental_points entry"
        )
    return normalized


def _normalize_common(
    value: Mapping[str, Any],
    *,
    expected_keys: frozenset[str],
    expected_kind: str,
    expected_semantics: str,
    expected_method: Mapping[str, Any] | None,
    expected_generation: int | None,
    expected_source_run_id: str | None,
    require_complete: bool,
) -> tuple[dict[str, Any], set[str]]:
    _exact_keys(value, expected_keys, label="knowledge fragment")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != SCHEMA_VERSION
    ):
        _fail(f"knowledge fragment schema_version must be {SCHEMA_VERSION}")
    if value["kind"] != expected_kind:
        _fail(f"knowledge fragment kind must be {expected_kind!r}")
    if value["semantics"] != expected_semantics:
        _fail(
            f"knowledge fragment semantics must be {expected_semantics!r}"
        )
    coverage = _text(
        value["coverage"], label="knowledge fragment coverage", maximum=20
    )
    if coverage not in COVERAGE_VALUES:
        _fail(
            "knowledge fragment coverage must be draft or complete"
        )
    if require_complete and coverage != "complete":
        _fail("knowledge fragment coverage must be complete")
    complete = coverage == "complete"

    method = _normalize_method(
        value["method"], label="knowledge fragment method"
    )
    if expected_method is not None:
        expected = _normalize_method(
            expected_method, label="expected method"
        )
        if method != expected:
            _fail("knowledge fragment method does not match the expected method")
    generation = _integer(
        value["generation"], label="knowledge fragment generation"
    )
    if (
        expected_generation is not None
        and generation != _integer(
            expected_generation, label="expected generation"
        )
    ):
        _fail(
            "knowledge fragment generation does not match the expected generation"
        )
    source_run_id = _identifier(
        value["source_run_id"], label="knowledge fragment source_run_id"
    )
    if expected_source_run_id is not None and source_run_id != _identifier(
        expected_source_run_id, label="expected source_run_id"
    ):
        _fail(
            "knowledge fragment source_run_id does not match the expected source run"
        )

    statements, statement_ids = _normalize_statements(
        value["statements"], complete=complete
    )
    dependencies = _normalize_dependencies(
        value["dependencies"], local_statement_ids=statement_ids
    )
    normalized = {
        "schema_version": SCHEMA_VERSION,
        "kind": expected_kind,
        "semantics": expected_semantics,
        "coverage": coverage,
        "method": method,
        "generation": generation,
        "source_run_id": source_run_id,
        "statements": statements,
        "dependencies": dependencies,
        "lead_summary": _normalize_lead_summary(
            value["lead_summary"], complete=complete
        ),
    }
    return normalized, statement_ids


def validate_theory_fragment(
    value: Mapping[str, Any],
    *,
    expected_method: Mapping[str, Any] | None = None,
    expected_generation: int | None = None,
    expected_source_run_id: str | None = None,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Validate and normalize one complete-replacement Phase 3 fragment."""

    fragment = _mapping(value, label="knowledge fragment")
    normalized, _ = _normalize_common(
        fragment,
        expected_keys=_THEORY_KEYS,
        expected_kind=THEORY_KIND,
        expected_semantics=THEORY_SEMANTICS,
        expected_method=expected_method,
        expected_generation=expected_generation,
        expected_source_run_id=expected_source_run_id,
        require_complete=require_complete,
    )
    return normalized


def _normalized_evidence_index(
    value: Mapping[str, Any],
) -> tuple[dict[str, str], int, str, dict[str, dict[str, str]], int]:
    index = _mapping(value, label="normalized evidence index")
    for field in ("method", "generation", "source_run_id", "entries"):
        if field not in index:
            _fail(f"normalized evidence index is missing field {field!r}")
    method = _normalize_method(
        index["method"], label="normalized evidence index method"
    )
    generation = _integer(
        index["generation"], label="normalized evidence index generation"
    )
    source_run_id = _identifier(
        index["source_run_id"],
        label="normalized evidence index source_run_id",
    )
    schema_version = index.get("schema_version")
    if type(schema_version) is not int or schema_version not in {1, 2, 3}:
        _fail("normalized evidence index schema_version is unsupported")
    raw_entries = index["entries"]
    if (
        not isinstance(raw_entries, list)
        or len(raw_entries) > MAX_EVIDENCE_BINDINGS
    ):
        _fail(
            f"normalized evidence index entries must be a list with at most "
            f"{MAX_EVIDENCE_BINDINGS} items"
        )
    entries: dict[str, dict[str, str]] = {}
    for number, raw_entry in enumerate(raw_entries, start=1):
        label = f"normalized evidence entry {number}"
        entry = _mapping(raw_entry, label=label)
        if "evidence_id" not in entry or "status" not in entry:
            _fail(f"{label} must contain evidence_id and status")
        evidence_id = _identifier(
            entry["evidence_id"], label=f"{label} evidence_id"
        )
        status_value = _text(
            entry["status"], label=f"{label} status", maximum=20
        )
        if status_value not in EVIDENCE_STATUSES:
            _fail(
                f"{label} status must be one of "
                + ", ".join(sorted(EVIDENCE_STATUSES))
            )
        if evidence_id in entries:
            _fail(f"duplicate normalized evidence_id {evidence_id!r}")
        applicability_state = str(entry.get("applicability_state", ""))
        if schema_version >= 3 and applicability_state not in {
            "active_current_method", "active_reusable", "attention", "historical",
        }:
            _fail(f"{label} has invalid applicability_state")
        entries[evidence_id] = {
            "status": status_value,
            "applicability_state": applicability_state,
        }
    return method, generation, source_run_id, entries, schema_version


def _normalize_assessments(
    value: Any,
    *,
    binding_number: int,
    local_statement_ids: set[str],
    current_statement_ids: set[str],
    applicability_state: str,
    evidence_schema_version: int,
) -> list[dict[str, str]]:
    label = f"evidence binding {binding_number} assessments"
    if (
        not isinstance(value, list)
        or len(value) > MAX_ASSESSMENTS_PER_EVIDENCE
    ):
        _fail(
            f"{label} must be a list with at most "
            f"{MAX_ASSESSMENTS_PER_EVIDENCE} items"
        )
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for number, raw_assessment in enumerate(value, start=1):
        item_label = f"evidence binding {binding_number} assessment {number}"
        assessment = _mapping(raw_assessment, label=item_label)
        _exact_keys(assessment, _ASSESSMENT_KEYS, label=item_label)
        statement_id = _identifier(
            assessment["statement_id"],
            label=f"{item_label} statement_id",
        )
        if statement_id not in local_statement_ids:
            _fail(
                f"{item_label} statement_id is not defined in this fragment"
            )
        if (
            evidence_schema_version >= 3
            and statement_id in current_statement_ids
            and applicability_state
            not in {"active_current_method", "active_reusable"}
        ):
            _fail(
                f"{item_label} cannot use noncurrent evidence for a Current statement"
            )
        relation = _text(
            assessment["relation"],
            label=f"{item_label} relation",
            maximum=50,
        )
        if relation not in EVIDENCE_RELATIONS:
            _fail(
                f"{item_label} relation must be one of "
                + ", ".join(sorted(EVIDENCE_RELATIONS))
            )
        identity = (statement_id, relation)
        if identity in seen:
            _fail(f"duplicate evidence assessment {identity!r}")
        seen.add(identity)
        normalized.append({
            "statement_id": statement_id,
            "relation": relation,
            "interpretation": _text(
                assessment["interpretation"],
                label=f"{item_label} interpretation",
            ),
        })
    return normalized


def _normalize_evidence_bindings(
    value: Any,
    *,
    index_entries: Mapping[str, Mapping[str, str]],
    local_statement_ids: set[str],
    current_statement_ids: set[str],
    evidence_schema_version: int,
    complete: bool,
) -> list[dict[str, Any]]:
    if (
        not isinstance(value, list)
        or len(value) > MAX_EVIDENCE_BINDINGS
    ):
        _fail(
            f"knowledge fragment evidence_bindings must be a list with at most "
            f"{MAX_EVIDENCE_BINDINGS} items"
        )
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for number, raw_binding in enumerate(value, start=1):
        label = f"evidence binding {number}"
        binding = _mapping(raw_binding, label=label)
        _exact_keys(binding, _EVIDENCE_BINDING_KEYS, label=label)
        evidence_id = _identifier(
            binding["evidence_id"], label=f"{label} evidence_id"
        )
        if evidence_id in seen_ids:
            _fail(f"duplicate evidence binding {evidence_id!r}")
        seen_ids.add(evidence_id)
        if evidence_id not in index_entries:
            _fail(
                f"{label} refers to unknown evidence_id {evidence_id!r}"
            )
        evidence_status = _text(
            binding["evidence_status"],
            label=f"{label} evidence_status",
            maximum=20,
        )
        evidence_record = index_entries[evidence_id]
        if evidence_status != evidence_record["status"]:
            _fail(
                f"{label} evidence_status does not match evidence-index status"
            )
        role = _text(
            binding["role"], label=f"{label} role", maximum=50
        )
        if role not in EVIDENCE_ROLES:
            _fail(
                f"{label} role must be one of "
                + ", ".join(sorted(EVIDENCE_ROLES))
            )
        normalized.append({
            "evidence_id": evidence_id,
            "evidence_status": evidence_status,
            "role": role,
            "assessments": _normalize_assessments(
                binding["assessments"],
                binding_number=number,
                local_statement_ids=local_statement_ids,
                current_statement_ids=current_statement_ids,
                applicability_state=evidence_record["applicability_state"],
                evidence_schema_version=evidence_schema_version,
            ),
        })
    if complete and seen_ids != set(index_entries):
        missing = sorted(set(index_entries).difference(seen_ids))
        _fail(
            "complete empirical knowledge fragment omits evidence IDs: "
            + ", ".join(missing)
        )
    return normalized


def validate_empirical_fragment(
    value: Mapping[str, Any],
    evidence_index: Mapping[str, Any],
    *,
    expected_method: Mapping[str, Any] | None = None,
    expected_generation: int | None = None,
    expected_source_run_id: str | None = None,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Validate a Phase 4 fragment against its normalized evidence index."""

    (
        index_method,
        index_generation,
        index_run,
        index_entries,
        evidence_schema_version,
    ) = (
        _normalized_evidence_index(evidence_index)
    )
    if expected_method is not None:
        caller_method = _normalize_method(
            expected_method, label="expected method"
        )
        if caller_method != index_method:
            _fail("normalized evidence index method does not match the expected method")
    if expected_generation is not None and _integer(
        expected_generation, label="expected generation"
    ) != index_generation:
        _fail(
            "normalized evidence index generation does not match the expected generation"
        )
    if expected_source_run_id is not None and _identifier(
        expected_source_run_id, label="expected source_run_id"
    ) != index_run:
        _fail(
            "normalized evidence index source_run_id does not match the expected source run"
        )

    fragment = _mapping(value, label="knowledge fragment")
    normalized, statement_ids = _normalize_common(
        fragment,
        expected_keys=_EMPIRICAL_KEYS,
        expected_kind=EMPIRICAL_KIND,
        expected_semantics=EMPIRICAL_SEMANTICS,
        expected_method=index_method,
        expected_generation=index_generation,
        expected_source_run_id=index_run,
        require_complete=require_complete,
    )
    normalized["evidence_bindings"] = _normalize_evidence_bindings(
        fragment["evidence_bindings"],
        index_entries=index_entries,
        local_statement_ids=statement_ids,
        current_statement_ids={
            statement["statement_id"]
            for statement in normalized["statements"]
            if statement["formulation_state"] == "Current"
        },
        evidence_schema_version=evidence_schema_version,
        complete=normalized["coverage"] == "complete",
    )
    return normalized


def _unique_json_object(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail(f"knowledge fragment contains duplicate field {key!r}")
        value[key] = item
    return value


def parse_fragment(
    payload: bytes,
    *,
    label: str = "knowledge fragment",
) -> dict[str, Any]:
    """Parse bounded UTF-8 JSON while rejecting duplicate fields and NaN."""

    if type(payload) is not bytes:
        _fail(f"{label} payload must be bytes")
    if not payload or len(payload) > MAX_KNOWLEDGE_BYTES:
        _fail(
            f"{label} must contain 1 to {MAX_KNOWLEDGE_BYTES} bytes"
        )
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        _fail(f"{label} is not valid UTF-8", exc)
    try:
        value = json.loads(
            source,
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda constant: _fail(
                f"{label} contains invalid numeric value {constant!r}"
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, KnowledgeFragmentError):
            raise
        _fail(f"{label} is not valid JSON: {exc}", exc)
    if not isinstance(value, dict):
        _fail(f"{label} must contain one JSON object")
    return value


def read_fragment(
    path: str | Path,
    *,
    label: str = "knowledge fragment",
) -> tuple[dict[str, Any], bytes]:
    """Read a bounded regular file and parse its fragment JSON."""

    candidate = Path(path)
    try:
        metadata = candidate.lstat()
        if metadata_is_link_or_reparse(metadata) or not stat.S_ISREG(
            metadata.st_mode
        ):
            _fail(f"{label} must be a regular file, not a link")
        if metadata.st_size < 1 or metadata.st_size > MAX_KNOWLEDGE_BYTES:
            _fail(
                f"{label} must contain 1 to {MAX_KNOWLEDGE_BYTES} bytes"
            )
        payload = candidate.read_bytes()
    except KnowledgeFragmentError:
        raise
    except OSError as exc:
        _fail(f"{label} cannot be read: {exc}", exc)
    return parse_fragment(payload, label=label), payload
