"""Claude Code hooks: session context, protected paths, formatting and the Stop-hook gate.
Every hook is a no-op in repositories without a local profile and never raises."""
from __future__ import annotations

import fnmatch
import io
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from .core import DEFAULT_PROTECTED, PLUGIN_ROOT, _read, data_dir, load_json, load_profile, project_id, repo_root, save_json, state_dir, tree_fingerprint
from .gating import _matches, _relative_to_cwd, gate
from .mcp import integrations
from .flow import specs_status

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
