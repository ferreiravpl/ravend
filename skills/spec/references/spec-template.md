---
slug: <kebab-case-slug>
title: <short title>
tier: small | large | bug
status: draft | approved | in-progress | review | done | abandoned
source: <PROJ-123 | https://github.com/org/repo/issues/45 | prompt>
branch: feat/<slug>
created: <YYYY-MM-DD>
---

# <Title>

## Problem
<Why this exists, for whom, current vs desired behavior. Bugs: observed vs expected + reproduction steps.>

## Acceptance criteria
- AC1 [api]: Given <state>, when <action>, then <observable result>.
- AC2 [unit]: Given …, when …, then ….
- AC3 [e2e]: Given …, when …, then ….

## Design            <!-- large only -->
- Affected: <module/file list>
- Contracts: <endpoint, DTO, event, DB schema/migration changes>
- Decisions: <choice — reason — rejected alternative>

## Out of scope
- <explicitly excluded items>

## Assumptions
- <assumption the implementation relies on>

## Open questions
- <only if any; blocking ones are prefixed with BLOCKING:>

## Tasks
- [ ] T1: <title> — files: <paths> — proves: AC1 — deps: none
- [ ] T2: <title> — files: <paths> — proves: AC2, AC3 — deps: T1
- [ ] T3: <title> — files: <paths> — proves: AC4 — deps: none [P]

## Log
- <YYYY-MM-DD> spec created (tier <tier>)
