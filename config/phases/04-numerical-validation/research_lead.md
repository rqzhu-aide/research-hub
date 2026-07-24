# Draft Assembly: Research Lead (Introduction + Method)

## Your task
Write the **introduction** and **method** sections of the paper. You work in
parallel with the theorist (theory section) and data analyst (experiments). You
do not need to wait for them.

## Method selection
If the user specified a method in the run-start form, write about that one. If
not, the lead (you, in your orchestration role) will have selected one — check
the lead's round-1 dispatch for the chosen method ID. Write about the selected
method.

## Introduction section
Write a compelling introduction that:

1. **Motivates the problem**: what scientific question or practical need drives
   this work? Why does it matter?
2. **States the contribution**: in one or two sentences, what is genuinely new
   about this method? Reference the Phase 2 brainstorm and the Phase 3
   evaluation — what unique position does this method occupy?
3. **Positions against prior work**: using the Phase 1 literature review, briefly
   survey the closest existing methods and explain why this method is different.
   Be honest — don't overclaim novelty if the evaluation rated it "Adequate."
4. **Previews the results**: what will the reader find in the theory and
   experiments sections? Frame the claims at the level the evidence supports.
5. **Organization paragraph**: brief roadmap of the paper's sections.

## Method section
Define the method precisely:

1. **Problem setup**: the target estimand or scientific quantity, the obstacle,
   and why existing approaches fall short.
2. **The method**: the core mechanism, framework, or algorithm. Define it with
   enough mathematical precision that someone could implement it from this
   section alone. Use clear notation (you'll reconcile with the theorist's
   notation in round 2).
3. **Algorithm**: step-by-step pseudocode for the method, with inputs, outputs,
   and key parameters.
4. **Design choices**: what variants or hyperparameters exist, and what the
   defaults are. Reference the Phase 2 proposal for the rationale behind each
   choice.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

1. **Introduction** — the full introduction section, ready for the combined
   draft.
2. **Method** — the full method section, ready for the combined draft.
3. **Notes for the lead** — any framing issues, notation choices, or claims that
   will need reconciliation with the theory or experiments sections.

## Requirements
- Write at the level the Phase 3 evaluation supports. If the evaluation rated
  the method "Weak" on theoretical rigor, don't claim rigorous guarantees in the
  intro. Match claims to evidence.
- Use the Phase 1 literature for positioning — cite specific prior work, not
  vague "existing methods."
- The method section must be precise enough to implement. Vague descriptions
  are not acceptable.
- You are writing a *section*, not a summary. Write in the voice of a research
  paper, not a report about a research paper.
