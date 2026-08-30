#!/bin/bash
set -e

# Ensure cache directory exists and is writable
mkdir -p /home/node/.cache/ai-memory/native-runner

echo "Iniciando OpenCode via ai-memory (managed mode)..."

# ai-memory run handles:
# - MCP configuration
# - Lifecycle hooks installation  
# - Session continuity (handoffs)
# - Native session resume
exec ai-memory run opencode "$@"