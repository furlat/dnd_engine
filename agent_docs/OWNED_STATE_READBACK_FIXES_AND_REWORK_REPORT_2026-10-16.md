# Owned state: four fixes, three remaining findings, and Antimagic removal

Date: 2026-10-16. Worktree:
`/home/tommaso/.codex/worktrees/spells-rank-one-two/dnd_engine`.
Branch: `codex/spells-rank-one-two`. Existing repair checkpoint: `059ad0af4c9`.
These follow-up changes are in the working tree. No client files were edited.

The human authorized four local readback fixes and requested this report on
three other candidates and the choice to remove Antimagic. The three candidates
remain analysis only. Their existing production behavior has not been changed.

## 1. Four delivered fixes

| Owner | Former reconstruction | Delivered state/result handling |
| --- | --- | --- |
| `UsableItem` finite resource | Scan every event since preparation, filtering for completed resource changes on this item. | An internal item revision is captured before preparation declaration dispatch. Native consumption/recharge increments it at commitment. Comparing two integers detects intervening spending/recharge even when values return to the same number. |
| `GuardianOfFaithZone` | Read the new event interval after each strike and sum its matching applied-damage facts. | The existing `damage_dealt` counter receives its own completed applied-damage fact directly. Threshold retirement stays after damage returns; cancellation, save/resistance, temporary HP, per-turn entry and the possible last-hit overshoot beyond 60 remain. |
| Shared fall resolution | Collect the new event interval, reconstruct matching incoming lineages, then sum applied damage. | Capture the exact completed applied-damage result locally; retain the same positive-damage/living-target check before Prone and the same returned amount. |
| `Harm` | Search child events for its completed uncanceled incoming damage and read `final_damage`. | Receive that exact incoming result directly, capture `final_damage` locally, then apply the existing HarmSource at the same point after damage returns. |

Source owners: `dnd/blocks/base_item.py`, `dnd/spells/conjuration.py`,
`dnd/actions.py`, `dnd/spells/necromancy.py`, with a small additive callback in
`dnd/entity.py::receive_damage`.

### Exact receipts matter

The callback is `on_completed(incoming, applied)`: the exact final
`TakeDamageEvent` and the optional result returned by the existing applied-damage
publisher. It runs after incoming completion, at the existing damage-return
boundary. Both results retain their real phase/cancellation state. Guardian and
fall require applied-event COMPLETION; Harm requires uncanceled incoming
COMPLETION. Effects capture only their local amount in the callback; retirement,
Prone and HarmSource still run afterward in their original order.

The existing `on_resolved(DamageResolution)` API and its users are unchanged.
There is no new receipt model, result registry, global listener or manager.
No public/native event field or schema version was added by these four fixes.

A native counterexample established why raw damage resolution is insufficient:
grant 10 temporary HP during Harm's incoming EFFECT, with a 28-point packet.
The current engine reports 18 in completed incoming/applied facts while the raw
resolution reports 28. A fully absorbed fall packet can similarly have no
applied-damage fact even though raw resolution is positive. Three native
regressions now require the consumers to agree with their own exact completed
facts; the uniform raw-resolution implementation fails all three.

**Separate shared-engine observation:** the damage owner measures temporary-HP
loss against the pool before declaration, so an admission-time temporary-HP grant
can make its published damage facts omit some newly absorbed damage. This report
does not claim that arithmetic is the desired DND rule. It is a pre-existing
shared bookkeeping issue, outside the authorized four readback simplifications.
Its correction should be discussed separately. These changes preserve the
previously consumed factual results rather than silently substituting a different
measure.

### Finite-item details

Both the item revision and the preparation snapshot are `PrivateAttr` runtime
data. The snapshot exists before DECLARATION handlers run, so a reentrant
spend/recharge during admission cannot revive the outer preparation. The revision
advances before retirement or resource completion can publish consequences.
Unrelated items/events and refused resource operations do not invalidate it.
Stack rollover is one spending operation and repeated commitment cannot spend it
twice.

The existing exact-lineage terminal lookup remains: it provides native
idempotence and is bounded by that operation's lifecycle. Only the unrelated
event-tail scan was removed. A closely related recharge bug was also corrected:
recharge now explicitly publishes/checks DECLARATION, EXECUTION and EFFECT before
mutating charges. A declaration veto previously could be ignored by constructor
publication. Native tests cover each refusal phase and a surviving older
preparation.

## 2. Scope of the remaining findings

The following three findings come from inspection of the current engine in this
worktree. Each section identifies its present owner, what it reconstructs, a
possible local simplification and the behavior that must be preserved. These
recommendations are not implemented by this batch.

## 3. Deferred candidate: turn identity witnesses

Current owner: `dnd/encounter.py::_turn_identity_observers`. At turn closure or
active-member departure it scans events since turn start, selects the actual
`turn_execution_id`, and unions observer identities for the active actor. This
recovers knowledge after death, hiding or departure removed live sensory contact.
Cost grows with events produced during this turn, not all previous combat.

**Recommendation:** keep an observer set on the active encounter/turn execution,
updated at canonical event publication from the already computed identity grant
for that actor. Preserve the current event eligibility and turn-ID predicates.
Set union makes repeated phase observations harmless. Reset only at the real
turn boundary and release it with that encounter/turn's lifetime. No global
actor-memory service or per-observer history query is needed.

**Boundary to preserve:** accumulate only identity grants already recorded for
this actor during the actual turn. Recognizing a dead actor must not reveal its
current location or hidden movement. Never rebuild the set from present-day FOV
or all party observers. Turn closure and active-member departure must include all
eligible observations produced before their existing completion boundary.

Acceptance cases before a later implementation:

- An opportunity attack kills the mover; turn end retains its witnessed identity
  without restoring exact location. Existing case:
  `test_encounter_apis.py::test_opportunity_attack_death_keeps_witnessed_turn_identity_without_location`.
- A reaction first reveals the actor during its turn; only actual witnesses gain
  that identity. A distant opponent is not included by party-wide sharing.
- Hiding, source retirement and deferred active-member departure preserve the
  corresponding witnessed identity; the next turn starts with its own set.
- Ordinary publication/replay grants remain equivalent at turn closure and
  active-member departure.

This can be a small encounter-owned set. Its update must be part of the existing
event-time observation boundary and must end with its owning turn/encounter.

## 4. Deferred candidate: Fireball state and destruction receipts

Current owner: `dnd/spells/evocation.py::Fireball._apply_target_applications`. There are two distinct
readbacks:

1. At stage/recipient boundaries, retrieve and sort the cast's indexed lineage
   merely to inspect its latest cancellation state. This is a small cast-local
   query, not a whole-history scan.
2. After a reach stage, scan newly emitted events to collect relevant barrier
   destruction lineages. These become explicit prerequisites of the next
   `AreaReachEvent`. That is real causal information used by staged propagation.

**Recommendation:** use direct latest-version/lineage access for the first
query. For the second, retain stage-owned destruction results on the actual
Fireball invocation: finite envelope, visited recipients, reach set, preceding
stage, relevant barrier identities and propagation revision. Feed destruction
receipts from their real application results;
advance once the relevant destruction and propagation work has settled. Neither
a counter alone nor a blanket global list of destroyed objects is sufficient.

**Boundary to preserve:** expansion depends on actual committed breakage and the
current propagation revision. Cancellation must be read from the accepted cast
state. Preserve the existing finite envelope, doorway/corner rules, Globe
clipping and recipient visitation. A destruction collector must belong to the
particular cast stage and exclude unrelated destruction. The direct
latest-version cleanup is smaller than replacing stage-result collection; both
remain deferred in this batch.

Acceptance cases:

- Breaking a real door/barrier opens only the next permitted reach stage, with
  exact destruction prerequisites and each recipient visited at most once.
- Root/stage cancellation stops subsequent work while keeping spent costs and
  already committed facts. Nested reactions retain their true causal identity.
- Container/attachment destruction, shared barriers, Globe clipping and unchanged
  propagation revision preserve current behavior.

Four existing Globe propagation fixtures already fail at checkpoint
`059ad0af4c9` (dice/footprint expectations). Reconcile that baseline before treating
them as successful qualification evidence; this report does not rewrite their
expectations.

## 5. Deferred candidate: residue-fear entry provenance

Current owner: `dnd/conditions.py::residue_fear_origin`. Ordinary entry supplies
`old_position`. For a same-position occupancy-layer transition, such as landing,
it walks parents and sometimes committed movement children to recover the real
preceding step. It then records a `ResidueFearOrigin`, including the particular
material/condition identity and initial retreat direction. This is local ancestry
reconstruction, not a lifetime combat-history scan.

**Recommendation:** carry the causative entry predecessor in the admitted
movement/landing operation and its spatial entry fact. The residue owner can
consume that exact data directly and keep its existing origin/paid-retreat state.
Use the actual committed step or transfer; do not infer it from the planned path,
last global movement event, a mutable `Entity.last_position`, or today's support
height.

**Boundary to preserve:** entry provenance belongs to the particular movement
or landing that caused this contact. Preserve the existing departure/arrival
order, occupancy layer and recorded support information. Nested movement must
not overwrite another operation's predecessor. The residue condition should
receive the actual entry origin without searching unrelated movement records.

Paid retreat still executes after spatial publication settles. The existing
`get_paid_entry_retreat(since_cursor=...)` compares one stored application cursor;
it does not scan history and is not a new defect filed by this report.

Acceptance cases:

- Ordinary ground entry keeps the current initial retreat and paid movement.
- Jump air cells do not become ground entries; full and partial landings identify
  the actual last committed transit.
- Teleport, forced landing and nested portal movement preserve the causative
  entry and do not overwrite another pending operation's predecessor.
- Connected residue contact, shared fear sources and material replacement keep
  source-specific cleanup and the original retreat heading.

Any change must preserve the current movement and landing semantics. A shared
last-step cache would introduce an unnecessary state owner and cross-operation
ambiguity.

## 6. Human decision: remove Antimagic Field

The human explicitly chose removal after the full spell/performance audit:
remove Antimagic and the ad hoc work dedicated to it. That decision is implemented
in this worktree; the feature is not disabled behind an entry or replaced with a
new suppression manager. The detailed delivered inventory is in the
[AM removal handoff](SPELL_CATALOG_REPAIR_AND_ANTIMAGIC_REMOVAL_HANDOFF_2026-10-16.md).

| Removed burden | Concrete simplification |
| --- | --- |
| Live spell, zone, condition/class entries | No AM footprint/exclusion rules, overlapping AM provider accounting or exception identity. Cold inputs explicitly reject the removed spell. |
| All-item/area/entity AM refreshes and global light refresh | Ordinary local movement no longer asks AM to rescan unrelated registries or rebuild their presentation. |
| Provider token fields on conditions/items/actions | No retained suppression-provider UUID sets, before/after AM snapshots or their public player fields. |
| Creation suspension and global return callbacks | Goodberries and other creations no longer install AM-driven return/retry work on unrelated movement. Their real lifetime owners remain. |
| Artifact/deity exceptions and magic-property stripping | No AM exception plumbing across spell origins, divine class actions, items and attack/equipment composition. Ordinary magical provenance/damage remains. |
| AM-only callbacks, activation guards and stone exemptions | Fewer cross-system transitions, conditional branches and coupled effect rules. New/completed construction still follows its native formation/physical behavior. |

The old audit measured remote object moves outside the field: 1/25/100 items
caused 10/202/802 presentation snapshots. After removal ordinary moves produce
2/2/2. Remote movement with 4/16 never-suppressed Goodberries previously dispatched
4/16 no-effect creation-return callbacks, even after the field ended; those
handlers are gone. These are work-count observations, not a whole-game speedup
percentage or a matched unprofiled timing claim. Historical and post-repair raw
measurements remain separate artifacts linked by the removal handoff.

**Kept independent mechanisms:** Globe admission/formation/clipping and its
provider geometry records; contribution-owner gates and inactive-owner
maintenance; condition admission/removal/shared leases; item lifetime and
physical construction; Banishment suspension/return and occupied-return retries;
and local optical/light presence. Removing AM does not justify deleting all
suppression-like state or making retained-but-inactive owners effective.

The prior concentration, exact-recipient dispatch and Antilife locality repairs
also removed avoidable work, but their improvements must not all be attributed
to AM removal. The four fixes in section 1 are another independent cleanup.

### Contract changes from removal

The AM cut already moved protocol 1 from player schema 10 to **11**, removed the
named AM player fields and archived the exact old contract. Native recording
schema 2 and public sequence schema 5 remain. These four follow-up fixes add no
further wire fields or schema bump.

## 7. Qualification and review

The affected native batch passes **263 tests**, covering all four owners plus
direct items, created spell items, earlier spell interactions and damage/admission
audit regressions. The four primary suites independently pass **136 tests**,
including the three completed-fact consistency cases and resource declaration
reentrancy/refusal/stack cases. Counts overlap and must not be summed.

Reproduce the primary behavior lane:

```bash
uv run --no-sync python -m pytest \
  tests/engine/test_item_resource_lifecycle.py \
  tests/engine/test_spell_handoff_holy.py \
  tests/engine/test_spell_handoff_necromancy.py \
  tests/engine/test_telekinesis_landing.py --assert=plain -q --tb=short
```

The maintained native profiler is
`tests/manual/item_resource_commit_performance.py`. Run with
`uv run --no-sync python -m tests.manual.item_resource_commit_performance`.
[Saved evidence](ITEM_RESOURCE_COMMIT_BENCHMARK_2026-10-16.jsonl) records Python
3.13.12, WSL/Linux and the source directory. Setup and unrelated event creation
are outside the profiled commit. Event-tail iterator resumes are now **0/0/0**
for **0/1,000/10,000** unrelated events, compared with the measured previous
**3/1,003/10,003**. All three native commitments succeed and spend exactly once.
This proves removal of that traversal, not constant total engine time.

Source lint and diff checks pass. Actual-code anti-OOP and anti-slop reviewers
approved the exact-completed-fact version and independently exercised the primary
lane. Both also approved this report; the Fireball source-method pointer was
corrected following review. Final adherence confirmation is recorded with the companion
[finite plan](plans/OWNED_DAMAGE_RESULTS_AND_ITEM_RESOURCE_REVISION_PLAN_2026-10-16.md).
The additional native life-state/dice/concentration/spellcasting,
player-record/capture/schema and source-owned progression boundary lane passes
**80 tests**. The native schema exporter still reports 325 definitions and 1,716
fields with unchanged schema-11 identity, matching both SDK copies.

The three deferred candidates and the shared admission-time temporary-HP
bookkeeping observation remain explicit discussion items. They were not
implemented by this batch.
