#!/usr/bin/env python3

"""Run helper: round tracking and Hermes task dispatch."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence



from core import launch_common
from core import project_state
from core import launch_manifest
from core import launch_process
from core import launch_prompts

import logging
log = logging.getLogger(__name__)

def _planned_roles(manifest: Mapping[str, Any], round_n: int) -> list[str]:
    phase = manifest["phase"]
    if phase.get("pattern") == "sequential":
        stages = phase.get("stages", [])
        if round_n < 1 or round_n > len(stages):
            raise launch_common.LaunchError(f"No configured sequential stage {round_n}")
        return [str(stages[round_n - 1]["role"])]
    rounds = int(manifest["rounds_requested"])
    if round_n < 1 or round_n > rounds:
        raise launch_common.LaunchError(f"Run has no configured round {round_n}")
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
        launch_manifest._manifest_declares_protocol_checkpoint(manifest)
        and launch_manifest._manifest_schema_version(manifest) >= 6
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
    """Verify completed role reports and supporting evidence before reuse."""

    root = project_dir.resolve()
    for round_ in run.get("rounds", []):
        number = int(round_.get("n", 0))
        if before_round is not None and number >= before_round:
            continue
        if not round_.get("completed"):
            continue
        outputs = [str(item) for item in round_.get("outputs", [])]
        raw_artifacts = round_.get("artifacts", [])
        if not isinstance(raw_artifacts, list) or any(
            not isinstance(item, Mapping) for item in raw_artifacts
        ):
            raise launch_common.LaunchError(
                f"Round {number} role-report artifact inventory is invalid"
            )
        artifacts = list(raw_artifacts)
        if (
            len(artifacts) != len(outputs)
            or sorted(outputs)
            != sorted(str(item.get("path", "")) for item in artifacts)
        ):
            raise launch_common.LaunchError(
                f"Round {number} role-report records do not match its outputs"
            )

        raw_supporting = round_.get("supporting_artifacts", [])
        if not isinstance(raw_supporting, list) or any(
            not isinstance(item, Mapping) for item in raw_supporting
        ):
            raise launch_common.LaunchError(
                f"Round {number} supporting artifact inventory is invalid"
            )
        supporting = list(raw_supporting)
        if len(supporting) > project_state.MAX_ROUND_SUPPORTING_FILES:
            raise launch_common.LaunchError(
                f"Round {number} contains too many supporting artifacts"
            )
        supporting_paths = [str(item.get("path", "")) for item in supporting]
        if (
            len(set(supporting_paths)) != len(supporting_paths)
            or set(supporting_paths) & set(outputs)
        ):
            raise launch_common.LaunchError(
                f"Round {number} supporting artifact paths are not distinct"
            )
        role_directories = {
            (root / output).parent.resolve(strict=False) for output in outputs
        }
        if supporting and len(role_directories) != 1:
            raise launch_common.LaunchError(
                f"Round {number} supporting artifacts have no unique round directory"
            )
        round_directory = next(iter(role_directories), None)
        supporting_size = 0

        for artifact_kind, records in (
            ("role report", artifacts),
            ("supporting artifact", supporting),
        ):
            for artifact in records:
                if artifact_kind == "supporting artifact" and set(artifact) != {
                    "path",
                    "sha256",
                    "size",
                }:
                    raise launch_common.LaunchError(
                        f"Round {number} supporting artifact record is invalid"
                    )
                raw_path = str(artifact.get("path", ""))
                raw_candidate = root / raw_path
                if launch_common._path_uses_symlink_below(raw_candidate, root):
                    raise launch_common.LaunchError(
                        f"Round {number} {artifact_kind} path uses a symbolic link: "
                        f"{raw_path}"
                    )
                try:
                    candidate = raw_candidate.resolve(strict=True)
                    candidate.relative_to(root)
                    if artifact_kind == "supporting artifact":
                        candidate.relative_to(round_directory)
                except OSError as exc:
                    raise launch_common.LaunchError(
                        f"Round {number} {artifact_kind} is missing: {raw_path}"
                    ) from exc
                except (TypeError, ValueError) as exc:
                    raise launch_common.LaunchError(
                        f"Round {number} {artifact_kind} escaped its allowed directory"
                    ) from exc
                contents = launch_common._bounded_bytes(
                    candidate,
                    label=f"round {number} {artifact_kind}",
                    max_bytes=project_state.MAX_RUN_ARTIFACT_BYTES,
                )
                try:
                    recorded_size = int(artifact.get("size", -1))
                except (TypeError, ValueError) as exc:
                    raise launch_common.LaunchError(
                        f"Round {number} {artifact_kind} has an invalid size record: "
                        f"{raw_path}"
                    ) from exc
                if (
                    len(contents) != recorded_size
                    or hashlib.sha256(contents).hexdigest()
                    != str(artifact.get("sha256", "")).lower()
                ):
                    raise launch_common.LaunchError(
                        f"Round {number} {artifact_kind} changed after completion: "
                        f"{raw_path}"
                    )
                if artifact_kind == "supporting artifact":
                    supporting_size += len(contents)
        if supporting_size > project_state.MAX_ROUND_SUPPORTING_BYTES:
            raise launch_common.LaunchError(
                f"Round {number} supporting artifacts exceed the aggregate safety limit"
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
                raise launch_common.LaunchError(f"Task {task.get('task_id', '?')} has no sealed brief")
            raw_brief = Path(str(raw_path))
            if launch_common._path_uses_symlink_below(raw_brief, control_root):
                raise launch_common.LaunchError(
                    f"Task {task.get('task_id', '?')} brief path uses a symbolic link"
                )
            try:
                brief = raw_brief.resolve(strict=True)
                brief.relative_to(control_root)
            except (OSError, ValueError) as exc:
                raise launch_common.LaunchError(
                    f"Task {task.get('task_id', '?')} brief is unavailable"
                ) from exc
            brief_digest = launch_common._sha256_file(
                brief,
                max_bytes=launch_common.MAX_TASK_BRIEF_BYTES,
                label=f"task {task.get('task_id', '?')} brief",
                allow_empty=False,
            )
            if brief_digest != expected_digest:
                raise launch_common.LaunchError(
                    f"Task {task.get('task_id', '?')} brief changed after dispatch"
                )
            if task.get("review_bundle") is not None:
                launch_prompts._verified_review_bundle(
                    project_dir,
                    task,
                    phase_slug=phase_slug,
                    run_id=str(run.get("run_id", "")),
                    round_n=int(round_.get("n", 0)),
                )


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
    manifest = launch_manifest._read_manifest(project_dir, phase_slug, run_id)
    launch_manifest._verify_frozen_inputs(project_dir, phase_slug, run_id, manifest)
    planned_roles = _planned_roles(manifest, round_n)
    if role not in planned_roles:
        raise launch_common.LaunchError(
            f"Role {role!r} is not planned for round {round_n}: {', '.join(planned_roles)}"
        )
    run = project_state.get_run(project_dir, phase_slug, run_id)
    if run.get("status") != "running":
        raise launch_common.LaunchError("Tasks can only be dispatched for a running run")
    if round_n < 1 or round_n > len(run.get("rounds", [])):
        raise launch_common.LaunchError("Record the round before dispatching its tasks")
    round_state = run["rounds"][round_n - 1]
    if set(round_state.get("agents", [])) != set(planned_roles):
        raise launch_common.LaunchError("Recorded round roles do not match the frozen run plan")
    _verify_completed_round_artifacts(project_dir, run, before_round=round_n)
    _verify_task_briefs(project_dir, phase_slug, run, round_n=round_n)
    phase_four_split = (
        launch_manifest._manifest_declares_protocol_checkpoint(manifest)
        and launch_manifest._manifest_schema_version(manifest) >= 6
        and round_n == 1
        and role == "data_scientist"
    )
    if phase_four_split:
        if task_kind not in {"protocol", "result"}:
            raise launch_common.LaunchError(
                "Phase 04 round 1 requires separate protocol and result tasks"
            )
    elif task_kind != "standard":
        raise launch_common.LaunchError("A specialized task kind is valid only for Phase 04 round 1")
    existing = [
        task
        for task in round_state.get("tasks", [])
        if task.get("role") == role
        and str(task.get("task_kind", "standard")) == task_kind
    ]
    if existing:
        if len(existing) == 1:
            if (
                launch_manifest._manifest_declares_protocol_checkpoint(manifest)
                and launch_manifest._manifest_schema_version(manifest) >= 6
                and (
                    (round_n == 1 and task_kind == "result")
                    or round_n > 1
                )
            ):
                project_state.require_protocol_checkpoint(
                    project_dir, phase_slug, run_id
                )
            return str(existing[0]["task_id"])
        raise launch_common.LaunchError(
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
                raise launch_common.LaunchError(
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
                raise launch_common.LaunchError(
                    "Phase 04 result work requires exactly one preceding protocol task"
                )
            protocol_status = _show_task(
                manifest, str(protocol_tasks[0].get("task_id", ""))
            ).get("status")
            if protocol_status != "done":
                raise launch_common.LaunchError(
                    "Phase 04 result work cannot start until the protocol task is done"
                )
            if launch_manifest._manifest_schema_version(manifest) >= 7:
                declaration = manifest.get("protocol_checkpoint")
                if not isinstance(declaration, Mapping):
                    raise launch_common.LaunchError(
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
        launch_manifest._manifest_declares_protocol_checkpoint(manifest)
        and launch_manifest._manifest_schema_version(manifest) >= 6
        and round_n > 1
    ):
        project_state.require_protocol_checkpoint(
            project_dir, phase_slug, run_id
        )
        run = project_state.get_run(project_dir, phase_slug, run_id)
        round_state = run["rounds"][round_n - 1]

    directive = launch_prompts._directive_text(
        project_dir, phase_slug, run_id, round_n, directive_file
    )
    if directive != str(round_state.get("lead_directive", "")).strip():
        raise launch_common.LaunchError("Round directive changed after it was recorded")
    snapshots = manifest["snapshots"]
    reviewer_substage = launch_prompts._paper_reviewer_substage(manifest, round_n)
    proof_audit_stage = launch_prompts._is_proof_audit_stage(manifest, round_n, role)
    context_lines = []
    if reviewer_substage != "independent":
        for item in snapshots.get("summaries", []):
            if item.get("trusted"):
                evidence_label = "accepted current evidence"
            elif item.get("usable"):
                evidence_label = "completed same-branch evidence, not an accepted baseline"
            else:
                evidence_label = (
                    f"{item.get('evidence_status', 'historical')} advisory evidence"
                )
            context_lines.append(
                f"- Summary, {item['phase']} run {item['run_id']} "
                f"({item.get('kind', 'context')}; {evidence_label}; "
                f"SHA-256 {item['sha256']}): {item['path']}"
            )
            for report in item.get("discussion", []):
                context_lines.append(
                    f"  - Prior role report, round {report.get('round')}, "
                    f"{report.get('role') or 'role not recorded'} "
                    f"(SHA-256 {report.get('sha256', 'not recorded')}): "
                    f"{report.get('path')}"
                )
            for artifact in item.get("supporting_artifacts", []):
                context_lines.append(
                    f"  - Frozen supporting artifact, round {artifact.get('round')} "
                    f"(SHA-256 {artifact.get('sha256', 'not recorded')}): "
                    f"{artifact.get('path')}"
                )
            for artifact in item.get("protocol_artifacts", []):
                context_lines.append(
                    f"  - Frozen {artifact.get('kind', 'protocol artifact')} "
                    f"({artifact.get('purpose', 'sealed protocol evidence')}; "
                    f"SHA-256 {artifact.get('sha256', 'not recorded')}): "
                    f"{artifact.get('path')}"
                )
    prior_lines: list[str] = []
    for prior_round in run.get("rounds", [])[: round_n - 1]:
        prior_number = int(prior_round.get("n", 0) or 0)
        for report in prior_round.get("artifacts", []):
            if isinstance(report, Mapping):
                prior_lines.append(
                    f"- Role report, round {prior_number}: "
                    f"{project_dir / str(report.get('path', ''))} "
                    f"(SHA-256 {report.get('sha256', 'not recorded')})"
                )
        for artifact in prior_round.get("supporting_artifacts", []):
            if isinstance(artifact, Mapping):
                prior_lines.append(
                    f"- Supporting artifact, round {prior_number}: "
                    f"{project_dir / str(artifact.get('path', ''))} "
                    f"(SHA-256 {artifact.get('sha256', 'not recorded')})"
                )
    prior_text = "\n".join(prior_lines)
    output = launch_common._contained_file_destination(
        _planned_task_output(manifest, round_n, role, task_kind),
        project_dir,
        label=f"round {round_n} {role} output",
    )
    playbook = snapshots["playbooks"][f"{role}.md"]["path"]
    try:
        soul_entry = snapshots["souls"][role]
    except (KeyError, TypeError) as exc:
        raise launch_common.LaunchError(
            "This run has no frozen role soul. Start a new run so its full "
            "instruction context can be sealed."
        ) from exc
    soul_text, soul_digest, soul_path = launch_manifest._frozen_snapshot_text(
        soul_entry, f"souls.{role}"
    )
    reviewer_playbook = ""
    reviewer_playbook_digest = ""
    if role == launch_common.PAPER_REVIEWER_ROLE:
        reviewer_playbook, reviewer_playbook_digest, _ = launch_manifest._frozen_snapshot_text(
            snapshots["playbooks"][f"{role}.md"], f"playbooks.{role}.md"
        )
    review_snapshot = (
        launch_prompts._paper_review_manuscript_snapshot(manifest) if reviewer_substage else None
    )
    review_manuscript_block = launch_prompts._paper_review_manuscript_block(
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
    protocol_checkpoint_block = launch_prompts._phase_four_protocol_checkpoint_block(
        project_dir, manifest, run, round_n, role, task_kind
    )
    method_selection_block = launch_prompts._method_selection_prompt_block(
        manifest.get("method_selection"),
        manifest.get("snapshots", {}).get("selected_method"),
    )

    if proof_audit_stage:
        proof_material = launch_prompts._proof_audit_material_block(
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

The Phase 05 reviewer protocol is sealed into this brief with SHA-256
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

Frozen prior results and discussion:
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
    manifest_schema = launch_manifest._manifest_schema_version(manifest)
    production_workspace = bool(
        phase_slug in {
            launch_common.IDEA_EVALUATION_PHASE,
            launch_common.DRAFT_ASSEMBLY_PHASE,
        }
        and manifest_schema >= 11
    )
    protocol_workspace = bool(
        launch_manifest._manifest_declares_protocol_checkpoint(manifest)
        and manifest_schema >= 7
    )
    if production_workspace or protocol_workspace:
        if phase_four_split and task_kind == "protocol":
            declaration = manifest["protocol_checkpoint"]
            workspace_directory = Path(
                str(declaration.get("protocol_root", ""))
            )
            workspace_label = "Phase 04 isolated protocol workspace"
        else:
            workspace_directory = _planned_output(manifest, round_n, role).parent
            workspace_label = "Phase 3 or Phase 4 write-limited round workspace"
        task_workspace = launch_common._ensure_contained_directory(
            workspace_directory,
            project_dir,
            label=workspace_label,
        )
        if production_workspace and not (
            phase_four_split and task_kind == "protocol"
        ):
            task_brief += f"""

## Required supporting-file location

Write every code file, data file, table, figure, proof supplement, or other
supporting artifact created by this task inside the assigned round workspace:
`{task_workspace}`

You may read the sealed inputs named above, but do not write supporting files
elsewhere in the project. Research Hub inventories and seals this round
workspace when the stage completes. Files written elsewhere are outside the
scientific record for this run.
"""
    if role == launch_common.PAPER_REVIEWER_ROLE:
        task_workspace, brief_path, brief_hash, review_bundle_record = (
            launch_prompts._prepare_review_bundle(
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
        brief_path = launch_prompts._task_brief_path(
            project_dir, phase_slug, run_id, round_n, role, task_kind
        )
        launch_common._write_text_atomic(brief_path, task_brief)
        brief_hash = launch_common._sha256_file(
            brief_path,
            max_bytes=launch_common.MAX_TASK_BRIEF_BYTES,
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
    preloaded_skills = launch_manifest._verified_preloaded_skill_names(manifest, role)
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
    launch_common._guard_command_length(command)
    created = launch_process._run_command(
        command,
        timeout=30,
        environment=launch_process._hermes_environment(launch_manifest._manifest_hermes_root(manifest)),
    )
    if created.returncode != 0:
        detail = (created.stderr or created.stdout).strip()
        raise launch_common.LaunchError(f"Hermes task creation failed for {role}: {detail}")
    try:
        payload = json.loads(created.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise launch_common.LaunchError("Hermes task creation returned invalid JSON") from exc
    task_id = _task_id_from_json(payload)
    if not task_id:
        raise launch_common.LaunchError("Hermes task creation did not return a task ID")
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
        warning = launch_process._archive_external_task(manifest, task_id)
        if warning:
            raise launch_common.LaunchError(
                f"Task {task_id} could not be recorded and cleanup is unconfirmed: {warning}"
            ) from exc
        raise
    return task_id


def _show_task(manifest: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    shown = launch_process._run_command(
        [
            str(manifest["hermes_executable"]),
            "kanban",
            "--board",
            str(manifest["board_slug"]),
            "show",
            task_id,
            "--json",
        ],
        environment=launch_process._hermes_environment(launch_manifest._manifest_hermes_root(manifest)),
    )
    if shown.returncode != 0:
        detail = (shown.stderr or shown.stdout).strip()
        raise launch_common.LaunchError(f"Could not verify Hermes task {task_id}: {detail}")
    try:
        return _task_payload(json.loads(shown.stdout or "{}"))
    except json.JSONDecodeError as exc:
        raise launch_common.LaunchError(f"Hermes returned invalid JSON for task {task_id}") from exc



def _complete_round_checked(
    project_dir: str | Path,
    phase_slug: str,
    run_id: str | int,
    round_n: int,
    outputs: Sequence[str | Path],
) -> int:
    project_dir = Path(project_dir).resolve()
    run = project_state.get_run(project_dir, phase_slug, run_id)
    stable_id = str(run["run_id"])
    manifest = launch_manifest._read_manifest(project_dir, phase_slug, stable_id)
    launch_manifest._verify_frozen_inputs(project_dir, phase_slug, stable_id, manifest)
    planned_roles = _planned_roles(manifest, round_n)
    if round_n < 1 or round_n > len(run.get("rounds", [])):
        raise launch_common.LaunchError(f"Run has no recorded round {round_n}")
    round_state = run["rounds"][round_n - 1]
    _verify_completed_round_artifacts(project_dir, run, before_round=round_n)
    _verify_task_briefs(project_dir, phase_slug, run, round_n=round_n)
    tasks = list(round_state.get("tasks", []))
    phase_four_split = (
        launch_manifest._manifest_declares_protocol_checkpoint(manifest)
        and launch_manifest._manifest_schema_version(manifest) >= 6
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
            raise launch_common.LaunchError(
                "Phase 04 round 1 requires one completed protocol task followed "
                "by one completed result task"
            )
        project_state.require_protocol_checkpoint(
            project_dir, phase_slug, stable_id
        )
    else:
        recorded_roles = [str(task.get("role")) for task in tasks]
        if sorted(recorded_roles) != sorted(planned_roles):
            raise launch_common.LaunchError(
                "Round cannot complete until exactly one task is recorded for each planned role"
            )
    unfinished = []
    for task in tasks:
        payload = _show_task(manifest, str(task["task_id"]))
        if payload.get("status") != "done":
            unfinished.append(f"{task['task_id']} ({payload.get('status', 'unknown')})")
    if unfinished:
        raise launch_common.LaunchError("Hermes tasks are not done: " + ", ".join(unfinished))
    for task in tasks:
        if (
            str(task.get("role")) == launch_common.PAPER_REVIEWER_ROLE
            and task.get("review_bundle") is not None
        ):
            launch_prompts._import_review_bundle_output(project_dir, manifest, task, round_n)
    expected = {
        _planned_output(manifest, round_n, role).resolve() for role in planned_roles
    }
    supplied = {Path(output).resolve() for output in outputs}
    if supplied != expected:
        raise launch_common.LaunchError("Round outputs do not match the frozen role output plan")
    if phase_slug in {
        launch_common.IDEA_EVALUATION_PHASE,
        launch_common.DRAFT_ASSEMBLY_PHASE,
    }:
        supporting_count = project_state.complete_round(
            project_dir,
            phase_slug,
            run_id,
            round_n,
            list(outputs),
            discover_supporting=True,
        )
    else:
        project_state.complete_round(
            project_dir, phase_slug, run_id, round_n, list(outputs)
        )
        supporting_count = 0
    return int(supporting_count or 0)
