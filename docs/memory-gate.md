# AI Memory Gate: recall before the model runs

On every prompt, a `UserPromptSubmit` hook decides — with local, editable rules —
whether the prompt needs long-term memory. If it does, the hook queries the
**ai-memory** MCP server and injects `<ai-memory-recall>` into the prompt before
the model runs. If not, it exits silently in about 240 milliseconds.

## How it works

```
UserPromptSubmit (Claude Code)
 └─ .agents/hooks/memory_gate.py            budget: MEMORY_GATE_DEADLINE (6s)
     ├─ MEMORY_GATE_MODE=off         → exit
     ├─ MEMORY_GATE_MODE=always      → query ai-memory directly
     └─ MEMORY_GATE_MODE=rules (default)
          ├─ recall_decision.needs_memory(prompt) == false → silent (~0ms)
          └─ true → search() via ai-memory MCP (HTTP + Bearer from MCP config)
                     ├─ hits    → inject <ai-memory-recall> (≤ 3000 chars)
                     └─ empty   → silent
```

| File | Role |
|---|---|
| `.agents/hooks/memory_gate.py` | The hook: budget, MCP query, injection. Stdlib only. |
| `.agents/hooks/recall_decision.py` | The decision: normalize, score, threshold. No network. |
| `.agents/hooks/recall_rules.json` | The lexicon: PT/EN signal stems, weights, threshold. Edit without code. |
| `~/.memory-gate/` | Cached search-tool discovery. |

## Configuration

| Env | Default | Meaning |
|---|---|---|
| `MEMORY_GATE_MODE` | `rules` | `rules` \| `always` \| `off` |
| `MEMORY_GATE_DEADLINE` | `6.0` | Total hook budget (seconds); settings `timeout` = deadline + 2 |
| `MEMORY_GATE_RULES` | sibling `recall_rules.json` | Path to the rules file |
| `MEMORY_GATE_MATCH` | `ai-memory,ai_memory` | Substrings identifying the ai-memory server in Claude MCP config |
| `MEMORY_GATE_HOME` | `~/.memory-gate` | State/cache directory |
| `AI_MEMORY_URL` / `AI_MEMORY_TOKEN` / `AI_MEMORY_TIMEOUT` / `AI_MEMORY_TOOL` / `AI_MEMORY_MAX_CHARS` | — / — / `2.0` / auto / `3000` | ai-memory connection layer; when unset, URL+headers come from `.mcp.json` / `~/.claude.json` with `${VAR}` expansion (the token lives in one place only) |

## The rules

`needs_memory` normalizes the prompt (casefold, accents stripped — `que decisoes`
matches `Que Decisões`), sums the `weight` of every `pattern` that occurs as a
substring, and fires when the score reaches `threshold` (default `2.0`).

- Strong phrases weigh 2.5 (`que decid`, `onde paramos`, `did we`, `remind`);
  weak roots weigh 1.0–1.5 and only compose (`vamos decidir` scores 1.0 → silent;
  `que decidimos` scores 3.5 → fires).
- Add or tune signals by editing `recall_rules.json` — no code changes.
- **Known limitation:** pasting logs/history that contain words like "decided"
  can score a false positive. Raise `threshold` to compensate.

## Error policy

| Failure | Behavior |
|---|---|
| Rules file missing / malformed / empty | fail-open: query runs anyway, one warning on **stderr** |
| ai-memory unreachable / timeout / error | silent, no injection — the prompt is never delayed |

## Latency (measured on this machine)

| Path | Before (external scoring) | After (local rules) |
|---|---|---|
| Prompt that does not need memory | ~4.3 s (2 scoring passes) | **~240 ms wall** (decision itself 0.48 ms; the rest is Python interpreter startup, unchanged from the old hook) |
| Prompt that needs memory | scoring + ~1.7 s query | ~240 ms + query |

## Verification

```bash
cd .agents/hooks && python3 -m unittest test_recall_decision test_memory_gate   # 20 tests
grep -riE --exclude-dir=.git --exclude-dir=__pycache__ "claude[-_.]?decide" .   # only the spec
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Gate silent on prompts you expected to fire | Lexicon misses that phrasing | Add a stem to `recall_rules.json` (weights compose; threshold 2.0) |
| `fail-open` warnings on stderr in every session | Rules file missing/typo in `MEMORY_GATE_RULES` | Fix the path; the file ships next to the hook |
| Injection present but empty content | The ai-memory wiki has no matching pages | Install ai-memory's capture hooks (separate setup); recall injects only real hits |
| Query too slow | Remote server / big wiki | `AI_MEMORY_TIMEOUT` (default 2.0 s) and `AI_MEMORY_MAX_CHARS` |

## Scope

- Runs on **Claude Code** only (`UserPromptSubmit` hook).
- The self-contained template lives in `examples/` — copy that folder into any project.
- Complementary, uninstalled piece: ai-memory's official capture hooks (fills the wiki this gate reads).
