# Phase: Numerical Validation

## Goal
Implement the proposed method, run experiments, and validate it numerically.
Turn the method sketch from Phase 02 into working code, benchmarks, and
empirical evidence that it does what the theory claims (or honest evidence
about where it falls short).

## Gating
**Requires Phase 02 (Method Development) to be complete.** The lead reads the
method development summary before composing directives — you can't implement a
method that hasn't been specified.

Note: Phase 03 (Theoretical Justification) is NOT required. Implementation and
theory can proceed in parallel once the method is specified. If Phase 03 has
already run, its findings inform the experiments (e.g., test the regime where
the theory is proven, stress-test where it's conjectural).

## Pattern
**Sequential.** This is a build-and-test pipeline:
1. Data scientist implements the core method and runs initial experiments (round 1)
2. Theorist checks the implementation against the math, identifies regime mismatches (round 2)
3. Data scientist revises and runs the final validation suite (round 3, if requested)

Each member takes the previous one's output as input. The lead creates tasks
one at a time — do NOT create them all at once.

## Folder
All outputs land in `numerical/run/NN/`:
- `round-01/data_scientist.md` — implementation + initial experiments
- `round-02/theorist.md` — math-vs-code check
- `round-03/data_scientist.md` — revised implementation + final validation (if 3 rounds)
- Summary goes to `phase-summaries/04-numerical-validation.html`

Actual code, scripts, and data artifacts go in `numerical/` (the folder is the
project's numerical workspace; the run outputs are the human-readable reports).

## Files in this folder
- `_lead.md` — how the research_lead runs a sequential implementation pipeline. **Read first.**
- `data_scientist.md` — the implementation + experimentation protocol
- `theorist.md` — the math-vs-code verification protocol
- `research_lead.md` — the positioning/significance review protocol (optional final stage)

## What success looks like
By the end of this phase, the project should have:
1. Working code that implements the method (in `numerical/`)
2. Experimental results demonstrating the method's behavior (at least on synthetic/benchmark problems)
3. Honest performance assessment — what works, what doesn't, under what conditions
4. A validation story: do the numbers support the method's claims?

If the method doesn't work as hoped, that's a valid (if disappointing) outcome
— the lead must report honestly and flag what would need to change.
