#!/usr/bin/env python3
"""Ravend runtime — project identity, per-developer local data, quality gate, app lifecycle and hooks.

Standard library only (Python 3.8+). Everything Ravend learns or produces about a project lives
outside the repository, under $RAVEND_HOME (default ~/.ravend)/projects/<project-id>/:

    profile.json   commands the gate runs (written by /ravend:init)
    project.md     short, human-editable notes about the project's conventions
    knowledge/     lessons learned (index.md + one file per lesson)
    specs/<slug>/  spec.md, review-N.md, verify.md, evidence/
    runs/          gate and app logs
    state/         gate state (armed session, last green tree, block counter)

Usage:
    ravend.py project                    print project identity/paths as JSON
    ravend.py detect                     print detected stacks/tooling as JSON
    ravend.py gate [fast|full] [--dry-run] [--scope worktree|branch]
    ravend.py app start|stop|status
    ravend.py arm | disarm               enable/disable the Stop-hook gate for this session
    ravend.py status [--json]            active specs + last gate result
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
import urllib.request
from datetime import datetime
from pathlib import Path

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
    d = data_dir(root)
    run_dir = d / "runs" / f"gate-{mode}-{datetime.now():%Y%m%d-%H%M%S}"
    results, app_started = [], False
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
    if dry_run:
        return 0
    failed = [r for r in results if r["status"] in ("FAIL", "TIMEOUT")]
    ran = [r for r in results if r["status"] != "SKIP"]
    status = "FAIL" if failed else ("PASS" if ran else "EMPTY")
    state = {"mode": mode, "status": status, "at": datetime.now().isoformat(timespec="seconds"),
             "fingerprint": tree_fingerprint(root), "steps": results}
    try:
        save_json(d / "state" / f"last-gate-{mode}.json", state)
        if status == "PASS":
            green = load_json(d / "state" / "green.json", {}) or {}
            green[mode] = state["fingerprint"]
            save_json(d / "state" / "green.json", green)
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
    d = data_dir(root)
    pids = load_json(d / "state" / "app.json", {}) or {}
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
        save_json(d / "state" / "app.json", pids)
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
    d = data_dir(root)
    for pid in (load_json(d / "state" / "app.json", {}) or {}).values():
        _kill_group(int(pid))
    save_json(d / "state" / "app.json", {})


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
            "last_gate": {m: load_json(d / "state" / f"last-gate-{m}.json") for m in ("fast", "full")},
            "tree": tree_fingerprint(root), "green": load_json(d / "state" / "green.json", {}),
            "armed": load_json(d / "state" / "armed.json")}
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    print(f"project {data['project_id']} · data {d} · profile {'yes' if data['has_profile'] else 'NO'}")
    for s in data["specs"][:10]:
        print(f"  spec {s['slug']} [{s['status']}/{s['tier']}] {s['done']}/{s['total']} next: {s['next'] or '-'}")
    for m, g in data["last_gate"].items():
        if g:
            fresh = "current" if g.get("fingerprint") == data["tree"] else "stale"
            print(f"  last gate {m}: {g['status']} at {g['at']} ({fresh})")
    return 0


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
            print("[ravend] This repo has no local Ravend profile. Pipeline commands need /ravend:init first.")
        return 0
    out = [f"[ravend] project `{project_id(root)}` — local data dir (never committed): {d}",
           f"stacks: {', '.join(profile.get('stacks', [])) or '?'} · gate: `{cli} gate fast|full` · status: `{cli} status`"]
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
        out.append(f"active spec `{s['slug']}` [{s['status']}] {s['done']}/{s['total']} tasks · next: {s['next'] or '-'}"
                   f" · {s['path']}")
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
    d = data_dir(root)
    armed = load_json(d / "state" / "armed.json")
    if not armed or armed.get("session") not in ("*", inp.get("session_id")):
        return 0
    tree = tree_fingerprint(root)
    if tree and tree == (load_json(d / "state" / "green.json", {}) or {}).get("fast"):
        return 0
    blocks_file = d / "state" / "stop-blocks.json"
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

def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
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
                          "plugin_root": str(PLUGIN_ROOT)}, indent=2))
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
        d = data_dir(root)
        try:
            if cmd == "arm":
                save_json(d / "state" / "armed.json", {"session": os.environ.get("RAVEND_SESSION_ID") or "*",
                                                       "at": datetime.now().isoformat(timespec="seconds")})
                save_json(d / "state" / "stop-blocks.json", {"count": 0})
                print("[ravend] Stop-hook gate armed for this session")
            else:
                (d / "state" / "armed.json").unlink(missing_ok=True)
                print("[ravend] Stop-hook gate disarmed")
        except OSError as exc:
            print(f"[ravend] could not {cmd} the Stop-hook gate ({exc.strerror}: {d / 'state'}). "
                  "Run the gate manually before finishing each task.", file=sys.stderr)
            return 1
        return 0
    if cmd == "status":
        return status(root, "--json" in rest)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
