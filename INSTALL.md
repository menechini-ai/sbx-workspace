# Guia de Instalação e Uso

Este projeto configura um ambiente de desenvolvimento com **memória de longo prazo** (ai-memory) para agentes de IA (Claude Code e OpenCode), permitindo continuidade entre sessões e troca de contexto entre diferentes agentes. Inclui **9Router** como gateway gratuito de API IA com 1 master + 3 slaves.

Cada serviço roda de forma independente com seu próprio `docker-compose.yaml` e `Makefile`, orquestrados pelo Makefile raiz.

---

## Pré-requisitos

- **Docker** e **Docker Compose** instalados
- **Chave de API Anthropic** (para Claude Code/OpenCode)
- **Git** configurado (para commits automáticos)

---

## Configuração Inicial

### 1. Clone e configure variáveis de ambiente

```bash
git clone <seu-repo>
cd <seu-repo>

cp .env-example .env
nano .env
```

### 2. Configure o `.env`

```bash
# Chave da Anthropic (ou use 9Router como gateway gratuito)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Token do ai-memory
AI_MEMORY_AUTH_TOKEN=seu_token_super_seguro

# Modelo padrão
ANTHROPIC_MODEL=claude-sonnet-4-8

# UID/GID do seu usuário (para volumes)
UID=1000
GID=1000
```

---

## Comandos

### Subir serviços

```bash
make up SERVICE=ai-memory   # inicia ai-memory
make up SERVICE=9router     # inicia 9Router (master + 3 slaves)
```

### Agentes

```bash
make cc                     # Claude Code com memória
make code                   # OpenCode com memória
```

### Parar serviços

```bash
make down                   # para todos
make down SERVICE=ai-memory # para só ai-memory
make down SERVICE=9router   # para só 9Router
```

### Logs

```bash
make logs SERVICE=ai-memory # logs do ai-memory
make logs SERVICE=9router   # logs do 9Router
```

### Limpeza

```bash
make clean                  # remove volumes de todos
make clean SERVICE=ai-memory # limpa só ai-memory
```

### Build

```bash
make build                  # constrói imagens Dockerfile (claude-code, opencode)
```

---

## Estrutura do Projeto

Cada serviço tem seu próprio `docker-compose.yaml` e `Makefile` em `scripts/`:

```
.
├── Makefile                     # Orquestrador raiz
├── .env                         # Chaves compartilhadas
├── .env-example                 # Template
├── scripts/
│   ├── ai-memory/
│   │   ├── docker-compose.yaml  # Servidor ai-memory (porta 49374)
│   │   └── Makefile             # up/down/logs/clean
│   ├── claude-code/
│   │   ├── docker-compose.yaml  # Container Claude Code
│   │   ├── Dockerfile
│   │   ├── entrypoint.sh
│   │   └── Makefile             # up/down/run/logs/clean
│   ├── opencode/
│   │   ├── docker-compose.yaml  # Container OpenCode
│   │   ├── Dockerfile
│   │   ├── entrypoint.sh
│   │   └── Makefile             # up/down/run/logs/clean
│   └── 9router/
│       ├── docker-compose.yaml  # 9Router: master + 3 slaves
│       ├── Makefile             # up/down/logs/clean
│       ├── README.md            # Guia completo de configuração
│       └── .env                 # Config do 9Router
└── workspace/                   # Seu código (montado em /workspace)
```

### Como funciona a delegação

O Makefile raiz delega para cada sub-Makefile:

```bash
make up SERVICE=ai-memory
# → cd scripts/ai-memory && make up
# → docker compose --env-file ../../.env up -d
```

Cada sub-Makefile usa `--env-file ../../.env` para carregar as variáveis do `.env` na raiz.

### Rede compartilhada

Todos os serviços usam a rede `clawbox-net` como `external: true`. A rede é criada automaticamente pelo 9router (que a define) ou pode ser criada manualmente:

```bash
docker network create clawbox-net
```

---

## 9Router — Gateway IA Gratuito

O 9Router roda como containers Docker (1 master + 3 slaves) e fornece um gateway gratuito para APIs de IA:

- **Master** (porta 20128): Dashboard + API principal
- **Slaves** (portas 20129-20131): Providers reais
- **Dashboard**: http://localhost:20128/dashboard

```bash
make up SERVICE=9router     # inicia
make logs SERVICE=9router   # logs
make down SERVICE=9router   # para
```

**Configuração completa:** Veja [`scripts/9router/README.md`](scripts/9router/README.md).

### Integração com agentes

Para usar o 9Router como endpoint da Anthropic, configure no `.env`:

```bash
ANTHROPIC_BASE_URL=http://host.docker.internal:20128/v1
ANTHROPIC_API_KEY=not-needed
```

---

## Como Funciona a Memória

### Servidor ai-memory
- Roda na porta **49374** (interno: `http://ai-memory:49374`)
- Armazena wiki em `~/.ai-memory` (host) / `/data` (container)

### Modo Gerenciado
Ao executar `make cc` ou `make code`:
1. Conecta ao servidor ai-memory automaticamente
2. Instala **lifecycle hooks** para capturar observações
3. Configura **MCP** (Model Context Protocol) para ferramentas de memória
4. Permite **handoffs cross-agent**: saia do Claude, continue no OpenCode

---

## Fluxo de Trabalho Recomendado

### Sessão única
```bash
make up SERVICE=ai-memory   # inicia servidor
make up SERVICE=9router     # opcional, para IA gratuita
make cc                     # abre Claude Code
# ... trabalha ...
exit                        # sai - handoff salvo automaticamente
```

### Trocar de agente
```bash
make cc                     # Claude Code
# ... trabalha, depois sai ...
make code                   # OpenCode retoma onde parou
```

### Continuar depois de dias
```bash
make up SERVICE=ai-memory   # garante servidor rodando
make cc                     # nova sessão - recebe briefing
```

---

## Troubleshooting

### "ai-memory não conecta"
```bash
make logs SERVICE=ai-memory
docker exec -it ai-memory ai-memory status
```

### "Permissão negada em volumes"
```bash
sudo chown -R $USER:$USER ~/.ai-memory
```

### "9Router não inicia"
```bash
make logs SERVICE=9router
cat scripts/9router/.env
make down SERVICE=9router && make up SERVICE=9router
```

### "Rede clawbox-net não existe"
```bash
docker network create clawbox-net
```

---

## Referências

- [ai-memory GitHub](https://github.com/akitaonrails/ai-memory)
- [Claude Code Docs](https://docs.anthropic.com/claude-code)
- [OpenCode Docs](https://opencode.ai/docs)
- [9Router Setup](scripts/9router/README.md)
