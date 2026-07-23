"""Prepare explicit lifecycle data for the Research Hub web interface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import project_state
from .launch_run import LaunchError, exact_rerun_options


MAX_REVIEW_TARGET_BYTES = 2 * 1024 * 1024
SOURCE_BASELINE_STATUS_BY_RUN_STATUS = {
    "approved": "accepted",
    "awaiting_review": "proposed",
    "revision_requested": "proposed",
    "superseded": "historical",
}


def decision_report_version(kind: str, report: Mapping[str, Any]) -> str:
    """Return the state layer's decision-report fingerprint."""

    return project_state.decision_report_version(kind, report)


def recovery_phase_config(
    project_dir: Path,
    phase_slug: str,
    phase_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a non-launchable display plan for a phase removed from config.

    The newest run's sealed manifest is preferred because it preserves the plan
    the user actually launched. A generic state-derived plan keeps cancellation
    and history reachable when that manifest is absent or fails verification.
    """

    project_dir = Path(project_dir).resolve()
    runs = [run for run in phase_state.get("runs", []) if isinstance(run, Mapping)]
    latest_id = str(phase_state.get("latest_run") or "")
    latest = next(
        (run for run in reversed(runs) if str(run.get("run_id", "")) == latest_id),
        runs[-1] if runs else None,
    )
    recovered: dict[str, Any] | None = None
    if latest is not None:
        raw_manifest = latest.get("manifest_path")
        expected_hash = str(latest.get("manifest_sha256") or "").lower()
        if raw_manifest and expected_hash:
            try:
                manifest_path = Path(str(raw_manifest)).resolve(strict=True)
                manifest_root = (
                    project_state.state_dir(project_dir) / "runs" / phase_slug
                ).resolve()
                manifest_path.relative_to(manifest_root)
                payload = project_state.bounded_file_bytes(
                    manifest_path,
                    maximum=project_state.MAX_CONTROL_FILE_BYTES,
                    label="run manifest",
                )
                if hashlib.sha256(payload).hexdigest() != expected_hash:
                    raise ValueError("manifest hash mismatch")
                manifest = json.loads(payload.decode("utf-8"))
                if not isinstance(manifest, Mapping):
                    raise ValueError("manifest must be a mapping")
                manifest_phase = manifest.get("phase")
                if (
                    not isinstance(manifest_phase, Mapping)
                    or manifest.get("phase_slug") != phase_slug
                    or manifest.get("run_id") != latest.get("run_id")
                    or manifest_phase.get("slug") != phase_slug
                ):
                    raise ValueError("manifest identity mismatch")
                recovered = dict(manifest_phase)
            except (
                OSError,
                TypeError,
                ValueError,
                UnicodeError,
                json.JSONDecodeError,
                project_state.ProjectStateError,
            ):
                recovered = None

    try:
        requested = max(1, int((latest or {}).get("rounds_requested", 1)))
    except (TypeError, ValueError):
        requested = 1
    fallback_name = phase_slug.split("-", 1)[-1].replace("-", " ").title()
    phase = recovered or {
        "slug": phase_slug,
        "name": fallback_name,
        "description": "This phase is no longer present in the current configuration.",
        "pattern": "parallel",
        "rounds": {"min": requested, "default": requested, "max": requested},
        "gated_by": [],
        "context_from": [],
        "folder": "No longer configured",
        "members": sorted({
            str(agent)
            for run in runs
            for round_ in run.get("rounds", [])
            if isinstance(round_, Mapping)
            for agent in round_.get("agents", [])
            if str(agent)
        }),
    }
    phase["slug"] = phase_slug
    phase["name"] = str(phase.get("name") or fallback_name)
    phase["description"] = str(
        phase.get("description")
        or "This phase is no longer present in the current configuration."
    )
    if phase.get("pattern") not in {"parallel", "sequential", "debate"}:
        phase["pattern"] = "parallel"
    raw_members = phase.get("members", [])
    phase["members"] = [
        str(member) for member in raw_members if str(member)
    ] if isinstance(raw_members, (list, tuple)) else []
    phase["stages"] = [
        dict(stage) for stage in phase.get("stages", []) if isinstance(stage, Mapping)
    ]
    if phase["pattern"] == "sequential" and not phase["stages"]:
        phase["pattern"] = "parallel"
    raw_rounds = phase.get("rounds")
    try:
        minimum = int(raw_rounds["min"])
        default = int(raw_rounds["default"])
        maximum = int(raw_rounds["max"])
        if not 1 <= minimum <= default <= maximum <= 50:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        phase["rounds"] = {
            "min": requested,
            "default": requested,
            "max": requested,
        }
    else:
        phase["rounds"] = {
            "min": minimum,
            "default": default,
            "max": maximum,
        }
    raw_gates = phase.get("gated_by", [])
    phase["gated_by"] = [
        str(item) for item in raw_gates if str(item)
    ] if isinstance(raw_gates, (list, tuple)) else []
    raw_context = phase.get("context_from", [])
    phase["context_from"] = [
        str(item) for item in raw_context if str(item)
    ] if isinstance(raw_context, (list, tuple)) else []
    phase["folder"] = str(phase.get("folder") or "No longer configured")
    phase["recovery_only"] = True
    phase["recovery_source"] = (
        "latest sealed run manifest" if recovered is not None else "project state fallback"
    )
    return phase


def _dependencies(phases: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    return {
        str(phase["slug"]): [str(item) for item in phase.get("gated_by", [])]
        for phase in phases
    }


def _completed_count(run: Mapping[str, Any]) -> int:
    return sum(1 for item in run.get("rounds", []) if item.get("completed"))


def _discover_summary_path(
    project_dir: Path, run: Mapping[str, Any], phase_slug: str
) -> str | None:
    """Resolve the summary path. Falls back to the conventional location
    (phase-summaries/<slug>/<run_id>.html) when the lead never recorded
    final_summary in state — the 'failed but artifacts exist' case."""
    raw_path = run.get("final_summary")
    if raw_path:
        return str(raw_path)
    # Fallback: check the conventional location by run_id
    run_id = run.get("id") or run.get("run_id")
    if not run_id:
        return None
    candidate = (
        project_dir.resolve()
        / "phase-summaries"
        / phase_slug
        / f"{run_id}.html"
    )
    if candidate.is_file() and candidate.stat().st_size > 0:
        return str(candidate.relative_to(project_dir.resolve()))
    return None


def _truncate_conclusion(text: str, max_chars: int = 140) -> str:
    """First sentence(s) of a recommendation, truncated for an overview row."""
    text = text.strip()
    if not text:
        return ""
    # Try to cut at the first sentence boundary within range
    for boundary in (". ", ".\n"):
        idx = text.find(boundary)
        if 0 < idx <= max_chars:
            return text[:idx + 1]
    if len(text) <= max_chars:
        return text
    # Hard truncate at word boundary
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + "…"


def _summary_available(
    project_dir: Path,
    run: Mapping[str, Any],
    phase_slug: str = "",
) -> bool:
    raw_path = _discover_summary_path(project_dir, run, phase_slug)
    if not raw_path:
        return False
    root = project_dir.resolve()
    candidate = (root / str(raw_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    try:
        digest, _ = project_state.bounded_file_digest(
            candidate,
            maximum=project_state.MAX_SUMMARY_BYTES,
            label="final summary",
        )
    except (OSError, project_state.ProjectStateError):
        return False
    recorded_hash = run.get("summary_sha256")
    return not recorded_hash or digest == recorded_hash


def _sealed_run_manifest(
    run: Mapping[str, Any], phase_slug: str
) -> dict[str, Any] | None:
    raw_manifest = run.get("manifest_path")
    manifest_digest = str(run.get("manifest_sha256", "")).lower()
    if not raw_manifest or not manifest_digest:
        return None
    try:
        manifest_path = Path(str(raw_manifest)).resolve(strict=True)
        payload = project_state.bounded_file_bytes(
            manifest_path,
            maximum=project_state.MAX_CONTROL_FILE_BYTES,
            label="run manifest",
        )
        if hashlib.sha256(payload).hexdigest() != manifest_digest:
            return None
        manifest = json.loads(payload.decode("utf-8"))
        if (
            manifest.get("phase_slug") != phase_slug
            or manifest.get("run_id") != run.get("run_id")
        ):
            return None
    except (
        OSError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        project_state.ProjectStateError,
    ):
        return None
    return manifest


def _source_baseline_status(source_baseline: Mapping[str, Any]) -> str:
    field = (
        "source_baseline_status"
        if source_baseline.get("schema_version") == 2
        else "provenance"
    )
    return str(source_baseline.get(field, "")).strip()


def _source_descriptor(
    project_dir: Path,
    phase_slug: str,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a strict display record for a derivative run's sealed source."""

    if not isinstance(manifest, Mapping):
        return None
    source_kind = ""
    source: Mapping[str, Any] | None = None
    target: Mapping[str, Any] | None = None
    baseline: Mapping[str, Any] | None = None
    raw_path = ""
    digest = ""
    source_round: int | None = None
    if phase_slug == "03-theoretical-justification":
        candidate = manifest.get("proof_audit_source")
        if not isinstance(candidate, Mapping):
            return None
        source = candidate
        target_value = candidate.get("target")
        baseline_value = candidate.get("source_baseline")
        if not isinstance(target_value, Mapping):
            return None
        target = target_value
        baseline = baseline_value if isinstance(baseline_value, Mapping) else None
        source_kind = "theory_audit"
        raw_path = str(target.get("source_path", ""))
        digest = str(target.get("sha256", "")).lower()
        try:
            source_round = int(target.get("source_round", 0))
        except (TypeError, ValueError):
            return None
        if source_round < 1:
            return None
    elif phase_slug == "06-paper-writing":
        candidate = manifest.get("paper_review")
        if not isinstance(candidate, Mapping) or candidate.get("kind") != "review_only":
            return None
        baseline_value = candidate.get("source_baseline")
        source = candidate
        baseline = baseline_value if isinstance(baseline_value, Mapping) else None
        source_kind = "manuscript_review"
        raw_path = str(candidate.get("source_path", ""))
        digest = str(candidate.get("source_sha256", "")).lower()
        if digest != str(candidate.get("review_sha256", "")).lower():
            return None
    else:
        return None

    source_schema = source.get("schema_version", 1)
    if baseline is not None:
        source_run_id = str(
            source.get("run_id", "") or baseline.get("run_id", "")
        ).strip()
        baseline_run_id = str(baseline.get("run_id", "")).strip()
        selected_status = str(baseline.get("status_at_selection", "")).strip()
        baseline_status = _source_baseline_status(baseline)
        if (
            not source_run_id
            or source_run_id != baseline_run_id
            or selected_status not in SOURCE_BASELINE_STATUS_BY_RUN_STATUS
            or baseline_status
            != SOURCE_BASELINE_STATUS_BY_RUN_STATUS[selected_status]
        ):
            return None
    elif source_schema == 1:
        source_run_id = str(source.get("run_id", "")).strip()
        if not source_run_id:
            source_run_id = "not recorded in legacy manifest"
        selected_status = "not recorded in legacy manifest"
        baseline_status = "not recorded in legacy manifest"
    else:
        return None
    if (
        len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        return None
    root = Path(project_dir).resolve()
    try:
        candidate_path = Path(raw_path)
        if candidate_path.is_absolute():
            relative_path = candidate_path.resolve(strict=False).relative_to(root)
        else:
            if not raw_path or ".." in candidate_path.parts:
                return None
            relative_path = candidate_path
    except (OSError, ValueError):
        return None
    return {
        "kind": source_kind,
        "source_run_id": source_run_id,
        "source_path": relative_path.as_posix(),
        "source_sha256": digest,
        "status_at_selection": selected_status,
        "source_baseline_status": baseline_status,
        "source_round": source_round,
    }


def _phase_six_post_review_target(
    project_dir: Path,
    phase_slug: str,
    run: Mapping[str, Any],
    integrity_report: Mapping[str, Any],
) -> dict[str, str] | None:
    """Return an exact selectable post-review manuscript from a sealed run."""

    if phase_slug != "06-paper-writing":
        return None
    status = str(run.get("status", ""))
    decision_record = run.get("decision_record")
    if (
        status not in SOURCE_BASELINE_STATUS_BY_RUN_STATUS
        or not run.get("submitted_at")
        or not run.get("final_summary")
        or not isinstance(decision_record, Mapping)
        or not isinstance(decision_record.get("data"), Mapping)
        or not integrity_report.get("ok")
    ):
        return None
    manifest = _sealed_run_manifest(run, phase_slug)
    if manifest is None:
        return None
    try:
        paper_review = manifest.get("paper_review")
        if isinstance(paper_review, Mapping) and paper_review.get("kind") == "review_only":
            return None
        root = project_dir.resolve()
        output_root = Path(str(manifest.get("output_root", ""))).resolve()
        output_root.relative_to(root)
        artifacts = run.get("submission_artifacts")
        record = (
            artifacts.get("post_review_manuscript")
            if isinstance(artifacts, Mapping)
            else None
        )
        if not isinstance(record, Mapping):
            return None
        target = (root / str(record.get("path", ""))).resolve(strict=True)
        target.relative_to(root)
        if target != (output_root / "manuscript-post-review.md").resolve():
            return None
        contents = project_state.bounded_file_bytes(
            target,
            maximum=MAX_REVIEW_TARGET_BYTES,
            label="post-review manuscript",
        )
        recorded_size = int(record.get("size", -1))
    except (
        OSError,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        project_state.ProjectStateError,
    ):
        return None
    digest = hashlib.sha256(contents).hexdigest()
    if (
        not contents.strip()
        or recorded_size != len(contents)
        or digest != str(record.get("sha256", "")).lower()
    ):
        return None
    return {
        "path": target.relative_to(root).as_posix(),
        "sha256": digest,
        "source_run_id": str(run.get("run_id", "")),
        "source_status": status,
        "source_baseline_status": SOURCE_BASELINE_STATUS_BY_RUN_STATUS[status],
    }


def _run_view(
    project_dir: Path,
    phase_slug: str,
    run: Mapping[str, Any] | None,
    number: int | None = None,
) -> dict[str, Any] | None:
    if run is None:
        return None
    run_id = str(run.get("run_id", ""))
    requested = int(run.get("rounds_requested", 1) or 1)
    completed = _completed_count(run)
    current = next(
        (
            item
            for item in run.get("rounds", [])
            if item.get("started") and not item.get("completed")
        ),
        None,
    )
    log_path = project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.log"
    status = str(run.get("status", "pending"))
    started_at = run.get("started") or run.get("created_at")
    completed_at = run.get("completed") or run.get("ended_at")
    decision_note = run.get("decision_note", "")
    summary_available = _summary_available(project_dir, run, phase_slug)
    integrity_report = (
        project_state.run_integrity_report(project_dir, phase_slug, run_id)
        if run.get("final_summary")
        else {"ok": True, "reason": ""}
    )
    decision_record = run.get("decision_record")
    baseline_acknowledgement = run.get("approval_baseline_acknowledgement")
    approval_kind = str(run.get("approval_kind", "")).strip()
    if not approval_kind and isinstance(baseline_acknowledgement, Mapping):
        approval_kind = str(
            baseline_acknowledgement.get("approval_kind", "")
        ).strip()
    scientific_decision = (
        dict(decision_record.get("data", {}))
        if isinstance(decision_record, Mapping)
        and isinstance(decision_record.get("data"), Mapping)
        else None
    )
    action_labels = {
        "approve": "Approve",
        "approve_with_limitations": "Approve with limitations",
        "request_revision": "Request revision",
        "rerun": "Rerun",
        "defer": "Defer the decision",
    }
    post_review_target = _phase_six_post_review_target(
        project_dir, phase_slug, run, integrity_report
    )
    manifest = _sealed_run_manifest(run, phase_slug)
    source_descriptor = _source_descriptor(project_dir, phase_slug, manifest)
    method_selection = (
        dict(manifest.get("method_selection", {}))
        if isinstance(manifest, Mapping)
        and isinstance(manifest.get("method_selection"), Mapping)
        else None
    )
    protocol_checkpoint_required = bool(
        phase_slug == "04-numerical-validation"
        and manifest
        and isinstance(manifest.get("protocol_checkpoint"), Mapping)
    )
    frozen_phase = manifest.get("phase", {}) if manifest else {}
    has_frozen_plan = bool(
        manifest
        and isinstance(frozen_phase, Mapping)
        and str(frozen_phase.get("slug", "")) == phase_slug
    )
    plan_stages = [
        dict(stage)
        for stage in frozen_phase.get("stages", [])
        if isinstance(stage, Mapping)
    ]
    plan_members = [
        str(member.get("role", "") if isinstance(member, Mapping) else member)
        for member in frozen_phase.get("members", [])
        if str(member.get("role", "") if isinstance(member, Mapping) else member)
    ]
    plan_pattern = str(frozen_phase.get("pattern", "")) if has_frozen_plan else ""
    plan_folder = str(frozen_phase.get("folder", "")) if has_frozen_plan else ""
    run_plan = str(frozen_phase.get("run_plan", ""))
    if phase_slug == "03-theoretical-justification" and not run_plan:
        if frozen_phase.get("audit_only"):
            run_plan = "audit_only"
        elif frozen_phase.get("proof_audit"):
            run_plan = "standard_with_audit"
        elif has_frozen_plan:
            run_plan = "standard"

    if frozen_phase.get("review_only"):
        plan_variant = "Review only: exact selected manuscript"
    elif frozen_phase.get("audit_only"):
        plan_variant = "Independent audit of an existing sealed theory artifact"
    elif frozen_phase.get("proof_audit"):
        plan_variant = "Standard theory plus independent proof audit"
    elif phase_slug == "03-theoretical-justification" and has_frozen_plan:
        plan_variant = "Standard theory"
    elif phase_slug == "06-paper-writing" and plan_stages:
        plan_variant = "Full manuscript writing and independent review"
    elif has_frozen_plan:
        plan_variant = "Standard phase plan"
    else:
        plan_variant = None

    # Display status: when a run is "failed" but real artifacts exist on disk
    # (summary HTML written by the lead), show "partial" instead of "failed".
    # The lead did the work but didn't formally submit it (round-tracking gap,
    # crash after writing files, etc.). Underlying status stays "failed" so
    # state logic is unaffected; only the user-facing label softens.
    if status == "failed" and summary_available:
        display_status = "partial"
    else:
        display_status = status

    return {
        "id": run_id,
        "run_id": run_id,
        "number": number,
        "status": status,
        "display_status": display_status,
        "status_label": (
            "Completed (partial)" if display_status == "partial"
            else status.replace("_", " ").title()
        ),
        "mode": run.get("mode", ""),
        "rounds_requested": requested,
        "requested_count": requested,
        "rounds_completed": completed,
        "completed_count": completed,
        "progress_percent": min(100, round((completed / requested) * 100)) if requested else 0,
        "current_round": current.get("n") if current else None,
        "current_round_detail": current,
        "rounds": list(run.get("rounds", [])),
        "started": started_at,
        "started_at": started_at,
        "submitted_at": run.get("submitted_at"),
        "completed": completed_at,
        "completed_at": completed_at,
        "ended_at": run.get("ended_at"),
        "decision_at": run.get("decision_at"),
        "decision_by": run.get("decision_by"),
        "decision_note": decision_note,
        "approved_at": run.get("decision_at") if status == "approved" else None,
        "approval_note": decision_note if status == "approved" else "",
        "revision_feedback": decision_note if status == "revision_requested" else "",
        "feedback": run.get("user_feedback", ""),
        "user_feedback": run.get("user_feedback", ""),
        "summary_path": _discover_summary_path(project_dir, run, phase_slug),
        "summary_available": summary_available,
        "summary_integrity_error": bool(run.get("final_summary") and not summary_available),
        "integrity_error": not bool(integrity_report.get("ok")),
        "integrity_error_detail": str(integrity_report.get("reason", "")),
        "scientific_decision": scientific_decision,
        "scientific_outcome": (
            scientific_decision.get("scientific_outcome")
            if scientific_decision
            else None
        ),
        "conclusion": (
            _truncate_conclusion(scientific_decision.get("recommendation", ""))
            if scientific_decision and scientific_decision.get("recommendation")
            else ""
        ),
        "recommended_user_action": (
            scientific_decision.get("recommended_user_action")
            if scientific_decision
            else None
        ),
        "recommended_user_action_label": (
            action_labels.get(
                str(scientific_decision.get("recommended_user_action", "")),
                "Not recorded",
            )
            if scientific_decision
            else "Not recorded"
        ),
        "decision_record_version": (
            str(decision_record.get("sha256", ""))
            if isinstance(decision_record, Mapping)
            else ""
        ),
        "post_review_target": post_review_target,
        "source_descriptor": source_descriptor,
        "method_selection": method_selection,
        "plan_stages": plan_stages,
        "plan_variant": plan_variant,
        "frozen_plan": {
            "available": has_frozen_plan,
            "variant": plan_variant,
            "pattern": plan_pattern,
            "folder": plan_folder,
            "members": plan_members,
            "stages": plan_stages,
            "run_plan": run_plan or None,
        },
        "rerun_config": None,
        "log_available": log_path.is_file(),
        "error": run.get("error"),
        "cancel_reason": run.get("cancel_reason"),
        "cleanup_outcome": run.get("cleanup_outcome"),
        "cleanup_reason": run.get("cleanup_reason"),
        "cleanup_started_at": run.get("cleanup_started_at"),
        "cleanup_completed_at": run.get("cleanup_completed_at"),
        "cleanup_recovery_note": run.get("cleanup_recovery_note"),
        "protocol_checkpoint": (
            dict(run["protocol_checkpoint"])
            if isinstance(run.get("protocol_checkpoint"), Mapping)
            else None
        ),
        "protocol_checkpoint_required": protocol_checkpoint_required,
        "override_metadata": run.get("override_metadata"),
        "prerequisite_snapshot": run.get("prerequisite_snapshot"),
        "context_inputs": list(run.get("context_inputs", [])),
        "approval_context_acknowledgement": run.get("approval_context_acknowledgement"),
        "approval_baseline_acknowledgement": run.get(
            "approval_baseline_acknowledgement"
        ),
        "approval_kind": approval_kind or None,
        "approval_kind_label": (
            "Approve with limitations"
            if approval_kind == "approve_with_limitations"
            else "Approve"
            if approval_kind == "approve"
            else None
        ),
        "is_active": status in project_state.ACTIVE_RUN_STATUSES,
        "needs_review": status == "awaiting_review",
        "stages_requested": requested,
        "stages_completed": completed,
    }


def _phase_runs(
    project_dir: Path,
    phase_slug: str,
    phase_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        _run_view(project_dir, phase_slug, run, index + 1)
        for index, run in enumerate(phase_state.get("runs", []))
    ]


def _rounds_policy(phase: Mapping[str, Any]) -> dict[str, Any]:
    raw = phase.get("rounds", {})
    stages = list(phase.get("stages", []))
    if phase.get("pattern") == "sequential":
        count = len(stages)
        return {
            "min": count,
            "default": count,
            "max": count,
            "fixed": True,
            "options": [count],
            "label": f"{count} fixed stages",
        }
    minimum = int(raw.get("min", 1))
    default = int(raw.get("default", minimum))
    maximum = int(raw.get("max", default))
    return {
        "min": minimum,
        "default": default,
        "max": maximum,
        "fixed": minimum == maximum,
        "options": list(range(minimum, maximum + 1)),
        "label": (
            f"{minimum} round" if minimum == maximum == 1
            else f"{minimum} to {maximum} rounds"
        ),
    }


def _prerequisite_view(
    report: Mapping[str, Any], phases: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    names = {
        str(phase["slug"]): str(phase.get("name", phase["slug"]))
        for phase in phases
    }
    requirements = []
    for item in report.get("requirements", []):
        entry = dict(item)
        entry["name"] = names.get(str(item.get("phase")), str(item.get("phase")))
        requirements.append(entry)
    blockers = [str(item) for item in report.get("blockers", [])]
    missing = [entry for entry in requirements if not entry.get("satisfied")]
    missing_names = [entry["name"] for entry in missing]
    satisfied = bool(report.get("satisfied", not blockers))
    if satisfied and requirements:
        message = "All recommended prerequisite results are approved and current."
    elif satisfied:
        message = "This phase has no prerequisites and can be run at any time."
    else:
        message = "Missing or stale context: " + ", ".join(missing_names)
    return {
        **dict(report),
        "ok": satisfied,
        "satisfied": satisfied,
        "blockers": blockers,
        "missing": missing,
        "missing_names": missing_names,
        "requirements": requirements,
        "message": message,
    }


def _decision_label(phase_state: Mapping[str, Any], latest: Mapping[str, Any] | None) -> str:
    if latest and latest.get("status") in project_state.ACTIVE_RUN_STATUSES:
        if latest.get("status") == "stopping":
            return "Cleanup needs your attention"
        return "Agents are working"
    if phase_state.get("stale"):
        return "Approved result needs review after an upstream change"
    if latest is None:
        return "Not run yet"
    labels = {
        "starting": "Starting",
        "running": "Agents are working",
        "submitting": "Preparing the result for review",
        "stopping": "Cleanup needs your attention",
        "awaiting_review": "Your decision is needed",
        "approved": "Approved and current",
        "revision_requested": "Revision requested; ready to rerun",
        "failed": "Run failed; approved fallback preserved",
        "cancelled": "Run cancelled; ready to rerun",
        "superseded": "Superseded by an approved run",
    }
    return labels.get(str(latest.get("status")), str(latest.get("status", "Pending")))


def _decision_state(
    phase_state: Mapping[str, Any], latest: Mapping[str, Any] | None
) -> str:
    """Return the state that currently needs the user's attention."""

    if latest is not None:
        latest_status = str(latest.get("status", "pending"))
        if latest_status in project_state.ACTIVE_RUN_STATUSES:
            return latest_status
        if str(latest.get("run_id", "")) != str(phase_state.get("approved_run", "")):
            # When the latest run failed but artifacts exist, surface "partial"
            # so the phase row doesn't alarm with "failed" when work is usable.
            if latest.get("display_status") == "partial":
                return "partial"
            return latest_status
    if phase_state.get("stale"):
        return "stale"
    return str(phase_state.get("status", "pending"))


def prepare_phase_data(
    project_dir: Path,
    project_id: int,
    phase_cfg: Mapping[str, Any],
    phases_cfg: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one phase's controls, decision state, and immutable history."""

    project_dir = Path(project_dir).resolve()
    phase_slug = str(phase_cfg["slug"])
    recovery_only = bool(phase_cfg.get("recovery_only"))
    state = project_state.load(project_dir)
    approved_method_selection = None
    method_phase = state.get("phases", {}).get(
        project_state.METHOD_DEVELOPMENT_PHASE, {}
    )
    method_run_id = str(method_phase.get("approved_run") or "").strip()
    method_run = next(
        (
            candidate
            for candidate in method_phase.get("runs", [])
            if isinstance(candidate, Mapping)
            and str(candidate.get("run_id", "")) == method_run_id
        ),
        None,
    )
    if (
        method_run_id
        and isinstance(method_run, Mapping)
        and not bool(method_phase.get("stale"))
    ):
        decision = method_run.get("decision_record")
        selected = (
            decision.get("data", {}).get("selected_scientific_object")
            if isinstance(decision, Mapping)
            and isinstance(decision.get("data"), Mapping)
            else None
        )
        try:
            integrity_ok = bool(
                project_state.run_integrity_report(
                    project_dir,
                    project_state.METHOD_DEVELOPMENT_PHASE,
                    method_run_id,
                ).get("ok")
            )
        except (KeyError, OSError, project_state.ProjectStateError):
            integrity_ok = False
        if (
            method_run.get("status") == "approved"
            and integrity_ok
            and isinstance(selected, Mapping)
            and selected.get("kind") == "method"
            and str(selected.get("stable_id", "")).strip()
            and str(selected.get("version", "")).strip()
        ):
            approved_method_selection = {
                "kind": "method",
                "stable_id": str(selected["stable_id"]),
                "version": str(selected["version"]),
                "source_run_id": method_run_id,
                "decision_sha256": str(decision.get("sha256", "")),
            }
    phase_state = state.get("phases", {}).get(
        phase_slug,
        {"status": "pending", "runs": [], "approved_run": None, "stale": False},
    )
    run_views = _phase_runs(project_dir, phase_slug, phase_state)
    by_id = {item["run_id"]: item for item in run_views}
    latest = by_id.get(str(phase_state.get("latest_run")))
    if latest is None and run_views:
        latest = run_views[-1]
    approved = by_id.get(str(phase_state.get("approved_run")))
    active_marker = state.get("active_run")
    active_anywhere = bool(active_marker)
    active_conflict = bool(active_marker and active_marker.get("conflict"))
    conflicting_active_runs = [
        dict(item)
        for item in (active_marker.get("runs", []) if active_conflict else [])
        if isinstance(item, Mapping)
    ]
    active_reference = None
    if active_conflict:
        active_reference = next(
            (
                item
                for item in conflicting_active_runs
                if item.get("phase_slug") == phase_slug
            ),
            None,
        )
    elif active_marker and active_marker.get("phase_slug") == phase_slug:
        active_reference = active_marker
    active_run = (
        by_id.get(str(active_reference.get("run_id"))) if active_reference else None
    )
    active_here = bool(active_run)
    awaiting_decision = next(
        (
            item
            for item in reversed(run_views)
            if item.get("status") == "awaiting_review"
        ),
        None,
    )
    displayed_latest = active_run if active_here else (awaiting_decision or latest)
    if (
        displayed_latest
        and not active_here
        and phase_slug in {
            "03-theoretical-justification",
            "06-paper-writing",
        }
        and displayed_latest.get("frozen_plan", {}).get("available")
    ):
        try:
            displayed_latest["rerun_config"] = exact_rerun_options(
                project_dir, phase_slug, displayed_latest["run_id"]
            )
        except (
            KeyError,
            OSError,
            ValueError,
            LaunchError,
            project_state.ProjectStateError,
        ):
            displayed_latest["rerun_config"] = None
    raw_report = project_state.prerequisite_report(
        project_dir, phase_slug, _dependencies(phases_cfg)
    )
    report = _prerequisite_view(raw_report, phases_cfg)
    approval_report = None
    approval_subject = displayed_latest
    if approval_subject and (
        approval_subject.get("status") == "awaiting_review"
        or approval_subject.get("status") in project_state.ACTIVE_RUN_STATUSES
    ):
        approval_report = project_state.approval_context_report(
            project_dir,
            phase_slug,
            approval_subject["run_id"],
            _dependencies(phases_cfg),
        )
    policy = _rounds_policy(phase_cfg)
    stages = []
    completed_for_stages = active_run["rounds_completed"] if active_run else 0
    current_stage = active_run["current_round"] if active_run else None
    stage_source = (
        active_run.get("plan_stages", [])
        if active_run and active_run.get("plan_stages")
        else phase_cfg.get("stages", [])
    )
    for index, raw_stage in enumerate(stage_source, 1):
        stage = dict(raw_stage)
        if index <= completed_for_stages:
            stage["status"] = "completed"
        elif current_stage == index:
            stage["status"] = "running"
        else:
            stage["status"] = "pending"
        stages.append(stage)

    baseline_integrity_error = bool(approved and approved.get("integrity_error"))
    decision_state = _decision_state(phase_state, displayed_latest)
    decision_label = _decision_label(phase_state, displayed_latest)
    if baseline_integrity_error and (
        displayed_latest is None
        or displayed_latest.get("run_id") == approved.get("run_id")
    ):
        decision_state = "stale"
        decision_label = "Approved evidence is missing or changed"
    stale_reason = phase_state.get("stale_reason")
    if baseline_integrity_error and not stale_reason:
        stale_reason = (
            "Approved evidence is missing or changed, so it cannot be treated as "
            "a current baseline. Restore the recorded file or approve a replacement run."
        )

    configured_members = [
        str(member.get("role", "") if isinstance(member, Mapping) else member)
        for member in phase_cfg.get("members", [])
        if str(member.get("role", "") if isinstance(member, Mapping) else member)
    ]
    plan_view = {
        "frozen": False,
        "variant": (
            "Standard theory"
            if phase_slug == "03-theoretical-justification"
            else "Full manuscript writing and independent review"
            if phase_slug == "06-paper-writing"
            else "Standard phase plan"
        ),
        "pattern": str(phase_cfg.get("pattern", "")),
        "folder": str(phase_cfg.get("folder", "")),
        "members": configured_members,
    }
    if active_run and active_run.get("frozen_plan", {}).get("available"):
        frozen_plan = active_run["frozen_plan"]
        plan_view = {
            "frozen": True,
            "variant": frozen_plan.get("variant"),
            "pattern": frozen_plan.get("pattern"),
            "folder": frozen_plan.get("folder"),
            "members": list(frozen_plan.get("members", [])),
        }

    return {
        "project_id": project_id,
        "phase_cfg": dict(phase_cfg),
        "phase_slug": phase_slug,
        "recovery_only": recovery_only,
        "recovery_source": phase_cfg.get("recovery_source"),
        "state": dict(phase_state),
        "status": (
            active_run.get("status", "running")
            if active_here
            else phase_state.get("status", "pending")
        ),
        "decision_state": decision_state,
        "decision_label": decision_label,
        "stale": bool(phase_state.get("stale")) or baseline_integrity_error,
        "stale_reason": stale_reason,
        "latest_run": displayed_latest,
        "approved_run": approved,
        "baseline_integrity_error": baseline_integrity_error,
        "active_run": active_run,
        "project_active_run": dict(active_marker) if active_marker else None,
        "run_active": active_here,
        "run_status": active_run,
        "active_conflict": active_conflict,
        "conflicting_active_runs": conflicting_active_runs,
        "active_elsewhere": (
            dict(active_marker) if active_anywhere and not active_here else False
        ),
        "can_start": not active_anywhere and not recovery_only,
        "launch_available": not active_anywhere and not recovery_only,
        "can_run": report["satisfied"],
        "prerequisite_report": report,
        "prerequisite_report_version": decision_report_version(
            "prerequisite", raw_report
        ),
        "approved_method_selection": approved_method_selection,
        "approval_context_report": approval_report,
        "approval_context_report_version": (
            decision_report_version("approval_context", approval_report)
            if approval_report
            else None
        ),
        "gating_reason": "" if report["satisfied"] else report["message"],
        "rounds_policy": policy,
        "round_options": policy["options"],
        "stages": stages,
        "plan_view": plan_view,
        "run_history": list(reversed(run_views)),
        "summary_path": (
            displayed_latest.get("summary_path") if displayed_latest else None
        ),
    }


def prepare_overview_data(
    project_dir: Path,
    phases_cfg: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build non-linear decision cards for the project overview."""

    project_dir = Path(project_dir).resolve()
    state = project_state.load(project_dir)
    phases_state = state.get("phases", {})
    active = state.get("active_run")
    active_conflict = bool(active and active.get("conflict"))
    conflicting_active_runs = [
        dict(item)
        for item in (active.get("runs", []) if active_conflict else [])
        if isinstance(item, Mapping)
    ]
    dependencies = _dependencies(phases_cfg)
    cards: list[dict[str, Any]] = []
    # Pre-compute global ordinal rank for each run (by start time across ALL phases)
    # This gives every run its own horizontal slot — no clustering regardless of time gaps.
    from datetime import datetime
    def _parse_iso(ts: str | None):
        if not ts:
            return None
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    _all_runs_for_rank: list[tuple[str, datetime]] = []
    for phase_cfg in phases_cfg:
        phase_slug = str(phase_cfg["slug"])
        phase_state = phases_state.get(phase_slug, {})
        for r in phase_state.get("runs", []):
            if isinstance(r, Mapping):
                rid = str(r.get("run_id", ""))
                ts = _parse_iso(r.get("started"))
                if rid and ts:
                    _all_runs_for_rank.append((rid, ts))
    _all_runs_for_rank.sort(key=lambda x: x[1])
    _rank_by_id: dict[str, int] = {rid: i for i, (rid, _) in enumerate(_all_runs_for_rank)}
    _total_ranked = max(len(_all_runs_for_rank), 1)
    for number, phase_cfg in enumerate(phases_cfg, 1):
        phase_slug = str(phase_cfg["slug"])
        phase_state = phases_state.get(
            phase_slug,
            {"status": "pending", "runs": [], "approved_run": None, "stale": False},
        )
        views = _phase_runs(project_dir, phase_slug, phase_state)
        by_id = {item["run_id"]: item for item in views}
        latest = by_id.get(str(phase_state.get("latest_run")))
        if latest is None and views:
            latest = views[-1]
        approved = by_id.get(str(phase_state.get("approved_run")))
        report = _prerequisite_view(
            project_state.prerequisite_report(
                project_dir, phase_slug, dependencies
            ),
            phases_cfg,
        )
        active_reference = None
        if active_conflict:
            active_reference = next(
                (
                    item
                    for item in conflicting_active_runs
                    if item.get("phase_slug") == phase_slug
                ),
                None,
            )
        elif active and active.get("phase_slug") == phase_slug:
            active_reference = active
        active_view = (
            by_id.get(str(active_reference.get("run_id")))
            if active_reference
            else None
        )
        is_active = bool(active_view)
        awaiting_decision = next(
            (
                item
                for item in reversed(views)
                if item.get("status") == "awaiting_review"
            ),
            None,
        )
        displayed_latest = active_view if is_active else (awaiting_decision or latest)
        baseline_integrity_error = bool(approved and approved.get("integrity_error"))
        decision_state = _decision_state(phase_state, displayed_latest)
        decision_label = _decision_label(phase_state, displayed_latest)
        if baseline_integrity_error and (
            displayed_latest is None
            or displayed_latest.get("run_id") == approved.get("run_id")
        ):
            decision_state = "stale"
            decision_label = "Approved evidence is missing or changed"
        stale_reason = phase_state.get("stale_reason")
        if baseline_integrity_error and not stale_reason:
            stale_reason = "Approved evidence is missing or changed."
        cards.append({
            "number": number,
            "slug": phase_slug,
            "name": phase_cfg.get("name", phase_slug),
            "description": phase_cfg.get("description", ""),
            "pattern": phase_cfg.get("pattern", ""),
            "folder": phase_cfg.get("folder", ""),
            "members": list(phase_cfg.get("members", [])),
            "gated_by": list(phase_cfg.get("gated_by", [])),
            "recovery_only": bool(phase_cfg.get("recovery_only")),
            "recovery_source": phase_cfg.get("recovery_source"),
            "status": (
                active_view.get("status", "running")
                if is_active
                else phase_state.get("status", "pending")
            ),
            "decision_state": decision_state,
            "decision_label": decision_label,
            "run_count": len(views),
            "latest_run": displayed_latest,
            "approved_run": approved,
            "baseline_integrity_error": baseline_integrity_error,
            "is_active": is_active,
            "can_start": not bool(active) and not bool(phase_cfg.get("recovery_only")),
            "can_run": report["satisfied"],
            "prerequisite_report": report,
            "stale": bool(phase_state.get("stale")) or baseline_integrity_error,
            "stale_reason": stale_reason,
            "rounds_policy": _rounds_policy(phase_cfg),
            "last_run_started": (
                displayed_latest.get("started") if displayed_latest else None
            ),
            "last_run_completed": (
                displayed_latest.get("completed") if displayed_latest else None
            ),
            "last_run_rounds": (
                f"{displayed_latest['rounds_completed']}/{displayed_latest['rounds_requested']}"
                if displayed_latest
                else None
            ),
            "summary_path": (
                displayed_latest.get("summary_path") if displayed_latest else None
            ),
            "timeline_runs": [
                {
                    "run_id": v.get("run_id", ""),
                    "status": v.get("status", ""),
                    "display_status": v.get("display_status", v.get("status", "")),
                    "summary_available": bool(v.get("summary_available")),
                    "started": v.get("started"),
                    "completed": v.get("completed"),
                    "number": v.get("number") or v.get("run_number", ""),
                    "scientific_outcome": v.get("scientific_outcome", ""),
                    # Ordinal rank positioning: each run gets its own slot based on
                    # global temporal order. 5%–95% range keeps dots off the edges.
                    "left_pct": round(
                        5 + (_rank_by_id.get(str(v.get("run_id", "")), 0) / max(_total_ranked - 1, 1)) * 90,
                        1,
                    ),
                }
                for v in views
                if v.get("started")
            ],
        })
    return cards
