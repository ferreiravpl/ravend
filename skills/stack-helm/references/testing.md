# Helm testing snippets

## helm-unittest (`<chart>/tests/deployment_test.yaml`)
```yaml
suite: deployment
templates: [templates/deployment.yaml]
tests:
  - it: sets requests and limits from values            # AC2 [infra]
    set:
      resources.requests.memory: 256Mi
      resources.limits.memory: 512Mi
    asserts:
      - equal: {path: spec.template.spec.containers[0].resources.limits.memory, value: 512Mi}
  - it: liveness does not depend on external services
    asserts:
      - equal: {path: spec.template.spec.containers[0].livenessProbe.httpGet.path, value: /q/health/live}
  - it: staging values keep a single replica
    values: [../values-staging.yaml]
    asserts:
      - equal: {path: spec.replicas, value: 1}
```

## Gate steps (profile.json)
```json
"fast": [
  {"name": "helm-lint", "run": "helm lint chart -f chart/values-staging.yaml", "when": ["chart/*"]}
],
"full": [
  {"name": "helm-lint", "run": "helm lint chart -f chart/values-staging.yaml && helm lint chart -f chart/values-prod.yaml"},
  {"name": "kubeconform", "run": "helm template app chart -f chart/values-prod.yaml | kubeconform -strict -summary -ignore-missing-schemas"},
  {"name": "helm-unittest", "run": "helm unittest chart"}
]
```
