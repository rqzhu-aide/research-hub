---
sidebar_position: 2
title: "Method Registry & Permanent Numbering"
---

# Method Registry & Permanent Numbering

Every method proposed in Phase 2 gets a **permanent integer number** that survives retirement and merge. This gives each method a stable, human-friendly handle.

## The registry file

The single source of truth lives at `ideas/methods/_registry.yaml`:

```yaml
next_number: 8
entries:
  - number: 1
    stable_id: spectral-graph-coupling
    label: Spectral graph coupling
    status: recommended
    added_in_run: f14ad9b2-a9c3-409c-a45c-30027df11377
  - number: 4
    stable_id: cheeger-optimal-dn
    label: Cheeger-optimal D_N
    status: retired
    added_in_run: f14ad9b2-a9c3-409c-a45c-30027df11377
    retired_in_run: 9bc360f2-e8d1-4682-bea0-42101f027991
```

## Rules

1. **Numbers are never reused.** A retired or merged method keeps its number occupied. The `next_number` only ever increases. There are no gaps filled.

2. **Every method file has a `number:` field** in its frontmatter, matching the registry.

3. **Display methods with their number.** Users see "#1 Spectral graph coupling", "#5 Kernel-metric coupling". The number is how you refer to a method across reruns.

4. **Retirement updates the registry.** When a method is retired, its entry gets `status: retired` and `retired_in_run: <run_id>`. The number stays.

5. **Merge updates the registry.** When method B is merged into method A, method B's entry gets `status: retired` and `merged_into: <A's stable_id>`. Both numbers stay occupied.

## Why permanent numbers?

Names can drift, descriptions can change, but "#4" always means the same method. A user who remembers "method #4" from last week still refers to the same method, even if it was later retired or merged into another.

This is the "jersey number" principle: once assigned, the number is the method's identity for the life of the project.
