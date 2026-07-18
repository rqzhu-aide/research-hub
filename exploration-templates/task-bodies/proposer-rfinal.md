## Task: Proposer Round {{round_num}} of {{max_rounds}} — FINAL ROUND

### Situation
This is the **final round**. The method needs to converge into a clean,
complete specification that the team can move to mathematical validation.

Do not introduce fundamentally new directions unless the critique reveals a
fatal flaw. Focus on synthesis and polish.

### Instructions
1. Read the critic's final feedback.
2. Resolve all remaining open questions, or clearly state which cannot be
   resolved at this stage and why.
3. Produce a **clean method specification** — someone reading only this document
   should understand: the objective function, the optimization domain, the
   algorithm, and the evaluation metric.
4. Summarize the trajectory: how did the method evolve across rounds?

### Files to read
- `setting.md`
- `{{prev_critique_path}}` (critique of your previous proposal)

### Output
Write your response to: `{{output_path}}`

Use this structure:

- **Problem Statement** — finalized, precise
- **Proposed Method** — complete specification (the core deliverable)
- **Theoretical Justification** — why this should work
- **Summary of Iterations** — key changes across rounds and what drove them
- **Remaining Risks** — honest assessment of what could go wrong
- **Recommended Next Steps** — what the math validation phase should focus on

**Length guidance:** 2000–4000 words. This is the document that downstream
phases will build on — make it self-contained.
