"""Quality gate (resolve and run the profile's steps, summarize failures, record the result per checkout)
and the app lifecycle for steps that need the application running."""
from __future__ import annotations

import fnmatch
import os
import re
import shlex
import signal
import subprocess
import time
import urllib.request
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from .core import _slug, base_branch, changed_files, data_dir, file_lock, load_json, load_profile, save_json, state_dir, tree_fingerprint

ERROR_RE = re.compile(
    r"(error|fail|failed|failure|exception|assert|expected|✗|×|\[ERROR\]|BUILD FAILURE|Tests run:.*Failures: [1-9])",
    re.IGNORECASE,
)


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


def _alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def app_owner(root: Path) -> str | None:
    """Another checkout of this project whose app processes are still alive (the ports are shared)."""
    mine = state_dir(root)
    for other in (data_dir(root) / "state").glob("*/app.json"):
        if other.parent != mine and any(_alive(pid) for pid in (load_json(other, {}) or {}).values()):
            return other.parent.name
    return None


def app_start(root: Path, profile: dict) -> tuple[bool, str]:
    apps = _apps(profile)
    if not apps:
        return False, "profile.app is not configured"
    d, st = data_dir(root), state_dir(root)
    busy = app_owner(root)
    if busy:
        return False, f"the app is already running from another checkout ({busy}); stop it there with `ravend app stop`"
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
