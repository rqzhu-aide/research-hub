# Shared Research Standards

Condensed operational rules. Controlled vocabularies below are exact —
validation rejects anything else. Phase-specific detail lives in each phase's
playbook; this file defines only the shared contract.

## User decisions

- Only the user starts a phase or rerun, sets round count, chooses a method for
  a method-bound run, selects run scope and optional context, overrides a
  recommended prerequisite, or chooses the next phase.
- Work only within the launched run. On completion, submit the result and stop.
  A valid result may update its phase's canonical record, but no submission
  starts another phase or makes a downstream scientific decision.
- Always end with the phase-appropriate options for the user: proceed, rerun,
  return to an earlier phase, revise, or defer — with consequences.
- User direction refines scientific focus; it never transfers the user's
  decisions to an agent.

## Evidence discipline

- Read the supplied materials and prior-round reports before acting.
- Separate inherited facts, new observations, assumptions, hypotheses,
  interpretations, recommendations, and user decisions.
- Before comparing or synthesizing, state what is supported, disputed, and
  missing. If sources conflict, report the conflict and the source behind each
  conclusion; never blend incompatible versions into a false consensus.
- Never invent a citation, theorem, datum, result, file, or completed check.
- Never silently alter, replace, or ignore missing, corrupt, outdated, or
  inconsistent input. State the problem and its scientific consequence.

## Statement vocabulary (exact terms)

Statement types: **Definition or methodological statement**, **Mathematical
statement**, **Empirical statement**, **Interpretive**, **Originality**,
**Scientific importance**.

Formulation states: **Proposed** (staged this run), **Current** (in the
canonical record), **Superseded** (replaced by a valid current result),
**Withdrawn** (explicitly removed without replacement; preserves ID and
history, not a contradiction verdict).

Assessment statuses: **Supported**, **Partially supported**, **Contradicted**,
**Inconclusive**, **Not assessable**, **Untested**. Record separately the
evidential basis (definition/exact calculation, mathematical derivation,
empirical/numerical result, heuristic argument) and provenance (project result
with path, primary external source, secondary external source, none).

For mathematical statements also record: **logical status** (proved,
conjectured, unproved, refuted by a counterexample), **result type** (identity
or exact calculation, finite-sample equality, inequality or bound,
approximation with stated remainder, asymptotic limit/rate/distribution), and
**assumptions and scope**. Use **open question** for unresolved questions, not
as a logical status. No other field substitutes for the assessment status.

## Canonical current records

Canonical current records drive decisions; run records are immutable
provenance. Failed, invalid, or incomplete work never displaces a valid
current record. Record update is an automatic lifecycle operation.

- **P1 literature:** cumulative library. A run stages `reference-delta/` (new
  cards + complete current synthesis). Promotion never replaces cards and
  rejects duplicate identities.
- **P2 methods:** the published menu is the catalog. Full-catalog runs may add,
  revise, merge, retain, retire. Focused runs change only the selected method —
  all other files byte-for-byte unchanged. P2 never selects a downstream
  method; a `recommended` status is advice only.
- **P2 versions:** each method file has exactly one authoritative
  `## Mathematical definition` section holding every calculation-defining
  object. Advance the version only when that section changes mathematically;
  the Hub computes the definition digest and version history.
- **P3 theory:** one complete current `theory-manuscript.md` per method,
  replaced atomically by a valid Complete run. Archived P3 summaries enter
  context only via the explicit launch option.
- **P4 empirical:** one cumulative `evidence-index.json` +
  `empirical-synthesis.md` per method. Outputs bind to the exact method
  version and become `outdated` after a calculation-defining revision.
  Reanalysis gets a new evidence ID; an old ID never returns to `current`.
- **P5 manuscript:** one current `manuscript.md` per branch, updated in place
  by atomic replacement. Reviews and summaries stay immutable; old generations
  are not normal inputs.

Use the exact records supplied in the manifest; preserve identities and record
conflicts rather than blending. An audit/review run preserves every unaffected
statement and stable ID, applies only supported changes, and records the
source as **current** or **historical**.

## Statement records and operations

Each statement record: stable never-reused ID, type, exact wording and scope,
formulation state, assessment status, evidential basis, provenance, assumptions
and uncertainty, parent/replaced ID, originating phase and run. Mint IDs as
`S-P02-R003-round02-theorist-001`; never renumber or reuse.

- Same ID only when evidence, assessment, or uncertainty changes. A wording or
  scope change is a new statement (operation `add`, new ID, preceding ID as
  `parent_statement_id`).
- `revise` = same-ID change with wording and scope unchanged. `withdraw` =
  existing ID with proposed state Withdrawn.
- Role reports contain **Scientific record changes** (compact per-statement
  deltas: ID, operation, changed fields, basis, reason), not record
  reconstructions. State `No change to the scientific record` when appropriate.
- Final summaries reconcile role changes, record unresolved conflicts, and
  carry the **Current scientific record** table (P2 instead carries the
  **Published method menu**).
- Cite exact project paths for project sources. Unsupported factual claims are
  labeled assumption, hypothesis, interpretation, or recommendation.

## Criticism and prior-round use

- Address the argument, not the person; name the statement at issue. Classify
  each concern: **invalidates a central conclusion**, **narrows scope or
  interpretation**, **affects presentation only**, or **optional improvement**.
  Propose a correction or discriminating test. Never ignore substantive
  criticism; report null results and problems in your own earlier work.
- Every role report opens with one scientific completion outcome — **Complete**,
  **Partial**, or **Failed** — and, when later rounds use it, states what
  changed and which assumptions, limitations, failures, and disagreements
  remain. Partial/Failed reports still state what was attempted, completed,
  usable, and missing with causes; later roles use only the supported content
  and mark dependent conclusions Not assessable. A missing artifact is a
  technical failure (recover or rerun via the Web UI), not a Failed outcome.
- Examine a report's underlying evidence before relying on it.

## User Decision Brief and decision record

Every final summary opens with a **User Decision Brief**: (1) decision
requested, (2) most defensible conclusion and recommendation, (3) main
evidence, (4) principal unresolved risk, (5) smallest result that would change
the recommendation, (6) consequences of each phase-appropriate option including
carried-forward limitations, (7) the exact rerun question. Follow it with the
**Comparison with the current record** (P2: **Comparison with the current
menu**), or state this is the initial run. The brief informs; it never decides.

The structured decision record must state the same outcome, decision,
recommendation, evidence, risk, decision changer, option consequences, rerun
question, record changes, and comparison as the summary.

Method selection is a launch input: the exact tuple `stable_id`, `version`,
`definition_sha256` is frozen at launch; no role may substitute or infer it.
Outside P2 the catalog is read-only. After a calculation-defining P2 revision,
earlier P3/P4 work is historical — not current support merely because the
stable ID is unchanged.

## Separate status judgments

Report separately: (1) **method and basis alignment** (exact identity and
sibling basis), (2) **research attention** (outdated/unresolved P4 evidence),
(3) **scientific completion outcome**. Alignment does not establish validity;
attention does not change completion; a Complete run can produce weak evidence
and a Partial run can hold valid current results.

## Phase 03/04 sibling workflow

P3 and P4 are independent after P2; neither gates the other; both write to the
selected method branch. Fixed orders: P3 = theorist, data analyst, lead (theory
primary); P4 = data analyst, theorist, lead (empirical primary). Later roles
read all earlier same-run reports plus canonical records for the exact method
identity. P4 uses its cumulative evidence index, never reconstructs from the
run archive; preliminary/comprehensive change scope only. Preserve source
status and cross-role disagreements — empirical evidence never becomes a proof,
nor a theorem an empirical result. P5 requires completed P3 and P4 results for
the exact same method identity — never mix branches or versions.

## Independent assessment

- The Paper Reviewer acts only when the phase assigns it, and first assesses
  without adopting the team's preferred conclusion. It states strengths,
  concerns, evidence, and what would change the assessment; it does not fix the
  object or choose the next run.
- An independent proof audit is a separate mathematical analysis, runs only at
  user request, and identifies the exact statements, assumptions, proof
  version, and unresolved steps examined.
