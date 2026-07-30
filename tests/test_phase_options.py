from __future__ import annotations

import pytest

from core import phase_options


def test_phase_two_defaults_to_full_catalog() -> None:
    assert phase_options.phase_two_scope(None, active_method_ids={"m1"}) == {
        "schema_version": 1,
        "kind": "method_catalog",
        "scope": "full_catalog",
        "focused_method_id": None,
    }


def test_phase_two_focused_scope_requires_an_active_method() -> None:
    assert phase_options.phase_two_scope(
        "focused_method",
        focused_method_id="m1",
        active_method_ids={"m1", "m2"},
    )["focused_method_id"] == "m1"

    with pytest.raises(phase_options.PhaseOptionError, match="requires one"):
        phase_options.phase_two_scope(
            "focused_method", active_method_ids={"m1"}
        )
    with pytest.raises(phase_options.PhaseOptionError, match="not active"):
        phase_options.phase_two_scope(
            "focused_method",
            focused_method_id="retired",
            active_method_ids={"m1"},
        )


def test_phase_two_full_scope_rejects_a_hidden_focused_method() -> None:
    with pytest.raises(phase_options.PhaseOptionError, match="cannot be supplied"):
        phase_options.phase_two_scope(
            "full_catalog",
            focused_method_id="m1",
            active_method_ids={"m1"},
        )


def test_phase_three_history_is_explicit_and_requires_prior_summaries() -> None:
    current = phase_options.phase_three_context_policy(
        "", has_archived_summaries=False
    )
    assert current["policy"] == "current_only"
    assert current["include_archived_summaries"] is False

    with pytest.raises(phase_options.PhaseOptionError, match="not available"):
        phase_options.phase_three_context_policy(
            "include_archived_summaries",
            has_archived_summaries=False,
        )

    history = phase_options.phase_three_context_policy(
        "include_archived_summaries",
        has_archived_summaries=True,
    )
    assert history["include_archived_summaries"] is True


def test_manifest_phase_options_reject_cross_phase_values() -> None:
    with pytest.raises(phase_options.PhaseOptionError, match="only valid"):
        phase_options.validate_manifest_phase_options(
            "04-draft-assembly",
            {
                "scope": "full_catalog",
                "focused_method_id": None,
            },
            None,
        )

    phase_options.validate_manifest_phase_options(
        "03-idea-evaluation",
        None,
        {
            "policy": "current_only",
            "include_archived_summaries": False,
        },
    )
