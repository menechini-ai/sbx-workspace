# AI Workspace

Development environment with long-term memory (ai-memory) for AI agents, including **9Router** as a free AI API gateway.

## Components

| Service | Directory | Description |
|---------|-----------|-------------|
| **ai-memory** | `scripts/ai-memory/` | Session memory server with MCP tools (port 49374) |
| **9Router Pool** | `scripts/9router-pool/` | Free AI API gateway: 1 master + N slaves, Round Robin |
| **claude-code** | `scripts/claude-code/` | Claude Code container with ai-memory integration |

## Quick Start

```bash
cp .env-example .env
nano .env                              # Add ANTHROPIC_API_KEY

make up SERVICE=9router-pool           # Start gateway (master + 2 slaves)
make up SERVICE=ai-memory              # Start memory server
make cc                                # Run Claude Code
```

## Commands

### Root Makefile

```bash
# Start services
make up SERVICE=ai-memory              # docker compose up
make up SERVICE=9router-pool           # pool.py create

# Stop services
make down                              # Stop all
make down SERVICE=ai-memory            # Stop specific

# Logs
make logs SERVICE=ai-memory            # Tail logs

# Cleanup
make clean                             # Remove all volumes
make clean SERVICE=ai-memory           # Clean specific

# Build
make build                             # Build claude-code image

# Shortcuts
make cc                                # claude-code run
```

### 9Router Pool

```bash
cd scripts/9router-pool

python3 pool.py create                 # Create pool (1 master + 1 slave)
python3 pool.py list                   # Show configuration
python3 pool.py sync                   # Sync providers/models to master
python3 pool.py test                   # Test connectivity
python3 pool.py scale N                # Scale to N slaves (1-15)
python3 pool.py backup                 # Backup master config

# Make targets
make create                            # Same as pool.py create
make list                              # Same as pool.py list
make sync                              # Same as pool.py sync
make test                              # Same as pool.py test
make clean                             # Stop + remove volumes
```

### ai-memory

```bash
cd scripts/ai-memory
make up                                # Start container
make down                              # Stop container
make logs                              # Tail logs
make clean                             # Stop + remove volume
```

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                    AI Workspace                       │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  claude-code  │  │  ai-memory   │  │ 9Router    │  │
│  │  :5555       │  │  :49374      │  │ Master     │  │
│  │              │  │              │  │ :20128     │  │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
│         │                 │                │          │
│         └────────┬────────┘                │          │
│                  ▼                         ▼          │
│           ┌─────────────┐          ┌──────────────┐   │
│           │ Vault/       │          │ 9Router      │   │
│           │ ai-memory/   │          │ Slaves       │   │
│           │ (SQLite+MD)  │          │ :20129+      │   │
│           └─────────────┘          └──────────────┘   │
│                                      │                │
│                                      ▼                │
│                               Free AI Providers       │
│                               (via Tor/proxy)         │
└──────────────────────────────────────────────────────┘

Network: sbx-net (Docker bridge)
```

### Request Flow

```
Claude Code → 9Router Master (:20128) → Round Robin → Slaves (:20129+) → Free AI Providers
     │
     └──► ai-memory (:49374) ← session persistence (SQLite + Markdown)
```

### Port Allocation

| Port | Service |
|------|---------|
| 20128 | 9Router Master |
| 20129-20142 | 9Router Slaves (max 15) |
| 49374 | ai-memory |
| 5555 | claude-code |

## Environment Variables

Copy `.env-example` to `.env` and configure:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key |
| `ANTHROPIC_BASE_URL` | No | `http://host.docker.internal:20128/v1` | API endpoint (9Router master) |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-8` | Default model |
| `AI_MEMORY_AUTH_TOKEN` | Yes | — | Auth token for ai-memory |
| `AI_MEMORY_SERVER_URL` | No | `http://host.docker.internal:49374` | ai-memory endpoint |
| `UID` / `GID` | No | `1000` | Container user permissions |

## MCP Integration

ai-memory exposes MCP tools to Claude Code:
- `memory_briefing` — Session briefing
- `memory_recent` — Recent memories
- `memory_status` — Server status

Configured in `.claude/settings.local.json`.

## File Structure

```
.
├── Makefile                          # Root orchestrator
├── .env                              # Secrets (gitignored)
├── .env-example                      # Template
├── scripts/
│   ├── ai-memory/
│   │   ├── docker-compose.yaml
│   │   └── Makefile
│   ├── 9router-pool/
│   │   ├── docker-compose.yaml       # Master (:20128) + Slaves (:20129+)
│   │   ├── pool.py                   # Pool management CLI
│   │   ├── config.json               # Pool configuration
│   │   └── Makefile
│   └── claude-code/
│       ├── docker-compose.yaml
│       ├── Dockerfile
│       ├── entrypoint.sh
│       └── Makefile
└── workspace/                        # Your code (mounted in containers)
```

## Notes

- All services use Docker network `sbx-net`
- ai-memory data persists in `Vault/ai-memory/`
- 9Router uses named Docker volumes
- 9Router pool supports 1-15 slaves via `pool.py scale N`
