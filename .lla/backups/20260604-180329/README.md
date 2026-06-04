# Ravend — Orquestrador SDD para OpenCode

## 1. Visão geral

Este repositório implementa um **LLA (Lightweight Local Agent Workspace)** voltado para desenvolvimento de software com **OpenCode**, usando **SDD** como fluxo principal.

Neste contexto, SDD significa:

1. Intake da demanda
2. PRD
3. Tech Spec
4. Task Decomposition
5. Implementação
6. QA
7. Code Review
8. Loop incremental até aceite

A proposta do Ravend não é obrigar sempre o fluxo completo.
A proposta é:

- ter um fluxo padrão confiável;
- permitir atalhos seguros quando a demanda já vier pronta;
- registrar o estado do trabalho em arquivos;
- reduzir dependência de memória conversacional;
- capturar aprendizado incremental sem inflar contexto.

---

## 2. Objetivo do orquestrador

O Ravend existe para resolver quatro problemas comuns em agentes de desenvolvimento:

### 2.1. Falta de continuidade
Sem arquivos de estado, o agente depende demais da memória da conversa.

### 2.2. Contexto grande demais
Se tudo for carregado sempre, o custo cresce, a precisão cai e o fluxo degrada.

### 2.3. Delegação sem contrato
Quando agentes trocam contexto de maneira solta, cada handoff fica ambíguo.

### 2.4. Aprendizado inexistente ou caro
Sem memória incremental, o sistema repete erros.
Com memória mal feita, o sistema carrega histórico demais.

O Ravend tenta equilibrar isso com:

- regras estáveis em `AGENTS.md`;
- contexto estável em `.lla/context/`;
- procedimentos reutilizáveis em `.opencode/skills/`;
- agentes especializados em `.opencode/agents/`;
- estado persistente em `.lla/sdd/current/`;
- contratos estruturados em `.lla/manifests/`;
- memória incremental seletiva em `.lla/knowledge/`.

---

## 3. Princípios de projeto

### 3.1. SDD é o caminho padrão, não a única opção
O fluxo completo é o caminho preferencial.
Mas o sistema pode operar em modo reduzido:

- só implementação;
- só QA;
- só review;
- review + implementação em loop;
- intake + planejamento sem codificação.

### 3.2. O menor fluxo seguro vence
O orquestrador deve escolher o menor fluxo que resolva o problema sem perder confiabilidade.

### 3.3. Contexto persistido em arquivo é melhor que contexto “lembrado”
Tudo o que precisa sobreviver entre sessões deve ir para arquivo.

### 3.4. Markdown para raciocínio humano, JSON para contrato operacional
Explicações, decisões, especificações e relatórios ficam em Markdown.
Escopo, handoff, índice e seleção ficam em JSON.

### 3.5. Conhecimento incremental deve ser seletivo
Não se carrega toda a base de conhecimento sempre.
Primeiro usa-se o índice. Depois carrega-se só o que for relevante.

---

## 4. Estrutura geral do repositório

```text
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
│       └── sdd-context-compaction/
└── .lla/
    ├── context/
    │   ├── project.md
    │   ├── architecture.md
    │   ├── conventions.md
    │   └── stack.md
    ├── templates/
    │   ├── prd-template.md
    │   ├── tech-spec-template.md
    │   ├── task-template.md
    │   └── knowledge-entry-template.md
    ├── manifests/
    │   ├── task-scope.json
    │   ├── agent-handoff.json
    │   ├── knowledge-index.json
    │   └── schemas/
    │       ├── task-scope.schema.json
    │       ├── agent-handoff.schema.json
    │       └── knowledge-index.schema.json
    ├── knowledge/
    │   ├── README.md
    │   ├── reviewer/
    │   ├── implementer/
    │   └── shared/
    └── sdd/
        └── current/
            ├── intake.md
            ├── prd.md
            ├── tech-spec.md
            ├── tasks.md
            ├── progress.md
            ├── decisions.md
            ├── qa-report.md
            ├── review-report.md
            └── acceptance.md
```

---

## 5. Arquivos principais no nível raiz

### 5.1. `README.md`
Este arquivo.

Responsável por:
- explicar a arquitetura do orquestrador;
- explicar o papel de cada diretório;
- explicar o papel de cada arquivo principal;
- servir como documento de manutenção;
- orientar evolução futura.

Ele é para humanos.

### 5.2. `AGENTS.md`
É o arquivo de regras do projeto.

Responsável por:
- definir missão do orquestrador;
- definir fluxo padrão;
- dizer quando o SDD pode ser encurtado;
- definir política de escrita em arquivos;
- definir política de leitura da base de conhecimento;
- orientar o comportamento global dos agentes.

Ele é para runtime do OpenCode e também para humanos.

### 5.3. `opencode.json`
É a configuração principal do OpenCode para este repositório.

Responsável por:
- definir o `default_agent`;
- definir `instructions`;
- definir permissões gerais;
- definir MCPs habilitados;
- definir compaction;
- definir exclusões do watcher.

---

## 6. Diretório `.opencode/`

Este diretório contém os componentes diretamente conectados ao runtime do OpenCode.

### 6.1. `.opencode/agents/`
Contém os agentes especializados.

Cada arquivo representa um agente ou subagente com:
- descrição;
- modo;
- permissões;
- prompt base;
- fronteiras de atuação.

### 6.2. `.opencode/commands/`
Contém os commands slash do projeto.

Esses commands são atalhos de entrada.
Eles não devem concentrar a lógica inteira do sistema.
O papel deles é iniciar fluxos com intenção clara e contexto mínimo.

### 6.3. `.opencode/skills/`
Contém as skills do projeto.

Uma skill representa um procedimento reutilizável e carregável sob demanda.

Ela serve para:
- evitar repetição de instruções;
- reduzir tamanho do prompt base;
- padronizar procedimentos;
- manter o sistema modular.

---

## 7. Diretório `.lla/`

Este diretório contém o estado persistente e a memória operacional do Ravend.

### 7.1. `.lla/context/`
Contém contexto estável do projeto.

Esses arquivos existem para reunir informação que:
- muda pouco;
- precisa ser reaproveitada;
- deve ficar fora do prompt base do agente;
- pode ser carregada pelas `instructions`.

Arquivos:

#### `project.md`
Descreve:
- domínio do projeto;
- objetivo do produto;
- áreas de negócio;
- restrições relevantes de produto.

#### `architecture.md`
Descreve:
- estrutura do repositório;
- componentes principais;
- integração entre módulos;
- fluxo de dados;
- decisões arquiteturais globais.

#### `conventions.md`
Descreve:
- padrões de código;
- naming conventions;
- convenções de testes;
- regras de revisão;
- decisões de organização da codebase.

#### `stack.md`
Descreve:
- linguagens;
- frameworks;
- ferramentas de build;
- ferramentas de teste;
- comandos úteis;
- pré-requisitos técnicos.

### 7.2. `.lla/templates/`
Contém modelos reutilizáveis para artefatos.

Arquivos:

#### `prd-template.md`
Modelo de PRD.

#### `tech-spec-template.md`
Modelo de especificação técnica.

#### `task-template.md`
Modelo de task.

#### `knowledge-entry-template.md`
Modelo de entrada de conhecimento incremental.

### 7.3. `.lla/sdd/current/`
Contém o estado atual da entrega em andamento.

Arquivos:

#### `intake.md`
Registro inicial da demanda.

Responsável por:
- resumir pedido bruto;
- separar fatos, hipóteses e dúvidas;
- registrar origem da demanda.

#### `prd.md`
Documento de produto da demanda atual.

Responsável por:
- deixar claro o problema;
- definir objetivo;
- registrar escopo e não escopo;
- definir critérios de aceite do ponto de vista de negócio/entrega.

#### `tech-spec.md`
Especificação técnica da demanda atual.

Responsável por:
- traduzir o PRD em solução técnica;
- definir módulos impactados;
- definir interfaces;
- definir riscos;
- definir estratégia de teste.

#### `tasks.md`
Decomposição da demanda em tarefas executáveis.

Responsável por:
- quebrar o trabalho;
- tornar implementação incremental;
- facilitar handoffs;
- reduzir escopo por execução.

#### `progress.md`
Linha do tempo resumida da execução atual.

Responsável por:
- registrar fase atual;
- apontar o próximo passo;
- resumir pendências;
- facilitar retomada de sessão.

#### `decisions.md`
Registro de decisões importantes.

Responsável por:
- armazenar trade-offs;
- justificar escolhas;
- preservar contexto útil para review e evolução futura.

#### `qa-report.md`
Relatório da verificação técnica.

Responsável por:
- listar comandos executados;
- registrar resultados;
- apontar falhas;
- informar lacunas de validação.

#### `review-report.md`
Relatório de revisão.

Responsável por:
- apontar problemas;
- classificar severidade;
- dizer se foi aceito ou rejeitado;
- alimentar base de conhecimento.

#### `acceptance.md`
Registro de aceite.

Responsável por:
- indicar conclusão;
- consolidar escopo entregue;
- registrar observações finais;
- fechar formalmente o ciclo.

### 7.4. `.lla/manifests/`
Contém contratos estruturados e artefatos operacionais em JSON.

Arquivos:

#### `task-scope.json`
É o contrato da tarefa ativa.

Responsável por:
- definir escopo de arquivos;
- definir critérios de aceite da tarefa;
- informar comandos de teste;
- listar focos de review;
- indicar referências de conhecimento.

#### `agent-handoff.json`
É o contrato de passagem entre agentes.

Responsável por:
- informar agente de origem;
- informar agente de destino;
- definir objetivo;
- listar insumos obrigatórios;
- listar restrições;
- definir “done definition”.

#### `knowledge-index.json`
É o índice da base de conhecimento.

Responsável por:
- registrar entradas disponíveis;
- permitir seleção por tags;
- evitar leitura de toda a base;
- viabilizar retrieval seletivo.

#### `.lla/manifests/schemas/*.json`
São esquemas de referência.

Responsáveis por:
- padronizar estrutura dos manifests;
- documentar contrato esperado;
- reduzir deriva estrutural;
- orientar manutenção.

### 7.5. `.lla/knowledge/`
Contém memória incremental reutilizável.

Subpastas:

#### `reviewer/`
Lições geradas a partir de code review.

#### `implementer/`
Guardrails para implementação.

#### `shared/`
Convenções ou aprendizados compartilhados.

A pasta também possui:

#### `README.md`
Documento explicando a política da base de conhecimento.

---

## 8. Por que Markdown e JSON

### 8.1. Quando usar Markdown
Markdown é melhor quando existe:
- explicação;
- ambiguidade controlada;
- decisão;
- trade-off;
- narrativa;
- contexto humano.

Por isso ele é usado em:
- PRD;
- tech spec;
- tasks;
- relatórios;
- convenções;
- contexto estável;
- conhecimento incremental em formato humano.

### 8.2. Quando usar JSON
JSON é melhor quando existe:
- contrato;
- estrutura rígida;
- baixo custo de parsing mental;
- necessidade de seleção automatizada;
- necessidade de handoff com pouca ambiguidade.

Por isso ele é usado em:
- manifests;
- índice de conhecimento;
- schemas.

### 8.3. Por que não XML aqui
XML não traz vantagem operacional para este caso.

Ele só faria sentido se:
- um sistema externo exigisse XML;
- alguma integração específica dependesse desse formato.

Como formato interno do Ravend, XML aumentaria atrito sem ganho claro.

---

## 9. Agentes e suas responsabilidades

### 9.1. `orchestrator`
É o agente principal.

Responsável por:
- interpretar a solicitação;
- decidir se usa fluxo completo ou reduzido;
- acionar os agentes corretos;
- garantir que o estado seja persistido;
- evitar carga desnecessária de contexto;
- acionar captura de conhecimento quando houver aprendizado reutilizável.

### 9.2. `intake`
Responsável por transformar entrada bruta em demanda organizada.

O que faz:
- lê pedido do usuário ou card do Jira;
- organiza objetivo, restrições, lacunas e sinais de aceite;
- grava `intake.md`;
- prepara handoff inicial.

### 9.3. `spec-writer`
Responsável por PRD e especificação técnica.

O que faz:
- cria ou atualiza `prd.md`;
- cria ou atualiza `tech-spec.md`;
- prepara material para o planner.

### 9.4. `planner`
Responsável por estratégia de execução.

O que faz:
- decide formato do plano;
- reduz a demanda para o menor conjunto seguro de passos;
- produz handoff claro;
- evita escopo inflado.

### 9.5. `task-decomposer`
Responsável por gerar tarefas pequenas.

O que faz:
- quebra a especificação em tarefas;
- define critérios de aceite por tarefa;
- define arquivos em escopo;
- alimenta `task-scope.json`.

### 9.6. `implementer`
Responsável por implementar uma tarefa por vez.

O que faz:
- lê a task ativa;
- lê só o contexto necessário;
- aplica mudança delimitada;
- atualiza decisões relevantes.

### 9.7. `qa`
Responsável por verificar tecnicamente a mudança.

O que faz:
- executa testes;
- executa build quando fizer sentido;
- registra lacunas;
- escreve `qa-report.md`.

### 9.8. `reviewer`
Responsável por revisar a solução.

O que faz:
- verifica aderência ao escopo;
- verifica aderência à spec;
- verifica qualidade e manutenção;
- decide aceite, rejeição ou correções.

### 9.9. `knowledge-curator`
Responsável por consolidar aprendizado.

O que faz:
- transforma findings recorrentes em conhecimento reutilizável;
- decide categoria do aprendizado;
- atualiza `knowledge-index.json`;
- cria entradas compactas.

---

## 10. Skills e seus papéis

### 10.1. `sdd-intake`
Normaliza a demanda.

### 10.2. `sdd-prd`
Gera PRD proporcional à complexidade.

### 10.3. `sdd-tech-spec`
Transforma a demanda em solução técnica.

### 10.4. `sdd-task-decomposition`
Quebra em tarefas executáveis e compactas.

### 10.5. `sdd-implementation`
Guia implementação de task única.

### 10.6. `sdd-qa-verification`
Guia a verificação com menor escopo suficiente.

### 10.7. `sdd-review-loop`
Guia revisão e decisão de aceite.

### 10.8. `sdd-knowledge-capture`
Transforma erro repetível em aprendizado compacto.

### 10.9. `sdd-context-compaction`
Ajuda a comprimir estado de sessões longas para arquivos persistentes.

---

## 11. Commands disponíveis

### 11.1. `/sdd-start`
Inicia fluxo a partir de um pedido textual.

### 11.2. `/sdd-jira`
Inicia fluxo a partir de um item do Jira.

### 11.3. `/sdd-implement`
Executa implementação de escopo delimitado.

### 11.4. `/sdd-qa`
Executa verificação de QA.

### 11.5. `/sdd-review`
Executa code review.

### 11.6. `/sdd-resume`
Retoma fluxo a partir do estado persistido.

### 11.7. `/sdd-accept`
Consolida aceite e encerra ciclo.

---

## 12. Fluxos suportados

### 12.1. Fluxo completo
Usado quando a demanda ainda não está bem especificada.

Sequência:
1. intake
2. PRD
3. tech spec
4. tasks
5. implementação
6. QA
7. review
8. knowledge capture
9. aceite

### 12.2. Fast path para implementação
Usado quando já existe plano aprovado.

Sequência:
1. task-scope
2. implementação
3. QA
4. review
5. knowledge capture
6. aceite

### 12.3. Fast path para review
Usado quando só se quer revisar alteração existente.

Sequência:
1. carregar contexto mínimo
2. revisar
3. registrar findings
4. capturar aprendizado, se aplicável

### 12.4. Fast path para QA
Usado quando só se quer validar algo técnico.

Sequência:
1. carregar task ativa
2. executar testes/build/lint relevantes
3. registrar relatório

---

## 13. Exemplo detalhado de fluxo completo

### Cenário
Usuário informa um card do Jira para implementação.

### Etapa 1 — entrada
O usuário chama:

```text
/sdd-jira PROJ-123
```

### Etapa 2 — orquestrador inicia intake
Arquivos lidos prioritariamente:
- `AGENTS.md`
- `.lla/context/project.md`
- `.lla/context/architecture.md`
- `.lla/context/conventions.md`
- `.lla/context/stack.md`

Arquivos escritos:
- `.lla/sdd/current/intake.md`
- `.lla/manifests/agent-handoff.json`

### Etapa 3 — spec-writer gera PRD e tech spec
Arquivos lidos:
- `.lla/sdd/current/intake.md`
- `.lla/templates/prd-template.md`
- `.lla/templates/tech-spec-template.md`
- `.lla/context/*.md`

Arquivos escritos:
- `.lla/sdd/current/prd.md`
- `.lla/sdd/current/tech-spec.md`
- `.lla/sdd/current/progress.md`

### Etapa 4 — planner decide execução
Arquivos lidos:
- `.lla/sdd/current/prd.md`
- `.lla/sdd/current/tech-spec.md`
- `.lla/sdd/current/decisions.md`

Arquivos escritos:
- `.lla/sdd/current/tasks.md`
- `.lla/manifests/agent-handoff.json`

### Etapa 5 — task-decomposer detalha a task ativa
Arquivos lidos:
- `.lla/sdd/current/tasks.md`
- `.lla/templates/task-template.md`
- `.lla/sdd/current/tech-spec.md`

Arquivos escritos:
- `.lla/manifests/task-scope.json`
- `.lla/sdd/current/progress.md`

### Etapa 6 — implementer executa
Arquivos lidos:
- `.lla/manifests/task-scope.json`
- `.lla/sdd/current/tech-spec.md`
- `.lla/context/conventions.md`
- `.lla/context/stack.md`
- `.lla/manifests/knowledge-index.json`
- entradas específicas em `.lla/knowledge/...` quando referenciadas

Arquivos escritos:
- código da aplicação
- `.lla/sdd/current/decisions.md`
- `.lla/sdd/current/progress.md`

### Etapa 7 — QA verifica
Arquivos lidos:
- `.lla/manifests/task-scope.json`
- `.lla/context/stack.md`
- `.lla/sdd/current/tech-spec.md`

Arquivos escritos:
- `.lla/sdd/current/qa-report.md`

### Etapa 8 — reviewer revisa
Arquivos lidos:
- `.lla/manifests/task-scope.json`
- `.lla/sdd/current/tech-spec.md`
- `.lla/context/conventions.md`
- `.lla/manifests/knowledge-index.json`
- entradas relevantes de `.lla/knowledge/reviewer/`
- `.lla/sdd/current/qa-report.md`

Arquivos escritos:
- `.lla/sdd/current/review-report.md`

### Etapa 9 — knowledge-curator captura aprendizado
Executa apenas se houver lição reaproveitável.

Arquivos lidos:
- `.lla/sdd/current/review-report.md`
- `.lla/sdd/current/qa-report.md`
- `.lla/manifests/knowledge-index.json`
- `.lla/templates/knowledge-entry-template.md`

Arquivos escritos:
- nova entrada em `.lla/knowledge/...`
- atualização de `.lla/manifests/knowledge-index.json`

### Etapa 10 — aceite
Arquivos lidos:
- `.lla/sdd/current/review-report.md`
- `.lla/sdd/current/qa-report.md`
- `.lla/sdd/current/tasks.md`

Arquivos escritos:
- `.lla/sdd/current/acceptance.md`
- `.lla/sdd/current/progress.md`

---

## 14. Como dar manutenção

### Quando mexer em `AGENTS.md`
Quando mudar:
- política global do orquestrador;
- fluxo padrão;
- critérios de fast path;
- regras de persistência;
- regras de knowledge retrieval.

### Quando mexer em `.opencode/agents/`
Quando mudar:
- responsabilidade de um agente;
- permissões;
- fronteira de atuação;
- estilo de delegação.

### Quando mexer em `.opencode/skills/`
Quando mudar:
- procedimento reutilizável;
- checklist operacional;
- comportamento padronizado.

### Quando mexer em `.lla/context/`
Quando mudar:
- stack;
- arquitetura;
- convenções;
- contexto de produto.

### Quando mexer em `.lla/manifests/`
Quando mudar:
- contrato de handoff;
- contrato da task;
- taxonomia da knowledge.

### Quando mexer em `.lla/knowledge/`
Quando surgir:
- erro recorrente;
- padrão recorrente de review;
- aprendizado reutilizável.

---

## 15. Estratégia de crescimento futuro

As próximas evoluções mais naturais do Ravend são:

1. ligar MCP real do Jira;
2. refinar taxonomia do knowledge-index;
3. adaptar os prompts dos agentes por stack;
4. adicionar validação automatizada dos schemas JSON;
5. adicionar commands auxiliares para retomada e aceite;
6. criar knowledge entries por linguagem/framework/camada.

---

## 16. Resumo final

O Ravend foi desenhado para ser:
- incremental;
- modular;
- econômico em tokens;
- explícito na persistência de estado;
- confiável em handoff entre agentes;
- flexível para fluxo completo e fluxos reduzidos.

A ideia central não é ter muitos agentes.
A ideia central é ter contratos claros, contexto pequeno e aprendizado incremental útil.
