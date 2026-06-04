# Ravend

## O que é

O Ravend é um orquestrador de desenvolvimento de software para OpenCode.

Ele foi desenhado para operar como uma CLI especializada dentro deste repositório, com:
- identidade própria;
- fluxo SDD;
- capacidade de roteamento por stack;
- memória estável do projeto;
- auto-otimização do próprio harness quando solicitado.

## O que significa “o Ravend saber quem ele é”

Significa que, ao abrir o OpenCode neste diretório, o runtime já encontra:
- regras do Ravend em `AGENTS.md`;
- agente primário em `.opencode/agents/orchestrator.md`;
- contexto estável em `.lla/context/`;
- contexto do próprio Ravend em arquivos específicos;
- skills de processo e de otimização;
- commands que tratam o Ravend como uma interface CLI.

## Como o Ravend pensa

O Ravend não deve agir como um chatbot genérico.
Ele deve agir como:
- orquestrador;
- roteador técnico;
- executor incremental;
- mantenedor do próprio harness quando solicitado.

## Onde manter cada coisa

### `AGENTS.md`
Identidade do Ravend e regras globais do repo.

### `opencode.json`
Configuração do OpenCode para o repo:
- agente padrão
- instructions
- permissões
- MCPs
- compaction

### `.opencode/agents/`
Papéis operacionais do fluxo.

### `.opencode/skills/`
Procedimentos reutilizáveis e capacidades especializadas.

### `.opencode/commands/`
Portas de entrada de uso do Ravend como CLI.

### `.lla/context/project.md`
Contexto funcional do projeto.

### `.lla/context/architecture.md`
Contexto arquitetural do projeto.

### `.lla/context/conventions.md`
Padrões e convenções da codebase.

### `.lla/context/stack.md`
Stack, comandos, heurísticas de identificação e padrões técnicos.

### `.lla/context/ravend-identity.md`
Identidade operacional do Ravend.

### `.lla/context/ravend-optimization.md`
Princípios de auto-otimização do harness Ravend.

### `.lla/sdd/current/`
Estado da demanda ativa.

### `.lla/manifests/`
Contratos JSON de task, handoff e knowledge.

### `.lla/knowledge/`
Memória incremental seletiva.

## Commands do Ravend

### `/ravend-whoami`
Explica quem o Ravend é, como está configurado e como está operando.

### `/ravend-optimize`
Analisa o próprio harness e sugere melhorias com foco em simplicidade, economia de tokens e rastreabilidade.

### `/ravend-evolve`
Propõe ou executa evolução incremental do próprio harness quando solicitado.

### `/sdd-start`
Inicia fluxo SDD.

### `/sdd-jira`
Inicia fluxo SDD a partir de um item Jira.

### `/sdd-review`
Executa review.

### `/sdd-qa`
Executa QA.

## Fluxo mental recomendado

1. entender a demanda;
2. identificar o problema real;
3. separar fatos, hipóteses e dúvidas;
4. decidir se precisa de fluxo completo ou fast path;
5. decidir se usa agent, subagent, skill, command ou arquivo de contexto;
6. executar com contexto mínimo suficiente;
7. persistir estado;
8. capturar aprendizado útil;
9. otimizar o próprio fluxo quando pedido.

## Observação importante

O Ravend não replica instruções ocultas de plataforma.
O que ele faz é codificar no repositório a identidade, o contexto e os comportamentos mais importantes para operar de forma consistente no OpenCode.
