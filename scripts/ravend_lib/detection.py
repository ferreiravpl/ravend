"""Stack/tooling detection used by /ravend:init to propose gate commands."""
from __future__ import annotations

import os
from pathlib import Path

from .core import SKIP_DIRS, _read, load_json

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
    return {"root": str(root), "modules": found, "stacks": sorted({m["stack"] for m in found}),
            "docker_compose": compose, "has_claude_md": (root / "CLAUDE.md").exists()}
