# Phase 3 — Theory & Proofs (Read/Write Rules)

References [file-system.md](./file-system.md) for the canonical folder layout.
See [read-write-overview.md](./read-write-overview.md) for output types, cross-phase dependencies, and update semantics.

**Goal:** Develop rigorous theoretical foundations for a method. Runs independently from Phase 4 — either can run first.

**Read strategy:** Prompt context includes the run-specific instruction, the Phase 1 literature (theorist focus, Layer 2), and the data_scientist's Layer 3 highlight for brief awareness. The theorist also knows the folder location of `numerical/numerical_status.md` — can read it for deep auditing when needed.

## Folder context

```
<method_stable_id>/proofs/
├── proof_status.md                # Layer 2 — proof status, assumptions, dependency graph; frontmatter records method_version (updated each run)
├── highlight.md                   # Layer 3 — theorist's own summary (updated each run)
├── review.md                      # Layer 3 — data_scientist's cross-review (updated each run)
├── lead-highlight.md              # Layer 3 — research_lead's user-facing synthesis (updated each run)
├── material/                      # Single live copy — continuously improved
├── archived/                      # Retired proof material
├── run-1.md                       # Per-run report by theorist
├── run-2.md
└── ...
```

## Run 1 (initial per method)

### Step 1 — Theorist

The theorist receives a prompt to develop the initial proof.

**Input:**

```
Run-specific instruction
Phase-1/run-<latest>/theorist-focus.md   # Layer 2 — literature grounding
<method_stable_id>/<stable_id>.md        # Method definition (Layer 2)
Phase-2/method-registry.json             # Method version check

<method_stable_id>/numerical/highlight.md     # Layer 3 — brief awareness (if exists)
```

**Output:**

```
<method_stable_id>/proofs/
├── material/                      # Full proof work (Layer 1)
├── proof_status.md                # Layer 2 — assumptions, framework, key results, open items; frontmatter: method_version
├── highlight.md                   # Layer 3 — theoretical readiness
└── run-1.md                       # Run report (incl. recommendations for method refinement)
```

### Step 2 — Data scientist review

The data_scientist receives a prompt to review the proof.

**Input:**

```
<method_stable_id>/proofs/proof_status.md     # Layer 2 — full proof status
```

**Output:**

```
<method_stable_id>/proofs/review.md           # Layer 3 — cross-review comment
```

### Step 3 — Lead synthesis

The research_lead receives a prompt to synthesize the user-facing highlight.

**Input:**

```
<method_stable_id>/proofs/proof_status.md     # Layer 2
<method_stable_id>/proofs/review.md           # Layer 3 — data_scientist's review
```

**Output:**

```
<method_stable_id>/proofs/lead-highlight.md   # Layer 3 — user-facing highlight for UI
```

## Run N (re-run)

### Step 1 — Theorist

The theorist receives a prompt to improve or expand the proof.

**Input:**

```
Run-specific instruction
Phase-1/run-<latest>/theorist-focus.md       # Layer 2 — literature grounding
<method_stable_id>/<stable_id>.md            # Method definition
Phase-2/method-registry.json                 # Method version check
<method_stable_id>/proofs/
├── proof_status.md                           # Current state (Layer 2)
├── highlight.md                              # Own previous highlight (Layer 3)
├── review.md                                 # Previous cross-review (Layer 3)
├── run-<N-1>.md                              # Previous run report
└── material/                                 # Existing proof (Layer 1)

<method_stable_id>/numerical/highlight.md     # Layer 3 — brief awareness (if exists)
<method_stable_id>/draft/highlight.md         # Layer 3 — brief awareness (if exists)
```

**Output:**

```
<method_stable_id>/proofs/
├── material/                      # Improved/expanded (archive old if replaced)
├── proof_status.md                # Updated in place
├── highlight.md                   # Updated in place
└── run-<N>.md                     # New run report
```

### Step 2 — Data scientist review

The data_scientist receives a prompt to review the updated proof.

**Input:**

```
<method_stable_id>/proofs/proof_status.md     # Layer 2 — updated proof status
```

**Output:**

```
<method_stable_id>/proofs/review.md           # Layer 3 — updated cross-review comment
```

### Step 3 — Lead synthesis

The research_lead receives a prompt to synthesize the user-facing highlight.

**Input:**

```
<method_stable_id>/proofs/proof_status.md     # Layer 2
<method_stable_id>/proofs/review.md           # Layer 3 — data_scientist's review
```

**Output:**

```
<method_stable_id>/proofs/lead-highlight.md   # Layer 3 — user-facing highlight for UI
```
