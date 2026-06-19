# Research Hub

A lightweight, SQLite-backed workflow orchestrator for multi-agent research projects using Hermes profiles.

## Core Idea

You define **3–4 Hermes profiles** in `config.yaml`. The Hub manages projects as workflows where tasks flow between these agents across iterations, with per-project folders for their workspaces.

## Quick Start

```bash
cd /home/tez/product/research-hub

# 1. Initialize the database
python3 hub.py init

# 2. Edit config.yaml to match your Hermes profiles
#    (You create/manage profiles via `hermes profile create`, not here)

# 3. Create a project
python3 hub.py create "My Project" "Exploring X" "Prove theorem Y"

# 4. Check status
python3 hub.py status 1

# 5. Launch interactive dashboard
python3 dashboard.py
```

## File Layout

```
research-hub/
├── config.yaml          # Your agent profiles & workflow stages
├── hub.db               # SQLite state (projects, tasks, iterations)
├── hub.py               # Core orchestrator (CLI)
├── dashboard.py         # Interactive TUI for monitoring
├── schema.sql           # DB schema
├── projects/            # Per-project agent workspaces
│   └── project-001-my_project/
│       ├── stage-00-ideation/
│       ├── stage-01-methodology/
│       └── ...
└── logs/
```

## Configuring Agents

In `config.yaml`, list the Hermes profiles you want to use. Example:

```yaml
agents:
  - id: "research-lead"
    profile: "consultant"      # Must match `hermes profile list`
    name: "Research Lead"
    role: "paper_drafts, lit_survey"
    model: "kimi-k2.6"

  - id: "method-dev"
    profile: "method-dev"
    name: "Method Developer"
    role: "math_proofs"
    model: "claude-sonnet-4"
```

You can have **3 or 4 agents** — the hub adapts.

## Workflow Stages

Define how tasks flow between agents:

```yaml
workflows:
  default:
    - stage: "ideation"
      agent: "research-lead"
    - stage: "methodology"
      agent: "method-dev"
      depends_on: ["ideation"]
    - stage: "implementation"
      agent: "coder"
      depends_on: ["methodology"]
```

Stages run in order. A stage only starts once its `depends_on` stages complete.

## Commands

| Command | Description |
|---------|-------------|
| `hub.py init` | Create SQLite database |
| `hub.py create <name> [desc] [goal]` | New project |
| `hub.py list` | Show all projects |
| `hub.py status <id>` | Project task board |
| `hub.py advance <id>` | Check ready tasks |
| `hub.py step <id>` | Dispatch next ready task |
| `hub.py summary <id>` | Text summary |
| `dashboard.py` | Interactive TUI |

## Next Steps

The current scaffold handles project creation, task tracking, and folder management. The actual **agent dispatch** (`hermes run --profile <name> ...`) is stubbed in `hub.py:run_step()`. You can wire it to Hermes cron jobs, `delegate_task`, or manual runs.
