"""Stack/tooling detection used by /ravend:init to propose gate commands."""
from __future__ import annotations

import os
import re
from pathlib import Path

from .core import SKIP_DIRS, _read, load_json, project_id, ravend_home

# --------------------------------------------------------------------------- detection

def detect(root: Path) -> dict:
    found: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirnames[:] = [x for x in dirnames if x not in SKIP_DIRS and not x.startswith(".")]
        if len(rel.parts) > 3:
            dirnames[:] = []
            continue
        names = set(filenames)
        mod: dict = {"path": str(rel) if str(rel) != "." else "."}
        if any(n.endswith(".tf") for n in names):
            mod.update({"stack": "terraform", "build": "terragrunt" if "terragrunt.hcl" in names else "terraform",
                        "signals": [s for s, hit in (("tflint", ".tflint.hcl" in names),
                                                     ("terraform-test", any(n.endswith(".tftest.hcl") for n in names)),
                                                     ("lockfile", ".terraform.lock.hcl" in names)) if hit]})
            found.append(mod)
            continue
        if "Chart.yaml" in names:
            mod.update({"stack": "helm", "build": "helm",
                        "signals": [s for s, hit in (("values-per-env", any(re.match(r"values-.+\.ya?ml$", n) for n in names)),
                                                     ("chart-tests", (Path(dirpath) / "templates" / "tests").is_dir()),
                                                     ("unittest", (Path(dirpath) / "tests").is_dir())) if hit]})
            found.append(mod)
            dirnames[:] = []
            continue
        build_file = next((n for n in ("pom.xml", "build.gradle.kts", "build.gradle") if n in names), None)
        if build_file:
            text = _read(Path(dirpath) / build_file)
            mod["build"] = "maven" if build_file == "pom.xml" else "gradle"
            mod["wrapper"] = ("mvnw" in names) if build_file == "pom.xml" else ("gradlew" in names)
            mod["stack"] = "quarkus" if "io.quarkus" in text else ("spring" if "spring-boot" in text else "java")
            mod["signals"] = [s for s, k in (("testcontainers", "testcontainers"), ("spotless", "spotless"),
                              ("checkstyle", "checkstyle"), ("jacoco", "jacoco"), ("pitest", "pitest"),
                              ("springdoc", "springdoc"), ("smallrye-openapi", "smallrye-openapi"),
                              ("archunit", "archunit"), ("lombok", "lombok")) if k in text]
            is_root_aggregator = "<modules>" in text
            if not is_root_aggregator or rel == Path("."):
                found.append(mod)
            continue
        if "package.json" in names:
            pkg = load_json(Path(dirpath) / "package.json", {}) or {}
            deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
            stack = "angular" if "@angular/core" in deps else ("react" if "react" in deps else
                    ("vue" if "vue" in deps else "node"))
            mod.update({
                "build": "pnpm" if "pnpm-lock.yaml" in names else "yarn" if "yarn.lock" in names
                else "bun" if ("bun.lockb" in names or "bun.lock" in names) else "npm",
                "stack": stack,
                "versions": {k: deps[k] for k in ("@angular/core", "react", "vite", "typescript", "next") if k in deps},
                "scripts": sorted((pkg.get("scripts") or {}).keys()),
                "test_runner": next((t for t in ("vitest", "jest", "karma", "@playwright/test") if t in deps), None),
                "signals": [s for s in ("@playwright/test", "eslint", "prettier", "@biomejs/biome", "msw",
                                        "@testing-library/react", "@stryker-mutator/core", "tailwindcss")
                            if s in deps],
            })
            if any(n.startswith("playwright.config") for n in names):
                mod["signals"].append("playwright.config")
            found.append(mod)
    compose = [str(p.relative_to(root)) for p in root.glob("*compose*.y*ml")]
    workflows = ci_workflows(root)
    stacks = {m["stack"] for m in found} | ({"github-actions"} if workflows else set())
    return {"root": str(root), "modules": found, "stacks": sorted(stacks), "docker_compose": compose,
            "ci": {"provider": "github-actions", "workflows": workflows} if workflows else None,
            "siblings": sibling_repos(root), "has_claude_md": (root / "CLAUDE.md").exists()}


# --------------------------------------------------------------------------- CI workflows
# A minimal reader for `run:` steps of GitHub Actions workflows (no YAML dependency): single-line `run: cmd`
# and block scalars `run: |` / `run: >`. Good enough to compare what CI runs with the local gate.

RUN_RE = re.compile(r"^(?P<indent>\s*)(?:-\s+)?run:\s*(?P<value>.*)$")


def workflow_runs(text: str) -> list[str]:
    lines, cmds, i = text.splitlines(), [], 0
    while i < len(lines):
        m = RUN_RE.match(lines[i])
        if not m:
            i += 1
            continue
        key_col = lines[i].index("run:")
        value = m.group("value").strip()
        i += 1
        if value and value[0] not in "|>":
            cmds.append(value.strip("'\""))
            continue
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > key_col):
            line = lines[i].strip()
            if line and not line.startswith("#"):
                cmds.append(line)
            i += 1
    joined: list[str] = []
    for c in cmds:  # shell line continuations
        if joined and joined[-1].endswith("\\"):
            joined[-1] = joined[-1][:-1].rstrip() + " " + c
        else:
            joined.append(c)
    return joined


def ci_workflows(root: Path) -> list[dict]:
    out = []
    for wf in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        text = _read(wf)
        uses = sorted(set(re.findall(r"uses:\s*([\w.-]+/[\w.-]+)", text)))
        out.append({"file": str(wf.relative_to(root)), "runs": workflow_runs(text), "uses": uses})
    return out


def sibling_repos(root: Path) -> list[dict]:
    """Other git repos next to this one (same parent folder), and whether this developer already configured
    Ravend there — /ravend:init offers to start from a sibling's profile and to mark siblings as related."""
    out = []
    try:
        candidates = sorted(p for p in root.parent.iterdir() if p.is_dir() and p != root and (p / ".git").exists())
    except OSError:
        return out
    for path in candidates[:40]:
        pid = project_id(path)
        profile = load_json(ravend_home() / "projects" / pid / "profile.json")
        out.append({"path": str(path), "name": path.name, "project_id": pid, "has_profile": bool(profile),
                    "stacks": (profile or {}).get("stacks", [])})
    return out
