# Existing gear bug fixes — pre-plan

Scope: repair four existing bugs from the item audit before adding roster gear.
The human approved implementation and item-owned coating transfer semantics on
October 2. Evidence is in [the item audit](GEAR_INVENTORY_AND_COMPOSITION_2026-10-02.md).

## Intended behavior and boundaries

| Bug | Caller-visible requirement | Repair boundary |
| --- | --- | --- |
| Droppable anatomy | A wolf's bite/hide remain attached to that wolf; ordinary weapons and armor remain removable and lootable | Cold intrinsic metadata, creature materialization and existing equipment/inventory transition owners |
| Dagger bonus leaks | Unseen Strike applies only when that exact dagger produces the eligible attack | Existing item-owned handler and native damage-event weapon provenance |
| Coating cleanup/lifetime | Removing a coating removes only its own contribution; coating follows its weapon with an explicit duration/source link | Item-owned conditions, extra damage contributions and existing expiry/destruction/concentration cleanup |
| Magical wearable flag | A wearable can explicitly declare magical identity; Spellblade Crown carries its intended identity and existing +3 CHA effect | Wearable definition, direct builder and rules-facing item facts |

The tests observe public actions, authoritative state and emitted event results.
They must not depend on private hook names, parallel-array indexes or class layout.
Read HOW_TO_TEST.MD before writing them.

## Execution order

1. **Reproduce the four failures first.** Add small deterministic public gameplay
   cases. Record current failure and expected result, including ordinary-item
   control cases. Do not weaken existing tests or infer magic from a sprite.
2. **Preserve intrinsic semantics.** Carry explicit anatomy ownership from cold
   definitions/materialization to the native item. Validate initial installation
   on its owner. Reject voluntary unequip, replacement, drop and pickup/transfer
   through existing native preflight, with no partial equipment changes. Anatomy
   remains attached on death. Ordinary world detachment preserves the entity and
   its attached anatomy for redeployment; it is not terminal disposal. Existing
   terminal item retirement and uncommitted rollback retain their own cleanup. No new body-part
   harvesting/severing mechanic. A drop-only `is_pickable=False` patch is insufficient.
   Do not turn all HIDDEN gear or all creature gear into anatomy.
3. **Scope the dagger to the participating item.** Its existing conditional
   damage handler must resolve the weapon identity represented by the native
   attack event, preserving hand and slot semantics. Require that identity to
   equal the provider item. Keep the existing unseen-target condition and bonus
   amount. Unequip/destruction still removes its handler exactly once. If slot
   alone cannot identify the actual weapon at resolution, carry the smallest
   typed provenance fact through the existing attack event; do not infer it from
   appearance or introduce an alternate attack path.
4. **Give coating contributions exact ownership.** Replace damage-type-based
   removal with stable per-contribution identity, including weapon/provider
   identity. Migrate the touched authored extra damage producers to the same
   ownership contract so built-in fire damage and temporary fire coats coexist.
   Reuse existing item condition and linked-duration mechanisms; the modifier
   belongs to the weapon, and a concentration requirement links to its sustainer.
   Destruction removes intact-item-dependent effects through existing events.
   Do not redesign every condition or introduce a general enchantment hierarchy.
5. **Declare magical wearables.** Add an explicit cold magical flag with a
   nonmagical default and forward it through all wearable builder branches.
   Mark Spellblade Crown magical, retaining its existing +3 CHA equip/unequip
   behavior. Do not mark ordinary recolored/tinted variants magical. Verify the
   existing Disintegrate item exception through spell resolution. Magical weapon
   damage provenance is a separate known gap, outside these four repairs.
6. **Validate together.** Run focused gear, attack, coating, item destruction and
   equipment tests, then the complete engine suite. Run existing event projection/
   replay and architecture checks appropriate to changed typed facts. Report any
   unrelated failures and discuss backend changes with the human; do not silently
   rewrite their expected results. Record changes, verified behavior and remaining
   limitations in RECOVERY_PLAN.md.

## Regression matrix

| Area | Required cases |
| --- | --- |
| Intrinsic anatomy | Default and intrinsic-only creature deployment; public unequip/drop/replacement attempts leave bite/hide and slots unchanged; other creature cannot acquire detached anatomy; ordinary dagger/armor equip/drop/pickup still works; world detachment/redeployment preserves attached anatomy; terminal item retirement/rollback retains existing cleanup |
| Dagger | Its own eligible hit gets one bonus; visible attacker gets none; bow/other main-hand/off-hand/unarmed attacks get none while dagger is equipped; dagger used in either supported hand gets its own bonus; opportunity attack and object-target path preserve applicable semantics; re-equip does not duplicate handler |
| Contributions | Built-in fire plus timed fire; two independent same-type sources in both removal orders; separate weapons on one wielder; removal/expiry preserves other sources; reapplication follows accepted stacking policy; attack damage demonstrates actual surviving packets |
| Lifetime | Timed expiry without duplicate duration advancement on same-round transfer/drop/pickup; ordinary drop/transfer; item destruction; concentration loss; unequip/re-equip; source removal under the accepted source-link policy; no orphan conditions/handlers or duplicate damage |
| Wearable identity | Crown explicitly magical, ordinary apparel nonmagical; +3 CHA attaches/detaches without accumulation; existing item-directed Disintegrate magical exception observed; visual tint unchanged |
| Existing attack economy | Existing creature/object, chosen-hand/off-hand, opportunity, Extra Attack, Haste, Slow, Action Surge and Frenzy regression tests continue passing; no new action budget or attack route |
| Events | Rejected transitions have no committed equip/drop effect; successful transitions and condition removal retain native event causality; existing clients/replay retain compatible item facts |

Avoid a cartesian explosion: add the smallest cases exposing each failure, retain
existing comprehensive attack-economy coverage, and add cases only where changed
ownership/provenance makes an existing case insufficient. Do not claim the prior
53 passing tests cover these regressions.

## Accepted coating semantics

Accepted coating semantics: an applied physical timed/permanent coating stays
on the item when dropped/transferred; a concentration-linked enhancement also stays
on the item but ends when its original sustainer's concentration ends. Ordinary
unequip does not strip the coating. Destruction retires its item-dependent effect.
Source death/removal must follow existing duration/concentration rules, not a blanket
new rule that deletes all physical coatings. World detachment does not mean death
or terminal disposal.

The duration clock uses the existing encounter/round identity: held/inventory item
conditions advance at the holder's TurnStart, while floor item conditions advance
at a round boundary. Moving a condition between those owners can otherwise count
the same authored round twice. Accepted contract: drop/transfer does not reset,
accelerate or extend the remaining duration, and an elapsed authored interval is
counted once. Identify an existing authoritative timing fact to preserve this
contract during the coating repair; do not introduce a second global turn clock.
Include same-round transfer/drop/pickup and boundary expiry in the public cases.

Reapplication/stacking must be inspected per existing consumable: do not silently
convert an intended replacement into stacked damage. Exact contribution removal
must work whether policy is replacement or coexistence. One condition per display
name cannot be used to collapse distinct weapons' effects.

The plan does not add disarming/harvesting body parts, new bound/conjured roster
rules, Maul/firearms/ammunition, thrown/versatile modes, ranged hand reservation,
magical weapon resistance rules, or migrate all special items to a new composer.
Those stay in the wider item plan. Small typed ownership facts needed by these
four repairs should be reusable there without building that whole system now.

## Independent review

Anti-slop reviewer approves the bounded scope, public failing regressions and
ordinary-item controls. ECS/anti-OOP reviewer approves the revised plan after
correcting world-detachment semantics and declaring coating clock continuity.
Both also reviewed the implementation. Final anti-slop and ECS/anti-OOP reviews
approved the corrected ownership, provisional rollback and native event paths.


## Implementation checkpoint — October 2

- Natural weapons/armor carry explicit intrinsic owner identity; native inventory,
  equipment, drop and pickup transitions enforce it. World detachment preserves
  attached anatomy. Ordinary gear remains transferable.
- Assassin's Dagger resolves its native parent attack's source item UUID before
  adding Unseen Strike. Other weapons receive no borrowed dagger bonus.
- Coatings are weapon-owned conditions. Each removes its exact bonus-value UUID;
  authored damage remains. Transfer retains duration and original concentration
  sustainer. Existing encounter/round facts prevent double advancement.
- Coating replacement uses the native condition owner's required-condition seam.
  Provisional failure releases owned packets/slots directly. Shared accepted
  removal phases are reused within a temporary transaction scope. Concentration
  accepts its own EFFECT before removing the prior graph; pending new slots and
  unrelated retained children survive. Rejected applications at DECLARATION,
  EXECUTION and EFFECT preserve the previous enhancement. Native charges/action
  costs already committed before execution remain spent.
- Wearable definitions expose magical identity; Spellblade Crown declares it and
  retains its existing +3 CHA effect. Disintegrate observes that identity.

Verification after the final concentration correction:

- Complete engine suite: **1,931 passed**, including the 33 new gear regressions
  (210.50 seconds).
- Equipment/replay, architecture dependency/source hygiene and direct-item
  progression selection: **61 passed** (53.91 seconds).
- Independent final anti-slop and ECS/anti-OOP implementation reviews: approved.

Commands used the existing `/home/tommaso/.cache/dnd-engine/venv/bin/python` runtime,
with repository sources under `/mnt/c/users/tommaso/documents/dev/dnd_engine`.

The earlier complete architecture/progression run had 79 passes and five failures:

| Failure | Observed cause |
| --- | --- |
| Current artifact hashes | Recorded hashes differ for `content_icon_bindings.json` and `srd_5_1_source_coverage.json` |
| SRD status inventory | Current coverage has 178 playable/742 missing, while the snapshot expects 177/743 |
| Structural authored-owner count | Current definitions contain 11 identities; snapshot expects 10 |
| Public direct-item inventory | Window insert/wall definitions absent from the expected catalog set |
| Server spell-catalog cold start | Paused server imports missing `dnd.core.senses` |

These concern earlier content/server changes, not the four repaired gear paths.
Their expected results and backend were left unchanged for discussion with the
human. This checkpoint does not claim the entire repository suite is green.
