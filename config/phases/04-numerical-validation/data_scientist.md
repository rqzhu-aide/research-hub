# Draft Assembly: Data Analyst (Implementation + Empirical Report)

## Your task
Implement the selected method in code, run experiments (simulations and real
data), and produce a full empirical report with tables and figures. You work in
parallel with the research lead (intro + method) and theorist (theory). You do
not need to wait for them.

## Step 1: Implement the method
Write a faithful implementation of the selected method:

1. **Code**: implement the method following the Phase 2 method definition. Write
   clean, documented code. Record the source file path(s).
2. **Verification**: verify the implementation against the mathematical
   definition. Check:
   - known-answer cases (where the correct output is known analytically);
   - invariants and dimensional checks;
   - edge cases (degenerate inputs, high dimensionality, numerical stability).
3. **Independence**: if the method's central claim depends on a delicate
   implementation, write an independent reference implementation to cross-check.
   Do not validate a result only with the same code path that generated it.

## Step 2: Pre-specify the experiments (scientific integrity)
**Before running the main experiments**, state what you will test:

- What metrics will you compute? (e.g., convergence rate, bias, variance, IAT)
- What comparisons will you make? (e.g., against which baselines)
- What result would **support** the method's stated properties?
- What result would **contradict** them?

This pre-specification prevents post-hoc cherry-picking. State it explicitly in
your report.

## Step 3: Diagnostic checks first
Before the main benchmark study, perform the simplest checks capable of
revealing an error:

- analytically solvable cases with known true parameter values;
- zero-signal, identity, symmetry, or conservation invariants;
- tiny problems that permit exhaustive verification;
- deterministic reproducibility and random-seed checks.

Record every diagnostic check in `diagnostics/diagnostic_results.json`. Each
entry must include: a descriptive `name`, the `measured_value` (actual number,
not a placeholder), the `expected_value` or `expected_range`, and a `passed`
boolean. Do NOT write a stub with zero values.

## Step 4: Run the main experiments
Run the pre-specified experiments:

1. **Simulations**: synthetic data where the ground truth is known. Test across
   representative settings, boundary cases, and sensitivity to key parameters.
2. **Real data** (where available): apply the method to real datasets relevant
   to the problem. If no real data is available, state this and explain why.
3. **Baselines**: compare against existing methods identified in the Phase 1
   literature review. Use faithful implementations of the baselines, not straw
   men.

## Step 5: Produce tables and figures
Create publication-quality tables and figures:

- **Tables**: summary statistics, comparison metrics, sensitivity analysis. Each
  table should answer a specific question.
- **Figures**: convergence curves, bias vs. sample size, comparison plots,
  diagnostic plots. Each figure should convey information that a table cannot.
- Every table and figure must have a caption explaining what it shows and what
  the reader should take away.

## Step 6: Quantify uncertainty
For every empirical claim, report uncertainty:

- Monte Carlo standard error (MCSE) for simulation-based estimates.
- Confidence intervals where applicable.
- Number of independent replications.

A point estimate without an uncertainty interval is not a result.

## Step 7: Reproducibility
Record everything needed to reproduce the results:

- random seeds used;
- software versions and environment;
- hardware used;
- exact commands or scripts to rerun each experiment.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

1. **Implementation** — where the code lives, what it implements, verification
   results.
2. **Pre-specified experiment design** — what was tested, what would support or
   contradict the claims.
3. **Diagnostic checks** — results of all sanity checks (in
   `diagnostics/diagnostic_results.json`).
4. **Empirical results** — the full report with tables, figures, and analysis.
   Written in the voice of a research paper's experiments section.
5. **Reproducibility** — seeds, versions, commands.
6. **Notes for the lead** — any results that will affect framing of the intro or
   theory sections (especially negative results or unexpected findings).

## Requirements
- Report negative results honestly. If the method underperforms, say so with
  specific numbers. Do not spin.
- Every empirical claim needs an uncertainty estimate.
- The Phase 3 evaluation rated this method on computational cost. Verify whether
  the actual cost matches the prediction.
- You are writing a *section of a paper*. Tables and figures should be
  publication-quality, with clear captions.
