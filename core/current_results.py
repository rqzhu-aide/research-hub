"""Current-head records: which finalized run is the current result for each phase.

This module implements the storage foundation described in
``docs/STORAGE_RESTRUCTURE_PLAN.md``.  It is a *derived* layer over
``project_state``: every head can be reconstructed from run history and
manifests.  The records live in their own directory beneath
``state_dir(project_dir)`` and use a dedicated lock that is never held
at the same time as the project lock.

Rollout modes (§19):

    "off"      – existing behaviour, current-results code is inert
    "shadow"   – compute and compare heads without controlling context
    "enforced" – current heads control context for verified phase paths

Only storage primitives, schema validation, record reads/writes, and
derived-status helpers are implemented here.  Promotion, bootstrap,
context resolution, and UI projection arrive in later milestones.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from core import project_state

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

ROLLOUT_MODES = frozenset({"off", "shadow", "enforced"})
_DEFAULT_ROLLOUT_MODE = "off"

#: Maximum length of a raw identifier before hashing (defence-in-depth).
_MAX_RAW_ID_BYTES = 256

#: Maximum number of heads in one record (5 phases).
_MAX_HEADS_PER_RECORD = 8

#: Maximum encoded record size (bytes).
_MAX_RECORD_BYTES = 64 * 1024

#: Hex prefix length used for filesystem-safe keys (128 bits).
_SAFE_KEY_LEN = 32

#: Phases stored in the global record.
_GLOBAL_PHASES = frozenset({"01-literature-review", "02-method-development"})

#: Phases stored in branch records.
_BRANCH_PHASES = frozenset(
    {"03-idea-evaluation", "04-draft-assembly", "05-review-revision"}
)

#: Valid scientific outcomes for a head.
_HEAD_SCIENTIFIC_OUTCOMES = frozenset({"Complete", "Partial"})

#: Valid representation types.
_REPRESENTATION_TYPES = frozenset(
    {"verified_run_bundle", "canonical_scientific_package", "legacy_provisional"}
)

#: Valid derived statuses for a method-bound head.
_DERIVED_STATUSES = frozenset(
    {"fresh", "stale", "provisional", "corrupt", "missing", "retired"}
)

#: Required fields in every head object.
_REQUIRED_HEAD_FIELDS = frozenset(
    {
        "generation",
        "run_id",
        "phase_slug",
        "scientific_outcome",
        "representation",
        "source_integrity",
        "promoted_at",
        "operation_id",
    }
)

#: Required sub-fields of ``source_integrity``.
_REQUIRED_INTEGRITY_FIELDS = frozenset(
    {"run_manifest_sha256", "final_summary_sha256", "decision_sha256"}
)

#: Required sub-fields of ``method_identity`` (method-bound heads only).
_REQUIRED_METHOD_IDENTITY_FIELDS = frozenset(
    {"stable_id", "version", "definition_sha256"}
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CurrentResultsError(RuntimeError):
    """Base class for current-results errors."""


class CurrentResultsValidationError(CurrentResultsError, ValueError):
    """A record is structurally invalid."""


class CurrentResultsLockError(CurrentResultsError):
    """The dedicated current-results lock could not be acquired."""


# ---------------------------------------------------------------------------
# Rollout mode
# ---------------------------------------------------------------------------

_rollout_mode: str = _DEFAULT_ROLLOUT_MODE


def get_rollout_mode() -> str:
    """Return the current rollout mode (``off``, ``shadow``, or ``enforced``)."""

    return _rollout_mode


def set_rollout_mode(mode: str) -> None:
    """Set the rollout mode at runtime (primarily for tests)."""

    global _rollout_mode
    normalised = str(mode).strip().lower()
    if normalised not in ROLLOUT_MODES:
        raise CurrentResultsValidationError(
            f"rollout mode must be one of {sorted(ROLLOUT_MODES)}, got: {mode!r}"
        )
    _rollout_mode = normalised


def is_enabled() -> bool:
    """True when the rollout mode is not ``off``."""

    return _rollout_mode != "off"


# ---------------------------------------------------------------------------
# Safe key derivation
# ---------------------------------------------------------------------------


def _validate_raw_identifier(raw: str, label: str) -> str:
    """Validate a raw identifier and return the stripped value."""

    if not isinstance(raw, str):
        raise CurrentResultsValidationError(f"{label} must be a string")
    stripped = raw.strip()
    if not stripped:
        raise CurrentResultsValidationError(f"{label} must not be empty")
    if len(stripped.encode("utf-8")) > _MAX_RAW_ID_BYTES:
        raise CurrentResultsValidationError(
            f"{label} exceeds {_MAX_RAW_ID_BYTES} bytes"
        )
    return stripped


def safe_branch_key(stable_id: str) -> str:
    """Derive a filesystem-safe key from a stable method ID.

    The key is the first :data:`_SAFE_KEY_LEN` hex characters of the
    SHA-256 digest of the canonical UTF-8 encoding of the stripped ID.
    Raw method IDs are never used as path components.
    """

    canonical = _validate_raw_identifier(stable_id, "stable method ID")
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:_SAFE_KEY_LEN]


def safe_run_key(run_id: str) -> str:
    """Derive a filesystem-safe key from a run ID."""

    canonical = _validate_raw_identifier(run_id, "run ID")
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:_SAFE_KEY_LEN]


def safe_operation_key(operation_id: str) -> str:
    """Derive a filesystem-safe key from an operation ID."""

    canonical = _validate_raw_identifier(operation_id, "operation ID")
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:_SAFE_KEY_LEN]


# ---------------------------------------------------------------------------
# Paths  (all derived from state_dir)
# ---------------------------------------------------------------------------


def _current_results_root(project_dir: str | Path) -> Path:
    """Return the root directory for current-results files."""

    return project_state.state_dir(project_dir) / "current-results"


def global_record_path(project_dir: str | Path) -> Path:
    return _current_results_root(project_dir) / "global.json"


def branch_record_path(project_dir: str | Path, stable_id: str) -> Path:
    return _current_results_root(project_dir) / "branches" / f"{safe_branch_key(stable_id)}.json"


def launch_basis_path(project_dir: str | Path, run_id: str) -> Path:
    return _current_results_root(project_dir) / "launch-bases" / f"{safe_run_key(run_id)}.json"


def transaction_path(project_dir: str | Path, operation_id: str) -> Path:
    return _current_results_root(project_dir) / "transactions" / f"{safe_operation_key(operation_id)}.prepared.json"


def applied_receipt_path(project_dir: str | Path, operation_id: str) -> Path:
    return _current_results_root(project_dir) / "receipts" / f"{safe_operation_key(operation_id)}.applied.json"


def not_applied_receipt_path(project_dir: str | Path, operation_id: str) -> Path:
    return _current_results_root(project_dir) / "receipts" / f"{safe_operation_key(operation_id)}.not-applied.json"


def bootstrap_report_path(project_dir: str | Path) -> Path:
    return _current_results_root(project_dir) / "migration" / "bootstrap-report.json"


def lock_file_path(project_dir: str | Path) -> Path:
    return _current_results_root(project_dir) / "current-results.lock"


# ---------------------------------------------------------------------------
# Dedicated lock  (never held together with the project lock)
# ---------------------------------------------------------------------------


@contextmanager
def current_results_lock(
    project_dir: str | Path, timeout: float = 15.0
) -> Iterator[None]:
    """Acquire the dedicated current-results advisory lock.

    Uses the same byte-range lock mechanism as ``_project_lock`` but on a
    separate lock file inside the current-results directory.  This lock must
    never be held while the project lock is held (see §11 of the plan).
    """

    root = _current_results_root(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = lock_file_path(project_dir)
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open(path, flags, 0o600)
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        opened_meta = os.fstat(descriptor)
        path_meta = path.lstat()
        if (
            _metadata_is_link_or_reparse(path_meta)
            or not stat.S_ISREG(opened_meta.st_mode)
            or not os.path.samestat(opened_meta, path_meta)
        ):
            raise CurrentResultsLockError(
                f"current-results lock must be a regular file: {path}"
            )
        handle = os.fdopen(descriptor, "a+b")
        descriptor = -1  # ownership transferred
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        deadline = time.monotonic() + timeout
        acquired = False
        try:
            while not acquired:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except (OSError, BlockingIOError):
                    if time.monotonic() >= deadline:
                        raise CurrentResultsLockError(
                            f"timed out waiting for current-results lock: {path}"
                        )
                    time.sleep(0.1)
            yield
        finally:
            if acquired:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            handle.close()
    except OSError as exc:
        raise CurrentResultsLockError(
            f"current-results lock is unavailable: {exc}"
        ) from exc
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    return bool(getattr(metadata, "st_reparse_tag", 0))


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def _validate_sha256_field(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise CurrentResultsValidationError(f"{label} must be a string")
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        c not in "0123456789abcdef" for c in digest
    ):
        raise CurrentResultsValidationError(f"{label} must be a 64-char hex digest")
    return digest


def _validate_method_identity(value: Any, *, allow_none: bool = False) -> dict[str, str] | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, Mapping):
        raise CurrentResultsValidationError("method_identity must be a mapping or null")
    result: dict[str, str] = {}
    for field in ("stable_id", "version"):
        raw = str(value.get(field, "")).strip()
        if not raw:
            raise CurrentResultsValidationError(
                f"method_identity.{field} must not be empty"
            )
        result[field] = raw
    result["definition_sha256"] = _validate_sha256_field(
        value.get("definition_sha256", ""),
        "method_identity.definition_sha256",
    )
    # Reject unknown keys
    unknown = set(value.keys()) - _REQUIRED_METHOD_IDENTITY_FIELDS
    if unknown:
        raise CurrentResultsValidationError(
            f"method_identity has unknown fields: {sorted(unknown)}"
        )
    return result


def validate_head(head: Mapping[str, Any], *, method_bound: bool) -> dict[str, Any]:
    """Validate a single head object and return a normalised copy.

    Parameters
    ----------
    head
        The raw head mapping.
    method_bound
        True for phase 03/04/05 heads (require ``method_identity``).
    """

    if not isinstance(head, Mapping):
        raise CurrentResultsValidationError("head must be a mapping")
    missing = _REQUIRED_HEAD_FIELDS - set(head.keys())
    if missing:
        raise CurrentResultsValidationError(
            f"head is missing required fields: {sorted(missing)}"
        )
    unknown = set(head.keys()) - _REQUIRED_HEAD_FIELDS - {"method_identity", "status_at_promotion"}
    if unknown:
        raise CurrentResultsValidationError(
            f"head has unknown fields: {sorted(unknown)}"
        )
    result: dict[str, Any] = {}

    generation = head["generation"]
    if not isinstance(generation, int) or generation < 1:
        raise CurrentResultsValidationError(
            "generation must be a positive integer"
        )
    result["generation"] = generation

    run_id = str(head["run_id"]).strip()
    if not run_id:
        raise CurrentResultsValidationError("run_id must not be empty")
    result["run_id"] = run_id

    phase_slug = str(head["phase_slug"]).strip()
    if not phase_slug:
        raise CurrentResultsValidationError("phase_slug must not be empty")
    result["phase_slug"] = phase_slug

    outcome = str(head["scientific_outcome"]).strip()
    if outcome not in _HEAD_SCIENTIFIC_OUTCOMES:
        raise CurrentResultsValidationError(
            f"scientific_outcome must be one of {sorted(_HEAD_SCIENTIFIC_OUTCOMES)}"
        )
    result["scientific_outcome"] = outcome

    representation = str(head["representation"]).strip()
    if representation not in _REPRESENTATION_TYPES:
        raise CurrentResultsValidationError(
            f"representation must be one of {sorted(_REPRESENTATION_TYPES)}"
        )
    result["representation"] = representation

    integrity_raw = head["source_integrity"]
    if not isinstance(integrity_raw, Mapping):
        raise CurrentResultsValidationError("source_integrity must be a mapping")
    integrity: dict[str, str] = {}
    for field in _REQUIRED_INTEGRITY_FIELDS:
        integrity[field] = _validate_sha256_field(
            integrity_raw.get(field, ""),
            f"source_integrity.{field}",
        )
    unknown_integrity = set(integrity_raw.keys()) - _REQUIRED_INTEGRITY_FIELDS
    if unknown_integrity:
        raise CurrentResultsValidationError(
            f"source_integrity has unknown fields: {sorted(unknown_integrity)}"
        )
    result["source_integrity"] = integrity

    promoted_at = str(head["promoted_at"]).strip()
    if not promoted_at:
        raise CurrentResultsValidationError("promoted_at must not be empty")
    result["promoted_at"] = promoted_at

    operation_id = str(head["operation_id"]).strip()
    if not operation_id:
        raise CurrentResultsValidationError("operation_id must not be empty")
    result["operation_id"] = operation_id

    if method_bound:
        result["method_identity"] = _validate_method_identity(head.get("method_identity"))
    elif head.get("method_identity") is not None:
        raise CurrentResultsValidationError(
            "non-method-bound head must not have method_identity"
        )

    if "status_at_promotion" in head:
        result["status_at_promotion"] = str(head["status_at_promotion"]).strip()

    return result


def validate_global_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a global current-results record."""

    if not isinstance(record, Mapping):
        raise CurrentResultsValidationError("global record must be a mapping")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise CurrentResultsValidationError(
            f"global record schema_version must be {SCHEMA_VERSION}"
        )
    heads_raw = record.get("heads")
    if not isinstance(heads_raw, Mapping):
        raise CurrentResultsValidationError("global record heads must be a mapping")
    if len(heads_raw) > _MAX_HEADS_PER_RECORD:
        raise CurrentResultsValidationError(
            f"global record has too many heads ({len(heads_raw)} > {_MAX_HEADS_PER_RECORD})"
        )
    heads: dict[str, dict[str, Any]] = {}
    for slug, head in heads_raw.items():
        slug_str = str(slug)
        if slug_str not in _GLOBAL_PHASES:
            raise CurrentResultsValidationError(
                f"global record contains non-global phase: {slug_str}"
            )
        heads[slug_str] = validate_head(head, method_bound=False)
    unknown = set(record.keys()) - {"schema_version", "heads"}
    if unknown:
        raise CurrentResultsValidationError(
            f"global record has unknown fields: {sorted(unknown)}"
        )
    return {"schema_version": SCHEMA_VERSION, "heads": heads}


def validate_branch_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a branch current-results record."""

    if not isinstance(record, Mapping):
        raise CurrentResultsValidationError("branch record must be a mapping")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise CurrentResultsValidationError(
            f"branch record schema_version must be {SCHEMA_VERSION}"
        )
    stable_id = str(record.get("stable_id", "")).strip()
    if not stable_id:
        raise CurrentResultsValidationError("branch record stable_id must not be empty")

    method_status = str(record.get("method_status", "active")).strip()
    if method_status not in {"active", "retired"}:
        raise CurrentResultsValidationError(
            "method_status must be 'active' or 'retired'"
        )

    catalog_generation = record.get("catalog_generation", 0)
    if not isinstance(catalog_generation, int) or catalog_generation < 0:
        raise CurrentResultsValidationError(
            "catalog_generation must be a non-negative integer"
        )

    active_identity = _validate_method_identity(
        record.get("active_method_identity"), allow_none=True
    )

    heads_raw = record.get("heads", {})
    if not isinstance(heads_raw, Mapping):
        raise CurrentResultsValidationError("branch record heads must be a mapping")
    if len(heads_raw) > _MAX_HEADS_PER_RECORD:
        raise CurrentResultsValidationError(
            f"branch record has too many heads ({len(heads_raw)} > {_MAX_HEADS_PER_RECORD})"
        )
    heads: dict[str, dict[str, Any]] = {}
    for slug, head in heads_raw.items():
        slug_str = str(slug)
        if slug_str not in _BRANCH_PHASES:
            raise CurrentResultsValidationError(
                f"branch record contains non-branch phase: {slug_str}"
            )
        heads[slug_str] = validate_head(head, method_bound=True)

    # Optional catalog provenance fields
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stable_id": stable_id,
        "method_status": method_status,
        "catalog_generation": catalog_generation,
        "active_method_identity": active_identity,
        "heads": heads,
    }
    for optional_field in (
        "catalog_source_run_id",
        "catalog_sha256",
        "reconciliation_pending",
    ):
        if optional_field in record:
            result[optional_field] = record[optional_field]
    return result


# ---------------------------------------------------------------------------
# Head digest (canonical JSON)
# ---------------------------------------------------------------------------


def compute_head_sha256(head: Mapping[str, Any]) -> str:
    """Compute SHA-256 over the canonical JSON encoding of a head.

    The digest itself is never part of the hashed object (§7.3).
    """

    normalised = json.loads(json.dumps(head, sort_keys=True))
    normalised.pop("head_sha256", None)
    canonical = json.dumps(
        normalised,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON atomically: temp file in same dir, then rename."""

    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    if len(encoded) > _MAX_RECORD_BYTES:
        raise CurrentResultsValidationError(
            f"record exceeds {_MAX_RECORD_BYTES} bytes"
        )
    tmp = path.with_suffix(".tmp")
    # Verify we're writing to a plain directory, not a symlink target
    if path.parent.is_symlink():
        raise CurrentResultsValidationError(
            f"cannot write into a symlinked directory: {path.parent}"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(tmp, flags, 0o600)
    try:
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Record reads
# ---------------------------------------------------------------------------


def load_global(project_dir: str | Path) -> dict[str, Any] | None:
    """Load and validate the global record, or return None if absent."""

    path = global_record_path(project_dir)
    if not path.is_file():
        return None
    return _read_and_validate(path, validate_global_record)


def load_branch(project_dir: str | Path, stable_id: str) -> dict[str, Any] | None:
    """Load and validate a branch record, or return None if absent."""

    path = branch_record_path(project_dir, stable_id)
    if not path.is_file():
        return None
    return _read_and_validate(path, validate_branch_record)


def _read_and_validate(
    path: Path, validator
) -> dict[str, Any]:
    """Read, size-check, parse, and validate a JSON record file."""

    raw = _read_bounded(path)
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CurrentResultsValidationError(
            f"current-results record is not valid JSON: {path}: {exc}"
        ) from exc
    return validator(parsed)


def _read_bounded(path: Path) -> bytes:
    """Read a file with a size bound."""

    size = path.stat().st_size
    if size > _MAX_RECORD_BYTES:
        raise CurrentResultsValidationError(
            f"current-results record exceeds {_MAX_RECORD_BYTES} bytes: {path}"
        )
    with open(path, "rb") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Derived status
# ---------------------------------------------------------------------------


def derive_head_status(
    head: Mapping[str, Any] | None,
    active_method_identity: Mapping[str, Any] | None,
    *,
    method_status: str = "active",
) -> str:
    """Derive the display/semantic status of a method-bound head.

    Returns one of the :data:`_DERIVED_STATUSES` values:

    - ``missing`` – no head exists for this phase.
    - ``retired`` – the method is retired.
    - ``provisional`` – the head lacks exact method identity (legacy).
    - ``stale`` – the head's identity does not match the active method.
    - ``fresh`` – identity matches and representation is valid.
    - ``corrupt`` – the head's representation is legacy_provisional with
      no verified bundle (diagnostic only; full integrity checked elsewhere).
    """

    if head is None:
        return "missing"
    if method_status == "retired":
        return "retired"
    representation = str(head.get("representation", ""))
    if representation == "legacy_provisional":
        return "provisional"
    head_identity = head.get("method_identity")
    if not isinstance(head_identity, Mapping):
        return "provisional"
    if active_method_identity is None:
        return "stale"
    for field in _REQUIRED_METHOD_IDENTITY_FIELDS:
        head_val = str(head_identity.get(field, "")).strip().lower()
        active_val = str(active_method_identity.get(field, "")).strip().lower()
        if field == "stable_id":
            # stable_id is case-sensitive
            head_val = str(head_identity.get(field, "")).strip()
            active_val = str(active_method_identity.get(field, "")).strip()
        if not head_val or not active_val:
            return "provisional"
        if head_val != active_val:
            return "stale"
    return "fresh"


def is_phase_global(phase_slug: str) -> bool:
    """True when the phase is stored in the global record (P1, P2)."""

    return project_state._resolve_slug(phase_slug) in _GLOBAL_PHASES


def is_phase_branch(phase_slug: str) -> bool:
    """True when the phase is stored in a branch record (P3, P4, P5)."""

    return project_state._resolve_slug(phase_slug) in _BRANCH_PHASES


def is_phase_method_bound(phase_slug: str) -> bool:
    """True when the phase requires exact method identity on every head."""

    return is_phase_branch(phase_slug)


# ---------------------------------------------------------------------------
# Write helpers (used by later milestones)
# ---------------------------------------------------------------------------


def write_global_record(
    project_dir: str | Path,
    record: Mapping[str, Any],
) -> None:
    """Validate and atomically write the global record.

    Must be called inside :func:`current_results_lock`.
    """

    validated = validate_global_record(record)
    _atomic_write_json(global_record_path(project_dir), validated)


def write_branch_record(
    project_dir: str | Path,
    stable_id: str,
    record: Mapping[str, Any],
) -> None:
    """Validate and atomically write a branch record.

    Must be called inside :func:`current_results_lock`.
    The ``stable_id`` parameter is used only for the path; the record's
    own ``stable_id`` field is authoritative.
    """

    validated = validate_branch_record(record)
    if validated["stable_id"] != stable_id.strip():
        raise CurrentResultsValidationError(
            "branch record stable_id does not match the path key"
        )
    _atomic_write_json(branch_record_path(project_dir, stable_id), validated)


# ---------------------------------------------------------------------------
# §8: Launch-basis record (immutable sidecar)
# ---------------------------------------------------------------------------

LAUNCH_BASIS_SCHEMA_VERSION = 1

#: Required fields in a launch-basis record.
_REQUIRED_LAUNCH_BASIS_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "target_phase",
        "selected_heads",
        "created_at",
    }
)

#: Required fields in each selected-head entry.
_REQUIRED_SELECTED_HEAD_FIELDS = frozenset(
    {"scope", "phase_slug", "run_id", "generation", "head_sha256"}
)


def validate_launch_basis(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a launch-basis sidecar record."""

    if not isinstance(record, Mapping):
        raise CurrentResultsValidationError("launch basis must be a mapping")
    if record.get("schema_version") != LAUNCH_BASIS_SCHEMA_VERSION:
        raise CurrentResultsValidationError(
            f"launch basis schema_version must be {LAUNCH_BASIS_SCHEMA_VERSION}"
        )
    missing = _REQUIRED_LAUNCH_BASIS_FIELDS - set(record.keys())
    if missing:
        raise CurrentResultsValidationError(
            f"launch basis missing required fields: {sorted(missing)}"
        )
    run_id = str(record["run_id"]).strip()
    if not run_id:
        raise CurrentResultsValidationError("launch basis run_id must not be empty")
    target_phase = str(record["target_phase"]).strip()
    if not target_phase:
        raise CurrentResultsValidationError("launch basis target_phase must not be empty")

    selected_heads_raw = record["selected_heads"]
    if not isinstance(selected_heads_raw, list):
        raise CurrentResultsValidationError("selected_heads must be a list")
    if len(selected_heads_raw) > _MAX_HEADS_PER_RECORD:
        raise CurrentResultsValidationError(
            f"too many selected heads ({len(selected_heads_raw)})"
        )
    selected_heads: list[dict[str, Any]] = []
    for i, entry in enumerate(selected_heads_raw):
        if not isinstance(entry, Mapping):
            raise CurrentResultsValidationError(f"selected_heads[{i}] must be a mapping")
        missing_entry = _REQUIRED_SELECTED_HEAD_FIELDS - set(entry.keys())
        if missing_entry:
            raise CurrentResultsValidationError(
                f"selected_heads[{i}] missing: {sorted(missing_entry)}"
            )
        scope = str(entry["scope"]).strip()
        if scope not in {"global", "branch"}:
            raise CurrentResultsValidationError(
                f"selected_heads[{i}].scope must be 'global' or 'branch'"
            )
        validated_entry: dict[str, Any] = {
            "scope": scope,
            "phase_slug": str(entry["phase_slug"]).strip(),
            "run_id": str(entry["run_id"]).strip(),
            "generation": int(entry["generation"]),
            "head_sha256": _validate_sha256_field(
                entry["head_sha256"], f"selected_heads[{i}].head_sha256"
            ),
        }
        if "relationship" in entry:
            validated_entry["relationship"] = str(entry["relationship"]).strip()
        selected_heads.append(validated_entry)

    result: dict[str, Any] = {
        "schema_version": LAUNCH_BASIS_SCHEMA_VERSION,
        "run_id": run_id,
        "target_phase": target_phase,
        "selected_heads": selected_heads,
        "created_at": str(record["created_at"]).strip(),
    }
    # Optional method identity for method-bound target phases
    identity = record.get("selected_method_identity")
    if identity is not None:
        result["selected_method_identity"] = _validate_method_identity(identity)
    if "same_phase_base_generation" in record:
        gen = record["same_phase_base_generation"]
        if not isinstance(gen, int) or gen < 0:
            raise CurrentResultsValidationError(
                "same_phase_base_generation must be a non-negative integer"
            )
        result["same_phase_base_generation"] = gen
    return result


def write_launch_basis(
    project_dir: str | Path,
    record: Mapping[str, Any],
) -> str:
    """Validate and atomically write a launch-basis sidecar.

    Returns the SHA-256 of the encoded record (for storage in run state).

    Must be called inside :func:`current_results_lock`.
    """

    validated = validate_launch_basis(record)
    path = launch_basis_path(project_dir, validated["run_id"])
    _atomic_write_json(path, validated)
    # Compute the SHA-256 of the canonical encoding for integrity checking
    encoded = json.dumps(validated, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_launch_basis(
    project_dir: str | Path,
    run_id: str,
) -> dict[str, Any] | None:
    """Load and validate a launch-basis sidecar, or return None if absent."""

    path = launch_basis_path(project_dir, run_id)
    if not path.is_file():
        return None
    return _read_and_validate(path, validate_launch_basis)


def compute_launch_basis_sha256(record: Mapping[str, Any]) -> str:
    """Compute the canonical SHA-256 of a launch-basis record."""

    validated = validate_launch_basis(record)
    encoded = json.dumps(validated, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# §14: Bootstrap — build heads from existing project state
# ---------------------------------------------------------------------------

#: Statuses that may hold an intact completed result eligible for bootstrap.
#: This is broader than ``COMPLETED_METHOD_RESULT_STATUSES`` (which excludes
#: ``revision_requested`` and ``superseded``). The plan (§14) says these
#: statuses are acceptable when the scientific result remains intact.
_BOOTSTRAP_ELIGIBLE_STATUSES = frozenset(
    {"approved", "awaiting_review", "revision_requested", "superseded"}
)

#: Scientific outcomes that make a head eligible.
_BOOTSTRAP_ELIGIBLE_OUTCOMES = frozenset({"Complete", "Partial"})


def _bootstrap_candidate_for_run(
    project_dir: str | Path,
    phase_slug: str,
    run: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Evaluate whether a single run can become a head candidate.

    Returns a validated candidate dict with the fields needed to build a
    head, or None if the run is ineligible.

    This is the "generalized candidate validator" (§14) factored from the
    identity/outcome/integrity checks in ``completed_method_branch_result``
    and ``completed_phase_result``, but with a broader status policy.
    """

    run_id = str(run.get("run_id", "")).strip()
    if not run_id:
        return None
    status = str(run.get("status", "")).strip()
    if status not in _BOOTSTRAP_ELIGIBLE_STATUSES:
        return None
    if not run.get("submitted_at") or not run.get("final_summary"):
        return None
    # Scientific outcome from the decision record
    decision_record = run.get("decision_record")
    data = decision_record.get("data") if isinstance(decision_record, Mapping) else None
    outcome_raw = data.get("scientific_outcome") if isinstance(data, Mapping) else None
    outcome = str(outcome_raw) if outcome_raw in _BOOTSTRAP_ELIGIBLE_OUTCOMES else ""
    if not outcome:
        return None
    # Integrity check
    try:
        if not project_state.run_integrity_report(project_dir, phase_slug, run_id).get("ok"):
            return None
    except Exception:
        return None
    # Source integrity digests
    manifest_sha256 = str(run.get("manifest_sha256", "")).strip().lower()
    summary_sha256 = str(run.get("summary_sha256", "")).strip().lower()
    decision_sha256 = ""
    if isinstance(decision_record, Mapping):
        decision_sha256 = str(decision_record.get("sha256", "")).strip().lower()
    if not manifest_sha256 or not summary_sha256:
        return None
    candidate: dict[str, Any] = {
        "run_id": run_id,
        "phase_slug": phase_slug,
        "status_at_promotion": status,
        "scientific_outcome": outcome,
        "source_integrity": {
            "run_manifest_sha256": manifest_sha256,
            "final_summary_sha256": summary_sha256,
            "decision_sha256": decision_sha256 or "0" * 64,
        },
    }
    # Method identity for method-bound phases
    if is_phase_branch(phase_slug):
        identity = _resolve_run_method_identity(project_dir, phase_slug, run_id)
        if identity is None:
            # Stable-ID-only recovery → provisional
            candidate["representation"] = "legacy_provisional"
            candidate["method_identity"] = None
        else:
            candidate["representation"] = "verified_run_bundle"
            candidate["method_identity"] = identity
    else:
        candidate["representation"] = "verified_run_bundle"
    return candidate


def _resolve_run_method_identity(
    project_dir: str | Path,
    phase_slug: str,
    run_id: str,
) -> dict[str, str] | None:
    """Resolve exact method identity from a run's sealed manifest.

    Returns None if identity cannot be verified (legacy/provisional).
    """

    try:
        from core import launch_manifest
        manifest = launch_manifest._read_manifest(Path(project_dir), phase_slug, run_id)
    except Exception:
        return None
    selection = manifest.get("method_selection")
    snapshots = manifest.get("snapshots", {})
    selected_method = snapshots.get("selected_method") if isinstance(snapshots, Mapping) else None
    if not isinstance(selection, Mapping) or not isinstance(selected_method, Mapping):
        return None
    stable_id = str(selection.get("stable_id", "")).strip()
    version = str(selection.get("version", "")).strip()
    digest = str(selected_method.get("sha256", "")).strip().lower()
    if not stable_id or not version or len(digest) != 64:
        return None
    return {
        "stable_id": stable_id,
        "version": version,
        "definition_sha256": digest,
    }


def _bootstrap_phase(
    project_dir: str | Path,
    phase_slug: str,
) -> dict[str, Any] | None:
    """Find the newest eligible candidate for one phase.

    Scans runs in reverse chronological order (newest first) and returns
    the first eligible candidate, or None if no run qualifies.
    """

    try:
        runs = project_state.get_runs(project_dir, phase_slug)
    except Exception:
        return None
    for run in reversed(runs):
        if not isinstance(run, Mapping):
            continue
        candidate = _bootstrap_candidate_for_run(project_dir, phase_slug, run)
        if candidate is not None:
            return candidate
    return None


def _build_head_from_candidate(
    candidate: Mapping[str, Any],
    generation: int,
    promoted_at: str,
    operation_id: str,
    *,
    method_bound: bool,
) -> dict[str, Any]:
    """Build a validated head dict from a bootstrap candidate."""

    head: dict[str, Any] = {
        "generation": generation,
        "run_id": candidate["run_id"],
        "phase_slug": candidate["phase_slug"],
        "scientific_outcome": candidate["scientific_outcome"],
        "representation": candidate["representation"],
        "source_integrity": dict(candidate["source_integrity"]),
        "promoted_at": promoted_at,
        "operation_id": operation_id,
    }
    if "status_at_promotion" in candidate:
        head["status_at_promotion"] = candidate["status_at_promotion"]
    if method_bound:
        identity = candidate.get("method_identity")
        if isinstance(identity, Mapping):
            head["method_identity"] = dict(identity)
        else:
            # Provisional — should not happen for valid method-bound heads,
            # but validate_head will catch it if it does.
            head["representation"] = "legacy_provisional"
    return validate_head(head, method_bound=method_bound)


def bootstrap_project(
    project_dir: str | Path,
    *,
    write: bool = False,
) -> dict[str, Any]:
    """Bootstrap current-head records from existing project state.

    This is non-destructive: it never edits or deletes existing runs or
    manifests (§14).  It scans run history and builds head records.

    Parameters
    ----------
    project_dir
        The project directory.
    write
        If True, atomically write the records to disk inside
        :func:`current_results_lock`.  If False (default), only compute
        and return the report (shadow mode).

    Returns
    -------
    dict
        A bootstrap report with ``global_heads``, ``branch_heads``,
        ``skipped``, ``ambiguous``, and ``written`` keys.
    """

    from core import launch_manifest  # noqa: F401 — used in _bootstrap_candidate_for_run

    root = Path(project_dir).resolve()
    report: dict[str, Any] = {
        "project_dir": str(root),
        "global_heads": {},
        "branch_heads": {},  # stable_id → {phase_slug → head}
        "skipped": [],
        "ambiguous": [],
        "written": False,
    }

    # --- Global heads (P1, P2) ---
    for slug in sorted(_GLOBAL_PHASES):
        candidate = _bootstrap_phase(root, slug)
        if candidate is None:
            continue
        try:
            head = _build_head_from_candidate(
                candidate,
                generation=1,
                promoted_at=project_state._now_iso(),
                operation_id=f"bootstrap:{slug}:{candidate['run_id']}",
                method_bound=False,
            )
        except CurrentResultsValidationError as exc:
            report["skipped"].append({"phase": slug, "run_id": candidate["run_id"], "reason": str(exc)})
            continue
        report["global_heads"][slug] = head

    # --- Branch heads (P3, P4, P5) ---
    # Group candidates by stable_id
    branch_candidates: dict[str, dict[str, dict[str, Any]]] = {}  # stable_id → phase → candidate
    for slug in sorted(_BRANCH_PHASES):
        candidate = _bootstrap_phase(root, slug)
        if candidate is None:
            continue
        identity = candidate.get("method_identity")
        if isinstance(identity, Mapping):
            stable_id = str(identity.get("stable_id", "")).strip()
            if stable_id:
                branch_candidates.setdefault(stable_id, {})[slug] = candidate
        else:
            # Provisional — cannot assign to a branch
            report["skipped"].append({
                "phase": slug,
                "run_id": candidate["run_id"],
                "reason": "stable-ID-only recovery; marked legacy_provisional",
            })

    for stable_id, phase_map in branch_candidates.items():
        heads: dict[str, Any] = {}
        for slug, candidate in phase_map.items():
            try:
                head = _build_head_from_candidate(
                    candidate,
                    generation=1,
                    promoted_at=project_state._now_iso(),
                    operation_id=f"bootstrap:{slug}:{candidate['run_id']}",
                    method_bound=True,
                )
            except CurrentResultsValidationError as exc:
                report["skipped"].append({"phase": slug, "run_id": candidate["run_id"], "reason": str(exc)})
                continue
            heads[slug] = head
        if heads:
            report["branch_heads"][stable_id] = heads

    if write:
        with current_results_lock(root):
            # Write global record
            if report["global_heads"]:
                global_record = {"schema_version": SCHEMA_VERSION, "heads": dict(report["global_heads"])}
                write_global_record(root, global_record)
            # Write branch records
            for stable_id, heads in report["branch_heads"].items():
                # Build active method identity from the first head
                sample_head = next(iter(heads.values()))
                active_identity = dict(sample_head.get("method_identity", {}))
                branch_record = {
                    "schema_version": SCHEMA_VERSION,
                    "stable_id": stable_id,
                    "method_status": "active",
                    "catalog_generation": 0,
                    "active_method_identity": active_identity,
                    "heads": dict(heads),
                }
                write_branch_record(root, stable_id, branch_record)
            report["written"] = True

    return report


# ---------------------------------------------------------------------------
# §10–11: Promotion — atomic head replacement after finalization
# ---------------------------------------------------------------------------

#: Statuses eligible for promotion. Must be a valid finalized state.
_PROMOTION_ELIGIBLE_STATUSES = frozenset(
    {"approved", "awaiting_review"}
)


def promote_run(
    project_dir: str | Path,
    phase_slug: str,
    run_id: str,
    *,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Promote a finalized run to current head.

    This is called *after* the project lock has been released by
    :func:`finalize_run_submission` (see §11 of the plan).

    The function acquires the current-results lock, validates the candidate,
    performs an atomic head replacement, writes a receipt, and returns a
    result dict describing what happened.

    Parameters
    ----------
    project_dir
        The project directory.
    phase_slug
        The phase being promoted.
    run_id
        The run to promote.
    timestamp
        Optional ISO timestamp override (for testing).

    Returns
    -------
    dict
        ``{"promoted": bool, "operation_id": str, "reason": str, ...}``
    """

    root = Path(project_dir).resolve()
    resolved_slug = project_state._resolve_slug(phase_slug)
    promoted_at = timestamp or project_state._now_iso()
    operation_id = f"promote:{resolved_slug}:{run_id}"

    result: dict[str, Any] = {
        "promoted": False,
        "operation_id": operation_id,
        "phase_slug": resolved_slug,
        "run_id": run_id,
        "reason": "",
    }

    # Read the run from project state (read-only, no lock needed here because
    # the project lock was already released and we're reading committed data).
    try:
        run = project_state.get_run(root, resolved_slug, run_id)
    except Exception as exc:
        result["reason"] = f"run not found: {exc}"
        _write_not_applied_receipt(root, operation_id, result["reason"])
        return result

    # Validate eligibility
    status = str(run.get("status", "")).strip()
    if status not in _PROMOTION_ELIGIBLE_STATUSES:
        result["reason"] = f"status {status!r} not eligible for promotion"
        _write_not_applied_receipt(root, operation_id, result["reason"])
        return result

    if not run.get("submitted_at") or not run.get("final_summary"):
        result["reason"] = "run is missing submitted_at or final_summary"
        _write_not_applied_receipt(root, operation_id, result["reason"])
        return result

    # Scientific outcome
    decision_record = run.get("decision_record")
    data = decision_record.get("data") if isinstance(decision_record, Mapping) else None
    outcome_raw = data.get("scientific_outcome") if isinstance(data, Mapping) else None
    if outcome_raw not in _BOOTSTRAP_ELIGIBLE_OUTCOMES:
        result["reason"] = f"scientific outcome {outcome_raw!r} not eligible"
        _write_not_applied_receipt(root, operation_id, result["reason"])
        return result

    # Integrity check
    try:
        if not project_state.run_integrity_report(root, resolved_slug, run_id).get("ok"):
            result["reason"] = "run fails integrity check"
            _write_not_applied_receipt(root, operation_id, result["reason"])
            return result
    except Exception as exc:
        result["reason"] = f"integrity check error: {exc}"
        _write_not_applied_receipt(root, operation_id, result["reason"])
        return result

    # Source integrity digests
    manifest_sha256 = str(run.get("manifest_sha256", "")).strip().lower()
    summary_sha256 = str(run.get("summary_sha256", "")).strip().lower()
    decision_sha256 = ""
    if isinstance(decision_record, Mapping):
        decision_sha256 = str(decision_record.get("sha256", "")).strip().lower()
    if not manifest_sha256 or not summary_sha256:
        result["reason"] = "run is missing manifest_sha256 or summary_sha256"
        _write_not_applied_receipt(root, operation_id, result["reason"])
        return result

    # Build the candidate head
    method_bound = is_phase_method_bound(resolved_slug)
    candidate_head: dict[str, Any] = {
        "run_id": run_id,
        "phase_slug": resolved_slug,
        "scientific_outcome": outcome_raw,
        "representation": "verified_run_bundle",
        "source_integrity": {
            "run_manifest_sha256": manifest_sha256,
            "final_summary_sha256": summary_sha256,
            "decision_sha256": decision_sha256 or "0" * 64,
        },
        "status_at_promotion": status,
    }

    if method_bound:
        identity = _resolve_run_method_identity(root, resolved_slug, run_id)
        if identity is None:
            result["reason"] = "method-bound run has no resolvable method identity"
            _write_not_applied_receipt(root, operation_id, result["reason"])
            return result
        candidate_head["method_identity"] = identity

    # --- All checks passed: acquire lock and write ---
    with current_results_lock(root):
        if method_bound:
            promoted, reason = _promote_branch_head(
                root, resolved_slug, candidate_head, operation_id, promoted_at
            )
        else:
            promoted, reason = _promote_global_head(
                root, resolved_slug, candidate_head, operation_id, promoted_at
            )
        result["promoted"] = promoted
        result["reason"] = reason
        if promoted:
            _write_applied_receipt(root, operation_id, result)
        else:
            _write_not_applied_receipt(root, operation_id, reason)
    return result


def _promote_global_head(
    root: Path,
    phase_slug: str,
    candidate: Mapping[str, Any],
    operation_id: str,
    promoted_at: str,
) -> tuple[bool, str]:
    """Promote a global (P1/P2) head. Must hold current_results_lock."""

    record = load_global(root)
    if record is None:
        record = {"schema_version": SCHEMA_VERSION, "heads": {}}
    heads = record["heads"]
    existing = heads.get(phase_slug)
    next_generation = (existing.get("generation", 0) + 1) if existing else 1

    head = _build_head_from_candidate(
        candidate,
        generation=next_generation,
        promoted_at=promoted_at,
        operation_id=operation_id,
        method_bound=False,
    )
    # Write prepared transaction
    _write_transaction(root, operation_id, {
        "phase_slug": phase_slug,
        "scope": "global",
        "expected_generation": existing.get("generation", 0) if existing else 0,
        "proposed_head_sha256": compute_head_sha256(head),
        "prepared_at": promoted_at,
    })
    # Atomically replace
    heads[phase_slug] = head
    record["heads"] = heads
    write_global_record(root, record)
    return True, f"promoted to generation {next_generation}"


def _promote_branch_head(
    root: Path,
    phase_slug: str,
    candidate: Mapping[str, Any],
    operation_id: str,
    promoted_at: str,
) -> tuple[bool, str]:
    """Promote a branch (P3/P4/P5) head. Must hold current_results_lock."""

    identity = candidate.get("method_identity")
    if not isinstance(identity, Mapping):
        return False, "candidate has no method identity"
    stable_id = str(identity.get("stable_id", "")).strip()
    if not stable_id:
        return False, "candidate has empty stable_id"

    record = load_branch(root, stable_id)
    if record is None:
        # Create a new branch record
        record = {
            "schema_version": SCHEMA_VERSION,
            "stable_id": stable_id,
            "method_status": "active",
            "catalog_generation": 0,
            "active_method_identity": dict(identity),
            "heads": {},
        }
    heads = record["heads"]
    existing = heads.get(phase_slug)
    next_generation = (existing.get("generation", 0) + 1) if existing else 1

    head = _build_head_from_candidate(
        candidate,
        generation=next_generation,
        promoted_at=promoted_at,
        operation_id=operation_id,
        method_bound=True,
    )
    # Write prepared transaction
    _write_transaction(root, operation_id, {
        "phase_slug": phase_slug,
        "scope": "branch",
        "branch_key": stable_id,
        "expected_generation": existing.get("generation", 0) if existing else 0,
        "proposed_head_sha256": compute_head_sha256(head),
        "prepared_at": promoted_at,
    })
    # Atomically replace
    heads[phase_slug] = head
    record["heads"] = heads
    # Update active method identity if this is the first head or identity changed
    current_active = record.get("active_method_identity")
    if not isinstance(current_active, Mapping):
        record["active_method_identity"] = dict(identity)
    write_branch_record(root, stable_id, record)
    return True, f"promoted to generation {next_generation}"


# ---------------------------------------------------------------------------
# §11: Transactions and receipts
# ---------------------------------------------------------------------------


def _write_transaction(
    root: Path,
    operation_id: str,
    details: Mapping[str, Any],
) -> None:
    """Write a prepared-transaction file."""

    path = transaction_path(root, operation_id)
    payload = {
        "operation_id": operation_id,
        **details,
    }
    _atomic_write_json(path, payload)


def _write_applied_receipt(
    root: Path,
    operation_id: str,
    result: Mapping[str, Any],
) -> None:
    """Write an applied receipt."""

    path = applied_receipt_path(root, operation_id)
    payload = {
        "operation_id": operation_id,
        "applied": True,
        "result": dict(result),
        "applied_at": project_state._now_iso(),
    }
    _atomic_write_json(path, payload)


def _write_not_applied_receipt(
    root: Path,
    operation_id: str,
    reason: str,
) -> None:
    """Write a not-applied receipt."""

    path = not_applied_receipt_path(root, operation_id)
    payload = {
        "operation_id": operation_id,
        "applied": False,
        "reason": reason,
        "applied_at": project_state._now_iso(),
    }
    _atomic_write_json(path, payload)


# ---------------------------------------------------------------------------
# §12: Phase 2 method reconciliation
# ---------------------------------------------------------------------------


def reconcile_method_catalog(
    project_dir: str | Path,
    *,
    write: bool = False,
) -> dict[str, Any]:
    """Reconcile branch records with the published Phase 2 method catalog.

    Reads the published method menu (``ideas/methods/``), resolves each
    method's identity, and updates the ``active_method_identity`` in
    branch records. Existing heads are retained — their freshness is
    derived from the identity comparison (§3.4, §12).

    This is non-destructive: it never deletes or modifies heads. It only
    updates the branch record's cached view of the active method.

    Parameters
    ----------
    project_dir
        The project directory.
    write
        If True, atomically update branch records inside
        :func:`current_results_lock`.

    Returns
    -------
    dict
        Reconciliation report: ``{"methods": {...}, "updated": [...], "written": bool}``
    """

    from core import method_menu

    root = Path(project_dir).resolve()
    report: dict[str, Any] = {
        "methods": {},
        "updated": [],
        "written": False,
        "catalog_sha256": "",
    }

    # Read the published method menu
    try:
        menu = method_menu.load_method_menu(root)
        catalog_sha = method_menu.catalog_version(root)
    except Exception:
        return report

    report["catalog_sha256"] = catalog_sha

    # Resolve each active method's identity
    for entry in menu.get("entries", []):
        if not isinstance(entry, Mapping):
            continue
        stable_id = str(entry.get("stable_id", "")).strip()
        version = str(entry.get("version", "")).strip()
        sha256 = str(entry.get("sha256", "")).strip().lower()
        status = str(entry.get("status", "active")).strip()
        if not stable_id or not version or len(sha256) != 64:
            continue
        report["methods"][stable_id] = {
            "stable_id": stable_id,
            "version": version,
            "definition_sha256": sha256,
            "status": status,
        }

    if write:
        with current_results_lock(root):
            for stable_id, identity in report["methods"].items():
                record = load_branch(root, stable_id)
                if record is None:
                    continue  # No branch record yet — nothing to reconcile
                # Update active method identity
                old_identity = record.get("active_method_identity")
                new_identity = {
                    "stable_id": identity["stable_id"],
                    "version": identity["version"],
                    "definition_sha256": identity["definition_sha256"],
                }
                if old_identity != new_identity:
                    record["active_method_identity"] = new_identity
                    record["catalog_generation"] = record.get("catalog_generation", 0) + 1
                    report["updated"].append(stable_id)
                # Always update catalog provenance
                record["catalog_source_run_id"] = None  # Set by Phase 02 finalization
                record["catalog_sha256"] = report["catalog_sha256"]
                record.pop("reconciliation_pending", None)
                write_branch_record(root, stable_id, record)
            report["written"] = True

    return report


def get_branch_freshness(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, dict[str, str]]:
    """Return the derived freshness status for every head in a branch.

    This is the primary read API for the UI (§15). It merges the branch
    record's heads with the active method identity and derives freshness.
    """

    root = Path(project_dir).resolve()
    record = load_branch(root, stable_id)
    if record is None:
        return {}
    active_identity = record.get("active_method_identity")
    method_status = str(record.get("method_status", "active")).strip()
    result: dict[str, dict[str, str]] = {}
    for slug, head in record.get("heads", {}).items():
        status = derive_head_status(head, active_identity, method_status=method_status)
        outcome = str(head.get("scientific_outcome", ""))
        result[slug] = {
            "status": status,
            "scientific_outcome": outcome,
            "run_id": str(head.get("run_id", "")),
            "generation": str(head.get("generation", 0)),
        }
    return result


# ---------------------------------------------------------------------------
# §9: Context resolution — resolve exact head run IDs for a new launch
# ---------------------------------------------------------------------------


def resolve_context_heads(
    project_dir: str | Path,
    target_phase: str,
    selected_method_id: str = "",
) -> dict[str, Any]:
    """Resolve which exact head run IDs should serve as context for a new run.

    Merges global heads (P1, P2) with branch heads (P3, P4, P5) for the
    selected method. Returns a dict mapping phase_slug → head info, or
    an empty dict if no current-results records exist (caller should
    fall back to all-history selection in that case — but only in shadow
    mode; enforced mode should block).

    Parameters
    ----------
    project_dir
        The project directory.
    target_phase
        The phase being launched.
    selected_method_id
        The stable method ID for method-bound phases.

    Returns
    -------
    dict
        ``{"phase_slug": {"run_id": str, "generation": int, ...}, ...}``
        or ``{}`` if no records exist.
    """

    root = Path(project_dir).resolve()
    result: dict[str, Any] = {}

    # Global heads (always included for any target phase)
    global_record = load_global(root)
    if global_record is not None:
        for slug, head in global_record.get("heads", {}).items():
            result[slug] = {
                "run_id": head["run_id"],
                "generation": head["generation"],
                "scope": "global",
                "head_sha256": compute_head_sha256(head),
            }

    # Branch heads (for method-bound target phases)
    if selected_method_id:
        method_id = str(selected_method_id).strip()
        branch_record = load_branch(root, method_id)
        if branch_record is not None:
            active_identity = branch_record.get("active_method_identity")
            method_status = str(branch_record.get("method_status", "active")).strip()
            for slug, head in branch_record.get("heads", {}).items():
                status = derive_head_status(
                    head, active_identity, method_status=method_status
                )
                entry = {
                    "run_id": head["run_id"],
                    "generation": head["generation"],
                    "scope": "branch",
                    "head_sha256": compute_head_sha256(head),
                    "freshness": status,
                }
                # Include stale heads as labeled recheck baselines (§9)
                if status == "stale":
                    entry["relationship"] = "stale_recheck_baseline"
                result[slug] = entry

    return result
