#!/usr/bin/env python3

"""Run manifest construction helpers and frozen-input validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Mapping



from core import launch_common
from core import project_state
from core import profile_skills
from core import launch_plans

import logging
log = logging.getLogger(__name__)

MANIFEST_SCHEMA_VERSION = 11


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
            raise launch_common.LaunchError(f"The method {label.replace('_', ' ')} is invalid")
        if any(
            not (
                character.isascii()
                and (character.isalnum() or character in {"-", "_", ".", "/"})
            )
            for character in value
        ):
            raise launch_common.LaunchError(
                f"The method {label.replace('_', ' ')} must use ASCII letters, "
                "digits, hyphens, underscores, periods, or slashes"
            )
    return normalized


def phase_requires_method_binding(phase: Mapping[str, Any]) -> bool:
    """True when a run of this phase must freeze an exact method identity.

    The binding is config-driven: a phase opts in with ``method_binding:
    true``. The Phase 03 and Phase 04 slugs keep the historical binding
    unless the phase has been repurposed to a parallel or debate layout, so
    manifests sealed under the legacy plans continue to validate while
    repurposed phases on the same slugs do not inherit it.
    """

    if phase.get("method_binding") is True:
        return True
    return project_state._resolve_slug(str(phase.get("slug", ""))) in {
        launch_common.IDEA_EVALUATION_PHASE,
        launch_common.DRAFT_ASSEMBLY_PHASE,
    } and str(phase.get("pattern", "")) not in {"parallel", "debate"}


def phase_uses_catalog_method_selection(phase: Mapping[str, Any]) -> bool:
    """True when the user must choose a current Phase 2 catalog entry."""

    return (
        phase_requires_method_binding(phase)
        and project_state._resolve_slug(str(phase.get("slug", "")))
        in {
            launch_common.IDEA_EVALUATION_PHASE,
            launch_common.DRAFT_ASSEMBLY_PHASE,
            launch_common.PAPER_WRITING_PHASE,
        }
        and phase.get("audit_only") is not True
    )


def _manifest_declares_protocol_checkpoint(manifest: Mapping[str, Any]) -> bool:
    """True when the frozen run plan carries a protocol checkpoint."""

    return isinstance(manifest.get("protocol_checkpoint"), Mapping)


def _snapshot_leaf(
    value: Any, label: str, *, allow_extra: bool = False
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise launch_common.LaunchError(f"Frozen snapshot {label} must be a mapping")
    keys = set(value)
    required = {"path", "sha256"}
    if not required.issubset(keys) or (not allow_extra and keys != required):
        qualifier = "contain" if allow_extra else "contain exactly"
        raise launch_common.LaunchError(
            f"Frozen snapshot {label} must {qualifier} path and sha256"
        )
    path = value.get("path")
    digest = value.get("sha256")
    if not isinstance(path, str) or not path.strip():
        raise launch_common.LaunchError(f"Frozen snapshot {label}.path must be a nonempty string")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in digest)
    ):
        raise launch_common.LaunchError(f"Frozen snapshot {label}.sha256 must be a SHA-256 digest")
    return value


def _manifest_schema_version(manifest: Mapping[str, Any]) -> int:
    value = manifest.get("schema_version", 1)
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value not in range(1, MANIFEST_SCHEMA_VERSION + 1)
    ):
        raise launch_common.LaunchError(f"Unsupported run manifest schema version: {value!r}")
    return value


def _manifest_hermes_root(manifest: Mapping[str, Any]) -> Path | None:
    """Return a sealed Hermes root, while retaining manifests created earlier."""

    value = manifest.get("hermes_root")
    if value is None:
        return None
    if not isinstance(value, str) or not value or "\x00" in value:
        raise launch_common.LaunchError("Run manifest hermes_root must be a nonempty path")
    root = Path(value)
    normalized = Path(os.path.abspath(value))
    if not root.is_absolute() or normalized != root or str(root) != value:
        raise launch_common.LaunchError("Run manifest hermes_root must be an absolute normalized path")
    return root


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
        raise launch_common.LaunchError("Run manifest recommended_skills has an invalid structure")
    if snapshot.get("schema_version") != 1:
        raise launch_common.LaunchError("Run manifest recommended_skills schema is unsupported")
    source_revision = snapshot.get("source_revision")
    if source_revision is not None and (
        not isinstance(source_revision, str)
        or len(source_revision) != 40
        or any(character not in "0123456789abcdef" for character in source_revision)
    ):
        raise launch_common.LaunchError("Run manifest recommended skill revision is invalid")
    roles = snapshot.get("roles")
    if not isinstance(roles, Mapping) or len(roles) > 32:
        raise launch_common.LaunchError("Run manifest recommended skill roles are invalid")
    if source_revision is None and roles:
        raise launch_common.LaunchError("Unavailable recommended skills must not declare role state")
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
            raise launch_common.LaunchError("Run manifest recommended skill role is invalid")
        if not isinstance(role_record, Mapping) or set(role_record) != {
            "profile",
            "skills",
        }:
            raise launch_common.LaunchError(
                f"Run manifest recommended skills for {role} are invalid"
            )
        profile = role_record.get("profile")
        skills = role_record.get("skills")
        if not isinstance(profile, str) or not isinstance(skills, list):
            raise launch_common.LaunchError(
                f"Run manifest recommended skills for {role} are invalid"
            )
        names: set[str] = set()
        for record in skills:
            if not isinstance(record, Mapping) or set(record) != skill_keys:
                raise launch_common.LaunchError(
                    f"Run manifest recommended skill record for {role} is invalid"
                )
            name = record.get("name")
            state = record.get("state")
            reason = record.get("reason")
            installed_digest = record.get("installed_digest")
            if not isinstance(name, str) or not name or name in names:
                raise launch_common.LaunchError(
                    f"Run manifest recommended skill name for {role} is invalid"
                )
            names.add(name)
            if state not in status_states or not isinstance(reason, str) or not reason:
                raise launch_common.LaunchError(
                    f"Run manifest recommended skill status for {role} is invalid"
                )
            if not launch_common._is_sha256_digest(record.get("expected_digest")):
                raise launch_common.LaunchError(
                    f"Run manifest recommended skill digest for {role} is invalid"
                )
            if installed_digest is not None and not launch_common._is_sha256_digest(
                installed_digest
            ):
                raise launch_common.LaunchError(
                    f"Run manifest installed skill digest for {role} is invalid"
                )
            if record.get("source_revision") != source_revision:
                raise launch_common.LaunchError(
                    f"Run manifest recommended skill revision for {role} is invalid"
                )
            if not isinstance(record.get("profile_path"), str):
                raise launch_common.LaunchError(
                    f"Run manifest recommended skill path for {role} is invalid"
                )
            if type(record.get("managed")) is not bool or type(
                record.get("preload")
            ) is not bool:
                raise launch_common.LaunchError(
                    f"Run manifest recommended skill flags for {role} are invalid"
                )
            if record["preload"] and (
                state != "current"
                or installed_digest != record["expected_digest"]
                or not launch_plans._should_preload_recommended_skill(
                    phase_slug,
                    role,
                    name,
                    review_only=review_only,
                )
            ):
                raise launch_common.LaunchError(
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
        raise launch_common.LaunchError("The run has no valid Hermes profile mapping")
    mapped_profile = str(manifest_profiles.get(role, ""))
    if not profile or profile != mapped_profile:
        raise launch_common.LaunchError(
            f"The recorded Hermes profile for {role} no longer matches the run"
        )
    names = [str(record["name"]) for record in records]
    try:
        bundled = profile_skills.load_manifest()
        requirements = set(
            profile_skills.role_requirements(role, manifest=bundled)
        )
        if not set(names).issubset(requirements):
            raise launch_common.LaunchError(
                f"The bundled skill recommendation for {role} changed after launch"
            )
        statuses = profile_skills.profile_skill_statuses(
            profile,
            names,
            manifest=bundled,
            hermes_root=_manifest_hermes_root(manifest),
        )
    except launch_common.LaunchError:
        raise
    except (profile_skills.ProfileSkillsError, OSError, ValueError, KeyError) as exc:
        raise launch_common.LaunchError(
            f"The recommended skill for {role} could not be verified before use"
        ) from exc
    for record in records:
        name = str(record["name"])
        live = launch_plans._recommended_skill_status_record(statuses[name], preload=True)
        stable_fields = (
            "name",
            "state",
            "expected_digest",
            "installed_digest",
            "source_revision",
            "profile_path",
        )
        if any(live[field] != record[field] for field in stable_fields):
            raise launch_common.LaunchError(
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
        raise launch_common.LaunchError("Run manifest phase must be a mapping")
    members = phase.get("members")
    if not isinstance(members, list) or any(
        not isinstance(role, str) or not role for role in members
    ):
        raise launch_common.LaunchError("Run manifest phase members must be a list of role names")
    # F16: validate run_plan if present; it must be a recognized theory plan
    # or run mode. An empty string is acceptable (no plan specified).
    raw_plan = phase.get("run_plan", "")
    if isinstance(raw_plan, str) and raw_plan:
        valid_plans = launch_common.THEORY_RUN_PLANS | launch_common.RUN_MODES | launch_common.PAPER_RUN_MODES
        if raw_plan not in valid_plans:
            raise launch_common.LaunchError(
                f"Run manifest phase run_plan has unrecognized value: {raw_plan!r}"
            )
    required_roles = set(members) | {"research_lead"}
    snapshots = manifest.get("snapshots")
    if not isinstance(snapshots, Mapping):
        raise launch_common.LaunchError("Run manifest snapshots must be a mapping")
    required_snapshot_keys = {"setting", "team", "souls", "playbooks", "summaries"}
    requires_method_snapshot = bool(
        _manifest_schema_version(manifest) >= 10
        and phase_requires_method_binding(phase)
        and phase.get("audit_only") is not True
    )
    if requires_method_snapshot:
        required_snapshot_keys.add("selected_method")
    if set(snapshots) != required_snapshot_keys:
        expected = ", ".join(sorted(required_snapshot_keys))
        raise launch_common.LaunchError(
            f"Run manifest snapshots must contain exactly: {expected}"
        )
    _snapshot_leaf(snapshots.get("setting"), "setting")

    team = snapshots.get("team")
    if not isinstance(team, Mapping) or set(team) != {"charter", "norms"}:
        raise launch_common.LaunchError("Frozen snapshot team must contain exactly charter and norms")
    _snapshot_leaf(team.get("charter"), "team.charter")
    _snapshot_leaf(team.get("norms"), "team.norms")

    souls = snapshots.get("souls")
    if not isinstance(souls, Mapping) or set(souls) != required_roles:
        expected = ", ".join(sorted(required_roles))
        raise launch_common.LaunchError(f"Frozen snapshot souls must contain exactly: {expected}")
    for role in sorted(required_roles):
        _snapshot_leaf(souls.get(role), f"souls.{role}")

    required_playbooks = {"_lead.md", "_phase.md"} | {
        f"{role}.md" for role in members
    }
    playbooks = snapshots.get("playbooks")
    if not isinstance(playbooks, Mapping) or set(playbooks) != required_playbooks:
        expected = ", ".join(sorted(required_playbooks))
        raise launch_common.LaunchError(f"Frozen snapshot playbooks must contain exactly: {expected}")
    for name in sorted(required_playbooks):
        _snapshot_leaf(playbooks.get(name), f"playbooks.{name}")

    summaries = snapshots.get("summaries")
    if not isinstance(summaries, list):
        raise launch_common.LaunchError("Frozen snapshot summaries must be a list")
    schema_version = _manifest_schema_version(manifest)
    valid_context_outcomes = {"Complete", "Partial", "Failed", "Missing"}
    for index, entry in enumerate(summaries):
        _snapshot_leaf(entry, f"summaries[{index}]", allow_extra=True)
        if schema_version >= 11:
            required_context_fields = {
                "supporting_artifacts",
                "protocol_artifacts",
                "scientific_outcome",
            }
            if not required_context_fields.issubset(entry):
                raise launch_common.LaunchError(
                    "Schema-11 frozen context summary must contain supporting_artifacts, "
                    "protocol_artifacts, and scientific_outcome"
                )
            outcome = entry.get("scientific_outcome")
            if (
                outcome not in valid_context_outcomes
                or type(entry.get("trusted")) is not bool
                or type(entry.get("usable")) is not bool
                or not isinstance(entry.get("evidence_status"), str)
                or not entry.get("evidence_status", "").strip()
            ):
                raise launch_common.LaunchError(
                    "Schema-11 frozen context summary has invalid scientific status metadata"
                )
            if outcome in {"Failed", "Missing"} and (
                entry.get("trusted") or entry.get("usable")
            ):
                raise launch_common.LaunchError(
                    "Failed or missing scientific context must remain advisory"
                )
            decision = entry.get("decision_record")
            if outcome == "Missing":
                if decision is not None:
                    raise launch_common.LaunchError(
                        "Context with a missing scientific outcome must not claim a decision record"
                    )
            else:
                decision_leaf = _snapshot_leaf(
                    decision,
                    f"summaries[{index}].decision_record",
                    allow_extra=True,
                )
                expected_decision_fields = {
                    "path",
                    "sha256",
                    "size",
                    "schema_version",
                    "selected_scientific_object",
                    "scientific_outcome",
                }
                if (
                    set(decision_leaf) != expected_decision_fields
                    or decision_leaf.get("scientific_outcome") != outcome
                    or isinstance(decision_leaf.get("size"), bool)
                    or not isinstance(decision_leaf.get("size"), int)
                    or decision_leaf["size"] < 1
                    or decision_leaf["size"] > launch_common.MAX_SOURCE_DECISION_BYTES
                    or decision_leaf.get("schema_version")
                    not in project_state.SUPPORTED_DECISION_RECORD_SCHEMA_VERSIONS
                ):
                    raise launch_common.LaunchError(
                        "Schema-11 frozen context decision record has invalid metadata"
                    )

        discussion = entry.get("discussion", [])
        if not isinstance(discussion, list):
            raise launch_common.LaunchError(
                f"Frozen snapshot summaries[{index}].discussion must be a list"
            )
        discussion_paths: set[str] = set()
        for discussion_index, record in enumerate(discussion):
            leaf = _snapshot_leaf(
                record,
                f"summaries[{index}].discussion[{discussion_index}]",
                allow_extra=True,
            )
            if set(leaf) != {"path", "sha256", "size", "round", "role"}:
                raise launch_common.LaunchError(
                    "Frozen prior discussion record has an invalid structure"
                )
            if (
                isinstance(leaf.get("size"), bool)
                or not isinstance(leaf.get("size"), int)
                or leaf["size"] < 1
                or leaf["size"] > project_state.MAX_RUN_ARTIFACT_BYTES
                or isinstance(leaf.get("round"), bool)
                or not isinstance(leaf.get("round"), int)
                or leaf["round"] < 1
                or not isinstance(leaf.get("role"), str)
                or not leaf["role"].strip()
                or leaf["path"] in discussion_paths
            ):
                raise launch_common.LaunchError(
                    "Frozen prior discussion record has invalid metadata"
                )
            discussion_paths.add(str(leaf["path"]))

        if schema_version >= 11 and "supporting_artifacts" not in entry:
            raise launch_common.LaunchError(
                "Schema-11 frozen context has no supporting artifact inventory"
            )
        supporting = entry.get("supporting_artifacts", [])
        if not isinstance(supporting, list):
            raise launch_common.LaunchError(
                f"Frozen prior supporting artifacts in summary {index} must be a list"
            )
        supporting_counts: dict[int, int] = {}
        supporting_sizes: dict[int, int] = {}
        supporting_paths: set[str] = set()
        supporting_sources: set[str] = set()
        for supporting_index, record in enumerate(supporting):
            leaf = _snapshot_leaf(
                record,
                f"summaries[{index}].supporting_artifacts[{supporting_index}]",
                allow_extra=True,
            )
            if set(leaf) != {"path", "sha256", "size", "round", "source_path"}:
                raise launch_common.LaunchError(
                    "Frozen prior supporting artifact record has an invalid structure"
                )
            size = leaf.get("size")
            round_n = leaf.get("round")
            source_path = leaf.get("source_path")
            if (
                isinstance(size, bool)
                or not isinstance(size, int)
                or size < 1
                or size > project_state.MAX_RUN_ARTIFACT_BYTES
                or isinstance(round_n, bool)
                or not isinstance(round_n, int)
                or round_n < 1
                or not isinstance(source_path, str)
                or not source_path.strip()
                or "\x00" in source_path
                or Path(source_path).is_absolute()
                or Path(source_path).as_posix() != source_path
                or ".." in Path(source_path).parts
                or leaf["path"] in supporting_paths
                or source_path in supporting_sources
            ):
                raise launch_common.LaunchError(
                    "Frozen prior supporting artifact record has invalid metadata"
                )
            supporting_paths.add(str(leaf["path"]))
            supporting_sources.add(source_path)
            supporting_counts[round_n] = supporting_counts.get(round_n, 0) + 1
            supporting_sizes[round_n] = supporting_sizes.get(round_n, 0) + size
            if (
                supporting_counts[round_n] > project_state.MAX_ROUND_SUPPORTING_FILES
                or supporting_sizes[round_n] > project_state.MAX_ROUND_SUPPORTING_BYTES
            ):
                raise launch_common.LaunchError(
                    "Frozen prior supporting artifacts exceed a round safety limit"
                )

        if schema_version >= 11 and "protocol_artifacts" not in entry:
            raise launch_common.LaunchError(
                "Schema-11 frozen context has no protocol artifact inventory"
            )
        protocol = entry.get("protocol_artifacts", [])
        if not isinstance(protocol, list):
            raise launch_common.LaunchError(
                f"Frozen prior protocol artifacts in summary {index} must be a list"
            )
        protocol_paths: set[str] = set()
        protocol_kinds: dict[str, int] = {}
        protocol_file_count = 0
        protocol_file_size = 0
        for protocol_index, record in enumerate(protocol):
            leaf = _snapshot_leaf(
                record,
                f"summaries[{index}].protocol_artifacts[{protocol_index}]",
                allow_extra=True,
            )
            if set(leaf) != {"path", "sha256", "size", "kind", "purpose"}:
                raise launch_common.LaunchError(
                    "Frozen prior protocol artifact record has an invalid structure"
                )
            size = leaf.get("size")
            kind = leaf.get("kind")
            purpose = leaf.get("purpose")
            if (
                isinstance(size, bool)
                or not isinstance(size, int)
                or size < 1
                or kind not in {"checkpoint", "protocol_file", "protocol_report"}
                or not isinstance(purpose, str)
                or not purpose.strip()
                or len(purpose) > 1_000
                or leaf["path"] in protocol_paths
            ):
                raise launch_common.LaunchError(
                    "Frozen prior protocol artifact record has invalid metadata"
                )
            maximum = (
                project_state.MAX_PROTOCOL_CHECKPOINT_BYTES
                if kind == "checkpoint"
                else project_state.MAX_RUN_ARTIFACT_BYTES
            )
            if size > maximum:
                raise launch_common.LaunchError(
                    "Frozen prior protocol artifact exceeds its file safety limit"
                )
            protocol_paths.add(str(leaf["path"]))
            protocol_kinds[kind] = protocol_kinds.get(kind, 0) + 1
            if kind == "protocol_file":
                protocol_file_count += 1
                protocol_file_size += size
        if (
            protocol_kinds.get("checkpoint", 0) > 1
            or protocol_kinds.get("protocol_report", 0) > 1
            or protocol_file_count > project_state.MAX_PROTOCOL_CHECKPOINT_FILES
            or protocol_file_size
            > project_state.MAX_PROTOCOL_CHECKPOINT_AGGREGATE_BYTES
        ):
            raise launch_common.LaunchError(
                "Frozen prior protocol artifacts exceed a checkpoint safety limit"
            )
    if requires_method_snapshot:
        selected_method = _snapshot_leaf(
            snapshots.get("selected_method"),
            "selected_method",
            allow_extra=True,
        )
        expected_method_fields = {
            "path",
            "sha256",
            "stable_id",
            "version",
            "label",
            "catalog_path",
        }
        if set(selected_method) != expected_method_fields:
            raise launch_common.LaunchError(
                "Frozen snapshot selected_method has an invalid structure"
            )
        selection = manifest.get("method_selection")
        if not isinstance(selection, Mapping):
            raise launch_common.LaunchError(
                "The selected method snapshot has no frozen method identity"
            )
        identity = _method_identity(
            str(selection.get("stable_id", "")),
            str(selection.get("version", "")),
        )
        if (
            selected_method.get("stable_id") != identity["stable_id"]
            or selected_method.get("version") != identity["version"]
        ):
            raise launch_common.LaunchError(
                "The selected method snapshot does not match the frozen method identity"
            )
        if not str(selected_method.get("catalog_path", "")).strip():
            raise launch_common.LaunchError(
                "The selected method snapshot has no published catalog path"
            )
    if _manifest_schema_version(manifest) >= 3:
        outputs = manifest.get("submission_outputs")
        if not isinstance(outputs, Mapping):
            raise launch_common.LaunchError("Run manifest submission_outputs must be a mapping")
        phase_slug = str(manifest.get("phase_slug", ""))
        paper_review = manifest.get("paper_review")
        full_paper_run = (
            phase_slug == launch_common.PAPER_WRITING_PHASE
            and isinstance(paper_review, Mapping)
            and paper_review.get("kind") == "full"
        )
        assembly_paper_run = (
            phase_slug == launch_common.PAPER_WRITING_PHASE
            and isinstance(paper_review, Mapping)
            and paper_review.get("kind") == "assembly"
        )
        # R5: assembly runs expect {assembly_manuscript}; full runs expect
        # {post_review_manuscript, review_diff}; other runs expect {}.
        if assembly_paper_run:
            expected_names = {"assembly_manuscript"}
        elif full_paper_run:
            expected_names = {"post_review_manuscript", "review_diff"}
        else:
            expected_names = set()
        if set(outputs) != expected_names:
            raise launch_common.LaunchError(
                "Run manifest submission_outputs do not match the selected run variant"
            )
        expected_paths = launch_plans._paper_manuscript_paths(str(manifest.get("output_root", "")))
        if assembly_paper_run:
            expected = {
                "assembly_manuscript": (expected_paths["assembly"], False),
            }
        elif full_paper_run:
            expected = {
                "post_review_manuscript": (expected_paths["post_review"], False),
                "review_diff": (expected_paths["diff"], True),
            }
        else:
            expected = {}
        for name, (expected_path, allow_empty) in expected.items():
            record = outputs.get(name)
            if not isinstance(record, Mapping):
                raise launch_common.LaunchError(f"Submission output {name} must be a mapping")
            if set(record) != {"path", "allow_empty"}:
                raise launch_common.LaunchError(
                    f"Submission output {name} must contain path and allow_empty"
                )
            if Path(str(record.get("path", ""))).resolve() != expected_path.resolve():
                raise launch_common.LaunchError(
                    f"Submission output {name} does not match the Phase 05 plan"
                )
            if record.get("allow_empty") is not allow_empty:
                raise launch_common.LaunchError(
                    f"Submission output {name} has an invalid empty-file policy"
                )
    if _manifest_schema_version(manifest) >= 4:
        decision_path = manifest.get("decision_path")
        summary_path = manifest.get("summary_path")
        if not isinstance(decision_path, str) or not decision_path.strip():
            raise launch_common.LaunchError("Run manifest decision_path must be a nonempty string")
        if not isinstance(summary_path, str) or not summary_path.strip():
            raise launch_common.LaunchError("Run manifest summary_path must be a nonempty string")
        expected_decision_path = Path(summary_path).with_suffix(".decision.json").resolve()
        if Path(decision_path).resolve() != expected_decision_path:
            raise launch_common.LaunchError(
                "Run manifest decision_path must be beside the immutable summary"
            )
    if _manifest_schema_version(manifest) >= 8:
        for field in ("phase_plan_version", "prerequisite_report_version"):
            digest = str(manifest.get(field, "")).strip().lower()
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise launch_common.LaunchError(f"Run manifest {field} must be a SHA-256 digest")
        _validated_manifest_method_selection(manifest)
    if _manifest_schema_version(manifest) >= 5:
        phase_slug = str(manifest.get("phase_slug", ""))
        declared = manifest.get("protocol_checkpoint")
        phase_declares = bool(phase.get("protocol_checkpoint"))
        repurposed = str(phase.get("pattern", "")) in {"parallel", "debate"}
        legacy_checkpoint_phase = (
            project_state._resolve_slug(phase_slug)
            == launch_common.DRAFT_ASSEMBLY_PHASE
            and not repurposed
        )
        if declared is None:
            if phase_declares or legacy_checkpoint_phase:
                raise launch_common.LaunchError(
                    "The run manifest schema requires a declared protocol "
                    "checkpoint for this phase"
                )
            return
        if not phase_declares and not legacy_checkpoint_phase:
            raise launch_common.LaunchError(
                "A protocol checkpoint declaration is valid only for Phase 04 "
                "legacy runs or a phase whose configuration opts in"
            )
        required_checkpoint_fields = {
            "schema_version",
            "path",
            "max_bytes",
        }
        if _manifest_schema_version(manifest) >= 6:
            required_checkpoint_fields.add("protocol_root")
        if not isinstance(declared, Mapping) or set(declared) != required_checkpoint_fields:
            raise launch_common.LaunchError(
                "Phase 04 protocol_checkpoint does not match the manifest schema"
            )
        if (
            declared.get("schema_version")
            != project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION
        ):
            raise launch_common.LaunchError("Phase 04 protocol checkpoint schema is invalid")
        maximum = declared.get("max_bytes")
        if (
            isinstance(maximum, bool)
            or maximum != project_state.MAX_PROTOCOL_CHECKPOINT_BYTES
        ):
            raise launch_common.LaunchError("Phase 04 protocol checkpoint size policy is invalid")
        raw_project_dir = str(manifest.get("project_dir", "")).strip()
        raw_output_root = str(manifest.get("output_root", "")).strip()
        raw_checkpoint = str(declared.get("path", "")).strip()
        if not raw_project_dir or not raw_output_root or not raw_checkpoint:
            raise launch_common.LaunchError(
                "Phase 04 protocol checkpoint paths must be nonempty"
            )
        project_root = Path(raw_project_dir).resolve()
        output_root = Path(raw_output_root).resolve()
        checkpoint = Path(raw_checkpoint).resolve()
        try:
            output_root.relative_to(project_root)
            checkpoint.relative_to(project_root)
        except ValueError as exc:
            raise launch_common.LaunchError(
                "Phase 04 protocol checkpoint escaped the project"
            ) from exc
        expected_checkpoint = (
            output_root
            / ("protocol/protocol-checkpoint.json" if _manifest_schema_version(manifest) >= 7 else "protocol-checkpoint.json")
        ).resolve()
        if checkpoint != expected_checkpoint:
            raise launch_common.LaunchError(
                "Phase 04 protocol checkpoint path does not match the run plan"
            )
        if _manifest_schema_version(manifest) >= 6:
            protocol_root = Path(str(declared.get("protocol_root", ""))).resolve()
            expected_protocol_root = (output_root / "protocol").resolve()
            try:
                protocol_root.relative_to(project_root)
            except ValueError as exc:
                raise launch_common.LaunchError(
                    "Phase 04 protocol directory escaped the project"
                ) from exc
            if protocol_root != expected_protocol_root:
                raise launch_common.LaunchError(
                    "Phase 04 protocol directory does not match the run plan"
                )


def _validated_manifest_method_selection(
    manifest: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Validate method identity and provenance against the frozen input inventory."""

    str(manifest.get("phase_slug", ""))
    phase = manifest.get("phase")
    audit_only = isinstance(phase, Mapping) and phase.get("audit_only") is True
    required = (
        isinstance(phase, Mapping)
        and phase_requires_method_binding(phase)
        and not audit_only
    )
    value = manifest.get("method_selection")
    if value is None:
        if required:
            raise launch_common.LaunchError("The frozen run plan has no exact method selection")
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
        raise launch_common.LaunchError("The frozen method selection has an invalid structure")
    if not required:
        raise launch_common.LaunchError("This run variant must not declare a method selection")
    identity = _method_identity(
        str(value.get("stable_id", "")), str(value.get("version", ""))
    )
    if value.get("kind") != identity["kind"]:
        raise launch_common.LaunchError("The frozen scientific object must be a method")
    source = value.get("source")
    if (
        int(manifest.get("schema_version", 1)) >= 9
        and source != "run_specific_user_selection"
    ):
        raise launch_common.LaunchError(
            "New runs require a method chosen by the user for that run"
        )
    if source == "run_specific_user_selection":
        if any(
            value.get(field) is not None
            for field in ("source_phase", "source_run_id", "decision_record")
        ):
            raise launch_common.LaunchError(
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
            raise launch_common.LaunchError("The approved method-selection provenance is incomplete")
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
            raise launch_common.LaunchError(
                "The approved method selection does not match its frozen decision record"
            )
    else:
        raise launch_common.LaunchError("The frozen method selection has an invalid source")
    return dict(value)


def _frozen_snapshot_text(
    value: Any,
    label: str,
    *,
    max_bytes: int = launch_common.MAX_EMBEDDED_SOUL_BYTES,
) -> tuple[str, str, Path]:
    leaf = _snapshot_leaf(value, label)
    raw_path = Path(str(leaf["path"]))
    if raw_path.is_symlink():
        raise launch_common.LaunchError(f"Frozen snapshot {label} must not be a symbolic link")
    try:
        path = raw_path.resolve(strict=True)
    except OSError as exc:
        raise launch_common.LaunchError(f"Frozen snapshot {label} is unavailable") from exc
    text = launch_common._read_utf8_bounded(path, label=f"frozen {label}", max_bytes=max_bytes)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    expected = str(leaf["sha256"]).lower()
    if digest != expected:
        raise launch_common.LaunchError(f"Frozen snapshot {label} changed after launch preparation")
    return text, expected, path


def _read_manifest(project_dir: Path, phase_slug: str, run_id: str) -> dict[str, Any]:
    path = launch_common.run_manifest_path(project_dir, phase_slug, run_id)
    try:
        payload = launch_common._bounded_bytes(
            path,
            label="run manifest",
            max_bytes=project_state.MAX_CONTROL_FILE_BYTES,
        )
        manifest = json.loads(payload.decode("utf-8"))
    except (launch_common.LaunchError, UnicodeError, ValueError) as exc:
        raise launch_common.LaunchError(f"Run manifest is unavailable or invalid: {path}") from exc
    if manifest.get("run_id") != run_id or manifest.get("phase_slug") != phase_slug:
        raise launch_common.LaunchError("Run manifest identity does not match the requested run")
    run = project_state.get_run(project_dir, phase_slug, run_id)
    if Path(str(run.get("manifest_path", ""))).resolve() != path.resolve():
        raise launch_common.LaunchError("Run manifest path does not match the sealed state record")
    digest = hashlib.sha256(payload).hexdigest()
    if not run.get("manifest_sha256") or digest != run.get("manifest_sha256"):
        raise launch_common.LaunchError("Run manifest changed after launch preparation")
    _validate_manifest_snapshot_schema(manifest)
    return manifest


COMPLETED_METHOD_RESULT_STATUSES = frozenset({"approved", "awaiting_review"})
COMPLETED_SCIENTIFIC_OUTCOMES = frozenset({"Complete", "Partial"})


def _completed_scientific_outcome(run: Mapping[str, Any]) -> str:
    record = run.get("decision_record")
    data = record.get("data") if isinstance(record, Mapping) else None
    outcome = data.get("scientific_outcome") if isinstance(data, Mapping) else None
    return str(outcome) if outcome in COMPLETED_SCIENTIFIC_OUTCOMES else ""


def completed_method_branch_result(
    project_dir: str | Path,
    phase_slug: str,
    method: Mapping[str, Any],
) -> dict[str, str] | None:
    """Return the newest intact completed result for one exact method branch."""

    root = Path(project_dir).resolve()
    stable_id = str(method.get("stable_id", "")).strip()
    version = str(method.get("version", "")).strip()
    definition_sha256 = str(method.get("sha256", "")).strip().lower()
    if (
        not stable_id
        or not version
        or len(definition_sha256) != 64
        or any(character not in "0123456789abcdef" for character in definition_sha256)
    ):
        return None
    for run in reversed(project_state.get_runs(root, phase_slug)):
        if (
            not isinstance(run, Mapping)
            or str(run.get("status", "")) not in COMPLETED_METHOD_RESULT_STATUSES
            or not run.get("submitted_at")
            or not run.get("final_summary")
        ):
            continue
        scientific_outcome = _completed_scientific_outcome(run)
        if not scientific_outcome:
            continue
        run_id = str(run.get("run_id", "")).strip()
        if not run_id:
            continue
        try:
            manifest = _read_manifest(root, phase_slug, run_id)
            if (
                project_state._resolve_slug(phase_slug)
                in {
                    launch_common.IDEA_EVALUATION_PHASE,
                    launch_common.DRAFT_ASSEMBLY_PHASE,
                }
                and _manifest_schema_version(manifest) < 11
            ):
                continue
            selection = _validated_manifest_method_selection(manifest)
            selected_method = manifest.get("snapshots", {}).get("selected_method")
            if (
                not isinstance(selection, Mapping)
                or not isinstance(selected_method, Mapping)
                or str(selection.get("stable_id", "")) != stable_id
                or str(selection.get("version", "")) != version
                or str(selected_method.get("stable_id", "")) != stable_id
                or str(selected_method.get("version", "")) != version
                or not hmac.compare_digest(
                    str(selected_method.get("sha256", "")).lower(),
                    definition_sha256,
                )
                or not project_state.run_integrity_report(root, phase_slug, run_id).get("ok")
            ):
                continue
        except (KeyError, OSError, ValueError, launch_common.LaunchError, project_state.ProjectStateError):
            continue
        return {
            "phase": phase_slug,
            "run_id": run_id,
            "status": str(run.get("status", "")),
            "method_id": stable_id,
            "method_version": version,
            "method_sha256": definition_sha256,
            "scientific_outcome": scientific_outcome,
        }
    return None


def completed_phase_result(
    project_dir: str | Path,
    phase_slug: str,
) -> dict[str, str] | None:
    """Return the newest intact completed result for a non-branch phase."""

    root = Path(project_dir).resolve()
    for run in reversed(project_state.get_runs(root, phase_slug)):
        if (
            not isinstance(run, Mapping)
            or str(run.get("status", "")) not in COMPLETED_METHOD_RESULT_STATUSES
            or not run.get("submitted_at")
            or not run.get("final_summary")
        ):
            continue
        scientific_outcome = _completed_scientific_outcome(run)
        if not scientific_outcome:
            continue
        run_id = str(run.get("run_id", "")).strip()
        if not run_id:
            continue
        try:
            if not project_state.run_integrity_report(root, phase_slug, run_id).get("ok"):
                continue
        except (KeyError, OSError, ValueError, project_state.ProjectStateError):
            continue
        return {
            "phase": phase_slug,
            "run_id": run_id,
            "status": str(run.get("status", "")),
            "scientific_outcome": scientific_outcome,
        }
    return None


def phase_five_branch_readiness(
    project_dir: str | Path,
    method: Mapping[str, Any],
) -> dict[str, Any]:
    """Check the Phase 1 to Phase 4 results required by Phase 5."""

    requirements: list[dict[str, Any]] = []
    blockers: list[str] = []
    for phase_slug, label, branch_specific in (
        ("01-literature-review", "Phase 1 literature review", False),
        (project_state.METHOD_DEVELOPMENT_PHASE, "Phase 2 method development", False),
        (launch_common.IDEA_EVALUATION_PHASE, "Phase 3 theoretical development", True),
        (launch_common.DRAFT_ASSEMBLY_PHASE, "Phase 4 implementation and experiments", True),
    ):
        result = (
            completed_method_branch_result(project_dir, phase_slug, method)
            if branch_specific
            else completed_phase_result(project_dir, phase_slug)
        )
        requirements.append({
            "phase": phase_slug,
            "label": label,
            "satisfied": result is not None,
            "result": result,
        })
        if result is None:
            blockers.append(label)
    return {
        "ready": not blockers,
        "method_id": str(method.get("stable_id", "")).strip(),
        "method_version": str(method.get("version", "")).strip(),
        "method_sha256": str(method.get("sha256", "")).strip().lower(),
        "requirements": requirements,
        "blockers": blockers,
    }

def phase_five_required_completed_runs(
    readiness: Mapping[str, Any],
) -> dict[str, str]:
    """Return exact Phase 1 to Phase 4 run IDs from a ready report."""

    expected_requirements = (
        ("01-literature-review", "Phase 1 literature review", False),
        (
            project_state.METHOD_DEVELOPMENT_PHASE,
            "Phase 2 method development",
            False,
        ),
        (
            launch_common.IDEA_EVALUATION_PHASE,
            "Phase 3 theoretical development",
            True,
        ),
        (
            launch_common.DRAFT_ASSEMBLY_PHASE,
            "Phase 4 implementation and experiments",
            True,
        ),
    )
    if (
        not isinstance(readiness, Mapping)
        or set(readiness)
        != {
            "ready",
            "method_id",
            "method_version",
            "method_sha256",
            "requirements",
            "blockers",
        }
        or readiness.get("ready") is not True
        or readiness.get("blockers") != []
    ):
        raise launch_common.LaunchError(
            "Phase 5 readiness is incomplete or malformed"
        )
    method_id = readiness.get("method_id")
    method_version = readiness.get("method_version")
    method_sha256 = readiness.get("method_sha256")
    if (
        not isinstance(method_id, str)
        or not method_id.strip()
        or "\x00" in method_id
        or not isinstance(method_version, str)
        or not method_version.strip()
        or "\x00" in method_version
        or not isinstance(method_sha256, str)
        or len(method_sha256) != 64
        or any(character not in "0123456789abcdef" for character in method_sha256)
    ):
        raise launch_common.LaunchError(
            "Phase 5 readiness has invalid method identity metadata"
        )

    requirements = readiness.get("requirements")
    if not isinstance(requirements, list) or len(requirements) != len(
        expected_requirements
    ):
        raise launch_common.LaunchError(
            "Phase 5 readiness must contain exactly one result for each prior phase"
        )
    by_phase: dict[str, Mapping[str, Any]] = {}
    expected_by_phase = {
        phase_slug: (label, branch_specific)
        for phase_slug, label, branch_specific in expected_requirements
    }
    for requirement in requirements:
        if (
            not isinstance(requirement, Mapping)
            or set(requirement) != {"phase", "label", "satisfied", "result"}
        ):
            raise launch_common.LaunchError(
                "Phase 5 readiness contains an invalid requirement"
            )
        phase_slug = requirement.get("phase")
        expected = (
            expected_by_phase.get(phase_slug)
            if isinstance(phase_slug, str)
            else None
        )
        if (
            not isinstance(phase_slug, str)
            or expected is None
            or phase_slug in by_phase
            or requirement.get("label") != expected[0]
        ):
            raise launch_common.LaunchError(
                "Phase 5 readiness contains a missing, duplicate, or unknown phase"
            )
        by_phase[phase_slug] = requirement

    completed: dict[str, str] = {}
    for phase_slug, _, branch_specific in expected_requirements:
        requirement = by_phase.get(phase_slug)
        result = requirement.get("result") if isinstance(requirement, Mapping) else None
        expected_result_fields = {
            "phase",
            "run_id",
            "status",
            "scientific_outcome",
        }
        if branch_specific:
            expected_result_fields |= {
                "method_id",
                "method_version",
                "method_sha256",
            }
        if (
            not isinstance(requirement, Mapping)
            or requirement.get("satisfied") is not True
            or not isinstance(result, Mapping)
            or set(result) != expected_result_fields
            or result.get("phase") != phase_slug
            or result.get("status") not in COMPLETED_METHOD_RESULT_STATUSES
            or result.get("scientific_outcome")
            not in COMPLETED_SCIENTIFIC_OUTCOMES
            or (
                branch_specific
                and (
                    result.get("method_id") != method_id
                    or result.get("method_version") != method_version
                    or result.get("method_sha256") != method_sha256
                )
            )
        ):
            raise launch_common.LaunchError(
                f"Phase 5 readiness has no usable completed result for {phase_slug}"
            )
        run_id = result.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip() or "\x00" in run_id:
            raise launch_common.LaunchError(
                f"Phase 5 readiness has an invalid run ID for {phase_slug}"
            )
        completed[phase_slug] = run_id.strip()
    return completed

def _verify_frozen_inputs(
    project_dir: Path,
    phase_slug: str,
    run_id: str,
    manifest: Mapping[str, Any],
) -> None:
    """Verify every frozen prompt input and every derived output boundary."""

    _validate_manifest_snapshot_schema(manifest)
    context_root = launch_common.run_context_dir(project_dir, phase_slug, run_id).resolve()

    def verify_node(value: Any) -> None:
        if isinstance(value, Mapping):
            if "path" in value and "sha256" in value:
                raw_candidate = Path(str(value["path"]))
                if launch_common._path_uses_symlink_below(raw_candidate, context_root):
                    raise launch_common.LaunchError("Frozen input path must not use symbolic links")
                try:
                    candidate = raw_candidate.resolve(strict=True)
                except OSError as exc:
                    raise launch_common.LaunchError(
                        f"Frozen input is missing or unreadable: {value['path']}"
                    ) from exc
                try:
                    candidate.relative_to(context_root)
                except ValueError as exc:
                    raise launch_common.LaunchError("Frozen input path escaped the run context directory") from exc
                if not candidate.is_file():
                    raise launch_common.LaunchError(f"Frozen input is not a file: {candidate}")
                digest = launch_common._sha256_file(candidate)
                if digest != value["sha256"]:
                    raise launch_common.LaunchError(f"Frozen input changed after launch: {candidate}")
            for nested in value.values():
                verify_node(nested)
        elif isinstance(value, list):
            for nested in value:
                verify_node(nested)

    verify_node(manifest.get("snapshots", {}))
    phase = manifest["phase"]
    method_selection = manifest.get("method_selection") or {}
    stable_id = method_selection.get("stable_id")
    expected_output = (
        project_dir
        / (("branches/" + str(stable_id)) if stable_id else "")
        / str(phase.get("folder", ""))
        / "run"
        / f"{int(manifest['run_number']):02d}"
    ).resolve()
    actual_output = Path(str(manifest["output_root"])).resolve()
    try:
        actual_output.relative_to(project_dir.resolve())
    except ValueError as exc:
        raise launch_common.LaunchError("Run output root escaped the project directory") from exc
    if actual_output != expected_output:
        raise launch_common.LaunchError("Run output root does not match the frozen phase plan")
    expected_summary = (
        project_dir / "phase-summaries" / phase_slug / f"{run_id}.html"
    ).resolve()
    if Path(str(manifest["summary_path"])).resolve() != expected_summary:
        raise launch_common.LaunchError("Run summary path does not match the immutable run identity")
    if phase.get("audit_only") is True:
        if phase_slug != launch_common.IDEA_EVALUATION_PHASE:
            raise launch_common.LaunchError("An audit-only plan is only valid in Phase 03")
        launch_plans._verified_frozen_theory_audit_source(project_dir, manifest)
    elif manifest.get("proof_audit_source") is not None:
        raise launch_common.LaunchError("A non-audit-only run cannot declare a prior theory target")
    paper_review = manifest.get("paper_review")
    if isinstance(paper_review, Mapping) and paper_review.get("kind") == "review_only":
        review_schema = paper_review.get("schema_version", 1)
        if review_schema not in {1, 2}:
            raise launch_common.LaunchError("Review-only source metadata schema is invalid")
        review_path = Path(str(paper_review.get("review_path", ""))).resolve()
        if review_path != launch_plans._paper_manuscript_paths(actual_output)["review"]:
            raise launch_common.LaunchError("Review-only manuscript path does not match the run plan")
        try:
            review_path.relative_to(project_dir.resolve())
        except ValueError as exc:
            raise launch_common.LaunchError("Review-only manuscript escaped the project") from exc
        expected_digest = str(paper_review.get("review_sha256", "")).lower()
        if not review_path.is_file() or launch_common._sha256_file(review_path) != expected_digest:
            raise launch_common.LaunchError("The preserved review-only manuscript is missing or changed")
        if review_schema == 2:
            launch_plans._verified_frozen_source_baseline(
                project_dir,
                manifest,
                paper_review.get("source_baseline"),
                expected_phase_slug=launch_common.PAPER_WRITING_PHASE,
                relative_directory="paper-review/source-baseline",
            )
        elif paper_review.get("source_baseline") is not None:
            raise launch_common.LaunchError("Legacy review-only source has unexpected baseline metadata")
