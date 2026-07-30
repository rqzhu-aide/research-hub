from __future__ import annotations

import copy
from pathlib import Path

from core import web_branch_status, web_phase_data


def _method() -> dict[str, str]:
    return {
        "stable_id": "method-a",
        "version": "v2",
        "sha256": "a" * 64,
    }


_EDGE_IDS = (
    "p1-literature--p2-method:p1_synthesis",
    "p1-literature--p2-method:p1_collection",
    "p1-literature--p5-manuscript:p1_synthesis",
    "p1-literature--p5-manuscript:p1_collection",
    "p2-method--p3-theory:method_definition",
    "p2-method--p4-empirical:method_definition",
    "p2-method--p5-manuscript:p2_definition",
    "p4-empirical--p3-theory:counterpart_basis",
    "p3-theory--p4-empirical:counterpart_basis",
    "p3-theory--p5-manuscript:p3_record",
    "p4-empirical--p5-manuscript:p4_index",
    "p4-empirical--p5-manuscript:p4_synthesis",
)


def _node(
    node_id: str,
    *,
    freshness: str = "current",
    alignment: str = "exact_match",
    generation: int | None = 1,
    item_count: int | None = None,
    outdated: int = 0,
    unresolved: int = 0,
    diagnostics: list[str] | None = None,
) -> dict:
    return {
        "id": node_id,
        "generation": generation,
        "source_run_id": f"{node_id}-run" if generation is not None else None,
        "facts": {
            "item_count": item_count,
            "outdated_count": outdated,
            "unresolved_count": unresolved,
        },
        "status": {
            "record_freshness": freshness,
            "alignment_status": alignment,
        },
        "diagnostics": list(diagnostics or []),
    }


def _graph(
    nodes: list[dict],
    *,
    edge_overrides: dict[str, str | dict] | None = None,
) -> dict:
    overrides = edge_overrides or {}
    if not any(node.get("id") == "p2-method" for node in nodes):
        nodes = [_node("p2-method", generation=None), *nodes]

    edges: list[dict] = []
    current_method = {
        "stable_id": "method-a",
        "version": "v2",
        "definition_sha256": "a" * 64,
    }
    for edge_id in _EDGE_IDS:
        override = overrides.get(edge_id, "exact_match")
        edge = {
            "id": edge_id,
            "alignment_status": (
                override
                if isinstance(override, str)
                else override["alignment_status"]
            ),
            "expected": {},
            "observed": {},
        }
        if edge_id.startswith("p2-method--"):
            edge["expected"] = {
                "sha256": "a" * 64,
                "generation": None,
                "method_identity": dict(current_method),
            }
            edge["observed"] = copy.deepcopy(edge["expected"])
        if isinstance(override, dict):
            edge.update(override)
        edges.append(edge)
    return {
        "branch": {
            "stable_id": "method-a",
            "version": "v2",
            "definition_sha256": "a" * 64,
        },
        "nodes": nodes,
        "edges": edges,
        "graph_sha256": "b" * 64,
    }


def _install_heads(monkeypatch, *, version: str = "h" * 64) -> None:
    monkeypatch.setattr(
        web_branch_status.knowledge_heads,
        "derive_live_heads",
        lambda *_args: {"verified": True},
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_heads,
        "heads_version",
        lambda _heads: version,
    )


def test_phase_two_review_version_excludes_downstream_records() -> None:
    graph = _graph([
        _node("p3-theory"),
        _node("p4-empirical"),
        _node("p5-manuscript"),
    ])
    initial = (
        web_branch_status.knowledge_graph.phase_two_review_projection_version(
            graph
        )
    )

    downstream_change = copy.deepcopy(graph)
    downstream_change["nodes"][1]["source_run_id"] = "new-theory-run"
    assert (
        web_branch_status.knowledge_graph.phase_two_review_projection_version(
            downstream_change
        )
        == initial
    )

    literature_change = copy.deepcopy(graph)
    literature_change["edges"][0]["observed"] = {"sha256": "c" * 64}
    assert (
        web_branch_status.knowledge_graph.phase_two_review_projection_version(
            literature_change
        )
        != initial
    )


def test_method_record_statuses_use_current_packages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    method = _method()
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: {"method-a"},
    )
    graph = _graph([
        _node("p3-theory", generation=2),
        _node(
            "p4-empirical",
            alignment="review_required",
            generation=5,
            item_count=5,
            outdated=1,
            unresolved=2,
        ),
        _node("p5-manuscript", generation=3),
    ])
    graph_calls: list[str] = []
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda _root, stable_id: graph_calls.append(stable_id) or graph,
    )
    _install_heads(monkeypatch)

    status = web_branch_status.method_record_statuses(
        tmp_path, [method]
    )[0]

    assert status["has_theory_history"] is True
    assert status["knowledge_heads_version"] == "h" * 64
    assert status["phase_two_review_version"] == (
        web_branch_status.knowledge_graph.phase_two_review_projection_version(
            graph
        )
    )
    assert graph_calls == ["method-a"]
    assert status["record_status"]["theory"] == {
        "state": "current",
        "label": "Theory is aligned",
        "reason": (
            "The theory package matches the current method and the current "
            "decision-relevant Phase 4 conclusions and evidence."
        ),
        "generation": 2,
        "source_run_id": "p3-theory-run",
    }
    empirical = status["record_status"]["empirical"]
    assert empirical["state"] == "update_needed"
    assert empirical["label"] == "Empirical evidence requires re-evaluation"
    assert empirical["reason"] == (
        "The evidence index contains 1 outdated and 2 unresolved entries."
    )
    assert empirical["indexed_evidence_count"] == 5
    assert empirical["current_evidence_count"] == 2
    assert empirical["outdated_evidence_count"] == 1
    assert empirical["unresolved_evidence_count"] == 2
    assert empirical["method_applicability"]["state"] == (
        "valid_current_version"
    )
    assert empirical["sibling_basis"]["state"] == "current"
    assert empirical["research_attention"]["state"] == "required"
    assert status["record_status"]["manuscript"]["state"] == "current"
    assert status["launch_context_error"] == ""


def test_phase_four_signals_separate_method_basis_and_attention(
    tmp_path: Path,
    monkeypatch,
) -> None:
    method_edge = "p2-method--p4-empirical:method_definition"
    counterpart_edge = "p3-theory--p4-empirical:counterpart_basis"
    previous_method = {
        "stable_id": "method-a",
        "version": "v1",
        "definition_sha256": "c" * 64,
    }
    current_method = {
        "stable_id": "method-a",
        "version": "v2",
        "definition_sha256": "a" * 64,
    }
    graph = _graph(
        [
            _node("p3-theory"),
            _node("p4-empirical", alignment="review_required", item_count=3),
            _node("p5-manuscript"),
        ],
        edge_overrides={
            method_edge: {
                "alignment_status": "review_required",
                "expected": {
                    "sha256": "c" * 64,
                    "generation": None,
                    "method_identity": previous_method,
                },
                "observed": {
                    "sha256": "a" * 64,
                    "generation": None,
                    "method_identity": current_method,
                },
            },
            counterpart_edge: "exact_match",
        },
    )
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    empirical = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]["empirical"]

    assert empirical["method_applicability"]["state"] == "previous_version"
    assert empirical["method_applicability"]["rerun_required"] is True
    assert empirical["sibling_basis"]["state"] == "current"
    assert empirical["research_attention"]["state"] == "none"


def test_phase_four_signals_report_changed_theory_without_method_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    counterpart_edge = "p3-theory--p4-empirical:counterpart_basis"
    graph = _graph(
        [
            _node("p3-theory"),
            _node("p4-empirical", alignment="review_required", item_count=2),
            _node("p5-manuscript"),
        ],
        edge_overrides={counterpart_edge: "review_required"},
    )
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    empirical = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]["empirical"]

    assert empirical["method_applicability"]["state"] == (
        "valid_current_version"
    )
    assert empirical["sibling_basis"]["state"] == "changed"
    assert empirical["research_attention"]["state"] == "none"


def test_reference_collection_change_marks_only_manuscript_for_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    collection_edge = "p1-literature--p5-manuscript:p1_collection"
    graph = _graph(
        [
            _node("p3-theory"),
            _node("p4-empirical", item_count=2),
            _node("p5-manuscript", alignment="review_required"),
        ],
        edge_overrides={
            collection_edge: {
                "alignment_status": "review_required",
                "expected": {"sha256": "1" * 64},
                "observed": {"sha256": "2" * 64},
            },
        },
    )
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    records = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]

    assert records["theory"]["state"] == "current"
    assert records["empirical"]["state"] == "current"
    assert records["manuscript"]["state"] == "update_needed"
    assert (
        records["manuscript"]["label"] == "Manuscript inputs need review"
    )
    assert records["manuscript"]["reason"] == (
        "The Phase 1 reference collection has changed since the manuscript "
        "was generated."
    )
    assert records["manuscript"]["changed_input_labels"] == [
        "Phase 1 reference collection"
    ]


def test_phase_one_collection_and_synthesis_changes_have_one_compact_reason(
    tmp_path: Path,
    monkeypatch,
) -> None:
    collection_edge = "p1-literature--p5-manuscript:p1_collection"
    synthesis_edge = "p1-literature--p5-manuscript:p1_synthesis"
    graph = _graph(
        [
            _node("p3-theory"),
            _node("p4-empirical", item_count=2),
            _node("p5-manuscript", alignment="review_required"),
        ],
        edge_overrides={
            collection_edge: {
                "alignment_status": "review_required",
                "expected": {"sha256": "1" * 64},
                "observed": {"sha256": "2" * 64},
            },
            synthesis_edge: {
                "alignment_status": "review_required",
                "expected": {"sha256": "3" * 64},
                "observed": {"sha256": "4" * 64},
            },
        },
    )
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    manuscript = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]["manuscript"]

    assert manuscript["reason"] == (
        "The Phase 1 reference collection and literature synthesis have "
        "changed since the manuscript was generated."
    )
    assert manuscript["changed_input_labels"] == [
        "Phase 1 reference collection",
        "Phase 1 literature synthesis",
    ]


def test_legacy_manuscript_collection_basis_is_yellow_not_invalid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    collection_edge = "p1-literature--p5-manuscript:p1_collection"
    graph = _graph(
        [
            _node("p3-theory"),
            _node("p4-empirical", item_count=2),
            _node("p5-manuscript", alignment="review_required"),
        ],
        edge_overrides={
            collection_edge: {
                "alignment_status": "review_required",
                "expected": {"sha256": None},
                "observed": {"sha256": "2" * 64},
            },
        },
    )
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    manuscript = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]["manuscript"]

    assert manuscript["state"] == "update_needed"
    assert manuscript["reason"] == (
        "This manuscript was created before Research Hub recorded its exact "
        "Phase 1 reference collection."
    )


def test_current_theory_reason_distinguishes_an_absent_phase_four_package(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph = _graph([
        _node("p3-theory"),
        _node(
            "p4-empirical",
            freshness="missing",
            alignment="not_available",
            generation=None,
        ),
        _node(
            "p5-manuscript",
            freshness="missing",
            alignment="not_available",
            generation=None,
        ),
    ])
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    records = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]

    assert records["theory"]["state"] == "current"
    assert records["theory"]["reason"] == (
        "The theory package matches the current method. No Phase 4 empirical "
        "package existed for this theory run, and none exists now."
    )
    assert records["empirical"]["state"] == "not_run"


def test_method_revision_marks_branch_records_for_update(
    tmp_path: Path,
    monkeypatch,
) -> None:
    method = _method()
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    graph = _graph(
        [
            _node("p3-theory", alignment="review_required"),
            _node("p4-empirical", alignment="review_required", item_count=0),
            _node("p5-manuscript", alignment="review_required"),
        ],
        edge_overrides={
            "p2-method--p3-theory:method_definition": "review_required",
            "p2-method--p4-empirical:method_definition": "review_required",
            "p2-method--p5-manuscript:p2_definition": "review_required",
        },
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    status = web_branch_status.method_record_statuses(
        tmp_path, [method]
    )[0]["record_status"]

    assert status["theory"]["state"] == "update_needed"
    assert "earlier Phase 2 method definition" in status["theory"]["reason"]
    assert status["empirical"]["state"] == "update_needed"
    assert "earlier Phase 2 method definition" in status["empirical"]["reason"]
    assert status["manuscript"]["state"] == "update_needed"
    assert "earlier Phase 2 method definition" in status["manuscript"]["reason"]


def test_current_record_with_unavailable_alignment_needs_update(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph = _graph(
        [
            _node("p3-theory", alignment="not_available"),
            _node("p4-empirical", item_count=0),
            _node(
                "p5-manuscript",
                freshness="missing",
                alignment="not_available",
                generation=None,
            ),
        ],
        edge_overrides={
            "p4-empirical--p3-theory:counterpart_basis": "not_available",
        },
    )
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    theory = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]["theory"]

    assert theory["state"] == "update_needed"
    assert theory["label"] == "Theory requires re-evaluation"
    assert "information needed by Phase 3 theory is absent" in theory["reason"]


def test_status_reason_identifies_legacy_counterpart_basis(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph = _graph(
        [
            _node("p3-theory", alignment="review_required"),
            _node("p4-empirical", item_count=1),
            _node(
                "p5-manuscript",
                freshness="missing",
                alignment="not_available",
                generation=None,
            ),
        ],
        edge_overrides={
            "p4-empirical--p3-theory:counterpart_basis": {
                "alignment_status": "review_required",
                "expected": {"state": "unknown_legacy"},
                "observed": {"state": "available"},
            },
        },
    )
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    records = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]
    theory = records["theory"]

    assert theory["state"] == "update_needed"
    assert theory["reason"] == (
        "The Phase 3 theory record was created before Research Hub recorded "
        "which Phase 4 empirical conclusions and evidence it used."
    )
    assert records["manuscript"]["state"] == "not_run"
    assert records["manuscript"]["reason"] == (
        "No current Phase 5 manuscript exists for this method."
    )


def test_missing_blocked_and_invalid_graph_states_are_distinct(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph = _graph(
        [
            _node(
                "p3-theory",
                freshness="invalid",
                alignment="blocked",
                generation=None,
                diagnostics=["canonical proof record is invalid"],
            ),
            _node(
                "p4-empirical",
                freshness="missing",
                alignment="not_available",
                generation=None,
            ),
            _node("p5-manuscript", alignment="blocked"),
        ],
        edge_overrides={
            "p2-method--p3-theory:method_definition": "blocked",
            "p3-theory--p5-manuscript:p3_record": "blocked",
            "p4-empirical--p5-manuscript:p4_index": "blocked",
            "p4-empirical--p5-manuscript:p4_synthesis": "blocked",
        },
    )
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    _install_heads(monkeypatch)

    records = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]["record_status"]

    assert records["theory"]["state"] == "invalid"
    assert "canonical proof record is invalid" in records["theory"]["reason"]
    assert records["empirical"]["state"] == "not_run"
    assert records["manuscript"]["state"] == "invalid"
    assert "cannot be verified" in records["manuscript"]["reason"]
    assert len(records["manuscript"]["reason"]) <= 900


def test_graph_build_failure_marks_branch_records_invalid(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: {"method-a"},
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: (_ for _ in ()).throw(
            web_branch_status.knowledge_graph.KnowledgeGraphBuildError(
                "method catalog is inconsistent"
            )
        ),
    )
    _install_heads(monkeypatch, version="v" * 64)

    result = web_branch_status.method_record_statuses(
        tmp_path, [_method()]
    )[0]

    assert result["has_theory_history"] is True
    assert result["knowledge_heads_version"] == "v" * 64
    assert result["launch_context_error"] == (
        "The current method and branch records cannot be verified for a new run."
    )
    for record in result["record_status"].values():
        assert record["state"] == "invalid"
        assert "method catalog is inconsistent" in record["reason"]


def test_head_derivation_failure_makes_method_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph = _graph([
        _node("p3-theory"),
        _node("p4-empirical"),
        _node("p5-manuscript", freshness="missing", alignment="not_available"),
    ])
    monkeypatch.setattr(
        web_branch_status,
        "_methods_with_theory_history",
        lambda _root: set(),
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_graph,
        "build_branch_basis_graph",
        lambda *_args: graph,
    )
    monkeypatch.setattr(
        web_branch_status.knowledge_heads,
        "derive_live_heads",
        lambda *_args: (_ for _ in ()).throw(ValueError("bad heads")),
    )

    result = web_branch_status.method_record_statuses(tmp_path, [_method()])[0]

    assert result["record_status"]["theory"]["state"] == "current"
    assert result["knowledge_heads_version"] is None
    assert result["launch_context_error"] == (
        "The current Phase 3 and Phase 4 records cannot be verified for a new run."
    )


def test_phase_record_aggregate_keeps_invalid_state_red() -> None:
    methods = [
        {
            "stable_id": "invalid-method",
            "label": "Invalid Method",
            "status": "active",
            "record_status": {"theory": {"state": "invalid"}},
        },
        {
            "stable_id": "changed-method",
            "label": "Changed Method",
            "status": "active",
            "record_status": {"theory": {"state": "update_needed"}},
        },
    ]

    aggregate = web_branch_status.aggregate_phase_record_status(
        "03-idea-evaluation", methods
    )

    assert aggregate["state"] == "invalid"
    assert aggregate["label"] == (
        "Phase 3 theory cannot be verified for 1 of 2 active methods"
    )
    assert aggregate["affected_method_ids"] == [
        "invalid-method",
        "changed-method",
    ]
    assert aggregate["invalid_count"] == 1
    assert "Check record integrity for: Invalid Method." in aggregate["reason"]
    assert "then decide whether a rerun is needed" in aggregate["reason"]

def test_phase_record_aggregate_reports_only_affected_methods() -> None:
    methods = [
        {
            "stable_id": "method-a",
            "status": "active",
            "record_status": {
                "theory": {"state": "update_needed"},
            },
        },
        {
            "stable_id": "method-b",
            "status": "active",
            "record_status": {
                "theory": {"state": "current"},
            },
        },
        {
            "stable_id": "method-retired",
            "status": "retired",
            "record_status": {
                "theory": {"state": "update_needed"},
            },
        },
    ]

    aggregate = web_branch_status.aggregate_phase_record_status(
        "03-idea-evaluation", methods
    )

    assert aggregate == {
        "state": "stale",
        "label": "Phase 3 theory alignment needs review for 1 of 2 active methods",
        "reason": (
            "Review phase 3 theory alignment for: method-a, then decide whether "
            "a rerun is needed."
        ),
        "affected_method_ids": ["method-a"],
        "active_count": 2,
        "current_count": 1,
        "not_run_count": 0,
        "invalid_count": 0,
    }


def test_phase_record_aggregate_reports_partially_completed_methods() -> None:
    methods = [
        {
            "stable_id": "method-a",
            "status": "active",
            "record_status": {
                "empirical": {"state": "current"},
            },
        },
        {
            "stable_id": "method-b",
            "status": "active",
            "record_status": {
                "empirical": {"state": "not_run"},
            },
        },
    ]

    aggregate = web_branch_status.aggregate_phase_record_status(
        "04-draft-assembly", methods
    )

    assert aggregate["state"] == "partial"
    assert aggregate["label"] == (
        "Phase 4 empirical work is current for 1 of 2 active methods"
    )
    assert aggregate["affected_method_ids"] == []
    assert aggregate["current_count"] == 1
    assert aggregate["not_run_count"] == 1


def _web_method(
    stable_id: str,
    record_state: str,
    *,
    retired: bool = False,
) -> dict:
    return {
        "stable_id": stable_id,
        "status": "retired" if retired else "active",
        "errors": [],
        "record_status": {
            "theory": {
                "state": record_state,
                "label": record_state,
            },
        },
    }


def _web_run(run_id: str, status: str, *, current_updated: bool) -> dict:
    return {
        "run_id": run_id,
        "status": status,
        "display_status": status,
        "number": 1,
        "rounds_completed": 1,
        "rounds_requested": 1,
        "current_updated": current_updated,
        "integrity_error": False,
        "started": "2026-01-01T00:00:00+00:00",
        "completed": "2026-01-01T00:01:00+00:00",
    }


def _install_web_status_fakes(
    monkeypatch,
    *,
    state: dict,
    methods: list[dict],
    run_views: list[dict],
) -> None:
    monkeypatch.setattr(web_phase_data.project_state, "load", lambda *_args: state)
    monkeypatch.setattr(
        web_phase_data,
        "_method_details",
        lambda *_args: [dict(method) for method in methods],
    )
    monkeypatch.setattr(
        web_phase_data,
        "_phase_runs",
        lambda *_args: [dict(run) for run in run_views],
    )
    monkeypatch.setattr(
        web_phase_data.method_menu,
        "load_method_menu",
        lambda *_args: {"entries": [], "warnings": []},
    )
    monkeypatch.setattr(
        web_phase_data.method_menu,
        "catalog_version",
        lambda *_args: "a" * 64,
    )
    monkeypatch.setattr(
        web_phase_data.web_prerequisites,
        "phase_prerequisite_report",
        lambda *_args: {
            "phase": "03-idea-evaluation",
            "policy": "current_records",
            "satisfied": True,
            "blockers": [],
            "requirements": [],
        },
    )


def test_phase_and_overview_use_all_active_method_records(
    tmp_path: Path,
    monkeypatch,
) -> None:
    phase_slug = "03-idea-evaluation"
    current = _web_run("run-method-b", "completed", current_updated=True)
    phase_state = {
        "status": "completed",
        "current_run": current["run_id"],
        "latest_run": current["run_id"],
        "stale": False,
        "runs": [current],
    }
    state = {"phases": {phase_slug: phase_state}, "active_run": None}
    methods = [
        _web_method("method-a", "update_needed"),
        _web_method("method-b", "current"),
        _web_method("method-retired", "update_needed", retired=True),
    ]
    _install_web_status_fakes(
        monkeypatch,
        state=state,
        methods=methods,
        run_views=[current],
    )
    phase = {
        "slug": phase_slug,
        "name": "Theory",
        "method_binding": True,
        "pattern": "parallel",
        "rounds": {"min": 1, "default": 1, "max": 1},
        "gated_by": [],
        "members": [],
    }

    phase_data = web_phase_data.prepare_phase_data(tmp_path, 1, phase, [phase])
    overview = web_phase_data.prepare_overview_data(tmp_path, [phase])[0]

    for view in (phase_data, overview):
        assert view["decision_state"] == "stale"
        assert view["stale"] is True
        assert view["branch_status_summary"]["affected_method_ids"] == [
            "method-a"
        ]
        assert "1 of 2 active methods" in view["decision_label"]


def test_newer_failed_run_remains_visible_when_branch_records_are_current(
    tmp_path: Path,
    monkeypatch,
) -> None:
    phase_slug = "03-idea-evaluation"
    current = _web_run("run-current", "completed", current_updated=True)
    failed = _web_run("run-failed", "failed", current_updated=False)
    phase_state = {
        "status": "completed",
        "current_run": current["run_id"],
        "latest_run": failed["run_id"],
        "stale": False,
        "runs": [current, failed],
    }
    state = {"phases": {phase_slug: phase_state}, "active_run": None}
    _install_web_status_fakes(
        monkeypatch,
        state=state,
        methods=[_web_method("method-a", "current")],
        run_views=[current, failed],
    )
    phase = {"slug": phase_slug, "name": "Theory", "gated_by": []}

    overview = web_phase_data.prepare_overview_data(tmp_path, [phase])[0]

    assert overview["branch_status_summary"]["state"] == "current"
    assert overview["decision_state"] == "failed"
    assert overview["decision_label"] == "Run failed; current result preserved"
    assert overview["stale"] is False


def test_archived_summary_option_requires_usable_noncurrent_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    prompts = web_branch_status.launch_prompts
    phase_slug = "03-idea-evaluation"
    stable_id = "method-a"
    current = {
        "run_id": "run-current",
        "status": "completed",
        "final_summary": "current.html",
        "decision_record": {
            "data": {"scientific_outcome": "Complete"},
        },
    }
    archived = {
        "run_id": "run-archived",
        "status": "failed",
        "final_summary": "archived.html",
        "decision_record": {
            "data": {"scientific_outcome": "Complete"},
        },
    }
    phase_state = {
        "current_run": current["run_id"],
        "current_runs": {stable_id: current["run_id"]},
        "runs": [current, archived],
    }
    monkeypatch.setattr(
        prompts.project_state,
        "load",
        lambda *_args: {"phases": {phase_slug: phase_state}},
    )
    monkeypatch.setattr(
        prompts,
        "_sealed_run_method_selection",
        lambda *_args: {"stable_id": stable_id, "version": "v1"},
    )
    monkeypatch.setattr(
        prompts.project_state,
        "run_integrity_report",
        lambda *_args: {"ok": True},
    )

    assert not prompts._has_archived_method_summary(
        tmp_path, phase_slug, stable_id
    )

    archived["status"] = "completed"
    assert prompts._has_archived_method_summary(
        tmp_path, phase_slug, stable_id
    )

    archived["decision_record"]["data"]["scientific_outcome"] = "Failed"
    assert not prompts._has_archived_method_summary(
        tmp_path, phase_slug, stable_id
    )
