# Situation 18: Two Projects, Shared Hermes Profiles

## Scenario

The researcher creates a second hub project (`project-005`) alongside
`project-004`. Both use the same four Hermes profiles (`research_lead`,
`theorist`, `data_scientist`, `paper_reviewer` from `config.yaml`). They run
P1 on project-004 and P3 on project-005 **at the same time**, and later
install recommended skills for the shared theorist profile from project-004's
Profiles page while project-005 has a run in flight. What isolates the two
projects — and what leaks?

## Step-by-step evaluation

### Step 1: Concurrent runs on two projects

- **System behavior**: the single-active-run rule is **per project**
  (`project.lock` inside each project's own control directory). Two projects
  can genuinely run in parallel.
- **Task routing**: each project gets its own kanban board,
  `rhub-<workspace-hash-8>-p<project_id>` (`launch_run.py:347-350`,
  `_workspace_board_slug`), created on demand (`_ensure_board`, `:240-278`).
  Tasks from project-004 and project-005 never share a board, so results
  return to the correct run.
- **Registry**: `hub.db` access uses WAL + `busy_timeout`
  (`hub.py:609-614`) — safe under concurrent readers/writers.
- **Smooth?** ✅ Run isolation is real: separate locks, separate boards,
  separate control dirs, separate manifests.

### Step 2: Both runs want the same profile at once

- **System behavior**: the profiles are **shared across projects** — both
  runs dispatch tasks naming e.g. `theorist`. Hermes serializes task
  execution per profile; the second project's task waits.
- **Consequence**: throughput contention, not correctness. A 240-minute
  project-004 run can starve project-005's launch of agents for hours. There
  is no scheduling, priority, or even a UI hint that the profile is busy on
  another project.
- **Smooth?** ⚠️ Correct but opaque — project-005's run looks "stuck" with
  no visible reason.

### Step 3: Agent memory crosses projects

- **System behavior**: runs do **not** write profile memory or skills (skills
  are installed explicitly from the Profiles page and fingerprint-validated
  at launch, `launch_run.py:882-893`, `:1351-1367`). But the *agents
  themselves* have persistent per-profile memory across sessions — a theorist
  that worked on project-004's Langevin method carries those memories into
  project-005's tasks.
- **Consequence**: the hub's carefully frozen per-run context
  (`_trusted_context`, manifest snapshots) is bypassed by an uncontrolled
  channel: the agent's own accumulated memory. Project-005's theorist may
  cite project-004's results as if they were its own project's prior work.
- **Smooth?** ❌ Cross-project contamination is possible through the one
  channel the hub does not control.

### Step 4: Skill install mid-run on the other project

- **System behavior**: skill fingerprints are frozen into each run's manifest
  at launch (`launch_run.py:882-893`) and re-checked while inputs freeze
  (`:1357-1367`, "The phase instructions changed while the run inputs were
  being frozen"). Manifest validation later is against the frozen snapshot
  (`launch_manifest.py:149-162`, `:283-349`) — not the live profile.
- **Consequence**: installing skills from project-004 while project-005's run
  is in flight does **not** break the in-flight run; its manifest already
  froze what it needed. The next project-005 launch sees the new fingerprint.
- **Smooth?** ✅ Yes — frozen snapshots do their job.

## Issues identified

### 🟡 Issue A: Agent memory is an uncontrolled cross-project channel

**Severity: Medium.** The hub freezes per-run context precisely, but the
shared profiles' persistent memories accumulate across projects and runs.
Two projects on related topics will slowly contaminate each other's agents;
two on unrelated topics get noise. There is no per-project memory namespacing
or guidance to agents about which project a memory belongs to.

### 🟡 Issue B: Profile contention is invisible

**Severity: Low-Medium.** When two projects' runs compete for the same
profile, the losing run simply waits — no status, no queue position, no
"theorist is busy on project-004" hint in the UI.

### 🟢 Observation: run-level isolation is solid

Per-project locks, per-project kanban boards
(`launch_run.py:347-350`), frozen skill fingerprints, WAL+busy-timeout on the
registry — everything the hub controls is correctly isolated.

## Space summary

| Component | Size |
|---|---|
| Project-004 run (P1) | ~0.5 MB |
| Project-005 run (P3) | ~1.0 MB |
| Shared profile state (skills) | ~0.1 MB |
| **Total added** | **~1.6 MB** |

## Verdict

✅ **Everything the hub owns is isolated** — runs, boards, locks, manifests,
skill fingerprints.

⚠️ **The one thing it doesn't own — the agents' persistent memory — is a
wide-open cross-project channel**, and profile contention is invisible to the
user. Multi-project use works, but "one profile family per project" is the
safer operating mode today.
