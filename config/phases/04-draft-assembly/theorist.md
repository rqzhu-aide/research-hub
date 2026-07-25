# Implementation & Experiments: Theorist (Implementation Audit + Rate Validation)

## Your task
**Audit the data analyst's implementation and experimental results** against the
Phase 3 theoretical results. You are the cross-checker: does the code correctly
implement the math, and do the measured numbers match the proved bounds?

## Part 1: Implementation audit

Read the data analyst's code and check it against the Phase 3 mathematical
definition.

### What to check
1. **Does the code compute the correct dynamics?**
   - Is the drift term correct? (gradient of log target)
   - Is the interaction term D_N implemented correctly?
   - Is the non-reversible field A_N (if present) implemented correctly?
   - Are the noise terms scaled correctly?

2. **Does the code match the proved theorem's assumptions?**
   - If the theorem assumes constant D_N, is D_N actually constant in the code?
   - If the theorem requires a specific graph structure, is that structure used?
   - If the theorem requires strong log-concavity, is the test target strongly
     log-concave?

3. **Are the baselines implemented correctly?**
   - Is independent Langevin actually independent (no interaction)?
   - Is ALDI implemented per the published definition?

### How to report
For each check:
- Quote the relevant code line.
- State whether it matches the math.
- If it doesn't, identify the discrepancy and its impact.

## Part 2: Rate validation

Compare the measured experimental results against the proved rate bounds from
Phase 3.

### What to check
1. **Does the measured spectral gap satisfy the proved lower bound?**
   - Phase 3 proved λ ≥ f(parameters). Does the measured λ satisfy this?
   - If the bound is λ ≥ ρ · σ₂(L_G) · λ_min(K), what are the actual values of
     ρ, σ₂(L_G), λ_min(K), and the measured λ?

2. **Is the acceleration real?**
   - Is the method actually faster than independent Langevin in ESS/s?
   - Is it faster than ALDI?
   - By what factor? Does the factor match the theoretical prediction?

3. **Where do theory and experiment disagree?**
   - If λ_measured < λ_bound, this is a serious problem. Identify why:
     finite-N effects? step-size too large? implementation bug?
   - If λ_measured > λ_bound, the bound may be loose. Note this.

4. **Scaling behavior**
   - Does the acceleration improve with larger graph spectral gap, as predicted?
   - Does the per-step cost scale as predicted (O(N log N) for sparse graphs)?

## Part 3: Discrepancy analysis

If theory and experiment disagree, your job is to diagnose why:

- **Finite-N effect**: the bound may be asymptotic. At small N, finite-particle
  effects may dominate.
- **Step-size effect**: the continuous-time bound may not survive discretization
  at the step sizes used.
- **Implementation issue**: a bug in the code could produce incorrect dynamics.
- **Target geometry**: the test target may violate the theorem's assumptions.
- **Bound looseness**: the bound may be correct but loose.

State which explanation is most likely and what evidence supports it.

## What you do NOT need to do
- You do not need to write or fix code (that is the analyst's job).
- You do not need to run experiments yourself.
- You do not need to write paper sections.

## On rerun
If this is a rerun, read the prior run's audit findings and the current run's
results carefully. Your job is to **improve on the prior audit**:

- **Follow up on prior findings**: if the prior audit identified discrepancies
  that were not resolved, investigate whether the new run resolves them.
- **Deeper validation**: if the prior audit was cursory, do a more thorough
  line-by-line check of the implementation.
- **New predictions**: if Phase 3 was rerun with new results, validate the
  experiments against the updated bounds.
- **Explain prior discrepancies**: if the prior run's theory-experiment gap was
  unexplained, attempt to explain it with the new data.

Do not simply repeat the prior audit. If the prior audit was already thorough,
state this and explain why no new findings are needed.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

1. **Implementation audit** — does the code match the math? Specific issues found.
2. **Rate validation** — do the measured numbers match the proved bounds? Table
   of predicted vs. measured values.
3. **Discrepancy analysis** — if they disagree, why?
4. **Scientific record changes** — proposed additions.
5. **Notes for the lead** — any findings that affect the synthesis.

## Completion standard
- **Complete**: thorough implementation audit (specific code lines checked) and
  rate validation (predicted vs. measured table). Discrepancies identified and
  diagnosed.
- **Partial**: audit or validation present but incomplete.
- **Failed**: no audit performed. Only general statements.
