"""Control-loop tests for scripts/ravend_run.py with a scripted fake `claude` CLI (no API calls)."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ravend  # noqa: E402

RUNNER = Path(ravend.__file__).with_name("ravend_run.py")

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ["plugin", "list"]:
    print("ravend@ravend  0.1.0  enabled"); sys.exit(0)
prompt = args[args.index("-p") + 1]
script = json.loads(Path(os.environ["FAKE_SCRIPT"]).read_text())
log = Path(os.environ["FAKE_LOG"]); calls = json.loads(log.read_text()) if log.exists() else []
calls.append(prompt); log.write_text(json.dumps(calls))
if os.environ.get("FAKE_ARGS"):
    alog = Path(os.environ["FAKE_ARGS"]); allargs = json.loads(alog.read_text()) if alog.exists() else []
    cfg = args[args.index("--mcp-config") + 1] if "--mcp-config" in args else None
    allargs.append({"prompt": prompt, "args": args, "mcp": json.loads(Path(cfg).read_text()) if cfg else None})
    alog.write_text(json.dumps(allargs))
stage = prompt.split()[0].replace("/ravend:", "")
if stage == "build" and "--fix" in prompt:
    stage = "fix"
queue = script.get(stage, [])
n = sum(1 for c in calls if c.split()[0].replace("/ravend:", "") == prompt.split()[0].replace("/ravend:", "")
        and (("--fix" in c) == ("--fix" in prompt)))
out = queue[min(n, len(queue)) - 1] if queue else {}
if stage == "fix" and os.environ.get("FAKE_FIX_FILE"):
    Path(os.environ["FAKE_FIX_FILE"]).write_text("export const sum = (a, b) => a + b;\n")
print(json.dumps({"type": "result", "is_error": False, "total_cost_usd": 0.01, "structured_output": out}))
'''


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo, self.bin = base / "repo", base / "bin"
        self.bin.mkdir()
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        (self.repo / "src").mkdir(parents=True)
        (self.repo / "test").mkdir()
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a + b;\n")
        (self.repo / "test" / "sum.test.js").write_text(
            "import { test } from 'node:test'; import assert from 'node:assert/strict';\n"
            "import { sum } from '../src/sum.js';\ntest('sum', () => assert.equal(sum(2, 2), 4));\n")
        (self.repo / "package.json").write_text('{"type":"module"}')
        subprocess.run("git init -q -b main && git -c user.email=t@t -c user.name=t add -A && "
                       "git -c user.email=t@t -c user.name=t commit -qm init", cwd=self.repo, shell=True, check=True)
        self.env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                    "RAVEND_HOME": str(base / "home"), "FAKE_SCRIPT": str(base / "script.json"),
                    "FAKE_LOG": str(base / "calls.json")}
        os.environ["RAVEND_HOME"] = self.env["RAVEND_HOME"]
        ravend.save_json(ravend.data_dir(self.repo) / "profile.json", {
            "version": 1, "gate": {"fast": [{"name": "t", "run": "node --test"}],
                                   "full": [{"name": "t", "run": "node --test"}]}})

    def tearDown(self):
        os.environ.pop("RAVEND_HOME", None)
        self.tmp.cleanup()

    def run_pipeline(self, script, *args, **extra_env):
        Path(self.env["FAKE_SCRIPT"]).write_text(json.dumps(script))
        res = subprocess.run([sys.executable, str(RUNNER), *args], cwd=self.repo, capture_output=True, text=True,
                             env={**self.env, **extra_env})
        log = Path(self.env["FAKE_LOG"])
        calls = json.loads(log.read_text()) if log.exists() else []
        return res, [c.split()[0] + (" --fix" if "--fix" in c else "") for c in calls]

    SPEC_SMALL = {"spec": [{"slug": "s", "tier": "small", "blocking_questions": []}]}
    OK = {"build": [{"status": "done", "summary": "ok"}],
          "verify": [{"gate": "PASS", "uncovered_criteria": [], "summary": "ok"}],
          "review": [{"verdict": "APPROVED", "findings": []}]}

    def test_happy_path_small_until_review(self):
        res, calls = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "add thing")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(calls, ["/ravend:spec", "/ravend:build", "/ravend:verify", "/ravend:review"])

    def test_large_spec_pauses_for_approval(self):
        res, calls = self.run_pipeline({"spec": [{"slug": "big", "tier": "large", "blocking_questions": []}]}, "x")
        self.assertEqual(res.returncode, 0)
        self.assertIn("--resume big", res.stdout)
        self.assertEqual(calls, ["/ravend:spec"])

    def test_blocking_questions_need_a_human(self):
        res, _ = self.run_pipeline({"spec": [{"slug": "q", "tier": "small", "blocking_questions": ["auth?"]}]}, "x")
        self.assertEqual(res.returncode, 3)

    def test_review_fix_round_then_approved(self):
        script = {**self.SPEC_SMALL, **self.OK,
                  "review": [{"verdict": "CHANGES_REQUESTED", "findings": [{"severity": "P1", "file": "a", "title": "bug"}]},
                             {"verdict": "APPROVED", "findings": []}],
                  "fix": [{"status": "done", "summary": "fixed"}]}
        res, calls = self.run_pipeline(script, "x")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertEqual(calls[-3:], ["/ravend:review", "/ravend:build --fix", "/ravend:review"])

    def test_same_finding_twice_escalates(self):
        finding = {"verdict": "CHANGES_REQUESTED", "findings": [{"severity": "P0", "file": "a", "title": "bug"}]}
        script = {**self.SPEC_SMALL, **self.OK, "review": [finding, finding, finding],
                  "fix": [{"status": "done", "summary": "tried"}]}
        res, calls = self.run_pipeline(script, "x")
        self.assertEqual(res.returncode, 3)
        self.assertEqual(calls.count("/ravend:review"), 2)

    def test_runner_reruns_gate_and_does_not_trust_verify_claim(self):
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")  # red
        script = {**self.SPEC_SMALL, **self.OK, "fix": [{"status": "done", "summary": "fixed"}]}
        res, calls = self.run_pipeline(script, "x", FAKE_FIX_FILE=str(self.repo / "src" / "sum.js"))
        self.assertEqual(res.returncode, 0, res.stdout)
        # verify claimed PASS but the real gate was red -> one fix round, then verify again
        self.assertEqual(calls[2:5], ["/ravend:verify", "/ravend:build --fix", "/ravend:verify"])

    def test_missing_profile_exit_2(self):
        (ravend.data_dir(self.repo) / "profile.json").unlink()
        res, calls = self.run_pipeline(self.SPEC_SMALL, "x")
        self.assertEqual((res.returncode, calls), (2, []))


    def test_chosen_mcp_servers_are_allowed_only_in_their_stages(self):
        data = ravend.data_dir(self.repo)
        profile = json.loads((data / "profile.json").read_text())
        profile["integrations"] = {"issues": ["claude.ai Atlassian"], "browser": ["chrome-devtools"]}
        ravend.save_json(data / "profile.json", profile)
        args_log = Path(self.tmp.name) / "args.json"
        res, _ = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "x", FAKE_ARGS=str(args_log))
        self.assertEqual(res.returncode, 0, res.stdout)
        allowed = {c["prompt"].split()[0]: c["args"] for c in json.loads(args_log.read_text())}
        self.assertIn("mcp__claude_ai_Atlassian", allowed["/ravend:spec"])
        self.assertNotIn("mcp__chrome-devtools", allowed["/ravend:spec"])
        self.assertIn("mcp__chrome-devtools", allowed["/ravend:verify"])
        self.assertNotIn("mcp__playwright", allowed["/ravend:verify"])  # a browser MCP was chosen

    def test_second_run_in_same_checkout_is_refused(self):
        lock = ravend.state_dir(self.repo) / "run.lock"
        with ravend.file_lock(lock, blocking=False):
            res, calls = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "x")
        self.assertEqual(res.returncode, 2, res.stdout)
        self.assertIn("--worktree", res.stdout)
        self.assertEqual(calls, ["/ravend:spec"])

    def test_worktree_run_gets_local_mcp_servers_of_main_checkout(self):
        cfg = Path(self.tmp.name) / "cfg"
        ravend.save_json(cfg / ".claude.json", {"projects": {str(self.repo): {"mcpServers": {
            "pw": {"command": "npx", "args": ["@playwright/mcp@1"]}}}}})
        args_log = Path(self.tmp.name) / "args.json"
        res, _ = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "x", "--worktree", "--until", "build",
                                   FAKE_ARGS=str(args_log), CLAUDE_CONFIG_DIR=str(cfg))
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        calls = json.loads(args_log.read_text())
        self.assertIsNone(calls[0]["mcp"])  # spec runs in the main checkout
        self.assertEqual(calls[1]["mcp"], {"mcpServers": {"pw": {"command": "npx", "args": ["@playwright/mcp@1"]}}})
        path = calls[1]["args"][calls[1]["args"].index("--mcp-config") + 1]
        self.assertFalse(Path(path).exists())  # temp config removed at the end


if __name__ == "__main__":
    unittest.main()
