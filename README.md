# Claude Code History Browser 🔍

A beautiful terminal-based tool for browsing and searching your Claude Code chat histories.

## Features

- 📋 **List all conversations** with summary, date, message count, and branch info
- 🔍 **Search** by summary, first prompt, or branch name
- 🔎 **Deep grep** through all message content
- 👁️ **View full conversations** with formatted messages
- 📊 **Statistics** about your chat history
- 🎨 **Beautiful terminal UI** using the `rich` library
- 🗓️ **Filter** by date range or branch

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
╭───┬────────────────┬──────────────────────────────────────────────┬──────────┬────────────────────────╮
│ # │ Date           │ Summary                                      │ Messages │ Branch                 │
├───┼────────────────┼──────────────────────────────────────────────┼──────────┼────────────────────────┤
│ 1 │ 2026-01-22 ... │ vLLM version control and v0.13.0 upgrade ... │ 8        │ feature/qwen3_embe...  │
│ 2 │ 2026-01-22 ... │ TTNN RMS Norm L1 Memory Overflow Debugging   │ 4        │ feature/qwen3_embe...  │
│ 3 │ 2026-01-22 ... │ Fix JAX BFP8 training with nested jit ...    │ 15       │ feature/bfp8_model...  │
╰───┴────────────────┴──────────────────────────────────────────────┴──────────┴────────────────────────╯

Total sessions: 15
```

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
- Each project has a `sessions-index.json` with metadata
- Individual conversations are in `.jsonl` files (JSON Lines format)

## Tips

1. **Use grep for code/function searches**: If you remember discussing a specific function or file, use `grep` instead of `search`
2. **Use search for topic searches**: If you remember the topic but not exact terms, use `search`
3. **Pipe to less for long outputs**: `./claude-history-browser.py view 1 | less`
4. **Combine with shell tools**: `./claude-history-browser.py list | grep qwen`

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
