# Claude Code History Browser 🔍

A beautiful terminal-based tool for browsing and searching your Claude Code chat histories.

## Features

- 📋 **List all conversations** with summary, date, message count, branch, and project path
- 🔍 **Search** by summary, first prompt, or branch name
- 🔎 **Deep grep** through all message content
- 👁️ **View full conversations** with formatted messages (thinking/tool calls filtered by default)
- 📊 **Statistics** about your chat history
- 🎨 **Beautiful terminal UI** using the `rich` library
- 🗓️ **Filter** by date range, branch, or project path
- ✅ **Index status** column shows which sessions have AI-generated summaries
- 📐 **Dynamic column widths** adjust to content for cleaner output

## Installation

### Prerequisites

```bash
# Install the rich library for beautiful output
pip install rich
```

If you don't have `rich` installed, the tool will still work with basic text output.

### Terminal Width

The tool uses wide tables for better readability. For best results, use a terminal width of at least 150 characters. If your terminal is narrower, some columns may be hidden. You can force a wider display by setting the COLUMNS environment variable:

```bash
# Force wide output (recommended)
COLUMNS=200 ./claude-history-browser.py list

# Or set it for all commands
export COLUMNS=200
```

### Make executable

```bash
chmod +x claude-history-browser.py
```

### Optional: Add to PATH

You can add an alias to your `.bashrc` or `.zshrc`:

```bash
alias claude-history='/path/to/claude-code-history/claude-history-browser.py'
```

Or simply source the aliases file:

```bash
source /path/to/claude-code-history/claude-history-aliases.sh
```

## Usage

### List all sessions

```bash
# List all conversations (sorted by date, newest first)
./claude-history-browser.py list

# Show only 10 most recent
./claude-history-browser.py list --limit 10

# Filter by branch
./claude-history-browser.py list --branch feature/my-branch

# Filter by project path (substring match)
./claude-history-browser.py list --project liquidity-bot

# Filter by date range
./claude-history-browser.py list --since 2026-01-20
./claude-history-browser.py list --until 2026-01-21
```

### Search in summaries and prompts

```bash
# Search for conversations about CompilerConfig
./claude-history-browser.py search "CompilerConfig"

# Search for test-related conversations
./claude-history-browser.py search "test"

# Limit results
./claude-history-browser.py search "BFP8" --limit 5
```

### Deep grep through message content

```bash
# Search through all message content
./claude-history-browser.py grep "pytest"

# Case-sensitive search
./claude-history-browser.py grep "CompilerConfig" --case-sensitive

# Limit results
./claude-history-browser.py grep "YAML" --limit 3
```

### View a specific conversation

```bash
# View by session number (from list command)
./claude-history-browser.py view 1

# View by session ID
./claude-history-browser.py view 81b9f767-88c1-4e70-9d90-4cc77c92b4f7

# View with no message truncation
./claude-history-browser.py view 1 --max-message-length 0

# Include thinking blocks (hidden by default)
./claude-history-browser.py view 1 --include-thinking

# Include empty messages like tool calls (hidden by default)
./claude-history-browser.py view 1 --include-empty
```

### Statistics

```bash
# Show statistics about your chat history
./claude-history-browser.py stats
```

## Example Workflow

```bash
# 1. List recent conversations
./claude-history-browser.py list --limit 10

# 2. Search for something specific
./claude-history-browser.py search "CompilerConfig"

# 3. View the details of conversation #3
./claude-history-browser.py view 3

# 4. Deep search through all content
./claude-history-browser.py grep "test_models.py"
```

## Output Examples

### List View
```
                                        Claude Code Sessions
╭────┬──────────────────┬─────┬────────────────────────────────────────────┬──────┬────────┬─────────────────────╮
│ #  │ Date             │ IDX │ Summary                                    │ Msgs │ Branch │ Project             │
├────┼──────────────────┼─────┼────────────────────────────────────────────┼──────┼────────┼─────────────────────┤
│ 1  │ 2026-01-30 19:44 │     │ Current active session...                  │ 101  │ main   │ ~/project/myapp     │
│ 2  │ 2026-01-30 18:54 │ ✓   │ Implementing Robust Auto-Switching System  │ 71   │ main   │ ~/project/bot       │
│ 3  │ 2026-01-28 05:31 │ ✓   │ Auto-switch regime system improvements     │ 27   │ main   │ ~/project/bot       │
╰────┴──────────────────┴─────┴────────────────────────────────────────────┴──────┴────────┴─────────────────────╯

Total sessions: 26
IDX column: ✓ = indexed, blank = not yet indexed (3 unindexed)
```

**Column notes:**
- **IDX**: Shows ✓ if session has an AI-generated summary, blank if not yet indexed
- **Project**: Shows project path with `~` for home directory
- Columns dynamically resize based on content

### View Detail
Shows a beautiful panel with:
- Session metadata (summary, dates, branch, message count)
- All messages with role (user/assistant), timestamp, and content
- Syntax highlighting and formatted output

### Grep Results
Shows:
- Which sessions contain your search term
- Number of matches per session
- Preview of the matching content

## Data Location

The tool reads from `~/.claude/` directory where Claude Code stores all chat histories:
- Sessions are stored in `~/.claude/projects/`
- Each project has a `sessions-index.json` with metadata and AI-generated summaries
- Individual conversations are in `.jsonl` files (JSON Lines format)

### Indexed vs Unindexed Sessions

Claude Code uses **lazy indexing** - sessions are indexed when you close the *next* session, not the current one:
- **Indexed (✓)**: Has AI-generated summary in `sessions-index.json`
- **Unindexed (blank)**: Session exists but not yet in index (active or never revisited)

To index old sessions, simply start and `/exit` a new session in that project directory.

## Tips

1. **Use grep for code/function searches**: If you remember discussing a specific function or file, use `grep` instead of `search`
2. **Use search for topic searches**: If you remember the topic but not exact terms, use `search`
3. **Pipe to less for long outputs**: `./claude-history-browser.py view 1 | less`
4. **Combine with shell tools**: `./claude-history-browser.py list | grep qwen`
5. **Filter by project**: Use `--project` to quickly find sessions from a specific codebase
6. **Clean view output**: By default, tool calls and thinking blocks are hidden - use `--include-thinking` or `--include-empty` to see them

## Troubleshooting

### "rich library not found"
Install with: `pip install rich`

The tool will still work without it, just with basic text output.

### No sessions found
Make sure Claude Code has been run at least once in your project directory.

### Permission denied
Make the script executable: `chmod +x claude-history-browser.py`

## Future Enhancements

Potential additions:
- Interactive mode with arrow key navigation
- Export conversations to Markdown/HTML
- Filter by message count range
- Search with regex patterns
- Tag/favorite system
- Delete old conversations

## Contributing

Feel free to extend this tool! The code is well-structured with separate classes for:
- `ClaudeHistoryBrowser`: Core functionality
- `RichDisplay`: Rich library UI
- `BasicDisplay`: Fallback text UI

---

Enjoy browsing your Claude Code history! 🚀
