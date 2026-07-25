"""Read the project's method menu (``ideas/methods/<stable_id>.md``).

The Phase 02 lead publishes one markdown file per retained idea. Each file
carries a YAML frontmatter block with ``stable_id``, ``version``, ``label``,
and ``status`` (``recommended`` | ``viable`` | ``frontier`` | ``retired``).
Method-bound phases (Phase 03/04) let the user pick one of these branches in
the run-start form; the chosen branch freezes the run's exact method identity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

METHOD_MENU_DIR = Path("ideas") / "methods"

VALID_STATUSES = ("recommended", "viable", "frontier", "retired")

_STATUS_RANK = {status: rank for rank, status in enumerate(VALID_STATUSES)}

_REQUIRED_KEYS = ("stable_id", "version", "label", "status")

_FRONTMATTER_DELIMITER = "---"


class BranchNotFound(KeyError):
    """Raised when retiring a branch that has no menu file."""


class BranchAlreadyRetired(ValueError):
    """Raised when retiring a branch that is already retired."""


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str | None]:
    """Return (frontmatter mapping, error). Error is None on success."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        return {}, "file does not start with a '---' frontmatter block"
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            end = index
            break
    if end is None:
        return {}, "frontmatter block is not closed with a second '---'"
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        return {}, f"frontmatter is not valid YAML: {exc}"
    if not isinstance(data, dict):
        return {}, "frontmatter must be a mapping of key: value lines"
    return data, None


def parse_method_file(path: Path, project_dir: Path) -> dict[str, Any]:
    """Parse one menu file into an entry dict with an ``errors`` list."""
    entry: dict[str, Any] = {
        "stable_id": "",
        "version": "",
        "label": "",
        "status": "",
        "path": str(path.relative_to(project_dir)),
        "errors": [],
    }
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        entry["errors"].append(f"file cannot be read: {exc}")
        return entry

    data, error = _parse_frontmatter(text)
    if error is not None:
        entry["errors"].append(error)
        return entry

    for key in _REQUIRED_KEYS:
        value = data.get(key)
        if value is None or not str(value).strip():
            entry["errors"].append(f"frontmatter is missing '{key}'")
        else:
            entry[key] = str(value).strip()

    if entry["stable_id"] and entry["stable_id"] != path.stem:
        entry["errors"].append(
            f"stable_id '{entry['stable_id']}' does not match the filename "
            f"'{path.stem}.md'"
        )
    if entry["status"] and entry["status"] not in VALID_STATUSES:
        entry["errors"].append(
            f"status '{entry['status']}' is not one of "
            + ", ".join(VALID_STATUSES)
        )
    return entry


def load_method_menu(project_dir: str | Path) -> dict[str, Any]:
    """Load the full menu: ``{"entries": [...], "warnings": [...]}``.

    Entries are sorted recommended → viable → frontier → retired, then by
    stable_id. A missing menu folder is an empty menu, not an error.
    """
    project_dir = Path(project_dir).resolve()
    menu_dir = project_dir / METHOD_MENU_DIR
    entries: list[dict[str, Any]] = []
    if menu_dir.is_dir():
        for path in sorted(menu_dir.glob("*.md")):
            entries.append(parse_method_file(path, project_dir))
    entries.sort(
        key=lambda e: (_STATUS_RANK.get(e["status"], len(_STATUS_RANK)), e["stable_id"])
    )

    warnings: list[str] = []
    valid = [e for e in entries if not e["errors"]]
    recommended = [e for e in valid if e["status"] == "recommended"]
    if valid and len(recommended) != 1:
        warnings.append(
            f"The method menu should name exactly one recommended branch; "
            f"found {len(recommended)}."
        )
    seen: set[str] = set()
    for entry in valid:
        if entry["stable_id"] in seen:
            warnings.append(
                f"Duplicate stable_id '{entry['stable_id']}' in the method menu."
            )
        seen.add(entry["stable_id"])
    return {"entries": entries, "warnings": warnings}


def find_selectable_entry(
    project_dir: str | Path, stable_id: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a user-chosen branch for launch.

    Returns (entry, None) when the branch exists, is valid, and is not
    retired; otherwise (None, human-readable reason).
    """
    stable_id = str(stable_id).strip()
    menu = load_method_menu(project_dir)
    for entry in menu["entries"]:
        # Match the parsed stable_id, or the filename stem when the file's
        # frontmatter is broken (so the user hears "invalid", not "missing").
        if stable_id not in {entry["stable_id"], Path(entry["path"]).stem}:
            continue
        if entry["errors"]:
            return None, f"its menu file is invalid: {entry['errors'][0]}"
        if entry["status"] == "retired":
            return None, "it is retired and cannot start new runs"
        return entry, None
    return None, "no method menu file defines this branch"


def retire_branch(project_dir: str | Path, stable_id: str) -> dict[str, Any]:
    """Retire a branch by flipping its frontmatter ``status`` to ``retired``.

    The menu file is rewritten in place; the branch folder and sealed run
    artifacts are never touched. Returns the updated entry dict.

    Raises:
        BranchNotFound: no menu file for ``stable_id``.
        BranchAlreadyRetired: the branch is already retired.
    """
    stable_id = str(stable_id).strip()
    root = Path(project_dir).resolve()
    path = root / METHOD_MENU_DIR / f"{stable_id}.md"
    if not path.is_file():
        raise BranchNotFound(stable_id)
    text = path.read_text(encoding="utf-8")
    data, error = _parse_frontmatter(text)
    if error is not None:
        raise BranchNotFound(f"{stable_id}: {error}")
    if str(data.get("status", "")).strip() == "retired":
        raise BranchAlreadyRetired(stable_id)

    # Rewrite only the status line inside the frontmatter block.
    lines = text.splitlines(keepends=True)
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            end = index
            break
    if end is None:
        raise BranchNotFound(f"{stable_id}: frontmatter not closed")

    replaced = False
    for index in range(1, end):
        stripped = lines[index].strip()
        if stripped.startswith("status:") or stripped.startswith("status :"):
            lines[index] = "status: retired\n"
            replaced = True
            break
    if not replaced:
        # Insert a status line before the closing delimiter.
        lines.insert(end, "status: retired\n")

    path.write_text("".join(lines), encoding="utf-8")
    entry = parse_method_file(path, root)
    return entry
