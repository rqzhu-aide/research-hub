"""Validate user-controlled scope and context choices for phase runs.

These values are deliberately separate from free-text instructions.  They are
small, stable contracts shared by the Web UI, launch manifest, and agent
prompt.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


LITERATURE_SCOPE_INCREMENTAL = "incremental"

METHOD_SCOPE_FULL_CATALOG = "full_catalog"
METHOD_SCOPE_FOCUSED = "focused_method"
METHOD_SCOPES = frozenset({METHOD_SCOPE_FULL_CATALOG, METHOD_SCOPE_FOCUSED})

THEORY_CONTEXT_CURRENT = "current_only"
THEORY_CONTEXT_WITH_HISTORY = "include_archived_summaries"
THEORY_CONTEXT_POLICIES = frozenset(
    {THEORY_CONTEXT_CURRENT, THEORY_CONTEXT_WITH_HISTORY}
)


class PhaseOptionError(ValueError):
    """A phase option is missing, contradictory, or outside its phase."""


def _normalized_method_ids(values: Iterable[object]) -> set[str]:
    return {str(value).strip() for value in values if str(value).strip()}


def phase_two_scope(
    requested_scope: object,
    *,
    focused_method_id: object = "",
    active_method_ids: Iterable[object] = (),
) -> dict[str, Any]:
    """Return the validated Phase 2 catalog scope.

    A focused run may update one existing active method, but it still works
    from a complete staged copy of the catalog.  The promotion layer is
    responsible for proving that every non-selected entry stayed unchanged.
    """

    scope = str(requested_scope or METHOD_SCOPE_FULL_CATALOG).strip()
    if scope not in METHOD_SCOPES:
        raise PhaseOptionError(f"Unknown Phase 2 catalog scope: {scope!r}")

    method_id = str(focused_method_id or "").strip()
    active_ids = _normalized_method_ids(active_method_ids)
    if scope == METHOD_SCOPE_FULL_CATALOG:
        if method_id:
            raise PhaseOptionError(
                "A focused method cannot be supplied for a full-catalog run"
            )
        return {
            "schema_version": 1,
            "kind": "method_catalog",
            "scope": METHOD_SCOPE_FULL_CATALOG,
            "focused_method_id": None,
        }

    if not method_id:
        raise PhaseOptionError("A focused Phase 2 run requires one active method")
    if method_id not in active_ids:
        raise PhaseOptionError(
            "The focused Phase 2 method is not active in the current catalog"
        )
    return {
        "schema_version": 1,
        "kind": "method_catalog",
        "scope": METHOD_SCOPE_FOCUSED,
        "focused_method_id": method_id,
    }


def phase_three_context_policy(
    requested_policy: object,
    *,
    has_archived_summaries: bool,
) -> dict[str, Any]:
    """Return the validated Phase 3 context policy.

    The current theory package is always the primary input.  Archived run
    summaries are opt-in and cannot be requested before such history exists.
    """

    policy = str(requested_policy or THEORY_CONTEXT_CURRENT).strip()
    if policy not in THEORY_CONTEXT_POLICIES:
        raise PhaseOptionError(f"Unknown Phase 3 context policy: {policy!r}")
    if policy == THEORY_CONTEXT_WITH_HISTORY and not has_archived_summaries:
        raise PhaseOptionError(
            "Archived Phase 3 summaries are not available for this method"
        )
    return {
        "schema_version": 1,
        "kind": "theory_context",
        "policy": policy,
        "include_archived_summaries": policy == THEORY_CONTEXT_WITH_HISTORY,
    }


def validate_manifest_phase_options(
    phase_slug: str,
    run_scope: object,
    context_policy: object,
    *,
    audit_only: bool = False,
) -> None:
    """Validate phase-option records embedded in an immutable run manifest."""

    if phase_slug == "02-method-development":
        if not isinstance(run_scope, Mapping):
            raise PhaseOptionError("Phase 2 manifest has no catalog scope")
        scope = run_scope.get("scope")
        focused_id = run_scope.get("focused_method_id")
        if scope not in METHOD_SCOPES:
            raise PhaseOptionError("Phase 2 manifest has an invalid catalog scope")
        if scope == METHOD_SCOPE_FOCUSED and not str(focused_id or "").strip():
            raise PhaseOptionError(
                "Focused Phase 2 manifest has no selected method"
            )
        if scope == METHOD_SCOPE_FULL_CATALOG and focused_id is not None:
            raise PhaseOptionError(
                "Full-catalog Phase 2 manifest includes a focused method"
            )
    elif run_scope is not None:
        raise PhaseOptionError("Catalog scope is only valid for Phase 2")

    if phase_slug == "03-idea-evaluation" and not audit_only:
        if not isinstance(context_policy, Mapping):
            raise PhaseOptionError("Phase 3 manifest has no context policy")
        policy = context_policy.get("policy")
        include_history = context_policy.get("include_archived_summaries")
        if policy not in THEORY_CONTEXT_POLICIES:
            raise PhaseOptionError("Phase 3 manifest has an invalid context policy")
        expected = policy == THEORY_CONTEXT_WITH_HISTORY
        if include_history is not expected:
            raise PhaseOptionError(
                "Phase 3 manifest context policy is internally inconsistent"
            )
    elif context_policy is not None:
        raise PhaseOptionError("Theory context policy is only valid for Phase 3")
