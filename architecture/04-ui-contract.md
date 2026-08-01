# Web UI Contract

## 1. Purpose

The Web UI helps a researcher understand current scientific state, inspect its evidence, and deliberately start or rerun a phase. It is a projection of immutable formal generations, derived record state, the current index, and run state. It is never a source of scientific truth or workflow state.

The same command service should support the Web UI and an authorized remote agent. Different clients must not produce different workflow semantics.

## 2. UI invariants

### UI-001: No inferred authority

The UI must not infer completion, currency, or validity from folder existence, file timestamps, filename patterns, or arbitrary Markdown prose.

### UI-002: No automatic phase progression

Publishing a run may update available actions, but the UI must not start another run. Every launch requires a distinct user command.

### UI-003: No generic approval control

A valid run is published automatically under the authority of the launch command. The UI does not add a separate approval step. It presents the result and the next decisions available to the researcher.

### UI-004: Separate status dimensions

Publication authority, record position, method alignment, research attention, scientific outcome, and execution state must be shown separately. A single color may summarize them only when the components remain visible and the combination rule is documented.

### UI-005: Current first, history on demand

Pages display current formal records by default. Historical generations and run artifacts are available through explicit expansion or context selection, but are not mixed into the current summary.

### UI-006: Structured summary source

Summary cards use validated `DecisionBrief` and typed view fields. The UI must not select the first paragraph of a document or use heuristic text extraction as the scientific summary.

### UI-007: Consequences before launch

Before submitting a command, the UI shows the resolved method, scope, current inputs, optional context, and expected publication target. The user should understand what the run will reconsider and what it can replace or append.

### UI-008: Canonical state sources

The UI obtains current publication state, record position, alignment, attention,
and evidence eligibility from validated record-state and current-index
projections. It obtains scientific outcome and creation-time assessments from the
immutable content generation. It joins them by stable IDs and never writes back
to either source.

## 3. Backend view models

The UI consumes read-only view models produced by backend projection services.

### 3.1 Project overview

`ProjectOverviewView` contains:

- Project question and domains.
- Current literature basis summary.
- Method catalog rows.
- Active runs.
- Open high-severity attention items.
- Available user commands.

### 3.2 Method row

`MethodRowView` contains:

- Stable method ID, display name, version, and lifecycle state.
- Compact method definition summary.
- Literature provenance summary.
- Phase 3 publication position, alignment, attention count, scientific outcome, and last publication time.
- Phase 4 publication position, alignment, attention count, scientific outcome, and last publication time.
- Phase 5 publication position, alignment, attention, outcome, and manuscript state.
- Allowed actions for this method.

The row must not collapse "not run," "outdated," "inconclusive," and "failed execution" into one state.

### 3.3 Phase view

`PhaseView` contains:

- Phase purpose in direct scientific language.
- Current formal record summary.
- Exact basis and change summary.
- Alignment, outcome, and attention views.
- Primary artifacts and structured evidence links.
- Current decision brief.
- Active and recent run states.
- Run configuration schema and resolved defaults.
- Eligibility explanation and available actions.

### 3.4 Run view

`RunView` contains:

- Run ID, phase, mode, selected method, and requesting actor.
- Frozen contract, input, prepared-context, and manifest summary with digests.
- Exact stage sequence, execution groups, and current role.
- State and event times.
- Structured handoffs available for inspection.
- Validation or conflict report.
- Publication receipt when published.

Mutable progress text is clearly distinguished from formal published conclusions.

### 3.5 Decision brief view

The compact decision view displays, in this order:

1. Decision currently available.
2. Most defensible scientific conclusion.
3. Fundamental contribution or material change.
4. Strongest evidence.
5. Main assumption, uncertainty, or risk.
6. Material role disagreement.
7. Available actions and expected consequences.
8. Exact question a rerun would answer.

Each claim links to its structured statement and supporting primary artifact when available.

## 4. Common phase-page structure

Every phase page uses the same conceptual arrangement.

### 4.1 Current record panel

Shows what is formally current, when it was published, which run produced it, its exact basis, and what changed from the preceding generation. An empty state explains what the first run will create.

### 4.2 Scientific assessment panel

Shows alignment, scientific outcome, and open attention separately. It identifies assumptions and disagreement without converting them into software error language.

### 4.3 Evidence and detail panel

Provides progressive access from compact decision view to structured record to primary artifacts. Links preserve statement and evidence identifiers so users can return to the same location.

### 4.4 Run or rerun panel

Selects one declared run mode and collects its exact phase-specific choices, including instructions, method when applicable, Phase 1 search scope, and context. The UI submits one contract-bound `choice_values` map and does not duplicate the same decision in a second scope field. It shows resolved current inputs and the formal object that a successful run will update.

### 4.5 History panel

Lists prior formal generations and diagnostic run records separately. The user may compare changes or select historical context for a new run. History is not included in a new run merely because the panel was opened.

## 5. Phase-specific controls

### 5.1 Phase 1

Display:

- Current literature corpus size and coverage.
- Current synthesis.
- Newly added, corrected, retracted, withdrawn, and duplicate sources from the latest run.
- Search provenance and unresolved coverage gaps.

User controls:

- Search or update focus.
- Instructions.
- Selected project context.
- Launch or rerun.

The UI should explain that Phase 1 normally expands the literature basis rather than replacing it.

### 5.2 Phase 2

Display:

- Current method catalog, including active and retired methods.
- Method versions, concise mathematical summaries, provenance, and downstream state.
- Changes from the latest catalog publication.

User controls:

- Full-catalog update or focused-method update.
- Selected method for focused mode.
- Instructions and context.
- Manual method retirement or reactivation through an explicit typed command with a reason and exact current basis.
- Launch or rerun.

The lead may recommend methods, but the UI never labels a recommendation as the user's selection.

### 5.3 Phase 3

Display:

- Read-only list of feasible current methods.
- Selected method's definition, exact version, mathematical details, and provenance.
- Current complete theory record, if one exists.
- Proof status, assumptions, counterexamples, open obligations, analyst critique, and lead conclusion.
- Alignment to the current method definition and any selected P4 context.

User controls:

- Method selection.
- Instructions.
- Current context selection.
- Optional historical-context selection, disabled when no history exists.
- Launch or rerun.

Selecting a method reveals detail and prepares a command. It does not create a durable branch or run until the user launches Phase 3.

### 5.4 Phase 4

Display:

- The same read-only feasible-method list and selected-method summary used by Phase 3.
- The four current formal Phase 4 components: evidence index, empirical synthesis, implementation record, and phase decision.
- Evidence registry with exact method version, applicability, code, data, configuration, uncertainty, and source run.
- Evidence newly added, revalidated, contradicted, or classified as outdated.
- Alignment to the current method definition and any selected P3 context.

User controls:

- Method selection.
- Preliminary or comprehensive scope on every run.
- Instructions.
- Current and optional historical context.
- Launch or rerun.

Preliminary and comprehensive describe scientific scope, not chronological order. Either may be selected when eligible.

### 5.5 Phase 5

Display:

- Exact P1, P2, P3, and P4 generations proposed as the manuscript basis.
- Eligibility and any alignment problem for each input.
- Current manuscript and change summary.
- Open review issues and their dispositions.

User controls:

- Method or manuscript target.
- Assembly or review-revision mode.
- Instructions and allowed context.
- Launch or rerun.

If P5 is ineligible, the page identifies the exact missing or mismatched record and offers navigation to the relevant phase. It does not launch the corrective run.

## 6. Action eligibility

The backend returns commands as typed action descriptors:

```json
{
  "action": "start_run",
  "phase": "P3",
  "enabled": false,
  "reason_code": "METHOD_NOT_SELECTED",
  "researcher_message": "Select a current method before starting theory development."
}
```

The UI may disable a control only from this backend eligibility response or a directly local incomplete form field. It must not duplicate phase dependency logic in frontend code.

An enabled action states:

- Whether it starts a research run or performs a no-run control transaction.
- Which exact method, version, record generation, and control head it concerns.
- Which formal current records or selected history will be used.
- The required reason and the expected scientific or eligibility consequences.
- Whether publication replaces a current record, appends evidence, updates a catalog, or withdraws one exact generation.

Typed actions include `start_run`, `retire_method`, `reactivate_method`, and
`withdraw_formal_generation`. Retirement and reactivation appear with the Phase
2 method table. Withdrawal appears in formal-record correction controls, not in
an ordinary phase-run panel. A confirmation form is part of command construction;
it is not a second generic approval state. No control command launches a phase.

## 7. Status presentation

### 7.1 Execution state

Use only the canonical run states: `created`, `preparing`, `prepared`, `running`, `submitted`, `validating`, `promoting`, `published`, `failed`, `rejected`, `conflicted`, or `cancelled`. The display label for `promoting` may be "Publishing," but the persisted value does not change.

### 7.2 Alignment

Use scientific basis language:

- Exact current basis.
- Assessed compatible.
- Reassessment needed.
- Uses an earlier method definition.
- Not applicable.

### 7.3 Scientific outcome

Use direct scientific language:

- Supported under stated assumptions.
- Partially supported.
- Contradicted.
- Inconclusive.
- Not yet assessed.

### 7.4 Research attention

Show the number and severity of open attention items, with the exact research questions available on expansion. Do not use attention as a synonym for invalidity.

Color is supplementary. Every status includes text, an accessible icon or shape, and an explanation. Light and dark themes must meet WCAG AA contrast for ordinary text and status indicators.

## 8. Errors, conflicts, and recovery

Messages should distinguish:

- Missing scientific prerequisite.
- Run execution failure.
- Submission validation problem.
- Publication conflict caused by a changed current basis.
- Scientific outcome that is unfavorable but formally valid.

For each non-published run, show:

- What happened.
- Whether formal current records changed.
- Whether run-local work remains available.
- The smallest user action that can proceed.

Do not present a scientifically contradicted result with a red software-error banner. Do not present a rejected schema as a scientific contradiction.

## 9. Remote operation

The Web UI and remote agent use the same read and command APIs. A remote request must expose:

- Operating identity.
- User authority or delegation.
- Resolved command before submission.
- Resulting run ID for a research run, or transaction ID and receipt for a control command.

The UI should show that a run or control transaction was requested remotely and
by whom. Remote control does not weaken user authority, bypass control-command
concurrency, or allow direct formal-record mutation.

## 10. UI acceptance tests

Implementation must prove:

1. A project with no runs presents meaningful empty states and launch controls.
2. Publishing a phase updates the view but does not launch another phase.
3. P3 and P4 can each be launched after an eligible P2 method exists.
4. P4 preliminary or comprehensive scope is selectable on any eligible run.
5. Historical context is disabled when absent and excluded by default when present.
6. A method definition change updates P3, P4, and P5 alignment views without erasing their prior outcomes.
7. An inconclusive published result appears as a formal scientific outcome, not an execution failure.
8. A failed run leaves the prior current result visible and clearly distinguishes failed attempt from current record.
9. Every compact claim can navigate to its structured statement and supporting artifact.
10. UI controls match backend eligibility under refresh, concurrent publication, and remote commands.
11. Light and dark themes satisfy contrast and keyboard-navigation requirements.
12. No test depends on parsing arbitrary Markdown to determine status or available actions;
13. Deleting and rebuilding backend state projections does not change any user-visible state when the authority-event journal is unchanged.
14. Method lifecycle and formal withdrawal controls display their exact basis, reason requirement, no-run behavior, and consequence summary.
15. A stale Web or remote control command produces the same conflict response and no formal change.
