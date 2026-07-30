"""Focused tests for compact immutable knowledge mutation events."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from core import knowledge_events as events
from core import project_state


def _method(
    *,
    version: str = "v1",
    digest: str = "a" * 64,
) -> dict[str, str]:
    return {
        "stable_id": "method-a",
        "version": version,
        "definition_sha256": digest,
    }


def _statement(
    statement_id: str,
    *,
    wording: str,
    phase: str = "theory",
) -> dict[str, Any]:
    empirical = phase == "empirical"
    return {
        "statement_id": statement_id,
        "statement_type": (
            "Empirical statement" if empirical else "Mathematical statement"
        ),
        "wording": wording,
        "scope": "The stated model and regularity conditions.",
        "formulation_state": "Current",
        "assessment_status": "Supported",
        "evidential_basis": ["The current canonical phase package."],
        "source_provenance": ["knowledge-fragment.json"],
        "assumptions": ["The recorded conditions hold."],
        "uncertainty": ["The stated limitation remains."],
        "logical_status": "Not applicable" if empirical else "proved",
        "mathematical_result_type": (
            "Not applicable"
            if empirical
            else "asymptotic limit, rate, or distribution"
        ),
    }


def _fragment(
    *,
    phase_slug: str,
    generation: int,
    source_run_id: str,
    statements: list[dict[str, Any]],
    dependencies: list[dict[str, str]] | None = None,
    method: dict[str, str] | None = None,
    evidence_bindings: list[dict[str, Any]] | None = None,
    summary_point: str = "The current result is decision relevant.",
) -> dict[str, Any]:
    empirical = phase_slug == events.EMPIRICAL_PHASE
    result: dict[str, Any] = {
        "schema_version": 1,
        "kind": (
            "empirical_knowledge_fragment"
            if empirical
            else "theory_knowledge_fragment"
        ),
        "semantics": (
            "cumulative_evidence"
            if empirical
            else "complete_replacement"
        ),
        "coverage": "complete",
        "method": method or _method(),
        "generation": generation,
        "source_run_id": source_run_id,
        "statements": statements,
        "dependencies": dependencies or [],
        "lead_summary": {
            "fundamental_points": [summary_point],
            "decision_relevant_changes": [],
            "unresolved_questions": [],
        },
    }
    if empirical:
        result["evidence_bindings"] = evidence_bindings or []
    return result


def _payload(fragment: dict[str, Any]) -> bytes:
    return (
        json.dumps(fragment, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _index(
    fragment: dict[str, Any],
    statuses: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "method": fragment["method"],
        "generation": fragment["generation"],
        "source_run_id": fragment["source_run_id"],
        "entries": [
            {"evidence_id": evidence_id, "status": status}
            for evidence_id, status in sorted(statuses.items())
        ],
    }


def test_first_event_binds_exact_fragment_and_records_only_additions() -> None:
    fragment = _fragment(
        phase_slug=events.THEORY_PHASE,
        generation=1,
        source_run_id="run-001",
        statements=[
            _statement(
                "statement-b",
                wording="A complete asymptotic claim.",
            ),
            _statement(
                "statement-a",
                wording="A complete finite-sample claim.",
            ),
        ],
    )
    payload = _payload(fragment)

    event = events.build_event(
        phase_slug=events.THEORY_PHASE,
        previous_fragment_bytes=None,
        current_fragment_bytes=payload,
    )

    assert event["previous_baseline_status"] == "absent"
    assert event["previous_method_identity"] is None
    assert event["previous_generation"] is None
    assert event["current_generation"] == 1
    assert event["previous_fragment_sha256"] is None
    assert event["current_fragment_sha256"] == hashlib.sha256(
        payload
    ).hexdigest()
    assert event["statement_changes"] == [
        {
            "statement_id": "statement-a",
            "change_type": "added",
            "changed_fields": [],
        },
        {
            "statement_id": "statement-b",
            "change_type": "added",
            "changed_fields": [],
        },
    ]
    encoded = events.event_bytes(event)
    assert b"A complete asymptotic claim." not in encoded
    assert events.parse_event_bytes(encoded) == event


def test_later_event_records_revisions_and_removals_without_copying_text() -> None:
    previous = _fragment(
        phase_slug=events.THEORY_PHASE,
        generation=1,
        source_run_id="run-001",
        statements=[
            _statement("claim-main", wording="The original claim."),
            _statement("claim-aux", wording="An auxiliary claim."),
        ],
        dependencies=[{
            "source_statement_id": "claim-main",
            "relation": "depends_on",
            "target_statement_id": "claim-aux",
            "reason": "The main proof invokes the auxiliary claim.",
        }],
    )
    current = _fragment(
        phase_slug=events.THEORY_PHASE,
        generation=2,
        source_run_id="run-002",
        statements=[
            _statement("claim-main", wording="The repaired claim."),
        ],
    )

    event = events.build_event(
        phase_slug=events.THEORY_PHASE,
        previous_fragment_bytes=_payload(previous),
        current_fragment_bytes=_payload(current),
    )

    assert event["statement_changes"] == [
        {
            "statement_id": "claim-aux",
            "change_type": "removed",
            "changed_fields": [],
        },
        {
            "statement_id": "claim-main",
            "change_type": "revised",
            "changed_fields": ["wording"],
        },
    ]
    assert event["dependency_changes"] == [{
        "source_statement_id": "claim-main",
        "relation": "depends_on",
        "target_statement_id": "claim-aux",
        "change_type": "removed",
        "changed_fields": [],
    }]
    encoded = events.event_bytes(event)
    assert b"The original claim." not in encoded
    assert b"The repaired claim." not in encoded


def test_phase_four_event_records_evidence_binding_changes() -> None:
    first_binding = {
        "evidence_id": "pilot",
        "evidence_status": "current",
        "role": "scientific_result",
        "assessments": [],
    }
    previous = _fragment(
        phase_slug=events.EMPIRICAL_PHASE,
        generation=1,
        source_run_id="run-001",
        statements=[
            _statement(
                "empirical-main",
                wording="The pilot result is current.",
                phase="empirical",
            )
        ],
        evidence_bindings=[first_binding],
    )
    current_bindings = [
        {
            **first_binding,
            "evidence_status": "outdated",
        },
        {
            "evidence_id": "benchmark",
            "evidence_status": "current",
            "role": "scientific_result",
            "assessments": [],
        },
    ]
    current = _fragment(
        phase_slug=events.EMPIRICAL_PHASE,
        generation=2,
        source_run_id="run-002",
        method=_method(version="v2", digest="b" * 64),
        statements=[
            _statement(
                "empirical-main",
                wording="The pilot result is current.",
                phase="empirical",
            )
        ],
        evidence_bindings=current_bindings,
    )

    event = events.build_event(
        phase_slug=events.EMPIRICAL_PHASE,
        previous_fragment_bytes=_payload(previous),
        current_fragment_bytes=_payload(current),
        previous_evidence_index=_index(previous, {"pilot": "current"}),
        current_evidence_index=_index(
            current,
            {"benchmark": "current", "pilot": "outdated"},
        ),
    )

    assert event["previous_method_identity"]["version"] == "v1"
    assert event["current_method_identity"]["version"] == "v2"
    assert event["evidence_binding_changes"] == [
        {
            "evidence_id": "benchmark",
            "change_type": "added",
            "changed_fields": [],
        },
        {
            "evidence_id": "pilot",
            "change_type": "revised",
            "changed_fields": ["evidence_status"],
        },
    ]


def test_event_order_and_fingerprints_are_deterministic() -> None:
    fragment = _fragment(
        phase_slug=events.THEORY_PHASE,
        generation=1,
        source_run_id="run-001",
        statements=[
            _statement("statement-z", wording="Claim Z."),
            _statement("statement-a", wording="Claim A."),
        ],
    )
    payload = _payload(fragment)

    first = events.build_event(
        phase_slug=events.THEORY_PHASE,
        previous_fragment_bytes=None,
        current_fragment_bytes=payload,
    )
    second = events.build_event(
        phase_slug=events.THEORY_PHASE,
        previous_fragment_bytes=None,
        current_fragment_bytes=payload,
    )

    assert first == second
    assert events.event_bytes(first) == events.event_bytes(second)
    assert [
        item["statement_id"] for item in first["statement_changes"]
    ] == ["statement-a", "statement-z"]
    assert len(first["event_id"]) == 64
    assert len(first["event_sha256"]) == 64


def test_legacy_baseline_advances_without_inferred_item_changes() -> None:
    current = _fragment(
        phase_slug=events.THEORY_PHASE,
        generation=4,
        source_run_id="run-004",
        method=_method(version="v2", digest="b" * 64),
        statements=[
            _statement("current-claim", wording="The current repaired claim."),
        ],
    )

    event = events.build_event(
        phase_slug=events.THEORY_PHASE,
        previous_fragment_bytes=None,
        current_fragment_bytes=_payload(current),
        previous_baseline_status="legacy_unavailable",
        previous_method_identity=_method(),
        previous_generation=3,
    )

    assert event["previous_baseline_status"] == "legacy_unavailable"
    assert event["previous_generation"] == 3
    assert event["current_generation"] == 4
    assert event["previous_method_identity"] == _method()
    assert event["previous_fragment_sha256"] is None
    assert event["statement_changes"] == []
    assert event["dependency_changes"] == []
    assert event["evidence_binding_changes"] == []


@pytest.mark.parametrize(
    ("field", "change"),
    [
        (
            "statement_changes",
            {
                "statement_id": "current-claim",
                "change_type": "added",
                "changed_fields": [],
            },
        ),
        (
            "dependency_changes",
            {
                "source_statement_id": "current-claim",
                "relation": "depends_on",
                "target_statement_id": "other-claim",
                "change_type": "added",
                "changed_fields": [],
            },
        ),
        (
            "evidence_binding_changes",
            {
                "evidence_id": "legacy-result",
                "change_type": "added",
                "changed_fields": [],
            },
        ),
    ],
)
def test_schema_rejects_item_changes_for_legacy_unavailable_baseline(
    field: str,
    change: dict[str, Any],
) -> None:
    current = _fragment(
        phase_slug=events.THEORY_PHASE,
        generation=4,
        source_run_id="run-004",
        method=_method(version="v2", digest="b" * 64),
        statements=[
            _statement("current-claim", wording="The repaired claim."),
        ],
    )
    event = events.build_event(
        phase_slug=events.THEORY_PHASE,
        previous_fragment_bytes=None,
        current_fragment_bytes=_payload(current),
        previous_baseline_status="legacy_unavailable",
        previous_method_identity=_method(),
        previous_generation=3,
    )
    unsealed = {
        key: deepcopy(value)
        for key, value in event.items()
        if key != "event_sha256"
    }
    unsealed[field] = [change]

    with pytest.raises(
        events.KnowledgeEventValidationError,
        match="legacy unavailable",
    ):
        events.seal_event(unsealed)


def _first_event() -> dict[str, Any]:
    fragment = _fragment(
        phase_slug=events.THEORY_PHASE,
        generation=1,
        source_run_id="run-001",
        statements=[
            _statement("statement-a", wording="A current claim."),
        ],
    )
    return events.build_event(
        phase_slug=events.THEORY_PHASE,
        previous_fragment_bytes=None,
        current_fragment_bytes=_payload(fragment),
    )


def test_write_is_idempotent_and_read_uses_opaque_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    event = _first_event()

    first_path = events.write_event(project, event)
    second_path = events.write_event(project, event)

    assert first_path == second_path
    assert first_path.read_bytes() == events.event_bytes(event)
    assert "method-a" not in first_path.parts
    assert events.THEORY_PHASE not in first_path.parts
    assert events.read_event(
        project,
        "method-a",
        events.THEORY_PHASE,
        event["event_id"],
    ) == event


def test_write_rejects_different_bytes_at_deterministic_path(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    event = _first_event()
    events.write_event(project, event)
    changed = {
        key: deepcopy(value)
        for key, value in event.items()
        if key != "event_sha256"
    }
    changed["lead_summary"]["fundamental_points"] = [
        "A different compact summary."
    ]
    conflicting_event = events.seal_event(changed)

    with pytest.raises(events.KnowledgeEventConflict):
        events.write_event(project, conflicting_event)


def test_safe_removal_requires_exact_fingerprint(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    event = _first_event()
    path = events.write_event(project, event)

    with pytest.raises(events.KnowledgeEventConflict):
        events.remove_event(
            project,
            "method-a",
            events.THEORY_PHASE,
            event["event_id"],
            expected_event_sha256="f" * 64,
        )
    assert path.is_file()

    assert events.remove_event(
        project,
        "method-a",
        events.THEORY_PHASE,
        event["event_id"],
        expected_event_sha256=event["event_sha256"],
    )
    assert not path.exists()
    assert not events.remove_event(
        project,
        "method-a",
        events.THEORY_PHASE,
        event["event_id"],
        expected_event_sha256=event["event_sha256"],
    )


def test_idempotent_event_write_resyncs_existing_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    event = _first_event()
    path = events._write_event_unlocked(project, event)
    calls: list[Path] = []

    def fail_once(directory: Path) -> None:
        calls.append(Path(directory))
        if len(calls) == 1:
            raise OSError("simulated event directory sync failure")

    monkeypatch.setattr(
        project_state,
        "_sync_state_directory",
        fail_once,
    )

    with pytest.raises(OSError, match="simulated event directory"):
        events._write_event_unlocked(project, event)
    assert path.is_file()
    assert events._write_event_unlocked(project, event) == path
    assert calls == [path.parent, path.parent]


def test_event_removal_retry_resyncs_absent_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    event = _first_event()
    path = events._write_event_unlocked(project, event)
    calls: list[Path] = []

    def fail_once(directory: Path) -> None:
        calls.append(Path(directory))
        if len(calls) == 1:
            raise OSError("simulated event removal sync failure")

    monkeypatch.setattr(
        project_state,
        "_sync_state_directory",
        fail_once,
    )

    with pytest.raises(OSError, match="simulated event removal"):
        events._remove_event_unlocked(
            project,
            "method-a",
            events.THEORY_PHASE,
            event["event_id"],
            expected_event_sha256=event["event_sha256"],
        )
    assert not path.exists()
    assert events._remove_event_unlocked(
        project,
        "method-a",
        events.THEORY_PHASE,
        event["event_id"],
        expected_event_sha256=event["event_sha256"],
    ) is False
    assert calls == [path.parent, path.parent]
