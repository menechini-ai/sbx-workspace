COMPOSE := docker compose --env-file ../../.env

.PHONY: up down logs clean restart test status

up:
	@docker network inspect sbx-net >/dev/null 2>&1 || docker network create sbx-net
	$(COMPOSE) up -d --remove-orphans

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v

restart:
	$(COMPOSE) restart

status:
	@docker ps --filter name=sbx-tor --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	@echo ""
	@echo "SOCKS proxy: 127.0.0.1:$${TOR_SOCKS_PORT:-9050}"
	@echo "HTTP  proxy: 127.0.0.1:$${TOR_HTTP_PORT:-8118}"

# Testa se o Tor está roteando corretamente
test:
	@echo "Testando SOCKS (9050) via Tor..."
	@curl -s --socks5-hostname 127.0.0.1:$${TOR_SOCKS_PORT:-9050} https://check.torproject.org/api/ip | jq . 2>/dev/null || \
		curl -s --socks5-hostname 127.0.0.1:$${TOR_SOCKS_PORT:-9050} https://check.torproject.org/api/ip || \
		echo "Falha: Tor SOCKS não respondeu"
	@echo ""
	@echo "Testando HTTP proxy (8118) via Tor..."
	@curl -s -x http://127.0.0.1:$${TOR_HTTP_PORT:-8118} https://check.torproject.org/api/ip | jq . 2>/dev/null || \
		curl -s -x http://127.0.0.1:$${TOR_HTTP_PORT:-8118} https://check.torproject.org/api/ip || \
		echo "Falha: Tor HTTP não respondeu"
