---
sidebar_position: 3
title: "Reruns: Audit, Fix, Extend"
---

# Reruns: Audit, Fix, Extend

When you rerun a phase that already has prior output, Research Hub treats it as an **iterative refinement** of existing material — not a clean restart.

## The rerun protocol

Every phase lead playbook includes this protocol for reruns:

1. **Audit first.** Read every prior round output for this method. Identify what's correct, incomplete, wrong, or missing. Write the audit findings into the report.

2. **Fix in place.** Correct errors, fill gaps, tighten claims in the existing material. Build on it, don't discard it.

3. **Add new material.** Extend with new theorems, experiments, baselines, or analysis that the prior run lacked.

4. **Never replace.** Prior outputs are sealed history. Write new rounds into the **new run directory**. The prior run's files stay intact. The final summary references both prior and new material, noting what changed.

## What triggers a rerun?

The user explicitly reruns a phase when they want:
- A different question, scope, or approach
- Updated context (e.g., a new literature library from a Phase 1 rerun)
- To fix errors found in a prior run's review
- To extend with additional analysis

## What happens to the prior run?

- Its files are never deleted or overwritten
- Its status remains in history (`approved`, `awaiting_review`, etc.)
- The new run's summary includes a comparison with the prior run
- If the prior run was `approved`, it stays approved until the user approves the new run as a replacement

## Method-bound reruns

For phases 3, 4, and 5, reruns are bound to a specific method. Output goes to `branches/<stable_id>/<folder>/run/NN/`. Each method accumulates its own independent run history.

## Phase 2 reruns: special rules

Phase 2 (Method Development) has additional rerun logic:

- **Re-evaluate all existing methods** against the four criteria (novelty, tractability, acceleration potential, differentiation)
- **Retire** methods that score Weak/Insufficient on 2+ dimensions AND have no downstream records
- **Merge** substantially identical methods (same mechanism described differently), keeping the survivor with downstream records
- **Never reuse** method numbers (see [Method Registry](./method-registry.md))
