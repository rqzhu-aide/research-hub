"""Frozen Phase 5 launch inputs and upstream scientific basis.

Schema 12 through 14 Phase 5 runs use this module to project one immutable launch
inventory into two values:

* the exact current manuscript, or its explicit absence; and
* the exact Phase 1 through Phase 4 basis used by the submitted manuscript.

No function in this module reads a live phase record.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from core import empirical_records, literature_records, manuscript_records, theory_records
from core.filesystem_utils import metadata_is_link_or_reparse
from core.strict_json import StrictJsonError, parse_json_object


MANIFEST_SCHEMA_VERSION = 14
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = frozenset({12, 13, MANIFEST_SCHEMA_VERSION})
P1_KEY = "p1_literature"
P3_KEY = "p3_theory"
P4_KEY = "p4_empirical"
P5_KEY = "p5_manuscript"

_MAX_RECORDS = 16
_MAX_FILES_PER_RECORD = 4
_MAX_SELECTED_METHOD_BYTES = 2 * 1024 * 1024
_MAX_LITERATURE_BYTES = 5 * 1024 * 1024
_MAX_THEORY_RECORD_BYTES = 256 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,299}$")
_BASE_RECORD_FIELDS = {
    "key",
    "kind",
    "source_run_id",
    "generation",
    "method_identity",
    "files",
}
_SCHEMA_12_RECORD_FIELDS = _BASE_RECORD_FIELDS - {"method_identity"}
_FILE_FIELDS = {"path", "sha256", "source_path", "size"}


class Phase5ProjectionError(ValueError):
    """A schema 12 or 13 Phase 5 launch projection is invalid or corrupt."""


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Phase5ProjectionError(f"{label} must be an object")
    return value


def _positive_generation(value: Any, *, label: str) -> int:
    if type(value) is not int or value < 1:
        raise Phase5ProjectionError(f"{label} must be a positive integer")
    return value


def _method_identity(value: Mapping[str, Any]) -> dict[str, str]:
    try:
        return theory_records.normalize_method_identity(value)
    except theory_records.TheoryValidationError as exc:
        raise Phase5ProjectionError(
            f"selected method identity is invalid: {exc}"
        ) from exc


def _context_root(
    project_dir: str | Path,
    manifest: Mapping[str, Any],
) -> tuple[Path, Path]:
    root = Path(project_dir).resolve()
    phase_slug = manifest.get("phase_slug")
    run_id = manifest.get("run_id")
    if (
        type(phase_slug) is not str
        or _COMPONENT_RE.fullmatch(phase_slug) is None
        or type(run_id) is not str
        or _COMPONENT_RE.fullmatch(run_id) is None
    ):
        raise Phase5ProjectionError(
            "run manifest has an invalid phase or run identity"
        )

    # Local import avoids a module cycle because project_state imports
    # phase_records, which imports this module.
    from core import project_state

    context_root = (
        project_state.state_dir(root)
        / "runs"
        / phase_slug
        / f"{run_id}.context"
    ).resolve(strict=False)
    return root, context_root


def _source_path(value: Any) -> str:
    if type(value) is not str or not value or "\x00" in value:
        raise Phase5ProjectionError("frozen current-record source path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise Phase5ProjectionError("frozen current-record source path is invalid")
    return value


def _file_metadata(value: Any) -> dict[str, Any]:
    file_record = _mapping(value, label="frozen current-record file")
    if set(file_record) != _FILE_FIELDS:
        raise Phase5ProjectionError(
            "frozen current-record file has unsupported fields"
        )
    path = file_record.get("path")
    digest = file_record.get("sha256")
    size = file_record.get("size")
    if (
        type(path) is not str
        or not path
        or "\x00" in path
        or type(digest) is not str
        or _SHA256_RE.fullmatch(digest) is None
        or type(size) is not int
        or size < 1
    ):
        raise Phase5ProjectionError(
            "frozen current-record file metadata is invalid"
        )
    return {
        "path": path,
        "sha256": digest,
        "source_path": _source_path(file_record.get("source_path")),
        "size": size,
    }


def _inventory(
    value: Any,
    *,
    manifest_schema_version: int,
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or len(value) > _MAX_RECORDS:
        raise Phase5ProjectionError(
            f"frozen current_records must contain at most {_MAX_RECORDS} records"
        )
    inventory: dict[str, dict[str, Any]] = {}
    seen_paths: set[str] = set()
    seen_sources: set[str] = set()
    for raw in value:
        record = _mapping(raw, label="frozen current record")
        expected_fields = (
            _BASE_RECORD_FIELDS
            if manifest_schema_version >= 13
            else _SCHEMA_12_RECORD_FIELDS
        )
        if set(record) != expected_fields:
            raise Phase5ProjectionError(
                "frozen current record has unsupported fields"
            )
        key = record.get("key")
        kind = record.get("kind")
        if (
            type(key) is not str
            or not key
            or len(key) > 200
            or key in inventory
            or type(kind) is not str
            or not kind
            or len(kind) > 200
        ):
            raise Phase5ProjectionError(
                "frozen current record has invalid identity metadata"
            )
        files = record.get("files")
        if (
            not isinstance(files, list)
            or not 1 <= len(files) <= _MAX_FILES_PER_RECORD
        ):
            raise Phase5ProjectionError(
                "frozen current record has an invalid file list"
            )
        normalized_files = [_file_metadata(item) for item in files]
        for file_record in normalized_files:
            path = file_record["path"]
            source = file_record["source_path"]
            if path in seen_paths or source in seen_sources:
                raise Phase5ProjectionError(
                    "frozen current records contain duplicate files"
                )
            seen_paths.add(path)
            seen_sources.add(source)
        record_identity: dict[str, str] | None = None
        if manifest_schema_version >= 13:
            raw_identity = record.get("method_identity")
            if key in {P3_KEY, P4_KEY}:
                if not isinstance(raw_identity, Mapping):
                    raise Phase5ProjectionError(
                        f"frozen {key} requires an exact method identity"
                    )
                record_identity = _method_identity(raw_identity)
            elif raw_identity is not None:
                raise Phase5ProjectionError(
                    "nonmethod frozen current record must have null "
                    "method_identity"
                )
        inventory[key] = {
            "key": key,
            "kind": kind,
            "source_run_id": record.get("source_run_id"),
            "generation": record.get("generation"),
            "method_identity": record_identity,
            "files": normalized_files,
        }
    return inventory


def _snapshot_bytes(
    context_root: Path,
    file_record: Mapping[str, Any],
    *,
    maximum: int,
    label: str,
) -> bytes:
    size = file_record["size"]
    if type(size) is not int or size < 1 or size > maximum:
        raise Phase5ProjectionError(f"{label} exceeds its byte limit")
    raw_path = Path(file_record["path"])
    try:
        contained_root = context_root.resolve(strict=True)
        lexical_relative = raw_path.relative_to(contained_root)
        cursor = contained_root
        for part in lexical_relative.parts:
            cursor = cursor / part
            if metadata_is_link_or_reparse(cursor.lstat()):
                raise Phase5ProjectionError(
                    f"{label} must not use symbolic links"
                )
        candidate = raw_path.resolve(strict=True)
        relative = candidate.relative_to(contained_root)
    except (OSError, ValueError) as exc:
        raise Phase5ProjectionError(
            f"{label} is outside the sealed run context"
        ) from exc
    if relative != lexical_relative:
        raise Phase5ProjectionError(f"{label} must not use symbolic links")
    cursor = contained_root
    for part in relative.parts:
        cursor = cursor / part
        try:
            if metadata_is_link_or_reparse(cursor.lstat()):
                raise Phase5ProjectionError(
                    f"{label} must not use symbolic links"
                )
        except OSError as exc:
            raise Phase5ProjectionError(f"{label} cannot be inspected") from exc
    try:
        payload = candidate.read_bytes()
    except OSError as exc:
        raise Phase5ProjectionError(f"{label} cannot be read") from exc
    if (
        len(payload) != size
        or not hmac.compare_digest(
            hashlib.sha256(payload).hexdigest(),
            file_record["sha256"],
        )
    ):
        raise Phase5ProjectionError(
            f"{label} does not match the sealed launch inventory"
        )
    return payload


def _source_files(
    context_root: Path,
    record: Mapping[str, Any],
    requirements: Mapping[str, tuple[int, str]],
) -> dict[str, bytes]:
    by_source = {
        str(item["source_path"]): item
        for item in record["files"]
    }
    missing = set(requirements).difference(by_source)
    if missing:
        raise Phase5ProjectionError(
            "frozen current record is missing required files: "
            + ", ".join(sorted(missing))
        )
    return {
        source: _snapshot_bytes(
            context_root,
            by_source[source],
            maximum=maximum,
            label=label,
        )
        for source, (maximum, label) in requirements.items()
    }


def _record(
    inventory: Mapping[str, Mapping[str, Any]],
    key: str,
    *,
    kind: str,
    method: Mapping[str, str] | None,
) -> Mapping[str, Any]:
    record = inventory.get(key)
    if record is None:
        raise Phase5ProjectionError(f"Phase 5 launch is missing frozen {key}")
    if record["kind"] != kind:
        raise Phase5ProjectionError(f"frozen {key} has an invalid kind")
    if method is not None and record["method_identity"] != method:
        raise Phase5ProjectionError(
            f"frozen {key} does not match the selected method"
        )
    _positive_generation(record["generation"], label=f"frozen {key} generation")
    return record


def _relative_directory(root: Path, directory: Path) -> str:
    try:
        return directory.resolve(strict=False).relative_to(root).as_posix()
    except ValueError as exc:
        raise Phase5ProjectionError(
            "canonical current-record path escaped the project"
        ) from exc


def _frozen_current_manuscript(
    root: Path,
    context_root: Path,
    inventory: Mapping[str, Mapping[str, Any]],
    method: Mapping[str, str],
) -> dict[str, Any] | None:
    record_inventory = inventory.get(P5_KEY)
    if record_inventory is None:
        return None
    if record_inventory["kind"] != "current_manuscript":
        raise Phase5ProjectionError("frozen p5_manuscript has an invalid kind")
    generation = _positive_generation(
        record_inventory["generation"],
        label="frozen p5_manuscript generation",
    )
    directory = _relative_directory(
        root,
        manuscript_records.current_manuscript_directory(
            root, method["stable_id"]
        ),
    )
    manuscript_source = f"{directory}/{manuscript_records.MANUSCRIPT_FILENAME}"
    record_source = f"{directory}/{manuscript_records.RECORD_FILENAME}"
    files = _source_files(
        context_root,
        record_inventory,
        {
            manuscript_source: (
                manuscript_records.MAX_MANUSCRIPT_BYTES,
                "frozen current manuscript",
            ),
            record_source: (
                manuscript_records.MAX_RECORD_BYTES,
                "frozen current manuscript record",
            ),
        },
    )
    try:
        raw_record = parse_json_object(
            files[record_source], label="frozen current manuscript record"
        )
    except StrictJsonError as exc:
        raise Phase5ProjectionError(str(exc)) from exc
    try:
        normalized = manuscript_records._normalize_current_record(
            raw_record,
            label="frozen current manuscript record",
        )
    except manuscript_records.ManuscriptRecordError as exc:
        raise Phase5ProjectionError(str(exc)) from exc
    payload = files[manuscript_source]
    if (
        normalized["method_identity"]["stable_id"] != method["stable_id"]
        or normalized["generation"] != generation
        or normalized["source_run_id"] != record_inventory["source_run_id"]
        or normalized["manuscript_size"] != len(payload)
        or not hmac.compare_digest(
            normalized["manuscript_sha256"],
            hashlib.sha256(payload).hexdigest(),
        )
    ):
        raise Phase5ProjectionError(
            "frozen current manuscript does not match its record"
        )
    return {
        "record": normalized,
        "manuscript_bytes": payload,
    }


def derive_frozen_phase5_state(
    project_dir: str | Path,
    manifest: Mapping[str, Any],
    method_identity: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a schema 12 through 14 inventory without reading live records."""

    source = _mapping(manifest, label="run manifest")
    schema_version = source.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS
    ):
        raise Phase5ProjectionError(
            "frozen Phase 5 projection requires run manifest schema 12, 13, or 14"
        )
    root, context_root = _context_root(project_dir, source)
    snapshots = _mapping(source.get("snapshots"), label="run snapshots")
    inventory = _inventory(
        snapshots.get("current_records"),
        manifest_schema_version=schema_version,
    )
    method = _method_identity(method_identity)

    selected = _mapping(
        snapshots.get("selected_method"),
        label="frozen selected method",
    )
    selected_digest = selected.get(
        "definition_sha256" if schema_version >= 14 else "sha256"
    )
    if (
        selected.get("stable_id") != method["stable_id"]
        or selected.get("version") != method["version"]
        or selected_digest != method["definition_sha256"]
    ):
        raise Phase5ProjectionError(
            "frozen selected method does not match the run method identity"
        )
    selected_path = Path(str(selected.get("path")))
    try:
        selected_size = selected_path.stat().st_size
    except OSError as exc:
        raise Phase5ProjectionError(
            "frozen selected method cannot be inspected"
        ) from exc
    _snapshot_bytes(
        context_root,
        {
            "path": str(selected_path),
            "sha256": selected_digest,
            "size": selected_size,
        },
        maximum=_MAX_SELECTED_METHOD_BYTES,
        label="frozen selected method",
    )

    if schema_version == 12:
        from core import knowledge_heads

        try:
            frozen_heads = knowledge_heads.derive_frozen_heads(
                root,
                source,
                method["stable_id"],
            )
        except knowledge_heads.KnowledgeHeadsError as exc:
            raise Phase5ProjectionError(
                f"frozen schema 12 Phase 3/4 basis is invalid: {exc}"
            ) from exc
        for key in (P3_KEY, P4_KEY):
            head = frozen_heads.get(key)
            if (
                not isinstance(head, Mapping)
                or head.get("method_identity") != method
                or key not in inventory
            ):
                raise Phase5ProjectionError(
                    "frozen schema 12 Phase 3/4 basis does not match the "
                    "selected method"
                )
            inventory[key]["method_identity"] = dict(method)

    literature = _record(
        inventory,
        P1_KEY,
        kind="current_literature",
        method=None,
    )
    theory = _record(
        inventory,
        P3_KEY,
        kind="current_theory",
        method=method,
    )
    empirical = _record(
        inventory,
        P4_KEY,
        kind="current_empirical",
        method=method,
    )

    literature_source = Path(literature_records.LITERATURE_SUMMARY).as_posix()
    literature_index_source = Path(literature_records.REFERENCE_INDEX).as_posix()
    theory_directory = _relative_directory(
        root,
        theory_records.current_theory_directory(root, method["stable_id"]),
    )
    empirical_directory = _relative_directory(
        root,
        empirical_records.canonical_package_dir(root, method["stable_id"]),
    )
    theory_record_source = (
        f"{theory_directory}/{theory_records.RECORD_FILENAME}"
    )
    empirical_synthesis_source = (
        f"{empirical_directory}/{empirical_records.SYNTHESIS_FILENAME}"
    )
    empirical_index_source = (
        f"{empirical_directory}/{empirical_records.INDEX_FILENAME}"
    )

    literature_files = _source_files(
        context_root,
        literature,
        {
            literature_source: (
                _MAX_LITERATURE_BYTES,
                "frozen literature synthesis",
            ),
            literature_index_source: (
                _MAX_LITERATURE_BYTES,
                "frozen Phase 1 reference index",
            ),
        },
    )
    theory_files = _source_files(
        context_root,
        theory,
        {
            theory_record_source: (
                _MAX_THEORY_RECORD_BYTES,
                "frozen Phase 3 record",
            ),
        },
    )
    empirical_files = _source_files(
        context_root,
        empirical,
        {
            empirical_synthesis_source: (
                empirical_records.MAX_SYNTHESIS_BYTES,
                "frozen empirical synthesis",
            ),
            empirical_index_source: (
                empirical_records.MAX_INDEX_BYTES,
                "frozen empirical evidence index",
            ),
        },
    )

    try:
        frozen_literature = (
            literature_records.normalize_frozen_literature_source(
                {
                    "generation": literature["generation"],
                    "source_run_id": literature["source_run_id"],
                    "summary_bytes": literature_files[literature_source],
                    "summary_sha256": hashlib.sha256(
                        literature_files[literature_source]
                    ).hexdigest(),
                    "index_bytes": literature_files[literature_index_source],
                    "index_sha256": hashlib.sha256(
                        literature_files[literature_index_source]
                    ).hexdigest(),
                }
            )
        )
    except literature_records.LiteratureRecordError as exc:
        raise Phase5ProjectionError(
            f"frozen Phase 1 literature record is invalid: {exc}"
        ) from exc
    if frozen_literature is None:
        raise Phase5ProjectionError(
            "frozen Phase 1 literature record is unexpectedly absent"
        )

    basis = {
        "p1_synthesis": {
            "identity": "literature-synthesis",
            "sha256": frozen_literature["summary_sha256"],
            "generation": frozen_literature["generation"],
        },
        "p1_collection": {
            "identity": "reference-card-collection",
            "sha256": frozen_literature["papers_sha256"],
            "generation": frozen_literature["generation"],
        },
        "p2_definition": {
            "identity": method,
            "sha256": selected_digest,
            "generation": None,
        },
        "p3_record": {
            "identity": f"{method['stable_id']}:theory",
            "sha256": hashlib.sha256(
                theory_files[theory_record_source]
            ).hexdigest(),
            "generation": theory["generation"],
        },
        "p4_synthesis": {
            "identity": f"{method['stable_id']}:empirical-synthesis",
            "sha256": hashlib.sha256(
                empirical_files[empirical_synthesis_source]
            ).hexdigest(),
            "generation": empirical["generation"],
        },
        "p4_index": {
            "identity": f"{method['stable_id']}:evidence-index",
            "sha256": hashlib.sha256(
                empirical_files[empirical_index_source]
            ).hexdigest(),
            "generation": empirical["generation"],
        },
    }
    try:
        normalized_basis = manuscript_records.normalize_upstream_basis(
            basis,
            method_identity=method,
        )
    except manuscript_records.ManuscriptRecordError as exc:
        raise Phase5ProjectionError(
            f"frozen Phase 5 upstream basis is invalid: {exc}"
        ) from exc
    return {
        "upstream_basis": normalized_basis,
        "p5_manuscript": _frozen_current_manuscript(
            root,
            context_root,
            inventory,
            method,
        ),
    }
