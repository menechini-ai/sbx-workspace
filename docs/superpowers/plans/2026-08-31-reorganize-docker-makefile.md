# Reorganização Docker + Makefile — Padrão clawboxfree

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar o docker-compose monolítico em comandos por serviço, cada um com seu docker-compose.yaml e Makefile, com um Makefile raiz orquestrador.

**Architecture:** Cada serviço em `scripts/<service>/` ganha seu próprio `docker-compose.yaml` + `Makefile`. O Makefile raiz delega com `docker compose -f scripts/$SERVICE/docker-compose.yaml <action>`. A rede `clawbox-net` é criada pelo 9router e referenciada como `external` pelos demais.

**Tech Stack:** Docker Compose v2, Make

**Spec:** N/A (design aprovado em chat)

## Global Constraints

- Rede `clawbox-net` definida em `scripts/9router/docker-compose.yaml` (já existe)
- Todos os outros services usam `external: true` na rede
- `.env` na raiz é compartilhado entre todos os services
- Containers de agentes (cc, code) usam `docker compose run --rm` (não `up -d`)
- Serviços de infra (ai-memory, 9router) usam `docker compose up -d`

## File Structure

| Ação | Arquivo |
|------|---------|
| Criar | `scripts/ai-memory/docker-compose.yaml` |
| Criar | `scripts/ai-memory/Makefile` |
| Criar | `scripts/claude-code/docker-compose.yaml` |
| Criar | `scripts/claude-code/Makefile` |
| Criar | `scripts/opencode/docker-compose.yaml` |
| Criar | `scripts/opencode/Makefile` |
| Criar | `scripts/9router/Makefile` |
| Modificar | `Makefile` (raiz — orquestrador) |
| Remover | `docker-compose.yaml` (raiz — monolítico) |

---

### Task 1: docker-compose.yaml do ai-memory

**Files:**
- Create: `scripts/ai-memory/docker-compose.yaml`

Extrair o serviço `ai-memory` do docker-compose.yaml raiz para seu próprio arquivo.

- [ ] **Step 1: Criar `scripts/ai-memory/docker-compose.yaml`**

```yaml
services:
  ai-memory:
    image: akitaonrails/ai-memory:latest
    container_name: ai-memory
    restart: unless-stopped
    user: "${UID}:${GID}"
    ports:
      - "49374:49374"
    volumes:
      - /home/access/.ai-memory:/data
    environment:
      - AI_MEMORY_AUTH_TOKEN=${AI_MEMORY_AUTH_TOKEN}
      - AI_MEMORY_LLM_PROVIDER=anthropic
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.anthropic.com}
      - ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-claude-sonnet-4-8}
    extra_hosts:
      - host.docker.internal:host-gateway
    networks:
      - clawbox-net

networks:
  clawbox-net:
    external: true
```

- [ ] **Step 2: Verificar**

```bash
cd /home/access/SRE/AI/sbx-workspace
docker compose -f scripts/ai-memory/docker-compose.yaml config
```

Esperado: YAML válido sem erros.

---

### Task 2: Makefile do ai-memory

**Files:**
- Create: `scripts/ai-memory/Makefile`

- [ ] **Step 1: Criar `scripts/ai-memory/Makefile`**

```makefile
COMPOSE := docker compose

.PHONY: up down logs clean

up:
	$(COMPOSE) up -d  --remove-orphans

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v
```

- [ ] **Step 2: Verificar**

```bash
cd /home/access/SRE/AI/sbx-workspace/scripts/ai-memory
make up
docker ps | grep ai-memory
make down
```

---

### Task 3: docker-compose.yaml do claude-code

**Files:**
- Create: `scripts/claude-code/docker-compose.yaml`

- [ ] **Step 1: Criar `scripts/claude-code/docker-compose.yaml`**

```yaml
services:
  claude-code:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: claude-code
    restart: "no"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.anthropic.com}
      - ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-claude-sonnet-4-8}
      - ANTHROPIC_DEFAULT_OPUS_MODEL=${ANTHROPIC_DEFAULT_OPUS_MODEL:-claude-opus-4-8}
      - ANTHROPIC_DEFAULT_SONNET_MODEL=${ANTHROPIC_DEFAULT_SONNET_MODEL:-claude-sonnet-4-8}
      - ANTHROPIC_DEFAULT_HAIKU_MODEL=${ANTHROPIC_DEFAULT_HAIKU_MODEL:-claude-haiku-4-8}
      - CLAUDE_CODE_MAX_CONTEXT_TOKENS=100000
      - CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1
      - AI_MEMORY_SERVER_URL=${AI_MEMORY_SERVER_URL:-http://ai-memory:49374}
      - AI_MEMORY_AUTH_TOKEN=${AI_MEMORY_AUTH_TOKEN}
    volumes:
      - ../../workspace:/workspace
      - ../../.claude:/workspace/.claude:rw
      - claude_config:/home/node/.claude
    working_dir: /workspace
    tty: true
    stdin_open: true
    extra_hosts:
      - host.docker.internal:host-gateway
    networks:
      - clawbox-net
    depends_on:
      ai-memory:
        condition: service_started

volumes:
  claude_config:

networks:
  clawbox-net:
    external: true
```

- [ ] **Step 2: Verificar**

```bash
docker compose -f scripts/claude-code/docker-compose.yaml config
```

---

### Task 4: Makefile do claude-code

**Files:**
- Create: `scripts/claude-code/Makefile`

- [ ] **Step 1: Criar `scripts/claude-code/Makefile`**

```makefile
COMPOSE := docker compose
GIT_NAME := $(shell git config user.name 2>/dev/null || echo "Agent")
GIT_EMAIL := $(shell git config user.email 2>/dev/null || echo "agent@local")

.PHONY: up down run logs clean

up:
	$(COMPOSE) up -d  --remove-orphans

run:
	@echo "Iniciando Claude Code..."
	@GIT_AUTHOR_NAME="$(GIT_NAME)" \
	GIT_AUTHOR_EMAIL="$(GIT_EMAIL)" \
	GIT_COMMITTER_NAME="$(GIT_NAME)" \
	GIT_COMMITTER_EMAIL="$(GIT_EMAIL)" \
	$(COMPOSE) run --rm claude-code

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v
```

---

### Task 5: docker-compose.yaml do opencode

**Files:**
- Create: `scripts/opencode/docker-compose.yaml`

- [ ] **Step 1: Criar `scripts/opencode/docker-compose.yaml`**

```yaml
services:
  opencode:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: opencode
    restart: "no"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-https://api.anthropic.com}
      - ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-claude-sonnet-4-8}
      - ANTHROPIC_DEFAULT_OPUS_MODEL=${ANTHROPIC_DEFAULT_OPUS_MODEL:-claude-opus-4-8}
      - ANTHROPIC_DEFAULT_SONNET_MODEL=${ANTHROPIC_DEFAULT_SONNET_MODEL:-claude-sonnet-4-8}
      - ANTHROPIC_DEFAULT_HAIKU_MODEL=${ANTHROPIC_DEFAULT_HAIKU_MODEL:-claude-haiku-4-8}
      - AI_MEMORY_SERVER_URL=${AI_MEMORY_SERVER_URL:-http://ai-memory:49374}
      - AI_MEMORY_AUTH_TOKEN=${AI_MEMORY_AUTH_TOKEN}
    volumes:
      - /home/access/SRE/AI/sbx-workspace:/workspace
      - ~/.gitconfig:/root/.gitconfig:ro
      - opencode_config:/home/node/.config/opencode
    working_dir: /workspace
    tty: true
    stdin_open: true
    extra_hosts:
      - host.docker.internal:host-gateway
    networks:
      - clawbox-net
    depends_on:
      ai-memory:
        condition: service_started

volumes:
  opencode_config:

networks:
  clawbox-net:
    external: true
```

- [ ] **Step 2: Verificar**

```bash
docker compose -f scripts/opencode/docker-compose.yaml config
```

---

### Task 6: Makefile do opencode

**Files:**
- Create: `scripts/opencode/Makefile`

- [ ] **Step 1: Criar `scripts/opencode/Makefile`**

```makefile
COMPOSE := docker compose
GIT_NAME := $(shell git config user.name 2>/dev/null || echo "Agent")
GIT_EMAIL := $(shell git config user.email 2>/dev/null || echo "agent@local")

.PHONY: up down run logs clean

up:
	$(COMPOSE) up -d  --remove-orphans

run:
	@echo "Iniciando OpenCode..."
	@GIT_AUTHOR_NAME="$(GIT_NAME)" \
	GIT_AUTHOR_EMAIL="$(GIT_EMAIL)" \
	GIT_COMMITTER_NAME="$(GIT_NAME)" \
	GIT_COMMITTER_EMAIL="$(GIT_EMAIL)" \
	$(COMPOSE) run --rm opencode

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v
```

---

### Task 7: Makefile do 9router

**Files:**
- Create: `scripts/9router/Makefile`

- [ ] **Step 1: Criar `scripts/9router/Makefile`**

```makefile
COMPOSE := docker compose

.PHONY: up down logs clean

up:
	$(COMPOSE) up -d  --remove-orphans

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v
```

---

### Task 8: Makefile raiz orquestrador

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Substituir o Makefile raiz**

```makefile
SERVICES := ai-memory claude-code opencode 9router

.PHONY: up down logs clean build $(SERVICES)

# make up ai-memory / make up cc / make up code / make up 9router
up:
	@if [ -z "$(filter $(SERVICES),$(SERVICE))" ]; then \
		echo "Uso: make up <servico>"; \
		echo "Servicos: $(SERVICES)"; \
		echo "Atalhos: make cc (=claude-code), make code (=opencode)"; \
		exit 1; \
	fi
	$(MAKE) $(SERVICE)

# Atalhos
cc: claude-code
code: opencode

# Delega para cada serviço
ai-memory:
	cd scripts/ai-memory && make up

claude-code:
	cd scripts/claude-code && make up

opencode:
	cd scripts/opencode && make up

9router:
	cd scripts/9router && make up

# Para tudo
down:
	@for svc in $(SERVICES); do \
		echo "Parando $$svc..."; \
		cd scripts/$$svc && make down && cd ../..; \
	done

# Logs
logs:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Uso: make logs <servico>"; \
		exit 1; \
	fi
	cd scripts/$(SERVICE) && make logs

# Limpa tudo (volumes)
clean:
	@for svc in $(SERVICES); do \
		echo "Limpando $$svc..."; \
		cd scripts/$$svc && make clean && cd ../..; \
	done

# Build (para services com Dockerfile)
build:
	docker compose -f scripts/claude-code/docker-compose.yaml build
	docker compose -f scripts/opencode/docker-compose.yaml build
```

- [ ] **Step 2: Remover docker-compose.yaml raiz**

```bash
rm docker-compose.yaml
```

- [ ] **Step 3: Verificar**

```bash
cd /home/access/SRE/AI/sbx-workspace
# Testar help
make up

# Testar subir ai-memory
make up ai-memory

# Testar atalho cc
make cc

# Testar down
make down
```

---

### Task 9: Atualizar .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Verificar se precisa de ajustes**

O `.gitignore` atual deve continuar funcionando. Verificar que `docker-compose.yaml` removido não cause problemas.

```bash
git status
```
