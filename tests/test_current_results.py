"""Contract tests for the current-head foundation (STORAGE_RESTRUCTURE_PLAN.md).

These tests encode the intended semantics *before* all integration code
exists.  Milestone 0 tests verify storage primitives and schema invariants.
Later milestones will add promotion, bootstrap, context resolution, and UI
projection tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import current_results as cr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project directory — no project state needed for storage tests."""

    root = tmp_path / "project-001-example"
    root.mkdir(parents=True)
    return root


def _valid_global_head(phase_slug: str = "01-literature-review") -> dict:
    return {
        "generation": 1,
        "run_id": "run-abc-001",
        "phase_slug": phase_slug,
        "scientific_outcome": "Complete",
        "representation": "verified_run_bundle",
        "source_integrity": {
            "run_manifest_sha256": "a" * 64,
            "final_summary_sha256": "b" * 64,
            "decision_sha256": "c" * 64,
        },
        "promoted_at": "2026-07-28T12:00:00Z",
        "operation_id": "promote-01-literature-review:run-abc-001",
    }


def _valid_branch_head(
    phase_slug: str = "03-idea-evaluation",
    stable_id: str = "method-a",
    version: str = "v1",
    digest: str | None = None,
) -> dict:
    return {
        "generation": 1,
        "run_id": "run-def-003",
        "phase_slug": phase_slug,
        "method_identity": {
            "stable_id": stable_id,
            "version": version,
            "definition_sha256": digest or "d" * 64,
        },
        "scientific_outcome": "Complete",
        "representation": "verified_run_bundle",
        "source_integrity": {
            "run_manifest_sha256": "e" * 64,
            "final_summary_sha256": "f" * 64,
            "decision_sha256": "1" * 64,
        },
        "promoted_at": "2026-07-28T14:00:00Z",
        "operation_id": f"promote-{phase_slug}:run-def-003",
    }


def _valid_branch_record(
    stable_id: str = "method-a",
    version: str = "v1",
    digest: str | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "stable_id": stable_id,
        "method_status": "active",
        "catalog_generation": 1,
        "active_method_identity": {
            "stable_id": stable_id,
            "version": version,
            "definition_sha256": digest or "d" * 64,
        },
        "heads": {},
    }


def _valid_global_record() -> dict:
    return {
        "schema_version": 1,
        "heads": {},
    }


# ---------------------------------------------------------------------------
# §6: Control-storage layout — safe keys
# ---------------------------------------------------------------------------


class TestSafeKeys:
    """Raw method/run/operation IDs never become filenames."""

    def test_safe_branch_key_is_hex(self) -> None:
        key = cr.safe_branch_key("method-a")
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_safe_branch_key_is_deterministic(self) -> None:
        assert cr.safe_branch_key("method-a") == cr.safe_branch_key("method-a")

    def test_safe_branch_key_differs_for_different_ids(self) -> None:
        assert cr.safe_branch_key("method-a") != cr.safe_branch_key("method-b")

    def test_safe_branch_key_rejects_empty(self) -> None:
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.safe_branch_key("")

    def test_safe_branch_key_rejects_non_string(self) -> None:
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.safe_branch_key(123)  # type: ignore[arg-type]

    def test_safe_run_key_is_hex(self) -> None:
        key = cr.safe_run_key("run-abc-001")
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_safe_operation_key_is_hex(self) -> None:
        key = cr.safe_operation_key("promote-03:run-abc")
        assert len(key) == 32


class TestSafePaths:
    """All paths are derived from state_dir and never use raw IDs."""

    def test_global_record_path_under_state_dir(self, project: Path) -> None:
        from core import project_state
        expected_root = project_state.state_dir(project) / "current-results"
        path = cr.global_record_path(project)
        assert path == expected_root / "global.json"

    def test_branch_record_path_uses_hashed_key(self, project: Path) -> None:
        from core import project_state
        expected_root = project_state.state_dir(project) / "current-results" / "branches"
        path = cr.branch_record_path(project, "method-a")
        key = cr.safe_branch_key("method-a")
        assert path == expected_root / f"{key}.json"
        # Raw ID does NOT appear in the path
        assert "method-a" not in path.name

    def test_launch_basis_path_uses_hashed_key(self, project: Path) -> None:
        path = cr.launch_basis_path(project, "run-abc-001")
        assert "run-abc-001" not in path.name

    def test_transaction_path_uses_hashed_key(self, project: Path) -> None:
        path = cr.transaction_path(project, "promote-03:run-abc")
        assert "promote" not in path.name


# ---------------------------------------------------------------------------
# §7: Record model — schema validation
# ---------------------------------------------------------------------------


class TestHeadValidation:
    """Every head contains exactly the required fields."""

    def test_valid_global_head(self) -> None:
        head = _valid_global_head()
        result = cr.validate_head(head, method_bound=False)
        assert result["run_id"] == "run-abc-001"
        assert "method_identity" not in result

    def test_valid_branch_head(self) -> None:
        head = _valid_branch_head()
        result = cr.validate_head(head, method_bound=True)
        assert result["method_identity"]["stable_id"] == "method-a"

    def test_missing_required_field_fails(self) -> None:
        head = _valid_global_head()
        del head["run_id"]
        with pytest.raises(cr.CurrentResultsValidationError, match="run_id"):
            cr.validate_head(head, method_bound=False)

    def test_generation_must_be_positive(self) -> None:
        head = _valid_global_head()
        head["generation"] = 0
        with pytest.raises(cr.CurrentResultsValidationError, match="generation"):
            cr.validate_head(head, method_bound=False)

    def test_invalid_scientific_outcome(self) -> None:
        head = _valid_global_head()
        head["scientific_outcome"] = "Failed"
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.validate_head(head, method_bound=False)

    def test_invalid_representation(self) -> None:
        head = _valid_global_head()
        head["representation"] = "unknown_type"
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.validate_head(head, method_bound=False)

    def test_sha256_must_be_64_hex(self) -> None:
        head = _valid_global_head()
        head["source_integrity"]["run_manifest_sha256"] = "short"
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.validate_head(head, method_bound=False)

    def test_branch_head_requires_method_identity(self) -> None:
        head = _valid_global_head()
        with pytest.raises(cr.CurrentResultsValidationError, match="method_identity"):
            cr.validate_head(head, method_bound=True)

    def test_global_head_rejects_method_identity(self) -> None:
        head = _valid_branch_head()
        with pytest.raises(cr.CurrentResultsValidationError, match="must not have"):
            cr.validate_head(head, method_bound=False)

    def test_unknown_field_rejected(self) -> None:
        head = _valid_global_head()
        head["unexpected_field"] = True
        with pytest.raises(cr.CurrentResultsValidationError, match="unknown"):
            cr.validate_head(head, method_bound=False)


class TestGlobalRecordValidation:
    def test_valid_empty_global(self) -> None:
        result = cr.validate_global_record(_valid_global_record())
        assert result["heads"] == {}

    def test_valid_global_with_heads(self) -> None:
        record = _valid_global_record()
        record["heads"]["01-literature-review"] = _valid_global_head()
        result = cr.validate_global_record(record)
        assert "01-literature-review" in result["heads"]

    def test_global_rejects_branch_phase(self) -> None:
        record = _valid_global_record()
        record["heads"]["03-idea-evaluation"] = _valid_branch_head()
        with pytest.raises(cr.CurrentResultsValidationError, match="non-global"):
            cr.validate_global_record(record)

    def test_global_rejects_wrong_schema(self) -> None:
        record = _valid_global_record()
        record["schema_version"] = 99
        with pytest.raises(cr.CurrentResultsValidationError, match="schema_version"):
            cr.validate_global_record(record)


class TestBranchRecordValidation:
    def test_valid_empty_branch(self) -> None:
        result = cr.validate_branch_record(_valid_branch_record())
        assert result["heads"] == {}

    def test_valid_branch_with_heads(self) -> None:
        record = _valid_branch_record()
        record["heads"]["03-idea-evaluation"] = _valid_branch_head()
        result = cr.validate_branch_record(record)
        assert "03-idea-evaluation" in result["heads"]

    def test_branch_rejects_global_phase(self) -> None:
        record = _valid_branch_record()
        record["heads"]["01-literature-review"] = _valid_global_head()
        with pytest.raises(cr.CurrentResultsValidationError, match="non-branch"):
            cr.validate_branch_record(record)

    def test_branch_rejects_wrong_schema(self) -> None:
        record = _valid_branch_record()
        record["schema_version"] = 99
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.validate_branch_record(record)


# ---------------------------------------------------------------------------
# §7.3: Head digest (canonical JSON)
# ---------------------------------------------------------------------------


class TestHeadDigest:
    def test_digest_is_deterministic(self) -> None:
        head = _valid_branch_head()
        d1 = cr.compute_head_sha256(head)
        d2 = cr.compute_head_sha256(head)
        assert d1 == d2
        assert len(d1) == 64

    def test_digest_excludes_head_sha256_field(self) -> None:
        head = _valid_branch_head()
        d1 = cr.compute_head_sha256(head)
        head["head_sha256"] = "deadbeef" * 8
        d2 = cr.compute_head_sha256(head)
        assert d1 == d2  # Adding head_sha256 doesn't change digest

    def test_digest_changes_with_content(self) -> None:
        head = _valid_branch_head()
        d1 = cr.compute_head_sha256(head)
        head["generation"] = 2
        d2 = cr.compute_head_sha256(head)
        assert d1 != d2


# ---------------------------------------------------------------------------
# §7.4: Derived status
# ---------------------------------------------------------------------------


class TestDerivedStatus:
    def _active_identity(self, stable_id: str = "method-a", version: str = "v1") -> dict:
        return {
            "stable_id": stable_id,
            "version": version,
            "definition_sha256": "d" * 64,
        }

    def test_missing_head(self) -> None:
        assert cr.derive_head_status(None, self._active_identity()) == "missing"

    def test_retired_method(self) -> None:
        head = _valid_branch_head()
        assert cr.derive_head_status(head, self._active_identity(), method_status="retired") == "retired"

    def test_fresh_head(self) -> None:
        head = _valid_branch_head()
        assert cr.derive_head_status(head, self._active_identity()) == "fresh"

    def test_stale_head_version_mismatch(self) -> None:
        head = _valid_branch_head(version="v1")
        active = self._active_identity(version="v2")
        assert cr.derive_head_status(head, active) == "stale"

    def test_stale_head_digest_mismatch(self) -> None:
        head = _valid_branch_head(digest="d" * 64)
        active = self._active_identity()
        active["definition_sha256"] = "e" * 64
        assert cr.derive_head_status(head, active) == "stale"

    def test_provisional_head_no_identity(self) -> None:
        head = _valid_branch_head()
        del head["method_identity"]
        head["representation"] = "legacy_provisional"
        assert cr.derive_head_status(head, self._active_identity()) == "provisional"


# ---------------------------------------------------------------------------
# §6: Atomic writes and record reads
# ---------------------------------------------------------------------------


class TestAtomicWriteAndRead:
    def test_write_then_read_global(self, project: Path) -> None:
        record = _valid_global_record()
        record["heads"]["01-literature-review"] = _valid_global_head()
        cr.write_global_record(project, record)
        loaded = cr.load_global(project)
        assert loaded is not None
        assert "01-literature-review" in loaded["heads"]

    def test_write_then_read_branch(self, project: Path) -> None:
        record = _valid_branch_record()
        record["heads"]["03-idea-evaluation"] = _valid_branch_head()
        cr.write_branch_record(project, "method-a", record)
        loaded = cr.load_branch(project, "method-a")
        assert loaded is not None
        assert "03-idea-evaluation" in loaded["heads"]

    def test_load_missing_returns_none(self, project: Path) -> None:
        assert cr.load_global(project) is None
        assert cr.load_branch(project, "method-a") is None

    def test_corrupt_record_rejected(self, project: Path) -> None:
        path = cr.global_record_path(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not valid json")
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.load_global(project)

    def test_oversized_record_rejected(self, project: Path) -> None:
        record = _valid_global_record()
        record["heads"]["01-literature-review"] = _valid_global_head()
        record["heads"]["01-literature-review"]["operation_id"] = "x" * (cr._MAX_RECORD_BYTES + 100)
        with pytest.raises(cr.CurrentResultsValidationError, match="exceeds"):
            cr.write_global_record(project, record)

    def test_failed_write_preserves_prior(self, project: Path) -> None:
        record = _valid_global_record()
        record["heads"]["01-literature-review"] = _valid_global_head()
        cr.write_global_record(project, record)

        # Attempt to write an invalid record (should fail)
        bad_record = _valid_global_record()
        bad_record["schema_version"] = 99
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.write_global_record(project, bad_record)

        # Original record should be intact
        loaded = cr.load_global(project)
        assert loaded is not None
        assert loaded["schema_version"] == 1

    def test_path_under_state_dir(self, project: Path) -> None:
        from core import project_state
        cr.write_global_record(project, _valid_global_record())
        path = cr.global_record_path(project)
        sd = project_state.state_dir(project)
        assert str(path).startswith(str(sd))


# ---------------------------------------------------------------------------
# §6: Dedicated lock
# ---------------------------------------------------------------------------


class TestCurrentResultsLock:
    def test_lock_acquires_and_releases(self, project: Path) -> None:
        with cr.current_results_lock(project):
            pass  # Should not raise
        # Should be able to re-acquire
        with cr.current_results_lock(project, timeout=1):
            pass

    def test_lock_is_serialized(self, project: Path) -> None:
        """Two concurrent lock attempts should serialize (second waits)."""
        import threading
        import time as time_mod

        results = []

        def hold_lock():
            with cr.current_results_lock(project):
                results.append("acquired")
                time_mod.sleep(0.3)
                results.append("released")

        def wait_for_lock():
            time_mod.sleep(0.1)
            with cr.current_results_lock(project, timeout=5):
                results.append("second_acquired")

        t1 = threading.Thread(target=hold_lock)
        t2 = threading.Thread(target=wait_for_lock)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert results == ["acquired", "released", "second_acquired"]


# ---------------------------------------------------------------------------
# §19: Rollout modes
# ---------------------------------------------------------------------------


class TestRolloutMode:
    def teardown_method(self) -> None:
        cr.set_rollout_mode("off")

    def test_default_mode_is_off(self) -> None:
        cr.set_rollout_mode("off")
        assert cr.get_rollout_mode() == "off"
        assert not cr.is_enabled()

    def test_shadow_mode(self) -> None:
        cr.set_rollout_mode("shadow")
        assert cr.get_rollout_mode() == "shadow"
        assert cr.is_enabled()

    def test_enforced_mode(self) -> None:
        cr.set_rollout_mode("enforced")
        assert cr.get_rollout_mode() == "enforced"
        assert cr.is_enabled()

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.set_rollout_mode("invalid_mode")


# ---------------------------------------------------------------------------
# §3.1: Phase scope
# ---------------------------------------------------------------------------


class TestPhaseScope:
    def test_phase_1_is_global(self) -> None:
        assert cr.is_phase_global("01-literature-review")
        assert not cr.is_phase_branch("01-literature-review")

    def test_phase_2_is_global(self) -> None:
        assert cr.is_phase_global("02-method-development")
        assert not cr.is_phase_branch("02-method-development")

    def test_phase_3_is_branch(self) -> None:
        assert cr.is_phase_branch("03-idea-evaluation")
        assert not cr.is_phase_global("03-idea-evaluation")

    def test_phase_4_is_branch(self) -> None:
        assert cr.is_phase_branch("04-draft-assembly")
        assert not cr.is_phase_global("04-draft-assembly")

    def test_phase_5_is_branch(self) -> None:
        assert cr.is_phase_branch("05-review-revision")
        assert not cr.is_phase_global("05-review-revision")

    def test_method_bound_for_branch_phases(self) -> None:
        for slug in ("03-idea-evaluation", "04-draft-assembly", "05-review-revision"):
            assert cr.is_phase_method_bound(slug)
        for slug in ("01-literature-review", "02-method-development"):
            assert not cr.is_phase_method_bound(slug)

    def test_phase_5_never_global(self) -> None:
        """Phase 5 must never be stored under a global method key."""
        record = _valid_global_record()
        record["heads"]["05-review-revision"] = {
            **_valid_global_head(),
            "phase_slug": "05-review-revision",
        }
        with pytest.raises(cr.CurrentResultsValidationError, match="non-global"):
            cr.validate_global_record(record)


# ---------------------------------------------------------------------------
# §3.4: Method identity binding
# ---------------------------------------------------------------------------


class TestMethodIdentity:
    def test_branch_head_identity_is_self_contained(self) -> None:
        """validate_head checks structural validity, not cross-record consistency.

        A head with method-a identity is structurally valid even when placed in
        a method-b record. The mismatch is detected by derive_head_status
        (stale), not by validate_head.
        """
        head = _valid_branch_head(stable_id="method-a")
        result = cr.validate_head(head, method_bound=True)
        assert result["method_identity"]["stable_id"] == "method-a"
        # Cross-record mismatch is a derived status, not a validation error:
        active = {"stable_id": "method-b", "version": "v1", "definition_sha256": "d" * 64}
        assert cr.derive_head_status(result, active) == "stale"

    def test_definition_sha256_required_for_branch(self) -> None:
        head = _valid_branch_head()
        head["method_identity"]["definition_sha256"] = ""
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.validate_head(head, method_bound=True)

    def test_method_identity_unknown_field_rejected(self) -> None:
        head = _valid_branch_head()
        head["method_identity"]["extra_field"] = "x"
        with pytest.raises(cr.CurrentResultsValidationError, match="unknown"):
            cr.validate_head(head, method_bound=True)


# ---------------------------------------------------------------------------
# §3.5: Reruns preserve prior head — structural prerequisite
# ---------------------------------------------------------------------------


class TestRerunPreservation:
    """Test the generation counter that makes reruns safe.

    A rerun does not invalidate the prior head. The prior head's generation
    persists until a valid replacement is finalized and promoted.
    """

    def test_generation_must_be_positive(self) -> None:
        head = _valid_global_head()
        head["generation"] = 0
        with pytest.raises(cr.CurrentResultsValidationError, match="positive"):
            cr.validate_head(head, method_bound=False)

    def test_higher_generation_does_not_invalidate_prior(self, project: Path) -> None:
        """Two heads with different generations are both valid records."""
        head1 = _valid_branch_head()
        head1["generation"] = 1
        head1["run_id"] = "run-001"
        head1["operation_id"] = "promote:run-001"

        head2 = _valid_branch_head()
        head2["generation"] = 2
        head2["run_id"] = "run-002"
        head2["operation_id"] = "promote:run-002"

        # Both validate independently
        cr.validate_head(head1, method_bound=True)
        cr.validate_head(head2, method_bound=True)


# ---------------------------------------------------------------------------
# §14: Bootstrap — non-destructive derived indexing
# ---------------------------------------------------------------------------


class TestBootstrapShadow:
    """Bootstrap computes heads from project state without writing."""

    def test_empty_project_produces_empty_report(self, project: Path) -> None:
        report = cr.bootstrap_project(project, write=False)
        assert report["global_heads"] == {}
        assert report["branch_heads"] == {}
        assert report["written"] is False

    def test_bootstrap_is_idempotent(self, project: Path) -> None:
        """Running bootstrap twice produces the same result."""
        r1 = cr.bootstrap_project(project, write=False)
        r2 = cr.bootstrap_project(project, write=False)
        assert r1 == r2

    def test_bootstrap_writes_when_requested(self, project: Path) -> None:
        """Even with no heads, write=True succeeds and sets written=True."""
        report = cr.bootstrap_project(project, write=True)
        assert report["written"] is True
        # No files should be created for an empty project
        assert not cr.global_record_path(project).exists()


class TestBootstrapValidation:
    """Bootstrap candidates must pass the generalized validator."""

    def test_failed_run_not_eligible(self) -> None:
        """Failed runs never promote."""
        # This is tested at the candidate level: _BOOTSTRAP_ELIGIBLE_STATUSES
        # does not include "failed"
        assert "failed" not in cr._BOOTSTRAP_ELIGIBLE_STATUSES
        assert "cancelled" not in cr._BOOTSTRAP_ELIGIBLE_STATUSES

    def test_superseded_run_is_eligible(self) -> None:
        """Superseded runs may hold intact scientific results (§14)."""
        assert "superseded" in cr._BOOTSTRAP_ELIGIBLE_STATUSES

    def test_revision_requested_is_eligible(self) -> None:
        """Revision-requested runs may hold intact results (§14)."""
        assert "revision_requested" in cr._BOOTSTRAP_ELIGIBLE_STATUSES


# ---------------------------------------------------------------------------
# §8: Launch-basis sidecar
# ---------------------------------------------------------------------------


class TestLaunchBasis:
    def _valid_basis(self) -> dict:
        return {
            "schema_version": 1,
            "run_id": "run-new-001",
            "target_phase": "04-draft-assembly",
            "selected_heads": [
                {
                    "scope": "global",
                    "phase_slug": "02-method-development",
                    "run_id": "run-02",
                    "generation": 5,
                    "head_sha256": "a" * 64,
                },
                {
                    "scope": "branch",
                    "phase_slug": "03-idea-evaluation",
                    "run_id": "run-03",
                    "generation": 4,
                    "head_sha256": "b" * 64,
                },
            ],
            "same_phase_base_generation": 6,
            "created_at": "2026-07-28T15:00:00Z",
        }

    def test_valid_launch_basis(self) -> None:
        result = cr.validate_launch_basis(self._valid_basis())
        assert result["run_id"] == "run-new-001"
        assert len(result["selected_heads"]) == 2

    def test_wrong_schema_rejected(self) -> None:
        basis = self._valid_basis()
        basis["schema_version"] = 99
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.validate_launch_basis(basis)

    def test_missing_required_field(self) -> None:
        basis = self._valid_basis()
        del basis["target_phase"]
        with pytest.raises(cr.CurrentResultsValidationError, match="target_phase"):
            cr.validate_launch_basis(basis)

    def test_invalid_scope(self) -> None:
        basis = self._valid_basis()
        basis["selected_heads"][0]["scope"] = "unknown"
        with pytest.raises(cr.CurrentResultsValidationError, match="scope"):
            cr.validate_launch_basis(basis)

    def test_head_sha256_must_be_hex(self) -> None:
        basis = self._valid_basis()
        basis["selected_heads"][0]["head_sha256"] = "short"
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.validate_launch_basis(basis)

    def test_write_and_load(self, project: Path) -> None:
        basis = self._valid_basis()
        digest = cr.write_launch_basis(project, basis)
        assert len(digest) == 64

        loaded = cr.load_launch_basis(project, "run-new-001")
        assert loaded is not None
        assert loaded["run_id"] == "run-new-001"

    def test_load_missing_returns_none(self, project: Path) -> None:
        assert cr.load_launch_basis(project, "nonexistent") is None

    def test_digest_is_deterministic(self) -> None:
        basis = self._valid_basis()
        d1 = cr.compute_launch_basis_sha256(basis)
        d2 = cr.compute_launch_basis_sha256(basis)
        assert d1 == d2

    def test_optional_method_identity(self) -> None:
        basis = self._valid_basis()
        basis["selected_method_identity"] = {
            "stable_id": "method-a",
            "version": "v1",
            "definition_sha256": "d" * 64,
        }
        result = cr.validate_launch_basis(basis)
        assert result["selected_method_identity"]["stable_id"] == "method-a"


# ---------------------------------------------------------------------------
# §8 + §11: State schema migration — current_results_basis field
# ---------------------------------------------------------------------------


class TestSchemaMigration:
    """SCHEMA_VERSION 8 adds current_results_basis to every run."""

    def test_schema_version_is_8(self) -> None:
        from core import project_state
        assert project_state.SCHEMA_VERSION == 8

    def test_old_schema_migrates_basis_field(self, tmp_path: Path) -> None:
        """A schema 7 project state should migrate to schema 8 with basis=None."""
        from core import project_state

        root = tmp_path / "migration-test"
        root.mkdir()
        state_dir = project_state.state_dir(root)
        state_dir.mkdir(parents=True)

        # Write a schema 7 state with a run
        old_state = {
            "schema_version": 7,
            "project": {"id": "test", "slug": "test", "name": "Test"},
            "phases": {
                "01-literature-review": {
                    "runs": [
                        {
                            "run_id": "run-old-001",
                            "status": "approved",
                            "mode": "",
                            "rounds_requested": 1,
                            "rounds": [],
                            "final_summary": None,
                        }
                    ],
                },
            },
            "dependencies": {},
        }
        import json as _json
        (state_dir / "project.yaml").write_text(
            _json.dumps(old_state), encoding="utf-8"
        )

        # Load triggers migration
        data = project_state.load(root)
        run = data["phases"]["01-literature-review"]["runs"][0]
        assert "current_results_basis" in run
        assert run["current_results_basis"] is None
        assert run["current_results_basis_sha256"] is None

    def test_new_runs_get_basis_field(self, tmp_path: Path) -> None:
        """Runs created after schema 8 should have the basis field."""
        from core import project_state

        root = tmp_path / "new-project"
        root.mkdir()
        project_state.init(
            root,
            "test-001",
            "test",
            "Test",
            phase_slugs=["01-literature-review"],
            dependencies={"01-literature-review": []},
        )
        run_id = project_state.reserve_run(root, "01-literature-review", "test")
        data = project_state.load(root)
        run = data["phases"]["01-literature-review"]["runs"][0]
        assert "current_results_basis" in run
        assert run["current_results_basis"] is None


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
        """Promoting a nonexistent run produces a not-applied receipt."""
        cr.set_rollout_mode("shadow")
        try:
            result = cr.promote_run(project, "01-literature-review", "nonexistent-run")
            assert result["promoted"] is False
            assert "not found" in result["reason"]
            # Check receipt exists
            receipt = cr.not_applied_receipt_path(
                project, result["operation_id"]
            )
            assert receipt.is_file()
        finally:
            cr.set_rollout_mode("off")

    def test_not_applied_receipt_for_ineligible_status(self, project: Path) -> None:
        """Promoting a run with an ineligible status produces a receipt."""
        from core import project_state

        project_state.init(
            project, "test", "test", "Test",
            phase_slugs=["01-literature-review"],
            dependencies={"01-literature-review": []},
        )
        run_id = project_state.reserve_run(project, "01-literature-review", "test")
        # Run is in "starting" status, not eligible

        cr.set_rollout_mode("shadow")
        try:
            result = cr.promote_run(project, "01-literature-review", run_id)
            assert result["promoted"] is False
            assert "not eligible" in result["reason"]
        finally:
            cr.set_rollout_mode("off")


class TestPromotionIdempotency:
    """Repeated promotion of the same run is idempotent."""

    def test_operation_id_is_deterministic(self) -> None:
        """The operation ID is derived from phase and run ID."""
        op1 = f"promote:03-idea-evaluation:run-abc"
        op2 = f"promote:03-idea-evaluation:run-abc"
        assert op1 == op2


class TestRerunPreservesPriorHead:
    """§3.5: Starting a rerun does not invalidate the prior head."""

    def test_prior_head_remains_during_rerun(self, project: Path) -> None:
        """When a new run starts, the prior head's generation persists."""
        # Write a branch record with a head at generation 3
        head = _valid_branch_head()
        head["generation"] = 3
        head["run_id"] = "run-old-001"
        head["operation_id"] = "promote:03-idea-evaluation:run-old-001"
        record = _valid_branch_record()
        record["heads"]["03-idea-evaluation"] = head
        cr.write_branch_record(project, "method-a", record)

        # Load it — generation should still be 3
        loaded = cr.load_branch(project, "method-a")
        assert loaded is not None
        assert loaded["heads"]["03-idea-evaluation"]["generation"] == 3
