# Literature Review — Deep Run (context-aware)
## Role: Data Scientist

## First: read the current project state
Read what the project has built so far:
- `numerical/` — code, experiments, results
- `draft/` — proposed method (for its implementation implications)
- `references/literature-review/run/` — prior runs

Identify: **what has been implemented? What data, optimization, and
numerical choices were made? Where are the bottlenecks?**

## What to search for (targeted)
1. **Same or similar data** — papers or projects using the same datasets or
   data regimes. Useful for baselines, preprocessing, and known pitfalls.

2. **Better optimization / numerical methods** — algorithms or tricks that
   could improve the performance, scalability, or stability of our
   implementation.

3. **Reusable packages and tools** — libraries that could replace or
   accelerate parts of our code.

## What to produce
Write to `{{output_path}}`:

1. **Implementation summary** (1 paragraph): your read of the project's
   current numerical and code state.

2. **Targeted resource list** (8-12 entries): for each — what it is and the
   specific improvement it offers (faster, more stable, replaces step X,
   provides baseline Y). Tag each `[data]`, `[optimization]`, `[tooling]`,
   or `[baseline]`.

3. **Engineering recommendations** (1-2 paragraphs): concrete and
   actionable — "swap solver X for Y, expect ~3× speedup", "dataset Z has
   the labels we're missing", "package P handles our edge case".

## Norm
Actionable. Every suggestion should have a clear "do this because…" attached.
