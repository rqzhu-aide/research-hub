"""Prepare explicit lifecycle data for the Research Hub web interface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import method_menu, project_state
from .launch_manifest import phase_requires_method_binding
from .launch_run import LaunchError, exact_rerun_options


MAX_REVIEW_TARGET_BYTES = 2 * 1024 * 1024
SOURCE_BASELINE_STATUS_BY_RUN_STATUS = {
    "approved": "accepted",
    "awaiting_review": "proposed",
    "revision_requested": "proposed",
    "superseded": "historical",
}


def decision_report_version(kind: str, report: Mapping[str, Any]) -> str:
    """Return the state layer's decision-report fingerprint."""

    return project_state.decision_report_version(kind, report)


def recovery_phase_config(
    project_dir: Path,
    phase_slug: str,
    phase_state: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a non-launchable display plan for a phase removed from config.

    The newest run's sealed manifest is preferred because it preserves the plan
    the user actually launched. A generic state-derived plan keeps cancellation
    and history reachable when that manifest is absent or fails verification.
    """

    project_dir = Path(project_dir).resolve()
    runs = [run for run in phase_state.get("runs", []) if isinstance(run, Mapping)]
    latest_id = str(phase_state.get("latest_run") or "")
    latest = next(
        (run for run in reversed(runs) if str(run.get("run_id", "")) == latest_id),
        runs[-1] if runs else None,
    )
    recovered: dict[str, Any] | None = None
    if latest is not None:
        raw_manifest = latest.get("manifest_path")
        expected_hash = str(latest.get("manifest_sha256") or "").lower()
        if raw_manifest and expected_hash:
            try:
                manifest_path = Path(str(raw_manifest)).resolve(strict=True)
                manifest_root = (
                    project_state.state_dir(project_dir) / "runs" / phase_slug
                ).resolve()
                manifest_path.relative_to(manifest_root)
                payload = project_state.bounded_file_bytes(
                    manifest_path,
                    maximum=project_state.MAX_CONTROL_FILE_BYTES,
                    label="run manifest",
                )
                if hashlib.sha256(payload).hexdigest() != expected_hash:
                    raise ValueError("manifest hash mismatch")
                manifest = json.loads(payload.decode("utf-8"))
                if not isinstance(manifest, Mapping):
                    raise ValueError("manifest must be a mapping")
                manifest_phase = manifest.get("phase")
                if (
                    not isinstance(manifest_phase, Mapping)
                    or manifest.get("phase_slug") != phase_slug
                    or manifest.get("run_id") != latest.get("run_id")
                    or manifest_phase.get("slug") != phase_slug
                ):
                    raise ValueError("manifest identity mismatch")
                recovered = dict(manifest_phase)
            except (
                OSError,
                TypeError,
                ValueError,
                UnicodeError,
                json.JSONDecodeError,
                project_state.ProjectStateError,
            ):
                recovered = None

    try:
        requested = max(1, int((latest or {}).get("rounds_requested", 1)))
    except (TypeError, ValueError):
        requested = 1
    fallback_name = phase_slug.split("-", 1)[-1].replace("-", " ").title()
    phase = recovered or {
        "slug": phase_slug,
        "name": fallback_name,
        "description": "This phase is no longer present in the current configuration.",
        "pattern": "parallel",
        "rounds": {"min": requested, "default": requested, "max": requested},
        "gated_by": [],
        "context_from": [],
        "folder": "No longer configured",
        "members": sorted({
            str(agent)
            for run in runs
            for round_ in run.get("rounds", [])
            if isinstance(round_, Mapping)
            for agent in round_.get("agents", [])
            if str(agent)
        }),
    }
    phase["slug"] = phase_slug
    phase["name"] = str(phase.get("name") or fallback_name)
    phase["description"] = str(
        phase.get("description")
        or "This phase is no longer present in the current configuration."
    )
    if phase.get("pattern") not in {"parallel", "sequential", "debate"}:
        phase["pattern"] = "parallel"
    raw_members = phase.get("members", [])
    phase["members"] = [
        str(member) for member in raw_members if str(member)
    ] if isinstance(raw_members, (list, tuple)) else []
    phase["stages"] = [
        dict(stage) for stage in phase.get("stages", []) if isinstance(stage, Mapping)
    ]
    if phase["pattern"] == "sequential" and not phase["stages"]:
        phase["pattern"] = "parallel"
    raw_rounds = phase.get("rounds")
    try:
        minimum = int(raw_rounds["min"])
        default = int(raw_rounds["default"])
        maximum = int(raw_rounds["max"])
        if not 1 <= minimum <= default <= maximum <= 50:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        phase["rounds"] = {
            "min": requested,
            "default": requested,
            "max": requested,
        }
    else:
        phase["rounds"] = {
            "min": minimum,
            "default": default,
            "max": maximum,
        }
    raw_gates = phase.get("gated_by", [])
    phase["gated_by"] = [
        str(item) for item in raw_gates if str(item)
    ] if isinstance(raw_gates, (list, tuple)) else []
    raw_context = phase.get("context_from", [])
    phase["context_from"] = [
        str(item) for item in raw_context if str(item)
    ] if isinstance(raw_context, (list, tuple)) else []
    phase["folder"] = str(phase.get("folder") or "No longer configured")
    phase["recovery_only"] = True
    phase["recovery_source"] = (
        "latest sealed run manifest" if recovered is not None else "project state fallback"
    )
    return phase


def _dependencies(phases: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    return {
        str(phase["slug"]): [str(item) for item in phase.get("gated_by", [])]
        for phase in phases
    }


def _completed_count(run: Mapping[str, Any]) -> int:
    return sum(1 for item in run.get("rounds", []) if item.get("completed"))


def _discover_summary_path(
    project_dir: Path, run: Mapping[str, Any], phase_slug: str
) -> str | None:
    """Resolve the summary path. Falls back to the conventional location
    (phase-summaries/<slug>/<run_id>.html) when the lead never recorded
    final_summary in state — the 'failed but artifacts exist' case."""
    raw_path = run.get("final_summary")
    if raw_path:
        return str(raw_path)
    # Fallback: check the conventional location by run_id
    run_id = run.get("id") or run.get("run_id")
    if not run_id:
        return None
    candidate = (
        project_dir.resolve()
        / "phase-summaries"
        / phase_slug
        / f"{run_id}.html"
    )
    if candidate.is_file() and candidate.stat().st_size > 0:
        return str(candidate.relative_to(project_dir.resolve()))
    return None


def _truncate_conclusion(text: str, max_chars: int = 140) -> str:
    """First sentence(s) of a recommendation, truncated for an overview row."""
    text = text.strip()
    if not text:
        return ""
    # Try to cut at the first sentence boundary within range
    for boundary in (". ", ".\n"):
        idx = text.find(boundary)
        if 0 < idx <= max_chars:
            return text[:idx + 1]
    if len(text) <= max_chars:
        return text
    # Hard truncate at word boundary
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + "…"


_SUMMARY_HIGHLIGHT_TARGET_WORDS = 250
_SUMMARY_HIGHLIGHT_MAX_CHARS = 2000


def _summary_highlight(
    project_dir: Path,
    run: Mapping[str, Any],
    phase_slug: str,
) -> str:
    """Extract a ~250-word abstract from a run's HTML summary.

    Concatenates content paragraphs (skipping meta/info) until the target
    word count is reached, then truncates cleanly.
    """
    import re

    path = _discover_summary_path(project_dir, run, phase_slug)
    if not path:
        return ""
    full_path = project_dir.resolve() / path
    try:
        html = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if not html.strip():
        return ""
    # Remove style/script blocks
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.IGNORECASE)
    search_from = h1_match.end() if h1_match else 0
    # Collect content paragraphs until we hit the word target
    collected: list[str] = []
    total_words = 0
    for p_match in re.finditer(r"<p([^>]*)>(.*?)</p>", html[search_from:], re.DOTALL | re.IGNORECASE):
        attrs = p_match.group(1)
        raw = p_match.group(2)
        if "meta" in attrs.lower() or "info" in attrs.lower():
            continue
        text = re.sub(r"<[^>]+>", "", raw).strip()
        if not text or len(text) <= 20:
            continue
        wc = len(text.split())
        if total_words + wc > _SUMMARY_HIGHLIGHT_TARGET_WORDS and collected:
            # Truncate this paragraph to fit the remaining budget
            remaining = _SUMMARY_HIGHLIGHT_TARGET_WORDS - total_words
            words = text.split()
            text = " ".join(words[:remaining]) + "…"
            collected.append(text)
            break
        collected.append(text)
        total_words += wc
        if total_words >= _SUMMARY_HIGHLIGHT_TARGET_WORDS:
            break
    result = "\n\n".join(collected)
    if not result:
        # Fallback: first 2000 chars of body text
        body = re.sub(r"<[^>]+>", " ", html[search_from:])
        result = re.sub(r"\s+", " ", body).strip()
    if not result:
        return ""
    if len(result) > _SUMMARY_HIGHLIGHT_MAX_CHARS:
        result = result[:_SUMMARY_HIGHLIGHT_MAX_CHARS].rsplit(" ", 1)[0] + "…"
    return result


def _cross_phase_context(
    project_dir: Path,
    phase_slug: str,
    phases_cfg: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build context chips showing what other phases can feed into this run.

    Each entry: {slug, name, status, run_number, has_result}
    Phases with no result are shown grayed out.
    For phases that create branches (method development), includes branch info.
    """
    state = project_state.load(project_dir)
    phases_state = state.get("phases", {})
    result: list[dict[str, Any]] = []
    for phase in phases_cfg:
        slug = str(phase.get("slug", ""))
        if slug == phase_slug:
            continue
        phase_state = phases_state.get(slug, {})
        approved_id = str(phase_state.get("approved_run") or "").strip()
        latest_id = str(phase_state.get("latest_run") or "").strip()
        has_result = bool(approved_id or latest_id)
        runs = phase_state.get("runs", [])
        run_number = ""
        if approved_id:
            for r in runs:
                if str(r.get("run_id", "")) == approved_id:
                    run_number = str(r.get("run_number", ""))
                    break
        elif latest_id:
            for r in runs:
                if str(r.get("run_id", "")) == latest_id:
                    run_number = str(r.get("run_number", ""))
                    break
        entry: dict[str, Any] = {
            "slug": slug,
            "name": str(phase.get("name", slug)),
            "has_result": has_result,
            "run_number": run_number,
        }
        # For method development phases, include branch/method info
        if slug == project_state.METHOD_DEVELOPMENT_PHASE:
            # Include the full method menu so downstream phases can pick which to include
            entry["method_menu"] = method_menu.load_method_menu(project_dir)
            if approved_id:
                for r in runs:
                    if str(r.get("run_id", "")) == approved_id:
                        decision = r.get("decision_record")
                        if isinstance(decision, Mapping):
                            data = decision.get("data", {})
                            selected = data.get("selected_scientific_object") if isinstance(data, Mapping) else None
                            if isinstance(selected, Mapping) and selected.get("stable_id"):
                                entry["method_id"] = str(selected.get("stable_id", ""))
                                entry["method_version"] = str(selected.get("version", ""))
                        break
        result.append(entry)
    return result


def _method_details(project_dir: Path) -> list[dict[str, Any]]:
    """Load all method files with full markdown content and metadata."""
    import re

    method_dir = project_dir.resolve() / "ideas" / "methods"
    if not method_dir.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for path in sorted(method_dir.glob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
        if not fm_match:
            continue
        fm_text = fm_match.group(1)
        body = fm_match.group(2).strip()

        def _yaml_val(key: str) -> str:
            m = re.search(rf'^{key}:\s*"?([^"\n]+?)"?\s*$', fm_text, re.MULTILINE)
            return m.group(1).strip() if m else ""

        created_ts = ""
        try:
            created_ts = str(path.stat().st_mtime)
        except OSError:
            pass

        # Render markdown body to HTML
        import markdown as md
        body_html = md.markdown(body, extensions=["fenced_code", "tables", "md_in_html"])

        entries.append({
            "stable_id": _yaml_val("stable_id") or path.stem,
            "version": _yaml_val("version"),
            "label": _yaml_val("label") or path.stem,
            "status": _yaml_val("status") or "viable",
            "body": body,
            "body_html": body_html,
            "created_ts": created_ts,
            "created_display": _format_method_ts(created_ts),
        })
    rank = {"recommended": 0, "viable": 1, "frontier": 2, "retired": 3}
    entries.sort(key=lambda e: (rank.get(e["status"], 9), e["stable_id"]))
    return entries


def _format_method_ts(ts: str) -> str:
    if not ts:
        return ""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return ""


def _method_comparison(project_dir: Path) -> str:
    """Extract method comparison/ranking from the latest method run summary."""
    result = _method_comparison_data(project_dir)
    if not result:
        return ""
    return result  # Already text, kept for backward compat


def _method_comparison_data(project_dir: Path) -> str:
    """Extract the Full Idea Set ranking table from the latest method run summary."""
    import re

    summary_dir = project_dir.resolve() / "phase-summaries" / "02-method-development"
    if not summary_dir.is_dir():
        return ""
    summaries = sorted(
        summary_dir.glob("*.html"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not summaries:
        return ""
    try:
        html = summaries[0].read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    idx = html.find("Full Idea Set")
    if idx < 0:
        idx = html.find("Comparison")
    if idx < 0:
        return ""
    next_h2 = html.find("<h2", idx + 10)
    end = next_h2 if next_h2 > 0 else len(html)
    section = html[idx:end]
    text = re.sub(r"<br\s*/?>", "\n", section)
    text = re.sub(r"</?(?:tr|div|p)>", "\n", text)
    text = re.sub(r"</?(?:td|th)>", " | ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()[:3000]


def _method_scores(project_dir: Path) -> dict[str, dict[str, str]]:
    """Extract the 3-axis scoring (risk, potential, tractability) from the theorist output.

    Parses markdown tables from ideas/run/*/round-01/theorist.md.
    Returns {method_name_lower: {risk: str, potential: str, tractability: str}}.
    """
    import re

    ideas_dir = project_dir.resolve() / "ideas" / "run"
    if not ideas_dir.is_dir():
        return {}
    scores: dict[str, dict[str, str]] = {}
    # Check all rounds for scoring tables
    for run_dir in sorted(ideas_dir.iterdir()):
        for round_dir in sorted((run_dir / "round-01").parent.iterdir() if (run_dir / "round-01").exists() else []):
            theorist_file = round_dir / "theorist.md"
            if not theorist_file.is_file():
                continue
            try:
                text = theorist_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Find markdown scoring tables with our three axes
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if "Mathematical risk" not in line and "Acceleration potential" not in line:
                    continue
                headers = [h.strip() for h in line.split("|") if h.strip()]
                if len(headers) < 4:
                    continue
                # Parse subsequent rows until empty/non-table line
                for j in range(i + 2, min(len(lines), i + 12)):
                    row_line = lines[j].strip()
                    if not row_line.startswith("|"):
                        break
                    cells = [c.strip() for c in row_line.split("|") if c.strip()]
                    if len(cells) < 4:
                        continue
                    idea_name = re.sub(r"^\d+\.\s*", "", cells[0]).strip()
                    # Extract just the rating word (Low/Medium/High/Very high) from each cell
                    def _extract_rating(cell: str) -> str:
                        m = re.match(r"(Very high|High|Medium|Low|Moderate)", cell, re.IGNORECASE)
                        return m.group(1) if m else cell[:20]
                    scores[idea_name.lower()] = {
                        "risk": _extract_rating(cells[1]),
                        "potential": _extract_rating(cells[2]),
                        "tractability": _extract_rating(cells[3]),
                    }
    return scores


def _method_ranking_rows(project_dir: Path) -> list[dict[str, Any]]:
    """Parse the Full Idea Set table and enrich with downstream phase status.

    Returns simplified rows: {name, note, p3, p4, p5, stable_id}
    where p3/p4/p5 are 'done' / 'pending' / '' for green/gray/empty lights.
    """
    import re
    from . import project_state as ps

    # Parse the ranking table from the summary HTML
    summary_dir = project_dir.resolve() / "phase-summaries" / "02-method-development"
    if not summary_dir.is_dir():
        return []
    summaries = sorted(summary_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not summaries:
        return []
    try:
        html = summaries[0].read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE)
    raw_rows: list[dict[str, str]] = []
    for table_html in tables:
        headers = re.findall(r"<th[^>]*>(.*?)</th>", table_html, re.DOTALL | re.IGNORECASE)
        headers = [re.sub(r"<[^>]+>", "", h).strip() for h in headers]
        if not any("Idea" in h for h in headers):
            continue
        row_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
        for row_html in row_matches[1:]:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            if len(cells) != len(headers):
                continue
            raw_rows.append(dict(zip(headers, cells)))
        break

    if not raw_rows:
        return []

    # Load method files to match names to stable_ids
    method_dir = project_dir.resolve() / "ideas" / "methods"
    name_to_id: dict[str, str] = {}
    if method_dir.is_dir():
        for path in method_dir.glob("*.md"):
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = re.match(r"^---\s*\n(.*?)\n---", raw, re.DOTALL)
            if not fm:
                continue
            fm_text = fm.group(1)
            label_m = re.search(r'^label:\s*"?([^"\n]+?)"?\s*$', fm_text, re.MULTILINE)
            sid_m = re.search(r'^stable_id:\s*"?([^"\n]+?)"?\s*$', fm_text, re.MULTILINE)
            if label_m and sid_m:
                name_to_id[label_m.group(1).strip().lower()] = sid_m.group(1).strip()

    # Check which phases have runs
    state = ps.load(project_dir)
    phases_state = state.get("phases", {})
    p03_has = bool(phases_state.get("03-idea-evaluation", {}).get("runs"))
    p04_has = bool(phases_state.get("04-draft-assembly", {}).get("runs"))
    p05_has = bool(phases_state.get("05-review-revision", {}).get("runs"))

    # Determine which method is the approved one
    approved_method_id = ""
    p02_state = phases_state.get("02-method-development", {})
    approved_run_id = str(p02_state.get("approved_run") or "")
    for r in p02_state.get("runs", []):
        if str(r.get("run_id", "")) == approved_run_id:
            dr = r.get("decision_record", {})
            sel = dr.get("data", {}).get("selected_scientific_object", {}) if isinstance(dr.get("data"), dict) else {}
            if isinstance(sel, dict) and sel.get("stable_id"):
                approved_method_id = str(sel["stable_id"])
            break

    # Build simplified rows
    method_scores = _method_scores(project_dir)
    result: list[dict[str, Any]] = []
    for row in raw_rows:
        idea = row.get("Idea", row.get("idea", ""))
        note = row.get("Phase 03 status", row.get("Phase 03 Status", ""))
        # Also include mechanism class as part of note if present
        mech = row.get("Mechanism class", row.get("Mechanism Class", "")
        )
        brief = f"{mech}: {note}" if mech and note else (note or mech or "")

        # Match to stable_id
        stable_id = name_to_id.get(idea.lower().strip(), "")

        # Phase lights: green for approved method if phase has runs
        is_approved = stable_id and stable_id == approved_method_id
        p3 = "done" if (is_approved and p03_has) else ""
        p4 = "done" if (is_approved and p04_has) else ""
        p5 = "done" if (is_approved and p05_has) else ""

        # Scores from theorist evaluation — match by substring
        idea_lower = idea.lower().strip()
        scores = method_scores.get(idea_lower, {})
        if not scores:
            # Try partial match: score keys are abbreviated names
            for score_key, score_val in method_scores.items():
                if score_key in idea_lower or idea_lower.startswith(score_key):
                    scores = score_val
                    break

        result.append({
            "name": idea,
            "note": brief,
            "risk": scores.get("risk", ""),
            "potential": scores.get("potential", ""),
            "tractability": scores.get("tractability", ""),
            "p3": p3,
            "p4": p4,
            "p5": p5,
            "stable_id": stable_id,
            "is_method": bool(stable_id),
        })
    return result


def _summary_available(
    project_dir: Path,
    run: Mapping[str, Any],
    phase_slug: str = "",
) -> bool:
    raw_path = _discover_summary_path(project_dir, run, phase_slug)
    if not raw_path:
        return False
    root = project_dir.resolve()
    candidate = (root / str(raw_path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    try:
        digest, _ = project_state.bounded_file_digest(
            candidate,
            maximum=project_state.MAX_SUMMARY_BYTES,
            label="final summary",
        )
    except (OSError, project_state.ProjectStateError):
        return False
    recorded_hash = run.get("summary_sha256")
    return not recorded_hash or digest == recorded_hash


def _sealed_run_manifest(
    run: Mapping[str, Any], phase_slug: str
) -> dict[str, Any] | None:
    raw_manifest = run.get("manifest_path")
    manifest_digest = str(run.get("manifest_sha256", "")).lower()
    if not raw_manifest or not manifest_digest:
        return None
    try:
        manifest_path = Path(str(raw_manifest)).resolve(strict=True)
        payload = project_state.bounded_file_bytes(
            manifest_path,
            maximum=project_state.MAX_CONTROL_FILE_BYTES,
            label="run manifest",
        )
        if hashlib.sha256(payload).hexdigest() != manifest_digest:
            return None
        manifest = json.loads(payload.decode("utf-8"))
        if (
            manifest.get("phase_slug") != phase_slug
            or manifest.get("run_id") != run.get("run_id")
        ):
            return None
    except (
        OSError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        project_state.ProjectStateError,
    ):
        return None
    return manifest


def _source_baseline_status(source_baseline: Mapping[str, Any]) -> str:
    field = (
        "source_baseline_status"
        if source_baseline.get("schema_version") == 2
        else "provenance"
    )
    return str(source_baseline.get(field, "")).strip()


def _source_descriptor(
    project_dir: Path,
    phase_slug: str,
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a strict display record for a derivative run's sealed source."""

    if not isinstance(manifest, Mapping):
        return None
    source_kind = ""
    source: Mapping[str, Any] | None = None
    target: Mapping[str, Any] | None = None
    baseline: Mapping[str, Any] | None = None
    raw_path = ""
    digest = ""
    source_round: int | None = None
    if phase_slug == "03-idea-evaluation":
        candidate = manifest.get("proof_audit_source")
        if not isinstance(candidate, Mapping):
            return None
        source = candidate
        target_value = candidate.get("target")
        baseline_value = candidate.get("source_baseline")
        if not isinstance(target_value, Mapping):
            return None
        target = target_value
        baseline = baseline_value if isinstance(baseline_value, Mapping) else None
        source_kind = "theory_audit"
        raw_path = str(target.get("source_path", ""))
        digest = str(target.get("sha256", "")).lower()
        try:
            source_round = int(target.get("source_round", 0))
        except (TypeError, ValueError):
            return None
        if source_round < 1:
            return None
    elif phase_slug == "05-review-revision":
        candidate = manifest.get("paper_review")
        if not isinstance(candidate, Mapping) or candidate.get("kind") != "review_only":
            return None
        baseline_value = candidate.get("source_baseline")
        source = candidate
        baseline = baseline_value if isinstance(baseline_value, Mapping) else None
        source_kind = "manuscript_review"
        raw_path = str(candidate.get("source_path", ""))
        digest = str(candidate.get("source_sha256", "")).lower()
        if digest != str(candidate.get("review_sha256", "")).lower():
            return None
    else:
        return None

    source_schema = source.get("schema_version", 1)
    if baseline is not None:
        source_run_id = str(
            source.get("run_id", "") or baseline.get("run_id", "")
        ).strip()
        baseline_run_id = str(baseline.get("run_id", "")).strip()
        selected_status = str(baseline.get("status_at_selection", "")).strip()
        baseline_status = _source_baseline_status(baseline)
        if (
            not source_run_id
            or source_run_id != baseline_run_id
            or selected_status not in SOURCE_BASELINE_STATUS_BY_RUN_STATUS
            or baseline_status
            != SOURCE_BASELINE_STATUS_BY_RUN_STATUS[selected_status]
        ):
            return None
    elif source_schema == 1:
        source_run_id = str(source.get("run_id", "")).strip()
        if not source_run_id:
            source_run_id = "not recorded in legacy manifest"
        selected_status = "not recorded in legacy manifest"
        baseline_status = "not recorded in legacy manifest"
    else:
        return None
    if (
        len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        return None
    root = Path(project_dir).resolve()
    try:
        candidate_path = Path(raw_path)
        if candidate_path.is_absolute():
            relative_path = candidate_path.resolve(strict=False).relative_to(root)
        else:
            if not raw_path or ".." in candidate_path.parts:
                return None
            relative_path = candidate_path
    except (OSError, ValueError):
        return None
    return {
        "kind": source_kind,
        "source_run_id": source_run_id,
        "source_path": relative_path.as_posix(),
        "source_sha256": digest,
        "status_at_selection": selected_status,
        "source_baseline_status": baseline_status,
        "source_round": source_round,
    }


def _phase_six_post_review_target(
    project_dir: Path,
    phase_slug: str,
    run: Mapping[str, Any],
    integrity_report: Mapping[str, Any],
) -> dict[str, str] | None:
    """Return an exact selectable post-review manuscript from a sealed run."""

    if phase_slug != "05-review-revision":
        return None
    status = str(run.get("status", ""))
    decision_record = run.get("decision_record")
    if (
        status not in SOURCE_BASELINE_STATUS_BY_RUN_STATUS
        or not run.get("submitted_at")
        or not run.get("final_summary")
        or not isinstance(decision_record, Mapping)
        or not isinstance(decision_record.get("data"), Mapping)
        or not integrity_report.get("ok")
    ):
        return None
    manifest = _sealed_run_manifest(run, phase_slug)
    if manifest is None:
        return None
    try:
        paper_review = manifest.get("paper_review")
        if isinstance(paper_review, Mapping) and paper_review.get("kind") == "review_only":
            return None
        root = project_dir.resolve()
        output_root = Path(str(manifest.get("output_root", ""))).resolve()
        output_root.relative_to(root)
        artifacts = run.get("submission_artifacts")
        record = (
            artifacts.get("post_review_manuscript")
            if isinstance(artifacts, Mapping)
            else None
        )
        if not isinstance(record, Mapping):
            return None
        target = (root / str(record.get("path", ""))).resolve(strict=True)
        target.relative_to(root)
        if target != (output_root / "manuscript-post-review.md").resolve():
            return None
        contents = project_state.bounded_file_bytes(
            target,
            maximum=MAX_REVIEW_TARGET_BYTES,
            label="post-review manuscript",
        )
        recorded_size = int(record.get("size", -1))
    except (
        OSError,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        project_state.ProjectStateError,
    ):
        return None
    digest = hashlib.sha256(contents).hexdigest()
    if (
        not contents.strip()
        or recorded_size != len(contents)
        or digest != str(record.get("sha256", "")).lower()
    ):
        return None
    return {
        "path": target.relative_to(root).as_posix(),
        "sha256": digest,
        "source_run_id": str(run.get("run_id", "")),
        "source_status": status,
        "source_baseline_status": SOURCE_BASELINE_STATUS_BY_RUN_STATUS[status],
    }


def _run_view(
    project_dir: Path,
    phase_slug: str,
    run: Mapping[str, Any] | None,
    number: int | None = None,
) -> dict[str, Any] | None:
    if run is None:
        return None
    run_id = str(run.get("run_id", ""))
    requested = int(run.get("rounds_requested", 1) or 1)
    completed = _completed_count(run)
    current = next(
        (
            item
            for item in run.get("rounds", [])
            if item.get("started") and not item.get("completed")
        ),
        None,
    )
    log_path = project_state.state_dir(project_dir) / "runs" / phase_slug / f"{run_id}.log"
    status = str(run.get("status", "pending"))
    started_at = run.get("started") or run.get("created_at")
    completed_at = run.get("completed") or run.get("ended_at")
    decision_note = run.get("decision_note", "")
    summary_available = _summary_available(project_dir, run, phase_slug)
    integrity_report = (
        project_state.run_integrity_report(project_dir, phase_slug, run_id)
        if run.get("final_summary")
        else {"ok": True, "reason": ""}
    )
    decision_record = run.get("decision_record")
    baseline_acknowledgement = run.get("approval_baseline_acknowledgement")
    approval_kind = str(run.get("approval_kind", "")).strip()
    if not approval_kind and isinstance(baseline_acknowledgement, Mapping):
        approval_kind = str(
            baseline_acknowledgement.get("approval_kind", "")
        ).strip()
    scientific_decision = (
        dict(decision_record.get("data", {}))
        if isinstance(decision_record, Mapping)
        and isinstance(decision_record.get("data"), Mapping)
        else None
    )
    action_labels = {
        "approve": "Approve",
        "approve_with_limitations": "Approve with limitations",
        "request_revision": "Request revision",
        "rerun": "Rerun",
        "defer": "Defer the decision",
    }
    post_review_target = _phase_six_post_review_target(
        project_dir, phase_slug, run, integrity_report
    )
    manifest = _sealed_run_manifest(run, phase_slug)
    source_descriptor = _source_descriptor(project_dir, phase_slug, manifest)
    method_selection = (
        dict(manifest.get("method_selection", {}))
        if isinstance(manifest, Mapping)
        and isinstance(manifest.get("method_selection"), Mapping)
        else None
    )
    protocol_checkpoint_required = bool(
        manifest
        and isinstance(manifest.get("protocol_checkpoint"), Mapping)
    )
    frozen_phase = manifest.get("phase", {}) if manifest else {}
    has_frozen_plan = bool(
        manifest
        and isinstance(frozen_phase, Mapping)
        and str(frozen_phase.get("slug", "")) == phase_slug
    )
    plan_stages = [
        dict(stage)
        for stage in frozen_phase.get("stages", [])
        if isinstance(stage, Mapping)
    ]
    plan_members = [
        str(member.get("role", "") if isinstance(member, Mapping) else member)
        for member in frozen_phase.get("members", [])
        if str(member.get("role", "") if isinstance(member, Mapping) else member)
    ]
    plan_pattern = str(frozen_phase.get("pattern", "")) if has_frozen_plan else ""
    plan_folder = str(frozen_phase.get("folder", "")) if has_frozen_plan else ""
    run_plan = str(frozen_phase.get("run_plan", ""))
    if phase_slug == "03-idea-evaluation" and not run_plan:
        if frozen_phase.get("audit_only"):
            run_plan = "audit_only"
        elif frozen_phase.get("proof_audit"):
            run_plan = "standard_with_audit"
        elif has_frozen_plan and plan_pattern == "sequential":
            run_plan = "standard"

    if frozen_phase.get("review_only"):
        plan_variant = "Review only: exact selected manuscript"
    elif frozen_phase.get("audit_only"):
        plan_variant = "Independent audit of an existing sealed theory artifact"
    elif frozen_phase.get("proof_audit"):
        plan_variant = "Standard theory plus independent proof audit"
    elif (
        phase_slug == "03-idea-evaluation"
        and has_frozen_plan
        and plan_pattern == "sequential"
    ):
        plan_variant = "Standard theory"
    elif phase_slug == "05-review-revision" and plan_stages:
        plan_variant = "Full manuscript writing and independent review"
    elif has_frozen_plan:
        plan_variant = "Standard phase plan"
    else:
        plan_variant = None

    # Display status: when a run is "failed" but real artifacts exist on disk
    # (summary HTML written by the lead), show "partial" instead of "failed".
    # The lead did the work but didn't formally submit it (round-tracking gap,
    # crash after writing files, etc.). Underlying status stays "failed" so
    # state logic is unaffected; only the user-facing label softens.
    if status == "failed" and summary_available:
        display_status = "partial"
    else:
        display_status = status

    return {
        "id": run_id,
        "run_id": run_id,
        "number": number,
        "status": status,
        "display_status": display_status,
        "status_label": (
            "Completed (partial)" if display_status == "partial"
            else status.replace("_", " ").title()
        ),
        "mode": run.get("mode", ""),
        "rounds_requested": requested,
        "requested_count": requested,
        "rounds_completed": completed,
        "completed_count": completed,
        "progress_percent": min(100, round((completed / requested) * 100)) if requested else 0,
        "current_round": current.get("n") if current else None,
        "current_round_detail": current,
        "rounds": list(run.get("rounds", [])),
        "started": started_at,
        "started_at": started_at,
        "submitted_at": run.get("submitted_at"),
        "completed": completed_at,
        "completed_at": completed_at,
        "ended_at": run.get("ended_at"),
        "decision_at": run.get("decision_at"),
        "decision_by": run.get("decision_by"),
        "decision_note": decision_note,
        "approved_at": run.get("decision_at") if status == "approved" else None,
        "approval_note": decision_note if status == "approved" else "",
        "revision_feedback": decision_note if status == "revision_requested" else "",
        "feedback": run.get("user_feedback", ""),
        "user_feedback": run.get("user_feedback", ""),
        "summary_path": _discover_summary_path(project_dir, run, phase_slug),
        "summary_available": summary_available,
        "summary_integrity_error": bool(run.get("final_summary") and not summary_available),
        "integrity_error": not bool(integrity_report.get("ok")),
        "integrity_error_detail": str(integrity_report.get("reason", "")),
        "scientific_decision": scientific_decision,
        "scientific_outcome": (
            scientific_decision.get("scientific_outcome")
            if scientific_decision
            else None
        ),
        "conclusion": (
            _truncate_conclusion(scientific_decision.get("recommendation", ""))
            if scientific_decision and scientific_decision.get("recommendation")
            else ""
        ),
        "recommended_user_action": (
            scientific_decision.get("recommended_user_action")
            if scientific_decision
            else None
        ),
        "recommended_user_action_label": (
            action_labels.get(
                str(scientific_decision.get("recommended_user_action", "")),
                "Not recorded",
            )
            if scientific_decision
            else "Not recorded"
        ),
        "decision_record_version": (
            str(decision_record.get("sha256", ""))
            if isinstance(decision_record, Mapping)
            else ""
        ),
        "post_review_target": post_review_target,
        "source_descriptor": source_descriptor,
        "method_selection": method_selection,
        "plan_stages": plan_stages,
        "plan_variant": plan_variant,
        "frozen_plan": {
            "available": has_frozen_plan,
            "variant": plan_variant,
            "pattern": plan_pattern,
            "folder": plan_folder,
            "members": plan_members,
            "stages": plan_stages,
            "run_plan": run_plan or None,
        },
        "rerun_config": None,
        "log_available": log_path.is_file(),
        "error": run.get("error"),
        "cancel_reason": run.get("cancel_reason"),
        "cleanup_outcome": run.get("cleanup_outcome"),
        "cleanup_reason": run.get("cleanup_reason"),
        "cleanup_started_at": run.get("cleanup_started_at"),
        "cleanup_completed_at": run.get("cleanup_completed_at"),
        "cleanup_recovery_note": run.get("cleanup_recovery_note"),
        "protocol_checkpoint": (
            dict(run["protocol_checkpoint"])
            if isinstance(run.get("protocol_checkpoint"), Mapping)
            else None
        ),
        "protocol_checkpoint_required": protocol_checkpoint_required,
        "override_metadata": run.get("override_metadata"),
        "prerequisite_snapshot": run.get("prerequisite_snapshot"),
        "context_inputs": list(run.get("context_inputs", [])),
        "approval_context_acknowledgement": run.get("approval_context_acknowledgement"),
        "approval_baseline_acknowledgement": run.get(
            "approval_baseline_acknowledgement"
        ),
        "approval_kind": approval_kind or None,
        "approval_kind_label": (
            "Approve with limitations"
            if approval_kind == "approve_with_limitations"
            else "Approve"
            if approval_kind == "approve"
            else None
        ),
        "is_active": status in project_state.ACTIVE_RUN_STATUSES,
        "needs_review": status == "awaiting_review",
        "stages_requested": requested,
        "stages_completed": completed,
        "summary_highlight": _summary_highlight(project_dir, run, phase_slug),
    }


def _phase_runs(
    project_dir: Path,
    phase_slug: str,
    phase_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [
        _run_view(project_dir, phase_slug, run, index + 1)
        for index, run in enumerate(phase_state.get("runs", []))
    ]


def _rounds_policy(phase: Mapping[str, Any]) -> dict[str, Any]:
    raw = phase.get("rounds", {})
    stages = list(phase.get("stages", []))
    if phase.get("pattern") == "sequential":
        count = len(stages)
        return {
            "min": count,
            "default": count,
            "max": count,
            "fixed": True,
            "options": [count],
            "label": f"{count} fixed stages",
        }
    minimum = int(raw.get("min", 1))
    default = int(raw.get("default", minimum))
    maximum = int(raw.get("max", default))
    return {
        "min": minimum,
        "default": default,
        "max": maximum,
        "fixed": minimum == maximum,
        "options": list(range(minimum, maximum + 1)),
        "label": (
            f"{minimum} round" if minimum == maximum == 1
            else f"{minimum} to {maximum} rounds"
        ),
    }


def _prerequisite_view(
    report: Mapping[str, Any], phases: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    names = {
        str(phase["slug"]): str(phase.get("name", phase["slug"]))
        for phase in phases
    }
    requirements = []
    for item in report.get("requirements", []):
        entry = dict(item)
        entry["name"] = names.get(str(item.get("phase")), str(item.get("phase")))
        requirements.append(entry)
    blockers = [str(item) for item in report.get("blockers", [])]
    missing = [entry for entry in requirements if not entry.get("satisfied")]
    missing_names = [entry["name"] for entry in missing]
    satisfied = bool(report.get("satisfied", not blockers))
    if satisfied and requirements:
        message = "All recommended prerequisite results are approved and current."
    elif satisfied:
        message = "This phase has no prerequisites and can be run at any time."
    else:
        message = "Missing or stale context: " + ", ".join(missing_names)
    return {
        **dict(report),
        "ok": satisfied,
        "satisfied": satisfied,
        "blockers": blockers,
        "missing": missing,
        "missing_names": missing_names,
        "requirements": requirements,
        "message": message,
    }


def _decision_label(phase_state: Mapping[str, Any], latest: Mapping[str, Any] | None) -> str:
    if latest and latest.get("status") in project_state.ACTIVE_RUN_STATUSES:
        if latest.get("status") == "stopping":
            return "Cleanup needs your attention"
        return "Agents are working"
    if phase_state.get("stale"):
        return "Approved result needs review after an upstream change"
    if latest is None:
        return "Not run yet"
    labels = {
        "starting": "Starting",
        "running": "Agents are working",
        "submitting": "Preparing the result for review",
        "stopping": "Cleanup needs your attention",
        "awaiting_review": "Your decision is needed",
        "approved": "Approved and current",
        "revision_requested": "Revision requested; ready to rerun",
        "failed": "Run failed; approved fallback preserved",
        "cancelled": "Run cancelled; ready to rerun",
        "superseded": "Superseded by an approved run",
    }
    return labels.get(str(latest.get("status")), str(latest.get("status", "Pending")))


def _decision_state(
    phase_state: Mapping[str, Any], latest: Mapping[str, Any] | None
) -> str:
    """Return the state that currently needs the user's attention."""

    if latest is not None:
        latest_status = str(latest.get("status", "pending"))
        if latest_status in project_state.ACTIVE_RUN_STATUSES:
            return latest_status
        if str(latest.get("run_id", "")) != str(phase_state.get("approved_run", "")):
            # When the latest run failed but artifacts exist, surface "partial"
            # so the phase row doesn't alarm with "failed" when work is usable.
            if latest.get("display_status") == "partial":
                return "partial"
            return latest_status
    if phase_state.get("stale"):
        return "stale"
    return str(phase_state.get("status", "pending"))


def _downstream_context_options(
    project_dir: Path,
    phase_slug: str,
    phases_cfg: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Identify downstream (future) phases that have approved results.

    Returns a dict with ``available`` (bool), ``phases`` (list of display
    dicts with slug/name/run_id), so the launch form can show the downstream
    context toggle only when it would actually add context.
    """

    dependencies = _dependencies(phases_cfg)
    # Reverse BFS: find phases that transitively gate on phase_slug.
    reverse: dict[str, set[str]] = {}
    for gated_phase, prerequisites in dependencies.items():
        for prerequisite in prerequisites:
            reverse.setdefault(prerequisite, set()).add(gated_phase)
    descendants: set[str] = set()
    queue = list(reverse.get(phase_slug, set()))
    while queue:
        item = queue.pop(0)
        if item in descendants:
            continue
        descendants.add(item)
        queue.extend(reverse.get(item, set()))
    if not descendants:
        return {"available": False, "phases": []}
    state = project_state.load(project_dir)
    phases_state = state.get("phases", {})
    name_by_slug = {
        str(phase["slug"]): str(phase.get("name", phase["slug"]))
        for phase in phases_cfg
    }
    options: list[dict[str, str]] = []
    for slug in sorted(descendants):
        phase_state = phases_state.get(slug, {})
        approved_id = str(phase_state.get("approved_run") or "").strip()
        if not approved_id:
            continue
        options.append({
            "slug": slug,
            "name": name_by_slug.get(slug, slug),
            "run_id": approved_id,
        })
    return {"available": bool(options), "phases": options}


def prepare_phase_data(
    project_dir: Path,
    project_id: int,
    phase_cfg: Mapping[str, Any],
    phases_cfg: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one phase's controls, decision state, and immutable history."""

    project_dir = Path(project_dir).resolve()
    phase_slug = str(phase_cfg["slug"])
    recovery_only = bool(phase_cfg.get("recovery_only"))
    state = project_state.load(project_dir)
    approved_method_selection = None
    method_phase = state.get("phases", {}).get(
        project_state.METHOD_DEVELOPMENT_PHASE, {}
    )
    method_run_id = str(method_phase.get("approved_run") or "").strip()
    method_run = next(
        (
            candidate
            for candidate in method_phase.get("runs", [])
            if isinstance(candidate, Mapping)
            and str(candidate.get("run_id", "")) == method_run_id
        ),
        None,
    )
    if (
        method_run_id
        and isinstance(method_run, Mapping)
        and not bool(method_phase.get("stale"))
    ):
        decision = method_run.get("decision_record")
        selected = (
            decision.get("data", {}).get("selected_scientific_object")
            if isinstance(decision, Mapping)
            and isinstance(decision.get("data"), Mapping)
            else None
        )
        try:
            integrity_ok = bool(
                project_state.run_integrity_report(
                    project_dir,
                    project_state.METHOD_DEVELOPMENT_PHASE,
                    method_run_id,
                ).get("ok")
            )
        except (KeyError, OSError, project_state.ProjectStateError):
            integrity_ok = False
        if (
            method_run.get("status") == "approved"
            and integrity_ok
            and isinstance(selected, Mapping)
            and selected.get("kind") == "method"
            and str(selected.get("stable_id", "")).strip()
            and str(selected.get("version", "")).strip()
        ):
            approved_method_selection = {
                "kind": "method",
                "stable_id": str(selected["stable_id"]),
                "version": str(selected["version"]),
                "source_run_id": method_run_id,
                "decision_sha256": str(decision.get("sha256", "")),
            }
            # Enrich with the human-readable label from the method menu
            try:
                menu = method_menu.load_method_menu(project_dir)
            except Exception:
                menu = None
            if menu and isinstance(menu.get("entries"), list):
                match = next(
                    (
                        entry for entry in menu["entries"]
                        if isinstance(entry, Mapping)
                        and str(entry.get("stable_id", ""))
                        == approved_method_selection["stable_id"]
                    ),
                    None,
                )
                if isinstance(match, Mapping) and str(match.get("label", "")).strip():
                    approved_method_selection["label"] = str(match["label"])
    phase_state = state.get("phases", {}).get(
        phase_slug,
        {"status": "pending", "runs": [], "approved_run": None, "stale": False},
    )
    run_views = _phase_runs(project_dir, phase_slug, phase_state)
    by_id = {item["run_id"]: item for item in run_views}
    latest = by_id.get(str(phase_state.get("latest_run")))
    if latest is None and run_views:
        latest = run_views[-1]
    approved = by_id.get(str(phase_state.get("approved_run")))
    active_marker = state.get("active_run")
    active_anywhere = bool(active_marker)
    active_conflict = bool(active_marker and active_marker.get("conflict"))
    conflicting_active_runs = [
        dict(item)
        for item in (active_marker.get("runs", []) if active_conflict else [])
        if isinstance(item, Mapping)
    ]
    active_reference = None
    if active_conflict:
        active_reference = next(
            (
                item
                for item in conflicting_active_runs
                if item.get("phase_slug") == phase_slug
            ),
            None,
        )
    elif active_marker and active_marker.get("phase_slug") == phase_slug:
        active_reference = active_marker
    active_run = (
        by_id.get(str(active_reference.get("run_id"))) if active_reference else None
    )
    active_here = bool(active_run)
    awaiting_decision = next(
        (
            item
            for item in reversed(run_views)
            if item.get("status") == "awaiting_review"
        ),
        None,
    )
    displayed_latest = active_run if active_here else (awaiting_decision or latest)
    if (
        displayed_latest
        and not active_here
        and phase_slug in {
            "03-idea-evaluation",
            "05-review-revision",
        }
        and displayed_latest.get("frozen_plan", {}).get("available")
    ):
        try:
            displayed_latest["rerun_config"] = exact_rerun_options(
                project_dir, phase_slug, displayed_latest["run_id"]
            )
        except (
            KeyError,
            OSError,
            ValueError,
            LaunchError,
            project_state.ProjectStateError,
        ):
            displayed_latest["rerun_config"] = None
    raw_report = project_state.prerequisite_report(
        project_dir, phase_slug, _dependencies(phases_cfg)
    )
    report = _prerequisite_view(raw_report, phases_cfg)
    approval_report = None
    approval_subject = displayed_latest
    if approval_subject and (
        approval_subject.get("status") == "awaiting_review"
        or approval_subject.get("status") in project_state.ACTIVE_RUN_STATUSES
    ):
        approval_report = project_state.approval_context_report(
            project_dir,
            phase_slug,
            approval_subject["run_id"],
            _dependencies(phases_cfg),
        )
    policy = _rounds_policy(phase_cfg)
    stages = []
    completed_for_stages = active_run["rounds_completed"] if active_run else 0
    current_stage = active_run["current_round"] if active_run else None
    stage_source = (
        active_run.get("plan_stages", [])
        if active_run and active_run.get("plan_stages")
        else phase_cfg.get("stages", [])
    )
    for index, raw_stage in enumerate(stage_source, 1):
        stage = dict(raw_stage)
        if index <= completed_for_stages:
            stage["status"] = "completed"
        elif current_stage == index:
            stage["status"] = "running"
        else:
            stage["status"] = "pending"
        stages.append(stage)

    baseline_integrity_error = bool(approved and approved.get("integrity_error"))
    decision_state = _decision_state(phase_state, displayed_latest)
    decision_label = _decision_label(phase_state, displayed_latest)
    if baseline_integrity_error and (
        displayed_latest is None
        or displayed_latest.get("run_id") == approved.get("run_id")
    ):
        decision_state = "stale"
        decision_label = "Approved evidence is missing or changed"
    stale_reason = phase_state.get("stale_reason")
    if baseline_integrity_error and not stale_reason:
        stale_reason = (
            "Approved evidence is missing or changed, so it cannot be treated as "
            "a current baseline. Restore the recorded file or approve a replacement run."
        )

    configured_members = [
        str(member.get("role", "") if isinstance(member, Mapping) else member)
        for member in phase_cfg.get("members", [])
        if str(member.get("role", "") if isinstance(member, Mapping) else member)
    ]
    plan_view = {
        "frozen": False,
        "variant": (
            "Standard theory"
            if phase_slug == "03-idea-evaluation"
            and (
                phase_cfg.get("proof_audit") is not None
                or phase_cfg.get("available_run_plans") is not None
            )
            else "Full manuscript writing and independent review"
            if phase_slug == "05-review-revision"
            else "Standard phase plan"
        ),
        "pattern": str(phase_cfg.get("pattern", "")),
        "folder": str(phase_cfg.get("folder", "")),
        "members": configured_members,
    }
    if active_run and active_run.get("frozen_plan", {}).get("available"):
        frozen_plan = active_run["frozen_plan"]
        plan_view = {
            "frozen": True,
            "variant": frozen_plan.get("variant"),
            "pattern": frozen_plan.get("pattern"),
            "folder": frozen_plan.get("folder"),
            "members": list(frozen_plan.get("members", [])),
        }

    downstream_context = _downstream_context_options(
        project_dir, phase_slug, phases_cfg
    )
    return {
        "project_id": project_id,
        "phase_cfg": dict(phase_cfg),
        "phase_slug": phase_slug,
        "recovery_only": recovery_only,
        "recovery_source": phase_cfg.get("recovery_source"),
        "state": dict(phase_state),
        "status": (
            active_run.get("status", "running")
            if active_here
            else phase_state.get("status", "pending")
        ),
        "decision_state": decision_state,
        "decision_label": decision_label,
        "stale": bool(phase_state.get("stale")) or baseline_integrity_error,
        "stale_reason": stale_reason,
        "latest_run": displayed_latest,
        "approved_run": approved,
        "baseline_integrity_error": baseline_integrity_error,
        "active_run": active_run,
        "project_active_run": dict(active_marker) if active_marker else None,
        "run_active": active_here,
        "run_status": active_run,
        "active_conflict": active_conflict,
        "conflicting_active_runs": conflicting_active_runs,
        "active_elsewhere": (
            dict(active_marker) if active_anywhere and not active_here else False
        ),
        "can_start": not active_anywhere and not recovery_only,
        "launch_available": not active_anywhere and not recovery_only,
        "can_run": report["satisfied"],
        "prerequisite_report": report,
        "prerequisite_report_version": decision_report_version(
            "prerequisite", raw_report
        ),
        "approved_method_selection": approved_method_selection,
        "method_menu": (
            method_menu.load_method_menu(project_dir)
            if phase_requires_method_binding(phase_cfg)
               or phase_slug == project_state.METHOD_DEVELOPMENT_PHASE
            else None
        ),
        "approval_context_report": approval_report,
        "approval_context_report_version": (
            decision_report_version("approval_context", approval_report)
            if approval_report
            else None
        ),
        "gating_reason": "" if report["satisfied"] else report["message"],
        "rounds_policy": policy,
        "round_options": policy["options"],
        "stages": stages,
        "plan_view": plan_view,
        "run_history": list(reversed(run_views)),
        "summary_path": (
            displayed_latest.get("summary_path") if displayed_latest else None
        ),
        "downstream_context": downstream_context,
        "cross_phase_context": _cross_phase_context(
            project_dir, phase_slug, phases_cfg
        ),
        "method_details": (
            _method_details(project_dir)
            if phase_slug == project_state.METHOD_DEVELOPMENT_PHASE
            else []
        ),
        "method_comparison": (
            _method_comparison(project_dir)
            if phase_slug == project_state.METHOD_DEVELOPMENT_PHASE
            else ""
        ),
        "method_ranking_table": (
            _method_ranking_rows(project_dir)
            if phase_slug == project_state.METHOD_DEVELOPMENT_PHASE
            else []
        ),
    }


def prepare_overview_data(
    project_dir: Path,
    phases_cfg: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build non-linear decision cards for the project overview."""

    project_dir = Path(project_dir).resolve()
    state = project_state.load(project_dir)
    phases_state = state.get("phases", {})
    active = state.get("active_run")
    active_conflict = bool(active and active.get("conflict"))
    conflicting_active_runs = [
        dict(item)
        for item in (active.get("runs", []) if active_conflict else [])
        if isinstance(item, Mapping)
    ]
    dependencies = _dependencies(phases_cfg)
    cards: list[dict[str, Any]] = []
    # Pre-compute global ordinal rank for each run (by start time across ALL phases)
    # This gives every run its own horizontal slot — no clustering regardless of time gaps.
    from datetime import datetime
    def _parse_iso(ts: str | None):
        if not ts:
            return None
        try:
            return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    _all_runs_for_rank: list[tuple[str, datetime]] = []
    for phase_cfg in phases_cfg:
        phase_slug = str(phase_cfg["slug"])
        phase_state = phases_state.get(phase_slug, {})
        for r in phase_state.get("runs", []):
            if isinstance(r, Mapping):
                rid = str(r.get("run_id", ""))
                ts = _parse_iso(r.get("started"))
                if rid and ts:
                    _all_runs_for_rank.append((rid, ts))
    _all_runs_for_rank.sort(key=lambda x: x[1])
    _rank_by_id: dict[str, int] = {rid: i for i, (rid, _) in enumerate(_all_runs_for_rank)}
    _total_ranked = max(len(_all_runs_for_rank), 1)
    for number, phase_cfg in enumerate(phases_cfg, 1):
        phase_slug = str(phase_cfg["slug"])
        phase_state = phases_state.get(
            phase_slug,
            {"status": "pending", "runs": [], "approved_run": None, "stale": False},
        )
        views = _phase_runs(project_dir, phase_slug, phase_state)
        by_id = {item["run_id"]: item for item in views}
        latest = by_id.get(str(phase_state.get("latest_run")))
        if latest is None and views:
            latest = views[-1]
        approved = by_id.get(str(phase_state.get("approved_run")))
        report = _prerequisite_view(
            project_state.prerequisite_report(
                project_dir, phase_slug, dependencies
            ),
            phases_cfg,
        )
        active_reference = None
        if active_conflict:
            active_reference = next(
                (
                    item
                    for item in conflicting_active_runs
                    if item.get("phase_slug") == phase_slug
                ),
                None,
            )
        elif active and active.get("phase_slug") == phase_slug:
            active_reference = active
        active_view = (
            by_id.get(str(active_reference.get("run_id")))
            if active_reference
            else None
        )
        is_active = bool(active_view)
        awaiting_decision = next(
            (
                item
                for item in reversed(views)
                if item.get("status") == "awaiting_review"
            ),
            None,
        )
        displayed_latest = active_view if is_active else (awaiting_decision or latest)
        baseline_integrity_error = bool(approved and approved.get("integrity_error"))
        decision_state = _decision_state(phase_state, displayed_latest)
        decision_label = _decision_label(phase_state, displayed_latest)
        if baseline_integrity_error and (
            displayed_latest is None
            or displayed_latest.get("run_id") == approved.get("run_id")
        ):
            decision_state = "stale"
            decision_label = "Approved evidence is missing or changed"
        stale_reason = phase_state.get("stale_reason")
        if baseline_integrity_error and not stale_reason:
            stale_reason = "Approved evidence is missing or changed."
        cards.append({
            "number": number,
            "slug": phase_slug,
            "name": phase_cfg.get("name", phase_slug),
            "description": phase_cfg.get("description", ""),
            "pattern": phase_cfg.get("pattern", ""),
            "folder": phase_cfg.get("folder", ""),
            "members": list(phase_cfg.get("members", [])),
            "gated_by": list(phase_cfg.get("gated_by", [])),
            "recovery_only": bool(phase_cfg.get("recovery_only")),
            "recovery_source": phase_cfg.get("recovery_source"),
            "status": (
                active_view.get("status", "running")
                if is_active
                else phase_state.get("status", "pending")
            ),
            "decision_state": decision_state,
            "decision_label": decision_label,
            "run_count": len(views),
            "latest_run": displayed_latest,
            "approved_run": approved,
            "baseline_integrity_error": baseline_integrity_error,
            "is_active": is_active,
            "can_start": not bool(active) and not bool(phase_cfg.get("recovery_only")),
            "can_run": report["satisfied"],
            "prerequisite_report": report,
            "stale": bool(phase_state.get("stale")) or baseline_integrity_error,
            "stale_reason": stale_reason,
            "rounds_policy": _rounds_policy(phase_cfg),
            "last_run_started": (
                displayed_latest.get("started") if displayed_latest else None
            ),
            "last_run_completed": (
                displayed_latest.get("completed") if displayed_latest else None
            ),
            "last_run_rounds": (
                f"{displayed_latest['rounds_completed']}/{displayed_latest['rounds_requested']}"
                if displayed_latest
                else None
            ),
            "summary_path": (
                displayed_latest.get("summary_path") if displayed_latest else None
            ),
            "timeline_runs": [
                {
                    "run_id": v.get("run_id", ""),
                    "status": v.get("status", ""),
                    "display_status": v.get("display_status", v.get("status", "")),
                    "summary_available": bool(v.get("summary_available")),
                    "started": v.get("started"),
                    "completed": v.get("completed"),
                    "number": v.get("number") or v.get("run_number", ""),
                    "scientific_outcome": v.get("scientific_outcome", ""),
                    # Ordinal rank positioning: each run gets its own slot based on
                    # global temporal order. 5%–95% range keeps dots off the edges.
                    "left_pct": round(
                        5 + (_rank_by_id.get(str(v.get("run_id", "")), 0) / max(_total_ranked - 1, 1)) * 90,
                        1,
                    ),
                }
                for v in views
                if v.get("started")
            ],
        })
    return cards
