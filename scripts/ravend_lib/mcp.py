"""The developer's MCP servers: discovery (config files + `claude mcp list`, never secrets), the role
catalog and the per-stage tool permissions derived from profile.integrations."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

from .core import load_json

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
