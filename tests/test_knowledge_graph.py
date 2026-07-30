"""Behavioral tests for the rebuildable current-record basis graph."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from core import (
    empirical_records,
    knowledge_basis,
    knowledge_graph,
    knowledge_heads,
    knowledge_schema,
    literature_records,
    manuscript_records,
    method_menu,
    phase_records,
    project_state,
    theory_records,
)


def _write_method(
    project: Path,
    stable_id: str,
    *,
    version: str,
    number: int,
    body: str,
) -> dict[str, Any]:
    menu = project / method_menu.METHOD_MENU_DIR
    menu.mkdir(parents=True, exist_ok=True)
    (menu / f"{stable_id}.md").write_text(
        "---\n"
        f"stable_id: {stable_id}\n"
        f"version: {version}\n"
        f"label: {stable_id}\n"
        "status: recommended\n"
        f"number: {number}\n"
        "---\n\n"
        f"# {stable_id}\n\n{body}\n",
        encoding="utf-8",
    )
    matches = [
        entry
        for entry in method_menu.load_method_menu(project)["entries"]
        if entry["stable_id"] == stable_id
    ]
    assert len(matches) == 1
    assert matches[0]["errors"] == []
    return matches[0]


def _literature_card() -> str:
    return (
        "---\n"
        'doi: "10.1000/basis-graph"\n'
        'title: "A verified statistical reference"\n'
        'authors: ["First Author", "Second Author"]\n'
        "year: 2025\n"
        'venue: "Journal of Careful Tests"\n'
        'relation: "direct prior work"\n'
        'found_in_run: "p1-run"\n'
        'found_by_role: "research_lead"\n'
        "also_found_in: []\n"
        "---\n\n"
        "# A verified statistical reference\n\n"
        "This card records relevant prior work.\n"
    )


def _promote_literature(project: Path) -> None:
    output = project / "runs" / "p1-run"
    literature_records.prepare_reference_delta(
        project,
        output,
        source_run_id="p1-run",
    )
    delta = output / literature_records.STAGED_DELTA_DIRNAME
    (
        delta
        / literature_records.STAGED_PAPERS_DIRNAME
        / "verified-reference.md"
    ).write_text(_literature_card(), encoding="utf-8")
    (delta / literature_records.STAGED_SUMMARY_FILENAME).write_text(
        "# Literature synthesis\n\n"
        "The current reference library supports the method context.\n",
        encoding="utf-8",
    )
    seal = literature_records.seal_reference_delta(project, output)
    literature_records.promote_reference_delta(project, output, seal)


def _complete_theory_fragment(output: Path) -> None:
    path = output / theory_records.KNOWLEDGE_FILENAME
    fragment = json.loads(path.read_text(encoding="utf-8"))
    statement_id = "S-P03-stable-research_lead-001"
    fragment["coverage"] = "complete"
    fragment["statements"] = [
        {
            "statement_id": statement_id,
            "statement_type": "Mathematical statement",
            "wording": "The current method has a complete proof.",
            "scope": "The assumptions stated in the theory manuscript.",
            "formulation_state": "Current",
            "assessment_status": "Supported",
            "evidential_basis": ["The complete theory manuscript."],
            "source_provenance": ["theory-manuscript.md"],
            "assumptions": ["The stated regularity conditions."],
            "uncertainty": ["Finite-sample behavior remains open."],
            "logical_status": "proved",
            "mathematical_result_type": (
                "asymptotic limit, rate, or distribution"
            ),
        }
    ]
    fragment["dependencies"] = []
    fragment["lead_summary"] = {
        "fundamental_points": ["The principal result has a complete proof."],
        "decision_relevant_changes": [],
        "unresolved_questions": ["Finite-sample behavior remains open."],
    }
    path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _promote_theory(
    project: Path,
    identity: dict[str, str],
    *,
    run_id: str = "p3-run",
    counterpart_basis: dict[str, Any] | None = None,
) -> None:
    output = project / "runs" / run_id
    output.mkdir(parents=True)
    theory_records.prepare_staged_theory(
        project,
        output,
        identity,
        source_run_id=run_id,
    )
    (output / theory_records.THEORY_FILENAME).write_text(
        "# Theory manuscript\n\nA complete proof for the current method.\n",
        encoding="utf-8",
    )
    _complete_theory_fragment(output)
    seal = theory_records.seal_staged_theory(
        project,
        output,
        method_identity=identity,
        source_run_id=run_id,
        scientific_outcome="Complete",
        counterpart_basis=counterpart_basis,
    )
    theory_records.promote_staged_theory(
        project,
        output,
        seal,
        expected_method_identity=identity,
    )


def _complete_empirical_fragment(index: dict) -> dict:
    return {
        "schema_version": 1,
        "kind": "empirical_knowledge_fragment",
        "semantics": "cumulative_evidence",
        "coverage": "complete",
        "method": index["method"],
        "generation": index["generation"],
        "source_run_id": index["source_run_id"],
        "statements": [
            {
                "statement_id": (
                    f"S-P04-{index['source_run_id']}-research_lead-001"
                ),
                "statement_type": "Empirical statement",
                "wording": (
                    "The synthesis reports the current empirical record."
                ),
                "scope": "The simulations and analyses in the evidence index.",
                "formulation_state": "Current",
                "assessment_status": "Supported",
                "evidential_basis": [
                    "The empirical synthesis and evidence index."
                ],
                "source_provenance": [
                    empirical_records.SYNTHESIS_FILENAME
                ],
                "assumptions": [
                    "The recorded analyses completed as described."
                ],
                "uncertainty": [
                    "Limitations remain stated in the synthesis."
                ],
                "logical_status": "Not applicable",
                "mathematical_result_type": "Not applicable",
            }
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
        "lead_summary": {
            "fundamental_points": [
                "The synthesis records the current empirical evidence."
            ],
            "decision_relevant_changes": [],
            "unresolved_questions": [],
        },
    }
def _promote_empirical(
    project: Path,
    identity: dict[str, str],
    *,
    counterpart_basis: dict[str, Any],
) -> None:
    output = project / "runs" / "p4-run"
    output.mkdir(parents=True)
    synthesis = output / empirical_records.SYNTHESIS_FILENAME
    synthesis.write_text(
        "# Empirical synthesis\n\nNo unresolved evidence remains.\n",
        encoding="utf-8",
    )
    index = {
        "schema_version": empirical_records.INDEX_SCHEMA_VERSION,
        "kind": empirical_records.INDEX_KIND,
        "method": identity,
        "generation": 1,
        "source_run_id": "p4-run",
        "synthesis": {
            "path": empirical_records.SYNTHESIS_FILENAME,
            "sha256": project_state.bounded_file_digest(
                synthesis,
                maximum=empirical_records.MAX_SYNTHESIS_BYTES,
                label="test synthesis",
            )[0],
            "size": synthesis.stat().st_size,
        },
        "entries": [],
        "counterpart_basis": counterpart_basis,
    }
    (output / empirical_records.INDEX_FILENAME).write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / empirical_records.KNOWLEDGE_FILENAME).write_text(
        json.dumps(
            _complete_empirical_fragment(index),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    empirical_records.promote_staged_package(project, output)


def _promote_manuscript(
    project: Path,
    identity: dict[str, str],
    *,
    run_id: str = "p5-run",
) -> None:
    basis = phase_records.current_upstream_basis(project, identity)
    output = project / "runs" / run_id
    output.mkdir(parents=True)
    (output / manuscript_records.MANUSCRIPT_FILENAME).write_text(
        "# Manuscript\n\nThe current theory and evidence are synthesized.\n",
        encoding="utf-8",
    )
    seal = manuscript_records.seal_staged_manuscript(
        project,
        output,
        method_identity=identity,
        upstream_basis=basis,
        source_run_id=run_id,
        scientific_outcome="Complete",
    )
    manuscript_records.promote_staged_manuscript(
        project,
        output,
        seal,
        expected_method_identity=identity,
        expected_upstream_basis=basis,
    )


def _branch_through_first_p4(project: Path) -> dict[str, str]:
    entry = _write_method(
        project,
        "method-a",
        version="v1",
        number=1,
        body="The first exact method definition.",
    )
    identity = phase_records.method_identity(entry)
    _promote_literature(project)
    _promote_theory(
        project,
        identity,
        counterpart_basis=knowledge_basis.absent_basis(
            phase_slug=knowledge_basis.EMPIRICAL_PHASE
        ),
    )
    p3_basis = knowledge_heads.derive_live_heads(
        project, "method-a"
    )[knowledge_heads.P3_KEY]
    _promote_empirical(
        project,
        identity,
        counterpart_basis=p3_basis,
    )
    return identity


def _converge_theory(project: Path, identity: dict[str, str]) -> None:
    p4_basis = knowledge_heads.derive_live_heads(
        project, "method-a"
    )[knowledge_heads.P4_KEY]
    _promote_theory(
        project,
        identity,
        run_id="p3-run-2",
        counterpart_basis=p4_basis,
    )


def _complete_branch(project: Path) -> dict[str, str]:
    identity = _branch_through_first_p4(project)
    _converge_theory(project, identity)
    _promote_manuscript(project, identity)
    return identity


def test_p5_inherits_current_p3_review_when_frozen_files_match(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _branch_through_first_p4(project)
    _promote_manuscript(project, identity)

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}
    direct_p5_edges = [
        edge for edge in graph["edges"] if edge["target"] == "p5-manuscript"
    ]

    assert direct_p5_edges
    assert all(
        edge["alignment_status"] == "exact_match"
        for edge in direct_p5_edges
    )
    assert nodes["p3-theory"]["status"] == {
        "record_freshness": "current",
        "alignment_status": "review_required",
        "scientific_status": "not_assessed",
    }
    assert nodes["p4-empirical"]["status"]["alignment_status"] == (
        "exact_match"
    )
    assert nodes["p5-manuscript"]["status"] == {
        "record_freshness": "current",
        "alignment_status": "review_required",
        "scientific_status": "not_assessed",
    }

    unsealed = {
        key: copy.deepcopy(value)
        for key, value in graph.items()
        if key != "graph_sha256"
    }
    unsealed["nodes"][-1]["status"]["alignment_status"] = "exact_match"
    unsealed["summary"] = knowledge_schema.summarize_nodes(
        unsealed["nodes"]
    )
    with pytest.raises(
        knowledge_schema.KnowledgeSchemaError,
        match="current Phase 3 and Phase 4 alignment",
    ):
        knowledge_schema.seal_graph(unsealed)


def test_graph_rebuild_tracks_exact_p1_to_p5_basis_deterministically(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _branch_through_first_p4(project)

    before_convergence = knowledge_graph.build_branch_basis_graph(
        project, "method-a"
    )
    initial_nodes = {
        node["id"]: node for node in before_convergence["nodes"]
    }
    assert initial_nodes["p3-theory"]["status"]["alignment_status"] == (
        "review_required"
    )
    assert initial_nodes["p4-empirical"]["status"]["alignment_status"] == (
        "exact_match"
    )

    _converge_theory(project, identity)
    _promote_manuscript(project, identity)
    first = knowledge_graph.build_branch_basis_graph(project, "method-a")
    second = knowledge_graph.build_branch_basis_graph(project, "method-a")

    assert first == second
    assert first["branch"] == identity
    nodes = {node["id"]: node for node in first["nodes"]}
    theory_fragment = (
        theory_records.current_theory_directory(project, "method-a")
        / theory_records.KNOWLEDGE_FILENAME
    )
    empirical_fragment = (
        empirical_records.canonical_package_dir(project, "method-a")
        / empirical_records.KNOWLEDGE_FILENAME
    )
    assert nodes["p3-theory"]["digests"]["collection_sha256"] == (
        hashlib.sha256(theory_fragment.read_bytes()).hexdigest()
    )
    assert nodes["p4-empirical"]["digests"]["collection_sha256"] == (
        hashlib.sha256(empirical_fragment.read_bytes()).hexdigest()
    )
    assert nodes["p2-method"]["status"]["alignment_status"] == (
        "review_required"
    )
    assert first["summary"] == {
        "record_freshness": "complete",
        "alignment_status": "review_required",
        "scientific_status": "not_assessed",
    }
    assert all(
        node["status"]["record_freshness"] == "current"
        for node in first["nodes"]
    )
    assert all(
        node["status"]["scientific_status"] == "not_assessed"
        for node in first["nodes"]
    )
    phase_two_literature_edges = {
        knowledge_schema.P1_P2_SYNTHESIS_EDGE_ID,
        knowledge_schema.P1_P2_COLLECTION_EDGE_ID,
    }
    assert all(
        edge["alignment_status"] == "exact_match"
        for edge in first["edges"]
        if edge["id"] not in phase_two_literature_edges
    )
    assert all(
        edge["alignment_status"] == "review_required"
        for edge in first["edges"]
        if edge["id"] in phase_two_literature_edges
    )
    assert knowledge_schema.validate_graph(first) == first


def test_new_reference_with_unchanged_synthesis_marks_only_collection_stale(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _complete_branch(project)
    before = knowledge_graph.build_branch_basis_graph(project, "method-a")
    before_edges = {edge["id"]: edge for edge in before["edges"]}
    p1_synthesis_edge = knowledge_schema.P1_SYNTHESIS_EDGE_ID
    p1_collection_edge = knowledge_schema.P1_COLLECTION_EDGE_ID
    assert before_edges[p1_synthesis_edge]["alignment_status"] == "exact_match"
    assert before_edges[p1_collection_edge]["alignment_status"] == "exact_match"

    prior_literature = literature_records.load_current_literature_record(project)
    assert prior_literature is not None
    output = project / "runs" / "p1-run-2"
    literature_records.prepare_reference_delta(
        project,
        output,
        source_run_id="p1-run-2",
    )
    delta = output / literature_records.STAGED_DELTA_DIRNAME
    second_card = (
        _literature_card()
        .replace("10.1000/basis-graph", "10.1000/basis-graph-2")
        .replace(
            "A verified statistical reference",
            "A second verified statistical reference",
        )
        .replace('found_in_run: "p1-run"', 'found_in_run: "p1-run-2"')
    )
    (
        delta
        / literature_records.STAGED_PAPERS_DIRNAME
        / "second-verified-reference.md"
    ).write_text(second_card, encoding="utf-8")
    seal = literature_records.seal_reference_delta(project, output)
    literature_records.promote_reference_delta(project, output, seal)

    current_literature = literature_records.load_current_literature_record(project)
    assert current_literature is not None
    assert (
        current_literature["summary_sha256"]
        == prior_literature["summary_sha256"]
    )
    assert (
        current_literature["papers_sha256"]
        != prior_literature["papers_sha256"]
    )

    stale = knowledge_graph.build_branch_basis_graph(project, "method-a")
    assert stale["graph_sha256"] != before["graph_sha256"]
    stale_nodes = {node["id"]: node for node in stale["nodes"]}
    stale_edges = {edge["id"]: edge for edge in stale["edges"]}
    assert stale_edges[p1_synthesis_edge]["alignment_status"] == "exact_match"
    assert stale_edges[p1_collection_edge]["alignment_status"] == (
        "review_required"
    )
    assert stale_nodes["p3-theory"]["status"]["alignment_status"] == "exact_match"
    assert stale_nodes["p4-empirical"]["status"]["alignment_status"] == "exact_match"
    assert stale_nodes["p5-manuscript"]["status"]["alignment_status"] == (
        "review_required"
    )

    _promote_manuscript(project, identity, run_id="p5-run-2")
    refreshed = knowledge_graph.build_branch_basis_graph(project, "method-a")
    refreshed_edges = {edge["id"]: edge for edge in refreshed["edges"]}
    assert refreshed_edges[p1_synthesis_edge]["alignment_status"] == "exact_match"
    assert refreshed_edges[p1_collection_edge]["alignment_status"] == "exact_match"


def test_legacy_manuscript_without_collection_basis_is_yellow(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _complete_branch(project)
    record_path = (
        manuscript_records.current_manuscript_directory(project, "method-a")
        / manuscript_records.RECORD_FILENAME
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["schema_version"] = manuscript_records.LEGACY_SCHEMA_VERSION
    record["upstream_basis"].pop("p1_collection")
    record_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {edge["id"]: edge for edge in graph["edges"]}
    collection = edges[knowledge_schema.P1_COLLECTION_EDGE_ID]

    assert collection["expected"]["sha256"] is None
    assert collection["alignment_status"] == "review_required"
    assert edges[knowledge_schema.P1_SYNTHESIS_EDGE_ID][
        "alignment_status"
    ] == "exact_match"
    assert nodes["p5-manuscript"]["status"]["record_freshness"] == "current"
    assert nodes["p5-manuscript"]["status"]["alignment_status"] == (
        "review_required"
    )


def test_valid_p4_fragment_revision_changes_only_its_collection_digest(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _complete_branch(project)
    first = knowledge_graph.build_branch_basis_graph(project, "method-a")
    first_p4 = {node["id"]: node for node in first["nodes"]}[
        "p4-empirical"
    ]
    fragment_path = (
        empirical_records.canonical_package_dir(project, "method-a")
        / empirical_records.KNOWLEDGE_FILENAME
    )
    fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
    fragment["lead_summary"]["decision_relevant_changes"] = [
        "The current empirical interpretation was clarified."
    ]
    fragment_path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    second = knowledge_graph.build_branch_basis_graph(project, "method-a")
    second_p4 = {node["id"]: node for node in second["nodes"]}[
        "p4-empirical"
    ]

    assert second_p4["status"]["record_freshness"] == "current"
    assert second_p4["digests"]["record_sha256"] == (
        first_p4["digests"]["record_sha256"]
    )
    assert second_p4["digests"]["primary_sha256"] == (
        first_p4["digests"]["primary_sha256"]
    )
    assert second_p4["digests"]["collection_sha256"] != (
        first_p4["digests"]["collection_sha256"]
    )
    assert second_p4["digests"]["collection_sha256"] == hashlib.sha256(
        fragment_path.read_bytes()
    ).hexdigest()


def test_method_revision_changes_alignment_not_record_freshness(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _complete_branch(project)

    revised = _write_method(
        project,
        "method-a",
        version="v2",
        number=1,
        body="A revised exact method definition.",
    )
    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert graph["branch"] == phase_records.method_identity(revised)
    for node_id in ("p3-theory", "p4-empirical", "p5-manuscript"):
        assert nodes[node_id]["status"]["record_freshness"] == "current"
        assert (
            nodes[node_id]["status"]["alignment_status"]
            == "review_required"
        )
    assert graph["summary"]["record_freshness"] == "complete"
    assert graph["summary"]["alignment_status"] == "review_required"
    assert graph["summary"]["scientific_status"] == "not_assessed"


def test_invalid_current_record_is_explicit_and_blocks_alignment(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _complete_branch(project)
    theory_path = (
        theory_records.current_theory_directory(project, "method-a")
        / theory_records.THEORY_FILENAME
    )
    theory_path.write_text(
        "# Tampered theory\n\nThis no longer matches its record.\n",
        encoding="utf-8",
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert nodes["p3-theory"]["status"] == {
        "record_freshness": "invalid",
        "alignment_status": "blocked",
        "scientific_status": "not_assessed",
    }
    assert nodes["p3-theory"]["diagnostics"]
    assert nodes["p5-manuscript"]["status"]["alignment_status"] == "blocked"
    assert graph["summary"]["record_freshness"] == "invalid"
    assert graph["summary"]["alignment_status"] == "blocked"


def test_invalid_empirical_fragment_blocks_p4_and_downstream_alignment(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _complete_branch(project)
    fragment_path = (
        empirical_records.canonical_package_dir(project, "method-a")
        / empirical_records.KNOWLEDGE_FILENAME
    )
    fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
    fragment["method"]["version"] = "invalid-version"
    fragment_path.write_text(
        json.dumps(fragment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert nodes["p4-empirical"]["status"]["record_freshness"] == "invalid"
    assert nodes["p4-empirical"]["status"]["alignment_status"] == "blocked"
    assert nodes["p4-empirical"]["digests"]["collection_sha256"] is None
    assert nodes["p5-manuscript"]["status"]["alignment_status"] == "blocked"


def test_branch_isolation_and_shadow_cache_location(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_method(
        project,
        "method-a",
        version="v1",
        number=1,
        body="Method A.",
    )
    method_b = _write_method(
        project,
        "method-b",
        version="v1",
        number=2,
        body="Method B.",
    )

    graph = knowledge_graph.materialize_shadow_graph(project, "method-b")
    cache = knowledge_graph.shadow_graph_path(project, "method-b")
    control = project_state.state_dir(project)

    assert graph["branch"] == phase_records.method_identity(method_b)
    assert graph["branch_key"] == knowledge_schema.branch_key("method-b")
    assert cache == (
        control
        / "knowledge"
        / "branches"
        / knowledge_schema.branch_key("method-b")
        / knowledge_graph.SHADOW_FILENAME
    )
    assert cache.is_file()
    assert knowledge_graph.read_shadow_graph(project, "method-b") == graph
    assert not project_state.state_file(project).exists()
    assert "method-a" not in knowledge_schema.graph_bytes(graph).decode("utf-8")


def test_unlocked_refresh_and_safe_cache_invalidation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    method = _write_method(
        project,
        "method-a",
        version="v1",
        number=1,
        body="Method A.",
    )

    def unexpected_lock(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unlocked graph helper reacquired the project lock")

    monkeypatch.setattr(project_state, "_project_lock", unexpected_lock)
    graph = knowledge_graph.refresh_shadow_graph_unlocked(project, "method-a")
    cache = knowledge_graph.shadow_graph_path(project, "method-a")
    assert graph["branch"] == phase_records.method_identity(method)
    assert knowledge_graph.read_shadow_graph(project, "method-a") == graph

    synced: list[Path] = []
    monkeypatch.setattr(
        project_state,
        "_sync_state_directory",
        lambda directory: synced.append(Path(directory)),
    )
    assert knowledge_graph.invalidate_shadow_graph_unlocked(
        project, "method-a"
    ) is True
    assert synced == [cache.parent]
    assert not cache.exists()
    assert knowledge_graph.invalidate_shadow_graph_unlocked(
        project, "method-a"
    ) is False
    assert synced == [cache.parent, cache.parent]

    cache.mkdir()
    with pytest.raises(
        project_state.StateValidationError,
        match="cache must be a regular file",
    ):
        knowledge_graph.invalidate_shadow_graph_unlocked(project, "method-a")
    assert cache.is_dir()


def test_invalidation_retry_resyncs_an_already_absent_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_method(
        project,
        "method-a",
        version="v1",
        number=1,
        body="Method A.",
    )
    knowledge_graph.refresh_shadow_graph_unlocked(project, "method-a")
    cache = knowledge_graph.shadow_graph_path(project, "method-a")
    calls: list[Path] = []

    def fail_once(directory: Path) -> None:
        calls.append(Path(directory))
        if len(calls) == 1:
            raise OSError("simulated namespace sync failure")

    monkeypatch.setattr(
        project_state,
        "_sync_state_directory",
        fail_once,
    )

    with pytest.raises(
        project_state.StateValidationError,
        match="removal could not be made durable",
    ):
        knowledge_graph.invalidate_shadow_graph_unlocked(
            project,
            "method-a",
        )
    assert not cache.exists()
    assert knowledge_graph.invalidate_shadow_graph_unlocked(
        project,
        "method-a",
    ) is False
    assert calls == [cache.parent, cache.parent]
