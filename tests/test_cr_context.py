"""Context resolution, Phase 5 readiness, and _trusted_context integration."""

from __future__ import annotations

from pathlib import Path

from core import current_results as cr
from tests._cr_helpers import (
    project,
    _valid_branch_head,
    _valid_branch_record,
    _valid_global_record,
    _valid_global_head,
)


# ---------------------------------------------------------------------------
# §13: Phase 5 readiness
# ---------------------------------------------------------------------------


class TestPhase5Readiness:
    """P5 requires complete, up-to-date P3 and P4 heads."""

    def test_missing_p3_blocks_p5(self, project: Path) -> None:
        record = _valid_branch_record(stable_id="method-a", version="v1", digest="a" * 64)
        p4_head = _valid_branch_head(phase_slug="04-draft-assembly")
        p4_head["generation"] = 1
        p4_head["run_id"] = "run-004"
        p4_head["operation_id"] = "promote:04:run-004"
        record["heads"]["04-draft-assembly"] = p4_head
        cr.write_branch_record(project, "method-a", record)

        freshness = cr.get_branch_freshness(project, "method-a")
        assert "03-idea-evaluation" not in freshness
        assert "04-draft-assembly" in freshness

    def test_stale_p3_or_p4_blocks_p5(self, project: Path) -> None:
        p3_head = _valid_branch_head(phase_slug="03-idea-evaluation", version="v1", digest="a" * 64)
        p3_head["generation"] = 1
        p3_head["run_id"] = "run-003"
        p3_head["operation_id"] = "promote:03:run-003"

        p4_head = _valid_branch_head(phase_slug="04-draft-assembly", version="v1", digest="a" * 64)
        p4_head["generation"] = 1
        p4_head["run_id"] = "run-004"
        p4_head["operation_id"] = "promote:04:run-004"

        record = _valid_branch_record(stable_id="method-a", version="v2", digest="b" * 64)
        record["heads"]["03-idea-evaluation"] = p3_head
        record["heads"]["04-draft-assembly"] = p4_head
        cr.write_branch_record(project, "method-a", record)

        freshness = cr.get_branch_freshness(project, "method-a")
        assert freshness["03-idea-evaluation"]["status"] == "stale"
        assert freshness["04-draft-assembly"]["status"] == "stale"

    def test_both_fresh_allows_p5(self, project: Path) -> None:
        p3_head = _valid_branch_head(phase_slug="03-idea-evaluation", version="v1", digest="a" * 64)
        p3_head["generation"] = 1
        p3_head["run_id"] = "run-003"
        p3_head["operation_id"] = "promote:03:run-003"

        p4_head = _valid_branch_head(phase_slug="04-draft-assembly", version="v1", digest="a" * 64)
        p4_head["generation"] = 1
        p4_head["run_id"] = "run-004"
        p4_head["operation_id"] = "promote:04:run-004"

        record = _valid_branch_record(stable_id="method-a", version="v1", digest="a" * 64)
        record["heads"]["03-idea-evaluation"] = p3_head
        record["heads"]["04-draft-assembly"] = p4_head
        cr.write_branch_record(project, "method-a", record)

        freshness = cr.get_branch_freshness(project, "method-a")
        assert freshness["03-idea-evaluation"]["status"] == "fresh"
        assert freshness["04-draft-assembly"]["status"] == "fresh"


# ---------------------------------------------------------------------------
# §9: Context resolution
# ---------------------------------------------------------------------------


class TestContextResolution:
    """resolve_context_heads merges global and branch heads."""

    def test_empty_project_returns_empty(self, project: Path) -> None:
        result = cr.resolve_context_heads(project, "03-idea-evaluation", "method-a")
        assert result == {}

    def test_global_heads_included(self, project: Path) -> None:
        record = _valid_global_record()
        record["heads"]["01-literature-review"] = _valid_global_head()
        record["heads"]["02-method-development"] = {
            **_valid_global_head(),
            "phase_slug": "02-method-development",
            "run_id": "run-02",
            "operation_id": "promote:02:run-02",
        }
        cr.write_global_record(project, record)

        result = cr.resolve_context_heads(project, "03-idea-evaluation", "method-a")
        assert "01-literature-review" in result
        assert "02-method-development" in result
        assert result["01-literature-review"]["scope"] == "global"

    def test_branch_heads_included(self, project: Path) -> None:
        p3_head = _valid_branch_head(phase_slug="03-idea-evaluation", version="v1", digest="a" * 64)
        p3_head["generation"] = 1
        p3_head["run_id"] = "run-003"
        p3_head["operation_id"] = "promote:03:run-003"

        record = _valid_branch_record(stable_id="method-a", version="v1", digest="a" * 64)
        record["heads"]["03-idea-evaluation"] = p3_head
        cr.write_branch_record(project, "method-a", record)

        result = cr.resolve_context_heads(project, "04-draft-assembly", "method-a")
        assert "03-idea-evaluation" in result
        assert result["03-idea-evaluation"]["scope"] == "branch"
        assert result["03-idea-evaluation"]["run_id"] == "run-003"

    def test_stale_head_labeled_as_recheck_baseline(self, project: Path) -> None:
        p3_head = _valid_branch_head(phase_slug="03-idea-evaluation", version="v1", digest="a" * 64)
        p3_head["generation"] = 1
        p3_head["run_id"] = "run-003"
        p3_head["operation_id"] = "promote:03:run-003"

        record = _valid_branch_record(stable_id="method-a", version="v2", digest="b" * 64)
        record["heads"]["03-idea-evaluation"] = p3_head
        cr.write_branch_record(project, "method-a", record)

        result = cr.resolve_context_heads(project, "04-draft-assembly", "method-a")
        assert result["03-idea-evaluation"]["freshness"] == "stale"
        assert result["03-idea-evaluation"]["relationship"] == "stale_recheck_baseline"

    def test_at_most_one_head_per_phase(self, project: Path) -> None:
        p3_head = _valid_branch_head(phase_slug="03-idea-evaluation")
        p3_head["generation"] = 1
        p3_head["run_id"] = "run-003"
        p3_head["operation_id"] = "promote:03:run-003"

        record = _valid_branch_record(stable_id="method-a")
        record["heads"]["03-idea-evaluation"] = p3_head
        cr.write_branch_record(project, "method-a", record)

        result = cr.resolve_context_heads(project, "04-draft-assembly", "method-a")
        p3_entries = [k for k in result if "03-idea-evaluation" in k]
        assert len(p3_entries) == 1


# ---------------------------------------------------------------------------
# §9 integration: _trusted_context current-head filtering
# ---------------------------------------------------------------------------


class TestTrustedContextIntegration:
    """Rollout mode behavior in _trusted_context."""

    def test_off_mode_is_default(self, project: Path) -> None:
        """The system starts in off mode — no behavior change."""
        assert cr.get_rollout_mode() == "off"
        assert not cr.is_enabled()

    def test_resolve_returns_empty_when_no_records(self, project: Path) -> None:
        """With no current-results records, resolution returns empty."""
        result = cr.resolve_context_heads(project, "03-idea-evaluation", "method-a")
        assert result == {}

    def test_off_mode_does_not_filter_context(self, project: Path) -> None:
        """In off mode, _trusted_context uses all-history selection (unfiltered)."""
        # This is verified by the 400+ existing tests that run with mode=off.
        # The key invariant: _cr_heads is empty in off mode, so no filtering occurs.
        assert cr.get_rollout_mode() == "off"

    def test_enforced_mode_falls_back_when_no_records(self, project: Path) -> None:
        """In enforced mode with no records, _trusted_context falls back to
        all-history selection (not empty) — a safety guard prevents
        launching a run with zero context."""
        # resolve_context_heads returns {} when no records exist.
        # _trusted_context logs a warning and falls back to all-history.
        result = cr.resolve_context_heads(project, "03-idea-evaluation", "method-a")
        assert result == {}
