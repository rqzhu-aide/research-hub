from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from core import web_prerequisites


def test_non_phase_five_report_requires_current_intact_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = {"policy": "current_records", "satisfied": True}
    prerequisite_report = Mock(return_value=report)
    monkeypatch.setattr(
        web_prerequisites.project_state,
        "prerequisite_report",
        prerequisite_report,
    )
    dependencies = {"03-idea-evaluation": ["02-method-development"]}

    result = web_prerequisites.phase_prerequisite_report(
        tmp_path,
        "03-idea-evaluation",
        dependencies,
    )

    assert result is report
    prerequisite_report.assert_called_once_with(
        tmp_path,
        "03-idea-evaluation",
        dependencies,
        current_records=True,
    )


def test_phase_five_report_preserves_exact_completed_run_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = {"policy": "required_completed_runs", "satisfied": True}
    prerequisite_report = Mock(return_value=report)
    monkeypatch.setattr(
        web_prerequisites.project_state,
        "prerequisite_report",
        prerequisite_report,
    )
    dependencies = {"05-review-revision": ["03-idea-evaluation"]}
    required_runs = {"03-idea-evaluation": "theory-ready"}

    result = web_prerequisites.phase_prerequisite_report(
        tmp_path,
        "05-review-revision",
        dependencies,
        required_completed_runs=required_runs,
    )

    assert result is report
    prerequisite_report.assert_called_once_with(
        tmp_path,
        "05-review-revision",
        dependencies,
        required_completed_runs=required_runs,
    )
