"""Validate, stage, publish, and retire Phase 02 method-menu entries.

The published catalog lives in ``ideas/methods``. Phase 02 runs work on an
isolated copy at ``<output_root>/method-menu``. A completed run seals that
copy before it can replace the published catalog.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml
from yaml.constructor import ConstructorError


METHOD_MENU_DIR = Path("ideas") / "methods"
METHOD_REGISTRY_FILENAME = "_registry.yaml"
STAGED_METHOD_MENU_DIRNAME = "method-menu"

METHOD_MENU_SEAL_SCHEMA_VERSION = 1
METHOD_MENU_PROMOTION_SCHEMA_VERSION = 1

VALID_STATUSES = ("recommended", "viable", "frontier", "retired")

_STATUS_RANK = {status: rank for rank, status in enumerate(VALID_STATUSES)}
_FRONTMATTER_DELIMITER = "---"
_MAX_METHOD_FILE_BYTES = 1 * 1024 * 1024
_MAX_REGISTRY_BYTES = 1 * 1024 * 1024
_MAX_CATALOG_BYTES = 20 * 1024 * 1024
_MAX_CATALOG_FILES = 1000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
_BACKUP_PREFIX = ".method-menu-backup-"
_PREPARED_PREFIX = ".method-menu-prepared-"
_DISPLACED_PREFIX = ".method-menu-displaced-"


class MethodMenuError(ValueError):
    """Base class for method-menu validation and transaction failures."""


class MethodMenuValidationError(MethodMenuError):
    """Raised when a catalog or menu entry violates its contract."""


class StaleMethodMenu(MethodMenuError):
    """Raised when submitted form or seal data no longer matches disk."""


class BranchNotFound(KeyError):
    """Raised when retiring a branch that has no menu file."""


class BranchAlreadyRetired(MethodMenuError):
    """Raised when retiring a branch that is already retired."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _yaml_load(text: str, *, label: str) -> Any:
    try:
        return yaml.load(text, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise MethodMenuValidationError(f"{label} is not valid YAML: {exc}") from exc


def _is_link_or_reparse(path: Path) -> bool:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return False
    attributes = int(getattr(details, "st_file_attributes", 0))
    reparse = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    return stat.S_ISLNK(details.st_mode) or bool(reparse and attributes & reparse)


def _project_root(project_dir: str | Path) -> Path:
    root = Path(project_dir).resolve()
    if not root.is_dir():
        raise MethodMenuValidationError(
            f"project directory is not a directory: {root}"
        )
    return root


def _relative_to_root(root: Path, path: Path, *, label: str) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise MethodMenuValidationError(
            f"{label} resolves outside the project directory"
        ) from exc


def _safe_project_path(
    root: Path,
    value: str | Path,
    *,
    label: str,
) -> Path:
    supplied = Path(value)
    lexical = supplied if supplied.is_absolute() else root / supplied
    lexical = Path(os.path.abspath(lexical))
    try:
        relative = lexical.relative_to(root)
    except ValueError as exc:
        raise MethodMenuValidationError(
            f"{label} is outside the project directory"
        ) from exc

    current = root
    for part in relative.parts:
        current = current / part
        try:
            current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise MethodMenuValidationError(
                f"{label} cannot be inspected: {exc}"
            ) from exc
        if _is_link_or_reparse(current):
            raise MethodMenuValidationError(
                f"{label} must not contain a symbolic link or junction: {current}"
            )

    resolved = lexical.resolve(strict=False)
    _relative_to_root(root, resolved, label=label)
    return resolved


def _guard_regular_file(path: Path, *, label: str) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError as exc:
        raise MethodMenuValidationError(f"{label} cannot be inspected: {exc}") from exc
    if _is_link_or_reparse(path) or not stat.S_ISREG(details.st_mode):
        raise MethodMenuValidationError(
            f"{label} must be a regular file, not a link or junction"
        )
    return details


def _read_bounded_bytes(path: Path, *, maximum: int, label: str) -> bytes:
    details = _guard_regular_file(path, label=label)
    if details.st_size > maximum:
        raise MethodMenuValidationError(
            f"{label} exceeds the {maximum}-byte limit"
        )
    try:
        with path.open("rb") as handle:
            value = handle.read(maximum + 1)
    except OSError as exc:
        raise MethodMenuValidationError(f"{label} cannot be read: {exc}") from exc
    if len(value) > maximum:
        raise MethodMenuValidationError(
            f"{label} exceeds the {maximum}-byte limit"
        )
    return value


def _read_bounded_utf8(path: Path, *, maximum: int, label: str) -> tuple[str, bytes]:
    raw = _read_bounded_bytes(path, maximum=maximum, label=label)
    try:
        return raw.decode("utf-8"), raw
    except UnicodeDecodeError as exc:
        raise MethodMenuValidationError(f"{label} is not valid UTF-8") from exc


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _digest_bytes(encoded)


def _validate_stable_id(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set, bool)) or value is None:
        raise MethodMenuValidationError("frontmatter 'stable_id' must be text")
    normalized = str(value).strip()
    if not _STABLE_ID_RE.fullmatch(normalized):
        raise MethodMenuValidationError(
            "frontmatter 'stable_id' must contain at most 200 ASCII letters, "
            "digits, hyphens, underscores, or periods, and start with a letter "
            "or digit"
        )
    return normalized


def _validate_version(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set, bool)) or value is None:
        raise MethodMenuValidationError("frontmatter 'version' must be text")
    normalized = str(value).strip()
    if not _IDENTITY_RE.fullmatch(normalized):
        raise MethodMenuValidationError(
            "frontmatter 'version' must contain at most 200 ASCII letters, "
            "digits, hyphens, underscores, periods, or slashes"
        )
    return normalized


def _positive_integer(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise MethodMenuValidationError(f"{label} must be a positive integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip().isdigit():
        result = int(value.strip())
    else:
        raise MethodMenuValidationError(f"{label} must be a positive integer")
    if result <= 0:
        raise MethodMenuValidationError(f"{label} must be a positive integer")
    return result


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise MethodMenuValidationError(
            "file does not start with a '---' frontmatter block"
        )
    end = next(
        (
            index
            for index in range(1, len(lines))
            if lines[index].strip() == _FRONTMATTER_DELIMITER
        ),
        None,
    )
    if end is None:
        raise MethodMenuValidationError(
            "frontmatter block is not closed with a second '---'"
        )
    data = _yaml_load("\n".join(lines[1:end]), label="frontmatter")
    if not isinstance(data, dict):
        raise MethodMenuValidationError(
            "frontmatter must be a mapping of key: value lines"
        )
    return data, "\n".join(lines[end + 1 :]).strip()


def _empty_entry(path: Path, root: Path) -> dict[str, Any]:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = path.name
    return {
        "stable_id": "",
        "version": "",
        "label": "",
        "status": "",
        "number": None,
        "body": "",
        "path": relative,
        "sha256": "",
        "errors": [],
    }


def _parse_method_path(path: Path, root: Path) -> dict[str, Any]:
    entry = _empty_entry(path, root)
    try:
        text, raw = _read_bounded_utf8(
            path,
            maximum=_MAX_METHOD_FILE_BYTES,
            label=f"method file {path.name!r}",
        )
        entry["sha256"] = _digest_bytes(raw)
        data, body = _parse_frontmatter(text)
        entry["body"] = body
        if not body:
            entry["errors"].append("method body must be nonempty")

        try:
            entry["stable_id"] = _validate_stable_id(data.get("stable_id"))
        except MethodMenuValidationError as exc:
            entry["errors"].append(str(exc))
        try:
            entry["version"] = _validate_version(data.get("version"))
        except MethodMenuValidationError as exc:
            entry["errors"].append(str(exc))

        label = data.get("label")
        if not isinstance(label, str) or not label.strip():
            entry["errors"].append("frontmatter 'label' must be nonempty text")
        else:
            entry["label"] = label.strip()

        status_value = data.get("status")
        status = status_value.strip() if isinstance(status_value, str) else ""
        if status not in VALID_STATUSES:
            entry["errors"].append(
                "frontmatter 'status' must be one of "
                + ", ".join(VALID_STATUSES)
            )
        else:
            entry["status"] = status

        try:
            entry["number"] = _positive_integer(
                data.get("number"),
                label="frontmatter 'number'",
            )
        except MethodMenuValidationError as exc:
            entry["errors"].append(str(exc))

        if entry["stable_id"] and entry["stable_id"] != path.stem:
            entry["errors"].append(
                f"stable_id '{entry['stable_id']}' does not match the filename "
                f"'{path.stem}.md'"
            )
    except (OSError, MethodMenuValidationError) as exc:
        entry["errors"].append(str(exc))
    return entry


def parse_method_file(path: Path, project_dir: Path) -> dict[str, Any]:
    """Parse one published method file into a display-safe entry record."""

    try:
        root = _project_root(project_dir)
        menu_dir = _safe_project_path(
            root,
            METHOD_MENU_DIR,
            label="method-menu directory",
        )
        candidate = _safe_project_path(root, path, label="method file")
        if candidate.parent != menu_dir:
            raise MethodMenuValidationError(
                "method file is not directly inside the method-menu directory"
            )
        return _parse_method_path(candidate, root)
    except (OSError, MethodMenuValidationError) as exc:
        fallback_root = Path(project_dir).resolve()
        fallback_path = Path(path)
        entry = _empty_entry(fallback_path, fallback_root)
        entry["errors"].append(str(exc))
        return entry


def _add_cross_entry_errors(
    entries: list[dict[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    by_id: dict[str, list[dict[str, Any]]] = {}
    by_number: dict[int, list[dict[str, Any]]] = {}
    for entry in entries:
        stable_id = str(entry.get("stable_id", ""))
        number = entry.get("number")
        if stable_id:
            by_id.setdefault(stable_id, []).append(entry)
        if isinstance(number, int):
            by_number.setdefault(number, []).append(entry)
    for stable_id, matches in by_id.items():
        if len(matches) > 1:
            message = f"duplicate stable_id {stable_id!r} in the method menu"
            warnings.append(message)
            for entry in matches:
                entry["errors"].append(message)
    for number, matches in by_number.items():
        if len(matches) > 1:
            message = f"duplicate method number {number} in the method menu"
            warnings.append(message)
            for entry in matches:
                entry["errors"].append(message)
    return warnings


def _load_registry(path: Path) -> dict[str, Any]:
    text, _ = _read_bounded_utf8(
        path,
        maximum=_MAX_REGISTRY_BYTES,
        label="method registry",
    )
    registry = _yaml_load(text, label="method registry")
    if not isinstance(registry, dict):
        raise MethodMenuValidationError("method registry must be a mapping")
    if set(registry).difference({"next_number", "entries"}):
        extras = ", ".join(
            sorted(str(key) for key in set(registry).difference({"next_number", "entries"}))
        )
        raise MethodMenuValidationError(
            f"method registry contains unsupported top-level fields: {extras}"
        )
    next_number = _positive_integer(
        registry.get("next_number"),
        label="method registry 'next_number'",
    )
    rows = registry.get("entries")
    if not isinstance(rows, list):
        raise MethodMenuValidationError("method registry 'entries' must be a list")

    normalized_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_numbers: set[int] = set()
    for index, row in enumerate(rows, start=1):
        label = f"method registry entry {index}"
        if not isinstance(row, dict):
            raise MethodMenuValidationError(f"{label} must be a mapping")
        stable_id = _validate_stable_id(row.get("stable_id"))
        number = _positive_integer(row.get("number"), label=f"{label} 'number'")
        display_label = row.get("label")
        if not isinstance(display_label, str) or not display_label.strip():
            raise MethodMenuValidationError(f"{label} 'label' must be nonempty text")
        status_value = row.get("status")
        status = status_value.strip() if isinstance(status_value, str) else ""
        if status not in VALID_STATUSES:
            raise MethodMenuValidationError(
                f"{label} 'status' must be one of " + ", ".join(VALID_STATUSES)
            )
        if stable_id in seen_ids:
            raise MethodMenuValidationError(
                f"method registry contains duplicate stable_id {stable_id!r}"
            )
        if number in seen_numbers:
            raise MethodMenuValidationError(
                f"method registry contains duplicate method number {number}"
            )
        seen_ids.add(stable_id)
        seen_numbers.add(number)
        normalized = dict(row)
        normalized.update(
            {
                "stable_id": stable_id,
                "number": number,
                "label": display_label.strip(),
                "status": status,
            }
        )
        normalized_rows.append(normalized)
    if seen_numbers and next_number <= max(seen_numbers):
        raise MethodMenuValidationError(
            "method registry 'next_number' must be greater than every assigned number"
        )
    return {
        **registry,
        "next_number": next_number,
        "entries": normalized_rows,
    }


def _reconcile_registry(
    entries: list[dict[str, Any]],
    registry: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    method_by_id = {
        str(entry["stable_id"]): entry
        for entry in entries
        if str(entry.get("stable_id", ""))
    }
    registry_by_id = {
        str(row["stable_id"]): row
        for row in registry.get("entries", [])
        if isinstance(row, Mapping)
    }
    for stable_id, entry in method_by_id.items():
        row = registry_by_id.get(stable_id)
        if row is None:
            message = f"method registry has no entry for stable_id {stable_id!r}"
            entry["errors"].append(message)
            warnings.append(message)
            continue
        comparisons = (
            ("number", entry.get("number"), row.get("number")),
            ("label", entry.get("label"), row.get("label")),
            ("status", entry.get("status"), row.get("status")),
        )
        for field, method_value, registry_value in comparisons:
            if method_value != registry_value:
                message = (
                    f"method registry {field} for {stable_id!r} does not match "
                    "its method file"
                )
                entry["errors"].append(message)
                warnings.append(message)
    for stable_id in sorted(set(registry_by_id).difference(method_by_id)):
        warnings.append(
            f"method registry entry {stable_id!r} has no corresponding method file"
        )
    return warnings


def _load_menu_directory(
    root: Path,
    menu_dir: Path,
    *,
    require_registry: bool,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not menu_dir.exists():
        if require_registry:
            warnings.append("method-menu directory does not exist")
        return {"entries": entries, "warnings": warnings, "registry": None}
    if _is_link_or_reparse(menu_dir) or not menu_dir.is_dir():
        warnings.append(
            "method-menu directory must be a regular directory, not a link or junction"
        )
        return {"entries": entries, "warnings": warnings, "registry": None}

    try:
        children = sorted(menu_dir.iterdir(), key=lambda item: item.name)
    except OSError as exc:
        warnings.append(f"method-menu directory cannot be read: {exc}")
        return {"entries": entries, "warnings": warnings, "registry": None}

    for child in children:
        if child.suffix.lower() != ".md":
            continue
        entries.append(_parse_method_path(child, root))
    warnings.extend(_add_cross_entry_errors(entries))

    registry_path = menu_dir / METHOD_REGISTRY_FILENAME
    registry: dict[str, Any] | None = None
    if registry_path.exists() or _is_link_or_reparse(registry_path):
        try:
            registry = _load_registry(registry_path)
        except (OSError, MethodMenuValidationError) as exc:
            warnings.append(str(exc))
        else:
            warnings.extend(_reconcile_registry(entries, registry))
    elif require_registry:
        warnings.append(
            f"method-menu directory is missing {METHOD_REGISTRY_FILENAME}"
        )

    entries.sort(
        key=lambda entry: (
            _STATUS_RANK.get(str(entry.get("status", "")), len(_STATUS_RANK)),
            entry.get("number") if isinstance(entry.get("number"), int) else 2**31,
            str(entry.get("stable_id", "")),
            str(entry.get("path", "")),
        )
    )
    return {"entries": entries, "warnings": warnings, "registry": registry}


def catalog_version(project_dir: str | Path) -> str:
    """Return a digest of every file in the published method catalog."""

    root = _project_root(project_dir)
    menu_dir = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="method-menu directory",
    )
    return _catalog_digest(_catalog_file_records(menu_dir))


def load_method_menu(project_dir: str | Path) -> dict[str, Any]:
    """Load the published menu without crashing the Web UI on invalid rows."""

    try:
        root = _project_root(project_dir)
        menu_dir = _safe_project_path(
            root,
            METHOD_MENU_DIR,
            label="method-menu directory",
        )
    except (OSError, MethodMenuValidationError) as exc:
        return {"entries": [], "warnings": [str(exc)]}
    result = _load_menu_directory(root, menu_dir, require_registry=False)
    return {
        "entries": result["entries"],
        "warnings": result["warnings"],
    }


def find_selectable_entry(
    project_dir: str | Path,
    stable_id: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a valid, non-retired branch for a method-bound launch."""

    requested = str(stable_id).strip()
    menu = load_method_menu(project_dir)
    for entry in menu["entries"]:
        if requested not in {
            str(entry.get("stable_id", "")),
            Path(str(entry.get("path", ""))).stem,
        }:
            continue
        if entry["errors"]:
            return None, f"its menu file is invalid: {entry['errors'][0]}"
        if menu["warnings"]:
            return None, f"the method menu is invalid: {menu['warnings'][0]}"
        if entry["status"] == "retired":
            return None, "it is retired and cannot start new runs"
        return entry, None
    if menu["warnings"]:
        return None, f"the method menu is invalid: {menu['warnings'][0]}"
    return None, "no method menu file defines this branch"


def _allowed_catalog_child(path: Path) -> bool:
    return path.name == METHOD_REGISTRY_FILENAME or path.suffix.lower() == ".md"


def _catalog_file_records(menu_dir: Path) -> list[dict[str, Any]]:
    if not menu_dir.exists():
        return []
    if _is_link_or_reparse(menu_dir) or not menu_dir.is_dir():
        raise MethodMenuValidationError(
            "method-menu directory must be a regular directory, not a link or junction"
        )
    children = sorted(menu_dir.iterdir(), key=lambda item: item.name)
    if len(children) > _MAX_CATALOG_FILES:
        raise MethodMenuValidationError(
            f"method menu contains more than {_MAX_CATALOG_FILES} files"
        )
    records: list[dict[str, Any]] = []
    total = 0
    for child in children:
        if not _allowed_catalog_child(child):
            raise MethodMenuValidationError(
                f"method menu contains unsupported item {child.name!r}"
            )
        maximum = (
            _MAX_REGISTRY_BYTES
            if child.name == METHOD_REGISTRY_FILENAME
            else _MAX_METHOD_FILE_BYTES
        )
        raw = _read_bounded_bytes(
            child,
            maximum=maximum,
            label=f"method-menu file {child.name!r}",
        )
        total += len(raw)
        if total > _MAX_CATALOG_BYTES:
            raise MethodMenuValidationError(
                f"method menu exceeds the {_MAX_CATALOG_BYTES}-byte total limit"
            )
        records.append(
            {
                "path": child.name,
                "sha256": _digest_bytes(raw),
                "size": len(raw),
            }
        )
    return records


def _catalog_digest(files: list[dict[str, Any]]) -> str:
    return _canonical_digest(files)


def _raise_invalid_menu(menu: Mapping[str, Any]) -> None:
    warnings = menu.get("warnings")
    if isinstance(warnings, list) and warnings:
        raise MethodMenuValidationError(str(warnings[0]))
    entries = menu.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, Mapping) and entry.get("errors"):
                errors = entry["errors"]
                first = errors[0] if isinstance(errors, list) else errors
                raise MethodMenuValidationError(
                    f"method file {entry.get('path', '')!r} is invalid: {first}"
                )


def _entry_snapshot(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stable_id": str(entry.get("stable_id", "")),
        "number": entry.get("number"),
        "version": str(entry.get("version", "")),
        "label": str(entry.get("label", "")),
        "status": str(entry.get("status", "")),
        "sha256": str(entry.get("sha256", "")),
    }


def _valid_published_numbers(
    root: Path,
    menu_dir: Path,
) -> dict[str, int]:
    """Return stable numbers only for individually valid published entries."""

    if not menu_dir.exists():
        return {}
    menu = _load_menu_directory(root, menu_dir, require_registry=False)
    return {
        str(entry["stable_id"]): int(entry["number"])
        for entry in menu["entries"]
        if not entry.get("errors")
        and str(entry.get("stable_id", "")).strip()
        and isinstance(entry.get("number"), int)
    }


def _require_preserved_published_methods(
    published_numbers: Mapping[str, int],
    staged_entries: list[Mapping[str, Any]],
) -> None:
    """Require retirement rather than deletion and preserve stable numbers."""

    staged_by_id = {
        str(entry.get("stable_id", "")): entry
        for entry in staged_entries
        if str(entry.get("stable_id", ""))
    }
    for stable_id, number in sorted(published_numbers.items()):
        staged = staged_by_id.get(stable_id)
        if staged is None:
            raise MethodMenuValidationError(
                f"staged method menu removes published method {stable_id!r}; "
                "retain the entry and set status to 'retired' instead"
            )
        if staged.get("number") != number:
            raise MethodMenuValidationError(
                f"staged method menu changes the permanent number for "
                f"{stable_id!r}; keep method number {number}"
            )


def _published_baseline_from_seal(
    seal: Mapping[str, Any],
) -> tuple[bool, list[dict[str, Any]], str | None]:
    exists = seal.get("published_exists")
    files = seal.get("published_files")
    digest = seal.get("published_catalog_sha256")
    if not isinstance(exists, bool) or not isinstance(files, list):
        raise StaleMethodMenu("method-menu seal has no valid published baseline")
    if exists:
        if not isinstance(digest, str) or digest != _catalog_digest(files):
            raise StaleMethodMenu("method-menu seal has no valid published baseline")
    elif files != [] or digest is not None:
        raise StaleMethodMenu("method-menu seal has no valid published baseline")
    return exists, files, digest


def _seal_directory(
    root: Path,
    menu_dir: Path,
    *,
    require_registry: bool,
) -> dict[str, Any]:
    files = _catalog_file_records(menu_dir)
    menu = _load_menu_directory(
        root,
        menu_dir,
        require_registry=require_registry,
    )
    _raise_invalid_menu(menu)
    return {
        "schema_version": METHOD_MENU_SEAL_SCHEMA_VERSION,
        "kind": "method_menu",
        "staged_path": _relative_to_root(
            root,
            menu_dir,
            label="staged method-menu directory",
        ),
        "files": files,
        "catalog_sha256": _catalog_digest(files),
        "entries": [
            _entry_snapshot(entry)
            for entry in sorted(
                menu["entries"],
                key=lambda value: str(value.get("stable_id", "")),
            )
        ],
    }


def _same_json(left: Any, right: Any) -> bool:
    try:
        left_text = json.dumps(left, sort_keys=True, separators=(",", ":"))
        right_text = json.dumps(right, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(left_text, right_text)


def _staging_directory(root: Path, output_root: str | Path) -> tuple[Path, Path]:
    output = _safe_project_path(root, output_root, label="run output directory")
    if output.exists() and not output.is_dir():
        raise MethodMenuValidationError("run output path is not a directory")
    output.mkdir(parents=True, exist_ok=True)
    output = _safe_project_path(root, output, label="run output directory")
    staged = _safe_project_path(
        root,
        output / STAGED_METHOD_MENU_DIRNAME,
        label="staged method-menu directory",
    )
    return output, staged


def _copy_catalog(source: Path, destination: Path) -> None:
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise MethodMenuValidationError(
                "catalog copy destination must be an empty directory"
            )
    else:
        destination.mkdir(parents=False, exist_ok=False)
    if not source.exists():
        return
    records = _catalog_file_records(source)
    for record in records:
        name = str(record["path"])
        raw = _read_bounded_bytes(
            source / name,
            maximum=(
                _MAX_REGISTRY_BYTES
                if name == METHOD_REGISTRY_FILENAME
                else _MAX_METHOD_FILE_BYTES
            ),
            label=f"method-menu file {name!r}",
        )
        (destination / name).write_bytes(raw)


def _registry_for_entries(entries: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for entry in sorted(
        entries,
        key=lambda value: (
            value.get("number") if isinstance(value.get("number"), int) else 2**31,
            str(value.get("stable_id", "")),
        ),
    ):
        if entry.get("errors"):
            continue
        rows.append(
            {
                "number": entry["number"],
                "stable_id": entry["stable_id"],
                "label": entry["label"],
                "status": entry["status"],
                "added_in_run": "imported",
            }
        )
    numbers = [int(row["number"]) for row in rows]
    return {
        "next_number": max(numbers, default=0) + 1,
        "entries": rows,
    }


def _remove_regular_tree(path: Path) -> None:
    if not path.exists():
        return
    if _is_link_or_reparse(path) or not path.is_dir():
        raise MethodMenuValidationError(
            f"refusing to remove non-directory or linked path: {path}"
        )
    shutil.rmtree(path)


def _replace_directory(prepared: Path, destination: Path) -> None:
    backup: Path | None = None
    if destination.exists():
        backup = destination.parent / f"{_DISPLACED_PREFIX}{uuid.uuid4().hex}"
        os.replace(destination, backup)
    try:
        os.replace(prepared, destination)
    except BaseException:
        if backup is not None:
            os.replace(backup, destination)
        raise
    if backup is not None:
        _remove_regular_tree(backup)


def stage_method_menu(
    project_dir: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """Seed ``<output_root>/method-menu`` from the current published menu."""

    root = _project_root(project_dir)
    source = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="published method-menu directory",
    )
    output, staged = _staging_directory(root, output_root)
    prepared: Path | None = Path(
        tempfile.mkdtemp(prefix=_PREPARED_PREFIX, dir=str(output))
    )
    try:
        _copy_catalog(source, prepared)
        registry_path = prepared / METHOD_REGISTRY_FILENAME
        if not registry_path.exists():
            seeded = _load_menu_directory(
                root,
                prepared,
                require_registry=False,
            )
            registry_path.write_text(
                yaml.safe_dump(
                    _registry_for_entries(seeded["entries"]),
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
                newline="",
            )
        _replace_directory(prepared, staged)
        prepared = None
    finally:
        if prepared is not None and prepared.exists():
            _remove_regular_tree(prepared)

    files = _catalog_file_records(staged)
    staged_menu = _load_menu_directory(root, staged, require_registry=True)
    warnings = list(staged_menu["warnings"])
    for entry in staged_menu["entries"]:
        warnings.extend(
            f"{entry['path']}: {error}" for error in entry.get("errors", [])
        )
    return {
        "schema_version": 1,
        "kind": "method_menu_stage",
        "path": _relative_to_root(root, staged, label="staged method-menu directory"),
        "staged_path": _relative_to_root(
            root,
            staged,
            label="staged method-menu directory",
        ),
        "source_files": files,
        "source_catalog_sha256": _catalog_digest(files),
        "warnings": warnings,
    }


def seal_staged_menu(
    project_dir: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    """Validate and seal the exact run-local method-menu bytes."""

    root = _project_root(project_dir)
    _, staged = _staging_directory(root, output_root)
    staged_seal = _seal_directory(root, staged, require_registry=True)
    published = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="published method-menu directory",
    )
    published_exists = published.exists()
    published_files = _catalog_file_records(published)
    published_digest = (
        _catalog_digest(published_files) if published_exists else None
    )
    _require_preserved_published_methods(
        _valid_published_numbers(root, published),
        staged_seal["entries"],
    )
    staged_seal.update(
        {
            "published_exists": published_exists,
            "published_files": published_files,
            "published_catalog_sha256": published_digest,
        }
    )
    return staged_seal


def verify_staged_menu_seal(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute a staged seal and reject any change after submission."""

    if not isinstance(seal, Mapping):
        raise MethodMenuValidationError("method-menu seal must be a mapping")
    root = _project_root(project_dir)
    _, staged = _staging_directory(root, output_root)
    expected_path = _relative_to_root(
        root,
        staged,
        label="staged method-menu directory",
    )
    if (
        seal.get("schema_version") != METHOD_MENU_SEAL_SCHEMA_VERSION
        or seal.get("kind") != "method_menu"
        or seal.get("staged_path") != expected_path
    ):
        raise StaleMethodMenu("method-menu seal identity is invalid or stale")
    _published_baseline_from_seal(seal)
    current = _seal_directory(root, staged, require_registry=True)
    for field in ("files", "catalog_sha256", "entries"):
        if not _same_json(seal.get(field), current[field]):
            raise StaleMethodMenu(
                "staged method menu changed after it was submitted"
            )
    return current


def _menu_snapshots(
    root: Path,
    menu_dir: Path,
) -> dict[str, dict[str, Any]]:
    if not menu_dir.exists():
        return {}
    menu = _load_menu_directory(root, menu_dir, require_registry=False)
    snapshots: dict[str, dict[str, Any]] = {}
    for entry in menu["entries"]:
        stable_id = str(entry.get("stable_id", "")).strip()
        if not stable_id:
            stable_id = Path(str(entry.get("path", ""))).stem
        snapshots[stable_id] = _entry_snapshot(entry)
    return snapshots


def _menu_changes(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    identifiers = sorted(set(before).union(after))
    changes: list[dict[str, Any]] = []
    for stable_id in identifiers:
        old = before.get(stable_id)
        new = after.get(stable_id)
        if _same_json(old, new):
            continue
        if old is None:
            kind = "added"
        elif new is None:
            kind = "removed"
        else:
            kind = "updated"
        changes.append(
            {
                "stable_id": stable_id,
                "change": kind,
                "before": dict(old) if old is not None else None,
                "after": dict(new) if new is not None else None,
            }
        )
    return [change["stable_id"] for change in changes], changes


def _copy_sealed_catalog(
    staged: Path,
    prepared: Path,
    files: list[Mapping[str, Any]],
) -> None:
    prepared.mkdir(parents=False, exist_ok=False)
    for record in files:
        name = str(record.get("path", ""))
        if (
            not name
            or Path(name).name != name
            or not _allowed_catalog_child(Path(name))
        ):
            raise MethodMenuValidationError(
                "method-menu seal contains an invalid file path"
            )
        source = staged / name
        raw = _read_bounded_bytes(
            source,
            maximum=(
                _MAX_REGISTRY_BYTES
                if name == METHOD_REGISTRY_FILENAME
                else _MAX_METHOD_FILE_BYTES
            ),
            label=f"sealed method-menu file {name!r}",
        )
        if (
            record.get("size") != len(raw)
            or record.get("sha256") != _digest_bytes(raw)
        ):
            raise StaleMethodMenu(
                f"sealed method-menu file {name!r} changed during promotion"
            )
        (prepared / name).write_bytes(raw)


def _restore_promotion_swap(
    published: Path,
    backup: Path | None,
) -> None:
    displaced: Path | None = None
    if published.exists():
        displaced = published.parent / f"{_DISPLACED_PREFIX}{uuid.uuid4().hex}"
        os.replace(published, displaced)
    try:
        if backup is not None and backup.exists():
            os.replace(backup, published)
    except BaseException:
        if displaced is not None and displaced.exists():
            os.replace(displaced, published)
        raise
    if displaced is not None and displaced.exists():
        _remove_regular_tree(displaced)


def promote_staged_menu(
    project_dir: str | Path,
    output_root: str | Path,
    seal: Mapping[str, Any],
) -> dict[str, Any]:
    """Atomically publish a sealed staged menu and retain a rollback backup."""

    root = _project_root(project_dir)
    verified = verify_staged_menu_seal(root, output_root, seal)
    _, staged = _staging_directory(root, output_root)
    ideas = _safe_project_path(root, METHOD_MENU_DIR.parent, label="ideas directory")
    ideas.mkdir(parents=True, exist_ok=True)
    ideas = _safe_project_path(root, ideas, label="ideas directory")
    published = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="published method-menu directory",
    )

    sealed_exists, sealed_files, sealed_digest = _published_baseline_from_seal(seal)
    previous_exists = published.exists()
    previous_files = _catalog_file_records(published)
    previous_catalog_sha256 = (
        _catalog_digest(previous_files) if previous_exists else None
    )
    if (
        previous_exists != sealed_exists
        or not _same_json(previous_files, sealed_files)
        or previous_catalog_sha256 != sealed_digest
    ):
        raise StaleMethodMenu(
            "published method menu changed after the staged menu was sealed"
        )
    _require_preserved_published_methods(
        _valid_published_numbers(root, published),
        verified["entries"],
    )
    before = _menu_snapshots(root, published)
    after = {
        str(entry["stable_id"]): dict(entry)
        for entry in verified["entries"]
    }
    changed_ids, changes = _menu_changes(before, after)

    prepared: Path | None = ideas / f"{_PREPARED_PREFIX}{uuid.uuid4().hex}"
    backup: Path | None = None
    swap_complete = False
    try:
        _copy_sealed_catalog(staged, prepared, verified["files"])
        prepared_seal = _seal_directory(root, prepared, require_registry=True)
        for field in ("files", "catalog_sha256", "entries"):
            if not _same_json(prepared_seal[field], verified[field]):
                raise StaleMethodMenu(
                    "prepared method menu does not match the sealed staged menu"
                )

        current_files = _catalog_file_records(published)
        current_digest = (
            _catalog_digest(current_files) if published.exists() else None
        )
        if not _same_json(current_files, previous_files) or current_digest != previous_catalog_sha256:
            raise StaleMethodMenu(
                "published method menu changed while the new menu was being prepared"
            )

        if published.exists():
            backup = ideas / f"{_BACKUP_PREFIX}{uuid.uuid4().hex}"
            os.replace(published, backup)
            try:
                captured_files = _catalog_file_records(backup)
                captured_digest = _catalog_digest(captured_files)
                if (
                    not previous_exists
                    or not _same_json(captured_files, previous_files)
                    or captured_digest != previous_catalog_sha256
                ):
                    raise StaleMethodMenu(
                        "published method menu changed during promotion"
                    )
            except BaseException:
                os.replace(backup, published)
                backup = None
                raise
        elif previous_exists:
            raise StaleMethodMenu("published method menu disappeared during promotion")
        try:
            os.replace(prepared, published)
            prepared = None
            swap_complete = True
        except BaseException:
            if backup is not None:
                os.replace(backup, published)
                backup = None
            raise

        post = _seal_directory(root, published, require_registry=True)
        for field in ("files", "catalog_sha256", "entries"):
            if not _same_json(post[field], verified[field]):
                raise StaleMethodMenu(
                    "published method menu failed post-write verification"
                )
    except BaseException:
        if swap_complete and published.exists():
            _restore_promotion_swap(published, backup)
            backup = None
        if prepared is not None and prepared.exists():
            _remove_regular_tree(prepared)
        raise

    return {
        "schema_version": METHOD_MENU_PROMOTION_SCHEMA_VERSION,
        "kind": "method_menu_promotion",
        "project_root": str(root),
        "published_path": METHOD_MENU_DIR.as_posix(),
        "backup_path": (
            _relative_to_root(root, backup, label="method-menu backup")
            if backup is not None
            else None
        ),
        "previous_files": previous_files,
        "previous_catalog_sha256": previous_catalog_sha256,
        "published_files": verified["files"],
        "published_catalog_sha256": verified["catalog_sha256"],
        "changed_stable_ids": changed_ids,
        "changes": changes,
    }


def _promotion_paths(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> tuple[Path, Path, Path | None]:
    if not isinstance(promotion, Mapping):
        raise MethodMenuValidationError("method-menu promotion must be a mapping")
    root = _project_root(project_dir)
    if (
        promotion.get("schema_version") != METHOD_MENU_PROMOTION_SCHEMA_VERSION
        or promotion.get("kind") != "method_menu_promotion"
        or promotion.get("project_root") != str(root)
        or promotion.get("published_path") != METHOD_MENU_DIR.as_posix()
    ):
        raise MethodMenuValidationError("method-menu promotion identity is invalid")
    published = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="published method-menu directory",
    )
    backup_value = promotion.get("backup_path")
    backup: Path | None = None
    if backup_value is not None:
        if not isinstance(backup_value, str):
            raise MethodMenuValidationError("method-menu backup path is invalid")
        backup = _safe_project_path(root, backup_value, label="method-menu backup")
        if (
            backup.parent != published.parent
            or not backup.name.startswith(_BACKUP_PREFIX)
        ):
            raise MethodMenuValidationError("method-menu backup path is invalid")
    return root, published, backup


def _verify_catalog_record(
    path: Path,
    expected_files: Any,
    expected_digest: Any,
    *,
    label: str,
) -> None:
    if not isinstance(expected_files, list):
        raise MethodMenuValidationError(f"{label} file record is invalid")
    files = _catalog_file_records(path)
    digest = _catalog_digest(files) if path.exists() else None
    if not _same_json(files, expected_files) or digest != expected_digest:
        raise StaleMethodMenu(f"{label} changed after promotion")


def commit_method_menu_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Commit a promotion by deleting its verified rollback backup."""

    _, published, backup = _promotion_paths(project_dir, promotion)
    _verify_catalog_record(
        published,
        promotion.get("published_files"),
        promotion.get("published_catalog_sha256"),
        label="published method menu",
    )
    if backup is None:
        return
    if not backup.exists():
        raise StaleMethodMenu("method-menu rollback backup is missing")
    _verify_catalog_record(
        backup,
        promotion.get("previous_files"),
        promotion.get("previous_catalog_sha256"),
        label="method-menu rollback backup",
    )
    _remove_regular_tree(backup)


def rollback_method_menu_promotion(
    project_dir: str | Path,
    promotion: Mapping[str, Any],
) -> None:
    """Restore the exact catalog that preceded a promotion."""

    root, published, backup = _promotion_paths(project_dir, promotion)
    current_files = _catalog_file_records(published)
    if _catalog_digest(current_files) != promotion.get("published_catalog_sha256"):
        raise StaleMethodMenu("published method menu changed after promotion")

    displaced = published.parent / f"{_DISPLACED_PREFIX}{uuid.uuid4().hex}"
    os.replace(published, displaced)
    try:
        if backup is not None:
            if not backup.exists():
                raise StaleMethodMenu("method-menu rollback backup is missing")
            _verify_catalog_record(
                backup,
                promotion.get("previous_files"),
                promotion.get("previous_catalog_sha256"),
                label="method-menu rollback backup",
            )
            os.replace(backup, published)
        expected_files = promotion.get("previous_files")
        expected_digest = promotion.get("previous_catalog_sha256")
        if backup is None:
            if expected_files != [] or expected_digest is not None:
                raise MethodMenuValidationError(
                    "method-menu promotion has inconsistent prior-state metadata"
                )
        else:
            _verify_catalog_record(
                published,
                expected_files,
                expected_digest,
                label="restored method menu",
            )
    except BaseException:
        if published.exists():
            recovery = published.parent / f"{_DISPLACED_PREFIX}{uuid.uuid4().hex}"
            os.replace(published, recovery)
            os.replace(displaced, published)
            _remove_regular_tree(recovery)
        else:
            os.replace(displaced, published)
        raise
    _remove_regular_tree(displaced)
    if backup is None and published.exists():
        raise MethodMenuValidationError("rollback unexpectedly recreated a prior menu")
    _safe_project_path(root, published, label="published method-menu directory")


def _rewrite_retired_method(path: Path) -> None:
    text, _ = _read_bounded_utf8(
        path,
        maximum=_MAX_METHOD_FILE_BYTES,
        label=f"method file {path.name!r}",
    )
    data, body = _parse_frontmatter(text)
    data["status"] = "retired"
    path.write_text(
        "---\n"
        + yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
        + "---\n\n"
        + body
        + "\n",
        encoding="utf-8",
        newline="",
    )


def retire_branch(
    project_dir: str | Path,
    stable_id: str,
    *,
    expected_version: str,
    expected_sha256: str,
) -> dict[str, Any]:
    """Retire one method if the submitted version and file hash are current."""

    normalized_id = _validate_stable_id(stable_id)
    normalized_version = str(expected_version).strip()
    normalized_sha256 = str(expected_sha256).strip().lower()
    if not normalized_version or not _SHA256_RE.fullmatch(normalized_sha256):
        raise StaleMethodMenu(
            "retirement request has no valid expected version and SHA-256"
        )

    root = _project_root(project_dir)
    published = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="published method-menu directory",
    )
    if not published.is_dir():
        raise BranchNotFound(normalized_id)
    before_files = _catalog_file_records(published)
    before_digest = _catalog_digest(before_files)
    menu = _load_menu_directory(root, published, require_registry=False)
    _raise_invalid_menu(menu)
    target = next(
        (
            entry
            for entry in menu["entries"]
            if entry.get("stable_id") == normalized_id
        ),
        None,
    )
    if target is None:
        raise BranchNotFound(normalized_id)
    if not hmac.compare_digest(str(target["version"]), normalized_version):
        raise StaleMethodMenu(
            "method version changed after the retirement form was shown"
        )
    if not hmac.compare_digest(str(target["sha256"]), normalized_sha256):
        raise StaleMethodMenu(
            "method file changed after the retirement form was shown"
        )
    if target["status"] == "retired":
        raise BranchAlreadyRetired(normalized_id)

    ideas = published.parent
    prepared: Path | None = ideas / f"{_PREPARED_PREFIX}{uuid.uuid4().hex}"
    backup: Path | None = None
    try:
        _copy_catalog(published, prepared)
        _rewrite_retired_method(prepared / f"{normalized_id}.md")
        registry_path = prepared / METHOD_REGISTRY_FILENAME
        if registry_path.exists():
            registry = _load_registry(registry_path)
            row = next(
                (
                    item
                    for item in registry["entries"]
                    if item["stable_id"] == normalized_id
                ),
                None,
            )
            if row is None:
                raise MethodMenuValidationError(
                    f"method registry has no entry for stable_id {normalized_id!r}"
                )
            row["status"] = "retired"
            row["retired_by"] = "user"
            row["retired_at"] = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )
            registry_path.write_text(
                yaml.safe_dump(
                    registry,
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
                newline="",
            )

        post_menu = _load_menu_directory(
            root,
            prepared,
            require_registry=registry_path.exists(),
        )
        _raise_invalid_menu(post_menu)
        after_files = _catalog_file_records(prepared)
        after_digest = _catalog_digest(after_files)

        current_files = _catalog_file_records(published)
        if (
            not _same_json(current_files, before_files)
            or _catalog_digest(current_files) != before_digest
        ):
            raise StaleMethodMenu(
                "published method menu changed while retirement was being prepared"
            )
        backup = ideas / f"{_BACKUP_PREFIX}{uuid.uuid4().hex}"
        os.replace(published, backup)
        try:
            os.replace(prepared, published)
            prepared = None
        except BaseException:
            os.replace(backup, published)
            backup = None
            raise

        verified_files = _catalog_file_records(published)
        verified_menu = _load_menu_directory(
            root,
            published,
            require_registry=registry_path.exists(),
        )
        _raise_invalid_menu(verified_menu)
        if (
            not _same_json(verified_files, after_files)
            or _catalog_digest(verified_files) != after_digest
        ):
            raise StaleMethodMenu(
                "retired method menu failed post-write verification"
            )
    except BaseException:
        if backup is not None and backup.exists():
            _restore_promotion_swap(published, backup)
            backup = None
        if prepared is not None and prepared.exists():
            _remove_regular_tree(prepared)
        raise

    if backup is not None:
        _remove_regular_tree(backup)
    result = next(
        entry
        for entry in verified_menu["entries"]
        if entry.get("stable_id") == normalized_id
    )
    return result
