# Claude Code History Browser 🔍

Browse, search and export your Claude Code chat histories from the terminal.

The repo ships two tools that share the same data layer:

| Tool | What it is | Best for |
|------|------------|----------|
| **`claude-history-tui.py`** (`ch-tui`) | Full-screen interactive browser (textual) | Finding and reading a conversation, deleting sessions, exporting markdown |
| **`claude-history-browser.py`** (`ch`) | One-shot CLI (rich) | Scripting, piping, grepping across every session |

Both read `~/.claude/` read-only (except the TUI's explicit delete and markdown
export), and both honour `CLAUDE_CONFIG_DIR` if you point Claude Code elsewhere.

## Features

**Interactive TUI (`ch-tui`)**

- 🖥️ **Session list** with vim-like navigation and a live detail preview pane
- 🔍 **Filter as you type** by summary, first prompt, branch or project
- 📁 **Project filter** by regex
- 👁️ **Full conversation viewer** with markdown rendering and collapsed "working..." chatter
- 🔎 **In-document search** — `/`, `?`, `n`, `N` with highlighted hits and match counts
- 🗑️ **Delete sessions** (transcript, index entry and file history) behind a confirmation
- 📝 **Markdown export** with smart caching, plus open-in-editor / open-in-viewer
- 📐 **Columns stretch to the terminal width**

**CLI (`ch`)**

- 📋 **List all conversations** with date, index status, summary, message count, branch and project
- 🔍 **Search** summaries, first prompts and branch names
- 🔎 **Deep grep** through every message body
- 📖 **View a conversation** in three layouts (`border`, `box`, `simple`)
- 📊 **Statistics** across your whole history
- 🎨 **Rich output** with a plain-text fallback when `rich` isn't installed

**Both**

- 🏷️ **Session titles** — a session's own title (one you set yourself, or Claude's
  AI-generated one) is used in place of the first-prompt summary
- ✅ **Index status** shows which sessions have an AI-generated summary yet
- 🗓️ **Filters** by branch, project path and date

## Installation

### Prerequisites

```bash
# rich for the CLI output, textual for the TUI
pip install -r requirements.txt
```

`claude-history-browser.py` works without `rich` (it falls back to plain text).
`textual` is required for `claude-history-tui.py` — without it the TUI fails at
startup with `ModuleNotFoundError: No module named 'textual'`.

### Make executable

```bash
chmod +x claude-history-browser.py claude-history-tui.py
```

### Aliases

```bash
source /path/to/claude-code-history/claude-history-aliases.sh
```

| Alias | Runs |
|-------|------|
| `ch-tui` | The interactive TUI |
| `ch` | The CLI (any subcommand) |
| `ch-list` | `ch list` |
| `ch-search` | `ch search` |
| `ch-grep` | `ch grep` |
| `ch-view` | `ch view` |
| `ch-stats` | `ch stats` |
| `ch-recent` | 10 most recent sessions |
| `ch-today` | Sessions modified today |
| `ch-proj <project> <cmd>` | Any command scoped to a project, e.g. `ch-proj liquidity view 1` |

Sourcing the file also exports `COLUMNS=200` so the CLI tables get room to breathe.

Or add a single alias by hand:

```bash
alias claude-history='/path/to/claude-code-history/claude-history-browser.py'
```

### Terminal width

The CLI uses wide tables. For best results use a terminal at least 150 columns
wide; below that some columns get squeezed. You can force a width:

```bash
COLUMNS=200 ./claude-history-browser.py list
```

The TUI adapts to whatever size the window is and re-flows on resize.

### Custom Claude directory

Both tools read `$CLAUDE_CONFIG_DIR` when it is set, falling back to `~/.claude`:

```bash
CLAUDE_CONFIG_DIR=/data/me/.claude ch-tui
```

## TUI (ch-tui)

```bash
./claude-history-tui.py
# or
ch-tui

# Start with a filter already applied
ch-tui --project liquidity-bot
ch-tui --branch main
ch-tui --since 2026-01-20
```

### Session list

```
 ⭘                    Claude Code History Browser — 25 sessions
┌──────────────────────────────────────────────────────────┐┌────────────────────────┐
│ #    MD   Date              Summary                Msgs  ││ Summary: Add in-doc    │
│ 1         2026-01-30 19:44  Add in-doc search      101   ││ search                 │
│ 2    ✓    2026-01-30 18:54  Auto-switching system  71    ││                        │
│ 3    ✓    2026-01-28 05:31  Regime improvements    27    ││ Messages: 101          │
│                                                          ││ Branch: main           │
└──────────────────────────────────────────────────────────┘└────────────────────────┘
 q Quit  d Delete  m Edit MD  v View MD  / Search  p Project  r Refresh
```

(Branch and Project columns are cut off above; they sit to the right of Msgs.)

- **MD** — `✓` when the cached markdown export is up to date with the transcript
- **Summary** — the session's title if it has one, otherwise the first prompt
- The Summary / Branch / Project columns share the leftover width, so the table
  fills the window instead of leaving dead space on wide terminals
- The pane on the right previews the highlighted session: summary, message
  count, branch, project, created/modified timestamps, index status and the
  first prompt

### Key bindings

| Key | Action |
|-----|--------|
| `j/k` | Navigate up/down |
| `Enter` | Open the session conversation |
| `d` | Delete session (with confirmation) |
| `m` | Edit markdown in your editor |
| `v` | View markdown in your viewer |
| `M` | Force regenerate markdown |
| `/` | Filter sessions as you type |
| `p` | Project filter (regex) |
| `r` | Refresh the session list |
| `Esc` | Close the active filter |
| `q` | Quit |

The `/` filter matches against summary, first prompt, branch and project path.

### In the conversation view

Vim-style search inside the open conversation:

| Key | Action |
|-----|--------|
| `/` | Search forwards - type to jump to hits as you type |
| `?` | Search backwards |
| `Enter` | Accept the search, hand focus back to the document |
| `n` | Jump to the next hit (same direction as the search) |
| `N` | Jump to the previous hit |
| `Esc` | Cancel the search / clear highlights, then leave the view |
| `j/k`, `PgUp/PgDn` | Scroll |
| `g`/`G` or `Ctrl-A`/`Ctrl-E` | Jump to top/bottom |
| `q` | Back to the session list |

Every hit is highlighted in yellow, the current one in cyan, and the bar at the
bottom shows `3/17` style match counts (plus `(wrapped)` when the search rolls
past the end). Searches are regex (an invalid pattern falls back to a literal
match) and case-insensitive unless the term contains an uppercase character,
like vim's `smartcase`.

Messages are rendered as markdown with a coloured left border per role. Empty
and system-noise messages are dropped, and runs of short "working on it"
assistant messages are collapsed into a single block, with a count of what was
hidden at the end of the transcript.

### Deleting a session

`d` opens a confirmation modal listing exactly what will be removed (`y` to
confirm, `n`/`Esc` to back out):

- the session's `.jsonl` transcript in `~/.claude/projects/<project>/`
- its entry in that project's `sessions-index.json`
- its file-history directory `~/.claude/file-history/<sessionId>/`

Deletion is permanent — there is no undo.

### Markdown export

The TUI generates and caches markdown files from your sessions:

- **Location:** `~/.claude/markdown/{project-hash}/{sessionId}.md`
- **Caching:** mtime comparison against the transcript for fast invalidation
- **Background generation:** stale files regenerate on startup
- **MD column:** shows `✓` when the export is current

#### Markdown format

```markdown
# [Summary or first prompt]

**Session ID:** `uuid`
**Project:** `/path/to/project`
**Branch:** `main`
**Created:** 2026-01-30 18:34
**Modified:** 2026-01-30 19:44
**Messages:** 42

---

## User (2026-01-30 18:34)

User message content...

---

## Assistant (2026-01-30 18:35)

Assistant response...

---
```

#### Editor/viewer configuration

**Editor (`m` key):**
1. `CLAUDE_HISTORY_EDITOR` environment variable
2. `EDITOR` environment variable
3. `cursor` (if available)
4. `open` (macOS) / `xdg-open` (Linux)

**Viewer (`v` key):**
1. `CLAUDE_HISTORY_MD_VIEWER` environment variable
2. `open` (macOS - uses system default app)
3. `glow` (Linux, if available)
4. `xdg-open` (Linux fallback)

To use a specific app as your markdown viewer on macOS, set it as the default app for `.md` files in Finder (Get Info → Open with → Change All).

## CLI (claude-history-browser.py)

### List sessions

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

### Search summaries, prompts and branches

```bash
# Search for conversations about CompilerConfig
./claude-history-browser.py search "CompilerConfig"

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

### View a conversation

```bash
# View by session number (from list command)
./claude-history-browser.py view 1

# View by session ID
./claude-history-browser.py view 81b9f767-88c1-4e70-9d90-4cc77c92b4f7

# View with no message truncation (default cap is 4000 chars per message)
./claude-history-browser.py view 1 --max-message-length 0

# Include thinking blocks (hidden by default)
./claude-history-browser.py view 1 --include-thinking

# Include empty messages like tool calls (hidden by default)
./claude-history-browser.py view 1 --include-empty

# Message layout: border (default), box (panels), simple (header+rule)
./claude-history-browser.py view 1 --format simple

# Keep colours when piping
./claude-history-browser.py view 1 --color always | less -r
```

Session numbers come from `list`, so pass the *same* `--project`/`--branch`
filters to `view` for the numbers to line up.

### Statistics

```bash
./claude-history-browser.py stats
```

Reports total sessions, total messages, average messages per session, and the
number of unique branches and projects.

### Example workflow

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

### Output examples

#### List view
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
- **IDX**: ✓ if the session has an AI-generated summary, blank if not yet indexed
- **Project**: project path with `~` for home directory
- Columns resize to fit their content

#### View detail
Shows session metadata (summary, dates, branch, message count) followed by every
message with its role, timestamp and content, formatted per `--format`.

#### Grep results
Shows which sessions contain the term, the number of matches per session, and a
preview of the matching content.

## Data location

Both tools read from `~/.claude/` (or `$CLAUDE_CONFIG_DIR`), where Claude Code
stores its history:

- `~/.claude/projects/<project-hash>/` — one `.jsonl` transcript per session
- `~/.claude/projects/<project-hash>/sessions-index.json` — metadata and AI-generated summaries
- `~/.claude/file-history/<sessionId>/` — file snapshots for a session
- `~/.claude/markdown/<project-hash>/<sessionId>.md` — markdown exports written by the TUI

### Session titles

A session's display name is picked in this order:

1. **Custom title** — a title you set yourself, stored as a `custom-title` entry in the transcript
2. **AI title** — Claude's own generated title, stored as an `ai-title` entry
3. **Indexed summary** — the AI summary in `sessions-index.json`
4. **First prompt** — the first line of your opening message, truncated

### Indexed vs unindexed sessions

Claude Code uses **lazy indexing** — sessions are indexed when you close the
*next* session, not the current one:

- **Indexed (✓)**: has an AI-generated summary in `sessions-index.json`
- **Unindexed (blank)**: the transcript exists but isn't in the index yet
  (active session, or never revisited). These are read straight from the
  `.jsonl`, so they still show up in both tools.

To index old sessions, start and `/exit` a new session in that project directory.

## Tips

1. **Reading a conversation? Use the TUI.** `ch-tui`, `Enter`, then `/` to find the bit you want
2. **Use grep for code/function searches**: if you remember a specific function or file, use `grep` rather than `search`
3. **Use search for topic searches**: if you remember the topic but not exact terms, use `search`
4. **Pipe to less for long outputs**: `./claude-history-browser.py view 1 --color always | less -r`
5. **Combine with shell tools**: `./claude-history-browser.py list | grep qwen`
6. **Filter by project**: `--project` (or `ch-proj`) quickly narrows to one codebase
7. **Clean view output**: tool calls and thinking blocks are hidden by default — add `--include-thinking` / `--include-empty` to see them

## Troubleshooting

### "rich library not found"
Install with `pip install rich`. The CLI still works without it, just with basic
text output.

### "No module named 'textual'"
The TUI (`ch-tui`) requires `textual`, unlike `claude-history-browser.py` which
only needs `rich`. Install with `pip install textual` (or
`pip install -r requirements.txt` for both).

### No sessions found
Make sure Claude Code has been run at least once in your project directory, and
that `CLAUDE_CONFIG_DIR` points at the right place if you have moved it.

### Permission denied
Make the scripts executable: `chmod +x claude-history-browser.py claude-history-tui.py`

## Future Enhancements

### High Value
- **JSON output mode** - `list --json` for scripting/piping to `jq`
- **Show files mentioned** - Extract file paths discussed in a session (useful for "what did I work on?")
- **Better stats** - Activity by day/week, most active projects, average session length

### Medium Value
- **Regex search** - `grep --regex "def \w+\("` for pattern matching
- **Message count filter** - `list --min-messages 50` to find substantial conversations
- **Diff sessions** - Compare two related sessions to see what changed

### Nice to Have
- **Copy session ID to clipboard** - Quick `view 3 --copy-id`
- **Continuation chain** - Show which sessions were continued from others (detect "This session is being continued")
- **Timeline/calendar view** - Visual activity heatmap

## Contributing

Feel free to extend this tool. Both scripts carry their own copy of the
`ClaudeHistoryBrowser` data layer (session discovery, metadata, titles), so a
change to how sessions are read usually needs applying to both.

`claude-history-browser.py`:
- `ClaudeHistoryBrowser` — core data access
- `RichDisplay` / `BasicDisplay` — rich UI and plain-text fallback

`claude-history-tui.py`:
- `ClaudeHistoryTUI` — the app: session list, filters, preview
- `SessionViewerScreen` — conversation view and in-document search
- `InstantScrollRichLog` — the log widget: instant scrolling and hit highlighting
- `MarkdownGenerator` — markdown export, caching, editor/viewer launching
- `SessionDeletionService` — works out and removes a session's files

---

Enjoy browsing your Claude Code history! 🚀
