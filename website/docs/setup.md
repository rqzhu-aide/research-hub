---
sidebar_position: 1
title: "Install Research Hub"
slug: /setup
---

# Install Research Hub

The supported installation path targets Linux. Before installing, review:

- [System Requirements](./system-requirements);
- [Operating Systems](./operating-systems);
- [Set Up Hermes Profiles](./profile-setup).

## Before using research data

The Web UI runs locally, but the configured models and tools may not. Research
Hub sends phase prompts and the assembled run context through Hermes to the
provider configured for each profile. Agent tools may contact other external
services.

Review provider and tool data-handling policies before including confidential,
clinical, genomic, or otherwise sensitive material. Do not put credentials or
secrets in project briefs, run instructions, logs, reports, or manuscripts.

## 1. Install Hermes Agent

On Linux:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

Open a new terminal if necessary, then verify:

```bash
hermes --version
```

For provider configuration and current Hermes installation options, use the
[Hermes documentation](https://hermes-agent.nousresearch.com/docs/).

## 2. Download and install Research Hub

```bash
git clone https://github.com/rqzhu-aide/research-hub.git
cd research-hub
./setup.sh
```

The setup script:

1. creates or reuses `.venv`;
2. installs Research Hub and its development test dependency;
3. initializes or migrates the project registry;
4. validates `config.yaml`;
5. reports whether `hermes` is available on `PATH`.

Choose a specific Python interpreter when needed:

```bash
PYTHON=python3.12 ./setup.sh
```

Research Hub must run from this checkout. Keep the checkout available after
installation.

## 3. Configure the Hermes profiles

Create and configure the four scientific profiles, then map them on the
**Agent profiles** page. The Paper Reviewer must use a profile separate from
the three author-side roles.

The complete procedure, memory model, profile paths, and recommended-skill
controls are in [Set Up Hermes Profiles](./profile-setup).

## 4. Start the Web UI

From the Research Hub checkout:

```bash
.venv/bin/python webapp.py
```

Open [http://127.0.0.1:5055](http://127.0.0.1:5055).

The server is intentionally local. Do not expose port 5055 or bind Research Hub
to a public or LAN address. If you want to issue commands from another device,
use the same-host operator pattern described in
[Direct and Remote Operation](./operation-modes).

## 5. Choose the workspace

The shipped configuration stores projects under `~/research`.

To use another location:

1. open **Settings**;
2. enter the workspace directory;
3. save the setting;
4. restart Research Hub.

Use a local writable filesystem and back up the entire workspace when no run is
active. See [Files and Research Records](./reference/files-and-records).

## 6. Verify the installation

Before starting a real project:

1. Open **Agent profiles** and confirm all four role mappings.
2. Confirm the model and provider displayed for each profile.
3. Review profile memory and recommended-skill status.
4. Create a disposable project with a short brief.
5. Open each phase and inspect its run plan.
6. Launch a short test run only after the displayed role, inputs, and settings
   are correct.
7. Inspect progress, the final summary, artifacts, and log.
8. Test a rerun and cancellation before relying on a long computation.

Starting one phase never starts another. You choose every run and rerun.

## Update Research Hub

Update only when no run is active. Stop the Web UI and back up the configured
workspace first.

From a clean source checkout:

```bash
git status --short
git pull --ff-only origin main
./setup.sh
```

If `git status --short` lists local changes, preserve or resolve them before
pulling. Do not overwrite workflow or documentation changes you intend to keep.

Running `setup.sh` again updates the Python environment, applies available
database migrations, and validates the current configuration. Restart the Web
UI after it completes.

## Common problems

### `hermes` is not found

Open a new terminal and confirm:

```bash
hermes --version
```

If the command is still unavailable, review the current Hermes installation
instructions and your shell `PATH`.

### A profile is missing

```bash
hermes profile list
```

Create and configure the missing profile, or assign another existing profile on
the **Agent profiles** page.

### The reviewer profile is rejected

The Paper Reviewer is using a profile already assigned to an author-side role.
Assign a separate profile.

### Port 5055 is already in use

Choose another local port:

```bash
RESEARCH_HUB_PORT=5056 .venv/bin/python webapp.py
```

The address must remain loopback-only.

### A run cannot use tools

Web-launched background runs require `hub.allow_unattended_tools: true`. Review
the implications in [System Requirements](./system-requirements) before
enabling it.

## Next steps

- [Creating a Project](./project-setup)
- [Roles and Team](./roles)
- [Agent Instructions, Memory, and Skills](./team-resources)
- [Direct and Remote Operation](./operation-modes)
- [Research Workflow](./workflow/pipeline)
- [Current Limitations](./known-limitations)
