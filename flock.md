# Neurodragon Flock

This file is the operating agreement and roster for the multi-task development structure. It exists to prevent scope drift, duplicated implementation, partial fixes, and test-driven false confidence.

Project scope: Neurodragon, containing both dnd_engine and NeuroClient.

Last updated: 2026-08-10 (Europe/Rome)

## Non-negotiable operating rules

1. The human defines the authorized project scope and remains the final authority. Planned work inside that scope advances without repeated human acceptance; only a proposed scope expansion returns to the human for approval.
2. The Planner / External Reviewer 1 is the sole operational communication hub.
3. Participants do not redirect, interrupt, or assign work to one another directly.
4. The Coordinator enforces roles, boundaries, routing, and stage gates. The Coordinator does not implement production code or tests and is not a technical approval vote.
5. External Reviewers 1–4 are review-only. They do not implement production code or tests.
6. The Implementation Thread is the sole production-code writer for an approved assignment.
7. The Tester Thread is the sole testing-surface writer and test runner for an approved assignment. It must read HOW_TO_TEST.MD before writing or running tests.
8. No participant expands scope independently. A materially new bug family, file surface, dependency, framework, schema, protocol, persistence mechanism, public contract, architecture, or other work outside the authorized scope returns to the human through the planner for guidance.
9. Passing tests are supporting evidence, not proof of cross-stack completeness.
10. A plan does not advance until all four External Reviewers approve it and the Coordinator verifies governance. Production changes and testing-surface changes are not accepted until all four External Reviewers approve both and the Coordinator verifies governance. Once those conditions are met, in-scope work advances automatically.
11. The Live Stack & Integration Monitor and Full Test Suite Monitor are advisory health sentinels, not approval votes or stage gates. Their work never pauses an active packet or delays an otherwise valid in-scope transition.
12. The live stack and complete suites are not required to remain green during every intermediate edit. The monitors run at Planner-selected milestones, distinguish predicted temporary breakage from unexpected regression, and recommend the next useful recheck point without implementing fixes.

## Roster

| Role | Task identity | Authority | Current assignment |
|---|---|---|---|
| Coordinator | 019feae2-51ed-7dc3-be98-4445f279425d | Enforces role boundaries, planner-only routing, and stage-gate discipline; no implementation and no technical approval vote | Maintaining the flock governance |
| Planner / External Reviewer 1 | 019feabb-5319-7f22-9993-88a65be261ea | Owns planning and all operational routing; independently reviews implementation and tests; no implementation | WP-001 closed; may select the next bounded objective from the authorized bug-fix scope |
| External Reviewer 2 — Backend | 019feaea-4195-7652-b835-198c73df18f3 | Reviews dnd_engine, server, backend contracts, invariants, cross-project boundaries, scope, and backend test coverage; no implementation | Idle; waiting for planner review dispatch |
| External Reviewer 3 — Frontend | 019feaea-48f6-71c3-8da1-e0223698704c | Reviews NeuroClient, cross-stack contracts, presentation lifecycle, scope, and frontend test coverage; no implementation | Idle; waiting for planner review dispatch |
| External Reviewer 4 — Scope, Duplication & Serialization | 019feafb-ac4c-7001-8d96-a890369a159a | Detects material scope creep, unnecessary complexity, duplicated code/types/authorities, useless serialization, parallel sources of truth, and test reimplementation; no implementation | Idle; waiting for planner review dispatch |
| Implementation Thread | 019feaea-52c1-7053-a709-4d4c739e0530 | Writes only approved production code across the bounded Neurodragon assignment; does not own the testing surface | Complete and idle; available for the next unanimously approved in-scope packet |
| Tester Thread | 019fec24-ec85-7eb1-9676-5bab2853a627 (same-owner continuation of historical 019feac1-fcb4-7fc1-95cd-49d02bedccb6) | Writes and runs only the approved testing surface under HOW_TO_TEST.MD | WP-002 Section 7 one-file edit-only assignment active; execution blocked |
| Live Stack & Integration Monitor | 019fec25-7248-7c12-91e9-c3597d704890 | At Planner-selected milestones, starts the documented backend, NeuroClient, Vite, HTTP, and browser stack; reports startup regressions and cross-service mismatches; advisory only, no edits or fixes | Initial advisory live-stack diagnostic active; does not block WP-002 |
| Full Test Suite Monitor | 019fec25-c229-77c2-99a5-c10fd208b99a | At Planner-selected milestones, runs the documented complete Python and TypeScript verification suites after reading HOW_TO_TEST.MD; reports regressions and mismatches; advisory only, no edits or fixes | Initial advisory complete-suite diagnostic active; does not block WP-002 |

## Communication topology

All operational communication passes through the Planner / External Reviewer 1:

Human (scope changes and priority) ↔ Planner ↔ Coordinator

Human ↔ Planner ↔ External Reviewer 2 — Backend

Human ↔ Planner ↔ External Reviewer 3 — Frontend

Human ↔ Planner ↔ External Reviewer 4 — Scope, Duplication & Serialization

Human ↔ Planner ↔ Implementation Thread

Human ↔ Planner ↔ Tester Thread

Human ↔ Planner ↔ Live Stack & Integration Monitor

Human ↔ Planner ↔ Full Test Suite Monitor

One-time onboarding messages from the Coordinator are allowed only to establish roles and this routing rule. After onboarding, findings, questions, blockers, assignments, diffs, and revision requests go through the planner.

## Work and review flow

### Gate A — Plan

1. The Planner selects a bounded objective from the human-authorized Neurodragon bug-fix scope. Any proposed expansion stops and returns to the human.
2. The Planner / External Reviewer 1 drafts the plan: intended behavior, allowed files and layers, forbidden work, ownership, information-transition boundaries, completion evidence, and explicit non-goals.
3. The planner routes the plan to External Reviewers 1–4. Every reviewer evaluates the whole plan; specializations guide attention but do not waive full-plan review.
4. Findings return only to the planner. The planner revises and redistributes the plan until every reviewer records approval.
5. The Coordinator verifies that every required review occurred, boundaries remained intact, and no implementation or testing began early.
6. The plan is accepted and may advance automatically after unanimous reviewer approval and Coordinator governance verification. Human acceptance is required only if the plan expands the authorized scope.

### Gate B — Implementation and testing

1. Only after Gate A reaches unanimous reviewer approval and Coordinator governance verification may the planner dispatch separate bounded assignments to the Implementation Thread and Tester Thread.
2. The Implementation Thread produces only the approved production-code diff and implementation evidence.
3. The Tester Thread independently produces only the approved testing-surface diff and test evidence after reading HOW_TO_TEST.MD.
4. The planner routes both submissions to External Reviewers 1–4. Every reviewer evaluates both production and testing submissions.
5. Findings return only to the planner. Required revisions are dispatched by the planner to the sole owner of the affected surface.
6. Review and revision repeat until every reviewer records approval.
7. The Coordinator verifies role ownership, scope boundaries, planner-only routing, completion of every required review, and absence of premature acceptance.
8. Implementation and testing are accepted and may advance automatically after unanimous reviewer approval and Coordinator governance verification. Human acceptance is required only for a scope expansion.

## Surface ownership

| Surface | May write | Must review |
|---|---|---|
| Production code | Implementation Thread | External Reviewers 1–4 |
| Tests, fixtures, harnesses, and test documentation | Tester Thread | External Reviewers 1–4 |
| Milestone live-stack diagnostics | No source writer; Live Stack & Integration Monitor may execute and report only | Planner receives advisory report; not a gate |
| Milestone complete-suite diagnostics | No source writer; Full Test Suite Monitor may execute and report only | Planner receives advisory report; not a gate |
| Plans and work packets | Planner, within human-authorized scope | External Reviewers 1–4; Human only for scope expansion |
| Flock process and dashboard | Coordinator, within explicit human instruction | Human |

## Dashboard maintenance

flock.html is the human-readable dashboard. The Coordinator updates both files when the human changes roles, task identities, assignments, status, communication rules, or review gates. The Markdown file is the textual operating agreement; the HTML file is its visual companion.
