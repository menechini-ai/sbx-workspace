COMPOSE := docker compose --env-file ../../.env

.PHONY: up down logs clean run attach

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v

run:
	docker exec -it claude-code claude --dangerously-skip-permissions

attach:
	docker exec -it claude-code claude --dangerously-skip-permissions