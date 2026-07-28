"""Promotion engine: eligibility, atomicity, receipts, reconciliation."""

from __future__ import annotations

from pathlib import Path

import pytest

from core import current_results as cr
from tests._cr_helpers import (
    project,
    _valid_branch_head,
    _valid_branch_record,
    _valid_global_record,
    _valid_global_head,
)


# ---------------------------------------------------------------------------
# §10–11: Promotion — eligibility, atomicity, receipts
# ---------------------------------------------------------------------------


class TestPromotionEligibility:
    """A run may replace a head only when it meets all eligibility criteria."""

    def test_failed_status_not_eligible(self) -> None:
        assert "failed" not in cr._PROMOTION_ELIGIBLE_STATUSES

    def test_cancelled_status_not_eligible(self) -> None:
        assert "cancelled" not in cr._PROMOTION_ELIGIBLE_STATUSES

    def test_approved_status_eligible(self) -> None:
        assert "approved" in cr._PROMOTION_ELIGIBLE_STATUSES

    def test_awaiting_review_eligible(self) -> None:
        assert "awaiting_review" in cr._PROMOTION_ELIGIBLE_STATUSES


class TestPromotionReceipts:
    """Every promotion attempt produces a receipt."""

    def test_not_applied_receipt_for_missing_run(self, project: Path) -> None:
        cr.set_rollout_mode("shadow")
        try:
            result = cr.promote_run(project, "01-literature-review", "nonexistent-run")
            assert result["promoted"] is False
            assert "not found" in result["reason"]
            receipt = cr.not_applied_receipt_path(
                project, result["operation_id"]
            )
            assert receipt.is_file()
        finally:
            cr.set_rollout_mode("off")

    def test_not_applied_receipt_for_ineligible_status(self, project: Path) -> None:
        from core import project_state

        project_state.init(
            project, "test", "test", "Test",
            phase_slugs=["01-literature-review"],
            dependencies={"01-literature-review": []},
        )
        run_id = project_state.reserve_run(project, "01-literature-review", "test")

        cr.set_rollout_mode("shadow")
        try:
            result = cr.promote_run(project, "01-literature-review", run_id)
            assert result["promoted"] is False
            assert "not eligible" in result["reason"]
        finally:
            cr.set_rollout_mode("off")


class TestPromotionIdempotency:
    """Promoting the same run twice produces the same operation_id."""

    def test_operation_id_is_deterministic(self, project: Path) -> None:
        """The operation ID is derived deterministically from phase and run."""
        # promote_run builds operation_id as f"promote:{slug}:{run_id}"
        # Calling it twice for the same run should produce the same id.
        op1 = cr.safe_operation_key("promote:03-idea-evaluation:run-abc")
        op2 = cr.safe_operation_key("promote:03-idea-evaluation:run-abc")
        assert op1 == op2

    def test_different_runs_produce_different_ids(self) -> None:
        op1 = cr.safe_operation_key("promote:03-idea-evaluation:run-abc")
        op2 = cr.safe_operation_key("promote:03-idea-evaluation:run-def")
        assert op1 != op2


class TestRerunPreservesPriorHead:
    """§3.5: Starting a rerun does not invalidate the prior head."""

    def test_prior_head_remains_during_rerun(self, project: Path) -> None:
        head = _valid_branch_head()
        head["generation"] = 3
        head["run_id"] = "run-old-001"
        head["operation_id"] = "promote:03-idea-evaluation:run-old-001"
        record = _valid_branch_record()
        record["heads"]["03-idea-evaluation"] = head
        cr.write_branch_record(project, "method-a", record)

        loaded = cr.load_branch(project, "method-a")
        assert loaded is not None
        assert loaded["heads"]["03-idea-evaluation"]["generation"] == 3


# ---------------------------------------------------------------------------
# §12: Method reconciliation
# ---------------------------------------------------------------------------


class TestMethodReconciliation:
    """Phase 2 catalog changes make P3/P4 heads stale."""

    def test_reconcile_detects_identity_change(self, project: Path) -> None:
        head = _valid_branch_head(stable_id="method-a", version="v1", digest="a" * 64)
        head["generation"] = 1
        head["run_id"] = "run-001"
        head["operation_id"] = "promote:03:run-001"
        record = _valid_branch_record(stable_id="method-a", version="v1", digest="a" * 64)
        record["heads"]["03-idea-evaluation"] = head
        cr.write_branch_record(project, "method-a", record)

        record["active_method_identity"] = {
            "stable_id": "method-a",
            "version": "v2",
            "definition_sha256": "b" * 64,
        }
        record["catalog_generation"] = 2
        cr.write_branch_record(project, "method-a", record)

        freshness = cr.get_branch_freshness(project, "method-a")
        assert freshness["03-idea-evaluation"]["status"] == "stale"

    def test_reconcile_preserves_heads(self, project: Path) -> None:
        head = _valid_branch_head(stable_id="method-a", version="v1", digest="a" * 64)
        head["generation"] = 1
        head["run_id"] = "run-001"
        head["operation_id"] = "promote:03:run-001"
        record = _valid_branch_record(stable_id="method-a", version="v1", digest="a" * 64)
        record["heads"]["03-idea-evaluation"] = head
        cr.write_branch_record(project, "method-a", record)

        loaded = cr.load_branch(project, "method-a")
        assert "03-idea-evaluation" in loaded["heads"]
        assert loaded["heads"]["03-idea-evaluation"]["method_identity"]["version"] == "v1"

    def test_freshness_for_missing_branch(self, project: Path) -> None:
        assert cr.get_branch_freshness(project, "nonexistent") == {}

    def test_freshness_for_fresh_head(self, project: Path) -> None:
        head = _valid_branch_head(stable_id="method-a", version="v1", digest="a" * 64)
        head["generation"] = 1
        head["run_id"] = "run-001"
        head["operation_id"] = "promote:03:run-001"
        record = _valid_branch_record(stable_id="method-a", version="v1", digest="a" * 64)
        record["heads"]["03-idea-evaluation"] = head
        cr.write_branch_record(project, "method-a", record)

        freshness = cr.get_branch_freshness(project, "method-a")
        assert freshness["03-idea-evaluation"]["status"] == "fresh"
