---
sidebar_position: 8
title: "Configuration Reference"
slug: /reference/config
---

# Configuration Reference

This page covers the full `config.yaml` schema for advanced configuration.

## Hub settings

```yaml
hub:
  name: "My Research Hub"           # display name
  workspace_dir: "~/research"        # where projects are stored
  run_timeout_minutes: 240           # max runtime per phase run
  allow_unattended_tools: true       # required for background launches
```

| Field | Description | Default |
|-------|-------------|---------|
| `name` | Display name for your hub | — |
| `workspace_dir` | Where project files are stored | `~/research` |
| `run_timeout_minutes` | Maximum runtime before force-stop | `240` |
| `allow_unattended_tools` | Lets background Hermes runs use tools without prompts | `true` |

## Agent mapping

```yaml
agents:
- id: "research_lead"               # stable role identifier
  profile: "research_lead"          # Hermes profile name
  name: "Research Lead"             # display name
  role: "domain, framing, writing"  # human-readable role description

- id: "theorist"
  profile: "theorist"
  name: "Theorist"
  role: "methods, mathematics, rigor"

- id: "data_scientist"
  profile: "data_scientist"
  name: "Data Analyst"
  role: "computational, algorithms, implementation"

- id: "paper_reviewer"
  profile: "paper_reviewer"         # must be independent from above
  name: "Paper Reviewer"
  role: "independent audit"
```

- **`id`** is the stable role identifier referenced by phase configs
- **`profile`** is the Hermes profile name — doesn't need to match `id`
- Model and provider settings stay in each Hermes profile's own configuration

## Phase configuration

### Parallel phase

```yaml
- slug: "02-method-development"
  name: "Method Development"
  short_name: "New Method"
  description: "Brainstorm genuinely new ideas"
  pattern: parallel
  gated_by: ["01-literature-review"]
  folder: "ideas/"
  members: [theorist, research_lead, data_scientist]
  rounds: {min: 2, default: 2, max: 3}
```

### Debate phase (Phase 3)

```yaml
- slug: "03-idea-evaluation"
  name: "Theoretical Development"
  pattern: debate
  gated_by: ["02-method-development"]
  folder: "evaluations/"
  members: [theorist, research_lead, data_scientist]
  rounds: {min: 2, default: 2, max: 3}
  method_binding: true
```

### Parallel phase with run modes (Phase 4)

```yaml
- slug: "04-draft-assembly"
  name: "Implementation & Experiments"
  description: "Implement the method in code, run pre-specified experiments with
    diagnostics, and validate theoretical predictions against measured results"
  pattern: parallel
  method_binding: true
  run_modes:
    plans: ["preliminary", "comprehensive"]
    default: "preliminary"
  gated_by: ["03-idea-evaluation"]
  folder: "draft/sections/"
  members: [research_lead, theorist, data_scientist]
  rounds: {min: 1, default: 2, max: 2}
```

### Sequential phase with run modes (Phase 5)

```yaml
- slug: "05-review-revision"
  name: "Paper Assembly & Review"
  description: "Assemble the paper from theory and experiments, then independent
    paper review and revision into final manuscript"
  pattern: sequential
  method_binding: true
  run_modes:
    plans: ["assembly", "review_revision"]
    default: "assembly"
  gated_by: ["04-draft-assembly"]
  folder: "draft/revised/"
  members: [paper_reviewer, research_lead]
  stages:
  - name: Assemble
    role: research_lead
    description: "Combine theory, experiments, and literature into a coherent
      manuscript with unified notation and consistent claims."
```

## Phase fields

| Field | Description |
|-------|-------------|
| `slug` | Unique phase identifier (used in URLs, paths) |
| `pattern` | `parallel`, `debate`, or `sequential` |
| `gated_by` | Recommended approved prerequisites |
| `folder` | Output directory within the project workspace |
| `members` | Participating role IDs |
| `rounds` | User-selectable round count: `{min, default, max}` |
| `stages` | For sequential phases: ordered list of `{role, name, description}` |
| `run_modes` | User-selectable run variants: `{plans: [...], default: ...}` (Phases 4 & 5) |
| `short_name` | Short tab/sidebar label (e.g. `"Lit Review"`, `"New Method"`) |

## Optional feature declarations

| Feature | Declaration | Effect |
|---------|-------------|--------|
| **Protocol checkpoint** | `protocol_checkpoint: true` | Seals a protocol document before result-stage work |
| **Method binding** | `method_binding: true` | Freezes method identity per run; routes output to branches |
| **Run modes** | `run_modes:` on Phase 04 or 05 | Two user-selectable modes per phase; the second mode is gated by an approved run of the first |

## Prerequisite graph

- **`gated_by`** — recommended approved prerequisites. Missing prerequisites trigger a warning requiring explicit override.
- **`context_from`** — additional approved summaries that are useful but not required.
- The current phase's prior approved result is automatically included on reruns.

## Configuration validation

At startup, Research Hub validates:
- Role and profile identifiers exist and match Hermes profiles
- `research_lead` is present
- `paper_reviewer` uses an independent profile
- Output folders are project-relative and safe
- Round bounds are consistent
- Sequential stage owners are valid
- Prerequisite graph has no cycles
- Optional feature declarations are valid for their phase
- Required playbook files exist
- `run_plan` values in sealed manifests are recognized theory plans or run modes
