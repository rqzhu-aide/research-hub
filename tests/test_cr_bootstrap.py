"""Bootstrap: non-destructive derived indexing from existing run history."""

from __future__ import annotations

from pathlib import Path

from core import current_results as cr
from tests._cr_helpers import project


class TestBootstrapShadow:
    """Bootstrap computes heads from project state without writing."""

    def test_empty_project_produces_empty_report(self, project: Path) -> None:
        report = cr.bootstrap_project(project, write=False)
        assert report["global_heads"] == {}
        assert report["branch_heads"] == {}
        assert report["written"] is False

    def test_bootstrap_is_idempotent(self, project: Path) -> None:
        r1 = cr.bootstrap_project(project, write=False)
        r2 = cr.bootstrap_project(project, write=False)
        assert r1 == r2

    def test_bootstrap_writes_when_requested(self, project: Path) -> None:
        report = cr.bootstrap_project(project, write=True)
        assert report["written"] is True
        assert not cr.global_record_path(project).exists()


class TestBootstrapValidation:
    """Bootstrap candidates must pass the generalized validator."""

    def test_failed_run_not_eligible(self) -> None:
        assert "failed" not in cr._BOOTSTRAP_ELIGIBLE_STATUSES
        assert "cancelled" not in cr._BOOTSTRAP_ELIGIBLE_STATUSES

    def test_superseded_run_is_eligible(self) -> None:
        assert "superseded" in cr._BOOTSTRAP_ELIGIBLE_STATUSES

    def test_revision_requested_is_eligible(self) -> None:
        assert "revision_requested" in cr._BOOTSTRAP_ELIGIBLE_STATUSES
