# Paladin aura local refresh repair

2026-10-16. User authorizes fixing the Paladin aura inefficiency introduced in
this spell/class worktree. Scope is GA-P1 from the global native audit only.

## Behavior and boundary

Native Paladin aura benefits must continue to follow deployment, movement,
provider consciousness/life state, level-18 radius changes, faction changes and
exact source removal. Refresh work must use indexed local occupants and the
zone's existing retained membership receipts, independent of unrelated world
population. A distant faction change without a retained lease must return
without reconciling the aura.

Inputs are actual authored Paladin builds, committed movement/faction/life/
condition/progression operations and native removal vetoes. Outputs are retained
benefit sources, saving-throw bonus, control immunities and recorded diagnostic
work counts. Existing dirty work must be preserved.

## Implementation

1. Read current zone/anchor/membership owners and HOW_TO_TEST.MD. Retain the
   saved 18-operation diagnostic as the before measurement. Add finite native
   behavior controls for faction changes/overlapping providers, consciousness
   and life recovery, undeploy/redeploy and retained rejected-removal cleanup.
   Reuse existing movement/radius/source-removal regressions.
2. In `dnd/classes/paladin.py`, remove the dormant turn-start global refresh
   override. Keep existing native zone anchor relocation and footprint changes.
3. Refresh provider changes from `zone._occupants_at(affected_positions)` plus
   exact recipient IDs in `zone.linked_conditions`, deduplicated deterministically.
   Reuse apply_membership/remove_membership and the existing reentrancy guard.
   No new membership registry, manager, cache or shared-area-system rewrite.
4. Handle typed EntityFactionChangedEvent: owner change refreshes local/retained
   recipients; another entity change considers only that recipient when local
   or already retained. Ignore unrelated faction events before reconciliation.
   The new baseline recovery test also reproduces a missed existing life-state
   boundary: Entity publishes LifeStateChangeEvent only at COMPLETION, which
   EventQueue does not dispatch to handlers, while the aura waits at an unposted
   EFFECT. Replace that inert aura-owned trigger with the existing committed
   DAMAGE_APPLIED and HEALING_APPLIED effects for its provider, so HP changes
   refresh locally after HP commits. No shared event dispatch changes.
5. Run focused Paladin and shared spatial/anchored ownership controls; repeat the
   exact diagnostic and save after counts separately. New code must eliminate
   world enumeration and unrelated membership-removal attempts. Report indexed
   local work honestly; make no whole-engine latency claim.
6. Obtain anti-slop and anti-OOP review plus plan-adherence signoff. Update the
   audit's GA-P1 status and save the bounded repair/qualification evidence.

No other audit correctness findings, client work, schema changes, commit or push
are included in this request. User authorization to implement this repair takes
precedence over the earlier audit-only scope restriction.

## Review roles

- Plan-adherence monitor: enforce GA-P1 scope and completion of meaningful native
  behavior/performance checks; prevent unrelated rewrites and speculative work.
- Anti-OOP reviewer: check exact zone/source ownership, membership cleanup,
  lifecycle behavior and reuse of existing ECS composition.
- Anti-slop reviewer: check locality, removed dead code, duplicate state and
  performance evidence/coverage claims.

Root owns repository edits; reviewers inspect and independently validate them.

## Completion

Implemented. The focused native lane passes 19 tests; the final bounded Paladin,
shared spatial/condition and audit batch passes 145 with 36 unrelated pre-existing
strict expected failures unchanged (19.19s). The same 18-operation diagnostic now
has zero world enumeration and zero unrelated membership-removal attempts at
1/25/100 distant actors. Local queries and lease operations remain explicit.

Anti-slop, anti-OOP and plan-adherence reviewers approved the scoped implementation
and evidence. The [repair report](../PALADIN_AURA_LOCAL_REFRESH_FIX_REPORT_2026-10-16.md)
records exact changes, the separate healing-recovery listener correction and the
pre-existing direct-revival coverage gap. All work remains in the same worktree.
