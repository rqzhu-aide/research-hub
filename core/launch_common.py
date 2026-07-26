#!/usr/bin/env python3

"""Shared constants, paths, exceptions, and small helpers for run launching."""

from __future__ import annotations

import os
import shlex
import stat
import subprocess
import tempfile
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from core.filesystem_utils import metadata_is_link_or_reparse

log = logging.getLogger(__name__)


# Repository root is the parent of the core/ package directory.
HUB_DIR = Path(__file__).resolve().parent.parent


from core import project_state

HUB_CONFIG = HUB_DIR / "config.yaml"


PHASES_DIR = HUB_DIR / "config" / "phases"


TEAM_DIR = HUB_DIR / "config" / "team"


SOULS_DIR = HUB_DIR / "config" / "souls"


MAX_EMBEDDED_SOUL_BYTES = 512_000


MAX_REVIEW_MANUSCRIPT_BYTES = 2 * 1024 * 1024


MAX_REVIEW_BUNDLE_BYTES = 16 * 1024 * 1024


MAX_REVIEW_OUTPUT_BYTES = 2 * 1024 * 1024


MAX_TASK_BRIEF_BYTES = 4 * 1024 * 1024


MAX_LEAD_PROMPT_BYTES = 16 * 1024 * 1024


MAX_DIRECTIVE_BYTES = 256 * 1024


REVIEW_BUNDLE_SCHEMA_VERSION = 1


SOURCE_BASELINE_SCHEMA_VERSION = 2


MAX_SOURCE_SUMMARY_BYTES = 4 * 1024 * 1024


MAX_SOURCE_DECISION_BYTES = 128 * 1024


ELIGIBLE_SOURCE_STATUSES = frozenset({
    "approved",
    "awaiting_review",
    "revision_requested",
    "superseded",
})


SOURCE_BASELINE_STATUS_BY_RUN_STATUS = {
    "approved": "accepted",
    "awaiting_review": "proposed",
    "revision_requested": "proposed",
    "superseded": "historical",
}


PAPER_WRITING_PHASE = "05-review-revision"


IDEA_EVALUATION_PHASE = "03-idea-evaluation"


DRAFT_ASSEMBLY_PHASE = "04-draft-assembly"


PAPER_REVIEWER_ROLE = "paper_reviewer"


PAPER_REVIEWER_SKILL = "stat-paper-reviewer"


PAPER_WRITING_SKILL = "stat-paper-writing"


PAPER_WRITING_SKILL_ROLES = frozenset({
    "research_lead",
    "theorist",
    "data_scientist",
})


THEORY_PLAN_STANDARD = "standard"


THEORY_PLAN_STANDARD_WITH_AUDIT = "standard_with_audit"


THEORY_PLAN_AUDIT_ONLY = "audit_only"


THEORY_RUN_PLANS = frozenset({
    THEORY_PLAN_STANDARD,
    THEORY_PLAN_STANDARD_WITH_AUDIT,
    THEORY_PLAN_AUDIT_ONLY,
})

# Phase 04 run modes — preliminary (implement + test) vs comprehensive (benchmark).
RUN_MODE_PRELIMINARY = "preliminary"
RUN_MODE_COMPREHENSIVE = "comprehensive"

RUN_MODES = frozenset({
    RUN_MODE_PRELIMINARY,
    RUN_MODE_COMPREHENSIVE,
})

# Phase 05 run modes — assembly (assemble manuscript) vs review-revision (review + revise).
RUN_MODE_ASSEMBLY = "assembly"

RUN_MODE_REVIEW_REVISION = "review_revision"

PAPER_RUN_MODES = frozenset({
    RUN_MODE_ASSEMBLY,
    RUN_MODE_REVIEW_REVISION,
})


class LaunchError(RuntimeError):
    """A run could not be prepared or launched safely."""


class _ProcessOutputLimitExceeded(LaunchError):
    """A supervised subprocess exceeded its output byte budget."""


def _shell_join(arguments: Sequence[str | Path]) -> str:
    """Serialize a command for the platform shell used by Hermes terminal."""

    values = [str(value) for value in arguments]
    if os.name == "nt":
        quoted = ["'" + value.replace("'", "''") + "'" for value in values]
        return "& " + " ".join(quoted)
    return shlex.join(values)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
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


def _bounded_bytes(
    path: Path,
    *,
    label: str,
    max_bytes: int,
    allow_empty: bool = False,
) -> bytes:
    """Read one bounded regular file through the shared no-follow validator."""

    try:
        return project_state.bounded_file_bytes(
            path,
            maximum=max_bytes,
            label=label,
            allow_empty=allow_empty,
        )
    except project_state.ProjectStateError as exc:
        raise LaunchError(str(exc)) from exc


def _sha256_file(
    path: Path,
    *,
    max_bytes: int = MAX_REVIEW_BUNDLE_BYTES,
    label: str = "file",
    allow_empty: bool = True,
) -> str:
    try:
        digest, _ = project_state.bounded_file_digest(
            path,
            maximum=max_bytes,
            label=label,
            allow_empty=allow_empty,
        )
    except project_state.ProjectStateError as exc:
        raise LaunchError(str(exc)) from exc
    return digest


def _metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    """Backward-compatible alias for :func:`core.filesystem_utils.metadata_is_link_or_reparse`."""

    return metadata_is_link_or_reparse(metadata)


def _path_uses_symlink_below(path: Path, boundary: Path) -> bool:
    """Return whether a path component below boundary redirects through a link."""

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


def _ensure_contained_directory(
    directory: Path, boundary: Path, *, label: str
) -> Path:
    """Create a directory only through ordinary components inside a trusted root."""

    try:
        root = Path(boundary).resolve(strict=True)
    except OSError as exc:
        raise LaunchError(f"{label} boundary is unavailable: {boundary}") from exc
    candidate = Path(os.path.abspath(directory))
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise LaunchError(f"{label} escaped its allowed directory") from exc
    if _path_uses_symlink_below(candidate, root):
        raise LaunchError(f"{label} must not use symbolic links")
    try:
        candidate.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise LaunchError(f"Could not create {label}: {candidate}") from exc
    if _path_uses_symlink_below(candidate, root):
        raise LaunchError(f"{label} changed to a symbolic link during creation")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise LaunchError(f"{label} is not contained in its allowed directory") from exc
    if not resolved.is_dir():
        raise LaunchError(f"{label} must be a directory")
    return candidate


def _contained_file_destination(
    path: Path, boundary: Path, *, label: str
) -> Path:
    """Return a non-linked file path whose parent is safely contained."""

    root = Path(boundary).resolve(strict=True)
    candidate = Path(os.path.abspath(path))
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise LaunchError(f"{label} escaped its allowed directory") from exc
    _ensure_contained_directory(candidate.parent, root, label=f"{label} parent")
    if _path_uses_symlink_below(candidate, root) or candidate.is_symlink():
        raise LaunchError(f"{label} must not use symbolic links")
    return candidate


def _read_utf8_bounded(path: Path, *, label: str, max_bytes: int) -> str:
    payload = _bounded_bytes(path, label=label, max_bytes=max_bytes)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LaunchError(f"{label} is not valid UTF-8: {path}") from exc
    if not text.strip():
        raise LaunchError(f"{label} is empty: {path}")
    return text


def _is_sha256_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _guard_command_length(arguments: Sequence[str]) -> None:
    if os.name == "nt":
        command = subprocess.list2cmdline(list(arguments))
        utf16_units = len(command.encode("utf-16-le")) // 2
        if utf16_units >= 30_000:
            raise LaunchError("Hermes command exceeds the safe Windows command-line length")


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _run_index(project_dir: Path, phase_slug: str, run_id: str) -> int:
    for index, run in enumerate(project_state.get_runs(project_dir, phase_slug)):
        if run.get("run_id") == run_id:
            return index
    raise LaunchError(f"Reserved run {run_id} disappeared from project state")


def run_manifest_path(project_dir: Path, phase_slug: str, run_id: str) -> Path:
    return project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.manifest.json"


def run_context_dir(project_dir: Path, phase_slug: str, run_id: str) -> Path:
    return project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.context"


def prompt_path(project_dir: Path, phase_slug: str, run_id: str) -> Path:
    return project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.prompt.md"


def run_log_path(project_dir: Path, phase_slug: str, run_id: str) -> Path:
    return project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.log"
