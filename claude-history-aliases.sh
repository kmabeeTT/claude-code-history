#!/bin/bash
# Claude Code History Browser Aliases
#
# Usage: source this file to add convenient aliases
#   source claude-history-aliases.sh
#
# Or add to your ~/.bashrc or ~/.zshrc:
#   source /path/to/claude-code-history/claude-history-aliases.sh

# Get the directory where this script is located
# Handle both bash and zsh
if [[ -n "$ZSH_VERSION" ]]; then
    SCRIPT_DIR="${0:A:h}"
elif [[ -n "$BASH_SOURCE" ]]; then
    SCRIPT_DIR="$(builtin cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    # Fallback to known location
    SCRIPT_DIR="$HOME/project/claude-code-history"
fi
CLAUDE_HISTORY_BROWSER="$SCRIPT_DIR/claude-history-browser.py"
CLAUDE_HISTORY_BROWSER_TUI="$SCRIPT_DIR/claude-history-tui.py"

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

# TUI mode
alias ch-tui="python3 $CLAUDE_HISTORY_BROWSER_TUI"

# Common shortcuts
alias ch-recent="python3 $CLAUDE_HISTORY_BROWSER list --limit 10"
alias ch-today="python3 $CLAUDE_HISTORY_BROWSER list --since $(date +%Y-%m-%d)"

# Project-scoped helper function
# Usage: ch-proj liquidity list     # list sessions for liquidity project
#        ch-proj liquidity view 1   # view session #1 from liquidity project
#        ch-proj liquidity grep foo # search in liquidity project sessions
ch-proj() {
    if [[ $# -lt 2 ]]; then
        echo "Usage: ch-proj <project> <command> [args...]"
        echo "Example: ch-proj liquidity list"
        echo "         ch-proj liquidity view 1"
        return 1
    fi
    local project="$1"
    shift
    python3 "$CLAUDE_HISTORY_BROWSER" "$@" --project "$project"
}

echo "✅ Claude History Browser aliases loaded!"
echo ""
echo "Available commands:"
echo "  ch              - Main command"
echo "  ch-tui          - Interactive TUI browser"
echo "  ch-list         - List all sessions"
echo "  ch-search       - Search summaries/prompts"
echo "  ch-grep         - Search message content"
echo "  ch-view         - View a session"
echo "  ch-stats        - Show statistics"
echo "  ch-recent       - Show 10 most recent"
echo "  ch-today        - Show today's sessions"
echo "  ch-proj         - Project-scoped commands"
echo ""
echo "Examples:"
echo "  ch-list --limit 5"
echo "  ch-list --project liquidity"
echo "  ch-view 1 --project liquidity"
echo "  ch-proj liquidity list           # same as above"
echo "  ch-proj liquidity view 1         # view #1 from filtered list"
echo "  ch-search 'CompilerConfig'"
echo "  ch-grep 'pytest' --limit 3"
echo ""
