"""Focused tests for the cumulative Phase 01 reference library."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from core import literature_records


def _card(
    title: str,
    *,
    arxiv_id: str | None = None,
    doi: str | None = None,
    pmid: str | None = None,
    pmcid: str | None = None,
    repository_url: str | None = None,
    github_repo: str | None = None,
    pypi_package: str | None = None,
    found_in_run: str = "01",
    found_by_role: str = "research_lead",
    also_found_in: tuple[str, ...] = (),
    relation: str = "direct prior work",
    body: str = "A precise assessment of this source.",
) -> str:
    identity_rows = []
    for field, value in (
        ("arxiv_id", arxiv_id),
        ("doi", doi),
        ("pmid", pmid),
        ("pmcid", pmcid),
        ("repository_url", repository_url),
        ("github_repo", github_repo),
        ("pypi_package", pypi_package),
    ):
        if value is not None:
            identity_rows.append(f"{field}: {json.dumps(value)}\n")
    also = json.dumps(list(also_found_in))
    return (
        "---\n"
        + "".join(identity_rows)
        + f"title: {json.dumps(title)}\n"
        + 'authors: ["First Author", "Second Author"]\n'
        + "year: 2025\n"
        + 'venue: "Journal of Careful Tests"\n'
        + f"relation: {json.dumps(relation)}\n"
        + f"found_in_run: {json.dumps(found_in_run)}\n"
        + f"found_by_role: {json.dumps(found_by_role)}\n"
        + f"also_found_in: {also}\n"
        + "---\n\n"
        + f"# {title}\n\n"
        + body
        + "\n"
    )


def _delta_dir(output: Path) -> Path:
    return output / literature_records.STAGED_DELTA_DIRNAME


def _run_delta(
    project: Path,
    output: Path,
    *,
    cards: dict[str, str],
    summary: str,
) -> dict[str, Any]:
    literature_records.prepare_reference_delta(project, output)
    staged = _delta_dir(output)
    for filename, contents in cards.items():
        (staged / literature_records.STAGED_PAPERS_DIRNAME / filename).write_text(
            contents,
            encoding="utf-8",
            newline="",
        )
    (staged / literature_records.STAGED_SUMMARY_FILENAME).write_text(
        summary,
        encoding="utf-8",
        newline="",
    )
    seal = literature_records.seal_reference_delta(project, output)
    return literature_records.promote_reference_delta(project, output, seal)


def _canonical_bytes(project: Path) -> dict[str, bytes]:
    references = project / literature_records.REFERENCE_DIR
    result: dict[str, bytes] = {}
    papers = project / literature_records.PAPERS_DIR
    if papers.exists():
        for path in sorted(papers.iterdir(), key=lambda value: value.name):
            result[f"papers/{path.name}"] = path.read_bytes()
    for filename in (
        literature_records.REFERENCE_INDEX.name,
        literature_records.LITERATURE_SUMMARY.name,
    ):
        path = references / filename
        if path.exists():
            result[filename] = path.read_bytes()
    return result


def _frozen_current(project: Path) -> dict[str, Any]:
    current = literature_records.load_current_literature_record(project)
    assert current is not None
    summary = (project / literature_records.LITERATURE_SUMMARY).read_bytes()
    index = (project / literature_records.REFERENCE_INDEX).read_bytes()
    return {
        "generation": current["generation"],
        "source_run_id": current["source_run_id"],
        "summary_bytes": summary,
        "summary_sha256": current["summary_sha256"],
        "index_bytes": index,
        "index_sha256": current["index_sha256"],
    }


def test_initial_promotion_builds_cards_index_and_summary(tmp_path: Path) -> None:
    output = tmp_path / "references" / "literature-review" / "run" / "01"

    promotion = _run_delta(
        tmp_path,
        output,
        cards={
            "arxiv-2509-09162.md": _card(
                "A New Statistical Method",
                arxiv_id="arXiv:2509.09162v2",
                doi="https://doi.org/10.1234/Example.7",
            )
        },
        summary="# Literature Summary\n\nCurrent evidence and coverage gaps.\n",
    )

    assert promotion["added"] == ["arxiv-2509-09162.md"]
    assert "amended" not in promotion
    assert (
        tmp_path / literature_records.PAPERS_DIR / "arxiv-2509-09162.md"
    ).exists()
    assert (
        tmp_path / literature_records.LITERATURE_SUMMARY
    ).read_text(encoding="utf-8").startswith("# Literature Summary")
    index = json.loads(
        (tmp_path / literature_records.REFERENCE_INDEX).read_text(
            encoding="utf-8"
        )
    )
    assert index["kind"] == "reference_index"
    assert index["entries"][0]["aliases"] == [
        "arxiv:2509.09162",
        "doi:10.1234/example.7",
    ]
    assert index["entries"][0]["found_in_run"] == "01"


def test_schema_13_stage_uses_the_exact_frozen_literature_source(
    tmp_path: Path,
) -> None:
    first = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first,
        cards={
            "first.md": _card("First Paper", arxiv_id="2401.00001")
        },
        summary="# Literature Summary\n\nFrozen synthesis.\n",
    )
    frozen = _frozen_current(tmp_path)
    second = tmp_path / "references" / "literature-review" / "run" / "02"

    stage = literature_records.prepare_reference_delta(
        tmp_path,
        second,
        source_run_id="p1-second",
        frozen_current=frozen,
    )

    assert stage["prior_generation"] == frozen["generation"]
    assert (
        _delta_dir(second) / literature_records.STAGED_SUMMARY_FILENAME
    ).read_bytes() == frozen["summary_bytes"]


def test_schema_13_stage_rejects_a_newer_live_literature_record(
    tmp_path: Path,
) -> None:
    first = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first,
        cards={
            "first.md": _card("First Paper", arxiv_id="2401.00001")
        },
        summary="# Literature Summary\n\nFirst synthesis.\n",
    )
    frozen = _frozen_current(tmp_path)
    second = tmp_path / "references" / "literature-review" / "run" / "02"
    _run_delta(
        tmp_path,
        second,
        cards={
            "second.md": _card(
                "Second Paper",
                arxiv_id="2401.00002",
                found_in_run="02",
            )
        },
        summary="# Literature Summary\n\nUpdated synthesis.\n",
    )
    third = tmp_path / "references" / "literature-review" / "run" / "03"

    with pytest.raises(
        literature_records.StaleLiteratureRecord,
        match="changed after this run was frozen",
    ):
        literature_records.prepare_reference_delta(
            tmp_path,
            third,
            frozen_current=frozen,
        )

    assert not _delta_dir(third).exists()


def test_schema_13_frozen_absence_rejects_a_later_literature_record(
    tmp_path: Path,
) -> None:
    first = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first,
        cards={
            "first.md": _card("First Paper", arxiv_id="2401.00001")
        },
        summary="# Literature Summary\n\nAppeared after launch.\n",
    )
    second = tmp_path / "references" / "literature-review" / "run" / "02"

    with pytest.raises(
        literature_records.StaleLiteratureRecord,
        match="appeared after this run was frozen",
    ):
        literature_records.prepare_reference_delta(
            tmp_path,
            second,
            frozen_current=None,
        )

    assert not _delta_dir(second).exists()


def test_legacy_stage_without_frozen_source_uses_the_live_summary(
    tmp_path: Path,
) -> None:
    first = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first,
        cards={
            "first.md": _card("First Paper", arxiv_id="2401.00001")
        },
        summary="# Literature Summary\n\nCurrent live synthesis.\n",
    )
    live_summary = (
        tmp_path / literature_records.LITERATURE_SUMMARY
    ).read_bytes()
    second = tmp_path / "references" / "literature-review" / "run" / "02"

    literature_records.prepare_reference_delta(tmp_path, second)

    assert (
        _delta_dir(second) / literature_records.STAGED_SUMMARY_FILENAME
    ).read_bytes() == live_summary


def test_append_preserves_every_existing_card_byte_for_byte(tmp_path: Path) -> None:
    first_output = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first_output,
        cards={
            "first.md": _card(
                "First Paper",
                arxiv_id="2401.00001",
            )
        },
        summary="# Literature Summary\n\nFirst paper.\n",
    )
    first_path = tmp_path / literature_records.PAPERS_DIR / "first.md"
    original = first_path.read_bytes()

    second_output = tmp_path / "references" / "literature-review" / "run" / "02"
    promotion = _run_delta(
        tmp_path,
        second_output,
        cards={
            "second.md": _card(
                "Second Paper",
                pmid="https://pubmed.ncbi.nlm.nih.gov/12345678/",
                pmcid="PMC7654321",
                found_in_run="02",
                found_by_role="theorist",
            )
        },
        summary="# Literature Summary\n\nFirst and second papers.\n",
    )

    assert promotion["added"] == ["second.md"]
    assert first_path.read_bytes() == original
    assert sorted(path.name for path in first_path.parent.iterdir()) == [
        "first.md",
        "second.md",
    ]
    index = json.loads(
        (tmp_path / literature_records.REFERENCE_INDEX).read_text(
            encoding="utf-8"
        )
    )
    assert len(index["entries"]) == 2


def test_same_filename_is_rejected_without_changing_current_library(
    tmp_path: Path,
) -> None:
    first_output = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first_output,
        cards={
            "theory.md": _card(
                "Theory Paper",
                arxiv_id="2302.00003",
                body="Initial assessment.",
            )
        },
        summary="# Literature Summary\n\nInitial assessment.\n",
    )
    before = _canonical_bytes(tmp_path)

    second_output = tmp_path / "references" / "literature-review" / "run" / "02"
    with pytest.raises(
        literature_records.LiteratureRecordValidationError,
        match="accepts only new references",
    ):
        _run_delta(
            tmp_path,
            second_output,
            cards={
                "theory.md": _card(
                    "Theory Paper",
                    arxiv_id="2302.00003v3",
                    body="Attempted replacement.",
                )
            },
            summary="# Literature Summary\n\nAttempted replacement.\n",
        )

    assert _canonical_bytes(tmp_path) == before


def test_existing_filename_is_rejected_case_insensitively(
    tmp_path: Path,
) -> None:
    first_output = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first_output,
        cards={
            "Fixed.md": _card(
                "Fixed Identity",
                arxiv_id="2201.00001",
            )
        },
        summary="# Literature Summary\n\nFixed identity.\n",
    )
    second_output = tmp_path / "references" / "literature-review" / "run" / "02"
    literature_records.prepare_reference_delta(tmp_path, second_output)
    staged = _delta_dir(second_output)
    (staged / "papers" / "fixed.md").write_text(
        _card(
            "Different Paper",
            arxiv_id="2201.99999",
            found_in_run="02",
        ),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        literature_records.LiteratureRecordValidationError,
        match="conflicts with existing reference card",
    ):
        literature_records.seal_reference_delta(tmp_path, second_output)


def test_duplicate_alias_under_a_new_filename_is_rejected(tmp_path: Path) -> None:
    first_output = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first_output,
        cards={
            "canonical.md": _card(
                "Canonical Paper",
                doi="10.1000/ABC.123",
            )
        },
        summary="# Literature Summary\n\nCanonical paper.\n",
    )
    second_output = tmp_path / "references" / "literature-review" / "run" / "02"
    literature_records.prepare_reference_delta(tmp_path, second_output)
    staged = _delta_dir(second_output)
    (staged / "papers" / "duplicate.md").write_text(
        _card(
            "Same Paper Under Another Name",
            doi="https://doi.org/10.1000/abc.123",
            found_in_run="02",
        ),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        literature_records.LiteratureRecordValidationError,
        match="duplicates canonical identity",
    ):
        literature_records.seal_reference_delta(tmp_path, second_output)


def test_repository_aliases_are_canonicalized_for_duplicate_detection(
    tmp_path: Path,
) -> None:
    first_output = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first_output,
        cards={
            "software.md": _card(
                "Reference Implementation",
                github_repo="ResearchOrg/Important-Code",
            )
        },
        summary="# Literature Summary\n\nReference implementation.\n",
    )
    second_output = tmp_path / "references" / "literature-review" / "run" / "02"
    literature_records.prepare_reference_delta(tmp_path, second_output)
    staged = _delta_dir(second_output)
    (staged / "papers" / "duplicate-software.md").write_text(
        _card(
            "Duplicated Repository",
            repository_url="http://www.github.com/researchorg/important-code.git",
            found_in_run="02",
        ),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        literature_records.LiteratureRecordValidationError,
        match="duplicates canonical identity",
    ):
        literature_records.seal_reference_delta(tmp_path, second_output)


def test_promotion_rejects_a_changed_live_baseline_without_overwrite(
    tmp_path: Path,
) -> None:
    first_output = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first_output,
        cards={
            "first.md": _card(
                "First Paper",
                arxiv_id="2101.00001",
            )
        },
        summary="# Literature Summary\n\nFirst baseline.\n",
    )
    second_output = tmp_path / "references" / "literature-review" / "run" / "02"
    literature_records.prepare_reference_delta(tmp_path, second_output)
    staged = _delta_dir(second_output)
    (staged / "papers" / "second.md").write_text(
        _card(
            "Second Paper",
            arxiv_id="2101.00002",
            found_in_run="02",
        ),
        encoding="utf-8",
        newline="",
    )
    (staged / "literature-summary.md").write_text(
        "# Literature Summary\n\nProposed second baseline.\n",
        encoding="utf-8",
        newline="",
    )
    seal = literature_records.seal_reference_delta(tmp_path, second_output)

    live_summary = tmp_path / literature_records.LITERATURE_SUMMARY
    live_summary.write_text(
        "# Literature Summary\n\nConcurrent scientific correction.\n",
        encoding="utf-8",
        newline="",
    )
    concurrent = _canonical_bytes(tmp_path)

    with pytest.raises(literature_records.StaleLiteratureRecord, match="changed"):
        literature_records.promote_reference_delta(
            tmp_path,
            second_output,
            seal,
        )

    assert _canonical_bytes(tmp_path) == concurrent


def test_post_seal_delta_change_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "references" / "literature-review" / "run" / "01"
    literature_records.prepare_reference_delta(tmp_path, output)
    staged = _delta_dir(output)
    card_path = staged / "papers" / "paper.md"
    card_path.write_text(
        _card("Paper", arxiv_id="2001.00001"),
        encoding="utf-8",
        newline="",
    )
    seal = literature_records.seal_reference_delta(tmp_path, output)
    card_path.write_text(
        _card(
            "Paper",
            arxiv_id="2001.00001",
            body="Changed after submission.",
        ),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(literature_records.StaleLiteratureRecord, match="changed"):
        literature_records.verify_reference_delta_seal(
            tmp_path,
            output,
            seal,
        )


def test_failed_component_replacement_restores_exact_prior_library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_output = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        first_output,
        cards={
            "first.md": _card(
                "First Paper",
                arxiv_id="1901.00001",
            )
        },
        summary="# Literature Summary\n\nStable baseline.\n",
    )
    original = _canonical_bytes(tmp_path)

    second_output = tmp_path / "references" / "literature-review" / "run" / "02"
    literature_records.prepare_reference_delta(tmp_path, second_output)
    staged = _delta_dir(second_output)
    (staged / "papers" / "second.md").write_text(
        _card(
            "Second Paper",
            arxiv_id="1901.00002",
            found_in_run="02",
        ),
        encoding="utf-8",
        newline="",
    )
    (staged / "literature-summary.md").write_text(
        "# Literature Summary\n\nReplacement that must roll back.\n",
        encoding="utf-8",
        newline="",
    )
    seal = literature_records.seal_reference_delta(tmp_path, second_output)

    real_replace = os.replace
    live_index = (tmp_path / literature_records.REFERENCE_INDEX).resolve()
    failed = False

    def fail_installing_index(source: str | Path, destination: str | Path) -> None:
        nonlocal failed
        source_path = Path(source)
        destination_path = Path(destination).resolve()
        if (
            not failed
            and source_path.parent.name.startswith(
                literature_records._PREPARED_PREFIX
            )
            and source_path.name == literature_records.REFERENCE_INDEX.name
            and destination_path == live_index
        ):
            failed = True
            raise OSError("simulated reference-index replacement failure")
        real_replace(source, destination)

    monkeypatch.setattr(literature_records.os, "replace", fail_installing_index)

    with pytest.raises(
        OSError,
        match="simulated reference-index replacement failure",
    ):
        literature_records.promote_reference_delta(
            tmp_path,
            second_output,
            seal,
        )

    assert failed
    assert _canonical_bytes(tmp_path) == original
    references = tmp_path / literature_records.REFERENCE_DIR
    assert not any(
        child.name.startswith(
            (
                literature_records._PREPARED_PREFIX,
                literature_records._BACKUP_PREFIX,
            )
        )
        for child in references.iterdir()
    )


def test_current_reference_index_rejects_duplicate_json_fields(
    tmp_path: Path,
) -> None:
    output = tmp_path / "references" / "literature-review" / "run" / "01"
    _run_delta(
        tmp_path,
        output,
        cards={
            "paper.md": _card(
                "A Carefully Indexed Paper",
                arxiv_id="2601.00001",
            )
        },
        summary="# Literature Summary\n\nCurrent synthesis.\n",
    )
    index_path = tmp_path / literature_records.REFERENCE_INDEX
    original = index_path.read_text(encoding="utf-8")
    index_path.write_text(
        original.replace("{", '{\n  "schema_version": 2,', 1),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        literature_records.LiteratureRecordValidationError,
        match="duplicate field 'schema_version'",
    ):
        literature_records.load_current_literature_record(tmp_path)


def test_reference_delta_baseline_rejects_duplicate_json_fields(
    tmp_path: Path,
) -> None:
    output = tmp_path / "references" / "literature-review" / "run" / "01"
    literature_records.prepare_reference_delta(tmp_path, output)
    baseline_path = _delta_dir(output) / literature_records.BASELINE_FILENAME
    original = baseline_path.read_text(encoding="utf-8")
    baseline_path.write_text(
        original.replace("{", '{"schema_version":1,', 1),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        literature_records.LiteratureRecordValidationError,
        match="duplicate field 'schema_version'",
    ):
        literature_records.seal_reference_delta(
            tmp_path,
            output,
        )
