#!/usr/bin/env python3

"""Launch and supervise explicit, user-directed Research Hub phase runs.

The launcher prepares one run and delegates its internal work to the configured
research lead. It never starts another phase and it never approves a result.
The lead's final action submits an immutable summary for user review.

This module is the orchestration facade. Implementation details live in
focused sibling modules (launch_common, launch_process, launch_manifest,
launch_plans, launch_prompts, launch_dispatch, launch_supervision); every
public and historically private name is re-exported here so existing callers
and tests keep a single import location.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence



from core import launch_common
from core import project_state
from core import profile_skills
from core import launch_dispatch
from core import launch_manifest
from core import launch_plans
from core import launch_process
from core import launch_prompts
from core import launch_supervision

# Re-exports: launch_run is the single import facade for callers and tests.
# Every name below is defined in a sibling module and re-exported here so
# that `from core.launch_run import X` works without callers needing to know
# which focused module owns it.
from core.launch_common import (
    ELIGIBLE_SOURCE_STATUSES,
    LaunchError,
    MAX_DIRECTIVE_BYTES,
    MAX_EMBEDDED_SOUL_BYTES,
    MAX_LEAD_PROMPT_BYTES,
    MAX_REVIEW_BUNDLE_BYTES,
    MAX_REVIEW_MANUSCRIPT_BYTES,
    MAX_REVIEW_OUTPUT_BYTES,
    MAX_SOURCE_DECISION_BYTES,
    MAX_SOURCE_SUMMARY_BYTES,
    MAX_TASK_BRIEF_BYTES,
    DRAFT_ASSEMBLY_PHASE,
    PAPER_REVIEWER_ROLE,
    PAPER_REVIEWER_SKILL,
    PAPER_WRITING_PHASE,
    PAPER_WRITING_SKILL,
    REVIEW_BUNDLE_SCHEMA_VERSION,
    SOULS_DIR,
    SOURCE_BASELINE_SCHEMA_VERSION,
    SOURCE_BASELINE_STATUS_BY_RUN_STATUS,
    TEAM_DIR,
    IDEA_EVALUATION_PHASE,
    THEORY_PLAN_AUDIT_ONLY,
    THEORY_PLAN_STANDARD,
    THEORY_PLAN_STANDARD_WITH_AUDIT,
    RUN_MODE_PRELIMINARY,
    RUN_MODE_COMPREHENSIVE,
    RUN_MODE_ASSEMBLY,
    RUN_MODE_REVIEW_REVISION,
    RUN_MODES,
    PAPER_RUN_MODES,
    DRAFT_ASSEMBLY_PHASE,
    _ProcessOutputLimitExceeded,
    _bounded_bytes,
    _contained_file_destination,
    _ensure_contained_directory,
    _guard_command_length,
    _is_sha256_digest,
    _metadata_is_link_or_reparse,
    _parse_timestamp,
    _path_uses_symlink_below,
    _read_utf8_bounded,
    _run_index,
    _sha256_file,
    _shell_join,
    _write_bytes_atomic,
    _write_text_atomic,
    prompt_path,
    run_context_dir,
    run_log_path,
    run_manifest_path,
)
from core.launch_dispatch import (
    _complete_round_checked,
    _dispatch_task,
    _planned_output,
    _planned_roles,
    _planned_task_output,
    _show_task,
    _task_id_from_json,
    _task_payload,
    _verify_completed_round_artifacts,
    _verify_task_briefs,
)
from core.launch_manifest import (
    MANIFEST_SCHEMA_VERSION,
    _frozen_snapshot_text,
    _manifest_declares_protocol_checkpoint,
    _manifest_hermes_root,
    _manifest_schema_version,
    _method_identity,
    _read_manifest,
    _snapshot_leaf,
    _validated_manifest_method_selection,
    _validate_manifest_snapshot_schema,
    _validate_recommended_skills_snapshot,
    _verified_preloaded_skill_names,
    _verify_frozen_inputs,
    phase_requires_method_binding,
)
from core.launch_plans import (
    _configured_proof_audit,
    _copy_paper_review_source,
    _dependencies,
    _freeze_source_baseline,
    _freeze_theory_audit_source,
    _launch_instruction_fingerprint,
    _load_hub_config,
    _method_selection_for_run,
    _paper_manuscript_paths,
    _phase_config,
    _phase_for_theory_plan,
    _phase_for_run_mode,
    _phase_slugs,
    _phase_with_proof_audit,
    _resolve_paper_review_source,
    _resolve_theory_audit_source,
    _role_profiles,
    _round_count,
    _should_preload_recommended_skill,
    _recommended_skill_status_record,
    _recommended_skills_snapshot,
    _source_baseline_from_run,
    _source_baseline_status,
    _source_file_payload,
    _verified_frozen_source_baseline,
    _verified_frozen_theory_audit_source,
    exact_rerun_options,
    launch_plan_version,
    paper_review_only_phase,
    phase_supports_theory_plans,
    phase_supports_run_modes,
    theory_audit_source_options,
    _review_revision_gate_satisfied,
)
from core.launch_process import (
    MAX_COMMAND_OUTPUT_BYTES,
    MAX_PROCESS_CONTROL_OUTPUT_BYTES,
    MAX_RUN_LOG_BYTES,
    PROCESS_OUTPUT_CHUNK_BYTES,
    PROCESS_READER_JOIN_SECONDS,
    PROCESS_TREE_TERMINATION_SECONDS,
    RUN_LOG_LIMIT_MARKER,
    _archive_external_task,
    _assign_windows_kill_job,
    _board_slugs,
    _close_windows_job,
    _flush_worker_log_streams,
    _hermes_environment,
    _open_new_run_log,
    _pid_identity_status,
    _pid_is_alive,
    _process_identity,
    _run_command,
    _run_logged_command,
    _run_log_descriptor_metadata,
    _run_process_with_bounded_output,
    _stop_external_tasks,
    _task_list,
    _terminate_pid_tree,
    _terminate_windows_job,
    _terminate_windows_process_tree,
    _truncate_run_log,
    _verified_run_log_descriptor,
    _worker_log_descriptor,
    _write_worker_output,
)
from core.launch_prompts import (
    _ancestor_slugs,
    _build_lead_prompt,
    _descendant_slugs,
    _directive_text,
    _import_review_bundle_output,
    _is_proof_audit_stage,
    _method_selection_prompt_block,
    _paper_review_manuscript_block,
    _paper_review_manuscript_snapshot,
    _paper_reviewer_substage,
    _phase_four_protocol_checkpoint_block,
    _prepare_review_bundle,
    _proof_audit_material_block,
    _review_bundle_root,
    _review_bundle_sources,
    _review_source_payload,
    _reviewer_task_text,
    _snapshot_run_inputs,
    _source_baseline_lead_block,
    _task_brief_path,
    _task_instructions,
    _trusted_context,
    _verified_review_bundle,
)
from core.launch_supervision import (
    _cleanup_run_execution,
    cancel_active_run,
    get_run_status,
    reconcile_active_run,
    retry_run_cleanup,
)


def _ensure_board(
    hermes: str,
    board_slug: str,
    display_name: str,
    *,
    hermes_root: str | os.PathLike[str] | None = None,
) -> None:
    """Create the project board, while treating CLI failures as real failures."""

    environment = launch_process._hermes_environment(hermes_root)
    listed = launch_process._run_command(
        [hermes, "kanban", "boards", "list", "--json"],
        environment=environment,
    )
    if listed.returncode != 0:
        detail = (listed.stderr or listed.stdout).strip()
        raise launch_common.LaunchError(f"Hermes could not list kanban boards: {detail or 'unknown error'}")
    try:
        slugs = launch_process._board_slugs(json.loads(listed.stdout or "[]"))
    except json.JSONDecodeError as exc:
        raise launch_common.LaunchError("Hermes returned invalid JSON while listing kanban boards") from exc
    if board_slug in slugs:
        return

    created = launch_process._run_command(
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
        raise launch_common.LaunchError(f"Hermes could not create kanban board {board_slug}: {detail or 'unknown error'}")


def _preflight(
    project_dir: Path,
    phase: Mapping[str, Any],
    profiles: Mapping[str, str],
    config: Mapping[str, Any],
    *,
    hermes_root: str | os.PathLike[str] | None = None,
) -> tuple[str, Path]:
    if not project_dir.is_dir():
        raise launch_common.LaunchError(f"Project directory does not exist: {project_dir}")
    if not (project_dir / "setting.md").is_file():
        raise launch_common.LaunchError("Project setting.md is missing")

    required_roles = set(str(role) for role in phase.get("members", []))
    required_roles.add("research_lead")
    missing_profiles = sorted(role for role in required_roles if not profiles.get(role))
    if missing_profiles:
        raise launch_common.LaunchError("No Hermes profile is mapped for: " + ", ".join(missing_profiles))

    if not bool(config.get("hub", {}).get("allow_unattended_tools", False)):
        raise launch_common.LaunchError(
            "Background web runs require hub.allow_unattended_tools: true because no "
            "interactive terminal is available to answer Hermes tool approvals."
        )

    phase_dir = launch_common.PHASES_DIR / str(phase["slug"])
    required_files = [phase_dir / "_phase.md", phase_dir / "_lead.md"]
    required_files.extend(phase_dir / f"{role}.md" for role in required_roles)
    missing_files = [str(path) for path in required_files if not path.is_file()]
    if missing_files:
        raise launch_common.LaunchError("Required playbook files are missing: " + ", ".join(missing_files))
    required_souls = [launch_common.SOULS_DIR / f"{role}.md" for role in sorted(required_roles)]
    missing_souls = [str(path) for path in required_souls if not path.is_file()]
    if missing_souls:
        raise launch_common.LaunchError("Required role soul files are missing: " + ", ".join(missing_souls))

    hermes = shutil.which("hermes")
    if not hermes:
        raise launch_common.LaunchError(
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
        raise launch_common.LaunchError("Hermes profile locations could not be resolved safely") from exc
    if missing_on_disk:
        raise launch_common.LaunchError(
            "Configured Hermes profiles do not exist: " + ", ".join(missing_on_disk)
        )
    return hermes, resolved_hermes_root


def _workspace_board_slug(project_dir: Path, project_id: int) -> str:
    workspace = project_dir.parent.parent.resolve()
    workspace_id = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:8]
    return f"rhub-{workspace_id}-p{project_id}"


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
    run_mode: str = "",
    run_specific_method_id: str = "",
    run_specific_method_version: str = "",
    expected_phase_plan_version: str = "",
    expected_workspace_path: str = "",
    expected_project_directory_name: str = "",
    expected_project_path: str = "",
    include_downstream: bool = False,
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
            raise launch_common.LaunchError("The expected workspace project identity is incomplete")
        requested_project = Path(project_dir).resolve(strict=False)
        current_workspace = hub.get_workspace_dir().resolve(strict=True)
        current_project_record = hub.get_project(project_id)
        current_project = hub.get_project_dir(project_id)
        if current_project_record is None or current_project is None:
            raise launch_common.LaunchError(
                "The project is no longer present in the current workspace. "
                "Reload the page before launching a run."
            )
        try:
            current_project = current_project.resolve(strict=True)
        except OSError as exc:
            raise launch_common.LaunchError(
                "The project directory is unavailable. Reload the page before "
                "launching a run."
            ) from exc
        if current_project != requested_project:
            raise launch_common.LaunchError(
                "The workspace or project changed before launch. Reload the page "
                "and confirm the requested phase again."
            )
        if all(expected_identity) and (
            str(current_workspace) != expected_workspace_path
            or str(current_project_record["directory_name"] or "")
            != expected_project_directory_name
            or str(current_project) != expected_project_path
        ):
            raise launch_common.LaunchError(
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
            run_mode=run_mode,
            run_specific_method_id=run_specific_method_id,
            run_specific_method_version=run_specific_method_version,
            expected_phase_plan_version=expected_phase_plan_version,
            include_downstream=include_downstream,
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
    run_mode: str = "",
    run_specific_method_id: str = "",
    run_specific_method_version: str = "",
    expected_phase_plan_version: str = "",
    include_downstream: bool = False,
) -> dict[str, Any]:
    """Prepare and launch exactly one user-authorized phase run."""

    project_dir = Path(project_dir).resolve()
    config = launch_plans._load_hub_config()
    configured_phase = launch_plans._phase_config(config, phase_slug)
    phase = dict(configured_phase)
    review_source: tuple[Path, str, dict[str, Any]] | None = None
    theory_audit_source: dict[str, Any] | None = None
    selected_theory_plan = str(theory_plan).strip()
    if review_target is not None:
        if phase_slug != launch_common.PAPER_WRITING_PHASE:
            raise launch_common.LaunchError("An exact manuscript review target is only valid in Phase 06")
        review_source = launch_plans._resolve_paper_review_source(
            project_dir, review_target, review_target_sha256
        )
        phase = launch_plans.paper_review_only_phase(phase)
    elif review_target_sha256:
        raise launch_common.LaunchError("A review target hash was supplied without a review target")
    if launch_plans.phase_supports_theory_plans(configured_phase):
        if not selected_theory_plan:
            selected_theory_plan = (
                launch_common.THEORY_PLAN_STANDARD_WITH_AUDIT
                if proof_audit
                else launch_common.THEORY_PLAN_STANDARD
            )
        if proof_audit and selected_theory_plan != launch_common.THEORY_PLAN_STANDARD_WITH_AUDIT:
            raise launch_common.LaunchError("Conflicting Phase 03 proof-audit plan options")
        if selected_theory_plan not in launch_common.THEORY_RUN_PLANS:
            raise launch_common.LaunchError(f"Unknown Phase 03 run plan: {selected_theory_plan!r}")
        source_id = str(proof_audit_source_run_id).strip()
        if selected_theory_plan == launch_common.THEORY_PLAN_AUDIT_ONLY:
            if not source_id:
                raise launch_common.LaunchError(
                    "An audit-only Phase 03 run requires a selected source run"
                )
            theory_audit_source = launch_plans._resolve_theory_audit_source(
                project_dir, source_id
            )
        elif source_id:
            raise launch_common.LaunchError(
                "A proof-audit source run is only valid for the audit-only plan"
            )
        phase = launch_plans._phase_for_theory_plan(phase, selected_theory_plan)
    elif proof_audit or selected_theory_plan or proof_audit_source_run_id:
        raise launch_common.LaunchError("This phase does not declare theory run plans")
    selected_run_mode = str(run_mode).strip()
    if launch_plans.phase_supports_run_modes(configured_phase):
        if not selected_run_mode:
            plans, default_mode = launch_plans._configured_run_modes(configured_phase)
            selected_run_mode = default_mode
        all_modes = launch_common.RUN_MODES | launch_common.PAPER_RUN_MODES
        if selected_run_mode not in all_modes:
            raise launch_common.LaunchError(f"Unknown run mode: {selected_run_mode!r}")
        phase = launch_plans._phase_for_run_mode(phase, selected_run_mode)
    elif selected_run_mode:
        raise launch_common.LaunchError("This phase does not declare run modes")
    try:
        hermes_root = profile_skills.resolve_hermes_root()
    except (profile_skills.ProfileSkillsError, OSError, ValueError) as exc:
        raise launch_common.LaunchError("Hermes profile locations could not be resolved safely") from exc
    plan_phase = phase if review_source is not None else configured_phase
    initial_recommended_skills = launch_plans._recommended_skills_snapshot(
        config,
        phase_slug,
        effective_phase=plan_phase,
        hermes_root=hermes_root,
    )
    current_phase_plan_version = launch_plans.launch_plan_version(
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
        raise launch_common.LaunchError(
            "The phase plan or scientific instructions changed since this page was "
            "shown. Reload the phase and review the run again."
        )
    profiles = launch_plans._role_profiles(config)
    rounds = launch_plans._round_count(phase, rounds_requested)
    hermes, hermes_root = _preflight(
        project_dir,
        phase,
        profiles,
        config,
        hermes_root=hermes_root,
    )
    dependencies = launch_plans._dependencies(config)

    state = project_state.load(project_dir)
    if not state.get("project"):
        project_state.init(
            project_dir,
            f"project-{project_id:03d}",
            project_dir.name,
            project_dir.name,
            launch_plans._phase_slugs(config),
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
        raise launch_common.LaunchError(
            "The prerequisite scientific inputs changed since this page was shown. "
            "Reload the phase and review the run again."
        )
    if reviewed_phase_plan_version and not submitted_prerequisite_version:
        raise launch_common.LaunchError(
            "The launch has no reviewed prerequisite version. Reload the phase and "
            "review the run again."
        )
    override = None
    if not report.get("satisfied"):
        reason = prerequisite_override_reason.strip()
        if not reason:
            blockers = ", ".join(report.get("blockers", []))
            raise launch_common.LaunchError(
                f"This run is missing approved, current prerequisite results from {blockers}. "
                "Review the warning and explicitly confirm the override in the web UI."
            )
        if not submitted_prerequisite_version:
            raise launch_common.LaunchError(
                "The prerequisite warning has no submitted version. Reload the phase "
                "and confirm the override again."
            )
        override = {"actor": "user", "reason": reason}

    prior_runs = project_state.get_runs(project_dir, phase_slug)
    if review_source:
        mode = "user-directed review-only rerun"
    elif selected_theory_plan == launch_common.THEORY_PLAN_AUDIT_ONLY:
        mode = "user-directed audit-only rerun"
    elif selected_theory_plan == launch_common.THEORY_PLAN_STANDARD_WITH_AUDIT:
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
    if (
        phase_slug == launch_common.DRAFT_ASSEMBLY_PHASE
        and selected_run_mode == launch_common.RUN_MODE_COMPREHENSIVE
        and run_specific_method_id
    ):
        if not launch_plans._comprehensive_gate_satisfied(
            project_dir, run_specific_method_id
        ):
            raise launch_common.LaunchError(
                "A comprehensive Phase 04 run requires a prior approved preliminary "
                "run for this method branch. Launch a preliminary run first to "
                "confirm the implementation works, then approve it before "
                "benchmarking."
            )
    if (
        phase_slug == launch_common.PAPER_WRITING_PHASE
        and selected_run_mode == launch_common.RUN_MODE_REVIEW_REVISION
        and run_specific_method_id
    ):
        if not launch_plans._review_revision_gate_satisfied(
            project_dir, run_specific_method_id
        ):
            raise launch_common.LaunchError(
                "A review-revision Phase 05 run requires a prior approved assembly "
                "run for this method branch. Launch an assembly run first to "
                "produce the manuscript, then approve it before reviewing and revising."
            )
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
        index = launch_common._run_index(project_dir, phase_slug, run_id)
        run_number = index + 1
        context_inputs = launch_prompts._trusted_context(
            project_dir, phase_slug, config,
            include_downstream=include_downstream,
        )
        project_state.set_run_context(
            project_dir, phase_slug, run_id, context_inputs
        )
        snapshots = launch_prompts._snapshot_run_inputs(
            project_dir, phase, run_id, context_inputs
        )
        method_selection = launch_plans._method_selection_for_run(
            phase,
            snapshots,
            run_specific_method_id,
            run_specific_method_version,
        )
        output_root = launch_plans._branch_aware_output_root(
            project_dir,
            str(phase.get("folder", "")),
            run_number=run_number,
            method_selection=method_selection,
        )
        launch_common._ensure_contained_directory(
            output_root, project_dir, label="run output directory"
        )
        paper_review: dict[str, Any] = {
            "kind": "full",
            "review_path": str(launch_plans._paper_manuscript_paths(output_root)["review"]),
        }
        if review_source:
            source_path, source_digest, _source_baseline = review_source
            review_path = launch_plans._paper_manuscript_paths(output_root)["review"]
            launch_plans._copy_paper_review_source(
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
        paper_paths = launch_plans._paper_manuscript_paths(output_root)
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
            if phase_slug == launch_common.PAPER_WRITING_PHASE and not review_source
            else {}
        )
        if review_source:
            paper_review["source_baseline"] = launch_plans._freeze_source_baseline(
                project_dir,
                launch_common.run_context_dir(project_dir, phase_slug, run_id)
                / "paper-review"
                / "source-baseline",
                review_source[2],
            )
        frozen_theory_audit_source = (
            launch_plans._freeze_theory_audit_source(
                project_dir, run_id, theory_audit_source
            )
            if theory_audit_source is not None
            else None
        )

        summary = launch_common._contained_file_destination(
            project_dir / "phase-summaries" / phase_slug / f"{run_id}.html",
            project_dir,
            label="run summary destination",
        )
        decision_path = launch_common._contained_file_destination(
            summary.with_suffix(".decision.json"),
            project_dir,
            label="structured decision destination",
        )
        control_root = project_state._ensure_control_directory(project_dir).resolve(
            strict=True
        )
        prompt_file = launch_common._contained_file_destination(
            launch_common.prompt_path(project_dir, phase_slug, run_id),
            control_root,
            label="run prompt destination",
        )
        log_file = launch_common._contained_file_destination(
            launch_common.run_log_path(project_dir, phase_slug, run_id),
            control_root,
            label="run log destination",
        )
        run = project_state.get_run(project_dir, phase_slug, run_id)
        prompt = launch_prompts._build_lead_prompt(
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
            run_mode=str(phase.get("run_plan", "")),
        )
        launch_common._write_text_atomic(prompt_file, prompt)
        timeout_minutes = int(config.get("hub", {}).get("run_timeout_minutes", 120))
        if timeout_minutes < 1:
            raise launch_common.LaunchError("hub.run_timeout_minutes must be a positive integer")
        recommended_skills = launch_plans._recommended_skills_snapshot(
            config,
            phase_slug,
            effective_phase=plan_phase,
            hermes_root=hermes_root,
        )
        if launch_plans.launch_plan_version(
            config,
            phase_slug,
            effective_phase=plan_phase,
            hermes_root=hermes_root,
            recommended_skills_snapshot=recommended_skills,
        ) != current_phase_plan_version:
            raise launch_common.LaunchError(
                "The phase instructions changed while the run inputs were being "
                "frozen. Reload the phase and launch again."
            )
        manifest = {
            "schema_version": launch_manifest.MANIFEST_SCHEMA_VERSION,
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
            "include_downstream": bool(include_downstream),
        }
        # Protocol checkpoint: only when explicitly declared in the phase config
        # (was hard-coded for Phase 04; now config-driven so phases can opt in)
        if configured_phase.get("protocol_checkpoint"):
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
        launch_manifest._validate_manifest_snapshot_schema(manifest)
        manifest_file = launch_common.run_manifest_path(project_dir, phase_slug, run_id)
        launch_common._write_text_atomic(
            manifest_file, json.dumps(manifest, indent=2, ensure_ascii=False)
        )
        project_state.seal_run_manifest(
            project_dir, phase_slug, run_id, manifest_file
        )
        launch_manifest._verify_frozen_inputs(project_dir, phase_slug, run_id, manifest)

        # Pre-flight: verify the worker subprocess can import the core package.
        # The worker runs with cwd=<project_workspace>, so `core` must be
        # importable via the installed package path, not the repo directory.
        # Without this check, a missing editable install produces a cryptic
        # ModuleNotFoundError inside the worker log instead of a clear error here.
        try:
            subprocess.run(
                [sys.executable, "-c", "from core import launch_common"],
                capture_output=True,
                timeout=10,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise launch_common.LaunchError(
                "The 'core' package is not importable from the worker Python. "
                "Install it with: pip install -e . (in the venv used by the service)"
            ) from exc

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
        environment = launch_process._hermes_environment(
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
        with launch_process._open_new_run_log(log_file) as log_handle:
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
            observed_identity = launch_process._process_identity(process.pid)
            if (
                current.get("process_pid") == process.pid
                and observed_identity
                and current.get("process_identity") == observed_identity
            ):
                registered = True
                break
            if current.get("status") not in project_state.ACTIVE_RUN_STATUSES:
                if current.get("status") == "failed":
                    raise launch_common.LaunchError(current.get("error") or "Run worker failed during startup")
                registered = True
                break
            if process.poll() is not None:
                raise launch_common.LaunchError("Run worker exited before completing its startup handshake")
            time.sleep(0.05)
        if not registered:
            raise launch_common.LaunchError("Run worker did not complete its startup handshake")
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
            identity = launch_process._process_identity(process.pid)
            try:
                if identity:
                    launch_process._terminate_pid_tree(process.pid, identity)
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
                launch_process._stop_external_tasks(project_dir, phase_slug, run_id)
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
        if isinstance(exc, (launch_common.LaunchError, project_state.ProjectStateError)):
            raise
        raise launch_common.LaunchError(f"Run launch failed: {exc}") from exc

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
    expected_manifest = launch_common.run_manifest_path(project_path, phase_slug, run_id).resolve()
    if Path(manifest_file).resolve() != expected_manifest:
        print("Worker manifest path does not match the run identity", file=sys.stderr)
        return 1
    manifest = launch_manifest._read_manifest(project_path, phase_slug, run_id)
    process_identity = launch_process._process_identity(os.getpid())
    if not process_identity:
        project_state.fail_run_if_active(
            project_path,
            phase_slug,
            run_id,
            "Could not establish a safe worker process identity.",
        )
        return 1
    try:
        launch_manifest._verify_frozen_inputs(project_path, phase_slug, run_id, manifest)
        prompt_file = Path(str(manifest["prompt_path"])).resolve(strict=True)
        if prompt_file != launch_common.prompt_path(project_path, phase_slug, run_id).resolve():
            raise launch_common.LaunchError("Frozen lead prompt path does not match the run identity")
        actual_hash = launch_common._sha256_file(
            prompt_file,
            max_bytes=launch_common.MAX_LEAD_PROMPT_BYTES,
            label="frozen lead prompt",
            allow_empty=False,
        )
        if actual_hash != manifest.get("prompt_sha256"):
            raise launch_common.LaunchError("The frozen lead prompt failed its integrity check")
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
        preloaded_skills = launch_manifest._verified_preloaded_skill_names(
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
        result = launch_process._run_logged_command(
            command,
            timeout=int(manifest["timeout_minutes"]) * 60,
            project_dir=project_path,
            phase_slug=phase_slug,
            run_id=run_id,
            environment=launch_process._hermes_environment(launch_manifest._manifest_hermes_root(manifest)),
        )
        return_code = int(result.returncode)
    except subprocess.TimeoutExpired:
        error = (
            f"Run exceeded the configured {manifest['timeout_minutes']}-minute timeout."
        )
        _, warnings = launch_supervision._cleanup_run_execution(
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
    except launch_common._ProcessOutputLimitExceeded as exc:
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
        _, warnings = launch_supervision._cleanup_run_execution(
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


def _run_ref(arguments: argparse.Namespace) -> str | int:
    if getattr(arguments, "run_id", None):
        return arguments.run_id
    if getattr(arguments, "run_index", None) is not None:
        return int(arguments.run_index)
    raise launch_common.LaunchError("A run ID is required")


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
    status.add_argument("--project-dir", help="Project workspace directory")
    status.add_argument("--all-projects", action="store_true",
                        help="Scan all projects in the workspace root")

    worker = commands.add_parser("worker", help=argparse.SUPPRESS)
    worker.add_argument("--project-dir", required=True)
    worker.add_argument("--phase", required=True)
    worker.add_argument("--run-id", required=True)
    worker.add_argument("--manifest", required=True)
    return parser


def _status_all_projects() -> str:
    """Summarize active and approved runs across all projects in the workspace."""
    # The workspace root is read from the hub database config. Since hub.py
    # lives outside the core package, we resolve the workspace from the
    # config.yaml in the repo root (parent of the core package directory).
    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "config.yaml"
    workspace = Path.home() / "research" / "projects"
    if config_path.is_file():
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            hub_cfg = cfg.get("hub", {})
            if hub_cfg.get("workspace_dir"):
                workspace = Path(hub_cfg["workspace_dir"]).expanduser() / "projects"
        except Exception:
            pass

    lines: list[str] = []
    active_total = 0
    for dirname in sorted(os.listdir(workspace)):
        if not dirname.startswith("project-"):
            continue
        full = workspace / dirname
        try:
            data = project_state.load(full)
        except Exception:
            continue
        name = data.get("project", {}).get("name", dirname)
        project_lines: list[str] = []
        for slug, phase in sorted(data.get("phases", {}).items()):
            if not isinstance(phase, dict):
                continue
            approved = phase.get("approved_run")
            label = slug.split("-", 1)[1] if "-" in slug else slug
            for run in phase.get("runs", []):
                if not isinstance(run, dict):
                    continue
                status = run.get("status", "?")
                rid = run.get("run_id", "?")[:12]
                if status in ("running", "awaiting_review", "staged", "stopping"):
                    active_total += 1
                    badge = "🔄" if status == "running" else "⏸️"
                    project_lines.append(f"  {badge} **{label}** — run {rid} — {status}")
                elif run.get("run_id") == approved:
                    project_lines.append(f"  ✅ **{label}** — run {rid} — approved")
        if project_lines:
            lines.append(f"## {name}")
            lines.extend(project_lines)
    if not lines:
        return "No active runs across all projects."
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    worker_log: tuple[Path, int, os.stat_result] | None = None
    exit_code = 0
    try:
        if args.command == "complete":
            reference = _run_ref(args)
            run = project_state.get_run(args.project_dir, args.phase, reference)
            manifest = launch_manifest._read_manifest(
                Path(args.project_dir).resolve(), args.phase, str(run["run_id"])
            )
            if Path(args.summary).resolve() != Path(manifest["summary_path"]).resolve():
                raise launch_common.LaunchError("Summary path does not match the immutable run manifest")
            if launch_manifest._manifest_schema_version(manifest) >= 4:
                if not args.decision_record:
                    raise launch_common.LaunchError("This run requires a structured decision record")
                if Path(args.decision_record).resolve() != Path(
                    manifest["decision_path"]
                ).resolve():
                    raise launch_common.LaunchError(
                        "Decision record path does not match the immutable run manifest"
                    )
            launch_manifest._verify_frozen_inputs(
                Path(args.project_dir).resolve(), args.phase, str(run["run_id"]), manifest
            )
            launch_dispatch._verify_completed_round_artifacts(Path(args.project_dir).resolve(), run)
            launch_dispatch._verify_task_briefs(Path(args.project_dir).resolve(), args.phase, run)
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
            manifest = launch_manifest._read_manifest(
                project_dir, args.phase, stable_id
            )
            launch_manifest._verify_frozen_inputs(
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
            manifest = launch_manifest._read_manifest(
                Path(args.project_dir).resolve(), args.phase, stable_id
            )
            agents = [item.strip() for item in args.agents.split(",") if item.strip()]
            if sorted(agents) != sorted(launch_dispatch._planned_roles(manifest, args.round)):
                raise launch_common.LaunchError("Round agents do not match the frozen run plan")
            lead_directive = (
                launch_prompts._directive_text(
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
            task_id = launch_dispatch._dispatch_task(
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
                raise launch_common.LaunchError("At least one --output is required")
            launch_dispatch._complete_round_checked(
                args.project_dir,
                args.phase,
                _run_ref(args),
                args.round,
                outputs,
            )
            print(f"Round {args.round} completed with {len(outputs)} artifacts.")
        elif args.command == "status":
            if args.all_projects:
                print(_status_all_projects())
            elif args.project_dir:
                print(json.dumps(launch_supervision.get_run_status(args.project_dir), indent=2))
            else:
                print("error: status requires --project-dir or --all-projects", file=sys.stderr)
                exit_code = 2
        elif args.command == "worker":
            log_path = launch_common.run_log_path(
                Path(args.project_dir).resolve(), args.phase, args.run_id
            )
            descriptor = launch_process._worker_log_descriptor()
            bound_metadata = launch_process._run_log_descriptor_metadata(descriptor)
            worker_log = (log_path, descriptor, bound_metadata)
            launch_process._flush_worker_log_streams()
            launch_process._verified_run_log_descriptor(
                log_path, descriptor, expected=bound_metadata
            )
            exit_code = _worker(
                args.project_dir,
                args.phase,
                args.run_id,
                args.manifest,
            )
    except (launch_common.LaunchError, project_state.ProjectStateError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        if worker_log is not None:
            log_path, descriptor, bound_metadata = worker_log
            try:
                launch_process._truncate_run_log(
                    log_path,
                    descriptor=descriptor,
                    expected=bound_metadata,
                )
            except launch_common.LaunchError:
                exit_code = 1
    return exit_code

if __name__ == "__main__":
    raise SystemExit(main())

