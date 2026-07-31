# Phase + Role + Run-Specific Context Construction — Assessment & Plan

**Date:** 2026-07-30
**Author:** Coder agent
**Sources reviewed:** `issues/22-context-reduction-agent-runs.md` (original analysis),
`issues/22-context-reduction-analysis.md` (developer review)
**Verdict:** Analysis is valid; the review's ranking is mostly right; both miss the
biggest lever. Plan below is implementable in three small steps without touching
the integrity model.

---

## 1. Independent verification

### Numbers — confirmed, with two corrections

I measured the actual config files and a real P2 summary:

| Claim | Measured | Note |
|---|---|---|
| charter + norms = 16 KB | **21.7 KB** (1.8 + 19.9) | norms.md is ~6 KB *larger* than claimed — condensing saves more, not less |
| souls ≈ 6 KB (3 roles) | 8.7 KB for 4 roles (2.1–2.3 KB each) | ✓ scale |
| P2 summary = 29 KB | 29.3 KB | ✓ |
| playbooks 18 KB/run | per-phase subset of 172 KB total | plausible per run |

### Architecture facts both documents missed

1. **The burden is instruction-driven, not injection-driven.** Frozen context is
   *not* inlined into prompts (except role souls). The lead prompt says
   "read these files **completely**: _lead.md, _phase.md, charter, norms, setting"
   (`launch_prompts.py:3078`); the task brief says "Read these files before working:
   role playbook, setting, charter, norms" (`launch_dispatch.py:650`). Agents burn
   context because we *tell them to read everything*, not because the files exist.
   **The cheapest reduction is changing the reading instructions — zero format changes.**

2. **Upstream per-role outputs are already role-tagged separate files.** The frozen
   `discussion/` inventory carries an explicit `role` field per file
   (`launch_prompts.py:302-338`). Role-scoped context is feasible *today* at the
   file level for discussion; only the summary HTML mixes roles.

3. **The P2 summary HTML is not method-sectioned.** Verified on project-004: its
   headings are decision-brief sections (User Decision Brief, Phase Outcome,
   Record Changes, Evidence), not per-method sections. HTML extraction of "the
   selected method's section" would be fragile — the developer review is right to
   be wary, and I go further: **don't filter the summary at all**. What a P3+ run
   actually needs from P2 is (a) *which* method was selected and why → in the
   decision record; (b) the method definition → already frozen separately (2 KB).
   Method-scoping should ride on a **decision digest**, not summary surgery.

4. **The integrity model is per-file.** `_snapshot_run_inputs` freezes each input
   with its own SHA-256 + manifest entry; `_verify_frozen_inputs` re-checks at
   dispatch. Adding *new, smaller* frozen artifacts (digests) is fully compatible —
   they get their own digests and link back to the sealed originals by path+SHA.
   Nothing in the reduction plan requires weakening verification.

### Where the original analysis is wrong (agreeing with the review)

- Profile SOUL.md / MEMORY.md are Hermes-controlled — out of scope (and #20's fix
  now instructs agents to scope memory per project).
- Cutting souls to 0 is wrong; merging into playbooks is right but low priority.
- "Single condensed context bundle" would collapse per-file integrity — reject.

## 2. The plan: declarative per-phase, per-role context views

**Design principle:** the system needs *both* sides of the handoff —
**generation** (each run authors role-facing briefs at seal time) and
**consumption** (each prompt's reading list is phase + role + run specific).
Freezing stays maximal (disk is cheap, integrity intact); what changes is what
gets *written* per run and what each role is *told to read*.

### Step 0 — Role-facing handoff briefs (generation side; the missing half)

Filtering alone is not enough: the role-tagged discussion files are verbose
first-person work logs, and the summary HTML is a role-mixed synthesis. A
downstream theorist needs a **distilled brief written for theorists**, authored
by the upstream team that just finished the work — not a filtered slice of a
document written for everyone.

**What:** as part of the final summary stage, the research lead of every run
writes one short **handoff brief per downstream consumer role** (~1–2 KB each):

| Upstream run | Handoff briefs to author |
|---|---|
| P1 literature review | for `research_lead` (P2 method scoping), for `paper_reviewer` (P5 citations) |
| P2 method development | for `theorist` (P3: chosen method + open questions), for `data_scientist` (P4: implementability notes), for `paper_reviewer` (P5: claims inventory) |
| P3 theory | for `data_scientist` (P4: what to validate, assumptions to honor), for `paper_reviewer` (P5: proved claims + limitations) |
| P4 empirical | for `paper_reviewer` + `research_lead` (P5: evidence status, what the data showed, outdated/unresolved entries) |

**Format:** `handoff/{role}.md` in the run's summary artifacts — free text with
three required lines: *what you must know*, *what you must verify/honor*, *what
changed vs the previous run* (reruns). Sealed and hashed like every other run
artifact; the manifest/seal pipeline gains them as a new artifact kind.

**Backward compatibility:** old runs have no handoff briefs. The downstream
reading list falls back to decision digest + role-tagged discussion files for
those runs (labeled "no role brief available — synthesized from raw outputs").
New runs get the briefs; nothing breaks.

**Contract change:** the phase playbooks (`config/phases/*/_lead.md`) must
instruct the lead to write the briefs, and the finalization check should warn
(not fail) when they're missing. This is a genuine contract addition — it
belongs in the phase docs when implemented.

### Step 1 — Reading guidance rewrite (consumption side; hours once Step 0 exists)

Change the mandated reading lists to role-scoped views:

- **Task briefs** (`launch_dispatch.py`, `_reviewer_task_text` and the run brief
  template): replace "Read these files before working: …charter, norms…" with a
  **role view**: the handoff brief *for your role* from each upstream run (full
  read — this is the dense, authored handoff), decision digests (full read),
  your own role's upstream discussion files (only when the task needs depth),
  other roles' outputs (titles only — "consult if your task touches X"), norms
  (referenced, not mandated — see Step 3).
- **Lead prompt** (`launch_prompts.py::_build_lead_prompt`): the lead keeps the
  full view (it synthesizes across roles — correct as-is) plus *all* handoff
  briefs (they're small).
- The "Frozen prior results and discussion" list is built per role from the
  handoff-brief inventory + the existing `role`-tagged discussion inventory.

Expected saving: ~40–60 KB of *mandated* reading per role agent per round, and
— more importantly — what they *do* read is authored for them, not mined by
them.

### Step 2 — Decision digest artifact (1–2 days, structural win)

New helper `_condense_decision(decision_data) -> str` (fields: scientific outcome,
selected object, recommendation + recommended action, top-3 main evidence,
principal risk, smallest decision changer, `rerun_question`, record changes) —
the same field set already proven in the webapp's `_decision_brief`
(`web_phase_data.py`).

- Generated at freeze time in `_snapshot_run_inputs()` for every upstream summary
  entry, frozen as `summaries/{phase}-{run_id}-decision-digest.md` with its own
  SHA-256 and a manifest entry linking the sealed source.
- Reading lists use the digest by default; the full summary/decision stays frozen
  and labeled "read only when the digest is insufficient for your task."
- Saving: P1+P2+P3 decisions ~55 KB → ~8 KB, and P2's 29 KB full-catalog summary
  becomes on-demand instead of mandated.

**Bonus (run-specific):** the digest's `rerun_question` should be *promoted into
the task brief's directive section* for reruns — "this rerun exists to answer: …".
That is genuine run-specific context construction, not just reduction.

### Step 3 — Norms condensation (trivial)

`config/team/norms.md` 19.9 KB → ~4–5 KB, deduplicating repeated rules. Norms are
behavioral guidance, not machine-parsed; keep the full version in the repo, freeze
the condensed one. Optionally drop norms from the *role* briefs' mandated list
(lead keeps it) once condensed.

### Deferred (with reasons)

- **Souls merged into playbooks** — real but small (~6 KB); touches snapshot
  structure + manifest. Do after Steps 1–3 settle.
- **Role-scoped summary HTML** — requires seal-time format changes; high blast
  radius. The role-tagged discussion files already provide the role view; the
  summary HTML is a *synthesis*, which is precisely what should stay shared.
- **P4/P5 summary injection into P3 reruns** — the Issue-7 fix already surfaces
  superseded runs as labeled history; a generic downstream summary adds little.

## 3. Touchpoints (for whoever implements)

| Change | File | Function |
|---|---|---|
| Handoff brief authoring (contract) | `config/phases/*/_lead.md` | summary-stage instructions |
| Handoff brief sealing + manifest kind | `core/phase_records.py`, `core/launch_manifest.py` | seal pipeline, artifact inventory |
| Role-scoped reading lists (briefs first) | `core/launch_dispatch.py` | task-brief template + `_reviewer_task_text` |
| Lead view (full + all briefs) | `core/launch_prompts.py` | `_build_lead_prompt` |
| Digest generation + freezing | `core/launch_prompts.py` | `_snapshot_run_inputs` (+ `_condense_decision`) |
| Digest field mapping | reuse `core/web_phase_data.py::_decision_brief` fields | — |
| Rerun-question promotion | `core/launch_dispatch.py` | brief directive block |
| Norms text | `config/team/norms.md` | — |

**Compatibility:** existing runs' frozen contexts and sealed artifacts are
immutable and unaffected. Runs without handoff briefs fall back to digest +
role-tagged discussion in the reading list. New snapshot keys and the new
sealed artifact kind are additive; the manifest records what exists per run.
Tests to add: handoff brief presence/warning at finalization, digest content
correctness, role-view list construction per role (brief present vs fallback),
manifest/verify round-trip with the new artifacts.

## 4. Expected outcome

| | Now | After Steps 0–3 |
|---|---|---|
| Mandated reading per role agent | ~150–190 KB | ~50–70 KB |
| What roles read upstream | role-mixed synthesis + raw logs | briefs *authored for their role* + digests |
| Mechanism | read-everything instructions | generate-at-seal briefs + role-scoped views |
| Integrity model | per-file SHA + manifest | unchanged (briefs/digests are new sealed artifacts) |

The 45% target from the original analysis is achievable — and with Step 0 the
reduction is a *quality* improvement too: downstream roles read a distilled
brief written for them by the team that did the work, instead of mining raw
outputs written for everyone.
