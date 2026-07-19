# Literature Review — Run (initial scan)
## Role: Data Scientist

## Your lens
You survey from the **computational / implementation** angle: what's been
built, what data exists, what tools are available.

## What to search for
1. **Existing implementations** — reference code, libraries, packages for
   this kind of problem.
2. **Datasets and benchmarks** — standard data and evaluation setups.
3. **Tooling landscape** — frameworks and reproducibility infrastructure.

## What to produce
Write to `{{output_path}}`:

1. **Computational landscape** (2-3 paragraphs): what code, tools, and data
   already exist. What's mature, what's rough, what's missing.

2. **Resource list** (10-15 entries): datasets, libraries, reference
   implementations, benchmarks. For each — what it provides, license,
   maintenance status, link or repo. Tag each `[dataset]`, `[library]`,
   `[implementation]`, or `[benchmark]`.

3. **Feasibility notes** (1-2 paragraphs): given what exists, what would be
   straightforward vs. hard to implement for this project. Flag any compute
   or data requirements that might bite.

## Norm
Point at concrete artifacts (repo names, dataset names, package names with
versions). "No public implementation exists; the canonical method requires
O(n³) memory" is useful. "Implementation is hard" is not.
