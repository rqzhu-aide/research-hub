---
sidebar_position: 4
title: "Method Branches"
---

# Method Branches

When a phase is **method-bound** (Phases 3, 4, 5 with a selected method), its output is routed into a per-method branch directory. This keeps each method's artifacts isolated and accumulates a complete history per method.

## Branch path structure

```
branches/<stable_id>/
├── evaluations/run/       ← Phase 3 output for this method
│   ├── 01/
│   ├── 02/
│   └── 04/
└── draft/sections/run/    ← Phase 4 output for this method
    └── 01/
```

For example, `spectral-graph-coupling`:
```
branches/spectral-graph-coupling/
├── evaluations/run/
│   ├── 01/   ← Run 1 (approved)
│   ├── 02/   ← Run 2
│   ├── 03/   ← Run 3 (failed launch)
│   └── 04/   ← Run 4 (rerun with audit/fix/extend)
└── draft/sections/run/
    └── 01/   ← Phase 4 Run 1
```

## Why branches?

Without branching, all methods' Phase 3/4/5 outputs would pile into the same `evaluations/run/` directory, making it impossible to tell which results belong to which method. Branches solve this:

- Each method gets its own clean run history
- A future Phase 4 run for method X reads only from method X's branch
- Multiple methods can be developed in parallel without collision

## How method binding works

When you launch a Phase 3/4/5 run, the launcher freezes the exact method identity (stable_id + version + provenance) into the run manifest. This identity determines the output path for the entire run. The method is **sealed** — it cannot change mid-run.

The method identity is recorded in the manifest's `method_selection` field:

```json
"method_selection": {
  "kind": "method",
  "stable_id": "spectral-graph-coupling",
  "version": "v1",
  "source": "approved_phase_02_selection",
  "source_phase": "02-method-development",
  "source_run_id": "f14ad9b2-a9c3-409c-a45c-30027df11377"
}
```

## Phase 2 is not method-bound

Phase 2 (Method Development) proposes methods — it doesn't operate on a single selected method. Its output stays at the flat `ideas/` path, shared across all methods. Only Phases 3, 4, and 5 are method-bound.

## Migrating legacy flat runs

Older runs created before method-branching may live at flat paths (`evaluations/run/01/` instead of `branches/<method>/evaluations/run/01/`). These can be migrated into the branch structure, rewriting all path references in sealed manifests, decision records, and summaries. The migration script at `migrate_to_branches.py` handles this.
