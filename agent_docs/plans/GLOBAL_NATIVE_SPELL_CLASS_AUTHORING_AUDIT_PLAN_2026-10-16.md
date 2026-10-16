# Global native spell, class and authoring audit

Date: 2026-10-16. Worktree:
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
The user requests further global scans for suspect spells, class abilities,
and character/item authoring. This is source inspection and native reproduction,
not authorization to redesign or repair new findings during the audit.

## Scope

Search current worktree spells, classes, character origin/progression/grant
authoring, direct item definitions/builders/loadouts/runtime properties and
authored creature/monster abilities. Follow their shared native owners only to
establish a concrete candidate's actual behavior. Preserve existing dirty work.
Use only the current native source, its tests and this conversation; do not
include unrelated proposals, other checkouts, chats or client work.

Look for effects/costs before admission; wrong source/recipient or missing exact
ownership; grants/resources that leak across rejection/removal/releveling;
ineffective declared fields; missing lifecycle wiring; reconstructible state and
recurring broad scans; unsafe shared mutable authoring data; and dynamic/import
shortcuts that conceal missing composition. Search hits are candidates, not bugs.

## Procedure and evidence

1. Inventory files and actionable search/AST patterns across every target domain.
   Record search-only versus inspected-body versus native-executed coverage.
2. Read owning implementations and callers before ranking candidates. Separate
   existing known/deferred findings and repaired cases from new discoveries.
3. Reproduce high-impact new candidates through supported native commands/builds,
   progression, equipment/item operations and real event admission. Read
   HOW_TO_TEST.MD before writing tests. Assert scalar state/structured facts;
   no private-method monkeypatch assertions or huge object repr failures.
4. Keep finite desired-behavior regressions for confirmed new bugs, using explicit
   strict expected failures while repairs remain unapproved. A passing control
   distinguishes intended behavior from the faulty case. Do not change production
   mechanics or unrelated tests to obtain a green audit result.
5. Use existing passive diagnostics/profiling to qualify suspected recurring cost;
   distinguish cast/build-only enumeration from hot handler fanout and unbounded
   history. No invented whole-engine timing gains.
6. Save a ranked report and coverage inventory in agent_docs. For each finding,
   record trigger, actual/desired behavior, owner/code reference, reproduction or
   source-only status, affected scope and an existing-native repair direction.
7. Run the new audit lane and appropriate existing controls, then obtain final
   review and report the actual results and limitations without claiming a full
   repository pass or manual coverage that was not performed.

## Review roles

- **Plan-adherence monitor:** keep all four requested domains covered, preserve
  audit-only scope, distinguish actual new findings from old debt and avoid
  spending the entire audit on one small helper.
- **Anti-OOP reviewer:** independently inspect character/item authoring and exact
  source/grant/lifecycle boundaries; check the final findings and regressions.
- **Anti-slop reviewer:** independently inspect class/ability handlers, redundant
  state reconstruction/dispatch/scans, false positives and evidence claims.

Root reviews spells/shared paths, integrates findings and writes the report.
Reviewers may run read-only probes and send exact repro instructions; root owns
all repository edits so test/report changes remain coordinated.
