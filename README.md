# AI Workspace

Ambiente de desenvolvimento com **memória de longo prazo** (ai-memory) para agentes de IA, incluindo **9Router** como gateway gratuito de API IA.

## O que é

- **ai-memory**: Servidor que permite continuidade entre sessões e troca de contexto entre Claude Code e OpenCode
- **9Router**: Gateway gratuito de API IA com 1 master + 3 slaves ( Round Robin load balancing)

## Quick Start

```bash
# 1. Clone e configure
cp .env-example .env
nano .env  # adicione suas chaves

# 2. Suba tudo
make up           # servidor ai-memory
make 9router-up   # 9Router (gateway IA gratuito)

# 3. Use
make cc           # Claude Code com memória
make code         # OpenCode com memória
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

## Comandos

| Comando | Descrição |
|---------|-----------|
| `make up` | Inicia servidor ai-memory |
| `make down` | Para todos os serviços |
| `make cc` | Abre Claude Code com memória |
| `make code` | Abre OpenCode com memória |
| `make 9router-up` | Inicia 9Router (master + 3 slaves) |
| `make 9router-down` | Para 9Router |
| `make 9router-logs` | Ver logs do 9Router |
| `make logs` | Ver logs do ai-memory |
| `make build` | Constrói todas as imagens |
| `make clean` | Remove volumes e limpa |
| `make rebuild` | Rebuild completo |

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [INSTALL.md](INSTALL.md) | Guia completo de instalação e uso |
| [scripts/9router/README.md](scripts/9router/README.md) | Configuração detalhada do 9Router (providers, combos, Round Robin) |

## Estrutura

```
.
├── docker-compose.yaml          # Serviços principais (ai-memory, opencode, claude-code)
├── Makefile                     # Comandos de conveniência
├── .env                         # Suas chaves (não versionar!)
├── .env-example                 # Template
├── INSTALL.md                   # Guia de instalação
├── scripts/
│   ├── base/Dockerfile          # Imagem base compartilhada
│   ├── claude-code/             # Container Claude Code
│   ├── opencode/                # Container OpenCode
│   └── 9router/                 # 9Router: master + 3 slaves
│       ├── docker-compose.yaml  # Definição dos serviços
│       ├── README.md            # Guia completo de configuração
│       ├── .env                 # Config do 9Router
│       └── get-api-keys.sh      # Script de gerenciamento de API keys
└── workspace/                   # Seu código (montado em /workspace)
```

## Licença

Uso interno.
