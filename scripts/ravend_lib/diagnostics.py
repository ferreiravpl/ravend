"""`ravend doctor`: checks the installation and the project setup and says how to fix each problem."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .core import PLUGIN_ROOT, data_dir, load_json, load_profile, ravend_home, save_json
from .detection import ci_workflows
from .mcp import integrations, mcp_servers

# --------------------------------------------------------------------------- gate × CI
# What CI runs is the team's definition of "green". The local gate.full should run at least the same checks,
# or "green here, red in CI" becomes routine. The comparison is by tool + subcommand, not by exact text.

SETUP_WORDS = {"echo", "cd", "export", "mkdir", "cp", "mv", "rm", "ls", "cat", "curl", "wget", "sudo", "apt", "apt-get",
               "chmod", "set", "source", "printf", "tee", "test", "[", "true", "unzip", "tar", "if", "then", "else", "fi",
               "for", "do", "done", "while", "env", "sleep", "which", "git", "gh", "aws", "docker", "base64", "jq", "sed",
               "awk", "grep", "eval", "kubectl", "pip", "pip3", "python", "python3", "node", "corepack", "sdk", "exit"}
SKIP_SUBCOMMANDS = {"terraform": {"init", "apply", "plan", "output", "workspace", "version"},
                    "helm": {"upgrade", "install", "package", "push", "registry", "repo", "dependency", "version"},
                    "npm": {"ci", "install", "i", "publish"}, "pnpm": {"install", "i", "publish"},
                    "yarn": {"install", "publish"}}
MAVEN_PHASES = ["validate", "compile", "test-compile", "test", "package", "integration-test", "verify", "install", "deploy"]
GRADLE_COVERS = {"build": {"build", "check", "test", "assemble", "compileJava", "compileTestJava"}, "check": {"check", "test"}}


def _keys(cmd: str) -> set[str]:
    return {k for part in re.split(r"&&|\|\||[|;]", cmd) for k in _segment_keys(part)}


def _segment_keys(cmd: str) -> set[str]:
    words = [w for w in cmd.split() if not re.match(r"^[A-Z_][A-Z0-9_]*=", w)]
    if not words:
        return set()
    tool = words[0]
    if tool in ("npx", "pnpx", "bunx") and len(words) > 1:
        words = words[1:]
        tool = words[0]
    tool = {"./mvnw": "mvn", "mvnw": "mvn", "./gradlew": "gradle", "gradlew": "gradle", "tofu": "terraform"}.get(tool, tool)
    rest = [w for w in words[1:] if not w.startswith("-") and "=" not in w]
    if tool in SETUP_WORDS or tool.startswith(("$", "#")):
        return set()
    if tool == "mvn":
        profiles = sorted({p for w in words if w.startswith("-P") for p in w[2:].split(",") if p}
                          | ({"native"} if any(re.match(r"-D(native|quarkus\.native\.enabled=true|quarkus\.package\.type=native)", w)
                                               for w in words) else set()))
        tag = f" [{','.join(profiles)}]" if profiles else ""
        phases = [w for w in rest if w in MAVEN_PHASES]
        keys = {f"mvn {w}{tag}" for w in rest if ":" in w and not w.startswith("$")}
        return keys | ({f"mvn {max(phases, key=MAVEN_PHASES.index)}{tag}"} if phases else set())
    if tool == "gradle":
        return {f"gradle {w.split(':')[-1]}" for w in rest if re.match(r"^[\w:-]+$", w)}
    sub = rest[0] if rest and re.match(r"^[a-z][\w:-]*$", rest[0]) else ""
    if tool in ("npm", "pnpm", "yarn") and sub == "run" and len(rest) > 1:
        sub = rest[1]
    if sub in SKIP_SUBCOMMANDS.get(tool, set()):
        return set()
    return {f"{tool} {sub}".strip()}


def _covered(key: str, gate_keys: set[str]) -> bool:
    if key in gate_keys:
        return True
    tool, _, sub = key.partition(" ")
    if tool == "mvn":
        phase, _, tag = sub.partition(" ")
        if phase not in MAVEN_PHASES:
            return False
        for k in gate_keys:
            g_tool, _, g_sub = k.partition(" ")
            g_phase, _, g_tag = g_sub.partition(" ")
            if g_tool == "mvn" and g_tag == tag and g_phase in MAVEN_PHASES \
                    and MAVEN_PHASES.index(g_phase) >= MAVEN_PHASES.index(phase):
                return True
        return False
    if tool == "gradle":
        return any(sub in GRADLE_COVERS.get(k[7:], ()) for k in gate_keys if k.startswith("gradle "))
    return False


def ci_drift(root: Path, profile: dict) -> list[str]:
    """CI commands (tool + subcommand) that no gate.full step runs."""
    gate_keys = {k for step in (profile.get("gate") or {}).get("full") or [] for k in _keys(step.get("run") or "")}
    missing: dict[str, str] = {}
    for wf in ci_workflows(root):
        for cmd in wf["runs"]:
            for key in _keys(cmd):
                if not _covered(key, gate_keys):
                    missing.setdefault(key, wf["file"])
    return [f"`{k}` ({f})" for k, f in missing.items()]

# --------------------------------------------------------------------------- doctor

def _check(name: str, ok: bool | None, detail: str, fix: str = "") -> dict:
    return {"check": name, "status": "ok" if ok else ("warn" if ok is None else "fail"), "detail": detail, "fix": fix}


def _plugin_manifest() -> dict:
    return load_json(PLUGIN_ROOT / ".claude-plugin" / "plugin.json", {}) or {}


def _plugin_version() -> str:
    return _plugin_manifest().get("version", "?")


# Update check: the published version and changelog are read from the plugin's repository (main branch),
# at most once per UPDATE_TTL_SECONDS, never blocking a session for more than UPDATE_TIMEOUT_SECONDS.
UPDATE_COMMAND = "claude plugin marketplace update ravend && claude plugin update ravend@ravend"
UPDATE_TTL_SECONDS = 12 * 3600
FAILED_CHECK_TTL_SECONDS = 3600
UPDATE_TIMEOUT_SECONDS = 2
MAX_CHANGE_LINES = 12
_CHANGELOG_HEADING = re.compile(r"^##\s*\[?v?(\d+\.\d+\.\d+)")
_CHANGELOG_ITEM = re.compile(r"^\s*[-*]\s+(.+)")


def _version_key(version: str) -> tuple:
    return tuple(int(part) for part in re.findall(r"\d+", version)[:3])


def _published_base_url() -> str | None:
    """Raw-file URL of the plugin's main branch; RAVEND_UPDATE_URL overrides it (tests, mirrors)."""
    override = os.environ.get("RAVEND_UPDATE_URL")
    if override:
        return override.rstrip("/")

    github = re.match(r"https://github\.com/([^/]+/[^/#?]+?)(?:\.git)?/?$", _plugin_manifest().get("repository", ""))
    if not github:
        return None

    return f"https://raw.githubusercontent.com/{github.group(1)}/main"


def _download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=UPDATE_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def _fetch_published(base_url: str) -> dict | None:
    try:
        version = json.loads(_download_text(base_url + "/.claude-plugin/plugin.json")).get("version")
    except (OSError, ValueError):
        return None

    try:
        changelog = _download_text(base_url + "/CHANGELOG.md")
    except (OSError, ValueError):
        changelog = ""

    return {"version": version, "changelog": changelog}


def _published_release() -> dict | None:
    """{"version", "changelog"} of the published plugin, cached in RAVEND_HOME; None when it cannot be known."""
    cache_file = ravend_home() / "update-check.json"
    cached = load_json(cache_file, {}) or {}
    ttl = UPDATE_TTL_SECONDS if cached.get("published") else FAILED_CHECK_TTL_SECONDS
    if time.time() - cached.get("checked_at", 0) < ttl:
        return cached.get("published")

    base_url = _published_base_url()
    published = _fetch_published(base_url) if base_url else None
    try:
        save_json(cache_file, {"checked_at": time.time(), "published": published})
    except OSError:
        pass

    return published


def changes_since(changelog: str, installed: str, published: str) -> list[str]:
    """One "<version> — <change>" line per changelog item newer than `installed`, up to `published`."""
    lines, version = [], None
    for line in changelog.splitlines():
        heading = _CHANGELOG_HEADING.match(line)
        if heading:
            version = heading.group(1)
            continue

        item = _CHANGELOG_ITEM.match(line)
        if item and version and _version_key(installed) < _version_key(version) <= _version_key(published):
            lines.append(f"{version} — {item.group(1).strip()}")

    return lines[:MAX_CHANGE_LINES]


def available_update() -> dict | None:
    """{"installed", "published", "changes"} when a newer Ravend is published; None otherwise or when unknown."""
    installed = _plugin_version()
    published = _published_release()
    if not published or not published.get("version"):
        return None

    if _version_key(published["version"]) <= _version_key(installed):
        return None

    changes = changes_since(published.get("changelog") or "", installed, published["version"])
    return {"installed": installed, "published": published["version"], "changes": changes}


def _update_check() -> dict:
    update = available_update()
    if not update:
        return _check("atualização", True, "nenhuma versão mais nova publicada (ou sem rede)")

    detail = f"instalada {update['installed']}, publicada {update['published']}"
    detail += "".join(f"\n          {change}" for change in update["changes"])
    return _check("atualização", None, detail, f"{UPDATE_COMMAND} e reinicie o Claude Code")


def doctor(root: Path | None, probe: bool = True) -> list[dict]:
    checks = [_check("python", sys.version_info >= (3, 8), sys.version.split()[0], "instale Python 3.8+"),
              _check("git", bool(shutil.which("git")), shutil.which("git") or "não encontrado", "instale o git"),
              _check("claude", bool(shutil.which("claude")), shutil.which("claude") or "não encontrado",
                     "necessário para `ravend auto`; instale o Claude Code CLI"),
              _check("plugin", True, f"Ravend {_plugin_version()} em {PLUGIN_ROOT}")]
    if probe:
        checks.append(_update_check())
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
        if ci_workflows(root):
            drift = ci_drift(root, profile)
            checks.append(_check("gate × CI", not drift or None,
                                 "o gate full cobre o que o CI roda" if not drift else
                                 "o CI roda e o gate full não: " + ", ".join(drift[:6]),
                                 "inclua esses passos no gate.full (rode /ravend:init → comandos do gate) para "
                                 "não descobrir o vermelho só no PR" if drift else ""))
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
