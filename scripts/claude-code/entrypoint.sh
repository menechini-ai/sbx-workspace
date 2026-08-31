#!/bin/bash
set -e

# AI_MEMORY_SERVER_URL e AI_MEMORY_AUTH_TOKEN vêm do docker-compose environment
ai-memory install-mcp   --client claude-code --apply
ai-memory install-hooks --agent  claude-code --apply

exec claude "$@"