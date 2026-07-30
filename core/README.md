# Research Hub core package

Application modules for project state management, run orchestration,
prompt construction, versioned phase records, the knowledge layer, and web
view models. The Flask entry point (`webapp.py`) and the data layer
(`hub.py`) live in the repository root; everything here is imported by them.

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

## Versioned phase records

Each phase owns a canonical scientific record. Runs stage output off to the
side; sealing binds the submitted bytes; promotion replaces the canonical
record transactionally. `phase_records.py` is the facade the state machine
calls; the per-phase modules own the layouts.

| Module | Responsibility |
|--------|----------------|
| `literature_records.py` | Phase 1 cumulative reference library: per-run deltas merged atomically into cards, index, and synthesis |
| `method_menu.py` | Phase 2 method catalog: validate, stage, publish, and retire versioned methods with stable IDs and definition digests |
| `theory_records.py` / `theory_promotion.py` | Phase 3 current-replacement theory packages and their deterministic transaction machine |
| `empirical_records.py` / `empirical_promotion.py` / `empirical_schema.py` | Phase 4 current-replacement empirical packages, evidence index, and transactions |
| `manuscript_records.py` | Phase 5 manuscripts assembled from exact frozen upstream bases |
| `phase_records.py` | Phase-record facade: planning, promotion, recovery entry points, current upstream basis |
| `phase5_projection.py` | Phase 5 readiness projection from current branch records |
| `promotion_journal.py` | Durable per-run promotion intents (crash-recovery metadata) |
| `promotion_recovery.py` | Reconciles retained journals after interruption; converge or roll back |

## Knowledge layer

Structured companions to the Phase 3/4 packages that let the system detect
semantic drift between sibling phases without reading full manuscripts. The
branch graph is a rebuildable shadow materialization — never a source of
scientific truth.

| Module | Responsibility |
|--------|----------------|
| `knowledge_schema.py` | Shared schema constants and graph shape |
| `knowledge_content.py` | Semantic content projections and digests (generation-free) |
| `knowledge_basis.py` | Pure basis values and alignment semantics (`exact_match`, `review_required`, …) |
| `knowledge_fragments.py` | Validation of phase-owned knowledge fragments |
| `knowledge_heads.py` | Verified current Phase 3/4 heads, live or frozen derivation |
| `knowledge_events.py` / `knowledge_event_schema.py` / `knowledge_event_diff.py` | Immutable knowledge mutation events: storage, contract, and diffing |
| `knowledge_graph.py` | Per-branch dependency graph over canonical records |

## State and views

| Module | Responsibility |
|--------|----------------|
| `project_state.py` | Locked, atomic per-project run state: reservations, transitions, approvals, staleness, prerequisite reports, and integrity verification. Kept as one module by design: it is a single tightly-coupled state machine, and all callers use module-attribute access. |
| `web_phase_data.py` | Read-only view models for the phase and overview pages. |
| `web_branch_status.py` | Per-method branch status aggregation for the phase tabs. |
| `web_prerequisites.py` | Prerequisite report adapter for launch forms. |
| `current_results.py` | Freshness derivation (fresh/stale/unknown badge) for method-bound runs; UI-only, does not gate launches. |
| `profile_skills.py` | Read-only recommended-skill status checks and explicit, transactional profile installation or replacement. |
| `phase_options.py` | Per-phase run options presented by the Web UI. |

## Supporting utilities

| Module | Responsibility |
|--------|----------------|
| `filesystem_utils.py` | Shared symlink/reparse detection and filesystem predicates |
| `strict_json.py` | Strict JSON parsing helpers (no ambiguous documents) |
| `safe_markdown.py` | Markdown rendering with a safe subset for summaries |

There is no unattended automation in this repository by design: every phase
run is started and approved explicitly by the user from the Web UI. See the
top-level `README.md` for the control model.
