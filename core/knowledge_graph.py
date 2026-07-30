"""Rebuildable per-branch graph of exact canonical record dependencies.

The graph is a shadow materialization. It never replaces Phase 1 through Phase
5 records and is not a prerequisite for reading them. The optional cache lives
under the protected Research Hub control directory, outside the agent-writable
project tree.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core import (
    empirical_records,
    knowledge_basis,
    knowledge_content,
    knowledge_fragments,
    knowledge_schema,
    literature_records,
    manuscript_records,
    method_menu,
    phase_records,
    project_state,
    theory_records,
)
from core.filesystem_utils import metadata_is_link_or_reparse


SHADOW_FILENAME = "basis-graph.json"
MAX_RECORD_FILE_BYTES = 4 * 1024 * 1024


class KnowledgeGraphBuildError(ValueError):
    """A current branch could not be resolved for graph construction."""


def _empty_digests() -> dict[str, None]:
    return {
        "record_sha256": None,
        "primary_sha256": None,
        "collection_sha256": None,
    }


def _facts(
    *,
    item_count: int | None = None,
    outdated_count: int = 0,
    unresolved_count: int = 0,
) -> dict[str, int | None]:
    return {
        "item_count": item_count,
        "outdated_count": outdated_count,
        "unresolved_count": unresolved_count,
    }


def _status(
    freshness: str,
    alignment: str,
) -> dict[str, str]:
    return {
        "record_freshness": freshness,
        "alignment_status": alignment,
        "scientific_status": "not_assessed",
    }


def _base_node(
    node_id: str,
    *,
    freshness: str,
    alignment: str,
    generation: int | None = None,
    source_run_id: str | None = None,
    method_identity: Mapping[str, Any] | None = None,
    digests: Mapping[str, Any] | None = None,
    facts: Mapping[str, Any] | None = None,
    diagnostics: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "phase_slug": knowledge_schema.NODE_PHASES[node_id],
        "kind": knowledge_schema.NODE_KINDS[node_id],
        "generation": generation,
        "source_run_id": source_run_id,
        "method_identity": (
            dict(method_identity) if method_identity is not None else None
        ),
        "digests": dict(digests) if digests is not None else _empty_digests(),
        "facts": dict(facts) if facts is not None else _facts(),
        "status": _status(freshness, alignment),
        "diagnostics": list(diagnostics or []),
    }


def _replace_alignment(node: Mapping[str, Any], alignment: str) -> dict[str, Any]:
    result = dict(node)
    result["status"] = {
        **dict(node["status"]),
        "alignment_status": alignment,
    }
    return result


def _record_state(node: Mapping[str, Any]) -> str:
    return {
        "current": "present",
        "missing": "absent",
        "invalid": "invalid",
    }[str(node["status"]["record_freshness"])]


def _record_alignment(
    node: Mapping[str, Any],
    incoming: list[str],
) -> str:
    freshness = node["status"]["record_freshness"]
    if freshness == "missing":
        return "not_available"
    if freshness == "invalid":
        return "blocked"
    return knowledge_schema.aggregate_alignment_status(incoming)


def _bounded_error(error: BaseException, root: Path) -> str:
    message = " ".join(str(error).split())
    for candidate in (str(root), root.as_posix()):
        message = message.replace(candidate, "<project>")
    if len(message) > knowledge_schema.MAX_DIAGNOSTIC_LENGTH - 30:
        message = (
            message[: knowledge_schema.MAX_DIAGNOSTIC_LENGTH - 33] + "..."
        )
    return f"canonical record is invalid: {message or type(error).__name__}"


def _record_digest(path: Path, *, label: str) -> str:
    digest, _ = project_state.bounded_file_digest(
        path,
        maximum=MAX_RECORD_FILE_BYTES,
        label=label,
    )
    return digest


def _current_method(
    project_dir: Path,
    stable_id: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    try:
        expected_key = knowledge_schema.branch_key(stable_id)
    except knowledge_schema.KnowledgeSchemaError as exc:
        raise KnowledgeGraphBuildError(str(exc)) from exc
    del expected_key
    menu = method_menu.load_method_menu(project_dir)
    warnings = menu.get("warnings")
    if isinstance(warnings, list) and warnings:
        raise KnowledgeGraphBuildError(
            f"the current method catalog is invalid: {warnings[0]}"
        )
    matches = [
        entry
        for entry in menu.get("entries", [])
        if isinstance(entry, Mapping)
        and str(entry.get("stable_id", "")).strip() == stable_id
    ]
    if len(matches) != 1:
        raise KnowledgeGraphBuildError(
            f"the current method catalog does not define exactly one {stable_id!r}"
        )
    entry = dict(matches[0])
    errors = entry.get("errors")
    if isinstance(errors, list) and errors:
        raise KnowledgeGraphBuildError(
            f"the current method definition is invalid: {errors[0]}"
        )
    provenance_error = str(entry.get("provenance_error", "")).strip()
    if provenance_error:
        raise KnowledgeGraphBuildError(
            f"the current method provenance is invalid: {provenance_error}"
        )
    try:
        identity = phase_records.method_identity(entry)
    except phase_records.PhaseRecordError as exc:
        raise KnowledgeGraphBuildError(str(exc)) from exc
    return entry, identity


def _literature_node(root: Path) -> dict[str, Any]:
    try:
        record = literature_records.load_current_literature_record(root)
    except literature_records.LiteratureRecordError as exc:
        return _base_node(
            "p1-literature",
            freshness="invalid",
            alignment="blocked",
            diagnostics=[_bounded_error(exc, root)],
        )
    if record is None:
        return _base_node(
            "p1-literature",
            freshness="missing",
            alignment="not_available",
        )
    return _base_node(
        "p1-literature",
        freshness="current",
        alignment="exact_match",
        generation=int(record["generation"]),
        source_run_id=str(record["source_run_id"]),
        digests={
            "record_sha256": str(record["index_sha256"]),
            "primary_sha256": str(record["summary_sha256"]),
            "collection_sha256": str(record["papers_sha256"]),
        },
        facts=_facts(item_count=int(record["paper_count"])),
    )


def _method_node(
    entry: Mapping[str, Any],
    identity: Mapping[str, str],
) -> dict[str, Any]:
    digest = identity["definition_sha256"]
    provenance = entry.get("provenance")
    review_source_run_id = (
        str(provenance.get("review_source_run_id", "")).strip() or None
        if isinstance(provenance, Mapping)
        else None
    )
    return _base_node(
        "p2-method",
        freshness="current",
        alignment="exact_match",
        source_run_id=review_source_run_id,
        method_identity=identity,
        digests={
            "record_sha256": digest,
            "primary_sha256": digest,
            "collection_sha256": None,
        },
        diagnostics=[],
    )


def _theory_node(
    root: Path,
    stable_id: str,
) -> tuple[dict[str, Any], Any, Any]:
    try:
        record = theory_records.load_current_theory(root, stable_id)
    except theory_records.TheoryRecordError as exc:
        return (
            _base_node(
                "p3-theory",
                freshness="invalid",
                alignment="blocked",
                diagnostics=[_bounded_error(exc, root)],
            ),
            None,
            None,
        )
    if record is None:
        return (
            _base_node(
                "p3-theory",
                freshness="missing",
                alignment="not_available",
            ),
            None,
            None,
        )
    try:
        current_dir = theory_records.current_theory_directory(root, stable_id)
        record_digest = _record_digest(
            current_dir / theory_records.RECORD_FILENAME,
            label="current theory record",
        )
        fragment = None
        collection_digest = None
        if isinstance(record.get("knowledge_sha256"), str):
            raw_fragment, fragment_payload = knowledge_fragments.read_fragment(
                current_dir / theory_records.KNOWLEDGE_FILENAME,
                label="current theory knowledge fragment",
            )
            fragment = knowledge_fragments.validate_theory_fragment(
                raw_fragment,
                expected_method=record["method_identity"],
                expected_generation=record["generation"],
                expected_source_run_id=record["source_run_id"],
                require_complete=True,
            )
            collection_digest = hashlib.sha256(fragment_payload).hexdigest()
    except (
        knowledge_fragments.KnowledgeFragmentError,
        project_state.ProjectStateError,
    ) as exc:
        return (
            _base_node(
                "p3-theory",
                freshness="invalid",
                alignment="blocked",
                diagnostics=[_bounded_error(exc, root)],
            ),
            None,
            None,
        )
    return (
        _base_node(
            "p3-theory",
            freshness="current",
            alignment="exact_match",
            generation=int(record["generation"]),
            source_run_id=str(record["source_run_id"]),
            method_identity=record["method_identity"],
            digests={
                "record_sha256": record_digest,
                "primary_sha256": str(record["manuscript_sha256"]),
                "collection_sha256": collection_digest,
            },
        ),
        record,
        fragment,
    )


def _empirical_node(
    root: Path,
    stable_id: str,
) -> tuple[dict[str, Any], Any, Any]:
    try:
        record = empirical_records.load_current_package(root, stable_id)
    except empirical_records.EmpiricalRecordError as exc:
        return (
            _base_node(
                "p4-empirical",
                freshness="invalid",
                alignment="blocked",
                diagnostics=[_bounded_error(exc, root)],
            ),
            None,
            None,
        )
    if record is None:
        return (
            _base_node(
                "p4-empirical",
                freshness="missing",
                alignment="not_available",
            ),
            None,
            None,
        )
    try:
        package_dir = empirical_records.canonical_package_dir(root, stable_id)
        record_digest = _record_digest(
            package_dir / empirical_records.INDEX_FILENAME,
            label="current empirical evidence index",
        )
        knowledge_path = package_dir / empirical_records.KNOWLEDGE_FILENAME
        fragment = None
        try:
            knowledge_path.lstat()
        except FileNotFoundError:
            collection_digest = None
        except OSError as exc:
            raise project_state.StateValidationError(
                "current empirical knowledge fragment is unavailable"
            ) from exc
        else:
            fragment, fragment_payload = knowledge_fragments.read_fragment(
                knowledge_path,
                label="current empirical knowledge fragment",
            )
            fragment = knowledge_fragments.validate_empirical_fragment(
                fragment,
                record,
                expected_method=record["method"],
                expected_generation=record["generation"],
                expected_source_run_id=record["source_run_id"],
                require_complete=True,
            )
            collection_digest = hashlib.sha256(fragment_payload).hexdigest()
    except (
        empirical_records.EmpiricalRecordError,
        knowledge_fragments.KnowledgeFragmentError,
        project_state.ProjectStateError,
    ) as exc:
        return (
            _base_node(
                "p4-empirical",
                freshness="invalid",
                alignment="blocked",
                diagnostics=[_bounded_error(exc, root)],
            ),
            None,
            None,
        )
    entries = record["entries"]
    outdated_count = sum(
        1 for entry in entries if entry["status"] == "outdated"
    )
    unresolved_count = sum(
        1 for entry in entries if entry["status"] == "unresolved"
    )
    diagnostics = []
    if outdated_count or unresolved_count:
        diagnostics.append(
            "record contains "
            f"{outdated_count} outdated and {unresolved_count} unresolved "
            "evidence entries"
        )
    return (
        _base_node(
            "p4-empirical",
            freshness="current",
            alignment="exact_match",
            generation=int(record["generation"]),
            source_run_id=str(record["source_run_id"]),
            method_identity=record["method"],
            digests={
                "record_sha256": record_digest,
                "primary_sha256": str(record["synthesis"]["sha256"]),
                "collection_sha256": collection_digest,
            },
            facts=_facts(
                item_count=len(entries),
                outdated_count=outdated_count,
                unresolved_count=unresolved_count,
            ),
            diagnostics=diagnostics,
        ),
        record,
        fragment,
    )


def _semantic_basis(
    node: Mapping[str, Any],
    record: Any,
    fragment: Any,
    *,
    phase_slug: str,
    evidence_index: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    state = _record_state(node)
    if state == "absent":
        return knowledge_basis.absent_basis(phase_slug=phase_slug)
    if state == "invalid":
        return None
    if not isinstance(record, Mapping):
        raise knowledge_basis.KnowledgeBasisValidationError(
            "present semantic record is unavailable"
        )
    method = record.get("method_identity", record.get("method"))
    if fragment is None:
        return knowledge_basis.unknown_legacy_basis(
            phase_slug=phase_slug,
            method_identity=method,
            generation=record.get("generation"),
            source_run_id=record.get("source_run_id"),
        )
    content_reference = knowledge_content.build_content_reference(
        phase_slug=phase_slug,
        fragment=fragment,
        evidence_index=evidence_index,
    )
    return knowledge_basis.available_basis(
        phase_slug=phase_slug,
        method_identity=method,
        content_reference=content_reference,
        generation=record["generation"],
        source_run_id=record["source_run_id"],
    )


def _stored_counterpart_basis(
    node: Mapping[str, Any],
    record: Any,
    *,
    counterpart_phase: str,
) -> dict[str, Any] | None:
    state = _record_state(node)
    if state != "present":
        return None
    if not isinstance(record, Mapping):
        raise knowledge_basis.KnowledgeBasisValidationError(
            "present counterpart record is unavailable"
        )
    if "counterpart_basis" not in record:
        return knowledge_basis.unknown_legacy_basis(
            phase_slug=counterpart_phase
        )
    basis = knowledge_basis.validate_basis(record["counterpart_basis"])
    if basis["phase_slug"] != counterpart_phase:
        raise knowledge_basis.KnowledgeBasisValidationError(
            "counterpart basis names the wrong phase"
        )
    return basis


def _invalid_semantic_node(
    node_id: str,
    error: BaseException,
    root: Path,
) -> dict[str, Any]:
    return _base_node(
        node_id,
        freshness="invalid",
        alignment="blocked",
        diagnostics=[_bounded_error(error, root)],
    )


def _manuscript_node(root: Path, stable_id: str) -> tuple[dict[str, Any], Any]:
    try:
        record = manuscript_records.load_current_manuscript(root, stable_id)
    except manuscript_records.ManuscriptRecordError as exc:
        return (
            _base_node(
                "p5-manuscript",
                freshness="invalid",
                alignment="blocked",
                diagnostics=[_bounded_error(exc, root)],
            ),
            None,
        )
    if record is None:
        return (
            _base_node(
                "p5-manuscript",
                freshness="missing",
                alignment="not_available",
            ),
            None,
        )
    try:
        record_digest = _record_digest(
            manuscript_records.current_manuscript_directory(root, stable_id)
            / manuscript_records.RECORD_FILENAME,
            label="current manuscript record",
        )
    except project_state.ProjectStateError as exc:
        return (
            _base_node(
                "p5-manuscript",
                freshness="invalid",
                alignment="blocked",
                diagnostics=[_bounded_error(exc, root)],
            ),
            None,
        )
    return (
        _base_node(
            "p5-manuscript",
            freshness="current",
            alignment="exact_match",
            generation=int(record["generation"]),
            source_run_id=str(record["source_run_id"]),
            method_identity=record["method_identity"],
            digests={
                "record_sha256": record_digest,
                "primary_sha256": str(record["manuscript_sha256"]),
                "collection_sha256": None,
            },
        ),
        record,
    )


def _reference(
    digest: str | None,
    generation: int | None,
    *,
    method_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "sha256": digest,
        "generation": generation,
        "method_identity": (
            dict(method_identity) if method_identity is not None else None
        ),
    }


def _observed_reference(
    node: Mapping[str, Any],
    *,
    digest_field: str,
    include_generation: bool = True,
) -> dict[str, Any]:
    return _reference(
        node["digests"][digest_field],
        node["generation"] if include_generation else None,
        method_identity=(
            node["method_identity"]
            if node["id"] == "p2-method"
            else None
        ),
    )


def _edge_alignment(
    edge_id: str,
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> str:
    source_freshness = source["status"]["record_freshness"]
    target_freshness = target["status"]["record_freshness"]
    if source_freshness == "invalid" or target_freshness == "invalid":
        return "blocked"
    if target_freshness == "missing":
        return "not_available"
    if source_freshness == "missing":
        if (
            edge_id in {
                knowledge_schema.P1_P2_SYNTHESIS_EDGE_ID,
                knowledge_schema.P1_P2_COLLECTION_EDGE_ID,
            }
            and expected["sha256"] is None
        ):
            return "not_available"
        return "blocked"
    if expected["sha256"] is None:
        if (
            edge_id in knowledge_schema.P1_UNKNOWN_BASIS_REVIEW_EDGES
            and observed["sha256"] is not None
        ):
            return "review_required"
        return "blocked"
    if observed["sha256"] is None:
        return "blocked"
    return "exact_match" if expected == observed else "review_required"


def _semantic_edge(
    edge_id: str,
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    expected: Mapping[str, Any] | None,
    observed: Mapping[str, Any] | None,
    current_method: Mapping[str, Any],
) -> dict[str, Any]:
    alignment = knowledge_basis.contextual_alignment(
        observed,
        expected,
        source_record_state=_record_state(source),
        target_record_state=_record_state(target),
    )
    if (
        alignment == "exact_match"
        and _record_state(source) == "present"
        and observed["method_identity"] != dict(current_method)
    ):
        alignment = "review_required"
    return {
        "id": edge_id,
        "source": source["id"],
        "target": target["id"],
        "basis_slot": "counterpart_basis",
        "expected": (
            dict(expected) if expected is not None else None
        ),
        "observed": (
            dict(observed) if observed is not None else None
        ),
        "alignment_status": alignment,
    }


def _edge(
    edge_id: str,
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    basis_slot: str,
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source": source["id"],
        "target": target["id"],
        "basis_slot": basis_slot,
        "expected": dict(expected),
        "observed": dict(observed),
        "alignment_status": _edge_alignment(
            edge_id,
            source, target, expected, observed
        ),
    }


def _expected_from_method(record: Any) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        return _reference(None, None)
    method = record.get("method_identity", record.get("method"))
    if not isinstance(method, Mapping):
        return _reference(None, None)
    return _reference(
        str(method.get("definition_sha256", "")) or None,
        None,
        method_identity=method,
    )


def _expected_from_method_literature(
    entry: Mapping[str, Any],
    basis_slot: str,
) -> dict[str, Any]:
    provenance = entry.get("provenance")
    basis = (
        provenance.get("literature_basis")
        if isinstance(provenance, Mapping)
        else None
    )
    if (
        not isinstance(basis, Mapping)
        or basis.get("availability") != "available"
    ):
        return _reference(None, None)
    field = (
        "synthesis_sha256"
        if basis_slot == "p1_synthesis"
        else "collection_sha256"
    )
    digest = basis.get(field)
    return _reference(str(digest) if isinstance(digest, str) else None, None)


def _expected_from_manuscript(
    record: Any,
    basis_slot: str,
) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        return _reference(None, None)
    basis = record.get("upstream_basis")
    if not isinstance(basis, Mapping):
        return _reference(None, None)
    selected = basis.get(basis_slot)
    if not isinstance(selected, Mapping):
        return _reference(None, None)
    digest = selected.get("sha256")
    generation = selected.get("generation")
    identity = selected.get("identity")
    compared_generation = (
        None if basis_slot in {"p1_synthesis", "p1_collection"} else generation
    )
    return _reference(
        str(digest) if isinstance(digest, str) else None,
        compared_generation if type(compared_generation) is int else None,
        method_identity=(
            identity
            if basis_slot == "p2_definition"
            and isinstance(identity, Mapping)
            else None
        ),
    )


def build_branch_basis_graph(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, Any]:
    """Rebuild one branch graph from verified canonical current records."""

    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise KnowledgeGraphBuildError(
            f"project directory is not a directory: {root}"
        )
    normalized_id = str(stable_id).strip()
    entry, identity = _current_method(root, normalized_id)

    p1 = _literature_node(root)
    p2 = _method_node(entry, identity)
    p3, theory_record, theory_fragment = _theory_node(root, normalized_id)
    p4, empirical_record, empirical_fragment = _empirical_node(
        root, normalized_id
    )
    p5, manuscript_record = _manuscript_node(root, normalized_id)

    try:
        current_p3_basis = _semantic_basis(
            p3,
            theory_record,
            theory_fragment,
            phase_slug=knowledge_basis.THEORY_PHASE,
        )
        p3_stored_p4_basis = _stored_counterpart_basis(
            p3,
            theory_record,
            counterpart_phase=knowledge_basis.EMPIRICAL_PHASE,
        )
    except (
        knowledge_basis.KnowledgeBasisError,
        knowledge_content.KnowledgeContentError,
    ) as exc:
        p3 = _invalid_semantic_node("p3-theory", exc, root)
        theory_record = None
        current_p3_basis = None
        p3_stored_p4_basis = None

    try:
        current_p4_basis = _semantic_basis(
            p4,
            empirical_record,
            empirical_fragment,
            phase_slug=knowledge_basis.EMPIRICAL_PHASE,
            evidence_index=empirical_record,
        )
        p4_stored_p3_basis = _stored_counterpart_basis(
            p4,
            empirical_record,
            counterpart_phase=knowledge_basis.THEORY_PHASE,
        )
    except (
        knowledge_basis.KnowledgeBasisError,
        knowledge_content.KnowledgeContentError,
    ) as exc:
        p4 = _invalid_semantic_node("p4-empirical", exc, root)
        empirical_record = None
        current_p4_basis = None
        p4_stored_p3_basis = None

    p2_observed = _observed_reference(p2, digest_field="primary_sha256")
    edges = [
        _edge(
            knowledge_schema.P1_P2_SYNTHESIS_EDGE_ID,
            p1,
            p2,
            basis_slot="p1_synthesis",
            expected=_expected_from_method_literature(
                entry, "p1_synthesis"
            ),
            observed=_observed_reference(
                p1,
                digest_field="primary_sha256",
                include_generation=False,
            ),
        ),
        _edge(
            knowledge_schema.P1_P2_COLLECTION_EDGE_ID,
            p1,
            p2,
            basis_slot="p1_collection",
            expected=_expected_from_method_literature(
                entry, "p1_collection"
            ),
            observed=_observed_reference(
                p1,
                digest_field="collection_sha256",
                include_generation=False,
            ),
        ),
        _edge(
            "p1-literature--p5-manuscript:p1_synthesis",
            p1,
            p5,
            basis_slot="p1_synthesis",
            expected=_expected_from_manuscript(
                manuscript_record, "p1_synthesis"
            ),
            observed=_observed_reference(
                p1,
                digest_field="primary_sha256",
                include_generation=False,
            ),
        ),
        _edge(
            knowledge_schema.P1_COLLECTION_EDGE_ID,
            p1,
            p5,
            basis_slot="p1_collection",
            expected=_expected_from_manuscript(
                manuscript_record, "p1_collection"
            ),
            observed=_observed_reference(
                p1,
                digest_field="collection_sha256",
                include_generation=False,
            ),
        ),
        _edge(
            "p2-method--p3-theory:method_definition",
            p2,
            p3,
            basis_slot="method_definition",
            expected=_expected_from_method(theory_record),
            observed=p2_observed,
        ),
        _edge(
            "p2-method--p4-empirical:method_definition",
            p2,
            p4,
            basis_slot="method_definition",
            expected=_expected_from_method(empirical_record),
            observed=p2_observed,
        ),
        _edge(
            "p2-method--p5-manuscript:p2_definition",
            p2,
            p5,
            basis_slot="p2_definition",
            expected=_expected_from_manuscript(
                manuscript_record, "p2_definition"
            ),
            observed=p2_observed,
        ),
        _semantic_edge(
            "p4-empirical--p3-theory:counterpart_basis",
            p4,
            p3,
            expected=p3_stored_p4_basis,
            observed=current_p4_basis,
            current_method=identity,
        ),
        _semantic_edge(
            "p3-theory--p4-empirical:counterpart_basis",
            p3,
            p4,
            expected=p4_stored_p3_basis,
            observed=current_p3_basis,
            current_method=identity,
        ),
        _edge(
            "p3-theory--p5-manuscript:p3_record",
            p3,
            p5,
            basis_slot="p3_record",
            expected=_expected_from_manuscript(
                manuscript_record, "p3_record"
            ),
            observed=_observed_reference(p3, digest_field="record_sha256"),
        ),
        _edge(
            "p4-empirical--p5-manuscript:p4_index",
            p4,
            p5,
            basis_slot="p4_index",
            expected=_expected_from_manuscript(
                manuscript_record, "p4_index"
            ),
            observed=_observed_reference(p4, digest_field="record_sha256"),
        ),
        _edge(
            "p4-empirical--p5-manuscript:p4_synthesis",
            p4,
            p5,
            basis_slot="p4_synthesis",
            expected=_expected_from_manuscript(
                manuscript_record, "p4_synthesis"
            ),
            observed=_observed_reference(p4, digest_field="primary_sha256"),
        ),
    ]

    edge_by_id = {edge["id"]: edge for edge in edges}
    p2 = _replace_alignment(
        p2,
        _record_alignment(
            p2,
            [
                edge_by_id[
                    knowledge_schema.P1_P2_SYNTHESIS_EDGE_ID
                ]["alignment_status"],
                edge_by_id[
                    knowledge_schema.P1_P2_COLLECTION_EDGE_ID
                ]["alignment_status"],
            ],
        ),
    )
    p3 = _replace_alignment(
        p3,
        _record_alignment(
            p3,
            [
                edge_by_id[
                    "p2-method--p3-theory:method_definition"
                ]["alignment_status"],
                edge_by_id[
                    "p4-empirical--p3-theory:counterpart_basis"
                ]["alignment_status"],
            ],
        ),
    )
    p4_alignment = _record_alignment(
        p4,
        [
            edge_by_id[
                "p2-method--p4-empirical:method_definition"
            ]["alignment_status"],
            edge_by_id[
                "p3-theory--p4-empirical:counterpart_basis"
            ]["alignment_status"],
        ],
    )
    if p4_alignment == "exact_match" and (
        p4["facts"]["outdated_count"] or p4["facts"]["unresolved_count"]
    ):
        p4_alignment = "review_required"
    p4 = _replace_alignment(p4, p4_alignment)

    if p5["status"]["record_freshness"] == "current":
        incoming = [
            edge["alignment_status"]
            for edge in edges
            if edge["target"] == "p5-manuscript"
        ]
        incoming.extend(
            node["status"]["alignment_status"]
            for node in (p3, p4)
            if node["status"]["record_freshness"] == "current"
        )
        p5 = _replace_alignment(
            p5,
            knowledge_schema.aggregate_alignment_status(incoming),
        )

    nodes = [p1, p2, p3, p4, p5]
    return knowledge_schema.seal_graph(
        {
            "schema_version": knowledge_schema.SCHEMA_VERSION,
            "kind": knowledge_schema.GRAPH_KIND,
            "branch_key": knowledge_schema.branch_key(normalized_id),
            "branch": identity,
            "nodes": nodes,
            "edges": edges,
            "summary": knowledge_schema.summarize_nodes(nodes),
        }
    )


def phase_two_review_projection(
    graph: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the method-specific state behind the Phase 2 literature label.

    The projection deliberately excludes Phase 3 through Phase 5 records. A
    theory or empirical update already has its own launch token and must not
    change this Phase 2 review token.
    """

    if not isinstance(graph, Mapping):
        raise KnowledgeGraphBuildError(
            "the branch graph is unavailable for Phase 2 review"
        )
    branch = graph.get("branch")
    try:
        normalized_branch = knowledge_schema.normalize_method_identity(branch)
    except knowledge_schema.KnowledgeSchemaError as exc:
        raise KnowledgeGraphBuildError(
            "the branch graph has no valid Phase 2 method identity"
        ) from exc

    nodes = [
        node
        for node in graph.get("nodes", [])
        if isinstance(node, Mapping) and node.get("id") == "p2-method"
    ]
    if len(nodes) != 1:
        raise KnowledgeGraphBuildError(
            "the branch graph has no unique Phase 2 method node"
        )
    node = nodes[0]
    status = node.get("status")
    diagnostics = node.get("diagnostics")
    if not isinstance(status, Mapping) or not isinstance(diagnostics, list):
        raise KnowledgeGraphBuildError(
            "the Phase 2 method review state is invalid"
        )

    edge_by_id = {
        str(edge.get("id", "")): edge
        for edge in graph.get("edges", [])
        if isinstance(edge, Mapping)
    }
    projected_edges: list[dict[str, Any]] = []
    for edge_id in (
        knowledge_schema.P1_P2_SYNTHESIS_EDGE_ID,
        knowledge_schema.P1_P2_COLLECTION_EDGE_ID,
    ):
        edge = edge_by_id.get(edge_id)
        if not isinstance(edge, Mapping):
            raise KnowledgeGraphBuildError(
                "the branch graph is missing a Phase 2 literature edge"
            )
        expected = edge.get("expected")
        observed = edge.get("observed")
        alignment = edge.get("alignment_status")
        if (
            not isinstance(expected, Mapping)
            or not isinstance(observed, Mapping)
            or alignment not in knowledge_schema.ALIGNMENT_STATUS_VALUES
        ):
            raise KnowledgeGraphBuildError(
                "a Phase 2 literature edge is invalid"
            )
        projected_edges.append({
            "id": edge_id,
            "expected": dict(expected),
            "observed": dict(observed),
            "alignment_status": str(alignment),
        })

    return {
        "schema_version": 1,
        "method_identity": normalized_branch,
        "review_source_run_id": (
            str(node.get("source_run_id"))
            if node.get("source_run_id") is not None
            else None
        ),
        "status": dict(status),
        "diagnostics": [
            str(item) for item in diagnostics if isinstance(item, str)
        ],
        "literature_edges": projected_edges,
    }


def phase_two_review_projection_version(
    graph: Mapping[str, Any],
) -> str:
    """Return a deterministic hash of one method's Phase 2 review state."""

    payload = json.dumps(
        phase_two_review_projection(graph),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def shadow_graph_path(
    project_dir: str | Path,
    stable_id: str,
) -> Path:
    """Return the protected, opaque cache path for one branch graph."""

    return (
        project_state.state_dir(project_dir)
        / "knowledge"
        / "branches"
        / knowledge_schema.branch_key(str(stable_id).strip())
        / SHADOW_FILENAME
    )


def _write_shadow_graph_unlocked(
    project_dir: Path,
    stable_id: str,
    graph: Mapping[str, Any],
) -> Path:
    control = project_state._ensure_control_directory(project_dir)
    target = shadow_graph_path(project_dir, stable_id)
    directory = project_state._ensure_plain_directory_tree(
        target.parent,
        control,
        label="knowledge graph cache directory",
    )
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        metadata = None
    except OSError as exc:
        raise project_state.StateValidationError(
            f"knowledge graph cache is unavailable: {target}"
        ) from exc
    if metadata is not None and (
        metadata_is_link_or_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
    ):
        raise project_state.StateValidationError(
            "knowledge graph cache must be a regular file"
        )

    payload = knowledge_schema.graph_bytes(graph)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=directory,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        project_state._ensure_plain_directory_tree(
            directory,
            control,
            label="knowledge graph cache directory",
        )
        os.replace(temporary, target)
        project_state._sync_state_directory(directory)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def refresh_shadow_graph_unlocked(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, Any]:
    """Rebuild and cache one branch graph while the caller holds the lock."""

    root = Path(project_dir).resolve()
    normalized_id = str(stable_id).strip()
    graph = build_branch_basis_graph(root, normalized_id)
    _write_shadow_graph_unlocked(root, normalized_id, graph)
    return graph


def invalidate_shadow_graph_unlocked(
    project_dir: str | Path,
    stable_id: str,
) -> bool:
    """Remove one derived branch cache while the caller holds the lock."""

    root = Path(project_dir).resolve()
    control = project_state._ensure_control_directory(root)
    target = shadow_graph_path(root, stable_id)
    directory = target.parent
    try:
        directory_metadata = directory.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise project_state.StateValidationError(
            f"knowledge graph cache directory is unavailable: {directory}"
        ) from exc
    if metadata_is_link_or_reparse(directory_metadata) or not stat.S_ISDIR(
        directory_metadata.st_mode
    ):
        raise project_state.StateValidationError(
            "knowledge graph cache directory must be a plain directory"
        )
    directory = project_state._ensure_plain_directory_tree(
        directory,
        control,
        label="knowledge graph cache directory",
    )

    try:
        metadata = target.lstat()
    except FileNotFoundError:
        try:
            project_state._sync_state_directory(directory)
        except OSError as exc:
            raise project_state.StateValidationError(
                "knowledge graph cache absence could not be made durable"
            ) from exc
        return False
    except OSError as exc:
        raise project_state.StateValidationError(
            f"knowledge graph cache is unavailable: {target}"
        ) from exc
    if metadata_is_link_or_reparse(metadata) or not stat.S_ISREG(
        metadata.st_mode
    ):
        raise project_state.StateValidationError(
            "knowledge graph cache must be a regular file"
        )
    try:
        target.unlink()
    except FileNotFoundError:
        try:
            project_state._sync_state_directory(directory)
        except OSError as exc:
            raise project_state.StateValidationError(
                "knowledge graph cache absence could not be made durable"
            ) from exc
        return False
    except OSError as exc:
        raise project_state.StateValidationError(
            f"knowledge graph cache could not be removed: {target}"
        ) from exc
    try:
        project_state._sync_state_directory(directory)
    except OSError as exc:
        raise project_state.StateValidationError(
            "knowledge graph cache removal could not be made durable"
        ) from exc
    return True


def materialize_shadow_graph(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, Any]:
    """Rebuild and atomically cache a graph without changing project state."""

    root = Path(project_dir).resolve()
    with project_state._project_lock(root):
        return refresh_shadow_graph_unlocked(root, stable_id)


def read_shadow_graph(
    project_dir: str | Path,
    stable_id: str,
) -> dict[str, Any] | None:
    """Read a cached shadow graph.

    Callers must not treat this cache as current without rebuilding from the
    canonical records.
    """

    path = shadow_graph_path(project_dir, stable_id)
    if not path.exists():
        return None
    payload = project_state.bounded_file_bytes(
        path,
        maximum=knowledge_schema.MAX_GRAPH_BYTES,
        label="knowledge graph cache",
    )
    graph = knowledge_schema.parse_graph_bytes(payload)
    if graph["branch_key"] != knowledge_schema.branch_key(
        str(stable_id).strip()
    ):
        raise knowledge_schema.KnowledgeSchemaError(
            "knowledge graph cache belongs to another branch"
        )
    return graph
