"""Current Phase 5 working manuscripts and immutable review snapshots.

Each method branch has one canonical working draft.  A successful Phase 5 run
replaces that draft atomically and records the exact upstream scientific inputs
used to produce it.  Review snapshots are separate, content-addressed copies
because a reviewer must always refer to exact manuscript bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from core.filesystem_utils import metadata_is_link_or_reparse
from core.strict_json import StrictJsonError, parse_json_object
from core.theory_records import TheoryValidationError, normalize_method_identity


MANUSCRIPT_FILENAME = "manuscript.md"
RECORD_FILENAME = "record.json"
LEGACY_SCHEMA_VERSION = 1
SCHEMA_VERSION = 2
PROMOTION_TRANSACTION_SCHEMA_VERSION = 1
_PROMOTION_TRANSACTION_KEY = "_promotion_transaction"
REVIEW_SNAPSHOT_SCHEMA_VERSION = 1

LEGACY_UPSTREAM_INPUT_KEYS = (
    "p1_synthesis",
    "p2_definition",
    "p3_record",
    "p4_synthesis",
    "p4_index",
)
UPSTREAM_INPUT_KEYS = (
    "p1_synthesis",
    "p1_collection",
    *LEGACY_UPSTREAM_INPUT_KEYS[1:],
)
UPSTREAM_INPUT_LABELS = {
    "p1_synthesis": "Phase 1 literature synthesis",
    "p1_collection": "Phase 1 reference collection",
    "p2_definition": "Phase 2 method definition",
    "p3_record": "Phase 3 theory package",
    "p4_synthesis": "Phase 4 empirical synthesis",
    "p4_index": "Phase 4 evidence index",
}

MAX_MANUSCRIPT_BYTES = 40 * 1024 * 1024
MAX_RECORD_BYTES = 512 * 1024
_MAX_MANUSCRIPT_BYTES = MAX_MANUSCRIPT_BYTES
_MAX_RECORD_BYTES = MAX_RECORD_BYTES
_LIVE_CURRENT_MANUSCRIPT = object()
_MAX_IDENTITY_FIELDS = 20
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_ELIGIBLE_OUTCOMES = frozenset({"Complete", "Partial"})


class ManuscriptRecordError(ValueError):
    """Base class for Phase 5 record failures."""


class ManuscriptValidationError(ManuscriptRecordError):
    """Raised when a manuscript, basis, identity, or record is invalid."""


class ManuscriptStageChanged(ManuscriptRecordError):
    """Raised when staged content or its frozen basis changed before promotion."""


class ManuscriptRecordCorrupt(ManuscriptRecordError):
    """Raised when a published draft or review snapshot cannot be verified."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any, label: str, *, maximum: int = 300) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > maximum:
        raise ManuscriptValidationError(
            f"{label} must contain between 1 and {maximum} characters"
        )
    return normalized


def _method_identity(value: Mapping[str, Any]) -> dict[str, str]:
    try:
        return normalize_method_identity(value)
    except TheoryValidationError as exc:
        raise ManuscriptValidationError(str(exc)) from exc


def _project_root(project_dir: str | Path) -> Path:
    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise ManuscriptValidationError(
            f"project directory is not a directory: {root}"
        )
    return root


def _safe_project_path(root: Path, value: str | Path, *, label: str) -> Path:
    supplied = Path(value)
    lexical = supplied if supplied.is_absolute() else root / supplied
    lexical = Path(os.path.abspath(lexical))
    try:
        relative = lexical.relative_to(root)
    except ValueError as exc:
        raise ManuscriptValidationError(
            f"{label} is outside the project directory"
        ) from exc

    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ManuscriptValidationError(
                f"{label} cannot be inspected: {exc}"
            ) from exc
        if metadata_is_link_or_reparse(metadata):
            raise ManuscriptValidationError(
                f"{label} must not contain a symbolic link or junction"
            )
    return lexical.resolve(strict=False)


def staged_manuscript_path(
    project_dir: str | Path,
    output_root: str | Path,
) -> Path:
    """Return the required Phase 5 staging path within a run output root."""

    root = _project_root(project_dir)
    output = _safe_project_path(root, output_root, label="Phase 5 output directory")
    return output / MANUSCRIPT_FILENAME


def current_manuscript_directory(
    project_dir: str | Path,
    stable_id: str,
) -> Path:
    """Return the canonical working-draft directory for one method."""

    root = _project_root(project_dir)
    identity = _text(stable_id, "method stable ID", maximum=200)
    if not _STABLE_ID_RE.fullmatch(identity):
        raise ManuscriptValidationError(
            "method stable ID contains unsupported characters"
        )
    return root / "branches" / identity / "draft" / "current"


def _normalize_input_identity(value: Any, label: str) -> str | dict[str, Any]:
    if isinstance(value, str):
        return _text(value, f"{label} identity", maximum=500)
    if not isinstance(value, Mapping):
        raise ManuscriptValidationError(
            f"{label} identity must be a string or a flat object"
        )
    if not value or len(value) > _MAX_IDENTITY_FIELDS:
        raise ManuscriptValidationError(
            f"{label} identity must contain 1 to {_MAX_IDENTITY_FIELDS} fields"
        )
    normalized: dict[str, Any] = {}
    for raw_key, raw_item in sorted(value.items(), key=lambda pair: str(pair[0])):
        key = _text(raw_key, f"{label} identity field", maximum=100)
        if key in normalized:
            raise ManuscriptValidationError(f"{label} identity has duplicate fields")
        if raw_item is None or isinstance(raw_item, (bool, int)):
            item = raw_item
        elif isinstance(raw_item, str):
            item = _text(raw_item, f"{label} identity value", maximum=500)
        else:
            raise ManuscriptValidationError(
                f"{label} identity values must be strings, integers, booleans, or null"
            )
        normalized[key] = item
    return normalized


def normalize_upstream_basis(
    value: Mapping[str, Any],
    *,
    method_identity: Mapping[str, Any],
    schema_version: int = SCHEMA_VERSION,
) -> dict[str, dict[str, Any]]:
    """Validate the exact upstream inputs used by one manuscript."""

    method = _method_identity(method_identity)
    if type(schema_version) is not int:
        raise ManuscriptValidationError(
            "manuscript basis has an unsupported schema version"
        )
    if schema_version == LEGACY_SCHEMA_VERSION:
        input_keys = LEGACY_UPSTREAM_INPUT_KEYS
    elif schema_version == SCHEMA_VERSION:
        input_keys = UPSTREAM_INPUT_KEYS
    else:
        raise ManuscriptValidationError(
            "manuscript basis has an unsupported schema version"
        )
    if not isinstance(value, Mapping) or set(value) != set(input_keys):
        expected = ", ".join(input_keys)
        raise ManuscriptValidationError(
            f"upstream basis must contain exactly {expected}"
        )

    normalized: dict[str, dict[str, Any]] = {}
    for key in input_keys:
        raw = value[key]
        if not isinstance(raw, Mapping) or set(raw) != {
            "identity",
            "sha256",
            "generation",
        }:
            raise ManuscriptValidationError(
                f"{key} basis must contain exactly identity, sha256, and generation"
            )
        identity = _normalize_input_identity(raw.get("identity"), key)
        digest = str(raw.get("sha256", "")).strip().lower()
        generation = raw.get("generation")
        if not _SHA256_RE.fullmatch(digest):
            raise ManuscriptValidationError(f"{key} basis has an invalid SHA-256 digest")
        if generation is not None and (
            not isinstance(generation, int)
            or isinstance(generation, bool)
            or generation < 1
        ):
            raise ManuscriptValidationError(
                f"{key} generation must be null or a positive integer"
            )
        normalized[key] = {
            "identity": identity,
            "sha256": digest,
            "generation": generation,
        }

    p2_identity = normalized["p2_definition"]["identity"]
    if not isinstance(p2_identity, Mapping) or dict(p2_identity) != method:
        raise ManuscriptValidationError(
            "p2_definition identity must equal the manuscript method identity"
        )
    if normalized["p2_definition"]["sha256"] != method["definition_sha256"]:
        raise ManuscriptValidationError(
            "p2_definition digest must equal the method definition digest"
        )
    return normalized


def _read_manuscript(
    path: Path,
    *,
    error_type: type[ManuscriptRecordError],
) -> bytes:
    try:
        if metadata_is_link_or_reparse(path.lstat()):
            raise error_type("manuscript must not be a symbolic link")
        payload = path.read_bytes()
    except FileNotFoundError as exc:
        raise error_type(f"manuscript is missing: {path}") from exc
    except OSError as exc:
        raise error_type(f"manuscript cannot be read: {exc}") from exc
    if not payload or len(payload) > _MAX_MANUSCRIPT_BYTES:
        raise error_type(
            f"manuscript must contain 1 to {_MAX_MANUSCRIPT_BYTES} bytes"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error_type("manuscript must be UTF-8 text") from exc
    if not text.strip():
        raise error_type("manuscript must contain scientific content")
    return payload


def seal_staged_manuscript(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    method_identity: Mapping[str, Any],
    upstream_basis: Mapping[str, Any],
    source_run_id: str,
    scientific_outcome: str,
) -> dict[str, Any]:
    """Seal a staged working draft and its exact upstream basis."""

    method = _method_identity(method_identity)
    basis = normalize_upstream_basis(upstream_basis, method_identity=method)
    run_id = _text(source_run_id, "source run ID")
    outcome = str(scientific_outcome).strip()
    if outcome not in _ELIGIBLE_OUTCOMES:
        raise ManuscriptValidationError(
            "only Complete or Partial Phase 5 results can replace the working draft"
        )
    payload = _read_manuscript(
        staged_manuscript_path(project_dir, output_root),
        error_type=ManuscriptValidationError,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "method_identity": method,
        "upstream_basis": basis,
        "source_run_id": run_id,
        "scientific_outcome": outcome,
        "manuscript_sha256": _sha256(payload),
        "manuscript_size": len(payload),
    }


def _normalize_seal(
    value: Mapping[str, Any],
    *,
    allow_legacy: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ManuscriptValidationError("manuscript seal must be an object")
    required = {
        "schema_version",
        "method_identity",
        "upstream_basis",
        "source_run_id",
        "scientific_outcome",
        "manuscript_sha256",
        "manuscript_size",
    }
    schema_version = value.get("schema_version")
    allowed_versions = (
        {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}
        if allow_legacy
        else {SCHEMA_VERSION}
    )
    if set(value) != required or schema_version not in allowed_versions:
        raise ManuscriptValidationError("manuscript seal has an unsupported structure")
    method = _method_identity(value["method_identity"])
    basis = normalize_upstream_basis(
        value["upstream_basis"],
        method_identity=method,
        schema_version=schema_version,
    )
    run_id = _text(value.get("source_run_id"), "source run ID")
    outcome = str(value.get("scientific_outcome", "")).strip()
    digest = str(value.get("manuscript_sha256", "")).strip().lower()
    size = value.get("manuscript_size")
    if outcome not in _ELIGIBLE_OUTCOMES:
        raise ManuscriptValidationError("manuscript seal has an ineligible outcome")
    if not _SHA256_RE.fullmatch(digest):
        raise ManuscriptValidationError("manuscript seal has an invalid digest")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ManuscriptValidationError("manuscript seal has an invalid size")
    return {
        "schema_version": schema_version,
        "method_identity": method,
        "upstream_basis": basis,
        "source_run_id": run_id,
        "scientific_outcome": outcome,
        "manuscript_sha256": digest,
        "manuscript_size": size,
    }


def _record_payload(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _remove_internal_tree(path: Path) -> None:
    if not path.exists():
        return
    if metadata_is_link_or_reparse(path.lstat()):
        raise ManuscriptRecordCorrupt(
            "internal transaction path became a symbolic link"
        )
    shutil.rmtree(path)


def _verified_current(directory: Path, stable_id: str) -> dict[str, Any] | None:
    manuscript_path = directory / MANUSCRIPT_FILENAME
    record_path = directory / RECORD_FILENAME
    if not directory.exists():
        return None
    if metadata_is_link_or_reparse(directory.lstat()):
        raise ManuscriptRecordCorrupt("current manuscript directory is a symbolic link")
    if not manuscript_path.exists() or not record_path.exists():
        raise ManuscriptRecordCorrupt("current manuscript package is incomplete")
    try:
        if metadata_is_link_or_reparse(record_path.lstat()):
            raise ManuscriptRecordCorrupt(
                "current manuscript record is a symbolic link"
            )
        raw = record_path.read_bytes()
    except OSError as exc:
        raise ManuscriptRecordCorrupt(
            f"current manuscript record cannot be read: {exc}"
        ) from exc
    if not raw or len(raw) > _MAX_RECORD_BYTES:
        raise ManuscriptRecordCorrupt("current manuscript record has an invalid size")
    try:
        value = parse_json_object(raw, label="current manuscript record")
    except StrictJsonError as exc:
        raise ManuscriptRecordCorrupt(str(exc)) from exc
    required = {
        "schema_version",
        "method_identity",
        "upstream_basis",
        "source_run_id",
        "scientific_outcome",
        "generation",
        "manuscript_file",
        "manuscript_sha256",
        "manuscript_size",
    }
    if (
        set(value) != required
        or value.get("schema_version")
        not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}
    ):
        raise ManuscriptRecordCorrupt(
            "current manuscript record has an unsupported structure"
        )
    try:
        seal = _normalize_seal(
            {
                key: value[key]
                for key in (
                    "schema_version",
                    "method_identity",
                    "upstream_basis",
                    "source_run_id",
                    "scientific_outcome",
                    "manuscript_sha256",
                    "manuscript_size",
                )
            },
            allow_legacy=True,
        )
    except ManuscriptValidationError as exc:
        raise ManuscriptRecordCorrupt(str(exc)) from exc
    if seal["method_identity"]["stable_id"] != stable_id:
        raise ManuscriptRecordCorrupt(
            "current manuscript record belongs to another method"
        )
    generation = value.get("generation")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
    ):
        raise ManuscriptRecordCorrupt("current manuscript generation must be positive")
    if value.get("manuscript_file") != MANUSCRIPT_FILENAME:
        raise ManuscriptRecordCorrupt(
            "current manuscript record names an unexpected file"
        )
    payload = _read_manuscript(
        manuscript_path, error_type=ManuscriptRecordCorrupt
    )
    if len(payload) != seal["manuscript_size"] or _sha256(payload) != seal[
        "manuscript_sha256"
    ]:
        raise ManuscriptRecordCorrupt(
            "current manuscript does not match its record"
        )
    return {
        **seal,
        "generation": generation,
        "manuscript_file": MANUSCRIPT_FILENAME,
    }


def load_current_manuscript(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, Any] | None:
    """Load and verify one branch's canonical working draft."""

    directory = current_manuscript_directory(project_dir, stable_id)
    return _verified_current(directory, str(stable_id).strip())


def _atomic_write_staged(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and metadata_is_link_or_reparse(path.lstat()):
        raise ManuscriptValidationError("staged manuscript is a symbolic link")
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _minimal_manuscript_template(method: Mapping[str, str]) -> bytes:
    text = f"""# Manuscript

Selected method: `{method["stable_id"]}`
Method version: `{method["version"]}`
Method-definition SHA-256: `{method["definition_sha256"]}`

No verified current manuscript exists for this method branch. Develop the
first complete draft below from the current Phase 1 through Phase 4 records.

## Abstract

## Introduction

## Method

## Theory

## Empirical evaluation

## Discussion

## References
"""
    return text.encode("utf-8")


def prepare_staged_manuscript(
    project_dir: str | Path,
    output_root: str | Path,
    method_identity: Mapping[str, Any],
    *,
    frozen_current: object = _LIVE_CURRENT_MANUSCRIPT,
    require_current: bool = False,
) -> dict[str, Any]:
    """Prepare the branch working draft for a new Phase 5 run.

    An existing verified branch manuscript is copied byte for byte, including
    when upstream work has revised the method. This gives the revision run the
    actual draft it must update. A template is created only for the first
    manuscript run on that branch. Schema 13 callers pass the exact frozen
    launch source, including explicit absence. Legacy callers retain the live
    lookup.
    """

    method = _method_identity(method_identity)
    destination = staged_manuscript_path(project_dir, output_root)
    canonical = current_manuscript_directory(project_dir, method["stable_id"])
    if destination == canonical / MANUSCRIPT_FILENAME:
        raise ManuscriptValidationError(
            "Phase 5 staging directory must differ from the current draft"
        )
    frozen_payload: bytes | None = None
    if frozen_current is _LIVE_CURRENT_MANUSCRIPT:
        current = load_current_manuscript(project_dir, method["stable_id"])
    elif frozen_current is None:
        current = None
    else:
        if (
            not isinstance(frozen_current, Mapping)
            or set(frozen_current) != {"record", "manuscript_bytes"}
        ):
            raise ManuscriptValidationError(
                "frozen current manuscript has an unsupported structure"
            )
        try:
            current = _normalize_current_record(
                frozen_current["record"],
                label="frozen current manuscript record",
            )
        except KeyError as exc:
            raise ManuscriptValidationError(
                "frozen current manuscript is incomplete"
            ) from exc
        frozen_payload = frozen_current.get("manuscript_bytes")
        if type(frozen_payload) is not bytes or not frozen_payload:
            raise ManuscriptValidationError(
                "frozen current manuscript bytes are invalid"
            )
        if (
            current["method_identity"]["stable_id"] != method["stable_id"]
            or len(frozen_payload) != current["manuscript_size"]
            or _sha256(frozen_payload) != current["manuscript_sha256"]
        ):
            raise ManuscriptValidationError(
                "frozen current manuscript does not match its record"
            )
    if current is None:
        if require_current:
            raise ManuscriptValidationError(
                "review-revision requires a current manuscript frozen at launch"
            )
        payload = _minimal_manuscript_template(method)
        source = "template"
        reason = "no_current"
        generation: int | None = None
        source_method: dict[str, str] | None = None
    else:
        source_method = dict(current["method_identity"])
        if require_current and source_method != method:
            raise ManuscriptValidationError(
                "review-revision requires a current manuscript for the exact "
                "selected method"
            )
        if frozen_payload is None:
            payload = _read_manuscript(
                canonical / MANUSCRIPT_FILENAME,
                error_type=ManuscriptRecordCorrupt,
            )
        else:
            payload = frozen_payload
        source = "current"
        reason = (
            "exact_method_match"
            if source_method == method
            else "method_revision_pending"
        )
        generation = int(current["generation"])
    _atomic_write_staged(destination, payload)
    return {
        "path": destination,
        "source": source,
        "reason": reason,
        "method_identity": method,
        "source_method_identity": source_method,
        "source_generation": generation,
        "sha256": _sha256(payload),
        "size": len(payload),
    }


def promote_staged_manuscript(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
    *,
    expected_method_identity: Mapping[str, Any],
    expected_upstream_basis: Mapping[str, Any],
    retain_backup: bool = False,
) -> dict[str, Any]:
    """Atomically replace one branch's current working manuscript."""

    root = _project_root(project_dir)
    verified_seal = _normalize_seal(seal, allow_legacy=True)
    expected_method = _method_identity(expected_method_identity)
    seal_schema_version = verified_seal["schema_version"]
    if seal_schema_version == LEGACY_SCHEMA_VERSION:
        if not isinstance(expected_upstream_basis, Mapping):
            raise ManuscriptValidationError("upstream basis must be an object")
        expected_source = {
            key: expected_upstream_basis[key]
            for key in LEGACY_UPSTREAM_INPUT_KEYS
            if key in expected_upstream_basis
        }
    else:
        expected_source = expected_upstream_basis
    expected_basis = normalize_upstream_basis(
        expected_source,
        method_identity=expected_method,
        schema_version=seal_schema_version,
    )
    if verified_seal["method_identity"] != expected_method:
        raise ManuscriptStageChanged(
            "staged manuscript method identity does not match the selected method"
        )
    if verified_seal["upstream_basis"] != expected_basis:
        raise ManuscriptStageChanged(
            "staged manuscript upstream basis does not match the sealed run basis"
        )

    staged_path = staged_manuscript_path(root, output_root)
    staged_payload = _read_manuscript(
        staged_path, error_type=ManuscriptValidationError
    )
    if (
        len(staged_payload) != verified_seal["manuscript_size"]
        or _sha256(staged_payload) != verified_seal["manuscript_sha256"]
    ):
        raise ManuscriptStageChanged("staged manuscript changed after sealing")

    stable_id = expected_method["stable_id"]
    destination = current_manuscript_directory(root, stable_id)
    previous = _verified_current(destination, stable_id)
    if (
        previous is not None
        and previous["schema_version"] == SCHEMA_VERSION
        and seal_schema_version == LEGACY_SCHEMA_VERSION
    ):
        raise ManuscriptStageChanged(
            "a legacy manuscript cannot replace a current schema 2 manuscript"
        )
    if previous is not None and previous["source_run_id"] == verified_seal[
        "source_run_id"
    ]:
        comparable = {
            key: previous[key]
            for key in (
                "method_identity",
                "upstream_basis",
                "source_run_id",
                "scientific_outcome",
                "manuscript_sha256",
                "manuscript_size",
            )
        }
        expected_comparable = {
            key: verified_seal[key] for key in comparable
        }
        if comparable == expected_comparable:
            result = dict(previous)
            if retain_backup:
                result[_PROMOTION_TRANSACTION_KEY] = {
                    "schema_version": PROMOTION_TRANSACTION_SCHEMA_VERSION,
                    "kind": "manuscript_promotion_transaction",
                    "project_root": str(root),
                    "published_path": destination.relative_to(root).as_posix(),
                    "backup_path": None,
                    "changed": False,
                    "previous_record": dict(previous),
                    "published_record": dict(previous),
                }
            return result
        raise ManuscriptStageChanged(
            "source run already promoted with different manuscript content"
        )

    generation = 1 if previous is None else int(previous["generation"]) + 1
    record = {
        **verified_seal,
        "generation": generation,
        "manuscript_file": MANUSCRIPT_FILENAME,
    }
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    prepared = parent / f".current-prepared-{uuid.uuid4().hex}"
    backup = parent / f".current-backup-{uuid.uuid4().hex}"
    rejected = parent / f".current-rejected-{uuid.uuid4().hex}"
    prepared.mkdir()
    backup_created = False
    installed = False
    try:
        (prepared / MANUSCRIPT_FILENAME).write_bytes(staged_payload)
        (prepared / RECORD_FILENAME).write_bytes(_record_payload(record))
        if _verified_current(prepared, stable_id) != record:
            raise ManuscriptRecordCorrupt(
                "prepared manuscript package failed verification"
            )

        if destination.exists():
            os.replace(destination, backup)
            backup_created = True
        try:
            os.replace(prepared, destination)
            installed = True
            published = _verified_current(destination, stable_id)
            if published != record:
                raise ManuscriptRecordCorrupt(
                    "published manuscript package failed verification"
                )
        except BaseException:
            if destination.exists():
                os.replace(destination, rejected)
            if backup_created:
                os.replace(backup, destination)
                backup_created = False
            if rejected.exists():
                _remove_internal_tree(rejected)
            raise
        if backup_created and not retain_backup:
            _remove_internal_tree(backup)
            backup_created = False
        result = dict(record)
        if retain_backup:
            result[_PROMOTION_TRANSACTION_KEY] = {
                "schema_version": PROMOTION_TRANSACTION_SCHEMA_VERSION,
                "kind": "manuscript_promotion_transaction",
                "project_root": str(root),
                "published_path": destination.relative_to(root).as_posix(),
                "backup_path": (
                    backup.relative_to(root).as_posix()
                    if backup_created
                    else None
                ),
                "changed": True,
                "previous_record": (
                    dict(previous) if previous is not None else None
                ),
                "published_record": dict(record),
            }
        return result
    finally:
        if prepared.exists():
            _remove_internal_tree(prepared)
        if backup_created and not destination.exists():
            os.replace(backup, destination)
        elif backup.exists() and not (
            retain_backup and installed and backup_created
        ):
            _remove_internal_tree(backup)
        if rejected.exists():
            _remove_internal_tree(rejected)
        if installed and not destination.exists():
            raise ManuscriptRecordCorrupt(
                "manuscript promotion ended without a current package"
            )


def _basis_input_changed(
    key: str,
    stored: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> bool:
    """Compare scientific content while retaining Phase 1 run provenance."""

    if key in {"p1_synthesis", "p1_collection"}:
        return any(
            stored.get(field) != expected.get(field)
            for field in ("identity", "sha256")
        )
    return dict(stored) != dict(expected)


def compare_manuscript_basis(
    current_record: Mapping[str, Any] | None,
    *,
    method_identity: Mapping[str, Any],
    upstream_basis: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare a draft's frozen basis with the currently available inputs."""

    expected_method = _method_identity(method_identity)
    expected_basis = normalize_upstream_basis(
        upstream_basis, method_identity=expected_method
    )
    if current_record is None:
        changed_keys = list(UPSTREAM_INPUT_KEYS)
    else:
        if not isinstance(current_record, Mapping):
            raise ManuscriptValidationError("current manuscript record must be an object")
        try:
            stored_schema_version = current_record["schema_version"]
            stored_method = _method_identity(current_record["method_identity"])
            stored_basis = normalize_upstream_basis(
                current_record["upstream_basis"],
                method_identity=stored_method,
                schema_version=stored_schema_version,
            )
        except KeyError as exc:
            raise ManuscriptValidationError(
                "current manuscript record lacks its scientific basis"
            ) from exc
        changed_keys = [
            key
            for key in UPSTREAM_INPUT_KEYS
            if key not in stored_basis
            or _basis_input_changed(
                key, stored_basis[key], expected_basis[key]
            )
        ]
        if stored_method != expected_method and "p2_definition" not in changed_keys:
            changed_keys.insert(1 if changed_keys else 0, "p2_definition")
    return {
        "status": "current" if not changed_keys else "update_needed",
        "changed_inputs": changed_keys,
        "changed_input_labels": [
            UPSTREAM_INPUT_LABELS[key] for key in changed_keys
        ],
    }


def assess_current_manuscript(
    project_dir: str | Path,
    stable_id: str,
    *,
    method_identity: Mapping[str, Any],
    upstream_basis: Mapping[str, Any],
) -> dict[str, Any]:
    """Load one current draft and derive its current or update-needed state."""

    record = load_current_manuscript(project_dir, stable_id)
    comparison = compare_manuscript_basis(
        record,
        method_identity=method_identity,
        upstream_basis=upstream_basis,
    )
    return {"record": record, **comparison}


def _review_snapshot_path(project_dir: str | Path, digest: str) -> Path:
    from core.project_state import state_dir

    root = _project_root(project_dir)
    control = state_dir(root).resolve(strict=False)
    return control / "review-snapshots" / "sha256" / digest[:2] / f"{digest}.md"


def read_review_snapshot(
    project_dir: str | Path,
    digest: str,
) -> bytes:
    """Read and verify one content-addressed reviewed manuscript."""

    normalized = str(digest).strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise ManuscriptValidationError("review snapshot digest is invalid")
    path = _review_snapshot_path(project_dir, normalized)
    try:
        if metadata_is_link_or_reparse(path.lstat()):
            raise ManuscriptRecordCorrupt(
                "review snapshot must not be a symbolic link"
            )
        payload = path.read_bytes()
    except FileNotFoundError as exc:
        raise ManuscriptRecordCorrupt("review snapshot is missing") from exc
    except OSError as exc:
        raise ManuscriptRecordCorrupt(
            f"review snapshot cannot be read: {exc}"
        ) from exc
    if _sha256(payload) != normalized:
        raise ManuscriptRecordCorrupt(
            "review snapshot does not match its content address"
        )
    return payload


def preserve_current_for_review(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, Any]:
    """Preserve the exact current draft bytes in control storage.

    Repeated calls for identical bytes return the same path.  Existing content
    is verified and never overwritten, so tampering cannot be hidden by a new
    review request.
    """

    record = load_current_manuscript(project_dir, stable_id)
    if record is None:
        raise ManuscriptValidationError(
            "a current manuscript is required before review"
        )
    current_dir = current_manuscript_directory(project_dir, stable_id)
    payload = _read_manuscript(
        current_dir / MANUSCRIPT_FILENAME,
        error_type=ManuscriptRecordCorrupt,
    )
    digest = _sha256(payload)
    path = _review_snapshot_path(project_dir, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = read_review_snapshot(project_dir, digest)
        if existing != payload:
            raise ManuscriptRecordCorrupt(
                "review snapshot content differs from the current manuscript"
            )
    else:
        temporary = path.parent / f".{digest}.{uuid.uuid4().hex}.tmp"
        try:
            temporary.write_bytes(payload)
            if _sha256(temporary.read_bytes()) != digest:
                raise ManuscriptRecordCorrupt(
                    "temporary review snapshot failed verification"
                )
            if path.exists():
                read_review_snapshot(project_dir, digest)
            else:
                os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        read_review_snapshot(project_dir, digest)

    from core.project_state import state_dir

    relative = path.relative_to(state_dir(project_dir).resolve(strict=False)).as_posix()
    return {
        "schema_version": REVIEW_SNAPSHOT_SCHEMA_VERSION,
        "sha256": digest,
        "size": len(payload),
        "path": relative,
        "source_generation": record["generation"],
        "method_identity": record["method_identity"],
    }


def _normalize_current_record(
    value: Mapping[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ManuscriptValidationError(f"{label} must be an object")
    required = {
        "schema_version",
        "method_identity",
        "upstream_basis",
        "source_run_id",
        "scientific_outcome",
        "manuscript_sha256",
        "manuscript_size",
        "generation",
        "manuscript_file",
    }
    if set(value) != required:
        raise ManuscriptValidationError(f"{label} has an unsupported structure")
    seal = _normalize_seal(
        {
            key: value[key]
            for key in required
            if key not in {"generation", "manuscript_file"}
        },
        allow_legacy=True,
    )
    generation = value.get("generation")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
        or value.get("manuscript_file") != MANUSCRIPT_FILENAME
    ):
        raise ManuscriptValidationError(f"{label} generation is invalid")
    return {
        **seal,
        "generation": generation,
        "manuscript_file": MANUSCRIPT_FILENAME,
    }


def _promotion_transaction(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> tuple[Path, Path | None, bool, dict[str, Any] | None, dict[str, Any]]:
    """Validate and resolve a retained manuscript-promotion transaction."""

    if not isinstance(promotion, Mapping):
        raise ManuscriptValidationError("manuscript promotion must be an object")
    transaction = promotion.get(_PROMOTION_TRANSACTION_KEY)
    required = {
        "schema_version",
        "kind",
        "project_root",
        "published_path",
        "backup_path",
        "changed",
        "previous_record",
        "published_record",
    }
    if (
        not isinstance(transaction, Mapping)
        or set(transaction) != required
        or transaction.get("schema_version")
        != PROMOTION_TRANSACTION_SCHEMA_VERSION
        or transaction.get("kind") != "manuscript_promotion_transaction"
    ):
        raise ManuscriptValidationError(
            "manuscript promotion has no valid retained transaction"
        )
    root = _project_root(project_dir)
    if transaction.get("project_root") != str(root):
        raise ManuscriptValidationError(
            "manuscript promotion project identity is invalid"
        )
    published = _normalize_current_record(
        transaction.get("published_record"),
        label="published manuscript record",
    )
    previous_value = transaction.get("previous_record")
    previous = (
        _normalize_current_record(previous_value, label="previous manuscript record")
        if previous_value is not None
        else None
    )
    stable_id = published["method_identity"]["stable_id"]
    destination = current_manuscript_directory(root, stable_id)
    if transaction.get("published_path") != destination.relative_to(root).as_posix():
        raise ManuscriptValidationError("manuscript promotion path is invalid")
    changed = transaction.get("changed")
    if not isinstance(changed, bool):
        raise ManuscriptValidationError(
            "manuscript promotion changed flag is invalid"
        )
    backup_value = transaction.get("backup_path")
    backup: Path | None = None
    if backup_value is not None:
        if not isinstance(backup_value, str):
            raise ManuscriptValidationError(
                "manuscript promotion backup path is invalid"
            )
        backup = _safe_project_path(root, backup_value, label="manuscript backup")
        if (
            backup.parent != destination.parent
            or not backup.name.startswith(".current-backup-")
        ):
            raise ManuscriptValidationError(
                "manuscript promotion backup path is invalid"
            )
    if changed:
        if (previous is None) != (backup is None):
            raise ManuscriptValidationError(
                "manuscript promotion prior-state metadata is inconsistent"
            )
    elif backup is not None or previous != published:
        raise ManuscriptValidationError(
            "no-change manuscript promotion is inconsistent"
        )
    outer_record = {
        key: value
        for key, value in promotion.items()
        if key != _PROMOTION_TRANSACTION_KEY
    }
    if outer_record != published:
        raise ManuscriptValidationError(
            "manuscript promotion record changed after publication"
        )
    return destination, backup, changed, previous, published


def commit_manuscript_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Commit a retained manuscript promotion after state persistence."""

    destination, backup, _, previous, published = _promotion_transaction(
        project_dir, promotion
    )
    stable_id = published["method_identity"]["stable_id"]
    if _verified_current(destination, stable_id) != published:
        raise ManuscriptStageChanged(
            "published manuscript package changed after promotion"
        )
    if backup is None or not backup.exists():
        return
    if _verified_current(backup, stable_id) != previous:
        raise ManuscriptStageChanged(
            "manuscript rollback backup changed after promotion"
        )
    _remove_internal_tree(backup)


def rollback_manuscript_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Restore the manuscript package that preceded a retained promotion."""

    destination, backup, changed, previous, published = _promotion_transaction(
        project_dir, promotion
    )
    stable_id = published["method_identity"]["stable_id"]
    if _verified_current(destination, stable_id) == previous and (
        backup is None or not backup.exists()
    ):
        return
    if _verified_current(destination, stable_id) != published:
        raise ManuscriptStageChanged(
            "published manuscript package changed after promotion"
        )
    if not changed:
        return
    if backup is not None and (
        not backup.exists() or _verified_current(backup, stable_id) != previous
    ):
        raise ManuscriptStageChanged(
            "manuscript rollback backup changed after promotion"
        )

    displaced = destination.parent / f".current-rejected-{uuid.uuid4().hex}"
    os.replace(destination, displaced)
    try:
        if backup is not None:
            os.replace(backup, destination)
            if _verified_current(destination, stable_id) != previous:
                raise ManuscriptRecordCorrupt(
                    "restored manuscript package failed verification"
                )
        elif destination.exists():
            raise ManuscriptRecordCorrupt(
                "manuscript rollback unexpectedly restored a package"
            )
    except BaseException:
        if destination.exists():
            recovery = destination.parent / f".current-rejected-{uuid.uuid4().hex}"
            os.replace(destination, recovery)
            os.replace(displaced, destination)
            _remove_internal_tree(recovery)
        else:
            os.replace(displaced, destination)
        raise
    _remove_internal_tree(displaced)
