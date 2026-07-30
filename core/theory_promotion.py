"""Deterministic planning and recovery for Phase 3 directory promotion."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any, Mapping

from core import (
    knowledge_event_diff,
    knowledge_event_schema,
    knowledge_fragments,
    project_state,
    theory_records as records,
)
from core.filesystem_utils import metadata_is_link_or_reparse


THEORY_FILENAME = records.THEORY_FILENAME
KNOWLEDGE_FILENAME = records.KNOWLEDGE_FILENAME
RECORD_FILENAME = records.RECORD_FILENAME
LEGACY_SCHEMA_VERSION = records.LEGACY_SCHEMA_VERSION
SCHEMA_VERSION = records.SCHEMA_VERSION
PROMOTION_TRANSACTION_SCHEMA_VERSION = (
    records.PROMOTION_TRANSACTION_SCHEMA_VERSION
)
PROMOTION_INTENT_SCHEMA_VERSION = records.PROMOTION_INTENT_SCHEMA_VERSION
PROMOTION_INTENT_KIND = records.PROMOTION_INTENT_KIND
THEORY_PHASE_SLUG = records.THEORY_PHASE_SLUG
_PROMOTION_TRANSACTION_KEY = records._PROMOTION_TRANSACTION_KEY
_MAX_MANUSCRIPT_BYTES = records._MAX_MANUSCRIPT_BYTES
_MAX_RECORD_BYTES = records._MAX_RECORD_BYTES

TheoryRecordError = records.TheoryRecordError
TheoryValidationError = records.TheoryValidationError
TheoryStageChanged = records.TheoryStageChanged
TheoryRecordCorrupt = records.TheoryRecordCorrupt

_sha256 = records._sha256
_text = records._text
normalize_method_identity = records.normalize_method_identity
_project_root = records._project_root
_safe_project_path = records._safe_project_path
staged_theory_path = records.staged_theory_path
staged_knowledge_path = records.staged_knowledge_path
current_theory_directory = records.current_theory_directory
_read_manuscript = records._read_manuscript
_read_fragment = records._read_fragment
_validate_fragment = records._validate_fragment
_normalize_seal = records._normalize_seal
_record_payload = records._record_payload
_remove_internal_tree = records._remove_internal_tree
_verified_current = records._verified_current
_normalize_current_record = records._normalize_current_record
_promotion_transaction = records._promotion_transaction

def _operation_token(operation_id: str) -> tuple[str, str]:
    try:
        normalized = knowledge_event_schema.normalize_digest(
            operation_id,
            label="promotion operation ID",
        )
    except knowledge_event_schema.KnowledgeEventError as exc:
        raise TheoryValidationError(
            "promotion operation ID must be exactly 64 lowercase hex characters"
        ) from exc
    return normalized, normalized


def _checkpoint_digest(record: Mapping[str, Any]) -> str:
    normalized = _normalize_current_record(
        record, label="theory checkpoint record"
    )
    return _sha256(_record_payload(normalized))


def _intent_relative_paths(
    root: Path,
    destination: Path,
    operation_sha256: str,
) -> dict[str, str]:
    parent = destination.parent
    return {
        "canonical": destination.relative_to(root).as_posix(),
        "prepared": (
            parent / f".current-prepared-{operation_sha256}"
        ).relative_to(root).as_posix(),
        "backup": (
            parent / f".current-backup-{operation_sha256}"
        ).relative_to(root).as_posix(),
        "rejected": (
            parent / f".current-rejected-{operation_sha256}"
        ).relative_to(root).as_posix(),
    }


def _intent_paths_are_unused(root: Path, paths: Mapping[str, str]) -> None:
    for field in ("prepared", "backup", "rejected"):
        candidate = _safe_project_path(
            root,
            paths[field],
            label=f"theory promotion {field} path",
        )
        try:
            candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise TheoryValidationError(
                f"theory promotion {field} path cannot be inspected"
            ) from exc
        raise TheoryStageChanged(
            f"theory promotion {field} path is already in use"
        )


def _validated_promotion_candidate(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
    expected_method_identity: Mapping[str, Any],
) -> tuple[
    Path,
    dict[str, Any],
    dict[str, str],
    bytes,
    bytes,
    Path,
    dict[str, Any] | None,
    dict[str, Any],
    bool,
]:
    root = _project_root(project_dir)
    verified_seal = _normalize_seal(seal)
    expected = normalize_method_identity(expected_method_identity)
    if verified_seal["method_identity"] != expected:
        raise TheoryStageChanged(
            "staged theory method identity does not match the selected method"
        )
    staged_payload = _read_manuscript(
        staged_theory_path(root, output_root),
        error_type=TheoryValidationError,
    )
    if (
        len(staged_payload) != verified_seal["manuscript_size"]
        or _sha256(staged_payload) != verified_seal["manuscript_sha256"]
    ):
        raise TheoryStageChanged(
            "staged theory manuscript changed after sealing"
        )
    raw_fragment, fragment_payload = _read_fragment(
        staged_knowledge_path(root, output_root),
        error_type=TheoryValidationError,
    )
    if (
        len(fragment_payload) != verified_seal["knowledge_size"]
        or _sha256(fragment_payload)
        != verified_seal["knowledge_sha256"]
    ):
        raise TheoryStageChanged(
            "staged theory knowledge fragment changed after sealing"
        )

    stable_id = expected["stable_id"]
    destination = current_theory_directory(root, stable_id)
    previous = _verified_current(destination, stable_id)
    no_change = False
    if (
        previous is not None
        and previous["source_run_id"] == verified_seal["source_run_id"]
    ):
        comparable_fields = (
            "method_identity",
            "source_run_id",
            "scientific_outcome",
            "structurally_self_contained",
            "manuscript_sha256",
            "manuscript_size",
            "knowledge_sha256",
            "knowledge_size",
            "counterpart_basis",
        )
        if previous["schema_version"] == SCHEMA_VERSION:
            comparable = {
                key: previous[key] for key in comparable_fields
            }
            sealed = {
                key: verified_seal[key] for key in comparable_fields
            }
            no_change = comparable == sealed
        if not no_change:
            raise TheoryStageChanged(
                "source run already promoted with different theory content"
            )
        generation = int(previous["generation"])
    else:
        generation = (
            1 if previous is None else int(previous["generation"]) + 1
        )
    _validate_fragment(
        raw_fragment,
        method=expected,
        generation=generation,
        source_run_id=verified_seal["source_run_id"],
        require_complete=True,
        error_type=TheoryStageChanged,
    )
    record = (
        dict(previous)
        if no_change
        else {
            **verified_seal,
            "generation": generation,
            "manuscript_file": THEORY_FILENAME,
            "knowledge_file": KNOWLEDGE_FILENAME,
        }
    )
    return (
        root,
        verified_seal,
        expected,
        staged_payload,
        fragment_payload,
        destination,
        previous,
        record,
        no_change,
    )


def _planned_retained_promotion(
    root: Path,
    destination: Path,
    backup_path: str,
    previous: Mapping[str, Any] | None,
    published: Mapping[str, Any],
    *,
    changed: bool,
) -> dict[str, Any]:
    result = dict(published)
    result[_PROMOTION_TRANSACTION_KEY] = {
        "schema_version": PROMOTION_TRANSACTION_SCHEMA_VERSION,
        "kind": "theory_promotion_transaction",
        "project_root": str(root),
        "published_path": destination.relative_to(root).as_posix(),
        "backup_path": (
            backup_path if changed and previous is not None else None
        ),
        "changed": changed,
        "previous_record": (
            dict(previous) if previous is not None else None
        ),
        "published_record": dict(published),
    }
    return result


def _planned_knowledge_event(
    root: Path,
    destination: Path,
    previous: Mapping[str, Any] | None,
    published: Mapping[str, Any],
    current_fragment_payload: bytes,
) -> dict[str, Any]:
    previous_payload: bytes | None = None
    previous_status = "absent"
    previous_method: Mapping[str, Any] | None = None
    previous_generation: int | None = None
    if previous is not None:
        previous_method = previous["method_identity"]
        previous_generation = int(previous["generation"])
        if previous["schema_version"] in records._KNOWLEDGE_SCHEMA_VERSIONS:
            _, previous_payload = _read_fragment(
                destination / KNOWLEDGE_FILENAME,
                error_type=TheoryRecordCorrupt,
            )
            previous_status = "available"
        else:
            previous_status = "legacy_unavailable"
    try:
        return knowledge_event_diff.build_event(
            phase_slug=THEORY_PHASE_SLUG,
            previous_fragment_bytes=previous_payload,
            current_fragment_bytes=current_fragment_payload,
            previous_baseline_status=previous_status,
            previous_method_identity=previous_method,
            previous_generation=previous_generation,
        )
    except knowledge_event_schema.KnowledgeEventError as exc:
        raise TheoryStageChanged(
            f"theory knowledge event cannot be planned: {exc}"
        ) from exc


def plan_staged_theory_promotion(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
    *,
    expected_method_identity: Mapping[str, Any],
    operation_id: str,
) -> dict[str, Any]:
    """Plan and validate a deterministic Phase 3 directory transaction."""

    (
        root,
        verified_seal,
        expected,
        _,
        fragment_payload,
        destination,
        previous,
        published,
        no_change,
    ) = _validated_promotion_candidate(
        project_dir,
        output_root,
        seal,
        expected_method_identity,
    )
    normalized_operation, operation_sha256 = _operation_token(operation_id)
    paths = _intent_relative_paths(
        root, destination, operation_sha256
    )
    _intent_paths_are_unused(root, paths)
    planned_promotion = _planned_retained_promotion(
        root,
        destination,
        paths["backup"],
        previous,
        published,
        changed=not no_change,
    )
    event = (
        None
        if no_change
        else _planned_knowledge_event(
            root,
            destination,
            previous,
            published,
            fragment_payload,
        )
    )
    return {
        "schema_version": PROMOTION_INTENT_SCHEMA_VERSION,
        "kind": PROMOTION_INTENT_KIND,
        "operation_id": normalized_operation,
        "operation_sha256": operation_sha256,
        "phase_slug": THEORY_PHASE_SLUG,
        "source_run_id": verified_seal["source_run_id"],
        "method_identity": expected,
        "paths": paths,
        "previous_checkpoint_sha256": (
            _checkpoint_digest(previous)
            if previous is not None
            else None
        ),
        "published_checkpoint_sha256": _checkpoint_digest(published),
        "planned_promotion": planned_promotion,
        "knowledge_event": event,
    }


def _normalize_promotion_intent(
    project_dir: str | Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TheoryValidationError("theory promotion intent must be an object")
    required = {
        "schema_version",
        "kind",
        "operation_id",
        "operation_sha256",
        "phase_slug",
        "source_run_id",
        "method_identity",
        "paths",
        "previous_checkpoint_sha256",
        "published_checkpoint_sha256",
        "planned_promotion",
        "knowledge_event",
    }
    if (
        set(value) != required
        or value.get("schema_version") != PROMOTION_INTENT_SCHEMA_VERSION
        or value.get("kind") != PROMOTION_INTENT_KIND
        or value.get("phase_slug") != THEORY_PHASE_SLUG
    ):
        raise TheoryValidationError(
            "theory promotion intent has an unsupported structure"
        )
    root = _project_root(project_dir)
    operation_id, operation_sha256 = _operation_token(
        value.get("operation_id")
    )
    if value.get("operation_sha256") != operation_sha256:
        raise TheoryValidationError(
            "theory promotion intent operation digest is invalid"
        )
    method = normalize_method_identity(value.get("method_identity"))
    source_run_id = _text(
        value.get("source_run_id"), "source run ID", maximum=300
    )
    destination = current_theory_directory(root, method["stable_id"])
    expected_paths = _intent_relative_paths(
        root, destination, operation_sha256
    )
    supplied_paths = value.get("paths")
    if (
        not isinstance(supplied_paths, Mapping)
        or set(supplied_paths) != set(expected_paths)
        or dict(supplied_paths) != expected_paths
    ):
        raise TheoryValidationError(
            "theory promotion intent paths are invalid"
        )
    for field, relative in expected_paths.items():
        resolved = _safe_project_path(
            root,
            relative,
            label=f"theory promotion {field} path",
        )
        expected = (
            destination
            if field == "canonical"
            else destination.parent
            / f".current-{field}-{operation_sha256}"
        )
        if resolved != expected.resolve(strict=False):
            raise TheoryValidationError(
                f"theory promotion intent {field} path is invalid"
            )

    planned_value = value.get("planned_promotion")
    destination_from_plan, backup, changed, previous, published = (
        _promotion_transaction(root, planned_value)
    )
    if (
        destination_from_plan != destination
        or published["method_identity"] != method
        or published["source_run_id"] != source_run_id
    ):
        raise TheoryValidationError(
            "theory promotion intent does not match its planned publication"
        )
    expected_backup = (
        _safe_project_path(
            root,
            expected_paths["backup"],
            label="theory promotion backup path",
        )
        if changed and previous is not None
        else None
    )
    if backup != expected_backup:
        raise TheoryValidationError(
            "theory promotion intent backup path is invalid"
        )
    previous_checkpoint = value.get("previous_checkpoint_sha256")
    if previous is None:
        if previous_checkpoint is not None:
            raise TheoryValidationError(
                "theory promotion intent has an unexpected prior checkpoint"
            )
    else:
        expected_previous_checkpoint = _checkpoint_digest(previous)
        if previous_checkpoint != expected_previous_checkpoint:
            raise TheoryValidationError(
                "theory promotion intent prior checkpoint is invalid"
            )
    published_checkpoint = value.get("published_checkpoint_sha256")
    if published_checkpoint != _checkpoint_digest(published):
        raise TheoryValidationError(
            "theory promotion intent published checkpoint is invalid"
        )

    event_value = value.get("knowledge_event")
    event: dict[str, Any] | None
    if not changed:
        if event_value is not None:
            raise TheoryValidationError(
                "no-change theory promotion intent cannot contain an event"
            )
        event = None
    else:
        try:
            event = knowledge_event_schema.validate_event(event_value)
        except knowledge_event_schema.KnowledgeEventError as exc:
            raise TheoryValidationError(
                f"theory promotion knowledge event is invalid: {exc}"
            ) from exc
        expected_baseline = (
            "absent"
            if previous is None
            else "available"
            if previous["schema_version"] in records._KNOWLEDGE_SCHEMA_VERSIONS
            else "legacy_unavailable"
        )
        expected_previous_digest = (
            previous["knowledge_sha256"]
            if previous is not None
            and previous["schema_version"] in records._KNOWLEDGE_SCHEMA_VERSIONS
            else None
        )
        event_checks = (
            event["phase_slug"] == THEORY_PHASE_SLUG,
            event["previous_baseline_status"] == expected_baseline,
            event["current_method_identity"] == method,
            event["source_run_id"] == source_run_id,
            event["current_generation"] == published["generation"],
            event["current_fragment_sha256"]
            == published["knowledge_sha256"],
            event["previous_method_identity"]
            == (
                previous["method_identity"]
                if previous is not None
                else None
            ),
            event["previous_generation"]
            == (
                previous["generation"]
                if previous is not None
                else None
            ),
            event["previous_fragment_sha256"]
            == expected_previous_digest,
        )
        if not all(event_checks):
            raise TheoryValidationError(
                "theory promotion event does not match its checkpoints"
            )
        if expected_baseline == "legacy_unavailable" and any((
            event["statement_changes"],
            event["dependency_changes"],
            event["evidence_binding_changes"],
        )):
            raise TheoryValidationError(
                "legacy theory baseline cannot claim item-level changes"
            )

    planned = dict(planned_value)
    planned[_PROMOTION_TRANSACTION_KEY] = dict(
        planned_value[_PROMOTION_TRANSACTION_KEY]
    )
    return {
        "schema_version": PROMOTION_INTENT_SCHEMA_VERSION,
        "kind": PROMOTION_INTENT_KIND,
        "operation_id": operation_id,
        "operation_sha256": operation_sha256,
        "phase_slug": THEORY_PHASE_SLUG,
        "source_run_id": source_run_id,
        "method_identity": method,
        "paths": expected_paths,
        "previous_checkpoint_sha256": previous_checkpoint,
        "published_checkpoint_sha256": published_checkpoint,
        "planned_promotion": planned,
        "knowledge_event": event,
    }


def _intent_runtime_paths(
    root: Path,
    intent: Mapping[str, Any],
) -> dict[str, Path]:
    return {
        field: _safe_project_path(
            root,
            relative,
            label=f"theory promotion {field} path",
        )
        for field, relative in intent["paths"].items()
    }


def _lstat_package_directory(path: Path, *, label: str) -> os.stat_result | None:
    """Inspect a package path without following a dangling redirect."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise TheoryValidationError(f"{label} cannot be inspected") from exc
    if metadata_is_link_or_reparse(metadata):
        raise TheoryStageChanged(f"{label} must not be a symbolic link or junction")
    if not stat.S_ISDIR(metadata.st_mode):
        raise TheoryStageChanged(f"{label} must be a directory")
    return metadata


def _recognized_incomplete_package(path: Path) -> bool:
    """Recognize only one bounded subset of the planned package files."""

    try:
        directory_metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise TheoryValidationError(
            "theory transaction directory cannot be inspected"
        ) from exc
    if (
        metadata_is_link_or_reparse(directory_metadata)
        or not stat.S_ISDIR(directory_metadata.st_mode)
    ):
        return False
    try:
        entries = list(path.iterdir())
    except OSError as exc:
        raise TheoryValidationError(
            "theory transaction directory cannot be enumerated"
        ) from exc
    expected_limits = {
        THEORY_FILENAME: _MAX_MANUSCRIPT_BYTES,
        KNOWLEDGE_FILENAME: knowledge_fragments.MAX_KNOWLEDGE_BYTES,
        RECORD_FILENAME: _MAX_RECORD_BYTES,
    }
    names = {entry.name for entry in entries}
    if (
        len(names) != len(entries)
        or not names.issubset(expected_limits)
    ):
        return False
    for entry in entries:
        try:
            metadata = entry.lstat()
        except OSError as exc:
            raise TheoryValidationError(
                "theory transaction entry cannot be inspected"
            ) from exc
        if (
            metadata_is_link_or_reparse(metadata)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > expected_limits[entry.name]
        ):
            return False
    return True

def _write_durable_prepared_file(path: Path, payload: bytes) -> None:
    """Create one prepared package file and make its bytes durable."""

    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise TheoryValidationError(
            f"prepared theory file cannot be created: {path.name}"
        ) from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _sync_transaction_parent(parent: Path) -> None:
    """Make one completed transaction-directory mutation durable."""

    project_state._sync_state_directory(parent)


def _create_transaction_directory(path: Path) -> None:
    path.mkdir()
    _sync_transaction_parent(path.parent)


def _replace_transaction_path(source: Path, destination: Path) -> None:
    if source.parent != destination.parent:
        raise TheoryValidationError(
            "theory transaction rename must remain in one directory"
        )
    os.replace(source, destination)
    _sync_transaction_parent(destination.parent)


def _remove_bounded_transaction_tree(path: Path) -> None:
    metadata = _lstat_package_directory(
        path,
        label="theory transaction cleanup path",
    )
    if metadata is None:
        _sync_transaction_parent(path.parent)
        return
    if not _recognized_incomplete_package(path):
        raise TheoryStageChanged(
            "theory transaction cleanup found unexpected entries"
        )
    _remove_internal_tree(path)
    _sync_transaction_parent(path.parent)


def _package_role(
    path: Path,
    stable_id: str,
    previous: Mapping[str, Any] | None,
    published: Mapping[str, Any],
    previous_checkpoint: str | None,
    published_checkpoint: str,
    *,
    allow_bounded_incomplete: bool = False,
) -> str:
    metadata = _lstat_package_directory(
        path,
        label="theory transaction package",
    )
    if metadata is None:
        return "absent"
    try:
        record = _verified_current(path, stable_id)
    except TheoryRecordError:
        if (
            allow_bounded_incomplete
            and _recognized_incomplete_package(path)
        ):
            return "incomplete"
        raise
    if record is None:
        raise TheoryStageChanged(
            "theory transaction package changed during inspection"
        )
    checkpoint = _checkpoint_digest(record)
    if (
        previous is not None
        and record == previous
        and checkpoint == previous_checkpoint
    ):
        return "old"
    if record == published and checkpoint == published_checkpoint:
        return "new"
    raise TheoryStageChanged(
        f"theory transaction package is not an expected checkpoint: {path}"
    )

def _intent_package_state(
    root: Path,
    intent: Mapping[str, Any],
) -> tuple[
    dict[str, Path],
    tuple[str, str, str, str],
    dict[str, Any] | None,
    dict[str, Any],
]:
    paths = _intent_runtime_paths(root, intent)
    _, _, _, previous, published = _promotion_transaction(
        root, intent["planned_promotion"]
    )
    stable_id = published["method_identity"]["stable_id"]
    state = tuple(
        _package_role(
            paths[field],
            stable_id,
            previous,
            published,
            intent["previous_checkpoint_sha256"],
            intent["published_checkpoint_sha256"],
            allow_bounded_incomplete=(field in {"prepared", "rejected"}),
        )
        for field in ("canonical", "prepared", "backup", "rejected")
    )
    return paths, state, previous, published


def execute_theory_promotion_intent(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
    *,
    expected_method_identity: Mapping[str, Any],
    promotion_intent: Mapping[str, Any],
) -> dict[str, Any]:
    root = _project_root(project_dir)
    intent = _normalize_promotion_intent(root, promotion_intent)
    expected = normalize_method_identity(expected_method_identity)
    if expected != intent["method_identity"]:
        raise TheoryStageChanged(
            "promotion intent method does not match the selected method"
        )
    replanned = plan_staged_theory_promotion(
        root,
        output_root,
        seal,
        expected_method_identity=expected,
        operation_id=intent["operation_id"],
    )
    if _normalize_promotion_intent(root, replanned) != intent:
        raise TheoryStageChanged(
            "staged or current theory changed after promotion planning"
        )
    planned_promotion = intent["planned_promotion"]
    _, _, changed, previous, published = _promotion_transaction(
        root, planned_promotion
    )
    if not changed:
        return dict(planned_promotion)

    paths = _intent_runtime_paths(root, intent)
    destination = paths["canonical"]
    prepared = paths["prepared"]
    backup = paths["backup"]
    rejected = paths["rejected"]
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    _intent_paths_are_unused(root, intent["paths"])
    _create_transaction_directory(prepared)
    prepared_verified = False
    try:
        staged_payload = _read_manuscript(
            staged_theory_path(root, output_root),
            error_type=TheoryValidationError,
        )
        _, fragment_payload = _read_fragment(
            staged_knowledge_path(root, output_root),
            error_type=TheoryValidationError,
        )
        if (
            _sha256(staged_payload) != published["manuscript_sha256"]
            or len(staged_payload) != published["manuscript_size"]
            or _sha256(fragment_payload) != published["knowledge_sha256"]
            or len(fragment_payload) != published["knowledge_size"]
        ):
            raise TheoryStageChanged(
                "staged theory changed after promotion planning"
            )
        _write_durable_prepared_file(
            prepared / THEORY_FILENAME,
            staged_payload,
        )
        _write_durable_prepared_file(
            prepared / KNOWLEDGE_FILENAME,
            fragment_payload,
        )
        _write_durable_prepared_file(
            prepared / RECORD_FILENAME,
            _record_payload(published),
        )
        project_state._sync_state_directory(prepared)
        if _package_role(
            prepared,
            published["method_identity"]["stable_id"],
            previous,
            published,
            intent["previous_checkpoint_sha256"],
            intent["published_checkpoint_sha256"],
        ) != "new":
            raise TheoryRecordCorrupt(
                "prepared theory package failed checkpoint verification"
            )
        prepared_verified = True
    except Exception:
        _remove_bounded_transaction_tree(prepared)
        raise

    try:
        current_role = _package_role(
            destination,
            published["method_identity"]["stable_id"],
            previous,
            published,
            intent["previous_checkpoint_sha256"],
            intent["published_checkpoint_sha256"],
        )
        expected_role = "old" if previous is not None else "absent"
        if current_role != expected_role:
            raise TheoryStageChanged(
                "current theory changed after promotion planning"
            )
        if previous is not None:
            _replace_transaction_path(destination, backup)
        _replace_transaction_path(prepared, destination)
        if _package_role(
            destination,
            published["method_identity"]["stable_id"],
            previous,
            published,
            intent["previous_checkpoint_sha256"],
            intent["published_checkpoint_sha256"],
        ) != "new":
            raise TheoryRecordCorrupt(
                "published theory package failed checkpoint verification"
            )
    except BaseException:
        if prepared_verified:
            recover_theory_promotion_intent(
                root, intent, make_current=False
            )
        raise
    if _lstat_package_directory(
        rejected,
        label="theory promotion rejected path",
    ) is not None:
        raise TheoryRecordCorrupt(
            "theory promotion left an unexpected rejected package"
        )
    return dict(planned_promotion)


def recover_theory_promotion_intent(
    project_dir: str | Path,
    promotion_intent: Mapping[str, Any],
    *,
    make_current: bool,
) -> dict[str, Any] | None:
    """Converge exact deterministic partial-swap states to old or new."""

    if type(make_current) is not bool:
        raise TheoryValidationError("make_current must be boolean")
    root = _project_root(project_dir)
    intent = _normalize_promotion_intent(root, promotion_intent)
    _, _, changed, previous, published = _promotion_transaction(
        root, intent["planned_promotion"]
    )
    if not changed:
        paths, state, _, _ = _intent_package_state(root, intent)
        if state != ("new", "absent", "absent", "absent"):
            raise TheoryStageChanged(
                "no-change theory intent has unexpected transaction paths"
            )
        _sync_transaction_parent(paths["canonical"].parent)
        return dict(intent["planned_promotion"]) if make_current else None

    for _ in range(8):
        paths, state, previous, published = _intent_package_state(
            root, intent
        )
        canonical, prepared, backup, rejected = (
            paths["canonical"],
            paths["prepared"],
            paths["backup"],
            paths["rejected"],
        )
        has_previous = previous is not None
        if make_current:
            completed = (
                ("new", "absent", "old", "absent")
                if has_previous
                else ("new", "absent", "absent", "absent")
            )
            if state == completed:
                _sync_transaction_parent(canonical.parent)
                return dict(intent["planned_promotion"])
            if has_previous and state == (
                "new",
                "absent",
                "absent",
                "absent",
            ):
                _sync_transaction_parent(canonical.parent)
                return dict(intent["planned_promotion"])
            if has_previous and state == (
                "old", "new", "absent", "absent"
            ):
                _replace_transaction_path(canonical, backup)
                continue
            if has_previous and state == (
                "absent", "new", "old", "absent"
            ):
                _replace_transaction_path(prepared, canonical)
                continue
            if has_previous and state == (
                "absent", "absent", "old", "new"
            ):
                _replace_transaction_path(rejected, canonical)
                continue
            if has_previous and state == (
                "old", "absent", "absent", "new"
            ):
                _replace_transaction_path(canonical, backup)
                continue
            if not has_previous and state == (
                "absent", "new", "absent", "absent"
            ):
                _replace_transaction_path(prepared, canonical)
                continue
            if not has_previous and state == (
                "absent", "absent", "absent", "new"
            ):
                _replace_transaction_path(rejected, canonical)
                continue
        else:
            completed = (
                ("old", "absent", "absent", "absent")
                if has_previous
                else ("absent", "absent", "absent", "absent")
            )
            if state == completed:
                _sync_transaction_parent(canonical.parent)
                return None
            if has_previous and state == (
                "old", "incomplete", "absent", "absent"
            ):
                _remove_bounded_transaction_tree(prepared)
                continue
            if not has_previous and state == (
                "absent", "incomplete", "absent", "absent"
            ):
                _remove_bounded_transaction_tree(prepared)
                continue
            if has_previous and state == (
                "old", "new", "absent", "absent"
            ):
                _remove_bounded_transaction_tree(prepared)
                continue
            if has_previous and state == (
                "absent", "new", "old", "absent"
            ):
                _replace_transaction_path(backup, canonical)
                continue
            if has_previous and state == (
                "new", "absent", "old", "absent"
            ):
                _replace_transaction_path(canonical, rejected)
                continue
            if has_previous and state == (
                "absent", "absent", "old", "new"
            ):
                _replace_transaction_path(backup, canonical)
                continue
            if has_previous and state in {
                ("old", "absent", "absent", "new"),
                ("old", "absent", "absent", "incomplete"),
            }:
                _remove_bounded_transaction_tree(rejected)
                continue
            if not has_previous and state == (
                "absent", "new", "absent", "absent"
            ):
                _remove_bounded_transaction_tree(prepared)
                continue
            if not has_previous and state == (
                "new", "absent", "absent", "absent"
            ):
                _replace_transaction_path(canonical, rejected)
                continue
            if not has_previous and state in {
                ("absent", "absent", "absent", "new"),
                ("absent", "absent", "absent", "incomplete"),
            }:
                _remove_bounded_transaction_tree(rejected)
                continue
        raise TheoryStageChanged(
            "theory promotion intent found an ambiguous partial-swap state: "
            + ", ".join(state)
        )
    raise TheoryRecordCorrupt(
        "theory promotion recovery did not converge"
    )
