#!/bin/bash
set -e

# Configure ai-memory MCP server for Claude Code (only once per workspace)
MARKER_FILE="/workspace/.ai-memory-configured"
if command -v ai-memory &> /dev/null && [ ! -f "$MARKER_FILE" ]; then
    echo "Installing ai-memory MCP hooks for Claude Code..."
    ai-memory install-mcp --client claude-code --apply || true
    ai-memory install-hooks --agent claude-code --apply || true
    touch "$MARKER_FILE"
fi

# Start Claude Code
exec claude --dangerously-skip-permissions