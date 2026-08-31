# AI Workspace

Ambiente de desenvolvimento com **memória de longo prazo** (ai-memory) para agentes de IA, incluindo **9Router** como gateway gratuito de API IA.

## O que é

- **ai-memory**: Servidor que permite continuidade entre sessões e troca de contexto entre Claude Code e OpenCode
- **9Router**: Gateway gratuito de API IA com 1 master + 3 slaves (Round Robin load balancing)

## Quick Start

```bash
# 1. Clone e configure
cp .env-example .env
nano .env  # adicione suas chaves

# 2. Suba o que precisar
make up SERVICE=ai-memory   # servidor ai-memory
make up SERVICE=9router     # 9Router (gateway IA gratuito)

# 3. Use
make cc                     # Claude Code com memória
make code                   # OpenCode com memória
```

## Comandos

| Comando | Descrição |
|---------|-----------|
| `make up SERVICE=ai-memory` | Inicia ai-memory |
| `make up SERVICE=9router` | Inicia 9Router (master + 3 slaves) |
| `make cc` | Abre Claude Code com memória |
| `make code` | Abre OpenCode com memória |
| `make down` | Para todos os serviços |
| `make down SERVICE=ai-memory` | Para só ai-memory |
| `make down SERVICE=9router` | Para só 9Router |
| `make logs SERVICE=ai-memory` | Logs do ai-memory |
| `make logs SERVICE=9router` | Logs do 9Router |
| `make clean` | Remove volumes e limpa tudo |
| `make clean SERVICE=ai-memory` | Limpa só ai-memory |
| `make build` | Constrói imagens Dockerfile |

## Estrutura

Cada serviço tem seu próprio `docker-compose.yaml` e `Makefile` em `scripts/`:

```
.
├── Makefile                     # Orquestrador raiz (delega para cada serviço)
├── .env                         # Suas chaves (compartilhado entre todos)
├── .env-example                 # Template
├── scripts/
│   ├── ai-memory/
│   │   ├── docker-compose.yaml  # Servidor ai-memory
│   │   └── Makefile
│   ├── claude-code/
│   │   ├── docker-compose.yaml  # Container Claude Code
│   │   ├── Dockerfile
│   │   ├── entrypoint.sh
│   │   └── Makefile
│   ├── opencode/
│   │   ├── docker-compose.yaml  # Container OpenCode
│   │   ├── Dockerfile
│   │   ├── entrypoint.sh
│   │   └── Makefile
│   └── 9router/
│       ├── docker-compose.yaml  # 9Router: master + 3 slaves
│       ├── Makefile
│       ├── README.md
│       └── .env
└── workspace/                   # Seu código (montado em /workspace)
```

## Arquitetura

```
┌─────────────────┐     ┌──────────────────┐
│   ai-memory     │◄────│  Claude Code     │
│   (servidor)    │     │  (managed run)   │
│   porta 49374   │     └──────────────────┘
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

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [INSTALL.md](INSTALL.md) | Guia completo de instalação e uso |
| [scripts/9router/README.md](scripts/9router/README.md) | Configuração detalhada do 9Router |

## Licença

Uso interno.
