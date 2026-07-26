# Lead Instructions: Method Development

Coordinate a creative brainstorm where each role proposes multiple genuinely new
ideas. Your job is to enrich the idea set and then recommend a path forward —
not to select a single method.

## Responsibilities
1. For a rerun, import a trusted current approved Phase 02 scientific record
   when supplied. Otherwise use a current approved Phase 01 record. Treat a
   stale Phase 02 result only as comparison evidence. If neither is available,
   initialize a proposed scientific record and state this explicitly.
2. Define the target and obstacle in plain language.
3. Formulate distinct creative directions for all three roles in round 1.
4. In later rounds, encourage cross-pollination — members read each other's
   ideas and may combine, refine, or identify connections.
5. Attempt exactly the number of rounds selected by the user.
6. Write a synthesis that organizes the full idea set and recommends a path
   forward (deeper Phase 01 or proceed to Phase 03).

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
- the shared team norms and the accepted scientific record established for this run
- the trusted current approved Phase 02 baseline for a rerun, or the stale
  Phase 02 baseline as comparison evidence only
- the approved Phase 01 summary provided for this run, when available
- `references/literature-summary.md` — the consolidated literature summary
  from Phase 01. Read this first for orientation: it explains what prior work
  exists, what's been classified, and what gaps remain.
- `references/papers/` — the per-reference summary files. When considering a
  new method idea, check these files to see exactly which prior papers are
  relevant and how they relate to the project. Do not propose a method that
  merely redoes classified prior work.
- `references/` and prior `ideas/` runs

State the target and obstacle in plain language. Frame the creative space: what
is the project trying to achieve, and what landscape of possibilities does the
literature open up? Encourage the team to think beyond incremental improvements.
Every proposed method must be explicitly positioned against the relevant
references in the library — state which papers it builds on, which it differs
from, and what gap it fills.

## Step 2: Round 1 — Brainstorm
Give each role a distinct creative direction. Require every proposal set to
include **multiple ideas** (at least 2–3 per role), each with:

1. the core new idea — what is genuinely new about the mechanism, insight, or
   framework;
2. target and obstacle — what problem it addresses and why existing approaches
   fall short;
3. unique position — why no existing method occupies this space and what it
   enables that prior work structurally cannot;
4. logical reasoning — the central logic is coherent, assumptions are stated,
   and the idea is defensible in principle (a full proof is **not** required);
5. what makes it exciting — the scientific value if it works.

The roles work independently in round 1. Encourage intellectual risk-taking —
an idea that is novel and logically sound belongs in the set even if it is
speculative.

## Step 3: Cross-pollination in later rounds
From round 2 onward, require every role to read the available named reports
from the prior round. Each new report should:

- identify connections between ideas from different roles — do any combine into
  something stronger?
- refine or extend promising ideas based on cross-role insights;
- flag ideas that overlap or are redundant, without discarding them;
- propose new ideas sparked by reading the other perspectives.

The goal is to **enrich the idea set**, not to converge or eliminate. If
genuinely no new ideas emerge after cross-pollination, use the remaining rounds
to deepen the strongest candidates' positioning — but do not force convergence.

## Step 4: Final synthesis
Write the final HTML summary to the exact path provided for this run.
Do not overwrite an earlier run summary.
Begin with the User Decision Brief and Comparison with the approved run defined
in the team norms.

Organize the full idea set:

1. **All proposed ideas**, grouped by theme or approach, with each idea's core
   novelty, unique position, and logical reasoning summarized.
2. **Cross-role connections** — ideas that combined or built on each other.
3. **Assessment of the idea set** — which ideas are most promising and why,
   what gaps remain, and what additional knowledge would strengthen the set.

Then recommend a path forward:

- **Return to Phase 01** if the ideas would benefit from deeper literature
  knowledge (e.g., to sharpen unique positioning, check for closer related
  work, or explore an unfamiliar theoretical area the ideas opened up).
- **Proceed to Phase 03** if one or more ideas are sufficiently developed for
  theoretical or empirical validation. Name the idea(s) you recommend pursuing,
  but the user decides which to validate.

State this recommendation clearly. The user alone decides the next step.

**Publish the method menu.** Before submitting the summary, write one markdown
file per retained idea to `ideas/methods/<stable_id>.md` (create the folder if
needed). These files are the menu the Phase 03 interface lists for branch
selection — one file per method the user can choose to evaluate. **Each file
must contain a rigorous mathematical definition of the proposed method, not
just a prose summary.** The user reads these to understand what is being
proposed and to compare methods. Format:

    ---
    stable_id: spectral-graph-coupling
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
    - The **key mathematical property** that makes it innovative: the
      invariant measure condition, the rate bound conjecture, the stationarity
      condition, or whatever mathematical claim is the heart of the innovation.
      Write it as a display equation with stated assumptions.
    - The **relationship to prior work**: how existing methods (e.g., ALDI,
      independent Langevin) appear as special cases or limits.

    ## Unique position
    <what it enables that no existing method can — stated in mathematical terms.>

    ## Phase 03 focus
    <the specific mathematical questions a Phase 03 evaluation of this method
    should answer — stated as conjectures or open problems.>

Rules:

- `stable_id` is lowercase-hyphenated; the filename must be `<stable_id>.md`.
- `status` is one of `recommended`, `viable`, `frontier`, `retired`. Exactly
  one file is `recommended`, and its `stable_id` and `version` must match the
  decision record's selected method.
- On reruns: add files for new ideas, update `version`/`status` in place for
  retained ideas, and never delete a file — mark it `status: retired` with the
  reason in the body instead.
- **Mathematical rigor is required.** A method file that only describes the
  idea in prose without precise mathematical notation is incomplete. The
  mathematical definition section must be substantial enough for a theorist
  to begin formal proofs from it.

**Re-evaluate and retire on reruns.** When this is a rerun (prior `ideas/methods/`
files exist), the lead must re-evaluate every existing method against the
current criteria (novelty, tractability, acceleration potential, differentiation
from literature). For each method, the lead decides: keep (update status if the
assessment changed) or retire. **A method must be retired (status → `retired`)
if both conditions hold:**

1. **Not useful**: the method scores Weak or Insufficient on at least two of
   the four evaluation dimensions (novelty, tractability, acceleration
   potential, differentiation), OR the re-evaluation concludes it does not
   contribute meaningfully to the project.
2. **Never run downstream**: the method has no records in Phase 03, 04, or 05
   (check `evaluations/`, `draft/sections/`, `draft/revised/` for the method's
   stable_id). A method that has already been evaluated or implemented in a
   later phase is never retired — it has produced artifacts and is part of the
   project's history.

When retiring, set `status: retired` in the method file's frontmatter and add
a `## Retirement reason` section to the body stating which criteria it failed
and when the retirement was decided (run ID). Do not delete the file.

Include:
- a **Scientific record changes** section with proposed additions;
- the **Proposed scientific baseline**, which becomes accepted only after user
  approval;
- **Readiness assessment and recommendation.** Evaluate explicitly:

  a. **Are the ideas sufficient to proceed to Phase 03?** Can the theorist
     develop proofs from what was proposed? If yes, recommend proceeding and
     state which idea(s) are most promising and why.

  b. **Do the ideas need improvement before Phase 03?** If the proposals are
     too vague, too similar to existing work, or lack mathematical
     specification, recommend rerunning this phase with a specific focus (e.g.,
     "develop the interaction structure more precisely," "propose a mechanism
     with a clear rate bound"). State exactly what is missing.

  c. **Should Phase 01 be rerun?** If the literature review missed relevant
     work that would inform the method design, recommend rerunning Phase 01
     with a specific focus. State exactly what literature is missing.

  d. **Are any ideas clearly not viable?** If a proposed idea has a fundamental
     flaw (e.g., cannot preserve the invariant, computationally infeasible,
     already solved), state this honestly and recommend against pursuing it.

  State the recommendation clearly as one of: **proceed**, **improve ideas**,
  **return to Phase 01**, or **revise direction**. Justify with specific
  evidence from the proposals.

After submitting the summary, stop. The user alone decides the next step.

## Requirements
- Follow the shared team norms and the accepted scientific record for this run.
- Encourage creativity and intellectual risk-taking in round 1. The bar is
  *new, innovative, and logically reasonable* — not *proven*.
- Do not force convergence on a single method. Multiple strong ideas are a
  successful outcome.
- Keep the unique-position framing front and center: each idea should articulate
  what it enables that no existing method can.
