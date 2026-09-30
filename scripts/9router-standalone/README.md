# 9Router Standalone Manager

Gerenciador standalone para instância única do 9Router. Versão simplificada do pool sem master/slave, sem scale — apenas uma instância com watchdog para auto-discovery de modelos.

## Estrutura

```
9router-standalone/
├── config.json          # Configuração (instância + defaults)
├── docker-compose.yaml  # Docker compose da instância
├── .env                 # Variáveis de ambiente
├── standalone.py        # Entry point principal
├── Makefile             # Comandos make
└── src/server_standalone/
    ├── __main__.py      # CLI principal
    ├── commands.py      # Comandos: list, create, test, sync, fetch, backup, clean
    ├── config.py        # Carregar/salvar config.json
    ├── models.py        # Classes Instance, RouterClient
    ├── sync.py          # Lógica de sync (configurar instância)
    ├── fetch.py         # Buscar modelos opencode free
    ├── watch.py         # Watchdog: health check + auto-discovery
    ├── docker.py        # Gerar docker-compose.yaml e .env
    └── console.py       # Helpers de output colorido
```

## Configuração (config.json)

```json
{
  "instance": {
    "name": "standalone",
    "host": "localhost:20128",
    "password": "123456"
  },
  "defaults": {
    "models": [
      "oc/big-pickle",
      "oc/jev-1.13-free",
      ...
    ],
    "combos": [
      {
        "name": "claude-sonnet-5",
        "models": ["oc/big-pickle", "oc/jev-1.13-free", ...]
      }
    ],
    "publish": ["claude-sonnet-5"],
    "proxy": {
      "name": "tor-proxy",
      "url": "socks5://sbx-tor:9050",
      "type": "socks5",
      "noProxy": "localhost,127.0.0.1"
    }
  }
}
```

## Comandos

### Via Python

```bash
# Listar configuração
python standalone.py list

# Criar instância (sobe container + sync)
python standalone.py create

# Testar conectividade
python standalone.py test

# Sincronizar configuração
python standalone.py sync
python standalone.py sync --dry-run
python standalone.py sync --health-check

# Buscar modelos opencode free
python standalone.py fetch

# Backup
python standalone.py backup
python standalone.py backup --output meu-backup.json

# Limpar tudo
python standalone.py clean
python standalone.py clean --dry-run

# Watchdog (monitoramento contínuo)
python standalone.py watch
python standalone.py watch --interval 180 --fetch-interval 600
```

### Via Make

```bash
make list
make create
make test
make sync
make fetch
make backup
make clean
make watch
make watch-fast   # interval=60s, fetch=5min
```

## Watchdog (watch)

O comando `watch` roda um loop contínuo que:

1. **Health Check** (a cada `--interval` segundos, padrão 180s):
   - Testa todos os providers da instância
   - Verifica combos e custom models

2. **Auto-Discovery de Modelos** (a cada `--fetch-interval` segundos, padrão 600s/10min):
   - Busca modelos free do opencode via `/api/providers/suggested-models`
   - Testa thinking capability de cada modelo
   - Atualiza `config.json` com novos modelos
   - Faz hot-reload na instância (reconfigura combos)

```bash
# Padrão: health a cada 3min, fetch a cada 10min
python standalone.py watch

# Agressivo: health a cada 1min, fetch a cada 5min
python standalone.py watch --interval 60 --fetch-interval 300

# Apenas health check (sem auto-discovery)
python standalone.py watch --fetch-interval 0
```

## Arquitetura

Diferente do pool, o standalone **não tem**:
- ❌ Master
- ❌ Slaves
- ❌ Scale (scale up/down)
- ❌ Provider nodes/connections
- ❌ Round-robin entre múltiplas instâncias

O standalone **tem**:
- ✅ Uma instância 9Router rodando como master
- ✅ Proxy pool (Tor) configurado automaticamente
- ✅ Combos criados a partir de `defaults.combos`
- ✅ Custom models limpos (mantém apenas os que estão em combos)
- ✅ Watchdog com auto-discovery de modelos opencode
- ✅ Hot-reload de modelos sem reiniciar container

## Uso com OpenCode

Após `create` ou `sync`, a API key é exibida:

```
API Key da Instância (use nos clientes):
  sk-xxxxxxxxxxxxxxxxxxxxxxxx

Exemplo OpenCode:
  apiKey: "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
  baseUrl: "http://localhost:20128/v1"
```

Configure no OpenCode:

```json
{
  "apiKey": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
  "baseUrl": "http://localhost:20128/v1"
}
```

Os modelos disponíveis serão os combos publicados (ex: `claude-sonnet-5`, `claude-opus-5`).

## Docker

A instância roda na porta **20128** (configurável via `ROUTER_PORT_STANDALONE` no `.env`).

Volumes persistidos:
- `9router-standalone-data` → `/app/data` (configuração do 9Router)

Rede:
- `sbx-net` (bridge) — compartilhada com `sbx-tor` se existir

## Requisitos

- Docker + Docker Compose
- Python 3.10+
- `requests` (`pip install requests`)
- Container `sbx-tor` rodando na rede `sbx-net` (para proxy Tor)

## Fluxo Típico

```bash
# 1. Primeira vez: criar tudo
make create

# 2. Verificar se está funcionando
make test

# 3. Rodar watchdog em background (screen/tmux/systemd)
make watch

# 4. Quando quiser atualizar modelos manualmente
make fetch
make sync

# 5. Limpar tudo se precisar resetar
make clean
```