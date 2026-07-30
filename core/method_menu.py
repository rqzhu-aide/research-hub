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
METHOD_PROVENANCE_SCHEMA_VERSION = 1
METHOD_REVISION_SCHEMA_VERSION = 1
LITERATURE_BASIS_SCHEMA_VERSION = 1

VALID_STATUSES = ("recommended", "viable", "frontier", "retired")

_STATUS_RANK = {status: rank for rank, status in enumerate(VALID_STATUSES)}
_FRONTMATTER_DELIMITER = "---"
_DEFINITION_HEADING_RE = re.compile(
    r"^ {0,3}##[ \t]+Mathematical[ \t]+definition[ \t]*#*[ \t]*$",
    re.IGNORECASE,
)
_SECTION_BOUNDARY_RE = re.compile(r"^ {0,3}#{1,2}[ \t]+")
_MAX_METHOD_FILE_BYTES = 1 * 1024 * 1024
_MAX_REGISTRY_BYTES = 1 * 1024 * 1024
_MAX_CATALOG_BYTES = 20 * 1024 * 1024
_MAX_CATALOG_FILES = 1000
_MAX_VERSION_HISTORY_ENTRIES = 1000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")
_BACKUP_PREFIX = ".method-menu-backup-"
_PREPARED_PREFIX = ".method-menu-prepared-"
_DISPLACED_PREFIX = ".method-menu-displaced-"
_REVIEW_SCOPES = frozenset({"full_catalog", "focused_method"})
_REVIEW_OUTCOMES = frozenset({"Complete", "Partial"})
_PROVENANCE_DISPOSITIONS = frozenset({
    "added", "changed", "reviewed_no_change", "user_retired",
})
_VERSION_HISTORY_CHANGES = frozenset({
    "added", "definition_revised", "legacy_import", "version_advanced",
})
_MAX_RUN_ID_LENGTH = 300


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


def _sha256(value: Any, *, label: str) -> str:
    digest = value.strip().lower() if isinstance(value, str) else ""
    if not _SHA256_RE.fullmatch(digest):
        raise MethodMenuValidationError(f"{label} must be a SHA-256 digest")
    return digest


def method_definition_sha256(entry: Mapping[str, Any]) -> str:
    """Return the scientific definition digest, with legacy fallback."""

    if not isinstance(entry, Mapping):
        raise MethodMenuValidationError("method entry must be a mapping")
    value = (
        entry.get("definition_sha256")
        if "definition_sha256" in entry
        else entry.get("sha256")
    )
    return _sha256(value, label="method definition")


def _run_id(value: Any, *, label: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    run_id = value.strip() if isinstance(value, str) else ""
    if (
        not run_id
        or len(run_id) > _MAX_RUN_ID_LENGTH
        or "\x00" in run_id
        or any(ord(character) < 32 for character in run_id)
    ):
        raise MethodMenuValidationError(f"{label} must be a valid run ID")
    return run_id


def normalize_literature_basis(value: Any) -> dict[str, Any]:
    """Validate the exact Phase 1 basis reviewed by one Phase 2 run."""

    fields = {
        "schema_version",
        "availability",
        "source_run_id",
        "generation",
        "synthesis_sha256",
        "collection_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise MethodMenuValidationError(
            "Phase 2 literature basis has unsupported fields"
        )
    if value.get("schema_version") != LITERATURE_BASIS_SCHEMA_VERSION:
        raise MethodMenuValidationError(
            "Phase 2 literature basis has an unsupported schema version"
        )
    availability = value.get("availability")
    if availability not in {"available", "absent"}:
        raise MethodMenuValidationError(
            "Phase 2 literature basis availability must be available or absent"
        )
    if availability == "absent":
        if any(
            value.get(field) is not None
            for field in (
                "source_run_id",
                "generation",
                "synthesis_sha256",
                "collection_sha256",
            )
        ):
            raise MethodMenuValidationError(
                "An absent Phase 2 literature basis cannot name Phase 1 content"
            )
        return {
            "schema_version": LITERATURE_BASIS_SCHEMA_VERSION,
            "availability": "absent",
            "source_run_id": None,
            "generation": None,
            "synthesis_sha256": None,
            "collection_sha256": None,
        }

    generation = value.get("generation")
    if (
        isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 1
    ):
        raise MethodMenuValidationError(
            "Available Phase 2 literature basis generation must be positive"
        )
    return {
        "schema_version": LITERATURE_BASIS_SCHEMA_VERSION,
        "availability": "available",
        "source_run_id": _run_id(
            value.get("source_run_id"),
            label="Phase 2 literature basis source_run_id",
        ),
        "generation": generation,
        "synthesis_sha256": _sha256(
            value.get("synthesis_sha256"),
            label="Phase 2 literature synthesis",
        ),
        "collection_sha256": _sha256(
            value.get("collection_sha256"),
            label="Phase 2 reference collection",
        ),
    }


def _normalize_version_history(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise MethodMenuValidationError(
            "method revision history must be a nonempty list"
        )
    if len(value) > _MAX_VERSION_HISTORY_ENTRIES:
        raise MethodMenuValidationError("method revision history is too long")

    normalized: list[dict[str, Any]] = []
    seen_versions: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or set(item) != {
            "version", "definition_sha256", "source_run_id", "change",
        }:
            raise MethodMenuValidationError(
                "method revision history entry has unsupported fields"
            )
        version = _validate_version(item.get("version"))
        if version in seen_versions:
            raise MethodMenuValidationError(
                "method revision history cannot repeat a version"
            )
        seen_versions.add(version)
        change = str(item.get("change", "")).strip()
        if change not in _VERSION_HISTORY_CHANGES:
            raise MethodMenuValidationError(
                "method revision history change is invalid"
            )
        source_run_id = _run_id(
            item.get("source_run_id"),
            label="method revision history source_run_id",
            nullable=change == "legacy_import",
        )
        current = {
            "version": version,
            "definition_sha256": _sha256(
                item.get("definition_sha256"),
                label="method revision history definition_sha256",
            ),
            "source_run_id": source_run_id,
            "change": change,
        }
        if index == 0 and change not in {"added", "legacy_import"}:
            raise MethodMenuValidationError(
                "method revision history must begin with added or legacy_import"
            )
        if index > 0:
            previous = normalized[-1]
            if change == "definition_revised" and hmac.compare_digest(
                current["definition_sha256"], previous["definition_sha256"]
            ):
                raise MethodMenuValidationError(
                    "definition_revised must change the definition digest"
                )
            if change == "version_advanced" and not hmac.compare_digest(
                current["definition_sha256"], previous["definition_sha256"]
            ):
                raise MethodMenuValidationError(
                    "version_advanced cannot change the definition digest"
                )
            if change in {"added", "legacy_import"}:
                raise MethodMenuValidationError(
                    "added and legacy_import can occur only at the start of history"
                )
        normalized.append(current)
    return normalized


def _normalize_method_revision(value: Any) -> dict[str, Any]:
    fields = {
        "schema_version", "current_version", "definition_sha256", "history",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise MethodMenuValidationError(
            "method revision record has unsupported fields"
        )
    if value.get("schema_version") != METHOD_REVISION_SCHEMA_VERSION:
        raise MethodMenuValidationError(
            "method revision record has an unsupported schema version"
        )
    history = _normalize_version_history(value.get("history"))
    current_version = _validate_version(value.get("current_version"))
    definition_sha256 = _sha256(
        value.get("definition_sha256"),
        label="method revision definition_sha256",
    )
    latest = history[-1]
    if latest["version"] != current_version or not hmac.compare_digest(
        latest["definition_sha256"], definition_sha256
    ):
        raise MethodMenuValidationError(
            "method revision record does not match its latest history entry"
        )
    return {
        "schema_version": METHOD_REVISION_SCHEMA_VERSION,
        "current_version": current_version,
        "definition_sha256": definition_sha256,
        "history": history,
    }


def normalize_method_provenance(value: Any) -> dict[str, Any]:
    """Validate system-managed provenance for one current method."""

    base_fields = {
        "schema_version",
        "method_sha256",
        "definition_source_run_id",
        "review_source_run_id",
        "review_scientific_outcome",
        "review_scope",
        "disposition",
        "literature_basis",
    }
    supplied_fields = frozenset(value) if isinstance(value, Mapping) else frozenset()
    if not isinstance(value, Mapping) or supplied_fields not in {
        frozenset(base_fields), frozenset(base_fields | {"revision"}),
    }:
        raise MethodMenuValidationError(
            "method provenance has unsupported fields"
        )
    if value.get("schema_version") != METHOD_PROVENANCE_SCHEMA_VERSION:
        raise MethodMenuValidationError(
            "method provenance has an unsupported schema version"
        )
    outcome = value.get("review_scientific_outcome")
    if outcome not in _REVIEW_OUTCOMES:
        raise MethodMenuValidationError(
            "method provenance review outcome must be Complete or Partial"
        )
    scope = value.get("review_scope")
    if scope not in _REVIEW_SCOPES:
        raise MethodMenuValidationError(
            "method provenance review scope is invalid"
        )
    disposition = value.get("disposition")
    if disposition not in _PROVENANCE_DISPOSITIONS:
        raise MethodMenuValidationError(
            "method provenance disposition is invalid"
        )
    normalized = {
        "schema_version": METHOD_PROVENANCE_SCHEMA_VERSION,
        "method_sha256": _sha256(
            value.get("method_sha256"),
            label="method provenance method_sha256",
        ),
        "definition_source_run_id": _run_id(
            value.get("definition_source_run_id"),
            label="method provenance definition_source_run_id",
            nullable=True,
        ),
        "review_source_run_id": _run_id(
            value.get("review_source_run_id"),
            label="method provenance review_source_run_id",
        ),
        "review_scientific_outcome": str(outcome),
        "review_scope": str(scope),
        "disposition": str(disposition),
        "literature_basis": normalize_literature_basis(
            value.get("literature_basis")
        ),
    }
    if "revision" in value:
        revision = _normalize_method_revision(value.get("revision"))
        defining_event = next(
            item
            for item in reversed(revision["history"])
            if item["change"]
            in {"added", "legacy_import", "definition_revised"}
        )
        if defining_event["source_run_id"] != normalized["definition_source_run_id"]:
            raise MethodMenuValidationError(
                "method provenance definition source does not match revision history"
            )
        normalized["revision"] = revision
    return normalized


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


def _definition_identity(body: str) -> tuple[str, str]:
    """Hash the exact mathematical definition section of a method file."""

    lines = body.splitlines()
    headings = [
        index
        for index, line in enumerate(lines)
        if _DEFINITION_HEADING_RE.fullmatch(line)
    ]
    if len(headings) > 1:
        raise MethodMenuValidationError(
            "method body must contain at most one '## Mathematical definition' section"
        )
    if not headings:
        content = body.strip()
        basis = "legacy_body"
    else:
        start = headings[0]
        end = next(
            (
                index
                for index in range(start + 1, len(lines))
                if _SECTION_BOUNDARY_RE.match(lines[index])
            ),
            len(lines),
        )
        content = "\n".join(lines[start + 1 : end]).strip()
        basis = "explicit_section"
    if not content:
        raise MethodMenuValidationError("method mathematical definition is empty")
    return _digest_bytes(content.encode("utf-8")), basis


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
        "definition_sha256": "",
        "definition_digest_basis": "",
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
        else:
            try:
                (
                    entry["definition_sha256"],
                    entry["definition_digest_basis"],
                ) = _definition_identity(body)
            except MethodMenuValidationError as exc:
                entry["errors"].append(str(exc))

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
        if "provenance" in row:
            try:
                normalized["provenance"] = normalize_method_provenance(
                    row.get("provenance")
                )
            except MethodMenuValidationError as exc:
                raise MethodMenuValidationError(f"{label} {exc}") from exc
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
        entry["provenance"] = None
        entry["provenance_error"] = ""
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
        provenance = row.get("provenance")
        if isinstance(provenance, Mapping):
            entry["provenance"] = dict(provenance)
            if not hmac.compare_digest(
                str(provenance.get("method_sha256", "")),
                str(entry.get("sha256", "")),
            ):
                entry["provenance_error"] = (
                    "The recorded Phase 2 provenance does not match the "
                    "current method file."
                )
            revision = provenance.get("revision")
            if isinstance(revision, Mapping) and (
                str(revision.get("current_version", ""))
                != str(entry.get("version", ""))
                or not hmac.compare_digest(
                    str(revision.get("definition_sha256", "")),
                    str(entry.get("definition_sha256", "")),
                )
            ):
                entry["provenance_error"] = (
                    "The recorded Phase 2 method revision does not match the "
                    "current method version and mathematical definition."
                )
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
    for entry in entries:
        entry["provenance"] = None
        entry["provenance_error"] = ""
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


def catalog_references_review_run(
    project_dir: str | Path,
    run_id: str,
    *,
    stable_id: str = "",
) -> bool:
    """Return whether an active, intact catalog row cites a Phase 2 review run."""

    requested_run = str(run_id).strip()
    requested_method = str(stable_id).strip()
    if not requested_run:
        return False
    menu = load_method_menu(project_dir)
    if menu["warnings"]:
        return False
    for entry in menu["entries"]:
        if (
            entry.get("status") == "retired"
            or entry.get("errors")
            or entry.get("provenance_error")
            or (
                requested_method
                and str(entry.get("stable_id", "")) != requested_method
            )
        ):
            continue
        provenance = entry.get("provenance")
        if (
            isinstance(provenance, Mapping)
            and str(provenance.get("review_source_run_id", "")).strip()
            == requested_run
            and hmac.compare_digest(
                str(provenance.get("method_sha256", "")).lower(),
                str(entry.get("sha256", "")).lower(),
            )
        ):
            return True
    return False


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


def _expected_catalog_digest(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise MethodMenuValidationError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


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
        "definition_sha256": str(entry.get("definition_sha256", "")),
        "definition_digest_basis": str(
            entry.get("definition_digest_basis", "")
        ),
    }


def _require_method_revision_identity(
    published_methods: Mapping[str, Mapping[str, Any]],
    staged_entries: list[Mapping[str, Any]],
) -> None:
    """Require a new version whenever the mathematical definition changes."""

    for current in staged_entries:
        stable_id = str(current.get("stable_id", ""))
        before = published_methods.get(stable_id)
        if before is None:
            if current.get("definition_digest_basis") != "explicit_section":
                raise MethodMenuValidationError(
                    f"new method {stable_id!r} must contain an explicit "
                    "'## Mathematical definition' section"
                )
            continue

        version_changed = str(before.get("version", "")) != str(
            current.get("version", "")
        )
        definition_changed = not hmac.compare_digest(
            str(before.get("definition_sha256", "")),
            str(current.get("definition_sha256", "")),
        )
        if definition_changed and not version_changed:
            raise MethodMenuValidationError(
                f"method {stable_id!r} changes its mathematical calculation "
                "without advancing the version"
            )
        if version_changed and current.get("definition_digest_basis") != "explicit_section":
            raise MethodMenuValidationError(
                f"revised method {stable_id!r} must contain an explicit "
                "'## Mathematical definition' section"
            )


def _system_method_revision(
    before: Mapping[str, Any] | None,
    current: Mapping[str, Any],
    prior_provenance: Mapping[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    prior_revision = (
        prior_provenance.get("revision")
        if isinstance(prior_provenance, Mapping)
        else None
    )
    if isinstance(prior_revision, Mapping):
        if before is None or (
            str(prior_revision.get("current_version", ""))
            != str(before.get("version", ""))
            or not hmac.compare_digest(
                str(prior_revision.get("definition_sha256", "")),
                str(before.get("definition_sha256", "")),
            )
        ):
            raise MethodMenuValidationError(
                "published method revision provenance is stale"
            )
        history = [dict(item) for item in prior_revision.get("history", [])]
    elif before is not None:
        prior_definition_run = (
            prior_provenance.get("definition_source_run_id")
            if isinstance(prior_provenance, Mapping)
            else None
        )
        history = [{
            "version": str(before["version"]),
            "definition_sha256": str(before["definition_sha256"]),
            "source_run_id": prior_definition_run,
            "change": "legacy_import",
        }]
    else:
        history = []

    current_version = str(current["version"])
    current_digest = str(current["definition_sha256"])
    if not history:
        history.append({
            "version": current_version,
            "definition_sha256": current_digest,
            "source_run_id": run_id,
            "change": "added",
        })
    else:
        latest = history[-1]
        version_changed = str(latest["version"]) != current_version
        definition_changed = not hmac.compare_digest(
            str(latest["definition_sha256"]), current_digest
        )
        if definition_changed and not version_changed:
            raise MethodMenuValidationError(
                f"method {current.get('stable_id')!r} changes its mathematical "
                "calculation without advancing the version"
            )
        if version_changed:
            history.append({
                "version": current_version,
                "definition_sha256": current_digest,
                "source_run_id": run_id,
                "change": (
                    "definition_revised"
                    if definition_changed
                    else "version_advanced"
                ),
            })

    return _normalize_method_revision({
        "schema_version": METHOD_REVISION_SCHEMA_VERSION,
        "current_version": current_version,
        "definition_sha256": current_digest,
        "history": history,
    })


def _valid_published_methods(
    root: Path,
    menu_dir: Path,
) -> dict[str, dict[str, Any]]:
    """Return identity fields for individually valid published entries."""

    if not menu_dir.exists():
        return {}
    menu = _load_menu_directory(root, menu_dir, require_registry=False)
    return {
        str(entry["stable_id"]): _entry_snapshot(entry)
        for entry in menu["entries"]
        if not entry.get("errors")
        and str(entry.get("stable_id", "")).strip()
        and isinstance(entry.get("number"), int)
    }


def _require_preserved_published_methods(
    published_methods: Mapping[str, Mapping[str, Any]],
    staged_entries: list[Mapping[str, Any]],
) -> None:
    """Preserve published identities and explicit user retirements."""

    staged_by_id = {
        str(entry.get("stable_id", "")): entry
        for entry in staged_entries
        if str(entry.get("stable_id", ""))
    }
    for stable_id, published in sorted(published_methods.items()):
        number = published.get("number")
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
        if (
            published.get("status") == "retired"
            and staged.get("status") != "retired"
        ):
            raise MethodMenuValidationError(
                f"staged method menu reactivates retired method {stable_id!r}; "
                "keep it retired unless the user explicitly reactivates it"
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
    *,
    expected_catalog_sha256: str | None = None,
) -> dict[str, Any]:
    """Seed ``<output_root>/method-menu`` from the current published menu."""

    root = _project_root(project_dir)
    source = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="published method-menu directory",
    )
    expected_digest = _expected_catalog_digest(
        expected_catalog_sha256,
        label="expected method catalog digest",
    )
    source_files = _catalog_file_records(source)
    source_digest = _catalog_digest(source_files)
    if expected_digest is not None and not hmac.compare_digest(
        expected_digest, source_digest
    ):
        raise StaleMethodMenu(
            "published method catalog changed after it was reviewed"
        )
    output, staged = _staging_directory(root, output_root)
    prepared: Path | None = Path(
        tempfile.mkdtemp(prefix=_PREPARED_PREFIX, dir=str(output))
    )
    try:
        _copy_catalog(source, prepared)
        copied_source_files = _catalog_file_records(prepared)
        current_source_files = _catalog_file_records(source)
        if not _same_json(copied_source_files, source_files) or not _same_json(
            current_source_files, source_files
        ):
            raise StaleMethodMenu(
                "published method catalog changed while it was staged"
            )
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

    staged_files = _catalog_file_records(staged)
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
        "source_files": source_files,
        "source_catalog_sha256": source_digest,
        "staged_files": staged_files,
        "staged_catalog_sha256": _catalog_digest(staged_files),
        "warnings": warnings,
    }


def _registry_rows_by_id(
    registry: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(registry, Mapping):
        return {}
    return {
        str(row["stable_id"]): dict(row)
        for row in registry.get("entries", [])
        if isinstance(row, Mapping) and str(row.get("stable_id", "")).strip()
    }


def _write_registry_atomic(path: Path, registry: Mapping[str, Any]) -> None:
    payload = yaml.safe_dump(
        dict(registry),
        sort_keys=False,
        allow_unicode=True,
    ).encode("utf-8")
    if len(payload) > _MAX_REGISTRY_BYTES:
        raise MethodMenuValidationError(
            f"method registry exceeds the {_MAX_REGISTRY_BYTES}-byte limit"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".registry-",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply_run_provenance(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    run_id: str,
    scientific_outcome: str,
    review_scope: str,
    literature_basis: Mapping[str, Any],
    focused_method_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Write per-method review provenance into the staged catalog.

    The updater is deterministic and runs immediately before sealing. It
    overwrites agent-authored provenance for methods covered by this run and
    restores the published value for every method outside the selected scope.
    """

    root = _project_root(project_dir)
    normalized_run_id = _run_id(run_id, label="Phase 2 provenance run_id")
    outcome = str(scientific_outcome).strip()
    if outcome not in _REVIEW_OUTCOMES:
        raise MethodMenuValidationError(
            "Phase 2 provenance requires a Complete or Partial outcome"
        )
    scope = str(review_scope).strip()
    if scope not in _REVIEW_SCOPES:
        raise MethodMenuValidationError("Phase 2 provenance scope is invalid")
    normalized_basis = normalize_literature_basis(literature_basis)
    focused_id = (
        _validate_stable_id(focused_method_id)
        if focused_method_id is not None
        else None
    )
    if (scope == "focused_method") != (focused_id is not None):
        raise MethodMenuValidationError(
            "Focused Phase 2 provenance requires exactly one selected method"
        )

    _, staged = _staging_directory(root, output_root)
    staged_menu = _load_menu_directory(root, staged, require_registry=True)
    _raise_invalid_menu(staged_menu)
    staged_registry = staged_menu.get("registry")
    if not isinstance(staged_registry, Mapping):
        raise MethodMenuValidationError(
            "staged method menu has no valid registry"
        )
    staged_entries = {
        str(entry["stable_id"]): entry
        for entry in staged_menu["entries"]
        if str(entry.get("stable_id", "")).strip()
    }
    staged_rows = _registry_rows_by_id(staged_registry)
    if set(staged_entries) != set(staged_rows):
        raise MethodMenuValidationError(
            "staged method files and registry rows do not match"
        )
    if focused_id is not None and focused_id not in staged_entries:
        raise MethodMenuValidationError(
            "Focused Phase 2 provenance names an unknown method"
        )

    published = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="published method-menu directory",
    )
    published_menu = _load_menu_directory(
        root, published, require_registry=False
    )
    published_entries = {
        str(entry["stable_id"]): entry
        for entry in published_menu["entries"]
        if str(entry.get("stable_id", "")).strip() and not entry.get("errors")
    }
    published_rows = _registry_rows_by_id(published_menu.get("registry"))
    _require_method_revision_identity(
        published_entries,
        list(staged_entries.values()),
    )

    reviewed_ids = (
        {focused_id}
        if focused_id is not None
        else set(staged_entries)
    )
    provenance_by_id: dict[str, dict[str, Any]] = {}
    for row in staged_registry["entries"]:
        stable_id = str(row["stable_id"])
        if stable_id not in reviewed_ids:
            prior = published_rows.get(stable_id, {}).get("provenance")
            if isinstance(prior, Mapping):
                row["provenance"] = dict(prior)
            else:
                row.pop("provenance", None)
            continue

        current = staged_entries[stable_id]
        before = published_entries.get(stable_id)
        changed = before is None or not _same_json(
            _entry_snapshot(before),
            _entry_snapshot(current),
        )
        prior = published_rows.get(stable_id, {}).get("provenance")
        revision = _system_method_revision(
            before,
            current,
            prior if isinstance(prior, Mapping) else None,
            normalized_run_id,
        )
        definition_changed = before is None or not hmac.compare_digest(
            str(before.get("definition_sha256", "")),
            str(current.get("definition_sha256", "")),
        )
        prior_definition_run = (
            prior.get("definition_source_run_id")
            if isinstance(prior, Mapping)
            else None
        )
        disposition = (
            "added"
            if before is None
            else "changed"
            if changed
            else "reviewed_no_change"
        )
        provenance = normalize_method_provenance({
            "schema_version": METHOD_PROVENANCE_SCHEMA_VERSION,
            "method_sha256": str(current["sha256"]),
            "definition_source_run_id": (
                normalized_run_id
                if definition_changed
                else prior_definition_run
            ),
            "review_source_run_id": normalized_run_id,
            "review_scientific_outcome": outcome,
            "review_scope": scope,
            "disposition": disposition,
            "literature_basis": normalized_basis,
            "revision": revision,
        })
        row["provenance"] = provenance
        provenance_by_id[stable_id] = provenance

    registry_path = staged / METHOD_REGISTRY_FILENAME
    _write_registry_atomic(registry_path, staged_registry)
    verified = _load_menu_directory(root, staged, require_registry=True)
    _raise_invalid_menu(verified)
    for entry in verified["entries"]:
        if entry.get("provenance_error"):
            raise MethodMenuValidationError(str(entry["provenance_error"]))
    return provenance_by_id


def seal_staged_menu(
    project_dir: str | Path,
    output_root: str | Path,
    *,
    expected_published_catalog_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate and seal the exact run-local method-menu bytes."""

    root = _project_root(project_dir)
    _, staged = _staging_directory(root, output_root)
    staged_seal = _seal_directory(root, staged, require_registry=True)
    expected_digest = _expected_catalog_digest(
        expected_published_catalog_sha256,
        label="expected published method catalog digest",
    )
    published = _safe_project_path(
        root,
        METHOD_MENU_DIR,
        label="published method-menu directory",
    )
    published_exists = published.exists()
    published_files = _catalog_file_records(published)
    live_published_digest = _catalog_digest(published_files)
    if expected_digest is not None and not hmac.compare_digest(
        expected_digest, live_published_digest
    ):
        raise StaleMethodMenu(
            "published method catalog changed after this run was frozen"
        )
    published_digest = (
        live_published_digest if published_exists else None
    )
    _require_preserved_published_methods(
        _valid_published_methods(root, published),
        staged_seal["entries"],
    )
    _require_method_revision_identity(
        _valid_published_methods(root, published),
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


def _focused_method_path(
    root: Path,
    menu_dir: Path,
    stable_id: str,
) -> tuple[str, Mapping[str, Any]]:
    menu = _load_menu_directory(root, menu_dir, require_registry=True)
    _raise_invalid_menu(menu)
    matches = [
        entry
        for entry in menu["entries"]
        if str(entry.get("stable_id", "")).strip() == stable_id
    ]
    if len(matches) != 1:
        raise MethodMenuValidationError(
            "The focused method must appear exactly once in both catalog versions"
        )
    entry = matches[0]
    return Path(str(entry.get("path", ""))).name, entry


def _validate_focused_catalog_update(
    root: Path,
    published: Path,
    staged: Path,
    focused_method_id: str,
) -> None:
    """Require every non-selected method file to remain byte-identical."""

    stable_id = str(focused_method_id).strip()
    if not stable_id:
        raise MethodMenuValidationError("Focused catalog update has no method ID")
    if not published.exists():
        raise MethodMenuValidationError(
            "A focused catalog update requires an existing published catalog"
        )

    before_name, before_entry = _focused_method_path(root, published, stable_id)
    after_name, after_entry = _focused_method_path(root, staged, stable_id)
    if before_name != after_name:
        raise MethodMenuValidationError(
            "A focused catalog update cannot rename the selected method file"
        )
    if str(before_entry.get("status", "")) == "retired":
        raise MethodMenuValidationError(
            "A focused catalog update cannot target a retired method"
        )
    if str(after_entry.get("status", "")) == "retired":
        raise MethodMenuValidationError(
            "Retire a method through the user control, not a focused team run"
        )

    before_registry = _load_registry(published / METHOD_REGISTRY_FILENAME)
    after_registry = _load_registry(staged / METHOD_REGISTRY_FILENAME)
    if before_registry["next_number"] != after_registry["next_number"]:
        raise MethodMenuValidationError(
            "A focused catalog update cannot change the registry next_number"
        )
    before_rows = {
        str(row["stable_id"]): row for row in before_registry["entries"]
    }
    after_rows = {
        str(row["stable_id"]): row for row in after_registry["entries"]
    }
    for other_id in sorted(set(before_rows) - {stable_id}):
        if not _same_json(before_rows[other_id], after_rows.get(other_id)):
            raise MethodMenuValidationError(
                "A focused catalog update changed the non-selected registry "
                f"row for {other_id!r}"
            )

    excluded = {METHOD_REGISTRY_FILENAME, before_name}
    before_files = {
        str(record["path"]): record
        for record in _catalog_file_records(published)
        if str(record["path"]) not in excluded
    }
    after_files = {
        str(record["path"]): record
        for record in _catalog_file_records(staged)
        if str(record["path"]) not in excluded
    }
    if not _same_json(before_files, after_files):
        raise MethodMenuValidationError(
            "A focused catalog update changed a non-selected method"
        )

    before = _menu_snapshots(root, published)
    after = _menu_snapshots(root, staged)
    if set(before) != set(after):
        raise MethodMenuValidationError(
            "A focused catalog update cannot add or remove methods"
        )
    for other_id in sorted(set(before) - {stable_id}):
        if not _same_json(before[other_id], after[other_id]):
            raise MethodMenuValidationError(
                f"A focused catalog update changed non-selected method {other_id!r}"
            )


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


def _downstream_invalidated_stable_ids(
    changes: list[Mapping[str, Any]],
) -> list[str]:
    """Return branches whose exact scientific method identity is no longer current."""

    invalidated: list[str] = []
    for change in changes:
        stable_id = str(change.get("stable_id", "")).strip()
        before = change.get("before")
        after = change.get("after")
        if not stable_id or before is None:
            continue
        if not isinstance(before, Mapping) or after is None:
            invalidated.append(stable_id)
            continue
        if not isinstance(after, Mapping):
            invalidated.append(stable_id)
            continue
        identity_changed = (
            str(before.get("version", "")) != str(after.get("version", ""))
            or not hmac.compare_digest(
                str(before.get("definition_sha256", "")),
                str(after.get("definition_sha256", "")),
            )
        )
        newly_retired = (
            str(before.get("status", "")) != "retired"
            and str(after.get("status", "")) == "retired"
        )
        if identity_changed or newly_retired:
            invalidated.append(stable_id)
    return invalidated


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
    *,
    focused_method_id: str | None = None,
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
        _valid_published_methods(root, published),
        verified["entries"],
    )
    _require_method_revision_identity(
        _valid_published_methods(root, published),
        verified["entries"],
    )
    if focused_method_id is not None:
        _validate_focused_catalog_update(
            root,
            published,
            staged,
            focused_method_id,
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

    downstream_invalidated_ids = _downstream_invalidated_stable_ids(changes)
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
        "downstream_invalidated_stable_ids": downstream_invalidated_ids,
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
    if backup is None or not backup.exists():
        return
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
    try:
        _verify_catalog_record(
            published,
            promotion.get("previous_files"),
            promotion.get("previous_catalog_sha256"),
            label="restored method menu",
        )
    except StaleMethodMenu:
        pass
    else:
        if backup is None or not backup.exists():
            return
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
            provenance = row.get("provenance")
            if isinstance(provenance, Mapping):
                rewritten = _parse_method_path(
                    prepared / f"{normalized_id}.md", root
                )
                provenance = dict(provenance)
                provenance["method_sha256"] = str(rewritten["sha256"])
                provenance["disposition"] = "user_retired"
                row["provenance"] = normalize_method_provenance(provenance)
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
