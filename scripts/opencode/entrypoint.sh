#!/bin/bash
set -e

ai-memory install-mcp   --client opencode --apply
ai-memory install-hooks --agent  opencode --apply   # gera plugin TS em ~/.config/opencode/plugins/

exec opencode "$@"