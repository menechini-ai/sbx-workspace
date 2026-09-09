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
# 1. Criar pool básico (1 master + 1 slave)
python3 pool.py create

# 2. Usar a API key do master nos clientes
```

## Comandos

### pool.py create

Cria pool básico: 1 master + 1 slave, sobe containers e sincroniza.

```bash
python3 pool.py create
```

**O que faz:**
1. Reseta config.json para 1 slave
2. Gera docker-compose.yaml e .env
3. Executa `docker compose up -d --remove-orphans`
4. Aguarda containers ficarem prontos
5. Executa `sync` (health check + combos + providers + API key)

**Opções:**
```bash
python3 pool.py create --dry-run  # Simula sem alterar
```

### pool.py list

Lista a configuração atual do pool.

```bash
python3 pool.py list
```

**Saída:**
```
9ROUTER POOL
─────────────────────────────────────────────────────────────────────
Master: localhost:20128
Slaves: 1
  - rs001 → localhost:20129

Models: 2
  - claude-sonnet-5
  - claude-opus-5

Combos: 2
  - claude-opus-5 (2 models)
  - claude-sonnet-5 (2 models)
```

### pool.py sync

Sincroniza a configuração local com o master. Cria providers, connections, combos, custom models e API keys.

```bash
python3 pool.py sync
```

**O que faz:**
1. Verifica saúde do slave antes de configurar
2. Cria API keys nos slaves
3. Cria combos nos slaves (com verificação)
4. Remove combos existentes no master
5. Cria provider nodes no master
6. Cria provider connections no master
7. Cria custom models no master
8. Cria combos no master
9. Configura round-robin
10. Exporta a API key do master

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
python3 pool.py test
```

**Saída:**
```
9ROUTER POOL TEST
─────────────────────────────────────────────────────────────────────
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
python3 pool.py scale 1      # 1 slave (padrão)
python3 pool.py scale 3      # 3 slaves
python3 pool.py scale 6      # 6 slaves
python3 pool.py scale 10     # 10 slaves
python3 pool.py scale 15     # 15 slaves (máximo)
```

**O que faz:**
1. Gera `docker-compose.yaml` com N slaves
2. Gera `.env` com portas (20129-20128+N)
3. Atualiza `config.json`
4. Executa `docker compose up -d --remove-orphans`
5. Remove volumes órfãos ao reduzir
6. Executa `sync`

**Opções:**
```bash
python3 pool.py scale 6 --dry-run    # Simular sem alterar
python3 pool.py scale 6 --no-sync    # Não sincronizar após criar
```

### pool.py slave add

Adiciona um slave manualmente.

```bash
python3 pool.py slave add rs004 localhost:20132 --docker-host 9router-slave-004:20132
```

### pool.py slave delete

Remove um slave.

```bash
python3 pool.py slave delete rs004
```

### pool.py backup

Faz backup da configuração do master.

```bash
python3 pool.py backup
python3 pool.py backup --output backup.json
```

### pool.py clean

Remove tudo: containers, dados, configs. **Não recria nada.**

```bash
python3 pool.py clean           # Remove tudo
python3 pool.py clean --dry-run # Simula sem alterar
```

**O que faz:**
1. `docker compose down -v --remove-orphans` — para e remove todos os containers e volumes
2. Reseta `config.json` para 1 slave
3. Gera `docker-compose.yaml` e `.env` para 1 slave

**Depois rode:** `python3 pool.py create` para recriar ou `python3 pool.py sync` para configurar

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

Após rodar `python3 pool.py create` ou `python3 pool.py sync`, use a API key exportada:

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
| `docker-compose.yaml` | Definição dos containers (gerado) |
| `.env` | Variáveis de ambiente (gerado) |
| `torrc` | Configuração do Tor proxy |

## Troubleshooting

### Provider não conecta ao slave

```bash
python3 pool.py test
```

Verifique se todos os slaves estão SAUDÁVEL.

### Combo não aparece no master

```bash
python3 pool.py sync
```

Re-sincroniza a configuração.

### Containers não iniciam

```bash
docker compose logs 9router-master
docker compose logs 9router-slave-001
```

### Limpar tudo e recomeçar

```bash
python3 pool.py clean
python3 pool.py create
```
