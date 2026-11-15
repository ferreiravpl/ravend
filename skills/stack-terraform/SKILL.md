---
name: stack-terraform
description: "Particularidades de Terraform/AWS para implementar e testar — validate, tflint, checkov, terraform test com mocks, plan como evidência, moved/import em vez de mexer no state. Nunca aplica. Carregada quando a task mexe em .tf."
---

# Terraform

**Codebase first.** Mirror the repo's layout (root modules per layer/environment, shared `modules/`, naming and tagging locals, backend config) and its pinned versions (`required_version`, `required_providers`, `.terraform.lock.hcl`). Confirm resource arguments for the pinned provider version with the `docs` integration (AWS docs / Context7) — argument names change between major versions.

## Never mutate real infrastructure
`apply`, `destroy`, `import` (CLI), `state rm|mv|push`, `taint` and `force-unlock` are blocked by Ravend's command guard. Changes reach real accounts only through PR → CI. Need a state change? Express it in code: `moved {}` (rename/refactor), `import {}` (adopt an existing resource, TF ≥ 1.5), `removed {}` (stop managing, TF ≥ 1.7).

## Proof levels → tools
| AC `[infra]` proves | Tool (gate step) |
|---|---|
| syntax/format | `terraform fmt -check -recursive` · `terraform init -backend=false && terraform validate` (per root module) |
| rules and provider errors | `tflint --recursive` (with the AWS ruleset when the repo configures it) |
| security/compliance | `checkov -d <dir> --quiet` or `trivy config <dir>` — whichever the repo/CI uses |
| behavior of a module | `terraform test` with `.tftest.hcl` files: `command = plan`, `mock_provider "aws" {}` (TF ≥ 1.7), `assert { condition = … }` on planned values — no credentials needed |
| what changes in a real environment | `terraform plan` in CI (or locally with read-only credentials if the developer has them) — the plan output is the evidence in the PR, not an apply |
Snippets: [references/testing.md](references/testing.md).

## Review the plan, not only the code
Every `-/+` (replace) or `destroy` of an existing resource is a finding unless the spec asks for it. Typical causes: renamed resource/module without `moved`, changed `name`/`identifier`/`availability_zone`, changed `for_each` keys, `count` → `for_each`.

## AWS pitfalls that cause real incidents
- Stateful resources (RDS, S3 with data, DynamoDB, KMS keys, ElastiCache): `lifecycle { prevent_destroy = true }` plus the service's own protection (`deletion_protection`, `skip_final_snapshot = false`, versioning). Never remove them in a refactor.
- S3: block public access, encryption and versioning on by default; bucket policies scoped by prefix/role.
- IAM: least privilege — resource ARNs of this environment, no `"*"` action/resource without a written reason; workloads assume roles (IRSA/pod identity, OIDC for CI) instead of access keys.
- SQS/SNS: DLQ with `maxReceiveCount` on every consumer queue; consumer visibility timeout > handler timeout; SNS → SQS subscriptions need the queue policy and `raw_message_delivery` decided explicitly; filter policies for versioned events.
- Names and tags carry the environment (`<project>-<env>-…`); one environment can never read another's secrets/queues.
- Secrets never in `.tf`/`.tfvars` committed to git — reference Secrets Manager/SSM; mark outputs `sensitive = true`.
- Provider lock for every platform the team and CI use: `terraform providers lock -platform=linux_amd64 -platform=darwin_arm64`.

## Commands
- Per root module: `terraform -chdir=<dir> init -backend=false -input=false` then `validate` (no state access).
- `terraform test -chdir=<module>` · `terraform fmt -recursive` (formatting is safe; it only rewrites files).
