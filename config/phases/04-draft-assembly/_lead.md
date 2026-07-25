# Lead Instructions: Implementation & Experiments

Coordinate the implementation and experimental validation phase. Your job is to
ensure experiments are pre-specified, honestly run, and that the results are
synthesized with integrity.

## Step 1: Read prior context
Read:
- `setting.md`
- the approved Phase 03 summary (proved theorems and rate bounds)
- the approved Phase 02 summary (method definition)
- the approved Phase 01 summary (literature, for baselines)
- prior `draft/sections/` runs

## Step 2: Round 1 — pre-specify and implement
Dispatch tasks:

1. **You (lead)**: write the experiment protocol. State:
   - What metrics will be computed (ESS/s, IAT, KL divergence to target, etc.)
   - What comparisons (which baselines, which parameter settings)
   - What result would **support** the theoretical predictions
   - What result would **contradict** them
   - What targets will be tested (Gaussian, mixture, banana, etc.)

2. **Data analyst**: implement the method in code. Run diagnostic checks first
   (known-answer cases, invariants). Then run initial experiments.

3. **Theorist**: independently check the implementation against the Phase 3
   mathematical definition. Does the code compute what the theory describes?

## Step 3: Round 2 — full benchmark + audit
1. **Data analyst**: run the full benchmark study based on the lead's protocol.
   Produce tables and figures with real measured data.

2. **Theorist**: audit the results against the proved rate bounds from Phase 3.
   Does the measured spectral gap satisfy the proved lower bound? If not, why?

3. **You (lead)**: synthesize. What was validated? What was challenged? What
   remains open?

## Step 4: Final synthesis
Write the HTML summary. Present:

1. **Experiment protocol** — what was tested and why.
2. **Diagnostic results** — did the sanity checks pass?
3. **Benchmark results** — the key numbers, with uncertainty.
4. **Theory-experiment agreement** — do the measured rates match the proved
   bounds?
5. **What worked and what didn't** — honest assessment.
6. **Recommendation** — proceed to paper assembly, or what needs more work.

## Requirements
- The data analyst MUST produce working code. A report without actual code files
  is a Failed run.
- The data analyst MUST produce diagnostic results with real numbers. A stub
  JSON with zero values is a Failed run.
- Experiments MUST be pre-specified by the lead before the results are known.
- Negative results MUST be reported honestly with specific numbers.
- The theorist's audit is mandatory. If they find a discrepancy between code and
  math, it must be resolved.
