#!/usr/bin/env python3
"""Ravend runtime — project identity, per-developer local data, quality gate, app lifecycle and hooks.

Standard library only (Python 3.8+). Everything Ravend learns or produces about a project lives
outside the repository, under $RAVEND_HOME (default ~/.ravend)/projects/<project-id>/:

    profile.json   commands the gate runs (written by /ravend:init)
    project.md     short, human-editable notes about the project's conventions
    knowledge/     lessons learned (index.md + one file per lesson)
    specs/<slug>/  spec.md, review-N.md, verify.md, evidence/
    runs/          gate and app logs
    state/<checkout>/  gate state per clone/worktree (armed session, last green tree, block counter, app pids)

Usage:
    ravend.py project                    print project identity/paths/integrations as JSON
    ravend.py detect                     print detected stacks/tooling as JSON
    ravend.py mcp [--no-probe]           list the developer's MCP servers (user/local/project/plugins/claude.ai)
    ravend.py integrations [--stage S]   MCP servers chosen per role in profile.json
    ravend.py gate [fast|full] [--dry-run] [--scope worktree|branch]
    ravend.py app start|stop|status
    ravend.py arm | disarm               enable/disable the Stop-hook gate for this session
    ravend.py status [--json]            active specs + last gate result
    ravend.py install-cli [--dir DIR]    install the `ravend` terminal command (default ~/.local/bin)
    ravend.py hook <session-start|pre-edit|post-edit|stop>   (stdin: hook JSON)
"""
from __future__ import annotations

import fnmatch
import hashlib
import io
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from contextlib import ExitStack, contextmanager
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: no cross-process locks (native Windows is unsupported anyway)
    fcntl = None

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROTECTED = [".env", ".env.local", ".env.*.local", "*.pem", "*.key", "*id_rsa*"]
ERROR_RE = re.compile(
    r"(error|fail|failed|failure|exception|assert|expected|✗|×|\[ERROR\]|BUILD FAILURE|Tests run:.*Failures: [1-9])",
    re.IGNORECASE,
)
SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", ".gradle", ".idea", ".vscode", "coverage", ".angular", ".next", "out"}


# --------------------------------------------------------------------------- paths & identity

def ravend_home() -> Path:
    # EVAL_RAVEND_HOME exists only for `claude plugin eval`, which lets cases set EVAL_* variables only.
    home = os.environ.get("RAVEND_HOME") or os.environ.get("EVAL_RAVEND_HOME") or Path.home() / ".ravend"
    return Path(home).expanduser().resolve()


def git(args: list[str], cwd: Path, env: dict | None = None) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def repo_root(cwd: Path) -> Path | None:
    top = git(["rev-parse", "--show-toplevel"], cwd)
    return Path(top) if top else None


def _slug(text: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9._-]+", "-", text.lower())).strip("-.")


def project_id(root: Path) -> str:
    """Stable id shared by every clone/worktree of the same repo: derived from origin, else the git dir."""
    remote = git(["config", "--get", "remote.origin.url"], root)
    if remote:
        r = re.sub(r"^[a-z+]+://", "", remote.strip())
        r = re.sub(r"^[^@/]+@", "", r)
        r = re.sub(r"\.git/?$", "", r).replace(":", "/")
        return _slug(r)
    common = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], root) or str(root)
    base = Path(common).parent if common.endswith(".git") else Path(common)
    return f"{_slug(base.name)}-{hashlib.sha1(str(base).encode()).hexdigest()[:8]}"


def data_dir(root: Path) -> Path:
    return ravend_home() / "projects" / project_id(root)


def state_dir(root: Path) -> Path:
    """Gate/app state is per checkout: the main clone and each git worktree get their own, so parallel
    runs on different worktrees never overwrite each other's gate result. Specs/knowledge stay shared."""
    key = f"{_slug(root.name) or 'repo'}-{hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:8]}"
    return data_dir(root) / "state" / key


@contextmanager
def file_lock(path: Path, blocking: bool = True, wait_msg: str = ""):
    """Exclusive cross-process lock. Yields True when held, False when non-blocking and busy."""
    if fcntl is None:
        yield True
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if not blocking:
                yield False
                return
            if wait_msg:
                print(wait_msg, flush=True)
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def ensure_dirs(d: Path) -> None:
    for sub in ("knowledge", "specs", "runs", "state"):
        try:
            (d / sub).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # read-only home (sandbox/CI): commands that need to write will report it


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_profile(root: Path) -> dict | None:
    return load_json(data_dir(root) / "profile.json")


def base_branch(root: Path, profile: dict | None) -> str:
    configured = ((profile or {}).get("git") or {}).get("base_branch")
    if configured:
        return configured
    head = git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], root)
    if head:
        return head
    for name in ("main", "master", "develop"):
        if git(["rev-parse", "--verify", "--quiet", name], root):
            return name
    return "HEAD"


# --------------------------------------------------------------------------- changes & fingerprint

def changed_files(root: Path, scope: str, profile: dict | None) -> list[str]:
    files: set[str] = set()
    has_head = git(["rev-parse", "--verify", "--quiet", "HEAD"], root) is not None
    if has_head:
        files.update((git(["diff", "--name-only", "HEAD"], root) or "").splitlines())
    files.update((git(["diff", "--name-only", "--cached"], root) or "").splitlines())
    files.update((git(["ls-files", "--others", "--exclude-standard"], root) or "").splitlines())
    if scope == "branch" and has_head:
        base = base_branch(root, profile)
        mb = git(["merge-base", "HEAD", base], root)
        if mb:
            files.update((git(["diff", "--name-only", mb, "HEAD"], root) or "").splitlines())
    return sorted(f for f in files if f)


def tree_fingerprint(root: Path) -> str | None:
    """Hash of the full working tree content (tracked + untracked, honoring .gitignore).
    Identical content gives the same id whether it is committed or not."""
    index = git(["rev-parse", "--path-format=absolute", "--git-path", "index"], root)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_index = Path(tmp) / "index"
        if index and Path(index).exists():
            shutil.copyfile(index, tmp_index)
        env = {**os.environ, "GIT_INDEX_FILE": str(tmp_index)}
        if git(["add", "-A"], root, env=env) is None:
            return None
        return git(["write-tree"], root, env=env)


# --------------------------------------------------------------------------- gate

def _matches(path: str, patterns) -> bool:
    if not patterns:
        return True
    if isinstance(patterns, str):
        patterns = [patterns]
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def _java_tests(files: list[str]) -> str:
    names: list[str] = []
    for f in files:
        if not f.endswith((".java", ".kt")):
            continue
        stem = Path(f).stem
        if "/src/test/" in f"/{f}" or stem.endswith(("Test", "Tests", "IT")):
            names.append(stem)
        elif "/src/main/" in f"/{f}":
            names.append(f"{stem}*Test")
    return ",".join(dict.fromkeys(names))


def _relative_to_cwd(files: list[str], cwd_rel: str) -> list[str]:
    if not cwd_rel or cwd_rel == ".":
        return files
    prefix = cwd_rel.rstrip("/") + "/"
    return [f[len(prefix):] if f.startswith(prefix) else os.path.relpath(f, cwd_rel) for f in files]


def resolve_step(step: dict, root: Path, changed: list[str], base: str) -> tuple[str | None, str]:
    """Return (command, reason). command None means the step is skipped."""
    when = step.get("when")
    relevant = [f for f in changed if _matches(f, when)] if when else list(changed)
    if when and not relevant:
        return None, "no changed files match `when`"
    cwd_rel = step.get("cwd", ".")
    existing = [f for f in relevant if (root / f).exists()]
    cmd = step["run"]
    if "{files}" in cmd:
        rel = [f for f in _relative_to_cwd(existing, cwd_rel) if _matches(f, step.get("files_glob"))]
        if not rel:
            return None, "no existing changed files for {files}"
        cmd = cmd.replace("{files}", " ".join(shlex.quote(f) for f in rel))
    for placeholder in ("{java_tests}", "{gradle_tests}"):
        if placeholder in cmd:
            tests = _java_tests(existing)
            if not tests:
                return None, "no Java tests related to the change"
            value = (shlex.quote(tests) if placeholder == "{java_tests}"
                     else " ".join(f"--tests {shlex.quote(t)}" for t in tests.split(",")))
            cmd = cmd.replace(placeholder, value)
    return cmd.replace("{base}", shlex.quote(base)), ""


def run_cmd(cmd: str, cwd: Path, timeout: int, log: Path) -> tuple[int, float, str, str | None]:
    """Run a step. Returns (exit code, seconds, combined output, log path or None if it could not be saved).
    Output is captured in memory so the gate still works when the data dir is read-only (sandboxes, CI)."""
    start = time.time()
    try:
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=True)
    except OSError as exc:
        return 127, 0.0, f"[ravend] could not start: {exc}", None
    try:
        out, _ = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        _kill_group(proc.pid)
        out, _ = proc.communicate()
        out = (out or b"") + f"\n[ravend] TIMEOUT after {timeout}s\n".encode()
        code = 124
    text = (out or b"").decode("utf-8", errors="replace")
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"$ (cd {cwd} && {cmd})\n{text}", encoding="utf-8")
        saved: str | None = str(log)
    except OSError:
        saved = None
    return code, time.time() - start, text, saved


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGTERM)
        time.sleep(2)
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def failure_excerpt(output: str, tail: int) -> str:
    """Error-looking lines (max 25) plus the last `tail` lines, in original order, with gap markers."""
    lines = output.splitlines()
    hits = [i for i, ln in enumerate(lines) if ERROR_RE.search(ln)][:25]
    keep = sorted(set(hits) | set(range(max(0, len(lines) - tail), len(lines))))
    out, prev = [], -1
    for i in keep:
        if i != prev + 1:
            out.append("  …")
        out.append(lines[i][:400])
        prev = i
    return "\n".join(out)


def gate(root: Path, mode: str = "fast", scope: str | None = None, dry_run: bool = False) -> int:
    profile = load_profile(root)
    if not profile:
        print("[ravend] no local profile for this project. Run /ravend:init first.")
        return 2
    steps = ((profile.get("gate") or {}).get(mode)) or []
    if not steps:
        print(f"[ravend] gate.{mode} has no steps in profile.json")
        return 2
    scope = scope or ("branch" if mode == "full" else "worktree")
    changed = changed_files(root, scope, profile)
    base = base_branch(root, profile)
    tail = int((profile.get("gate") or {}).get("tail_lines", 60))
    d, st = data_dir(root), state_dir(root)
    run_dir = d / "runs" / f"gate-{mode}-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    results, app_started = [], False
    locks = ExitStack()
    print(f"[ravend] gate {mode} · {len(changed)} changed file(s) · scope={scope}")
    for step in steps:
        name = step.get("name", "step")
        cmd, why = resolve_step(step, root, changed, base)
        if cmd is None:
            print(f"  - {name}: SKIP ({why})")
            results.append({"name": name, "status": "SKIP", "reason": why})
            continue
        if dry_run:
            print(f"  - {name}: would run in ./{step.get('cwd', '.')}: {cmd}")
            continue
        if step.get("needs_app") and not app_started:
            # the app binds fixed ports: worktrees running gates in parallel take turns
            locks.enter_context(file_lock(d / "state" / "app.lock",
                                          wait_msg="  · app: waiting — another checkout is using it"))
            ok, msg = app_start(root, profile)
            print(f"  · app: {msg}")
            if not ok:
                results.append({"name": name, "status": "FAIL", "reason": f"app did not start: {msg}"})
                break
            app_started = True
        log = run_dir / f"{_slug(name)}.log"
        code, secs, output, saved = run_cmd(cmd, root / step.get("cwd", "."), int(step.get("timeout", 900)), log)
        status = "PASS" if code == 0 else ("TIMEOUT" if code == 124 else "FAIL")
        print(f"  - {name}: {status} ({secs:.0f}s)")
        results.append({"name": name, "status": status, "exit": code, "seconds": round(secs, 1), "log": saved})
        if code != 0:
            where = f"full log: {saved}" if saved else "log not saved (data dir not writable)"
            print(f"\n----- {name} (exit {code}) — {where}\n{failure_excerpt(output, tail)}\n-----")
            if not step.get("continue_on_fail"):
                break
    if app_started:
        app_stop(root)
    locks.close()
    if dry_run:
        return 0
    failed = [r for r in results if r["status"] in ("FAIL", "TIMEOUT")]
    ran = [r for r in results if r["status"] != "SKIP"]
    status = "FAIL" if failed else ("PASS" if ran else "EMPTY")
    state = {"mode": mode, "status": status, "at": datetime.now().isoformat(timespec="seconds"),
             "fingerprint": tree_fingerprint(root), "steps": results}
    try:
        save_json(st / f"last-gate-{mode}.json", state)
        if status == "PASS":
            green = load_json(st / "green.json", {}) or {}
            green[mode] = state["fingerprint"]
            save_json(st / "green.json", green)
    except OSError:
        print("[ravend] warning: could not record gate state (data dir not writable)")
    summary = ", ".join(f"{r['name']}={r['status']}" for r in results) or "nothing to run"
    print(f"RAVEND_GATE {mode.upper()}: {status} [{summary}]")
    return 1 if failed else 0


# --------------------------------------------------------------------------- app lifecycle

def _apps(profile: dict) -> list[dict]:
    app = profile.get("app")
    return app if isinstance(app, list) else ([app] if app else [])


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310 - local healthcheck
            return 200 <= resp.status < 400
    except Exception:
        return False


def app_start(root: Path, profile: dict) -> tuple[bool, str]:
    apps = _apps(profile)
    if not apps:
        return False, "profile.app is not configured"
    d, st = data_dir(root), state_dir(root)
    pids = load_json(st / "app.json", {}) or {}
    for app in apps:
        name = app.get("name", "app")
        url = app.get("healthcheck")
        if url and _http_ok(url):
            continue  # already running (maybe started by the developer)
        log = d / "runs" / f"app-{_slug(name)}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        fh = log.open("w", encoding="utf-8")
        proc = subprocess.Popen(app["start"], shell=True, cwd=root / app.get("cwd", "."), stdout=fh,
                                stderr=subprocess.STDOUT, start_new_session=True)
        pids[name] = proc.pid
        save_json(st / "app.json", pids)
        deadline = time.time() + int(app.get("timeout", 180))
        while url and time.time() < deadline:
            if proc.poll() is not None:
                return False, f"{name} exited with {proc.returncode}; log: {log}"
            if _http_ok(url):
                break
            time.sleep(2)
        else:
            if url:
                return False, f"{name} not healthy at {url} after {app.get('timeout', 180)}s; log: {log}"
    return True, "running: " + ", ".join(a.get("name", "app") for a in apps)


def app_stop(root: Path) -> None:
    st = state_dir(root)
    for pid in (load_json(st / "app.json", {}) or {}).values():
        _kill_group(int(pid))
    save_json(st / "app.json", {})


# --------------------------------------------------------------------------- MCP integrations
# The developer's own MCP servers, mapped to the roles the pipeline knows how to use. The mapping lives in
# profile.json ("integrations": {role: [server name, ...]}) and is written by /ravend:init after asking.

ROLES = {
    "issues":        ("Issue tracker: read tickets/acceptance notes (Jira, Linear, GitHub/GitLab issues)", ["spec"]),
    "git":           ("Git hosting: issues, PRs, CI checks, review comments (GitHub, GitLab, Bitbucket)",
                      ["spec", "review", "ship"]),
    "context":       ("Code context: semantic search, symbol navigation, codebase index (Serena, Sourcegraph…)",
                      ["spec", "build", "review"]),
    "docs":          ("Library/framework documentation, version-correct APIs (Context7, vendor docs)", ["spec", "build"]),
    "knowledge":     ("Internal docs and decisions: wiki, ADRs, product docs (Confluence, Notion, Drive)", ["spec"]),
    "design":        ("UI design source: frames, tokens, specs (Figma)", ["spec", "build", "verify"]),
    "browser":       ("Drive a browser to explore UI for E2E/visual tests (Playwright, Chrome DevTools)", ["verify"]),
    "api":           ("Call/test HTTP APIs, collections, contracts (Postman, api-test)", ["verify"]),
    "database":      ("Inspect schema and data (Postgres, MySQL, Mongo…), read-only", ["spec", "build", "verify"]),
    "observability": ("Errors, logs, traces, metrics (Sentry, Datadog, Grafana)", ["spec", "verify"]),
}
STAGES = ["spec", "build", "verify", "review", "ship"]


def mcp_tool_prefix(server: str) -> str:
    """Permission/tool prefix Claude Code gives a server's tools: mcp__<name with non [A-Za-z0-9_-] as _>."""
    return "mcp__" + re.sub(r"[^A-Za-z0-9_-]", "_", server)


def claude_config_file() -> Path:
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(cfg) / ".claude.json" if cfg else Path.home() / ".claude.json"


def _mcp_hint(conf: dict) -> tuple[str, str]:
    """(transport, short non-secret hint) — never args with values, env or headers."""
    if conf.get("url"):
        return conf.get("type", "http"), urllib.parse.urlparse(conf["url"]).netloc
    words = [conf.get("command", "")] + [a for a in conf.get("args", []) if isinstance(a, str)]
    pkg = next((w for w in words[1:] if not w.startswith("-") and not re.search(r"[:=]", w)
                and ("mcp" in w.lower() or w.startswith("@"))), "")
    return "stdio", " ".join(x for x in (Path(words[0]).name, pkg) if x)


def _list_line(line: str) -> dict | None:
    """Parse one `claude mcp list` line: `<name>: <command or url> - <status>`."""
    m = re.match(r"^(?P<name>[^\s].*?): (?P<target>.+) - (?P<status>[^-]+)$", line.strip())
    if not m:
        return None
    target = m.group("target").strip()
    if re.match(r"^https?://", target):
        transport, hint = "http", urllib.parse.urlparse(target).netloc
    else:
        transport, hint = _mcp_hint({"command": target.split(" ")[0], "args": target.split(" ")[1:]})
    return {"name": m.group("name").strip(), "transport": transport, "hint": hint,
            "status": re.sub(r"^[^\w]+", "", m.group("status").strip())}


def mcp_servers(root: Path, probe: bool = True) -> list[dict]:
    """Every MCP server the developer has for this repo. Config files first (fast, offline); then
    `claude mcp list`, which also sees plugin servers and claude.ai connectors and reports health."""
    found: dict[str, dict] = {}

    def add(name: str, source: str, conf: dict | None = None, **extra) -> None:
        row = found.setdefault(name, {"name": name, "source": source, "tools": mcp_tool_prefix(name)})
        if conf is not None:
            row["transport"], row["hint"] = _mcp_hint(conf)
        row.update({k: v for k, v in extra.items() if v})

    cfg = load_json(claude_config_file(), {}) or {}
    for name, conf in (cfg.get("mcpServers") or {}).items():
        add(name, "user", conf)
    for name, conf in (((cfg.get("projects") or {}).get(str(root)) or {}).get("mcpServers") or {}).items():
        add(name, "local", conf)
    for name, conf in ((load_json(root / ".mcp.json", {}) or {}).get("mcpServers") or {}).items():
        add(name, "project", conf)
    if probe and shutil.which("claude"):
        try:
            out = subprocess.run(["claude", "mcp", "list"], cwd=root, capture_output=True, text=True,
                                 timeout=90).stdout
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        for line in out.splitlines():
            row = _list_line(line)
            if not row:
                continue
            source = ("claude.ai" if row["name"].startswith("claude.ai ") else
                      "plugin" if row["name"].startswith("plugin:") else "listed")
            known = found.get(row["name"])
            add(row["name"], known["source"] if known else source, status=row["status"],
                transport=None if known and known.get("transport") else row["transport"],
                hint=None if known and known.get("hint") else row["hint"])
    return sorted(found.values(), key=lambda r: (r["source"], r["name"].lower()))


def integrations(profile: dict | None, stage: str | None = None) -> dict:
    """{role: {"servers": [...], "tools": [mcp__…], "stages": [...], "purpose": ...}} from profile.integrations."""
    out = {}
    for role, servers in ((profile or {}).get("integrations") or {}).items():
        servers = [servers] if isinstance(servers, str) else [s for s in (servers or []) if isinstance(s, str)]
        if not servers:
            continue
        purpose, stages = ROLES.get(role, ("custom role", STAGES))
        if stage and stage not in stages:
            continue
        out[role] = {"servers": servers, "tools": [mcp_tool_prefix(s) for s in servers],
                     "stages": stages, "purpose": purpose}
    return out


def integration_tools(profile: dict | None, stage: str | None = None) -> list[str]:
    return list(dict.fromkeys(t for r in integrations(profile, stage).values() for t in r["tools"]))


def local_mcp_config(root: Path) -> dict:
    """Local-scope servers of this checkout (keyed by path in ~/.claude.json). A git worktree has another
    path, so the headless runner passes these explicitly when it works in a worktree."""
    cfg = load_json(claude_config_file(), {}) or {}
    return dict((((cfg.get("projects") or {}).get(str(root)) or {}).get("mcpServers") or {}))


# --------------------------------------------------------------------------- terminal command

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


# --------------------------------------------------------------------------- detection

def _read(p: Path, limit: int = 200_000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def detect(root: Path) -> dict:
    found: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS and not x.startswith(".")]
        if len(rel.parts) > 3:
            dirnames[:] = []
            continue
        names = set(filenames)
        mod: dict = {"path": str(rel) if str(rel) != "." else "."}
        build_file = next((n for n in ("pom.xml", "build.gradle.kts", "build.gradle") if n in names), None)
        if build_file:
            text = _read(Path(dirpath) / build_file)
            mod["build"] = "maven" if build_file == "pom.xml" else "gradle"
            mod["wrapper"] = ("mvnw" in names) if build_file == "pom.xml" else ("gradlew" in names)
            mod["stack"] = "quarkus" if "io.quarkus" in text else ("spring" if "spring-boot" in text else "java")
            mod["signals"] = [s for s, k in (("testcontainers", "testcontainers"), ("spotless", "spotless"),
                              ("checkstyle", "checkstyle"), ("jacoco", "jacoco"), ("pitest", "pitest"),
                              ("springdoc", "springdoc"), ("smallrye-openapi", "smallrye-openapi"),
                              ("archunit", "archunit"), ("lombok", "lombok")) if k in text]
            is_root_aggregator = "<modules>" in text
            if not is_root_aggregator or rel == Path("."):
                found.append(mod)
            continue
        if "package.json" in names:
            pkg = load_json(Path(dirpath) / "package.json", {}) or {}
            deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
            stack = "angular" if "@angular/core" in deps else ("react" if "react" in deps else
                    ("vue" if "vue" in deps else "node"))
            mod.update({
                "build": "pnpm" if "pnpm-lock.yaml" in names else "yarn" if "yarn.lock" in names
                else "bun" if ("bun.lockb" in names or "bun.lock" in names) else "npm",
                "stack": stack,
                "versions": {k: deps[k] for k in ("@angular/core", "react", "vite", "typescript", "next") if k in deps},
                "scripts": sorted((pkg.get("scripts") or {}).keys()),
                "test_runner": next((t for t in ("vitest", "jest", "karma", "@playwright/test") if t in deps), None),
                "signals": [s for s in ("@playwright/test", "eslint", "prettier", "@biomejs/biome", "msw",
                                        "@testing-library/react", "@stryker-mutator/core", "tailwindcss")
                            if s in deps],
            })
            if any(n.startswith("playwright.config") for n in names):
                mod["signals"].append("playwright.config")
            found.append(mod)
    compose = [str(p.relative_to(root)) for p in root.glob("*compose*.y*ml")]
    return {"root": str(root), "modules": found, "stacks": sorted({m["stack"] for m in found}),
            "docker_compose": compose, "has_claude_md": (root / "CLAUDE.md").exists()}


# --------------------------------------------------------------------------- specs & status

def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    out = {}
    for line in (m.group(1).splitlines() if m else []):
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


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


# --------------------------------------------------------------------------- hooks

def _hook_input() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}


def _hook_root(inp: dict) -> Path | None:
    return repo_root(Path(inp.get("cwd") or os.getcwd()))


def hook_session_start(inp: dict) -> int:
    root = _hook_root(inp)
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if env_file:
        lines = [f"export RAVEND_ROOT={shlex.quote(str(PLUGIN_ROOT))}"]
        if inp.get("session_id"):
            lines.append(f"export RAVEND_SESSION_ID={shlex.quote(inp['session_id'])}")
        if root:
            lines.append(f"export RAVEND_DATA={shlex.quote(str(data_dir(root)))}")
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    if not root:
        return 0
    d = data_dir(root)
    profile = load_profile(root)
    cli = f"python3 {PLUGIN_ROOT}/scripts/ravend.py"
    if not profile:
        if any((root / f).exists() for f in ("pom.xml", "build.gradle", "build.gradle.kts", "package.json")):
            print("[ravend] This repo has no local Ravend profile. Run /ravend:init once (it detects the gate "
                  "commands and lets the developer pick which of their MCP servers the pipeline should use).")
        return 0
    out = [f"[ravend] project `{project_id(root)}` — local data dir (never committed): {d}",
           f"stacks: {', '.join(profile.get('stacks', [])) or '?'} · gate: `{cli} gate fast|full` · status: `{cli} status`"]
    chosen = integrations(profile)
    if chosen:
        out.append("integrations (the developer's MCP servers for each role — prefer them in the listed stages; "
                   "skip one that is not connected): " + " · ".join(
                       f"{role}→{', '.join(r['servers'])} [{'/'.join(r['stages'])}]" for role, r in chosen.items()))
    notes = d / "project.md"
    if notes.exists():
        body = _read(notes).strip().splitlines()
        out.append("project notes (project.md):" if len(body) <= 60 else f"project notes: {notes} (read when relevant)")
        if len(body) <= 60:
            out.extend(body)
    index = d / "knowledge" / "index.md"
    if index.exists():
        lessons = [ln for ln in _read(index).splitlines() if ln.startswith("- ")]
        if lessons:
            out.append(f"knowledge ({len(lessons)} lessons, files in {d / 'knowledge'}):")
            out.extend(lessons[:25])
    active = [s for s in specs_status(d) if s["status"] not in ("done", "abandoned")][:3]
    for s in active:
        out.append(f"active spec `{s['slug']}` [{s['status']}] {s['done']}/{s['total']} tasks · {s['path']}")
    if active:
        out.append("To resume, the developer runs /ravend:continue (it asks `ravend.py next` what comes next).")
    print("\n".join(out))
    return 0


def _tool_path(inp: dict, root: Path) -> str | None:
    ti = inp.get("tool_input") or {}
    p = ti.get("file_path") or ti.get("notebook_path") or ti.get("path")
    if not p:
        return None
    try:
        return str(Path(p).resolve().relative_to(root.resolve()))
    except ValueError:
        return None


def hook_pre_edit(inp: dict) -> int:
    root = _hook_root(inp)
    profile = load_profile(root) if root else None
    if not profile:
        return 0
    rel = _tool_path(inp, root)
    if rel is None:
        return 0
    patterns = profile.get("protected_paths", DEFAULT_PROTECTED)
    name = Path(rel).name
    hit = next((p for p in patterns if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p)), None)
    if hit:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"Ravend: `{rel}` matches protected path `{hit}` (profile.protected_paths). "
                                        "Ask the developer to change it manually."}}))
    return 0


def hook_post_edit(inp: dict) -> int:
    root = _hook_root(inp)
    profile = load_profile(root) if root else None
    if not profile or os.environ.get("RAVEND_FORMAT") == "off":
        return 0
    rel = _tool_path(inp, root)
    if rel is None or not (root / rel).exists():
        return 0
    for rule in profile.get("format", []):
        if not _matches(rel, rule.get("glob")):
            continue
        cwd_rel = rule.get("cwd", ".")
        target = _relative_to_cwd([rel], cwd_rel)[0]
        cmd = rule["run"].replace("{file}", shlex.quote(target))
        try:
            res = subprocess.run(cmd, shell=True, cwd=root / cwd_rel, capture_output=True, text=True,
                                 timeout=int(rule.get("timeout", 30)))
        except subprocess.TimeoutExpired:
            return 0
        if res.returncode != 0:
            msg = (res.stderr or res.stdout).strip().splitlines()[-15:]
            print(f"[ravend] formatter failed on {rel} (`{cmd}`):\n" + "\n".join(msg), file=sys.stderr)
            return 2
        return 0
    return 0


def hook_stop(inp: dict) -> int:
    if os.environ.get("RAVEND_GATE") == "off":
        return 0
    root = _hook_root(inp)
    profile = load_profile(root) if root else None
    if not profile:
        return 0
    st = state_dir(root)
    armed = load_json(st / "armed.json")
    if not armed or armed.get("session") not in ("*", inp.get("session_id")):
        return 0
    tree = tree_fingerprint(root)
    if tree and tree == (load_json(st / "green.json", {}) or {}).get("fast"):
        return 0
    blocks_file = st / "stop-blocks.json"
    blocks = (load_json(blocks_file, {}) or {}).get("count", 0)
    max_blocks = int((profile.get("gate") or {}).get("max_stop_blocks", 3))
    buf = io.StringIO()
    real_stdout, sys.stdout = sys.stdout, buf
    try:
        code = gate(root, "fast")
    finally:
        sys.stdout = real_stdout
    report = buf.getvalue()
    if code == 0:
        save_json(blocks_file, {"count": 0})
        return 0
    if code == 2:  # misconfigured profile: do not trap the session
        print(json.dumps({"systemMessage": "Ravend gate is armed but misconfigured:\n" + report[-1500:]}))
        return 0
    if blocks >= max_blocks:
        save_json(blocks_file, {"count": 0})
        print(json.dumps({"systemMessage": f"Ravend: quality gate still failing after {max_blocks} attempts — "
                                           "stopping so a human can decide. Last report:\n" + report[-2000:]}))
        return 0
    save_json(blocks_file, {"count": blocks + 1})
    print(json.dumps({"decision": "block", "reason":
                      f"Ravend quality gate (fast) FAILED — attempt {blocks + 1}/{max_blocks}. Fix the root cause "
                      "(do not weaken or skip tests), then finish again.\n\n" + report[-6000:]}))
    return 0


# --------------------------------------------------------------------------- main

HELP = """Ravend — comandos de terminal (rode dentro do repositório do projeto)

  ravend auto "<demanda>" [--pr]      pipeline sem supervisão, num worktree separado (ravend auto --help)
  ravend next [<slug>]                qual é o próximo passo de uma spec e por quê
  ravend status                       specs em andamento e último gate
  ravend doctor                       confere se está tudo configurado e diz o que falta
  ravend gate fast|full [--dry-run]   roda o quality gate desta pasta
  ravend mcp                          seus servidores MCP
  ravend integrations                 os MCPs escolhidos para cada papel

Registro de estado (usado pelas skills; raramente à mão):
  ravend spec approve|done|abandon <slug> [--pr <url>]
  ravend task done <slug> <T1>
  ravend verify record <slug> [--uncovered "AC2: ..."]...
  ravend review record <slug> [--file review.json]   (JSON do reviewer; sem --file lê da entrada padrão)

Uso interno: project, detect, app start|stop|status, arm, disarm, install-cli [--dir DIR], hook <evento>
"""


def _opt(rest: list[str], name: str) -> str | None:
    return rest[rest.index(name) + 1] if name in rest and rest.index(name) + 1 < len(rest) else None


def _flow_cli(cmd: str, rest: list[str], root: Path) -> int:
    d = data_dir(root)
    try:
        if cmd == "next":
            slug = next((a for a in rest if not a.startswith("-")), None)
            info = next_action(root, slug)
            if "--json" in rest:
                print(json.dumps(info, indent=2, ensure_ascii=False))
            else:
                print_next(info)
            return 0
        sub = rest[0] if rest else ""
        args = [a for a in rest[1:] if not a.startswith("-")]
        if cmd == "spec" and sub in ("approve", "done", "abandon") and args:
            status_value = {"approve": "approved", "done": "done", "abandon": "abandoned"}[sub]
            pr = _opt(rest, "--pr")
            set_spec_status(d, args[0], status_value, f"{status_value}" + (f" — PR {pr}" if pr else ""))
            if pr:
                path = spec_file(d, args[0])
                path.write_text(_set_frontmatter(path.read_text(encoding="utf-8"), "pr", pr), encoding="utf-8")
            print(f"[ravend] spec {args[0]}: {status_value}")
            return 0
        if cmd == "task" and sub == "done" and len(args) >= 2:
            print(f"[ravend] {args[0]}: {mark_task_done(d, args[0], args[1])} concluída")
            return 0
        if cmd == "verify" and sub == "record" and args:
            uncovered = [rest[i + 1] for i, a in enumerate(rest) if a == "--uncovered" and i + 1 < len(rest)]
            args = [a for a in args if a not in uncovered]
            entry = record_verify(root, args[0], uncovered)
            ok = _verify_ok(entry)
            print(f"[ravend] verificação registrada: gate {entry['gate']}"
                  + (f", {len(entry['uncovered'])} critério(s) sem teste" if entry["uncovered"] else "")
                  + (" — ok" if ok else ""))
            return 0
        if cmd == "review" and sub == "record" and args:
            source = _opt(rest, "--file")
            args = [a for a in args if a != source]
            if source:
                try:
                    Path(source).resolve().relative_to(root.resolve())
                    raise FlowError("o arquivo do review está dentro do repositório e muda o código que está sendo "
                                    "registrado; passe o JSON pela entrada padrão (heredoc) ou por um arquivo fora do repo")
                except ValueError:
                    pass
            raw_text = Path(source).read_text(encoding="utf-8") if source else sys.stdin.read()
            match = re.search(r"\{.*\}", raw_text, re.S)
            if not match:
                raise FlowError("nenhum JSON de review encontrado na entrada")
            entry = record_review(root, args[0], json.loads(match.group(0)))
            print(f"[ravend] review {entry['n']} registrado: {entry['verdict']}"
                  f" ({len(entry['blocking'])} P0/P1, {entry['p2']} P2) → "
                  f"{d / 'specs' / args[0] / ('review-%d.md' % entry['n'])}")
            return 0
    except FlowError as exc:
        print(f"[ravend] {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"[ravend] não foi possível registrar: {exc}", file=sys.stderr)
        return 2
    print(HELP)
    return 2


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(HELP)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "auto":
        runner = PLUGIN_ROOT / "scripts" / "ravend_auto.py"
        os.execv(sys.executable, [sys.executable, str(runner), *rest])
    if cmd == "hook":
        inp = _hook_input()
        handler = {"session-start": hook_session_start, "pre-edit": hook_pre_edit,
                   "post-edit": hook_post_edit, "stop": hook_stop}.get(rest[0] if rest else "")
        if not handler:
            return 0
        try:
            return handler(inp)
        except Exception as exc:  # a broken hook must never break the session
            print(f"[ravend] hook {rest[0]} error: {exc}", file=sys.stderr)
            return 0
    if cmd == "doctor":
        return print_doctor(doctor(repo_root(Path.cwd()), probe="--no-probe" not in rest))
    if cmd == "install-cli":
        target = Path(rest[rest.index("--dir") + 1]).expanduser() if "--dir" in rest else Path.home() / ".local" / "bin"
        return install_cli(target)
    root = repo_root(Path.cwd())
    if not root:
        print("[ravend] not inside a git repository", file=sys.stderr)
        return 2
    if cmd == "project":
        d = data_dir(root)
        ensure_dirs(d)
        print(json.dumps({"project_id": project_id(root), "root": str(root), "data_dir": str(d),
                          "has_profile": (d / "profile.json").exists(),
                          "base_branch": base_branch(root, load_profile(root)),
                          "plugin_root": str(PLUGIN_ROOT),
                          "integrations": integrations(load_profile(root))}, indent=2, ensure_ascii=False))
        return 0
    if cmd == "mcp":
        print(json.dumps(mcp_servers(root, probe="--no-probe" not in rest), indent=2, ensure_ascii=False))
        return 0
    if cmd == "integrations":
        stage = rest[rest.index("--stage") + 1] if "--stage" in rest else None
        print(json.dumps({"roles": {k: v[0] for k, v in ROLES.items()},
                          "chosen": integrations(load_profile(root), stage)}, indent=2, ensure_ascii=False))
        return 0
    if cmd == "detect":
        print(json.dumps(detect(root), indent=2))
        return 0
    if cmd == "gate":
        mode = next((a for a in rest if a in ("fast", "full")), "fast")
        scope = rest[rest.index("--scope") + 1] if "--scope" in rest else None
        return gate(root, mode, scope, "--dry-run" in rest)
    if cmd == "app":
        action = rest[0] if rest else "status"
        profile = load_profile(root) or {}
        if action == "start":
            ok, msg = app_start(root, profile)
            print(msg)
            return 0 if ok else 1
        if action == "stop":
            app_stop(root)
            print("stopped")
            return 0
        for app in _apps(profile):
            url = app.get("healthcheck")
            print(f"{app.get('name', 'app')}: {'UP' if url and _http_ok(url) else 'DOWN'} {url or ''}")
        return 0
    if cmd in ("arm", "disarm"):
        st = state_dir(root)
        try:
            if cmd == "arm":
                save_json(st / "armed.json", {"session": os.environ.get("RAVEND_SESSION_ID") or "*",
                                              "at": datetime.now().isoformat(timespec="seconds")})
                save_json(st / "stop-blocks.json", {"count": 0})
                print("[ravend] Stop-hook gate armed for this session")
            else:
                (st / "armed.json").unlink(missing_ok=True)
                print("[ravend] Stop-hook gate disarmed")
        except OSError as exc:
            print(f"[ravend] could not {cmd} the Stop-hook gate ({exc.strerror}: {st}). "
                  "Run the gate manually before finishing each task.", file=sys.stderr)
            return 1
        return 0
    if cmd == "status":
        return status(root, "--json" in rest)
    if cmd in ("next", "spec", "task", "verify", "review"):
        return _flow_cli(cmd, rest, root)
    print(HELP)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
