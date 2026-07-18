## Task: Proposer Round {{round_num}} of {{max_rounds}}

### Situation
This is a **middle round**. The critic has reviewed your previous proposal
and provided specific feedback. Your job now is to revise and refine.

### Instructions
1. Read the critic's feedback carefully.
2. For each point raised, decide: **address it** (revise the method) or
   **push back** (explain why the original approach is sound, with evidence).
3. Narrow scope — converge toward a single, well-specified method.
4. If the critique surfaced a genuinely better direction, pivot. Don't anchor
   on your earlier proposal out of stubbornness.

### Files to read
- `setting.md`
- `{{prev_critique_path}}` (critique of your previous proposal)

### Output
Write your response to: `{{output_path}}`

Your proposal must explicitly reference the critique. Use this structure:

- **Problem Restatement** — update if the problem definition has evolved
- **Changes from Previous Round** — a bullet list of what changed and why
- **Related Work** — new findings since the last round, if any
- **Proposed Method** — the revised method, fully specified
- **Response to Critique** — point-by-point: addressed / rejected (with reasons)
- **Open Questions** — remaining uncertainties

**Length guidance:** 1500–3500 words. Prioritize precision over breadth.
