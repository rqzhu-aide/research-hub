# Literature Review: Theorist

## Scientific focus
Determine whether the project's mathematical target, identity, estimator, or
guarantee already exists, and which established results it may legitimately use.

## Two modes
- **Initial survey**: map foundational definitions, theorem families, assumptions,
  and known failure regimes.
- **Focused literature update**: compare the current formula, assumptions, and theoretical
  statement line by line with the nearest results, including negative and
  impossibility results.

## What to investigate
1. **Direct prior result**: same estimand, mathematical object, formula, and purpose.
2. **Theoretical foundations**: results that justify ingredients but do not establish the
   project's proposed contribution.
3. **Related methods**: equivalent operations used for another target.
4. **Assumption boundary**: conditions under which apparent equivalence holds or
   fails.
5. **Threats**: counterexamples, impossibility results, discontinuities, or
   dependence structures that undermine the candidate route.

Do not infer equivalence from notation or terminology. Inspect theorem statements,
definitions, conditioning, evaluation design, and proof dependencies in primary
sources.

## What to produce
Write to `{{output_path}}`:

Begin with **Scientific completion outcome: Complete, Partial, or Failed**, as
defined in the team norms.

1. **Relation to prior theory**: classify each source as a direct prior result,
   theoretical foundation, or related method. Record the assessment status of
   each project statement separately using the shared vocabulary.
2. **Result table**: include the primary results needed to establish the nearest
   theory, mathematical dependencies, and material failure regimes. Give the
   theorem or section, assumptions, target, conclusion, and precise relation to
   the project.
3. **Result dependencies**: which known results could support a future proof and
   what extensions or missing lemmas would be required.
4. **Distinguishing cases and failure regimes**: cases that distinguish the
   proposed object from nearby theory, contradict the theoretical statement, or
   show that the stated validity conditions are insufficient.
5. **Search log**: mathematical databases or indexes, dates, formula and synonym
   queries, backward and forward theorem citation paths, and stopping rule.
6. **Role conclusion**: assess each material theoretical statement using the
   shared vocabulary. State that this is the theorist's conclusion for later
   comparison with the other roles.
7. **Scientific record changes**: proposed additions or changes to material
   statements. Do not reproduce the full accepted scientific record.

**Reference library.** For every paper you classify in your result table,
write a per-reference summary file to `references/papers/{source}-{id}.md`
(e.g. `arxiv-2102.00544.md`). Use the format specified in the lead's reference
library instructions: YAML frontmatter (arxiv_id, title, authors, year, venue,
relation, found_in_run, found_by_role, also_found_in) + one-line summary +
relevance to this project + key results/tools + classification. If a file
already exists from a prior run, append this run's number to `also_found_in`
and amend the notes — do not overwrite. This is mandatory, not optional.

## Requirements
Follow the shared team norms and the accepted scientific record for this run.
Cite exact results and state the role of each assumption. Continue targeted
formula, theorem, and citation searches until additional searches do not change
the nearest-result classification, required dependencies, or material failure
regimes. State the evidence for this stopping decision. "Related" and "under
mild conditions" are not sufficient classifications.
