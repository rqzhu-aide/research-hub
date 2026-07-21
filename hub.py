#!/usr/bin/env python3
"""Storage and configuration helpers for the Research Hub web application.

The database is intentionally small: it is the registry of projects. Runtime
and phase history live in a sibling control directory managed by the run-state
helpers in ``scripts/``.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import stat
import sys
import threading
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterator, List, Optional, Sequence

import yaml


HUB_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = HUB_DIR / "config.yaml"
SCHEMA_PATH = HUB_DIR / "schema.sql"

SQLITE_BUSY_TIMEOUT_MS = 5_000
MAX_CONFIGURED_ROUNDS = 50
MAX_ROLE_SOUL_BYTES = 100 * 1024
MAX_CONFIG_BYTES = 2 * 1024 * 1024
PROJECT_SLUG_MAX_LENGTH = 64
REQUIRED_LEAD_AGENT_ID = "research_lead"

_schema_lock = threading.RLock()
_operation_thread_lock = threading.RLock()

_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PHASE_SLUG_RE = re.compile(r"^[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
_ALLOWED_PATTERNS = {"parallel", "sequential", "debate"}


class ConfigurationError(ValueError):
    """Raised when ``config.yaml`` cannot safely describe a workspace."""


def _metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    """Recognize POSIX links and Windows reparse points."""

    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(
        stat,
        "FILE_ATTRIBUTE_REPARSE_POINT",
        0x400 if os.name == "nt" else 0,
    )
    return bool(
        reparse_flag
        and getattr(metadata, "st_file_attributes", 0) & reparse_flag
    )


def _verify_open_lock_file(handle: BinaryIO, path: Path, *, label: str) -> None:
    """Require a named lock path to still identify the opened regular file."""

    try:
        opened_metadata = os.fstat(handle.fileno())
        path_metadata = path.lstat()
    except OSError as exc:
        raise RuntimeError(f"{label} is unavailable: {path}") from exc
    if (
        _metadata_is_link_or_reparse(path_metadata)
        or not stat.S_ISREG(opened_metadata.st_mode)
        or not os.path.samestat(opened_metadata, path_metadata)
    ):
        raise RuntimeError(
            f"{label} must be one unchanged regular file, not a link: {path}"
        )


@contextmanager
def _open_verified_lock_file(path: Path, *, label: str) -> Iterator[BinaryIO]:
    """Open a lock file without following a link and verify its path identity."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, 0o600)
        handle = os.fdopen(descriptor, "a+b")
        descriptor = None
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise RuntimeError(f"{label} is unavailable: {path}") from exc
    try:
        _verify_open_lock_file(handle, path, label=label)
        if os.name != "nt":
            try:
                os.fchmod(handle.fileno(), 0o600)
            except OSError as exc:
                raise RuntimeError(
                    f"{label} permissions could not be restricted: {path}"
                ) from exc
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
            os.fsync(handle.fileno())
        _verify_open_lock_file(handle, path, label=label)
        yield handle
    finally:
        handle.close()


@contextmanager
def operation_lock(timeout: float = 30.0) -> Iterator[None]:
    """Serialize launches, project creation, and workspace replacement."""

    lock_path = CONFIG_PATH.with_suffix(".operations.lock")
    with _operation_thread_lock, _open_verified_lock_file(
        lock_path, label="hub operation lock"
    ) as handle:
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

                        fcntl.flock(
                            handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                        )
                    acquired = True
                except (OSError, BlockingIOError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "timed out waiting for another hub operation to finish"
                        )
                    time.sleep(0.025)
            _verify_open_lock_file(handle, lock_path, label="hub operation lock")
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


def _require_nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_safe_relative_folder(value: object, field: str) -> str:
    """Validate a portable project-relative output directory."""
    folder = _require_nonempty_string(value, field)
    if "\\" in folder or ":" in folder or "\x00" in folder:
        raise ConfigurationError(
            f"{field} must use a safe, forward-slash relative path"
        )
    path = PurePosixPath(folder)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ConfigurationError(f"{field} must stay inside the project directory")
    return folder


def _validate_rounds(value: object, field: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigurationError(
            f"{field} must be a mapping with min, default, and max integers"
        )
    if set(value) != {"min", "default", "max"}:
        raise ConfigurationError(f"{field} must contain exactly min, default, and max")
    limits = {key: value[key] for key in ("min", "default", "max")}
    if any(isinstance(number, bool) or not isinstance(number, int) for number in limits.values()):
        raise ConfigurationError(f"{field} values must be integers")
    if not (1 <= limits["min"] <= limits["default"] <= limits["max"]):
        raise ConfigurationError(
            f"{field} must satisfy 1 <= min <= default <= max"
        )
    if limits["max"] > MAX_CONFIGURED_ROUNDS:
        raise ConfigurationError(
            f"{field}.max cannot exceed {MAX_CONFIGURED_ROUNDS}"
        )
    return limits


def _validate_gate_dag(phases: Sequence[dict]) -> None:
    dependencies = {phase["slug"]: phase["gated_by"] for phase in phases}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(slug: str) -> None:
        if slug in visiting:
            cycle = " -> ".join([*sorted(visiting), slug])
            raise ConfigurationError(f"phase gated_by graph contains a cycle: {cycle}")
        if slug in visited:
            return
        visiting.add(slug)
        for dependency in dependencies[slug]:
            visit(dependency)
        visiting.remove(slug)
        visited.add(slug)

    for phase_slug in dependencies:
        visit(phase_slug)


def _validate_role_soul(agent_id: str, path: Path) -> None:
    """Require a bounded, readable UTF-8 instruction file for one agent."""
    label = f"agent {agent_id!r} soul"
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ConfigurationError(f"{label} must be a regular file: {path}") from exc
    except OSError as exc:
        raise ConfigurationError(
            f"cannot inspect {label} at {path}: {exc}"
        ) from exc

    if not stat.S_ISREG(metadata.st_mode):
        raise ConfigurationError(f"{label} must be a regular file: {path}")
    if metadata.st_size > MAX_ROLE_SOUL_BYTES:
        raise ConfigurationError(
            f"{label} at {path} exceeds the maximum size of "
            f"{MAX_ROLE_SOUL_BYTES} bytes"
        )

    try:
        with path.open("rb") as handle:
            payload = handle.read(MAX_ROLE_SOUL_BYTES + 1)
    except OSError as exc:
        raise ConfigurationError(f"cannot read {label} at {path}: {exc}") from exc
    if len(payload) > MAX_ROLE_SOUL_BYTES:
        raise ConfigurationError(
            f"{label} at {path} exceeds the maximum size of "
            f"{MAX_ROLE_SOUL_BYTES} bytes"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigurationError(f"{label} is not valid UTF-8: {path}") from exc
    if not text.strip():
        raise ConfigurationError(
            f"{label} must contain non-whitespace text: {path}"
        )


def validate_config(cfg: object, *, config_root: Optional[Path] = None) -> dict:
    """Validate and normalize a loaded Research Hub configuration.

    Sequential phases have a fixed stage plan. If their ``rounds`` mapping is
    omitted, it is inferred from the number of stages. Parallel and debate
    phases must provide explicit bounds so the web UI can explain the user's
    choice before launching a run.
    """
    if not isinstance(cfg, dict):
        raise ConfigurationError("config.yaml must contain a mapping")

    hub_cfg = cfg.get("hub")
    if not isinstance(hub_cfg, dict):
        raise ConfigurationError("hub must be a mapping")
    _require_nonempty_string(hub_cfg.get("name"), "hub.name")
    _require_nonempty_string(hub_cfg.get("workspace_dir"), "hub.workspace_dir")
    max_iterations = hub_cfg.get("max_iterations", 10)
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
        raise ConfigurationError("hub.max_iterations must be a positive integer")
    run_timeout = hub_cfg.get("run_timeout_minutes", 120)
    if isinstance(run_timeout, bool) or not isinstance(run_timeout, int) or run_timeout < 1:
        raise ConfigurationError("hub.run_timeout_minutes must be a positive integer")
    unattended = hub_cfg.get("allow_unattended_tools", False)
    if not isinstance(unattended, bool):
        raise ConfigurationError("hub.allow_unattended_tools must be true or false")

    agents = cfg.get("agents")
    if not isinstance(agents, list) or not agents:
        raise ConfigurationError("agents must be a non-empty list")
    agent_ids: set[str] = set()
    for index, agent in enumerate(agents):
        field = f"agents[{index}]"
        if not isinstance(agent, dict):
            raise ConfigurationError(f"{field} must be a mapping")
        agent_id = _require_nonempty_string(agent.get("id"), f"{field}.id")
        profile = _require_nonempty_string(agent.get("profile"), f"{field}.profile")
        _require_nonempty_string(agent.get("name"), f"{field}.name")
        if not _AGENT_ID_RE.fullmatch(agent_id):
            raise ConfigurationError(f"{field}.id is not a safe agent identifier")
        if not _PROFILE_RE.fullmatch(profile):
            raise ConfigurationError(f"{field}.profile is not a safe Hermes profile name")
        if agent_id in agent_ids:
            raise ConfigurationError(f"duplicate agent id: {agent_id}")
        agent_ids.add(agent_id)

    if REQUIRED_LEAD_AGENT_ID not in agent_ids:
        raise ConfigurationError(
            f"agents must include required id {REQUIRED_LEAD_AGENT_ID!r}; "
            "the launcher uses this agent as the research lead"
        )

    soul_root = (config_root or CONFIG_PATH.parent) / "config" / "souls"
    for agent_id in sorted(agent_ids):
        _validate_role_soul(agent_id, soul_root / f"{agent_id}.md")

    phases = cfg.get("phases")
    if not isinstance(phases, list) or not phases:
        raise ConfigurationError("phases must be a non-empty list")
    phase_slugs: set[str] = set()
    phase_folders: dict[str, str] = {}
    for index, phase in enumerate(phases):
        field = f"phases[{index}]"
        if not isinstance(phase, dict):
            raise ConfigurationError(f"{field} must be a mapping")
        slug = _require_nonempty_string(phase.get("slug"), f"{field}.slug")
        if not _PHASE_SLUG_RE.fullmatch(slug):
            raise ConfigurationError(f"{field}.slug must look like 01-phase-name")
        if slug in phase_slugs:
            raise ConfigurationError(f"duplicate phase slug: {slug}")
        phase_slugs.add(slug)

    playbook_root = (config_root or CONFIG_PATH.parent) / "config" / "phases"
    for index, phase in enumerate(phases):
        field = f"phases[{index}]"
        slug = phase["slug"]
        _require_nonempty_string(phase.get("name"), f"{field}.name")
        _require_nonempty_string(phase.get("description"), f"{field}.description")
        pattern = _require_nonempty_string(phase.get("pattern"), f"{field}.pattern")
        if pattern not in _ALLOWED_PATTERNS:
            allowed = ", ".join(sorted(_ALLOWED_PATTERNS))
            raise ConfigurationError(f"{field}.pattern must be one of: {allowed}")
        folder = _validate_safe_relative_folder(phase.get("folder"), f"{field}.folder")
        normalized_folder = unicodedata.normalize(
            "NFC", PurePosixPath(folder).as_posix()
        ).casefold()
        prior_folder = phase_folders.get(normalized_folder)
        if prior_folder is not None:
            raise ConfigurationError(
                f"{field}.folder uses the same output directory as phase {prior_folder}"
            )
        phase_folders[normalized_folder] = slug

        members = phase.get("members")
        if not isinstance(members, list) or not members:
            raise ConfigurationError(f"{field}.members must be a non-empty list")
        if any(not isinstance(member, str) or member not in agent_ids for member in members):
            raise ConfigurationError(f"{field}.members must reference configured agent ids")
        if len(set(members)) != len(members):
            raise ConfigurationError(f"{field}.members cannot contain duplicates")

        proof_audit = phase.get("proof_audit")
        if slug == "03-theoretical-justification":
            if not isinstance(proof_audit, dict) or set(proof_audit) != {"plans", "stage"}:
                raise ConfigurationError(
                    f"{field}.proof_audit must contain exactly plans and stage"
                )
            expected_plans = ["standard", "standard_with_audit", "audit_only"]
            if proof_audit.get("plans") != expected_plans:
                raise ConfigurationError(
                    f"{field}.proof_audit.plans must contain standard, "
                    "standard_with_audit, and audit_only in that order"
                )
            audit_stage = proof_audit.get("stage")
            if not isinstance(audit_stage, dict) or set(audit_stage) != {
                "role", "name", "description"
            }:
                raise ConfigurationError(
                    f"{field}.proof_audit.stage must contain exactly role, name, "
                    "and description"
                )
            audit_role = _require_nonempty_string(
                audit_stage.get("role"), f"{field}.proof_audit.stage.role"
            )
            _require_nonempty_string(
                audit_stage.get("name"), f"{field}.proof_audit.stage.name"
            )
            _require_nonempty_string(
                audit_stage.get("description"),
                f"{field}.proof_audit.stage.description",
            )
            if audit_role != "paper_reviewer" or audit_role not in members:
                raise ConfigurationError(
                    f"{field}.proof_audit.stage.role must be paper_reviewer and "
                    "listed in phase members"
                )
        elif proof_audit is not None:
            raise ConfigurationError(
                f"{field}.proof_audit is only valid for Phase 03"
            )

        gates = phase.get("gated_by")
        if not isinstance(gates, list):
            raise ConfigurationError(f"{field}.gated_by must be a list")
        if len(set(gates)) != len(gates):
            raise ConfigurationError(f"{field}.gated_by cannot contain duplicates")
        for gate in gates:
            if not isinstance(gate, str) or gate not in phase_slugs:
                raise ConfigurationError(f"{field}.gated_by references an unknown phase")
            if gate == slug:
                raise ConfigurationError(f"{field}.gated_by cannot reference itself")

        context_from = phase.get("context_from", [])
        if not isinstance(context_from, list):
            raise ConfigurationError(f"{field}.context_from must be a list")
        if len(set(context_from)) != len(context_from):
            raise ConfigurationError(f"{field}.context_from cannot contain duplicates")
        for source in context_from:
            if not isinstance(source, str) or source not in phase_slugs:
                raise ConfigurationError(f"{field}.context_from references an unknown phase")
            if source == slug:
                raise ConfigurationError(f"{field}.context_from cannot reference itself")

        stages = phase.get("stages")
        if pattern == "sequential":
            if not isinstance(stages, list) or not stages:
                raise ConfigurationError(f"{field}.stages must define the sequential pipeline")
            for stage_index, stage in enumerate(stages):
                stage_field = f"{field}.stages[{stage_index}]"
                if not isinstance(stage, dict):
                    raise ConfigurationError(f"{stage_field} must be a mapping")
                if set(stage) != {"role", "name", "description"}:
                    raise ConfigurationError(
                        f"{stage_field} must contain exactly role, name, and description"
                    )
                role = _require_nonempty_string(stage.get("role"), f"{stage_field}.role")
                _require_nonempty_string(stage.get("name"), f"{stage_field}.name")
                _require_nonempty_string(stage.get("description"), f"{stage_field}.description")
                if role not in members:
                    raise ConfigurationError(f"{stage_field}.role must be listed in phase members")
            stage_count = len(stages)
            if phase.get("rounds") is None:
                phase["rounds"] = {
                    "min": stage_count,
                    "default": stage_count,
                    "max": stage_count,
                }
            rounds = _validate_rounds(phase["rounds"], f"{field}.rounds")
            if set(rounds.values()) != {stage_count}:
                raise ConfigurationError(
                    f"{field}.rounds must be fixed at the {stage_count} configured stages"
                )
        else:
            if stages is not None:
                raise ConfigurationError(f"{field}.stages is only valid for sequential phases")
            rounds = _validate_rounds(phase.get("rounds"), f"{field}.rounds")
            if pattern == "debate" and rounds["min"] < 2:
                raise ConfigurationError(f"{field}.rounds.min must be at least 2 for debate")

        phase_dir = playbook_root / slug
        required_playbooks = [phase_dir / "_lead.md", phase_dir / "_phase.md"]
        required_playbooks.extend(phase_dir / f"{member}.md" for member in members)
        missing = [path for path in required_playbooks if not path.is_file()]
        if missing:
            names = ", ".join(str(path) for path in missing)
            raise ConfigurationError(f"{field} is missing required playbooks: {names}")

    _validate_gate_dag(phases)
    return cfg


def load_config() -> dict:
    """Load and fully validate ``config.yaml`` using strict UTF-8."""
    try:
        metadata = CONFIG_PATH.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            raise ConfigurationError(
                f"configuration must be a regular file: {CONFIG_PATH}"
            )
        if metadata.st_size > MAX_CONFIG_BYTES:
            raise ConfigurationError(
                f"configuration exceeds the {MAX_CONFIG_BYTES:,}-byte safety limit"
            )
        with CONFIG_PATH.open("rb") as handle:
            payload = handle.read(MAX_CONFIG_BYTES + 1)
    except OSError as exc:
        raise ConfigurationError(f"cannot read configuration at {CONFIG_PATH}: {exc}") from exc
    if len(payload) > MAX_CONFIG_BYTES:
        raise ConfigurationError(
            f"configuration exceeds the {MAX_CONFIG_BYTES:,}-byte safety limit"
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigurationError(
            f"configuration is not valid UTF-8: {CONFIG_PATH}"
        ) from exc
    try:
        cfg = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {CONFIG_PATH}: {exc}") from exc
    return validate_config(cfg, config_root=CONFIG_PATH.parent)


def _resolve_workspace() -> Path:
    """Resolve the explicitly configured workspace, with no silent fallback."""
    cfg = load_config()
    raw_workspace = cfg["hub"]["workspace_dir"]
    candidate = Path(raw_workspace).expanduser()
    if not candidate.is_absolute():
        candidate = CONFIG_PATH.parent / candidate
    return candidate.resolve(strict=False)


def get_workspace_dir() -> Path:
    return _resolve_workspace()


def get_db_path() -> Path:
    return get_workspace_dir() / "hub.db"


def get_projects_dir() -> Path:
    return get_workspace_dir() / "projects"


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    """Yield a configured SQLite connection and always close it."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate_projects_table(conn: sqlite3.Connection) -> None:
    """Apply additive migrations supported for earlier project registries."""
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
    }
    if "id" not in columns or "name" not in columns:
        raise RuntimeError("existing projects table is incompatible: id and name are required")

    additions = {
        "description": "TEXT",
        "goal": "TEXT",
        "status": "TEXT DEFAULT 'active'",
        "workflow_name": "TEXT DEFAULT 'default'",
        "current_iteration": "INTEGER DEFAULT 0",
        "max_iterations": "INTEGER DEFAULT 10",
        "directory_name": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }
    for column, declaration in additions.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE projects ADD COLUMN {column} {declaration}")

    now = "CURRENT_TIMESTAMP"
    conn.execute("UPDATE projects SET status = 'active' WHERE status IS NULL")
    conn.execute("UPDATE projects SET workflow_name = 'default' WHERE workflow_name IS NULL")
    conn.execute("UPDATE projects SET current_iteration = 0 WHERE current_iteration IS NULL")
    conn.execute("UPDATE projects SET max_iterations = 10 WHERE max_iterations IS NULL")
    conn.execute(f"UPDATE projects SET created_at = {now} WHERE created_at IS NULL")
    conn.execute(f"UPDATE projects SET updated_at = {now} WHERE updated_at IS NULL")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_directory_name "
        "ON projects(directory_name)"
    )
    conn.execute("PRAGMA user_version = 1")


def init_db(*, verbose: bool = True) -> Path:
    """Create or additively migrate the project registry and workspace roots."""
    workspace = get_workspace_dir()
    workspace.mkdir(parents=True, exist_ok=True)
    get_projects_dir().mkdir(parents=True, exist_ok=True)
    try:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"cannot read database schema at {SCHEMA_PATH}: {exc}") from exc

    with _schema_lock:
        with get_db() as conn:
            # BEGIN IMMEDIATE serializes additive migrations across web workers.
            conn.executescript(f"BEGIN IMMEDIATE;\n{schema}")
            _migrate_projects_table(conn)
    if verbose:
        print(f"[hub] Database initialized at {get_db_path()}")
    return get_db_path()


def get_agents(cfg: dict) -> List[dict]:
    return cfg.get("agents", [])


def get_agent(cfg: dict, agent_id: str) -> Optional[dict]:
    return next((agent for agent in get_agents(cfg) if agent["id"] == agent_id), None)


def get_phases_config(cfg: dict) -> List[dict]:
    return cfg.get("phases", [])


def get_phase_config(cfg: dict, slug: str) -> Optional[dict]:
    return next((phase for phase in get_phases_config(cfg) if phase["slug"] == slug), None)


def _slugify_project_name(name: str) -> str:
    """Create a readable Unicode slug containing no filesystem separators."""
    normalized = unicodedata.normalize("NFKC", name).strip().casefold()
    pieces: list[str] = []
    separator_pending = False
    for character in normalized:
        category = unicodedata.category(character)
        if category[0] in {"L", "N"}:
            if separator_pending and pieces:
                pieces.append("-")
            pieces.append(character)
            separator_pending = False
        elif category[0] == "M" and pieces and pieces[-1] != "-":
            pieces.append(character)
        else:
            separator_pending = bool(pieces)
    slug = "".join(pieces).strip("-")[:PROJECT_SLUG_MAX_LENGTH].rstrip("-")
    return slug or "project"


def _validated_project_path(directory_name: str) -> Path:
    if (
        not isinstance(directory_name, str)
        or not directory_name
        or directory_name in {".", ".."}
        or "/" in directory_name
        or "\\" in directory_name
        or ":" in directory_name
        or "\x00" in directory_name
    ):
        raise RuntimeError("stored project directory name is unsafe")
    projects_root = get_projects_dir().resolve(strict=False)
    candidate = projects_root / directory_name
    try:
        metadata = candidate.lstat()
    except FileNotFoundError:
        metadata = None
    except OSError as exc:
        raise RuntimeError(f"project directory is unavailable: {candidate}") from exc
    if metadata is not None and _metadata_is_link_or_reparse(metadata):
        raise RuntimeError(
            f"project directory must not be a symbolic link or reparse point: {candidate}"
        )
    resolved = candidate.resolve(strict=False)
    if resolved != projects_root and projects_root not in resolved.parents:
        raise RuntimeError("project directory resolves outside the projects root")
    if metadata is not None:
        try:
            current_metadata = candidate.lstat()
        except OSError as exc:
            raise RuntimeError(
                f"project directory changed during validation: {candidate}"
            ) from exc
        if (
            _metadata_is_link_or_reparse(current_metadata)
            or not os.path.samestat(metadata, current_metadata)
        ):
            raise RuntimeError(
                f"project directory changed during validation: {candidate}"
            )
    return candidate


def _artifact_directories(cfg: dict) -> list[PurePosixPath]:
    paths = {
        PurePosixPath("phase-summaries"),
        PurePosixPath("references"),
        PurePosixPath("ideas"),
        PurePosixPath("draft"),
        PurePosixPath("numerical"),
    }
    for phase in get_phases_config(cfg):
        paths.add(PurePosixPath(phase["folder"]))
    return sorted(paths, key=lambda path: (len(path.parts), path.as_posix()))


def _create_project_tree(
    project_dir: Path,
    *,
    cfg: dict,
    setting_content: str,
) -> None:
    created_root = False
    try:
        project_dir.mkdir(parents=False, exist_ok=False)
        created_root = True
        for relative_path in _artifact_directories(cfg):
            (project_dir / Path(*relative_path.parts)).mkdir(parents=True, exist_ok=True)
        (project_dir / "setting.md").write_text(
            setting_content,
            encoding="utf-8",
            newline="\n",
        )
    except BaseException:
        if created_root:
            shutil.rmtree(project_dir, ignore_errors=True)
        raise


def create_project(
    name: str,
    description: str = "",
    brief: str = "",
    max_iterations: int = 10,
) -> int:
    """Create one project while workspace replacement is excluded."""

    with operation_lock():
        return _create_project_locked(name, description, brief, max_iterations)


def _create_project_locked(
    name: str,
    description: str = "",
    brief: str = "",
    max_iterations: int = 10,
) -> int:
    """Create a project registry row and its contained workspace atomically."""
    cfg = load_config()
    clean_name = _require_nonempty_string(name, "project name")
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer")
    init_db(verbose=False)

    project_dir: Optional[Path] = None
    project_tree_created = False
    control_dir: Optional[Path] = None
    control_tree_created = False
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO projects (name, description, goal, max_iterations) "
                "VALUES (?, ?, ?, ?)",
                (clean_name, description, brief, max_iterations),
            )
            project_id = int(cursor.lastrowid)
            directory_name = (
                f"project-{project_id:03d}-{_slugify_project_name(clean_name)}"
            )
            project_dir = _validated_project_path(directory_name)
            conn.execute(
                "UPDATE projects SET directory_name = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (directory_name, project_id),
            )
            _create_project_tree(
                project_dir,
                cfg=cfg,
                setting_content=_build_setting_md(clean_name, description, brief),
            )
            project_tree_created = True
            from scripts import project_state

            control_dir = project_state.state_dir(project_dir)
            control_dir.mkdir(parents=True, exist_ok=False)
            control_tree_created = True
            project_state.init(
                project_dir,
                f"project-{project_id:03d}",
                _slugify_project_name(clean_name),
                clean_name,
                phase_slugs=[phase["slug"] for phase in get_phases_config(cfg)],
                dependencies={
                    phase["slug"]: list(phase.get("gated_by", []))
                    for phase in get_phases_config(cfg)
                },
            )
    except BaseException:
        if project_tree_created and project_dir is not None and project_dir.exists():
            try:
                shutil.rmtree(project_dir)
            except OSError:
                pass
        if control_tree_created and control_dir is not None and control_dir.exists():
            try:
                shutil.rmtree(control_dir)
            except OSError:
                pass
        raise

    print(f"[hub] Created project #{project_id}: {clean_name}")
    print(f"      Folder: {project_dir}")
    return project_id


def _build_setting_md(name: str, description: str, brief: str) -> str:
    parts = [f"# {name}\n"]
    if description:
        parts.append(f"_{description}_\n")
    parts.append("## Project Description\n")
    parts.append(
        brief.strip()
        or "[Describe the project, focused domain, priorities, and constraints.]"
    )
    parts.append("")
    return "\n".join(parts)


def list_projects() -> List[sqlite3.Row]:
    init_db(verbose=False)
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM projects ORDER BY created_at DESC, id DESC"
        ).fetchall()


def get_project(project_id: int) -> Optional[sqlite3.Row]:
    init_db(verbose=False)
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()


def get_project_dir(project_id: int) -> Optional[Path]:
    """Return a contained project directory, migrating old rows on discovery."""
    project = get_project(project_id)
    if project is None:
        return None

    directory_name = project["directory_name"]
    if directory_name:
        candidate = _validated_project_path(directory_name)
        if candidate.is_dir():
            return candidate

    pattern = f"project-{project_id:03d}-*"
    matches: list[Path] = []
    for candidate in sorted(get_projects_dir().glob(pattern), key=lambda path: path.name):
        if not candidate.is_dir():
            continue
        safe_candidate = _validated_project_path(candidate.name)
        if safe_candidate.resolve(strict=False) == candidate.resolve(strict=False):
            matches.append(safe_candidate)
    if not matches:
        return None
    if len(matches) > 1:
        raise RuntimeError(
            f"multiple workspace directories found for project #{project_id}"
        )

    discovered = matches[0]
    with get_db() as conn:
        conn.execute(
            "UPDATE projects SET directory_name = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (discovered.name, project_id),
        )
    return discovered


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research Hub workspace utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="validate configuration and initialize the workspace")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "init":
        load_config()
        init_db(verbose=True)
        return 0
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConfigurationError as exc:
        print(f"[hub] Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
