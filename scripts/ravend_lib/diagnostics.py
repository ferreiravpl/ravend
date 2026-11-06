"""`ravend doctor`: checks the installation and the project setup and says how to fix each problem."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .core import PLUGIN_ROOT, data_dir, load_json, load_profile
from .mcp import integrations, mcp_servers

# --------------------------------------------------------------------------- doctor

def _check(name: str, ok: bool | None, detail: str, fix: str = "") -> dict:
    return {"check": name, "status": "ok" if ok else ("warn" if ok is None else "fail"), "detail": detail, "fix": fix}


def _plugin_version() -> str:
    return (load_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json", {}) or {}).get("version", "?")


def doctor(root: Path | None, probe: bool = True) -> list[dict]:
    checks = [_check("python", sys.version_info >= (3, 8), sys.version.split()[0], "instale Python 3.8+"),
              _check("git", bool(shutil.which("git")), shutil.which("git") or "não encontrado", "instale o git"),
              _check("claude", bool(shutil.which("claude")), shutil.which("claude") or "não encontrado",
                     "necessário para `ravend auto`; instale o Claude Code CLI"),
              _check("plugin", True, f"Ravend {_plugin_version()} em {PLUGIN_ROOT}")]
    if not root:
        checks.append(_check("repositório", False, "fora de um repositório git", "rode dentro do repositório do projeto"))
        return checks
    d = data_dir(root)
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe_file = d / ".write-test"
        probe_file.write_text("x")
        probe_file.unlink()
        checks.append(_check("dados locais", True, str(d)))
    except OSError as exc:
        checks.append(_check("dados locais", False, f"{d}: {exc.strerror}", "verifique permissões ou defina RAVEND_HOME"))
    profile = load_profile(root)
    if not profile:
        checks.append(_check("perfil", False, "este repositório ainda não foi configurado", "rode /ravend:init"))
    else:
        checks.append(_check("perfil", True, str(d / "profile.json")))
        for mode in ("fast", "full"):
            steps = (profile.get("gate") or {}).get(mode) or []
            if not steps:
                checks.append(_check(f"gate {mode}", False, "nenhum passo configurado", "rode /ravend:init"))
                continue
            missing = []
            for step in steps:
                word = (step.get("run") or "").strip().split(" ")[0]
                cwd = root / step.get("cwd", ".")
                if word and not word.startswith("{") and not (shutil.which(word) or (cwd / word).exists()):
                    missing.append(f"{step.get('name', 'passo')}: `{word}` não encontrado em ./{step.get('cwd', '.')}")
            checks.append(_check(f"gate {mode}", not missing, "; ".join(missing) or f"{len(steps)} passo(s)",
                                 "corrija o comando no profile.json ou rode /ravend:init" if missing else ""))
        chosen = integrations(profile)
        if chosen:
            known = {r["name"]: r for r in mcp_servers(root, probe=probe)}
            for role, info in chosen.items():
                for server in info["servers"]:
                    row = known.get(server)
                    if not row:
                        checks.append(_check(f"MCP {role}", False, f"`{server}` não está configurado",
                                             "rode /ravend:init e escolha de novo"))
                    elif probe and row.get("status") and "connect" in row["status"].lower() and "fail" not in row["status"].lower():
                        checks.append(_check(f"MCP {role}", True, f"{server} conectado"))
                    else:
                        checks.append(_check(f"MCP {role}", None, f"{server}: {row.get('status') or 'status desconhecido'}",
                                             "confira com `claude mcp list` ou reautentique o servidor"))
        if "git" not in chosen:
            gh = shutil.which("gh")
            authed = gh and subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0
            checks.append(_check("gh", bool(authed) or None, "autenticado" if authed else
                                 ("não autenticado" if gh else "não instalado"),
                                 "" if authed else "necessário para abrir PRs: gh auth login"))
    on_path = shutil.which("ravend")
    checks.append(_check("comando ravend", bool(on_path) or None, on_path or "não instalado",
                         "" if on_path else f"opcional: python3 {PLUGIN_ROOT}/scripts/ravend.py install-cli"))
    return checks


def print_doctor(checks: list[dict]) -> int:
    marks = {"ok": " ok  ", "warn": "aviso", "fail": "ERRO "}
    for c in checks:
        print(f"  [{marks[c['status']]}] {c['check']}: {c['detail']}")
        if c["fix"] and c["status"] != "ok":
            print(f"          → {c['fix']}")
    fails = sum(1 for c in checks if c["status"] == "fail")
    warns = sum(1 for c in checks if c["status"] == "warn")
    print("Tudo certo." if not fails and not warns else f"{fails} erro(s), {warns} aviso(s).")
    return 1 if fails else 0
