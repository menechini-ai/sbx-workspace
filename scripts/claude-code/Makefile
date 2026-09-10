COMPOSE := docker compose --env-file ../../.env

.PHONY: up down logs clean run

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v

run:
	$(COMPOSE) run --rm claude-code
