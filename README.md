<div align="center">
<img src="./imgs/ravend-logo.png" alt="Ravend" width="160" />

# Ravend

**Da demanda ao PR, com testes e quality gate que o Claude não consegue pular.**
</div>

Ravend é um plugin do [Claude Code](https://claude.com/claude-code). Você descreve o que quer (em texto, por uma issue do Jira ou do GitHub) e ele conduz o trabalho até o PR:

```
spec ──▶ build (teste primeiro) ──▶ verify ──▶ review ──▶ PR
```

No dia a dia você usa **três comandos**:

| Comando | Para quê |
|---|---|
| `/ravend:start <demanda>` | Começar algo novo. |
| `/ravend:continue` | Continuar de onde parou. O Ravend sabe qual é o próximo passo. |
| `/ravend:doctor` | Descobrir por que algo não está funcionando. |

O resto (as etapas, o gate, o tamanho da demanda) você vê acontecer. Não precisa decorar.

---

## Sumário
- [Começando (5 minutos)](#começando-5-minutos)
- [Os três comandos do dia a dia](#os-três-comandos-do-dia-a-dia)
- [Exemplos](#exemplos)
- [Quando o Ravend te pergunta algo](#quando-o-ravend-te-pergunta-algo)
- [Como ele decide o próximo passo](#como-ele-decide-o-próximo-passo)
- [Usando os seus MCPs](#usando-os-seus-mcps)
- [Todos os comandos](#todos-os-comandos)
- [Quality gate](#quality-gate)
- [Modo sem supervisão: `ravend auto`](#modo-sem-supervisão-ravend-auto)
- [Comando `ravend` no terminal](#comando-ravend-no-terminal)
- [Referência](#referência)

---

## Começando (5 minutos)

**Requisitos:** Claude Code 2.1+, `git`, Python 3.8+ e, para abrir PRs, o `gh` autenticado (`gh auth login`) ou um MCP de git.

**1. Instale o plugin** (uma vez por máquina) e reinicie a sessão do Claude Code:
```text
/plugin install ravend --marketplace ferreiravpl/ravend
```

**2. Configure o repositório** (uma vez por repositório, em cada máquina). Abra o Claude Code na pasta do projeto e rode:
```text
/ravend:init
```
O `init` pergunta antes de cada passo e:
- lê o projeto (pom.xml, package.json, CI…) e descobre os comandos de build, teste e lint;
- lista os **MCPs que você já tem** e pergunta quais usar em cada etapa (veja [Usando os seus MCPs](#usando-os-seus-mcps));
- oferece instalar o comando `ravend` no terminal;
- termina rodando o `doctor` e mostra o que ainda falta.

**Nada é gravado no repositório**: a configuração fica em `~/.ravend/`, na sua máquina. Para refazer qualquer parte depois, rode `/ravend:init` de novo; ele pergunta o que você quer refazer.

**3. Peça algo:**
```text
/ravend:start Adicionar paginação em GET /products e na listagem do front
```

## Os três comandos do dia a dia

### `/ravend:start <demanda>`
Começa uma demanda nova e conduz até o PR. Aceita texto livre, chave do Jira (`PROJ-123`) ou issue do GitHub (`#45` ou a URL).

O que acontece:
1. Escreve uma **spec**: critérios de aceite testáveis e uma lista de tasks, do tamanho da demanda.
2. Se a demanda for grande, **para e pede sua aprovação** da spec.
3. Implementa task por task, **teste primeiro**, rodando o quality gate e fazendo um commit por task.
4. **Verifica**: roda a suíte completa e confere se cada critério tem um teste que passa.
5. Faz um **review** com um agente que não viu a implementação.
6. Se o review ou a verificação apontarem problemas, corrige e verifica de novo (no máximo 2 rodadas).
7. **Pergunta se pode abrir o PR.**

### `/ravend:continue`
Retoma o trabalho de onde parou: depois de fechar a sessão, de um `/clear`, ou quando você não lembra em que etapa estava. O Ravend olha o estado da spec (tasks, último gate, última verificação, último review) e executa o próximo passo.

Se houver mais de uma spec em andamento, ele usa a da branch atual ou pergunta qual. Para escolher direto: `/ravend:continue <slug>` (o slug é o nome curto da spec, mostrado quando ela é criada).

### `/ravend:doctor`
Confere Python, git, o perfil do projeto, se os comandos do gate existem, se os MCPs escolhidos estão conectados, o `gh` e o comando de terminal. Para cada problema, diz o que fazer. Também existe no terminal: `ravend doctor`.

## Exemplos

Digitados **dentro do Claude Code**.

**Uma correção pequena**
```text
/ravend:start Trocar o texto do botão "Salvar" para "Salvar alterações" na tela de perfil
```
É trivial: sem spec. Ele faz a mudança, roda o gate e pergunta se pode abrir o PR.

**Uma feature**
```text
/ravend:start Permitir filtrar produtos por categoria na API e na tela de listagem
```
Spec, build test-first, verificação e review. Se for grande (vários módulos, contrato novo de API ou banco), para antes de implementar para você aprovar a spec.

**Um bug**
```text
/ravend:start Bug: o total do carrinho fica negativo quando o cupom é maior que o valor dos itens
```
Primeiro escreve um teste que reproduz o bug e confirma que ele falha. Só depois corrige.

**A partir do Jira ou do GitHub**
```text
/ravend:start PROJ-123
/ravend:start #45
/ravend:start https://github.com/minha-org/meu-repo/issues/45
```

**Fechou a sessão no meio**
```text
/ravend:continue
```
Ele mostra onde parou (por exemplo, "Implementar T3 (2/5 prontas)") e segue.

## Quando o Ravend te pergunta algo

| Momento | Por quê |
|---|---|
| **Dúvida de regra de negócio** | Se algo na demanda muda o resultado e não dá para deduzir do código, ele pergunta em vez de inventar. |
| **Aprovar a spec** | Só em demandas grandes. Nas pequenas ele segue sozinho. |
| **Abrir o PR** | Sempre. Push e PR são visíveis para o time. |
| **Quando não consegue avançar** | Depois de 2 rodadas de correção sem resolver, ou se o review apontar o mesmo problema de novo, ele para e te mostra o que tentou. |

## Como ele decide o próximo passo

Quem decide é código, não o modelo. O comando `ravend next` lê o que está gravado e responde uma ação:

| Situação | Próximo passo |
|---|---|
| Spec grande ainda não aprovada | Pedir sua aprovação |
| Spec com pergunta em aberto | Perguntar a você |
| Tem task pendente | Implementar a próxima task |
| Tasks prontas, mas o código ainda não foi verificado (ou mudou desde a verificação) | Verificar |
| Gate vermelho ou critério sem teste | Corrigir e verificar de novo |
| Verificado, mas sem review deste código | Review |
| Review com problema P0/P1 | Corrigir e verificar de novo |
| Tudo verde e aprovado neste código | Abrir o PR (com sua autorização) |

"Este código" quer dizer exatamente o conteúdo atual dos arquivos: se qualquer coisa mudar depois de uma verificação ou review, ela deixa de valer e o passo é refeito.

O tamanho da demanda também é decidido no começo, na spec:

| Tamanho | Exemplo | O que muda |
|---|---|---|
| **trivial** | Corrigir um texto, ajustar um valor padrão (até ~2 arquivos) | Sem spec. Direto para o código. |
| **small** | Novo filtro num endpoint existente | Spec curta. Segue sem pedir aprovação. |
| **large** | Feature front + back, endpoint ou tabela nova, migração | Spec completa com design. Pede sua aprovação antes de codar. |
| **bug** | "O total fica negativo quando…" | Escreve primeiro o teste que reproduz o bug. |

Discordou? Force o tamanho com `/ravend:spec --tier large <demanda>` e depois `/ravend:continue`.

## Usando os seus MCPs

O Ravend usa as ferramentas que **você** já tem. No `/ravend:init`, ele lista os seus servidores MCP (os seus, os do projeto, os de plugins e os conectores do claude.ai) e pergunta, papel por papel, quais entram no fluxo:

```text
Você tem um MCP de contexto do código? Selecione os que o Ravend deve usar ao explorar e revisar.
  [x] serena        busca semântica e navegação por símbolos
  [ ] Nenhum
```

Ele só pergunta sobre papéis para os quais você tem algum MCP compatível. Para navegador e documentação, se você não tiver nenhum, oferece instalar Playwright e Context7.

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

A escolha fica no seu `profile.json`, então cada dev do time pode usar MCPs diferentes no mesmo repositório. Para mudar, rode `/ravend:init` e escolha "integrações MCP". No terminal: `ravend mcp` lista todos os seus MCPs (sem mostrar tokens) e `ravend integrations` mostra os escolhidos.

## Todos os comandos

Os três do dia a dia chamam as etapas abaixo na ordem certa. Você pode chamar uma etapa direto quando quiser controle fino; cada uma também aparece com descrição no menu `/ravend:`.

| Comando | O que faz | Exemplo |
|---|---|---|
| `/ravend:start` | Começa uma demanda e conduz até o PR. | `/ravend:start PROJ-123` |
| `/ravend:continue` | Executa o próximo passo da spec em andamento, até precisar de você. | `/ravend:continue` |
| `/ravend:doctor` | Diagnostica a configuração e diz o que falta. | `/ravend:doctor` |
| `/ravend:init` | Configura o repositório na sua máquina. Rodando de novo, pergunta o que refazer. | `/ravend:init` |
| `/ravend:spec` | Só planeja: escreve a spec, sem implementar. Aceita `--tier` para forçar o tamanho. | `/ravend:spec #45` |
| `/ravend:build` | Implementa as tasks (teste primeiro, gate, commit). Se a verificação ou o review apontaram problemas, corrige; o Ravend sabe o que falhou. Para algo trivial, aceita a descrição sem spec. | `/ravend:build filtro-categoria` |
| `/ravend:verify` | Roda a suíte completa, monta a matriz critério → teste e escreve os testes de API/E2E que faltam. Não mexe em código de produção. | `/ravend:verify filtro-categoria` |
| `/ravend:review` | Review por um agente que não viu a implementação. Findings P0/P1/P2 com arquivo, linha e cenário de falha. | `/ravend:review filtro-categoria` |
| `/ravend:ship` | Abre o PR. Recusa se o gate não estiver verde neste código ou se o review não estiver aprovado. Sempre pede confirmação. | `/ravend:ship filtro-categoria` |
| `/ravend:remember` | Guarda uma lição específica do projeto, para não repetir o erro. Aparece no início de cada sessão. | `/ravend:remember Nunca usar LocalDateTime nos DTOs; o padrão é OffsetDateTime` |

Carregadas automaticamente quando o assunto aparece (você não chama): `stack-spring`, `stack-quarkus`, `stack-angular`, `stack-react`, `api-tests` e `e2e-playwright`.

## Quality gate

O gate é a lista de comandos que **o seu projeto já usa** para dizer se o código está ok: compilar, testes, lint. O Ravend só considera algo pronto quando esses comandos terminam com sucesso. Quem decide é o exit code, não a opinião do modelo.

| Gate | O que roda | Quando |
|---|---|---|
| **fast** | Compilação + testes ligados aos arquivos alterados + lint desses arquivos. Deve levar menos de 2 minutos. | Depois de cada task. Também quando o Claude tenta encerrar durante um build com o código mudado. |
| **full** | O que o CI rodaria: build completo, todos os testes, lint, integração e E2E. | Na verificação e antes do PR. |

Você normalmente não roda o gate na mão. Se quiser: `/ravend:verify <slug>` dentro do Claude Code, ou `ravend gate full` no terminal (`ravend gate full --dry-run` só mostra os comandos).

**De onde vêm os comandos:** o `/ravend:init` descobre e grava em `~/.ravend/projects/<projeto>/profile.json`. Exemplo de um projeto Spring com Maven:

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

**Desligar temporariamente:** `RAVEND_GATE=off` desliga a checagem ao encerrar; `RAVEND_FORMAT=off` desliga a formatação automática.

## Modo sem supervisão: `ravend auto`

Faz o mesmo pipeline do `/ravend:start` **pelo terminal**, sem sessão aberta. Serve para deixar rodando enquanto você faz outra coisa, rodar várias demandas em paralelo ou rodar em CI.

O trabalho acontece sempre numa **pasta separada** (um git worktree ao lado do repositório, `../meu-repo-<slug>`, na branch da feature). A sua pasta fica livre e cada demanda tem a sua.

O próximo passo é decidido pelo mesmo `ravend next` do `/ravend:continue`, e o gate full é rodado pelo próprio script. Se o modelo disser que está verde e não estiver, o script percebe.

```bash
ravend auto "Adicionar filtro por categoria em GET /products"   # para quando estiver pronto para PR
ravend auto PROJ-123 --pr                                        # vai até abrir o PR
ravend auto "#45" --no-pause --pr                                # sem pausa para aprovar spec grande
ravend auto --resume filtro-categoria --pr                       # continua uma spec que você aprovou
```

Duas demandas em paralelo:
```bash
ravend auto "#45" > ravend-45.log 2>&1 &
ravend auto "#46" > ravend-46.log 2>&1 &
```
Se o gate precisar subir a aplicação, as execuções se revezam para não disputar a mesma porta.

| Opção | Para que serve |
|---|---|
| `--pr` | Ir até abrir o PR. Sem ela, para quando estiver pronto para PR. |
| `--no-pause` | Não parar para você aprovar uma spec grande. |
| `--resume <slug>` | Continuar uma spec que já existe. |
| `--budget-usd X` | Gasto máximo em dólares por chamada ao Claude. |
| `--model <modelo>` | Modelo usado em todas as etapas. |
| `--permission-mode <modo>` | Padrão `acceptEdits`: libera edição de arquivos, git, os comandos do seu gate e os seus MCPs (cada um só nas etapas do papel dele). Use `bypassPermissions` só em container/sandbox. |

| Saída | Significado | O que fazer |
|---|---|---|
| `0` | Terminou, ou parou de propósito (spec para aprovar, pronto para PR). | Ler a última linha. |
| `1` | Erro inesperado. | Ver os logs. |
| `2` | Falta configuração (sem `/ravend:init`, spec não existe, pasta ocupada). | Ler a mensagem; `ravend doctor` ajuda. |
| `3` | Precisa de você (pergunta em aberto, correção que não converge, etapa bloqueada). | Abrir o Claude Code na pasta do worktree e rodar `/ravend:continue`. |

Logs de cada chamada: `~/.ravend/projects/<projeto>/runs/auto-*`. Em CI, a máquina também precisa do `profile.json`: rode `/ravend:init` lá uma vez ou copie o arquivo.

## Comando `ravend` no terminal

O `/ravend:init` oferece instalar. Para instalar depois, peça ao Claude ("instala o comando ravend") ou rode:
```bash
python3 "$(ls -d ~/.claude/plugins/cache/*/ravend/*/ | sort -V | tail -1)scripts/ravend.py" install-cli
```
Isso cria `~/.local/bin/ravend`, que sempre aponta para a versão instalada do plugin. Se `~/.local/bin` não estiver no `PATH`, a saída mostra a linha para o `.bashrc`/`.zshrc`.

| Comando | O que faz |
|---|---|
| `ravend auto "<demanda>"` | Pipeline sem supervisão (`ravend auto --help`). |
| `ravend next [<slug>]` | Qual é o próximo passo de uma spec e por quê. |
| `ravend status` | Specs em andamento, o próximo passo de cada uma e o último gate. |
| `ravend doctor` | Confere a configuração e diz o que falta. |
| `ravend gate fast\|full [--dry-run]` | Roda o quality gate desta pasta. |
| `ravend mcp` / `ravend integrations` | Seus MCPs / os escolhidos para cada papel. |
| `ravend spec approve <slug>` | Aprova uma spec grande sem abrir o Claude Code (para depois usar `ravend auto --resume`). |

`ravend help` lista também os comandos de registro de estado que as skills usam (`task done`, `verify record`, `review record`), que você raramente vai precisar.

---

## Referência

Detalhes de funcionamento. Não é preciso ler para usar.

### Onde ficam os dados

Tudo fica na sua máquina, nunca no repositório. O que o time vê é o PR: o `/ravend:ship` coloca nele o resumo, os critérios de aceite com o teste que prova cada um, o resultado do gate e o veredito do review.

```
~/.ravend/projects/github.com-org-repo/     (ou $RAVEND_HOME/projects/…)
├── profile.json     comandos do gate, formatters, como subir a app, arquivos protegidos, MCPs
├── project.md       notas curtas sobre o projeto, lidas no início de cada sessão
├── knowledge/       lições salvas com /ravend:remember
├── specs/<slug>/    spec.md, verify.md, review-N.md, state.json (registros de verificação e review)
├── runs/            logs do gate e do ravend auto
└── state/<pasta>/   último gate e sessão em build, um por clone/worktree
```

O nome da pasta do projeto vem do remote `origin`, então é o mesmo em todos os clones e worktrees. Apagar essa pasta "desinstala" o Ravend daquele repositório.

### Hooks

Inativos em repositórios sem `/ravend:init`.

| Hook | O que faz |
|---|---|
| Início da sessão | Mostra o projeto, as notas, as lições, os MCPs escolhidos e as specs em andamento. |
| Antes de editar | Bloqueia edição dos `protected_paths` (`.env`, chaves, código gerado…). |
| Depois de editar | Roda o formatter configurado no arquivo editado. |
| Ao encerrar | Só durante um build: se o código mudou desde o último gate verde, roda o `gate fast` e não deixa o Claude encerrar com ele vermelho. Depois de 3 bloqueios seguidos, libera e pede sua intervenção. |

### Testes que o Ravend escreve

- **Unit e API:** no repositório, no estilo do projeto, com os padrões das skills de stack.
- **E2E e visual:** arquivos `@playwright/test` no repositório, que rodam no gate e no CI. O MCP de navegador só serve para explorar a tela, dentro de um agente separado.
- **App rodando:** passos do gate com `needs_app` sobem a aplicação (`profile.app`), esperam o healthcheck e derrubam no final.

### Agentes

| Agente | Por que existe |
|---|---|
| `reviewer` (opus) | Review com contexto limpo, sem o viés de quem implementou. Só lê. |
| `verifier` (sonnet) | Escreve testes de API/E2E que faltam e isola a exploração do navegador. |
| `implementer` (sonnet) | Só para tasks independentes marcadas `[P]`, em paralelo, cada uma no seu worktree. |

### Integrações

- **GitHub:** issues via `gh issue view`, PRs via `gh pr create`, ou pelo seu MCP de git.
- **Jira:** configure o MCP remoto da Atlassian no Claude Code e use `/ravend:start PROJ-123`. Sem ele, o Ravend pede para você colar o texto da issue.
- **Worktrees:** MCPs de escopo local ficam registrados no caminho da pasta principal; o `ravend auto` os repassa para o worktree.

### Custo de contexto

Cerca de 2k tokens fixos por sessão (as descrições das skills). O conteúdo de cada skill só é carregado quando ela é usada, e o gate devolve só o trecho do erro. Confira com `claude --plugin-dir . plugin details ravend`.

### Limitações conhecidas

- A checagem ao encerrar roda o `gate fast` de forma síncrona. Mantenha o fast abaixo de 2 minutos.
- O paralelismo com `implementer` só vale para tasks que mexem em arquivos diferentes.
- Screenshots de referência do Playwright dependem do SO e do navegador. Gere-as no mesmo ambiente do CI.
- Windows nativo não é suportado; use WSL.

### Desenvolvendo o plugin

```bash
claude --plugin-dir .                                   # usa o plugin a partir do checkout
python3 -m unittest discover -s tests                   # testes do runtime e do ravend auto
claude plugin validate . && claude plugin validate skills --strict && claude plugin validate agents
claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit Agent --runs 1 --ablation none
```

Os evals em [`evals/`](evals/) usam um repositório de exemplo e verificam que uma mudança trivial não gera spec, que uma demanda grande gera spec large com critérios testáveis, que o build é test-first e roda o gate, e que o review pega um bug de limite que a suíte verde não pega.

```
.claude-plugin/   plugin.json, marketplace.json
skills/           start, continue, doctor, init, spec, build, verify, review, ship, remember,
                  api-tests, e2e-playwright, stack-*
agents/           reviewer, verifier, implementer
hooks/hooks.json  SessionStart, PreToolUse, PostToolUse, Stop
scripts/          ravend.py (runtime + máquina de estados) · ravend_auto.py (ravend auto)
tests/            testes do runtime e do ravend auto
evals/            cenários de avaliação + repositório de exemplo
```

## Licença

[MIT](LICENSE)
