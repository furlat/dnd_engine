# 14. Spellcasting Core

## Purpose

This chapter documents the spellcasting platform that every implemented spell
uses: spell slots, spellcasting modifiers, `SpellAction` metadata, spell event
payloads, registration, explicit variant generation, multi-target convolution,
and concentration bookkeeping.

Individual spell families are documented in the next chapter. This chapter is
only about the shared machinery underneath them.

The examples are executable in both:

- `tests/engine_book/test_chapter_14_spellcasting_core.py`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

The pytest file calls the same example functions, so the book examples and the
proper `uv run pytest` suite stay in 1:1 parity.

## Source Files Studied

- `dnd/actions.py`
- `dnd/core/base_actions.py`
- `dnd/actions_functional.py`
- `dnd/blocks/action_economy.py`
- `dnd/blocks/spellcasting.py`
- `dnd/entity.py`
- `dnd/conditions.py`
- `dnd/spells/__init__.py`
- `dnd/spells/evocation.py`
- `dnd/spells/enchantment.py`
- `dnd/spells/transmutation.py`
- `server/spell_catalog.py`
- `examples/test_spell_system.py`
- `examples/test_spell_catalog_api.py`
- `examples/test_spell_crit_dice.py`
- `examples/test_self_range_aoe_availability.py`
- `examples/test_concentration.py`
- `examples/test_concentration_spells.py`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: spell slots, spell slot levels, cantrip scaling at character
  levels 5, 11, and 17, spell attack bonuses, spell save DCs, upcasting, and
  concentration all correspond to local SRD material in
  `interactive_ruleset/Spells/# Spellcasting.md`.
- `SRD-aligned`: many individual spell classes map to entries in
  `interactive_ruleset/Spells/*.md`; this chapter only covers the generic
  casting substrate.
- `Engine adaptation`: known spells are registered as action templates on the
  entity rather than stored in `SpellcastingBlock`.
- `Engine adaptation`: spell slots are `ModifiableValue`s on `ActionEconomy`;
  spending a slot adds a negative cost modifier, and long rest removes those
  cost modifiers.
- `Engine adaptation`: upcast variants can be generated explicitly through
  `SpellAction.generate_variants()` and are also surfaced by
  `get_available_actions()` as executable slot-specific rows such as
  `Magic Missile__slot_3`.
- `Engine extension`: `SpellEvent` carries combat-log and client-facing metadata
  such as stable `spell_id`, AoE shape, range, projectile type, and damage
  types.

## Spell Slots

Spell slots live in `ActionEconomy`, not in `SpellcastingBlock`. The config
field `ActionEconomyConfig.spell_slots` seeds `spell_slot_1` through
`spell_slot_9` as `ModifiableValue`s.

Costs use the same action-cost pipeline as movement, actions, and reactions:

- `spell_slot_cost_type(1)` is `"spell_slot_1"`;
- `ActionEconomy.can_afford()` reads the slot value's `normalized_score`;
- `ActionEconomy.consume()` adds a negative cost modifier;
- `reset_all_costs()` restores turn resources but not spell slots;
- `reset_spell_slot_costs()` removes spell-slot cost modifiers.

Example EB-14-001:

```python
assert caster.action_economy.spell_slot_1.normalized_score == 2
assert caster.has_spell_slot(1)
assert caster.get_lowest_spell_slot(1) == 1

caster.action_economy.consume("spell_slot_1", 1)
assert caster.action_economy.spell_slot_1.normalized_score == 1

caster.action_economy.reset_all_costs()
assert caster.action_economy.spell_slot_1.normalized_score == 1

caster.action_economy.reset_spell_slot_costs()
assert caster.action_economy.spell_slot_1.normalized_score == 2
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_001_spell_slots_are_action_economy_values`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## SpellcastingBlock

`SpellcastingBlock` is modifier-only. Every entity has one, including
non-casters, but harmless defaults do not make the entity a spellcaster by
themselves.

Stored here:

- spellcasting ability;
- spell-specific attack bonus;
- spell-specific damage bonus;
- spell save DC bonus;
- spell crit threshold bonus;
- spell crit extra dice;
- extra spell damage payloads.

Not stored here:

- spell slots;
- known spells;
- proficiency bonus;
- generic attack/damage modifiers.

Example EB-14-002:

```python
block = SpellcastingBlock.create(
    source_entity_uuid=uuid4(),
    config=SpellcastingConfig(
        spellcasting_ability="wisdom",
        spell_attack_modifiers=[("Wand", 2)],
        spell_damage_modifiers=[("Elemental Affinity", 3)],
        spell_dc_modifiers=[("Focus", 1)],
        spell_crit_threshold_modifiers=[("Spell Sniper", 1)],
        spell_crit_extra_dice_modifiers=[("Arcane Surge", 2)],
        extra_spell_damage_dices=[6],
        extra_spell_damage_dices_numbers=[1],
        extra_spell_damage_bonus_modifiers=[[("Radiant Focus", 2)]],
        extra_spell_damage_types=["Radiant"],
    ),
)

assert block.spellcasting_ability == "wisdom"
assert block.spell_attack_bonus.normalized_score == 2
assert block.spell_damage_bonus.normalized_score == 3
assert block.spell_dc_bonus.normalized_score == 1
assert block.spell_crit_threshold.normalized_score == 1
assert block.spell_crit_extra_dice.normalized_score == 2
assert not hasattr(block, "spell_slot_1")
assert not hasattr(block, "known_spells")

extra_damage = block.get_extra_spell_damage()

assert len(extra_damage) == 1
assert extra_damage[0].damage_dice == 6
assert extra_damage[0].dice_numbers == 1
assert extra_damage[0].damage_bonus is not None
assert extra_damage[0].damage_bonus.normalized_score == 2
assert extra_damage[0].damage_type == DamageType.RADIANT
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_002_spellcasting_block_is_modifier_only`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Entity Spell Numbers

Entity spell helpers combine values from multiple blocks:

- `spell_attack_bonus()` combines proficiency, spellcasting ability score,
  ability modifier bonuses, generic equipment attack bonus, and spell-specific
  attack bonus.
- `spell_save_dc()` is `8 + proficiency + spellcasting ability modifier +
  spell_dc_bonus`.
- `get_spell_crit_threshold()` stacks generic equipment crit threshold and
  spell-specific crit threshold.
- `get_spell_crit_extra_dice()` stacks generic and spell-specific extra crit
  dice.
- `get_spell_damage_bonus()` combines generic equipment damage bonus and
  spell-specific damage bonus.

Example EB-14-003:

```python
assert caster.spell_attack_bonus().normalized_score == 10
assert caster.spell_save_dc() == 16
assert caster.get_spell_crit_threshold() == 18
assert caster.get_spell_crit_extra_dice() == 3
assert caster.get_spell_damage_bonus().normalized_score == 6
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_003_entity_spell_numbers_compose_from_multiple_blocks`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## SpellAction And SpellEvent

`SpellAction` is the base class for spells. It is a `BaseAction` with spell
metadata:

- `spell_level`;
- `spell_school`;
- `concentration`;
- `verbal`;
- `spell_range`;
- `cast_at_level`;
- `caster_level`;
- range/cost/target overrides;
- selected client-facing spell metadata.

`SpellAction.model_post_init()` marks concentration spells with
`requires_concentration` and adds a spell-slot cost for leveled spells. If a
leveled spell is constructed with `cast_at_level == 0`, it is cast at its base
spell level.

`SpellEvent` is the event payload for spell casts. It carries spell identity,
cast level, attack/save/damage details, selected AoE/range/projectile metadata,
and damage-type metadata. The parity example pins the declaration fields that
the current tests inspect.

Example EB-14-004:

```python
cantrip = FireBolt(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
missile = MagicMissile(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)

assert [cost.cost_type for cost in cantrip.costs] == ["actions"]
assert cantrip.cast_at_level == 0
assert [cost.cost_type for cost in missile.costs] == ["actions", "spell_slot_1"]
assert missile.cast_at_level == 1

declaration = missile._create_declaration_event(use_register=False)
assert declaration.spell_id == "magic_missile"
assert declaration.spell_level == 1
assert declaration.cast_at_level == 1
assert declaration.spell_school == "evocation"
assert declaration.range_ft == 120
assert declaration.projectile_type == "dart"
assert declaration.damage_types == [DamageType.FORCE]
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_004_spell_actions_create_spell_events_and_slot_costs`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Cantrips And Upcasting

Cantrip scaling is centralized in `SpellAction._get_cantrip_dice_count()`:

- caster level 1-4: one die;
- caster level 5-10: two dice;
- caster level 11-16: three dice;
- caster level 17+: four dice.

Example EB-14-005:

```python
assert cantrip._get_cantrip_dice_count(4) == 1
assert cantrip._get_cantrip_dice_count(5) == 2
assert cantrip._get_cantrip_dice_count(11) == 3
assert cantrip._get_cantrip_dice_count(17) == 4
```

Upcasting has two layers:

- `get_upcast_bonus()` returns `cast_at_level - spell_level`, clamped at zero;
- individual spells decide what that bonus means.

`MagicMissile`, for example, uses the bonus to add one dart per slot level above
1st level.

Example EB-14-006:

```python
cantrip_variants = cantrip_template.generate_variants(caster)
missile_variants = missile_template.generate_variants(caster)

assert len(cantrip_variants) == 1
assert cantrip_variants[0].cast_at_level == 0
assert cantrip_variants[0].template is False
assert cantrip_variants[0].use_register is False
assert [cost.cost_type for cost in cantrip_variants[0].costs] == ["actions"]

assert [variant.cast_at_level for variant in missile_variants] == [1, 3]
assert all(variant.template is False for variant in missile_variants)
assert all(variant.is_variant for variant in missile_variants)
assert [cost.cost_type for cost in missile_variants[1].costs] == [
    "actions",
    "spell_slot_3",
]
assert missile_variants[1].get_upcast_bonus() == 2
assert missile_variants[1].get_multi_target_count() == 5
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_005_cantrip_dice_scale_at_srd_thresholds`
- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_006_generate_variants_uses_available_slots`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Slot Variant Discovery

Registration stores spell templates directly in `Entity.registered_actions`.
During action discovery, leveled `SpellAction` templates expand through
`generate_variants()` into one discovery row per currently available spell slot
at or above the spell's base level.

Generated rows use stable execution names in the form
`Spell Name__slot_N`. The row also exposes `base_template_name`, `spell_level`,
`cast_at_level`, and `is_spell_variant`, so API clients do not need to parse the
name to display the slot level. `execute_by_index()` accepts the generated name
and creates the matching non-template spell variant before applying targets.

Cantrips remain available because they have no spell-slot cost.

Example EB-14-007:

```python
register_spell(caster, MagicMissile, caster_level=5)
register_spell(caster, FireBolt, caster_level=5)

available = get_available_actions(caster)
missile_actions = [
    info for info in available.entity_actions if info.base_template_name == "Magic Missile"
]

assert [info.template_name for info in missile_actions] == [
    "Magic Missile__slot_1",
    "Magic Missile__slot_3",
]
assert [info.cast_at_level for info in missile_actions] == [1, 3]
assert [info.num_projectiles for info in missile_actions] == [3, 5]

caster.action_economy.consume("spell_slot_1", 1)
caster.action_economy.reset_all_costs()

exhausted = get_available_actions(caster)
remaining_missiles = [
    info for info in exhausted.entity_actions if info.base_template_name == "Magic Missile"
]

assert [info.template_name for info in remaining_missiles] == ["Magic Missile__slot_3"]
assert any(info.template_name == "Fire Bolt" for info in exhausted.all_actions)

result = execute_by_index(caster, "Magic Missile__slot_3", target_index=0, available=exhausted)

assert result is not None and not result.canceled
assert result.cast_at_level == 3
assert result.total_targets == 5
assert caster.action_economy.spell_slot_3.normalized_score == 0
```

Example EB-14-019 shows that explicit variants remain executable directly:

```python
template = MagicMissile(source_entity_uuid=caster.uuid, template=True)
variants = template.generate_variants(caster)
level_three = next(variant for variant in variants if variant.cast_at_level == 3)
level_three.target_entity_uuid = target.uuid

result = level_three.apply()

assert result is not None and not result.canceled
assert result.cast_at_level == 3
assert result.total_targets == 5
assert caster.action_economy.spell_slot_1.normalized_score == 1
assert caster.action_economy.spell_slot_3.normalized_score == 0
```

The generated variant is a non-template action with its own cost list. Applying
the level 3 Magic Missile variant consumes the action and the level 3 slot,
leaves the level 1 slot untouched, and uses the upcast projectile count.

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_007_registered_spells_surface_executable_slot_variants`
- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_019_generated_upcast_variant_executes_with_higher_slot`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Temporary Spell Overrides

Spells inherit the shared action override fields from `BaseAction`. Conditions
and class features can temporarily mutate registered templates, then clean those
mutations up by UUID:

- `alt_cost_type`: replace the primary action cost, usually actions to bonus
  actions;
- `alt_extra_costs`: append additional resource costs;
- `alt_target_type` and `alt_target_count`: alter targeting shape;
- `alt_skip_slot`: remove spell slot costs from `effective_costs`;
- `alt_range`: override spell range.

The availability system reads `effective_costs`, so these overrides affect
registered templates immediately. Variant generation is different: leveled
spell variants are still generated only for currently available slots, even
when `alt_skip_slot=True`.

Example EB-14-012:

```python
template = caster.get_action_template("Magic Missile")
assert isinstance(template, SpellAction)
assert template.generate_variants(caster) == []
assert not any(info.template_name == "Magic Missile" for info in get_available_actions(caster).all_actions)

modified = apply_action_overrides(
    caster,
    lambda action: action.name == "Magic Missile",
    {"alt_skip_slot": True, "alt_cost_type": "bonus_actions"},
)

template = caster.get_action_template("Magic Missile")
assert isinstance(template, SpellAction)
assert [(cost.name, cost.cost_type, cost.cost) for cost in template.effective_costs] == [
    ("Cast Spell", "bonus_actions", 1)
]

available = get_available_actions(caster)
assert len([info for info in available.all_actions if info.template_name == "Magic Missile"]) == 1
assert template.generate_variants(caster) == []

clear_action_overrides(caster, modified)
```

Example EB-14-018 covers range overrides. A target at 130 feet is visible but
outside Fire Bolt's normal 120-foot range. `alt_range=300` makes the registered
template discover that target, and clearing the override removes it again:

```python
reset_spell_state(width=32, height=2)
caster = create_spellcaster(position=(0, 0), spell_slots={})
far_target = create_spell_target(position=(26, 0))
Entity.update_all_entities_senses(max_distance=32)
register_spell(caster, FireBolt, caster_level=5)

def has_fire_bolt_target() -> bool:
    available = get_available_actions(caster)
    return any(
        target_info.target_uuid == far_target.uuid
        for info in available.entity_actions
        if info.template_name == "Fire Bolt"
        for target_info in info.valid_targets
    )

template = caster.get_action_template("Fire Bolt")
assert isinstance(template, SpellAction)
assert template.effective_range == 120
assert not has_fire_bolt_target()

modified = apply_action_overrides(
    caster,
    lambda action: action.name == "Fire Bolt",
    {"alt_range": 300},
)

assert modified == [template.uuid]
assert template.effective_range == 300
assert template.get_range().normal == 300
assert has_fire_bolt_target()

clear_action_overrides(caster, modified)

assert template.alt_range is None
assert template.effective_range == 120
assert not has_fire_bolt_target()
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_012_spell_action_overrides_change_template_costs_not_slot_variant_discovery`
- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_018_spell_range_overrides_affect_discovery_and_clear_cleanly`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Multi-Target Convolution

Spells use the normal `BaseAction.apply()` pipeline. For `MULTI_ENTITY` and
`POSITION_AOE` spells, the base action performs convolution:

1. Build the parent execution event.
2. Resolve all target UUIDs.
3. Create one child event per target with its own lineage.
4. Call the spell's `_apply()` for each child.
5. Aggregate `total_targets` and `total_damage` onto the parent event.
6. Complete the parent so combat logs can collect child entries.

Example EB-14-008 uses `MagicMissile`, which fills missing darts with the
primary target and observes the aggregate parent totals produced by the child
cast convolution:

```python
event = MagicMissile(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
).apply()

assert event.total_targets == 3
assert 6 <= event.total_damage <= 15
assert get_hp(target) == initial_hp - event.total_damage
assert caster.action_economy.spell_slot_1.normalized_score == 0
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_008_magic_missile_convolution_aggregates_child_casts`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Spell Damage Metadata

`SpellEvent.phase_to()` auto-populates `damage_types` from a supplied `damages`
payload when the caller did not already provide `damage_types`. Duplicate
damage types are collapsed while preserving first-seen order.

Example EB-14-009:

```python
updated = event.phase_to(EventPhase.COMPLETION, damages=damages)

assert updated.damage_types == [DamageType.FIRE, DamageType.FORCE]
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_009_spell_event_damage_types_follow_damage_payloads`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Concentration

Concentration is represented by the `Concentrating` condition on the caster.
`SpellAction.ensure_concentration()` creates or reuses that condition for the
current cast. The condition owns concentration slots and linked spell effects.

When concentration ends, `BaseBlock` cleanup removes the linked effects. When a
concentration spell completes without any linked effects, `_cleanup_concentration()`
removes the empty concentration condition.

Example EB-14-010:

```python
linked_event = BookLinkedConcentrationSpell(source_entity_uuid=caster.uuid).apply()

assert "Concentrating" in caster.active_conditions
assert "Dashing" in caster.active_conditions
assert len(caster.active_conditions["Concentrating"].linked_conditions) == 1

caster.remove_condition("Concentrating")

assert "Concentrating" not in caster.active_conditions
assert "Dashing" not in caster.active_conditions

caster.action_economy.reset_all_costs()
empty_event = BookEmptyConcentrationSpell(source_entity_uuid=caster.uuid).apply()
assert not empty_event.canceled
assert "Concentrating" not in caster.active_conditions
```

`DropConcentration` can also remove one named concentration spell while leaving
other active concentration slots intact. This is outside the usual SRD
one-concentration limit, but the engine supports it through
`max_concentration_slots`, so the book pins the behavior directly.

Example EB-14-014:

```python
caster.max_concentration_slots.self_static.add_value_modifier(
    NumericalModifier(
        name="Book Multi Concentration",
        value=1,
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
    )
)

first = BookNamedConcentrationSpell(
    source_entity_uuid=caster.uuid,
    name="Book First Concentration",
    linked_effect_name="Book First Effect",
    template=False,
).apply()
caster.action_economy.reset_all_costs()
second = BookNamedConcentrationSpell(
    source_entity_uuid=caster.uuid,
    name="Book Second Concentration",
    linked_effect_name="Book Second Effect",
    template=False,
).apply()

assert isinstance(first, SpellEvent) and not first.canceled
assert isinstance(second, SpellEvent) and not second.canceled
concentration = caster.active_conditions["Concentrating"]
assert isinstance(concentration, Concentrating)
assert len(concentration.concentration_slots) == 2
assert "Book First Effect" in caster.active_conditions
assert "Book Second Effect" in caster.active_conditions

actions_before_drop = caster.action_economy.actions.normalized_score
drop_event = DropConcentration(
    source_entity_uuid=caster.uuid,
    target_spell="Book First Concentration",
    template=False,
).apply()

assert drop_event is not None and not drop_event.canceled
assert caster.action_economy.actions.normalized_score == actions_before_drop
assert "Book First Effect" not in caster.active_conditions
assert "Book Second Effect" in caster.active_conditions
remaining = caster.active_conditions["Concentrating"]
assert isinstance(remaining, Concentrating)
assert remaining.spell_name == "Book Second Concentration"
```

Damage and death use separate event routes. Damage breaks concentration through
the `TAKE_DAMAGE` EFFECT handler after an impossible Constitution save; death
breaks concentration through the `DEATH` EFFECT handler without rolling a save.

Example EB-14-015:

```python
set_hp(caster, 100)
cast_event = BookNamedConcentrationSpell(
    source_entity_uuid=caster.uuid,
    name="Book Fragile Concentration",
    linked_effect_name="Book Fragile Effect",
    template=False,
).apply()

starting_hp = get_hp(caster)
actual_damage = caster.receive_damage(60, DamageType.FIRE, caster.uuid)

assert actual_damage == 60
assert get_hp(caster) == starting_hp - 60
assert "Concentrating" not in caster.active_conditions
assert "Book Fragile Effect" not in caster.active_conditions

dying_caster = create_spellcaster(name="Death-Test Wizard", position=(2, 0))
death_cast = BookNamedConcentrationSpell(
    source_entity_uuid=dying_caster.uuid,
    name="Book Death Concentration",
    linked_effect_name="Book Death Effect",
    template=False,
).apply()

assert isinstance(death_cast, SpellEvent) and not death_cast.canceled
assert "Concentrating" in dying_caster.active_conditions
assert "Book Death Effect" in dying_caster.active_conditions

death_event = DeathEvent(
    source_entity_uuid=dying_caster.uuid,
    target_entity_uuid=dying_caster.uuid,
    entity_uuid=dying_caster.uuid,
    entity_name=dying_caster.name,
    killer_uuid=dying_caster.uuid,
    killer_name=dying_caster.name,
    final_hp=0,
)
death_event = death_event.phase_to(EventPhase.EXECUTION)
death_event = death_event.phase_to(EventPhase.EFFECT)

assert not death_event.canceled
assert "Concentrating" not in dying_caster.active_conditions
assert "Book Death Effect" not in dying_caster.active_conditions
```

For a single multi-target concentration cast, `BaseAction.apply()` calls
`_apply()` once per target on the same spell instance. `SpellAction` stores the
first `Concentrating` UUID in `cast_concentrating_uuid`, so later targets in the
same cast reuse the same condition and the same concentration slot.

Example EB-14-016:

```python
spell = BookMultiTargetConcentrationSpell(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=first_target.uuid,
    extra_target_entity_uuids=[second_target.uuid],
    template=False,
)
event = spell.apply()

assert event is not None and not event.canceled
assert "Book Multi Effect First Target" in first_target.active_conditions
assert "Book Multi Effect Second Target" in second_target.active_conditions

concentration = caster.active_conditions["Concentrating"]
assert isinstance(concentration, Concentrating)
assert spell.cast_concentrating_uuid == concentration.uuid
assert len(concentration.concentration_slots) == 1

slot = next(iter(concentration.concentration_slots.values()))
assert slot.spell_name == "Book Multi Concentration"
assert len(concentration.linked_conditions) == 2

caster.remove_condition("Concentrating")

assert "Book Multi Effect First Target" not in first_target.active_conditions
assert "Book Multi Effect Second Target" not in second_target.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_010_concentration_links_cleanup_and_empty_casts`
- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_014_drop_concentration_can_target_one_multi_slot_spell`
- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_015_damage_and_death_break_concentration_deterministically`
- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_016_multi_target_concentration_reuses_one_slot`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Registration And Setup Order

`register_spell()` is intentionally thin: instantiate the spell class with
`source_entity_uuid`, `caster_level`, and `template=True`, then register it on
the entity.

`register_spells_by_name()` performs exact-name lookup in `ALL_SPELLS` and
raises `ValueError` for unknown names.

`setup_standard_actions()` clears `registered_actions` before adding standard
actions. Therefore the safe order is:

1. call `setup_standard_actions(entity)`;
2. then register spells.

Example EB-14-011:

```python
register_spells_by_name(caster, ["Fire Bolt", "Magic Missile"], caster_level=5)

assert [action.name for action in caster.registered_actions] == [
    "Fire Bolt",
    "Magic Missile",
]
fire_bolt_template = caster.get_action_template("Fire Bolt")
assert isinstance(fire_bolt_template, SpellAction)
assert fire_bolt_template.caster_level == 5

setup_standard_actions(caster)

assert caster.get_action_template("Fire Bolt") is None
assert caster.get_action_template("Drop Concentration") is not None

register_spell(caster, FireBolt, caster_level=5)

assert caster.get_action_template("Fire Bolt") is not None
```

Example EB-14-013 records the `is_spellcaster` boundary for cantrip-only
casters. The SRD treats cantrips as level 0 spells that can be cast without
spell slots, and the engine represents known or prepared spells as registered
`SpellAction` templates. A cantrip-only entity therefore has no spell slots, but
becomes a spellcaster as soon as it has a registered cantrip template:

```python
assert caster.is_spellcaster is False

register_spell(caster, FireBolt, caster_level=5)

available = get_available_actions(caster)
cantrips = [info for info in available.entity_actions if info.template_name == "Fire Bolt"]

assert len(cantrips) == 1
assert caster.is_spellcaster is True
```

This keeps `SpellcastingBlock` defaults harmless while making registered spell
templates part of the spellcaster identity check.

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_011_spell_registration_uses_templates_and_setup_order_matters`
- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_013_registered_cantrip_makes_entity_spellcaster`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Catalog Identity

The spell catalog starts from the level dictionaries in `dnd/spells/__init__.py`.
`ALL_SPELLS` is the union of those buckets, and backend catalog entries use
`normalize_spell_id(display_name)`. `SpellAction._create_declaration_event()`
uses the same normalizer, so a spell's `SpellEvent.spell_id` matches the
backend catalog id.

Example EB-14-017:

```python
level_buckets = {
    0: CANTRIPS,
    1: LEVEL_1_SPELLS,
    2: LEVEL_2_SPELLS,
    3: LEVEL_3_SPELLS,
    4: LEVEL_4_SPELLS,
    5: LEVEL_5_SPELLS,
    6: LEVEL_6_SPELLS,
    7: LEVEL_7_SPELLS,
    8: LEVEL_8_SPELLS,
    9: LEVEL_9_SPELLS,
}
bucketed_names = [name for spells in level_buckets.values() for name in spells]

assert len(bucketed_names) == len(set(bucketed_names))
assert set(bucketed_names) == set(ALL_SPELLS)

before_registry_count = len(BaseObject._registry)
entries = {
    normalize_spell_id(display_name): build_spell_catalog_entry(display_name, spell_cls)
    for display_name, spell_cls in ALL_SPELLS.items()
}
after_registry_count = len(BaseObject._registry)

assert after_registry_count == before_registry_count
assert len(entries) == len(ALL_SPELLS)

for expected_level, spells in level_buckets.items():
    for display_name in spells:
        entry = entries[normalize_spell_id(display_name)]
        assert entry.name == display_name
        assert entry.level == expected_level

for display_name in ("Fire Bolt", "Magic Missile", "Fireball"):
    spell_cls = ALL_SPELLS[display_name]
    spell = spell_cls(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        use_register=False,
    )
    event = spell._create_declaration_event(use_register=False)

    assert isinstance(event, SpellEvent)
    assert event.spell_id == entries[normalize_spell_id(display_name)].id
    assert event.spell_level == entries[normalize_spell_id(display_name)].level
```

Representative metadata is still checked where it belongs in the same catalog
contract: Magic Missile exposes multi-target volley metadata, and Fireball
exposes Dexterity-save metadata.

Parity tests:

- `tests/engine_book/test_chapter_14_spellcasting_core.py::test_eb_14_017_spell_catalog_identity_matches_spell_events`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

## Documentation Hygiene Notes

Chapter 14 cleanup normalized the fully spellcasting-owned blocks first:

- `dnd/blocks/action_economy.py` now has zero standalone comments, zero inline
  comment markers, and descriptions on all Pydantic fields.
- `dnd/blocks/spellcasting.py` now has zero comments and descriptions on all
  Pydantic fields, including the extra spell damage configuration.
- `dnd/actions.py` now has zero standalone comments and zero missing Pydantic
  field descriptions. The one remaining inline hash marker is a type-checker
  directive on the `Hidden` constructor call.
- `EntityConfig.spellcasting` now describes the actual default behavior: every
  entity receives harmless spellcasting defaults when no explicit config is
  supplied.
- `dnd/spells/__init__.py` now describes itself as the spell catalog export
  surface rather than claiming to provide registration utilities.

Behavior intentionally preserved:

- registered leveled spells surface as executable slot-specific discovery rows;
- `alt_skip_slot` changes template `effective_costs` but does not make
  `generate_variants()` ignore slot availability;
- `alt_range` affects template discovery through `get_range()` and is cleared
  by `clear_action_overrides()`;
- `Entity.is_spellcaster` recognizes registered cantrip templates.

## Findings And Follow-Up

The book examples pin the current spellcasting-core model. Deeper Chapter 14
edge coverage should add:

- additional class-specific metamagic action costs.
