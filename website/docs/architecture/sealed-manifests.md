---
sidebar_position: 3
title: "Sealed Manifests"
---

# Sealed Manifests

The sealed manifest is the cryptographic anchor that makes Research Hub runs reproducible and tamper-evident.

## What the manifest records

```json
{
  "schema_version": 2,
  "project_dir": "/home/user/research/projects/my-project",
  "phase_slug": "03-idea-evaluation",
  "run_id": "1539c04e-131a-4ff8-89ac-0984e15d6730",
  "run_number": 4,
  "rounds_requested": "2",
  "phase": {
    "slug": "03-idea-evaluation",
    "folder": "evaluations/",
    "pattern": "debate"
  },
  "output_root": "/home/user/research/projects/my-project/branches/spectral-graph-coupling/evaluations/run/04",
  "summary_path": "/home/user/research/projects/my-project/phase-summaries/03-idea-evaluation/1539c04e....html",
  "prompt_path": ".../runs/03-idea-evaluation/1539c04e....prompt.md",
  "prompt_sha256": "a1b2c3...",
  "snapshots": {
    "playbooks": {
      "path": "...context/playbooks/_lead.md",
      "sha256": "d4e5f6..."
    },
    "summaries": {
      "path": "...context/summaries/02-method-development-f14ad9b2....html",
      "sha256": "789abc..."
    }
  },
  "method_selection": {
    "stable_id": "spectral-graph-coupling",
    "version": "v1"
  },
  "phase_plan_version": "653242b0...",
  "prerequisite_report_version": "e0a5daa1..."
}
```

## Verification points

### At launch
- Every frozen input file exists and its hash matches the manifest
- The output root matches the phase plan (including branch prefix for method-bound runs)
- The summary path matches the immutable run identity
- The prompt hash matches the sealed prompt

### During the run
- The worker reads only from frozen `.context/` copies
- Round directives are written to the manifest-declared output root

### At submission
- Output artifacts exist at the expected paths
- The summary is written to the manifest-declared summary path

### At approval
- The exact summary hash is recorded in the decision record
- Downstream runs that consume this summary verify they got the same hash

## Why hashes?

Without hash verification, a run could be silently affected by:
- A playbook edited after launch
- A prior summary modified after approval
- A context file swapped mid-run

The sealing mechanism makes all of these detectable. If any input changes, verification fails immediately.

## Reproducibility

Because every input is frozen and hashed, a run is fully reproducible:
- You know exactly which playbook version was used
- You know exactly which approved summary was consumed
- You can re-verify integrity months or years later
- Decision records provide a provenance chain for every approved result
