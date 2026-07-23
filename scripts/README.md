# Research Hub Scripts

Supporting scripts for the Research Hub. These are **automation tools** used to
run multi-phase pipelines unattended, not part of the core application.

## Core application files (not in this directory)

| File | Purpose |
|------|---------|
| `webapp.py` | Flask web UI (:5055) — the main application |
| `hub.py` | Data-access layer (DB, config, project resolution) |
| `scripts/project_state.py` | State machine — sole owner of `.log/project.yaml` |
| `scripts/launch_run.py` | Thin launcher — spawns the research_lead per phase |
| `scripts/web_phase_data.py` | Bridge: reads state + config → template-ready dicts |

## Automation scripts

### `pipeline_runner.py` — supervised multi-phase runner

Runs a chain of phases (e.g. 03→04→05→06) unattended: monitors each run to
completion, diagnoses the result, auto-approves healthy runs, and starts the
next phase. Stops and reports on any anomaly.

```bash
# Run phases 04 through 06 (handles approve → start → monitor → diagnose)
python3 scripts/pipeline_runner.py 04-numerical-validation

# From a specific phase through the end
python3 scripts/pipeline_runner.py 03-theoretical-justification
```

**When to use:** after re-approving an upstream phase that cascades staleness
downstream, or when you need to run multiple gated phases in sequence without
babysitting each one.

**Launch pattern:**
```bash
cd /home/tez/product/research-hub
python3 scripts/pipeline_runner.py 04-numerical-validation 2>&1 | tee /tmp/pipeline.log &
```

Or via Hermes: `terminal(background=True, notify_on_complete=True)` so you're
alerted when the whole chain finishes (~90–120 min for 4 phases).

**Key details:**
- The `wait_for_run_complete()` timeout is 7200s (2h) — this is just how long
  *you* poll; the run's own timeout (`config.yaml → hub.run_timeout_minutes`)
  is what kills work. Set that based on the slowest phase.
- Auto-approve only happens after the diagnosis checklist passes (healthy
  status, all rounds have outputs, summary exists). On any anomaly, the runner
  stops and reports.

### `hub_driver.py` — webapp automation primitives

Session-based HTTP client that handles CSRF tokens, version-locked hidden form
fields, and the approve/start endpoints. Used by `pipeline_runner.py`.

```python
from scripts.hub_driver import approve_run, start_phase, get_phase_tab

# Start a phase (extracts CSRF + version fields automatically)
ok, msg = start_phase('04-numerical-validation', feedback='focus on Gaussian targets')

# Approve a completed run
ok, msg = approve_run('03-theoretical-justification', 'de861134-f939-...')
```

**Why this exists:** the approve and start endpoints require version-locked
hidden fields (`phase_plan_version`, `prerequisite_report_version`,
`decision_record_version`) that change each time the page renders. This module
extracts them from the rendered HTML so programmatic callers don't have to.

### `package_and_email.py` — zip + deliver the finished paper

Packages the manuscript, phase summaries, protocol, and numerical results into
a `.zip`, then sends it via QQ Mail SMTP.

```bash
python3 scripts/package_and_email.py
```

**What it includes:** manuscript (pre + post review), reviewer diff, all 6
phase summaries (HTML), study design + method spec, numerical results JSON.
**Excludes:** raw `.npz` trace files (18 MB — too large for email).

**Credentials:** reads QQ SMTP login from `~/.config/himalaya/config.toml`.
For large attachments (>1 MB), uses Python `smtplib` directly rather than
the himalaya CLI.

## Recovery scripts (in launch_run.py, invoked via CLI subcommands)

These are called by the research_lead during a run, not directly by the user:

- `launch_run.py worker` — the main launcher subcommand (spawned by webapp)
- `launch_run.py complete` — signals run completion (called by the lead)
- `launch_run.py round-start` / `round-complete` — per-round state tracking

**Recovery routes (via webapp):**
- `POST /project/<id>/phase/<slug>/run/<run_id>/cancel` — cancels a run,
  clears stale `active_run` (zombie recovery)
- `POST /project/<id>/phase/<slug>/run/<run_id>/retry-cleanup` — retries
  cleanup after a crash
- `POST /project/<id>/phase/<slug>/run/<run_id>/recover-cleanup` — manual
  recovery override (requires verification note)
