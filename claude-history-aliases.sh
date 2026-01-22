#!/bin/bash
# Claude Code History Browser Aliases
#
# Usage: source this file to add convenient aliases
#   source claude-history-aliases.sh
#
# Or add to your ~/.bashrc or ~/.zshrc:
#   source /path/to/claude-code-history/claude-history-aliases.sh

# Get the directory where this script is located
# Use 'builtin cd' to avoid issues with aliased cd commands
SCRIPT_DIR="$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HISTORY_BROWSER="$SCRIPT_DIR/claude-history-browser.py"

# Force wide terminal for better table display
export COLUMNS=200

# Main command
alias ch="python3 $CLAUDE_HISTORY_BROWSER"

# Specific commands
alias ch-list="python3 $CLAUDE_HISTORY_BROWSER list"
alias ch-search="python3 $CLAUDE_HISTORY_BROWSER search"
alias ch-grep="python3 $CLAUDE_HISTORY_BROWSER grep"
alias ch-view="python3 $CLAUDE_HISTORY_BROWSER view"
alias ch-stats="python3 $CLAUDE_HISTORY_BROWSER stats"

# Common shortcuts
alias ch-recent="python3 $CLAUDE_HISTORY_BROWSER list --limit 10"
alias ch-today="python3 $CLAUDE_HISTORY_BROWSER list --since $(date +%Y-%m-%d)"

echo "✅ Claude History Browser aliases loaded!"
echo ""
echo "Available commands:"
echo "  ch              - Main command"
echo "  ch-list         - List all sessions"
echo "  ch-search       - Search summaries/prompts"
echo "  ch-grep         - Search message content"
echo "  ch-view         - View a session"
echo "  ch-stats        - Show statistics"
echo "  ch-recent       - Show 10 most recent"
echo "  ch-today        - Show today's sessions"
echo ""
echo "Examples:"
echo "  ch-list --limit 5"
echo "  ch-search 'CompilerConfig'"
echo "  ch-grep 'pytest' --limit 3"
echo "  ch-view 1"
echo ""
