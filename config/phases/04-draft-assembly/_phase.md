# Phase: Implementation & Experiments

## Goal
**Implement the method in code, run experiments, and produce empirical results**
that validate or challenge the theoretical predictions from Phase 3. The data
analyst builds the implementation and runs the experiments. The theorist audits
the numerical results against the proved rate bounds. The lead synthesizes.

This phase produces **concrete code and data**: working implementations,
diagnostic check results, experiment outputs with measured numbers. A report
that *describes* what experiments would show is **not** a deliverable.

## Role division — who does the heavy lifting

| Role | Primary responsibility | Audit responsibility |
|------|----------------------|---------------------|
| **Data Analyst** | **Implement** the method in code, **run** experiments, **produce** tables and figures with real data | Audit the theorist's predictions: do the numbers match? |
| **Theorist** | **Audit** the experimental results against the proved rate bounds | Check implementation correctness against the mathematical definition |
| **Research Lead** | **Synthesize** the empirical findings, assess what was validated and what wasn't | Ensure experiments are pre-specified and honestly reported |

The data analyst does the implementation and experiments. The theorist cross-checks
that the code matches the math and the results match the theory. The lead ensures
scientific integrity.

## Study structure
**Parallel pattern.** All three roles work independently in round 1.

- **Round 1**: Data analyst implements and runs initial experiments. Theorist
  independently checks the implementation against the Phase 3 mathematical
  definition. Lead pre-specifies the experiment protocol.
- **Round 2**: Data analyst runs the full benchmark study. Theorist audits
  whether the measured rates match the proved bounds. Lead synthesizes findings.

## Required deliverables

### Data analyst MUST produce:

1. **Working implementation** — actual Python code that implements the method.
   Not pseudocode, not a description. Code that can be run to produce results.
2. **Diagnostic checks** — sanity checks with real measured values:
   - Known-answer tests (e.g., does the invariant measure match for a Gaussian?)
   - Conservation invariants
   - Reproducibility checks (same seed → same result)
   - Results recorded in a JSON file with actual numbers, not stubs
3. **Benchmark experiments** — actual experimental results:
   - Convergence curves (measured, not theoretical)
   - ESS/s comparison against baselines
   - Rate estimation (does the measured spectral gap match the proved bound?)
   - Tables and figures with real data
4. **Reproducibility record** — seeds, code paths, commands, hardware.

### Theorist MUST produce:

1. **Implementation audit** — does the code correctly implement the mathematical
   definition from Phase 3? Identify any discrepancies.
2. **Rate validation** — do the measured convergence rates match the proved
   bounds from Phase 3? If the theory predicts λ ≥ f(params), does the measured
   λ satisfy this?
3. **Discrepancy analysis** — if theory and experiment disagree, identify why:
   finite-N effects? step-size effects? implementation bug?

### Lead MUST produce:

1. **Experiment protocol** — what experiments will test, specified before the
   results are known.
2. **Synthesis** — what was validated, what was challenged, what remains open.
3. **Recommendation** — is the method empirically supported?

## Scientific integrity requirements

1. **Pre-specify before running**: the lead states what experiments will test
   and what results would support or contradict the claims, BEFORE the analyst
   runs them.
2. **Diagnostic checks first**: simple known-answer cases before complex
   benchmarks.
3. **Quantify uncertainty**: MCSE, confidence intervals, number of replications
   for every empirical claim.
4. **Report negative results honestly**: if the method underperforms, say so
   with specific numbers.
5. **Record reproducibility info**: seeds, versions, commands.

## Prior information
Requires a current Phase 03 summary approved by the user (contains the proved
theorems and rate bounds). Phases 01 (literature) and 02 (methods) are also
provided.

**On rerun:** the prior Phase 04 run is provided as **comparison evidence** —
"here is the implementation, the experiments, and what was measured before." The
new run must **improve on it**, not merely repeat it:

- **Fix bugs**: if the prior implementation had errors identified in the audit,
  correct them and rerun the affected experiments.
- **Extend experiments**: if the prior run tested only some targets or parameter
  settings, test additional ones.
- **Strengthen results**: if the prior measured rates were close to the bound,
  run more replications to tighten the estimate. If the prior ESS/s improvement
  was marginal, test at larger N or different graph structures.
- **Close gaps**: if the prior run left diagnostics incomplete or experiments
  untested, complete them.
- **Improve code**: if the prior implementation was inefficient or unstable,
  optimize it and rerun.

The prior run's code and results are starting material, not a constraint. The
new run should read them carefully and build on them. Re-running the same
experiments from scratch without improvement is not useful.

## Files and outputs
Write all outputs under `draft/sections/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, ...: per-round reports
- The data analyst's code files live alongside the report
- Write the HTML summary to the exact path provided for this run.

## What the user decides
The user starts every run. After the experiments, the lead presents the findings
and a recommendation. The user decides:

- to proceed to Phase 05 (Paper Assembly & Review);
- to request a revision (e.g., run additional experiments);
- to return to Phase 03 (if the experiments revealed a theory gap);
- or to rerun with different experimental settings.

## Files in this folder
- `_lead.md`: instructions for the research lead.
- `data_scientist.md`: implementation and experiment instructions.
- `theorist.md`: implementation and result audit instructions.
- `research_lead.md`: protocol and synthesis instructions.
