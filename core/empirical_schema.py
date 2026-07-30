"""Bounded schema and path validation for Phase 04 empirical records.

The cumulative evidence policy and promotion transaction live in
``core.empirical_records``. This module owns only the on-disk contract and its
filesystem boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from core import knowledge_fragments, method_menu, project_state


LEGACY_INDEX_SCHEMA_VERSION = 1
COUNTERPART_INDEX_SCHEMA_VERSION = 2
INDEX_SCHEMA_VERSION = 3
INDEX_KIND = "empirical_evidence_index"
SYNTHESIS_FILENAME = "empirical-synthesis.md"
INDEX_FILENAME = "evidence-index.json"
KNOWLEDGE_FILENAME = knowledge_fragments.KNOWLEDGE_FILENAME
EVIDENCE_TYPES = frozenset({
    "code", "data", "figure", "log", "model", "protocol",
    "report", "result", "table", "other",
})
RUN_SCOPES = frozenset({"preliminary", "comprehensive"})
EVIDENCE_STATUSES = frozenset({
    "current", "outdated", "superseded", "withdrawn", "unresolved",
})
SCIENTIFIC_OUTPUT_TYPES = frozenset({
    "figure", "model", "report", "result", "table",
})
METHOD_IMPLEMENTATION_TYPES = frozenset({"code"})
VERSION_BOUND_TYPES = SCIENTIFIC_OUTPUT_TYPES | METHOD_IMPLEMENTATION_TYPES
INPUT_TYPES = frozenset({"data"})
INFRASTRUCTURE_TYPES = frozenset({"log", "protocol", "other"})
EVIDENCE_CLASSES = frozenset({
    "scientific_result", "method_implementation", "input", "infrastructure",
})
APPLICABILITY_SCOPES = frozenset({"exact_method", "reusable"})
APPLICABILITY_STATES = frozenset({
    "active_current_method", "active_reusable", "attention", "historical",
})

MAX_INDEX_BYTES = 4 * 1024 * 1024
MAX_SYNTHESIS_BYTES = 4 * 1024 * 1024
MAX_CURRENT_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_CURRENT_ARTIFACT_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_EVIDENCE_ENTRIES = 2_000
MAX_PATH_LENGTH = 1_000
MAX_REASON_LENGTH = 2_000

IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
METHOD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:-]{0,199}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

LEGACY_INDEX_KEYS = frozenset({
    "schema_version", "kind", "method", "generation", "source_run_id",
    "synthesis", "entries",
})
INDEX_KEYS = LEGACY_INDEX_KEYS | {"counterpart_basis"}
METHOD_KEYS = frozenset({"stable_id", "version", "definition_sha256"})
SYNTHESIS_KEYS = frozenset({"path", "sha256", "size"})
ENTRY_KEYS = frozenset({
    "evidence_id", "type", "path", "sha256", "size", "source_run_id",
    "run_scope", "status", "status_reason", "method_dependent",
})
NORMALIZED_ENTRY_KEYS = ENTRY_KEYS | {
    "evidence_class", "applicability_scope", "applicability_state",
}


class EmpiricalRecordError(ValueError):
    """Base class for empirical-record validation and promotion failures."""


class EmpiricalRecordValidationError(EmpiricalRecordError):
    """An empirical package does not satisfy the bounded schema."""


@dataclass(frozen=True)
class PackageSnapshot:
    """Validated bytes and normalized data for one empirical package."""

    index: dict[str, Any]
    synthesis_bytes: bytes
    index_bytes: bytes
    knowledge_bytes: bytes | None = None


def fail(message: str, exc: BaseException | None = None) -> None:
    """Raise the schema's public validation error."""

    if exc is None:
        raise EmpiricalRecordValidationError(message)
    raise EmpiricalRecordValidationError(message) from exc


def project_root(project_dir: str | Path) -> Path:
    """Resolve an existing project directory through the shared validator."""

    try:
        return method_menu._project_root(project_dir)
    except method_menu.MethodMenuValidationError as exc:
        fail(str(exc), exc)
    raise AssertionError("unreachable")


def safe_project_path(root: Path, value: str | Path, *, label: str) -> Path:
    """Resolve a path inside a project without links or reparse points."""

    try:
        return method_menu._safe_project_path(root, value, label=label)
    except method_menu.MethodMenuValidationError as exc:
        fail(str(exc), exc)
    raise AssertionError("unreachable")


def read_bytes(
    root: Path,
    value: str | Path,
    *,
    maximum: int,
    label: str,
    allow_empty: bool,
) -> tuple[Path, bytes]:
    path = safe_project_path(root, value, label=label)
    try:
        payload = project_state.bounded_file_bytes(
            path, maximum=maximum, label=label, allow_empty=allow_empty
        )
    except project_state.ProjectStateError as exc:
        fail(str(exc), exc)
    return path, payload


def exact_keys(
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


def mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        fail(f"{label} must be an object with text field names")
    return value


def text(
    value: Any,
    *,
    label: str,
    maximum: int = 200,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if type(value) is not str:
        fail(f"{label} must be text")
    if not value.strip() or len(value) > maximum:
        fail(f"{label} must contain between 1 and {maximum} characters")
    if pattern is not None and pattern.fullmatch(value) is None:
        fail(f"{label} has an invalid format")
    return value


def integer(
    value: Any,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        fail(f"{label} must be an integer from {minimum} through {maximum}")
    return value


def sha256(value: Any, *, label: str) -> str:
    return text(value, label=label, maximum=64, pattern=SHA256_RE)


def normalized_relative_path(
    root: Path,
    value: Any,
    *,
    label: str,
) -> tuple[str, Path]:
    stored = text(value, label=label, maximum=MAX_PATH_LENGTH)
    if "\\" in stored:
        fail(f"{label} must use forward slashes")
    relative = PurePosixPath(stored)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or ":" in relative.parts[0]
    ):
        fail(f"{label} must be a normalized project-relative path")
    path = safe_project_path(root, Path(*relative.parts), label=label)
    try:
        normalized = path.relative_to(root).as_posix()
    except ValueError as exc:
        fail(f"{label} is outside the project directory", exc)
    if normalized != stored:
        fail(f"{label} must be a normalized project-relative path")
    return stored, path


def _unique_json_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail(f"evidence index contains duplicate field {key!r}")
        value[key] = item
    return value


def parse_index(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{label} is not valid UTF-8", exc)
    try:
        value = json.loads(
            source,
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda constant: fail(
                f"{label} contains invalid numeric value {constant!r}"
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, EmpiricalRecordError):
            raise
        fail(f"{label} is not valid JSON: {exc}", exc)
    if not isinstance(value, dict):
        fail(f"{label} must contain one JSON object")
    return value


def canonical_relative_dir(stable_id: str) -> Path:
    return Path("branches") / stable_id / "draft" / "sections" / "current"


def canonical_package_dir(project_dir: str | Path, stable_id: str) -> Path:
    """Return the validated canonical package directory for one method."""

    root = project_root(project_dir)
    method_id = text(
        stable_id, label="method stable_id", maximum=200, pattern=METHOD_ID_RE
    )
    return safe_project_path(
        root,
        canonical_relative_dir(method_id),
        label="canonical empirical package directory",
    )


def _validate_method(raw: Any, expected_stable_id: str | None) -> dict[str, str]:
    method = mapping(raw, label="evidence index method")
    exact_keys(method, METHOD_KEYS, label="evidence index method")
    stable_id = text(
        method["stable_id"],
        label="method stable_id",
        maximum=200,
        pattern=METHOD_ID_RE,
    )
    if expected_stable_id is not None and stable_id != expected_stable_id:
        fail("evidence index method stable_id does not match its branch directory")
    return {
        "stable_id": stable_id,
        "version": text(
            method["version"],
            label="method version",
            maximum=200,
            pattern=VERSION_RE,
        ),
        "definition_sha256": sha256(
            method["definition_sha256"], label="method definition_sha256"
        ),
    }


def _validate_synthesis(raw: Any, payload: bytes) -> dict[str, Any]:
    synthesis = mapping(raw, label="evidence index synthesis")
    exact_keys(synthesis, SYNTHESIS_KEYS, label="evidence index synthesis")
    if synthesis["path"] != SYNTHESIS_FILENAME:
        fail(f"evidence index synthesis path must be {SYNTHESIS_FILENAME!r}")
    digest = sha256(synthesis["sha256"], label="evidence index synthesis sha256")
    size = integer(
        synthesis["size"],
        label="evidence index synthesis size",
        minimum=1,
        maximum=MAX_SYNTHESIS_BYTES,
    )
    if size != len(payload):
        fail("empirical synthesis size does not match the evidence index")
    if digest != hashlib.sha256(payload).hexdigest():
        fail("empirical synthesis SHA-256 does not match the evidence index")
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("empirical synthesis is not valid UTF-8", exc)
    if not source.strip():
        fail("empirical synthesis must not be empty")
    return {"path": SYNTHESIS_FILENAME, "sha256": digest, "size": size}


def _evidence_class(evidence_type: str) -> str:
    if evidence_type in SCIENTIFIC_OUTPUT_TYPES:
        return "scientific_result"
    if evidence_type in METHOD_IMPLEMENTATION_TYPES:
        return "method_implementation"
    if evidence_type in INPUT_TYPES:
        return "input"
    return "infrastructure"


def evidence_requires_exact_method(entry: Mapping[str, Any]) -> bool:
    """Return whether evidence is valid only for its recorded method version."""

    scope = entry.get("applicability_scope")
    if scope in APPLICABILITY_SCOPES:
        return scope == "exact_method"
    return (
        str(entry.get("type", "")) in VERSION_BOUND_TYPES
        or entry.get("method_dependent") is True
    )


def derived_entry_applicability(entry: Mapping[str, Any]) -> dict[str, str]:
    evidence_type = str(entry.get("type", ""))
    status = str(entry.get("status", ""))
    exact_method = evidence_requires_exact_method(entry)
    if status == "current":
        state = "active_current_method" if exact_method else "active_reusable"
    elif status in {"outdated", "unresolved"}:
        state = "attention"
    else:
        state = "historical"
    return {
        "evidence_class": _evidence_class(evidence_type),
        "applicability_scope": "exact_method" if exact_method else "reusable",
        "applicability_state": state,
    }


def serialized_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Remove derived applicability fields before writing an evidence index."""

    if not isinstance(entry, Mapping) or not ENTRY_KEYS.issubset(entry):
        fail("evidence entry is missing serialized fields")
    return {
        "evidence_id": entry["evidence_id"],
        "type": entry["type"],
        "path": entry["path"],
        "sha256": entry["sha256"],
        "size": entry["size"],
        "source_run_id": entry["source_run_id"],
        "run_scope": entry["run_scope"],
        "status": entry["status"],
        "status_reason": entry["status_reason"],
        "method_dependent": evidence_requires_exact_method(entry),
    }


def _validate_entry(
    root: Path,
    raw: Any,
    *,
    number: int,
    verify_current_artifacts: bool,
    schema_version: int,
) -> tuple[dict[str, Any], int]:
    label = f"evidence entry {number}"
    entry = mapping(raw, label=label)
    exact_keys(entry, ENTRY_KEYS, label=label)
    evidence_id = text(
        entry["evidence_id"],
        label=f"{label} evidence_id",
        maximum=200,
        pattern=IDENTIFIER_RE,
    )
    evidence_type = text(entry["type"], label=f"{label} type", maximum=50)
    if evidence_type not in EVIDENCE_TYPES:
        fail(f"{label} type must be one of {', '.join(sorted(EVIDENCE_TYPES))}")
    stored_path, artifact_path = normalized_relative_path(
        root, entry["path"], label=f"{label} path"
    )
    digest = sha256(entry["sha256"], label=f"{label} sha256")
    size = integer(
        entry["size"],
        label=f"{label} size",
        minimum=0,
        maximum=MAX_CURRENT_ARTIFACT_BYTES,
    )
    source_run_id = text(
        entry["source_run_id"],
        label=f"{label} source_run_id",
        maximum=200,
        pattern=IDENTIFIER_RE,
    )
    run_scope = text(entry["run_scope"], label=f"{label} run_scope", maximum=20)
    if run_scope not in RUN_SCOPES:
        fail(f"{label} run_scope must be preliminary or comprehensive")
    status = text(entry["status"], label=f"{label} status", maximum=20)
    if status not in EVIDENCE_STATUSES:
        fail(
            f"{label} status must be one of "
            f"{', '.join(sorted(EVIDENCE_STATUSES))}"
        )
    status_reason = text(
        entry["status_reason"],
        label=f"{label} status_reason",
        maximum=MAX_REASON_LENGTH,
    )
    method_dependent = entry["method_dependent"]
    if type(method_dependent) is not bool:
        fail(f"{label} method_dependent must be true or false")
    if (
        schema_version == INDEX_SCHEMA_VERSION
        and evidence_type in VERSION_BOUND_TYPES
        and method_dependent is False
    ):
        fail(
            f"{label} type {evidence_type!r} must be bound to the exact "
            "method version"
        )
    effective_method_dependent = (
        method_dependent or evidence_type in VERSION_BOUND_TYPES
    )
    applicability = derived_entry_applicability({
        "type": evidence_type,
        "status": status,
        "method_dependent": effective_method_dependent,
    })

    current_size = 0
    if status == "current" and verify_current_artifacts:
        try:
            actual_digest, actual_size = project_state.bounded_file_digest(
                artifact_path,
                maximum=MAX_CURRENT_ARTIFACT_BYTES,
                label=f"{label} current artifact",
                allow_empty=True,
            )
        except project_state.ProjectStateError as exc:
            fail(str(exc), exc)
        if actual_size != size or actual_digest != digest:
            fail(
                f"{label} current artifact does not match its recorded "
                "size and SHA-256"
            )
        current_size = actual_size

    return {
        "evidence_id": evidence_id,
        "type": evidence_type,
        "path": stored_path,
        "sha256": digest,
        "size": size,
        "source_run_id": source_run_id,
        "run_scope": run_scope,
        "status": status,
        "status_reason": status_reason,
        "method_dependent": effective_method_dependent,
        **applicability,
    }, current_size


def validate_counterpart_basis(value: Any) -> dict[str, Any]:
    """Validate a Phase 3 basis stored by a Phase 4 package."""

    from core import knowledge_basis

    try:
        basis = knowledge_basis.validate_basis(value)
    except knowledge_basis.KnowledgeBasisError as exc:
        fail(f"empirical counterpart basis is invalid: {exc}", exc)
    if basis["phase_slug"] != knowledge_basis.THEORY_PHASE:
        fail("empirical counterpart basis must describe Phase 3")
    return basis


def validate_index(
    root: Path,
    index: Mapping[str, Any],
    synthesis_bytes: bytes,
    *,
    expected_stable_id: str | None,
    verify_current_artifacts: bool,
) -> dict[str, Any]:
    """Validate and normalize one evidence index and its bound synthesis."""

    index = mapping(index, label="evidence index")
    schema_version = index.get("schema_version")
    if type(schema_version) is not int:
        fail("evidence index schema_version is unsupported")
    if schema_version in {
        COUNTERPART_INDEX_SCHEMA_VERSION,
        INDEX_SCHEMA_VERSION,
    }:
        exact_keys(index, INDEX_KEYS, label="evidence index")
        counterpart_basis = validate_counterpart_basis(
            index["counterpart_basis"]
        )
    elif schema_version == LEGACY_INDEX_SCHEMA_VERSION:
        exact_keys(index, LEGACY_INDEX_KEYS, label="evidence index")
        counterpart_basis = None
    else:
        fail("evidence index schema_version is unsupported")
    if index["kind"] != INDEX_KIND:
        fail(f"evidence index kind must be {INDEX_KIND!r}")

    method = _validate_method(index["method"], expected_stable_id)
    generation = integer(
        index["generation"],
        label="evidence index generation",
        minimum=1,
        maximum=2_147_483_647,
    )
    source_run_id = text(
        index["source_run_id"],
        label="evidence index source_run_id",
        maximum=200,
        pattern=IDENTIFIER_RE,
    )
    synthesis = _validate_synthesis(index["synthesis"], synthesis_bytes)

    raw_entries = index["entries"]
    if not isinstance(raw_entries, list):
        fail("evidence index entries must be a list")
    if len(raw_entries) > MAX_EVIDENCE_ENTRIES:
        fail(f"evidence index exceeds the {MAX_EVIDENCE_ENTRIES}-entry limit")
    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    current_total = 0
    for number, raw_entry in enumerate(raw_entries, start=1):
        entry, current_size = _validate_entry(
            root,
            raw_entry,
            number=number,
            verify_current_artifacts=verify_current_artifacts,
            schema_version=schema_version,
        )
        evidence_id = entry["evidence_id"]
        if evidence_id in seen_ids:
            fail(f"duplicate evidence_id {evidence_id!r}")
        seen_ids.add(evidence_id)
        entries.append(entry)
        current_total += current_size
        if current_total > MAX_CURRENT_ARTIFACT_TOTAL_BYTES:
            fail("current empirical artifacts exceed the aggregate byte limit")

    normalized = {
        "schema_version": schema_version,
        "kind": INDEX_KIND,
        "method": method,
        "generation": generation,
        "source_run_id": source_run_id,
        "synthesis": synthesis,
        "entries": entries,
    }
    if counterpart_basis is not None:
        normalized["counterpart_basis"] = counterpart_basis
    return normalized


def read_package(
    root: Path,
    directory: Path,
    *,
    expected_stable_id: str | None,
    verify_current_artifacts: bool,
    required: bool,
    require_knowledge: bool = False,
    require_complete_knowledge: bool = True,
) -> PackageSnapshot | None:
    """Read and validate a staged or canonical empirical package."""

    directory = safe_project_path(
        root,
        directory,
        label="empirical package directory",
    )
    synthesis_path = safe_project_path(
        root,
        directory / SYNTHESIS_FILENAME,
        label="empirical synthesis",
    )
    index_path = safe_project_path(
        root,
        directory / INDEX_FILENAME,
        label="empirical evidence index",
    )
    knowledge_path = safe_project_path(
        root,
        directory / KNOWLEDGE_FILENAME,
        label="empirical knowledge fragment",
    )
    synthesis_exists = synthesis_path.exists()
    index_exists = index_path.exists()
    knowledge_exists = knowledge_path.exists()
    if not synthesis_exists and not index_exists and not knowledge_exists:
        if required:
            fail(f"empirical package is missing from {directory}")
        return None
    if synthesis_exists != index_exists or (
        knowledge_exists and not synthesis_exists
    ):
        fail(
            f"empirical package is incomplete in {directory}; "
            f"{SYNTHESIS_FILENAME} and {INDEX_FILENAME} are required"
        )
    if require_knowledge and not knowledge_exists:
        fail(f"{KNOWLEDGE_FILENAME} is required")

    _, synthesis_bytes = read_bytes(
        root,
        synthesis_path,
        maximum=MAX_SYNTHESIS_BYTES,
        label="empirical synthesis",
        allow_empty=False,
    )
    _, index_bytes = read_bytes(
        root,
        index_path,
        maximum=MAX_INDEX_BYTES,
        label="empirical evidence index",
        allow_empty=False,
    )
    index = validate_index(
        root,
        parse_index(index_bytes, label="empirical evidence index"),
        synthesis_bytes,
        expected_stable_id=expected_stable_id,
        verify_current_artifacts=verify_current_artifacts,
    )

    knowledge_bytes: bytes | None = None
    if knowledge_exists:
        _, knowledge_bytes = read_bytes(
            root,
            knowledge_path,
            maximum=knowledge_fragments.MAX_KNOWLEDGE_BYTES,
            label="empirical knowledge fragment",
            allow_empty=False,
        )
        try:
            parsed = knowledge_fragments.parse_fragment(
                knowledge_bytes,
                label="empirical knowledge fragment",
            )
            knowledge_fragments.validate_empirical_fragment(
                parsed,
                index,
                expected_method=index["method"],
                expected_generation=index["generation"],
                expected_source_run_id=index["source_run_id"],
                require_complete=require_complete_knowledge,
            )
        except knowledge_fragments.KnowledgeFragmentError as exc:
            fail(str(exc), exc)
    return PackageSnapshot(
        index,
        synthesis_bytes,
        index_bytes,
        knowledge_bytes,
    )
