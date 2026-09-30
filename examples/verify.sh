#!/usr/bin/env bash
# Smoke-check the AI Memory Gate + ai-memory setup after copying this folder into a project.
# Every check prints what it found; exit 1 if any hard check fails.
set -u
cd "$(dirname "$0")"

# token for ${AI_MEMORY_AUTH_TOKEN} expansion (step 2 of README)
if [ -f .env ]; then set -a; . ./.env; set +a; fi
case "${AI_MEMORY_AUTH_TOKEN:-}" in
  *REPLACE_ME*|"")
    echo "!! .env still holds the placeholder — do README step 2 (paste your real token) first."
    exit 1 ;;
esac

fail=0

echo "== 1) decision + gate unit tests (expect: Ran 20 tests, OK) =="
(cd .agents/hooks && python3 -m unittest test_recall_decision test_memory_gate) || fail=1

echo "== 2) Claude Code sees the MCP server (expect: ai-memory ... Connected) =="
claude mcp list 2>&1 | sed -E 's/(Bearer )[A-Za-z0-9._~+-]+/\1[REDACTED]/g' || fail=1

echo "== 3) decision latency (expect: < 50 ms) =="
python3 - <<'EOF' || fail=1
import sys, time
sys.path.insert(0, ".agents/hooks")
import recall_decision as rd
t = time.monotonic()
rd.needs_memory("run the tests")
ms = (time.monotonic() - t) * 1000
print(f"needs_memory: {ms:.1f} ms")
sys.exit(0 if ms < 50 else 1)
EOF

echo "== 4) gate end-to-end (a <ai-memory-recall> JSON block, or silent if the wiki is empty) =="
echo '{"hook_event_name":"UserPromptSubmit","prompt":"que decidimos sobre tokens e auth?","cwd":"'"$PWD"'","session_id":"verify"}' \
  | python3 .agents/hooks/memory_gate.py

echo
if [ "$fail" = 0 ]; then echo "ALL HARD CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit "$fail"
