"""Unit tests for scripts/ravend.py (stdlib unittest). Run: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ravend  # noqa: E402

SCRIPT = Path(ravend.__file__)


def sh(cmd, cwd, **env):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, env={**os.environ, **env})


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.home = base / "home"
        self.repo = base / "repo"
        (self.repo / "src").mkdir(parents=True)
        (self.repo / "test").mkdir()
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a + b;\n")
        (self.repo / "test" / "sum.test.js").write_text(
            "import { test } from 'node:test'; import assert from 'node:assert/strict';\n"
            "import { sum } from '../src/sum.js';\ntest('sum', () => assert.equal(sum(2, 2), 4));\n")
        (self.repo / "package.json").write_text('{"name":"demo","type":"module"}')
        sh("git init -q -b main && git -c user.email=t@t -c user.name=t add -A && "
           "git -c user.email=t@t -c user.name=t commit -qm init", self.repo)
        os.environ["RAVEND_HOME"] = str(self.home)
        self.data = ravend.data_dir(self.repo)
        ravend.save_json(self.data / "profile.json", {
            "version": 1, "stacks": ["node"], "protected_paths": [".env"],
            "gate": {"fast": [{"name": "tests", "run": "node --test", "when": ["src/*", "test/*"]}],
                     "full": [{"name": "tests", "run": "node --test"}]}})

    def tearDown(self):
        os.environ.pop("RAVEND_HOME", None)
        self.tmp.cleanup()

    def run_cli(self, *args, stdin=None, **env):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.repo, input=stdin, capture_output=True,
                              text=True, env={**os.environ, **env})

    def hook(self, event, **payload):
        payload.setdefault("cwd", str(self.repo))
        payload.setdefault("session_id", "s1")
        return self.run_cli("hook", event, stdin=json.dumps(payload))


class Identity(unittest.TestCase):
    def test_project_id_from_remote_is_stable_across_url_styles(self):
        with tempfile.TemporaryDirectory() as tmp:
            sh("git init -q && git remote add origin git@github.com:Org/Repo.git", tmp)
            ssh = ravend.project_id(Path(tmp))
            sh("git remote set-url origin https://github.com/Org/Repo.git", tmp)
            self.assertEqual(ssh, ravend.project_id(Path(tmp)))
            self.assertEqual(ssh, "github.com-org-repo")


class Placeholders(unittest.TestCase):
    def test_java_tests_maps_main_and_test_files(self):
        files = ["svc/src/main/java/a/OrderService.java", "svc/src/test/java/a/PriceTest.java", "README.md"]
        self.assertEqual(ravend._java_tests(files), "OrderService*Test,PriceTest")

    def test_gradle_tests_expands_one_flag_per_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for f in ("src/main/java/A.java", "src/test/java/BTest.java"):
                (root / f).parent.mkdir(parents=True, exist_ok=True)
                (root / f).write_text("x")
            step = {"run": "./gradlew test {gradle_tests}"}
            cmd, _ = ravend.resolve_step(step, root, ["src/main/java/A.java", "src/test/java/BTest.java"], "main")
            self.assertEqual(cmd, "./gradlew test --tests 'A*Test' --tests BTest")
            cmd, _ = ravend.resolve_step(step, root, [], "main")
            self.assertIsNone(cmd)  # nothing changed -> skipped

    def test_files_are_relative_to_step_cwd_and_skip_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "web" / "src").mkdir(parents=True)
            (root / "web" / "src" / "a.ts").write_text("x")
            step = {"run": "eslint {files}", "cwd": "web", "when": ["web/*"]}
            cmd, _ = ravend.resolve_step(step, root, ["web/src/a.ts", "api/X.java"], "main")
            self.assertEqual(cmd, "eslint src/a.ts")
            cmd, why = ravend.resolve_step(step, root, ["api/X.java"], "main")
            self.assertIsNone(cmd)
            self.assertIn("when", why)


class Gate(RepoCase):
    def test_fast_gate_skips_when_nothing_changed_and_fails_on_broken_code(self):
        self.assertEqual(self.run_cli("gate", "fast").returncode, 0)
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")
        res = self.run_cli("gate", "fast")
        self.assertEqual(res.returncode, 1)
        self.assertIn("RAVEND_GATE FAST: FAIL", res.stdout)
        self.assertIn("full log:", res.stdout)

    def test_missing_profile_returns_2(self):
        (self.data / "profile.json").unlink()
        self.assertEqual(self.run_cli("gate", "fast").returncode, 2)


class Hooks(RepoCase):
    def test_stop_is_noop_when_not_armed(self):
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")
        self.assertEqual(self.hook("stop").stdout.strip(), "")

    def test_stop_blocks_on_red_then_allows_after_fix_and_commit(self):
        self.run_cli("arm", RAVEND_SESSION_ID="s1")
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")
        out = json.loads(self.hook("stop").stdout)
        self.assertEqual(out["decision"], "block")
        self.assertEqual(self.hook("stop", session_id="other").stdout.strip(), "")
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a + b;\n// changed\n")
        self.assertEqual(self.hook("stop").stdout.strip(), "")
        sh("git -c user.email=t@t -c user.name=t commit -qam fix", self.repo)
        state = json.loads((self.data / "state" / "green.json").read_text())
        self.assertEqual(state["fast"], ravend.tree_fingerprint(self.repo))  # same tree after commit

    def test_stop_gives_up_after_max_blocks(self):
        self.run_cli("arm", RAVEND_SESSION_ID="s1")
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")
        decisions = [json.loads(self.hook("stop").stdout).get("decision") for _ in range(4)]
        self.assertEqual(decisions, ["block", "block", "block", None])

    def test_pre_edit_denies_protected_paths_only(self):
        denied = json.loads(self.hook("pre-edit", tool_input={"file_path": str(self.repo / ".env")}).stdout)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.hook("pre-edit", tool_input={"file_path": str(self.repo / "src/a.js")}).stdout, "")

    def test_session_start_injects_context_and_env(self):
        env_file = Path(self.tmp.name) / "env"
        res = self.run_cli("hook", "session-start", stdin=json.dumps({"cwd": str(self.repo), "session_id": "s9"}),
                           CLAUDE_ENV_FILE=str(env_file))
        self.assertIn("local data dir (never committed)", res.stdout)
        self.assertIn("RAVEND_SESSION_ID=s9", env_file.read_text())

    def test_hooks_are_silent_outside_ravend_projects(self):
        with tempfile.TemporaryDirectory() as other:
            sh("git init -q", other)
            for event in ("session-start", "pre-edit", "post-edit", "stop"):
                res = self.run_cli("hook", event, stdin=json.dumps({"cwd": other, "session_id": "s1"}))
                self.assertEqual((res.returncode, res.stdout.strip()), (0, ""), event)


if __name__ == "__main__":
    unittest.main()
