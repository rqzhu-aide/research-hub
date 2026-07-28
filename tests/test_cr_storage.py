"""Storage primitives: safe keys, paths, validation, digests, locks, rollout mode."""

from __future__ import annotations

from pathlib import Path

import pytest

from core import current_results as cr
from tests._cr_helpers import (
    project,
    _valid_global_head,
    _valid_branch_head,
    _valid_branch_record,
    _valid_global_record,
)


# ---------------------------------------------------------------------------
# §6: Safe keys
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
        assert d1 == d2

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

        bad_record = _valid_global_record()
        bad_record["schema_version"] = 99
        with pytest.raises(cr.CurrentResultsValidationError):
            cr.write_global_record(project, bad_record)

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
            pass
        with cr.current_results_lock(project, timeout=1):
            pass

    def test_lock_is_serialized(self, project: Path) -> None:
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
        head = _valid_branch_head(stable_id="method-a")
        result = cr.validate_head(head, method_bound=True)
        assert result["method_identity"]["stable_id"] == "method-a"
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
# §3.5: Reruns preserve prior head
# ---------------------------------------------------------------------------


class TestRerunPreservation:
    def test_generation_must_be_positive(self) -> None:
        head = _valid_global_head()
        head["generation"] = 0
        with pytest.raises(cr.CurrentResultsValidationError, match="positive"):
            cr.validate_head(head, method_bound=False)

    def test_higher_generation_does_not_invalidate_prior(self, project: Path) -> None:
        head1 = _valid_branch_head()
        head1["generation"] = 1
        head1["run_id"] = "run-001"
        head1["operation_id"] = "promote:run-001"

        head2 = _valid_branch_head()
        head2["generation"] = 2
        head2["run_id"] = "run-002"
        head2["operation_id"] = "promote:run-002"

        cr.validate_head(head1, method_bound=True)
        cr.validate_head(head2, method_bound=True)
