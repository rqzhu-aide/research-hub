"""Current Phase 3 theory packages.

Phase 3 is a replacement workflow.  A successful run publishes one complete
theory manuscript for one stable method branch.  Run directories remain an
audit trail, while this module identifies the compact manuscript that should
be used by default on the next run.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any, Mapping

from core import knowledge_basis, knowledge_fragments

from core.filesystem_utils import metadata_is_link_or_reparse


THEORY_FILENAME = "theory-manuscript.md"
KNOWLEDGE_FILENAME = knowledge_fragments.KNOWLEDGE_FILENAME
RECORD_FILENAME = "record.json"
LEGACY_SCHEMA_VERSION = 1
STRUCTURED_SCHEMA_VERSION = 2
SCHEMA_VERSION = 3
_KNOWLEDGE_SCHEMA_VERSIONS = frozenset({
    STRUCTURED_SCHEMA_VERSION,
    SCHEMA_VERSION,
})
PROMOTION_TRANSACTION_SCHEMA_VERSION = 1
PROMOTION_INTENT_SCHEMA_VERSION = 1
PROMOTION_INTENT_KIND = "method_phase_directory_promotion_intent"
THEORY_PHASE_SLUG = "03-idea-evaluation"
_PROMOTION_TRANSACTION_KEY = "_promotion_transaction"

_MAX_MANUSCRIPT_BYTES = 20 * 1024 * 1024
_MAX_RECORD_BYTES = 256 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9._/+:-]{1,200}$")
_ELIGIBLE_OUTCOMES = frozenset({"Complete", "Partial"})
_LIVE_CURRENT_SOURCE = object()


class TheoryRecordError(ValueError):
    """Base class for Phase 3 record failures."""


class TheoryValidationError(TheoryRecordError):
    """Raised when a manuscript, identity, or record is invalid."""


class TheoryStageChanged(TheoryRecordError):
    """Raised when staged content no longer matches its seal."""


class TheoryRecordCorrupt(TheoryRecordError):
    """Raised when the published package cannot be verified."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any, label: str, *, maximum: int = 200) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > maximum:
        raise TheoryValidationError(
            f"{label} must contain between 1 and {maximum} characters"
        )
    return normalized


def normalize_method_identity(value: Mapping[str, Any]) -> dict[str, str]:
    """Validate and normalize an exact method identity."""

    if not isinstance(value, Mapping):
        raise TheoryValidationError("method identity must be an object")
    required = {"stable_id", "version", "definition_sha256"}
    if set(value) != required:
        raise TheoryValidationError(
            "method identity must contain exactly stable_id, version, and "
            "definition_sha256"
        )
    stable_id = _text(value.get("stable_id"), "method stable ID")
    version = _text(value.get("version"), "method version")
    digest = str(value.get("definition_sha256", "")).strip().lower()
    if not _STABLE_ID_RE.fullmatch(stable_id):
        raise TheoryValidationError("method stable ID contains unsupported characters")
    if not _IDENTITY_RE.fullmatch(version):
        raise TheoryValidationError("method version contains unsupported characters")
    if not _SHA256_RE.fullmatch(digest):
        raise TheoryValidationError(
            "method definition_sha256 must be a lowercase SHA-256 digest"
        )
    return {
        "stable_id": stable_id,
        "version": version,
        "definition_sha256": digest,
    }


def _normalize_counterpart_basis(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        basis = knowledge_basis.validate_basis(value)
    except knowledge_basis.KnowledgeBasisError as exc:
        raise TheoryValidationError(
            f"theory counterpart basis is invalid: {exc}"
        ) from exc
    if basis["phase_slug"] != knowledge_basis.EMPIRICAL_PHASE:
        raise TheoryValidationError(
            "theory counterpart basis must describe Phase 4"
        )
    return basis


def _default_counterpart_basis() -> dict[str, Any]:
    return knowledge_basis.unknown_legacy_basis(
        phase_slug=knowledge_basis.EMPIRICAL_PHASE,
    )


def _project_root(project_dir: str | Path) -> Path:
    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise TheoryValidationError(f"project directory is not a directory: {root}")
    return root


def _safe_project_path(root: Path, value: str | Path, *, label: str) -> Path:
    supplied = Path(value)
    lexical = supplied if supplied.is_absolute() else root / supplied
    lexical = Path(os.path.abspath(lexical))
    try:
        relative = lexical.relative_to(root)
    except ValueError as exc:
        raise TheoryValidationError(f"{label} is outside the project directory") from exc

    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise TheoryValidationError(f"{label} cannot be inspected: {exc}") from exc
        if metadata_is_link_or_reparse(metadata):
            raise TheoryValidationError(
                f"{label} must not contain a symbolic link or junction"
            )
    return lexical.resolve(strict=False)


def staged_theory_path(
    project_dir: str | Path,
    output_root: str | Path,
) -> Path:
    """Return the required Phase 3 staging path within a run output root."""

    root = _project_root(project_dir)
    output = _safe_project_path(root, output_root, label="Phase 3 output directory")
    return output / THEORY_FILENAME


def staged_knowledge_path(
    project_dir: str | Path,
    output_root: str | Path,
) -> Path:
    """Return the required Phase 3 knowledge-fragment staging path."""

    root = _project_root(project_dir)
    output = _safe_project_path(root, output_root, label="Phase 3 output directory")
    return output / KNOWLEDGE_FILENAME


def current_theory_directory(
    project_dir: str | Path,
    stable_id: str,
) -> Path:
    """Return the canonical current-package directory for one method."""

    root = _project_root(project_dir)
    identity = _text(stable_id, "method stable ID")
    if not _STABLE_ID_RE.fullmatch(identity):
        raise TheoryValidationError("method stable ID contains unsupported characters")
    return root / "branches" / identity / "evaluations" / "current"


def _read_manuscript(path: Path, *, error_type: type[TheoryRecordError]) -> bytes:
    try:
        if metadata_is_link_or_reparse(path.lstat()):
            raise error_type("theory manuscript must not be a symbolic link")
        payload = path.read_bytes()
    except FileNotFoundError as exc:
        raise error_type(f"theory manuscript is missing: {path}") from exc
    except OSError as exc:
        raise error_type(f"theory manuscript cannot be read: {exc}") from exc
    if not payload or len(payload) > _MAX_MANUSCRIPT_BYTES:
        raise error_type(
            f"theory manuscript must contain 1 to {_MAX_MANUSCRIPT_BYTES} bytes"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise error_type("theory manuscript must be UTF-8 text") from exc
    if not text.strip():
        raise error_type("theory manuscript must contain scientific content")
    return payload


def _read_fragment(
    path: Path,
    *,
    error_type: type[TheoryRecordError],
) -> tuple[dict[str, Any], bytes]:
    try:
        return knowledge_fragments.read_fragment(
            path, label="Phase 3 knowledge fragment"
        )
    except knowledge_fragments.KnowledgeFragmentError as exc:
        raise error_type(str(exc)) from exc


def _validate_fragment(
    value: Mapping[str, Any],
    *,
    method: Mapping[str, Any],
    generation: int,
    source_run_id: str,
    require_complete: bool,
    error_type: type[TheoryRecordError],
) -> dict[str, Any]:
    try:
        return knowledge_fragments.validate_theory_fragment(
            value,
            expected_method=method,
            expected_generation=generation,
            expected_source_run_id=source_run_id,
            require_complete=require_complete,
        )
    except knowledge_fragments.KnowledgeFragmentError as exc:
        raise error_type(str(exc)) from exc


def _fragment_payload(fragment: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(fragment, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def seal_staged_theory(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    method_identity: Mapping[str, Any],
    source_run_id: str,
    scientific_outcome: str,
    structurally_self_contained: bool = False,
    counterpart_basis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Seal the staged replacement manuscript and complete knowledge fragment."""

    identity = normalize_method_identity(method_identity)
    run_id = _text(source_run_id, "source run ID", maximum=300)
    outcome = str(scientific_outcome).strip()
    if outcome not in _ELIGIBLE_OUTCOMES:
        raise TheoryValidationError(
            "only Complete or self-contained Partial Phase 3 results can be promoted"
        )
    self_contained = bool(structurally_self_contained)
    if outcome == "Partial" and not self_contained:
        raise TheoryValidationError(
            "a Partial Phase 3 result must be structurally self-contained"
        )

    current = load_current_theory(project_dir, identity["stable_id"])
    generation = (
        1
        if current is None
        else int(current["generation"])
        if current["source_run_id"] == run_id
        else int(current["generation"]) + 1
    )
    manuscript = _read_manuscript(
        staged_theory_path(project_dir, output_root),
        error_type=TheoryValidationError,
    )
    raw_fragment, fragment_payload = _read_fragment(
        staged_knowledge_path(project_dir, output_root),
        error_type=TheoryValidationError,
    )
    _validate_fragment(
        raw_fragment,
        method=identity,
        generation=generation,
        source_run_id=run_id,
        require_complete=True,
        error_type=TheoryValidationError,
    )
    basis = _normalize_counterpart_basis(
        counterpart_basis
        if counterpart_basis is not None
        else _default_counterpart_basis()
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "method_identity": identity,
        "source_run_id": run_id,
        "scientific_outcome": outcome,
        "structurally_self_contained": self_contained,
        "manuscript_sha256": _sha256(manuscript),
        "manuscript_size": len(manuscript),
        "knowledge_sha256": _sha256(fragment_payload),
        "knowledge_size": len(fragment_payload),
        "counterpart_basis": basis,
    }


def _normalize_seal(
    value: Mapping[str, Any],
    *,
    allow_legacy: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TheoryValidationError("theory seal must be an object")
    schema_version = value.get("schema_version")
    if type(schema_version) is not int:
        raise TheoryValidationError("theory seal has an unsupported structure")
    base = {
        "schema_version",
        "method_identity",
        "source_run_id",
        "scientific_outcome",
        "structurally_self_contained",
        "manuscript_sha256",
        "manuscript_size",
    }
    if schema_version == SCHEMA_VERSION:
        required = base | {
            "knowledge_sha256",
            "knowledge_size",
            "counterpart_basis",
        }
    elif allow_legacy and schema_version == STRUCTURED_SCHEMA_VERSION:
        required = base | {"knowledge_sha256", "knowledge_size"}
    elif allow_legacy and schema_version == LEGACY_SCHEMA_VERSION:
        required = base
    else:
        raise TheoryValidationError("theory seal has an unsupported structure")
    if set(value) != required:
        raise TheoryValidationError("theory seal has an unsupported structure")

    identity = normalize_method_identity(value["method_identity"])
    run_id = _text(value.get("source_run_id"), "source run ID", maximum=300)
    outcome = str(value.get("scientific_outcome", "")).strip()
    self_contained = value.get("structurally_self_contained")
    digest = str(value.get("manuscript_sha256", "")).strip().lower()
    size = value.get("manuscript_size")
    if outcome not in _ELIGIBLE_OUTCOMES:
        raise TheoryValidationError("theory seal has an ineligible outcome")
    if not isinstance(self_contained, bool):
        raise TheoryValidationError("theory seal self-contained flag must be boolean")
    if outcome == "Partial" and not self_contained:
        raise TheoryValidationError("Partial theory seal is not self-contained")
    if not _SHA256_RE.fullmatch(digest):
        raise TheoryValidationError("theory seal has an invalid manuscript digest")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise TheoryValidationError("theory seal has an invalid manuscript size")
    normalized = {
        "schema_version": schema_version,
        "method_identity": identity,
        "source_run_id": run_id,
        "scientific_outcome": outcome,
        "structurally_self_contained": self_contained,
        "manuscript_sha256": digest,
        "manuscript_size": size,
    }
    if schema_version in _KNOWLEDGE_SCHEMA_VERSIONS:
        knowledge_digest = str(value.get("knowledge_sha256", "")).strip().lower()
        knowledge_size = value.get("knowledge_size")
        if not _SHA256_RE.fullmatch(knowledge_digest):
            raise TheoryValidationError(
                "theory seal has an invalid knowledge digest"
            )
        if (
            not isinstance(knowledge_size, int)
            or isinstance(knowledge_size, bool)
            or knowledge_size < 1
        ):
            raise TheoryValidationError(
                "theory seal has an invalid knowledge size"
            )
        normalized.update({
            "knowledge_sha256": knowledge_digest,
            "knowledge_size": knowledge_size,
        })
    if schema_version == SCHEMA_VERSION:
        normalized["counterpart_basis"] = _normalize_counterpart_basis(
            value.get("counterpart_basis")
        )
    return normalized


def _record_payload(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _remove_internal_tree(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise TheoryRecordCorrupt(
            "internal transaction path cannot be inspected"
        ) from exc
    if metadata_is_link_or_reparse(metadata):
        raise TheoryRecordCorrupt(
            "internal transaction path became a symbolic link or junction"
        )
    if not stat.S_ISDIR(metadata.st_mode):
        raise TheoryRecordCorrupt(
            "internal transaction path must remain a directory"
        )
    shutil.rmtree(path)


def _verified_current(directory: Path, stable_id: str) -> dict[str, Any] | None:
    manuscript_path = directory / THEORY_FILENAME
    record_path = directory / RECORD_FILENAME
    knowledge_path = directory / KNOWLEDGE_FILENAME
    try:
        directory_metadata = directory.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise TheoryRecordCorrupt(
            "current theory directory cannot be inspected"
        ) from exc
    if metadata_is_link_or_reparse(directory_metadata):
        raise TheoryRecordCorrupt(
            "current theory directory is a symbolic link or junction"
        )
    if not stat.S_ISDIR(directory_metadata.st_mode):
        raise TheoryRecordCorrupt("current theory package must be a directory")
    if not manuscript_path.exists() or not record_path.exists():
        raise TheoryRecordCorrupt("current theory package is incomplete")
    try:
        if metadata_is_link_or_reparse(record_path.lstat()):
            raise TheoryRecordCorrupt("current theory record is a symbolic link")
        raw = record_path.read_bytes()
    except OSError as exc:
        raise TheoryRecordCorrupt(
            f"current theory record cannot be read: {exc}"
        ) from exc
    if not raw or len(raw) > _MAX_RECORD_BYTES:
        raise TheoryRecordCorrupt("current theory record has an invalid size")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TheoryRecordCorrupt(
            "current theory record is not valid JSON"
        ) from exc
    if not isinstance(value, Mapping):
        raise TheoryRecordCorrupt("current theory record must be an object")

    schema_version = value.get("schema_version")
    if type(schema_version) is not int:
        raise TheoryRecordCorrupt(
            "current theory record has an unsupported structure"
        )
    base = {
        "schema_version",
        "method_identity",
        "source_run_id",
        "scientific_outcome",
        "structurally_self_contained",
        "generation",
        "manuscript_file",
        "manuscript_sha256",
        "manuscript_size",
    }
    if schema_version == SCHEMA_VERSION:
        required = base | {
            "knowledge_file",
            "knowledge_sha256",
            "knowledge_size",
            "counterpart_basis",
        }
    elif schema_version == STRUCTURED_SCHEMA_VERSION:
        required = base | {
            "knowledge_file",
            "knowledge_sha256",
            "knowledge_size",
        }
    elif schema_version == LEGACY_SCHEMA_VERSION:
        required = base
    else:
        raise TheoryRecordCorrupt(
            "current theory record has an unsupported structure"
        )
    if set(value) != required:
        raise TheoryRecordCorrupt(
            "current theory record has an unsupported structure"
        )
    seal_fields = required - {
        "generation",
        "manuscript_file",
        "knowledge_file",
    }
    try:
        seal = _normalize_seal(
            {key: value[key] for key in seal_fields},
            allow_legacy=True,
        )
    except TheoryValidationError as exc:
        raise TheoryRecordCorrupt(str(exc)) from exc
    if seal["method_identity"]["stable_id"] != stable_id:
        raise TheoryRecordCorrupt(
            "current theory record belongs to another method"
        )
    generation = value.get("generation")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
    ):
        raise TheoryRecordCorrupt(
            "current theory generation must be positive"
        )
    if value.get("manuscript_file") != THEORY_FILENAME:
        raise TheoryRecordCorrupt(
            "current theory record names an unexpected manuscript"
        )
    manuscript = _read_manuscript(
        manuscript_path,
        error_type=TheoryRecordCorrupt,
    )
    if (
        len(manuscript) != seal["manuscript_size"]
        or _sha256(manuscript) != seal["manuscript_sha256"]
    ):
        raise TheoryRecordCorrupt(
            "current theory manuscript does not match its record"
        )

    record = {
        **seal,
        "generation": generation,
        "manuscript_file": THEORY_FILENAME,
    }
    if schema_version in _KNOWLEDGE_SCHEMA_VERSIONS:
        if (
            value.get("knowledge_file") != KNOWLEDGE_FILENAME
            or not knowledge_path.exists()
        ):
            raise TheoryRecordCorrupt(
                "current theory package is missing its knowledge fragment"
            )
        raw_fragment, fragment_payload = _read_fragment(
            knowledge_path,
            error_type=TheoryRecordCorrupt,
        )
        _validate_fragment(
            raw_fragment,
            method=seal["method_identity"],
            generation=generation,
            source_run_id=seal["source_run_id"],
            require_complete=True,
            error_type=TheoryRecordCorrupt,
        )
        if (
            len(fragment_payload) != seal["knowledge_size"]
            or _sha256(fragment_payload) != seal["knowledge_sha256"]
        ):
            raise TheoryRecordCorrupt(
                "current theory knowledge fragment does not match its record"
            )
        record["knowledge_file"] = KNOWLEDGE_FILENAME
    expected_entries = {THEORY_FILENAME, RECORD_FILENAME}
    if schema_version in _KNOWLEDGE_SCHEMA_VERSIONS:
        expected_entries.add(KNOWLEDGE_FILENAME)
    try:
        entries = list(directory.iterdir())
    except OSError as exc:
        raise TheoryRecordCorrupt(
            "current theory package cannot be enumerated"
        ) from exc
    names = {entry.name for entry in entries}
    if len(names) != len(entries) or names != expected_entries:
        raise TheoryRecordCorrupt(
            "current theory package contains unexpected entries"
        )
    for entry in entries:
        try:
            entry_metadata = entry.lstat()
        except OSError as exc:
            raise TheoryRecordCorrupt(
                "current theory package entry cannot be inspected"
            ) from exc
        if metadata_is_link_or_reparse(entry_metadata) or not stat.S_ISREG(
            entry_metadata.st_mode
        ):
            raise TheoryRecordCorrupt(
                "current theory package entries must be regular files"
            )
    return record


def load_current_theory(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, Any] | None:
    """Load and verify the current theory package for one method."""

    directory = current_theory_directory(project_dir, stable_id)
    return _verified_current(directory, str(stable_id).strip())


def _atomic_write_staged_package(
    manuscript_path: Path,
    manuscript_payload: bytes,
    knowledge_path: Path,
    knowledge_payload: bytes,
) -> None:
    """Replace both staged files together or restore their prior bytes."""

    if manuscript_path.parent != knowledge_path.parent:
        raise TheoryValidationError(
            "staged theory files must share one output directory"
        )
    parent = manuscript_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    members = (
        (
            knowledge_path,
            knowledge_payload,
            "staged theory knowledge fragment",
        ),
        (manuscript_path, manuscript_payload, "staged theory manuscript"),
    )
    token = uuid.uuid4().hex
    prepared: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []

    try:
        for target, payload, label in members:
            try:
                metadata = target.lstat()
            except FileNotFoundError:
                metadata = None
            except OSError as exc:
                raise TheoryValidationError(
                    f"{label} cannot be inspected: {exc}"
                ) from exc
            if metadata is not None and (
                metadata_is_link_or_reparse(metadata)
                or not stat.S_ISREG(metadata.st_mode)
            ):
                raise TheoryValidationError(
                    f"{label} must be a regular file, not a link"
                )
            temporary = parent / f".{target.name}.{token}.tmp"
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            prepared.append((target, temporary))

        for target, _temporary in prepared:
            if target.exists():
                backup = parent / f".{target.name}.{token}.backup"
                os.replace(target, backup)
                backups.append((target, backup))
        for target, temporary in prepared:
            os.replace(temporary, target)
            installed.append(target)
    except BaseException:
        for target in reversed(installed):
            if target.exists():
                target.unlink()
        for target, backup in reversed(backups):
            if backup.exists():
                os.replace(backup, target)
        raise
    else:
        for _target, backup in backups:
            if backup.exists():
                backup.unlink()
    finally:
        for _target, temporary in prepared:
            if temporary.exists():
                temporary.unlink()


def _minimal_theory_template(method: Mapping[str, str]) -> bytes:
    text = f"""# Theory Manuscript

Selected method: `{method["stable_id"]}`
Method version: `{method["version"]}`
Method-definition SHA-256: `{method["definition_sha256"]}`

No verified current theory manuscript matches this exact method definition.
Develop a complete replacement manuscript below.

## Statistical formulation

## Assumptions

## Main results

## Proofs

## Limitations and unresolved questions
"""
    return text.encode("utf-8")


def _draft_theory_fragment(
    method: Mapping[str, str],
    *,
    generation: int,
    source_run_id: str,
    prior: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = {
        "schema_version": knowledge_fragments.SCHEMA_VERSION,
        "kind": knowledge_fragments.THEORY_KIND,
        "semantics": knowledge_fragments.THEORY_SEMANTICS,
        "coverage": "draft",
        "method": dict(method),
        "generation": generation,
        "source_run_id": source_run_id,
        "statements": list(prior.get("statements", [])) if prior else [],
        "dependencies": list(prior.get("dependencies", [])) if prior else [],
        "lead_summary": (
            dict(prior["lead_summary"])
            if prior
            else {
                "fundamental_points": [],
                "decision_relevant_changes": [],
                "unresolved_questions": [],
            }
        ),
    }
    return _validate_fragment(
        candidate,
        method=method,
        generation=generation,
        source_run_id=source_run_id,
        require_complete=False,
        error_type=TheoryValidationError,
    )


def prepare_staged_theory(
    project_dir: str | Path,
    output_root: str | Path,
    method_identity: Mapping[str, Any],
    *,
    source_run_id: str | None = None,
    frozen_current: object = _LIVE_CURRENT_SOURCE,
) -> dict[str, Any]:
    """Prepare a replacement manuscript from one verified current source."""

    method = normalize_method_identity(method_identity)
    destination = staged_theory_path(project_dir, output_root)
    knowledge_destination = staged_knowledge_path(project_dir, output_root)
    canonical = current_theory_directory(project_dir, method["stable_id"])
    if destination == canonical / THEORY_FILENAME:
        raise TheoryValidationError(
            "Phase 3 staging directory must differ from the current package"
        )
    run_id = _text(
        source_run_id if source_run_id is not None else Path(output_root).name,
        "source run ID",
        maximum=300,
    )

    frozen_manuscript: bytes | None = None
    frozen_fragment: dict[str, Any] | None = None
    if frozen_current is _LIVE_CURRENT_SOURCE:
        current = load_current_theory(project_dir, method["stable_id"])
    elif frozen_current is None:
        current = None
    else:
        if not isinstance(frozen_current, Mapping) or set(frozen_current) != {
            "record",
            "manuscript_bytes",
            "knowledge_fragment",
        }:
            raise TheoryValidationError(
                "frozen current theory source has an invalid structure"
            )
        raw_record = frozen_current.get("record")
        try:
            current = _normalize_current_record(
                raw_record,
                label="frozen current theory record",
            )
        except TheoryRecordError as exc:
            raise TheoryValidationError(str(exc)) from exc
        frozen_manuscript = frozen_current.get("manuscript_bytes")
        if type(frozen_manuscript) is not bytes or not frozen_manuscript:
            raise TheoryValidationError(
                "frozen current theory manuscript is invalid"
            )
        if (
            len(frozen_manuscript) != current["manuscript_size"]
            or _sha256(frozen_manuscript) != current["manuscript_sha256"]
        ):
            raise TheoryValidationError(
                "frozen current theory manuscript does not match its record"
            )
        raw_fragment = frozen_current.get("knowledge_fragment")
        if current.get("knowledge_file") == KNOWLEDGE_FILENAME:
            try:
                frozen_fragment = _validate_fragment(
                    raw_fragment,
                    method=current["method_identity"],
                    generation=int(current["generation"]),
                    source_run_id=current["source_run_id"],
                    require_complete=True,
                    error_type=TheoryValidationError,
                )
            except TheoryRecordError as exc:
                raise TheoryValidationError(str(exc)) from exc
        elif raw_fragment is not None:
            raise TheoryValidationError(
                "legacy frozen theory record has an unbound knowledge fragment"
            )

    if current is None:
        generation = 1
    elif current["source_run_id"] == run_id:
        generation = int(current["generation"])
    else:
        generation = int(current["generation"]) + 1

    prior_fragment: dict[str, Any] | None = None
    if current is not None and current["method_identity"] == method:
        if frozen_current is _LIVE_CURRENT_SOURCE:
            manuscript = _read_manuscript(
                canonical / THEORY_FILENAME,
                error_type=TheoryRecordCorrupt,
            )
            if current["schema_version"] in _KNOWLEDGE_SCHEMA_VERSIONS:
                raw_prior, _ = _read_fragment(
                    canonical / KNOWLEDGE_FILENAME,
                    error_type=TheoryRecordCorrupt,
                )
                prior_fragment = _validate_fragment(
                    raw_prior,
                    method=method,
                    generation=int(current["generation"]),
                    source_run_id=current["source_run_id"],
                    require_complete=True,
                    error_type=TheoryRecordCorrupt,
                )
        else:
            assert frozen_manuscript is not None
            manuscript = frozen_manuscript
            prior_fragment = frozen_fragment
        source = "current"
        reason = "exact_method_match"
        source_generation: int | None = int(current["generation"])
    else:
        manuscript = _minimal_theory_template(method)
        source = "template"
        reason = "no_current" if current is None else "method_revised"
        source_generation = None

    fragment = _draft_theory_fragment(
        method,
        generation=generation,
        source_run_id=run_id,
        prior=prior_fragment,
    )
    fragment_payload = _fragment_payload(fragment)
    _atomic_write_staged_package(
        destination,
        manuscript,
        knowledge_destination,
        fragment_payload,
    )
    return {
        "path": destination,
        "knowledge_path": knowledge_destination,
        "source": source,
        "reason": reason,
        "method_identity": method,
        "source_generation": source_generation,
        "target_generation": generation,
        "source_run_id": run_id,
        "sha256": _sha256(manuscript),
        "size": len(manuscript),
        "knowledge_sha256": _sha256(fragment_payload),
        "knowledge_size": len(fragment_payload),
    }

def plan_staged_theory_promotion(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
    *,
    expected_method_identity: Mapping[str, Any],
    operation_id: str,
) -> dict[str, Any]:
    """Plan a deterministic Phase 3 directory transaction."""

    from core import theory_promotion

    return theory_promotion.plan_staged_theory_promotion(
        project_dir,
        output_root,
        seal,
        expected_method_identity=expected_method_identity,
        operation_id=operation_id,
    )

def promote_staged_theory(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
    *,
    expected_method_identity: Mapping[str, Any],
    retain_backup: bool = False,
    promotion_intent: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically replace one method's complete current theory package."""

    if promotion_intent is not None:
        if not retain_backup:
            raise TheoryValidationError(
                "promotion_intent requires retain_backup"
            )
        from core import theory_promotion

        return theory_promotion.execute_theory_promotion_intent(
            project_dir,
            output_root,
            seal,
            expected_method_identity=expected_method_identity,
            promotion_intent=promotion_intent,
        )

    root = _project_root(project_dir)
    verified_seal = _normalize_seal(seal)
    expected = normalize_method_identity(expected_method_identity)
    if verified_seal["method_identity"] != expected:
        raise TheoryStageChanged(
            "staged theory method identity does not match the selected method"
        )

    staged_path = staged_theory_path(root, output_root)
    staged_payload = _read_manuscript(
        staged_path,
        error_type=TheoryValidationError,
    )
    if (
        len(staged_payload) != verified_seal["manuscript_size"]
        or _sha256(staged_payload) != verified_seal["manuscript_sha256"]
    ):
        raise TheoryStageChanged(
            "staged theory manuscript changed after sealing"
        )
    raw_fragment, staged_fragment_payload = _read_fragment(
        staged_knowledge_path(root, output_root),
        error_type=TheoryValidationError,
    )
    if (
        len(staged_fragment_payload) != verified_seal["knowledge_size"]
        or _sha256(staged_fragment_payload)
        != verified_seal["knowledge_sha256"]
    ):
        raise TheoryStageChanged(
            "staged theory knowledge fragment changed after sealing"
        )

    stable_id = expected["stable_id"]
    destination = current_theory_directory(root, stable_id)
    previous = _verified_current(destination, stable_id)
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
                key: previous[key]
                for key in comparable_fields
            }
            expected_comparable = {
                key: verified_seal[key]
                for key in comparable_fields
            }
            if comparable == expected_comparable:
                _validate_fragment(
                    raw_fragment,
                    method=expected,
                    generation=int(previous["generation"]),
                    source_run_id=verified_seal["source_run_id"],
                    require_complete=True,
                    error_type=TheoryStageChanged,
                )
                result = dict(previous)
                if retain_backup:
                    result[_PROMOTION_TRANSACTION_KEY] = {
                        "schema_version": PROMOTION_TRANSACTION_SCHEMA_VERSION,
                        "kind": "theory_promotion_transaction",
                        "project_root": str(root),
                        "published_path": destination.relative_to(root).as_posix(),
                        "backup_path": None,
                        "changed": False,
                        "previous_record": dict(previous),
                        "published_record": dict(previous),
                    }
                return result
        raise TheoryStageChanged(
            "source run already promoted with different theory content"
        )

    generation = 1 if previous is None else int(previous["generation"]) + 1
    _validate_fragment(
        raw_fragment,
        method=expected,
        generation=generation,
        source_run_id=verified_seal["source_run_id"],
        require_complete=True,
        error_type=TheoryStageChanged,
    )
    record = {
        **verified_seal,
        "generation": generation,
        "manuscript_file": THEORY_FILENAME,
        "knowledge_file": KNOWLEDGE_FILENAME,
    }

    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    prepared = parent / f".current-prepared-{uuid.uuid4().hex}"
    backup = parent / f".current-backup-{uuid.uuid4().hex}"
    displaced_new = parent / f".current-rejected-{uuid.uuid4().hex}"
    prepared.mkdir()
    backup_created = False
    installed = False
    try:
        (prepared / THEORY_FILENAME).write_bytes(staged_payload)
        (prepared / KNOWLEDGE_FILENAME).write_bytes(staged_fragment_payload)
        (prepared / RECORD_FILENAME).write_bytes(_record_payload(record))
        if _verified_current(prepared, stable_id) != record:
            raise TheoryRecordCorrupt(
                "prepared theory package failed verification"
            )

        if destination.exists():
            os.replace(destination, backup)
            backup_created = True
        try:
            os.replace(prepared, destination)
            installed = True
            published = _verified_current(destination, stable_id)
            if published != record:
                raise TheoryRecordCorrupt(
                    "published theory package failed verification"
                )
        except BaseException:
            if destination.exists():
                os.replace(destination, displaced_new)
            if backup_created:
                os.replace(backup, destination)
                backup_created = False
            if displaced_new.exists():
                _remove_internal_tree(displaced_new)
            raise
        if backup_created and not retain_backup:
            _remove_internal_tree(backup)
            backup_created = False
        result = dict(record)
        if retain_backup:
            result[_PROMOTION_TRANSACTION_KEY] = {
                "schema_version": PROMOTION_TRANSACTION_SCHEMA_VERSION,
                "kind": "theory_promotion_transaction",
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
        if displaced_new.exists():
            _remove_internal_tree(displaced_new)
        if installed and not destination.exists():
            raise TheoryRecordCorrupt(
                "theory promotion ended without a current package"
            )


def _normalize_current_record(
    value: Mapping[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TheoryValidationError(f"{label} must be an object")
    schema_version = value.get("schema_version")
    if type(schema_version) is not int:
        raise TheoryValidationError(
            f"{label} has an unsupported structure"
        )
    base = {
        "schema_version",
        "method_identity",
        "source_run_id",
        "scientific_outcome",
        "structurally_self_contained",
        "manuscript_sha256",
        "manuscript_size",
        "generation",
        "manuscript_file",
    }
    if schema_version == SCHEMA_VERSION:
        required = base | {
            "knowledge_file",
            "knowledge_sha256",
            "knowledge_size",
            "counterpart_basis",
        }
    elif schema_version == STRUCTURED_SCHEMA_VERSION:
        required = base | {
            "knowledge_file",
            "knowledge_sha256",
            "knowledge_size",
        }
    elif schema_version == LEGACY_SCHEMA_VERSION:
        required = base
    else:
        raise TheoryValidationError(
            f"{label} has an unsupported structure"
        )
    if set(value) != required:
        raise TheoryValidationError(
            f"{label} has an unsupported structure"
        )
    seal_fields = required - {
        "generation",
        "manuscript_file",
        "knowledge_file",
    }
    seal = _normalize_seal(
        {key: value[key] for key in seal_fields},
        allow_legacy=True,
    )
    generation = value.get("generation")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
        or value.get("manuscript_file") != THEORY_FILENAME
        or (
            schema_version in _KNOWLEDGE_SCHEMA_VERSIONS
            and value.get("knowledge_file") != KNOWLEDGE_FILENAME
        )
    ):
        raise TheoryValidationError(f"{label} generation is invalid")
    normalized = {
        **seal,
        "generation": generation,
        "manuscript_file": THEORY_FILENAME,
    }
    if schema_version in _KNOWLEDGE_SCHEMA_VERSIONS:
        normalized["knowledge_file"] = KNOWLEDGE_FILENAME
    return normalized


def _promotion_transaction(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> tuple[Path, Path | None, bool, dict[str, Any] | None, dict[str, Any]]:
    """Validate and resolve a retained theory-promotion transaction."""

    if not isinstance(promotion, Mapping):
        raise TheoryValidationError("theory promotion must be an object")
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
        or transaction.get("kind") != "theory_promotion_transaction"
    ):
        raise TheoryValidationError(
            "theory promotion has no valid retained transaction"
        )
    root = _project_root(project_dir)
    if transaction.get("project_root") != str(root):
        raise TheoryValidationError("theory promotion project identity is invalid")
    published = _normalize_current_record(
        transaction.get("published_record"),
        label="published theory record",
    )
    previous_value = transaction.get("previous_record")
    previous = (
        _normalize_current_record(previous_value, label="previous theory record")
        if previous_value is not None
        else None
    )
    stable_id = published["method_identity"]["stable_id"]
    destination = current_theory_directory(root, stable_id)
    if transaction.get("published_path") != destination.relative_to(root).as_posix():
        raise TheoryValidationError("theory promotion path is invalid")
    changed = transaction.get("changed")
    if not isinstance(changed, bool):
        raise TheoryValidationError("theory promotion changed flag is invalid")
    backup_value = transaction.get("backup_path")
    backup: Path | None = None
    if backup_value is not None:
        if not isinstance(backup_value, str):
            raise TheoryValidationError("theory promotion backup path is invalid")
        backup = _safe_project_path(root, backup_value, label="theory backup")
        if (
            backup.parent != destination.parent
            or not backup.name.startswith(".current-backup-")
        ):
            raise TheoryValidationError("theory promotion backup path is invalid")
    if changed:
        if (previous is None) != (backup is None):
            raise TheoryValidationError(
                "theory promotion prior-state metadata is inconsistent"
            )
    elif backup is not None or previous != published:
        raise TheoryValidationError("no-change theory promotion is inconsistent")
    outer_record = {
        key: value
        for key, value in promotion.items()
        if key != _PROMOTION_TRANSACTION_KEY
    }
    if outer_record != published:
        raise TheoryValidationError("theory promotion record changed after publication")
    return destination, backup, changed, previous, published


def recover_theory_promotion_intent(
    project_dir: str | Path,
    promotion_intent: Mapping[str, Any],
    *,
    make_current: bool,
) -> dict[str, Any] | None:
    """Recover one deterministic Phase 3 directory transaction."""

    from core import theory_promotion

    return theory_promotion.recover_theory_promotion_intent(
        project_dir,
        promotion_intent,
        make_current=make_current,
    )

def commit_theory_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Commit a retained theory promotion after state persistence succeeds."""

    destination, backup, _, previous, published = _promotion_transaction(
        project_dir, promotion
    )
    stable_id = published["method_identity"]["stable_id"]
    if _verified_current(destination, stable_id) != published:
        raise TheoryStageChanged("published theory package changed after promotion")
    if backup is None:
        return

    from core import project_state

    verified_backup = _verified_current(backup, stable_id)
    if verified_backup is None:
        project_state._sync_state_directory(backup.parent)
        return
    if verified_backup != previous:
        raise TheoryStageChanged("theory rollback backup changed after promotion")
    _remove_internal_tree(backup)
    project_state._sync_state_directory(backup.parent)

def rollback_theory_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Restore the theory package that preceded a retained promotion."""

    destination, backup, changed, previous, published = _promotion_transaction(
        project_dir, promotion
    )
    stable_id = published["method_identity"]["stable_id"]
    current_record = _verified_current(destination, stable_id)
    backup_record = (
        _verified_current(backup, stable_id) if backup is not None else None
    )
    if current_record == previous and backup_record is None:
        return
    if current_record != published:
        raise TheoryStageChanged("published theory package changed after promotion")
    if not changed:
        return
    if backup is not None and backup_record != previous:
        raise TheoryStageChanged("theory rollback backup changed after promotion")
    displaced = destination.parent / f".current-rejected-{uuid.uuid4().hex}"
    os.replace(destination, displaced)
    try:
        if backup is not None:
            os.replace(backup, destination)
            if _verified_current(destination, stable_id) != previous:
                raise TheoryRecordCorrupt("restored theory package failed verification")
        elif destination.exists():
            raise TheoryRecordCorrupt("theory rollback unexpectedly restored a package")
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
