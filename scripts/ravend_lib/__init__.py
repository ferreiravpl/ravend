"""Ravend runtime, split by responsibility. `scripts/ravend.py` is the command-line entry point.

    core         project identity, local data dirs, JSON/profile I/O, git, locks, tree fingerprint
    gating       quality gate and the app lifecycle for steps that need the app running
    mcp          the developer's MCP servers, role catalog, per-stage permissions
    detection    stack/tooling detection for /ravend:init
    flow         specs, the `next` state machine and the state records
    diagnostics  `ravend doctor`
    hooks        Claude Code hooks (session start, protected paths, formatting, Stop-hook gate)
    cli          argparse definitions and dispatch

Importing the package gives one flat namespace (every top-level name of every module) for
ravend_auto.py and the tests, so callers do not need to know which module holds what.
"""
from . import cli, core, detection, diagnostics, flow, gating, hooks, mcp

for _module in (core, gating, mcp, detection, flow, diagnostics, hooks, cli):
    for _name, _value in vars(_module).items():
        if not _name.startswith("__"):
            globals().setdefault(_name, _value)
del _module, _name, _value
