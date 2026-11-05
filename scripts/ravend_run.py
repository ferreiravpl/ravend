#!/usr/bin/env python3
"""Ravend headless pipeline: demand -> spec -> build -> verify -> review -> PR, unattended.

The control loop lives here (deterministic code); the model is only called inside each stage via
`claude -p` with a JSON schema. The quality gate is re-run by this script itself, so a stage can
never "claim" green.

Examples:
    ravend_run.py "Add pagination to GET /products"            # stops after spec if tier=large
    ravend_run.py PROJ-123 --yes --until review                 # no human checkpoint, no PR
    ravend_run.py --resume add-product-pagination --until pr    # continue after approving the spec
    ravend_run.py "..." --worktree --budget-usd 3 --permission-mode bypassPermissions  # in a sandbox

Exit codes: 0 done (or paused at a checkpoint), 1 failed, 2 misconfigured, 3 needs a human.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ravend  # noqa: E402

STAGES = ["spec", "build", "verify", "review", "pr"]
SPEC_SCHEMA = {
    "type": "object",
    "properties": {
        "slug": {"type": "string"}, "tier": {"enum": ["trivial", "small", "large", "bug"]},
        "spec_path": {"type": "string"}, "blocking_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["slug", "tier", "blocking_questions"],
}
BUILD_SCHEMA = {
    "type": "object",
    "properties": {"status": {"enum": ["done", "blocked"]}, "summary": {"type": "string"},
                   "blockers": {"type": "array", "items": {"type": "string"}}},
    "required": ["status", "summary"],
}
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {"gate": {"enum": ["PASS", "FAIL"]}, "uncovered_criteria": {"type": "array", "items": {"type": "string"}},
                   "summary": {"type": "string"}},
    "required": ["gate", "uncovered_criteria", "summary"],
}
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"enum": ["APPROVED", "CHANGES_REQUESTED"]}, "iteration": {"type": "integer"},
        "findings": {"type": "array", "items": {"type": "object", "properties": {
            "severity": {"enum": ["P0", "P1", "P2"]}, "file": {"type": "string"}, "line": {"type": ["integer", "null"]},
            "title": {"type": "string"}}, "required": ["severity", "file", "title"]}},
    },
    "required": ["verdict", "findings"],
}
SHIP_SCHEMA = {"type": "object", "properties": {"pr_url": {"type": "string"}}, "required": ["pr_url"]}


class Runner:
    def __init__(self, args: argparse.Namespace, root: Path):
        self.args, self.root, self.cwd = args, root, root
        self.profile = ravend.load_profile(root) or {}
        self.data = ravend.data_dir(root)
        self.log_dir = self.data / "runs" / f"headless-{datetime.now():%Y%m%d-%H%M%S}"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.cost = 0.0
        self.calls = 0
        self.plugin_dir = None if self._plugin_installed() else str(ravend.PLUGIN_ROOT)

    # ------------------------------------------------------------------ helpers
    def say(self, msg: str) -> None:
        print(f"[ravend-run] {msg}", flush=True)

    @staticmethod
    def _plugin_installed() -> bool:
        try:
            out = subprocess.run(["claude", "plugin", "list"], capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.TimeoutExpired):
            return False
        return re.search(r"\bravend@", out) is not None

    def allowed_tools(self, ship: bool = False) -> list[str]:
        tools = ["Read", "Edit", "Write", "MultiEdit", "Glob", "Grep", "Skill", "Agent", "TodoWrite",
                 "Bash(git *)", f"Bash(python3 {ravend.PLUGIN_ROOT}/scripts/ravend.py *)", "Bash(mkdir *)",
                 "mcp__playwright"]
        commands = [s.get("run", "") for mode in ("fast", "full") for s in (self.profile.get("gate") or {}).get(mode, [])]
        commands += [a.get("start", "") for a in ravend._apps(self.profile)]
        for cmd in commands:
            first = cmd.strip().split(" ")[0] if cmd.strip() else ""
            if first and not first.startswith("{"):
                tools.append(f"Bash({first} *)")
        tools += (self.profile.get("headless") or {}).get("allowed_tools", [])
        if ship:
            tools.append("Bash(gh *)")
        return list(dict.fromkeys(tools))

    def claude(self, stage: str, prompt: str, schema: dict, ship: bool = False) -> dict:
        cmd = ["claude", "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(schema),
               "--permission-mode", self.args.permission_mode, "--allowedTools", *self.allowed_tools(ship)]
        if self.args.budget_usd:
            cmd += ["--max-budget-usd", str(self.args.budget_usd)]
        if self.args.model:
            cmd += ["--model", self.args.model]
        if self.plugin_dir:
            cmd += ["--plugin-dir", self.plugin_dir]
        cmd += self.args.claude_arg or []
        self.calls += 1
        self.say(f"{stage}: claude -p {prompt!r}")
        proc = subprocess.run(cmd, cwd=self.cwd, capture_output=True, text=True,
                              env={**os.environ, "RAVEND_HEADLESS": "1"})
        raw_path = self.log_dir / f"{self.calls:02d}-{stage}.json"
        raw_path.write_text(proc.stdout or proc.stderr, encoding="utf-8")
        try:
            res = json.loads(proc.stdout)
        except ValueError:
            raise SystemExit(self.fail(f"{stage}: claude returned non-JSON (exit {proc.returncode}); see {raw_path}"))
        self.cost += float(res.get("total_cost_usd") or 0)
        if res.get("is_error"):
            raise SystemExit(self.fail(f"{stage}: {res.get('subtype') or 'error'} — {str(res.get('result'))[:500]}"))
        out = res.get("structured_output")
        if out is None:
            text = res.get("result") or ""
            match = re.search(r"\{.*\}", text, re.S)
            try:
                out = json.loads(match.group(0)) if match else None
            except ValueError:
                out = None
        if not isinstance(out, dict):
            raise SystemExit(self.fail(f"{stage}: no structured output; see {raw_path}"))
        return out

    def gate_full(self) -> bool:
        self.say("verify: running gate full (deterministic, outside the model)")
        code = subprocess.run([sys.executable, str(ravend.PLUGIN_ROOT / "scripts" / "ravend.py"), "gate", "full"],
                              cwd=self.cwd).returncode
        if code == 2:
            raise SystemExit(self.fail("gate is misconfigured (profile.json) — fix with /ravend:init"))
        return code == 0

    def fail(self, msg: str, code: int = 1) -> int:
        self.say(f"STOP: {msg}")
        self.summary()
        return code

    def summary(self) -> None:
        self.say(f"calls={self.calls} cost≈${self.cost:.2f} logs={self.log_dir}")

    def reached(self, stage: str) -> bool:
        """True when `stage` is the last one requested (--until), so the pipeline stops after it."""
        return STAGES.index(stage) >= STAGES.index(self.args.until)

    def worktree(self, slug: str) -> None:
        git_cfg = self.profile.get("git") or {}
        branch = f"{git_cfg.get('branch_prefix', 'feat/')}{slug}"
        path = self.root.parent / f"{self.root.name}-{slug}"
        if not path.exists():
            base = ravend.base_branch(self.root, self.profile)
            exists = ravend.git(["rev-parse", "--verify", "--quiet", branch], self.root) is not None
            args = ["worktree", "add", str(path), branch] if exists else ["worktree", "add", "-b", branch, str(path), base]
            if ravend.git(args, self.root) is None:
                raise SystemExit(self.fail(f"could not create worktree {path}", 2))
        self.cwd = path
        self.say(f"worktree: {path} (branch {branch})")

    # ------------------------------------------------------------------ pipeline
    def run(self) -> int:
        a = self.args
        if not self.profile:
            return self.fail("no local profile — run /ravend:init interactively once in this repo", 2)
        flags = " --headless" + (" --approved" if a.yes or a.resume else "")
        if a.resume:
            slug = a.resume
            spec = self.data / "specs" / slug / "spec.md"
            if not spec.exists():
                return self.fail(f"spec not found: {spec}", 2)
            tier = ravend._frontmatter(spec.read_text(encoding="utf-8")).get("tier", "large")
        else:
            out = self.claude("spec", f"/ravend:spec{flags} {a.demand}", SPEC_SCHEMA)
            slug, tier = out["slug"], out["tier"]
            self.say(f"spec: {slug} (tier {tier}) {out.get('spec_path', '')}")
            if out.get("blocking_questions"):
                for q in out["blocking_questions"]:
                    self.say(f"  ? {q}")
                return self.fail("spec has blocking questions — answer them in the spec, then --resume", 3)
            if a.until == "spec":
                self.summary()
                return 0
            if tier == "large" and not a.yes:
                self.say(f"checkpoint: review/approve the spec, then: ravend_run.py --resume {slug} --until {a.until}")
                self.summary()
                return 0
        if a.worktree:
            self.worktree(slug)

        build = self.claude("build", f"/ravend:build {slug}{flags}", BUILD_SCHEMA)
        if build["status"] == "blocked":
            for b in build.get("blockers", []):
                self.say(f"  ! {b}")
            return self.fail("build blocked", 3)
        if self.reached("build"):
            self.summary()
            return 0

        for attempt in range(a.max_fix_rounds + 1):
            ver = self.claude("verify", f"/ravend:verify {slug}{flags}", VERIFY_SCHEMA)
            green = self.gate_full()
            if green and not ver.get("uncovered_criteria"):
                break
            if attempt == a.max_fix_rounds:
                return self.fail(f"verify still failing after {a.max_fix_rounds} fix rounds: {ver.get('summary')}", 3)
            self.claude("fix-verify", f"/ravend:build {slug} --fix verify{flags}", BUILD_SCHEMA)
        if self.reached("verify"):
            self.summary()
            return 0

        previous: set | None = None
        for attempt in range(a.max_fix_rounds + 1):
            rev = self.claude("review", f"/ravend:review {slug}{flags}", REVIEW_SCHEMA)
            blocking = {(f["file"], f["title"]) for f in rev["findings"] if f["severity"] in ("P0", "P1")}
            self.say(f"review: {rev['verdict']} · {len(blocking)} blocking finding(s)")
            if rev["verdict"] == "APPROVED" and not blocking:
                break
            if attempt == a.max_fix_rounds or blocking == previous:
                return self.fail("review did not converge — a human needs to look at the findings", 3)
            previous = blocking
            self.claude("fix-review", f"/ravend:build {slug} --fix review{flags}", BUILD_SCHEMA)
            if not self.gate_full():
                return self.fail("gate broke while fixing review findings", 3)
        if self.reached("review"):
            self.summary()
            return 0

        ship = self.claude("ship", f"/ravend:ship {slug}{flags} --yes", SHIP_SCHEMA, ship=True)
        self.say(f"PR: {ship['pr_url']}")
        self.summary()
        return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("demand", nargs="?", help="free text, Jira key (PROJ-123) or GitHub issue (#45 / URL)")
    p.add_argument("--resume", metavar="SLUG", help="continue an existing spec (treated as approved)")
    p.add_argument("--until", choices=STAGES, default="review", help="last stage to run (default: review)")
    p.add_argument("--yes", action="store_true", help="skip the spec-approval checkpoint")
    p.add_argument("--max-fix-rounds", type=int, default=2)
    p.add_argument("--budget-usd", type=float, help="max spend per claude call (--max-budget-usd)")
    p.add_argument("--model", help="model for every stage (default: your Claude Code default)")
    p.add_argument("--permission-mode", default="acceptEdits",
                   help="claude permission mode (acceptEdits | bypassPermissions in a sandbox | ...)")
    p.add_argument("--worktree", action="store_true", help="work in a sibling git worktree on the feature branch")
    p.add_argument("--claude-arg", action="append", help="extra raw argument for claude (repeatable)")
    args = p.parse_args()
    if not args.demand and not args.resume:
        p.error("give a demand or --resume SLUG")
    if not shutil.which("claude"):
        print("claude CLI not found on PATH", file=sys.stderr)
        return 2
    root = ravend.repo_root(Path.cwd())
    if not root:
        print("run inside a git repository", file=sys.stderr)
        return 2
    return Runner(args, root).run()


if __name__ == "__main__":
    sys.exit(main())
