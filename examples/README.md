# Starter: AI Memory Gate + ai-memory for any project

A self-contained folder that makes Claude Code recall long-term memory **before** the model
runs: on every prompt, local rules (`recall_rules.json`) decide whether the prompt needs
memory; if so, the hook queries your ai-memory server and injects `<ai-memory-recall>`.

Full explanation (architecture, measured latency, config reference, troubleshooting):
[`docs/memory-gate.md`](docs/memory-gate.md) — a verbatim copy of the source repo's
`docs/memory-gate.md`, kept inside this folder on purpose.

## What's inside

| Path | Purpose |
|---|---|
| `.mcp.json` | ai-memory MCP server for Claude Code **and** for the gate. `${AI_MEMORY_AUTH_TOKEN}` placeholder — never a literal token. |
| `.env` | Your server URL + token placeholder (step 2). |
| `.claude/settings.json` | Enables the `memory_gate.py` UserPromptSubmit hook (timeout 8 s). |
| `.agents/hooks/memory_gate.py` | The hook: decides, queries, injects. Stdlib only. |
| `.agents/hooks/recall_decision.py` | The decision: normalize, score, threshold. |
| `.agents/hooks/recall_rules.json` | PT/EN signal lexicon — edit this to tune what triggers recall. |
| `.agents/hooks/test_*.py` | 20 unit tests (decision + gate against fakes). |
| `docs/memory-gate.md` | The full doc (mirror). |
| `verify.sh` | Smoke-check everything after setup. |
| `.opencode/opencode.json` | Same MCP server for OpenCode (manual recall via tools). |

## Setup

1. **Copy this folder** into your project root.
2. **Token** — generate one on the server (`ai-memory generate-auth-token`) and put it in
   `.env`: `AI_MEMORY_AUTH_TOKEN=<your token>`. Never commit it; `verify.sh` refuses
   placeholders.
3. **MCP** — `.mcp.json` already points at `http://127.0.0.1:49374/mcp` with
   `Authorization: Bearer ${AI_MEMORY_AUTH_TOKEN}`. Claude Code expands the variable;
   the gate reads the same block. Adjust the URL for a remote server.
4. **Verify** — `bash verify.sh`. Expect: 20 tests OK, `ai-memory … Connected`,
   decision latency < 50 ms, and a live gate call.

## Tuning recall

- **What triggers memory** → edit `.agents/hooks/recall_rules.json`. Strong phrases weigh
  2.5, weak roots 1.0–1.5, and weights compose; firing needs `score >= threshold` (2.0).
  Add stems for phrasings you use (`{"pattern": "que optamos", "weight": 2.5}`).
- **Query every prompt instead of rules** → `"MEMORY_GATE_MODE": "always"` in
  `.claude/settings.json` `env`.
- **Disable the gate** → `"MEMORY_GATE_MODE": "off"`.
- **Latency budget** → `MEMORY_GATE_DEADLINE` (default 6 s; settings `timeout` = deadline + 2).
- **Bigger/smaller recall text** → `AI_MEMORY_MAX_CHARS` (default 3000).

## Requirements

- Claude Code, Python 3.8+, stdlib only. No GPU, no extra packages, no daemons.
- A running ai-memory server (local Docker or remote) with a token.

## Troubleshooting

See the table in [`docs/memory-gate.md`](docs/memory-gate.md#troubleshooting). Quick checks:

- Gate silent on prompts you expect to fire → `cd .agents/hooks && python3 -m unittest test_recall_decision`
  to confirm rules load; then add stems to `recall_rules.json`.
- `fail-open` warnings on stderr → `MEMORY_GATE_RULES` points somewhere wrong.
- Empty recall content → your wiki has no matching pages yet (capture hooks not installed).
