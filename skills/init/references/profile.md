# profile.json reference

Location: `<data_dir>/profile.json` (local to the developer, never committed). Read by `scripts/ravend.py` (gate, hooks, app) and `scripts/ravend_run.py` (headless).

```jsonc
{
  "version": 1,
  "stacks": ["spring", "angular"],                 // informational, shown at session start
  "modules": [{"path": "backend", "stack": "spring"}, {"path": "frontend", "stack": "angular"}],
  "git": {
    "base_branch": "main",                          // default: origin/HEAD, then main/master/develop
    "branch_prefix": "feat/",
    "commit_per_task": true                         // /ravend:build commits after each green task
  },
  "format": [                                       // PostToolUse: first matching rule runs on the edited file
    {"glob": "frontend/*.ts", "cwd": "frontend", "run": "npx prettier --write {file}", "timeout": 30}
  ],
  "protected_paths": [".env", ".env.*.local", "*.pem", "*.key", "frontend/src/generated/*"],
  "app": [                                          // object or list; started for steps with needs_app
    {"name": "api", "cwd": "backend", "start": "./mvnw -q spring-boot:run -Dspring-boot.run.profiles=local",
     "healthcheck": "http://localhost:8080/actuator/health", "timeout": 180}
  ],
  "gate": {
    "tail_lines": 60,                               // lines of output shown per failing step
    "max_stop_blocks": 3,                           // Stop hook gives up (asks for a human) after N blocks
    "fast": [ /* steps */ ],
    "full": [ /* steps */ ]
  },
  "headless": {"allowed_tools": ["Bash(docker compose *)"]}
}
```

## Step fields
| field | meaning |
|---|---|
| `name` | label in reports and log file name |
| `run` | shell command; placeholders below |
| `cwd` | directory relative to repo root (default `.`) |
| `when` | glob(s) over **repo-relative** changed paths; step is skipped if none match. `*` crosses `/` |
| `files_glob` | extra filter applied to `{files}` (relative to `cwd`), e.g. `*.ts` |
| `timeout` | seconds (default 900) |
| `needs_app` | start `app` before this step (stopped at the end of the gate) |
| `continue_on_fail` | keep running later steps after a failure (default: stop at first failure) |

Placeholders (a step whose placeholder resolves empty is skipped):
- `{files}` — changed files that still exist, matching `when`/`files_glob`, relative to `cwd`, shell-quoted.
- `{java_tests}` — comma list for Surefire `-Dtest`: changed test classes + `<Class>*Test` for changed main classes.
- `{gradle_tests}` — the same as repeated `--tests <pattern>` flags.
- `{base}` — base branch (for diff-aware tools like diff-cover).

Changed files: fast = working tree vs HEAD + untracked; full = everything since `merge-base(HEAD, base)` + working tree.

## Examples

### Spring Boot, Maven, single module at repo root
```json
"format": [],
"gate": {
  "fast": [
    {"name": "format", "run": "./mvnw -q spotless:apply", "when": ["*.java"]},
    {"name": "compile", "run": "./mvnw -q test-compile", "when": ["*.java", "pom.xml", "src/main/resources/*"]},
    {"name": "unit", "run": "./mvnw -q surefire:test -Dtest={java_tests} -Dsurefire.failIfNoSpecifiedTests=false", "when": ["*.java"]}
  ],
  "full": [
    {"name": "verify", "run": "./mvnw -q verify", "timeout": 1800},
    {"name": "checkstyle", "run": "./mvnw -q checkstyle:check"}
  ]
}
```
Drop `format`/`checkstyle` if the repo has no spotless/checkstyle. `verify` runs Failsafe ITs (Testcontainers) and JaCoCo checks when configured. Multi-module: run from root with `-pl <module> -am`.

### Quarkus, Gradle
```json
"gate": {
  "fast": [
    {"name": "compile", "run": "./gradlew -q compileTestJava", "when": ["*.java", "*.gradle*"]},
    {"name": "unit", "run": "./gradlew -q test {gradle_tests}", "when": ["*.java"]}
  ],
  "full": [{"name": "build", "run": "./gradlew -q build", "timeout": 1800}]
}
```
`@QuarkusTest` uses Dev Services (Docker) for databases — make sure Docker is running before gate full.

### Angular (npm, Vitest or Karma)
```json
"format": [{"glob": "web/*.ts", "cwd": "web", "run": "npx prettier --write {file}"},
           {"glob": "web/*.html", "cwd": "web", "run": "npx prettier --write {file}"}],
"gate": {
  "fast": [
    {"name": "typecheck", "cwd": "web", "run": "npx tsc -p tsconfig.app.json --noEmit", "when": ["web/*.ts"]},
    {"name": "lint", "cwd": "web", "run": "npx eslint {files}", "when": ["web/*"], "files_glob": "*.ts"},
    {"name": "unit", "cwd": "web", "run": "npx ng test --watch=false", "when": ["web/*"]}
  ],
  "full": [
    {"name": "build", "cwd": "web", "run": "npm run build"},
    {"name": "unit", "cwd": "web", "run": "npx ng test --watch=false"},
    {"name": "e2e", "cwd": "web", "run": "npx playwright test", "when": ["web/*"]}
  ]
}
```
Karma projects need a headless browser: `npx ng test --watch=false --browsers=ChromeHeadless`. If `playwright.config.ts` has a `webServer` entry it starts the dev server itself (no `needs_app`); use `needs_app` only when the backend must be up too.

### React + Vite (Vitest)
```json
"format": [{"glob": "web/src/*", "cwd": "web", "run": "npx prettier --write {file}"}],
"gate": {
  "fast": [
    {"name": "typecheck", "cwd": "web", "run": "npx tsc -b", "when": ["web/*.ts", "web/*.tsx"]},
    {"name": "lint", "cwd": "web", "run": "npx eslint {files}", "when": ["web/*"], "files_glob": "*.ts*"},
    {"name": "unit", "cwd": "web", "run": "npx vitest related {files} --run", "when": ["web/src/*"]}
  ],
  "full": [
    {"name": "build", "cwd": "web", "run": "npm run build"},
    {"name": "unit", "cwd": "web", "run": "npx vitest run"},
    {"name": "e2e", "cwd": "web", "run": "npx playwright test"}
  ]
}
```
Jest instead of Vitest: `npx jest --findRelatedTests {files}` (fast) / `npx jest` (full).

### Optional depth steps (gate.full)
- Diff coverage (Java): `./mvnw -q verify jacoco:report && diff-cover target/site/jacoco/jacoco.xml --compare-branch={base} --fail-under=80`
- Mutation (Java, PIT): `./mvnw -q org.pitest:pitest-maven:mutationCoverage -DtargetClasses=<pkg>.*` (slow — large tier only)
- Mutation (TS, Stryker): `npx stryker run --mutate {files}` with `files_glob: "src/*.ts"`
