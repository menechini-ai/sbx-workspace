# Guia de Instalação e Uso

Este projeto configura um ambiente de desenvolvimento com **memória de longo prazo** (ai-memory) para agentes de IA (Claude Code e OpenCode), permitindo continuidade entre sessões e troca de contexto entre diferentes agentes. Inclui **9Router** como gateway gratuito de API IA com 1 master + 3 slaves.

---

## Pré-requisitos

- **Docker** e **Docker Compose** instalados
- **Chave de API Anthropic** (para Claude Code/OpenCode)
- **Git** configurado (para commits automáticos)
- **9Router** (opcional - gateway gratuito de API IA, rodando como containers slave/master). Veja [`scripts/9router/README.md`](scripts/9router/README.md).

---

## Configuração Inicial

### 1. Clone e configure variáveis de ambiente

```bash
# Clone o repositório
git clone <seu-repo>
cd <seu-repo>

# Copie o arquivo de exemplo
cp .env-example .env

# Edite com suas chaves
nano .env
```

### 2. Configure o `.env`

```bash
# Obrigatório: Chave da Anthropic (ou use 9Router como gateway gratuito)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Opcional: Token do ai-memory (padrão: seu_token_super_seguro)
AI_MEMORY_AUTH_TOKEN=seu_token_super_seguro

# Opcional: Modelo padrão (padrão: claude-sonnet-4-8)
ANTHROPIC_MODEL=claude-sonnet-4-8

# 9Router (gateway gratuito de IA) - usa containers slave como providers
# O master roda na porta 20128, slaves nas 20129-20131
# Configure no 9Router dashboard: http://localhost:20128/dashboard
# Veja scripts/9router/README.md para guia completo de configuração
ROUTER_PORT_MASTER=20128
ROUTER_PORT_SLAVE_001=20129
ROUTER_PORT_SLAVE_002=20130
ROUTER_PORT_SLAVE_003=20131
```

---

## Comandos Principais (via Makefile)

```bash
# Construir a imagem base compartilhada (execute uma vez)
make build-base

# Construir todas as imagens dos agentes
make build

# Iniciar servidor de memória (background)
make up

# Iniciar 9Router (master + 3 slaves) - gateway IA gratuito
make 9router-up

# Iniciar Claude Code com memória
make cc

# Iniciar OpenCode com memória
make code

# Ver logs do servidor de memória
make logs

# Ver logs do 9Router
make 9router-logs

# Parar tudo
make down

# Parar 9Router
make 9router-down

# Limpeza completa (remove volumes)
make clean

# Rebuild total
make rebuild
```

---

## 9Router — Gateway IA Gratuito

O 9Router roda como containers Docker (1 master + 3 slaves) e fornece um gateway gratuito para APIs de IA:

- **Master** (porta 20128): Dashboard + API principal, roteia requisições para slaves
- **Slaves** (portas 20129-20131): Providers reais, recursos limitados (256MB RAM, 0.5 CPU)
- **Dashboard**: http://localhost:20128/dashboard

**Configuração completa:** Veja [`scripts/9router/README.md`](scripts/9router/README.md) para guia passo a passo.

### Integração com ai-memory, Claude Code e OpenCode

Os agentes (Claude Code, OpenCode) podem usar o 9Router como endpoint da Anthropic:

```bash
# Configure no .env para usar 9Router local
ANTHROPIC_BASE_URL=http://host.docker.internal:20128/v1
ANTHROPIC_API_KEY=not-needed  # 9Router não exige key válida
```

O 9Router master distribui carga entre os 3 slaves automaticamente via Round Robin.

### Comandos 9Router

```bash
# Subir 9Router (master + 3 slaves)
make 9router-up

# Ver logs
make 9router-logs

# Parar
make 9router-down

# Acessar dashboard
open http://localhost:20128/dashboard
```

### Configuração dos Providers (Master → Slaves)

Para que o master roteie requests para os slaves, é necessário criar providers no dashboard:

1. Acesse `http://localhost:20128/dashboard/providers`
2. Clique em **"Add Provider"** → **"Anthropic Compatible"**
3. Para cada slave, preencha:

| Campo | Slave-001 | Slave-002 | Slave-003 |
|-------|-----------|-----------|-----------|
| Name | rs001 | rs002 | rs003 |
| API Key | sk-0de3e4a71ffae2e1-... | sk-a1eed18320e1407e-... | sk-84e6135c711c53f1-... |
| Prefix | rs001 | rs002 | rs003 |
| Base URL | http://9router-slave-001:20129/v1 | http://9router-slave-002:20130/v1 | http://9router-slave-003:20131/v1 |
| Node Name | rs001 | rs002 | rs003 |
| Default Model | opencode-thinking-tools | opencode-thinking-tools | opencode-thinking-tools |
| Priority | 1 | 2 | 3 |

**Importante:** Cada slave precisa de um UUID de provider DIFERENTE (gerado automaticamente ao criar via dashboard).

Para detalhes completos, veja [`scripts/9router/README.md`](scripts/9router/README.md).

---

## Como Funciona a Memória

### Servidor ai-memory
- Roda na porta **49374** (interno: `http://ai-memory:49374`)
- Armazena wiki em `~/.ai-memory` (host) / `/data` (container)
- Interface web: `http://localhost:49374/web` (se exposto)

### Modo Gerenciado (`ai-memory run <agent>`)
Ao executar `make cc` ou `make code`:
1. Conecta ao servidor ai-memory automaticamente
2. Instala **lifecycle hooks** para capturar observações
3. Configura **MCP** (Model Context Protocol) para ferramentas de memória
4. Permite **handoffs cross-agent**: saia do Claude, continue no OpenCode
5. Resume sessões nativas automaticamente

---

## Fluxo de Trabalho Recomendado

### Sessão única (Claude Code)
```bash
make up      # Inicia servidor ai-memory (uma vez)
make 9router-up  # Inicia 9Router (opcional, para IA gratuita)
make cc      # Abre Claude Code com memória
# ... trabalha ...
exit         # Sai do Claude - handoff salvo automaticamente
```

### Trocar de agente (Claude → OpenCode)
```bash
make cc      # Claude Code
# ... trabalha, depois sai ...
make code    # OpenCode retoma onde parou (handoff automático)
```

### Continuar depois de dias
```bash
make up      # Garante servidor rodando
make cc      # Nova sessão - recebe briefing do último trabalho
```

---

## Estrutura do Projeto

```
.
├── docker-compose.yaml          # Orquestração dos serviços (ai-memory, opencode, claude-code)
├── Makefile                     # Comandos de conveniência
├── .env                         # Suas chaves (não versionar!)
├── .env-example                 # Template
├── scripts/
│   ├── base/Dockerfile          # Imagem base compartilhada
│   ├── claude-code/
│   │   ├── Dockerfile           # Extende base + claude-code + plugins
│   │   └── entrypoint.sh        # ai-memory run claude
│   ├── opencode/
│   │   ├── Dockerfile           # Extende base + opencode-ai
│   │   └── entrypoint.sh        # ai-memory run opencode
│   └── 9router/
│       ├── docker-compose.yaml  # 9Router: master + 3 slaves (IA gratuita)
│       ├── .env                 # Config do 9Router
│       ├── README.md            # Guia completo de configuração
│       └── get-api-keys.sh      # Script de gerenciamento de API keys
└── workspace/                   # Seu código (montado em /workspace)
    ├── CLAUDE.md                # Instruções para Claude
    ├── .claude/skills/          # Skills do ai-memory
    └── .agents/skills/          # Skills adicionais
```

---

## Personalização

### Adicionar nova skill ao Claude Code
```bash
# No container do Claude Code (após make cc)
claude plugin install <nome-do-plugin>@claude-plugins-official
```

### Alterar modelo padrão
```bash
# No .env ou exportando antes do make
export ANTHROPIC_MODEL=claude-opus-4-8
make cc
```

### Expor interface web do ai-memory
Edite `docker-compose.yaml`:
```yaml
services:
  ai-memory:
    ports:
      - "49374:49374"  # Já exposto por padrão
```
Acesse: `http://localhost:49374/web` (use token como senha no Basic Auth)

### Usar 9Router como provider dos agentes
Para usar o 9Router em vez da Anthropic diretamente, configure no `.env`:
```bash
# Redireciona chamadas Anthropic para o 9Router local
ANTHROPIC_BASE_URL=http://host.docker.internal:20128/v1
# 9Router não exige key válida, mas o campo precisa existir
ANTHROPIC_API_KEY=not-needed
```
O 9Router master roteia automaticamente para os 3 slaves via Round Robin.

**Documentação completa:** Veja [`scripts/9router/README.md`](scripts/9router/README.md) para guia passo a passo de configuração de providers, combos e Round Robin.

---

## Troubleshooting

### "ai-memory não conecta"
```bash
# Verifique se servidor subiu
make logs

# Teste conexão manual
docker exec -it opencode ai-memory status
```

### "Permissão negada em volumes"
```bash
# Ajuste permissões no host
sudo chown -R $USER:$USER ~/.ai-memory .opencode .claude
```

### "Imagem base não encontrada"
```bash
# Force rebuild da base
make build-base
make build
```

### "Token inválido"
Verifique se `AI_MEMORY_AUTH_TOKEN` no `.env` bate com o do servidor ai-memory.

### "9Router não inicia"
```bash
# Verifique logs do 9Router
make 9router-logs

# Verifique se o .env do 9Router existe
cat scripts/9router/.env

# Reinicie
make 9router-down && make 9router-up
```

### "Slaves 9Router com poucos recursos"
Os slaves têm 256MB RAM e 0.5 CPU (metade do master). Para ajustar, edite `scripts/9router/docker-compose.yaml` e mude os limites em `x-service-slave`.

### "Round Robin não funciona"
Verifique se as settings foram aplicadas. Veja [`scripts/9router/README.md`](scripts/9router/README.md) para configuração completa.

### "Provider 9Router não roda requests"
Cada slave precisa de um UUID de provider DIFERENTE. Se todos apontam para o mesmo slave, delete e recrie via dashboard. Veja [`scripts/9router/README.md`](scripts/9router/README.md) para detalhes.

### "Combo não aparece no master"
Verifique se combos foram criados com o mesmo nome usado nos slaves. Veja [`scripts/9router/README.md`](scripts/9router/README.md).

---

## Arquitetura

```
┌─────────────────┐     ┌──────────────────┐
│   ai-memory     │◄────│  Claude Code     │
│   (servidor)    │     │  (managed run)   │
│   porta 49374   │     └──────────────────┘
│   volumes:      │
│   ~/.ai-memory  │     ┌──────────────────┐
└─────────────────┘     │    OpenCode      │
                        │  (managed run)   │
                        └──────────────────┘
              ▲                    ▲
              │                    │
              ▼                    ▼
      ┌───────────────┐    ┌───────────────┐
      │ Wiki markdown │    │ Sessões nativas│
      │ + SQLite      │    │ + Handoffs    │
      └───────────────┘    └───────────────┘


┌──────────────────────────────────────────────────────────────┐
│                      9Router Cluster                         │
│  ┌──────────────┐    ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │   MASTER     │───►│ SLAVE 1  │ │ SLAVE 2  │ │ SLAVE 3  │  │
│  │  port 20128  │    │ 20129    │ │ 20130    │ │ 20131    │  │
│  │  512MB/1CPU  │    │ 256MB/0.5│ │ 256MB/0.5│ │ 256MB/0.5│  │
│  │ Dashboard    │    │ rs001    │ │ rs002    │ │ rs003    │  │
│  │ Round Robin  │    │ Prio: 1  │ │ Prio: 2  │ │ Prio: 3  │  │
│  └──────────────┘    └──────────┘ └──────────┘ └──────────┘  │
│         ▲                                              │      │
│         │                    ▲                          │      │
│         └────────────────────┼──────────────────────────┘      │
│                              ▼                                 │
│              ┌───────────────────────────────┐                │
│              │  ANTHROPIC_BASE_URL=          │                │
│              │  http://host.docker.internal: │                │
│              │  20128/v1                     │                │
│              └───────────────────────────────┘                │
└──────────────────────────────────────────────────────────────┘

Documentação completa: scripts/9router/README.md
```

---

## Recursos Avançados

### Sessions gerenciadas (`ai-memory run`)
```bash
# Lista workstreams disponíveis
ai-memory workstreams

# Continua última sessão ativa
ai-memory continue

# Nova sessão limpa no mesmo workstream
ai-memory run --fresh claude
```

### Escrita manual de páginas duráveis
```bash
# No agente: "salve uma nota permanente que decidimos usar Postgres"
# Ou via CLI:
ai-memory write-page --path decisions/001-db.md --body "# Decisão\n\nUsar Postgres..." --pinned
```

### Backup/Restaurar
```bash
# Backup completo
ai-memory backup

# Listar checkpoints
ai-memory checkpoints

# Restaurar página específica
ai-memory restore-page --path decisions/001-db.md --from <commit-hash>
```

---

## Referências

- [ai-memory GitHub](https://github.com/akitaonrails/ai-memory)
- [Documentação oficial](https://github.com/akitaonrails/ai-memory/tree/main/docs)
- [MCP Specification](https://modelcontextprotocol.io/)
- [Claude Code Docs](https://docs.anthropic.com/claude-code)
- [OpenCode Docs](https://opencode.ai/docs)
- [9Router Setup](scripts/9router/README.md) — Guia completo de configuração master/slave com providers, combos e Round Robin