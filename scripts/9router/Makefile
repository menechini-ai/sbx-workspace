COMPOSE := docker compose --env-file ../../.env

.PHONY: up down logs clean

up:
	$(COMPOSE) up -d  --remove-orphans

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

clean:
	$(COMPOSE) down -v
