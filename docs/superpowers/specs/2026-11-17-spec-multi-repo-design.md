# Spec multi-repo — design

Data: 2026-11-17 · Status: rascunho para aprovação · Fora deste design: PR/merge/CI entre repos ([#10](https://github.com/ferreiravpl/ravend/issues/10))

## Intenção

Em microsserviços, uma demanda raramente cabe num repo: um evento novo atravessa o repo de contratos, o serviço que publica e o serviço que consome. Hoje o Ravend amarra spec, gate, verify, review e CI a **um** repo, e trata os outros como só leitura (`related_repos`): a mudança no repo vizinho vira `Depends on` + pergunta bloqueante, e o fluxo para. O dev precisa conseguir **implementar em todos os repos envolvidos dentro de uma spec só**, sem perder as garantias que cada repo tem hoje.

## Objetivos

1. Uma spec declara os repos que toca; as tasks dizem em qual repo rodam.
2. Edição liberada só nos repos da spec; os demais continuam como hoje.
3. Cada repo mantém o próprio gate (fast e full), paths protegidos e formatter, mesmo quando a sessão foi aberta em outro repo.
4. Verify e review valem para o conjunto: a spec só avança quando **todos** os repos estão verdes, verificados e revisados **no código atual de cada um**.
5. O review enxerga todos os diffs juntos e checa a compatibilidade entre eles.
6. A spec de um repo só é o caso com um repo: um caminho de código, não dois.

## Não-objetivos (v1)

- **PR, merge e CI entre repos** — depende da decisão da [#10](https://github.com/ferreiravpl/ravend/issues/10). Na v1, quando tudo está verde e aprovado, o `next` para e entrega as branches prontas (ver *Fim do fluxo na v1*).
- **`ravend auto` com spec multi-repo** — exige um worktree por repo e caminhos relativos reescritos. Na v1 o runner recusa (código, saída 2) com mensagem clara.
- **Retomar a spec a partir de outro repo dela** — a spec é conduzida da sessão do *repo de origem*. Abrir a sessão em outro repo da spec não a encontra (v1).
- **Inferir dependências dos arquivos de build** — a ordem vem das `deps` das tasks.

## Anti-objetivos (seria fracasso mesmo funcionando)

- Um gate "do conjunto" que esconde o vermelho de um repo atrás do verde de outro.
- Editar um repo vizinho sem que o gate dele rode antes de a sessão terminar.
- Um review aprovado que não olhou o diff de algum repo da spec.
- Novos comandos ou campos que o dev precise configurar: tudo sai do `/ravend:spec` e do `next`.
- Qualquer coisa escrita dentro dos repos (continua tudo em `~/.ravend`).

## Restrições

- Runtime só stdlib, Python 3.8+; módulos importam só os anteriores (core → gating → mcp → detection → flow → ci → diagnostics → hooks → cli).
- Hooks: no-op sem profile, nunca quebram a sessão.
- Ordem das etapas só em `next_action`.
- O parser de frontmatter (`core._frontmatter`) é uma linha por chave — valores de lista vão numa linha.
- Claude Code só edita fora do cwd com o diretório adicionado (`/add-dir` ou `--add-dir`).
- Repos de uma spec precisam ter profile próprio (o gate daquele repo é o que garante o código dele).

## Abordagens consideradas

| | Como | Prós | Contras |
|---|---|---|---|
| **A. Spec coordenadora + filhas** | Uma spec "mãe" lista repos e ordem; cada repo ganha uma spec normal; `next` da mãe delega. | Reaproveita o runtime quase sem mudança. | Dois níveis de spec; review de cada filha vê um repo só, a checagem entre repos vira etapa extra. |
| **B. Uma spec, tasks por repo** ✅ | `repos:` na spec, `repo:` em cada task; verify/review/approvals registrados com a impressão digital de cada repo. | Um modelo só (1 repo = caso particular); um review vê tudo; é o que o dev descreveu. | Refatora os registros do `flow.py`. |
| C. Pasta-pai como monorepo virtual | Tratar a pasta que contém os repos como um projeto. | — | Não é repo git (hooks desligados, sem project id); gate único quebra a independência de deploy. Descartada. |

**Escolhida: B** (decisão do dev, 2026-11-17).

## O que foi decidido

### 1. Declaração na spec

Frontmatter, uma linha, caminhos relativos ao repo de origem; o repo de origem é implícito:

```yaml
repos: ../contracts, ../consumer
```

- Nome de cada repo = nome da pasta (`contracts`, `consumer`); o de origem é o nome da pasta dele. Nomes repetidos → erro de spec (`next` responde `answer` com a pergunta bloqueante). O nome só serve para escrever a spec; **nos registros, cada repo é identificado pelo `project_id`** (vem do remote, é igual em todo clone e worktree), para que retomar de outro checkout não invalide verify/review. *(decisão do Claude)*
- **Repos participantes** = os que têm ao menos uma task. O repo de origem guarda a spec, mas só participa (branch, gate, verify, review, Stop) se tiver task. Um repo em `repos:` sem nenhuma task → erro de spec (`answer`). *(decisão do Claude)*
- Sem `repos:` → spec de um repo, exatamente como hoje.
- Tasks ganham `repo:` (ausente = repo de origem); `files:` são relativos àquele repo:

```
- [ ] T1: evento OrderPlaced v2 — repo: contracts — files: src/main/java/.../OrderPlaced.java — proves: AC1 — deps: none
- [ ] T2: publicar v2 — files: src/main/java/.../OrderService.java — proves: AC2 — deps: T1
- [ ] T3: consumir v2 sem quebrar v1 — repo: consumer — files: ... — proves: AC3 — deps: T1
```

- O `/ravend:spec` decide os repos: lê os irmãos (o `project` passa a incluir `siblings` com `has_profile`) e planeja edição nos que a demanda exige. Um irmão sem profile não entra em `repos:` → continua `Depends on` + pergunta "rode /ravend:init em X". `related_repos` que não estão em `repos:` continuam só leitura.

### 2. Validação (`next`, código)

Antes de qualquer etapa, para spec com `repos:`, o `next` confere cada repo e responde `answer` (pergunta bloqueante) se:
- o caminho não existe ou não é repo git;
- o repo não tem profile;
- uma task cita `repo:` que não está em `repos:`.

O `next` passa a devolver `repos: [{name, project_id, path, abs, branch, on_branch, has_profile}]` (só os participantes) para as skills.

**Aprovação presa ao conjunto de repos** *(decisão do Claude)*: toda spec multi-repo precisa de aprovação registrada pelo runtime (`ravend spec approve`), qualquer tier, e a aprovação grava o conjunto de repos participantes (por `project_id`). Se o conjunto mudar depois (alguém acrescentou um repo em `repos:` ou uma task com `repo:` novo), o `next` volta para `approve`, e os hooks liberam edição só nos repos do conjunto **aprovado**. Assim o agente não destrava sozinho um repo editando a spec.

### 3. Branch

Mesma branch (`spec.branch`) em todos os repos. O build cria/troca a branch num repo antes da primeira task dele (mesma regra de hoje: árvore com mudanças alheias → para e pergunta). Garantia em código: `verify record` e `review record` recusam se algum repo da spec não está na branch da spec.

### 4. Edição e hooks resolvem o repo do arquivo

Novo resolvedor nos hooks: dado o arquivo editado, se ele está dentro de um repo da **spec ativa** do repo da sessão (a spec da branch atual ou a única ativa, mesma regra do `_pick_spec`), o hook usa o root e o profile **daquele** repo.

| Hook | Mudança |
|---|---|
| `PreToolUse` Edit/Write | Repo do conjunto aprovado da spec ativa → libera (mesmo se estiver em `related_repos`) e aplica `protected_paths` / regras de agente **daquele** repo. Só quando a spec ativa é multi-repo: arquivo num repo irmão **com profile** fora do conjunto aprovado → nega ("acrescente o repo em `repos:`; a spec volta para a sua aprovação"). Sem spec ativa, spec de um repo ou spec ativa ambígua → **exatamente como hoje** *(decisão do Claude: nada muda para quem usa spec de um repo)*. |
| `PostToolUse` | Formatter do profile do repo do arquivo, com `cwd` relativo a ele. |
| `Stop` | `ravend arm` grava em `armed.json` a lista de repos da spec ativa. O hook roda o gate fast em **cada** repo cuja árvore difere do `green.fast` dele; bloqueia se qualquer um falhar, com o relatório de cada repo. Limite de bloqueios igual ao de hoje. |
| `SessionStart` | Com spec multi-repo ativa, lista os repos dela e avisa que a sessão precisa deles adicionados (`/add-dir <caminho>`) para editar. |

O gate de cada repo continua rodando com a pasta daquele repo como cwd, e grava o estado no `state/` daquele repo (nenhuma mudança no `gating.py`).

### 5. Registros por repo (`flow.py`)

Os registros de `state.json` passam a guardar a impressão digital de cada repo:

```json
"verify":  [{"fingerprints": {"<project_id origem>": "ab12", "<project_id contracts>": "cd34"}, "gates": {"<project_id origem>": "PASS", "<project_id contracts>": "PASS"}, "uncovered": [], "at": "..."}],
"reviews": [{"n": 1, "fingerprints": {...}, "verdict": "APPROVED", "lenses": [...], ...}]
```

- "Este código" = todas as impressões digitais atuais iguais às registradas. Mudou um repo → verify e review deixam de valer para o conjunto.
- `verify record` lê o último `gate full` **de cada repo** (do `state/` daquele repo) e recusa se algum não rodou no código atual dele; o resultado do conjunto é PASS só se todos forem PASS.
- `review record` grava o mapa atual.
- Registros antigos (`fingerprint` no topo) são lidos como `{<project_id do repo de origem>: fingerprint}` — specs em andamento continuam válidas.
- Spec de um repo: o mapa tem uma entrada. Um caminho de código.

### 6. Ordem das tasks

`next` escolhe a primeira task pendente cujas `deps` estão todas prontas (hoje: a primeira pendente). Isso vale também para spec de um repo e não muda o resultado quando as tasks estão em ordem. A resposta `build` inclui `repo` e `repo_path` da task.

### 7. Áreas de risco

`risk_hits` roda por repo: arquivos alterados na branch daquele repo + `files:` das tasks daquele repo, contra o `profile.risk` **daquele** repo. Os hits levam o nome do repo. Uma aprovação vale para a spec inteira; as lentes exigidas são a união.

Spec com 2+ repos exige a lente `contract` no review (somada às de risco), em código.

### 8. Etapas (skills)

| Skill | Mudança |
|---|---|
| `spec` | Seção 1: planejar edição em irmãos com profile; escrever `repos:` e `repo:` nas tasks; ordenar por dependência (lib/contrato antes de quem usa). Template ganha os dois campos. |
| `build` | Para a task, `cd` no `repo_path` do `next`; troca de branch ali; `$RV gate fast` e commit **naquele repo**; `$RV task done` sempre a partir do repo de origem. Se o diretório não estiver acessível na sessão, pede `/add-dir`. Fix de `verify`/`review` idem, por repo. **Sem `ravend:implementer` em paralelo numa spec multi-repo (v1)**: o worktree isolado só existe para o repo da sessão, e o implementer editaria o checkout principal do vizinho. O `next` devolve `parallel: false` e a skill roda em sequência. *(decisão do Claude)* |
| `verify` | `$RV gate full` em cada repo da spec; matriz critério × teste atravessa os repos (arquivo de teste com o nome do repo); `verify record` a partir do repo de origem. |
| `review` | Passa ao reviewer a lista de repos com o base ref de cada um (`git -C <repo> merge-base HEAD <base daquele repo>`). O reviewer olha todos os diffs e aplica a lente `contract` com um item a mais: cada repo pode ir para produção sozinho e em qualquer ordem (consumidor tolera o formato antigo e o novo; produtor não remove campo que alguém ainda lê). |
| `continue` | Ação nova `handoff` (abaixo). |

### 9. Fim do fluxo na v1

Tudo verde, verificado e revisado no código atual de todos os repos → para spec multi-repo o `next` responde **`handoff`** (em vez de `ship`): "Pronta em N repos, branch `<branch>` em cada um; a abertura dos PRs entre repos ainda não é conduzida pelo Ravend (#10)." com a lista de repos e commits. O `continue` mostra e para. O dev abre os PRs; `ravend spec done <slug>` fecha a spec. Spec de um repo continua com `ship` → CI como hoje.

### 10. `ravend auto`

Recusa spec com `repos:` (saída 2, mensagem apontando o uso interativo), em código.

## Deixado para quem implementa

- Nomes internos das funções e onde o resolvedor de repo mora (`hooks.py` ou `flow.py`, respeitando a ordem de imports).
- Formato exato da mensagem do `handoff` e do aviso de `/add-dir`.
- Como o `SessionStart` detecta se o diretório já foi adicionado (se der para detectar; senão, só avisa).
- Testes: seguir o padrão de `tests/test_ravend.py` (repos git reais em pasta temporária). Cobrir no mínimo: spec com 2 repos do approve ao handoff; verify invalidado por mudança só no repo vizinho; hook libera/nega por repo; Stop roda o gate do vizinho; risco por repo; registros antigos migrados; `ravend auto` recusa; ordem por `deps`.
- Evals: um caso novo de `spec` em fixture sintética com dois repos (lib + serviço), provando `repos:` e `repo:` nas tasks na ordem certa; rodar os evals de `spec`, `continue` e `build` afetados.
- Atualizar README (o que o dev vê: spec em vários repos, `/add-dir`, limite da v1) e `docs/ARCHITECTURE.md` (tabela do `next`, hooks, dados locais) no mesmo PR.
