---
sidebar_position: 2
title: "Installation"
slug: /install
---

# Installation

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | 3.11+ recommended |
| Hermes Agent | latest | The `hermes` command must be on `PATH` |

You also need a **Hermes profile** for each research role (research lead, theorist, data scientist, paper reviewer). Create these via Hermes before configuring Research Hub.

## Setup

```bash
git clone https://github.com/rqzhu-aide/research-hub.git
cd research-hub
./setup.sh
```

`setup.sh`:
1. Creates a Python virtual environment (`.venv/`)
2. Installs the `research-hub` package (editable mode)
3. Initializes the hub database
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

## Configure

Edit `config.yaml`:

```yaml
hub:
  name: "My Research Hub"
  workspace_dir: "~/research"
  run_timeout_minutes: 120
  allow_unattended_tools: true

agents:
- id: "research_lead"
  profile: "research_lead"      # your Hermes profile name
  name: "Research Lead"
  role: "domain, framing, writing"

- id: "theorist"
  profile: "theory-profile"     # must exist in Hermes
  name: "Theorist"
  role: "methods, mathematics, rigor"

- id: "data_scientist"
  profile: "data-profile"
  name: "Data Scientist"
  role: "computational, algorithms, implementation"

- id: "paper_reviewer"
  profile: "reviewer-profile"   # must be independent from above
  name: "Paper Reviewer"
  role: "independent audit"
```

Set:
1. **`hub.workspace_dir`** — where project files are stored (defaults to `~/research`)
2. **`agents`** — map each role ID to a Hermes profile you have created
3. **`hub.name`** — your hub's display name

:::note
The `paper_reviewer` profile **must be independent** from the contributing roles. Research Hub validates this at startup.
:::

## Run

```bash
.venv/bin/python webapp.py
```

Open [http://127.0.0.1:5055](http://127.0.0.1:5055).

## Verify

1. Check that Hermes profiles are detected: open **Profiles** in the Web UI
2. Optionally install recommended skills (stat-paper-writing, stat-paper-reviewer)
3. Create a test project and verify the phase tabs appear

## Troubleshooting

- **`hermes` not on PATH**: ensure Hermes Agent is installed and the `hermes` command is available in your shell
- **Profile not found**: the `profile` name in `config.yaml` must exactly match a Hermes profile you created
- **Port already in use**: set `RESEARCH_HUB_PORT` environment variable to use a different port
