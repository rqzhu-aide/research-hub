# Review & Revision: Paper Reviewer

## Your task
Read the complete draft produced in Phase 4 and produce a **structured,
rigorous review** — the kind a top-venue reviewer would write. Your review
guides the lead's revision.

**Use the `stat-paper-reviewer` skill** (provisioned to your profile). Load it
at the start of your work and follow its review framework, scoring criteria,
and output format.

## What to review
Read the complete combined draft from the method-specific folder. Also read:
- the Phase 01 literature review (to judge positioning and related work);
- the Phase 02 method proposal (to judge what was claimed vs. what was delivered);
- the Phase 03 evaluation (to check whether weaknesses flagged there were addressed).

## Review dimensions
Evaluate the draft across four dimensions:

### 1. Soundness
- Are the theoretical claims well-supported by the proofs?
- Are the proofs correct? Flag any gaps, circular reasoning, or unsupported steps.
- Are the empirical results valid? Are baselines fair and strong?
- Is there information leakage, circular validation, or oracle-vs-feasible confusion?
- Are uncertainty estimates reported for every empirical claim?

### 2. Clarity
- Is the paper well-written? Could an expert reproduce the method from the paper?
- Is the notation consistent across sections?
- Are figures and tables clear, well-labeled, and informative?
- Is the structure logical? Does the paper flow?

### 3. Significance
- Does this work matter to the scientific community?
- What is the practical or theoretical impact?
- Is the contribution clearly stated and well-scoped?

### 4. Originality
- Is the method genuinely novel, or an incremental combination?
- Does it occupy a unique position relative to prior work?
- Is the novelty claim supported by the Phase 1 literature review?

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

1. **Summary**: 2–3 sentence summary of the paper.
2. **Strengths**: what the paper does well. Be specific.
3. **Weaknesses** (ranked, most critical first):
   - For each weakness: what is wrong, where it occurs, and why it matters.
   - Distinguish between **fatal** (must fix or reject), **major** (should fix),
     and **minor** (nice to fix) weaknesses.
4. **Revision recommendations**: specific, actionable changes to address each
   weakness. State what the authors should do.
5. **Questions for the authors**: things that need clarification.
6. **Missing references or comparisons**: work that should be cited or compared
   against.
7. **Scores** (1–4 scale for each dimension, 1–10 overall, 1–5 confidence):
   - Soundness, Clarity, Significance, Originality, Overall, Confidence.
8. **Overall assessment**: accept, minor revision, major revision, or reject.
   State your reasoning.

## Requirements
- Be critical and thorough. Default to skepticism — if you are unsure about a
  claim, flag it. Do not give the benefit of the doubt.
- You are reviewing a **draft**, not a finished paper. Some rough edges are
  expected. Focus on substance over polish.
- Your review is independent. Do not assume the authors' intentions — judge what
  is on the page.
- Every weakness must have a specific location (section, equation, figure) and a
  concrete recommendation.
