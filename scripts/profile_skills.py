"""Safe provisioning of Research Hub's bundled skills into Hermes profiles.

The functions that inspect profiles are read-only.  A profile is changed only
through :func:`provision_skill` or :func:`provision_profile_skills`, which are
intended to be called after an explicit user action in the Web UI.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence
from urllib.parse import urlsplit


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = APP_ROOT / "bundled_skills" / "manifest.json"
SIDECAR_NAME = ".research-hub-skills.json"
LOCK_NAME = ".research-hub-skills.lock"
BACKUP_DIRECTORY_NAME = ".research-hub-skill-backups"
MANIFEST_SCHEMA_VERSION = 1
SIDECAR_SCHEMA_VERSION = 1

MAX_MANIFEST_BYTES = 256 * 1024
MAX_SIDECAR_BYTES = 256 * 1024
MAX_BUNDLE_FILES = 4_096
MAX_BUNDLE_FILE_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_BYTES = 64 * 1024 * 1024
MAX_RELATIVE_PATH_BYTES = 1_024
MAX_PROFILE_CONFIG_BYTES = 2 * 1024 * 1024

PROFILE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
RESERVED_PROFILE_NAMES = frozenset({"hermes", "test", "tmp", "root", "sudo"})
SKILL_NAME_RE = PROFILE_NAME_RE
ROLE_NAME_RE = PROFILE_NAME_RE
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")

STATUS_STATES = frozenset(
    {"profile_missing", "missing", "current", "modified", "conflict", "invalid"}
)


class ProfileSkillsError(RuntimeError):
    """Base error for bundle inspection and profile provisioning."""


class RootResolutionError(ProfileSkillsError, ValueError):
    """The Hermes root cannot be resolved safely."""


class ProfileNameError(ProfileSkillsError, ValueError):
    """A Hermes profile name is not canonical."""


class ManifestValidationError(ProfileSkillsError, ValueError):
    """The bundled skill manifest is malformed or inconsistent."""


class BundleValidationError(ProfileSkillsError, ValueError):
    """A skill bundle contains unsafe or unexpected content."""


class ProfileNotFoundError(ProfileSkillsError, FileNotFoundError):
    """The requested Hermes profile does not exist."""


class UnsafeProfileError(ProfileSkillsError, ValueError):
    """A profile path or its installation metadata is unsafe."""


class SkillConflictError(ProfileSkillsError):
    """A different skill copy exists and replacement was not authorized."""


class ProvisioningError(ProfileSkillsError):
    """A requested profile change could not be completed safely."""


@dataclass(frozen=True)
class BundledSkill:
    """One validated skill entry in the bundle manifest."""

    name: str
    directory: str
    digest: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class SkillManifest:
    """A validated bundle manifest and its source identity."""

    path: Path
    source_repository: str
    source_revision: str
    skills: Mapping[str, BundledSkill]

    @property
    def bundle_root(self) -> Path:
        return self.path.parent


@dataclass(frozen=True)
class SkillStatus:
    """Read-only assessment of one recommended skill in one profile."""

    profile: str
    profile_path: str
    skill: str
    state: str
    reason: str
    expected_digest: str
    installed_digest: str | None
    source_revision: str
    managed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProvisionResult:
    """Result of one explicit provisioning action."""

    profile: str
    skill: str
    action: str
    status: SkillStatus
    backup_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.to_dict()
        return result


@dataclass(frozen=True)
class _BundleSnapshot:
    files: tuple[tuple[str, bytes, int], ...]
    directories: tuple[str, ...]
    digest: str


@dataclass(frozen=True)
class _SidecarSnapshot:
    existed: bool
    payload: bytes | None
    mode: int


_PROVISION_LOCK = threading.RLock()


def _absolute(path: str | os.PathLike[str]) -> Path:
    value = os.fspath(path)
    if not value or "\x00" in value:
        raise RootResolutionError("Hermes root paths must be nonempty and contain no NUL")
    return Path(os.path.abspath(os.path.expanduser(value)))


def resolve_hermes_root(
    *,
    environ: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
    platform_name: str | None = None,
) -> Path:
    """Resolve the Hermes base directory without changing the filesystem.

    ``RESEARCH_HUB_HERMES_ROOT`` is an explicit base-directory override.
    ``HERMES_HOME`` may identify either the base directory or a named profile
    at ``<base>/profiles/<name>``.  The remaining defaults follow the native
    Hermes locations on Windows and POSIX systems.
    """

    env = os.environ if environ is None else environ
    override = str(env.get("RESEARCH_HUB_HERMES_ROOT", "")).strip()
    if override:
        return _absolute(override)

    platform_value = os.name if platform_name is None else platform_name
    is_windows = platform_value.casefold() in {"nt", "windows", "win32"}
    if is_windows:
        local_app_data = str(env.get("LOCALAPPDATA", "")).strip()
        home_path = Path.home() if home is None else Path(home)
        base = Path(local_app_data) if local_app_data else home_path / "AppData" / "Local"
        native_root = _absolute(base / "hermes")
    else:
        home_path = Path.home() if home is None else Path(home)
        native_root = _absolute(home_path / ".hermes")

    configured_home = str(env.get("HERMES_HOME", "")).strip()
    if configured_home:
        candidate = _absolute(configured_home)
        try:
            candidate.relative_to(native_root)
        except ValueError:
            if candidate.parent.name.casefold() == "profiles" and candidate.name:
                return candidate.parent.parent
            return candidate
        return native_root
    return native_root


def validate_profile_name(profile_name: str) -> str:
    """Return a canonical profile name or raise ``ProfileNameError``."""

    if not isinstance(profile_name, str) or not PROFILE_NAME_RE.fullmatch(profile_name):
        raise ProfileNameError(
            "profile names must match [a-z0-9][a-z0-9_-]{0,63} exactly"
        )
    if profile_name in RESERVED_PROFILE_NAMES:
        raise ProfileNameError(f"{profile_name!r} is reserved by Hermes")
    return profile_name


def profile_home(
    profile_name: str | None = "default",
    *,
    hermes_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
    platform_name: str | None = None,
) -> Path:
    """Return the Hermes home for a named profile or the default profile."""

    root = (
        _absolute(hermes_root)
        if hermes_root is not None
        else resolve_hermes_root(environ=environ, home=home, platform_name=platform_name)
    )
    if profile_name is None or profile_name == "default":
        return root
    name = validate_profile_name(profile_name)
    return root / "profiles" / name


def _metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(
        reparse_flag
        and getattr(metadata, "st_file_attributes", 0) & reparse_flag
    )


def _safe_lstat(path: Path, *, label: str) -> os.stat_result:
    try:
        return path.lstat()
    except OSError as exc:
        raise UnsafeProfileError(f"{label} cannot be inspected safely: {path}") from exc


def _read_regular_file(
    path: Path,
    *,
    maximum: int,
    label: str,
    validation_error: type[ProfileSkillsError],
) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise validation_error(f"{label} cannot be inspected: {path}") from exc
    if _metadata_is_link_or_reparse(before) or not stat.S_ISREG(before.st_mode):
        raise validation_error(f"{label} must be a regular file without links: {path}")
    if before.st_size > maximum:
        raise validation_error(f"{label} exceeds the {maximum:,}-byte limit: {path}")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise validation_error(f"{label} cannot be opened safely: {path}") from exc
    try:
        opened = os.fstat(descriptor)
        if _metadata_is_link_or_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise validation_error(f"{label} changed while it was being opened: {path}")
        if not os.path.samestat(before, opened):
            raise validation_error(f"{label} changed while it was being opened: {path}")
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, min(256 * 1024, maximum + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise validation_error(
                    f"{label} exceeds the {maximum:,}-byte limit: {path}"
                )
        after = os.fstat(descriptor)
        if not os.path.samestat(opened, after) or after.st_size != size:
            raise validation_error(f"{label} changed while it was being read: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _json_without_duplicates(payload: bytes, *, label: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ManifestValidationError(f"{label} repeats the field {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=object_pairs)
    except ManifestValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError(f"{label} is not valid UTF-8 JSON") from exc


def _require_exact_keys(value: Any, keys: set[str], *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ManifestValidationError(
            f"{label} must contain exactly: {', '.join(sorted(keys))}"
        )
    return value


def _validate_repository(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 2_048:
        raise ManifestValidationError("manifest source.repository must be an HTTPS URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ManifestValidationError("manifest source.repository must be a plain HTTPS URL")
    return value


def _validate_relative_name(name: str, *, label: str) -> None:
    encoded = name.encode("utf-8")
    if len(encoded) > MAX_RELATIVE_PATH_BYTES or "\\" in name or "\x00" in name:
        raise BundleValidationError(f"{label} contains an unsafe relative path")
    for part in name.split("/"):
        if not part or part in {".", ".."}:
            raise BundleValidationError(f"{label} contains an unsafe relative path")


def _snapshot_directory(path: Path, *, label: str) -> _BundleSnapshot:
    try:
        root_metadata = path.lstat()
    except OSError as exc:
        raise BundleValidationError(f"{label} is unavailable: {path}") from exc
    if _metadata_is_link_or_reparse(root_metadata) or not stat.S_ISDIR(
        root_metadata.st_mode
    ):
        raise BundleValidationError(f"{label} must be a directory without links: {path}")

    pending: list[tuple[Path, str, os.stat_result]] = [(path, "", root_metadata)]
    files: list[tuple[str, bytes, int]] = []
    directories: list[str] = []
    total_bytes = 0
    entry_count = 0
    casefolded_paths: set[str] = set()

    while pending:
        directory, prefix, initial_directory_metadata = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError as exc:
            raise BundleValidationError(f"{label} cannot be scanned: {directory}") from exc

        for entry in entries:
            entry_count += 1
            if entry_count > MAX_BUNDLE_FILES:
                raise BundleValidationError(
                    f"{label} exceeds the {MAX_BUNDLE_FILES:,}-entry limit"
                )
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            relative = relative.replace(os.sep, "/")
            _validate_relative_name(relative, label=label)
            folded = relative.casefold()
            if folded in casefolded_paths:
                raise BundleValidationError(
                    f"{label} contains paths that collide by case: {relative}"
                )
            casefolded_paths.add(folded)

            entry_path = Path(entry.path)
            try:
                # Path.lstat supplies stable file identities on Windows, where
                # DirEntry.stat can expose zero device and inode values.
                metadata = entry_path.lstat()
            except OSError as exc:
                raise BundleValidationError(
                    f"{label} entry cannot be inspected: {relative}"
                ) from exc
            if _metadata_is_link_or_reparse(metadata):
                raise BundleValidationError(
                    f"{label} must not contain links or reparse points: {relative}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                directories.append(relative)
                pending.append((entry_path, relative, metadata))
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise BundleValidationError(
                    f"{label} must contain only regular files and directories: {relative}"
                )
            if getattr(metadata, "st_nlink", 1) > 1:
                raise BundleValidationError(f"{label} must not contain hard links: {relative}")
            payload = _read_regular_file(
                entry_path,
                maximum=MAX_BUNDLE_FILE_BYTES,
                label=f"{label} file {relative}",
                validation_error=BundleValidationError,
            )
            total_bytes += len(payload)
            if total_bytes > MAX_BUNDLE_BYTES:
                raise BundleValidationError(
                    f"{label} exceeds the {MAX_BUNDLE_BYTES:,}-byte aggregate limit"
                )
            files.append((relative, payload, stat.S_IMODE(metadata.st_mode)))

        try:
            final_directory_metadata = directory.lstat()
        except OSError as exc:
            raise BundleValidationError(
                f"{label} changed while it was being scanned: {directory}"
            ) from exc
        if (
            _metadata_is_link_or_reparse(final_directory_metadata)
            or not stat.S_ISDIR(final_directory_metadata.st_mode)
            or not os.path.samestat(initial_directory_metadata, final_directory_metadata)
        ):
            raise BundleValidationError(
                f"{label} changed while it was being scanned: {directory}"
            )

    files.sort(key=lambda item: item[0])
    digest = hashlib.sha256()
    for relative, payload, _mode in files:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(payload)
        digest.update(b"\x00")
    return _BundleSnapshot(
        files=tuple(files),
        directories=tuple(sorted(directories)),
        digest=digest.hexdigest(),
    )


def bundle_digest(path: str | os.PathLike[str]) -> str:
    """Return the canonical digest of a safe, bounded bundle directory."""

    return _snapshot_directory(Path(path), label="skill bundle").digest


def load_manifest(
    *,
    app_root: str | os.PathLike[str] | None = None,
    manifest_path: str | os.PathLike[str] | None = None,
) -> SkillManifest:
    """Load the strict manifest and verify every referenced skill bundle."""

    if manifest_path is not None:
        path = _absolute(manifest_path)
    else:
        root = APP_ROOT if app_root is None else _absolute(app_root)
        path = root / "bundled_skills" / "manifest.json"
    payload = _read_regular_file(
        path,
        maximum=MAX_MANIFEST_BYTES,
        label="bundled skill manifest",
        validation_error=ManifestValidationError,
    )
    document = _json_without_duplicates(payload, label="bundled skill manifest")
    top = _require_exact_keys(
        document, {"schema_version", "source", "skills"}, label="manifest"
    )
    if type(top["schema_version"]) is not int or top["schema_version"] != 1:
        raise ManifestValidationError("manifest schema_version must be 1")
    source = _require_exact_keys(
        top["source"], {"repository", "revision"}, label="manifest source"
    )
    repository = _validate_repository(source["repository"])
    revision = source["revision"]
    if not isinstance(revision, str) or not REVISION_RE.fullmatch(revision):
        raise ManifestValidationError("manifest source.revision must be a 40-digit hash")

    raw_skills = top["skills"]
    if not isinstance(raw_skills, dict) or not raw_skills or len(raw_skills) > 32:
        raise ManifestValidationError("manifest skills must be a nonempty mapping")
    skills: dict[str, BundledSkill] = {}
    for name, raw_skill in raw_skills.items():
        if not isinstance(name, str) or not SKILL_NAME_RE.fullmatch(name):
            raise ManifestValidationError(f"manifest skill name is invalid: {name!r}")
        item = _require_exact_keys(
            raw_skill, {"directory", "digest", "roles"}, label=f"skill {name!r}"
        )
        directory = item["directory"]
        if directory != name:
            raise ManifestValidationError(
                f"skill {name!r} directory must match its canonical name"
            )
        expected_digest = item["digest"]
        if not isinstance(expected_digest, str) or not SHA256_RE.fullmatch(
            expected_digest
        ):
            raise ManifestValidationError(f"skill {name!r} digest must be SHA-256")
        raw_roles = item["roles"]
        if not isinstance(raw_roles, list) or not raw_roles:
            raise ManifestValidationError(f"skill {name!r} roles must be nonempty")
        roles: list[str] = []
        for role in raw_roles:
            if not isinstance(role, str) or not ROLE_NAME_RE.fullmatch(role):
                raise ManifestValidationError(
                    f"skill {name!r} has an invalid role: {role!r}"
                )
            if role in roles:
                raise ManifestValidationError(
                    f"skill {name!r} repeats the role {role!r}"
                )
            roles.append(role)
        snapshot = _snapshot_directory(path.parent / directory, label=f"skill {name!r}")
        if snapshot.digest != expected_digest:
            raise ManifestValidationError(
                f"skill {name!r} digest does not match the bundled files"
            )
        skills[name] = BundledSkill(
            name=name,
            directory=directory,
            digest=expected_digest,
            roles=tuple(roles),
        )
    return SkillManifest(
        path=path,
        source_repository=repository,
        source_revision=revision,
        skills=skills,
    )


def role_requirements(
    role: str,
    *,
    manifest: SkillManifest | None = None,
    app_root: str | os.PathLike[str] | None = None,
    manifest_path: str | os.PathLike[str] | None = None,
) -> tuple[str, ...]:
    """Return the sorted recommended skill names for one team role."""

    if not isinstance(role, str) or not ROLE_NAME_RE.fullmatch(role):
        raise ValueError("role names must be canonical lowercase identifiers")
    loaded = manifest or load_manifest(app_root=app_root, manifest_path=manifest_path)
    return tuple(sorted(name for name, skill in loaded.skills.items() if role in skill.roles))


def profile_requirements(
    role_profiles: Mapping[str, str],
    *,
    manifest: SkillManifest | None = None,
    app_root: str | os.PathLike[str] | None = None,
    manifest_path: str | os.PathLike[str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Union role requirements for each profile, including shared profiles."""

    loaded = manifest or load_manifest(app_root=app_root, manifest_path=manifest_path)
    union: dict[str, set[str]] = {}
    for role, profile in role_profiles.items():
        if not isinstance(role, str) or not ROLE_NAME_RE.fullmatch(role):
            raise ValueError("role names must be canonical lowercase identifiers")
        validate_profile_name(profile)
        union.setdefault(profile, set()).update(
            role_requirements(role, manifest=loaded)
        )
    return {profile: tuple(sorted(skills)) for profile, skills in sorted(union.items())}


def _profile_path_state(profile: str, root: Path) -> tuple[Path, str | None]:
    target = profile_home(profile, hermes_root=root)
    components = [root]
    if profile != "default":
        components.extend((root / "profiles", target))
    for index, component in enumerate(components):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            if index == len(components) - 1 or index == 0:
                return target, "profile_missing"
            return target, "profile_missing"
        except OSError as exc:
            raise UnsafeProfileError(
                f"Hermes profile path cannot be inspected: {component}"
            ) from exc
        if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise UnsafeProfileError(
                f"Hermes profile paths must be directories without links: {component}"
            )
    config_path = target / "config.yaml"
    try:
        config_path.lstat()
    except FileNotFoundError:
        return target, "profile_missing"
    except OSError as exc:
        raise UnsafeProfileError(
            f"Hermes profile configuration cannot be inspected: {config_path}"
        ) from exc
    _read_regular_file(
        config_path,
        maximum=MAX_PROFILE_CONFIG_BYTES,
        label="Hermes profile configuration",
        validation_error=UnsafeProfileError,
    )
    return target, None


def configured_profile_home(
    profile_name: str,
    *,
    hermes_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
    platform_name: str | None = None,
) -> Path | None:
    """Return a safely configured profile home, or ``None`` when absent."""

    profile = validate_profile_name(profile_name)
    root = (
        _absolute(hermes_root)
        if hermes_root is not None
        else resolve_hermes_root(
            environ=environ,
            home=home,
            platform_name=platform_name,
        )
    )
    target, state = _profile_path_state(profile, root)
    return None if state == "profile_missing" else target


@contextmanager
def _profile_lock(profile_path: Path, timeout: float = 15.0) -> Iterator[None]:
    """Serialize provisioning for a profile across threads and processes."""

    try:
        profile_metadata = profile_path.lstat()
    except OSError as exc:
        raise ProvisioningError(
            f"profile directory is unavailable while locking: {profile_path}"
        ) from exc
    if _metadata_is_link_or_reparse(profile_metadata) or not stat.S_ISDIR(
        profile_metadata.st_mode
    ):
        raise ProvisioningError("profile directory must not be a link while locking")
    lock_path = profile_path / LOCK_NAME
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(lock_path, flags, 0o600)
        if os.name != "nt":
            os.fchmod(descriptor, 0o600)
        opened_metadata = os.fstat(descriptor)
        path_metadata = lock_path.lstat()
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise ProvisioningError(
            f"profile skill lock is unavailable: {lock_path}"
        ) from exc
    if (
        _metadata_is_link_or_reparse(path_metadata)
        or not stat.S_ISREG(opened_metadata.st_mode)
        or not os.path.samestat(opened_metadata, path_metadata)
    ):
        os.close(descriptor)
        raise ProvisioningError(
            f"profile skill lock must be a regular file without links: {lock_path}"
        )

    handle = os.fdopen(descriptor, "a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + timeout
    acquired = False
    try:
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise ProvisioningError(
                        f"timed out waiting for profile skill lock: {lock_path}"
                    )
                time.sleep(0.025)
        try:
            locked_metadata = os.fstat(handle.fileno())
            current_metadata = lock_path.lstat()
            current_profile_metadata = profile_path.lstat()
        except OSError as exc:
            raise ProvisioningError(
                f"profile skill lock changed while being acquired: {lock_path}"
            ) from exc
        if (
            _metadata_is_link_or_reparse(current_metadata)
            or not stat.S_ISREG(locked_metadata.st_mode)
            or not os.path.samestat(locked_metadata, current_metadata)
            or _metadata_is_link_or_reparse(current_profile_metadata)
            or not os.path.samestat(profile_metadata, current_profile_metadata)
        ):
            raise ProvisioningError(
                f"profile skill lock changed while being acquired: {lock_path}"
            )
        yield
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def _load_sidecar(profile_path: Path) -> dict[str, dict[str, str]]:
    path = profile_path / SIDECAR_NAME
    try:
        path.lstat()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise UnsafeProfileError(f"skill installation metadata cannot be inspected: {path}") from exc
    payload = _read_regular_file(
        path,
        maximum=MAX_SIDECAR_BYTES,
        label="skill installation metadata",
        validation_error=UnsafeProfileError,
    )
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnsafeProfileError("skill installation metadata is invalid") from exc
    if not isinstance(document, dict) or set(document) != {"schema_version", "skills"}:
        raise UnsafeProfileError("skill installation metadata has an invalid structure")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise UnsafeProfileError("skill installation metadata has an unsupported schema")
    raw_skills = document["skills"]
    if not isinstance(raw_skills, dict) or len(raw_skills) > 128:
        raise UnsafeProfileError("skill installation metadata has invalid skills")
    records: dict[str, dict[str, str]] = {}
    expected_keys = {
        "source_repository",
        "source_revision",
        "bundle_digest",
        "installed_at",
    }
    for name, record in raw_skills.items():
        if not isinstance(name, str) or not SKILL_NAME_RE.fullmatch(name):
            raise UnsafeProfileError("skill installation metadata has an invalid skill name")
        if not isinstance(record, dict) or set(record) != expected_keys:
            raise UnsafeProfileError(
                f"skill installation metadata for {name!r} has invalid fields"
            )
        if not all(isinstance(record[key], str) for key in expected_keys):
            raise UnsafeProfileError(
                f"skill installation metadata for {name!r} has invalid values"
            )
        if not SHA256_RE.fullmatch(record["bundle_digest"]):
            raise UnsafeProfileError(
                f"skill installation metadata for {name!r} has an invalid digest"
            )
        if not REVISION_RE.fullmatch(record["source_revision"]):
            raise UnsafeProfileError(
                f"skill installation metadata for {name!r} has an invalid revision"
            )
        records[name] = dict(record)
    return records


def _invalid_status(
    profile: str,
    profile_path: Path,
    skill: BundledSkill,
    manifest: SkillManifest,
    reason: str,
) -> SkillStatus:
    return SkillStatus(
        profile=profile,
        profile_path=str(profile_path),
        skill=skill.name,
        state="invalid",
        reason=reason,
        expected_digest=skill.digest,
        installed_digest=None,
        source_revision=manifest.source_revision,
        managed=False,
    )


def _skill_status_loaded(
    profile: str,
    skill: BundledSkill,
    manifest: SkillManifest,
    root: Path,
) -> SkillStatus:
    try:
        profile_path, path_state = _profile_path_state(profile, root)
    except UnsafeProfileError as exc:
        return _invalid_status(profile, profile_home(profile, hermes_root=root), skill, manifest, str(exc))
    if path_state == "profile_missing":
        return SkillStatus(
            profile=profile,
            profile_path=str(profile_path),
            skill=skill.name,
            state="profile_missing",
            reason="profile_missing",
            expected_digest=skill.digest,
            installed_digest=None,
            source_revision=manifest.source_revision,
            managed=False,
        )
    try:
        records = _load_sidecar(profile_path)
    except UnsafeProfileError as exc:
        return _invalid_status(profile, profile_path, skill, manifest, str(exc))

    skills_path = profile_path / "skills"
    try:
        skills_metadata = skills_path.lstat()
    except FileNotFoundError:
        skills_metadata = None
    except OSError as exc:
        return _invalid_status(profile, profile_path, skill, manifest, str(exc))
    if skills_metadata is not None and (
        _metadata_is_link_or_reparse(skills_metadata)
        or not stat.S_ISDIR(skills_metadata.st_mode)
    ):
        return _invalid_status(
            profile, profile_path, skill, manifest, "profile skills path is unsafe"
        )

    destination = skills_path / skill.name
    try:
        destination.lstat()
    except FileNotFoundError:
        return SkillStatus(
            profile=profile,
            profile_path=str(profile_path),
            skill=skill.name,
            state="missing",
            reason="missing",
            expected_digest=skill.digest,
            installed_digest=None,
            source_revision=manifest.source_revision,
            managed=skill.name in records,
        )
    except OSError as exc:
        return _invalid_status(profile, profile_path, skill, manifest, str(exc))

    try:
        installed_digest = _snapshot_directory(
            destination, label=f"installed skill {skill.name!r}"
        ).digest
    except BundleValidationError as exc:
        return _invalid_status(profile, profile_path, skill, manifest, str(exc))
    record = records.get(skill.name)
    managed = record is not None
    if installed_digest == skill.digest:
        reason = "current_managed" if managed else "current_unmanaged"
        return SkillStatus(
            profile=profile,
            profile_path=str(profile_path),
            skill=skill.name,
            state="current",
            reason=reason,
            expected_digest=skill.digest,
            installed_digest=installed_digest,
            source_revision=manifest.source_revision,
            managed=managed,
        )
    if record is None:
        state, reason = "conflict", "unmanaged_conflict"
    elif installed_digest == record["bundle_digest"]:
        state, reason = "modified", "managed_outdated"
    else:
        state, reason = "modified", "managed_modified"
    return SkillStatus(
        profile=profile,
        profile_path=str(profile_path),
        skill=skill.name,
        state=state,
        reason=reason,
        expected_digest=skill.digest,
        installed_digest=installed_digest,
        source_revision=manifest.source_revision,
        managed=managed,
    )


def skill_status(
    profile_name: str,
    skill_name: str,
    *,
    manifest: SkillManifest | None = None,
    app_root: str | os.PathLike[str] | None = None,
    manifest_path: str | os.PathLike[str] | None = None,
    hermes_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
    platform_name: str | None = None,
) -> SkillStatus:
    """Inspect one profile skill without changing profile files."""

    profile = validate_profile_name(profile_name)
    loaded = manifest or load_manifest(app_root=app_root, manifest_path=manifest_path)
    if skill_name not in loaded.skills:
        raise KeyError(f"unknown bundled skill: {skill_name}")
    root = (
        _absolute(hermes_root)
        if hermes_root is not None
        else resolve_hermes_root(environ=environ, home=home, platform_name=platform_name)
    )
    return _skill_status_loaded(profile, loaded.skills[skill_name], loaded, root)


def profile_skill_statuses(
    profile_name: str,
    skill_names: Sequence[str] | None = None,
    *,
    manifest: SkillManifest | None = None,
    app_root: str | os.PathLike[str] | None = None,
    manifest_path: str | os.PathLike[str] | None = None,
    hermes_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
    platform_name: str | None = None,
) -> dict[str, SkillStatus]:
    """Inspect a selected set of skills in one profile without mutation."""

    profile = validate_profile_name(profile_name)
    loaded = manifest or load_manifest(app_root=app_root, manifest_path=manifest_path)
    names = sorted(loaded.skills) if skill_names is None else list(skill_names)
    unknown = sorted(set(names) - set(loaded.skills))
    if unknown:
        raise KeyError("unknown bundled skills: " + ", ".join(unknown))
    root = (
        _absolute(hermes_root)
        if hermes_root is not None
        else resolve_hermes_root(environ=environ, home=home, platform_name=platform_name)
    )
    return {
        name: _skill_status_loaded(profile, loaded.skills[name], loaded, root)
        for name in names
    }


def _capture_sidecar(profile_path: Path) -> _SidecarSnapshot:
    """Capture exact sidecar bytes before a provisioning transaction."""

    sidecar = profile_path / SIDECAR_NAME
    try:
        metadata = sidecar.lstat()
    except FileNotFoundError:
        return _SidecarSnapshot(existed=False, payload=None, mode=0o600)
    except OSError as exc:
        raise UnsafeProfileError("skill installation metadata cannot be inspected") from exc
    if (
        _metadata_is_link_or_reparse(metadata) or not stat.S_ISREG(metadata.st_mode)
    ):
        raise UnsafeProfileError("skill installation metadata is not a safe regular file")
    payload = _read_regular_file(
        sidecar,
        maximum=MAX_SIDECAR_BYTES,
        label="skill installation metadata",
        validation_error=UnsafeProfileError,
    )
    return _SidecarSnapshot(
        existed=True,
        payload=payload,
        mode=stat.S_IMODE(metadata.st_mode),
    )


def _write_sidecar_payload(profile_path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    """Atomically write already validated sidecar bytes."""

    sidecar = profile_path / SIDECAR_NAME
    try:
        metadata = sidecar.lstat()
    except FileNotFoundError:
        metadata = None
    except OSError as exc:
        raise UnsafeProfileError("skill installation metadata cannot be inspected") from exc
    if metadata is not None and (
        _metadata_is_link_or_reparse(metadata) or not stat.S_ISREG(metadata.st_mode)
    ):
        raise UnsafeProfileError("skill installation metadata is not a safe regular file")
    payload = bytes(payload)
    if len(payload) > MAX_SIDECAR_BYTES:
        raise ProvisioningError("skill installation metadata exceeds its safety limit")
    temporary = profile_path / f".{SIDECAR_NAME}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, flags, mode)
        if os.name != "nt":
            os.fchmod(descriptor, mode)
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ProvisioningError("skill installation metadata write stopped early")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, sidecar)
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def _write_sidecar(
    profile_path: Path,
    records: Mapping[str, Mapping[str, str]],
) -> None:
    payload = (
        json.dumps(
            {"schema_version": SIDECAR_SCHEMA_VERSION, "skills": records},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    _write_sidecar_payload(profile_path, payload)


def _sidecar_record(manifest: SkillManifest, skill: BundledSkill) -> dict[str, str]:
    return {
        "source_repository": manifest.source_repository,
        "source_revision": manifest.source_revision,
        "bundle_digest": skill.digest,
        "installed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _ensure_skills_directory(profile_path: Path) -> tuple[Path, bool]:
    skills_path = profile_path / "skills"
    try:
        metadata = skills_path.lstat()
    except FileNotFoundError:
        try:
            os.mkdir(skills_path, 0o700)
        except FileExistsError:
            pass
        metadata = _safe_lstat(skills_path, label="profile skills directory")
        created = True
    else:
        created = False
    if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise UnsafeProfileError("profile skills path must be a directory without links")
    return skills_path, created


def _stage_snapshot(skills_path: Path, skill: BundledSkill, snapshot: _BundleSnapshot) -> Path:
    staging = skills_path / f".{skill.name}.install-{uuid.uuid4().hex}"
    try:
        os.mkdir(staging, 0o700)
        for relative in snapshot.directories:
            (staging / Path(*relative.split("/"))).mkdir(mode=0o700, parents=True)
        for relative, payload, source_mode in snapshot.files:
            target = staging / Path(*relative.split("/"))
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            mode = 0o755 if source_mode & 0o111 else 0o644
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                mode,
            )
            try:
                view = memoryview(payload)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        raise ProvisioningError(f"copy stopped early for {relative}")
                    view = view[written:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        staged_digest = _snapshot_directory(staging, label=f"staged skill {skill.name!r}").digest
        if staged_digest != skill.digest:
            raise ProvisioningError("staged skill digest does not match the manifest")
        return staging
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _ensure_backup_directory(profile_path: Path) -> tuple[Path, bool]:
    backup_root = profile_path / BACKUP_DIRECTORY_NAME
    try:
        metadata = backup_root.lstat()
    except FileNotFoundError:
        try:
            os.mkdir(backup_root, 0o700)
        except FileExistsError:
            pass
        metadata = _safe_lstat(backup_root, label="profile skill backup directory")
        created = True
    else:
        created = False
    if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise UnsafeProfileError(
            "profile skill backup path must be a directory without links"
        )
    return backup_root, created


def _backup_path(backup_root: Path, skill_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return backup_root / f"{skill_name}.backup-{timestamp}"


def _recovery_path(backup_root: Path, label: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return backup_root / f"{label}.rollback-{timestamp}-{uuid.uuid4().hex[:8]}"


def _preserve_for_recovery(source: Path, backup_root: Path, *, label: str) -> Path | None:
    """Move a possibly externally changed path aside without traversing it."""

    try:
        source.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ProvisioningError(f"rollback path cannot be inspected: {source}") from exc
    recovery = _recovery_path(backup_root, label)
    try:
        os.rename(source, recovery)
    except OSError as exc:
        raise ProvisioningError(
            f"rollback content could not be preserved safely: {source}"
        ) from exc
    return recovery


def _restore_sidecar(
    profile_path: Path,
    snapshot: _SidecarSnapshot,
    backup_root: Path,
) -> Path | None:
    """Restore exact prior sidecar bytes and preserve the current sidecar."""

    sidecar = profile_path / SIDECAR_NAME
    preserved = _preserve_for_recovery(
        sidecar,
        backup_root,
        label="skill-metadata",
    )
    if snapshot.existed:
        if snapshot.payload is None:
            raise ProvisioningError("prior skill metadata snapshot is incomplete")
        _write_sidecar_payload(profile_path, snapshot.payload, mode=snapshot.mode)
    return preserved


def _rollback_destination(
    destination: Path,
    prior_backup: Path | None,
    backup_root: Path,
    *,
    skill_name: str,
) -> Path | None:
    """Restore the prior destination and preserve the candidate being removed."""

    preserved = _preserve_for_recovery(
        destination,
        backup_root,
        label=f"{skill_name}.candidate",
    )
    if prior_backup is not None:
        try:
            os.rename(prior_backup, destination)
        except OSError as exc:
            raise ProvisioningError(
                f"prior {skill_name} installation could not be restored"
            ) from exc
    return preserved


def _verify_current_installation(
    profile: str,
    skill: BundledSkill,
    manifest: SkillManifest,
    root: Path,
    expected_record: Mapping[str, str],
) -> SkillStatus:
    """Verify both installed bytes and the exact management record."""

    status = _skill_status_loaded(profile, skill, manifest, root)
    if status.state != "current":
        raise ProvisioningError(
            f"installed {skill.name} did not verify as current: {status.reason}"
        )
    records = _load_sidecar(Path(status.profile_path))
    if records.get(skill.name) != dict(expected_record):
        raise ProvisioningError(
            f"installed {skill.name} management record changed during verification"
        )
    return status


def provision_skill(
    profile_name: str,
    skill_name: str,
    *,
    replace: bool = False,
    expected_status: SkillStatus | None = None,
    manifest: SkillManifest | None = None,
    app_root: str | os.PathLike[str] | None = None,
    manifest_path: str | os.PathLike[str] | None = None,
    hermes_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
    platform_name: str | None = None,
) -> ProvisionResult:
    """Install one bundled skill after an explicit user request.

    A differing existing directory is preserved unless ``replace=True``.  A
    replacement first moves the old directory to a timestamped backup.  Any
    subsequent failure restores that backup before the error is returned.
    When supplied, ``expected_status`` is checked under the profile lock before
    any mutation.
    """

    profile = validate_profile_name(profile_name)
    loaded = manifest or load_manifest(app_root=app_root, manifest_path=manifest_path)
    if skill_name not in loaded.skills:
        raise KeyError(f"unknown bundled skill: {skill_name}")
    skill = loaded.skills[skill_name]
    root = (
        _absolute(hermes_root)
        if hermes_root is not None
        else resolve_hermes_root(environ=environ, home=home, platform_name=platform_name)
    )
    try:
        initial_profile_path, initial_state = _profile_path_state(profile, root)
    except UnsafeProfileError:
        raise
    if initial_state == "profile_missing":
        raise ProfileNotFoundError(f"Hermes profile does not exist: {profile}")

    with _PROVISION_LOCK, _profile_lock(initial_profile_path):
        status = _skill_status_loaded(profile, skill, loaded, root)
        if expected_status is not None:
            if not isinstance(expected_status, SkillStatus):
                raise TypeError("expected_status must be a SkillStatus")
            if status != expected_status:
                raise SkillConflictError(
                    f"{skill.name} changed after the installation was reviewed; "
                    "reload its status before trying again"
                )
        if status.state == "profile_missing":
            raise ProfileNotFoundError(f"Hermes profile does not exist: {profile}")
        if status.state == "invalid":
            raise UnsafeProfileError(status.reason)
        if status.state in {"modified", "conflict"} and not replace:
            raise SkillConflictError(
                f"{skill.name} differs from the bundled copy; explicit replacement is required"
            )

        profile_path = Path(status.profile_path)
        prior_sidecar = _capture_sidecar(profile_path)
        records = _load_sidecar(profile_path)
        new_record = _sidecar_record(loaded, skill)
        existing_record = records.get(skill.name)
        if status.state == "current":
            record_matches = (
                existing_record is not None
                and existing_record["source_repository"] == loaded.source_repository
                and existing_record["source_revision"] == loaded.source_revision
                and existing_record["bundle_digest"] == skill.digest
            )
            if record_matches:
                return ProvisionResult(
                    profile=profile,
                    skill=skill.name,
                    action="already_current",
                    status=status,
                )
            records[skill.name] = new_record
            try:
                _write_sidecar(profile_path, records)
                adopted = _verify_current_installation(
                    profile,
                    skill,
                    loaded,
                    root,
                    new_record,
                )
            except Exception as exc:
                backup_root, created_backup_root = _ensure_backup_directory(
                    profile_path
                )
                try:
                    _restore_sidecar(profile_path, prior_sidecar, backup_root)
                except Exception as rollback_exc:
                    raise ProvisioningError(
                        "skill adoption failed and prior metadata could not be restored"
                    ) from rollback_exc
                finally:
                    if created_backup_root:
                        try:
                            backup_root.rmdir()
                        except OSError:
                            pass
                raise ProvisioningError(
                    "skill adoption failed; prior metadata was restored"
                ) from exc
            return ProvisionResult(
                profile=profile, skill=skill.name, action="adopted", status=adopted
            )

        source_snapshot = _snapshot_directory(
            loaded.bundle_root / skill.directory, label=f"skill {skill.name!r}"
        )
        if source_snapshot.digest != skill.digest:
            raise ManifestValidationError(
                f"skill {skill.name!r} changed after manifest validation"
            )
        skills_path, created_skills_path = _ensure_skills_directory(profile_path)
        destination = skills_path / skill.name
        staging = _stage_snapshot(skills_path, skill, source_snapshot)
        backup: Path | None = None
        backup_root: Path | None = None
        created_backup_root = False
        transaction_started = False
        sidecar_attempted = False
        try:
            if status.state == "missing":
                try:
                    destination.lstat()
                except FileNotFoundError:
                    pass
                else:
                    raise SkillConflictError(
                        f"{skill.name} appeared while installation was being prepared"
                    )
                os.rename(staging, destination)
                transaction_started = True
            else:
                current = _skill_status_loaded(profile, skill, loaded, root)
                if (
                    current.state != status.state
                    or current.installed_digest != status.installed_digest
                ):
                    raise SkillConflictError(
                        f"{skill.name} changed while replacement was being prepared"
                    )
                backup_root, created_backup_root = _ensure_backup_directory(profile_path)
                backup = _backup_path(backup_root, skill.name)
                os.rename(destination, backup)
                transaction_started = True
                os.rename(staging, destination)

            records[skill.name] = new_record
            sidecar_attempted = True
            _write_sidecar(profile_path, records)
            final_status = _verify_current_installation(
                profile,
                skill,
                loaded,
                root,
                new_record,
            )
            action = (
                "installed"
                if backup is None and status.state == "missing"
                else "replaced"
            )
            return ProvisionResult(
                profile=profile,
                skill=skill.name,
                action=action,
                status=final_status,
                backup_path=str(backup) if backup is not None else None,
            )
        except Exception as exc:
            if not transaction_started:
                raise
            rollback_errors: list[Exception] = []
            try:
                if backup_root is None:
                    backup_root, created_backup_root = _ensure_backup_directory(
                        profile_path
                    )
                _rollback_destination(
                    destination,
                    backup,
                    backup_root,
                    skill_name=skill.name,
                )
                backup = None
            except Exception as rollback_exc:
                rollback_errors.append(rollback_exc)
            if sidecar_attempted:
                try:
                    if backup_root is None:
                        backup_root, created_backup_root = _ensure_backup_directory(
                            profile_path
                        )
                    _restore_sidecar(profile_path, prior_sidecar, backup_root)
                except Exception as rollback_exc:
                    rollback_errors.append(rollback_exc)
            if rollback_errors:
                raise ProvisioningError(
                    "skill provisioning failed and the prior state could not be fully restored"
                ) from rollback_errors[0]
            raise ProvisioningError(
                "skill provisioning failed; the prior installation and metadata were restored"
            ) from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            if created_skills_path:
                try:
                    skills_path.rmdir()
                except OSError:
                    pass
            if created_backup_root and backup_root is not None:
                try:
                    backup_root.rmdir()
                except OSError:
                    pass


def provision_profile_skills(
    profile_name: str,
    roles: Sequence[str],
    *,
    replace: bool = False,
    manifest: SkillManifest | None = None,
    app_root: str | os.PathLike[str] | None = None,
    manifest_path: str | os.PathLike[str] | None = None,
    hermes_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
    platform_name: str | None = None,
) -> tuple[ProvisionResult, ...]:
    """Provision the union of recommendations for roles sharing a profile."""

    loaded = manifest or load_manifest(app_root=app_root, manifest_path=manifest_path)
    names: set[str] = set()
    for role in roles:
        names.update(role_requirements(role, manifest=loaded))
    return tuple(
        provision_skill(
            profile_name,
            name,
            replace=replace,
            manifest=loaded,
            hermes_root=hermes_root,
            environ=environ,
            home=home,
            platform_name=platform_name,
        )
        for name in sorted(names)
    )


# Explicit aliases keep call sites readable without introducing separate behavior.
recommended_skills_for_role = role_requirements
recommended_skills_by_profile = profile_requirements
get_skill_status = skill_status
get_profile_skill_statuses = profile_skill_statuses
install_skill = provision_skill


__all__ = [
    "BundleValidationError",
    "BundledSkill",
    "ManifestValidationError",
    "ProfileNameError",
    "ProfileNotFoundError",
    "ProfileSkillsError",
    "ProvisionResult",
    "ProvisioningError",
    "RESERVED_PROFILE_NAMES",
    "RootResolutionError",
    "SIDECAR_NAME",
    "STATUS_STATES",
    "SkillConflictError",
    "SkillManifest",
    "SkillStatus",
    "UnsafeProfileError",
    "bundle_digest",
    "configured_profile_home",
    "get_profile_skill_statuses",
    "get_skill_status",
    "install_skill",
    "load_manifest",
    "profile_home",
    "profile_requirements",
    "profile_skill_statuses",
    "provision_profile_skills",
    "provision_skill",
    "recommended_skills_by_profile",
    "recommended_skills_for_role",
    "resolve_hermes_root",
    "role_requirements",
    "skill_status",
    "validate_profile_name",
]
