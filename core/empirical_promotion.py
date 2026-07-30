"""Deterministic planning and recovery for Phase 4 package promotion."""

from __future__ import annotations

from contextlib import nullcontext
import copy
import hashlib
import json
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Any, Mapping

from core import (
    empirical_records as records,
    empirical_schema as schema,
    knowledge_event_diff,
    knowledge_event_schema,
    project_state,
)
from core.filesystem_utils import metadata_is_link_or_reparse


_OPERATION_RE = re.compile(r"^[0-9a-f]{64}$")
_PREPARED_PREFIX = ".empirical-package-prepared-"
_REJECTED_PREFIX = ".empirical-package-rejected-"
_EXPECTED_PACKAGE_FILES = frozenset({
    records.SYNTHESIS_FILENAME,
    records.INDEX_FILENAME,
    records.KNOWLEDGE_FILENAME,
})
_FILE_LIMITS = {
    records.SYNTHESIS_FILENAME: records.MAX_SYNTHESIS_BYTES,
    records.INDEX_FILENAME: records.MAX_INDEX_BYTES,
    records.KNOWLEDGE_FILENAME: records.MAX_KNOWLEDGE_BYTES,
}


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _lock(root: Path, lock_held: bool):
    if type(lock_held) is not bool:
        raise records.EmpiricalRecordValidationError(
            "lock_held must be boolean"
        )
    return nullcontext() if lock_held else project_state._project_lock(root)


def _normalize_method_identity(value: Mapping[str, Any]) -> dict[str, str]:
    method = schema.mapping(value, label="expected method identity")
    schema.exact_keys(
        method,
        schema.METHOD_KEYS,
        label="expected method identity",
    )
    return {
        "stable_id": schema.text(
            method.get("stable_id"),
            label="expected method stable_id",
            maximum=200,
            pattern=schema.METHOD_ID_RE,
        ),
        "version": schema.text(
            method.get("version"),
            label="expected method version",
            maximum=200,
            pattern=schema.VERSION_RE,
        ),
        "definition_sha256": schema.sha256(
            method.get("definition_sha256"),
            label="expected method definition_sha256",
        ),
    }


def _operation_for_run(source_run_id: str) -> str:
    identity = f"{records.EMPIRICAL_PHASE_SLUG}\x00{source_run_id}"
    return _digest(identity.encode("utf-8"))


def _operation_token(operation_id: Any) -> tuple[str, str]:
    if (
        type(operation_id) is not str
        or _OPERATION_RE.fullmatch(operation_id) is None
    ):
        raise records.EmpiricalRecordValidationError(
            "promotion operation ID must be a lowercase SHA-256 digest"
        )
    return operation_id, _digest(operation_id.encode("utf-8"))


def _snapshot_payload(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _checkpoint_digest(record: Mapping[str, Any]) -> str:
    has_knowledge = (
        "knowledge_sha256" in record or "knowledge_size" in record
    )
    if "counterpart_basis" in record:
        version = records.PROMOTION_TRANSACTION_SCHEMA_VERSION
    elif has_knowledge:
        version = records._KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION
    else:
        version = records._LEGACY_PROMOTION_TRANSACTION_SCHEMA_VERSION
    normalized = records._normalize_snapshot_record(
        record,
        label="empirical checkpoint snapshot",
        transaction_schema_version=version,
    )
    return _digest(_snapshot_payload(normalized))


def _intent_relative_paths(
    root: Path,
    current_dir: Path,
    operation_sha256: str,
) -> dict[str, str]:
    parent = current_dir.parent
    return {
        "canonical": current_dir.relative_to(root).as_posix(),
        "prepared": (
            parent / f"{_PREPARED_PREFIX}{operation_sha256}"
        ).relative_to(root).as_posix(),
        "backup": (
            parent / f"{records._BACKUP_PREFIX}{operation_sha256}"
        ).relative_to(root).as_posix(),
        "rejected": (
            parent / f"{_REJECTED_PREFIX}{operation_sha256}"
        ).relative_to(root).as_posix(),
    }


def _runtime_paths(
    root: Path,
    intent: Mapping[str, Any],
) -> dict[str, Path]:
    return {
        field: schema.safe_project_path(
            root,
            relative,
            label=f"empirical promotion {field} path",
        )
        for field, relative in intent["paths"].items()
    }


def _intent_paths_are_unused(
    root: Path,
    paths: Mapping[str, str],
) -> None:
    for field in ("prepared", "backup", "rejected"):
        candidate = schema.safe_project_path(
            root,
            paths[field],
            label=f"empirical promotion {field} path",
        )
        try:
            candidate.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise records.EmpiricalRecordValidationError(
                f"empirical promotion {field} path cannot be inspected"
            ) from exc
        raise records.EmpiricalRecordPromotionError(
            f"empirical promotion {field} path is already in use"
        )


def _planned_promotion(
    root: Path,
    current_dir: Path,
    backup_path: str,
    previous: Mapping[str, Any] | None,
    published: Mapping[str, Any],
) -> dict[str, Any]:
    result = {
        "schema_version": 1,
        "kind": "empirical_package_promotion",
        "method": copy.deepcopy(published["method"]),
        "generation": published["generation"],
        "source_run_id": published["source_run_id"],
        "current_directory": current_dir.relative_to(root).as_posix(),
        "previous_generation": (
            previous["generation"] if previous is not None else None
        ),
        "knowledge_sha256": published["knowledge_sha256"],
        "knowledge_size": published["knowledge_size"],
        "counterpart_basis": copy.deepcopy(
            published["counterpart_basis"]
        ),
    }
    result[records._PROMOTION_TRANSACTION_KEY] = {
        "schema_version": records.PROMOTION_TRANSACTION_SCHEMA_VERSION,
        "kind": "empirical_promotion_transaction",
        "project_root": str(root),
        "published_path": current_dir.relative_to(root).as_posix(),
        "backup_path": backup_path if previous is not None else None,
        "previous_snapshot": (
            copy.deepcopy(previous) if previous is not None else None
        ),
        "published_snapshot": copy.deepcopy(published),
    }
    return result


def _build_event(
    previous: schema.PackageSnapshot | None,
    current: schema.PackageSnapshot,
) -> dict[str, Any]:
    if current.knowledge_bytes is None:
        raise records.EmpiricalRecordPromotionError(
            "published empirical snapshot has no knowledge fragment"
        )
    previous_fragment: bytes | None = None
    previous_index: Mapping[str, Any] | None = None
    previous_status = "absent"
    previous_method: Mapping[str, Any] | None = None
    previous_generation: int | None = None
    if previous is not None:
        previous_method = previous.index["method"]
        previous_generation = int(previous.index["generation"])
        if previous.knowledge_bytes is None:
            previous_status = "legacy_unavailable"
        else:
            previous_status = "available"
            previous_fragment = previous.knowledge_bytes
            previous_index = previous.index
    try:
        return knowledge_event_diff.build_event(
            phase_slug=records.EMPIRICAL_PHASE_SLUG,
            previous_fragment_bytes=previous_fragment,
            current_fragment_bytes=current.knowledge_bytes,
            previous_evidence_index=previous_index,
            current_evidence_index=current.index,
            previous_baseline_status=previous_status,
            previous_method_identity=previous_method,
            previous_generation=previous_generation,
        )
    except knowledge_event_schema.KnowledgeEventError as exc:
        raise records.EmpiricalRecordPromotionError(
            f"empirical knowledge event cannot be planned: {exc}"
        ) from exc


def _plan_unlocked(
    root: Path,
    output_root: str | Path,
    *,
    operation_id: str,
    expected_method_identity: Mapping[str, Any],
) -> dict[str, Any]:
    normalized_operation, operation_sha256 = _operation_token(operation_id)
    expected = _normalize_method_identity(expected_method_identity)
    _, staged, current_dir, previous = records._staged_and_previous(
        root,
        output_root,
    )
    if copy.deepcopy(staged.index["method"]) != expected:
        raise records.EmpiricalRecordContinuityError(
            "staged empirical method identity does not match the selected method"
        )
    source_run_id = str(staged.index["source_run_id"])
    if normalized_operation != _operation_for_run(source_run_id):
        raise records.EmpiricalRecordValidationError(
            "promotion operation ID does not match the Phase 4 source run"
        )
    paths = _intent_relative_paths(root, current_dir, operation_sha256)
    _intent_paths_are_unused(root, paths)
    published = records._snapshot_record(staged)
    previous_record = (
        records._snapshot_record(previous) if previous is not None else None
    )
    planned = _planned_promotion(
        root,
        current_dir,
        paths["backup"],
        previous_record,
        published,
    )
    return {
        "schema_version": records.PROMOTION_INTENT_SCHEMA_VERSION,
        "kind": records.PROMOTION_INTENT_KIND,
        "operation_id": normalized_operation,
        "operation_sha256": operation_sha256,
        "phase_slug": records.EMPIRICAL_PHASE_SLUG,
        "source_run_id": source_run_id,
        "method_identity": expected,
        "paths": paths,
        "previous_checkpoint_sha256": (
            _checkpoint_digest(previous_record)
            if previous_record is not None
            else None
        ),
        "published_checkpoint_sha256": _checkpoint_digest(published),
        "planned_promotion": planned,
        "knowledge_event": _build_event(previous, staged),
    }


def plan_staged_package_promotion(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    operation_id: str,
    expected_method_identity: Mapping[str, Any],
    lock_held: bool = False,
) -> dict[str, Any]:
    """Validate and plan a deterministic Phase 4 directory transaction."""

    root = schema.project_root(project_dir)
    with _lock(root, lock_held):
        return _plan_unlocked(
            root,
            output_root,
            operation_id=operation_id,
            expected_method_identity=expected_method_identity,
        )
def _normalize_intent(
    root: Path,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent must be an object"
        )
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
        or value.get("schema_version")
        != records.PROMOTION_INTENT_SCHEMA_VERSION
        or value.get("kind") != records.PROMOTION_INTENT_KIND
        or value.get("phase_slug") != records.EMPIRICAL_PHASE_SLUG
    ):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent has an unsupported structure"
        )
    operation_id, operation_sha256 = _operation_token(
        value.get("operation_id")
    )
    if value.get("operation_sha256") != operation_sha256:
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent operation digest is invalid"
        )
    method = _normalize_method_identity(value.get("method_identity"))
    source_run_id = schema.text(
        value.get("source_run_id"),
        label="empirical promotion source_run_id",
        maximum=200,
        pattern=schema.IDENTIFIER_RE,
    )
    if operation_id != _operation_for_run(source_run_id):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion operation does not match its source run"
        )
    current_dir = records.canonical_package_dir(
        root,
        method["stable_id"],
    )
    expected_paths = _intent_relative_paths(
        root,
        current_dir,
        operation_sha256,
    )
    supplied_paths = value.get("paths")
    if (
        not isinstance(supplied_paths, Mapping)
        or set(supplied_paths) != set(expected_paths)
        or dict(supplied_paths) != expected_paths
    ):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent paths are invalid"
        )
    resolved_paths = {
        field: schema.safe_project_path(
            root,
            relative,
            label=f"empirical promotion {field} path",
        )
        for field, relative in expected_paths.items()
    }
    exact_paths = {
        "canonical": current_dir,
        "prepared": current_dir.parent
        / f"{_PREPARED_PREFIX}{operation_sha256}",
        "backup": current_dir.parent
        / f"{records._BACKUP_PREFIX}{operation_sha256}",
        "rejected": current_dir.parent
        / f"{_REJECTED_PREFIX}{operation_sha256}",
    }
    if any(
        resolved_paths[field] != expected.resolve(strict=False)
        for field, expected in exact_paths.items()
    ):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent paths are invalid"
        )

    planned_value = value.get("planned_promotion")
    (
        _,
        planned_current,
        backup,
        previous,
        published,
    ) = records._promotion_transaction(root, planned_value)
    if (
        planned_current != current_dir
        or published["method"] != method
        or published["source_run_id"] != source_run_id
    ):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent does not match its planned publication"
        )
    expected_backup = (
        resolved_paths["backup"] if previous is not None else None
    )
    if backup != expected_backup:
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent backup path is invalid"
        )
    previous_checkpoint = value.get("previous_checkpoint_sha256")
    if previous is None:
        if previous_checkpoint is not None:
            raise records.EmpiricalRecordValidationError(
                "empirical promotion intent has an unexpected prior checkpoint"
            )
    elif previous_checkpoint != _checkpoint_digest(previous):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent prior checkpoint is invalid"
        )
    published_checkpoint = value.get("published_checkpoint_sha256")
    if published_checkpoint != _checkpoint_digest(published):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion intent published checkpoint is invalid"
        )

    try:
        event = knowledge_event_schema.validate_event(
            value.get("knowledge_event")
        )
    except knowledge_event_schema.KnowledgeEventError as exc:
        raise records.EmpiricalRecordValidationError(
            f"empirical promotion knowledge event is invalid: {exc}"
        ) from exc
    baseline = (
        "absent"
        if previous is None
        else "available"
        if previous.get("knowledge_sha256") is not None
        else "legacy_unavailable"
    )
    previous_digest = (
        previous["knowledge_sha256"]
        if previous is not None
        and previous.get("knowledge_sha256") is not None
        else None
    )
    event_checks = (
        event["phase_slug"] == records.EMPIRICAL_PHASE_SLUG,
        event["previous_baseline_status"] == baseline,
        event["current_method_identity"] == method,
        event["source_run_id"] == source_run_id,
        event["current_generation"] == published["generation"],
        event["current_fragment_sha256"]
        == published["knowledge_sha256"],
        event["previous_method_identity"]
        == (previous["method"] if previous is not None else None),
        event["previous_generation"]
        == (previous["generation"] if previous is not None else None),
        event["previous_fragment_sha256"] == previous_digest,
    )
    if not all(event_checks):
        raise records.EmpiricalRecordValidationError(
            "empirical promotion event does not match its checkpoints"
        )
    if baseline == "legacy_unavailable" and any((
        event["statement_changes"],
        event["dependency_changes"],
        event["evidence_binding_changes"],
    )):
        raise records.EmpiricalRecordValidationError(
            "legacy empirical baseline cannot claim item-level changes"
        )

    return {
        "schema_version": records.PROMOTION_INTENT_SCHEMA_VERSION,
        "kind": records.PROMOTION_INTENT_KIND,
        "operation_id": operation_id,
        "operation_sha256": operation_sha256,
        "phase_slug": records.EMPIRICAL_PHASE_SLUG,
        "source_run_id": source_run_id,
        "method_identity": method,
        "paths": expected_paths,
        "previous_checkpoint_sha256": previous_checkpoint,
        "published_checkpoint_sha256": published_checkpoint,
        "planned_promotion": copy.deepcopy(dict(planned_value)),
        "knowledge_event": event,
    }


def _expected_snapshot_files(
    snapshot_record: Mapping[str, Any],
) -> frozenset[str]:
    names = {
        records.SYNTHESIS_FILENAME,
        records.INDEX_FILENAME,
    }
    if snapshot_record.get("knowledge_sha256") is not None:
        names.add(records.KNOWLEDGE_FILENAME)
    return frozenset(names)


def _safe_operation_layout(
    path: Path,
    *,
    label: str,
) -> frozenset[str]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise records.EmpiricalRecordPromotionError(
            f"{label} cannot be inspected: {path}"
        ) from exc
    if metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(
        metadata.st_mode
    ):
        raise records.EmpiricalRecordPromotionError(
            f"{label} must be a plain directory"
        )
    try:
        entries = list(path.iterdir())
    except OSError as exc:
        raise records.EmpiricalRecordPromotionError(
            f"{label} cannot be inspected"
        ) from exc
    names = frozenset(entry.name for entry in entries)
    if len(entries) != len(names) or not names.issubset(
        _EXPECTED_PACKAGE_FILES
    ):
        raise records.EmpiricalRecordPromotionError(
            f"{label} contains unexpected content"
        )
    for entry in entries:
        try:
            entry_metadata = entry.lstat()
        except OSError as exc:
            raise records.EmpiricalRecordPromotionError(
                f"{label} entry cannot be inspected"
            ) from exc
        if (
            metadata_is_link_or_reparse(entry_metadata)
            or not stat.S_ISREG(entry_metadata.st_mode)
            or entry_metadata.st_size > _FILE_LIMITS[entry.name]
        ):
            raise records.EmpiricalRecordPromotionError(
                f"{label} contains an unsafe entry"
            )
    return names


def verify_exact_snapshot_layout(
    directory: Path,
    expected: Mapping[str, Any],
    *,
    label: str,
) -> None:
    """Require exact plain package entries before destructive cleanup."""

    names = _safe_operation_layout(directory, label=label)
    if names != _expected_snapshot_files(expected):
        raise records.EmpiricalRecordPromotionError(
            f"{label} contains incomplete or unexpected content"
        )


def _package_role(
    root: Path,
    path: Path,
    previous: Mapping[str, Any] | None,
    published: Mapping[str, Any],
    *,
    prepared_path: bool,
    rejected_path: bool,
) -> tuple[str, schema.PackageSnapshot | None]:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return "absent", None
    except OSError as exc:
        raise records.EmpiricalRecordPromotionError(
            f"empirical transaction path cannot be inspected: {path}"
        ) from exc
    if metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(
        metadata.st_mode
    ):
        raise records.EmpiricalRecordPromotionError(
            f"empirical transaction path must be a plain directory: {path}"
        )
    label = (
        "prepared empirical package"
        if prepared_path
        else "rejected empirical package"
        if rejected_path
        else "empirical transaction package"
    )
    names = _safe_operation_layout(path, label=label)
    published_files = _expected_snapshot_files(published)
    previous_files = (
        _expected_snapshot_files(previous)
        if previous is not None
        else None
    )
    if rejected_path and names != published_files:
        return "incomplete_rejected", None
    if not prepared_path and not rejected_path and names not in {
        published_files,
        previous_files,
    }:
        raise records.EmpiricalRecordPromotionError(
            f"empirical transaction package has incomplete content: {path}"
        )
    try:
        snapshot = schema.read_package(
            root,
            path,
            expected_stable_id=published["method"]["stable_id"],
            verify_current_artifacts=True,
            required=True,
        )
    except records.EmpiricalRecordError as exc:
        if prepared_path:
            return "incomplete_prepared", None
        raise records.EmpiricalRecordPromotionError(
            f"empirical transaction package is invalid: {path}"
        ) from exc
    assert snapshot is not None
    if (
        previous is not None
        and names == previous_files
        and records._snapshot_matches_record(snapshot, previous)
    ):
        return "old", snapshot
    if (
        names == published_files
        and records._snapshot_matches_record(snapshot, published)
    ):
        return "new", snapshot
    if prepared_path and names != published_files:
        return "incomplete_prepared", None
    raise records.EmpiricalRecordPromotionError(
        f"empirical transaction package is not an expected checkpoint: {path}"
    )


def _intent_state(
    root: Path,
    intent: Mapping[str, Any],
) -> tuple[
    dict[str, Path],
    tuple[str, str, str, str],
    dict[str, schema.PackageSnapshot | None],
    dict[str, Any] | None,
    dict[str, Any],
]:
    paths = _runtime_paths(root, intent)
    _, _, _, previous, published = records._promotion_transaction(
        root,
        intent["planned_promotion"],
    )
    roles: list[str] = []
    snapshots: dict[str, schema.PackageSnapshot | None] = {}
    for field in ("canonical", "prepared", "backup", "rejected"):
        role, snapshot = _package_role(
            root,
            paths[field],
            previous,
            published,
            prepared_path=field == "prepared",
            rejected_path=field == "rejected",
        )
        roles.append(role)
        snapshots[field] = snapshot
    return paths, tuple(roles), snapshots, previous, published


def _real_event_from_state(
    intent: Mapping[str, Any],
    state: tuple[str, str, str, str],
    snapshots: Mapping[str, schema.PackageSnapshot | None],
    previous: Mapping[str, Any] | None,
) -> bool:
    fields = ("canonical", "prepared", "backup", "rejected")
    new_snapshot = next(
        (
            snapshots[field]
            for field, role in zip(fields, state)
            if role == "new"
        ),
        None,
    )
    if new_snapshot is None:
        return False
    old_snapshot = next(
        (
            snapshots[field]
            for field, role in zip(fields, state)
            if role == "old"
        ),
        None,
    )
    if previous is not None and old_snapshot is None:
        return False
    expected = _build_event(old_snapshot, new_snapshot)
    if expected != intent["knowledge_event"]:
        raise records.EmpiricalRecordPromotionError(
            "empirical promotion event does not match the transaction packages"
        )
    return True


def _path_exists_lstat(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise records.EmpiricalRecordPromotionError(
            f"empirical transaction path cannot be inspected: {path}"
        ) from exc
    return True


def _sync(directory: Path) -> None:
    try:
        project_state._sync_state_directory(directory)
    except OSError as exc:
        raise records.EmpiricalRecordPromotionError(
            "empirical transaction directory could not be synchronized: "
            f"{directory}"
        ) from exc


def _sync_if_present(directory: Path) -> None:
    """Sync a completed recovery parent only when it exists.

    A recovery pass that performed no filesystem mutation may complete for a
    branch whose transaction directory tree was never created (a first
    promotion interrupted before filesystem prepare). There is then nothing
    to make durable, so the sync is skipped.
    """

    if not _path_exists_lstat(directory):
        return
    _sync(directory)


def _replace(source: Path, destination: Path) -> None:
    try:
        os.replace(source, destination)
    except OSError as exc:
        raise records.EmpiricalRecordPromotionError(
            f"empirical transaction move failed: {source}"
        ) from exc
    _sync(destination.parent)


def _remove_known_tree(path: Path) -> None:
    _safe_operation_layout(path, label="empirical transaction package")
    try:
        shutil.rmtree(path)
    except OSError as exc:
        raise records.EmpiricalRecordPromotionError(
            f"empirical transaction package could not be removed: {path}"
        ) from exc
    _sync(path.parent)


def _recover_unlocked(
    root: Path,
    intent_value: Mapping[str, Any],
    *,
    make_current: bool,
) -> dict[str, Any] | None:
    intent = _normalize_intent(root, intent_value)
    for _ in range(8):
        paths, state, snapshots, previous, _ = _intent_state(root, intent)
        canonical, prepared, backup, rejected = (
            paths["canonical"],
            paths["prepared"],
            paths["backup"],
            paths["rejected"],
        )
        has_previous = previous is not None
        has_real_new = _real_event_from_state(
            intent,
            state,
            snapshots,
            previous,
        )
        if make_current:
            completed = (
                ("new", "absent", "old", "absent")
                if has_previous
                else ("new", "absent", "absent", "absent")
            )
            if state == completed:
                _sync_if_present(canonical.parent)
                return copy.deepcopy(intent["planned_promotion"])
            if has_previous and state == (
                "new",
                "absent",
                "absent",
                "absent",
            ):
                _sync_if_present(canonical.parent)
                return copy.deepcopy(intent["planned_promotion"])
            if (
                any(
                    role in {
                        "incomplete_prepared",
                        "incomplete_rejected",
                    }
                    for role in state
                )
                and not has_real_new
            ):
                raise records.EmpiricalRecordPromotionError(
                    "incomplete prepared empirical package cannot be "
                    "recovered forward"
                )
            if has_previous and state == (
                "old", "new", "absent", "absent"
            ):
                _replace(canonical, backup)
                continue
            if has_previous and state == (
                "absent", "new", "old", "absent"
            ):
                _replace(prepared, canonical)
                continue
            if has_previous and state == (
                "absent", "absent", "old", "new"
            ):
                _replace(rejected, canonical)
                continue
            if has_previous and state == (
                "old", "absent", "absent", "new"
            ):
                _replace(canonical, backup)
                continue
            if not has_previous and state == (
                "absent", "new", "absent", "absent"
            ):
                _replace(prepared, canonical)
                continue
            if not has_previous and state == (
                "absent", "absent", "absent", "new"
            ):
                _replace(rejected, canonical)
                continue
        else:
            completed = (
                ("old", "absent", "absent", "absent")
                if has_previous
                else ("absent", "absent", "absent", "absent")
            )
            if state == completed:
                _sync_if_present(canonical.parent)
                return None
            if has_previous and state in {
                ("old", "new", "absent", "absent"),
                (
                    "old",
                    "incomplete_prepared",
                    "absent",
                    "absent",
                ),
            }:
                _remove_known_tree(prepared)
                continue
            if has_previous and state in {
                ("absent", "new", "old", "absent"),
                (
                    "absent",
                    "incomplete_prepared",
                    "old",
                    "absent",
                ),
            }:
                _replace(backup, canonical)
                continue
            if has_previous and state == (
                "new", "absent", "old", "absent"
            ):
                _replace(canonical, rejected)
                continue
            if has_previous and state in {
                ("absent", "absent", "old", "new"),
                (
                    "absent",
                    "absent",
                    "old",
                    "incomplete_rejected",
                ),
            }:
                _replace(backup, canonical)
                continue
            if has_previous and state in {
                ("old", "absent", "absent", "new"),
                (
                    "old",
                    "absent",
                    "absent",
                    "incomplete_rejected",
                ),
            }:
                _remove_known_tree(rejected)
                continue
            if not has_previous and state in {
                ("absent", "new", "absent", "absent"),
                (
                    "absent",
                    "incomplete_prepared",
                    "absent",
                    "absent",
                ),
            }:
                _remove_known_tree(prepared)
                continue
            if not has_previous and state == (
                "new", "absent", "absent", "absent"
            ):
                _replace(canonical, rejected)
                continue
            if not has_previous and state in {
                ("absent", "absent", "absent", "new"),
                (
                    "absent",
                    "absent",
                    "absent",
                    "incomplete_rejected",
                ),
            }:
                _remove_known_tree(rejected)
                continue
        raise records.EmpiricalRecordPromotionError(
            "empirical promotion intent found an ambiguous partial-swap "
            "state: " + ", ".join(state)
        )
    raise records.EmpiricalRecordPromotionError(
        "empirical promotion recovery did not converge"
    )


def execute_staged_package_promotion(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    promotion_intent: Mapping[str, Any],
    lock_held: bool = False,
) -> dict[str, Any]:
    """Execute an exact fresh plan while preserving its rollback backup."""

    root = schema.project_root(project_dir)
    with _lock(root, lock_held):
        intent = _normalize_intent(root, promotion_intent)
        replanned = _plan_unlocked(
            root,
            output_root,
            operation_id=intent["operation_id"],
            expected_method_identity=intent["method_identity"],
        )
        if _normalize_intent(root, replanned) != intent:
            raise records.EmpiricalRecordPromotionError(
                "staged or current empirical package changed after planning"
            )
        _, staged, _, _ = records._staged_and_previous(root, output_root)
        _, _, _, _, planned_snapshot = records._promotion_transaction(
            root,
            intent["planned_promotion"],
        )
        if records._snapshot_record(staged) != planned_snapshot:
            raise records.EmpiricalRecordPromotionError(
                "staged empirical package changed after promotion planning"
            )
        paths = _runtime_paths(root, intent)
        canonical = paths["canonical"]
        prepared = paths["prepared"]
        backup = paths["backup"]
        parent = canonical.parent
        try:
            project_state._ensure_plain_directory_tree(
                parent,
                root,
                label="canonical empirical package parent directory",
            )
        except project_state.ProjectStateError as exc:
            raise records.EmpiricalRecordValidationError(str(exc)) from exc
        _intent_paths_are_unused(root, intent["paths"])
        try:
            prepared.mkdir()
        except OSError as exc:
            raise records.EmpiricalRecordPromotionError(
                "prepared empirical package could not be created"
            ) from exc
        _sync(parent)
        try:
            records._write_prepared_file(
                prepared / records.SYNTHESIS_FILENAME,
                staged.synthesis_bytes,
            )
            records._write_prepared_file(
                prepared / records.INDEX_FILENAME,
                staged.index_bytes,
            )
            assert staged.knowledge_bytes is not None
            records._write_prepared_file(
                prepared / records.KNOWLEDGE_FILENAME,
                staged.knowledge_bytes,
            )
            _sync(prepared)
            _, state, snapshots, previous, _ = _intent_state(root, intent)
            if state[1] != "new":
                raise records.EmpiricalRecordPromotionError(
                    "prepared empirical package failed checkpoint verification"
                )
            _real_event_from_state(intent, state, snapshots, previous)
        except BaseException:
            if _path_exists_lstat(prepared):
                _recover_unlocked(root, intent, make_current=False)
            raise

        try:
            expected_state = (
                ("old", "new", "absent", "absent")
                if intent["previous_checkpoint_sha256"] is not None
                else ("absent", "new", "absent", "absent")
            )
            _, state, _, _, _ = _intent_state(root, intent)
            if state != expected_state:
                raise records.EmpiricalRecordPromotionError(
                    "current empirical package changed after promotion planning"
                )
            if intent["previous_checkpoint_sha256"] is not None:
                _replace(canonical, backup)
            _replace(prepared, canonical)
            _, final_state, snapshots, previous, _ = _intent_state(
                root,
                intent,
            )
            expected_final = (
                ("new", "absent", "old", "absent")
                if previous is not None
                else ("new", "absent", "absent", "absent")
            )
            if final_state != expected_final:
                raise records.EmpiricalRecordPromotionError(
                    "published empirical package failed checkpoint verification"
                )
            _real_event_from_state(
                intent,
                final_state,
                snapshots,
                previous,
            )
        except BaseException:
            _recover_unlocked(root, intent, make_current=False)
            raise
        return copy.deepcopy(intent["planned_promotion"])


def recover_empirical_promotion_intent(
    project_dir: str | Path,
    promotion_intent: Mapping[str, Any],
    *,
    make_current: bool,
    lock_held: bool = False,
) -> dict[str, Any] | None:
    """Converge exact deterministic partial-swap states to old or new."""

    if type(make_current) is not bool:
        raise records.EmpiricalRecordValidationError(
            "make_current must be boolean"
        )
    root = schema.project_root(project_dir)
    with _lock(root, lock_held):
        return _recover_unlocked(
            root,
            promotion_intent,
            make_current=make_current,
        )
