"""Verified current Phase 3 and Phase 4 knowledge heads.

A head is a compact semantic basis derived from a phase-owned current package.
Live derivation reads canonical packages. Frozen derivation reads only the
sealed ``snapshots.current_records`` copies in a schema 12 or 13 run manifest.
Phase 4 evidence artifacts remain project references and are never copied or
opened by frozen head derivation.

This module is intentionally one-way. It may read phase record modules, but
phase record modules must not import it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from core import empirical_records
from core import empirical_schema
from core import knowledge_basis
from core import knowledge_content
from core import knowledge_fragments
from core import knowledge_schema
from core import project_state
from core import theory_records
from core.filesystem_utils import metadata_is_link_or_reparse


SCHEMA_VERSION = 1
SUPPORTED_FROZEN_MANIFEST_SCHEMAS = frozenset({12, 13, 14})
MAX_FROZEN_RECORDS = 16
MAX_FILES_PER_RECORD = 4

P3_KEY = "p3_theory"
P4_KEY = "p4_empirical"
P1_KEY = "p1_literature"
P3_KIND = "current_theory"
P4_KIND = "current_empirical"
P1_KIND = "current_literature"

_HEAD_FIELDS = frozenset({"schema_version", P3_KEY, P4_KEY})
_RECORD_FIELDS = frozenset({
    "key",
    "kind",
    "source_run_id",
    "generation",
    "files",
})
_SCHEMA_13_RECORD_FIELDS = _RECORD_FIELDS | {"method_identity"}
_FILE_FIELDS = frozenset({"path", "sha256", "source_path", "size"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PATH_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,299}$")
_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,299}$")

_MAX_THEORY_MANUSCRIPT_BYTES = 20 * 1024 * 1024
_MAX_THEORY_RECORD_BYTES = 256 * 1024
_MAX_LITERATURE_FILE_BYTES = 5 * 1024 * 1024


class KnowledgeHeadsError(ValueError):
    """Base class for invalid or unverifiable knowledge heads."""


class KnowledgeHeadsValidationError(KnowledgeHeadsError):
    """A caller value or heads value violates the strict contract."""


class KnowledgeHeadsCorrupt(KnowledgeHeadsError):
    """A live or frozen source cannot be verified."""


def _fail(message: str, exc: BaseException | None = None) -> None:
    if exc is None:
        raise KnowledgeHeadsValidationError(message)
    raise KnowledgeHeadsValidationError(message) from exc


def _corrupt(message: str, exc: BaseException | None = None) -> None:
    if exc is None:
        raise KnowledgeHeadsCorrupt(message)
    raise KnowledgeHeadsCorrupt(message) from exc


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be an object with text field names")
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
    _fail(f"{label} has invalid fields: {'; '.join(details)}")


def _stable_id(value: Any) -> str:
    if type(value) is not str or _STABLE_ID_RE.fullmatch(value) is None:
        _fail("stable_id must be a bounded safe method identifier")
    return value


def _generation(value: Any, *, label: str) -> int:
    if (
        type(value) is not int
        or not 1 <= value <= knowledge_basis.MAX_GENERATION
    ):
        _corrupt(f"{label} must be a positive 32-bit integer")
    return value


def _source_run_id(value: Any, *, label: str) -> str:
    if type(value) is not str or _RUN_ID_RE.fullmatch(value) is None:
        _corrupt(f"{label} must be a bounded safe identifier")
    return value


def _method_identity(value: Any, *, label: str) -> dict[str, str]:
    try:
        return knowledge_schema.normalize_method_identity(value)
    except knowledge_schema.KnowledgeSchemaError as exc:
        _corrupt(f"{label} is invalid: {exc}", exc)
    raise AssertionError("unreachable")


def _project_root(project_dir: str | Path) -> Path:
    try:
        return empirical_schema.project_root(project_dir)
    except empirical_schema.EmpiricalRecordError as exc:
        _fail(str(exc), exc)
    raise AssertionError("unreachable")


def validate_heads(value: Any) -> dict[str, Any]:
    """Validate and normalize the exact two-head value."""

    heads = _mapping(value, label="knowledge heads")
    _exact_fields(heads, _HEAD_FIELDS, label="knowledge heads")
    if (
        type(heads["schema_version"]) is not int
        or heads["schema_version"] != SCHEMA_VERSION
    ):
        _fail(f"knowledge heads schema_version must be {SCHEMA_VERSION}")
    try:
        theory = knowledge_basis.validate_basis(heads[P3_KEY])
        empirical = knowledge_basis.validate_basis(heads[P4_KEY])
    except knowledge_basis.KnowledgeBasisError as exc:
        _fail(str(exc), exc)
    if theory["phase_slug"] != knowledge_basis.THEORY_PHASE:
        _fail(f"{P3_KEY} must contain a Phase 3 basis")
    if empirical["phase_slug"] != knowledge_basis.EMPIRICAL_PHASE:
        _fail(f"{P4_KEY} must contain a Phase 4 basis")
    return {
        "schema_version": SCHEMA_VERSION,
        P3_KEY: theory,
        P4_KEY: empirical,
    }


def heads_version(value: Mapping[str, Any]) -> str:
    """Return a deterministic digest suitable for stale Web decisions."""

    normalized = validate_heads(value)
    try:
        payload = json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        _fail(f"knowledge heads are not canonical JSON: {exc}", exc)
    return hashlib.sha256(payload).hexdigest()


def _heads(theory: Mapping[str, Any], empirical: Mapping[str, Any]) -> dict[str, Any]:
    return validate_heads({
        "schema_version": SCHEMA_VERSION,
        P3_KEY: theory,
        P4_KEY: empirical,
    })


def _available(
    *,
    phase_slug: str,
    method: Mapping[str, Any],
    generation: int,
    source_run_id: str,
    fragment: Mapping[str, Any],
    evidence_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        reference = knowledge_content.build_content_reference(
            phase_slug=phase_slug,
            fragment=fragment,
            evidence_index=evidence_index,
        )
        return knowledge_basis.available_basis(
            phase_slug=phase_slug,
            method_identity=method,
            content_reference=reference,
            generation=generation,
            source_run_id=source_run_id,
        )
    except (
        knowledge_content.KnowledgeContentError,
        knowledge_basis.KnowledgeBasisError,
    ) as exc:
        _corrupt(str(exc), exc)
    raise AssertionError("unreachable")


def _unknown(
    *,
    phase_slug: str,
    method: Mapping[str, Any],
    generation: int,
    source_run_id: str,
) -> dict[str, Any]:
    try:
        return knowledge_basis.unknown_legacy_basis(
            phase_slug=phase_slug,
            method_identity=method,
            generation=generation,
            source_run_id=source_run_id,
        )
    except knowledge_basis.KnowledgeBasisError as exc:
        _corrupt(str(exc), exc)
    raise AssertionError("unreachable")


def _absent(phase_slug: str) -> dict[str, Any]:
    return knowledge_basis.absent_basis(phase_slug=phase_slug)


def _live_theory_head(root: Path, stable_id: str) -> dict[str, Any]:
    try:
        record = theory_records.load_current_theory(root, stable_id)
    except theory_records.TheoryRecordError as exc:
        _corrupt(f"current Phase 3 package is invalid: {exc}", exc)
    if record is None:
        return _absent(knowledge_basis.THEORY_PHASE)

    method = record["method_identity"]
    generation = record["generation"]
    source_run_id = record["source_run_id"]
    if record.get("knowledge_file") is None:
        return _unknown(
            phase_slug=knowledge_basis.THEORY_PHASE,
            method=method,
            generation=generation,
            source_run_id=source_run_id,
        )
    if record.get("knowledge_file") != theory_records.KNOWLEDGE_FILENAME:
        _corrupt("current Phase 3 package names an unexpected knowledge fragment")

    fragment_path = (
        theory_records.current_theory_directory(root, stable_id)
        / theory_records.KNOWLEDGE_FILENAME
    )
    try:
        fragment_path = empirical_schema.safe_project_path(
            root,
            fragment_path,
            label="current Phase 3 knowledge fragment",
        )
        fragment, payload = knowledge_fragments.read_fragment(
            fragment_path,
            label="current Phase 3 knowledge fragment",
        )
        if (
            record.get("knowledge_size") != len(payload)
            or record.get("knowledge_sha256")
            != hashlib.sha256(payload).hexdigest()
        ):
            _corrupt(
                "current Phase 3 knowledge fragment does not match its record"
            )
        normalized = knowledge_fragments.validate_theory_fragment(
            fragment,
            expected_method=method,
            expected_generation=generation,
            expected_source_run_id=source_run_id,
            require_complete=True,
        )
    except KnowledgeHeadsError:
        raise
    except (
        empirical_schema.EmpiricalRecordError,
        knowledge_fragments.KnowledgeFragmentError,
    ) as exc:
        _corrupt(f"current Phase 3 knowledge fragment is invalid: {exc}", exc)
    return _available(
        phase_slug=knowledge_basis.THEORY_PHASE,
        method=method,
        generation=generation,
        source_run_id=source_run_id,
        fragment=normalized,
    )


def _package_entries(directory: Path) -> set[str] | None:
    try:
        metadata = directory.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        _corrupt("current Phase 4 package cannot be inspected", exc)
    if metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(
        metadata.st_mode
    ):
        _corrupt("current Phase 4 package must be a regular directory")
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        _corrupt("current Phase 4 package cannot be enumerated", exc)
    names = {entry.name for entry in entries}
    if len(names) != len(entries):
        _corrupt("current Phase 4 package contains duplicate entries")
    for entry in entries:
        try:
            entry_metadata = entry.lstat()
        except OSError as exc:
            _corrupt("current Phase 4 package entry cannot be inspected", exc)
        if metadata_is_link_or_reparse(entry_metadata) or not stat.S_ISREG(
            entry_metadata.st_mode
        ):
            _corrupt("current Phase 4 package entries must be regular files")
    return names


def _live_empirical_head(root: Path, stable_id: str) -> dict[str, Any]:
    try:
        directory = empirical_records.canonical_package_dir(root, stable_id)
    except empirical_schema.EmpiricalRecordError as exc:
        _corrupt(f"current Phase 4 package path is invalid: {exc}", exc)
    names = _package_entries(directory)
    if names is None or not names:
        return _absent(knowledge_basis.EMPIRICAL_PHASE)

    base = {
        empirical_records.SYNTHESIS_FILENAME,
        empirical_records.INDEX_FILENAME,
    }
    allowed = base | {empirical_records.KNOWLEDGE_FILENAME}
    if not base.issubset(names) or not names.issubset(allowed):
        _corrupt("current Phase 4 package is incomplete or has unexpected files")
    try:
        snapshot = empirical_schema.read_package(
            root,
            directory,
            expected_stable_id=stable_id,
            verify_current_artifacts=True,
            required=True,
            require_complete_knowledge=True,
        )
    except empirical_schema.EmpiricalRecordError as exc:
        _corrupt(f"current Phase 4 package is invalid: {exc}", exc)
    assert snapshot is not None
    if _package_entries(directory) != names:
        _corrupt("current Phase 4 package changed while heads were derived")

    index = snapshot.index
    method = index["method"]
    generation = index["generation"]
    source_run_id = index["source_run_id"]
    if snapshot.knowledge_bytes is None:
        return _unknown(
            phase_slug=knowledge_basis.EMPIRICAL_PHASE,
            method=method,
            generation=generation,
            source_run_id=source_run_id,
        )
    try:
        fragment = knowledge_fragments.parse_fragment(
            snapshot.knowledge_bytes,
            label="current Phase 4 knowledge fragment",
        )
        normalized = knowledge_fragments.validate_empirical_fragment(
            fragment,
            index,
            expected_method=method,
            expected_generation=generation,
            expected_source_run_id=source_run_id,
            require_complete=True,
        )
    except knowledge_fragments.KnowledgeFragmentError as exc:
        _corrupt(f"current Phase 4 knowledge fragment is invalid: {exc}", exc)
    return _available(
        phase_slug=knowledge_basis.EMPIRICAL_PHASE,
        method=method,
        generation=generation,
        source_run_id=source_run_id,
        fragment=normalized,
        evidence_index=index,
    )


def derive_live_heads(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, Any]:
    """Derive heads from verified canonical packages for one stable method."""

    root = _project_root(project_dir)
    method_id = _stable_id(stable_id)
    return _heads(
        _live_theory_head(root, method_id),
        _live_empirical_head(root, method_id),
    )


def _unique_json_object(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _corrupt(f"frozen JSON contains duplicate field {key!r}")
        value[key] = item
    return value


def _parse_json_object(
    payload: bytes,
    *,
    label: str,
    maximum: int,
) -> dict[str, Any]:
    if type(payload) is not bytes or not 1 <= len(payload) <= maximum:
        _corrupt(f"{label} has an invalid size")
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        _corrupt(f"{label} is not valid UTF-8", exc)
    try:
        value = json.loads(
            source,
            object_pairs_hook=_unique_json_object,
            parse_constant=lambda constant: _corrupt(
                f"{label} contains invalid numeric value {constant!r}"
            ),
        )
    except KnowledgeHeadsError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        _corrupt(f"{label} is not valid JSON: {exc}", exc)
    if not isinstance(value, dict):
        _corrupt(f"{label} must contain one JSON object")
    return value


def _path_component(value: Any, *, label: str) -> str:
    if type(value) is not str or _PATH_COMPONENT_RE.fullmatch(value) is None:
        _fail(f"{label} must be a bounded safe path component")
    return value


def _safe_frozen_path(context_root: Path, value: Any) -> Path:
    if type(value) is not str or not value or "\x00" in value:
        _corrupt("frozen current-record path must be a nonempty absolute path")
    candidate = Path(value)
    lexical = Path(os.path.abspath(candidate))
    if not candidate.is_absolute() or candidate != lexical:
        _corrupt("frozen current-record path must be absolute and normalized")
    try:
        relative = candidate.relative_to(context_root)
    except ValueError as exc:
        _corrupt("frozen current-record path escaped its run context", exc)
    if not relative.parts or relative.parts[0] != "current":
        _corrupt("frozen current-record path must be under context/current")

    current = context_root
    components = (None, *relative.parts)
    for index, part in enumerate(components):
        if part is not None:
            current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            _corrupt(f"frozen current-record path is unavailable: {current}", exc)
        if metadata_is_link_or_reparse(metadata):
            _corrupt("frozen current-record path must not use links or junctions")
        if index == len(components) - 1:
            if not stat.S_ISREG(metadata.st_mode):
                _corrupt("frozen current-record path must name a regular file")
        elif not stat.S_ISDIR(metadata.st_mode):
            _corrupt("frozen current-record parent must be a directory")
    return candidate


def _source_path(value: Any) -> str:
    if type(value) is not str or not value or "\x00" in value or "\\" in value:
        _corrupt("frozen source_path must be normalized project-relative text")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or ":" in relative.parts[0]
        or relative.as_posix() != value
    ):
        _corrupt("frozen source_path must be a normalized project-relative path")
    return value


def _file_metadata(value: Any) -> dict[str, Any]:
    file_record = _mapping(value, label="frozen current-record file")
    _exact_fields(
        file_record,
        _FILE_FIELDS,
        label="frozen current-record file",
    )
    digest = file_record["sha256"]
    size = file_record["size"]
    if type(digest) is not str or _SHA256_RE.fullmatch(digest) is None:
        _corrupt("frozen current-record sha256 must be a lowercase digest")
    if type(size) is not int or size < 1:
        _corrupt("frozen current-record size must be a positive integer")
    return {
        "path": file_record["path"],
        "sha256": digest,
        "source_path": _source_path(file_record["source_path"]),
        "size": size,
    }


def _inventory(
    current_records: Any,
    *,
    manifest_schema_version: int,
) -> dict[str, dict[str, Any]]:
    if (
        not isinstance(current_records, list)
        or len(current_records) > MAX_FROZEN_RECORDS
    ):
        _fail(
            f"frozen current_records must contain at most "
            f"{MAX_FROZEN_RECORDS} records"
        )
    inventory: dict[str, dict[str, Any]] = {}
    seen_paths: set[str] = set()
    seen_sources: set[str] = set()
    for raw_record in current_records:
        record = _mapping(raw_record, label="frozen current record")
        expected_fields = (
            _SCHEMA_13_RECORD_FIELDS
            if manifest_schema_version >= 13
            else _RECORD_FIELDS
        )
        _exact_fields(record, expected_fields, label="frozen current record")
        key = record["key"]
        kind = record["kind"]
        if type(key) is not str or not key or len(key) > 200:
            _corrupt("frozen current-record key is invalid")
        if key in inventory:
            _corrupt(f"frozen current_records contains duplicate key {key!r}")
        if type(kind) is not str or not kind or len(kind) > 200:
            _corrupt("frozen current-record kind is invalid")
        method_identity: dict[str, str] | None = None
        if manifest_schema_version >= 13:
            raw_identity = record["method_identity"]
            if key in {P3_KEY, P4_KEY}:
                if raw_identity is None:
                    _corrupt(
                        f"method-aware frozen {key} requires method_identity"
                    )
                method_identity = _method_identity(
                    raw_identity,
                    label=f"method-aware frozen {key} method_identity",
                )
            elif raw_identity is not None:
                _corrupt(
                    "method-aware nonmethod current record must have null "
                    "method_identity"
                )
        files = record["files"]
        if (
            not isinstance(files, list)
            or not 1 <= len(files) <= MAX_FILES_PER_RECORD
        ):
            _corrupt("frozen current record has an invalid file list")
        normalized_files = [_file_metadata(item) for item in files]
        for file_record in normalized_files:
            path = str(file_record["path"])
            source = file_record["source_path"]
            if path in seen_paths or source in seen_sources:
                _corrupt("frozen current_records contains duplicate files")
            seen_paths.add(path)
            seen_sources.add(source)
        inventory[key] = {
            "key": key,
            "kind": kind,
            "source_run_id": record["source_run_id"],
            "generation": record["generation"],
            "method_identity": method_identity,
            "files": normalized_files,
        }
    return inventory


def _read_frozen_file(
    context_root: Path,
    file_record: Mapping[str, Any],
    *,
    maximum: int,
    label: str,
) -> bytes:
    if file_record["size"] > maximum:
        _corrupt(f"{label} exceeds its byte limit")
    path = _safe_frozen_path(context_root, file_record["path"])
    try:
        payload = project_state.bounded_file_bytes(
            path,
            maximum=maximum,
            label=label,
            allow_empty=False,
        )
    except project_state.ProjectStateError as exc:
        _corrupt(str(exc), exc)
    if (
        len(payload) != file_record["size"]
        or not hmac.compare_digest(
            hashlib.sha256(payload).hexdigest(),
            file_record["sha256"],
        )
    ):
        _corrupt(f"{label} does not match its recorded size and SHA-256")
    return payload


def _files_by_source(
    record: Mapping[str, Any],
    *,
    expected: set[str],
    required: set[str],
) -> dict[str, Mapping[str, Any]]:
    files = {
        str(item["source_path"]): item
        for item in record["files"]
    }
    if not required.issubset(files) or not set(files).issubset(expected):
        _corrupt(
            f"frozen {record['key']} package is incomplete or has "
            "unexpected source files"
        )
    return files


def _theory_source_paths(stable_id: str) -> dict[str, str]:
    parent = (
        PurePosixPath("branches")
        / stable_id
        / "evaluations"
        / "current"
    )
    return {
        "manuscript": (parent / theory_records.THEORY_FILENAME).as_posix(),
        "record": (parent / theory_records.RECORD_FILENAME).as_posix(),
        "knowledge": (parent / theory_records.KNOWLEDGE_FILENAME).as_posix(),
    }


def _empirical_source_paths(stable_id: str) -> dict[str, str]:
    parent = (
        PurePosixPath("branches")
        / stable_id
        / "draft"
        / "sections"
        / "current"
    )
    return {
        "synthesis": (
            parent / empirical_records.SYNTHESIS_FILENAME
        ).as_posix(),
        "index": (parent / empirical_records.INDEX_FILENAME).as_posix(),
        "knowledge": (
            parent / empirical_records.KNOWLEDGE_FILENAME
        ).as_posix(),
    }


def _frozen_literature_source(
    context_root: Path,
    record: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the exact frozen Phase 1 summary and reference index."""

    if record is None:
        return None
    if record["kind"] != P1_KIND:
        _corrupt(f"frozen {P1_KEY} has an unexpected kind")
    generation = _generation(
        record["generation"],
        label=f"frozen {P1_KEY} generation",
    )
    source_run_id = _source_run_id(
        record["source_run_id"],
        label=f"frozen {P1_KEY} source_run_id",
    )
    paths = {
        "summary": "references/literature-summary.md",
        "index": "references/reference-index.json",
    }
    files = _files_by_source(
        record,
        expected=set(paths.values()),
        required=set(paths.values()),
    )
    summary = _read_frozen_file(
        context_root,
        files[paths["summary"]],
        maximum=_MAX_LITERATURE_FILE_BYTES,
        label="frozen Phase 1 literature summary",
    )
    index = _read_frozen_file(
        context_root,
        files[paths["index"]],
        maximum=_MAX_LITERATURE_FILE_BYTES,
        label="frozen Phase 1 reference index",
    )
    return {
        "generation": generation,
        "source_run_id": source_run_id,
        "summary_bytes": summary,
        "summary_sha256": files[paths["summary"]]["sha256"],
        "index_bytes": index,
        "index_sha256": files[paths["index"]]["sha256"],
    }


def _frozen_theory_state(
    context_root: Path,
    stable_id: str,
    record: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return one verified frozen theory head and its staging source."""

    if record is None:
        return _absent(knowledge_basis.THEORY_PHASE), None
    if record["kind"] != P3_KIND:
        _corrupt(f"frozen {P3_KEY} has an unexpected kind")
    top_generation = _generation(
        record["generation"],
        label=f"frozen {P3_KEY} generation",
    )
    top_run = _source_run_id(
        record["source_run_id"],
        label=f"frozen {P3_KEY} source_run_id",
    )
    paths = _theory_source_paths(stable_id)
    files = _files_by_source(
        record,
        expected=set(paths.values()),
        required={paths["manuscript"], paths["record"]},
    )
    manuscript = _read_frozen_file(
        context_root,
        files[paths["manuscript"]],
        maximum=_MAX_THEORY_MANUSCRIPT_BYTES,
        label="frozen Phase 3 manuscript",
    )
    record_payload = _read_frozen_file(
        context_root,
        files[paths["record"]],
        maximum=_MAX_THEORY_RECORD_BYTES,
        label="frozen Phase 3 record",
    )
    raw_record = _parse_json_object(
        record_payload,
        label="frozen Phase 3 record",
        maximum=_MAX_THEORY_RECORD_BYTES,
    )
    try:
        normalized_record = theory_records._normalize_current_record(
            raw_record,
            label="frozen Phase 3 record",
        )
    except theory_records.TheoryRecordError as exc:
        _corrupt(str(exc), exc)

    method = normalized_record["method_identity"]
    generation = normalized_record["generation"]
    source_run_id = normalized_record["source_run_id"]
    if method["stable_id"] != stable_id:
        _corrupt("frozen Phase 3 record belongs to another method")
    if (
        record.get("method_identity") is not None
        and record["method_identity"] != method
    ):
        _corrupt(
            "frozen Phase 3 record does not match the current method identity "
            "(method_identity)"
        )
    if generation != top_generation or source_run_id != top_run:
        _corrupt(
            "frozen Phase 3 record does not match its inventory provenance"
        )
    if (
        normalized_record["manuscript_size"] != len(manuscript)
        or normalized_record["manuscript_sha256"]
        != hashlib.sha256(manuscript).hexdigest()
    ):
        _corrupt("frozen Phase 3 manuscript does not match its record")

    source = {
        "record": normalized_record,
        "manuscript_bytes": manuscript,
        "knowledge_fragment": None,
    }
    expects_knowledge = (
        normalized_record.get("knowledge_file")
        == theory_records.KNOWLEDGE_FILENAME
    )
    has_knowledge = paths["knowledge"] in files
    if not expects_knowledge:
        if has_knowledge:
            _corrupt("legacy frozen Phase 3 package has an unbound fragment")
        return (
            _unknown(
                phase_slug=knowledge_basis.THEORY_PHASE,
                method=method,
                generation=generation,
                source_run_id=source_run_id,
            ),
            source,
        )
    if not has_knowledge:
        _corrupt("frozen Phase 3 package is missing its knowledge fragment")
    fragment_payload = _read_frozen_file(
        context_root,
        files[paths["knowledge"]],
        maximum=knowledge_fragments.MAX_KNOWLEDGE_BYTES,
        label="frozen Phase 3 knowledge fragment",
    )
    if (
        normalized_record.get("knowledge_size") != len(fragment_payload)
        or normalized_record.get("knowledge_sha256")
        != hashlib.sha256(fragment_payload).hexdigest()
    ):
        _corrupt("frozen Phase 3 fragment does not match its record")
    try:
        fragment = knowledge_fragments.parse_fragment(
            fragment_payload,
            label="frozen Phase 3 knowledge fragment",
        )
        normalized = knowledge_fragments.validate_theory_fragment(
            fragment,
            expected_method=method,
            expected_generation=generation,
            expected_source_run_id=source_run_id,
            require_complete=True,
        )
    except knowledge_fragments.KnowledgeFragmentError as exc:
        _corrupt(f"frozen Phase 3 knowledge fragment is invalid: {exc}", exc)
    source["knowledge_fragment"] = normalized
    return (
        _available(
            phase_slug=knowledge_basis.THEORY_PHASE,
            method=method,
            generation=generation,
            source_run_id=source_run_id,
            fragment=normalized,
        ),
        source,
    )


def _verify_referenced_empirical_artifacts(
    root: Path,
    index: Mapping[str, Any],
) -> None:
    """Verify every immutable artifact retained by a frozen P4 index."""

    total = 0
    for number, entry in enumerate(index["entries"], start=1):
        if entry["status"] != "current":
            continue
        try:
            _, artifact_path = empirical_schema.normalized_relative_path(
                root,
                entry["path"],
                label=f"frozen evidence entry {number} artifact",
            )
            digest, size = project_state.bounded_file_digest(
                artifact_path,
                maximum=empirical_schema.MAX_CURRENT_ARTIFACT_BYTES,
                label=f"frozen evidence entry {number} artifact",
                allow_empty=True,
            )
        except (
            empirical_schema.EmpiricalRecordError,
            project_state.ProjectStateError,
        ) as exc:
            _corrupt(
                f"frozen Phase 4 evidence artifact is invalid: {exc}",
                exc,
            )
        if (
            size != entry["size"]
            or not hmac.compare_digest(digest, entry["sha256"])
        ):
            _corrupt(
                "frozen Phase 4 evidence artifact does not match its "
                "recorded size and SHA-256"
            )
        total += size
        if total > empirical_schema.MAX_CURRENT_ARTIFACT_TOTAL_BYTES:
            _corrupt("frozen Phase 4 evidence artifacts exceed the byte limit")


def _frozen_empirical_state(
    root: Path,
    context_root: Path,
    stable_id: str,
    record: Mapping[str, Any] | None,
    *,
    verify_referenced_artifacts: bool,
) -> tuple[dict[str, Any], empirical_schema.PackageSnapshot | None]:
    """Return one verified frozen empirical head and its staging source."""

    if record is None:
        return _absent(knowledge_basis.EMPIRICAL_PHASE), None
    if record["kind"] != P4_KIND:
        _corrupt(f"frozen {P4_KEY} has an unexpected kind")
    top_generation = _generation(
        record["generation"],
        label=f"frozen {P4_KEY} generation",
    )
    top_run = _source_run_id(
        record["source_run_id"],
        label=f"frozen {P4_KEY} source_run_id",
    )
    paths = _empirical_source_paths(stable_id)
    files = _files_by_source(
        record,
        expected=set(paths.values()),
        required={paths["synthesis"], paths["index"]},
    )
    synthesis = _read_frozen_file(
        context_root,
        files[paths["synthesis"]],
        maximum=empirical_records.MAX_SYNTHESIS_BYTES,
        label="frozen Phase 4 synthesis",
    )
    index_payload = _read_frozen_file(
        context_root,
        files[paths["index"]],
        maximum=empirical_records.MAX_INDEX_BYTES,
        label="frozen Phase 4 evidence index",
    )
    try:
        raw_index = empirical_schema.parse_index(
            index_payload,
            label="frozen Phase 4 evidence index",
        )
        index = empirical_schema.validate_index(
            root,
            raw_index,
            synthesis,
            expected_stable_id=stable_id,
            verify_current_artifacts=False,
        )
    except empirical_schema.EmpiricalRecordError as exc:
        _corrupt(f"frozen Phase 4 evidence index is invalid: {exc}", exc)

    method = index["method"]
    generation = index["generation"]
    source_run_id = index["source_run_id"]
    if generation != top_generation or source_run_id != top_run:
        _corrupt(
            "frozen Phase 4 index does not match its inventory provenance"
        )
    if (
        record.get("method_identity") is not None
        and record["method_identity"] != method
    ):
        _corrupt(
            "frozen Phase 4 index does not match the current method identity "
            "(method_identity)"
        )
    if verify_referenced_artifacts:
        _verify_referenced_empirical_artifacts(root, index)

    fragment_payload = None
    if paths["knowledge"] in files:
        fragment_payload = _read_frozen_file(
            context_root,
            files[paths["knowledge"]],
            maximum=knowledge_fragments.MAX_KNOWLEDGE_BYTES,
            label="frozen Phase 4 knowledge fragment",
        )
    snapshot = empirical_schema.PackageSnapshot(
        index=index,
        synthesis_bytes=synthesis,
        index_bytes=index_payload,
        knowledge_bytes=fragment_payload,
    )
    if fragment_payload is None:
        return (
            _unknown(
                phase_slug=knowledge_basis.EMPIRICAL_PHASE,
                method=method,
                generation=generation,
                source_run_id=source_run_id,
            ),
            snapshot,
        )
    try:
        fragment = knowledge_fragments.parse_fragment(
            fragment_payload,
            label="frozen Phase 4 knowledge fragment",
        )
        normalized = knowledge_fragments.validate_empirical_fragment(
            fragment,
            index,
            expected_method=method,
            expected_generation=generation,
            expected_source_run_id=source_run_id,
            require_complete=True,
        )
    except knowledge_fragments.KnowledgeFragmentError as exc:
        _corrupt(f"frozen Phase 4 knowledge fragment is invalid: {exc}", exc)
    return (
        _available(
            phase_slug=knowledge_basis.EMPIRICAL_PHASE,
            method=method,
            generation=generation,
            source_run_id=source_run_id,
            fragment=normalized,
            evidence_index=index,
        ),
        snapshot,
    )


def _frozen_manifest_inventory(
    project_dir: str | Path,
    manifest: Mapping[str, Any],
    stable_id: str | None,
) -> tuple[Path, Path, str | None, dict[str, dict[str, Any]]]:
    root = _project_root(project_dir)
    method_id = _stable_id(stable_id) if stable_id is not None else None
    source = _mapping(manifest, label="run manifest")
    schema_version = source.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version not in SUPPORTED_FROZEN_MANIFEST_SCHEMAS
    ):
        _fail("frozen heads require run manifest schema 12 or 13")
    phase_slug = _path_component(
        source.get("phase_slug"),
        label="run manifest phase_slug",
    )
    run_id = _path_component(
        source.get("run_id"),
        label="run manifest run_id",
    )
    snapshots = _mapping(source.get("snapshots"), label="run snapshots")
    if "current_records" not in snapshots:
        _fail("run snapshots are missing current_records")
    inventory = _inventory(
        snapshots["current_records"],
        manifest_schema_version=schema_version,
    )
    context_root = (
        project_state.state_dir(root)
        / "runs"
        / phase_slug
        / f"{run_id}.context"
    )
    return root, context_root, method_id, inventory


def derive_frozen_launch_state(
    project_dir: str | Path,
    manifest: Mapping[str, Any],
    stable_id: str | None = None,
) -> dict[str, Any]:
    """Derive heads and staging sources from one frozen launch inventory."""

    root, context_root, method_id, inventory = _frozen_manifest_inventory(
        project_dir,
        manifest,
        stable_id,
    )
    literature_source = _frozen_literature_source(
        context_root,
        inventory.get(P1_KEY),
    )
    if method_id is None:
        if P3_KEY in inventory or P4_KEY in inventory:
            _corrupt(
                "nonmethod frozen launch inventory contains branch records"
            )
        theory_source = None
        empirical_source = None
        heads = None
    else:
        theory_head, theory_source = _frozen_theory_state(
            context_root,
            method_id,
            inventory.get(P3_KEY),
        )
        empirical_head, empirical_source = _frozen_empirical_state(
            root,
            context_root,
            method_id,
            inventory.get(P4_KEY),
            verify_referenced_artifacts=True,
        )
        heads = _heads(theory_head, empirical_head)
    return {
        "knowledge_heads": heads,
        P1_KEY: literature_source,
        P3_KEY: theory_source,
        P4_KEY: empirical_source,
    }


def derive_frozen_heads(
    project_dir: str | Path,
    manifest: Mapping[str, Any],
    stable_id: str,
) -> dict[str, Any]:
    """Derive heads only from one schema 12 or 13 frozen run manifest."""

    root, context_root, method_id, inventory = _frozen_manifest_inventory(
        project_dir,
        manifest,
        stable_id,
    )
    theory_head, _ = _frozen_theory_state(
        context_root,
        method_id,
        inventory.get(P3_KEY),
    )
    empirical_head, _ = _frozen_empirical_state(
        root,
        context_root,
        method_id,
        inventory.get(P4_KEY),
        verify_referenced_artifacts=False,
    )
    return _heads(theory_head, empirical_head)
