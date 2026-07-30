"""Paper-card schema, canonical identities, and reference-index generation.

This module contains no run lifecycle or promotion logic.  It interprets the
scientific records stored in ``references/papers`` so Phase 01 transactions,
future import tools, and diagnostics share one definition of a valid card.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

import yaml
from yaml.constructor import ConstructorError

from core.filesystem_utils import metadata_is_link_or_reparse
from core.strict_json import StrictJsonError, parse_json_object


REFERENCE_INDEX_SCHEMA_VERSION = 2
MAX_CARD_BYTES = 1 * 1024 * 1024
MAX_PAPERS = 10_000
MAX_LIBRARY_BYTES = 250 * 1024 * 1024

_FRONTMATTER_DELIMITER = "---"
_SAFE_CARD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,239}\.md$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_ARXIV_RE = re.compile(
    r"^(?:[a-z][a-z0-9.+-]*/\d{7}|\d{4}\.\d{4,5})$",
    re.IGNORECASE,
)
_PMID_RE = re.compile(r"^\d{1,12}$")
_PMCID_RE = re.compile(r"^PMC\d{1,12}$", re.IGNORECASE)
_IDENTITY_FIELDS = (
    "doi",
    "arxiv_id",
    "arxiv",
    "pmid",
    "pmcid",
    "repository_url",
    "repo_url",
    "github_repo",
    "pypi_package",
)
PROVENANCE_FIELDS = ("found_in_run", "found_by_role")


class LiteratureRecordError(ValueError):
    """Base class for reference-library validation and transaction failures."""


class LiteratureRecordValidationError(LiteratureRecordError):
    """Raised when a reference card or delta violates the library contract."""


class StaleLiteratureRecord(LiteratureRecordError):
    """Raised when sealed or live reference-library bytes have changed."""


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


def _is_link_or_reparse(path: Path) -> bool:
    try:
        return metadata_is_link_or_reparse(path.lstat())
    except FileNotFoundError:
        return False


def _read_bounded_bytes(path: Path, *, maximum: int, label: str) -> bytes:
    try:
        details = path.lstat()
    except OSError as exc:
        raise LiteratureRecordValidationError(
            f"{label} cannot be inspected: {exc}"
        ) from exc
    if metadata_is_link_or_reparse(details) or not stat.S_ISREG(details.st_mode):
        raise LiteratureRecordValidationError(
            f"{label} must be a regular file, not a link or junction"
        )
    if details.st_size > maximum:
        raise LiteratureRecordValidationError(
            f"{label} exceeds the {maximum}-byte limit"
        )
    try:
        with path.open("rb") as handle:
            raw = handle.read(maximum + 1)
    except OSError as exc:
        raise LiteratureRecordValidationError(f"{label} cannot be read: {exc}") from exc
    if len(raw) > maximum:
        raise LiteratureRecordValidationError(
            f"{label} exceeds the {maximum}-byte limit"
        )
    return raw


def _read_bounded_utf8(path: Path, *, maximum: int, label: str) -> tuple[str, bytes]:
    raw = _read_bounded_bytes(path, maximum=maximum, label=label)
    try:
        return raw.decode("utf-8"), raw
    except UnicodeDecodeError as exc:
        raise LiteratureRecordValidationError(f"{label} is not valid UTF-8") from exc


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


def _card_name(path: Path) -> str:
    if not _SAFE_CARD_NAME.fullmatch(path.name):
        raise LiteratureRecordValidationError(
            f"reference-card filename {path.name!r} is not a safe .md filename"
        )
    return path.name


def paper_file_records(
    papers_dir: Path,
    *,
    prefix: str,
) -> list[dict[str, Any]]:
    """Return bounded, deterministic byte records for one paper-card folder."""

    if not papers_dir.exists():
        return []
    if _is_link_or_reparse(papers_dir) or not papers_dir.is_dir():
        raise LiteratureRecordValidationError(
            f"{prefix.rstrip('/')} must be a regular directory"
        )
    children = sorted(papers_dir.iterdir(), key=lambda item: item.name)
    if len(children) > MAX_PAPERS:
        raise LiteratureRecordValidationError(
            f"reference library contains more than {MAX_PAPERS} paper cards"
        )
    records: list[dict[str, Any]] = []
    total = 0
    for child in children:
        name = _card_name(child)
        raw = _read_bounded_bytes(
            child,
            maximum=MAX_CARD_BYTES,
            label=f"reference card {name!r}",
        )
        total += len(raw)
        if total > MAX_LIBRARY_BYTES:
            raise LiteratureRecordValidationError(
                f"reference cards exceed the {MAX_LIBRARY_BYTES}-byte total limit"
            )
        records.append(
            {
                "path": f"{prefix}{name}",
                "sha256": _digest_bytes(raw),
                "size": len(raw),
            }
        )
    return records


def _parse_frontmatter(text: str, *, label: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise LiteratureRecordValidationError(
            f"{label} does not start with a '---' frontmatter block"
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
        raise LiteratureRecordValidationError(
            f"{label} frontmatter is not closed with a second '---'"
        )
    try:
        metadata = yaml.load(
            "\n".join(lines[1:end]),
            Loader=_UniqueKeySafeLoader,
        )
    except yaml.YAMLError as exc:
        raise LiteratureRecordValidationError(
            f"{label} frontmatter is not valid YAML: {exc}"
        ) from exc
    if not isinstance(metadata, dict) or any(
        not isinstance(key, str) for key in metadata
    ):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter must be a mapping with text keys"
        )
    body = "\n".join(lines[end + 1 :]).strip()
    if not body:
        raise LiteratureRecordValidationError(f"{label} body must be nonempty")
    return metadata, body


def _identity_text(value: Any, *, field: str, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} must be one text value"
        )
    text = str(value).strip()
    if not text:
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} must be nonempty"
        )
    return text


def _strip_prefix(text: str, prefixes: tuple[str, ...]) -> str:
    lowered = text.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            return text[len(prefix) :]
    return text


def _normalize_doi(value: Any, *, field: str, label: str) -> str:
    text = _strip_prefix(
        _identity_text(value, field=field, label=label),
        ("https://doi.org/", "http://doi.org/", "doi:"),
    ).strip()
    if not _DOI_RE.fullmatch(text):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} is not a valid DOI"
        )
    return f"doi:{text.lower()}"


def _normalize_arxiv(value: Any, *, field: str, label: str) -> str:
    text = _strip_prefix(
        _identity_text(value, field=field, label=label),
        (
            "https://arxiv.org/abs/",
            "http://arxiv.org/abs/",
            "https://arxiv.org/pdf/",
            "http://arxiv.org/pdf/",
            "arxiv:",
        ),
    )
    if text.lower().endswith(".pdf"):
        text = text[:-4]
    text = re.sub(r"v\d+$", "", text.strip(), flags=re.IGNORECASE)
    if not _ARXIV_RE.fullmatch(text):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} is not a valid arXiv identifier"
        )
    return f"arxiv:{text.lower()}"


def _normalize_pmid(value: Any, *, field: str, label: str) -> str:
    text = _strip_prefix(
        _identity_text(value, field=field, label=label),
        (
            "https://pubmed.ncbi.nlm.nih.gov/",
            "http://pubmed.ncbi.nlm.nih.gov/",
            "pmid:",
        ),
    ).strip().strip("/")
    if not _PMID_RE.fullmatch(text):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} is not a valid PMID"
        )
    return f"pmid:{text}"


def _normalize_pmcid(value: Any, *, field: str, label: str) -> str:
    text = _strip_prefix(
        _identity_text(value, field=field, label=label),
        (
            "https://pmc.ncbi.nlm.nih.gov/articles/",
            "http://pmc.ncbi.nlm.nih.gov/articles/",
            "pmcid:",
        ),
    ).strip().strip("/").upper()
    if not _PMCID_RE.fullmatch(text):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} is not a valid PMCID"
        )
    return f"pmcid:{text}"


def _normalize_repository(value: Any, *, field: str, label: str) -> str:
    text = _identity_text(value, field=field, label=label)
    if field == "github_repo" and "://" not in text:
        text = f"https://github.com/{text.strip('/')}"
    parsed = urlsplit(text)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} is not a canonical repository URL"
        )
    host = parsed.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    try:
        port = parsed.port
    except ValueError as exc:
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} has an invalid port"
        ) from exc
    netloc = host
    if port and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    if not path or path == "/":
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} must identify a repository"
        )
    if host in {"github.com", "gitlab.com", "bitbucket.org"}:
        path = path.lower()
    canonical = urlunsplit(("https", netloc, path, "", ""))
    return f"repo:{canonical}"


def _normalize_pypi(value: Any, *, field: str, label: str) -> str:
    text = _identity_text(value, field=field, label=label).lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,199}", text):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} is not a valid package name"
        )
    return f"pypi:{re.sub(r'[-_.]+', '-', text)}"


def _normalize_identity(field: str, value: Any, *, label: str) -> str:
    if field == "doi":
        return _normalize_doi(value, field=field, label=label)
    if field in {"arxiv_id", "arxiv"}:
        return _normalize_arxiv(value, field=field, label=label)
    if field == "pmid":
        return _normalize_pmid(value, field=field, label=label)
    if field == "pmcid":
        return _normalize_pmcid(value, field=field, label=label)
    if field in {"repository_url", "repo_url", "github_repo"}:
        return _normalize_repository(value, field=field, label=label)
    if field == "pypi_package":
        return _normalize_pypi(value, field=field, label=label)
    raise LiteratureRecordValidationError(f"unsupported identity field {field!r}")


def _provenance_value(value: Any, *, field: str, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} must be one text value"
        )
    normalized = str(value).strip()
    if not normalized:
        raise LiteratureRecordValidationError(
            f"{label} frontmatter {field!r} must be nonempty"
        )
    return normalized


def _also_found(value: Any, *, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter 'also_found_in' must be a list"
        )
    normalized = [
        _provenance_value(item, field="also_found_in", label=label)
        for item in value
    ]
    if len(set(normalized)) != len(normalized):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter 'also_found_in' contains duplicates"
        )
    return normalized


def parse_card(path: Path, *, relative_path: str) -> dict[str, Any]:
    """Parse and normalize one complete reference card."""

    label = f"reference card {relative_path!r}"
    text, raw = _read_bounded_utf8(path, maximum=MAX_CARD_BYTES, label=label)
    metadata, body = _parse_frontmatter(text, label=label)
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        raise LiteratureRecordValidationError(
            f"{label} frontmatter 'title' must be nonempty text"
        )
    identities = {
        field: _normalize_identity(field, metadata[field], label=label)
        for field in _IDENTITY_FIELDS
        if field in metadata
    }
    aliases = sorted(set(identities.values()))
    if not aliases:
        raise LiteratureRecordValidationError(
            f"{label} needs a DOI, arXiv ID, PMID, PMCID, repository URL, "
            "GitHub repository, or PyPI package identity"
        )
    provenance = {
        field: _provenance_value(metadata.get(field), field=field, label=label)
        for field in PROVENANCE_FIELDS
    }
    relation = metadata.get("relation")
    if relation is not None and not isinstance(relation, str):
        raise LiteratureRecordValidationError(
            f"{label} frontmatter 'relation' must be text"
        )
    return {
        "path": relative_path,
        "filename": Path(relative_path).name,
        "sha256": _digest_bytes(raw),
        "size": len(raw),
        "title": title.strip(),
        "relation": relation.strip() if isinstance(relation, str) else "",
        "identities": identities,
        "aliases": aliases,
        "provenance": provenance,
        "also_found_in": _also_found(
            metadata.get("also_found_in", []),
            label=label,
        ),
        "body": body,
    }


def load_cards(papers_dir: Path, *, prefix: str) -> list[dict[str, Any]]:
    """Load a folder and reject identity aliases shared by different cards."""

    records = paper_file_records(papers_dir, prefix=prefix)
    cards = [
        parse_card(
            papers_dir / Path(str(record["path"])).name,
            relative_path=str(record["path"]),
        )
        for record in records
    ]
    aliases: dict[str, str] = {}
    for card in cards:
        for alias in card["aliases"]:
            previous = aliases.get(alias)
            if previous is not None:
                raise LiteratureRecordValidationError(
                    f"reference cards {previous!r} and {card['path']!r} "
                    f"share canonical identity {alias!r}"
                )
            aliases[alias] = str(card["path"])
    return cards


def build_delta_operations(
    canonical_cards: list[dict[str, Any]],
    delta_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate that a Phase 1 delta contains only new references."""

    existing_by_name = {
        str(card["filename"]).casefold(): str(card["filename"])
        for card in canonical_cards
    }
    existing_by_alias = {
        alias: str(card["filename"])
        for card in canonical_cards
        for alias in card["aliases"]
    }
    delta_names: dict[str, str] = {}
    delta_aliases: dict[str, str] = {}
    operations: list[dict[str, Any]] = []
    for card in sorted(delta_cards, key=lambda value: str(value["filename"])):
        filename = str(card["filename"])
        filename_key = filename.casefold()
        existing_name = existing_by_name.get(filename_key)
        if existing_name is not None:
            raise LiteratureRecordValidationError(
                f"delta card {filename!r} conflicts with existing reference card "
                f"{existing_name!r}; Phase 1 accepts only new references"
            )
        other_name = delta_names.get(filename_key)
        if other_name is not None:
            raise LiteratureRecordValidationError(
                f"delta cards {other_name!r} and {filename!r} have filenames "
                "that collide across supported operating systems"
            )
        delta_names[filename_key] = filename
        for alias in card["aliases"]:
            other_delta = delta_aliases.get(alias)
            if other_delta is not None and other_delta != filename:
                raise LiteratureRecordValidationError(
                    f"delta cards {other_delta!r} and {filename!r} share "
                    f"canonical identity {alias!r}"
                )
            delta_aliases[alias] = filename
            canonical_name = existing_by_alias.get(alias)
            if canonical_name is not None:
                raise LiteratureRecordValidationError(
                    f"delta card {filename!r} duplicates canonical identity "
                    f"{alias!r} already stored in {canonical_name!r}; Phase 1 "
                    "does not replace existing references"
                )
        operations.append(
            {
                "filename": filename,
                "change": "added",
                "source_path": f"papers/{filename}",
                "source_sha256": card["sha256"],
                "aliases": card["aliases"],
            }
        )
    return operations


def build_reference_index(
    papers_dir: Path,
    *,
    source_run_id: str,
    generation: int,
    summary_sha256: str,
) -> bytes:
    """Generate the deterministic identity and provenance index."""

    normalized_run_id = str(source_run_id).strip()
    if not normalized_run_id:
        raise LiteratureRecordValidationError(
            "reference index source_run_id must be nonempty"
        )
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise LiteratureRecordValidationError(
            "reference index generation must be a positive integer"
        )
    if not isinstance(summary_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", summary_sha256):
        raise LiteratureRecordValidationError(
            "reference index summary_sha256 must be a lowercase SHA-256 digest"
        )
    cards = load_cards(papers_dir, prefix="papers/")
    records = paper_file_records(papers_dir, prefix="papers/")
    by_path = {str(record["path"]): record for record in records}
    entries: list[dict[str, Any]] = []
    for card in sorted(cards, key=lambda value: str(value["path"])):
        path = str(card["path"])
        identities: dict[str, list[str]] = {}
        for alias in card["aliases"]:
            kind, value = alias.split(":", 1)
            identities.setdefault(kind, []).append(value)
        entries.append(
            {
                "path": path,
                "sha256": by_path[path]["sha256"],
                "title": card["title"],
                "relation": card["relation"],
                "identities": identities,
                "aliases": card["aliases"],
                "found_in_run": card["provenance"]["found_in_run"],
                "found_by_role": card["provenance"]["found_by_role"],
                "also_found_in": card["also_found_in"],
            }
        )
    index = {
        "schema_version": REFERENCE_INDEX_SCHEMA_VERSION,
        "kind": "reference_index",
        "source_run_id": normalized_run_id,
        "generation": generation,
        "summary_sha256": summary_sha256,
        "papers_sha256": _canonical_digest(records),
        "entries": entries,
    }
    return (
        json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def validate_reference_index(
    papers_dir: Path,
    raw: bytes,
    *,
    summary_sha256: str,
) -> dict[str, Any]:
    """Validate an index against the exact current paper-card collection."""

    try:
        value = parse_json_object(raw, label="reference index")
    except StrictJsonError as exc:
        raise LiteratureRecordValidationError(str(exc)) from exc
    if (
        value.get("schema_version") != REFERENCE_INDEX_SCHEMA_VERSION
        or value.get("kind") != "reference_index"
    ):
        raise LiteratureRecordValidationError(
            "reference index schema or kind is invalid"
        )
    source_run_id = value.get("source_run_id")
    generation = value.get("generation")
    expected = json.loads(
        build_reference_index(
            papers_dir,
            source_run_id=source_run_id,
            generation=generation,
            summary_sha256=summary_sha256,
        )
    )
    if value != expected:
        raise LiteratureRecordValidationError(
            "reference index does not match the current paper cards"
        )
    return value
