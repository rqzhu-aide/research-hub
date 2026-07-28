"""Transactional project and run state for Research Hub.

The state file is intentionally small and human-readable, but all writes go
through this module.  A per-project, cross-process lock protects read/modify/
write operations and each YAML update is committed with ``os.replace``.

Runs are execution records. A phase separately points at its current trusted
(``approved_run``) record, so starting or failing a rerun never destroys the
last trusted result. Downstream work becomes stale only when a replacement is
accepted or a completed Phase 02 run publishes an affected method revision.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import stat
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import yaml

from core.filesystem_utils import metadata_is_link_or_reparse
from core import method_menu

import logging
log = logging.getLogger(__name__)


SCHEMA_VERSION = 8

PAPER_WRITING_PHASE = "05-review-revision"
DRAFT_ASSEMBLY_PHASE = "04-draft-assembly"
METHOD_DEVELOPMENT_PHASE = "02-method-development"

# Slug renames: old → new.  Used by _migrate_slug_aliases to rewrite
# existing project state and filesystem layout so sealed history
# remains accessible after slugs are renamed in config.yaml.
SLUG_ALIASES: dict[str, str] = {
    "03-theoretical-justification": "03-idea-evaluation",
    "04-numerical-validation": "04-draft-assembly",
    "05-data-analysis": "05-review-revision",
    "06-paper-writing": "05-review-revision",
}
PHASE_SIX_SUBMISSION_ARTIFACTS = {
    "post_review_manuscript": ("manuscript-post-review.md", False),
    "review_diff": ("manuscript-post-review.diff", True),
}
REVIEW_BUNDLE_SCHEMA_VERSION = 1
MAX_REVIEW_BUNDLE_BYTES = 16 * 1024 * 1024
MAX_REVIEW_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_RUN_ARTIFACT_BYTES = 8 * 1024 * 1024
MAX_ROUND_SUPPORTING_FILES = 64
MAX_ROUND_SUPPORTING_BYTES = 64 * 1024 * 1024
MAX_SUMMARY_BYTES = 4 * 1024 * 1024
MAX_CONTROL_FILE_BYTES = 2 * 1024 * 1024
MAX_STATE_FILE_BYTES = 16 * 1024 * 1024
PROTOCOL_CHECKPOINT_SCHEMA_VERSION = 1
MAX_PROTOCOL_CHECKPOINT_BYTES = 256 * 1024
MAX_PROTOCOL_CHECKPOINT_FILES = 64
MAX_PROTOCOL_CHECKPOINT_AGGREGATE_BYTES = 16 * 1024 * 1024
MAX_LEGACY_MIGRATION_BYTES = 64 * 1024 * 1024
MAX_LEGACY_MIGRATION_FILES = 2_000
FILE_READ_CHUNK_BYTES = 256 * 1024
DECISION_RECORD_SCHEMA_VERSION = 2
PHASE_TWO_DECISION_RECORD_SCHEMA_VERSION = 3
SUPPORTED_DECISION_RECORD_SCHEMA_VERSIONS = frozenset({1, 2, 3})
MAX_DECISION_RECORD_BYTES = 128 * 1024
MAX_DECISION_TEXT_LENGTH = 12_000
MAX_DECISION_LIST_ITEMS = 12
MAX_SCIENTIFIC_RECORD_CHANGES = 50
SCIENTIFIC_OUTCOMES = frozenset({"Complete", "Partial", "Failed"})
COMPLETED_SCIENTIFIC_OUTCOMES = frozenset({"Complete", "Partial"})
COMPLETED_RESULT_STATUSES = frozenset({"approved", "awaiting_review"})
APPROVAL_USER_ACTIONS = frozenset({
    "approve",
    "approve_with_limitations",
    "request_revision",
    "rerun",
    "defer",
})
PHASE_TWO_USER_ACTIONS = frozenset({
    "proceed",
    "rerun",
    "return_to_phase_1",
    "defer",
})
RECOMMENDED_USER_ACTIONS = APPROVAL_USER_ACTIONS | PHASE_TWO_USER_ACTIONS
DECISION_OPTION_KEYS = frozenset({
    "approve",
    "approve_with_limitations",
    "request_revision",
    "rerun",
    "defer",
})
PHASE_TWO_DECISION_OPTION_KEYS = frozenset({
    "proceed",
    "rerun",
    "return_to_phase_1",
    "defer",
})
SCIENTIFIC_RECORD_OPERATIONS = frozenset({"add", "revise", "withdraw"})
FORMULATION_STATES = frozenset({"Proposed", "Current", "Superseded", "Withdrawn"})
ASSESSMENT_STATUSES = frozenset({
    "Supported",
    "Partially supported",
    "Contradicted",
    "Inconclusive",
    "Not assessable",
    "Untested",
})
STATEMENT_TYPES = frozenset({
    "Definition or methodological statement",
    "Mathematical statement",
    "Empirical statement",
    "Interpretive",
    "Originality",
    "Scientific importance",
})
LOGICAL_STATUSES = frozenset({
    "proved",
    "conjectured",
    "unproved",
    "refuted by a counterexample",
    "Not applicable",
})
MATHEMATICAL_RESULT_TYPES = frozenset({
    "identity or exact calculation",
    "finite-sample equality",
    "inequality or bound",
    "approximation with a stated remainder or error",
    "asymptotic limit, rate, or distribution",
    "Not applicable",
})
SCIENTIFIC_RECORD_FIELDS = frozenset({
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
NEW_STATEMENT_REQUIRED_FIELDS = SCIENTIFIC_RECORD_FIELDS

RUN_STATUSES = frozenset({
    "starting",
    "running",
    "submitting",
    "stopping",
    "awaiting_review",
    "approved",
    "revision_requested",
    "failed",
    "cancelled",
    "superseded",
})
ACTIVE_RUN_STATUSES = frozenset({"starting", "running", "submitting", "stopping"})
TERMINAL_RUN_STATUSES = frozenset({
    "approved",
    "revision_requested",
    "failed",
    "cancelled",
    "superseded",
})


class ProjectStateError(RuntimeError):
    """Base class for state-machine errors."""


class StateConflict(ProjectStateError):
    """The requested transition conflicts with current project state."""


class StateValidationError(ProjectStateError, ValueError):
    """The supplied transition data is invalid."""


# ---------------------------------------------------------------------------
# Paths, time, and locking
# ---------------------------------------------------------------------------


def state_dir(project_dir: str | Path) -> Path:
    """Return a control directory outside the agent-writable project root."""

    project = Path(project_dir).resolve(strict=False)
    return project.parent / ".research-hub-control" / project.name


def legacy_state_dir(project_dir: str | Path) -> Path:
    return Path(project_dir).resolve(strict=False) / ".log"


def state_file(project_dir: str | Path) -> Path:
    return state_dir(project_dir) / "project.yaml"


def lock_file(project_dir: str | Path) -> Path:
    return state_dir(project_dir) / "project.lock"


def _metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    """Backward-compatible alias for :func:`core.filesystem_utils.metadata_is_link_or_reparse`."""

    return metadata_is_link_or_reparse(metadata)


def _path_uses_link_below(path: Path, boundary: Path) -> bool:
    """Return whether an existing component below a trusted root redirects."""

    candidate = Path(os.path.abspath(path))
    root = Path(os.path.abspath(boundary))
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if _metadata_is_link_or_reparse(metadata):
            return True
    return False


def _ensure_plain_directory_tree(
    directory: Path, boundary: Path, *, label: str
) -> Path:
    """Create a directory without traversing links below a trusted root."""

    try:
        root = Path(boundary).resolve(strict=True)
    except OSError as exc:
        raise StateValidationError(f"{label} boundary is unavailable: {boundary}") from exc
    candidate = Path(os.path.abspath(directory))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise StateValidationError(f"{label} escaped its allowed directory") from exc

    current = root
    for part in relative.parts:
        current = current / part
        try:
            current.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise StateValidationError(f"could not create {label}: {current}") from exc
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise StateValidationError(f"could not inspect {label}: {current}") from exc
        if _metadata_is_link_or_reparse(metadata):
            raise StateValidationError(
                f"{label} must not use a symbolic link or reparse point: {current}"
            )
        if not stat.S_ISDIR(metadata.st_mode):
            raise StateValidationError(f"{label} must be a directory: {current}")
    return candidate


def _ensure_control_directory(project_dir: str | Path) -> Path:
    project = Path(project_dir).resolve(strict=False)
    return _ensure_plain_directory_tree(
        state_dir(project), project.parent, label="project control directory"
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def decision_report_version(kind: str, report: Mapping[str, Any]) -> str:
    """Return a stable fingerprint of decision-relevant report content."""

    def canonicalize(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): canonicalize(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
                if str(key) != "checked_at"
            }
        if isinstance(value, (list, tuple)):
            return [canonicalize(item) for item in value]
        return value

    payload = json.dumps(
        {"kind": str(kind), "report": canonicalize(report)},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@contextmanager
def _project_lock(project_dir: str | Path, timeout: float = 15.0) -> Iterator[None]:
    """Acquire the project's advisory lock on Windows or POSIX.

    The lock covers one byte in a dedicated file.  It is advisory, so callers
    must use this module rather than writing ``project.yaml`` directly.
    """

    _ensure_control_directory(project_dir)
    path = lock_file(project_dir)
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        opened_metadata = os.fstat(descriptor)
        path_metadata = path.lstat()
    except OSError as exc:
        try:
            os.close(descriptor)
        except (NameError, OSError):
            pass
        raise StateValidationError(f"project state lock is unavailable: {path}") from exc
    if (
        _metadata_is_link_or_reparse(path_metadata)
        or not stat.S_ISREG(opened_metadata.st_mode)
        or not os.path.samestat(opened_metadata, path_metadata)
    ):
        os.close(descriptor)
        raise StateValidationError(
            f"project state lock must be a regular file, not a link: {path}"
        )
    handle = os.fdopen(descriptor, "a+b")
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
                    raise StateConflict(
                        f"timed out waiting for project state lock: {path}"
                    )
                time.sleep(0.025)
        try:
            locked_metadata = os.fstat(handle.fileno())
            current_path_metadata = path.lstat()
        except OSError as exc:
            raise StateValidationError(
                f"project state lock changed while it was being acquired: {path}"
            ) from exc
        if (
            _metadata_is_link_or_reparse(current_path_metadata)
            or not stat.S_ISREG(locked_metadata.st_mode)
            or not os.path.samestat(locked_metadata, current_path_metadata)
        ):
            raise StateValidationError(
                f"project state lock changed while it was being acquired: {path}"
            )
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


# ---------------------------------------------------------------------------
# Atomic persistence and schema migration
# ---------------------------------------------------------------------------


def _read_bounded_file(
    path: Path,
    *,
    maximum: int,
    label: str,
    allow_empty: bool = False,
) -> bytes:
    """Read one regular file without following its final path component."""

    try:
        path_metadata = path.lstat()
    except OSError as exc:
        raise StateValidationError(f"{label} could not be read: {path}") from exc
    if _metadata_is_link_or_reparse(path_metadata):
        raise StateValidationError(
            f"{label} must not be a symbolic link or reparse point: {path}"
        )

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise StateValidationError(f"{label} could not be read: {path}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not os.path.samestat(path_metadata, metadata):
            raise StateValidationError(f"{label} changed while it was being opened: {path}")
        if not stat.S_ISREG(metadata.st_mode):
            raise StateValidationError(f"{label} must be a regular file: {path}")
        if metadata.st_size > maximum:
            raise StateValidationError(
                f"{label} exceeds the {maximum:,}-byte safety limit: {path}"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read(maximum + 1)
        if len(payload) > maximum:
            raise StateValidationError(
                f"{label} exceeds the {maximum:,}-byte safety limit: {path}"
            )
        if len(payload) != metadata.st_size:
            raise StateValidationError(f"{label} changed while it was being read: {path}")
        try:
            final_metadata = path.lstat()
        except OSError as exc:
            raise StateValidationError(f"{label} changed while it was being read: {path}") from exc
        if _metadata_is_link_or_reparse(final_metadata) or not os.path.samestat(
            metadata, final_metadata
        ):
            raise StateValidationError(f"{label} changed while it was being read: {path}")
        if not allow_empty and not payload.strip():
            raise StateValidationError(f"{label} is empty: {path}")
        return payload
    finally:
        os.close(descriptor)


def _hash_bounded_file(
    path: Path,
    *,
    maximum: int,
    label: str,
    allow_empty: bool = False,
) -> tuple[str, int]:
    """Hash one bounded regular file through fixed-size chunks."""

    try:
        path_metadata = path.lstat()
    except OSError as exc:
        raise StateValidationError(f"{label} could not be read: {path}") from exc
    if _metadata_is_link_or_reparse(path_metadata):
        raise StateValidationError(
            f"{label} must not be a symbolic link or reparse point: {path}"
        )

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise StateValidationError(f"{label} could not be read: {path}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not os.path.samestat(path_metadata, metadata):
            raise StateValidationError(f"{label} changed while it was being opened: {path}")
        if not stat.S_ISREG(metadata.st_mode):
            raise StateValidationError(f"{label} must be a regular file: {path}")
        if metadata.st_size > maximum:
            raise StateValidationError(
                f"{label} exceeds the {maximum:,}-byte safety limit: {path}"
            )
        digest = hashlib.sha256()
        size = 0
        has_content = False
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            while True:
                chunk = handle.read(FILE_READ_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > maximum:
                    raise StateValidationError(
                        f"{label} exceeds the {maximum:,}-byte safety limit: {path}"
                    )
                digest.update(chunk)
                has_content = has_content or bool(chunk.strip())
        if size != metadata.st_size:
            raise StateValidationError(f"{label} changed while it was being read: {path}")
        try:
            final_metadata = path.lstat()
        except OSError as exc:
            raise StateValidationError(f"{label} changed while it was being read: {path}") from exc
        if _metadata_is_link_or_reparse(final_metadata) or not os.path.samestat(
            metadata, final_metadata
        ):
            raise StateValidationError(f"{label} changed while it was being read: {path}")
        if not allow_empty and not has_content:
            raise StateValidationError(f"{label} is empty: {path}")
        return digest.hexdigest(), size
    finally:
        os.close(descriptor)


def bounded_file_bytes(
    path: str | Path,
    *,
    maximum: int,
    label: str,
    allow_empty: bool = False,
) -> bytes:
    """Read a bounded regular file for another Research Hub component."""

    return _read_bounded_file(
        Path(path), maximum=maximum, label=label, allow_empty=allow_empty
    )


def bounded_file_digest(
    path: str | Path,
    *,
    maximum: int,
    label: str,
    allow_empty: bool = False,
) -> tuple[str, int]:
    """Hash a bounded regular file for another Research Hub component."""

    return _hash_bounded_file(
        Path(path), maximum=maximum, label=label, allow_empty=allow_empty
    )


def _legacy_migration_plan(legacy: Path) -> list[tuple[Path, Path, int]]:
    """Return a bounded plan for the recognized legacy control files."""

    try:
        legacy_metadata = legacy.lstat()
    except OSError as exc:
        raise StateValidationError(f"legacy state directory is unavailable: {legacy}") from exc
    if _metadata_is_link_or_reparse(legacy_metadata) or not stat.S_ISDIR(
        legacy_metadata.st_mode
    ):
        raise StateValidationError("legacy state path must be a regular directory")

    sources: list[tuple[Path, Path, int]] = []
    total = 0

    def add_file(source: Path, relative: Path) -> None:
        nonlocal total
        try:
            metadata = source.lstat()
        except OSError as exc:
            raise StateValidationError(f"legacy state entry is unavailable: {source}") from exc
        if _metadata_is_link_or_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
            raise StateValidationError(
                f"legacy state contains a non-regular file: {source}"
            )
        if metadata.st_size > MAX_RUN_ARTIFACT_BYTES:
            raise StateValidationError(
                f"legacy state file exceeds the per-file safety limit: {source}"
            )
        total += metadata.st_size
        sources.append((source, relative, metadata.st_size))
        if len(sources) > MAX_LEGACY_MIGRATION_FILES:
            raise StateValidationError("legacy state contains too many files to migrate safely")
        if total > MAX_LEGACY_MIGRATION_BYTES:
            raise StateValidationError("legacy state exceeds the aggregate migration limit")

    project_yaml = legacy / "project.yaml"
    add_file(project_yaml, Path("project.yaml"))
    runs = legacy / "runs"
    if runs.exists():
        try:
            runs_metadata = runs.lstat()
        except OSError as exc:
            raise StateValidationError("legacy runs directory is unavailable") from exc
        if _metadata_is_link_or_reparse(runs_metadata) or not stat.S_ISDIR(
            runs_metadata.st_mode
        ):
            raise StateValidationError("legacy runs path must be a regular directory")
        stack = [runs]
        while stack:
            directory = stack.pop()
            try:
                directory_metadata = directory.lstat()
            except OSError as exc:
                raise StateValidationError(
                    f"legacy state directory could not be inspected: {directory}"
                ) from exc
            if _metadata_is_link_or_reparse(directory_metadata) or not stat.S_ISDIR(
                directory_metadata.st_mode
            ):
                raise StateValidationError(
                    f"legacy state contains a symbolic link or reparse point: {directory}"
                )
            try:
                entries = list(os.scandir(directory))
            except OSError as exc:
                raise StateValidationError(
                    f"legacy state directory could not be inspected: {directory}"
                ) from exc
            for entry in entries:
                source = Path(entry.path)
                try:
                    entry_metadata = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    raise StateValidationError(
                        f"legacy state entry is unavailable: {source}"
                    ) from exc
                if _metadata_is_link_or_reparse(entry_metadata):
                    raise StateValidationError(
                        f"legacy state contains a symbolic link or reparse point: {source}"
                    )
                if stat.S_ISDIR(entry_metadata.st_mode):
                    stack.append(source)
                elif stat.S_ISREG(entry_metadata.st_mode):
                    add_file(source, source.relative_to(legacy))
                else:
                    raise StateValidationError(
                        f"legacy state contains a special file: {source}"
                    )
    return sources


def _copy_legacy_state_safely(legacy: Path, destination: Path) -> None:
    """Copy recognized legacy files, writing project.yaml last as the commit marker."""

    plan = _legacy_migration_plan(legacy)
    destination_boundary = destination.parent.parent
    _ensure_plain_directory_tree(
        destination, destination_boundary, label="legacy migration destination"
    )
    project_entry = next(item for item in plan if item[1] == Path("project.yaml"))
    for source, relative, expected_size in [
        item for item in plan if item[1] != Path("project.yaml")
    ] + [project_entry]:
        target = destination / relative
        _ensure_plain_directory_tree(
            target.parent,
            destination_boundary,
            label="legacy migration destination",
        )
        try:
            current_legacy_metadata = legacy.lstat()
        except OSError as exc:
            raise StateValidationError(
                f"legacy state directory is unavailable: {legacy}"
            ) from exc
        if (
            _metadata_is_link_or_reparse(current_legacy_metadata)
            or not stat.S_ISDIR(current_legacy_metadata.st_mode)
            or _path_uses_link_below(source, legacy)
        ):
            raise StateValidationError(
                f"legacy state contains a symbolic link or reparse point: {source}"
            )
        payload = _read_bounded_file(
            source,
            maximum=max(expected_size, 1),
            label="legacy state file",
            allow_empty=True,
        )
        if len(payload) != expected_size:
            raise StateValidationError(
                f"legacy state file changed during migration: {source}"
            )
        try:
            target_metadata = target.lstat()
        except FileNotFoundError:
            target_metadata = None
        except OSError as exc:
            raise StateValidationError(
                f"legacy migration destination is unavailable: {target}"
            ) from exc
        if target_metadata is not None and (
            _metadata_is_link_or_reparse(target_metadata)
            or not stat.S_ISREG(target_metadata.st_mode)
        ):
            raise StateValidationError(
                f"legacy migration destination must be a regular file: {target}"
            )
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            _ensure_plain_directory_tree(
                target.parent,
                destination_boundary,
                label="legacy migration destination",
            )
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()


def _read_unlocked(project_dir: str | Path) -> dict[str, Any]:
    path = state_file(project_dir)
    legacy = legacy_state_dir(project_dir)
    if not path.exists() and (legacy / "project.yaml").is_file():
        # Copy once so existing projects retain their history while future
        # control mutations happen outside the Hermes workspace. Keep the old
        # folder as a recoverable backup and never trust it again after import.
        _copy_legacy_state_safely(legacy, state_dir(project_dir))
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "project": {}, "phases": {}}
    payload = _read_bounded_file(
        path,
        maximum=MAX_STATE_FILE_BYTES,
        label="project state",
        allow_empty=True,
    )
    try:
        value = yaml.safe_load(payload.decode("utf-8")) or {}
    except (UnicodeError, yaml.YAMLError) as exc:
        raise StateValidationError(f"project state is not valid UTF-8 YAML: {path}") from exc
    if not isinstance(value, dict):
        raise StateValidationError(f"project state must be a mapping: {path}")
    return value


def _save_unlocked(project_dir: str | Path, data: Mapping[str, Any]) -> None:
    """Atomically replace project.yaml with a fully flushed temporary file."""

    directory = _ensure_control_directory(project_dir)
    path = state_file(project_dir)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=directory
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            yaml.safe_dump(
                dict(data),
                handle,
                sort_keys=False,
                default_flow_style=False,
                allow_unicode=True,
                width=100,
            )
            handle.flush()
            if os.fstat(handle.fileno()).st_size > MAX_STATE_FILE_BYTES:
                raise StateValidationError(
                    f"project state exceeds the {MAX_STATE_FILE_BYTES:,}-byte safety limit"
                )
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _save(project_dir: str | Path, data: dict[str, Any]) -> None:
    """Compatibility helper for callers that used the old private function."""

    with _project_lock(project_dir):
        migrated = _migrate(copy.deepcopy(data))
        _save_unlocked(project_dir, migrated)


def _new_phase() -> dict[str, Any]:
    return {
        "status": "pending",
        "approved_run": None,
        "latest_run": None,
        "latest_run_status": None,
        "stale": False,
        "stale_at": None,
        "stale_reason": None,
        "stale_by_run": None,
        "publication_readiness": None,
        "runs": [],
    }


def _restore_legacy_active_process_pid(data: dict[str, Any]) -> None:
    """Attach a valid legacy active marker PID to its exact active run.

    The former launcher stored the worker PID only in ``_active_run``.  Keep
    that PID for liveness reconciliation, but do not trust legacy marker data
    as a process-birth identity.  Without a verified identity, cleanup code
    must not terminate the PID automatically.
    """

    marker = data.get("_active_run")
    if not isinstance(marker, Mapping):
        marker = data.get("active_run")
    if not isinstance(marker, Mapping):
        return

    phase_names: list[str] = []
    for key in ("phase", "phase_slug"):
        if key not in marker:
            continue
        value = marker.get(key)
        if not isinstance(value, str) or not value.strip():
            return
        phase_names.append(value.strip())
    if not phase_names or len(set(phase_names)) != 1:
        return

    phase = data.get("phases", {}).get(phase_names[0])
    if not isinstance(phase, Mapping):
        return
    runs = phase.get("runs")
    if not isinstance(runs, list):
        return

    indexed_run: dict[str, Any] | None = None
    if "run_index" in marker:
        run_index = marker.get("run_index")
        if (
            isinstance(run_index, bool)
            or not isinstance(run_index, int)
            or run_index < 0
            or run_index >= len(runs)
            or not isinstance(runs[run_index], dict)
        ):
            return
        indexed_run = runs[run_index]

    identified_run: dict[str, Any] | None = None
    if "run_id" in marker:
        run_id = marker.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            return
        matches = [run for run in runs if run.get("run_id") == run_id]
        if len(matches) != 1:
            return
        identified_run = matches[0]

    run = indexed_run if indexed_run is not None else identified_run
    if run is None or (
        indexed_run is not None
        and identified_run is not None
        and indexed_run is not identified_run
    ):
        return
    if run.get("status") not in ACTIVE_RUN_STATUSES:
        return

    pid = marker.get("pid")
    if (
        isinstance(pid, bool)
        or not isinstance(pid, int)
        or pid <= 0
        or pid > (1 << 31) - 1
    ):
        return
    if run.get("process_pid") is None:
        run["process_pid"] = pid


def _resolve_slug(slug: str) -> str:
    """Map a possibly-legacy slug to its current name (no-op for current slugs)."""
    return SLUG_ALIASES.get(slug, slug)


_ERROR_PATTERNS_INFRA = (
    "modulenotfounderror",
    "no module named",
    "can't open file",
    "no such file or directory",
    "importerror",
    "worker exited before completing",
    "not importable",
)


def _classify_error(error_text: str) -> str:
    """Classify a run failure as 'infrastructure' or 'research'."""
    lower = error_text.lower()
    if any(pat in lower for pat in _ERROR_PATTERNS_INFRA):
        return "infrastructure"
    return "research"


def _migrate_sealed_decision_record(root: Path, run: dict[str, Any]) -> None:
    """Repair a sealed decision record whose origins name a legacy slug.

    The change origins are validated against the manifest's (already migrated)
    phase slug, so the sealed file must be rewritten and its recorded hash,
    size, and parsed copy recomputed.
    """

    record = run.get("decision_record")
    if not isinstance(record, dict):
        return
    relative = str(record.get("path", "")).strip()
    if not relative:
        return
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
        if path.stat().st_size > MAX_CONTROL_FILE_BYTES:
            return
        payload = path.read_bytes()
        data = json.loads(payload.decode("utf-8"))
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    changed = False
    changes = data.get("scientific_record_changes")
    if isinstance(changes, list):
        for change in changes:
            if not isinstance(change, dict):
                continue
            origin = change.get("change_origin")
            if isinstance(origin, dict):
                old = str(origin.get("phase", ""))
                if _resolve_slug(old) != old:
                    origin["phase"] = _resolve_slug(old)
                    changed = True
    if not changed:
        return
    try:
        normalized = validate_decision_record(data)
    except (ProjectStateError, StateValidationError, ValueError, TypeError):
        return
    new_payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    path.write_bytes(new_payload)
    new_hash = hashlib.sha256(new_payload).hexdigest()
    old_hash = str(record.get("sha256", ""))
    record["sha256"] = new_hash
    record["size"] = len(new_payload)
    record["data"] = normalized

    # F9 fix: keep the approval-baseline acknowledgement consistent with the
    # migrated record. approve_run stored the pre-migration digest here; after
    # migration the audit trail would otherwise reference a stale hash.
    ack = run.get("approval_baseline_acknowledgement")
    if isinstance(ack, dict):
        ack_digest = str(ack.get("decision_record_sha256", ""))
        if ack_digest and ack_digest == old_hash:
            ack["decision_record_sha256"] = new_hash
            ack["decision_record_rehashed_at_migration"] = _now_iso()

def _migrate_sealed_protocol_checkpoint(root: Path, run: dict[str, Any]) -> None:
    """Repair a sealed protocol checkpoint whose identity names a legacy slug."""

    record = run.get("protocol_checkpoint")
    if not isinstance(record, dict):
        return
    relative = str(record.get("path", "")).strip()
    if not relative:
        return
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
        if path.stat().st_size > MAX_CONTROL_FILE_BYTES:
            return
        payload = path.read_bytes()
        data = json.loads(payload.decode("utf-8"))
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    old = str(data.get("phase_slug", ""))
    if _resolve_slug(old) == old:
        return
    data["phase_slug"] = _resolve_slug(old)
    new_payload = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    path.write_bytes(new_payload)
    record["sha256"] = hashlib.sha256(new_payload).hexdigest()
    record["size"] = len(new_payload)
    record["data"] = data

def _rewrite_slug_path_strings(
    value: Any, old_slug: str, new_slug: str
) -> tuple[Any, bool]:
    """Recursively rewrite run-state path strings for a renamed phase slug.

    The migration moves ``runs/<old>/`` and ``phase-summaries/<old>/`` on
    disk; every recorded path string (snapshot paths, prompt and summary
    paths, decision-record paths, ``final_summary``) must follow or sealed
    integrity checks fail against files that no longer exist at the recorded
    location.
    """

    replacements = (
        (f"/runs/{old_slug}/", f"/runs/{new_slug}/"),
        (f"\\runs\\{old_slug}\\", f"\\runs\\{new_slug}\\"),
        (
            f"phase-summaries/{old_slug}/",
            f"phase-summaries/{new_slug}/",
        ),
        (
            f"phase-summaries\\{old_slug}\\",
            f"phase-summaries\\{new_slug}\\",
        ),
    )
    if isinstance(value, dict):
        changed = False
        rewritten: dict[str, Any] = {}
        for key, item in value.items():
            new_item, item_changed = _rewrite_slug_path_strings(
                item, old_slug, new_slug
            )
            rewritten[key] = new_item
            changed = changed or item_changed
        return rewritten, changed
    if isinstance(value, list):
        changed = False
        rewritten_list: list[Any] = []
        for item in value:
            new_item, item_changed = _rewrite_slug_path_strings(
                item, old_slug, new_slug
            )
            rewritten_list.append(new_item)
            changed = changed or item_changed
        return rewritten_list, changed
    if isinstance(value, str):
        rewritten_value = value
        for old_path, new_path in replacements:
            rewritten_value = rewritten_value.replace(old_path, new_path)
        if rewritten_value != value:
            return rewritten_value, True
    return value, False

def _migrate_slug_aliases(
    project_dir: str | Path, data: dict[str, Any]
) -> None:
    """Rewrite legacy phase slugs in state and move filesystem directories.

    Idempotent: if no legacy slugs are present, it returns immediately.
    Touches: phase dict keys, dependencies, context_inputs, prerequisite
    snapshot requirements, and the sealed manifest ``phase_slug`` field +
    recomputed hash.  Moves ``runs/<old>/`` and ``phase-summaries/<old>/``
    on disk.
    """

    if not SLUG_ALIASES:
        return
    phases = data.get("phases", {})
    if not isinstance(phases, dict):
        return

    # Detect whether any alias work is needed in the state data.
    old_keys = [k for k in phases if k in SLUG_ALIASES]
    deps = data.get("dependencies", {})
    stale_deps = False
    if isinstance(deps, dict):
        stale_deps = any(
            old in SLUG_ALIASES
            for prereqs in deps.values()
            if isinstance(prereqs, list)
            for old in prereqs
        )
    if not old_keys and not stale_deps:
        # State is already migrated, but filesystem dirs may still
        # have legacy names from a previous incomplete migration.
        pass
    else:
        # 1. Rename phase dict keys; merge instead of overwrite.
        #    Multiple legacy slugs can map to the same new slug (e.g. both
        #    05-data-analysis and 06-paper-writing → 05-review-revision).
        #    Blind assignment would silently destroy one phase's history.
        for old_slug, new_slug in SLUG_ALIASES.items():
            if old_slug not in phases or old_slug == new_slug:
                continue
            old_phase = phases.pop(old_slug)
            if new_slug not in phases:
                phases[new_slug] = old_phase
            elif isinstance(phases[new_slug], dict) and isinstance(old_phase, dict):
                # Merge: concatenate runs lists, preserving both histories.
                existing_runs = phases[new_slug].get("runs", [])
                if not isinstance(existing_runs, list):
                    existing_runs = []
                merged_runs = list(old_phase.get("runs", [])) + existing_runs
                phases[new_slug].setdefault("runs", [])
                phases[new_slug]["runs"] = merged_runs
                # Preserve the legacy phase's metadata if the target is empty.
                for key, value in old_phase.items():
                    if key == "runs":
                        continue
                    if key not in phases[new_slug] or not phases[new_slug][key]:
                        phases[new_slug][key] = value
            else:
                # Type mismatch: keep the existing and log a warning.
                phases[new_slug] = old_phase

    # 2. Rewrite dependencies
    deps = data.get("dependencies", {})
    if isinstance(deps, dict):
        new_deps: dict[str, list[str]] = {}
        for phase_key, prereqs in deps.items():
            resolved_key = _resolve_slug(phase_key)
            if isinstance(prereqs, list):
                new_deps[resolved_key] = [_resolve_slug(p) for p in prereqs]
            else:
                new_deps[resolved_key] = prereqs
        data["dependencies"] = new_deps

    # 3. Rewrite every run's context_inputs and prerequisite_snapshot
    for phase_slug, phase in phases.items():
        if not isinstance(phase, dict):
            continue
        runs = phase.get("runs", [])
        if not isinstance(runs, list):
            continue
        for run_index, run in enumerate(runs):
            if not isinstance(run, dict):
                continue
            # Backfill run_number for legacy runs (pre-R11)
            if not run.get("run_number"):
                run["run_number"] = run_index + 1
            # context_inputs
            ctx = run.get("context_inputs")
            if isinstance(ctx, list):
                for entry in ctx:
                    if isinstance(entry, dict) and entry.get("phase"):
                        entry["phase"] = _resolve_slug(str(entry["phase"]))
            # prerequisite_snapshot requirements
            snap = run.get("prerequisite_snapshot")
            if isinstance(snap, dict):
                for req in snap.get("requirements", []):
                    if isinstance(req, dict) and req.get("phase"):
                        req["phase"] = _resolve_slug(str(req["phase"]))
                snap["phase"] = _resolve_slug(str(snap.get("phase", "")))
            # Path strings: final_summary, decision_record.path, manifest_path,
            # and any other recorded path must follow the moved directories.
            for old_slug, new_slug in SLUG_ALIASES.items():
                if old_slug == new_slug:
                    continue
                rewritten_run, run_changed = _rewrite_slug_path_strings(
                    runs[run_index], old_slug, new_slug
                )
                if run_changed:
                    runs[run_index] = rewritten_run
        # latest_run reference is already inside the phase dict (resolved key)

    # 4. Rewrite active_run marker
    active = data.get("active_run")
    if isinstance(active, dict) and active.get("phase_slug"):
        active["phase_slug"] = _resolve_slug(str(active["phase_slug"]))

    # 5. Move filesystem directories and patch manifests
    runs_root = state_dir(project_dir) / "runs"
    summaries_root = Path(project_dir).resolve() / "phase-summaries"

    for old_slug, new_slug in SLUG_ALIASES.items():
        if old_slug == new_slug:
            continue
        # Move runs/<old>/ → runs/<new>/
        old_runs = runs_root / old_slug
        new_runs = runs_root / new_slug
        if old_runs.is_dir():
            new_runs.parent.mkdir(parents=True, exist_ok=True)
            if new_runs.exists():
                # Merge: move individual files. Items that collide (target
                # already exists) are quarantined instead of deleted; an
                # integrity-first system must never destroy sealed artifacts.
                leftover: list[Path] = []
                for item in old_runs.iterdir():
                    target = new_runs / item.name
                    if not target.exists():
                        item.rename(target)
                    else:
                        leftover.append(item)
                if leftover:
                    quarantine = runs_root / f"{new_slug}.migration-conflicts"
                    quarantine.mkdir(parents=True, exist_ok=True)
                    for item in leftover:
                        item.rename(quarantine / item.name)
                    old_runs.rmdir()
                else:
                    old_runs.rmdir()
            else:
                old_runs.rename(new_runs)
        # Move phase-summaries/<old>/ → phase-summaries/<new>/
        old_sum = summaries_root / old_slug
        new_sum = summaries_root / new_slug
        if old_sum.is_dir():
            new_sum.parent.mkdir(parents=True, exist_ok=True)
            if new_sum.exists():
                sum_leftover: list[Path] = []
                for item in old_sum.iterdir():
                    target = new_sum / item.name
                    if not target.exists():
                        item.rename(target)
                    else:
                        sum_leftover.append(item)
                if sum_leftover:
                    quarantine = summaries_root / f"{new_slug}.migration-conflicts"
                    quarantine.mkdir(parents=True, exist_ok=True)
                    for item in sum_leftover:
                        item.rename(quarantine / item.name)
                    old_sum.rmdir()
                else:
                    old_sum.rmdir()
            else:
                old_sum.rename(new_sum)

    # 6. Patch phase_slug in sealed manifests and recompute hashes.
    #    Also fix manifest_path to point at the renamed runs/ directory.
    for phase_slug, phase in phases.items():
        if not isinstance(phase, dict):
            continue
        for run in phase.get("runs", []):
            if not isinstance(run, dict):
                continue
            manifest_path = run.get("manifest_path")
            if not manifest_path:
                continue
            manifest_file = Path(str(manifest_path))
            # If the path still references a legacy slug, resolve it.
            resolved_manifest_path = runs_root / phase_slug / manifest_file.name
            if manifest_file.resolve() != resolved_manifest_path.resolve():
                manifest_file = resolved_manifest_path
            if not manifest_file.is_file():
                continue
            try:
                # Bounded read: manifest files are control files, capped at
                # MAX_CONTROL_FILE_BYTES to match the module's read discipline.
                file_size = manifest_file.stat().st_size
                if file_size > MAX_CONTROL_FILE_BYTES:
                    continue
                payload = manifest_file.read_bytes()
                manifest = json.loads(payload.decode("utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            changed = False
            old_in_manifest = manifest.get("phase_slug", "")
            if old_in_manifest and _resolve_slug(old_in_manifest) != old_in_manifest:
                manifest["phase_slug"] = _resolve_slug(old_in_manifest)
                changed = True
            # The frozen phase plan records its slug; rerun and display logic
            # compare it against the current phase slug.
            frozen_phase = manifest.get("phase")
            if isinstance(frozen_phase, dict):
                frozen_slug = str(frozen_phase.get("slug", ""))
                if _resolve_slug(frozen_slug) != frozen_slug:
                    frozen_phase["slug"] = _resolve_slug(frozen_slug)
                    changed = True
            # Frozen summary context references prerequisite phases by slug.
            summaries = manifest.get("snapshots", {}).get("summaries")
            if isinstance(summaries, list):
                for entry in summaries:
                    if isinstance(entry, dict) and entry.get("phase"):
                        old_entry_slug = str(entry["phase"])
                        if _resolve_slug(old_entry_slug) != old_entry_slug:
                            entry["phase"] = _resolve_slug(old_entry_slug)
                            changed = True
            # Every recorded path (snapshots, prompt, summary, decision,
            # checkpoint) must follow the moved runs/ and phase-summaries/
            # directories or sealed integrity verification fails.
            for old_slug, new_slug in SLUG_ALIASES.items():
                if old_slug == new_slug:
                    continue
                manifest, paths_changed = _rewrite_slug_path_strings(
                    manifest, old_slug, new_slug
                )
                changed = changed or paths_changed
            if str(manifest_file) != str(run.get("manifest_path", "")):
                changed = True
            if changed:
                # Rewrite and recompute hash
                new_payload = json.dumps(
                    manifest, indent=2, ensure_ascii=False
                ).encode("utf-8")
                manifest_file.write_bytes(new_payload)
                run["manifest_sha256"] = hashlib.sha256(new_payload).hexdigest()
                run["manifest_path"] = str(manifest_file)

    # 7. Repair sealed decision records and protocol checkpoints whose
    #    embedded run identity names a legacy slug.
    root = Path(project_dir).resolve()
    for phase_slug, phase in phases.items():
        if not isinstance(phase, dict):
            continue
        for run in phase.get("runs", []):
            if not isinstance(run, dict):
                continue
            _migrate_sealed_decision_record(root, run)
            _migrate_sealed_protocol_checkpoint(root, run)


def _migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade legacy state in place while retaining unknown and old fields."""

    try:
        source_schema_version = int(data.get("schema_version", 0))
    except (TypeError, ValueError):
        source_schema_version = 0
    data.setdefault("project", {})
    phases = data.setdefault("phases", {})
    if not isinstance(phases, dict):
        raise StateValidationError("state field 'phases' must be a mapping")
    data.setdefault("dependencies", {})

    seen_ids: set[str] = set()
    for phase_slug, phase_value in list(phases.items()):
        if not isinstance(phase_value, dict):
            phase_value = {"legacy_value": phase_value}
            phases[phase_slug] = phase_value
        phase = phase_value
        legacy_phase_status = str(phase.get("status", "pending"))
        runs = phase.setdefault("runs", [])
        if not isinstance(runs, list):
            phase["legacy_runs"] = runs
            runs = []
            phase["runs"] = runs

        phase_run_ids: set[str] = set()
        for index, run_value in enumerate(list(runs)):
            if not isinstance(run_value, dict):
                run_value = {"legacy_value": run_value}
                runs[index] = run_value
            run = run_value
            candidate_id = run.get("run_id")
            if not isinstance(candidate_id, str) or not candidate_id or candidate_id in seen_ids:
                candidate_id = str(uuid.uuid4())
                run["run_id"] = candidate_id
            seen_ids.add(candidate_id)
            phase_run_ids.add(candidate_id)
            run.setdefault("mode", "")
            try:
                requested = int(run.get("rounds_requested", 1))
            except (TypeError, ValueError):
                requested = 1
            run["rounds_requested"] = max(1, requested)
            run.setdefault("user_feedback", "")
            run.setdefault("created_at", _to_iso(run.get("started")) or _now_iso())
            run.setdefault("started", run.get("created_at"))
            run.setdefault("process_pid", None)
            run.setdefault("process_identity", None)
            run.setdefault("rounds", [])
            if not isinstance(run["rounds"], list):
                run["legacy_rounds"] = run["rounds"]
                run["rounds"] = []
            for round_index, round_value in enumerate(list(run["rounds"])):
                if not isinstance(round_value, dict):
                    round_value = {"legacy_value": round_value}
                    run["rounds"][round_index] = round_value
                round_value.setdefault("tasks", [])
                if not isinstance(round_value["tasks"], list):
                    round_value["legacy_tasks"] = round_value["tasks"]
                    round_value["tasks"] = []
                round_value.setdefault("artifacts", [])
            run.setdefault("final_summary", None)
            run.setdefault("summary_sha256", None)
            run.setdefault("context_inputs", [])
            if not isinstance(run["context_inputs"], list):
                run["legacy_context_inputs"] = run["context_inputs"]
                run["context_inputs"] = []
            run.setdefault("context_frozen", bool(run["context_inputs"]))
            run.setdefault("manifest_path", None)
            run.setdefault("manifest_sha256", None)
            run.setdefault("review_target", None)
            run.setdefault("submission_artifacts", {})
            if not isinstance(run["submission_artifacts"], dict):
                run["legacy_submission_artifacts"] = run["submission_artifacts"]
                run["submission_artifacts"] = {}
            run.setdefault("method_menu_seal", None)
            run.setdefault("method_menu_changes", None)
            run.setdefault("publication_kind", None)
            run.setdefault("published_at", None)
            run.setdefault("publication_outcome", None)
            run.setdefault("publication_readiness", None)
            run.setdefault("migration_warning", None)
            run.setdefault("decision_record", None)
            run.setdefault("protocol_checkpoint", None)
            run.setdefault("replacement_request", None)
            run.setdefault("timeout_minutes", None)
            run.setdefault("prerequisite_snapshot", None)
            run.setdefault("override_metadata", None)
            run.setdefault("submitted_at", None)
            run.setdefault("decision_at", None)
            run.setdefault("decision_by", None)
            run.setdefault("decision_note", None)
            run.setdefault("approval_baseline_acknowledgement", None)
            run.setdefault("approval_context_acknowledgement", None)
            run.setdefault("ended_at", _to_iso(run.get("completed")))
            run.setdefault("error", None)
            run.setdefault("cleanup_outcome", None)
            run.setdefault("cleanup_reason", None)
            run.setdefault("cleanup_started_at", None)
            run.setdefault("cleanup_completed_at", None)
            run.setdefault("cleanup_recovery_note", None)
            run.setdefault("current_results_basis", None)
            if isinstance(run.get("current_results_basis"), dict):
                run.setdefault("current_results_basis_sha256", None)
            else:
                run.setdefault("current_results_basis_sha256", None)

        # Infer legacy outcomes after every run has an ID.  The former phase
        # status described only the newest run, so earlier completed runs are
        # retained as the accepted fallback where possible.
        explicit_approved = phase.get("approved_run")
        if not isinstance(explicit_approved, str) or explicit_approved not in phase_run_ids:
            explicit_approved = None
        completed_candidates: list[dict[str, Any]] = []
        for index, run in enumerate(runs):
            status = run.get("status")
            if status not in RUN_STATUSES:
                is_last = index == len(runs) - 1
                if is_last and legacy_phase_status == "running" and not run.get("completed"):
                    status = "running"
                elif is_last and legacy_phase_status == "failed":
                    status = "failed"
                elif run.get("completed") or run.get("final_summary"):
                    status = "approved" if legacy_phase_status == "completed" and is_last else "superseded"
                else:
                    status = "cancelled"
                run["status"] = status
            if run["status"] == "approved":
                completed_candidates.append(run)
        if explicit_approved is None and completed_candidates:
            explicit_approved = completed_candidates[-1]["run_id"]
        if explicit_approved is not None:
            for run in runs:
                if run["run_id"] == explicit_approved:
                    run["status"] = "approved"
                elif run.get("status") == "approved":
                    run["status"] = "superseded"

        phase["approved_run"] = explicit_approved
        phase.setdefault("latest_run", None)
        phase.setdefault("latest_run_status", None)
        phase.setdefault("stale", False)
        phase.setdefault("stale_at", None)
        phase.setdefault("stale_reason", None)
        phase.setdefault("stale_by_run", None)
        phase.setdefault("publication_readiness", None)

    # Legacy Phase 02 submissions were produced under a different contract:
    # they awaited approval and could encode a selected method. They are kept as
    # immutable history, but are never promoted implicitly during a state read.
    if source_schema_version < 7:
        method_phase = phases.get(METHOD_DEVELOPMENT_PHASE)
        if isinstance(method_phase, dict):
            current_run_id = method_phase.get("approved_run")
            for candidate in method_phase.get("runs", []):
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("status") != "awaiting_review":
                    continue
                timestamp = str(
                    candidate.get("completed")
                    or candidate.get("submitted_at")
                    or candidate.get("ended_at")
                    or _now_iso()
                )
                candidate["status"] = "superseded"
                candidate["superseded_at"] = timestamp
                candidate["superseded_by"] = current_run_id
                candidate["migration_warning"] = {
                    "code": "legacy_phase_two_result_not_published",
                    "message": (
                        "This legacy Phase 02 result awaited approval under the "
                        "earlier method-selection contract. It remains historical "
                        "and was not published automatically."
                    ),
                    "recorded_at": timestamp,
                }

    _restore_legacy_active_process_pid(data)
    data["schema_version"] = SCHEMA_VERSION
    _refresh_derived_state(data)
    return data


def _seal_safe_legacy_approved_evidence(
    project_dir: str | Path, data: dict[str, Any]
) -> bool:
    """Establish hashes for contained legacy baselines without trusting new paths."""

    changed = False
    root = Path(project_dir).resolve()
    for phase in data.get("phases", {}).values():
        if not isinstance(phase, Mapping):
            continue
        approved_id = phase.get("approved_run")
        run = next(
            (
                candidate
                for candidate in phase.get("runs", [])
                if isinstance(candidate, dict)
                and candidate.get("run_id") == approved_id
                and candidate.get("status") == "approved"
            ),
            None,
        )
        if run is None or run.get("manifest_path") or run.get("manifest_sha256"):
            continue
        summary = run.get("final_summary")
        if not summary:
            continue
        pending_artifacts: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        try:
            normalized_summary = _normalize_existing_path(
                project_dir, str(summary), summary=True
            )
            summary_digest, _ = _hash_bounded_file(
                root / normalized_summary,
                maximum=MAX_SUMMARY_BYTES,
                label="legacy final summary",
            )
            for round_ in run.get("rounds", []):
                if not isinstance(round_, dict) or not round_.get("completed"):
                    continue
                outputs = [str(item) for item in round_.get("outputs", [])]
                artifacts = round_.get("artifacts", [])
                if not outputs or artifacts:
                    continue
                sealed: list[dict[str, Any]] = []
                for output in outputs:
                    normalized = _normalize_existing_path(
                        project_dir, output, nonempty_file=True
                    )
                    digest, size = _hash_bounded_file(
                        root / normalized,
                        maximum=MAX_RUN_ARTIFACT_BYTES,
                        label="legacy round artifact",
                    )
                    sealed.append({"path": normalized, "sha256": digest, "size": size})
                pending_artifacts.append((round_, sealed))
        except (OSError, ProjectStateError):
            # Unsafe or incomplete legacy evidence remains visible as history,
            # but cannot satisfy a prerequisite or become trusted context.
            continue
        if not run.get("summary_sha256"):
            run["summary_sha256"] = summary_digest
            changed = True
        for round_, sealed in pending_artifacts:
            round_["artifacts"] = sealed
            changed = True
    return changed


def load(project_dir: str | Path) -> dict[str, Any]:
    """Load and, when needed, atomically migrate a project's state."""

    with _project_lock(project_dir):
        raw = _read_unlocked(project_dir)
        before = copy.deepcopy(raw)
        data = _migrate(raw)
        _migrate_slug_aliases(project_dir, data)
        _seal_safe_legacy_approved_evidence(project_dir, data)
        if data != before:
            _save_unlocked(project_dir, data)
        return data


def init(
    project_dir: str | Path,
    project_id: str,
    slug: str,
    name: str,
    phase_slugs: Sequence[str] | None = None,
    dependencies: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Initialize a project, preserving existing runs and unknown metadata."""

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        existing_project = data.get("project", {})
        data["project"] = {
            **existing_project,
            "id": project_id,
            "slug": slug,
            "name": name,
            "created": existing_project.get("created") or _now_iso(),
        }
        for phase_slug in phase_slugs or ():
            data["phases"].setdefault(phase_slug, _new_phase())
        if dependencies is not None:
            data["dependencies"] = _normalize_dependencies(dependencies)
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return copy.deepcopy(data)


# ---------------------------------------------------------------------------
# Internal state helpers
# ---------------------------------------------------------------------------


def _normalize_dependencies(
    dependencies: Mapping[str, Sequence[str]] | None,
) -> dict[str, list[str]]:
    if not dependencies:
        return {}
    return {
        str(phase): [str(prerequisite) for prerequisite in prerequisites]
        for phase, prerequisites in dependencies.items()
    }


def _run_index(phase: Mapping[str, Any], run_id: str) -> int:
    for index, run in enumerate(phase.get("runs", [])):
        if run.get("run_id") == run_id:
            return index
    raise KeyError(f"phase has no run id {run_id!r}")


def _resolve_run(
    data: Mapping[str, Any], phase_slug: str, run_ref: str | int
) -> tuple[dict[str, Any], dict[str, Any], int]:
    phase = data.get("phases", {}).get(phase_slug)
    if not isinstance(phase, dict):
        raise KeyError(f"unknown phase {phase_slug!r}")
    runs = phase.get("runs", [])
    if isinstance(run_ref, bool):
        raise KeyError(f"invalid run reference {run_ref!r}")
    if isinstance(run_ref, int):
        if run_ref < 0 or run_ref >= len(runs):
            raise KeyError(f"phase {phase_slug!r} has no run index {run_ref}")
        return phase, runs[run_ref], run_ref
    for index, run in enumerate(runs):
        if run.get("run_id") == run_ref:
            return phase, run, index
    raise KeyError(f"phase {phase_slug!r} has no run id {run_ref!r}")


def _get_run(data: Mapping[str, Any], phase_slug: str, run_ref: str | int) -> dict[str, Any]:
    """Compatibility lookup accepting either the immutable ID or old index."""

    return _resolve_run(data, phase_slug, run_ref)[1]


def _active_entries(data: Mapping[str, Any]) -> list[tuple[str, dict[str, Any], int]]:
    active: list[tuple[str, dict[str, Any], int]] = []
    for phase_slug, phase in data.get("phases", {}).items():
        for index, run in enumerate(phase.get("runs", [])):
            if run.get("status") in ACTIVE_RUN_STATUSES:
                active.append((phase_slug, run, index))
    return active


def _refresh_phase(phase: dict[str, Any]) -> None:
    runs = phase.get("runs", [])
    latest = runs[-1] if runs else None
    phase["latest_run"] = latest.get("run_id") if latest else None
    phase["latest_run_status"] = latest.get("status") if latest else None

    approved_id = phase.get("approved_run")
    approved = next((r for r in runs if r.get("run_id") == approved_id), None)
    if approved is None or approved.get("status") != "approved":
        phase["approved_run"] = None
        approved = None

    active = next((r for r in reversed(runs) if r.get("status") in ACTIVE_RUN_STATUSES), None)
    if active is not None:
        phase["status"] = active["status"]
    elif approved is not None:
        phase["status"] = "stale" if phase.get("stale") else "approved"
    elif latest is not None:
        phase["status"] = latest.get("status", "pending")
    else:
        phase["status"] = "pending"


def _refresh_derived_state(data: dict[str, Any]) -> None:
    for phase in data.get("phases", {}).values():
        _refresh_phase(phase)

    active = _active_entries(data)
    if len(active) == 1:
        phase_slug, run, index = active[0]
        marker = {
            "phase": phase_slug,
            "phase_slug": phase_slug,
            "run_id": run["run_id"],
            "run_index": index,
            "pid": run.get("process_pid"),
            "process_identity": run.get("process_identity"),
            "started": run.get("started"),
            "status": run.get("status"),
        }
        data["active_run"] = marker
        data["_active_run"] = copy.deepcopy(marker)
    elif not active:
        data["active_run"] = None
        data.pop("_active_run", None)
    else:
        # Legacy files should never contain this, but retain every run and
        # expose the inconsistency.  New transitions reject it atomically.
        data["active_run"] = {
            "conflict": True,
            "runs": [
                {"phase_slug": phase, "run_id": run["run_id"]}
                for phase, run, _ in active
            ],
        }
        data.pop("_active_run", None)


def _ensure_status(run: Mapping[str, Any], allowed: set[str] | frozenset[str], action: str) -> None:
    status = run.get("status")
    if status not in allowed:
        expected = ", ".join(sorted(allowed))
        raise StateConflict(f"cannot {action} a run in status {status!r}; expected {expected}")


def _path_uses_symlink_below(path: Path, boundary: Path) -> bool:
    """Return whether a path component is a link or Windows reparse point."""

    return _path_uses_link_below(path, boundary)


def _normalize_existing_path(
    project_dir: str | Path,
    raw_path: str | Path,
    *,
    summary: bool = False,
    nonempty_file: bool = False,
) -> str:
    root = Path(project_dir).resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical = Path(os.path.abspath(candidate))
    try:
        lexical.relative_to(root)
    except ValueError:
        pass
    else:
        if _path_uses_symlink_below(lexical, root):
            raise StateValidationError(
                f"artifact path must not use symbolic links: {raw_path}"
            )
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise StateValidationError(f"artifact does not exist: {raw_path}") from exc
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise StateValidationError(
            f"artifact must stay inside the project directory: {raw_path}"
        ) from exc
    if summary or nonempty_file:
        if not resolved.is_file():
            label = "final summary" if summary else "artifact"
            raise StateValidationError(f"{label} must be a file: {raw_path}")
        label = "final summary" if summary else "artifact"
        _hash_bounded_file(
            resolved,
            maximum=MAX_SUMMARY_BYTES if summary else MAX_RUN_ARTIFACT_BYTES,
            label=label,
        )
    return relative.as_posix()


def _same_directory_snapshot(
    before: os.stat_result, after: os.stat_result
) -> bool:
    """Return whether a directory's identity and observable metadata stayed fixed."""

    return bool(
        os.path.samestat(before, after)
        and before.st_mode == after.st_mode
        and before.st_size == after.st_size
        and before.st_nlink == after.st_nlink
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_ctime_ns == after.st_ctime_ns
    )


def discover_round_supporting_files(
    project_dir: str | Path,
    round_directory: str | Path,
    *,
    exclude: Sequence[str | Path] = (),
) -> list[str]:
    """Return bounded regular files below a round directory, excluding reports."""

    root = Path(project_dir).resolve()
    candidate = Path(round_directory)
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical = Path(os.path.abspath(candidate))
    if _path_uses_symlink_below(lexical, root):
        raise StateValidationError(
            "round artifact directory must not use symbolic links or reparse points"
        )
    try:
        round_root = lexical.resolve(strict=True)
        round_root.relative_to(root)
        root_metadata = round_root.lstat()
    except (OSError, ValueError) as exc:
        raise StateValidationError(
            "round artifact directory must be an existing directory inside the project"
        ) from exc
    if (
        _metadata_is_link_or_reparse(root_metadata)
        or not stat.S_ISDIR(root_metadata.st_mode)
    ):
        raise StateValidationError(
            "round artifact directory must be a regular directory"
        )

    excluded = {
        _normalize_existing_path(project_dir, path, nonempty_file=True)
        for path in exclude
    }
    discovered: list[str] = []
    total_size = 0
    pending = [round_root]
    while pending:
        directory = pending.pop()
        try:
            before = directory.lstat()
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name)
        except OSError as exc:
            raise StateValidationError(
                f"round artifact directory could not be inspected: {directory}"
            ) from exc
        if _metadata_is_link_or_reparse(before) or not stat.S_ISDIR(before.st_mode):
            raise StateValidationError(
                f"round artifact directory contains a redirected directory: {directory}"
            )
        for entry in entries:
            path = Path(entry.path)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise StateValidationError(
                    f"round artifact entry could not be inspected: {path}"
                ) from exc
            if _metadata_is_link_or_reparse(metadata):
                raise StateValidationError(
                    "round artifact entry must not be a symbolic link or reparse "
                    f"point: {path}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                pending.append(path)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise StateValidationError(
                    f"round artifact entry must be a regular file: {path}"
                )
            normalized = _normalize_existing_path(project_dir, path)
            if normalized in excluded:
                continue
            _, size = _hash_bounded_file(
                root / normalized,
                maximum=MAX_RUN_ARTIFACT_BYTES,
                label="round supporting artifact",
            )
            discovered.append(normalized)
            total_size += size
            if len(discovered) > MAX_ROUND_SUPPORTING_FILES:
                raise StateValidationError(
                    "round contains too many supporting artifacts; "
                    f"the limit is {MAX_ROUND_SUPPORTING_FILES}"
                )
            if total_size > MAX_ROUND_SUPPORTING_BYTES:
                raise StateValidationError(
                    "round supporting artifacts exceed the "
                    f"{MAX_ROUND_SUPPORTING_BYTES:,}-byte aggregate safety limit"
                )
        try:
            after = directory.lstat()
        except OSError as exc:
            raise StateValidationError(
                f"round artifact directory changed while it was inspected: {directory}"
            ) from exc
        if (
            _metadata_is_link_or_reparse(after)
            or not _same_directory_snapshot(before, after)
        ):
            raise StateValidationError(
                f"round artifact directory changed while it was inspected: {directory}"
            )
    return sorted(discovered)

def _completed_round_count(run: Mapping[str, Any]) -> int:
    return sum(1 for round_ in run.get("rounds", []) if round_.get("completed"))


def _validate_recorded_artifacts(
    project_dir: str | Path, run: Mapping[str, Any]
) -> None:
    """Reject completed-round evidence that changed after it was recorded."""

    root = Path(project_dir).resolve()
    for round_ in run.get("rounds", []):
        if not round_.get("completed"):
            continue
        outputs = [str(item) for item in round_.get("outputs", [])]
        artifacts = [
            item for item in round_.get("artifacts", []) if isinstance(item, Mapping)
        ]
        artifact_paths = [str(item.get("path", "")) for item in artifacts]
        if sorted(outputs) != sorted(artifact_paths) or len(artifacts) != len(outputs):
            raise StateValidationError(
                f"round {round_.get('n')} artifact records do not match its outputs"
            )
        for artifact in artifacts:
            normalized = _normalize_existing_path(
                project_dir, str(artifact.get("path", "")), nonempty_file=True
            )
            digest, size = _hash_bounded_file(
                root / normalized,
                maximum=MAX_RUN_ARTIFACT_BYTES,
                label="round artifact",
            )
            if digest != str(artifact.get("sha256", "")).lower():
                raise StateValidationError(
                    f"round {round_.get('n')} artifact changed after completion: {normalized}"
                )
            try:
                recorded_size = int(artifact.get("size", -1))
            except (TypeError, ValueError) as exc:
                raise StateValidationError(
                    f"round {round_.get('n')} artifact size record is invalid: {normalized}"
                ) from exc
            if recorded_size != size:
                raise StateValidationError(
                    f"round {round_.get('n')} artifact size changed after completion: {normalized}"
                )

        supporting = round_.get("supporting_artifacts", [])
        if not isinstance(supporting, list) or any(
            not isinstance(item, Mapping) for item in supporting
        ):
            raise StateValidationError(
                f"round {round_.get('n')} supporting artifact inventory is invalid"
            )
        if len(supporting) > MAX_ROUND_SUPPORTING_FILES:
            raise StateValidationError(
                f"round {round_.get('n')} contains too many supporting artifacts"
            )
        supporting_paths = [str(item.get("path", "")) for item in supporting]
        if (
            len(set(supporting_paths)) != len(supporting_paths)
            or set(supporting_paths) & set(outputs)
        ):
            raise StateValidationError(
                f"round {round_.get('n')} supporting artifact paths are not distinct"
            )
        role_directories = {
            (root / output).parent.resolve(strict=False) for output in outputs
        }
        if supporting and len(role_directories) != 1:
            raise StateValidationError(
                f"round {round_.get('n')} supporting artifacts have no unique round directory"
            )
        round_directory = next(iter(role_directories), None)
        supporting_size = 0
        for artifact in supporting:
            if set(artifact) != {"path", "sha256", "size"}:
                raise StateValidationError(
                    f"round {round_.get('n')} supporting artifact record is invalid"
                )
            normalized = _normalize_existing_path(
                project_dir, str(artifact.get("path", "")), nonempty_file=True
            )
            try:
                (root / normalized).relative_to(round_directory)
            except (TypeError, ValueError) as exc:
                raise StateValidationError(
                    f"round {round_.get('n')} supporting artifact escaped its round directory"
                ) from exc
            digest, size = _hash_bounded_file(
                root / normalized,
                maximum=MAX_RUN_ARTIFACT_BYTES,
                label="round supporting artifact",
            )
            if digest != str(artifact.get("sha256", "")).lower():
                raise StateValidationError(
                    f"round {round_.get('n')} supporting artifact changed after completion: {normalized}"
                )
            try:
                recorded_size = int(artifact.get("size", -1))
            except (TypeError, ValueError) as exc:
                raise StateValidationError(
                    f"round {round_.get('n')} supporting artifact size record is invalid: {normalized}"
                ) from exc
            if recorded_size != size:
                raise StateValidationError(
                    f"round {round_.get('n')} supporting artifact size changed after completion: {normalized}"
                )
            supporting_size += size
        if supporting_size > MAX_ROUND_SUPPORTING_BYTES:
            raise StateValidationError(
                f"round {round_.get('n')} supporting artifacts exceed the aggregate safety limit"
            )

def _validate_review_bundle_record(
    project_dir: str | Path,
    record: Mapping[str, Any],
    *,
    phase_slug: str,
    run_id: str,
    round_n: int,
    role: str,
    brief_path: Path,
    brief_sha256: str,
) -> dict[str, str]:
    control_root = state_dir(project_dir).resolve()
    review_root = (control_root / "review-workspaces").resolve()
    raw_root = Path(str(record.get("root", "")))
    raw_manifest = Path(str(record.get("manifest_path", "")))
    if _path_uses_symlink_below(raw_root, review_root):
        raise StateValidationError("reviewer workspace path must not use symbolic links")
    if _path_uses_symlink_below(raw_manifest, raw_root):
        raise StateValidationError(
            "reviewer workspace manifest must not use symbolic links"
        )
    try:
        root = raw_root.resolve(strict=True)
        root.relative_to(review_root)
        manifest_path = raw_manifest.resolve(strict=True)
        manifest_path.relative_to(root)
    except (OSError, ValueError) as exc:
        raise StateValidationError(
            "reviewer workspace must stay in project control storage"
        ) from exc
    if manifest_path != root / "bundle.json":
        raise StateValidationError("reviewer workspace manifest path is invalid")
    payload = _read_bounded_file(
        manifest_path,
        maximum=MAX_CONTROL_FILE_BYTES,
        label="reviewer workspace manifest",
    )
    expected_manifest_hash = str(record.get("manifest_sha256", "")).lower()
    if hashlib.sha256(payload).hexdigest() != expected_manifest_hash:
        raise StateValidationError("reviewer workspace manifest changed after dispatch")
    try:
        bundle = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StateValidationError("reviewer workspace manifest is invalid") from exc
    if (
        not isinstance(bundle, Mapping)
        or bundle.get("schema_version") != REVIEW_BUNDLE_SCHEMA_VERSION
        or bundle.get("phase_slug") != phase_slug
        or bundle.get("run_id") != run_id
        or bundle.get("round") != round_n
        or bundle.get("role") != role
    ):
        raise StateValidationError("reviewer workspace identity is invalid")
    inputs = bundle.get("inputs")
    if not isinstance(inputs, list):
        raise StateValidationError("reviewer workspace inputs must be a list")
    leaves = [bundle.get("task"), *inputs]
    total = 0
    for leaf in leaves:
        if not isinstance(leaf, Mapping):
            raise StateValidationError("reviewer workspace file record is invalid")
        raw_candidate = root / str(leaf.get("path", ""))
        if _path_uses_symlink_below(raw_candidate, root):
            raise StateValidationError(
                "reviewer workspace input must not use symbolic links"
            )
        try:
            candidate = raw_candidate.resolve(strict=True)
            candidate.relative_to(root)
            size = int(leaf.get("size", -1))
        except (OSError, ValueError, TypeError) as exc:
            raise StateValidationError("reviewer workspace input is unavailable") from exc
        if not candidate.is_file():
            raise StateValidationError("reviewer workspace input must be a regular file")
        if size < 0 or size > MAX_REVIEW_BUNDLE_BYTES - total:
            raise StateValidationError(
                "reviewer workspace exceeds the aggregate safety limit"
            )
        digest, actual_size = _hash_bounded_file(
            candidate,
            maximum=MAX_REVIEW_BUNDLE_BYTES - total,
            label="reviewer workspace input",
            allow_empty=True,
        )
        total += actual_size
        if (
            size != actual_size
            or digest != str(leaf.get("sha256", "")).lower()
        ):
            raise StateValidationError("reviewer workspace input changed after dispatch")
    if total > MAX_REVIEW_BUNDLE_BYTES:
        raise StateValidationError("reviewer workspace exceeds the aggregate safety limit")
    task_record = bundle.get("task")
    if (
        not isinstance(task_record, Mapping)
        or (root / str(task_record.get("path", ""))).resolve() != brief_path
        or str(task_record.get("sha256", "")).lower() != brief_sha256.lower()
    ):
        raise StateValidationError("reviewer task brief does not match its workspace")
    output = bundle.get("output")
    if not isinstance(output, Mapping):
        raise StateValidationError("reviewer workspace output record is invalid")
    try:
        raw_output = root / str(output.get("path", ""))
        if _path_uses_symlink_below(raw_output, root):
            raise StateValidationError(
                "reviewer workspace output must not use symbolic links"
            )
        output_path = raw_output.resolve()
        output_path.relative_to(root / "output")
        max_bytes = int(output.get("max_bytes", 0))
    except (ValueError, TypeError) as exc:
        raise StateValidationError("reviewer workspace output path is invalid") from exc
    if max_bytes < 1 or max_bytes > MAX_REVIEW_OUTPUT_BYTES:
        raise StateValidationError("reviewer workspace output size policy is invalid")
    return {
        "root": str(root),
        "manifest_path": str(manifest_path),
        "manifest_sha256": expected_manifest_hash,
    }


def _validate_recorded_task_briefs(
    project_dir: str | Path, phase_slug: str, run: Mapping[str, Any]
) -> None:
    control_root = state_dir(project_dir).resolve()
    for round_ in run.get("rounds", []):
        for task in round_.get("tasks", []):
            if not isinstance(task, Mapping):
                raise StateValidationError("task record must be a mapping")
            raw_path = task.get("brief_path")
            expected_digest = str(task.get("brief_sha256", "")).lower()
            if not raw_path or not expected_digest:
                raise StateValidationError(
                    f"task {task.get('task_id', '?')} has no sealed brief"
                )
            raw_brief = Path(str(raw_path))
            if _path_uses_symlink_below(raw_brief, control_root):
                raise StateValidationError(
                    f"task {task.get('task_id', '?')} brief path uses a symbolic link"
                )
            try:
                brief = raw_brief.resolve(strict=True)
                brief.relative_to(control_root)
            except (OSError, ValueError) as exc:
                raise StateValidationError(
                    f"task {task.get('task_id', '?')} brief is missing or outside control storage"
                ) from exc
            if not brief.is_file():
                raise StateValidationError(
                    f"task {task.get('task_id', '?')} brief is not a file"
                )
            digest, _ = _hash_bounded_file(
                brief,
                maximum=MAX_CONTROL_FILE_BYTES,
                label=f"task {task.get('task_id', '?')} brief",
            )
            if digest != expected_digest:
                raise StateValidationError(
                    f"task {task.get('task_id', '?')} brief changed after dispatch"
                )
            review_bundle = task.get("review_bundle")
            if review_bundle is not None:
                if not isinstance(review_bundle, Mapping):
                    raise StateValidationError("reviewer workspace record must be a mapping")
                _validate_review_bundle_record(
                    project_dir,
                    review_bundle,
                    phase_slug=phase_slug,
                    run_id=str(run.get("run_id", "")),
                    round_n=int(round_.get("n", 0)),
                    role=str(task.get("role", "")),
                    brief_path=brief,
                    brief_sha256=expected_digest,
                )


def _manifest_schema_version(manifest: Mapping[str, Any] | None) -> int:
    """Safely extract ``schema_version`` from a manifest.

    Returns 1 (the legacy default) for ``None`` manifests (legacy direct runs)
    and for manifests whose ``schema_version`` is missing or non-numeric.
    This guards against ``ValueError`` from user-editable state files that
    could set ``schema_version: "abc"``.
    """

    if manifest is None:
        return 1
    try:
        return int(manifest.get("schema_version", 1))
    except (TypeError, ValueError):
        return 1


def _validate_recorded_manifest(
    project_dir: str | Path,
    phase_slug: str,
    run: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return a verified sealed manifest, or ``None`` for a legacy direct run."""

    raw_path = run.get("manifest_path")
    expected_digest = str(run.get("manifest_sha256") or "").lower()
    if not raw_path and not expected_digest:
        return None
    if not raw_path or not expected_digest:
        raise StateValidationError("run manifest record is incomplete")
    expected_root = (state_dir(project_dir) / "runs" / phase_slug).resolve()
    raw_manifest_path = Path(str(raw_path))
    if _path_uses_symlink_below(raw_manifest_path, expected_root):
        raise StateValidationError("run manifest path must not use symbolic links")
    try:
        manifest_path = raw_manifest_path.resolve(strict=True)
        manifest_path.relative_to(expected_root)
    except (OSError, ValueError) as exc:
        raise StateValidationError(
            "run manifest is missing or outside its phase control directory"
        ) from exc
    if not manifest_path.is_file():
        raise StateValidationError("run manifest is not a file")
    payload = _read_bounded_file(
        manifest_path,
        maximum=MAX_CONTROL_FILE_BYTES,
        label="run manifest",
    )
    if hashlib.sha256(payload).hexdigest() != expected_digest:
        raise StateValidationError("run manifest changed after launch preparation")
    try:
        manifest = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StateValidationError("run manifest is invalid") from exc
    if not isinstance(manifest, dict):
        raise StateValidationError("run manifest must be a mapping")
    if (
        manifest.get("run_id") != run.get("run_id")
        or manifest.get("phase_slug") != phase_slug
    ):
        raise StateValidationError("run manifest identity does not match the state record")
    return manifest


def _manifest_protocol_checkpoint_spec(
    project_dir: str | Path,
    phase_slug: str,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the fixed Phase 04 checkpoint declaration from a modern manifest."""

    if manifest is None:
        return None
    try:
        schema_version = int(manifest.get("schema_version", 1))
    except (TypeError, ValueError) as exc:
        raise StateValidationError("run manifest schema version is invalid") from exc
    declared = manifest.get("protocol_checkpoint")
    phase = manifest.get("phase")
    phase_declares = isinstance(phase, Mapping) and bool(
        phase.get("protocol_checkpoint")
    )
    repurposed = isinstance(phase, Mapping) and str(
        phase.get("pattern", "")
    ) in {"parallel", "debate"}
    legacy_checkpoint_phase = (
        _resolve_slug(phase_slug) == DRAFT_ASSEMBLY_PHASE and not repurposed
    )
    if not phase_declares and not legacy_checkpoint_phase:
        if declared is not None:
            raise StateValidationError(
                "a protocol checkpoint requires the phase configuration to opt in"
            )
        return None
    if declared is None:
        if schema_version >= 5:
            raise StateValidationError(
                "modern manifest has no protocol checkpoint declaration"
            )
        return None
    required_fields = {
        "schema_version",
        "path",
        "max_bytes",
    }
    if schema_version >= 6:
        required_fields.add("protocol_root")
    if not isinstance(declared, Mapping) or set(declared) != required_fields:
        raise StateValidationError(
            "protocol checkpoint declaration does not match the manifest schema"
        )
    if declared.get("schema_version") != PROTOCOL_CHECKPOINT_SCHEMA_VERSION:
        raise StateValidationError("protocol checkpoint declaration schema is invalid")
    try:
        maximum = int(declared.get("max_bytes", 0))
    except (TypeError, ValueError) as exc:
        raise StateValidationError("protocol checkpoint size policy is invalid") from exc
    if maximum != MAX_PROTOCOL_CHECKPOINT_BYTES:
        raise StateValidationError("protocol checkpoint size policy is invalid")

    root = Path(project_dir).resolve()
    output_root = Path(str(manifest.get("output_root", "")))
    if not output_root.is_absolute():
        output_root = root / output_root
    expected = Path(
        os.path.abspath(
            output_root
            / (
                "protocol/protocol-checkpoint.json"
                if schema_version >= 7
                else "protocol-checkpoint.json"
            )
        )
    )
    candidate = Path(os.path.abspath(Path(str(declared.get("path", "")))))
    try:
        expected.relative_to(root)
        candidate.relative_to(root)
    except ValueError as exc:
        raise StateValidationError("protocol checkpoint path escaped the project") from exc
    if candidate != expected:
        raise StateValidationError(
            "protocol checkpoint path does not match the frozen Phase 04 plan"
        )
    result = {
        "manifest_schema_version": schema_version,
        "schema_version": PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
        "path": candidate,
        "max_bytes": maximum,
    }
    if schema_version >= 6:
        protocol_root = Path(
            os.path.abspath(Path(str(declared.get("protocol_root", ""))))
        )
        expected_protocol_root = Path(os.path.abspath(output_root / "protocol"))
        try:
            protocol_root.relative_to(root)
        except ValueError as exc:
            raise StateValidationError(
                "protocol directory escaped the project"
            ) from exc
        if protocol_root != expected_protocol_root:
            raise StateValidationError(
                "protocol directory does not match the frozen Phase 04 plan"
            )
        result["protocol_root"] = protocol_root
    return result


def _read_protocol_checkpoint_file(
    project_dir: str | Path,
    phase_slug: str,
    run: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> tuple[bytes, dict[str, Any]]:
    root = Path(project_dir).resolve()
    checkpoint = Path(str(spec["path"]))
    if _path_uses_symlink_below(checkpoint, root):
        raise StateValidationError("protocol checkpoint path must not use symbolic links")
    try:
        resolved = checkpoint.resolve(strict=True)
        relative = resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise StateValidationError(
            "protocol checkpoint must be an existing file inside the project"
        ) from exc
    payload = _read_bounded_file(
        resolved,
        maximum=int(spec["max_bytes"]),
        label="protocol checkpoint",
    )
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StateValidationError(
            "protocol checkpoint must be valid UTF-8 JSON"
        ) from exc
    required_keys = {
        "schema_version",
        "phase_slug",
        "run_id",
        "main_results_generated",
        "protocol_files",
    }
    if not isinstance(parsed, Mapping) or set(parsed) != required_keys:
        raise StateValidationError(
            "protocol checkpoint must contain exactly schema_version, phase_slug, "
            "run_id, main_results_generated, and protocol_files"
        )
    if parsed.get("schema_version") != PROTOCOL_CHECKPOINT_SCHEMA_VERSION:
        raise StateValidationError("protocol checkpoint schema version is invalid")
    if parsed.get("phase_slug") != phase_slug or parsed.get("run_id") != run.get("run_id"):
        raise StateValidationError("protocol checkpoint run identity is invalid")
    if parsed.get("main_results_generated") is not False:
        raise StateValidationError(
            "protocol checkpoint must be sealed before main results are generated"
        )
    files = parsed.get("protocol_files")
    if (
        not isinstance(files, list)
        or not files
        or len(files) > MAX_PROTOCOL_CHECKPOINT_FILES
    ):
        raise StateValidationError(
            f"protocol checkpoint must list 1 to {MAX_PROTOCOL_CHECKPOINT_FILES} files"
        )
    normalized_files: list[dict[str, Any]] = []
    seen: set[str] = set()
    aggregate = 0
    protocol_boundary: Path | None = None
    if spec.get("protocol_root") is not None:
        raw_protocol_root = Path(str(spec["protocol_root"]))
        if _path_uses_symlink_below(raw_protocol_root, root):
            raise StateValidationError(
                "run-scoped protocol directory must not use symbolic links"
            )
        try:
            protocol_boundary = raw_protocol_root.resolve(strict=True)
            protocol_boundary.relative_to(root)
        except (OSError, ValueError) as exc:
            raise StateValidationError(
                "run-scoped protocol directory is unavailable"
            ) from exc
        if not protocol_boundary.is_dir():
            raise StateValidationError(
                "run-scoped protocol directory must be a directory"
            )
    for index, item in enumerate(files):
        if not isinstance(item, Mapping) or set(item) != {
            "path",
            "sha256",
            "size",
            "purpose",
        }:
            raise StateValidationError(
                f"protocol checkpoint file {index + 1} has invalid fields"
            )
        normalized = _normalize_existing_path(
            project_dir, str(item.get("path", "")), nonempty_file=True
        )
        if normalized == relative.as_posix():
            raise StateValidationError("protocol checkpoint cannot list itself")
        if protocol_boundary is not None:
            try:
                (root / normalized).resolve(strict=True).relative_to(
                    protocol_boundary
                )
            except (OSError, ValueError) as exc:
                raise StateValidationError(
                    "every checkpointed protocol file must be inside the "
                    "run-scoped protocol directory"
                ) from exc
        if normalized in seen:
            raise StateValidationError("protocol checkpoint contains duplicate file paths")
        seen.add(normalized)
        digest, size = _hash_bounded_file(
            root / normalized,
            maximum=MAX_RUN_ARTIFACT_BYTES,
            label="protocol file",
        )
        expected_digest = str(item.get("sha256", "")).strip().lower()
        try:
            expected_size = int(item.get("size", -1))
        except (TypeError, ValueError) as exc:
            raise StateValidationError("protocol checkpoint file size is invalid") from exc
        if digest != expected_digest or size != expected_size:
            raise StateValidationError(
                f"protocol file does not match its checkpoint record: {normalized}"
            )
        purpose = str(item.get("purpose", "")).strip()
        if not purpose or len(purpose) > 1_000:
            raise StateValidationError(
                "protocol checkpoint file purpose must contain 1 to 1,000 characters"
            )
        aggregate += size
        if aggregate > MAX_PROTOCOL_CHECKPOINT_AGGREGATE_BYTES:
            raise StateValidationError(
                "protocol checkpoint files exceed the aggregate safety limit"
            )
        normalized_files.append({
            "path": normalized,
            "sha256": digest,
            "size": size,
            "purpose": purpose,
        })
    if _read_bounded_file(
        resolved,
        maximum=int(spec["max_bytes"]),
        label="protocol checkpoint",
    ) != payload:
        raise StateValidationError("protocol checkpoint changed while it was being sealed")
    return payload, {
        "schema_version": PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
        "phase_slug": phase_slug,
        "run_id": str(run.get("run_id", "")),
        "main_results_generated": False,
        "protocol_files": normalized_files,
    }


def _validate_isolated_protocol_workspace(
    project_dir: str | Path,
    spec: Mapping[str, Any],
    checkpoint_data: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify the exact files left by a completed schema-7 protocol task."""

    if int(spec.get("manifest_schema_version", 0)) < 7:
        raise StateValidationError(
            "isolated protocol workspace validation requires manifest schema 7"
        )
    root = Path(project_dir).resolve()
    protocol_root = Path(str(spec.get("protocol_root", ""))).resolve(strict=True)
    checkpoint = Path(str(spec.get("path", ""))).resolve(strict=True)
    report = protocol_root / "protocol-stage.md"
    if _path_uses_symlink_below(report, protocol_root):
        raise StateValidationError(
            "protocol-stage report must not use symbolic links"
        )
    report_payload = _read_bounded_file(
        report,
        maximum=MAX_RUN_ARTIFACT_BYTES,
        label="protocol-stage report",
    )
    try:
        report_text = report_payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StateValidationError(
            "protocol-stage report must be valid UTF-8"
        ) from exc
    first_line = next(
        (line.strip() for line in report_text.splitlines() if line.strip()), ""
    )
    prefix = "Scientific completion outcome: "
    scientific_outcome = first_line[len(prefix):] if first_line.startswith(prefix) else ""
    if scientific_outcome not in SCIENTIFIC_OUTCOMES:
        raise StateValidationError(
            "protocol-stage report must begin with a Complete, Partial, or Failed "
            "scientific completion outcome"
        )

    listed_files = checkpoint_data.get("protocol_files", [])
    allowed = {checkpoint, report.resolve(strict=True)}
    for item in listed_files if isinstance(listed_files, list) else []:
        if not isinstance(item, Mapping):
            raise StateValidationError("protocol checkpoint file record is invalid")
        listed = (root / str(item.get("path", ""))).resolve(strict=True)
        if listed == report.resolve(strict=True):
            raise StateValidationError(
                "protocol-stage report must remain distinct from checkpointed protocol files"
            )
        allowed.add(listed)

    for current, directories, files in os.walk(protocol_root, followlinks=False):
        current_path = Path(current)
        for name in [*directories, *files]:
            candidate = current_path / name
            try:
                metadata = candidate.lstat()
            except OSError as exc:
                raise StateValidationError(
                    f"isolated protocol workspace changed during verification: {candidate}"
                ) from exc
            if _metadata_is_link_or_reparse(metadata):
                raise StateValidationError(
                    f"isolated protocol workspace must not contain links: {candidate}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise StateValidationError(
                    f"isolated protocol workspace contains a non-file entry: {candidate}"
                )
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(protocol_root)
            except (OSError, ValueError) as exc:
                raise StateValidationError(
                    f"isolated protocol workspace file escaped its boundary: {candidate}"
                ) from exc
            if resolved not in allowed:
                raise StateValidationError(
                    "isolated protocol workspace contains an unlisted file; result "
                    f"generation remains blocked: {resolved.relative_to(protocol_root)}"
                )

    report_digest = hashlib.sha256(report_payload).hexdigest()
    return {
        "path": report.relative_to(root).as_posix(),
        "sha256": report_digest,
        "size": len(report_payload),
        "scientific_outcome": scientific_outcome,
    }


def _validate_recorded_protocol_checkpoint(
    project_dir: str | Path,
    phase_slug: str,
    run: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
    *,
    required: bool,
) -> None:
    spec = _manifest_protocol_checkpoint_spec(project_dir, phase_slug, manifest)
    record = run.get("protocol_checkpoint")
    if spec is None:
        if record:
            raise StateValidationError(
                "run records a protocol checkpoint that is not in its manifest"
            )
        return
    if not record:
        if required:
            raise StateValidationError(
                "Phase 04 protocol checkpoint was not sealed before the main study"
            )
        return
    if not isinstance(record, Mapping):
        raise StateValidationError("protocol checkpoint state record is invalid")
    payload, normalized = _read_protocol_checkpoint_file(
        project_dir, phase_slug, run, spec
    )
    protocol_report = None
    if int(spec.get("manifest_schema_version", 0)) >= 7:
        protocol_report = _validate_isolated_protocol_workspace(
            project_dir, spec, normalized
        )
    digest = hashlib.sha256(payload).hexdigest()
    if str(record.get("path", "")) != Path(str(spec["path"])).relative_to(
        Path(project_dir).resolve()
    ).as_posix():
        raise StateValidationError("protocol checkpoint state path is invalid")
    if digest != str(record.get("sha256", "")).lower():
        raise StateValidationError("protocol checkpoint changed after it was sealed")
    try:
        recorded_size = int(record.get("size", -1))
    except (TypeError, ValueError) as exc:
        raise StateValidationError("protocol checkpoint state size is invalid") from exc
    if recorded_size != len(payload) or record.get("data") != normalized:
        raise StateValidationError("protocol checkpoint state record changed")
    if int(spec.get("manifest_schema_version", 0)) >= 7:
        if record.get("protocol_report") != protocol_report:
            raise StateValidationError(
                "protocol-stage report changed after the checkpoint was sealed"
            )
    elif record.get("protocol_report") is not None:
        raise StateValidationError(
            "legacy protocol checkpoint has unexpected protocol-stage metadata"
        )


def seal_protocol_checkpoint(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    checkpoint_path: str | Path,
    *,
    isolated_task_completed: bool = False,
) -> dict[str, Any]:
    """Seal the Phase 04 computational protocol before main result generation."""

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"running"}, "seal a protocol checkpoint for")
        rounds = run.get("rounds", [])
        if (
            len(rounds) != 1
            or rounds[0].get("n") != 1
            or not rounds[0].get("started")
            or rounds[0].get("completed")
        ):
            raise StateConflict(
                "the protocol checkpoint must be sealed during the open first round"
            )
        manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
        spec = _manifest_protocol_checkpoint_spec(project_dir, phase_slug, manifest)
        if spec is None:
            raise StateValidationError(
                "this run has no protocol checkpoint declaration"
            )
        existing = run.get("protocol_checkpoint")
        if spec.get("protocol_root") is not None:
            tasks = list(rounds[0].get("tasks", []))
            task_sequence = [
                (task.get("role"), task.get("task_kind"))
                if isinstance(task, Mapping)
                else (None, None)
                for task in tasks
            ]
            protocol_only = [("data_scientist", "protocol")]
            protocol_then_result = [
                *protocol_only,
                ("data_scientist", "result"),
            ]
            allowed_sequences = (
                (protocol_only, protocol_then_result)
                if existing
                else (protocol_only,)
            )
            if task_sequence not in allowed_sequences:
                raise StateConflict(
                    "the checkpoint must be sealed by the single run-scoped "
                    "protocol task before any result task is dispatched"
                )
            if int(spec.get("manifest_schema_version", 0)) >= 7:
                if not isolated_task_completed:
                    raise StateConflict(
                        "schema-7 protocol checkpoints are sealed only after the "
                        "isolated protocol task has completed"
                    )
                protocol_task = tasks[0] if tasks else None
                expected_workspace = Path(str(spec["protocol_root"])).resolve()
                if (
                    not isinstance(protocol_task, Mapping)
                    or Path(str(protocol_task.get("workspace_path", ""))).resolve()
                    != expected_workspace
                ):
                    raise StateValidationError(
                        "protocol task was not recorded in its isolated workspace"
                    )
        supplied = Path(os.path.abspath(Path(checkpoint_path)))
        if supplied != Path(str(spec["path"])):
            raise StateValidationError(
                "protocol checkpoint path does not match the frozen run plan"
            )
        payload, normalized = _read_protocol_checkpoint_file(
            project_dir, phase_slug, run, spec
        )
        protocol_report = (
            _validate_isolated_protocol_workspace(project_dir, spec, normalized)
            if int(spec.get("manifest_schema_version", 0)) >= 7
            else None
        )
        record = {
            "path": supplied.relative_to(Path(project_dir).resolve()).as_posix(),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "schema_version": PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "data": normalized,
            "protocol_report": protocol_report,
            "sealed_at": _now_iso(),
        }
        if existing:
            if (
                isinstance(existing, Mapping)
                and existing.get("path") == record["path"]
                and existing.get("sha256") == record["sha256"]
                and existing.get("size") == record["size"]
                and existing.get("data") == record["data"]
                and existing.get("protocol_report") == record["protocol_report"]
            ):
                return copy.deepcopy(dict(existing))
            raise StateConflict("the protocol checkpoint is already sealed")
        run["protocol_checkpoint"] = record
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return copy.deepcopy(record)


def require_protocol_checkpoint(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
) -> dict[str, Any]:
    """Verify and return the sealed checkpoint before result work is dispatched."""

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
        _validate_recorded_protocol_checkpoint(
            project_dir, phase_slug, run, manifest, required=True
        )
        record = run.get("protocol_checkpoint")
        if not isinstance(record, Mapping):
            raise StateValidationError("protocol checkpoint state record is invalid")
        return copy.deepcopy(dict(record))


def _phase_six_submission_specs(
    project_dir: str | Path,
    phase_slug: str,
    run: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
) -> dict[str, tuple[Path, bool]]:
    """Return exact required Phase 05 products and whether each may be empty."""

    if phase_slug != PAPER_WRITING_PHASE or manifest is None:
        return {}
    paper_review = manifest.get("paper_review")
    if not isinstance(paper_review, Mapping):
        return {}
    kind = paper_review.get("kind")
    root = Path(project_dir).resolve()
    try:
        output_root = Path(str(manifest.get("output_root", ""))).resolve()
        output_root.relative_to(root)
    except ValueError as exc:
        raise StateValidationError("Phase 05 output directory escaped the project") from exc
    # R5: assembly runs require manuscript.md; full runs require the
    # post-review pair; review-only runs require nothing.
    if kind == "assembly":
        expected = {
            "assembly_manuscript": (output_root / "manuscript.md", False),
        }
    elif kind == "full":
        expected = {
            name: (output_root / filename, allow_empty)
            for name, (filename, allow_empty) in PHASE_SIX_SUBMISSION_ARTIFACTS.items()
        }
    else:
        return {}
    if _manifest_schema_version(manifest) >= 3:
        declared = manifest.get("submission_outputs")
        if not isinstance(declared, Mapping) or set(declared) != set(expected):
            raise StateValidationError(
                "Phase 05 manifest does not declare its exact submission artifacts"
            )
        for name, (expected_path, allow_empty) in expected.items():
            record = declared.get(name)
            if not isinstance(record, Mapping):
                raise StateValidationError(
                    f"Phase 05 submission output {name} must be a mapping"
                )
            if Path(str(record.get("path", ""))).resolve() != expected_path.resolve():
                raise StateValidationError(
                    f"Phase 05 submission output {name} does not match the run plan"
                )
            if record.get("allow_empty") is not allow_empty:
                raise StateValidationError(
                    f"Phase 05 submission output {name} has an invalid empty-file policy"
                )
    return expected


def _seal_submission_artifacts(
    project_dir: str | Path,
    specs: Mapping[str, tuple[Path, bool]],
) -> dict[str, dict[str, Any]]:
    root = Path(project_dir).resolve()
    records: dict[str, dict[str, Any]] = {}
    for name, (path, allow_empty) in specs.items():
        normalized = _normalize_existing_path(
            project_dir, path, nonempty_file=not allow_empty
        )
        candidate = root / normalized
        if not candidate.is_file():
            raise StateValidationError(f"submission artifact must be a file: {normalized}")
        digest, size = _hash_bounded_file(
            candidate,
            maximum=MAX_RUN_ARTIFACT_BYTES,
            label="submission artifact",
            allow_empty=allow_empty,
        )
        records[name] = {
            "path": normalized,
            "sha256": digest,
            "size": size,
        }
    return records


def _validate_recorded_submission_artifacts(
    project_dir: str | Path,
    phase_slug: str,
    run: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
) -> None:
    specs = _phase_six_submission_specs(project_dir, phase_slug, run, manifest)
    records = run.get("submission_artifacts") or {}
    if not isinstance(records, Mapping):
        raise StateValidationError("submission artifact record must be a mapping")
    if specs and set(records) != set(specs):
        missing = sorted(set(specs) - set(records))
        detail = ", ".join(missing) if missing else "unexpected artifact records"
        raise StateValidationError(
            f"Phase 05 submission artifacts are incomplete: {detail}"
        )
    root = Path(project_dir).resolve()
    for name, record in records.items():
        if not isinstance(record, Mapping):
            raise StateValidationError(f"submission artifact {name!r} must be a mapping")
        normalized = _normalize_existing_path(
            project_dir, str(record.get("path", "")), nonempty_file=False
        )
        candidate = root / normalized
        if not candidate.is_file():
            raise StateValidationError(f"submission artifact is not a file: {normalized}")
        if name in specs:
            expected_path = specs[name][0].resolve()
            if candidate.resolve() != expected_path:
                raise StateValidationError(
                    f"submission artifact path does not match the Phase 05 plan: {name}"
                )
        digest, size = _hash_bounded_file(
            candidate,
            maximum=MAX_RUN_ARTIFACT_BYTES,
            label="submission artifact",
            allow_empty=bool(name in specs and specs[name][1]),
        )
        if digest != str(record.get("sha256", "")).lower():
            raise StateValidationError(
                f"submission artifact changed after submission: {normalized}"
            )
        try:
            recorded_size = int(record.get("size", -1))
        except (TypeError, ValueError) as exc:
            raise StateValidationError(
                f"submission artifact size record is invalid: {normalized}"
            ) from exc
        if recorded_size != size:
            raise StateValidationError(
                f"submission artifact size changed after submission: {normalized}"
            )


def _decision_text(value: Any, label: str, *, maximum: int = MAX_DECISION_TEXT_LENGTH) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateValidationError(f"decision record {label} must be a nonempty string")
    text = value.strip()
    if len(text) > maximum:
        raise StateValidationError(
            f"decision record {label} exceeds {maximum:,} characters"
        )
    return text


def validate_decision_record(value: Any) -> dict[str, Any]:
    """Validate and normalize one decision-facing scientific record."""

    if not isinstance(value, Mapping):
        raise StateValidationError("decision record must be a JSON object")
    base_required = {
        "schema_version",
        "scientific_outcome",
        "decision_requested",
        "recommended_user_action",
        "recommendation",
        "main_evidence",
        "principal_risk",
        "smallest_decision_changer",
        "option_consequences",
        "rerun_question",
        "rerun_comparison",
        "proposed_baseline",
        "scientific_record_changes",
    }
    schema_version = value.get("schema_version")
    if schema_version not in SUPPORTED_DECISION_RECORD_SCHEMA_VERSIONS:
        raise StateValidationError(
            "decision record schema_version must be 1, 2, or 3"
        )
    required = set(base_required)
    if schema_version >= 2:
        required.add("selected_scientific_object")
    if set(value) != required:
        missing = sorted(required - set(value))
        extra = sorted(set(value) - required)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise StateValidationError(
            "decision record fields are invalid: " + "; ".join(details)
        )
    scientific_outcome = value.get("scientific_outcome")
    if scientific_outcome not in SCIENTIFIC_OUTCOMES:
        raise StateValidationError(
            "decision record scientific_outcome must be Complete, Partial, or Failed"
        )
    recommended_action = value.get("recommended_user_action")
    allowed_actions = (
        PHASE_TWO_USER_ACTIONS
        if schema_version == PHASE_TWO_DECISION_RECORD_SCHEMA_VERSION
        else APPROVAL_USER_ACTIONS
    )
    if recommended_action not in allowed_actions:
        allowed_text = ", ".join(sorted(allowed_actions))
        raise StateValidationError(
            "decision record recommended_user_action must be one of: "
            + allowed_text
        )

    evidence = value.get("main_evidence")
    if (
        not isinstance(evidence, list)
        or not evidence
        or len(evidence) > MAX_DECISION_LIST_ITEMS
    ):
        raise StateValidationError(
            f"decision record main_evidence must contain 1 to {MAX_DECISION_LIST_ITEMS} items"
        )
    normalized_evidence = [
        _decision_text(item, f"main_evidence[{index}]", maximum=2_000)
        for index, item in enumerate(evidence)
    ]

    consequences = value.get("option_consequences")
    consequence_keys = (
        PHASE_TWO_DECISION_OPTION_KEYS
        if schema_version == PHASE_TWO_DECISION_RECORD_SCHEMA_VERSION
        else DECISION_OPTION_KEYS
    )
    if not isinstance(consequences, Mapping) or set(consequences) != consequence_keys:
        raise StateValidationError(
            "decision record option_consequences must contain exactly: "
            + ", ".join(sorted(consequence_keys))
        )
    normalized_consequences = {
        key: _decision_text(consequences[key], f"option_consequences.{key}", maximum=2_000)
        for key in sorted(consequence_keys)
    }

    changes = value.get("scientific_record_changes")
    if (
        not isinstance(changes, list)
        or len(changes) > MAX_SCIENTIFIC_RECORD_CHANGES
    ):
        raise StateValidationError(
            f"decision record scientific_record_changes must contain at most "
            f"{MAX_SCIENTIFIC_RECORD_CHANGES} items"
        )
    normalized_changes: list[dict[str, Any]] = []
    change_fields = {
        "statement_id",
        "operation",
        "changed_fields",
        "proposed_values",
        "evidential_basis",
        "reason",
        "parent_statement_id",
        "change_origin",
    }
    seen_statement_ids: set[str] = set()
    for index, change in enumerate(changes):
        if not isinstance(change, Mapping) or set(change) != change_fields:
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}] has invalid fields"
            )
        operation = change.get("operation")
        if operation not in SCIENTIFIC_RECORD_OPERATIONS:
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].operation is invalid"
            )
        statement_id = _decision_text(
            change.get("statement_id"),
            f"scientific_record_changes[{index}].statement_id",
            maximum=200,
        )
        if any(
            not (
                character.isascii()
                and (character.isalnum() or character in {"-", "_", "."})
            )
            for character in statement_id
        ):
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].statement_id "
                "must use ASCII letters, digits, hyphens, underscores, or periods"
            )
        if statement_id in seen_statement_ids:
            raise StateValidationError(
                "decision record scientific_record_changes must contain at most "
                "one consolidated change per statement_id"
            )
        seen_statement_ids.add(statement_id)
        changed = change.get("changed_fields")
        if (
            not isinstance(changed, list)
            or not changed
            or len(changed) > len(SCIENTIFIC_RECORD_FIELDS)
            or any(not isinstance(field, str) for field in changed)
            or len(set(changed)) != len(changed)
            or not set(changed).issubset(SCIENTIFIC_RECORD_FIELDS)
        ):
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].changed_fields "
                "must be a unique nonempty list of recognized scientific-record fields"
            )
        proposed = change.get("proposed_values")
        if not isinstance(proposed, Mapping) or set(proposed) != set(changed):
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].proposed_values "
                "must contain exactly the named changed_fields"
            )
        normalized_values: dict[str, Any] = {}
        for field in changed:
            proposed_value = proposed[field]
            label = (
                f"scientific_record_changes[{index}].proposed_values.{field}"
            )
            if isinstance(proposed_value, str):
                normalized_values[field] = _decision_text(
                    proposed_value, label, maximum=4_000
                )
            elif (
                isinstance(proposed_value, list)
                and proposed_value
                and len(proposed_value) <= MAX_DECISION_LIST_ITEMS
            ):
                normalized_values[field] = [
                    _decision_text(item, f"{label}[{item_index}]", maximum=2_000)
                    for item_index, item in enumerate(proposed_value)
                ]
            else:
                raise StateValidationError(
                    f"decision record {label} must be a nonempty string or "
                    f"a list of 1 to {MAX_DECISION_LIST_ITEMS} nonempty strings"
                )
        if operation == "add" and not NEW_STATEMENT_REQUIRED_FIELDS.issubset(changed):
            missing_new_fields = sorted(NEW_STATEMENT_REQUIRED_FIELDS - set(changed))
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}] adds a new "
                "statement but omits: " + ", ".join(missing_new_fields)
            )
        controlled_fields = {
            "statement_type": STATEMENT_TYPES,
            "formulation_state": FORMULATION_STATES,
            "assessment_status": ASSESSMENT_STATUSES,
            "logical_status": LOGICAL_STATUSES,
            "mathematical_result_type": MATHEMATICAL_RESULT_TYPES,
        }
        for field, allowed_values in controlled_fields.items():
            if field not in normalized_values:
                continue
            controlled_value = normalized_values[field]
            if not isinstance(controlled_value, str) or controlled_value not in allowed_values:
                raise StateValidationError(
                    f"decision record scientific_record_changes[{index}] uses an "
                    f"unrecognized {field}; allowed values are: "
                    + ", ".join(sorted(allowed_values))
                )
        proposed_formulation_state = normalized_values.get("formulation_state")
        if operation == "add" and proposed_formulation_state != "Proposed":
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}] adds a new "
                "statement and must set formulation_state to Proposed"
            )
        if operation != "withdraw" and proposed_formulation_state == "Withdrawn":
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}] must use the "
                "withdraw operation when setting formulation_state to Withdrawn"
            )
        if operation == "revise" and {"wording", "scope"}.intersection(changed):
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}] must use a "
                "new statement ID and add operation for a wording or scope change"
            )
        if (
            operation == "withdraw"
            and (
                "formulation_state" not in changed
                or normalized_values.get("formulation_state") != "Withdrawn"
            )
        ):
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}] withdraws a "
                "statement without setting formulation_state to Withdrawn"
            )
        basis = change.get("evidential_basis")
        if (
            not isinstance(basis, list)
            or not basis
            or len(basis) > MAX_DECISION_LIST_ITEMS
        ):
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].evidential_basis "
                f"must contain 1 to {MAX_DECISION_LIST_ITEMS} items"
            )
        raw_parent = change.get("parent_statement_id")
        if raw_parent is None:
            parent_statement_id = None
        else:
            parent_statement_id = _decision_text(
                raw_parent,
                f"scientific_record_changes[{index}].parent_statement_id",
                maximum=200,
            )
            if any(
                not (
                    character.isascii()
                    and (character.isalnum() or character in {"-", "_", "."})
                )
                for character in parent_statement_id
            ):
                raise StateValidationError(
                    f"decision record scientific_record_changes[{index}]."
                    "parent_statement_id must use ASCII letters, digits, hyphens, "
                    "underscores, or periods"
                )
            if parent_statement_id == statement_id:
                raise StateValidationError(
                    f"decision record scientific_record_changes[{index}] cannot "
                    "name its own statement_id as parent_statement_id"
                )
        if parent_statement_id and operation != "add":
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}] may name a "
                "parent_statement_id only when adding a replacement statement"
            )
        origin = change.get("change_origin")
        origin_fields = {"phase", "run", "round_or_stage", "role"}
        if not isinstance(origin, Mapping) or set(origin) != origin_fields:
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].change_origin "
                "must contain exactly phase, run, round_or_stage, and role"
            )
        normalized_origin = {
            field: _decision_text(
                origin[field],
                f"scientific_record_changes[{index}].change_origin.{field}",
                maximum=200,
            )
            for field in sorted(origin_fields)
        }
        normalized_changes.append({
            "statement_id": statement_id,
            "operation": operation,
            "changed_fields": list(changed),
            "proposed_values": normalized_values,
            "evidential_basis": [
                _decision_text(
                    item,
                    f"scientific_record_changes[{index}].evidential_basis[{basis_index}]",
                    maximum=2_000,
                )
                for basis_index, item in enumerate(basis)
            ],
            "reason": _decision_text(
                change.get("reason"),
                f"scientific_record_changes[{index}].reason",
                maximum=4_000,
            ),
            "parent_statement_id": parent_statement_id,
            "change_origin": normalized_origin,
        })

    normalized_selected_object: dict[str, str] | None = None
    if schema_version >= 2:
        selected_object = value.get("selected_scientific_object")
        if selected_object is not None:
            if not isinstance(selected_object, Mapping) or set(selected_object) != {
                "kind",
                "stable_id",
                "version",
            }:
                raise StateValidationError(
                    "decision record selected_scientific_object must be null or "
                    "contain exactly kind, stable_id, and version"
                )
            kind = _decision_text(
                selected_object.get("kind"),
                "selected_scientific_object.kind",
                maximum=100,
            )
            if kind != "method":
                raise StateValidationError(
                    "decision record selected_scientific_object.kind must be method"
                )
            stable_id = _decision_text(
                selected_object.get("stable_id"),
                "selected_scientific_object.stable_id",
                maximum=200,
            )
            version = _decision_text(
                selected_object.get("version"),
                "selected_scientific_object.version",
                maximum=200,
            )
            for label, item in (("stable_id", stable_id), ("version", version)):
                if any(
                    not (
                        character.isascii()
                        and (character.isalnum() or character in {"-", "_", ".", "/"})
                    )
                    for character in item
                ):
                    raise StateValidationError(
                        "decision record selected_scientific_object."
                        f"{label} must use ASCII letters, digits, hyphens, "
                        "underscores, periods, or slashes"
                    )
            normalized_selected_object = {
                "kind": kind,
                "stable_id": stable_id,
                "version": version,
            }

    normalized_record = {
        "schema_version": schema_version,
        "scientific_outcome": scientific_outcome,
        "decision_requested": _decision_text(
            value.get("decision_requested"), "decision_requested", maximum=2_000
        ),
        "recommended_user_action": recommended_action,
        "recommendation": _decision_text(
            value.get("recommendation"), "recommendation", maximum=4_000
        ),
        "main_evidence": normalized_evidence,
        "principal_risk": _decision_text(
            value.get("principal_risk"), "principal_risk", maximum=4_000
        ),
        "smallest_decision_changer": _decision_text(
            value.get("smallest_decision_changer"),
            "smallest_decision_changer",
            maximum=4_000,
        ),
        "option_consequences": normalized_consequences,
        "rerun_question": _decision_text(
            value.get("rerun_question"), "rerun_question", maximum=4_000
        ),
        "rerun_comparison": _decision_text(
            value.get("rerun_comparison"), "rerun_comparison", maximum=4_000
        ),
        "proposed_baseline": _decision_text(
            value.get("proposed_baseline"), "proposed_baseline"
        ),
        "scientific_record_changes": normalized_changes,
    }
    if schema_version >= 2:
        normalized_record["selected_scientific_object"] = normalized_selected_object
    return normalized_record


def _read_decision_record_file(
    project_dir: str | Path, raw_path: str | Path
) -> tuple[str, bytes, dict[str, Any]]:
    root = Path(project_dir).resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    if _path_uses_symlink_below(candidate, root):
        raise StateValidationError("decision record must not be a symbolic link")
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise StateValidationError(
            "decision record must be an existing file inside the project"
        ) from exc
    if not resolved.is_file():
        raise StateValidationError("decision record must be a regular file")
    payload = _read_bounded_file(
        resolved,
        maximum=MAX_DECISION_RECORD_BYTES,
        label="decision record",
    )
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StateValidationError("decision record must be valid UTF-8 JSON") from exc
    return relative.as_posix(), payload, validate_decision_record(parsed)


def _manifest_decision_path(
    project_dir: str | Path, manifest: Mapping[str, Any] | None
) -> Path | None:
    if manifest is None or _manifest_schema_version(manifest) < 4:
        return None
    declared = manifest.get("decision_path")
    summary = manifest.get("summary_path")
    if not isinstance(declared, str) or not declared.strip():
        raise StateValidationError("run manifest has no decision record path")
    if not isinstance(summary, str) or not summary.strip():
        raise StateValidationError("run manifest has no final summary path")
    expected = Path(summary).with_suffix(".decision.json").resolve()
    candidate = Path(declared).resolve()
    root = Path(project_dir).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise StateValidationError("decision record path escaped the project") from exc
    if candidate != expected:
        raise StateValidationError(
            "run manifest decision record path does not match its final summary"
        )
    return candidate


def _seal_decision_record(
    project_dir: str | Path,
    manifest: Mapping[str, Any] | None,
    raw_path: str | Path | None,
) -> dict[str, Any] | None:
    expected = _manifest_decision_path(project_dir, manifest)
    if raw_path is None:
        if expected is not None:
            raise StateValidationError("this run requires a structured decision record")
        return None
    supplied = Path(raw_path).resolve()
    if expected is not None and supplied != expected:
        raise StateValidationError(
            "decision record path does not match the immutable run manifest"
        )
    normalized, payload, data = _read_decision_record_file(project_dir, supplied)
    _validate_decision_record_context(data, manifest)
    return {
        "path": normalized,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "schema_version": int(data["schema_version"]),
        "data": data,
        "sealed_at": _now_iso(),
    }


def _validate_decision_record_context(
    data: Mapping[str, Any], manifest: Mapping[str, Any] | None
) -> None:
    """Bind every proposed scientific-record change to this exact run."""

    if manifest is None:
        if data.get("schema_version") == PHASE_TWO_DECISION_RECORD_SCHEMA_VERSION:
            raise StateValidationError(
                "decision record schema 3 requires a current Phase 02 manifest"
            )
        return
    phase_slug = str(manifest.get("phase_slug", "")).strip()
    run_id = str(manifest.get("run_id", "")).strip()
    if not phase_slug or not run_id:
        raise StateValidationError(
            "run manifest cannot bind decision-record changes to a phase and run"
        )
    try:
        manifest_schema = int(manifest.get("schema_version", 1))
    except (TypeError, ValueError) as exc:
        raise StateValidationError("run manifest schema version is invalid") from exc
    decision_schema = data.get("schema_version")
    selected_object = data.get("selected_scientific_object")
    is_new_method_menu = (
        phase_slug == METHOD_DEVELOPMENT_PHASE and manifest_schema >= 9
    )
    if is_new_method_menu:
        if decision_schema != PHASE_TWO_DECISION_RECORD_SCHEMA_VERSION:
            raise StateValidationError(
                "current Phase 02 runs require decision record schema 3"
            )
        if selected_object is not None:
            raise StateValidationError(
                "Phase 02 publishes a method menu and must not select one method"
            )
    else:
        if decision_schema == PHASE_TWO_DECISION_RECORD_SCHEMA_VERSION:
            raise StateValidationError(
                "decision record schema 3 is reserved for current Phase 02 runs"
            )
        if manifest_schema >= 7 and decision_schema != DECISION_RECORD_SCHEMA_VERSION:
            raise StateValidationError(
                "schema-7 and later runs require decision record schema 2"
            )
        if phase_slug == METHOD_DEVELOPMENT_PHASE and manifest_schema >= 7:
            if not isinstance(selected_object, Mapping):
                raise StateValidationError(
                    "legacy Phase 02 decision record must name one selected method ID and version"
                )
            stable_id = str(selected_object.get("stable_id", ""))
            version = str(selected_object.get("version", ""))
            decision_requested = str(data.get("decision_requested", ""))
            if stable_id not in decision_requested or version not in decision_requested:
                raise StateValidationError(
                    "legacy Phase 02 decision_requested must repeat the selected method ID and version"
                )
    phase = manifest.get("phase")
    if not isinstance(phase, Mapping):
        if manifest_schema < 5:
            return
        raise StateValidationError(
            "run manifest cannot bind decision-record origins to a frozen phase plan"
        )
    members = {
        str(role)
        for role in phase.get("members", [])
        if isinstance(role, str) and role
    }
    members.add("research_lead")
    try:
        rounds_requested = int(manifest.get("rounds_requested", 0))
    except (TypeError, ValueError) as exc:
        raise StateValidationError(
            "run manifest rounds_requested is invalid"
        ) from exc
    stages = phase.get("stages", [])
    pattern = str(phase.get("pattern", ""))
    for index, change in enumerate(data.get("scientific_record_changes", [])):
        origin = change.get("change_origin", {})
        if (
            not isinstance(origin, Mapping)
            or origin.get("phase") != phase_slug
            or origin.get("run") != run_id
        ):
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].change_origin "
                "does not match the immutable phase and run"
            )
        role = str(origin.get("role", ""))
        stage = str(origin.get("round_or_stage", ""))
        if role not in members:
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].change_origin "
                "role is not part of the frozen run plan"
            )
        if stage == "summary":
            if role != "research_lead":
                raise StateValidationError(
                    f"decision record scientific_record_changes[{index}].change_origin "
                    "may use summary only for research_lead synthesis"
                )
            continue
        if not stage.startswith("round ") or not stage[6:].isdigit():
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].change_origin."
                "round_or_stage must be summary or round N"
            )
        round_n = int(stage[6:])
        if round_n < 1 or round_n > rounds_requested:
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].change_origin "
                "round is outside the frozen run plan"
            )
        if pattern == "sequential":
            if not isinstance(stages, list) or round_n > len(stages):
                raise StateValidationError(
                    "frozen sequential phase stages do not match rounds_requested"
                )
            planned_stage = stages[round_n - 1]
            planned_role = (
                str(planned_stage.get("role", ""))
                if isinstance(planned_stage, Mapping)
                else ""
            )
            if role != planned_role:
                raise StateValidationError(
                    f"decision record scientific_record_changes[{index}].change_origin "
                    "role does not match the frozen sequential stage"
                )
        elif role not in {
            str(item)
            for item in phase.get("members", [])
            if isinstance(item, str)
        }:
            raise StateValidationError(
                f"decision record scientific_record_changes[{index}].change_origin "
                "role is not assigned to the recorded round"
            )


def _validate_recorded_decision_record(
    project_dir: str | Path,
    run: Mapping[str, Any],
    manifest: Mapping[str, Any] | None,
) -> None:
    expected = _manifest_decision_path(project_dir, manifest)
    record = run.get("decision_record")
    if not record:
        if expected is not None and run.get("submitted_at"):
            raise StateValidationError("run has no sealed decision record")
        return
    if not isinstance(record, Mapping):
        raise StateValidationError("decision record state entry must be a mapping")
    normalized, payload, data = _read_decision_record_file(
        project_dir, str(record.get("path", ""))
    )
    _validate_decision_record_context(data, manifest)
    if expected is not None and (Path(project_dir).resolve() / normalized).resolve() != expected:
        raise StateValidationError("sealed decision record path does not match the run manifest")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != str(record.get("sha256", "")).lower():
        raise StateValidationError("decision record changed after submission")
    try:
        recorded_size = int(record.get("size", -1))
    except (TypeError, ValueError) as exc:
        raise StateValidationError("decision record size entry is invalid") from exc
    if recorded_size != len(payload):
        raise StateValidationError("decision record size changed after submission")
    if record.get("schema_version") != data.get("schema_version"):
        raise StateValidationError("decision record state schema is invalid")
    if record.get("data") != data:
        raise StateValidationError("decision record data does not match its sealed file")


def _validate_recorded_summary(
    project_dir: str | Path, run: Mapping[str, Any]
) -> None:
    if not run.get("final_summary"):
        raise StateValidationError("run has no final summary")
    normalized = _normalize_existing_path(
        project_dir, str(run["final_summary"]), summary=True
    )
    digest, _ = _hash_bounded_file(
        Path(project_dir).resolve() / normalized,
        maximum=MAX_SUMMARY_BYTES,
        label="final summary",
    )
    expected_digest = str(run.get("summary_sha256") or "").lower()
    if not expected_digest:
        raise StateValidationError("final summary has no sealed hash")
    if digest != expected_digest:
        raise StateValidationError("final summary changed after submission")


def _validate_run_integrity(
    project_dir: str | Path,
    phase_slug: str,
    run: Mapping[str, Any],
    *,
    require_summary: bool,
) -> None:
    manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
    _validate_recorded_protocol_checkpoint(
        project_dir,
        phase_slug,
        run,
        manifest,
        required=bool(phase_slug == DRAFT_ASSEMBLY_PHASE and manifest and manifest.get("protocol_checkpoint") is not None),
    )
    _validate_recorded_artifacts(project_dir, run)
    _validate_recorded_task_briefs(project_dir, phase_slug, run)
    paper_review = manifest.get("paper_review") if manifest else None
    if (
        phase_slug == PAPER_WRITING_PHASE
        and isinstance(paper_review, Mapping)
        and paper_review.get("kind") in {"full", "review_only"}
        and not run.get("review_target")
    ):
        raise StateValidationError("Phase 05 run has no sealed review manuscript")
    _validate_recorded_review_target(project_dir, run)
    _validate_recorded_submission_artifacts(
        project_dir, phase_slug, run, manifest
    )
    _validate_recorded_decision_record(project_dir, run, manifest)
    if require_summary:
        _validate_recorded_summary(project_dir, run)


def _report_from_data(
    data: Mapping[str, Any],
    phase_slug: str,
    dependencies: Mapping[str, Sequence[str]],
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    for prerequisite in dependencies.get(phase_slug, []):
        phase = data.get("phases", {}).get(prerequisite, {})
        approved_id = phase.get("approved_run")
        approved = next(
            (r for r in phase.get("runs", []) if r.get("run_id") == approved_id),
            None,
        )
        stale = bool(phase.get("stale"))
        partial_publication = bool(
            prerequisite == METHOD_DEVELOPMENT_PHASE
            and isinstance(approved, Mapping)
            and approved.get("publication_kind") == "method_menu"
            and approved.get("publication_readiness") == "partial"
        )
        satisfied = (
            approved is not None
            and approved.get("status") == "approved"
            and not stale
            and not partial_publication
        )
        integrity_error = False
        integrity_detail = ""
        if satisfied and project_dir is not None:
            try:
                _validate_run_integrity(
                    project_dir,
                    prerequisite,
                    approved,
                    require_summary=True,
                )
            except (OSError, ProjectStateError) as exc:
                integrity_error = True
                integrity_detail = str(exc)
            if integrity_error:
                satisfied = False
        if approved is None:
            reason = "no approved run"
        elif approved.get("status") != "approved":
            reason = "approved run reference is invalid"
        elif stale:
            reason = "approved result is stale"
        elif partial_publication:
            reason = "published Phase 02 method menu is scientifically partial"
        elif integrity_error:
            reason = "approved evidence is missing or changed"
        else:
            reason = "approved and current"
        requirements.append({
            "phase": prerequisite,
            "satisfied": satisfied,
            "approved_run": approved_id,
            "stale": stale,
            "phase_status": phase.get("status", "pending"),
            "reason": reason,
            "integrity_detail": integrity_detail,
        })
    blockers = [item["phase"] for item in requirements if not item["satisfied"]]
    return {
        "phase": phase_slug,
        "satisfied": not blockers,
        "blockers": blockers,
        "requirements": requirements,
        "checked_at": _now_iso(),
    }


def _scientific_outcome(run: Mapping[str, Any]) -> str:
    record = run.get("decision_record")
    data = record.get("data") if isinstance(record, Mapping) else None
    outcome = data.get("scientific_outcome") if isinstance(data, Mapping) else None
    return str(outcome) if outcome in SCIENTIFIC_OUTCOMES else ""


def _completed_result_from_phase(
    phase: Mapping[str, Any],
    phase_slug: str,
    project_dir: str | Path | None,
) -> tuple[Mapping[str, Any] | None, str]:
    """Return the newest scientifically usable, intact result for one phase."""

    integrity_detail = ""
    saw_scientific_failure = False
    for run in reversed(phase.get("runs", [])):
        if (
            not isinstance(run, Mapping)
            or str(run.get("status", "")) not in COMPLETED_RESULT_STATUSES
            or not run.get("submitted_at")
            or not run.get("final_summary")
        ):
            continue
        if _scientific_outcome(run) not in COMPLETED_SCIENTIFIC_OUTCOMES:
            saw_scientific_failure = True
            continue
        if project_dir is not None:
            try:
                _validate_run_integrity(
                    project_dir,
                    phase_slug,
                    run,
                    require_summary=True,
                )
            except (OSError, ProjectStateError) as exc:
                integrity_detail = str(exc)
                continue
        return run, ""
    if integrity_detail:
        return None, integrity_detail
    if saw_scientific_failure:
        return None, "the completed run has a Failed or missing scientific outcome"
    return None, "no completed result"


def _completion_report_from_data(
    data: Mapping[str, Any],
    phase_slug: str,
    dependencies: Mapping[str, Sequence[str]],
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Report completed scientific results without requiring user approval."""

    requirements: list[dict[str, Any]] = []
    for prerequisite in dependencies.get(phase_slug, []):
        phase = data.get("phases", {}).get(prerequisite, {})
        result, integrity_detail = _completed_result_from_phase(
            phase, prerequisite, project_dir
        )
        result_id = str(result.get("run_id", "")) if result else None
        outcome = _scientific_outcome(result) if result else ""
        if result is not None:
            reason = "completed and intact"
        elif integrity_detail and integrity_detail != "no completed result":
            reason = integrity_detail
        else:
            reason = "no completed result"
        requirements.append({
            "phase": prerequisite,
            "satisfied": result is not None,
            "completed_run": result_id,
            "approved_run": phase.get("approved_run"),
            "stale": bool(phase.get("stale")),
            "phase_status": phase.get("status", "pending"),
            "scientific_outcome": outcome,
            "reason": reason,
            "integrity_detail": (
                integrity_detail
                if result is None and integrity_detail != "no completed result"
                else ""
            ),
        })
    blockers = [item["phase"] for item in requirements if not item["satisfied"]]
    return {
        "phase": phase_slug,
        "policy": "completed_results",
        "satisfied": not blockers,
        "blockers": blockers,
        "requirements": requirements,
        "checked_at": _now_iso(),
    }

def _normalize_required_completed_runs(
    required_completed_runs: Mapping[str, str],
) -> dict[str, str]:
    """Normalize an exact phase-to-run prerequisite mapping."""

    if not isinstance(required_completed_runs, Mapping):
        raise StateValidationError("required_completed_runs must be a mapping")
    normalized: dict[str, str] = {}
    for raw_phase, raw_run_id in required_completed_runs.items():
        if not isinstance(raw_phase, str) or not isinstance(raw_run_id, str):
            raise StateValidationError(
                "required_completed_runs must map phase names to exact run IDs"
            )
        phase_slug = _resolve_slug(raw_phase.strip())
        run_id = raw_run_id.strip()
        if not phase_slug or not run_id or "\x00" in phase_slug or "\x00" in run_id:
            raise StateValidationError(
                "required_completed_runs contains an empty or invalid phase or run ID"
            )
        existing = normalized.get(phase_slug)
        if existing is not None and existing != run_id:
            raise StateValidationError(
                f"required_completed_runs names conflicting runs for {phase_slug}"
            )
        normalized[phase_slug] = run_id
    return normalized


def _required_completed_report_from_data(
    data: Mapping[str, Any],
    phase_slug: str,
    required_completed_runs: Mapping[str, str],
    project_dir: str | Path | None,
) -> dict[str, Any]:
    """Report whether each exact prerequisite run remains scientifically usable."""

    requirements: list[dict[str, Any]] = []
    normalized = _normalize_required_completed_runs(required_completed_runs)
    for prerequisite, required_run_id in normalized.items():
        phase = data.get("phases", {}).get(prerequisite, {})
        run = next(
            (
                candidate
                for candidate in phase.get("runs", [])
                if isinstance(candidate, Mapping)
                and str(candidate.get("run_id", "")) == required_run_id
            ),
            None,
        )
        outcome = _scientific_outcome(run) if isinstance(run, Mapping) else ""
        integrity_detail = ""
        satisfied = False
        if run is None:
            reason = "the exact completed run is no longer recorded"
        elif str(run.get("status", "")) not in COMPLETED_RESULT_STATUSES:
            reason = "the exact completed run is no longer approved or awaiting review"
        elif not run.get("submitted_at") or not run.get("final_summary"):
            reason = "the exact completed run has no submitted final summary"
        elif outcome not in COMPLETED_SCIENTIFIC_OUTCOMES:
            reason = "the exact completed run has a Failed or missing scientific outcome"
        elif project_dir is None:
            satisfied = True
            reason = "exact completed result is recorded; integrity was not evaluated"
        else:
            try:
                _validate_run_integrity(
                    project_dir,
                    prerequisite,
                    run,
                    require_summary=True,
                )
            except (OSError, ProjectStateError) as exc:
                integrity_detail = str(exc)
                reason = integrity_detail
            else:
                satisfied = True
                reason = "completed and intact"
        requirements.append({
            "phase": prerequisite,
            "satisfied": satisfied,
            "completed_run": required_run_id,
            "approved_run": phase.get("approved_run"),
            "stale": bool(phase.get("stale")),
            "phase_status": phase.get("status", "pending"),
            "scientific_outcome": outcome,
            "reason": reason,
            "integrity_detail": integrity_detail,
        })
    blockers = [item["phase"] for item in requirements if not item["satisfied"]]
    return {
        "phase": phase_slug,
        "required_completed_runs": dict(normalized),
        "policy": "required_completed_runs",
        "satisfied": not blockers,
        "blockers": blockers,
        "requirements": requirements,
        "checked_at": _now_iso(),
    }


def _approval_context_report_from_data(
    data: Mapping[str, Any],
    phase_slug: str,
    run: Mapping[str, Any],
    dependencies: Mapping[str, Sequence[str]],
    project_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Compare one run's frozen inputs with the currently accepted context."""

    changes: list[dict[str, str | None]] = []
    seen: set[str] = set()
    snapshot = run.get("prerequisite_snapshot") or {}
    launch_requirements = {
        str(item.get("phase")): item
        for item in snapshot.get("requirements", [])
        if isinstance(item, Mapping) and item.get("phase")
    }
    snapshot_required_runs = snapshot.get("required_completed_runs")
    exact_completion_policy = bool(
        snapshot.get("policy") == "required_completed_runs"
        or isinstance(snapshot_required_runs, Mapping)
    )
    completion_policy = bool(
        snapshot.get("policy") == "completed_results"
        and not exact_completion_policy
    )
    if exact_completion_policy:
        required_completed_runs = (
            _normalize_required_completed_runs(snapshot_required_runs)
            if isinstance(snapshot_required_runs, Mapping)
            else {
                prerequisite: str(item.get("completed_run", "")).strip()
                for prerequisite, item in launch_requirements.items()
                if str(item.get("completed_run", "")).strip()
            }
        )
        current_report = _required_completed_report_from_data(
            data,
            phase_slug,
            required_completed_runs,
            project_dir,
        )
    elif completion_policy:
        current_report = _completion_report_from_data(
            data, phase_slug, dependencies, project_dir
        )
    else:
        current_report = _report_from_data(data, phase_slug, dependencies, project_dir)
    current_requirements = {
        str(item.get("phase")): item
        for item in current_report.get("requirements", [])
        if isinstance(item, Mapping) and item.get("phase")
    }

    def add_change(source_phase: str, launch_run: Any, current_run: Any, reason: str) -> None:
        if source_phase in seen:
            return
        seen.add(source_phase)
        changes.append({
            "phase": source_phase,
            "launch_run": str(launch_run) if launch_run else None,
            "current_run": str(current_run) if current_run else None,
            "reason": reason,
        })

    prerequisite_phases = (
        tuple(launch_requirements)
        if exact_completion_policy
        else dependencies.get(phase_slug, [])
    )
    for prerequisite in prerequisite_phases:
        source_phase = data.get("phases", {}).get(prerequisite, {})
        launched = launch_requirements.get(prerequisite)
        current_requirement = current_requirements.get(prerequisite, {})
        identity_field = (
            "completed_run"
            if completion_policy or exact_completion_policy
            else "approved_run"
        )
        current_id = current_requirement.get(identity_field)
        if launched is None:
            add_change(
                prerequisite,
                None,
                current_id,
                "the prerequisite version was not recorded at launch",
            )
            continue
        launch_id = launched.get(identity_field)
        if exact_completion_policy:
            if current_id != launch_id:
                add_change(
                    prerequisite,
                    launch_id,
                    current_id,
                    "the exact completed prerequisite run changed after launch",
                )
            elif not current_requirement.get("satisfied"):
                add_change(
                    prerequisite,
                    launch_id,
                    current_id,
                    "the exact completed prerequisite evidence is missing or changed",
                )
            continue
        if completion_policy:
            if current_id != launch_id:
                add_change(
                    prerequisite,
                    launch_id,
                    current_id,
                    "the completed prerequisite result changed after launch",
                )
            elif not current_requirement.get("satisfied"):
                add_change(
                    prerequisite,
                    launch_id,
                    current_id,
                    "the completed prerequisite evidence is missing or changed",
                )
            continue
        current_stale = bool(source_phase.get("stale"))
        launch_stale = bool(launched.get("stale"))
        if current_id != launch_id:
            add_change(
                prerequisite,
                launch_id,
                current_id,
                "the approved prerequisite run changed after launch",
            )
        elif current_stale != launch_stale:
            add_change(
                prerequisite,
                launch_id,
                current_id,
                "the prerequisite freshness changed after launch",
            )
        elif current_requirements.get(prerequisite, {}).get("reason") == (
            "approved evidence is missing or changed"
        ):
            add_change(
                prerequisite,
                launch_id,
                current_id,
                "the approved prerequisite evidence is missing or changed",
            )

    for entry in run.get("context_inputs", []):
        if not isinstance(entry, Mapping):
            continue
        source_name = str(entry.get("phase", ""))
        if not source_name or source_name == phase_slug or source_name in seen:
            continue
        source_phase = data.get("phases", {}).get(source_name, {})
        launch_id = entry.get("run_id")
        if exact_completion_policy:
            current_run = next(
                (
                    candidate
                    for candidate in source_phase.get("runs", [])
                    if isinstance(candidate, Mapping)
                    and str(candidate.get("run_id", "")) == str(launch_id or "")
                ),
                None,
            )
            current_id = (
                str(current_run.get("run_id", ""))
                if isinstance(current_run, Mapping)
                else None
            )
            integrity_changed = current_run is None
            if not integrity_changed and project_dir is not None:
                try:
                    _validate_run_integrity(
                        project_dir,
                        source_name,
                        current_run,
                        require_summary=True,
                    )
                    summary_path = _normalize_existing_path(
                        project_dir,
                        current_run.get("final_summary", ""),
                        summary=True,
                    )
                    digest, _ = _hash_bounded_file(
                        Path(project_dir).resolve() / summary_path,
                        maximum=MAX_SUMMARY_BYTES,
                        label="frozen context summary",
                    )
                    integrity_changed = (
                        summary_path != str(entry.get("summary", "")).strip()
                        or digest != str(entry.get("sha256", "")).lower()
                        or digest
                        != str(current_run.get("summary_sha256", "")).lower()
                    )
                except (OSError, ProjectStateError):
                    integrity_changed = True
            if integrity_changed:
                add_change(
                    source_name,
                    launch_id,
                    current_id,
                    "the frozen context source evidence is missing or changed",
                )
            continue
        if completion_policy:
            current_result, _ = _completed_result_from_phase(
                source_phase, source_name, project_dir
            )
            current_id = (
                str(current_result.get("run_id", ""))
                if current_result is not None
                else None
            )
        else:
            current_id = source_phase.get("approved_run")
        integrity_changed = False
        if current_id == launch_id and project_dir is not None:
            current_run = next(
                (
                    candidate
                    for candidate in source_phase.get("runs", [])
                    if candidate.get("run_id") == current_id
                ),
                None,
            )
            try:
                allowed_statuses = (
                    COMPLETED_RESULT_STATUSES
                    if completion_policy
                    else frozenset({"approved"})
                )
                if (
                    current_run is None
                    or current_run.get("status") not in allowed_statuses
                    or (
                        completion_policy
                        and _scientific_outcome(current_run)
                        not in COMPLETED_SCIENTIFIC_OUTCOMES
                    )
                ):
                    integrity_changed = True
                else:
                    _validate_run_integrity(
                        project_dir,
                        source_name,
                        current_run,
                        require_summary=True,
                    )
                    summary_path = _normalize_existing_path(
                        project_dir, current_run.get("final_summary", ""), summary=True
                    )
                    digest, _ = _hash_bounded_file(
                        Path(project_dir).resolve() / summary_path,
                        maximum=MAX_SUMMARY_BYTES,
                        label="completed context summary",
                    )
                    integrity_changed = (
                        digest != str(entry.get("sha256", "")).lower()
                        or bool(current_run.get("summary_sha256"))
                        and digest != current_run.get("summary_sha256")
                    )
            except (OSError, ProjectStateError):
                integrity_changed = True
        if current_id != launch_id or (
            not completion_policy and bool(source_phase.get("stale"))
        ):
            add_change(
                source_name,
                launch_id,
                current_id,
                (
                    "a completed context source changed after launch"
                    if completion_policy
                    else "an approved context source changed or became stale after launch"
                ),
            )
        elif integrity_changed:
            add_change(
                source_name,
                launch_id,
                current_id,
                "approved context-source evidence is missing or changed",
            )

    launch_override = copy.deepcopy(run.get("override_metadata"))
    reasons = [str(item["reason"]) for item in changes]
    if launch_override:
        reasons.append("the run was launched with an explicit prerequisite override")
    return {
        "requires_acknowledgement": bool(changes or launch_override),
        "changed_sources": changes,
        "launch_override": launch_override,
        "reasons": reasons,
        "checked_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------


def reserve_run(
    project_dir: str | Path,
    phase_slug: str,
    mode: str,
    rounds_requested: int = 1,
    user_feedback: str = "",
    *,
    dependencies: Mapping[str, Sequence[str]] | None = None,
    gating: Mapping[str, Sequence[str]] | None = None,
    override_metadata: Mapping[str, Any] | str | None = None,
    replace_awaiting_review_note: str | None = None,
    replace_awaiting_review_run_id: str | None = None,
    expected_prerequisite_report_version: str | None = None,
    completed_results: bool = False,
    required_completed_runs: Mapping[str, str] | None = None,
) -> str:
    """Atomically reserve the project's sole active execution and return its ID.

    Unsatisfied prerequisites require explicit override metadata. The exact
    prerequisite report and override are snapshotted on the run so the UI can
    explain the user's decision later. ``completed_results`` uses completed,
    intact scientific results instead of user approval as the dependency rule.
    ``required_completed_runs`` binds the report to exact completed run IDs.
    """

    if completed_results and required_completed_runs is not None:
        raise StateValidationError(
            "completed_results and required_completed_runs are mutually exclusive"
        )
    normalized_required_runs = (
        _normalize_required_completed_runs(required_completed_runs)
        if required_completed_runs is not None
        else None
    )

    if isinstance(rounds_requested, bool):
        raise StateValidationError("rounds_requested must be a positive integer")
    try:
        requested = int(rounds_requested)
    except (TypeError, ValueError) as exc:
        raise StateValidationError("rounds_requested must be a positive integer") from exc
    if requested < 1:
        raise StateValidationError("rounds_requested must be at least 1")

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        active = _active_entries(data)
        if active:
            current_phase, current_run, _ = active[0]
            raise StateConflict(
                f"project already has an active run: {current_phase} "
                f"({current_run['run_id']}, {current_run['status']})"
            )

        phase = data["phases"].setdefault(phase_slug, _new_phase())
        latest = phase.get("runs", [])[-1] if phase.get("runs") else None
        replacement_request = None
        if latest and latest.get("status") == "awaiting_review":
            replacement_note = str(replace_awaiting_review_note or "").strip()
            if not replacement_note:
                raise StateConflict(
                    f"phase {phase_slug!r} has a run awaiting review; an explicit "
                    "replacement note is required to rerun it"
                )
            expected_replaced_run = str(
                replace_awaiting_review_run_id or ""
            ).strip()
            if not expected_replaced_run:
                raise StateConflict(
                    "the exact awaiting-review run selected for replacement is required"
                )
            if not hmac.compare_digest(
                expected_replaced_run, str(latest.get("run_id", ""))
            ):
                raise StateConflict(
                    "the result awaiting review changed after the replacement was "
                    "confirmed; review the current result before rerunning"
                )
            replacement_request = {
                "run_id": str(latest["run_id"]),
                "note": replacement_note,
                "requested_at": _now_iso(),
                "committed_at": None,
            }
        elif (
            replace_awaiting_review_note is not None
            or replace_awaiting_review_run_id is not None
        ):
            raise StateValidationError(
                "awaiting-review replacement metadata is valid only when the latest "
                "run awaits review"
            )

        supplied_dependencies = dependencies if dependencies is not None else gating
        if supplied_dependencies is not None:
            normalized_dependencies = _normalize_dependencies(supplied_dependencies)
            data["dependencies"] = normalized_dependencies
        else:
            normalized_dependencies = _normalize_dependencies(data.get("dependencies", {}))
        if normalized_required_runs is not None:
            report = _required_completed_report_from_data(
                data,
                phase_slug,
                normalized_required_runs,
                project_dir,
            )
        elif completed_results:
            report = _completion_report_from_data(
                data, phase_slug, normalized_dependencies, project_dir
            )
        else:
            report = _report_from_data(
                data, phase_slug, normalized_dependencies, project_dir
            )

        normalized_override: dict[str, Any] | None = None
        if override_metadata is not None:
            if isinstance(override_metadata, str):
                normalized_override = {"reason": override_metadata}
            else:
                normalized_override = dict(override_metadata)
            reason = str(normalized_override.get("reason", "")).strip()
            if not reason:
                raise StateValidationError("prerequisite override requires a nonempty reason")
            normalized_override["reason"] = reason
            normalized_override.setdefault("actor", "user")
            normalized_override["recorded_at"] = _now_iso()
            normalized_override["blockers"] = list(report["blockers"])
        if report["blockers"] and normalized_required_runs is not None:
            raise StateConflict(
                "exact completed prerequisites are missing or changed: "
                + ", ".join(report["blockers"])
            )
        if report["blockers"] and normalized_override is None:
            if normalized_required_runs is not None:
                required_state = "bound to intact exact completed runs"
            elif completed_results:
                required_state = "completed and intact"
            else:
                required_state = "approved and current"
            raise StateConflict(
                f"prerequisites are not {required_state}: "
                + ", ".join(report["blockers"])
            )
        if expected_prerequisite_report_version is not None:
            submitted_version = str(expected_prerequisite_report_version).strip()
            current_version = decision_report_version("prerequisite", report)
            if not submitted_version or not hmac.compare_digest(
                submitted_version, current_version
            ):
                raise StateConflict(
                    "prerequisite status changed after the user reviewed it"
                )
            if normalized_override is not None:
                normalized_override["prerequisite_report_version"] = current_version

        run_id = str(uuid.uuid4())
        timestamp = _now_iso()
        run_number = len(phase["runs"]) + 1
        run = {
            "run_id": run_id,
            "run_number": run_number,
            "status": "starting",
            "mode": str(mode),
            "rounds_requested": requested,
            "user_feedback": str(user_feedback),
            "created_at": timestamp,
            "started": timestamp,
            "process_pid": None,
            "process_identity": None,
            "completed": None,
            "ended_at": None,
            "rounds": [],
            "final_summary": None,
            "summary_sha256": None,
            "context_inputs": [],
            "context_frozen": False,
            "manifest_path": None,
            "manifest_sha256": None,
            "review_target": None,
            "submission_artifacts": {},
            "method_menu_seal": None,
            "method_menu_changes": None,
            "publication_kind": None,
            "published_at": None,
            "publication_outcome": None,
            "publication_readiness": None,
            "migration_warning": None,
            "decision_record": None,
            "replacement_request": replacement_request,
            "timeout_minutes": None,
            "prerequisite_snapshot": report,
            "override_metadata": normalized_override,
            "submitted_at": None,
            "decision_at": None,
            "decision_by": None,
            "decision_note": None,
            "approval_baseline_acknowledgement": None,
            "approval_context_acknowledgement": None,
            "error": None,
            "cleanup_outcome": None,
            "cleanup_reason": None,
            "cleanup_started_at": None,
            "cleanup_completed_at": None,
            "cleanup_recovery_note": None,
        }
        phase["runs"].append(run)
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return run_id


def set_process_pid(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    pid: int,
    *,
    process_identity: str | None = None,
) -> None:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise StateValidationError("process PID must be a positive integer")
    identity = str(process_identity or "").strip() or None
    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"starting", "running"}, "set process PID for")
        existing = run.get("process_pid")
        if existing is not None and existing != pid:
            raise StateConflict(f"run already belongs to process PID {existing}")
        run["process_pid"] = pid
        run["process_identity"] = identity
        replacement = run.get("replacement_request")
        if isinstance(replacement, Mapping) and not replacement.get("committed_at"):
            source_id = str(replacement.get("run_id", ""))
            try:
                source = _get_run(data, phase_slug, source_id)
            except KeyError as exc:
                raise StateConflict("replacement source run is no longer available") from exc
            if source.get("status") != "awaiting_review":
                raise StateConflict(
                    "replacement source is no longer awaiting the user's decision"
                )
            timestamp = _now_iso()
            source["status"] = "revision_requested"
            source["decision_at"] = timestamp
            source["decision_by"] = "user"
            source["decision_note"] = str(replacement.get("note", ""))
            source["replaced_by_rerun"] = True
            source["replaced_by_run"] = str(run.get("run_id", ""))
            run["replacement_request"] = {
                **dict(replacement),
                "committed_at": timestamp,
            }
        run["status"] = "running"
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)


def set_run_context(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    entries: Sequence[Mapping[str, Any]],
) -> None:
    """Freeze exact completed summaries used as cross-phase inputs.

    Each entry contains ``phase``, ``run_id``, ``summary``, and ``sha256``.
    The referenced run and file are checked, including the content hash.  An
    identical repeat is idempotent; changing a frozen context is rejected.
    """

    normalized_entries: list[dict[str, str]] = []
    seen_sources: set[tuple[str, str]] = set()
    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"starting", "running"}, "set context for")
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise StateValidationError("each context entry must be a mapping")
            source_phase = str(entry.get("phase", "")).strip()
            source_run_id = str(entry.get("run_id", "")).strip()
            supplied_hash = str(entry.get("sha256", "")).strip().lower()
            if not source_phase or not source_run_id:
                raise StateValidationError("context phase and run_id must be nonempty")
            source_key = (source_phase, source_run_id)
            if source_key in seen_sources:
                raise StateValidationError(
                    f"duplicate context source: {source_phase}/{source_run_id}"
                )
            seen_sources.add(source_key)
            try:
                _, source_run, _ = _resolve_run(data, source_phase, source_run_id)
            except KeyError as exc:
                raise StateValidationError(
                    f"context references an unknown run: {source_phase}/{source_run_id}"
                ) from exc
            source_status = str(source_run.get("status", ""))
            if source_status not in {
                "approved", "awaiting_review", "revision_requested", "superseded"
            }:
                raise StateValidationError(
                    f"context run has no completed result: {source_phase}/{source_run_id}"
                )
            try:
                _validate_run_integrity(
                    project_dir,
                    source_phase,
                    source_run,
                    require_summary=True,
                )
            except (OSError, ProjectStateError) as exc:
                raise StateValidationError(
                    f"context run evidence is unavailable: {source_phase}/{source_run_id}"
                ) from exc
            summary_path = _normalize_existing_path(
                project_dir, entry.get("summary", ""), summary=True
            )
            if summary_path != source_run.get("final_summary"):
                raise StateValidationError(
                    f"context summary does not match run {source_phase}/{source_run_id}"
                )
            digest, _ = _hash_bounded_file(
                Path(project_dir).resolve() / summary_path,
                maximum=MAX_SUMMARY_BYTES,
                label="completed context summary",
            )
            if supplied_hash != digest:
                raise StateValidationError(
                    f"context sha256 does not match summary: {source_phase}/{source_run_id}"
                )
            recorded_digest = source_run.get("summary_sha256")
            if recorded_digest and recorded_digest != digest:
                raise StateValidationError(
                    f"completed summary changed after submission: {source_phase}/{source_run_id}"
                )
            if not recorded_digest:
                # Establish an integrity baseline when migrating a legacy approved run.
                source_run["summary_sha256"] = digest
            normalized_entries.append({
                "phase": source_phase,
                "run_id": source_run_id,
                "summary": summary_path,
                "sha256": digest,
                "status_at_selection": source_status,
            })

        existing = run.get("context_inputs", [])
        if run.get("context_frozen"):
            if existing == normalized_entries:
                return
            raise StateConflict("run context is already frozen and cannot be changed")
        run["context_inputs"] = normalized_entries
        run["context_frozen"] = True
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)


def seal_run_manifest(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    manifest_path: str | Path,
) -> str:
    """Record the exact run manifest hash before the worker starts."""

    expected_root = (state_dir(project_dir) / "runs" / phase_slug).resolve()
    raw_candidate = Path(manifest_path)
    if _path_uses_symlink_below(raw_candidate, expected_root):
        raise StateValidationError("run manifest path must not use symbolic links")
    candidate = raw_candidate.resolve(strict=True)
    try:
        candidate.relative_to(expected_root)
    except ValueError as exc:
        raise StateValidationError("run manifest must stay in its phase control directory") from exc
    payload = _read_bounded_file(
        candidate,
        maximum=MAX_CONTROL_FILE_BYTES,
        label="run manifest",
    )
    digest = hashlib.sha256(payload).hexdigest()
    try:
        manifest = json.loads(payload.decode("utf-8"))
        timeout_minutes = int(manifest["timeout_minutes"])
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise StateValidationError("run manifest is invalid or missing its timeout") from exc
    if manifest.get("phase_slug") != phase_slug or timeout_minutes < 1:
        raise StateValidationError("run manifest identity or timeout is invalid")
    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"starting"}, "seal the manifest for")
        if manifest.get("run_id") != run.get("run_id"):
            raise StateValidationError("run manifest identity does not match the state record")
        existing_path = run.get("manifest_path")
        existing_hash = run.get("manifest_sha256")
        path_text = str(candidate)
        if existing_path or existing_hash:
            if existing_path == path_text and existing_hash == digest:
                return digest
            raise StateConflict("run manifest is already sealed")
        run["manifest_path"] = path_text
        run["manifest_sha256"] = digest
        run["timeout_minutes"] = timeout_minutes
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return digest


def seal_review_target(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    manuscript: str | Path,
    sha256: str,
) -> dict[str, Any]:
    """Record the exact manuscript used by every reviewer substage."""

    expected_digest = str(sha256).strip().lower()
    if (
        len(expected_digest) != 64
        or any(character not in "0123456789abcdef" for character in expected_digest)
    ):
        raise StateValidationError("review target sha256 must be a SHA-256 digest")
    normalized = _normalize_existing_path(
        project_dir, manuscript, nonempty_file=True
    )
    current_digest, current_size = _hash_bounded_file(
        Path(project_dir).resolve() / normalized,
        maximum=MAX_REVIEW_OUTPUT_BYTES,
        label="review target",
    )
    if current_digest != expected_digest:
        raise StateValidationError("review target hash does not match its contents")

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"starting", "running"}, "seal the review target for")
        existing = run.get("review_target")
        if existing:
            if (
                existing.get("path") == normalized
                and str(existing.get("sha256", "")).lower() == current_digest
                and int(existing.get("size", -1)) == current_size
            ):
                return copy.deepcopy(existing)
            raise StateConflict("the run review target is already sealed")
        record = {
            "path": normalized,
            "sha256": current_digest,
            "size": current_size,
            "sealed_at": _now_iso(),
        }
        run["review_target"] = record
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return copy.deepcopy(record)


def _validate_recorded_review_target(
    project_dir: str | Path, run: Mapping[str, Any]
) -> None:
    record = run.get("review_target")
    if not record:
        return
    if not isinstance(record, Mapping):
        raise StateValidationError("review target record must be a mapping")
    normalized = _normalize_existing_path(
        project_dir, str(record.get("path", "")), nonempty_file=True
    )
    digest, size = _hash_bounded_file(
        Path(project_dir).resolve() / normalized,
        maximum=MAX_REVIEW_OUTPUT_BYTES,
        label="review target",
    )
    if digest != str(record.get("sha256", "")).lower():
        raise StateValidationError(
            f"review target changed after reviewer dispatch: {normalized}"
        )
    try:
        recorded_size = int(record.get("size", -1))
    except (TypeError, ValueError) as exc:
        raise StateValidationError("review target size record is invalid") from exc
    if recorded_size != size:
        raise StateValidationError(
            f"review target size changed after reviewer dispatch: {normalized}"
        )


def start_round(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    lead_directive: str,
    agents: Sequence[str],
    round_n: int | None = None,
) -> int:
    """Start exactly the next requested round, with no overlap or overflow."""

    normalized_agents = [str(agent).strip() for agent in agents if str(agent).strip()]
    if not normalized_agents:
        raise StateValidationError("a round must record at least one agent")
    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"starting", "running"}, "start a round in")
        if any(round_.get("started") and not round_.get("completed") for round_ in run["rounds"]):
            raise StateConflict("the previous round is still in progress")
        expected = len(run["rounds"]) + 1
        if round_n is not None and round_n != expected:
            raise StateValidationError(f"expected round {expected}, got {round_n}")
        if expected > run["rounds_requested"]:
            raise StateConflict(
                f"run requested exactly {run['rounds_requested']} rounds; no more may start"
            )
        if phase_slug == DRAFT_ASSEMBLY_PHASE and expected > 1:
            manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
            _validate_recorded_protocol_checkpoint(
                project_dir, phase_slug, run, manifest, required=True
            )
        run["rounds"].append({
            "n": expected,
            "started": _now_iso(),
            "completed": None,
            "lead_directive": str(lead_directive),
            "agents": normalized_agents,
            "tasks": [],
            "artifacts": [],
            "outputs": [],
        })
        run["status"] = "running"
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return expected


def record_task(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    round_n: int,
    *,
    role: str,
    task_id: str,
    title: str,
    task_kind: str = "standard",
    brief_path: str | Path | None = None,
    brief_sha256: str | None = None,
    review_bundle: Mapping[str, Any] | None = None,
    workspace_path: str | Path | None = None,
) -> None:
    """Attach an exact external task ID to the active run's open round."""

    normalized_role = str(role).strip()
    normalized_task_id = str(task_id).strip()
    normalized_title = str(title).strip()
    normalized_task_kind = str(task_kind).strip()
    if not normalized_role:
        raise StateValidationError("task role must be nonempty")
    if not normalized_task_id:
        raise StateValidationError("task_id must be nonempty")
    if not normalized_title:
        raise StateValidationError("task title must be nonempty")
    if normalized_task_kind not in {"standard", "protocol", "result"}:
        raise StateValidationError("task kind is invalid")
    if brief_path is None or not str(brief_sha256 or "").strip():
        raise StateValidationError(
            "task brief path and sha256 are required for every external task"
        )
    control_root = state_dir(project_dir).resolve()
    raw_brief = Path(brief_path)
    if _path_uses_symlink_below(raw_brief, control_root):
        raise StateValidationError("task brief path must not use symbolic links")
    brief = raw_brief.resolve(strict=True)
    try:
        brief.relative_to(control_root)
    except ValueError as exc:
        raise StateValidationError("task brief must stay in the project control directory") from exc
    digest, _ = _hash_bounded_file(
        brief,
        maximum=MAX_CONTROL_FILE_BYTES,
        label="task brief",
    )
    if digest != str(brief_sha256).strip().lower():
        raise StateValidationError("task brief sha256 does not match its contents")
    normalized_brief = str(brief)
    normalized_brief_hash = digest
    normalized_workspace: str | None = None
    if workspace_path is not None:
        workspace_root = Path(project_dir).resolve()
        raw_workspace = Path(workspace_path)
        if _path_uses_symlink_below(raw_workspace, workspace_root):
            raise StateValidationError("task workspace must not use symbolic links")
        try:
            resolved_workspace = raw_workspace.resolve(strict=True)
            resolved_workspace.relative_to(workspace_root)
        except (OSError, ValueError) as exc:
            raise StateValidationError(
                "task workspace must be an existing directory inside the project"
            ) from exc
        if not resolved_workspace.is_dir():
            raise StateValidationError("task workspace must be a directory")
        normalized_workspace = str(resolved_workspace)

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"running"}, "record a task for")
        if round_n < 1 or round_n > len(run["rounds"]):
            raise KeyError(f"run has no round {round_n}")
        round_ = run["rounds"][round_n - 1]
        if round_.get("n") != round_n or round_n != len(run["rounds"]):
            raise StateConflict("tasks may only be recorded on the current round")
        if not round_.get("started") or round_.get("completed"):
            raise StateConflict("tasks require an open round")
        normalized_review_bundle = None
        if review_bundle is not None:
            if normalized_role != "paper_reviewer":
                raise StateValidationError(
                    "only the paper reviewer may use a sealed reviewer workspace"
                )
            normalized_review_bundle = _validate_review_bundle_record(
                project_dir,
                review_bundle,
                phase_slug=phase_slug,
                run_id=str(run.get("run_id", "")),
                round_n=round_n,
                role=normalized_role,
                brief_path=brief,
                brief_sha256=normalized_brief_hash,
            )
        if phase_slug == DRAFT_ASSEMBLY_PHASE and round_n == 1:
            manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
            spec = _manifest_protocol_checkpoint_spec(
                project_dir, phase_slug, manifest
            )
            if spec is not None and spec.get("protocol_root") is not None:
                manifest_schema = int(spec.get("manifest_schema_version", 0))
                recorded_tasks = [
                    task
                    for task in round_.get("tasks", [])
                    if isinstance(task, Mapping)
                ]
                if normalized_task_kind == "protocol":
                    if recorded_tasks or run.get("protocol_checkpoint"):
                        raise StateConflict(
                            "the protocol task must be the first Phase 04 round 1 task"
                        )
                elif normalized_task_kind == "result":
                    protocol_tasks = [
                        task
                        for task in recorded_tasks
                        if task.get("role") == "data_scientist"
                        and task.get("task_kind") == "protocol"
                    ]
                    if len(protocol_tasks) != 1 or len(recorded_tasks) != 1:
                        raise StateConflict(
                            "the Phase 04 result task requires exactly one preceding "
                            "protocol task"
                        )
                    _validate_recorded_protocol_checkpoint(
                        project_dir, phase_slug, run, manifest, required=True
                    )
                else:
                    raise StateValidationError(
                        "modern Phase 04 round 1 requires protocol or result task kind"
                    )
                if manifest_schema >= 7:
                    expected_workspace = (
                        Path(str(spec["protocol_root"]))
                        if normalized_task_kind == "protocol"
                        else Path(str(manifest.get("output_root", "")))
                        / "round-01"
                    ).resolve()
                    if (
                        normalized_workspace is None
                        or Path(normalized_workspace) != expected_workspace
                    ):
                        raise StateValidationError(
                            "schema-7 Phase 04 task workspace does not match its "
                            "write-limited run directory"
                        )
            elif normalized_task_kind != "standard":
                raise StateValidationError(
                    "legacy Phase 04 round 1 supports only a standard task"
                )
        elif normalized_task_kind != "standard":
            raise StateValidationError(
                "specialized task kinds are valid only for Phase 04 round 1"
            )
        elif phase_slug == DRAFT_ASSEMBLY_PHASE:
            manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
            # F7 fix: manifest may be None for legacy direct runs.
            if manifest is not None and _manifest_schema_version(manifest) >= 7:
                expected_workspace = (
                    Path(str(manifest.get("output_root", "")))
                    / f"round-{round_n:02d}"
                ).resolve()
                if (
                    normalized_workspace is None
                    or Path(normalized_workspace) != expected_workspace
                ):
                    raise StateValidationError(
                        "schema-7 Phase 04 task workspace does not match its "
                        "write-limited round directory"
                    )
        for phase in data.get("phases", {}).values():
            for existing_run in phase.get("runs", []):
                for existing_round in existing_run.get("rounds", []):
                    if any(
                        task.get("task_id") == normalized_task_id
                        for task in existing_round.get("tasks", [])
                        if isinstance(task, dict)
                    ):
                        raise StateConflict(f"task_id is already recorded: {normalized_task_id}")
        round_["tasks"].append({
            "task_id": normalized_task_id,
            "role": normalized_role,
            "task_kind": normalized_task_kind,
            "title": normalized_title,
            "brief_path": normalized_brief,
            "brief_sha256": normalized_brief_hash,
            "review_bundle": normalized_review_bundle,
            "workspace_path": normalized_workspace,
            "recorded_at": _now_iso(),
        })
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)


def complete_round(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    round_n: int,
    outputs: Sequence[str | Path] | None = None,
    *,
    supporting_outputs: Sequence[str | Path] | None = None,
    discover_supporting: bool = False,
) -> int:
    """Complete the open round and seal role reports and supporting files."""

    if not isinstance(discover_supporting, bool):
        raise StateValidationError("discover_supporting must be a boolean")
    if discover_supporting and supporting_outputs is not None:
        raise StateValidationError(
            "discover_supporting and supporting_outputs are mutually exclusive"
        )

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"running"}, "complete a round in")
        if round_n < 1 or round_n > len(run["rounds"]):
            raise KeyError(f"run has no round {round_n}")
        round_ = run["rounds"][round_n - 1]
        if round_.get("n") != round_n:
            raise StateValidationError("round numbering is inconsistent")
        if round_.get("completed"):
            raise StateConflict(f"round {round_n} is already completed")
        if round_n != len(run["rounds"]):
            raise StateConflict("only the currently open round may be completed")
        if phase_slug == DRAFT_ASSEMBLY_PHASE:
            manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
            _validate_recorded_protocol_checkpoint(
                project_dir, phase_slug, run, manifest, required=True
            )
        supplied_outputs = list(outputs or ())
        agent_count = len(set(round_.get("agents", [])))
        if len(supplied_outputs) < agent_count:
            raise StateValidationError(
                f"round records {agent_count} agents and requires at least that many output files"
            )
        normalized = [
            _normalize_existing_path(project_dir, output, nonempty_file=True)
            for output in supplied_outputs
        ]
        if len(set(normalized)) != len(normalized):
            raise StateValidationError("round output files must be unique")
        round_["outputs"] = normalized
        round_["artifacts"] = []
        for path in normalized:
            digest, size = _hash_bounded_file(
                Path(project_dir).resolve() / path,
                maximum=MAX_RUN_ARTIFACT_BYTES,
                label="round artifact",
            )
            round_["artifacts"].append({
                "path": path,
                "sha256": digest,
                "size": size,
            })
        root = Path(project_dir).resolve()
        round_directories = {
            (root / output).parent.resolve(strict=False) for output in normalized
        }
        if discover_supporting:
            if len(round_directories) != 1:
                raise StateValidationError(
                    "supporting discovery requires one unambiguous round directory"
                )
            supplied_supporting = discover_round_supporting_files(
                project_dir,
                next(iter(round_directories)),
                exclude=normalized,
            )
        else:
            supplied_supporting = list(supporting_outputs or ())
        if len(supplied_supporting) > MAX_ROUND_SUPPORTING_FILES:
            raise StateValidationError(
                "round contains too many supporting artifacts; "
                f"the limit is {MAX_ROUND_SUPPORTING_FILES}"
            )
        supporting = [
            _normalize_existing_path(project_dir, output, nonempty_file=True)
            for output in supplied_supporting
        ]
        if len(set(supporting)) != len(supporting):
            raise StateValidationError("round supporting artifact files must be unique")
        if set(supporting) & set(normalized):
            raise StateValidationError(
                "role reports and supporting artifacts must be recorded separately"
            )
        if supporting and len(round_directories) != 1:
            raise StateValidationError(
                "supporting artifacts require one unambiguous round directory"
            )
        round_directory = next(iter(round_directories), None)
        round_["supporting_artifacts"] = []
        supporting_size = 0
        for path in supporting:
            try:
                (root / path).relative_to(round_directory)
            except (TypeError, ValueError) as exc:
                raise StateValidationError(
                    "supporting artifact escaped its round directory"
                ) from exc
            digest, size = _hash_bounded_file(
                root / path,
                maximum=MAX_RUN_ARTIFACT_BYTES,
                label="round supporting artifact",
            )
            supporting_size += size
            if supporting_size > MAX_ROUND_SUPPORTING_BYTES:
                raise StateValidationError(
                    "round supporting artifacts exceed the "
                    f"{MAX_ROUND_SUPPORTING_BYTES:,}-byte aggregate safety limit"
                )
            round_["supporting_artifacts"].append({
                "path": path,
                "sha256": digest,
                "size": size,
            })
        if discover_supporting:
            rediscovered = discover_round_supporting_files(
                project_dir,
                round_directory,
                exclude=normalized,
            )
            if rediscovered != sorted(supporting):
                raise StateValidationError(
                    "round supporting artifact inventory changed while it was sealed"
                )
            sealed_by_path = {
                str(record["path"]): record
                for record in round_["supporting_artifacts"]
            }
            for path in rediscovered:
                digest, size = _hash_bounded_file(
                    root / path,
                    maximum=MAX_RUN_ARTIFACT_BYTES,
                    label="round supporting artifact rescan",
                )
                record = sealed_by_path.get(path)
                if (
                    record is None
                    or digest != str(record.get("sha256", "")).lower()
                    or size != int(record.get("size", -1))
                ):
                    raise StateValidationError(
                        "round supporting artifact changed while it was sealed: "
                        f"{path}"
                    )
        round_["completed"] = _now_iso()
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return len(supporting)


def stage_run_submission(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    final_summary: str | Path,
    decision_record: str | Path | None = None,
) -> None:
    """Record a valid summary while the worker is still under user control."""

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"running"}, "submit")
        requested = run["rounds_requested"]
        rounds = run.get("rounds", [])
        numbers = [round_.get("n") for round_ in rounds]
        if len(rounds) != requested or numbers != list(range(1, requested + 1)):
            raise StateValidationError(
                f"run requires exactly {requested} rounds; recorded {len(rounds)}"
            )
        completed = _completed_round_count(run)
        if completed != requested:
            raise StateValidationError(
                f"run requires {requested} completed rounds; only {completed} are complete"
            )
        manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
        _validate_recorded_protocol_checkpoint(
            project_dir,
            phase_slug,
            run,
            manifest,
            required=bool(phase_slug == DRAFT_ASSEMBLY_PHASE and manifest and manifest.get("protocol_checkpoint") is not None),
        )
        _validate_recorded_artifacts(project_dir, run)
        _validate_recorded_task_briefs(project_dir, phase_slug, run)
        paper_review = manifest.get("paper_review") if manifest else None
        if (
            phase_slug == PAPER_WRITING_PHASE
            and isinstance(paper_review, Mapping)
            and paper_review.get("kind") in {"full", "review_only"}
            and not run.get("review_target")
        ):
            raise StateValidationError("Phase 05 run has no sealed review manuscript")
        _validate_recorded_review_target(project_dir, run)
        specs = _phase_six_submission_specs(
            project_dir, phase_slug, run, manifest
        )
        run["submission_artifacts"] = _seal_submission_artifacts(
            project_dir, specs
        )
        _validate_recorded_submission_artifacts(
            project_dir, phase_slug, run, manifest
        )
        normalized_summary = _normalize_existing_path(
            project_dir, final_summary, summary=True
        )
        if manifest is not None and manifest.get("summary_path"):
            expected_summary = Path(str(manifest["summary_path"])).resolve()
            actual_summary = (Path(project_dir).resolve() / normalized_summary).resolve()
            if actual_summary != expected_summary:
                raise StateValidationError(
                    "final summary path does not match the immutable run manifest"
                )
        run["decision_record"] = _seal_decision_record(
            project_dir, manifest, decision_record
        )
        if (
            phase_slug == METHOD_DEVELOPMENT_PHASE
            and _manifest_schema_version(manifest) >= 9
        ):
            if not isinstance(manifest, Mapping):
                raise StateValidationError(
                    "current Phase 02 submission requires a sealed run manifest"
                )
            output_root = str(manifest.get("output_root", "")).strip()
            if not output_root:
                raise StateValidationError(
                    "current Phase 02 manifest has no output directory"
                )
            try:
                sealed_menu = method_menu.seal_staged_menu(
                    project_dir, output_root
                )
            except (OSError, ValueError) as exc:
                raise StateValidationError(
                    f"Phase 02 staged method menu is invalid: {exc}"
                ) from exc
            if not isinstance(sealed_menu, Mapping):
                raise StateValidationError(
                    "Phase 02 staged method menu seal is invalid"
                )
            run["method_menu_seal"] = copy.deepcopy(dict(sealed_menu))
        timestamp = _now_iso()
        run["final_summary"] = normalized_summary
        summary_digest, _ = _hash_bounded_file(
            Path(project_dir).resolve() / normalized_summary,
            maximum=MAX_SUMMARY_BYTES,
            label="final summary",
        )
        run["summary_sha256"] = summary_digest
        run["submitted_at"] = timestamp
        run["status"] = "submitting"
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)


def _phase_two_scientific_outcome(run: Mapping[str, Any]) -> str:
    record = run.get("decision_record")
    data = record.get("data") if isinstance(record, Mapping) else None
    outcome = data.get("scientific_outcome") if isinstance(data, Mapping) else None
    if outcome not in SCIENTIFIC_OUTCOMES:
        raise StateValidationError(
            "current Phase 02 submission has no valid scientific outcome"
        )
    return str(outcome)


def _promotion_changed_method_ids(
    promotion: Mapping[str, Any],
) -> set[str] | None:
    """Return changed method IDs, or ``None`` when the diff is unavailable."""

    for key in ("changed_stable_ids", "changed_ids"):
        values = promotion.get(key)
        if isinstance(values, list) and all(
            isinstance(value, str) and value.strip() for value in values
        ):
            return {value.strip() for value in values}
    changes = promotion.get("changes")
    if isinstance(changes, Mapping):
        return {
            str(stable_id).strip()
            for stable_id in changes
            if str(stable_id).strip()
        }
    if isinstance(changes, list):
        result: set[str] = set()
        for change in changes:
            if not isinstance(change, Mapping):
                return None
            stable_id = str(change.get("stable_id", "")).strip()
            if not stable_id:
                return None
            result.add(stable_id)
        return result
    return None


def _method_menu_change_record(
    promotion: Mapping[str, Any], changed_ids: set[str] | None
) -> dict[str, Any]:
    """Keep the scientific diff while excluding opaque rollback state."""

    record: dict[str, Any] = {
        "changed_stable_ids": sorted(changed_ids) if changed_ids is not None else None,
    }
    changes = promotion.get("changes")
    if isinstance(changes, (Mapping, list)):
        record["changes"] = copy.deepcopy(changes)
    return record


def _approved_method_identity(
    project_dir: str | Path,
    phase_slug: str,
    phase: Mapping[str, Any],
) -> str | None:
    approved_id = phase.get("approved_run")
    if not isinstance(approved_id, str) or not approved_id:
        return None
    approved = next(
        (
            candidate
            for candidate in phase.get("runs", [])
            if isinstance(candidate, Mapping)
            and candidate.get("run_id") == approved_id
            and candidate.get("status") == "approved"
        ),
        None,
    )
    if approved is None:
        return None
    try:
        manifest = _validate_recorded_manifest(
            project_dir, phase_slug, approved
        )
    except (OSError, ProjectStateError):
        return None
    selection = manifest.get("method_selection") if isinstance(manifest, Mapping) else None
    if not isinstance(selection, Mapping):
        return None
    stable_id = str(selection.get("stable_id", "")).strip()
    return stable_id or None


def _stale_changed_method_descendants_unlocked(
    project_dir: str | Path,
    data: dict[str, Any],
    run_id: str | None,
    timestamp: str,
    changed_ids: set[str] | None,
    *,
    reason_override: str | None = None,
    conservative_on_unknown: bool = True,
) -> list[str]:
    """Stale only branches affected by the new menu, then cascade."""

    if changed_ids == set():
        return []
    dependencies = _normalize_dependencies(data.get("dependencies", {}))
    reverse: dict[str, list[str]] = {}
    for dependent, prerequisites in dependencies.items():
        for prerequisite in prerequisites:
            reverse.setdefault(prerequisite, []).append(dependent)

    queue = [
        (phase_slug, False)
        for phase_slug in reverse.get(METHOD_DEVELOPMENT_PHASE, [])
    ]
    visited: dict[str, bool] = {}
    staled: list[str] = []
    while queue:
        phase_slug, forced = queue.pop(0)
        if visited.get(phase_slug) is True:
            continue
        if visited.get(phase_slug) is False and not forced:
            continue
        visited[phase_slug] = forced
        phase = data.get("phases", {}).get(phase_slug)
        identity = None
        affected = forced
        reason = "an upstream result depends on an affected method"
        if not affected and isinstance(phase, Mapping) and phase.get("approved_run"):
            identity = _approved_method_identity(project_dir, phase_slug, phase)
            if identity is None and conservative_on_unknown:
                affected = True
                reason = "the approved run has no verifiable sealed method identity"
            elif identity is not None and (changed_ids is None or identity in changed_ids):
                affected = True
                reason = (
                    reason_override
                    or f"method {identity} changed in the published Phase 02 menu"
                )

        if affected and isinstance(phase, dict) and phase.get("approved_run"):
            phase["stale"] = True
            phase["stale_at"] = timestamp
            phase["stale_reason"] = reason
            phase["stale_by_run"] = run_id
            staled.append(phase_slug)

        for descendant in reverse.get(phase_slug, []):
            queue.append((descendant, affected))
    return staled


def mark_method_dependents_stale(
    project_dir: str | Path,
    stable_id: str,
    *,
    reason: str,
    stale_by_run: str | None = None,
) -> list[str]:
    """Stale approved results bound to one retired or revised method."""

    normalized_id = str(stable_id).strip()
    normalized_reason = str(reason).strip()
    if not normalized_id:
        raise StateValidationError("method stable ID must be nonempty")
    if not normalized_reason:
        raise StateValidationError("method staleness reason must be nonempty")
    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        staled = _stale_changed_method_descendants_unlocked(
            project_dir,
            data,
            stale_by_run,
            _now_iso(),
            {normalized_id},
            reason_override=normalized_reason,
            conservative_on_unknown=False,
        )
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return staled


def _publish_method_menu_run_unlocked(
    phase: dict[str, Any],
    run: dict[str, Any],
    timestamp: str,
    scientific_outcome: str,
    change_record: Mapping[str, Any],
) -> None:
    """Make a completed Phase 02 run the current published menu."""

    old_published_id = phase.get("approved_run")
    if old_published_id and old_published_id != run["run_id"]:
        old = next(
            (
                candidate
                for candidate in phase.get("runs", [])
                if candidate.get("run_id") == old_published_id
            ),
            None,
        )
        if isinstance(old, dict) and old.get("status") == "approved":
            old["status"] = "superseded"
            old["superseded_at"] = timestamp
            old["superseded_by"] = run["run_id"]

    readiness = "ready" if scientific_outcome == "Complete" else "partial"
    run["status"] = "approved"
    run["published_at"] = timestamp
    run["publication_kind"] = "method_menu"
    run["publication_outcome"] = scientific_outcome
    run["publication_readiness"] = readiness
    run["method_menu_changes"] = copy.deepcopy(dict(change_record))
    phase["approved_run"] = run["run_id"]
    phase["publication_readiness"] = readiness
    phase["stale"] = False
    phase["stale_at"] = None
    phase["stale_reason"] = None
    phase["stale_by_run"] = None


def finalize_run_submission(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    *,
    expected_pid: int | None = None,
) -> bool:
    """Finalize a submission after its worker exits."""

    if expected_pid is not None and (
        isinstance(expected_pid, bool) or not isinstance(expected_pid, int) or expected_pid <= 0
    ):
        raise StateValidationError("expected PID must be a positive integer")
    finalized = _finalize_run_submission_locked(
        project_dir, phase_slug, run_ref, expected_pid=expected_pid
    )
    if not finalized:
        return False

    # --- Current-results promotion (§11) ---
    # The project lock has been released. Promotion runs under the separate
    # current-results lock. Failures are logged but never affect the
    # already-committed finalization result.
    try:
        from core import current_results
        if current_results.is_enabled():
            result = current_results.promote_run(
                project_dir, phase_slug, finalized["run_id"]
            )
            if not result["promoted"]:
                log.info(
                    "current-results promotion not applied for %s/%s: %s",
                    phase_slug, finalized["run_id"][:12], result["reason"],
                )
    except Exception:
        log.warning("current-results promotion failed", exc_info=True)
    return True


def _finalize_run_submission_locked(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    *,
    expected_pid: int | None = None,
) -> dict[str, str] | None:
    """Run the locked finalization logic.

    Returns ``{"run_id": str}`` on success, or None if the run was not
    in a finalizable state (returns False from the public API).
    """

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        phase, run, _ = _resolve_run(data, phase_slug, run_ref)
        if run.get("status") != "submitting":
            return None
        if expected_pid is not None and run.get("process_pid") != expected_pid:
            return None
        if not run.get("final_summary") or not run.get("submitted_at"):
            raise StateValidationError("submitted run is missing its summary record")
        _validate_run_integrity(
            project_dir, phase_slug, run, require_summary=True
        )
        manifest = _validate_recorded_manifest(project_dir, phase_slug, run)
        timestamp = _now_iso()
        run["completed"] = timestamp
        run["ended_at"] = timestamp
        publishes_method_menu = bool(
            phase_slug == METHOD_DEVELOPMENT_PHASE
            and _manifest_schema_version(manifest) >= 9
        )
        if not publishes_method_menu:
            if phase_slug == METHOD_DEVELOPMENT_PHASE:
                run["status"] = "superseded"
                run["superseded_at"] = timestamp
                run["superseded_by"] = phase.get("approved_run")
                run["migration_warning"] = {
                    "code": "legacy_phase_two_result_not_published",
                    "message": (
                        "This legacy Phase 02 result completed under the earlier "
                        "method-selection contract. It remains historical and "
                        "was not published automatically."
                    ),
                    "recorded_at": timestamp,
                }
            else:
                run["status"] = "awaiting_review"
            _refresh_derived_state(data)
            _save_unlocked(project_dir, data)
            return {"run_id": str(run["run_id"])}

        scientific_outcome = _phase_two_scientific_outcome(run)
        if scientific_outcome == "Failed":
            run["status"] = "failed"
            run["publication_outcome"] = "Failed"
            run["publication_readiness"] = "failed"
            run["method_menu_changes"] = None
            _refresh_derived_state(data)
            _save_unlocked(project_dir, data)
            return {"run_id": str(run["run_id"])}  # Failed — promote_run will skip

        if not isinstance(manifest, Mapping):
            raise StateValidationError(
                "current Phase 02 publication requires a sealed run manifest"
            )
        seal = run.get("method_menu_seal")
        if not isinstance(seal, Mapping):
            raise StateValidationError(
                "current Phase 02 publication has no sealed staged menu"
            )
        output_root = str(manifest.get("output_root", "")).strip()
        promotion: Mapping[str, Any] | None = None
        try:
            promotion = method_menu.promote_staged_menu(
                project_dir, output_root, seal
            )
        except (OSError, ValueError) as exc:
            raise StateValidationError(
                f"Phase 02 staged method menu could not be published: {exc}"
            ) from exc
        if not isinstance(promotion, Mapping):
            raise StateValidationError(
                "Phase 02 method-menu promotion record is invalid"
            )

        changed_ids = _promotion_changed_method_ids(promotion)
        change_record = _method_menu_change_record(promotion, changed_ids)
        try:
            _publish_method_menu_run_unlocked(
                phase,
                run,
                timestamp,
                scientific_outcome,
                change_record,
            )
            _stale_changed_method_descendants_unlocked(
                project_dir,
                data,
                str(run["run_id"]),
                timestamp,
                changed_ids,
            )
            _refresh_derived_state(data)
            _save_unlocked(project_dir, data)
        except Exception:
            try:
                method_menu.rollback_method_menu_promotion(
                    project_dir, promotion
                )
            except Exception as rollback_error:
                log.critical(
                    "Phase 02 menu rollback failed after state finalization error: %s",
                    rollback_error,
                )
            raise
        try:
            method_menu.commit_method_menu_promotion(project_dir, promotion)
        except Exception as cleanup_error:
            log.warning(
                "Published Phase 02 menu backup could not be removed: %s",
                cleanup_error,
            )
        return {"run_id": str(run["run_id"])}

def submit_run_for_review(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    final_summary: str | Path,
    decision_record: str | Path | None = None,
) -> None:
    """Compatibility helper for synchronous callers without a live worker."""

    stage_run_submission(
        project_dir, phase_slug, run_ref, final_summary, decision_record
    )
    if not finalize_run_submission(project_dir, phase_slug, run_ref):
        raise StateConflict("run changed state before it could enter user review")


def approve_run(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    *,
    approval_kind: str,
    dependencies: Mapping[str, Sequence[str]] | None = None,
    gating: Mapping[str, Sequence[str]] | None = None,
    reviewer: str = "user",
    note: str = "",
    baseline_acknowledgement: str = "",
    expected_decision_record_version: str | None = None,
    context_acknowledgement: str = "",
    expected_context_report_version: str | None = None,
) -> list[str]:
    """Approve a submitted run and stale recursively dependent approvals.

    Returns the phase slugs made stale.  The old approved run is superseded
    only at this point, preserving it as a fallback throughout rerun execution.
    """

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        phase, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"awaiting_review"}, "approve")
        _validate_run_integrity(
            project_dir, phase_slug, run, require_summary=True
        )

        scientific_record = run.get("decision_record")
        normalized_approval_kind = str(approval_kind).strip()
        if normalized_approval_kind not in {
            "approve",
            "approve_with_limitations",
        }:
            raise StateValidationError(
                "approval kind must be approve or approve_with_limitations"
            )
        baseline_acknowledgement_text = str(baseline_acknowledgement).strip()
        decision_record_version = None
        if scientific_record:
            if not isinstance(scientific_record, Mapping):
                raise StateValidationError("run decision record is invalid")
            if not baseline_acknowledgement_text:
                raise StateConflict(
                    "review and explicitly accept the proposed scientific baseline "
                    "before approval"
                )
            decision_record_version = str(
                scientific_record.get("sha256", "")
            ).lower()
            submitted_decision_version = str(
                expected_decision_record_version or ""
            ).strip().lower()
            if not submitted_decision_version or not hmac.compare_digest(
                submitted_decision_version, decision_record_version
            ):
                raise StateConflict(
                    "the proposed scientific baseline changed after the user reviewed it"
                )
        elif baseline_acknowledgement_text or expected_decision_record_version:
            raise StateConflict("this legacy run has no structured scientific baseline")

        supplied_dependencies = dependencies if dependencies is not None else gating
        # F8 fix: capture the pre-approval dependency graph for stale
        # propagation BEFORE any replacement. The reverse graph used for
        # staleness must reflect the edges that existed when downstream phases
        # were approved, not the post-mutation map.
        pre_approval_dependencies = _normalize_dependencies(
            data.get("dependencies", {})
        )
        if supplied_dependencies is not None:
            normalized_dependencies = _normalize_dependencies(supplied_dependencies)
            data["dependencies"] = normalized_dependencies
        else:
            normalized_dependencies = _normalize_dependencies(data.get("dependencies", {}))
        context_report = _approval_context_report_from_data(
            data, phase_slug, run, normalized_dependencies, project_dir
        )
        acknowledgement = str(context_acknowledgement).strip()
        if context_report["requires_acknowledgement"] and not acknowledgement:
            raise StateConflict(
                "the run used overridden or changed context; review it and explicitly "
                "acknowledge that limitation before approval"
            )
        context_report_version = decision_report_version(
            "approval_context", context_report
        )
        if expected_context_report_version is not None:
            submitted_version = str(expected_context_report_version).strip()
            if not submitted_version or not hmac.compare_digest(
                submitted_version, context_report_version
            ):
                raise StateConflict(
                    "approval context changed after the user reviewed it"
                )

        old_approved_id = phase.get("approved_run")
        if old_approved_id and old_approved_id != run["run_id"]:
            old = _get_run(data, phase_slug, old_approved_id)
            if old.get("status") == "approved":
                old["status"] = "superseded"
                old["superseded_at"] = _now_iso()
                old["superseded_by"] = run["run_id"]

        timestamp = _now_iso()
        run["status"] = "approved"
        run["decision_at"] = timestamp
        run["decision_by"] = str(reviewer)
        run["decision_note"] = str(note)
        run["approval_kind"] = normalized_approval_kind
        run["approval_baseline_acknowledgement"] = (
            {
                "actor": str(reviewer),
                "approval_kind": normalized_approval_kind,
                "note": baseline_acknowledgement_text,
                "recorded_at": timestamp,
                "decision_record_sha256": decision_record_version,
                "summary_sha256": str(run.get("summary_sha256") or ""),
                "proposed_baseline": scientific_record["data"]["proposed_baseline"],
            }
            if scientific_record
            else None
        )
        run["approval_context_acknowledgement"] = (
            {
                "actor": str(reviewer),
                "note": acknowledgement,
                "recorded_at": timestamp,
                "report": context_report,
                "report_version": context_report_version,
            }
            if acknowledgement
            else None
        )
        phase["approved_run"] = run["run_id"]
        phase["stale"] = False
        phase["stale_at"] = None
        phase["stale_reason"] = None
        phase["stale_by_run"] = None

        # Build the reverse dependency graph from the PRE-approval edges.
        # A phase that depended on the approved phase under the old graph but
        # not the new one must still be staled.
        reverse: dict[str, list[str]] = {}
        for dependent, prerequisites in pre_approval_dependencies.items():
            for prerequisite in prerequisites:
                reverse.setdefault(prerequisite, []).append(dependent)
        descendants: list[str] = []
        queue = list(reverse.get(phase_slug, []))
        visited: set[str] = set()
        while queue:
            dependent = queue.pop(0)
            if dependent in visited:
                continue
            visited.add(dependent)
            descendants.append(dependent)
            queue.extend(reverse.get(dependent, []))

        staled: list[str] = []
        for dependent in descendants:
            dependent_phase = data["phases"].get(dependent)
            if not dependent_phase or not dependent_phase.get("approved_run"):
                continue
            dependent_phase["stale"] = True
            dependent_phase["stale_at"] = timestamp
            dependent_phase["stale_reason"] = (
                f"upstream phase {phase_slug} approved a replacement run"
            )
            dependent_phase["stale_by_run"] = run["run_id"]
            staled.append(dependent)

        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return staled


def request_revision(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    note: str,
    *,
    reviewer: str = "user",
) -> None:
    if not str(note).strip():
        raise StateValidationError("revision request requires a nonempty note")
    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        _ensure_status(run, {"awaiting_review"}, "request revision for")
        run["status"] = "revision_requested"
        run["decision_at"] = _now_iso()
        run["decision_by"] = str(reviewer)
        run["decision_note"] = str(note).strip()
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)


def begin_run_cleanup(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    outcome: str,
    reason: str,
    *,
    expected_pid: int | None = None,
) -> bool:
    """Hold the active-run lease while its local and Hermes work is stopped."""

    if outcome not in {"failed", "cancelled"}:
        raise StateValidationError("cleanup outcome must be failed or cancelled")
    if expected_pid is not None and (
        isinstance(expected_pid, bool) or not isinstance(expected_pid, int) or expected_pid <= 0
    ):
        raise StateValidationError("expected PID must be a positive integer")
    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        if expected_pid is not None and run.get("process_pid") != expected_pid:
            return False
        if run.get("status") == "stopping":
            if run.get("cleanup_outcome") != outcome:
                raise StateConflict(
                    f"run cleanup is already targeting {run.get('cleanup_outcome')}"
                )
            return True
        if run.get("status") not in ACTIVE_RUN_STATUSES:
            return False
        run["status"] = "stopping"
        run["cleanup_outcome"] = outcome
        run["cleanup_reason"] = str(reason)
        run["cleanup_started_at"] = _now_iso()
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return True


def finalize_run_cleanup(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    *,
    expected_pid: int | None = None,
    cleanup_confirmed: bool = True,
    recovery_note: str = "",
) -> bool:
    """Publish the terminal outcome after cleanup or an explicit recovery."""

    if expected_pid is not None and (
        isinstance(expected_pid, bool) or not isinstance(expected_pid, int) or expected_pid <= 0
    ):
        raise StateValidationError("expected PID must be a positive integer")
    note = str(recovery_note).strip()
    if not cleanup_confirmed and not note:
        raise StateConflict(
            "unconfirmed cleanup requires an explicit recovery note"
        )
    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        if run.get("status") != "stopping":
            return False
        if expected_pid is not None and run.get("process_pid") != expected_pid:
            return False
        outcome = run.get("cleanup_outcome")
        if outcome not in {"failed", "cancelled"}:
            raise StateValidationError("stopping run has no valid cleanup outcome")
        timestamp = _now_iso()
        run["status"] = outcome
        if outcome == "failed":
            run["error"] = str(run.get("cleanup_reason") or "run cleanup failed")
            run["error_category"] = _classify_error(run["error"])
        else:
            run["cancel_reason"] = str(run.get("cleanup_reason") or "")
        run["cleanup_completed_at"] = timestamp
        run["cleanup_recovery_note"] = note or None
        run["ended_at"] = timestamp
        run["completed"] = timestamp
        _refresh_derived_state(data)
        _save_unlocked(project_dir, data)
        return True


def recover_run_cleanup(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    note: str,
) -> bool:
    """Explicitly release a stopping lease when cleanup cannot be confirmed."""

    if not str(note).strip():
        raise StateValidationError("cleanup recovery requires a nonempty note")
    return finalize_run_cleanup(
        project_dir,
        phase_slug,
        run_ref,
        cleanup_confirmed=False,
        recovery_note=note,
    )


def fail_run(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    error: str,
) -> None:
    if not begin_run_cleanup(project_dir, phase_slug, run_ref, "failed", error):
        status = get_run_status(project_dir, phase_slug, run_ref)
        raise StateConflict(f"cannot fail a run in status {status!r}")
    if not finalize_run_cleanup(project_dir, phase_slug, run_ref):
        raise StateConflict("run changed state before failure could be finalized")


def fail_run_if_active(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    error: str,
    expected_pid: int | None = None,
) -> bool:
    """Atomically fail a still-active run, optionally owned by one process.

    Returns ``False`` when another transition already ended execution or when
    the recorded PID does not match.  This makes worker reconciliation safe
    against a concurrent successful submission, cancellation, or replacement.
    """

    if not begin_run_cleanup(
        project_dir,
        phase_slug,
        run_ref,
        "failed",
        error,
        expected_pid=expected_pid,
    ):
        return False
    return finalize_run_cleanup(
        project_dir, phase_slug, run_ref, expected_pid=expected_pid
    )


def cancel_run(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    reason: str = "",
) -> None:
    if not begin_run_cleanup(project_dir, phase_slug, run_ref, "cancelled", reason):
        status = get_run_status(project_dir, phase_slug, run_ref)
        raise StateConflict(f"cannot cancel a run in status {status!r}")
    if not finalize_run_cleanup(project_dir, phase_slug, run_ref):
        raise StateConflict("run changed state before cancellation could be finalized")


def cancel_run_if_active(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    reason: str = "",
    expected_pid: int | None = None,
) -> bool:
    """Atomically cancel a still-active run, optionally matching its PID."""

    if not begin_run_cleanup(
        project_dir,
        phase_slug,
        run_ref,
        "cancelled",
        reason,
        expected_pid=expected_pid,
    ):
        return False
    return finalize_run_cleanup(
        project_dir, phase_slug, run_ref, expected_pid=expected_pid
    )


# ---------------------------------------------------------------------------
# Queries and prerequisite reporting
# ---------------------------------------------------------------------------


def get_status(project_dir: str | Path, phase_slug: str) -> str:
    return load(project_dir).get("phases", {}).get(phase_slug, {}).get("status", "pending")


def get_phase_status(project_dir: str | Path, phase_slug: str) -> dict[str, Any]:
    phase = load(project_dir).get("phases", {}).get(phase_slug)
    return copy.deepcopy(phase) if phase is not None else _new_phase()


def get_runs(project_dir: str | Path, phase_slug: str) -> list[dict[str, Any]]:
    return copy.deepcopy(
        load(project_dir).get("phases", {}).get(phase_slug, {}).get("runs", [])
    )


def last_run(project_dir: str | Path, phase_slug: str) -> dict[str, Any] | None:
    runs = get_runs(project_dir, phase_slug)
    return runs[-1] if runs else None


def get_run(
    project_dir: str | Path, phase_slug: str, run_ref: str | int
) -> dict[str, Any]:
    return copy.deepcopy(_get_run(load(project_dir), phase_slug, run_ref))


def get_run_status(
    project_dir: str | Path, phase_slug: str, run_ref: str | int
) -> str:
    return str(get_run(project_dir, phase_slug, run_ref).get("status"))


def get_active_run(project_dir: str | Path) -> dict[str, Any] | None:
    marker = load(project_dir).get("active_run")
    return copy.deepcopy(marker) if marker else None


def get_approved_run(project_dir: str | Path, phase_slug: str) -> dict[str, Any] | None:
    data = load(project_dir)
    phase = data.get("phases", {}).get(phase_slug, {})
    approved_id = phase.get("approved_run")
    if not approved_id:
        return None
    return copy.deepcopy(_get_run(data, phase_slug, approved_id))


def completed_round_count(
    project_dir: str | Path, phase_slug: str, run_ref: str | int
) -> int:
    return _completed_round_count(get_run(project_dir, phase_slug, run_ref))


def current_round(
    project_dir: str | Path, phase_slug: str, run_ref: str | int
) -> dict[str, Any] | None:
    run = get_run(project_dir, phase_slug, run_ref)
    for round_ in run.get("rounds", []):
        if round_.get("started") and not round_.get("completed"):
            return round_
    return None


def all_phases(project_dir: str | Path) -> dict[str, Any]:
    return copy.deepcopy(load(project_dir).get("phases", {}))


def prerequisite_report(
    project_dir: str | Path,
    phase_slug: str,
    dependencies: Mapping[str, Sequence[str]] | None = None,
    *,
    gating: Mapping[str, Sequence[str]] | None = None,
    completed_results: bool = False,
    required_completed_runs: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if completed_results and required_completed_runs is not None:
        raise StateValidationError(
            "completed_results and required_completed_runs are mutually exclusive"
        )
    data = load(project_dir)
    supplied = dependencies if dependencies is not None else gating
    normalized = _normalize_dependencies(
        supplied if supplied is not None else data.get("dependencies", {})
    )
    if required_completed_runs is not None:
        return _required_completed_report_from_data(
            data,
            phase_slug,
            _normalize_required_completed_runs(required_completed_runs),
            project_dir,
        )
    if completed_results:
        return _completion_report_from_data(
            data, phase_slug, normalized, project_dir
        )
    return _report_from_data(data, phase_slug, normalized, project_dir)


def run_integrity_report(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
) -> dict[str, Any]:
    """Report whether all sealed evidence for one submitted run is unchanged."""

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        try:
            _validate_run_integrity(
                project_dir,
                phase_slug,
                run,
                require_summary=bool(run.get("submitted_at") or run.get("final_summary")),
            )
        except (OSError, ProjectStateError) as exc:
            return {
                "ok": False,
                "reason": str(exc),
                "checked_at": _now_iso(),
            }
        return {"ok": True, "reason": "", "checked_at": _now_iso()}


def approval_context_report(
    project_dir: str | Path,
    phase_slug: str,
    run_ref: str | int,
    dependencies: Mapping[str, Sequence[str]] | None = None,
    *,
    gating: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Explain whether approval needs an explicit context acknowledgement."""

    with _project_lock(project_dir):
        data = _migrate(_read_unlocked(project_dir))
        _, run, _ = _resolve_run(data, phase_slug, run_ref)
        supplied = dependencies if dependencies is not None else gating
        normalized = _normalize_dependencies(
            supplied if supplied is not None else data.get("dependencies", {})
        )
        return copy.deepcopy(
            _approval_context_report_from_data(
                data, phase_slug, run, normalized, project_dir
            )
        )


def summary(project_dir: str | Path) -> str:
    data = load(project_dir)
    project = data.get("project", {})
    grouped: dict[str, list[str]] = {}
    for phase_slug, phase in data.get("phases", {}).items():
        grouped.setdefault(phase.get("status", "pending"), []).append(
            phase_slug.split("-", 1)[-1]
        )
    details = " | ".join(
        f"{status}: {', '.join(slugs)}" for status, slugs in grouped.items() if slugs
    )
    return f"[{project.get('id', '?')}] {project.get('name', '?')} - {details}"
