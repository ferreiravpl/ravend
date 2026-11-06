"""Specs and the flow state machine: what comes next for a spec (`next_action`) and the records the
runtime keeps (`task done`, `verify record`, `review record`, spec status)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .core import _frontmatter, _read, data_dir, git, load_json, load_profile, project_id, save_json, state_dir, tree_fingerprint
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


def spec_file(d: Path, slug: str) -> Path:
    return d / "specs" / slug / "spec.md"


def _require_spec(d: Path, slug: str) -> Path:
    path = spec_file(d, slug)
    if not path.exists():
        raise FlowError(f"spec não encontrada: {slug} ({path})")
    return path


def spec_state(d: Path, slug: str) -> dict:
    st = load_json(d / "specs" / slug / "state.json", {}) or {}
    st.setdefault("verify", [])
    st.setdefault("reviews", [])
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


def record_verify(root: Path, slug: str, uncovered: list[str]) -> dict:
    """Ties the verification to the code it was made on. The gate result comes from the runtime's own
    last `gate full` of this checkout, which must have run on exactly this tree."""
    d = data_dir(root)
    _require_spec(d, slug)
    tree = tree_fingerprint(root)
    last = load_json(state_dir(root) / "last-gate-full.json")
    if not last or not tree or last.get("fingerprint") != tree:
        raise FlowError("o gate full não rodou neste código (ou o código mudou depois). Rode `gate full` e registre de novo.")
    entry = {"fingerprint": tree, "gate": last.get("status"), "uncovered": [u for u in uncovered if u.strip()],
             "at": datetime.now().isoformat(timespec="seconds")}
    st = spec_state(d, slug)
    if st["verify"] and st["verify"][-1].get("fingerprint") == tree:
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
    _require_spec(d, slug)
    findings = [f for f in (raw.get("findings") or []) if isinstance(f, dict)]
    blocking = sorted({f"{f.get('file', '?')} — {f.get('title', '')}" for f in findings
                       if f.get("severity") in ("P0", "P1")})
    verdict = "CHANGES_REQUESTED" if blocking else "APPROVED"
    tree = tree_fingerprint(root)
    st = spec_state(d, slug)
    same_code = st["reviews"] and st["reviews"][-1].get("fingerprint") == tree
    n = st["reviews"][-1]["n"] if same_code else len(st["reviews"]) + 1
    entry = {"n": n, "fingerprint": tree, "verdict": verdict, "blocking": blocking,
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
    if status_value == "draft":
        questions = _open_blocking_questions(text)
        if questions:
            return out("answer", "A spec tem perguntas em aberto que mudam o resultado.", None, questions=questions)
        return out("approve", f"A spec ({fm.get('tier', '?')}) espera a sua aprovação antes do build.",
                   f"ravend spec approve {slug}")
    tasks = TASK_RE.findall(text)
    pending = [t for mark, t, _ in tasks if mark == " "]
    if pending:
        title = next(rest for mark, t, rest in tasks if t == pending[0])
        return out("build", f"Implementar {pending[0]}{title.split(' — ')[0].rstrip()} "
                            f"({len(tasks) - len(pending)}/{len(tasks)} prontas).",
                   f"/ravend:build {slug}", task=pending[0])
    tree = tree_fingerprint(root)
    st = spec_state(d, slug)
    verifies, reviews = st["verify"], st["reviews"]
    last_v = verifies[-1] if verifies else None
    if not last_v or last_v.get("fingerprint") != tree:
        why = "Ainda não verificada." if not last_v else "O código mudou desde a última verificação."
        return out("verify", why + " Rodar o gate full e conferir critério × teste.", f"/ravend:verify {slug}")
    if not _verify_ok(last_v):
        fails = _trailing(verifies, lambda e: not _verify_ok(e))
        problem = ("gate full vermelho" if last_v.get("gate") != "PASS"
                   else "critérios sem teste: " + "; ".join(last_v.get("uncovered", [])))
        if fails > max_rounds:
            return out("human", f"A verificação continua falhando depois de {max_rounds} rodadas de correção ({problem}).")
        return out("fix", f"Corrigir: {problem} (rodada {fails} de {max_rounds}).", f"/ravend:build {slug}",
                   fix="verify", problem=problem)
    last_r = reviews[-1] if reviews else None
    if not last_r or last_r.get("fingerprint") != tree:
        return out("review", "Verificada e verde; falta o review deste código.", f"/ravend:review {slug}")
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
    return out("ship", "Pronta para PR: gate full verde, critérios cobertos e review aprovado neste código.",
               f"/ravend:ship {slug}")


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
