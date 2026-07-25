"""Tests for the ideas/methods/ menu parser used for Phase 03 branch selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from core import method_menu


def _write(project_dir: Path, filename: str, body: str) -> Path:
    menu_dir = project_dir / method_menu.METHOD_MENU_DIR
    menu_dir.mkdir(parents=True, exist_ok=True)
    path = menu_dir / filename
    path.write_text(body, encoding="utf-8")
    return path


def _entry(
    stable_id: str,
    *,
    version: str = "v1",
    label: str | None = None,
    status: str = "viable",
) -> str:
    return (
        "---\n"
        f"stable_id: {stable_id}\n"
        f"version: {version}\n"
        f"label: {label or stable_id.replace('-', ' ').title()}\n"
        f"status: {status}\n"
        "---\n\n"
        f"# {label or stable_id}\n\nBody text.\n"
    )


def test_missing_menu_folder_is_an_empty_menu(tmp_path: Path) -> None:
    menu = method_menu.load_method_menu(tmp_path)
    assert menu == {"entries": [], "warnings": []}


def test_entries_are_parsed_and_sorted_by_status(tmp_path: Path) -> None:
    _write(tmp_path, "zebra-frontier.md", _entry("zebra-frontier", status="frontier"))
    _write(tmp_path, "alpha-retired.md", _entry("alpha-retired", status="retired"))
    _write(tmp_path, "main-method.md", _entry("main-method", status="recommended"))
    _write(tmp_path, "beta-viable.md", _entry("beta-viable", status="viable"))

    menu = method_menu.load_method_menu(tmp_path)

    assert [e["stable_id"] for e in menu["entries"]] == [
        "main-method",
        "beta-viable",
        "zebra-frontier",
        "alpha-retired",
    ]
    assert all(not e["errors"] for e in menu["entries"])
    assert menu["entries"][0]["label"] == "Main Method"
    assert menu["warnings"] == []
    assert menu["entries"][0]["path"] == "ideas/methods/main-method.md"


def test_filename_must_match_stable_id(tmp_path: Path) -> None:
    _write(tmp_path, "actual-name.md", _entry("different-name"))

    (entry,) = method_menu.load_method_menu(tmp_path)["entries"]

    assert any("does not match the filename" in e for e in entry["errors"])


def test_invalid_status_is_an_error(tmp_path: Path) -> None:
    _write(tmp_path, "some-method.md", _entry("some-method", status="unknown"))

    (entry,) = method_menu.load_method_menu(tmp_path)["entries"]

    assert any("status 'unknown'" in e for e in entry["errors"])


def test_missing_frontmatter_is_an_error(tmp_path: Path) -> None:
    _write(tmp_path, "no-front.md", "# Just a heading\n\nNo frontmatter here.\n")

    (entry,) = method_menu.load_method_menu(tmp_path)["entries"]

    assert any("frontmatter" in e for e in entry["errors"])


def test_missing_required_keys_are_errors(tmp_path: Path) -> None:
    _write(tmp_path, "sparse.md", "---\nstable_id: sparse\n---\n\n# Sparse\n")

    (entry,) = method_menu.load_method_menu(tmp_path)["entries"]

    assert any("missing 'version'" in e for e in entry["errors"])
    assert any("missing 'label'" in e for e in entry["errors"])
    assert any("missing 'status'" in e for e in entry["errors"])


def test_menu_requires_exactly_one_recommended(tmp_path: Path) -> None:
    _write(tmp_path, "one.md", _entry("one", status="viable"))
    _write(tmp_path, "two.md", _entry("two", status="recommended"))
    _write(tmp_path, "three.md", _entry("three", status="recommended"))

    menu = method_menu.load_method_menu(tmp_path)

    assert any("exactly one recommended" in w for w in menu["warnings"])


def test_find_selectable_entry_resolves_valid_branch(tmp_path: Path) -> None:
    _write(tmp_path, "main-method.md", _entry("main-method", status="recommended"))

    entry, error = method_menu.find_selectable_entry(tmp_path, "main-method")

    assert error is None
    assert entry is not None
    assert entry["stable_id"] == "main-method"
    assert entry["version"] == "v1"


def test_find_selectable_entry_rejects_retired_branch(tmp_path: Path) -> None:
    _write(tmp_path, "old-method.md", _entry("old-method", status="retired"))

    entry, error = method_menu.find_selectable_entry(tmp_path, "old-method")

    assert entry is None
    assert error is not None and "retired" in error


def test_find_selectable_entry_rejects_unknown_and_invalid(tmp_path: Path) -> None:
    _write(tmp_path, "broken.md", "no frontmatter at all")

    entry, error = method_menu.find_selectable_entry(tmp_path, "broken")
    assert entry is None
    assert error is not None and "invalid" in error

    entry, error = method_menu.find_selectable_entry(tmp_path, "ghost")
    assert entry is None
    assert error is not None and "no method menu file" in error


# ---------------------------------------------------------------------------
# Branch retirement (Stage 3c)
# ---------------------------------------------------------------------------

def test_retire_branch_sets_status_to_retired(tmp_path: Path) -> None:
    """Retiring a branch flips its frontmatter status to 'retired'."""
    menu_dir = tmp_path / "ideas" / "methods"
    menu_dir.mkdir(parents=True)
    (menu_dir / "spectral-graph-coupling.md").write_text(
        "---\n"
        "stable_id: spectral-graph-coupling\n"
        "version: v1\n"
        "label: Spectral Graph Coupling\n"
        "status: recommended\n"
        "---\n\n# Spectral Graph Coupling\n",
        encoding="utf-8",
    )

    method_menu.retire_branch(tmp_path, "spectral-graph-coupling")

    menu = method_menu.load_method_menu(tmp_path)
    entry = next(e for e in menu["entries"] if e["stable_id"] == "spectral-graph-coupling")
    assert entry["status"] == "retired"


def test_retire_branch_rejects_unknown_branch(tmp_path: Path) -> None:
    """Retiring a branch that doesn't exist raises an error."""
    menu_dir = tmp_path / "ideas" / "methods"
    menu_dir.mkdir(parents=True)
    with pytest.raises(method_menu.BranchNotFound):
        method_menu.retire_branch(tmp_path, "ghost-branch")


def test_retire_branch_rejects_already_retired(tmp_path: Path) -> None:
    """Retiring an already-retired branch raises an error."""
    menu_dir = tmp_path / "ideas" / "methods"
    menu_dir.mkdir(parents=True)
    (menu_dir / "old-idea.md").write_text(
        "---\n"
        "stable_id: old-idea\n"
        "version: v1\n"
        "label: Old Idea\n"
        "status: retired\n"
        "---\n\n# Old Idea\n",
        encoding="utf-8",
    )
    with pytest.raises(method_menu.BranchAlreadyRetired):
        method_menu.retire_branch(tmp_path, "old-idea")
