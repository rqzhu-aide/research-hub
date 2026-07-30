"""Authoritative branch-status views for the Research Hub Web UI.

This module rebuilds the compact dependency graph for each method branch.
Run history is inspected only to determine whether the user may opt into
archived Phase 3 summaries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from core import (
    knowledge_graph,
    knowledge_heads,
    launch_prompts,
    launch_manifest,
    phase_records,
    project_state,
)
from core.launch_common import LaunchError


THEORY_PHASE = "03-idea-evaluation"
PHASE_RECORD_KEYS = {
    "02-method-development": ("method", "Phase 2 literature basis"),
    "03-idea-evaluation": ("theory", "Phase 3 theory"),
    "04-draft-assembly": ("empirical", "Phase 4 empirical work"),
    "05-review-revision": ("manuscript", "Phase 5 manuscript"),
}
_RECORD_KEYS = ("method", "theory", "empirical", "manuscript")

_RECORD_NODES = {
    "method": "p2-method",
    "theory": "p3-theory",
    "empirical": "p4-empirical",
    "manuscript": "p5-manuscript",
}
_RECORD_LABELS = {
    "method": {
        "current": "Reviewed against current Phase 1 evidence",
        "update_needed": "New Phase 1 evidence to review",
        "not_run": "Phase 1 basis was not recorded",
        "invalid": "Method provenance cannot be verified",
    },
    "theory": {
        "current": "Theory is aligned",
        "update_needed": "Theory requires re-evaluation",
        "not_run": "Theory not run",
        "invalid": "Theory package cannot be verified",
    },
    "empirical": {
        "current": "Empirical evidence is aligned",
        "update_needed": "Empirical evidence requires re-evaluation",
        "not_run": "Empirical work not run",
        "invalid": "Empirical package cannot be verified",
    },
    "manuscript": {
        "current": "Manuscript is aligned",
        "update_needed": "Manuscript inputs need review",
        "not_run": "No manuscript draft",
        "invalid": "Manuscript cannot be verified",
    },
}
_NOT_RUN_REASONS = {
    "method": "No current Phase 2 method definition exists.",
    "theory": "No current Phase 3 theory package exists for this method.",
    "empirical": "No current Phase 4 empirical package exists for this method.",
    "manuscript": "No current Phase 5 manuscript exists for this method.",
}
_CURRENT_REASONS = {
    "method": (
        "This method was reviewed against the current Phase 1 reference "
        "collection and literature synthesis."
    ),
    "theory": "The theory package matches the current method.",
    "empirical": "The empirical package matches the current method.",
    "manuscript": (
        "The manuscript matches the current reference collection, literature "
        "synthesis, method definition, theory package, and empirical package."
    ),
}
_GENERIC_INVALID_REASONS = {
    "method": "The current Phase 2 method provenance cannot be verified.",
    "theory": "The current Phase 3 theory package cannot be verified.",
    "empirical": "The current Phase 4 empirical package cannot be verified.",
    "manuscript": "The current Phase 5 manuscript cannot be verified.",
}
_METHOD_EDGES = {
    "theory": "p2-method--p3-theory:method_definition",
    "empirical": "p2-method--p4-empirical:method_definition",
    "manuscript": "p2-method--p5-manuscript:p2_definition",
}
_METHOD_RECORD_NAMES = {
    "theory": "Phase 3 theory",
    "empirical": "Phase 4 empirical",
    "manuscript": "Phase 5 manuscript",
}
_COUNTERPART_EDGES = {
    "theory": (
        "p4-empirical--p3-theory:counterpart_basis",
        "Phase 3 theory",
        "Phase 4 empirical",
    ),
    "empirical": (
        "p3-theory--p4-empirical:counterpart_basis",
        "Phase 4 empirical",
        "Phase 3 theory",
    ),
}
_P1_P2_COLLECTION_EDGE_ID = "p1-literature--p2-method:p1_collection"
_P1_P2_SYNTHESIS_EDGE_ID = "p1-literature--p2-method:p1_synthesis"
_P1_COLLECTION_EDGE_ID = "p1-literature--p5-manuscript:p1_collection"
_P1_SYNTHESIS_EDGE_ID = "p1-literature--p5-manuscript:p1_synthesis"
_MANUSCRIPT_INPUT_EDGES = {
    _P1_COLLECTION_EDGE_ID: (
        "The Phase 1 reference collection has changed since the manuscript "
        "was generated.",
        "The Phase 1 reference collection used by the manuscript cannot be "
        "verified.",
        "Phase 1 reference collection",
    ),
    _P1_SYNTHESIS_EDGE_ID: (
        "The literature synthesis has changed since the manuscript was "
        "generated.",
        "The literature synthesis used by the manuscript cannot be verified.",
        "Phase 1 literature synthesis",
    ),
    "p3-theory--p5-manuscript:p3_record": (
        "The current Phase 3 theory differs from the theory used by the "
        "manuscript.",
        "The Phase 3 theory used by the manuscript cannot be verified.",
        "Phase 3 theory",
    ),
    "p4-empirical--p5-manuscript:p4_index": (
        "The current Phase 4 evidence index differs from the index used by "
        "the manuscript.",
        "The Phase 4 evidence index used by the manuscript cannot be "
        "verified.",
        "Phase 4 evidence index",
    ),
    "p4-empirical--p5-manuscript:p4_synthesis": (
        "The current Phase 4 synthesis differs from the synthesis used by "
        "the manuscript.",
        "The Phase 4 synthesis used by the manuscript cannot be verified.",
        "Phase 4 synthesis",
    ),
}


def _methods_with_theory_history(project_dir: Path) -> set[str]:
    """Return method IDs with an intact, usable archived Phase 3 summary."""

    method_ids: set[str] = set()
    try:
        runs = project_state.get_runs(project_dir, THEORY_PHASE)
    except (KeyError, OSError, project_state.ProjectStateError):
        return method_ids
    for run in runs:
        if not isinstance(run, Mapping):
            continue
        run_id = str(run.get("run_id", "")).strip()
        if not run_id:
            continue
        try:
            manifest = launch_manifest._read_manifest(
                project_dir, THEORY_PHASE, run_id
            )
        except (
            KeyError,
            OSError,
            ValueError,
            LaunchError,
            project_state.ProjectStateError,
        ):
            continue
        selection = manifest.get("method_selection")
        if isinstance(selection, Mapping):
            stable_id = str(selection.get("stable_id", "")).strip()
            if stable_id:
                method_ids.add(stable_id)
    return {
        stable_id
        for stable_id in method_ids
        if launch_prompts._has_archived_method_summary(
            project_dir, THEORY_PHASE, stable_id
        )
    }


def _empty_status(record_key: str) -> dict[str, Any]:
    return {
        "state": "not_run",
        "label": _RECORD_LABELS[record_key]["not_run"],
        "reason": _NOT_RUN_REASONS[record_key],
        "generation": None,
        "source_run_id": "",
    }


def _invalid_status(record_key: str, reason: str) -> dict[str, Any]:
    return {
        **_empty_status(record_key),
        "state": "invalid",
        "label": _RECORD_LABELS[record_key]["invalid"],
        "reason": reason,
    }


def _bounded_text(value: Any) -> str:
    text = " ".join(str(value).split())
    return text[:600]


def _deduplicated(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _bounded_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _edge_alignment(edge: Any) -> str:
    if not isinstance(edge, Mapping):
        return "blocked"
    return str(edge.get("alignment_status", "blocked"))


def _unknown_legacy(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("state") == "unknown_legacy"


def _projected_state(node: Mapping[str, Any]) -> str:
    status = node.get("status")
    if not isinstance(status, Mapping):
        return "invalid"
    freshness = str(status.get("record_freshness", "invalid"))
    alignment = str(status.get("alignment_status", "blocked"))
    if freshness == "invalid" or alignment == "blocked":
        return "invalid"
    if freshness == "missing":
        return "not_run"
    if freshness == "current":
        if alignment in {"review_required", "not_available"}:
            return "update_needed"
        if alignment == "exact_match":
            return "current"
    return "invalid"


def _method_edge_reason(record_key: str, edge: Any) -> str:
    alignment = _edge_alignment(edge)
    record_name = _METHOD_RECORD_NAMES[record_key]
    if alignment == "review_required":
        return (
            f"The {record_name} record was produced for an earlier "
            "Phase 2 method definition."
        )
    if alignment == "blocked":
        return (
            f"The Phase 2 method definition used by {record_name} cannot be "
            "verified."
        )
    if alignment == "not_available":
        return f"No {record_name} record is available for method comparison."
    return ""


def _phase_two_literature_reason(
    state: str,
    node: Mapping[str, Any],
    edges: Mapping[str, Mapping[str, Any]],
) -> str:
    if state == "current":
        return _CURRENT_REASONS["method"]
    collection = edges.get(_P1_P2_COLLECTION_EDGE_ID)
    synthesis = edges.get(_P1_P2_SYNTHESIS_EDGE_ID)
    collection_status = _edge_alignment(collection)
    synthesis_status = _edge_alignment(synthesis)
    statuses = {collection_status, synthesis_status}
    if "blocked" in statuses:
        return (
            "The recorded Phase 2 literature basis or the current Phase 1 "
            "record cannot be verified."
        )
    if statuses == {"not_available"}:
        if str(node.get("source_run_id") or ""):
            return (
                "No Phase 1 record was available when this method was last "
                "reviewed in Phase 2."
            )
        return (
            "This method was published before Research Hub recorded the "
            "Phase 1 basis reviewed in Phase 2."
        )

    changed: list[str] = []
    if collection_status == "review_required":
        changed.append("reference collection")
    if synthesis_status == "review_required":
        changed.append("literature synthesis")
    if len(changed) == 2:
        collection_expected = (
            collection.get("expected")
            if isinstance(collection, Mapping)
            else None
        )
        synthesis_expected = (
            synthesis.get("expected")
            if isinstance(synthesis, Mapping)
            else None
        )
        legacy = bool(
            not str(node.get("source_run_id") or "")
            and isinstance(collection_expected, Mapping)
            and collection_expected.get("sha256") is None
            and isinstance(synthesis_expected, Mapping)
            and synthesis_expected.get("sha256") is None
        )
        if legacy:
            return (
                "This method was published before Research Hub recorded the "
                "Phase 1 basis reviewed in Phase 2."
            )
        return (
            "The Phase 1 reference collection and literature synthesis "
            "changed after this method was last reviewed in Phase 2."
        )
    if changed:
        return (
            f"The Phase 1 {changed[0]} changed after this method was last "
            "reviewed in Phase 2."
        )
    return "The Phase 1 basis reviewed for this method needs inspection."


def _counterpart_edge_reason(record_key: str, edge: Any) -> str:
    edge_id, record_name, counterpart_name = _COUNTERPART_EDGES[record_key]
    del edge_id
    alignment = _edge_alignment(edge)
    if alignment == "exact_match":
        return ""
    expected = edge.get("expected") if isinstance(edge, Mapping) else None
    observed = edge.get("observed") if isinstance(edge, Mapping) else None
    if _unknown_legacy(expected):
        return (
            f"The {record_name} record was created before Research Hub recorded "
            f"which {counterpart_name} conclusions and evidence it used."
        )
    if _unknown_legacy(observed):
        return (
            f"The current {counterpart_name} record does not contain enough "
            "information for an exact comparison."
        )
    if alignment == "review_required":
        if record_key == "theory":
            return (
                "Decision-relevant Phase 4 conclusions or evidence changed "
                "since this Phase 3 theory package was produced."
            )
        return (
            "Decision-relevant Phase 3 claims changed since this Phase 4 "
            "empirical package was produced."
        )
    if alignment == "blocked":
        return (
            f"The {counterpart_name} information used by {record_name} cannot be "
            "verified."
        )
    return f"The {counterpart_name} information needed by {record_name} is absent."


def _current_reason(
    record_key: str,
    nodes: Mapping[str, Mapping[str, Any]],
) -> str:
    """Describe exact alignment without implying that an absent sibling ran."""

    if record_key == "theory":
        counterpart = nodes.get(_RECORD_NODES["empirical"])
        if (
            not isinstance(counterpart, Mapping)
            or _projected_state(counterpart) == "not_run"
        ):
            return (
                "The theory package matches the current method. No Phase 4 "
                "empirical package existed for this theory run, and none exists "
                "now."
            )
        return (
            "The theory package matches the current method and the current "
            "decision-relevant Phase 4 conclusions and evidence."
        )
    if record_key == "empirical":
        counterpart = nodes.get(_RECORD_NODES["theory"])
        if (
            not isinstance(counterpart, Mapping)
            or _projected_state(counterpart) == "not_run"
        ):
            return (
                "The empirical package matches the current method. No Phase 3 "
                "theory package existed for this empirical run, and none exists "
                "now."
            )
        return (
            "The empirical package matches the current method and the current "
            "decision-relevant Phase 3 theoretical claims."
        )
    return _CURRENT_REASONS[record_key]

def _manuscript_edge_reason(edge_id: str, edge: Any) -> str:
    review_reason, blocked_reason, input_name = _MANUSCRIPT_INPUT_EDGES[edge_id]
    alignment = _edge_alignment(edge)
    if alignment == "review_required":
        expected = edge.get("expected") if isinstance(edge, Mapping) else None
        if (
            edge_id == _P1_COLLECTION_EDGE_ID
            and (
                not isinstance(expected, Mapping)
                or expected.get("sha256") is None
            )
        ):
            return (
                "This manuscript was created before Research Hub recorded its "
                "exact Phase 1 reference collection."
            )
        return review_reason
    if alignment == "blocked":
        return blocked_reason
    if alignment == "not_available":
        return f"{input_name} is not available for the manuscript."
    return ""


def _count(value: Any) -> int:
    return value if type(value) is int and value >= 0 else 0


def _p4_counts(node: Mapping[str, Any]) -> tuple[int | None, int, int]:
    facts = node.get("facts")
    if not isinstance(facts, Mapping):
        return None, 0, 0
    item_count = facts.get("item_count")
    current = item_count if type(item_count) is int and item_count >= 0 else None
    outdated = _count(facts.get("outdated_count"))
    unresolved = _count(facts.get("unresolved_count"))
    return current, outdated, unresolved


def _reference_method_identity(edge: Any, side: str) -> dict[str, str] | None:
    if not isinstance(edge, Mapping):
        return None
    reference = edge.get(side)
    if not isinstance(reference, Mapping):
        return None
    identity = reference.get("method_identity")
    if not isinstance(identity, Mapping):
        return None
    stable_id = str(identity.get("stable_id", "")).strip()
    version = str(identity.get("version", "")).strip()
    digest = str(identity.get("definition_sha256", "")).strip().lower()
    if (
        not stable_id
        or not version
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        return None
    return {
        "stable_id": stable_id,
        "version": version,
        "definition_sha256": digest,
    }


def _method_applicability(
    node: Mapping[str, Any],
    edge: Any,
    current_method: Mapping[str, Any],
) -> dict[str, Any]:
    node_state = _projected_state(node)
    current_version = str(current_method.get("version", "")).strip()
    if node_state == "not_run":
        return {
            "state": "not_run",
            "display_state": "not_run",
            "current_version": current_version,
            "record_version": "",
            "rerun_required": False,
            "label": f"Phase 4 has not run for method {current_version}".strip(),
            "reason": "No Phase 4 record exists for this method version.",
        }

    alignment = _edge_alignment(edge)
    record_identity = _reference_method_identity(edge, "expected")
    current_identity = {
        "stable_id": str(current_method.get("stable_id", "")).strip(),
        "version": current_version,
        "definition_sha256": str(
            current_method.get("definition_sha256", "")
        ).strip().lower(),
    }
    record_version = (
        record_identity["version"] if record_identity is not None else ""
    )
    if alignment == "exact_match" and record_identity == current_identity:
        return {
            "state": "valid_current_version",
            "display_state": "current",
            "current_version": current_version,
            "record_version": record_version or current_version,
            "rerun_required": False,
            "label": f"Valid for method {current_version}".strip(),
            "reason": (
                "This Phase 4 record was produced for the current method "
                "version."
            ),
        }
    if alignment == "review_required":
        if record_version and record_version != current_version:
            label = (
                f"Previous method version {record_version}; rerun Phase 4 for "
                f"{current_version}"
            )
            reason = (
                f"This Phase 4 record was produced for method {record_version}, "
                f"not the current method {current_version}. Rerun Phase 4 for "
                f"{current_version} before using this record as current evidence."
            )
        else:
            label = f"Method definition mismatch; rerun Phase 4 for {current_version}".strip()
            reason = (
                "The Phase 4 method definition does not match the current "
                "catalog definition. Rerun Phase 4 before using this record."
            )
        return {
            "state": "previous_version",
            "display_state": "update_needed",
            "current_version": current_version,
            "record_version": record_version,
            "rerun_required": True,
            "label": label,
            "reason": reason,
        }
    return {
        "state": "unverifiable",
        "display_state": "invalid",
        "current_version": current_version,
        "record_version": record_version,
        "rerun_required": True,
        "label": "Method version cannot be verified",
        "reason": (
            "The method version recorded by Phase 4 cannot be compared with "
            "the current catalog method."
        ),
    }


def _sibling_basis_status(
    node: Mapping[str, Any],
    edge: Any,
    nodes: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    if _projected_state(node) == "not_run":
        return {
            "state": "not_available",
            "display_state": "not_run",
            "label": "No Phase 4 record",
            "reason": "Phase 4 has not run for this method.",
        }
    alignment = _edge_alignment(edge)
    theory = nodes.get(_RECORD_NODES["theory"])
    theory_missing = (
        not isinstance(theory, Mapping)
        or _projected_state(theory) == "not_run"
    )
    if alignment == "exact_match":
        if theory_missing:
            return {
                "state": "not_available",
                "display_state": "current",
                "label": "No Phase 3 result was used, and none exists now",
                "reason": "Phase 4 was run without a Phase 3 result.",
            }
        return {
            "state": "current",
            "display_state": "current",
            "label": "Uses the current Phase 3 result",
            "reason": "The recorded Phase 3 basis matches the current result.",
        }
    if alignment == "review_required":
        return {
            "state": "changed",
            "display_state": "update_needed",
            "label": "Phase 3 basis changed; update the Phase 4 interpretation",
            "reason": (
                "Decision-relevant Phase 3 claims changed after this Phase 4 "
                "record was produced."
            ),
        }
    if alignment == "not_available" and theory_missing:
        return {
            "state": "not_available",
            "display_state": "not_run",
            "label": "No Phase 3 result was used, and none exists now",
            "reason": "There is no Phase 3 result to compare.",
        }
    return {
        "state": "unverifiable",
        "display_state": "invalid",
        "label": "Phase 3 basis cannot be verified",
        "reason": "The Phase 3 basis recorded by Phase 4 cannot be verified.",
    }


def _research_attention(
    node: Mapping[str, Any],
    record_state: str,
) -> dict[str, Any]:
    indexed, outdated, unresolved = _p4_counts(node)
    if record_state == "not_run":
        return {
            "state": "not_run",
            "display_state": "not_run",
            "indexed_count": indexed,
            "outdated_count": outdated,
            "unresolved_count": unresolved,
            "label": "No Phase 4 evidence has been indexed",
            "reasons": [],
        }
    if record_state == "invalid":
        return {
            "state": "unverifiable",
            "display_state": "invalid",
            "indexed_count": indexed,
            "outdated_count": outdated,
            "unresolved_count": unresolved,
            "label": "Evidence applicability cannot be verified",
            "reasons": ["The Phase 4 evidence index cannot be verified."],
        }
    reasons: list[str] = []
    if outdated:
        noun = "result" if outdated == 1 else "results"
        reasons.append(f"{outdated} outdated {noun} require revalidation")
    if unresolved:
        noun = "entry has" if unresolved == 1 else "entries have"
        reasons.append(
            f"{unresolved} {noun} unresolved applicability or interpretation"
        )
    return {
        "state": "required" if reasons else "none",
        "display_state": "update_needed" if reasons else "current",
        "indexed_count": indexed,
        "outdated_count": outdated,
        "unresolved_count": unresolved,
        "label": "; ".join(reasons)
        if reasons
        else "No indexed evidence requires revalidation",
        "reasons": reasons,
    }


def _compact_reason(values: Sequence[str]) -> str:
    selected = _deduplicated(values)[:3]
    text = " ".join(selected)
    if len(text) <= 900:
        return text
    return text[:897].rstrip() + "..."


def _record_reason_parts(
    record_key: str,
    state: str,
    node: Mapping[str, Any],
    nodes: Mapping[str, Mapping[str, Any]],
    edges: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    if record_key == "method":
        return [
            _phase_two_literature_reason(
                state, node, edges
            )
        ]
    if state == "not_run":
        return [_NOT_RUN_REASONS[record_key]]

    reasons: list[str] = []
    if state == "invalid":
        diagnostics = node.get("diagnostics")
        if isinstance(diagnostics, list):
            reasons.extend(
                str(item) for item in diagnostics if isinstance(item, str)
            )

    method_reason = _method_edge_reason(
        record_key, edges.get(_METHOD_EDGES[record_key])
    )
    if method_reason:
        reasons.append(method_reason)

    if record_key in _COUNTERPART_EDGES:
        counterpart_reason = _counterpart_edge_reason(
            record_key,
            edges.get(_COUNTERPART_EDGES[record_key][0]),
        )
        if counterpart_reason:
            reasons.append(counterpart_reason)

    if record_key == "empirical":
        _, outdated, unresolved = _p4_counts(node)
        if outdated or unresolved:
            reasons.append(
                "The evidence index contains "
                f"{outdated} outdated and {unresolved} unresolved entries."
            )

    if record_key == "manuscript":
        skipped_edges: set[str] = set()
        collection_edge = edges.get(_P1_COLLECTION_EDGE_ID)
        synthesis_edge = edges.get(_P1_SYNTHESIS_EDGE_ID)
        collection_expected = (
            collection_edge.get("expected")
            if isinstance(collection_edge, Mapping)
            else None
        )
        if (
            _edge_alignment(collection_edge) == "review_required"
            and _edge_alignment(synthesis_edge) == "review_required"
            and isinstance(collection_expected, Mapping)
            and collection_expected.get("sha256") is not None
        ):
            reasons.append(
                "The Phase 1 reference collection and literature synthesis "
                "have changed since the manuscript was generated."
            )
            skipped_edges.update({_P1_COLLECTION_EDGE_ID, _P1_SYNTHESIS_EDGE_ID})
        for edge_id in _MANUSCRIPT_INPUT_EDGES:
            if edge_id in skipped_edges:
                continue
            reason = _manuscript_edge_reason(edge_id, edges.get(edge_id))
            if reason:
                reasons.append(reason)
        for upstream_key in ("theory", "empirical"):
            upstream = nodes.get(_RECORD_NODES[upstream_key], {})
            upstream_state = (
                _projected_state(upstream)
                if isinstance(upstream, Mapping)
                else "invalid"
            )
            if upstream_state != "current":
                reasons.extend(
                    _record_reason_parts(
                        upstream_key,
                        upstream_state,
                        upstream if isinstance(upstream, Mapping) else {},
                        nodes,
                        edges,
                    )
                )

    reasons = _deduplicated(reasons)
    if reasons:
        return reasons
    if state == "current":
        return [_current_reason(record_key, nodes)]
    if state == "update_needed":
        return [
            f"The current {_METHOD_RECORD_NAMES[record_key]} inputs have "
            "changed."
        ]
    return [_GENERIC_INVALID_REASONS[record_key]]


def _changed_manuscript_inputs(
    nodes: Mapping[str, Mapping[str, Any]],
    edges: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    labels: list[str] = []
    method_edge = edges.get(_METHOD_EDGES["manuscript"])
    if _edge_alignment(method_edge) != "exact_match":
        labels.append("Phase 2 method")
    for edge_id, (_, _, label) in _MANUSCRIPT_INPUT_EDGES.items():
        if _edge_alignment(edges.get(edge_id)) != "exact_match":
            labels.append(label)
    for record_key, label in (
        ("theory", "Phase 3 theory alignment"),
        ("empirical", "Phase 4 empirical alignment"),
    ):
        node = nodes.get(_RECORD_NODES[record_key])
        if isinstance(node, Mapping) and _projected_state(node) != "current":
            labels.append(label)
    return _deduplicated(labels)


def _phase_two_literature_label(
    state: str,
    node: Mapping[str, Any],
    edges: Mapping[str, Mapping[str, Any]],
) -> str:
    """Distinguish changed evidence from unavailable or legacy provenance."""

    default = _RECORD_LABELS["method"][state]
    if state != "update_needed":
        return default
    collection = edges.get(_P1_P2_COLLECTION_EDGE_ID)
    synthesis = edges.get(_P1_P2_SYNTHESIS_EDGE_ID)
    statuses = {
        _edge_alignment(collection),
        _edge_alignment(synthesis),
    }
    if statuses == {"not_available"}:
        return "Phase 1 evidence unavailable"
    expected = [
        edge.get("expected")
        for edge in (collection, synthesis)
        if isinstance(edge, Mapping)
    ]
    if (
        not str(node.get("source_run_id") or "")
        and len(expected) == 2
        and all(
            isinstance(reference, Mapping)
            and reference.get("sha256") is None
            for reference in expected
        )
    ):
        return "Phase 1 basis needs review"
    return default


def _record_status_from_graph(
    record_key: str,
    nodes: Mapping[str, Mapping[str, Any]],
    edges: Mapping[str, Mapping[str, Any]],
    current_method: Mapping[str, Any],
) -> dict[str, Any]:
    node = nodes.get(_RECORD_NODES[record_key])
    if not isinstance(node, Mapping):
        return _invalid_status(
            record_key,
            f"The dependency graph omits {_RECORD_NODES[record_key]}.",
        )
    state = _projected_state(node)
    reasons = _record_reason_parts(record_key, state, node, nodes, edges)
    result = {
        "state": state,
        "label": (
            _phase_two_literature_label(state, node, edges)
            if record_key == "method"
            else _RECORD_LABELS[record_key][state]
        ),
        "reason": _compact_reason(reasons),
        "generation": (
            node.get("generation")
            if type(node.get("generation")) is int
            else None
        ),
        "source_run_id": str(node.get("source_run_id") or ""),
    }
    if record_key == "empirical":
        indexed, outdated, unresolved = _p4_counts(node)
        current_evidence = (
            indexed - outdated - unresolved
            if indexed is not None
            else None
        )
        result.update({
            "indexed_evidence_count": indexed,
            "current_evidence_count": current_evidence,
            "outdated_evidence_count": outdated,
            "unresolved_evidence_count": unresolved,
            "method_applicability": _method_applicability(
                node,
                edges.get(_METHOD_EDGES["empirical"]),
                current_method,
            ),
            "sibling_basis": _sibling_basis_status(
                node,
                edges.get(_COUNTERPART_EDGES["empirical"][0]),
                nodes,
            ),
            "research_attention": _research_attention(node, state),
        })
    elif record_key == "manuscript":
        result["changed_input_labels"] = _changed_manuscript_inputs(
            nodes, edges
        )
    return result


def _graph_record_statuses(
    graph: Mapping[str, Any],
    *,
    current_method: Mapping[str, Any],
) -> dict[str, Any]:
    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])
    nodes = {
        str(node.get("id", "")): node
        for node in raw_nodes
        if isinstance(node, Mapping)
    }
    edges = {
        str(edge.get("id", "")): edge
        for edge in raw_edges
        if isinstance(edge, Mapping)
    }
    return {
        record_key: _record_status_from_graph(
            record_key,
            nodes,
            edges,
            current_method,
        )
        for record_key in _RECORD_KEYS
    }


def _one_method_status(
    project_dir: Path,
    entry: Mapping[str, Any],
    *,
    theory_history_ids: set[str],
) -> dict[str, Any]:
    stable_id = str(entry.get("stable_id", "")).strip()
    result = {
        "has_theory_history": stable_id in theory_history_ids,
        "knowledge_heads_version": None,
        "phase_two_review_version": None,
        "branch_graph_version": None,
        "launch_context_error": "",
        "record_status": {
            record_key: _empty_status(record_key)
            for record_key in _RECORD_KEYS
        },
    }
    try:
        current_method = phase_records.method_identity(entry)
    except (ValueError, TypeError):
        reason = "The Phase 2 method identity cannot be verified."
        result["launch_context_error"] = (
            "The current method and branch records cannot be verified for a "
            "new run."
        )
        result["record_status"] = {
            record_key: _invalid_status(record_key, reason)
            for record_key in _RECORD_KEYS
        }
        return result

    try:
        graph = knowledge_graph.build_branch_basis_graph(
            project_dir, stable_id
        )
    except (OSError, ValueError) as exc:
        detail = _bounded_text(exc)
        for candidate in (str(project_dir), project_dir.as_posix()):
            detail = detail.replace(candidate, "<project>")
        reason = (
            "The current branch records cannot be verified: "
            f"{detail}"
        )
        result["record_status"] = {
            record_key: _invalid_status(record_key, reason)
            for record_key in _RECORD_KEYS
        }
        result["launch_context_error"] = (
            "The current method and branch records cannot be verified for a "
            "new run."
        )
    else:
        result["record_status"] = _graph_record_statuses(
            graph,
            current_method=current_method,
        )
        provenance = entry.get("provenance")
        method_status = result["record_status"]["method"]
        if isinstance(provenance, Mapping):
            method_status.update({
                "definition_source_run_id": str(
                    provenance.get("definition_source_run_id") or ""
                ),
                "review_source_run_id": str(
                    provenance.get("review_source_run_id") or ""
                ),
                "review_scope": str(provenance.get("review_scope") or ""),
                "review_scientific_outcome": str(
                    provenance.get("review_scientific_outcome") or ""
                ),
                "disposition": str(provenance.get("disposition") or ""),
            })
        try:
            result["phase_two_review_version"] = (
                knowledge_graph.phase_two_review_projection_version(graph)
            )
        except (TypeError, ValueError):
            result["launch_context_error"] = (
                "The selected method's Phase 2 literature-review status "
                "cannot be verified for a new run."
            )
        graph_version = str(graph.get("graph_sha256", "")).strip().lower()
        if len(graph_version) == 64 and all(
            character in "0123456789abcdef"
            for character in graph_version
        ):
            result["branch_graph_version"] = graph_version
        else:
            result["launch_context_error"] = (
                "The current branch records cannot be verified for a new run."
            )

    try:
        heads = knowledge_heads.derive_live_heads(project_dir, stable_id)
        result["knowledge_heads_version"] = knowledge_heads.heads_version(
            heads
        )
    except (OSError, ValueError):
        result["knowledge_heads_version"] = None
        result["launch_context_error"] = (
            "The current Phase 3 and Phase 4 records cannot be verified for a "
            "new run."
        )
    return result


def method_record_statuses(
    project_dir: str | Path,
    entries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return current-record status for each catalog entry in input order."""

    root = Path(project_dir).resolve()
    theory_history_ids = _methods_with_theory_history(root)
    return [
        _one_method_status(
            root,
            entry,
            theory_history_ids=theory_history_ids,
        )
        for entry in entries
    ]


def _aggregate_empirical_signals(
    active: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    applicability_counts = {
        "valid_current_version": 0,
        "previous_version": 0,
        "unverifiable": 0,
        "not_run": 0,
    }
    sibling_counts = {
        "current": 0,
        "changed": 0,
        "unverifiable": 0,
        "not_available": 0,
    }
    attention_method_ids: list[str] = []
    unverifiable_method_ids: list[str] = []
    outdated_count = 0
    unresolved_count = 0

    for method in active:
        stable_id = str(method.get("stable_id", "")).strip()
        method_id = stable_id or "unknown method"
        records = method.get("record_status")
        record = (
            records.get("empirical")
            if isinstance(records, Mapping)
            else None
        )
        record = record if isinstance(record, Mapping) else {}
        record_state = str(record.get("state", "not_run"))

        applicability = record.get("method_applicability")
        applicability_state = (
            str(applicability.get("state", ""))
            if isinstance(applicability, Mapping)
            else ""
        )
        if applicability_state not in applicability_counts:
            applicability_state = (
                "not_run" if record_state == "not_run" else "unverifiable"
            )
        applicability_counts[applicability_state] += 1

        sibling = record.get("sibling_basis")
        sibling_state = (
            str(sibling.get("state", ""))
            if isinstance(sibling, Mapping)
            else ""
        )
        if sibling_state not in sibling_counts:
            sibling_state = (
                "not_available"
                if record_state == "not_run"
                else "unverifiable"
            )
        sibling_counts[sibling_state] += 1

        attention = record.get("research_attention")
        if isinstance(attention, Mapping):
            attention_state = str(attention.get("state", ""))
            outdated_count += _count(attention.get("outdated_count"))
            unresolved_count += _count(attention.get("unresolved_count"))
        else:
            outdated_count += _count(record.get("outdated_evidence_count"))
            unresolved_count += _count(record.get("unresolved_evidence_count"))
            attention_state = (
                "not_run" if record_state == "not_run" else "unverifiable"
            )
        if attention_state == "required":
            attention_method_ids.append(method_id)
        elif attention_state == "unverifiable":
            unverifiable_method_ids.append(method_id)

    if unverifiable_method_ids:
        attention_state = "unverifiable"
        attention_label = (
            "Evidence applicability cannot be verified for "
            f"{len(unverifiable_method_ids)} active methods"
        )
        attention_reason = (
            "Check the Phase 4 evidence records for: "
            f"{', '.join(unverifiable_method_ids)}."
        )
    elif attention_method_ids:
        attention_state = "required"
        attention_label = (
            "Phase 4 evidence requires revalidation for "
            f"{len(attention_method_ids)} active methods"
        )
        attention_reason = (
            "Review outdated or unresolved evidence for: "
            f"{', '.join(attention_method_ids)}."
        )
    elif active:
        attention_state = "none"
        attention_label = "No indexed Phase 4 evidence requires revalidation"
        attention_reason = ""
    else:
        attention_state = "none"
        attention_label = "No active methods are available"
        attention_reason = ""

    return {
        "method_applicability_counts": applicability_counts,
        "sibling_basis_counts": sibling_counts,
        "research_attention": {
            "state": attention_state,
            "label": attention_label,
            "reason": attention_reason,
            "affected_method_ids": _deduplicated(
                [*unverifiable_method_ids, *attention_method_ids]
            ),
            "outdated_evidence_count": outdated_count,
            "unresolved_evidence_count": unresolved_count,
        },
    }


def aggregate_phase_record_status(
    phase_slug: str,
    methods: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Summarize branch freshness without using one phase-global pointer."""

    definition = PHASE_RECORD_KEYS.get(str(phase_slug))
    if definition is None:
        return None
    record_key, label = definition
    active = [
        method
        for method in methods
        if str(method.get("status", "")) != "retired"
        and not method.get("errors")
    ]
    aggregate_extras = (
        _aggregate_empirical_signals(active)
        if record_key == "empirical"
        else {}
    )
    affected: list[str] = []
    affected_labels: list[str] = []
    invalid: list[str] = []
    invalid_labels: list[str] = []
    attention_ids: list[str] = []
    current_count = 0
    not_run_count = 0
    for method in active:
        stable_id = str(method.get("stable_id", "")).strip()
        method_id = stable_id or "unknown method"
        method_label = str(
            method.get("label") or method.get("name") or method_id
        )
        records = method.get("record_status")
        record = records.get(record_key) if isinstance(records, Mapping) else None
        record_state = (
            str(record.get("state", "not_run"))
            if isinstance(record, Mapping)
            else "not_run"
        )
        if record_state == "current":
            current_count += 1
        elif record_state == "not_run":
            not_run_count += 1
        elif record_state == "invalid":
            invalid.append(method_id)
            invalid_labels.append(method_label)
            attention_ids.append(method_id)
        else:
            affected.append(method_id)
            affected_labels.append(method_label)
            attention_ids.append(method_id)

    active_count = len(active)
    if invalid:
        count = len(invalid)
        noun = "method" if active_count == 1 else "methods"
        reason = f"Check record integrity for: {', '.join(invalid_labels)}."
        if affected:
            review_subject = (
                "Phase 4 status"
                if record_key == "empirical"
                else f"{label} alignment"
            )
            reason += (
                f" Review {review_subject.lower()} for: "
                f"{', '.join(affected_labels)}, then decide whether a rerun is "
                "needed."
            )
        return {
            "state": "invalid",
            "label": (
                f"{label} cannot be verified for {count} of {active_count} "
                f"active {noun}"
            ),
            "reason": reason,
            "affected_method_ids": attention_ids,
            "active_count": active_count,
            "current_count": current_count,
            "not_run_count": not_run_count,
            "invalid_count": len(invalid),
            **aggregate_extras,
        }
    if affected:
        count = len(affected)
        noun = "method" if active_count == 1 else "methods"
        if record_key == "empirical":
            aggregate_label = (
                f"Phase 4 records need attention for {count} of {active_count} "
                f"active {noun}"
            )
            aggregate_reason = (
                "Review method applicability, Phase 3 basis, and indexed "
                f"evidence for: {', '.join(affected_labels)}, then decide "
                "whether a rerun is needed."
            )
        else:
            aggregate_label = (
                f"{label} alignment needs review for {count} of {active_count} "
                f"active {noun}"
            )
            aggregate_reason = (
                f"Review {label.lower()} alignment for: "
                f"{', '.join(affected_labels)}, then decide whether a rerun is "
                "needed."
            )
        return {
            "state": "stale",
            "label": aggregate_label,
            "reason": aggregate_reason,
            "affected_method_ids": attention_ids,
            "active_count": active_count,
            "current_count": current_count,
            "not_run_count": not_run_count,
            "invalid_count": 0,
            **aggregate_extras,
        }
    if current_count and current_count == active_count:
        noun = "method" if active_count == 1 else "methods"
        label_text = f"{label} is current for all {active_count} active {noun}"
        aggregate_state = "current"
    elif current_count:
        noun = "method" if active_count == 1 else "methods"
        label_text = (
            f"{label} is current for {current_count} of {active_count} active {noun}"
        )
        aggregate_state = "partial"
    elif active_count:
        label_text = f"{label} has not run for any active method"
        aggregate_state = "not_run"
    else:
        label_text = "No active methods are available"
        aggregate_state = "not_run"
    return {
        "state": aggregate_state,
        "label": label_text,
        "reason": "",
        "affected_method_ids": [],
        "active_count": active_count,
        "current_count": current_count,
        "not_run_count": not_run_count,
        "invalid_count": 0,
        **aggregate_extras,
    }
