#!/usr/bin/env python3
"""
Research Hub Dashboard
User-facing TUI to monitor and manage projects and agent workflows.
"""

import sqlite3
import yaml
import json
import os
import sys
from pathlib import Path
from hub import get_db, list_projects, get_project, get_project_tasks, project_summary, advance_workflow

HUB_DIR = Path(__file__).parent.resolve()

def clear():
    os.system("clear" if os.name != "nt" else "cls")

def print_header():
    cfg = yaml.safe_load((HUB_DIR / "config.yaml").read_text())
    name = cfg.get("hub", {}).get("name", "Research Hub")
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

def print_projects():
    projects = list_projects()
    if not projects:
        print("\n  No projects yet. Create one with: hub.py create <name>")
        return
    print("\n  Projects:")
    print(f"  {'ID':>4} {'Status':>10} {'Iter':>6} {'Name'}")
    print(f"  {'-'*50}")
    for p in projects:
        print(f"  {p['id']:4} {p['status']:>10} {p['current_iteration']:>2}/{p['max_iterations']:>2}  {p['name']}")

def print_project_detail(project_id: int):
    clear()
    print_header()
    print(project_summary(project_id))
    print()
    st = advance_workflow(project_id)
    ready = st.get("ready_tasks", [])
    if ready:
        print(f"\n  Ready to run ({len(ready)} task(s)):")
        for t in ready:
            print(f"    - {t['stage']} (agent: {t['agent_id']})")
    else:
        print("\n  No tasks ready (waiting on dependencies or all done).")
    if st.get("has_failure"):
        print("\n  ⚠️  Some tasks failed. Check logs.")
    if st.get("is_complete"):
        print("\n  🎉 All tasks in current iteration completed!")

def interactive_loop():
    while True:
        clear()
        print_header()
        print_projects()
        print("\n  Commands: [s]elect project | [c]reate | [r]efresh | [q]uit")
        choice = input("  > ").strip().lower()

        if choice == "q":
            break
        elif choice == "r":
            continue
        elif choice == "c":
            name = input("  Project name: ").strip()
            desc = input("  Description: ").strip()
            goal = input("  Goal: ").strip()
            if name:
                os.system(f"python3 {HUB_DIR}/hub.py create '{name}' '{desc}' '{goal}'")
                input("\n  Press Enter...")
        elif choice == "s":
            pid = input("  Project ID: ").strip()
            if pid.isdigit():
                project_menu(int(pid))

def project_menu(project_id: int):
    while True:
        print_project_detail(project_id)
        print("\n  [r]un step | [a]dvance | [i]teration +1 | [b]ack | [q]uit")
        choice = input("  > ").strip().lower()
        if choice == "b":
            break
        elif choice == "q":
            sys.exit(0)
        elif choice == "r":
            os.system(f"python3 {HUB_DIR}/hub.py step {project_id}")
            input("\n  Press Enter...")
        elif choice == "a":
            os.system(f"python3 {HUB_DIR}/hub.py advance {project_id}")
            input("\n  Press Enter...")
        elif choice == "i":
            os.system(f"python3 {HUB_DIR}/hub.py step {project_id}")
            input("\n  Press Enter...")

if __name__ == "__main__":
    interactive_loop()
