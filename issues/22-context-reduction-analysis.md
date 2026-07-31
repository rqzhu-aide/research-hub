# Context Reduction Analysis — Review & Assessment

**Date:** 2026-07-30
**Reviewer:** Agent (tez-developer)
**Source:** `issues/22-context-reduction-agent-runs.md`
**Verdict:** Numbers are accurate. Core thesis is valid. Some implementation ideas are wrong or oversimplified. Specific reductions are ranked below.

---

## 1. Are the numbers valid?

**Yes.** I measured the actual frozen context from the real P3 run (`9081e83c`):

| Component | Analysis claims | Actual measured | Accurate? |
|---|---|---|---|
| Charter + norms | 16 KB | 15.9 KB (1.8 + 14.1) | ✓ |
| Agent souls (3 roles) | 6 KB | 6.5 KB | ✓ |
| Phase playbooks (5 files) | 18 KB | 22.9 KB | Understated by ~5 KB |
| P1 summary | 20 KB | 19.9 KB | ✓ |
| P1 decision | 14 KB | 13.3 KB | ✓ |
| P2 summary | 29 KB | 29.3 KB | ✓ |
| P2 decision | 23 KB | 22.6 KB | ✓ |
| P3 run 1 summary | 39 KB | (measured on 2nd P3 run: 39.9 KB) | ✓ |
| P3 run 1 decision | 19 KB | 19.1 KB | ✓ |
| Project setting | 4 KB | 4.0 KB | ✓ |
| Method definition | 2 KB | ~2 KB | ✓ |
| **Total** | **~193 KB** | **~196 KB** | ✓ |

The per-round multiplication claim (193 KB × 3 agents × 3 rounds ≈ 1.7 MB) is also correct — each agent task brief references the frozen files, and agents read them via file tools, consuming context window per read.

---

## 2. Is the core thesis valid?

**Yes.** The system freezes a one-size-fits-all context bundle for every agent in every round. Three structural problems are real:

1. **P2 sends all 7 methods** when only 1 is selected. This is the single biggest waste (~52 KB combined summary + decision). The selected method is a tiny fraction of the catalog.

2. **Summaries are not role-scoped.** A theorist in P3 receives the data_scientist's full P1 findings. Cross-role visibility can be useful for awareness, but the *full* content is overkill — a 1-sentence summary per other-role would suffice.

3. **Team norms (14 KB) are static boilerplate.** They are identical in every run and define behavioral standards, not task-specific instructions.

---

## 3. Where the analysis is wrong or oversimplified

### 3a. "SOUL.md on disk is irrelevant" — conflates two different things

The analysis confuses Hermes profile files with Research Hub frozen context:

- **Profile SOUL.md** (`~/.hermes/profiles/developer/SOUL.md`): Hermes personality. Research Hub does NOT control this. It's irrelevant to the frozen context, yes — but Research Hub can't eliminate it.
- **Frozen role souls** (`config/souls/*.md`, copied into `.context/souls/`): These ARE Research Hub controlled and ARE injected into the task brief (inlined as `BEGIN FROZEN ROLE SOUL ... END FROZEN ROLE SOUL`). These are the ones that matter.

The role souls (~2 KB each) define role-specific reasoning standards (e.g., "as a theorist, prioritize mathematical rigor"). They're small and serve a real purpose. Cutting them to 0 is wrong. Merging them into the playbook header is the right move.

### 3b. "Profile memory is mostly boilerplate" — true but not Research Hub's problem

Profile MEMORY.md content is managed by Hermes, not Research Hub. Issue #20 already identifies cross-project memory contamination. The analysis's suggestion to put role content in profile memory would *worsen* Issue #20. The current design is correct: role content lives in the frozen context, not in profile memory.

### 3c. "Single condensed context bundle" — conflicts with the integrity model

The current system deliberately separates files (charter, norms, souls, playbooks, summaries, decisions) so each can be:
- Independently SHA-256 verified
- Tracked in the manifest
- Re-verified at dispatch time (`_verify_frozen_inputs`)

Merging everything into one blob would collapse the granular integrity model. The right approach is to reduce *content* within the existing file structure, not merge the files.

### 3d. Role-scoping is architecturally harder than implied

The analysis says "add role-filtering to upstream summary inclusion." But summaries are sealed HTML files generated at phase completion — they mix all roles' outputs in a single document. Role-scoping requires either:
- **At seal time:** Generate role-tagged sections in the summary HTML, then filter at freeze time. This changes the summary format (affects all future and past runs).
- **At freeze time:** Parse the HTML and extract role-specific sections. Fragile, format-coupled.

This is the hardest reduction to implement correctly.

---

## 4. Ranked recommendations

### Tier 1 — Do first (easy, high impact)

#### 4.1. Method-scope the P2 summary and decision for P3+ runs (~40 KB saved)

**What:** When freezing context for a method-bound phase (P3/P4/P5), include only the selected method's section from the P2 summary and decision, not the full 7-method catalog.

**Where to change:** `_trusted_context()` in `launch_prompts.py` (line ~1014) or `_snapshot_run_inputs()` (line ~34). The P2 summary is already method-scoped for *which run to include* — extend this to *what content within the summary* to include.

**Implementation:** The cleanest approach is to generate a method-filtered summary variant at freeze time. The P2 summary HTML has method sections; extract only the selected method's section + the cross-method synthesis. Store it as a filtered copy in `.context/summaries/`.

**Risk:** Low. The filtered copy is a new frozen artifact with its own SHA-256. No existing integrity model changes.

**Savings:** ~21 KB (summary) + ~18 KB (decision) = **~39 KB per agent per round.**

#### 4.2. Condense norms.md (14 KB → ~4 KB, saves ~10 KB)

**What:** The current `config/team/norms.md` is 14 KB of detailed norms. Much of it is repetitive ("always cite sources," "never fabricate," "report uncertainty"). A condensed version retaining the essential rules would be ~4 KB.

**Where to change:** Edit `config/team/norms.md` directly. No code changes needed.

**Risk:** Very low. Norms are behavioral guidance, not machine-parsed.

**Savings:** **~10 KB per agent per round.**

### Tier 2 — Worth doing (medium effort, good impact)

#### 4.3. Merge role souls into playbook headers (~6 KB saved, simpler architecture)

**What:** Instead of separate `souls/theorist.md` + `playbooks/theorist.md`, merge the soul content (~2 KB) into the top of each playbook. The soul defines "who you are"; the playbook defines "what to do." They belong together.

**Where to change:**
- `config/souls/*.md` → merge into `config/phases/*/role.md` headers
- `_snapshot_run_inputs()` — stop copying souls separately; the playbook snapshot already includes the merged content
- `_dispatch_task()` / `_build_lead_prompt()` — stop inlining soul text separately; it's already in the playbook

**Risk:** Medium. Changes the snapshot structure and manifest schema. Existing frozen runs keep their old structure (backward compatible since the manifest records what was frozen).

**Savings:** ~6 KB per agent per round (3 souls × 2 KB). Also eliminates duplicated content (soul is currently both inlined in the task brief AND available as a separate file).

#### 4.4. Don't send prior-phase decisions as full JSON (~40 KB saved across P1+P2+P3)

**What:** Decision JSONs (P1: 13 KB, P2: 23 KB, P3: 19 KB) are structured records containing proposed values, evidence chains, and metadata. Agents mostly need the *outcome* (selected method, key decisions, scientific outcome label), not the full structured record.

**What to do:** At freeze time, generate a condensed decision digest (~2-3 KB) containing: scientific outcome, selected object, key decisions, and changed values. The full JSON stays in the sealed run directory for audit; only the digest goes into frozen context.

**Where to change:** `_snapshot_run_inputs()` — add a `_condense_decision()` step when copying decision records into the frozen context.

**Risk:** Medium. Agents lose access to detailed evidence chains from upstream decisions. But those are in the upstream summary, which is already included.

**Savings:** ~37 KB (13 + 23 + 19 → ~6 KB condensed).

### Tier 3 — Complex, defer

#### 4.5. Role-scoped summaries (~10 KB saved per agent)

**What:** Each agent receives only their role-relevant sections from upstream summaries, plus a 1-sentence digest of other roles' findings.

**Why defer:** Requires changing the summary format (add role tags to sections) and the freeze logic (filter by role). This touches the sealing pipeline, summary generation, and freeze pipeline. High blast radius.

**Alternative:** Keep full summaries but add a "role relevance guide" to the task brief — a 3-line note saying "Your primary upstream is the theorist's P1 findings; the data_scientist's findings cover implementation feasibility." This costs 0 KB extra (it's in the brief) and guides the agent to read selectively.

#### 4.6. P4/P5 high-level summary injection (new functionality)

**What:** The analysis proposes injecting ~5 KB P4 and ~3 KB P5 summaries into runs that need downstream awareness.

**Why defer:** P3 runs don't need P4/P5 context (P4/P5 haven't run yet). P5 runs already get P3/P4 full summaries. The only case where this matters is a P3/P4 *re-run* after P5 has completed — and in that case, the agent should be told what changed, not given a generic summary.

---

## 5. Summary table

| Reduction | Effort | Savings per agent | Risk | Priority |
|---|---|---|---|---|
| Method-scope P2 summary+decision | Low | ~39 KB | Low | **Do first** |
| Condense norms.md | Trivial | ~10 KB | Very low | **Do first** |
| Merge souls into playbooks | Medium | ~6 KB | Medium | Tier 2 |
| Condense decision JSONs | Medium | ~37 KB | Medium | Tier 2 |
| Role-scoped summaries | High | ~10 KB | High | Defer |
| P4/P5 summary injection | Medium | N/A (new) | Low | Defer |

**Tier 1 combined savings: ~49 KB per agent per round (~25% of frozen context).**
**Tier 1 + Tier 2 combined: ~92 KB (~47% of frozen context).**

The analysis document's target of 45% reduction is achievable with Tier 1 + Tier 2 changes.

---

## 6. What NOT to change

- **The frozen-context integrity model.** SHA-256 verification, per-run copies, and manifest tracking are correct. Reductions should happen *within* this model (smaller frozen files), not by bypassing it.
- **Profile SOUL.md / MEMORY.md.** These are Hermes-controlled, not Research Hub-controlled. Issue #20 handles the memory contamination problem.
- **Charter.md.** It's only 1.8 KB. The overhead of removing it (and potentially losing team-structure awareness) isn't worth the savings.
