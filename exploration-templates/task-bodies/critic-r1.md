## Task: Critic Round {{round_num}} of {{max_rounds}}

### Situation
This is the **first round** of critique. The proposer has submitted an initial
exploration. Your job is to evaluate breadth, identify the most promising
direction, and flag any fatal flaws early — before the team invests more rounds
in a dead end.

### Instructions
1. Read the proposal and the project settings.
2. Independently research the literature to check the proposer's claims and
   find work they may have missed.
3. Evaluate: Is the problem well-stated? Are the proposed directions grounded
   in existing work? Is anything fundamentally flawed?
4. Be specific. "The method is unclear" is not useful. "Section 3.2 conflates
   policy gradient with natural gradient, which would make the estimator biased
   under constraint (2)" is useful.

### Files to read
- `setting.md`
- `{{proposal_path}}` (proposal to evaluate)

### Output
Write your response to: `{{output_path}}`

Follow the output format from your memory file:
Summary of Proposal, Strengths, Weaknesses, Suggestions for Improvement, Independent Literature Findings.

**Length guidance:** 1000–2500 words. Prioritize identifying the 2–3 most
important issues over exhaustive nitpicking.
