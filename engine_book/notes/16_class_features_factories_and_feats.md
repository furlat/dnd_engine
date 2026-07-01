# 16. Class Features, Factories, And Feats

## Purpose

This chapter documents how implemented class features are modeled on top of the
lower layers already covered: conditions, action templates, event handlers,
resources, action costs, spell templates, and factories.

The examples are executable in both:

- `tests/engine_book/test_chapter_16_class_features.py`
- `tests/engine_book/test_chapter_16_class_features.py`

The pytest file calls the same example functions, so the book examples and the
`uv run pytest` suite stay in 1:1 parity.

## Source Files Studied

- `dnd/classes/fighter.py`
- `dnd/classes/fighter_factory.py`
- `dnd/classes/barbarian.py`
- `dnd/classes/barbarian_factory.py`
- `dnd/classes/rage.py`
- `dnd/classes/sorcerer.py`
- `dnd/classes/sorcerer_factory.py`
- `dnd/classes/paladin.py`
- `dnd/classes/feats.py`
- `dnd/actions_functional.py`
- `dnd/core/base_actions.py`
- `dnd/blocks/action_economy.py`
- `examples/test_second_wind.py`
- `examples/test_action_surge.py`
- `examples/test_great_weapon_fighting.py`
- `examples/test_protection.py`
- `examples/test_two_weapon_fighting.py`
- `examples/test_improved_critical.py`
- `examples/test_survivor.py`
- `examples/test_barbarian_rage.py`
- `examples/test_barbarian_frenzy.py`
- `examples/test_barbarian_minor_features.py`
- `examples/test_barbarian_fighter_combat.py`
- `examples/test_brutal_critical.py`
- `examples/test_sorcerer_factory.py`
- `examples/test_divine_smite.py`
- `examples/test_lucky_feat.py`
- `tests/engine_book/test_chapter_16_class_features.py`
- `tests/engine_book/test_chapter_16_class_features.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: Fighter features map to
  `interactive_ruleset/Classes/Fighter.md`, including Fighting Style, Second
  Wind, Action Surge, Extra Attack, Indomitable, and Champion features.
- `SRD-aligned`: Barbarian feature names and broad progression map to
  `interactive_ruleset/Classes/Barbarian.md`, including Rage, Reckless Attack,
  Danger Sense, Fast Movement, Brutal Critical, Relentless Rage, Persistent
  Rage, and Berserker features.
- `SRD-aligned`: Sorcerer Font of Magic, Metamagic, Draconic Resilience, and
  Elemental Affinity map to `interactive_ruleset/Classes/Sorcerer.md`.
- `SRD-aligned`: Divine Smite maps to
  `interactive_ruleset/Classes/Paladin.md`.
- `Engine adaptation`: factories use BG3-style level 1 bonuses, equipment
  presets, curated spell lists, and required ASI choices.
- `Engine adaptation`: Berserker Frenzy is BG3-style and does not add
  exhaustion when it ends.
- `Engine adaptation`: Mindless Rage removes existing Charmed/Frightened
  conditions when rage begins instead of preserving hidden suspended state for
  later restoration.
- `Engine adaptation`: metamagic mutates registered spell templates through
  temporary `alt_*` fields, then clears those overrides after the next spell.
- `Engine extension`: `LuckyFeature` is implemented as a simple-AI feat
  condition, but the local `interactive_ruleset/feats_srd5_2.md` does not
  appear to contain a matching Lucky feat entry.

## Feature Pattern

Most implemented class features are `BaseCondition` subclasses. A feature
condition can:

- add a resource to `ActionEconomy`;
- register one or more action templates;
- register event handlers;
- add modifiers to `ModifiableValue` channels;
- clean up those resources, templates, handlers, and modifiers on removal.

Actions granted by features are ordinary `BaseAction` subclasses. They validate
state, apply event-driven effects, and consume resources through the same cost
pipeline as core actions.

## Factory Wiring

The class factories create fully wired entities:

- calculate ability scores and proficiency;
- create the entity with hit dice, saves, equipment, spell slots, and
  appearance;
- call `setup_standard_actions()`;
- equip starter gear;
- apply level-gated feature conditions;
- register spells or reactions where relevant.

Example EB-16-001 proves representative wiring for Fighter, Barbarian, and
Sorcerer:

```python
fighter = create_fighter(FighterConfig(level=5, asi_4=[("strength", 2)]))
barbarian = create_barbarian(
    BarbarianConfig(
        level=5,
        primal_path=PrimalPathChoice.BERSERKER,
        asi_4=[("strength", 2)],
    )
)
sorcerer = create_sorcerer(
    SorcererConfig(
        level=5,
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        spell_names=["Fire Bolt", "Magic Missile", "Hold Person"],
    )
)

assert "Extra Attack" in fighter.active_conditions
assert fighter.action_economy.resources["action_surge"].maximum == 1
assert barbarian.action_economy.resources["rage"].maximum == 3
assert sorcerer.action_economy.resources["sorcery_points"].maximum == 5
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_001_factories_apply_level_gated_features_and_resources`
- `tests/engine_book/test_chapter_16_class_features.py`

## Fighter Resources And Actions

`SecondWindFeature` adds the `second_wind` short-rest resource and registers the
`Second Wind` action. The action costs a bonus action plus one resource use and
heals through `Entity.receive_healing()`.

`ActionSurgeFeature` adds the `action_surge` short-rest resource and registers
the `Action Surge` action. The action applies `ActionSurging`, a one-round
condition that grants +1 action and prevents another Action Surge in the same
turn.

Example EB-16-002:

```python
fighter = create_fighter(FighterConfig(level=2))

assert fighter.get_action_template("Second Wind") is not None
assert fighter.get_action_template("Action Surge") is not None

set_hp(fighter, get_hp(fighter) - 5)
SecondWind(source_entity_uuid=fighter.uuid, fighter_level=2, template=False).apply()
assert fighter.action_economy.resources["second_wind"].current == 0

ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()
assert "ActionSurging" in fighter.active_conditions
assert fighter.action_economy.resources["action_surge"].current == 0

fighter.action_economy.on_short_rest()
assert fighter.action_economy.resources["second_wind"].current == 1
assert fighter.action_economy.resources["action_surge"].current == 1
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_002_fighter_resources_actions_and_short_rest_recharge`
- `tests/engine_book/test_chapter_16_class_features.py`

## Fighter Fighting Style Matrix

The level-1 Fighting Style choice is not a single implementation pattern. Each
style hooks into the lowest engine layer that matches its rule:

| Style | Engine Hook |
| --- | --- |
| Archery | static +2 on `equipment.ranged_attack_bonus` |
| Defense | contextual +1 on `equipment.ac_bonus` while armor is equipped |
| Dueling | contextual +2 on `equipment.melee_damage_bonus` while one-handing a melee weapon with no off-hand weapon |
| Great Weapon Fighting | player-toggleable `DAMAGE_ROLL_RESULT` handler |
| Protection | player-toggleable `ATTACK` `EXECUTION` handler that spends a reaction |
| Two-Weapon Fighting | contextual off-hand ability-bonus modifiers |

Example EB-16-013 proves the modifier placements and cleanup:

```python
archer = create_fighter(
    FighterConfig(
        level=1,
        fighting_style="archery",
        equipment_preset="archery",
    )
)
defender = create_fighter(FighterConfig(level=1, fighting_style="defense"))
duelist = create_fighter(FighterConfig(level=1, fighting_style="dueling"))

assert archer.equipment.ranged_attack_bonus.normalized_score == 2
archer.remove_condition("Fighting Style: Archery")
assert archer.equipment.ranged_attack_bonus.normalized_score == 0

assert defender.ac_bonus().normalized_score == 19
defender.remove_condition("Fighting Style: Defense")
assert defender.ac_bonus().normalized_score == 18

assert duelist.equipment.melee_damage_bonus.normalized_score == 2
duelist.remove_condition("Fighting Style: Dueling")
assert duelist.equipment.melee_damage_bonus.normalized_score == 0
```

Great Weapon Fighting and Protection are handler-backed:

```python
great_weapon = create_fighter(
    FighterConfig(
        level=1,
        fighting_style="great_weapon",
        equipment_preset="greatsword",
    )
)
gwf_handler = great_weapon.get_event_handler_by_name("Great Weapon Fighting")
assert gwf_handler is not None
assert gwf_handler.player_toggleable

great_weapon.remove_condition("Fighting Style: Great Weapon Fighting")
assert great_weapon.get_event_handler_by_name("Great Weapon Fighting") is None
```

The Protection part of the same example performs a live attack against an
adjacent ally. The protector must have a shield, be able to see the attacker,
and have a reaction available:

```python
protection_event = Attack(
    source_entity_uuid=enemy.uuid,
    target_entity_uuid=ally.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    template=False,
).apply()

assert protection_event.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
assert protector.action_economy.reactions.normalized_score == 0
```

Two-Weapon Fighting is stored on the off-hand ability bonus values. With the
dual-wield preset's finesse shortsword, the melee off-hand bonus uses the better
of Strength and Dexterity:

```python
two_weapon = create_fighter(
    FighterConfig(
        level=1,
        fighting_style="two_weapon",
        equipment_preset="dual_wield",
    )
)
expected_off_hand_bonus = max(
    two_weapon.ability_scores.strength.modifier,
    two_weapon.ability_scores.dexterity.modifier,
)

assert two_weapon.equipment.off_hand_melee_ability_bonus.normalized_score == expected_off_hand_bonus

two_weapon.remove_condition("Fighting Style: Two-Weapon Fighting")
assert two_weapon.equipment.off_hand_melee_ability_bonus.normalized_score == 0
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_013_fighting_styles_place_expected_modifiers_and_handlers`
- `tests/engine_book/test_chapter_16_class_features.py`

## Fighter Additional Fighting Style

The SRD Champion gains `Additional Fighting Style` at level 10. The engine
models this as `FighterConfig.second_fighting_style`, gated by validation and
applied only when the fighter level is at least 10. The config also enforces the
SRD rule that a fighter cannot take the same Fighting Style option twice.

Example EB-16-007 uses a level-10 Champion with Defense plus Protection:

```python
fighter = create_fighter(
    FighterConfig(
        level=10,
        fighting_style="defense",
        second_fighting_style="protection",
        asi_4=[("strength", 2)],
        asi_6=[("constitution", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
    )
)
extra_attack = fighter.active_conditions["Extra Attack"]

assert "Fighting Style: Defense" in fighter.active_conditions
assert "Fighting Style: Protection" in fighter.active_conditions
assert fighter.get_event_handler_by_name("Protection") is not None
assert "Indomitable" in fighter.active_conditions
assert "Improved Critical" in fighter.active_conditions
assert isinstance(extra_attack, ExtraAttackFeature)
assert extra_attack.extra_attacks == 1

assert fighter.proficiency_bonus.normalized_score == 4
assert fighter.ability_scores.strength.ability_score.score == 20
assert fighter.ability_scores.constitution.ability_score.score == 17
assert fighter.ac_bonus().normalized_score == 19
assert fighter.action_economy.resources["indomitable"].maximum == 1
assert fighter.action_economy.resources["extra_attacks"].maximum == 1
assert fighter.get_action_template("Extra Attack_MELEE_MAIN") is not None
```

The example also checks that invalid second-style choices raise Pydantic
validation errors:

```python
duplicate_style_error = None
try:
    FighterConfig(
        level=10,
        fighting_style="defense",
        second_fighting_style="defense",
        asi_4=[("strength", 2)],
        asi_6=[("constitution", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
    )
except ValidationError as exc:
    duplicate_style_error = exc

assert duplicate_style_error is not None
assert "Cannot take same fighting style twice" in str(duplicate_style_error)
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_007_fighter_level_ten_champion_adds_distinct_second_fighting_style`
- `tests/engine_book/test_chapter_16_class_features.py`

## Extra Attack And Action Surge

The SRD says Extra Attack lets a fighter attack twice when taking the Attack
action, while Action Surge grants one additional action on the fighter's turn.
The engine implements the interaction with a fighter-specific
`Extra Attack Resource` handler:

- an action-cost `Attack` at `EXECUTION` phase grants `extra_attacks`;
- the first such attack applies the internal `ExtraAttacksGranted` marker;
- later action-cost attacks in the same turn add another batch of extra attacks;
- `ExtraAttack` spends `extra_attacks` without spending another normal action.

Example EB-16-008 proves the level-5 action sequence:

```python
fighter = create_fighter(
    FighterConfig(level=5, asi_4=[("strength", 2)])
)
target = create_book_target(position=(2, 1))
force_attack_miss(fighter)
fighter.action_economy.reset_all_costs()
fighter.action_economy.on_turn_start()

assert fighter.action_economy.actions.normalized_score == 1
assert fighter.action_economy.resources["extra_attacks"].current == 1
assert "ExtraAttacksGranted" not in fighter.active_conditions

Attack(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    template=False,
).apply()

assert fighter.action_economy.actions.normalized_score == 0
assert fighter.action_economy.resources["extra_attacks"].current == 1
assert "ExtraAttacksGranted" in fighter.active_conditions

ExtraAttack(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    template=False,
).apply()

assert fighter.action_economy.resources["extra_attacks"].current == 0

ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()

assert fighter.action_economy.actions.normalized_score == 1

Attack(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    template=False,
).apply()

assert fighter.action_economy.resources["extra_attacks"].current == 1

ExtraAttack(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    template=False,
).apply()

assert fighter.action_economy.resources["extra_attacks"].current == 0
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_008_extra_attack_recharges_for_action_surge_attack_action`
- `tests/engine_book/test_chapter_16_class_features.py`

The SRD also says the number of attacks increases to three at fighter level 11
and four at fighter level 20. The engine stores the extra count on
`ExtraAttackFeature.extra_attacks` and mirrors it in the `extra_attacks`
resource maximum. After an action-cost `Attack`, that many `ExtraAttack`
actions can be spent.

Example EB-16-009 proves the level 11 and level 20 scaling:

```python
level_eleven = create_fighter(
    FighterConfig(
        level=11,
        asi_4=[("strength", 2)],
        asi_6=[("constitution", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
    )
)
level_twenty = create_fighter(
    FighterConfig(
        level=20,
        asi_4=[("strength", 2)],
        asi_6=[("constitution", 2)],
        asi_8=[("dexterity", 2)],
        asi_12=[("wisdom", 2)],
        asi_14=[("constitution", 2)],
        asi_16=[("strength", 1), ("wisdom", 1)],
        asi_19=[("dexterity", 1), ("constitution", 1)],
    )
)

prove_extra_attack_count(level_eleven, target_eleven, expected_extra_attacks=2)
prove_extra_attack_count(level_twenty, target_twenty, expected_extra_attacks=3)
```

`prove_extra_attack_count()` forces misses so the durable target survives, sets
the `extra_attacks` resource to 0, applies one action-cost attack, then spends
exactly the expected number of `ExtraAttack` actions and verifies the next one
does not succeed.

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_009_extra_attack_counts_scale_at_fighter_levels_eleven_and_twenty`
- `tests/engine_book/test_chapter_16_class_features.py`

Example EB-16-014 extends the same proof through Action Surge at the higher
Extra Attack breakpoints. It spends a full attack batch, uses Action Surge, then
spends a second full batch from the surged Attack action:

```python
for fighter, target, expected_extra_attacks, expected_action_surge_uses in [
    (level_eleven, target_eleven, 2, 1),
    (level_twenty, target_twenty, 3, 2),
]:
    force_attack_miss(fighter)
    fighter.action_economy.reset_all_costs()
    fighter.action_economy.on_turn_start()

    resource = fighter.action_economy.resources["extra_attacks"]
    action_surge_resource = fighter.action_economy.resources["action_surge"]
    feature = fighter.active_conditions["Extra Attack"]

    assert isinstance(feature, ExtraAttackFeature)
    assert feature.extra_attacks == expected_extra_attacks
    assert resource.maximum == expected_extra_attacks
    assert resource.current == expected_extra_attacks
    assert action_surge_resource.current == expected_action_surge_uses
    assert fighter.action_economy.actions.normalized_score == 1

    resource.current = 0
    spend_attack_batch(fighter, target, expected_extra_attacks)

    ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()

    assert fighter.action_economy.actions.normalized_score == 1
    assert action_surge_resource.current == expected_action_surge_uses - 1

    spend_attack_batch(fighter, target, expected_extra_attacks)

    assert fighter.action_economy.actions.normalized_score == 0
    assert resource.current == 0
```

The helper `spend_attack_batch()` applies one action-cost `Attack`, verifies the
resource fills to the level's full extra-attack count, spends that many
`ExtraAttack` actions, then verifies the next extra attack cannot proceed. This
keeps the level 11 and level 20 Action Surge behavior tied to the same resource
contract as the lower-level example.

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_014_higher_level_extra_attack_refreshes_after_action_surge`
- `tests/engine_book/test_chapter_16_class_features.py`

## Fighter Indomitable

The SRD Indomitable feature lets a fighter reroll a failed saving throw and
requires using the new roll. The engine models this as an `Indomitable`
condition that adds a long-rest `indomitable` resource and registers a
player-toggleable `SAVING_THROW` `EFFECT` handler. The handler only fires for
the fighter's own failed saving throws.

Example EB-16-010 proves the live behavior with deterministic d20 rolls:

```python
fighter = create_fighter(
    FighterConfig(
        level=9,
        asi_4=[("strength", 2)],
        asi_6=[("constitution", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
    )
)
caster = create_book_target(position=(2, 1))

handler = fighter.get_event_handler_by_name("Indomitable")
resource = fighter.action_economy.resources["indomitable"]

assert "Indomitable" in fighter.active_conditions
assert handler is not None
assert handler.player_toggleable
assert resource.current == 1
assert resource.maximum == 1
```

A successful save does not spend the resource:

```python
easy_request = caster.create_saving_throw_request(
    target_entity_uuid=fighter.uuid,
    ability_name="wisdom",
    dc=1,
)
with patch("dnd.core.dice.random.randint", return_value=10):
    easy_outcome, easy_roll, easy_success = fighter.saving_throw(easy_request)

assert easy_success
assert easy_roll.total == 11
assert resource.current == 1
```

A failed save triggers the Indomitable reroll and spends the resource:

```python
hard_roll_values = iter([2])

def hard_save_randint(minimum: int, maximum: int) -> int:
    return next(hard_roll_values, 18)

hard_request = caster.create_saving_throw_request(
    target_entity_uuid=fighter.uuid,
    ability_name="wisdom",
    dc=15,
)
with patch("dnd.core.dice.random.randint", side_effect=hard_save_randint):
    hard_outcome, hard_roll, hard_success = fighter.saving_throw(hard_request)

assert hard_success
assert hard_roll.results == [18]
assert hard_roll.total == 19
assert resource.current == 0

fighter.action_economy.on_long_rest()
assert resource.current == 1
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_010_indomitable_rerolls_failed_saves_and_recharges_on_long_rest`
- `tests/engine_book/test_chapter_16_class_features.py`

## Champion Criticals

The SRD Champion improves weapon critical-hit ranges. The engine models this as
numeric modifiers on `equipment.crit_threshold`; `Entity.get_crit_threshold()`
converts the accumulated modifier back into the minimum natural d20 face.

- levels 3 through 14 apply `Improved Critical`, producing a threshold of 19;
- level 15 and later apply `Superior Critical`, producing a threshold of 18;
- the factory does not stack both conditions at level 15.

Example EB-16-011 proves the thresholds and the attack-outcome consequence:

```python
level_fourteen = create_fighter(
    FighterConfig(
        level=14,
        asi_4=[("strength", 2)],
        asi_6=[("constitution", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
        asi_12=[("wisdom", 2)],
        asi_14=[("dexterity", 2)],
    )
)
level_fifteen = create_fighter(
    FighterConfig(
        level=15,
        asi_4=[("strength", 2)],
        asi_6=[("constitution", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
        asi_12=[("wisdom", 2)],
        asi_14=[("dexterity", 2)],
    )
)

assert "Improved Critical" in level_fourteen.active_conditions
assert "Superior Critical" not in level_fourteen.active_conditions
assert level_fourteen.get_crit_threshold(WeaponSlot.MELEE_MAIN) == 19
assert level_fourteen.get_crit_threshold(WeaponSlot.RANGED_MAIN) == 19

assert "Improved Critical" not in level_fifteen.active_conditions
assert "Superior Critical" in level_fifteen.active_conditions
assert level_fifteen.get_crit_threshold(WeaponSlot.MELEE_MAIN) == 18
assert level_fifteen.get_crit_threshold(WeaponSlot.RANGED_MAIN) == 18
```

The same example creates deterministic attack rolls and sends them through
`determine_attack_outcome()`:

```python
assert determine_attack_outcome(
    create_attack_roll(level_fourteen, 18),
    10,
    crit_threshold=level_fourteen.get_crit_threshold(),
) == AttackOutcome.HIT
assert determine_attack_outcome(
    create_attack_roll(level_fourteen, 19),
    10,
    crit_threshold=level_fourteen.get_crit_threshold(),
) == AttackOutcome.CRIT

assert determine_attack_outcome(
    create_attack_roll(level_fifteen, 17),
    10,
    crit_threshold=level_fifteen.get_crit_threshold(),
) == AttackOutcome.HIT
assert determine_attack_outcome(
    create_attack_roll(level_fifteen, 18),
    10,
    crit_threshold=level_fifteen.get_crit_threshold(),
) == AttackOutcome.CRIT
```

Removing `Superior Critical` removes its modifier and restores both melee and
ranged thresholds to 20.

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_011_champion_critical_thresholds_upgrade_without_stacking`
- `tests/engine_book/test_chapter_16_class_features.py`

## Champion Survivor

The SRD Survivor feature heals the Champion at the start of each of their turns
when current hit points are no more than half maximum and greater than 0. The
engine implements this as a `Survivor` condition with a `TURN_START`
`EXECUTION` handler. That timing means healing happens before start-of-turn
condition advancement and action-economy reset.

Example EB-16-012 proves the gates and cleanup:

```python
fighter = create_fighter(
    FighterConfig(
        level=18,
        asi_4=[("strength", 2)],
        asi_6=[("constitution", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
        asi_12=[("wisdom", 2)],
        asi_14=[("constitution", 2)],
        asi_16=[("dexterity", 2)],
    )
)
survivor_handler = fighter.get_event_handler_by_name("Survivor")
max_hp = get_hp(fighter)
con_mod = fighter.ability_scores.constitution.modifier
expected_healing = 5 + con_mod

assert "Survivor" in fighter.active_conditions
assert survivor_handler is not None
assert "Superior Critical" in fighter.active_conditions
```

At half HP, the turn-start event is modified by Survivor and the fighter heals:

```python
set_hp(fighter, max_hp // 2)
wounded_hp = get_hp(fighter)
healing_event = fighter.on_turn_start()

assert get_hp(fighter) == wounded_hp + expected_healing
assert "Survivor heals" in (healing_event.status_message or "")
```

The same example verifies that Survivor does not heal above half HP, does not
heal at 0 HP, and stops healing after the condition removes its owned handler:

```python
set_hp(fighter, max_hp // 2 + 1)
above_half_hp = get_hp(fighter)
fighter.on_turn_start()
assert get_hp(fighter) == above_half_hp

set_hp(fighter, 0)
fighter.on_turn_start()
assert get_hp(fighter) == 0

fighter.remove_condition("Survivor")
assert fighter.get_event_handler_by_name("Survivor") is None
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_012_survivor_heals_only_at_valid_turn_start_thresholds`
- `tests/engine_book/test_chapter_16_class_features.py`

## Barbarian Rage And Frenzy

`RageFeature` adds a long-rest `rage` resource and registers `Rage` and
`End Rage`. Active `Raging` grants Strength skill/save advantage, contextual
melee damage, physical resistance, and maintenance handlers.

`FrenzyFeature` adds the `Frenzy` action. `Frenzy` applies `Raging` first, then
applies `Frenzied` as a sub-condition of `Raging`. This matters because removing
`Raging` cascades into removing `Frenzied`, and `Frenzied._remove()` unregisters
`Frenzied Strike`.

Example EB-16-003:

```python
barbarian = create_barbarian(
    BarbarianConfig(level=3, primal_path=PrimalPathChoice.BERSERKER)
)

Frenzy(source_entity_uuid=barbarian.uuid, rage_damage=2, template=False).apply()

assert "Raging" in barbarian.active_conditions
assert "Frenzied" in barbarian.active_conditions
assert barbarian.get_action_template("Frenzied Strike") is not None

barbarian.remove_condition("Raging")

assert "Frenzied" not in barbarian.active_conditions
assert barbarian.get_action_template("Frenzied Strike") is None
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_003_barbarian_rage_and_frenzy_cleanup_cascade`
- `tests/engine_book/test_chapter_16_class_features.py`

## Barbarian Scaling Matrix

The Barbarian factory computes several SRD-like scaling values before applying
feature conditions:

- `get_rage_uses(level)`: 2, 3, 4, 5, 6, then engine-unlimited `999` at level
  20;
- `get_rage_damage(level)`: +2 through level 8, +3 through level 15, +4 from
  level 16 onward;
- `get_brutal_critical_dice(level)`: 1 at level 9, 2 at level 13, 3 at level
  17;
- level gates for Fast Movement, Feral Instinct, Relentless Rage, Persistent
  Rage, Indomitable Might, and Primal Champion.

Example EB-16-015 creates Barbarians at levels 1, 9, 17, and 20 and verifies
the applied feature state:

```python
level_one = create_barbarian(BarbarianConfig(level=1))
level_nine = create_barbarian(
    BarbarianConfig(
        level=9,
        primal_path=PrimalPathChoice.BERSERKER,
        asi_4=[("strength", 2)],
        asi_8=[("constitution", 2)],
    )
)
level_seventeen = create_barbarian(
    BarbarianConfig(
        level=17,
        primal_path=PrimalPathChoice.BERSERKER,
        asi_4=[("strength", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
        asi_12=[("constitution", 2)],
        asi_16=[("dexterity", 2)],
    )
)
level_twenty = create_barbarian(
    BarbarianConfig(
        level=20,
        primal_path=PrimalPathChoice.BERSERKER,
        asi_4=[("strength", 2)],
        asi_8=[("strength", 1), ("constitution", 1)],
        asi_12=[("constitution", 2)],
        asi_16=[("constitution", 2)],
        asi_19=[("dexterity", 2)],
    )
)
```

The rage feature stores both the resource maximum and the damage value used by
`Rage` and `Frenzy`:

```python
level_one_rage = level_one.active_conditions["Rage Feature"]
level_nine_rage = level_nine.active_conditions["Rage Feature"]
level_seventeen_rage = level_seventeen.active_conditions["Rage Feature"]
level_twenty_rage = level_twenty.active_conditions["Rage Feature"]

assert isinstance(level_one_rage, RageFeature)
assert level_one.action_economy.resources["rage"].maximum == 2
assert level_one_rage.rage_damage == 2

assert level_nine.action_economy.resources["rage"].maximum == 4
assert level_nine_rage.rage_damage == 3

assert level_seventeen.action_economy.resources["rage"].maximum == 6
assert level_seventeen_rage.rage_damage == 4

assert level_twenty.action_economy.resources["rage"].maximum == 999
assert level_twenty_rage.rage_damage == 4
```

The same example verifies movement, initiative, Brutal Critical, and high-level
handler gates:

```python
assert "Fast Movement" in level_nine.active_conditions
assert level_nine.action_economy.movement.normalized_score == 40
assert "Feral Instinct" in level_nine.active_conditions
assert level_nine.initiative.advantage == AdvantageStatus.ADVANTAGE
assert level_nine.get_crit_extra_dice(WeaponSlot.MELEE_MAIN) == 1
assert level_nine.get_crit_extra_dice(WeaponSlot.RANGED_MAIN) == 0

assert level_seventeen.get_crit_extra_dice(WeaponSlot.MELEE_MAIN) == 3
assert "Relentless Rage" in level_seventeen.active_conditions
assert level_seventeen.action_economy.resources["relentless_rage"].maximum == 5
assert level_seventeen.get_event_handler_by_name("Relentless Rage") is not None
assert "PersistentRage" in level_seventeen.active_conditions
assert "Indomitable Might" not in level_seventeen.active_conditions
```

At level 20, `PrimalChampion` adds +4 Strength and +4 Constitution as ordinary
condition-owned modifiers. Removing the condition removes those modifiers:

```python
assert "Indomitable Might" in level_twenty.active_conditions
assert level_twenty.get_event_handler_by_name("Indomitable Might") is not None
assert "Primal Champion" in level_twenty.active_conditions
assert level_twenty.ability_scores.strength.ability_score.score == 24
assert level_twenty.ability_scores.constitution.ability_score.score == 24

level_twenty.remove_condition("Primal Champion")

assert level_twenty.ability_scores.strength.ability_score.score == 20
assert level_twenty.ability_scores.constitution.ability_score.score == 20
```

The deeper Primal Champion example follows the same modifiers into every
derived combat surface that consumes Strength or Constitution. The raw ability
scores rise by 4, but the SRD ability modifier changes by 2 because the engine
now aggregates raw ability-score modifiers before applying `(score - 10) // 2`.
That +2 modifier flows into melee attack, melee damage, Athletics, Strength and
Constitution saves, Barbarian unarmored AC, and level-scaled HP:

```python
boosted = snapshot()

assert boosted["strength_score"] == 24
assert boosted["constitution_score"] == 24
assert boosted["strength_modifier"] == 7
assert boosted["constitution_modifier"] == 7

barbarian.remove_condition("Primal Champion")
unboosted = snapshot()

assert unboosted["strength_score"] == 20
assert unboosted["constitution_score"] == 20
assert "Primal Champion" not in barbarian.active_conditions

ability_delta = 2
hit_point_delta = ability_delta * barbarian.health.total_hit_dices_number

for key in [
    "strength_modifier",
    "constitution_modifier",
    "melee_attack",
    "melee_damage",
    "athletics",
    "strength_save",
    "constitution_save",
    "unarmored_ac",
]:
    assert boosted[key] == unboosted[key] + ability_delta

assert boosted["hp"] == unboosted["hp"] + hit_point_delta
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_015_barbarian_factory_scales_rage_brutal_critical_and_capstone`
- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_023_barbarian_primal_champion_updates_derived_combat_surfaces`
- `tests/engine_book/test_chapter_16_class_features.py`

## Barbarian Tactical Features

Early Barbarian features mix action-template registration, live modifier
channels, and contextual condition immunity.

`RecklessAttackFeature` grants a self-target `Reckless Attack` action template.
The action costs nothing. When executed, it applies `Reckless Attacking` for one
round. That condition:

- adds advantage to the Barbarian's melee attack bonus;
- adds an outgoing `to_target_static` advantage on AC, so attackers pulling
  target modifiers gain advantage against the Barbarian;
- cancels repeated use while the marker condition is already active.

This is SRD-related but not a literal SRD timing model: the engine exposes
Reckless Attack as an explicit free action instead of a choice made inside the
first Strength melee attack.

Example EB-16-019:

```python
available = get_available_actions(barbarian)
reckless_info = next(
    action for action in available.self_actions
    if action.template_name == "Reckless Attack"
)

reckless_event = execute_action(
    barbarian,
    "Reckless Attack",
    reckless_info.valid_targets[0],
)

assert not reckless_event.canceled
assert "Reckless Attacking" in barbarian.active_conditions
assert barbarian.equipment.melee_attack_bonus.advantage == AdvantageStatus.ADVANTAGE
assert barbarian.equipment.ac_bonus.to_target_static.advantage_sum > 0
```

`DangerSense` adds a contextual advantage modifier to the Dexterity saving-throw
bonus. The modifier only contributes when the effect source is visible and the
Barbarian is not Blinded, Deafened, or Incapacitated.

```python
dex_save_bonus = barbarian.saving_throws.get_saving_throw("dexterity").bonus
dex_save_bonus.set_target_entity(visible_source.uuid)

assert dex_save_bonus.advantage == AdvantageStatus.ADVANTAGE

barbarian.add_condition(
    Blinded(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
)

assert dex_save_bonus.advantage == AdvantageStatus.NONE
```

`MindlessRage` installs contextual condition immunities for Charmed and
Frightened. The immunity check returns true only while the Barbarian has
`Raging` or `Frenzied`. Entering rage also removes any currently active Charmed
or Frightened condition.

```python
barbarian.add_condition(
    Charmed(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
)
barbarian.add_condition(
    Raging(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_damage=2,
    )
)

assert "Raging" in barbarian.active_conditions
assert "Charmed" not in barbarian.active_conditions

blocked_charm_event = barbarian.add_condition(
    Charmed(source_entity_uuid=visible_source.uuid, target_entity_uuid=barbarian.uuid)
)

assert blocked_charm_event.canceled
```

The same example proves that Poisoned is not blocked by Mindless Rage and that
Charmed can apply again after `Raging` is removed, because the immunity is
contextual rather than static.

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_019_barbarian_reckless_danger_sense_and_mindless_rage_edges`
- `tests/engine_book/test_chapter_16_class_features.py`

## Barbarian Rage Event Features

Relentless Rage and Persistent Rage both depend on event handlers rather than
ordinary static modifiers.

`RelentlessRage` adds a `relentless_rage` short-rest resource with five uses and
registers a `TAKE_DAMAGE` `EFFECT` handler. The handler only acts when the
Barbarian is raging or frenzied and incoming damage would reduce current HP to
0 or lower. It rolls a Constitution save, starting at DC 10 and increasing by 5
for each successful use already consumed.

Example EB-16-020 first forces a successful save:

```python
set_hp(relentless, 5)

with patch("dnd.core.dice.random.randint", return_value=20):
    survival_damage = deal_damage_to(
        relentless,
        20,
        DamageType.FIRE,
        source_uuid=damage_source.uuid,
    )

assert survival_damage == 4
assert get_hp(relentless) == 1
assert relentless_resource.current == 4
assert "Dead" not in relentless.active_conditions
```

The same example then forces a failed save after the first use has raised the
DC. Failure does not spend another resource use, and ordinary lethal damage can
leave the engine HP total below zero while applying `Dead`.

```python
set_hp(relentless, 5)

with patch("dnd.core.dice.random.randint", return_value=1):
    failed_save_damage = deal_damage_to(
        relentless,
        20,
        DamageType.FIRE,
        source_uuid=damage_source.uuid,
    )

assert failed_save_damage == 20
assert get_hp(relentless) <= 0
assert relentless_resource.current == 4
assert "Dead" in relentless.active_conditions
```

`PersistentRage` is a pure marker condition. The `Raging` condition owns the
turn-start maintenance handler; that handler removes rage on idle turn starts
unless `PersistentRage` is active.

```python
persistent.on_turn_start()

assert "Raging" in persistent.active_conditions

persistent.remove_condition("PersistentRage")
persistent.on_turn_start()

assert "PersistentRage" not in persistent.active_conditions
assert "Raging" not in persistent.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_020_barbarian_relentless_and_persistent_rage_events`
- `tests/engine_book/test_chapter_16_class_features.py`

## Barbarian Indomitable Might

`IndomitableMight` registers a `SKILL_CHECK` `EFFECT` handler. The handler only
acts on the Barbarian's own Athletics checks. If the final check total is below
the Barbarian's Strength score, it replaces the event dice total with that
score.

The high-level `Entity.skill_check()` API now treats the post-handler event as
authoritative: it recomputes the outcome from the final dice total before
completion and returns the same final roll/result that the completed event
stores.

Example EB-16-021:

```python
athletics_request = SkillCheckEvent(
    source_entity_uuid=barbarian.uuid,
    target_entity_uuid=barbarian.uuid,
    skill_name="athletics",
    dc=18,
)

with patch("dnd.core.dice.random.randint", return_value=1):
    athletics_outcome, athletics_roll, athletics_success = barbarian.skill_check(
        athletics_request
    )

athletics_completion = get_latest_skill_check_event(barbarian.uuid, "athletics")

assert athletics_outcome == AttackOutcome.HIT
assert athletics_roll.total == strength_score
assert athletics_success is True
assert athletics_completion.dice_roll.total == strength_score
assert athletics_completion.result is True
```

The same example proves that non-Athletics skill checks are not raised to the
Strength score, and that removing `Indomitable Might` removes the handler.

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_021_barbarian_indomitable_might_recomputes_skill_check_result`
- `tests/engine_book/test_chapter_16_class_features.py`

## Barbarian Retaliation

`Retaliation` registers a player-toggleable `TAKE_DAMAGE` `EFFECT` handler. The
handler checks that the Barbarian is the damaged target, the damage source is an
entity within 5 feet, the Barbarian has a reaction available, and the Barbarian
has a main-hand melee weapon.

When all gates pass, the handler makes a melee `Attack` against the damage
source and then spends the Barbarian's reaction. The retaliation attack itself
uses `costs=[]`; the feature owns the reaction cost, so it does not spend the
normal action.

Example EB-16-022:

```python
attacker_hp_before = get_hp(attacker)
actions_before = barbarian.action_economy.actions.normalized_score
reactions_before = barbarian.action_economy.reactions.normalized_score

force_attack_hit(barbarian)
incoming_damage = deal_damage_to(
    barbarian,
    1,
    DamageType.FIRE,
    source_uuid=attacker.uuid,
)

assert incoming_damage == 1
assert get_hp(attacker) < attacker_hp_before
assert barbarian.action_economy.actions.normalized_score == actions_before
assert barbarian.action_economy.reactions.normalized_score == reactions_before - 1
```

The same executable example proves that a second qualifying damage event does
not retaliate after the reaction is spent, distant damage sources do not trigger
the handler, and an unarmed Barbarian does not retaliate. Removing `Retaliation`
removes the handler.

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_022_barbarian_retaliation_reaction_attack_gates`
- `tests/engine_book/test_chapter_16_class_features.py`

## Sorcerer Metamagic

Sorcerer metamagic uses temporary action-template overrides.

`QuickenedSpell` spends sorcery points and applies `MetamagicActive` with
`metamagic_type="quickened"`. That condition sets `alt_cost_type` to
`"bonus_actions"` on action-cost spell templates. It also registers a
`CAST_SPELL` handler that removes the condition after the next spell, which in
turn clears all mutated template fields.

Example EB-16-004:

```python
fire_bolt_template = sorcerer.get_action_template("Fire Bolt")

QuickenedSpell(source_entity_uuid=sorcerer.uuid, template=False).apply()

assert "MetamagicActive" in sorcerer.active_conditions
assert fire_bolt_template.alt_cost_type == "bonus_actions"
assert fire_bolt_template.effective_costs[0].cost_type == "bonus_actions"

spell_instance = fire_bolt_template.instantiate(target_entity_uuid=target.uuid)
spell_instance.apply()

assert "MetamagicActive" not in sorcerer.active_conditions
assert fire_bolt_template.alt_cost_type is None
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_004_sorcerer_quickened_spell_overrides_and_cleanup`
- `tests/engine_book/test_chapter_16_class_features.py`

## Sorcerer Font Of Magic, Twinned, And Distant

`SorceryPointsFeature` adds the `sorcery_points` long-rest resource, registers
chosen metamagic actions, and registers Font of Magic conversion actions for
each spell-slot level the entity actually has. The conversion action names use
the engine's registered action names:

- `Slot→SP L{slot_level}` spends one bonus action plus one slot and restores
  sorcery points equal to the slot level, capped at maximum;
- `{cost}SP→Slot L{slot_level}` spends one bonus action plus sorcery points and
  removes one matching spell-slot cost modifier.

Example EB-16-016 starts with a level-10 Sorcerer, which has 10 sorcery points
and slot levels 1 through 5:

```python
font_sorcerer = create_sorcerer(
    SorcererConfig(
        level=10,
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("charisma", 1), ("constitution", 1)],
        spell_names=[
            "Fire Bolt",
            "Ray of Frost",
            "Shocking Grasp",
            "Magic Missile",
            "Hold Person",
            "Fireball",
        ],
    )
)

assert font_sorcerer.action_economy.resources["sorcery_points"].current == 10
assert font_sorcerer.action_economy.resources["sorcery_points"].maximum == 10
assert font_sorcerer.get_action_template("Twinned Spell") is not None
assert font_sorcerer.get_action_template("Distant Spell") is not None

for slot_level, sp_cost in [(1, 2), (2, 3), (3, 5), (4, 6), (5, 7)]:
    assert font_sorcerer.get_action_template(f"Slot→SP L{slot_level}") is not None
    assert font_sorcerer.get_action_template(f"{sp_cost}SP→Slot L{slot_level}") is not None
assert font_sorcerer.get_action_template("Slot→SP L6") is None
```

The example then proves both Font of Magic directions:

```python
font_sorcerer.action_economy.consume_resource("sorcery_points", 8)
slot_to_sp = font_sorcerer.get_action_template("Slot→SP L3")
slot_to_sp.instantiate().apply()

assert font_sorcerer.action_economy.get_resource_current("sorcery_points") == 5
assert font_sorcerer.action_economy.spell_slot_3.normalized_score == 2
assert font_sorcerer.action_economy.bonus_actions.normalized_score == 0

font_sorcerer.action_economy.reset_all_costs()
font_sorcerer.action_economy.consume("spell_slot_2", 1, "book_slot_use")
sp_to_slot = font_sorcerer.get_action_template("3SP→Slot L2")
sp_to_slot.instantiate().apply()

assert font_sorcerer.action_economy.get_resource_current("sorcery_points") == 2
assert font_sorcerer.action_economy.spell_slot_2.normalized_score == 3
```

Twinned Spell mutates only single-entity `SpellAction` templates. Cantrips gain
two targets with no extra casting cost; leveled single-target spells add extra
sorcery-point costs so total cost equals the spell level; multi-target and area
spells are not changed.

```python
twinned_action = twinned_sorcerer.get_action_template("Twinned Spell")
twinned_action.instantiate().apply()

fire_bolt = twinned_sorcerer.get_action_template("Fire Bolt")
hold_person = twinned_sorcerer.get_action_template("Hold Person")
magic_missile = twinned_sorcerer.get_action_template("Magic Missile")
fireball = twinned_sorcerer.get_action_template("Fireball")

assert fire_bolt.alt_target_type == TargetType.MULTI_ENTITY
assert fire_bolt.alt_target_count == 2
assert fire_bolt.alt_extra_costs == []
assert hold_person.alt_target_type == TargetType.MULTI_ENTITY
assert hold_person.alt_target_count == 2
assert hold_person.alt_extra_costs[0].resource_cost == 1
assert magic_missile.alt_target_type is None
assert fireball.alt_target_type is None
assert twinned_sorcerer.action_economy.get_resource_current("sorcery_points") == 9
```

Removing `Sorcery Points Feature` unregisters its actions and removes
`MetamagicActive`, which clears the mutated spell templates:

```python
twinned_sorcerer.remove_condition("Sorcery Points Feature")

assert "MetamagicActive" not in twinned_sorcerer.active_conditions
assert twinned_sorcerer.get_action_template("Twinned Spell") is None
assert twinned_sorcerer.get_action_template("Slot→SP L1") is None
assert fire_bolt.alt_target_type is None
assert hold_person.alt_target_type is None
```

Distant Spell mutates `SpellAction.alt_range`:

```python
distant_action = distant_sorcerer.get_action_template("Distant Spell")
distant_action.instantiate().apply()

distant_fire_bolt = distant_sorcerer.get_action_template("Fire Bolt")
ray_of_frost = distant_sorcerer.get_action_template("Ray of Frost")
shocking_grasp = distant_sorcerer.get_action_template("Shocking Grasp")
magic_missile = distant_sorcerer.get_action_template("Magic Missile")

assert distant_fire_bolt.spell_range.normal == 120
assert distant_fire_bolt.alt_range == 240
assert distant_fire_bolt.effective_range == 240
assert ray_of_frost.spell_range.normal == 60
assert ray_of_frost.alt_range == 120
assert shocking_grasp.alt_range == 30
assert magic_missile.alt_range == 240
assert distant_sorcerer.action_economy.get_resource_current("sorcery_points") == 9
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_016_sorcerer_font_of_magic_twinned_and_distant_overrides`
- `tests/engine_book/test_chapter_16_class_features.py`

## Sorcerer Draconic Origin

The Draconic Bloodline factory path applies two different mechanisms:

- `EquipmentConfig(unarmored_ac_type=UnarmoredAc.DRACONIC_SORCERER)` makes
  unarmored AC use 13 + Dexterity modifier;
- `DraconicResilience` adds a condition-owned max-HP bonus equal to Sorcerer
  level;
- `ElementalAffinity` at level 6 adds a resistance modifier for the configured
  draconic damage type.

Example EB-16-017 proves the level-1 HP and AC surface:

```python
level_one = create_sorcerer(SorcererConfig(level=1))

assert "Draconic Resilience" in level_one.active_conditions
assert level_one.health.max_hit_points_bonus.normalized_score == 1
assert get_hp(level_one) == 9
assert level_one.ac_bonus().normalized_score == 15
```

Equipping real armor switches AC to the armor formula rather than the Draconic
unarmored formula:

```python
level_one.equipment.equip(create_leather_armor(level_one.uuid), BodyPart.BODY)

assert level_one.ac_bonus().normalized_score == 13
```

Removing the condition removes the HP modifier:

```python
level_one.remove_condition("Draconic Resilience")

assert "Draconic Resilience" not in level_one.active_conditions
assert level_one.health.max_hit_points_bonus.normalized_score == 0
assert get_hp(level_one) == 8
```

At level 6, `ElementalAffinity` creates actual damage resistance. The example
checks both the resistance enum and a real damage application:

```python
fire_sorcerer = create_sorcerer(
    SorcererConfig(
        level=6,
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        draconic_damage_type="Fire",
    )
)

assert "Elemental Affinity" in fire_sorcerer.active_conditions
assert fire_sorcerer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.RESISTANCE
assert fire_sorcerer.health.get_resistance(DamageType.COLD) == ResistanceStatus.NONE

hp_before = get_hp(fire_sorcerer)
actual_fire_damage = deal_damage_to(fire_sorcerer, 20, DamageType.FIRE)

assert actual_fire_damage == 10
assert get_hp(fire_sorcerer) == hp_before - 10
```

The same example proves cleanup and ancestry selection:

```python
fire_sorcerer.remove_condition("Elemental Affinity")

assert fire_sorcerer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.NONE
assert deal_damage_to(fire_sorcerer, 10, DamageType.FIRE) == 10

cold_sorcerer = create_sorcerer(
    SorcererConfig(
        level=6,
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        draconic_damage_type="Cold",
    )
)

assert cold_sorcerer.health.get_resistance(DamageType.COLD) == ResistanceStatus.RESISTANCE
assert cold_sorcerer.health.get_resistance(DamageType.FIRE) == ResistanceStatus.NONE
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_017_sorcerer_draconic_resilience_and_elemental_affinity`
- `tests/engine_book/test_chapter_16_class_features.py`

## Lucky Feat

`LuckyFeature` adds a long-rest `luck_points` resource with maximum 3 and
registers one player-toggleable handler for attack, save, and skill-check d20
result events.

The current processor is not a full player-choice prompt. It is a simple AI:
only own rolls, only if points remain, only when the total is below 10. It
rerolls a d20 and keeps the better result. This is an engine adaptation rather
than a complete table-interaction model of the feat, and the local SRD 5.2 feat
file does not include a Lucky feat entry. The local SRD Halfling Lucky trait is
a different rule: natural 1 only, reroll, must use the new roll.

Example EB-16-005 uses the processor directly with deterministic dice:

```python
entity.add_condition(LuckyFeature(source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid))

with patch("dnd.core.dice.random.randint", return_value=20):
    modified = lucky_processor(low_event, entity.uuid)

assert modified.get_effective_roll().total == 20
assert entity.action_economy.resources["luck_points"].current == 2
assert modified.roll_modifications
```

Example EB-16-025 pins the policy and feature lifecycle:

```python
handler = entity.get_event_handler_by_name("Lucky")
resource = entity.action_economy.resources["luck_points"]

assert handler is not None
assert handler.player_toggleable
assert {trigger.event_type for trigger in handler.trigger_conditions} == {
    EventType.ATTACK_D20_ROLL_RESULT,
    EventType.SAVE_D20_ROLL_RESULT,
    EventType.CHECK_D20_ROLL_RESULT,
}
assert resource.maximum == 3

with patch("dnd.core.dice.random.randint", return_value=20):
    own_low = lucky_processor(make_event(entity, 4, bonus), entity.uuid)

assert own_low is not None
assert own_low.get_effective_roll().total == 20
assert resource.current == 2

assert lucky_processor(make_event(other, 4, other_bonus), entity.uuid) is None
assert resource.current == 2

assert lucky_processor(make_event(entity, 10, bonus), entity.uuid) is None
assert resource.current == 2

resource.current = 0
assert lucky_processor(make_event(entity, 4, bonus), entity.uuid) is None
assert resource.current == 0

entity.action_economy.on_long_rest()
assert resource.current == 3

entity.remove_condition("Lucky")

assert "Lucky" not in entity.active_conditions
assert entity.get_event_handler_by_name("Lucky") is None
assert not entity.action_economy.has_resource("luck_points")
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_005_lucky_feat_resource_and_d20_processor`
- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_025_lucky_policy_lifecycle_and_cleanup_contract`
- `tests/engine_book/test_chapter_16_class_features.py`

## Divine Smite

Divine Smite is implemented as handler registration, not a normal action.
`register_divine_smite()` adds one toggleable `DAMAGE_ROLL_RESULT` handler per
slot level, highest first.

Each handler checks:

- the event is a damage-roll result;
- the source is the paladin;
- the weapon slot is melee;
- the attack is a hit or crit;
- no previous Divine Smite handler has already marked the event;
- the matching spell slot is available.

When it fires, it consumes that slot, appends one radiant damage payload, rolls
the smite dice, and records metadata in event context.

The SRD target-type rider is part of the same handler: undead and fiend targets
add one radiant d8 after the normal slot-level calculation, raising the cap from
5d8 to 6d8 for those target types.

Example EB-16-006:

```python
register_divine_smite(paladin, max_slot_level=2)
force_attack_hit(paladin)

Attack(
    source_entity_uuid=paladin.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    template=False,
).apply()

context = get_smite_context(paladin.uuid)

assert context["divine_smite_slot_level"] == 2
assert context["divine_smite_dice_count"] == 3
assert paladin.action_economy.spell_slot_2.normalized_score == 0
assert paladin.action_economy.spell_slot_1.normalized_score == 1
```

Example EB-16-018 covers the handler gates and critical-hit dice behavior:

```python
fallthrough_paladin.set_handler_enabled("Divine Smite (L3)", False)
force_attack_hit(fallthrough_paladin)

Attack(
    source_entity_uuid=fallthrough_paladin.uuid,
    target_entity_uuid=fallthrough_target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    template=False,
).apply()

fallthrough_context = get_smite_context(fallthrough_paladin.uuid)

assert fallthrough_context["divine_smite_slot_level"] == 2
assert fallthrough_paladin.action_economy.spell_slot_3.normalized_score == 1
assert fallthrough_paladin.action_economy.spell_slot_2.normalized_score == 0
```

The same executable example proves that:

- disabling every smite handler preserves every spell slot;
- a miss preserves the spell slot and records no smite context;
- a ranged weapon hit preserves the spell slot and records no smite context;
- an empty matching spell slot records no smite context;
- a critical hit still records the base smite dice count, but the appended
  radiant roll contains doubled dice.

Example EB-16-024 covers the SRD creature-type dice and cap:

```python
humanoid_event, _ = smite_case(CreatureType.HUMANOID, 5)
humanoid_results = humanoid_event.final_rolls[-1].results

assert humanoid_event.context["divine_smite_slot_level"] == 5
assert humanoid_event.context["divine_smite_dice_count"] == 5
assert humanoid_event.context["divine_smite_creature_type_bonus"] == 0
assert isinstance(humanoid_results, list)
assert len(humanoid_results) == 5

undead_event, _ = smite_case(CreatureType.UNDEAD, 1)
undead_results = undead_event.final_rolls[-1].results

assert undead_event.context["divine_smite_slot_level"] == 1
assert undead_event.context["divine_smite_dice_count"] == 3
assert undead_event.context["divine_smite_creature_type_bonus"] == 1
assert isinstance(undead_results, list)
assert len(undead_results) == 3

fiend_event, _ = smite_case(CreatureType.FIEND, 5)
fiend_results = fiend_event.final_rolls[-1].results

assert fiend_event.context["divine_smite_slot_level"] == 5
assert fiend_event.context["divine_smite_dice_count"] == 6
assert fiend_event.context["divine_smite_creature_type_bonus"] == 1
assert isinstance(fiend_results, list)
assert len(fiend_results) == 6
```

Parity tests:

- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_006_divine_smite_handlers_use_highest_melee_hit_slot_once`
- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_018_divine_smite_handler_gates_fallthrough_and_critical_dice`
- `tests/engine_book/test_chapter_16_class_features.py::test_eb_16_024_divine_smite_creature_type_bonus_dice_and_cap`
- `tests/engine_book/test_chapter_16_class_features.py`

## Documentation Hygiene

The class-feature subsystem has had a first hygiene pass across
`dnd/classes/*.py`: standalone comments, inline comments, and section banners
were removed from the Fighter, Barbarian, Rage/Frenzy, Sorcerer, Paladin, feat,
dice-processor, and factory modules. The pass is deliberately narrow and
behavior-preserving.

The public factory config models now expose all 63 construction fields through
`Field(..., description=...)`, covering `FighterConfig`, `BarbarianConfig`, and
`SorcererConfig`. Rage/Frenzy model metadata is also cleaned for 33 public
fields across `Raging`, `Rage`, `EndRage`, `RageFeature`, `Frenzied`,
`FrenziedStrike`, `Frenzy`, and `FrenzyFeature`. `LuckyFeature` adds 2 cleaned
feat-condition fields. Fighter fighting-style conditions add 12 cleaned fields
across Archery, Defense, Dueling, Great Weapon Fighting, Protection, and
Two-Weapon Fighting. Second Wind and Action Surge feature/action models add 18
cleaned fields across `SecondWind`, `SecondWindFeature`, `ActionSurging`,
`ActionSurge`, and `ActionSurgeFeature`, bringing the guarded Chapter 16
class-feature metadata slice to 128 public fields. The remaining Fighter
feature/action models add 21 cleaned fields across `ImprovedCritical`,
`ExtraAttacksGranted`, `ExtraAttack`, `ExtraAttackFeature`, `Indomitable`,
`SuperiorCritical`, and `Survivor`, bringing the guarded Chapter 16
class-feature metadata slice to 149 public fields. Early Barbarian tactical and
scaling models add 19 cleaned fields across `RecklessAttacking`,
`RecklessAttack`, `RecklessAttackFeature`, `DangerSense`, `FastMovement`,
`MindlessRage`, `FeralInstinct`, and `BrutalCritical`, bringing the guarded
Chapter 16 class-feature metadata slice to 168 public fields. The remaining
high-level Barbarian models add 22 cleaned fields across `RelentlessRage`,
`PersistentRage`, `IndomitableMight`, `PrimalChampion`, `Retaliation`,
`IntimidatingPresenceImmunity`, `IntimidatingPresence`,
`ExtendIntimidatingPresence`, and `IntimidatingPresenceFeature`, bringing the
guarded Chapter 16 class-feature metadata slice to 190 public fields. Sorcerer
feature condition/action models add 41 cleaned fields across
`DraconicResilience`, `ElementalAffinity`, `MetamagicActive`, `QuickenedSpell`,
`TwinnedSpell`, `DistantSpell`, `ConvertSlotToSP`, `ConvertSPToSlot`, and
`SorceryPointsFeature`, bringing the guarded Chapter 16 class-feature metadata
slice to 231 public fields. The complete guarded Chapter 16 class-feature model
set now uses Google-style class docstrings with field-level `Attributes:`
entries, covering all 56 guarded classes across factory configs, Fighter,
Barbarian, Rage/Frenzy, Sorcerer, and Lucky feature models. The integrity suite
guards these class-feature metadata and docstring contracts in
`tests/engine_book/test_book_integrity.py`.

Further Google-style docstring normalization outside the guarded class-feature
model slice remains a later scoped hygiene pass.

## Deep Coverage Backlog

Current Chapter 16 backlog is covered. Add new rows only after further code
study, new feature work, or a concrete controller/player-intervention API.
