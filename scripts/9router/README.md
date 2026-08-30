# 9Router Multi-Instance Setup

Guia completo para configurar 9Router com 1 Master + 3 Slaves usando Round Robin load balancing.

## Por que isso importa

9Router é um gateway de API que roteia requests entre múltiplos provedores de IA. Configurar um master com múltiplos slaves permite:

- **Round Robin**: Distribuir requests entre 3 slaves para evitar rate limits
- **Failover**: Se um slave cai, o próximo assume automaticamente
- **Centralização**: Clientes conectam apenas no master (porta 20128)

```
┌─────────────────────────────────────────────────────────┐
│                      CLIENTS                            │
│                    (OpenCode, etc.)                      │
└──────────────────────┬──────────────────────────────────┘
                       │ API Key do Master
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  9ROUTER MASTER                         │
│               http://localhost:20128                    │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  rs001      │  │  rs002      │  │  rs003      │     │
│  │  Priority:1 │  │  Priority:2 │  │  Priority:3 │     │
│  │  ─────────  │  │  ─────────  │  │  ─────────  │     │
│  │  baseUrl:   │  │  baseUrl:   │  │  baseUrl:   │     │
│  │  slave-001  │  │  slave-002  │  │  slave-003  │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
└─────────┼────────────────┼────────────────┼─────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ SLAVE-001   │  │ SLAVE-002   │  │ SLAVE-003   │
│ Port: 20129 │  │ Port: 20130 │  │ Port: 20131 │
└─────────────┘  └─────────────┘  └─────────────┘
```

## Pré-requisitos

- Docker + Docker Compose instalados
- Containers na rede `clawbox-net` (criada pelo docker-compose)
- Acesso ao dashboard em `http://localhost:20128/dashboard`

## Passo 1 — Subir os Containers

```bash
cd scripts/9router
docker compose up -d
```

| Serviço | Container | Porta | Função |
|---------|-----------|-------|--------|
| master | clawbox-9router-master | 20128 | Gateway principal |
| slave-001 | clawbox-9router-slave-001 | 20129 | Backend 1 |
| slave-002 | clawbox-9router-slave-002 | 20130 | Backend 2 |
| slave-003 | clawbox-9router-slave-003 | 20131 | Backend 3 |

## Passo 2 — Criar API Keys

Cada instância precisa de sua própria API key para autenticar requests.

```bash
# Criar keys em todas as instâncias de uma vez
./get-api-keys.sh -c "default"

# Listar keys criadas
./get-api-keys.sh -l

# Testar se as keys funcionam
./get-api-keys.sh -t
```

**Resultado esperado:**

| Instância | API Key | Uso |
|-----------|---------|-----|
| master | `sk-1592f4d063b197d2-i3kofi-7b4407d5` | Clientes conectam aqui |
| slave-001 | `sk-0de3e4a71ffae2e1-sso8a2-bcdb10df` | Master conecta aqui |
| slave-002 | `sk-a1eed18320e1407e-zl4na1-aa967696` | Master conecta aqui |
| slave-003 | `sk-84e6135c711c53f1-pyyjma-c0061ae8` | Master conecta aqui |

**Por que isso é necessário:** O master usa a API key do slave para autenticar requests que envia a ele. Sem a key, o slave rejeita o request.

## Passo 3 — Criar Combos nos Slaves

Combos são grupos de modelos que rodam em Round Robin. Criar em **cada slave** (portas 20129, 20130, 20131).

```bash
# Login no slave (exemplo: slave-001)
curl -s -c /tmp/cookies.txt -X POST http://127.0.0.1:20129/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"123456"}'

# Combo 1: opencode-thinking-tools (3 modelos free)
curl -s -b /tmp/cookies.txt -X POST http://127.0.0.1:20129/api/combos \
  -H "Content-Type: application/json" \
  -d '{
    "name": "opencode-thinking-tools",
    "models": [
      "oc/deepseek-v4-flash-free",
      "oc/mimo-v2.5-free",
      "oc/nemotron-3-ultra-free"
    ]
  }'

# Combo 2: opencode-basic (2 modelos free)
curl -s -b /tmp/cookies.txt -X POST http://127.0.0.1:20129/api/combos \
  -H "Content-Type: application/json" \
  -d '{
    "name": "opencode-basic",
    "models": [
      "oc/nemotron-3.5-lightning-free",
      "oc/muse-spark-1.2-contributor-free"
    ]
  }'
```

Repetir para cada slave (portas 20130 e 20131).

**Modelos OpenCode Free disponíveis:**

| Modelo | Tipo |
|--------|------|
| `oc/deepseek-v4-flash-free` | Raciocínio |
| `oc/mimo-v2.5-free` | Raciocínio |
| `oc/nemotron-3-ultra-free` | Raciocínio |
| `oc/nemotron-3.5-lightning-free` | Básico |
| `oc/muse-spark-1.2-contributor-free` | Básico |

**Por que combos:** O Round Robin funciona dentro do combo. Se um modelo falha, o próximo da lista assume.

## Passo 4 — Configurar Round Robin nos Slaves

```bash
curl -s -b /tmp/cookies.txt -X PATCH http://127.0.0.1:20129/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "comboStrategy": "round-robin",
    "comboStickyRoundRobinLimit": 3,
    "stickyRoundRobinLimit": 3,
    "fallbackStrategy": "round-robin"
  }'
```

Repetir para cada slave (20130 e 20131).

**O que cada setting faz:**

| Setting | Valor | Significado |
|---------|-------|-------------|
| `comboStrategy` | `round-robin` | Roda entre os modelos do combo |
| `comboStickyRoundRobinLimit` | `3` | Mantém cliente no mesmo modelo por 3 requests |
| `stickyRoundRobinLimit` | `3` | Mantém cliente no mesmo provider por 3 requests |
| `fallbackStrategy` | `round-robin` | Se falha, tenta o próximo em round-robin |

## Passo 5 — Criar Providers no Master (CRÍTICO)

### Regra Importante

**Cada slave precisa de um provider type UUID DIFERENTE.**

Se você usar o mesmo UUID para múltiplos slaves, o `providerSpecificData` (prefix, baseUrl, nodeName) será sobrescrito e todos apontarão para o mesmo slave.

### Passo 5.1 — Criar Provider via Dashboard

1. Acesse: `http://localhost:20128/dashboard/providers`
2. Clique em **"Add Provider"**
3. Selecione **"Anthropic Compatible"**
4. Preencha:
   - **Name**: `rs001`
   - **API Key**: `sk-0de3e4a71ffae2e1-sso8a2-bcdb10df` (key do slave-001)
5. Salve — um UUID será gerado automaticamente

### Passo 5.2 — Configurar Customization

Na página do provider criado, preencha:

| Campo | Valor | Por que |
|-------|-------|---------|
| Prefix | `rs001` | Identifica modelos deste slave |
| Base URL | `http://9router-slave-001:20129/v1` | Endpoint do slave |
| Node Name | `rs001` | Nome do nó no cluster |
| Default Model | `opencode-thinking-tools` | Combo padrão |
| Priority | `1` | Prioridade (menor = mais usado) |

### Passo 5.3 — Repetir para cada Slave

| Slave | Name | API Key | Prefix | Base URL | Priority |
|-------|------|---------|--------|----------|----------|
| 001 | rs001 | `sk-0de3e4a71ffae2e1-...` | rs001 | `http://9router-slave-001:20129/v1` | 1 |
| 002 | rs002 | `sk-a1eed18320e1407e-...` | rs002 | `http://9router-slave-002:20130/v1` | 2 |
| 003 | rs003 | `sk-84e6135c711c53f1-...` | rs003 | `http://9router-slave-003:20131/v1` | 3 |

**Cada criação gera um UUID diferente:**

```
rs001: anthropic-compatible-4204be8f-51d8-44e4-bfa6-c92e5429ebbf
rs002: anthropic-compatible-c81adce8-ee2f-4e15-bf57-a2088303ea27
rs003: anthropic-compatible-65a56d84-b579-4649-83b0-9f8f78993578
```

**Por que UUIDs diferentes:** O 9Router usa o UUID para identificar cada provider. Se dois slaves compartilham o mesmo UUID, as configurações conflitam.

## Passo 6 — Criar Combos no Master

O master precisa dos mesmos combos que os slaves, para que saiba quais modelos estão disponíveis.

```bash
# Login no master
curl -s -c /tmp/cookies_master.txt -X POST http://127.0.0.1:20128/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"123456"}'

# Combo 1
curl -s -b /tmp/cookies_master.txt -X POST http://127.0.0.1:20128/api/combos \
  -H "Content-Type: application/json" \
  -d '{
    "name": "opencode-thinking-tools",
    "models": [
      "oc/deepseek-v4-flash-free",
      "oc/mimo-v2.5-free",
      "oc/nemotron-3-ultra-free"
    ]
  }'

# Combo 2
curl -s -b /tmp/cookies_master.txt -X POST http://127.0.0.1:20128/api/combos \
  -H "Content-Type: application/json" \
  -d '{
    "name": "opencode-basic",
    "models": [
      "oc/nemotron-3.5-lightning-free",
      "oc/muse-spark-1.2-contributor-free"
    ]
  }'
```

## Passo 7 — Configurar Round Robin no Master

```bash
curl -s -b /tmp/cookies_master.txt -X PATCH http://127.0.0.1:20128/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "comboStrategy": "round-robin",
    "comboStickyRoundRobinLimit": 3,
    "stickyRoundRobinLimit": 3,
    "fallbackStrategy": "round-robin"
  }'
```

## Verificação Final

```bash
# Testar request via master
curl -s -H "Authorization: Bearer sk-1592f4d063b197d2-i3kofi-7b4407d5" \
  -X POST http://127.0.0.1:20128/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"opencode-thinking-tools",
    "messages":[{"role":"user","content":"Say hello"}],
    "max_tokens":20
  }'
```

**Resultado esperado:** Response com `"choices"[0]["message"]["content"]` contendo a resposta do modelo.

## Endpoints

| Endpoint | URL | Uso |
|----------|-----|-----|
| Master API | `http://localhost:20128/v1` | Clientes conectam aqui |
| Master Dashboard | `http://localhost:20128/dashboard` | Configuração |
| Slave-001 API | `http://localhost:20129/v1` | Acesso direto (debug) |
| Slave-002 API | `http://localhost:20130/v1` | Acesso direto (debug) |
| Slave-003 API | `http://localhost:20131/v1` | Acesso direto (debug) |

## Troubleshooting

### Provider não roda requests para o slave

**Causa provável:** Todos os providers estão usando o mesmo UUID.

**Como verificar:**
```bash
curl -s -b /tmp/cookies_master.txt http://127.0.0.1:20128/api/providers | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data.get('connections', []):
    print(f'{c[\"name\"]}: provider={c[\"provider\"]}')"
```

**Solução:** Cada provider precisa de UUID diferente. Se estiverem iguais, delete e recrie via dashboard.

### Combo não aparece no master

**Causa provável:** Combo foi criado com nome diferente ou não foi criado.

**Como verificar:**
```bash
curl -s -b /tmp/cookies_master.txt http://127.0.0.1:20128/api/combos | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data.get('combos', []):
    print(f'{c[\"name\"]}: {len(c.get(\"models\",[]))} modelos')}"
```

**Solução:** Recriar o combo com o mesmo nome usado nos slaves.

### Round Robin não funciona

**Causa provável:** Settings não foram aplicados.

**Como verificar:**
```bash
curl -s -b /tmp/cookies_master.txt http://127.0.0.1:20128/api/settings | python3 -c "
import sys, json
data = json.load(sys.stdin)
for k, v in data.items():
    if 'combo' in k.lower() or 'round' in k.lower() or 'sticky' in k.lower():
        print(f'{k}: {v}')"
```

**Solução:** Reaplicar as settings via PATCH.

### Request retorna "Invalid model format"

**Causa provável:** Modelo não existe no combo ou combo não existe.

**Como verificar:**
```bash
# Listar modelos disponíveis
curl -s -H "Authorization: Bearer sk-1592f4d063b197d2-i3kofi-7b4407d5" \
  http://127.0.0.1:20128/v1/models | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = [m['id'] for m in data.get('data', [])]
filtered = [m for m in models if 'opencode' in m or 'thinking' in m or 'basic' in m]
for m in sorted(filtered):
    print(m)"
```

**Solução:** Usar nome exato do combo (ex: `opencode-thinking-tools`).

## Arquivos Importantes

| Arquivo | Descrição |
|---------|-----------|
| `docker-compose.yaml` | Definição dos serviços e portas |
| `.env` | Variáveis de ambiente (portas, senhas) |
| `.env-examples` | Exemplo de .env com variáveis explícitas |
| `get-api-keys.sh` | Script de gerenciamento de API keys |
| `data/9router/master/db/data.sqlite` | DB do master (providers, combos, settings) |
| `data/9router/slave/00{1,2,3}/db/data.sqlite` | DB dos slaves |
