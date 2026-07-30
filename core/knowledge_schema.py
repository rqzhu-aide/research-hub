"""Strict schema for rebuildable branch basis graphs.

The graph records mechanical alignment between canonical current records.
Schema 2 adds directed Phase 3 and Phase 4 semantic-basis edges. Schema 3 adds
the Phase 1 reference-collection basis used by Phase 5. Schema 4 adds the
Phase 1 basis reviewed for each Phase 2 method. All prior schemas remain
readable. The graph never infers whether a scientific claim is valid.
Canonical phase packages remain authoritative, and a graph can always be
discarded and rebuilt from them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


LEGACY_SCHEMA_VERSION = 1
SEMANTIC_SCHEMA_VERSION = 2
COLLECTION_SCHEMA_VERSION = 3
SCHEMA_VERSION = 4
GRAPH_KIND = "branch_basis_graph"
MAX_GRAPH_BYTES = 512 * 1024
MAX_NODES = 16
MAX_EDGES = 32
MAX_DIAGNOSTICS_PER_NODE = 8
MAX_DIAGNOSTIC_LENGTH = 1_000
MAX_RUN_ID_LENGTH = 300
MAX_GENERATION = 2_147_483_647
MAX_ITEM_COUNT = 1_000_000

NODE_IDS = (
    "p1-literature",
    "p2-method",
    "p3-theory",
    "p4-empirical",
    "p5-manuscript",
)
NODE_PHASES = {
    "p1-literature": "01-literature-review",
    "p2-method": "02-method-development",
    "p3-theory": "03-idea-evaluation",
    "p4-empirical": "04-draft-assembly",
    "p5-manuscript": "05-review-revision",
}
NODE_KINDS = {
    "p1-literature": "literature_record",
    "p2-method": "method_definition",
    "p3-theory": "theory_record",
    "p4-empirical": "empirical_record",
    "p5-manuscript": "manuscript_record",
}
P1_SYNTHESIS_EDGE_ID = "p1-literature--p5-manuscript:p1_synthesis"
P1_COLLECTION_EDGE_ID = "p1-literature--p5-manuscript:p1_collection"
P1_P2_SYNTHESIS_EDGE_ID = "p1-literature--p2-method:p1_synthesis"
P1_P2_COLLECTION_EDGE_ID = "p1-literature--p2-method:p1_collection"
LEGACY_EDGE_IDS = (
    P1_SYNTHESIS_EDGE_ID,
    "p2-method--p3-theory:method_definition",
    "p2-method--p4-empirical:method_definition",
    "p2-method--p5-manuscript:p2_definition",
    "p3-theory--p5-manuscript:p3_record",
    "p4-empirical--p5-manuscript:p4_index",
    "p4-empirical--p5-manuscript:p4_synthesis",
)
SEMANTIC_EDGE_IDS = (
    "p4-empirical--p3-theory:counterpart_basis",
    "p3-theory--p4-empirical:counterpart_basis",
)
SEMANTIC_EDGE_ENDPOINTS = {
    "p4-empirical--p3-theory:counterpart_basis": (
        "p4-empirical",
        "p3-theory",
    ),
    "p3-theory--p4-empirical:counterpart_basis": (
        "p3-theory",
        "p4-empirical",
    ),
}
SCHEMA_TWO_EDGE_IDS = (
    P1_SYNTHESIS_EDGE_ID,
    "p2-method--p3-theory:method_definition",
    "p2-method--p4-empirical:method_definition",
    "p2-method--p5-manuscript:p2_definition",
    *SEMANTIC_EDGE_IDS,
    "p3-theory--p5-manuscript:p3_record",
    "p4-empirical--p5-manuscript:p4_index",
    "p4-empirical--p5-manuscript:p4_synthesis",
)
SCHEMA_THREE_EDGE_IDS = (
    P1_SYNTHESIS_EDGE_ID,
    P1_COLLECTION_EDGE_ID,
    *SCHEMA_TWO_EDGE_IDS[1:],
)
EDGE_IDS = (
    P1_P2_SYNTHESIS_EDGE_ID,
    P1_P2_COLLECTION_EDGE_ID,
    *SCHEMA_THREE_EDGE_IDS,
)
P1_UNKNOWN_BASIS_REVIEW_EDGES = frozenset({
    P1_COLLECTION_EDGE_ID,
    P1_P2_SYNTHESIS_EDGE_ID,
    P1_P2_COLLECTION_EDGE_ID,
})

RECORD_FRESHNESS_VALUES = frozenset({"current", "missing", "invalid"})
ALIGNMENT_STATUS_VALUES = frozenset(
    {"exact_match", "review_required", "not_available", "blocked"}
)
SCIENTIFIC_STATUS_VALUES = frozenset({"not_assessed"})
GRAPH_FRESHNESS_VALUES = frozenset({"complete", "partial", "empty", "invalid"})

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9._/+:-]{1,200}$")
_NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,199}$")

_GRAPH_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "branch_key",
        "branch",
        "nodes",
        "edges",
        "summary",
        "graph_sha256",
    }
)
_UNSEALED_GRAPH_FIELDS = _GRAPH_FIELDS - {"graph_sha256"}
_NODE_FIELDS = frozenset(
    {
        "id",
        "phase_slug",
        "kind",
        "generation",
        "source_run_id",
        "method_identity",
        "digests",
        "facts",
        "status",
        "diagnostics",
    }
)
_DIGEST_FIELDS = frozenset(
    {"record_sha256", "primary_sha256", "collection_sha256"}
)
_FACT_FIELDS = frozenset(
    {"item_count", "outdated_count", "unresolved_count"}
)
_STATUS_FIELDS = frozenset(
    {"record_freshness", "alignment_status", "scientific_status"}
)
_EDGE_FIELDS = frozenset(
    {
        "id",
        "source",
        "target",
        "basis_slot",
        "expected",
        "observed",
        "alignment_status",
    }
)
_LEGACY_REFERENCE_FIELDS = frozenset({"sha256", "generation"})
_REFERENCE_FIELDS = frozenset(
    {"sha256", "generation", "method_identity"}
)
_SUMMARY_FIELDS = frozenset(
    {"record_freshness", "alignment_status", "scientific_status"}
)
_METHOD_FIELDS = frozenset(
    {"stable_id", "version", "definition_sha256"}
)


class KnowledgeSchemaError(ValueError):
    """A basis graph does not satisfy its bounded schema."""


def _fail(message: str) -> None:
    raise KnowledgeSchemaError(message)


def _mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be an object with text field names")
    return value


def _exact_fields(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    actual = frozenset(value)
    if actual == expected:
        return
    missing = sorted(expected.difference(actual))
    extra = sorted(actual.difference(expected))
    details: list[str] = []
    if missing:
        details.append(f"missing {', '.join(missing)}")
    if extra:
        details.append(f"unexpected {', '.join(extra)}")
    _fail(f"{label} has invalid fields: {'; '.join(details)}")


def _text(
    value: Any,
    *,
    label: str,
    maximum: int,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if type(value) is not str:
        _fail(f"{label} must be text")
    if not value or len(value) > maximum or value != value.strip():
        _fail(f"{label} must contain 1 to {maximum} trimmed characters")
    if pattern is not None and pattern.fullmatch(value) is None:
        _fail(f"{label} has an invalid format")
    return value


def _nullable_text(
    value: Any,
    *,
    label: str,
    maximum: int,
) -> str | None:
    if value is None:
        return None
    return _text(value, label=label, maximum=maximum)


def _nullable_sha256(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label=label, maximum=64, pattern=_SHA256_RE)


def _nullable_integer(
    value: Any,
    *,
    label: str,
    maximum: int,
) -> int | None:
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= maximum:
        _fail(f"{label} must be null or an integer from 0 through {maximum}")
    return value


def normalize_method_identity(value: Any) -> dict[str, str]:
    """Validate one exact Phase 2 method identity."""

    method = _mapping(value, label="method identity")
    _exact_fields(method, _METHOD_FIELDS, label="method identity")
    return {
        "stable_id": _text(
            method["stable_id"],
            label="method stable_id",
            maximum=200,
            pattern=_STABLE_ID_RE,
        ),
        "version": _text(
            method["version"],
            label="method version",
            maximum=200,
            pattern=_VERSION_RE,
        ),
        "definition_sha256": _text(
            method["definition_sha256"],
            label="method definition_sha256",
            maximum=64,
            pattern=_SHA256_RE,
        ),
    }


def branch_key(stable_id: str) -> str:
    """Return the opaque cache key for one stable method branch."""

    normalized = _text(
        stable_id,
        label="method stable_id",
        maximum=200,
        pattern=_STABLE_ID_RE,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_status(value: Any, *, label: str) -> dict[str, str]:
    status = _mapping(value, label=label)
    _exact_fields(status, _STATUS_FIELDS, label=label)
    freshness = status["record_freshness"]
    alignment = status["alignment_status"]
    scientific = status["scientific_status"]
    if freshness not in RECORD_FRESHNESS_VALUES:
        _fail(f"{label} has an unsupported record_freshness")
    if alignment not in ALIGNMENT_STATUS_VALUES:
        _fail(f"{label} has an unsupported alignment_status")
    if scientific not in SCIENTIFIC_STATUS_VALUES:
        _fail(f"{label} has an unsupported scientific_status")
    if freshness == "missing" and alignment != "not_available":
        _fail(f"{label} missing records must use not_available alignment")
    if freshness == "invalid" and alignment != "blocked":
        _fail(f"{label} invalid records must use blocked alignment")
    return {
        "record_freshness": freshness,
        "alignment_status": alignment,
        "scientific_status": scientific,
    }


def _normalize_digests(value: Any, *, label: str) -> dict[str, str | None]:
    digests = _mapping(value, label=label)
    _exact_fields(digests, _DIGEST_FIELDS, label=label)
    return {
        key: _nullable_sha256(digests[key], label=f"{label} {key}")
        for key in sorted(_DIGEST_FIELDS)
    }


def _normalize_facts(value: Any, *, label: str) -> dict[str, int | None]:
    facts = _mapping(value, label=label)
    _exact_fields(facts, _FACT_FIELDS, label=label)
    item_count = _nullable_integer(
        facts["item_count"],
        label=f"{label} item_count",
        maximum=MAX_ITEM_COUNT,
    )
    outdated = _nullable_integer(
        facts["outdated_count"],
        label=f"{label} outdated_count",
        maximum=MAX_ITEM_COUNT,
    )
    unresolved = _nullable_integer(
        facts["unresolved_count"],
        label=f"{label} unresolved_count",
        maximum=MAX_ITEM_COUNT,
    )
    if outdated is None or unresolved is None:
        _fail(f"{label} attention counts must be integers")
    if item_count is not None and outdated + unresolved > item_count:
        _fail(f"{label} attention counts exceed item_count")
    return {
        "item_count": item_count,
        "outdated_count": outdated,
        "unresolved_count": unresolved,
    }


def _normalize_node(
    value: Any,
    *,
    number: int,
    schema_version: int,
) -> dict[str, Any]:
    label = f"basis graph node {number}"
    node = _mapping(value, label=label)
    _exact_fields(node, _NODE_FIELDS, label=label)
    node_id = _text(
        node["id"],
        label=f"{label} id",
        maximum=200,
        pattern=_NODE_ID_RE,
    )
    if node_id not in NODE_PHASES:
        _fail(f"{label} has an unsupported id")
    if node["phase_slug"] != NODE_PHASES[node_id]:
        _fail(f"{label} phase_slug does not match its id")
    if node["kind"] != NODE_KINDS[node_id]:
        _fail(f"{label} kind does not match its id")
    generation = _nullable_integer(
        node["generation"],
        label=f"{label} generation",
        maximum=MAX_GENERATION,
    )
    if generation == 0:
        _fail(f"{label} generation must be positive when present")
    source_run_id = _nullable_text(
        node["source_run_id"],
        label=f"{label} source_run_id",
        maximum=MAX_RUN_ID_LENGTH,
    )
    method_identity = (
        None
        if node["method_identity"] is None
        else normalize_method_identity(node["method_identity"])
    )
    digests = _normalize_digests(node["digests"], label=f"{label} digests")
    facts = _normalize_facts(node["facts"], label=f"{label} facts")
    status = _normalize_status(node["status"], label=f"{label} status")

    raw_diagnostics = node["diagnostics"]
    if not isinstance(raw_diagnostics, list):
        _fail(f"{label} diagnostics must be a list")
    if len(raw_diagnostics) > MAX_DIAGNOSTICS_PER_NODE:
        _fail(f"{label} has too many diagnostics")
    diagnostics = [
        _text(
            item,
            label=f"{label} diagnostic {index}",
            maximum=MAX_DIAGNOSTIC_LENGTH,
        )
        for index, item in enumerate(raw_diagnostics, start=1)
    ]

    freshness = status["record_freshness"]
    if freshness == "current":
        if digests["record_sha256"] is None or digests["primary_sha256"] is None:
            _fail(f"{label} current records require record and primary digests")
        if node_id != "p2-method" and (
            generation is None or source_run_id is None
        ):
            _fail(f"{label} current records require generation and source_run_id")
        if node_id == "p2-method":
            if generation is not None:
                _fail(f"{label} Phase 2 identity has no run generation")
            if (
                schema_version < SCHEMA_VERSION
                and source_run_id is not None
            ):
                _fail(
                    f"{label} legacy Phase 2 identity has no source run"
                )
    else:
        if any(item is not None for item in digests.values()):
            _fail(f"{label} noncurrent records must not publish digests")
        if generation is not None or source_run_id is not None:
            _fail(f"{label} noncurrent records must not publish run identity")
        if method_identity is not None:
            _fail(f"{label} noncurrent records must not publish method identity")
    if freshness == "invalid" and not diagnostics:
        _fail(f"{label} invalid records require one diagnostic")

    if node_id == "p1-literature":
        if method_identity is not None:
            _fail(f"{label} literature record must not have a method identity")
        if freshness == "current" and digests["collection_sha256"] is None:
            _fail(f"{label} current literature requires a collection digest")
    elif method_identity is None and freshness == "current":
        _fail(f"{label} current branch records require a method identity")

    if node_id == "p4-empirical":
        if freshness == "current" and facts["item_count"] is None:
            _fail(f"{label} current empirical records require item_count")
    elif facts["outdated_count"] or facts["unresolved_count"]:
        _fail(f"{label} only empirical records can carry attention counts")

    return {
        "id": node_id,
        "phase_slug": node["phase_slug"],
        "kind": node["kind"],
        "generation": generation,
        "source_run_id": source_run_id,
        "method_identity": method_identity,
        "digests": digests,
        "facts": facts,
        "status": status,
        "diagnostics": diagnostics,
    }


def _normalize_reference(
    value: Any,
    *,
    label: str,
    schema_version: int,
) -> dict[str, Any]:
    reference = _mapping(value, label=label)
    expected_fields = (
        _LEGACY_REFERENCE_FIELDS
        if schema_version == LEGACY_SCHEMA_VERSION
        else _REFERENCE_FIELDS
    )
    _exact_fields(reference, expected_fields, label=label)
    digest = _nullable_sha256(reference["sha256"], label=f"{label} sha256")
    generation = _nullable_integer(
        reference["generation"],
        label=f"{label} generation",
        maximum=MAX_GENERATION,
    )
    if generation == 0:
        _fail(f"{label} generation must be positive when present")
    if digest is None and generation is not None:
        _fail(f"{label} cannot have a generation without a digest")
    normalized = {"sha256": digest, "generation": generation}
    if schema_version >= SEMANTIC_SCHEMA_VERSION:
        method = (
            None
            if reference["method_identity"] is None
            else normalize_method_identity(reference["method_identity"])
        )
        if digest is None and method is not None:
            _fail(f"{label} cannot have a method identity without a digest")
        normalized["method_identity"] = method
    return normalized


def _normalize_basis_reference(
    value: Any,
    *,
    label: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    from core import knowledge_basis

    try:
        return knowledge_basis.validate_basis(value)
    except knowledge_basis.KnowledgeBasisError as exc:
        _fail(f"{label} is invalid: {exc}")
    raise AssertionError("unreachable")


def _normalize_edge(
    value: Any,
    *,
    number: int,
    schema_version: int,
) -> dict[str, Any]:
    label = f"basis graph edge {number}"
    edge = _mapping(value, label=label)
    _exact_fields(edge, _EDGE_FIELDS, label=label)
    edge_id = _text(edge["id"], label=f"{label} id", maximum=300)
    source = _text(
        edge["source"],
        label=f"{label} source",
        maximum=200,
        pattern=_NODE_ID_RE,
    )
    target = _text(
        edge["target"],
        label=f"{label} target",
        maximum=200,
        pattern=_NODE_ID_RE,
    )
    basis_slot = _text(
        edge["basis_slot"],
        label=f"{label} basis_slot",
        maximum=100,
        pattern=_NODE_ID_RE,
    )
    alignment = edge["alignment_status"]
    if alignment not in ALIGNMENT_STATUS_VALUES:
        _fail(f"{label} has an unsupported alignment_status")
    if schema_version >= SEMANTIC_SCHEMA_VERSION and edge_id in SEMANTIC_EDGE_IDS:
        if (
            (source, target) != SEMANTIC_EDGE_ENDPOINTS[edge_id]
            or basis_slot != "counterpart_basis"
        ):
            _fail(f"{label} semantic edge endpoints are invalid")
        expected = _normalize_basis_reference(
            edge["expected"], label=f"{label} expected basis"
        )
        observed = _normalize_basis_reference(
            edge["observed"], label=f"{label} observed basis"
        )
        source_phase = NODE_PHASES[source]
        for name, basis in (("expected", expected), ("observed", observed)):
            if basis is not None and basis["phase_slug"] != source_phase:
                _fail(
                    f"{label} {name} basis phase does not match its source"
                )
    else:
        if (
            schema_version >= COLLECTION_SCHEMA_VERSION
            and edge_id == P1_COLLECTION_EDGE_ID
            and (
                (source, target) != ("p1-literature", "p5-manuscript")
                or basis_slot != "p1_collection"
            )
        ):
            _fail(f"{label} Phase 1 collection edge is invalid")
        if (
            schema_version >= SCHEMA_VERSION
            and edge_id in {
                P1_P2_SYNTHESIS_EDGE_ID,
                P1_P2_COLLECTION_EDGE_ID,
            }
        ):
            expected_slot = (
                "p1_synthesis"
                if edge_id == P1_P2_SYNTHESIS_EDGE_ID
                else "p1_collection"
            )
            if (
                (source, target) != ("p1-literature", "p2-method")
                or basis_slot != expected_slot
            ):
                _fail(f"{label} Phase 1 to Phase 2 edge is invalid")
        expected = _normalize_reference(
            edge["expected"],
            label=f"{label} expected reference",
            schema_version=schema_version,
        )
        observed = _normalize_reference(
            edge["observed"],
            label=f"{label} observed reference",
            schema_version=schema_version,
        )
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "basis_slot": basis_slot,
        "expected": expected,
        "observed": observed,
        "alignment_status": alignment,
    }


def _derive_edge_alignment(
    edge: Mapping[str, Any],
    nodes: Mapping[str, Mapping[str, Any]],
) -> str:
    if edge["id"] in SEMANTIC_EDGE_IDS:
        from core import knowledge_basis

        record_states = {
            "current": "present",
            "missing": "absent",
            "invalid": "invalid",
        }
        try:
            alignment = knowledge_basis.contextual_alignment(
                edge["observed"],
                edge["expected"],
                source_record_state=record_states[
                    nodes[edge["source"]]["status"]["record_freshness"]
                ],
                target_record_state=record_states[
                    nodes[edge["target"]]["status"]["record_freshness"]
                ],
            )
        except knowledge_basis.KnowledgeBasisError as exc:
            _fail(f"basis graph semantic edge is invalid: {exc}")
        source_current = (
            nodes[edge["source"]]["status"]["record_freshness"] == "current"
        )
        if (
            alignment == "exact_match"
            and source_current
            and edge["observed"]["method_identity"]
            != nodes["p2-method"]["method_identity"]
        ):
            return "review_required"
        return alignment
    source_status = nodes[edge["source"]]["status"]["record_freshness"]
    target_status = nodes[edge["target"]]["status"]["record_freshness"]
    if source_status == "invalid" or target_status == "invalid":
        return "blocked"
    if target_status == "missing":
        return "not_available"
    if source_status == "missing":
        if (
            edge["id"] in {
                P1_P2_SYNTHESIS_EDGE_ID,
                P1_P2_COLLECTION_EDGE_ID,
            }
            and edge["expected"]["sha256"] is None
        ):
            return "not_available"
        return "blocked"
    expected = edge["expected"]
    observed = edge["observed"]
    if expected["sha256"] is None:
        if (
            edge["id"] in P1_UNKNOWN_BASIS_REVIEW_EDGES
            and observed["sha256"] is not None
        ):
            return "review_required"
        return "blocked"
    if observed["sha256"] is None:
        return "blocked"
    return "exact_match" if expected == observed else "review_required"


def aggregate_alignment_status(values: Sequence[str]) -> str:
    """Aggregate mechanical alignment without scientific inference."""

    normalized = list(values)
    if any(
        type(value) is not str or value not in ALIGNMENT_STATUS_VALUES
        for value in normalized
    ):
        _fail("alignment aggregation contains an unsupported status")
    for status in ("blocked", "review_required", "not_available"):
        if status in normalized:
            return status
    return "exact_match"


def _record_alignment(
    node: Mapping[str, Any],
    incoming: Sequence[str],
) -> str:
    freshness = node["status"]["record_freshness"]
    if freshness == "missing":
        return "not_available"
    if freshness == "invalid":
        return "blocked"
    return aggregate_alignment_status(incoming)


def summarize_nodes(nodes: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Derive graph-level mechanical status from normalized node statuses."""

    freshness_values = [
        str(node["status"]["record_freshness"]) for node in nodes
    ]
    if "invalid" in freshness_values:
        freshness = "invalid"
    else:
        current_count = freshness_values.count("current")
        if current_count == len(freshness_values):
            freshness = "complete"
        elif current_count:
            freshness = "partial"
        else:
            freshness = "empty"

    alignment_values = [
        str(node["status"]["alignment_status"]) for node in nodes
    ]
    if "blocked" in alignment_values:
        alignment = "blocked"
    elif "review_required" in alignment_values:
        alignment = "review_required"
    elif "not_available" in alignment_values:
        alignment = "not_available"
    else:
        alignment = "exact_match"
    return {
        "record_freshness": freshness,
        "alignment_status": alignment,
        "scientific_status": "not_assessed",
    }


def _normalize_summary(value: Any) -> dict[str, str]:
    summary = _mapping(value, label="basis graph summary")
    _exact_fields(summary, _SUMMARY_FIELDS, label="basis graph summary")
    if summary["record_freshness"] not in GRAPH_FRESHNESS_VALUES:
        _fail("basis graph summary has unsupported record_freshness")
    if summary["alignment_status"] not in ALIGNMENT_STATUS_VALUES:
        _fail("basis graph summary has unsupported alignment_status")
    if summary["scientific_status"] not in SCIENTIFIC_STATUS_VALUES:
        _fail("basis graph summary has unsupported scientific_status")
    return {
        "record_freshness": summary["record_freshness"],
        "alignment_status": summary["alignment_status"],
        "scientific_status": summary["scientific_status"],
    }


def _normalize_unsealed(value: Any) -> dict[str, Any]:
    graph = _mapping(value, label="basis graph")
    _exact_fields(graph, _UNSEALED_GRAPH_FIELDS, label="basis graph")
    schema_version = graph["schema_version"]
    if type(schema_version) is not int or schema_version not in {
        LEGACY_SCHEMA_VERSION,
        SEMANTIC_SCHEMA_VERSION,
        COLLECTION_SCHEMA_VERSION,
        SCHEMA_VERSION,
    }:
        _fail(
            "basis graph schema_version must be one of "
            f"{LEGACY_SCHEMA_VERSION}, {SEMANTIC_SCHEMA_VERSION}, "
            f"{COLLECTION_SCHEMA_VERSION}, or {SCHEMA_VERSION}"
        )
    if graph["kind"] != GRAPH_KIND:
        _fail(f"basis graph kind must be {GRAPH_KIND!r}")
    branch = normalize_method_identity(graph["branch"])
    expected_key = branch_key(branch["stable_id"])
    if graph["branch_key"] != expected_key:
        _fail("basis graph branch_key does not match its stable_id")

    raw_nodes = graph["nodes"]
    if not isinstance(raw_nodes, list):
        _fail("basis graph nodes must be a list")
    if not 1 <= len(raw_nodes) <= MAX_NODES:
        _fail(f"basis graph must contain 1 to {MAX_NODES} nodes")
    nodes = [
        _normalize_node(
            item,
            number=number,
            schema_version=schema_version,
        )
        for number, item in enumerate(raw_nodes, start=1)
    ]
    node_ids = [node["id"] for node in nodes]
    if tuple(node_ids) != NODE_IDS:
        _fail("basis graph nodes must contain the five phase nodes in order")
    node_map = {node["id"]: node for node in nodes}
    if node_map["p2-method"]["method_identity"] != branch:
        _fail("Phase 2 node identity must equal the graph branch identity")
    if node_map["p2-method"]["digests"]["primary_sha256"] != (
        branch["definition_sha256"]
    ):
        _fail("Phase 2 node digest must equal the branch definition digest")
    for node_id in ("p3-theory", "p4-empirical", "p5-manuscript"):
        method = node_map[node_id]["method_identity"]
        if method is not None and method["stable_id"] != branch["stable_id"]:
            _fail(f"{node_id} belongs to another stable method branch")

    raw_edges = graph["edges"]
    if not isinstance(raw_edges, list):
        _fail("basis graph edges must be a list")
    if len(raw_edges) > MAX_EDGES:
        _fail(f"basis graph exceeds the {MAX_EDGES}-edge limit")
    edges = [
        _normalize_edge(
            item,
            number=number,
            schema_version=schema_version,
        )
        for number, item in enumerate(raw_edges, start=1)
    ]
    edge_ids = [edge["id"] for edge in edges]
    if schema_version == LEGACY_SCHEMA_VERSION:
        expected_edge_ids = LEGACY_EDGE_IDS
    elif schema_version == SEMANTIC_SCHEMA_VERSION:
        expected_edge_ids = SCHEMA_TWO_EDGE_IDS
    elif schema_version == COLLECTION_SCHEMA_VERSION:
        expected_edge_ids = SCHEMA_THREE_EDGE_IDS
    else:
        expected_edge_ids = EDGE_IDS
    if tuple(edge_ids) != expected_edge_ids:
        _fail("basis graph edges must contain the fixed basis edges in order")
    for edge in edges:
        if edge["source"] not in node_map or edge["target"] not in node_map:
            _fail(f"basis graph edge {edge['id']!r} names an unknown node")
        if (
            schema_version >= SEMANTIC_SCHEMA_VERSION
            and edge["source"] == "p2-method"
            and edge["observed"]["method_identity"] != branch
        ):
            _fail(
                f"basis graph edge {edge['id']!r} does not observe "
                "the current Phase 2 identity"
            )
        derived = _derive_edge_alignment(edge, node_map)
        if edge["alignment_status"] != derived:
            _fail(
                f"basis graph edge {edge['id']!r} alignment is not mechanical"
            )

    edge_map = {edge["id"]: edge for edge in edges}
    if schema_version >= SCHEMA_VERSION:
        p2_alignment = _record_alignment(
            node_map["p2-method"],
            [
                edge_map[P1_P2_SYNTHESIS_EDGE_ID]["alignment_status"],
                edge_map[P1_P2_COLLECTION_EDGE_ID]["alignment_status"],
            ],
        )
    else:
        p2_alignment = _record_alignment(
            node_map["p2-method"],
            [],
        )
    if (
        node_map["p2-method"]["status"]["alignment_status"]
        != p2_alignment
    ):
        _fail(
            "Phase 2 node alignment must follow its reviewed Phase 1 basis"
        )

    p3_incoming = [
        edge_map["p2-method--p3-theory:method_definition"][
            "alignment_status"
        ]
    ]
    if schema_version >= SEMANTIC_SCHEMA_VERSION:
        p3_incoming.append(
            edge_map[
                "p4-empirical--p3-theory:counterpart_basis"
            ]["alignment_status"]
        )
    p3_alignment = _record_alignment(
        node_map["p3-theory"], p3_incoming
    )
    if node_map["p3-theory"]["status"]["alignment_status"] != p3_alignment:
        _fail("Phase 3 node alignment must follow its incoming basis edges")

    p4_incoming = [
        edge_map["p2-method--p4-empirical:method_definition"][
            "alignment_status"
        ]
    ]
    if schema_version >= SEMANTIC_SCHEMA_VERSION:
        p4_incoming.append(
            edge_map[
                "p3-theory--p4-empirical:counterpart_basis"
            ]["alignment_status"]
        )
    p4_facts = node_map["p4-empirical"]["facts"]
    p4_alignment = _record_alignment(
        node_map["p4-empirical"], p4_incoming
    )
    if p4_alignment == "exact_match" and (
        p4_facts["outdated_count"] or p4_facts["unresolved_count"]
    ):
        p4_alignment = "review_required"
    if node_map["p4-empirical"]["status"]["alignment_status"] != p4_alignment:
        _fail("Phase 4 node alignment does not match its record facts")

    p5_incoming = [
        edge["alignment_status"]
        for edge in edges
        if edge["target"] == "p5-manuscript"
    ]
    if schema_version >= SEMANTIC_SCHEMA_VERSION:
        p5_incoming.extend(
            node_map[node_id]["status"]["alignment_status"]
            for node_id in ("p3-theory", "p4-empirical")
            if node_map[node_id]["status"]["record_freshness"] == "current"
        )
    p5_freshness = node_map["p5-manuscript"]["status"]["record_freshness"]
    if p5_freshness == "missing":
        p5_alignment = "not_available"
    elif p5_freshness == "invalid":
        p5_alignment = "blocked"
    else:
        p5_alignment = aggregate_alignment_status(p5_incoming)
    if node_map["p5-manuscript"]["status"]["alignment_status"] != p5_alignment:
        _fail(
            "Phase 5 node alignment does not match its frozen basis "
            "and current Phase 3 and Phase 4 alignment"
        )

    summary = _normalize_summary(graph["summary"])
    if summary != summarize_nodes(nodes):
        _fail("basis graph summary does not match its node statuses")
    return {
        "schema_version": schema_version,
        "kind": GRAPH_KIND,
        "branch_key": expected_key,
        "branch": branch,
        "nodes": nodes,
        "edges": edges,
        "summary": summary,
    }


def _fingerprint(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def seal_graph(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an unsealed graph and add its deterministic fingerprint."""

    normalized = _normalize_unsealed(value)
    return {**normalized, "graph_sha256": _fingerprint(normalized)}


def validate_graph(value: Any) -> dict[str, Any]:
    """Validate and normalize a sealed basis graph."""

    graph = _mapping(value, label="basis graph")
    _exact_fields(graph, _GRAPH_FIELDS, label="basis graph")
    supplied_digest = _text(
        graph["graph_sha256"],
        label="basis graph graph_sha256",
        maximum=64,
        pattern=_SHA256_RE,
    )
    unsealed = {key: item for key, item in graph.items() if key != "graph_sha256"}
    normalized = _normalize_unsealed(unsealed)
    expected_digest = _fingerprint(normalized)
    if not hmac.compare_digest(supplied_digest, expected_digest):
        _fail("basis graph fingerprint does not match its content")
    return {**normalized, "graph_sha256": expected_digest}


def graph_bytes(value: Any) -> bytes:
    """Return deterministic, bounded JSON bytes for one sealed graph."""

    normalized = validate_graph(value)
    payload = (
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_GRAPH_BYTES:
        _fail(f"basis graph exceeds the {MAX_GRAPH_BYTES:,}-byte limit")
    return payload


def _unique_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _fail(f"basis graph contains duplicate field {key!r}")
        value[key] = item
    return value


def parse_graph_bytes(payload: bytes) -> dict[str, Any]:
    """Parse bounded UTF-8 JSON and validate one sealed graph."""

    if not payload or len(payload) > MAX_GRAPH_BYTES:
        _fail(
            f"basis graph must contain 1 to {MAX_GRAPH_BYTES:,} bytes"
        )
    try:
        source = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KnowledgeSchemaError("basis graph is not valid UTF-8") from exc
    try:
        value = json.loads(
            source,
            object_pairs_hook=_unique_object,
            parse_constant=lambda constant: _fail(
                f"basis graph contains invalid numeric value {constant!r}"
            ),
        )
    except json.JSONDecodeError as exc:
        raise KnowledgeSchemaError(
            f"basis graph is not valid JSON: {exc}"
        ) from exc
    return validate_graph(value)
