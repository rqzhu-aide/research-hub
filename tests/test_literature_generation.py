"""Generation and integrity tests for the cumulative literature record."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import literature_records


def _card(arxiv_id: str, *, run_id: str) -> str:
    return (
        "---\n"
        f'arxiv_id: "{arxiv_id}"\n'
        'title: "Generation Test Paper"\n'
        'authors: ["Careful Author"]\n'
        "year: 2026\n"
        'venue: "Journal of Storage Tests"\n'
        'relation: "theoretical foundation"\n'
        f'found_in_run: "{run_id}"\n'
        'found_by_role: "research_lead"\n'
        "also_found_in: []\n"
        "---\n\n"
        "# Generation Test Paper\n\n"
        "A classified source used to test current-record continuity.\n"
    )


def _prepare_run(
    project: Path,
    run_number: str,
    *,
    source_run_id: str,
) -> tuple[Path, dict[str, object]]:
    output = (
        project
        / "references"
        / "literature-review"
        / "run"
        / run_number
    )
    stage = literature_records.prepare_reference_delta(
        project,
        output,
        source_run_id=source_run_id,
    )
    return output, stage


def test_generations_advance_and_current_record_is_verified(tmp_path: Path) -> None:
    first_output, first_stage = _prepare_run(
        tmp_path,
        "01",
        source_run_id="literature-run-01",
    )
    first_delta = first_output / literature_records.STAGED_DELTA_DIRNAME
    (first_delta / "papers" / "paper.md").write_text(
        _card("2601.00001", run_id="01"),
        encoding="utf-8",
        newline="",
    )
    (first_delta / "literature-summary.md").write_text(
        "# Literature Summary\n\nFirst cumulative synthesis.\n",
        encoding="utf-8",
        newline="",
    )
    assert first_stage["prior_generation"] == 0
    assert first_stage["generation"] == 1
    first_seal = literature_records.seal_reference_delta(
        tmp_path,
        first_output,
    )
    first_promotion = literature_records.promote_reference_delta(
        tmp_path,
        first_output,
        first_seal,
    )
    assert first_promotion["source_run_id"] == "literature-run-01"
    assert first_promotion["generation"] == 1

    current = literature_records.load_current_literature_record(tmp_path)
    assert current is not None
    assert current["source_run_id"] == "literature-run-01"
    assert current["generation"] == 1
    assert current["paper_count"] == 1
    assert len(current["summary_sha256"]) == 64
    assert len(current["index_sha256"]) == 64

    second_output, second_stage = _prepare_run(
        tmp_path,
        "02",
        source_run_id="literature-run-02",
    )
    second_delta = second_output / literature_records.STAGED_DELTA_DIRNAME
    (second_delta / "literature-summary.md").write_text(
        "# Literature Summary\n\nSecond cumulative synthesis.\n",
        encoding="utf-8",
        newline="",
    )
    assert second_stage["prior_generation"] == 1
    assert second_stage["generation"] == 2
    second_seal = literature_records.seal_reference_delta(
        tmp_path,
        second_output,
    )
    literature_records.promote_reference_delta(
        tmp_path,
        second_output,
        second_seal,
    )

    current = literature_records.load_current_literature_record(tmp_path)
    assert current is not None
    assert current["source_run_id"] == "literature-run-02"
    assert current["generation"] == 2
    assert current["paper_count"] == 1


def test_current_loader_rejects_summary_tampering(tmp_path: Path) -> None:
    output, _ = _prepare_run(
        tmp_path,
        "01",
        source_run_id="literature-run-01",
    )
    delta = output / literature_records.STAGED_DELTA_DIRNAME
    (delta / "papers" / "paper.md").write_text(
        _card("2601.00002", run_id="01"),
        encoding="utf-8",
        newline="",
    )
    seal = literature_records.seal_reference_delta(tmp_path, output)
    literature_records.promote_reference_delta(tmp_path, output, seal)

    (tmp_path / literature_records.LITERATURE_SUMMARY).write_text(
        "# Literature Summary\n\nUntracked replacement.\n",
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        literature_records.LiteratureRecordValidationError,
        match="does not match",
    ):
        literature_records.load_current_literature_record(tmp_path)


def test_seal_rejects_tampered_prior_generation(tmp_path: Path) -> None:
    output, _ = _prepare_run(
        tmp_path,
        "01",
        source_run_id="literature-run-01",
    )
    baseline_path = (
        output
        / literature_records.STAGED_DELTA_DIRNAME
        / literature_records.BASELINE_FILENAME
    )
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["prior_generation"] = 7
    baseline_path.write_text(
        json.dumps(baseline, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        literature_records.StaleLiteratureRecord,
        match="prior generation",
    ):
        literature_records.seal_reference_delta(tmp_path, output)
