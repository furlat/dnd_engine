# CR-2I direct-item prerequisite scope amendment

Status: `REJECTED — RETAINED AS EVIDENCE; SLICE 1A AND PRODUCTION UNAUTHORIZED`

This amendment corrects one sequencing error discovered by the reviewed Slice
0 preflight for
`DND_CONTENT_RECOVERY_DIRECT_ITEM_HARD_CUT_CR1_CR3_IMPLEMENTATION_PLAN_2026-08-31.md`.
It does not replace the accepted broader content-recovery plan and does not
authorize the direct `BaseItem`/147-item hard cut.

## 1. Governing evidence

- accepted implementation-plan SHA-256:
  `51b06ddd6c67742fe32dee8f7bb729a72134d54df1805d6b434ad68dba24ae0b`;
- accepted implementation-plan substantive SHA-256:
  `cf4a85a6fbb2e1021dbab87a7b7a79495dba8b853ffcafbd414c1096243e8107`;
- reviewed Slice 0 ledger SHA-256:
  `c98f181888e57f2c126129ff1f97649cc0eb60bf7cbbdf3792f992b1862c781c`;
- current complete affected lane: 409 nodes, normalized SHA-256
  `c4253a3f09c295f1f33e087ac3f36aecd4d455053ba70c7b1adbb6d8c525680a`;
- current execution: 4 failed, 405 passed in 322.10s.

The four maintained failures are one Wall Torch/Sleet Storm failure and three
door discovery/path/reaction failures. They are repair obligations, not
grounds for test deletion or architecture expansion.

## 2. Door fixture decision

The single unauthenticated door placement is the range-only fixture in
`tests/manual/test_134_stackable_usable_item_legacy_contract.py`. Its test
observes only that a distant unusable object does not surface an action. No
boundary direction is observable in the assertion or mechanics under test.

That fixture is authored with `CardinalDirection.WEST`, matching the canonical
production barrier convention. This is one explicit fixture value. It is not
a runtime default, inference rule, compatibility mode, or permission to omit
direction from any real placement. Accepted-plan stop condition 10 is therefore
resolved for this inventory.

## 3. Sequencing correction

The accepted plan treated all 33 item-required behavior IDs as family-local.
Slice 0 proved that eight of the spell classes are not family-local: the
shared spell catalog requires `SpellCatalogCompositionRow.declaration`, and
character, origin, and scenario holders consume `row.declaration.ref`.

Removing only those eight declarations while unrelated spells remain legacy
would require at least one forbidden construct:

- an optional legacy/direct catalog field;
- a per-spell switch or resolver;
- a parallel catalog;
- a class exposing both direct and attached declaration authority; or
- a partial direct holder whose runtime still authenticates a legacy ref.

The private Guardian spell/object family reaches the same seam. It remains
blocked with those eight spell families. Guardian's independent spatial-zone
`ContentRef` remains outside this amendment and stays deferred to CR-9.

The direct item cut itself also remains atomic. `BaseItem.content_ref`,
`semantic_key`, item Events, durable state, all 147 public IDs, and the private
Guardian item may not be split into an accepted 135/12 or similar hybrid.

## 4. Slice 1A — 25 family-local behavior cuts

Slice 1A migrates exactly these 25 direct behavior IDs:

```text
action.environment.arcane_device.activate
action.environment.campfire.cook
action.environment.campfire.rest
action.environment.directional_door.close
action.environment.directional_door.open
action.environment.heroes_feast.eat
action.environment.storage_chest.loot_all
action.environment.trap_lever.pull
action.environment.wall_torch.extinguish
action.environment.wall_torch.ignite
action.item.field_kit.deploy
action.item.potion_greater_invisibility.drink
action.item.potion_haste.drink
action.item.potion_healing.drink
action.item.torch.extinguish
action.item.torch.ignite
action.item.weapon_coat.apply
condition.consumable.weapon_coat.concentration_fire
condition.consumable.weapon_coat.fire
condition.consumable.weapon_coat.lightning
condition.consumable.weapon_coat.timed_fire
condition.field_focus
condition.spell.greater_invisibility
condition.spell.haste
spell.acid_flask
```

For each exact family, the existing concrete action, condition, or private
Acid Flask spell class remains the mechanics owner. The cut must atomically:

1. carry the existing primitive semantic/source ID through the class's
   existing action/condition/spell and Event fields;
2. remove that class's attached behavior declaration and generic runtime
   admission;
3. migrate its existing discovery, execution, charge/cost, source/provider,
   condition-child, cleanup, Event, and reset consumers;
4. remove or replace only the legacy dependency edges that point at the
   migrated behavior, including legacy item/spell declarations that consume a
   now-direct condition/action ID; and
5. preserve the concrete class, ECS component owners, action economy,
   condition ownership, effect semantics, and import DAG.

No migrated class may retain an attached `ContentDeclaration`. No new
registry, resolver, service, manager, adapter, provider gateway, admission
table, callback transaction, or compatibility alias is allowed. Existing
maps may retain only unrelated legacy families; they may not become mixed
runtime authorities for the migrated rows.

### 4.1 Bounded repairs inside existing owners

- `WallTorch.light()` must consult the same existing exposed-flame
  suppression fact already honored by portable Torch relighting. Do not add a
  flame manager, spell special case, or new Event path.
- Directional-door discovery and state changes must use the existing
  owner-Tile boundary object and current movement/path/reaction invalidation
  seams. Do not restore whole-Tile collision, add an edge index, or create a
  door controller.
- The range-only manual door fixture receives explicit `WEST` authored data.

### 4.2 Slice 1A checkpoint gates

Slice 1A stops for coordinator and independent review after all of the
following are true:

- all 25 families execute in a fresh process without their removed runtime
  declarations/admission;
- no selected class has both direct and legacy identity;
- unrelated behavior and all shared catalog spell families remain wholly
  legacy and green;
- discovery/execution, costs/charges, source/provider/root identity,
  condition cleanup, equip/use symmetry, and reset behavior remain exact;
- the complete 409-node affected lane is green, including the four current
  regression nodes;
- new public proofs authenticate direct admission absence and real execution,
  rather than inspecting only source shape;
- compileall, diff-check, fresh imports, dependency-DAG, no-late-import,
  no-reflection, and no-server/SDK/renderer gates pass; and
- correctness, anti-slop, and anti-OOP/ECS/import-DAG reviewers approve the
  exact Slice 1A candidate.

Any production/test repair after candidate freeze invalidates affected
validation and all three reviews.

## 5. Explicitly deferred shared spell cut

These eight behavior IDs are not authorized in Slice 1A:

```text
spell.burning_hands
spell.fire_bolt
spell.fireball
spell.hold_person
spell.invisibility
spell.mage_armor
spell.magic_missile
spell.spike_growth
```

The Guardian spell/action/source/private-object family is also unauthorized.
Before either group changes, a separate evidence-based implementation plan
must freeze the complete shared spell catalog and all character, origin,
scenario, entitlement, durable, Event, runtime, and admission consumers. That
plan must choose one atomic direct owner path for the whole affected spell
holder seam; it may not create a transitional mixed catalog.

## 6. Consequence for the 147-item cut

Accepted-plan Slices 2–6 remain unauthorized until the shared spell cut is
planned, reviewed, and complete. When that prerequisite is satisfied, the
existing atomic direct-item law still applies:

- all 147 public item IDs plus the private Guardian item move together;
- `BaseItem` receives one required direct item identity;
- legacy item declarations/recipes/presets/materializers and item
  `ContentRef` state are deleted in the same candidate; and
- there is no accepted intermediate direct/legacy BaseItem schema.

This amendment therefore advances valid CR-2 work without weakening the
direct-item hard cut or pulling a partial spell redesign into it.

## 7. Review requirements

Before Slice 1A production work, three independent reviewers must approve the
same amendment bytes:

1. correctness/completeness, including the 25/8 partition, Guardian boundary,
   door disposition, and complete consumer implications;
2. anti-slop, including the absence of a mixed catalog, migration membrane,
   new runtime authority, or speculative shared-spell design; and
3. anti-OOP/ECS/import-DAG, including concrete class ownership, component
   cleanup, no callback transaction, and no late import/cycle workaround.

Substantive edits invalidate all approvals.

## 8. Rejection record

All three required reviewers rejected this candidate. The 25/8 arithmetic is
correct, but the proposed 25-family cut is not family-local under the current
shared core contract:

- action discovery requires `BehaviorBinding` and mandatory
  `AuthoredBehaviorAttribution`;
- action Events carry the same binding rather than a primitive direct fact;
- condition saving-throw provenance requires binding `ContentRef` values;
- the still-legacy Haste and Greater Invisibility spell profiles require the
  selected condition declarations; and
- the still-legacy Heroes' Feast object declaration requires its selected
  action declaration.

Removing only the selected declarations would therefore require a forbidden
synthetic binding, optional/union attribution, per-family switch, resolver, or
parallel Event/discovery path. No Slice 1A production or test edit is
authorized by this file. The `WEST` fixture recommendation remains useful,
but the behavior migration must instead plan one atomic primitive-ID cut over
the complete shared behavior fact surface.
