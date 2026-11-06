#!/usr/bin/env python3
"""ravend auto — o pipeline inteiro sem supervisão: spec → build → verify → review → (PR).

Uso (dentro do repositório, depois do /ravend:init):
    ravend auto "Adicionar paginação em GET /products"   para no review; pausa antes do build se a spec for large
    ravend auto PROJ-123 --pr                             vai até abrir o PR
    ravend auto "#45" --no-pause --pr                     sem pausa para aprovar a spec large
    ravend auto --resume add-products-pagination --pr     continua uma spec que você já aprovou

O trabalho acontece sempre num git worktree irmão (../<repo>-<slug>), na branch da feature: a sua pasta
fica livre e várias demandas podem rodar em paralelo. O próximo passo de cada volta é decidido por
`ravend.py next` (a mesma máquina de estados do /ravend:continue); o gate full é rodado por este script,
nunca pelo modelo. Os MCPs escolhidos no /ravend:init são liberados só nas etapas do papel deles.

Códigos de saída: 0 concluído ou pausado de propósito · 1 erro inesperado · 2 configuração faltando ·
3 precisa de você (pergunta em aberto, correção que não converge, etapa bloqueada).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ravend_lib as ravend  # noqa: E402

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
SHIP_SCHEMA = {"type": "object", "properties": {"pr_url": {"type": "string"}, "blocked": {"type": "string"}},
               "required": ["pr_url"]}


def command_patterns(cmd: str) -> list[str]:
    """Bash permissions for one gate/app command: the command itself, and the same command with extra
    arguments (narrowest test runs). Text from the first placeholder on becomes the wildcard, so
    `npx eslint {files}` allows `npx eslint …`, never every `npx`."""
    cmd = " ".join(cmd.split())
    fixed = cmd.split("{", 1)[0].strip()
    if not fixed:
        return []
    return [f"Bash({fixed} *)"] if "{" in cmd else [f"Bash({fixed})", f"Bash({fixed} *)"]


class Runner:
    def __init__(self, args: argparse.Namespace, root: Path):
        self.args, self.root, self.cwd = args, root, root
        self.profile = ravend.load_profile(root) or {}
        self.data = ravend.data_dir(root)
        self.log_dir = self.data / "runs" / f"auto-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.cost = 0.0
        self.calls = 0
        # the skills must match this runtime: load this checkout unless it IS the installed plugin
        self.plugin_dir = None if self._installed_here() else str(ravend.PLUGIN_ROOT)
        self.mcp_config: str | None = None
        self.resources = ExitStack()

    # ------------------------------------------------------------------ helpers
    def say(self, msg: str) -> None:
        print(f"[ravend auto] {msg}", flush=True)

    @staticmethod
    def _installed_here() -> bool:
        cfg = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        data = ravend.load_json(cfg / "plugins" / "installed_plugins.json", {}) or {}
        for key, entries in (data.get("plugins") or {}).items():
            if key.split("@")[0] == "ravend":
                for entry in entries or []:
                    try:
                        if Path(entry.get("installPath", "")).resolve() == ravend.PLUGIN_ROOT.resolve():
                            return True
                    except OSError:
                        continue
        return False

    def allowed_tools(self, stage: str = "build") -> list[str]:
        role_stage = {"fix-verify": "build", "fix-review": "build"}.get(stage, stage)
        tools = ["Read", "Edit", "Write", "MultiEdit", "Glob", "Grep", "Skill", "Agent", "TodoWrite",
                 "Bash(git *)", f"Bash(python3 {ravend.PLUGIN_ROOT}/scripts/ravend.py *)", "Bash(mkdir *)"]
        tools += ravend.integration_tools(self.profile, role_stage)
        if role_stage == "verify" and "browser" not in ravend.integrations(self.profile):
            tools.append("mcp__playwright")  # the server /ravend:init suggests when no browser MCP was chosen
        commands = [s.get("run", "") for mode in ("fast", "full") for s in (self.profile.get("gate") or {}).get(mode, [])]
        commands += [a.get("start", "") for a in ravend._apps(self.profile)]
        tools += [pattern for cmd in commands for pattern in command_patterns(cmd)]
        tools += (self.profile.get("headless") or {}).get("allowed_tools", [])
        if role_stage == "ship":
            tools.append("Bash(gh *)")
        return list(dict.fromkeys(tools))

    def claude(self, stage: str, prompt: str, schema: dict) -> dict:
        cmd = ["claude", "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(schema),
               "--permission-mode", self.args.permission_mode, "--allowedTools", *self.allowed_tools(stage)]
        if self.mcp_config:
            cmd += ["--mcp-config", self.mcp_config]
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
            raise SystemExit(self.fail(f"{stage}: o claude não devolveu JSON (exit {proc.returncode}); veja {raw_path}"))
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
            raise SystemExit(self.fail(f"{stage}: resposta sem o JSON esperado; veja {raw_path}"))
        return out

    def gate_full(self) -> bool:
        self.say("gate full: rodado por este script, fora do modelo")
        code = subprocess.run([sys.executable, str(ravend.PLUGIN_ROOT / "scripts" / "ravend.py"), "gate", "full"],
                              cwd=self.cwd).returncode
        if code == 2:
            raise SystemExit(self.fail("gate mal configurado no profile.json — corrija com /ravend:init", 2))
        return code == 0

    def fail(self, msg: str, code: int = 1) -> int:
        self.say(f"PAROU: {msg}")
        self.summary()
        return code

    def summary(self) -> None:
        self.say(f"chamadas={self.calls} custo≈US${self.cost:.2f} logs={self.log_dir}")

    def worktree(self, slug: str) -> None:
        git_cfg = self.profile.get("git") or {}
        branch = f"{git_cfg.get('branch_prefix', 'feat/')}{slug}"
        path = self.root.parent / f"{self.root.name}-{slug}"
        if not path.exists():
            base = ravend.base_branch(self.root, self.profile)
            exists = ravend.git(["rev-parse", "--verify", "--quiet", branch], self.root) is not None
            args = ["worktree", "add", str(path), branch] if exists else ["worktree", "add", "-b", branch, str(path), base]
            if ravend.git(args, self.root) is None:
                raise SystemExit(self.fail(f"não foi possível criar o worktree {path}", 2))
        self.cwd = path
        self.say(f"worktree: {path} (branch {branch})")
        # local-scope MCP servers are registered for the main checkout's path only; bring them along
        local = ravend.local_mcp_config(self.root)
        if local:
            tmp = self.resources.enter_context(tempfile.TemporaryDirectory(prefix="ravend-mcp-"))
            cfg = Path(tmp) / "mcp.json"  # may hold tokens: private temp dir, removed when the run ends
            cfg.write_text(json.dumps({"mcpServers": local}), encoding="utf-8")
            cfg.chmod(0o600)
            self.mcp_config = str(cfg)
            self.say(f"worktree: repassando {len(local)} MCP(s) de escopo local: {', '.join(sorted(local))}")

    # ------------------------------------------------------------------ pipeline
    def run(self) -> int:
        try:
            return self._run()
        finally:
            self.resources.close()

    def lock_checkout(self) -> bool:
        """One unattended run per checkout: two runs in the same working tree would mix branches and edits."""
        held = self.resources.enter_context(ravend.file_lock(ravend.state_dir(self.cwd) / "run.lock", blocking=False))
        return bool(held)

    def _run(self) -> int:
        a = self.args
        if not self.profile:
            return self.fail("este repositório não tem perfil — rode /ravend:init uma vez (interativo)", 2)
        flags = " --headless" + (" --approved" if a.no_pause or a.resume else "")
        if a.resume:
            slug = a.resume
            if not ravend.spec_file(self.data, slug).exists():
                return self.fail(f"spec não encontrada: {ravend.spec_file(self.data, slug)}", 2)
        else:
            out = self.claude("spec", f"/ravend:spec{flags} {a.demand}", SPEC_SCHEMA)
            slug, tier = out.get("slug") or ravend._slug(a.demand)[:40], out["tier"]
            self.say(f"spec: {slug} (tier {tier}) {out.get('spec_path', '')}")
            if out.get("blocking_questions"):
                for q in out["blocking_questions"]:
                    self.say(f"  ? {q}")
                return self.fail("a spec tem perguntas em aberto — responda na spec e rode de novo com --resume", 3)
            if tier == "trivial":
                return self.trivial(slug, flags)
            if tier == "large" and not a.no_pause:
                self.say(f"pausa: revise a spec e continue com: ravend auto --resume {slug}" + (" --pr" if a.pr else ""))
                self.summary()
                return 0
        self.worktree(slug)
        if not self.lock_checkout():
            return self.fail(f"já existe um `ravend auto` trabalhando em {self.cwd}", 2)
        previous = None
        for _ in range(40):
            info = ravend.next_action(self.cwd, slug)
            action = info["action"]
            self.say(f"próximo: {action} — {info['message']}")
            key = (action, info.get("task"), info.get("fix"), info.get("message"))
            if action in ("build", "fix") and key == previous:
                return self.fail(f"a etapa {action} não avançou o estado ({info['message']})", 3)
            previous = key
            if action == "approve":
                if not (a.no_pause or a.resume):
                    self.say(f"pausa: aprove a spec e continue com: ravend auto --resume {slug}")
                    self.summary()
                    return 0
                ravend.set_spec_status(self.data, slug, "approved", "aprovada (ravend auto)")
            elif action == "answer":
                for q in info.get("questions", []):
                    self.say(f"  ? {q}")
                return self.fail("a spec tem perguntas em aberto", 3)
            elif action in ("build", "fix"):
                stage = "build" if action == "build" else f"fix-{info.get('fix')}"
                out = self.claude(stage, f"/ravend:build {slug}{flags}", BUILD_SCHEMA)
                if out["status"] == "blocked":
                    for b in out.get("blockers", []):
                        self.say(f"  ! {b}")
                    return self.fail(f"{stage} bloqueado", 3)
            elif action == "verify":
                out = self.claude("verify", f"/ravend:verify {slug}{flags}", VERIFY_SCHEMA)
                self.gate_full()
                entry = ravend.record_verify(self.cwd, slug, out.get("uncovered_criteria") or [])
                self.say(f"verify: gate {entry['gate']}, {len(entry['uncovered'])} critério(s) sem teste")
            elif action == "review":
                before = ravend.spec_state(self.data, slug)["reviews"]
                out = self.claude("review", f"/ravend:review {slug}{flags}", REVIEW_SCHEMA)
                st = ravend.spec_state(self.data, slug)
                last = st["reviews"][-1] if st["reviews"] else None
                if not last or last.get("fingerprint") != ravend.tree_fingerprint(self.cwd):
                    # the skill could not record it on this code: record it here, keeping the reviewer's full
                    # findings when the skill managed to store them during this stage
                    fresh = last and last.get("raw") and (len(st["reviews"]) > len(before) or last != (before or [None])[-1])
                    ravend.record_review(self.cwd, slug, last["raw"] if fresh else out)
                last = ravend.spec_state(self.data, slug)["reviews"][-1]
                self.say(f"review {last['n']}: {last['verdict']} · {len(last['blocking'])} P0/P1")
            elif action == "ship":
                if not a.pr:
                    self.say(f"pronto para PR na branch do worktree {self.cwd}. Abra com /ravend:ship {slug} "
                             f"ou rode de novo com --resume {slug} --pr")
                    self.summary()
                    return 0
                out = self.claude("ship", f"/ravend:ship {slug}{flags} --yes", SHIP_SCHEMA)
                if not out.get("pr_url"):
                    return self.fail(f"o ship não abriu o PR: {out.get('blocked') or 'sem motivo informado'}", 3)
                self.say(f"PR: {out['pr_url']}")
                if ravend.next_action(self.cwd, slug)["action"] != "done":
                    ravend.set_spec_status(self.data, slug, "done", f"PR {out['pr_url']}")
                self.summary()
                return 0
            elif action == "human":
                for b in info.get("blocking", []):
                    self.say(f"  ! {b}")
                return self.fail(info["message"], 3)
            elif action == "done":
                self.summary()
                return 0
            else:
                return self.fail(info["message"], 2)
        return self.fail("limite de etapas atingido sem concluir", 3)

    def trivial(self, slug: str, flags: str) -> int:
        """Trivial change: no spec, no review — implement in a worktree and prove it with the gate."""
        self.worktree(slug)
        if not self.lock_checkout():
            return self.fail(f"já existe um `ravend auto` trabalhando em {self.cwd}", 2)
        out = self.claude("build", f"/ravend:build {self.args.demand}{flags}", BUILD_SCHEMA)
        if out["status"] == "blocked":
            return self.fail("build bloqueado: " + "; ".join(out.get("blockers", [])), 3)
        if not self.gate_full():
            return self.fail("gate full vermelho na mudança trivial", 3)
        self.say(f"mudança trivial pronta e verde na branch do worktree {self.cwd}")
        self.summary()
        return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="ravend auto", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("demand", nargs="?", help="texto, chave do Jira (PROJ-123) ou issue do GitHub (#45 ou URL)")
    p.add_argument("--resume", metavar="SLUG", help="continuar uma spec existente (considerada aprovada)")
    p.add_argument("--pr", action="store_true", help="ir até abrir o PR (sem isso, para quando estiver pronto para PR)")
    p.add_argument("--no-pause", action="store_true", help="não pausar para você aprovar uma spec large")
    p.add_argument("--budget-usd", type=float, help="gasto máximo por chamada ao Claude (--max-budget-usd)")
    p.add_argument("--model", help="modelo usado em todas as etapas (padrão: o do seu Claude Code)")
    p.add_argument("--permission-mode", default="acceptEdits",
                   help="modo de permissão do Claude (acceptEdits; bypassPermissions só em sandbox/container)")
    p.add_argument("--claude-arg", action="append", help="argumento extra repassado ao claude (repetível)")
    args = p.parse_args()
    if not args.demand and not args.resume:
        p.error("informe uma demanda ou --resume <slug>")
    if not shutil.which("claude"):
        print("o comando `claude` não está no PATH", file=sys.stderr)
        return 2
    root = ravend.repo_root(Path.cwd())
    if not root:
        print("rode dentro de um repositório git", file=sys.stderr)
        return 2
    return Runner(args, root).run()


if __name__ == "__main__":
    sys.exit(main())
