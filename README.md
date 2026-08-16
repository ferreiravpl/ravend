<div align="center">
<img src="./imgs/ravend-logo.png" alt="Ravend" width="180" />
</div>

# Ravend
**Orquestre desenvolvimento assistido por IA com disciplina estruturada — do intake ao código em produção.**

Um harness agentic para substituir prompts dispersos, tracking manual de tarefas e ciclos de review copiados e colados. Ravend conduz o ciclo completo de desenvolvimento assistido por IA dentro do [OpenCode](https://opencode.ai): intake de demanda, especificação de produto, design técnico, decomposição de tarefas, implementação, QA, review e aceite iterativo — tudo com contexto mínimo, estado persistente e especialização por stack.

> **Construção ativa** — Este projeto está em desenvolvimento. Estrutura, skills e comandos podem mudar.

---

## Destaques

- **Disciplina Estruturada de Desenvolvimento (SDD).** Um pipeline comprovado: intake → PRD → tech spec → decomposição → implementação → QA → review → loop até aceite. Cada fase produz artefatos markdown que alimentam a próxima. Comece de uma demanda bruta para rastreabilidade completa, ou pule direto para implementação quando o escopo já estiver claro.

- **QA com build real.** O agente QA não apenas sugere testes — ele executa build, compilação, testes com escopo restrito, lint gate (checkstyle + ESLint) e guardrail validators. PASS/FAIL baseado em exit codes, nunca em julgamento subjetivo. Fallback graceful quando ferramentas não estão disponíveis.

- **QA backend + frontend de verdade.** Backend: build, testes unitários, lint, guardrails **e validação de API em runtime** via MCP `api-test` — sobe a aplicação, exercita os endpoints do escopo e asserta status/contrato (com import de spec OpenAPI quando disponível). Frontend: build, testes e **E2E em navegador real** via MCP Playwright com screenshot de evidência. Tudo opcional com fallback: indisponibilidade vira SKIP com nota, nunca bloqueia o gate.

- **Review com score determinístico.** O reviewer produz score 0-100 com regras de dedução objetivas, classifica findings em P0 (bloqueante), P1 (deve corrigir) e P2 (opcional), e gera ações obrigatórias numeradas quando reprova. Aprovação exige score ≥ 95 e zero P0/P1.

- **Loop de qualidade com convergência garantida.** O orchestrator coordena o ciclo implementer → QA → reviewer → correção → QA → reviewer com limites claros: max 3 iterações de review, max 2 retries de QA, score delta rule (+5 mínimo entre iterações) e escalada automática para humano quando o loop não converge.

- **Roteamento por stack.** Ravend detecta a stack dominante (Quarkus, Spring, Angular) e carrega skills especializadas sob demanda — checklists de implementação, padrões de review e convenções específicas do seu framework. Nada de conselho genérico; cada ação é fundamentada na realidade da sua codebase.

- **Guardrails de código.** Cinco guardrails protegem contra problemas recorrentes: tamanho de classe (150 linhas), formatação (140 chars), nomenclatura de testes (snake_case), economia de contexto (max 3 skills) e escopo mínimo (não expandir). Cada guardrail tem severidade, applyTo por agente e comandos de verificação executáveis.

- **Knowledge base pré-seeded com anti-patterns.** 10 anti-patterns cobrindo Spring, Quarkus, Angular e Java genérico — de field injection a subscribe sem cleanup. Regra de frequência: padrões vistos 3+ vezes viram hard constraint (equivalente a P0). Write-back segmentado por stack.

- **Minimalismo de contexto.** Sem despejar o repositório inteiro. Ravend carrega apenas o contexto necessário para a fase e tarefa atual, persiste estado em arquivos e compacta sessões longas automaticamente. Resultado: menor custo de tokens, execução mais rápida e menos risco de alucinação.

- **Estado persistente, fluxos retomáveis.** Cada execução SDD persiste seu estado em `.lla/sdd/current/`, com isolamento por task: artefatos por task em `{task_id}/`, artefatos compartilhados da demanda em `shared/`. Tasks concluídas são arquivadas em `~/.ravend/archive/` (fora do repo). Interrompa um fluxo, feche sua sessão e retome exatamente de onde parou com `/sdd-resume`. Sem contexto perdido, sem trabalho repetido.

- **Harness auto-otimizável.** Ravend pode auditar e evoluir sua própria configuração — agentes, skills, commands, arquivos de contexto e economia de tokens. Execute `/ravend-optimize` para uma análise crítica, ou `/ravend-evolve` para propor e executar melhorias incrementais.

- **Captura incremental de conhecimento.** Findings recorrentes são destilados em entradas compactas e indexadas em [`.lla/knowledge/`](./.lla/knowledge/), organizadas por papel (reviewer, implementer, shared). Conhecimento é carregado seletivamente — nunca tudo de uma vez. Consulte [`knowledge-index.json`](./.lla/manifests/knowledge-index.json) para o catálogo.

- **Markdown primeiro, JSON para contratos.** Markdown legível para specs, PRDs e decisões. JSON legível por máquina para manifests operacionais, schemas de output e handoffs. Tudo versionável, diffável e editável entre etapas.

---

## Como Funciona

```
intake → PRD → tech spec → decomposição → implementação → QA → review → aceite
↑                                                                    │
└────────────────────── loop até aceite ──────────────────────────────┘
```

1. **Intake** — Normaliza uma demanda bruta, ticket ou item Jira em um brief estruturado e acionável.
2. **PRD** — Produz um Documento de Requisitos de Produto proporcional à complexidade.
3. **Tech Spec** — Traduz o PRD em uma solução técnica implementável.
4. **Decomposição** — Quebra a spec em tarefas pequenas, verificáveis e com execution prompts.
5. **Implementação** — Executa uma tarefa por vez com skills da stack, guardrails e contexto mínimo.
6. **QA** — Executa build real, testes com escopo restrito, lint gate e guardrail validators. PASS/FAIL por exit code. API runtime via `api-test` quando o diff tem backend; E2E de UI via Playwright quando tem frontend.
7. **Review** — Avalia com score determinístico (0-100), classifica findings (P0/P1/P2), gera ações obrigatórias se reprovado.
8. **Loop** — Itera até aceite (score ≥ 95, zero P0/P1). Depois captura aprendizados e arquiva.

Cada fase produz artefatos em `.lla/sdd/current/` (isolados por task em `{task_id}/`, compartilhados em `shared/`) e contratos operacionais em [`.lla/manifests/`](./.lla/manifests/).

### Fast Path

Nem toda mudança precisa do pipeline completo. Ravend prefere o **menor caminho seguro** — se já existe plano suficiente ou o escopo é trivial, pula direto para implementação. O fluxo SDD é o padrão, não uma camisa de força.

---

## Exemplo de Fluxo Completo

Demanda: *"Adicionar autenticação JWT com refresh token no módulo de usuários"* (full stack: Spring + Angular). Cada fase mostra o command, as skills carregadas e o artefato gerado.

### 1. Intake

```
/sdd-start Adicionar autenticação JWT com refresh token no módulo de usuários
```

| O que acontece | Skills / ferramentas |
|---|---|
| Agente `intake` normaliza a demanda em brief estruturado | `sdd-intake` (+ `brainstorming` se a demanda estiver ambígua) |
| **Artefato:** `.lla/sdd/current/shared/intake.md` | |

### 2. PRD e Tech Spec

```
/sdd-start (continua) ou /sdd-implement (fast path se o escopo já estiver claro)
```

| O que acontece | Skills / ferramentas |
|---|---|
| `spec-writer` produz PRD proporcional à complexidade e traduz em solução técnica | `sdd-prd`, `sdd-tech-spec` |
| **Artefatos:** `shared/prd.md`, `shared/tech-spec.md` | |

### 3. Decomposição

| O que acontece | Skills / ferramentas |
|---|---|
| `stack-routing` detecta full stack (spring + angular); `planner` seleciona as skills certas; `task-decomposer` quebra em tasks pequenas com execution prompts | `sdd-task-decomposition`, `stack-routing`, `writing-plans` |
| **Artefatos:** `shared/tasks.md`, `manifests/task-scope.json` (com `inspect_first`, `interface_to_implement`, `edge_cases`, `tests_to_implement`) | |

### 4. Implementação (task por task)

```
/sdd-implement task_01
```

| O que acontece | Skills / ferramentas |
|---|---|
| `implementer` implementa uma task delimitada com skills da stack e guardrails; registra decisões | `sdd-implementation`, `spring-implementation`, guardrails (`minimal-change`, `class-size`, `code-formatting`, `unit-test-naming`), `test-driven-development`, `context7` (docs de libs se necessário) |
| **Artefatos:** `{task_id}/decisions.md`, código no repo | |

### 5. QA completo (backend + frontend)

```
/sdd-qa task_01
```

| O que acontece | Skills / ferramentas |
|---|---|
| **Backend:** build real (`mvn compile`), testes com escopo restrito (`mvn test`), lint gate (checkstyle), guardrail validators — PASS/FAIL por exit code | `sdd-qa-verification` |
| **API runtime:** sobe o backend, detecta spec em `/v3/api-docs`, exercita `POST /auth/login` (sucesso + erro) e asserta status/contrato | `qa-api-testing` + MCP `api-test` |
| **Frontend:** build (`npm run build`), testes, lint (ESLint) | `sdd-qa-verification` |
| **E2E:** navega no fluxo de login, interage, asserta e salva screenshot como evidência | `qa-e2e-playwright` + MCP `playwright` |
| **Artefatos:** `{task_id}/qa-report.md`, `{task_id}/api-*.json`, `{task_id}/e2e-*.png` | |

Se o QA falhar com bug real: `systematic-debugging` para investigar a causa raiz antes de corrigir.

### 6. Review com loop de convergência

```
/sdd-review task_01
```

| O que acontece | Skills / ferramentas |
|---|---|
| `reviewer` avalia com score determinístico 0-100, findings P0/P1/P2, cruza com anti-patterns do knowledge e gera ações obrigatórias se reprovado | `sdd-review-loop`, `spring-review`, `angular-review`, knowledge (`anti-patterns.md`), guardrails, `requesting-code-review` / `receiving-code-review` |
| **Artefato:** `{task_id}/review_1.md` + output JSON | |

Se **REJECTED** (score < 95 ou P0/P1), o loop roda até convergir:

```
/sdd-implement task_01   # corrige apenas P0/P1 listados
/sdd-qa task_01
/sdd-review task_01      # iteração 2 — score deve subir ≥ 5 (score delta rule)
```

Limites: max 3 iterações de review, max 2 retries de QA. Sem convergência → escalada para humano.

### 7. Aceite

```
/sdd-accept
```

| O que acontece | Skills / ferramentas |
|---|---|
| Consolida aceite, gera `session.md` com métricas (score final, iterações, artefatos) e arquiva em `~/.ravend/archive/` | — |

**Artefato final:** `~/.ravend/archive/{date}_{task_id}-{slug}/session.md`

---

## Quick Start

### 1. Abra este repositório no OpenCode

Ravend roda como orquestrador residente dentro do [OpenCode](https://opencode.ai). Ao abrir este repo, o runtime carrega automaticamente:

- Identidade e regras em [`AGENTS.md`](./AGENTS.md)
- Configuração de agentes em [`opencode.json`](./opencode.json)
- Contexto estável em [`.lla/context/`](./.lla/context/)
- Templates em [`.lla/templates/`](./.lla/templates/)

### 2. Inicie um fluxo de desenvolvimento

```
/sdd-start Adicionar autenticação de usuário com JWT
```

Ravend executa o intake, produz PRD e tech spec se necessário, decompõe em tarefas e conduz a implementação até QA e review.

### 3. Comece a partir do Jira

```
/sdd-jira PROJ-1234
```

Puxa o item do Jira, normaliza via intake e segue o mesmo pipeline.

### 4. Retome um fluxo interrompido

```
/sdd-resume
```

Lê o estado persistido em `.lla/sdd/current/` e continua de onde parou. Se houver múltiplas tasks ativas, lista e pede para escolher.

### 5. Execute uma fase específica

```
/sdd-implement task_03
/sdd-qa task_03
/sdd-review task_03
/sdd-accept
```

Cada command ataca uma fase específica. Use quando você já sabe o que precisa acontecer.

---

## Commands

| Command | Finalidade |
|---|---|
| `/sdd-start <demanda>` | Inicia um fluxo SDD completo a partir de uma demanda textual |
| `/sdd-jira <chave>` | Inicia um fluxo SDD completo a partir de um item Jira |
| `/sdd-resume` | Retoma o fluxo atual a partir do estado persistido |
| `/sdd-implement <escopo>` | Executa implementação de uma tarefa ou escopo delimitado |
| `/sdd-qa <escopo>` | Executa verificação de QA com build real, testes, lint e guardrails |
| `/sdd-review <escopo>` | Revisa mudanças com score determinístico e findings P0/P1/P2 |
| `/sdd-accept` | Consolida aceite quando QA e review estão satisfatórios |
| `/ravend-whoami` | Explica quem é o Ravend, como está configurado e o que está ativo |
| `/ravend-optimize` | Analisa o harness e sugere otimizações |
| `/ravend-evolve <alvo>` | Propõe ou executa evolução incremental do harness |

Definições completas em [`.opencode/commands/`](./.opencode/commands/).

---

## Agentes

Ravend delega para agentes especializados, cada um com papel claro:

| Agente | Papel |
|---|---|
| [`orchestrator`](./.opencode/agents/orchestrator.md) | Agente primário. Escolhe o menor caminho seguro, persiste estado, coordena o pipeline e o loop de qualidade |
| [`intake`](./.opencode/agents/intake.md) | Normaliza demandas brutas em briefs estruturados e acionáveis |
| [`spec-writer`](./.opencode/agents/spec-writer.md) | Produz PRDs e refina especificações de produto |
| [`planner`](./.opencode/agents/planner.md) | Identifica stack dominante, seleciona skills, evita planos inflados |
| [`task-decomposer`](./.opencode/agents/task-decomposer.md) | Quebra specs em tarefas pequenas com execution prompts |
| [`implementer`](./.opencode/agents/implementer.md) | Implementa uma tarefa delimitada com skills da stack; corrige P0/P1 do review |
| [`qa`](./.opencode/agents/qa.md) | Executa build real, testes, lint gate, guardrail validators; valida API em runtime (backend) e E2E de UI (frontend) |
| [`reviewer`](./.opencode/agents/reviewer.md) | Revisa com score determinístico, findings P0/P1/P2 e output JSON estruturado |
| [`knowledge-curator`](./.opencode/agents/knowledge-curator.md) | Destila findings recorrentes em entradas compactas, indexadas e segmentadas por stack |

---

## Skills

Skills são carregadas sob demanda — nunca todas de uma vez. Elas fornecem procedimentos específicos por stack e por processo.

### Skills de Processo (SDD)

| Skill | Finalidade |
|---|---|
| `sdd-intake` | Normaliza demanda em intake estruturado |
| `sdd-prd` | Produz ou refina um PRD |
| `sdd-tech-spec` | Traduz PRD em tech spec implementável |
| `sdd-task-decomposition` | Quebra spec em tarefas com critérios de aceite e execution prompts |
| `sdd-implementation` | Guia a implementação de uma tarefa com execution prompt, guardrails e knowledge |
| `sdd-qa-verification` | Executa build real, testes, lint gate e guardrail validators com output JSON |
| `qa-e2e-playwright` | Valida fluxos de UI em navegador real via MCP Playwright (gate E2E opcional) |
| `qa-api-testing` | Valida contratos de API em runtime via MCP `api-test` com assertions e import OpenAPI (gate backend opcional) |
| `sdd-review-loop` | Revisa com score determinístico, findings P0/P1/P2, anti-pattern detection e output JSON |
| `sdd-context-compaction` | Compacta estado de sessões longas em arquivos persistentes |
| `sdd-knowledge-capture` | Converte findings recorrentes em conhecimento reutilizável com write-back segmentado |

### Skills de Stack

| Skill | Finalidade |
|---|---|
| `quarkus-implementation` | Padrões e checklist de implementação para Quarkus |
| `quarkus-review` | Checklist de review para codebases Quarkus |
| `spring-implementation` | Padrões e checklist de implementação para Spring |
| `spring-review` | Checklist de review para codebases Spring |
| `angular-implementation` | Padrões e checklist de implementação para Angular |
| `angular-review` | Checklist de review para codebases Angular |
| `stack-routing` | Identifica stack dominante e seleciona skills corretas |

### Skills Meta

| Skill | Finalidade |
|---|---|
| `ravend-harness-optimization` | Analisa e otimiza o próprio harness Ravend |
| `ravend-self-evolution` | Guia a evolução incremental do sistema agentic Ravend |

Definições completas em [`.opencode/skills/`](./.opencode/skills/).

### Skills Externas (Superpowers)

Skills genéricas de processo — brainstorming, writing-plans, test-driven-development, systematic-debugging, verification-before-completion e outras — são instaladas globalmente (não versionadas neste repo) via clone de [`obra/superpowers`](https://github.com/obra/superpowers) em `~/.config/opencode/superpowers/`, registradas no config global do OpenCode (`skills.paths`). Ficam disponíveis em qualquer projeto e são atualizadas com `git pull`.

---

## Integrações (MCP)

Servidores MCP configurados em `opencode.json`:

| MCP | Status | Uso |
|---|---|---|
| `filesystem` | enabled | Acesso a arquivos do workspace |
| `playwright` | enabled | Navegador real para testes E2E de UI (QA) |
| `api-test` | enabled | Testes de API REST em runtime com assertions e import OpenAPI (QA) |
| `context7` | enabled | Documentação atualizada de bibliotecas via MCP |
| `jira` | disabled | Requer credenciais e configuração manual para habilitar |
| `github` | disabled | Requer credenciais e configuração manual para habilitar |

Context7 fica disponível para qualquer agente consultar docs de libs durante planejamento e implementação. Playwright é usado pela skill `qa-e2e-playwright` quando o diff contém frontend; `api-test` pela skill `qa-api-testing` quando o diff contém backend.

---

## Guardrails

Guardrails são regras de código carregadas condicionalmente por agente e stack. Eles protegem contra problemas recorrentes sem poluir o contexto global.

| Guardrail | Severidade | applyTo | Regra |
|---|---|---|---|
| `minimal-change` | P0 | implementer | Não expandir escopo da task |
| `class-size` | P1 | implementer, qa, reviewer | Max 150 linhas por classe (excl. package/import/blank) |
| `code-formatting` | P1 | implementer, qa | Max 140 chars por linha |
| `unit-test-naming` | P1 | implementer, qa | snake_case: `should_X_when_Y` |
| `context-economy` | P1 | orchestrator | Não carregar >3 skills sem necessidade |

Definições completas em [`.lla/guardrails/`](./.lla/guardrails/). Thresholds canônicos em [`.lla/context/style-policy.md`](./.lla/context/style-policy.md).

**Precedência:** se o projeto-alvo tem checkstyle.xml, prettier ou .editorconfig com thresholds diferentes, o do projeto-alvo prevalece.

---

## Knowledge Base

A knowledge base em [`.lla/knowledge/`](./.lla/knowledge/) armazena anti-patterns e lições recorrentes, organizados por papel e stack:

| Segmento | Conteúdo |
|---|---|
| `shared/anti-patterns.md` | Índice mestre com AP-1 a AP-10 (Spring, Quarkus, Angular, Java genérico) |
| `reviewer/anti-patterns-spring.md` | Field injection, findAll sem Pageable, N+1, catch genérico |
| `reviewer/anti-patterns-quarkus.md` | @Singleton sem proxy, blocking no event loop, persist sem @Transactional |
| `reviewer/anti-patterns-angular.md` | Subscribe sem cleanup, uso de any, DOM direto |

**Regra de frequência:** anti-patterns com freq ≥ 3 são hard constraints (equivalente a P0 na review). O reviewer os trata como bloqueantes.

**Write-back segmentado:** quando o reviewer detecta um padrão recorrente não catalogado, o knowledge-curator registra tanto no índice mestre quanto no segmento da stack.

Catálogo completo em [`knowledge-index.json`](./.lla/manifests/knowledge-index.json).

---

## Estrutura do Repositório

```
.
├── AGENTS.md                    # Identidade e regras globais do Ravend
├── opencode.json                # Configuração do OpenCode (agentes, MCPs: filesystem/playwright/context7, permissions)
├── .opencode/
│   ├── agents/                  # Definições de agentes
│   ├── skills/                  # Definições de skills (SDD, por stack, meta)
│   └── commands/                # Portas de entrada de commands CLI
├── .lla/
│   ├── context/                 # Contexto estável do projeto
│   │   ├── project.md           # Missão do produto, domínio, restrições
│   │   ├── architecture.md      # Estrutura do repo, módulos, fronteiras
│   │   ├── conventions.md       # Padrões de código, nomenclatura, testes
│   │   ├── stack.md             # Linguagens, frameworks, build, heurísticas
│   │   ├── style-policy.md      # Fonte canônica de thresholds numéricos
│   │   ├── ravend-identity.md   # Identidade operacional do Ravend
│   │   └── ravend-optimization.md # Princípios de auto-otimização
│ ├── sdd/
│ │ └── current/ # Estado do fluxo SDD ativo
│ │     ├── {task_id}/ # Artefatos por task (decisions, qa-report, review_N, progress, task-scope.json)
│ │     └── shared/    # Artefatos compartilhados da demanda (intake, prd, tech-spec, tasks.md, acceptance.md)
│   ├── manifests/               # Contratos JSON (schemas, handoffs, knowledge-index)
│   │   └── schemas/             # Schemas de output (qa-output, review-output, task-scope, agent-handoff)
│   ├── guardrails/              # Guardrails de código com applyTo e severidade
│   ├── knowledge/               # Base de memória incremental e seletiva
│   │   ├── reviewer/            # Anti-patterns segmentados por stack
│   │   ├── implementer/         # Conhecimento específico do implementer
│   │   └── shared/              # Índice mestre de anti-patterns
│   └── templates/               # Templates de PRD, tech spec, task, review, session, knowledge
```

Skills externas (Superpowers) vivem fora do repo, em `~/.config/opencode/superpowers/` — ver seção Skills Externas.

---

## Princípios de Design

- **Menor caminho seguro.** SDD completo quando necessário; fast path quando suficiente.
- **Minimalismo de contexto.** Carrega apenas o que a fase atual exige. Persiste o resto em arquivos.
- **Consciente da stack, não acoplado.** Especialização entra via skills, não via lógica hardcoded.
- **Resultados, não promessas.** QA executa build real. Review produz score determinístico. Loop converge ou escala.
- **Defesa em camadas.** Guardrails, anti-patterns e style policy protegem sem poluir o contexto global.
- **Auto-melhorável.** Ravend pode auditar, otimizar e evoluir seu próprio harness.
- **Sem vendor lock-in.** Todos os artefatos são markdown e JSON. Versionáveis, diffáveis, editáveis.
- **"Não alterar nada" é válido.** Quando a melhor decisão é nenhuma decisão, o Ravend diz isso.

---

## Stacks Suportadas

| Stack | Implementação | Review | Anti-patterns |
|---|---|---|---|
| Quarkus | `quarkus-implementation` | `quarkus-review` | @Singleton, blocking, @Transactional |
| Spring | `spring-implementation` | `spring-review` | Field injection, N+1, findAll, catch genérico |
| Angular | `angular-implementation` | `angular-review` | Subscribe, any, DOM direto |

Stacks adicionais podem ser adicionadas criando novos diretórios de skill em [`.opencode/skills/`](./.opencode/skills/) e segmentos de knowledge em [`.lla/knowledge/reviewer/`](./.lla/knowledge/reviewer/).

---

## Auto-Otimização

Ravend tem consciência da própria arquitetura. Quando você pede para otimizar:

- Audita agentes, skills, commands, manifests e arquivos de contexto
- Identifica duplicação, inflação e complexidade desnecessária
- Sugere remoções, consolidações e simplificações
- Aponta trade-offs de economia de tokens e riscos de alucinação
- Propõe evolução incremental com before/after claro

Execute `/ravend-optimize` para análise, ou `/ravend-evolve` para execução. Veja os critérios de otimização em [`.lla/context/ravend-optimization.md`](./.lla/context/ravend-optimization.md).

---

## Licença

Este projeto é fornecido como-is para uso com OpenCode. Veja arquivos individuais para termos aplicáveis.
