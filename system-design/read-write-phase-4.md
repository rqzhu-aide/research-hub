# Phase 4 — Numerical Validation (Read/Write Rules)

References [file-system.md](./file-system.md) for the canonical folder layout.
See [read-write-overview.md](./read-write-overview.md) for output types, cross-phase dependencies, and update semantics.

**Goal:** Implement and empirically validate a method. Runs independently from Phase 3 — either can run first.

**Read strategy:** Prompt context includes the run-specific instruction, the Phase 1 literature (data_scientist focus, Layer 2), and the theorist's Layer 3 highlight for brief awareness. The data_scientist also knows the folder location of `proofs/proof_status.md` — can read it for deep auditing when needed.

## Folder context

```
<method_stable_id>/numerical/
├── numerical_status.md            # Layer 2 — code/results status; frontmatter records method_version (updated each run)
├── highlight.md                   # Layer 3 — data_scientist's own summary (updated each run)
├── review.md                      # Layer 3 — theorist's cross-review (updated each run)
├── lead-highlight.md              # Layer 3 — research_lead's user-facing synthesis (updated each run)
├── implementation/                # Single live copy — kept current with method definition
├── results/                       # All simulation outputs
├── archived/                      # Retired material (wrong impl, old version)
├── run-1.md                       # Per-run report by data_scientist
├── run-2.md
└── ...
```

## Run 1 — Preliminary Run

The first run is always a **preliminary/exploratory run**: develop a first-pass implementation, test on simple cases, establish the computational framework. Output is a working codebase and initial status — not final results.

### Step 1 — Data scientist

The data_scientist receives a prompt to develop and test the initial implementation.

**Input:**

```
Run-specific instruction
Phase-1/run-<latest>/data_scientist-focus.md   # Layer 2 — literature grounding
<method_stable_id>/<stable_id>.md              # Method definition (Layer 2)
Phase-2/method-registry.json                   # Method version check

<method_stable_id>/proofs/highlight.md         # Layer 3 — brief awareness (if exists)
```

**Output:**

```
<method_stable_id>/numerical/
├── implementation/                # First-pass code (Layer 1)
├── results/                       # Preliminary simulation outputs (Layer 1)
├── numerical_status.md            # Layer 2 — what the code does, test status, known issues; frontmatter: method_version
├── highlight.md                   # Layer 3 — preliminary numerical status
└── run-1.md                       # Run report (approach, test results, known limitations)
```

### Step 2 — Theorist review

The theorist receives a prompt to review the implementation and results.

**Input:**

```
<method_stable_id>/numerical/numerical_status.md   # Layer 2 — full numerical status
```

**Output:**

```
<method_stable_id>/numerical/review.md             # Layer 3 — cross-review comment
```

### Step 3 — Lead synthesis

The research_lead receives a prompt to synthesize the user-facing highlight.

**Input:**

```
<method_stable_id>/numerical/numerical_status.md   # Layer 2
<method_stable_id>/numerical/review.md             # Layer 3 — theorist's review
```

**Output:**

```
<method_stable_id>/numerical/lead-highlight.md     # Layer 3 — user-facing highlight for UI
```

## Run N — Comprehensive Run

All runs after the preliminary run are **comprehensive runs**: the data_scientist runs full simulation studies, compares against benchmarks, and produces publication-quality results.

### Step 1 — Data scientist

The data_scientist receives a prompt to run comprehensive simulations and update results.

**Input:**

```
Run-specific instruction
Phase-1/run-<latest>/data_scientist-focus.md       # Layer 2 — literature grounding
<method_stable_id>/<stable_id>.md                  # Method definition
Phase-2/method-registry.json                       # Method version check
<method_stable_id>/numerical/
├── numerical_status.md                             # Current state (Layer 2)
├── highlight.md                                    # Own previous highlight (Layer 3)
├── review.md                                       # Previous cross-review (Layer 3)
├── run-<N-1>.md                                    # Previous run report
├── implementation/                                 # Existing code (Layer 1)
└── results/                                        # Existing results (Layer 1)

<method_stable_id>/proofs/highlight.md              # Layer 3 — brief awareness (if exists)
<method_stable_id>/draft/highlight.md               # Layer 3 — brief awareness (if exists)
```

**Output:**

```
<method_stable_id>/numerical/
├── implementation/                # Updated code (archive old if replaced)
├── results/                       # New simulation outputs (archive old if stale)
├── numerical_status.md            # Updated in place
├── highlight.md                   # Updated in place
└── run-<N>.md                     # New run report
```

### Step 2 — Theorist review

The theorist receives a prompt to review the updated implementation and results.

**Input:**

```
<method_stable_id>/numerical/numerical_status.md   # Layer 2 — updated numerical status
```

**Output:**

```
<method_stable_id>/numerical/review.md             # Layer 3 — updated cross-review comment
```

### Step 3 — Lead synthesis

The research_lead receives a prompt to synthesize the user-facing highlight.

**Input:**

```
<method_stable_id>/numerical/numerical_status.md   # Layer 2
<method_stable_id>/numerical/review.md             # Layer 3 — theorist's review
```

**Output:**

```
<method_stable_id>/numerical/lead-highlight.md     # Layer 3 — user-facing highlight for UI
```
