# Four local history-readback simplifications

Date: 2026-10-16. Worktree:
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
User authorized these four fixes and a report on three deferred candidates.
Existing spell repair changes remain in this working tree; do not reset them.

## Finite scope and acceptance

| Change | Real boundary/input | Required result |
| --- | --- | --- |
| Guardian of Faith | Native hostile entry, save and damage resolution | Its existing `damage_dealt` counter receives only its own resolved packet, including temporary HP. Cancellation/immunity add zero; resistance/save reduction and retirement at or beyond 60 remain. No new-event readback. |
| Fall damage | Native fall/forced landing damage | Capture the exact completed DamageApplied fact through `on_completed`; return that amount and apply ordinary Prone only on positive damage to a living recipient. Preserve immunity, cancellation, temporary HP, reactive healing and native landing order. No event-tail reconstruction. |
| Harm | Native cast, save, minimum-1-HP damage cap and HarmSource application | Capture the accepted damage via existing callback; keep current maximum-HP reduction/cancellation/save/temporary-HP/reactive-healing behavior and owner admission. No child-event readback. |
| Item charges | Native preparation/commit, consumption, stack rollover and rest recharge | One internal monotonic revision per usable item; capture it before preparation admission and compare at commit. Increment on actual finite consumption and admitted recharge before publishing consequences. Spend/recharge back to identical values still invalidates older preparations. Unrelated events/items and vetoed operations do not. Preserve existing once-per-lineage terminal event handling; remove only the cross-event-tail resource-change scan. |

Use exact completed native damage facts passed directly by `receive_damage`.
An executed admission-time temporary-HP grant disproved equivalence with raw
`DamageResolution.applied_damage`: Harm's native completed damage can be 18 while
that preview reports 28. Add one optional `on_completed(incoming, applied)` hook
after current completion, retaining the helper's existing applied-event result
locally. Harm consumes uncanceled TakeDamage completion/final_damage;
Guardian/Fall consume DamageApplied completion/applied_damage, or zero when absent.
Existing `on_resolved` users retain their current behavior. Keep effects in their current owning handlers/functions and
preserve consequence order. No new damage service, condition manager, global
listener, resource manager, schema field, late import or type/introspection trick.
The shared damage owner's temporary-HP fact arithmetic is not changed in this
batch; preserve the existing fact boundaries and record the discrepancy.
The item revision and preparation snapshot are internal runtime data, not a
recording/live-client contract. No NDClient/frontend work.

## Work sequence

1. Read recovery/test instructions and affected native implementation/tests.
2. Add finite native behavior cases where current coverage is missing; reuse
   existing Harm/Guardian/fall/resource suites. Scalar state/event assertions;
   no mocked engine internals or method-call assertions.
3. Implement only the four changes. Preserve native event lineage idempotence,
   source attribution, cancellation, temp HP and retirement behavior.
4. Repeat the measured item preparation/commit diagnostic with 0/1,000/10,000
   unrelated events. Use a profiler as diagnostic evidence, not a private-method
   monkeypatch/test gate or machine-dependent wall-time assertion.
5. Run affected native spell, landing/movement, item/cold-record and repair tests;
   source lint and diff checks. Expand checks only for actual shared risk.
6. Save a report in `agent_docs` about the three deferred candidates below,
   their current native owners, and the human's Antimagic-removal choice and
   concrete simplifications. Record implementation/results here.
7. Obtain actual-code anti-slop and anti-OOP review and plan-adherence approval.

Review roles: **plan-adherence monitor** tracks the finite four fixes/report;
**anti-OOP reviewer** checks owning state, native lifecycle and consequence order;
**anti-slop reviewer** checks no speculative framework, accurate scope/performance
claims and removal of the demonstrated scans. These are implementation checks,
not another human permission gate; the user already authorized this scope.

## Three candidates remain analysis only

- Encounter turn identity: consider a turn-owned witness set while preserving
  event-time disclosure, death/leave handling and actual turn identity.
- Fireball: consider direct latest-lineage access separately from stage-local
  destruction dependency receipts. Preserve real staged propagation/admission.
- Residue fear: consider explicit entry/landing predecessor data across ordinary
  movement, jumps, forced movement and teleport. Do not invent a global last-step
  cache or change movement semantics in this batch.

Base recommendations on the current native code and its observed behavior.
Keep these three as findings for discussion, without implementing them in this batch.
The original spell audit/CSV/baseline measurements stay unchanged. Link the
delivered AM-removal handoff rather than reviving its historical mechanics.

## Implementation record

The four fixes and requested report are delivered in this worktree. Guardian,
Harm and fall no longer reconstruct their completed amounts from child/history
queries. `receive_damage` exposes its exact existing results through one optional
completion callback; the prior raw-resolution hook is unchanged. No new receipt
model/service/registry or wire field was introduced. Usable item/preparation
private revisions replace cross-event-tail invalidation while preserving native
per-lineage idempotence. Recharge now honors all its admission phases; three
native refusal cases confirm it changes neither resource nor prior preparation.

The exact-result correction was proved by three native counterexamples:
admission-time temporary HP makes raw resolution differ from the previously
consumed incoming/applied facts. All three fail with the uniform raw-resolution
approach and pass with exact completed facts. Their continuations remain in the
same order. Shared damage-fact arithmetic itself was not changed.

Qualification: **263 affected native tests pass**; an additional **80 shared
boundary tests pass**. Independent primary-lane reviews pass **136 tests**;
these overlapping counts are not unique totals. Source lint and diff checks pass.
Native schema export has the unchanged protocol-1/schema-11 identity, 325
definitions and 1,716 fields, matching both current SDK copies. No client edits.

The maintained profiler and
[raw samples](../ITEM_RESOURCE_COMMIT_BENCHMARK_2026-10-16.jsonl) show **0/0/0**
event-tail generator resumes at **0/1,000/10,000** unrelated events between native
preparation and commitment, replacing measured **3/1,003/10,003**. Setup is excluded;
no whole-game speedup or wall-time gate is claimed.

The [requested report](../OWNED_STATE_READBACK_FIXES_AND_REWORK_REPORT_2026-10-16.md)
describes the four delivered fixes, the three remaining native-code findings,
and the AM-removal choice, deleted machinery, preserved independent owners,
work-count evidence and schema consequences. The three
candidates and shared temporary-HP bookkeeping observation remain deferred.

Actual-code anti-OOP and anti-slop reviews approve the exact-completed-fact
implementation after independent native qualification. Both final report reviews
are approved, including deferred scope, native source findings, exact-result
semantics, AM boundaries and performance claims. The reviewed Fireball source
pointer was corrected to `_apply_target_applications`.

Final plan-adherence review is **approved**. The monitor independently reran all
136 primary cases and verified the exact-fact boundary, item revision admission,
diagnostic, final report, unchanged contracts and deferred scope. No required
implementation or report work remains for this finite follow-up.
