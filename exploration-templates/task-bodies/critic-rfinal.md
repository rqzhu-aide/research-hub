## Task: Critic Round {{round_num}} of {{max_rounds}} — FINAL ROUND

### Situation
This is the **final round** of the exploration phase. The proposer has submitted
what should be a converged method specification. Your job is to give a clear
verdict: **is this method ready to move to mathematical validation?**

### Instructions
1. Read the final proposal thoroughly.
2. Evaluate the complete method as a whole — not just incremental changes.
3. Identify any remaining risks or gaps that the math validation phase must
   address.
4. Give an explicit readiness verdict.

### Files to read
- `setting.md`
- `{{proposal_path}}` (final proposal to evaluate)

### Output
Write your response to: `{{output_path}}`

Use this structure:

- **Overall Assessment** — your verdict on the method as a whole
- **Strengths** — what is solid and ready to build on
- **Critical Risks** — what could cause the method to fail in implementation
- **Gaps for Math Validation** — specific theoretical questions that need
  formal proof or disproof
- **Readiness Verdict** — one of:
  - ✅ **READY** — proceed to mathematical validation
  - ⚠️ **READY WITH RESERVATIONS** — proceed, but address [specific items] first
  - ❌ **NOT READY** — [specific reasons]; the exploration phase needs revision

**Length guidance:** 1000–2500 words. Be decisive — the team needs a clear
signal on whether to proceed.
