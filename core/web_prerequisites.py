"""Apply the prerequisite policy used by the web control surface."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from . import project_state


def phase_prerequisite_report(
    project_dir: str | Path,
    phase_slug: str,
    dependencies: Mapping[str, Sequence[str]],
    *,
    required_completed_runs: Mapping[str, str] | None = None,
    required_method_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate authoritative current records, or Phase 5's exact selected runs."""

    if required_completed_runs is not None:
        exact_policy: dict[str, Any] = {
            "required_completed_runs": required_completed_runs,
        }
        if required_method_id is not None:
            exact_policy["required_method_id"] = required_method_id
        return project_state.prerequisite_report(
            project_dir,
            phase_slug,
            dependencies,
            **exact_policy,
        )
    return project_state.prerequisite_report(
        project_dir,
        phase_slug,
        dependencies,
        current_records=True,
    )
