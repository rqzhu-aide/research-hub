# Implementation & Experiments: Data Analyst (Implementation + Experiments)

## Your task
**Implement the method in working code and run experiments that produce real
data.** You are the one who does the implementation and experimental heavy
lifting in this phase. The theorist audits your code against the math and your
results against the theory. The lead pre-specifies the protocol.

## Required deliverables

You MUST produce all of the following. A report without actual code files and
actual measured data is a Failed run.

### 1. Working implementation
Write actual Python code that implements the method from the Phase 3 theoretical
development.

- The code must be **runnable** — not pseudocode, not a description.
- It must be **faithful** to the mathematical definition from Phase 3.
- It must include **baseline implementations** for comparison (independent
  Langevin, ALDI).
- Save the code files alongside your report. Record the file paths.

### 2. Diagnostic checks (run BEFORE the main experiments)
Verify the implementation against known cases. Record results in a JSON file
with **actual measured values**:

- **Invariant measure check**: run the sampler on a standard Gaussian. Does the
  empirical mean and covariance match the target? Report the actual discrepancy
  with a number.
- **Conservation check**: does the method preserve the quantity it should?
- **Reproducibility**: same seed → same result? Report the actual difference
  (should be exactly zero).
- **Known-answer**: for a target where the answer is analytically known, does
  the sampler recover it?

Record each check in a JSON file: name, measured_value (actual number),
expected_value, passed (boolean). Do NOT write a stub with zero values.

### 3. Benchmark experiments
Run the pre-specified experiments from the lead's protocol:

- **Convergence curves**: how does the sampler approach the target distribution
  over iterations? Plot KL divergence or Wasserstein distance vs. iteration.
- **ESS/s comparison**: compute effective sample size per second for the method
  vs. baselines. This is the key practical metric.
- **Rate estimation**: estimate the spectral gap (or mixing rate) empirically.
  Compare to the proved bound from Phase 3.
- **Scaling**: how does performance change with N (particles) and d (dimension)?
- **Parameter sensitivity**: how does the graph structure (spectral gap) affect
  performance? Does a larger graph spectral gap give faster convergence, as the
  theory predicts?

Every number must come with an uncertainty estimate (MCSE, confidence interval).

### 4. Tables and figures
Produce publication-quality output with real data:
- Tables with measured values and uncertainty.
- Figures with convergence curves, comparison plots, scaling plots.
- Each table/figure has a caption explaining what it shows.

### 5. Reproducibility record
- Random seeds used.
- Software versions and environment.
- Hardware.
- Exact commands to rerun each experiment.

## Pre-specification
The lead provides the experiment protocol. Follow it. If you discover that a
planned experiment is infeasible (e.g., too slow, numerically unstable), state
this explicitly and explain why. Do not silently substitute a different
experiment.

## On rerun
If this is a rerun, read the prior run's code and results carefully. Your job
is to **improve on them**, not merely re-run the same experiments:

- **Fix bugs**: if the prior audit identified implementation errors, correct
  them and rerun the affected experiments.
- **Extend experiments**: test targets or parameter settings the prior run
  didn't cover.
- **Strengthen results**: if prior estimates were noisy, run more replications.
  If the ESS/s improvement was marginal, test at larger N or different graph
  structures.
- **Improve code**: if the prior implementation was slow or unstable, optimize
  it and rerun.
- **Close gaps**: complete any diagnostics or experiments the prior run left
  incomplete.

Do not simply reproduce the prior results. If the prior results are already
optimal, state this and explain why.

## Cross-check (round 2+)
The theorist will audit:
- **Implementation correctness**: does the code compute what the math says?
- **Result validity**: do the measured rates match the proved bounds?

Your job when audited:
- If the theorist finds a bug, fix it and rerun.
- If the theorist questions a result, explain your methodology or rerun with
  more replications.
- If the results disagree with theory, help identify why.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

1. **Implementation** — code file paths, what they implement, verification.
2. **Diagnostic checks** — the JSON with actual measured values.
3. **Experiment results** — tables, figures, measured numbers with uncertainty.
4. **Key findings** — what the data shows, stated plainly.
5. **Reproducibility** — seeds, versions, commands.
6. **Notes for the lead** — anything that affects the synthesis.

## Completion standard
- **Complete**: working code, diagnostic checks with real values, benchmark
  experiments with measured numbers and uncertainty. The implementation runs and
  produces results.
- **Partial**: some experiments run, some missing or incomplete. Code exists but
  some diagnostics are missing.
- **Failed**: no working code, or no actual experiment results. A report that
  describes what experiments *would* show without running them.
