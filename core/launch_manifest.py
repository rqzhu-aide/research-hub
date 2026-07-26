#!/usr/bin/env python3

"""Run manifest construction helpers and frozen-input validation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping



from core import launch_common
from core import project_state
from core import profile_skills
from core import launch_plans

MANIFEST_SCHEMA_VERSION = 8


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
    required_roles = set(members) | {"research_lead"}
    snapshots = manifest.get("snapshots")
    if not isinstance(snapshots, Mapping):
        raise launch_common.LaunchError("Run manifest snapshots must be a mapping")
    required_snapshot_keys = {"setting", "team", "souls", "playbooks", "summaries"}
    if set(snapshots) != required_snapshot_keys:
        raise launch_common.LaunchError(
            "Run manifest snapshots must contain exactly setting, team, souls, "
            "playbooks, and summaries"
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
    for index, entry in enumerate(summaries):
        _snapshot_leaf(entry, f"summaries[{index}]", allow_extra=True)

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
