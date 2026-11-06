#!/usr/bin/env python3
"""Ravend runtime — entry point for hooks, skills and the `ravend` terminal command.

Standard library only (Python 3.8+). The code lives in the `ravend_lib` package next to this file
(see its __init__ for the module map). Everything Ravend learns or produces about a project lives
outside the repository, under $RAVEND_HOME (default ~/.ravend)/projects/<project-id>/:

    profile.json        commands the gate runs, formatters, app, protected paths, MCP integrations
    project.md          short notes about the project's conventions
    knowledge/          lessons (index.md + one file per lesson)
    specs/<slug>/       spec.md, verify.md, review-N.md, state.json (verify/review records)
    runs/               gate, app and `ravend auto` logs
    state/<checkout>/   gate state per clone/worktree

`python3 ravend.py --help` lists the commands.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ravend_lib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
