---
title: "System Requirements"
slug: /system-requirements
---

# System Requirements

Research Hub is a local Python application that coordinates Hermes Agent
profiles. The Web UI itself is lightweight. The research performed by the
agents may require substantially more memory, storage, computation, software,
or network access.

Check [Operating Systems](./operating-systems) before installation. Linux is
the only currently supported Research Hub platform.

## Required for Research Hub

| Requirement | Current requirement | Why it is needed |
|---|---|---|
| Operating system | Supported Linux environment | The shipped installer and documented commands are Linux-oriented |
| Python | 3.10 or later | Runs the Web UI, project registry, state manager, and launch workers |
| Git | A current command-line installation | Downloads and updates the application |
| Hermes Agent | Installed on `PATH` with the required profile and task commands | Runs the scientific roles and their staged work |
| Web browser | A current browser on the Research Hub host | Opens the loopback Web UI at `127.0.0.1` |
| Model access | A configured provider for every participating Hermes profile | Supplies the model used by each role |
| Writable local storage | Application checkout, project workspace, and Hermes profile directories | Stores configuration, projects, frozen inputs, logs, memories, and skills |

Research Hub must run from an editable installation in its source checkout. The
current Python package does not install the Web UI templates, static assets,
workflow configuration, and launch instructions as a standalone wheel.

## Hermes capabilities

Research Hub uses more than a basic Hermes chat command. The installed Hermes
release must support:

- named profiles;
- profile-specific memory and skills;
- Kanban boards and tasks;
- task creation, inspection, waiting, blocking, and archival;
- workspace attachment and structured command output;
- explicit skill loading for applicable tasks.

The current release does not declare a minimum Hermes version or run a complete
capability probe during setup. Verify the full workflow with a disposable
project after installing or updating Hermes.

Web-launched runs are background jobs. The shipped configuration therefore uses:

```yaml
hub:
  allow_unattended_tools: true
```

This setting does not start a phase automatically. It allows a run that the
user has already launched to use its configured tools without waiting for an
interactive terminal permission prompt that the Web UI cannot display.

## Storage and permissions

Use local, writable storage for:

- the Research Hub checkout;
- the configured `workspace_dir`;
- the Hermes profile root;
- temporary files created by Python and Hermes.

Avoid placing an active workspace on a network share or synchronization service
whose locking, rename, timestamp, or link behavior differs from a local
filesystem. Research Hub relies on file identity, atomic replacement, locks,
and content hashes to preserve run records.

Storage needs depend on the project. Phase 1 can preserve literature records,
Phase 3 can preserve derivations and proof artifacts, Phase 4 can produce code
and large experiment outputs, and Phase 5 can retain multiple manuscript
versions. Back up the entire workspace when no run is active.

## Network and data access

The Research Hub server itself binds only to the local loopback interface.
Network access may still be required by:

- the model provider configured for each profile;
- literature search, browser, repository, or data tools;
- package managers and scientific software installers;
- remote datasets, APIs, or compute services selected for a project.

Review the provider and tool data-handling policies before using confidential,
clinical, genomic, or otherwise sensitive material. Do not place credentials
or secrets in a project brief, run instruction, report, or manuscript.

## Requirements for scientific workloads

Research Hub does not install every language or library an agent may use. A
project may additionally require:

- Python, R, Julia, Lean, or another scientific runtime;
- compilers and system libraries;
- statistical, machine-learning, optimization, or biological software;
- CPU, GPU, memory, and disk appropriate for the requested experiments;
- licensed software, controlled data access, or institutional credentials.

A skill or library reference pack can tell an agent how to use a library. It
does not install that library or verify its runtime. Record important package
versions, environments, seeds, hardware, and external data versions in the
project artifacts.

## Optional operator requirements

Direct use requires only a local browser. Operating Research Hub through a
separate Hermes operator profile additionally requires:

- a dedicated operator profile on the Research Hub host;
- a local browser automation backend or local Chromium sidecar;
- an authorized Hermes messaging gateway if the user will issue commands from
  another device;
- a restricted tool configuration appropriate for the operator.

Research Hub itself must remain loopback-only. See
[Direct and Remote Operation](./operation-modes).

## Documentation contributor requirements

These are not required to run Research Hub:

| Tool | Purpose |
|---|---|
| Node.js 20 or later | Builds the Docusaurus documentation site |
| npm | Installs the locked documentation dependencies |
| pytest | Runs the development test suite |

## Preflight checklist

Before using a real project:

1. Confirm `python3 --version`, `git --version`, and `hermes --version`.
2. Confirm the four scientific Hermes profiles exist and have working model
   configurations.
3. Start Research Hub and open `http://127.0.0.1:5055`.
4. Confirm **Agent profiles** shows the intended mapping and profile state.
5. Create a disposable project and complete a short run.
6. Test progress monitoring, cancellation, completion, and rerun behavior.
7. Inspect the generated summary, artifacts, log, and frozen records.

Continue with [Install Research Hub](./setup) and
[Set Up Hermes Profiles](./profile-setup).
