"""Protected storage facade for immutable knowledge mutation events."""

from __future__ import annotations

import hashlib
import hmac
import os
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core import knowledge_schema, project_state
from core.filesystem_utils import metadata_is_link_or_reparse
from core.knowledge_event_diff import build_event
from core.knowledge_event_schema import (
    EMPIRICAL_PHASE,
    EVENT_KIND,
    MAX_EVENT_BYTES,
    SCHEMA_VERSION,
    THEORY_PHASE,
    KnowledgeEventConflict,
    KnowledgeEventError,
    KnowledgeEventValidationError,
    event_bytes,
    normalize_digest,
    normalize_phase_slug,
    parse_event_bytes,
    seal_event,
    validate_event,
)


def _phase_key(phase_slug: str) -> str:
    return hashlib.sha256(phase_slug.encode("utf-8")).hexdigest()


def event_path(
    project_dir: str | Path,
    stable_id: str,
    phase_slug: str,
    event_id: str,
) -> Path:
    """Return the protected opaque path for one event."""

    phase_slug = normalize_phase_slug(phase_slug)
    event_id = normalize_digest(event_id, label="event_id")
    return (
        project_state.state_dir(project_dir)
        / "knowledge"
        / "branches"
        / knowledge_schema.branch_key(str(stable_id).strip())
        / "events"
        / _phase_key(phase_slug)
        / f"{event_id}.json"
    )


def _plain_existing_directory(
    directory: Path,
    boundary: Path,
    *,
    label: str,
) -> bool:
    root = Path(os.path.abspath(boundary))
    candidate = Path(os.path.abspath(directory))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise KnowledgeEventValidationError(
            f"{label} escaped its protected directory"
        ) from exc
    current = root
    for part in (None, *relative.parts):
        if part is not None:
            current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise KnowledgeEventValidationError(
                f"{label} cannot be inspected: {current}"
            ) from exc
        if (
            metadata_is_link_or_reparse(metadata)
            or not stat.S_ISDIR(metadata.st_mode)
        ):
            raise KnowledgeEventValidationError(
                f"{label} must use only regular directories"
            )
    return True


def _read_path(
    target: Path,
    control: Path,
    *,
    missing_ok: bool,
) -> bytes | None:
    if not _plain_existing_directory(
        target.parent,
        control,
        label="knowledge event directory",
    ):
        if missing_ok:
            return None
        raise KnowledgeEventValidationError(
            "knowledge event directory is missing"
        )
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        if missing_ok:
            return None
        raise KnowledgeEventValidationError(
            "knowledge event file is missing"
        )
    except OSError as exc:
        raise KnowledgeEventValidationError(
            f"knowledge event file cannot be inspected: {target}"
        ) from exc
    if (
        metadata_is_link_or_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise KnowledgeEventValidationError(
            "knowledge event must be a regular file, not a link"
        )
    if metadata.st_size < 1 or metadata.st_size > MAX_EVENT_BYTES:
        raise KnowledgeEventValidationError(
            f"knowledge event must contain 1 to {MAX_EVENT_BYTES} bytes"
        )
    try:
        return project_state.bounded_file_bytes(
            target,
            maximum=MAX_EVENT_BYTES,
            label="knowledge event",
        )
    except project_state.ProjectStateError as exc:
        raise KnowledgeEventValidationError(
            f"knowledge event cannot be read safely: {exc}"
        ) from exc


def _check_location(
    event: Mapping[str, Any],
    *,
    stable_id: str,
    phase_slug: str,
    event_id: str,
) -> None:
    stable_id = str(stable_id).strip()
    if event["phase_slug"] != phase_slug:
        raise KnowledgeEventValidationError(
            "stored event belongs to another phase"
        )
    if event["event_id"] != event_id:
        raise KnowledgeEventValidationError(
            "stored event has an unexpected event ID"
        )
    if event["current_method_identity"]["stable_id"] != stable_id:
        raise KnowledgeEventValidationError(
            "stored event belongs to another method"
        )
    if event["branch_key"] != knowledge_schema.branch_key(stable_id):
        raise KnowledgeEventValidationError(
            "stored event belongs to another branch"
        )


def read_event(
    project_dir: str | Path,
    stable_id: str,
    phase_slug: str,
    event_id: str,
) -> dict[str, Any] | None:
    """Safely read one event, or return null when it is absent."""

    phase_slug = normalize_phase_slug(phase_slug)
    event_id = normalize_digest(event_id, label="event_id")
    control = project_state.state_dir(project_dir)
    target = event_path(
        project_dir, stable_id, phase_slug, event_id
    )
    payload = _read_path(target, control, missing_ok=True)
    if payload is None:
        return None
    event = parse_event_bytes(payload)
    _check_location(
        event,
        stable_id=stable_id,
        phase_slug=phase_slug,
        event_id=event_id,
    )
    return event


def _write_event_unlocked(
    project_dir: str | Path,
    event: Mapping[str, Any],
) -> Path:
    normalized = validate_event(event)
    payload = event_bytes(normalized)
    stable_id = normalized["current_method_identity"]["stable_id"]
    phase_slug = normalized["phase_slug"]
    event_id = normalized["event_id"]
    control = project_state._ensure_control_directory(project_dir)
    target = event_path(
        project_dir, stable_id, phase_slug, event_id
    )
    directory = project_state._ensure_plain_directory_tree(
        target.parent,
        control,
        label="knowledge event directory",
    )

    existing = _read_path(target, control, missing_ok=True)
    if existing is not None:
        if existing == payload:
            project_state._sync_state_directory(target.parent)
            return target
        raise KnowledgeEventConflict(
            "knowledge event path already contains different bytes"
        )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{event_id}.",
        suffix=".tmp",
        dir=directory,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        project_state._ensure_plain_directory_tree(
            directory,
            control,
            label="knowledge event directory",
        )
        try:
            os.link(temporary, target)
        except FileExistsError:
            existing = _read_path(target, control, missing_ok=False)
            if existing != payload:
                raise KnowledgeEventConflict(
                    "knowledge event path already contains different bytes"
                )
        except OSError as exc:
            raise KnowledgeEventValidationError(
                f"knowledge event cannot be created atomically: {exc}"
            ) from exc
        project_state._sync_state_directory(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return target


def write_event(
    project_dir: str | Path,
    event: Mapping[str, Any],
) -> Path:
    """Atomically create one event with exact-byte idempotence."""

    root = Path(project_dir).resolve()
    with project_state._project_lock(root):
        return _write_event_unlocked(root, event)


def _remove_event_unlocked(
    project_dir: str | Path,
    stable_id: str,
    phase_slug: str,
    event_id: str,
    *,
    expected_event_sha256: str,
) -> bool:
    phase_slug = normalize_phase_slug(phase_slug)
    event_id = normalize_digest(event_id, label="event_id")
    expected = normalize_digest(
        expected_event_sha256,
        label="expected_event_sha256",
    )
    control = project_state.state_dir(project_dir)
    target = event_path(
        project_dir, stable_id, phase_slug, event_id
    )
    payload = _read_path(target, control, missing_ok=True)
    if payload is None:
        if _plain_existing_directory(
            target.parent,
            control,
            label="knowledge event directory",
        ):
            project_state._sync_state_directory(target.parent)
        return False
    event = parse_event_bytes(payload)
    _check_location(
        event,
        stable_id=stable_id,
        phase_slug=phase_slug,
        event_id=event_id,
    )
    if not hmac.compare_digest(event["event_sha256"], expected):
        raise KnowledgeEventConflict(
            "event fingerprint does not match the removal request"
        )
    current = _read_path(target, control, missing_ok=False)
    if current != payload:
        raise KnowledgeEventValidationError(
            "knowledge event changed before removal"
        )
    try:
        target.unlink()
    except OSError as exc:
        raise KnowledgeEventValidationError(
            f"knowledge event cannot be removed: {exc}"
        ) from exc
    project_state._sync_state_directory(target.parent)
    return True


def remove_event(
    project_dir: str | Path,
    stable_id: str,
    phase_slug: str,
    event_id: str,
    *,
    expected_event_sha256: str,
) -> bool:
    """Remove one exact event during rollback reconciliation."""

    root = Path(project_dir).resolve()
    with project_state._project_lock(root):
        return _remove_event_unlocked(
            root,
            stable_id,
            phase_slug,
            event_id,
            expected_event_sha256=expected_event_sha256,
        )
