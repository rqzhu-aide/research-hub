# Research Hub core package

Application modules for project state management, run orchestration,
prompt construction, and web view models. The Flask entry point
(`webapp.py`) and the data layer (`hub.py`) live in the repository
root; everything here is imported by them.

## Run launching (`launch_*`)

`launch_run.py` is the orchestration facade: it prepares one user-authorized
run, delegates the internal work to the research lead, and supervises the
worker. It also re-exports every public name from the focused modules below,
so callers have a single import location. Cross-module calls use
module-attribute access (`launch_manifest._read_manifest(...)`), which keeps
monkeypatching in tests precise and explicit.

| Module | Responsibility |
|--------|----------------|
| `launch_common.py` | Shared constants, config paths, exceptions, small file/text helpers, run artifact paths |
| `launch_process.py` | Process execution with bounded output, run logs, PID identity and termination |
| `launch_manifest.py` | Run manifest structure and frozen-input validation |
| `launch_plans.py` | Phase plan selection (theory plans, method binding), skill fingerprints, source baselines |
| `launch_prompts.py` | Sealed lead prompts, task briefs, review bundles, round instructions |
| `launch_dispatch.py` | Run helper mechanics: round tracking and Hermes task dispatch |
| `launch_supervision.py` | Active-run reconciliation, cancellation, and cleanup |

## State and views

| Module | Responsibility |
|--------|----------------|
| `project_state.py` | Locked, atomic per-project run state: reservations, transitions, approvals, staleness, prerequisite reports, and integrity verification. Kept as one module by design: it is a single tightly-coupled state machine, and all callers use module-attribute access. |
| `web_phase_data.py` | Read-only view models for the phase and overview pages. |
| `profile_skills.py` | Read-only recommended-skill status checks and explicit, transactional profile installation or replacement. |

There is no unattended automation in this repository by design: every phase
run is started and approved explicitly by the user from the Web UI. See the
top-level `README.md` for the control model.
