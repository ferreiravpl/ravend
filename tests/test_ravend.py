"""Unit tests for scripts/ravend.py (stdlib unittest). Run: python3 -m unittest discover -s tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ravend_lib as ravend  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ravend.py"

# The suite never reaches the network: the update check reads from here (nothing is published there).
os.environ["RAVEND_UPDATE_URL"] = "file:///nonexistent/ravend-published"


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
        state = json.loads((ravend.state_dir(self.repo) / "green.json").read_text())
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
        self.assertIn("Brazilian Portuguese (pt-BR)", res.stdout)
        self.assertIn("follows the repository's written rules", res.stdout)
        self.assertIn(f"Ravend CLI: `python3 {ravend.PLUGIN_ROOT}/scripts/ravend.py`", res.stdout)
        self.assertIn("RAVEND_SESSION_ID=s9", env_file.read_text())

    def test_hooks_are_silent_outside_ravend_projects(self):
        with tempfile.TemporaryDirectory() as other:
            sh("git init -q", other)
            for event in ("session-start", "pre-edit", "post-edit", "stop"):
                res = self.run_cli("hook", event, stdin=json.dumps({"cwd": other, "session_id": "s1"}))
                self.assertEqual((res.returncode, res.stdout.strip()), (0, ""), event)


class Integrations(RepoCase):
    def test_tool_prefix_matches_claude_code_naming(self):
        self.assertEqual(ravend.mcp_tool_prefix("claude.ai Atlassian"), "mcp__claude_ai_Atlassian")
        self.assertEqual(ravend.mcp_tool_prefix("plugin:context7:context7"), "mcp__plugin_context7_context7")
        self.assertEqual(ravend.mcp_tool_prefix("my-db"), "mcp__my-db")

    def test_list_line_parsing_never_keeps_secrets(self):
        row = ravend._list_line("pg: npx -y @org/postgres-mcp --password hunter2 postgres://u:p@h/db - ✔ Connected")
        self.assertEqual((row["name"], row["status"]), ("pg", "Connected"))
        self.assertNotIn("hunter2", json.dumps(row))
        self.assertNotIn("u:p", json.dumps(row))
        row = ravend._list_line("db: npx postgres://admin:pw@db.local/mcp @x/db-mcp - ✔ Connected")
        self.assertEqual(row["hint"], "npx @x/db-mcp")
        row = ravend._list_line("claude.ai Atlassian: https://mcp.atlassian.com/v1/sse?token=abc - ✗ Failed to connect")
        self.assertEqual((row["hint"], row["status"]), ("mcp.atlassian.com", "Failed to connect"))
        self.assertIsNone(ravend._list_line("Checking MCP server health…"))

    def test_discovers_user_local_and_project_servers_without_secrets(self):
        cfg = Path(self.tmp.name) / "cfg"
        ravend.save_json(cfg / ".claude.json", {
            "mcpServers": {"github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
                                      "headers": {"Authorization": "Bearer SECRET"}}},
            "projects": {str(self.repo): {"mcpServers": {"pw": {"command": "npx", "args": ["@playwright/mcp@1"],
                                                                "env": {"TOKEN": "SECRET"}}}}}})
        ravend.save_json(self.repo / ".mcp.json", {"mcpServers": {"serena": {"command": "uvx", "args": ["serena-mcp"]}}})
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfg)
        try:
            rows = {r["name"]: r for r in ravend.mcp_servers(self.repo, probe=False)}
        finally:
            os.environ.pop("CLAUDE_CONFIG_DIR")
        self.assertEqual({n: r["source"] for n, r in rows.items()},
                         {"github": "user", "pw": "local", "serena": "project"})
        self.assertEqual(rows["pw"]["hint"], "npx @playwright/mcp@1")
        self.assertNotIn("SECRET", json.dumps(rows))

    def test_integrations_are_filtered_by_stage_and_injected_at_session_start(self):
        profile = json.loads((self.data / "profile.json").read_text())
        profile["integrations"] = {"issues": ["claude.ai Atlassian"], "browser": ["playwright"], "empty": []}
        ravend.save_json(self.data / "profile.json", profile)
        self.assertEqual(list(ravend.integrations(profile, "spec")), ["issues"])
        self.assertEqual(ravend.integration_tools(profile, "verify"), ["mcp__playwright"])
        self.assertNotIn("empty", ravend.integrations(profile))
        out = self.hook("session-start").stdout
        self.assertIn("issues→claude.ai Atlassian [spec]", out)
        project = json.loads(self.run_cli("project").stdout)
        self.assertEqual(project["integrations"]["browser"]["tools"], ["mcp__playwright"])


class Checkouts(RepoCase):
    def test_worktrees_keep_separate_gate_state(self):
        wt = Path(self.tmp.name) / "repo-wt"
        sh(f"git worktree add -q -b feat/x {wt}", self.repo)
        self.assertEqual(ravend.data_dir(wt), self.data)  # specs/knowledge shared
        self.assertNotEqual(ravend.state_dir(wt), ravend.state_dir(self.repo))
        (wt / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "gate", "full"], cwd=wt, capture_output=True,
                                        env=os.environ.copy()).returncode, 1)
        self.assertEqual(self.run_cli("gate", "full").returncode, 0)
        self.assertEqual(json.loads((ravend.state_dir(wt) / "last-gate-full.json").read_text())["status"], "FAIL")
        self.assertEqual(json.loads((ravend.state_dir(self.repo) / "last-gate-full.json").read_text())["status"], "PASS")

    def test_non_blocking_lock_reports_busy(self):
        lock = Path(self.tmp.name) / "x.lock"
        with ravend.file_lock(lock, blocking=False) as first:
            with ravend.file_lock(lock, blocking=False) as second:
                self.assertEqual((first, second), (True, ravend.fcntl is None))


class TerminalCommand(RepoCase):
    def test_install_cli_finds_installed_plugin_and_forwards(self):
        cfg, bindir = Path(self.tmp.name) / "cfg", Path(self.tmp.name) / "bin"
        ravend.save_json(cfg / "plugins" / "installed_plugins.json", {"version": 2, "plugins": {
            "ravend@ravend": [{"scope": "user", "installPath": str(SCRIPT.parent.parent)}]}})
        self.assertEqual(self.run_cli("install-cli", "--dir", str(bindir)).returncode, 0)
        env = {"CLAUDE_CONFIG_DIR": str(cfg)}
        res = subprocess.run([str(bindir / "ravend"), "status"], cwd=self.repo, capture_output=True, text=True,
                             env={**os.environ, **env})
        self.assertIn("perfil sim", res.stdout)
        res = subprocess.run([str(bindir / "ravend"), "auto", "--help"], cwd=self.repo, capture_output=True, text=True,
                             env={**os.environ, **env})
        self.assertIn("usage: ravend auto", res.stdout)


SPEC = """---
slug: s
title: Coupon
tier: {tier}
status: {status}
branch: feat/s
---
# Coupon

## Tasks
- [ ] T1: first — files: src/sum.js — proves: AC1 — deps: none
- [ ] T2: second — files: src/sum.js — proves: AC1 — deps: T1

## Log
"""


class FlowBase(RepoCase):
    def write_spec(self, tier="small", status="approved"):
        path = ravend.spec_file(self.data, "s")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SPEC.format(tier=tier, status=status))
        return path

    def nxt(self):
        return ravend.next_action(self.repo, "s")


class Flow(FlowBase):
    def test_no_spec_points_to_start_and_one_spec_is_picked_automatically(self):
        self.assertEqual(ravend.next_action(self.repo)["action"], "start")
        self.write_spec()
        self.assertEqual(ravend.next_action(self.repo)["slug"], "s")

    def test_large_draft_waits_for_approval_and_blocking_questions_win(self):
        path = self.write_spec(tier="large", status="draft")
        self.assertEqual(self.nxt()["action"], "approve")
        path.write_text(path.read_text() + "\n## Open questions\n- BLOCKING: which currency?\n")
        info = self.nxt()
        self.assertEqual((info["action"], info["questions"]), ("answer", ["BLOCKING: which currency?"]))
        self.assertEqual(self.run_cli("spec", "approve", "s").returncode, 0)
        self.assertEqual(self.nxt()["action"], "build")

    def test_full_cycle_build_verify_fix_review_ship(self):
        self.write_spec()
        self.assertEqual((self.nxt()["action"], self.nxt()["task"]), ("build", "T1"))
        self.assertEqual(self.run_cli("task", "done", "s", "t1").returncode, 0)
        self.assertEqual(self.nxt()["task"], "T2")
        self.assertEqual(self.run_cli("task", "done", "s", "T9").returncode, 2)  # unknown task
        self.run_cli("task", "done", "s", "T2")
        self.assertIn("in-progress", ravend.spec_file(self.data, "s").read_text())
        self.assertEqual(self.nxt()["action"], "verify")
        # recording without a gate on this exact code is refused
        self.assertEqual(self.run_cli("verify", "record", "s").returncode, 2)
        self.run_cli("gate", "full")
        self.assertEqual(self.run_cli("verify", "record", "s", "--uncovered", "AC1: no test").returncode, 0)
        info = self.nxt()
        self.assertEqual((info["action"], info["fix"]), ("fix", "verify"))
        (self.repo / "test" / "more.test.js").write_text("import { test } from 'node:test'; test('x', () => {});\n")
        self.assertEqual(self.nxt()["action"], "verify")  # code changed after the record
        self.run_cli("gate", "full")
        self.run_cli("verify", "record", "s")
        self.assertEqual(self.nxt()["action"], "review")
        review = {"verdict": "APPROVED", "findings": [{"severity": "P1", "file": "src/sum.js", "line": 1,
                                                       "title": "overflow", "scenario": "big numbers"}]}
        res = self.run_cli("review", "record", "s", stdin=json.dumps(review))
        self.assertIn("CHANGES_REQUESTED", res.stdout)  # a P1 can never be APPROVED
        self.assertIn("overflow", (self.data / "specs" / "s" / "review-1.md").read_text())
        self.assertEqual((self.nxt()["action"], self.nxt()["fix"]), ("fix", "review"))
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a + b; // fixed\n")
        self.run_cli("gate", "full")
        self.run_cli("verify", "record", "s")
        self.run_cli("review", "record", "s", stdin='{"verdict": "APPROVED", "findings": []}')
        self.assertEqual(self.nxt()["action"], "ship")
        self.run_cli("spec", "done", "s", "--pr", "https://example.com/pr/9")
        info = self.nxt()
        self.assertEqual(info["action"], "done")
        self.assertIn("pr/9", info["message"])

    def test_review_file_inside_the_repo_is_refused(self):
        self.write_spec()
        (self.repo / "review.json").write_text('{"findings": []}')
        res = self.run_cli("review", "record", "s", "--file", str(self.repo / "review.json"))
        self.assertEqual(res.returncode, 2)
        self.assertIn("pasta de dados", res.stderr)
        outside = Path(self.tmp.name) / "review.json"
        outside.write_text('{"findings": []}')
        self.assertEqual(self.run_cli("review", "record", "s", "--file", str(outside)).returncode, 0)
        self.assertEqual(ravend.spec_state(self.data, "s")["reviews"][0]["raw"], {"findings": []})

    def test_review_file_in_a_data_dir_inside_the_repo_is_accepted(self):
        os.environ["RAVEND_HOME"] = str(self.repo / ".ravend-home")  # as in the evals: data dir inside the repo
        (self.repo / ".git" / "info" / "exclude").write_text(".ravend-home/\n")
        self.data = ravend.data_dir(self.repo)
        ravend.save_json(self.data / "profile.json", {"version": 1, "gate": {"fast": [], "full": []}})
        review_input = self.write_spec().parent / "review-input.json"
        review_input.write_text('{"findings": []}')
        res = self.run_cli("review", "record", "s", "--file", str(review_input))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(len(ravend.spec_state(self.data, "s")["reviews"]), 1)

    def test_repeated_review_findings_escalate_to_human(self):
        self.write_spec()
        for t in ("T1", "T2"):
            self.run_cli("task", "done", "s", t)
        bad = json.dumps({"findings": [{"severity": "P0", "file": "a.js", "title": "same bug"}]})
        for i in range(2):
            (self.repo / "src" / "sum.js").write_text(f"export const sum = (a, b) => a + b; // try {i}\n")
            self.run_cli("gate", "full")
            self.run_cli("verify", "record", "s")
            self.run_cli("review", "record", "s", stdin=bad)
        info = self.nxt()
        self.assertEqual(info["action"], "human")
        self.assertEqual(info["blocking"], ["a.js — same bug"])

    def test_two_active_specs_need_a_choice_unless_the_branch_tells(self):
        self.write_spec()
        other = ravend.spec_file(self.data, "other")
        other.parent.mkdir(parents=True)
        other.write_text(SPEC.format(tier="small", status="approved").replace("feat/s", "feat/other"))
        self.assertEqual(ravend.next_action(self.repo)["action"], "choose")
        sh("git switch -q -c feat/other", self.repo)
        self.assertEqual(ravend.next_action(self.repo)["slug"], "other")

    def test_next_task_respects_deps(self):
        path = self.write_spec()
        path.write_text(path.read_text().replace("first — files: src/sum.js — proves: AC1 — deps: none",
                                                 "first — files: src/sum.js — proves: AC1 — deps: T2")
                        .replace("second — files: src/sum.js — proves: AC1 — deps: T1",
                                 "second — files: src/sum.js — proves: AC1 — deps: none"))
        self.assertEqual(self.nxt()["task"], "T2")

    def test_legacy_records_still_count_for_the_origin(self):
        path = self.write_spec()
        path.write_text(path.read_text().replace("- [ ]", "- [x]"))
        ravend.save_json(self.data / "specs" / "s" / "state.json", {"verify": [
            {"fingerprint": ravend.tree_fingerprint(self.repo), "gate": "PASS", "uncovered": []}]})
        self.assertEqual(self.nxt()["action"], "review")


class App(RepoCase):
    def test_app_running_from_another_checkout_blocks_a_second_start(self):
        sleeper = subprocess.Popen(["sleep", "30"])
        try:
            ravend.save_json(self.data / "state" / "other-checkout" / "app.json", {"api": sleeper.pid})
            ok, msg = ravend.app_start(self.repo, {"app": {"name": "api", "start": "true"}})
            self.assertFalse(ok)
            self.assertIn("other-checkout", msg)
        finally:
            sleeper.kill()
            sleeper.wait()
        self.assertIsNone(ravend.app_owner(self.repo))  # dead pids do not block


class UpdateNotice(RepoCase):
    def publish(self, version, changelog=""):
        published = Path(self.tmp.name) / "published"
        (published / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (published / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": version}))
        (published / "CHANGELOG.md").write_text(changelog)
        return {"RAVEND_UPDATE_URL": published.as_uri()}

    def session_start(self, **env):
        return self.run_cli("hook", "session-start", stdin=json.dumps({"cwd": str(self.repo)}), **env)

    def test_newer_published_version_is_announced_with_its_changes(self):
        env = self.publish("99.0.0", "# Changelog\n## 99.0.0\n- big change\n- another one\n## 0.0.1\n- ancient\n")
        res = self.session_start(**env)
        self.assertEqual(res.returncode, 0)
        self.assertIn("update available", res.stdout)
        self.assertIn("99.0.0 — big change", res.stdout)
        self.assertIn("99.0.0 — another one", res.stdout)
        self.assertNotIn("ancient", res.stdout)
        self.assertIn(ravend.UPDATE_COMMAND, res.stdout)

    def test_installed_version_already_published_is_silent(self):
        env = self.publish(ravend.diagnostics._plugin_version(), "## 0.0.1\n- ancient\n")
        self.assertNotIn("update available", self.session_start(**env).stdout)

    def test_unreachable_source_never_breaks_the_session(self):
        res = self.session_start()
        self.assertEqual(res.returncode, 0)
        self.assertNotIn("update available", res.stdout)
        self.assertIn("local data dir", res.stdout)

    def test_published_release_is_cached_between_sessions(self):
        self.assertIn("update available", self.session_start(**self.publish("99.0.0")).stdout)
        self.assertIn("update available", self.session_start(**self.publish(ravend.diagnostics._plugin_version())).stdout)

    def test_doctor_warns_about_the_update(self):
        res = self.run_cli("doctor", **self.publish("99.0.0", "## 99.0.0\n- big change\n"))
        self.assertIn("atualização: instalada", res.stdout)
        self.assertIn("99.0.0 — big change", res.stdout)

    def test_changelog_has_lines_for_the_current_version(self):
        root = Path(__file__).resolve().parent.parent
        version = json.loads((root / ".claude-plugin" / "plugin.json").read_text())["version"]
        lines = ravend.changes_since((root / "CHANGELOG.md").read_text(), "0.0.0", version)
        self.assertTrue(any(line.startswith(version + " — ") for line in lines),
                        f"CHANGELOG.md needs a `## {version}` section with at least one `- ` line")


class Doctor(RepoCase):
    def test_doctor_reports_missing_gate_command_and_profile(self):
        res = self.run_cli("doctor", "--no-probe")
        self.assertIn("perfil", res.stdout)
        profile = json.loads((self.data / "profile.json").read_text())
        profile["gate"]["full"] = [{"name": "build", "run": "./mvnw -q verify"}]
        ravend.save_json(self.data / "profile.json", profile)
        res = self.run_cli("doctor", "--no-probe")
        self.assertEqual(res.returncode, 1)
        self.assertIn("`./mvnw` não encontrado", res.stdout)
        (self.data / "profile.json").unlink()
        self.assertIn("rode /ravend:init", self.run_cli("doctor", "--no-probe").stdout)


FAKE_GH = r"""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ["pr", "view"]:
    print(Path(os.environ["FAKE_GH_PR"]).read_text()); sys.exit(0)
if args[:2] == ["run", "view"]:
    print("step 1 ok\nERROR: native image build failed: class X not registered for reflection\n"); sys.exit(0)
sys.exit(1)
"""


class RiskAndCI(FlowBase):
    def setUp(self):
        super().setUp()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        (self.bin / "gh").write_text(FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.pr_json = Path(self.tmp.name) / "pr.json"
        self.env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "FAKE_GH_PR": str(self.pr_json),
                    "RAVEND_CI_INTERVAL": "0"}

    def cli(self, *args, **kw):
        return self.run_cli(*args, **{**self.env, **kw})

    def set_profile(self, **extra):
        profile = json.loads((self.data / "profile.json").read_text())
        profile.update(extra)
        ravend.save_json(self.data / "profile.json", profile)

    def verified_and_reviewed(self, review='{"verdict": "APPROVED", "findings": []}'):
        self.run_cli("gate", "full")
        self.run_cli("verify", "record", "s")
        self.run_cli("review", "record", "s", stdin=review)

    def pr(self, state="OPEN", head=None, checks=()):
        head = head or ravend.git(["rev-parse", "HEAD"], self.repo)
        self.pr_json.write_text(json.dumps({"state": state, "headRefOid": head, "url": "https://example.com/pr/9",
                                            "statusCheckRollup": list(checks)}))

    def test_risk_area_needs_human_approval_and_review_lenses_even_when_small(self):
        self.set_profile(risk=[{"name": "dinheiro", "paths": ["src/*"], "lenses": ["money", "Concurrency"]},
                               {"name": "docs", "paths": ["docs/**"], "lenses": ["contract"]}])
        self.write_spec()  # small, already approved by the spec skill
        info = self.nxt()
        self.assertEqual(info["action"], "approve")
        self.assertEqual([h["name"] for h in info["risk"]], ["dinheiro"])  # from the task's declared files
        self.assertEqual(self.run_cli("spec", "approve", "s").returncode, 0)
        self.assertEqual(self.nxt()["action"], "build")
        self.run_cli("task", "done", "s", "T1")
        self.run_cli("task", "done", "s", "T2")
        self.verified_and_reviewed()
        info = self.nxt()
        self.assertEqual((info["action"], info["lenses"]), ("review", ["concurrency", "money"]))
        self.run_cli("review", "record", "s", stdin='{"verdict": "APPROVED", "findings": [], "lenses": ["money"]}')
        self.assertIn("concurrency", self.nxt()["message"])
        self.run_cli("review", "record", "s",
                     stdin='{"verdict": "APPROVED", "findings": [], "lenses": ["money", "concurrency"]}')
        self.assertEqual(self.nxt()["action"], "ship")

    def test_after_the_pr_ci_is_followed_until_merge_and_red_ci_is_a_fix_round(self):
        self.write_spec()
        for t in ("T1", "T2"):
            self.run_cli("task", "done", "s", t)
        self.verified_and_reviewed()
        self.assertEqual(self.run_cli("spec", "shipped", "s").returncode, 2)  # needs --pr
        self.run_cli("spec", "shipped", "s", "--pr", "https://example.com/pr/9")
        self.assertEqual(self.nxt()["action"], "ci")
        self.pr(checks=[{"__typename": "CheckRun", "name": "build", "status": "IN_PROGRESS", "conclusion": ""}])
        self.cli("ci", "s")
        self.assertIn("Aguardando", self.nxt()["message"])
        self.pr(checks=[{"__typename": "CheckRun", "name": "native", "status": "COMPLETED", "conclusion": "FAILURE",
                         "detailsUrl": "https://github.com/o/r/actions/runs/42/job/7"},
                        {"__typename": "StatusContext", "context": "lint", "state": "SUCCESS"}])
        res = self.cli("ci", "s", "--wait", "1")
        self.assertIn("VERMELHO", res.stdout)
        info = self.nxt()
        self.assertEqual((info["action"], info["fix"]), ("fix", "ci"))
        self.assertIn("native", info["problem"])
        self.assertIn("not registered for reflection", Path(info["logs"][0]).read_text())
        # the fix is a new commit: verify and review again, then push it to the PR, then CI again
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a + b; // native fix\n")
        sh("git -c user.email=t@t -c user.name=t commit -qam fix", self.repo)
        self.assertEqual(self.nxt()["action"], "verify")
        self.verified_and_reviewed()
        self.assertEqual(self.nxt()["action"], "ship")  # local commit not in the PR yet
        self.pr(checks=[{"__typename": "CheckRun", "name": "native", "status": "COMPLETED", "conclusion": "SUCCESS"}])
        self.cli("ci", "s")
        self.assertEqual(self.nxt()["action"], "merge")
        self.pr(state="MERGED", checks=[])
        self.cli("ci", "s")
        self.assertEqual(self.nxt()["action"], "done")

    def test_ci_can_be_recorded_by_hand_without_gh(self):
        self.write_spec()
        for t in ("T1", "T2"):
            self.run_cli("task", "done", "s", t)
        self.verified_and_reviewed()
        self.run_cli("spec", "shipped", "s", "--pr", "https://example.com/pr/9")
        self.run_cli("ci", "s", "--state", "fail", "--failed", "e2e: timeout")
        self.assertEqual(self.nxt()["fix"], "ci")
        self.assertEqual(ravend.classify([{"name": "a", "status": "COMPLETED", "conclusion": "SKIPPED"}])[0], "pass")


class Guards(RepoCase):
    def pre(self, event, tool, **tool_input):
        payload = {"tool_name": tool, "tool_input": tool_input}
        agent = tool_input.pop("_agent", None)
        if agent:
            payload["agent_type"] = agent
        res = self.hook(event, **payload)
        return "deny" in res.stdout

    def test_commands_that_change_real_infra_are_denied_but_reads_and_plans_pass(self):
        self.assertTrue(self.pre("pre-command", "Bash", command="cd infra && terraform -chdir=x apply -auto-approve"))
        self.assertTrue(self.pre("pre-command", "Bash", command="gh pr merge 3 --squash"))
        self.assertFalse(self.pre("pre-command", "Bash", command="terraform plan -out tf.plan"))
        self.assertFalse(self.pre("pre-command", "Bash", command='git commit -m "explica o terraform apply no CI"'))
        self.assertTrue(self.pre("pre-command", "mcp__aws-api__call_aws", cli_command="aws sqs purge-queue --queue-url q"))
        self.assertFalse(self.pre("pre-command", "mcp__aws-api__call_aws", cli_command="aws sqs get-queue-attributes --queue-url q"))
        self.assertFalse(self.pre("pre-command", "mcp__github__create_pull_request", body="CI runs terraform apply after merge"))
        self.assertTrue(self.pre("pre-command", "mcp__github__merge_pull_request", pull_number=3))
        res = self.hook("pre-command", tool_name="Bash", tool_input={"command": "terraform apply"})
        self.assertIn("deny", res.stdout)
        res = subprocess.run([sys.executable, str(SCRIPT), "hook", "pre-command"], cwd=self.repo, capture_output=True,
                             text=True, env={**os.environ, "RAVEND_GUARD": "off"},
                             input=json.dumps({"cwd": str(self.repo), "tool_name": "Bash",
                                               "tool_input": {"command": "terraform apply"}}))
        self.assertNotIn("deny", res.stdout)

    def test_reviewer_is_read_only_and_verifier_only_touches_tests(self):
        src = str(self.repo / "src" / "sum.js")
        self.assertTrue(self.pre("pre-edit", "Edit", file_path=src, _agent="ravend:reviewer"))
        self.assertTrue(self.pre("pre-command", "Bash", command="git checkout main", _agent="ravend:reviewer"))
        self.assertFalse(self.pre("pre-command", "Bash", command="git diff main...HEAD | head", _agent="ravend:reviewer"))
        self.assertTrue(self.pre("pre-edit", "Write", file_path=src, _agent="ravend:verifier"))
        self.assertFalse(self.pre("pre-edit", "Write", file_path=str(self.repo / "test" / "x.test.js"), _agent="ravend:verifier"))
        self.assertFalse(self.pre("pre-edit", "Edit", file_path=src))  # the main session may edit code

    def test_related_repositories_are_read_only(self):
        other = Path(self.tmp.name) / "contracts"
        other.mkdir()
        profile = json.loads((self.data / "profile.json").read_text())
        profile["related_repos"] = [{"name": "contracts", "path": "../contracts", "use": "event records"}]
        ravend.save_json(self.data / "profile.json", profile)
        self.assertTrue(self.pre("pre-edit", "Write", file_path=str(other / "Event.java")))
        self.assertIn("contracts=", self.hook("session-start").stdout)


class InfraAndCI(RepoCase):
    WORKFLOW = """name: ci
on: [pull_request]
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
      - run: ./mvnw -B -ntp verify
      - name: native
        run: |
          ./mvnw -B package -Dnative \\
            -DskipTests
      - run: terraform fmt -check -recursive
"""

    def test_detects_terraform_helm_workflows_and_configured_siblings(self):
        (self.repo / "infra" / "network").mkdir(parents=True)
        (self.repo / "infra" / "network" / "main.tf").write_text('resource "x" "y" {}\\n')
        (self.repo / "infra" / "network" / ".tflint.hcl").write_text("")
        (self.repo / "chart" / "templates").mkdir(parents=True)
        (self.repo / "chart" / "Chart.yaml").write_text("name: c\\n")
        (self.repo / "chart" / "values-staging.yaml").write_text("")
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        (self.repo / ".github" / "workflows" / "ci.yml").write_text(self.WORKFLOW)
        sibling = Path(self.tmp.name) / "lib"
        sibling.mkdir()
        sh("git init -q", sibling)
        ravend.save_json(ravend.data_dir(sibling) / "profile.json", {"stacks": ["quarkus"]})
        info = json.loads(self.run_cli("detect").stdout)
        stacks = {m["path"]: m for m in info["modules"]}
        self.assertEqual(stacks["infra/network"]["stack"], "terraform")
        self.assertIn("tflint", stacks["infra/network"]["signals"])
        self.assertEqual(stacks["chart"]["signals"], ["values-per-env"])
        self.assertIn("github-actions", info["stacks"])
        self.assertIn("./mvnw -B package -Dnative -DskipTests", info["ci"]["workflows"][0]["runs"])
        self.assertEqual([(s["name"], s["has_profile"]) for s in info["siblings"]], [("lib", True)])

    def test_doctor_warns_when_ci_runs_what_the_gate_does_not(self):
        (self.repo / ".github" / "workflows").mkdir(parents=True)
        (self.repo / ".github" / "workflows" / "ci.yml").write_text(self.WORKFLOW)
        profile = json.loads((self.data / "profile.json").read_text())
        profile["gate"]["full"] = [{"name": "verify", "run": "node --test"}, {"name": "jvm", "run": "./mvnw -q verify"}]
        ravend.save_json(self.data / "profile.json", profile)
        drift = ravend.ci_drift(self.repo, profile)
        self.assertEqual(drift, ["`mvn package [native]` (.github/workflows/ci.yml)",
                                 "`terraform fmt` (.github/workflows/ci.yml)"])
        self.assertIn("gate × CI", self.run_cli("doctor", "--no-probe").stdout)


MULTI_SPEC = """---
slug: m
title: multi
tier: small
status: approved
branch: feat/m
repos: {repos}
---
## Acceptance criteria
- AC1 [unit]: Given a, when b, then c.
## Tasks
- [ ] T1: lib change — repo: lib — files: src/lib.js — proves: AC1 — deps: none
- [ ] T2: use it — files: src/sum.js — proves: AC1 — deps: T1
"""


def make_repo(path: Path, branch="main"):
    (path / "src").mkdir(parents=True)
    (path / "src" / "lib.js").write_text("export const one = 1;\n")
    (path / "package.json").write_text('{"name":"lib","type":"module"}')
    sh(f"git init -q -b {branch} && git -c user.email=t@t -c user.name=t add -A && "
       "git -c user.email=t@t -c user.name=t commit -qm init", path)


class MultiRepoBase(FlowBase):
    def setUp(self):
        super().setUp()
        self.lib = Path(self.tmp.name) / "lib"
        make_repo(self.lib)
        self.lib_data = ravend.data_dir(self.lib)
        self.lib_profile({})

    def lib_profile(self, extra, repo=None):
        profile = {"version": 1, "protected_paths": ["secret.txt"],
                   "gate": {"fast": [{"name": "t", "run": "true"}], "full": [{"name": "t", "run": "true"}]}}
        profile.update(extra)
        ravend.save_json(ravend.data_dir(repo or self.lib) / "profile.json", profile)

    def write_multi(self, repos="../lib", body=None):
        path = ravend.spec_file(self.data, "m")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body or MULTI_SPEC.format(repos=repos))
        return path

    def nxt(self):
        return ravend.next_action(self.repo, "m")

    def cli_in(self, cwd, *args, stdin=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, input=stdin, capture_output=True,
                              text=True, env=os.environ.copy())


class MultiRepo(MultiRepoBase):
    def test_repos_and_task_meta_are_parsed(self):
        text = MULTI_SPEC.format(repos="../lib, ../x")
        self.assertEqual(ravend.spec_repo_paths(text), ["../lib", "../x"])
        self.assertTrue(ravend.is_multi(text))
        self.assertFalse(ravend.is_multi(SPEC.format(tier="small", status="approved")))
        meta = ravend.task_meta(text)
        self.assertEqual(meta[0], {"id": "T1", "done": False, "title": "lib change", "repo": "lib", "deps": []})
        self.assertEqual((meta[1]["repo"], meta[1]["deps"]), (None, ["T1"]))

    def test_participants_resolve_by_project_id_and_dedupe(self):
        text = self.write_multi("../lib, ../lib/, " + str(self.lib)).read_text()
        repos, errors = ravend.spec_repos(self.repo, text)
        self.assertEqual(errors, [])
        self.assertEqual([r["project_id"] for r in repos], [ravend.project_id(self.repo), ravend.project_id(self.lib)])
        self.assertEqual([r["name"] for r in repos], ["repo", "lib"])
        self.assertTrue(repos[0]["origin"])

    def test_invalid_repos_become_blocking_questions(self):
        self.write_multi("../lib, ../nope")
        info = self.nxt()
        self.assertEqual(info["action"], "answer")
        self.assertTrue(any("../nope" in q for q in info["questions"]))
        self.write_multi()
        (self.lib_data / "profile.json").unlink()
        info = self.nxt()
        self.assertEqual(info["action"], "answer")
        self.assertTrue(any("lib" in q and "init" in q for q in info["questions"]))
        self.lib_profile({})
        self.write_multi(body=MULTI_SPEC.format(repos="../lib") + "- [ ] T3: x — repo: other — files: a — deps: none\n")
        self.assertTrue(any("other" in q for q in self.nxt()["questions"]))

    def test_build_points_to_the_task_repo_and_disables_parallel(self):
        self.write_multi()
        self.run_cli("spec", "approve", "m")
        info = self.nxt()
        self.assertEqual((info["action"], info["task"], info["repo"]), ("build", "T1", "lib"))
        self.assertEqual(info["repo_path"], str(self.lib.resolve()))
        self.assertIs(info["parallel"], False)
        self.assertEqual([r["name"] for r in info["repos"]], ["repo", "lib"])

    def on_branch(self):
        sh("git switch -qc feat/m", self.repo)
        sh("git switch -qc feat/m", self.lib)

    def tasks_done(self):
        self.write_multi()
        self.run_cli("spec", "approve", "m")
        self.run_cli("task", "done", "m", "T1")
        self.run_cli("task", "done", "m", "T2")

    def gate_both(self):
        self.run_cli("gate", "full")
        self.cli_in(self.lib, "gate", "full")

    def test_verify_needs_every_repo_gated_on_the_spec_branch(self):
        self.tasks_done()
        info = self.nxt()
        self.assertEqual((info["action"], info["off_branch"]), ("human", ["repo", "lib"]))
        self.assertIn("switch feat/m", info["command"])
        res = self.run_cli("verify", "record", "m")
        self.assertEqual(res.returncode, 2)
        self.assertIn("feat/m", res.stderr)
        self.on_branch()
        self.run_cli("gate", "full")
        res = self.run_cli("verify", "record", "m")
        self.assertEqual(res.returncode, 2)
        self.assertIn("lib", res.stderr)
        self.cli_in(self.lib, "gate", "full")
        self.assertEqual(self.run_cli("verify", "record", "m").returncode, 0)
        self.assertEqual(self.nxt()["action"], "review")

    def test_neighbour_switched_away_asks_to_switch_back_without_reverifying(self):
        self.tasks_done()
        self.on_branch()
        self.gate_both()
        self.run_cli("verify", "record", "m")
        self.assertEqual(self.nxt()["action"], "review")
        sh("git switch -q main", self.lib)
        info = self.nxt()
        self.assertEqual((info["action"], info["off_branch"]), ("human", ["lib"]))
        self.assertIn("em `main`", info["message"])
        self.assertIn(f"git -C {self.lib} switch feat/m", info["command"])
        sh("git switch -q feat/m", self.lib)
        self.assertEqual(self.nxt()["action"], "review")

    def test_change_only_in_the_neighbour_invalidates_verify_and_review(self):
        self.tasks_done()
        self.on_branch()
        self.gate_both()
        self.run_cli("verify", "record", "m")
        review = '{"findings": [], "lenses": ["contract"]}'
        self.assertEqual(self.run_cli("review", "record", "m", stdin=review).returncode, 0)
        self.assertNotIn(self.nxt()["action"], ("verify", "review"))
        (self.lib / "src" / "lib.js").write_text("export const one = 2;\n")
        self.assertEqual(self.nxt()["action"], "verify")

    def test_project_lists_siblings_with_profile(self):
        siblings = json.loads(self.run_cli("project").stdout)["siblings"]
        lib = next(s for s in siblings if s["name"] == "lib")
        self.assertTrue(lib["has_profile"])

    def test_multi_repo_spec_always_needs_runtime_approval_bound_to_its_repos(self):
        self.write_multi()
        self.assertEqual(self.nxt()["action"], "approve")
        self.run_cli("spec", "approve", "m")
        self.assertEqual(self.nxt()["action"], "build")
        lib2 = Path(self.tmp.name) / "lib2"
        make_repo(lib2)
        self.lib_profile({}, repo=lib2)
        self.write_multi(body=MULTI_SPEC.format(repos="../lib, ../lib2")
                         + "- [ ] T3: more — repo: lib2 — files: src/lib.js — deps: none\n")
        info = self.nxt()
        self.assertEqual(info["action"], "approve")
        self.assertIn("lib2", info["message"])
        self.run_cli("spec", "approve", "m")
        self.assertEqual(self.nxt()["action"], "build")

    def test_risk_uses_each_repos_own_profile_and_base(self):
        sh("git branch -m main master && git switch -qc feat/m", self.lib)
        (self.lib / "src" / "other.js").write_text("x\n")
        sh("git -c user.email=t@t -c user.name=t add -A && git -c user.email=t@t -c user.name=t commit -qm o", self.lib)
        self.lib_profile({"git": {"base_branch": "master"},
                          "risk": [{"name": "dinheiro", "paths": ["src/other.js"], "lenses": ["money"]}]})
        self.write_multi()
        self.run_cli("spec", "approve", "m")
        info = self.nxt()
        self.assertEqual(info["lenses"], ["contract", "money"])
        self.assertEqual((info["risk"][0]["name"], info["risk"][0]["repo"]), ("dinheiro", "lib"))

    def test_ready_multi_repo_spec_hands_off_instead_of_shipping(self):
        self.tasks_done()
        self.on_branch()
        self.gate_both()
        self.run_cli("verify", "record", "m")
        self.run_cli("review", "record", "m", stdin='{"findings": []}')
        info = self.nxt()
        self.assertEqual(info["action"], "review")
        self.assertIn("contract", info["message"])
        self.run_cli("review", "record", "m", stdin='{"findings": [], "lenses": ["contract"]}')
        info = self.nxt()
        self.assertEqual(info["action"], "handoff")
        self.assertIn("#10", info["message"])
        self.assertEqual([r["name"] for r in info["repos"]], ["repo", "lib"])
        self.run_cli("spec", "done", "m")
        self.assertEqual(self.nxt()["action"], "done")

    def test_neighbour_with_empty_gate_is_refused(self):
        self.lib_profile({"gate": {"fast": [], "full": []}})
        self.tasks_done()
        self.on_branch()
        self.gate_both()
        self.assertEqual(self.run_cli("verify", "record", "m").returncode, 2)


class MultiRepoHooks(MultiRepoBase):
    def setUp(self):
        super().setUp()
        profile = json.loads((self.data / "profile.json").read_text())
        profile["related_repos"] = [{"name": "lib", "path": "../lib"}]
        ravend.save_json(self.data / "profile.json", profile)

    def approved(self):
        self.write_multi()
        self.run_cli("spec", "approve", "m")

    def denied(self, path):
        res = self.hook("pre-edit", tool_name="Write", tool_input={"file_path": str(path)})
        return res.stdout if "deny" in res.stdout else ""

    def test_edit_in_an_approved_neighbour_is_allowed_and_uses_its_protected_paths(self):
        self.assertTrue(self.denied(self.lib / "src" / "lib.js"))  # related, no spec yet: read-only
        self.approved()
        self.assertFalse(self.denied(self.lib / "src" / "lib.js"))
        self.assertIn("secret.txt", self.denied(self.lib / "secret.txt"))
        self.assertFalse(self.denied(self.lib / "src" / "new" / "dir" / "x.js"))

    def test_neighbour_outside_the_approved_set_is_denied_only_for_multi_repo_specs(self):
        other = Path(self.tmp.name) / "other"
        make_repo(other)
        self.lib_profile({}, repo=other)
        self.approved()
        self.assertIn("approved repositories", self.denied(other / "src" / "a.js"))
        ravend.spec_file(self.data, "m").unlink()
        self.write_spec()
        self.assertFalse(self.denied(other / "src" / "a.js"))

    def test_neighbours_are_denied_until_the_runtime_approves_the_repo_set(self):
        other = Path(self.tmp.name) / "other"
        make_repo(other)
        self.lib_profile({}, repo=other)
        body = MULTI_SPEC.format(repos="../other").replace("repo: lib", "repo: other")
        self.write_multi(body=body)  # written, not yet approved
        self.assertIn("approved repositories", self.denied(other / "src" / "a.js"))
        ravend.spec_file(self.data, "m").unlink()
        self.write_spec(tier="large", status="draft")
        self.run_cli("spec", "approve", "s")  # an approval without a repo set (single-repo spec)
        path = ravend.spec_file(self.data, "s")
        path.write_text(path.read_text().replace("branch: feat/s\n", "branch: feat/s\nrepos: ../other\n")
                        .replace("— files: src/sum.js — proves: AC1 — deps: T1", "— repo: other — files: src/lib.js — deps: T1"))
        self.assertIn("approved repositories", self.denied(other / "src" / "a.js"))

    def test_stop_still_gates_the_session_repo_when_it_has_no_task(self):
        body = MULTI_SPEC.format(repos="../lib").replace("- [ ] T2: use it — files", "- [ ] T2: use it — repo: lib — files")
        self.write_multi(body=body)
        self.run_cli("spec", "approve", "m")
        self.run_cli("arm", RAVEND_SESSION_ID="s1")
        (self.repo / "src" / "sum.js").write_text("export const sum = (a, b) => a - b;\n")
        self.assertEqual(json.loads(self.hook("stop").stdout).get("decision"), "block")

    def test_post_edit_formats_with_the_neighbours_formatter(self):
        self.lib_profile({"format": [{"glob": "src/*.js", "run": "echo formatted >> {file}"}]})
        self.approved()
        self.hook("post-edit", tool_name="Edit", tool_input={"file_path": str(self.lib / "src" / "lib.js")})
        self.assertIn("formatted", (self.lib / "src" / "lib.js").read_text())

    def test_stop_runs_the_gate_of_each_changed_repo(self):
        self.lib_profile({"gate": {"fast": [{"name": "lint", "run": "false", "when": ["src/*"]}],
                                   "full": [{"name": "t", "run": "true"}]}})
        self.approved()
        self.run_cli("arm", RAVEND_SESSION_ID="s1")
        (self.lib / "src" / "lib.js").write_text("export const one = 3;\n")
        out = json.loads(self.hook("stop").stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("lib", out["reason"])
        shutil.rmtree(self.lib)
        res = self.hook("stop")
        self.assertEqual(res.returncode, 0)
        out = json.loads(res.stdout or "{}")
        self.assertNotEqual(out.get("decision"), "block")
        self.assertIn("not found", out.get("systemMessage", ""))

    def test_session_start_lists_the_spec_repos(self):
        self.approved()
        out = self.hook("session-start").stdout
        self.assertIn(str(self.lib.resolve()), out)
        self.assertIn("/add-dir", out)


if __name__ == "__main__":
    unittest.main()
