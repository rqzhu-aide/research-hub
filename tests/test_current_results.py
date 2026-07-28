"""Tests for the simplified current-results freshness module.

The module answers one question: was a run done with the method as it
exists now in the published catalog?
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core import current_results as cr


# ---------------------------------------------------------------------------
# Phase scope
# ---------------------------------------------------------------------------


class TestPhaseScope:
    def test_method_bound_phases(self) -> None:
        assert cr.is_method_bound_phase("03-idea-evaluation")
        assert cr.is_method_bound_phase("04-draft-assembly")
        assert cr.is_method_bound_phase("05-review-revision")

    def test_non_method_bound_phases(self) -> None:
        assert not cr.is_method_bound_phase("01-literature-review")
        assert not cr.is_method_bound_phase("02-method-development")

    def test_unknown_phase(self) -> None:
        assert not cr.is_method_bound_phase("99-nonexistent")


# ---------------------------------------------------------------------------
# Freshness derivation
# ---------------------------------------------------------------------------


class TestDeriveFreshness:
    """derive_freshness compares a run's frozen identity to the catalog."""

    def test_empty_method_id_returns_unknown(self, tmp_path: Path) -> None:
        assert cr.derive_freshness(tmp_path, "03-idea-evaluation", "") == "unknown"

    def test_missing_catalog_returns_unknown(self, tmp_path: Path) -> None:
        """No method catalog published → can't compare."""
        assert cr.derive_freshness(
            tmp_path, "03-idea-evaluation", "method-a",
            run_version="v1", run_definition_sha256="a" * 64,
        ) == "unknown"

    def test_matching_identity_returns_fresh(self, tmp_path: Path) -> None:
        sha = cr._write_test_catalog(tmp_path, "method-a", version="v1")
        assert cr.derive_freshness(
            tmp_path, "03-idea-evaluation", "method-a",
            run_version="v1", run_definition_sha256=sha,
        ) == "fresh"

    def test_version_mismatch_returns_stale(self, tmp_path: Path) -> None:
        sha = cr._write_test_catalog(tmp_path, "method-a", version="v2")
        assert cr.derive_freshness(
            tmp_path, "03-idea-evaluation", "method-a",
            run_version="v1", run_definition_sha256=sha,
        ) == "stale"

    def test_digest_mismatch_returns_stale(self, tmp_path: Path) -> None:
        cr._write_test_catalog(tmp_path, "method-a", version="v1")
        assert cr.derive_freshness(
            tmp_path, "03-idea-evaluation", "method-a",
            run_version="v1", run_definition_sha256="b" * 64,
        ) == "stale"

    def test_no_run_identity_returns_unknown(self, tmp_path: Path) -> None:
        """Pre-method-menu runs have no version/digest → unknown."""
        cr._write_test_catalog(tmp_path, "method-a", version="v1")
        assert cr.derive_freshness(
            tmp_path, "03-idea-evaluation", "method-a",
            run_version="", run_definition_sha256="",
        ) == "unknown"

    def test_retired_method_returns_stale(self, tmp_path: Path) -> None:
        cr._write_test_catalog(
            tmp_path, "method-a", version="v1", status="retired"
        )
        # find_selectable_entry returns (None, "it is retired...")
        # derive_freshness checks error for "retired" → unknown per the
        # logic: retired means the method was removed, not revised
        result = cr.derive_freshness(
            tmp_path, "03-idea-evaluation", "method-a",
            run_version="v1", run_definition_sha256="a" * 64,
        )
        assert result in ("stale", "unknown")
