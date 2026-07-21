# Research Hub

Research Hub is a local Web UI for running structured, multi-agent research workflows with Hermes. It coordinates project files, phase playbooks, run history, and user review. The research agents do the work inside a phase, but the user controls the workflow.

The central rule is simple: **nothing advances automatically**. The user explicitly starts every phase run, reviews its evidence, and decides whether to approve it, request a revision, rerun it, or leave it unapproved. Any phase can be rerun when the user wants a different question, scope, or approach.

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

An active run can also be cancelled by the user. Cancellation and worker failure
first enter `stopping` while Research Hub verifies that the local worker and Hermes
tasks have stopped. The project launch lock remains held until cleanup succeeds.
If automatic cleanup cannot be confirmed, the Web UI lets the user retry it or
explicitly release the lock after manually verifying shutdown and recording a note.
```

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

## Quick start

Requirements:

- Python 3.10 or newer
- Hermes Agent installed and available as `hermes` on `PATH`
- A Hermes profile for each configured research role
- A running Hermes gateway for each participating profile

From the repository root:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

Activate the virtual environment using the command for your shell, then edit `config.yaml`. Set the workspace directory, map every role to an existing Hermes profile, and review the phase definitions.

Research Hub currently runs directly from this source tree. It is not distributed
as a Python package or wheel, because its runtime also depends on the repository's
configuration, playbooks, templates, static files, scripts, and database schema.

Initialize or migrate the workspace database:

```bash
python hub.py init
```

Start the local Web UI:

```bash
python webapp.py
```

Open [http://127.0.0.1:5055](http://127.0.0.1:5055), then:

1. Create a project and write a focused research brief.
2. Open a phase and read its purpose, prerequisites, participants, and round plan.
3. Choose the allowed round count for a parallel or debate phase. Sequential
   phases use their configured stage plans. For Phase 03, choose standard theory,
   standard theory plus an independent audit, or an audit-only run of a sealed
   existing theory artifact. Standard Phase 03 and Phase 04 runs use the exact
   approved Phase 02 method ID and version, or both fields of a run-specific
   method identity entered by the user.
4. Add optional direction for the agents.
5. If prerequisites are missing or stale, review the warning and explicitly confirm the override if you still want to proceed.
6. Start the run, monitor its progress and log, or cancel it while it is active. If cleanup remains pending, inspect the recorded reason, retry cleanup, or release the lock only after manually verifying that external work has stopped.
7. When the run reaches `awaiting_review`, read the summary and choose approve, request revision, or rerun.
8. Start another phase only when you decide it is useful.

After a full Phase 06 run produces a post-review manuscript, its history row
offers a separate control to review that exact version. The new review-only run
shows the selected path and SHA-256 and performs no author revision.

`python hub.py init` is idempotent. Normal Web UI access also initializes and additively migrates the small project registry when needed.

## Default research workflow

The default configuration has six phases. The dependency column describes recommended trusted context. It does not remove the user's ability to override a warning and run a phase.

| Phase | Pattern | User-selectable work | Recommended approved prerequisites |
|---|---|---|---|
| Literature Review | Parallel | 1 to 5 rounds, default 2 | None |
| Method Development | Debate | 2 to 3 rounds, default 2 | Literature Review |
| Theoretical Analysis | Sequential | Standard 3 stages, standard plus audit 4 stages, or audit-only 1 stage | Method Development |
| Numerical Validation | Sequential | 4 fixed stages | Method Development |
| Scientific Interpretation | Debate | 2 to 3 rounds, default 2 | Numerical Validation |
| Paper Writing | Sequential | 5 fixed stages, or a 2-stage review-only rerun of a selected manuscript | Theoretical Analysis and Scientific Interpretation |

The fixed sequential stages are:

- **Theoretical Analysis:** standard theory has the theorist draft the analysis,
  the research lead assess how the results support the contribution, and the
  theorist revise it. The user can add a fourth-stage independent audit of the
  final theorist artifact, or run a one-stage audit of an eligible sealed artifact
  from an earlier run without repeating or revising the theory.
- **Numerical Validation:** the data analyst implements and tests, the theorist
  checks the mathematics against the code, the data analyst corrects and
  completes the study, and the research lead assesses the evidence. Before any
  main result is generated, a protocol-only task must finish and seal a
  machine-verified checkpoint containing the study design and exact
  protocol-file hashes. Only then can the separate result task be dispatched.
- **Paper Writing:** the research lead frames the paper, the theorist writes the
  theory, and the data analyst writes experiments and results. A paper reviewer
  then performs a context-restricted first reading of the exact review manuscript before
  a second, context-aware assessment against the scientific record.

For parallel and debate phases, the user chooses a round count within the
configured range before launch. The launcher then executes that exact count. For
sequential phases, stage order and ownership are fixed by the selected configured
plan and shown in the UI before launch. Phase 03's two audit plans and Phase 06's
review-only rerun are explicit user-selected variants; none is added automatically.

## Orchestration patterns

| Pattern | Execution contract |
|---|---|
| `parallel` | Every configured member investigates independently in each round. Later rounds target gaps found in earlier outputs. |
| `debate` | Members produce proposals in the first round, then cross-critique and revise in later rounds. |
| `sequential` | Exactly one configured role owns each stage. Stages run in order and each stage receives the prior output. |

The research lead coordinates only the run the user authorized. It creates run-scoped Hermes kanban tasks, waits for the required artifacts, and writes a decision-oriented HTML summary. Its final command submits the run for review and stops.

## Scientific handoff contract

Every role returns a nonempty report labeled **Complete**, **Partial**, or
**Failed**. Partial and Failed reports preserve usable evidence and identify the
missing work and its scientific consequence. A missing artifact is a technical
run failure rather than a scientific outcome.

Material hypotheses, theoretical statements, empirical findings, and
conclusions are tracked in one accepted scientific record with stable statement
IDs. Roles propose compact scientific record changes. Every final summary begins
with a User Decision Brief and a Comparison with the approved run, then gives
the consolidated changes and the Proposed scientific baseline. Approval accepts
that baseline as a whole; the user requests revision before approval when only
part is acceptable.

Each new run also writes a validated decision record beside its HTML summary.
The Web UI shows the scientific outcome, requested decision, team recommendation,
main evidence, principal risk, smallest result that would change the recommendation,
option consequences, rerun question, and exact proposed baseline separately from
the technical run status. Complete, Partial, and Failed never approve, reject,
or launch work. Approval requires the user to accept the exact sealed proposed
baseline explicitly.

## Architecture

The application deliberately separates project registration, run control, orchestration, and presentation:

| Component | Responsibility |
|---|---|
| `webapp.py` | Flask Web UI, user decisions, launch controls, progress, review, settings, and profile mapping |
| `hub.py` | Validated configuration, SQLite project registry, safe project paths, database initialization and migration |
| `scripts/project_state.py` | Locked and atomic project state, run transitions, approvals, staleness, prerequisite reports, and immutable context records |
| `scripts/launch_run.py` | Preflight checks, prompt construction, Hermes worker launch, progress commands, cancellation, and worker reconciliation |
| `scripts/web_phase_data.py` | Read-only view models for phase and overview pages |
| `config/phases/<slug>/` | Phase protocol, research-lead instructions, and role-specific playbooks |
| `config/souls/` | Stable identity, reasoning standards, and boundaries for each role |
| `config/team/` | Shared team charter and operating norms |

SQLite stores only the project registry. Each project's run-control history lives in a matching directory under `projects/.research-hub-control/`, outside the Hermes project workspace. Recognized regular files from an existing `.log/` state directory are copied there once within file-count and byte limits; links and special files are refused, and the original directory remains a recoverable legacy backup. Safe legacy approved summaries receive a one-time integrity hash when they can be verified inside the project. State changes use a per-project cross-process lock and atomic file replacement, which also enforces the one-active-run rule. Project creation, run reservation, and workspace replacement additionally share a hub-wide operation lock.

At launch, the system freezes the project brief, role souls, playbooks, team
rules, current approved prerequisite summaries and structured decision records,
optional approved context, and the phase's prior approved result. Standard Phase
03 and Phase 04 runs also freeze the exact selected method ID, version, and its
approved or run-specific provenance. It records run IDs and content hashes,
validates the frozen-input schema, and embeds each role's exact soul text and hash
in its sealed prompt or task brief. A selected Phase 03 proof audit seals the
exact final theory artifact and its evidence inventory, including an eligible
artifact from an earlier run for audit-only. Audit-only Phase 03 runs and
review-only Phase 06 runs also freeze the source run's complete summary and
structured scientific record. The new run labels that source as accepted,
proposed, or historical from its status at selection, preserves unaffected
statement IDs, and applies only findings produced by the new audit or review.
Reviewer tasks run from
sealed workspaces containing only their authorized copied inputs and one report
path. Phase 06 preserves the context-restricted first reading before the
context-aware assessment. This controls the context supplied by Research Hub;
it is not an operating-system sandbox. The evidence lineage remains inspectable
even if project files or upstream work change later.

For Phase 04, the frozen manifest names one run-specific protocol directory and
checkpoint. Round 1 first dispatches a protocol-only data-analyst task with the
protocol-stage report and checkpoint inventory. After that isolated task ends,
Research Hub requires every listed regular file to be inside the protocol
directory, verifies its byte size and SHA-256 hash, seals the report and complete
inventory, and only then dispatches the separate result task. Every result-stage
task receives a different write-limited round directory. Later stages and run
submission also require the unchanged sealed checkpoint. The Web UI shows whether
this checkpoint is pending or sealed. Corrections use new versioned
files and retain the sealed originals.

## Project layout

Application files live in this repository:

```text
research-hub/
|-- webapp.py
|-- hub.py
|-- config.yaml
|-- schema.sql
|-- scripts/
|   |-- launch_run.py
|   |-- project_state.py
|   `-- web_phase_data.py
|-- config/
|   |-- phases/<phase-slug>/
|   |   |-- _phase.md
|   |   |-- _lead.md
|   |   `-- <role>.md
|   |-- souls/<role>.md
|   `-- team/
|-- templates/
|-- static/
`-- tests/
```

Runtime data lives under `hub.workspace_dir`, which defaults to `~/research`:

```text
~/research/
|-- hub.db
`-- projects/
    |-- .research-hub-control/
    |   `-- project-003-example/
    |       |-- project.yaml
    |       `-- runs/<phase-slug>/
    |           |-- <run-id>.prompt.md
    |           |-- <run-id>.manifest.json
    |           |-- <run-id>.context/
    |           `-- <run-id>.log
    `-- project-003-example/
        |-- setting.md
        |-- phase-summaries/<phase-slug>/<run-id>.html
        |-- references/
        |-- ideas/
        |-- numerical/
        `-- draft/
```

Phase artifacts are stored below the phase's configured folder in run-specific and round-specific directories. Summary paths include the immutable run ID, so reruns preserve all earlier evidence and decisions.

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

When `allow_unattended_tools` is `true`, the explicitly launched background Hermes run may use tools without an interactive confirmation prompt. Agents are instructed to keep their work in the project, but the Hermes process inherits the filesystem and network access of the operating-system account that launched it. Use an appropriately restricted account or sandbox when stronger isolation is required. Setting this option to `false` disables background phase launch because the detached Web UI worker has no interactive terminal in which to request approvals.

### Parallel or debate phase

```yaml
- slug: "02-method-development"
  name: "Method Development"
  description: "Design and specify the proposed method"
  pattern: debate
  gated_by: ["01-literature-review"]
  context_from: []
  folder: "ideas/"
  members: [theorist, research_lead, data_scientist]
  rounds: {min: 2, default: 2, max: 3}
```

### Sequential phase

```yaml
- slug: "03-theoretical-justification"
  name: "Theoretical Analysis"
  description: "Develop proofs, bounds, and guarantees"
  pattern: sequential
  gated_by: ["02-method-development"]
  folder: "draft/theory/"
  members: [theorist, research_lead, paper_reviewer]
  proof_audit:
    plans: [standard, standard_with_audit, audit_only]
    stage:
      role: paper_reviewer
      name: "Audit the final theoretical analysis independently"
      description: "Check the exact sealed theory artifact without revising it."
  rounds: {min: 3, default: 3, max: 3}
  stages:
  - role: theorist
    name: "Develop the theory"
    description: "Develop the necessary results, their dependencies, assumptions, scope, and proofs."
  - role: research_lead
    name: "Assess theoretical support"
    description: "Assess how the results support the contribution, including scope and unresolved gaps."
  - role: theorist
    name: "Revise the analysis"
    description: "Revise the analysis where needed and state any unresolved mathematical questions explicitly."
```

For a standard sequential phase, `rounds.min`, `rounds.default`, and `rounds.max`
must all equal the number of configured stages. Phase 03 additionally declares
its audit plans and reviewer stage; the selected plan fixes its run to 3, 4, or
1 stage. The standard `rounds` mapping may be omitted and is then inferred from
the stage count.

Configuration is validated before use. Validation checks role and profile identifiers, the required `research_lead`, bounded nonblank UTF-8 role souls, safe project-relative output folders, round bounds, sequential stage owners, debate minimum rounds, prerequisite graph cycles, and required playbook files. Invalid configuration fails with a focused error instead of launching partial work.

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

Install the development requirements and run the suite from the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

The current tests cover configuration validation, clean initialization and
additive database migration, safe project directory handling, atomic run
reservation, prerequisite overrides, context and summary integrity, manifest
sealing, round and artifact validation, optional proof-audit plans, exact
manuscript re-review targets, separated reviewer substages, review transitions,
immutable derivative-run source baselines, pre-result Phase 04 protocol
checkpoints and workspaces, structured method selection, launch-plan and
prerequisite version binding, explicit baseline acceptance, approval-time context
drift, recursive staleness, verified cleanup and explicit recovery,
cancellation through submission, failure fallback, and legacy state migration.

## License

Private project.
