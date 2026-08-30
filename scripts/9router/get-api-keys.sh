#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 9Router API Key Manager
# Login and retrieve/create API keys for all 9Router instances
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── Load .env ────────────────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
  set -a; source "$ENV_FILE"; set +a
fi

PASSWORD="${INITIAL_PASSWORD:-123456}"

# ── Instance definitions ─────────────────────────────────────────────────────
declare -A INSTANCES=(
  ["master"]="127.0.0.1:${ROUTER_PORT_MASTER:-20128}"
  ["slave-001"]="127.0.0.1:${ROUTER_PORT_SLAVE_001:-20129}"
  ["slave-002"]="127.0.0.1:${ROUTER_PORT_SLAVE_002:-20130}"
  ["slave-003"]="127.0.0.1:${ROUTER_PORT_SLAVE_003:-20131}"
)

# Ordered keys for consistent output
INSTANCE_ORDER=("master" "slave-001" "slave-002" "slave-003")

# ── Functions ────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -l, --list          List existing API keys (default)
  -c, --create NAME   Create a new API key with given name
  -d, --delete ID     Delete an API key by ID
  -t, --test          Test all API keys with /v1/models
  -o, --output FILE   Save results to JSON file
  -h, --help          Show this help

Examples:
  $(basename "$0")                  # List all keys
  $(basename "$0") -c "my-key"      # Create key named "my-key"
  $(basename "$0") -t               # Test all keys
  $(basename "$0") -o keys.json     # Save to file
EOF
  exit 0
}

msg()  { echo -e "${CYAN}[*]${NC} $*"; }
ok()   { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[-]${NC} $*" >&2; }

# Login and return cookie file path
login() {
  local host="$1"
  local cookie_file
  cookie_file=$(mktemp /tmp/9router_cookie.XXXXXX)

  local resp
  resp=$(curl -sf -c "$cookie_file" -X POST "http://${host}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"password\":\"${PASSWORD}\"}" 2>/dev/null) || {
    rm -f "$cookie_file"
    echo ""
    return 1
  }

  if echo "$resp" | grep -q '"success":true'; then
    echo "$cookie_file"
  else
    rm -f "$cookie_file"
    echo ""
    return 1
  fi
}

# Get keys from instance
get_keys() {
  local host="$1"
  local cookie="$2"
  curl -sf -b "$cookie" "http://${host}/api/keys" 2>/dev/null
}

# Create a key on instance
create_key() {
  local host="$1"
  local cookie="$2"
  local name="$3"
  curl -sf -b "$cookie" -X POST "http://${host}/api/keys" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${name}\"}" 2>/dev/null
}

# Delete a key on instance
delete_key() {
  local host="$1"
  local cookie="$2"
  local key_id="$3"
  curl -sf -b "$cookie" -X DELETE "http://${host}/api/keys/${key_id}" 2>/dev/null
}

# Test an API key
test_key() {
  local host="$1"
  local key="$2"
  local resp
  resp=$(curl -sf "http://${host}/v1/models" \
    -H "Authorization: Bearer ${key}" 2>/dev/null) || {
    echo "FAIL"
    return 1
  }
  if echo "$resp" | grep -q '"object":"list"'; then
    local count
    count=$(echo "$resp" | grep -o '"id":' | wc -l)
    echo "OK (${count} models)"
  else
    echo "ERROR"
  fi
}

# ── Parse args ───────────────────────────────────────────────────────────────
ACTION="list"
KEY_NAME=""
KEY_ID=""
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -l|--list)   ACTION="list";   shift ;;
    -c|--create) ACTION="create"; KEY_NAME="$2"; shift 2 ;;
    -d|--delete) ACTION="delete"; KEY_ID="$2"; shift 2 ;;
    -t|--test)   ACTION="test";   shift ;;
    -o|--output) OUTPUT_FILE="$2"; shift 2 ;;
    -h|--help)   usage ;;
    *) err "Unknown option: $1"; usage ;;
  esac
done

if [[ "$ACTION" == "create" && -z "$KEY_NAME" ]]; then
  err "Key name required with -c"; exit 1
fi

if [[ "$ACTION" == "delete" && -z "$KEY_ID" ]]; then
  err "Key ID required with -d"; exit 1
fi

# ── Main ─────────────────────────────────────────────────────────────────────
TMPDIR_WORK=$(mktemp -d /tmp/9router_work.XXXXXX)
trap 'rm -rf "$TMPDIR_WORK"' EXIT

echo ""
echo -e "${BOLD}9Router API Key Manager${NC}"
echo "────────────────────────────────────────────"

JSON_OUTPUT="["

for inst in "${INSTANCE_ORDER[@]}"; do
  host="${INSTANCES[$inst]}"
  echo ""
  msg "${BOLD}${inst}${NC} → ${host}"

  # Login
  cookie=$(login "$host") || {
    warn "Failed to login to ${inst} (${host})"
    if [[ "$ACTION" != "list" ]]; then
      JSON_OUTPUT+="{\"instance\":\"${inst}\",\"host\":\"${host}\",\"error\":\"login_failed\"},"
    fi
    continue
  }
  ok "Logged in"

  case "$ACTION" in
    list)
      resp=$(get_keys "$host" "$cookie") || resp='{"keys":[]}'
      keys=$(echo "$resp" | python3 -c "
import sys, json
data = json.load(sys.stdin)
keys = data.get('keys', [])
if not keys:
    print('  (no keys)')
else:
    for k in keys:
        status = 'active' if k.get('isActive') else 'inactive'
        print(f\"  {k['key']}  name={k.get('name','-')}  id={k['id'][:12]}...  [{status}]\")
" 2>/dev/null || echo "  (parse error)")
      echo "$keys"
      JSON_OUTPUT+="{\"instance\":\"${inst}\",\"host\":\"${host}\",\"keys\":$(get_keys "$host" "$cookie" 2>/dev/null || echo '{"keys":[]}')},"
      ;;

    create)
      resp=$(create_key "$host" "$cookie" "$KEY_NAME") || resp=""
      if [[ -n "$resp" ]] && echo "$resp" | grep -q '"key"'; then
        key_val=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])" 2>/dev/null)
        ok "Created: ${key_val}"
        JSON_OUTPUT+="{\"instance\":\"${inst}\",\"host\":\"${host}\",\"created\":$(echo "$resp")},"
      else
        warn "Failed to create key on ${inst}"
        JSON_OUTPUT+="{\"instance\":\"${inst}\",\"host\":\"${host}\",\"error\":\"create_failed\"},"
      fi
      ;;

    delete)
      resp=$(delete_key "$host" "$cookie" "$KEY_ID") || resp=""
      if [[ -n "$resp" ]]; then
        ok "Deleted key ${KEY_ID}"
      else
        warn "Failed to delete key on ${inst}"
      fi
      ;;

    test)
      keys_resp=$(get_keys "$host" "$cookie") || keys_resp='{"keys":[]}'
      echo "$keys_resp" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for k in data.get('keys', []):
    if k.get('isActive'):
        print(f\"  {k['key']}\")
" 2>/dev/null | while read -r api_key; do
        result=$(test_key "$host" "$api_key")
        echo "  ${api_key} → ${result}"
      done
      ;;
  esac
done

# Clean trailing comma and close JSON
JSON_OUTPUT="${JSON_OUTPUT%,}]"

if [[ -n "$OUTPUT_FILE" ]]; then
  echo "$JSON_OUTPUT" | python3 -m json.tool > "$OUTPUT_FILE" 2>/dev/null || echo "$JSON_OUTPUT" > "$OUTPUT_FILE"
  ok "Results saved to ${OUTPUT_FILE}"
fi

echo ""
echo "────────────────────────────────────────────"
