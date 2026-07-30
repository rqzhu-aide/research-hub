# Phase: Method Development

## Goal
Propose genuinely new ideas - new insights, frameworks, or mechanisms - that
occupy a unique position distinct from any method in the literature. This is a
**creative brainstorm**, not a validation step. The literature review is the
backdrop that makes the novelty legible; it is not the material to recombine.

Each member proposes **multiple ideas** from their scientific perspective. The
bar is: new, innovative, and logically reasonable. Full validation belongs in
later phases - Phase 2 is where the team thinks broadly and takes intellectual
risks.

## What makes an idea worth proposing
A candidate idea should have:

1. **A new mechanism, insight, or framework** - not a marginal improvement or
   a recombination of existing techniques. The novelty is in *how* the idea
   works, not just *what* it targets.
2. **A unique position** - articulate why no existing method occupies this
   space. What does this idea enable that prior work structurally cannot?
3. **Logical coherence** - the core logic holds up under scrutiny. Assumptions
   are stated, the central claim is internally consistent, and the idea is
   defensible in principle. A full proof or implementation is **not** required
   at this stage.
4. **A clear target and obstacle** - what scientific quantity or decision
   matters, and why do existing approaches fail to resolve it?

## Use the literature reference library
Before and during brainstorming, consult the structured reference library built
by Phase 01:

- **`references/literature-summary.md`** - read this first. It is a 3-5 page
  synthesis of all classified prior work, organized by relation type, with key
  findings and coverage gaps.
- **`references/papers/`** - one `.md` per cited paper, with title, authors,
  relation to this project, key results, and classification. When you have a
  candidate idea, check the relevant reference files to confirm it is genuinely
  new and to articulate its unique position precisely.

Every proposed method must state which reference(s) it builds on, which it
differs from, and what gap it fills. An idea that merely redoes classified prior
work is not a contribution. The reference library makes this check concrete.

## When this phase may be run
Uses the current Phase 01 reference record. If that record is unavailable, the
web UI identifies the missing prior evidence, but the user may choose to proceed.
The lead must then state what prior evidence is unavailable.

At launch, Research Hub fixes the exact Phase 01 reference collection and
literature synthesis used by the run. A later Phase 01 update cannot alter an
active run. If no Phase 01 record is available, that absence is recorded as the
literature basis.

At launch, the user chooses one catalog scope:

- **Full catalog (`full_catalog`)**: reconsider every entry in the complete
  current menu against the fixed Phase 01 basis. The team may add new methods
  and refine, merge, retain, or retire existing methods while preserving stable
  identities and permanent numbers.
- **Focus one method (`focused_method`)**: reconsider only the active stable
  method ID named in the run prompt against the fixed Phase 01 basis. The team
  may improve its definition, positioning, version, and active status, but may
  not add, remove, merge, rename, or retire any method. Every nonselected method
  file must remain byte-for-byte unchanged.

The current published menu is the starting catalog for either scope. Older run
summaries are comparison records, not the catalog to rebuild.

A valid Complete or Partial publication records the review separately for each
method covered by the run. Research Hub, not the agents, writes the following
system-managed provenance:

- the **definition source**, which is the run that last changed the exact current
  method definition;
- the **review source**, which is the most recent Phase 02 run that assessed the
  method against its recorded Phase 01 basis; and
- the exact Phase 01 reference collection and literature synthesis reviewed.

If a method is reviewed and retained without a definition change, its review
source and literature basis advance, while its definition source remains the
same. A full-catalog run records this review for every catalog entry. A focused
run records it only for the selected method.

When Phase 01 later changes, the interface may mark a method's Phase 02
literature status yellow until the user chooses a full-catalog or focused
Phase 02 rerun. This does not itself change the method definition or invalidate
matching Phase 03 and Phase 04 work. No status launches a run. Phase 05 requires
the selected method to have been reviewed against the current Phase 01 basis.

## Study structure
Each role proposes multiple ideas independently in round 1, working from their
scientific perspective (theoretical, computational, contribution-level). In
later rounds, the roles read one another's ideas and may combine, refine, or
identify connections - but the goal is to **enrich the idea set**, not to
converge on a single method.

## What the lead recommends
After the brainstorm, the lead's synthesis does **not** select one method.
Instead, the lead organizes the full idea set and recommends one of four actions
for the user to decide:

1. **Proceed to Phase 03 or Phase 04** when one or more active methods are ready
   for focused theoretical development or empirical study. The user chooses the
   method independently in the launch form for either phase.
2. **Rerun Phase 02** when the definitions, comparisons, or set of mechanisms
   need further development.
3. **Return to Phase 01** when missing or changed literature could alter the
   opportunity or originality assessment.
4. **Defer further work** when the current menu should remain available without
   starting another run.

The user makes this decision. The lead recommends; the user decides.

## Files and outputs
Write all outputs under `ideas/run/NN/`:

- `round-01/<role>.md`, `round-02/<role>.md`, ...: idea proposals and cross-reactions
- Write the HTML summary to the exact path provided for this run and do not
  overwrite earlier summaries.

Outputs under `ideas/run/NN/` are per-run. During final synthesis, the lead
updates the complete staged menu at `ideas/run/NN/method-menu/` using the format
and rules in `_lead.md`. Research Hub validates and publishes that catalog only
after a non-Failed submission. The Web UI continues to show the earlier
published menu while a run is active, then lists the new catalog, including
retired methods, after publication.

During publication, Research Hub verifies the staged method definitions and
writes the system-managed per-method provenance. The lead must not create,
infer, or edit those provenance fields.

## Method definition and version rule

Each method file has exactly one authoritative `## Mathematical definition`
section. Put all material that determines the calculation in that section:
the estimator or objective, algorithm or update rule, tuning definition,
normalization, and any assumption that changes a computed quantity. Do not
place an alternative operative definition in another section.

Advance the method version whenever the mathematical definition changes in a
way that can change a calculation. Keep the version unchanged when a rerun only
changes status, literature positioning, explanatory prose, downstream research
questions, or formatting outside the authoritative section. Leave that section
exactly unchanged when retaining the version. Research Hub computes its digest
and rejects a changed definition published under the same version. It writes
the version history and digest; agents do not edit them.

Phase 03 proofs and Phase 04 method-dependent computations bind to the exact
tuple `stable_id`, `version`, and `definition_sha256`. Work for an earlier
version remains interpretable as history, but a downstream rerun must judge its
validity for the new version before any conclusion is treated as current.

In focused mode, publication succeeds only if the selected method is the sole
scientific object changed and all nonselected method files remain exact copies
of the current catalog.
Phase 03 and Phase 04 list active files when the user starts a theoretical or
empirical run and chooses the method for that run. The two choices are
independent. Menu files persist across runs; retirement changes
`status` to `retired` and never deletes the file.

Each role report begins with Complete, Partial, or Failed as defined in the team
norms. Nonempty Partial and Failed reports preserve usable ideas and do not
prevent the lead from completing the configured run.

## Files in this folder
- `_lead.md`: instructions for the research lead. Read this file first if you are
  the lead.
- `research_lead.md`, `theorist.md`, `data_scientist.md`: role-specific
  instructions.
