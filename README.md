# Research Hub

A web-based orchestrator for **team-lead-driven multi-agent research projects**. Define a small team of Hermes profiles, and the Hub runs them through a structured sequence of research phases — literature review → method development → theory → numerics → analysis → paper — with a live web UI to watch it happen.

The key idea: one profile (the **research lead**) is an autonomous orchestrator, and the rest are contributors. Python is a thin launcher + recorder. The actual intelligence lives in **playbooks** (markdown files per phase) that the lead reads, interprets, and dispatches against.

## How it works

1. **Define 3–4 Hermes profiles** in `config.yaml` (one must be the research lead).
2. **Define the phases** your project moves through, each with a `pattern` (parallel / sequential / debate) and a gate list (`gated_by`).
3. **Write playbooks** in `config/phases/<slug>/` — one per role per phase. These are the instructions each agent receives.
4. **Start a phase** from the web UI. The Hub's launcher assembles a prompt, spawns the lead as a background `hermes chat`, and records progress as a kanban board.
5. **The lead takes over**: reads the playbook, decides who does what, creates tasks on the board, and assigns them to member profiles. Members run in their own gateways.
6. **Phase summaries land as HTML** in `phase-summaries/<slug>.html`. The next phase's members automatically receive all prior summaries as context.

## Quick start

```bash
cd /home/tez/product/research-hub

# 1. Initialize the database (only once)
python3 hub.py init

# 2. Edit config.yaml to match your Hermes profiles
#    Profiles are created/managed via `hermes profile create`, not here.

# 3. Make sure each profile has a running gateway (systemd, or `hermes gateway start`)

# 4. Launch the web app
python3 webapp.py
#    → open http://localhost:5055

# 5. In the browser:
#      - Create a project (name, topic, goal, optional seed paper)
#      - Go to the project page, switch to a phase tab
#      - Click "Start phase" → watch progress update live via HTMX polling
#      - When complete, read the HTML summary inline
```

The web app is the primary interface. There is no separate TUI dashboard anymore.

## Architecture

```
                  ┌─────────────────────────────────┐
                  │         webapp.py (Flask)        │  ← web UI (Jinja + HTMX)
                  └────────────┬────────────────────┘
                               │ reads from
                               ▼
        ┌───────────────────────────────────────────────────┐
        │   hub.py  (data layer: SQLite access, config)      │
        └────────────┬──────────────────────┬────────────────┘
                     │ starts               │ reads
                     ▼                      ▼
   ┌──────────────────────────┐   ┌─────────────────────────────────┐
   │  scripts/launch_run.py   │   │     config/phases/<slug>/        │
   │  (thin launcher)         │   │     ──────────────────────       │
   │  ────────────────        │   │     _lead.md   (lead playbook)   │
   │  • assembles prompt      │   │     _phase.md (metadata)        │
   │  • spawns research_lead  │   │     research_lead.md            │
   │    as background chat    │   │     theorist.md                 │
   │  • records kanban board  │   │     data_scientist.md           │
   │  • tracks round state    │   │     ...                         │
   └───────────┬──────────────┘   └─────────────────────────────────┘
               │ delegates via
               ▼
   ┌────────────────────────────────────────────────────────┐
   │   Hermes kanban board (one per project)                │
   │   ────────────────────────────────                     │
   │   The lead creates tasks here; member gateways         │
   │   pick them up. The board is the visible queue.        │
   └────────────────────────────────────────────────────────┘
```

**hub.py** is the data-access layer — project CRUD, phase status, summary retrieval, config loading. No orchestration logic lives here anymore.

**launch_run.py** is a thin launcher. It composes the lead's prompt (phase metadata + playbook + cross-phase context), spawns the lead as a background `hermes chat`, and exposes `complete` / `round-start` / `round-complete` subcommands for state tracking.

**project_state.py** is a small state machine that reads/writes `.log/project.yaml` per project — tracking runs, rounds, and gate enforcement (`can_run()`).

**The playbooks are where the intelligence lives.** Each phase has 4–6 markdown files. The lead's playbook (`_lead.md`) explains how to orchestrate that phase's pattern; each member's playbook is their brief.

## Orchestration patterns

Each phase declares a `pattern`. The lead treats it as a strong default but may adapt.

| Pattern | How it works | Example phase |
|---------|--------------|---------------|
| **parallel** | All members work independently; lead merges outputs. | Literature review |
| **sequential** | Pipeline A → B → C. Each member takes the previous member's output as input. | Theoretical justification |
| **debate** | Owner proposes → critics critique → owner refines. Often across 2 rounds. | Method development |

A **run** is N rounds. N=1 is steering (tight user control); N>1 is autonomy (lead iterates between rounds, auto-advancing).

## Project layout

```
research-hub/                      # the app
├── webapp.py                      # Flask app (primary UI)
├── hub.py                         # data-access layer
├── scripts/
│   ├── launch_run.py              # thin launcher + round tracking
│   └── project_state.py           # .log/project.yaml state machine
├── config.yaml                    # hub + agents + phases
├── schema.sql                     # SQLite schema
├── config/
│   ├── phases/                    # one folder per phase
│   │   └── 01-literature-review/
│   │       ├── _lead.md
│   │       ├── _phase.md
│   │       ├── research_lead.md
│   │       ├── theorist.md
│   │       └── data_scientist.md
│   ├── souls/                     # role design notes (reference)
│   ├── team/                      # team norms docs (reference)
│   └── projects/                  # project templates (reference)
├── templates/                     # 14 Jinja templates
└── static/
    └── style.css                  # vivid indigo/violet design system
```

Project **data** lives separately, under the workspace dir configured in `config.yaml` (default `~/research`):

```
~/research/
├── hub.db                                                     # SQLite state
└── projects/
    └── project-003-invariant_preserving_.../
        ├── .log/project.yaml                                  # run/round state
        ├── references/                                        # phase 01 outputs
        ├── ideas/                                             # phase 02 outputs
        ├── draft/theory/                                      # phase 03 outputs
        ├── numerical/                                         # phase 04 outputs
        ├── draft/analysis/                                    # phase 05 outputs
        ├── draft/                                             # phase 06 outputs
        └── phase-summaries/
            ├── 01-literature-review.html
            ├── 02-method-development.html
            └── ...
```

## Configuring agents

Profiles are managed by Hermes (`hermes profile create`). In `config.yaml` you just list them:

```yaml
hub:
  name: "My Research Hub"
  workspace_dir: "~/research"
  max_iterations: 10

agents:
- id: "research_lead"
  profile: "research_lead"     # must match `hermes profile list`
  name: "Research Lead"
  role: "domain, framing, writing"
- id: "theorist"
  profile: "theorist"
  name: "Theorist"
  role: "methods, math, rigor"
- id: "data_scientist"
  profile: "data_scientist"
  name: "Data Scientist"
  role: "implementation, data, reproducibility"
- id: "paper_reviewer"
  profile: "paper_reviewer"
  name: "Paper Reviewer"
  role: "independent quality check (on-demand)"
```

Role id == profile name (identity mapping), so role references inside phase playbooks map directly to Hermes profiles. Model and provider are **not** defined here — they live in each profile's own `config.yaml`, and the web UI's Profiles tab reads them live.

Each profile needs a running gateway. For long-term use, a systemd user service per profile is recommended (`hermes gateway start` in foreground, or `systemctl --user enable hermes-gateway@<profile>`).

## Defining phases

```yaml
phases:
- slug: "01-literature-review"
  name: "Literature Review"
  description: "Survey and organize relevant literature"
  pattern: parallel
  gated_by: []                          # empty = runnable anytime
  folder: "references/"                 # outputs land here
  members: [research_lead, theorist, data_scientist]
- slug: "02-method-development"
  name: "Method Development"
  description: "Design and specify the proposed method"
  pattern: debate
  gated_by: ["01-literature-review"]    # waits for phase 01 to complete
  folder: "ideas/"
  members: [theorist, research_lead, data_scientist]   # first = primary contributor
```

What's declared here is **metadata**, not a script. The research lead reads it as guidance and orchestrates accordingly. To add a new phase: drop a folder in `config/phases/`, add the entry to `config.yaml`, and write the playbook files.

## Writing playbooks

Each `config/phases/<slug>/` folder should contain:

- **`_phase.md`** — phase-level metadata (pattern, expected outputs, completion criteria). Read by the launcher.
- **`_lead.md`** — the lead's playbook. Tells the lead how to orchestrate *this* pattern, how to decide round count, how to brief members, what to do between rounds.
- **`<role>.md`** — one per member role. The brief each member receives for this phase.

Playbooks should be **generic and portable** — no project-specific content. They describe *how the team works in this phase*, not what a specific project should conclude. **Honesty is a first-class value** in every playbook: negative results must be surfaced, and claims must match evidence.

## Key design decisions

- **One run per project at a time.** Different projects can run in parallel.
- **Phases are gates.** `gated_by` is enforced — a phase can't start until its dependencies complete.
- **The lead is autonomous within a phase.** It decides task breakdown, member assignment, and round count by reading project state.
- **Cross-phase context is automatic.** All members in phase N receive links to all completed phase summaries from phases 1…N−1.
- **Phase summaries are HTML.** One file per phase at `phase-summaries/<slug>.html`. Rendered inline in the web UI.
- **Kanban is the visible queue.** The lead creates tasks; member gateways consume them. Per-project board scope via the `HERMES_KANBAN_BOARD` environment variable.
- **App/data split.** Code lives in `research-hub/`; project data lives under `~/research/`. Commits never contain runtime data.

## Tech stack

- **Flask + Jinja + HTMX** — no JS framework; the web UI polls phase progress at ~1 Hz and swaps panels server-side.
- **SQLite** per project for interaction data (runs, tasks, rounds).
- **ruamel.yaml** for config parsing.
- **Hermes Agent** for profiles, gateways, kanban, and chat — the Hub speaks to Hermes via the `hermes` CLI.

## Requirements

- Python 3.10+
- Hermes Agent installed and on PATH
- 3–4 Hermes profiles already created
- A gateway running per profile (systemd recommended)
- Flask, ruamel.yaml (see `requirements.txt` if present)

## License

Private project.
