"""Focused tests for the Phase 02 method-menu catalog and transactions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from core import method_menu


def _write(project_dir: Path, filename: str, body: str) -> Path:
    menu_dir = project_dir / method_menu.METHOD_MENU_DIR
    menu_dir.mkdir(parents=True, exist_ok=True)
    path = menu_dir / filename
    path.write_text(body, encoding="utf-8", newline="")
    return path


def _entry(
    stable_id: str,
    *,
    version: str = "v1",
    label: str | None = None,
    status: str = "viable",
    number: int = 1,
    body: str = "A precise mathematical and scientific method description.",
    explicit_definition: bool = True,
) -> str:
    display = label or stable_id.replace("-", " ").title()
    scientific_body = (
        f"## Mathematical definition\n\n{body}"
        if explicit_definition
        else body
    )
    return (
        "---\n"
        f"stable_id: {stable_id}\n"
        f"version: {version}\n"
        f"label: {display}\n"
        f"status: {status}\n"
        f"number: {number}\n"
        "---\n\n"
        f"# {display}\n\n{scientific_body}\n"
    )


def _registry_rows(*rows: dict[str, Any]) -> str:
    numbers = [int(row["number"]) for row in rows]
    return yaml.safe_dump(
        {
            "next_number": max(numbers, default=0) + 1,
            "entries": list(rows),
        },
        sort_keys=False,
    )


def _registry_row(
    stable_id: str,
    *,
    number: int = 1,
    label: str | None = None,
    status: str = "viable",
) -> dict[str, Any]:
    return {
        "number": number,
        "stable_id": stable_id,
        "label": label or stable_id.replace("-", " ").title(),
        "status": status,
        "added_in_run": "run-1",
    }


def _literature_basis(
    *,
    source_run_id: str = "p1-run-1",
    generation: int = 1,
    synthesis: str = "a",
    collection: str = "b",
) -> dict[str, Any]:
    return {
        "schema_version": method_menu.LITERATURE_BASIS_SCHEMA_VERSION,
        "availability": "available",
        "source_run_id": source_run_id,
        "generation": generation,
        "synthesis_sha256": synthesis * 64,
        "collection_sha256": collection * 64,
    }


def _method_provenance(
    method_sha256: str,
    *,
    definition_run_id: str | None = "p2-definition-run",
    review_run_id: str = "p2-review-run",
    review_scope: str = "full_catalog",
    disposition: str = "changed",
    literature_basis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return method_menu.normalize_method_provenance({
        "schema_version": method_menu.METHOD_PROVENANCE_SCHEMA_VERSION,
        "method_sha256": method_sha256,
        "definition_source_run_id": definition_run_id,
        "review_source_run_id": review_run_id,
        "review_scientific_outcome": "Complete",
        "review_scope": review_scope,
        "disposition": disposition,
        "literature_basis": literature_basis or _literature_basis(),
    })


def _write_registry(project_dir: Path, *rows: dict[str, Any]) -> Path:
    menu_dir = project_dir / method_menu.METHOD_MENU_DIR
    menu_dir.mkdir(parents=True, exist_ok=True)
    path = menu_dir / method_menu.METHOD_REGISTRY_FILENAME
    path.write_text(_registry_rows(*rows), encoding="utf-8", newline="")
    return path


def _current_entry(project_dir: Path, stable_id: str) -> dict[str, Any]:
    return next(
        entry
        for entry in method_menu.load_method_menu(project_dir)["entries"]
        if entry["stable_id"] == stable_id
    )


def _retire(project_dir: Path, stable_id: str) -> dict[str, Any]:
    entry = _current_entry(project_dir, stable_id)
    return method_menu.retire_branch(
        project_dir,
        stable_id,
        expected_version=entry["version"],
        expected_sha256=entry["sha256"],
    )


def _staged_dir(project_dir: Path, output_root: Path) -> Path:
    return output_root / method_menu.STAGED_METHOD_MENU_DIRNAME


def test_missing_menu_folder_is_an_empty_menu(tmp_path: Path) -> None:
    assert method_menu.load_method_menu(tmp_path) == {
        "entries": [],
        "warnings": [],
    }


def test_entries_are_parsed_and_sorted_by_status(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "zebra-frontier.md",
        _entry("zebra-frontier", status="frontier", number=3),
    )
    _write(
        tmp_path,
        "alpha-retired.md",
        _entry("alpha-retired", status="retired", number=4),
    )
    _write(
        tmp_path,
        "main-method.md",
        _entry("main-method", status="recommended", number=1),
    )
    _write(
        tmp_path,
        "beta-viable.md",
        _entry("beta-viable", status="viable", number=2),
    )

    menu = method_menu.load_method_menu(tmp_path)

    assert [entry["stable_id"] for entry in menu["entries"]] == [
        "main-method",
        "beta-viable",
        "zebra-frontier",
        "alpha-retired",
    ]
    assert all(not entry["errors"] for entry in menu["entries"])
    assert menu["entries"][0]["number"] == 1
    assert menu["entries"][0]["body"].startswith("# Main Method")
    assert len(menu["entries"][0]["sha256"]) == 64


def test_number_and_body_are_required(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "missing-number.md",
        (
            "---\n"
            "stable_id: missing-number\n"
            "version: v1\n"
            "label: Missing Number\n"
            "status: viable\n"
            "---\n\nA body.\n"
        ),
    )
    _write(
        tmp_path,
        "empty-body.md",
        (
            "---\n"
            "stable_id: empty-body\n"
            "version: v1\n"
            "label: Empty Body\n"
            "status: viable\n"
            "number: 2\n"
            "---\n\n"
        ),
    )

    entries = {
        Path(entry["path"]).stem: entry
        for entry in method_menu.load_method_menu(tmp_path)["entries"]
    }

    assert any("positive integer" in error for error in entries["missing-number"]["errors"])
    assert any("body must be nonempty" in error for error in entries["empty-body"]["errors"])


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("stable_id", "bad id", "stable_id"),
        ("stable_id", "../escape", "stable_id"),
        ("version", "version with spaces", "version"),
        ("version", "Î²1", "version"),
    ],
)
def test_identity_fields_use_the_launch_identity_charset(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    text = _entry("valid-id", version="v2.1/finite-sample")
    text = text.replace(f"{field}: {'valid-id' if field == 'stable_id' else 'v2.1/finite-sample'}", f"{field}: {value}")
    _write(tmp_path, "valid-id.md", text)

    (entry,) = method_menu.load_method_menu(tmp_path)["entries"]

    assert any(message in error for error in entry["errors"])


def test_version_may_use_a_launch_identity_slash(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "robust-score.md",
        _entry("robust-score", version="v2.1/finite-sample"),
    )

    entry = _current_entry(tmp_path, "robust-score")

    assert entry["version"] == "v2.1/finite-sample"
    assert entry["errors"] == []


def test_prose_only_edit_preserves_scoped_definition_identity(
    tmp_path: Path,
) -> None:
    original_text = (
        _entry(
            "robust-score",
            body=(
                "Define the score as $S(\\theta)=\\sum_i \\psi_i(\\theta)$.\n\n"
                "### Computation\n\nSolve $S(\\theta)=0$ by safeguarded Newton steps."
            ),
        )
        + "\n## Scientific interpretation\n\nOriginal interpretation.\n"
    )
    _write(tmp_path, "robust-score.md", original_text)
    before = _current_entry(tmp_path, "robust-score")
    row = _registry_row("robust-score")
    row["provenance"] = _method_provenance(
        before["sha256"],
        definition_run_id="p2-definition-run",
    )
    _write_registry(tmp_path, row)
    output = tmp_path / "ideas" / "method-development" / "run" / "02"
    method_menu.stage_method_menu(tmp_path, output)
    staged_path = _staged_dir(tmp_path, output) / "robust-score.md"
    staged_path.write_text(
        original_text.replace(
            "Original interpretation.",
            "Revised interpretation with clearer scientific motivation.",
        ),
        encoding="utf-8",
        newline="",
    )

    provenance = method_menu.apply_run_provenance(
        tmp_path,
        output,
        run_id="p2-prose-revision",
        scientific_outcome="Complete",
        review_scope="focused_method",
        focused_method_id="robust-score",
        literature_basis=_literature_basis(),
    )
    staged = method_menu._load_menu_directory(
        tmp_path.resolve(),
        _staged_dir(tmp_path, output),
        require_registry=True,
    )["entries"][0]

    assert before["sha256"] != staged["sha256"]
    assert before["definition_sha256"] == staged["definition_sha256"]
    assert staged["definition_digest_basis"] == "explicit_section"
    assert provenance["robust-score"]["definition_source_run_id"] == (
        "p2-definition-run"
    )
    assert provenance["robust-score"]["disposition"] == "changed"


def test_empty_explicit_mathematical_definition_is_rejected(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "empty-definition.md",
        _entry("empty-definition", body=""),
    )

    entry = _current_entry(tmp_path, "empty-definition")

    assert "method mathematical definition is empty" in entry["errors"]


def test_same_version_cannot_change_mathematical_definition(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", version="v1"))
    _write_registry(tmp_path, _registry_row("one"))
    output = tmp_path / "ideas" / "method-development" / "run" / "02"
    method_menu.stage_method_menu(tmp_path, output)
    (_staged_dir(tmp_path, output) / "one.md").write_text(
        _entry(
            "one",
            version="v1",
            body="A different estimator and calculation rule.",
        ),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="without advancing the version",
    ):
        method_menu.apply_run_provenance(
            tmp_path,
            output,
            run_id="p2-definition-change",
            scientific_outcome="Complete",
            review_scope="focused_method",
            focused_method_id="one",
            literature_basis=_literature_basis(),
        )


def test_new_method_requires_explicit_mathematical_definition(
    tmp_path: Path,
) -> None:
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "new-method.md").write_text(
        _entry("new-method", explicit_definition=False),
        encoding="utf-8",
        newline="",
    )
    (staged / method_menu.METHOD_REGISTRY_FILENAME).write_text(
        _registry_rows(_registry_row("new-method")),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="new method 'new-method'.*explicit",
    ):
        method_menu.apply_run_provenance(
            tmp_path,
            output,
            run_id="p2-add-method",
            scientific_outcome="Complete",
            review_scope="full_catalog",
            literature_basis=_literature_basis(),
        )


def test_version_only_advance_preserves_definition_source_history(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", version="v1"))
    before = _current_entry(tmp_path, "one")
    row = _registry_row("one")
    row["provenance"] = _method_provenance(
        before["sha256"],
        definition_run_id="p2-original-definition",
    )
    _write_registry(tmp_path, row)
    output = tmp_path / "ideas" / "method-development" / "run" / "02"
    method_menu.stage_method_menu(tmp_path, output)
    (_staged_dir(tmp_path, output) / "one.md").write_text(
        _entry("one", version="v2"),
        encoding="utf-8",
        newline="",
    )

    provenance = method_menu.apply_run_provenance(
        tmp_path,
        output,
        run_id="p2-version-only",
        scientific_outcome="Complete",
        review_scope="focused_method",
        focused_method_id="one",
        literature_basis=_literature_basis(),
    )["one"]

    assert provenance["definition_source_run_id"] == "p2-original-definition"
    history = provenance["revision"]["history"]
    assert [item["version"] for item in history] == ["v1", "v2"]
    assert [item["change"] for item in history] == [
        "legacy_import",
        "version_advanced",
    ]
    assert history[0]["source_run_id"] == "p2-original-definition"
    assert history[1]["source_run_id"] == "p2-version-only"
    assert history[0]["definition_sha256"] == history[1]["definition_sha256"]


def test_run_provenance_rejects_stale_published_revision(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", version="v1"))
    before = _current_entry(tmp_path, "one")
    provenance = _method_provenance(
        before["sha256"],
        definition_run_id="p2-original-definition",
    )
    provenance["revision"] = {
        "schema_version": method_menu.METHOD_REVISION_SCHEMA_VERSION,
        "current_version": "v2",
        "definition_sha256": before["definition_sha256"],
        "history": [{
            "version": "v2",
            "definition_sha256": before["definition_sha256"],
            "source_run_id": "p2-original-definition",
            "change": "added",
        }],
    }
    row = _registry_row("one")
    row["provenance"] = provenance
    _write_registry(tmp_path, row)
    output = tmp_path / "ideas" / "method-development" / "run" / "02"
    method_menu.stage_method_menu(tmp_path, output)

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="published method revision provenance is stale",
    ):
        method_menu.apply_run_provenance(
            tmp_path,
            output,
            run_id="p2-review-stale",
            scientific_outcome="Complete",
            review_scope="focused_method",
            focused_method_id="one",
            literature_basis=_literature_basis(),
        )


def test_duplicate_frontmatter_keys_are_rejected(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "duplicate.md",
        _entry("duplicate").replace(
            "status: viable\n",
            "status: viable\nstatus: frontier\n",
        ),
    )

    (entry,) = method_menu.load_method_menu(tmp_path)["entries"]

    assert any("duplicate key 'status'" in error for error in entry["errors"])


def test_invalid_utf8_and_oversize_files_are_invalid_rows(
    tmp_path: Path,
) -> None:
    menu_dir = tmp_path / method_menu.METHOD_MENU_DIR
    menu_dir.mkdir(parents=True)
    (menu_dir / "invalid-utf8.md").write_bytes(b"\xff\xfe")
    (menu_dir / "too-large.md").write_bytes(
        b"x" * (method_menu._MAX_METHOD_FILE_BYTES + 1)
    )

    menu = method_menu.load_method_menu(tmp_path)
    entries = {Path(entry["path"]).stem: entry for entry in menu["entries"]}

    assert any("UTF-8" in error for error in entries["invalid-utf8"]["errors"])
    assert any("exceeds" in error for error in entries["too-large"]["errors"])


def test_filename_status_and_duplicate_numbers_are_validated(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "actual-name.md",
        _entry("different-name", status="unknown", number=7),
    )
    _write(tmp_path, "second.md", _entry("second", number=7))

    menu = method_menu.load_method_menu(tmp_path)

    first = next(entry for entry in menu["entries"] if Path(entry["path"]).stem == "actual-name")
    assert any("does not match the filename" in error for error in first["errors"])
    assert any("'status'" in error for error in first["errors"])
    assert all(
        any("duplicate method number" in error for error in entry["errors"])
        for entry in menu["entries"]
    )


def test_registry_is_strict_and_reconciled_when_present(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "one.md",
        _entry("one", label="Method One", status="recommended", number=1),
    )
    registry = _write_registry(
        tmp_path,
        _registry_row(
            "one",
            label="Different Label",
            status="viable",
            number=1,
        ),
    )

    menu = method_menu.load_method_menu(tmp_path)

    assert any("label" in warning for warning in menu["warnings"])
    assert any("status" in warning for warning in menu["warnings"])
    assert _current_entry(tmp_path, "one")["errors"]

    registry.write_text(
        (
            "next_number: 2\n"
            "next_number: 3\n"
            "entries: []\n"
        ),
        encoding="utf-8",
    )
    duplicate = method_menu.load_method_menu(tmp_path)
    assert any("duplicate key 'next_number'" in warning for warning in duplicate["warnings"])


def test_matching_registry_is_valid(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "one.md",
        _entry("one", label="Method One", status="recommended", number=1),
    )
    _write_registry(
        tmp_path,
        _registry_row(
            "one",
            label="Method One",
            status="recommended",
            number=1,
        ),
    )

    menu = method_menu.load_method_menu(tmp_path)

    assert menu["warnings"] == []
    assert menu["entries"][0]["errors"] == []


def test_selectable_entry_rejects_retired_invalid_and_unknown(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "active.md", _entry("active", number=1))
    _write(tmp_path, "retired.md", _entry("retired", status="retired", number=2))
    _write(tmp_path, "broken.md", "not frontmatter")

    entry, error = method_menu.find_selectable_entry(tmp_path, "active")
    assert entry is not None and error is None

    entry, error = method_menu.find_selectable_entry(tmp_path, "retired")
    assert entry is None and error is not None and "retired" in error

    entry, error = method_menu.find_selectable_entry(tmp_path, "broken")
    assert entry is None and error is not None and "invalid" in error

    entry, error = method_menu.find_selectable_entry(tmp_path, "ghost")
    assert entry is None and error is not None and "no method menu file" in error


def test_linked_method_menu_root_is_rejected_for_reads_and_writes(
    tmp_path: Path,
) -> None:
    external = tmp_path.parent / f"{tmp_path.name}-external"
    external.mkdir()
    (tmp_path / "ideas").mkdir()
    try:
        (tmp_path / method_menu.METHOD_MENU_DIR).symlink_to(
            external,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("directory symlinks are unavailable on this platform")

    menu = method_menu.load_method_menu(tmp_path)
    assert menu["entries"] == []
    assert any("link or junction" in warning for warning in menu["warnings"])

    output = tmp_path / "runs" / "02" / "run" / "01"
    with pytest.raises(method_menu.MethodMenuValidationError, match="link or junction"):
        method_menu.stage_method_menu(tmp_path, output)


def test_output_root_outside_project_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside" / "run"

    with pytest.raises(method_menu.MethodMenuValidationError, match="outside"):
        method_menu.stage_method_menu(tmp_path, outside)


def test_stage_seeds_current_menu_and_creates_missing_registry(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", number=4))
    output = tmp_path / "ideas" / "method-development" / "run" / "01"

    stage = method_menu.stage_method_menu(tmp_path, output)

    staged = _staged_dir(tmp_path, output)
    assert stage["kind"] == "method_menu_stage"
    assert stage["path"] == staged.relative_to(tmp_path).as_posix()
    assert (staged / "one.md").read_text(encoding="utf-8") == (
        tmp_path / method_menu.METHOD_MENU_DIR / "one.md"
    ).read_text(encoding="utf-8")
    registry = yaml.safe_load(
        (staged / method_menu.METHOD_REGISTRY_FILENAME).read_text(encoding="utf-8")
    )
    assert registry["next_number"] == 5
    assert registry["entries"][0]["stable_id"] == "one"
    assert stage["warnings"] == []


def test_fresh_stage_preserves_the_reviewed_empty_source_digest(
    tmp_path: Path,
) -> None:
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    expected = method_menu.catalog_version(tmp_path)

    stage = method_menu.stage_method_menu(
        tmp_path,
        output,
        expected_catalog_sha256=expected,
    )

    assert stage["source_files"] == []
    assert stage["source_catalog_sha256"] == expected
    assert [record["path"] for record in stage["staged_files"]] == [
        method_menu.METHOD_REGISTRY_FILENAME
    ]
    assert stage["staged_catalog_sha256"] != expected


def test_stage_rejects_a_stale_reviewed_source_digest(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one"))
    output = tmp_path / "ideas" / "method-development" / "run" / "01"

    with pytest.raises(
        method_menu.StaleMethodMenu,
        match="changed after it was reviewed",
    ):
        method_menu.stage_method_menu(
            tmp_path,
            output,
            expected_catalog_sha256="0" * 64,
        )

    assert not _staged_dir(tmp_path, output).exists()


def test_stage_rejects_a_source_catalog_change_during_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write(tmp_path, "one.md", _entry("one"))
    expected = method_menu.catalog_version(tmp_path)
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    original_copy = method_menu._copy_catalog

    def copy_then_mutate(source_dir: Path, destination: Path) -> None:
        original_copy(source_dir, destination)
        source.write_text(
            _entry(
                "one",
                body="A concurrent change during catalog staging.",
            ),
            encoding="utf-8",
            newline="",
        )

    monkeypatch.setattr(method_menu, "_copy_catalog", copy_then_mutate)

    with pytest.raises(
        method_menu.StaleMethodMenu,
        match="changed while it was staged",
    ):
        method_menu.stage_method_menu(
            tmp_path,
            output,
            expected_catalog_sha256=expected,
        )

    assert not _staged_dir(tmp_path, output).exists()


def test_seal_rejects_a_published_catalog_change_after_staging(
    tmp_path: Path,
) -> None:
    published = _write(tmp_path, "one.md", _entry("one"))
    expected = method_menu.catalog_version(tmp_path)
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(
        tmp_path,
        output,
        expected_catalog_sha256=expected,
    )
    published.write_text(
        _entry(
            "one",
            body="A concurrent change before the run was submitted.",
        ),
        encoding="utf-8",
        newline="",
    )

    with pytest.raises(
        method_menu.StaleMethodMenu,
        match="changed after this run was frozen",
    ):
        method_menu.seal_staged_menu(
            tmp_path,
            output,
            expected_published_catalog_sha256=expected,
        )


def test_fresh_stage_has_an_empty_registry_and_can_be_sealed(
    tmp_path: Path,
) -> None:
    output = tmp_path / "ideas" / "method-development" / "run" / "01"

    method_menu.stage_method_menu(tmp_path, output)
    seal = method_menu.seal_staged_menu(tmp_path, output)

    assert seal["kind"] == "method_menu"
    assert seal["entries"] == []
    assert [record["path"] for record in seal["files"]] == [
        method_menu.METHOD_REGISTRY_FILENAME
    ]
    assert len(seal["catalog_sha256"]) == 64


def test_seal_rejects_invalid_or_unexpected_staged_content(
    tmp_path: Path,
) -> None:
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "notes.txt").write_text("unsupported", encoding="utf-8")

    with pytest.raises(method_menu.MethodMenuValidationError, match="unsupported"):
        method_menu.seal_staged_menu(tmp_path, output)

    (staged / "notes.txt").unlink()
    (staged / "bad.md").write_text("not frontmatter", encoding="utf-8")
    with pytest.raises(method_menu.MethodMenuValidationError, match="invalid"):
        method_menu.seal_staged_menu(tmp_path, output)


def test_verify_seal_detects_post_submission_changes(tmp_path: Path) -> None:
    _write(tmp_path, "one.md", _entry("one"))
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    seal = method_menu.seal_staged_menu(tmp_path, output)
    staged_method = _staged_dir(tmp_path, output) / "one.md"
    staged_method.write_text(
        staged_method.read_text(encoding="utf-8") + "\nChanged.\n",
        encoding="utf-8",
    )

    with pytest.raises(method_menu.StaleMethodMenu, match="changed"):
        method_menu.verify_staged_menu_seal(tmp_path, output, seal)


def test_promotion_reports_changes_and_rollback_restores_exact_catalog(
    tmp_path: Path,
) -> None:
    published_method = _write(
        tmp_path,
        "one.md",
        _entry("one", version="v1", status="viable", number=1),
    )
    registry = _write_registry(
        tmp_path,
        _registry_row("one", status="viable", number=1),
    )
    original_method = published_method.read_bytes()
    original_registry = registry.read_bytes()
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", status="recommended", number=1),
        encoding="utf-8",
    )
    (staged / "two.md").write_text(
        _entry("two", version="v1", status="frontier", number=2),
        encoding="utf-8",
    )
    (staged / method_menu.METHOD_REGISTRY_FILENAME).write_text(
        _registry_rows(
            _registry_row("one", status="recommended", number=1),
            _registry_row("two", status="frontier", number=2),
        ),
        encoding="utf-8",
    )
    seal = method_menu.seal_staged_menu(tmp_path, output)

    promotion = method_menu.promote_staged_menu(tmp_path, output, seal)

    assert promotion["changed_stable_ids"] == ["one", "two"]
    assert [change["change"] for change in promotion["changes"]] == [
        "updated",
        "added",
    ]
    assert _current_entry(tmp_path, "one")["version"] == "v2"
    assert _current_entry(tmp_path, "two")["status"] == "frontier"
    assert promotion["backup_path"]

    method_menu.rollback_method_menu_promotion(tmp_path, promotion)

    menu_dir = tmp_path / method_menu.METHOD_MENU_DIR
    assert (menu_dir / "one.md").read_bytes() == original_method
    assert (menu_dir / method_menu.METHOD_REGISTRY_FILENAME).read_bytes() == original_registry
    assert not (menu_dir / "two.md").exists()


@pytest.mark.parametrize(
    ("change_kind", "expected_invalidated"),
    [
        ("prose", []),
        ("status", []),
        ("version", ["one"]),
        ("definition", ["one"]),
        ("retirement", ["one"]),
    ],
)
def test_promotion_invalidates_only_scientific_method_identity_changes(
    tmp_path: Path,
    change_kind: str,
    expected_invalidated: list[str],
) -> None:
    original = (
        _entry("one", version="v1", status="viable", body="Estimator A.")
        + "\n## Scientific interpretation\n\nOriginal interpretation.\n"
    )
    _write(tmp_path, "one.md", original)
    _write_registry(tmp_path, _registry_row("one", status="viable"))
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)

    staged_text = original
    staged_status = "viable"
    if change_kind == "prose":
        staged_text = original.replace(
            "Original interpretation.", "Revised interpretation."
        )
    elif change_kind == "status":
        staged_status = "recommended"
        staged_text = _entry(
            "one",
            version="v1",
            status=staged_status,
            body="Estimator A.",
        ) + "\n## Scientific interpretation\n\nOriginal interpretation.\n"
    elif change_kind == "version":
        staged_text = _entry(
            "one", version="v2", status="viable", body="Estimator A."
        ) + "\n## Scientific interpretation\n\nOriginal interpretation.\n"
    elif change_kind == "definition":
        staged_text = _entry(
            "one", version="v2", status="viable", body="Estimator B."
        ) + "\n## Scientific interpretation\n\nOriginal interpretation.\n"
    elif change_kind == "retirement":
        staged_status = "retired"
        staged_text = _entry(
            "one",
            version="v1",
            status=staged_status,
            body="Estimator A.",
        ) + "\n## Scientific interpretation\n\nOriginal interpretation.\n"
    else:
        raise AssertionError(f"unsupported change kind {change_kind!r}")
    (staged / "one.md").write_text(
        staged_text,
        encoding="utf-8",
        newline="",
    )
    if staged_status != "viable":
        registry_path = staged / method_menu.METHOD_REGISTRY_FILENAME
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["entries"][0]["status"] = staged_status
        registry_path.write_text(
            yaml.safe_dump(registry, sort_keys=False),
            encoding="utf-8",
            newline="",
        )

    seal = method_menu.seal_staged_menu(tmp_path, output)
    promotion = method_menu.promote_staged_menu(tmp_path, output, seal)

    assert promotion["changed_stable_ids"] == ["one"]
    assert promotion["downstream_invalidated_stable_ids"] == (
        expected_invalidated
    )
    method_menu.commit_method_menu_promotion(tmp_path, promotion)


def test_commit_removes_backup_and_keeps_published_menu(tmp_path: Path) -> None:
    _write(tmp_path, "one.md", _entry("one", number=1))
    _write_registry(tmp_path, _registry_row("one", number=1))
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", number=1),
        encoding="utf-8",
    )
    seal = method_menu.seal_staged_menu(tmp_path, output)
    promotion = method_menu.promote_staged_menu(tmp_path, output, seal)
    backup = tmp_path / str(promotion["backup_path"])

    method_menu.commit_method_menu_promotion(tmp_path, promotion)

    assert not backup.exists()
    assert _current_entry(tmp_path, "one")["version"] == "v2"


def test_focused_promotion_changes_only_the_selected_method(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", version="v1", number=1))
    original_two = _write(
        tmp_path, "two.md", _entry("two", version="v1", number=2)
    ).read_bytes()
    _write_registry(
        tmp_path,
        _registry_row("one", number=1),
        _registry_row("two", number=2),
    )
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", number=1),
        encoding="utf-8",
    )
    seal = method_menu.seal_staged_menu(tmp_path, output)

    promotion = method_menu.promote_staged_menu(
        tmp_path,
        output,
        seal,
        focused_method_id="one",
    )

    assert promotion["changed_stable_ids"] == ["one"]
    assert (tmp_path / method_menu.METHOD_MENU_DIR / "two.md").read_bytes() == (
        original_two
    )
    method_menu.commit_method_menu_promotion(tmp_path, promotion)


def test_focused_promotion_rejects_non_selected_changes(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", number=1))
    original_two = _write(
        tmp_path, "two.md", _entry("two", version="v1", number=2)
    ).read_bytes()
    _write_registry(
        tmp_path,
        _registry_row("one", number=1),
        _registry_row("two", number=2),
    )
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", number=1),
        encoding="utf-8",
    )
    (staged / "two.md").write_text(
        _entry("two", version="v2", number=2),
        encoding="utf-8",
    )
    seal = method_menu.seal_staged_menu(tmp_path, output)

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="non-selected",
    ):
        method_menu.promote_staged_menu(
            tmp_path,
            output,
            seal,
            focused_method_id="one",
        )

    assert (tmp_path / method_menu.METHOD_MENU_DIR / "two.md").read_bytes() == (
        original_two
    )


def test_focused_promotion_rejects_non_selected_registry_metadata_change(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", number=1))
    _write(tmp_path, "two.md", _entry("two", number=2))
    _write_registry(
        tmp_path,
        _registry_row("one", number=1),
        _registry_row("two", number=2),
    )
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", number=1),
        encoding="utf-8",
    )
    changed_two = _registry_row("two", number=2)
    changed_two["added_in_run"] = "run-2"
    (staged / method_menu.METHOD_REGISTRY_FILENAME).write_text(
        _registry_rows(
            _registry_row("one", number=1),
            changed_two,
        ),
        encoding="utf-8",
    )
    seal = method_menu.seal_staged_menu(tmp_path, output)

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="non-selected registry row.*'two'",
    ):
        method_menu.promote_staged_menu(
            tmp_path,
            output,
            seal,
            focused_method_id="one",
        )


def test_focused_promotion_rejects_registry_next_number_change(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", number=1))
    _write(tmp_path, "two.md", _entry("two", number=2))
    rows = (
        _registry_row("one", number=1),
        _registry_row("two", number=2),
    )
    _write_registry(tmp_path, *rows)
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", number=1),
        encoding="utf-8",
    )
    (staged / method_menu.METHOD_REGISTRY_FILENAME).write_text(
        yaml.safe_dump(
            {
                "next_number": 10,
                "entries": list(rows),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    seal = method_menu.seal_staged_menu(tmp_path, output)

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="cannot change the registry next_number",
    ):
        method_menu.promote_staged_menu(
            tmp_path,
            output,
            seal,
            focused_method_id="one",
        )


def test_full_run_provenance_reviews_all_methods_without_redefining_them(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", number=1))
    _write(tmp_path, "two.md", _entry("two", number=2))
    entries = {
        entry["stable_id"]: entry
        for entry in method_menu.load_method_menu(tmp_path)["entries"]
    }
    rows = [
        _registry_row("one", number=1),
        _registry_row("two", number=2),
    ]
    rows[0]["provenance"] = _method_provenance(
        entries["one"]["sha256"],
        definition_run_id="one-definition-run",
    )
    rows[1]["provenance"] = _method_provenance(
        entries["two"]["sha256"],
        definition_run_id="two-definition-run",
    )
    _write_registry(tmp_path, *rows)
    output = tmp_path / "ideas" / "method-development" / "run" / "02"
    method_menu.stage_method_menu(tmp_path, output)
    reviewed_basis = _literature_basis(
        source_run_id="p1-run-2",
        generation=2,
        synthesis="c",
        collection="d",
    )

    provenance = method_menu.apply_run_provenance(
        tmp_path,
        output,
        run_id="p2-full-review",
        scientific_outcome="Complete",
        review_scope="full_catalog",
        literature_basis=reviewed_basis,
    )

    assert set(provenance) == {"one", "two"}
    assert provenance["one"]["definition_source_run_id"] == (
        "one-definition-run"
    )
    assert provenance["two"]["definition_source_run_id"] == (
        "two-definition-run"
    )
    for value in provenance.values():
        assert value["review_source_run_id"] == "p2-full-review"
        assert value["review_scope"] == "full_catalog"
        assert value["disposition"] == "reviewed_no_change"
        assert value["literature_basis"] == reviewed_basis


def test_focused_no_change_provenance_updates_only_the_selected_method(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", number=1))
    _write(tmp_path, "two.md", _entry("two", number=2))
    entries = {
        entry["stable_id"]: entry
        for entry in method_menu.load_method_menu(tmp_path)["entries"]
    }
    one_prior = _method_provenance(
        entries["one"]["sha256"],
        definition_run_id="one-definition-run",
    )
    two_prior = _method_provenance(
        entries["two"]["sha256"],
        definition_run_id="two-definition-run",
    )
    rows = [
        _registry_row("one", number=1),
        _registry_row("two", number=2),
    ]
    rows[0]["provenance"] = one_prior
    rows[1]["provenance"] = two_prior
    _write_registry(tmp_path, *rows)
    output = tmp_path / "ideas" / "method-development" / "run" / "02"
    method_menu.stage_method_menu(tmp_path, output)
    staged_registry_path = (
        _staged_dir(tmp_path, output)
        / method_menu.METHOD_REGISTRY_FILENAME
    )
    staged_registry = yaml.safe_load(
        staged_registry_path.read_text(encoding="utf-8")
    )
    staged_registry["entries"][1]["provenance"]["review_source_run_id"] = (
        "agent-authored-out-of-scope-value"
    )
    staged_registry_path.write_text(
        yaml.safe_dump(staged_registry, sort_keys=False),
        encoding="utf-8",
        newline="",
    )
    reviewed_basis = _literature_basis(
        source_run_id="p1-run-2",
        generation=2,
        synthesis="c",
        collection="d",
    )

    provenance = method_menu.apply_run_provenance(
        tmp_path,
        output,
        run_id="p2-focused-review",
        scientific_outcome="Partial",
        review_scope="focused_method",
        focused_method_id="one",
        literature_basis=reviewed_basis,
    )

    assert set(provenance) == {"one"}
    selected = provenance["one"]
    assert selected["definition_source_run_id"] == "one-definition-run"
    assert selected["review_source_run_id"] == "p2-focused-review"
    assert selected["review_scientific_outcome"] == "Partial"
    assert selected["review_scope"] == "focused_method"
    assert selected["disposition"] == "reviewed_no_change"
    assert selected["literature_basis"] == reviewed_basis
    staged_rows = {
        row["stable_id"]: row
        for row in yaml.safe_load(
            staged_registry_path.read_text(encoding="utf-8")
        )["entries"]
    }
    assert staged_rows["two"]["provenance"] == two_prior


def test_focused_changed_definition_gets_a_new_definition_source_run(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one", number=1))
    _write(tmp_path, "two.md", _entry("two", number=2))
    entries = {
        entry["stable_id"]: entry
        for entry in method_menu.load_method_menu(tmp_path)["entries"]
    }
    two_prior = _method_provenance(
        entries["two"]["sha256"],
        definition_run_id="two-definition-run",
    )
    rows = [
        _registry_row("one", number=1),
        _registry_row("two", number=2),
    ]
    rows[0]["provenance"] = _method_provenance(
        entries["one"]["sha256"],
        definition_run_id="one-definition-run",
    )
    rows[1]["provenance"] = two_prior
    _write_registry(tmp_path, *rows)
    output = tmp_path / "ideas" / "method-development" / "run" / "02"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry(
            "one",
            version="v2",
            number=1,
            body="A revised mathematical and scientific method definition.",
        ),
        encoding="utf-8",
        newline="",
    )

    provenance = method_menu.apply_run_provenance(
        tmp_path,
        output,
        run_id="p2-definition-update",
        scientific_outcome="Complete",
        review_scope="focused_method",
        focused_method_id="one",
        literature_basis=_literature_basis(),
    )

    selected = provenance["one"]
    assert selected["definition_source_run_id"] == "p2-definition-update"
    assert selected["review_source_run_id"] == "p2-definition-update"
    assert selected["disposition"] == "changed"
    staged_menu = method_menu._load_menu_directory(
        tmp_path.resolve(),
        staged,
        require_registry=True,
    )
    staged_entries = {
        entry["stable_id"]: entry for entry in staged_menu["entries"]
    }
    assert selected["method_sha256"] == staged_entries["one"]["sha256"]
    staged_rows = {
        row["stable_id"]: row
        for row in staged_menu["registry"]["entries"]
    }
    assert staged_rows["two"]["provenance"] == two_prior


def test_legacy_registry_without_provenance_remains_readable(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "one.md", _entry("one"))
    _write_registry(tmp_path, _registry_row("one"))

    entry = _current_entry(tmp_path, "one")

    assert entry["provenance"] is None
    assert entry["provenance_error"] == ""


def test_promotion_failure_restores_previous_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = _write(tmp_path, "one.md", _entry("one", number=1)).read_bytes()
    _write_registry(tmp_path, _registry_row("one", number=1))
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", number=1),
        encoding="utf-8",
    )
    seal = method_menu.seal_staged_menu(tmp_path, output)
    published = (tmp_path / method_menu.METHOD_MENU_DIR).resolve()
    real_seal = method_menu._seal_directory

    def fail_post_write(
        root: Path,
        menu_dir: Path,
        *,
        require_registry: bool,
    ) -> dict[str, Any]:
        if menu_dir.resolve() == published:
            raise method_menu.MethodMenuValidationError("simulated post-write failure")
        return real_seal(root, menu_dir, require_registry=require_registry)

    monkeypatch.setattr(method_menu, "_seal_directory", fail_post_write)

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="simulated post-write failure",
    ):
        method_menu.promote_staged_menu(tmp_path, output, seal)

    assert (
        tmp_path / method_menu.METHOD_MENU_DIR / "one.md"
    ).read_bytes() == original


def test_retire_branch_updates_method_and_registry(tmp_path: Path) -> None:
    method_path = _write(
        tmp_path,
        "numbered-method.md",
        _entry(
            "numbered-method",
            status="recommended",
            number=4,
            body="Original scientific rationale.",
        ),
    )
    registry_path = _write_registry(
        tmp_path,
        _registry_row(
            "numbered-method",
            status="recommended",
            number=4,
        ),
    )

    retired = _retire(tmp_path, "numbered-method")

    assert retired["status"] == "retired"
    assert "Original scientific rationale." in method_path.read_text(encoding="utf-8")
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    row = registry["entries"][0]
    assert row["number"] == 4
    assert row["status"] == "retired"
    assert row["retired_by"] == "user"
    assert row["retired_at"].endswith("+00:00")


def test_retire_branch_requires_current_version_and_hash(tmp_path: Path) -> None:
    path = _write(tmp_path, "one.md", _entry("one"))
    original = path.read_bytes()
    current = _current_entry(tmp_path, "one")

    with pytest.raises(method_menu.StaleMethodMenu, match="version changed"):
        method_menu.retire_branch(
            tmp_path,
            "one",
            expected_version="v0",
            expected_sha256=current["sha256"],
        )
    with pytest.raises(method_menu.StaleMethodMenu, match="file changed"):
        method_menu.retire_branch(
            tmp_path,
            "one",
            expected_version=current["version"],
            expected_sha256="0" * 64,
        )

    assert path.read_bytes() == original


def test_retire_branch_rejects_missing_retired_and_invalid_catalog(
    tmp_path: Path,
) -> None:
    with pytest.raises(method_menu.BranchNotFound):
        method_menu.retire_branch(
            tmp_path,
            "ghost",
            expected_version="v1",
            expected_sha256="0" * 64,
        )

    _write(tmp_path, "retired.md", _entry("retired", status="retired"))
    retired = _current_entry(tmp_path, "retired")
    with pytest.raises(method_menu.BranchAlreadyRetired):
        method_menu.retire_branch(
            tmp_path,
            "retired",
            expected_version=retired["version"],
            expected_sha256=retired["sha256"],
        )

    duplicate_path = _write(
        tmp_path,
        "duplicate.md",
        _entry("duplicate", number=2).replace(
            "status: viable\n",
            "status: viable\nstatus: frontier\n",
        ),
    )
    duplicate_sha = hashlib.sha256(duplicate_path.read_bytes()).hexdigest()
    with pytest.raises(method_menu.MethodMenuValidationError, match="duplicate"):
        method_menu.retire_branch(
            tmp_path,
            "duplicate",
            expected_version="v1",
            expected_sha256=duplicate_sha,
        )


def test_retirement_rolls_back_on_post_write_verification_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write(tmp_path, "one.md", _entry("one"))
    original = path.read_bytes()
    current = _current_entry(tmp_path, "one")
    published = (tmp_path / method_menu.METHOD_MENU_DIR).resolve()
    real_load = method_menu._load_menu_directory
    published_calls = 0

    def fail_second_published_load(
        root: Path,
        menu_dir: Path,
        *,
        require_registry: bool,
    ) -> dict[str, Any]:
        nonlocal published_calls
        if menu_dir.resolve() == published:
            published_calls += 1
            if published_calls == 2:
                raise method_menu.MethodMenuValidationError(
                    "simulated retirement verification failure"
                )
        return real_load(root, menu_dir, require_registry=require_registry)

    monkeypatch.setattr(method_menu, "_load_menu_directory", fail_second_published_load)

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="simulated retirement verification failure",
    ):
        method_menu.retire_branch(
            tmp_path,
            "one",
            expected_version=current["version"],
            expected_sha256=current["sha256"],
        )

    assert path.read_bytes() == original


def test_seal_rejects_removing_a_valid_published_method(tmp_path: Path) -> None:
    method_path = _write(tmp_path, "one.md", _entry("one", number=1))
    registry_path = _write_registry(tmp_path, _registry_row("one", number=1))
    original_method = method_path.read_bytes()
    original_registry = registry_path.read_bytes()
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").unlink()
    (staged / method_menu.METHOD_REGISTRY_FILENAME).write_text(
        yaml.safe_dump({"next_number": 2, "entries": []}, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="retain the entry.*retired",
    ):
        method_menu.seal_staged_menu(tmp_path, output)

    assert method_path.read_bytes() == original_method
    assert registry_path.read_bytes() == original_registry


def test_seal_rejects_renumbering_a_valid_published_method(tmp_path: Path) -> None:
    method_path = _write(tmp_path, "one.md", _entry("one", number=1))
    registry_path = _write_registry(tmp_path, _registry_row("one", number=1))
    original_method = method_path.read_bytes()
    original_registry = registry_path.read_bytes()
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", status="recommended", number=2),
        encoding="utf-8",
    )
    (staged / method_menu.METHOD_REGISTRY_FILENAME).write_text(
        _registry_rows(_registry_row("one", status="recommended", number=2)),
        encoding="utf-8",
    )

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="keep method number 1",
    ):
        method_menu.seal_staged_menu(tmp_path, output)

    assert method_path.read_bytes() == original_method
    assert registry_path.read_bytes() == original_registry


def test_seal_rejects_reactivating_a_retired_published_method(
    tmp_path: Path,
) -> None:
    method_path = _write(
        tmp_path,
        "one.md",
        _entry("one", status="retired", number=1),
    )
    registry_path = _write_registry(
        tmp_path,
        _registry_row("one", status="retired", number=1),
    )
    original_method = method_path.read_bytes()
    original_registry = registry_path.read_bytes()
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", status="viable", number=1),
        encoding="utf-8",
    )
    (staged / method_menu.METHOD_REGISTRY_FILENAME).write_text(
        _registry_rows(_registry_row("one", status="viable", number=1)),
        encoding="utf-8",
    )

    with pytest.raises(
        method_menu.MethodMenuValidationError,
        match="reactivates retired method 'one'",
    ):
        method_menu.seal_staged_menu(tmp_path, output)

    assert method_path.read_bytes() == original_method
    assert registry_path.read_bytes() == original_registry


def test_invalid_legacy_entry_can_be_repaired_in_staging(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "legacy.md",
        (
            "---\n"
            "stable_id: legacy\n"
            "version: v1\n"
            "label: Legacy Method\n"
            "status: viable\n"
            "---\n\n"
            "A legacy entry with no stable number.\n"
        ),
    )
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "legacy.md").write_text(
        _entry("legacy", label="Legacy Method", number=7),
        encoding="utf-8",
    )
    (staged / method_menu.METHOD_REGISTRY_FILENAME).write_text(
        _registry_rows(
            _registry_row("legacy", label="Legacy Method", number=7)
        ),
        encoding="utf-8",
    )

    seal = method_menu.seal_staged_menu(tmp_path, output)

    assert seal["entries"][0]["stable_id"] == "legacy"
    assert seal["entries"][0]["number"] == 7


def test_promotion_rejects_live_catalog_change_after_seal_without_overwrite(
    tmp_path: Path,
) -> None:
    published_method = _write(
        tmp_path,
        "one.md",
        _entry("one", version="v1", number=1),
    )
    registry_path = _write_registry(tmp_path, _registry_row("one", number=1))
    output = tmp_path / "ideas" / "method-development" / "run" / "01"
    method_menu.stage_method_menu(tmp_path, output)
    staged = _staged_dir(tmp_path, output)
    (staged / "one.md").write_text(
        _entry("one", version="v2", number=1),
        encoding="utf-8",
    )
    seal = method_menu.seal_staged_menu(tmp_path, output)

    published_method.write_text(
        _entry(
            "one",
            version="v1",
            number=1,
            body="A concurrent scientific clarification.",
        ),
        encoding="utf-8",
    )
    concurrent_method = published_method.read_bytes()
    concurrent_registry = registry_path.read_bytes()

    with pytest.raises(
        method_menu.StaleMethodMenu,
        match="changed after the staged menu was sealed",
    ):
        method_menu.promote_staged_menu(tmp_path, output, seal)

    assert published_method.read_bytes() == concurrent_method
    assert registry_path.read_bytes() == concurrent_registry
    assert _current_entry(tmp_path, "one")["version"] == "v1"
