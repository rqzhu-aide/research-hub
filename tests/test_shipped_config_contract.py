"""Contract tests: the shipped config.yaml must support every phase it declares.

These tests load the repository's real ``config.yaml`` and exercise the
launch-plan code paths for every configured phase. Feature logic that keys
off hardcoded phase slugs (theory run plans, method binding, protocol
checkpoints) previously broke repurposed phases while the unit tests — all
using their own fixture configs — stayed green. This suite would have caught
that: it fails whenever the shipped configuration cannot build a round plan
or validate a launch manifest for one of its own phases.
"""

from __future__ import annotations

from pathlib import Path

import pytest


import hub  # noqa: E402
from core import launch_run  # noqa: E402


@pytest.fixture(scope="module")
def shipped_config() -> dict:
    return hub.load_config()


def _round_count(phase: dict) -> int:
    if phase.get("pattern") == "sequential":
        return len(phase["stages"])
    return int(phase.get("rounds", {}).get("default", 1))


def _manifest_for_phase(phase: dict, tmp_path: Path) -> dict:
    """Mirror the manifest structure the launch builder freezes."""

    members = [str(role) for role in phase.get("members", [])]
    roles = set(members) | {"research_lead"}

    def leaf(name: str) -> dict:
        return {"path": f"/frozen/{name}", "sha256": "a" * 64}

    summary = tmp_path / "phase-summaries" / phase["slug"] / "run.html"
    manifest = {
        "schema_version": launch_run.MANIFEST_SCHEMA_VERSION,
        "phase_slug": phase["slug"],
        "phase": phase,
        "snapshots": {
            "setting": leaf("setting.md"),
            "team": {"charter": leaf("charter.md"), "norms": leaf("norms.md")},
            "souls": {role: leaf(f"{role}.md") for role in sorted(roles)},
            "playbooks": {
                **{f"{role}.md": leaf(f"{role}.md") for role in members},
                "_lead.md": leaf("_lead.md"),
                "_phase.md": leaf("_phase.md"),
            },
            "summaries": [],
        },
        "submission_outputs": {},
        "summary_path": str(summary),
        "decision_path": str(summary.with_suffix(".decision.json")),
        "phase_plan_version": "a" * 64,
        "prerequisite_report_version": "b" * 64,
        "hermes_root": "/tmp/hermes",
        "method_selection": None,
    }
    if launch_run.phase_requires_method_binding(phase) and not phase.get(
        "audit_only"
    ):
        manifest["method_selection"] = {
            "kind": "method",
            "stable_id": "contract-method",
            "version": "v1",
            "source": "run_specific_user_selection",
            "source_phase": None,
            "source_run_id": None,
            "decision_record": None,
        }
    if phase.get("protocol_checkpoint"):
        output_root = tmp_path / "project" / "run" / "01"
        manifest["output_root"] = str(output_root)
        manifest["project_dir"] = str(tmp_path / "project")
        manifest["protocol_checkpoint"] = {
            "schema_version": (
                launch_run.project_state.PROTOCOL_CHECKPOINT_SCHEMA_VERSION
            ),
            "path": str(output_root / "protocol" / "protocol-checkpoint.json"),
            "protocol_root": str(output_root / "protocol"),
            "max_bytes": launch_run.project_state.MAX_PROTOCOL_CHECKPOINT_BYTES,
        }
    return manifest


def test_shipped_config_declares_phases(shipped_config: dict) -> None:
    slugs = [phase["slug"] for phase in shipped_config["phases"]]
    assert slugs, "the shipped config must declare at least one phase"


def test_every_shipped_phase_builds_a_round_plan(
    shipped_config: dict, tmp_path: Path
) -> None:
    for phase in shipped_config["phases"]:
        text = launch_run._task_instructions(
            tmp_path,
            phase,
            "run-contract",
            1,
            _round_count(phase),
            "contract-board",
        )
        assert "dispatch-task" in text, phase["slug"]


def test_every_shipped_phase_manifest_validates(
    shipped_config: dict, tmp_path: Path
) -> None:
    for phase in shipped_config["phases"]:
        manifest = _manifest_for_phase(phase, tmp_path)
        launch_run._validate_manifest_snapshot_schema(manifest)


def test_every_shipped_phase_has_a_plan_version(shipped_config: dict) -> None:
    for phase in shipped_config["phases"]:
        digest = launch_run.launch_plan_version(shipped_config, phase["slug"])
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)


def test_theory_plans_match_the_shipped_declaration(shipped_config: dict) -> None:
    for phase in shipped_config["phases"]:
        declared = (
            phase.get("proof_audit") is not None
            or phase.get("available_run_plans") is not None
        )
        assert launch_run.phase_supports_theory_plans(phase) is declared, phase[
            "slug"
        ]


def test_repurposed_phases_do_not_inherit_legacy_slug_behavior(
    shipped_config: dict,
) -> None:
    """Parallel/debate phases on legacy slugs must behave as plain phases."""

    for phase in shipped_config["phases"]:
        if phase.get("pattern") not in {"parallel", "debate"}:
            continue
        assert not launch_run.phase_supports_theory_plans(phase), phase["slug"]
        # Slug inference must not leak into repurposed phases; a parallel/debate
        # phase may bind only via the explicit `method_binding: true` opt-in.
        if phase.get("method_binding") is not True:
            assert not launch_run.phase_requires_method_binding(phase), phase[
                "slug"
            ]
        assert not phase.get("protocol_checkpoint"), phase["slug"]


def test_shipped_playbooks_exist_for_every_phase(shipped_config: dict) -> None:
    phases_dir = Path(__file__).resolve().parents[1] / "config" / "phases"
    for phase in shipped_config["phases"]:
        phase_dir = phases_dir / phase["slug"]
        for name in ["_phase.md", "_lead.md"] + [
            f"{role}.md" for role in phase.get("members", [])
        ]:
            assert (phase_dir / name).is_file(), f"{phase['slug']}/{name}"
