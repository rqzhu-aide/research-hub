# Situation 04: Failed Promotions and Crash Recovery

## Hypothesis

A researcher completes P1 + P2 with one method, `method-alpha` v1.

They run P3 for alpha. The theorist produces a theory. The lead submits the
summary. Research Hub begins sealing and promoting the theory record.

**Crash**: the Hermes process is killed (OOM, power loss, or manual kill)
mid-promotion — the theory package has been staged and validated, but the
atomic rename from the staging directory to the canonical directory has not
completed. A `prepared` transaction directory exists.

The researcher restarts and tries to launch P3 again.

Then a similar crash happens during P4 promotion, but this time the atomic
rename **partially** completes (the OS renamed the file but the fsync of the
parent directory didn't happen).

Finally, the researcher runs P5, and during the P5 run, another crash occurs
before any output is produced.

## Steps and evaluation

### Step 1: P1 + P2 complete

Standard. Disk: ~2.1 MB.

### Step 2: P3 run — work completes, crash during promotion

- **What happens on crash**: The launch_run process has finished the agent
  work. The `seal_output()` call has validated the staged theory. Then
  `promote_output()` begins:
  1. `plan_staged_theory_promotion()` creates a `prepared` transaction with the
     promotion intent.
  2. The promotion journal (`promotion_journal.py`) writes a `prepared` status
     entry.
  3. `os.replace(staged, canonical)` — **this is where the crash happens**.
     The rename hasn't occurred. The `prepared` directory exists, but the
     `canonical` directory does not.

- **State after crash** (assuming the crash lands during step 3 below):
  - Run status in `project.yaml`: `submitting` (the finalization didn't
    complete).
  - On disk: `branches/method-alpha/evaluations/` has a `.prepared/` directory
    containing the validated theory package.
  - The promotion journal has a `prepared` entry but no `promoted` entry.

- **Smooth?** ⚠️ The system has a **dedicated recovery path** for this, but
  whether it works depends on *exactly* when the crash happens. The production
  order in the finalizer (`project_state`, ~line 6166) is:

  1. `plan_staged_theory_promotion()` — intent computed (pure, no filesystem
     changes).
  2. `promotion_journal.prepare()` — **journal with the intent is now
     durable** (status `prepared`).
  3. `promote_output()` — filesystem prepare: `parent.mkdir(parents=True,
     exist_ok=True)`, create `prepared/`, copy+verify, then `os.replace`.

  **Window A — crash between steps 2 and 3** (journal durable, nothing on
  disk): on the next locked project load,
  `_reconcile_promotion_journals_unlocked` runs recovery with the retained
  intent. Recovery sees the all-absent "completed" state and calls
  `_sync(canonical.parent)` — but on a **first-ever promotion for a new
  branch**, `branches/method-alpha/evaluations/` (theory) or
  `branches/method-alpha/draft/sections/` (empirical) has never been created,
  so the fsync `os.open` fails. This is the failing test
  `test_lock_held_paths_do_not_reacquire_project_lock` (empirical, wrapped as
  `EmpiricalRecordPromotionError`) — and theory has the **same latent bug with
  no test coverage**, surfacing as a raw `FileNotFoundError`.

  **Window B — crash during step 3** (the scenario originally described
  above: `prepared/` exists, rename not done): recovery works, because the
  prepare step already created the branch directory tree. Recovery sees
  `(absent, prepared, absent, absent)` and completes the promotion with
  `_replace(prepared, canonical)`.

- **Impact of the Window-A bug is worse than "one stuck run".** A failed
  recovery raises `StateValidationError` out of
  `_reconcile_promotion_journals_unlocked`, which runs on **every locked
  project load** — so the project becomes **unopenable** (every page and
  launch fails) until manual repair. The journal is retained, so the crash
  recurs on every load.

- **Manual recovery**: create the missing directory, then let recovery retry:
  1. Theory: `mkdir -p branches/method-alpha/evaluations/`
     Empirical: `mkdir -p branches/method-alpha/draft/sections/`
  2. Reload the project (any page). Reconcile now completes the fsync and
     removes the journal.
  3. Alternative: delete the journal file under the control directory to
     abandon the promotion entirely (the staged run output remains, and the
     run can be resubmitted).

- **Context per role (if P3 rerun instead of recovered)**: Same as a fresh P3
  run ≈ 100–120 KB per stage.

### Step 3: P3 recovery and rerun

After manual directory creation (or whenever the crash landed in Window B,
where the branch directory tree already exists), recovery completes the
promotion:

- `_recover_unlocked()` sees state `(absent, new, absent, absent)` (no
  canonical, prepared exists, no backup, no rejected).
- It executes `_replace(prepared, canonical)` — atomic rename.
- `_sync(canonical.parent)` — fsync succeeds (directory now exists).
- Run status updates to `awaiting_review` or `completed`.
- The promotion journal records `promoted`.

- **Smooth?** ✅ Recovery works **if the directory exists**. The bug is in the
  first-run case where the branch directory tree hasn't been created yet.

- **Disk**: Theory package ~150 KB in canonical + ~150 KB backup (if retained)
  + journal entries. Running total: **~3.3 MB**.

### Step 4: P4 run — crash during atomic rename (partial completion)

- **What happens**: `os.replace(staged, canonical)` succeeds (the OS rename is
  atomic), but `_sync(canonical.parent)` (fsync of the parent directory) is
  interrupted. The file exists but its directory entry may not be durable.

- **State after crash**:
  - The canonical empirical package exists on disk (the rename happened).
  - But the fsync didn't complete, so on a power-loss scenario the directory
    entry might not be persisted.
  - If the system doesn't lose power (just process kill), the file is fine.

- **Smooth?** ✅ For process kills (not power loss), this is fine — the file
  exists in the filesystem cache and will be visible on next access. The
  recovery path sees state `(new, absent, absent, absent)` (canonical exists,
  no prepared, no backup) and simply calls `_sync(canonical.parent)` to make
  it durable. This is the "completed" state in the recovery state machine.

  For actual power loss without fsync: the canonical file may not exist after
  reboot. Recovery sees `(absent, prepared, absent, absent)` and re-executes
  the promotion. **This is the correct behavior** — the prepared directory was
  fsynced before the rename was attempted.

- **Disk**: Adds ~600 KB. Running total: **~3.9 MB**.

### Step 5: P5 run — crash before any output

- **What happens**: The P5 launch succeeds. Agents start running. The process
  is killed before any agent produces output.

- **State after crash**:
  - Run status: `running` (or `starting`).
  - No round outputs exist. No summary. No staged output.
  - No promotion was attempted.

- **System behavior**: The run is simply orphaned. On restart:
  1. The status check sees a `running` run with no process alive.
  2. The user can cancel it or rerun.
  3. No cleanup is needed — no partial promotions exist.

- **Smooth?** ✅ Yes. An interrupted run before any output is the simplest
  crash case. The run is abandoned, no artifacts to recover.

### Step 6: P5 rerun — succeeds

- **Smooth?** ✅ Standard launch. All upstream records exist and are current.
- **Context per role**: ~200–250 KB (all current records frozen).
- **Disk**: Adds ~500 KB. Running total: **~4.4 MB**.

## Space summary

| Component | Size |
|---|---|
| P1 + P2 | ~2.1 MB |
| P3 (crashed + recovered) | ~1.3 MB |
| P4 (crashed + recovered) | ~0.8 MB |
| P5 (crashed, then rerun) | ~0.7 MB |
| Journals + transaction dirs | ~0.2 MB |
| **Total** | **~5.1 MB** |

## Verdict

⚠️ **Crash recovery is well-designed but has a first-run bug.**

The journal-based recovery system is architecturally sound: it tracks prepared
transactions, can complete or roll back promotions, and handles the full state
machine of `(canonical, prepared, backup, rejected)` tuples. The atomic rename
+ fsync pattern is the correct durability approach.

**The bug**: `_sync(canonical.parent)` crashes when the parent directory
doesn't exist. The vulnerable window is narrow but real: a **first-ever
promotion to a new branch** that is interrupted *after the promotion journal
is durable but before the filesystem prepare creates the branch directory
tree*. Because journal reconcile runs on every locked project load, the failed
recovery doesn't just strand one run — it makes the **whole project
unopenable** until someone creates the missing directory by hand. This is a
**real, user-facing bug** that should be fixed before relying on the recovery
system. It affects both theory (raw `FileNotFoundError`, untested) and
empirical (wrapped `EmpiricalRecordPromotionError`, caught by the failing
test at HEAD).

The fix is simple: `canonical.parent.mkdir(parents=True, exist_ok=True)` before
the `_sync` call, or guard `_sync` with `if directory.exists()`. Both modules
need it, plus a theory-side regression test mirroring the empirical one.
