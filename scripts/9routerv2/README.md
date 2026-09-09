# 9Router Pool Manager

Gerencia um pool de 9Router com 1 Master + N Slaves (1-15) usando Round Robin load balancing.

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                      CLIENTS                            │
│                (OpenCode, Claude, etc.)                  │
└──────────────────────┬──────────────────────────────────┘
                       │ API Key do Master
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  9ROUTER MASTER                         │
│               http://localhost:20128                    │
│                                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │  rs001  │  │  rs002  │  │  rs003  │  │  rs00N  │   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘   │
└───────┼────────────┼────────────┼────────────┼──────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ SLAVE-1 │  │ SLAVE-2 │  │ SLAVE-3 │  │ SLAVE-N │
│ :20129  │  │ :20130  │  │ :20131  │  │ :20128+N│
└─────────┘  └─────────┘  └─────────┘  └─────────┘
```

## Pré-requisitos

- Docker + Docker Compose
- Python 3.10+
- `requests` library (`pip install requests`)

## Início Rápido

```bash
# 1. Subir com 1 slave
docker compose up -d

# 2. Sincronizar com master (cria providers, combos, API keys)
python pool.py sync

# 3. Usar a API key do master nos clientes
```

## Comandos

### pool.py list

Lista a configuração atual do pool.

```bash
python pool.py list
```

**Saída:**
```
9ROUTER POOL
──────────────────────────────────────────────────────────────────────
Master: localhost:20128
Slaves: 3
  - rs001 → localhost:20129
  - rs002 → localhost:20130
  - rs003 → localhost:20131

Models: 4
  - claude-sonnet-5
  - claude-opus-5
  - kc/openrouter/free
  - kc/kilo-auto/free

Combos: 2
  - claude-opus-5 (3 models)
  - claude-sonnet-5 (2 models)
```

### pool.py sync

Sincroniza a configuração local com o master. Cria providers, connections, combos, custom models e API keys.

```bash
python pool.py sync
```

**O que faz:**
1. Cria API keys nos slaves
2. Cria provider nodes no master
3. Cria provider connections no master
4. Cria custom models no master
5. Cria combos no master
6. Configura round-robin
7. Exporta a API key do master

**Saída importante:**
```
API Key do Master (use nos clientes):
  sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

Exemplo OpenCode:
  apiKey: "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  baseUrl: "http://localhost:20128/v1"
```

### pool.py test

Testa conectividade com todas as instâncias.

```bash
python pool.py test
```

**Saída:**
```
9ROUTER POOL TEST
──────────────────────────────────────────────────────────────────────
master → localhost:20128
  [+] login OK
  [+] rs001 → SAUDÁVEL
  [+] rs002 → SAUDÁVEL
  [+] rs003 → SAUDÁVEL

rs001 → localhost:20129
  [+] login OK

rs002 → localhost:20130
  [+] login OK

rs003 → localhost:20131
  [+] login OK

[+] Todos os 4 instâncias OK
```

### pool.py scale N

Escala o pool para N slaves (1-15).

```bash
python pool.py scale 1      # 1 slave (padrão)
python pool.py scale 3      # 3 slaves
python pool.py scale 6      # 6 slaves
python pool.py scale 10     # 10 slaves
python pool.py scale 15     # 15 slaves (máximo)
```

**O que faz:**
1. Gera `docker-compose.yaml` com N slaves
2. Gera `.env` com portas (20129-20128+N)
3. Cria/remove diretórios `data/9router/slave/NNN`
4. Atualiza `config.json`
5. Executa `docker compose up -d`

**Opções:**
```bash
python pool.py scale 6 --dry-run    # Simular sem alterar
python pool.py scale 6 --no-sync    # Não sincronizar após criar
```

### pool.py slave add

Adiciona um slave manualmente.

```bash
python pool.py slave add rs004 localhost:20132 --docker-host 9router-slave-004:20132
```

### pool.py slave delete

Remove um slave.

```bash
python pool.py slave delete rs004
```

### pool.py backup

Faz backup da configuração do master.

```bash
python pool.py backup
python pool.py backup --output backup.json
```

### pool.py clean

Remove tudo: containers, dados, configs. Reseta para 1 master + 1 slave.

```bash
python pool.py clean           # Remove tudo e sobe limpo
python pool.py clean --dry-run # Simula sem alterar
```

**O que faz:**
1. `docker compose down -v --remove-orphans` — para e remove todos os containers
2. Remove `data/9router/master` e `data/9router/slave/NNN`
3. Reseta `config.json` para 1 slave
4. Gera `docker-compose.yaml` e `.env` para 1 slave
5. Sobe com 1 master + 1 slave limpo

**Depois rode:** `python pool.py sync` para configurar

**Se der erro de permissão:**
```bash
sudo rm -rf scripts/9routerv2/data/9router/master
sudo rm -rf scripts/9routerv2/data/9router/slave
```

## Portas

| Serviço | Porta | Uso |
|---------|-------|-----|
| master | 20128 | API principal + Dashboard |
| slave-001 | 20129 | Backend 1 |
| slave-002 | 20130 | Backend 2 |
| slave-003 | 20131 | Backend 3 |
| slave-NNN | 20128+N | Backend N |
| tor | 9050/8118 | Proxy (SOCKS/HTTP) |

## Endpoints

| Endpoint | URL | Uso |
|----------|-----|-----|
| Master API | `http://localhost:20128/v1` | Clientes conectam aqui |
| Master Dashboard | `http://localhost:20128/dashboard` | Configuração web |
| Slave API | `http://localhost:20129/v1` | Acesso direto (debug) |

## Configuração

### config.json

```json
{
  "master": {
    "name": "master",
    "host": "localhost:20128",
    "password": "123456"
  },
  "defaults": {
    "models": [
      "claude-sonnet-5",
      "claude-opus-5",
      "kc/openrouter/free",
      "kc/kilo-auto/free"
    ],
    "combos": [
      {
        "name": "claude-opus-5",
        "models": [
          "oc/deepseek-v4-flash-free",
          "oc/mimo-v2.5-free",
          "oc/nemotron-3-ultra-free"
        ]
      }
    ],
    "publish": ["claude-opus-5", "claude-sonnet-5"]
  },
  "slaves": [
    {
      "name": "rs001",
      "host": "localhost:20129",
      "docker_host": "9router-slave-001:20129",
      "password": "123456"
    }
  ]
}
```

### Adicionar Models

Edite `config.json` → `defaults.models`:

```json
"models": [
  "claude-sonnet-5",
  "claude-opus-5",
  "kc/openrouter/free",
  "kc/kilo-auto/free",
  "novo-modelo"
]
```

### Adicionar Combos

Edite `config.json` → `defaults.combos`:

```json
"combos": [
  {
    "name": "novo-combo",
    "models": ["modelo-a", "modelo-b"]
  }
]
```

### Publicar Combos

Edite `config.json` → `defaults.publish`:

```json
"publish": ["claude-opus-5", "claude-sonnet-5", "novo-combo"]
```

## Uso com OpenCode

Após rodar `python pool.py sync`, use a API key exportada:

```yaml
# ~/.opencode/config.yaml
providers:
  9router:
    apiKey: "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    baseUrl: "http://localhost:20128/v1"
```

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `pool.py` | Script principal de gerenciamento |
| `config.json` | Configuração do pool |
| `docker-compose.yaml` | Definição dos containers |
| `.env` | Variáveis de ambiente |
| `torrc` | Configuração do Tor proxy |
| `data/` | Dados dos containers |

## Troubleshooting

### Provider não conecta ao slave

```bash
python pool.py test
```

Verifique se todos os slaves estão SAUDÁVEL.

### Combo não aparece no master

```bash
python pool.py sync
```

Re-sincroniza a configuração.

### Scale não cria diretórios

```bash
sudo chown -R access:access data/9router/slave/
```

### Containers não iniciam

```bash
docker compose logs 9router-master
docker compose logs 9router-slave-001
```
