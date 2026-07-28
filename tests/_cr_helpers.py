"""Shared fixtures and helpers for current-results test files.

Import via:  from tests._cr_helpers import project, _valid_global_head, ...
"""

from __future__ import annotations

from pathlib import Path

import pytest


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
