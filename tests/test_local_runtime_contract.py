from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import webapp


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("localhost", "127.0.0.1"),
        ("LOCALHOST", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("127.0.0.42", "127.0.0.42"),
        ("::1", "::1"),
        ("[::1]", "::1"),
    ],
)
def test_loopback_bind_validation_accepts_only_local_forms(
    value: str, expected: str
) -> None:
    assert webapp._validated_loopback_host(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "0.0.0.0", "::", "192.168.1.20", "research.example", "localhost:5055"],
)
def test_loopback_bind_validation_refuses_exposed_or_ambiguous_hosts(
    value: str,
) -> None:
    with pytest.raises(RuntimeError):
        webapp._validated_loopback_host(value)


def test_webapp_import_refuses_non_loopback_environment() -> None:
    environment = dict(os.environ)
    environment["RESEARCH_HUB_HOST"] = "0.0.0.0"
    result = subprocess.run(
        [sys.executable, "-c", "import webapp"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert "Refusing non-loopback RESEARCH_HUB_HOST" in result.stderr


def test_flask_rejects_untrusted_host_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(webapp.app.config, "TESTING", True)
    monkeypatch.setitem(webapp.app.config, "SECRET_KEY", "test-only-secret")
    monkeypatch.setitem(
        webapp.app.config,
        "TRUSTED_HOSTS",
        webapp._trusted_hosts_for_bind("127.0.0.1"),
    )
    with webapp.app.test_client() as client:
        trusted = client.get("/static/style.css", base_url="http://127.0.0.1:5055")
        untrusted = client.get("/static/style.css", base_url="http://research.example")

    assert trusted.status_code == 200
    assert untrusted.status_code == 400


@pytest.mark.parametrize(
    "environment",
    [
        {"SERVER_ADDR": "0.0.0.0", "REMOTE_ADDR": "127.0.0.1"},
        {"SERVER_ADDR": "127.0.0.1", "REMOTE_ADDR": "192.168.1.20"},
    ],
)
def test_flask_rejects_non_loopback_server_or_client_addresses(
    monkeypatch: pytest.MonkeyPatch, environment: dict[str, str]
) -> None:
    monkeypatch.setitem(webapp.app.config, "TESTING", True)
    monkeypatch.setitem(webapp.app.config, "SECRET_KEY", "test-only-secret")
    with webapp.app.test_client() as client:
        response = client.get(
            "/static/style.css",
            base_url="http://127.0.0.1:5055",
            environ_overrides=environment,
        )

    assert response.status_code == 400


def test_repository_declares_source_run_installation() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    runtime = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    development = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "[build-system]" not in pyproject
    assert "[project]" not in pyproject
    assert "Flask==3.1.3" in runtime
    assert "Werkzeug==3.1.8" in runtime
    assert "-r requirements.txt" in development
    assert "pytest==8.4.1" in development
    assert "not distributed\nas a Python package or wheel" in readme
    assert "pip install -e" not in readme
