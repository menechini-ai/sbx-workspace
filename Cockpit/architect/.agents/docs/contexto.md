# Contexto do Projeto

## Estrutura
- `scripts/` - Infraestrutura Docker (ai-memory, 9router, omniroute)
- `workspace/` - Código isolado (montado em containers)
- `Cockpit/` - Configuração dos agentes
- `Vault/` - Memória persistente

## Serviços
- ai-memory: Servidor de memória (porta 49374)
- 9router: Gateway IA gratuito (master + 3 slaves)
- omniroute: Alternativa ao 9Router

## Rede
- clawbox-net: Rede Docker compartilhada

## Convenções
- Symlinks de workspace/ para Cockpit/
- Vault/ gitignored
- Skills no formato Agent Skills