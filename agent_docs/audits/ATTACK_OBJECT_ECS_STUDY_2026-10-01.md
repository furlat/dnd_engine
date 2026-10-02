# Attack targets and destruction: ECS study

Date: 2026-10-01. Read-only investigation for the attack/object refactor. No
production changes are proposed as already implemented. Scope follows the human's
latest decision: delete `AttackObject`; ordinary `Attack` must accept eligible
objects for melee, ranged and unarmed attacks. Preserve action economy, extra
attacks and creature-specific rules. The main plan owns exact frontend sequencing
and independent correctness review.

## Conclusion

The current split is redundant at the action, weapon and damage-roll boundaries.
It is useful only at the final recipient consequences: creatures can die or enter
dying; items enter their existing destruction lifecycle. Keep those consequences,
the existing Health component and the existing item/placement identities. Do not
create a `Damageable` superclass, a damage service, a second object registry or a
renderer-owned substitute for the missing native facts.

The lean change is one attack workflow, one typed damage-roll workflow, and an
explicitly authored set of eligible recipient kinds. A small number of ordinary
functions select existing owners at the boundary; a passive target/contact value
records the chosen geometry and kind. Targets do not acquire action execution
methods or a new inheritance tree.

## Evidence and defects

| Existing owner | Evidence | Consequence for this refactor |
| --- | --- | --- |
| `Attack` | `dnd/actions.py:1849`, `:2287` | Already creates `AttackEvent`, captures weapon identity, applies action costs and passes through attack/damage result handlers. Preserve this path. |
| Attack declaration | `dnd/actions.py:1770` | `create_weapon_attack_declaration_event` snapshots weapon metadata and source-item presentation. Target lookup is currently creature-only. Generalize the target fact, not the weapon path. |
| `AttackObject` | `dnd/actions.py:5196` | Separate OBJECT action, main-melee slot hardcoded, auto-hit, generic `ActionEvent`. It bypasses ordinary attack-result and damage-result handlers. Delete it after all callers migrate. |
| Mixed damage loss | `dnd/actions.py:5253` | Object attack sums all damage rolls, then submits the total using only the weapon's main damage type. A weapon with an elemental rider incorrectly applies that rider under the main affinity. |
| Item damage | `dnd/blocks/base_item.py:718` | Accepts one typed scalar and creates a synthetic damage specification; no original roll packets are retained. Health and TakeDamage events already exist, but the public item damage entry does not preserve mixed packets. |
| Creature damage | `dnd/entity.py:2971`, `:3008` | Preserves actual typed packets, resolves mixed affinities and owns creature-only survival/death consequences. Do not copy its death-save branch into items. |
| Shared arithmetic | `dnd/blocks/health.py:624`, `dnd/core/damage.py:43` | `preview_damage_components` and `DamageResolution` already express mixed affinity and HP allocation. Reuse them for both recipients. |
| Object admission | `dnd/core/base_actions.py:1251`, `dnd/core/gridmap.py:2400` | OBJECT actions are forced through `manual_object_contact`, whose 5-foot cap is correct for manual interaction but wrong for ranged or reach attacks. |
| Object discovery | `dnd/entity.py:6372`, `dnd/actions_functional.py:97` | Separate AttackObject registration/discovery exists today. Migrate object candidates into the chosen attack's discovery; do not retain a second executor with a renamed label. |
| Item aftermath | `dnd/blocks/base_item.py:593` | Existing accepted `ItemDestructionEvent` owns physical refresh, attachments, connectors, lights, conditions and authored spills. Keep it. |
| Spatial refresh | `dnd/core/gridmap.py:3139` | Exact placement bands are updated and channel revisions invalidated before emitting `SpatialChangeEvent`. AoE must requery this authority after destruction. |
| AoE geometry | `dnd/core/aoe.py:46`, `:239` | Connected propagation reaches a blocking centre cell but stops carrying onward. Boundary blocking returns a Boolean; the current result does not record which blocking boundary received contact. |
| AoE recipients | `dnd/core/base_actions.py:1395`, `:2025` | Shape resolution collects only creature occupants and freezes them before applying damage. No object selection or post-break continuation exists. |
| Fireball | `dnd/spells/evocation.py:830` | Uses connected propagation; `_apply` requires Entity and rolls/saves per creature. `_finalize_aoe` deposits Ashen on the recorded final area. Object damage cannot be added by changing the sprite or residue pass. |
| Prop material | `dnd/content/items/world_prop_builders.py:769` | Furniture material is authored but builders currently pass only HP into item Health. Tags do not constitute fire resistance, vulnerability or flammability rules. |

Native reproduction, run during this study: an ordinary actor attacked a placed
100-HP object immune to fire, using a weapon with `1d6` slashing plus `1d6` fire.
With fixed die faces `6, 6`, `AttackObject.apply()` succeeded and removed **12 HP**.
The completed TakeDamage fact carried only `Slashing`, with one resolution
component `(Slashing, incoming=12, after_affinity=12)`. Correct component affinity
would remove 6 HP. The probe exercised the real public command after normal
runtime bootstrap; no production files were changed.

## Ownership and dependency direction

1. **Cold contracts** remain in dependency-leaf `dnd/types` / existing core
   contracts. They contain identity, enums, coordinates and typed outcomes, with
   no Entity/BaseItem references, renderer assets or callables.
2. **GridMap and placement values** own contact geometry and channel queries.
   They know the exact placed supports and edge providers. They must not import
   `Attack`, `Fireball`, content factories or the renderer to decide damage.
3. **Attack and spell action execution** own attack delivery, costs, rolling and
   recipient selection. They use the existing equipment, Health and target
   owners. A finite spell traversal helper may coordinate geometry and damage;
   GridMap itself must not cast spells as a side effect of a query.
4. **Health** owns damage arithmetic. Creature and item owners retain their
   established post-damage consequences. Shared packet handling can be factored
   into a small function where needed, without moving death or destruction into
   Health.
5. **Item destruction and native spatial events** continue to own physical
   change. The renderer consumes frozen facts and authored timing; it never
   decides which door breaks, what becomes reachable, or which recipient is hit.

`BaseItem` already imports `GridMap`, event contracts and Health. `GridMap`
already queries `BaseBlock` spatial capabilities without importing concrete
items. Preserve that DAG. A resolver needing both Entity and BaseItem belongs
above both, alongside action execution, not inside either owner or the event
schema module. Do not introduce late imports to make a circular extraction run.

## Minimum target and damage changes

- Keep the existing target UUID and weapon slot. Do not create parallel
  `target_object_uuid` / `target_creature_uuid` command fields.
- Author whether an action accepts creatures, objects or both. Ordinary Attack
  accepts both; creature-only effects remain creature-only. Reuse existing
  targeting types where possible, or add one finite recipient-kind declaration;
  do not infer eligibility from a spell name, damage type, VFX key or presence of
  a Health attribute.
- Resolve one cold target/contact value containing UUID, kind, position/contact
  and existing presentation/placement facts needed by playback. Snapshot it at
  accepted execution, since an object can become a wreck or retire before replay.
  Do not duplicate the complete item state if an existing received fact supplies
  it with the required causal lifetime.
- Generalize the existing object surface query to accept authored reach/range.
  `manual_object_contact` can remain the fixed five-foot wrapper for pickup and
  device use. Attack discovery and execution must share the general query.
- Preserve the actual `DamageRollPacket` components through TakeDamage and
  affinity resolution. Add the same optional packet inputs to the item boundary,
  or introduce a cold packet value only if that prevents repeated lossy scalar
  conversions. No generic dictionary payload or second damage arithmetic path.
- Decide object hit resolution explicitly. Current object attacks auto-hit and
  item profiles have no AC. Preserving that rule while unifying weapon delivery
  is smaller than silently inventing object AC. If the human chooses AC, author
  it as item defense data and exercise the same attack-roll event lane. It is a
  gameplay decision, not a necessary inheritance change.
- Natural/unarmed attacks should be represented by the same existing equipment
  fallback/attack choice. No dummy invisible weapon is needed to hide a bow.
- Every target-sensitive attack handler must check actual recipient eligibility.
  Adding objects to Attack must not cause creature-only smites, marks, conditions,
  reactions or blood releases to acquire object behavior accidentally. The
  correctness reviewer owns the exhaustive economy/feature matrix.

## Placement requirements that must survive

`WorldObjectPlacement` already contains complete `covered_supports`, orientation,
height bands and a boundary direction (`dnd/types/world_placement.py:52`). There
is no need for new multi-cell storage.

- Use any reachable exposed support of a multi-cell target, not just its anchor.
  A two-cell wagon is one item and one damage recipient.
- A boundary object can be contacted from either adjacent support, including
  when the canonical owner tile lies beyond the blocked edge.
- Exempt only the actual terminal target provider during the contact query, as
  `can_reach_between(..., terminal_provider_uuid=...)` already does. Other
  intervening objects, parallel boundaries and unrelated attachment components
  remain physical barriers.
- Keep contact channels separate from visibility. A known closed transparent
  object can be targeted without allowing an attack through it. An open window
  can admit a Light weapon while denying a heavy one.
- Existing `supported_by_uuid` describes a wall/insert assembly independently of
  inventory ownership. Do not turn the insert into an anonymous visual fragment.

## Fireball contact and breach

The human proposed same-cast continuation through a door destroyed by the blast.
This is a bounded resolution rule; it must be explicitly authored for the spell,
not added as a universal side effect of all damage or all connected areas.

The proposed finite contact rounds are sound under these constraints:

1. Freeze the original geometric envelope and spell origin once. Preserve the
   spell's authored damage-roll contract; resolve each newly affected recipient
   once, without rolling again when the footprint is recomputed. Fireball
   currently rolls per recipient, so shared dice for the whole cast would be a
   separate rule change.
2. Compute the reached region using current native channels. Gather creatures
   and eligible exposed objects in that region, plus **blocking boundary
   providers encountered on its frontier**. Looking only at
   `get_objects_at(reached_cells)` is insufficient: a door can be registered on
   the far side of the edge that blocked entry.
3. Use the existing edge contributions from both sides of `get_world_edge` to
   identify such providers. Exact channel and height rules stay with the map.
   Geometry reports contacts; the spell decides eligible recipients and applies
   its damage.
4. Deduplicate objects by UUID for the entire cast, not by tile or contact face.
   Each active object receives at most one packet for this blast even if it
   covers multiple cells, appears on multiple boundary contributions, or is
   encountered again after another obstruction falls.
5. Let ordinary TakeDamage → ItemDestruction → SpatialChange run. Never clear an
   edge speculatively because its damage estimate exceeds HP: immunity,
   reduction, cancellation, another intact boundary and destruction consequences
   may leave it blocked.
6. Requery map channels after those accepted changes. Continue only into newly
   reachable cells within the original envelope, then apply damage only to new
   recipients. A strong or immune door remains a barrier. A destroyed door does
   not become another explosion origin and does not refresh the damage roll.
7. Stop when no new cells/eligible contacts are reached and no frontier topology
   changed. With finite cells and once-per-item damage this has a natural bound;
   no frame loop, raymarching simulation or arbitrary safety iteration count is
   required.

For simultaneously exposed wall/insert components, use deterministic
parent-before-supported-item resolution and skip children already destroyed by
the parent's cascade. Do not independently animate a second hit/destruction on a
child that ceased to be active. If the insert is the only initially contacted
blocking component, resolve it normally; its parent remains independently active.
This preserves existing once-only assembly semantics.

Transient consequences such as oil ignition remain separate native owners under
their actual destruction cause. Their damage is not another application of the
original Fireball and must not be accidentally deduplicated with it. Conversely,
do not grow the original Fireball envelope to include an oil spill's extent.

### Minimal causal recording

The root spell's final `resolved_area_positions` alone is insufficient for a
breach: playback would show damage behind the door while its intact pixels remain.
The native result needs ordered reached-region steps and the actual destruction
lineages that allowed each later step. These are facts, not timestamps.

Prefer a small passive step value or finite child fact containing:

- added/reached positions for this step;
- stable step ordinal;
- actual prerequisite destruction lineage(s), empty for initial contact;
- a way to associate ordinary per-target application IDs with the step.

Use the existing action application ID and lineage machinery; do not introduce
a parallel scheduler graph or generic dependency framework. Exact placement on
the root event versus a typed child event should be chosen with the renderer
owner after checking replay admission. Merely relying on list order of damage
events is not a durable causal contract. Neither is a native field containing
animation milliseconds.

The renderer must wait for the relevant destruction's **authored physical
clearance**, not its final debris frame, before revealing later reached regions
and delivering their effects. The authoritative backend resolves immediately.
Existing subjective event filtering must apply to the new fact so object contact
does not reveal hidden rooms or occupants. No cloud compositing or XYZ ownership
rule needs to change for this attack refactor.

## Destruction behavior to preserve

`BaseItem.destroy` is idempotent and has a reentrancy guard. Persistent aftermath
keeps the same item UUID and authored family; `retire` is the separate terminal
removal path. `ItemDestructionEvent` retains previous item/placement state, then
ordinary descendants reindex supports and channels, remove connectors, destroy
supported children, stop item-sustained conditions/light, and generate authored
spills. This contract is already exercised in:

- `tests/engine/test_item_destruction_events.py` (causality, same UUID, aftermath,
  no second destruction, spills/ignition);
- `tests/engine/test_multicell_objects.py` (coverage, placement and destruction);
- `tests/engine/test_windows.py` (parent/insert independence and once-only cascade);
- `tests/engine/test_environment_prop_access.py` (physical channel differences).

Do not replace wrecks with generic debris entities or clear objects directly from
GridMap in attack/spell code. Do not move object physics into renderer callbacks.

## Acceptance gates

1. Ordinary discovered Attack targets creature, adjacent object, ranged object,
   a reach-weapon object and unarmed object with correct loadout and the same
   weapon/packet event evidence. No discovered `action.attack_object` remains.
2. Mixed slashing/fire damage against differently resistant objects preserves
   both affinities and accurate TakeDamage/Destruction cause types.
3. Attacking a far cell of a rotated multi-cell body works, while shooting
   through the intact body does not. Either side of a boundary works; an
   unrelated intervening blocker rejects before costs.
4. Fireball hits an exposed closed door; surviving/immune doors contain it,
   destroyed doors allow only in-envelope continuation. No recipient is damaged
   twice across reach rounds and no already cascaded insert breaks twice.
5. Two sequential destructible barriers produce two causal expansion steps;
   an undamaged parallel provider prevents continuation. Reversed construction
   order does not change results.
6. Oil spills, device concentration and lights still terminate/transform under
   their destruction lineages. Same-UUID wreck physics survives serialized replay.
7. Four-view event-driven clips show bow → melee → empty hands, real projectile
   object impact, intact/destroyed door blast, and a wall/insert assembly. Later
   blast effects do not appear before the blocking art clears. Pixel review
   verifies weapon identity, not only absence of presentation gaps.

This is an ECS-compatible bounded direction. Approval of the eventual plan
depends on the explicit object-hit and spell-object eligibility decisions and
the separate correctness review for economy and creature-only effects.

## Follow-up: one inventory and execution seam for attack choices

The human explicitly permits ordinary polymorphism / finite branches and asks
for a helper exposing every attack choice, including Frenzy. This does not
require another registry or a broad new attack-class hierarchy.

Existing `BaseAction.is_attack` already tests `ActionCategory.ATTACK`
(`dnd/core/base_actions.py:945`). `AvailableActionInfo.is_attack` exposes the same
classification on discovery rows. `get_discovery_variants` already expands
registered templates, including restricted-action grants, and retains the exact
registered template UUID (`:1536`). Reuse those facts.

| Current attack producer | Execution seam / real distinction |
| --- | --- |
| Ordinary equipped `Attack` | Registered per slot by `actions_functional.update_weapon_template`; shared declaration, `_validate` and `attack_consequences`. Normal main action versus offhand bonus cost belongs to the chosen action. |
| `ExtraAttack` | Currently repeats target/visibility validation and then calls the same `Attack.attack_consequences`; consumes `extra_attacks`, requires earned marker, expands equipped slots (`classes/fighter.py:1268`). |
| `FrenziedStrike` | Currently repeats target/visibility validation and then calls the same consequence function; requires Frenzied state and selected melee capability, costs one bonus action (`classes/rage.py:921`). `Frenzy` itself is setup, not an attack. |
| `NaturalAttack` | Already subclasses Attack but rewrites live main-hand equipment and unarmed dice temporarily during prediction and application (`monsters/traits.py:588`, `:675`). This is not clean source selection. |
| Opportunity attack | Reaction handler constructs ordinary Attack with reaction cost and the handler's behavior binding; triggered by creature movement (`reactions.py:19`). It is not a registered on-turn menu choice. |
| Retaliation | Damage-triggered handler constructs an Attack with empty child costs, then spends reaction after success (`classes/barbarian.py:1061`). Cost/provenance semantics must be retained or deliberately corrected with tests; enumeration cannot synthesize it as a free normal action. |
| Monster `MultiattackAction` | Parent spends one action and authors ordered `(slot,count)` steps; children are ordinary zero-cost Attacks (`monsters/traits.py:517`). It is a composite attack choice, not one weapon swing and not the player's Extra Attack entitlement. |
| `TrueStrike` | Spell root executes a no-cost ordinary Attack with ability override; temporarily mutates equipment bonus-damage arrays (`spells/evocation.py:3850`). Preserve spell root cost/identity and child-attack causality. |
| Attack-roll spells | Remain SpellAction choices with `ActionOutcomeProfile.resolution == ATTACK_ROLL`; they are not eligible for weapon-only action grants just because they roll to hit. |

### Proposed small change

1. Add a helper/property returning the actor's registered attack templates, or
   their normal discovery variants, by existing `is_attack`; document which
   stage it returns. Do not rebuild costs, names, bindings, availability or
   grants in this helper. Registered actions remain the membership authority.
2. Keep the UI-facing helper about discoverable attack choices. For an audit of
   **all attack-roll** actions, additionally query the existing outcome profile
   resolution on non-attack rows; do not silently make that broader set eligible
   for Haste or Extra Attack. Reaction handlers stay separately enumerated as
   triggered producers. No new AttackKind field is needed just to form this list.
3. Make existing `ExtraAttack` and `FrenziedStrike` thin `Attack` specializations.
   They retain their authored names/semantic bindings, costs and source/slot
   prerequisites, but inherit the one declaration, target-contact validation,
   damage-roll and result path. This is reuse of existing action behavior, not a
   new entity ownership hierarchy. A source-prerequisite hook should be called
   once by the shared path and equally by discovery and execution.
4. Explicitly neutralize inherited `restricted_action_kinds` on resource-spending
   extras/Frenzy. Do not let subclassing turn bonus/resource/reaction actions into
   Haste's one-weapon-attack option. Normal Attack/Haste/Surge grants must retain
   their actual receipt and registered-template identity.
5. Keep Multiattack's parent sequencing, but execute each strike through the
   same attack source/recipient path. Preserve its stop condition when its target
   ceases to be active. Object targets must not be implicitly granted to all
   creature-only reaction or stat-block policies merely because the inner strike
   can resolve object contact.
6. Use one pure selected attack-source resolver for equipped, unarmed and natural
   sources. A small passive declaration of source kind / selected slot / existing
   natural damage-and-range values is enough; do not construct fake equipment.
   NaturalAttack overrides that source selection instead of changing the actor's
   equipment in a `try/finally`. Explicit unarmed choice with a bow/sword still
   equipped needs the same distinction. Existing bonus/modifiable-value owners
   must remain in the calculation; pure source selection is not permission to
   replace their logic with raw dice.
7. Pass True Strike's attack-local damage rider via this existing attack input
   boundary, if included in the final patch, rather than mutating equipment
   globally. This is one affected producer, not a rewrite of spellcasting.

Ordinary Attack target unification and source selection are the common work.
Frenzy/extra/reaction policies stay visibly authored and testable. The helper
must never claim that every listed action has the same eligible recipients,
weapon slots, cost source or action-multiplicity entitlement.

## Independent consolidated-plan review

Reviewed `agent_docs/ATTACKS_AND_DESTRUCTIBLE_OBJECTS_PLAN_2026-10-01.md` after the
initial study and follow-up. **Approved from the anti-OOP/ECS perspective.** There
is no remaining architecture blocker in the written plan.

- The new query-only `performs_attack` predicate is justified: some spell-attack
  outcome profiles are absent, so the existing probability profile is not a
  complete or appropriately cheap membership source. The predicate is explicit
  authoring data, defaults to the existing attack category, and is expressly
  forbidden from authorizing Haste, Extra Attack, recipient kinds or costs. It
  does not become a parallel attack registry or behavior dispatcher.
- ExtraAttack and FrenziedStrike reuse the existing action owner while preserving
  their identities/costs/source gates. Explicit restricted-grant neutralization
  closes the inheritance hazard. This is acceptable ordinary polymorphism under
  the human's clarification, with no new entity inheritance framework.
- Pure equipped/unarmed/natural source selection removes live equipment mutation
  and still retains the existing modifier-aware calculations. True Strike's
  additional input stays local to its child attack.
- Recipient facts are passive; one finite target-kind branch chooses existing
  defense/application owners. Health arithmetic, creature consequences, item
  destruction and GridMap physical changes remain with their actual owners.
- Finite area reach/contact stages query exact native geometry, retain one cast
  envelope, process each recipient once and record real causal destruction
  prerequisites. They do not ask GridMap to execute spells or the renderer to
  decide which objects are destroyed.
- Presentation consumes filtered stage/target facts with authored clearance;
  native data does not contain animation times. Original records are preserved
  without retaining a second live AttackObject implementation.

The object-AC and Fireball structural-damage proposals remain explicit human
gameplay choices before implementation, as the plan states. That is a rule gate,
not an ECS deficiency. The implemented patch still needs the planned native,
serialization, visual and correctness reviews; this approval is for the design.

## Final amendment review: commitment, grants and Slow

Reviewed the amended section 2 of the consolidated plan. **Approved; no remaining
anti-OOP/ECS design blocker.** Numeric multiplicity and suppression belong to
ActionEconomy, with source-owned contributions and cleanup. Adapting the legacy
ExtraAttackFeature to that existing grant owner avoids two competing counts.

Moving ExtraAttacksGranted from fighter to `dnd/conditions.py` preserves the
dependency DAG and uses the existing home for turn-lived attack facts. Committing
the batch before cancelable EXECUTION dispatch removes listener-order dependence.
Parenting its marker to the already published DECLARATION is necessary because
the EXECUTION value supplied to `_apply_costs` is still detached. Preserve the
same action lineage and exactly-once grant across phase dispatch.

Slow's cap is passive source-owned economy data, consulted by both commitment
and extra-attack admission. The stated policy to discard an existing batch when
Slow enters, without restoring it when Slow leaves, remains explicit; a later
ordinary paid Attack can earn a fresh batch. Neither action code importing the
Slow condition nor listener-priority ordering is needed. Validation must still
exercise both feature/condition installation orders and cancellation on each
side of cost commitment. This review made no production changes.

## Implementation review and native corrections

The implemented ownership remains consistent with the approved ECS design:
`Equipment` snapshots the selected source; `Attack` owns the existing shared
strike lifecycle; `Health` evaluates typed damage; `BaseItem` owns destruction;
`GridMap` answers contact/reach queries and receives normal lifecycle changes.
Natural attacks supply a passive `NaturalWeaponSpec`; True Strike supplies
attack-local extra damage. No fake equipment, damageable hierarchy, parallel
attack registry or client-authored rules were introduced.

The independent review found and corrected these actual integration gaps:

- Device spell object contacts measured from the operator instead of the
  emitter. The existing map contact query now accepts the action's actual
  origin while retaining the operator's subjective knowledge.
- The new combined target mode was omitted from device sector validation,
  item-use object discovery and stable unavailable item rows. Both creature and
  object Fire Bolt targets now follow the same existing device constraints.
  Discovery reports a reachable multicell contact instead of a distant anchor.
- Fire Bolt continued after a canceled EFFECT and could attempt a destroyed
  object after EXECUTION handlers. It now respects cancellation and repeats
  native eligibility/contact checks before applying damage.
- Globe's shared spell handler looked up only creatures. It now protects the
  recorded object contact too; Fireball's local duplicate protection check was
  removed. The existing protection owner remains authoritative.
- True Strike retained a five-foot spell range when using a bow. Its existing
  range interface now reads the selected weapon, preserving child Attack
  long-range handling. Its metadata getter reads Equipment directly instead
  of constructing an ephemeral Attack to query equipment.
- Source metadata now uses `Equipment.snapshot_attack_source_metadata` for
  ordinary declaration/discovery and True Strike. The architecture test names
  the single declaration constructor now also used by NaturalAttack.

`AreaReachEvent` is passive causal data: stage index, newly reached cells,
previous stage lineage and prior blocker-destruction lineages. Each target
application is a child of its stage. Fireball queries a fixed original envelope
after real destruction, visits each recipient at most once, resolves parents
before attached inserts, and records the cumulative actual affected footprint.
No native phase or geometry query uses an animation frame or duration.

Validation recorded during this review:

- 30 focused Fireball footprint, staged breach and Globe checks passed.
- 21 natural-source purity, staged Fireball/Globe and shared-declaration checks
  passed. Purity is observed during native attack events, not merely after a
  temporary mutation might have been restored.
- 11 spell-object routing, item availability and ordinary object attack checks
  passed, including reproduced device-origin/sector and canceled-impact bugs.
- 143 broader device, prop access, window access and True Strike presentation
  checks passed.
- Scoped native typing completed with zero errors.

The shared DamageRollResultEvent cancellation hole was reproduced for both
creature and object targets, then fixed before HP application. Thirteen final
attack-source/object-spell checks pass, including both cancellation regressions
and unchanged spent action costs. The correctness reviewer also explicitly
neutralized restricted-grant metadata on ExtraAttack/FrenziedStrike, matching
the reviewed plan in addition to the existing cost guard.

**Native ECS review approved.** Full-suite and saved-event visual acceptance
remain root-task gates; these bounded native results do not claim that staged
breach presentation has already passed those gates.

### Full-suite follow-up: authored remote controls

The new source-item reach check also rejected the existing lever's remote
door/light action. Restored this through an explicit per-execution controller
UUID, validated against the handle's existing typed authored link and physical
reach to the handle. `BaseBlock.get_item_control_link` is a neutral query;
`ControlLever` owns target-kind validation through its existing linked-item
resolver. No concrete lever dependency enters the action core, and neither
event parentage nor an arbitrary target UUID confers remote access. The private
controller value is restored after execution. Pressure plates retain their
existing native control operation.

All 73 environment-control, pressure-plate and spell-device checks pass,
including repeated remote activation, occupied-door rejection, invalid link
identity/kind, distant or missing controllers, ordinary nested calls without
authority, and displacement of the operator during nested execution. Scoped
typing for the changed native owners reports zero errors.

### Final frontend ECS review

**Approved after one reproduced correction.** `stage_lineage` was advancing
existing object geometry to future world updates before binding: a lethal
bookshelf attack aimed at height 0.5 (the wreck) instead of height 1.0 (the
intact object). Staging now supplies only absent binding contacts; historical
objects, tiles and connectors retain their original values until actual
prefix reduction. A cold saved-event regression verifies the intact impact
contact and the distinct final wreck geometry.

No further blocking ownership or dependency issues were found in the reviewed
scope. Native `AreaReachFact` and destruction prerequisites supply causal
facts; the presentation layer alone translates authored clearance into time.
Dense serial destruction retains one continuous explosion clock. Observations
and visibility gate newly revealed bodies, object contacts remain distinct
from creature rigs, and completed Idle samples use the ordinary scene clock.
The native engine is not invoked during sampling. Twenty focused breach,
object attack, True Strike and recovery checks passed, followed by the new
lethal-contact regression passing against the corrected staging behavior.
The root task retains responsibility for the complete-suite and visual gates.

### Approved removal completion: active icon residue

Removed exactly the retired `action.attack_object` definition from the active
icon ledger and its six-line generated Python mapping. The existing importer
rendered that single row and recomputed the ledger's canonical binding digest;
all unrelated rows and the ledger's CRLF formatting were preserved. Full
regeneration was deliberately avoided because the legacy ledger and generated
selection have broader preexisting differences. The original NeuroClient source
row and archived evidence remain unchanged. `PRESENTATION_CONTRACT.md` now
describes the shared Attack/contact path instead of the removed object recipe.

Validation loaded the authenticated ledger, checked both active mappings and
native declarations contain no retired identity, and searched executable/native
and presentation data for the old command. Only the explicitly historical source
row and its documentation remain. Icon closure now reports `unknown=[]`; the
same 11 unrelated missing icon dispositions remain deferred for discussion.
