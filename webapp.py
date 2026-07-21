#!/usr/bin/env python3
"""Local web control surface for explicit Research Hub phase runs."""

from __future__ import annotations

import base64
import hmac
import hashlib
import html
import io
import ipaddress
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import traceback
from contextlib import contextmanager
from functools import wraps
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlsplit

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.sansio.utils import host_is_trusted

sys.path.insert(0, str(Path(__file__).parent.resolve()))

import hub
from scripts import project_state
from scripts.launch_run import (
    LaunchError,
    NUMERICAL_VALIDATION_PHASE,
    PAPER_WRITING_PHASE,
    THEORETICAL_ANALYSIS_PHASE,
    THEORY_PLAN_AUDIT_ONLY,
    THEORY_PLAN_STANDARD,
    THEORY_PLAN_STANDARD_WITH_AUDIT,
    cancel_active_run,
    exact_rerun_options,
    launch_plan_version,
    launch_run,
    reconcile_active_run,
    retry_run_cleanup,
    run_log_path,
    theory_audit_source_options,
)
from scripts.web_phase_data import (
    decision_report_version,
    prepare_overview_data,
    prepare_phase_data,
    recovery_phase_config,
)


MAX_PROJECT_SETTING_BYTES = 2 * 1024 * 1024
MAX_PROFILE_MEMORY_BYTES = 2 * 1024 * 1024


def _validated_loopback_host(value: str) -> str:
    """Return a safe local bind host or refuse a network-exposed address."""

    host = value.strip()
    if host.lower() == "localhost":
        return "127.0.0.1"
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise RuntimeError(
            "RESEARCH_HUB_HOST must be localhost or a literal loopback IP address."
        ) from exc
    if not address.is_loopback:
        raise RuntimeError(
            f"Refusing non-loopback RESEARCH_HUB_HOST {value!r}; "
            "Research Hub has no network authentication."
        )
    return address.compressed


def _trusted_hosts_for_bind(host: str) -> list[str]:
    """Allow normal local Host headers and the exact configured loopback bind."""

    trusted = ["localhost", "127.0.0.1", "[::1]"]
    configured = f"[{host}]" if ":" in host else host
    if configured not in trusted:
        trusted.append(configured)
    return trusted


def _is_loopback_request_address(value: object) -> bool:
    """Return whether one WSGI connection address is an explicit loopback IP."""

    text = str(value or "").strip()
    if not text:
        return False
    if text.lower() == "localhost":
        return True
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    text = text.split("%", 1)[0]
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


_BIND_HOST = _validated_loopback_host(
    os.environ.get("RESEARCH_HUB_HOST", "127.0.0.1")
)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("RESEARCH_HUB_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=os.environ.get("RESEARCH_HUB_HTTPS", "").lower()
    in {"1", "true", "yes"},
    TRUSTED_HOSTS=_trusted_hosts_for_bind(_BIND_HOST),
)

MAX_NAME_LENGTH = 160
MAX_DESCRIPTION_LENGTH = 2_000
MAX_BRIEF_LENGTH = 50_000
MAX_FEEDBACK_LENGTH = 5_000
MAX_LOG_BYTES = 1_000_000
_CONFIG_THREAD_LOCK = threading.RLock()


# ---------------------------------------------------------------------------
# Request and rendering security
# ---------------------------------------------------------------------------


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return str(token)


app.jinja_env.globals["csrf_token"] = csrf_token


def _project_identity_payload(
    project_id: int,
    project: dict[str, Any],
    project_dir: Path,
) -> dict[str, Any]:
    """Describe the exact workspace project represented by one rendered form."""

    return {
        "version": 1,
        "workspace": str(hub.get_workspace_dir().resolve(strict=True)),
        "project_id": int(project_id),
        "directory_name": str(project.get("directory_name") or ""),
        "project_path": str(project_dir.resolve(strict=True)),
    }


def _project_identity_key() -> bytes:
    key = app.secret_key
    if isinstance(key, bytes):
        return key
    return str(key).encode("utf-8")


def _encode_project_identity(identity: dict[str, Any]) -> str:
    payload = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(_project_identity_key(), payload, hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_project_identity(token: str) -> dict[str, Any]:
    if not token or len(token) > 8_192 or token.count(".") != 1:
        raise ValueError("The project form identity is missing or invalid. Reload the page")
    encoded, supplied_signature = token.split(".", 1)
    try:
        payload = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(
            "The project form identity is invalid. Reload the page"
        ) from exc
    expected_signature = hmac.new(
        _project_identity_key(), payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise ValueError("The project form identity is invalid. Reload the page")
    try:
        identity = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "The project form identity is invalid. Reload the page"
        ) from exc
    if (
        not isinstance(identity, dict)
        or identity.get("version") != 1
        or isinstance(identity.get("project_id"), bool)
        or not isinstance(identity.get("project_id"), int)
        or not all(
            isinstance(identity.get(field), str) and identity.get(field)
            for field in ("workspace", "directory_name", "project_path")
        )
    ):
        raise ValueError("The project form identity is invalid. Reload the page")
    return identity


def _make_project_identity_token(
    project_id: int,
    project: dict[str, Any],
    project_dir: Path,
) -> str:
    return _encode_project_identity(
        _project_identity_payload(project_id, project, project_dir)
    )


def _submitted_project_identity(project_id: int) -> dict[str, Any]:
    identity = _decode_project_identity(request.form.get("project_identity", "").strip())
    if identity["project_id"] != project_id:
        raise ValueError("The project form does not match this project. Reload the page")
    return identity


def _queried_project_identity(project_id: int) -> dict[str, Any]:
    """Decode the exact project identity carried by a read-side refresh."""

    identity = _decode_project_identity(
        request.args.get("project_identity", "").strip()
    )
    if identity["project_id"] != project_id:
        raise ValueError("The project refresh does not match this project. Reload the page")
    return identity


def _require_matching_project_identity(
    identity: dict[str, Any],
    project_id: int,
    project: dict[str, Any],
    project_dir: Path,
) -> None:
    current = _project_identity_payload(project_id, project, project_dir)
    supplied_payload = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    current_payload = json.dumps(
        current, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if not hmac.compare_digest(supplied_payload, current_payload):
        raise ValueError(
            "The workspace or project changed after this page was shown. "
            "Reload the page and review the action again"
        )


@app.before_request
def validate_host_header() -> None:
    server_address = request.environ.get("SERVER_ADDR")
    if server_address is not None and not _is_loopback_request_address(server_address):
        abort(400, description="Research Hub accepts requests only on a loopback server address.")
    if not _is_loopback_request_address(request.remote_addr):
        abort(400, description="Research Hub accepts requests only from a loopback client.")
    trusted_hosts = app.config.get("TRUSTED_HOSTS") or ()
    if not host_is_trusted(request.host, trusted_hosts):
        abort(400, description="The request Host header is not trusted.")


@app.before_request
def validate_csrf() -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    expected = str(session.get("csrf_token", ""))
    if not supplied or not expected or not hmac.compare_digest(str(supplied), expected):
        abort(400, description="The request token is missing or expired. Refresh and try again.")


@app.after_request
def security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.endpoint != "phase_summary":
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
            "form-action 'self'; img-src 'self' data:; connect-src 'self'; "
            "script-src 'self'; style-src 'self'; font-src 'self'",
        )
    return response


class _SafeHtml(HTMLParser):
    """Small whitelist sanitizer for project-brief Markdown output."""

    allowed_tags = {
        "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol",
        "li", "strong", "em", "code", "pre", "blockquote", "a", "table", "thead",
        "tbody", "tr", "th", "td",
    }
    void_tags = {"br", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.allowed_tags:
            return
        rendered: list[str] = []
        if tag == "a":
            values = dict(attrs)
            href = values.get("href") or ""
            parsed = urlsplit(href)
            if parsed.scheme.lower() in {"", "http", "https", "mailto"} and not href.startswith("//"):
                rendered.append(f'href="{html.escape(href, quote=True)}"')
                rendered.append('rel="noopener noreferrer"')
        suffix = (" " + " ".join(rendered)) if rendered else ""
        self.parts.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data))

    def get_html(self) -> str:
        return "".join(self.parts)


def _render_project_markdown(source: str) -> str:
    try:
        import markdown

        generated = markdown.markdown(
            html.escape(source), extensions=["extra", "sane_lists"]
        )
    except Exception:
        return ""
    sanitizer = _SafeHtml()
    sanitizer.feed(generated)
    sanitizer.close()
    return sanitizer.get_html()


def _bounded_form_value(name: str, limit: int, *, required: bool = False) -> str:
    value = request.form.get(name, "").strip()
    if required and not value:
        raise ValueError(f"{name.replace('_', ' ').title()} is required")
    if len(value) > limit:
        raise ValueError(f"{name.replace('_', ' ').title()} cannot exceed {limit:,} characters")
    return value


def _bounded_utf8_file(
    path: Path,
    *,
    maximum: int,
    label: str,
    allow_empty: bool = True,
) -> str:
    """Read a regular local text file without allowing an unbounded response."""

    payload = project_state.bounded_file_bytes(
        path,
        maximum=maximum,
        label=label,
        allow_empty=allow_empty,
    )
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not valid UTF-8") from exc


def _require_current_report_version(
    field_name: str,
    kind: str,
    report: dict[str, Any],
    changed_message: str,
) -> None:
    submitted = request.form.get(field_name, "").strip()
    expected = decision_report_version(kind, report)
    if not submitted or not hmac.compare_digest(submitted, expected):
        raise ValueError(changed_message)


# ---------------------------------------------------------------------------
# Config and profile helpers
# ---------------------------------------------------------------------------


@contextmanager
def _config_file_lock() -> Iterator[None]:
    lock_path = hub.CONFIG_PATH.with_suffix(".yaml.lock")
    with _CONFIG_THREAD_LOCK, hub._open_verified_lock_file(
        lock_path, label="hub configuration lock"
    ) as handle:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            hub._verify_open_lock_file(
                handle, lock_path, label="hub configuration lock"
            )
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _mutate_config(mutator: Callable[[Any], None]) -> tuple[str, str]:
    from ruamel.yaml import YAML

    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    with _config_file_lock():
        previous_text = _bounded_utf8_file(
            hub.CONFIG_PATH,
            maximum=hub.MAX_CONFIG_BYTES,
            label="hub configuration",
            allow_empty=False,
        )
        data = yaml_rt.load(previous_text)
        mutator(data)
        hub.validate_config(data, config_root=hub.CONFIG_PATH.parent)
        buffer = io.StringIO()
        yaml_rt.dump(data, buffer)
        fd, temporary_name = tempfile.mkstemp(
            prefix=".config-", suffix=".yaml.tmp", dir=hub.CONFIG_PATH.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as temporary:
                temporary.write(buffer.getvalue())
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, hub.CONFIG_PATH)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        return previous_text, buffer.getvalue()


def _restore_config_text(
    text: str, *, expected_current_text: str | None = None
) -> None:
    """Atomically restore a known-valid config after a failed external change."""

    with _config_file_lock():
        if expected_current_text is not None:
            current_text = _bounded_utf8_file(
                hub.CONFIG_PATH,
                maximum=hub.MAX_CONFIG_BYTES,
                label="hub configuration",
                allow_empty=False,
            )
            if not hmac.compare_digest(current_text, expected_current_text):
                raise RuntimeError(
                    "configuration changed after the workspace update; refusing "
                    "to overwrite the newer configuration during rollback"
                )
        fd, temporary_name = tempfile.mkstemp(
            prefix=".config-restore-", suffix=".yaml.tmp", dir=hub.CONFIG_PATH.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as temporary:
                temporary.write(text)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, hub.CONFIG_PATH)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def _profiles() -> list[dict[str, Any]]:
    return hub.get_agents(hub.load_config())


def list_hermes_profiles() -> list[str]:
    profiles_dir = Path.home() / ".hermes" / "profiles"
    if not profiles_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in profiles_dir.iterdir()
        if entry.is_dir() and (entry / "config.yaml").is_file()
    )


def _read_profile_config(profile_name: str) -> dict[str, Any]:
    if profile_name not in list_hermes_profiles():
        return {"model": None, "provider": None, "base_url": None, "config_exists": False}
    config_path = Path.home() / ".hermes" / "profiles" / profile_name / "config.yaml"
    try:
        import yaml

        config_text = _bounded_utf8_file(
            config_path,
            maximum=hub.MAX_CONFIG_BYTES,
            label=f"Hermes profile {profile_name!r} configuration",
            allow_empty=False,
        )
        data = yaml.safe_load(config_text) or {}
    except Exception:
        return {
            "model": None,
            "provider": None,
            "base_url": None,
            "config_exists": True,
            "config_error": True,
        }
    model = data.get("model") or {}
    fallbacks: list[dict[str, Any]] = []
    raw_fallbacks = data.get("fallback_providers")
    if isinstance(raw_fallbacks, str):
        try:
            import json

            parsed = json.loads(raw_fallbacks)
            if isinstance(parsed, list):
                fallbacks = [
                    {
                        "provider": item.get("provider") or item.get("base_url") or "?",
                        "model": item.get("model"),
                    }
                    for item in parsed
                    if isinstance(item, dict)
                ]
        except (TypeError, ValueError):
            pass
    return {
        "model": model.get("default"),
        "provider": model.get("provider"),
        "base_url": model.get("base_url"),
        "config_exists": True,
        "fallbacks": fallbacks,
    }


def _enrich_agent(agent: dict[str, Any]) -> None:
    memory = (
        Path.home()
        / ".hermes"
        / "profiles"
        / str(agent["profile"])
        / "memories"
        / "MEMORY.md"
    )
    agent["memory_exists"] = memory.is_file()
    agent["memory_size"] = memory.stat().st_size if memory.is_file() else 0
    runtime = _read_profile_config(str(agent["profile"]))
    agent["runtime_model"] = runtime["model"]
    agent["runtime_provider"] = runtime["provider"]
    agent["runtime_base_url"] = runtime["base_url"]
    agent["config_exists"] = runtime["config_exists"]
    agent["config_error"] = runtime.get("config_error", False)
    agent["fallbacks"] = runtime.get("fallbacks", [])


def _project_context(project_id: int) -> tuple[dict[str, Any], Path] | None:
    project = hub.get_project(project_id)
    project_dir = hub.get_project_dir(project_id)
    if not project or not project_dir:
        return None
    return dict(project), project_dir.resolve()


def _matching_project_context(
    project_id: int, identity: dict[str, Any]
) -> tuple[dict[str, Any], Path]:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    project, project_dir = resolved
    _require_matching_project_identity(
        identity, project_id, project, project_dir
    )
    return project, project_dir


@contextmanager
def _locked_submitted_project(
    project_id: int,
) -> Iterator[tuple[dict[str, Any], Path]]:
    """Revalidate a rendered project identity while workspace changes are excluded."""

    identity = _submitted_project_identity(project_id)
    with hub.operation_lock():
        yield _matching_project_context(project_id, identity)


def _locked_project_mutation(handler: Callable[..., Response]) -> Callable[..., Response]:
    """Hold the workspace lock around a project mutation from a rendered form."""

    @wraps(handler)
    def wrapped(project_id: int, *args: Any, **kwargs: Any) -> Response:
        try:
            with _locked_submitted_project(project_id):
                return handler(project_id, *args, **kwargs)
        except (OSError, RuntimeError, ValueError) as exc:
            flash(f"Action was not applied: {exc}", "error")
            phase_slug = kwargs.get("phase_slug")
            if isinstance(phase_slug, str) and phase_slug:
                return _redirect_phase(project_id, phase_slug)
            return redirect(url_for("project_view", project_id=project_id))

    return wrapped


def _phase_or_404(phase_slug: str) -> tuple[dict[str, Any], dict[str, Any]]:
    config = hub.load_config()
    phase = hub.get_phase_config(config, phase_slug)
    if not phase:
        abort(404, description="Unknown phase")
    return config, phase


def _phase_catalog(project_dir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return configured phases plus non-launchable records removed from config."""

    phases = [dict(phase) for phase in hub.get_phases_config(config)]
    configured = {str(phase["slug"]) for phase in phases}
    state = project_state.load(project_dir)
    for phase_slug, phase_state in state.get("phases", {}).items():
        slug = str(phase_slug)
        if slug in configured or not isinstance(phase_state, dict):
            continue
        phases.append(recovery_phase_config(project_dir, slug, phase_state))
    return phases


def _display_phase_or_404(
    project_dir: Path,
    config: dict[str, Any],
    phase_slug: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    phases = _phase_catalog(project_dir, config)
    phase = next(
        (candidate for candidate in phases if str(candidate.get("slug")) == phase_slug),
        None,
    )
    if phase is None:
        abort(404, description="Unknown phase")
    return phases, phase


def _gating(config: dict[str, Any]) -> dict[str, list[str]]:
    return {
        str(phase["slug"]): list(phase.get("gated_by", []))
        for phase in hub.get_phases_config(config)
    }


def _redirect_phase(project_id: int, phase_slug: str) -> Response:
    return redirect(url_for("project_view", project_id=project_id, tab=phase_slug))


# ---------------------------------------------------------------------------
# Project pages and decisions
# ---------------------------------------------------------------------------


@app.route("/")
def index() -> Response | str:
    projects = [dict(project) for project in hub.list_projects()]
    if projects:
        return redirect(url_for("project_view", project_id=projects[0]["id"]))
    return render_template("index.html", projects=[], project=None, profiles=_profiles())


@app.route("/project/new", methods=["GET", "POST"])
def new_project() -> Response | str:
    projects = [dict(project) for project in hub.list_projects()]
    if request.method == "GET":
        return render_template("new_project.html", projects=projects, project=None)
    try:
        name = _bounded_form_value("name", MAX_NAME_LENGTH, required=True)
        description = _bounded_form_value("description", MAX_DESCRIPTION_LENGTH)
        brief = _bounded_form_value("brief", MAX_BRIEF_LENGTH, required=True)
        project_id = hub.create_project(name, description, brief)
    except Exception as exc:
        app.logger.exception("Project creation failed")
        flash(f"Project could not be created: {exc}", "error")
        return redirect(url_for("new_project"))
    flash(f"Project '{name}' created. No phase has been started.", "success")
    return redirect(url_for("project_view", project_id=project_id))


@app.route("/project/<int:project_id>")
def project_view(project_id: int) -> Response | str:
    resolved = _project_context(project_id)
    if not resolved:
        flash(f"Project #{project_id} was not found.", "error")
        return redirect(url_for("index"))
    project, project_dir = resolved
    try:
        reconcile_active_run(project_dir)
    except Exception:
        app.logger.exception("Could not reconcile active run for project %s", project_id)

    config = hub.load_config()
    phases = _phase_catalog(project_dir, config)
    allowed_tabs = {str(phase["slug"]) for phase in phases}
    tab = request.args.get("tab", "overview")
    if tab != "overview" and tab not in allowed_tabs:
        flash(f"Unknown project tab: {tab}", "error")
        tab = "overview"

    setting_path = project_dir / "setting.md"
    settings_content = ""
    if setting_path.is_file():
        try:
            settings_content = _bounded_utf8_file(
                setting_path,
                maximum=MAX_PROJECT_SETTING_BYTES,
                label="project brief",
            )
        except (OSError, ValueError, project_state.ProjectStateError) as exc:
            settings_content = f"Project brief unavailable: {exc}"
    phase_summaries = prepare_overview_data(project_dir, phases)
    phase_config = (
        next(
            (phase for phase in phases if str(phase.get("slug")) == tab),
            None,
        )
        if tab != "overview"
        else None
    )
    phase_data = (
        prepare_phase_data(project_dir, project_id, phase_config, phases)
        if phase_config
        else None
    )
    if phase_data is not None and tab == THEORETICAL_ANALYSIS_PHASE:
        phase_data["theory_audit_sources"] = theory_audit_source_options(
            project_dir
        )
    if phase_data is not None and not phase_data.get("recovery_only"):
        phase_data["phase_plan_version"] = launch_plan_version(config, tab)
    context = {
        "project": project,
        "projects": [dict(item) for item in hub.list_projects()],
        "phase_configs": phases,
        "phase_summaries": phase_summaries,
        "active_tab": tab,
        "settings_content": settings_content,
        "settings_html": _render_project_markdown(settings_content),
        "proj_dir": str(project_dir),
        "project_identity": _make_project_identity_token(
            project_id, project, project_dir
        ),
        "phase_cfg": phase_config,
        "phase_data": phase_data,
        "run_permissions": {
            "unattended_tools": bool(config.get("hub", {}).get("allow_unattended_tools", False))
        },
        "profiles": _profiles(),
    }
    if request.headers.get("HX-Request") == "true":
        return render_template("_project_tabs.html", **context)
    return render_template("project.html", **context)


@app.post("/project/<int:project_id>/phase/<phase_slug>/start")
def start_phase(project_id: int, phase_slug: str) -> Response:
    config, phase = _phase_or_404(phase_slug)
    try:
        project_identity = _submitted_project_identity(project_id)
        _, project_dir = _matching_project_context(project_id, project_identity)
        submitted_phase_plan_version = _bounded_form_value(
            "phase_plan_version", 64, required=True
        ).lower()
        if any(
            character not in "0123456789abcdef"
            for character in submitted_phase_plan_version
        ):
            raise ValueError("Phase plan version is invalid")
        feedback = _bounded_form_value("feedback", MAX_FEEDBACK_LENGTH)
        rerun_from = request.form.get("rerun_from", "").strip()
        replace_awaiting_review = request.form.get(
            "replace_awaiting_review", ""
        ).strip()
        if replace_awaiting_review not in {"", "1"}:
            raise ValueError("The awaiting-result replacement choice is invalid")
        if len(rerun_from) > 256:
            raise ValueError("The selected prior run ID is too long")
        preserve_frozen_plan = request.form.get("preserve_frozen_plan", "").strip()
        if preserve_frozen_plan not in {"", "1"}:
            raise ValueError("The configuration-repeat request is invalid")
        review_target = request.form.get("review_target", "").strip()
        review_target_sha256 = request.form.get("review_target_sha256", "").strip()
        theory_plan = request.form.get("theory_plan", "").strip()
        proof_audit_source_run_id = request.form.get(
            "proof_audit_source_run_id", ""
        ).strip()
        if preserve_frozen_plan:
            if not rerun_from:
                raise ValueError("Select the prior run whose configuration should be repeated")
            if any(
                (
                    review_target,
                    review_target_sha256,
                    theory_plan,
                    proof_audit_source_run_id,
                )
            ):
                raise ValueError(
                    "Configuration repeats recover plan details from the sealed prior run"
                )
            exact_options = exact_rerun_options(
                project_dir, phase_slug, rerun_from
            )
            if exact_options["kind"] == "theory":
                theory_plan = exact_options["theory_plan"]
                proof_audit_source_run_id = exact_options.get(
                    "proof_audit_source_run_id", ""
                )
            elif exact_options["kind"] == "paper_review_only":
                review_target = exact_options["review_target"]
                review_target_sha256 = exact_options["review_target_sha256"]
            elif exact_options["kind"] != "paper_full":
                raise ValueError("The prior run's recorded configuration is not supported")
        if len(proof_audit_source_run_id) > 256:
            raise ValueError("The selected proof-audit source run ID is too long")
        if phase_slug == THEORETICAL_ANALYSIS_PHASE:
            theory_plan = theory_plan or THEORY_PLAN_STANDARD
            if theory_plan not in {
                THEORY_PLAN_STANDARD,
                THEORY_PLAN_STANDARD_WITH_AUDIT,
                THEORY_PLAN_AUDIT_ONLY,
            }:
                raise ValueError("Select one of the available Phase 03 run plans")
            if theory_plan == THEORY_PLAN_AUDIT_ONLY:
                if not proof_audit_source_run_id:
                    raise ValueError(
                        "Select the existing final theory artifact to audit"
                    )
            elif proof_audit_source_run_id:
                raise ValueError(
                    "A source run is only valid for the audit-only Phase 03 plan"
                )
        elif theory_plan or proof_audit_source_run_id:
            raise ValueError("Phase 03 run-plan options are not valid for this phase")

        run_specific_method_id = _bounded_form_value(
            "run_specific_method_id", 200
        )
        run_specific_method_version = _bounded_form_value(
            "run_specific_method_version", 200
        )
        if bool(run_specific_method_id) != bool(run_specific_method_version):
            raise ValueError(
                "Enter both the stable method ID and method version, or leave both blank"
            )
        method_bound_phase = phase_slug in {
            THEORETICAL_ANALYSIS_PHASE,
            NUMERICAL_VALIDATION_PHASE,
        }
        if not method_bound_phase and (
            run_specific_method_id or run_specific_method_version
        ):
            raise ValueError(
                "A run-specific method identity is valid only for Phase 03 or Phase 04"
            )
        if (
            phase_slug == THEORETICAL_ANALYSIS_PHASE
            and theory_plan == THEORY_PLAN_AUDIT_ONLY
            and (run_specific_method_id or run_specific_method_version)
        ):
            raise ValueError(
                "An audit-only Phase 03 run uses the method embodied in its sealed source artifact"
            )
        if review_target:
            if phase_slug != PAPER_WRITING_PHASE:
                raise ValueError("An exact manuscript review target is only valid in Phase 06")
            if len(review_target) > 4_096:
                raise ValueError("The selected manuscript path is too long")
            rounds = 2
        elif review_target_sha256:
            raise ValueError("A manuscript hash was supplied without a review target")
        elif phase_slug == THEORETICAL_ANALYSIS_PHASE:
            standard_stage_count = len(phase["stages"])
            rounds = {
                THEORY_PLAN_STANDARD: standard_stage_count,
                THEORY_PLAN_STANDARD_WITH_AUDIT: standard_stage_count + 1,
                THEORY_PLAN_AUDIT_ONLY: 1,
            }[theory_plan]
        elif phase["pattern"] == "sequential":
            rounds = len(phase["stages"])
        else:
            policy = phase["rounds"]
            rounds = int(request.form.get("rounds", policy["default"]))
            if rounds < policy["min"] or rounds > policy["max"]:
                raise ValueError(
                    f"Choose between {policy['min']} and {policy['max']} rounds"
                )

        report = project_state.prerequisite_report(
            project_dir, phase_slug, _gating(config)
        )
        _require_current_report_version(
            "prerequisite_report_version",
            "prerequisite",
            report,
            "Prerequisite status changed since this page was shown. Review the updated "
            "scientific inputs before launching",
        )
        override_reason = ""
        prerequisite_report_version = request.form.get(
            "prerequisite_report_version", ""
        ).strip()
        if not report["satisfied"]:
            if request.form.get("override_prerequisites") != "1":
                raise ValueError(
                    "Confirm the prerequisite override after reviewing the missing context"
                )
            override_reason = (
                "The user reviewed the web UI warning and explicitly chose to run despite "
                "missing or stale prerequisites: " + ", ".join(report["blockers"])
            )

        replace_note = None
        if rerun_from:
            source = project_state.get_run(project_dir, phase_slug, rerun_from)
            if source.get("status") == "awaiting_review":
                if replace_awaiting_review != "1":
                    raise ValueError(
                        "Explicitly confirm that this new run replaces the result "
                        "currently awaiting your decision"
                    )
                replace_note = (
                    "The user explicitly chose to replace the result awaiting review "
                    "with a new run. "
                    + (f"New direction: {feedback}" if feedback else "No additional direction supplied.")
                )
        elif replace_awaiting_review:
            raise ValueError(
                "An awaiting-result replacement choice requires an exact source run"
            )

        launch_options: dict[str, Any] = {
            "prerequisite_override_reason": override_reason,
            "prerequisite_report_version": prerequisite_report_version,
            "replace_awaiting_review_note": replace_note,
            "run_specific_method_id": run_specific_method_id,
            "run_specific_method_version": run_specific_method_version,
            "expected_phase_plan_version": submitted_phase_plan_version,
        }
        if replace_note is not None:
            launch_options["replace_awaiting_review_run_id"] = rerun_from
        if review_target:
            launch_options.update(
                review_target=review_target,
                review_target_sha256=review_target_sha256,
            )
        if phase_slug == THEORETICAL_ANALYSIS_PHASE:
            launch_options["theory_plan"] = theory_plan
            if theory_plan == THEORY_PLAN_AUDIT_ONLY:
                launch_options["proof_audit_source_run_id"] = (
                    proof_audit_source_run_id
                )
        result = launch_run(
            project_dir,
            project_id,
            phase_slug,
            feedback,
            rounds,
            expected_workspace_path=project_identity["workspace"],
            expected_project_directory_name=project_identity["directory_name"],
            expected_project_path=project_identity["project_path"],
            **launch_options,
        )
    except Exception as exc:
        app.logger.exception("Run launch failed")
        flash(f"Run could not be started: {exc}", "error")
        return _redirect_phase(project_id, phase_slug)

    unit = "stages" if phase["pattern"] == "sequential" else "rounds"
    flash(
        f"Run #{result['run_number']} started with {result['rounds_requested']} {unit}. "
        "It will stop for your review when the agents finish.",
        "success",
    )
    return _redirect_phase(project_id, phase_slug)


@app.get("/project/<int:project_id>/phase/<phase_slug>/progress")
def phase_progress(project_id: int, phase_slug: str) -> str:
    try:
        identity = _queried_project_identity(project_id)
        with hub.operation_lock():
            project, project_dir = _matching_project_context(project_id, identity)
            config = hub.load_config()
            phases, phase = _display_phase_or_404(project_dir, config, phase_slug)
            reconcile_active_run(project_dir)
            data = prepare_phase_data(
                project_dir, project_id, phase, phases
            )
            return render_template(
                "_run_progress.html",
                phase_data=data,
                project=project,
                project_id=project_id,
                phase_slug=phase_slug,
                project_identity=_make_project_identity_token(
                    project_id, project, project_dir
                ),
            )
    except ValueError as exc:
        abort(409, description=str(exc))


@app.post("/project/<int:project_id>/phase/<phase_slug>/run/<run_id>/approve")
@_locked_project_mutation
def approve_run(project_id: int, phase_slug: str, run_id: str) -> Response:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    _, project_dir = resolved
    config, _ = _phase_or_404(phase_slug)
    try:
        run = project_state.get_run(project_dir, phase_slug, run_id)
        decision_record = run.get("decision_record")
        baseline_acknowledgement = ""
        decision_record_version = None
        if not decision_record:
            raise ValueError(
                "This legacy run has no structured scientific baseline and cannot "
                "be approved in the Web UI. Keep it as readable history or rerun the phase"
            )
        if decision_record:
            if request.form.get("accept_proposed_baseline") != "1":
                raise ValueError(
                    "Review and accept the proposed scientific baseline before approval"
                )
            submitted_decision_version = request.form.get(
                "decision_record_version", ""
            ).strip().lower()
            expected_decision_version = str(
                decision_record.get("sha256", "")
            ).lower()
            if not submitted_decision_version or not hmac.compare_digest(
                submitted_decision_version, expected_decision_version
            ):
                raise ValueError(
                    "The proposed scientific baseline changed since this page was shown. "
                    "Review it and confirm again"
                )
            decision_record_version = submitted_decision_version
            approval_kind = request.form.get("approval_kind", "").strip()
            approval_labels = {
                "approve": "approve",
                "approve_with_limitations": "approve with limitations",
            }
            if approval_kind not in approval_labels:
                raise ValueError(
                    "Choose whether to approve or approve with limitations"
                )
            selected_object = decision_record.get("data", {}).get(
                "selected_scientific_object"
            )
            selected_object_acknowledgement = ""
            if phase_slug == project_state.METHOD_DEVELOPMENT_PHASE:
                if not isinstance(selected_object, dict):
                    raise ValueError(
                        "The Phase 02 result has no structured method selection. "
                        "Request revision before approval"
                    )
                if request.form.get("accept_selected_scientific_object") != "1":
                    raise ValueError(
                        "Review and explicitly select the named method ID and version"
                    )
                selected_object_acknowledgement = (
                    " The user also selected method "
                    f"{selected_object.get('stable_id')}, version "
                    f"{selected_object.get('version')}, for downstream study."
                )
            baseline_acknowledgement = (
                "The user reviewed the sealed summary and structured decision record "
                "and accepted the proposed scientific baseline as a whole, choosing to "
                f"{approval_labels[approval_kind]}."
                + selected_object_acknowledgement
            )
        approval_note = _bounded_form_value("approval_note", MAX_FEEDBACK_LENGTH)
        context_report = project_state.approval_context_report(
            project_dir, phase_slug, run_id, _gating(config)
        )
        context_acknowledgement = ""
        context_report_version = None
        if context_report["requires_acknowledgement"]:
            if request.form.get("acknowledge_context") != "1":
                raise ValueError(
                    "Review and acknowledge the run's overridden or changed context before approval"
                )
            _require_current_report_version(
                "approval_context_report_version",
                "approval_context",
                context_report,
                "Approval context changed since this page was shown. Review the updated "
                "warning and confirm again",
            )
            context_report_version = request.form.get(
                "approval_context_report_version", ""
            ).strip()
            affected = [
                str(item["phase"])
                for item in context_report.get("changed_sources", [])
            ]
            context_acknowledgement = (
                "The user reviewed the approval warning and chose to accept this result "
                "despite its overridden or changed launch context"
                + (": " + ", ".join(affected) if affected else ".")
            )
        staled = project_state.approve_run(
            project_dir,
            phase_slug,
            run_id,
            approval_kind=approval_kind,
            dependencies=_gating(config),
            reviewer="user",
            note=approval_note,
            baseline_acknowledgement=baseline_acknowledgement,
            expected_decision_record_version=decision_record_version,
            context_acknowledgement=context_acknowledgement,
            expected_context_report_version=context_report_version,
        )
    except Exception as exc:
        flash(f"Run could not be approved: {exc}", "error")
    else:
        message = "Run approved as the phase baseline."
        if staled:
            message += " Reassess affected phases: " + ", ".join(staled) + "."
        flash(message, "success")
    return _redirect_phase(project_id, phase_slug)


@app.post("/project/<int:project_id>/phase/<phase_slug>/run/<run_id>/revision")
@_locked_project_mutation
def request_revision(project_id: int, phase_slug: str, run_id: str) -> Response:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    _, project_dir = resolved
    _phase_or_404(phase_slug)
    try:
        feedback = _bounded_form_value("feedback", MAX_FEEDBACK_LENGTH, required=True)
        project_state.request_revision(
            project_dir, phase_slug, run_id, feedback, reviewer="user"
        )
    except Exception as exc:
        flash(f"Revision request could not be recorded: {exc}", "error")
    else:
        flash("Revision request recorded. Launch a rerun when you are ready.", "success")
    return _redirect_phase(project_id, phase_slug)


@app.post("/project/<int:project_id>/phase/<phase_slug>/run/<run_id>/cancel")
@_locked_project_mutation
def cancel_run(project_id: int, phase_slug: str, run_id: str) -> Response:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    _, project_dir = resolved
    try:
        project_state.get_run(project_dir, phase_slug, run_id)
    except KeyError:
        abort(404, description="Run not found")
    try:
        cancel_active_run(project_dir, phase_slug, run_id)
    except Exception as exc:
        app.logger.exception("Run cancellation failed")
        flash(f"Run could not be cancelled cleanly: {exc}", "error")
    else:
        flash("Run cancelled. Its completed artifacts and log remain in history.", "success")
    return _redirect_phase(project_id, phase_slug)


@app.post(
    "/project/<int:project_id>/phase/<phase_slug>/run/<run_id>/retry-cleanup"
)
@_locked_project_mutation
def retry_cleanup(project_id: int, phase_slug: str, run_id: str) -> Response:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    _, project_dir = resolved
    config = hub.load_config()
    _display_phase_or_404(project_dir, config, phase_slug)
    try:
        retry_run_cleanup(project_dir, phase_slug, run_id)
    except KeyError:
        abort(404, description="Run not found")
    except Exception as exc:
        flash(f"Cleanup retry did not complete: {exc}", "error")
    else:
        flash(
            "Cleanup completed and the project launch lock was released. "
            "The run record and completed artifacts remain in history.",
            "success",
        )
    return _redirect_phase(project_id, phase_slug)


@app.post(
    "/project/<int:project_id>/phase/<phase_slug>/run/<run_id>/recover-cleanup"
)
@_locked_project_mutation
def recover_cleanup(project_id: int, phase_slug: str, run_id: str) -> Response:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    _, project_dir = resolved
    config = hub.load_config()
    _display_phase_or_404(project_dir, config, phase_slug)
    try:
        if request.form.get("confirm_external_stopped") != "1":
            raise ValueError(
                "Confirm that the local worker and Hermes tasks have stopped"
            )
        note = _bounded_form_value(
            "recovery_note", MAX_FEEDBACK_LENGTH, required=True
        )
        released = project_state.recover_run_cleanup(
            project_dir, phase_slug, run_id, note
        )
        if not released:
            raise ValueError("This run is no longer waiting for cleanup recovery")
    except KeyError:
        abort(404, description="Run not found")
    except Exception as exc:
        flash(f"Cleanup lock was not released: {exc}", "error")
    else:
        flash(
            "Cleanup lock released from your explicit verification. "
            "The recovery note is preserved in the run history.",
            "success",
        )
    return _redirect_phase(project_id, phase_slug)


@app.get("/project/<int:project_id>/phase/<phase_slug>/run/<run_id>/summary")
def phase_summary(project_id: int, phase_slug: str, run_id: str) -> Response:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    _, project_dir = resolved
    try:
        run = project_state.get_run(project_dir, phase_slug, run_id)
    except KeyError:
        abort(404, description="Run not found")
    raw_path = run.get("final_summary")
    if not raw_path:
        abort(404, description="This run has no submitted summary")
    summary = (project_dir / str(raw_path)).resolve()
    try:
        summary.relative_to(project_dir)
    except ValueError:
        abort(404, description="Invalid summary path")
    if not summary.is_file():
        abort(404, description="Summary file not found")
    try:
        payload = project_state.bounded_file_bytes(
            summary,
            maximum=project_state.MAX_SUMMARY_BYTES,
            label="final summary",
        )
    except project_state.ProjectStateError as exc:
        abort(409, description=str(exc))
    recorded_hash = run.get("summary_sha256")
    if recorded_hash and hashlib.sha256(payload).hexdigest() != recorded_hash:
        abort(409, description="The submitted summary changed after it was recorded")
    response = Response(payload, mimetype="text/html")
    response.headers["Content-Security-Policy"] = (
        "sandbox; default-src 'none'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/project/<int:project_id>/phase/<phase_slug>/run/<run_id>/log")
def run_log(project_id: int, phase_slug: str, run_id: str) -> Response:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    _, project_dir = resolved
    try:
        project_state.get_run(project_dir, phase_slug, run_id)
    except KeyError:
        abort(404, description="Run not found")
    log_file = run_log_path(project_dir, phase_slug, run_id).resolve()
    try:
        log_file.relative_to(project_state.state_dir(project_dir).resolve())
    except ValueError:
        abort(404, description="Invalid log path")
    if not log_file.is_file():
        abort(404, description="Run log is not available yet")
    size = log_file.stat().st_size
    with open(log_file, "rb") as handle:
        if size > MAX_LOG_BYTES:
            handle.seek(size - MAX_LOG_BYTES)
        payload = handle.read(MAX_LOG_BYTES).decode("utf-8", errors="replace")
    if size > MAX_LOG_BYTES:
        payload = "[Earlier log output omitted]\n" + payload
    response = Response(payload, mimetype="text/plain")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/project/<int:project_id>/settings")
@_locked_project_mutation
def save_settings(project_id: int) -> Response:
    resolved = _project_context(project_id)
    if not resolved:
        abort(404, description="Project not found")
    _, project_dir = resolved
    try:
        content = _bounded_form_value("settings_content", MAX_BRIEF_LENGTH)
        target = project_dir / "setting.md"
        fd, temporary_name = tempfile.mkstemp(
            prefix=".setting-", suffix=".md.tmp", dir=project_dir
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, target)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
    except Exception as exc:
        flash(f"Project brief could not be saved: {exc}", "error")
    else:
        flash("Project brief saved. Future runs will use the new version.", "success")
    return redirect(url_for("project_view", project_id=project_id))


@app.post("/project/<int:project_id>/open-folder")
def open_folder(project_id: int) -> tuple[str, int]:
    try:
        with _locked_submitted_project(project_id) as (_, project_dir):
            if os.name == "nt":
                os.startfile(str(project_dir))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(
                    ["open", str(project_dir)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    ["xdg-open", str(project_dir)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
    except Exception as exc:
        return f"Could not open project directory: {exc}", 500
    return "", 204


# ---------------------------------------------------------------------------
# Hub and profile settings
# ---------------------------------------------------------------------------


@app.get("/settings")
def hub_settings() -> str:
    config = hub.load_config()
    projects = [dict(project) for project in hub.list_projects()]
    return render_template(
        "hub_settings.html",
        workspace_dir=str(hub.get_workspace_dir()),
        projects_dir=str(hub.get_projects_dir()),
        db_path=str(hub.get_db_path()),
        hub_config=config.get("hub", {}),
        projects=projects,
        project=None,
        project_count=len(projects),
    )


@app.post("/settings/workspace")
def change_workspace() -> Response:
    try:
        with hub.operation_lock():
            original_config = _bounded_utf8_file(
                hub.CONFIG_PATH,
                maximum=hub.MAX_CONFIG_BYTES,
                label="hub configuration",
                allow_empty=False,
            )
            new_workspace = _bounded_form_value(
                "workspace_dir", 4_096, required=True
            )
            for item in hub.list_projects():
                project_dir = hub.get_project_dir(int(item["id"]))
                if project_dir and project_state.get_active_run(project_dir):
                    raise ValueError(
                        "Stop the active project run before changing workspaces"
                    )

            def update(data: Any) -> None:
                data.setdefault("hub", {})["workspace_dir"] = new_workspace

            mutation = _mutate_config(update)
            if isinstance(mutation, tuple) and len(mutation) == 2:
                previous_text, written_text = mutation
            else:
                previous_text = original_config
                written_text = _bounded_utf8_file(
                    hub.CONFIG_PATH,
                    maximum=hub.MAX_CONFIG_BYTES,
                    label="hub configuration",
                    allow_empty=False,
                )
            try:
                hub.init_db(verbose=False)
            except Exception:
                _restore_config_text(
                    previous_text, expected_current_text=written_text
                )
                raise
    except Exception as exc:
        app.logger.exception("Workspace update failed")
        flash(f"Workspace could not be changed: {exc}", "error")
    else:
        flash(
            "Workspace changed. Existing project files were not moved; switch back to view "
            "the prior workspace registry.",
            "success",
        )
    return redirect(url_for("hub_settings"))


@app.get("/profiles")
def profiles_view() -> str:
    agents = [dict(agent) for agent in _profiles()]
    for agent in agents:
        _enrich_agent(agent)
    return render_template(
        "profiles.html",
        agents=agents,
        all_profiles=list_hermes_profiles(),
        projects=[dict(project) for project in hub.list_projects()],
        project=None,
    )


@app.post("/agent/<agent_id>/profile")
def assign_agent_profile(agent_id: str) -> Response | tuple[str, int] | str:
    new_profile = request.form.get("profile", "").strip()
    available = list_hermes_profiles()
    if new_profile not in available:
        return "Unknown Hermes profile", 400

    found = False

    def update(data: Any) -> None:
        nonlocal found
        for agent in data.get("agents", []):
            if agent.get("id") == agent_id:
                agent["profile"] = new_profile
                found = True
                return

    try:
        with hub.operation_lock():
            _mutate_config(update)
    except Exception as exc:
        return f"Profile assignment failed: {exc}", 400
    if not found:
        return "Unknown agent role", 404
    agent = hub.get_agent(hub.load_config(), agent_id)
    if not agent:
        return "Agent role disappeared after update", 500
    rendered = dict(agent)
    _enrich_agent(rendered)
    if request.headers.get("HX-Request") == "true":
        return render_template("_profile_card.html", a=rendered, all_profiles=available)
    flash(f"{rendered['name']} now uses the {new_profile} profile for future runs.", "success")
    return redirect(url_for("profiles_view"))


@app.get("/profiles/<name>/memory")
def profile_memory(name: str) -> str:
    if name not in list_hermes_profiles():
        abort(404, description="Unknown Hermes profile")
    memory = Path.home() / ".hermes" / "profiles" / name / "memories" / "MEMORY.md"
    if memory.is_file():
        try:
            content = _bounded_utf8_file(
                memory,
                maximum=MAX_PROFILE_MEMORY_BYTES,
                label=f"profile {name!r} memory",
            )
        except (OSError, ValueError, project_state.ProjectStateError) as exc:
            content = f"(Profile memory is unavailable: {exc})"
    else:
        content = f"(No MEMORY.md found for profile '{name}')"
    return render_template(
        "profile_memory.html",
        name=name,
        content=content,
        projects=[dict(project) for project in hub.list_projects()],
        project=None,
    )


if __name__ == "__main__":
    port = int(os.environ.get("RESEARCH_HUB_PORT", "5055"))
    debug = os.environ.get("RESEARCH_HUB_DEBUG", "").lower() in {"1", "true", "yes"}
    display_host = f"[{_BIND_HOST}]" if ":" in _BIND_HOST else _BIND_HOST
    print(f"[webapp] Research Hub Web UI: http://{display_host}:{port}")
    app.run(host=_BIND_HOST, port=port, debug=debug)
