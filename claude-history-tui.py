#!/usr/bin/env python3
"""
Claude Code History TUI Browser
An interactive terminal UI for browsing and managing Claude Code sessions.
"""

import argparse
import json
import os
import re
import shutil
import textwrap
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import List, Dict, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
    Button,
    RichLog,
)
from textual.message import Message
from textual import events
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown
from rich.console import Console
from rich.theme import Theme


class ClaudeHistoryBrowser:
    """Session data access layer - shared with claude-history-browser.py"""

    def __init__(self, claude_dir: str = None):
        self.claude_dir = Path(claude_dir or os.path.expanduser("~/.claude"))
        self.projects_dir = self.claude_dir / "projects"
        self.file_history_dir = self.claude_dir / "file-history"

    def find_all_projects(self) -> List[Path]:
        """Find all project directories."""
        if not self.projects_dir.exists():
            return []
        return [p for p in self.projects_dir.iterdir() if p.is_dir()]

    def load_sessions_index(self, project_dir: Path) -> Dict:
        """Load sessions index for a project."""
        index_file = project_dir / "sessions-index.json"
        if not index_file.exists():
            return {"entries": [], "originalPath": str(project_dir)}
        with open(index_file, "r") as f:
            return json.load(f)

    def save_sessions_index(self, project_dir: Path, index: Dict):
        """Save sessions index for a project."""
        index_file = project_dir / "sessions-index.json"
        with open(index_file, "w") as f:
            json.dump(index, f, indent=2)

    def load_session_messages(self, session_file: Path) -> List[Dict]:
        """Load all messages from a session JSONL file."""
        if not session_file.exists():
            return []
        messages = []
        with open(session_file, "r") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get("type") in ["user", "assistant"]:
                        messages.append(data)
                except json.JSONDecodeError:
                    continue
        return messages

    def extract_session_metadata(self, session_file: Path) -> Optional[Dict]:
        """Extract metadata from a session .jsonl file directly."""
        try:
            messages = self.load_session_messages(session_file)
            if not messages:
                return None

            first_user_msg = next(
                (m for m in messages if m.get("message", {}).get("role") == "user"),
                None,
            )
            if not first_user_msg:
                return None

            first_prompt = self._extract_message_text(first_user_msg)
            if len(first_prompt) > 150:
                first_prompt = first_prompt[:150] + "..."

            created = first_user_msg.get("timestamp", "")
            modified = messages[-1].get("timestamp", created)
            session_id = session_file.stem
            git_branch = messages[0].get("gitBranch", "N/A")
            project_path = messages[0].get("cwd", "N/A")

            summary = first_prompt.split("\n")[0][:100]
            if len(summary) < len(first_prompt.split("\n")[0]):
                summary += "..."

            return {
                "sessionId": session_id,
                "fullPath": str(session_file),
                "firstPrompt": first_prompt,
                "summary": summary,
                "messageCount": len(messages),
                "created": created,
                "modified": modified,
                "gitBranch": git_branch,
                "projectPath": project_path,
                "isSidechain": False,
                "isUnindexed": True,
            }
        except Exception:
            return None

    def _extract_message_text(self, msg: Dict, include_thinking: bool = False) -> str:
        """Extract text content from a message."""
        message = msg.get("message", {})
        content = message.get("content", "")

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                    elif item.get("type") == "thinking" and include_thinking:
                        texts.append(f"[thinking] {item.get('thinking', '')}")
                elif isinstance(item, str):
                    texts.append(item)
            return " ".join(texts)
        return ""

    def _is_system_noise(self, text: str) -> bool:
        """Check if text is system noise that should be filtered out."""
        if not text:
            return True
        text_stripped = text.strip()
        noise_patterns = [
            "<local-command-caveat>",
            "<command-name>",
            "<local-command-stdout>",
            "<command-args>",
            "</local-command-caveat>",
            "</command-name>",
            "</local-command-stdout>",
            "</command-args>",
            "[Request interrupted by user",
            "No response requested.",
        ]
        for pattern in noise_patterns:
            if pattern in text_stripped:
                return True
        if text_stripped.startswith("<") and text_stripped.endswith(">"):
            return True
        return False

    def _is_transitional_message(self, text: str, max_chars: int = 250) -> bool:
        """Check if text is a short transitional/narration message.

        These are brief messages where Claude explains what it's about to do,
        like "Let me read the file" or "Now I'll add the function".
        """
        if not text or len(text) > max_chars:
            return False

        text_lower = text.lower().strip()

        # Direct transitional starters
        direct_transitional_starts = [
            "now update ", "now add ", "now create ", "now run ",
            "now check ", "now test ", "now fix ", "now modify ",
            "now read ", "now look ", "now find ", "now search ",
            "now implement ", "now write ", "now remove ", "now delete ",
            "now change ", "now replace ", "now refactor ", "now enhance ",
        ]

        if any(text_lower.startswith(start) for start in direct_transitional_starts):
            return True

        # Phrases that indicate transitional narration
        transitional_phrases = [
            "let me ", "let's ", "i'll ", "i will ",
            "i need to ", "i should ", "i'm going to ",
        ]

        has_transitional_phrase = any(phrase in text_lower for phrase in transitional_phrases)

        if not has_transitional_phrase:
            return False

        # Additional patterns that often prefix transitional messages
        prefix_patterns = [
            "now ", "first, ", "next, ", "excellent!", "great!",
            "perfect!", "good!", "ok,", "okay,", "alright,", "i see", "the ",
        ]

        if any(text_lower.startswith(phrase) for phrase in transitional_phrases):
            return True

        if any(text_lower.startswith(prefix) for prefix in prefix_patterns):
            return True

        if len(text) < 200:
            return True

        return False

    def get_all_sessions(self) -> List[Dict]:
        """Get all sessions from all projects, including unindexed ones."""
        all_sessions = []

        for project_dir in self.find_all_projects():
            index = self.load_sessions_index(project_dir)
            indexed_session_ids = set()

            for entry in index.get("entries", []):
                entry["project_dir"] = str(project_dir)
                entry["project_name"] = project_dir.name
                entry["isUnindexed"] = False
                all_sessions.append(entry)
                indexed_session_ids.add(entry["sessionId"])

            for jsonl_file in project_dir.glob("*.jsonl"):
                session_id = jsonl_file.stem
                if session_id not in indexed_session_ids:
                    metadata = self.extract_session_metadata(jsonl_file)
                    if metadata:
                        metadata["project_dir"] = str(project_dir)
                        metadata["project_name"] = project_dir.name
                        all_sessions.append(metadata)

        return all_sessions

    def format_date(self, date_str: str) -> str:
        """Format ISO date string to readable format."""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return date_str


class SessionDeletionService:
    """Handles clean deletion of sessions and associated files."""

    def __init__(self, browser: ClaudeHistoryBrowser):
        self.browser = browser

    def get_files_to_delete(self, session: Dict) -> Dict[str, List[str]]:
        """Get list of files that would be deleted for a session."""
        files = {"session_file": [], "index_entry": [], "file_history": []}

        session_file = Path(session.get("fullPath", ""))
        if session_file.exists():
            files["session_file"].append(str(session_file))

        if not session.get("isUnindexed", True):
            project_dir = Path(session.get("project_dir", ""))
            index_file = project_dir / "sessions-index.json"
            if index_file.exists():
                files["index_entry"].append(str(index_file))

        session_id = session.get("sessionId", "")
        file_history_dir = self.browser.file_history_dir / session_id
        if file_history_dir.exists():
            files["file_history"].append(str(file_history_dir))

        return files

    def delete_session(self, session: Dict) -> Dict[str, bool]:
        """Delete a session and all associated files."""
        results = {"session_file": False, "index_entry": False, "file_history": False}

        # Delete session file
        session_file = Path(session.get("fullPath", ""))
        if session_file.exists():
            try:
                session_file.unlink()
                results["session_file"] = True
            except Exception:
                pass

        # Update sessions index
        if not session.get("isUnindexed", True):
            project_dir = Path(session.get("project_dir", ""))
            try:
                index = self.browser.load_sessions_index(project_dir)
                session_id = session.get("sessionId", "")
                index["entries"] = [
                    e for e in index.get("entries", []) if e.get("sessionId") != session_id
                ]
                self.browser.save_sessions_index(project_dir, index)
                results["index_entry"] = True
            except Exception:
                pass

        # Delete file history directory
        session_id = session.get("sessionId", "")
        file_history_dir = self.browser.file_history_dir / session_id
        if file_history_dir.exists():
            try:
                shutil.rmtree(file_history_dir)
                results["file_history"] = True
            except Exception:
                pass

        return results


class SessionPreview(Static):
    """Preview panel showing selected session details."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session: Optional[Dict] = None

    def update_session(self, session: Optional[Dict]):
        """Update the preview with a new session."""
        self.session = session
        if session is None:
            self.update("No session selected")
            return

        browser = ClaudeHistoryBrowser()
        home_dir = os.path.expanduser("~")

        summary = session.get("summary", "No summary")
        msg_count = session.get("messageCount", 0)
        branch = session.get("gitBranch", "N/A") or "N/A"
        project = session.get("projectPath", "N/A") or "N/A"
        if project.startswith(home_dir):
            project = "~" + project[len(home_dir):]
        created = browser.format_date(session.get("created", ""))
        modified = browser.format_date(session.get("modified", ""))
        first_prompt = session.get("firstPrompt", "")[:300]
        if len(session.get("firstPrompt", "")) > 300:
            first_prompt += "..."
        indexed = "Yes" if not session.get("isUnindexed", False) else "No"

        text = Text()
        text.append("Summary: ", style="bold cyan")
        text.append(f"{summary}\n\n")
        text.append("Messages: ", style="bold cyan")
        text.append(f"{msg_count}\n")
        text.append("Branch: ", style="bold cyan")
        text.append(f"{branch}\n")
        text.append("Project: ", style="bold cyan")
        text.append(f"{project}\n")
        text.append("Created: ", style="bold cyan")
        text.append(f"{created}\n")
        text.append("Modified: ", style="bold cyan")
        text.append(f"{modified}\n")
        text.append("Indexed: ", style="bold cyan")
        text.append(f"{indexed}\n\n")
        text.append("First prompt:\n", style="bold cyan")
        text.append(first_prompt, style="dim")

        self.update(text)


class DeleteConfirmScreen(ModalScreen):
    """Modal screen for confirming session deletion."""

    BINDINGS = [
        Binding("y", "confirm", "Yes, delete"),
        Binding("n", "cancel", "No, cancel"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, session: Dict, files_to_delete: Dict[str, List[str]]):
        super().__init__()
        self.session = session
        self.files_to_delete = files_to_delete

    def compose(self) -> ComposeResult:
        summary = self.session.get("summary", "No summary")[:60]
        msg_count = self.session.get("messageCount", 0)

        files_list = []
        if self.files_to_delete["session_file"]:
            files_list.append(f"  - Session file: {self.files_to_delete['session_file'][0]}")
        if self.files_to_delete["index_entry"]:
            files_list.append(f"  - Index entry in: {self.files_to_delete['index_entry'][0]}")
        if self.files_to_delete["file_history"]:
            files_list.append(f"  - File history: {self.files_to_delete['file_history'][0]}")

        content = f"""[bold red]Delete Session?[/bold red]

[bold]Summary:[/bold] {summary}
[bold]Messages:[/bold] {msg_count}

[bold]Files to be deleted:[/bold]
{chr(10).join(files_list) if files_list else '  (none)'}

Press [bold]y[/bold] to confirm deletion or [bold]n[/bold]/[bold]Escape[/bold] to cancel.
"""
        yield Container(
            Static(content, id="delete-content"),
            id="delete-dialog",
        )

    def action_confirm(self):
        self.dismiss(True)

    def action_cancel(self):
        self.dismiss(False)


class SessionViewerScreen(Screen):
    """Full screen view of a session's conversation."""

    # Viewer-specific bindings + shadow app bindings to hide them from footer
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("q", "go_back", "Back"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
        Binding("ctrl+a", "scroll_top", "Home"),
        Binding("ctrl+e", "scroll_bottom", "End"),
        Binding("page_up", "page_up", "PgUp", show=False),
        Binding("page_down", "page_down", "PgDn", show=False),
        # Shadow app bindings to hide them from footer
        Binding("d", "noop", "Delete", show=False),
        Binding("/", "noop", "Search", show=False),
        Binding("p", "noop", "Project", show=False),
        Binding("r", "noop", "Refresh", show=False),
        Binding("enter", "noop", "View", show=False),
    ]


    # Custom theme for markdown rendering (bright blue inline code)
    CUSTOM_THEME = Theme({
        "markdown.code": "bright_blue",
    })

    def __init__(self, session: Dict):
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="conversation", wrap=True, highlight=True, markup=True)
        yield Footer()

    def render_markdown_with_border(self, content: str, style: str, width: int = 100) -> List[Text]:
        """Render markdown content with colored left border."""
        lines = []
        try:
            # Create a temporary console to capture markdown rendering
            string_io = StringIO()
            temp_console = Console(
                file=string_io,
                force_terminal=True,
                width=width - 3,  # Account for border
                theme=self.CUSTOM_THEME
            )
            temp_console.print(Markdown(content))
            rendered = string_io.getvalue()

            # Add border to each line
            for line in rendered.rstrip('\n').split('\n'):
                text = Text()
                text.append("▌ ", style=style)
                text.append_text(Text.from_ansi(line))
                lines.append(text)
        except Exception:
            # Fallback to plain text with wrapping
            for line in content.split('\n'):
                wrapped = textwrap.wrap(line, width=width - 3) if line else ['']
                for wrapped_line in wrapped:
                    text = Text()
                    text.append("▌ ", style=style)
                    text.append(wrapped_line)
                    lines.append(text)
        return lines

    def write_message(self, log: RichLog, role: str, timestamp: str, content: str, browser: ClaudeHistoryBrowser):
        """Write a single message to the log with border formatting."""
        if role == "user":
            style = "bold green"
            emoji = "👤"
        else:
            style = "bold blue"
            emoji = "🤖"

        log.write("")

        # Write header with border
        header = Text()
        header.append("▌ ", style=style)
        header.append(f"{emoji} {role.upper()} - {timestamp}", style=style)
        log.write(header)

        # Empty border line
        empty_border = Text()
        empty_border.append("▌", style=style)
        log.write(empty_border)

        # Truncate very long messages
        truncated = False
        if len(content) > 4000:
            content = content[:4000]
            truncated = True

        # Render markdown content with border
        for line in self.render_markdown_with_border(content, style):
            log.write(line)

        if truncated:
            trunc_text = Text()
            trunc_text.append("▌ ", style=style)
            trunc_text.append("... (message truncated)", style="dim")
            log.write(trunc_text)

    def write_transitional_group(self, log: RichLog, group: List[Dict]):
        """Write a group of transitional messages in collapsed form."""
        style = "bold blue"

        log.write("")

        # Header
        header = Text()
        header.append("▌ ", style=style)
        header.append("🤖 ASSISTANT - working...", style=style)
        log.write(header)

        # Empty border line
        empty_border = Text()
        empty_border.append("▌", style=style)
        log.write(empty_border)

        # Count line
        count_line = Text()
        count_line.append("▌ ", style=style)
        count_line.append(f"{len(group)} transitional messages:", style="dim")
        log.write(count_line)

        # Show preview of each message
        for m in group:
            preview = m['content'][:150]
            if len(m['content']) > 150:
                preview += "..."
            preview_line = Text()
            preview_line.append("▌ ", style=style)
            preview_line.append(f"• {preview}", style="dim")
            log.write(preview_line)

    def on_mount(self):
        browser = ClaudeHistoryBrowser()
        log = self.query_one("#conversation", RichLog)

        # Session header
        summary = self.session.get("summary", "No summary")
        msg_count = self.session.get("messageCount", 0)
        branch = self.session.get("gitBranch", "N/A")
        created = browser.format_date(self.session.get("created", ""))

        header_text = Text()
        header_text.append(f"Session: {summary}\n", style="bold")
        header_text.append(f"Messages: {msg_count} | Branch: {branch} | Created: {created}\n")
        header_text.append("─" * 80)
        log.write(header_text)

        # Load and pre-process messages
        session_file = Path(self.session.get("fullPath", ""))
        messages = browser.load_session_messages(session_file)

        # Pre-process: extract content, classify as transitional or not
        processed_msgs = []
        skipped = 0
        for msg in messages:
            role = msg.get("message", {}).get("role", "unknown")
            timestamp = browser.format_date(msg.get("timestamp", ""))
            content = browser._extract_message_text(msg)

            if not content.strip() or browser._is_system_noise(content):
                skipped += 1
                continue

            is_transitional = (
                role == "assistant" and browser._is_transitional_message(content)
            )

            processed_msgs.append({
                'role': role,
                'timestamp': timestamp,
                'content': content,
                'is_transitional': is_transitional,
            })

        # Display messages, grouping consecutive transitional ones
        transitional_group = []
        grouped_count = 0

        for pm in processed_msgs:
            if pm['is_transitional']:
                transitional_group.append(pm)
            else:
                # Flush any pending transitional group
                if len(transitional_group) > 1:
                    self.write_transitional_group(log, transitional_group)
                    grouped_count += len(transitional_group)
                elif len(transitional_group) == 1:
                    m = transitional_group[0]
                    self.write_message(log, m['role'], m['timestamp'], m['content'], browser)
                transitional_group = []

                # Write the current non-transitional message
                self.write_message(log, pm['role'], pm['timestamp'], pm['content'], browser)

        # Flush remaining transitional group
        if len(transitional_group) > 1:
            self.write_transitional_group(log, transitional_group)
            grouped_count += len(transitional_group)
        elif len(transitional_group) == 1:
            m = transitional_group[0]
            self.write_message(log, m['role'], m['timestamp'], m['content'], browser)

        # Summary
        if skipped > 0 or grouped_count > 0:
            summary_parts = []
            if skipped > 0:
                summary_parts.append(f"{skipped} empty/noise")
            if grouped_count > 0:
                summary_parts.append(f"{grouped_count} transitional grouped")
            log.write("")
            summary_text = Text()
            summary_text.append(f"({', '.join(summary_parts)})", style="dim")
            log.write(summary_text)

    def action_go_back(self):
        self.app.pop_screen()

    def action_noop(self):
        """Do nothing - used to shadow app bindings."""
        pass

    def action_scroll_down(self):
        log = self.query_one("#conversation", RichLog)
        log.scroll_down()

    def action_scroll_up(self):
        log = self.query_one("#conversation", RichLog)
        log.scroll_up()

    def action_scroll_top(self):
        log = self.query_one("#conversation", RichLog)
        log.scroll_home(duration=0.15)

    def action_scroll_bottom(self):
        log = self.query_one("#conversation", RichLog)
        log.scroll_end(duration=0.15)

    def action_page_up(self):
        log = self.query_one("#conversation", RichLog)
        log.scroll_page_up(duration=0.1)

    def action_page_down(self):
        log = self.query_one("#conversation", RichLog)
        log.scroll_page_down(duration=0.1)


class SearchInput(Input):
    """Search input with custom handling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.placeholder = "Type to filter sessions..."


class ClaudeHistoryTUI(App):
    """Main TUI application for browsing Claude Code history."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
    }

    #content-area {
        height: 1fr;
    }

    #session-list-container {
        width: 75%;
        height: 100%;
        border: solid $primary;
    }

    #preview-container {
        width: 25%;
        height: 100%;
        border: solid $secondary;
        padding: 1;
    }

    #session-list {
        height: 100%;
    }

    #search-container {
        height: 3;
        padding: 0 1;
        display: none;
    }

    #search-container.visible {
        display: block;
    }

    #search-input {
        width: 100%;
    }

    #project-filter-container {
        height: 3;
        padding: 0 1;
        display: none;
    }

    #project-filter-container.visible {
        display: block;
    }

    #project-filter-input {
        width: 100%;
    }

    SessionPreview {
        height: 100%;
    }

    #delete-dialog {
        align: center middle;
        width: 140;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }

    #delete-content {
        width: 100%;
    }

    .notification {
        dock: bottom;
        height: 3;
        width: 100%;
        background: $success;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "view_session", "View"),
        Binding("d", "delete_session", "Delete"),
        Binding("/", "search", "Search"),
        Binding("p", "project_filter", "Project"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "escape", "Cancel", show=False),
    ]

    def __init__(
        self,
        branch_filter: Optional[str] = None,
        project_filter: Optional[str] = None,
        since_filter: Optional[str] = None,
    ):
        super().__init__()
        self.browser = ClaudeHistoryBrowser()
        self.deletion_service = SessionDeletionService(self.browser)
        self.sessions: List[Dict] = []
        self.filtered_sessions: List[Dict] = []
        self.branch_filter = branch_filter
        self.project_filter = project_filter
        self.since_filter = since_filter
        self.search_mode = False
        self.search_query = ""
        self.project_filter_mode = False
        self.project_filter_regex = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Container(id="search-container"):
                yield SearchInput(id="search-input")
            with Container(id="project-filter-container"):
                yield Input(id="project-filter-input", placeholder="Project filter (regex)...")
            with Horizontal(id="content-area"):
                with Container(id="session-list-container"):
                    yield DataTable(id="session-list", cursor_type="row")
                with Container(id="preview-container"):
                    yield SessionPreview(id="preview")
        yield Footer()

    def on_mount(self):
        self.title = "Claude Code History Browser"
        self.load_sessions()
        # Focus the table so arrow keys work immediately
        table = self.query_one("#session-list", DataTable)
        table.focus()

    def load_sessions(self):
        """Load all sessions and apply filters."""
        self.sessions = self.browser.get_all_sessions()
        self.apply_filters()

    def populate_table(self):
        """Populate the data table with sessions."""
        table = self.query_one("#session-list", DataTable)
        table.clear(columns=True)

        table.add_column("#", width=4)
        table.add_column("Date", width=16)
        table.add_column("Summary", width=50)
        table.add_column("Msgs", width=5)
        table.add_column("Branch", width=15)
        table.add_column("Project", width=33)

        home_dir = os.path.expanduser("~")

        for idx, session in enumerate(self.filtered_sessions, 1):
            date = self.browser.format_date(
                session.get("modified", session.get("created", ""))
            )
            summary = session.get("summary", "No summary")
            if len(summary) > 47:
                summary = summary[:44] + "..."
            msg_count = str(session.get("messageCount", 0))
            branch = session.get("gitBranch", "") or ""
            if len(branch) > 12:
                branch = branch[:9] + "..."
            project = session.get("projectPath", "") or ""
            if project.startswith(home_dir):
                project = "~" + project[len(home_dir):]
            if len(project) > 30:
                project = "..." + project[-(27):]

            table.add_row(str(idx), date, summary, msg_count, branch, project)

        # Update preview with first session
        if self.filtered_sessions:
            preview = self.query_one("#preview", SessionPreview)
            preview.update_session(self.filtered_sessions[0])

        # Update title with count
        self.sub_title = f"{len(self.filtered_sessions)} sessions"

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        """Update preview when row selection changes."""
        if event.cursor_row is not None and event.cursor_row < len(self.filtered_sessions):
            session = self.filtered_sessions[event.cursor_row]
            preview = self.query_one("#preview", SessionPreview)
            preview.update_session(session)

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """View session when Enter is pressed on a row."""
        if event.cursor_row is not None and event.cursor_row < len(self.filtered_sessions):
            session = self.filtered_sessions[event.cursor_row]
            self.push_screen(SessionViewerScreen(session))

    def get_selected_session(self) -> Optional[Dict]:
        """Get the currently selected session."""
        table = self.query_one("#session-list", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.filtered_sessions):
            return self.filtered_sessions[table.cursor_row]
        return None

    def action_cursor_down(self):
        """Move cursor down (vim j key)."""
        table = self.query_one("#session-list", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self):
        """Move cursor up (vim k key)."""
        table = self.query_one("#session-list", DataTable)
        table.action_cursor_up()

    def action_view_session(self):
        """View the selected session."""
        session = self.get_selected_session()
        if session:
            self.push_screen(SessionViewerScreen(session))

    def action_delete_session(self):
        """Delete the selected session."""
        session = self.get_selected_session()
        if session:
            files = self.deletion_service.get_files_to_delete(session)
            self.push_screen(
                DeleteConfirmScreen(session, files), self.handle_delete_confirm
            )

    def handle_delete_confirm(self, confirmed: bool):
        """Handle the delete confirmation result."""
        if confirmed:
            session = self.get_selected_session()
            if session:
                results = self.deletion_service.delete_session(session)
                self.load_sessions()  # Refresh the list
                self.notify(
                    f"Session deleted successfully",
                    severity="information",
                    timeout=3,
                )

    def action_search(self):
        """Toggle search mode."""
        search_container = self.query_one("#search-container")
        search_input = self.query_one("#search-input", SearchInput)

        if self.search_mode:
            # Hide search
            search_container.remove_class("visible")
            self.search_mode = False
            search_input.value = ""
            self.search_query = ""
            self.apply_filters()  # Re-apply other filters
        else:
            # Show search
            search_container.add_class("visible")
            self.search_mode = True
            search_input.focus()

    def action_project_filter(self):
        """Toggle project filter mode."""
        project_container = self.query_one("#project-filter-container")
        project_input = self.query_one("#project-filter-input", Input)

        if self.project_filter_mode:
            # Hide project filter
            project_container.remove_class("visible")
            self.project_filter_mode = False
            project_input.value = ""
            self.project_filter_regex = ""
            self.apply_filters()  # Re-apply other filters
        else:
            # Show project filter
            project_container.add_class("visible")
            self.project_filter_mode = True
            project_input.focus()

    def on_input_changed(self, event: Input.Changed):
        """Filter sessions as user types in search or project filter."""
        if event.input.id == "search-input":
            self.search_query = event.value.lower()
            self.apply_filters()
        elif event.input.id == "project-filter-input":
            self.project_filter_regex = event.value
            self.apply_filters()

    def on_input_submitted(self, event: Input.Submitted):
        """Handle input submission."""
        if event.input.id in ("search-input", "project-filter-input"):
            # Focus back on table
            table = self.query_one("#session-list", DataTable)
            table.focus()

    def apply_filters(self):
        """Apply all active filters to sessions."""
        # Start with all sessions
        filtered = self.sessions

        # Apply CLI filters (--branch, --project, --since)
        if self.branch_filter:
            filtered = [
                s for s in filtered if self.branch_filter in s.get("gitBranch", "")
            ]

        if self.project_filter:
            filtered = [
                s
                for s in filtered
                if self.project_filter.lower() in s.get("projectPath", "").lower()
            ]

        if self.since_filter:
            try:
                since_date = datetime.fromisoformat(self.since_filter)
                filtered = [
                    s
                    for s in filtered
                    if datetime.fromisoformat(
                        s.get("modified", "").replace("Z", "+00:00")
                    )
                    >= since_date
                ]
            except ValueError:
                pass

        # Apply interactive search filter
        if self.search_query:
            query = self.search_query
            filtered = [
                s
                for s in filtered
                if query in s.get("summary", "").lower()
                or query in s.get("firstPrompt", "").lower()
                or query in s.get("gitBranch", "").lower()
                or query in s.get("projectPath", "").lower()
            ]

        # Apply project regex filter
        if self.project_filter_regex:
            try:
                pattern = re.compile(self.project_filter_regex, re.IGNORECASE)
                filtered = [
                    s for s in filtered if pattern.search(s.get("projectPath", ""))
                ]
            except re.error:
                # Invalid regex, ignore filter
                pass

        self.filtered_sessions = sorted(
            filtered, key=lambda x: x.get("modified", ""), reverse=True
        )

        self.populate_table()

    def action_refresh(self):
        """Refresh the session list."""
        self.sessions = self.browser.get_all_sessions()
        self.apply_filters()
        self.notify("Sessions refreshed", severity="information", timeout=2)

    def action_escape(self):
        """Handle escape key."""
        if self.search_mode:
            self.action_search()  # Toggle off search
        elif self.project_filter_mode:
            self.action_project_filter()  # Toggle off project filter


def main():
    parser = argparse.ArgumentParser(
        description="Interactive TUI for browsing Claude Code history"
    )
    parser.add_argument("--branch", help="Filter by git branch")
    parser.add_argument("--project", help="Filter by project path (substring match)")
    parser.add_argument("--since", help="Filter sessions since date (YYYY-MM-DD)")

    args = parser.parse_args()

    app = ClaudeHistoryTUI(
        branch_filter=args.branch,
        project_filter=args.project,
        since_filter=args.since,
    )
    app.run()


if __name__ == "__main__":
    main()
