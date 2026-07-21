from __future__ import annotations

import copy
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest
import yaml

import hub
from scripts import project_state


def _create_windows_directory_junction(link: Path, target: Path) -> None:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            "could not create a Windows directory junction for the test: "
            + (result.stderr or result.stdout).strip()
        )


def _valid_config(workspace: Path) -> dict:
    return {
        "hub": {
            "name": "Test Research Hub",
            "workspace_dir": str(workspace),
            "max_iterations": 10,
        },
        "agents": [
            {
                "id": "research_lead",
                "profile": "lead-profile",
                "name": "Lead",
                "role": "framing",
            },
            {
                "id": "analyst",
                "profile": "analyst-profile",
                "name": "Analyst",
                "role": "analysis",
            },
        ],
        "phases": [
            {
                "slug": "01-discovery",
                "name": "Discovery",
                "description": "Explore the problem",
                "pattern": "parallel",
                "rounds": {"min": 1, "default": 2, "max": 4},
                "gated_by": [],
                "folder": "references/",
                "members": ["research_lead", "analyst"],
            },
            {
                "slug": "02-validation",
                "name": "Validation",
                "description": "Check the proposed result",
                "pattern": "sequential",
                "gated_by": ["01-discovery"],
                "folder": "draft/validation/",
                "members": ["analyst", "research_lead"],
                "stages": [
                    {
                        "role": "analyst",
                        "name": "Build",
                        "description": "Build the validation artifact",
                    },
                    {
                        "role": "research_lead",
                        "name": "Review",
                        "description": "Review the validation artifact",
                    },
                ],
            },
        ],
    }


def _write_app_config(app_root: Path, cfg: dict) -> Path:
    config_path = app_root / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    soul_dir = app_root / "config" / "souls"
    soul_dir.mkdir(parents=True, exist_ok=True)
    for agent in cfg.get("agents", []):
        (soul_dir / f"{agent['id']}.md").write_text(
            f"# {agent['name']} soul\n", encoding="utf-8"
        )
    for phase in cfg.get("phases", []):
        phase_dir = app_root / "config" / "phases" / phase["slug"]
        phase_dir.mkdir(parents=True, exist_ok=True)
        required = ["_lead", "_phase", *phase.get("members", [])]
        for name in required:
            (phase_dir / f"{name}.md").write_text(
                f"# {name}\n", encoding="utf-8"
            )
    return config_path


@pytest.fixture
def configured_hub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    app_root = tmp_path / "app"
    workspace = tmp_path / "workspace"
    app_root.mkdir()
    config_path = _write_app_config(app_root, _valid_config(workspace))
    monkeypatch.setattr(hub, "CONFIG_PATH", config_path)
    return app_root, workspace


def test_clean_workspace_auto_initializes_and_cli_is_idempotent(configured_hub):
    _, workspace = configured_hub

    assert hub.list_projects() == []
    assert hub.main(["init"]) == 0
    assert (workspace / "hub.db").is_file()
    assert (workspace / "projects").is_dir()

    with sqlite3.connect(workspace / "hub.db") as raw:
        tables = {
            row[0]
            for row in raw.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert tables == {"projects", "sqlite_sequence"}

    project_id = hub.create_project(
        "因果推断 Study",
        "Unicode description",
        "Evaluate an estimator.",
    )
    project = dict(hub.get_project(project_id))
    project_dir = hub.get_project_dir(project_id)

    assert project["directory_name"] == project_dir.name
    assert "因果推断-study" in project_dir.name
    for relative in (
        "phase-summaries",
        "references",
        "ideas",
        "draft",
        "draft/validation",
        "numerical",
    ):
        assert (project_dir / relative).is_dir()
    assert project_state.state_dir(project_dir).is_dir()
    assert not project_state.state_dir(project_dir).is_relative_to(project_dir)
    assert "因果推断 Study" in (project_dir / "setting.md").read_text(
        encoding="utf-8"
    )

    with hub.get_db() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5_000
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_project_slug_and_stored_directory_cannot_escape_projects_root(configured_hub):
    _, workspace = configured_hub
    project_id = hub.create_project(
        r"..\..\C:\CON/研究 🚀",
        brief="Traversal-like names must remain safe.",
    )
    project_dir = hub.get_project_dir(project_id)
    projects_root = (workspace / "projects").resolve()

    assert project_dir.resolve().is_relative_to(projects_root)
    assert "研究" in project_dir.name
    assert "\\" not in project_dir.name
    assert "/" not in project_dir.name

    with hub.get_db() as conn:
        conn.execute(
            "UPDATE projects SET directory_name = ? WHERE id = ?",
            (r"..\outside", project_id),
        )
    with pytest.raises(RuntimeError, match="unsafe"):
        hub.get_project_dir(project_id)


@pytest.mark.skipif(os.name == "nt", reason="POSIX symbolic-link behavior")
def test_project_directory_rejects_an_intra_root_symbolic_link(configured_hub) -> None:
    _, workspace = configured_hub
    hub.init_db(verbose=False)
    projects = workspace / "projects"
    target = projects / "project-002-target"
    target.mkdir()
    link = projects / "project-001-alias"
    link.symlink_to(target, target_is_directory=True)
    with hub.get_db() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, directory_name) VALUES (?, ?, ?)",
            (1, "Alias", link.name),
        )

    with pytest.raises(RuntimeError, match="symbolic link or reparse point"):
        hub.get_project_dir(1)


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_project_directory_rejects_an_intra_root_junction(configured_hub) -> None:
    _, workspace = configured_hub
    hub.init_db(verbose=False)
    projects = workspace / "projects"
    target = projects / "project-002-target"
    target.mkdir()
    junction = projects / "project-001-alias"
    _create_windows_directory_junction(junction, target)
    try:
        with hub.get_db() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, directory_name) VALUES (?, ?, ?)",
                (1, "Alias", junction.name),
            )
        with pytest.raises(RuntimeError, match="symbolic link or reparse point"):
            hub.get_project_dir(1)
    finally:
        if junction.exists():
            junction.rmdir()


@pytest.mark.skipif(os.name == "nt", reason="POSIX symbolic-link behavior")
def test_operation_lock_rejects_a_symbolic_link(
    configured_hub,
) -> None:
    app_root, _ = configured_hub
    target = app_root / "unrelated-empty-file"
    target.write_bytes(b"")
    lock_path = hub.CONFIG_PATH.with_suffix(".operations.lock")
    lock_path.symlink_to(target)

    with pytest.raises(RuntimeError, match="hub operation lock is unavailable"):
        with hub.operation_lock():
            pytest.fail("a linked lock file must never be acquired")
    assert target.read_bytes() == b""


def test_directory_failure_rolls_back_project_registry_row(
    configured_hub, monkeypatch: pytest.MonkeyPatch
):
    def fail_tree(*args, **kwargs):
        raise OSError("simulated directory failure")

    monkeypatch.setattr(hub, "_create_project_tree", fail_tree)
    with pytest.raises(OSError, match="simulated"):
        hub.create_project("Cannot be created", brief="Test rollback")
    assert hub.list_projects() == []


def test_preexisting_project_directory_is_never_deleted_on_create_collision(
    configured_hub,
) -> None:
    _, workspace = configured_hub
    hub.init_db(verbose=False)
    collision = workspace / "projects" / "project-001-collision"
    collision.mkdir()
    sentinel = collision / "keep.txt"
    sentinel.write_text("unrelated data", encoding="utf-8")

    with pytest.raises(FileExistsError):
        hub.create_project("Collision", brief="Must not delete an existing folder")

    assert sentinel.read_text(encoding="utf-8") == "unrelated data"
    assert hub.list_projects() == []


def test_existing_database_is_migrated_and_directory_is_discovered(configured_hub):
    _, workspace = configured_hub
    workspace.mkdir()
    projects_root = workspace / "projects"
    projects_root.mkdir()
    legacy_dir = projects_root / "project-001-legacy"
    legacy_dir.mkdir()

    with sqlite3.connect(workspace / "hub.db") as conn:
        conn.execute(
            "CREATE TABLE projects ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO projects (name, created_at) VALUES (?, CURRENT_TIMESTAMP)",
            ("Legacy",),
        )

    hub.init_db(verbose=False)
    with sqlite3.connect(workspace / "hub.db") as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
        }
    assert "directory_name" in columns
    assert "max_iterations" in columns

    assert hub.get_project_dir(1) == legacy_dir
    assert dict(hub.get_project(1))["directory_name"] == "project-001-legacy"


def test_config_validation_covers_rounds_stages_paths_and_gate_dag(configured_hub):
    app_root, _ = configured_hub
    valid = hub.load_config()
    assert valid["phases"][1]["rounds"] == {"min": 2, "default": 2, "max": 2}

    missing_workspace = copy.deepcopy(valid)
    del missing_workspace["hub"]["workspace_dir"]
    with pytest.raises(hub.ConfigurationError, match="workspace_dir"):
        hub.validate_config(missing_workspace, config_root=app_root)

    unsafe_folder = copy.deepcopy(valid)
    unsafe_folder["phases"][0]["folder"] = "../outside"
    with pytest.raises(hub.ConfigurationError, match="stay inside"):
        hub.validate_config(unsafe_folder, config_root=app_root)

    duplicate_folder = copy.deepcopy(valid)
    duplicate_folder["phases"][1]["folder"] = "REFERENCES"
    with pytest.raises(hub.ConfigurationError, match="same output directory"):
        hub.validate_config(duplicate_folder, config_root=app_root)

    missing_rounds = copy.deepcopy(valid)
    del missing_rounds["phases"][0]["rounds"]
    with pytest.raises(hub.ConfigurationError, match="rounds"):
        hub.validate_config(missing_rounds, config_root=app_root)

    shallow_debate = copy.deepcopy(valid)
    shallow_debate["phases"][0]["pattern"] = "debate"
    shallow_debate["phases"][0]["rounds"] = {"min": 1, "default": 2, "max": 3}
    with pytest.raises(hub.ConfigurationError, match="at least 2"):
        hub.validate_config(shallow_debate, config_root=app_root)

    wrong_stage_role = copy.deepcopy(valid)
    wrong_stage_role["phases"][1]["stages"][0]["role"] = "not-a-member"
    with pytest.raises(hub.ConfigurationError, match="listed in phase members"):
        hub.validate_config(wrong_stage_role, config_root=app_root)

    cycle = copy.deepcopy(valid)
    cycle["phases"][0]["gated_by"] = ["02-validation"]
    with pytest.raises(hub.ConfigurationError, match="cycle"):
        hub.validate_config(cycle, config_root=app_root)

    missing_soul = app_root / "config" / "souls" / "analyst.md"
    missing_soul.unlink()
    with pytest.raises(hub.ConfigurationError, match="regular file") as exc_info:
        hub.validate_config(copy.deepcopy(valid), config_root=app_root)
    assert "analyst" in str(exc_info.value)
    assert str(missing_soul) in str(exc_info.value)
    missing_soul.write_text("# Analyst soul\n", encoding="utf-8")

    missing_playbook = (
        app_root
        / "config"
        / "phases"
        / "01-discovery"
        / "research_lead.md"
    )
    missing_playbook.unlink()
    with pytest.raises(hub.ConfigurationError, match="missing required playbooks"):
        hub.validate_config(copy.deepcopy(valid), config_root=app_root)


def test_config_requires_launcher_research_lead(configured_hub):
    app_root, _ = configured_hub
    config = hub.load_config()
    config["agents"][0]["id"] = "lead"

    with pytest.raises(hub.ConfigurationError, match="research_lead"):
        hub.validate_config(config, config_root=app_root)


@pytest.mark.parametrize(
    "profile",
    [
        "Lead-Profile",
        "lead.profile",
        "lead/profile",
        "a" * 65,
        "hermes",
        "test",
        "tmp",
        "root",
        "sudo",
    ],
    ids=[
        "uppercase",
        "dot",
        "slash",
        "too-long",
        "reserved-hermes",
        "reserved-test",
        "reserved-tmp",
        "reserved-root",
        "reserved-sudo",
    ],
)
def test_config_rejects_noncanonical_hermes_profile_names(
    configured_hub, profile: str
):
    app_root, _ = configured_hub
    config = hub.load_config()
    config["agents"][0]["profile"] = profile

    with pytest.raises(hub.ConfigurationError, match="profile"):
        hub.validate_config(config, config_root=app_root)


def test_config_requires_reviewer_to_use_an_independent_profile(configured_hub):
    app_root, _ = configured_hub
    config = hub.load_config()
    config["agents"].append(
        {
            "id": "paper_reviewer",
            "profile": "lead-profile",
            "name": "Outside reviewer",
            "role": "independent review",
        }
    )

    with pytest.raises(hub.ConfigurationError, match="distinct Hermes profile"):
        hub.validate_config(config, config_root=app_root)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"", "non-whitespace text"),
        (b" \n\t", "non-whitespace text"),
        (b"\xff", "valid UTF-8"),
        (b"x" * (hub.MAX_ROLE_SOUL_BYTES + 1), "maximum size"),
    ],
    ids=["empty", "whitespace", "invalid-utf8", "oversized"],
)
def test_config_rejects_invalid_role_soul_content(
    configured_hub, payload: bytes, message: str
):
    app_root, _ = configured_hub
    config = hub.load_config()
    soul_path = app_root / "config" / "souls" / "analyst.md"
    soul_path.write_bytes(payload)

    with pytest.raises(hub.ConfigurationError, match=message) as exc_info:
        hub.validate_config(config, config_root=app_root)
    assert "analyst" in str(exc_info.value)
    assert str(soul_path) in str(exc_info.value)


def test_config_rejects_non_file_role_soul(configured_hub):
    app_root, _ = configured_hub
    config = hub.load_config()
    soul_path = app_root / "config" / "souls" / "analyst.md"
    soul_path.unlink()
    soul_path.mkdir()

    with pytest.raises(hub.ConfigurationError, match="regular file") as exc_info:
        hub.validate_config(config, config_root=app_root)
    assert "analyst" in str(exc_info.value)
    assert str(soul_path) in str(exc_info.value)
