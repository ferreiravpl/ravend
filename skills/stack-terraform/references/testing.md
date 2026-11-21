# Terraform testing snippets

## `terraform test` with a mocked AWS provider (no credentials, TF ≥ 1.7)
`modules/queue/tests/queue.tftest.hcl`:
```hcl
mock_provider "aws" {}

variables {
  name        = "orders"
  environment = "staging"
}

run "consumer_queue_has_a_dlq" {
  command = plan

  assert {
    condition     = jsondecode(aws_sqs_queue.main.redrive_policy).maxReceiveCount == 10
    error_message = "consumer queue must redrive to the DLQ after 10 receives"
  }

  assert {
    condition     = startswith(aws_sqs_queue.main.name, "orders-staging")
    error_message = "queue name must carry the environment"
  }
}

run "rejects_unknown_environment" {
  command = plan
  variables { environment = "qa" }
  expect_failures = [var.environment]     # validation block on the variable
}
```
Values only known after apply (ARNs, ids) are unknown in `plan` with a mock — assert on inputs and derived attributes, or give the mock `override_resource { values = {...} }`.

## Gate steps (profile.json)
```json
"fast": [
  {"name": "fmt", "run": "terraform fmt -check -recursive", "when": ["*.tf", "*.tfvars", "*.tftest.hcl"]},
  {"name": "validate", "cwd": "envs/staging", "run": "terraform init -backend=false -input=false >/dev/null && terraform validate", "when": ["*.tf"]}
],
"full": [
  {"name": "fmt", "run": "terraform fmt -check -recursive"},
  {"name": "tflint", "run": "tflint --recursive"},
  {"name": "test", "cwd": "modules/queue", "run": "terraform init -backend=false -input=false >/dev/null && terraform test"},
  {"name": "checkov", "run": "checkov -d . --quiet --compact"}
]
```
One `validate`/`test` step per root module or module with tests (copy the step and change `cwd`).

## Reading a plan for review
```bash
terraform plan -out tf.plan -input=false -lock=false     # read-only credentials; never in the gate by default
terraform show -json tf.plan | jq -r '.resource_changes[] | select(.change.actions != ["no-op"]) | "\(.change.actions|join("/")) \(.address)"'
```
`delete/create` or `delete` on a stateful resource = stop and ask.
