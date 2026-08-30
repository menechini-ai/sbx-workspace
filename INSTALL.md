# Guia de Instalação e Uso

Este projeto configura um ambiente de desenvolvimento com **memória de longo prazo** (ai-memory) para agentes de IA (Claude Code e OpenCode), permitindo continuidade entre sessões e troca de contexto entre diferentes agentes.

---

## Pré-requisitos

- **Docker** e **Docker Compose** instalados
- **Chave de API Anthropic** (para Claude Code/OpenCode)
- **Git** configurado (para commits automáticos)

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
# Obrigatório: Chave da Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx

# Opcional: Token do ai-memory (padrão: seu_token_super_seguro)
AI_MEMORY_AUTH_TOKEN=seu_token_super_seguro

# Opcional: Modelo padrão (padrão: claude-sonnet-4-8)
ANTHROPIC_MODEL=claude-sonnet-4-8
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

# Iniciar Claude Code com memória
make run

# Iniciar OpenCode com memória
make code

# Ver logs do servidor de memória
make logs

# Parar tudo
make down

# Limpeza completa (remove volumes)
make clean

# Rebuild total
make rebuild
```

---

## Como Funciona a Memória

### Servidor ai-memory
- Roda na porta **49374** (interno: `http://ai-memory:49374`)
- Armazena wiki em `~/.ai-memory` (host) / `/data` (container)
- Interface web: `http://localhost:49374/web` (se exposto)

### Modo Gerenciado (`ai-memory run <agent>`)
Ao executar `make run` ou `make code`:
1. Conecta ao servidor ai-memory automaticamente
2. Instala **lifecycle hooks** para capturar observações
3. Configura **MCP** (Model Context Protocol) para ferramentas de memória
4. Permite **handoffs cross-agent**: saia do Claude, continue no OpenCode
5. Resume sessões nativas automaticamente

---

## Fluxo de Trabalho Recomendado

### Sessão única (Claude Code)
```bash
make up      # Inicia servidor (uma vez)
make run     # Abre Claude Code com memória
# ... trabalha ...
exit         # Sai do Claude - handoff salvo automaticamente
```

### Trocar de agente (Claude → OpenCode)
```bash
make run     # Claude Code
# ... trabalha, depois sai ...
make code    # OpenCode retoma onde parou (handoff automático)
```

### Continuar depois de dias
```bash
make up      # Garante servidor rodando
make run     # Nova sessão - recebe briefing do último trabalho
```

---

## Estrutura do Projeto

```
.
├── docker-compose.yaml          # Orquestração dos serviços
├── Makefile                     # Comandos de conveniência
├── .env                         # Suas chaves (não versionar!)
├── .env-example                 # Template
├── scripts/
│   ├── base/Dockerfile          # Imagem base compartilhada
│   ├── claude-code/
│   │   ├── Dockerfile           # Extende base + claude-code + plugins
│   │   └── entrypoint.sh        # ai-memory run claude
│   └── opencode/
│       ├── Dockerfile           # Extende base + opencode-ai
│       └── entrypoint.sh        # ai-memory run opencode
└── workspace/                   # Seu código (montado em /workspace)
    ├── CLAUDE.md                # Instruções para Claude
    ├── .claude/skills/          # Skills do ai-memory
    └── .agents/skills/          # Skills adicionais
```

---

## Personalização

### Adicionar nova skill ao Claude Code
```bash
# No container do Claude Code (após make run)
claude plugin install <nome-do-plugin>@claude-plugins-official
```

### Alterar modelo padrão
```bash
# No .env ou exportando antes do make
export ANTHROPIC_MODEL=claude-opus-4-8
make run
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