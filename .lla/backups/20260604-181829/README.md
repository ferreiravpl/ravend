# Ravend — Orquestrador SDD para OpenCode

## Visão geral

O Ravend é um workspace local de orquestração para OpenCode focado em desenvolvimento de software com:

- SDD como fluxo padrão;
- agentes com papéis estáveis;
- skills com especialização por stack;
- manifests JSON para handoff objetivo;
- memória incremental em arquivos.

A ideia central é simples:

- **agentes** resolvem responsabilidades do fluxo;
- **skills** resolvem especialização técnica;
- **manifests** reduzem ambiguidade;
- **knowledge** evita repetição de erro;
- **planner** decide o que carregar e quem chamar.

## Decisão arquitetural principal

O Ravend não cria muitos agentes especializados logo no começo.

Em vez disso:

- `implementer` continua sendo o papel de implementação;
- `reviewer` continua sendo o papel de revisão;
- `planner` identifica a stack dominante;
- o agente certo carrega a skill certa.

Hoje as stacks priorizadas são:

- Quarkus
- Spring
- Angular

## Por que isso existe

Porque os problemas mais comuns em fluxos agentic são:

- contexto demais;
- delegação ruim;
- prompts monolíticos;
- pouca continuidade entre sessões;
- repetição dos mesmos erros.

O Ravend tenta resolver isso com:

- estado persistido;
- handoff explícito;
- especialização sob demanda;
- knowledge indexada;
- fluxo mínimo viável.

## Estrutura principal

    .
    ├── AGENTS.md
    ├── README.md
    ├── opencode.json
    ├── .opencode/
    │   ├── agents/
    │   ├── commands/
    │   └── skills/
    └── .lla/
        ├── context/
        ├── templates/
        ├── manifests/
        ├── knowledge/
        └── sdd/current/

## Diretórios

### `.opencode/agents/`
Papéis do workflow.

### `.opencode/commands/`
Entradas de fluxo.

### `.opencode/skills/`
Procedimentos reutilizáveis e especialização técnica.

### `.lla/context/`
Contexto estável do projeto.

### `.lla/templates/`
Modelos de artefatos.

### `.lla/manifests/`
Contratos operacionais em JSON.

### `.lla/knowledge/`
Aprendizado incremental seletivo.

### `.lla/sdd/current/`
Estado atual da entrega em andamento.

## Papéis dos agentes

### `orchestrator`
Coordena o fluxo e escolhe o menor caminho seguro.

### `intake`
Transforma demanda bruta em contexto inicial.

### `spec-writer`
Produz PRD e tech spec.

### `planner`
Identifica stack, escolhe skills, define plano mínimo.

### `task-decomposer`
Quebra em tarefas pequenas.

### `implementer`
Implementa uma tarefa por vez.

### `qa`
Valida com testes e build.

### `reviewer`
Revisa qualidade, aderência e risco.

### `knowledge-curator`
Transforma findings recorrentes em conhecimento reutilizável.

## Especialização por stack

O planner deve responder:

- a mudança é Quarkus?
- é Spring?
- é Angular?
- é full stack?
- o foco é implementação ou review?

Com isso, ele aciona skills como:

- `quarkus-implementation`
- `quarkus-review`
- `spring-implementation`
- `spring-review`
- `angular-implementation`
- `angular-review`

## Fluxo resumido

1. entrada
2. intake
3. PRD
4. tech spec
5. tasks
6. implementação
7. QA
8. review
9. captura de conhecimento
10. aceite

## Manutenção

### Mude `AGENTS.md` quando
- mudar política global;
- mudar roteamento;
- mudar regra do fluxo.

### Mude `.opencode/skills/` quando
- mudar padrão técnico;
- surgir erro recorrente;
- surgir nova convenção da stack.

### Mude `.lla/context/` quando
- mudar arquitetura;
- mudar stack;
- mudar convenções;
- mudar comandos de build/teste.

### Mude `.lla/manifests/` quando
- mudar contrato de handoff;
- mudar contrato da task;
- mudar taxonomia da knowledge.

## Direção futura

O próximo crescimento natural é:

- refinar as skills por stack com padrões da tua codebase real;
- enriquecer a knowledge por framework e camada;
- talvez criar poucos especialistas reais no futuro, mas só onde houver dor comprovada.
