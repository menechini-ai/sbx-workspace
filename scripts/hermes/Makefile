COMPOSE := docker compose --env-file ../../.env

.PHONY: up down logs clean restart build status shell config init-volumes

# Sobe o hermes-agent (gateway + dashboard)
up:
	@docker network inspect sbx-net >/dev/null 2>&1 || docker network create sbx-net
	@mkdir -p ../../Vault/hermes
	@HERMES_UID=$$(id -u) HERMES_GID=$$(id -g) $(COMPOSE) up -d --remove-orphans
	@echo ""
	@echo "Aguardando inicializacao..."
	@sleep 3
	@$(MAKE) status

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v

restart:
	$(COMPOSE) restart

build:
	$(COMPOSE) build

status:
	@docker ps --filter name=sbx-hermes --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "Gateway:  network_mode=host (acessivel via localhost)"
	@echo "Dashboard: http://localhost:9119 (use SSH tunnel: ssh -L 9119:localhost:9119)"
	@echo "Data dir: ../../Vault/hermes"

shell:
	@HERMES_UID=$$(id -u) HERMES_GID=$$(id -g) $(COMPOSE) run --rm hermes-gateway hermes --help

# Inicializa a configuracao do hermes
config:
	@mkdir -p ../../Vault/hermes
	@docker run --rm -v ../../Vault/hermes:/opt/data nousresearch/hermes-agent:latest hermes setup --accept-hooks 2>&1 | tail -n 20 || true
	@echo ""
	@echo "Configuracao criada em ../../Vault/hermes/config.yaml"
	@echo "Edite o arquivo e defina:"
	@echo "  model.default: anthropic/claude-opus-4.6"
	@echo "  model.provider: anthropic   # ou custom para 9Router"
	@echo "  model.base_url: http://host.docker.internal:20128/v1  # se provider=custom"
	@echo ""
	@echo "Para adicionar ai-memory como MCP server, edite config.yaml:"
	@echo "  mcp_servers:"
	@echo "    ai-memory:"
	@echo "      url: http://host.docker.internal:49374/mcp"
	@echo "      headers:"
	@echo "        Authorization: Bearer \$\$\{AI_MEMORY_AUTH_TOKEN\}"

# Sobe o hermes-agent com config inicial (primeira vez)
init: up config

# Testa se o gateway esta respondendo
test-gateway:
	@curl -s -m 5 http://localhost:8642/ 2>/dev/null || echo "Gateway nao responde na porta 8642 (padrao API_SERVER_PORT)"
	@echo "Use: hermes gateway start com API_SERVER_HOST=0.0.0.0 API_SERVER_KEY=..."
