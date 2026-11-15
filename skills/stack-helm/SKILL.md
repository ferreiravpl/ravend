---
name: stack-helm
description: "Particularidades de Helm/Kubernetes para implementar e testar — lint, template + kubeconform, helm-unittest, probes, recursos e upgrades seguros. Nunca faz deploy. Carregada quando a task mexe num chart."
---

# Helm / Kubernetes

**Codebase first.** Mirror the chart's structure (`_helpers.tpl` names and labels, how values are split per environment, how the base/library chart is consumed) and the Kubernetes version the cluster runs (API versions and deprecations follow it).

## Never touch a live cluster
`helm install|upgrade|uninstall|rollback` and mutating `kubectl` (`apply`, `delete`, `patch`, `scale`, `rollout restart`…) are blocked by Ravend's command guard. Read-only inspection (`kubectl get/describe/logs`, `helm get values`, `helm history`) is fine when the developer has access. Deploys happen through CI.

## Proof levels → tools
| AC `[infra]` proves | Tool (gate step) |
|---|---|
| chart renders and follows conventions | `helm lint <chart> -f <chart>/values-<env>.yaml` for each env file |
| manifests are valid for the cluster version | `helm template <name> <chart> -f values-<env>.yaml \| kubeconform -strict -summary -kubernetes-version <x.y.z> -ignore-missing-schemas` |
| template logic (conditionals, defaults, per-env values) | `helm unittest <chart>` (helm-unittest plugin) when the repo uses it — assert on rendered fields |
| policy (security context, limits, labels) | the repo's policy tool if any (`conftest`, `kyverno test`, `checkov -d`), else assertions in helm-unittest |
Snippets: [references/testing.md](references/testing.md).

## Checklist for workload changes
- `resources.requests` and `limits` on every container; memory limit ≥ request.
- Probes: readiness checks only the dependencies on the request's critical path; liveness checks the process itself (never a database or another service), with `initialDelaySeconds`/`startupProbe` for slow starts (native images start fast, JVM ones do not).
- Pod security: `runAsNonRoot`, `readOnlyRootFilesystem` where possible, drop `ALL` capabilities, no privileged/hostPath.
- Upgrades: changing a Deployment's `selector` labels or a StatefulSet's `volumeClaimTemplates` fails on upgrade — flag it. Renaming a resource deletes the old one.
- Config and secrets: values reference secrets managed outside the chart (External Secrets/CSI); never put secret values in `values*.yaml`.
- Every environment-specific value lives in `values-<env>.yaml`; templates have no environment `if`s beyond what the repo already does.
