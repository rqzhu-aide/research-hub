"""Phase-specific current-record coordination.

The storage modules own their individual schemas and atomic file operations.
This module is the small dispatcher shared by launch preparation, submission
sealing, finalization, and current-context construction.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core import (
    empirical_records,
    knowledge_basis,
    knowledge_fragments,
    literature_records,
    manuscript_records,
    method_menu,
    phase5_projection,
    theory_records,
)


LITERATURE_PHASE = "01-literature-review"
METHOD_PHASE = "02-method-development"
THEORY_PHASE = "03-idea-evaluation"
EMPIRICAL_PHASE = "04-draft-assembly"
MANUSCRIPT_PHASE = "05-review-revision"

SCHEMA_VERSION = 1
ELIGIBLE_CUMULATIVE_OUTCOMES = frozenset({"Complete", "Partial"})
_LIVE_CURRENT_RECORDS = object()


class PhaseRecordError(ValueError):
    """A current phase record could not be prepared, sealed, or promoted."""


def method_identity(
    method: Mapping[str, Any],
    *,
    definition_sha256: str | None = None,
) -> dict[str, str]:
    """Normalize the exact method identity used by branch records."""

    if not isinstance(method, Mapping):
        raise PhaseRecordError("A branch record requires a method identity")
    digest = str(
        definition_sha256
        if definition_sha256 is not None
        else method.get("definition_sha256", method.get("sha256", ""))
    ).strip().lower()
    identity = {
        "stable_id": str(method.get("stable_id", "")).strip(),
        "version": str(method.get("version", "")).strip(),
        "definition_sha256": digest,
    }
    if (
        not identity["stable_id"]
        or not identity["version"]
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise PhaseRecordError("The branch record method identity is incomplete")
    return identity


def manifest_method_identity(manifest: Mapping[str, Any]) -> dict[str, str]:
    selection = manifest.get("method_selection")
    snapshots = manifest.get("snapshots")
    selected = (
        snapshots.get("selected_method")
        if isinstance(snapshots, Mapping)
        else None
    )
    if not isinstance(selection, Mapping) or not isinstance(selected, Mapping):
        raise PhaseRecordError("The run manifest has no frozen method definition")
    schema_version = manifest.get("schema_version", 1)
    digest_field = (
        "definition_sha256"
        if type(schema_version) is int and schema_version >= 14
        else "sha256"
    )
    return method_identity(
        selection,
        definition_sha256=str(selected.get(digest_field, "")),
    )


def manifest_knowledge_heads(
    manifest: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return exact schema 13 and later heads without consulting live records."""

    schema_version = manifest.get("schema_version", 1)
    if type(schema_version) is not int or schema_version < 1:
        raise PhaseRecordError("The run manifest schema version is invalid")
    if schema_version < 13:
        return None
    raw_heads = manifest.get("knowledge_heads")
    if raw_heads is None:
        return None
    if not isinstance(raw_heads, Mapping) or set(raw_heads) != {
        "schema_version",
        "p3_theory",
        "p4_empirical",
    }:
        raise PhaseRecordError(
            "Schema 13 method run has invalid knowledge_heads"
        )
    if raw_heads.get("schema_version") != 1:
        raise PhaseRecordError("Knowledge heads schema version is invalid")
    try:
        p3_basis = knowledge_basis.validate_basis(raw_heads.get("p3_theory"))
        p4_basis = knowledge_basis.validate_basis(raw_heads.get("p4_empirical"))
    except knowledge_basis.KnowledgeBasisError as exc:
        raise PhaseRecordError(f"Knowledge heads are invalid: {exc}") from exc
    if (
        p3_basis["phase_slug"] != knowledge_basis.THEORY_PHASE
        or p4_basis["phase_slug"] != knowledge_basis.EMPIRICAL_PHASE
    ):
        raise PhaseRecordError("Knowledge heads name the wrong phases")
    normalized = {
        "schema_version": 1,
        "p3_theory": p3_basis,
        "p4_empirical": p4_basis,
    }
    if dict(raw_heads) != normalized:
        raise PhaseRecordError("Knowledge heads are not normalized")
    return normalized


def manifest_method_catalog_basis(
    manifest: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return the exact schema 13 and later Phase 2 source-catalog basis."""

    schema_version = manifest.get("schema_version", 1)
    if type(schema_version) is not int or schema_version < 1:
        raise PhaseRecordError("The run manifest schema version is invalid")
    if schema_version < 13:
        return None
    if "method_catalog_basis" not in manifest:
        raise PhaseRecordError(
            "Schema 13 manifest is missing method_catalog_basis"
        )
    raw_basis = manifest.get("method_catalog_basis")
    if str(manifest.get("phase_slug", "")) != METHOD_PHASE:
        if raw_basis is not None:
            raise PhaseRecordError(
                "Only a Phase 2 manifest may declare method_catalog_basis"
            )
        return None
    if not isinstance(raw_basis, Mapping) or set(raw_basis) != {
        "schema_version",
        "sha256",
    }:
        raise PhaseRecordError(
            "Schema 13 Phase 2 manifest has invalid method_catalog_basis"
        )
    digest = raw_basis.get("sha256")
    if (
        raw_basis.get("schema_version") != 1
        or type(digest) is not str
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise PhaseRecordError(
            "Schema 13 Phase 2 method_catalog_basis is invalid"
        )
    return {"schema_version": 1, "sha256": digest}


def phase_two_literature_basis(
    frozen_source: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Convert a verified launch-frozen Phase 1 source into graph provenance."""

    try:
        normalized = literature_records.normalize_frozen_literature_source(
            frozen_source
        )
    except literature_records.LiteratureRecordError as exc:
        raise PhaseRecordError(
            f"Frozen Phase 1 literature basis is invalid: {exc}"
        ) from exc
    if normalized is None:
        return method_menu.normalize_literature_basis({
            "schema_version": method_menu.LITERATURE_BASIS_SCHEMA_VERSION,
            "availability": "absent",
            "source_run_id": None,
            "generation": None,
            "synthesis_sha256": None,
            "collection_sha256": None,
        })
    return method_menu.normalize_literature_basis({
        "schema_version": method_menu.LITERATURE_BASIS_SCHEMA_VERSION,
        "availability": "available",
        "source_run_id": normalized["source_run_id"],
        "generation": normalized["generation"],
        "synthesis_sha256": normalized["summary_sha256"],
        "collection_sha256": normalized["papers_sha256"],
    })


def manifest_phase_two_literature_basis(
    manifest: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return a Phase 2 basis only when it was frozen into the run manifest."""

    schema_version = manifest.get("schema_version", 1)
    if type(schema_version) is not int or schema_version < 1:
        raise PhaseRecordError("The run manifest schema version is invalid")
    if schema_version < 13:
        return None
    phase_slug = str(manifest.get("phase_slug", ""))
    if "phase_two_literature_basis" not in manifest:
        # Compatibility for already sealed schema 13 and later manifests. Never infer
        # their review basis from live Phase 1 files at submission time.
        return None
    raw_basis = manifest.get("phase_two_literature_basis")
    if phase_slug != METHOD_PHASE:
        if raw_basis is not None:
            raise PhaseRecordError(
                "Only a Phase 2 manifest may declare a Phase 2 literature basis"
            )
        return None
    if raw_basis is None:
        raise PhaseRecordError(
            "Phase 2 manifest has no frozen literature basis"
        )
    try:
        return method_menu.normalize_literature_basis(raw_basis)
    except method_menu.MethodMenuError as exc:
        raise PhaseRecordError(
            f"Phase 2 manifest literature basis is invalid: {exc}"
        ) from exc


def manifest_counterpart_basis(
    manifest: Mapping[str, Any],
    phase_slug: str,
) -> dict[str, Any] | None:
    """Select a phase counterpart only from schema 13 and later frozen heads."""

    heads = manifest_knowledge_heads(manifest)
    if heads is None:
        return None
    if phase_slug == THEORY_PHASE:
        return dict(heads["p4_empirical"])
    if phase_slug == EMPIRICAL_PHASE:
        return dict(heads["p3_theory"])
    return None


def _file_record(path: Path, *, maximum: int, label: str) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise PhaseRecordError(f"{label} is unavailable: {exc}") from exc
    if not payload or len(payload) > maximum:
        raise PhaseRecordError(
            f"{label} must contain 1 to {maximum:,} bytes"
        )
    return {
        "path": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
    }


def _relative_file_record(
    root: Path,
    path: Path,
    *,
    maximum: int,
    label: str,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    record = _file_record(path, maximum=maximum, label=label)
    if (
        expected_sha256 is not None
        and not hmac.compare_digest(
            str(record["sha256"]),
            str(expected_sha256).strip().lower(),
        )
    ):
        raise PhaseRecordError(
            f"{label} changed after its current record was validated"
        )
    try:
        relative = path.resolve(strict=True).relative_to(root.resolve())
    except (OSError, ValueError) as exc:
        raise PhaseRecordError(f"{label} escaped the project directory") from exc
    record["path"] = relative.as_posix()
    return record


def prepare_output(
    project_dir: str | Path,
    phase_slug: str,
    output_root: str | Path,
    *,
    run_id: str,
    method: Mapping[str, Any] | None = None,
    run_mode: str = "",
    counterpart_basis: Mapping[str, Any] | None = None,
    frozen_current_records: object = _LIVE_CURRENT_RECORDS,
    expected_catalog_sha256: str | None = None,
) -> dict[str, Any] | None:
    """Prepare one run-local phase output from the verified current record."""

    if phase_slug == LITERATURE_PHASE:
        options: dict[str, Any] = {}
        if frozen_current_records is not _LIVE_CURRENT_RECORDS:
            if not isinstance(frozen_current_records, Mapping):
                raise PhaseRecordError(
                    "Frozen launch state is required for current-schema staging"
                )
            options["frozen_current"] = frozen_current_records.get(
                "p1_literature"
            )
        return literature_records.prepare_reference_delta(
            project_dir,
            output_root,
            source_run_id=run_id,
            **options,
        )
    if phase_slug == METHOD_PHASE:
        return method_menu.stage_method_menu(
            project_dir,
            output_root,
            expected_catalog_sha256=expected_catalog_sha256,
        )
    if phase_slug == THEORY_PHASE:
        if method is None:
            raise PhaseRecordError("Phase 3 requires one selected method")
        options: dict[str, Any] = {}
        if frozen_current_records is not _LIVE_CURRENT_RECORDS:
            if not isinstance(frozen_current_records, Mapping):
                raise PhaseRecordError(
                    "Frozen launch state is required for current-schema staging"
                )
            options["frozen_current"] = frozen_current_records.get("p3_theory")
        return theory_records.prepare_staged_theory(
            project_dir,
            output_root,
            method_identity=method_identity(method),
            source_run_id=run_id,
            **options,
        )
    if phase_slug == EMPIRICAL_PHASE:
        if method is None:
            raise PhaseRecordError("Phase 4 requires one selected method")
        options = {}
        if frozen_current_records is not _LIVE_CURRENT_RECORDS:
            if not isinstance(frozen_current_records, Mapping):
                raise PhaseRecordError(
                    "Frozen launch state is required for current-schema staging"
                )
            options["frozen_current"] = frozen_current_records.get("p4_empirical")
        return empirical_records.prepare_staged_package(
            project_dir,
            output_root,
            method_identity=method_identity(method),
            source_run_id=run_id,
            run_scope=run_mode,
            counterpart_basis=counterpart_basis,
            **options,
        )
    if phase_slug == MANUSCRIPT_PHASE:
        if method is None:
            raise PhaseRecordError("Phase 5 requires one selected method")
        options = {}
        if frozen_current_records is not _LIVE_CURRENT_RECORDS:
            if not isinstance(frozen_current_records, Mapping):
                raise PhaseRecordError(
                    "Frozen launch state is required for current-schema staging"
                )
            options["frozen_current"] = frozen_current_records.get(
                phase5_projection.P5_KEY
            )
            options["require_current"] = run_mode == "review-revision"
        return manuscript_records.prepare_staged_manuscript(
            project_dir,
            output_root,
            method_identity=method_identity(method),
            **options,
        )
    return None


def _literature_record(project_dir: str | Path) -> dict[str, Any] | None:
    loader = getattr(
        literature_records, "load_current_literature_record", None
    )
    if loader is None:
        return None
    record = loader(project_dir)
    return dict(record) if isinstance(record, Mapping) else None


def current_upstream_basis(
    project_dir: str | Path,
    method: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return the exact current P1 to P4 basis for a Phase 5 draft."""

    root = Path(project_dir).resolve()
    identity = method_identity(method)
    literature = _literature_record(root)
    theory = theory_records.load_current_theory(root, identity["stable_id"])
    empirical = empirical_records.load_current_package(
        root, identity["stable_id"]
    )
    if literature is None:
        raise PhaseRecordError("Phase 5 requires a current literature synthesis")
    if theory is None:
        raise PhaseRecordError("Phase 5 requires a current Phase 3 theory package")
    if empirical is None:
        raise PhaseRecordError(
            "Phase 5 requires a current Phase 4 empirical package"
        )
    if dict(theory.get("method_identity", {})) != identity:
        raise PhaseRecordError(
            "The current Phase 3 package does not match the selected method"
        )
    if dict(empirical.get("method", {})) != identity:
        raise PhaseRecordError(
            "The current Phase 4 package does not match the selected method"
        )

    theory_dir = theory_records.current_theory_directory(
        root, identity["stable_id"]
    )
    empirical_dir = empirical_records.canonical_package_dir(
        root, identity["stable_id"]
    )
    literature_summary = root / literature_records.LITERATURE_SUMMARY
    theory_record = theory_dir / theory_records.RECORD_FILENAME
    empirical_synthesis = (
        empirical_dir / empirical_records.SYNTHESIS_FILENAME
    )
    empirical_index = empirical_dir / empirical_records.INDEX_FILENAME

    return {
        "p1_synthesis": {
            "identity": "literature-synthesis",
            "sha256": _file_record(
                literature_summary,
                maximum=4 * 1024 * 1024,
                label="current literature synthesis",
            )["sha256"],
            "generation": literature.get("generation"),
        },
        "p1_collection": {
            "identity": "reference-card-collection",
            "sha256": literature["papers_sha256"],
            "generation": literature.get("generation"),
        },
        "p2_definition": {
            "identity": identity,
            "sha256": identity["definition_sha256"],
            "generation": None,
        },
        "p3_record": {
            "identity": f"{identity['stable_id']}:theory",
            "sha256": _file_record(
                theory_record,
                maximum=2 * 1024 * 1024,
                label="current theory record",
            )["sha256"],
            "generation": theory.get("generation"),
        },
        "p4_synthesis": {
            "identity": f"{identity['stable_id']}:empirical-synthesis",
            "sha256": _file_record(
                empirical_synthesis,
                maximum=empirical_records.MAX_SYNTHESIS_BYTES,
                label="current empirical synthesis",
            )["sha256"],
            "generation": empirical.get("generation"),
        },
        "p4_index": {
            "identity": f"{identity['stable_id']}:evidence-index",
            "sha256": _file_record(
                empirical_index,
                maximum=empirical_records.MAX_INDEX_BYTES,
                label="current empirical evidence index",
            )["sha256"],
            "generation": empirical.get("generation"),
        },
    }


def frozen_phase5_state(
    project_dir: str | Path,
    manifest: Mapping[str, Any],
    method: Mapping[str, Any],
) -> dict[str, Any]:
    """Return schema 12 or 13 inputs projected only from launch snapshots."""

    try:
        return phase5_projection.derive_frozen_phase5_state(
            project_dir,
            manifest,
            method_identity(method),
        )
    except phase5_projection.Phase5ProjectionError as exc:
        raise PhaseRecordError(
            f"Frozen Phase 5 inputs could not be verified: {exc}"
        ) from exc


def manifest_upstream_basis(
    project_dir: str | Path,
    manifest: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return the Phase 5 basis selected by the manifest schema."""

    schema_version = manifest.get("schema_version", 1)
    if type(schema_version) is not int or schema_version < 1:
        raise PhaseRecordError("The run manifest schema version is invalid")
    identity = manifest_method_identity(manifest)
    if schema_version >= 12:
        state = frozen_phase5_state(project_dir, manifest, identity)
        return {
            key: dict(value)
            for key, value in state["upstream_basis"].items()
        }
    raise PhaseRecordError(
        "This legacy Phase 5 run has no exact frozen scientific basis and "
        "cannot replace the current manuscript. Start a new Phase 5 run."
    )


def _empirical_seal(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    counterpart_basis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    index = empirical_records.validate_staged_package(project_dir, output_root)
    if index.get("schema_version") == empirical_records.INDEX_SCHEMA_VERSION:
        expected_basis = (
            counterpart_basis
            if counterpart_basis is not None
            else knowledge_basis.unknown_legacy_basis(
                phase_slug=knowledge_basis.THEORY_PHASE,
            )
        )
        index = empirical_records.validate_staged_package(
            project_dir,
            output_root,
            counterpart_basis=expected_basis,
        )
    elif counterpart_basis is not None:
        raise PhaseRecordError(
            "A legacy empirical index cannot bind a counterpart basis"
        )
    root = Path(output_root).resolve()
    synthesis = _file_record(
        root / empirical_records.SYNTHESIS_FILENAME,
        maximum=empirical_records.MAX_SYNTHESIS_BYTES,
        label="staged empirical synthesis",
    )
    evidence_index = _file_record(
        root / empirical_records.INDEX_FILENAME,
        maximum=empirical_records.MAX_INDEX_BYTES,
        label="staged empirical evidence index",
    )
    knowledge = _file_record(
        root / empirical_records.KNOWLEDGE_FILENAME,
        maximum=knowledge_fragments.MAX_KNOWLEDGE_BYTES,
        label="staged empirical knowledge fragment",
    )
    return {
        "index": index,
        "synthesis": synthesis,
        "evidence_index": evidence_index,
        "knowledge_fragment": knowledge,
    }


def seal_output(
    project_dir: str | Path,
    phase_slug: str,
    output_root: str | Path,
    *,
    run_id: str,
    scientific_outcome: str,
    manifest: Mapping[str, Any],
    counterpart_basis: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Seal the exact current-record candidate for one submitted run."""

    outcome = str(scientific_outcome).strip()
    eligible = outcome in ELIGIBLE_CUMULATIVE_OUTCOMES
    manifest_basis = manifest_counterpart_basis(manifest, phase_slug)
    schema_version = manifest.get("schema_version", 1)
    method_catalog_basis = manifest_method_catalog_basis(manifest)
    literature_basis = manifest_phase_two_literature_basis(manifest)
    if schema_version >= 13:
        if (
            counterpart_basis is not None
            and counterpart_basis != manifest_basis
        ):
            raise PhaseRecordError(
                "Submission counterpart basis differs from the frozen manifest"
            )
        counterpart_basis = manifest_basis
    elif counterpart_basis is not None:
        raise PhaseRecordError(
            "Legacy manifests cannot acquire a counterpart basis after launch"
        )
    kind = "none"
    data: Mapping[str, Any] | None = None

    if phase_slug == LITERATURE_PHASE and eligible:
        kind = "literature"
        data = literature_records.seal_reference_delta(
            project_dir, output_root
        )
    elif phase_slug == METHOD_PHASE and eligible:
        kind = "method_catalog"
        if literature_basis is not None:
            run_scope = manifest.get("run_scope")
            if not isinstance(run_scope, Mapping):
                raise PhaseRecordError(
                    "Phase 2 manifest has no valid catalog scope"
                )
            scope = str(run_scope.get("scope", "")).strip()
            focused_id = (
                str(run_scope.get("focused_method_id", "")).strip()
                if scope == "focused_method"
                else None
            )
            try:
                method_menu.apply_run_provenance(
                    project_dir,
                    output_root,
                    run_id=run_id,
                    scientific_outcome=outcome,
                    review_scope=scope,
                    literature_basis=literature_basis,
                    focused_method_id=focused_id,
                )
            except method_menu.MethodMenuError as exc:
                raise PhaseRecordError(str(exc)) from exc
        data = method_menu.seal_staged_menu(
            project_dir,
            output_root,
            expected_published_catalog_sha256=(
                method_catalog_basis["sha256"]
                if method_catalog_basis is not None
                else None
            ),
        )
    elif phase_slug == THEORY_PHASE and eligible:
        kind = "theory"
        data = theory_records.seal_staged_theory(
            project_dir,
            output_root,
            method_identity=manifest_method_identity(manifest),
            source_run_id=run_id,
            scientific_outcome=outcome,
            counterpart_basis=counterpart_basis,
        )
    elif phase_slug == EMPIRICAL_PHASE and eligible:
        kind = "empirical"
        data = _empirical_seal(
            project_dir,
            output_root,
            counterpart_basis=counterpart_basis,
        )
    elif (
        phase_slug == MANUSCRIPT_PHASE
        and outcome == "Complete"
        and not (
            isinstance(manifest.get("paper_review"), Mapping)
            and manifest["paper_review"].get("kind") == "review_only"
        )
    ):
        identity = manifest_method_identity(manifest)
        kind = "manuscript"
        data = manuscript_records.seal_staged_manuscript(
            project_dir,
            output_root,
            method_identity=identity,
            upstream_basis=manifest_upstream_basis(project_dir, manifest),
            source_run_id=run_id,
            scientific_outcome=outcome,
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "phase_slug": phase_slug,
        "scientific_outcome": outcome,
        "eligible": data is not None,
        "kind": kind,
        "data": dict(data) if isinstance(data, Mapping) else None,
    }


def _verify_empirical_seal(
    project_dir: str | Path,
    output_root: str | Path,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    sealed_index = data.get("index")
    sealed_basis = (
        sealed_index.get("counterpart_basis")
        if isinstance(sealed_index, Mapping)
        else None
    )
    current = _empirical_seal(
        project_dir,
        output_root,
        counterpart_basis=sealed_basis,
    )
    if json.dumps(current, sort_keys=True, separators=(",", ":")) != json.dumps(
        data, sort_keys=True, separators=(",", ":")
    ):
        raise PhaseRecordError(
            "The staged empirical package changed after submission"
        )
    return current


def _sealed_candidate(
    phase_slug: str,
    seal: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    if (
        not isinstance(seal, Mapping)
        or seal.get("schema_version") != SCHEMA_VERSION
        or seal.get("phase_slug") != phase_slug
    ):
        raise PhaseRecordError("The phase-record seal is invalid")
    if seal.get("eligible") is not True:
        return None
    data = seal.get("data")
    if not isinstance(data, Mapping):
        raise PhaseRecordError("The phase-record seal has no candidate data")
    return data


def validate_promotion_intent(
    phase_slug: str,
    intent: Mapping[str, Any] | None,
    *,
    operation_id: str,
    run_id: str,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Cross-check a deterministic P3 or P4 intent against its run."""

    if intent is None:
        return None
    if phase_slug not in {THEORY_PHASE, EMPIRICAL_PHASE}:
        raise PhaseRecordError(
            "Only Phase 3 and Phase 4 may carry a promotion intent"
        )
    if not isinstance(intent, Mapping):
        raise PhaseRecordError("The phase promotion intent is invalid")
    if (
        intent.get("operation_id") != operation_id
        or intent.get("phase_slug") != phase_slug
        or intent.get("source_run_id") != run_id
    ):
        raise PhaseRecordError(
            "The phase promotion intent does not match its journaled run"
        )
    if not isinstance(manifest, Mapping):
        raise PhaseRecordError(
            "A phase promotion intent requires its verified run manifest"
        )
    expected = manifest_method_identity(manifest)
    try:
        actual = method_identity(intent.get("method_identity", {}))
    except PhaseRecordError as exc:
        raise PhaseRecordError(
            "The phase promotion intent has an invalid method identity"
        ) from exc
    if actual != expected:
        raise PhaseRecordError(
            "The phase promotion intent does not match the frozen method"
        )
    return dict(intent)


def plan_output_promotion(
    project_dir: str | Path,
    phase_slug: str,
    output_root: str | Path,
    seal: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    operation_id: str,
    lock_held: bool = False,
) -> dict[str, Any] | None:
    """Plan a deterministic promotion for Phase 3 or Phase 4."""

    data = _sealed_candidate(phase_slug, seal)
    if phase_slug not in {THEORY_PHASE, EMPIRICAL_PHASE} or data is None:
        return None
    identity = manifest_method_identity(manifest)
    if phase_slug == THEORY_PHASE:
        return theory_records.plan_staged_theory_promotion(
            project_dir,
            output_root,
            data,
            expected_method_identity=identity,
            operation_id=operation_id,
        )

    verified = _verify_empirical_seal(project_dir, output_root, data)
    if dict(verified["index"].get("method", {})) != identity:
        raise PhaseRecordError(
            "The empirical package does not match the selected method"
        )
    return empirical_records.plan_staged_package_promotion(
        project_dir,
        output_root,
        operation_id=operation_id,
        expected_method_identity=identity,
        lock_held=lock_held,
    )


def promote_output(
    project_dir: str | Path,
    phase_slug: str,
    output_root: str | Path,
    seal: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    lock_held: bool = False,
    retain_backup: bool = False,
    promotion_intent: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Promote one sealed phase candidate to its canonical current record."""

    data = _sealed_candidate(phase_slug, seal)
    if data is None:
        return None

    if phase_slug == LITERATURE_PHASE:
        if promotion_intent is not None:
            raise PhaseRecordError("Phase 1 does not support a promotion intent")
        literature_records.verify_reference_delta_seal(
            project_dir, output_root, data
        )
        return literature_records.promote_reference_delta(
            project_dir, output_root, data,
            retain_backup=retain_backup,
        )
    if phase_slug == METHOD_PHASE:
        if promotion_intent is not None:
            raise PhaseRecordError("Phase 2 does not support a promotion intent")
        run_scope = manifest.get("run_scope")
        focused_id = (
            str(run_scope.get("focused_method_id", "")).strip()
            if isinstance(run_scope, Mapping)
            and run_scope.get("scope") == "focused_method"
            else None
        )
        return method_menu.promote_staged_menu(
            project_dir,
            output_root,
            data,
            focused_method_id=focused_id,
        )
    if phase_slug == THEORY_PHASE:
        return theory_records.promote_staged_theory(
            project_dir,
            output_root,
            data,
            expected_method_identity=manifest_method_identity(manifest),
            retain_backup=retain_backup,
            promotion_intent=promotion_intent,
        )
    if phase_slug == EMPIRICAL_PHASE:
        verified = _verify_empirical_seal(project_dir, output_root, data)
        identity = manifest_method_identity(manifest)
        if dict(verified["index"].get("method", {})) != identity:
            raise PhaseRecordError(
                "The empirical package does not match the selected method"
            )
        return empirical_records.promote_staged_package(
            project_dir,
            output_root,
            lock_held=lock_held,
            retain_backup=retain_backup,
            promotion_intent=promotion_intent,
        )
    if phase_slug == MANUSCRIPT_PHASE:
        if promotion_intent is not None:
            raise PhaseRecordError("Phase 5 does not support a promotion intent")
        identity = manifest_method_identity(manifest)
        return manuscript_records.promote_staged_manuscript(
            project_dir,
            output_root,
            data,
            expected_method_identity=identity,
            expected_upstream_basis=manifest_upstream_basis(
                project_dir, manifest
            ),
            retain_backup=retain_backup,
        )
    return None


def recover_prepared_promotion(
    project_dir: str | Path,
    phase_slug: str,
    promotion_intent: Mapping[str, Any],
    *,
    make_current: bool,
    lock_held: bool = False,
) -> dict[str, Any] | None:
    """Converge one exact deterministic P3 or P4 transaction."""

    if phase_slug == THEORY_PHASE:
        return theory_records.recover_theory_promotion_intent(
            project_dir,
            promotion_intent,
            make_current=make_current,
        )
    if phase_slug == EMPIRICAL_PHASE:
        return empirical_records.recover_empirical_promotion_intent(
            project_dir,
            promotion_intent,
            make_current=make_current,
            lock_held=lock_held,
        )
    raise PhaseRecordError(
        "Only Phase 3 and Phase 4 support prepared promotion recovery"
    )


def commit_promotion(
    project_dir: str | Path,
    phase_slug: str,
    promotion: Mapping[str, Any],
) -> None:
    """Commit a retained phase promotion after state persistence."""

    if not isinstance(promotion, Mapping):
        raise PhaseRecordError("The phase promotion record is invalid")
    if phase_slug == LITERATURE_PHASE:
        literature_records.commit_reference_delta_promotion(project_dir, promotion)
    elif phase_slug == METHOD_PHASE:
        method_menu.commit_method_menu_promotion(project_dir, promotion)
    elif phase_slug == THEORY_PHASE:
        theory_records.commit_theory_promotion(project_dir, promotion)
    elif phase_slug == EMPIRICAL_PHASE:
        empirical_records.commit_empirical_package_promotion(project_dir, promotion)
    elif phase_slug == MANUSCRIPT_PHASE:
        manuscript_records.commit_manuscript_promotion(project_dir, promotion)
    else:
        raise PhaseRecordError(f"Unknown phase-record promotion: {phase_slug}")


def rollback_promotion(
    project_dir: str | Path,
    phase_slug: str,
    promotion: Mapping[str, Any],
) -> None:
    """Restore the canonical record that preceded a retained promotion."""

    if not isinstance(promotion, Mapping):
        raise PhaseRecordError("The phase promotion record is invalid")
    if phase_slug == LITERATURE_PHASE:
        literature_records.rollback_reference_delta_promotion(project_dir, promotion)
    elif phase_slug == METHOD_PHASE:
        method_menu.rollback_method_menu_promotion(project_dir, promotion)
    elif phase_slug == THEORY_PHASE:
        theory_records.rollback_theory_promotion(project_dir, promotion)
    elif phase_slug == EMPIRICAL_PHASE:
        empirical_records.rollback_empirical_package_promotion(project_dir, promotion)
    elif phase_slug == MANUSCRIPT_PHASE:
        manuscript_records.rollback_manuscript_promotion(project_dir, promotion)
    else:
        raise PhaseRecordError(f"Unknown phase-record promotion: {phase_slug}")


def current_context_records(
    project_dir: str | Path,
    *,
    method: Mapping[str, Any] | None = None,
    include_manuscript: bool = False,
) -> list[dict[str, Any]]:
    """Describe compact current records to freeze into a new run."""

    root = Path(project_dir).resolve()
    records: list[dict[str, Any]] = []
    literature = _literature_record(root)
    if literature is not None:
        records.append(
            {
                "key": "p1_literature",
                "kind": "current_literature",
                "source_run_id": literature.get("source_run_id"),
                "generation": literature.get("generation"),
                "method_identity": None,
                "files": [
                    _relative_file_record(
                        root,
                        root / literature_records.LITERATURE_SUMMARY,
                        maximum=literature_records.MAX_SUMMARY_BYTES,
                        label="current literature synthesis",
                        expected_sha256=literature["summary_sha256"],
                    ),
                    _relative_file_record(
                        root,
                        root / literature_records.REFERENCE_INDEX,
                        maximum=literature_records.MAX_INDEX_BYTES,
                        label="current reference index",
                        expected_sha256=literature["index_sha256"],
                    ),
                ],
            }
        )
    if method is None:
        return records

    identity = method_identity(method)
    theory = theory_records.load_current_theory(root, identity["stable_id"])
    if theory is not None:
        directory = theory_records.current_theory_directory(
            root, identity["stable_id"]
        )
        theory_files = [
            _relative_file_record(
                root,
                directory / theory_records.THEORY_FILENAME,
                maximum=8 * 1024 * 1024,
                label="current theory manuscript",
            ),
            _relative_file_record(
                root,
                directory / theory_records.RECORD_FILENAME,
                maximum=2 * 1024 * 1024,
                label="current theory record",
            ),
        ]
        if theory.get("knowledge_file") == theory_records.KNOWLEDGE_FILENAME:
            theory_files.append(
                _relative_file_record(
                    root,
                    directory / theory_records.KNOWLEDGE_FILENAME,
                    maximum=knowledge_fragments.MAX_KNOWLEDGE_BYTES,
                    label="current theory knowledge fragment",
                )
            )
        records.append(
            {
                "key": "p3_theory",
                "kind": "current_theory",
                "source_run_id": theory.get("source_run_id"),
                "generation": theory.get("generation"),
                "method_identity": dict(theory["method_identity"]),
                "files": theory_files,
            }
        )
    empirical = empirical_records.load_current_package(
        root, identity["stable_id"]
    )
    if empirical is not None:
        directory = empirical_records.canonical_package_dir(
            root, identity["stable_id"]
        )
        empirical_files = [
            _relative_file_record(
                root,
                directory / empirical_records.SYNTHESIS_FILENAME,
                maximum=empirical_records.MAX_SYNTHESIS_BYTES,
                label="current empirical synthesis",
            ),
            _relative_file_record(
                root,
                directory / empirical_records.INDEX_FILENAME,
                maximum=empirical_records.MAX_INDEX_BYTES,
                label="current empirical evidence index",
            ),
        ]
        knowledge_path = directory / empirical_records.KNOWLEDGE_FILENAME
        if knowledge_path.exists():
            empirical_files.append(
                _relative_file_record(
                    root,
                    knowledge_path,
                    maximum=knowledge_fragments.MAX_KNOWLEDGE_BYTES,
                    label="current empirical knowledge fragment",
                )
            )
        records.append(
            {
                "key": "p4_empirical",
                "kind": "current_empirical",
                "source_run_id": empirical.get("source_run_id"),
                "generation": empirical.get("generation"),
                "method_identity": dict(empirical["method"]),
                "files": empirical_files,
            }
        )
    if include_manuscript:
        manuscript = manuscript_records.load_current_manuscript(
            root, identity["stable_id"]
        )
        if manuscript is not None:
            directory = manuscript_records.current_manuscript_directory(
                root, identity["stable_id"]
            )
            records.append(
                {
                    "key": "p5_manuscript",
                    "kind": "current_manuscript",
                    "source_run_id": manuscript.get("source_run_id"),
                    "generation": manuscript.get("generation"),
                    "method_identity": None,
                    "files": [
                        _relative_file_record(
                            root,
                            directory / manuscript_records.MANUSCRIPT_FILENAME,
                            maximum=manuscript_records.MAX_MANUSCRIPT_BYTES,
                            label="current manuscript",
                        ),
                        _relative_file_record(
                            root,
                            directory / manuscript_records.RECORD_FILENAME,
                            maximum=manuscript_records.MAX_RECORD_BYTES,
                            label="current manuscript record",
                        ),
                    ],
                }
            )
    return records
