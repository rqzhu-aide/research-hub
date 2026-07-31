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

**Design principle:** keep freezing everything (disk is cheap, integrity intact),
but make the **reading list** in each prompt phase + role + run specific. Add one
new artifact type (decision digest) so "smaller reading" doesn't mean "less
information."

### Step 1 — Reading guidance rewrite (hours, biggest ROI)

Change the mandated reading lists to role-scoped views:

- **Task briefs** (`launch_dispatch.py`, `_reviewer_task_text` and the run brief
  template): replace "Read these files before working: …charter, norms…" with a
  **role view**: your role's upstream discussion files (full read), decision
  digests (full read), other roles' outputs (titles only — "consult if your task
  touches X"), norms (referenced, not mandated — see Step 2).
- **Lead prompt** (`launch_prompts.py::_build_lead_prompt`): the lead keeps the
  full view (it synthesizes across roles — correct as-is).
- The "Frozen prior results and discussion" list is built per role from the
  existing `role`-tagged discussion inventory — no format change needed.

Expected saving: ~30–50 KB of *mandated* reading per role agent per round,
immediately.

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
| Role-scoped reading lists | `core/launch_dispatch.py` | task-brief template + `_reviewer_task_text` |
| Lead view (unchanged full) | `core/launch_prompts.py` | `_build_lead_prompt` |
| Digest generation + freezing | `core/launch_prompts.py` | `_snapshot_run_inputs` (+ `_condense_decision`) |
| Digest field mapping | reuse `core/web_phase_data.py::_decision_brief` fields | — |
| Rerun-question promotion | `core/launch_dispatch.py` | brief directive block |
| Norms text | `config/team/norms.md` | — |

**Compatibility:** existing runs' frozen contexts are immutable and unaffected.
New snapshot keys (`decision_digest`) are additive; the manifest records what was
frozen, so verification keeps working per-run. Tests to add: digest content
correctness, role-view list construction per role, manifest/verify round-trip
with the new artifact.

## 4. Expected outcome

| | Now | After Steps 1–3 |
|---|---|---|
| Mandated reading per role agent | ~150–190 KB | ~60–80 KB |
| Mechanism | read-everything instructions | role-scoped views + digests |
| Integrity model | per-file SHA + manifest | unchanged |

The 45% target from the original analysis is achievable — mostly without cutting
any content, just by *not mandating* that every role read all of it.
