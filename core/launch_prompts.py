#!/usr/bin/env python3

"""Sealed prompt and task-brief construction for phase runs."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence



from core import launch_common
from core import project_state
from core import launch_dispatch
from core import launch_manifest
from core import launch_plans

def _snapshot_run_inputs(
    project_dir: Path,
    phase: Mapping[str, Any],
    run_id: str,
    context_inputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Copy every prompt input into a run-scoped, immutable context folder."""

    phase_slug = str(phase["slug"])
    destination = launch_common.run_context_dir(project_dir, phase_slug, run_id)
    try:
        control_root = project_state._ensure_control_directory(project_dir).resolve(
            strict=True
        )
    except project_state.ProjectStateError as exc:
        raise launch_common.LaunchError(str(exc)) from exc
    launch_common._ensure_contained_directory(
        destination.parent, control_root, label="run context parent"
    )
    if destination.exists() or destination.is_symlink():
        raise launch_common.LaunchError(f"Run context already exists: {destination}")
    destination.mkdir()

    def copy(
        source: Path,
        relative_name: str,
        *,
        max_bytes: int,
    ) -> dict[str, str]:
        if source.is_symlink():
            raise launch_common.LaunchError(f"Prompt input must not be a symbolic link: {source}")
        try:
            source = source.resolve(strict=True)
        except OSError as exc:
            raise launch_common.LaunchError(f"Prompt input is missing or unreadable: {source}") from exc
        payload = launch_common._bounded_bytes(
            source,
            label="prompt input",
            max_bytes=max_bytes,
        )
        target = launch_common._contained_file_destination(
            destination / relative_name,
            destination,
            label="frozen prompt input destination",
        )
        source_before = hashlib.sha256(payload).hexdigest()
        launch_common._write_bytes_atomic(target, payload)
        source_after = launch_common._sha256_file(
            source,
            max_bytes=max_bytes,
            label="prompt input",
            allow_empty=False,
        )
        target_digest = launch_common._sha256_file(
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
            raise launch_common.LaunchError(
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
                launch_common.TEAM_DIR / "charter.md",
                "team/charter.md",
                max_bytes=launch_common.MAX_EMBEDDED_SOUL_BYTES,
            ),
            "norms": copy(
                launch_common.TEAM_DIR / "norms.md",
                "team/norms.md",
                max_bytes=launch_common.MAX_EMBEDDED_SOUL_BYTES,
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
            launch_common.SOULS_DIR / f"{role}.md",
            f"souls/{role}.md",
            max_bytes=launch_common.MAX_EMBEDDED_SOUL_BYTES,
        )
        launch_manifest._frozen_snapshot_text(soul_snapshot, f"souls.{role}")
        snapshots["souls"][role] = soul_snapshot
    phase_dir = launch_common.PHASES_DIR / phase_slug
    playbook_names = ["_lead.md", "_phase.md"] + [
        f"{role}.md" for role in phase.get("members", [])
    ]
    for name in playbook_names:
        snapshots["playbooks"][name] = copy(
            phase_dir / name,
            f"playbooks/{name}",
            max_bytes=launch_common.MAX_EMBEDDED_SOUL_BYTES,
        )
    for entry in context_inputs:
        source = project_dir / str(entry["summary"])
        relative_name = f"summaries/{entry['phase']}-{entry['run_id']}.html"
        snapshot = copy(
            source,
            relative_name,
            max_bytes=launch_common.MAX_SOURCE_SUMMARY_BYTES,
        )
        expected_digest = str(entry.get("sha256", "")).lower()
        if not expected_digest or snapshot["sha256"] != expected_digest:
            raise launch_common.LaunchError(
                f"Approved context changed while the run was being frozen: "
                f"{entry['phase']} run {entry['run_id']}"
            )
        frozen_entry = {**dict(entry), **snapshot}
        decision_input = entry.get("decision_record")
        if isinstance(decision_input, Mapping):
            decision_snapshot = copy(
                project_dir / str(decision_input.get("path", "")),
                f"decisions/{entry['phase']}-{entry['run_id']}.json",
                max_bytes=launch_common.MAX_SOURCE_DECISION_BYTES,
            )
            expected_decision_digest = str(
                decision_input.get("sha256", "")
            ).lower()
            if (
                not expected_decision_digest
                or decision_snapshot["sha256"] != expected_decision_digest
            ):
                raise launch_common.LaunchError(
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


def _trusted_context(
    project_dir: Path,
    phase_slug: str,
    config: Mapping[str, Any],
    *,
    include_downstream: bool = False,
) -> list[dict[str, Any]]:
    """Return approved run inputs, including the phase's prior baseline.

    When ``include_downstream`` is true, approved summaries from *downstream*
    (future) phases are also included.  These are marked as advisory context
    so the agent can see where the current line of work fits into later results
    the user already has, without treating them as trusted prerequisites.
    """

    dependencies = launch_plans._dependencies(config)
    ancestors = _ancestor_slugs(phase_slug, dependencies)
    phase = launch_plans._phase_config(config, phase_slug)
    optional = {str(item) for item in phase.get("context_from", [])}
    candidates = ancestors | optional | {phase_slug}
    downstream = set()
    if include_downstream:
        downstream = _descendant_slugs(phase_slug, dependencies)
        candidates = candidates | downstream
    state = project_state.load(project_dir)
    entries: list[dict[str, Any]] = []
    for candidate in launch_plans._phase_slugs(config):
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
            digest = launch_common._sha256_file(
                summary,
                max_bytes=launch_common.MAX_SOURCE_SUMMARY_BYTES,
                label="approved context summary",
                allow_empty=False,
            )
        except launch_common.LaunchError:
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
                _, decision_payload, decision_relative = launch_plans._source_file_payload(
                    project_dir,
                    str(decision_record.get("path", "")),
                    str(decision_record.get("sha256", "")),
                    expected_size=decision_size,
                    label="approved context decision record",
                    max_bytes=launch_common.MAX_SOURCE_DECISION_BYTES,
                )
                normalized_decision = project_state.validate_decision_record(
                    json.loads(decision_payload.decode("utf-8"))
                )
            except (
                launch_common.LaunchError,
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
                "downstream_advisory" if candidate in downstream else (
                    "optional_approved_context"
                    if candidate in optional
                    else "prerequisite"
                )
            ),
            "trusted": (
                candidate != phase_slug or not bool(phase_state.get("stale"))
            ) and candidate not in downstream,
        }
        if decision_input is not None:
            context_entry["decision_record"] = decision_input
        entries.append(context_entry)
    return entries


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


def _descendant_slugs(
    phase_slug: str,
    dependencies: Mapping[str, Sequence[str]],
) -> set[str]:
    """Return all phases that are downstream of ``phase_slug`` in the gate graph.

    A descendant is any phase that has ``phase_slug`` as a transitive
    ``gated_by`` prerequisite.  This is the forward (future-phase) counterpart
    of :func:`_ancestor_slugs`.
    """

    # Build reverse adjacency: for each phase, which phases gate on it.
    reverse: dict[str, set[str]] = {}
    for gated_phase, prerequisites in dependencies.items():
        for prerequisite in prerequisites:
            reverse.setdefault(prerequisite, set()).add(gated_phase)
    descendants: set[str] = set()
    queue = list(reverse.get(phase_slug, set()))
    while queue:
        item = queue.pop(0)
        if item in descendants:
            continue
        descendants.add(item)
        queue.extend(reverse.get(item, set()))
    return descendants


def _tracker_command(command: str, project_dir: Path, phase_slug: str, run_id: str, *extra: str) -> str:
    return launch_common._shell_join([
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

    if not launch_manifest._manifest_declares_protocol_checkpoint(manifest):
        return ""
    schema_version = launch_manifest._manifest_schema_version(manifest)
    if schema_version < 5:
        return ""
    declaration = manifest["protocol_checkpoint"]
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
            raise launch_common.LaunchError("Phase 04 run has no run-scoped protocol directory")
        checkpoint = run.get("protocol_checkpoint")
        if not isinstance(checkpoint, Mapping):
            raise launch_common.LaunchError(
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
            raise launch_common.LaunchError("Phase 04 sealed checkpoint has no protocol files")
        assigned_workspace = (
            launch_dispatch._planned_output(manifest, round_n, role).parent
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
        raise launch_common.LaunchError("Phase 04 round 1 task kind is invalid")
    isolated_protocol_task = modern_split and schema_version >= 7
    if protocol_root is not None:
        try:
            protocol_example_path = (
                protocol_root.resolve().relative_to(project_dir.resolve())
                / "study-design.yaml"
            ).as_posix()
        except ValueError as exc:
            raise launch_common.LaunchError("Phase 04 protocol directory escaped the project") from exc
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
        str(manifest.get("phase_slug", "")),
        str(manifest.get("run_id", "")),
        "--checkpoint",
        str(checkpoint_path),
    )
    example = json.dumps(
        {
            "schema_version": project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION,
            "phase_slug": str(manifest.get("phase_slug", "")),
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
    output_root: Path | None = None,
) -> str:
    phase_slug = str(phase["slug"])
    # Use the branch-aware output root when provided (sealed in the manifest);
    # fall back to flat path only for legacy manifests that lack output_root.
    if output_root is not None:
        output_root = Path(output_root)
    else:
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
        if phase.get("protocol_checkpoint") and round_n == 1:
            if roles != ["data_scientist"]:
                raise launch_common.LaunchError(
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


def _paper_reviewer_substage(
    manifest: Mapping[str, Any], round_n: int
) -> str | None:
    if str(manifest.get("phase_slug")) != launch_common.PAPER_WRITING_PHASE:
        return None
    stages = list(manifest.get("phase", {}).get("stages", []))
    reviewer_rounds = [
        index
        for index, stage in enumerate(stages, 1)
        if str(stage.get("role")) == launch_common.PAPER_REVIEWER_ROLE
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
        str(manifest.get("phase_slug")) == launch_common.IDEA_EVALUATION_PHASE
        and phase.get("proof_audit") is True
        and role == launch_common.PAPER_REVIEWER_ROLE
        and round_n == len(stages)
        and stages
        and str(stages[-1].get("role")) == launch_common.PAPER_REVIEWER_ROLE
    )


def _proof_audit_material_block(
    project_dir: Path,
    manifest: Mapping[str, Any],
    run: Mapping[str, Any],
    round_n: int,
) -> str:
    """Seal the exact final theory artifact and audit evidence into the brief."""

    if manifest.get("phase", {}).get("audit_only") is True:
        source = launch_plans._verified_frozen_theory_audit_source(project_dir, manifest)
        target_record = source["target"]
        target = Path(str(target_record["path"])).resolve()
        theory = launch_common._read_utf8_bounded(
            target,
            label="frozen audit-only theory artifact",
            max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
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
        raise launch_common.LaunchError("The selected proof audit has no preceding theorist stage")
    target_round = theorist_rounds[-1]
    target = launch_dispatch._planned_output(manifest, target_round, "theorist").resolve()
    root = project_dir.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise launch_common.LaunchError("The proof-audit target escaped the project") from exc
    round_state = next(
        (
            item
            for item in run.get("rounds", [])
            if int(item.get("n", 0)) == target_round and item.get("completed")
        ),
        None,
    )
    if round_state is None:
        raise launch_common.LaunchError("The final theorist stage is not complete")
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
        raise launch_common.LaunchError("The final theory artifact has no sealed artifact record")
    theory = launch_common._read_utf8_bounded(
        target,
        label="final theory artifact",
        max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
    )
    digest = hashlib.sha256(theory.encode("utf-8")).hexdigest()
    if digest != str(record.get("sha256", "")).lower() or launch_common._sha256_file(target) != digest:
        raise launch_common.LaunchError("The final theory artifact changed after stage completion")

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
    """Read one stable snapshot of the Phase 05 review manuscript."""

    raw_output_root = Path(str(manifest["output_root"]))
    path = launch_plans._paper_manuscript_paths(raw_output_root)["review"]
    project_value = manifest.get("project_dir")
    uses_link = (
        launch_common._path_uses_symlink_below(path, Path(str(project_value)).resolve())
        if project_value
        else raw_output_root.is_symlink() or path.is_symlink()
    )
    if uses_link:
        raise launch_common.LaunchError("The Phase 05 review manuscript must not use symbolic links")
    try:
        path = path.resolve(strict=True)
    except OSError as exc:
        raise launch_common.LaunchError(
            f"The Phase 05 review manuscript is missing: {path}"
        ) from exc
    digest_before = launch_common._sha256_file(path)
    manuscript = launch_common._read_utf8_bounded(
        path,
        label="Phase 05 review manuscript",
        max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
    )
    digest = hashlib.sha256(manuscript.encode("utf-8")).hexdigest()
    digest_after = launch_common._sha256_file(path)
    if digest_before != digest or digest_after != digest:
        raise launch_common.LaunchError(
            "The Phase 05 review manuscript changed while the reviewer task "
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
    """Seal the exact Phase 05 manuscript into the reviewer task brief."""

    if (
        str(manifest.get("phase_slug")) != launch_common.PAPER_WRITING_PHASE
        or role != launch_common.PAPER_REVIEWER_ROLE
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


def _source_baseline_lead_block(source_baseline: Any) -> str:
    """Describe how the lead must preserve a selected run's complete baseline."""

    if not isinstance(source_baseline, Mapping):
        raise launch_common.LaunchError("Special run has no frozen source baseline")
    summary = source_baseline.get("summary")
    decision = source_baseline.get("decision_record")
    if not isinstance(summary, Mapping) or not isinstance(decision, Mapping):
        raise launch_common.LaunchError("Special run source baseline is incomplete")
    baseline_status = launch_plans._source_baseline_status(source_baseline)
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
        raise launch_common.LaunchError("Special run source-baseline status is invalid")
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
        raise launch_common.LaunchError("The frozen method selection has an invalid source")
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
    run_mode: str = "",
    output_root: Path | None = None,
) -> str:
    phase_slug = str(phase["slug"])
    phase_name = str(phase.get("name", phase_slug))
    try:
        lead_soul_entry = snapshots["souls"]["research_lead"]
    except (KeyError, TypeError) as exc:
        raise launch_common.LaunchError("The run has no frozen research_lead soul") from exc
    lead_soul_text, lead_soul_digest, lead_soul_path = launch_manifest._frozen_snapshot_text(
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
            f"{'trusted current input' if entry.get('trusted', True) else 'advisory context — for awareness, not as evidence to build upon'}; "
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
        output_root=output_root,
    )
    manuscript_paths_text = ""
    if phase_slug == launch_common.PAPER_WRITING_PHASE:
        # Use the branch-aware output root when available; fall back to flat
        # path for legacy manifests.
        manuscript_base = (
            Path(output_root)
            if output_root is not None
            else project_dir
            / str(phase.get("folder", ""))
            / "run"
            / f"{run_number:02d}"
        )
        paths = launch_plans._paper_manuscript_paths(manuscript_base)
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
        elif paper_review and paper_review.get("kind") == "assembly":
            manuscript_paths_text = f"""## Assembly manuscript path

- Assembled manuscript: `{paths['assembly']}`

Write the complete assembled manuscript to the path above. This is the sole
output of the assembly stage — there is no review or post-review variant.
The user will review the assembled manuscript, then launch a review-revision
run to audit and revise it.
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
Phase 05 run that reviews it.
"""
    proof_audit_text = ""
    if phase_slug == launch_common.IDEA_EVALUATION_PHASE and phase.get("proof_audit"):
        if phase.get("audit_only"):
            if not isinstance(proof_audit_source, Mapping):
                raise launch_common.LaunchError("The audit-only lead prompt has no source identity")
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

    run_mode_text = ""
    if (
        phase_slug == launch_common.DRAFT_ASSEMBLY_PHASE
        and run_mode
        and run_mode in launch_common.RUN_MODES
    ):
        if run_mode == launch_common.RUN_MODE_PRELIMINARY:
            run_mode_text = """## User-selected preliminary run

This is a PRELIMINARY implementation run. The goal is to confirm the method
works in code, not to produce final paper-ready results. Focus narrowly:

1. **Implement the method** — write working Python code that implements the
   mathematical definition from the Phase 03 results. Not pseudocode, not a
   description. Code that runs.
2. **Diagnostic sanity checks only** — run simple known-answer tests that
   confirm the implementation is correct (e.g., does the invariant measure
   match for a Gaussian? do conservation laws hold? does the same seed produce
   the same result?). Record the measured values in a JSON file.
3. **Stop there.** Do NOT run the full benchmark study, do NOT compare against
   baselines, do NOT generate publication figures. That is the comprehensive
   run's job.

The user will review whether the implementation works. If it does, they will
launch a comprehensive run to benchmark it against existing methods.
"""
        else:  # comprehensive
            run_mode_text = """## User-selected comprehensive run

This is a COMPREHENSIVE benchmark run. A prior preliminary run already produced
a working implementation in this branch — read it and build on it. The goal is
to produce the comparison results needed for the paper draft:

1. **Benchmark against existing methods** — compare the implemented method
   against the relevant baselines across the settings that will appear in the
   paper (convergence curves, ESS/s, rate estimation against proved bounds).
2. **Multiple settings** — test across the parameter regimes the paper will
   report (different dimensions, graph structures, step sizes, etc.).
3. **Publication-quality tables and figures** — real measured numbers with
   quantified uncertainty (MCSE, confidence intervals, replications).
4. **Theorist audit** — do the measured rates match the proved bounds from
   Phase 03? If theory and experiment disagree, identify why.

Do not re-implement the method from scratch. The preliminary run's code is the
starting point. If you find bugs, fix them and rerun the affected experiments.
"""
    elif (
        phase_slug == launch_common.PAPER_WRITING_PHASE
        and run_mode
        and run_mode in launch_common.PAPER_RUN_MODES
    ):
        if run_mode == launch_common.RUN_MODE_ASSEMBLY:
            run_mode_text = """## User-selected assembly run

This is an ASSEMBLY run. Your sole task is to combine the separate Phase 1–4
artifacts into one coherent manuscript. This is the convergence point — the
first and only stage where the whole research thread becomes a single paper.

1. **Introduction** — motivate the problem, state the contribution, position
   against the Phase 01 literature.
2. **Method** — use the Phase 02 method definition (the precise definition of
   what was proposed).
3. **Theory** — use the Phase 03 proved theorems with full proofs. Do not
   re-derive; use the theorist's actual output.
4. **Experiments** — use the Phase 04 implementation, diagnostics, and
   benchmark results (tables, figures). Use the analyst's actual output.
5. **Discussion** — synthesize open questions from Phases 3–4 and connections
   to broader literature.

Reconcile notation, ensure claim consistency (intro claims must match what the
theory proves and what the experiments show), and merge all references into one
bibliography. Use the `stat-paper-writing` skill for paper conventions.

The user will review the assembled manuscript and then launch a
review-revision run.
"""
        else:  # review_revision
            run_mode_text = """## User-selected review-revision run

This is a REVIEW-REVISION run. A prior assembly run already produced a complete
manuscript in this branch — read it. Your task has two stages:

**Stage 1 (paper_reviewer):** Audit the assembled manuscript independently.
Use the `stat-paper-reviewer` skill. Evaluate soundness, clarity, significance,
and originality. Produce ranked weaknesses (fatal/major/minor), specific
revision recommendations, missing references, scores, and an overall assessment.

**Stage 2 (research_lead):** Address every review point. Use the
`stat-paper-writing` skill during revision. For each weakness: fix it, defer it
with explicit reasoning, or push back with reasoning. Produce the final revised
manuscript plus a mandatory revision log documenting every change.

Do not re-assemble the manuscript from scratch. The assembly run's output is the
starting point. If the review reveals the manuscript needs major structural
changes, flag that a new assembly run may be needed.
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
{f'- Run mode: {run_mode}' if run_mode else ''}

{prerequisite_text}

{method_selection_text}

{manuscript_paths_text}

{proof_audit_text}

{run_mode_text}

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

Use these frozen summary inputs according to their labels. Trusted inputs are
current evidence you build upon. Advisory context (downstream results, prior
baselines) is for awareness — understand what was already achieved or decided
in later phases, but do not treat it as evidence this run must reproduce:

{context_text}

Clearly distinguish inherited facts, historical baselines, advisory downstream
results, new findings, uncertainty, and recommendations.

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
        / f"round-{round_n:02d}-{launch_common.PAPER_REVIEWER_ROLE}"
    )


def _review_source_payload(
    path: Path,
    expected_digest: str,
    label: str,
    *,
    max_bytes: int = launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
) -> bytes:
    if path.is_symlink():
        raise launch_common.LaunchError(f"Sealed reviewer input must not be a symbolic link: {label}")
    try:
        source = path.resolve(strict=True)
    except OSError as exc:
        raise launch_common.LaunchError(f"Sealed reviewer input is unavailable: {label}") from exc
    if not source.is_file():
        raise launch_common.LaunchError(f"Sealed reviewer input must be a regular file: {label}")
    if max_bytes < 1 or max_bytes > launch_common.MAX_REVIEW_BUNDLE_BYTES:
        raise launch_common.LaunchError(f"Sealed reviewer input has an invalid size policy: {label}")
    try:
        with source.open("rb") as handle:
            payload = handle.read(max_bytes + 1)
    except OSError as exc:
        raise launch_common.LaunchError(f"Could not read sealed reviewer input: {label}") from exc
    if len(payload) > max_bytes:
        raise launch_common.LaunchError(f"Sealed reviewer input exceeds the safety limit: {label}")
    if not payload.strip():
        raise launch_common.LaunchError(f"Sealed reviewer input is empty: {label}")
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise launch_common.LaunchError(f"Sealed reviewer input is not valid UTF-8: {label}") from exc
    digest = hashlib.sha256(payload).hexdigest()
    if digest != str(expected_digest).lower() or launch_common._sha256_file(source) != digest:
        raise launch_common.LaunchError(f"Sealed reviewer input changed before bundling: {label}")
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
        max_bytes: int = launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
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
            raise launch_common.LaunchError("Reviewer task has no sealed manuscript snapshot")
        review_path, _text, review_digest = review_snapshot
        add(review_path, review_digest, "Exact manuscript under review")

    stages = list(manifest.get("phase", {}).get("stages", []))
    if proof_audit_stage:
        if manifest.get("phase", {}).get("audit_only") is True:
            source = launch_plans._verified_frozen_theory_audit_source(project_dir, manifest)
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
                raise launch_common.LaunchError("The selected proof audit has no preceding theorist stage")
            target_round = theorist_rounds[-1]
            target_state = run.get("rounds", [])[target_round - 1]
            target = launch_dispatch._planned_output(manifest, target_round, "theorist").resolve()
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
                raise launch_common.LaunchError("The final theory artifact has no sealed record")
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
            source_baseline = launch_plans._verified_frozen_source_baseline(
                project_dir,
                manifest,
                paper_review.get("source_baseline"),
                expected_phase_slug=launch_common.PAPER_WRITING_PHASE,
                relative_directory="paper-review/source-baseline",
            )
            baseline_status = launch_plans._source_baseline_status(source_baseline)
            source_run_id = str(source_baseline.get("run_id", ""))
            for name, purpose, maximum in (
                (
                    "summary",
                    f"Frozen {baseline_status} source summary from run {source_run_id}",
                    launch_common.MAX_SOURCE_SUMMARY_BYTES,
                ),
                (
                    "decision_record",
                    f"Frozen {baseline_status} structured source record from run {source_run_id}",
                    launch_common.MAX_SOURCE_DECISION_BYTES,
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
        raise launch_common.LaunchError("Paper reviewer task has no configured review subtype")
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
            raise launch_common.LaunchError("Proof audit requires a nonempty sealed audit directive")
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
            raise launch_common.LaunchError(
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
    control_root = launch_common._ensure_contained_directory(
        project_state.state_dir(project_dir),
        project_dir.parent,
        label="project control directory",
    )
    root = launch_common._ensure_contained_directory(
        raw_root, control_root, label="reviewer workspace"
    )
    root / "inputs"
    records: list[dict[str, Any]] = []
    total = 0
    for index, source in enumerate(sources, 1):
        payload = _review_source_payload(
            Path(source["source"]),
            str(source["sha256"]),
            str(source["purpose"]),
            max_bytes=int(source.get("max_bytes", launch_common.MAX_REVIEW_MANUSCRIPT_BYTES)),
        )
        total += len(payload)
        if total > launch_common.MAX_REVIEW_BUNDLE_BYTES:
            raise launch_common.LaunchError("Sealed reviewer inputs exceed the aggregate safety limit")
        suffix = Path(source["source"]).suffix.lower()
        if suffix not in {".md", ".html", ".txt", ".json"}:
            suffix = ".txt"
        relative = Path("inputs") / f"input-{index:02d}{suffix}"
        destination = launch_common._contained_file_destination(
            root / relative, root, label="reviewer input destination"
        )
        launch_common._write_bytes_atomic(destination, payload)
        if launch_common._sha256_file(destination) != str(source["sha256"]).lower():
            raise launch_common.LaunchError("A reviewer input changed while its bundle was written")
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
    task_path = launch_common._contained_file_destination(
        root / "task.md", root, label="reviewer task destination"
    )
    launch_common._write_text_atomic(task_path, task_text)
    task_payload = launch_common._bounded_bytes(
        task_path,
        label="reviewer task",
        max_bytes=launch_common.MAX_TASK_BRIEF_BYTES,
    )
    launch_common._contained_file_destination(
        root / "output" / "report.md", root, label="reviewer report destination"
    )
    bundle = {
        "schema_version": launch_common.REVIEW_BUNDLE_SCHEMA_VERSION,
        "phase_slug": str(manifest["phase_slug"]),
        "run_id": str(manifest["run_id"]),
        "round": round_n,
        "role": launch_common.PAPER_REVIEWER_ROLE,
        "subtype": subtype,
        "task": {
            "path": "task.md",
            "sha256": hashlib.sha256(task_payload).hexdigest(),
            "size": len(task_payload),
        },
        "inputs": records,
        "output": {"path": "output/report.md", "max_bytes": launch_common.MAX_REVIEW_OUTPUT_BYTES},
    }
    manifest_path = launch_common._contained_file_destination(
        root / "bundle.json", root, label="reviewer bundle manifest destination"
    )
    launch_common._write_text_atomic(
        manifest_path, json.dumps(bundle, indent=2, ensure_ascii=False, sort_keys=True)
    )
    bundle_record = {
        "root": str(root),
        "manifest_path": str(manifest_path),
        "manifest_sha256": launch_common._sha256_file(manifest_path),
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
        raise launch_common.LaunchError("Reviewer task has no sealed workspace record")
    control_root = project_state.state_dir(project_dir).resolve()
    raw_root = Path(str(record.get("root", "")))
    raw_manifest = Path(str(record.get("manifest_path", "")))
    if launch_common._path_uses_symlink_below(raw_root, control_root / "review-workspaces"):
        raise launch_common.LaunchError("Reviewer workspace path must not use symbolic links")
    if launch_common._path_uses_symlink_below(raw_manifest, raw_root):
        raise launch_common.LaunchError("Reviewer workspace manifest must not use symbolic links")
    try:
        root = raw_root.resolve(strict=True)
        root.relative_to(control_root / "review-workspaces")
        manifest_path = raw_manifest.resolve(strict=True)
        manifest_path.relative_to(root)
    except (OSError, ValueError) as exc:
        raise launch_common.LaunchError("Reviewer workspace escaped project control storage") from exc
    if manifest_path != root / "bundle.json":
        raise launch_common.LaunchError("Reviewer workspace manifest path is invalid")
    payload = launch_common._bounded_bytes(
        manifest_path,
        label="reviewer workspace manifest",
        max_bytes=project_state.MAX_CONTROL_FILE_BYTES,
    )
    if hashlib.sha256(payload).hexdigest() != str(record.get("manifest_sha256", "")).lower():
        raise launch_common.LaunchError("Reviewer workspace manifest changed after dispatch")
    try:
        bundle = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise launch_common.LaunchError("Reviewer workspace manifest is invalid") from exc
    if (
        not isinstance(bundle, Mapping)
        or bundle.get("schema_version") != launch_common.REVIEW_BUNDLE_SCHEMA_VERSION
        or bundle.get("phase_slug") != phase_slug
        or bundle.get("run_id") != run_id
        or bundle.get("round") != round_n
        or bundle.get("role") != launch_common.PAPER_REVIEWER_ROLE
    ):
        raise launch_common.LaunchError("Reviewer workspace identity is invalid")
    leaves = [bundle.get("task"), *list(bundle.get("inputs", []))]
    for leaf in leaves:
        if not isinstance(leaf, Mapping):
            raise launch_common.LaunchError("Reviewer workspace file record is invalid")
        raw_candidate = root / str(leaf.get("path", ""))
        if launch_common._path_uses_symlink_below(raw_candidate, root):
            raise launch_common.LaunchError("Reviewer workspace input must not use symbolic links")
        try:
            candidate = raw_candidate.resolve(strict=True)
            candidate.relative_to(root)
            size = int(leaf.get("size", -1))
        except (OSError, ValueError, TypeError) as exc:
            raise launch_common.LaunchError("Reviewer workspace input is unavailable") from exc
        if size < 1 or size > launch_common.MAX_REVIEW_BUNDLE_BYTES:
            raise launch_common.LaunchError("Reviewer workspace input size is invalid")
        contents = launch_common._bounded_bytes(
            candidate,
            label="reviewer workspace input",
            max_bytes=launch_common.MAX_REVIEW_BUNDLE_BYTES,
        )
        if (
            len(contents) != size
            or hashlib.sha256(contents).hexdigest()
            != str(leaf.get("sha256", "")).lower()
        ):
            raise launch_common.LaunchError("Reviewer workspace input changed after dispatch")
    task_record = bundle["task"]
    if (
        str((root / str(task_record["path"])).resolve())
        != str(Path(str(task.get("brief_path", ""))).resolve())
        or str(task_record["sha256"]).lower()
        != str(task.get("brief_sha256", "")).lower()
    ):
        raise launch_common.LaunchError("Reviewer task brief does not match its workspace manifest")
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
        raise launch_common.LaunchError("Reviewer workspace output record is invalid")
    raw_output = root / str(output_record.get("path", ""))
    if launch_common._path_uses_symlink_below(raw_output, root):
        raise launch_common.LaunchError("Reviewer report must not use symbolic links")
    try:
        output = raw_output.resolve(strict=True)
        output.relative_to(root / "output")
        max_bytes = int(output_record.get("max_bytes", 0))
    except (OSError, ValueError, TypeError) as exc:
        raise launch_common.LaunchError("Reviewer report is missing from its sealed workspace") from exc
    if not output.is_file():
        raise launch_common.LaunchError("Reviewer report must be a regular file")
    if max_bytes < 1 or max_bytes > launch_common.MAX_REVIEW_OUTPUT_BYTES:
        raise launch_common.LaunchError("Reviewer report size policy is invalid")
    payload = launch_common._bounded_bytes(
        output,
        label="reviewer report",
        max_bytes=max_bytes,
    )
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise launch_common.LaunchError("Reviewer report is not valid UTF-8") from exc
    destination = launch_common._contained_file_destination(
        launch_dispatch._planned_output(manifest, round_n, launch_common.PAPER_REVIEWER_ROLE),
        project_dir,
        label="imported reviewer report destination",
    )
    if destination.exists():
        existing = launch_common._bounded_bytes(
            destination,
            label="imported reviewer report",
            max_bytes=launch_common.MAX_REVIEW_OUTPUT_BYTES,
        )
        if existing != payload:
            raise launch_common.LaunchError("Reviewer report destination already contains different content")
    else:
        launch_common._write_bytes_atomic(destination, payload)
    if launch_common._bounded_bytes(
        destination,
        label="imported reviewer report",
        max_bytes=launch_common.MAX_REVIEW_OUTPUT_BYTES,
    ) != payload:
        raise launch_common.LaunchError("Reviewer report changed while it was imported")
    return destination


def _directive_text(
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    round_n: int,
    directive_file: str | Path,
) -> str:
    manifest = launch_manifest._read_manifest(project_dir, phase_slug, run_id)
    expected = (
        Path(str(manifest["output_root"]))
        / ".directives"
        / f"round-{round_n:02d}.md"
    ).resolve()
    try:
        expected.relative_to(project_dir.resolve())
    except ValueError as exc:
        raise launch_common.LaunchError("Round directive path escaped the project directory") from exc
    candidate = Path(directive_file).resolve()
    if candidate != expected:
        raise launch_common.LaunchError(f"Directive must use the run-scoped path: {expected}")
    text = launch_common._read_utf8_bounded(
        candidate,
        label="round directive",
        max_bytes=launch_common.MAX_DIRECTIVE_BYTES,
    ).strip()
    if not text:
        raise launch_common.LaunchError("Round directive cannot be empty")
    if len(text) > 50_000:
        raise launch_common.LaunchError("Round directive cannot exceed 50,000 characters")
    return text
