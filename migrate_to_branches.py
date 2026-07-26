#!/usr/bin/env python3
"""Full migration: move flat run dirs into branches/spectral-graph-coupling/
and rewrite every reference in sealed artifacts, summaries, and manifests.

Runs AFTER Phase 3 Run 4 finishes so it doesn't get disrupted.

Mapping:
  evaluations/run/01            -> branches/spectral-graph-coupling/evaluations/run/01
  evaluations/run/02            -> branches/spectral-graph-coupling/evaluations/run/02
  evaluations/run/04 (stray)    -> DELETE (real output already in branch path)
  draft/sections/run/01         -> branches/spectral-graph-coupling/draft/sections/run/01

Rewrites:
  - All *.manifest.json, *.prompt.md, *.task.md, *.decision.json, *.html
    under .research-hub-control/.../runs/
  - All phase-summaries/**/*.html and *.decision.json
  - project_state.json run metadata (output_root fields)

After migration, the flat paths are gone and everything resolves to the branch.
"""
import json
import re
import shutil
from pathlib import Path

PROJECT = Path('/home/tez/research/projects/project-004-entangled-langevin-sampling')
CONTROL = Path('/home/tez/research/projects/.research-hub-control/project-004-entangled-langevin-sampling')
METHOD = 'spectral-graph-coupling'
BRANCH = f'branches/{METHOD}'

# Path substitutions as (regex, replacement-template) — anchored to path
# boundaries via a capture group to avoid partial matches like
# 'evaluations/run/01' inside 'evaluations/run/012' or 'some-evaluations/run/01'.
# Boundary = start-of-string, '/', '"', "'", '`', '(', ')', or whitespace.
PRE = r'(^|[/"\'`()])'   # capture group 1: boundary char before
POST = r'(?=/|$|["\'`) ])' # lookahead: boundary after (fixed-width, OK)
SUBSTITUTIONS = [
    (re.compile(PRE + r'evaluations/run/01' + POST),
     r'\1' + f'{BRANCH}/evaluations/run/01'),
    (re.compile(PRE + r'evaluations/run/02' + POST),
     r'\1' + f'{BRANCH}/evaluations/run/02'),
    (re.compile(PRE + r'draft/sections/run/01' + POST),
     r'\1' + f'{BRANCH}/draft/sections/run/01'),
]

def rewrite_text(content: str) -> str:
    """Apply all path substitutions to a text blob."""
    for pattern, replacement in SUBSTITUTIONS:
        content = pattern.sub(replacement, content)
    return content

def rewrite_file(path: Path) -> bool:
    """Rewrite a file in place. Returns True if changed."""
    try:
        original = path.read_text(errors='ignore')
    except Exception:
        return False
    new = rewrite_text(original)
    if new != original:
        path.write_text(new)
        return True
    return False

def move_run_dir(src: Path, dst: Path):
    """Move a run directory, merging into existing dst parent."""
    if not src.exists():
        print(f'  SKIP (not found): {src}')
        return
    if dst.exists():
        print(f'  MERGE: {src} -> {dst} (dst exists, merging contents)')
        for item in src.iterdir():
            target = dst / item.name
            if target.exists():
                shutil.rmtree(target) if target.is_dir() else target.unlink()
            shutil.move(str(item), str(target))
        src.rmdir()
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f'  MOVED: {src} -> {dst}')

def rewrite_json_paths(obj):
    """Recursively rewrite path-like string values in a JSON structure."""
    if isinstance(obj, dict):
        return {k: rewrite_json_paths(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [rewrite_json_paths(v) for v in obj]
    elif isinstance(obj, str):
        return rewrite_text(obj)
    return obj

def main():
    print('=== PHASE 1: Move flat run directories into branch ===')
    moves = [
        (PROJECT / 'evaluations/run/01', PROJECT / f'{BRANCH}/evaluations/run/01'),
        (PROJECT / 'evaluations/run/02', PROJECT / f'{BRANCH}/evaluations/run/02'),
        (PROJECT / 'draft/sections/run/01', PROJECT / f'{BRANCH}/draft/sections/run/01'),
    ]
    for src, dst in moves:
        move_run_dir(src, dst)

    # Delete the stray flat run/04 (duplicate of branch path)
    stray = PROJECT / 'evaluations/run/04'
    if stray.exists():
        shutil.rmtree(stray)
        print(f'  DELETED stray: {stray}')

    # Clean up empty flat run parents
    for flat_parent in [PROJECT / 'evaluations/run', PROJECT / 'draft/sections/run']:
        if flat_parent.exists() and not any(flat_parent.iterdir()):
            flat_parent.rmdir()
            print(f'  REMOVED empty: {flat_parent}')
        elif flat_parent.exists():
            remaining = [x.name for x in flat_parent.iterdir()]
            print(f'  WARNING: {flat_parent} still has: {remaining}')

    print()
    print('=== PHASE 2: Rewrite references in sealed artifacts ===')
    # Control dir: manifests, prompts, task files, context summaries, decisions
    control_runs = CONTROL / 'runs'
    text_files_rewritten = 0
    json_files_rewritten = 0
    for f in control_runs.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix == '.json':
            try:
                data = json.loads(f.read_text())
                new_data = rewrite_json_paths(data)
                if new_data != data:
                    f.write_text(json.dumps(new_data, indent=2))
                    json_files_rewritten += 1
            except (json.JSONDecodeError, Exception):
                pass
        elif f.suffix in {'.md', '.html'}:
            if rewrite_file(f):
                text_files_rewritten += 1
    print(f'  Control dir: {json_files_rewritten} JSON, {text_files_rewritten} text files rewritten')

    print()
    print('=== PHASE 3: Rewrite phase summaries ===')
    summaries = PROJECT / 'phase-summaries'
    sum_rewritten = 0
    for f in summaries.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix in {'.html', '.json', '.md'}:
            if f.suffix == '.json':
                try:
                    data = json.loads(f.read_text())
                    new_data = rewrite_json_paths(data)
                    if new_data != data:
                        f.write_text(json.dumps(new_data, indent=2))
                        sum_rewritten += 1
                        continue
                except (json.JSONDecodeError, Exception):
                    pass
            if rewrite_file(f):
                sum_rewritten += 1
    print(f'  {sum_rewritten} summary files rewritten')

    print()
    print('=== PHASE 4: Rewrite project.yaml (state file) ===')
    state_file = CONTROL / 'project.yaml'
    if state_file.exists():
        original = state_file.read_text()
        new = rewrite_text(original)
        if new != original:
            state_file.write_text(new)
            print('  project.yaml rewritten')
        else:
            print('  project.yaml: no changes needed')
    else:
        print('  project.yaml not found')

    print()
    print('=== MIGRATION COMPLETE ===')
    print('Verify with:')
    print('  find evaluations/run draft/sections/run -type d 2>/dev/null  # should be empty/gone')
    print('  find branches/spectral-graph-coupling -type d  # should contain all runs')

if __name__ == '__main__':
    main()
