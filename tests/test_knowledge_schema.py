"""Focused tests for the bounded branch basis graph schema."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from core import knowledge_graph, knowledge_schema


def _write_method(project: Path) -> None:
    menu = project / "ideas" / "methods"
    menu.mkdir(parents=True)
    (menu / "method-a.md").write_text(
        "---\n"
        "stable_id: method-a\n"
        "version: v1\n"
        "label: Method A\n"
        "status: recommended\n"
        "number: 1\n"
        "---\n\n"
        "# Method A\n\n"
        "A bounded statistical method definition.\n",
        encoding="utf-8",
    )


def _missing_record_graph(tmp_path: Path) -> dict:
    project = tmp_path / "project"
    project.mkdir()
    _write_method(project)
    return knowledge_graph.build_branch_basis_graph(project, "method-a")


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], "exact_match"),
        (["exact_match"], "exact_match"),
        (["not_available", "exact_match"], "not_available"),
        (["review_required", "not_available"], "review_required"),
        (
            ["blocked", "review_required", "not_available"],
            "blocked",
        ),
    ],
)
def test_alignment_aggregation_uses_mechanical_severity_order(
    values: list[str],
    expected: str,
) -> None:
    assert knowledge_schema.aggregate_alignment_status(values) == expected


def test_alignment_aggregation_rejects_unknown_status() -> None:
    with pytest.raises(
        knowledge_schema.KnowledgeSchemaError,
        match="unsupported status",
    ):
        knowledge_schema.aggregate_alignment_status(["scientifically_valid"])


def test_schema_round_trip_is_deterministic_and_bounded(tmp_path: Path) -> None:
    graph = _missing_record_graph(tmp_path)

    first = knowledge_schema.graph_bytes(graph)
    second = knowledge_schema.graph_bytes(graph)
    parsed = knowledge_schema.parse_graph_bytes(first)

    assert first == second
    assert parsed == graph
    assert len(first) <= knowledge_schema.MAX_GRAPH_BYTES
    assert graph["graph_sha256"] == parsed["graph_sha256"]


def test_schema_separates_record_alignment_and_scientific_status(
    tmp_path: Path,
) -> None:
    graph = _missing_record_graph(tmp_path)
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert nodes["p2-method"]["status"] == {
        "record_freshness": "current",
        "alignment_status": "not_available",
        "scientific_status": "not_assessed",
    }
    assert nodes["p3-theory"]["status"] == {
        "record_freshness": "missing",
        "alignment_status": "not_available",
        "scientific_status": "not_assessed",
    }
    assert graph["summary"] == {
        "record_freshness": "partial",
        "alignment_status": "not_available",
        "scientific_status": "not_assessed",
    }


def test_schema_rejects_extra_fields_and_unbounded_diagnostics(
    tmp_path: Path,
) -> None:
    graph = _missing_record_graph(tmp_path)
    unsealed = {
        key: copy.deepcopy(value)
        for key, value in graph.items()
        if key != "graph_sha256"
    }
    unsealed["unexpected"] = True
    with pytest.raises(
        knowledge_schema.KnowledgeSchemaError,
        match="unexpected unexpected",
    ):
        knowledge_schema.seal_graph(unsealed)

    del unsealed["unexpected"]
    unsealed["nodes"][1]["diagnostics"] = [
        "x" * (knowledge_schema.MAX_DIAGNOSTIC_LENGTH + 1)
    ]
    with pytest.raises(
        knowledge_schema.KnowledgeSchemaError,
        match="diagnostic",
    ):
        knowledge_schema.seal_graph(unsealed)


def test_schema_rejects_fingerprint_tampering_and_duplicate_json_fields(
    tmp_path: Path,
) -> None:
    graph = _missing_record_graph(tmp_path)
    tampered = copy.deepcopy(graph)
    tampered["nodes"][1]["facts"]["item_count"] = 1

    with pytest.raises(
        knowledge_schema.KnowledgeSchemaError,
        match="fingerprint",
    ):
        knowledge_schema.validate_graph(tampered)

    with pytest.raises(
        knowledge_schema.KnowledgeSchemaError,
        match="duplicate field",
    ):
        knowledge_schema.parse_graph_bytes(
            b'{"schema_version":1,"schema_version":1}'
        )


def test_parser_retains_sealed_schema_one_read_compatibility(
    tmp_path: Path,
) -> None:
    current = _missing_record_graph(tmp_path)
    legacy_source = {
        key: copy.deepcopy(value)
        for key, value in current.items()
        if key != "graph_sha256"
    }
    legacy_source["schema_version"] = knowledge_schema.LEGACY_SCHEMA_VERSION
    legacy_source["edges"] = [
        edge
        for edge in legacy_source["edges"]
        if edge["id"] in knowledge_schema.LEGACY_EDGE_IDS
    ]
    for edge in legacy_source["edges"]:
        del edge["expected"]["method_identity"]
        del edge["observed"]["method_identity"]
    legacy_p2 = next(
        node for node in legacy_source["nodes"] if node["id"] == "p2-method"
    )
    legacy_p2["source_run_id"] = None
    legacy_p2["status"]["alignment_status"] = "exact_match"
    legacy_source["summary"] = knowledge_schema.summarize_nodes(
        legacy_source["nodes"]
    )

    legacy = knowledge_schema.seal_graph(legacy_source)
    parsed = knowledge_schema.parse_graph_bytes(
        knowledge_schema.graph_bytes(legacy)
    )

    assert parsed == legacy
    assert parsed["schema_version"] == 1
    assert tuple(edge["id"] for edge in parsed["edges"]) == (
        knowledge_schema.LEGACY_EDGE_IDS
    )


def test_parser_retains_sealed_schema_two_read_compatibility(
    tmp_path: Path,
) -> None:
    current = _missing_record_graph(tmp_path)
    schema_two_source = {
        key: copy.deepcopy(value)
        for key, value in current.items()
        if key != "graph_sha256"
    }
    schema_two_source["schema_version"] = (
        knowledge_schema.SEMANTIC_SCHEMA_VERSION
    )
    schema_two_source["edges"] = [
        edge
        for edge in schema_two_source["edges"]
        if edge["id"] in knowledge_schema.SCHEMA_TWO_EDGE_IDS
    ]
    schema_two_p2 = next(
        node for node in schema_two_source["nodes"] if node["id"] == "p2-method"
    )
    schema_two_p2["source_run_id"] = None
    schema_two_p2["status"]["alignment_status"] = "exact_match"
    schema_two_source["summary"] = knowledge_schema.summarize_nodes(
        schema_two_source["nodes"]
    )

    schema_two = knowledge_schema.seal_graph(schema_two_source)
    parsed = knowledge_schema.parse_graph_bytes(
        knowledge_schema.graph_bytes(schema_two)
    )

    assert parsed == schema_two
    assert parsed["schema_version"] == 2
    assert tuple(edge["id"] for edge in parsed["edges"]) == (
        knowledge_schema.SCHEMA_TWO_EDGE_IDS
    )


def test_parser_retains_sealed_schema_three_read_compatibility(
    tmp_path: Path,
) -> None:
    current = _missing_record_graph(tmp_path)
    schema_three_source = {
        key: copy.deepcopy(value)
        for key, value in current.items()
        if key != "graph_sha256"
    }
    schema_three_source["schema_version"] = (
        knowledge_schema.COLLECTION_SCHEMA_VERSION
    )
    schema_three_source["edges"] = [
        edge
        for edge in schema_three_source["edges"]
        if edge["id"] in knowledge_schema.SCHEMA_THREE_EDGE_IDS
    ]
    schema_three_p2 = next(
        node
        for node in schema_three_source["nodes"]
        if node["id"] == "p2-method"
    )
    schema_three_p2["source_run_id"] = None
    schema_three_p2["status"]["alignment_status"] = "exact_match"
    schema_three_source["summary"] = knowledge_schema.summarize_nodes(
        schema_three_source["nodes"]
    )

    schema_three = knowledge_schema.seal_graph(schema_three_source)
    parsed = knowledge_schema.parse_graph_bytes(
        knowledge_schema.graph_bytes(schema_three)
    )

    assert parsed == schema_three
    assert parsed["schema_version"] == 3
    assert tuple(edge["id"] for edge in parsed["edges"]) == (
        knowledge_schema.SCHEMA_THREE_EDGE_IDS
    )
