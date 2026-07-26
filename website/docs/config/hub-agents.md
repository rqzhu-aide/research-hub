---
sidebar_position: 1
title: "Hub & Agents Configuration"
---

# Hub & Agents Configuration

Research Hub is configured via `config.yaml`. Hermes creates and owns profiles; Research Hub maps stable research role IDs to those profile names.

## Hub settings

```yaml
hub:
  name: "My Research Hub"
  workspace_dir: "~/research"
  run_timeout_minutes: 120
  allow_unattended_tools: true
```

| Field | Description |
|-------|-------------|
| `name` | Display name for your hub |
| `workspace_dir` | Where project files are stored (defaults to `~/research`) |
| `run_timeout_minutes` | Maximum runtime before a run is force-stopped |
| `allow_unattended_tools` | When `true`, background Hermes runs may use tools without interactive confirmation. Required for phase launches (the detached worker has no terminal). |

## Agent mapping

```yaml
agents:
- id: "research_lead"
  profile: "research_lead"
  name: "Research Lead"
  role: "domain, framing, writing"

- id: "theorist"
  profile: "theory-profile"
  name: "Theorist"
  role: "methods, mathematics, rigor"

- id: "data_scientist"
  profile: "data-profile"
  name: "Data Scientist"
  role: "computational, algorithms, implementation"

- id: "paper_reviewer"
  profile: "reviewer-profile"
  name: "Paper Reviewer"
  role: "independent audit"
```

- **`id`** is the stable role identifier referenced by phase members and stage owners
- **`profile`** is the Hermes profile used to execute that role — the two names don't need to match
- Model and provider settings stay in each Hermes profile's own configuration

## Required roles

- `research_lead` — required; coordinates every phase
- `theorist`, `data_scientist` — contributing roles
- `paper_reviewer` — **must use an independent profile** separate from the contributing roles

## Recommended skills

Research Hub ships two pinned Hermes skills:

| Role | Skill |
|------|-------|
| research_lead, theorist, data_scientist | `stat-paper-writing` |
| paper_reviewer | `stat-paper-reviewer` |

Skills are recommendations, not prerequisites. A phase runs even if a skill is absent. The Web UI's **Profiles** page shows skill status and lets you install them.

## Hermes profile location

Hermes profiles live at:
- **POSIX:** `~/.hermes`
- **Windows:** `%LOCALAPPDATA%\hermes`

`RESEARCH_HUB_HERMES_ROOT` can override the root. If `HERMES_HOME` is set, Research Hub derives the same profile root from it.
