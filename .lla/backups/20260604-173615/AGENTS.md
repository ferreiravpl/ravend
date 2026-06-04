# LLA SDD Orchestrator

This repository is an OpenCode-first software development orchestrator.

## Mission

Drive software work through an SDD workflow by default:

intake -> PRD -> tech spec -> task decomposition -> implementation -> QA -> code review -> loop until accepted

## Important operating rules

- SDD is the default path, but agents may be invoked independently when the user already has an approved plan or needs only QA or review.
- Never force PRD and tech spec when the task is already sufficiently bounded and the user explicitly asks for implementation, QA, or review only.
- Persist important state to `.lla/sdd/current/` instead of relying on long conversational memory.
- Prefer loading skills on demand instead of embedding large static instructions in agent prompts.
- Prefer compact, scoped context over broad repository-wide dumps.
- Use `.lla/manifests/*.json` for machine-readable task scope, file scope, and handoff metadata.
- Use `.lla/knowledge/` as incremental memory. Do not load the entire knowledge base by default.
- Load only relevant knowledge entries by stack, layer, issue type, or agent role.
- Reviewer findings that represent reusable lessons should be distilled into compact knowledge entries and indexed.
- Reviewer and QA are allowed to reject implementation and require another iteration.
- Acceptance occurs only after active task completion, QA sufficiency, and review approval.

## State files

Primary working files live under `.lla/sdd/current/`:

- `intake.md`
- `prd.md`
- `tech-spec.md`
- `tasks.md`
- `progress.md`
- `decisions.md`
- `qa-report.md`
- `review-report.md`
- `acceptance.md`

## Knowledge model

Knowledge is split into:

- `reviewer/` for review-driven lessons
- `implementer/` for implementation guardrails
- `shared/` for cross-role conventions

Use the knowledge index first, then load only relevant entries.

## Agent invocation policy

Default entrypoint is `orchestrator`.

The orchestrator may delegate to:

- `intake`
- `planner`
- `spec-writer`
- `task-decomposer`
- `implementer`
- `qa`
- `reviewer`
- `knowledge-curator`

Direct use is also valid when requested by the user.

## Artifact format policy

Use Markdown for narrative and decision-heavy artifacts.
Use JSON for manifests, indexes, and compact machine-readable state.
Do not introduce XML unless an external tool requires XML.
