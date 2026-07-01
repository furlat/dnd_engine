# 09. Action Templates, Costs, And Discovery

## Purpose

Actions are the executable surface of the engine. Earlier chapters document state, values, events, entities, and conditions; this chapter documents how possible commands are registered, discovered, instantiated, paid for, and executed.

The examples are executable in both:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

The pytest file calls the same example functions, so the book examples and proper test suite stay in 1:1 parity.

## Source Files Studied

- `dnd/core/base_actions.py`
- `dnd/actions.py`
- `dnd/actions_functional.py`
- `dnd/entity.py`
- `dnd/blocks/base_item.py`
- `dnd/blocks/inventory.py`
- `dnd/items/test_items.py`
- `examples/test_available_actions.py`
- `examples/test_action_overrides.py`
- `examples/test_action_overrides_exec.py`
- `examples/test_inventory_use_actions.py`
- `examples/test_usable_items.py`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: Dash, Dodge, Disengage, Hide, Shove, attacks, and movement are represented as combat options related to `interactive_ruleset/Gameplay/Combat.md`.
- `SRD-aligned`: `Shake Awake` represents the action-based wake-up clause shared by `interactive_ruleset/Spells/Sleep.md` and `interactive_ruleset/Spells/Eyebite.md`.
- `SRD-aligned`: standard action costs consume actions, bonus actions, reactions, movement, or spell slots.
- `Engine extension`: actions are registered as templates and later instantiated into ephemeral executable actions.
- `Engine extension`: discovery returns UI-ready grouped action metadata with indexed targets.
- `Engine adaptation`: object interaction is modeled through explicit object and item-use action templates.
- `Engine adaptation`: Prone uses BG3-style auto-stand behavior, so voluntary Stand Up and Drop Prone are not standard registered actions.

## Templates And Instances

Registered actions are templates:

```python
Dash(source_entity_uuid=entity.uuid, template=True)
```

`Entity.register_action()` rejects non-template actions. A template cannot be executed directly. To execute it, the engine calls `instantiate()` with any target fields needed for that target type.

Instantiation:

- deep-copies the template;
- assigns a fresh UUID;
- sets `template=False`;
- sets `use_register=False`;
- preserves the source entity and static configuration.

Example EB-09-001:

```python
template = Dash(source_entity_uuid=entity.uuid, template=True)
entity.register_action(template)

with raises(ValueError):
    template.apply()

instance = template.instantiate()
assert instance.template is False
assert instance.uuid != template.uuid
assert instance.source_entity_uuid == template.source_entity_uuid
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_001_templates_must_be_registered_and_instantiated`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Costs

Actions hold `Cost` objects. A cost can include:

- a turn economy cost such as `actions`, `bonus_actions`, `reactions`, or `movement`;
- a spell slot cost;
- a named resource cost.

`BaseAction.check_costs()` checks `effective_costs`. `effective_costs` includes temporary override fields:

- `alt_cost_type`
- `alt_extra_costs`
- `alt_target_type`
- `alt_target_count`
- `alt_skip_slot`

The execution pipeline checks costs before declaration. Costs are consumed only after successful completion through `_apply_costs()`.

Current fix recorded by EB-09-007: subclass declaration events must serialize `effective_costs`, not raw `self.costs`, otherwise discovery and execution disagree under action overrides.

## Discovery Result Shape

`Entity.get_available_actions()` returns `AvailableActionsResult`:

- `entity_uuid`
- `entity_actions`
- `position_actions`
- `self_actions`
- `object_actions`
- `remaining_movement`
- `handler_details`

`all_actions` flattens groups in this order:

```python
entity_actions + position_actions + self_actions + object_actions
```

Each `AvailableActionInfo` includes:

- `template_name`
- `target_type`
- `valid_targets`
- `can_afford`
- display name and description
- cost type and amount
- weapon metadata when applicable
- action category
- item-use metadata when applicable

Example EB-09-002:

```python
available = get_available_actions(goblin)

assert {"Dash", "Dodge", "Disengage"}.issubset(self_names)
assert "Move" in position_names
assert "Jump" in position_names

dash_info = find_action(available, "Dash")
assert dash_info.target_type == TargetType.SELF
assert dash_info.valid_targets[0].index == 0
assert dash_info.cost_type == "actions"

attack_info = next(info for info in available.entity_actions if info.is_attack)
assert attack_info.weapon_slot is not None
assert attack_info.weapon_name is not None
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_002_standard_actions_discover_self_position_and_entity_groups`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Target Types

Target types decide which collector discovers an action and how execution instantiates it:

- `SELF`: one synthetic target at index 0 when valid.
- `ENTITY`: visible entity targets.
- `MULTI_ENTITY`: primary target plus extra target UUIDs.
- `POSITION_PATH`: path-based movement using `senses.paths`.
- `POSITION_LOS`: visible positions within range.
- `POSITION_AOE`: positions with AoE preview metadata.
- `OBJECT`: object UUID stored in `target_entity_uuid`.

Movement discovery includes path metadata:

- position
- distance
- path cost
- path
- hazardous path flag
- safe path cost/path when available

Example EB-09-011:

```python
hazard_tile = grid.get_tile(5, 5)
hazard = BaseCondition(
    name="Test Hazard",
    source_entity_uuid=uuid4(),
    target_entity_uuid=hazard_tile.uuid,
    hazard_filter=HazardFilter.ALL,
)
hazard_tile.add_condition(hazard)

scout = create_skeleton(name="Scout", position=(5, 3), faction="heroes")
Entity.update_all_entities_senses()

available = get_available_actions(scout)
move_info = find_action(available, "Move")
hazard_target = next(
    target for target in move_info.valid_targets if target.position == (5, 6)
)

assert hazard_target.is_path_hazardous is True
assert hazard_target.path is not None
assert hazard_target.safe_path is not None
assert hazard_target.safe_path_cost is not None
assert (5, 5) in hazard_target.path[1:]
assert (5, 5) not in hazard_target.safe_path[1:]

result = execute_by_index(
    scout,
    "Move",
    hazard_target.index,
    available=available,
    prefer_safe=True,
)

assert result is not None
assert result.path == hazard_target.safe_path
assert scout.position == hazard_target.position
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_011_move_discovery_marks_hazardous_and_safe_paths`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Entity Target Filters

`Entity.get_available_actions()` has two target-pool controls for entity actions:

- `target_filter`: `"enemies"` by default, or `"allies"` / `"all"`.
- `include_dead`: `False` by default, so entities with no HP are hidden from target lists.

These controls shape the discovery pool before `pre_validate()` is called. For attack actions, the default query shows living enemies only. An explicit ally or all-target query can surface friendly targets, and `include_dead=True` includes zero-HP entities.

Example EB-09-008:

```python
hero = create_goblin(name="Hero", position=(5, 5), faction="heroes")
ally = create_goblin(name="Ally", position=(5, 6), faction="heroes")
enemy = create_skeleton(name="Enemy", position=(6, 5), faction="monsters")
dead_enemy = create_skeleton(name="Dead Enemy", position=(6, 6), faction="monsters")
dead_enemy.health.take_damage(999, DamageType.BLUDGEONING, hero.uuid)

default_attack = find_attack_action(hero.get_available_actions())
assert [target.target_uuid for target in default_attack.valid_targets] == [enemy.uuid]

ally_attack = find_attack_action(hero.get_available_actions(target_filter="allies"))
assert [target.target_uuid for target in ally_attack.valid_targets] == [ally.uuid]

all_living_attack = find_attack_action(hero.get_available_actions(target_filter="all"))
assert [target.target_uuid for target in all_living_attack.valid_targets] == [
    enemy.uuid,
    ally.uuid,
]

all_targets_attack = find_attack_action(
    hero.get_available_actions(target_filter="all", include_dead=True)
)
assert [target.target_uuid for target in all_targets_attack.valid_targets] == [
    enemy.uuid,
    dead_enemy.uuid,
    ally.uuid,
]
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_008_target_filters_and_dead_targets_shape_entity_actions`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Multi-Entity Spell Discovery

Registered spells participate in the same template discovery system as weapon attacks and standard actions. `Magic Missile` is a registered `MULTI_ENTITY` spell: one primary indexed target is selected through `execute_by_index()`, and additional dart targets are passed as extra UUIDs. Discovery exposes spell-specific metadata for UI and controller layers:

- `target_type == TargetType.MULTI_ENTITY`
- `action_category == ActionCategory.SPELL`
- `base_template_name == "Magic Missile"`
- `cast_at_level == 1`
- `is_spell_variant is True`
- `num_projectiles == 3` at a 1st-level cast
- `allow_same_target is True`

Magic Missile spends both the normal action cost and a 1st-level spell slot. Each dart auto-hits and deals `1d4 + 1` force damage.

Example EB-09-009:

```python
register_spell(caster, MagicMissile, caster_level=5)

available = get_available_actions(caster)
missile_info = find_action(available, "Magic Missile__slot_1")

assert missile_info.target_type == TargetType.MULTI_ENTITY
assert missile_info.action_category == ActionCategory.SPELL
assert missile_info.base_template_name == "Magic Missile"
assert missile_info.cast_at_level == 1
assert missile_info.is_spell_variant
assert missile_info.num_projectiles == 3
assert missile_info.allow_same_target is True

result = execute_by_index(
    caster,
    "Magic Missile__slot_1",
    targets_by_name["Target 1"].index,
    extra_target_uuids=[
        str(targets_by_name["Target 2"].target_uuid),
        str(targets_by_name["Target 3"].target_uuid),
    ],
    available=available,
)

assert result is not None
assert result.total_targets == 3
assert caster.action_economy.actions.normalized_score == 0
assert caster.action_economy.spell_slot_1.normalized_score == 1
assert all(2 <= damage <= 5 for damage in damages.values())
assert result.total_damage == sum(damages.values())
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_009_registered_multi_entity_spell_discovers_and_executes`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Position AoE Spell Discovery

Registered `POSITION_AOE` spells also use the action-template discovery system. `Fireball` exposes position targets, and each target carries preview metadata for controller and UI layers:

- slot-specific execution name and `cast_at_level`;
- center position and distance;
- affected entity UUIDs and names;
- affected entity count;
- affected grid positions for the AoE shape preview.

Fireball's template uses a 20-foot sphere, targets all creatures in the area, and includes allies when they are inside the blast. Execution spends the action and a 3rd-level spell slot, then applies DEX-save fire damage to each affected creature.

Example EB-09-010:

```python
register_spell(caster, Fireball, caster_level=5)

available = get_available_actions(caster)
fireball_info = find_action(available, "Fireball__slot_3")
center_target = next(
    target for target in fireball_info.valid_targets if target.position == (6, 6)
)

assert fireball_info.target_type == TargetType.POSITION_AOE
assert fireball_info.action_category == ActionCategory.SPELL
assert fireball_info.base_template_name == "Fireball"
assert fireball_info.cast_at_level == 3
assert fireball_info.is_spell_variant
assert center_target.affected_count == 3
assert set(center_target.affected_entity_names or []) == {
    "Goblin 1",
    "Goblin 2",
    "Ally",
}
assert (6, 6) in set(center_target.affected_positions or [])

result = execute_by_index(caster, "Fireball__slot_3", center_target.index, available=available)

assert result is not None
assert result.total_targets == 3
assert result.aoe_position == (6, 6)
assert result.aoe_shape_type == "sphere"
assert result.aoe_radius_ft == 20
assert caster.action_economy.actions.normalized_score == 0
assert caster.action_economy.spell_slot_3.normalized_score == 0
assert all(damage > 0 for damage in damages.values())
assert result.total_damage == sum(damages.values())
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_010_registered_position_aoe_spell_previews_and_executes`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Execution By Index

`execute_by_index()` is the UI/CLI-friendly execution route:

1. Find the `AvailableActionInfo` by `template_name`.
2. Find the requested `AvailableTarget.index`.
3. Instantiate the registered template based on target type.
4. Apply the instance.

For item-use actions, it routes to `execute_use_action()` instead.

Example EB-09-003:

```python
available = get_available_actions(entity)
dash_info = find_action(available, "Dash")
result = execute_by_index(entity, dash_info.template_name, 0, available=available)

assert result is not None
assert "Dashing" in entity.active_conditions
assert entity.action_economy.actions.normalized_score == 0

after = get_available_actions(entity)
assert find_action(after, "Dash").can_afford is False
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_003_execute_by_index_instantiates_and_applies_costs`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Object Actions

Object actions come from registered templates with `TargetType.OBJECT`, such as:

- `Pick Up`
- `Attack Object`

The target UUID is the floor object UUID. `Pick Up` is free in this engine.
`Attack Object` is shown only for nearby breakable, targetable floor items.

Example EB-09-004:

```python
potion.place_on_grid((4, 3))
available = get_available_actions(entity)
pickup_info = find_action(available, "Pick Up")

assert pickup_info.target_type == TargetType.OBJECT
assert pickup_info.cost_amount == 0
assert any(target.target_uuid == potion.uuid for target in pickup_info.valid_targets)

execute_by_index(entity, "Pick Up", target_index, available=available)
assert potion.uuid in entity.inventory.items
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_004_floor_objects_create_object_actions_and_can_be_picked_up`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

Example EB-09-012:

```python
crate = BaseItem(
    source_entity_uuid=crate_source,
    name="Training Crate",
    is_pickable=False,
    is_targetable=True,
    health=BaseItem.create_item_health(
        crate_source,
        hp=4,
        hit_dice_value=4,
        vulnerabilities=[DamageType.BLUDGEONING],
    ),
)
crate.place_on_grid((4, 3))
Entity.update_all_entities_senses()

available = get_available_actions(entity)
attack_info = find_action(available, "Attack Object")
crate_target = next(
    target for target in attack_info.valid_targets if target.target_uuid == crate.uuid
)

assert attack_info.target_type == TargetType.OBJECT
assert attack_info.action_category == ActionCategory.ATTACK
assert attack_info.cost_type == "actions"
assert attack_info.cost_amount == 1
assert crate_target.target_name == "Training Crate"

result = execute_by_index(entity, "Attack Object", crate_target.index, available=available)

assert result is not None
assert BaseBlock.get(crate.uuid) is None
assert get_map().get_object_position(crate.uuid) is None
assert crate.uuid not in entity.senses.objects
assert entity.action_economy.actions.normalized_score == 0
```

EB-09-012 now keeps discovery and execution aligned: the action advertises one
standard action, and successful object damage consumes that action after the
object attack completes.

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_012_attack_object_discovers_and_destroys_breakables`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Item Use Actions

Item use actions come from two places:

- inventory items through `entity.inventory.get_all_use_actions(entity.uuid)`;
- nearby visible environment `UsableItem`s within 5 feet.

Discovery rewrites item-use template names to:

```text
{action_name}__item_{item_uuid}
```

and sets:

- `is_item_use=True`
- `source_item_uuid`
- optional stack count

Execution strips the suffix, asks the item for fresh use actions, applies the selected action, and consumes charges only if the result succeeds and is not canceled.

Example EB-09-005:

```python
potion = create_healing_potion(entity.uuid)
entity.loot_item(potion)

available = get_available_actions(entity)
potion_info = next(info for info in available.self_actions if info.is_item_use)

assert potion_info.template_name.startswith("Drink Potion__item_")
assert potion_info.source_item_uuid == potion.uuid

execute_by_index(entity, potion_info.template_name, 0, available=available)
assert potion.uuid not in entity.inventory.items
```

Example EB-09-006:

```python
nearby.place_on_grid((4, 3))
far.place_on_grid((8, 8))

source_item_uuids = {
    info.source_item_uuid
    for info in get_available_actions(entity).self_actions
    if info.is_item_use
}

assert nearby.uuid in source_item_uuids
assert far.uuid not in source_item_uuids
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_005_inventory_use_actions_are_routed_and_consume_charges`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_006_nearby_environment_use_actions_are_distance_gated`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Overrides

Action overrides mutate registered templates temporarily. They are used by features such as metamagic and item/class effects.

`apply_action_overrides()` returns the modified template UUIDs. `clear_action_overrides()` restores supported override fields on those templates.

Example EB-09-007:

```python
modified = apply_action_overrides(
    entity,
    lambda action: action.name == "Dash",
    {"alt_cost_type": "bonus_actions"},
)

dash_info = find_action(get_available_actions(entity), "Dash")
assert dash_info.cost_type == "bonus_actions"

execute_by_index(entity, "Dash", 0)
assert entity.action_economy.actions.normalized_score == 1
assert entity.action_economy.bonus_actions.normalized_score == 0

clear_action_overrides(entity, modified)
```

Parity tests:

- `tests/engine_book/test_chapter_09_action_templates_discovery.py::test_eb_09_007_action_overrides_change_cost_display_and_consumption`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

## Pytest Parity Layer

The legacy examples remain the existing regression floor, but the engine-book tests now also live under `tests/engine_book/`.

The pytest layer imports the exact `tests/engine_book/test_chapter_*.py` functions and parameterizes them. This gives:

- script compatibility for the current examples workflow;
- proper `uv run pytest` entry points;
- no duplicated assertion logic between book examples and tests.

Run focused chapter tests with:

```bash
uv run pytest -q tests/engine_book/test_chapter_09_action_templates_discovery.py
```

Do not run unrestricted `pytest` across the whole repository.

## Deeper Coverage Still Needed

- Add direct MULTI_ENTITY and POSITION_AOE examples in Chapter 14/15 with spell-specific target metadata.
- Add safe-path and hazardous-path movement discovery examples in the terrain chapter.
- Add `Attack Object` damage/breakage examples in the item/object chapter.
- Add resource-cost examples from class features once the class feature chapters are reached.
- Continue migrating engine-book parity into `tests/engine_book/` as new chapters are added.

## Documentation Hygiene Notes

- Chapter 09 hygiene reviewed `dnd/core/base_actions.py`, `dnd/actions_functional.py`, and the action registry/discovery region of `dnd/entity.py` from source behavior, not prior comments.
- `BaseCost`, `Cost`, `ActionEvent`, `BaseAction`, `StructuredAction`, `AvailableTarget`, `AvailableActionInfo`, and `AvailableActionsResult` now carry explicit Pydantic field descriptions for the Chapter 09 contracts they expose.
- Action template, instantiation, target filtering, target discovery, item-use routing, action override, and multi-target/AoE convolution comments were converted into Google-style docstrings or removed where the code was self-evident.
- `Attack Object` cost behavior was aligned with discovery: the object action
  advertises one action of cost and consumes that action after successful
  execution.
