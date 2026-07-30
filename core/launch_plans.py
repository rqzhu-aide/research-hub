#!/usr/bin/env python3

"""Phase plan selection, method binding, and source-baseline freezing."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Mapping



from core import launch_common
from core import project_state
from core import profile_skills
from core import launch_dispatch
from core import launch_manifest
from core import launch_prompts

import logging
log = logging.getLogger(__name__)

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
) -> tuple[list[str], dict[str, str]] | tuple[None, None]:
    """Return the declared Phase 03 plan list and reviewer stage.

    Theory run plans exist only when the phase configuration explicitly
    declares them with ``proof_audit`` (plans plus reviewer stage) or with
    ``available_run_plans`` (plans only, default reviewer stage). A phase
    without either declaration (for example a debate-style idea evaluation)
    has no theory plans at all.
    """

    expected_plans = [
        launch_common.THEORY_PLAN_STANDARD,
        launch_common.THEORY_PLAN_STANDARD_WITH_AUDIT,
        launch_common.THEORY_PLAN_AUDIT_ONLY,
    ]
    configured = phase.get("proof_audit")
    declared_plans = phase.get("available_run_plans")
    if configured is None and declared_plans is None:
        return None, None
    if configured is None:
        plans = declared_plans
        stage: Any = {
            "role": launch_common.PAPER_REVIEWER_ROLE,
            "name": "Audit the final theoretical analysis independently",
            "description": (
                "Check the exact sealed theory artifact, assumptions, proof "
                "dependencies, and central conclusions without revising the theory."
            ),
        }
    else:
        if not isinstance(configured, Mapping) or set(configured) != {"plans", "stage"}:
            raise launch_common.LaunchError("Phase 03 proof_audit must contain plans and stage")
        plans = configured.get("plans")
        stage = configured.get("stage")
    if plans != expected_plans:
        raise launch_common.LaunchError(
            "Phase 03 proof_audit.plans must declare standard, "
            "standard_with_audit, and audit_only in that order"
        )
    if not isinstance(stage, Mapping) or set(stage) != {"role", "name", "description"}:
        raise launch_common.LaunchError(
            "Phase 03 proof_audit.stage must contain role, name, and description"
        )
    normalized = {
        key: str(stage.get(key, "")).strip()
        for key in ("role", "name", "description")
    }
    if any(not value for value in normalized.values()):
        raise launch_common.LaunchError("Phase 03 proof_audit.stage fields must be nonempty")
    if normalized["role"] != launch_common.PAPER_REVIEWER_ROLE:
        raise launch_common.LaunchError("Phase 03 proof audit must be assigned to paper_reviewer")
    return list(plans), normalized


def phase_supports_theory_plans(phase: Mapping[str, Any]) -> bool:
    """True when the phase configuration declares Phase 03 theory run plans."""

    plans, _ = _configured_proof_audit(phase)
    return plans is not None


def _configured_run_modes(
    phase: Mapping[str, Any],
) -> tuple[list[str], str] | tuple[None, None]:
    """Return (plans, default_mode) declared on the phase, or (None, None).

    Phase 04 run_modes is an opt-in block (preliminary/comprehensive).
    Phase 05 run_modes is an opt-in block (assembly/review_revision).
    When absent the phase runs as a single-shape run with no mode selector.
    """

    declared = phase.get("run_modes")
    if not isinstance(declared, Mapping):
        if declared is None:
            return None, None
        raise launch_common.LaunchError("Phase run_modes must be a mapping")
    plans = declared.get("plans")
    default_mode = declared.get("default")
    slug = str(phase.get("slug", ""))
    if slug == launch_common.DRAFT_ASSEMBLY_PHASE:
        if not isinstance(plans, list) or plans != ["preliminary", "comprehensive"]:
            raise launch_common.LaunchError(
                "Phase 04 run_modes.plans must declare preliminary and comprehensive "
                "in that order"
            )
        if default_mode not in ("preliminary", "comprehensive"):
            raise launch_common.LaunchError(
                "Phase 04 run_modes.default must be preliminary or comprehensive"
            )
    elif slug == launch_common.PAPER_WRITING_PHASE:
        if not isinstance(plans, list) or plans != ["assembly", "review_revision"]:
            raise launch_common.LaunchError(
                "Phase 05 run_modes.plans must declare assembly and review_revision "
                "in that order"
            )
        if default_mode not in ("assembly", "review_revision"):
            raise launch_common.LaunchError(
                "Phase 05 run_modes.default must be assembly or review_revision"
            )
    else:
        raise launch_common.LaunchError(
            "run_modes is only valid for Phase 04 or Phase 05"
        )
    return list(plans), str(default_mode)


def phase_supports_run_modes(phase: Mapping[str, Any]) -> bool:
    """True when the phase configuration declares run modes (Phase 04 or 05)."""

    plans, _ = _configured_run_modes(phase)
    return plans is not None


def _phase_for_run_mode(
    phase: Mapping[str, Any], mode: str
) -> dict[str, Any]:
    """Return the phase configuration shaped for the selected run mode.

    Phase 04 modes change scientific scope but retain the same ordered stages.
    Phase 05 modes (assembly/review_revision) adjust stages and rounds.
    The shaped dict carries ``run_plan`` so downstream prompt assembly and the
    manifest record which scope or shape the user picked.
    """

    slug = str(phase.get("slug", ""))
    plans, default_mode = _configured_run_modes(phase)
    if plans is None:
        raise launch_common.LaunchError("This phase does not declare run modes")

    if slug == launch_common.DRAFT_ASSEMBLY_PHASE:
        if mode not in launch_common.RUN_MODES:
            raise launch_common.LaunchError(f"Unknown Phase 04 run mode: {mode!r}")
        shaped = dict(phase)
        shaped["run_plan"] = mode
        return shaped

    # Phase 05: assembly vs review_revision
    if mode not in launch_common.PAPER_RUN_MODES:
        raise launch_common.LaunchError(f"Unknown Phase 05 run mode: {mode!r}")

    shaped = dict(phase)
    shaped["run_plan"] = mode
    if mode == launch_common.RUN_MODE_ASSEMBLY:
        # Assembly: single research_lead stage
        shaped["members"] = ["research_lead"]
        shaped["stages"] = [dict(phase["stages"][0])]
        shaped["rounds"] = {"min": 1, "default": 1, "max": 1}
    else:  # review_revision
        # Review + Revise: paper_reviewer audits, then research_lead revises
        shaped["members"] = ["paper_reviewer", "research_lead"]
        shaped["stages"] = [
            {
                "role": "paper_reviewer",
                "name": "Review the assembled manuscript",
                "description": (
                    "Audit the assembled manuscript independently: soundness, "
                    "clarity, significance, originality. Produce ranked revision "
                    "recommendations."
                ),
            },
            {
                "role": "research_lead",
                "name": "Revise the manuscript",
                "description": (
                    "Address each review point, revise the draft, produce the final "
                    "manuscript with a revision log."
                ),
            },
        ]
        shaped["rounds"] = {"min": 2, "default": 2, "max": 2}
    return shaped




def paper_review_only_phase(phase: Mapping[str, Any]) -> dict[str, Any]:
    """Return the two-stage plan for reviewing an exact existing manuscript."""

    review_phase = dict(phase)
    review_phase["members"] = [launch_common.PAPER_REVIEWER_ROLE]
    review_phase["stages"] = [
        {
            "role": launch_common.PAPER_REVIEWER_ROLE,
            "name": "Read the selected manuscript independently",
            "description": (
                "Record a first-reader assessment using only the sealed manuscript."
            ),
        },
        {
            "role": launch_common.PAPER_REVIEWER_ROLE,
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
    if audit_stage is None:
        raise launch_common.LaunchError("This phase does not declare theory run plans")
    audit_phase = dict(phase)
    members = [str(role) for role in phase.get("members", [])]
    if launch_common.PAPER_REVIEWER_ROLE not in members:
        members.append(launch_common.PAPER_REVIEWER_ROLE)
    audit_phase["members"] = members
    stages = [dict(stage) for stage in phase.get("stages", [])]
    stages.append(audit_stage)
    audit_phase["stages"] = stages
    count = len(stages)
    audit_phase["rounds"] = {"min": count, "default": count, "max": count}
    audit_phase["proof_audit"] = True
    audit_phase["run_plan"] = launch_common.THEORY_PLAN_STANDARD_WITH_AUDIT
    return audit_phase


def _phase_for_theory_plan(
    phase: Mapping[str, Any], plan: str
) -> dict[str, Any]:
    """Return the exact Phase 03 stage plan selected by the user."""

    if str(phase.get("slug")) != launch_common.IDEA_EVALUATION_PHASE:
        raise launch_common.LaunchError("Theory run plans are only valid in Phase 03")
    plans, audit_stage = _configured_proof_audit(phase)
    if plans is None or audit_stage is None:
        raise launch_common.LaunchError("This phase does not declare theory run plans")
    if plan not in plans:
        raise launch_common.LaunchError(f"Unknown Phase 03 run plan: {plan!r}")
    if plan == launch_common.THEORY_PLAN_STANDARD:
        selected = dict(phase)
        selected["members"] = list(dict.fromkeys(
            str(stage["role"]) for stage in phase.get("stages", [])
        ))
        selected["proof_audit"] = False
        selected["run_plan"] = plan
        return selected
    if plan == launch_common.THEORY_PLAN_STANDARD_WITH_AUDIT:
        return _phase_with_proof_audit(phase)
    selected = dict(phase)
    selected["members"] = [launch_common.PAPER_REVIEWER_ROLE]
    selected["stages"] = [audit_stage]
    selected["rounds"] = {"min": 1, "default": 1, "max": 1}
    selected["proof_audit"] = True
    selected["audit_only"] = True
    selected["run_plan"] = plan
    return selected


def _load_hub_config() -> dict[str, Any]:
    """Load the validated hub configuration."""

    import hub

    return hub.load_config()


def _phase_config(config: Mapping[str, Any], phase_slug: str) -> dict[str, Any]:
    for phase in config.get("phases", []):
        if phase.get("slug") == phase_slug:
            return dict(phase)
    raise launch_common.LaunchError(f"Unknown phase: {phase_slug}")


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


def _round_count(phase: Mapping[str, Any], requested: int | None) -> int:
    policy = phase.get("rounds", {})
    minimum = int(policy.get("min", 1))
    default = int(policy.get("default", minimum))
    maximum = int(policy.get("max", default))
    if phase.get("pattern") == "sequential":
        fixed = len(phase.get("stages", []))
        if fixed < 1:
            raise launch_common.LaunchError(f"Sequential phase {phase['slug']} has no configured stages")
        return fixed
    value = default if requested is None else int(requested)
    if value < minimum or value > maximum:
        raise launch_common.LaunchError(
            f"{phase.get('name', phase['slug'])} allows {minimum} to {maximum} rounds; "
            f"received {value}."
        )
    return value


def _should_preload_recommended_skill(
    phase_slug: str,
    role: str,
    skill_name: str,
    *,
    review_only: bool = False,
) -> bool:
    """Return whether one exact recommended skill applies to this run mode."""

    if role == launch_common.PAPER_REVIEWER_ROLE and skill_name == launch_common.PAPER_REVIEWER_SKILL:
        return True
    return (
        phase_slug == launch_common.PAPER_WRITING_PHASE
        and not review_only
        and role in launch_common.PAPER_WRITING_SKILL_ROLES
        and skill_name == launch_common.PAPER_WRITING_SKILL
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

    relative = path.relative_to(launch_common.HUB_DIR).as_posix()
    try:
        metadata = path.lstat()
    except OSError:
        return {"path": relative, "state": "missing"}
    if launch_common._metadata_is_link_or_reparse(metadata):
        return {"path": relative, "state": "linked"}
    if not stat.S_ISREG(metadata.st_mode):
        return {"path": relative, "state": "not_regular"}
    try:
        payload = launch_common._bounded_bytes(
            path,
            label=f"launch instruction {relative}",
            max_bytes=launch_common.MAX_EMBEDDED_SOUL_BYTES,
        )
    except (OSError, launch_common.LaunchError):
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
        launch_common.TEAM_DIR / "charter.md",
        launch_common.TEAM_DIR / "norms.md",
        *[launch_common.SOULS_DIR / f"{role}.md" for role in sorted(roles)],
        launch_common.PHASES_DIR / phase_slug / "_lead.md",
        launch_common.PHASES_DIR / phase_slug / "_phase.md",
        *[
            launch_common.PHASES_DIR / phase_slug / f"{role}.md"
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


def _method_selection_for_run(
    phase: Mapping[str, Any],
    snapshots: Mapping[str, Any],
    run_specific_method_id: str,
    run_specific_method_version: str,
) -> dict[str, Any] | None:
    """Freeze the exact method identity for Phase 03, Phase 04, and Phase 05 work."""

    phase_slug = str(phase.get("slug", ""))
    method_phase = launch_manifest.phase_requires_method_binding(phase)
    supplied_id = str(run_specific_method_id).strip()
    supplied_version = str(run_specific_method_version).strip()
    if bool(supplied_id) != bool(supplied_version):
        raise launch_common.LaunchError(
            "Supply both the run-specific method ID and version, or neither"
        )
    if not method_phase:
        if supplied_id or supplied_version:
            raise launch_common.LaunchError(
                "A run-specific method identity is not valid for this phase"
            )
        return None
    if phase_slug == launch_common.IDEA_EVALUATION_PHASE and phase.get("audit_only") is True:
        if supplied_id or supplied_version:
            raise launch_common.LaunchError(
                "An audit-only Phase 03 run uses its sealed source artifact"
            )
        return None
    if supplied_id:
        selected = launch_manifest._method_identity(supplied_id, supplied_version)
        return {
            **selected,
            "source": "run_specific_user_selection",
            "source_phase": None,
            "source_run_id": None,
            "decision_record": None,
        }

    raise launch_common.LaunchError(
        "Choose an active method for this run."
    )

def _branch_aware_output_root(
    project_dir: Path,
    phase_folder: str,
    *,
    run_number: int,
    method_selection: Mapping[str, Any] | None,
) -> Path:
    """Compute a run's output directory, redirecting into a branch folder.

    Method-bound runs (Phase 03/04/05 with a sealed method identity) write
    inside ``branches/<stable_id>/<folder>/run/NN/`` so each method's
    artifacts accumulate independently. Runs without a method selection keep
    the legacy flat path ``<folder>/run/NN/``.
    """

    base = Path(str(phase_folder or ""))
    tail = base / "run" / f"{run_number:02d}"
    if method_selection and method_selection.get("stable_id"):
        return project_dir / "branches" / str(method_selection["stable_id"]) / tail
    return project_dir / tail


def _paper_manuscript_paths(output_root: str | Path) -> dict[str, Path]:
    root = Path(output_root).resolve()
    return {
        "review": root / "manuscript-review.md",
        "post_review": root / "manuscript-post-review.md",
        "diff": root / "manuscript-post-review.diff",
        "assembly": root / "manuscript.md",
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
    if launch_common._path_uses_symlink_below(candidate, root):
        raise launch_common.LaunchError(f"{label} must not use symbolic links")
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(root).as_posix()
    except OSError as exc:
        raise launch_common.LaunchError(f"{label} is unavailable") from exc
    except ValueError as exc:
        raise launch_common.LaunchError(f"{label} escaped the project") from exc
    payload = launch_common._bounded_bytes(resolved, label=label, max_bytes=max_bytes)
    try:
        payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise launch_common.LaunchError(f"{label} is not valid UTF-8") from exc
    expected = str(expected_sha256).strip().lower()
    if (
        len(expected) != 64
        or any(character not in "0123456789abcdef" for character in expected)
    ):
        raise launch_common.LaunchError(f"{label} has no valid sealed SHA-256")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected or launch_common._sha256_file(
        resolved, max_bytes=max_bytes, label=label, allow_empty=False
    ) != expected:
        raise launch_common.LaunchError(f"{label} changed after submission")
    if expected_size is not None and len(payload) != expected_size:
        raise launch_common.LaunchError(f"{label} changed size after submission")
    return resolved, payload, relative


def _source_baseline_from_run(
    project_dir: Path,
    phase_slug: str,
    source_run: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the complete decision baseline of one eligible submitted run."""

    source_id = str(source_run.get("run_id", "")).strip()
    status = str(source_run.get("status", "")).strip()
    if status not in launch_common.ELIGIBLE_SOURCE_STATUSES:
        allowed = ", ".join(sorted(launch_common.ELIGIBLE_SOURCE_STATUSES))
        raise launch_common.LaunchError(
            f"The selected source run status is not eligible; choose one of: {allowed}"
        )
    submitted_at = str(source_run.get("submitted_at", "")).strip()
    if not submitted_at or not source_run.get("final_summary"):
        raise launch_common.LaunchError("The selected source run has no completed submission")
    decision_record = source_run.get("decision_record")
    if not isinstance(decision_record, Mapping):
        raise launch_common.LaunchError("The selected source run has no structured decision record")
    try:
        integrity = project_state.run_integrity_report(
            project_dir, phase_slug, source_id
        )
    except (KeyError, OSError, project_state.ProjectStateError) as exc:
        raise launch_common.LaunchError("The selected source run could not be verified") from exc
    if not isinstance(integrity, Mapping) or not integrity.get("ok"):
        reason = str(integrity.get("reason", "")).strip() if isinstance(
            integrity, Mapping
        ) else ""
        detail = f": {reason}" if reason else ""
        raise launch_common.LaunchError(f"The selected source run failed its integrity check{detail}")

    summary_path, summary_payload, summary_relative = _source_file_payload(
        project_dir,
        str(source_run.get("final_summary", "")),
        str(source_run.get("summary_sha256", "")),
        expected_size=None,
        label="selected source final summary",
        max_bytes=launch_common.MAX_SOURCE_SUMMARY_BYTES,
    )
    try:
        decision_size = int(decision_record.get("size", -1))
    except (TypeError, ValueError) as exc:
        raise launch_common.LaunchError("The selected source decision record has an invalid size") from exc
    decision_path, decision_payload, decision_relative = _source_file_payload(
        project_dir,
        str(decision_record.get("path", "")),
        str(decision_record.get("sha256", "")),
        expected_size=decision_size,
        label="selected source decision record",
        max_bytes=launch_common.MAX_SOURCE_DECISION_BYTES,
    )
    try:
        parsed_decision = json.loads(decision_payload.decode("utf-8"))
        normalized_decision = project_state.validate_decision_record(parsed_decision)
    except (UnicodeError, json.JSONDecodeError, project_state.ProjectStateError) as exc:
        raise launch_common.LaunchError("The selected source decision record is invalid") from exc
    decision_schema = decision_record.get("schema_version")
    if (
        decision_schema not in project_state.SUPPORTED_DECISION_RECORD_SCHEMA_VERSIONS
        or normalized_decision.get("schema_version") != decision_schema
    ):
        raise launch_common.LaunchError("The selected source decision record schema is invalid")

    return {
        "schema_version": launch_common.SOURCE_BASELINE_SCHEMA_VERSION,
        "phase_slug": phase_slug,
        "run_id": source_id,
        "status_at_selection": status,
        "source_baseline_status": launch_common.SOURCE_BASELINE_STATUS_BY_RUN_STATUS[status],
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
        raise launch_common.LaunchError("Source-baseline destination escaped run storage") from exc
    launch_common._ensure_contained_directory(
        destination.parent, run_storage, label="source-baseline destination parent"
    )
    if destination.exists() or destination.is_symlink():
        raise launch_common.LaunchError(f"The source-baseline destination already exists: {destination}")
    destination.mkdir()

    def freeze_leaf(
        name: str, filename: str, *, max_bytes: int
    ) -> dict[str, Any]:
        item = source_baseline.get(name)
        if not isinstance(item, Mapping):
            raise launch_common.LaunchError(f"Selected source baseline has no {name}")
        try:
            expected_size = int(item.get("size", -1))
        except (TypeError, ValueError) as exc:
            raise launch_common.LaunchError(f"Selected source baseline {name} has an invalid size") from exc
        source, payload, source_relative = _source_file_payload(
            root,
            str(item.get("source", "")),
            str(item.get("sha256", "")),
            expected_size=expected_size,
            label=f"selected source baseline {name}",
            max_bytes=max_bytes,
        )
        frozen_path = launch_common._contained_file_destination(
            destination / filename,
            run_storage,
            label=f"frozen source baseline {name}",
        )
        if frozen_path.exists():
            raise launch_common.LaunchError(f"Frozen source baseline already exists: {frozen_path}")
        launch_common._write_bytes_atomic(frozen_path, payload)
        expected = str(item.get("sha256", "")).lower()
        if launch_common._sha256_file(
            source,
            max_bytes=max_bytes,
            label=f"selected source baseline {name}",
            allow_empty=False,
        ) != expected or launch_common._sha256_file(
            frozen_path,
            max_bytes=max_bytes,
            label=f"frozen source baseline {name}",
            allow_empty=False,
        ) != expected:
            raise launch_common.LaunchError(f"Selected source baseline {name} changed while copying")
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
        "schema_version": launch_common.SOURCE_BASELINE_SCHEMA_VERSION,
        "phase_slug": str(source_baseline.get("phase_slug", "")),
        "run_id": str(source_baseline.get("run_id", "")),
        "status_at_selection": str(source_baseline.get("status_at_selection", "")),
        "source_baseline_status": _source_baseline_status(source_baseline),
        "submitted_at": str(source_baseline.get("submitted_at", "")),
        "summary": freeze_leaf(
            "summary", "final-summary.html", max_bytes=launch_common.MAX_SOURCE_SUMMARY_BYTES
        ),
        "decision_record": freeze_leaf(
            "decision_record",
            "decision-record.json",
            max_bytes=launch_common.MAX_SOURCE_DECISION_BYTES,
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
        raise launch_common.LaunchError("Frozen source baseline has an invalid inventory")
    status = str(source_baseline.get("status_at_selection", ""))
    if (
        schema_version not in {1, launch_common.SOURCE_BASELINE_SCHEMA_VERSION}
        or source_baseline.get("phase_slug") != expected_phase_slug
        or not str(source_baseline.get("run_id", "")).strip()
        or not str(source_baseline.get("submitted_at", "")).strip()
        or status not in launch_common.ELIGIBLE_SOURCE_STATUSES
        or _source_baseline_status(source_baseline)
        != launch_common.SOURCE_BASELINE_STATUS_BY_RUN_STATUS[status]
    ):
        raise launch_common.LaunchError("Frozen source baseline identity or status is invalid")

    context_root = launch_common.run_context_dir(
        project_dir,
        str(manifest.get("phase_slug", "")),
        str(manifest.get("run_id", "")),
    ).resolve()
    baseline_root = (context_root / relative_directory).resolve()
    try:
        baseline_root.relative_to(context_root)
    except ValueError as exc:
        raise launch_common.LaunchError("Frozen source baseline directory escaped the run context") from exc

    for name, filename, maximum in (
        ("summary", "final-summary.html", launch_common.MAX_SOURCE_SUMMARY_BYTES),
        ("decision_record", "decision-record.json", launch_common.MAX_SOURCE_DECISION_BYTES),
    ):
        item = source_baseline.get(name)
        expected_fields = {"path", "source_path", "sha256", "size"}
        if name == "decision_record":
            expected_fields.add("schema_version")
        if not isinstance(item, Mapping) or set(item) != expected_fields:
            raise launch_common.LaunchError(f"Frozen source baseline {name} record is invalid")
        source_path = str(item.get("source_path", "")).strip()
        if (
            not source_path
            or Path(source_path).is_absolute()
            or ".." in Path(source_path).parts
        ):
            raise launch_common.LaunchError(f"Frozen source baseline {name} path is invalid")
        try:
            expected_size = int(item.get("size", -1))
        except (TypeError, ValueError) as exc:
            raise launch_common.LaunchError(f"Frozen source baseline {name} size is invalid") from exc
        path, payload, _ = _source_file_payload(
            context_root,
            str(item.get("path", "")),
            str(item.get("sha256", "")),
            expected_size=expected_size,
            label=f"frozen source baseline {name}",
            max_bytes=maximum,
        )
        if path != (baseline_root / filename).resolve():
            raise launch_common.LaunchError(f"Frozen source baseline {name} path is invalid")
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
                raise launch_common.LaunchError("Frozen source decision record is invalid") from exc
            if (
                item.get("schema_version")
                not in project_state.SUPPORTED_DECISION_RECORD_SCHEMA_VERSIONS
                or normalized.get("schema_version") != item.get("schema_version")
            ):
                raise launch_common.LaunchError("Frozen source decision record schema is invalid")
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
    if launch_common._path_uses_symlink_below(candidate, root):
        raise launch_common.LaunchError("The selected review target must not use symbolic links")
    try:
        candidate = candidate.resolve(strict=True)
        candidate.relative_to(root)
    except OSError as exc:
        raise launch_common.LaunchError(f"The selected review target is unavailable: {review_target}") from exc
    except ValueError as exc:
        raise launch_common.LaunchError("The selected review target must stay inside the project") from exc
    if candidate.name != "manuscript-post-review.md":
        raise launch_common.LaunchError(
            "A review-only Phase 05 run requires a manuscript-post-review.md target"
        )
    sealed_digest = ""
    source_baseline: dict[str, Any] | None = None
    for recorded_run in project_state.get_runs(root, launch_common.PAPER_WRITING_PHASE):
        if recorded_run.get("status") in project_state.ACTIVE_RUN_STATUSES:
            continue
        run_id = str(recorded_run.get("run_id", ""))
        if not run_id:
            continue
        try:
            manifest = launch_manifest._read_manifest(root, launch_common.PAPER_WRITING_PHASE, run_id)
            output_root = Path(str(manifest["output_root"])).resolve()
            output_root.relative_to(root)
        except (launch_common.LaunchError, OSError, ValueError, KeyError):
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
                root, launch_common.PAPER_WRITING_PHASE, recorded_run
            )
            sealed_digest = recorded_digest
            break
    if not sealed_digest or source_baseline is None:
        raise launch_common.LaunchError(
            "The selected manuscript is not a sealed post-review output of a "
            "recorded Phase 05 run"
        )
    launch_common._read_utf8_bounded(
        candidate,
        label="selected post-review manuscript",
        max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
    )
    expected = str(expected_sha256).strip().lower()
    if (
        len(expected) != 64
        or any(character not in "0123456789abcdef" for character in expected)
    ):
        raise launch_common.LaunchError("The selected review target requires its displayed SHA-256")
    digest = launch_common._sha256_file(
        candidate,
        max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
        label="selected post-review manuscript",
        allow_empty=False,
    )
    if digest != expected or digest != sealed_digest:
        raise launch_common.LaunchError(
            "The selected post-review manuscript does not match its sealed run "
            "record or changed after the page was shown. Reload the phase and choose it again."
        )
    return candidate, digest, source_baseline


def _copy_paper_review_source(
    project_dir: Path, source: Path, destination: Path, sha256: str
) -> None:
    """Copy an exact review source without changing or overwriting either version."""

    destination = launch_common._contained_file_destination(
        destination, project_dir, label="review-only manuscript destination"
    )
    if destination.exists():
        raise launch_common.LaunchError(f"The review-only destination already exists: {destination}")
    payload = launch_common._bounded_bytes(
        source,
        label="selected review target",
        max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
    )
    source_before = hashlib.sha256(payload).hexdigest()
    if source_before != sha256 or launch_common._sha256_file(
        source,
        max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
        label="selected review target",
        allow_empty=False,
    ) != sha256:
        raise launch_common.LaunchError("The selected post-review manuscript changed before copying")
    try:
        launch_common._write_bytes_atomic(destination, payload)
    except OSError as exc:
        raise launch_common.LaunchError(f"Could not preserve the selected review target: {source}") from exc
    source_after = launch_common._sha256_file(
        source,
        max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
        label="selected review target",
        allow_empty=False,
    )
    destination_digest = launch_common._sha256_file(
        destination,
        max_bytes=launch_common.MAX_REVIEW_MANUSCRIPT_BYTES,
        label="preserved review target",
        allow_empty=False,
    )
    if source_after != sha256 or destination_digest != sha256:
        try:
            destination.unlink()
        except OSError:
            pass
        raise launch_common.LaunchError("The selected review target changed while it was being preserved")


def _resolve_theory_audit_source(
    project_dir: str | Path, source_run_id: str
) -> dict[str, Any]:
    """Resolve one exact final theorist artifact from sealed Phase 03 records."""

    root = Path(project_dir).resolve()
    source_id = str(source_run_id).strip()
    if not source_id or len(source_id) > 256:
        raise launch_common.LaunchError("Select a valid source run for the proof audit")
    try:
        source_run = project_state.get_run(
            root, launch_common.IDEA_EVALUATION_PHASE, source_id
        )
    except (KeyError, project_state.ProjectStateError) as exc:
        raise launch_common.LaunchError("The selected proof-audit source run is unavailable") from exc
    source_baseline = _source_baseline_from_run(
        root, launch_common.IDEA_EVALUATION_PHASE, source_run
    )

    source_manifest = launch_manifest._read_manifest(
        root, launch_common.IDEA_EVALUATION_PHASE, source_id
    )
    launch_manifest._verify_frozen_inputs(
        root, launch_common.IDEA_EVALUATION_PHASE, source_id, source_manifest
    )
    stages = list(source_manifest.get("phase", {}).get("stages", []))
    theorist_rounds = [
        index
        for index, stage in enumerate(stages, 1)
        if isinstance(stage, Mapping) and str(stage.get("role")) == "theorist"
    ]
    if not theorist_rounds:
        raise launch_common.LaunchError(
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
        raise launch_common.LaunchError(
            "The selected source run has no completed final theorist stage"
        )
    target = launch_dispatch._planned_output(source_manifest, target_round, "theorist")
    if target.is_symlink():
        raise launch_common.LaunchError("The selected final theory artifact cannot be a symbolic link")
    try:
        target = target.resolve(strict=True)
        target.relative_to(root)
    except OSError as exc:
        raise launch_common.LaunchError("The selected final theory artifact is unavailable") from exc
    except ValueError as exc:
        raise launch_common.LaunchError("The selected final theory artifact escaped the project") from exc
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
        raise launch_common.LaunchError("The selected final theory artifact has no sealed record")

    def checked_source(
        path: Path, record: Mapping[str, Any], purpose: str
    ) -> dict[str, Any]:
        expected = str(record.get("sha256", "")).lower()
        payload = launch_prompts._review_source_payload(path, expected, purpose)
        try:
            recorded_size = int(record.get("size", -1))
        except (TypeError, ValueError) as exc:
            raise launch_common.LaunchError(f"Sealed evidence has an invalid size: {purpose}") from exc
        if recorded_size != len(payload):
            raise launch_common.LaunchError(f"Sealed evidence changed size: {purpose}")
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
        payload = launch_prompts._review_source_payload(
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
        "phase_slug": launch_common.IDEA_EVALUATION_PHASE,
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
        manifest = launch_manifest._read_manifest(root, phase_slug, str(run_id).strip())
    except (KeyError, project_state.ProjectStateError) as exc:
        raise launch_common.LaunchError("The prior run is unavailable") from exc
    frozen_phase = manifest.get("phase")
    if (
        not isinstance(frozen_phase, Mapping)
        or frozen_phase.get("slug") != phase_slug
    ):
        raise launch_common.LaunchError("The prior run has no verified frozen phase plan")

    if phase_slug == project_state.METHOD_DEVELOPMENT_PHASE:
        run_scope = manifest.get("run_scope")
        if not isinstance(run_scope, Mapping):
            return {"kind": "standard"}
        result = {
            "kind": "method_scope",
            "method_catalog_scope": str(run_scope.get("scope", "")).strip(),
        }
        focused_id = str(run_scope.get("focused_method_id") or "").strip()
        if focused_id:
            result["focused_method_id"] = focused_id
        return result

    if phase_slug == launch_common.IDEA_EVALUATION_PHASE:
        context_policy = manifest.get("context_policy")
        preserved_policy = (
            str(context_policy.get("policy", "")).strip()
            if isinstance(context_policy, Mapping)
            else ""
        )
        plan = str(frozen_phase.get("run_plan", "")).strip()
        if not plan:
            if frozen_phase.get("audit_only"):
                plan = launch_common.THEORY_PLAN_AUDIT_ONLY
            elif frozen_phase.get("proof_audit"):
                plan = launch_common.THEORY_PLAN_STANDARD_WITH_AUDIT
        if not plan:
            # A phase without declared theory plans (for example a debate)
            # records no special plan; preserving it is a plain rerun.
            result = {"kind": "standard"}
            if preserved_policy:
                result["theory_context_policy"] = preserved_policy
            return result
        if plan not in launch_common.THEORY_RUN_PLANS:
            raise launch_common.LaunchError("The prior Phase 03 run plan cannot be reproduced")
        result = {"kind": "theory", "theory_plan": plan}
        if preserved_policy:
            result["theory_context_policy"] = preserved_policy
        if plan == launch_common.THEORY_PLAN_AUDIT_ONLY:
            try:
                frozen_source = _verified_frozen_theory_audit_source(root, manifest)
            except project_state.ProjectStateError as exc:
                raise launch_common.LaunchError("The prior proof-audit source is unavailable") from exc
            source_run_id = str(frozen_source.get("run_id", "")).strip()
            frozen_target = frozen_source.get("target")
            if not source_run_id or not isinstance(frozen_target, Mapping):
                raise launch_common.LaunchError("The prior proof-audit source is incomplete")
            try:
                current_source = _resolve_theory_audit_source(root, source_run_id)
            except project_state.ProjectStateError as exc:
                raise launch_common.LaunchError("The prior proof-audit source is unavailable") from exc
            current_target = current_source.get("target")
            if (
                not isinstance(current_target, Mapping)
                or str(current_target.get("sha256", "")).lower()
                != str(frozen_target.get("sha256", "")).lower()
            ):
                raise launch_common.LaunchError(
                    "The selected proof-audit source changed after the prior run"
                )
            result["proof_audit_source_run_id"] = source_run_id
            result["source_sha256"] = str(
                frozen_target.get("sha256", "")
            ).lower()
        return result

    if phase_slug == launch_common.DRAFT_ASSEMBLY_PHASE:
        plan = str(frozen_phase.get("run_plan", "")).strip()
        if not plan:
            # A Phase 04 run from before run_modes shipped records no plan;
            # preserving it is a plain rerun.
            return {"kind": "standard"}
        if plan not in launch_common.RUN_MODES:
            raise launch_common.LaunchError("The prior Phase 04 run mode cannot be reproduced")
        return {"kind": "run_mode", "run_mode": plan}

    if phase_slug == launch_common.PAPER_WRITING_PHASE:
        plan = str(frozen_phase.get("run_plan", "")).strip()
        if plan in launch_common.PAPER_RUN_MODES:
            return {"kind": "run_mode", "run_mode": plan}
        # Legacy Phase 05 runs from before run_modes shipped
        paper_review = manifest.get("paper_review")
        if not isinstance(paper_review, Mapping):
            if plan:
                raise launch_common.LaunchError("The prior Phase 05 run plan cannot be reproduced")
            return {"kind": "standard"}
        kind = str(paper_review.get("kind", ""))
        if kind == "full":
            return {"kind": "paper_full"}
        if kind != "review_only":
            raise launch_common.LaunchError("The prior Phase 05 run plan cannot be reproduced")
        try:
            source_path, source_digest, _source_baseline = _resolve_paper_review_source(
                root,
                str(paper_review.get("source_path", "")),
                str(paper_review.get("source_sha256", "")),
            )
        except project_state.ProjectStateError as exc:
            raise launch_common.LaunchError("The prior manuscript source is unavailable") from exc
        return {
            "kind": "paper_review_only",
            "review_target": source_path.relative_to(root).as_posix(),
            "review_target_sha256": source_digest,
        }

    raise launch_common.LaunchError("Exact plan preservation is only available for Phase 03, Phase 04, and Phase 05")


def theory_audit_source_options(project_dir: str | Path) -> list[dict[str, Any]]:
    """List source run identities whose final theorist artifact still verifies."""

    root = Path(project_dir).resolve()
    options: list[dict[str, Any]] = []
    for number, run in enumerate(
        project_state.get_runs(root, launch_common.IDEA_EVALUATION_PHASE), 1
    ):
        source_id = str(run.get("run_id", ""))
        if not source_id:
            continue
        try:
            source = _resolve_theory_audit_source(root, source_id)
        except (launch_common.LaunchError, project_state.ProjectStateError):
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
        launch_common.run_context_dir(project_dir, launch_common.IDEA_EVALUATION_PHASE, run_id)
        / "proof-audit"
    )
    destination.mkdir(parents=True, exist_ok=False)

    def freeze(
        item: Mapping[str, Any], filename: str, *, target: bool = False
    ) -> dict[str, Any]:
        source_path = Path(str(item.get("source", "")))
        expected = str(item.get("sha256", "")).lower()
        payload = launch_prompts._review_source_payload(
            source_path, expected, str(item.get("purpose", "proof-audit evidence"))
        )
        if len(payload) != int(item.get("size", -1)):
            raise launch_common.LaunchError("Proof-audit evidence changed while the run was prepared")
        frozen_path = destination / filename
        launch_common._write_bytes_atomic(frozen_path, payload)
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
        raise launch_common.LaunchError("The selected proof-audit source has no complete baseline")
    frozen_baseline = _freeze_source_baseline(
        project_dir,
        destination / "source-baseline",
        source_baseline,
    )
    return {
        "schema_version": 2,
        "phase_slug": launch_common.IDEA_EVALUATION_PHASE,
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
        raise launch_common.LaunchError("The audit-only run has no frozen source record")
    source_schema = source.get("schema_version")
    if (
        source_schema not in {1, 2}
        or source.get("phase_slug") != launch_common.IDEA_EVALUATION_PHASE
        or not str(source.get("run_id", "")).strip()
    ):
        raise launch_common.LaunchError("The audit-only source identity is invalid")
    target = source.get("target")
    evidence = source.get("evidence")
    if not isinstance(target, Mapping) or not isinstance(evidence, list):
        raise launch_common.LaunchError("The audit-only source inventory is invalid")
    context_root = launch_common.run_context_dir(
        project_dir,
        str(manifest.get("phase_slug", "")),
        str(manifest.get("run_id", "")),
    ).resolve()
    total = 0
    for label, item in [("target", target), *[
        (f"evidence[{index}]", value) for index, value in enumerate(evidence)
    ]]:
        if not isinstance(item, Mapping):
            raise launch_common.LaunchError(f"Audit-only {label} record is invalid")
        raw_path = Path(str(item.get("path", "")))
        if launch_common._path_uses_symlink_below(raw_path, context_root / "proof-audit"):
            raise launch_common.LaunchError(f"Audit-only {label} cannot be a symbolic link")
        try:
            path = raw_path.resolve(strict=True)
            path.relative_to(context_root / "proof-audit")
            size = int(item.get("size", -1))
        except (OSError, TypeError, ValueError) as exc:
            raise launch_common.LaunchError(f"Audit-only {label} is unavailable") from exc
        payload = launch_prompts._review_source_payload(
            path, str(item.get("sha256", "")), f"audit-only {label}"
        )
        if size != len(payload):
            raise launch_common.LaunchError(f"Audit-only {label} changed size")
        total += size
    if total > launch_common.MAX_REVIEW_BUNDLE_BYTES:
        raise launch_common.LaunchError("Audit-only target and evidence exceed the safety limit")
    if source_schema == 2:
        _verified_frozen_source_baseline(
            project_dir,
            manifest,
            source.get("source_baseline"),
            expected_phase_slug=launch_common.IDEA_EVALUATION_PHASE,
            relative_directory="proof-audit/source-baseline",
        )
    elif source.get("source_baseline") is not None:
        raise launch_common.LaunchError("Legacy audit-only source has unexpected baseline metadata")
    return source
