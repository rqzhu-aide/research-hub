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
Requires a current Phase 01 summary approved by the user. If that summary is
unavailable, the web UI identifies the missing prior evidence, but the user may
choose to proceed. The lead must then state what prior evidence is unavailable.

**On rerun:** the current published Phase 02 menu is the starting catalog, and
older runs are comparison evidence. Re-evaluate every current method, preserve
stable identities and numbers, and generate fresh ideas where the scientific
question supports them. Existing methods may be refined, merged, retained, or
retired. The team should think broadly again without discarding provenance.
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
