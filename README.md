# Research Hub

Research Hub is a local Web UI for running structured, multi-agent research workflows with Hermes. It coordinates project files, phase playbooks, run history, and user review. The research agents do the work inside a phase, but the user controls the workflow.

The central rule is simple: **nothing advances automatically**. The user explicitly starts every phase run, reviews its evidence, and decides whether to approve it, request a revision, rerun it, or leave it unapproved. Any phase can be rerun when the user wants a different question, scope, or approach.

## Quick start

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | 3.11+ recommended |
| Hermes Agent | latest | The `hermes` command must be on `PATH`; agents use it to execute phase tasks |

You also need a Hermes profile for each research role (research lead, theorist, data scientist, paper reviewer). Profiles are configured in `config.yaml` and created via Hermes.

### Setup (first time)

```bash
git clone <repo-url> research-hub
cd research-hub
./setup.sh
```

`setup.sh` creates the virtual environment, installs dependencies, initializes the database, and validates the config. It also checks whether `hermes` is on `PATH` and warns you if not.

<details>
<summary>Manual setup (if you prefer)</summary>

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python hub.py init
```

</details>

### Configure

Edit `config.yaml`. Set:

1. **`hub.workspace_dir`** — where project files are stored (defaults to `~/research`).
2. **`agents`** — map each research role (`research_lead`, `theorist`, `data_scientist`, `paper_reviewer`) to a Hermes profile name you have created.
3. **`hub.name`** — your hub's display name.

### Run

```bash
.venv/bin/python webapp.py
```

Open [http://127.0.0.1:5055](http://127.0.0.1:5055), then:

1. Create a project and write a focused research brief.
2. Open a phase and read its purpose, prerequisites, participants, and round plan.
3. Choose the allowed round count for a parallel or debate phase. Sequential phases use their configured stage plans.
4. Add optional direction for the agents.
5. If prerequisites are missing or stale, review the warning and explicitly confirm the override if you still want to proceed.
6. Start the run, monitor its progress and log, or cancel it while it is active.
7. When the run reaches `awaiting_review`, read the summary and choose approve, request revision, or rerun.
8. Start another phase only when you decide it is useful.

### Commands

| Command | What it does |
|---|---|
| `./setup.sh` | First-time setup: venv, install, init, sanity check |
| `make install` | Create venv + install runtime dependencies |
| `make install-dev` | Create venv + install runtime + test dependencies |
| `make init` | Initialize or migrate the hub database |
| `make run` | Start the web UI |
| `make test` | Run the full test suite |
| `make check` | Validate `config.yaml` |
| `make clean` | Remove caches |

## Repository structure

The repository separates **runtime files** (what you need to run Research Hub) from **development files** (tests and tooling). Runtime files are further split into the web entry point, the application package, configuration, and browser assets.

```text
research-hub/
│
├── webapp.py                     ← Flask entry point — start here
├── hub.py                        ← Project registry, config loader
├── schema.sql                    ← Hub database schema
├── config.yaml                   ← Main configuration (phases, agents, hub)
├── requirements.txt              ← Runtime dependencies
├── requirements-dev.txt          ← Test dependencies
├── setup.sh                      ← First-time setup script
├── Makefile                      ← Convenience commands
├── pyproject.toml                ← pytest config
│
├── core/                         ← Application package
│   ├── __init__.py
│   ├── README.md                    module overview
│   ├── launch_run.py                orchestration facade + re-exports
│   ├── launch_common.py             constants, paths, exceptions, helpers
│   ├── launch_process.py            process execution, run logs, PID supervision
│   ├── launch_manifest.py           manifest structure and frozen-input validation
│   ├── launch_plans.py              plan selection, method binding, baselines
│   ├── launch_prompts.py            sealed prompts, task briefs, review bundles
│   ├── launch_dispatch.py           round tracking and task dispatch
│   ├── launch_supervision.py        reconciliation, cancellation, cleanup
│   ├── project_state.py             state machine: runs, approvals, staleness
│   ├── profile_skills.py            recommended-skill installation
│   └── web_phase_data.py            read-only view models for the web UI
│
├── config/                       ← Phase playbooks and team definition
│   ├── phases/                      one directory per phase (slug-named)
│   │   └── <slug>/
│   │       ├── _phase.md               phase purpose, outputs, criteria
│   │       ├── _lead.md                lead coordination protocol
│   │       └── <role>.md               per-role instructions
│   ├── souls/                       agent personality files
│   │   └── <role>.md
│   ├── team/                        charter and norms
│   └── archive/                     superseded playbook designs (reference only)
│
├── bundled_skills/               ← Pinned Hermes skills shipped with the repo
│   ├── manifest.json
│   ├── stat-paper-reviewer/
│   └── stat-paper-writing/
│
├── static/                       ← Browser assets
│   ├── app.js
│   └── style.css
│
├── templates/                    ← Jinja2 HTML templates
│   ├── base.html
│   ├── project.html
│   ├── _tab_phase.html
│   └── …
│
└── tests/                        ← Test suite (not needed at runtime)
    ├── test_hub.py
    ├── test_launch_run.py
    ├── test_project_state.py
    ├── test_webapp.py
    ├── test_profile_skills.py
    ├── test_shipped_config_contract.py
    └── test_local_runtime_contract.py
```

**To deploy Research Hub on another machine**, you need everything except `tests/`, `Makefile`, and `requirements-dev.txt`. The `config/`, `bundled_skills/`, `templates/`, and `static/` directories are required at runtime — the application loads playbooks, skills, templates, and assets from them by path.

## Runtime data layout

Runtime data lives under `hub.workspace_dir`, which defaults to `~/research`. This is separate from the repository and is created when you start using Research Hub:

```text
~/research/
├── hub.db                           ← project registry (small SQLite database)
└── projects/
    ├── .research-hub-control/       ← internal control directory
    │   └── <project-slug>/
    │       ├── project.yaml             run state (atomic, locked)
    │       ├── project.lock
    │       └── runs/<phase-slug>/       sealed run artifacts
    │           ├── <run-id>.prompt.md
    │           ├── <run-id>.manifest.json
    │           ├── <run-id>.context/
    │           └── <run-id>.log
    └── <project-slug>/              ← agent-writable project workspace
        ├── setting.md                    research brief
        ├── phase-summaries/<slug>/       HTML run summaries
        ├── references/                   Phase 01 output
        ├── ideas/                        Phase 02 output
        ├── evaluations/                  Phase 03 output
        ├── draft/sections/               Phase 04 output
        └── draft/revised/                Phase 05 output
```

Phase artifacts are stored below the phase's configured `folder` in run-specific and round-specific directories. Summary paths include the immutable run ID, so reruns preserve all earlier evidence and decisions.

## Control model

A phase run follows this lifecycle:

```text
User starts a run
        |
        v
starting -> running -> submitting -> awaiting review
                                      |       |
                                      |       +-> request revision -> rerun when ready
                                      |
                                      +-> approve -> current approved result
```

An active run can also be cancelled by the user. Cancellation and worker failure first enter `stopping` while Research Hub verifies that the local worker and Hermes tasks have stopped. The project launch lock remains held until cleanup succeeds. If automatic cleanup cannot be confirmed, the Web UI lets the user retry it or explicitly release the lock after manually verifying shutdown and recording a note.

Important behavior:

- The user starts each phase and each rerun from the Web UI.
- Finishing the agent work only changes the run to `awaiting_review`. Agents cannot approve their own result.
- Approval is an explicit user decision. Only an approved, current run is trusted as cross-phase context.
- Prerequisites are informed warnings, not absolute locks. If an approved, current prerequisite is missing, the UI explains the gap and requires an explicit user override before starting.
- Only one run can be active within a project at a time. Separate projects can run independently.
- Starting or failing a rerun does not replace a previously approved result.
- Approving a replacement upstream run recursively marks approved dependent phases as stale. Their history is preserved, and the user decides whether and when to rerun them.
- Every run and summary remains in history. A new run never overwrites an earlier summary.
- Completing or approving a phase never starts the next phase.
- Each launch is bound to the phase configuration, role instructions, and exact prerequisite state that the UI presented. If any of them changes, the user must reload and review the run again.

## Default research workflow

The default configuration has five phases. The dependency column describes recommended trusted context. It does not remove the user's ability to override a warning and run a phase.

| Phase | Pattern | User-selectable work | Recommended approved prerequisites |
|---|---|---|---|
| Literature Review | Parallel | 1 to 5 rounds, default 2 | None |
| Method Development | Parallel | 2 to 3 rounds, default 2 | Literature Review |
| Idea Evaluation | Debate | 2 to 3 rounds, default 2 | Method Development |
| Draft Assembly | Parallel | 2 to 2 rounds, default 2 | Idea Evaluation |
| Review & Revision | Sequential | 2 stages (fixed) | Draft Assembly |

- **Literature Review:** the team surveys relevant work in parallel, producing structured notes and identifying gaps.
- **Method Development:** brainstorm genuinely new ideas — new mechanisms, frameworks, or insights.
- **Idea Evaluation:** a proposal is challenged and revised across multiple critique rounds, evaluating correctness, novelty, rigor, and cost.
- **Draft Assembly:** parallel drafting — intro and method (lead), theory and proofs (theorist), implementation and experiments (data analyst) — then the lead combines them into a formal draft.
- **Review & Revision:** the paper reviewer audits the complete draft — soundness, clarity, significance, originality — and produces ranked revision recommendations; the research lead then addresses each point and produces the final manuscript with a revision log.

Phase output folders follow the `folder` field in `config.yaml`. Folder names are descriptive of the phase purpose.

For parallel and debate phases, the user chooses a round count within the configured range before launch. The launcher then executes that exact count. For sequential phases, stage order and ownership are fixed by the selected configured plan and shown in the UI before launch. Optional variants — Phase 03 theory plans, opt-in protocol checkpoints, method binding, and Phase 06-style review runs — appear only when the phase configuration declares them.

### Optional phase features

- **Theory plans** (a Phase 03 slug with a `proof_audit` declaration): three user-selectable run plans — standard (configured stages only), standard with an independent audit stage, or audit-only (review the sealed artifact without revising it).
- **Protocol checkpoint** (a sequential phase with `protocol_checkpoint: true`): before any result-stage work, the lead writes a protocol document to a write-limited directory. The launcher then reads and hashes the entire protocol directory, verifies its byte size and SHA-256 hash, seals the report and complete inventory, and only then dispatches the separate result task. Every result-stage task receives a different write-limited round directory. Later stages and run submission also require the unchanged sealed checkpoint. The Web UI shows whether this checkpoint is pending or sealed. Corrections use new versioned files and retain the sealed originals.
- **Paper-writing review variants** (a phase with the `06-paper-writing` slug): a full run ends with a context-restricted first reading of the exact review manuscript before a context-aware assessment, and its history row offers a separate control to review that exact post-review manuscript in a new review-only run that performs no author revision. The default configuration does not include this phase; the Review & Revision phase covers draft review instead.

## Configuration

### Hub and agents

Hermes creates and owns profiles. Research Hub maps stable research role IDs to those profile names:

```yaml
hub:
  name: "My Research Hub"
  workspace_dir: "~/research"
  run_timeout_minutes: 120
  allow_unattended_tools: true

agents:
- id: "research_lead"
  profile: "research_lead"
  name: "Research Lead"
  role: "domain, framing, writing"

- id: "theorist"
  profile: "theory-profile"
  name: "Theorist"
  role: "methods, mathematics, rigor"
```

Phase members and stage owners reference `id`. `profile` is the Hermes profile used to execute that role, so the two names do not need to be identical. Model and provider settings remain in each Hermes profile's own configuration.

### Recommended role skills

Research Hub includes pinned copies of two recommended Hermes skills under `bundled_skills/`:

| Research role | Recommended skill |
|---|---|
| Research lead, theorist, data analyst | `stat-paper-writing` |
| Paper reviewer | `stat-paper-reviewer` |

Open **Profiles** in the Web UI to see the status for each role's mapped Hermes profile. Installation occurs only when the user selects **Install recommended skill**. A status check never changes the profile, and Research Hub never replaces a different or locally modified copy without a separate, confirmed replacement action. Repeating an install for the same pinned copy is safe.

The skills are recommendations, not phase prerequisites. A phase can still run when a recommended skill is absent. Immediately before starting a writing chat or queuing an independent-review task, Research Hub checks the installed content against the pinned bundle and passes the skill name to Hermes only when the copy is current. A copy that is missing, changed, or in conflict is not preloaded. Review-only paper runs do not give the author-side writing skill to the research lead.

Hermes task commands identify a skill by name. A manual change to the profile after a task is queued but before Hermes loads it can therefore change the guidance used by that task. Research Hub blocks its own skill installation and replacement controls while a run is active, but it cannot prevent edits made outside the application. Do not modify active Hermes profiles during a run.

The reviewer bundle contains an optional OpenAlex search helper. If an agent invokes it, the helper sends search terms and any author, affiliation, or ORCID filters to OpenAlex over HTTPS and can read `OPENALEX_API_KEY` from the Hermes process environment. Do not use confidential manuscript prose as a search query. Installing the skill does not run the helper or make a network request.

Hermes profile locations follow the active platform: `%LOCALAPPDATA%\hermes` on Windows and `~/.hermes` on POSIX systems. `RESEARCH_HUB_HERMES_ROOT` can set an explicit root. If `HERMES_HOME` is already set, Research Hub derives the same profile root from it. Each new run records the resolved root and supplies it to its Hermes processes, so status checks, installation, and execution use the same profile tree.

When `allow_unattended_tools` is `true`, the explicitly launched background Hermes run may use tools without an interactive confirmation prompt. Agents are instructed to keep their work in the project, but the Hermes process inherits the filesystem and network access of the operating-system account that launched it. Use an appropriately restricted account or sandbox when stronger isolation is required. Setting this option to `false` disables background phase launch because the detached Web UI worker has no interactive terminal in which to request approvals.

### Parallel or debate phase

```yaml
- slug: "02-method-development"
  name: "Method Development"
  description: "Brainstorm genuinely new ideas — new mechanisms, frameworks, or insights"
  pattern: parallel
  gated_by: ["01-literature-review"]
  folder: "ideas/"
  members: [theorist, research_lead, data_scientist]
  rounds: {min: 2, default: 2, max: 3}
```

### Sequential phase

```yaml
- slug: "05-review-revision"
  name: "Review & Revision"
  description: "Paper reviewer audits the draft; lead revises into the final manuscript"
  pattern: sequential
  gated_by: ["04-draft-assembly"]
  folder: "draft/revised/"
  members: [paper_reviewer, research_lead]
  rounds: {min: 2, default: 2, max: 2}
  stages:
  - role: paper_reviewer
    name: "Review"
    description: "Audit the complete draft and produce ranked revision recommendations."
  - role: research_lead
    name: "Revise"
    description: "Address each review point and produce the final manuscript with a revision log."
```

For a standard sequential phase, `rounds.min`, `rounds.default`, and `rounds.max` must all equal the number of configured stages. The standard `rounds` mapping may be omitted and is then inferred from the stage count.

### Optional feature declarations

Special run machinery activates only when the phase declares it (see *Optional phase features*):

```yaml
- slug: "03-idea-evaluation"
  name: "Idea Evaluation"
  pattern: debate
  # ...
  proof_audit:                      # user-selectable theory run plans
    plans: [standard, standard_with_audit, audit_only]
    stage:
      role: paper_reviewer
      name: "Audit the final theoretical analysis independently"
      description: "Check the exact sealed theory artifact without revising it."
  method_binding: true              # freeze an exact method identity per run
```

```yaml
- slug: "04-draft-assembly"
  name: "Draft Assembly"
  pattern: parallel
  # ...
  protocol_checkpoint: true         # seal the protocol before any main result
```

A `proof_audit` declaration is valid only on a Phase 03 slug. With it, the selected plan fixes the run to the configured stage count, the stage count plus one audit stage, or a single audit-only stage. `protocol_checkpoint` requires a sequential stage plan. `method_binding` is a boolean any phase may declare; Phase 03 and 04 slugs whose configured pattern is not parallel or debate keep the historical binding automatically so runs sealed under earlier configurations remain reproducible.

Configuration is validated before use. Validation checks role and profile identifiers, Hermes-reserved profile names, the required `research_lead`, a profile independent from contributing roles for `paper_reviewer`, bounded nonblank UTF-8 role souls, safe project-relative output folders, round bounds, sequential stage owners, debate minimum rounds, prerequisite graph cycles, optional feature declarations, and required playbook files. Invalid configuration fails with a focused error instead of launching partial work.

`gated_by` defines the recommended approved prerequisites and downstream staleness graph. `context_from` names additional approved, current phase summaries that are useful when available but are not prerequisites. The current phase's prior approved result is included automatically on reruns for comparison.

## Writing playbooks

Each `config/souls/<role>.md` file defines the role's durable identity, reasoning habits, and boundaries. The launcher freezes and hashes the relevant soul, then embeds its exact text in the sealed lead prompt or member task brief before the phase-specific playbook.

Each `config/phases/<slug>/` directory contains:

- `_phase.md`: purpose, expected outputs, and completion criteria.
- `_lead.md`: the phase-specific coordination protocol.
- `<role>.md`: the instructions for each participating role.

Playbooks should describe a reusable research process, not a predetermined conclusion. They should make negative findings, disagreements, uncertainty, unsupported claims, and missing evidence visible. A useful summary helps the user decide what to approve, what to revise, and what to investigate next.

## Security and trust boundary

Research Hub is a local research tool, not a multi-user service. The development server binds to `127.0.0.1` by default and the app does not provide user accounts or network authentication. Startup refuses non-loopback values of `RESEARCH_HUB_HOST`. At request time, Flask also rejects untrusted Host headers, known non-loopback server addresses, and non-loopback client addresses. Run the supported `python webapp.py` command from the source tree. Do not place it behind an untrusted proxy or expose it through another server or directly to an untrusted network.

State-changing Web UI requests use CSRF protection. Project Markdown is rendered without trusting embedded HTML, and agent-authored summaries are served with a restrictive browser sandbox and Content Security Policy. Run manifests, frozen inputs, completed evidence, final products, summaries, and structured decision records are hash checked. Approval requires a fresh context comparison and explicit acceptance of the sealed proposed baseline. These controls reduce browser and workflow risk, but agent output is still untrusted research material and should be read critically before approval.

Do not put API keys or other secrets in project briefs, playbooks, feedback, logs, or summaries. Hermes credentials should remain in the appropriate Hermes configuration or environment.

## Tests

```bash
make install-dev   # or: .venv/bin/pip install -r requirements-dev.txt
make test          # or: .venv/bin/python -m pytest
```

The current tests cover configuration validation, clean initialization and additive database migration, safe project directory handling, atomic run reservation, prerequisite overrides, context and summary integrity, manifest sealing, round and artifact validation, optional proof-audit plans, exact manuscript re-review targets, separated reviewer substages, review transitions, immutable derivative-run source baselines, opt-in protocol checkpoints and workspaces, structured method selection, launch-plan and prerequisite version binding, explicit baseline acceptance, approval-time context drift, recursive staleness, verified cleanup and explicit recovery, cancellation through submission, failure fallback, and legacy state migration.

A contract suite (`tests/test_shipped_config_contract.py`) loads the shipped `config.yaml` and verifies that every configured phase builds a round plan, validates a launch manifest, and inherits only the special behavior it explicitly declares.

## License

Private project.
