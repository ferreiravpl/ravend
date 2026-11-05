"""Control-loop tests for scripts/ravend_auto.py with a scripted fake `claude` CLI (no API calls).

The fake plays the skills' side effects through the real runtime: the spec stage writes a spec, build ticks
tasks with `ravend.py task done`, a fix edits code. Verify and review only answer JSON; the runner records them.
"""
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

RUNNER = Path(ravend.__file__).with_name("ravend_auto.py")

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ["plugin", "list"]:
    print("ravend@ravend  0.3.0  enabled"); sys.exit(0)
prompt = args[args.index("-p") + 1]
rv = [sys.executable, os.environ["FAKE_RAVEND"]]
script = json.loads(Path(os.environ["FAKE_SCRIPT"]).read_text())
words = prompt.split()
stage = words[0].replace("/ravend:", "")
slug = words[1] if len(words) > 1 and not words[1].startswith("-") else None
if stage == "build" and slug:
    nxt = json.loads(subprocess.run(rv + ["next", slug, "--json"], capture_output=True, text=True).stdout or "{}")
    if nxt.get("action") == "fix":
        stage = "fix"
log = Path(os.environ["FAKE_LOG"]); calls = json.loads(log.read_text()) if log.exists() else []
calls.append({"stage": stage, "prompt": prompt, "args": args,
              "mcp": json.loads(Path(args[args.index("--mcp-config") + 1]).read_text()) if "--mcp-config" in args else None})
log.write_text(json.dumps(calls))
n = sum(1 for c in calls if c["stage"] == stage)
queue = script.get(stage, [])
out = queue[min(n, len(queue)) - 1] if queue else {}
if stage == "spec" and out.get("tier") not in (None, "trivial"):
    data = Path(json.loads(subprocess.run(rv + ["project"], capture_output=True, text=True).stdout)["data_dir"])
    status = "draft" if out["tier"] == "large" else "approved"
    spec = data / "specs" / out["slug"] / "spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(f"---\nslug: {out['slug']}\ntitle: T\ntier: {out['tier']}\nstatus: {status}\nbranch: feat/{out['slug']}\n---\n"
                    "# T\n\n## Acceptance criteria\n- AC1 [unit]: x\n\n## Tasks\n"
                    "- [ ] T1: first — files: src/sum.js — proves: AC1 — deps: none\n"
                    "- [ ] T2: second — files: src/sum.js — proves: AC1 — deps: T1\n\n## Log\n")
if stage == "build" and slug:
    for task in ("T1", "T2"):
        subprocess.run(rv + ["task", "done", slug, task], capture_output=True)
if stage == "fix":
    touch = Path(os.getcwd()) / "src" / "fixes.js"
    touch.write_text(touch.read_text() + "// fix\n" if touch.exists() else "// fix\n")
    if os.environ.get("FAKE_FIX_FILE"):
        Path(os.getcwd(), os.environ["FAKE_FIX_FILE"]).write_text("export const sum = (a, b) => a + b;\n")
print(json.dumps({"type": "result", "is_error": False, "total_cost_usd": 0.01, "structured_output": out}))
'''


class RunnerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
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
                    "FAKE_LOG": str(base / "calls.json"), "FAKE_RAVEND": str(Path(ravend.__file__)),
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@t"}
        os.environ["RAVEND_HOME"] = self.env["RAVEND_HOME"]
        self.data = ravend.data_dir(self.repo)
        ravend.save_json(self.data / "profile.json", {
            "version": 1, "gate": {"fast": [{"name": "t", "run": "node --test"}],
                                   "full": [{"name": "t", "run": "node --test"}]}})

    def tearDown(self):
        os.environ.pop("RAVEND_HOME", None)
        self.tmp.cleanup()

    def worktree(self, slug="s"):
        return self.repo.parent / f"repo-{slug}"

    def run_pipeline(self, script, *args, **extra_env):
        Path(self.env["FAKE_SCRIPT"]).write_text(json.dumps(script))
        res = subprocess.run([sys.executable, str(RUNNER), *args], cwd=self.repo, capture_output=True, text=True,
                             env={**self.env, **extra_env})
        log = Path(self.env["FAKE_LOG"])
        self.calls = json.loads(log.read_text()) if log.exists() else []
        return res, [c["stage"] for c in self.calls]

    SPEC_SMALL = {"spec": [{"slug": "s", "tier": "small", "blocking_questions": []}]}
    OK = {"build": [{"status": "done", "summary": "ok"}],
          "fix": [{"status": "done", "summary": "fixed"}],
          "verify": [{"gate": "PASS", "uncovered_criteria": [], "summary": "ok"}],
          "review": [{"verdict": "APPROVED", "findings": []}],
          "ship": [{"pr_url": "https://example.com/pr/1"}]}
    P1 = {"verdict": "CHANGES_REQUESTED", "findings": [{"severity": "P1", "file": "src/sum.js", "title": "bug"}]}

    def test_happy_path_stops_ready_for_pr_in_a_worktree(self):
        res, calls = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "add thing")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(calls, ["spec", "build", "verify", "review"])
        self.assertIn("pronto para PR", res.stdout)
        self.assertTrue(self.worktree().exists())
        self.assertEqual(ravend.next_action(self.worktree(), "s")["action"], "ship")

    def test_pr_flag_ships_and_closes_the_spec(self):
        res, calls = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "add thing", "--pr")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(calls[-1], "ship")
        self.assertEqual(ravend.next_action(self.worktree(), "s")["action"], "done")

    def test_large_spec_pauses_then_resume_continues(self):
        big = {"spec": [{"slug": "big", "tier": "large", "blocking_questions": []}]}
        res, calls = self.run_pipeline({**big, **self.OK}, "x")
        self.assertEqual((res.returncode, calls), (0, ["spec"]))
        self.assertIn("--resume big", res.stdout)
        res, calls = self.run_pipeline({**big, **self.OK}, "--resume", "big")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertEqual(calls[1:], ["build", "verify", "review"])

    def test_blocking_questions_need_a_human(self):
        res, _ = self.run_pipeline({"spec": [{"slug": "q", "tier": "small", "blocking_questions": ["auth?"]}]}, "x")
        self.assertEqual(res.returncode, 3)

    def test_trivial_change_builds_and_gates_without_spec(self):
        res, calls = self.run_pipeline({"spec": [{"slug": "tiny", "tier": "trivial", "blocking_questions": []}],
                                        **self.OK}, "fix label")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(calls, ["spec", "build"])
        self.assertIn("trivial pronta", res.stdout)

    def test_review_fix_round_goes_back_through_verify(self):
        script = {**self.SPEC_SMALL, **self.OK, "review": [self.P1, {"verdict": "APPROVED", "findings": []}]}
        res, calls = self.run_pipeline(script, "x")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertEqual(calls, ["spec", "build", "verify", "review", "fix", "verify", "review"])
        self.assertTrue((self.data / "specs" / "s" / "review-1.md").exists())

    def test_same_finding_twice_escalates(self):
        script = {**self.SPEC_SMALL, **self.OK, "review": [self.P1, self.P1, self.P1]}
        res, calls = self.run_pipeline(script, "x")
        self.assertEqual(res.returncode, 3, res.stdout)
        self.assertEqual(calls.count("review"), 2)
        self.assertIn("mesmos problemas", res.stdout)

    def test_runner_reruns_gate_and_does_not_trust_verify_claim(self):
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")
        subprocess.run("git -c user.email=t@t -c user.name=t commit -qam red", cwd=self.repo, shell=True, check=True)
        res, calls = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "x", FAKE_FIX_FILE="src/sum.js")
        self.assertEqual(res.returncode, 0, res.stdout)
        # verify claimed PASS but the real gate was red -> one fix round, then verify again
        self.assertEqual(calls[2:5], ["verify", "fix", "verify"])

    def test_verify_that_never_turns_green_stops_after_max_rounds(self):
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")
        subprocess.run("git -c user.email=t@t -c user.name=t commit -qam red", cwd=self.repo, shell=True, check=True)
        res, calls = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "x")
        self.assertEqual(res.returncode, 3, res.stdout)
        self.assertEqual((calls.count("verify"), calls.count("fix")), (3, 2))

    def test_missing_profile_exit_2(self):
        (self.data / "profile.json").unlink()
        res, calls = self.run_pipeline(self.SPEC_SMALL, "x")
        self.assertEqual((res.returncode, calls), (2, []))

    def test_chosen_mcp_servers_are_allowed_only_in_their_stages(self):
        profile = json.loads((self.data / "profile.json").read_text())
        profile["integrations"] = {"issues": ["claude.ai Atlassian"], "browser": ["chrome-devtools"]}
        ravend.save_json(self.data / "profile.json", profile)
        res, _ = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "x")
        self.assertEqual(res.returncode, 0, res.stdout)
        allowed = {c["stage"]: c["args"] for c in self.calls}
        self.assertIn("mcp__claude_ai_Atlassian", allowed["spec"])
        self.assertNotIn("mcp__chrome-devtools", allowed["spec"])
        self.assertIn("mcp__chrome-devtools", allowed["verify"])
        self.assertNotIn("mcp__playwright", allowed["verify"])  # a browser MCP was chosen

    def test_second_run_on_the_same_worktree_is_refused(self):
        subprocess.run(["git", "worktree", "add", "-q", "-b", "feat/s", str(self.worktree()), "main"],
                       cwd=self.repo, check=True)
        with ravend.file_lock(ravend.state_dir(self.worktree()) / "run.lock", blocking=False):
            res, calls = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "x")
        self.assertEqual(res.returncode, 2, res.stdout)
        self.assertEqual(calls, ["spec"])

    def test_worktree_gets_local_mcp_servers_of_main_checkout(self):
        cfg = Path(self.tmp.name) / "cfg"
        ravend.save_json(cfg / ".claude.json", {"projects": {str(self.repo): {"mcpServers": {
            "pw": {"command": "npx", "args": ["@playwright/mcp@1"]}}}}})
        res, _ = self.run_pipeline({**self.SPEC_SMALL, **self.OK}, "x", CLAUDE_CONFIG_DIR=str(cfg))
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIsNone(self.calls[0]["mcp"])  # spec runs in the main checkout
        self.assertEqual(self.calls[1]["mcp"], {"mcpServers": {"pw": {"command": "npx", "args": ["@playwright/mcp@1"]}}})
        path = self.calls[1]["args"][self.calls[1]["args"].index("--mcp-config") + 1]
        self.assertFalse(Path(path).exists())  # temp config removed at the end


if __name__ == "__main__":
    unittest.main()
