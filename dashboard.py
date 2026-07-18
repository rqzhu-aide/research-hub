#!/usr/bin/env python3
"""
Research Hub Dashboard — Textual TUI
Multi-panel layout: project sidebar → phase bar → phase-specific 2×2 grid.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Select,
    Static,
    TextArea,
)

from hub import (
    get_agents,
    get_phase,
    get_project_dir,
    list_projects,
    load_config,
    load_setting_template,
    poll_idea_phase,
    setup_idea_phase,
)

# ── Widgets ──────────────────────────────────────────────────────────────────

class ProjectSidebar(Vertical):
    """Left sidebar listing all projects."""

    def compose(self) -> ComposeResult:
        yield Label("📁 Projects", id="sidebar-title")
        yield ListView(id="project-list")
        yield Button("👤 Profiles", id="btn-profiles", variant="primary")

    def refresh_projects(self) -> None:
        lv = self.query_one("#project-list", ListView)
        lv.clear()
        for p in list_projects():
            label = f"#{p['id']:03d} {p['name']}"
            lv.append(ListItem(Static(label), id=f"proj-{p['id']}"))


class ProfilesPage(Vertical):
    """Full-page overview of agent profiles."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]👤 Agent Profiles[/bold]", id="profiles-header")
        yield DataTable(id="profiles-table", zebra_stripes=True)
        yield Button("← Back", id="btn-back-profiles", variant="primary")

    def on_mount(self) -> None:
        table = self.query_one("#profiles-table", DataTable)
        table.add_column("Name", width=16)
        table.add_column("Profile", width=16)
        table.add_column("Role", width=30)
        table.add_column("Model", width=18)

    def populate(self, agents: list[dict]) -> None:
        table = self.query_one("#profiles-table", DataTable)
        table.clear()
        for a in agents:
            table.add_row(
                a.get("name", ""),
                a.get("profile", ""),
                a.get("role", ""),
                a.get("model", ""),
            )


class SettingsBar(Horizontal):
    """Settings bar: theme selector, density selector, settings toggle."""

    def compose(self) -> ComposeResult:
        yield Button("⚙️", id="btn-toggle-settings", variant="primary")
        yield Label("", id="settings-label")
        yield Select([], id="sel-theme", prompt="Theme", allow_blank=True)
        yield Select(
            [("Compact", 0), ("Normal", 1), ("Spacious", 2)],
            id="sel-density",
            value=1,
            prompt="Density",
            allow_blank=False,
        )

    def populate_themes(self, themes: list[str]) -> None:
        opts = [(t, t) for t in themes]
        sel = self.query_one("#sel-theme", Select)
        sel.set_options(opts)
        if opts:
            sel.value = opts[0][1]

    def get_values(self) -> dict:
        return {
            "theme": self._sel_val("sel-theme"),
            "density": self._sel_val("sel-density") or 1,
        }

    def _sel_val(self, sid: str):
        sel = self.query_one(f"#{sid}", Select)
        val = sel.value
        return None if val is Select.BLANK else val

    def set_values(self, theme: str, density: int) -> None:
        self._safe_set("sel-theme", theme)
        self._safe_set("sel-density", density)

    def _safe_set(self, sid: str, value):
        sel = self.query_one(f"#{sid}", Select)
        try:
            sel.value = value
        except Exception:
            pass

    def set_visible(self, visible: bool) -> None:
        for wid in ("sel-theme", "sel-density", "settings-label"):
            self.query_one(f"#{wid}").display = visible
        self.query_one("#settings-label").update(" Theme | Density" if visible else "")


class PhaseBar(Horizontal):
    """Horizontal bar with phase selection buttons."""

    def compose(self) -> ComposeResult:
        yield Button("🔍 Exploration", id="btn-exploration", variant="primary")
        yield Button("📐 Math Val.", id="btn-math", disabled=True)
        yield Button("🔢 Num Val.", id="btn-num", disabled=True)
        yield Button("📝 Manuscript", id="btn-manuscript", disabled=True)


class SettingsEditor(Vertical):
    """Top-left: setting.md editor."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]Project Settings[/bold] (setting.md)", id="settings-header")
        yield TextArea(id="settings-editor", language="markdown", show_line_numbers=True)
        yield Button("💾 Save", id="btn-save-settings", variant="success")

    @property
    def editor(self) -> TextArea:
        return self.query_one("#settings-editor", TextArea)

    def load(self, text: str) -> None:
        self.editor.text = text

    @property
    def text(self) -> str:
        return self.editor.text

    def set_locked(self, locked: bool) -> None:
        self.editor.disabled = locked
        self.query_one("#btn-save-settings", Button).disabled = locked


class AgentPanel(Vertical):
    """Top-right: agent assignment selectors."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]Agent Assignment[/bold]", id="agent-header")
        yield Label("Proposer:")
        yield Select([], id="sel-proposer", prompt="Select proposer profile")
        yield Label("Critic:")
        yield Select([], id="sel-critic", prompt="Select critic profile")
        yield Label("Manager:")
        yield Select([], id="sel-manager", prompt="Select manager profile")
        yield Label("Max Rounds:")
        yield Select(
            [(str(i), i) for i in range(1, 11)],
            id="sel-max-rounds",
            value=3,
            prompt="Rounds",
        )

    def populate_profiles(self, profiles: list[str]) -> None:
        opts = [(p, p) for p in profiles]
        for sid in ("sel-proposer", "sel-critic", "sel-manager"):
            sel = self.query_one(f"#{sid}", Select)
            sel.set_options(opts)
            if opts:
                sel.value = opts[0][1]

    def get_values(self) -> dict:
        return {
            "proposer": self._sel_val("sel-proposer"),
            "critic": self._sel_val("sel-critic"),
            "manager": self._sel_val("sel-manager"),
            "max_rounds": self._sel_val("sel-max-rounds") or 3,
        }

    def set_values(self, proposer: str, critic: str, manager: str, max_rounds: int) -> None:
        self._safe_set("sel-proposer", proposer)
        self._safe_set("sel-critic", critic)
        self._safe_set("sel-manager", manager)
        self._safe_set("sel-max-rounds", max_rounds)

    def _sel_val(self, sid: str):
        sel = self.query_one(f"#{sid}", Select)
        val = sel.value
        return None if val is Select.BLANK else val

    def _safe_set(self, sid: str, value):
        sel = self.query_one(f"#{sid}", Select)
        try:
            sel.value = value
        except Exception:
            pass  # value not in options

    def set_locked(self, locked: bool) -> None:
        for sid in ("sel-proposer", "sel-critic", "sel-manager", "sel-max-rounds"):
            self.query_one(f"#{sid}", Select).disabled = locked
        self.query_one("#btn-save-agents", Button).disabled = locked


class ProgressPanel(Vertical):
    """Bottom-left: run/stop + live progress table."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]Progress[/bold]", id="progress-header")
        yield Horizontal(
            Button("▶ Run", id="btn-run", variant="primary"),
            Button("⏹ Stop", id="btn-stop", variant="error", disabled=True),
            id="run-controls",
        )
        yield DataTable(id="progress-table")
        yield Static("", id="progress-status")

    def on_mount(self) -> None:
        table = self.query_one("#progress-table", DataTable)
        table.add_column("Round")
        table.add_column("Proposer")
        table.add_column("Critic")
        table.zebra_stripes = True

    def update_table(self, rounds: list[dict]) -> None:
        table = self.query_one("#progress-table", DataTable)
        table.clear()
        for r in rounds:
            icon = {"pending": "⏳", "running": "🔄", "completed": "✅", "failed": "❌", "blocked": "🚫"}
            ps = r.get("proposer_status", "pending")
            cs = r.get("critic_status", "pending")
            table.add_row(
                str(r["round_number"]),
                f"{icon.get(ps, '?')} {ps}",
                f"{icon.get(cs, '?')} {cs}",
            )

    def set_running(self, running: bool) -> None:
        self.query_one("#btn-run", Button).disabled = running
        self.query_one("#btn-stop", Button).disabled = not running

    def set_status(self, msg: str) -> None:
        self.query_one("#progress-status", Static).update(msg)


class ChatPanel(Vertical):
    """Bottom-right: one-shot CLI to manager profile."""

    def compose(self) -> ComposeResult:
        yield Label("[bold]💬 Manager Chat[/bold]", id="chat-header")
        yield RichLog(id="chat-log", wrap=True, highlight=True)
        yield Horizontal(
            Input(placeholder="Message manager...", id="chat-input"),
            Button("Send", id="btn-send", variant="primary"),
            id="chat-controls",
        )

    def log(self, msg: str, source: str = "") -> None:
        log = self.query_one("#chat-log", RichLog)
        from rich.markup import escape as markup_escape
        safe_msg = markup_escape(msg)
        if source:
            log.write(f"[bold]{markup_escape(source)}:[/bold] {safe_msg}")
        else:
            log.write(safe_msg)

    @property
    def input_text(self) -> str:
        return self.query_one("#chat-input", Input).value

    def clear_input(self) -> None:
        self.query_one("#chat-input", Input).value = ""


# ── Main App ─────────────────────────────────────────────────────────────────

class ResearchHubApp(App):
    """Research Hub Textual Dashboard."""

    CSS = """
    /* ── Global / Theme-aware ─────────────────────────────────────────── */
    Screen {
        layout: horizontal;
    }
    #sidebar {
        width: 24%;
        height: 100%;
        border-right: solid $primary-darken-2;
        background: $surface;
        padding: 0 1;
    }
    #sidebar-title {
        text-align: center;
        padding: 1 0;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    #main-content {
        width: 76%;
        height: 100%;
        background: $background;
    }

    /* ── Settings Bar ─────────────────────────────────────────────────── */
    #settings-bar {
        height: auto;
        layout: horizontal;
        border-bottom: solid $primary-darken-2;
        padding: 0 1;
        background: $surface-darken-1;
    }
    #settings-bar Button {
        width: auto;
        min-width: 3;
    }
    #settings-bar Select {
        width: 18;
        margin: 0 1;
    }
    #settings-bar #settings-label {
        width: auto;
        content-align: center middle;
        color: $text-muted;
    }

    /* ── Phase Bar ────────────────────────────────────────────────────── */
    #phase-bar {
        height: auto;
        layout: horizontal;
        border-bottom: solid $primary-darken-2;
        padding: 0 1;
    }
    #phase-bar Button {
        width: 1fr;
        margin: 0 1;
        border: round $primary-darken-1;
        text-style: bold;
    }
    #phase-bar Button:hover {
        background: $primary-darken-1;
    }
    #phase-bar Button:disabled {
        opacity: 0.4;
        text-style: none;
    }

    /* ── Exploration Page 2×2 Grid ───────────────────────────────────── */
    #exploration-page {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr 1fr;
        height: 1fr;
        grid-gutter: 1;
        padding: 1;
    }

    /* ── Panel Base Styles ───────────────────────────────────────────── */
    #settings-panel, #agent-panel, #progress-panel, #chat-panel {
        border: round $primary-darken-2;
        padding: 1 2;
        background: $surface;
    }
    #settings-panel:focus-within, #agent-panel:focus-within,
    #progress-panel:focus-within, #chat-panel:focus-within {
        border: round $primary;
    }

    /* ── Panel Headers ────────────────────────────────────────────────── */
    #settings-header, #agent-header, #progress-header, #chat-header {
        text-style: bold;
        color: $primary-lighten-2;
        border-bottom: hkey $primary-darken-2;
        padding-bottom: 1;
        margin-bottom: 1;
    }

    /* ── Settings Editor ──────────────────────────────────────────────── */
    #settings-editor {
        height: 1fr;
        border: round $primary-darken-2;
        background: $surface-lighten-1;
    }
    #settings-editor:focus {
        border: round $accent;
    }
    #btn-save-settings {
        margin-top: 1;
        width: 100%;
    }

    /* ── Agent Panel ──────────────────────────────────────────────────── */
    #agent-panel Label {
        margin-top: 1;
        color: $text-muted;
    }
    #agent-panel Select {
        margin-bottom: 1;
    }

    /* ── Progress Panel ───────────────────────────────────────────────── */
    #progress-panel #run-controls {
        height: auto;
        margin-bottom: 1;
    }
    #progress-panel #run-controls Button {
        width: 1fr;
        margin: 0 1;
    }
    #progress-table {
        height: 1fr;
        border: round $primary-darken-2;
    }
    #progress-status {
        margin-top: 1;
        color: $text-muted;
        text-align: center;
    }

    /* ── Chat Panel ───────────────────────────────────────────────────── */
    #chat-panel #chat-log {
        height: 1fr;
        border: round $primary-darken-2;
        background: $surface-lighten-1;
        padding: 0 1;
    }
    #chat-panel #chat-controls {
        height: auto;
        margin-top: 1;
    }
    #chat-panel #chat-input {
        width: 1fr;
    }
    #chat-panel #btn-send {
        width: auto;
        min-width: 6;
    }

    /* ── Profiles Page ─────────────────────────────────────────────────── */
    #profiles-page {
        height: 1fr;
        padding: 1 2;
        background: $surface;
    }
    #profiles-header {
        text-style: bold;
        color: $primary-lighten-2;
        border-bottom: hkey $primary-darken-2;
        padding-bottom: 1;
        margin-bottom: 1;
    }
    #profiles-table {
        height: 1fr;
        border: round $primary-darken-2;
    }
    #btn-back-profiles {
        margin-top: 1;
        width: auto;
        min-width: 10;
    }

    /* ── Sidebar Button ────────────────────────────────────────────────── */
    #sidebar #btn-profiles {
        width: 100%;
        margin-top: 1;
    }

    /* ── Density Variants ─────────────────────────────────────────────── */
    .-density-compact #exploration-page {
        grid-gutter: 0;
        padding: 0;
    }
    .-density-compact #settings-panel,
    .-density-compact #agent-panel,
    .-density-compact #progress-panel,
    .-density-compact #chat-panel {
        padding: 0 1;
    }
    .-density-compact #settings-header,
    .-density-compact #agent-header,
    .-density-compact #progress-header,
    .-density-compact #chat-header {
        padding-bottom: 0;
        margin-bottom: 0;
    }
    .-density-compact #agent-panel Label {
        margin-top: 0;
    }
    .-density-compact #progress-panel #run-controls {
        margin-bottom: 0;
    }
    .-density-compact #progress-status {
        margin-top: 0;
    }
    .-density-compact #chat-panel #chat-controls {
        margin-top: 0;
    }

    .-density-spacious #exploration-page {
        grid-gutter: 2;
        padding: 2;
    }
    .-density-spacious #settings-panel,
    .-density-spacious #agent-panel,
    .-density-spacious #progress-panel,
    .-density-spacious #chat-panel {
        padding: 2 3;
    }
    .-density-spacious #settings-header,
    .-density-spacious #agent-header,
    .-density-spacious #progress-header,
    .-density-spacious #chat-header {
        padding-bottom: 2;
        margin-bottom: 2;
    }
    .-density-spacious #agent-panel Label {
        margin-top: 2;
    }
    .-density-spacious #progress-panel #run-controls {
        margin-bottom: 2;
    }
    .-density-spacious #progress-status {
        margin-top: 2;
    }
    .-density-spacious #chat-panel #chat-controls {
        margin-top: 2;
    }
    .-density-compact #profiles-page {
        padding: 0;
    }
    .-density-compact #profiles-header {
        padding-bottom: 0;
        margin-bottom: 0;
    }
    .-density-compact #btn-back-profiles {
        margin-top: 0;
    }
    .-density-spacious #profiles-page {
        padding: 2 3;
    }
    .-density-spacious #profiles-header {
        padding-bottom: 2;
        margin-bottom: 2;
    }
    .-density-spacious #btn-back-profiles {
        margin-top: 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("t", "toggle_settings", "Toggle Settings"),
    ]

    selected_project_id: reactive[int | None] = reactive(None)
    is_running: reactive[bool] = reactive(False)
    density: reactive[int] = reactive(1)
    current_view: reactive[str] = reactive("exploration")
    poll_timer = None
    board_slug: str = ""
    _settings_visible: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar"):
            yield ProjectSidebar()
        with Vertical(id="main-content"):
            yield SettingsBar(id="settings-bar")
            yield PhaseBar(id="phase-bar")
            with Grid(id="exploration-page"):
                yield SettingsEditor(id="settings-panel")
                yield AgentPanel(id="agent-panel")
                yield ProgressPanel(id="progress-panel")
                yield ChatPanel(id="chat-panel")
            yield ProfilesPage(id="profiles-page")

    def on_mount(self) -> None:
        self.query_one(ProjectSidebar).refresh_projects()
        cfg = load_config()
        agents = get_agents(cfg)
        profiles = [a["profile"] for a in agents]
        self.query_one(AgentPanel).populate_profiles(profiles)
        # Initialize theme + density
        sb = self.query_one(SettingsBar)
        sb.populate_themes(self.available_themes)
        sb.set_values(self.theme, self.density)
        sb.set_visible(False)
        # Apply initial density class
        self._apply_density()
        # Populate profiles page
        self.query_one(ProfilesPage).populate(agents)
        # Start in exploration view
        self._show_view("exploration")

    def watch_density(self, density: int) -> None:
        self._apply_density()

    def _apply_density(self) -> None:
        classes = {
            "-density-compact": self.density == 0,
            "-density-spacious": self.density == 2,
        }
        self.update_classes(classes)

    def action_toggle_settings(self) -> None:
        self._settings_visible = not self._settings_visible
        self.query_one(SettingsBar).set_visible(self._settings_visible)

    def watch_current_view(self, view: str) -> None:
        self._show_view(view)

    def _show_view(self, view: str) -> None:
        show_exploration = view == "exploration"
        self.query_one("#exploration-page").display = show_exploration
        self.query_one("#phase-bar").display = show_exploration
        self.query_one("#profiles-page").display = not show_exploration

    def on_select_changed(self, event: Select.Changed) -> None:
        val = event.value
        if val is Select.BLANK:
            return
        sel_id = event.select.id
        if sel_id == "sel-theme":
            self.theme = str(val)
        elif sel_id == "sel-density":
            self.density = int(val)

    # ── Project selection ───────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id
        if not item_id or not item_id.startswith("proj-"):
            return
        pid = int(item_id.split("-")[1])
        if pid == self.selected_project_id:
            return
        # Stop monitoring the previous project if running
        if self.is_running:
            self._do_stop()
        self.selected_project_id = pid

    async def watch_selected_project_id(self, pid: int | None) -> None:
        if pid is None:
            return
        self._load_project_settings(pid)
        self._load_phase_config(pid)
        await self._refresh_progress()

    def _load_project_settings(self, pid: int) -> None:
        proj_dir = get_project_dir(pid)
        if not proj_dir:
            return
        settings_path = proj_dir / "setting.md"
        goals_path = proj_dir / "goals.md"
        if not settings_path.exists():
            if goals_path.exists():
                # Migrate old goals.md to setting.md
                settings_path.write_text(goals_path.read_text())
            else:
                settings_path.write_text(load_setting_template())
        self.query_one(SettingsEditor).load(settings_path.read_text())

    def _load_phase_config(self, pid: int) -> None:
        phase = get_phase(pid, "00-idea")
        panel = self.query_one(AgentPanel)
        if phase and phase["config_json"]:
            cfg = json.loads(phase["config_json"])
            panel.set_values(
                cfg.get("proposer", ""),
                cfg.get("critic", ""),
                cfg.get("manager", ""),
                phase["max_rounds"],
            )
            self.board_slug = f"rhub-p{pid}"
            # If phase already running, resume monitoring
            if phase["status"] in ("running", "active") and not self.is_running:
                self.is_running = True
                self._lock_ui(True)
                self.poll_timer = self.set_interval(3.0, self._poll_status)
        else:
            # defaults: pick distinct agents from config
            cfg_yaml = load_config()
            agents = get_agents(cfg_yaml)
            if agents:
                proposer = agents[0]["profile"]
                critic = agents[1]["profile"] if len(agents) > 1 else proposer
                manager = agents[-1]["profile"]
                if manager == proposer or manager == critic:
                    # Try to find a 3rd distinct profile
                    for a in agents:
                        if a["profile"] not in (proposer, critic):
                            manager = a["profile"]
                            break
                panel.set_values(proposer, critic, manager, 3)

    # ── Settings / Agents save ──────────────────────────────────────────────

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-save-settings":
            self._save_settings()
        elif btn_id == "btn-toggle-settings":
            self.action_toggle_settings()
        elif btn_id == "btn-profiles":
            self.current_view = "profiles"
        elif btn_id == "btn-back-profiles":
            self.current_view = "exploration"
        elif btn_id == "btn-run":
            await self.action_run()
        elif btn_id == "btn-stop":
            await self.action_stop()
        elif btn_id == "btn-send":
            await self.action_send_chat()

    def _save_settings(self) -> None:
        pid = self.selected_project_id
        if pid is None:
            self.notify("No project selected", severity="error")
            return
        proj_dir = get_project_dir(pid)
        if not proj_dir:
            return
        text = self.query_one(SettingsEditor).text
        (proj_dir / "setting.md").write_text(text)
        self.notify("Settings saved.")

    # ── Run / Stop ────────────────────────────────────────────────────────────────

    async def action_run(self) -> None:
        pid = self.selected_project_id
        if pid is None:
            self.notify("Select a project first.", severity="error")
            return

        vals = self.query_one(AgentPanel).get_values()
        if not all([vals["proposer"], vals["critic"], vals["manager"]]):
            self.notify("Select all three agent profiles.", severity="error")
            return

        # Guard: don't re-run if already running
        if self.is_running:
            self.notify("Phase is already running. Stop first to re-run.", severity="warning")
            return

        # Save settings
        self._save_settings()

        self.board_slug = f"rhub-p{pid}"
        self.is_running = True

        # Setup phase (creates kanban board + task chain) in background thread
        try:
            await asyncio.to_thread(
                setup_idea_phase,
                pid,
                vals["proposer"],
                vals["critic"],
                vals["manager"],
                vals["max_rounds"],
            )
            self.notify(f"Idea phase started on board {self.board_slug}")
        except Exception as e:
            self.is_running = False
            self.notify(f"Setup failed: {e}", severity="error")
            return

        self._lock_ui(True)
        self.poll_timer = self.set_interval(3.0, self._poll_status)

    async def action_stop(self) -> None:
        self._do_stop()
        self.query_one(ProgressPanel).set_status("Stopped by user.")

    def _do_stop(self) -> None:
        """Sync stop logic — safe to call from anywhere."""
        self.is_running = False
        if self.poll_timer:
            self.poll_timer.stop()
            self.poll_timer = None
        self._lock_ui(False)

    def _lock_ui(self, locked: bool) -> None:
        self.query_one(SettingsEditor).set_locked(locked)
        self.query_one(AgentPanel).set_locked(locked)
        self.query_one(ProgressPanel).set_running(locked)

    # ── Polling ─────────────────────────────────────────────────────────────

    async def _poll_status(self) -> None:
        pid = self.selected_project_id
        if pid is None:
            return
        try:
            status = await asyncio.to_thread(poll_idea_phase, pid)
        except Exception as e:
            self.query_one(ProgressPanel).set_status(f"Poll error: {e}")
            return

        if not status:
            return

        self.query_one(ProgressPanel).update_table(status.get("rounds", []))

        phase = status.get("phase", {})
        if phase.get("status") == "completed":
            self.query_one(ProgressPanel).set_status("✅ Phase completed.")
            self._do_stop()
        elif phase.get("status") == "failed":
            self.query_one(ProgressPanel).set_status("❌ Phase failed.")
            self._do_stop()
        else:
            running = sum(
                1 for r in status.get("rounds", [])
                if r.get("proposer_status") == "running" or r.get("critic_status") == "running"
            )
            done = sum(
                1 for r in status.get("rounds", [])
                if r.get("critic_status") == "completed"
            )
            total = len(status.get("rounds", []))
            self.query_one(ProgressPanel).set_status(
                f"Running: {running} | Completed: {done}/{total} rounds"
            )

    async def _refresh_progress(self) -> None:
        if self.selected_project_id:
            await self._poll_status()

    async def action_refresh(self) -> None:
        self.query_one(ProjectSidebar).refresh_projects()
        await self._refresh_progress()

    # ── Chat ────────────────────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in any Input widget."""
        if event.input.id == "chat-input":
            # Fire-and-forget the async chat send
            asyncio.create_task(self.action_send_chat())

    async def action_send_chat(self) -> None:
        panel = self.query_one(ChatPanel)
        msg = panel.input_text.strip()
        if not msg:
            return
        panel.clear_input()
        panel.log(msg, source="You")

        vals = self.query_one(AgentPanel).get_values()
        manager = vals.get("manager")
        if not manager:
            panel.log("No manager profile selected.", source="System")
            return

        # Disable input while waiting
        chat_input = panel.query_one("#chat-input", Input)
        send_btn = panel.query_one("#btn-send", Button)
        chat_input.disabled = True
        send_btn.disabled = True
        panel.log("⏳ Thinking...", source="Manager")

        try:
            proc = await asyncio.create_subprocess_exec(
                "hermes", "-z", msg, "--profile", manager,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)
            output = stdout.decode().strip() or stderr.decode().strip() or "(no response)"
        except asyncio.TimeoutError:
            output = "⏱️ Manager response timed out."
        except Exception as e:
            output = f"Error: {e}"
        finally:
            chat_input.disabled = False
            send_btn.disabled = False

        panel.log(output, source="Manager")


if __name__ == "__main__":
    app = ResearchHubApp()
    app.run()
