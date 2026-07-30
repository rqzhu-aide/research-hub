"""Shared completion and recovery for durable phase-record promotions.

The state layer decides whether a run is current. This module then applies
that decision to the exact prepared transaction, immutable knowledge event,
derived branch graph, retained backup, and recovery journal.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core import (
    knowledge_events,
    knowledge_graph,
    phase_records,
    promotion_journal,
)


log = logging.getLogger(__name__)


class PromotionRecoveryError(ValueError):
    """A durable promotion could not be completed or reconciled safely."""


def _intent_event(
    intent: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(intent, Mapping):
        return None
    event = intent.get("knowledge_event")
    if event is None:
        return None
    if not isinstance(event, Mapping):
        raise PromotionRecoveryError(
            "promotion intent knowledge event must be an object"
        )
    return dict(event)


def _stable_id(intent: Mapping[str, Any] | None) -> str | None:
    if not isinstance(intent, Mapping):
        return None
    identity = intent.get("method_identity")
    if not isinstance(identity, Mapping):
        raise PromotionRecoveryError(
            "promotion intent has no method identity"
        )
    stable_id = str(identity.get("stable_id", "")).strip()
    if not stable_id:
        raise PromotionRecoveryError(
            "promotion intent has no stable method ID"
        )
    return stable_id


def _refresh_or_invalidate_graph(
    project_dir: str | Path,
    stable_id: str,
) -> None:
    try:
        knowledge_graph.refresh_shadow_graph_unlocked(
            project_dir,
            stable_id,
        )
    except Exception as refresh_error:
        try:
            knowledge_graph.invalidate_shadow_graph_unlocked(
                project_dir,
                stable_id,
            )
        except Exception as invalidation_error:
            raise PromotionRecoveryError(
                "branch knowledge graph could neither be refreshed nor "
                "invalidated; promotion recovery remains pending"
            ) from invalidation_error
        log.warning(
            "Branch knowledge graph refresh failed; its stale cache was "
            "invalidated: %s",
            refresh_error,
        )


def _remove_exact_event(
    project_dir: str | Path,
    event: Mapping[str, Any] | None,
) -> None:
    if event is None:
        return
    identity = event.get("current_method_identity")
    if not isinstance(identity, Mapping):
        raise PromotionRecoveryError(
            "promotion event has no method identity"
        )
    knowledge_events._remove_event_unlocked(
        project_dir,
        str(identity.get("stable_id", "")),
        str(event.get("phase_slug", "")),
        str(event.get("event_id", "")),
        expected_event_sha256=str(event.get("event_sha256", "")),
    )


def _intent_promotion(
    journal: Mapping[str, Any],
    recovered: Mapping[str, Any] | None,
) -> dict[str, Any]:
    intent = journal.get("intent")
    if not isinstance(intent, Mapping):
        raise PromotionRecoveryError(
            "promotion recovery requires a deterministic intent"
        )
    planned = intent.get("planned_promotion")
    if not isinstance(planned, Mapping):
        raise PromotionRecoveryError(
            "promotion intent has no planned transaction"
        )
    normalized = dict(planned)
    if recovered is not None and dict(recovered) != normalized:
        raise PromotionRecoveryError(
            "recovered promotion does not match the journaled plan"
        )
    recorded = journal.get("promotion")
    if recorded is not None and (
        not isinstance(recorded, Mapping)
        or dict(recorded) != normalized
    ):
        raise PromotionRecoveryError(
            "recorded promotion does not match the journaled plan"
        )
    return normalized


def complete_after_state_decision(
    project_dir: str | Path,
    control_dir: str | Path,
    journal: Mapping[str, Any],
    *,
    make_current: bool,
    recover_filesystem: bool,
) -> None:
    """Finish one promotion after the durable state has chosen old or new.

    The caller holds the project lock. On any failure the retained journal is
    left in place so a later locked load can retry the exact operation.
    """

    if type(make_current) is not bool or type(recover_filesystem) is not bool:
        raise PromotionRecoveryError(
            "promotion recovery decisions must be boolean"
        )
    expected_root = str(Path(project_dir).resolve())
    if journal.get("project_root") != expected_root:
        raise PromotionRecoveryError(
            "promotion journal belongs to a different project"
        )
    phase_slug = str(journal.get("phase_slug", ""))
    run_id = str(journal.get("run_id", ""))
    intent_value = journal.get("intent")
    intent = dict(intent_value) if isinstance(intent_value, Mapping) else None
    promotion_value = journal.get("promotion")
    promotion = (
        dict(promotion_value)
        if isinstance(promotion_value, Mapping)
        else None
    )

    if intent is not None:
        recovered: Mapping[str, Any] | None = None
        if recover_filesystem:
            recovered = phase_records.recover_prepared_promotion(
                project_dir,
                phase_slug,
                intent,
                make_current=make_current,
                lock_held=True,
            )
        if make_current:
            promotion = _intent_promotion(journal, recovered)
        elif recovered is not None:
            raise PromotionRecoveryError(
                "rollback recovery returned a published transaction"
            )
    elif recover_filesystem:
        if journal.get("status") != "promoted" or promotion is None:
            raise PromotionRecoveryError(
                "an intentionless prepared journal requires inspection"
            )
        if make_current:
            phase_records.commit_promotion(
                project_dir,
                phase_slug,
                promotion,
            )
            promotion = None
        else:
            phase_records.rollback_promotion(
                project_dir,
                phase_slug,
                promotion,
            )
            promotion = None

    event = _intent_event(intent)
    stable_id = _stable_id(intent)
    if make_current:
        if event is not None:
            knowledge_events._write_event_unlocked(project_dir, event)
        if stable_id is not None:
            _refresh_or_invalidate_graph(project_dir, stable_id)
        if promotion is not None:
            phase_records.commit_promotion(
                project_dir,
                phase_slug,
                promotion,
            )
    else:
        _remove_exact_event(project_dir, event)
        if stable_id is not None:
            _refresh_or_invalidate_graph(project_dir, stable_id)

    promotion_journal.remove(
        control_dir,
        run_id,
    )
