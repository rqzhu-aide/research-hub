from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core import launch_run as launcher


def test_context_snapshot_rejects_more_than_512_copy_records(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / "setting.md").write_text("project", encoding="utf-8")

    team_dir = tmp_path / "team"
    team_dir.mkdir()
    (team_dir / "charter.md").write_text("charter", encoding="utf-8")
    (team_dir / "norms.md").write_text("norms", encoding="utf-8")

    souls_dir = tmp_path / "souls"
    souls_dir.mkdir()
    (souls_dir / "research_lead.md").write_text("lead soul", encoding="utf-8")

    phases_dir = tmp_path / "phases"
    phase_dir = phases_dir / "01-literature-review"
    phase_dir.mkdir(parents=True)
    for name in ("_lead.md", "_phase.md", "research_lead.md"):
        (phase_dir / name).write_text(name, encoding="utf-8")

    source = project / "phase-summaries" / "source.html"
    source.parent.mkdir()
    source.write_text("<p>source</p>", encoding="utf-8")
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    context = [
        {
            "phase": "01-literature-review",
            "run_id": f"history-{index:03d}",
            "summary": source.relative_to(project).as_posix(),
            "sha256": source_digest,
            "kind": "historical_advisory",
            "trusted": False,
            "usable": False,
            "source_status": "superseded",
            "evidence_status": "historical",
            "discussion": [],
            "supporting_artifacts": [],
            "protocol_artifacts": [],
        }
        for index in range(513)
    ]

    monkeypatch.setattr(launcher.launch_common, "TEAM_DIR", team_dir)
    monkeypatch.setattr(launcher.launch_common, "SOULS_DIR", souls_dir)
    monkeypatch.setattr(launcher.launch_common, "PHASES_DIR", phases_dir)

    with pytest.raises(launcher.LaunchError, match="512"):
        launcher._snapshot_run_inputs(
            project,
            {
                "slug": "01-literature-review",
                "members": ["research_lead"],
            },
            "too-many-context-records",
            context,
        )
