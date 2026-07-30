"""Durable journals for phase-record promotion across process termination.

The phase modules perform atomic filesystem swaps and retain verified rollback
backups. This module records the operation in the control directory so the
state layer can commit or roll it back after a restart.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

from core.filesystem_utils import metadata_is_link_or_reparse


LEGACY_SCHEMA_VERSION = 1
SCHEMA_VERSION = 2
KIND = "phase_record_promotion_journal"
DIRECTORY_NAME = "promotion-journals"
MAX_JOURNAL_BYTES = 16 * 1024 * 1024
MAX_JOURNALS = 32
STATUSES = frozenset({"prepared", "promoted"})
LEGACY_REQUIRED_KEYS = frozenset({
    "schema_version",
    "kind",
    "project_root",
    "phase_slug",
    "run_id",
    "status",
    "promotion",
})
REQUIRED_KEYS = LEGACY_REQUIRED_KEYS | frozenset({
    "operation_id",
    "intent",
})


class PromotionJournalError(ValueError):
    """A promotion journal is unsafe, malformed, or inconsistent."""


def _text(value: Any, label: str, *, maximum: int = 300) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > maximum or "\x00" in normalized:
        raise PromotionJournalError(
            f"{label} must contain between 1 and {maximum} safe characters"
        )
    return normalized


def operation_id(phase_slug: str, run_id: str) -> str:
    """Return the deterministic identity for one phase-run promotion."""

    identity = f"{_text(phase_slug, 'phase slug')}\x00{_text(run_id, 'run ID')}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _plain_directory(path: Path, *, create: bool) -> Path:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PromotionJournalError(
            f"promotion journal directory is unavailable: {path}"
        ) from exc
    if metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise PromotionJournalError(
            "promotion journal directory must be a plain directory"
        )
    return path.resolve()


def journal_directory(control_dir: str | Path, *, create: bool = False) -> Path:
    control = _plain_directory(Path(control_dir), create=create)
    directory = control / DIRECTORY_NAME
    try:
        directory.lstat()
    except FileNotFoundError:
        if not create:
            return directory
    except OSError as exc:
        raise PromotionJournalError(
            f"promotion journal directory is unavailable: {directory}"
        ) from exc
    return _plain_directory(directory, create=create)


def _journal_key(run_id: str) -> str:
    return hashlib.sha256(_text(run_id, "run ID").encode("utf-8")).hexdigest()


def journal_path(control_dir: str | Path, run_id: str) -> Path:
    return journal_directory(control_dir, create=True) / f"{_journal_key(run_id)}.json"


def _validate(
    value: Any,
    *,
    expected_path: Path | None = None,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PromotionJournalError("promotion journal has an unsupported structure")
    schema_version = value.get("schema_version")
    if schema_version == SCHEMA_VERSION:
        required_keys = REQUIRED_KEYS
    elif schema_version == LEGACY_SCHEMA_VERSION:
        required_keys = LEGACY_REQUIRED_KEYS
    else:
        raise PromotionJournalError("promotion journal schema is invalid")
    if set(value) != required_keys:
        raise PromotionJournalError("promotion journal has an unsupported structure")
    if value.get("kind") != KIND:
        raise PromotionJournalError("promotion journal schema is invalid")
    project_root = _text(value.get("project_root"), "project root", maximum=2_000)
    phase_slug = _text(value.get("phase_slug"), "phase slug")
    run_id = _text(value.get("run_id"), "run ID")
    status = str(value.get("status", ""))
    if status not in STATUSES:
        raise PromotionJournalError("promotion journal status is invalid")
    promotion = value.get("promotion")
    if status == "prepared" and promotion is not None:
        raise PromotionJournalError("prepared promotion journal has result metadata")
    if status == "promoted" and not isinstance(promotion, Mapping):
        raise PromotionJournalError("promoted journal has no promotion metadata")

    intent: dict[str, Any] | None = None
    promotion_id: str | None = None
    if schema_version == SCHEMA_VERSION:
        promotion_id = str(value.get("operation_id", ""))
        if promotion_id != operation_id(phase_slug, run_id):
            raise PromotionJournalError(
                "promotion journal operation ID does not match its phase and run"
            )
        raw_intent = value.get("intent")
        if raw_intent is not None and not isinstance(raw_intent, Mapping):
            raise PromotionJournalError("promotion journal intent must be an object")
        if isinstance(raw_intent, Mapping):
            intent = dict(raw_intent)
            if (
                intent.get("operation_id") != promotion_id
                or intent.get("phase_slug") != phase_slug
                or intent.get("source_run_id") != run_id
            ):
                raise PromotionJournalError(
                    "promotion journal intent does not match its phase, "
                    "run, and operation"
                )
            if not isinstance(intent.get("method_identity"), Mapping):
                raise PromotionJournalError(
                    "promotion journal intent has no method identity"
                )
            if not isinstance(intent.get("planned_promotion"), Mapping):
                raise PromotionJournalError(
                    "promotion journal intent has no planned promotion"
                )
            if status == "promoted" and "planned_promotion" in intent:
                if dict(promotion) != dict(intent["planned_promotion"]):
                    raise PromotionJournalError(
                        "recorded promotion does not match the prepared intent"
                    )
    if expected_path is not None and expected_path.name != f"{_journal_key(run_id)}.json":
        raise PromotionJournalError("promotion journal filename does not match its run ID")
    normalized = {
        "schema_version": schema_version,
        "kind": KIND,
        "project_root": project_root,
        "phase_slug": phase_slug,
        "run_id": run_id,
        "status": status,
        "promotion": dict(promotion) if isinstance(promotion, Mapping) else None,
    }
    if schema_version == SCHEMA_VERSION:
        normalized["operation_id"] = promotion_id
        normalized["intent"] = intent
    return normalized


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PromotionJournalError(
                f"promotion journal contains duplicate field {key!r}"
            )
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise PromotionJournalError(
        f"promotion journal contains non-finite JSON number {value!r}"
    )


def _decode_json(payload: bytes) -> Any:
    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_unique_json_object,
        parse_constant=_reject_json_constant,
    )


def _payload(value: Mapping[str, Any]) -> bytes:
    normalized = _validate(value)
    try:
        payload = (
            json.dumps(
                normalized,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PromotionJournalError(
            "promotion metadata is not JSON serializable"
        ) from exc
    if not payload or len(payload) > MAX_JOURNAL_BYTES:
        raise PromotionJournalError(
            f"promotion journal exceeds {MAX_JOURNAL_BYTES:,} bytes"
        )
    return payload


def _sync_directory(directory: Path) -> None:
    """Make a journal-directory entry durable where supported."""

    if os.name == "nt":
        return
    directory_descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _write(path: Path, value: Mapping[str, Any]) -> dict[str, Any]:
    payload = _payload(value)
    directory = _plain_directory(path.parent, create=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=directory
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _sync_directory(directory)
    finally:
        if temporary.exists():
            temporary.unlink()
    return _validate(_decode_json(payload), expected_path=path)


def prepare(
    control_dir: str | Path,
    project_dir: str | Path,
    phase_slug: str,
    run_id: str,
    *,
    intent: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist intent before any canonical phase record is mutated."""

    path = journal_path(control_dir, run_id)
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise PromotionJournalError(
            f"promotion journal path cannot be inspected: {path}"
        ) from exc
    else:
        raise PromotionJournalError(
            f"promotion journal already exists for run {run_id!r}"
        )
    normalized_phase = _text(phase_slug, "phase slug")
    normalized_run = _text(run_id, "run ID")
    return _write(path, {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "project_root": str(Path(project_dir).resolve()),
        "phase_slug": normalized_phase,
        "run_id": normalized_run,
        "operation_id": operation_id(normalized_phase, normalized_run),
        "status": "prepared",
        "intent": dict(intent) if isinstance(intent, Mapping) else intent,
        "promotion": None,
    })

def record_promotion(
    control_dir: str | Path,
    run_id: str,
    promotion: Mapping[str, Any],
) -> dict[str, Any]:
    """Record the retained rollback transaction before state persistence."""

    path = journal_path(control_dir, run_id)
    current = read(path)
    if current["schema_version"] != SCHEMA_VERSION:
        raise PromotionJournalError(
            "legacy prepared promotion journal cannot be advanced automatically"
        )
    if current["status"] != "prepared":
        raise PromotionJournalError("promotion journal is not prepared")
    intent = current.get("intent")
    if isinstance(intent, Mapping) and "planned_promotion" in intent:
        planned = intent["planned_promotion"]
        if not isinstance(planned, Mapping) or dict(promotion) != dict(planned):
            raise PromotionJournalError(
                "recorded promotion does not match the prepared intent"
            )
    current["status"] = "promoted"
    current["promotion"] = dict(promotion)
    return _write(path, current)


def read(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise PromotionJournalError(
            f"promotion journal is unavailable: {candidate}"
        ) from exc
    if metadata_is_link_or_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise PromotionJournalError("promotion journal must be a regular file")
    if metadata.st_size < 1 or metadata.st_size > MAX_JOURNAL_BYTES:
        raise PromotionJournalError("promotion journal size is invalid")
    try:
        value = _decode_json(candidate.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PromotionJournalError("promotion journal is invalid JSON") from exc
    return _validate(value, expected_path=candidate)


def read_all(control_dir: str | Path) -> list[dict[str, Any]]:
    directory = journal_directory(control_dir, create=False)
    try:
        metadata = directory.lstat()
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise PromotionJournalError(
            f"promotion journal directory is unavailable: {directory}"
        ) from exc
    if metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(
        metadata.st_mode
    ):
        raise PromotionJournalError(
            "promotion journal directory must be a plain directory"
        )
    files = sorted(directory.glob("*.json"), key=lambda path: path.name)
    if len(files) > MAX_JOURNALS:
        raise PromotionJournalError("too many unresolved promotion journals")
    return [read(path) for path in files]


def remove(control_dir: str | Path, run_id: str) -> None:
    path = journal_path(control_dir, run_id)
    try:
        path.unlink()
    except FileNotFoundError:
        _sync_directory(path.parent)
        return
    _sync_directory(path.parent)
