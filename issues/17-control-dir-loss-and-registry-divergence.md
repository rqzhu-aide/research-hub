# Situation 17: Control-Dir Loss and Registry Divergence

## Scenario (disaster recovery, three variants)

The Research Hub stores truth in three places: the SQLite registry
(`~/research/hub.db`, projects table only), the agent-visible workspace
(`~/research/projects/project-NNN-<slug>/`), and the protected control
directory (`~/research/projects/.research-hub-control/<slug>/` — state,
manifests, sealed prompts, journals). What breaks when each one is lost?

## Variant (a): control directory deleted or restored from a stale backup

### Missing control dir — FAILS OPEN

- **System behavior**: `_read_unlocked` returns an empty state when
  `project.yaml` is absent (`project_state.py:784-785`). **Verified
  empirically**: `load()` silently returns `{schema_version: 10, project: {},
  phases: {}}` and recreates the control dir + an empty `project.yaml`.
- **Consequence**: all run history, approvals, manifests, and current-record
  pointers are gone — with **zero warning**. The project opens looking brand
  new.
- **Partial self-heal**: the P1 literature record is file-derived
  (`phase_records.py:398-405`), so `references/` still feeds future launches.
  Run history, approvals, and manifests are unrecoverable; phase summaries in
  the workspace are orphaned (state-only reads, `web_phase_data.py:1793`).
- **Smooth?** ❌ Silent data loss. The system should fail loudly when a
  project with workspace artifacts has no control state.

### Corrupt project.yaml — 500

- **System behavior**: corrupt YAML → `StateValidationError`
  (`project_state.py:792-795`, verified), unhandled in `project_view`
  (`webapp.py:934`) → Flask 500. Fails closed, but ugly.

### Stale backup + retained promotion journal — fail closed

- **System behavior**: a week-old `project.yaml` restored alongside a newer
  retained journal → reconcile raises `StateValidationError` ("promotion
  recovery run is missing from state", `project_state.py:1711-1714`) on every
  load. Safe (no divergence), but the user gets a 500 with no guided repair.

## Variant (b): workspace deleted, hub.db intact

- **System behavior**: `hub.get_project_dir` glob fallback returns `None`
  (`hub.py:960-994`) → `project_view` flashes "not found" and redirects to
  the index (`webapp.py:1000-1005`) → the index redirects back to
  `projects[0]` (`webapp.py:975-979`) → **redirect loop** if it is the newest
  project. There is no delete/archive UI or CLI to remove the dead registry
  entry.
- **Smooth?** ❌ The loop makes the whole UI unusable until the DB row is
  removed by hand.

## Variant (c): hub.db deleted, workspaces + control dirs survive

- **System behavior**: `setup.sh` only runs `hub.py init` (`setup.sh:60`);
  the CLI has only `init` (`hub.py:997-1010`) → a fresh empty DB. **No
  re-registration/adopt mechanism exists.** Because the table uses
  AUTOINCREMENT (`schema.sql:7`), re-creating projects makes `project-001-*`
  rows while the old `project-004-*` workspace stays orphaned — id-based
  discovery (`hub.py:972-994`) can't adopt it.
- **Manual repair**: a sqlite insert with the matching `id` +
  `directory_name` fully restores the project (all other state is
  file-derived) — UNVERIFIED end-to-end.
- **Smooth?** ⚠️ Recoverable by hand; no supported path.

## Issues identified

### 🔴 Issue A: Missing control dir silently resets the project

**Severity: High.** `project_state.py:784-785` treats a missing
`project.yaml` as "new project" rather than "lost state". For a project with
a populated workspace, this is silent, irreversible-looking data loss. It
should detect the workspace/control mismatch and refuse to proceed with a
clear error and recovery instructions.

### 🟡 Issue B: Deleted workspace causes a redirect loop

**Severity: Medium.** `webapp.py:975-1005`: index → `projects[0]` →
project_view → index. The UI becomes unusable; no registry-delete path
exists.

### 🟡 Issue C: Corrupt or stale state fails as an unhandled 500

**Severity: Medium.** Corrupt YAML (`webapp.py:934`) and stale-backup journal
reconcile (`project_state.py:1711-1714`) both surface as raw Flask 500s. Fail
-closed is right; the error page should say what to do.

### 🟡 Issue D: No disaster-recovery re-registration path

**Severity: Medium.** `hub.py:997-1010` exposes only `init`. An
`adopt <directory>` command (scan workspace, re-register with the original id
from control-dir metadata) would make hub.db loss a non-event.

## Space summary

Not applicable — no runs are executed in this situation.

## Verdict

❌ **Disaster recovery is the weakest surface found in any situation.** The
three-storage-parts design is otherwise sound (registry is disposable, state
is file-derived), but the failure modes are: silent reset (a), redirect loop
(b), and manual-only repair (c). None of these need new architecture — only
detection, honest errors, and one `adopt` command.
