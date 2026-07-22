"""Drive the research-hub webapp: approve runs, start phases, poll status.

Maintains a requests session with CSRF cookie. Extracts version-locked hidden
fields from the rendered phase tab so approvals and starts satisfy all checks.
"""
import re, sys, time, html as html_mod
import requests

BASE = "http://localhost:5055"
PROJECT_ID = 3

s = requests.Session()
s.headers.update({"User-Agent": "hub-driver/1.0"})


def _extract(html: str, name: str) -> str:
    """Extract a hidden input value by name from rendered HTML."""
    m = re.search(rf'name="{re.escape(name)}"\s+value="([^"]*)"', html)
    return html_mod.unescape(m.group(1)) if m else ""


def get_phase_tab(slug: str) -> str:
    """GET the phase tab HTML, returning the full page text."""
    r = s.get(f"{BASE}/project/{PROJECT_ID}?tab={slug}", timeout=20)
    r.raise_for_status()
    return r.text


def approve_run(slug: str, run_id: str, approval_kind: str = "approve",
                note: str = "") -> tuple[bool, str]:
    """Approve a run. Returns (success, message)."""
    html = get_phase_tab(slug)
    csrf = _extract(html, "csrf_token")
    pid = _extract(html, "project_identity")
    drv = _extract(html, "decision_record_version")
    acrv = _extract(html, "approval_context_report_version")
    if not csrf or not pid or not drv:
        return False, f"missing hidden fields: csrf={bool(csrf)} pid={bool(pid)} drv={bool(drv)}"
    form = {
        "csrf_token": csrf,
        "project_identity": pid,
        "decision_record_version": drv,
        "accept_proposed_baseline": "1",
        "approval_kind": approval_kind,
        "approval_note": note,
    }
    # Phase 02 (method-development) requires method selection acknowledgement
    if slug == "02-method-development":
        form["accept_selected_scientific_object"] = "1"
    # Context acknowledgement only if the field is present in the page
    if acrv:
        form["approval_context_report_version"] = acrv
        form["acknowledge_context"] = "1"
    r = s.post(f"{BASE}/project/{PROJECT_ID}/phase/{slug}/run/{run_id}/approve",
               data=form, timeout=20, allow_redirects=True)
    # Follow-up GET to see flash message
    after = s.get(f"{BASE}/project/{PROJECT_ID}?tab={slug}", timeout=20).text
    # Look for flash messages
    flashes = re.findall(r'class="(?:flash|alert)[^"]*"[^>]*>([^<]+)', after)
    ok = r.status_code in (200, 302)
    return ok, f"HTTP {r.status_code}; flashes={flashes[:3]}"


def start_phase(slug: str, feedback: str = "", rounds: str = "",
                theory_plan: str = "") -> tuple[bool, str]:
    """Start a phase run. Returns (success, message)."""
    html = get_phase_tab(slug)
    csrf = _extract(html, "csrf_token")
    pid = _extract(html, "project_identity")
    ppv = _extract(html, "phase_plan_version")
    prv = _extract(html, "prerequisite_report_version")
    if not csrf or not pid or not ppv:
        return False, f"missing hidden fields: csrf={bool(csrf)} pid={bool(pid)} ppv={bool(ppv)}"
    form = {
        "csrf_token": csrf,
        "project_identity": pid,
        "phase_plan_version": ppv,
        "prerequisite_report_version": prv,
        "feedback": feedback,
    }
    if rounds:
        form["rounds"] = str(rounds)
    if slug == "03-theoretical-justification":
        form["theory_plan"] = theory_plan or "standard"
    r = s.post(f"{BASE}/project/{PROJECT_ID}/phase/{slug}/start",
               data=form, timeout=30, allow_redirects=True)
    # Capture flash from the POST response (followed redirect) directly
    flashes = re.findall(r'class="flash[^"]*"[^>]*>\s*<span[^>]*>([^<]*)', r.text)
    if not flashes:
        flashes = re.findall(r'class="flash[^"]*"[^>]*>[\s\S]*?</div>', r.text)[:3]
    ok = r.status_code in (200, 302)
    return ok, f"HTTP {r.status_code}; flashes={flashes[:3]}"


def latest_run_id(slug: str) -> str:
    """Get the latest run ID for a phase from the rendered page."""
    html = get_phase_tab(slug)
    # Run IDs are UUIDs; find them in run detail links
    ids = re.findall(r'/run/([0-9a-f-]{36})', html)
    return ids[0] if ids else ""


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    slug = sys.argv[2] if len(sys.argv) > 2 else ""
    if action == "approve":
        rid = sys.argv[3] if len(sys.argv) > 3 else ""
        print(approve_run(slug, rid))
    elif action == "start":
        print(start_phase(slug))
