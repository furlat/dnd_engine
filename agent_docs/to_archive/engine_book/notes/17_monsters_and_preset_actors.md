# 17. Monsters And Preset Actors

## Purpose

This chapter documents the current monster layer: factory functions that create
fully wired `Entity` instances, plus preset actors that extend a monster-like
base with custom equipment, actions, spells, and items.

The examples are executable in both:

- `tests/engine_book/test_chapter_17_monsters_presets.py`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

The pytest file calls the same example functions, so the book examples and the
`uv run pytest` suite stay in 1:1 parity.

## Source Files Studied

- `dnd/monsters/bestiary.py`
- `dnd/monsters/skeleton_abilities.py`
- `dnd/monsters/circus_fighter.py`
- `dnd/monsters/circus_fighter_conditions.py`
- `dnd/items/test_items.py`
- `dnd/spells/evocation.py`
- `dnd/spells/necromancy.py`
- `dnd/spells/abjuration.py`
- `dnd/spells/illusion.py`
- `dnd/spells/transmutation.py`
- `dnd/actions_functional.py`
- `dnd/entity.py`
- `examples/test_skeleton_units.py`
- `tests/engine_book/test_chapter_17_monsters_presets.py`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: `create_goblin()` uses the SRD goblin's core ability scores,
  AC 15 through leather armor plus shield, Stealth expertise-like bonus, speed,
  darkvision, scimitar, shortbow, and Nimble Escape bonus-action Hide/Disengage
  from `interactive_ruleset/Monsters/Goblin.md`.
- `SRD-aligned`: `create_skeleton()` uses the SRD skeleton's core ability
  scores, undead creature type, armor scraps AC 13, bludgeoning vulnerability,
  poison damage immunity, Poisoned and Exhaustion condition immunities,
  darkvision, shortsword, and shortbow from
  `interactive_ruleset/Monsters/Skeleton.md`.
- `Engine extension`: `create_skeleton(darkvision=False)` remains available for
  tests that need a skeleton-shaped actor without darkvision.
- `Engine deviation`: factory comments describe SRD average hit points, but the
  live `Health`/`HitDice` model currently computes higher HP values:
  goblin 10 instead of SRD 7, skeleton 17 instead of SRD 13.
- `Engine extension`: `create_skeleton_warrior()`,
  `create_skeleton_archer()`, and `create_skeleton_warlock()` are custom preset
  actors, not SRD stat blocks. They reuse skeleton-like undead defenses and add
  engine-specific tactical roles.
- `Engine extension`: `Mark Target`, `Acid Flask`, the skeleton warlock spell
  package, and Scroll of Invisibility inventory wiring are game presets built on
  ordinary engine primitives.
- `Engine extension`: `create_caster()` is a generic test spellcaster preset,
  not an SRD monster and not a class factory. It reuses SRD-named spell actions
  such as Fireball, Magic Missile, Burning Hands, Lightning Bolt, Shatter,
  Thunderwave, Invisibility, and Greater Invisibility, but gives them to a
  single constructed actor with generous spell slots and inventory potions.
- `Engine extension`: `dnd/monsters/circus_fighter.py` is a legacy/custom
  preset actor, not an SRD stat block. It creates a performer-fighter with
  bespoke weapons and applies custom conditions from
  `dnd/monsters/circus_fighter_conditions.py`.

The SRD monster-stat guidance in
`interactive_ruleset/Monsters/# Monster Statistics.md` describes monsters as
stat blocks with size, type, AC, hit points, speed, abilities, senses, and
actions. The engine does not currently parse those stat blocks declaratively;
it constructs equivalent or variant runtime state through Python factories.

## Factory Pattern

Monster factories are composition functions. They:

- build `AbilityScoresConfig`, `HealthConfig`, `EquipmentConfig`, and
  `ActionEconomyConfig`;
- call `Entity.create()` with position, faction, weight, creature type, and
  appearance;
- call `setup_standard_actions()` to add the shared action set;
- create and equip items, which in turn registers attack templates;
- optionally add spellcasting, spells, reactions, inventory items, or custom
  action templates.

Example EB-17-001 proves the basic factory state:

```python
goblin = create_goblin(position=(1, 1), faction="monsters")
skeleton = create_skeleton(position=(3, 1), faction="monsters")
skeleton_without_darkvision = create_skeleton(darkvision=False)

assert goblin.ac_bonus().normalized_score == 15
assert equipped_item_name(goblin, WeaponSlot.MELEE_MAIN) == "Scimitar"
assert get_max_hp(goblin) == 10

assert skeleton.creature_type == CreatureType.UNDEAD
assert skeleton.health.get_resistance(DamageType.BLUDGEONING) == ResistanceStatus.VULNERABILITY
assert skeleton.health.get_resistance(DamageType.POISON) == ResistanceStatus.IMMUNITY
assert equipped_item_name(skeleton, WeaponSlot.RANGED_MAIN) == "Shortbow"
assert "Attack_RANGED_MAIN" in action_template_names(skeleton)
assert skeleton.check_condition_immunity("Poisoned")
assert skeleton.check_condition_immunity("Exhaustion")
assert has_darkvision(skeleton)
assert not has_darkvision(skeleton_without_darkvision)
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_001_goblin_and_skeleton_factories_encode_srd_trait_state`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Base Goblin SRD Traits

The base goblin factory now models the SRD goblin's darkvision, scimitar,
shortbow, and `Nimble Escape` feature. The normal shared `Hide` and
`Disengage` actions remain action-cost templates; the goblin receives separate
Nimble Escape templates that reuse those behaviors with bonus-action costs.

Example EB-17-007 freezes that contract:

```python
goblin = create_goblin(position=(1, 1), faction="monsters")
action_names = action_template_names(goblin)
hide_template = goblin.get_action_template("Hide")
disengage_template = goblin.get_action_template("Disengage")
nimble_hide = goblin.get_action_template("Nimble Escape: Hide")
nimble_disengage = goblin.get_action_template("Nimble Escape: Disengage")

assert has_darkvision(goblin)
assert equipped_item_name(goblin, WeaponSlot.RANGED_MAIN) == "Shortbow"
assert "Attack_RANGED_MAIN" in action_names
assert {"Nimble Escape: Hide", "Nimble Escape: Disengage"} <= action_names

assert {"Hide", "Disengage"} <= action_names
assert hide_template is not None
assert disengage_template is not None
assert nimble_hide is not None
assert nimble_disengage is not None
assert [cost.cost_type for cost in hide_template.effective_costs] == ["actions"]
assert [cost.cost_type for cost in disengage_template.effective_costs] == ["actions"]
assert [cost.cost_type for cost in nimble_hide.effective_costs] == ["bonus_actions"]
assert [cost.cost_type for cost in nimble_disengage.effective_costs] == ["bonus_actions"]

nimble_event = nimble_disengage.instantiate().apply()
assert nimble_event is not None
assert not nimble_event.canceled
assert goblin.action_economy.actions.normalized_score == 1
assert goblin.action_economy.bonus_actions.normalized_score == 0
assert "Disengaging" in goblin.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_007_base_goblin_factory_models_srd_senses_attacks_and_nimble_escape`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Base Skeleton SRD Traits

The base skeleton factory models the SRD skeleton's senses, weapon actions, and
immunity surfaces through ordinary engine state:

- poison damage immunity is present;
- `Poisoned` and `Exhaustion` condition immunities are present and cancel
  attempted condition applications;
- darkvision is present by default, with `create_skeleton(darkvision=False)` as
  an explicit test override;
- a shortbow is equipped in `RANGED_MAIN`, so the normal ranged attack template
  exists.

Example EB-17-008 freezes that contract:

```python
skeleton = create_skeleton(position=(1, 1), faction="monsters")
skeleton_without_darkvision = create_skeleton(darkvision=False)
action_names = action_template_names(skeleton)
poisoned_event = skeleton.add_condition(
    Poisoned(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
)
exhaustion_event = skeleton.add_condition(
    Exhaustion(source_entity_uuid=skeleton.uuid, target_entity_uuid=skeleton.uuid)
)

assert has_darkvision(skeleton)
assert not has_darkvision(skeleton_without_darkvision)
assert equipped_item_name(skeleton, WeaponSlot.RANGED_MAIN) == "Shortbow"
assert "Attack_RANGED_MAIN" in action_names

assert skeleton.health.get_resistance(DamageType.POISON) == ResistanceStatus.IMMUNITY
assert skeleton.check_condition_immunity("Poisoned")
assert skeleton.check_condition_immunity("Exhaustion")
assert poisoned_event is not None
assert poisoned_event.canceled
assert exhaustion_event is not None
assert exhaustion_event.canceled
assert "Poisoned" not in skeleton.active_conditions
assert "Exhaustion" not in skeleton.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_008_base_skeleton_factory_models_srd_senses_attacks_and_immunities`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Monster HP Average Semantics

Monster factories use `HitDiceConfig(mode="average", ignore_first_level=False)`.
The live `HitDice.hit_points` calculation does not use the SRD monster average
directly. It treats the first die as maximum, then adds `(die_size // 2) + 1`
for each remaining die. `Health.get_max_hit_dices_points()` then adds the
Constitution modifier once per hit die.

That gives the current monster HP values:

- goblin: `d6` first die `6` plus one average `4`, CON modifier `0`, for 10;
- skeleton: `d8` first die `8` plus one average `5`, plus CON modifier `2`
  across two hit dice, for 17.

Example EB-17-009 freezes that formula:

```python
goblin = create_goblin(position=(1, 1), faction="monsters")
skeleton = create_skeleton(position=(3, 1), faction="monsters")

goblin_hit_dice = goblin.health.hit_dices[0]
skeleton_hit_dice = skeleton.health.hit_dices[0]

assert goblin_hit_dice.mode == "average"
assert not goblin_hit_dice.ignore_first_level
assert goblin_hit_dice.hit_dice_value.score == 6
assert goblin_hit_dice.hit_dice_count.score == 2
assert goblin_hit_dice.hit_points == 10
assert goblin.ability_scores.constitution.modifier == 0
assert get_max_hp(goblin) == 10

assert skeleton_hit_dice.mode == "average"
assert not skeleton_hit_dice.ignore_first_level
assert skeleton_hit_dice.hit_dice_value.score == 8
assert skeleton_hit_dice.hit_dice_count.score == 2
assert skeleton_hit_dice.hit_points == 13
assert skeleton.ability_scores.constitution.modifier == 2
assert skeleton.health.get_max_hit_dices_points(constitution_modifier=2) == 17
assert get_max_hp(skeleton) == 17
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_009_monster_average_hit_dice_use_first_die_maximum`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Generic Caster Preset

`create_caster()` builds a generic spellcaster actor for spell and combat tests.
It is not a class implementation. It composes:

- Charisma spellcasting through `SpellcastingConfig(spellcasting_ability="charisma")`;
- maximum-mode d6 hit dice using the requested level as hit-dice count;
- a generous spell-slot table from level 1 through 9;
- standard actions plus a dagger attack;
- spell templates for Fire Bolt, Magic Missile, Fireball, Burning Hands,
  Lightning Bolt, Shatter, Thunderwave, Invisibility, and Greater Invisibility;
- a player-toggleable Shield reaction handler;
- Potion of Greater Invisibility and Potion of Haste inventory items.

Example EB-17-010 freezes the core actor state:

```python
caster = create_caster(position=(1, 1), faction="heroes", level=5)
action_names = action_template_names(caster)
hit_dice = caster.health.hit_dices[0]
shield_handler = caster.get_event_handler_by_name("Shield")

assert caster.is_spellcaster
assert caster.spellcasting.spellcasting_ability == "charisma"
assert caster.ability_scores.charisma.modifier == 4
assert caster.proficiency_bonus.normalized_score == 3
assert caster.spell_attack_bonus().normalized_score == 7
assert caster.spell_save_dc() == 15

assert hit_dice.mode == "maximums"
assert hit_dice.hit_dice_value.score == 6
assert hit_dice.hit_dice_count.score == 5
assert hit_dice.hit_points == 30
assert get_max_hp(caster) == 40

assert {"Fire Bolt", "Magic Missile", "Fireball", "Burning Hands"} <= action_names
assert equipped_item_name(caster, WeaponSlot.MELEE_MAIN) == "Dagger"
assert shield_handler is not None
assert shield_handler.player_toggleable
```

Example EB-17-011 freezes the potion item-use surface:

```python
invisibility_potion = get_inventory_item(caster, "Potion of Greater Invisibility")
haste_potion = get_inventory_item(caster, "Potion of Haste")
invisibility_actions = invisibility_potion.get_use_actions(caster.uuid)
haste_actions = haste_potion.get_use_actions(caster.uuid)
available_item_names = available_item_template_names(caster)

assert invisibility_potion.is_consumable
assert invisibility_potion.charges == 1
assert invisibility_potion.stack_id == "potion_of_greater_invisibility"
assert invisibility_actions[0].name == "Drink Greater Invisibility Potion"
assert invisibility_actions[0].source_item_uuid == invisibility_potion.uuid
assert invisibility_actions[0].effective_costs == []

assert haste_potion.is_consumable
assert haste_potion.charges == 1
assert haste_potion.stack_id == "potion_of_haste"
assert haste_actions[0].name == "Drink Haste Potion"
assert haste_actions[0].source_item_uuid == haste_potion.uuid
assert haste_actions[0].effective_costs == []

assert any(name.startswith("Drink Greater Invisibility Potion") for name in available_item_names)
assert any(name.startswith("Drink Haste Potion") for name in available_item_names)
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_010_create_caster_wires_generic_spellcaster_state`
- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_011_create_caster_inventory_potions_are_item_use_actions`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Circus Warrior Preset

`create_warrior()` in `dnd/monsters/circus_fighter.py` is a custom legacy
preset. It does not call `setup_standard_actions()`, so it currently registers
no ordinary action templates and no direct weapon attack templates. It does
register an opportunity attack handler, equips a Flaming Scimitar and Rusty
Dagger, and applies four custom conditions:

- `Dual Wielder`;
- `Elemental Weapon Mastery`;
- `Elemental Affinity`;
- `Circus Performer`.

Those conditions are the interesting part of the preset. They alter AC,
resistances, action economy, skills, saving throws, unarmed damage, and
proficiency.

Example EB-17-012 freezes the current creation-time contract:

```python
performer = create_warrior(
    source_id=uuid4(),
    proficiency_bonus=2,
    name="Book Performer",
    position=(1, 1),
)
main_weapon = performer.equipment.get_item_by_slot(WeaponSlot.MELEE_MAIN)
off_weapon = performer.equipment.get_item_by_slot(WeaponSlot.MELEE_OFF)

assert action_template_names(performer) == set()
assert performer.get_event_handler_by_name("Opportunity Attack Handler") is not None
assert set(performer.active_conditions) == {
    "Circus Performer",
    "Dual Wielder",
    "Elemental Affinity",
    "Elemental Weapon Mastery",
}

assert get_max_hp(performer) == 48
assert get_hp(performer) == 58
assert performer.health.temporary_hit_points.score == 10
assert performer.health.damage_reduction.normalized_score == 1

assert equipped_item_name(performer, WeaponSlot.MELEE_MAIN) == "Flaming Scimitar"
assert equipped_item_name(performer, WeaponSlot.MELEE_OFF) == "Rusty Dagger"
assert isinstance(main_weapon, Weapon)
assert isinstance(off_weapon, Weapon)
assert main_weapon.extra_damage_type == [DamageType.FIRE]
assert off_weapon.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE

assert performer.ac_bonus().normalized_score == 14
assert performer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.RESISTANCE
assert performer.health.get_resistance(DamageType.COLD) == ResistanceStatus.VULNERABILITY
performer.remove_condition("Elemental Affinity")
assert performer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.NONE
assert performer.health.get_resistance(DamageType.COLD) == ResistanceStatus.NONE
assert performer.action_economy.actions.normalized_score == 100
assert performer.action_economy.reactions.normalized_score == 3
assert performer.action_economy.movement.normalized_score == 25
assert performer.skill_set.get_skill("acrobatics").skill_bonus.normalized_score == 7
assert performer.skill_set.get_skill("history").skill_bonus.normalized_score == -2
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_012_circus_warrior_preset_applies_custom_condition_bundle`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Specialized Skeleton Presets

The specialized skeleton factories are tactical presets:

- warrior: more hit dice, longsword, shield, AC 15, Acid Flask inventory item;
- archer: Dexterity 16, shortbow, two daggers, Mark Target action template;
- warlock: Charisma 14 spellcaster, Arcane Staff, crown, spell slots, cantrip
  and leveled spells, Shield reaction, and Scroll of Invisibility.

Example EB-17-002 checks that those presets are not just names. They result in
actual equipment slots, inventory contents, spell slots, and action templates.
The registered action-template surface keeps the base spell names. Executable
available-action discovery expands leveled spells into slot-specific rows such
as `Burning Hands__slot_1` and `Burning Hands__slot_2`, which the legacy
`examples/test_skeleton_units.py` baseline now checks directly.

```python
warrior = create_skeleton_warrior()
archer = create_skeleton_archer()
warlock = create_skeleton_warlock()

assert warrior.ac_bonus().normalized_score == 15
assert "Acid Flask" in inventory_item_names(warrior)

assert equipped_item_name(archer, WeaponSlot.RANGED_MAIN) == "Shortbow"
assert "Mark Target" in action_template_names(archer)

assert warlock.is_spellcaster
assert warlock.action_economy._get_spell_slot_value(1).normalized_score == 2
assert {"Eldritch Blast", "Burning Hands", "Thunderwave", "Necrotic Bless"} <= action_template_names(warlock)
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_002_specialized_skeleton_presets_wire_equipment_items_and_actions`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Mark Target

`MarkTargetAction` is a bonus-action skeleton archer ability. It is implemented
as ordinary action plus condition machinery:

1. Validate that the target is visible and within 60 ft.
2. Apply `Concentrating` to the archer.
3. Apply `Marked` to the target.
4. Link the archer's concentration condition to the target's mark.
5. Apply `Mark Cooldown` to prevent reuse.
6. Spend one bonus action.

`Marked` changes the target, not the archer. It strips current `Invisible` and
`Hidden`, adds a `to_target_static` advantage modifier on the target's AC, and
adds condition immunities that block future `Invisible` and `Hidden` while the
mark remains active.

Example EB-17-003 proves the concentration link and cleanup:

```python
event = MarkTargetAction(
    source_entity_uuid=archer.uuid,
    target_entity_uuid=target.uuid,
).apply()

assert "Marked" in target.active_conditions
assert "Concentrating" in archer.active_conditions
assert "Mark Cooldown" in archer.active_conditions

marked = target.active_conditions["Marked"]
concentrating = archer.active_conditions["Concentrating"]
assert (target.uuid, marked.uuid) in concentrating.linked_conditions

archer.remove_condition("Concentrating")

assert "Marked" not in target.active_conditions
assert not target.check_condition_immunity("Invisible")
assert not target.check_condition_immunity("Hidden")
```

Example EB-17-004 proves the stealth/invisibility relationship:

```python
target.add_condition(Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))

MarkTargetAction(source_entity_uuid=archer.uuid, target_entity_uuid=target.uuid).apply()

assert "Invisible" not in target.active_conditions
assert not target.is_invisible

target.add_condition(InvisibilityEffect(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
target.add_condition(Hidden(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid, stealth_result=20))

assert "Invisible" not in target.active_conditions
assert "Hidden" not in target.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_003_mark_target_creates_concentration_link_and_cleans_target_state`
- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_004_mark_target_strips_and_blocks_hidden_or_invisible_state`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Warlock Spell And Scroll Preset

The skeleton warlock is a preset actor, not a class factory and not an SRD
monster. It still uses the spellcasting engine normally:

- `SpellcastingConfig(spellcasting_ability="charisma")`;
- spell slots `{1: 2, 2: 1}`;
- registered spell templates for Eldritch Blast, Burning Hands, Thunderwave,
  and Necrotic Bless;
- `register_shield_reaction()`;
- a Scroll of Invisibility in inventory.

Example EB-17-005 proves both normal spell execution and item-provided action
discovery:

```python
event = EldritchBlast(
    source_entity_uuid=warlock.uuid,
    target_entity_uuid=target.uuid,
    caster_level=1,
).apply()

assert get_hp(target) < initial_hp
assert warlock.action_economy._get_spell_slot_value(1).normalized_score == 2

scroll = get_inventory_item(warlock, "Scroll of Invisibility")
scroll_actions = scroll.get_use_actions(warlock.uuid)

assert scroll_actions[0].name == "Invisibility"
assert scroll_actions[0].source_item_uuid == scroll.uuid
assert not any(cost.cost_type.startswith("spell_slot") for cost in scroll_actions[0].effective_costs)
```

After Eldritch Blast spends the warlock's normal action, the example resets
turn costs before checking `get_available_actions()`. That is important:
available-action discovery is affordability-aware, so item use actions can
disappear after the relevant action budget is consumed.

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_005_warlock_eldritch_blast_and_scroll_are_action_driven`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Acid Flask Preset Item

The warrior's Acid Flask is a `SpellScroll` carrying an `AcidFlaskSpell`
template. That is an engine shortcut: it is an item, but it reuses the spell
action machinery for range, area targeting, saving throw, and damage.

Example EB-17-006 proves the item/action relationship and the damage effect:

```python
flask = get_inventory_item(warrior, "Acid Flask")
use_actions = flask.get_use_actions(warrior.uuid)

event = AcidFlaskSpell(
    source_entity_uuid=warrior.uuid,
    caster_level=1,
    end_position=target.position,
).apply()

assert flask.is_consumable
assert flask.charges == 1
assert use_actions[0].name == "Acid Flask"
assert use_actions[0].source_item_uuid == flask.uuid
assert get_hp(target) < initial_hp
```

Parity tests:

- `tests/engine_book/test_chapter_17_monsters_presets.py::test_eb_17_006_warrior_acid_flask_is_a_consumable_spell_item`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

## Coverage Added

Chapter 17 adds executable coverage for:

- goblin and skeleton factory state;
- SRD relationship and current HP deviation, goblin darkvision/shortbow/Nimble
  Escape, skeleton darkvision, skeleton shortbow, and skeleton condition
  immunities;
- deterministic monster HP average-mode formula and Constitution contribution;
- generic `create_caster()` spellcaster state, spell slots, spells, Shield
  handler, dagger attack, and potion item-use actions;
- circus warrior custom equipment, condition bundle, action-template absence,
  opportunity handler, HP, resistances, Elemental Affinity cleanup, action
  economy, skills, and saves;
- specialized skeleton equipment slots and action templates;
- skeleton warlock spell slots, spell templates, and inventory scroll actions;
- Mark Target concentration linkage, advantage modifier placement, condition
  immunities, and cleanup;
- Acid Flask as a consumable inventory item backed by spell action logic.

## Documentation Hygiene Notes

Chapter 17 hygiene is being driven from executable behavior rather than
inherited comments. The `Mark Target` surface in
`dnd/monsters/skeleton_abilities.py` has no inline code comments, uses
Google-style docstrings for the marker condition, cooldown condition, and action
lifecycle, and every public condition or action model field uses `Field(...)`
with a description.

The monster factory and circus preset files no longer carry inline code
comments. `dnd/monsters/circus_fighter_conditions.py` now also uses
Google-style docstrings and `Field(...)` descriptions for its custom condition
models. Re-reading that file exposed an `Elemental Affinity` cleanup issue:
resistance modifier UUIDs were returned in the event-handler bookkeeping slot.
EB-17-012 now covers the corrected cleanup path.

## Remaining Work

Later tests should cover:

- broader SRD stat-block mapping or a declarative factory format if desired.
