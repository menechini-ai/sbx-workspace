"""Docker compose and env file generation for standalone."""

from __future__ import annotations

from typing import Any

from .config import BASE_DIR
from .console import info, success, warning


def generate_docker_compose(config: dict[str, Any]) -> str:
    """Generate docker-compose.yaml for standalone instance."""

    master_port = 20128

    compose = f"""x-common: &common
  restart: unless-stopped
  stop_grace_period: 10s
  env_file: .env
  logging:
    driver: json-file
    options:
      max-size: "20m"
      max-file: "3"

x-service-standalone: &service-standalone
  <<: *common
  deploy:
    resources:
      limits:
        memory: 512M
        cpus: "1.0"
      reservations:
        memory: 256M
        cpus: "0.25"

services:
  9router-standalone:
    <<: *service-standalone
    image: decolua/9router:${{NINEROUTER_TAG:-latest}}
    container_name: sbx-9router-standalone
    pull_policy: missing
    ports:
      - "${{ROUTER_PORT_STANDALONE:-{master_port}}}:{master_port}"
    volumes:
      - 9router-standalone-data:/app/data
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "--timeout=5", "http://127.0.0.1:{master_port}/"]
      interval: 10s
      timeout: 10s
      retries: 10
      start_period: 30s
    environment:
      DATA_DIR: /app/data
      PORT: "${{ROUTER_PORT_STANDALONE:-{master_port}}}"
      MACHINE_ID_SALT: $(openssl rand -hex 32)
      HOSTNAME: 0.0.0.0
      ROLE: master
      JWT_SECRET: "${{JWT_SECRET:-P4s5w0rd}}"
      INITIAL_PASSWORD: "${{INITIAL_PASSWORD:-123456}}"
      HTTP_PROXY: "${{TOR_SOCKS_URL:-socks5://sbx-tor:9050}}"
      HTTPS_PROXY: "${{TOR_SOCKS_URL:-socks5://sbx-tor:9050}}"
      ALL_PROXY: "${{TOR_SOCKS_URL:-socks5://sbx-tor:9050}}"
      NO_PROXY: "${{TOR_NO_PROXY:-localhost,127.0.0.1}}"
    networks:
      - sbx-net

volumes:
  9router-standalone-data:

networks:
  sbx-net:
    name: sbx-net
    driver: bridge
"""
    return compose


def generate_env() -> str:
    """Generate .env file for standalone."""

    lines = [
        "# sbx — 9Router Standalone Environment",
        "TZ=America/Sao_Paulo",
        "ROUTER_PORT_STANDALONE=20128",
        "ROUTER_DEBUG=false",
        "",
        "JWT_SECRET=N7ZndMLMYqJu8QLRtY+dE1VynAdESAJfc7maXp+lHqY=",
        "INITIAL_PASSWORD=123456",
    ]
    return "\n".join(lines) + "\n"