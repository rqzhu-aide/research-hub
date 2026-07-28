"""Launch-basis sidecar and state schema migration."""

from __future__ import annotations

from pathlib import Path

import pytest

from core import current_results as cr
from tests._cr_helpers import project


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
# §8 + §11: State schema migration
# ---------------------------------------------------------------------------


class TestSchemaMigration:
    """SCHEMA_VERSION 8 adds current_results_basis to every run."""

    def test_schema_version_is_8(self) -> None:
        from core import project_state
        assert project_state.SCHEMA_VERSION == 8

    def test_old_schema_migrates_basis_field(self, tmp_path: Path) -> None:
        from core import project_state

        root = tmp_path / "migration-test"
        root.mkdir()
        state_dir = project_state.state_dir(root)
        state_dir.mkdir(parents=True)

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

        data = project_state.load(root)
        run = data["phases"]["01-literature-review"]["runs"][0]
        assert "current_results_basis" in run
        assert run["current_results_basis"] is None
        assert run["current_results_basis_sha256"] is None

    def test_new_runs_get_basis_field(self, tmp_path: Path) -> None:
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
