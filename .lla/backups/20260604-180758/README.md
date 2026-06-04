# Ravend — Orquestrador SDD para OpenCode

## 1. Visão geral

O Ravend é um workspace local de orquestração para OpenCode focado em desenvolvimento de software com SDD como fluxo padrão e com especialização técnica por stack via skills, sem explodir o número de agentes.

Neste contexto, SDD significa:

1. Intake da demanda
2. PRD
3. Tech Spec
4. Task Decomposition
5. Implementação
6. QA
7. Code Review
8. Loop incremental até aceite

O objetivo do Ravend não é burocratizar toda demanda.

O objetivo é:
- ter um fluxo padrão confiável;
- permitir caminhos reduzidos quando houver contexto suficiente;
- manter contexto estável em arquivos;
- fazer handoff com baixo ruído;
- capturar aprendizado incremental;
- carregar especialização técnica só quando necessário.

---

## 2. Ideia central da arquitetura

O Ravend foi desenhado com uma decisão importante:

Papéis do workflow ficam em agentes.  
Especialização técnica fica em skills.

Isso significa:
- `implementer` continua sendo o papel de implementação;
- `reviewer` continua sendo o papel de revisão;
- `planner` continua sendo o papel de roteamento e planejamento;
- as diferenças entre Quarkus, Spring e Angular entram principalmente por skills especializadas.

Essa decisão existe para evitar:
- agentes demais;
- excesso de coordenação;
- prompt base gigante;
- sobreposição de responsabilidade;
- dificuldade de manutenção.

---

## 3. Como a especialização por stack funciona

### 3.1. O planner é o roteador técnico

O `planner` deve avaliar a codebase e a tarefa ativa para responder:
- a task é backend Java?
- ela é Quarkus ou Spring?
- é frontend Angular?
- é full stack?
- há impacto transversal entre backend e frontend?
- qual skill técnica precisa ser carregada?

O `planner` não precisa ser o maior especialista técnico do sistema.  
Ele precisa saber detectar o tipo de mudança e roteá-la corretamente.

### 3.2. Implementer e reviewer continuam genéricos como papel

Em vez de criar vários agentes logo de início como:
- `quarkus-implementer`
- `spring-implementer`
- `angular-implementer`
- `quarkus-reviewer`
- `spring-reviewer`
- `angular-reviewer`

o Ravend começa com:
- `implementer`
- `reviewer`

Esses agentes carregam skills específicas quando a stack exigir.

### 3.3. Skills técnicas são a camada de especialização

Foram adicionadas as seguintes skills:
- `quarkus-implementation`
- `quarkus-review`
- `spring-implementation`
- `spring-review`
- `angular-implementation`
- `angular-review`

Elas existem para conter:
- padrões esperados;
- checklist por stack;
- armadilhas comuns;
- pontos de revisão;
- anti-patterns;
- critérios do que observar e do que evitar.

---

## 4. Por que essa estratégia é melhor do que criar vários agentes agora

Criar muitos agentes especializados cedo demais parece organizado, mas costuma piorar o sistema.

### 4.1. Custo de manutenção
Cada agente adicional traz:
- prompt próprio;
- permissões próprias;
- comportamento próprio;
- documentação própria;
- necessidade de roteamento.

### 4.2. Risco de sobreposição
Quanto mais agentes, maior o risco de dúvida como:
- quem revisa backend Java compartilhado entre Quarkus e Spring?
- quem revisa Angular com impacto em API?
- quem revisa uma task full stack?

### 4.3. Custo de contexto
Se tudo vira agente, o sistema cresce mais rápido em complexidade do que em qualidade.

### 4.4. Evolução mais difícil
Skills são mais fáceis de ajustar, testar e substituir do que agentes inteiros.

Por isso, o Ravend usa esta estratégia:
1. papéis centrais fixos;
2. skills técnicas sob demanda;
3. planner roteando stack;
4. knowledge indexada por stack, camada e preocupação;
5. especialistas como agentes só quando a dor real aparecer.

---

## 5. Estrutura geral do repositório

Estrutura principal:

    .
    ├── AGENTS.md
    ├── README.md
    ├── opencode.json
    ├── .opencode/
    │   ├── agents/
    │   │   ├── orchestrator.md
    │   │   ├── intake.md
    │   │   ├── spec-writer.md
    │   │   ├── planner.md
    │   │   ├── task-decomposer.md
    │   │   ├── implementer.md
    │   │   ├── qa.md
    │   │   ├── reviewer.md
    │   │   └── knowledge-curator.md
    │   ├── commands/
    │   │   ├── sdd-start.md
    │   │   ├── sdd-jira.md
    │   │   ├── sdd-implement.md
    │   │   ├── sdd-qa.md
    │   │   ├── sdd-review.md
    │   │   ├── sdd-resume.md
    │   │   └── sdd-accept.md
    │   └── skills/
    │       ├── sdd-intake/
    │       ├── sdd-prd/
    │       ├── sdd-tech-spec/
    │       ├── sdd-task-decomposition/
    │       ├── sdd-implementation/
    │       ├── sdd-qa-verification/
    │       ├── sdd-review-loop/
    │       ├── sdd-knowledge-capture/
    │       ├── sdd-context-compaction/
    │       ├── quarkus-implementation/
    │       ├── quarkus-review/
    │       ├── spring-implementation/
    │       ├── spring-review/
    │       ├── angular-implementation/
    │       └── angular-review/
    └── .lla/
        ├── context/
        ├── templates/
        ├── manifests/
        ├── knowledge/
        └── sdd/current/

---

## 6. Papel de cada diretório

### 6.1. `.opencode/agents/`
Contém os papéis do workflow.

Cada arquivo define:
- quem é o agente;
- qual é sua responsabilidade;
- o que ele pode fazer;
- o que ele não deve fazer.

### 6.2. `.opencode/commands/`
Contém atalhos de entrada para fluxos comuns.

Eles não são o cérebro do sistema.  
Eles apenas iniciam fluxos com intenção clara.

### 6.3. `.opencode/skills/`
Contém procedimentos reutilizáveis.

Aqui vivem dois grupos de skill.

#### Skills de processo SDD
Exemplos:
- intake
- PRD
- spec
- decomposição
- implementação
- QA
- review
- captura de conhecimento

#### Skills de especialização técnica
Exemplos:
- implementação Quarkus
- review Quarkus
- implementação Spring
- review Spring
- implementação Angular
- review Angular

### 6.4. `.lla/context/`
Contexto estável do projeto.

### 6.5. `.lla/templates/`
Modelos de artefatos.

### 6.6. `.lla/sdd/current/`
Estado atual da demanda em andamento.

### 6.7. `.lla/manifests/`
Contratos operacionais em JSON.

### 6.8. `.lla/knowledge/`
Memória incremental indexada e carregada seletivamente.

---

## 7. O que cada agente faz

### `orchestrator`
- interpreta a solicitação;
- escolhe o menor fluxo seguro;
- decide se precisa de SDD completo ou caminho reduzido;
- aciona os agentes corretos;
- garante persistência de estado;
- aciona captura de conhecimento quando houver aprendizado reutilizável.

### `intake`
- transforma entrada bruta em demanda organizada;
- separa fatos, hipóteses e dúvidas;
- registra origem da demanda;
- prepara handoff inicial.

### `spec-writer`
- cria ou atualiza PRD;
- cria ou atualiza tech spec;
- prepara material para planejamento.

### `planner`
- identifica stack dominante;
- detecta se a mudança é Quarkus, Spring, Angular ou combinada;
- decide quais skills técnicas devem ser usadas;
- define plano mínimo viável;
- prepara handoffs claros.

### `task-decomposer`
- quebra a demanda em tarefas pequenas;
- define critérios de aceite;
- define arquivos em escopo;
- prepara `task-scope.json`.

### `implementer`
- implementa uma task por vez;
- lê apenas contexto necessário;
- usa skills técnicas conforme a stack;
- registra decisões relevantes.

### `qa`
- executa testes e build relevantes;
- registra resultados;
- aponta lacunas de validação.

### `reviewer`
- revisa a solução contra escopo, spec e convenções;
- usa skills técnicas conforme a stack;
- classifica findings;
- decide aceite, rejeição ou correções.

### `knowledge-curator`
- transforma findings recorrentes em conhecimento reutilizável;
- cria entradas curtas de knowledge;
- atualiza o índice.

---

## 8. O que cada arquivo principal faz

### `AGENTS.md`
Define as regras operacionais globais do Ravend.

### `opencode.json`
Define:
- agente padrão;
- instructions;
- permissões;
- MCPs;
- compaction;
- watcher ignore.

### `.lla/context/project.md`
Contexto de produto e domínio.

### `.lla/context/architecture.md`
Arquitetura da codebase.

### `.lla/context/conventions.md`
Padrões de código e revisão.

### `.lla/context/stack.md`
Stack, frameworks, comandos e detalhes técnicos.

### `.lla/sdd/current/intake.md`
Demanda inicial organizada.

### `.lla/sdd/current/prd.md`
Definição funcional da demanda.

### `.lla/sdd/current/tech-spec.md`
Definição técnica da solução.

### `.lla/sdd/current/tasks.md`
Lista de tarefas executáveis.

### `.lla/sdd/current/progress.md`
Situação atual e próximo passo.

### `.lla/sdd/current/decisions.md`
Decisões técnicas relevantes.

### `.lla/sdd/current/qa-report.md`
Saída de QA.

### `.lla/sdd/current/review-report.md`
Saída de review.

### `.lla/sdd/current/acceptance.md`
Fechamento da entrega.

### `.lla/manifests/task-scope.json`
Contrato da tarefa ativa.

### `.lla/manifests/agent-handoff.json`
Contrato de passagem entre agentes.

### `.lla/manifests/knowledge-index.json`
Índice seletivo da base de conhecimento.

---

## 9. Fluxo completo com leitura de arquivos

### Etapa 1 — entrada
Exemplo:
`/sdd-jira PROJ-123`

### Etapa 2 — orchestrator
Lê:
- `AGENTS.md`
- `.lla/context/project.md`
- `.lla/context/architecture.md`
- `.lla/context/conventions.md`
- `.lla/context/stack.md`

Decide:
- fluxo completo ou reduzido;
- stack dominante;
- agentes e skills necessários.

### Etapa 3 — intake
Lê:
- demanda do usuário ou card do Jira

Escreve:
- `.lla/sdd/current/intake.md`
- `.lla/manifests/agent-handoff.json`

### Etapa 4 — spec-writer
Lê:
- `.lla/sdd/current/intake.md`
- `.lla/templates/prd-template.md`
- `.lla/templates/tech-spec-template.md`
- `.lla/context/*.md`

Escreve:
- `.lla/sdd/current/prd.md`
- `.lla/sdd/current/tech-spec.md`

### Etapa 5 — planner
Lê:
- `.lla/sdd/current/prd.md`
- `.lla/sdd/current/tech-spec.md`
- `.lla/context/stack.md`
- `.lla/context/architecture.md`

Decide:
- stack dominante;
- skills técnicas a usar;
- forma do plano;
- se a task é backend, frontend ou full stack.

Escreve:
- `.lla/sdd/current/tasks.md`
- `.lla/manifests/agent-handoff.json`

### Etapa 6 — task-decomposer
Lê:
- `.lla/sdd/current/tasks.md`
- `.lla/sdd/current/tech-spec.md`
- `.lla/templates/task-template.md`

Escreve:
- `.lla/manifests/task-scope.json`

### Etapa 7 — implementer
Lê:
- `.lla/manifests/task-scope.json`
- `.lla/sdd/current/tech-spec.md`
- `.lla/context/conventions.md`
- `.lla/context/stack.md`
- `.lla/manifests/knowledge-index.json`
- skills técnicas relevantes

Exemplos:
- `quarkus-implementation`
- `spring-implementation`
- `angular-implementation`

Escreve:
- código da aplicação
- `.lla/sdd/current/decisions.md`
- `.lla/sdd/current/progress.md`

### Etapa 8 — qa
Lê:
- `.lla/manifests/task-scope.json`
- `.lla/context/stack.md`

Escreve:
- `.lla/sdd/current/qa-report.md`

### Etapa 9 — reviewer
Lê:
- `.lla/manifests/task-scope.json`
- `.lla/sdd/current/tech-spec.md`
- `.lla/context/conventions.md`
- `.lla/manifests/knowledge-index.json`
- skills técnicas relevantes

Exemplos:
- `quarkus-review`
- `spring-review`
- `angular-review`

Escreve:
- `.lla/sdd/current/review-report.md`

### Etapa 10 — knowledge-curator
Lê:
- `.lla/sdd/current/review-report.md`
- `.lla/sdd/current/qa-report.md`
- `.lla/manifests/knowledge-index.json`

Escreve:
- nova entrada em `.lla/knowledge/...`
- atualização do índice

### Etapa 11 — aceite
Lê:
- `.lla/sdd/current/review-report.md`
- `.lla/sdd/current/qa-report.md`
- `.lla/sdd/current/tasks.md`

Escreve:
- `.lla/sdd/current/acceptance.md`

---

## 10. Como dar manutenção

### Mude `AGENTS.md` quando:
- mudar a política do fluxo;
- mudar regra de fast path;
- mudar regra global de delegação;
- mudar política de knowledge retrieval.

### Mude `.opencode/agents/` quando:
- mudar responsabilidade de um agente;
- mudar permissões;
- mudar fronteira de atuação.

### Mude `.opencode/skills/` quando:
- mudar padrão técnico de stack;
- mudar checklist;
- mudar procedimento;
- surgir nova armadilha recorrente.

### Mude `.lla/context/` quando:
- mudar stack;
- mudar arquitetura;
- mudar convenções;
- mudar comandos de build/teste.

### Mude `.lla/manifests/` quando:
- mudar contrato de handoff;
- mudar contrato da task;
- mudar taxonomia de knowledge.

### Mude `.lla/knowledge/` quando:
- surgir erro recorrente;
- houver aprendizado reaproveitável;
- houver guideline técnico novo.

---

## 11. Resumo

A estratégia atual do Ravend é:

- agentes para papéis;
- skills para especialização;
- planner para roteamento;
- manifests para contratos;
- knowledge indexada para economia de contexto.

Isso reduz complexidade agora sem impedir crescimento depois.
