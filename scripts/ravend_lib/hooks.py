"""Claude Code hooks: session context, protected paths, formatting and the Stop-hook gate.
Every hook is a no-op in repositories without a local profile and never raises."""
from __future__ import annotations

import fnmatch
import io
import json
import os
import re
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
    related = related_repos(root, profile)
    if related:
        out.append("related repositories (read-only here: read their code/contracts, never edit them): " + " · ".join(
            f"{r['name']}={r['abs']}{'' if r['exists'] else ' (missing)'}" + (f" ({r['use']})" if r.get("use") else "")
            for r in related))
    risk = [a.get("name", "?") for a in profile.get("risk") or [] if isinstance(a, dict)]
    if risk:
        out.append(f"risk areas (need approval + review lenses, see `next`): {', '.join(risk)}")
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
    p = _abs_tool_path(inp)
    if not p:
        return None
    try:
        return str(p.relative_to(root.resolve()))
    except ValueError:
        return None


def _abs_tool_path(inp: dict) -> Path | None:
    ti = inp.get("tool_input") or {}
    p = ti.get("file_path") or ti.get("notebook_path") or ti.get("path")
    return Path(p).resolve() if p else None


def _deny(reason: str) -> int:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    return 0


def related_repos(root: Path, profile: dict) -> list[dict]:
    """profile.related_repos: [{"name": ..., "path": "../other-repo", "use": "..."}] — read-only references
    (shared libraries, contracts) that live in their own repositories. Paths relative to the repo root."""
    out = []
    for item in profile.get("related_repos") or []:
        item = {"path": item} if isinstance(item, str) else dict(item)
        if not item.get("path"):
            continue
        path = (root / Path(item["path"]).expanduser()).resolve()
        out.append({**item, "name": item.get("name") or path.name, "abs": str(path), "exists": path.is_dir()})
    return out


def _agent(inp: dict) -> str:
    """Plugin agents cannot carry their own hooks, so the plugin's hooks check which agent made the call."""
    name = str(inp.get("agent_type") or "")
    return name.split(":", 1)[1] if name.startswith("ravend:") else name


TEST_PATHS = ["src/test/*", "*/src/test/*", "src/testFixtures/*", "*/src/testFixtures/*", "test/*", "*/test/*",
              "tests/*", "*/tests/*", "e2e/*", "*/e2e/*", "*__tests__*", "*.spec.*", "*.test.*", "*Test.java",
              "*Tests.java", "*IT.java", "*Test.kt", "*IT.kt", "*_test.go", "test_*.py", "*.tftest.hcl",
              "playwright.config.*", "*/testdata/*", "*/fixtures/*"]


def _is_test_path(rel: str, profile: dict) -> bool:
    patterns = TEST_PATHS + list(profile.get("test_paths") or [])
    name = Path(rel).name
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in patterns)


def hook_pre_edit(inp: dict) -> int:
    root = _hook_root(inp)
    profile = load_profile(root) if root else None
    if not profile:
        return 0
    target = _abs_tool_path(inp)
    if target is None:
        return 0
    for repo in related_repos(root, profile):
        if target == Path(repo["abs"]) or Path(repo["abs"]) in target.parents:
            return _deny(f"Ravend: `{repo['name']}` ({repo['abs']}) is a related repository, read-only from here. "
                         "A change there needs its own spec and PR in that repository; record the dependency in "
                         "this spec (Open questions / Out of scope).")
    rel = _tool_path(inp, root)
    if rel is None:
        return 0
    agent = _agent(inp)
    if agent == "reviewer":
        return _deny("Ravend: the reviewer never edits files. Report the problem as a finding instead.")
    if agent == "verifier" and not _is_test_path(rel, profile):
        return _deny(f"Ravend: the verifier only writes tests, fixtures and test config; `{rel}` is not a test path "
                     "(profile.test_paths extends the list). A real bug stays as a failing test in the report.")
    patterns = profile.get("protected_paths", DEFAULT_PROTECTED)
    name = Path(rel).name
    hit = next((p for p in patterns if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p)), None)
    if hit:
        return _deny(f"Ravend: `{rel}` matches protected path `{hit}` (profile.protected_paths). "
                     "Ask the developer to change it manually.")
    return 0


# --------------------------------------------------------------------------- command guard
# Real infrastructure, deploys, merges and secrets change only through PR + CI + a human. These patterns are
# a guard against accidents (an agent "fixing" prod), not a sandbox: shells can always be convinced otherwise.

_FLAGS = r"(?:\s+--?[\w.=:/-]+(?:\s+(?!-)[^\s;&|]+)?)*"
INFRA_DENY = [
    (re.compile(r"\b(?:terraform|tofu|terragrunt)\b" + _FLAGS + r"\s+(?:run-all\s+|run\s+--all\s+)?"
                r"(apply|destroy|import|taint|untaint|force-unlock|state\s+(?:rm|mv|push|replace-provider)"
                r"|workspace\s+(?:delete|new))\b"), "changes real infrastructure/state; run `plan` and let CI apply"),
    (re.compile(r"\bhelm\b" + _FLAGS + r"\s+(install|upgrade|uninstall|delete|rollback)\b"), "deploys to a cluster"),
    (re.compile(r"\bkubectl\b" + _FLAGS + r"\s+(apply|create|delete|patch|replace|scale|edit|drain|cordon|uncordon"
                r"|taint|annotate|label|set|expose|autoscale|rollout\s+(?:restart|undo|resume|pause))\b"),
     "changes a live cluster"),
    (re.compile(r"\baws\b" + _FLAGS + r"\s+s3\s+(rm|mv|rb|mb|sync)\b"), "writes to S3"),
    (re.compile(r"\baws\b" + _FLAGS + r"\s+s3\s+cp\s+\S+\s+s3://"), "writes to S3"),
    (re.compile(r"\baws\b" + _FLAGS + r"\s+[a-z0-9-]+\s+((?:create|delete|put|update|terminate|modify|attach|detach"
                r"|associate|disassociate|run|start|stop|reboot|restore|import|deregister|register|tag|untag|invoke"
                r"|publish|send|purge|set|enable|disable|revoke|authorize|cancel|copy|reset|rotate|upload|replace"
                r"|accept|reject|batch-write|batch-delete|change|execute|admin)[a-z0-9-]*)\b"), "changes an AWS account"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "merges a PR — the merge is the developer's"),
    (re.compile(r"\bgh\s+(?:secret|variable)\s+(set|delete|remove)\b"), "changes repository/org secrets"),
    (re.compile(r"\bgh\s+(?:workflow\s+(?:run|enable|disable)|release\s+(?:create|delete|edit|upload)"
                r"|repo\s+(?:delete|edit|archive|rename))\b"), "changes the GitHub repository/org"),
    (re.compile(r"\bdocker\s+push\b"), "publishes an image — CI publishes"),
]
CLI_START = re.compile(r"^\s*(?:aws|terraform|tofu|terragrunt|helm|kubectl|gh|docker)\b")
AWS_READ_EXCEPTIONS = {"update-kubeconfig", "start-query", "stop-query", "get-login-password"}
MCP_DENY_TOOLS = re.compile(r"merge_pull_request|delete_repository|create_or_update_secret")

REVIEWER_WRITES = re.compile(
    r"(?:^|[;&|(]\s*|\$\(\s*)(?:rm|mv|cp|mkdir|touch|chmod|chown|tee|truncate|dd|ln|install|patch|npm\s+(?:i|install|ci|update)"
    r"|pnpm\s+(?:i|install|add)|yarn\s+add|pip3?\s+install)\b"
    r"|\bsed\s+(?:-\w*\s+)*-i|\bperl\s+-\w*i"
    r"|\bgit\s+(?:add|commit|push|reset|checkout|switch|restore|stash|rebase|merge|cherry-pick|revert|apply|am|clean"
    r"|rm|mv|tag|worktree|config|pull|branch\s+-[dDmM])\b")
REDIRECT = re.compile(r"(?<![0-9&>])>>?(?!\s*&)(?!\s*/dev/null)")


QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
SHELL_STRING = re.compile(r"\b(?:bash|sh|zsh|eval)\b(?:\s+-\w+)*\s+['\"]")


def _code_part(command: str) -> str:
    """The command without quoted text and heredoc bodies (commit messages, PR bodies), except when a quoted
    string is itself run as a command (`bash -c "..."`, `eval '...'`)."""
    first, _, rest = command.partition("\n")
    if "<<" in first:
        command = first
    else:
        command = first + ("\n" + rest if rest else "")
    return command if SHELL_STRING.search(command) else QUOTED.sub("''", command)


def command_denial(command: str, agent: str = "", extra: list[str] | None = None) -> str | None:
    """Why a shell command must not run here, or None."""
    command = _code_part(command)
    for rx, why in INFRA_DENY:
        m = rx.search(command)
        if m and not (m.groups() and m.group(m.lastindex or 1) in AWS_READ_EXCEPTIONS):
            return f"`{m.group(0).strip()}` {why}"
    for pattern in extra or []:
        try:
            if re.search(pattern, command):
                return f"matches profile.guard.deny `{pattern}`"
        except re.error:
            continue
    if agent == "reviewer":
        unquoted = QUOTED.sub("''", command)
        if REVIEWER_WRITES.search(unquoted) or REDIRECT.search(unquoted):
            return "the reviewer is read-only (git diff/log/show, grep, running an existing test)"
    return None


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def hook_pre_command(inp: dict) -> int:
    if os.environ.get("RAVEND_GUARD") == "off":
        return 0
    root = _hook_root(inp)
    profile = load_profile(root) if root else None
    if not profile:
        return 0
    tool = str(inp.get("tool_name") or "")
    ti = inp.get("tool_input") or {}
    extra = list((profile.get("guard") or {}).get("deny") or [])
    if tool == "Bash":
        texts, agent = [str(ti.get("command") or "")], _agent(inp)
    else:
        if MCP_DENY_TOOLS.search(tool):
            return _deny(f"Ravend: `{tool}` is the developer's call (merge, secrets, repository deletion).")
        # only arguments that are themselves CLI commands (e.g. an AWS MCP's `cli_command`), never free text
        # such as a PR body that mentions `terraform apply`
        texts, agent = [t for t in _strings(ti) if CLI_START.match(t)], ""
    for text in texts:
        why = command_denial(text, agent, extra)
        if why and why.startswith("the reviewer"):
            return _deny(f"Ravend: {why}. Report what you would change as a finding instead.")
        if why:
            return _deny(f"Ravend guard: {why}. Ravend never changes real infrastructure, deploys, merges or "
                         "secrets; the change goes through the PR and CI. Ask the developer to run it if needed "
                         "(RAVEND_GUARD=off disables this check for a session).")
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
