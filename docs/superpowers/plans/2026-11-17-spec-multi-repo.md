# Spec multi-repo — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** uma spec do Ravend declara os repos irmãos que toca e é implementada em todos eles, com gate, verify, review e paths protegidos de cada repo garantidos em código.

**Architecture:** tudo novo de spec/registro fica em `flow.py` (parse de `repos:`/`repo:`/`deps:`, repos participantes, registros com mapa de impressões digitais por `project_id`, aprovação presa ao conjunto de repos, `handoff`). Os hooks (`hooks.py`) ganham um resolvedor que troca root/profile para o repo do arquivo quando ele está no conjunto aprovado da spec ativa. Skills só executam o que o `next` devolve (`repo`, `repo_path`, `repos`, `parallel`).

**Tech Stack:** Python 3.8+ só stdlib · unittest · Markdown (skills) · `claude plugin eval`.

**Spec:** `docs/superpowers/specs/2026-11-17-spec-multi-repo-design.md` (leia antes de cada task).

## Global Constraints

- Runtime só biblioteca padrão, Python 3.8+ (`from __future__ import annotations` já está nos módulos).
- Ordem de imports: core → gating → mcp → detection → flow → ci → diagnostics → hooks → cli. Nenhum módulo importa um posterior.
- Hooks: no-op sem profile; nunca levantam exceção (o dispatcher já captura, mas o código novo não pode depender disso para casos normais como caminho inexistente).
- Nada é gravado dentro de repositório algum; tudo em `RAVEND_HOME`.
- Frontmatter é uma linha por chave: `repos: ../a, ../b`.
- Identidade de repo nos registros = `project_id(root)`; nome (pasta) só na spec.
- Spec sem `repos:` se comporta **exatamente** como hoje — os 50 testes atuais continuam passando sem alteração de asserção (só a migração de registros antigos é nova).
- Corpo das skills em inglês; `description`/`argument-hint` em pt-BR; README e ARCHITECTURE em pt-BR, sem histórico de mudanças no README.
- Nada de nomes de projetos reais em testes, evals, docs ou commits: domínios sintéticos (`shop`, `lib`, `pricing`).
- Commits como ferreiravpl (`git config user.email` = e-mail pessoal), Conventional Commits em pt-BR como o histórico, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Mesmo repo listado duas vezes** (`../lib` e `../lib/` ou um caminho absoluto) → um repo só, deduplicado por `project_id`; nomes repetidos de repos diferentes → pergunta bloqueante. Teste em Task 1.
2. **Repo da spec com gate vazio** (profile existe, `gate.full` sem passos) → `verify record` recusa; nunca conta como PASS. Teste em Task 2.
3. **Write de arquivo novo em pasta nova do vizinho** (o diretório ainda não existe) → o resolvedor sobe até o primeiro pai existente e acha o repo certo. Teste em Task 4.
4. **Vizinho com branch base diferente** (`master` no vizinho, `main` na origem) → arquivos alterados e risco do vizinho usam o `base_branch` do profile **dele**. Teste em Task 3.
5. **Caminho de repo que sumiu** depois do `arm` (pasta apagada/renomeada) → Stop hook não quebra; ignora o repo e avisa por `systemMessage`. Teste em Task 4.

---

### Task 1: Repos e tasks na spec; validação e ordem por `deps` no `next`

**Files:**
- Modify: `scripts/ravend_lib/flow.py` (novas funções perto de `TASK_RE`; `next_action` até o bloco `pending`)
- Test: `tests/test_ravend.py` (nova classe `MultiRepo(FlowBase)` + teste de `deps` em `Flow`)

**Interfaces:**
- Produces (em `flow.py`, exportadas por `ravend_lib`):
  - `spec_repo_paths(text: str) -> list[str]` — itens de `repos:` do frontmatter, `strip()`, vazios descartados; `[]` sem a chave.
  - `is_multi(text: str) -> bool` — `bool(spec_repo_paths(text))`.
  - `task_meta(text: str) -> list[dict]` — por task, em ordem: `{"id": "T1", "done": bool, "title": str, "repo": str | None, "deps": list[str]}`. `repo:` e `deps:` lidos do trecho entre `—` (regex `repo:\s*([^\s—]+)` e `deps:\s*([^—\n]+)`; `none` → `[]`; ids em maiúsculas).
  - `spec_repos(root: Path, text: str) -> tuple[list[dict], list[str]]` — `(participantes, erros)`. Cada participante: `{"name", "project_id", "path", "abs", "root": Path, "origin": bool, "has_profile": bool, "branch": str, "on_branch": bool}`. `path` como escrito (`.` para a origem); `abs` = `str(root_resolvido)`; `branch` = `git branch --show-current` daquele repo; `on_branch` = `branch == frontmatter.branch`. Sem `repos:` → `([origem], [])`.
  - Erros (strings que viram `questions` com prefixo `BLOCKING:`) — texto livre em pt-BR, um por problema: caminho inexistente/não-git; repo sem profile; dois repos diferentes com o mesmo nome; task com `repo:` fora de `repos:`; repo em `repos:` sem nenhuma task.
  - `next_action` passa a devolver, para spec multi-repo, `repos` (lista acima sem a chave `root`) em todas as respostas depois da validação, e em `build`: `repo` (nome), `repo_path` (abs) e `parallel: False`. Para spec de um repo, `build` ganha `repo`/`repo_path` da origem e **não** ganha `parallel`.

- [ ] **Step 1: Write the failing tests**

Crie em `tests/test_ravend.py`:

```python
MULTI_SPEC = """---
slug: m
title: multi
tier: small
status: approved
branch: feat/m
repos: {repos}
---
## Acceptance criteria
- AC1 [unit]: Given a, when b, then c.
## Tasks
- [ ] T1: lib change — repo: lib — files: src/lib.js — proves: AC1 — deps: none
- [ ] T2: use it — files: src/sum.js — proves: AC1 — deps: T1
"""

class MultiRepoBase(FlowBase):
    def setUp(self):
        super().setUp()
        self.lib = Path(self.tmp.name) / "lib"
        (self.lib / "src").mkdir(parents=True)
        (self.lib / "src" / "lib.js").write_text("export const one = 1;\n")
        (self.lib / "package.json").write_text('{"name":"lib","type":"module"}')
        sh("git init -q -b main && git -c user.email=t@t -c user.name=t add -A && "
           "git -c user.email=t@t -c user.name=t commit -qm init", self.lib)
        self.lib_data = ravend.data_dir(self.lib)
        ravend.save_json(self.lib_data / "profile.json", {
            "version": 1, "protected_paths": ["secret.txt"],
            "gate": {"fast": [{"name": "t", "run": "true"}], "full": [{"name": "t", "run": "true"}]}})

    def write_multi(self, repos="../lib", body=None):
        path = ravend.spec_file(self.data, "m")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body or MULTI_SPEC.format(repos=repos))
        return path

    def nxt(self):
        return ravend.next_action(self.repo, "m")
```

Testes em `class MultiRepo(MultiRepoBase)`:
- `test_repos_and_task_meta_are_parsed`: `spec_repo_paths(MULTI_SPEC.format(repos="../lib, ../x"))` == `["../lib", "../x"]`; `task_meta(...)[0]` == `{"id": "T1", "done": False, "title": "lib change", "repo": "lib", "deps": []}`; `[1]["deps"]` == `["T1"]`, `[1]["repo"]` is None.
- `test_participants_resolve_by_project_id_and_dedupe`: `write_multi("../lib, ../lib/, " + str(self.lib))`; `spec_repos(self.repo, text)` devolve 2 participantes (`repo` origem + `lib`), `[p["project_id"] for p in ...]` == `[ravend.project_id(self.repo), ravend.project_id(self.lib)]`, sem erros.
- `test_invalid_repos_become_blocking_questions`: com `repos: ../lib, ../nope` → `nxt()["action"] == "answer"` e uma question contém `../nope`; apagando `lib_data/profile.json` → question contém `lib` e `init`; uma task com `repo: other` → question contém `other`.
- `test_build_points_to_the_task_repo_and_disables_parallel`: depois de `self.run_cli("spec", "approve", "m")`, `nxt()` → `action == "build"`, `task == "T1"`, `repo == "lib"`, `repo_path == str(self.lib.resolve())`, `parallel is False`, `[r["name"] for r in info["repos"]] == ["repo", "lib"]`.
- Em `Flow`: `test_next_task_respects_deps` — spec de um repo com `T1 ... deps: T2` e `T2 ... deps: none` → `nxt()["task"] == "T2"`; o teste de ciclo completo atual continua verde.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s tests -k MultiRepo -k test_next_task_respects_deps -v`
Expected: FAIL/ERROR (`AttributeError: module 'ravend_lib' has no attribute 'spec_repo_paths'`).

- [ ] **Step 3: Implement**

Em `flow.py`: as quatro funções acima. `spec_repos` resolve cada caminho com `(root / Path(p).expanduser()).resolve()` e `repo_root(...)`, deduplica por `project_id` preservando a ordem (origem primeiro), carrega `load_json(ravend_home()/"projects"/pid/"profile.json")` para `has_profile` (como `detection.sibling_repos`). Origem participa só se alguma task não tem `repo:` ou tem `repo: <nome da origem>`. No `next_action`, logo depois do bloco `draft`: se `is_multi(text)` e há erros → `out("answer", "A spec multi-repo tem problemas nos repos declarados.", None, questions=["BLOCKING: " + e for e in erros])`. A escolha da task pendente passa a ser a primeira com todas as `deps` concluídas (se nenhuma estiver livre, a primeira pendente — não travar por `deps` inválida).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: `OK` (todos, incluindo os 50 antigos).

- [ ] **Step 5: Commit**

```bash
git add scripts/ravend_lib/flow.py tests/test_ravend.py
git commit -m "feat(flow): spec declara repos e tasks por repo; next valida e respeita deps"
```

---

### Task 2: Verify e review registrados por repo

**Files:**
- Modify: `scripts/ravend_lib/flow.py` (`record_verify`, `record_review`, `next_action` do bloco `tree` em diante)
- Modify: `scripts/ravend_lib/cli.py` (mensagens de `verify record` se precisar)
- Test: `tests/test_ravend.py` (`MultiRepo`, e um teste de migração em `Flow`)

**Interfaces:**
- Consumes: `spec_repos(root, text)` (Task 1).
- Produces:
  - `spec_fingerprints(repos: list[dict]) -> dict[str, str | None]` — `{project_id: tree_fingerprint(root)}`.
  - `record_fingerprints(entry: dict, origin_pid: str) -> dict[str, str]` — `entry["fingerprints"]` ou, em registro antigo, `{origin_pid: entry["fingerprint"]}`.
  - Entrada de verify: `{"fingerprints": {...}, "gates": {pid: "PASS"|"FAIL"}, "gate": "PASS"|"FAIL", "uncovered": [...], "at": ...}` (`gate` = PASS só se todos PASS). Entrada de review: igual a hoje, com `fingerprints` no lugar de `fingerprint`.
  - `record_verify`/`record_review` levantam `FlowError` se algum participante não está `on_branch` (só quando `is_multi`), ou se o `last-gate-full.json` de algum participante não existe/não bate com a impressão digital atual dele (verify). Gate com status diferente de PASS/FAIL (ex.: perfil sem passos não grava estado) → recusa.
  - "Este código" no `next` = `record_fingerprints(entry, origin) == spec_fingerprints(repos)`.

- [ ] **Step 1: Write the failing tests**

Em `MultiRepo`, helper `def on_branch(self): sh("git switch -qc feat/m", self.repo); sh("git switch -qc feat/m", self.lib)` e `def approve(self): self.run_cli("spec", "approve", "m")`.
- `test_verify_needs_every_repo_gated_on_the_spec_branch`: approve; `task done m T1`, `task done m T2`; `nxt()["action"] == "verify"`; sem branch → `verify record m` retorna 2 e stderr contém `feat/m`; `on_branch()`; `gate full` só na origem → `verify record m` retorna 2 e stderr contém `lib`; rode `gate full` com `cwd=self.lib` (use `subprocess.run([... "gate", "full"], cwd=self.lib)`) → `verify record m` retorna 0; `nxt()["action"] == "review"`.
- `test_change_only_in_the_neighbour_invalidates_verify_and_review`: chegue a `review` como acima, registre review aprovado; escreva `self.lib/src/lib.js` com outro conteúdo → `nxt()["action"] == "verify"`.
- `test_neighbour_with_empty_gate_is_refused`: perfil do `lib` com `"gate": {"fast": [], "full": []}`; depois de `gate full` em ambos → `verify record m` retorna 2.
- Em `Flow`: `test_legacy_records_still_count_for_the_origin` — grave à mão `state.json` com `{"verify": [{"fingerprint": <tree atual>, "gate": "PASS", "uncovered": []}]}` para spec de um repo com tasks prontas → `nxt()["action"] == "review"`.

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest discover -s tests -k test_verify_needs_every -k test_change_only -k test_neighbour_with_empty -k test_legacy_records -v`
Expected: FAIL.

- [ ] **Step 3: Implement** as interfaces above. O texto da spec é lido dentro de `record_verify`/`record_review` (eles já recebem `root` e `slug`). Spec de um repo usa o mesmo código (mapa com uma entrada) — não manter dois caminhos.

- [ ] **Step 4: Run all tests**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/ravend_lib/flow.py scripts/ravend_lib/cli.py tests/test_ravend.py
git commit -m "feat(flow): verify e review valem só com todos os repos da spec no código atual"
```

---

### Task 3: Aprovação presa ao conjunto, risco por repo, lente `contract` e `handoff`

**Files:**
- Modify: `scripts/ravend_lib/flow.py` (`approve_spec`, `risk_hits`, `next_action`)
- Modify: `scripts/ravend_lib/cli.py` (`print_next` mostra `repos` no `handoff`, se necessário)
- Test: `tests/test_ravend.py` (`MultiRepo`)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces:
  - `approve_spec(d, slug, note)` grava em cada approval `"repos": sorted(project_ids participantes)` quando a spec é multi-repo. Precisa do root: nova assinatura `approve_spec(d: Path, slug: str, note: str = "aprovada", root: Path | None = None)`; `cli._record` e `ravend_auto` passam o root.
  - `approved_repos(root: Path) -> list[dict] | None` — para a spec ativa (mesma escolha de `_pick_spec`, sem efeitos), se multi-repo e aprovada: os participantes cujo `project_id` está na última aprovação; caso contrário `None`. Usada pelos hooks e pelo `arm` (Task 4).
  - `risk_hits(root, text, profile, repo: str | None = None)` — com `repo`, conta só os `files:` das tasks daquele repo (task sem `repo:` = origem); hits ganham `"repo": <nome>` quando multi.
  - `next_action` (multi): sem approval, ou `repos` da última approval ≠ conjunto atual → `approve` com mensagem que lista os repos; lentes = união das lentes de risco de cada repo (cada um com o **próprio** profile e `changed_files(root_do_repo, "branch", profile_do_repo)`) + `"contract"` sempre que houver 2+ participantes; no lugar de `ship` → `out("handoff", "Pronta em N repos (branch <b> em cada um). A abertura dos PRs entre repos ainda não é conduzida pelo Ravend (#10).", f"ravend spec done {slug}", repos=[...])`.

- [ ] **Step 1: Write the failing tests**
- `test_multi_repo_spec_always_needs_runtime_approval_bound_to_its_repos`: spec `small`/`approved` multi → `nxt()["action"] == "approve"`; `spec approve m` → `build`; acrescente task `T3 ... repo: lib2` e repo `../lib2` (crie outro repo com profile) → `approve` de novo.
- `test_risk_uses_each_repos_own_profile_and_base`: profile do `lib` com `"git": {"base_branch": "master"}` (crie o `lib` com branch `master` neste teste) e `"risk": [{"name": "dinheiro", "paths": ["src/*"], "lenses": ["money"]}]`; aprovado; `nxt()["lenses"] == ["contract", "money"]` e `nxt()["risk"][0]["repo"] == "lib"`.
- `test_ready_multi_repo_spec_hands_off_instead_of_shipping`: ciclo até review aprovado com `"lenses": ["contract"]` → `nxt()["action"] == "handoff"`; review sem `contract` → `review`; `spec done m` → `done`.

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest discover -s tests -k test_multi_repo_spec_always -k test_risk_uses_each -k test_ready_multi_repo -v`
Expected: FAIL.

- [ ] **Step 3: Implement** as interfaces above.

- [ ] **Step 4: Run all tests** — `python3 -m unittest discover -s tests 2>&1 | tail -3` → `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/ravend_lib/flow.py scripts/ravend_lib/cli.py scripts/ravend_auto.py tests/test_ravend.py
git commit -m "feat(flow): aprovação presa aos repos, risco por repo, lente contract e handoff"
```

---

### Task 4: Hooks resolvem o repo do arquivo; Stop roda o gate de cada repo

**Files:**
- Modify: `scripts/ravend_lib/hooks.py` (`hook_pre_edit`, `hook_post_edit`, `hook_stop`, `hook_session_start`)
- Modify: `scripts/ravend_lib/cli.py` (`_arm` grava `repos`)
- Test: `tests/test_ravend.py` (`MultiRepoHooks(MultiRepoBase)`)

**Interfaces:**
- Consumes: `approved_repos(root)` (Task 3), `spec_repos`, `is_multi`.
- Produces:
  - `_edit_context(inp: dict) -> tuple[Path | None, dict | None, str | None, bool]` em `hooks.py` → `(root, profile, rel, in_spec)`: se o arquivo (ou o primeiro pai existente) está num repo de `approved_repos(session_root)`, devolve root/profile **daquele** repo e `in_spec=True`; senão, o root/profile da sessão como hoje.
  - `armed.json` ganha `"repos": [abs, ...]` (dos `approved_repos`, ou ausente se `None`).
  - Mensagem de negação nova (pt-BR ou inglês, como as atuais — inglês): repo irmão com profile fora do conjunto aprovado de uma spec multi-repo ativa → `"Ravend: `<nome>` is not one of this spec's approved repositories. Add it to `repos:` in the spec; the spec then goes back to the developer for approval."`

- [ ] **Step 1: Write the failing tests** (`self.pre` já existe em `Guards`; mova para `RepoCase` ou replique)
- `test_edit_in_an_approved_neighbour_is_allowed_and_uses_its_protected_paths`: `related_repos` da origem inclui `../lib`; spec aprovada → `pre-edit` em `lib/src/lib.js` liberado; em `lib/secret.txt` negado (protected do **lib**); em `lib/src/new/dir/x.js` (pasta inexistente) liberado.
- `test_neighbour_outside_the_approved_set_is_denied_only_for_multi_repo_specs`: crie `../other` com profile; com spec multi ativa → edição em `other/a.js` negada com `approved repositories`; com só spec de um repo (apague a multi, grave a `SPEC` normal) → liberada (comportamento atual).
- `test_post_edit_formats_with_the_neighbours_formatter`: profile do `lib` com `"format": [{"glob": "src/*.js", "run": "echo formatted >> {file}"}]` → `post-edit` em `lib/src/lib.js` acrescenta `formatted` ao arquivo do `lib`.
- `test_stop_runs_the_gate_of_each_changed_repo`: profile do `lib` com `gate.fast` `false` quando `src/*` muda; `arm` (com `RAVEND_SESSION_ID=s1`) e muda `lib/src/lib.js` → `hook stop` devolve `"decision": "block"` com `lib` no `reason`; apagando a pasta `lib` depois do `arm` → `hook stop` não bloqueia por ela e sai 0.
- `test_session_start_lists_the_spec_repos`: `session-start` contém `lib` e `/add-dir`.

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m unittest discover -s tests -k MultiRepoHooks -v`
Expected: FAIL.

- [ ] **Step 3: Implement** as interfaces above. `hook_stop`: para cada repo em `armed["repos"]` (ou só o root, se ausente) que existe e cuja árvore ≠ `green.json["fast"]` **daquele** repo, rode `gate(repo_root, "fast")` capturando stdout como hoje; junte os relatórios com cabeçalho `== <nome> ==`; código 2 de um repo (perfil sem passos) entra no `systemMessage`, não bloqueia; contador de bloqueios continua no `state_dir` da sessão. Repo inexistente → `systemMessage` "repo X não encontrado", sem bloquear.

- [ ] **Step 4: Run all tests** — `python3 -m unittest discover -s tests 2>&1 | tail -3` → `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/ravend_lib/hooks.py scripts/ravend_lib/cli.py tests/test_ravend.py
git commit -m "feat(hooks): edição, formatter e gate do Stop usam o repo do arquivo na spec multi-repo"
```

---

### Task 5: `project` com irmãos; `ravend auto` recusa spec multi-repo

**Files:**
- Modify: `scripts/ravend_lib/cli.py` (`project` inclui `siblings`)
- Modify: `scripts/ravend_auto.py` (recusa antes do `self.worktree(slug)`)
- Test: `tests/test_ravend.py` (`MultiRepo`), `tests/test_ravend_auto.py`

**Interfaces:**
- Consumes: `is_multi` (Task 1), `detection.sibling_repos(root)`.
- Produces: `ravend project` JSON ganha `"siblings": sibling_repos(root)`; `ravend auto` com spec multi-repo sai com código **2** e mensagem contendo `multi-repo` e `/ravend:continue`.

- [ ] **Step 1: Write the failing tests**
- `test_project_lists_siblings_with_profile`: `json.loads(self.run_cli("project").stdout)["siblings"]` contém `{"name": "lib", "has_profile": True, ...}`.
- Em `test_ravend_auto.py`: `test_multi_repo_spec_is_refused` — com o `claude` falso escrevendo uma spec com `repos: ../x` (ou spec gravada antes com `--resume`), `run_pipeline` retorna 2 e a saída contém `multi-repo`.

- [ ] **Step 2: Run** `python3 -m unittest discover -s tests -k test_project_lists_siblings -k test_multi_repo_spec_is_refused -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run all tests** → `OK`.
- [ ] **Step 5: Commit**

```bash
git add scripts/ravend_lib/cli.py scripts/ravend_auto.py tests/
git commit -m "feat: project lista repos irmãos; ravend auto recusa spec multi-repo"
```

---

### Task 6: Skills e eval

**Files:**
- Modify: `skills/spec/SKILL.md` (§1 intake: irmãos), `skills/spec/references/spec-template.md` (`repos:`, `repo:`)
- Modify: `skills/build/SKILL.md` (§0 e §2), `skills/verify/SKILL.md` (§1, §5), `skills/review/SKILL.md` (§1, §2), `skills/continue/SKILL.md` (tabela)
- Modify: `skills/review/references/lenses.md` (item novo na lente `contract`)
- Create: `evals/spec-multi-repo/case.yaml`, `evals/spec-multi-repo/scaffold.sh`

**Interfaces:**
- Consumes: campos do `next` (`repos`, `repo`, `repo_path`, `parallel`, `handoff`) e `project.siblings`.

Conteúdo (inglês, enxuto; cada SKILL.md continua curto):
- **spec §1**: substituir a linha de `related_repos` por: irmãos (`$RV project` → `siblings`) com `has_profile` que a demanda precisa mudar entram em `repos:` (caminho relativo), cada task com `repo: <pasta>` (omitido = este repo) e `files:` relativos àquele repo; ordenar por dependência (lib/contrato antes de quem usa) com `deps`; irmão sem profile ou `related_repos` fora de `repos:` → `Depends on` + `BLOCKING:` "run /ravend:init in <repo>". Spec multi-repo sempre passa pela aprovação do runtime (`$RV spec approve`), qualquer tier.
- **template**: linha `repos: <../other-repo, ...>  # only when the spec edits sibling repos` no frontmatter e `— repo: <dir>` no exemplo de task.
- **build**: `next` → `repo_path`: `cd` nele para ler/editar/rodar `gate fast`/commitar; `git switch -c <spec.branch>` ali antes da primeira task do repo (mudanças alheias → parar e perguntar); `$RV task done` e `$RV arm` sempre do repo de origem; diretório inacessível na sessão → pedir ao dev `/add-dir <repo_path>` e parar; `parallel: false` → nunca despachar `ravend:implementer`.
- **verify**: `gate full` em cada `repos[].abs` (`cd`), matriz com o repo de cada teste, `verify record` da origem.
- **review**: passar ao reviewer, para cada repo, `abs` + base ref (`git -C <abs> merge-base HEAD <base daquele repo>`); a lente `contract` vem do `next`.
- **lenses.md / contract**: "multi-repo: each repo can be deployed alone and in any order — consumers accept old and new shapes; producers keep fields still read; versions/coordinates consistent across repos."
- **continue**: linha `handoff` → mostrar a mensagem e os repos/branch, dizer que os PRs são do dev nesta versão e que `ravend spec done <slug>` fecha; parar.
- **eval `spec-multi-repo`**: `scaffold.sh` cria o `shop` (via `make-shop.sh base`) e um irmão `../pricing` (repo git com `src/price.js`, remote `https://example.com/acme/pricing.git`, profile em `.ravend-home/projects/example.com-acme-pricing/profile.json` com gate `node --test`). Prompt: `/ravend:spec --headless` "Prices must support a per-customer discount: add the discount rule to the pricing library and apply it in the cart total." Graders: `regex` do JSON headless; `file_exists` da spec em `.ravend-home/projects/example.com-acme-shop/specs/*/spec.md`; `llm` (trace): frontmatter com `repos: ../pricing`, task(s) com `repo: pricing` antes da task do `shop`, com `deps` apontando para ela. Se o harness do eval não permitir ler `../pricing`, crie o irmão dentro do workspace (`./pricing` + `repos: pricing`) e ajuste o grader — registre a escolha no `description` do caso.

- [ ] **Step 1: Edit the skills and lenses** conforme acima.
- [ ] **Step 2: Validate**

Run: `claude plugin validate . && claude plugin validate skills --strict && claude plugin validate agents`
Expected: sem erros.

- [ ] **Step 3: Create the eval case** e rode os afetados:

Run: `claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write Edit Agent --runs 1 --ablation none --case spec-multi-repo --case spec-tier-large --case continue-follows-next --case build-tdd-gate`
Expected: todos passam; se um falhar, rode o caso de novo antes de concluir regressão (variação de `--runs 1`).

- [ ] **Step 4: Commit**

```bash
git add skills/ evals/spec-multi-repo/
git commit -m "feat(skills): spec, build, verify, review e continue conduzem spec multi-repo; eval novo"
```

---

### Task 7: README, ARCHITECTURE e versão

**Files:**
- Modify: `README.md`, `docs/ARCHITECTURE.md`, `.claude-plugin/plugin.json` (`0.4.0` → `0.5.0`)

O que muda (estado atual, sem histórico):
- **README**: seção nova curta "Uma demanda em vários repositórios" (depois de "Áreas de risco e infraestrutura"): quando acontece (a spec planeja irmãos com `/ravend:init` feito), o que o dev faz (abrir o Claude no repo onde a demanda começa e `/add-dir` dos outros quando pedido), garantias (gate/review de cada repo, só repos aprovados editáveis, review com lente `contract`), limites da v1 (PRs abertos pelo dev; `ravend auto` recusa; retomar só do repo de origem). Ajustar a frase de "Também é garantido por hook" (linha ~186) e a linha "Antes de editar" da tabela de Hooks (~355) para dizer "só leitura, exceto os repos aprovados da spec multi-repo". Atualizar "Limitações conhecidas".
- **ARCHITECTURE**: tabela do `next` (linhas `answer` por repos inválidos, `approve` por conjunto de repos, `handoff`); registros (mapa de impressões digitais por `project_id`, migração); hooks (resolvedor de repo, Stop multi-repo, `armed.json.repos`); `ravend auto` (recusa); dados locais (`state.json → approvals[].repos`); tabela Código × prompt (linhas: "só repos aprovados da spec são editáveis", "verify/review valem para todos os repos"); módulos (`flow.py` novos nomes: `spec_repos`, `task_meta`, `approved_repos`, `spec_fingerprints`); contagem de testes e casos de eval (`spec-multi-repo`); glossário (Spec multi-repo, Repo participante, Handoff).

- [ ] **Step 1: Edit** os três arquivos.
- [ ] **Step 2: Check** `grep -n "related" README.md docs/ARCHITECTURE.md` — nenhuma frase diz mais que repos relacionados são sempre só leitura; `python3 -m unittest discover -s tests 2>&1 | tail -3` → `OK`; `claude plugin validate .` → ok.
- [ ] **Step 3: Commit**

```bash
git add README.md docs/ARCHITECTURE.md .claude-plugin/plugin.json
git commit -m "docs: README e ARCHITECTURE com spec multi-repo; versão 0.5.0"
```
