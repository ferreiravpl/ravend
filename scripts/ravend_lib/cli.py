"""Command line of the runtime (`ravend <comando>`): argparse definitions and the dispatch to the modules.
`hook` and `auto` are routed before parsing: a hook must never fail on arguments, and `auto` forwards
everything to ravend_auto.py."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from .core import PLUGIN_ROOT, base_branch, data_dir, ensure_dirs, load_profile, project_id, repo_root, save_json, state_dir
from .detection import detect
from .diagnostics import doctor, print_doctor
from .flow import (FlowError, _set_frontmatter, _verify_ok, mark_task_done, next_action, print_next, record_review,
                   record_verify, set_spec_status, spec_file, status)
from .gating import _apps, _http_ok, app_start, app_stop, gate
from .hooks import _hook_input, hook_post_edit, hook_pre_edit, hook_session_start, hook_stop
from .mcp import ROLES, STAGES, integrations, mcp_servers

CLI_SHIM = """#!/usr/bin/env python3
# `ravend` terminal command, installed by `ravend.py install-cli`. Finds the installed Ravend plugin
# (newest install, so plugin updates are picked up) and forwards every argument to scripts/ravend.py.
import json, os, sys
from pathlib import Path

FALLBACK = {fallback!r}


def plugin_root():
    cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        data = json.loads((cfg / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
        for key, entries in (data.get("plugins") or {{}}).items():
            for entry in reversed(entries if key.split("@")[0] == "ravend" else []):
                path = Path(entry.get("installPath", ""))
                if (path / "scripts" / "ravend.py").exists():
                    return path
    except (OSError, ValueError, AttributeError):
        pass
    return Path(FALLBACK)


target = plugin_root() / "scripts" / "ravend.py"
if not target.exists():
    sys.exit(f"ravend: plugin não encontrado ({{target}}). Reinstale com /plugin install ravend")
os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])
"""


def install_cli(target_dir: Path) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "ravend"
    path.write_text(CLI_SHIM.format(fallback=str(PLUGIN_ROOT)), encoding="utf-8")
    path.chmod(0o755)
    print(f"[ravend] instalado: {path}")
    on_path = any(Path(p).resolve() == target_dir.resolve() for p in os.environ.get("PATH", "").split(os.pathsep) if p)
    if not on_path:
        print(f"[ravend] {target_dir} não está no PATH. Adicione ao seu .bashrc/.zshrc: export PATH=\"{target_dir}:$PATH\"")
    return 0


# --------------------------------------------------------------------------- parser

DESCRIPTION = "Ravend — comandos de terminal. Rode dentro do repositório do projeto."
EPILOG = """dia a dia:
  ravend auto "<demanda>" [--pr]     pipeline sem supervisão, num worktree separado
  ravend next                        qual é o próximo passo e por quê
  ravend doctor                      o que está faltando na configuração

Cada comando tem a própria ajuda: ravend <comando> --help"""


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, "uso: " if prefix is None else prefix)


def _parser(**kwargs) -> argparse.ArgumentParser:
    """An ArgumentParser whose help reads in Portuguese (argparse's own error messages stay in English)."""
    parser = argparse.ArgumentParser(formatter_class=_HelpFormatter, add_help=False, **kwargs)
    parser._optionals.title = "opções"
    parser._positionals.title = "argumentos"
    parser.add_argument("-h", "--help", action="help", help="mostra esta ajuda")
    return parser


def build_parser() -> argparse.ArgumentParser:
    p = _parser(prog="ravend", description=DESCRIPTION, epilog=EPILOG)
    sub = p.add_subparsers(dest="cmd", metavar="<comando>", title="comandos", parser_class=argparse.ArgumentParser)

    def cmd(name: str, text: str) -> argparse.ArgumentParser:
        c = sub.add_parser(name, help=text, description=text, formatter_class=_HelpFormatter, add_help=False)
        c._optionals.title = "opções"
        c._positionals.title = "argumentos"
        c.add_argument("-h", "--help", action="help", help="mostra esta ajuda")
        return c

    cmd("auto", "pipeline sem supervisão num worktree separado (detalhes: ravend auto --help)")
    c = cmd("next", "qual é o próximo passo de uma spec e por quê")
    c.add_argument("slug", nargs="?", help="a spec; sem ela, usa a única em andamento ou a da branch atual")
    c.add_argument("--json", action="store_true", help="saída em JSON (usada pelas skills)")
    c = cmd("status", "specs em andamento, o próximo passo de cada uma e o último gate")
    c.add_argument("--json", action="store_true", help="saída em JSON")
    c = cmd("doctor", "confere a instalação e a configuração do projeto e diz o que fazer")
    c.add_argument("--no-probe", action="store_true", help="não consulta `claude mcp list` (mais rápido, sem status dos MCPs)")
    c = cmd("gate", "roda o quality gate desta pasta")
    c.add_argument("mode", nargs="?", choices=["fast", "full"], default="fast", help="fast (padrão) ou full")
    c.add_argument("--dry-run", action="store_true", help="só mostra os comandos que rodariam")
    c.add_argument("--scope", choices=["worktree", "branch"], help="arquivos considerados alterados (padrão: worktree no fast, branch no full)")
    c = cmd("mcp", "lista os seus servidores MCP, sem mostrar segredos")
    c.add_argument("--no-probe", action="store_true", help="só arquivos de configuração, sem `claude mcp list`")
    c = cmd("integrations", "papéis de MCP e os servidores escolhidos para cada um")
    c.add_argument("--stage", choices=STAGES, help="só os papéis usados nesta etapa")

    c = cmd("spec", "registra a aprovação, a conclusão ou o abandono de uma spec")
    c.add_argument("action", choices=["approve", "done", "abandon"])
    c.add_argument("slug")
    c.add_argument("--pr", metavar="URL", help="link do PR (com done)")
    c = cmd("task", "marca uma task da spec como concluída")
    c.add_argument("action", choices=["done"])
    c.add_argument("slug")
    c.add_argument("task", help="id da task, ex.: T3")
    c = cmd("verify", "registra a verificação deste código (usa o último gate full desta pasta)")
    c.add_argument("action", choices=["record"])
    c.add_argument("slug")
    c.add_argument("--uncovered", action="append", default=[], metavar="CRITÉRIO",
                   help="critério sem teste ou com teste fraco (repita para cada um)")
    c = cmd("review", "registra um review (JSON do reviewer) e gera o review-N.md")
    c.add_argument("action", choices=["record"])
    c.add_argument("slug")
    c.add_argument("--file", type=Path, help="arquivo com o JSON, fora do repositório; sem ele, lê da entrada padrão")

    cmd("project", "(interno) identidade do projeto, pastas e integrações, em JSON")
    cmd("detect", "(interno) stacks e ferramentas detectadas, em JSON")
    c = cmd("app", "(interno) sobe, derruba ou mostra a aplicação do profile")
    c.add_argument("action", nargs="?", choices=["start", "stop", "status"], default="status")
    cmd("arm", "(interno) ativa a checagem do gate ao encerrar a sessão")
    cmd("disarm", "(interno) desativa a checagem do gate ao encerrar a sessão")
    c = cmd("install-cli", "instala o comando `ravend` no terminal")
    c.add_argument("--dir", type=Path, default=Path.home() / ".local" / "bin", help="pasta de destino (padrão: ~/.local/bin)")
    cmd("hook", "(interno) chamado pelos hooks do Claude Code")
    cmd("help", "mostra esta ajuda")
    return p


# --------------------------------------------------------------------------- dispatch

def _run_hook(event: str) -> int:
    inp = _hook_input()
    handler = {"session-start": hook_session_start, "pre-edit": hook_pre_edit,
               "post-edit": hook_post_edit, "stop": hook_stop}.get(event)
    if not handler:
        return 0
    try:
        return handler(inp)
    except Exception as exc:  # a broken hook must never break the session
        print(f"[ravend] hook {event} error: {exc}", file=sys.stderr)
        return 0


def _record(args: argparse.Namespace, root: Path) -> int:
    d = data_dir(root)
    try:
        if args.cmd == "spec":
            status_value = {"approve": "approved", "done": "done", "abandon": "abandoned"}[args.action]
            set_spec_status(d, args.slug, status_value, status_value + (f" — PR {args.pr}" if args.pr else ""))
            if args.pr:
                path = spec_file(d, args.slug)
                path.write_text(_set_frontmatter(path.read_text(encoding="utf-8"), "pr", args.pr), encoding="utf-8")
            print(f"[ravend] spec {args.slug}: {status_value}")
        elif args.cmd == "task":
            print(f"[ravend] {args.slug}: {mark_task_done(d, args.slug, args.task)} concluída")
        elif args.cmd == "verify":
            entry = record_verify(root, args.slug, args.uncovered)
            print(f"[ravend] verificação registrada: gate {entry['gate']}"
                  + (f", {len(entry['uncovered'])} critério(s) sem teste" if entry["uncovered"] else "")
                  + (" — ok" if _verify_ok(entry) else ""))
        elif args.cmd == "review":
            if args.file:
                try:
                    args.file.resolve().relative_to(root.resolve())
                    raise FlowError("o arquivo do review está dentro do repositório e muda o código que está sendo "
                                    "registrado; passe o JSON pela entrada padrão (heredoc) ou por um arquivo fora do repo")
                except ValueError:
                    pass
            raw_text = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
            match = re.search(r"\{.*\}", raw_text, re.S)
            if not match:
                raise FlowError("nenhum JSON de review encontrado na entrada")
            entry = record_review(root, args.slug, json.loads(match.group(0)))
            print(f"[ravend] review {entry['n']} registrado: {entry['verdict']}"
                  f" ({len(entry['blocking'])} P0/P1, {entry['p2']} P2) → "
                  f"{d / 'specs' / args.slug / ('review-%d.md' % entry['n'])}")
        return 0
    except FlowError as exc:
        print(f"[ravend] {exc}", file=sys.stderr)
    except (OSError, ValueError) as exc:
        print(f"[ravend] não foi possível registrar: {exc}", file=sys.stderr)
    return 2


def _arm(disarm: bool, root: Path) -> int:
    st = state_dir(root)
    try:
        if disarm:
            (st / "armed.json").unlink(missing_ok=True)
            print("[ravend] Stop-hook gate disarmed")
        else:
            save_json(st / "armed.json", {"session": os.environ.get("RAVEND_SESSION_ID") or "*",
                                          "at": datetime.now().isoformat(timespec="seconds")})
            save_json(st / "stop-blocks.json", {"count": 0})
            print("[ravend] Stop-hook gate armed for this session")
    except OSError as exc:
        print(f"[ravend] could not {'disarm' if disarm else 'arm'} the Stop-hook gate ({exc.strerror}: {st}). "
              "Run the gate manually before finishing each task.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["hook"]:
        return _run_hook(argv[1] if len(argv) > 1 else "")
    if argv[:1] == ["auto"]:
        runner = PLUGIN_ROOT / "scripts" / "ravend_auto.py"
        os.execv(sys.executable, [sys.executable, str(runner), *argv[1:]])
    parser = build_parser()
    if not argv or argv[0] == "help":
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if args.cmd == "doctor":
        return print_doctor(doctor(repo_root(Path.cwd()), probe=not args.no_probe))
    if args.cmd == "install-cli":
        return install_cli(args.dir.expanduser())
    root = repo_root(Path.cwd())
    if not root:
        print("[ravend] rode dentro de um repositório git", file=sys.stderr)
        return 2
    if args.cmd == "project":
        d = data_dir(root)
        ensure_dirs(d)
        print(json.dumps({"project_id": project_id(root), "root": str(root), "data_dir": str(d),
                          "has_profile": (d / "profile.json").exists(),
                          "base_branch": base_branch(root, load_profile(root)),
                          "plugin_root": str(PLUGIN_ROOT),
                          "integrations": integrations(load_profile(root))}, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "mcp":
        print(json.dumps(mcp_servers(root, probe=not args.no_probe), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "integrations":
        print(json.dumps({"roles": {k: v[0] for k, v in ROLES.items()},
                          "chosen": integrations(load_profile(root), args.stage)}, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "detect":
        print(json.dumps(detect(root), indent=2))
        return 0
    if args.cmd == "gate":
        return gate(root, args.mode, args.scope, args.dry_run)
    if args.cmd == "app":
        profile = load_profile(root) or {}
        if args.action == "start":
            ok, msg = app_start(root, profile)
            print(msg)
            return 0 if ok else 1
        if args.action == "stop":
            app_stop(root)
            print("stopped")
            return 0
        for app in _apps(profile):
            url = app.get("healthcheck")
            print(f"{app.get('name', 'app')}: {'UP' if url and _http_ok(url) else 'DOWN'} {url or ''}")
        return 0
    if args.cmd in ("arm", "disarm"):
        return _arm(args.cmd == "disarm", root)
    if args.cmd == "status":
        return status(root, args.json)
    if args.cmd == "next":
        info = next_action(root, args.slug)
        if args.json:
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print_next(info)
        return 0
    if args.cmd in ("spec", "task", "verify", "review"):
        return _record(args, root)
    parser.print_help()
    return 2
