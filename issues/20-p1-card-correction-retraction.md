# Situation 20: The Uncorrectable Reference Card

## Scenario

During a P1 rerun, the researcher notices that an existing reference card —
promoted two cycles ago — is **wrong**: a paper was misclassified (its
claimed result contradicts what the paper actually proves), and the wrong
claim has since propagated into the literature synthesis and even a method's
positioning. The researcher asks the lead to fix the card in the next P1 run.
What happens?

## Step-by-step evaluation

### Step 1: P1 rerun stages a "correction"

- **System behavior**: P1's write model is **delta-only**. A run writes only
  genuinely new reference cards under `<output_root>/reference-delta`;
  **existing filenames and canonical identities are rejected**
  (`literature_records.py` module docstring, `:12-13`). The schema has no
  status, retraction, or supersession field (`literature_schema.py` — no
  status/retract/withdraw support; verified by inspection).
- **Consequence**: the corrected card — same paper, same filename — cannot be
  staged. The seal/promotion path rejects it.
- **Smooth?** ❌ The normal workflow cannot represent "card N was wrong".

### Step 2: Workarounds

- **Option A — new card**: stage a differently-named card ("…-correction" or
  a note card). Both cards now exist; the wrong one is still canonical, still
  digest-referenced by the frozen records of every past run, and still read
  by agents on future P1 reruns (the playbook has them read the library).
- **Option B — fix the synthesis only**: `literature-summary.md` IS rewritten
  every promotion, so the synthesis can retract the claim in prose. But the
  underlying card still contradicts it, and agents reading the library see
  both.
- **Option C — manual edit**: edit the canonical card on disk. The reference
  index records `papers_sha256` over the collection
  (`literature_records.py:375-387`); the edit changes the collection digest.
  The frozen records of *past* runs are unaffected (they hash their own
  frozen copies), but the graph's P1 collection edges compare digests — the
  edit looks exactly like a literature change, and any frozen basis naming
  the old collection digest flips to `review_required`. There is no
  "correction" semantics attached; it is indistinguishable from tampering in
  the audit trail.
- **Smooth?** ⚠️ All three are unsatisfying: A and B leave the error
  canonical; C works but is semantically invisible.

### Step 3: Downstream propagation of the wrong claim

- **System behavior**: the method whose positioning cited the wrong claim has
  a frozen P2 literature basis; the P1 collection digest change (via Option C
  or a new P1 run) flips its P1→P2 edges to `review_required`
  (`knowledge_graph.py:836-861`) — the yellow state is the *only* structured
  signal that something upstream changed. There is no P1→P2/P3/P4
  "correction propagation" (see ISSUES.md #6).
- **Smooth?** ⚠️ The graph notices *change*, never *why*.

## Issues identified

### 🟡 Issue A: No correction or retraction path for reference cards

**Severity: Medium.** The delta-only cumulative model makes cards immutable
by construction — no status field, no supersession, no removal path
(`literature_schema.py`; `literature_records.py:12-13`). A wrong card lives
forever in the canonical library that future agents read. A minimal fix: a
card-level `status: retracted` + `retracted_by`/`retraction_note` honored by
the index (excluded from agent context, retained for provenance and digest
stability), with the promotion path accepting retraction entries in a delta.

### 🟢 Observation: manual edits are at least detected

Because the index hashes the collection, any direct card edit changes the
digest and flips graph edges — tampering can't hide. What's missing is not
detection but *semantics*: correction, retraction, and external change are
indistinguishable.

## Space summary

| Component | Size |
|---|---|
| P1 rerun (correction attempt) | ~0.5 MB |
| Extra correction card / notes | ~5 KB |
| **Total** | **~0.5 MB** |

## Verdict

❌ **The system's most cumulative record has no error-handling path.** The
delta-only model is elegant for growth and provenance, but real literature
work produces misclassifications, and today the only honest fix is a manual
edit that the system can detect but cannot understand. Retraction semantics
belong in the schema.
