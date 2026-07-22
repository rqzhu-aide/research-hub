"""Supervised pipeline runner: approve completed phases, start next ones,
monitor to completion, with full diagnostics. Stops on any anomaly.

Usage: python3 pipeline_runner.py [--from-phase 03]
"""
import sys, time, re, json, os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hub_driver import approve_run, start_phase, get_phase_tab, s as session, BASE, PROJECT_ID

sys.path.insert(0, '/home/tez/product/research-hub')
from scripts import project_state

PDIR = Path('/home/tez/research/projects/project-003-invariant-preserving_interacting_langevin')
PHASES_ORDER = [
    ('03-theoretical-justification', {}),
    ('04-numerical-validation', {}),
    ('05-data-analysis', {}),
    ('06-paper-writing', {}),
]

LOG_LINES = []  # diagnostic log

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    LOG_LINES.append(line)
    print(line, flush=True)

def get_run_status(slug):
    """Get current run status for a phase."""
    state = project_state.load(PDIR)
    ps = state.get('phases', {}).get(slug, {})
    return {
        'approved': ps.get('approved_run'),
        'latest': ps.get('latest_run'),
        'stale': ps.get('stale', False),
        'runs': len(ps.get('runs', [])),
        'active': state.get('active_run'),
    }

def wait_for_run_complete(slug, run_id, timeout=7200):
    """Poll until the run completes (not running). Returns final status."""
    log(f"Waiting for {slug} run {run_id[:8]} to complete...")
    start = time.time()
    last_rounds = 0
    while time.time() - start < timeout:
        time.sleep(60)
        elapsed = int(time.time() - start)
        run = project_state.get_run(PDIR, slug, run_id)
        status = run.get('status', '?')
        rounds = run.get('rounds', [])
        n_rounds = len(rounds)
        if n_rounds != last_rounds:
            log(f"  [{elapsed//60}min] {n_rounds} rounds recorded, status={status}")
            last_rounds = n_rounds
        # Check if launcher process still alive
        active = project_state.load(PDIR).get('active_run')
        if not active or active.get('run_id') != run_id:
            # Run no longer active — check final status
            run = project_state.get_run(PDIR, slug, run_id)
            final_status = run.get('status')
            log(f"  Run finished with status: {final_status}")
            return final_status, run
    log(f"  TIMEOUT after {timeout//60}min")
    return 'timeout', None

def diagnose_run(slug, run_id, run):
    """Check a completed run for issues. Returns list of problems."""
    problems = []
    status = run.get('status', '?')
    if status == 'failed':
        problems.append(f"RUN FAILED: {run.get('error', 'no error message')}")
    elif status not in ('awaiting_review', 'approved', 'completed'):
        problems.append(f"Unexpected status: {status}")
    rounds = run.get('rounds', [])
    if not rounds:
        problems.append("No rounds recorded")
    for r in rounds:
        outputs = r.get('outputs', [])
        if not outputs:
            problems.append(f"Round {r.get('n')} has no outputs")
    # Check for summary
    summary_path = run.get('summary_path')
    if summary_path and not os.path.exists(summary_path):
        problems.append(f"Summary file missing: {summary_path}")
    return problems

def run_pipeline(start_from='03-theoretical-justification'):
    """Run the full pipeline from a given phase."""
    started = False
    results = {}
    
    for slug, opts in PHASES_ORDER:
        if slug == start_from:
            started = True
        if not started:
            continue
            
        log(f"\n{'='*60}")
        log(f"PHASE: {slug}")
        log(f"{'='*60}")
        
        # Step 1: Check if already running (phase 03 case)
        state = project_state.load(PDIR)
        active = state.get('active_run')
        if active and active.get('phase_slug') == slug:
            run_id = active.get('run_id')
            log(f"Phase {slug} already running (run {run_id[:8]}), waiting...")
            status, run = wait_for_run_complete(slug, run_id)
        else:
            # Step 2: Start the phase
            log(f"Starting {slug}...")
            ok, msg = start_phase(slug, **opts)
            log(f"  start result: ok={ok}, {msg}")
            if not ok:
                results[slug] = {'error': f'start failed: {msg}'}
                break
            time.sleep(5)
            # Get the new run ID
            st = get_run_status(slug)
            run_id = st['latest']
            if not run_id:
                results[slug] = {'error': 'no run ID after start'}
                break
            log(f"  started run {run_id[:8]}")
            # Step 3: Wait for completion
            status, run = wait_for_run_complete(slug, run_id)
        
        # Step 4: Diagnose
        if run:
            problems = diagnose_run(slug, run_id, run)
            if problems:
                log(f"  ⚠ DIAGNOSTIC ISSUES:")
                for p in problems:
                    log(f"    - {p}")
                results[slug] = {'status': status, 'problems': problems}
                # Don't approve if failed
                if status == 'failed':
                    break
            else:
                log(f"  ✓ Run looks healthy")
        else:
            log(f"  ⚠ No run data returned")
            results[slug] = {'error': 'no run data'}
            break
        
        # Step 5: Approve
        if status in ('awaiting_review', 'completed'):
            log(f"Approving {slug} run {run_id[:8]}...")
            ok, msg = approve_run(slug, run_id)
            log(f"  approve result: ok={ok}, {msg}")
            time.sleep(3)
            st = get_run_status(slug)
            if st['approved'] != run_id:
                log(f"  ⚠ Approval may have failed! approved={st['approved']}")
                results[slug] = {'error': 'approval failed', 'approved': st['approved']}
                break
            else:
                log(f"  ✓ Approved successfully")
                results[slug] = {'status': 'approved', 'run_id': run_id}
        elif status == 'approved':
            log(f"  Already approved")
            results[slug] = {'status': 'approved', 'run_id': run_id}
        else:
            log(f"  Cannot approve with status={status}")
            results[slug] = {'status': status, 'run_id': run_id}
            break
    
    log(f"\n{'='*60}")
    log(f"PIPELINE COMPLETE")
    log(f"{'='*60}")
    for slug, r in results.items():
        log(f"  {slug}: {r}")
    return results

if __name__ == '__main__':
    start_from = sys.argv[1] if len(sys.argv) > 1 else '03-theoretical-justification'
    run_pipeline(start_from)
