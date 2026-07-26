---
sidebar_position: 1
title: "Architecture Overview"
---

# Architecture Overview

Research Hub separates **runtime files** (what you need to run it) from **development files** (tests and tooling).

## Repository layout

```text
research-hub/
├── webapp.py                     ← Flask entry point
├── hub.py                        ← Project registry, config loader
├── schema.sql                    ← Hub database schema
├── config.yaml                   ← Main configuration
├── core/                         ← Application package
│   ├── launch_run.py                orchestration facade
│   ├── launch_common.py             constants, paths, helpers
│   ├── launch_process.py            process execution, supervision
│   ├── launch_manifest.py           manifest structure + validation
│   ├── launch_plans.py              plan selection, method binding
│   ├── launch_prompts.py            sealed prompts, task briefs
│   ├── launch_dispatch.py           round tracking, task dispatch
│   ├── launch_supervision.py        reconciliation, cleanup
│   ├── project_state.py             state machine: runs, approvals
│   └── web_phase_data.py            read-only view models for the UI
├── config/                       ← Phase playbooks and team definition
│   ├── phases/                      one directory per phase
│   ├── souls/                       agent personality files
│   └── team/                        charter and norms
├── bundled_skills/               ← Pinned Hermes skills
├── static/                       ← Browser assets
├── templates/                    ← Jinja2 HTML templates
└── tests/                        ← Test suite
```

## Runtime data layout

Runtime data lives under `hub.workspace_dir` (defaults to `~/research`):

```text
~/research/
├── hub.db                           ← project registry (SQLite)
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
        ├── branches/<method>/            method-bound run output
        │   ├── evaluations/run/
        │   └── draft/sections/run/
        ├── references/                   Phase 01 output
        └── ideas/                        Phase 02 output
```

## The two-directory split

Each project has two directories:

1. **Control directory** (`.research-hub-control/<project>/`) — internal state, manifests, prompts, logs. Agents do not write here directly; the system manages it.

2. **Workspace directory** (`<project>/`) — agent-writable. This is where research artifacts (references, ideas, evaluations, drafts) live. Agents read and write here during phase runs.

This separation ensures agents cannot corrupt run control state, and the system can verify agent output against sealed expectations.

## The launch lock

Only one run can be active per project at a time. The project launch lock (`project.lock`) prevents concurrent runs. The lock is held from launch through cleanup — if a worker fails or is cancelled, cleanup must complete before the next run can start.
