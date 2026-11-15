---
name: stack-github-actions
description: "Particularidades de GitHub Actions — actionlint/zizmor, permissions mínimas, OIDC, actions fixadas, environments e concurrency. Nunca dispara workflows nem mexe em secrets. Carregada quando a task mexe em .github/workflows."
---

# GitHub Actions

**Codebase first.** Mirror the existing workflows: job names (they may be required status checks — renaming one breaks branch protection), reusable workflows / composite actions already in the org, runner labels, cache strategy, how environments and OIDC roles are named.

## Never act on the org from here
`gh workflow run|enable|disable`, `gh secret|variable set|delete`, `gh release create` and `gh pr merge` are blocked by Ravend's command guard. A workflow change is proven by **the PR's own CI run** (Ravend follows it after the PR) plus static checks locally.

## Proof levels → tools
| AC `[infra]` proves | Tool (gate step) |
|---|---|
| YAML, expressions, `needs`, shell in `run:` | `actionlint` (runs shellcheck on `run:` blocks when installed) |
| workflow security (injection, permissions, unpinned actions, `pull_request_target`) | `zizmor .github/workflows` when available |
| the workflow actually works | the PR's CI run (`ravend ci`) — or a dry run on a branch where the trigger allows it |

## Rules that prevent incidents
- `permissions:` at workflow or job level, minimal (`contents: read` default; add `id-token: write` only on jobs that assume a cloud role, `pull-requests: write` only where needed).
- Cloud access by OIDC (e.g. `aws-actions/configure-aws-credentials` with `role-to-assume`), one role per environment, trust policy restricted to the repo and the branch/environment — no long-lived access keys in secrets.
- Third-party actions pinned to a full commit SHA (with the version in a comment); first-party `actions/*` at least to a major tag, as the repo already does.
- Untrusted input (`github.event.pull_request.title`, branch names, issue bodies) never interpolated directly in `run:` — pass through `env:` and quote.
- `pull_request_target` and `workflow_run` with checkout of PR code = secret exfiltration risk; avoid.
- Deploy jobs: `environment:` with required reviewers for production, `concurrency: { group: deploy-<env>, cancel-in-progress: false }`; the artifact deployed to production is the same one validated before (same image tag/SHA), never rebuilt.
- Cache keys include the lockfile hash; never cache directories with secrets.
- Long jobs: `timeout-minutes` set; matrix `fail-fast` decided explicitly.

## Gate steps (profile.json)
```json
"fast": [{"name": "actionlint", "run": "actionlint", "when": [".github/workflows/*"]}],
"full": [{"name": "actionlint", "run": "actionlint"},
         {"name": "zizmor", "run": "zizmor --min-severity medium .github/workflows", "when": [".github/workflows/*"]}]
```
