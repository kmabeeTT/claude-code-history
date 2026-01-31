#!/usr/bin/env python3
"""
Claude Code History Browser
A beautiful text-based tool to browse and search Claude Code chat histories.
"""

import json
import os
import re
import textwrap
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.prompt import Prompt, Confirm
    from rich import box
    from rich.layout import Layout
    from rich.text import Text
    from rich.theme import Theme
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("Warning: 'rich' library not found. Install with: pip install rich")
    print("Falling back to basic output.\n")

console = None  # Initialized after argument parsing

# Custom theme: style inline code as bright blue without dark background
# Defined at module level so it can be reused by temp consoles in border mode
custom_theme = Theme({
    "markdown.code": "bright_blue",
}) if HAS_RICH else None


def init_console(color_mode: str = 'always'):
    """Initialize the rich console with the specified color mode."""
    global console
    if not HAS_RICH:
        console = None
        return

    if color_mode == 'always':
        console = Console(force_terminal=True, theme=custom_theme)
    elif color_mode == 'never':
        console = Console(force_terminal=False, no_color=True, theme=custom_theme)
    else:  # auto
        console = Console(theme=custom_theme)


class ClaudeHistoryBrowser:
    def __init__(self, claude_dir: str = None):
        self.claude_dir = Path(claude_dir or os.path.expanduser("~/.claude"))
        self.projects_dir = self.claude_dir / "projects"
        self.sessions_cache = {}

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

        with open(index_file, 'r') as f:
            return json.load(f)

    def load_session_messages(self, session_file: Path) -> List[Dict]:
        """Load all messages from a session JSONL file."""
        if not session_file.exists():
            return []

        messages = []
        with open(session_file, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    if data.get('type') in ['user', 'assistant']:
                        messages.append(data)
                except json.JSONDecodeError:
                    continue
        return messages

    def extract_session_metadata(self, session_file: Path) -> Optional[Dict]:
        """Extract metadata from a session .jsonl file directly.

        Used for sessions that aren't in the index yet (active or recently closed).
        """
        try:
            messages = self.load_session_messages(session_file)
            if not messages:
                return None

            # Get first user message
            first_user_msg = next((m for m in messages if m.get('message', {}).get('role') == 'user'), None)
            if not first_user_msg:
                return None

            first_prompt = self._extract_message_text(first_user_msg)
            if len(first_prompt) > 150:
                first_prompt = first_prompt[:150] + "…"

            # Get timestamps
            created = first_user_msg.get('timestamp', '')
            modified = messages[-1].get('timestamp', created)

            # Get session ID from filename
            session_id = session_file.stem

            # Get git branch and project path from any message
            git_branch = messages[0].get('gitBranch', 'N/A')
            project_path = messages[0].get('cwd', 'N/A')

            # Generate summary from first prompt
            summary = first_prompt.split('\n')[0][:100]
            if len(summary) < len(first_prompt.split('\n')[0]):
                summary += "..."

            return {
                'sessionId': session_id,
                'fullPath': str(session_file),
                'firstPrompt': first_prompt,
                'summary': summary,
                'messageCount': len(messages),
                'created': created,
                'modified': modified,
                'gitBranch': git_branch,
                'projectPath': project_path,
                'isSidechain': False,
                'isUnindexed': True  # Mark as unindexed
            }
        except Exception:
            return None

    def get_all_sessions(self) -> List[Dict]:
        """Get all sessions from all projects, including unindexed ones."""
        all_sessions = []

        for project_dir in self.find_all_projects():
            # Load indexed sessions
            index = self.load_sessions_index(project_dir)
            indexed_session_ids = set()

            for entry in index.get('entries', []):
                entry['project_dir'] = str(project_dir)
                entry['project_name'] = project_dir.name
                entry['isUnindexed'] = False
                all_sessions.append(entry)
                indexed_session_ids.add(entry['sessionId'])

            # Find unindexed .jsonl files
            for jsonl_file in project_dir.glob('*.jsonl'):
                session_id = jsonl_file.stem
                if session_id not in indexed_session_ids:
                    # This is an unindexed session
                    metadata = self.extract_session_metadata(jsonl_file)
                    if metadata:
                        metadata['project_dir'] = str(project_dir)
                        metadata['project_name'] = project_dir.name
                        all_sessions.append(metadata)

        return all_sessions

    def search_sessions(self, query: str, sessions: List[Dict]) -> List[Dict]:
        """Search sessions by summary, first prompt, or branch."""
        query_lower = query.lower()
        results = []
        for session in sessions:
            searchable = f"{session.get('summary', '')} {session.get('firstPrompt', '')} {session.get('gitBranch', '')}".lower()
            if query_lower in searchable:
                results.append(session)
        return results

    def search_content(self, query: str, case_sensitive: bool = False) -> List[Dict]:
        """Search through all conversation content."""
        results = []
        sessions = self.get_all_sessions()

        for session in sessions:
            session_file = Path(session['fullPath'])
            messages = self.load_session_messages(session_file)

            matches = []
            for msg in messages:
                msg_content = self._extract_message_text(msg)
                if self._search_in_text(query, msg_content, case_sensitive):
                    matches.append({
                        'role': msg.get('message', {}).get('role', 'unknown'),
                        'timestamp': msg.get('timestamp', ''),
                        'preview': self._get_preview(msg_content, query, case_sensitive)
                    })

            if matches:
                results.append({
                    'session': session,
                    'matches': matches,
                    'match_count': len(matches)
                })

        return results

    def _is_system_noise(self, text: str) -> bool:
        """Check if text is system noise that should be filtered out."""
        if not text:
            return True
        text_stripped = text.strip()
        # Filter out command/system messages
        noise_patterns = [
            '<local-command-caveat>',
            '<command-name>',
            '<local-command-stdout>',
            '<command-args>',
            '</local-command-caveat>',
            '</command-name>',
            '</local-command-stdout>',
            '</command-args>',
            '[Request interrupted by user',
            'No response requested.',
        ]
        for pattern in noise_patterns:
            if pattern in text_stripped:
                return True
        # Filter messages that are just XML tags
        if text_stripped.startswith('<') and text_stripped.endswith('>'):
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

        # Direct transitional starters - these are always transitional regardless of content
        direct_transitional_starts = [
            "now update ",
            "now add ",
            "now create ",
            "now run ",
            "now check ",
            "now test ",
            "now fix ",
            "now modify ",
            "now read ",
            "now look ",
            "now find ",
            "now search ",
            "now implement ",
            "now write ",
            "now remove ",
            "now delete ",
            "now change ",
            "now replace ",
            "now refactor ",
            "now enhance ",
        ]

        if any(text_lower.startswith(start) for start in direct_transitional_starts):
            return True

        # Phrases that indicate transitional narration (can appear anywhere in short messages)
        transitional_phrases = [
            "let me ",
            "let's ",
            "i'll ",
            "i will ",
            "i need to ",
            "i should ",
            "i'm going to ",
        ]

        # Check if any transitional phrase appears in the message
        has_transitional_phrase = any(phrase in text_lower for phrase in transitional_phrases)

        if not has_transitional_phrase:
            return False

        # Additional patterns that often prefix transitional messages
        prefix_patterns = [
            "now ",
            "first, ",
            "next, ",
            "excellent!",
            "great!",
            "perfect!",
            "good!",
            "ok,",
            "okay,",
            "alright,",
            "i see",
            "the ",  # "The test is working. Let me..."
        ]

        # If message starts with a transitional phrase, it's definitely transitional
        if any(text_lower.startswith(phrase) for phrase in transitional_phrases):
            return True

        # If message starts with a prefix and contains transitional phrase, it's transitional
        if any(text_lower.startswith(prefix) for prefix in prefix_patterns):
            return True

        # Short message with transitional phrase is likely transitional
        if len(text) < 200:
            return True

        return False

    def _extract_message_text(self, msg: Dict, include_thinking: bool = False) -> str:
        """Extract text content from a message.

        Args:
            msg: Message dictionary
            include_thinking: Whether to include thinking blocks (default False)
        """
        message = msg.get('message', {})
        content = message.get('content', '')

        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        texts.append(item.get('text', ''))
                    elif item.get('type') == 'thinking' and include_thinking:
                        texts.append(f"[thinking] {item.get('thinking', '')}")
                elif isinstance(item, str):
                    texts.append(item)
            return ' '.join(texts)
        return ''

    def _search_in_text(self, query: str, text: str, case_sensitive: bool) -> bool:
        """Check if query exists in text."""
        if not case_sensitive:
            return query.lower() in text.lower()
        return query in text

    def _get_preview(self, text: str, query: str, case_sensitive: bool, context: int = 100) -> str:
        """Get a preview of text around the match."""
        if not case_sensitive:
            match_pos = text.lower().find(query.lower())
        else:
            match_pos = text.find(query)

        if match_pos == -1:
            return text[:200]

        start = max(0, match_pos - context)
        end = min(len(text), match_pos + len(query) + context)
        preview = text[start:end]

        if start > 0:
            preview = "..." + preview
        if end < len(text):
            preview = preview + "..."

        return preview

    def format_date(self, date_str: str) -> str:
        """Format ISO date string to readable format."""
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            return date_str


class RichDisplay:
    """Rich library display functions."""

    @staticmethod
    def show_sessions_table(sessions: List[Dict], title: str = "Claude Code Sessions"):
        """Display sessions in a beautiful table."""
        # Sort by modified date (newest first)
        sorted_sessions = sorted(sessions, key=lambda x: x.get('modified', ''), reverse=True)

        # Prepare data and calculate dynamic column widths
        browser = ClaudeHistoryBrowser()
        home_dir = os.path.expanduser("~")
        rows = []
        for idx, session in enumerate(sorted_sessions, 1):
            date = browser.format_date(session.get('modified', session.get('created', '')))
            summary = session.get('summary', 'No summary')
            msg_count = str(session.get('messageCount', 0))
            branch = session.get('gitBranch', '') or ''
            project = session.get('projectPath', '') or ''
            if project.startswith(home_dir):
                project = "~" + project[len(home_dir):]
            indexed = "✓" if not session.get('isUnindexed', False) else ""
            rows.append({
                'idx': str(idx),
                'date': date,
                'indexed': indexed,
                'summary': summary,
                'msg_count': msg_count,
                'branch': branch,
                'project': project,
            })

        # Calculate dynamic widths with min/max bounds
        def calc_width(key, min_w, max_w, header_len):
            if not rows:
                return min_w
            max_content = max(len(r[key]) for r in rows)
            return min(max_w, max(min_w, max_content, header_len))

        idx_width = calc_width('idx', 2, 5, 1)
        date_width = 16  # Fixed for date format
        indexed_width = 3  # "IDX" header
        summary_width = calc_width('summary', 30, 72, 7)  # 20% wider than before (60 -> 72)
        msg_width = calc_width('msg_count', 4, 8, 4)
        branch_width = calc_width('branch', 6, 40, 6)
        project_width = calc_width('project', 10, 50, 7)

        table = Table(title=title, box=box.ROUNDED, show_lines=False)

        table.add_column("#", style="dim", width=idx_width, justify="left")
        table.add_column("Date", style="cyan", width=date_width, justify="left")
        table.add_column("IDX", style="green", width=indexed_width, justify="left")
        table.add_column("Summary", style="bold", width=summary_width, justify="left")
        table.add_column("Msgs", style="green", width=msg_width, justify="left")
        table.add_column("Branch", style="yellow", width=branch_width, justify="left")
        table.add_column("Project", style="magenta", width=project_width, justify="left")

        for row in rows:
            summary = row['summary']
            if len(summary) > summary_width:
                summary = summary[:summary_width-3] + "..."
            branch = row['branch']
            if len(branch) > branch_width:
                branch = branch[:branch_width-3] + "..."
            project = row['project']
            if len(project) > project_width:
                project = "..." + project[-(project_width-3):]  # Show end of path

            table.add_row(
                row['idx'],
                row['date'],
                row['indexed'],
                summary,
                row['msg_count'],
                branch,
                project
            )

        console.print(table)
        console.print(f"\nTotal sessions: {len(sessions)}", style="bold")

        # Show note about unindexed sessions
        unindexed_count = sum(1 for s in sessions if s.get('isUnindexed', False))
        if unindexed_count > 0:
            console.print(f"IDX column: ✓ = indexed, blank = not yet indexed ({unindexed_count} unindexed)", style="dim")

    @staticmethod
    def show_session_detail(session: Dict, messages: List[Dict], max_length: Optional[int] = 2000,
                           include_thinking: bool = False, include_empty: bool = False,
                           format_style: str = 'box'):
        """Display detailed view of a session.

        Args:
            session: Session metadata dictionary
            messages: List of message dictionaries
            max_length: Maximum message length before truncation. None for no limit, 0 for no truncation.
            include_thinking: Whether to include thinking blocks
            include_empty: Whether to include empty messages
            format_style: Display format - 'box' (default), 'simple', or 'border'
        """
        console.print()

        # Session metadata panel
        browser = ClaudeHistoryBrowser()
        metadata = f"""
[bold cyan]Summary:[/bold cyan] {session.get('summary', 'No summary')}
[bold cyan]Created:[/bold cyan] {browser.format_date(session.get('created', ''))}
[bold cyan]Modified:[/bold cyan] {browser.format_date(session.get('modified', ''))}
[bold cyan]Messages:[/bold cyan] {session.get('messageCount', 0)}
[bold cyan]Branch:[/bold cyan] {session.get('gitBranch', 'N/A')}
[bold cyan]Project:[/bold cyan] {session.get('projectPath', 'N/A')}
[bold cyan]Session ID:[/bold cyan] {session.get('sessionId', 'N/A')}
"""
        console.print(Panel(metadata, title="Session Details", border_style="blue"))
        console.print()

        # Pre-process messages: extract content and classify
        processed_msgs = []
        for msg in messages:
            role = msg.get('message', {}).get('role', 'unknown')
            timestamp = browser.format_date(msg.get('timestamp', ''))
            content = browser._extract_message_text(msg, include_thinking=include_thinking)

            # Skip empty messages and system noise unless requested
            if not include_empty:
                if not content.strip() or browser._is_system_noise(content):
                    continue

            is_transitional = (role == 'assistant' and
                              browser._is_transitional_message(content))

            processed_msgs.append({
                'role': role,
                'timestamp': timestamp,
                'content': content,
                'is_transitional': is_transitional,
            })

        # Display messages, grouping consecutive transitional ones
        skipped = len(messages) - len(processed_msgs)
        transitional_group = []
        grouped_count = 0

        # Get terminal width for horizontal rules
        term_width = console.width or 80

        def flush_transitional_group():
            nonlocal grouped_count
            if len(transitional_group) > 1:
                # Show grouped transitional messages as collapsed
                if format_style == 'box':
                    console.print(Panel(
                        f"[dim]{len(transitional_group)} transitional messages:[/dim]\n" +
                        "\n".join(f"[dim]• {m['content'][:150]}{'...' if len(m['content']) > 150 else ''}[/dim]"
                                  for m in transitional_group),
                        title="🤖 ASSISTANT - working...",
                        border_style="dim blue"
                    ))
                elif format_style == 'simple':
                    console.print(f"[bold blue]🤖 ASSISTANT - working...[/bold blue]")
                    console.print("[bold blue]" + "─" * min(term_width, 100) + "[/bold blue]")
                    console.print(f"[dim]{len(transitional_group)} transitional messages:[/dim]")
                    for m in transitional_group:
                        console.print(f"[dim]• {m['content'][:150]}{'...' if len(m['content']) > 150 else ''}[/dim]")
                elif format_style == 'border':
                    console.print(f"[bold blue]▌[/bold blue] [bold blue]🤖 ASSISTANT - working...[/bold blue]")
                    console.print(f"[bold blue]▌[/bold blue]")
                    console.print(f"[bold blue]▌[/bold blue] [dim]{len(transitional_group)} transitional messages:[/dim]")
                    for m in transitional_group:
                        console.print(f"[bold blue]▌[/bold blue] [dim]• {m['content'][:150]}{'...' if len(m['content']) > 150 else ''}[/dim]")
                console.print()
                grouped_count += len(transitional_group)
            elif len(transitional_group) == 1:
                # Single transitional message - show normally
                show_message(transitional_group[0])
            transitional_group.clear()

        def show_message(pm):
            role, timestamp, content = pm['role'], pm['timestamp'], pm['content']

            if role == 'user':
                style = "bold green"
                emoji = "👤"
            else:
                style = "bold blue"
                emoji = "🤖"

            title = f"{emoji} {role.upper()} - {timestamp}"

            # Truncate very long messages if max_length is set
            # Special case: "This session is being continued" messages use 2000 char limit
            truncated = False
            original_len = len(content)
            effective_max = max_length
            if content.lower().startswith("this session is being continued"):
                effective_max = min(max_length, 2000) if max_length and max_length > 0 else 2000
            if effective_max is not None and effective_max > 0 and len(content) > effective_max:
                content = content[:effective_max]
                truncated = True

            if format_style == 'box':
                # Render markdown (tables, code blocks, etc.) for prettier output
                try:
                    rendered_content = Markdown(content)
                except Exception:
                    rendered_content = content
                console.print(Panel(rendered_content, title=title, border_style=style))
                if truncated:
                    console.print(f"[dim]  ... (message truncated, showing {effective_max} of {original_len} chars)[/dim]")

            elif format_style == 'simple':
                console.print(f"[{style}]{title}[/{style}]")
                console.print(f"[{style}]" + "─" * min(term_width, 100) + f"[/{style}]")
                # Render markdown
                try:
                    rendered_content = Markdown(content)
                    console.print(rendered_content)
                except Exception:
                    console.print(content)
                if truncated:
                    console.print(f"[dim]... (message truncated, showing {effective_max} of {original_len} chars)[/dim]")

            elif format_style == 'border':
                console.print(f"[{style}]▌[/{style}] [{style}]{title}[/{style}]")
                console.print(f"[{style}]▌[/{style}]")
                # Render markdown first, then add borders to each line
                border_width = max(40, term_width - 3)  # "▌ " takes ~2-3 chars
                border_char = f"[{style}]▌[/{style}] "
                try:
                    # Create a temporary console to capture markdown rendering
                    # Use custom_theme for consistent inline code styling (bright_blue)
                    string_io = StringIO()
                    temp_console = Console(file=string_io, force_terminal=True, width=border_width, theme=custom_theme)
                    temp_console.print(Markdown(content))
                    rendered = string_io.getvalue()
                    # Add border to each line of rendered output
                    # Print as raw text to preserve ANSI codes from markdown rendering
                    for line in rendered.rstrip('\n').split('\n'):
                        # Print border with markup, then line as raw (no markup processing)
                        console.print(border_char, end="")
                        print(line)  # Use plain print to avoid double-processing ANSI codes
                except Exception:
                    # Fallback to plain text with wrapping
                    for line in content.split('\n'):
                        if len(line) <= border_width:
                            console.print(f"[{style}]▌[/{style}] {line}")
                        else:
                            wrapped = textwrap.wrap(line, width=border_width, break_long_words=False, break_on_hyphens=False)
                            for wrapped_line in wrapped:
                                console.print(f"[{style}]▌[/{style}] {wrapped_line}")
                if truncated:
                    console.print(f"[{style}]▌[/{style}] [dim]... (message truncated, showing {effective_max} of {original_len} chars)[/dim]")

            console.print()

        for pm in processed_msgs:
            if pm['is_transitional']:
                transitional_group.append(pm)
            else:
                flush_transitional_group()
                show_message(pm)

        flush_transitional_group()  # Flush any remaining

        # Summary
        summary_parts = []
        if skipped > 0:
            summary_parts.append(f"{skipped} empty/noise")
        if grouped_count > 0:
            summary_parts.append(f"{grouped_count} transitional grouped")
        if summary_parts:
            console.print(f"[dim]({', '.join(summary_parts)})[/dim]")

    @staticmethod
    def show_search_results(results: List[Dict], query: str):
        """Display search results."""
        console.print()
        console.print(Panel(f"Search results for: [bold cyan]{query}[/bold cyan]",
                          style="bold yellow"))
        console.print()

        if not results:
            console.print("[yellow]No matches found.[/yellow]")
            return

        table = Table(title=f"Found {len(results)} sessions with matches",
                     box=box.ROUNDED, show_lines=True)

        table.add_column("#", style="dim", width=4)
        table.add_column("Session", style="bold cyan", width=60)
        table.add_column("Matches", justify="center", style="green", width=8)
        table.add_column("Preview", style="white", width=60)

        for idx, result in enumerate(results, 1):
            session = result['session']
            summary = session.get('summary', 'No summary')
            if len(summary) > 57:
                summary = summary[:54] + "..."

            match_count = str(result['match_count'])

            # Get first match preview
            first_match = result['matches'][0]
            preview = first_match['preview']
            if len(preview) > 57:
                preview = preview[:54] + "..."

            table.add_row(str(idx), summary, match_count, preview)

        console.print(table)


class BasicDisplay:
    """Fallback display without rich library."""

    @staticmethod
    def show_sessions_table(sessions: List[Dict], title: str = "Claude Code Sessions"):
        """Display sessions in basic table format."""
        sorted_sessions = sorted(sessions, key=lambda x: x.get('modified', ''), reverse=True)
        browser = ClaudeHistoryBrowser()

        # Prepare data and calculate dynamic column widths
        home_dir = os.path.expanduser("~")
        rows = []
        for idx, session in enumerate(sorted_sessions, 1):
            date = browser.format_date(session.get('modified', session.get('created', '')))
            summary = session.get('summary', 'No summary')
            msg_count = str(session.get('messageCount', 0))
            branch = session.get('gitBranch', '') or ''
            project = session.get('projectPath', '') or ''
            if project.startswith(home_dir):
                project = "~" + project[len(home_dir):]
            indexed = "Y" if not session.get('isUnindexed', False) else ""
            rows.append({
                'idx': str(idx),
                'date': date,
                'indexed': indexed,
                'summary': summary,
                'msg_count': msg_count,
                'branch': branch,
                'project': project,
            })

        # Calculate dynamic widths
        def calc_width(key, min_w, max_w, header_len):
            if not rows:
                return min_w
            max_content = max(len(r[key]) for r in rows)
            return min(max_w, max(min_w, max_content, header_len))

        idx_width = calc_width('idx', 2, 5, 1)
        date_width = 16
        indexed_width = 3
        summary_width = calc_width('summary', 30, 72, 7)
        msg_width = calc_width('msg_count', 4, 8, 4)
        branch_width = calc_width('branch', 6, 40, 6)
        project_width = calc_width('project', 10, 50, 7)

        total_width = idx_width + date_width + indexed_width + summary_width + msg_width + branch_width + project_width + 12

        print(f"\n{title}")
        print("=" * total_width)
        print(f"{'#':<{idx_width}} {'Date':<{date_width}} {'IDX':<{indexed_width}} {'Summary':<{summary_width}} {'Msgs':<{msg_width}} {'Branch':<{branch_width}} {'Project':<{project_width}}")
        print("-" * total_width)

        for row in rows:
            summary = row['summary']
            if len(summary) > summary_width:
                summary = summary[:summary_width-3] + "..."
            branch = row['branch']
            if len(branch) > branch_width:
                branch = branch[:branch_width-3] + "..."
            project = row['project']
            if len(project) > project_width:
                project = "..." + project[-(project_width-3):]

            print(f"{row['idx']:<{idx_width}} {row['date']:<{date_width}} {row['indexed']:<{indexed_width}} {summary:<{summary_width}} {row['msg_count']:<{msg_width}} {branch:<{branch_width}} {project:<{project_width}}")

        print(f"\nTotal sessions: {len(sessions)}")

        # Show note about unindexed sessions
        unindexed_count = sum(1 for s in sessions if s.get('isUnindexed', False))
        if unindexed_count > 0:
            print(f"IDX column: Y = indexed, blank = not yet indexed ({unindexed_count} unindexed)")
        print()

    @staticmethod
    def show_session_detail(session: Dict, messages: List[Dict], max_length: Optional[int] = 2000,
                           include_thinking: bool = False, include_empty: bool = False,
                           format_style: str = 'box'):
        """Display detailed view of a session.

        Args:
            session: Session metadata dictionary
            messages: List of message dictionaries
            max_length: Maximum message length before truncation. None for no limit, 0 for no truncation.
            include_thinking: Whether to include thinking blocks
            include_empty: Whether to include empty messages
            format_style: Display format - 'box', 'simple', or 'border' (all render similarly in basic mode)
        """
        browser = ClaudeHistoryBrowser()

        print("\n" + "=" * 100)
        print(f"Summary: {session.get('summary', 'No summary')}")
        print(f"Created: {browser.format_date(session.get('created', ''))}")
        print(f"Modified: {browser.format_date(session.get('modified', ''))}")
        print(f"Messages: {session.get('messageCount', 0)}")
        print(f"Branch: {session.get('gitBranch', 'N/A')}")
        print(f"Project: {session.get('projectPath', 'N/A')}")
        print("=" * 100)
        print()

        # Pre-process messages
        processed_msgs = []
        for msg in messages:
            role = msg.get('message', {}).get('role', 'unknown')
            timestamp = browser.format_date(msg.get('timestamp', ''))
            content = browser._extract_message_text(msg, include_thinking=include_thinking)

            if not include_empty:
                if not content.strip() or browser._is_system_noise(content):
                    continue

            is_transitional = (role == 'assistant' and
                              browser._is_transitional_message(content))
            processed_msgs.append({
                'role': role,
                'timestamp': timestamp,
                'content': content,
                'is_transitional': is_transitional,
            })

        skipped = len(messages) - len(processed_msgs)
        transitional_group = []
        grouped_count = 0

        def flush_transitional_group():
            nonlocal grouped_count
            if len(transitional_group) > 1:
                if format_style == 'border':
                    print(f"\n▌ ASSISTANT - working... ({len(transitional_group)} transitional messages)")
                    print("▌")
                    for m in transitional_group:
                        preview = m['content'][:150] + '...' if len(m['content']) > 150 else m['content']
                        print(f"▌   • {preview}")
                else:
                    print(f"\n{'─' * 100}")
                    print(f"ASSISTANT - working... ({len(transitional_group)} transitional messages)")
                    if format_style == 'box':
                        print(f"{'─' * 100}")
                    for m in transitional_group:
                        preview = m['content'][:150] + '...' if len(m['content']) > 150 else m['content']
                        print(f"  • {preview}")
                print()
                grouped_count += len(transitional_group)
            elif len(transitional_group) == 1:
                show_message(transitional_group[0])
            transitional_group.clear()

        def show_message(pm):
            role = pm['role']
            timestamp = pm['timestamp']
            emoji = "👤" if role == 'user' else "🤖"
            title = f"{emoji} {role.upper()} - {timestamp}"

            if format_style == 'border':
                border = "▌" if role == 'assistant' else "▌"
                print(f"\n{border} {title}")
                print(f"{border}")
            else:
                print(f"\n{title}")
                print(f"{'─' * 100}")

            content = pm['content']
            # Special case: "This session is being continued" messages use 2000 char limit
            effective_max = max_length
            if content.lower().startswith("this session is being continued"):
                effective_max = min(max_length, 2000) if max_length and max_length > 0 else 2000

            truncated = False
            original_len = len(content)
            if effective_max is not None and effective_max > 0 and len(content) > effective_max:
                content = content[:effective_max]
                truncated = True

            if format_style == 'border':
                border = "▌" if role == 'assistant' else "▌"
                for line in content.split('\n'):
                    print(f"{border} {line}")
                if truncated:
                    print(f"{border} ... (message truncated, {original_len} total chars)")
            else:
                print(content)
                if truncated:
                    print(f"\n... (message truncated, {original_len} total chars)")
            print()

        for pm in processed_msgs:
            if pm['is_transitional']:
                transitional_group.append(pm)
            else:
                flush_transitional_group()
                show_message(pm)

        flush_transitional_group()

        # Summary
        summary_parts = []
        if skipped > 0:
            summary_parts.append(f"{skipped} empty/noise")
        if grouped_count > 0:
            summary_parts.append(f"{grouped_count} transitional grouped")
        if summary_parts:
            print(f"({', '.join(summary_parts)})")

    @staticmethod
    def show_search_results(results: List[Dict], query: str):
        """Display search results."""
        print(f"\nSearch results for: {query}")
        print("=" * 135)

        if not results:
            print("No matches found.")
            return

        print(f"Found {len(results)} sessions with matches\n")
        print(f"{'#':<4} {'Session':<60} {'Matches':<8} {'Preview':<55}")
        print("-" * 135)

        for idx, result in enumerate(results, 1):
            session = result['session']
            summary = session.get('summary', 'No summary')[:57]
            match_count = result['match_count']
            preview = result['matches'][0]['preview'][:52]

            print(f"{idx:<4} {summary:<60} {match_count:<8} {preview:<55}")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="Browse and search Claude Code chat histories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                           # List all sessions
  %(prog)s list --limit 10                # Show 10 most recent sessions
  %(prog)s list --project liquidity       # Filter by project path
  %(prog)s search "test infra"            # Search in summaries/prompts
  %(prog)s grep "CompilerConfig"          # Search in all message content
  %(prog)s view 5                         # View session #5 (border format)
  %(prog)s view 1 --project liquidity     # View #1 from filtered list
  %(prog)s view 5 --format box            # View with panel boxes
  %(prog)s view 5 --format simple         # View with header+rule (copy-paste friendly)
  %(prog)s view 5 --max-message-length 0  # View with no truncation
  %(prog)s view SESSION_ID                # View by session ID
  %(prog)s stats                          # Show statistics

Tip: Use the same --project/--branch filters on both list and view to match numbers.
        """
    )

    parser.add_argument('command',
                       choices=['list', 'search', 'grep', 'view', 'stats'],
                       help='Command to execute')
    parser.add_argument('query', nargs='?',
                       help='Search query or session number/ID')
    parser.add_argument('--limit', type=int,
                       help='Limit number of results')
    parser.add_argument('--case-sensitive', action='store_true',
                       help='Case sensitive search (for grep)')
    parser.add_argument('--branch',
                       help='Filter by git branch')
    parser.add_argument('--project',
                       help='Filter by project path (substring match)')
    parser.add_argument('--since',
                       help='Filter sessions since date (YYYY-MM-DD)')
    parser.add_argument('--until',
                       help='Filter sessions until date (YYYY-MM-DD)')
    parser.add_argument('--max-message-length', type=int, default=4000,
                       help='Maximum message length before truncation (default: 4000). Use 0 for no truncation.')
    parser.add_argument('--include-thinking', action='store_true',
                       help='Include thinking blocks in view output (excluded by default)')
    parser.add_argument('--include-empty', action='store_true',
                       help='Include empty messages (tool calls, etc.) in view output')
    parser.add_argument('--format', choices=['box', 'simple', 'border'], default='border',
                       help='Message display format: border (default, left border), box (panels), simple (header+rule)')
    parser.add_argument('--color', choices=['always', 'auto', 'never'], default='always',
                       help='Color output mode (default: always). Use "always" for piping to less -r')

    args = parser.parse_args()

    # Initialize console with color mode
    init_console(args.color)

    browser = ClaudeHistoryBrowser()
    display = RichDisplay if HAS_RICH else BasicDisplay

    if args.command == 'list':
        sessions = browser.get_all_sessions()

        # Apply filters
        if args.branch:
            sessions = [s for s in sessions if args.branch in s.get('gitBranch', '')]

        if args.project:
            sessions = [s for s in sessions if args.project.lower() in s.get('projectPath', '').lower()]

        if args.since:
            since_date = datetime.fromisoformat(args.since)
            sessions = [s for s in sessions
                       if datetime.fromisoformat(s.get('modified', '').replace('Z', '+00:00')) >= since_date]

        if args.until:
            until_date = datetime.fromisoformat(args.until)
            sessions = [s for s in sessions
                       if datetime.fromisoformat(s.get('modified', '').replace('Z', '+00:00')) <= until_date]

        if args.limit:
            sessions = sorted(sessions, key=lambda x: x.get('modified', ''), reverse=True)[:args.limit]

        display.show_sessions_table(sessions)

    elif args.command == 'search':
        if not args.query:
            print("Error: search requires a query")
            return

        sessions = browser.get_all_sessions()
        results = browser.search_sessions(args.query, sessions)

        if args.limit:
            results = results[:args.limit]

        display.show_sessions_table(results, f"Search results for '{args.query}'")

    elif args.command == 'grep':
        if not args.query:
            print("Error: grep requires a query")
            return

        results = browser.search_content(args.query, args.case_sensitive)

        if args.limit:
            results = results[:args.limit]

        display.show_search_results(results, args.query)

    elif args.command == 'view':
        if not args.query:
            print("Error: view requires a session number or ID")
            return

        sessions = browser.get_all_sessions()

        # Apply the same filters as 'list' command so numbers match
        if args.branch:
            sessions = [s for s in sessions if args.branch in s.get('gitBranch', '')]

        if args.project:
            sessions = [s for s in sessions if args.project.lower() in s.get('projectPath', '').lower()]

        if args.since:
            since_date = datetime.fromisoformat(args.since)
            sessions = [s for s in sessions
                       if datetime.fromisoformat(s.get('modified', '').replace('Z', '+00:00')) >= since_date]

        if args.until:
            until_date = datetime.fromisoformat(args.until)
            sessions = [s for s in sessions
                       if datetime.fromisoformat(s.get('modified', '').replace('Z', '+00:00')) <= until_date]

        sorted_sessions = sorted(sessions, key=lambda x: x.get('modified', ''), reverse=True)

        # Try to parse as number first
        try:
            idx = int(args.query) - 1
            if 0 <= idx < len(sorted_sessions):
                session = sorted_sessions[idx]
            else:
                filter_msg = ""
                if args.project or args.branch or args.since or args.until:
                    filter_msg = " (with current filters)"
                print(f"Error: Session number {args.query} out of range (1-{len(sorted_sessions)}){filter_msg}")
                return
        except ValueError:
            # Try as session ID
            session = next((s for s in sessions if s.get('sessionId') == args.query), None)
            if not session:
                print(f"Error: Session ID '{args.query}' not found")
                return

        messages = browser.load_session_messages(Path(session['fullPath']))
        # Convert max_length: 0 means no truncation (None), otherwise use the value
        max_length = None if args.max_message_length == 0 else args.max_message_length
        display.show_session_detail(session, messages, max_length,
                                   include_thinking=args.include_thinking,
                                   include_empty=args.include_empty,
                                   format_style=args.format)

    elif args.command == 'stats':
        sessions = browser.get_all_sessions()

        total = len(sessions)
        total_messages = sum(s.get('messageCount', 0) for s in sessions)
        branches = set(s.get('gitBranch', 'N/A') for s in sessions)
        projects = set(s.get('projectPath', 'N/A') for s in sessions)

        if HAS_RICH:
            stats_text = f"""
[bold cyan]Total Sessions:[/bold cyan] {total}
[bold cyan]Total Messages:[/bold cyan] {total_messages}
[bold cyan]Average Messages per Session:[/bold cyan] {total_messages / total if total > 0 else 0:.1f}
[bold cyan]Unique Branches:[/bold cyan] {len(branches)}
[bold cyan]Unique Projects:[/bold cyan] {len(projects)}
"""
            console.print(Panel(stats_text, title="Claude Code History Statistics", border_style="green"))
        else:
            print("\nClaude Code History Statistics")
            print("=" * 50)
            print(f"Total Sessions: {total}")
            print(f"Total Messages: {total_messages}")
            print(f"Average Messages per Session: {total_messages / total if total > 0 else 0:.1f}")
            print(f"Unique Branches: {len(branches)}")
            print(f"Unique Projects: {len(projects)}")
            print()


if __name__ == '__main__':
    main()
