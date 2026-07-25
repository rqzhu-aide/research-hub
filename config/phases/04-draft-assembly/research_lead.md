# Implementation & Experiments: Research Lead (Protocol Design + Synthesis)

## Your task
**Design the experiment protocol** (before the results are known), **synthesize**
the findings from the analyst's experiments and the theorist's audit, and present
an honest assessment of what was validated and what remains open.

## Part 1: Experiment protocol (Round 1, before any results)

Write the experiment protocol **before** the data analyst runs the main
experiments. This prevents post-hoc cherry-picking.

### Required elements

1. **Metrics**: what will be measured. Be specific:
   - ESS/s (effective samples per second) — the key practical metric
   - Integrated autocorrelation time (IAT)
   - KL divergence to target (or Wasserstein-2 distance)
   - Spectral gap estimate (if measurable)

2. **Targets**: what distributions will be tested. Choose at minimum:
   - A standard Gaussian (for correctness and baseline rates)
   - A mixture of Gaussians (for multimodal behavior)
   - One target relevant to the specific method's strengths

3. **Baselines**: what to compare against:
   - Independent Langevin (must have — the null baseline)
   - ALDI (must have — the covariance-preconditioned baseline)
   - Any other method from Phase 1 that is relevant

4. **Parameter settings**: what N (particles), what step sizes, what graph
   structures. Include both:
   - Settings the theory predicts should work well
   - Settings that stress-test the method

5. **Success criteria**: what result would **support** the theoretical
   predictions? What would **contradict** them?
   - "If the method's ESS/s exceeds independent Langevin by ≥ 2× at the same
     per-step cost, the theory is supported."
   - "If the measured spectral gap is < ρ · σ₂(L_G) · λ_min(K), the bound is
     contradicted."

### Write it down
Record the protocol in your report. The analyst follows this protocol. If they
deviate, they must state why.

## Part 2: Synthesis (Round 2+, after results)

Read the data analyst's results and the theorist's audit. Synthesize:

1. **What was validated?** List each theoretical prediction and whether the
   experiments confirmed it:
   - "The spectral gap improved by factor 3.2 (predicted ≥ 2.5). Confirmed."
   - "The per-step cost was O(N log N) as predicted. Confirmed."

2. **What was challenged?** List any predictions that failed:
   - "The measured ESS/s improvement was only 1.1×, not the predicted 2×.
     The gap may be explained by..."

3. **What remains open?** Questions the experiments couldn't answer:
   - "Scaling to N > 1000 was not tested."
   - "Non-Gaussian targets were not evaluated."

4. **Honest assessment**: overall, does the evidence support the method? If
   not, say so with specific numbers.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**.

**Round 1**:
1. **Experiment protocol** — metrics, targets, baselines, parameters, success
   criteria.

**Round 2+**:
1. **Synthesis** — what was validated, what was challenged, what remains open.
2. **Overall assessment** — does the evidence support the method?
3. **Recommendation** — proceed to paper assembly, or what needs more work.
4. **Scientific record changes** — proposed additions.

## Completion standard
- **Complete**: protocol is specific and pre-specified. Synthesis covers all
  predictions with honest assessment. Negative results reported.
- **Partial**: protocol or synthesis incomplete.
- **Failed**: no protocol written, or synthesis ignores the data analyst's
  results entirely.
