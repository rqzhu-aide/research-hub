# Lead Instructions: Draft Assembly

Coordinate parallel section drafting, then combine the three sections into one
formal manuscript.

## Step 0: Select the method (if user did not specify)
Read the Phase 3 summary. If the user named a specific idea in the run-start
form, use that one. If not, **you decide** which idea to pursue based on the
Phase 3 rankings. State your choice, the method ID, and your reasoning clearly
at the top of your report. The user can override by rerunning with a different
choice.

## Step 1: Read prior context
Read:
- `setting.md`
- the approved Phase 02 summary (the full idea set and method definitions)
- the approved Phase 03 summary (the evaluation rankings)
- the approved Phase 01 summary (literature context)
- prior `numerical/` runs

Identify the selected method: its Phase 2 definition, its Phase 3 evaluation
across all four dimensions, and any open questions flagged during evaluation.

## Step 2: Round 1 — parallel drafting
Dispatch three independent tasks:

1. **You (research lead)**: write the introduction and method section.
   - Introduction: motivate the problem, state the contribution, position
     against prior work (using Phase 1 literature).
   - Method: define the method precisely — the target, the mechanism, the
     algorithm. Enough detail for someone to implement it.

2. **Theorist**: write the full theory section with detailed proofs.
   - All theoretical results the method rests on: theorems, lemmas,
     propositions.
   - Full proofs, not sketches. State every assumption and its role.
   - Scope and limitations: where the theory holds and where it breaks.

3. **Data analyst**: implement the method, run experiments, write the empirical
   report.
   - Implement the method in code (faithful to the theorist's formalization).
   - Run simulations on synthetic data and real data where available.
   - Produce tables and figures showing the method's performance.
   - Follow the scientific-integrity protocol (pre-specify, diagnose, quantify
     uncertainty, record reproducibility info).

All three work independently. They do not need to wait for each other in round 1.

## Step 3: Round 2 — combine into formal draft
Read all three sections. Then:

1. **Reconcile notation**: ensure the same symbols mean the same thing across
   the intro/method, theory, and experiments. Create a unified notation table
   if needed.
2. **Reconcile framing**: ensure the introduction's claims match what the
   theory proves and what the experiments show. If the intro overclaims, narrow
   it. If the theory proves something the intro doesn't mention, add it.
3. **Combine** into a single coherent manuscript with a logical flow:
   introduction → related work (from Phase 1) → method → theory → experiments →
   discussion → conclusion.
4. **Write the discussion**: what the results mean, limitations, and open
   questions flagged during Phase 3 evaluation.
5. **Assemble references** from all three sections into one bibliography.

## Step 4: Final synthesis
Write the HTML summary to the exact path provided. Report:
- which method was selected and why (especially if the lead decided);
- the structure of the combined draft and where each section's content came from;
- any notation or framing reconciliations that were needed;
- limitations and open questions carried from Phase 3;
- the draft's readiness for review.

Present explicit user options: approve the draft, request revision (specific
sections), rerun with a different method, or proceed to Phase 5 (data analysis
deepening) or Phase 6 (paper writing / finalization).

## Requirements
- If the user did not specify a method, you decide. State the choice and
  reasoning clearly. Do not ask the user to decide mid-run.
- All three sections must be present in the combined draft. If a member's report
  is Partial or Failed, use what they produced and note the gaps.
- The combined draft should read as one coherent paper, not three glued-together
  sections. Transitions and cross-references matter.
- Preserve the scientific integrity of each member's work — do not soften the
  theorist's proofs or the data analyst's negative results to make the paper
  "look better." Honest reporting is non-negotiable.
