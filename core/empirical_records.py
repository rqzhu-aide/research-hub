"""Cumulative Phase 04 empirical state for one method branch.

Run artifacts remain immutable in their run directories. This module preserves
their cumulative dispositions and promotes a compact current synthesis plus
evidence index. Schema and filesystem validation are isolated in
``core.empirical_schema``.
"""

from __future__ import annotations

from contextlib import nullcontext
import copy
import hashlib
import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping

from core import empirical_schema as schema
from core import knowledge_basis, knowledge_fragments
from core import project_state
from core.filesystem_utils import metadata_is_link_or_reparse


# Public schema names remain available here for existing callers.
INDEX_SCHEMA_VERSION = schema.INDEX_SCHEMA_VERSION
COUNTERPART_INDEX_SCHEMA_VERSION = schema.COUNTERPART_INDEX_SCHEMA_VERSION
INDEX_KIND = schema.INDEX_KIND
SYNTHESIS_FILENAME = schema.SYNTHESIS_FILENAME
INDEX_FILENAME = schema.INDEX_FILENAME
KNOWLEDGE_FILENAME = schema.KNOWLEDGE_FILENAME
EVIDENCE_TYPES = schema.EVIDENCE_TYPES
RUN_SCOPES = schema.RUN_SCOPES
EVIDENCE_STATUSES = schema.EVIDENCE_STATUSES
VERSION_BOUND_TYPES = schema.VERSION_BOUND_TYPES
APPLICABILITY_SCOPES = schema.APPLICABILITY_SCOPES
APPLICABILITY_STATES = schema.APPLICABILITY_STATES
MAX_SYNTHESIS_BYTES = schema.MAX_SYNTHESIS_BYTES
MAX_INDEX_BYTES = schema.MAX_INDEX_BYTES
MAX_KNOWLEDGE_BYTES = knowledge_fragments.MAX_KNOWLEDGE_BYTES

_LEGACY_PROMOTION_TRANSACTION_SCHEMA_VERSION = 1
_KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION = 2
PROMOTION_TRANSACTION_SCHEMA_VERSION = 3
PROMOTION_INTENT_SCHEMA_VERSION = 1
PROMOTION_INTENT_KIND = "method_phase_directory_promotion_intent"
EMPIRICAL_PHASE_SLUG = "04-draft-assembly"
_PROMOTION_TRANSACTION_KEY = "_promotion_transaction"
_BACKUP_PREFIX = ".empirical-package-backup-"

EmpiricalRecordError = schema.EmpiricalRecordError
EmpiricalRecordValidationError = schema.EmpiricalRecordValidationError

_IMMUTABLE_ENTRY_KEYS = (
    "evidence_id",
    "type",
    "path",
    "sha256",
    "size",
    "source_run_id",
    "run_scope",
    "method_dependent",
)


class EmpiricalRecordContinuityError(EmpiricalRecordError):
    """A staged package does not preserve the current evidence record."""


class EmpiricalRecordPromotionError(EmpiricalRecordError):
    """A validated empirical package could not be published safely."""


_NO_EXPECTED_COUNTERPART = object()
_LIVE_CURRENT_SOURCE = object()


def _default_counterpart_basis() -> dict[str, Any]:
    return knowledge_basis.unknown_legacy_basis(
        phase_slug=knowledge_basis.THEORY_PHASE,
    )


def _normalize_counterpart_basis(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return schema.validate_counterpart_basis(
        value if value is not None else _default_counterpart_basis()
    )


def canonical_package_dir(project_dir: str | Path, stable_id: str) -> Path:
    """Return the validated canonical package directory for one method."""

    return schema.canonical_package_dir(project_dir, stable_id)


def _entry_map(index: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(entry["evidence_id"]): entry for entry in index["entries"]}


def _method_changed(
    previous: Mapping[str, Any],
    staged: Mapping[str, Any],
) -> bool:
    return (
        previous["version"] != staged["version"]
        or previous["definition_sha256"] != staged["definition_sha256"]
    )


def _validate_continuity(
    previous: Mapping[str, Any] | None,
    staged: Mapping[str, Any],
    *,
    root: Path,
    staged_dir: Path,
    expected_counterpart_basis: object = _NO_EXPECTED_COUNTERPART,
) -> None:
    if staged.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise EmpiricalRecordContinuityError(
            "a newly staged empirical package must use the current evidence schema"
        )
    if expected_counterpart_basis is not _NO_EXPECTED_COUNTERPART:
        expected_basis = _normalize_counterpart_basis(
            expected_counterpart_basis
        )
        if (
            staged.get("schema_version") != INDEX_SCHEMA_VERSION
            or staged.get("counterpart_basis") != expected_basis
        ):
            raise EmpiricalRecordContinuityError(
                "staged empirical counterpart basis does not match the "
                "prepared run context"
            )

    def require_run_local_path(entry: Mapping[str, Any]) -> None:
        evidence_id = str(entry["evidence_id"])
        _, artifact = schema.normalized_relative_path(
            root,
            entry["path"],
            label=f"evidence {evidence_id!r} path",
        )
        try:
            artifact.relative_to(staged_dir)
        except ValueError as exc:
            raise EmpiricalRecordContinuityError(
                f"new evidence {evidence_id!r} must be stored under the "
                "current Phase 4 run directory"
            ) from exc

    if previous is None:
        if staged["generation"] != 1:
            raise EmpiricalRecordContinuityError(
                "the first empirical package must have generation 1"
            )
        if any(
            entry["source_run_id"] != staged["source_run_id"]
            for entry in staged["entries"]
        ):
            raise EmpiricalRecordContinuityError(
                "every entry in the first empirical package must originate "
                "from its source run"
            )
        for entry in staged["entries"]:
            require_run_local_path(entry)
        return

    if previous["method"]["stable_id"] != staged["method"]["stable_id"]:
        raise EmpiricalRecordContinuityError(
            "a staged package cannot change the method stable_id"
        )
    if staged["generation"] != previous["generation"] + 1:
        raise EmpiricalRecordContinuityError(
            "a staged empirical package must increment generation by exactly one"
        )

    old_entries = _entry_map(previous)
    new_entries = _entry_map(staged)
    omitted = sorted(set(old_entries).difference(new_entries))
    if omitted:
        raise EmpiricalRecordContinuityError(
            "the staged package omits prior evidence IDs: " + ", ".join(omitted)
        )

    for evidence_id, old in old_entries.items():
        new = new_entries[evidence_id]
        changed = [
            field for field in _IMMUTABLE_ENTRY_KEYS if old[field] != new[field]
        ]
        if changed:
            raise EmpiricalRecordContinuityError(
                f"evidence {evidence_id!r} changes immutable fields: "
                + ", ".join(changed)
            )
        if old["status"] != "current" and new["status"] == "current":
            raise EmpiricalRecordContinuityError(
                f"evidence {evidence_id!r} cannot return to current status; "
                "append a new run-local evidence entry for the revalidation "
                "or replacement"
            )
    for evidence_id in set(new_entries).difference(old_entries):
        if new_entries[evidence_id]["source_run_id"] != staged["source_run_id"]:
            raise EmpiricalRecordContinuityError(
                f"new evidence {evidence_id!r} must originate from the "
                "staged package source run"
            )
        require_run_local_path(new_entries[evidence_id])

    if not _method_changed(previous["method"], staged["method"]):
        return
    for evidence_id, old in old_entries.items():
        if (
            old["status"] != "current"
            or not schema.evidence_requires_exact_method(old)
        ):
            continue
        if new_entries[evidence_id]["status"] == "current":
            raise EmpiricalRecordContinuityError(
                f"exact-method evidence {evidence_id!r} cannot remain current "
                "after the method version changes"
            )


def load_current_package(
    project_dir: str | Path,
    stable_id: str,
    *,
    verify_current_artifacts: bool = True,
) -> dict[str, Any] | None:
    """Load and validate one method's current cumulative empirical package."""

    root = schema.project_root(project_dir)
    method_id = schema.text(
        stable_id,
        label="method stable_id",
        maximum=200,
        pattern=schema.METHOD_ID_RE,
    )
    snapshot = schema.read_package(
        root,
        schema.canonical_package_dir(root, method_id),
        expected_stable_id=method_id,
        verify_current_artifacts=verify_current_artifacts,
        required=False,
    )
    return copy.deepcopy(snapshot.index) if snapshot is not None else None


def _staged_and_previous(
    root: Path,
    output_root: str | Path,
    *,
    require_complete_knowledge: bool = True,
    expected_counterpart_basis: object = _NO_EXPECTED_COUNTERPART,
) -> tuple[Path, schema.PackageSnapshot, Path, schema.PackageSnapshot | None]:
    staged_dir = schema.safe_project_path(
        root, output_root, label="Phase 04 output directory"
    )
    staged = schema.read_package(
        root,
        staged_dir,
        expected_stable_id=None,
        verify_current_artifacts=True,
        required=True,
        require_knowledge=True,
        require_complete_knowledge=require_complete_knowledge,
    )
    assert staged is not None
    stable_id = str(staged.index["method"]["stable_id"])
    current_dir = schema.canonical_package_dir(root, stable_id)
    if staged_dir == current_dir:
        schema.fail(
            "the Phase 04 output directory must differ from the canonical package"
        )
    previous = schema.read_package(
        root,
        current_dir,
        expected_stable_id=stable_id,
        verify_current_artifacts=True,
        required=False,
    )
    _validate_continuity(
        previous.index if previous is not None else None,
        staged.index,
        root=root,
        staged_dir=staged_dir,
        expected_counterpart_basis=expected_counterpart_basis,
    )
    return staged_dir, staged, current_dir, previous


def validate_staged_package(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    require_complete_knowledge: bool = True,
    counterpart_basis: object = _NO_EXPECTED_COUNTERPART,
) -> dict[str, Any]:
    """Validate a staged package and its cumulative continuity."""

    root = schema.project_root(project_dir)
    _, staged, _, _ = _staged_and_previous(
        root,
        output_root,
        require_complete_knowledge=require_complete_knowledge,
        expected_counterpart_basis=counterpart_basis,
    )
    return copy.deepcopy(staged.index)


def reconcile_method_change(
    previous_index: Mapping[str, Any],
    *,
    method_version: str,
    method_definition_sha256: str,
    source_run_id: str,
    synthesis_sha256: str,
    synthesis_size: int,
    counterpart_basis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare prior entries for a changed definition of the same method."""

    if not isinstance(previous_index, Mapping):
        schema.fail("previous evidence index must be an object")
    try:
        previous_method = schema.mapping(
            previous_index["method"], label="previous evidence index method"
        )
        stable_id = schema.text(
            previous_method["stable_id"],
            label="method stable_id",
            maximum=200,
            pattern=schema.METHOD_ID_RE,
        )
        old_version = schema.text(
            previous_method["version"],
            label="previous method version",
            maximum=200,
            pattern=schema.VERSION_RE,
        )
        old_digest = schema.sha256(
            previous_method["definition_sha256"],
            label="previous method definition_sha256",
        )
        generation = schema.integer(
            previous_index["generation"],
            label="previous evidence index generation",
            minimum=1,
            maximum=2_147_483_646,
        )
        raw_entries = previous_index["entries"]
    except KeyError as exc:
        schema.fail(
            f"previous evidence index is missing field {exc.args[0]!r}", exc
        )

    version = schema.text(
        method_version,
        label="method version",
        maximum=200,
        pattern=schema.VERSION_RE,
    )
    digest = schema.sha256(
        method_definition_sha256, label="method definition_sha256"
    )
    run_id = schema.text(
        source_run_id,
        label="source_run_id",
        maximum=200,
        pattern=schema.IDENTIFIER_RE,
    )
    summary_digest = schema.sha256(synthesis_sha256, label="synthesis sha256")
    summary_size = schema.integer(
        synthesis_size,
        label="synthesis size",
        minimum=1,
        maximum=schema.MAX_SYNTHESIS_BYTES,
    )
    basis = _normalize_counterpart_basis(counterpart_basis)
    if version == old_version and digest == old_digest:
        schema.fail(
            "method-change reconciliation requires a revised version or definition"
        )
    if not isinstance(raw_entries, list) or (
        len(raw_entries) > schema.MAX_EVIDENCE_ENTRIES
    ):
        schema.fail("previous evidence index entries are invalid")

    entries: list[dict[str, Any]] = []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            schema.fail("previous evidence entries must be objects")
        entry = copy.deepcopy(dict(raw_entry))
        if (
            entry.get("status") == "current"
            and schema.evidence_requires_exact_method(entry)
        ):
            entry["status"] = "outdated"
            entry["status_reason"] = (
                "This evidence was produced for a previous method version and "
                "must be recomputed or revalidated."
            )
        entries.append(schema.serialized_entry(entry))

    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "kind": INDEX_KIND,
        "method": {
            "stable_id": stable_id,
            "version": version,
            "definition_sha256": digest,
        },
        "generation": generation + 1,
        "source_run_id": run_id,
        "synthesis": {
            "path": SYNTHESIS_FILENAME,
            "sha256": summary_digest,
            "size": summary_size,
        },
        "entries": entries,
        "counterpart_basis": basis,
    }


def _write_prepared_file(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".rollback", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass






def _same_snapshot(
    left: schema.PackageSnapshot | None,
    right: schema.PackageSnapshot | None,
) -> bool:
    if left is None or right is None:
        return left is right
    return (
        left.synthesis_bytes == right.synthesis_bytes
        and left.index_bytes == right.index_bytes
        and left.knowledge_bytes == right.knowledge_bytes
    )


def plan_staged_package_promotion(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    operation_id: str,
    expected_method_identity: Mapping[str, Any],
    lock_held: bool = False,
) -> dict[str, Any]:
    """Plan one deterministic empirical package promotion without mutation."""

    from core import empirical_promotion

    return empirical_promotion.plan_staged_package_promotion(
        project_dir,
        output_root,
        operation_id=operation_id,
        expected_method_identity=expected_method_identity,
        lock_held=lock_held,
    )


def recover_empirical_promotion_intent(
    project_dir: str | Path,
    promotion_intent: Mapping[str, Any],
    *,
    make_current: bool,
    lock_held: bool = False,
) -> dict[str, Any] | None:
    """Converge one deterministic empirical promotion after interruption."""

    from core import empirical_promotion

    return empirical_promotion.recover_empirical_promotion_intent(
        project_dir,
        promotion_intent,
        make_current=make_current,
        lock_held=lock_held,
    )


def promote_staged_package(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    lock_held: bool = False,
    retain_backup: bool = False,
    promotion_intent: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish one complete cumulative package as a directory transaction."""

    if promotion_intent is not None:
        if not retain_backup:
            raise EmpiricalRecordValidationError(
                "promotion_intent requires retain_backup"
            )
        from core import empirical_promotion

        return empirical_promotion.execute_staged_package_promotion(
            project_dir,
            output_root,
            promotion_intent=promotion_intent,
            lock_held=lock_held,
        )

    root = schema.project_root(project_dir)
    lock = nullcontext() if lock_held else project_state._project_lock(root)
    with lock:
        staged_dir, staged, current_dir, previous = _staged_and_previous(
            root,
            output_root,
        )
        try:
            project_state._ensure_plain_directory_tree(
                current_dir.parent,
                root,
                label="canonical empirical package parent directory",
            )
        except project_state.ProjectStateError as exc:
            schema.fail(str(exc), exc)

        prepared = Path(
            tempfile.mkdtemp(
                prefix=".empirical-package-prepared-",
                dir=current_dir.parent,
            )
        )
        backup: Path | None = None
        displaced = current_dir.parent / (
            f".empirical-package-rejected-{uuid.uuid4().hex}"
        )
        backup_created = False
        installed = False
        published: schema.PackageSnapshot | None = None
        try:
            prepared_synthesis = prepared / SYNTHESIS_FILENAME
            prepared_index = prepared / INDEX_FILENAME
            prepared_knowledge = prepared / KNOWLEDGE_FILENAME
            _write_prepared_file(prepared_synthesis, staged.synthesis_bytes)
            _write_prepared_file(prepared_index, staged.index_bytes)
            assert staged.knowledge_bytes is not None
            _write_prepared_file(prepared_knowledge, staged.knowledge_bytes)

            prepared_snapshot = schema.read_package(
                root,
                prepared,
                expected_stable_id=staged.index["method"]["stable_id"],
                verify_current_artifacts=True,
                required=True,
                require_knowledge=True,
            )
            if not _same_snapshot(staged, prepared_snapshot):
                raise EmpiricalRecordPromotionError(
                    "the prepared empirical package failed verification"
                )
            staged_recheck = schema.read_package(
                root,
                staged_dir,
                expected_stable_id=staged.index["method"]["stable_id"],
                verify_current_artifacts=True,
                required=True,
                require_knowledge=True,
            )
            if not _same_snapshot(staged, staged_recheck):
                raise EmpiricalRecordPromotionError(
                    "the staged empirical package changed during promotion"
                )
            current_recheck = schema.read_package(
                root,
                current_dir,
                expected_stable_id=staged.index["method"]["stable_id"],
                verify_current_artifacts=True,
                required=False,
            )
            if not _same_snapshot(previous, current_recheck):
                raise EmpiricalRecordPromotionError(
                    "the current empirical package changed during promotion"
                )

            try:
                if current_dir.exists():
                    backup = current_dir.parent / (
                        f"{_BACKUP_PREFIX}{uuid.uuid4().hex}"
                    )
                    os.replace(current_dir, backup)
                    backup_created = True
                os.replace(prepared, current_dir)
                installed = True
                published = schema.read_package(
                    root,
                    current_dir,
                    expected_stable_id=staged.index["method"]["stable_id"],
                    verify_current_artifacts=True,
                    required=True,
                    require_knowledge=True,
                )
                if not _same_snapshot(staged, published):
                    raise EmpiricalRecordPromotionError(
                        "the published empirical package failed verification"
                    )
            except BaseException as exc:
                rollback_failed = False
                try:
                    if installed and current_dir.exists():
                        os.replace(current_dir, displaced)
                    if backup_created and backup is not None and backup.exists():
                        os.replace(backup, current_dir)
                        backup_created = False
                    if previous is not None:
                        restored = schema.read_package(
                            root,
                            current_dir,
                            expected_stable_id=staged.index["method"]["stable_id"],
                            verify_current_artifacts=True,
                            required=True,
                        )
                        if not _same_snapshot(previous, restored):
                            raise EmpiricalRecordPromotionError(
                                "restored empirical package failed verification"
                            )
                    elif current_dir.exists():
                        raise EmpiricalRecordPromotionError(
                            "failed first promotion left a current package"
                        )
                    if displaced.exists():
                        shutil.rmtree(displaced)
                except BaseException as rollback_exc:
                    rollback_failed = True
                    raise EmpiricalRecordPromotionError(
                        "empirical package promotion failed and rollback also failed"
                    ) from rollback_exc
                finally:
                    if rollback_failed:
                        backup_created = backup is not None and backup.exists()
                if isinstance(exc, EmpiricalRecordError):
                    raise
                raise EmpiricalRecordPromotionError(
                    "empirical package promotion failed; the prior package was restored"
                ) from exc

            if backup_created and not retain_backup and backup is not None:
                try:
                    shutil.rmtree(backup)
                    backup_created = False
                    backup = None
                except OSError:
                    pass
        finally:
            if prepared.exists():
                try:
                    shutil.rmtree(prepared)
                except OSError:
                    pass
            if displaced.exists() and not installed:
                try:
                    shutil.rmtree(displaced)
                except OSError:
                    pass

    assert published is not None
    published_record = _snapshot_record(published)
    result = {
        "schema_version": 1,
        "kind": "empirical_package_promotion",
        "method": copy.deepcopy(staged.index["method"]),
        "generation": staged.index["generation"],
        "source_run_id": staged.index["source_run_id"],
        "current_directory": schema.canonical_relative_dir(
            staged.index["method"]["stable_id"]
        ).as_posix(),
        "previous_generation": (
            previous.index["generation"] if previous is not None else None
        ),
        "knowledge_sha256": published_record["knowledge_sha256"],
        "knowledge_size": published_record["knowledge_size"],
        "counterpart_basis": copy.deepcopy(
            published_record["counterpart_basis"]
        ),
    }
    if retain_backup:
        result[_PROMOTION_TRANSACTION_KEY] = {
            "schema_version": PROMOTION_TRANSACTION_SCHEMA_VERSION,
            "kind": "empirical_promotion_transaction",
            "project_root": str(root),
            "published_path": current_dir.relative_to(root).as_posix(),
            "backup_path": (
                backup.relative_to(root).as_posix()
                if backup is not None and backup.exists()
                else None
            ),
            "previous_snapshot": (
                _snapshot_record(previous) if previous is not None else None
            ),
            "published_snapshot": published_record,
        }
    return result


def _prepare_synthesis(
    previous: schema.PackageSnapshot | None,
    *,
    source_run_id: str,
    run_scope: str,
    method_changed: bool,
) -> bytes:
    scope_label = (
        "preliminary" if run_scope == "preliminary" else "comprehensive"
    )
    lines = [
        "# Empirical synthesis",
        "",
        f"Staging instructions for Phase 4 run `{source_run_id}` "
        f"with {scope_label} scope.",
        "",
        "Replace these instructions with a compact current synthesis. Retain "
        "applicable evidence from earlier runs, identify evidence that is "
        "outdated or unresolved, and state the evidence added by this run.",
    ]
    if method_changed:
        lines.extend([
            "",
            "The method version changed. Prior scientific outputs and method "
            "implementations have been marked outdated. Explicitly reusable "
            "inputs and infrastructure remain available.",
        ])
    if previous is not None:
        prior = previous.synthesis_bytes.decode("utf-8").strip()
        lines.extend(["", "## Previous current synthesis", "", prior])
    return ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def _prepare_method_identity(method_identity: Mapping[str, Any]) -> dict[str, str]:
    identity = schema.mapping(method_identity, label="method identity")
    stable_id = schema.text(
        identity.get("stable_id"),
        label="method stable_id",
        maximum=200,
        pattern=schema.METHOD_ID_RE,
    )
    version = schema.text(
        identity.get("version"),
        label="method version",
        maximum=200,
        pattern=schema.VERSION_RE,
    )
    definition = identity.get("definition_sha256")
    catalog_digest = identity.get("sha256")
    if definition is None:
        definition = catalog_digest
    elif catalog_digest is not None and catalog_digest != definition:
        schema.fail(
            "method identity sha256 and definition_sha256 do not agree"
        )
    return {
        "stable_id": stable_id,
        "version": version,
        "definition_sha256": schema.sha256(
            definition, label="method definition_sha256"
        ),
    }


def _default_evidence_role(entry: Mapping[str, Any]) -> str:
    evidence_type = str(entry["type"])
    if evidence_type == "code":
        return "implementation"
    if evidence_type == "protocol":
        return "protocol"
    if evidence_type in {"log", "report", "other"}:
        return "documentation"
    return "scientific_result"


def _prepare_knowledge_fragment(
    previous: schema.PackageSnapshot | None,
    index: Mapping[str, Any],
) -> dict[str, Any]:
    statements: list[dict[str, Any]] = []
    dependencies: list[dict[str, Any]] = []
    lead_summary = {
        "fundamental_points": [],
        "decision_relevant_changes": [],
        "unresolved_questions": [],
    }
    prior_bindings: dict[str, dict[str, Any]] = {}
    if previous is not None and previous.knowledge_bytes is not None:
        prior = knowledge_fragments.validate_empirical_fragment(
            knowledge_fragments.parse_fragment(
                previous.knowledge_bytes,
                label="current empirical knowledge fragment",
            ),
            previous.index,
        )
        statements = copy.deepcopy(prior["statements"])
        dependencies = copy.deepcopy(prior["dependencies"])
        lead_summary = copy.deepcopy(prior["lead_summary"])
        prior_bindings = {
            str(item["evidence_id"]): copy.deepcopy(item)
            for item in prior["evidence_bindings"]
        }

    bindings: list[dict[str, Any]] = []
    for entry in index["entries"]:
        evidence_id = str(entry["evidence_id"])
        binding = prior_bindings.get(evidence_id)
        if binding is None:
            binding = {
                "evidence_id": evidence_id,
                "evidence_status": entry["status"],
                "role": _default_evidence_role(entry),
                "assessments": [],
            }
        else:
            binding["evidence_status"] = entry["status"]
        bindings.append(binding)

    statements_requiring_reassessment = {
        assessment["statement_id"]
        for binding in bindings
        if binding["evidence_status"] != "current"
        for assessment in binding["assessments"]
    }
    for statement in statements:
        if (
            statement["statement_id"] in statements_requiring_reassessment
            and statement["formulation_state"] == "Current"
        ):
            statement["formulation_state"] = "Proposed"

    draft = {
        "schema_version": knowledge_fragments.SCHEMA_VERSION,
        "kind": knowledge_fragments.EMPIRICAL_KIND,
        "semantics": knowledge_fragments.EMPIRICAL_SEMANTICS,
        "coverage": "draft",
        "method": copy.deepcopy(index["method"]),
        "generation": index["generation"],
        "source_run_id": index["source_run_id"],
        "statements": statements,
        "dependencies": dependencies,
        "evidence_bindings": bindings,
        "lead_summary": lead_summary,
    }
    normalized_index = copy.deepcopy(dict(index))
    normalized_index["entries"] = []
    for entry in index["entries"]:
        normalized_entry = copy.deepcopy(dict(entry))
        normalized_entry.update(schema.derived_entry_applicability(entry))
        normalized_index["entries"].append(normalized_entry)
    return knowledge_fragments.validate_empirical_fragment(
        draft,
        normalized_index,
        require_complete=False,
    )


def prepare_staged_package(
    project_dir: str | Path,
    output_root: str | Path,
    method_identity: Mapping[str, Any],
    source_run_id: str,
    run_scope: str,
    counterpart_basis: Mapping[str, Any] | None = None,
    frozen_current: object = _LIVE_CURRENT_SOURCE,
) -> dict[str, Any]:
    """Seed a Phase 04 run with the current cumulative empirical state.

    A first run receives an empty generation-one index and explicit synthesis
    instructions. A later run retains every indexed artifact. If the selected
    method identity changed, exact-method current evidence is marked outdated
    while explicitly reusable inputs and infrastructure remain current.
    Existing staged files are never overwritten.
    """

    import hashlib
    import json

    root = schema.project_root(project_dir)
    identity = _prepare_method_identity(method_identity)
    run_id = schema.text(
        source_run_id,
        label="source_run_id",
        maximum=200,
        pattern=schema.IDENTIFIER_RE,
    )
    scope = schema.text(run_scope, label="run_scope", maximum=20)
    if scope not in RUN_SCOPES:
        schema.fail("run_scope must be preliminary or comprehensive")
    basis = _normalize_counterpart_basis(counterpart_basis)

    output = schema.safe_project_path(
        root, output_root, label="Phase 04 output directory"
    )
    current_dir = schema.canonical_package_dir(root, identity["stable_id"])
    if output == current_dir:
        schema.fail(
            "the Phase 04 output directory must differ from the canonical package"
        )
    if frozen_current is _LIVE_CURRENT_SOURCE:
        previous = schema.read_package(
            root,
            current_dir,
            expected_stable_id=identity["stable_id"],
            verify_current_artifacts=True,
            required=False,
        )
    elif frozen_current is None:
        previous = None
    elif isinstance(frozen_current, schema.PackageSnapshot):
        try:
            normalized_frozen_index = schema.validate_index(
                root,
                schema.parse_index(
                    frozen_current.index_bytes,
                    label="frozen Phase 4 evidence index",
                ),
                frozen_current.synthesis_bytes,
                expected_stable_id=identity["stable_id"],
                verify_current_artifacts=True,
            )
        except schema.EmpiricalRecordError:
            raise
        if normalized_frozen_index != frozen_current.index:
            schema.fail("frozen Phase 4 package changed after verification")
        if frozen_current.knowledge_bytes is not None:
            knowledge_fragments.validate_empirical_fragment(
                knowledge_fragments.parse_fragment(
                    frozen_current.knowledge_bytes,
                    label="frozen Phase 4 knowledge fragment",
                ),
                normalized_frozen_index,
                require_complete=True,
            )
        previous = frozen_current
    else:
        schema.fail("frozen current empirical source has an invalid structure")
    changed = previous is not None and _method_changed(
        previous.index["method"], identity
    )
    synthesis_bytes = _prepare_synthesis(
        previous,
        source_run_id=run_id,
        run_scope=scope,
        method_changed=changed,
    )
    synthesis = {
        "path": SYNTHESIS_FILENAME,
        "sha256": hashlib.sha256(synthesis_bytes).hexdigest(),
        "size": len(synthesis_bytes),
    }

    if previous is None:
        index: dict[str, Any] = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "kind": INDEX_KIND,
            "method": identity,
            "generation": 1,
            "source_run_id": run_id,
            "synthesis": synthesis,
            "entries": [],
            "counterpart_basis": basis,
        }
    elif changed:
        index = reconcile_method_change(
            previous.index,
            method_version=identity["version"],
            method_definition_sha256=identity["definition_sha256"],
            source_run_id=run_id,
            synthesis_sha256=synthesis["sha256"],
            synthesis_size=synthesis["size"],
            counterpart_basis=basis,
        )
    else:
        index = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "kind": INDEX_KIND,
            "method": identity,
            "generation": previous.index["generation"] + 1,
            "source_run_id": run_id,
            "synthesis": synthesis,
            "entries": [
                schema.serialized_entry(entry)
                for entry in previous.index["entries"]
            ],
            "counterpart_basis": basis,
        }

    knowledge = _prepare_knowledge_fragment(previous, index)

    try:
        project_state._ensure_plain_directory_tree(
            output, root, label="Phase 04 output directory"
        )
    except project_state.ProjectStateError as exc:
        schema.fail(str(exc), exc)
    synthesis_path = schema.safe_project_path(
        root, output / SYNTHESIS_FILENAME, label="staged empirical synthesis"
    )
    index_path = schema.safe_project_path(
        root, output / INDEX_FILENAME, label="staged empirical evidence index"
    )
    knowledge_path = schema.safe_project_path(
        root,
        output / KNOWLEDGE_FILENAME,
        label="staged empirical knowledge fragment",
    )
    if (
        synthesis_path.exists()
        or index_path.exists()
        or knowledge_path.exists()
    ):
        schema.fail(
            "the Phase 04 output already contains a staged empirical package"
        )

    index_bytes = (
        json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    knowledge_bytes = (
        json.dumps(
            knowledge,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    _write_bytes_atomic(synthesis_path, synthesis_bytes)
    try:
        _write_bytes_atomic(index_path, index_bytes)
        _write_bytes_atomic(knowledge_path, knowledge_bytes)
        staged = schema.read_package(
            root,
            output,
            expected_stable_id=identity["stable_id"],
            verify_current_artifacts=True,
            required=True,
            require_knowledge=True,
            require_complete_knowledge=False,
        )
        assert staged is not None
        _validate_continuity(
            previous.index if previous is not None else None,
            staged.index,
            root=root,
            staged_dir=output,
            expected_counterpart_basis=basis,
        )
    except BaseException:
        for path in (knowledge_path, index_path, synthesis_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise
    return copy.deepcopy(index)


def _snapshot_counterpart_basis(
    snapshot: schema.PackageSnapshot,
) -> dict[str, Any]:
    if snapshot.index["schema_version"] in {
        COUNTERPART_INDEX_SCHEMA_VERSION,
        INDEX_SCHEMA_VERSION,
    }:
        return schema.validate_counterpart_basis(
            snapshot.index["counterpart_basis"]
        )
    return _default_counterpart_basis()


def _snapshot_record(
    snapshot: schema.PackageSnapshot,
    *,
    transaction_schema_version: int = PROMOTION_TRANSACTION_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Return compact integrity metadata for one empirical package snapshot."""

    record = {
        "method": copy.deepcopy(snapshot.index["method"]),
        "generation": snapshot.index["generation"],
        "source_run_id": snapshot.index["source_run_id"],
        "synthesis_sha256": hashlib.sha256(
            snapshot.synthesis_bytes
        ).hexdigest(),
        "synthesis_size": len(snapshot.synthesis_bytes),
        "index_sha256": hashlib.sha256(snapshot.index_bytes).hexdigest(),
        "index_size": len(snapshot.index_bytes),
    }
    if transaction_schema_version in {
        _KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION,
        PROMOTION_TRANSACTION_SCHEMA_VERSION,
    }:
        record["knowledge_sha256"] = (
            hashlib.sha256(snapshot.knowledge_bytes).hexdigest()
            if snapshot.knowledge_bytes is not None
            else None
        )
        record["knowledge_size"] = (
            len(snapshot.knowledge_bytes)
            if snapshot.knowledge_bytes is not None
            else None
        )
    elif transaction_schema_version != _LEGACY_PROMOTION_TRANSACTION_SCHEMA_VERSION:
        raise EmpiricalRecordValidationError(
            "empirical transaction schema version is invalid"
        )
    if transaction_schema_version == PROMOTION_TRANSACTION_SCHEMA_VERSION:
        record["counterpart_basis"] = _snapshot_counterpart_basis(snapshot)
    return record


def _normalize_snapshot_record(
    value: Mapping[str, Any],
    *,
    label: str,
    transaction_schema_version: int,
) -> dict[str, Any]:
    base_keys = {
        "method",
        "generation",
        "source_run_id",
        "synthesis_sha256",
        "synthesis_size",
        "index_sha256",
        "index_size",
    }
    if transaction_schema_version == PROMOTION_TRANSACTION_SCHEMA_VERSION:
        expected_keys = base_keys | {
            "knowledge_sha256",
            "knowledge_size",
            "counterpart_basis",
        }
    elif transaction_schema_version == _KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION:
        expected_keys = base_keys | {
            "knowledge_sha256",
            "knowledge_size",
        }
    elif transaction_schema_version == _LEGACY_PROMOTION_TRANSACTION_SCHEMA_VERSION:
        expected_keys = base_keys
    else:
        raise EmpiricalRecordValidationError(f"{label} is invalid")
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise EmpiricalRecordValidationError(f"{label} is invalid")

    method = schema.mapping(value.get("method"), label=f"{label} method")
    schema.exact_keys(method, schema.METHOD_KEYS, label=f"{label} method")
    normalized_method = {
        "stable_id": schema.text(
            method.get("stable_id"),
            label=f"{label} method stable_id",
            maximum=200,
            pattern=schema.METHOD_ID_RE,
        ),
        "version": schema.text(
            method.get("version"),
            label=f"{label} method version",
            maximum=200,
            pattern=schema.VERSION_RE,
        ),
        "definition_sha256": schema.sha256(
            method.get("definition_sha256"),
            label=f"{label} method definition_sha256",
        ),
    }
    normalized = {
        "method": normalized_method,
        "generation": schema.integer(
            value.get("generation"),
            label=f"{label} generation",
            minimum=1,
            maximum=2_147_483_647,
        ),
        "source_run_id": schema.text(
            value.get("source_run_id"),
            label=f"{label} source_run_id",
            maximum=200,
            pattern=schema.IDENTIFIER_RE,
        ),
        "synthesis_sha256": schema.sha256(
            value.get("synthesis_sha256"),
            label=f"{label} synthesis sha256",
        ),
        "synthesis_size": schema.integer(
            value.get("synthesis_size"),
            label=f"{label} synthesis size",
            minimum=1,
            maximum=schema.MAX_SYNTHESIS_BYTES,
        ),
        "index_sha256": schema.sha256(
            value.get("index_sha256"),
            label=f"{label} index sha256",
        ),
        "index_size": schema.integer(
            value.get("index_size"),
            label=f"{label} index size",
            minimum=1,
            maximum=schema.MAX_INDEX_BYTES,
        ),
    }
    if transaction_schema_version in {
        _KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION,
        PROMOTION_TRANSACTION_SCHEMA_VERSION,
    }:
        knowledge_digest = value.get("knowledge_sha256")
        knowledge_size = value.get("knowledge_size")
        if knowledge_digest is None and knowledge_size is None:
            normalized["knowledge_sha256"] = None
            normalized["knowledge_size"] = None
        elif knowledge_digest is None or knowledge_size is None:
            raise EmpiricalRecordValidationError(f"{label} is invalid")
        else:
            normalized["knowledge_sha256"] = schema.sha256(
                knowledge_digest,
                label=f"{label} knowledge sha256",
            )
            normalized["knowledge_size"] = schema.integer(
                knowledge_size,
                label=f"{label} knowledge size",
                minimum=1,
                maximum=MAX_KNOWLEDGE_BYTES,
            )
    if transaction_schema_version == PROMOTION_TRANSACTION_SCHEMA_VERSION:
        normalized["counterpart_basis"] = schema.validate_counterpart_basis(
            value.get("counterpart_basis")
        )
    return normalized


def _snapshot_matches_record(
    snapshot: schema.PackageSnapshot,
    expected: Mapping[str, Any],
) -> bool:
    has_knowledge_digest = "knowledge_sha256" in expected
    has_knowledge_size = "knowledge_size" in expected
    has_counterpart = "counterpart_basis" in expected
    if has_knowledge_digest != has_knowledge_size:
        return False
    if has_counterpart and not has_knowledge_digest:
        return False
    transaction_version = (
        PROMOTION_TRANSACTION_SCHEMA_VERSION
        if has_counterpart
        else _KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION
        if has_knowledge_digest
        else _LEGACY_PROMOTION_TRANSACTION_SCHEMA_VERSION
    )
    if (
        transaction_version == _LEGACY_PROMOTION_TRANSACTION_SCHEMA_VERSION
        and snapshot.knowledge_bytes is not None
    ):
        return False
    return _snapshot_record(
        snapshot,
        transaction_schema_version=transaction_version,
    ) == expected


def _promotion_transaction(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> tuple[
    Path,
    Path,
    Path | None,
    dict[str, Any] | None,
    dict[str, Any],
]:
    """Validate and resolve a retained empirical-promotion transaction."""

    if not isinstance(promotion, Mapping):
        raise EmpiricalRecordValidationError(
            "empirical promotion must be an object"
        )
    transaction = promotion.get(_PROMOTION_TRANSACTION_KEY)
    required = {
        "schema_version",
        "kind",
        "project_root",
        "published_path",
        "backup_path",
        "previous_snapshot",
        "published_snapshot",
    }
    if not isinstance(transaction, Mapping) or set(transaction) != required:
        raise EmpiricalRecordValidationError(
            "empirical promotion has no valid retained transaction"
        )
    transaction_version = transaction.get("schema_version")
    if (
        type(transaction_version) is not int
        or transaction_version
        not in {
            _LEGACY_PROMOTION_TRANSACTION_SCHEMA_VERSION,
            _KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION,
            PROMOTION_TRANSACTION_SCHEMA_VERSION,
        }
        or transaction.get("kind") != "empirical_promotion_transaction"
    ):
        raise EmpiricalRecordValidationError(
            "empirical promotion has no valid retained transaction"
        )

    root = schema.project_root(project_dir)
    if transaction.get("project_root") != str(root):
        raise EmpiricalRecordValidationError(
            "empirical promotion project identity is invalid"
        )
    published = _normalize_snapshot_record(
        transaction.get("published_snapshot"),
        label="published empirical snapshot",
        transaction_schema_version=transaction_version,
    )
    if (
        transaction_version in {
            _KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION,
            PROMOTION_TRANSACTION_SCHEMA_VERSION,
        }
        and published["knowledge_sha256"] is None
    ):
        raise EmpiricalRecordValidationError(
            "published empirical snapshot must bind its knowledge fragment"
        )
    previous_value = transaction.get("previous_snapshot")
    previous = (
        _normalize_snapshot_record(
            previous_value,
            label="previous empirical snapshot",
            transaction_schema_version=transaction_version,
        )
        if previous_value is not None
        else None
    )
    stable_id = published["method"]["stable_id"]
    current_dir = schema.canonical_package_dir(root, stable_id)
    if (
        transaction.get("published_path")
        != current_dir.relative_to(root).as_posix()
    ):
        raise EmpiricalRecordValidationError(
            "empirical promotion path is invalid"
        )
    backup_value = transaction.get("backup_path")
    backup: Path | None = None
    if backup_value is not None:
        if not isinstance(backup_value, str):
            raise EmpiricalRecordValidationError(
                "empirical promotion backup path is invalid"
            )
        backup = schema.safe_project_path(
            root,
            backup_value,
            label="empirical rollback backup",
        )
        if backup.parent != current_dir.parent or not backup.name.startswith(
            _BACKUP_PREFIX
        ):
            raise EmpiricalRecordValidationError(
                "empirical promotion backup path is invalid"
            )
    if (previous is None) != (backup is None):
        raise EmpiricalRecordValidationError(
            "empirical promotion prior-state metadata is inconsistent"
        )
    expected_outer = {
        "schema_version": 1,
        "kind": "empirical_package_promotion",
        "method": copy.deepcopy(published["method"]),
        "generation": published["generation"],
        "source_run_id": published["source_run_id"],
        "current_directory": current_dir.relative_to(root).as_posix(),
        "previous_generation": (
            previous["generation"] if previous is not None else None
        ),
    }
    if transaction_version in {
        _KNOWLEDGE_PROMOTION_TRANSACTION_SCHEMA_VERSION,
        PROMOTION_TRANSACTION_SCHEMA_VERSION,
    }:
        expected_outer["knowledge_sha256"] = published["knowledge_sha256"]
        expected_outer["knowledge_size"] = published["knowledge_size"]
    if transaction_version == PROMOTION_TRANSACTION_SCHEMA_VERSION:
        expected_outer["counterpart_basis"] = published["counterpart_basis"]
    outer = {
        key: value
        for key, value in promotion.items()
        if key != _PROMOTION_TRANSACTION_KEY
    }
    if outer != expected_outer:
        raise EmpiricalRecordValidationError(
            "empirical promotion record changed after publication"
        )
    return root, current_dir, backup, previous, published


def _transaction_path_present(path: Path, *, label: str) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise EmpiricalRecordPromotionError(
            f"{label} cannot be inspected"
        ) from exc
    if metadata_is_link_or_reparse(metadata):
        raise EmpiricalRecordPromotionError(
            f"{label} must not be a symbolic link or reparse point"
        )
    return True


def _verified_transaction_snapshot(
    root: Path,
    directory: Path,
    expected: Mapping[str, Any],
    *,
    label: str,
) -> schema.PackageSnapshot:
    from core import empirical_promotion

    empirical_promotion.verify_exact_snapshot_layout(
        directory,
        expected,
        label=label,
    )
    snapshot = schema.read_package(
        root,
        directory,
        expected_stable_id=expected["method"]["stable_id"],
        verify_current_artifacts=True,
        required=True,
        require_knowledge=expected.get("knowledge_sha256") is not None,
    )
    if snapshot is None or not _snapshot_matches_record(snapshot, expected):
        raise EmpiricalRecordPromotionError(f"{label} changed after promotion")
    return snapshot


def _sync_promotion_parent(directory: Path) -> None:
    try:
        project_state._sync_state_directory(directory)
    except OSError as exc:
        raise EmpiricalRecordPromotionError(
            "empirical promotion directory could not be synchronized"
        ) from exc


def _remove_promotion_backup(backup: Path) -> None:
    try:
        metadata = backup.lstat()
    except FileNotFoundError as exc:
        raise EmpiricalRecordPromotionError(
            "empirical rollback backup is missing"
        ) from exc
    except OSError as exc:
        raise EmpiricalRecordPromotionError(
            "empirical rollback backup cannot be inspected"
        ) from exc
    if (
        metadata_is_link_or_reparse(metadata)
        or not stat.S_ISDIR(metadata.st_mode)
        or not backup.name.startswith(_BACKUP_PREFIX)
    ):
        raise EmpiricalRecordPromotionError(
            "empirical rollback backup path is invalid"
        )
    try:
        shutil.rmtree(backup)
    except OSError as exc:
        raise EmpiricalRecordPromotionError(
            "empirical rollback backup could not be removed"
        ) from exc
    _sync_promotion_parent(backup.parent)


def commit_empirical_package_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Commit a retained empirical promotion after state persistence."""

    root, current_dir, backup, previous, published = _promotion_transaction(
        project_dir, promotion
    )
    _verified_transaction_snapshot(
        root, current_dir, published, label="published empirical package"
    )
    if backup is None:
        return
    if not _transaction_path_present(
        backup,
        label="empirical rollback backup",
    ):
        _sync_promotion_parent(backup.parent)
        return
    _verified_transaction_snapshot(
        root, backup, previous, label="empirical rollback backup"
    )
    _remove_promotion_backup(backup)


def rollback_empirical_package_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Restore the empirical package that preceded a retained promotion."""

    root, current_dir, backup, previous_record, published_record = (
        _promotion_transaction(project_dir, promotion)
    )
    current = schema.read_package(
        root,
        current_dir,
        expected_stable_id=published_record["method"]["stable_id"],
        verify_current_artifacts=True,
        required=False,
    )
    already_restored = (
        current is None and previous_record is None
    ) or (
        current is not None
        and previous_record is not None
        and _snapshot_matches_record(current, previous_record)
    )
    if already_restored:
        if backup is not None and _transaction_path_present(
            backup,
            label="empirical rollback backup",
        ):
            _verified_transaction_snapshot(
                root,
                backup,
                previous_record,
                label="empirical rollback backup",
            )
            _remove_promotion_backup(backup)
        return

    _verified_transaction_snapshot(
        root,
        current_dir,
        published_record,
        label="published empirical package",
    )
    if backup is not None:
        _verified_transaction_snapshot(
            root,
            backup,
            previous_record,
            label="empirical rollback backup",
        )

    displaced = current_dir.parent / (
        f".empirical-package-rejected-{uuid.uuid4().hex}"
    )
    published_displaced = False
    previous_installed = False
    try:
        os.replace(current_dir, displaced)
        published_displaced = True
        if backup is not None:
            os.replace(backup, current_dir)
            previous_installed = True
            restored = schema.read_package(
                root,
                current_dir,
                expected_stable_id=published_record["method"]["stable_id"],
                verify_current_artifacts=True,
                required=True,
            )
            if restored is None or not _snapshot_matches_record(
                restored,
                previous_record,
            ):
                raise EmpiricalRecordPromotionError(
                    "restored empirical package failed verification"
                )
        else:
            restored = schema.read_package(
                root,
                current_dir,
                expected_stable_id=published_record["method"]["stable_id"],
                verify_current_artifacts=True,
                required=False,
            )
            if restored is not None:
                raise EmpiricalRecordPromotionError(
                    "empirical rollback unexpectedly restored a package"
                )
    except BaseException as exc:
        try:
            if previous_installed and backup is not None and current_dir.exists():
                os.replace(current_dir, backup)
                previous_installed = False
            if published_displaced and displaced.exists():
                os.replace(displaced, current_dir)
                published_displaced = False
        except BaseException as recovery_exc:
            raise EmpiricalRecordPromotionError(
                "empirical rollback failed and recovery also failed"
            ) from recovery_exc
        if isinstance(exc, EmpiricalRecordError):
            raise
        raise EmpiricalRecordPromotionError(
            "empirical rollback failed; the published package was restored"
        ) from exc
    finally:
        if displaced.exists() and not published_displaced:
            try:
                shutil.rmtree(displaced)
            except OSError:
                pass

    if displaced.exists():
        try:
            shutil.rmtree(displaced)
        except OSError:
            pass
