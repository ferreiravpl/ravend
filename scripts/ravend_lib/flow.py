"""Specs and the flow state machine: what comes next for a spec (`next_action`) and the records the
runtime keeps (`task done`, `verify record`, `review record`, spec status)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .core import (_frontmatter, _read, changed_files, data_dir, git, load_json, load_profile, project_id, ravend_home,
                   repo_root, save_json, state_dir, tree_fingerprint)
from .gating import _matches
from .mcp import integrations

# --------------------------------------------------------------------------- specs & status

def specs_status(d: Path) -> list[dict]:
    rows = []
    for spec in sorted((d / "specs").glob("*/spec.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = _read(spec)
        fm = _frontmatter(text)
        tasks = re.findall(r"^- \[([ xX])\] (.+)$", text, re.M)
        nxt = next((t for mark, t in tasks if mark == " "), None)
        rows.append({"slug": spec.parent.name, "status": fm.get("status", "?"), "tier": fm.get("tier", "?"),
                     "title": fm.get("title", spec.parent.name), "done": sum(1 for m, _ in tasks if m != " "),
                     "total": len(tasks), "next": nxt.split(" — ")[0] if nxt else None, "path": str(spec)})
    return rows


def status(root: Path, as_json: bool) -> int:
    d = data_dir(root)
    data = {"project_id": project_id(root), "data_dir": str(d), "has_profile": (d / "profile.json").exists(),
            "specs": specs_status(d),
            "last_gate": {m: load_json(state_dir(root) / f"last-gate-{m}.json") for m in ("fast", "full")},
            "tree": tree_fingerprint(root), "green": load_json(state_dir(root) / "green.json", {}),
            "armed": load_json(state_dir(root) / "armed.json"), "integrations": integrations(load_profile(root))}
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    print(f"projeto {data['project_id']} · dados {d} · perfil {'sim' if data['has_profile'] else 'NÃO (rode /ravend:init)'}")
    for s in data["specs"][:10]:
        if s["status"] in ("done", "abandoned"):
            continue
        print(f"  spec {s['slug']} [{s['status']}/{s['tier']}] {s['done']}/{s['total']} tasks · "
              f"próximo: {next_action(root, s['slug'])['message']}")
    for m, g in data["last_gate"].items():
        if g:
            fresh = "deste código" if g.get("fingerprint") == data["tree"] else "desatualizado: o código mudou"
            print(f"  último gate {m}: {g['status']} em {g['at']} ({fresh})")
    return 0


# --------------------------------------------------------------------------- flow (state machine)
# One source of truth for "what comes next", used by /ravend:continue, /ravend:start and ravend_auto.py.
# It reads only what is on disk: the spec (status, tasks), the per-checkout gate state and the spec's
# state.json (verify and review records, each tied to the tree fingerprint they were made on).
# The records are written by the runtime (`task done`, `verify record`, `review record`, `spec ...`),
# never edited by hand, so the decision cannot be thrown off by a reformatted file.

TASK_RE = re.compile(r"^- \[([ xX])\] (T\d+)\b(.*)$", re.M)
DEFAULT_MAX_FIX_ROUNDS = 2


class FlowError(Exception):
    """A state change that cannot be made (unknown spec/task, gate not run on this code...)."""


# --------------------------------------------------------------------------- multi-repo specs
# A spec may edit sibling repositories: `repos: ../contracts, ../consumer` in the frontmatter (paths relative
# to the origin repo, the one that holds the spec) and `— repo: <folder>` on each task (absent = origin).
# Records identify each repo by project_id (stable across clones/worktrees); the folder name is only for the spec.

TASK_REPO_RE = re.compile(r"(?:^|—)\s*repo:\s*([^\s—]+)")
TASK_DEPS_RE = re.compile(r"(?:^|—)\s*deps:\s*([^—\n]*)")


def spec_repo_paths(text: str) -> list[str]:
    return [p.strip() for p in _frontmatter(text).get("repos", "").split(",") if p.strip()]


def is_multi(text: str) -> bool:
    return bool(spec_repo_paths(text))


def task_meta(text: str) -> list[dict]:
    out = []
    for m in TASK_RE.finditer(text):
        rest = m.group(3).lstrip(":").strip()
        repo = TASK_REPO_RE.search(rest)
        deps = TASK_DEPS_RE.search(rest)
        out.append({"id": m.group(2), "done": m.group(1) != " ", "title": rest.split("—")[0].strip(),
                    "repo": repo.group(1) if repo else None,
                    "deps": re.findall(r"T\d+", deps.group(1).upper()) if deps else []})
    return out


def _repo_entry(path: str, root: Path, origin: bool, branch: str) -> dict:
    pid = project_id(root)
    current = git(["branch", "--show-current"], root) or ""
    return {"name": root.name, "project_id": pid, "path": path, "abs": str(root), "root": root, "origin": origin,
            "has_profile": bool(load_json(ravend_home() / "projects" / pid / "profile.json")),
            "branch": current, "on_branch": bool(branch) and current == branch}


def spec_repos(root: Path, text: str) -> tuple[list[dict], list[str]]:
    """The repos that take part in the spec, origin first, and what is wrong with the declaration (each error
    becomes a blocking question). Without `repos:` it is just the origin."""
    root = root.resolve()
    branch = _frontmatter(text).get("branch", "")
    origin = _repo_entry(".", root, True, branch)
    paths = spec_repo_paths(text)
    if not paths:
        return [origin], []
    errors: list[str] = []
    declared = [origin]
    for p in paths:
        target = (root / Path(p).expanduser()).resolve()
        top = repo_root(target) if target.is_dir() else None
        if not top:
            errors.append(f"o repo `{p}` (em `repos:`) não existe ou não é um repositório git")
            continue
        entry = _repo_entry(p, Path(top).resolve(), False, branch)
        if any(e["project_id"] == entry["project_id"] for e in declared):
            continue
        if any(e["name"] == entry["name"] for e in declared):
            errors.append(f"dois repos diferentes se chamam `{entry['name']}` em `repos:`; renomeie uma das pastas")
            continue
        if not entry["has_profile"]:
            errors.append(f"o repo `{entry['name']}` não tem profile do Ravend: rode /ravend:init nele antes")
        declared.append(entry)
    names = {e["name"] for e in declared}
    used = {t["repo"] or origin["name"] for t in task_meta(text)}
    for name in sorted(used - names):
        errors.append(f"há task com `repo: {name}`, mas `{name}` não está em `repos:`")
    for e in declared[1:]:
        if e["name"] not in used:
            errors.append(f"o repo `{e['name']}` está em `repos:` mas nenhuma task roda nele")
    return [e for e in declared if e["name"] in used], errors


def _public(repos: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if k != "root"} for r in repos]


def spec_file(d: Path, slug: str) -> Path:
    return d / "specs" / slug / "spec.md"


def _require_spec(d: Path, slug: str) -> Path:
    path = spec_file(d, slug)
    if not path.exists():
        raise FlowError(f"spec não encontrada: {slug} ({path})")
    return path


def spec_state(d: Path, slug: str) -> dict:
    st = load_json(d / "specs" / slug / "state.json", {}) or {}
    for key in ("verify", "reviews", "approvals", "ci"):
        st.setdefault(key, [])
    return st


def _save_spec_state(d: Path, slug: str, st: dict) -> None:
    save_json(d / "specs" / slug / "state.json", st)


def _set_frontmatter(text: str, key: str, value: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return text
    lines = m.group(1).splitlines()
    for i, line in enumerate(lines):
        if line.split(":", 1)[0].strip() == key:
            lines[i] = f"{key}: {value}"
            break
    else:
        lines.append(f"{key}: {value}")
    return "---\n" + "\n".join(lines) + "\n---" + text[m.end():]


def _append_log(text: str, line: str) -> str:
    entry = f"- {datetime.now():%Y-%m-%d} {line}"
    if re.search(r"^## Log\s*$", text, re.M):
        return text.rstrip("\n") + "\n" + entry + "\n"
    return text.rstrip("\n") + "\n\n## Log\n" + entry + "\n"


def mark_task_done(d: Path, slug: str, task: str) -> str:
    path = _require_spec(d, slug)
    text = path.read_text(encoding="utf-8")
    task = task.upper()
    hit = next((m for m in TASK_RE.finditer(text) if m.group(2) == task), None)
    if not hit:
        known = ", ".join(m.group(2) for m in TASK_RE.finditer(text)) or "nenhuma"
        raise FlowError(f"task {task} não existe na spec {slug} (tasks: {known})")
    if hit.group(1) == " ":
        text = text[:hit.start()] + f"- [x] {task}{hit.group(3)}" + text[hit.end():]
        text = _append_log(text, f"{task} concluída")
        if _frontmatter(text).get("status") in ("approved", "draft"):
            text = _set_frontmatter(text, "status", "in-progress")
        path.write_text(text, encoding="utf-8")
    return task


def set_spec_status(d: Path, slug: str, status_value: str, note: str = "") -> None:
    path = _require_spec(d, slug)
    text = _set_frontmatter(path.read_text(encoding="utf-8"), "status", status_value)
    path.write_text(_append_log(text, note or f"status: {status_value}"), encoding="utf-8")


def ship_spec(d: Path, slug: str, pr: str) -> None:
    """The PR is open: from here `next` follows its CI until the merge."""
    set_spec_status(d, slug, "shipped", f"PR aberto: {pr}")
    path = spec_file(d, slug)
    path.write_text(_set_frontmatter(path.read_text(encoding="utf-8"), "pr", pr), encoding="utf-8")


def approve_spec(d: Path, slug: str, note: str = "aprovada", root: Path | None = None) -> None:
    """A human approval (`ravend spec approve`, or `ravend auto --no-pause/--resume`). Recorded in state.json
    because a small spec is approved by the spec skill itself: only this record counts for risk areas.
    For a multi-repo spec it also records which repos were approved: only those may be edited."""
    text = _read(_require_spec(d, slug))
    set_spec_status(d, slug, "approved", note)
    st = spec_state(d, slug)
    approval = {"at": datetime.now().isoformat(timespec="seconds"), "note": note}
    if root is not None and is_multi(text):
        approval["repos"] = sorted(r["project_id"] for r in spec_repos(root, text)[0])
    st["approvals"].append(approval)
    _save_spec_state(d, slug, st)


# --------------------------------------------------------------------------- risk areas
# profile.risk: [{"name": "pagamentos", "paths": ["**/payment/**"], "lenses": ["money", "concurrency"],
#                 "approve": true}]. A spec whose tasks or branch diff touch those paths needs a human
# approval and a review that covered the listed lenses, whatever its tier.

TASK_FILES_RE = re.compile(r"files:\s*([^—\n]+)")


def _risk_match(path: str, pattern: str) -> bool:
    return _matches(path, pattern) or _matches("/" + path, pattern)


def risk_hits(root: Path, text: str, profile: dict | None, repo: str | None = None,
              origin: str | None = None) -> list[dict]:
    """Risk areas of `root`'s own profile touched by its branch diff and by the tasks' `files:`. With `repo`
    (multi-repo spec) only the tasks of that repo count (a task without `repo:` belongs to `origin`)."""
    areas = [a for a in ((profile or {}).get("risk") or []) if isinstance(a, dict) and a.get("paths")]
    if not areas:
        return []
    files = set(changed_files(root, "branch", profile))
    if repo is None:
        task_text = text
    else:
        task_text = "\n".join(m.group(0) for m, meta in zip(TASK_RE.finditer(text), task_meta(text))
                              if (meta["repo"] or origin) == repo)
    for m in TASK_FILES_RE.finditer(task_text):
        files.update(f.strip().strip("`") for f in m.group(1).split(",") if f.strip())
    hits = []
    for area in areas:
        paths = [area["paths"]] if isinstance(area["paths"], str) else area["paths"]
        touched = sorted(f for f in files if any(_risk_match(f, p) for p in paths))
        if touched:
            hits.append({"name": area.get("name", "risco"), "lenses": list(area.get("lenses") or []),
                         "approve": area.get("approve", True) is not False, "files": touched[:5],
                         **({"repo": repo} if repo is not None else {})})
    return hits


def spec_fingerprints(repos: list[dict]) -> dict:
    return {r["project_id"]: tree_fingerprint(r["root"]) for r in repos}


def record_fingerprints(entry: dict, origin_pid: str) -> dict:
    """The code a record was made on, per repo. Records from before multi-repo specs carry a single
    `fingerprint`: it belongs to the origin repo."""
    if entry.get("fingerprints"):
        return dict(entry["fingerprints"])
    return {origin_pid: entry["fingerprint"]} if entry.get("fingerprint") else {}


def approved_repos(root: Path) -> list[dict] | None:
    """The repos the active multi-repo spec may edit: the participants whose project_id is in the last runtime
    approval — only the origin (if it has tasks) before that approval. None when the active spec is not a
    multi-repo spec, or there is no single active spec (hooks then behave as before)."""
    d = data_dir(root)
    slug, early = _pick_spec(root, d)
    if early or not slug or not spec_file(d, slug).exists():
        return None
    text = _read(spec_file(d, slug))
    if not is_multi(text):
        return None
    repos = spec_repos(root, text)[0]
    approvals = spec_state(d, slug)["approvals"]
    if not approvals or "repos" not in approvals[-1]:
        # not approved as a multi-repo spec yet: nothing beyond the origin may be edited
        return [r for r in repos if r["origin"]]
    allowed = set(approvals[-1]["repos"])
    return [r for r in repos if r["project_id"] in allowed]


def _record_repos(root: Path, d: Path, slug: str) -> tuple[str, list[dict]]:
    text = _read(_require_spec(d, slug))
    repos, errors = spec_repos(root, text)
    if is_multi(text):
        if errors:
            raise FlowError("; ".join(errors))
        branch = _frontmatter(text).get("branch", "")
        off = [r["name"] for r in repos if not r["on_branch"]]
        if off:
            raise FlowError(f"repo(s) fora da branch `{branch}` da spec: {', '.join(off)}. "
                            f"Rode `git switch {branch}` neles e registre de novo.")
    return text, repos


def record_verify(root: Path, slug: str, uncovered: list[str]) -> dict:
    """Ties the verification to the code it was made on. The gate result comes from the runtime's own
    last `gate full` of this checkout, which must have run on exactly this tree."""
    d = data_dir(root)
    text, repos = _record_repos(root, d, slug)
    fps, gates = {}, {}
    for r in repos:
        tree = tree_fingerprint(r["root"])
        last = load_json(state_dir(r["root"]) / "last-gate-full.json")
        if not last or not tree or last.get("fingerprint") != tree:
            where = f" do repo `{r['name']}` ({r['abs']})" if is_multi(text) else ""
            raise FlowError(f"o gate full não rodou neste código{where} (ou o código mudou depois). "
                            "Rode `gate full` e registre de novo.")
        fps[r["project_id"]], gates[r["project_id"]] = tree, last.get("status")
    gate_value = next((g for g in gates.values() if g != "PASS"), "PASS")
    entry = {"fingerprints": fps, "gates": gates, "gate": gate_value,
             "uncovered": [u for u in uncovered if u.strip()], "at": datetime.now().isoformat(timespec="seconds")}
    st = spec_state(d, slug)
    if st["verify"] and record_fingerprints(st["verify"][-1], repos[0]["project_id"]) == fps:
        st["verify"][-1] = entry  # same code verified again: replace, do not count it twice
    else:
        st["verify"].append(entry)
    _save_spec_state(d, slug, st)
    return entry


def _verify_ok(entry: dict) -> bool:
    return entry.get("gate") == "PASS" and not entry.get("uncovered")


def _render_review(n: int, verdict: str, findings: list[dict], summary: str, raw: dict) -> str:
    out = [f"# Review {n} — {verdict}", "", f"{datetime.now():%Y-%m-%d %H:%M}", ""]
    if summary:
        out += [summary, ""]
    for sev in ("P0", "P1", "P2"):
        group = [f for f in findings if f.get("severity") == sev]
        if not group:
            continue
        out.append(f"## {sev}")
        for f in group:
            where = f"{f.get('file', '?')}:{f['line']}" if f.get("line") else f.get("file", "?")
            parts = [f"`{where}` — **{f.get('title', '')}**"]
            for key, label in (("scenario", "cenário"), ("action", "ação"), ("ac", "critério")):
                if f.get(key):
                    parts.append(f"{label}: {f[key]}")
            out.append("- " + " — ".join(parts))
        out.append("")
    if not findings:
        out += ["Nenhum finding.", ""]
    out += ["```json", json.dumps(raw, indent=2, ensure_ascii=False), "```", ""]
    return "\n".join(out)


def record_review(root: Path, slug: str, raw: dict) -> dict:
    """Stores a review and writes review-N.md. The verdict is derived, not trusted: any P0/P1 means
    CHANGES_REQUESTED, whatever the reviewer wrote."""
    d = data_dir(root)
    _, repos = _record_repos(root, d, slug)
    findings = [f for f in (raw.get("findings") or []) if isinstance(f, dict)]
    blocking = sorted({f"{f.get('file', '?')} — {f.get('title', '')}" for f in findings
                       if f.get("severity") in ("P0", "P1")})
    verdict = "CHANGES_REQUESTED" if blocking else "APPROVED"
    fps = spec_fingerprints(repos)
    st = spec_state(d, slug)
    same_code = st["reviews"] and record_fingerprints(st["reviews"][-1], repos[0]["project_id"]) == fps
    n = st["reviews"][-1]["n"] if same_code else len(st["reviews"]) + 1
    lenses = sorted({str(x).strip().lower() for x in (raw.get("lenses") or []) if str(x).strip()})
    entry = {"n": n, "fingerprints": fps, "verdict": verdict, "blocking": blocking, "lenses": lenses,
             "p2": sum(1 for f in findings if f.get("severity") == "P2"),
             "at": datetime.now().isoformat(timespec="seconds"), "raw": raw}
    if same_code:
        st["reviews"][-1] = entry
    else:
        st["reviews"].append(entry)
    (d / "specs" / slug / f"review-{n}.md").write_text(
        _render_review(n, verdict, findings, str(raw.get("summary") or ""), raw), encoding="utf-8")
    _save_spec_state(d, slug, st)
    return entry


def _trailing(items: list, pred) -> int:
    count = 0
    for item in reversed(items):
        if not pred(item):
            break
        count += 1
    return count


def _open_blocking_questions(text: str) -> list[str]:
    m = re.search(r"^## Open questions\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return []
    return [ln.strip("- ").strip() for ln in m.group(1).splitlines() if "BLOCKING" in ln.upper()]


def _pick_spec(root: Path, d: Path) -> tuple[str | None, dict | None]:
    active = [s for s in specs_status(d) if s["status"] not in ("done", "abandoned")]
    if not active:
        return None, {"action": "start", "message": "Nenhuma spec em andamento.", "command": "/ravend:start <demanda>"}
    if len(active) == 1:
        return active[0]["slug"], None
    branch = git(["branch", "--show-current"], root) or ""
    on_branch = [s for s in active
                 if _frontmatter(_read(spec_file(d, s["slug"]))).get("branch") == branch]
    if len(on_branch) == 1:
        return on_branch[0]["slug"], None
    return None, {"action": "choose", "message": "Há mais de uma spec em andamento; diga qual continuar.",
                  "options": [{"slug": s["slug"], "title": s["title"], "status": s["status"]} for s in active],
                  "command": "/ravend:continue <slug>"}


def next_action(root: Path, slug: str | None = None) -> dict:
    """What the pipeline should do next for a spec, and why. Pure function of what is on disk."""
    d = data_dir(root)
    if slug is None:
        slug, early = _pick_spec(root, d)
        if early:
            return early
    path = spec_file(d, slug)
    if not path.exists():
        return {"action": "start", "slug": slug, "message": f"A spec `{slug}` não existe.",
                "command": "/ravend:start <demanda>"}
    text = _read(path)
    fm = _frontmatter(text)
    base = {"slug": slug, "title": fm.get("title", slug), "tier": fm.get("tier", "?"), "spec_path": str(path)}
    status_value = fm.get("status", "draft")
    max_rounds = int(((load_profile(root) or {}).get("flow") or {}).get("max_fix_rounds", DEFAULT_MAX_FIX_ROUNDS))

    def out(action: str, message: str, command: str | None = None, **extra) -> dict:
        return {**base, "action": action, "message": message, "command": command, **extra}

    if status_value == "done":
        return out("done", "Spec concluída." + (f" PR: {fm['pr']}" if fm.get("pr") else ""))
    if status_value == "abandoned":
        return out("done", "Spec abandonada.")
    multi = is_multi(text)
    repos, repo_errors = spec_repos(root, text)
    if multi:
        if repo_errors:
            return out("answer", "A spec multi-repo tem problemas nos repos declarados.", None,
                       questions=["BLOCKING: " + e for e in repo_errors])
        base["repos"] = _public(repos)
    if status_value == "draft":
        questions = _open_blocking_questions(text)
        if questions:
            return out("answer", "A spec tem perguntas em aberto que mudam o resultado.", None, questions=questions)
        return out("approve", f"A spec ({fm.get('tier', '?')}) espera a sua aprovação antes do build.",
                   f"ravend spec approve {slug}")
    st = spec_state(d, slug)
    profile = load_profile(root) or {}
    if multi:
        pids = sorted(r["project_id"] for r in repos)
        last_a = st["approvals"][-1] if st["approvals"] else None
        if not last_a or sorted(last_a.get("repos") or []) != pids:
            names = ", ".join(r["name"] for r in repos)
            why = ("Os repos da spec mudaram desde a aprovação" if last_a
                   else "Uma spec multi-repo precisa da sua aprovação")
            return out("approve", f"{why}: ela vai editar {names}.", f"ravend spec approve {slug}")
        origin_name = root.resolve().name
        hits = [h for r in repos for h in risk_hits(r["root"], text, load_profile(r["root"]) or {}, r["name"],
                                                    origin_name)]
    else:
        hits = risk_hits(root, text, profile)
    lenses = sorted({lens.lower() for h in hits for lens in h["lenses"]} | ({"contract"} if len(repos) > 1 else set()))
    if hits or lenses:
        base.update(risk=hits, lenses=lenses)
    if any(h["approve"] for h in hits) and not st["approvals"]:
        names = ", ".join(h["name"] for h in hits)
        return out("approve", f"A spec toca área de risco ({names}) e precisa da sua aprovação antes de seguir.",
                   f"ravend spec approve {slug}")
    tasks = TASK_RE.findall(text)
    meta = task_meta(text)
    finished = {t["id"] for t in meta if t["done"]}
    pending = [t for t in meta if not t["done"]]
    if pending:
        ready = [t for t in pending if all(dep in finished for dep in t["deps"])]
        task = (ready or pending)[0]  # an impossible `deps` must not freeze the spec
        title = next(rest for mark, t, rest in tasks if t == task["id"])
        repo = next((r for r in repos if r["name"] == (task["repo"] or repos[0]["name"])), repos[0])
        extra = {"task": task["id"], "repo": repo["name"], "repo_path": repo["abs"]}
        if multi:
            extra["parallel"] = False  # an isolated worktree exists only for the session's repo
        return out("build", f"Implementar {task['id']}{title.split(' — ')[0].rstrip()}"
                            + (f" no repo `{repo['name']}`" if multi else "")
                            + f" ({len(tasks) - len(pending)}/{len(tasks)} prontas).",
                   f"/ravend:build {slug}", **extra)
    current = spec_fingerprints(repos)
    origin_pid = repos[0]["project_id"]
    verifies, reviews = st["verify"], st["reviews"]
    last_v = verifies[-1] if verifies else None
    if not last_v or record_fingerprints(last_v, origin_pid) != current:
        why = "Ainda não verificada." if not last_v else "O código mudou desde a última verificação."
        return out("verify", why + " Rodar o gate full e conferir critério × teste.", f"/ravend:verify {slug}")
    if not _verify_ok(last_v):
        fails = _trailing(verifies, lambda e: not _verify_ok(e))
        red = [r["name"] for r in repos if (last_v.get("gates") or {}).get(r["project_id"], "PASS") != "PASS"]
        problem = ("gate full vermelho" + (f" em {', '.join(red)}" if multi and red else "")
                   if last_v.get("gate") != "PASS"
                   else "critérios sem teste: " + "; ".join(last_v.get("uncovered", [])))
        if fails > max_rounds:
            return out("human", f"A verificação continua falhando depois de {max_rounds} rodadas de correção ({problem}).")
        return out("fix", f"Corrigir: {problem} (rodada {fails} de {max_rounds}).", f"/ravend:build {slug}",
                   fix="verify", problem=problem)
    last_r = reviews[-1] if reviews else None
    if not last_r or record_fingerprints(last_r, origin_pid) != current:
        return out("review", "Verificada e verde; falta o review deste código."
                   + (f" Lentes exigidas: {', '.join(lenses)}." if lenses else ""), f"/ravend:review {slug}")
    missing = [lens for lens in lenses if lens not in (last_r.get("lenses") or [])]
    if missing:
        return out("review", f"O review deste código não cobriu as lentes exigidas: {', '.join(missing)}.",
                   f"/ravend:review {slug}")
    if last_r.get("verdict") != "APPROVED":
        rounds = _trailing(reviews, lambda e: e.get("verdict") != "APPROVED")
        prev = reviews[-2] if len(reviews) > 1 else None
        repeated = bool(prev and prev.get("verdict") != "APPROVED" and prev.get("blocking") == last_r.get("blocking"))
        review_file = str(d / "specs" / slug / f"review-{last_r['n']}.md")
        if repeated:
            return out("human", "O review apontou os mesmos problemas de novo; a correção não está convergindo.",
                       None, review=review_file, blocking=last_r.get("blocking", []))
        if rounds > max_rounds:
            return out("human", f"O review ainda pede mudanças depois de {max_rounds} rodadas.", None,
                       review=review_file, blocking=last_r.get("blocking", []))
        return out("fix", f"Corrigir os {len(last_r.get('blocking', []))} problema(s) P0/P1 do review {last_r['n']} "
                          f"(rodada {rounds} de {max_rounds}).", f"/ravend:build {slug}",
                   fix="review", review=review_file, blocking=last_r.get("blocking", []))
    if status_value == "shipped" and fm.get("pr"):
        return _after_pr(root, slug, fm["pr"], st["ci"], max_rounds, out)
    if multi:
        branch = fm.get("branch", "")
        return out("handoff", f"Pronta em {len(repos)} repos (branch `{branch}` em cada um: "
                              f"{', '.join(r['name'] for r in repos)}): gate full verde, critérios cobertos e review "
                              "aprovado no código atual de todos. A abertura dos PRs entre repos ainda não é conduzida "
                              f"pelo Ravend (#10): abra os PRs e feche a spec com `ravend spec done {slug}`.",
                   f"ravend spec done {slug}")
    return out("ship", "Pronta para PR: gate full verde, critérios cobertos e review aprovado neste código.",
               f"/ravend:ship {slug}")


def _ci_ok(entry: dict) -> bool:
    return entry.get("state") == "pass"


def _after_pr(root: Path, slug: str, pr: str, records: list, max_rounds: int, out) -> dict:
    """The PR is open: push what changed locally, then follow its CI checks (records written by `ravend ci`)."""
    head = git(["rev-parse", "HEAD"], root)
    upstream = git(["rev-parse", "--verify", "--quiet", "@{u}"], root)
    last = records[-1] if records else None
    dirty = tree_fingerprint(root) != git(["rev-parse", "HEAD^{tree}"], root)
    if dirty or (upstream and upstream != head) or (not upstream and last and last.get("head") != head):
        return out("ship", f"Há mudanças locais que ainda não estão no PR ({pr}): commitar e enviar.",
                   f"/ravend:ship {slug}", pr=pr)
    if not last or last.get("head") != head or last.get("state") == "pending":
        why = "Aguardando o CI do PR." if last and last.get("head") == head else "Acompanhar o CI do PR."
        return out("ci", f"{why} {pr}", f"ravend ci {slug} --wait", pr=pr)
    if last.get("pr_state") == "MERGED":
        return out("done", f"PR mergeado: {pr}", pr=pr)
    if _ci_ok(last):
        return out("merge", f"CI verde no PR. O merge é seu: {pr}", None, pr=pr)
    fails = _trailing(records, lambda e: not _ci_ok(e) and e.get("state") != "pending")
    problem = "CI vermelho: " + "; ".join(last.get("failed") or ["checks falharam"])
    if fails > max_rounds:
        return out("human", f"O CI continua vermelho depois de {max_rounds} rodadas de correção ({problem}).", None,
                   pr=pr, logs=last.get("logs", []))
    return out("fix", f"Corrigir: {problem} (rodada {fails} de {max_rounds}).", f"/ravend:build {slug}",
               fix="ci", problem=problem, logs=last.get("logs", []), pr=pr)


def print_next(info: dict) -> None:
    head = f"[{info['slug']}] " if info.get("slug") else ""
    print(f"{head}{info['message']}")
    for q in info.get("questions", []):
        print(f"  ? {q}")
    for b in info.get("blocking", []):
        print(f"  ! {b}")
    for o in info.get("options", []):
        print(f"  - {o['slug']} [{o['status']}] {o['title']}")
    if info.get("command"):
        print(f"próximo: {info['command']}")
