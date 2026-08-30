#!/bin/bash
set -e

echo "Iniciando Claude Code via ai-memory (managed mode)..."

# ai-memory run handles:
# - MCP configuration
# - Lifecycle hooks installation
# - Session continuity (handoffs)
# - Native session resume
exec ai-memory run claude "$@"