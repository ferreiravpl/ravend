<div align="center">
<img src="./imgs/ravend-logo.png" alt="Ravend" width="160" />

# Ravend

**Pipeline de entrega spec-driven para o Claude Code — da demanda ao código testado, com gates de qualidade que o modelo não consegue pular.**
</div>

Ravend é um plugin do [Claude Code](https://claude.com/claude-code). Ele conduz uma demanda (texto, issue do Jira ou do GitHub) pelo caminho **spec → build test-first → verify → review independente → PR**. A profundidade do processo é proporcional ao tamanho da mudança. Tudo que precisa ser garantido roda em código (hooks e scripts), não em instruções de prompt.

```
demanda ──▶ /ravend:spec ──▶ [você aprova]* ──▶ /ravend:build ──▶ /ravend:verify ──▶ /ravend:review ──▶ [você aprova] ──▶ /ravend:ship ──▶ PR
              nível                              red→green→gate    gate full +         reviewer com         push + PR com
              trivial/small/large/bug            por task, commit  critérios→testes    contexto limpo       evidências
                                                                    E2E Playwright      P0/P1/P2
* só para mudanças "large"
```

---

## Sumário
- [Instalação](#instalação)
- [Primeiros passos](#primeiros-passos)
- [Comandos](#comandos)
- [Como o pipeline decide o tamanho do processo](#como-o-pipeline-decide-o-tamanho-do-processo)
- [Onde ficam os dados (local, por desenvolvedor)](#onde-ficam-os-dados-local-por-desenvolvedor)
- [Quality gate e hooks](#quality-gate-e-hooks)
- [Testes: unit, API e E2E](#testes-unit-api-e-e2e)
- [Agentes](#agentes)
- [Modo headless / CI](#modo-headless--ci)
- [Integrações](#integrações)
- [Custo de contexto e desempenho](#custo-de-contexto-e-desempenho)
- [Desenvolvendo o plugin](#desenvolvendo-o-plugin)
- [Vindo do Ravend para OpenCode](#vindo-do-ravend-para-opencode)
- [Limitações conhecidas](#limitações-conhecidas)

---

## Instalação

Requisitos: Claude Code 2.1+, `git`, **Python 3.8+** (os scripts usam só a biblioteca padrão) e `gh` autenticado, se você for usar `/ravend:ship`.

```text
/plugin install ravend --marketplace ferreiravpl/ravend
```
Ou em dois passos:
```text
/plugin marketplace add ferreiravpl/ravend
/plugin install ravend@ravend
```
Reinicie a sessão do Claude Code depois de instalar.

Recomendado: o plugin [`superpowers`](https://github.com/obra/superpowers) (`/plugin install superpowers@claude-plugins-official`). Ele cobre brainstorming, debugging sistemático e disciplina de TDD, e o Ravend aproveita essas skills quando estão presentes. O Ravend funciona sem ele.

## Primeiros passos

Em **cada repositório** onde você quer usar o pipeline (uma vez por máquina):

```text
/ravend:init
```
O `init` detecta stacks e módulos, lê os comandos reais do projeto (build files, scripts, CI) e gera o **perfil local** com os comandos do gate. Ele também escreve notas curtas do projeto e, se você aceitar, configura os MCPs Playwright/Context7 no escopo *local*. **Nada é escrito no repositório.**

Depois:

```text
/ravend:run Adicionar paginação em GET /products e na listagem do front
```
ou etapa por etapa:
```text
/ravend:spec PROJ-123
/ravend:build add-products-pagination
/ravend:verify add-products-pagination
/ravend:review add-products-pagination
/ravend:ship add-products-pagination
```

Para retomar depois de fechar a sessão ou dar `/clear`: o estado está na spec (checklist de tasks + log) e no git. A sessão nova mostra as specs ativas automaticamente; basta chamar o próximo comando.

## Comandos

| Comando | O que faz |
|---|---|
| `/ravend:init` | Configura o projeto **nesta máquina**: perfil do gate, notas do projeto, MCPs locais. |
| `/ravend:run <demanda>` | Pipeline completo interativo, parando só nos checkpoints humanos. |
| `/ravend:spec <demanda \| PROJ-123 \| #45>` | Classifica o nível e escreve uma spec única com critérios Given/When/Then e tasks. |
| `/ravend:build <slug> [--fix gate\|verify\|review]` | Implementa task a task: teste falhando → código → gate fast → commit. Também corrige falhas do gate e findings de review. |
| `/ravend:verify <slug>` | Roda o gate full, monta a matriz critério→teste e escreve os testes de API/E2E que faltam. |
| `/ravend:review <slug>` | Review por um agente com contexto limpo; findings P0/P1/P2 com `arquivo:linha` e cenário de falha. |
| `/ravend:ship <slug>` | Confere gate verde + review aprovado, faz push e abre o PR com critérios, evidências e veredito. |
| `/ravend:learn <lição>` | Guarda uma lição específica do projeto na knowledge local. |

Skills carregadas automaticamente por contexto: `stack-spring`, `stack-quarkus`, `stack-angular`, `stack-react`, `api-tests` e `e2e-playwright`.

## Como o pipeline decide o tamanho do processo

| Nível | Quando | O que acontece |
|---|---|---|
| **trivial** | ≤2 arquivos, sem comportamento novo | Sem spec. Implementa direto com o gate. |
| **small** | um módulo/camada, comportamento claro | Spec curta (problema, critérios, tasks). Segue sem pedir aprovação. |
| **large** | vários módulos ou full stack, contrato de API/DB novo, migração, ambiguidade real | Spec completa com design. **Você aprova antes do build.** |
| **bug** | defeito | Primeiro um teste que reproduz o bug; depois a correção. |

Uma spec, não cinco documentos. Os critérios de aceite são escritos em Given/When/Then com o nível de teste que vai prová-los (`[unit]`, `[api]`, `[e2e]`, `[visual]`) e viram testes no build.

Há só dois checkpoints humanos: **aprovar a spec** (só no nível large) e **aprovar o push/PR**. Entre eles, quem decide se algo está pronto é o gate.

## Onde ficam os dados (local, por desenvolvedor)

O Ravend é feito para ser usado por várias pessoas no mesmo repositório **sem sujar o repositório**. Perfil, notas, knowledge e specs são de cada desenvolvedor e ficam na máquina dele:

```
~/.ravend/                                  (ou $RAVEND_HOME)
└── projects/
    └── github.com-org-repo/                ← id derivado do remote origin (igual em todos os clones/worktrees)
        ├── profile.json                    comandos do gate, formatters, app, paths protegidos
        ├── project.md                      notas curtas de convenções do projeto (injetadas no início da sessão)
        ├── knowledge/                      lições aprendidas: index.md + 1 arquivo por lição
        ├── specs/<slug>/                   spec.md, verify.md, review-N.md, evidence/
        ├── runs/                           logs do gate, da app e do modo headless
        └── state/                          último gate, árvore verde, sessão armada
```

- **O que o time vê é o PR.** O `/ravend:ship` coloca no corpo do PR o resumo, os critérios de aceite com o teste que prova cada um, o resultado do gate e o veredito do review.
- Repositórios sem remote usam o nome da pasta mais um hash do caminho.
- Pode editar ou apagar qualquer arquivo dali à vontade. Apagar o diretório do projeto equivale a "desinstalar" o Ravend daquele repo.

## Quality gate e hooks

O gate é a peça central: **decisão por exit code, executada por script, nunca pelo julgamento do modelo.**

- **`gate fast`** roda depois de cada task. Cobre só o que mudou: compilação/typecheck, testes relacionados aos arquivos alterados e lint dos arquivos alterados.
- **`gate full`** é o que o CI rodaria para a branch: build, todos os testes, lint, integração e E2E. Opcionalmente também cobertura do diff e mutation testing.
- A saída mostra só o trecho relevante da falha e o caminho do log completo, para manter o contexto do modelo enxuto.
- Os comandos ficam no `profile.json` local; veja a referência com exemplos para Spring, Quarkus, Angular e React em [`skills/init/references/profile.md`](skills/init/references/profile.md).

```bash
python3 ~/.claude/plugins/.../ravend/scripts/ravend.py gate fast   # o caminho exato aparece no início da sessão
python3 .../ravend.py gate full --dry-run                          # mostra os comandos resolvidos
python3 .../ravend.py status                                       # specs ativas + último gate
```

Hooks do plugin (todos inertes em repositórios sem perfil local):

| Hook | Comportamento |
|---|---|
| `SessionStart` | Injeta id do projeto, notas, índice da knowledge e specs ativas. Exporta `RAVEND_ROOT`, `RAVEND_DATA` e `RAVEND_SESSION_ID`. |
| `PreToolUse` (Edit/Write) | Bloqueia edição de `protected_paths` (`.env`, chaves, código gerado…). |
| `PostToolUse` (Edit/Write) | Roda o formatter rápido configurado para o arquivo editado. Quem formata é a ferramenta, não o prompt. |
| `Stop` | **Só enquanto um build está armado** (`/ravend:build` arma e `/ravend:ship` desarma): se a árvore mudou desde o último gate verde, roda o `gate fast` e impede o Claude de encerrar com o gate vermelho. Depois de 3 bloqueios seguidos, libera e pede intervenção humana. |

Válvulas de escape: `RAVEND_GATE=off` (desliga o hook de Stop), `RAVEND_FORMAT=off` (desliga o formatter) e `ravend.py disarm`.

## Testes: unit, API e E2E

- **Unit e API:** os testes ficam versionados no repositório-alvo, no estilo do projeto. As skills de stack trazem padrões por camada: Spring (`@WebMvcTest`, `@SpringBootTest` + Testcontainers `@ServiceConnection`), Quarkus (`@QuarkusTest` + RestAssured + Dev Services, `@InjectMock`), Angular (TestBed + `HttpTestingController`, Vitest/Jest/Karma) e React (Vitest + Testing Library + MSW).
- **E2E e visual:** o resultado é sempre um arquivo `@playwright/test` no repo, que roda no gate e no CI. O **MCP do Playwright** serve para *explorar* a UI e descobrir roles/labels; essa exploração acontece dentro do agente `verifier`, então os snapshots grandes do navegador não entram na sua sessão. Critérios visuais usam `toHaveScreenshot`.
- **Ciclo de vida da app:** passos do gate com `needs_app` sobem a aplicação (`profile.app`), esperam o healthcheck e derrubam no final. O `webServer` do Playwright também funciona para o frontend.

## Agentes

Só três, e cada um existe por um motivo concreto:

| Agente | Modelo | Por quê |
|---|---|---|
| `reviewer` | opus | Review com **contexto limpo**, sem o viés de quem implementou. Só leitura; devolve JSON. |
| `verifier` | sonnet | Escreve testes de E2E/API que faltam e isola a exploração do navegador. Não toca em código de produção. |
| `implementer` | sonnet | Usado só para tasks `[P]` independentes em paralelo, cada uma no seu git worktree. |

A orquestração é feita pela própria sessão principal; não existe um "agente orquestrador". Intake, PRD, tech spec e decomposição viraram uma única skill, porque são a mesma linha de raciocínio, e quebrá-las em agentes só multiplicava handoffs e releitura de arquivos.

## Modo headless / CI

Para rodar sem supervisão (CI, máquina de build, background), use o runner. **O loop de controle é código**: o modelo é chamado em cada etapa via `claude -p` com JSON Schema, e o gate é re-executado pelo próprio runner, então nenhuma etapa consegue simplesmente declarar que está verde.

```bash
RUN="python3 ~/.claude/plugins/.../ravend/scripts/ravend_run.py"   # ou $RAVEND_ROOT/scripts/ravend_run.py

$RUN "Adicionar filtro por categoria em /products"          # para após a spec se o nível for large
$RUN --resume add-category-filter --until pr                  # continua depois que você aprovou a spec
$RUN PROJ-123 --yes --until review --worktree --budget-usd 3   # sem checkpoint, em worktree separado
```

| Opção | Efeito |
|---|---|
| `--until spec\|build\|verify\|review\|pr` | Última etapa (padrão `review`; `pr` faz push e abre o PR). |
| `--yes` | Pula a aprovação da spec large. |
| `--max-fix-rounds N` | Rodadas de correção do gate e do review (padrão 2). Para antes se o mesmo P0/P1 reaparecer. |
| `--budget-usd X` | Teto de gasto por chamada (`--max-budget-usd`). |
| `--worktree` | Trabalha num worktree irmão na branch da feature. |
| `--permission-mode` | Padrão `acceptEdits`. Ferramentas liberadas: git, o script do Ravend e os comandos do seu gate/app. Em sandbox/container, use `bypassPermissions`. |

Códigos de saída: `0` concluído (ou pausado num checkpoint), `1` falha, `2` configuração faltando, `3` precisa de humano. Os logs de cada chamada ficam em `~/.ravend/projects/<id>/runs/headless-*`.

O runner precisa do perfil local. Numa máquina de CI, rode `/ravend:init` uma vez ou copie um `profile.json` para `$RAVEND_HOME/projects/<id>/`.

## Integrações

- **GitHub:** issues via `gh issue view`; PRs via `gh pr create`.
- **Jira:** configure o MCP remoto oficial da Atlassian no Claude Code (escopo local ou de usuário) e use `/ravend:spec PROJ-123`. Sem o MCP, o Ravend pede que você cole o conteúdo da issue.
- **Playwright MCP / Context7:** oferecidos pelo `/ravend:init` com versão fixa e escopo local (`@playwright/mcp@0.0.84`, `@upstash/context7-mcp@4.5.0`).

## Custo de contexto e desempenho

- **~1,5k tokens fixos por sessão** (descrições de skills e agentes; os hooks não custam contexto). Cada skill só carrega o corpo quando é usada. Confira com `claude --plugin-dir . plugin details ravend`.
- **O prompt cache é preservado.** O contexto injetado no início da sessão é estável; o estado mutável fica em arquivos lidos sob demanda.
- **Subagentes só onde compensam:** review (independência), E2E (isolar snapshots ruidosos) e tasks paralelas. O resto acontece na sessão principal, que reaproveita o cache em vez de pagar a releitura de arquivos num contexto novo.
- **Saída de ferramentas filtrada:** o gate devolve só os trechos de erro; os logs completos ficam em disco.
- **Modelo por papel:** opus no review, sonnet na implementação e na verificação.

## Desenvolvendo o plugin

```bash
claude --plugin-dir .                                   # usa o plugin a partir do checkout
python3 -m unittest discover -s tests                   # testes do runtime (gate, hooks, identidade)
claude plugin validate .                                # manifesto + marketplace (o aviso sobre CLAUDE.md é esperado)
claude plugin validate skills && claude plugin validate agents
claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit Agent --runs 1 --ablation none
```

Os evals em [`evals/`](evals/) montam um repositório fixture (Node, sem dependências) e medem o comportamento que importa:
- uma mudança trivial não gera spec;
- uma demanda grande gera spec large com critérios testáveis;
- o build é test-first e roda o gate;
- o review pega um bug de limite que a suíte verde não pega.

Rode os evals a cada mudança de skill ou agente; sem `--ablation none`, eles também comparam com o Claude Code sem o plugin.

Observação: no sandbox do `claude plugin eval` o filesystem do Bash é read-only (só Edit/Write escrevem). Por isso branch e commit não são avaliados ali; isso fica coberto pelos testes do runtime em `tests/`, onde um `claude` falso exercita o loop completo do runner headless.

Estrutura:
```
.claude-plugin/   plugin.json, marketplace.json
skills/           init, spec, build, verify, review, ship, run, learn, api-tests, e2e-playwright, stack-*
agents/           reviewer, verifier, implementer
hooks/hooks.json  SessionStart, PreToolUse, PostToolUse, Stop
scripts/          ravend.py (runtime: identidade, gate, app, hooks) · ravend_run.py (headless)
tests/            testes do runtime
evals/            cenários de avaliação + fixture
```

## Vindo do Ravend para OpenCode

A versão anterior (agentes e comandos do OpenCode em `.opencode/` e `.lla/`) continua no histórico git, na `main`. Mapeamento:

| Antes | Agora |
|---|---|
| 9 agentes + orchestrator | Sessão principal + `reviewer`, `verifier` e `implementer` |
| intake → PRD → tech spec → tasks (4 artefatos) | `/ravend:spec`: 1 arquivo, profundidade proporcional |
| `/sdd-qa` com regras em prompt | `gate fast/full` em script + hook de Stop |
| score 0–100 e regra de delta | gate binário + findings P0/P1 com evidência; no máximo 2 rodadas |
| guardrails em markdown | formatters/linters do projeto via hooks e gate |
| knowledge versionada com frequências seed | knowledge local por dev, capturada só de casos observados |
| `.lla/sdd/current` + `~/.ravend/archive` | `~/.ravend/projects/<id>/specs` + git (o arquivo antigo não é tocado) |

## Limitações conhecidas

- O hook de Stop roda o `gate fast` de forma síncrona. Mantenha o fast realmente rápido (< 2 min) e deixe o pesado no `gate full`.
- O paralelismo com `implementer` em worktrees é opt-in e conservador: só vale para tasks com arquivos disjuntos, e o merge é feito na sessão principal.
- Baselines de screenshot do Playwright dependem do SO/navegador. Gere-as no mesmo ambiente do CI.
- Windows nativo não foi testado (os scripts usam process groups POSIX); use WSL.

## Licença

[MIT](LICENSE)
