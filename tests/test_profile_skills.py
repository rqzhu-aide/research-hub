from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from scripts import profile_skills as skills


REVISION = "1a32b75dc671266b515816b32fca7244c9fc42be"
REPOSITORY = "https://github.com/rqzhu-aide/stat-paper-skills"


def _make_app(
    tmp_path: Path,
    definitions: dict[str, tuple[list[str], dict[str, bytes]]] | None = None,
) -> tuple[Path, skills.SkillManifest]:
    app_root = tmp_path / "app"
    bundle_root = app_root / "bundled_skills"
    bundle_root.mkdir(parents=True)
    definitions = definitions or {
        "stat-paper-writing": (
            ["research_lead", "theorist", "data_scientist"],
            {
                "SKILL.md": b"# Writing\n",
                "references/guide.md": b"Write direct scientific statements.\n",
            },
        ),
        "stat-paper-reviewer": (
            ["paper_reviewer"],
            {
                "SKILL.md": b"# Reviewer\n",
                "scripts/check.py": b"print('check')\n",
            },
        ),
    }
    manifest_skills: dict[str, object] = {}
    for name, (roles, files) in definitions.items():
        directory = bundle_root / name
        directory.mkdir()
        for relative, payload in files.items():
            target = directory / Path(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        manifest_skills[name] = {
            "directory": name,
            "digest": skills.bundle_digest(directory),
            "roles": roles,
        }
    manifest_path = bundle_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": {"repository": REPOSITORY, "revision": REVISION},
                "skills": manifest_skills,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return app_root, skills.load_manifest(app_root=app_root)


def _make_profile(hermes_root: Path, name: str = "lead") -> Path:
    profile = hermes_root / "profiles" / name
    profile.mkdir(parents=True)
    (profile / "config.yaml").write_text("model: test\n", encoding="utf-8")
    return profile


def test_resolve_hermes_root_precedence_and_profile_home_derivation(tmp_path: Path) -> None:
    explicit = tmp_path / "explicit"
    configured = tmp_path / "base" / "profiles" / "lead"
    assert skills.resolve_hermes_root(
        environ={
            "RESEARCH_HUB_HERMES_ROOT": str(explicit),
            "HERMES_HOME": str(configured),
        }
    ) == explicit
    assert skills.resolve_hermes_root(environ={"HERMES_HOME": str(configured)}) == (
        tmp_path / "base"
    )
    assert skills.resolve_hermes_root(
        environ={"HERMES_HOME": str(tmp_path / "standalone")}
    ) == (tmp_path / "standalone")


def test_resolve_hermes_root_windows_and_posix_defaults(tmp_path: Path) -> None:
    local = tmp_path / "local"
    assert skills.resolve_hermes_root(
        environ={"LOCALAPPDATA": str(local)}, platform_name="nt"
    ) == local / "hermes"
    assert skills.resolve_hermes_root(
        environ={}, home=tmp_path / "home", platform_name="windows"
    ) == tmp_path / "home" / "AppData" / "Local" / "hermes"
    assert skills.resolve_hermes_root(
        environ={
            "LOCALAPPDATA": str(local),
            "HERMES_HOME": str(local / "hermes" / "nested"),
        },
        platform_name="windows",
    ) == local / "hermes"
    assert skills.resolve_hermes_root(
        environ={}, home=tmp_path / "home", platform_name="posix"
    ) == tmp_path / "home" / ".hermes"


def test_profile_home_supports_default_and_canonical_named_profiles(tmp_path: Path) -> None:
    root = tmp_path / ".hermes"
    assert skills.profile_home(hermes_root=root) == root
    assert skills.profile_home(None, hermes_root=root) == root
    assert skills.profile_home("default", hermes_root=root) == root
    assert skills.profile_home("paper_reviewer", hermes_root=root) == (
        root / "profiles" / "paper_reviewer"
    )
    assert skills.validate_profile_name("default") == "default"
    for invalid in (
        "Lead",
        "lead.profile",
        "-lead",
        "lead/profile",
        "",
        "a" * 65,
        "hermes",
        "test",
        "tmp",
        "root",
        "sudo",
    ):
        with pytest.raises(skills.ProfileNameError):
            skills.validate_profile_name(invalid)


def test_bundle_digest_uses_sorted_posix_paths_and_nul_delimiters(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "z").mkdir(parents=True)
    (bundle / "z" / "b.txt").write_bytes(b"second")
    (bundle / "a.txt").write_bytes(b"first")
    expected = hashlib.sha256(
        b"a.txt\x00first\x00z/b.txt\x00second\x00"
    ).hexdigest()
    assert skills.bundle_digest(bundle) == expected


def test_manifest_is_strict_and_verifies_bundle_digest(tmp_path: Path) -> None:
    app_root, loaded = _make_app(tmp_path)
    assert loaded.source_revision == REVISION
    assert set(loaded.skills) == {"stat-paper-writing", "stat-paper-reviewer"}

    manifest_path = app_root / "bundled_skills" / "manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["unexpected"] = True
    manifest_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(skills.ManifestValidationError, match="exactly"):
        skills.load_manifest(app_root=app_root)

    document.pop("unexpected")
    document["skills"]["stat-paper-writing"]["digest"] = "0" * 64
    manifest_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(skills.ManifestValidationError, match="does not match"):
        skills.load_manifest(app_root=app_root)


def test_manifest_rejects_duplicate_json_fields(tmp_path: Path) -> None:
    app_root, _loaded = _make_app(tmp_path)
    manifest_path = app_root / "bundled_skills" / "manifest.json"
    manifest_path.write_text(
        '{"schema_version":1,"schema_version":1,"source":{},"skills":{}}',
        encoding="utf-8",
    )
    with pytest.raises(skills.ManifestValidationError, match="repeats"):
        skills.load_manifest(app_root=app_root)


def test_bundle_rejects_symbolic_links_when_supported(tmp_path: Path) -> None:
    app_root, _loaded = _make_app(tmp_path)
    bundle = app_root / "bundled_skills" / "stat-paper-writing"
    link = bundle / "linked.md"
    try:
        link.symlink_to(bundle / "SKILL.md")
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable for this test account")
    with pytest.raises(
        (skills.BundleValidationError, skills.ManifestValidationError), match="links"
    ):
        skills.load_manifest(app_root=app_root)


def test_status_reports_profile_missing_and_missing_without_mutation(tmp_path: Path) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    missing_profile = skills.skill_status(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert missing_profile.state == "profile_missing"
    assert not hermes_root.exists()

    profile = _make_profile(hermes_root)
    assert skills.configured_profile_home("lead", hermes_root=hermes_root) == profile
    before = sorted(str(path.relative_to(profile)) for path in profile.rglob("*"))
    missing_skill = skills.skill_status(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    after = sorted(str(path.relative_to(profile)) for path in profile.rglob("*"))
    assert missing_skill.state == "missing"
    assert before == after
    assert not (profile / skills.SIDECAR_NAME).exists()


def test_profile_directory_requires_a_safe_regular_config(tmp_path: Path) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = hermes_root / "profiles" / "lead"
    profile.mkdir(parents=True)
    status = skills.skill_status(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert status.state == "profile_missing"
    assert skills.configured_profile_home("lead", hermes_root=hermes_root) is None
    with pytest.raises(skills.ProfileNotFoundError):
        skills.provision_skill(
            "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
        )

    config_target = tmp_path / "outside-config.yaml"
    config_target.write_text("model: unsafe\n", encoding="utf-8")
    try:
        (profile / "config.yaml").symlink_to(config_target)
    except (OSError, NotImplementedError):
        pytest.skip("file links are unavailable for this test account")
    invalid = skills.skill_status(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert invalid.state == "invalid"
    with pytest.raises(skills.UnsafeProfileError):
        skills.configured_profile_home("lead", hermes_root=hermes_root)


def test_profile_provision_lock_rejects_a_second_process_style_file_lock(
    tmp_path: Path,
) -> None:
    profile = _make_profile(tmp_path / "hermes")
    with skills._profile_lock(profile, timeout=0.2):
        with pytest.raises(skills.ProvisioningError, match="timed out"):
            with skills._profile_lock(profile, timeout=0.05):
                pytest.fail("the same profile lock was acquired twice")


def test_install_is_current_idempotent_and_records_profile_sidecar(tmp_path: Path) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)

    installed = skills.provision_skill(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert installed.action == "installed"
    assert installed.status.state == "current"
    assert installed.status.managed is True
    sidecar = profile / skills.SIDECAR_NAME
    first_metadata = sidecar.read_bytes()
    record = json.loads(first_metadata)["skills"]["stat-paper-writing"]
    assert record["source_revision"] == REVISION
    assert record["bundle_digest"] == manifest.skills["stat-paper-writing"].digest

    repeated = skills.provision_skill(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert repeated.action == "already_current"
    assert sidecar.read_bytes() == first_metadata


def test_exact_unmanaged_bundle_is_current_and_explicit_install_adopts_it(
    tmp_path: Path,
) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)
    destination = profile / "skills" / "stat-paper-writing"
    shutil.copytree(
        manifest.bundle_root / "stat-paper-writing",
        destination,
    )

    status = skills.skill_status(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert status.state == "current"
    assert status.reason == "current_unmanaged"
    assert not (profile / skills.SIDECAR_NAME).exists()

    adopted = skills.provision_skill(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert adopted.action == "adopted"
    assert adopted.status.reason == "current_managed"


def test_unmanaged_difference_is_conflict_and_is_not_overwritten(tmp_path: Path) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)
    destination = profile / "skills" / "stat-paper-writing"
    destination.mkdir(parents=True)
    custom = destination / "SKILL.md"
    custom.write_text("custom local skill\n", encoding="utf-8")

    status = skills.skill_status(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert status.state == "conflict"
    assert status.reason == "unmanaged_conflict"
    with pytest.raises(skills.SkillConflictError):
        skills.provision_skill(
            "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
        )
    assert custom.read_text(encoding="utf-8") == "custom local skill\n"


def test_managed_change_is_modified_and_replace_preserves_timestamped_backup(
    tmp_path: Path,
) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)
    skills.provision_skill(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    changed = profile / "skills" / "stat-paper-writing" / "SKILL.md"
    changed.write_text("user modification\n", encoding="utf-8")

    status = skills.skill_status(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert status.state == "modified"
    assert status.reason == "managed_modified"
    replaced = skills.provision_skill(
        "lead",
        "stat-paper-writing",
        replace=True,
        manifest=manifest,
        hermes_root=hermes_root,
    )
    assert replaced.action == "replaced"
    assert replaced.status.state == "current"
    assert replaced.backup_path is not None
    backup = Path(replaced.backup_path)
    assert ".backup-" in backup.name
    assert backup.parent == profile / skills.BACKUP_DIRECTORY_NAME
    assert backup.parent.parent == profile
    assert backup.parent != profile / "skills"
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "user modification\n"


def test_replacement_rolls_back_when_sidecar_update_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)
    skills.provision_skill(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    changed = profile / "skills" / "stat-paper-writing" / "SKILL.md"
    changed.write_text("must survive rollback\n", encoding="utf-8")

    def fail_sidecar(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated metadata failure")

    monkeypatch.setattr(skills, "_write_sidecar", fail_sidecar)
    with pytest.raises(skills.ProvisioningError, match="restored"):
        skills.provision_skill(
            "lead",
            "stat-paper-writing",
            replace=True,
            manifest=manifest,
            hermes_root=hermes_root,
        )
    assert changed.read_text(encoding="utf-8") == "must survive rollback\n"


def test_post_write_verification_failure_restores_exact_prior_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)
    skills.provision_skill(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    destination = profile / "skills" / "stat-paper-writing"
    prior_skill = destination / "SKILL.md"
    prior_skill.write_text("prior local modification\n", encoding="utf-8")

    sidecar = profile / skills.SIDECAR_NAME
    sidecar_document = json.loads(sidecar.read_text(encoding="utf-8"))
    prior_sidecar = (
        json.dumps(sidecar_document, separators=(",", ":")) + "\n\n"
    ).encode("utf-8")
    sidecar.write_bytes(prior_sidecar)

    def fail_final_verification(*_args: object, **_kwargs: object) -> None:
        prior_skill.write_text("external change during verification\n", encoding="utf-8")
        raise skills.ProvisioningError("simulated final verification failure")

    monkeypatch.setattr(
        skills, "_verify_current_installation", fail_final_verification
    )
    with pytest.raises(skills.ProvisioningError, match="restored"):
        skills.provision_skill(
            "lead",
            "stat-paper-writing",
            replace=True,
            manifest=manifest,
            hermes_root=hermes_root,
        )

    assert prior_skill.read_text(encoding="utf-8") == "prior local modification\n"
    assert sidecar.read_bytes() == prior_sidecar
    recovery_root = profile / skills.BACKUP_DIRECTORY_NAME
    recovered_candidates = list(
        recovery_root.glob("stat-paper-writing.candidate.rollback-*")
    )
    assert len(recovered_candidates) == 1
    assert (
        recovered_candidates[0] / "SKILL.md"
    ).read_text(encoding="utf-8") == "external change during verification\n"


def test_failed_new_install_preserves_changed_candidate_and_restores_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)
    destination = profile / "skills" / "stat-paper-writing"

    def fail_final_verification(*_args: object, **_kwargs: object) -> None:
        (destination / "SKILL.md").write_text(
            "external new content\n", encoding="utf-8"
        )
        raise skills.ProvisioningError("simulated final verification failure")

    monkeypatch.setattr(
        skills, "_verify_current_installation", fail_final_verification
    )
    with pytest.raises(skills.ProvisioningError, match="restored"):
        skills.provision_skill(
            "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
        )

    assert not destination.exists()
    assert not (profile / skills.SIDECAR_NAME).exists()
    recovered_candidates = list(
        (profile / skills.BACKUP_DIRECTORY_NAME).glob(
            "stat-paper-writing.candidate.rollback-*"
        )
    )
    assert len(recovered_candidates) == 1
    assert (
        recovered_candidates[0] / "SKILL.md"
    ).read_text(encoding="utf-8") == "external new content\n"


def test_failed_adoption_restores_absent_sidecar_without_removing_live_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)
    destination = profile / "skills" / "stat-paper-writing"
    shutil.copytree(manifest.bundle_root / "stat-paper-writing", destination)

    def fail_final_verification(*_args: object, **_kwargs: object) -> None:
        (destination / "SKILL.md").write_text(
            "external adoption change\n", encoding="utf-8"
        )
        raise skills.ProvisioningError("simulated final verification failure")

    monkeypatch.setattr(
        skills, "_verify_current_installation", fail_final_verification
    )
    with pytest.raises(skills.ProvisioningError, match="restored"):
        skills.provision_skill(
            "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
        )

    assert (destination / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "external adoption change\n"
    assert not (profile / skills.SIDECAR_NAME).exists()


def test_shared_profile_requirements_are_unioned_and_provisioned(tmp_path: Path) -> None:
    _app_root, manifest = _make_app(tmp_path)
    mapping = {
        "research_lead": "shared",
        "paper_reviewer": "shared",
        "theorist": "theory",
    }
    assert skills.role_requirements("paper_reviewer", manifest=manifest) == (
        "stat-paper-reviewer",
    )
    assert skills.profile_requirements(mapping, manifest=manifest) == {
        "shared": ("stat-paper-reviewer", "stat-paper-writing"),
        "theory": ("stat-paper-writing",),
    }

    hermes_root = tmp_path / "hermes"
    _make_profile(hermes_root, "shared")
    results = skills.provision_profile_skills(
        "shared",
        ["research_lead", "paper_reviewer"],
        manifest=manifest,
        hermes_root=hermes_root,
    )
    assert {result.skill for result in results} == {
        "stat-paper-reviewer",
        "stat-paper-writing",
    }
    assert all(result.status.state == "current" for result in results)


def test_unsafe_installed_skill_link_has_invalid_status(tmp_path: Path) -> None:
    _app_root, manifest = _make_app(tmp_path)
    hermes_root = tmp_path / "hermes"
    profile = _make_profile(hermes_root)
    skills_path = profile / "skills"
    skills_path.mkdir()
    external = tmp_path / "external-skill"
    external.mkdir()
    (external / "SKILL.md").write_text("external\n", encoding="utf-8")
    destination = skills_path / "stat-paper-writing"
    try:
        destination.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory links are unavailable for this test account")

    status = skills.skill_status(
        "lead", "stat-paper-writing", manifest=manifest, hermes_root=hermes_root
    )
    assert status.state == "invalid"
    with pytest.raises(skills.UnsafeProfileError):
        skills.provision_skill(
            "lead",
            "stat-paper-writing",
            replace=True,
            manifest=manifest,
            hermes_root=hermes_root,
        )
