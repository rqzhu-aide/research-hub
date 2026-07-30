"""Freshness derivation for method-bound phase results.

Compares a finalized run's frozen method identity against the currently
published method catalog to determine whether the run is still current.

This module is intentionally small. It answers one question:
  "Was this run done with the method as it exists now?"

The answer drives a UI badge (fresh / stale / unknown) on the phase tab.
It does NOT control context assembly or Phase 5 gating. Those use their
own existing logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


_BRANCH_PHASES = frozenset({
    "03-idea-evaluation",
    "04-draft-assembly",
    "05-review-revision",
})


def is_method_bound_phase(phase_slug: str) -> bool:
    """True for P3, P4, P5 (phases tied to a method branch)."""

    return str(phase_slug).strip() in _BRANCH_PHASES


def derive_freshness(
    project_dir: str | Path,
    phase_slug: str,
    method_stable_id: str,
    *,
    run_version: str = "",
    run_definition_sha256: str = "",
) -> str:
    """Compare a run's frozen method identity to the published catalog.

    Returns one of:
      - ``"fresh"``: version and digest match the active catalog entry
      - ``"stale"``: the method has been revised since this run
      - ``"unknown"``: the identity cannot be determined

    Parameters
    ----------
    project_dir
        Project root directory.
    phase_slug
        The phase the run belongs to.
    method_stable_id
        The method's stable ID from the run's frozen selection.
    run_version
        The version frozen into the run's manifest (may differ from current).
    run_definition_sha256
        The definition digest frozen into the run's manifest.
    """

    method_id = str(method_stable_id).strip()
    if not method_id:
        return "unknown"

    # Read the current published catalog entry for this method
    from core import method_menu

    entry, error = method_menu.find_selectable_entry(project_dir, method_id)
    if entry is None:
        if error and "retired" in error.lower():
            return "stale"  # Method was explicitly retired
        return "unknown"  # Catalog not published or method not found

    active_version = str(entry.get("version", "")).strip()
    try:
        active_sha = method_menu.method_definition_sha256(entry)
    except method_menu.MethodMenuValidationError:
        return "unknown"

    run_ver = str(run_version).strip()
    run_sha = str(run_definition_sha256).strip().lower()

    if not run_ver or not run_sha:
        # Pre-method-menu runs (method_selection was null in manifest)
        return "unknown"

    if run_ver == active_version and run_sha == active_sha:
        return "fresh"

    return "stale"


def get_run_freshness(
    project_dir: str | Path,
    phase_slug: str,
    run_id: str,
) -> str:
    """Resolve a run's freshness by reading its sealed manifest.

    Convenience wrapper: reads the manifest, extracts the frozen method
    identity, then calls :func:`derive_freshness`.
    """

    from core import launch_manifest

    root = Path(project_dir).resolve()
    try:
        manifest = launch_manifest._read_manifest(root, phase_slug, run_id)
    except Exception:
        return "unknown"

    selection = manifest.get("method_selection")
    if not isinstance(selection, Mapping):
        return "unknown"

    stable_id = str(selection.get("stable_id", "")).strip()
    version = str(selection.get("version", "")).strip()

    snapshots = manifest.get("snapshots")
    selected_method = (
        snapshots.get("selected_method") if isinstance(snapshots, Mapping) else None
    )
    schema_version = manifest.get("schema_version", 1)
    digest_field = (
        "definition_sha256"
        if type(schema_version) is int and schema_version >= 14
        else "sha256"
    )
    sha = (
        str(selected_method.get(digest_field, "")).strip().lower()
        if isinstance(selected_method, Mapping)
        else ""
    )

    return derive_freshness(
        root, phase_slug, stable_id,
        run_version=version, run_definition_sha256=sha,
    )


# ---------------------------------------------------------------------------
# Test helper (not part of public API)
# ---------------------------------------------------------------------------


def _write_test_catalog(
    project_dir: str | Path,
    stable_id: str,
    *,
    version: str = "v1",
    status: str = "recommended",
    label: str = "Test Method",
    number: int = 1,
) -> str:
    """Write a minimal method catalog entry for testing.

    Returns the mathematical-definition SHA-256 digest.
    """

    root = Path(project_dir).resolve()
    menu_dir = root / "ideas" / "methods"
    menu_dir.mkdir(parents=True, exist_ok=True)
    path = menu_dir / f"{stable_id}.md"
    definition = "Method body for testing."
    body = f"""---
stable_id: {stable_id}
version: {version}
status: {status}
label: {label}
number: {number}
---

# {label}

## Mathematical definition

{definition}
"""
    raw = body.encode("utf-8")
    path.write_bytes(raw)
    import hashlib
    return hashlib.sha256(definition.encode("utf-8")).hexdigest()
