---
sidebar_position: 1
title: "Setup Guide"
slug: /setup
---

# Setup Guide

This guide walks through everything you need to get Research Hub running: installing Hermes Agent, creating role profiles, cloning the repo, and launching the web UI.

## Prerequisites

### 1. Install Hermes Agent

Research Hub runs research agents through Hermes. If you don't have it:

```bash
# Linux / macOS / WSL2
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# Windows (PowerShell)
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```

Or [download the desktop installer](https://hermes-agent.nousresearch.com).

Verify it's on your PATH:

```bash
hermes --version
```

See the full [Hermes installation guide](https://hermes-agent.nousresearch.com/docs) for details.

### 2. Python

Research Hub requires Python 3.10+ (3.11+ recommended):

```bash
python3 --version
```

### 3. A model provider

Each Hermes profile needs a model provider. You can use:
- **Nous Portal** — one OAuth covers a model plus web search, image generation, TTS, and browser
- **OpenRouter** — access hundreds of models with one API key
- **OpenAI, Anthropic, or any OpenAI-compatible endpoint**

Configure the provider in each profile's own settings.

---

## Step 1: Create Hermes profiles for each role

Research Hub uses **four specialized research roles**, each backed by a separate Hermes profile. Create these before configuring Research Hub.

### Why separate profiles?

Each role needs its own persistent memory, skill set, and conversation context. The **paper reviewer** especially must be independent — it audits work produced by the other roles, so it cannot share context with them.

### Create the profiles

```bash
# Create four profiles
hermes profile create research_lead
hermes profile create theorist
hermes profile create data_scientist
hermes profile create paper_reviewer
```

### Configure each profile

For each profile, set:
1. **A model provider** — via `hermes setup` or by editing the profile's config
2. **The recommended skills** (optional, Research Hub can install these later):
   - `research_lead`, `theorist`, `data_scientist`: install `stat-paper-writing`
   - `paper_reviewer`: install `stat-paper-reviewer`

:::tip
Run `hermes setup --portal` for the fastest path — one OAuth flow covers a model plus all Tool Gateway tools.
:::

:::warning Independence requirement
The `paper_reviewer` profile **must not** be the same profile as any of `research_lead`, `theorist`, or `data_scientist`. Research Hub validates this at startup and will refuse to run if they overlap.
:::

---

## Step 2: Clone and install Research Hub

```bash
git clone https://github.com/rqzhu-aide/research-hub.git
cd research-hub
./setup.sh
```

### What `setup.sh` does

1. Creates a Python virtual environment at `.venv/`
2. Installs the `research-hub` package (editable mode)
3. Initializes the hub database (`hub.db`)
4. Validates the configuration
5. Checks that `hermes` is on `PATH`

<details>
<summary>Manual setup (if you prefer)</summary>

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python hub.py init
```

</details>

---

## Step 3: Configure Research Hub

Edit `config.yaml`:

```yaml
hub:
  name: "My Research Hub"
  workspace_dir: "~/research"        # where projects are stored
  run_timeout_minutes: 240            # max runtime per phase run
  allow_unattended_tools: true        # required for background launches

agents:
  # Map each role to the Hermes profile you created
  - id: "research_lead"
    profile: "research_lead"          # must match a Hermes profile name
    name: "Research Lead"
    role: "domain, framing, writing"

  - id: "theorist"
    profile: "theorist"
    name: "Theorist"
    role: "methods, mathematics, rigor"

  - id: "data_scientist"
    profile: "data_scientist"
    name: "Data Scientist"
    role: "computational, algorithms, implementation"

  - id: "paper_reviewer"
    profile: "paper_reviewer"         # must be independent from above
    name: "Paper Reviewer"
    role: "independent audit"
```

### Key settings

| Setting | What it does | Default |
|---------|-------------|---------|
| `hub.workspace_dir` | Where project files are stored | `~/research` |
| `hub.run_timeout_minutes` | Maximum runtime before force-stop | `240` |
| `hub.allow_unattended_tools` | Lets background Hermes runs use tools without prompts | `true` |
| `agents[].profile` | The Hermes profile name for each role | — |

The `id` field is a stable identifier used by phase configs. The `profile` field is the Hermes profile name — they don't need to match, but they often do.

---

## Step 4: Launch the web UI

```bash
.venv/bin/python webapp.py
```

Open [http://127.0.0.1:5055](http://127.0.0.1:5055).

### Verify your setup

1. **Check profiles**: open the **Profiles** page in the web UI — all four roles should show as connected
2. **Install skills** (optional): each role page has an **Install recommended skill** button
3. **Create a test project**: verify the five phase tabs appear

---

## Where files live

After setup, your filesystem looks like:

```
~/research/                          ← hub.workspace_dir
└── projects/
    ├── .research-hub-control/       ← internal state (don't edit manually)
    │   └── <project-slug>/
    │       ├── project.yaml         ← run state
    │       └── runs/                ← sealed run artifacts
    └── <project-slug>/              ← agent-writable workspace
        ├── setting.md               ← research brief
        ├── references/              ← Phase 1 output
        ├── ideas/                   ← Phase 2 output
        ├── branches/<method>/       ← Phase 3/4/5 output (per-method)
        │   ├── evaluations/         ← Phase 3
        │   ├── draft/sections/      ← Phase 4
        │   └── draft/revised/       ← Phase 5
```

The Research Hub code lives wherever you cloned it (e.g., `~/product/research-hub/`) — separate from the workspace.

---

## Troubleshooting

### `hermes` not on PATH
Ensure Hermes Agent is installed. If it's installed but not found, check your shell's PATH or restart your terminal.

### Profile not found
The `profile` name in `config.yaml` must exactly match a Hermes profile you created. Run `hermes profile list` to see available profiles.

### Port already in use
Set `RESEARCH_HUB_PORT` to use a different port:
```bash
RESEARCH_HUB_PORT=5056 .venv/bin/python webapp.py
```

### Reviewer profile overlap
If you see "paper_reviewer must use an independent profile", you've mapped the reviewer to the same Hermes profile as another role. Create a separate profile for the reviewer.

---

## Next steps

- [Creating a Project](./project-setup) — write a research brief and set goals
- [Pipeline Overview](./workflow/pipeline) — understand the 5-phase workflow
