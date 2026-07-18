## Task: Critic Round {{round_num}} of {{max_rounds}}

### Situation
This is a **middle round**. The proposer has revised based on your previous
critique. Your job is to check whether concerns were genuinely addressed (not
just waved away), probe deeper on feasibility, and push toward convergence.

### Instructions
1. Read the revised proposal.
2. For each concern you raised previously, assess: was it addressed, partially
   addressed, or ignored?
3. If the proposer pushed back on one of your points, evaluate their reasoning.
   Be willing to concede if they made a good case.
4. Go deeper on feasibility: Are the computations tractable? Are the
   assumptions realistic? What breaks at edge cases?
5. Suggest concrete improvements — not just "this is weak" but "here is how
   to make it stronger."

### Files to read
- `setting.md`
- `{{proposal_path}}` (revised proposal to evaluate)

### Output
Write your response to: `{{output_path}}`

Use this structure:

- **Assessment of Revision** — were previous concerns addressed?
- **Strengths** — what has improved
- **Remaining Weaknesses** — specific, with examples
- **Suggestions for Improvement** — concrete and actionable
- **Convergence Assessment** — is the method converging? What needs to happen
  in the final round to reach a specification ready for validation?

**Length guidance:** 1000–2500 words. Focus on the issues that will make or
break the final method.
