<div align="center">
<img src="./imgs/ravend-logo.png" alt="Ravend" width="160" />

# Ravend

**Da demanda ao PR, com testes e quality gate que o Claude não consegue pular.**
</div>

Ravend é um plugin do [Claude Code](https://claude.com/claude-code). Você descreve o que quer (em texto, por uma issue do Jira ou do GitHub) e ele conduz o trabalho até o PR:

```
spec ──▶ build (test-first) ──▶ verify ──▶ review ──▶ PR
```

Na prática, você vai usar quase sempre **um único comando**:

```text
/ravend:run Adicionar paginação em GET /products
```

O Ravend escreve a spec, implementa com testes, roda os testes e o lint do projeto, faz um review independente e, **se você autorizar**, abre o PR.

---

## Sumário
- [Começando (5 minutos)](#começando-5-minutos)
- [Exemplos do dia a dia](#exemplos-do-dia-a-dia)
- [Quando o Ravend te pergunta algo](#quando-o-ravend-te-pergunta-algo)
- [Quem decide o tamanho da demanda](#quem-decide-o-tamanho-da-demanda)
- [Usando os seus MCPs](#usando-os-seus-mcps)
- [Comandos, um por um](#comandos-um-por-um)
- [Quality gate: o que é e como rodar](#quality-gate-o-que-é-e-como-rodar)
- [Modo headless (sem você na frente)](#modo-headless-sem-você-na-frente)
- [Referência](#referência)

---

## Começando (5 minutos)

**Requisitos:** Claude Code 2.1+, `git`, Python 3.8+ e, para abrir PRs, o `gh` autenticado (`gh auth login`).

**1. Instale o plugin** (uma vez):
```text
/plugin install ravend --marketplace ferreiravpl/ravend
```
Reinicie a sessão do Claude Code depois.

**2. Configure o repositório** (uma vez por repositório, em cada máquina). Abra o Claude Code na pasta do projeto e rode:
```text
/ravend:init
```
O `init` faz três coisas, perguntando antes de cada uma:
- lê o projeto (pom.xml, package.json, CI…) e descobre quais comandos de build, teste e lint ele usa;
- lista os **MCPs que você já tem** e pergunta quais o Ravend deve usar em cada etapa (veja [Usando os seus MCPs](#usando-os-seus-mcps));
- oferece instalar o comando `ravend` no terminal, usado no [modo headless](#modo-headless-sem-você-na-frente).

**Nada é gravado no repositório**: a configuração fica em `~/.ravend/` na sua máquina.

**3. Peça algo:**
```text
/ravend:run Adicionar paginação em GET /products e na listagem do front
```

Pronto. Se fechar a sessão no meio, abra outra: ela mostra as specs em andamento e você continua com o próximo comando (veja [Retomar um trabalho](#retomar-um-trabalho)).

> Opcional: o plugin [`superpowers`](https://github.com/obra/superpowers) (`/plugin install superpowers@claude-plugins-official`) melhora brainstorming, debugging e disciplina de TDD. O Ravend usa as skills dele quando estão instaladas, mas funciona sem.

## Exemplos do dia a dia

Todos os exemplos abaixo são digitados **dentro do Claude Code**.

### Uma correção pequena
```text
/ravend:run Trocar o texto do botão "Salvar" para "Salvar alterações" na tela de perfil
```
O Ravend percebe que é trivial: não escreve spec, faz a mudança, roda o gate e pergunta se pode abrir o PR.

### Uma feature
```text
/ravend:run Permitir filtrar produtos por categoria na API e na tela de listagem
```
Ele escreve uma spec com critérios de aceite, implementa task por task (teste primeiro, depois o código), roda a suíte completa, faz o review e, no fim, pergunta se pode abrir o PR. Se a mudança for grande (vários módulos, contrato novo de API ou banco), ele **para antes de implementar** e te mostra a spec para aprovar.

### Um bug
```text
/ravend:run Bug: o total do carrinho fica negativo quando o cupom é maior que o valor dos itens
```
Primeiro ele escreve um teste que reproduz o bug (e confirma que o teste falha). Só depois corrige.

### A partir do Jira ou do GitHub
```text
/ravend:run PROJ-123
/ravend:run #45
/ravend:run https://github.com/minha-org/meu-repo/issues/45
```
Issues do GitHub são lidas pelo `gh`. Para o Jira, configure o [MCP da Atlassian](#integrações); sem ele, o Ravend pede para você colar o texto da issue.

### Só planejar, sem implementar
```text
/ravend:spec Migrar o cadastro de clientes para o novo serviço de endereços
```
Gera só a spec. Leia, ajuste o arquivo se quiser e, quando estiver ok:
```text
/ravend:build migrar-cadastro-enderecos
```

### Retomar um trabalho
Cada spec ganha um **slug** (um nome curto como `filtro-produtos-categoria`). Ao abrir uma sessão nova, o Ravend lista as specs em andamento com o slug e a próxima task. Para continuar, chame a etapa seguinte com o slug:
```text
/ravend:build filtro-produtos-categoria
/ravend:verify filtro-produtos-categoria
```

## Quando o Ravend te pergunta algo

Ele só para em três situações:

| Momento | Por quê |
|---|---|
| **Dúvida de regra de negócio** | Se algo na demanda muda o resultado e não dá para deduzir do código, ele pergunta em vez de inventar. |
| **Aprovar a spec** | Só em demandas grandes. Nas pequenas ele segue sozinho. |
| **Abrir o PR** | Sempre. Push e PR são visíveis para o time, então ele pede autorização. |

Ele também para e te chama se ficar travado: o mesmo erro 3 vezes seguidas, ou o review apontando o mesmo problema depois de 2 rodadas de correção.

## Quem decide o tamanho da demanda

**O próprio Ravend**, no começo do `/ravend:spec`. Ele lê a demanda e o código afetado e classifica em um dos quatro níveis, dizendo qual escolheu numa linha:

| Nível | Exemplo | O que muda para você |
|---|---|---|
| **trivial** | Corrigir um texto, ajustar um valor padrão (até ~2 arquivos, sem comportamento novo) | Sem spec. Vai direto para o código. |
| **small** | Novo filtro em um endpoint existente | Spec curta. Segue sem pedir aprovação. |
| **large** | Feature front + back, endpoint ou tabela nova, migração | Spec completa com design. **Para e pede sua aprovação antes de codar.** |
| **bug** | "O total fica negativo quando…" | Escreve primeiro o teste que reproduz o bug. |

Discordou da classificação? Force o nível:
```text
/ravend:spec --tier large Adicionar campo "apelido" no cadastro
```

## Usando os seus MCPs

O Ravend se adapta às ferramentas que **você** já usa. No `/ravend:init`, ele lista os seus servidores MCP (os seus, os do projeto, os de plugins e os conectores do claude.ai) e pergunta, papel por papel, quais entram no fluxo:

```text
Você tem um MCP de contexto do código? Selecione os que o Ravend deve usar ao explorar e revisar.
  [x] serena        busca semântica e navegação por símbolos
  [ ] Nenhum

Você tem um MCP para o seu git (GitHub/GitLab)?
  [x] github        ler issues, ver checks de CI, abrir o PR
  [ ] Nenhum
```

Ele só pergunta sobre papéis para os quais você tem algum MCP compatível. Para os que ficaram sem nenhum, oferece instalar um padrão (Playwright para navegador, Context7 para documentação).

| Papel | Para que o Ravend usa | Em quais etapas |
|---|---|---|
| `issues` | Ler o ticket (Jira, Linear, GitHub/GitLab issues) | spec |
| `git` | Ler issues, ver checks de CI e comentários, abrir o PR | spec, review, ship |
| `context` | Busca semântica e navegação no código | spec, build, review |
| `docs` | Documentação das bibliotecas na versão que o projeto usa | spec, build |
| `knowledge` | Wiki e decisões internas (Confluence, Notion, Drive) | spec |
| `design` | Telas e tokens de design (Figma) | spec, build, verify |
| `browser` | Explorar a tela para escrever testes E2E | verify |
| `api` | Chamar e testar a API | verify |
| `database` | Consultar o schema e os dados reais (só leitura) | spec, build, verify |
| `observability` | Erros, logs e métricas para investigar bugs (Sentry, Datadog) | spec, verify |

A escolha fica no seu `profile.json`, então cada dev do time pode usar MCPs diferentes no mesmo repositório. Para refazer só essa parte:
```text
/ravend:init --integrations
```
Para ver o que você tem e o que está em uso, no terminal:
```bash
ravend mcp             # todos os seus MCPs, com status (sem mostrar tokens)
ravend integrations    # papéis disponíveis e os MCPs escolhidos
```

> Por que no `init` e não na instalação? O Claude Code não permite que um plugin faça perguntas na hora de instalar. Por isso, ao abrir um repositório ainda não configurado, o Ravend avisa para rodar o `/ravend:init`.

## Comandos, um por um

O `<slug>` é o nome curto da spec, mostrado quando ela é criada e no início de cada sessão.

| Comando | Quando usar | Exemplo |
|---|---|---|
| `/ravend:init` | Uma vez por repositório. `--refresh` quando os comandos do projeto mudarem; `--integrations` para refazer só a escolha de MCPs. | `/ravend:init` |
| `/ravend:run` | **O comando do dia a dia.** Faz tudo, do começo ao fim. | `/ravend:run PROJ-123` |
| `/ravend:spec` | Para planejar sem implementar ainda. | `/ravend:spec #45` |
| `/ravend:build` | Implementar uma spec. Para algo trivial, aceita a descrição direto, sem spec. | `/ravend:build filtro-produtos-categoria` |
| `/ravend:build --fix` | Corrigir o que o gate (`gate`), a verificação (`verify`) ou o review (`review`) apontou. | `/ravend:build filtro-produtos-categoria --fix review` |
| `/ravend:verify` | Rodar a suíte completa e conferir se cada critério de aceite tem um teste que passa. Escreve os testes de API/E2E que faltarem. | `/ravend:verify filtro-produtos-categoria` |
| `/ravend:review` | Review feito por outro agente, que não viu a implementação. Aponta problemas P0/P1/P2 com arquivo e linha. | `/ravend:review filtro-produtos-categoria` |
| `/ravend:ship` | Abrir o PR. Só funciona se o gate estiver verde e o review aprovado. | `/ravend:ship filtro-produtos-categoria` |
| `/ravend:learn` | Ensinar algo específico do projeto, para não repetir o erro. | `/ravend:learn Nunca usar LocalDateTime nos DTOs; o padrão do projeto é OffsetDateTime` |

`/ravend:run` é só `spec → build → verify → review → ship` em sequência. Use os comandos separados quando quiser controlar cada etapa.

## Quality gate: o que é e como rodar

O gate é a lista de comandos que **o seu projeto já usa** para dizer se o código está ok: compilar, testes, lint. O Ravend só considera algo pronto quando esses comandos terminam com sucesso. Quem decide é o exit code do comando, não a opinião do modelo.

Existem dois:

| Gate | O que roda | Quando roda |
|---|---|---|
| **fast** | Compilação + testes ligados aos arquivos alterados + lint desses arquivos. Deve levar menos de 2 minutos. | Depois de cada task do `/ravend:build`. Também quando o Claude tenta encerrar com código alterado e o gate não está verde. |
| **full** | O que o CI rodaria: build completo, todos os testes, lint, integração e E2E. | No `/ravend:verify` e antes do `/ravend:ship`. |

**Você normalmente não precisa rodar o gate na mão**: o build, o verify e o ship rodam sozinhos. Se quiser rodar:

- **Dentro do Claude Code:** `/ravend:verify <slug>`, ou simplesmente peça "roda o gate full".
- **No terminal**, com o comando `ravend` (o `/ravend:init` oferece instalar; veja [Comando `ravend`](#comando-ravend-no-terminal)), de dentro do repositório:
  ```bash
  ravend gate fast              # roda o gate rápido
  ravend gate full              # roda o gate completo
  ravend gate full --dry-run    # só mostra quais comandos seriam executados
  ravend status                 # specs em andamento e resultado do último gate
  ```

**De onde vêm os comandos?** O `/ravend:init` descobre e grava em `~/.ravend/projects/<projeto>/profile.json`. Para mudar, edite esse arquivo ou rode `/ravend:init --refresh`. Exemplo de um projeto Spring com Maven:

```json
"gate": {
  "fast": [
    {"name": "compile", "run": "./mvnw -q test-compile", "when": ["*.java"]},
    {"name": "unit", "run": "./mvnw -q surefire:test -Dtest={java_tests} -Dsurefire.failIfNoSpecifiedTests=false", "when": ["*.java"]}
  ],
  "full": [
    {"name": "verify", "run": "./mvnw -q verify", "timeout": 1800}
  ]
}
```
Exemplos completos para Spring, Quarkus, Angular e React: [`skills/init/references/profile.md`](skills/init/references/profile.md).

**Precisa desligar temporariamente?** `RAVEND_GATE=off` desliga a checagem ao encerrar a sessão; `RAVEND_FORMAT=off` desliga a formatação automática.

## Modo headless (sem você na frente)

O `/ravend:run` é interativo: você acompanha na sessão do Claude Code. O modo headless faz o mesmo pipeline **por um script no terminal**, sem sessão aberta.

**Para que serve:**
- **Deixar rodando enquanto você faz outra coisa.** Dispare uma demanda e volte quando terminar. Com `--worktree`, ele trabalha numa pasta separada e a sua cópia do repositório fica livre para você continuar mexendo.
- **Várias demandas em paralelo**, cada uma no seu worktree.
- **Rodar em CI** ou numa máquina de build, por exemplo a partir de uma issue com um label.
- **Mais garantia de que o gate foi respeitado:** o script roda o gate por conta própria entre as etapas. Se o modelo disser que está verde e não estiver, o script percebe e para.

**Quando não usar:** se você quer acompanhar e opinar durante o trabalho. Para isso, use `/ravend:run`.

### Como usar

Rode **no terminal**, dentro do repositório (que já precisa ter passado pelo `/ravend:init`), com o [comando `ravend`](#comando-ravend-no-terminal).

**Caso 1: rodar até o review, sem abrir PR** (o padrão)
```bash
ravend run "Adicionar filtro por categoria em GET /products"
```
Se a demanda for *large*, ele para depois de escrever a spec e mostra o comando para continuar. Revise a spec (o caminho aparece na saída) e retome:
```bash
ravend run --resume filtro-produtos-categoria
```

**Caso 2: do começo ao PR, sem nenhuma pausa**
```bash
ravend run PROJ-123 --yes --until pr
```

**Caso 3: várias demandas em paralelo, em segundo plano**
```bash
ravend run "#45" --worktree > ravend-45.log 2>&1 &
ravend run "#46" --worktree > ravend-46.log 2>&1 &
```
Cada demanda trabalha numa pasta irmã do repositório (`../meu-repo-<slug>`), na sua própria branch, com o próprio resultado de gate. Se o gate precisar subir a aplicação, as execuções se revezam para não disputar a mesma porta. Sem `--worktree`, o Ravend recusa uma segunda execução na mesma pasta.

**Caso 4: só gerar a spec para revisar depois**
```bash
ravend run "Migrar cadastro de clientes para o serviço de endereços" --until spec
```

**Caso 5: em CI ou container descartável, com teto de gasto**
```bash
ravend run "$ISSUE_URL" --yes --until pr --budget-usd 3 --permission-mode bypassPermissions
```
Use `bypassPermissions` só em ambiente isolado (container/sandbox). A máquina de CI também precisa do `profile.json`: rode `/ravend:init` lá uma vez ou copie o arquivo para `~/.ravend/projects/<projeto>/`.

### Parâmetros

| Parâmetro | Para que serve | Padrão |
|---|---|---|
| `"<demanda>"` | Texto, `PROJ-123`, `#45` ou URL da issue. | — |
| `--resume <slug>` | Continuar uma spec que já existe (considerada aprovada). | — |
| `--until <etapa>` | Até onde ir: `spec`, `build`, `verify`, `review` ou `pr` (`pr` faz push e abre o PR). | `review` |
| `--yes` | Não parar para aprovar spec *large*. | desligado |
| `--worktree` | Trabalhar numa pasta separada (git worktree), sem mexer na sua cópia atual. | desligado |
| `--max-fix-rounds N` | Quantas vezes tentar corrigir falhas do gate/review antes de desistir e pedir ajuda. | `2` |
| `--budget-usd X` | Gasto máximo em dólares **por chamada** ao Claude. | sem limite |
| `--model <modelo>` | Modelo usado em todas as etapas. | o padrão do seu Claude Code |
| `--permission-mode <modo>` | Permissões do Claude. `acceptEdits` libera edição de arquivos, git, os comandos do seu gate e os seus MCPs escolhidos (cada um só nas etapas do papel dele). | `acceptEdits` |

### Como saber o resultado

O script imprime uma linha por etapa e termina com um código de saída:

| Código | Significado | O que fazer |
|---|---|---|
| `0` | Terminou (ou parou de propósito para você aprovar a spec). | Ver a saída. |
| `1` | Erro inesperado. | Ver os logs. |
| `2` | Falta configuração (sem `/ravend:init`, slug não existe…). | Ler a mensagem. |
| `3` | Precisa de você (pergunta em aberto, review que não convergiu, gate que não ficou verde). | Abrir o Claude Code e continuar com `/ravend:build <slug> --fix …` ou `--resume`. |

Os logs de cada chamada ficam em `~/.ravend/projects/<projeto>/runs/headless-*`.

### Comando `ravend` no terminal

O `/ravend:init` oferece instalar. Para instalar depois, peça ao Claude ("instala o comando ravend") ou rode no terminal:
```bash
python3 "$(ls -d ~/.claude/plugins/cache/*/ravend/*/ | sort -V | tail -1)scripts/ravend.py" install-cli
```
Isso cria `~/.local/bin/ravend`, que sempre aponta para a versão instalada do plugin. Se `~/.local/bin` não estiver no seu `PATH`, a saída mostra a linha para adicionar no `.bashrc`/`.zshrc`.

| Comando | O que faz |
|---|---|
| `ravend run "<demanda>" [opções]` | Pipeline headless (`ravend run --help`) |
| `ravend gate fast\|full [--dry-run]` | Quality gate da pasta atual |
| `ravend status` | Specs em andamento e último gate |
| `ravend mcp` / `ravend integrations` | Seus MCPs / os escolhidos para o Ravend |

---

## Referência

Detalhes de funcionamento. Não é preciso ler para usar.

### Onde ficam os dados

Tudo fica na sua máquina, nunca no repositório. Assim várias pessoas usam o Ravend no mesmo repo sem conflito. O que o time vê é o PR: o `/ravend:ship` coloca nele o resumo, os critérios de aceite com o teste que prova cada um, o resultado do gate e o veredito do review.

```
~/.ravend/projects/github.com-org-repo/     (ou $RAVEND_HOME/projects/…)
├── profile.json     comandos do gate, formatters, como subir a app, arquivos protegidos
├── project.md       notas curtas sobre o projeto, lidas no início de cada sessão
├── knowledge/       lições salvas com /ravend:learn
├── specs/<slug>/    spec.md, verify.md, review-N.md
├── runs/            logs do gate e do modo headless
└── state/<pasta>/   último gate e sessão em build, separados por clone/worktree
```

O nome da pasta vem do remote `origin`, então é o mesmo em todos os clones e worktrees. Pode editar ou apagar qualquer arquivo; apagar a pasta do projeto "desinstala" o Ravend daquele repo.

### Hooks

Ficam inativos em repositórios sem `/ravend:init`.

| Hook | O que faz |
|---|---|
| Início da sessão | Mostra o projeto, as notas, as lições salvas e as specs em andamento. |
| Antes de editar | Bloqueia edição dos `protected_paths` (`.env`, chaves, código gerado…). |
| Depois de editar | Roda o formatter configurado no arquivo editado. |
| Ao encerrar | Só durante um `/ravend:build`: se o código mudou desde o último gate verde, roda o `gate fast` e não deixa o Claude encerrar com ele vermelho. Depois de 3 bloqueios seguidos, libera e pede sua intervenção. |

### Testes

- **Unit e API:** ficam no repositório, no estilo do projeto. As skills de stack (`stack-spring`, `stack-quarkus`, `stack-angular`, `stack-react`) trazem os padrões de cada uma e são carregadas automaticamente.
- **E2E e visual:** viram arquivos `@playwright/test` no repositório e rodam no gate e no CI. O MCP do Playwright só é usado para explorar a tela e descobrir seletores, dentro de um agente separado, para não poluir a sua sessão.
- **App rodando:** passos do gate marcados com `needs_app` sobem a aplicação (`profile.app`), esperam o healthcheck e derrubam no final.

### Agentes

| Agente | Por que existe |
|---|---|
| `reviewer` (opus) | Review com contexto limpo, sem o viés de quem implementou. Só lê. |
| `verifier` (sonnet) | Escreve testes de API/E2E que faltam e isola a exploração do navegador. Não mexe em código de produção. |
| `implementer` (sonnet) | Só para tasks independentes marcadas `[P]`, em paralelo, cada uma no seu worktree. |

O resto acontece na sua sessão principal.

### Integrações

- **GitHub:** issues via `gh issue view`, PRs via `gh pr create`.
- **Jira:** configure o MCP remoto oficial da Atlassian no Claude Code e use `/ravend:spec PROJ-123`.
- **Seus MCPs:** escolhidos por papel no `/ravend:init` (veja [Usando os seus MCPs](#usando-os-seus-mcps)). Se você não tiver um para navegador ou documentação, o `init` oferece instalar Playwright e Context7, com versão fixa e só para você (escopo local).
- **Worktrees:** MCPs de escopo local ficam registrados no caminho da pasta principal. No modo headless com `--worktree`, o Ravend os repassa para o worktree automaticamente.

### Custo de contexto

- Cerca de 1,5k tokens fixos por sessão (as descrições das skills). O conteúdo de cada skill só é carregado quando ela é usada.
- O gate devolve só o trecho do erro; o log completo fica em disco.
- Subagentes só onde compensam (review, E2E, tasks paralelas). Confira com `claude --plugin-dir . plugin details ravend`.

### Limitações conhecidas

- A checagem ao encerrar roda o `gate fast` de forma síncrona. Mantenha o fast abaixo de 2 minutos e deixe o pesado no full.
- O paralelismo com `implementer` é conservador: só para tasks que mexem em arquivos diferentes.
- Screenshots de referência do Playwright dependem do SO e do navegador. Gere-as no mesmo ambiente do CI.
- Windows nativo não foi testado; use WSL.

### Desenvolvendo o plugin

```bash
claude --plugin-dir .                                   # usa o plugin a partir do checkout
python3 -m unittest discover -s tests                   # testes do runtime
claude plugin validate . && claude plugin validate skills --strict && claude plugin validate agents
claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit Agent --runs 1 --ablation none
```

Os evals em [`evals/`](evals/) usam um repositório fixture e verificam que uma mudança trivial não gera spec, que uma demanda grande gera spec large com critérios testáveis, que o build é test-first e roda o gate, e que o review pega um bug de limite que a suíte verde não pega. Rode-os a cada mudança de skill ou agente.

```
.claude-plugin/   plugin.json, marketplace.json
skills/           init, spec, build, verify, review, ship, run, learn, api-tests, e2e-playwright, stack-*
agents/           reviewer, verifier, implementer
hooks/hooks.json  SessionStart, PreToolUse, PostToolUse, Stop
scripts/          ravend.py (runtime) · ravend_run.py (headless)
tests/            testes do runtime
evals/            cenários de avaliação + fixture
```

## Licença

[MIT](LICENSE)
