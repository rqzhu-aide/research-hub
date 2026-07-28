---
title: "Set Up Hermes Profiles"
slug: /profile-setup
---

# Set Up Hermes Profiles

Research Hub assigns each scientific role to an existing Hermes profile. Hermes
owns the profile's model, provider credentials, tools, profile `SOUL.md`,
persistent memory, sessions, and skills. Research Hub owns the research
workflow and the additional role and phase instructions supplied for a run.

Create and configure the profiles before launching a phase.

## Recommended profile layout

Use one named profile for each scientific role:

| Research Hub role | Default profile name | Reason for separation |
|---|---|---|
| Research Lead | `research_lead` | Framing, synthesis, and manuscript work |
| Theorist | `theorist` | Mathematical development and proof-focused memory |
| Data Analyst | `data_scientist` | Implementation, computation, and empirical work |
| Paper Reviewer | `paper_reviewer` | Context-separated manuscript assessment |

Four separate profiles are recommended even when the same model provider is
used. The Paper Reviewer must not share a profile with any author-side role.
Research Hub enforces that separation.

If you use a Hermes profile to operate the Web UI on your behalf, create a fifth
profile such as `hub_operator`. Do not map it to a scientific role. See
[Direct and Remote Operation](./operation-modes).

## 1. Create the profiles

```bash
hermes profile create research_lead
hermes profile create theorist
hermes profile create data_scientist
hermes profile create paper_reviewer
```

The names above match the shipped Research Hub configuration. Other canonical
Hermes profile names are allowed and can be assigned later in the Web UI.

List the profiles visible to Hermes:

```bash
hermes profile list
```

## 2. Configure each profile

Configure the model provider and tools in each profile. For example:

```bash
hermes -p research_lead setup
hermes -p theorist setup
hermes -p data_scientist setup
hermes -p paper_reviewer setup
```

The exact setup flow depends on the provider and Hermes version. Use the
[Hermes profiles documentation](https://hermes-agent.nousresearch.com/docs/user-guide/profiles/)
for current commands and configuration options.

For each profile, verify:

- a working default model and provider;
- credentials stored in the Hermes profile environment rather than Research
  Hub project files;
- only the tools appropriate for that role;
- local filesystem and computation access needed for the intended phases;
- gateway and task support required by Research Hub.

## 3. Understand the two instruction sources

A mapped role receives instructions from both systems:

1. The Hermes profile can have its own `SOUL.md`, memory, tools, and skills.
2. Research Hub adds its standing role instructions, team standards,
   phase-specific playbook, user direction, and frozen project evidence.

Research Hub freezes and hashes its own role and phase instructions for a run.
It does not copy the Hermes profile's `SOUL.md` or persistent memory into the
run manifest. Keep essential scientific facts in the project brief and
artifacts rather than only in profile memory.

See [Agent Instructions, Memory, and Skills](./team-resources) for the complete
context model.

## 4. Map profiles in Research Hub

Start Research Hub, open **Agent profiles**, and review each role card.

For each role:

1. Select the intended existing Hermes profile.
2. Confirm the displayed model and provider are the ones you expect.
3. Inspect whether profile memory is present.
4. Review the recommended skill status.
5. Install or replace the bundled skill only when you want that exact copy.

Reassigning a role affects future runs. It does not move memories or skills
between profiles.

The same mapping can also be declared in `config.yaml`:

```yaml
agents:
- id: "research_lead"
  profile: "research_lead"

- id: "theorist"
  profile: "theorist"

- id: "data_scientist"
  profile: "data_scientist"

- id: "paper_reviewer"
  profile: "paper_reviewer"
```

Use the Web UI for normal profile reassignment. See
[Configuration Reference](./reference/config) for the full fields.

## Profile memory

Hermes profile memory persists across sessions and phases. On the **Agent
profiles** page, Research Hub can display `memories/MEMORY.md` when it exists.
Research Hub does not edit that file.

Use memory for durable role-level preferences and generally applicable
experience. Do not rely on it as the only record of:

- a project assumption;
- a dataset version;
- a theorem condition;
- an experimental result;
- a user decision;
- a manuscript claim.

Those materials belong in the project brief, branch artifacts, or run records
where they can be inspected and preserved with the work.

## Recommended skills

The application bundles pinned copies of:

| Profiles | Skill |
|---|---|
| Research Lead, Theorist, Data Analyst | `stat-paper-writing` |
| Paper Reviewer | `stat-paper-reviewer` |

The **Agent profiles** page performs a read-only status check before offering an
action.

| Status | Meaning |
|---|---|
| Missing | The bundled skill is not installed in this profile |
| Current | The installed content matches the bundled digest |
| Modified or conflicting | A different copy exists and must not be overwritten silently |
| Profile unavailable | The profile cannot be inspected or has not been created |

Installation always requires an explicit user action. Replacing a different
copy requires confirmation, and Research Hub preserves the prior copy as a
backup.

An installed skill is not necessarily preloaded in every phase. The current
automatic preload policy is described in
[Agent Instructions, Memory, and Skills](./team-resources).

## Profile locations

Research Hub resolves the Hermes profile root using this order:

1. `RESEARCH_HUB_HERMES_ROOT`, when explicitly set;
2. `HERMES_HOME`, including a named-profile location;
3. the platform default.

| Platform | Default Hermes root used by Research Hub |
|---|---|
| Linux and other POSIX systems | `~/.hermes` |
| Native Windows | `%LOCALAPPDATA%\hermes` |

Named profiles are stored under `<Hermes root>/profiles/<name>`. The default
profile uses the root itself.

Run Research Hub and Hermes in the same operating-system environment. A native
Windows Hermes installation and a WSL2 Hermes installation use different
profile roots and should not be treated as one shared profile collection.

## Changes during an active run

Do not reassign profiles, replace skills, or materially change profile tools
while a run is active.

Research Hub records the selected profile mapping and applicable bundled-skill
state when a run is prepared. It rechecks a skill immediately before explicit
preload. A changed skill can stop dispatch. Hermes-managed memory and profile
configuration remain external live state, so unnecessary mid-run changes also
weaken reproducibility.

## Readiness checklist

Before the first real run:

1. Every participating role maps to an existing profile.
2. The Paper Reviewer has a separate profile.
3. Each profile can complete a simple Hermes chat.
4. The required model provider and tools work.
5. Profile memory contains no inappropriate project secrets or stale claims.
6. Recommended skills have the status you intend.
7. A disposable Research Hub run completes and produces inspectable artifacts.

For platform-specific profile and path differences, see
[Operating Systems](./operating-systems).
