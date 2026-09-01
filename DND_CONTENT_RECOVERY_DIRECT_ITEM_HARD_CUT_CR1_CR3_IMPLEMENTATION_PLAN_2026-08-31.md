# Direct-item recovery hard cut (corrected CR-1/CR-2I/CR-3 plan)

Date: 2026-08-31  
Status: ACCEPTED FOR SLICE 0 — production implementation remains forbidden until the Slice 0 checkpoint is reviewed

## 1. Outcome

Recover the complete 147-item direct inventory through the current ECS without
leaving a registry/direct compatibility bridge.

The finished cut has:

- one direct namespaced `item_id` on every runtime item and item Event fact;
- frozen plain item definitions plus explicit domain builders;
- direct starting holdings, class/apparel loadouts, creature possessions,
  containers, and world placements;
- silent initial inventory/equipment installation inside the existing
  unpublished Entity composition boundary;
- ordinary post-birth inventory/equipment/world mutations continuing to
  publish their current committed Events;
- exact stack, quantity, charge, durability, equipment-footprint, intrinsic,
  container, world-placement, and failure-cleanup behavior;
- existing item visual fields and values frozen for CR-8, without making them
  mechanical authority or adding consumers; and
- no item/environment-object `ContentRef`, recipe, preset, declaration factory,
  generic item materializer, or `ITEM_RUNTIME_BINDINGS` entry/path.

This is not a new item framework. Items remain `BaseItem`/equipment ECS data,
Inventory and Equipment remain the mutation owners, Entity remains the
composition coordinator, GridMap remains the world-placement owner, and Events
continue to report committed facts.

## 2. Governing authority

| Authority | Frozen identity |
|---|---|
| Current checkout | `205fd679fde51d5319d332f12ec241d7aecd93a6` |
| Master recovery plan | `DND_JULY_RECONSTRUCTION_CONTENT_RECOVERY_AUDIT_AND_MIGRATION_PLAN_2026-08-30.md`, SHA-256 `3e6a38a534331f0cdf92127fe5d9b765bf7e81a7d44baee08876bfd1613bec7b` |
| CR-0 completion ledger | `DND_CONTENT_RECOVERY_CR0_COMPLETION_LEDGER_2026-08-30.md`, SHA-256 `b04eb0ed05d8e8d17a3c2136f9454aa9d08c22712c0ed63da551832eec1f09ef` |
| CR-0 evidence manifest | `content_data/ledgers/content_recovery_cr0_evidence.json`, SHA-256 `fdcd5c32b7ded90bb52e94fbb492181416b735eaddc4a3e0956540b613dbaa65` |
| Repository policy | `AGENTS.md`, SHA-256 `296ce0a99c52fab93261a15e193258b928c0b56c161b91ef8e412f5d27897668` |
| Test policy | `HOW_TO_TEST.MD`, SHA-256 `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |
| Accepted behavioral evidence | commit `513dd97`, mined by capability/value only |

Current code is implementation authority for owner boundaries, lifecycle,
Events, placement, and import direction. The accepted checkpoint is evidence
for direct IDs, exact values, and expected outcomes; no whole file or later
package topology is transplanted.

## 3. Why the literal CR-1 order cannot be implemented safely

CR-0's `target_cut` values are coarse planning dispositions, not mechanical
family proof. Direct inspection found two non-negotiable couplings.

### 3.1 The alleged behavior-free set contains behavior-bearing items

The CR-0 rows assigned to CR-1 include:

- `weapon.assassin_dagger`, which installs an equip-scoped damage handler;
- `weapon.arcane_staff`, which installs an equip-scoped spell-attack modifier;
- `apparel.spellblade_crown`, which installs an equip-scoped Charisma modifier;
  and
- padded, scale, half-plate, ring-mail, chain-mail, splint, and plate armor,
  which install reversible stealth and/or Strength movement modifiers.

The master plan itself assigns hook-bearing equipment to CR-3 and requires its
behavior families to be made direct first in CR-2. Treating these rows as
behavior-free would contradict the plan's behavior-family law.

### 3.2 Maintained holders mix mundane and behavior-bearing items

Legacy item identity is stored in `ContentRecipe` by:

- `CharacterItemV1` holdings;
- starting equipment/apparel/background packages;
- creature-possession grants;
- scenario/container/world builders; and
- the global item-runtime binding.

Maintained premades mix ordinary weapons/apparel with healing/haste potions,
portable torches, hook-bearing chain mail, and Spellblade Crown. Three Fighter
starting packages contain hook-bearing chain mail. Consequently, a literal
mundane-only hard cut would need at least one forbidden construct:

- optional `recipe` versus `item_id` fields;
- a legacy/direct discriminated migration union;
- a materializer that converts old recipes into direct IDs;
- a generic caller switch between registry and direct construction; or
- two constructible definitions for the same item.

All are compatibility membranes or dual construction authority. They are
rejected.

## 4. Narrow sequencing correction

The master outcome and family laws are unchanged. Only the item sub-track is
ordered according to its real dependency graph:

1. **CR-2I:** migrate only behavior families required by the 39
   behavior-bearing public items, without otherwise changing item construction;
2. **CR-I:** perform one atomic candidate covering the forced Guardian of Faith
   behavior/source/object family, the shared `BaseItem.item_id` cut, the 108
   behavior-free items, the 39 behavior-bearing items, all holders/callers,
   and the generic item runtime; then
3. resume the master plan at CR-4, while all remaining non-item behavior
   families remain scheduled for CR-9.

No production part of the 108-item direct path lands before CR-2I is complete.
That avoids a dormant parallel catalog and avoids modifying a durable record
to carry both old and new identities.

This correction combines the implementation responsibilities originally
spread across CR-1 and CR-3 and advances only the exact Guardian dependency
from CR-9 inside the inseparable CR-I candidate. It does not pull in origins,
class progression, premades, monsters,
scenarios, Pygame, or general CR-8/CR-9 work. Those domains are touched only
where they are active item holders or item callers.

## 5. Exact item inventory

The expected direct inventory is mechanically derived, not assumed:

- 108 behavior-free IDs listed in Appendix A;
- 39 behavior-bearing IDs listed in Appendix B; and
- total: **147 unique item IDs**.

The canonical value is the sorted, newline-terminated set of non-null
`reconciled_public_semantic_id` values on CR-0 item/environment-object rows:

- row count: **147**; and
- SHA-256: `04966a28ddf9fae4b413f0d101b61a262e26f76395475d54a4029874b583436d`.

Appendices A and B must equal that set exactly, not merely reproduce its
count. Slice 0 writes the mechanically regenerated sorted set and hash to the
implementation ledger and fails on any symmetric difference.

This is the **public authored/buildable item inventory**. The spell-private,
non-authorable, non-lootable transient object
`environment.spell_object.guardian_of_faith` also becomes a direct
`BaseItem.item_id` fact because every BaseItem shares that field, but it is
constructed only by the Guardian spell and is not admitted to the 147-key
item definition/builder table. Architecture gates distinguish the exact
147-key public builder set from this one direct private runtime object; they do
not pretend the latter is a 148th public item.

The 147 count reconciles the accepted direct-item inventory with current Oil
Barrel ownership. Slice 0 must regenerate this inventory from current +
accepted evidence and stop if the set differs. A count difference is not fixed
by silently adding or dropping an ID.

The 205 legacy recipe-preset rows are renderer-binding/source evidence, not
205 additional mechanical item species. Their exact rows and hashes remain
preserved by CR-0 for CR-8. Only the 20 accepted semantic wardrobe variants in
Appendix A are direct mechanical item IDs.

## 6. Target design

### 6.1 Identity and Event facts

- Replace item-instance `semantic_key`/`content_ref` ambiguity with one required
  `item_id: str` on `BaseItem`.
- Validate its namespaced shape locally at the item boundary. Do not introduce
  a universal semantic-ID object or import a content-domain enum into core.
- Delete `BaseItem.get_semantic_key()`; every item-specific consumer reads
  `.item_id` directly. Generic action/condition/Event semantic APIs are a
  different domain and are not renamed by this cut.
- Replace `ItemPresentationState.content_ref` and `semantic_key` with the same
  required `item_id` after the complete 147-item caller cut.
- `ItemLocationStateEvent`, `EntityCreatedEvent`, and
  `ItemChargeConsumptionEvent` carry the same direct `item_id`.
  `GameSummary` charge accounting consumes that field. No item Event fact
  keeps an `item_semantic_key`, `semantic_key`, or `content_ref` alias.
- Those Events continue carrying the complete item state. They do not resolve
  definitions or inspect content.
- Runtime UUID remains the item-instance identity. `item_id` is the authored
  species/behavior root.

There is no `ItemId` class hierarchy, universal `SemanticIdentity`, registry,
lookup service, or Event subtype solely for migration.

### 6.2 Cold definitions and direct builders

Use frozen data composition, not an OOP content hierarchy:

- one small frozen metadata value for common name/description/tags and the
  temporarily retained visual fields;
- separate frozen weapon, wearable, fixed-gear, and static-world-object rows;
- no definition inheritance and no polymorphic `build()` methods;
- read-only maps/tuples owned under `dnd/content/items`;
- explicit category builder functions that construct existing concrete ECS
  item types; and
- at most one small item-domain dispatch map from the 147 IDs to concrete
  builder callables.

The dispatch map is a direct Python selection table. It has no JSON parameter
language, factory strings, declaration objects, pack/version/hash data,
runtime installation, plugin behavior, or cross-domain registration.
It is immutable/non-installable, and an architecture gate requires its exact
key set to equal the canonical 147-ID set hash in section 5.

Behavior-bearing builders reuse their existing concrete item/action/condition/
light/spatial owners after CR-2I. Oil Barrel keeps its current direct material
transition and is never rewritten as a generic spatial recipe.

### 6.3 Visual debt boundary

CR-I does not invent the future Pygame binding system.

- Preserve the current item-instance visual fields and exact active values.
- Do not add a renderer import or a new visual consumer.
- Remove recipe-preset/declaration construction authority when the item hard
  cut occurs.
- Preserve these exact CR-0 artifact pairs and source bytes as CR-8 evidence:

  | Pair/rows | Current artifact | Accepted artifact |
  |---|---|---|
  | `authored_item_visuals`, 283/283 rows | `current.authored_item_visuals`: `content_data/ledgers/neuroclient_authored_item_visuals.json`, SHA `7850493fb83395a363110e0c5e99d9da69a287a7b1f663c4906715af41ce7a4a` | `accepted.authored_item_visuals`: `513dd97:deprecated/content_data_deprecated/ledgers/neuroclient_authored_item_visuals.json`, SHA `267ef479048dfd2fc52d78037e29becbd74d7ccc8939194a94dc44fa49118f08` |
  | `recipe_preset_icon_bindings`, 205/205 rows | the `recipe_presets` rows in `current.icon_bindings`: `content_data/ledgers/content_icon_bindings.json`, whole-artifact SHA `2129a753a0ad13d5fa472ad9dd9a3b354ae0f73299b753d12ef520ac17736ec8` | the `recipe_presets` rows in `accepted.icon_bindings`: `513dd97:deprecated/content_data_deprecated/ledgers/content_icon_bindings.json`, whole-artifact SHA `308d849b8e6e930409a611ace81fe86f819d9b370979882f7d3c0543252c7bbd` |
  | `icon_definition_bindings`, 669/671 rows | the `definitions` rows in the same current artifact | the `definitions` rows in the same accepted artifact |
  | `game_icon_asset_index`, 515/521 rows | `current.game_icon_asset_index`: `content_data/ledgers/neuroclient_game_icon_asset_index.json`, SHA `da24829f890902b37e79ea4e31fff2893ff184db2fc6eea36877c22081b2ed8f` | `accepted.game_icon_asset_index`: `513dd97:deprecated/content_data_deprecated/ledgers/neuroclient_game_icon_asset_index.json`, SHA `1cf4d2620016b27e94591c1a757401e49a1e195fdc9b5b831d3abf84f71a7da4` |

- Preserve the complete CR-0 `python_binding_overlay` (788 rows) as historical
  evidence. The item-relevant row set is the union of direct
  item/environment definition-presentation rows for Appendix A+B, the private
  Guardian object, and the retired `environment.door` collision source;
  item/environment presentation literals, the four premade holding rows,
  bestiary/configured-SRD wardrobe rows, and Field Kit rows. Slice 0 freezes
  their sorted `semantic_id` set, row count, normalized hash, and source
  locations before any owner moves.
- Remove only the migrated item rows from active generic-content icon closure
  when required to delete their declarations; do not delete the source/evidence
  ledgers or asset files.
- Record every such row in the implementation ledger as `preserved_for_CR8`,
  not `obsolete`.

Backend instance fields are deleted only in CR-8 after `/game` bindings exist.
Catalog/server presentation is out of scope and cannot keep item construction
alive.

### 6.4 Initial placement

Initial placement remains an ECS composition operation:

- Inventory owns capacity, weight, stack compatibility, storage membership,
  and location stamping.
- Equipment owns slot resolution, footprints/conflicts, reparenting, active
  weapon-set reconciliation, and equip hooks.
- Entity coordinates a tuple of already-built items while it is unpublished
  and undeployed.
- Initial installation calls the same pure validation and commit mechanics as
  runtime placement but suppresses transition/location Events because the
  complete state is published once by `Entity.compose_entity`.
- Runtime loot/equip/unequip/drop remains unchanged and eventful.

The implementation uses explicit owner methods and ordinary control flow. It
must not use callbacks, undo closures, context managers, command objects,
transaction wrappers, receipts stored in a registry, or a loadout manager.

Before mutation, the coordinator validates the whole initial tuple for:

- inventory capacity and weight;
- authored stack uniqueness and limits;
- equippable type and compatible slot;
- multi-slot footprint collisions;
- pre-existing equipment collisions; and
- final item state (quantity, charge, durability, intrinsic/pickable policy).

After validation it installs in deterministic order. If an item hook or later
composition step fails, the existing unpublished-Entity failure boundary
discards the whole provisional aggregate. It publishes no item/equipment/
world Event and leaves no BaseBlock/action/handler/light/spatial/GridMap/item
binding residue.

### 6.5 Loadouts, holdings, possessions, and containers

Every item holder stores direct data:

- `item_id`;
- final authored quantity;
- optional equipment slot;
- direct finite state when applicable; and
- only holder-specific disposition needed by the actual owner (intrinsic,
  inventory, equipped, contained, or world placement).

Starting equipment/apparel/background plans become frozen semantic plans.
Creature-possession grants become frozen item-ID placements.

Durable character holdings use one replacement schema rather than a
legacy/direct union:

- `CharacterItemV2` contains `schema_version=2`, `character_item_id`, required
  `item_id`, quantity, optional remaining charges, optional durability damage,
  optional equipped slot, and `character_item_digest`;
- its canonical digest input is exactly those fields in canonical JSON, with
  `item_id` replacing the complete recipe payload;
- `CharacterHoldingsRevision` becomes schema version 2, contains only
  `CharacterItemV2` rows, and authenticates their complete direct serialized
  values in its existing deterministic item order;
- schema-1 recipe payloads are not accepted through a compatibility parser;
  all maintained callers/fixtures are migrated atomically; and
- `ItemAugmentationRecord` and `durable_augmentations` are removed. Non-empty
  augmentations have no working runtime materializer today and hydration
  already rejects them, so they are unsupported speculative schema rather than
  recovered behavior. Old augmentation/recipe fields fail closed under the
  direct model's `extra=forbid` and schema validation.

Integrity proofs cover deterministic digests, item/holdings tampering, wrong
schema, forbidden old recipe/augmentation fields, charge/durability bounds,
and failed hydration without partial runtime state.

Specific weapon proficiency is part of the same item identity closure:

- `CreatureProficienciesConfig.base_weapon_ids`,
  `CreatureProficiencies.base_weapon_ids`, and
  `specific_weapon_sources` use direct `item_id` strings;
- `add_specific_weapon_source` and `is_weapon_proficient` accept the direct
  item ID, preserve source-owned add/remove behavior, and perform no item
  lookup;
- Entity attack calculations pass `weapon.item_id`; and
- `EntityCreatedEvent.weapon_proficiencies` publishes category values plus
  exact direct weapon IDs, with no `ContentRef.identity_key` encoding.

Containers store built item instances. World/scenario callers invoke direct
builders and then the current GridMap/item placement owner.

Existing package/class/creature/scenario declarations may remain for their
unmigrated owning domains, but none may contain an item `ContentRef`, item
recipe, item factory dependency, or item materializer callback after CR-I.
Their later domain cuts remove their own declaration identity.

This is the only staged holder exception: a legacy
*class/monster/scenario* identity may hold a direct item plan until its own
cut. It does not preserve any legacy item identity or construction authority.

### 6.6 Guardian of Faith forced prerequisite

CR-0 scheduled `environment.spell_object.guardian_of_faith` for CR-9 because
it is a private spell object rather than a public item. Direct inspection adds
a stronger dependency: the object subclasses `BaseItem`, so it cannot retain
`content_ref` after the shared BaseItem identity hard cut without optional
legacy state, subclass identity overrides, or an adapter. All are forbidden.

CR-I therefore advances this one exact family inside the same atomic candidate
as the shared BaseItem identity and complete item caller cut:

- migrate the Guardian spell/action/source behavior identity and all its
  discovery/execution consumers to the direct behavior seam;
- construct `GuardianOfFaithObject` directly inside its existing spell-effect
  owner with required literal
  `item_id="environment.spell_object.guardian_of_faith"`;
- preserve the current object/zone anchor, faction, spell DC, duration,
  placement, damage, discharge, destruction, Event parentage, and failure
  cleanup;
- delete `GUARDIAN_OF_FAITH_OBJECT_RECIPE`, its environment-object declaration/
  factory, `ItemBuildContext`, runtime binding/origin/provenance, and the
  `materialize_item_from_installed_runtime` call; and
- keep the private ID out of public definitions, the 147-key builder selector,
  loadouts, inventories, loot, containers, and authored map placement.

This is direct construction by the existing Guardian spell system, not an
item builder, special BaseItem subtype identity, or generic spell-object
factory. Every Guardian item fact/Event carries the same ordinary `item_id` as
every other BaseItem. No Guardian `ContentRef` survives in mechanics or facts.
The CR-0 scheduling deviation and its dependency evidence are recorded in the
CR-I ledger.

There is no accepted checkpoint after Guardian's legacy recipe/materializer is
removed and before required `BaseItem.item_id`, Guardian direct construction,
all 147 public item callers, and the item-runtime deletion are complete. The
temporary red interval exists only inside that active implementation turn.

If the complete Guardian behavior/source/object family cannot be cut without
pulling another unrelated CR-9 family or creating a compatibility path, stop
for a plan amendment before the BaseItem cut.

### 6.7 `environment.door` collision disposition

CR-0's current-only `environment.door` is not a 148th public ID. It is retired
into canonical `environment.directional_door` in CR-I:

- every gameplay/scenario/map-authoring caller is migrated from
  `environment.door` to `environment.directional_door`;
- `DoorParameters.is_open` maps to the canonical direct door's `is_open`;
- the legacy closed-door movement, optics, and propagation blocking semantics
  map to the same three directional `blocked_channels`;
- legacy `OpenDoorAction`/`CloseDoorAction`, `DoorObject`, declaration,
  presentation identity, and materializer root are deleted after equivalent
  canonical open/close discovery, execution, occupancy-close rejection, and
  structure-change proofs pass; and
- the direct definition/builder table contains only
  `environment.directional_door`, while the ledger records the CR-0 collision
  edge `environment.door -> environment.directional_door`.

A canonical directional door requires an authored owner-Tile boundary side.
No default orientation, class-based inference, or whole-Tile compatibility
mode is allowed. Slice 0 inventories every legacy door placement and its
orientation source; any caller without an unambiguous boundary side is a stop
for an authored-data/human decision before production edits.

## 7. Implementation slices

Slices 0 and 1 stop at coordinator review checkpoints. Slices 2–5 are bounded
work chunks inside one inseparable CR-I candidate: the coordinator may inspect
them, but no chunk is accepted, frozen, handed off, or called green until all
four are complete. A failed gate is repaired inside the active candidate and
all affected validation is rerun.

### Slice 0 — exact preflight and implementation ledger

Documentation/test inventory only; no production edits.

1. Create one CR-I implementation ledger.
2. Freeze the 147 IDs, their current and accepted builders/values, every active
   production caller, every maintained test caller, and the exact visual
   artifacts/row subsets in section 6.3.
3. Freeze exact item-required behavior IDs/classes and their current admission
   points.
4. Freeze the maintained affected test union and normalized node hash.
5. Freeze current import edges and governing hashes.
6. Classify each current item recipe/declaration/preset/binding/caller as:
   `migrate_CR-I`, `behavior_prerequisite_CR-2I`, `visual_evidence_CR-8`, or
   `unrelated_legacy_domain`; classify the complete Guardian family separately
   as `guardian_atomic_CR-I`.
7. Freeze the direct durable schema/digest callers, item Event fields and
   analytics consumers, and specific-weapon-proficiency storage/API/Event/
   attack-calculation callers.
8. Freeze the CR-0 architecture tests whose current-source assertions this cut
   intentionally invalidates and their exact successor disposition in section
   9.1.
9. Freeze every `environment.door` caller/placement, the exact parameter/action
   mapping to `environment.directional_door`, and an authenticated boundary
   side for each placement.
10. Freeze the complete Guardian behavior/source/object dependency family in
    section 6.6 and every caller/consumer required for its direct cut.

Stop if the item count, behavior ownership, visual value, active caller, or
accepted/current value conflicts cannot be resolved from the frozen evidence.

### Slice 1 — CR-2I item-required behavior families

Migrate only behavior identities exercised by Appendix B:

- Assassin's Dagger handler;
- potion drink actions;
- weapon-coat actions and their source-owned conditions;
- spell-item executable spell/action identities;
- torch ignite/extinguish behavior;
- Field Kit deployment;
- interactive door/lever/chest/campfire/device/cannon and Appendix B
  spell-object behavior (Guardian is excluded until Slice 2);
- item-required finite charge/cost behavior; and
- any equip-hook source identity that current mechanics actually expose.

For each family atomically migrate direct semantic behavior/source IDs, live
actions/conditions/handlers, Events, discovery/execution consumers, and remove
that family's content-runtime admission/declaration attachment. Unrelated
spells/actions/conditions remain wholly legacy.

The affected legacy item declarations are behavior consumers: their
`ContentDependency(target_ref=...)` edges and declaration-consistency guards
for migrated behaviors are removed/replaced with the direct behavior identity
in this slice. Their item factory, item `ContentRef`, recipe, preset,
constructor, and construction authority remain otherwise unchanged until
CR-I. This narrowly permitted edit is required for a green CR-2I checkpoint;
it is not a direct item path or second item identity.

Checkpoint gate:

- fresh-process direct behavior execution without item-runtime admission;
- action discovery/execution, charge/cost, source/provider/root, condition
  cleanup, and equip/unequip symmetry preserved;
- no migrated behavior has both declaration and direct identity; and
- no affected item declaration imports, depends on, or validates the removed
  behavior declaration, while its legacy item construction remains green; and
- no Event/action/condition redesign.

### Slice 2 — direct item data and construction

1. In one coordinated edit, change `BaseItem` and cold item/Event state to
   required `item_id` and cut the complete Guardian behavior/source/object
   family exactly as section 6.6 requires.
2. Add the frozen direct definitions and explicit builders for all 147 public
   IDs; Guardian remains direct concrete spell construction outside that map.
3. Migrate concrete item constructors to direct values and CR-2I behavior.
4. Preserve current visual fields/values and Oil Barrel mechanics.
5. Add direct-construction proofs for every public ID plus the private Guardian
   object, including fresh instances,
   independent nested values, exact mechanics, and zero registry bootstrap.

This slice is not complete while Guardian or any of the 147 public IDs is still
constructible by an item declaration/materializer. Therefore Slices 2–5 form
one frozen candidate; intermediate red tests are expected only inside the
active implementation turn and are never called an accepted checkpoint.

### Slice 3 — silent initial placement

1. Add the minimum explicit Inventory/Equipment/Entity initial-install
   operations described in section 6.4.
2. Reuse existing validation/slot/footprint/reparent/hook mechanics.
3. Add public feature proofs for silent initial inventory/equipment state,
   birth fact completeness, runtime eventful placement, and whole-Entity
   cleanup on failure.
4. Prove two-handed/multi-slot collision, stack collision, capacity, hook
   failure, and mixed inventory/equipment loadouts.

No new lifecycle, transaction abstraction, or callback rollback mechanism.

### Slice 4 — migrate every holder and caller

Migrate, without server/SDK/renderer work:

- direct test and gameplay item creation;
- Acolyte starting possessions;
- nine class starting-equipment plans;
- four starting-apparel plans;
- all four maintained premade holding rows as direct item state;
- bestiary, Circus, SRD-roster, configured-creature, and intrinsic
  possessions;
- specific weapon-proficiency config/storage/source APIs, Entity attack
  consumers, and birth facts;
- direct durable `CharacterItemV2`/holdings schema, digests, hydration,
  repository/domain callers, and all maintained fixtures;
- map/scenario world objects and container contents;
- every `environment.door` caller/placement/action to the exact canonical
  `environment.directional_door` collision disposition in section 6.7;
- spell-created Appendix B items/environment objects, with Guardian already
  direct through its inseparable Slice 2 family cut;
- floor placement, destruction, and item location facts; and
- reset/failure cleanup.

Every migrated caller imports a domain builder or a cold holder plan. No caller
resolves a registry row, constructs `ContentRecipe`, consults an item binding,
or infers an item from a Python class name.

### Slice 5 — migrated item-runtime hard deletion

Delete the complete migrated closure:

- item/environment item factory declarations for all 147 public IDs and the
  Guardian private object;
- every item/environment recipe and all 205 recipe presets;
- every generic item-materialization caller/path and its convenience bootstrap;
- all item/environment `ITEM_RUNTIME_BINDINGS`, item origins, recipe
  provenance, and reset hooks;
- item `ContentRef` and `ItemContentRefSnapshot` state;
- item-specific generic construction/dependency rows;
- `BaseItem.get_semantic_key`, item-state/Event semantic aliases, and all
  item-specific callers;
- recipe-shaped durable item schema and unsupported augmentation schema;
- obsolete item materializer/registry-shape tests; and
- migrated active icon-closure rows, while preserving CR-8 evidence/source
  artifacts.

Do not delete generic creature/character/scenario/behavior infrastructure
outside the exact item closure.

### Slice 6 — certification and exact-candidate review

1. Freeze exact changed production/test/document manifests and hashes.
2. Run the complete affected node union from Slice 0.
3. Run direct construction/state/placement/behavior/rollback proofs.
4. Run maintained character, item, monster, scenario, spell, spatial,
   world-initialization, Event, runtime-reset, and architecture lanes affected
   by the cut.
5. Run compileall, diff-check, fresh-import, dependency-DAG, no-late-import,
   no-reflection, no-server/SDK/renderer, and hard-cut scans.
6. Obtain exact-candidate correctness, anti-slop, and anti-OOP approval.
7. Any production/test repair invalidates the affected hashes, validation, and
   all three final reviews.

## 8. Required public proofs

At minimum the final candidate proves:

1. all 147 IDs construct without `bootstrap_content_system`;
2. two instances of each ID have distinct runtime UUIDs and independent nested
   modifiable values/state;
3. item state and `ItemLocationStateEvent` carry the same direct `item_id`;
4. `ItemChargeConsumptionEvent` and `GameSummary.item_charges_spent` use that
   exact `item_id` with unchanged charge counts;
5. `EntityCreatedEvent` contains exact initial inventory/equipment state and
   direct specific-weapon-proficiency IDs;
6. initial installation emits no item/equipment/world transition Events;
7. post-birth loot/equip/unequip/drop/merge/destroy continues to emit exact
   committed facts;
8. active weapon stance, equipment footprints, armor/shield AC, stealth/heavy
   penalties, Spellblade/Arcane modifiers, and Assassin handler remain exact;
9. stack quantities, finite charges, durability, consumable costs, containers,
   intrinsic items, and world blockers remain exact;
10. direct durable records round-trip exact state, authenticate item/holdings
    digests, reject tampering/old recipes/augmentations, and fail hydration
    without partial state;
11. specific weapon proficiency preserves base and source-owned add/remove,
    exact attack bonus, and non-proficiency behavior using direct item IDs;
12. initial and runtime failure paths leave no partial state or registry/world
   residue;
13. all four premade item holdings and maintained monster possessions match
    their frozen semantic plans;
14. Oil Barrel destruction still performs the current direct Oil/fire material
    transition;
15. every migrated behavior executes with exact provider/source/root IDs;
16. all section 6.3 artifacts and item-relevant overlay rows remain
    hash-preserved for CR-8 and active instance visual values do not drift; and
17. all former `environment.door` callers build the canonical directional door
    with exact open/closed channel behavior, action parity, and explicit
    boundary placement, while the legacy ID/class/actions have zero callers;
18. the Guardian spell/object/zone behavior remains exact through direct
    concrete construction, every Guardian item fact carries its private direct
    ID, and no public builder exposes it; and
19. no item/environment object path imports or touches the deleted generic
    item construction closure.

Feature tests assert observable item/entity/world/Event results. Architecture
tests alone do not claim gameplay correctness.

## 9. Hard-cut and dependency gates

The final candidate must have zero active production occurrences, except in
explicitly frozen evidence/documents, of:

- item/environment-object `ContentRef` construction or fields;
- `ItemBuildContext`;
- `ContentRecipe` used for an item;
- `ContentRecipePreset` and authored item recipe-preset exports;
- `materialize_item` or `materialize_item_from_installed_runtime`;
- `ITEM_RUNTIME_BINDINGS`, `ItemRuntimeBinding`, or `ItemRuntimeOrigin`;
- item factory decorators/declarations or recipe constants;
- item class-path identity fallback;
- `BaseItem.get_semantic_key()` and item-state/item-Event `semantic_key` or
  `item_semantic_key` fields/usages;
- specific-weapon `ContentRef`, `base_weapon_ref_keys`, or item
  `ContentRef.identity_key` storage/API/callers;
- recipe-shaped `CharacterItemV1`, `ItemAugmentationRecord`, and
  `durable_augmentations`;
- any item/environment-object lookup through the universal registry; and
- server/SDK/renderer imports from engine/content item modules.

The checker must parse imports/AST where aliases could hide a call. Text grep
is supporting evidence, not the only gate.

Import direction must remain:

```text
dnd/types + core item values
            ^
            |
blocks / Entity / GridMap / Events
            ^
            |
dnd/items mechanics + dnd/content/items definitions/builders
            ^
            |
character/monster/scenario authored holders
```

Core/blocks/Entity/GridMap/Events never import `dnd.content`. Definitions do
not import Entity or builders. Builders may import definitions and concrete
mechanics. No function-local import, `TYPE_CHECKING`, `getattr`, `isinstance`
dispatch used to hide content kind, or circular-import allowlist is permitted.

### 9.1 Governed CR-0 gate succession

The CR-0 evidence manifest remains immutable historical authority. CR-I does
not rewrite it to pretend that the old registry still matches current source.
Nor does it keep stale test names alive with different assertions. Slice 0
records this exact old-node to new-node succession:

| Retired CR-0 live-source node | CR-I successor node(s) |
|---|---|
| `test_legacy_authority_and_importer_inventories_match_current_python` | `test_cri_live_authority_and_importer_delta_is_exact` |
| `test_binding_reconciliation_covers_every_authored_row` | `test_cr0_binding_artifacts_remain_hash_and_row_exact`; `test_cri_direct_item_visual_values_match_frozen_cr0_rows`; `test_cri_non_item_visual_overlay_still_matches_current_owners` |
| `test_direct_item_inventory_is_mechanically_reconciled` | `test_cri_public_item_inventory_is_exact_and_direct` |
| `test_every_behavior_identity_has_one_exact_concrete_owner` | `test_cri_remaining_legacy_and_migrated_direct_behavior_owners_are_exact` |
| `test_every_materializable_root_has_one_exact_factory_owner` | `test_cri_remaining_legacy_and_direct_item_construction_owners_are_exact` |
| `test_every_current_proof_node_is_collectible` | `test_cri_maintained_proof_union_is_collectible_and_hash_exact` |

The old live gates are removed rather than duplicated or rewritten under stale
names. The CR-I ledger freezes a new sorted maintained-node union and normalized
hash; the last successor node collects that exact union. The ledger also
preserves the old node IDs, old 105-node hash, and mapping above as historical
provenance. Successors prove:

1. the original CR-0 manifest bytes and all 14 source-artifact hashes remain
   exact;
2. all eight binding pairs, including 283/283 authored visuals, 205/205 recipe
   preset bindings, 669/671 definition bindings, and 515/521 asset-index rows,
   remain historically row-reconciled with all 121 recorded changed/collision
   rows;
3. the complete 788-row Python overlay is preserved, while every item-relevant
   row frozen in Slice 0 maps to the same active visual value in the direct
   definition/holder and all non-item overlay rows still match their current
   owners;
4. the live declaration/authority and importer sets equal the CR-0 sets minus
   the exact CR-2I/CR-I governed removals—no count-only or broad allowlist;
5. the public builder set equals the canonical 147-ID hash above; the complete
   direct BaseItem species facts equal that set plus the one private Guardian
   ID; and the exact governed
   `environment.door -> environment.directional_door` collision is closed;
   and
6. every remaining legacy behavior identity/materializable root still has one
   concrete owner, while every migrated behavior/item identity has zero legacy
   owner and one direct feature proof.

The genuinely historical CR-0 manifest-shape, source-artifact-hash, SRD,
production-never-imports-evidence, and unaffected structural-owner assertions
remain active under their truthful names. The new CR-I union contains every
retained historical node plus every named successor and public feature proof.
No count-only assertion, broad allowlist, stale-name compatibility test, or
duplicate old/new live gate is permitted.

## 10. Anti-slop and anti-OOP rejection list

Reject any candidate containing:

- a new content/item manager, service, controller, repository, runtime,
  registry, resolver, materializer, loader, or bootstrap;
- a universal semantic-ID class;
- a polymorphic item-definition base class or visitor;
- factory strings, JSON construction parameters, reflection, or class-name
  fallback;
- a generic `build_item(definition: object)` switch over runtime types;
- optional legacy/direct fields, dual writes, alias properties, or fallback
  resolution;
- a callback/undo closure graph, context-manager transaction, command object,
  or receipt registry for initial placement;
- a second inventory/equipment/world mutation path with duplicated rules;
- Event-owned mechanics or Event-time definition lookup;
- content-owned Entity/Game/GridMap/Event lifecycle;
- moving visual authority into a temporary backend abstraction;
- Pygame, server, persistence storage, SDK, transport, or Phase CR-4+ work;
  or
- weakening tests/validators to tolerate missing identities, orphaned callers,
  or partial cleanup.

Small frozen data rows, explicit functions, existing ECS components, and one
item-domain callable map are sufficient.

## 11. Stop conditions

Stop and return for a plan amendment/human decision if:

1. the regenerated final inventory is not exactly reconcilable to 147 IDs;
2. an item-required behavior cannot be migrated family-atomically in CR-2I;
3. a maintained holder needs a generic parameter language rather than typed
   item state;
4. visual evidence would be lost rather than merely removed from runtime
   authority;
5. silent initial installation cannot reuse the current owner validation and
   commit mechanics;
6. failure cleanup would require a callback/transaction framework or Entity
   registry scan;
7. a holder migration requires server, SDK, renderer, or persistence-storage
   work;
8. an import edge would require a late import, `TYPE_CHECKING`, reflection, or
   cycle exception; or
9. any slice would leave a migrated item constructible through both direct and
   legacy paths;
10. any `environment.door` placement lacks an authenticated directional
    boundary side or cannot preserve its open/closed channel behavior;
11. the complete Guardian behavior/source/object family cannot migrate directly
    without pulling another unrelated CR-9 family or creating a special
    BaseItem identity/construction path; or
12. an invalidated CR-0 live-source gate cannot be retired to the exact named
    CR-I successor and new maintained-node union in section 9.1.

## Appendix A — 108 behavior-free direct IDs

### Fixed gear (5)

`gear.holy_symbol`, `gear.prayer_book`, `gear.incense`, `gear.vestments`,
`gear.common_clothes`.

### Pure world blockers (5)

`environment.blocker.crate`, `environment.blocker.boulder`,
`environment.blocker.barricade`, `environment.directional_wall`,
`environment.cliff_face`.

### Weapons and intrinsic attacks (43)

`weapon.club`, `weapon.spear`, `weapon.mace`, `weapon.dagger`,
`weapon.handaxe`, `weapon.javelin`, `weapon.light_hammer`,
`weapon.quarterstaff`, `weapon.sickle`, `weapon.dart`, `weapon.sling`,
`weapon.battleaxe`, `weapon.greataxe`, `weapon.greatsword`,
`weapon.double_bladed_sword`, `weapon.longsword`, `weapon.morningstar`,
`weapon.rapier`, `weapon.longbow`, `weapon.shortsword`, `weapon.scimitar`,
`weapon.trident`, `weapon.warhammer`, `weapon.shortbow`,
`weapon.light_crossbow`, `weapon.heavy_crossbow`,
`weapon.circus.rusty_dagger`, `weapon.circus.flaming_scimitar`,
`weapon.circus.longsword_plus_one`,
`weapon.circus.soul_draining_morningstar`,
`weapon.creature.kobold_sling`, `weapon.creature.spy_hand_crossbow`,
`weapon.creature.bandit_captain_thrown_dagger`,
`weapon.creature.thrown_javelin`, `weapon.creature.bugbear_morningstar`,
`weapon.creature.ogre_greatclub`, `weapon.creature.ogre_thrown_javelin`,
`weapon.creature.wolf_bite`, `weapon.creature.dire_wolf_bite`,
`weapon.creature.zombie_slam`, `weapon.creature.ogre_zombie_morningstar`,
`weapon.creature.ghoul_claws`, `weapon.creature.ghoul_bite`.

### Armor, shields, apparel, and intrinsic protection (55)

`armor.breastplate`, `armor.cloth`, `shield.wooden`,
`apparel.fine_clothes`, `apparel.cloth_hood`, `apparel.leather_hood`,
`apparel.chain_coif`, `apparel.horned_helmet`, `apparel.great_helm`,
`apparel.monster_helm`, `apparel.bracers`, `apparel.leather_gloves`,
`apparel.gauntlets`, `apparel.monster_hands`, `apparel.common_clothes`,
`apparel.travelers_clothes`, `apparel.costume`, `apparel.robes`,
`apparel.sandals`, `apparel.leather_shoes`, `apparel.iron_helmet`,
`apparel.wizard_hat`, `armor.chain_shirt`, `armor.hide`, `armor.leather`,
`armor.studded_leather`, `shield.shield`, `apparel.leather_boots`,
`apparel.leather_boots.brown`, `apparel.leather_shoes.brown`,
`apparel.armored_boots`, `apparel.cloth_shoes`, `apparel.cloth_shoes.red`,
`apparel.cloth_shoes.blue`, `apparel.iron_helmet.steel`,
`apparel.wizard_hat.red`, `apparel.costume.pit_fighter_wrap`,
`apparel.robes.red_mage`, `apparel.robes.wizard`,
`apparel.robes.acolyte_vestments`,
`apparel.common_clothes.farmhand_tunic`,
`apparel.common_clothes.peasant_rags`,
`apparel.travelers_clothes.thief_garb`, `apparel.robes.hedge_wizard`,
`apparel.robes.dark_cultist`, `apparel.robes.priest_vestments`,
`apparel.robes.necromancer`, `apparel.cloth_shoes.dark`,
`apparel.sandals.rope`, `armor.armor_scraps`, `apparel.crown`,
`apparel.leather_boots.dark`, `armor.circus.performer_leather`,
`armor.creature.wolf_natural`, `armor.creature.dire_wolf_natural`.

## Appendix B — 39 behavior-bearing/direct-special IDs

### Equip-hook items (10)

`weapon.arcane_staff`, `weapon.assassin_dagger`,
`apparel.spellblade_crown`, `armor.padded`, `armor.scale_mail`,
`armor.half_plate`, `armor.ring_mail`, `armor.chain_mail`, `armor.splint`,
`armor.plate`.

### Consumables and spell items (17)

`consumable.healing_potion`, `consumable.potion_haste`,
`consumable.potion_greater_invisibility`, `consumable.weapon_coat.fire`,
`consumable.weapon_coat.lightning`,
`consumable.weapon_coat.concentration_fire`,
`consumable.weapon_coat.timed_fire`, `consumable.acid_flask`,
`spell_item.scroll_fireball`, `spell_item.scroll_magic_missile`,
`spell_item.scroll_hold_person`, `spell_item.scroll_mage_armor`,
`spell_item.scroll_spike_growth`, `spell_item.scroll_invisibility`,
`spell_item.scroll_fire_bolt`, `spell_item.wand_magic_missiles`,
`spell_item.wand_fire`.

### Lights, interactive world items, and Field Kit (12)

`equipment.portable_torch`, `environment.directional_door`,
`environment.campfire`, `environment.arcane_device`,
`environment.arcane_machine_gun`, `environment.wall_torch`,
`environment.trap_lever`, `environment.storage_chest`,
`environment.fireball_cannon`, `environment.spell_object.heroes_feast`,
`gear.field_kit`, `environment.blocker.oil_barrel`.

## 12. Review requirements

Before implementation, three independent reviewers must evaluate the same file
bytes:

1. correctness/completeness, including the sequencing correction, 147-ID
   reconciliation, holder/caller closure, Event/placement law, and visual
   preservation;
2. anti-slop, including rejection of a migration membrane, generic item
   materializer under another name, excessive layers, and speculative CR-8+;
   and
3. anti-OOP/ECS/import-DAG, including data composition, actual component
   ownership, no callback transaction graph, and no hidden circularity.

Any substantive plan edit invalidates all three approvals.

### Accepted review record

Substantive candidate SHA-256:
`cf4a85a6fbb2e1021dbab87a7b7a79495dba8b853ffcafbd414c1096243e8107`.

- correctness/completeness: **APPROVE** — exact 147 public inventory/hash,
  Guardian/BaseItem atomic sequencing, door collision, holders/callers, Events,
  durable/proficiency closure, visuals, and CR-0 gate succession accepted;
- anti-slop: **APPROVE** — no migration membrane, stale test facade, duplicate
  catalog, speculative layer, or intermediate accepted hybrid remains; and
- anti-OOP/ECS/import-DAG: **APPROVE** — data composition and component
  ownership remain explicit, with no adapter, polymorphic identity, service,
  late import, reflection, or circularity.

The review record and status are metadata only. All three reviewers must
reconfirm the final file SHA before Slice 0 begins.
