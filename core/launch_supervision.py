#!/usr/bin/env python3

"""Active-run supervision: reconciliation, cancellation, and cleanup."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping



from core import launch_common
from core import project_state
from core import launch_plans
from core import launch_process

logger = logging.getLogger("launch.supervision")

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
        identity_status = launch_process._pid_identity_status(int(pid), identity)
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
                launch_process._terminate_pid_tree(int(pid), identity)
            except launch_common.LaunchError as exc:
                warnings.append(str(exc))
            else:
                remaining_status = launch_process._pid_identity_status(int(pid), identity)
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
        launch_process._stop_external_tasks(project_dir, phase_slug, run_id, manifest)
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
        or launch_plans._load_hub_config().get("hub", {}).get("run_timeout_minutes", 120)
    )
    started = launch_common._parse_timestamp(run.get("started"))
    age_seconds = (
        (datetime.now(timezone.utc) - started).total_seconds() if started else 0
    )
    timed_out = timeout_minutes > 0 and age_seconds > timeout_minutes * 60
    pid = run.get("process_pid")
    process_identity = run.get("process_identity")
    identity_status = launch_process._pid_identity_status(pid, process_identity) if pid else "absent"
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
            logger.warning("Cleanup pending: %s", warning)
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
            logger.warning("Cleanup pending: %s", warning)
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
            logger.warning("Cleanup pending: %s", warning)
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
        raise launch_common.LaunchError("Only a cleanup-pending run can retry cleanup")
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
        raise launch_common.LaunchError("Run changed state before cleanup could be retried")
    if warnings:
        raise launch_common.LaunchError("; ".join(warnings))
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
        raise launch_common.LaunchError("Only an active run can be cancelled")
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
        raise launch_common.LaunchError("Run changed state before cancellation could be recorded")
    if warnings:
        raise launch_common.LaunchError(
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
