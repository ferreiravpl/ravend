"""After the PR: read its CI checks (GitHub, through `gh`), keep only the failing part of the logs and record
the result in the spec's state.json (`ci[]`), which `next` reads to decide between waiting, fixing and merge."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .core import _frontmatter, _read, _slug, data_dir, git, load_profile
from .flow import FlowError, _require_spec, _save_spec_state, set_spec_status, spec_state
from .gating import failure_excerpt

DEFAULT_WAIT_MINUTES = 30
PASS_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
RUN_RE = re.compile(r"/actions/runs/(\d+)")


def _gh(args: list[str], root: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        proc = subprocess.run(["gh", *args], cwd=root, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return proc.returncode, proc.stdout if proc.returncode == 0 else (proc.stderr or proc.stdout)


def classify(rollup: list[dict]) -> tuple[str, list[dict]]:
    """('pass'|'fail'|'pending', failing checks) from `gh pr view --json statusCheckRollup`."""
    failed, pending = [], False
    for item in rollup or []:
        name = item.get("name") or item.get("context") or "check"
        url = item.get("detailsUrl") or item.get("targetUrl") or ""
        if item.get("__typename") == "StatusContext" or "context" in item:
            state = (item.get("state") or "").upper()
            if state in ("PENDING", "EXPECTED", ""):
                pending = True
            elif state != "SUCCESS":
                failed.append({"name": name, "url": url})
            continue
        if (item.get("status") or "").upper() != "COMPLETED":
            pending = True
        elif (item.get("conclusion") or "").upper() not in PASS_CONCLUSIONS:
            failed.append({"name": name, "url": url, "workflow": item.get("workflowName") or ""})
    return ("fail" if failed else "pending" if pending else "pass"), failed


def _failed_logs(root: Path, failed: list[dict], tail: int) -> list[str]:
    """`gh run view <id> --log-failed` once per failing workflow run, saved under runs/ci-*/ with an excerpt."""
    run_dir = data_dir(root) / "runs" / f"ci-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    paths, seen = [], set()
    for check in failed:
        m = RUN_RE.search(check.get("url", ""))
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        code, out = _gh(["run", "view", m.group(1), "--log-failed"], root, timeout=300)
        if code != 0 or not out.strip():
            continue
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            log = run_dir / f"{_slug(check['name']) or 'check'}.log"
            log.write_text(f"# {check['name']} — {check.get('url', '')}\n\n## excerpt\n"
                           f"{failure_excerpt(out, tail)}\n\n## full failed log\n{out}", encoding="utf-8")
            paths.append(str(log))
        except OSError:
            pass
    return paths


def record_ci(root: Path, slug: str, state: str, head: str | None, failed: list[str], logs: list[str],
              pr_state: str = "OPEN") -> dict:
    d = data_dir(root)
    _require_spec(d, slug)
    entry = {"head": head, "state": state, "failed": failed, "logs": logs, "pr_state": pr_state,
             "at": datetime.now().isoformat(timespec="seconds")}
    st = spec_state(d, slug)
    if st["ci"] and st["ci"][-1].get("head") == head:
        st["ci"][-1] = entry  # same commit checked again (pending → final): one record per commit
    else:
        st["ci"].append(entry)
    _save_spec_state(d, slug, st)
    if pr_state == "MERGED":
        set_spec_status(d, slug, "done", "PR mergeado")
    return entry


def ci_check(root: Path, slug: str, wait_minutes: float | None = None) -> dict:
    """Read the PR's checks (optionally waiting until none is pending) and record them."""
    d = data_dir(root)
    fm = _frontmatter(_read(_require_spec(d, slug)))
    pr = fm.get("pr")
    if not pr:
        raise FlowError(f"a spec {slug} não tem PR registrado (o /ravend:ship registra com `spec shipped`)")
    if not shutil.which("gh"):
        raise FlowError("o `gh` não está instalado: confira o CI pelo seu MCP de git e registre com "
                        f"`ravend ci {slug} --state pass|fail|pending [--failed \"<check>: <motivo>\"]`")
    profile = load_profile(root) or {}
    tail = int((profile.get("gate") or {}).get("tail_lines", 60))
    interval = float(os.environ.get("RAVEND_CI_INTERVAL", "30"))
    deadline = time.time() + 60 * (wait_minutes or 0)
    while True:
        code, out = _gh(["pr", "view", pr, "--json", "state,headRefOid,statusCheckRollup,url"], root)
        if code != 0:
            raise FlowError(f"não foi possível ler o PR {pr}: {out.strip()[:300]}")
        data = json.loads(out)
        state, failed = classify(data.get("statusCheckRollup") or [])
        if state != "pending" or data.get("state") != "OPEN" or time.time() >= deadline:
            break
        time.sleep(interval)
    logs = _failed_logs(root, failed, tail) if state == "fail" else []
    return record_ci(root, slug, state, data.get("headRefOid") or git(["rev-parse", "HEAD"], root),
                     [f"{f['name']}: {f['url']}" if f.get("url") else f["name"] for f in failed], logs,
                     data.get("state") or "OPEN")


def print_ci(entry: dict) -> None:
    label = {"pass": "verde", "fail": "VERMELHO", "pending": "ainda rodando"}.get(entry["state"], entry["state"])
    print(f"[ravend] CI {label} · commit {str(entry.get('head'))[:10]} · PR {entry.get('pr_state', '?')}")
    for f in entry.get("failed", []):
        print(f"  ✗ {f}")
    for log in entry.get("logs", []):
        print(f"  log: {log}")
