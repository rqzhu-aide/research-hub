"""Cumulative Phase 01 reference-library transactions.

The live scientific record consists of:

``references/papers/*.md``
    One complete card for every classified paper or software resource.
``references/reference-index.json``
    A generated identity and provenance index.
``references/literature-summary.md``
    The current cumulative synthesis.

A Phase 01 run writes only genuinely new reference cards under
``<output_root>/reference-delta``. Existing filenames and canonical identities
are rejected. Preparing that directory records the exact live baseline.
Sealing binds the submitted bytes to that baseline. Promotion then builds the
complete library off to the side, preserving every prior card byte for byte,
and replaces the generated index and cumulative synthesis with rollback on any
failure.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping

from core.literature_schema import (
    REFERENCE_INDEX_SCHEMA_VERSION,
    MAX_CARD_BYTES as _MAX_CARD_BYTES,
    LiteratureRecordError,
    build_delta_operations as _build_delta_operations,
    LiteratureRecordValidationError,
    StaleLiteratureRecord,
    build_reference_index as _build_reference_index,
    load_cards as _load_cards,
    paper_file_records as _paper_file_records,
    validate_reference_index,
)
from core.strict_json import StrictJsonError, parse_json_object


REFERENCE_DIR = Path("references")
PAPERS_DIR = REFERENCE_DIR / "papers"
REFERENCE_INDEX = REFERENCE_DIR / "reference-index.json"
LITERATURE_SUMMARY = REFERENCE_DIR / "literature-summary.md"

STAGED_DELTA_DIRNAME = "reference-delta"
STAGED_PAPERS_DIRNAME = "papers"
BASELINE_FILENAME = "_baseline.json"
STAGED_SUMMARY_FILENAME = "literature-summary.md"

REFERENCE_DELTA_SCHEMA_VERSION = 1
PROMOTION_TRANSACTION_SCHEMA_VERSION = 1
_PROMOTION_TRANSACTION_KEY = "_promotion_transaction"

MAX_SUMMARY_BYTES = 5 * 1024 * 1024
MAX_INDEX_BYTES = 5 * 1024 * 1024
_MAX_SUMMARY_BYTES = MAX_SUMMARY_BYTES
_MAX_INDEX_BYTES = MAX_INDEX_BYTES
_MAX_BASELINE_BYTES = 5 * 1024 * 1024
_LIVE_CURRENT = object()
_PREPARED_PREFIX = ".reference-library-prepared-"
_BACKUP_PREFIX = ".reference-library-backup-"
_DISPLACED_PREFIX = ".reference-library-displaced-"


def _is_link_or_reparse(path: Path) -> bool:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return False
    attributes = int(getattr(details, "st_file_attributes", 0))
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    return stat.S_ISLNK(details.st_mode) or bool(reparse and attributes & reparse)


def _project_root(project_dir: str | Path) -> Path:
    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise LiteratureRecordValidationError(
            f"project directory is not a directory: {root}"
        )
    return root


def _relative_to_root(root: Path, path: Path, *, label: str) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise LiteratureRecordValidationError(
            f"{label} resolves outside the project directory"
        ) from exc


def _safe_project_path(root: Path, value: str | Path, *, label: str) -> Path:
    supplied = Path(value)
    lexical = supplied if supplied.is_absolute() else root / supplied
    lexical = Path(os.path.abspath(lexical))
    try:
        relative = lexical.relative_to(root)
    except ValueError as exc:
        raise LiteratureRecordValidationError(
            f"{label} is outside the project directory"
        ) from exc

    current = root
    for part in relative.parts:
        current = current / part
        try:
            current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LiteratureRecordValidationError(
                f"{label} cannot be inspected: {exc}"
            ) from exc
        if _is_link_or_reparse(current):
            raise LiteratureRecordValidationError(
                f"{label} must not contain a symbolic link or junction: {current}"
            )

    resolved = lexical.resolve(strict=False)
    _relative_to_root(root, resolved, label=label)
    return resolved


def _read_bounded_bytes(path: Path, *, maximum: int, label: str) -> bytes:
    try:
        details = path.lstat()
    except OSError as exc:
        raise LiteratureRecordValidationError(
            f"{label} cannot be inspected: {exc}"
        ) from exc
    if _is_link_or_reparse(path) or not stat.S_ISREG(details.st_mode):
        raise LiteratureRecordValidationError(
            f"{label} must be a regular file, not a link or junction"
        )
    if details.st_size > maximum:
        raise LiteratureRecordValidationError(
            f"{label} exceeds the {maximum}-byte limit"
        )
    try:
        with path.open("rb") as handle:
            raw = handle.read(maximum + 1)
    except OSError as exc:
        raise LiteratureRecordValidationError(f"{label} cannot be read: {exc}") from exc
    if len(raw) > maximum:
        raise LiteratureRecordValidationError(
            f"{label} exceeds the {maximum}-byte limit"
        )
    return raw


def _read_bounded_utf8(path: Path, *, maximum: int, label: str) -> tuple[str, bytes]:
    raw = _read_bounded_bytes(path, maximum=maximum, label=label)
    try:
        return raw.decode("utf-8"), raw
    except UnicodeDecodeError as exc:
        raise LiteratureRecordValidationError(f"{label} is not valid UTF-8") from exc


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _digest_bytes(encoded)


def _same_json(left: Any, right: Any) -> bool:
    try:
        left_text = json.dumps(left, sort_keys=True, separators=(",", ":"))
        right_text = json.dumps(right, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(left_text, right_text)


def _canonical_file_records(root: Path) -> list[dict[str, Any]]:
    papers = _safe_project_path(root, PAPERS_DIR, label="reference-card directory")
    records = _paper_file_records(papers, prefix="papers/")
    for relative, maximum, label in (
        (REFERENCE_INDEX, _MAX_INDEX_BYTES, "reference index"),
        (LITERATURE_SUMMARY, _MAX_SUMMARY_BYTES, "literature summary"),
    ):
        path = _safe_project_path(root, relative, label=label)
        if not path.exists():
            continue
        raw = _read_bounded_bytes(path, maximum=maximum, label=label)
        records.append(
            {
                "path": path.relative_to(root / REFERENCE_DIR).as_posix(),
                "sha256": _digest_bytes(raw),
                "size": len(raw),
            }
        )
    return sorted(records, key=lambda record: str(record["path"]))


def load_current_literature_record(
    project_dir: str | Path,
) -> dict[str, Any] | None:
    """Load and verify the canonical cumulative literature record."""

    root = _project_root(project_dir)
    index_path = _safe_project_path(root, REFERENCE_INDEX, label="reference index")
    if not index_path.exists():
        return None
    summary_path = _safe_project_path(
        root,
        LITERATURE_SUMMARY,
        label="literature summary",
    )
    if not summary_path.exists():
        raise LiteratureRecordValidationError(
            "reference index exists but the literature summary is missing"
        )
    index_raw = _read_bounded_bytes(
        index_path,
        maximum=_MAX_INDEX_BYTES,
        label="reference index",
    )
    summary_raw = _read_bounded_bytes(
        summary_path,
        maximum=_MAX_SUMMARY_BYTES,
        label="literature summary",
    )
    summary_sha256 = _digest_bytes(summary_raw)
    papers = _safe_project_path(root, PAPERS_DIR, label="reference-card directory")
    index = validate_reference_index(
        papers,
        index_raw,
        summary_sha256=summary_sha256,
    )
    return {
        "generation": index["generation"],
        "source_run_id": index["source_run_id"],
        "paper_count": len(index["entries"]),
        "papers_sha256": index["papers_sha256"],
        "summary_sha256": summary_sha256,
        "index_sha256": _digest_bytes(index_raw),
    }


def _normalize_source_run_id(
    source_run_id: str | None,
    output_root: str | Path,
) -> str:
    candidate = Path(output_root).name if source_run_id is None else str(source_run_id)
    normalized = candidate.strip()
    if not normalized:
        raise LiteratureRecordValidationError("source_run_id must be nonempty")
    return normalized

def _baseline_manifest(
    root: Path,
    *,
    source_run_id: str,
    prior_generation: int,
) -> dict[str, Any]:
    files = _canonical_file_records(root)
    return {
        "schema_version": REFERENCE_DELTA_SCHEMA_VERSION,
        "kind": "reference_library_baseline",
        "source_run_id": source_run_id,
        "prior_generation": prior_generation,
        "files": files,
        "library_sha256": _canonical_digest(files),
    }


def _staging_paths(root: Path, output_root: str | Path) -> tuple[Path, Path]:
    output = _safe_project_path(root, output_root, label="run output directory")
    if output.exists() and not output.is_dir():
        raise LiteratureRecordValidationError("run output path is not a directory")
    output.mkdir(parents=True, exist_ok=True)
    output = _safe_project_path(root, output, label="run output directory")
    staged = _safe_project_path(
        root,
        output / STAGED_DELTA_DIRNAME,
        label="staged reference delta",
    )
    return output, staged


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="",
    )


def _remove_owned_tree(path: Path, *, parent: Path, prefix: str) -> None:
    if not path.exists():
        return
    if path.parent != parent or not path.name.startswith(prefix):
        raise LiteratureRecordValidationError(
            f"refusing to remove unowned temporary path: {path}"
        )
    if _is_link_or_reparse(path) or not path.is_dir():
        raise LiteratureRecordValidationError(
            f"refusing to remove linked or non-directory temporary path: {path}"
        )
    shutil.rmtree(path)


def _normalize_frozen_current(value: Any) -> dict[str, Any] | None:
    """Validate a Phase 1 source copied into a schema 13 or later run."""

    if value is None:
        return None
    required = {
        "generation",
        "source_run_id",
        "summary_bytes",
        "summary_sha256",
        "index_bytes",
        "index_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise LiteratureRecordValidationError(
            "frozen literature source has an unsupported structure"
        )
    generation = value.get("generation")
    source_run_id = value.get("source_run_id")
    summary = value.get("summary_bytes")
    index_raw = value.get("index_bytes")
    summary_sha256 = value.get("summary_sha256")
    index_sha256 = value.get("index_sha256")
    if (
        isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
        or not isinstance(source_run_id, str)
        or not source_run_id.strip()
        or not isinstance(summary, bytes)
        or not 1 <= len(summary) <= MAX_SUMMARY_BYTES
        or not isinstance(index_raw, bytes)
        or not 1 <= len(index_raw) <= MAX_INDEX_BYTES
        or not isinstance(summary_sha256, str)
        or not isinstance(index_sha256, str)
        or not hmac.compare_digest(_digest_bytes(summary), summary_sha256)
        or not hmac.compare_digest(_digest_bytes(index_raw), index_sha256)
    ):
        raise LiteratureRecordValidationError(
            "frozen literature source has invalid identity or file metadata"
        )
    try:
        index = parse_json_object(index_raw, label="frozen reference index")
    except StrictJsonError as exc:
        raise LiteratureRecordValidationError(str(exc)) from exc
    expected_index_fields = {
        "schema_version",
        "kind",
        "source_run_id",
        "generation",
        "summary_sha256",
        "papers_sha256",
        "entries",
    }
    papers_sha256 = index.get("papers_sha256") if isinstance(index, Mapping) else None
    if (
        not isinstance(index, Mapping)
        or set(index) != expected_index_fields
        or index.get("schema_version") != REFERENCE_INDEX_SCHEMA_VERSION
        or index.get("kind") != "reference_index"
        or index.get("source_run_id") != source_run_id
        or index.get("generation") != generation
        or index.get("summary_sha256") != summary_sha256
        or not isinstance(papers_sha256, str)
        or len(papers_sha256) != 64
        or any(character not in "0123456789abcdef" for character in papers_sha256)
        or not isinstance(index.get("entries"), list)
    ):
        raise LiteratureRecordValidationError(
            "frozen reference index does not match its launch inventory"
        )
    return {
        "generation": generation,
        "source_run_id": source_run_id,
        "summary_bytes": summary,
        "summary_sha256": summary_sha256,
        "index_bytes": index_raw,
        "index_sha256": index_sha256,
        "papers_sha256": papers_sha256,
    }


def normalize_frozen_literature_source(value: Any) -> dict[str, Any] | None:
    """Validate a launch-frozen Phase 1 summary and reference collection."""

    return _normalize_frozen_current(value)


def prepare_reference_delta(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    source_run_id: str | None = None,
    frozen_current: object = _LIVE_CURRENT,
) -> dict[str, Any]:
    """Create a run-local delta from a live or exact frozen baseline."""

    root = _project_root(project_dir)
    canonical_papers = _safe_project_path(
        root,
        PAPERS_DIR,
        label="reference-card directory",
    )
    _load_cards(canonical_papers, prefix="papers/")
    normalized_run_id = _normalize_source_run_id(source_run_id, output_root)

    current = load_current_literature_record(root)
    frozen = (
        None
        if frozen_current is None
        else (
            _LIVE_CURRENT
            if frozen_current is _LIVE_CURRENT
            else _normalize_frozen_current(frozen_current)
        )
    )
    if frozen is None:
        if current is not None or _canonical_file_records(root):
            raise StaleLiteratureRecord(
                "a Phase 1 record appeared after this run was frozen"
            )
    elif frozen is not _LIVE_CURRENT:
        if current is None:
            raise StaleLiteratureRecord(
                "the frozen Phase 1 record is no longer current"
            )
        for field in (
            "generation",
            "source_run_id",
            "papers_sha256",
            "summary_sha256",
            "index_sha256",
        ):
            if not hmac.compare_digest(str(current[field]), str(frozen[field])):
                raise StaleLiteratureRecord(
                    "the Phase 1 record changed after this run was frozen"
                )

    if frozen is not None and frozen is not _LIVE_CURRENT:
        prior_generation = frozen["generation"]
    else:
        prior_generation = current["generation"] if current is not None else 0
    baseline = _baseline_manifest(
        root,
        source_run_id=normalized_run_id,
        prior_generation=prior_generation,
    )
    if frozen is not None and frozen is not _LIVE_CURRENT:
        baseline_by_path = {
            str(record.get("path", "")): record for record in baseline["files"]
        }
        for path, digest, size in (
            (
                LITERATURE_SUMMARY.name,
                frozen["summary_sha256"],
                len(frozen["summary_bytes"]),
            ),
            (
                REFERENCE_INDEX.name,
                frozen["index_sha256"],
                len(frozen["index_bytes"]),
            ),
        ):
            record = baseline_by_path.get(path)
            if record is None or record.get("sha256") != digest or record.get("size") != size:
                raise StaleLiteratureRecord(
                    "the Phase 1 record changed while its baseline was prepared"
                )
        validate_reference_index(
            canonical_papers,
            frozen["index_bytes"],
            summary_sha256=frozen["summary_sha256"],
        )

    if frozen is not None and frozen is not _LIVE_CURRENT:
        summary = frozen["summary_bytes"]
    elif frozen is None:
        summary = b"# Literature Summary\n"
    else:
        live_summary = _safe_project_path(
            root,
            LITERATURE_SUMMARY,
            label="literature summary",
        )
        summary = (
            _read_bounded_bytes(
                live_summary,
                maximum=_MAX_SUMMARY_BYTES,
                label="literature summary",
            )
            if live_summary.exists()
            else b"# Literature Summary\n"
        )

    output, staged = _staging_paths(root, output_root)
    if staged.exists():
        raise LiteratureRecordValidationError(
            "staged reference delta already exists for this run"
        )

    prepared = Path(
        tempfile.mkdtemp(prefix=".reference-delta-prepared-", dir=str(output))
    )
    try:
        (prepared / STAGED_PAPERS_DIRNAME).mkdir()
        _write_json(prepared / BASELINE_FILENAME, baseline)
        (prepared / STAGED_SUMMARY_FILENAME).write_bytes(summary)
        os.replace(prepared, staged)
    finally:
        if prepared.exists():
            _remove_owned_tree(
                prepared,
                parent=output,
                prefix=".reference-delta-prepared-",
            )

    return {
        "schema_version": REFERENCE_DELTA_SCHEMA_VERSION,
        "kind": "reference_delta_stage",
        "staged_path": _relative_to_root(
            root,
            staged,
            label="staged reference delta",
        ),
        "source_run_id": baseline["source_run_id"],
        "prior_generation": baseline["prior_generation"],
        "generation": baseline["prior_generation"] + 1,
        "baseline_files": baseline["files"],
        "baseline_library_sha256": baseline["library_sha256"],
    }


def _load_baseline_marker(staged: Path) -> dict[str, Any]:
    marker = staged / BASELINE_FILENAME
    text, _ = _read_bounded_utf8(
        marker,
        maximum=_MAX_BASELINE_BYTES,
        label="reference-delta baseline",
    )
    try:
        baseline = parse_json_object(text, label="reference-delta baseline")
    except StrictJsonError as exc:
        raise LiteratureRecordValidationError(str(exc)) from exc
    files = baseline.get("files")
    digest = baseline.get("library_sha256")
    source_run_id = baseline.get("source_run_id")
    prior_generation = baseline.get("prior_generation")
    if (
        baseline.get("schema_version") != REFERENCE_DELTA_SCHEMA_VERSION
        or baseline.get("kind") != "reference_library_baseline"
        or not isinstance(source_run_id, str)
        or not source_run_id.strip()
        or isinstance(prior_generation, bool)
        or not isinstance(prior_generation, int)
        or prior_generation < 0
        or not isinstance(files, list)
        or not isinstance(digest, str)
        or digest != _canonical_digest(files)
    ):
        raise StaleLiteratureRecord(
            "reference-delta baseline identity or digest is invalid"
        )
    return baseline


def _validate_staged_shape(staged: Path) -> None:
    if _is_link_or_reparse(staged) or not staged.is_dir():
        raise LiteratureRecordValidationError(
            "staged reference delta must be a regular directory"
        )
    expected = {
        BASELINE_FILENAME,
        STAGED_PAPERS_DIRNAME,
        STAGED_SUMMARY_FILENAME,
    }
    found = {child.name for child in staged.iterdir()}
    if found != expected:
        extras = sorted(found - expected)
        missing = sorted(expected - found)
        detail = []
        if extras:
            detail.append(f"unsupported items: {', '.join(extras)}")
        if missing:
            detail.append(f"missing items: {', '.join(missing)}")
        raise LiteratureRecordValidationError(
            "staged reference delta has invalid contents"
            + (f" ({'; '.join(detail)})" if detail else "")
        )
    papers = staged / STAGED_PAPERS_DIRNAME
    if _is_link_or_reparse(papers) or not papers.is_dir():
        raise LiteratureRecordValidationError(
            "staged reference-delta papers must be a regular directory"
        )


def _stage_file_records(staged: Path) -> list[dict[str, Any]]:
    _validate_staged_shape(staged)
    records = _paper_file_records(
        staged / STAGED_PAPERS_DIRNAME,
        prefix="papers/",
    )
    for filename, maximum, label in (
        (BASELINE_FILENAME, _MAX_BASELINE_BYTES, "reference-delta baseline"),
        (
            STAGED_SUMMARY_FILENAME,
            _MAX_SUMMARY_BYTES,
            "staged literature summary",
        ),
    ):
        raw = _read_bounded_bytes(
            staged / filename,
            maximum=maximum,
            label=label,
        )
        records.append(
            {
                "path": filename,
                "sha256": _digest_bytes(raw),
                "size": len(raw),
            }
        )
    return sorted(records, key=lambda record: str(record["path"]))


def _seal_staged_delta(root: Path, staged: Path) -> dict[str, Any]:
    baseline = _load_baseline_marker(staged)
    try:
        current = load_current_literature_record(root)
    except LiteratureRecordValidationError as exc:
        raise StaleLiteratureRecord(
            "live reference library changed or became invalid"
        ) from exc
    live_generation = current["generation"] if current is not None else 0
    if baseline["prior_generation"] != live_generation:
        raise StaleLiteratureRecord(
            "reference-delta prior generation does not match the live record"
        )
    live_files = _canonical_file_records(root)
    if (
        not _same_json(live_files, baseline["files"])
        or _canonical_digest(live_files) != baseline["library_sha256"]
    ):
        raise StaleLiteratureRecord(
            "reference library changed after this run's delta was prepared"
        )
    canonical_cards = _load_cards(
        _safe_project_path(root, PAPERS_DIR, label="reference-card directory"),
        prefix="papers/",
    )
    delta_cards = _load_cards(
        staged / STAGED_PAPERS_DIRNAME,
        prefix="papers/",
    )
    summary_text, _ = _read_bounded_utf8(
        staged / STAGED_SUMMARY_FILENAME,
        maximum=_MAX_SUMMARY_BYTES,
        label="staged literature summary",
    )
    if not summary_text.strip():
        raise LiteratureRecordValidationError(
            "staged literature summary must be nonempty"
        )
    files = _stage_file_records(staged)
    return {
        "schema_version": REFERENCE_DELTA_SCHEMA_VERSION,
        "kind": "reference_delta",
        "staged_path": _relative_to_root(
            root,
            staged,
            label="staged reference delta",
        ),
        "files": files,
        "delta_sha256": _canonical_digest(files),
        "source_run_id": baseline["source_run_id"],
        "prior_generation": baseline["prior_generation"],
        "generation": baseline["prior_generation"] + 1,
        "baseline_files": baseline["files"],
        "baseline_library_sha256": baseline["library_sha256"],
        "operations": _build_delta_operations(canonical_cards, delta_cards),
    }


def seal_reference_delta(
    project_dir: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """Validate the run-local delta and seal its exact submitted bytes."""

    root = _project_root(project_dir)
    _, staged = _staging_paths(root, output_root)
    return _seal_staged_delta(root, staged)


def verify_reference_delta_seal(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
) -> dict[str, Any]:
    """Reject any delta, summary, baseline, or live-library change after sealing."""

    if not isinstance(seal, Mapping):
        raise LiteratureRecordValidationError(
            "reference-delta seal must be a mapping"
        )
    root = _project_root(project_dir)
    _, staged = _staging_paths(root, output_root)
    expected_path = _relative_to_root(
        root,
        staged,
        label="staged reference delta",
    )
    if (
        seal.get("schema_version") != REFERENCE_DELTA_SCHEMA_VERSION
        or seal.get("kind") != "reference_delta"
        or seal.get("staged_path") != expected_path
    ):
        raise StaleLiteratureRecord(
            "reference-delta seal identity is invalid or stale"
        )
    current = _seal_staged_delta(root, staged)
    for field in (
        "files",
        "delta_sha256",
        "source_run_id",
        "prior_generation",
        "generation",
        "baseline_files",
        "baseline_library_sha256",
        "operations",
    ):
        if not _same_json(seal.get(field), current[field]):
            raise StaleLiteratureRecord(
                "staged reference delta changed after it was sealed"
            )
    return current


def _record_by_path(records: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(record.get("path", "")): record for record in records}


def _copy_verified_file(
    source: Path,
    destination: Path,
    record: Mapping[str, Any],
    *,
    maximum: int,
    label: str,
) -> None:
    raw = _read_bounded_bytes(source, maximum=maximum, label=label)
    if (
        record.get("size") != len(raw)
        or record.get("sha256") != _digest_bytes(raw)
    ):
        raise StaleLiteratureRecord(f"{label} changed during promotion")
    destination.write_bytes(raw)


def _prepare_complete_library(
    root: Path,
    staged: Path,
    verified: Mapping[str, Any],
) -> Path:
    references = _safe_project_path(root, REFERENCE_DIR, label="references directory")
    references.mkdir(parents=True, exist_ok=True)
    references = _safe_project_path(root, references, label="references directory")
    prepared = Path(
        tempfile.mkdtemp(prefix=_PREPARED_PREFIX, dir=str(references))
    )
    prepared_papers = prepared / "papers"
    prepared_papers.mkdir()

    baseline_by_path = _record_by_path(list(verified["baseline_files"]))
    canonical_papers = _safe_project_path(
        root,
        PAPERS_DIR,
        label="reference-card directory",
    )
    for path, record in sorted(baseline_by_path.items()):
        if not path.startswith("papers/"):
            continue
        filename = Path(path).name
        _copy_verified_file(
            canonical_papers / filename,
            prepared_papers / filename,
            record,
            maximum=_MAX_CARD_BYTES,
            label=f"canonical reference card {filename!r}",
        )

    staged_by_path = _record_by_path(list(verified["files"]))
    for operation in verified["operations"]:
        filename = str(operation["filename"])
        source_path = str(operation["source_path"])
        record = staged_by_path.get(source_path)
        if record is None or record.get("sha256") != operation.get("source_sha256"):
            raise StaleLiteratureRecord(
                f"sealed record is missing for delta card {filename!r}"
            )
        _copy_verified_file(
            staged / source_path,
            prepared_papers / filename,
            record,
            maximum=_MAX_CARD_BYTES,
            label=f"sealed delta card {filename!r}",
        )

    summary_record = staged_by_path.get(STAGED_SUMMARY_FILENAME)
    if summary_record is None:
        raise StaleLiteratureRecord("sealed literature summary record is missing")
    _copy_verified_file(
        staged / STAGED_SUMMARY_FILENAME,
        prepared / STAGED_SUMMARY_FILENAME,
        summary_record,
        maximum=_MAX_SUMMARY_BYTES,
        label="sealed literature summary",
    )
    (prepared / REFERENCE_INDEX.name).write_bytes(
        _build_reference_index(
            prepared_papers,
            source_run_id=str(verified["source_run_id"]),
            generation=int(verified["generation"]),
            summary_sha256=str(summary_record["sha256"]),
        )
    )
    return prepared


def _prepared_file_records(prepared: Path) -> list[dict[str, Any]]:
    records = _paper_file_records(prepared / "papers", prefix="papers/")
    for filename, maximum, label in (
        (REFERENCE_INDEX.name, _MAX_INDEX_BYTES, "prepared reference index"),
        (
            STAGED_SUMMARY_FILENAME,
            _MAX_SUMMARY_BYTES,
            "prepared literature summary",
        ),
    ):
        raw = _read_bounded_bytes(
            prepared / filename,
            maximum=maximum,
            label=label,
        )
        records.append(
            {
                "path": filename,
                "sha256": _digest_bytes(raw),
                "size": len(raw),
            }
        )
    return sorted(records, key=lambda record: str(record["path"]))


def _rollback_component_swap(
    references: Path,
    prepared: Path,
    backup: Path,
    installed: list[str],
    moved_originals: list[str],
) -> None:
    for name in reversed(installed):
        live = references / name
        if live.exists():
            os.replace(live, prepared / name)
    for name in reversed(moved_originals):
        saved = backup / name
        if saved.exists():
            os.replace(saved, references / name)


def promote_reference_delta(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
    *,
    retain_backup: bool = False,
) -> dict[str, Any]:
    """Promote a sealed cumulative delta without deleting any prior paper."""

    root = _project_root(project_dir)
    verified = verify_reference_delta_seal(root, output_root, seal)
    _, staged = _staging_paths(root, output_root)
    live_files = _canonical_file_records(root)
    if (
        not _same_json(live_files, verified["baseline_files"])
        or _canonical_digest(live_files)
        != verified["baseline_library_sha256"]
    ):
        raise StaleLiteratureRecord(
            "reference library changed after this delta was sealed"
        )

    prepared = _prepare_complete_library(root, staged, verified)
    prepared_records = _prepared_file_records(prepared)
    baseline_papers = {
        str(record["path"])
        for record in verified["baseline_files"]
        if str(record.get("path", "")).startswith("papers/")
    }
    prepared_papers = {
        str(record["path"])
        for record in prepared_records
        if str(record.get("path", "")).startswith("papers/")
    }
    if not baseline_papers.issubset(prepared_papers):
        _remove_owned_tree(
            prepared,
            parent=prepared.parent,
            prefix=_PREPARED_PREFIX,
        )
        raise LiteratureRecordValidationError(
            "prepared reference library would delete canonical paper cards"
        )

    references = prepared.parent
    backup = references / f"{_BACKUP_PREFIX}{uuid.uuid4().hex}"
    backup.mkdir()
    installed: list[str] = []
    moved_originals: list[str] = []
    components = (
        PAPERS_DIR.name,
        REFERENCE_INDEX.name,
        LITERATURE_SUMMARY.name,
    )
    try:
        current_files = _canonical_file_records(root)
        if (
            not _same_json(current_files, verified["baseline_files"])
            or _canonical_digest(current_files)
            != verified["baseline_library_sha256"]
        ):
            raise StaleLiteratureRecord(
                "reference library changed while promotion was being prepared"
            )
        for name in components:
            live = references / name
            source = prepared / name
            if live.exists():
                os.replace(live, backup / name)
                moved_originals.append(name)
            try:
                os.replace(source, live)
            except BaseException:
                raise
            installed.append(name)

        post_files = _canonical_file_records(root)
        if not _same_json(post_files, prepared_records):
            raise StaleLiteratureRecord(
                "published reference library failed post-write verification"
            )
        current_record = load_current_literature_record(root)
        if (
            current_record is None
            or current_record["source_run_id"] != verified["source_run_id"]
            or current_record["generation"] != verified["generation"]
        ):
            raise StaleLiteratureRecord(
                "published reference record has the wrong run identity or generation"
            )
    except BaseException:
        _rollback_component_swap(
            references,
            prepared,
            backup,
            installed,
            moved_originals,
        )
        raise
    finally:
        if prepared.exists():
            _remove_owned_tree(
                prepared,
                parent=references,
                prefix=_PREPARED_PREFIX,
            )
        if backup.exists() and not any(backup.iterdir()):
            _remove_owned_tree(
                backup,
                parent=references,
                prefix=_BACKUP_PREFIX,
            )

    if not retain_backup:
        _remove_owned_tree(
            backup,
            parent=references,
            prefix=_BACKUP_PREFIX,
        )
    result = {
        "schema_version": REFERENCE_DELTA_SCHEMA_VERSION,
        "kind": "reference_delta_promotion",
        "source_run_id": current_record["source_run_id"],
        "generation": current_record["generation"],
        "paper_count": current_record["paper_count"],
        "summary_sha256": current_record["summary_sha256"],
        "index_sha256": current_record["index_sha256"],
        "published_files": prepared_records,
        "published_library_sha256": _canonical_digest(prepared_records),
        "changes": list(verified["operations"]),
        "added": [
            operation["filename"]
            for operation in verified["operations"]
            if operation["change"] == "added"
        ],
    }
    if retain_backup:
        result[_PROMOTION_TRANSACTION_KEY] = {
            "schema_version": PROMOTION_TRANSACTION_SCHEMA_VERSION,
            "kind": "literature_promotion_transaction",
            "project_root": str(root),
            "published_path": REFERENCE_DIR.as_posix(),
            "backup_path": (
                backup.relative_to(root).as_posix()
                if backup.exists()
                else None
            ),
            "previous_file_count": len(verified["baseline_files"]),
            "previous_library_sha256": verified["baseline_library_sha256"],
            "published_file_count": len(prepared_records),
            "published_library_sha256": _canonical_digest(prepared_records),
        }
    return result


def _library_file_records(directory: Path) -> list[dict[str, Any]]:
    """Return bounded records for one complete or legacy library directory."""

    if not directory.exists():
        return []
    if _is_link_or_reparse(directory) or not directory.is_dir():
        raise LiteratureRecordValidationError(
            "reference-library transaction directory is invalid"
        )
    allowed = {
        PAPERS_DIR.name,
        REFERENCE_INDEX.name,
        LITERATURE_SUMMARY.name,
    }
    for entry in directory.iterdir():
        if entry.name not in allowed or _is_link_or_reparse(entry):
            raise LiteratureRecordValidationError(
                "reference-library transaction directory contains an unexpected entry"
            )
    records = _paper_file_records(directory / PAPERS_DIR.name, prefix="papers/")
    for filename, maximum, label in (
        (REFERENCE_INDEX.name, _MAX_INDEX_BYTES, "reference index"),
        (LITERATURE_SUMMARY.name, _MAX_SUMMARY_BYTES, "literature summary"),
    ):
        path = directory / filename
        if not path.exists():
            continue
        raw = _read_bounded_bytes(path, maximum=maximum, label=label)
        records.append(
            {
                "path": filename,
                "sha256": _digest_bytes(raw),
                "size": len(raw),
            }
        )
    return sorted(records, key=lambda record: str(record["path"]))


def _promotion_transaction(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> tuple[Path, Path | None, int, str, int, str]:
    """Validate and resolve a retained literature-promotion transaction."""

    if not isinstance(promotion, Mapping):
        raise LiteratureRecordValidationError(
            "literature promotion must be an object"
        )
    transaction = promotion.get(_PROMOTION_TRANSACTION_KEY)
    required = {
        "schema_version",
        "kind",
        "project_root",
        "published_path",
        "backup_path",
        "previous_file_count",
        "previous_library_sha256",
        "published_file_count",
        "published_library_sha256",
    }
    if (
        not isinstance(transaction, Mapping)
        or set(transaction) != required
        or transaction.get("schema_version")
        != PROMOTION_TRANSACTION_SCHEMA_VERSION
        or transaction.get("kind") != "literature_promotion_transaction"
    ):
        raise LiteratureRecordValidationError(
            "literature promotion has no valid retained transaction"
        )
    root = _project_root(project_dir)
    if (
        transaction.get("project_root") != str(root)
        or transaction.get("published_path") != REFERENCE_DIR.as_posix()
    ):
        raise LiteratureRecordValidationError(
            "literature promotion project or path identity is invalid"
        )
    previous_count = transaction.get("previous_file_count")
    published_count = transaction.get("published_file_count")
    if (
        not isinstance(previous_count, int)
        or isinstance(previous_count, bool)
        or previous_count < 0
        or not isinstance(published_count, int)
        or isinstance(published_count, bool)
        or published_count < 1
    ):
        raise LiteratureRecordValidationError(
            "literature promotion file counts are invalid"
        )
    previous_digest = str(
        transaction.get("previous_library_sha256", "")
    ).strip().lower()
    published_digest = str(
        transaction.get("published_library_sha256", "")
    ).strip().lower()
    for digest in (previous_digest, published_digest):
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise LiteratureRecordValidationError(
                "literature promotion library digest is invalid"
            )
    published_files = promotion.get("published_files")
    if (
        not isinstance(published_files, list)
        or len(published_files) != published_count
        or _canonical_digest(published_files) != published_digest
        or promotion.get("published_library_sha256") != published_digest
    ):
        raise LiteratureRecordValidationError(
            "literature promotion file records are inconsistent"
        )
    backup_value = transaction.get("backup_path")
    backup: Path | None = None
    if backup_value is not None:
        if not isinstance(backup_value, str):
            raise LiteratureRecordValidationError(
                "literature promotion backup path is invalid"
            )
        backup = _safe_project_path(root, backup_value, label="literature backup")
        references = root / REFERENCE_DIR
        if backup.parent != references or not backup.name.startswith(_BACKUP_PREFIX):
            raise LiteratureRecordValidationError(
                "literature promotion backup path is invalid"
            )
    if previous_count > 0 and backup is None:
        raise LiteratureRecordValidationError(
            "literature promotion prior-state metadata is inconsistent"
        )
    return (
        root,
        backup,
        previous_count,
        previous_digest,
        published_count,
        published_digest,
    )




def _matches_library_record(
    records: list[dict[str, Any]],
    expected_count: int,
    expected_digest: str,
) -> bool:
    return len(records) == expected_count and hmac.compare_digest(
        _canonical_digest(records), expected_digest
    )
def commit_reference_delta_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Commit a retained literature promotion after state persistence."""

    (
        root,
        backup,
        previous_count,
        previous_digest,
        published_count,
        published_digest,
    ) = _promotion_transaction(project_dir, promotion)
    if not _matches_library_record(
        _canonical_file_records(root), published_count, published_digest
    ):
        raise StaleLiteratureRecord(
            "published reference library changed after promotion"
        )
    if backup is None or not backup.exists():
        return
    if not _matches_library_record(
        _library_file_records(backup), previous_count, previous_digest
    ):
        raise StaleLiteratureRecord(
            "reference-library rollback backup changed after promotion"
        )
    _remove_owned_tree(backup, parent=backup.parent, prefix=_BACKUP_PREFIX)


def rollback_reference_delta_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Restore the reference library that preceded a retained promotion."""

    (
        root,
        backup,
        previous_count,
        previous_digest,
        published_count,
        published_digest,
    ) = _promotion_transaction(project_dir, promotion)
    already_restored = _matches_library_record(
        _canonical_file_records(root), previous_count, previous_digest
    )
    if already_restored:
        if backup is not None and backup.exists():
            _remove_owned_tree(
                backup, parent=backup.parent, prefix=_BACKUP_PREFIX
            )
        return
    if not _matches_library_record(
        _canonical_file_records(root), published_count, published_digest
    ):
        raise StaleLiteratureRecord(
            "published reference library changed after promotion"
        )
    if backup is not None and (
        not backup.exists()
        or not _matches_library_record(
            _library_file_records(backup), previous_count, previous_digest
        )
    ):
        raise StaleLiteratureRecord(
            "reference-library rollback backup changed after promotion"
        )

    references = root / REFERENCE_DIR
    references.mkdir(parents=True, exist_ok=True)
    displaced = references / f"{_DISPLACED_PREFIX}{uuid.uuid4().hex}"
    displaced.mkdir()
    components = (
        PAPERS_DIR.name,
        REFERENCE_INDEX.name,
        LITERATURE_SUMMARY.name,
    )
    moved_current: list[str] = []
    restored_previous: list[str] = []
    try:
        for name in components:
            live = references / name
            if live.exists():
                os.replace(live, displaced / name)
                moved_current.append(name)
        if backup is not None:
            for name in components:
                saved = backup / name
                if saved.exists():
                    os.replace(saved, references / name)
                    restored_previous.append(name)
        if not _matches_library_record(
            _canonical_file_records(root), previous_count, previous_digest
        ):
            raise StaleLiteratureRecord(
                "restored reference library failed verification"
            )
    except BaseException:
        if backup is not None:
            for name in reversed(restored_previous):
                live = references / name
                if live.exists():
                    os.replace(live, backup / name)
        for name in reversed(moved_current):
            saved = displaced / name
            if saved.exists():
                os.replace(saved, references / name)
        raise
    finally:
        if displaced.exists() and not any(displaced.iterdir()):
            _remove_owned_tree(
                displaced,
                parent=references,
                prefix=_DISPLACED_PREFIX,
            )
    if displaced.exists():
        _remove_owned_tree(
            displaced,
            parent=references,
            prefix=_DISPLACED_PREFIX,
        )
    if backup is not None and backup.exists():
        _remove_owned_tree(backup, parent=references, prefix=_BACKUP_PREFIX)
