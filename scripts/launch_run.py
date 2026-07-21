#!/usr/bin/env python3
"""Launch and supervise explicit, user-directed Research Hub phase runs.

The launcher prepares one run and delegates its internal work to the configured
research lead. It never starts another phase and it never approves a result.
The lead's final action submits an immutable summary for user review.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
HUB_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(HUB_DIR))

import project_state
import profile_skills


HUB_CONFIG = HUB_DIR / "config.yaml"
PHASES_DIR = HUB_DIR / "config" / "phases"
TEAM_DIR = HUB_DIR / "config" / "team"
SOULS_DIR = HUB_DIR / "config" / "souls"
MANIFEST_SCHEMA_VERSION = 8
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
MAX_COMMAND_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_PROCESS_CONTROL_OUTPUT_BYTES = 256 * 1024
MAX_RUN_LOG_BYTES = 64 * 1024 * 1024
PROCESS_OUTPUT_CHUNK_BYTES = 64 * 1024
PROCESS_READER_JOIN_SECONDS = 2.0
PROCESS_TREE_TERMINATION_SECONDS = 5.0
RUN_LOG_LIMIT_MARKER = (
    b"\n[Research Hub stopped this run because Hermes output exceeded the "
    b"run-log safety limit.]\n"
)
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
PAPER_WRITING_PHASE = "06-paper-writing"
THEORETICAL_ANALYSIS_PHASE = "03-theoretical-justification"
NUMERICAL_VALIDATION_PHASE = "04-numerical-validation"
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


def _source_baseline_status(source_baseline: Mapping[str, Any]) -> str:
    """Read baseline status while retaining frozen schema 1 runs."""

    field = (
        "source_baseline_status"
        if source_baseline.get("schema_version") == 2
        else "provenance"
    )
    return str(source_baseline.get(field, "")).strip()


def _configured_proof_audit(
    phase: Mapping[str, Any],
) -> tuple[list[str], dict[str, str]]:
    """Return the validated Phase 03 plan list and reviewer stage."""

    expected_plans = [
        THEORY_PLAN_STANDARD,
        THEORY_PLAN_STANDARD_WITH_AUDIT,
        THEORY_PLAN_AUDIT_ONLY,
    ]
    configured = phase.get("proof_audit")
    if configured is None:
        plans = phase.get("available_run_plans", expected_plans)
        stage: Any = {
            "role": PAPER_REVIEWER_ROLE,
            "name": "Audit the final theoretical analysis independently",
            "description": (
                "Check the exact sealed theory artifact, assumptions, proof "
                "dependencies, and central conclusions without revising the theory."
            ),
        }
    else:
        if not isinstance(configured, Mapping) or set(configured) != {"plans", "stage"}:
            raise LaunchError("Phase 03 proof_audit must contain plans and stage")
        plans = configured.get("plans")
        stage = configured.get("stage")
    if plans != expected_plans:
        raise LaunchError(
            "Phase 03 proof_audit.plans must declare standard, "
            "standard_with_audit, and audit_only in that order"
        )
    if not isinstance(stage, Mapping) or set(stage) != {"role", "name", "description"}:
        raise LaunchError(
            "Phase 03 proof_audit.stage must contain role, name, and description"
        )
    normalized = {
        key: str(stage.get(key, "")).strip()
        for key in ("role", "name", "description")
    }
    if any(not value for value in normalized.values()):
        raise LaunchError("Phase 03 proof_audit.stage fields must be nonempty")
    if normalized["role"] != PAPER_REVIEWER_ROLE:
        raise LaunchError("Phase 03 proof audit must be assigned to paper_reviewer")
    return list(plans), normalized


def paper_review_only_phase(phase: Mapping[str, Any]) -> dict[str, Any]:
    """Return the two-stage plan for reviewing an exact existing manuscript."""

    review_phase = dict(phase)
    review_phase["members"] = [PAPER_REVIEWER_ROLE]
    review_phase["stages"] = [
        {
            "role": PAPER_REVIEWER_ROLE,
            "name": "Read the selected manuscript independently",
            "description": (
                "Record a first-reader assessment using only the sealed manuscript."
            ),
        },
        {
            "role": PAPER_REVIEWER_ROLE,
            "name": "Assess the selected manuscript against the evidence",
            "description": (
                "Compare the preserved first reading with the internal scientific record."
            ),
        },
    ]
    review_phase["rounds"] = {"min": 2, "default": 2, "max": 2}
    review_phase["review_only"] = True
    return review_phase


def _phase_with_proof_audit(phase: Mapping[str, Any]) -> dict[str, Any]:
    """Append the user-selected independent proof audit to Phase 03."""

    _, audit_stage = _configured_proof_audit(phase)
    audit_phase = dict(phase)
    members = [str(role) for role in phase.get("members", [])]
    if PAPER_REVIEWER_ROLE not in members:
        members.append(PAPER_REVIEWER_ROLE)
    audit_phase["members"] = members
    stages = [dict(stage) for stage in phase.get("stages", [])]
    stages.append(audit_stage)
    audit_phase["stages"] = stages
    count = len(stages)
    audit_phase["rounds"] = {"min": count, "default": count, "max": count}
    audit_phase["proof_audit"] = True
    audit_phase["run_plan"] = THEORY_PLAN_STANDARD_WITH_AUDIT
    return audit_phase


def _phase_for_theory_plan(
    phase: Mapping[str, Any], plan: str
) -> dict[str, Any]:
    """Return the exact Phase 03 stage plan selected by the user."""

    if str(phase.get("slug")) != THEORETICAL_ANALYSIS_PHASE:
        raise LaunchError("Theory run plans are only valid in Phase 03")
    plans, audit_stage = _configured_proof_audit(phase)
    if plan not in plans:
        raise LaunchError(f"Unknown Phase 03 run plan: {plan!r}")
    if plan == THEORY_PLAN_STANDARD:
        selected = dict(phase)
        selected["members"] = list(dict.fromkeys(
            str(stage["role"]) for stage in phase.get("stages", [])
        ))
        selected["proof_audit"] = False
        selected["run_plan"] = plan
        return selected
    if plan == THEORY_PLAN_STANDARD_WITH_AUDIT:
        return _phase_with_proof_audit(phase)
    selected = dict(phase)
    selected["members"] = [PAPER_REVIEWER_ROLE]
    selected["stages"] = [audit_stage]
    selected["rounds"] = {"min": 1, "default": 1, "max": 1}
    selected["proof_audit"] = True
    selected["audit_only"] = True
    selected["run_plan"] = plan
    return selected


class LaunchError(RuntimeError):
    """A run could not be prepared or launched safely."""


class _ProcessOutputLimitExceeded(LaunchError):
    """A supervised subprocess exceeded its output byte budget."""


def _load_hub_config() -> dict[str, Any]:
    """Load the validated hub configuration."""

    import hub

    return hub.load_config()


def _phase_config(config: Mapping[str, Any], phase_slug: str) -> dict[str, Any]:
    for phase in config.get("phases", []):
        if phase.get("slug") == phase_slug:
            return dict(phase)
    raise LaunchError(f"Unknown phase: {phase_slug}")


def _dependencies(config: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        str(phase["slug"]): [str(item) for item in phase.get("gated_by", [])]
        for phase in config.get("phases", [])
    }


def _phase_slugs(config: Mapping[str, Any]) -> list[str]:
    return [str(phase["slug"]) for phase in config.get("phases", [])]


def _role_profiles(config: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(agent["id"]): str(agent["profile"])
        for agent in config.get("agents", [])
    }


def _should_preload_recommended_skill(
    phase_slug: str,
    role: str,
    skill_name: str,
    *,
    review_only: bool = False,
) -> bool:
    """Return whether one exact recommended skill applies to this run mode."""

    if role == PAPER_REVIEWER_ROLE and skill_name == PAPER_REVIEWER_SKILL:
        return True
    return (
        phase_slug == PAPER_WRITING_PHASE
        and not review_only
        and role in PAPER_WRITING_SKILL_ROLES
        and skill_name == PAPER_WRITING_SKILL
    )


def _recommended_skill_status_record(
    status: profile_skills.SkillStatus,
    *,
    preload: bool,
) -> dict[str, Any]:
    """Normalize the read-only fields that determine safe skill preloading."""

    return {
        "name": status.skill,
        "state": status.state,
        "reason": status.reason,
        "expected_digest": status.expected_digest,
        "installed_digest": status.installed_digest,
        "source_revision": status.source_revision,
        "profile_path": status.profile_path,
        "managed": status.managed,
        "preload": preload,
    }


def _recommended_skills_snapshot(
    config: Mapping[str, Any],
    phase_slug: str,
    *,
    effective_phase: Mapping[str, Any] | None = None,
    hermes_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Describe relevant profile skills without changing any Hermes profile."""

    phase = (
        dict(effective_phase)
        if effective_phase is not None
        else _phase_config(config, phase_slug)
    )
    review_only = bool(phase.get("review_only", False))
    roles = {str(role) for role in phase.get("members", [])}
    roles.add("research_lead")
    profiles = _role_profiles(config)
    try:
        bundled = profile_skills.load_manifest()
        resolved_hermes_root = (
            Path(hermes_root)
            if hermes_root is not None
            else profile_skills.resolve_hermes_root()
        )
    except (profile_skills.ProfileSkillsError, OSError, ValueError):
        return {
            "schema_version": 1,
            "source_revision": None,
            "roles": {},
        }

    role_records: dict[str, Any] = {}
    for role in sorted(roles):
        try:
            requirements = profile_skills.role_requirements(
                role,
                manifest=bundled,
            )
        except (KeyError, ValueError):
            continue
        requirements = tuple(
            name
            for name in requirements
            if _should_preload_recommended_skill(
                phase_slug,
                role,
                name,
                review_only=review_only,
            )
        )
        if not requirements:
            continue
        profile = str(profiles.get(role, ""))
        if not profile:
            role_records[role] = {
                "profile": "",
                "skills": [
                    {
                        "name": name,
                        "state": "profile_missing",
                        "reason": "profile_unmapped",
                        "expected_digest": bundled.skills[name].digest,
                        "installed_digest": None,
                        "source_revision": bundled.source_revision,
                        "profile_path": "",
                        "managed": False,
                        "preload": False,
                    }
                    for name in requirements
                ],
            }
            continue
        try:
            statuses = profile_skills.profile_skill_statuses(
                profile,
                requirements,
                manifest=bundled,
                hermes_root=resolved_hermes_root,
            )
        except (profile_skills.ProfileSkillsError, OSError, ValueError, KeyError):
            role_records[role] = {
                "profile": profile,
                "skills": [
                    {
                        "name": name,
                        "state": "invalid",
                        "reason": "status_unavailable",
                        "expected_digest": bundled.skills[name].digest,
                        "installed_digest": None,
                        "source_revision": bundled.source_revision,
                        "profile_path": "",
                        "managed": False,
                        "preload": False,
                    }
                    for name in requirements
                ],
            }
            continue
        role_records[role] = {
            "profile": profile,
            "skills": [
                _recommended_skill_status_record(
                    statuses[name],
                    preload=(
                        statuses[name].state == "current"
                        and _should_preload_recommended_skill(
                            phase_slug,
                            role,
                            name,
                            review_only=review_only,
                        )
                    ),
                )
                for name in requirements
            ],
        }
    return {
        "schema_version": 1,
        "source_revision": bundled.source_revision,
        "roles": role_records,
    }


def _launch_instruction_fingerprint(path: Path) -> dict[str, Any]:
    """Describe one launch instruction without following a linked final path."""

    relative = path.relative_to(HUB_DIR).as_posix()
    try:
        metadata = path.lstat()
    except OSError:
        return {"path": relative, "state": "missing"}
    if _metadata_is_link_or_reparse(metadata):
        return {"path": relative, "state": "linked"}
    if not stat.S_ISREG(metadata.st_mode):
        return {"path": relative, "state": "not_regular"}
    try:
        payload = _bounded_bytes(
            path,
            label=f"launch instruction {relative}",
            max_bytes=MAX_EMBEDDED_SOUL_BYTES,
        )
    except (OSError, LaunchError):
        return {"path": relative, "state": "unreadable_or_oversize"}
    return {
        "path": relative,
        "state": "regular",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }


def launch_plan_version(
    config: Mapping[str, Any],
    phase_slug: str,
    *,
    effective_phase: Mapping[str, Any] | None = None,
    hermes_root: str | os.PathLike[str] | None = None,
    recommended_skills_snapshot: Mapping[str, Any] | None = None,
) -> str:
    """Fingerprint the exact phase configuration and instruction set shown to a user."""

    phase = (
        dict(effective_phase)
        if effective_phase is not None
        else _phase_config(config, phase_slug)
    )
    try:
        resolved_hermes_root = (
            Path(hermes_root)
            if hermes_root is not None
            else profile_skills.resolve_hermes_root()
        )
    except (profile_skills.ProfileSkillsError, OSError, ValueError):
        resolved_hermes_root = None
    roles = {str(role) for role in phase.get("members", [])}
    roles.add("research_lead")
    agents = sorted(
        (
            dict(agent)
            for agent in config.get("agents", [])
            if isinstance(agent, Mapping) and str(agent.get("id", "")) in roles
        ),
        key=lambda agent: str(agent.get("id", "")),
    )
    instruction_paths = [
        TEAM_DIR / "charter.md",
        TEAM_DIR / "norms.md",
        *[SOULS_DIR / f"{role}.md" for role in sorted(roles)],
        PHASES_DIR / phase_slug / "_lead.md",
        PHASES_DIR / phase_slug / "_phase.md",
        *[
            PHASES_DIR / phase_slug / f"{role}.md"
            for role in phase.get("members", [])
        ],
    ]
    hub_settings = config.get("hub", {})
    payload = {
        "schema_version": 1,
        "phase": phase,
        "agents": agents,
        "execution": {
            "allow_unattended_tools": bool(
                hub_settings.get("allow_unattended_tools", False)
            ),
            "run_timeout_minutes": hub_settings.get("run_timeout_minutes", 120),
            "hermes_root": (
                str(resolved_hermes_root)
                if resolved_hermes_root is not None
                else None
            ),
        },
        "instructions": [
            _launch_instruction_fingerprint(path) for path in instruction_paths
        ],
        "recommended_skills": (
            recommended_skills_snapshot
            if recommended_skills_snapshot is not None
            else _recommended_skills_snapshot(
                config,
                phase_slug,
                effective_phase=phase,
                hermes_root=resolved_hermes_root,
            )
        ),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _method_identity(stable_id: str, version: str) -> dict[str, str]:
    """Validate an exact method identity supplied by a user or decision record."""

    normalized = {
        "kind": "method",
        "stable_id": str(stable_id).strip(),
        "version": str(version).strip(),
    }
    for label in ("stable_id", "version"):
        value = normalized[label]
        if not value or len(value) > 200:
            raise LaunchError(f"The method {label.replace('_', ' ')} is invalid")
        if any(
            not (
                character.isascii()
                and (character.isalnum() or character in {"-", "_", ".", "/"})
            )
            for character in value
        ):
            raise LaunchError(
                f"The method {label.replace('_', ' ')} must use ASCII letters, "
                "digits, hyphens, underscores, periods, or slashes"
            )
    return normalized


def _round_count(phase: Mapping[str, Any], requested: int | None) -> int:
    policy = phase.get("rounds", {})
    minimum = int(policy.get("min", 1))
    default = int(policy.get("default", minimum))
    maximum = int(policy.get("max", default))
    if phase.get("pattern") == "sequential":
        fixed = len(phase.get("stages", []))
        if fixed < 1:
            raise LaunchError(f"Sequential phase {phase['slug']} has no configured stages")
        return fixed
    value = default if requested is None else int(requested)
    if value < minimum or value > maximum:
        raise LaunchError(
            f"{phase.get('name', phase['slug'])} allows {minimum} to {maximum} rounds; "
            f"received {value}."
        )
    return value


def _shell_join(arguments: Sequence[str | Path]) -> str:
    """Serialize a command for the platform shell used by Hermes terminal."""

    values = [str(value) for value in arguments]
    if os.name == "nt":
        quoted = ["'" + value.replace("'", "''") + "'" for value in values]
        return "& " + " ".join(quoted)
    return shlex.join(values)


def _assign_windows_kill_job(process: subprocess.Popen[Any]) -> Any | None:
    """Place a Windows process tree in a job that dies when its handle closes."""

    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = 0x00002000
        if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ) or not kernel32.AssignProcessToJobObject(
            job, wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
        ):
            kernel32.CloseHandle(job)
            return None
        return job
    except Exception:
        return None


def _terminate_windows_job(job: Any) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject(job, 1)


def _close_windows_job(job: Any) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle(job)


def _terminate_windows_process_tree(pid: int) -> None:
    """Best-effort fallback when a Windows kill-on-close job is unavailable."""

    killer: subprocess.Popen[Any] | None = None
    try:
        killer = subprocess.Popen(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            killer.wait(timeout=PROCESS_TREE_TERMINATION_SECONDS)
        except subprocess.TimeoutExpired:
            killer.kill()
            killer.wait(timeout=PROCESS_TREE_TERMINATION_SECONDS)
    except (OSError, subprocess.SubprocessError):
        if killer is not None and killer.poll() is None:
            try:
                killer.kill()
            except OSError:
                pass


def _run_process_with_bounded_output(
    arguments: Sequence[str],
    *,
    timeout: int,
    max_output_bytes: int,
    merge_stderr: bool = False,
    output_writer: Callable[[bytes], None] | None = None,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a process while draining at most one combined output byte budget."""

    if max_output_bytes < 1:
        raise _ProcessOutputLimitExceeded(
            "No output budget remains for the external command"
        )
    command = [str(argument) for argument in arguments]
    popen_options: dict[str, Any] = {}
    if os.name == "nt":
        popen_options["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        popen_options["start_new_session"] = True
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
            env=(dict(environment) if environment is not None else None),
            **popen_options,
        )
    except OSError as exc:
        raise LaunchError(f"Could not run {' '.join(command[:3])}: {exc}") from exc

    windows_job = _assign_windows_kill_job(process)
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    state_lock = threading.Lock()
    tree_lock = threading.Lock()
    overflow = threading.Event()
    termination_requested = threading.Event()
    reader_failures: list[BaseException] = []
    tree_terminated = False
    total = 0

    def stop_process() -> None:
        nonlocal tree_terminated, windows_job
        termination_requested.set()
        with tree_lock:
            if tree_terminated:
                return
            tree_terminated = True
            if os.name == "nt":
                if windows_job is not None:
                    try:
                        _terminate_windows_job(windows_job)
                    except OSError:
                        _terminate_windows_process_tree(process.pid)
                else:
                    _terminate_windows_process_tree(process.pid)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError:
                    if process.poll() is None:
                        try:
                            process.kill()
                        except OSError:
                            pass
            if process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass

    def release_process_tree() -> None:
        nonlocal tree_terminated, windows_job
        if os.name != "nt":
            return
        with tree_lock:
            if windows_job is not None:
                try:
                    _close_windows_job(windows_job)
                finally:
                    windows_job = None
                    tree_terminated = True

    def join_readers(timeout: float) -> list[threading.Thread]:
        deadline = time.monotonic() + timeout
        for reader in readers:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            reader.join(remaining)
        return [reader for reader in readers if reader.is_alive()]

    def wait_after_stop() -> int | None:
        try:
            return process.wait(timeout=PROCESS_TREE_TERMINATION_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
            try:
                return process.wait(timeout=PROCESS_TREE_TERMINATION_SECONDS)
            except subprocess.TimeoutExpired:
                return None

    def consume(name: str, stream: Any) -> None:
        nonlocal total
        try:
            while True:
                chunk = stream.read(PROCESS_OUTPUT_CHUNK_BYTES)
                if not chunk:
                    break
                with state_lock:
                    remaining = max_output_bytes - total
                    accepted = chunk[: max(0, remaining)]
                    total += len(accepted)
                    if len(accepted) != len(chunk):
                        overflow.set()
                if accepted:
                    if output_writer is None:
                        buffers[name].extend(accepted)
                    else:
                        output_writer(accepted)
                if overflow.is_set():
                    stop_process()
        except BaseException as exc:
            if not termination_requested.is_set():
                with state_lock:
                    reader_failures.append(exc)
            stop_process()
        finally:
            try:
                stream.close()
            except OSError:
                pass

    readers: list[threading.Thread] = []
    if process.stdout is not None:
        readers.append(
            threading.Thread(
                target=consume,
                args=("stdout", process.stdout),
                daemon=True,
            )
        )
    if not merge_stderr and process.stderr is not None:
        readers.append(
            threading.Thread(
                target=consume,
                args=("stderr", process.stderr),
                daemon=True,
            )
        )
    for reader in readers:
        reader.start()

    timed_out = False
    wait_failed = False
    try:
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_process()
        stopped_code = wait_after_stop()
        wait_failed = stopped_code is None
        return_code = stopped_code if stopped_code is not None else -1
    finally:
        release_process_tree()

    lingering_readers = join_readers(PROCESS_READER_JOIN_SECONDS)
    if lingering_readers:
        stop_process()
        lingering_readers = join_readers(PROCESS_READER_JOIN_SECONDS)

    stdout = bytes(buffers["stdout"]).decode("utf-8", errors="replace")
    stderr = bytes(buffers["stderr"]).decode("utf-8", errors="replace")
    if wait_failed:
        raise LaunchError(
            f"Could not terminate the process tree for {' '.join(command[:3])}"
        )
    if lingering_readers:
        raise LaunchError(
            f"Process-tree output did not close after termination: "
            f"{' '.join(command[:3])}"
        )
    if reader_failures:
        raise LaunchError(
            f"Could not record output from {' '.join(command[:3])}: "
            f"{reader_failures[0]}"
        ) from reader_failures[0]
    if timed_out:
        raise subprocess.TimeoutExpired(
            command, timeout, output=stdout, stderr=stderr
        )
    if overflow.is_set():
        raise _ProcessOutputLimitExceeded(
            f"External command output exceeded the {max_output_bytes:,}-byte safety limit: "
            f"{' '.join(command[:3])}"
        )
    return subprocess.CompletedProcess(command, return_code, stdout, stderr)


def _run_command(
    arguments: Sequence[str],
    *,
    timeout: int = 20,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return _run_process_with_bounded_output(
            arguments,
            timeout=timeout,
            max_output_bytes=MAX_COMMAND_OUTPUT_BYTES,
            environment=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LaunchError(f"Could not run {' '.join(arguments[:3])}: {exc}") from exc


def _hermes_environment(
    hermes_root: str | os.PathLike[str] | None,
    *,
    base: Mapping[str, str] | None = None,
) -> dict[str, str] | None:
    """Copy an environment and bind Hermes to one resolved profile root."""

    if hermes_root is None:
        return dict(base) if base is not None else None
    environment = dict(os.environ if base is None else base)
    for key in list(environment):
        if key.casefold() in {
            "hermes_home",
            "research_hub_hermes_root",
        }:
            environment.pop(key)
    root = str(Path(hermes_root))
    environment["HERMES_HOME"] = root
    environment["RESEARCH_HUB_HERMES_ROOT"] = root
    return environment


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


def _snapshot_leaf(
    value: Any, label: str, *, allow_extra: bool = False
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LaunchError(f"Frozen snapshot {label} must be a mapping")
    keys = set(value)
    required = {"path", "sha256"}
    if not required.issubset(keys) or (not allow_extra and keys != required):
        qualifier = "contain" if allow_extra else "contain exactly"
        raise LaunchError(
            f"Frozen snapshot {label} must {qualifier} path and sha256"
        )
    path = value.get("path")
    digest = value.get("sha256")
    if not isinstance(path, str) or not path.strip():
        raise LaunchError(f"Frozen snapshot {label}.path must be a nonempty string")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in digest)
    ):
        raise LaunchError(f"Frozen snapshot {label}.sha256 must be a SHA-256 digest")
    return value


def _manifest_schema_version(manifest: Mapping[str, Any]) -> int:
    value = manifest.get("schema_version", 1)
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value not in range(1, MANIFEST_SCHEMA_VERSION + 1)
    ):
        raise LaunchError(f"Unsupported run manifest schema version: {value!r}")
    return value


def _manifest_hermes_root(manifest: Mapping[str, Any]) -> Path | None:
    """Return a sealed Hermes root, while retaining manifests created earlier."""

    value = manifest.get("hermes_root")
    if value is None:
        return None
    if not isinstance(value, str) or not value or "\x00" in value:
        raise LaunchError("Run manifest hermes_root must be a nonempty path")
    root = Path(value)
    normalized = Path(os.path.abspath(value))
    if not root.is_absolute() or normalized != root or str(root) != value:
        raise LaunchError("Run manifest hermes_root must be an absolute normalized path")
    return root


def _is_sha256_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_recommended_skills_snapshot(manifest: Mapping[str, Any]) -> None:
    """Validate an optional read-only skill snapshot without consulting live state."""

    snapshot = manifest.get("recommended_skills")
    if snapshot is None:
        return
    if not isinstance(snapshot, Mapping) or set(snapshot) != {
        "schema_version",
        "source_revision",
        "roles",
    }:
        raise LaunchError("Run manifest recommended_skills has an invalid structure")
    if snapshot.get("schema_version") != 1:
        raise LaunchError("Run manifest recommended_skills schema is unsupported")
    source_revision = snapshot.get("source_revision")
    if source_revision is not None and (
        not isinstance(source_revision, str)
        or len(source_revision) != 40
        or any(character not in "0123456789abcdef" for character in source_revision)
    ):
        raise LaunchError("Run manifest recommended skill revision is invalid")
    roles = snapshot.get("roles")
    if not isinstance(roles, Mapping) or len(roles) > 32:
        raise LaunchError("Run manifest recommended skill roles are invalid")
    if source_revision is None and roles:
        raise LaunchError("Unavailable recommended skills must not declare role state")
    phase_slug = str(manifest.get("phase_slug", ""))
    phase = manifest.get("phase")
    review_only = bool(
        isinstance(phase, Mapping) and phase.get("review_only", False)
    )
    status_states = {
        "profile_missing",
        "missing",
        "current",
        "modified",
        "conflict",
        "invalid",
    }
    skill_keys = {
        "name",
        "state",
        "reason",
        "expected_digest",
        "installed_digest",
        "source_revision",
        "profile_path",
        "managed",
        "preload",
    }
    for role, role_record in roles.items():
        if not isinstance(role, str) or not role:
            raise LaunchError("Run manifest recommended skill role is invalid")
        if not isinstance(role_record, Mapping) or set(role_record) != {
            "profile",
            "skills",
        }:
            raise LaunchError(
                f"Run manifest recommended skills for {role} are invalid"
            )
        profile = role_record.get("profile")
        skills = role_record.get("skills")
        if not isinstance(profile, str) or not isinstance(skills, list):
            raise LaunchError(
                f"Run manifest recommended skills for {role} are invalid"
            )
        names: set[str] = set()
        for record in skills:
            if not isinstance(record, Mapping) or set(record) != skill_keys:
                raise LaunchError(
                    f"Run manifest recommended skill record for {role} is invalid"
                )
            name = record.get("name")
            state = record.get("state")
            reason = record.get("reason")
            installed_digest = record.get("installed_digest")
            if not isinstance(name, str) or not name or name in names:
                raise LaunchError(
                    f"Run manifest recommended skill name for {role} is invalid"
                )
            names.add(name)
            if state not in status_states or not isinstance(reason, str) or not reason:
                raise LaunchError(
                    f"Run manifest recommended skill status for {role} is invalid"
                )
            if not _is_sha256_digest(record.get("expected_digest")):
                raise LaunchError(
                    f"Run manifest recommended skill digest for {role} is invalid"
                )
            if installed_digest is not None and not _is_sha256_digest(
                installed_digest
            ):
                raise LaunchError(
                    f"Run manifest installed skill digest for {role} is invalid"
                )
            if record.get("source_revision") != source_revision:
                raise LaunchError(
                    f"Run manifest recommended skill revision for {role} is invalid"
                )
            if not isinstance(record.get("profile_path"), str):
                raise LaunchError(
                    f"Run manifest recommended skill path for {role} is invalid"
                )
            if type(record.get("managed")) is not bool or type(
                record.get("preload")
            ) is not bool:
                raise LaunchError(
                    f"Run manifest recommended skill flags for {role} are invalid"
                )
            if record["preload"] and (
                state != "current"
                or installed_digest != record["expected_digest"]
                or not _should_preload_recommended_skill(
                    phase_slug,
                    role,
                    name,
                    review_only=review_only,
                )
            ):
                raise LaunchError(
                    f"Run manifest cannot preload the recorded skill for {role}"
                )


def _verified_preloaded_skill_names(
    manifest: Mapping[str, Any],
    role: str,
) -> list[str]:
    """Recheck skills immediately before queue or chat start.

    This check controls whether the command starts. It does not monitor the
    profile after Hermes has accepted the queue or chat command.
    """

    snapshot = manifest.get("recommended_skills")
    if snapshot is None:
        return []
    _validate_recommended_skills_snapshot(manifest)
    roles = snapshot["roles"]
    role_record = roles.get(role)
    if not isinstance(role_record, Mapping):
        return []
    records = [record for record in role_record["skills"] if record["preload"]]
    if not records:
        return []
    profile = str(role_record["profile"])
    manifest_profiles = manifest.get("profiles")
    if not isinstance(manifest_profiles, Mapping):
        raise LaunchError("The run has no valid Hermes profile mapping")
    mapped_profile = str(manifest_profiles.get(role, ""))
    if not profile or profile != mapped_profile:
        raise LaunchError(
            f"The recorded Hermes profile for {role} no longer matches the run"
        )
    names = [str(record["name"]) for record in records]
    try:
        bundled = profile_skills.load_manifest()
        requirements = set(
            profile_skills.role_requirements(role, manifest=bundled)
        )
        if not set(names).issubset(requirements):
            raise LaunchError(
                f"The bundled skill recommendation for {role} changed after launch"
            )
        statuses = profile_skills.profile_skill_statuses(
            profile,
            names,
            manifest=bundled,
            hermes_root=_manifest_hermes_root(manifest),
        )
    except LaunchError:
        raise
    except (profile_skills.ProfileSkillsError, OSError, ValueError, KeyError) as exc:
        raise LaunchError(
            f"The recommended skill for {role} could not be verified before use"
        ) from exc
    for record in records:
        name = str(record["name"])
        live = _recommended_skill_status_record(statuses[name], preload=True)
        stable_fields = (
            "name",
            "state",
            "expected_digest",
            "installed_digest",
            "source_revision",
            "profile_path",
        )
        if any(live[field] != record[field] for field in stable_fields):
            raise LaunchError(
                f"The installed {name} skill changed after this run was prepared. "
                "Research Hub will not start this Hermes command. Review the "
                "profile and start a new run."
            )
    return names


def _validate_manifest_snapshot_schema(manifest: Mapping[str, Any]) -> None:
    """Require a complete v2 frozen-input inventory while retaining v1 reads."""

    _manifest_hermes_root(manifest)
    _validate_recommended_skills_snapshot(manifest)
    if _manifest_schema_version(manifest) == 1:
        return
    phase = manifest.get("phase")
    if not isinstance(phase, Mapping):
        raise LaunchError("Run manifest phase must be a mapping")
    members = phase.get("members")
    if not isinstance(members, list) or any(
        not isinstance(role, str) or not role for role in members
    ):
        raise LaunchError("Run manifest phase members must be a list of role names")
    required_roles = set(members) | {"research_lead"}
    snapshots = manifest.get("snapshots")
    if not isinstance(snapshots, Mapping):
        raise LaunchError("Run manifest snapshots must be a mapping")
    required_snapshot_keys = {"setting", "team", "souls", "playbooks", "summaries"}
    if set(snapshots) != required_snapshot_keys:
        raise LaunchError(
            "Run manifest snapshots must contain exactly setting, team, souls, "
            "playbooks, and summaries"
        )
    _snapshot_leaf(snapshots.get("setting"), "setting")

    team = snapshots.get("team")
    if not isinstance(team, Mapping) or set(team) != {"charter", "norms"}:
        raise LaunchError("Frozen snapshot team must contain exactly charter and norms")
    _snapshot_leaf(team.get("charter"), "team.charter")
    _snapshot_leaf(team.get("norms"), "team.norms")

    souls = snapshots.get("souls")
    if not isinstance(souls, Mapping) or set(souls) != required_roles:
        expected = ", ".join(sorted(required_roles))
        raise LaunchError(f"Frozen snapshot souls must contain exactly: {expected}")
    for role in sorted(required_roles):
        _snapshot_leaf(souls.get(role), f"souls.{role}")

    required_playbooks = {"_lead.md", "_phase.md"} | {
        f"{role}.md" for role in members
    }
    playbooks = snapshots.get("playbooks")
    if not isinstance(playbooks, Mapping) or set(playbooks) != required_playbooks:
        expected = ", ".join(sorted(required_playbooks))
        raise LaunchError(f"Frozen snapshot playbooks must contain exactly: {expected}")
    for name in sorted(required_playbooks):
        _snapshot_leaf(playbooks.get(name), f"playbooks.{name}")

    summaries = snapshots.get("summaries")
    if not isinstance(summaries, list):
        raise LaunchError("Frozen snapshot summaries must be a list")
    for index, entry in enumerate(summaries):
        _snapshot_leaf(entry, f"summaries[{index}]", allow_extra=True)

    if _manifest_schema_version(manifest) >= 3:
        outputs = manifest.get("submission_outputs")
        if not isinstance(outputs, Mapping):
            raise LaunchError("Run manifest submission_outputs must be a mapping")
        phase_slug = str(manifest.get("phase_slug", ""))
        paper_review = manifest.get("paper_review")
        full_paper_run = (
            phase_slug == PAPER_WRITING_PHASE
            and isinstance(paper_review, Mapping)
            and paper_review.get("kind") == "full"
        )
        expected_names = {"post_review_manuscript", "review_diff"} if full_paper_run else set()
        if set(outputs) != expected_names:
            raise LaunchError(
                "Run manifest submission_outputs do not match the selected run variant"
            )
        if full_paper_run:
            expected_paths = _paper_manuscript_paths(str(manifest.get("output_root", "")))
            expected = {
                "post_review_manuscript": (expected_paths["post_review"], False),
                "review_diff": (expected_paths["diff"], True),
            }
            for name, (expected_path, allow_empty) in expected.items():
                record = outputs.get(name)
                if not isinstance(record, Mapping):
                    raise LaunchError(f"Submission output {name} must be a mapping")
                if set(record) != {"path", "allow_empty"}:
                    raise LaunchError(
                        f"Submission output {name} must contain path and allow_empty"
                    )
                if Path(str(record.get("path", ""))).resolve() != expected_path.resolve():
                    raise LaunchError(
                        f"Submission output {name} does not match the Phase 6 plan"
                    )
                if record.get("allow_empty") is not allow_empty:
                    raise LaunchError(
                        f"Submission output {name} has an invalid empty-file policy"
                    )
    if _manifest_schema_version(manifest) >= 4:
        decision_path = manifest.get("decision_path")
        summary_path = manifest.get("summary_path")
        if not isinstance(decision_path, str) or not decision_path.strip():
            raise LaunchError("Run manifest decision_path must be a nonempty string")
        if not isinstance(summary_path, str) or not summary_path.strip():
            raise LaunchError("Run manifest summary_path must be a nonempty string")
        expected_decision_path = Path(summary_path).with_suffix(".decision.json").resolve()
        if Path(decision_path).resolve() != expected_decision_path:
            raise LaunchError(
                "Run manifest decision_path must be beside the immutable summary"
            )
    if _manifest_schema_version(manifest) >= 8:
        for field in ("phase_plan_version", "prerequisite_report_version"):
            digest = str(manifest.get(field, "")).strip().lower()
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise LaunchError(f"Run manifest {field} must be a SHA-256 digest")
        _validated_manifest_method_selection(manifest)
    if _manifest_schema_version(manifest) >= 5:
        phase_slug = str(manifest.get("phase_slug", ""))
        declared = manifest.get("protocol_checkpoint")
        if phase_slug != NUMERICAL_VALIDATION_PHASE:
            if declared is not None:
                raise LaunchError(
                    "A protocol checkpoint declaration is valid only for Phase 04"
                )
            return
        required_checkpoint_fields = {
            "schema_version",
            "path",
            "max_bytes",
        }
        if _manifest_schema_version(manifest) >= 6:
            required_checkpoint_fields.add("protocol_root")
        if not isinstance(declared, Mapping) or set(declared) != required_checkpoint_fields:
            raise LaunchError(
                "Phase 04 protocol_checkpoint does not match the manifest schema"
            )
        if (
            declared.get("schema_version")
            != project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION
        ):
            raise LaunchError("Phase 04 protocol checkpoint schema is invalid")
        maximum = declared.get("max_bytes")
        if (
            isinstance(maximum, bool)
            or maximum != project_state.MAX_PROTOCOL_CHECKPOINT_BYTES
        ):
            raise LaunchError("Phase 04 protocol checkpoint size policy is invalid")
        raw_project_dir = str(manifest.get("project_dir", "")).strip()
        raw_output_root = str(manifest.get("output_root", "")).strip()
        raw_checkpoint = str(declared.get("path", "")).strip()
        if not raw_project_dir or not raw_output_root or not raw_checkpoint:
            raise LaunchError(
                "Phase 04 protocol checkpoint paths must be nonempty"
            )
        project_root = Path(raw_project_dir).resolve()
        output_root = Path(raw_output_root).resolve()
        checkpoint = Path(raw_checkpoint).resolve()
        try:
            output_root.relative_to(project_root)
            checkpoint.relative_to(project_root)
        except ValueError as exc:
            raise LaunchError(
                "Phase 04 protocol checkpoint escaped the project"
            ) from exc
        expected_checkpoint = (
            output_root
            / ("protocol/protocol-checkpoint.json" if _manifest_schema_version(manifest) >= 7 else "protocol-checkpoint.json")
        ).resolve()
        if checkpoint != expected_checkpoint:
            raise LaunchError(
                "Phase 04 protocol checkpoint path does not match the run plan"
            )
        if _manifest_schema_version(manifest) >= 6:
            protocol_root = Path(str(declared.get("protocol_root", ""))).resolve()
            expected_protocol_root = (output_root / "protocol").resolve()
            try:
                protocol_root.relative_to(project_root)
            except ValueError as exc:
                raise LaunchError(
                    "Phase 04 protocol directory escaped the project"
                ) from exc
            if protocol_root != expected_protocol_root:
                raise LaunchError(
                    "Phase 04 protocol directory does not match the run plan"
                )


def _frozen_snapshot_text(
    value: Any,
    label: str,
    *,
    max_bytes: int = MAX_EMBEDDED_SOUL_BYTES,
) -> tuple[str, str, Path]:
    leaf = _snapshot_leaf(value, label)
    raw_path = Path(str(leaf["path"]))
    if raw_path.is_symlink():
        raise LaunchError(f"Frozen snapshot {label} must not be a symbolic link")
    try:
        path = raw_path.resolve(strict=True)
    except OSError as exc:
        raise LaunchError(f"Frozen snapshot {label} is unavailable") from exc
    text = _read_utf8_bounded(path, label=f"frozen {label}", max_bytes=max_bytes)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    expected = str(leaf["sha256"]).lower()
    if digest != expected:
        raise LaunchError(f"Frozen snapshot {label} changed after launch preparation")
    return text, expected, path


def _paper_manuscript_paths(output_root: str | Path) -> dict[str, Path]:
    root = Path(output_root).resolve()
    return {
        "review": root / "manuscript-review.md",
        "post_review": root / "manuscript-post-review.md",
        "diff": root / "manuscript-post-review.diff",
    }


def _source_file_payload(
    project_dir: Path,
    source_path: str | Path,
    expected_sha256: str,
    *,
    expected_size: int | None,
    label: str,
    max_bytes: int,
) -> tuple[Path, bytes, str]:
    """Read one sealed source file without trusting its recorded path or size."""

    root = project_dir.resolve()
    candidate = Path(source_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    if _path_uses_symlink_below(candidate, root):
        raise LaunchError(f"{label} must not use symbolic links")
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root).as_posix()
    except OSError as exc:
        raise LaunchError(f"{label} is unavailable") from exc
    except ValueError as exc:
        raise LaunchError(f"{label} escaped the project") from exc
    payload = _bounded_bytes(resolved, label=label, max_bytes=max_bytes)
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LaunchError(f"{label} is not valid UTF-8") from exc
    expected = str(expected_sha256).strip().lower()
    if (
        len(expected) != 64
        or any(character not in "0123456789abcdef" for character in expected)
    ):
        raise LaunchError(f"{label} has no valid sealed SHA-256")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected or _sha256_file(
        resolved, max_bytes=max_bytes, label=label, allow_empty=False
    ) != expected:
        raise LaunchError(f"{label} changed after submission")
    if expected_size is not None and len(payload) != expected_size:
        raise LaunchError(f"{label} changed size after submission")
    return resolved, payload, relative


def _source_baseline_from_run(
    project_dir: Path,
    phase_slug: str,
    source_run: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the complete decision baseline of one eligible submitted run."""

    source_id = str(source_run.get("run_id", "")).strip()
    status = str(source_run.get("status", "")).strip()
    if status not in ELIGIBLE_SOURCE_STATUSES:
        allowed = ", ".join(sorted(ELIGIBLE_SOURCE_STATUSES))
        raise LaunchError(
            f"The selected source run status is not eligible; choose one of: {allowed}"
        )
    submitted_at = str(source_run.get("submitted_at", "")).strip()
    if not submitted_at or not source_run.get("final_summary"):
        raise LaunchError("The selected source run has no completed submission")
    decision_record = source_run.get("decision_record")
    if not isinstance(decision_record, Mapping):
        raise LaunchError("The selected source run has no structured decision record")
    try:
        integrity = project_state.run_integrity_report(
            project_dir, phase_slug, source_id
        )
    except (KeyError, OSError, project_state.ProjectStateError) as exc:
        raise LaunchError("The selected source run could not be verified") from exc
    if not isinstance(integrity, Mapping) or not integrity.get("ok"):
        reason = str(integrity.get("reason", "")).strip() if isinstance(
            integrity, Mapping
        ) else ""
        detail = f": {reason}" if reason else ""
        raise LaunchError(f"The selected source run failed its integrity check{detail}")

    summary_path, summary_payload, summary_relative = _source_file_payload(
        project_dir,
        str(source_run.get("final_summary", "")),
        str(source_run.get("summary_sha256", "")),
        expected_size=None,
        label="selected source final summary",
        max_bytes=MAX_SOURCE_SUMMARY_BYTES,
    )
    try:
        decision_size = int(decision_record.get("size", -1))
    except (TypeError, ValueError) as exc:
        raise LaunchError("The selected source decision record has an invalid size") from exc
    decision_path, decision_payload, decision_relative = _source_file_payload(
        project_dir,
        str(decision_record.get("path", "")),
        str(decision_record.get("sha256", "")),
        expected_size=decision_size,
        label="selected source decision record",
        max_bytes=MAX_SOURCE_DECISION_BYTES,
    )
    try:
        parsed_decision = json.loads(decision_payload.decode("utf-8"))
        normalized_decision = project_state.validate_decision_record(parsed_decision)
    except (UnicodeError, json.JSONDecodeError, project_state.ProjectStateError) as exc:
        raise LaunchError("The selected source decision record is invalid") from exc
    decision_schema = decision_record.get("schema_version")
    if (
        decision_schema not in project_state.SUPPORTED_DECISION_RECORD_SCHEMA_VERSIONS
        or normalized_decision.get("schema_version") != decision_schema
    ):
        raise LaunchError("The selected source decision record schema is invalid")

    return {
        "schema_version": SOURCE_BASELINE_SCHEMA_VERSION,
        "phase_slug": phase_slug,
        "run_id": source_id,
        "status_at_selection": status,
        "source_baseline_status": SOURCE_BASELINE_STATUS_BY_RUN_STATUS[status],
        "submitted_at": submitted_at,
        "summary": {
            "source": summary_path,
            "source_path": summary_relative,
            "sha256": hashlib.sha256(summary_payload).hexdigest(),
            "size": len(summary_payload),
        },
        "decision_record": {
            "source": decision_path,
            "source_path": decision_relative,
            "sha256": hashlib.sha256(decision_payload).hexdigest(),
            "size": len(decision_payload),
            "schema_version": decision_schema,
        },
    }


def _freeze_source_baseline(
    project_dir: Path,
    destination: Path,
    source_baseline: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy a verified summary and decision record into the new run context."""

    root = project_dir.resolve()
    run_storage = (project_state.state_dir(root) / "runs").resolve()
    destination = Path(os.path.abspath(destination))
    try:
        destination.relative_to(run_storage)
    except ValueError as exc:
        raise LaunchError("Source-baseline destination escaped run storage") from exc
    _ensure_contained_directory(
        destination.parent, run_storage, label="source-baseline destination parent"
    )
    if destination.exists() or destination.is_symlink():
        raise LaunchError(f"The source-baseline destination already exists: {destination}")
    destination.mkdir()

    def freeze_leaf(
        name: str, filename: str, *, max_bytes: int
    ) -> dict[str, Any]:
        item = source_baseline.get(name)
        if not isinstance(item, Mapping):
            raise LaunchError(f"Selected source baseline has no {name}")
        try:
            expected_size = int(item.get("size", -1))
        except (TypeError, ValueError) as exc:
            raise LaunchError(f"Selected source baseline {name} has an invalid size") from exc
        source, payload, source_relative = _source_file_payload(
            root,
            str(item.get("source", "")),
            str(item.get("sha256", "")),
            expected_size=expected_size,
            label=f"selected source baseline {name}",
            max_bytes=max_bytes,
        )
        frozen_path = _contained_file_destination(
            destination / filename,
            run_storage,
            label=f"frozen source baseline {name}",
        )
        if frozen_path.exists():
            raise LaunchError(f"Frozen source baseline already exists: {frozen_path}")
        _write_bytes_atomic(frozen_path, payload)
        expected = str(item.get("sha256", "")).lower()
        if _sha256_file(
            source,
            max_bytes=max_bytes,
            label=f"selected source baseline {name}",
            allow_empty=False,
        ) != expected or _sha256_file(
            frozen_path,
            max_bytes=max_bytes,
            label=f"frozen source baseline {name}",
            allow_empty=False,
        ) != expected:
            raise LaunchError(f"Selected source baseline {name} changed while copying")
        frozen: dict[str, Any] = {
            "path": str(frozen_path),
            "source_path": source_relative,
            "sha256": expected,
            "size": len(payload),
        }
        if name == "decision_record":
            frozen["schema_version"] = item.get("schema_version")
        return frozen

    return {
        "schema_version": SOURCE_BASELINE_SCHEMA_VERSION,
        "phase_slug": str(source_baseline.get("phase_slug", "")),
        "run_id": str(source_baseline.get("run_id", "")),
        "status_at_selection": str(source_baseline.get("status_at_selection", "")),
        "source_baseline_status": _source_baseline_status(source_baseline),
        "submitted_at": str(source_baseline.get("submitted_at", "")),
        "summary": freeze_leaf(
            "summary", "final-summary.html", max_bytes=MAX_SOURCE_SUMMARY_BYTES
        ),
        "decision_record": freeze_leaf(
            "decision_record",
            "decision-record.json",
            max_bytes=MAX_SOURCE_DECISION_BYTES,
        ),
    }


def _verified_frozen_source_baseline(
    project_dir: Path,
    manifest: Mapping[str, Any],
    source_baseline: Any,
    *,
    expected_phase_slug: str,
    relative_directory: str,
) -> Mapping[str, Any]:
    """Verify one source baseline copied into this run's immutable context."""

    schema_version = source_baseline.get("schema_version") if isinstance(
        source_baseline, Mapping
    ) else None
    status_field = (
        "source_baseline_status" if schema_version == 2 else "provenance"
    )
    required = {
        "schema_version",
        "phase_slug",
        "run_id",
        "status_at_selection",
        status_field,
        "submitted_at",
        "summary",
        "decision_record",
    }
    if not isinstance(source_baseline, Mapping) or set(source_baseline) != required:
        raise LaunchError("Frozen source baseline has an invalid inventory")
    status = str(source_baseline.get("status_at_selection", ""))
    if (
        schema_version not in {1, SOURCE_BASELINE_SCHEMA_VERSION}
        or source_baseline.get("phase_slug") != expected_phase_slug
        or not str(source_baseline.get("run_id", "")).strip()
        or not str(source_baseline.get("submitted_at", "")).strip()
        or status not in ELIGIBLE_SOURCE_STATUSES
        or _source_baseline_status(source_baseline)
        != SOURCE_BASELINE_STATUS_BY_RUN_STATUS[status]
    ):
        raise LaunchError("Frozen source baseline identity or status is invalid")

    context_root = run_context_dir(
        project_dir,
        str(manifest.get("phase_slug", "")),
        str(manifest.get("run_id", "")),
    ).resolve()
    baseline_root = (context_root / relative_directory).resolve()
    try:
        baseline_root.relative_to(context_root)
    except ValueError as exc:
        raise LaunchError("Frozen source baseline directory escaped the run context") from exc

    for name, filename, maximum in (
        ("summary", "final-summary.html", MAX_SOURCE_SUMMARY_BYTES),
        ("decision_record", "decision-record.json", MAX_SOURCE_DECISION_BYTES),
    ):
        item = source_baseline.get(name)
        expected_fields = {"path", "source_path", "sha256", "size"}
        if name == "decision_record":
            expected_fields.add("schema_version")
        if not isinstance(item, Mapping) or set(item) != expected_fields:
            raise LaunchError(f"Frozen source baseline {name} record is invalid")
        source_path = str(item.get("source_path", "")).strip()
        if (
            not source_path
            or Path(source_path).is_absolute()
            or ".." in Path(source_path).parts
        ):
            raise LaunchError(f"Frozen source baseline {name} path is invalid")
        try:
            expected_size = int(item.get("size", -1))
        except (TypeError, ValueError) as exc:
            raise LaunchError(f"Frozen source baseline {name} size is invalid") from exc
        path, payload, _ = _source_file_payload(
            context_root,
            str(item.get("path", "")),
            str(item.get("sha256", "")),
            expected_size=expected_size,
            label=f"frozen source baseline {name}",
            max_bytes=maximum,
        )
        if path != (baseline_root / filename).resolve():
            raise LaunchError(f"Frozen source baseline {name} path is invalid")
        if name == "decision_record":
            try:
                normalized = project_state.validate_decision_record(
                    json.loads(payload.decode("utf-8"))
                )
            except (
                UnicodeError,
                json.JSONDecodeError,
                project_state.ProjectStateError,
            ) as exc:
                raise LaunchError("Frozen source decision record is invalid") from exc
            if (
                item.get("schema_version")
                not in project_state.SUPPORTED_DECISION_RECORD_SCHEMA_VERSIONS
                or normalized.get("schema_version") != item.get("schema_version")
            ):
                raise LaunchError("Frozen source decision record schema is invalid")
    return source_baseline


def _resolve_paper_review_source(
    project_dir: str | Path,
    review_target: str | Path,
    expected_sha256: str,
) -> tuple[Path, str, dict[str, Any]]:
    """Validate the user-selected post-review manuscript and its page version."""

    root = Path(project_dir).resolve()
    candidate = Path(review_target)
    if not candidate.is_absolute():
        candidate = root / candidate
    if _path_uses_symlink_below(candidate, root):
        raise LaunchError("The selected review target must not use symbolic links")
    try:
        candidate = candidate.resolve(strict=True)
        candidate.relative_to(root)
    except OSError as exc:
        raise LaunchError(f"The selected review target is unavailable: {review_target}") from exc
    except ValueError as exc:
        raise LaunchError("The selected review target must stay inside the project") from exc
    if candidate.name != "manuscript-post-review.md":
        raise LaunchError(
            "A review-only Phase 06 run requires a manuscript-post-review.md target"
        )
    sealed_digest = ""
    source_baseline: dict[str, Any] | None = None
    for recorded_run in project_state.get_runs(root, PAPER_WRITING_PHASE):
        if recorded_run.get("status") in project_state.ACTIVE_RUN_STATUSES:
            continue
        run_id = str(recorded_run.get("run_id", ""))
        if not run_id:
            continue
        try:
            manifest = _read_manifest(root, PAPER_WRITING_PHASE, run_id)
            output_root = Path(str(manifest["output_root"])).resolve()
            output_root.relative_to(root)
        except (LaunchError, OSError, ValueError, KeyError):
            continue
        paper_review = manifest.get("paper_review")
        if isinstance(paper_review, Mapping) and paper_review.get("kind") == "review_only":
            continue
        artifacts = recorded_run.get("submission_artifacts")
        post_review = (
            artifacts.get("post_review_manuscript")
            if isinstance(artifacts, Mapping)
            else None
        )
        if not isinstance(post_review, Mapping):
            continue
        try:
            recorded_path = (root / str(post_review.get("path", ""))).resolve()
            recorded_path.relative_to(root)
            recorded_size = int(post_review.get("size", -1))
        except (ValueError, TypeError):
            continue
        recorded_digest = str(post_review.get("sha256", "")).lower()
        if (
            recorded_path == candidate
            and recorded_path == (output_root / "manuscript-post-review.md").resolve()
            and recorded_size >= 0
            and len(recorded_digest) == 64
        ):
            source_baseline = _source_baseline_from_run(
                root, PAPER_WRITING_PHASE, recorded_run
            )
            sealed_digest = recorded_digest
            break
    if not sealed_digest or source_baseline is None:
        raise LaunchError(
            "The selected manuscript is not a sealed post-review output of a "
            "recorded Phase 06 run"
        )
    _read_utf8_bounded(
        candidate,
        label="selected post-review manuscript",
        max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
    )
    expected = str(expected_sha256).strip().lower()
    if (
        len(expected) != 64
        or any(character not in "0123456789abcdef" for character in expected)
    ):
        raise LaunchError("The selected review target requires its displayed SHA-256")
    digest = _sha256_file(
        candidate,
        max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
        label="selected post-review manuscript",
        allow_empty=False,
    )
    if digest != expected or digest != sealed_digest:
        raise LaunchError(
            "The selected post-review manuscript does not match its sealed run "
            "record or changed after the page was shown. Reload the phase and choose it again."
        )
    return candidate, digest, source_baseline


def _copy_paper_review_source(
    project_dir: Path, source: Path, destination: Path, sha256: str
) -> None:
    """Copy an exact review source without changing or overwriting either version."""

    destination = _contained_file_destination(
        destination, project_dir, label="review-only manuscript destination"
    )
    if destination.exists():
        raise LaunchError(f"The review-only destination already exists: {destination}")
    payload = _bounded_bytes(
        source,
        label="selected review target",
        max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
    )
    source_before = hashlib.sha256(payload).hexdigest()
    if source_before != sha256 or _sha256_file(
        source,
        max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
        label="selected review target",
        allow_empty=False,
    ) != sha256:
        raise LaunchError("The selected post-review manuscript changed before copying")
    try:
        _write_bytes_atomic(destination, payload)
    except OSError as exc:
        raise LaunchError(f"Could not preserve the selected review target: {source}") from exc
    source_after = _sha256_file(
        source,
        max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
        label="selected review target",
        allow_empty=False,
    )
    destination_digest = _sha256_file(
        destination,
        max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
        label="preserved review target",
        allow_empty=False,
    )
    if source_after != sha256 or destination_digest != sha256:
        try:
            destination.unlink()
        except OSError:
            pass
        raise LaunchError("The selected review target changed while it was being preserved")


def _paper_reviewer_substage(
    manifest: Mapping[str, Any], round_n: int
) -> str | None:
    if str(manifest.get("phase_slug")) != PAPER_WRITING_PHASE:
        return None
    stages = list(manifest.get("phase", {}).get("stages", []))
    reviewer_rounds = [
        index
        for index, stage in enumerate(stages, 1)
        if str(stage.get("role")) == PAPER_REVIEWER_ROLE
    ]
    if round_n not in reviewer_rounds:
        return None
    return "independent" if round_n == reviewer_rounds[0] else "contextual"


def _is_proof_audit_stage(
    manifest: Mapping[str, Any], round_n: int, role: str
) -> bool:
    phase = manifest.get("phase", {})
    stages = list(phase.get("stages", []))
    return bool(
        str(manifest.get("phase_slug")) == THEORETICAL_ANALYSIS_PHASE
        and phase.get("proof_audit") is True
        and role == PAPER_REVIEWER_ROLE
        and round_n == len(stages)
        and stages
        and str(stages[-1].get("role")) == PAPER_REVIEWER_ROLE
    )


def _proof_audit_material_block(
    project_dir: Path,
    manifest: Mapping[str, Any],
    run: Mapping[str, Any],
    round_n: int,
) -> str:
    """Seal the exact final theory artifact and audit evidence into the brief."""

    if manifest.get("phase", {}).get("audit_only") is True:
        source = _verified_frozen_theory_audit_source(project_dir, manifest)
        target_record = source["target"]
        target = Path(str(target_record["path"])).resolve()
        theory = _read_utf8_bounded(
            target,
            label="frozen audit-only theory artifact",
            max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
        )
        digest = str(target_record["sha256"]).lower()
        evidence_lines = [
            f"- {item.get('path')} ({item.get('purpose', 'sealed evidence')}; "
            f"SHA-256 {item.get('sha256', 'not recorded')})"
            for item in source.get("evidence", [])
            if isinstance(item, Mapping)
        ]
        evidence = "\n".join(evidence_lines) if evidence_lines else "- None available"
        return f"""## Sealed proof-audit target

- Source Phase 03 run ID: `{source['run_id']}`
- Original artifact path: `{target_record['source_path']}`
- Source stage: {target_record['source_round']}
- Frozen audit copy: `{target}`
- Final theory SHA-256: `{digest}`

BEGIN SEALED FINAL THEORY ARTIFACT

{theory.rstrip()}

END SEALED FINAL THEORY ARTIFACT

## Sealed evidence inventory available to the audit

{evidence}

The frozen copy and hash define the exact target. This run audits that target
without repeating or revising the theory. Do not use a prior research-lead
assessment or recommendation as mathematical evidence.
"""

    stages = list(manifest.get("phase", {}).get("stages", []))
    theorist_rounds = [
        index
        for index, stage in enumerate(stages[: round_n - 1], 1)
        if str(stage.get("role")) == "theorist"
    ]
    if not theorist_rounds:
        raise LaunchError("The selected proof audit has no preceding theorist stage")
    target_round = theorist_rounds[-1]
    target = _planned_output(manifest, target_round, "theorist").resolve()
    root = project_dir.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise LaunchError("The proof-audit target escaped the project") from exc
    round_state = next(
        (
            item
            for item in run.get("rounds", [])
            if int(item.get("n", 0)) == target_round and item.get("completed")
        ),
        None,
    )
    if round_state is None:
        raise LaunchError("The final theorist stage is not complete")
    relative_target = target.relative_to(root).as_posix()
    record = next(
        (
            item
            for item in round_state.get("artifacts", [])
            if str(item.get("path", "")) == relative_target
        ),
        None,
    )
    if not isinstance(record, Mapping):
        raise LaunchError("The final theory artifact has no sealed artifact record")
    theory = _read_utf8_bounded(
        target,
        label="final theory artifact",
        max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
    )
    digest = hashlib.sha256(theory.encode("utf-8")).hexdigest()
    if digest != str(record.get("sha256", "")).lower() or _sha256_file(target) != digest:
        raise LaunchError("The final theory artifact changed after stage completion")

    evidence_lines: list[str] = []
    for prior_round in run.get("rounds", [])[: round_n - 1]:
        prior_number = int(prior_round.get("n", 0) or 0)
        prior_role = (
            str(stages[prior_number - 1].get("role", ""))
            if 1 <= prior_number <= len(stages)
            else ""
        )
        if prior_role == "research_lead":
            # Keep the mathematical audit independent of the lead's preference
            # or recommendation. The final theory and approved source summaries
            # remain available as the proof target and scientific provenance.
            continue
        for artifact in prior_round.get("artifacts", []):
            if isinstance(artifact, Mapping):
                evidence_lines.append(
                    f"- {root / str(artifact.get('path', ''))} "
                    f"(SHA-256 {artifact.get('sha256', 'not recorded')})"
                )
    for summary in manifest.get("snapshots", {}).get("summaries", []):
        evidence_lines.append(
            f"- {summary.get('path')} from {summary.get('phase')} "
            f"(SHA-256 {summary.get('sha256', 'not recorded')})"
        )
    evidence = "\n".join(evidence_lines) if evidence_lines else "- None available"
    return f"""## Sealed proof-audit target

- Final theory path: `{target}`
- Final theory SHA-256: `{digest}`
- Source stage: {target_round}

BEGIN SEALED FINAL THEORY ARTIFACT

{theory.rstrip()}

END SEALED FINAL THEORY ARTIFACT

## Sealed evidence inventory available to the audit

{evidence}

The embedded theory text and hash define the exact target. Treat the listed
artifacts and summaries as the complete available evidence inventory. Do not
edit the target or any evidence file.
"""


def _paper_review_manuscript_snapshot(
    manifest: Mapping[str, Any],
) -> tuple[Path, str, str]:
    """Read one stable snapshot of the Phase 06 review manuscript."""

    raw_output_root = Path(str(manifest["output_root"]))
    path = _paper_manuscript_paths(raw_output_root)["review"]
    project_value = manifest.get("project_dir")
    uses_link = (
        _path_uses_symlink_below(path, Path(str(project_value)).resolve())
        if project_value
        else raw_output_root.is_symlink() or path.is_symlink()
    )
    if uses_link:
        raise LaunchError("The Phase 06 review manuscript must not use symbolic links")
    try:
        path = path.resolve(strict=True)
    except OSError as exc:
        raise LaunchError(
            f"The Phase 06 review manuscript is missing: {path}"
        ) from exc
    digest_before = _sha256_file(path)
    manuscript = _read_utf8_bounded(
        path,
        label="Phase 06 review manuscript",
        max_bytes=MAX_REVIEW_MANUSCRIPT_BYTES,
    )
    digest = hashlib.sha256(manuscript.encode("utf-8")).hexdigest()
    digest_after = _sha256_file(path)
    if digest_before != digest or digest_after != digest:
        raise LaunchError(
            "The Phase 06 review manuscript changed while the reviewer task "
            "was being sealed"
        )
    return path, manuscript, digest


def _paper_review_manuscript_block(
    manifest: Mapping[str, Any],
    role: str,
    playbook: str | Path,
    round_n: int | None = None,
    snapshot: tuple[Path, str, str] | None = None,
) -> str:
    """Seal the exact Phase 06 manuscript into the reviewer task brief."""

    if (
        str(manifest.get("phase_slug")) != PAPER_WRITING_PHASE
        or role != PAPER_REVIEWER_ROLE
    ):
        return ""
    path, manuscript, digest = snapshot or _paper_review_manuscript_snapshot(manifest)
    substage = _paper_reviewer_substage(manifest, round_n) if round_n else None
    if substage == "contextual":
        reading_rule = (
            "Use the preserved independent-reading report from the prior substage, then "
            "compare this same manuscript with the internal scientific record."
        )
    else:
        reading_rule = (
            "Perform the independent first reading using only the manuscript embedded "
            "below. Do not inspect project context or prior author outputs."
        )
    return f"""## Authoritative review manuscript

Follow the reviewer protocol `{playbook}`. {reading_rule}

- Source path: `{path}`
- SHA-256: `{digest}`

BEGIN SEALED REVIEW MANUSCRIPT

{manuscript.rstrip()}

END SEALED REVIEW MANUSCRIPT

The embedded content and digest, not any later edit to the source path, define
the exact version reviewed in this task.
"""


def _guard_command_length(arguments: Sequence[str]) -> None:
    if os.name == "nt":
        command = subprocess.list2cmdline(list(arguments))
        utf16_units = len(command.encode("utf-16-le")) // 2
        if utf16_units >= 30_000:
            raise LaunchError("Hermes command exceeds the safe Windows command-line length")


def _board_slugs(payload: Any) -> set[str]:
    if isinstance(payload, dict):
        payload = payload.get("boards", payload.get("items", []))
    if not isinstance(payload, list):
        return set()
    return {
        str(board.get("slug"))
        for board in payload
        if isinstance(board, dict) and board.get("slug")
    }


def _ensure_board(
    hermes: str,
    board_slug: str,
    display_name: str,
    *,
    hermes_root: str | os.PathLike[str] | None = None,
) -> None:
    """Create the project board, while treating CLI failures as real failures."""

    environment = _hermes_environment(hermes_root)
    listed = _run_command(
        [hermes, "kanban", "boards", "list", "--json"],
        environment=environment,
    )
    if listed.returncode != 0:
        detail = (listed.stderr or listed.stdout).strip()
        raise LaunchError(f"Hermes could not list kanban boards: {detail or 'unknown error'}")
    try:
        slugs = _board_slugs(json.loads(listed.stdout or "[]"))
    except json.JSONDecodeError as exc:
        raise LaunchError("Hermes returned invalid JSON while listing kanban boards") from exc
    if board_slug in slugs:
        return

    created = _run_command(
        [
            hermes,
            "kanban",
            "boards",
            "create",
            board_slug,
            "--name",
            display_name,
        ],
        environment=environment,
    )
    if created.returncode != 0:
        detail = (created.stderr or created.stdout).strip()
        raise LaunchError(f"Hermes could not create kanban board {board_slug}: {detail or 'unknown error'}")


def _preflight(
    project_dir: Path,
    phase: Mapping[str, Any],
    profiles: Mapping[str, str],
    config: Mapping[str, Any],
    *,
    hermes_root: str | os.PathLike[str] | None = None,
) -> tuple[str, Path]:
    if not project_dir.is_dir():
        raise LaunchError(f"Project directory does not exist: {project_dir}")
    if not (project_dir / "setting.md").is_file():
        raise LaunchError("Project setting.md is missing")

    required_roles = set(str(role) for role in phase.get("members", []))
    required_roles.add("research_lead")
    missing_profiles = sorted(role for role in required_roles if not profiles.get(role))
    if missing_profiles:
        raise LaunchError("No Hermes profile is mapped for: " + ", ".join(missing_profiles))

    if not bool(config.get("hub", {}).get("allow_unattended_tools", False)):
        raise LaunchError(
            "Background web runs require hub.allow_unattended_tools: true because no "
            "interactive terminal is available to answer Hermes tool approvals."
        )

    phase_dir = PHASES_DIR / str(phase["slug"])
    required_files = [phase_dir / "_phase.md", phase_dir / "_lead.md"]
    required_files.extend(phase_dir / f"{role}.md" for role in required_roles)
    missing_files = [str(path) for path in required_files if not path.is_file()]
    if missing_files:
        raise LaunchError("Required playbook files are missing: " + ", ".join(missing_files))
    required_souls = [SOULS_DIR / f"{role}.md" for role in sorted(required_roles)]
    missing_souls = [str(path) for path in required_souls if not path.is_file()]
    if missing_souls:
        raise LaunchError("Required role soul files are missing: " + ", ".join(missing_souls))

    hermes = shutil.which("hermes")
    if not hermes:
        raise LaunchError(
            "Hermes is not available on PATH. Install Hermes and start the configured "
            "profile gateways before launching a phase."
        )
    try:
        resolved_hermes_root = (
            profile_skills.profile_home("default", hermes_root=hermes_root)
            if hermes_root is not None
            else profile_skills.resolve_hermes_root()
        )
        missing_on_disk = sorted({
            profile
            for role, profile in profiles.items()
            if role in required_roles
            and profile_skills.configured_profile_home(
                profile,
                hermes_root=resolved_hermes_root,
            ) is None
        })
    except (profile_skills.ProfileSkillsError, OSError, ValueError) as exc:
        raise LaunchError("Hermes profile locations could not be resolved safely") from exc
    if missing_on_disk:
        raise LaunchError(
            "Configured Hermes profiles do not exist: " + ", ".join(missing_on_disk)
        )
    return hermes, resolved_hermes_root


def _ancestor_slugs(phase_slug: str, dependencies: Mapping[str, Sequence[str]]) -> set[str]:
    ancestors: set[str] = set()
    queue = list(dependencies.get(phase_slug, []))
    while queue:
        item = queue.pop(0)
        if item in ancestors:
            continue
        ancestors.add(item)
        queue.extend(dependencies.get(item, []))
    return ancestors


def _trusted_context(
    project_dir: Path,
    phase_slug: str,
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return approved run inputs, including the phase's prior baseline."""

    dependencies = _dependencies(config)
    ancestors = _ancestor_slugs(phase_slug, dependencies)
    phase = _phase_config(config, phase_slug)
    optional = {str(item) for item in phase.get("context_from", [])}
    candidates = ancestors | optional | {phase_slug}
    state = project_state.load(project_dir)
    entries: list[dict[str, Any]] = []
    for candidate in _phase_slugs(config):
        if candidate not in candidates:
            continue
        phase_state = state.get("phases", {}).get(candidate, {})
        if candidate != phase_slug and phase_state.get("stale"):
            continue
        approved_id = phase_state.get("approved_run")
        if not approved_id:
            continue
        try:
            run = project_state.get_run(project_dir, candidate, approved_id)
        except KeyError:
            continue
        if run.get("status") != "approved" or not run.get("final_summary"):
            continue
        if not project_state.run_integrity_report(
            project_dir, candidate, approved_id
        )["ok"]:
            continue
        summary = (project_dir / str(run["final_summary"])).resolve()
        try:
            summary.relative_to(project_dir)
        except ValueError:
            continue
        try:
            digest = _sha256_file(
                summary,
                max_bytes=MAX_SOURCE_SUMMARY_BYTES,
                label="approved context summary",
                allow_empty=False,
            )
        except LaunchError:
            continue
        recorded_digest = run.get("summary_sha256")
        if recorded_digest and digest != recorded_digest:
            # Never ingest altered evidence. Required-source integrity is also
            # surfaced by the prerequisite report and needs a user override.
            continue
        decision_input = None
        decision_record = run.get("decision_record")
        if isinstance(decision_record, Mapping):
            try:
                decision_size = int(decision_record.get("size", -1))
                _, decision_payload, decision_relative = _source_file_payload(
                    project_dir,
                    str(decision_record.get("path", "")),
                    str(decision_record.get("sha256", "")),
                    expected_size=decision_size,
                    label="approved context decision record",
                    max_bytes=MAX_SOURCE_DECISION_BYTES,
                )
                normalized_decision = project_state.validate_decision_record(
                    json.loads(decision_payload.decode("utf-8"))
                )
            except (
                LaunchError,
                UnicodeError,
                ValueError,
                json.JSONDecodeError,
                project_state.ProjectStateError,
            ):
                decision_input = None
            else:
                if (
                    normalized_decision.get("schema_version")
                    == decision_record.get("schema_version")
                    and normalized_decision == decision_record.get("data")
                ):
                    selected = normalized_decision.get(
                        "selected_scientific_object"
                    )
                    decision_input = {
                        "path": decision_relative,
                        "sha256": hashlib.sha256(decision_payload).hexdigest(),
                        "size": len(decision_payload),
                        "schema_version": normalized_decision.get("schema_version"),
                        "selected_scientific_object": (
                            dict(selected) if isinstance(selected, Mapping) else None
                        ),
                    }
        context_entry = {
            "phase": candidate,
            "run_id": str(approved_id),
            "summary": summary.relative_to(project_dir).as_posix(),
            "sha256": digest,
            "kind": "prior_phase_baseline" if candidate == phase_slug else (
                "optional_approved_context" if candidate in optional else "prerequisite"
            ),
            "trusted": candidate != phase_slug or not bool(phase_state.get("stale")),
        }
        if decision_input is not None:
            context_entry["decision_record"] = decision_input
        entries.append(context_entry)
    return entries


def _run_index(project_dir: Path, phase_slug: str, run_id: str) -> int:
    for index, run in enumerate(project_state.get_runs(project_dir, phase_slug)):
        if run.get("run_id") == run_id:
            return index
    raise LaunchError(f"Reserved run {run_id} disappeared from project state")


def run_manifest_path(project_dir: Path, phase_slug: str, run_id: str) -> Path:
    return project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.manifest.json"


def run_context_dir(project_dir: Path, phase_slug: str, run_id: str) -> Path:
    return project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.context"


def _workspace_board_slug(project_dir: Path, project_id: int) -> str:
    workspace = project_dir.parent.parent.resolve()
    workspace_id = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:8]
    return f"rhub-{workspace_id}-p{project_id}"


def _snapshot_run_inputs(
    project_dir: Path,
    phase: Mapping[str, Any],
    run_id: str,
    context_inputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Copy every prompt input into a run-scoped, immutable context folder."""

    phase_slug = str(phase["slug"])
    destination = run_context_dir(project_dir, phase_slug, run_id)
    try:
        control_root = project_state._ensure_control_directory(project_dir).resolve(
            strict=True
        )
    except project_state.ProjectStateError as exc:
        raise LaunchError(str(exc)) from exc
    _ensure_contained_directory(
        destination.parent, control_root, label="run context parent"
    )
    if destination.exists() or destination.is_symlink():
        raise LaunchError(f"Run context already exists: {destination}")
    destination.mkdir()

    def copy(
        source: Path,
        relative_name: str,
        *,
        max_bytes: int,
    ) -> dict[str, str]:
        if source.is_symlink():
            raise LaunchError(f"Prompt input must not be a symbolic link: {source}")
        try:
            source = source.resolve(strict=True)
        except OSError as exc:
            raise LaunchError(f"Prompt input is missing or unreadable: {source}") from exc
        payload = _bounded_bytes(
            source,
            label="prompt input",
            max_bytes=max_bytes,
        )
        target = _contained_file_destination(
            destination / relative_name,
            destination,
            label="frozen prompt input destination",
        )
        source_before = hashlib.sha256(payload).hexdigest()
        _write_bytes_atomic(target, payload)
        source_after = _sha256_file(
            source,
            max_bytes=max_bytes,
            label="prompt input",
            allow_empty=False,
        )
        target_digest = _sha256_file(
            target,
            max_bytes=max_bytes,
            label="frozen prompt input",
            allow_empty=False,
        )
        if source_before != source_after or source_after != target_digest:
            try:
                target.unlink()
            except OSError:
                pass
            raise LaunchError(
                f"Prompt input changed while the run was being frozen: {source}"
            )
        return {
            "path": str(target),
            "sha256": target_digest,
        }

    snapshots: dict[str, Any] = {
        "setting": copy(
            project_dir / "setting.md",
            "project/setting.md",
            max_bytes=project_state.MAX_CONTROL_FILE_BYTES,
        ),
        "team": {
            "charter": copy(
                TEAM_DIR / "charter.md",
                "team/charter.md",
                max_bytes=MAX_EMBEDDED_SOUL_BYTES,
            ),
            "norms": copy(
                TEAM_DIR / "norms.md",
                "team/norms.md",
                max_bytes=MAX_EMBEDDED_SOUL_BYTES,
            ),
        },
        "souls": {},
        "playbooks": {},
        "summaries": [],
    }
    soul_roles = {str(role) for role in phase.get("members", [])}
    soul_roles.add("research_lead")
    for role in sorted(soul_roles):
        soul_snapshot = copy(
            SOULS_DIR / f"{role}.md",
            f"souls/{role}.md",
            max_bytes=MAX_EMBEDDED_SOUL_BYTES,
        )
        _frozen_snapshot_text(soul_snapshot, f"souls.{role}")
        snapshots["souls"][role] = soul_snapshot
    phase_dir = PHASES_DIR / phase_slug
    playbook_names = ["_lead.md", "_phase.md"] + [
        f"{role}.md" for role in phase.get("members", [])
    ]
    for name in playbook_names:
        snapshots["playbooks"][name] = copy(
            phase_dir / name,
            f"playbooks/{name}",
            max_bytes=MAX_EMBEDDED_SOUL_BYTES,
        )
    for entry in context_inputs:
        source = project_dir / str(entry["summary"])
        relative_name = f"summaries/{entry['phase']}-{entry['run_id']}.html"
        snapshot = copy(
            source,
            relative_name,
            max_bytes=MAX_SOURCE_SUMMARY_BYTES,
        )
        expected_digest = str(entry.get("sha256", "")).lower()
        if not expected_digest or snapshot["sha256"] != expected_digest:
            raise LaunchError(
                f"Approved context changed while the run was being frozen: "
                f"{entry['phase']} run {entry['run_id']}"
            )
        frozen_entry = {**dict(entry), **snapshot}
        decision_input = entry.get("decision_record")
        if isinstance(decision_input, Mapping):
            decision_snapshot = copy(
                project_dir / str(decision_input.get("path", "")),
                f"decisions/{entry['phase']}-{entry['run_id']}.json",
                max_bytes=MAX_SOURCE_DECISION_BYTES,
            )
            expected_decision_digest = str(
                decision_input.get("sha256", "")
            ).lower()
            if (
                not expected_decision_digest
                or decision_snapshot["sha256"] != expected_decision_digest
            ):
                raise LaunchError(
                    "Approved decision record changed while the run was being frozen: "
                    f"{entry['phase']} run {entry['run_id']}"
                )
            decision_snapshot.update({
                "schema_version": decision_input.get("schema_version"),
                "selected_scientific_object": decision_input.get(
                    "selected_scientific_object"
                ),
            })
            frozen_entry["decision_record"] = decision_snapshot
        snapshots["summaries"].append(frozen_entry)
    return snapshots


def _method_selection_for_run(
    phase: Mapping[str, Any],
    snapshots: Mapping[str, Any],
    run_specific_method_id: str,
    run_specific_method_version: str,
) -> dict[str, Any] | None:
    """Freeze the exact method identity for Phase 03 and Phase 04 work."""

    phase_slug = str(phase.get("slug", ""))
    method_phase = phase_slug in {
        THEORETICAL_ANALYSIS_PHASE,
        NUMERICAL_VALIDATION_PHASE,
    }
    supplied_id = str(run_specific_method_id).strip()
    supplied_version = str(run_specific_method_version).strip()
    if bool(supplied_id) != bool(supplied_version):
        raise LaunchError(
            "Supply both the run-specific method ID and version, or neither"
        )
    if not method_phase:
        if supplied_id or supplied_version:
            raise LaunchError(
                "A run-specific method identity is valid only for Phase 03 or Phase 04"
            )
        return None
    if phase_slug == THEORETICAL_ANALYSIS_PHASE and phase.get("audit_only") is True:
        if supplied_id or supplied_version:
            raise LaunchError(
                "An audit-only Phase 03 run uses its sealed source artifact"
            )
        return None
    if supplied_id:
        selected = _method_identity(supplied_id, supplied_version)
        return {
            **selected,
            "source": "run_specific_user_selection",
            "source_phase": None,
            "source_run_id": None,
            "decision_record": None,
        }

    for entry in snapshots.get("summaries", []):
        if (
            not isinstance(entry, Mapping)
            or entry.get("phase") != project_state.METHOD_DEVELOPMENT_PHASE
            or not entry.get("trusted", True)
        ):
            continue
        decision = entry.get("decision_record")
        selected = (
            decision.get("selected_scientific_object")
            if isinstance(decision, Mapping)
            else None
        )
        if not isinstance(selected, Mapping) or selected.get("kind") != "method":
            continue
        identity = _method_identity(
            str(selected.get("stable_id", "")),
            str(selected.get("version", "")),
        )
        return {
            **identity,
            "source": "approved_phase_02_selection",
            "source_phase": project_state.METHOD_DEVELOPMENT_PHASE,
            "source_run_id": str(entry.get("run_id", "")),
            "decision_record": {
                "path": str(decision.get("path", "")),
                "sha256": str(decision.get("sha256", "")),
                "schema_version": decision.get("schema_version"),
            },
        }
    raise LaunchError(
        "This run needs an exact method identity. Approve a current Phase 02 result "
        "with a structured method ID and version, or enter a run-specific method "
        "ID and version in the Web UI."
    )


def _validated_manifest_method_selection(
    manifest: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Validate method identity and provenance against the frozen input inventory."""

    phase_slug = str(manifest.get("phase_slug", ""))
    phase = manifest.get("phase")
    audit_only = isinstance(phase, Mapping) and phase.get("audit_only") is True
    required = phase_slug in {
        THEORETICAL_ANALYSIS_PHASE,
        NUMERICAL_VALIDATION_PHASE,
    } and not audit_only
    value = manifest.get("method_selection")
    if value is None:
        if required:
            raise LaunchError("The frozen run plan has no exact method selection")
        return None
    fields = {
        "kind",
        "stable_id",
        "version",
        "source",
        "source_phase",
        "source_run_id",
        "decision_record",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise LaunchError("The frozen method selection has an invalid structure")
    if not required:
        raise LaunchError("This run variant must not declare a method selection")
    identity = _method_identity(
        str(value.get("stable_id", "")), str(value.get("version", ""))
    )
    if value.get("kind") != identity["kind"]:
        raise LaunchError("The frozen scientific object must be a method")
    source = value.get("source")
    if source == "run_specific_user_selection":
        if any(
            value.get(field) is not None
            for field in ("source_phase", "source_run_id", "decision_record")
        ):
            raise LaunchError(
                "A run-specific method selection has unexpected source metadata"
            )
    elif source == "approved_phase_02_selection":
        source_run_id = str(value.get("source_run_id", "")).strip()
        decision = value.get("decision_record")
        if (
            value.get("source_phase") != project_state.METHOD_DEVELOPMENT_PHASE
            or not source_run_id
            or not isinstance(decision, Mapping)
            or set(decision) != {"path", "sha256", "schema_version"}
        ):
            raise LaunchError("The approved method-selection provenance is incomplete")
        matching_entry = next(
            (
                entry
                for entry in manifest.get("snapshots", {}).get("summaries", [])
                if isinstance(entry, Mapping)
                and entry.get("phase") == project_state.METHOD_DEVELOPMENT_PHASE
                and str(entry.get("run_id", "")) == source_run_id
            ),
            None,
        )
        frozen_decision = (
            matching_entry.get("decision_record")
            if isinstance(matching_entry, Mapping)
            else None
        )
        selected = (
            frozen_decision.get("selected_scientific_object")
            if isinstance(frozen_decision, Mapping)
            else None
        )
        if (
            not isinstance(frozen_decision, Mapping)
            or not isinstance(selected, Mapping)
            or matching_entry.get("trusted") is False
            or frozen_decision.get("schema_version") != 2
            or len(str(frozen_decision.get("sha256", ""))) != 64
            or any(
                character not in "0123456789abcdef"
                for character in str(frozen_decision.get("sha256", "")).lower()
            )
            or dict(decision)
            != {
                "path": frozen_decision.get("path"),
                "sha256": frozen_decision.get("sha256"),
                "schema_version": frozen_decision.get("schema_version"),
            }
            or selected.get("kind") != "method"
            or selected.get("stable_id") != identity["stable_id"]
            or selected.get("version") != identity["version"]
        ):
            raise LaunchError(
                "The approved method selection does not match its frozen decision record"
            )
    else:
        raise LaunchError("The frozen method selection has an invalid source")
    return dict(value)


def _read_manifest(project_dir: Path, phase_slug: str, run_id: str) -> dict[str, Any]:
    path = run_manifest_path(project_dir, phase_slug, run_id)
    try:
        payload = _bounded_bytes(
            path,
            label="run manifest",
            max_bytes=project_state.MAX_CONTROL_FILE_BYTES,
        )
        manifest = json.loads(payload.decode("utf-8"))
    except (LaunchError, UnicodeError, ValueError) as exc:
        raise LaunchError(f"Run manifest is unavailable or invalid: {path}") from exc
    if manifest.get("run_id") != run_id or manifest.get("phase_slug") != phase_slug:
        raise LaunchError("Run manifest identity does not match the requested run")
    run = project_state.get_run(project_dir, phase_slug, run_id)
    if Path(str(run.get("manifest_path", ""))).resolve() != path.resolve():
        raise LaunchError("Run manifest path does not match the sealed state record")
    digest = hashlib.sha256(payload).hexdigest()
    if not run.get("manifest_sha256") or digest != run.get("manifest_sha256"):
        raise LaunchError("Run manifest changed after launch preparation")
    _validate_manifest_snapshot_schema(manifest)
    return manifest


def _resolve_theory_audit_source(
    project_dir: str | Path, source_run_id: str
) -> dict[str, Any]:
    """Resolve one exact final theorist artifact from sealed Phase 03 records."""

    root = Path(project_dir).resolve()
    source_id = str(source_run_id).strip()
    if not source_id or len(source_id) > 256:
        raise LaunchError("Select a valid source run for the proof audit")
    try:
        source_run = project_state.get_run(
            root, THEORETICAL_ANALYSIS_PHASE, source_id
        )
    except (KeyError, project_state.ProjectStateError) as exc:
        raise LaunchError("The selected proof-audit source run is unavailable") from exc
    source_baseline = _source_baseline_from_run(
        root, THEORETICAL_ANALYSIS_PHASE, source_run
    )

    source_manifest = _read_manifest(
        root, THEORETICAL_ANALYSIS_PHASE, source_id
    )
    _verify_frozen_inputs(
        root, THEORETICAL_ANALYSIS_PHASE, source_id, source_manifest
    )
    stages = list(source_manifest.get("phase", {}).get("stages", []))
    theorist_rounds = [
        index
        for index, stage in enumerate(stages, 1)
        if isinstance(stage, Mapping) and str(stage.get("role")) == "theorist"
    ]
    if not theorist_rounds:
        raise LaunchError(
            "The selected source run has no configured theorist stage to audit"
        )
    target_round = theorist_rounds[-1]
    round_state = next(
        (
            item
            for item in source_run.get("rounds", [])
            if isinstance(item, Mapping)
            and int(item.get("n", 0) or 0) == target_round
            and item.get("completed")
        ),
        None,
    )
    if round_state is None:
        raise LaunchError(
            "The selected source run has no completed final theorist stage"
        )
    target = _planned_output(source_manifest, target_round, "theorist")
    if target.is_symlink():
        raise LaunchError("The selected final theory artifact cannot be a symbolic link")
    try:
        target = target.resolve(strict=True)
        target.relative_to(root)
    except OSError as exc:
        raise LaunchError("The selected final theory artifact is unavailable") from exc
    except ValueError as exc:
        raise LaunchError("The selected final theory artifact escaped the project") from exc
    target_relative = target.relative_to(root).as_posix()
    target_record = next(
        (
            item
            for item in round_state.get("artifacts", [])
            if isinstance(item, Mapping)
            and str(item.get("path", "")) == target_relative
        ),
        None,
    )
    if not isinstance(target_record, Mapping):
        raise LaunchError("The selected final theory artifact has no sealed record")

    def checked_source(
        path: Path, record: Mapping[str, Any], purpose: str
    ) -> dict[str, Any]:
        expected = str(record.get("sha256", "")).lower()
        payload = _review_source_payload(path, expected, purpose)
        try:
            recorded_size = int(record.get("size", -1))
        except (TypeError, ValueError) as exc:
            raise LaunchError(f"Sealed evidence has an invalid size: {purpose}") from exc
        if recorded_size != len(payload):
            raise LaunchError(f"Sealed evidence changed size: {purpose}")
        return {
            "source": path.resolve(),
            "sha256": expected,
            "size": len(payload),
            "purpose": purpose,
        }

    target_source = checked_source(
        target,
        target_record,
        "Exact final theoretical analysis selected for audit",
    )
    evidence: list[dict[str, Any]] = []
    for prior_round in source_run.get("rounds", []):
        if not isinstance(prior_round, Mapping):
            continue
        number = int(prior_round.get("n", 0) or 0)
        if number >= target_round or number < 1 or number > len(stages):
            continue
        role = str(stages[number - 1].get("role", ""))
        if role != "theorist" or not prior_round.get("completed"):
            continue
        for artifact in prior_round.get("artifacts", []):
            if not isinstance(artifact, Mapping):
                continue
            path = root / str(artifact.get("path", ""))
            evidence.append(
                checked_source(
                    path,
                    artifact,
                    f"Sealed theorist report from source round {number}",
                )
            )
    for summary in source_manifest.get("snapshots", {}).get("summaries", []):
        if not isinstance(summary, Mapping):
            continue
        path = Path(str(summary.get("path", "")))
        digest = str(summary.get("sha256", "")).lower()
        trust = (
            "trusted current input"
            if summary.get("trusted", True)
            else "comparison-only historical baseline"
        )
        payload = _review_source_payload(
            path,
            digest,
            f"Frozen {trust} from {summary.get('phase', 'a prior phase')}",
        )
        evidence.append({
            "source": path.resolve(),
            "sha256": digest,
            "size": len(payload),
            "purpose": (
                f"Frozen {trust} from "
                f"{summary.get('phase', 'a prior phase')}"
            ),
        })
    return {
        "schema_version": 1,
        "phase_slug": THEORETICAL_ANALYSIS_PHASE,
        "run_id": source_id,
        "target": {
            **target_source,
            "source_path": target_relative,
            "source_round": target_round,
            "source_role": "theorist",
        },
        "evidence": evidence,
        "source_baseline": source_baseline,
    }


def exact_rerun_options(
    project_dir: str | Path, phase_slug: str, run_id: str
) -> dict[str, str]:
    """Recover one prior run's exact special plan from its sealed manifest.

    Browser fields identify the prior run but do not supply plan details. This
    resolver verifies the manifest and revalidates any external source before
    returning launcher options.
    """

    root = Path(project_dir).resolve()
    try:
        manifest = _read_manifest(root, phase_slug, str(run_id).strip())
    except (KeyError, project_state.ProjectStateError) as exc:
        raise LaunchError("The prior run is unavailable") from exc
    frozen_phase = manifest.get("phase")
    if (
        not isinstance(frozen_phase, Mapping)
        or frozen_phase.get("slug") != phase_slug
    ):
        raise LaunchError("The prior run has no verified frozen phase plan")

    if phase_slug == THEORETICAL_ANALYSIS_PHASE:
        plan = str(frozen_phase.get("run_plan", "")).strip()
        if not plan:
            if frozen_phase.get("audit_only"):
                plan = THEORY_PLAN_AUDIT_ONLY
            elif frozen_phase.get("proof_audit"):
                plan = THEORY_PLAN_STANDARD_WITH_AUDIT
            else:
                plan = THEORY_PLAN_STANDARD
        if plan not in THEORY_RUN_PLANS:
            raise LaunchError("The prior Phase 03 run plan cannot be reproduced")
        result = {"kind": "theory", "theory_plan": plan}
        if plan == THEORY_PLAN_AUDIT_ONLY:
            try:
                frozen_source = _verified_frozen_theory_audit_source(root, manifest)
            except project_state.ProjectStateError as exc:
                raise LaunchError("The prior proof-audit source is unavailable") from exc
            source_run_id = str(frozen_source.get("run_id", "")).strip()
            frozen_target = frozen_source.get("target")
            if not source_run_id or not isinstance(frozen_target, Mapping):
                raise LaunchError("The prior proof-audit source is incomplete")
            try:
                current_source = _resolve_theory_audit_source(root, source_run_id)
            except project_state.ProjectStateError as exc:
                raise LaunchError("The prior proof-audit source is unavailable") from exc
            current_target = current_source.get("target")
            if (
                not isinstance(current_target, Mapping)
                or str(current_target.get("sha256", "")).lower()
                != str(frozen_target.get("sha256", "")).lower()
            ):
                raise LaunchError(
                    "The selected proof-audit source changed after the prior run"
                )
            result["proof_audit_source_run_id"] = source_run_id
            result["source_sha256"] = str(
                frozen_target.get("sha256", "")
            ).lower()
        return result

    if phase_slug == PAPER_WRITING_PHASE:
        paper_review = manifest.get("paper_review")
        if not isinstance(paper_review, Mapping):
            raise LaunchError("The prior Phase 06 run has no verified plan metadata")
        kind = str(paper_review.get("kind", ""))
        if kind == "full":
            return {"kind": "paper_full"}
        if kind != "review_only":
            raise LaunchError("The prior Phase 06 run plan cannot be reproduced")
        try:
            source_path, source_digest, _source_baseline = _resolve_paper_review_source(
                root,
                str(paper_review.get("source_path", "")),
                str(paper_review.get("source_sha256", "")),
            )
        except project_state.ProjectStateError as exc:
            raise LaunchError("The prior manuscript source is unavailable") from exc
        return {
            "kind": "paper_review_only",
            "review_target": source_path.relative_to(root).as_posix(),
            "review_target_sha256": source_digest,
        }

    raise LaunchError("Exact plan preservation is only available for Phase 03 and Phase 06")


def theory_audit_source_options(project_dir: str | Path) -> list[dict[str, Any]]:
    """List source run identities whose final theorist artifact still verifies."""

    root = Path(project_dir).resolve()
    options: list[dict[str, Any]] = []
    for number, run in enumerate(
        project_state.get_runs(root, THEORETICAL_ANALYSIS_PHASE), 1
    ):
        source_id = str(run.get("run_id", ""))
        if not source_id:
            continue
        try:
            source = _resolve_theory_audit_source(root, source_id)
        except (LaunchError, project_state.ProjectStateError):
            continue
        target = source["target"]
        options.append({
            "run_id": source_id,
            "run_number": number,
            "status": str(run.get("status", "recorded")),
            "source_round": int(target["source_round"]),
            "sha256": str(target["sha256"]),
        })
    return list(reversed(options))


def _freeze_theory_audit_source(
    project_dir: Path,
    run_id: str,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy the selected theory, evidence, and source baseline into this run."""

    destination = (
        run_context_dir(project_dir, THEORETICAL_ANALYSIS_PHASE, run_id)
        / "proof-audit"
    )
    destination.mkdir(parents=True, exist_ok=False)

    def freeze(
        item: Mapping[str, Any], filename: str, *, target: bool = False
    ) -> dict[str, Any]:
        source_path = Path(str(item.get("source", "")))
        expected = str(item.get("sha256", "")).lower()
        payload = _review_source_payload(
            source_path, expected, str(item.get("purpose", "proof-audit evidence"))
        )
        if len(payload) != int(item.get("size", -1)):
            raise LaunchError("Proof-audit evidence changed while the run was prepared")
        frozen_path = destination / filename
        _write_bytes_atomic(frozen_path, payload)
        record: dict[str, Any] = {
            "path": str(frozen_path),
            "sha256": expected,
            "size": len(payload),
            "purpose": str(item.get("purpose", "Proof-audit evidence")),
        }
        if target:
            record.update({
                "source_path": str(item.get("source_path", "")),
                "source_round": int(item.get("source_round", 0)),
                "source_role": str(item.get("source_role", "")),
            })
        return record

    target = freeze(source["target"], "target.md", target=True)
    evidence = [
        freeze(item, f"evidence-{index:02d}{Path(str(item['source'])).suffix or '.txt'}")
        for index, item in enumerate(source.get("evidence", []), 1)
        if isinstance(item, Mapping)
    ]
    source_baseline = source.get("source_baseline")
    if not isinstance(source_baseline, Mapping):
        raise LaunchError("The selected proof-audit source has no complete baseline")
    frozen_baseline = _freeze_source_baseline(
        project_dir,
        destination / "source-baseline",
        source_baseline,
    )
    return {
        "schema_version": 2,
        "phase_slug": THEORETICAL_ANALYSIS_PHASE,
        "run_id": str(source.get("run_id", "")),
        "target": target,
        "evidence": evidence,
        "source_baseline": frozen_baseline,
    }


def _verified_frozen_theory_audit_source(
    project_dir: Path, manifest: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Verify the audit-only target and evidence frozen into a run manifest."""

    source = manifest.get("proof_audit_source")
    if not isinstance(source, Mapping):
        raise LaunchError("The audit-only run has no frozen source record")
    source_schema = source.get("schema_version")
    if (
        source_schema not in {1, 2}
        or source.get("phase_slug") != THEORETICAL_ANALYSIS_PHASE
        or not str(source.get("run_id", "")).strip()
    ):
        raise LaunchError("The audit-only source identity is invalid")
    target = source.get("target")
    evidence = source.get("evidence")
    if not isinstance(target, Mapping) or not isinstance(evidence, list):
        raise LaunchError("The audit-only source inventory is invalid")
    context_root = run_context_dir(
        project_dir,
        str(manifest.get("phase_slug", "")),
        str(manifest.get("run_id", "")),
    ).resolve()
    total = 0
    for label, item in [("target", target), *[
        (f"evidence[{index}]", value) for index, value in enumerate(evidence)
    ]]:
        if not isinstance(item, Mapping):
            raise LaunchError(f"Audit-only {label} record is invalid")
        raw_path = Path(str(item.get("path", "")))
        if _path_uses_symlink_below(raw_path, context_root / "proof-audit"):
            raise LaunchError(f"Audit-only {label} cannot be a symbolic link")
        try:
            path = raw_path.resolve(strict=True)
            path.relative_to(context_root / "proof-audit")
            size = int(item.get("size", -1))
        except (OSError, TypeError, ValueError) as exc:
            raise LaunchError(f"Audit-only {label} is unavailable") from exc
        payload = _review_source_payload(
            path, str(item.get("sha256", "")), f"audit-only {label}"
        )
        if size != len(payload):
            raise LaunchError(f"Audit-only {label} changed size")
        total += size
    if total > MAX_REVIEW_BUNDLE_BYTES:
        raise LaunchError("Audit-only target and evidence exceed the safety limit")
    if source_schema == 2:
        _verified_frozen_source_baseline(
            project_dir,
            manifest,
            source.get("source_baseline"),
            expected_phase_slug=THEORETICAL_ANALYSIS_PHASE,
            relative_directory="proof-audit/source-baseline",
        )
    elif source.get("source_baseline") is not None:
        raise LaunchError("Legacy audit-only source has unexpected baseline metadata")
    return source


def _verify_frozen_inputs(
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    manifest: Mapping[str, Any],
) -> None:
    """Verify every frozen prompt input and every derived output boundary."""

    _validate_manifest_snapshot_schema(manifest)
    context_root = run_context_dir(project_dir, phase_slug, run_id).resolve()

    def verify_node(value: Any) -> None:
        if isinstance(value, Mapping):
            if "path" in value and "sha256" in value:
                raw_candidate = Path(str(value["path"]))
                if _path_uses_symlink_below(raw_candidate, context_root):
                    raise LaunchError("Frozen input path must not use symbolic links")
                try:
                    candidate = raw_candidate.resolve(strict=True)
                except OSError as exc:
                    raise LaunchError(
                        f"Frozen input is missing or unreadable: {value['path']}"
                    ) from exc
                try:
                    candidate.relative_to(context_root)
                except ValueError as exc:
                    raise LaunchError("Frozen input path escaped the run context directory") from exc
                if not candidate.is_file():
                    raise LaunchError(f"Frozen input is not a file: {candidate}")
                digest = _sha256_file(candidate)
                if digest != value["sha256"]:
                    raise LaunchError(f"Frozen input changed after launch: {candidate}")
            for nested in value.values():
                verify_node(nested)
        elif isinstance(value, list):
            for nested in value:
                verify_node(nested)

    verify_node(manifest.get("snapshots", {}))
    phase = manifest["phase"]
    expected_output = (
        project_dir
        / str(phase.get("folder", ""))
        / "run"
        / f"{int(manifest['run_number']):02d}"
    ).resolve()
    actual_output = Path(str(manifest["output_root"])).resolve()
    try:
        actual_output.relative_to(project_dir.resolve())
    except ValueError as exc:
        raise LaunchError("Run output root escaped the project directory") from exc
    if actual_output != expected_output:
        raise LaunchError("Run output root does not match the frozen phase plan")
    expected_summary = (
        project_dir / "phase-summaries" / phase_slug / f"{run_id}.html"
    ).resolve()
    if Path(str(manifest["summary_path"])).resolve() != expected_summary:
        raise LaunchError("Run summary path does not match the immutable run identity")
    if phase.get("audit_only") is True:
        if phase_slug != THEORETICAL_ANALYSIS_PHASE:
            raise LaunchError("An audit-only plan is only valid in Phase 03")
        _verified_frozen_theory_audit_source(project_dir, manifest)
    elif manifest.get("proof_audit_source") is not None:
        raise LaunchError("A non-audit-only run cannot declare a prior theory target")
    paper_review = manifest.get("paper_review")
    if isinstance(paper_review, Mapping) and paper_review.get("kind") == "review_only":
        review_schema = paper_review.get("schema_version", 1)
        if review_schema not in {1, 2}:
            raise LaunchError("Review-only source metadata schema is invalid")
        review_path = Path(str(paper_review.get("review_path", ""))).resolve()
        if review_path != _paper_manuscript_paths(actual_output)["review"]:
            raise LaunchError("Review-only manuscript path does not match the run plan")
        try:
            review_path.relative_to(project_dir.resolve())
        except ValueError as exc:
            raise LaunchError("Review-only manuscript escaped the project") from exc
        expected_digest = str(paper_review.get("review_sha256", "")).lower()
        if not review_path.is_file() or _sha256_file(review_path) != expected_digest:
            raise LaunchError("The preserved review-only manuscript is missing or changed")
        if review_schema == 2:
            _verified_frozen_source_baseline(
                project_dir,
                manifest,
                paper_review.get("source_baseline"),
                expected_phase_slug=PAPER_WRITING_PHASE,
                relative_directory="paper-review/source-baseline",
            )
        elif paper_review.get("source_baseline") is not None:
            raise LaunchError("Legacy review-only source has unexpected baseline metadata")


def _tracker_command(command: str, project_dir: Path, phase_slug: str, run_id: str, *extra: str) -> str:
    return _shell_join([
        sys.executable,
        Path(__file__).resolve(),
        command,
        "--project-dir",
        project_dir,
        "--phase",
        phase_slug,
        "--run-id",
        run_id,
        *extra,
    ])


def _phase_four_protocol_checkpoint_block(
    project_dir: Path,
    manifest: Mapping[str, Any],
    run: Mapping[str, Any],
    round_n: int,
    role: str,
    task_kind: str,
) -> str:
    """Return the exact sealed-protocol context for a Phase 04 task."""

    if str(manifest.get("phase_slug", "")) != NUMERICAL_VALIDATION_PHASE:
        return ""
    schema_version = _manifest_schema_version(manifest)
    if schema_version < 5:
        return ""
    declaration = manifest.get("protocol_checkpoint")
    if not isinstance(declaration, Mapping):
        raise LaunchError("Phase 04 task has no protocol checkpoint declaration")
    checkpoint_path = Path(str(declaration.get("path", "")))
    modern_split = schema_version >= 6
    protocol_root = (
        Path(str(declaration.get("protocol_root", "")))
        if modern_split
        else None
    )
    uses_sealed_protocol = modern_split and (
        (round_n == 1 and role == "data_scientist" and task_kind == "result")
        or (round_n > 1 and task_kind == "standard")
    )
    if uses_sealed_protocol:
        if protocol_root is None:
            raise LaunchError("Phase 04 run has no run-scoped protocol directory")
        checkpoint = run.get("protocol_checkpoint")
        if not isinstance(checkpoint, Mapping):
            raise LaunchError(
                "Phase 04 task has no sealed protocol checkpoint"
            )
        checkpoint_data = checkpoint.get("data")
        files = (
            checkpoint_data.get("protocol_files", [])
            if isinstance(checkpoint_data, Mapping)
            else []
        )
        file_lines = "\n".join(
            "- `{path}`; SHA-256 `{sha256}`; {size} bytes; purpose: {purpose}".format(
                path=item.get("path", ""),
                sha256=item.get("sha256", ""),
                size=item.get("size", "size not recorded"),
                purpose=item.get("purpose", ""),
            )
            for item in files
            if isinstance(item, Mapping)
        )
        if not file_lines:
            raise LaunchError("Phase 04 sealed checkpoint has no protocol files")
        assigned_workspace = (
            _planned_output(manifest, round_n, role).parent
            if schema_version >= 7
            else Path(str(manifest.get("output_root", project_dir)))
        )
        task_direction = (
            "Generate the initial study results only"
            if round_n == 1
            else "Perform this task using the sealed design and protocol only"
        )
        return f"""## Mechanically verified prespecification boundary

Research Hub verified the sealed checkpoint before dispatching this task:
`{checkpoint.get('path', '')}`, SHA-256 `{checkpoint.get('sha256', '')}`, sealed
at `{checkpoint.get('sealed_at', '')}`. Read and follow these immutable protocol
files:

{file_lines}

{task_direction}. Write code, saved results, figures, and the report only inside
the assigned write-limited workspace `{assigned_workspace}`. Do not modify the
checkpoint or any file under `{protocol_root}`. If the frozen design cannot
answer a scientific question, report that limitation rather than changing the
design within this run.
"""
    if round_n != 1 or role != "data_scientist":
        return ""
    expected_protocol_kind = "protocol" if modern_split else "standard"
    if task_kind != expected_protocol_kind:
        raise LaunchError("Phase 04 round 1 task kind is invalid")
    isolated_protocol_task = modern_split and schema_version >= 7
    if protocol_root is not None:
        try:
            protocol_example_path = (
                protocol_root.resolve().relative_to(project_dir.resolve())
                / "study-design.yaml"
            ).as_posix()
        except ValueError as exc:
            raise LaunchError("Phase 04 protocol directory escaped the project") from exc
        if isolated_protocol_task:
            protocol_location = (
                " in the exact write-limited workspace "
                f"`{protocol_root}`. Every task-written file must remain in this "
                "directory and must be either listed in the checkpoint, the checkpoint "
                "itself, or `protocol-stage.md`"
            )
            completion_boundary = (
                "After writing the checkpoint and protocol-stage report, finish this "
                "protocol-only task and stop. Do not generate any main result. The "
                "separate result task cannot be dispatched until Research Hub verifies "
                "the finished workspace and seals both records"
            )
        else:
            protocol_location = (
                " under the exact run-scoped directory "
                f"`{protocol_root}`. Do not write outside that directory except for "
                "the checkpoint JSON and the protocol-stage report path supplied below"
            )
            completion_boundary = (
                "After the command exits successfully, finish this protocol-only task "
                "and stop. Do not generate any main result. The separate result task "
                "cannot be dispatched until this task is done and Research Hub has "
                "verified the checkpoint"
            )
    else:
        protocol_example_path = "project-relative/protocol-file.yaml"
        protocol_location = ""
        completion_boundary = (
            "Proceed to main-result work only after the command exits successfully"
        )
    command = _tracker_command(
        "protocol-seal",
        project_dir,
        NUMERICAL_VALIDATION_PHASE,
        str(manifest.get("run_id", "")),
        "--checkpoint",
        str(checkpoint_path),
    )
    example = json.dumps(
        {
            "schema_version": project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "phase_slug": NUMERICAL_VALIDATION_PHASE,
            "run_id": str(manifest.get("run_id", "")),
            "main_results_generated": False,
            "protocol_files": [
                {
                    "path": protocol_example_path,
                    "sha256": "0" * 64,
                    "size": 1234,
                    "purpose": "State what this file fixes before the main study.",
                }
            ],
        },
        indent=2,
        ensure_ascii=False,
    )
    sealing_step = (
        "Finish the protocol-stage report and this task after writing the JSON. "
        "Research Hub will verify the completed isolated workspace and seal the "
        "checkpoint before it permits a result task. Do not invoke the sealing "
        "command yourself"
        if isolated_protocol_task
        else f"Then run this exact command:\n\n```text\n{command}\n```"
    )
    return f"""## Mandatory Phase 04 protocol checkpoint

Complete this checkpoint before generating any main simulation, model fit,
primary estimate, table, or figure. First write at least one complete protocol
or configuration file{protocol_location}. If a missing scientific choice prevents the planned
study, write a protocol-status file that records the unresolved choice so the
round can still return a scientifically useful Partial report. Do not generate
main results to bypass that limitation.

Write UTF-8 JSON to this exact path:

`{checkpoint_path}`

Use exactly these fields, replacing every placeholder with the project-relative
path, exact SHA-256, byte size, and scientific purpose of each listed file:

```json
{example}
```

{sealing_step}

{completion_boundary}. Never overwrite the checkpoint JSON or a listed file.
"""


def _task_instructions(
    project_dir: Path,
    phase: Mapping[str, Any],
    run_id: str,
    run_number: int,
    rounds: int,
    board_slug: str = "",
) -> str:
    phase_slug = str(phase["slug"])
    output_root = project_dir / str(phase.get("folder", "")) / "run" / f"{run_number:02d}"
    def commands(round_n: int, roles: Sequence[str], label: str) -> str:
        directive_file = output_root / ".directives" / f"round-{round_n:02d}.md"
        agents_csv = ",".join(roles)
        start = _tracker_command(
            "round-start",
            project_dir,
            phase_slug,
            run_id,
            "--round",
            str(round_n),
            "--directive-file",
            str(directive_file),
            "--agents",
            agents_csv,
        )
        if phase_slug == NUMERICAL_VALIDATION_PHASE and round_n == 1:
            if roles != ["data_scientist"]:
                raise LaunchError(
                    "Phase 04 round 1 must be assigned only to the data analyst"
                )
            protocol_dispatch = _tracker_command(
                "dispatch-task",
                project_dir,
                phase_slug,
                run_id,
                "--round",
                "1",
                "--role",
                "data_scientist",
                "--task-kind",
                "protocol",
                "--directive-file",
                str(directive_file),
            )
            result_dispatch = _tracker_command(
                "dispatch-task",
                project_dir,
                phase_slug,
                run_id,
                "--round",
                "1",
                "--role",
                "data_scientist",
                "--task-kind",
                "result",
                "--directive-file",
                str(directive_file),
            )
            output = output_root / "round-01" / "data_scientist.md"
            complete = _tracker_command(
                "round-complete",
                project_dir,
                phase_slug,
                run_id,
                "--round",
                "1",
                "--output",
                str(output),
            )
            return f"""#### Round 1: {label}

1. Write `{directive_file}` with the fixed scientific validation brief and a
   specific data-analyst directive. Use a file editing tool, not shell
   interpolation.
2. Record the round:
```text
{start}
```
3. Dispatch the protocol-only task:
```text
{protocol_dispatch}
```
4. Wait for that task to finish. Its write-limited workspace contains only the
   run-scoped empirical and computational design, executable protocol, checkpoint
   JSON, and protocol-stage report. Read its report.
5. Dispatch the result task only after the protocol task is done. The helper
   first verifies the complete isolated workspace, seals the checkpoint and
   protocol-stage report, and then permits dispatch:
```text
{result_dispatch}
```
6. Wait for the result task to finish and read `{output}`.
7. Record round completion only after both tasks are done:
```text
{complete}
```
The helper rejects a result task before the protocol task is done and the
run-scoped checkpoint is sealed. Do not create any additional task.
"""
        task_blocks: list[str] = []
        outputs: list[str] = []
        for role in roles:
            output = output_root / f"round-{round_n:02d}" / f"{role}.md"
            outputs.append(str(output))
            dispatch = _tracker_command(
                "dispatch-task",
                project_dir,
                phase_slug,
                run_id,
                "--round",
                str(round_n),
                "--role",
                role,
                "--directive-file",
                str(directive_file),
            )
            task_blocks.append(
                f"Dispatch `{role}` with the run helper:\n```text\n{dispatch}\n```"
            )
        output_arguments: list[str] = []
        for output in outputs:
            output_arguments.extend(["--output", output])
        complete = _tracker_command(
            "round-complete",
            project_dir,
            phase_slug,
            run_id,
            "--round",
            str(round_n),
            *output_arguments,
        )
        return (
            f"#### Round {round_n}: {label}\n\n"
            f"1. Write `{directive_file}` with the round objective and a specific brief "
            "for every listed role. Include any required prior-output handoff. Use a file "
            "editing tool, not shell interpolation.\n"
            f"2. Record the round:\n```text\n{start}\n```\n"
            f"3. Dispatch only the tasks listed for this round. The helper injects the "
            "user direction, frozen project brief, frozen approved summaries, prior-round "
            "artifacts, role playbook, output path, and an idempotency key.\n\n"
            + "\n\n".join(task_blocks)
            + "\n\n4. Wait for every listed task to finish BEFORE proceeding to the "
            "next step. Run this wait command in the FOREGROUND terminal — it "
            "blocks until all tasks complete:\n"
            f"```text\nhermes kanban --board {board_slug} watch --poll 30 "
            "--timeout 3600\n```\n"
            "CRITICAL: This is a single-turn session with no background "
            "callbacks. You MUST run this command in the FOREGROUND (not "
            "backgrounded, no `&`, no `background=True`, no "
            "`notify_on_complete`). Do NOT start it and then do other work. "
            "Run it as a normal blocking terminal command and WAIT for it to "
            "return. If you background it and end your turn, the entire run "
            "will fail. Only after the watch command returns should you read "
            "every output and proceed to step 5.\n"
            "5. Ask the helper to verify every recorded Hermes task is done and every "
            "artifact is nonempty before recording completion:\n"
            f"```text\n{complete}\n```"
        )

    pattern = str(phase.get("pattern", "parallel"))
    if pattern == "sequential":
        sections = []
        for number, stage in enumerate(phase.get("stages", []), 1):
            role = str(stage["role"])
            label = f"{stage.get('name', role)}. {stage.get('description', '')}".strip()
            sections.append(commands(number, [role], label))
        intro = (
            "This phase uses a fixed sequence of scientific stages. Run one stage at a time in the "
            "configured order. Each stage must read the prior stage output. Do not "
            "skip, combine, reorder, parallelize, or add stages."
        )
        return intro + "\n\n" + "\n\n".join(sections)

    roles = [str(role) for role in phase.get("members", [])]
    sections = []
    for number in range(1, rounds + 1):
        if pattern == "debate":
            label = (
                "independent proposals"
                if number == 1
                else "cross-critique and revision based on every prior-round output"
            )
        else:
            label = (
                "independent investigation"
                if number == 1
                else "targeted follow-up on gaps found in prior-round outputs"
            )
        sections.append(commands(number, roles, label))
    intro = (
        "Dispatch all listed roles for a round, then wait for all of them before "
        "starting the next round."
    )
    return intro + "\n\n" + "\n\n".join(sections)


def _planned_roles(manifest: Mapping[str, Any], round_n: int) -> list[str]:
    phase = manifest["phase"]
    if phase.get("pattern") == "sequential":
        stages = phase.get("stages", [])
        if round_n < 1 or round_n > len(stages):
            raise LaunchError(f"No configured sequential stage {round_n}")
        return [str(stages[round_n - 1]["role"])]
    rounds = int(manifest["rounds_requested"])
    if round_n < 1 or round_n > rounds:
        raise LaunchError(f"Run has no configured round {round_n}")
    return [str(role) for role in phase.get("members", [])]


def _planned_output(manifest: Mapping[str, Any], round_n: int, role: str) -> Path:
    return (
        Path(str(manifest["output_root"]))
        / f"round-{round_n:02d}"
        / f"{role}.md"
    )


def _planned_task_output(
    manifest: Mapping[str, Any], round_n: int, role: str, task_kind: str
) -> Path:
    if (
        str(manifest.get("phase_slug", "")) == NUMERICAL_VALIDATION_PHASE
        and _manifest_schema_version(manifest) >= 6
        and round_n == 1
        and role == "data_scientist"
        and task_kind == "protocol"
    ):
        return Path(str(manifest["output_root"])) / "protocol" / "protocol-stage.md"
    return _planned_output(manifest, round_n, role)


def _verify_completed_round_artifacts(
    project_dir: Path,
    run: Mapping[str, Any],
    *,
    before_round: int | None = None,
) -> None:
    """Verify completed evidence before it becomes input to later work."""

    root = project_dir.resolve()
    for round_ in run.get("rounds", []):
        number = int(round_.get("n", 0))
        if before_round is not None and number >= before_round:
            continue
        if not round_.get("completed"):
            continue
        outputs = [str(item) for item in round_.get("outputs", [])]
        artifacts = [
            item for item in round_.get("artifacts", []) if isinstance(item, Mapping)
        ]
        if sorted(outputs) != sorted(str(item.get("path", "")) for item in artifacts):
            raise LaunchError(f"Round {number} artifact records do not match its outputs")
        for artifact in artifacts:
            raw_path = str(artifact.get("path", ""))
            raw_candidate = root / raw_path
            if _path_uses_symlink_below(raw_candidate, root):
                raise LaunchError(
                    f"Round {number} artifact path uses a symbolic link: {raw_path}"
                )
            try:
                candidate = raw_candidate.resolve(strict=True)
                candidate.relative_to(root)
            except OSError as exc:
                raise LaunchError(
                    f"Round {number} artifact is missing: {raw_path}"
                ) from exc
            except ValueError as exc:
                raise LaunchError(f"Round {number} artifact escaped the project") from exc
            contents = _bounded_bytes(
                candidate,
                label=f"round {number} artifact",
                max_bytes=project_state.MAX_RUN_ARTIFACT_BYTES,
            )
            try:
                recorded_size = int(artifact.get("size", -1))
            except (TypeError, ValueError) as exc:
                raise LaunchError(
                    f"Round {number} artifact has an invalid size record: {raw_path}"
                ) from exc
            if len(contents) != recorded_size or hashlib.sha256(contents).hexdigest() != str(
                artifact.get("sha256", "")
            ).lower():
                raise LaunchError(
                    f"Round {number} artifact changed after completion: {raw_path}"
                )


def _verify_task_briefs(
    project_dir: Path,
    phase_slug: str,
    run: Mapping[str, Any],
    *,
    round_n: int | None = None,
) -> None:
    control_root = project_state.state_dir(project_dir).resolve()
    for round_ in run.get("rounds", []):
        if round_n is not None and round_.get("n") != round_n:
            continue
        for task in round_.get("tasks", []):
            raw_path = task.get("brief_path")
            expected_digest = str(task.get("brief_sha256", "")).lower()
            if not raw_path or not expected_digest:
                raise LaunchError(f"Task {task.get('task_id', '?')} has no sealed brief")
            raw_brief = Path(str(raw_path))
            if _path_uses_symlink_below(raw_brief, control_root):
                raise LaunchError(
                    f"Task {task.get('task_id', '?')} brief path uses a symbolic link"
                )
            try:
                brief = raw_brief.resolve(strict=True)
                brief.relative_to(control_root)
            except (OSError, ValueError) as exc:
                raise LaunchError(
                    f"Task {task.get('task_id', '?')} brief is unavailable"
                ) from exc
            brief_digest = _sha256_file(
                brief,
                max_bytes=MAX_TASK_BRIEF_BYTES,
                label=f"task {task.get('task_id', '?')} brief",
                allow_empty=False,
            )
            if brief_digest != expected_digest:
                raise LaunchError(
                    f"Task {task.get('task_id', '?')} brief changed after dispatch"
                )
            if task.get("review_bundle") is not None:
                _verified_review_bundle(
                    project_dir,
                    task,
                    phase_slug=phase_slug,
                    run_id=str(run.get("run_id", "")),
                    round_n=int(round_.get("n", 0)),
                )


def _task_brief_path(
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    round_n: int,
    role: str,
    task_kind: str = "standard",
) -> Path:
    kind_suffix = "" if task_kind == "standard" else f".{task_kind}"
    return (
        project_state.state_dir(project_dir)
        / "runs"
        / phase_slug
        / f"{run_id}.round-{round_n:02d}.{role}{kind_suffix}.task.md"
    )


def _review_bundle_root(
    project_dir: Path, phase_slug: str, run_id: str, round_n: int
) -> Path:
    return (
        project_state.state_dir(project_dir)
        / "review-workspaces"
        / phase_slug
        / run_id
        / f"round-{round_n:02d}-{PAPER_REVIEWER_ROLE}"
    )


def _review_source_payload(
    path: Path,
    expected_digest: str,
    label: str,
    *,
    max_bytes: int = MAX_REVIEW_MANUSCRIPT_BYTES,
) -> bytes:
    if path.is_symlink():
        raise LaunchError(f"Sealed reviewer input must not be a symbolic link: {label}")
    try:
        source = path.resolve(strict=True)
    except OSError as exc:
        raise LaunchError(f"Sealed reviewer input is unavailable: {label}") from exc
    if not source.is_file():
        raise LaunchError(f"Sealed reviewer input must be a regular file: {label}")
    if max_bytes < 1 or max_bytes > MAX_REVIEW_BUNDLE_BYTES:
        raise LaunchError(f"Sealed reviewer input has an invalid size policy: {label}")
    try:
        with source.open("rb") as handle:
            payload = handle.read(max_bytes + 1)
    except OSError as exc:
        raise LaunchError(f"Could not read sealed reviewer input: {label}") from exc
    if len(payload) > max_bytes:
        raise LaunchError(f"Sealed reviewer input exceeds the safety limit: {label}")
    if not payload.strip():
        raise LaunchError(f"Sealed reviewer input is empty: {label}")
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LaunchError(f"Sealed reviewer input is not valid UTF-8: {label}") from exc
    digest = hashlib.sha256(payload).hexdigest()
    if digest != str(expected_digest).lower() or _sha256_file(source) != digest:
        raise LaunchError(f"Sealed reviewer input changed before bundling: {label}")
    return payload


def _review_bundle_sources(
    project_dir: Path,
    manifest: Mapping[str, Any],
    run: Mapping[str, Any],
    round_n: int,
    *,
    reviewer_substage: str | None,
    proof_audit_stage: bool,
    review_snapshot: tuple[Path, str, str] | None,
) -> tuple[str, list[dict[str, Any]]]:
    """Select only the frozen files authorized for one reviewer task."""

    sources: list[dict[str, Any]] = []
    seen: set[Path] = set()

    def add(
        path: Path,
        digest: str,
        purpose: str,
        *,
        max_bytes: int = MAX_REVIEW_MANUSCRIPT_BYTES,
    ) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        sources.append({
            "source": resolved,
            "sha256": str(digest).lower(),
            "purpose": purpose,
            "max_bytes": max_bytes,
        })

    if reviewer_substage:
        if review_snapshot is None:
            raise LaunchError("Reviewer task has no sealed manuscript snapshot")
        review_path, _text, review_digest = review_snapshot
        add(review_path, review_digest, "Exact manuscript under review")

    stages = list(manifest.get("phase", {}).get("stages", []))
    if proof_audit_stage:
        if manifest.get("phase", {}).get("audit_only") is True:
            source = _verified_frozen_theory_audit_source(project_dir, manifest)
            target_record = source["target"]
            add(
                Path(str(target_record.get("path", ""))),
                str(target_record.get("sha256", "")),
                "Exact existing final theoretical analysis under audit",
            )
            for item in source.get("evidence", []):
                if isinstance(item, Mapping):
                    add(
                        Path(str(item.get("path", ""))),
                        str(item.get("sha256", "")),
                        str(item.get("purpose", "Sealed mathematical evidence")),
                    )
        else:
            theorist_rounds = [
                index
                for index, stage in enumerate(stages[: round_n - 1], 1)
                if str(stage.get("role")) == "theorist"
            ]
            if not theorist_rounds:
                raise LaunchError("The selected proof audit has no preceding theorist stage")
            target_round = theorist_rounds[-1]
            target_state = run.get("rounds", [])[target_round - 1]
            target = _planned_output(manifest, target_round, "theorist").resolve()
            relative_target = target.relative_to(project_dir.resolve()).as_posix()
            target_record = next(
                (
                    item
                    for item in target_state.get("artifacts", [])
                    if isinstance(item, Mapping)
                    and str(item.get("path", "")) == relative_target
                ),
                None,
            )
            if not isinstance(target_record, Mapping):
                raise LaunchError("The final theory artifact has no sealed record")
            add(
                target,
                str(target_record.get("sha256", "")),
                "Exact final theoretical analysis under audit",
            )

    if reviewer_substage == "contextual":
        paper_review = manifest.get("paper_review")
        if (
            isinstance(paper_review, Mapping)
            and paper_review.get("kind") == "review_only"
            and paper_review.get("schema_version") == 2
        ):
            source_baseline = _verified_frozen_source_baseline(
                project_dir,
                manifest,
                paper_review.get("source_baseline"),
                expected_phase_slug=PAPER_WRITING_PHASE,
                relative_directory="paper-review/source-baseline",
            )
            baseline_status = _source_baseline_status(source_baseline)
            source_run_id = str(source_baseline.get("run_id", ""))
            for name, purpose, maximum in (
                (
                    "summary",
                    f"Frozen {baseline_status} source summary from run {source_run_id}",
                    MAX_SOURCE_SUMMARY_BYTES,
                ),
                (
                    "decision_record",
                    f"Frozen {baseline_status} structured source record from run {source_run_id}",
                    MAX_SOURCE_DECISION_BYTES,
                ),
            ):
                item = source_baseline[name]
                add(
                    Path(str(item.get("path", ""))),
                    str(item.get("sha256", "")),
                    purpose,
                    max_bytes=maximum,
                )

    if reviewer_substage == "contextual" or proof_audit_stage:
        team_snapshots = manifest.get("snapshots", {}).get("team", {})
        if isinstance(team_snapshots, Mapping):
            for name, purpose in (
                ("charter", "Frozen shared team charter"),
                ("norms", "Frozen shared scientific standards"),
            ):
                record = team_snapshots.get(name)
                if isinstance(record, Mapping):
                    add(
                        Path(str(record.get("path", ""))),
                        str(record.get("sha256", "")),
                        purpose,
                    )
        audit_only = bool(manifest.get("phase", {}).get("audit_only"))
        if not (proof_audit_stage and audit_only):
            for prior_round in run.get("rounds", [])[: round_n - 1]:
                number = int(prior_round.get("n", 0) or 0)
                prior_role = (
                    str(stages[number - 1].get("role", ""))
                    if 1 <= number <= len(stages)
                    else ""
                )
                if proof_audit_stage and prior_role == "research_lead":
                    continue
                for artifact in prior_round.get("artifacts", []):
                    if not isinstance(artifact, Mapping):
                        continue
                    add(
                        project_dir / str(artifact.get("path", "")),
                        str(artifact.get("sha256", "")),
                        f"Sealed round {number} report from {prior_role or 'configured role'}",
                    )
            for summary in manifest.get("snapshots", {}).get("summaries", []):
                if not isinstance(summary, Mapping):
                    continue
                trust = (
                    "trusted current input"
                    if summary.get("trusted", True)
                    else "comparison-only historical baseline"
                )
                add(
                    Path(str(summary.get("path", ""))),
                    str(summary.get("sha256", "")),
                    f"Frozen {trust} from {summary.get('phase', 'prior phase')}",
                )

    if proof_audit_stage:
        subtype = "proof_audit"
    elif reviewer_substage == "independent":
        subtype = "independent_manuscript_reading"
    elif reviewer_substage == "contextual":
        subtype = "contextual_manuscript_assessment"
    else:
        raise LaunchError("Paper reviewer task has no configured review subtype")
    return subtype, sources


def _reviewer_task_text(
    *,
    phase_slug: str,
    run_id: str,
    round_n: int,
    subtype: str,
    soul_text: str,
    soul_digest: str,
    protocol_text: str,
    protocol_digest: str,
    inputs: Sequence[Mapping[str, Any]],
    user_direction: str,
    review_directive: str,
) -> str:
    inventory = "\n".join(
        f"- `{item['path']}`: {item['purpose']} (SHA-256 `{item['sha256']}`)"
        for item in inputs
    )
    if subtype == "independent_manuscript_reading":
        objective = (
            "Read only the manuscript input. Record the first-reader assessment before "
            "consulting any author evidence. No other scientific context is authorized."
        )
        outcome_scope = "the independent manuscript reading"
    elif subtype == "contextual_manuscript_assessment":
        objective = (
            "Preserve the first-reading report, then compare the same manuscript with "
            "the listed sealed author reports and source baselines. Distinguish this "
            "traceability assessment from source-level verification."
        )
        outcome_scope = "the contextual manuscript assessment"
    else:
        objective = (
            "Audit the exact final theoretical analysis using only the listed mathematical "
            "evidence. Do not revise the theory or infer the research lead's preference."
        )
        outcome_scope = "the proof audit"
    scope_block = ""
    if subtype == "proof_audit":
        directive = review_directive.strip()
        if not directive:
            raise LaunchError("Proof audit requires a nonempty sealed audit directive")
        scope_block = f"""
## Prespecified audit scope

User direction supplied for this run:
{user_direction.strip() or '(none)'}

Sealed research lead directive for this audit:
{directive}

The directive prioritizes statements and checks but does not change the sealed
theory target or expand the authorized evidence.
"""
    elif subtype == "contextual_manuscript_assessment":
        directive = review_directive.strip()
        if not directive:
            raise LaunchError(
                "Contextual manuscript assessment requires a nonempty sealed directive"
            )
        scope_block = f"""
## Contextual assessment direction

User direction supplied for this run:
{user_direction.strip() or '(none)'}

Sealed research lead directive for this assessment:
{directive}

Use these directions only after preserving and reading the independent
first-reading report. They prioritize checks but do not add evidence to the
authorized inputs. Underlying proofs, code, data, or saved results that are not
listed below are not independently available; label source-level verification
of those items Not assessable.
"""
    return f"""# Research Hub sealed-context reviewer task

This task belongs only to phase `{phase_slug}`, run `{run_id}`, round {round_n}.
{objective}

The workspace contains only the files listed below, `task.md`, `bundle.json`, and
the designated output directory. Do not seek or use files outside this workspace.
The bundle hashes define the authorized context.

## Reviewer identity and standards

The reviewer role instructions are sealed here with SHA-256 `{soul_digest}`.

BEGIN FROZEN ROLE INSTRUCTIONS

{soul_text.rstrip()}

END FROZEN ROLE INSTRUCTIONS

The phase review protocol is sealed here with SHA-256 `{protocol_digest}`.

BEGIN FROZEN REVIEW PROTOCOL

{protocol_text.rstrip()}

END FROZEN REVIEW PROTOCOL
{scope_block}
## Authorized scientific inputs

{inventory or '- None'}

## Required report

Write one nonempty UTF-8 Markdown report to `output/report.md`. Begin with
`Scientific completion outcome: Complete`, `Scientific completion outcome:
Partial`, or `Scientific completion outcome: Failed`. The outcome refers only to
{outcome_scope}. For Partial or Failed, state the completed checks, usable
evidence, missing material, scientific consequence, and next verification.

Record the hash of the principal target and every listed source actually used.
Do not edit the input files. Complete the kanban task only after the report exists.
"""


def _prepare_review_bundle(
    project_dir: Path,
    manifest: Mapping[str, Any],
    run: Mapping[str, Any],
    round_n: int,
    *,
    reviewer_substage: str | None,
    proof_audit_stage: bool,
    review_snapshot: tuple[Path, str, str] | None,
    soul_text: str,
    soul_digest: str,
    protocol_text: str,
    protocol_digest: str,
    review_directive: str = "",
) -> tuple[Path, Path, str, dict[str, str]]:
    subtype, sources = _review_bundle_sources(
        project_dir,
        manifest,
        run,
        round_n,
        reviewer_substage=reviewer_substage,
        proof_audit_stage=proof_audit_stage,
        review_snapshot=review_snapshot,
    )
    raw_root = _review_bundle_root(
        project_dir, str(manifest["phase_slug"]), str(manifest["run_id"]), round_n
    )
    control_root = _ensure_contained_directory(
        project_state.state_dir(project_dir),
        project_dir.parent,
        label="project control directory",
    )
    root = _ensure_contained_directory(
        raw_root, control_root, label="reviewer workspace"
    )
    inputs_dir = root / "inputs"
    records: list[dict[str, Any]] = []
    total = 0
    for index, source in enumerate(sources, 1):
        payload = _review_source_payload(
            Path(source["source"]),
            str(source["sha256"]),
            str(source["purpose"]),
            max_bytes=int(source.get("max_bytes", MAX_REVIEW_MANUSCRIPT_BYTES)),
        )
        total += len(payload)
        if total > MAX_REVIEW_BUNDLE_BYTES:
            raise LaunchError("Sealed reviewer inputs exceed the aggregate safety limit")
        suffix = Path(source["source"]).suffix.lower()
        if suffix not in {".md", ".html", ".txt", ".json"}:
            suffix = ".txt"
        relative = Path("inputs") / f"input-{index:02d}{suffix}"
        destination = _contained_file_destination(
            root / relative, root, label="reviewer input destination"
        )
        _write_bytes_atomic(destination, payload)
        if _sha256_file(destination) != str(source["sha256"]).lower():
            raise LaunchError("A reviewer input changed while its bundle was written")
        records.append({
            "path": relative.as_posix(),
            "sha256": str(source["sha256"]).lower(),
            "size": len(payload),
            "purpose": str(source["purpose"]),
        })

    task_text = _reviewer_task_text(
        phase_slug=str(manifest["phase_slug"]),
        run_id=str(manifest["run_id"]),
        round_n=round_n,
        subtype=subtype,
        soul_text=soul_text,
        soul_digest=soul_digest,
        protocol_text=protocol_text,
        protocol_digest=protocol_digest,
        inputs=records,
        user_direction=str(manifest.get("user_feedback") or ""),
        review_directive=review_directive,
    )
    task_path = _contained_file_destination(
        root / "task.md", root, label="reviewer task destination"
    )
    _write_text_atomic(task_path, task_text)
    task_payload = _bounded_bytes(
        task_path,
        label="reviewer task",
        max_bytes=MAX_TASK_BRIEF_BYTES,
    )
    output_path = _contained_file_destination(
        root / "output" / "report.md", root, label="reviewer report destination"
    )
    bundle = {
        "schema_version": REVIEW_BUNDLE_SCHEMA_VERSION,
        "phase_slug": str(manifest["phase_slug"]),
        "run_id": str(manifest["run_id"]),
        "round": round_n,
        "role": PAPER_REVIEWER_ROLE,
        "subtype": subtype,
        "task": {
            "path": "task.md",
            "sha256": hashlib.sha256(task_payload).hexdigest(),
            "size": len(task_payload),
        },
        "inputs": records,
        "output": {"path": "output/report.md", "max_bytes": MAX_REVIEW_OUTPUT_BYTES},
    }
    manifest_path = _contained_file_destination(
        root / "bundle.json", root, label="reviewer bundle manifest destination"
    )
    _write_text_atomic(
        manifest_path, json.dumps(bundle, indent=2, ensure_ascii=False, sort_keys=True)
    )
    bundle_record = {
        "root": str(root),
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256_file(manifest_path),
    }
    return root, task_path, bundle["task"]["sha256"], bundle_record


def _verified_review_bundle(
    project_dir: Path,
    task: Mapping[str, Any],
    *,
    phase_slug: str,
    run_id: str,
    round_n: int,
) -> tuple[Path, Mapping[str, Any]]:
    record = task.get("review_bundle")
    if not isinstance(record, Mapping):
        raise LaunchError("Reviewer task has no sealed workspace record")
    control_root = project_state.state_dir(project_dir).resolve()
    raw_root = Path(str(record.get("root", "")))
    raw_manifest = Path(str(record.get("manifest_path", "")))
    if _path_uses_symlink_below(raw_root, control_root / "review-workspaces"):
        raise LaunchError("Reviewer workspace path must not use symbolic links")
    if _path_uses_symlink_below(raw_manifest, raw_root):
        raise LaunchError("Reviewer workspace manifest must not use symbolic links")
    try:
        root = raw_root.resolve(strict=True)
        root.relative_to(control_root / "review-workspaces")
        manifest_path = raw_manifest.resolve(strict=True)
        manifest_path.relative_to(root)
    except (OSError, ValueError) as exc:
        raise LaunchError("Reviewer workspace escaped project control storage") from exc
    if manifest_path != root / "bundle.json":
        raise LaunchError("Reviewer workspace manifest path is invalid")
    payload = _bounded_bytes(
        manifest_path,
        label="reviewer workspace manifest",
        max_bytes=project_state.MAX_CONTROL_FILE_BYTES,
    )
    if hashlib.sha256(payload).hexdigest() != str(record.get("manifest_sha256", "")).lower():
        raise LaunchError("Reviewer workspace manifest changed after dispatch")
    try:
        bundle = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise LaunchError("Reviewer workspace manifest is invalid") from exc
    if (
        not isinstance(bundle, Mapping)
        or bundle.get("schema_version") != REVIEW_BUNDLE_SCHEMA_VERSION
        or bundle.get("phase_slug") != phase_slug
        or bundle.get("run_id") != run_id
        or bundle.get("round") != round_n
        or bundle.get("role") != PAPER_REVIEWER_ROLE
    ):
        raise LaunchError("Reviewer workspace identity is invalid")
    leaves = [bundle.get("task"), *list(bundle.get("inputs", []))]
    for leaf in leaves:
        if not isinstance(leaf, Mapping):
            raise LaunchError("Reviewer workspace file record is invalid")
        raw_candidate = root / str(leaf.get("path", ""))
        if _path_uses_symlink_below(raw_candidate, root):
            raise LaunchError("Reviewer workspace input must not use symbolic links")
        try:
            candidate = raw_candidate.resolve(strict=True)
            candidate.relative_to(root)
            size = int(leaf.get("size", -1))
        except (OSError, ValueError, TypeError) as exc:
            raise LaunchError("Reviewer workspace input is unavailable") from exc
        if size < 1 or size > MAX_REVIEW_BUNDLE_BYTES:
            raise LaunchError("Reviewer workspace input size is invalid")
        contents = _bounded_bytes(
            candidate,
            label="reviewer workspace input",
            max_bytes=MAX_REVIEW_BUNDLE_BYTES,
        )
        if (
            len(contents) != size
            or hashlib.sha256(contents).hexdigest()
            != str(leaf.get("sha256", "")).lower()
        ):
            raise LaunchError("Reviewer workspace input changed after dispatch")
    task_record = bundle["task"]
    if (
        str((root / str(task_record["path"])).resolve())
        != str(Path(str(task.get("brief_path", ""))).resolve())
        or str(task_record["sha256"]).lower()
        != str(task.get("brief_sha256", "")).lower()
    ):
        raise LaunchError("Reviewer task brief does not match its workspace manifest")
    return root, bundle


def _import_review_bundle_output(
    project_dir: Path,
    manifest: Mapping[str, Any],
    task: Mapping[str, Any],
    round_n: int,
) -> Path:
    phase_slug = str(manifest["phase_slug"])
    run_id = str(manifest["run_id"])
    root, bundle = _verified_review_bundle(
        project_dir,
        task,
        phase_slug=phase_slug,
        run_id=run_id,
        round_n=round_n,
    )
    output_record = bundle.get("output")
    if not isinstance(output_record, Mapping):
        raise LaunchError("Reviewer workspace output record is invalid")
    raw_output = root / str(output_record.get("path", ""))
    if _path_uses_symlink_below(raw_output, root):
        raise LaunchError("Reviewer report must not use symbolic links")
    try:
        output = raw_output.resolve(strict=True)
        output.relative_to(root / "output")
        max_bytes = int(output_record.get("max_bytes", 0))
    except (OSError, ValueError, TypeError) as exc:
        raise LaunchError("Reviewer report is missing from its sealed workspace") from exc
    if not output.is_file():
        raise LaunchError("Reviewer report must be a regular file")
    if max_bytes < 1 or max_bytes > MAX_REVIEW_OUTPUT_BYTES:
        raise LaunchError("Reviewer report size policy is invalid")
    payload = _bounded_bytes(
        output,
        label="reviewer report",
        max_bytes=max_bytes,
    )
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LaunchError("Reviewer report is not valid UTF-8") from exc
    destination = _contained_file_destination(
        _planned_output(manifest, round_n, PAPER_REVIEWER_ROLE),
        project_dir,
        label="imported reviewer report destination",
    )
    if destination.exists():
        existing = _bounded_bytes(
            destination,
            label="imported reviewer report",
            max_bytes=MAX_REVIEW_OUTPUT_BYTES,
        )
        if existing != payload:
            raise LaunchError("Reviewer report destination already contains different content")
    else:
        _write_bytes_atomic(destination, payload)
    if _bounded_bytes(
        destination,
        label="imported reviewer report",
        max_bytes=MAX_REVIEW_OUTPUT_BYTES,
    ) != payload:
        raise LaunchError("Reviewer report changed while it was imported")
    return destination


def _directive_text(
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    round_n: int,
    directive_file: str | Path,
) -> str:
    manifest = _read_manifest(project_dir, phase_slug, run_id)
    expected = (
        Path(str(manifest["output_root"]))
        / ".directives"
        / f"round-{round_n:02d}.md"
    ).resolve()
    try:
        expected.relative_to(project_dir.resolve())
    except ValueError as exc:
        raise LaunchError("Round directive path escaped the project directory") from exc
    candidate = Path(directive_file).resolve()
    if candidate != expected:
        raise LaunchError(f"Directive must use the run-scoped path: {expected}")
    text = _read_utf8_bounded(
        candidate,
        label="round directive",
        max_bytes=MAX_DIRECTIVE_BYTES,
    ).strip()
    if not text:
        raise LaunchError("Round directive cannot be empty")
    if len(text) > 50_000:
        raise LaunchError("Round directive cannot exceed 50,000 characters")
    return text


def _task_id_from_json(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("id", "task_id"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("task", "data", "result"):
            found = _task_id_from_json(payload.get(key))
            if found:
                return found
    return None


def _task_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        nested = payload.get("task")
        if isinstance(nested, dict):
            return nested
        return payload
    return {}


def _dispatch_task(
    project_dir: str | Path,
    phase_slug: str,
    run_id: str,
    round_n: int,
    role: str,
    directive_file: str | Path,
    task_kind: str = "standard",
) -> str:
    """Create and record one exact, context-complete Hermes task."""

    project_dir = Path(project_dir).resolve()
    manifest = _read_manifest(project_dir, phase_slug, run_id)
    _verify_frozen_inputs(project_dir, phase_slug, run_id, manifest)
    planned_roles = _planned_roles(manifest, round_n)
    if role not in planned_roles:
        raise LaunchError(
            f"Role {role!r} is not planned for round {round_n}: {', '.join(planned_roles)}"
        )
    run = project_state.get_run(project_dir, phase_slug, run_id)
    if run.get("status") != "running":
        raise LaunchError("Tasks can only be dispatched for a running run")
    if round_n < 1 or round_n > len(run.get("rounds", [])):
        raise LaunchError("Record the round before dispatching its tasks")
    round_state = run["rounds"][round_n - 1]
    if set(round_state.get("agents", [])) != set(planned_roles):
        raise LaunchError("Recorded round roles do not match the frozen run plan")
    _verify_completed_round_artifacts(project_dir, run, before_round=round_n)
    _verify_task_briefs(project_dir, phase_slug, run, round_n=round_n)
    phase_four_split = (
        phase_slug == NUMERICAL_VALIDATION_PHASE
        and _manifest_schema_version(manifest) >= 6
        and round_n == 1
        and role == "data_scientist"
    )
    if phase_four_split:
        if task_kind not in {"protocol", "result"}:
            raise LaunchError(
                "Phase 04 round 1 requires separate protocol and result tasks"
            )
    elif task_kind != "standard":
        raise LaunchError("A specialized task kind is valid only for Phase 04 round 1")
    existing = [
        task
        for task in round_state.get("tasks", [])
        if task.get("role") == role
        and str(task.get("task_kind", "standard")) == task_kind
    ]
    if existing:
        if len(existing) == 1:
            if (
                phase_slug == NUMERICAL_VALIDATION_PHASE
                and _manifest_schema_version(manifest) >= 6
                and (
                    (round_n == 1 and task_kind == "result")
                    or round_n > 1
                )
            ):
                project_state.require_protocol_checkpoint(
                    project_dir, phase_slug, run_id
                )
            return str(existing[0]["task_id"])
        raise LaunchError(
            f"Multiple {task_kind} task IDs are already recorded for role {role}"
        )
    if phase_four_split:
        recorded_tasks = [
            task
            for task in round_state.get("tasks", [])
            if isinstance(task, Mapping)
        ]
        if task_kind == "protocol":
            if recorded_tasks or run.get("protocol_checkpoint"):
                raise LaunchError(
                    "The Phase 04 protocol task must be the first task in round 1"
                )
        else:
            protocol_tasks = [
                task
                for task in recorded_tasks
                if task.get("role") == "data_scientist"
                and task.get("task_kind") == "protocol"
            ]
            if len(protocol_tasks) != 1 or len(recorded_tasks) != 1:
                raise LaunchError(
                    "Phase 04 result work requires exactly one preceding protocol task"
                )
            protocol_status = _show_task(
                manifest, str(protocol_tasks[0].get("task_id", ""))
            ).get("status")
            if protocol_status != "done":
                raise LaunchError(
                    "Phase 04 result work cannot start until the protocol task is done"
                )
            if _manifest_schema_version(manifest) >= 7:
                declaration = manifest.get("protocol_checkpoint")
                if not isinstance(declaration, Mapping):
                    raise LaunchError(
                        "Phase 04 isolated protocol task has no checkpoint declaration"
                    )
                project_state.seal_protocol_checkpoint(
                    project_dir,
                    phase_slug,
                    run_id,
                    str(declaration.get("path", "")),
                    isolated_task_completed=True,
                )
            project_state.require_protocol_checkpoint(
                project_dir, phase_slug, run_id
            )
            run = project_state.get_run(project_dir, phase_slug, run_id)
    elif (
        phase_slug == NUMERICAL_VALIDATION_PHASE
        and _manifest_schema_version(manifest) >= 6
        and round_n > 1
    ):
        project_state.require_protocol_checkpoint(
            project_dir, phase_slug, run_id
        )
        run = project_state.get_run(project_dir, phase_slug, run_id)
        round_state = run["rounds"][round_n - 1]

    directive = _directive_text(
        project_dir, phase_slug, run_id, round_n, directive_file
    )
    if directive != str(round_state.get("lead_directive", "")).strip():
        raise LaunchError("Round directive changed after it was recorded")
    snapshots = manifest["snapshots"]
    reviewer_substage = _paper_reviewer_substage(manifest, round_n)
    proof_audit_stage = _is_proof_audit_stage(manifest, round_n, role)
    context_lines = []
    if reviewer_substage != "independent":
        for item in snapshots.get("summaries", []):
            trust = (
                "trusted current input"
                if item.get("trusted", True)
                else "historical baseline"
            )
            context_lines.append(
                f"- {item['phase']} run {item['run_id']} ({trust}): {item['path']}"
            )
    prior_outputs: list[str] = []
    prior_artifacts: list[Mapping[str, Any]] = []
    for prior_round in run.get("rounds", [])[: round_n - 1]:
        prior_outputs.extend(str(item) for item in prior_round.get("outputs", []))
        prior_artifacts.extend(
            item
            for item in prior_round.get("artifacts", [])
            if isinstance(item, Mapping)
        )
    if reviewer_substage == "contextual":
        prior_text = "\n".join(
            f"- {project_dir / str(item.get('path', ''))} "
            f"(SHA-256 {item.get('sha256', 'not recorded')})"
            for item in prior_artifacts
        )
    else:
        prior_text = "\n".join(f"- {project_dir / item}" for item in prior_outputs)
    output = _contained_file_destination(
        _planned_task_output(manifest, round_n, role, task_kind),
        project_dir,
        label=f"round {round_n} {role} output",
    )
    playbook = snapshots["playbooks"][f"{role}.md"]["path"]
    try:
        soul_entry = snapshots["souls"][role]
    except (KeyError, TypeError) as exc:
        raise LaunchError(
            "This run has no frozen role soul. Start a new run so its full "
            "instruction context can be sealed."
        ) from exc
    soul_text, soul_digest, soul_path = _frozen_snapshot_text(
        soul_entry, f"souls.{role}"
    )
    reviewer_playbook = ""
    reviewer_playbook_digest = ""
    if role == PAPER_REVIEWER_ROLE:
        reviewer_playbook, reviewer_playbook_digest, _ = _frozen_snapshot_text(
            snapshots["playbooks"][f"{role}.md"], f"playbooks.{role}.md"
        )
    review_snapshot = (
        _paper_review_manuscript_snapshot(manifest) if reviewer_substage else None
    )
    review_manuscript_block = _paper_review_manuscript_block(
        manifest,
        role,
        "embedded in this task brief" if reviewer_substage == "independent" else playbook,
        round_n,
        review_snapshot,
    )
    if reviewer_substage and review_snapshot:
        review_path, _, review_digest = review_snapshot
        project_state.seal_review_target(
            project_dir, phase_slug, run_id, review_path, review_digest
        )
    protocol_checkpoint_block = _phase_four_protocol_checkpoint_block(
        project_dir, manifest, run, round_n, role, task_kind
    )
    method_selection_block = _method_selection_prompt_block(
        manifest.get("method_selection")
    )

    if proof_audit_stage:
        proof_material = _proof_audit_material_block(
            project_dir, manifest, run, round_n
        )
        task_brief = f"""# Research Hub independent proof audit

This task belongs only to phase `{phase_slug}`, run `{run_id}`, round {round_n}.
It is a separate verification task. Do not revise the theory or start another
phase.

## Audit scope

User direction supplied for this run:
{manifest.get('user_feedback') or '(none)'}

Research lead directive for the audit:
{directive}

These instructions select the central statements and checks to prioritize.
They do not change the sealed theory target or expand the available evidence.

{method_selection_block}

## Frozen reviewer identity and reasoning standards

The reviewer role soul is sealed into this brief with SHA-256 `{soul_digest}`.

BEGIN FROZEN ROLE SOUL

{soul_text.rstrip()}

END FROZEN ROLE SOUL

## Frozen proof-audit protocol

The Phase 03 proof-audit protocol is sealed into this brief with SHA-256
`{reviewer_playbook_digest}`.

BEGIN FROZEN PROOF-AUDIT PROTOCOL

{reviewer_playbook.rstrip()}

END FROZEN PROOF-AUDIT PROTOCOL

{proof_material}

## Required output

Write only the independent proof-audit report to this exact path:
{output}

Begin with `Scientific completion outcome: Complete`, `Scientific completion
outcome: Partial`, or `Scientific completion outcome: Failed`. For Partial or
Failed, state attempted and completed checks, usable evidence, missing material
and its cause, scientific consequence, Scientific record changes, and the next
verification needed. A missing report is a technical failure, not a scientific
outcome.

Record the target path and hash, every source used, and any item that could not
be checked. When the report exists, complete this kanban task with a concise
handoff summary.
"""
    elif reviewer_substage == "independent":
        task_brief = f"""# Research Hub independent manuscript reading

This task belongs only to phase `{phase_slug}`, run `{run_id}`, round {round_n}.
It is intentionally separated from the project brief, user direction, phase
summaries, author reports, and prior-round artifacts.

## Frozen reviewer identity and reasoning standards

The role soul is sealed into this brief with SHA-256 `{soul_digest}`.

BEGIN FROZEN ROLE SOUL

{soul_text.rstrip()}

END FROZEN ROLE SOUL

## Frozen reviewer protocol

The Phase 06 reviewer protocol is sealed into this brief with SHA-256
`{reviewer_playbook_digest}`. In this substage, follow only its Initial
Independent Reading requirements.

BEGIN FROZEN REVIEWER PROTOCOL

{reviewer_playbook.rstrip()}

END FROZEN REVIEWER PROTOCOL

{review_manuscript_block}

## Required output

Write only the independent first-reading report to this exact path:
{output}

Begin with `Scientific completion outcome: Complete`, `Scientific completion
outcome: Partial`, or `Scientific completion outcome: Failed`. For Partial or
Failed, state what reading was attempted and completed, usable manuscript
evidence, what was missing and why, the consequence for the independent
assessment, and the next verification needed. Do not consult the accepted
scientific record or propose Scientific record changes in this context-restricted
substage.

Do not inspect any other project file in this substage. Record the reviewed
path and hash from the sealed manuscript block. When the report exists,
complete this kanban task with a concise handoff summary.
"""
    else:
        task_brief = f"""# Research Hub run task

This task belongs only to phase `{phase_slug}`, run `{run_id}`, round {round_n}.
The user explicitly authorized this run. Do not launch phases or approve results.

## Frozen role identity and reasoning standards

Read this embedded role soul before the phase-specific protocol. It is copied
from `{soul_path}` and sealed into this task brief with SHA-256 `{soul_digest}`.

BEGIN FROZEN ROLE SOUL

{soul_text.rstrip()}

END FROZEN ROLE SOUL

{review_manuscript_block}

## Frozen run inputs

Read these files before working:
- Role protocol: {playbook}
- Project brief: {snapshots['setting']['path']}
- Team charter: {snapshots['team']['charter']['path']}
- Team norms: {snapshots['team']['norms']['path']}

User direction for the run:
{manifest.get('user_feedback') or '(none)'}

Research lead directive for this round:
{directive}

Approved context and prior baseline snapshots:
{chr(10).join(context_lines) if context_lines else '- None available'}

Prior-round artifacts that must be read for critique or handoff:
{prior_text if prior_text else '- This is the first round or stage'}

{method_selection_block}

{protocol_checkpoint_block}

Write one nonempty Markdown report to this exact path:
{output}

Begin the report with `Scientific completion outcome: Complete`, `Scientific
completion outcome: Partial`, or `Scientific completion outcome: Failed`. A
Partial or Failed report must state attempted and completed work, usable
evidence, missing work and its cause, scientific consequence, Scientific record
changes, and the next verification needed. A missing or unreadable output artifact is a
technical failure and cannot be replaced by a narrative completion claim.

Reference supporting code, data, figures, citations, and uncertainties by path.
When the report exists, complete this kanban task with a concise handoff summary.
"""
    review_bundle_record: dict[str, str] | None = None
    task_workspace = project_dir
    if (
        phase_slug == NUMERICAL_VALIDATION_PHASE
        and _manifest_schema_version(manifest) >= 7
    ):
        if phase_four_split and task_kind == "protocol":
            declaration = manifest.get("protocol_checkpoint")
            if not isinstance(declaration, Mapping):
                raise LaunchError(
                    "Phase 04 isolated protocol task has no workspace declaration"
                )
            workspace_directory = Path(
                str(declaration.get("protocol_root", ""))
            )
            workspace_label = "Phase 04 isolated protocol workspace"
        else:
            workspace_directory = _planned_output(manifest, round_n, role).parent
            workspace_label = "Phase 04 write-limited round workspace"
        task_workspace = _ensure_contained_directory(
            workspace_directory,
            project_dir,
            label=workspace_label,
        )
    if role == PAPER_REVIEWER_ROLE:
        task_workspace, brief_path, brief_hash, review_bundle_record = (
            _prepare_review_bundle(
                project_dir,
                manifest,
                run,
                round_n,
                reviewer_substage=reviewer_substage,
                proof_audit_stage=proof_audit_stage,
                review_snapshot=review_snapshot,
                soul_text=soul_text,
                soul_digest=soul_digest,
                protocol_text=reviewer_playbook,
                protocol_digest=reviewer_playbook_digest,
                review_directive=(
                    directive
                    if proof_audit_stage or reviewer_substage == "contextual"
                    else ""
                ),
            )
        )
        body = (
            "Read `task.md` and `bundle.json` in the assigned workspace. Verify the "
            f"task SHA-256 is {brief_hash}, follow only that sealed context, and write "
            "the report to `output/report.md`. Do not start or approve any phase."
        )
    else:
        brief_path = _task_brief_path(
            project_dir, phase_slug, run_id, round_n, role, task_kind
        )
        _write_text_atomic(brief_path, task_brief)
        brief_hash = _sha256_file(
            brief_path,
            max_bytes=MAX_TASK_BRIEF_BYTES,
            label="task brief",
            allow_empty=False,
        )
        body = (
            f"Read the complete Research Hub task brief from {brief_path}. Verify its "
            f"SHA-256 is {brief_hash}, confirm it names run {run_id}, round {round_n}, "
            f"role {role}, and follow it exactly. Do not start or approve any phase."
        )
    short_id = run_id.split("-", 1)[0]
    phase_name = str(manifest["phase"].get("name", phase_slug))
    kind_label = f" {task_kind}" if task_kind != "standard" else ""
    title = f"{phase_name} [{short_id}] R{round_n:02d} {role}{kind_label}"
    profile = str(manifest["profiles"][role])
    idempotency_key = f"research-hub:{run_id}:{round_n}:{role}"
    if task_kind != "standard":
        idempotency_key += f":{task_kind}"
    preloaded_skills = _verified_preloaded_skill_names(manifest, role)
    command = [
        str(manifest["hermes_executable"]),
        "kanban",
        "--board",
        str(manifest["board_slug"]),
        "create",
        title,
        "--assignee",
        profile,
        "--workspace",
        f"dir:{task_workspace}",
        "--body",
        body,
        "--idempotency-key",
        idempotency_key,
        "--max-runtime",
        f"{int(manifest['timeout_minutes'])}m",
        "--max-retries",
        "1",
    ]
    for skill_name in preloaded_skills:
        command.extend(("--skill", skill_name))
    command.append("--json")
    _guard_command_length(command)
    created = _run_command(
        command,
        timeout=30,
        environment=_hermes_environment(_manifest_hermes_root(manifest)),
    )
    if created.returncode != 0:
        detail = (created.stderr or created.stdout).strip()
        raise LaunchError(f"Hermes task creation failed for {role}: {detail}")
    try:
        payload = json.loads(created.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise LaunchError("Hermes task creation returned invalid JSON") from exc
    task_id = _task_id_from_json(payload)
    if not task_id:
        raise LaunchError("Hermes task creation did not return a task ID")
    try:
        project_state.record_task(
            project_dir,
            phase_slug,
            run_id,
            round_n,
            role=role,
            task_id=task_id,
            title=title,
            task_kind=task_kind,
            brief_path=brief_path,
            brief_sha256=brief_hash,
            review_bundle=review_bundle_record,
            workspace_path=task_workspace,
        )
    except Exception as exc:
        # A concurrent identical dispatch may have recorded the idempotent task.
        # Otherwise, do not leave a just-created worker outside the run record.
        try:
            current = project_state.get_run(project_dir, phase_slug, run_id)
            current_tasks = current.get("rounds", [])[round_n - 1].get("tasks", [])
        except Exception:
            current_tasks = []
        if any(
            item.get("task_id") == task_id
            and item.get("role") == role
            and str(item.get("task_kind", "standard")) == task_kind
            for item in current_tasks
        ):
            return task_id
        warning = _archive_external_task(manifest, task_id)
        if warning:
            raise LaunchError(
                f"Task {task_id} could not be recorded and cleanup is unconfirmed: {warning}"
            ) from exc
        raise
    return task_id


def _show_task(manifest: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    shown = _run_command(
        [
            str(manifest["hermes_executable"]),
            "kanban",
            "--board",
            str(manifest["board_slug"]),
            "show",
            task_id,
            "--json",
        ],
        environment=_hermes_environment(_manifest_hermes_root(manifest)),
    )
    if shown.returncode != 0:
        detail = (shown.stderr or shown.stdout).strip()
        raise LaunchError(f"Could not verify Hermes task {task_id}: {detail}")
    try:
        return _task_payload(json.loads(shown.stdout or "{}"))
    except json.JSONDecodeError as exc:
        raise LaunchError(f"Hermes returned invalid JSON for task {task_id}") from exc


def _archive_external_task(
    manifest: Mapping[str, Any], task_id: str
) -> str | None:
    """Stop and archive one exact Hermes task, returning an uncertainty warning."""

    status = ""
    try:
        status = str(_show_task(manifest, task_id).get("status", ""))
    except Exception:
        # Still attempt the exact archive. Its return code is the cleanup proof.
        pass
    if status in {"done", "archived"}:
        return None
    if status not in {"blocked", ""}:
        try:
            _run_command(
                [
                    str(manifest["hermes_executable"]),
                    "kanban",
                    "--board",
                    str(manifest["board_slug"]),
                    "block",
                    task_id,
                    "Research Hub stopped this user-controlled run.",
                ],
                environment=_hermes_environment(_manifest_hermes_root(manifest)),
            )
        except Exception:
            pass
    try:
        archived = _run_command(
            [
                str(manifest["hermes_executable"]),
                "kanban",
                "--board",
                str(manifest["board_slug"]),
                "archive",
                task_id,
            ],
            environment=_hermes_environment(_manifest_hermes_root(manifest)),
        )
    except Exception as exc:
        return f"Could not archive Hermes task {task_id}: {exc}"
    if archived.returncode != 0:
        detail = (archived.stderr or archived.stdout).strip()
        return f"Could not archive Hermes task {task_id}: {detail or 'unknown error'}"
    return None


def _complete_round_checked(
    project_dir: str | Path,
    phase_slug: str,
    run_id: str | int,
    round_n: int,
    outputs: Sequence[str | Path],
) -> None:
    project_dir = Path(project_dir).resolve()
    run = project_state.get_run(project_dir, phase_slug, run_id)
    stable_id = str(run["run_id"])
    manifest = _read_manifest(project_dir, phase_slug, stable_id)
    _verify_frozen_inputs(project_dir, phase_slug, stable_id, manifest)
    planned_roles = _planned_roles(manifest, round_n)
    if round_n < 1 or round_n > len(run.get("rounds", [])):
        raise LaunchError(f"Run has no recorded round {round_n}")
    round_state = run["rounds"][round_n - 1]
    _verify_completed_round_artifacts(project_dir, run, before_round=round_n)
    _verify_task_briefs(project_dir, phase_slug, run, round_n=round_n)
    tasks = list(round_state.get("tasks", []))
    phase_four_split = (
        phase_slug == NUMERICAL_VALIDATION_PHASE
        and _manifest_schema_version(manifest) >= 6
        and round_n == 1
    )
    if phase_four_split:
        recorded_tasks = sorted(
            (
                str(task.get("role", "")),
                str(task.get("task_kind", "standard")),
            )
            for task in tasks
        )
        expected_tasks = [
            ("data_scientist", "protocol"),
            ("data_scientist", "result"),
        ]
        if recorded_tasks != expected_tasks:
            raise LaunchError(
                "Phase 04 round 1 requires one completed protocol task followed "
                "by one completed result task"
            )
        project_state.require_protocol_checkpoint(
            project_dir, phase_slug, stable_id
        )
    else:
        recorded_roles = [str(task.get("role")) for task in tasks]
        if sorted(recorded_roles) != sorted(planned_roles):
            raise LaunchError(
                "Round cannot complete until exactly one task is recorded for each planned role"
            )
    unfinished = []
    for task in tasks:
        payload = _show_task(manifest, str(task["task_id"]))
        if payload.get("status") != "done":
            unfinished.append(f"{task['task_id']} ({payload.get('status', 'unknown')})")
    if unfinished:
        raise LaunchError("Hermes tasks are not done: " + ", ".join(unfinished))
    for task in tasks:
        if (
            str(task.get("role")) == PAPER_REVIEWER_ROLE
            and task.get("review_bundle") is not None
        ):
            _import_review_bundle_output(project_dir, manifest, task, round_n)
    expected = {
        _planned_output(manifest, round_n, role).resolve() for role in planned_roles
    }
    supplied = {Path(output).resolve() for output in outputs}
    if supplied != expected:
        raise LaunchError("Round outputs do not match the frozen role output plan")
    project_state.complete_round(
        project_dir, phase_slug, run_id, round_n, list(outputs)
    )


def _source_baseline_lead_block(source_baseline: Any) -> str:
    """Describe how the lead must preserve a selected run's complete baseline."""

    if not isinstance(source_baseline, Mapping):
        raise LaunchError("Special run has no frozen source baseline")
    summary = source_baseline.get("summary")
    decision = source_baseline.get("decision_record")
    if not isinstance(summary, Mapping) or not isinstance(decision, Mapping):
        raise LaunchError("Special run source baseline is incomplete")
    baseline_status = _source_baseline_status(source_baseline)
    status_explanations = {
        "accepted": (
            "The source run was approved when selected. Treat it as the accepted "
            "source baseline for this derivative assessment."
        ),
        "proposed": (
            "The source run was submitted but not approved when selected. Treat its "
            "baseline as a proposal, not as an accepted result."
        ),
        "historical": (
            "The source run had been superseded when selected. Treat its baseline as "
            "historical, not as the current accepted result."
        ),
    }
    explanation = status_explanations.get(baseline_status)
    if explanation is None:
        raise LaunchError("Special run source-baseline status is invalid")
    return f"""## Frozen source baseline for the derivative run

- Source phase: `{source_baseline.get('phase_slug', '')}`
- Source run: `{source_baseline.get('run_id', '')}`
- Status at selection: `{source_baseline.get('status_at_selection', '')}`
- Source-baseline status: `{baseline_status}`
- Frozen final summary: `{summary.get('path', '')}`; SHA-256 `{summary.get('sha256', '')}`
- Frozen structured decision record: `{decision.get('path', '')}`; SHA-256 `{decision.get('sha256', '')}`

{explanation} Read both frozen files before final synthesis. The new
`proposed_baseline` must carry forward the source baseline in full, including
every unaffected material statement and its stable statement ID, and then state
only the changes supported by this run. Do not replace the full baseline with an
audit or review fragment. If the source-baseline status is `proposed` or
`historical`, state explicitly that approval of this run would adopt the
carried-forward source baseline together with the new findings; do not describe
that source as already accepted.
"""


def _method_selection_prompt_block(selection: Any) -> str:
    """State the exact method identity without implying an unmade approval."""

    if not isinstance(selection, Mapping):
        return ""
    source = str(selection.get("source", ""))
    if source == "approved_phase_02_selection":
        decision = selection.get("decision_record")
        provenance = (
            "Approved Phase 02 selection from run "
            f"`{selection.get('source_run_id', '')}`. Frozen decision record: "
            f"`{decision.get('path', '')}`; SHA-256 `{decision.get('sha256', '')}`."
            if isinstance(decision, Mapping)
            else "Approved Phase 02 selection."
        )
    elif source == "run_specific_user_selection":
        provenance = (
            "The user supplied this identity for this run. It does not replace or "
            "approve a Phase 02 baseline."
        )
    else:
        raise LaunchError("The frozen method selection has an invalid source")
    return f"""## Exact method identity frozen for this run

- Stable method ID: `{selection.get('stable_id', '')}`
- Method version: `{selection.get('version', '')}`
- Provenance: {provenance}

Use this exact method identity throughout the run. Do not substitute a nearby
variant, infer a different version from prose, or silently broaden its scope.
"""


def _build_lead_prompt(
    project_dir: Path,
    phase: Mapping[str, Any],
    profiles: Mapping[str, str],
    board_slug: str,
    run_id: str,
    run_number: int,
    rounds: int,
    user_feedback: str,
    prerequisite_snapshot: Mapping[str, Any],
    snapshots: Mapping[str, Any],
    summary_path: Path,
    decision_path: Path | None = None,
    paper_review: Mapping[str, Any] | None = None,
    proof_audit_source: Mapping[str, Any] | None = None,
    method_selection: Mapping[str, Any] | None = None,
) -> str:
    phase_slug = str(phase["slug"])
    phase_name = str(phase.get("name", phase_slug))
    try:
        lead_soul_entry = snapshots["souls"]["research_lead"]
    except (KeyError, TypeError) as exc:
        raise LaunchError("The run has no frozen research_lead soul") from exc
    lead_soul_text, lead_soul_digest, lead_soul_path = _frozen_snapshot_text(
        lead_soul_entry, "souls.research_lead"
    )
    missing = prerequisite_snapshot.get("blockers", [])
    if missing:
        prerequisite_text = (
            "The user explicitly overrode missing or stale prerequisite context for: "
            + ", ".join(str(item) for item in missing)
            + ". State this limitation in the summary and do not invent the missing evidence."
        )
    else:
        prerequisite_text = "All configured prerequisite results were approved and current at launch."
    method_selection_text = _method_selection_prompt_block(method_selection)

    summary_snapshots = snapshots.get("summaries", [])
    if summary_snapshots:
        context_text = "\n".join(
            f"- `{entry['path']}` from {entry['phase']} run `{entry['run_id']}` "
            f"({entry.get('kind', 'context')}; "
            f"{'trusted current input' if entry.get('trusted', True) else 'comparison-only historical baseline'}; "
            f"SHA-256 `{entry['sha256']}`)"
            for entry in summary_snapshots
        )
    else:
        context_text = "- No approved, current ancestor summary is available for this run."

    decision_path = decision_path or summary_path.with_suffix(".decision.json")
    phase_code = phase_slug.split("-", 1)[0]
    example_statement_id = (
        f"S-P{phase_code}-R{run_number:03d}-summary-research_lead-001"
    )
    complete = _tracker_command(
        "complete",
        project_dir,
        phase_slug,
        run_id,
        "--summary",
        str(summary_path),
        "--decision-record",
        str(decision_path),
    )
    decision_record_example = json.dumps(
        {
            "schema_version": project_state.DECISION_RECORD_SCHEMA_VERSION,
            "scientific_outcome": "Complete",
            "decision_requested": "State the specific choice the user is being asked to make.",
            "selected_scientific_object": (
                {
                    "kind": "method",
                    "stable_id": "State the exact stable method ID.",
                    "version": "State the exact method version.",
                }
                if phase_slug == project_state.METHOD_DEVELOPMENT_PHASE
                else None
            ),
            "recommended_user_action": "approve",
            "recommendation": "State the team's recommendation and its scientific scope.",
            "main_evidence": [
                "Give a result and identify its exact supporting artifact, table, figure, theorem, or citation."
            ],
            "principal_risk": "State the most consequential unresolved risk or limitation.",
            "smallest_decision_changer": "State the smallest additional result that would change the recommendation.",
            "option_consequences": {
                "approve": "State what becomes the accepted phase baseline.",
                "approve_with_limitations": "State what qualified baseline is accepted and which limitation remains explicit downstream.",
                "request_revision": "State the smallest revision needed before another decision.",
                "rerun": "State what a new run would test differently.",
                "defer": "State what remains unchanged while the result stays unapproved.",
            },
            "rerun_question": "State one exact scientific question for a possible rerun.",
            "rerun_comparison": "State what changed from the approved run, or say this is the initial run.",
            "proposed_baseline": "State the complete scientific conclusion and qualifications that approval would accept.",
            "scientific_record_changes": [
                {
                    "statement_id": example_statement_id,
                    "operation": "add",
                    "changed_fields": [
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
                    ],
                    "proposed_values": {
                        "statement_type": "Empirical statement",
                        "wording": "State one material scientific statement exactly.",
                        "scope": "State the population, regime, or conditions covered.",
                        "formulation_state": "Proposed",
                        "assessment_status": "Untested",
                        "evidential_basis": ["Name the supporting theorem, calculation, numerical result, or source."],
                        "source_provenance": ["Identify the exact project path or external source."],
                        "assumptions": ["State the assumptions needed for this statement."],
                        "uncertainty": ["State the material uncertainty or limitation."],
                        "logical_status": "Not applicable",
                        "mathematical_result_type": "Not applicable",
                    },
                    "evidential_basis": ["Identify the exact supporting evidence."],
                    "reason": "Explain why this addition or change is scientifically warranted.",
                    "parent_statement_id": None,
                    "change_origin": {
                        "phase": phase_slug,
                        "run": run_id,
                        "round_or_stage": "summary",
                        "role": "research_lead",
                    },
                }
            ],
        },
        indent=2,
        ensure_ascii=False,
    )
    task_plan = _task_instructions(
        project_dir, phase, run_id, run_number, rounds,
        board_slug=board_slug,
    )
    manuscript_paths_text = ""
    if phase_slug == PAPER_WRITING_PHASE:
        paths = _paper_manuscript_paths(
            project_dir
            / str(phase.get("folder", ""))
            / "run"
            / f"{run_number:02d}"
        )
        if paper_review and paper_review.get("kind") == "review_only":
            source_baseline_text = _source_baseline_lead_block(
                paper_review.get("source_baseline")
            )
            manuscript_paths_text = f"""## Review-only manuscript identity

- User-selected source: `{paper_review['source_path']}`
- Source SHA-256 at selection: `{paper_review['source_sha256']}`
- Preserved review copy: `{paper_review['review_path']}`
- Preserved copy SHA-256: `{paper_review['review_sha256']}`

This run must not draft or revise the manuscript. Dispatch only the two reviewer
substages in the frozen plan. Both reviewer tasks assess the preserved copy.
Never modify either the selected source or the preserved review copy.

{source_baseline_text}

Keep the independent first-reading substage blind to the source baseline. Do not
quote, summarize, identify, or pass either baseline file in its directive. The
contextual second reviewer receives the frozen baseline automatically after the
first-reading report has been preserved.
"""
        else:
            manuscript_paths_text = f"""## Required manuscript version paths

- Review manuscript, sealed into the reviewer task: `{paths['review']}`
- Separate post-review manuscript: `{paths['post_review']}`
- Exact review-to-post-review diff: `{paths['diff']}`

Never overwrite the review manuscript after dispatch. Any safe integration edit
must use the post-review path. If no edit is warranted, copy the review
manuscript byte for byte to the post-review path and write an empty diff; the
identical copy retains the reviewed status. A changed post-review manuscript
must remain labeled not independently reviewed until the user launches another
Phase 06 run that reviews it.
"""
    proof_audit_text = ""
    if phase_slug == THEORETICAL_ANALYSIS_PHASE and phase.get("proof_audit"):
        if phase.get("audit_only"):
            if not isinstance(proof_audit_source, Mapping):
                raise LaunchError("The audit-only lead prompt has no source identity")
            source = proof_audit_source
            target = source["target"]
            evidence_lines = "\n".join(
                "- `{path}`; SHA-256 `{sha256}`; purpose: {purpose}".format(
                    path=item.get("path", ""),
                    sha256=item.get("sha256", ""),
                    purpose=item.get("purpose", "supporting evidence"),
                )
                for item in source.get("evidence", [])
                if isinstance(item, Mapping)
            ) or "- No additional evidence was frozen for this audit."
            source_baseline_text = _source_baseline_lead_block(
                source.get("source_baseline")
            )
            proof_audit_text = f"""## User-selected audit-only run

The object of review is the final theorist artifact from Phase 03 run
`{source['run_id']}`, source stage {target['source_round']}.

- Original project path: `{target.get('source_path', '')}`
- Preserved audit copy: `{target.get('path', '')}`
- Target SHA-256: `{target.get('sha256', '')}`

The admissible supporting evidence is:

{evidence_lines}

{source_baseline_text}

Read the preserved target and this evidence inventory before writing the round
directive. The directive must identify the exact theorem, lemma, equation,
claim, proof step, or other statement to be checked, using the artifact's own
identifiers or exact wording where possible. It must state the relevant
assumptions, dependencies, proof locations, target hash, and admissible evidence
paths. Ask the reviewer to distinguish a false statement, a proof gap, an
unstated assumption, an ambiguous definition, and a presentation defect, and to
state what follows mathematically and scientifically from each finding.

Dispatch only the one paper-reviewer stage in the frozen plan. Do not ask a
theorist to repeat or revise the analysis. Do not give the reviewer a prior
research-lead assessment, recommendation, source summary, or structured decision
record. After the reviewer reports, apply the audit findings to the complete
frozen source baseline. Preserve every unaffected statement and stable statement
ID, and make only audit-supported changes to status, scope, uncertainty, or
withdrawal. Then submit the run and stop for the user's decision.
"""
        else:
            proof_audit_text = """## User-selected independent proof audit

The user added the optional proof-audit stage to this run. Complete the normal
three theoretical-analysis stages first. The run helper then seals the exact
final theorist artifact and the available evidence inventory into a separate
paper-reviewer task. Do not rewrite the target during the audit and do not add
another theorist stage.
"""

    return f"""# Research lead assignment: {phase_name}

The user explicitly launched this phase run. You may execute only this run.
Never approve it, start another phase, or make a downstream decision for the
user. Your result must make the user's next decision easy to understand.

## Run envelope

- Project directory: `{project_dir}`
- Frozen project brief: `{snapshots['setting']['path']}`
- Phase: `{phase_slug}`
- Immutable run ID: `{run_id}`
- Display run number: {run_number}
- Pattern: `{phase.get('pattern', 'parallel')}`
- Rounds or stages authorized by the user: {rounds}
- Kanban board: `{board_slug}`
- User direction: {user_feedback if user_feedback else '(none)'}

{prerequisite_text}

{method_selection_text}

{manuscript_paths_text}

{proof_audit_text}

## Frozen research lead identity and reasoning standards

This embedded soul was copied from `{lead_soul_path}` and sealed into this lead
prompt with SHA-256 `{lead_soul_digest}`. Read it before the phase playbooks.

BEGIN FROZEN RESEARCH LEAD SOUL

{lead_soul_text.rstrip()}

END FROZEN RESEARCH LEAD SOUL

## Read before dispatching

After reading the embedded soul, read these files completely:

- `{snapshots['playbooks']['_lead.md']['path']}`
- `{snapshots['playbooks']['_phase.md']['path']}`
- `{snapshots['team']['charter']['path']}`
- `{snapshots['team']['norms']['path']}`
- `{snapshots['setting']['path']}`

Use these frozen summary inputs according to their labels. A historical
baseline is for comparison only; do not treat it as current evidence:

{context_text}

Clearly distinguish inherited facts, historical baselines, new findings,
uncertainty, and recommendations.

## Execute this exact run plan

{task_plan}

The run helper creates unique idempotent tasks and records their exact IDs. Do
not create additional kanban tasks outside the helper.

## Submit evidence for the user's decision

After every authorized round or stage is recorded complete, first write a valid
UTF-8 JSON decision record to this exact immutable path:

`{decision_path}`

Use exactly this schema and replace every instructional value with a concise,
phase-specific scientific statement:

```json
{decision_record_example}
```

The scientific outcome describes completion of the requested scientific work.
It never approves or rejects the run. The recommended action must be one of
`approve`, `approve_with_limitations`, `request_revision`, `rerun`, or `defer`.
For Phase 02, `selected_scientific_object` must name exactly one method by stable
ID and version, and `decision_requested` must repeat both values. For every other
phase, set `selected_scientific_object` to `null`.
Use an empty `scientific_record_changes` list when no material statement would
change. For a status-only update, keep the statement ID and name only the fields
that change. A material wording or scope change uses a new project-unique ID and
names the preceding ID as `parent_statement_id`. Use `revise` only when wording
and scope stay unchanged. Use `withdraw` only for an existing ID and set its
proposed formulation state to `Withdrawn`. For a contributor result, record the
exact assigned role and `round N`, where N is its frozen round or stage number.
For research-lead synthesis, use role `research_lead` and stage `summary`, as in
the example. The `proposed_baseline` must be self-contained and must state
exactly what approval would accept, including its scope and qualifications.

Then write a nonempty, self-contained HTML summary to this exact immutable path:

`{summary_path}`

Keep it concise and readable. Include:

1. **User Decision Brief:** decision requested; most defensible conclusion and
   recommendation; main evidence; principal risk; smallest result that would
   change the recommendation; consequences of approve, approve with the stated
   limitations, request revision, rerun, or defer; and the exact rerun question.
2. **Comparison with the approved run:** what changed in the question, inputs, methods, evidence,
   conclusions, or limitations relative to the prior approved run. State that
   no approved comparison exists when applicable.
3. **Phase outcome:** Complete, Partial, or Failed, with attempted and completed
   work, usable evidence, missing work and its cause, scientific consequence,
   and next verification for Partial or Failed.
4. **Scientific record changes:** the same statement IDs, operations, changed
   fields, proposed values, evidence, reasons, lineage, and origins recorded in
   the JSON file, without adding or omitting a change.
5. **Proposed scientific baseline:** the complete set of material scientific
   statements, evidence, qualifications, and proposed changes if the run is
   approved. State explicitly that approval accepts this proposed baseline as
   a whole, while revision or rerun leaves the prior approved baseline unchanged.
6. **Phase evidence:** main findings, disagreements, negative results,
   uncertainty, limitations, and exact links or paths to supporting outputs.

The decision-facing facts in the HTML must agree exactly with the validated JSON
record. The HTML may explain them in more detail but must not change the outcome,
requested decision, recommendation, evidence, risks, option consequences,
comparison, proposed baseline, or scientific record changes.

Do not include scripts, forms, remote assets, or automatic navigation in the
summary. The web UI will display it in a sandbox.

Then submit it for user review with this exact command:

```text
{complete}
```

This command does not approve the run. Stop after it succeeds and wait for the
user's decision in the web UI.
"""


def prompt_path(project_dir: Path, phase_slug: str, run_id: str) -> Path:
    return project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.prompt.md"


def run_log_path(project_dir: Path, phase_slug: str, run_id: str) -> Path:
    return project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.log"


def _open_new_run_log(log_path: Path) -> Any:
    """Create a new regular run log without following or reusing a path."""

    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_APPEND
        | getattr(os, "O_BINARY", 0)
    )
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(log_path, flags, 0o600)
    except FileExistsError as exc:
        raise LaunchError(
            f"Run log destination already exists; refusing to reuse it: {log_path}"
        ) from exc
    except OSError as exc:
        raise LaunchError(f"Run log could not be created safely: {log_path}") from exc
    try:
        opened_metadata = os.fstat(descriptor)
        path_metadata = log_path.lstat()
        if (
            _metadata_is_link_or_reparse(path_metadata)
            or not stat.S_ISREG(opened_metadata.st_mode)
            or not os.path.samestat(opened_metadata, path_metadata)
        ):
            raise LaunchError(
                f"Run log must be one newly created regular file: {log_path}"
            )
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        handle = os.fdopen(
            descriptor,
            "a",
            encoding="utf-8",
            newline="\n",
            buffering=1,
        )
    except BaseException:
        os.close(descriptor)
        raise
    return handle


def _write_worker_output(payload: bytes, *, descriptor: int | None = None) -> None:
    """Forward bounded Hermes output to the worker's inherited run log."""

    inherited = _worker_log_descriptor()
    if descriptor is not None and inherited != descriptor:
        raise LaunchError("The inherited run-log descriptor changed during execution")
    binary = getattr(sys.stdout, "buffer", None)
    if binary is not None:
        binary.write(payload)
        binary.flush()
        return
    sys.stdout.write(payload.decode("utf-8", errors="replace"))
    sys.stdout.flush()


def _worker_log_descriptor() -> int:
    """Return the exact inherited descriptor used for persistent worker output."""

    try:
        descriptor = int(sys.stdout.fileno())
    except (AttributeError, OSError, TypeError, ValueError) as exc:
        raise LaunchError("The worker has no usable inherited run-log descriptor") from exc
    if descriptor < 0:
        raise LaunchError("The worker has no usable inherited run-log descriptor")
    return descriptor


def _run_log_descriptor_metadata(descriptor: int) -> os.stat_result:
    """Inspect a bound run-log descriptor without reopening its pathname."""

    try:
        metadata = os.fstat(descriptor)
    except (OSError, ValueError) as exc:
        raise LaunchError("The inherited run-log descriptor is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise LaunchError("The inherited run-log descriptor is not a regular file")
    return metadata


def _verified_run_log_descriptor(
    log_path: Path,
    descriptor: int,
    *,
    expected: os.stat_result | None = None,
) -> os.stat_result:
    """Require the named log path to identify the inherited regular file."""

    descriptor_metadata = _run_log_descriptor_metadata(descriptor)
    if expected is not None and not os.path.samestat(descriptor_metadata, expected):
        raise LaunchError("The inherited run-log descriptor changed during execution")
    try:
        path_metadata = log_path.lstat()
    except (OSError, ValueError) as exc:
        raise LaunchError(
            f"Run log no longer identifies the inherited worker output: {log_path}"
        ) from exc
    if (
        not stat.S_ISREG(descriptor_metadata.st_mode)
        or _metadata_is_link_or_reparse(path_metadata)
        or not os.path.samestat(descriptor_metadata, path_metadata)
    ):
        raise LaunchError(
            f"Run log no longer identifies the inherited worker output: {log_path}"
        )
    return descriptor_metadata


def _flush_worker_log_streams() -> None:
    """Flush Python's wrappers before measuring or truncating their shared file."""

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except (AttributeError, OSError, ValueError) as exc:
            raise LaunchError("The inherited run-log stream could not be flushed") from exc


def _run_logged_command(
    arguments: Sequence[str],
    *,
    timeout: int,
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    environment: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run Hermes while keeping the persistent run log within its byte cap."""

    log_path = run_log_path(project_dir, phase_slug, run_id)
    descriptor = _worker_log_descriptor()
    _flush_worker_log_streams()
    bound_metadata = _verified_run_log_descriptor(log_path, descriptor)
    try:
        remaining = MAX_RUN_LOG_BYTES - bound_metadata.st_size
        if remaining <= len(RUN_LOG_LIMIT_MARKER):
            marker = RUN_LOG_LIMIT_MARKER[: max(0, remaining)]
            if marker:
                _write_worker_output(marker, descriptor=descriptor)
            raise _ProcessOutputLimitExceeded(
                f"Run log reached the {MAX_RUN_LOG_BYTES:,}-byte safety limit"
            )
        output_budget = remaining - len(RUN_LOG_LIMIT_MARKER)
        try:
            return _run_process_with_bounded_output(
                arguments,
                timeout=timeout,
                max_output_bytes=output_budget,
                merge_stderr=True,
                output_writer=lambda payload: _write_worker_output(
                    payload, descriptor=descriptor
                ),
                environment=environment,
            )
        except _ProcessOutputLimitExceeded as exc:
            _write_worker_output(RUN_LOG_LIMIT_MARKER, descriptor=descriptor)
            raise _ProcessOutputLimitExceeded(
                f"Hermes output exceeded the {MAX_RUN_LOG_BYTES:,}-byte run-log safety limit"
            ) from exc
    finally:
        _flush_worker_log_streams()
        _verified_run_log_descriptor(
            log_path, descriptor, expected=bound_metadata
        )


def _truncate_run_log(
    log_path: Path,
    *,
    descriptor: int | None = None,
    expected: os.stat_result | None = None,
) -> None:
    """Enforce the persistent cap after all worker cleanup messages are written."""

    inherited = _worker_log_descriptor() if descriptor is None else int(descriptor)
    _flush_worker_log_streams()
    opened_metadata = _run_log_descriptor_metadata(inherited)
    if expected is not None and not os.path.samestat(opened_metadata, expected):
        raise LaunchError("The inherited run-log descriptor changed during execution")
    try:
        if opened_metadata.st_size > MAX_RUN_LOG_BYTES:
            marker = RUN_LOG_LIMIT_MARKER[:MAX_RUN_LOG_BYTES]
            retained = MAX_RUN_LOG_BYTES - len(marker)
            os.ftruncate(inherited, retained)
            os.lseek(inherited, retained, os.SEEK_SET)
            os.write(inherited, marker)
            os.fsync(inherited)
    except OSError as exc:
        raise LaunchError(f"Run log could not be capped safely: {log_path}") from exc
    _verified_run_log_descriptor(log_path, inherited, expected=opened_metadata)


def launch_run(
    project_dir: str | Path,
    project_id: int,
    phase_slug: str,
    user_feedback: str = "",
    rounds_requested: int | None = None,
    *,
    prerequisite_override_reason: str = "",
    prerequisite_report_version: str = "",
    replace_awaiting_review_note: str | None = None,
    replace_awaiting_review_run_id: str | None = None,
    review_target: str | Path | None = None,
    review_target_sha256: str = "",
    theory_plan: str = "",
    proof_audit_source_run_id: str = "",
    proof_audit: bool = False,
    run_specific_method_id: str = "",
    run_specific_method_version: str = "",
    expected_phase_plan_version: str = "",
    expected_workspace_path: str = "",
    expected_project_directory_name: str = "",
    expected_project_path: str = "",
) -> dict[str, Any]:
    """Launch one run while workspace replacement and project creation are excluded."""

    import hub

    with hub.operation_lock():
        expected_identity = (
            expected_workspace_path,
            expected_project_directory_name,
            expected_project_path,
        )
        if any(expected_identity) and not all(expected_identity):
            raise LaunchError("The expected workspace project identity is incomplete")
        requested_project = Path(project_dir).resolve(strict=False)
        current_workspace = hub.get_workspace_dir().resolve(strict=True)
        current_project_record = hub.get_project(project_id)
        current_project = hub.get_project_dir(project_id)
        if current_project_record is None or current_project is None:
            raise LaunchError(
                "The project is no longer present in the current workspace. "
                "Reload the page before launching a run."
            )
        try:
            current_project = current_project.resolve(strict=True)
        except OSError as exc:
            raise LaunchError(
                "The project directory is unavailable. Reload the page before "
                "launching a run."
            ) from exc
        if current_project != requested_project:
            raise LaunchError(
                "The workspace or project changed before launch. Reload the page "
                "and confirm the requested phase again."
            )
        if all(expected_identity) and (
            str(current_workspace) != expected_workspace_path
            or str(current_project_record["directory_name"] or "")
            != expected_project_directory_name
            or str(current_project) != expected_project_path
        ):
            raise LaunchError(
                "The workspace or project changed after this page was shown. "
                "Reload the page and review the launch again."
            )
        return _launch_run_locked(
            current_project,
            project_id,
            phase_slug,
            user_feedback,
            rounds_requested,
            prerequisite_override_reason=prerequisite_override_reason,
            prerequisite_report_version=prerequisite_report_version,
            replace_awaiting_review_note=replace_awaiting_review_note,
            replace_awaiting_review_run_id=replace_awaiting_review_run_id,
            review_target=review_target,
            review_target_sha256=review_target_sha256,
            theory_plan=theory_plan,
            proof_audit_source_run_id=proof_audit_source_run_id,
            proof_audit=proof_audit,
            run_specific_method_id=run_specific_method_id,
            run_specific_method_version=run_specific_method_version,
            expected_phase_plan_version=expected_phase_plan_version,
        )


def _launch_run_locked(
    project_dir: str | Path,
    project_id: int,
    phase_slug: str,
    user_feedback: str = "",
    rounds_requested: int | None = None,
    *,
    prerequisite_override_reason: str = "",
    prerequisite_report_version: str = "",
    replace_awaiting_review_note: str | None = None,
    replace_awaiting_review_run_id: str | None = None,
    review_target: str | Path | None = None,
    review_target_sha256: str = "",
    theory_plan: str = "",
    proof_audit_source_run_id: str = "",
    proof_audit: bool = False,
    run_specific_method_id: str = "",
    run_specific_method_version: str = "",
    expected_phase_plan_version: str = "",
) -> dict[str, Any]:
    """Prepare and launch exactly one user-authorized phase run."""

    project_dir = Path(project_dir).resolve()
    config = _load_hub_config()
    configured_phase = _phase_config(config, phase_slug)
    phase = dict(configured_phase)
    review_source: tuple[Path, str, dict[str, Any]] | None = None
    theory_audit_source: dict[str, Any] | None = None
    selected_theory_plan = str(theory_plan).strip()
    if review_target is not None:
        if phase_slug != PAPER_WRITING_PHASE:
            raise LaunchError("An exact manuscript review target is only valid in Phase 06")
        review_source = _resolve_paper_review_source(
            project_dir, review_target, review_target_sha256
        )
        phase = paper_review_only_phase(phase)
    elif review_target_sha256:
        raise LaunchError("A review target hash was supplied without a review target")
    if phase_slug == THEORETICAL_ANALYSIS_PHASE:
        if not selected_theory_plan:
            selected_theory_plan = (
                THEORY_PLAN_STANDARD_WITH_AUDIT
                if proof_audit
                else THEORY_PLAN_STANDARD
            )
        if proof_audit and selected_theory_plan != THEORY_PLAN_STANDARD_WITH_AUDIT:
            raise LaunchError("Conflicting Phase 03 proof-audit plan options")
        if selected_theory_plan not in THEORY_RUN_PLANS:
            raise LaunchError(f"Unknown Phase 03 run plan: {selected_theory_plan!r}")
        source_id = str(proof_audit_source_run_id).strip()
        if selected_theory_plan == THEORY_PLAN_AUDIT_ONLY:
            if not source_id:
                raise LaunchError(
                    "An audit-only Phase 03 run requires a selected source run"
                )
            theory_audit_source = _resolve_theory_audit_source(
                project_dir, source_id
            )
        elif source_id:
            raise LaunchError(
                "A proof-audit source run is only valid for the audit-only plan"
            )
        phase = _phase_for_theory_plan(phase, selected_theory_plan)
    elif proof_audit or selected_theory_plan or proof_audit_source_run_id:
        raise LaunchError("Phase 03 run-plan options are only valid in Phase 03")
    try:
        hermes_root = profile_skills.resolve_hermes_root()
    except (profile_skills.ProfileSkillsError, OSError, ValueError) as exc:
        raise LaunchError("Hermes profile locations could not be resolved safely") from exc
    plan_phase = phase if review_source is not None else configured_phase
    initial_recommended_skills = _recommended_skills_snapshot(
        config,
        phase_slug,
        effective_phase=plan_phase,
        hermes_root=hermes_root,
    )
    current_phase_plan_version = launch_plan_version(
        config,
        phase_slug,
        effective_phase=plan_phase,
        hermes_root=hermes_root,
        recommended_skills_snapshot=initial_recommended_skills,
    )
    reviewed_phase_plan_version = str(expected_phase_plan_version).strip().lower()
    if reviewed_phase_plan_version and not hmac.compare_digest(
        reviewed_phase_plan_version, current_phase_plan_version
    ):
        raise LaunchError(
            "The phase plan or scientific instructions changed since this page was "
            "shown. Reload the phase and review the run again."
        )
    profiles = _role_profiles(config)
    rounds = _round_count(phase, rounds_requested)
    hermes, hermes_root = _preflight(
        project_dir,
        phase,
        profiles,
        config,
        hermes_root=hermes_root,
    )
    dependencies = _dependencies(config)

    state = project_state.load(project_dir)
    if not state.get("project"):
        project_state.init(
            project_dir,
            f"project-{project_id:03d}",
            project_dir.name,
            project_dir.name,
            _phase_slugs(config),
            dependencies,
        )
        state = project_state.load(project_dir)

    board_slug = _workspace_board_slug(project_dir, project_id)
    display_name = str(state.get("project", {}).get("name") or board_slug)
    _ensure_board(
        hermes,
        board_slug,
        display_name,
        hermes_root=hermes_root,
    )

    report = project_state.prerequisite_report(project_dir, phase_slug, dependencies)
    current_prerequisite_version = project_state.decision_report_version(
        "prerequisite", report
    )
    submitted_prerequisite_version = prerequisite_report_version.strip().lower()
    if submitted_prerequisite_version and not hmac.compare_digest(
        submitted_prerequisite_version, current_prerequisite_version
    ):
        raise LaunchError(
            "The prerequisite scientific inputs changed since this page was shown. "
            "Reload the phase and review the run again."
        )
    if reviewed_phase_plan_version and not submitted_prerequisite_version:
        raise LaunchError(
            "The launch has no reviewed prerequisite version. Reload the phase and "
            "review the run again."
        )
    override = None
    if not report.get("satisfied"):
        reason = prerequisite_override_reason.strip()
        if not reason:
            blockers = ", ".join(report.get("blockers", []))
            raise LaunchError(
                f"This run is missing approved, current prerequisite results from {blockers}. "
                "Review the warning and explicitly confirm the override in the web UI."
            )
        if not submitted_prerequisite_version:
            raise LaunchError(
                "The prerequisite warning has no submitted version. Reload the phase "
                "and confirm the override again."
            )
        override = {"actor": "user", "reason": reason}

    prior_runs = project_state.get_runs(project_dir, phase_slug)
    if review_source:
        mode = "user-directed review-only rerun"
    elif selected_theory_plan == THEORY_PLAN_AUDIT_ONLY:
        mode = "user-directed audit-only rerun"
    elif selected_theory_plan == THEORY_PLAN_STANDARD_WITH_AUDIT:
        mode = (
            "user-directed rerun with independent proof audit"
            if prior_runs
            else "user-directed initial run with independent proof audit"
        )
    else:
        mode = "user-directed rerun" if prior_runs else "user-directed initial run"
    run_id: str | None = None
    process: subprocess.Popen[str] | None = None
    manifest_file: Path | None = None
    try:
        run_id = project_state.reserve_run(
            project_dir,
            phase_slug,
            mode,
            rounds,
            user_feedback,
            dependencies=dependencies,
            override_metadata=override,
            replace_awaiting_review_note=replace_awaiting_review_note,
            replace_awaiting_review_run_id=replace_awaiting_review_run_id,
            expected_prerequisite_report_version=(
                submitted_prerequisite_version or None
            ),
        )
        index = _run_index(project_dir, phase_slug, run_id)
        run_number = index + 1
        output_root = (
            project_dir
            / str(phase.get("folder", ""))
            / "run"
            / f"{run_number:02d}"
        )
        _ensure_contained_directory(
            output_root, project_dir, label="run output directory"
        )
        paper_review: dict[str, Any] = {
            "kind": "full",
            "review_path": str(_paper_manuscript_paths(output_root)["review"]),
        }
        if review_source:
            source_path, source_digest, _source_baseline = review_source
            review_path = _paper_manuscript_paths(output_root)["review"]
            _copy_paper_review_source(
                project_dir, source_path, review_path, source_digest
            )
            paper_review = {
                "schema_version": 2,
                "kind": "review_only",
                "source_path": str(source_path),
                "source_sha256": source_digest,
                "review_path": str(review_path),
                "review_sha256": source_digest,
            }
        paper_paths = _paper_manuscript_paths(output_root)
        submission_outputs = (
            {
                "post_review_manuscript": {
                    "path": str(paper_paths["post_review"]),
                    "allow_empty": False,
                },
                "review_diff": {
                    "path": str(paper_paths["diff"]),
                    "allow_empty": True,
                },
            }
            if phase_slug == PAPER_WRITING_PHASE and not review_source
            else {}
        )
        context_inputs = _trusted_context(project_dir, phase_slug, config)
        project_state.set_run_context(
            project_dir, phase_slug, run_id, context_inputs
        )
        snapshots = _snapshot_run_inputs(
            project_dir, phase, run_id, context_inputs
        )
        method_selection = _method_selection_for_run(
            phase,
            snapshots,
            run_specific_method_id,
            run_specific_method_version,
        )
        if review_source:
            paper_review["source_baseline"] = _freeze_source_baseline(
                project_dir,
                run_context_dir(project_dir, phase_slug, run_id)
                / "paper-review"
                / "source-baseline",
                review_source[2],
            )
        frozen_theory_audit_source = (
            _freeze_theory_audit_source(
                project_dir, run_id, theory_audit_source
            )
            if theory_audit_source is not None
            else None
        )

        summary = _contained_file_destination(
            project_dir / "phase-summaries" / phase_slug / f"{run_id}.html",
            project_dir,
            label="run summary destination",
        )
        decision_path = _contained_file_destination(
            summary.with_suffix(".decision.json"),
            project_dir,
            label="structured decision destination",
        )
        control_root = project_state._ensure_control_directory(project_dir).resolve(
            strict=True
        )
        prompt_file = _contained_file_destination(
            prompt_path(project_dir, phase_slug, run_id),
            control_root,
            label="run prompt destination",
        )
        log_file = _contained_file_destination(
            run_log_path(project_dir, phase_slug, run_id),
            control_root,
            label="run log destination",
        )
        run = project_state.get_run(project_dir, phase_slug, run_id)
        prompt = _build_lead_prompt(
            project_dir,
            phase,
            profiles,
            board_slug,
            run_id,
            run_number,
            rounds,
            user_feedback,
            run.get("prerequisite_snapshot", report),
            snapshots,
            summary,
            decision_path,
            paper_review,
            frozen_theory_audit_source,
            method_selection,
        )
        _write_text_atomic(prompt_file, prompt)
        timeout_minutes = int(config.get("hub", {}).get("run_timeout_minutes", 120))
        if timeout_minutes < 1:
            raise LaunchError("hub.run_timeout_minutes must be a positive integer")
        recommended_skills = _recommended_skills_snapshot(
            config,
            phase_slug,
            effective_phase=plan_phase,
            hermes_root=hermes_root,
        )
        if launch_plan_version(
            config,
            phase_slug,
            effective_phase=plan_phase,
            hermes_root=hermes_root,
            recommended_skills_snapshot=recommended_skills,
        ) != current_phase_plan_version:
            raise LaunchError(
                "The phase instructions changed while the run inputs were being "
                "frozen. Reload the phase and launch again."
            )
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "project_dir": str(project_dir),
            "phase_slug": phase_slug,
            "run_id": run_id,
            "run_number": run_number,
            "rounds_requested": rounds,
            "phase": phase,
            "profiles": profiles,
            "board_slug": board_slug,
            "hermes_executable": hermes,
            "hermes_root": str(hermes_root),
            "lead_profile": profiles["research_lead"],
            "timeout_minutes": timeout_minutes,
            "allow_unattended_tools": True,
            "user_feedback": user_feedback,
            "output_root": str(output_root),
            "summary_path": str(summary),
            "decision_path": str(decision_path),
            "prompt_path": str(prompt_file),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "snapshots": snapshots,
            "prerequisite_snapshot": run.get("prerequisite_snapshot", report),
            "paper_review": paper_review,
            "submission_outputs": submission_outputs,
            "method_selection": method_selection,
            "recommended_skills": recommended_skills,
            "phase_plan_version": current_phase_plan_version,
            "prerequisite_report_version": current_prerequisite_version,
        }
        if phase_slug == NUMERICAL_VALIDATION_PHASE:
            manifest["protocol_checkpoint"] = {
                "schema_version": (
                    project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION
                ),
                "path": str(output_root / "protocol" / "protocol-checkpoint.json"),
                "protocol_root": str(output_root / "protocol"),
                "max_bytes": project_state.MAX_PROTOCOL_CHECKPOINT_BYTES,
            }
        if frozen_theory_audit_source is not None:
            manifest["proof_audit_source"] = frozen_theory_audit_source
        _validate_manifest_snapshot_schema(manifest)
        manifest_file = run_manifest_path(project_dir, phase_slug, run_id)
        _write_text_atomic(
            manifest_file, json.dumps(manifest, indent=2, ensure_ascii=False)
        )
        project_state.seal_run_manifest(
            project_dir, phase_slug, run_id, manifest_file
        )
        _verify_frozen_inputs(project_dir, phase_slug, run_id, manifest)

        worker_args = [
            sys.executable,
            Path(__file__).resolve(),
            "worker",
            "--project-dir",
            project_dir,
            "--phase",
            phase_slug,
            "--run-id",
            run_id,
            "--manifest",
            manifest_file,
        ]

        environment = os.environ.copy()
        environment["HERMES_KANBAN_BOARD"] = board_slug
        environment["HERMES_KANBAN_WORKSPACE"] = str(project_dir)
        environment = _hermes_environment(
            hermes_root,
            base=environment,
        )
        popen_options: dict[str, Any] = {}
        if os.name == "nt":
            popen_options["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            popen_options["start_new_session"] = True
        with _open_new_run_log(log_file) as log_handle:
            process = subprocess.Popen(
                [str(value) for value in worker_args],
                cwd=str(project_dir),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                **popen_options,
            )
        deadline = time.monotonic() + 5
        registered = False
        while time.monotonic() < deadline:
            current = project_state.get_run(project_dir, phase_slug, run_id)
            observed_identity = _process_identity(process.pid)
            if (
                current.get("process_pid") == process.pid
                and observed_identity
                and current.get("process_identity") == observed_identity
            ):
                registered = True
                break
            if current.get("status") not in project_state.ACTIVE_RUN_STATUSES:
                if current.get("status") == "failed":
                    raise LaunchError(current.get("error") or "Run worker failed during startup")
                registered = True
                break
            if process.poll() is not None:
                raise LaunchError("Run worker exited before completing its startup handshake")
            time.sleep(0.05)
        if not registered:
            raise LaunchError("Run worker did not complete its startup handshake")
    except Exception as exc:
        cleanup_warnings: list[str] = []
        if run_id is not None:
            try:
                project_state.begin_run_cleanup(
                    project_dir, phase_slug, run_id, "failed", str(exc)
                )
            except Exception:
                pass
        if process is not None and process.poll() is None:
            identity = _process_identity(process.pid)
            try:
                if identity:
                    _terminate_pid_tree(process.pid, identity)
                else:
                    process.kill()
                    process.wait(timeout=5)
            except Exception as cleanup_exc:
                cleanup_warnings.append(str(cleanup_exc))
        if (
            run_id is not None
            and process is not None
            and manifest_file is not None
            and manifest_file.is_file()
        ):
            cleanup_warnings.extend(
                _stop_external_tasks(project_dir, phase_slug, run_id)
            )
        if run_id is not None and not cleanup_warnings:
            try:
                project_state.finalize_run_cleanup(
                    project_dir, phase_slug, run_id
                )
            except Exception as cleanup_exc:
                cleanup_warnings.append(str(cleanup_exc))
        for warning in cleanup_warnings:
            print(f"launch cleanup remains pending: {warning}", file=sys.stderr)
        if isinstance(exc, (LaunchError, project_state.ProjectStateError)):
            raise
        raise LaunchError(f"Run launch failed: {exc}") from exc

    return {
        "run_id": run_id,
        "run_index": index,
        "run_number": run_number,
        "rounds_requested": rounds,
        "board_slug": board_slug,
        "pid": process.pid,
        "prompt_file": str(prompt_file),
        "manifest_file": str(manifest_file),
        "log_file": str(log_file),
        "summary_file": str(summary),
    }


def _worker(
    project_dir: str,
    phase_slug: str,
    run_id: str,
    manifest_file: str,
) -> int:
    """Register supervision, run Hermes with a bounded prompt, and enforce timeout."""

    project_path = Path(project_dir).resolve()
    expected_manifest = run_manifest_path(project_path, phase_slug, run_id).resolve()
    if Path(manifest_file).resolve() != expected_manifest:
        print("Worker manifest path does not match the run identity", file=sys.stderr)
        return 1
    manifest = _read_manifest(project_path, phase_slug, run_id)
    process_identity = _process_identity(os.getpid())
    if not process_identity:
        project_state.fail_run_if_active(
            project_path,
            phase_slug,
            run_id,
            "Could not establish a safe worker process identity.",
        )
        return 1
    try:
        _verify_frozen_inputs(project_path, phase_slug, run_id, manifest)
        prompt_file = Path(str(manifest["prompt_path"])).resolve(strict=True)
        if prompt_file != prompt_path(project_path, phase_slug, run_id).resolve():
            raise LaunchError("Frozen lead prompt path does not match the run identity")
        actual_hash = _sha256_file(
            prompt_file,
            max_bytes=MAX_LEAD_PROMPT_BYTES,
            label="frozen lead prompt",
            allow_empty=False,
        )
        if actual_hash != manifest.get("prompt_sha256"):
            raise LaunchError("The frozen lead prompt failed its integrity check")
    except Exception as exc:
        project_state.fail_run_if_active(
            project_path,
            phase_slug,
            run_id,
            str(exc),
        )
        return 1
    try:
        project_state.set_process_pid(
            project_path,
            phase_slug,
            run_id,
            os.getpid(),
            process_identity=process_identity,
        )
    except Exception as exc:
        project_state.fail_run_if_active(
            project_path,
            phase_slug,
            run_id,
            str(exc),
        )
        return 1
    bootstrap = (
        f"Read the complete run instructions from {prompt_file}. Verify that you are "
        f"working on run {run_id}, follow the file exactly, and do not start any other phase."
    )
    try:
        preloaded_skills = _verified_preloaded_skill_names(
            manifest,
            "research_lead",
        )
        command = [
            str(manifest["hermes_executable"]),
            "--profile",
            str(manifest["lead_profile"]),
            "chat",
        ]
        for skill_name in preloaded_skills:
            command.extend(("--skills", skill_name))
        command.extend(("-q", bootstrap, "--yolo"))
        result = _run_logged_command(
            command,
            timeout=int(manifest["timeout_minutes"]) * 60,
            project_dir=project_path,
            phase_slug=phase_slug,
            run_id=run_id,
            environment=_hermes_environment(_manifest_hermes_root(manifest)),
        )
        return_code = int(result.returncode)
    except subprocess.TimeoutExpired:
        error = (
            f"Run exceeded the configured {manifest['timeout_minutes']}-minute timeout."
        )
        _, warnings = _cleanup_run_execution(
            project_path,
            phase_slug,
            run_id,
            outcome="failed",
            reason=error,
            expected_pid=os.getpid(),
            terminate_worker=False,
            manifest=manifest,
        )
        for warning in warnings:
            print(f"cleanup remains pending: {warning}", file=sys.stderr)
        return 1
    except _ProcessOutputLimitExceeded as exc:
        return_code = 1
        error = str(exc)
    except Exception as exc:
        return_code = 1
        error = f"Hermes could not start: {exc}"
    else:
        if return_code == 0:
            finalized = project_state.finalize_run_submission(
                project_path,
                phase_slug,
                run_id,
                expected_pid=os.getpid(),
            )
            if finalized:
                return 0
            current = project_state.get_run(project_path, phase_slug, run_id)
            if current.get("status") == "awaiting_review":
                return 0
            if current.get("status") not in project_state.ACTIVE_RUN_STATUSES:
                return 1
            error = "Hermes exited without recording a summary for user review."
        else:
            error = (
                f"Hermes exited with code {return_code} before the run was submitted "
                "for user review. Inspect the run log for details."
            )
    try:
        _, warnings = _cleanup_run_execution(
            project_path,
            phase_slug,
            run_id,
            outcome="failed",
            reason=error,
            expected_pid=os.getpid(),
            terminate_worker=False,
            manifest=manifest,
        )
        for warning in warnings:
            print(f"cleanup remains pending: {warning}", file=sys.stderr)
    except Exception as exc:
        print(f"Could not record worker outcome: {exc}", file=sys.stderr)
        return 1
    return return_code


def _process_identity(pid: int | None) -> str | None:
    """Return a process birth identity so a recycled PID is never trusted."""

    if not pid:
        return None
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class FILETIME(ctypes.Structure):
                _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(FILETIME),
                ctypes.POINTER(FILETIME),
                ctypes.POINTER(FILETIME),
                ctypes.POINTER(FILETIME),
            ]
            kernel32.GetProcessTimes.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                return None
            try:
                creation, exit_time, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                if not kernel32.GetProcessTimes(
                    handle,
                    ctypes.byref(creation),
                    ctypes.byref(exit_time),
                    ctypes.byref(kernel),
                    ctypes.byref(user),
                ):
                    return None
                ticks = (int(creation.high) << 32) | int(creation.low)
                return f"windows:{ticks}"
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return None
    proc = Path("/proc") / str(pid)
    try:
        stat = (proc / "stat").read_text(encoding="utf-8")
        remainder = stat.rsplit(")", 1)[1].split()
        start_ticks = remainder[19]
        executable = os.readlink(proc / "exe")
        return f"proc:{start_ticks}:{executable}"
    except (OSError, IndexError, ValueError):
        pass
    try:
        shown = _run_process_with_bounded_output(
            ["ps", "-p", str(pid), "-o", "lstart=,comm="],
            timeout=2,
            max_output_bytes=MAX_PROCESS_CONTROL_OUTPUT_BYTES,
        )
    except (LaunchError, subprocess.SubprocessError):
        return None
    value = shown.stdout.strip()
    return f"ps:{value}" if shown.returncode == 0 and value else None


def _pid_is_alive(pid: int | None, expected_identity: str | None = None) -> bool:
    """Conservatively report whether the recorded process may still be alive.

    Failure to read a live PID's birth identity is uncertainty, not evidence
    that the recorded worker has stopped.  Callers that need to distinguish an
    exact match from uncertainty use :func:`_pid_identity_status`.
    """

    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError):
        return False
    if expected_identity:
        observed_identity = _process_identity(pid)
        if observed_identity is not None and observed_identity != expected_identity:
            return False
    return True


def _pid_identity_status(pid: int | None, expected_identity: str | None) -> str:
    """Return absent, matching, mismatched, or unverifiable for one PID."""

    if not _pid_is_alive(pid):
        return "absent"
    if not expected_identity:
        return "unverifiable"
    observed_identity = _process_identity(pid)
    if observed_identity is None:
        return "unverifiable"
    return "matching" if observed_identity == expected_identity else "mismatched"


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _terminate_pid_tree(pid: int, expected_identity: str | None = None) -> None:
    if expected_identity and _process_identity(pid) != expected_identity:
        raise LaunchError(f"Refusing to stop recycled or unverified process PID {pid}")
    if os.name == "nt":
        try:
            result = _run_process_with_bounded_output(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                timeout=15,
                max_output_bytes=MAX_PROCESS_CONTROL_OUTPUT_BYTES,
            )
        except (LaunchError, subprocess.SubprocessError) as exc:
            raise LaunchError(f"Could not stop process {pid}: {exc}") from exc
        if result.returncode not in {0, 128}:
            detail = (result.stderr or result.stdout).strip()
            raise LaunchError(f"Could not stop process {pid}: {detail}")
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    except OSError as exc:
        raise LaunchError(f"Could not stop process {pid}: {exc}") from exc


def _task_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("tasks", "items", "data"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _stop_external_tasks(
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    manifest: Mapping[str, Any] | None = None,
) -> list[str]:
    """Archive every run-scoped Hermes task and stop its current worker."""

    warnings: list[str] = []
    try:
        manifest = dict(manifest or _read_manifest(project_dir, phase_slug, run_id))
    except Exception as exc:
        return [f"Could not load run manifest for task cleanup: {exc}"]
    task_ids: set[str] = set()
    try:
        run = project_state.get_run(project_dir, phase_slug, run_id)
        for round_state in run.get("rounds", []):
            task_ids.update(
                str(task["task_id"])
                for task in round_state.get("tasks", [])
                if task.get("task_id")
            )
    except Exception as exc:
        warnings.append(f"Could not read recorded task IDs: {exc}")

    try:
        listed = _run_command(
            [
                str(manifest["hermes_executable"]),
                "kanban",
                "--board",
                str(manifest["board_slug"]),
                "list",
                "--json",
            ],
            environment=_hermes_environment(_manifest_hermes_root(manifest)),
        )
    except Exception as exc:
        warnings.append(f"Could not list run-scoped Hermes tasks: {exc}")
        listed = None
    if listed is not None and listed.returncode == 0:
        try:
            short_id = run_id.split("-", 1)[0]
            for item in _task_list(json.loads(listed.stdout or "[]")):
                if f"[{short_id}]" in str(item.get("title", "")) and item.get("id"):
                    task_ids.add(str(item["id"]))
        except (TypeError, ValueError) as exc:
            warnings.append(f"Could not parse board task list: {exc}")
    elif listed is not None:
        warnings.append(
            "Could not list run-scoped Hermes tasks: "
            + (listed.stderr or listed.stdout).strip()
        )

    for task_id in sorted(task_ids):
        warning = _archive_external_task(manifest, task_id)
        if warning:
            warnings.append(warning)
    for warning in warnings:
        print(f"task cleanup warning: {warning}", file=sys.stderr)
    return warnings


def _cleanup_run_execution(
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    *,
    outcome: str,
    reason: str,
    expected_pid: int | None = None,
    terminate_worker: bool,
    manifest: Mapping[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Keep the active lease until process and Hermes cleanup is confirmed."""

    began = project_state.begin_run_cleanup(
        project_dir,
        phase_slug,
        run_id,
        outcome,
        reason,
        expected_pid=expected_pid,
    )
    if not began:
        return False, []

    run = project_state.get_run(project_dir, phase_slug, run_id)
    pid = run.get("process_pid")
    identity = str(run.get("process_identity") or "").strip() or None
    warnings: list[str] = []
    if terminate_worker and pid:
        identity_status = _pid_identity_status(int(pid), identity)
        if identity_status == "unverifiable":
            if identity:
                warnings.append(
                    f"Could not verify the recorded identity of process PID {pid}; "
                    "the active lease and external tasks remain unchanged."
                )
            else:
                warnings.append(
                    f"Refusing to stop unverified legacy process PID {pid}; "
                    "explicit recovery is required after manual inspection."
                )
        elif identity_status == "matching":
            try:
                _terminate_pid_tree(int(pid), identity)
            except LaunchError as exc:
                warnings.append(str(exc))
            else:
                remaining_status = _pid_identity_status(int(pid), identity)
                if remaining_status == "matching":
                    warnings.append(f"Worker PID {pid} is still alive after termination")
                elif remaining_status == "unverifiable":
                    warnings.append(
                        f"Could not confirm termination of process PID {pid}; "
                        "the active lease and external tasks remain unchanged."
                    )

    if warnings:
        return True, warnings

    warnings.extend(
        _stop_external_tasks(project_dir, phase_slug, run_id, manifest)
    )
    if not warnings:
        finalized = project_state.finalize_run_cleanup(
            project_dir,
            phase_slug,
            run_id,
            expected_pid=expected_pid,
        )
        if not finalized:
            warnings.append("Run changed state before cleanup could be finalized")
    return True, warnings


def reconcile_active_run(project_dir: str | Path) -> dict[str, Any] | None:
    """Recover state after a crashed or timed-out detached worker."""

    project_dir = Path(project_dir).resolve()
    active = project_state.get_active_run(project_dir)
    if not active or active.get("conflict"):
        return active
    phase_slug = str(active["phase_slug"])
    run_id = str(active["run_id"])
    run = project_state.get_run(project_dir, phase_slug, run_id)
    timeout_minutes = int(
        run.get("timeout_minutes")
        or _load_hub_config().get("hub", {}).get("run_timeout_minutes", 120)
    )
    started = _parse_timestamp(run.get("started"))
    age_seconds = (
        (datetime.now(timezone.utc) - started).total_seconds() if started else 0
    )
    timed_out = timeout_minutes > 0 and age_seconds > timeout_minutes * 60
    pid = run.get("process_pid")
    process_identity = run.get("process_identity")
    identity_status = _pid_identity_status(pid, process_identity) if pid else "absent"
    dead = bool(pid) and identity_status in {"absent", "mismatched"}
    unstarted = not pid and age_seconds > 30
    if run.get("status") == "stopping":
        _, warnings = _cleanup_run_execution(
            project_dir,
            phase_slug,
            run_id,
            outcome=str(run.get("cleanup_outcome") or "failed"),
            reason=str(run.get("cleanup_reason") or "Run cleanup is pending."),
            expected_pid=int(pid) if pid else None,
            terminate_worker=True,
        )
        for warning in warnings:
            print(f"cleanup remains pending: {warning}", file=sys.stderr)
    elif timed_out:
        _, warnings = _cleanup_run_execution(
            project_dir,
            phase_slug,
            run_id,
            outcome="failed",
            reason=f"Run exceeded the configured {timeout_minutes}-minute timeout.",
            expected_pid=int(pid) if pid else None,
            terminate_worker=True,
        )
        for warning in warnings:
            print(f"cleanup remains pending: {warning}", file=sys.stderr)
    elif dead or unstarted:
        _, warnings = _cleanup_run_execution(
            project_dir,
            phase_slug,
            run_id,
            outcome="failed",
            reason="The background worker stopped before submitting the run for review.",
            expected_pid=int(pid) if pid else None,
            terminate_worker=False,
        )
        for warning in warnings:
            print(f"cleanup remains pending: {warning}", file=sys.stderr)
    return project_state.get_active_run(project_dir)


def retry_run_cleanup(
    project_dir: str | Path,
    phase_slug: str,
    run_id: str,
) -> dict[str, Any]:
    """Retry cleanup for one exact run without touching another active run."""

    project_dir = Path(project_dir).resolve()
    run = project_state.get_run(project_dir, phase_slug, run_id)
    if run.get("status") != "stopping":
        raise LaunchError("Only a cleanup-pending run can retry cleanup")
    pid = run.get("process_pid")
    began, warnings = _cleanup_run_execution(
        project_dir,
        phase_slug,
        run_id,
        outcome=str(run.get("cleanup_outcome") or "failed"),
        reason=str(run.get("cleanup_reason") or "Run cleanup is pending."),
        expected_pid=int(pid) if pid else None,
        terminate_worker=True,
    )
    if not began:
        raise LaunchError("Run changed state before cleanup could be retried")
    if warnings:
        raise LaunchError("; ".join(warnings))
    return project_state.get_run(project_dir, phase_slug, run_id)


def cancel_active_run(
    project_dir: str | Path,
    phase_slug: str,
    run_id: str,
    reason: str = "Cancelled by the user from the web UI.",
) -> None:
    project_dir = Path(project_dir).resolve()
    run = project_state.get_run(project_dir, phase_slug, run_id)
    if run.get("status") not in project_state.ACTIVE_RUN_STATUSES:
        raise LaunchError("Only an active run can be cancelled")
    pid = run.get("process_pid")
    began, warnings = _cleanup_run_execution(
        project_dir,
        phase_slug,
        run_id,
        outcome="cancelled",
        reason=reason,
        expected_pid=int(pid) if pid else None,
        terminate_worker=True,
    )
    if not began:
        raise LaunchError("Run changed state before cancellation could be recorded")
    if warnings:
        raise LaunchError(
            "Cancellation is held in cleanup-pending state because external shutdown "
            "could not be confirmed. Inspect the log and board, then retry cancellation "
            "or explicitly recover the stopping run."
        )


def get_run_status(project_dir: str | Path) -> dict[str, Any]:
    reconcile_active_run(project_dir)
    active = project_state.get_active_run(project_dir)
    if not active or active.get("conflict"):
        return {"active": False, "conflict": active if active else None}
    run = project_state.get_run(
        project_dir, str(active["phase_slug"]), str(active["run_id"])
    )
    return {
        "active": True,
        **active,
        "rounds_requested": run.get("rounds_requested", 1),
        "rounds_completed": project_state.completed_round_count(
            project_dir, str(active["phase_slug"]), str(active["run_id"])
        ),
    }


def _run_ref(arguments: argparse.Namespace) -> str | int:
    if getattr(arguments, "run_id", None):
        return arguments.run_id
    if getattr(arguments, "run_index", None) is not None:
        return int(arguments.run_index)
    raise LaunchError("A run ID is required")


def _add_run_reference(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-id")
    group.add_argument("--run-index", type=int, help=argparse.SUPPRESS)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research Hub run launcher")
    commands = parser.add_subparsers(dest="command", required=True)

    complete = commands.add_parser("complete", help="Submit a run for user review")
    complete.add_argument("--project-dir", required=True)
    complete.add_argument("--phase", required=True)
    _add_run_reference(complete)
    complete.add_argument("--summary", required=True)
    complete.add_argument("--decision-record")

    protocol_seal = commands.add_parser(
        "protocol-seal",
        help="Seal the Phase 04 computational protocol before main results",
    )
    protocol_seal.add_argument("--project-dir", required=True)
    protocol_seal.add_argument("--phase", required=True)
    protocol_seal.add_argument("--run-id", required=True)
    protocol_seal.add_argument("--checkpoint", required=True)

    start = commands.add_parser("round-start", help="Record the start of a round")
    start.add_argument("--project-dir", required=True)
    start.add_argument("--phase", required=True)
    _add_run_reference(start)
    start.add_argument("--round", type=int, required=True)
    directive = start.add_mutually_exclusive_group(required=True)
    directive.add_argument("--directive-file")
    directive.add_argument("--directive", help=argparse.SUPPRESS)
    start.add_argument("--agents", required=True)

    dispatch = commands.add_parser("dispatch-task", help="Create one frozen run task")
    dispatch.add_argument("--project-dir", required=True)
    dispatch.add_argument("--phase", required=True)
    dispatch.add_argument("--run-id", required=True)
    dispatch.add_argument("--round", type=int, required=True)
    dispatch.add_argument("--role", required=True)
    dispatch.add_argument(
        "--task-kind",
        choices=("standard", "protocol", "result"),
        default="standard",
    )
    dispatch.add_argument("--directive-file", required=True)

    finish = commands.add_parser("round-complete", help="Record round artifacts")
    finish.add_argument("--project-dir", required=True)
    finish.add_argument("--phase", required=True)
    _add_run_reference(finish)
    finish.add_argument("--round", type=int, required=True)
    finish.add_argument("--output", action="append", default=[])
    finish.add_argument("--outputs", help=argparse.SUPPRESS)

    status = commands.add_parser("status", help="Show active run status")
    status.add_argument("--project-dir", required=True)

    worker = commands.add_parser("worker", help=argparse.SUPPRESS)
    worker.add_argument("--project-dir", required=True)
    worker.add_argument("--phase", required=True)
    worker.add_argument("--run-id", required=True)
    worker.add_argument("--manifest", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    worker_log: tuple[Path, int, os.stat_result] | None = None
    exit_code = 0
    try:
        if args.command == "complete":
            reference = _run_ref(args)
            run = project_state.get_run(args.project_dir, args.phase, reference)
            manifest = _read_manifest(
                Path(args.project_dir).resolve(), args.phase, str(run["run_id"])
            )
            if Path(args.summary).resolve() != Path(manifest["summary_path"]).resolve():
                raise LaunchError("Summary path does not match the immutable run manifest")
            if _manifest_schema_version(manifest) >= 4:
                if not args.decision_record:
                    raise LaunchError("This run requires a structured decision record")
                if Path(args.decision_record).resolve() != Path(
                    manifest["decision_path"]
                ).resolve():
                    raise LaunchError(
                        "Decision record path does not match the immutable run manifest"
                    )
            _verify_frozen_inputs(
                Path(args.project_dir).resolve(), args.phase, str(run["run_id"]), manifest
            )
            _verify_completed_round_artifacts(Path(args.project_dir).resolve(), run)
            _verify_task_briefs(Path(args.project_dir).resolve(), args.phase, run)
            project_state.stage_run_submission(
                args.project_dir,
                args.phase,
                reference,
                args.summary,
                args.decision_record,
            )
            recorded_items = (
                "Summary and decision record"
                if args.decision_record
                else "Summary"
            )
            print(
                f"{recorded_items} recorded. The run will enter user review "
                "after the worker exits."
            )
        elif args.command == "protocol-seal":
            project_dir = Path(args.project_dir).resolve()
            run = project_state.get_run(
                project_dir, args.phase, args.run_id
            )
            stable_id = str(run["run_id"])
            manifest = _read_manifest(
                project_dir, args.phase, stable_id
            )
            _verify_frozen_inputs(
                project_dir, args.phase, stable_id, manifest
            )
            record = project_state.seal_protocol_checkpoint(
                project_dir,
                args.phase,
                stable_id,
                args.checkpoint,
            )
            files = record.get("data", {}).get("protocol_files", [])
            print(
                "Protocol checkpoint sealed at "
                f"{record.get('sealed_at', 'recorded time')} with SHA-256 "
                f"{record.get('sha256', 'not recorded')} and {len(files)} "
                f"file{'s' if len(files) != 1 else ''}. Main-result work may begin."
            )
        elif args.command == "round-start":
            reference = _run_ref(args)
            run = project_state.get_run(args.project_dir, args.phase, reference)
            stable_id = str(run["run_id"])
            manifest = _read_manifest(
                Path(args.project_dir).resolve(), args.phase, stable_id
            )
            agents = [item.strip() for item in args.agents.split(",") if item.strip()]
            if sorted(agents) != sorted(_planned_roles(manifest, args.round)):
                raise LaunchError("Round agents do not match the frozen run plan")
            lead_directive = (
                _directive_text(
                    Path(args.project_dir).resolve(),
                    args.phase,
                    stable_id,
                    args.round,
                    args.directive_file,
                )
                if args.directive_file
                else args.directive
            )
            number = project_state.start_round(
                args.project_dir,
                args.phase,
                reference,
                lead_directive,
                agents,
                round_n=args.round,
            )
            print(f"Round {number} started.")
        elif args.command == "dispatch-task":
            task_id = _dispatch_task(
                args.project_dir,
                args.phase,
                args.run_id,
                args.round,
                args.role,
                args.directive_file,
                args.task_kind,
            )
            print(f"Task {task_id} is recorded for {args.role}.")
        elif args.command == "round-complete":
            outputs = list(args.output)
            if args.outputs:
                outputs.extend(
                    item.strip() for item in args.outputs.split(",") if item.strip()
                )
            if not outputs:
                raise LaunchError("At least one --output is required")
            _complete_round_checked(
                args.project_dir,
                args.phase,
                _run_ref(args),
                args.round,
                outputs,
            )
            print(f"Round {args.round} completed with {len(outputs)} artifacts.")
        elif args.command == "status":
            print(json.dumps(get_run_status(args.project_dir), indent=2))
        elif args.command == "worker":
            log_path = run_log_path(
                Path(args.project_dir).resolve(), args.phase, args.run_id
            )
            descriptor = _worker_log_descriptor()
            bound_metadata = _run_log_descriptor_metadata(descriptor)
            worker_log = (log_path, descriptor, bound_metadata)
            _flush_worker_log_streams()
            _verified_run_log_descriptor(
                log_path, descriptor, expected=bound_metadata
            )
            exit_code = _worker(
                args.project_dir,
                args.phase,
                args.run_id,
                args.manifest,
            )
    except (LaunchError, project_state.ProjectStateError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        if worker_log is not None:
            log_path, descriptor, bound_metadata = worker_log
            try:
                _truncate_run_log(
                    log_path,
                    descriptor=descriptor,
                    expected=bound_metadata,
                )
            except LaunchError:
                exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
