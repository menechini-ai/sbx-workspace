#!/bin/bash
set -ex
cd /home/access/SRE/AI/sbx-workspace

echo "=== [1/5] Parar e limpar tor antigo ==="
cd scripts/tor
docker compose --env-file ../../.env down -v 2>/dev/null || true
docker volume rm tor_tor-data 2>/dev/null || true

echo "=== [2/5] Subir tor novo (alpine + torrc limpo) ==="
docker compose --env-file ../../.env up -d
echo "Aguardando tor..."
for i in $(seq 1 40); do
  status=$(docker inspect sbx-tor --format '{{.State.Status}}' 2>/dev/null || echo "missing")
  if [ "$status" = "running" ]; then
    echo "sbx-tor running (attempt $i)"
    break
  fi
  echo "  aguardando... ($i/40) status=$status"
  sleep 3
done

docker ps --filter name=sbx-tor --format "{{.Names}} | {{.Status}} | {{.Ports}}"
sleep 5
echo "--- tor logs ---"
docker logs sbx-tor --tail 15 2>&1

echo ""
echo "=== [3/5] Recriar slaves com env vars HTTP_PROXY ==="
cd /home/access/SRE/AI/sbx-workspace/scripts/9router-pool
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d --remove-orphans
echo "Aguardando slaves healthy..."
for i in $(seq 1 30); do
  healthy=$(docker ps --filter "name=sbx-9router-slave" --filter "status=running" --format "{{.Names}}" | wc -l)
  if [ "$healthy" -ge 2 ]; then
    echo "slaves up: $healthy"
    break
  fi
  sleep 3
done

echo "=== Verificar env vars nos slaves ==="
docker exec sbx-9router-slave-001 env | grep -iE "proxy|no_proxy" || echo "⚠ slave-001: sem proxy env vars"
docker exec sbx-9router-slave-002 env | grep -iE "proxy|no_proxy" || echo "⚠ slave-002: sem proxy env vars"

echo ""
echo "=== [4/5] Sync (cria tor-proxy pool via API) ==="
python3 pool.py sync --skip-health-check 2>&1 || echo "⚠ sync falhou (código: $?)"

echo ""
echo "=== [5/5] Verificar proxy-pools via API ==="
for host in 20129 20130 20128; do
  echo "--- localhost:$host ---"
  curl -s -u admin:123456 http://localhost:$host/api/proxy-pools 2>/dev/null \
    || curl -s http://localhost:$host/api/proxy-pools 2>/dev/null \
    || echo "  não respondeu"
done

echo ""
echo "=== Testar SOCKS5 via rede ==="
docker run --rm --network sbx-net curlimages/curl:8.5.0 \
  -s --socks5-hostname sbx-tor:9050 https://check.torproject.org/api/ip -m 30 2>&1 \
  || echo "⚠ Tor SOCKS inacessível via rede"

echo ""
echo "=== PRONTO ==="
echo "Dashboard slaves: http://localhost:20129/dashboard/proxy-pools"
echo "Dashboard slaves: http://localhost:20130/dashboard/proxy-pools"
echo "Dashboard master: http://localhost:20128/dashboard/proxy-pools"
