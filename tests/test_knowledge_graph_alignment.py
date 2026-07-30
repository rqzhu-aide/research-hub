"""Direct mechanical alignment tests for the shadow basis graph."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core import (
    empirical_records,
    knowledge_basis,
    knowledge_content,
    knowledge_graph,
    knowledge_schema,
    method_menu,
    phase_records,
    theory_records,
)


def _digest(value: bytes | str) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def _method(project: Path) -> dict[str, str]:
    directory = project / method_menu.METHOD_MENU_DIR
    directory.mkdir(parents=True)
    (directory / "method-a.md").write_text(
        "---\n"
        "stable_id: method-a\n"
        "version: v1\n"
        "label: Method A\n"
        "status: recommended\n"
        "number: 1\n"
        "---\n\n"
        "# Method A\n\nA current statistical method.\n",
        encoding="utf-8",
    )
    entry = method_menu.load_method_menu(project)["entries"][0]
    return phase_records.method_identity(entry)


def _record_file(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return _digest(path.read_bytes())


def test_p4_attention_is_separate_from_scientific_assessment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)
    index_path = (
        empirical_records.canonical_package_dir(project, "method-a")
        / empirical_records.INDEX_FILENAME
    )
    _record_file(index_path, '{"test": "record bytes"}\n')
    current = {
        "method": identity,
        "generation": 1,
        "source_run_id": "p4-run",
        "synthesis": {"sha256": _digest("synthesis")},
        "entries": [
            {"status": "outdated"},
            {"status": "unresolved"},
        ],
    }
    monkeypatch.setattr(
        knowledge_graph.empirical_records,
        "load_current_package",
        lambda *_args, **_kwargs: current,
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    p4 = {node["id"]: node for node in graph["nodes"]}["p4-empirical"]

    assert p4["facts"] == {
        "item_count": 2,
        "outdated_count": 1,
        "unresolved_count": 1,
    }
    assert p4["digests"]["collection_sha256"] is None
    assert p4["status"] == {
        "record_freshness": "current",
        "alignment_status": "review_required",
        "scientific_status": "not_assessed",
    }


def test_p5_frozen_basis_change_is_detected_as_an_exact_digest_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)

    theory_record_path = (
        theory_records.current_theory_directory(project, "method-a")
        / theory_records.RECORD_FILENAME
    )
    current_theory_digest = _record_file(
        theory_record_path, '{"generation": 2}\n'
    )
    p4_index_path = (
        empirical_records.canonical_package_dir(project, "method-a")
        / empirical_records.INDEX_FILENAME
    )
    p4_index_digest = _record_file(p4_index_path, '{"generation": 1}\n')

    from core import manuscript_records

    manuscript_record_path = (
        manuscript_records.current_manuscript_directory(project, "method-a")
        / manuscript_records.RECORD_FILENAME
    )
    _record_file(manuscript_record_path, '{"generation": 1}\n')

    p1_summary_digest = _digest("literature summary")
    p4_synthesis_digest = _digest("empirical synthesis")
    old_theory_digest = _digest("previous theory record")
    manuscript = {
        "method_identity": identity,
        "generation": 1,
        "source_run_id": "p5-run",
        "manuscript_sha256": _digest("manuscript"),
        "upstream_basis": {
            "p1_synthesis": {
                "identity": "literature-synthesis",
                "sha256": p1_summary_digest,
                "generation": 1,
            },
            "p1_collection": {
                "identity": "reference-card-collection",
                "sha256": _digest("papers"),
                "generation": 1,
            },
            "p2_definition": {
                "identity": identity,
                "sha256": identity["definition_sha256"],
                "generation": None,
            },
            "p3_record": {
                "identity": "method-a:theory",
                "sha256": old_theory_digest,
                "generation": 1,
            },
            "p4_synthesis": {
                "identity": "method-a:empirical-synthesis",
                "sha256": p4_synthesis_digest,
                "generation": 1,
            },
            "p4_index": {
                "identity": "method-a:evidence-index",
                "sha256": p4_index_digest,
                "generation": 1,
            },
        },
    }
    monkeypatch.setattr(
        knowledge_graph.literature_records,
        "load_current_literature_record",
        lambda *_args: {
            "generation": 1,
            "source_run_id": "p1-run",
            "paper_count": 1,
            "papers_sha256": _digest("papers"),
            "summary_sha256": p1_summary_digest,
            "index_sha256": _digest("index"),
        },
    )
    monkeypatch.setattr(
        knowledge_graph.theory_records,
        "load_current_theory",
        lambda *_args: {
            "method_identity": identity,
            "generation": 2,
            "source_run_id": "p3-replacement",
            "manuscript_sha256": _digest("theory manuscript"),
        },
    )
    monkeypatch.setattr(
        knowledge_graph.empirical_records,
        "load_current_package",
        lambda *_args, **_kwargs: {
            "method": identity,
            "generation": 1,
            "source_run_id": "p4-run",
            "synthesis": {"sha256": p4_synthesis_digest},
            "entries": [],
        },
    )
    monkeypatch.setattr(
        knowledge_graph.manuscript_records,
        "load_current_manuscript",
        lambda *_args: manuscript,
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}
    edge = {
        item["id"]: item for item in graph["edges"]
    }["p3-theory--p5-manuscript:p3_record"]

    assert nodes["p3-theory"]["digests"]["collection_sha256"] is None
    assert nodes["p4-empirical"]["digests"]["collection_sha256"] is None
    assert edge["expected"] == {
        "sha256": old_theory_digest,
        "generation": 1,
        "method_identity": None,
    }
    assert edge["observed"] == {
        "sha256": current_theory_digest,
        "generation": 2,
        "method_identity": None,
    }
    assert edge["alignment_status"] == "review_required"
    assert nodes["p3-theory"]["status"]["alignment_status"] == (
        "review_required"
    )
    assert nodes["p5-manuscript"]["status"] == {
        "record_freshness": "current",
        "alignment_status": "review_required",
        "scientific_status": "not_assessed",
    }

def _v2_statement(statement_id: str, *, empirical: bool) -> dict[str, object]:
    return {
        "statement_id": statement_id,
        "statement_type": (
            "Empirical statement" if empirical else "Mathematical statement"
        ),
        "wording": "The current package records one stable scientific claim.",
        "scope": "The method and assumptions in the current package.",
        "formulation_state": "Current",
        "assessment_status": "Supported",
        "evidential_basis": ["The current canonical package."],
        "source_provenance": ["knowledge-fragment.json"],
        "assumptions": ["The stated regularity conditions."],
        "uncertainty": ["No broader claim is made."],
        "logical_status": "Not applicable" if empirical else "proved",
        "mathematical_result_type": (
            "Not applicable"
            if empirical
            else "asymptotic limit, rate, or distribution"
        ),
    }


def _v2_theory_fragment(
    identity: dict[str, str],
    *,
    generation: int = 1,
    run_id: str = "p3-run-1",
    summary: str = "The theory claim is current.",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "theory_knowledge_fragment",
        "semantics": "complete_replacement",
        "coverage": "complete",
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "statements": [_v2_statement("S-P03-stable-001", empirical=False)],
        "dependencies": [],
        "lead_summary": {
            "fundamental_points": [summary],
            "decision_relevant_changes": [],
            "unresolved_questions": [],
        },
    }


def _v2_empirical_package(
    identity: dict[str, str],
    *,
    generation: int = 1,
    run_id: str = "p4-run-1",
    summary: str = "The empirical claim is current.",
) -> tuple[dict[str, object], dict[str, object]]:
    index = {
        "schema_version": empirical_records.INDEX_SCHEMA_VERSION,
        "kind": empirical_records.INDEX_KIND,
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "synthesis": {
            "path": empirical_records.SYNTHESIS_FILENAME,
            "sha256": "c" * 64,
            "size": 100,
        },
        "entries": [],
    }
    fragment = {
        "schema_version": 1,
        "kind": "empirical_knowledge_fragment",
        "semantics": "cumulative_evidence",
        "coverage": "complete",
        "method": identity,
        "generation": generation,
        "source_run_id": run_id,
        "statements": [_v2_statement("S-P04-stable-001", empirical=True)],
        "dependencies": [],
        "evidence_bindings": [],
        "lead_summary": {
            "fundamental_points": [summary],
            "decision_relevant_changes": [],
            "unresolved_questions": [],
        },
    }
    return index, fragment


def _v2_available_basis(
    phase_slug: str,
    identity: dict[str, str],
    fragment: dict[str, object],
    *,
    evidence_index: dict[str, object] | None = None,
) -> dict[str, object]:
    return knowledge_basis.available_basis(
        phase_slug=phase_slug,
        method_identity=identity,
        content_reference=knowledge_content.build_content_reference(
            phase_slug=phase_slug,
            fragment=fragment,
            evidence_index=evidence_index,
        ),
        generation=int(fragment["generation"]),
        source_run_id=str(fragment["source_run_id"]),
    )


def _install_v2_phase_records(
    monkeypatch,
    identity: dict[str, str],
    *,
    theory_record: dict[str, object] | None,
    theory_fragment: dict[str, object] | None,
    empirical_record: dict[str, object] | None,
    empirical_fragment: dict[str, object] | None,
    theory_state: str = "current",
    empirical_state: str = "current",
) -> None:
    if theory_state == "current":
        assert theory_record is not None and theory_fragment is not None
        theory_node = knowledge_graph._base_node(
            "p3-theory",
            freshness="current",
            alignment="exact_match",
            generation=int(theory_record["generation"]),
            source_run_id=str(theory_record["source_run_id"]),
            method_identity=theory_record["method_identity"],
            digests={
                "record_sha256": "1" * 64,
                "primary_sha256": "2" * 64,
                "collection_sha256": "3" * 64,
            },
        )
    else:
        theory_node = knowledge_graph._base_node(
            "p3-theory",
            freshness=theory_state,
            alignment=(
                "not_available" if theory_state == "missing" else "blocked"
            ),
            diagnostics=(
                [] if theory_state == "missing" else ["invalid theory record"]
            ),
        )
        theory_record = None
        theory_fragment = None

    if empirical_state == "current":
        assert empirical_record is not None and empirical_fragment is not None
        empirical_node = knowledge_graph._base_node(
            "p4-empirical",
            freshness="current",
            alignment="exact_match",
            generation=int(empirical_record["generation"]),
            source_run_id=str(empirical_record["source_run_id"]),
            method_identity=empirical_record["method"],
            digests={
                "record_sha256": "4" * 64,
                "primary_sha256": "5" * 64,
                "collection_sha256": "6" * 64,
            },
            facts=knowledge_graph._facts(
                item_count=len(empirical_record["entries"])
            ),
        )
    else:
        empirical_node = knowledge_graph._base_node(
            "p4-empirical",
            freshness=empirical_state,
            alignment=(
                "not_available" if empirical_state == "missing" else "blocked"
            ),
            diagnostics=(
                []
                if empirical_state == "missing"
                else ["invalid empirical record"]
            ),
        )
        empirical_record = None
        empirical_fragment = None

    monkeypatch.setattr(
        knowledge_graph,
        "_theory_node",
        lambda *_args: (theory_node, theory_record, theory_fragment),
    )
    monkeypatch.setattr(
        knowledge_graph,
        "_empirical_node",
        lambda *_args: (
            empirical_node,
            empirical_record,
            empirical_fragment,
        ),
    )


def _v2_current_records(
    identity: dict[str, str],
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    theory_fragment = _v2_theory_fragment(identity)
    empirical_record, empirical_fragment = _v2_empirical_package(identity)
    p3_basis = _v2_available_basis(
        knowledge_basis.THEORY_PHASE,
        identity,
        theory_fragment,
    )
    p4_basis = _v2_available_basis(
        knowledge_basis.EMPIRICAL_PHASE,
        identity,
        empirical_fragment,
        evidence_index=empirical_record,
    )
    theory_record = {
        "method_identity": identity,
        "generation": theory_fragment["generation"],
        "source_run_id": theory_fragment["source_run_id"],
        "manuscript_sha256": "7" * 64,
        "knowledge_sha256": "8" * 64,
        "counterpart_basis": p4_basis,
    }
    empirical_record["counterpart_basis"] = p3_basis
    return (
        theory_record,
        theory_fragment,
        empirical_record,
        empirical_fragment,
    )


def test_v2_cross_phase_alignment_converges_without_scientific_inference(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)
    records = _v2_current_records(identity)
    _install_v2_phase_records(
        monkeypatch,
        identity,
        theory_record=records[0],
        theory_fragment=records[1],
        empirical_record=records[2],
        empirical_fragment=records[3],
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {edge["id"]: edge for edge in graph["edges"]}

    assert graph["schema_version"] == knowledge_schema.SCHEMA_VERSION
    assert edges[
        "p4-empirical--p3-theory:counterpart_basis"
    ]["alignment_status"] == "exact_match"
    assert edges[
        "p3-theory--p4-empirical:counterpart_basis"
    ]["alignment_status"] == "exact_match"
    assert nodes["p3-theory"]["status"]["alignment_status"] == "exact_match"
    assert nodes["p4-empirical"]["status"]["alignment_status"] == "exact_match"
    assert nodes["p3-theory"]["status"]["scientific_status"] == "not_assessed"
    assert nodes["p4-empirical"]["status"]["scientific_status"] == "not_assessed"


def test_v2_sibling_created_later_marks_only_the_older_phase_for_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)
    theory_record, theory_fragment, empirical_record, empirical_fragment = (
        _v2_current_records(identity)
    )
    theory_record["counterpart_basis"] = knowledge_basis.absent_basis(
        phase_slug=knowledge_basis.EMPIRICAL_PHASE
    )
    _install_v2_phase_records(
        monkeypatch,
        identity,
        theory_record=theory_record,
        theory_fragment=theory_fragment,
        empirical_record=empirical_record,
        empirical_fragment=empirical_fragment,
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert nodes["p3-theory"]["status"]["alignment_status"] == "review_required"
    assert nodes["p4-empirical"]["status"]["alignment_status"] == "exact_match"


def test_v2_unchanged_semantic_reruns_ignore_generation_and_summary_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)
    old_theory = _v2_theory_fragment(identity)
    old_index, old_empirical = _v2_empirical_package(identity)
    old_p3_basis = _v2_available_basis(
        knowledge_basis.THEORY_PHASE,
        identity,
        old_theory,
    )
    old_p4_basis = _v2_available_basis(
        knowledge_basis.EMPIRICAL_PHASE,
        identity,
        old_empirical,
        evidence_index=old_index,
    )

    theory = _v2_theory_fragment(
        identity,
        generation=2,
        run_id="p3-run-2",
        summary="The lead rewrote only the compact summary.",
    )
    empirical_record, empirical = _v2_empirical_package(
        identity,
        generation=2,
        run_id="p4-run-2",
        summary="The lead clarified only the compact summary.",
    )
    theory_record = {
        "method_identity": identity,
        "generation": 2,
        "source_run_id": "p3-run-2",
        "manuscript_sha256": "7" * 64,
        "knowledge_sha256": "8" * 64,
        "counterpart_basis": old_p4_basis,
    }
    empirical_record["counterpart_basis"] = old_p3_basis
    _install_v2_phase_records(
        monkeypatch,
        identity,
        theory_record=theory_record,
        theory_fragment=theory,
        empirical_record=empirical_record,
        empirical_fragment=empirical,
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    semantic_edges = [
        edge
        for edge in graph["edges"]
        if edge["id"] in {
            "p4-empirical--p3-theory:counterpart_basis",
            "p3-theory--p4-empirical:counterpart_basis",
        }
    ]

    assert all(
        edge["alignment_status"] == "exact_match"
        for edge in semantic_edges
    )


def test_v2_version_only_method_change_keeps_rerun_sibling_yellow(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    old_identity = _method(project)
    current_identity = {**old_identity, "version": "v2"}

    theory_fragment = _v2_theory_fragment(old_identity)
    p3_basis = _v2_available_basis(
        knowledge_basis.THEORY_PHASE,
        old_identity,
        theory_fragment,
    )
    empirical_record, empirical_fragment = _v2_empirical_package(
        current_identity
    )
    p4_basis = _v2_available_basis(
        knowledge_basis.EMPIRICAL_PHASE,
        current_identity,
        empirical_fragment,
        evidence_index=empirical_record,
    )
    theory_record = {
        "method_identity": old_identity,
        "generation": 1,
        "source_run_id": "p3-run-1",
        "manuscript_sha256": "7" * 64,
        "knowledge_sha256": "8" * 64,
        "counterpart_basis": p4_basis,
    }
    empirical_record["counterpart_basis"] = p3_basis
    _install_v2_phase_records(
        monkeypatch,
        old_identity,
        theory_record=theory_record,
        theory_fragment=theory_fragment,
        empirical_record=empirical_record,
        empirical_fragment=empirical_fragment,
    )
    monkeypatch.setattr(
        knowledge_graph,
        "_current_method",
        lambda *_args: ({}, current_identity),
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {edge["id"]: edge for edge in graph["edges"]}

    p4_method_edge = edges[
        "p2-method--p4-empirical:method_definition"
    ]
    assert p4_method_edge["alignment_status"] == "exact_match"
    assert p4_method_edge["expected"]["method_identity"] == current_identity
    assert p4_method_edge["observed"]["method_identity"] == current_identity
    assert edges[
        "p3-theory--p4-empirical:counterpart_basis"
    ]["alignment_status"] == "review_required"
    assert nodes["p4-empirical"]["status"]["alignment_status"] == "review_required"


def test_v2_missing_target_and_invalid_source_are_explicit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)
    _, _, empirical_record, empirical_fragment = _v2_current_records(identity)
    empirical_record["counterpart_basis"] = knowledge_basis.absent_basis(
        phase_slug=knowledge_basis.THEORY_PHASE
    )
    _install_v2_phase_records(
        monkeypatch,
        identity,
        theory_record=None,
        theory_fragment=None,
        empirical_record=empirical_record,
        empirical_fragment=empirical_fragment,
        theory_state="missing",
    )

    missing_graph = knowledge_graph.build_branch_basis_graph(
        project, "method-a"
    )
    missing_nodes = {node["id"]: node for node in missing_graph["nodes"]}
    missing_edges = {edge["id"]: edge for edge in missing_graph["edges"]}
    assert missing_edges[
        "p4-empirical--p3-theory:counterpart_basis"
    ]["alignment_status"] == "not_available"
    assert missing_edges[
        "p3-theory--p4-empirical:counterpart_basis"
    ]["alignment_status"] == "exact_match"
    assert missing_nodes["p4-empirical"]["status"]["alignment_status"] == (
        "exact_match"
    )

    _install_v2_phase_records(
        monkeypatch,
        identity,
        theory_record=None,
        theory_fragment=None,
        empirical_record=empirical_record,
        empirical_fragment=empirical_fragment,
        theory_state="invalid",
    )
    invalid_graph = knowledge_graph.build_branch_basis_graph(
        project, "method-a"
    )
    invalid_nodes = {node["id"]: node for node in invalid_graph["nodes"]}
    invalid_edges = {edge["id"]: edge for edge in invalid_graph["edges"]}
    assert invalid_edges[
        "p4-empirical--p3-theory:counterpart_basis"
    ]["alignment_status"] == "blocked"
    assert invalid_edges[
        "p3-theory--p4-empirical:counterpart_basis"
    ]["alignment_status"] == "blocked"
    assert invalid_nodes["p4-empirical"]["status"]["alignment_status"] == (
        "blocked"
    )


def test_v2_legacy_missing_counterpart_basis_requires_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)
    theory_record, theory_fragment, empirical_record, empirical_fragment = (
        _v2_current_records(identity)
    )
    del theory_record["counterpart_basis"]
    _install_v2_phase_records(
        monkeypatch,
        identity,
        theory_record=theory_record,
        theory_fragment=theory_fragment,
        empirical_record=empirical_record,
        empirical_fragment=empirical_fragment,
    )

    graph = knowledge_graph.build_branch_basis_graph(project, "method-a")
    edges = {edge["id"]: edge for edge in graph["edges"]}
    nodes = {node["id"]: node for node in graph["nodes"]}

    edge = edges["p4-empirical--p3-theory:counterpart_basis"]
    assert edge["expected"]["state"] == "unknown_legacy"
    assert edge["alignment_status"] == "review_required"
    assert nodes["p3-theory"]["status"]["alignment_status"] == "review_required"


def _install_phase_two_literature_alignment(
    project: Path,
    monkeypatch,
    identity: dict[str, str],
    *,
    current_synthesis: str,
    current_collection: str,
    reviewed_synthesis: str | None,
    reviewed_collection: str | None,
) -> dict[str, object]:
    entry: dict[str, object] = {}
    if reviewed_synthesis is not None and reviewed_collection is not None:
        entry["provenance"] = {
            "schema_version": method_menu.METHOD_PROVENANCE_SCHEMA_VERSION,
            "method_sha256": identity["definition_sha256"],
            "definition_source_run_id": "p2-definition-run",
            "review_source_run_id": "p2-review-run",
            "review_scientific_outcome": "Complete",
            "review_scope": "full_catalog",
            "disposition": "reviewed_no_change",
            "literature_basis": {
                "schema_version": (
                    method_menu.LITERATURE_BASIS_SCHEMA_VERSION
                ),
                "availability": "available",
                "source_run_id": "p1-reviewed-run",
                "generation": 1,
                "synthesis_sha256": reviewed_synthesis,
                "collection_sha256": reviewed_collection,
            },
        }
    monkeypatch.setattr(
        knowledge_graph,
        "_current_method",
        lambda *_args: (entry, identity),
    )
    p1_node = knowledge_graph._base_node(
        "p1-literature",
        freshness="current",
        alignment="exact_match",
        generation=2,
        source_run_id="p1-current-run",
        digests={
            "record_sha256": _digest("current-reference-index"),
            "primary_sha256": current_synthesis,
            "collection_sha256": current_collection,
        },
        facts=knowledge_graph._facts(item_count=2),
    )
    monkeypatch.setattr(
        knowledge_graph,
        "_literature_node",
        lambda *_args: p1_node,
    )
    records = _v2_current_records(identity)
    _install_v2_phase_records(
        monkeypatch,
        identity,
        theory_record=records[0],
        theory_fragment=records[1],
        empirical_record=records[2],
        empirical_fragment=records[3],
    )
    return knowledge_graph.build_branch_basis_graph(project, "method-a")


@pytest.mark.parametrize(
    (
        "synthesis_changed",
        "collection_changed",
        "expected_synthesis_status",
        "expected_collection_status",
    ),
    [
        (True, False, "review_required", "exact_match"),
        (False, True, "exact_match", "review_required"),
        (True, True, "review_required", "review_required"),
    ],
)
def test_phase_one_content_changes_mark_only_phase_two_for_review(
    tmp_path: Path,
    monkeypatch,
    synthesis_changed: bool,
    collection_changed: bool,
    expected_synthesis_status: str,
    expected_collection_status: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)
    reviewed_synthesis = _digest("reviewed synthesis")
    reviewed_collection = _digest("reviewed reference collection")
    current_synthesis = (
        _digest("updated synthesis")
        if synthesis_changed
        else reviewed_synthesis
    )
    current_collection = (
        _digest("expanded reference collection")
        if collection_changed
        else reviewed_collection
    )

    graph = _install_phase_two_literature_alignment(
        project,
        monkeypatch,
        identity,
        current_synthesis=current_synthesis,
        current_collection=current_collection,
        reviewed_synthesis=reviewed_synthesis,
        reviewed_collection=reviewed_collection,
    )

    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {edge["id"]: edge for edge in graph["edges"]}
    assert edges[
        knowledge_schema.P1_P2_SYNTHESIS_EDGE_ID
    ]["alignment_status"] == expected_synthesis_status
    assert edges[
        knowledge_schema.P1_P2_COLLECTION_EDGE_ID
    ]["alignment_status"] == expected_collection_status
    assert nodes["p2-method"]["status"]["alignment_status"] == (
        "review_required"
    )
    for edge_id in (
        "p2-method--p3-theory:method_definition",
        "p2-method--p4-empirical:method_definition",
    ):
        assert edges[edge_id]["alignment_status"] == "exact_match"
    assert nodes["p3-theory"]["status"]["alignment_status"] == "exact_match"
    assert nodes["p4-empirical"]["status"]["alignment_status"] == "exact_match"


def test_legacy_method_without_literature_provenance_requires_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)

    graph = _install_phase_two_literature_alignment(
        project,
        monkeypatch,
        identity,
        current_synthesis=_digest("current synthesis"),
        current_collection=_digest("current reference collection"),
        reviewed_synthesis=None,
        reviewed_collection=None,
    )

    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {edge["id"]: edge for edge in graph["edges"]}
    for edge_id in (
        knowledge_schema.P1_P2_SYNTHESIS_EDGE_ID,
        knowledge_schema.P1_P2_COLLECTION_EDGE_ID,
    ):
        assert edges[edge_id]["expected"]["sha256"] is None
        assert edges[edge_id]["alignment_status"] == "review_required"
    assert nodes["p2-method"]["source_run_id"] is None
    assert nodes["p2-method"]["status"]["alignment_status"] == (
        "review_required"
    )
    assert nodes["p3-theory"]["status"]["alignment_status"] == "exact_match"
    assert nodes["p4-empirical"]["status"]["alignment_status"] == "exact_match"


def test_phase_two_review_clears_literature_alignment_when_content_matches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    identity = _method(project)
    synthesis = _digest("current synthesis")
    collection = _digest("current reference collection")

    graph = _install_phase_two_literature_alignment(
        project,
        monkeypatch,
        identity,
        current_synthesis=synthesis,
        current_collection=collection,
        reviewed_synthesis=synthesis,
        reviewed_collection=collection,
    )

    nodes = {node["id"]: node for node in graph["nodes"]}
    edges = {edge["id"]: edge for edge in graph["edges"]}
    for edge_id in (
        knowledge_schema.P1_P2_SYNTHESIS_EDGE_ID,
        knowledge_schema.P1_P2_COLLECTION_EDGE_ID,
    ):
        assert edges[edge_id]["alignment_status"] == "exact_match"
    assert nodes["p2-method"]["source_run_id"] == "p2-review-run"
    assert nodes["p2-method"]["status"]["alignment_status"] == "exact_match"
    assert nodes["p3-theory"]["status"]["alignment_status"] == "exact_match"
    assert nodes["p4-empirical"]["status"]["alignment_status"] == "exact_match"
