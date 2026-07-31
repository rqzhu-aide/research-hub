# Context Reduction for Research Hub Agent Runs

**Date:** 2026-07-30
**Topic:** Frozen context size in Phase 3+ runs — analysis and reduction ideas

## Current State

A new Phase 3 ("Theory & Proofs") run freezes ~193 KB of context that gets re-sent to every agent in every round. For a 3-agent × 3-round run, that's ~193 KB × 3 agents × 3 rounds ≈ 1.7 MB of repeated context before any new round output accumulates.

### Breakdown of frozen context (~193 KB)

| Component | Size | Notes |
|-----------|------|-------|
| Team charter + norms | 16 KB | Boilerplate, identical every run |
| Agent souls (3 roles) | 6 KB | Thin role definitions |
| Phase playbooks (4 files) | 18 KB | Phase instructions × 3 roles + lead playbook |
| P1 Lit Review summary | 20 KB | All 3 roles' findings |
| P1 Lit Review decision | 14 KB | Structured decision JSON |
| P2 Method Dev summary | 29 KB | Full 7-method catalog |
| P2 Method Dev decision | 23 KB | Structured decision JSON |
| P3 Run 1 summary | 39 KB | Approved baseline (full HTML) |
| P3 Run 1 decision | 19 KB | Structured decision JSON |
| Project setting | 4 KB | `setting.md` |
| Method definition | 2 KB | Selected method's `.md` file |

### Additional per-round task (~17 KB each)

Each agent receives a task prompt with the full frozen context plus:
- Round-specific directives
- Accumulated prior-round output (grows each round)

## Key Problems

1. **Team boilerplate (40 KB) is dead weight.** Charter, norms, and souls are identical every run and don't change. They could be replaced by a 1-sentence reference.

2. **P1/P2 summaries are not role-scoped.** A theorist in P3 doesn't need the data_scientist's P1 findings. Each role sees all 3 roles' work from upstream phases.

3. **P2 sends all 7 methods** even though only 1 is selected for the run. The full 29 KB method catalog could be replaced by a focused summary of the selected method.

4. **SOUL.md on disk is irrelevant.** Each profile's SOUL.md is 513 bytes of default Hermes personality. The actual role-defining content comes from the task prompt. The profile SOUL could be eliminated entirely — role instructions should live in the phase+role context.

5. **Profile memory is mostly boilerplate.** Each profile's MEMORY.md (~6 KB) is team charter + norms + role definition injected as "memory." The agents save almost no actual facts between runs.

## Proposed Reduction

### What to cut

| Component | Current | Proposed | Saved |
|-----------|---------|-----------|-------|
| Team charter + norms | 16 KB | **0** | 16 KB |
| Agent souls | 6 KB | **0** | 6 KB |
| Phase playbooks | 18 KB | **~5 KB** (condensed) | 13 KB |
| P1 Lit Review summary | 20 KB | **~10 KB** (role-scoped) | 10 KB |
| P1 Lit Review decision | 14 KB | **~8 KB** (condensed) | 6 KB |
| P2 Method Dev summary | 29 KB | **~8 KB** (selected method only) | 21 KB |
| P2 Method Dev decision | 23 KB | **~5 KB** (method-scoped) | 18 KB |

### What stays the same

| Component | Current | Notes |
|-----------|---------|-------|
| P3 current run summary | 39 KB | Needed in full for continuity |
| P3 current run decision | 19 KB | Needed in full |
| Project setting | 4 KB | Essential |
| Method definition | 2 KB | Essential |

### Additional (new)

| Component | Size | Notes |
|-----------|------|-------|
| P4 high-level summary | ~5 KB | Only if P4 has been run |
| P5 high-level summary | ~3 KB | Only if P5 has been run |

### Totals

| | Current | Proposed | Reduction |
|---|---------|-----------|-----------|
| Frozen context | ~193 KB | ~108 KB | **~45%** |
| Per-round task | ~17 KB | ~12 KB | ~30% |

## Design Principle

Instead of separate "soul," "playbook," "charter," and "norms" files, each run should receive a **single condensed context bundle:** phase instructions + role instructions + scoped upstream summaries + current run state. The profile's SOUL.md stays the generic Hermes identity (or is left empty), and all role-defining content lives in the launched prompt.

## Implementation Path

Context assembly happens in `core/launch_prompts.py` and `core/launch_run.py`. The frozen context is written to `.context/` in the run directory at launch time (see `launch_process.py`). To implement this:

1. Replace multi-file soul/playbook/charter/norms with a single condensed set per phase+role
2. Add role-filtering to upstream summary inclusion (e.g., theorist only gets theorist-relevant P1/P2 sections)
3. Add method-filtering to P2 method catalog inclusion (only selected method)
4. Add P4/P5 high-level summary injection for downstream awareness
