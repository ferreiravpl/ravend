# Software SDD LLA for OpenCode

This repository bootstraps a local LLA (lightweight local agent workspace) for OpenCode.

## Purpose

Provide an SDD-oriented software development orchestrator that can:

- intake work from a source such as Jira via MCP
- produce PRD and technical specification artifacts when needed
- decompose work into bounded tasks
- implement incrementally
- run QA and review loops until accepted
- learn incrementally from review findings without forcing all historical knowledge into every prompt

## Core design principles

1. The default entry point is an `orchestrator` primary agent.
2. SDD is the default path, not the only path.
3. Subagents can also be used independently for planning, implementation, QA, and review.
4. Skills carry reusable procedures and are loaded on demand.
5. State is persisted in `.lla/` so long sessions do not depend on chat memory alone.
6. Knowledge grows incrementally through compact artifacts and indexed entries.

## Folder map

- `AGENTS.md` -> project-wide operating rules
- `opencode.json` -> OpenCode config, MCPs, instructions, permissions, compaction
- `.opencode/agents/` -> specialized agents and subagents
- `.opencode/skills/` -> reusable procedures loaded lazily
- `.opencode/commands/` -> optional slash command entry points
- `.lla/context/` -> stable project context
- `.lla/sdd/current/` -> current delivery artifacts and workflow state
- `.lla/knowledge/` -> persistent incremental knowledge base
- `.lla/manifests/` -> machine-readable scoped manifests for tasks, files, and handoffs

## Why markdown vs json

Use Markdown for human-authored reasoning artifacts:

- PRD
- tech spec
- task narratives
- reviewer findings
- acceptance notes
- project conventions

Use JSON for machine-readable, low-ambiguity, compact structures:

- manifests
- indexes
- knowledge catalog
- handoff metadata
- task state snapshots

Avoid XML by default. Only use XML when an external system or model-specific tagging convention truly requires it. For OpenCode-local orchestration, Markdown plus JSON is lower friction and easier to maintain.

## Suggested operating modes

- Full flow: intake -> PRD -> spec -> tasks -> implement -> QA -> review -> loop
- Fast path: task plan already exists, send directly to implementer
- Review path: reviewer and implementer loop without re-running the full SDD chain
- QA path: QA only for a bounded change or verification pass

## Next step after bootstrap

Customize the prompts of each agent and the project context in `.lla/context/`.
