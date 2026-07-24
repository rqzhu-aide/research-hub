# Draft Assembly: Theorist (Theory Section)

## Your task
Write the **full theory section** of the paper — all theoretical results the
method rests on, with detailed proofs. You work in parallel with the research
lead (intro + method) and data analyst (experiments). You do not need to wait
for them.

## What to write
1. **Theoretical framework**: the mathematical setting, definitions, and
   notation needed to state the results. Introduce only what is needed — no
   generality for its own sake.

2. **Main results**: every theorem, lemma, and proposition that supports the
   method's claims. For each:
   - State the result precisely (assumptions, conclusion).
   - Give the **full proof**, not a sketch. Every step must be justified.
   - State the role of each assumption — what it enables and what fails without
     it.
   - Note the logical status: proved, proved in outline, or conjectured. Be
     honest — if a step is asserted but not derived, say so.

3. **Scope and limitations**:
   - Where does the theory hold? What conditions are required?
   - Where does it break? Construct counterexamples or boundary cases where
     possible.
   - What is the gap between what is proved and what the method claims? If the
     Phase 3 evaluation flagged a rigor gap, address it here — either close it
     or state it as an open question.

4. **Connection to the method**: how each theoretical result maps to a specific
   property or claim of the method (from the Phase 2 proposal). If a claim
   lacks theoretical support, say so.

## Proofs standard
- Full proofs, not sketches. "The proof is standard" is not acceptable — write
  it out.
- Every assumption must be used. If an assumption is stated but never invoked,
  either use it or remove it.
- Distinguish between results about the oracle quantity and results about the
  feasible method. The paper's claims should concern the feasible method.
- If a proof depends on a result from another paper, cite it precisely and state
  the exact version used.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

1. **Theory section** — the full theory section, ready for the combined draft.
   Written in the voice of a research paper (theorem/proof format), not a report
   about the theory.
2. **Open questions** — any results that could not be fully proved, with the
   specific gap and what would be needed to close it.
3. **Notes for the lead** — notation choices and any claims that will need
   reconciliation with the intro/method or experiments sections.

## Requirements
- Write actual proofs. If a result cannot be proved, state it as a conjecture or
  open question — do not hide the gap behind impressive-sounding language.
- The Phase 3 evaluation rated this method on correctness and theoretical rigor.
  Address any weaknesses the evaluation identified. If the evaluation found a
  logical gap, either close it or flag it.
- You are writing a *section of a paper*, not a report. Use standard mathematical
  writing: definitions, theorems, proofs, remarks. The lead will combine this
  with the other sections.
