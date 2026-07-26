---
sidebar_position: 5
title: "Integrity & Sealed Manifests"
---

# Integrity & Sealed Manifests

Research Hub uses cryptographic integrity checks to ensure every run is reproducible and tamper-evident.

## What gets sealed

At launch time, the system freezes and hashes:

1. **Phase playbooks** — `_lead.md`, `_phase.md`, `<role>.md`
2. **Role souls** — `config/souls/<role>.md`
3. **Project brief** — `setting.md`
4. **Prerequisite summaries** — the approved HTML summaries of upstream phases
5. **The phase plan** — rounds, stages, method selection

All of these are copied into an immutable `.context/` directory and recorded in the run manifest with their SHA-256 hashes.

## The run manifest

Every run has a sealed manifest at:
```
.research-hub-control/<project>/runs/<phase>/<run_id>.manifest.json
```

The manifest records:
- `output_root` — where the run writes its output
- `summary_path` — where the summary will be written
- `prompt_path` — the sealed lead prompt
- `prompt_sha256` — hash of the prompt
- `snapshots` — frozen input files with their hashes
- `method_selection` — the sealed method identity (if method-bound)
- `phase_plan_version` — hash of the phase plan

## Hash verification

Research Hub verifies hashes at multiple points:

- **At launch:** frozen inputs are hashed and compared against the manifest
- **During the run:** the worker reads only from the frozen `.context/` copies
- **At submission:** output artifacts are validated against the manifest's expected paths
- **At approval:** the summary hash is recorded so later runs can verify they consumed the exact same content

If any frozen input changes after launch, the manifest verification fails and the run is rejected. This ensures a run cannot be silently affected by mid-flight edits to playbooks or prior summaries.

## Why this matters

Research is adversarial to its own conclusions. A run that silently used a different version of a proof, or read a summary that was edited after approval, produces results that cannot be trusted or reproduced. The sealing mechanism makes every run's exact inputs auditable:

- You can always determine *which version* of a playbook a run used
- You can always determine *which approved summary* a downstream phase consumed
- You can re-verify integrity months later

## Decision records

When a user approves a run, Research Hub writes a decision record (`.decision.json`) capturing:
- The run ID and phase
- The exact summary hash that was approved
- The context inputs that were current at approval time
- The decision timestamp and any user note

This record is itself sealed — it cannot be edited after creation. It serves as the provenance chain for every approved result.
