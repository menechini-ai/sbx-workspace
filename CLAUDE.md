# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI Workspace** — A development environment with long-term memory (ai-memory) for AI agents, including **9Router** as a free AI API gateway.

**Core Components:**
- **ai-memory**: Server enabling continuity between sessions and context sharing between Claude Code and OpenCode
- **9Router Pool**: Free AI API gateway with 1 master + N slaves (1-15) using Round Robin load balancing
- **OmniRoute**: Additional routing service (in development)

## Commands

### Root Makefile (Orchestrator)
```bash
# Start services
make up SERVICE=ai-memory    # Start ai-memory server
make up SERVICE=9router      # Start 9Router pool (master + 3 slaves)
make up SERVICE=omniroute    # Start OmniRoute

# Shortcuts
make cc                      # Run Claude Code with memory
make code                    # Run OpenCode with memory

# Stop services
make down                    # Stop all services
make down SERVICE=ai-memory  # Stop specific service

# Logs
make logs SERVICE=ai-memory  # View logs

# Cleanup
make clean                   # Remove all volumes and data
make clean SERVICE=ai-memory # Clean specific service

# Build
make build                   # Build Docker images for claude-code and opencode
```

### ai-memory Service (`scripts/ai-memory/`)
```bash
cd scripts/ai-memory
make up      # Start ai-memory container
make down    # Stop ai-memory
make logs    # View logs
make clean   # Remove volume and data
```

### 9Router Pool (`scripts/9router-pool/`)
```bash
cd scripts/9router-pool

# Pool management via pool.py
python3 pool.py create           # Create pool (1 master + 1 slave)
python3 pool.py list             # Show pool configuration
python3 pool.py sync             # Sync config with master (health check, combos, providers, API key)
python3 pool.py test             # Test connectivity to all instances
python3 pool.py scale N          # Scale to N slaves (1-15)
python3 pool.py backup           # Backup master configuration
python3 pool.py restore FILE     # Restore from backup

# Make targets
make up      # Start containers
make down    # Stop containers
make logs    # View logs
make clean   # Remove volumes
make build   # Build images
```

### Environment Configuration
```bash
cp .env-example .env
nano .env    # Add your API keys
```

Required variables in `.env`:
- `ANTHROPIC_API_KEY` — Your Anthropic API key
- `ANTHROPIC_BASE_URL` — Default: `http://host.docker.internal:20128/v1` (9Router master)
- `AI_MEMORY_AUTH_TOKEN` — Auth token for ai-memory
- `AI_MEMORY_SERVER_URL` — Default: `http://host.docker.internal:49374`

## Architecture

### Service Structure
```
.
├── Makefile                     # Root orchestrator (delegates to service Makefiles)
├── .env                         # Shared environment (gitignored)
├── .env-example                 # Template
├── scripts/
│   ├── ai-memory/               # Long-term memory server
│   │   ├── docker-compose.yaml  # ai-memory service on port 49374
│   │   └── Makefile
│   ├── 9router-pool/            # AI Gateway with Round Robin
│   │   ├── docker-compose.yaml  # Master (20128) + N slaves (20129+)
│   │   ├── pool.py              # Pool manager (create, scale, sync, test, backup)
│   │   ├── config.json          # Pool configuration
│   │   └── Makefile
│   └── omniroute/               # Additional router (WIP)
└── workspace/                   # Your code (mounted at /workspace in containers)
```

### Network Architecture
```
┌─────────────────┐     ┌──────────────────┐
│   ai-memory     │◄────│  Claude Code     │
│   (port 49374)  │     │  (managed run)   │
│                 │     └──────────────────┘
│                 │
│                 │     ┌──────────────────┐
│                 │     │    OpenCode      │
│                 │     │  (managed run)   │
│                 │     └──────────────────┘
└─────────────────┘
              ▲                    ▲
              │                    │
              ▼                    ▼
        ┌───────────────┐    ┌───────────────┐
        │ Wiki markdown │    │ Sessões nativas│
        │ + SQLite      │    │ + Handoffs    │
        └───────────────┘    └───────────────┘

┌──────────────────────────────────────────────────────────────┐
│                      9Router Cluster                         │
│  ┌──────────────┐    ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │   MASTER     │───►│ SLAVE 1  │ │ SLAVE 2  │ │ SLAVE 3  │  │
│  │  port 20128  │    │ 20129    │ │ 20130    │ │ 20131    │  │
│  │  Round Robin │    │ rs001    │ │ rs002    │ │ rs003    │  │
│  └──────────────┘    └──────────┘ └──────────┘ └──────────┘  │
└──────────────────────────────────────────────────────────────┘
```

All services share the `sbx-net` Docker network. ai-memory uses `host.docker.internal` to reach 9Router master.

### ai-memory Data Flow
- Stores data in `Vault/ai-memory/` (mounted at `/data` in container)
- Uses SQLite for session storage + markdown for wiki-style notes
- Provides MCP tools: `memory_briefing`, `memory_recent`, `memory_status`
- Connects to Anthropic via `ANTHROPIC_BASE_URL` (points to 9Router master)

### 9Router Pool Operation
1. **Master** (port 20128): Accepts client requests, routes via Round Robin to slaves
2. **Slaves** (ports 20129+): Connect to free AI providers via Tor/proxy
3. **Sync process**: `pool.py sync` configures providers, combos, custom models, and round-robin on master
4. **Clients** use Master's API key and base URL (`http://localhost:20128/v1`)

## Key Files to Know

| File | Purpose |
|------|---------|
| `Makefile` | Root orchestrator, delegates to service Makefiles |
| `scripts/ai-memory/docker-compose.yaml` | ai-memory container definition |
| `scripts/9router-pool/pool.py` | Pool management CLI (create/scale/sync/test/backup) |
| `scripts/9router-pool/config.json` | Pool configuration (slaves, models, combos) |
| `.env` | Runtime secrets (API keys, tokens) — **gitignored** |
| `.claude/settings.local.json` | Local Claude Code settings (MCP servers, permissions) |

## Development Notes

- **Docker network**: All services use external network `sbx-net`
- **UID/GID**: Set in `.env` (default 1000:1000) for file permissions
- **Volumes**: ai-memory data persists in `Vault/ai-memory/`; 9Router uses named volumes
- **No tests/linting**: This is a Docker/orchestration project, not a code library
- **Port allocation**: 9Router master=20128, slaves=20129-20142 (max 15 slaves)

## MCP Integration

ai-memory exposes MCP tools available to Claude Code:
- `memory_briefing` — Get session briefing
- `memory_recent` — Get recent memories
- `memory_status` — Check server status

Configured in `.claude/settings.local.json` under `enabledMcpjsonServers: ["ai-memory"]`.

## Common Workflows

### First Time Setup
```bash
cp .env-example .env
# Edit .env with your ANTHROPIC_API_KEY
make up SERVICE=9router     # Start gateway
make up SERVICE=ai-memory   # Start memory server
make cc                     # Launch Claude Code with memory
```

### Adding More Slaves to 9Router
```bash
cd scripts/9router-pool
python3 pool.py scale 5     # Scale to 5 slaves
python3 pool.py sync        # Re-sync configuration
```

### Cleanup Everything
```bash
make clean                  # Removes all volumes and data
```