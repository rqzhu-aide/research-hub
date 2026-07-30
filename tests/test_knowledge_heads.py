from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from core import empirical_records
from core import empirical_schema
from core import knowledge_basis
from core import knowledge_fragments
from core import knowledge_heads
from core import launch_common
from core import launch_manifest
from core import literature_records
from core import literature_schema
from core import launch_prompts
from core import phase_records
from core import project_state
from core import theory_records


def _identity(
    stable_id: str = "method-a",
    version: str = "v1",
) -> dict[str, str]:
    return {
        "stable_id": stable_id,
        "version": version,
        "definition_sha256": hashlib.sha256(
            f"{stable_id}:{version}".encode()
        ).hexdigest(),
    }


def _statement(
    statement_id: str,
    source: str,
    *,
    statement_type: str,
    logical_status: str,
    mathematical_result_type: str,
) -> dict[str, Any]:
    return {
        "statement_id": statement_id,
        "statement_type": statement_type,
        "wording": "The current package supports the stated result.",
        "scope": "The assumptions and experiments recorded in this package.",
        "formulation_state": "Current",
        "assessment_status": "Supported",
        "evidential_basis": ["The current verified package."],
        "source_provenance": [source],
        "assumptions": ["The recorded regularity conditions hold."],
        "uncertainty": ["The stated limitations remain unresolved."],
        "logical_status": logical_status,
        "mathematical_result_type": mathematical_result_type,
    }


def _lead_summary() -> dict[str, list[str]]:
    return {
        "fundamental_points": ["The current result is decision relevant."],
        "decision_relevant_changes": ["The current package is authoritative."],
        "unresolved_questions": ["One stated limitation remains open."],
    }


def _theory_fragment(
    identity: dict[str, str],
    generation: int,
    run_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": knowledge_fragments.SCHEMA_VERSION,
        "kind": knowledge_fragments.THEORY_KIND,
        "semantics": knowledge_fragments.THEORY_SEMANTICS,
        "coverage": "complete",
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "statements": [
            _statement(
                f"S-P03-{run_id}-research_lead-001",
                theory_records.THEORY_FILENAME,
                statement_type="Mathematical statement",
                logical_status="proved",
                mathematical_result_type="inequality or bound",
            )
        ],
        "dependencies": [],
        "lead_summary": _lead_summary(),
    }


def _write_theory(
    project: Path,
    identity: dict[str, str],
    *,
    generation: int = 2,
    run_id: str = "p3-run",
    legacy: bool = False,
) -> Path:
    directory = theory_records.current_theory_directory(
        project, identity["stable_id"]
    )
    directory.mkdir(parents=True)
    manuscript = b"# Theory\n\nA complete current proof.\n"
    (directory / theory_records.THEORY_FILENAME).write_bytes(manuscript)
    record: dict[str, Any] = {
        "schema_version": theory_records.LEGACY_SCHEMA_VERSION,
        "method_identity": identity,
        "source_run_id": run_id,
        "scientific_outcome": "Complete",
        "structurally_self_contained": False,
        "generation": generation,
        "manuscript_file": theory_records.THEORY_FILENAME,
        "manuscript_sha256": hashlib.sha256(manuscript).hexdigest(),
        "manuscript_size": len(manuscript),
    }
    if not legacy:
        fragment = (
            json.dumps(
                _theory_fragment(identity, generation, run_id),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
        (directory / theory_records.KNOWLEDGE_FILENAME).write_bytes(fragment)
        record.update({
            "schema_version": theory_records.SCHEMA_VERSION,
            "knowledge_file": theory_records.KNOWLEDGE_FILENAME,
            "knowledge_sha256": hashlib.sha256(fragment).hexdigest(),
            "knowledge_size": len(fragment),
            "counterpart_basis": knowledge_basis.unknown_legacy_basis(
                phase_slug=knowledge_basis.EMPIRICAL_PHASE,
            ),
        })
    (directory / theory_records.RECORD_FILENAME).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return directory


def _empirical_fragment(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": knowledge_fragments.SCHEMA_VERSION,
        "kind": knowledge_fragments.EMPIRICAL_KIND,
        "semantics": knowledge_fragments.EMPIRICAL_SEMANTICS,
        "coverage": "complete",
        "method": index["method"],
        "generation": index["generation"],
        "source_run_id": index["source_run_id"],
        "statements": [
            _statement(
                f"S-P04-{index['source_run_id']}-research_lead-001",
                empirical_records.SYNTHESIS_FILENAME,
                statement_type="Empirical statement",
                logical_status="Not applicable",
                mathematical_result_type="Not applicable",
            )
        ],
        "dependencies": [],
        "evidence_bindings": [
            {
                "evidence_id": entry["evidence_id"],
                "evidence_status": entry["status"],
                "role": "scientific_result",
                "assessments": [],
            }
            for entry in index["entries"]
        ],
        "lead_summary": _lead_summary(),
    }


def _write_empirical(
    project: Path,
    identity: dict[str, str],
    *,
    generation: int = 3,
    run_id: str = "p4-run",
    legacy: bool = False,
) -> tuple[Path, Path]:
    artifact = project / "runs" / run_id / "results" / "estimate.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"estimate": 1.25}\n', encoding="utf-8")
    directory = empirical_records.canonical_package_dir(
        project, identity["stable_id"]
    )
    directory.mkdir(parents=True)
    synthesis = b"# Empirical synthesis\n\nThe current estimate is stable.\n"
    (directory / empirical_records.SYNTHESIS_FILENAME).write_bytes(synthesis)
    index = {
        "schema_version": (
            empirical_schema.LEGACY_INDEX_SCHEMA_VERSION
            if legacy
            else empirical_records.INDEX_SCHEMA_VERSION
        ),
        "kind": empirical_records.INDEX_KIND,
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "synthesis": {
            "path": empirical_records.SYNTHESIS_FILENAME,
            "sha256": hashlib.sha256(synthesis).hexdigest(),
            "size": len(synthesis),
        },
        "entries": [
            {
                "evidence_id": "primary-estimate",
                "type": "result",
                "path": artifact.relative_to(project).as_posix(),
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "size": artifact.stat().st_size,
                "source_run_id": run_id,
                "run_scope": "comprehensive",
                "status": "current",
                "status_reason": "Validated in the recorded experiment.",
                "method_dependent": True,
            }
        ],
    }
    if not legacy:
        index["counterpart_basis"] = knowledge_basis.unknown_legacy_basis(
            phase_slug=knowledge_basis.THEORY_PHASE,
        )
    (directory / empirical_records.INDEX_FILENAME).write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not legacy:
        (directory / empirical_records.KNOWLEDGE_FILENAME).write_text(
            json.dumps(
                _empirical_fragment(index),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return directory, artifact


def _write_literature(project: Path) -> None:
    papers = project / literature_records.PAPERS_DIR
    papers.mkdir(parents=True)
    summary = b"# Literature Summary\n\nCurrent statistical literature.\n"
    (project / literature_records.LITERATURE_SUMMARY).write_bytes(summary)
    index = literature_schema.build_reference_index(
        papers,
        source_run_id="p1-run",
        generation=1,
        summary_sha256=hashlib.sha256(summary).hexdigest(),
    )
    (project / literature_records.REFERENCE_INDEX).write_bytes(index)


def _project(
    tmp_path: Path,
    *,
    legacy: bool = False,
) -> tuple[Path, dict[str, str], Path]:
    project = tmp_path / "project"
    project.mkdir(parents=True)
    identity = _identity()
    _write_theory(project, identity, legacy=legacy)
    _, artifact = _write_empirical(project, identity, legacy=legacy)
    return project, identity, artifact


def _freeze(
    project: Path,
    identity: dict[str, str],
    *,
    schema_version: int,
    phase_slug: str = "05-review-revision",
    include_method: bool = True,
) -> dict[str, Any]:
    run_id = "frozen-run"
    current = phase_records.current_context_records(
        project,
        method=identity if include_method else None,
    )
    context = (
        project_state.state_dir(project)
        / "runs"
        / phase_slug
        / f"{run_id}.context"
    )
    frozen: list[dict[str, Any]] = []
    for record_number, record in enumerate(current, start=1):
        files: list[dict[str, Any]] = []
        for file_number, file_record in enumerate(
            record["files"], start=1
        ):
            source_path = str(file_record["path"])
            target = (
                context
                / "current"
                / f"{record_number:02d}-{record['key']}"
                / f"{file_number:02d}-{Path(source_path).name}"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(project / source_path, target)
            payload = target.read_bytes()
            files.append({
                "path": str(target.resolve()),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "source_path": source_path,
                "size": len(payload),
            })
        frozen_record = {
            "key": record["key"],
            "kind": record["kind"],
            "source_run_id": record["source_run_id"],
            "generation": record["generation"],
            "files": files,
        }
        if schema_version == 13:
            frozen_record["method_identity"] = record["method_identity"]
        frozen.append(frozen_record)
    return {
        "schema_version": schema_version,
        "phase_slug": phase_slug,
        "run_id": run_id,
        "snapshots": {"current_records": frozen},
    }


def _record(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    return next(
        item
        for item in manifest["snapshots"]["current_records"]
        if item["key"] == key
    )


def _file(record: dict[str, Any], name: str) -> dict[str, Any]:
    return next(
        item
        for item in record["files"]
        if Path(item["source_path"]).name == name
    )


def _refresh_file_record(file_record: dict[str, Any]) -> None:
    payload = Path(file_record["path"]).read_bytes()
    file_record["sha256"] = hashlib.sha256(payload).hexdigest()
    file_record["size"] = len(payload)


def test_nonmethod_frozen_launch_state_includes_verified_p1_source(
    tmp_path: Path,
) -> None:
    project, identity, _ = _project(tmp_path)
    _write_literature(project)
    manifest = _freeze(
        project,
        identity,
        schema_version=13,
        phase_slug=phase_records.LITERATURE_PHASE,
        include_method=False,
    )

    state = knowledge_heads.derive_frozen_launch_state(
        project,
        manifest,
        None,
    )

    source = state[knowledge_heads.P1_KEY]
    assert state["knowledge_heads"] is None
    assert state[knowledge_heads.P3_KEY] is None
    assert state[knowledge_heads.P4_KEY] is None
    assert source["generation"] == 1
    assert source["source_run_id"] == "p1-run"
    assert source["summary_bytes"] == (
        project / literature_records.LITERATURE_SUMMARY
    ).read_bytes()
    assert source["index_bytes"] == (
        project / literature_records.REFERENCE_INDEX
    ).read_bytes()


@pytest.mark.parametrize("mutation", ["source_path", "sha256"])
def test_frozen_launch_state_rejects_tampered_p1_inventory(
    tmp_path: Path,
    mutation: str,
) -> None:
    project, identity, _ = _project(tmp_path)
    _write_literature(project)
    manifest = _freeze(
        project,
        identity,
        schema_version=13,
        phase_slug=phase_records.LITERATURE_PHASE,
        include_method=False,
    )
    summary = _file(
        _record(manifest, knowledge_heads.P1_KEY),
        literature_records.LITERATURE_SUMMARY.name,
    )
    if mutation == "source_path":
        summary["source_path"] = "references/not-the-summary.md"
    else:
        summary["sha256"] = "0" * 64

    with pytest.raises(knowledge_heads.KnowledgeHeadsError):
        knowledge_heads.derive_frozen_launch_state(
            project,
            manifest,
            None,
        )


def test_live_heads_report_absent_packages(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    heads = knowledge_heads.derive_live_heads(project, "method-a")
    assert heads["p3_theory"]["state"] == "absent"
    assert heads["p4_empirical"]["state"] == "absent"
    assert knowledge_heads.validate_heads(heads) == heads


def test_live_heads_distinguish_structured_and_legacy_packages(
    tmp_path: Path,
) -> None:
    structured, identity, _ = _project(tmp_path / "structured")
    heads = knowledge_heads.derive_live_heads(
        structured, identity["stable_id"]
    )
    theory = theory_records.load_current_theory(
        structured, identity["stable_id"]
    )
    empirical = empirical_records.load_current_package(
        structured, identity["stable_id"]
    )
    assert theory is not None
    assert empirical is not None
    assert theory["schema_version"] == theory_records.SCHEMA_VERSION
    assert (
        empirical["schema_version"]
        == empirical_records.INDEX_SCHEMA_VERSION
    )
    assert "counterpart_basis" in theory
    assert "counterpart_basis" in empirical
    assert heads["p3_theory"]["state"] == "available"
    assert heads["p4_empirical"]["state"] == "available"
    assert heads["p3_theory"]["method_identity"] == identity
    assert heads["p4_empirical"]["method_identity"] == identity

    legacy, legacy_identity, _ = _project(tmp_path / "legacy", legacy=True)
    legacy_heads = knowledge_heads.derive_live_heads(
        legacy, legacy_identity["stable_id"]
    )
    assert legacy_heads["p3_theory"]["state"] == "unknown_legacy"
    assert legacy_heads["p4_empirical"]["state"] == "unknown_legacy"
    assert legacy_heads["p3_theory"]["generation"] == 2
    assert legacy_heads["p4_empirical"]["source_run_id"] == "p4-run"


def test_heads_version_is_deterministic_and_provenance_sensitive(
    tmp_path: Path,
) -> None:
    project, identity, _ = _project(tmp_path)
    heads = knowledge_heads.derive_live_heads(project, identity["stable_id"])
    reordered = {
        "p4_empirical": copy.deepcopy(heads["p4_empirical"]),
        "p3_theory": copy.deepcopy(heads["p3_theory"]),
        "schema_version": 1,
    }
    assert knowledge_heads.heads_version(reordered) == (
        knowledge_heads.heads_version(heads)
    )
    changed = copy.deepcopy(heads)
    changed["p3_theory"]["generation"] += 1
    assert knowledge_heads.heads_version(changed) != (
        knowledge_heads.heads_version(heads)
    )


def test_live_heads_fail_closed_on_package_corruption(
    tmp_path: Path,
) -> None:
    project, identity, _ = _project(tmp_path)
    theory_dir = theory_records.current_theory_directory(
        project, identity["stable_id"]
    )
    (theory_dir / theory_records.KNOWLEDGE_FILENAME).write_text(
        "{}\n",
        encoding="utf-8",
    )
    with pytest.raises(knowledge_heads.KnowledgeHeadsError):
        knowledge_heads.derive_live_heads(project, identity["stable_id"])

    project_two, identity_two, _ = _project(tmp_path / "extra")
    empirical_dir = empirical_records.canonical_package_dir(
        project_two, identity_two["stable_id"]
    )
    (empirical_dir / "unexpected.txt").write_text("extra\n", encoding="utf-8")
    with pytest.raises(
        knowledge_heads.KnowledgeHeadsError,
        match="unexpected",
    ):
        knowledge_heads.derive_live_heads(
            project_two, identity_two["stable_id"]
        )


@pytest.mark.parametrize("schema_version", [12, 13])
def test_frozen_heads_match_live_heads_for_supported_manifests(
    tmp_path: Path,
    schema_version: int,
) -> None:
    project, identity, _ = _project(tmp_path)
    manifest = _freeze(
        project,
        identity,
        schema_version=schema_version,
    )
    assert knowledge_heads.derive_frozen_heads(
        project,
        manifest,
        identity["stable_id"],
    ) == knowledge_heads.derive_live_heads(project, identity["stable_id"])
    if schema_version == 13:
        assert _record(
            manifest, knowledge_heads.P3_KEY
        )["method_identity"] == identity
        assert _record(
            manifest, knowledge_heads.P4_KEY
        )["method_identity"] == identity


def test_schema_13_freezes_actual_identity_after_method_revision(
    tmp_path: Path,
) -> None:
    project, actual, _ = _project(tmp_path)
    selected = _identity(version="v2")
    manifest = _freeze(project, selected, schema_version=13)
    assert _record(
        manifest, knowledge_heads.P3_KEY
    )["method_identity"] == actual
    assert _record(
        manifest, knowledge_heads.P4_KEY
    )["method_identity"] == actual

    heads = knowledge_heads.derive_frozen_heads(
        project,
        manifest,
        actual["stable_id"],
    )

    assert heads["p3_theory"]["method_identity"] == actual
    assert heads["p4_empirical"]["method_identity"] == actual


def test_frozen_empirical_head_does_not_open_or_copy_evidence(
    tmp_path: Path,
) -> None:
    project, identity, artifact = _project(tmp_path)
    manifest = _freeze(project, identity, schema_version=13)
    context = Path(
        _file(
            _record(manifest, knowledge_heads.P4_KEY),
            empirical_records.INDEX_FILENAME,
        )["path"]
    ).parents[2]
    assert not list(context.rglob(artifact.name))
    artifact.unlink()
    heads = knowledge_heads.derive_frozen_heads(
        project,
        manifest,
        identity["stable_id"],
    )
    assert heads["p4_empirical"]["state"] == "available"


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_key",
        "duplicate_file",
        "unsafe_path",
        "forged_source",
        "forged_sha",
        "forged_generation",
    ],
)
def test_frozen_heads_reject_ambiguous_or_forged_inventory(
    tmp_path: Path,
    mutation: str,
) -> None:
    project, identity, _ = _project(tmp_path)
    manifest = _freeze(project, identity, schema_version=12)
    p3 = _record(manifest, knowledge_heads.P3_KEY)
    if mutation == "duplicate_key":
        manifest["snapshots"]["current_records"].append(copy.deepcopy(p3))
    elif mutation == "duplicate_file":
        p3["files"].append(copy.deepcopy(p3["files"][0]))
    elif mutation == "unsafe_path":
        p3["files"][0]["path"] = str(
            (project / p3["files"][0]["source_path"]).resolve()
        )
    elif mutation == "forged_source":
        p3["files"][0]["source_path"] = (
            "branches/other/evaluations/current/theory-manuscript.md"
        )
    elif mutation == "forged_sha":
        p3["files"][0]["sha256"] = "0" * 64
    else:
        p3["generation"] += 1
    with pytest.raises(knowledge_heads.KnowledgeHeadsError):
        knowledge_heads.derive_frozen_heads(
            project,
            manifest,
            identity["stable_id"],
        )


def test_schema_13_cross_checks_explicit_method_identity(
    tmp_path: Path,
) -> None:
    project, identity, _ = _project(tmp_path)
    manifest = _freeze(project, identity, schema_version=13)
    p4 = _record(manifest, knowledge_heads.P4_KEY)
    p4["method_identity"]["version"] = "forged"
    with pytest.raises(
        knowledge_heads.KnowledgeHeadsError,
        match="method_identity",
    ):
        knowledge_heads.derive_frozen_heads(
            project,
            manifest,
            identity["stable_id"],
        )

    schema_twelve = _freeze(project, identity, schema_version=12)
    _record(schema_twelve, knowledge_heads.P3_KEY)["method_identity"] = identity
    with pytest.raises(knowledge_heads.KnowledgeHeadsError):
        knowledge_heads.derive_frozen_heads(
            project,
            schema_twelve,
            identity["stable_id"],
        )


def test_frozen_heads_reject_duplicate_json_and_fragment_index_mismatch(
    tmp_path: Path,
) -> None:
    project, identity, _ = _project(tmp_path)
    duplicate = _freeze(project, identity, schema_version=12)
    p3_record = _file(
        _record(duplicate, knowledge_heads.P3_KEY),
        theory_records.RECORD_FILENAME,
    )
    path = Path(p3_record["path"])
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            f'"schema_version": {theory_records.SCHEMA_VERSION},',
            (
                f'"schema_version": {theory_records.SCHEMA_VERSION},\n'
                f'  "schema_version": {theory_records.SCHEMA_VERSION},'
            ),
            1,
        ),
        encoding="utf-8",
    )
    _refresh_file_record(p3_record)
    with pytest.raises(knowledge_heads.KnowledgeHeadsError, match="duplicate"):
        knowledge_heads.derive_frozen_heads(
            project,
            duplicate,
            identity["stable_id"],
        )

    mismatch = _freeze(project, identity, schema_version=12)
    p4_fragment = _file(
        _record(mismatch, knowledge_heads.P4_KEY),
        empirical_records.KNOWLEDGE_FILENAME,
    )
    fragment_path = Path(p4_fragment["path"])
    fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
    fragment["generation"] += 1
    fragment_path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_file_record(p4_fragment)
    with pytest.raises(knowledge_heads.KnowledgeHeadsError, match="fragment"):
        knowledge_heads.derive_frozen_heads(
            project,
            mismatch,
            identity["stable_id"],
        )

def _schema_13_method_manifest(
    project: Path,
    identity: dict[str, str],
    frozen: dict[str, Any],
    *,
    phase_slug: str = launch_common.IDEA_EVALUATION_PHASE,
) -> dict[str, Any]:
    manifest = {
        **frozen,
        "schema_version": 13,
        "project_dir": str(project),
        "phase_slug": phase_slug,
        "phase": {
            "slug": phase_slug,
            "method_binding": True,
        },
        "method_selection": {
            "kind": "method",
            "stable_id": identity["stable_id"],
            "version": identity["version"],
            "source": "run_specific_user_selection",
            "source_phase": None,
            "source_run_id": None,
            "decision_record": None,
        },
        "method_catalog_basis": None,
    }
    manifest["knowledge_heads"] = knowledge_heads.derive_frozen_heads(
        project,
        manifest,
        identity["stable_id"],
    )
    return manifest


def test_schema_13_manifest_heads_are_exactly_derived_from_frozen_records(
    tmp_path: Path,
) -> None:
    project, identity, _ = _project(tmp_path)
    manifest = _schema_13_method_manifest(
        project,
        identity,
        _freeze(
            project,
            identity,
            schema_version=13,
            phase_slug=launch_common.IDEA_EVALUATION_PHASE,
        ),
    )

    launch_manifest._validate_manifest_knowledge_heads(manifest)

    changed = copy.deepcopy(manifest)
    changed["knowledge_heads"][knowledge_heads.P3_KEY] = (
        knowledge_basis.absent_basis(
            phase_slug=knowledge_basis.THEORY_PHASE,
        )
    )
    with pytest.raises(
        launch_common.LaunchError,
        match="do not match the frozen current records",
    ):
        launch_manifest._validate_manifest_knowledge_heads(changed)

    nonmethod = {
        "schema_version": 13,
        "phase": {"slug": "01-literature-review"},
        "knowledge_heads": None,
    }
    launch_manifest._validate_manifest_knowledge_heads(nonmethod)
    nonmethod["knowledge_heads"] = manifest["knowledge_heads"]
    with pytest.raises(launch_common.LaunchError, match="require null"):
        launch_manifest._validate_manifest_knowledge_heads(nonmethod)


@pytest.mark.parametrize("mutation", ["content", "size", "missing"])
def test_schema_13_operational_check_revalidates_current_phase_four_artifacts(
    tmp_path: Path,
    mutation: str,
) -> None:
    project, identity, artifact = _project(tmp_path)
    manifest = _schema_13_method_manifest(
        project,
        identity,
        _freeze(
            project,
            identity,
            schema_version=13,
            phase_slug=launch_common.IDEA_EVALUATION_PHASE,
        ),
    )
    launch_manifest._verify_schema_13_referenced_scientific_context(
        project,
        manifest,
    )

    if mutation == "content":
        original = artifact.read_bytes()
        changed = original.replace(b"1.25", b"9.25")
        assert len(changed) == len(original)
        artifact.write_bytes(changed)
    elif mutation == "size":
        artifact.write_bytes(artifact.read_bytes() + b" ")
    else:
        artifact.unlink()

    with pytest.raises(
        launch_common.LaunchError,
        match="frozen Phase 3/4 context or referenced Phase 4 evidence",
    ):
        launch_manifest._verify_schema_13_referenced_scientific_context(
            project,
            manifest,
        )


def test_schema_12_manifest_keeps_legacy_reference_behavior(
    tmp_path: Path,
) -> None:
    project, identity, artifact = _project(tmp_path)
    manifest = _freeze(
        project,
        identity,
        schema_version=12,
        phase_slug=launch_common.IDEA_EVALUATION_PHASE,
    )
    artifact.unlink()

    launch_manifest._verify_schema_13_referenced_scientific_context(
        project,
        manifest,
    )
    heads = knowledge_heads.derive_frozen_heads(
        project,
        manifest,
        identity["stable_id"],
    )

    assert heads[knowledge_heads.P4_KEY]["state"] == "available"


def test_frozen_launch_state_is_the_only_p3_and_p4_staging_source(
    tmp_path: Path,
) -> None:
    project, identity, _ = _project(tmp_path)
    manifest = _schema_13_method_manifest(
        project,
        identity,
        _freeze(
            project,
            identity,
            schema_version=13,
            phase_slug=launch_common.IDEA_EVALUATION_PHASE,
        ),
    )
    state = knowledge_heads.derive_frozen_launch_state(
        project,
        manifest,
        identity["stable_id"],
    )
    frozen_theory = state[knowledge_heads.P3_KEY]["manuscript_bytes"]
    frozen_synthesis = state[knowledge_heads.P4_KEY].synthesis_bytes

    theory_dir = theory_records.current_theory_directory(
        project,
        identity["stable_id"],
    )
    empirical_dir = empirical_records.canonical_package_dir(
        project,
        identity["stable_id"],
    )
    (theory_dir / theory_records.THEORY_FILENAME).write_text(
        "# Canonical mutation after freeze\n",
        encoding="utf-8",
    )
    (empirical_dir / empirical_records.SYNTHESIS_FILENAME).write_text(
        "# Canonical mutation after freeze\n",
        encoding="utf-8",
    )

    p3_output = project / "runs" / "p3-next"
    p3 = phase_records.prepare_output(
        project,
        launch_common.IDEA_EVALUATION_PHASE,
        p3_output,
        run_id="p3-next",
        method=identity,
        frozen_current_records=state,
    )
    assert p3 is not None
    assert (p3_output / theory_records.THEORY_FILENAME).read_bytes() == frozen_theory

    p4_output = project / "runs" / "p4-next"
    p4 = phase_records.prepare_output(
        project,
        launch_common.DRAFT_ASSEMBLY_PHASE,
        p4_output,
        run_id="p4-next",
        method=identity,
        run_mode="comprehensive",
        counterpart_basis=state["knowledge_heads"][knowledge_heads.P3_KEY],
        frozen_current_records=state,
    )
    assert p4 is not None
    staged_synthesis = (
        p4_output / empirical_records.SYNTHESIS_FILENAME
    ).read_bytes()
    assert frozen_synthesis.strip() in staged_synthesis
    assert b"Canonical mutation after freeze" not in staged_synthesis


def test_frozen_method_mismatch_is_advisory_and_uses_phase_specific_staging(
    tmp_path: Path,
) -> None:
    project, identity, _ = _project(tmp_path)
    manifest = _schema_13_method_manifest(
        project,
        identity,
        _freeze(
            project,
            identity,
            schema_version=13,
            phase_slug=launch_common.IDEA_EVALUATION_PHASE,
        ),
    )
    state = knowledge_heads.derive_frozen_launch_state(
        project,
        manifest,
        identity["stable_id"],
    )
    revised = _identity(identity["stable_id"], "v2")

    p3_output = project / "runs" / "p3-revised"
    p3 = phase_records.prepare_output(
        project,
        launch_common.IDEA_EVALUATION_PHASE,
        p3_output,
        run_id="p3-revised",
        method=revised,
        frozen_current_records=state,
    )
    assert p3 is not None
    assert p3["source"] == "template"
    assert p3["reason"] == "method_revised"
    assert b"A complete current proof" not in (
        p3_output / theory_records.THEORY_FILENAME
    ).read_bytes()

    p4_output = project / "runs" / "p4-revised"
    p4 = phase_records.prepare_output(
        project,
        launch_common.DRAFT_ASSEMBLY_PHASE,
        p4_output,
        run_id="p4-revised",
        method=revised,
        run_mode="preliminary",
        counterpart_basis=state["knowledge_heads"][knowledge_heads.P3_KEY],
        frozen_current_records=state,
    )
    assert p4 is not None
    assert p4["method"] == revised
    assert [entry["status"] for entry in p4["entries"]] == ["outdated"]

    prompt = launch_prompts._current_records_prompt_block(
        manifest["snapshots"],
        phase_slug=launch_common.IDEA_EVALUATION_PHASE,
    )
    assert "Selected-method mismatch" not in prompt
    mismatched_snapshots = copy.deepcopy(manifest["snapshots"])
    mismatched_snapshots["selected_method"] = {
        "stable_id": revised["stable_id"],
        "version": revised["version"],
        "sha256": revised["definition_sha256"],
    }
    prompt = launch_prompts._current_records_prompt_block(
        mismatched_snapshots,
        phase_slug=launch_common.IDEA_EVALUATION_PHASE,
    )
    assert "Treat it as advisory" in prompt
    p5_prompt = launch_prompts._current_records_prompt_block(
        mismatched_snapshots,
        phase_slug=launch_common.PAPER_WRITING_PHASE,
    )
    assert "makes Phase 5 ineligible to launch" in p5_prompt
    assert "starts from a self-contained template" not in p5_prompt
    p4_prompt = launch_prompts._current_records_prompt_block(
        mismatched_snapshots,
        phase_slug=launch_common.DRAFT_ASSEMBLY_PHASE,
    )
    assert "retains indexed evidence" in p4_prompt
    assert "self-contained template" not in p4_prompt


def test_schema_13_submission_uses_only_manifest_counterpart_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, identity, _ = _project(tmp_path)
    manifest = _schema_13_method_manifest(
        project,
        identity,
        _freeze(
            project,
            identity,
            schema_version=13,
            phase_slug=launch_common.IDEA_EVALUATION_PHASE,
        ),
    )
    manifest["snapshots"]["selected_method"] = {
        "stable_id": identity["stable_id"],
        "version": identity["version"],
        "sha256": identity["definition_sha256"],
    }
    captured: list[Any] = []

    def fake_seal(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.append(kwargs.get("counterpart_basis"))
        return {"sealed": True}

    monkeypatch.setattr(theory_records, "seal_staged_theory", fake_seal)
    expected = manifest["knowledge_heads"][knowledge_heads.P4_KEY]
    future = copy.deepcopy(manifest)
    future["schema_version"] = 14
    assert phase_records.manifest_knowledge_heads(future) == manifest[
        "knowledge_heads"
    ]
    phase_records.seal_output(
        project,
        launch_common.IDEA_EVALUATION_PHASE,
        project / "unused",
        run_id="submit-run",
        scientific_outcome="Complete",
        manifest=manifest,
    )
    assert captured == [expected]

    with pytest.raises(phase_records.PhaseRecordError, match="differs"):
        phase_records.seal_output(
            project,
            launch_common.IDEA_EVALUATION_PHASE,
            project / "unused",
            run_id="submit-run",
            scientific_outcome="Complete",
            manifest=manifest,
            counterpart_basis=knowledge_basis.absent_basis(
                phase_slug=knowledge_basis.EMPIRICAL_PHASE,
            ),
        )

    legacy = copy.deepcopy(manifest)
    legacy["schema_version"] = 12
    legacy.pop("knowledge_heads")
    phase_records.seal_output(
        project,
        launch_common.IDEA_EVALUATION_PHASE,
        project / "unused",
        run_id="legacy-submit",
        scientific_outcome="Complete",
        manifest=legacy,
    )
    assert captured[-1] is None
    with pytest.raises(phase_records.PhaseRecordError, match="Legacy"):
        phase_records.seal_output(
            project,
            launch_common.IDEA_EVALUATION_PHASE,
            project / "unused",
            run_id="legacy-submit",
            scientific_outcome="Complete",
            manifest=legacy,
            counterpart_basis=expected,
        )


def test_frozen_launch_state_rejects_tampered_current_empirical_artifact(
    tmp_path: Path,
) -> None:
    project, identity, artifact = _project(tmp_path)
    frozen = _freeze(
        project,
        identity,
        schema_version=13,
        phase_slug=launch_common.DRAFT_ASSEMBLY_PHASE,
    )
    manifest = _schema_13_method_manifest(
        project,
        identity,
        frozen,
        phase_slug=launch_common.DRAFT_ASSEMBLY_PHASE,
    )
    artifact.write_text('{"estimate": 99}\n', encoding="utf-8")

    with pytest.raises(
        knowledge_heads.KnowledgeHeadsError,
        match="recorded size and SHA-256",
    ):
        knowledge_heads.derive_frozen_launch_state(
            project,
            manifest,
            identity["stable_id"],
        )


def test_frozen_launch_state_does_not_require_noncurrent_artifacts(
    tmp_path: Path,
) -> None:
    project, identity, artifact = _project(tmp_path)
    directory = empirical_records.canonical_package_dir(
        project,
        identity["stable_id"],
    )
    index_path = directory / empirical_records.INDEX_FILENAME
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"][0]["status"] = "outdated"
    index["entries"][0]["status_reason"] = (
        "The method changed and this artifact is not reused."
    )
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fragment_path = directory / empirical_records.KNOWLEDGE_FILENAME
    fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
    fragment["evidence_bindings"][0]["evidence_status"] = "outdated"
    fragment_path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifact.unlink()

    frozen = _freeze(
        project,
        identity,
        schema_version=13,
        phase_slug=launch_common.DRAFT_ASSEMBLY_PHASE,
    )
    manifest = _schema_13_method_manifest(
        project,
        identity,
        frozen,
        phase_slug=launch_common.DRAFT_ASSEMBLY_PHASE,
    )
    state = knowledge_heads.derive_frozen_launch_state(
        project,
        manifest,
        identity["stable_id"],
    )

    launch_manifest._verify_schema_13_referenced_scientific_context(
        project,
        manifest,
    )
    assert state[knowledge_heads.P4_KEY].index["entries"][0]["status"] == (
        "outdated"
    )
