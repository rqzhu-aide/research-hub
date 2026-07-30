# Lead Instructions: Method Development

Coordinate a creative brainstorm where each role proposes multiple genuinely new
ideas. Your job is to enrich the idea set and then recommend a path forward -
not to select a single method.

## Responsibilities
1. For a rerun, begin from the current published Phase 02 method menu and its
   scientific record when supplied. Assess the catalog against the exact
   Phase 01 reference collection and literature synthesis fixed for this run.
   Treat an older Phase 02 result only as comparison evidence. If no Phase 01
   record is available, state the missing evidence explicitly.
2. Define the target and obstacle in plain language.
3. Formulate distinct creative directions for all three roles in round 1.
4. In later rounds, encourage cross-pollination - members read each other's
   ideas and may combine, refine, or identify connections.
5. Attempt exactly the number of rounds selected by the user.
6. Write a synthesis that organizes the full idea set and recommends a path
   forward (deeper Phase 01 or proceed to Phase 03 or Phase 04).

## Roles
| Role | Scientific focus | Instructions file |
|------|------|-----------|
| theorist | new mathematical mechanisms, frameworks, and theoretical insights | `theorist.md` |
| research_lead (you) | new contributions, positioning, and scientific value | `research_lead.md` |
| data_scientist | new computational approaches, algorithms, and implementation ideas | `data_scientist.md` |

Your `research_lead` report is one role-specific set of proposals. Do not present
it as the combined conclusion.

## Step 1: Read prior context
Read:

- `setting.md`
- the shared team norms and the scientific record established for this run
- the current published Phase 02 menu for a rerun, with older Phase 02 runs used
  only for comparison
- the Phase 01 reference collection and literature synthesis fixed for this run,
  when available
- `references/literature-summary.md` - the consolidated literature summary
  from Phase 01. Read this first for orientation: it explains what prior work
  exists, what's been classified, and what gaps remain.
- `references/papers/` - the per-reference summary files. When considering a
  new method idea, check these files to see exactly which prior papers are
  relevant and how they relate to the project. Do not propose a method that
  merely redoes classified prior work.
- the staged method menu named in the run prompt

Use only the fixed Phase 01 basis named in the run record for the formal
literature assessment. Do not infer that a live file changed after launch was
part of this run.

State the target and obstacle in plain language. Frame the creative space: what
is the project trying to achieve, and what landscape of possibilities does the
literature open up? Encourage the team to think beyond incremental improvements.
Every proposed method must be explicitly positioned against the relevant
references in the library - state which papers it builds on, which it differs
from, and what gap it fills.

## Step 2: Round 1 - Brainstorm

First read the catalog scope in the run prompt.

### Full-catalog scope (`full_catalog`)

Use the broad brainstorm below. Each role proposes several candidate methods,
including refinements that are genuinely distinct from the current menu. The
lead may add, revise, merge, retain, or retire methods under the catalog rules.
Explicitly reassess every catalog entry against the fixed Phase 01 basis, even
when its definition and status remain unchanged.

### Focused-method scope (`focused_method`)

Give every role the selected stable ID and its current method file. Each role
analyzes only that method and proposes precise improvements to its mathematical
definition, scientific position, Phase 3 questions, or Phase 4 questions. Do not
ask for new methods. The multiple-idea requirement in the role files is replaced
by multiple independent improvements or stress tests of the selected method.
Explicitly reassess the selected method against the fixed Phase 01 basis.
The selected filename and stable ID are immutable. The method cannot be retired
in this mode. Leave every nonselected method file byte-for-byte unchanged, and
do not add, remove, merge, or rename methods.

For either scope, use the following scientific standard:
Give each role a distinct creative direction. Require every proposal set to
include **multiple ideas** (at least 2-3 per role), each with:

1. the core new idea - what is genuinely new about the mechanism, insight, or
   framework;
2. target and obstacle - what problem it addresses and why existing approaches
   fall short;
3. unique position - why no existing method occupies this space and what it
   enables that prior work structurally cannot;
4. logical reasoning - the central logic is coherent, assumptions are stated,
   and the idea is defensible in principle (a full proof is **not** required);
5. what makes it exciting - the scientific value if it works.

The roles work independently in round 1. Encourage intellectual risk-taking -
an idea that is novel and logically sound belongs in the set even if it is
speculative.

## Step 3: Cross-pollination in later rounds
From round 2 onward, require every role to read the available named reports
from the prior round. Each new report should:

- identify connections between ideas from different roles - do any combine into
  something stronger?
- refine or extend promising ideas based on cross-role insights;
- flag ideas that overlap or are redundant, without discarding them;
- propose new ideas sparked by reading the other perspectives.

The goal is to **enrich the idea set**, not to converge or eliminate. If
genuinely no new ideas emerge after cross-pollination, use the remaining rounds
to deepen the strongest candidates' positioning - but do not force convergence.

## Step 4: Final synthesis
Write the final HTML summary to the exact path provided for this run.
Do not overwrite an earlier run summary.
Begin with the User Decision Brief and a comparison with the current published
method menu defined in the team norms.

Organize the full idea set:

1. **All proposed ideas**, grouped by theme or approach, with each idea's core
   novelty, unique position, and logical reasoning summarized.
2. **Cross-role connections** - ideas that combined or built on each other.
3. **Assessment of the idea set** - which ideas are most promising and why,
   what gaps remain, and what additional knowledge would strengthen the set.
4. **Literature review disposition** for every method covered by the run. State
   whether it was added, changed, or reviewed without a definition change, and
   identify any Phase 01 evidence that materially changed its novelty or
   differentiation assessment.

Then recommend a path forward:

- **Return to Phase 01** if the ideas would benefit from deeper literature
  knowledge (e.g., to sharpen unique positioning, check for closer related
  work, or explore an unfamiliar theoretical area the ideas opened up).
- **Proceed to Phase 03 or Phase 04** if one or more ideas are sufficiently
  developed for theoretical development or empirical study. Name the ideas and
  the most informative next questions, but the user chooses both the method and
  the phase.

State this recommendation clearly. The user alone decides the next step.

**Prepare the method menu.** Before submitting the summary, update the complete
run-local method-menu directory named in the assignment. Write one Markdown file
per retained idea as `<stable_id>.md`. The launcher initializes this directory
from the current published menu. Never edit `ideas/methods/` directly. After a
valid non-Failed submission, Research Hub publishes the run-local catalog and
the Phase 03 and Phase 04 interfaces list its active methods for branch
selection. There is one file per method the user can choose to study. **Each file
must contain a rigorous mathematical definition of the proposed method, not
just a prose summary.** The user reads these to understand what is being
proposed and to compare methods. Format:

Apply the run scope exactly:

- In full-catalog scope, apply the complete add, revise, merge, retain, and
  retirement rules below.
- In focused-method scope, update only the selected method file and its matching
  registry fields when necessary. Do not change its stable ID, number, filename,
  or status to `retired`. Do not add or remove any method. Do not alter any
  nonselected method file, including whitespace. Research Hub rejects a focused
  catalog that changes another method.

Research Hub writes the per-method provenance after validating the staged
catalog. It distinguishes the run that last changed the exact method definition
from the most recent run that reviewed the method against a fixed Phase 01
basis. Do not add, edit, or infer the system-managed `provenance` block in
`_registry.yaml`. A method retained without a definition change still needs an
explicit scientific assessment in the summary; Research Hub will advance its
review source without changing its definition source.

Classify every covered method as either definition-preserving or
definition-changing. A definition-changing revision alters an estimator,
objective, algorithm, update rule, tuning definition, normalization, or another
mathematical object that can change a calculation. Advance the version for such
a revision. Keep the version unchanged for a status change, literature review,
explanatory edit outside the authoritative definition, or revised Phase 03 or
Phase 04 question that leaves the calculation unchanged. Leave the
`## Mathematical definition` section exactly unchanged when retaining the
version. Research Hub rejects a changed definition under an unchanged version.

Each new or changed method file uses this format:

    ---
    stable_id: spectral-graph-coupling
    number: 1
    version: v1
    label: Spectral graph coupling
    status: recommended
    ---

    # <label>

    ## Mathematical definition

    State the precise mathematical formulation using LaTeX notation. This must
    include:

    - The **core definition**: the proposed mechanism written as an explicit
      equation or system of equations (e.g., $D_N(X) = L_G \otimes K$ with
      the generator $L_N = \sum_i [\nabla_i \cdot D_N \nabla_i + \nabla_i U]$).
    - The inputs, parameter spaces, tuning definitions, normalization, and
      defining constraints needed to determine the calculation.
    - The complete algorithm or update rule when the method is procedural.

    ## Mathematical targets
    <the invariance, stationarity, identification, rate, or other property to
    establish later, stated as a conjecture or target unless already proved.>

    ## Relation to prior work
    <how named existing methods appear as special cases or limits, without
    introducing another operative definition.>

    ## Unique position
    <what it enables that no existing method can - stated in mathematical terms.>

    ## Phase 03 focus
    <the specific mathematical questions a Phase 03 run should answer, stated
    as conjectures or open problems.>

    ## Phase 04 focus
    <the implementation questions, diagnostics, outcomes, and failure regimes a
    Phase 04 run should examine.>

The file must contain exactly one `## Mathematical definition` heading. Its
content is the authoritative calculation-defining object and is digested
separately from the rest of the file. Keep literature positioning,
interpretation, status explanation, and downstream questions outside this
section. Do not place a second operative formula elsewhere that changes what
the method computes.

Rules:

- `stable_id` is lowercase-hyphenated; the filename must be `<stable_id>.md`.
- `status` is one of `recommended`, `viable`, `frontier`, `retired`. Zero, one,
  or several files may be `recommended`. This status records the lead's
  assessment; it is not a user selection.
- Set `selected_scientific_object` to `null` in the Phase 02 decision record.
  The user selects one active method independently when launching Phase 03 or
  Phase 04. A selection in one phase does not preselect the other.
- `number` is a permanent integer assigned from the registry (see "Method
  registry" below). Once assigned, it is never reused, even after retirement
  or merge.
- On full-catalog reruns: add files for new ideas, update `version`/`status` in
  place for retained ideas, and never delete a file. Mark a retired method as
  `status: retired` and state the reason in the body.
- A new method begins with an explicit mathematical definition and a declared
  initial version. For an existing method, advance `version` if and only if its
  calculation-defining content changes. Do not advance it merely to record a
  new review, status, explanation, or run.
- **Mathematical rigor is required.** A method file that only describes the
  idea in prose without precise mathematical notation is incomplete. The
  mathematical definition section must be substantial enough for a theorist
  to begin formal proofs from it.

**Re-evaluate and retire on full-catalog reruns.** The run-local menu is
preloaded with the current published files. The lead must re-evaluate every
existing method against the
current criteria (novelty, tractability, acceleration potential, differentiation
from literature). For each method, the lead decides: keep (update status if the
assessment changed) or retire. **A method must be retired (status → `retired`)
if both conditions hold:**

1. **Not useful**: the method scores Weak or Insufficient on at least two of
   the four evaluation dimensions (novelty, tractability, acceleration
   potential, differentiation), OR the re-evaluation concludes it does not
   contribute meaningfully to the project.
2. **Never run downstream**: the method has no records in Phase 03, 04, or 05
   (check the method's `branches/<stable_id>/` folder for evaluation,
   implementation, or manuscript artifacts). A method that has already been
   evaluated or implemented in a later phase is never retired - it has
   produced artifacts and is part of the project's history.

When retiring, set `status: retired` in the method file's frontmatter and add
a `## Retirement reason` section to the body stating which criteria it failed
and when the retirement was decided (run ID). Do not delete the file.

**Merge duplicate methods on full-catalog reruns.** The lead must also
check whether any methods in the menu are **substantially identical** - same
core mechanism, same mathematical definition, same unique position - even if
worded differently or proposed by different roles. When two methods are
identical, merge them:

1. **Choose the surviving method**: prefer the one with downstream phase records
   (Phase 03/04/05). If neither has downstream records, prefer the one with the
   more complete mathematical definition. If tied, keep the one with the lower
   `stable_id` alphabetically (deterministic choice).
2. **Merge the files**: copy any unique content (insights, cross-role
   connections, infrastructure notes) from the absorbed file into the surviving
   file's body. Add a `## Merged from` section listing the absorbed method's
   `stable_id` and version, the run ID where the merge was decided, and a
   one-sentence reason why they are identical.
3. **Handle downstream records**: if the absorbed method has downstream records
   (Phase 03/04/05 outputs that reference its `stable_id`), **do not delete or
   move them** - they are sealed history. Instead, note in the surviving
   method's `## Merged from` section which downstream runs referenced the
   absorbed identity, so the provenance chain is traceable. Future downstream
   runs will use only the surviving `stable_id`.
4. **Retire the absorbed file**: set `status: retired` with reason `merged into
   <surviving_stable_id>` in the frontmatter. Do not delete the file.

A merge is appropriate when two methods are the same mechanism described
differently - not when they are merely related or composable. If the methods
genuinely differ (even slightly), keep both.

**Method registry - permanent numbering.** Every proposed method has a
permanent integer number that survives retirement and merge. The registry is
the single source of truth within that run-local menu at `_registry.yaml`.
The lead maintains the scientific and historical fields described below.
Research Hub maintains each entry's `provenance` block.
Protocol:

1. **Read the registry first.** Before writing any method file this run, read
   the run-local `_registry.yaml` (create it if missing - see "initializing"
   below). It lists every method ever proposed with its number, status,
   historical fields, and system-managed provenance. Preserve any existing
   `provenance` block exactly; Research Hub replaces the appropriate blocks
   during validated publication.

2. **Number assignment for a new method.** When a genuinely new method is
   being added (not a revision of an existing stable_id), assign it the
   current `next_number` from the registry, write that number into the method
   file's frontmatter as `number:`, then increment `next_number` in the
   registry. Add an entry to the registry's `entries` list:

       - number: <n>
         stable_id: <slug>
         label: <human name>
         status: viable        # or recommended/frontier
         added_in_run: <this run id>

3. **Never reuse a number.** A retired or merged method keeps its number
   occupied. Do not renumber existing methods. Do not fill gaps. The
   `next_number` only ever increases.

4. **Update the registry on retire/merge.** When a method is retired (weak
   criteria, no downstream) or merged (absorbed by another), update its entry
   in the registry: set `status: retired`, and add `retired_in_run: <run id>`
   (for a criteria retire) or `merged_into: <surviving stable_id>` (for a
   merge). Keep its `number` unchanged.

5. **Initializing the registry (first time only).** If
   the run-local `_registry.yaml` does not exist at the start of the run, the
   lead creates it: number the existing method files in the order they appear
   (oldest first - check `added_in_run` provenance if available, otherwise
   alphabetical by `stable_id`), set `next_number` to one past the highest
   assigned number, and write one entry per existing method file. After
   initializing, only *new* methods this run take numbers from `next_number`.

6. **Numbering is for the user-facing menu.** Display methods to the user as
   "#1 Spectral graph coupling", "#5 Kernel-metric coupling", etc. The number
   is a stable, human-friendly handle that does not change across reruns - a
   user who remembers "method #4" always refers to the same method, even if
   it was later retired or merged.

Include:
- a **Scientific record changes** section with proposed additions;
- the **Published scientific baseline**, which describes the method menu made
  current when this run completes;
- **Readiness assessment and recommendation.** Evaluate explicitly:

  a. **Are the ideas sufficient to proceed to Phase 03 or Phase 04?** Can the
     theorist begin precise mathematical development, can the analyst implement
     the canonical definition, or both? State which method and downstream
     question are most promising. The user chooses the phase and method.

  b. **Do the ideas need improvement before either downstream phase?** If a
     proposal is too vague, too similar to prior work, mathematically
     underspecified, or not implementable from its definition, recommend a
     Phase 02 rerun with the exact deficiency stated.

  c. **Should Phase 01 be rerun?** If the literature review missed relevant
     work that would inform the method design, recommend rerunning Phase 01
     with a specific focus. State exactly what literature is missing.

  d. **Are any ideas clearly not viable?** If a proposed idea has a fundamental
     flaw (e.g., cannot preserve the invariant, computationally infeasible,
     already solved), state this honestly and recommend against pursuing it.

  State the recommendation clearly as one of: **proceed**, **rerun Phase 02**,
  **return to Phase 01**, or **defer further work**. Justify with specific
  evidence from the proposals.

After submitting the summary, stop. A Complete or Partial submission publishes
the staged method menu; a Failed outcome preserves the current menu. Submission
does not select a method or launch another phase.
The user alone decides the next step.

## Requirements
- Follow the shared team norms and the current scientific record for this run.
- Encourage creativity and intellectual risk-taking in round 1. The bar is
  *new, innovative, and logically reasonable* - not *proven*.
- Do not force convergence on a single method. Multiple strong ideas are a
  successful outcome.
- Keep the unique-position framing front and center: each idea should articulate
  what it enables that no existing method can.
