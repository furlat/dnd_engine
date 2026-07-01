# 13. Equipment, Inventory, And Items

## Purpose

This chapter documents the engine's object layer: how items move between floor,
inventory, equipment, and destruction states; how stacks and capacity work; how
equipment slots validate and apply hooks; and how usable objects expose actions.

The examples are executable in both:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

The pytest file calls the same example functions, so the book examples and the
proper `uv run pytest` suite stay in 1:1 parity.

## Source Files Studied

- `dnd/blocks/base_item.py`
- `dnd/blocks/inventory.py`
- `dnd/blocks/equipment.py`
- `dnd/items/armors.py`
- `dnd/items/weapons.py`
- `dnd/items/test_items.py`
- `dnd/items/environment.py`
- `dnd/entity.py`
- `dnd/actions.py`
- `dnd/actions_functional.py`
- `dnd/core/gridmap.py`
- `examples/test_items_phase1.py`
- `examples/test_items_phase1_advanced.py`
- `examples/test_items_lifecycle_hooks.py`
- `examples/test_items_equip_hooks.py`
- `examples/test_inventory_use_actions.py`
- `examples/test_stackable_items.py`
- `examples/test_usable_items.py`
- `examples/test_equipment_api.py`
- `examples/test_equipment_visual_metadata.py`
- `examples/test_door_interaction.py`
- `examples/test_torch_items.py`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: armor, shields, weapons, weapon properties, heavy armor
  Strength speed penalties, stealth disadvantage from armor, object damage,
  torches, potions, scrolls, and interacting with objects all correspond to
  local SRD material in `interactive_ruleset/Equipment/`,
  `interactive_ruleset/Treasure/`, and
  `interactive_ruleset/Gamemastering/Objects.md`.
- `SRD-aligned`: shields occupy a hand-like equipment slot and add defensive
  value while equipped.
- `Engine adaptation`: inventory uses explicit slots, optional weight capacity,
  UUID ownership fields, and stack merging. These are engine data rules, not a
  direct SRD inventory procedure.
- `Engine adaptation`: usable items and environment objects expose cloned
  action templates. The action system is the engine's uniform way to model
  drinking a potion, opening a door, using a scroll, or igniting a torch.
- `Engine extension`: floor objects participate in senses, path blocking,
  light, breakage, and action discovery through the same `BaseBlock` and event
  machinery used by entities and tiles.

## Item Identity And Location

`BaseItem` is a `BaseBlock`, so an item has UUID lookup, conditions, handlers,
and perceivability. Its location is represented by a small set of mutually
exclusive fields:

- `owner_uuid`: the entity or container-like item that owns the item;
- `stored_in_uuid`: the inventory or equipment block that stores it;
- `tile_uuid`: the map tile when the item is on the floor;
- `position`: the item's own floor position.

`BaseItem.get_position()` treats ownership as authoritative. An owned item
reports the owner's position. A floor item reports its own position only when
`tile_uuid` is set.

High-level entity helpers keep these fields synchronized:

- `Entity.loot_item()` removes grid placement, inserts into inventory, stamps
  ownership/storage, and fires loot hooks.
- `Entity.drop_item()` removes from inventory, clears ownership/storage, stamps
  floor state, places the object on the grid, and fires drop hooks.

Example EB-13-001:

```python
item.place_on_grid((1, 0))
assert item.tile_uuid is not None
assert get_map().get_object_position(item.uuid) == (1, 0)

assert entity.loot_item(item)
assert item.owner_uuid == entity.uuid
assert item.stored_in_uuid == entity.inventory.uuid
assert item.tile_uuid is None
assert get_map().get_object_position(item.uuid) is None
assert item.get_position() == entity.position

dropped = entity.drop_item(item.uuid, position=(0, 1))
assert dropped is item
assert item.owner_uuid is None
assert item.stored_in_uuid is None
assert item.tile_uuid is not None
assert get_map().get_object_position(item.uuid) == (0, 1)
```

Parity tests:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_001_floor_loot_and_drop_update_authoritative_location`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Inventory Stacks And Capacity

`Inventory` is a low-level container. It stores item objects and can enforce
slot and weight capacity. It also merges stackable items by `stack_id` up to
`max_stack`.

`Inventory.add_item()` is lower level than `Entity.loot_item()` because it does
not fire item loot hooks, but it is still a container boundary. On successful
insert it detaches the item from any previous floor/container location, clears
floor tile state, and stamps surviving item stacks to this inventory.

Example EB-13-002:

```python
first.stack_count = 8
second.stack_count = 2
third.stack_count = 5

assert entity.inventory.add_item(first)
assert entity.inventory.add_item(second)
assert first.stack_count == 10
assert second.stack_count == 0
assert BaseBlock.get(second.uuid) is None

assert entity.inventory.add_item(third)
assert first.stack_count == 10
assert third.stack_count == 5
assert entity.inventory.item_count == 2
```

This example proves exact stack consumption plus insertion of a separate full
third stack. The partial-remainder failure edge is pinned separately by
EB-13-012.

`Inventory.transfer_to()` removes an item from the source, attempts to add it to
the target, rolls back on failure, and stamps target ownership on success.

Example EB-13-003:

```python
assert not source.transfer_to(item.uuid, target)
assert source.has_item(item.uuid)
assert item.owner_uuid == source_owner
assert item.stored_in_uuid == source.uuid

target.remove_item(blocker.uuid)

assert source.transfer_to(item.uuid, target)
assert target.has_item(item.uuid)
assert item.owner_uuid == target_owner
assert item.stored_in_uuid == target.uuid
```

Example EB-13-012 proves that failed partial stack insertion is atomic. The
inventory computes the compatible-stack merge and the possible remainder before
mutating either stack. If the remainder cannot be inserted because of capacity,
the call returns `False` and both stack counts remain unchanged:

```python
existing.stack_count = 8
incoming.stack_count = 5
existing.weight = 1
incoming.weight = 1

assert inventory.add_item(existing)

result = inventory.add_item(incoming)

assert not result
assert existing.stack_count == 8
assert incoming.stack_count == 5
assert not inventory.has_item(incoming.uuid)
assert inventory.total_weight == 8
```

Example EB-13-017 covers transfer into an already-compatible target stack. If
the incoming object fully merges into the target's existing stack, the existing
target object remains the authoritative stored object. The incoming object is
reduced to `stack_count == 0`, unregistered, and cleared of ownership/storage
fields instead of being stamped as a target inventory item:

```python
incoming.stack_count = 2
existing.stack_count = 8

assert source.add_item(incoming)
incoming.owner_uuid = source_owner
incoming.stored_in_uuid = source.uuid
assert target.add_item(existing)
existing.owner_uuid = target_owner
existing.stored_in_uuid = target.uuid

assert source.transfer_to(incoming.uuid, target)

assert not source.has_item(incoming.uuid)
assert not target.has_item(incoming.uuid)
assert target.has_item(existing.uuid)
assert existing.stack_count == 10
assert BaseBlock.get(incoming.uuid) is None
assert incoming.owner_uuid is None
assert incoming.stored_in_uuid is None
```

Example EB-13-021 covers direct raw container use. Adding a floor item directly
to an inventory removes it from the grid and makes the inventory owner/storage
authoritative. Adding an item that already lives in a different inventory first
removes it from the previous inventory, preventing two containers from claiming
the same UUID:

```python
floor_item.place_on_grid((1, 0))

assert first_owner.inventory.add_item(floor_item)
assert first_owner.inventory.has_item(floor_item.uuid)
assert floor_item.owner_uuid == first_owner.uuid
assert floor_item.stored_in_uuid == first_owner.inventory.uuid
assert floor_item.tile_uuid is None
assert get_map().get_object_position(floor_item.uuid) is None

assert first_owner.inventory.add_item(transferred_item)
assert second_owner.inventory.add_item(transferred_item)

assert not first_owner.inventory.has_item(transferred_item.uuid)
assert second_owner.inventory.has_item(transferred_item.uuid)
assert transferred_item.owner_uuid == second_owner.uuid
assert transferred_item.stored_in_uuid == second_owner.inventory.uuid
```

Parity tests:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_002_inventory_stack_merge_can_consume_or_split_items`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_003_inventory_capacity_and_transfer_update_container_fields`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_012_partial_stack_merge_is_atomic_on_capacity_failure`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_017_transfer_to_existing_stack_consumes_incoming_location`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_021_raw_inventory_add_rehomes_existing_locations`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Equipment Containers And Slots

`Equipment` is the equipped-item container on an entity. It stores body armor,
body-part equipment, rings, and four weapon-hand slots:

- `MELEE_MAIN`
- `MELEE_OFF`
- `RANGED_MAIN`
- `RANGED_OFF`

`Entity.equip_item()` is the high-level helper. It removes the item from
inventory, unequips any replaced item back into inventory, and delegates slot
validation and hooks to `Equipment.equip()`.

Example EB-13-004:

```python
assert entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
assert entity.equipment.weapon_melee_main is sword
assert not entity.inventory.has_item(sword.uuid)
assert sword.is_equipped
assert sword.stored_in_uuid == entity.equipment.uuid

unequipped = entity.unequip_item(WeaponSlot.MELEE_MAIN)
assert unequipped is sword
assert entity.inventory.has_item(sword.uuid)
assert not sword.is_equipped
assert sword.stored_in_uuid == entity.inventory.uuid
```

Direct `Equipment.equip()` is a lower-level API. It validates weapon slot shape
and can replace a slot's current item, but it does not return the replaced item
to inventory.

Example EB-13-005:

```python
entity.equipment.equip(sword, WeaponSlot.MELEE_MAIN)
entity.equipment.equip(replacement, WeaponSlot.MELEE_MAIN)

assert entity.equipment.weapon_melee_main is replacement
assert not sword.is_equipped

try:
    entity.equipment.equip(bow, WeaponSlot.MELEE_MAIN)
    assert False
except ValueError as exc:
    assert "Ranged weapon" in str(exc)
```

Example EB-13-016 pins the direct cancellation boundary for the same lower-level
API. `Equipment.equip()` checks the equip event before replacing the current
slot item. A canceled direct replacement returns `False`, leaves the original
item equipped, and never stamps the incoming item as owned or equipped:

```python
original_weapon = entity.equipment.weapon_melee_main

result = entity.equipment.equip(replacement, WeaponSlot.MELEE_MAIN)

assert result is False
assert entity.equipment.weapon_melee_main is original_weapon
assert original_weapon.is_equipped
assert original_weapon.stored_in_uuid == entity.equipment.uuid
assert not replacement.is_equipped
assert replacement.equipped_slot is None
assert replacement.owner_uuid is None
assert replacement.stored_in_uuid is None
```

Example EB-13-013 shows the high-level cancellation boundary.
`Entity.equip_item()` attempts the equipment event before removing the incoming
item from inventory. If a `WEAPON_EQUIP` execution handler cancels the event,
the helper returns `False`, the existing slot occupant remains equipped, and the
incoming item remains in the inventory with its owner/storage fields unchanged:

```python
original_weapon = entity.equipment.weapon_melee_main

result = entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)

assert result is False
assert entity.equipment.weapon_melee_main is original_weapon
assert original_weapon.is_equipped
assert not sword.is_equipped
assert entity.inventory.has_item(sword.uuid)
assert sword.stored_in_uuid == entity.inventory.uuid
```

Example EB-13-014 captures the engine's videogame hand-occupancy rule: a
two-handed melee weapon uses both melee hands, and a shield or off-hand weapon
occupies the melee off hand. Conflicting melee equips are not hard-blocked. The
newer equip wins, and the displaced item moves back to inventory through the
same high-level rehome path as an ordinary slot replacement:

```python
assert entity.equip_item(greatsword.uuid, WeaponSlot.MELEE_MAIN)
assert entity.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)

assert entity.equipment.weapon_melee_main is None
assert entity.equipment.weapon_melee_off is shield
assert not greatsword.is_equipped
assert entity.inventory.has_item(greatsword.uuid)

assert second.equip_item(second_shield.uuid, WeaponSlot.MELEE_OFF)
assert second.equip_item(second_greatsword.uuid, WeaponSlot.MELEE_MAIN)

assert second.equipment.weapon_melee_main is second_greatsword
assert second.equipment.weapon_melee_off is None
assert second.inventory.has_item(second_shield.uuid)
```

This rule is based on the weapon's `TWO_HANDED` property, not on a specific
weapon name. Ranged and melee equipment slots remain separate loadout slots in
the engine rather than a single currently-in-hand state machine.

Example EB-13-022 pins that engine adaptation. A shield can occupy the melee
off-hand slot while a ranged-main weapon remains equipped and exposes its
attack template. The shield's AC bonus still contributes because the engine is
modeling parallel ready loadouts, not SRD object-interaction timing for
drawing, stowing, and swapping held objects:

```python
assert entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN)
assert entity.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
assert entity.equip_item(bow.uuid, WeaponSlot.RANGED_MAIN)
entity.update_entity_senses(max_distance=20)

action_names = {action.template_name for action in entity.get_available_actions().entity_actions}

assert entity.equipment.weapon_melee_off is shield
assert entity.equipment.weapon_ranged_main is bow
assert entity.ac_bonus().normalized_score == base_ac + 2
assert "Attack_MELEE_MAIN" in action_names
assert "Attack_RANGED_MAIN" in action_names
```

Example EB-13-015 captures the SRD heavy armor Strength requirement. Chain mail
has `strength_requirement == 13`; a STR 10 skeleton loses 10 feet of speed while
wearing it. The modifier is contextual, so raising Strength to the requirement
removes the speed penalty without re-equipping, and unequipping the armor
removes the rule hook entirely:

```python
assert entity.ability_scores.strength.ability_score.score == 10
assert entity.action_economy.movement.normalized_score == 30

assert entity.equipment.equip(chain_mail)

assert chain_mail.strength_requirement == 13
assert entity.action_economy.movement.normalized_score == 20

entity.ability_scores.strength.ability_score.self_static.add_value_modifier(strength_boost)

assert entity.ability_scores.strength.ability_score.score == 13
assert entity.action_economy.movement.normalized_score == 30

entity.ability_scores.strength.ability_score.self_static.remove_value_modifier(strength_boost.uuid)
assert entity.action_economy.movement.normalized_score == 20

entity.equipment.unequip(BodyPart.BODY)
assert entity.action_economy.movement.normalized_score == 30
```

Example EB-13-018 proves the destruction boundary for equipped items. When an
equipped item is destroyed, `BaseItem.destroy()` asks its container to remove
the item by UUID. `Equipment.remove_contained_item()` clears the slot without a
cancelable unequip event, but still calls item unequip hooks so modifiers and
derived values disappear:

```python
assert entity.equipment.equip(shield)
assert entity.ac_bonus().normalized_score == base_ac + 2

damage = shield.receive_damage(99, DamageType.BLUDGEONING, entity.uuid)

assert damage > 0
assert entity.equipment.weapon_melee_off is None
assert entity.ac_bonus().normalized_score == base_ac
assert BaseBlock.get(shield.uuid) is None

assert entity.equipment.equip(armor)
assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
assert entity.action_economy.movement.normalized_score == 20

armor.receive_damage(99, DamageType.BLUDGEONING, entity.uuid)

assert entity.equipment.body_armor is None
assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.NONE
assert entity.action_economy.movement.normalized_score == 30
assert BaseBlock.get(armor.uuid) is None
```

Example EB-13-019 pins weapon damage bonus accounting. A weapon's primary
damage bonus combines the selected ability modifier, the general equipment
damage bonus, and exactly one typed equipment damage bonus for the active slot:

```python
melee_base = damage_bonus(WeaponSlot.MELEE_MAIN)
ranged_base = damage_bonus(WeaponSlot.RANGED_MAIN)

entity.equipment.damage_bonus.self_static.add_value_modifier(general_bonus)
entity.equipment.melee_damage_bonus.self_static.add_value_modifier(melee_bonus)
entity.equipment.ranged_damage_bonus.self_static.add_value_modifier(ranged_bonus)

assert damage_bonus(WeaponSlot.MELEE_MAIN) == melee_base + 3 + 5
assert damage_bonus(WeaponSlot.RANGED_MAIN) == ranged_base + 3 + 7
```

Parity tests:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_004_equip_and_unequip_move_items_between_inventory_and_equipment`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_005_equipment_validates_weapon_slots_and_replaces_existing_items`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_016_canceled_direct_equip_preserves_existing_slot_item`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_013_canceled_high_level_equip_preserves_inventory_item`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_014_two_handed_melee_conflicts_auto_displace_by_equip_order`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_022_melee_and_ranged_slots_are_parallel_loadouts`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_015_heavy_armor_strength_requirement_reduces_speed`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_018_destroying_equipped_item_clears_slot_and_item_effects`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_019_equipment_damage_bonuses_are_counted_once`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Equip Hooks And Modifiers

Equippable items can implement `_on_equip()` and `_on_unequip()` hooks. The hook
pattern is how item data becomes engine state: armor can add a Stealth modifier,
weapons can register event handlers, and magical gear can add bonuses to nested
`ModifiableValue`s.

Example EB-13-006:

```python
assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.NONE

entity.equipment.equip(armor)
entity.equipment.equip(shield)

assert entity.equipment.body_armor is armor
assert entity.equipment.weapon_melee_off is shield
assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE

entity.equipment.unequip(BodyPart.BODY)
entity.equipment.unequip(WeaponSlot.MELEE_OFF)

assert entity.skill_set.stealth.skill_bonus.advantage == AdvantageStatus.NONE
```

Parity tests:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_006_equipment_hooks_apply_and_remove_modifiers`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Usable Items And Charges

`UsableItem` exposes item-bound actions. The default implementation deep-copies
the item's action templates and injects:

- the current user's `source_entity_uuid`;
- the item's `source_item_uuid`;
- a fresh action UUID.

Actions are hidden when the item lacks enough charges for the template's
`charge_cost`. On successful item-use execution, `execute_use_action()` calls
`consume_charge()`, which handles unlimited charges, finite charges,
stack-aware consumables, and final destruction.

Example EB-13-007:

```python
actions = potion.get_use_actions(entity.uuid)

assert len(actions) == 1
assert actions[0].source_entity_uuid == entity.uuid
assert actions[0].source_item_uuid == potion.uuid
assert actions[0].uuid != potion.use_action_templates[0].uuid

potion.charges = 0
assert potion.get_use_actions(entity.uuid) == []
```

Example EB-13-008:

```python
first = execute_use_action(entity, potion.uuid, "Drink Potion")
assert first is not None and not first.canceled
assert potion.stack_count == 1
assert potion.charges == potion.max_charges
assert entity.inventory.has_item(potion.uuid)

second = execute_use_action(entity, potion.uuid, "Drink Potion")
assert second is not None and not second.canceled
assert not entity.inventory.has_item(potion.uuid)
assert BaseBlock.get(potion.uuid) is None
```

Example EB-13-020 covers generic charge overspend. The default `UsableItem`
path now follows the same charge-cost rule as spell-scroll items: an action
whose `charge_cost` exceeds the item's current charges is not discoverable, and
direct execution by name fails before applying effects:

```python
potion.charges = 1
potion.max_charges = 2
potion.use_action_templates[0].charge_cost = 2
put_in_inventory(entity, potion)
set_hp(entity, 1)

assert potion.get_use_actions(entity.uuid) == []
try:
    execute_use_action(entity, potion.uuid, "Drink Potion")
    assert False
except ValueError as exc:
    assert "not found" in str(exc)

assert get_hp(entity) == 1
assert potion.charges == 1
assert entity.inventory.has_item(potion.uuid)
```

Parity tests:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_007_usable_item_actions_inject_user_and_item_identity`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_008_consumable_use_actions_consume_charges_and_stacks`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_020_generic_use_actions_require_sufficient_charges`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Environment Objects

Environment objects are items on the grid that are usually not pickable but can
be visible, targetable, blocking, breakable, or usable. Discovery runs through
senses: visible usable objects within interaction range can surface item-use
actions through available-action discovery. EB-13-009 checks the lower-level
sense membership and stateful object-provided actions directly.

Example EB-13-009:

```python
get_map().place_object(door.uuid, (1, 0))
entity.update_entity_senses(max_distance=5)

assert door.uuid in entity.senses.objects
assert door.blocks_movement
assert [action.name for action in door.get_use_actions(entity.uuid)] == ["Open Door"]

event = execute_use_action(entity, door.uuid, "Open Door")
assert event is not None and not event.canceled
assert door.is_open
assert not door.blocks_movement
assert [action.name for action in door.get_use_actions(entity.uuid)] == ["Close Door"]
```

Parity tests:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_009_environment_use_actions_are_stateful_and_spatial`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Breakable Containers And Destruction

Breakable items use an item-health block and `BaseItem.receive_damage()`.
Destruction calls `_on_destroy()` while the item still has location/container
context, then cleans conditions, light sources, container membership, floor
placement, equipment flags, and registry state.

Container items can use `_on_destroy()` to spill nested contents before the
container unregisters.

Example EB-13-010:

```python
damage = chest.receive_damage(99, DamageType.BLUDGEONING, uuid4())

assert damage > 0
assert BaseBlock.get(chest.uuid) is None
assert get_map().get_object_position(chest.uuid) is None
assert BaseBlock.get(gem.uuid) is gem
assert get_map().get_object_position(gem.uuid) == (2, 1)
assert gem.owner_uuid is None
assert gem.stored_in_uuid is None
assert gem.tile_uuid is not None
```

Parity tests:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_010_breakable_items_destroy_and_spill_nested_inventory`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Torches And Attached Light

Torches are usable items that create an anchored grid light source when ignited.
Their lifecycle hooks remove that light when the torch is extinguished, dropped,
destroyed, or otherwise cleaned up. EB-13-011 specifically proves ignition and
drop cleanup.

Example EB-13-011:

```python
event = execute_use_action(entity, torch.uuid, "Ignite Torch")

assert event is not None and not event.canceled
assert torch.is_lit
assert torch._light_source_uuid is not None
assert grid.get_tile(0, 0).resolved_light_level == LightLevel.VERY_BRIGHT

dropped = entity.drop_item(torch.uuid, (1, 0))

assert dropped is torch
assert torch.is_lit is False
assert torch._light_source_uuid is None
assert grid.get_tile(0, 0).resolved_light_level == LightLevel.DARKNESS
```

Parity tests:

- `tests/engine_book/test_chapter_13_items_inventory_equipment.py::test_eb_13_011_torch_lifecycle_manages_attached_light_sources`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

## Documentation Hygiene Notes

Chapter 13 cleanup fully reviewed `dnd/blocks/base_item.py`,
`dnd/blocks/inventory.py`, and `dnd/blocks/equipment.py`: these core item and
equipment files now have zero line comments, zero inline explanatory comments,
and zero Pydantic `Field(...)` declarations missing a `description`.

The supporting call sites were cleaned where Chapter 13 behavior depends on
them: entity loot/drop/equip helpers, grid-object actions in `dnd/actions.py`,
and the item fixtures in `dnd/items/test_items.py`. The fixture file now has no
inline code comments, no public model fields without `Field(...)`, and no
`Field(...)` declarations missing descriptions; it covers door, lever, chest,
campfire, scroll, wand, potion, weapon coat, device, torch, and wall torch
surfaces used by the item, spell, and monster examples. Armor factory helpers in
`dnd/items/armors.py` now have no inline code comments and use Google-style
factory docstrings. Directional environment objects in
`dnd/items/environment.py` now carry Pydantic field descriptions and Google-style
docstrings for directional walls, directional doors, and their open/close
actions. Weapon factories and hook-bearing weapon fixtures in
`dnd/items/weapons.py` now use Google-style docstrings, and `dnd/items/__init__.py`
has been reduced to clean exports and lookup tables. The package-level scan for
`dnd/items/*.py` now finds no `#` comments and no public model fields missing
`Field(...)` descriptions.

EB-13-012 now documents atomic failed stack insertion, EB-13-013 now documents
atomic high-level equip cancellation, and EB-13-014 now documents order-based
melee hand displacement for two-handed weapons versus shields/off-hand items.
EB-13-015 now documents contextual heavy armor Strength speed penalties.
EB-13-016 now documents direct equipment cancellation before replacement. The
pass also clarified that raw `Entity.drop_item()` does not perform distance
validation; the `Drop` action wrapper owns that validation.

## Findings And Follow-Up

The book examples pin the current stable item model. The earlier deeper Chapter
13 edge backlog is now covered by EB-13-017 through EB-13-022: transfer into
existing stacks, raw inventory rehoming, equipped destruction cleanup, generic
usable-item charge guards, damage-accounting guards, and parallel loadout
semantics. Add new Chapter 13 edges only after another source-code study finds a
fresh behavior gap.
