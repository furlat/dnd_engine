# 15. Spell Families And Implemented Spells

## Purpose

Chapter 14 documented the generic spellcasting substrate. This chapter documents
the implemented spell families that sit on top of it: spell catalog membership,
damage archetypes, healing, buffs, restoration, concentration links, zones,
teleportation, special senses, invisibility, and temporary hit points.

The examples are executable in both:

- `tests/engine_book/test_chapter_15_spell_families.py`
- `tests/engine_book/test_chapter_15_spell_families.py`

The pytest file calls the same example functions, so the book examples and the
`uv run pytest` suite stay in 1:1 parity.

This is pattern-level coverage. The engine contains many more spells than this
chapter can explain line by line, so per-spell SRD relationship rows remain a
separate deep-coverage backlog.

## Source Files Studied

- `dnd/spells/__init__.py`
- `dnd/spells/abjuration.py`
- `dnd/spells/conjuration.py`
- `dnd/spells/divination.py`
- `dnd/spells/enchantment.py`
- `dnd/spells/evocation.py`
- `dnd/spells/illusion.py`
- `dnd/spells/necromancy.py`
- `dnd/spells/transmutation.py`
- `dnd/actions.py`
- `dnd/conditions.py`
- `dnd/tile_conditions.py`
- `dnd/entity.py`
- `dnd/blocks/health.py`
- `examples/test_fireball.py`
- `examples/test_magic_missile_multi.py`
- `examples/test_healing_spells.py`
- `examples/test_spike_growth.py`
- `examples/test_haste.py`
- `examples/test_grease.py`
- `examples/test_web.py`
- `examples/test_sense_buff_spells.py`
- `examples/test_sleep_color_spray.py`
- `examples/test_new_spells.py`
- `examples/test_new_spells_batch2.py`
- `tests/engine_book/test_chapter_15_spell_families.py`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Rules Relationship

Status: mixed.

- `SRD-shaped`: the implemented spell families use local SRD spell files under
  `interactive_ruleset/Spells/*.md` as the comparison point for names, levels,
  schools, selected ranges, saving throw abilities, damage types, concentration
  flags, and representative effects.
- `SRD-shaped`: cantrips such as `Fire Bolt` and `Sacred Flame` use the generic
  cantrip threshold helper documented in Chapter 14. This chapter samples those
  effects rather than proving every SRD formula for every spell.
- `Engine adaptation`: zones are represented as conditions on the caster that
  register spatial handlers and tile markers, then link to concentration for
  cleanup.
- `Engine adaptation`: `Misty Step` updates position directly through the
  entity/grid position API rather than modeling a path.
- `Engine adaptation`: `False Life` writes temporary HP through
  `Health.add_temporary_hit_points()`, which replaces lower temporary HP rather
  than stacking it.
- `Engine extension`: many spell events carry visual/client metadata such as
  projectile type, damage type, AoE shape, total target counts, and child spell
  events.
- `Known implementation detail`: single-target attack spells such as
  `FireBolt` populate `damage_rolls` and damage payloads but do not necessarily
  populate the parent event's `total_damage` aggregate. Tests assert the actual
  HP delta and roll payload for those spells.

## Spell Catalog

The catalog in `dnd/spells/__init__.py` imports spell classes by school, groups
them by spell level, and merges those dictionaries into `ALL_SPELLS`.

Example EB-15-001 proves representative catalog identity:

```python
representatives = {
    "Fire Bolt": (FireBolt, 0, "evocation", TargetType.ENTITY),
    "Magic Missile": (MagicMissile, 1, "evocation", TargetType.MULTI_ENTITY),
    "Fireball": (Fireball, 3, "evocation", TargetType.POSITION_AOE),
    "Mage Armor": (MageArmor, 1, "abjuration", TargetType.ENTITY),
    "Misty Step": (MistyStep, 2, "conjuration", TargetType.POSITION),
}

for spell_name, (spell_cls, level, school, target_type) in representatives.items():
    spell = ALL_SPELLS[spell_name](source_entity_uuid=uuid4())
    assert ALL_SPELLS[spell_name] is spell_cls
    assert spell.spell_level == level
    assert spell.spell_school == school
    assert spell.target_type == target_type
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_001_spell_catalog_groups_representative_families`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Evocation Damage Families

Evocation demonstrates three major offensive shapes:

- spell attack: `FireBolt`;
- save cantrip: `SacredFlame`;
- position AoE save: `Fireball`.

`FireBolt` uses the caster's spell attack bonus and target AC propagation, rolls
fire damage on hit, and stores the roll in `damage_rolls`.

`SacredFlame` asks the target for a Dexterity saving throw against
`caster.spell_save_dc()`. On a failed save, it rolls radiant damage without crit
logic because it is a saving throw spell.

`Fireball` is a `POSITION_AOE` spell. The parent action resolves targets through
AoE convolution, then each target receives its own child spell application with
an independent Dexterity saving throw and damage result.

Example EB-15-002:

```python
force_spell_attack_hit(caster)
fire_bolt_event = FireBolt(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    caster_level=5,
    template=False,
).apply()

assert DamageType.FIRE in fire_bolt_event.damage_types
assert fire_bolt_event.damage_rolls[0].total > 0

penalize_save(target, "dexterity")
sacred_event = SacredFlame(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    caster_level=5,
    template=False,
).apply()

assert sacred_event.save_ability == "dexterity"
assert sacred_event.save_success is False
assert DamageType.RADIANT in sacred_event.damage_types
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_002_evocation_attack_save_and_area_damage_patterns`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Auto-Hit Damage And Healing

`MagicMissile` represents auto-hit multi-target damage. It is a
`MULTI_ENTITY` spell with repeated target support: the same target can receive
multiple darts, and the parent event aggregates the child events.

`CureWounds` and `HealingWord` represent healing spells. They compute healing
from spell dice plus casting ability modifier, fire spell/heal events, and then
call the entity healing path. `HealingWord` spends a bonus action instead of an
action.

Example EB-15-003:

```python
missile_event = MagicMissile(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    template=False,
).apply()

assert missile_event.total_targets == 3
assert DamageType.FORCE in missile_event.damage_types

set_hp(ally, 1)
cure_event = CureWounds(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert get_hp(ally) > 1
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_003_auto_hit_and_healing_spell_patterns`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Abjuration Buffs And Restoration

`MageArmor` is a protective condition spell. It applies a `Mage Armor`
condition to an unarmored target and modifies the target's AC machinery.

`LesserRestoration` is a removal spell. It scans a fixed list of supported
conditions, then removes one active condition tagged `ConditionTag.DISEASE`.
`GreaterRestoration` uses a broader engine-supported list, then removes one
active condition tagged `ConditionTag.PETRIFICATION`,
`ConditionTag.CURSE`, `ConditionTag.ABILITY_SCORE_REDUCTION`, or
`ConditionTag.HIT_POINT_MAXIMUM_REDUCTION`. `RemoveCurse` does not use names; it
removes every active condition tagged with `ConditionTag.CURSE`.

The same abjuration family also includes protective spells that prevent or
absorb harm rather than removing an existing effect:

- `ProtectionFromPoison` neutralizes an active `Poisoned` condition, adds poison
  resistance, adds advantage to saving throw requests whose
  `condition_context` is `"Poisoned"`, and adds a static immunity against
  future `Poisoned` applications.
- `DeathWard` registers a one-use handler for lethal `TAKE_DAMAGE` and
  no-damage `INSTANT_DEATH`. Lethal damage is rewritten so the target remains
  at 1 HP, while instant death is canceled before the normal `DeathEvent`; both
  paths remove `Death Ward`.
- `FreedomOfMovement` sets the target's difficult-terrain bypass flag, adds
  static immunities against `Grappled` and `Restrained`, blocks magical speed
  reduction, adds contextual immunity against `Paralyzed` when the incoming
  condition is tagged `ConditionTag.MAGICAL`, and registers a self action that
  spends 5 feet of movement to escape active nonmagical `Grappled` or
  `Restrained` conditions.

Example EB-15-004:

```python
mage_armor_event = MageArmor(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    template=False,
).apply()

assert "Mage Armor" in caster.active_conditions

poison = Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid)
caster.add_condition(poison)

restore_event = LesserRestoration(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    template=False,
).apply()

assert "Poisoned" not in caster.active_conditions
```

Example EB-15-023 pins the restoration matrix. Lesser Restoration removes a
supported `Poisoned` condition, then a disease-tagged condition, while
preserving unsupported `Stunned`; Greater Restoration then removes `Stunned`
and its `Incapacitated` sub-condition before removing one curse-tagged effect.
Remove Curse removes all remaining curse-tagged effects while preserving
unrelated `Poisoned`:

```python
ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
ally.add_condition(LingeringDiseaseEffect(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
ally.add_condition(Stunned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))

lesser_event = LesserRestoration(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert "Poisoned" not in ally.active_conditions
assert "Lingering Disease" in ally.active_conditions
assert "Stunned" in ally.active_conditions
assert "Incapacitated" in ally.active_conditions

lesser_disease_event = LesserRestoration(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert "Lingering Disease" not in ally.active_conditions
assert "Stunned" in ally.active_conditions
assert "Incapacitated" in ally.active_conditions

greater_event = GreaterRestoration(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert "Stunned" not in ally.active_conditions
assert "Incapacitated" not in ally.active_conditions

ally.add_condition(
    AbilityCurseEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cursed_ability="strength",
    )
)
ally.add_condition(LingeringCurseEffect(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))

greater_curse_event = GreaterRestoration(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert "Bestow Curse" not in ally.active_conditions
assert "Lingering Curse" in ally.active_conditions

ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
ally.add_condition(
    AbilityCurseEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        cursed_ability="strength",
    )
)

remove_curse_event = RemoveCurse(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert "Bestow Curse" not in ally.active_conditions
assert "Lingering Curse" not in ally.active_conditions
assert "Poisoned" in ally.active_conditions
```

Example EB-15-038 extends Greater Restoration to SRD effect categories that are
represented by condition-owned modifiers. The spell removes one tagged effect
per cast. Removing the ability-score and hit-point-maximum effects also removes
their owned modifiers through normal condition cleanup:

```python
base_strength_score = ally.ability_scores.strength.ability_score.score
base_max_hp = get_max_hp(ally)

ally.add_condition(BookPetrifyingEffect(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
ally.add_condition(
    BookAbilityScoreReduction(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        ability_name="strength",
        penalty=-4,
    )
)
ally.add_condition(
    BookHitPointMaximumReduction(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        penalty=-5,
    )
)

assert ally.ability_scores.strength.ability_score.score == base_strength_score - 4
assert get_max_hp(ally) == base_max_hp - 5

GreaterRestoration(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, template=False).apply()
assert "Book Petrifying Effect" not in ally.active_conditions

caster.action_economy.reset_all_costs()
GreaterRestoration(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, template=False).apply()
assert ally.ability_scores.strength.ability_score.score == base_strength_score

caster.action_economy.reset_all_costs()
GreaterRestoration(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, template=False).apply()
assert get_max_hp(ally) == base_max_hp
```

Example EB-15-039 proves the same restoration path removes the standard
`Petrified` condition model and its owned subtree/state:

```python
ally.add_condition(Petrified(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))

assert "Petrified" in ally.active_conditions
assert "Incapacitated" in ally.active_conditions
assert ally.check_condition_immunity("Poisoned")

for damage_type in DamageType:
    assert ally.health.get_resistance(damage_type) == ResistanceStatus.RESISTANCE

GreaterRestoration(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, template=False).apply()

assert "Petrified" not in ally.active_conditions
assert "Incapacitated" not in ally.active_conditions
assert not ally.check_condition_immunity("Poisoned")

for damage_type in DamageType:
    assert ally.health.get_resistance(damage_type) == ResistanceStatus.NONE
```

Example EB-15-040 proves Greater Restoration's exhaustion clause. Each cast
reduces one exhaustion level and replaces the old condition so its previous
modifiers are cleaned before the next level is applied:

```python
ally.add_condition(Exhaustion(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, level=3))

assert ally.active_conditions["Exhaustion"].level == 3
assert ally.action_economy.movement.normalized_score == base_movement // 2
assert ally.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE

GreaterRestoration(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, template=False).apply()

assert ally.active_conditions["Exhaustion"].level == 2
assert ally.action_economy.movement.normalized_score == base_movement // 2
assert ally.equipment.attack_bonus.advantage == AdvantageStatus.NONE

caster.action_economy.reset_all_costs()
GreaterRestoration(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, template=False).apply()
assert ally.active_conditions["Exhaustion"].level == 1

caster.action_economy.reset_all_costs()
GreaterRestoration(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid, template=False).apply()
assert "Exhaustion" not in ally.active_conditions
```

Example EB-15-025 pins protective abjurations:

```python
ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Poisoned" in ally.active_conditions

poison_event = ProtectionFromPoison(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert "Protection from Poison" in ally.active_conditions
assert "Concentrating" not in caster.active_conditions
assert "Poisoned" not in ally.active_conditions

poison_damage = deal_damage_to(
    ally,
    20,
    damage_type=DamageType.POISON,
    source_uuid=caster.uuid,
)
assert poison_damage == 10

ordinary_save_request = caster.create_saving_throw_request(
    target_entity_uuid=ally.uuid,
    ability_name="constitution",
    dc=10,
)
_, ordinary_save_roll, _ = ally.saving_throw(ordinary_save_request)
assert ordinary_save_roll.advantage_status == AdvantageStatus.NONE

poison_save_request = caster.create_saving_throw_request(
    target_entity_uuid=ally.uuid,
    ability_name="constitution",
    dc=10,
    condition_context="Poisoned",
)
_, poison_save_roll, _ = ally.saving_throw(poison_save_request)
assert poison_save_roll.advantage_status == AdvantageStatus.ADVANTAGE

ally.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Poisoned" not in ally.active_conditions

ward_event = DeathWard(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert "Death Ward" in ally.active_conditions
assert ally.get_event_handler_by_name("Death Ward") is not None

set_hp(ally, 10)
warded_damage = deal_damage_to(
    ally,
    50,
    damage_type=DamageType.SLASHING,
    source_uuid=caster.uuid,
)
assert warded_damage == 9
assert get_hp(ally) == 1
assert "Death Ward" not in ally.active_conditions
assert ally.get_event_handler_by_name("Death Ward") is None

set_hp(ally, 50)
second_ward_event = DeathWard(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()
assert "Death Ward" in ally.active_conditions

caster.action_economy.reset_all_costs()
warded_kill_event = PowerWordKill(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()
assert "Death Ward" not in ally.active_conditions
assert get_hp(ally) == 50
assert "Dead" not in ally.active_conditions

caster.action_economy.reset_all_costs()
set_hp(doomed, 50)
setup_standard_actions(doomed)
unwarded_kill_event = PowerWordKill(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=doomed.uuid,
    template=False,
).apply()
assert get_hp(doomed) == 0
assert "Dead" in doomed.active_conditions

ally.add_condition(Grappled(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
ally.add_condition(Restrained(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Grappled" in ally.active_conditions
assert "Restrained" in ally.active_conditions
assert ally.action_economy.movement.normalized_score == 0

movement_event = FreedomOfMovement(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

assert "Freedom of Movement" in ally.active_conditions
assert ally.ignore_difficult_terrain
assert ally.ignore_magical_speed_reduction
assert ally.ignore_underwater_penalties
assert "Grappled" in ally.active_conditions
assert "Restrained" in ally.active_conditions

available_escape_actions = ally.get_available_actions()
escape_action_info = next(
    action for action in available_escape_actions.self_actions
    if action.template_name == "Freedom of Movement Escape"
)
assert escape_action_info.can_afford
assert len(escape_action_info.valid_targets) == 1

escape_event = execute_by_index(
    ally,
    "Freedom of Movement Escape",
    0,
    available=available_escape_actions,
)
assert escape_event.phase == EventPhase.COMPLETION
assert "Grappled" not in ally.active_conditions
assert "Restrained" not in ally.active_conditions
assert ally.action_economy.movement.normalized_score == 25
ally.action_economy.reset_all_costs()

ally.equipment.equip(create_longbow(ally.uuid), WeaponSlot.RANGED_MAIN)
ally.add_condition(Underwater(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
ranged_underwater_context = {
    "weapon_slot": WeaponSlot.RANGED_MAIN.value,
    "weapon_name": "Longbow",
    "range_type": RangeType.RANGE.value,
    "is_long_range": True,
}
protected_ranged_attack = ally.attack_bonus(WeaponSlot.RANGED_MAIN, caster.uuid)
protected_ranged_attack.set_context(ranged_underwater_context)
assert protected_ranged_attack.advantage == AdvantageStatus.NONE
assert protected_ranged_attack.auto_hit == AutoHitStatus.NONE

water_lane = [(8, 1), (9, 1), (10, 1)]
grid = get_map()
for position in water_lane:
    grid.set_tile(position[0], position[1], tile=water_factory(position), fire_event=False)

Entity.update_entity_position(ally, water_lane[0])
ally.update_entity_senses(max_distance=20)
ally.register_action(Swim(source_entity_uuid=ally.uuid, template=True))
available_swims = ally.get_available_actions()
swim_info = next(action for action in available_swims.position_actions if action.template_name == "Swim")
assert any(target.position == water_lane[-1] and target.path_cost == 10 for target in swim_info.valid_targets)
ally.unregister_action("Swim")
ally.action_economy.reset_all_costs()
protected_swim = Swim(source_entity_uuid=ally.uuid, end_position=water_lane[-1]).apply()
assert protected_swim.phase == EventPhase.COMPLETION
assert ally.position == water_lane[-1]
assert ally.action_economy.movement.normalized_score == 20
Entity.update_entity_position(ally, water_lane[0])
ally.action_economy.reset_all_costs()

protected_speed = ally.action_economy.movement.normalized_score
protected_ac = ally.ac_bonus().normalized_score
ally.add_condition(SlowedEffect(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Slowed" in ally.active_conditions
assert ally.action_economy.movement.normalized_score == protected_speed
assert ally.ac_bonus().normalized_score == protected_ac - 2
ally.remove_condition("Slowed")

ally.add_condition(SpiritGuardiansSlowed(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Spirit Guardians Slowed" not in ally.active_conditions
assert ally.action_economy.movement.normalized_score == protected_speed

caster.add_condition(
    RayOfFrostEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        affected_target_uuid=ally.uuid,
    )
)
assert "Ray of Frost Effect" not in caster.active_conditions
assert ally.action_economy.movement.normalized_score == protected_speed

ally.add_condition(Grappled(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
ally.add_condition(Restrained(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Grappled" not in ally.active_conditions
assert "Restrained" not in ally.active_conditions
ally.add_condition(
    Paralyzed(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        tags={ConditionTag.MAGICAL},
    )
)
assert "Paralyzed" not in ally.active_conditions

ally.add_condition(Paralyzed(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Paralyzed" in ally.active_conditions
ally.remove_condition("Paralyzed")

ally.remove_condition("Freedom of Movement")
assert not ally.ignore_difficult_terrain
assert not ally.ignore_magical_speed_reduction
assert not ally.ignore_underwater_penalties
assert ally.get_action_template("Freedom of Movement Escape") is None

unprotected_ranged_attack = ally.attack_bonus(WeaponSlot.RANGED_MAIN, caster.uuid)
unprotected_ranged_attack.set_context(ranged_underwater_context)
assert unprotected_ranged_attack.advantage == AdvantageStatus.DISADVANTAGE
assert unprotected_ranged_attack.auto_hit == AutoHitStatus.AUTOMISS

ally.equipment.equip(create_club(ally.uuid), WeaponSlot.MELEE_MAIN)
melee_underwater_context = {
    "weapon_slot": WeaponSlot.MELEE_MAIN.value,
    "weapon_name": "Club",
    "range_type": RangeType.REACH.value,
    "is_long_range": False,
}
unprotected_melee_attack = ally.attack_bonus(WeaponSlot.MELEE_MAIN, caster.uuid)
unprotected_melee_attack.set_context(melee_underwater_context)
assert unprotected_melee_attack.advantage == AdvantageStatus.DISADVANTAGE

ally.swimming_speed = 30
swimming_melee_attack = ally.attack_bonus(WeaponSlot.MELEE_MAIN, caster.uuid)
swimming_melee_attack.set_context(melee_underwater_context)
assert swimming_melee_attack.advantage == AdvantageStatus.NONE
ally.swimming_speed = 0

unprotected_swim = Swim(source_entity_uuid=ally.uuid, end_position=water_lane[-1]).apply()
assert unprotected_swim.phase == EventPhase.COMPLETION
assert ally.position == water_lane[-1]
assert ally.action_economy.movement.normalized_score == 10
ally.action_economy.reset_all_costs()

unprotected_speed = ally.action_economy.movement.normalized_score
ally.add_condition(SlowedEffect(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Slowed" in ally.active_conditions
assert ally.action_economy.movement.normalized_score == unprotected_speed // 2
ally.remove_condition("Slowed")

ally.add_condition(SpiritGuardiansSlowed(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Spirit Guardians Slowed" in ally.active_conditions
assert ally.action_economy.movement.normalized_score == unprotected_speed // 2
ally.remove_condition("Spirit Guardians Slowed")

caster.add_condition(
    RayOfFrostEffect(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid,
        affected_target_uuid=ally.uuid,
    )
)
assert "Ray of Frost Effect" in caster.active_conditions
assert ally.action_economy.movement.normalized_score == unprotected_speed - 10
caster.remove_condition("Ray of Frost Effect")

ally.add_condition(Grappled(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
ally.add_condition(Restrained(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid))
assert "Grappled" in ally.active_conditions
assert "Restrained" in ally.active_conditions
ally.add_condition(
    Paralyzed(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        tags={ConditionTag.MAGICAL},
    )
)
assert "Paralyzed" in ally.active_conditions
```

SRD relationship: Lesser Restoration explicitly ends one blinded, deafened,
paralyzed, or poisoned condition or one disease, with disease represented by
`ConditionTag.DISEASE`. Greater Restoration removes one supported major
condition, one petrification-tagged effect, one curse-tagged condition, one
ability-score-reduction-tagged condition, or one
hit-point-maximum-reduction-tagged condition, and reduces `Exhaustion` by one
level. Remove Curse ends every curse currently represented as a
`ConditionTag.CURSE` condition. Protection from Poison, Death Ward, and Freedom of
Movement are implemented as persistent engine conditions. Protection from Poison
currently models active `Poisoned` neutralization, poison-damage resistance,
contextual advantage on saves against becoming `Poisoned`, and future `Poisoned`
immunity.
Death Ward models lethal damage survival and no-damage instant-death negation
through `InstantDeathEvent`; Power Word Kill now uses that no-damage primitive
instead of fake damage. Freedom of Movement currently models difficult-terrain
bypass, magical speed-reduction prevention, `Grappled`/`Restrained` immunity,
magical `Paralyzed` immunity via `ConditionTag.MAGICAL`, and the SRD 5-foot
automatic escape from active nonmagical `Grappled` or `Restrained` conditions.
The SRD underwater attack-penalty clause is represented by the explicit
`Underwater` condition: melee attacks without swim speed or an exception weapon
gain disadvantage, ranged attacks with non-exception weapons gain disadvantage,
and ranged attacks beyond normal range gain `AUTOMISS`. Freedom of Movement
sets `ignore_underwater_penalties` while active so those attack penalties do not
apply. `Swim` is the action-level water traversal surface: it uses
`MovementMode.SWIMMING`, spends movement per water step, doubles that cost for a
creature without swim speed, and lets Freedom of Movement suppress the extra
underwater movement cost through the same `ignore_underwater_penalties` flag.

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_004_abjuration_buffs_and_restoration_remove_conditions`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_023_restoration_spells_remove_supported_effects_only`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_038_greater_restoration_removes_srd_tagged_effect_surfaces`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_039_greater_restoration_removes_standard_petrified_condition`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_040_greater_restoration_reduces_exhaustion_one_level`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_025_protective_abjurations_prevent_and_absorb_effects`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Abjuration Reactions: Shield

`Shield` is implemented as a registered reaction handler rather than a normal
player-selected `SpellAction`. `register_shield_reaction(entity)` adds an
event handler named `Shield` with two trigger paths:

- `ATTACK` at `EXECUTION`: after the attack roll and outcome are known, the
  handler checks whether the result is a normal hit and whether +5 AC would
  convert that hit into a miss;
- `TAKE_DAMAGE` at `EFFECT`: if the damage descends from a `Magic Missile`
  spell event, the handler consumes resources, applies `Shield`, and cancels
  Magic Missile damage on the protected target.

The `ShieldBuff` condition is the persistent state. It adds +5 AC, registers a
Magic Missile blocker for subsequent darts, and registers turn-start cleanup.

Example EB-15-009 captures the attack-reaction path:

```python
register_shield_reaction(shielded)
ac_before = shielded.ac_bonus().normalized_score

with patch("dnd.core.dice.random.randint", return_value=10):
    attack_event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=shielded.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

assert attack_event.attack_outcome == AttackOutcome.MISS
assert attack_event.dice_roll.total == ac_before
assert "Shield" in shielded.active_conditions
assert shielded.action_economy.reactions.normalized_score == 0
assert shielded.action_economy.spell_slot_1.normalized_score == 0
```

Example EB-15-010 captures the Magic Missile path. Only the shielded target's
darts are canceled; another target in the same multi-target cast still takes
force damage:

```python
event = MagicMissile(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=shielded.uuid,
    extra_target_entity_uuids=[ally.uuid],
    template=False,
).apply()

assert event.total_targets == 3
assert event.total_damage > 0
assert get_hp(shielded) == shielded_hp
assert get_hp(ally) < ally_hp
assert "Shield" in shielded.active_conditions
```

Example EB-15-020 captures the resource-saving and lifecycle edges around the
same handler. The attack trigger does not fire for critical hits, misses, or a
hit that would still hit after +5 AC. It also does not fire without an available
reaction or 1st-level-or-higher spell slot. Once the buff is active, the
permanent `Shield` reaction handler stays registered, but the condition-owned
Magic Missile blocker and turn-start cleanup handlers are removed when the
shielded entity starts its next turn.

```python
for d20_result, expected_outcome in (
    (20, AttackOutcome.CRIT),
    (5, AttackOutcome.MISS),
    (15, AttackOutcome.HIT),
):
    shielded, attacker = setup_pair()
    reactions_before = shielded.action_economy.reactions.normalized_score
    slots_before = shielded.action_economy.spell_slot_1.normalized_score

    event = run_shield_attack(attacker, shielded, d20_result)

    assert event.attack_outcome == expected_outcome
    assert "Shield" not in shielded.active_conditions
    assert shielded.action_economy.reactions.normalized_score == reactions_before
    assert shielded.action_economy.spell_slot_1.normalized_score == slots_before

shielded, attacker = setup_pair(spell_slots={1: 2})
base_ac_bonus = shielded.equipment.ac_bonus.normalized_score
first_event = run_shield_attack(attacker, shielded, 10)

assert first_event.attack_outcome == AttackOutcome.MISS
assert "Shield" in shielded.active_conditions
assert shielded.equipment.ac_bonus.normalized_score == base_ac_bonus + 5
assert shielded.action_economy.reactions.normalized_score == 0
assert shielded.action_economy.spell_slot_1.normalized_score == 1
assert shielded.get_event_handler_by_name("Shield: Magic Missile Block") is not None

attacker.action_economy.reset_all_costs()
second_event = run_shield_attack(attacker, shielded, 10)

assert second_event.attack_outcome == AttackOutcome.MISS
assert shielded.action_economy.spell_slot_1.normalized_score == 1

turn_start = shielded.on_turn_start(round_number=2, turn_index=0)

assert turn_start.phase == EventPhase.COMPLETION
assert "Shield" not in shielded.active_conditions
assert shielded.equipment.ac_bonus.normalized_score == base_ac_bonus
assert shielded.action_economy.reactions.normalized_score == 1
assert shielded.get_event_handler_by_name("Shield") is not None
assert shielded.get_event_handler_by_name("Shield: Magic Missile Block") is None
```

Example EB-15-022 covers the player-toggleable handler contract. Disabling the
permanent `Shield` handler gates both trigger paths: a marginal weapon hit
stays a hit, and Magic Missile damage is not blocked. Re-enabling the same
handler lets the marginal weapon hit be converted again:

```python
shield_handler = shielded.get_event_handler_by_name("Shield")
assert shield_handler is not None and shield_handler.enabled
assert shielded.set_handler_enabled("Shield", False)
assert not shield_handler.enabled

reactions_before = shielded.action_economy.reactions.normalized_score
slots_before = shielded.action_economy.spell_slot_1.normalized_score

disabled_attack = run_shield_attack(attacker, shielded, 10)

assert disabled_attack.attack_outcome == AttackOutcome.HIT
assert "Shield" not in shielded.active_conditions
assert shielded.action_economy.reactions.normalized_score == reactions_before
assert shielded.action_economy.spell_slot_1.normalized_score == slots_before

attacker.action_economy.reset_all_costs()
assert shielded.set_handler_enabled("Shield", True)

enabled_attack = run_shield_attack(attacker, shielded, 10)

assert enabled_attack.attack_outcome == AttackOutcome.MISS
assert "Shield" in shielded.active_conditions
```

The same executable example resets state, disables `Shield`, casts Magic
Missile at the shielded entity, and asserts that HP falls while reaction and
spell-slot resources remain unchanged.

Example EB-15-036 pins the combat-log boundary. The condition application is a
child of the triggering attack, so the encounter receives one top-level attack
log and the `Shield` application appears in `sub_entries`:

```python
captured_logs = []
EventQueue.set_combat_log_callback(
    lambda event: captured_logs.append(event.combat_log)
    if event.combat_log else None
)

attack_event = run_shield_attack(attacker, shielded, 10)

assert attack_event.combat_log.entry_type == CombatLogEntryType.ATTACK
assert len(captured_logs) == 1

shield_logs = [
    entry for entry in attack_event.combat_log.sub_entries
    if entry.entry_type == CombatLogEntryType.CONDITION_APPLIED
    and entry.target_uuid == str(shielded.uuid)
    and "Shield" in entry.compact
]
assert len(shield_logs) == 1
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_009_shield_reaction_converts_marginal_attack_hit_to_miss`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_010_shield_blocks_magic_missile_darts_against_its_target_only`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_020_shield_non_firing_persistence_and_turn_cleanup`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_022_shield_handler_toggle_gates_attack_and_missile_reactions`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_036_shield_condition_log_nests_under_triggering_attack`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Multi-Target Concentration

`Bless` represents multi-target concentration. It applies one `Bless` effect to
each selected target, creates or reuses the caster's `Concentrating` condition,
and links every applied child condition to that concentration parent.

Breaking concentration removes all linked effects.

Example EB-15-005:

```python
event = Bless(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally_one.uuid,
    extra_target_entity_uuids=[ally_two.uuid],
    template=False,
).apply()

assert event.total_targets == 2
assert "Bless" in ally_one.active_conditions
assert "Bless" in ally_two.active_conditions

concentration = caster.active_conditions["Concentrating"]
assert len(concentration.linked_conditions) == 2

caster.remove_condition("Concentrating")
assert "Bless" not in ally_one.active_conditions
assert "Bless" not in ally_two.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_005_multi_target_concentration_links_each_effect`
- `tests/engine_book/test_chapter_15_spell_families.py`

## D20 Mutation Spells

`Bless`, `Bane`, and `Guidance` are not implemented as passive numerical
modifiers on a target's saving throw, attack, or skill values. They register
event handlers that listen for d20 roll-result events at `EFFECT` phase, then
replace the effective `DiceRoll` and append a roll-modification audit entry.

This means their behavior is visible at the dice-event layer:

- `Bless` listens to the blessed target's attack and save d20 result events and
  adds 1d4 to the effective roll.
- `Bane` listens to the baned target's attack and save d20 result events and
  subtracts 1d4 from the effective roll.
- `Guidance` listens only to the guided target's check d20 result events, adds
  1d4 once, then removes its own condition. Because `Guidance` is linked to
  concentration with the `"last"` child-removal policy, consuming the condition
  also removes `Concentrating`.

EB-15-015 demonstrates the saving-throw path for `Bless` and `Bane`.
EB-15-024 expands that into the roll-type matrix: `Bless` and `Bane` also
mutate attack rolls, do not mutate checks, and `Guidance` does not fire for
attacks or saves before its first check consumes it.

Example EB-15-015 proves Bless and Bane as persistent save-roll mutators:

```python
bless_event = Bless(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=ally.uuid,
    template=False,
).apply()

bless_bonus = ally.saving_throw_bonus(caster.uuid, "wisdom")
with patch("random.randint", side_effect=[10, 3]):
    blessed_roll, blessed_event = ally.roll_d20_event(
        bless_bonus,
        RollType.SAVE,
        ability_name="wisdom",
    )

assert blessed_event.original_roll.results == [10]
assert blessed_roll.total == blessed_event.original_roll.total + 3
assert blessed_event.roll_modifications[0][0] == "Bless"

bane_event = Bane(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=enemy.uuid,
    template=False,
).apply()

bane_bonus = enemy.saving_throw_bonus(caster.uuid, "wisdom")
with patch("random.randint", side_effect=[12, 2]):
    baned_roll, baned_event = enemy.roll_d20_event(
        bane_bonus,
        RollType.SAVE,
        ability_name="wisdom",
    )

assert baned_event.original_roll.results == [12]
assert baned_roll.total == baned_event.original_roll.total - 2
assert baned_event.roll_modifications[0][0] == "Bane"
```

Example EB-15-016 proves Guidance as a one-use check-roll mutator:

```python
event = Guidance(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    template=False,
).apply()

assert "Guidance" in caster.active_conditions
assert "Concentrating" in caster.active_conditions

skill_bonus = caster.skill_bonus(None, "perception")
with patch("random.randint", side_effect=[9, 4]):
    guided_roll, guided_event = caster.roll_d20_event(
        skill_bonus,
        RollType.CHECK,
        skill_name="perception",
    )

assert guided_event.original_roll.results == [9]
assert guided_roll.total == guided_event.original_roll.total + 4
assert guided_event.roll_modifications[0][0] == "Guidance"
assert "Guidance" not in caster.active_conditions
assert "Concentrating" not in caster.active_conditions
```

Example EB-15-024 proves the roll-type boundaries:

```python
bless_attack_bonus = ally.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
with patch("random.randint", side_effect=[8, 4]):
    blessed_attack_roll, blessed_attack_event = ally.roll_d20_event(
        bless_attack_bonus,
        RollType.ATTACK,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )

assert blessed_attack_roll.total == blessed_attack_event.original_roll.total + 4
assert blessed_attack_event.roll_modifications[0][0] == "Bless"

bless_check_bonus = ally.skill_bonus(None, "athletics")
with patch("random.randint", side_effect=[9]):
    blessed_check_roll, blessed_check_event = ally.roll_d20_event(
        bless_check_bonus,
        RollType.CHECK,
        skill_name="athletics",
    )

assert blessed_check_roll.total == blessed_check_event.original_roll.total
assert blessed_check_event.roll_modifications == []
assert "Bless" in ally.active_conditions

bane_attack_bonus = enemy.attack_bonus(WeaponSlot.MELEE_MAIN, target.uuid)
with patch("random.randint", side_effect=[13, 2]):
    baned_attack_roll, baned_attack_event = enemy.roll_d20_event(
        bane_attack_bonus,
        RollType.ATTACK,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )

assert baned_attack_roll.total == baned_attack_event.original_roll.total - 2
assert baned_attack_event.roll_modifications[0][0] == "Bane"

guidance_attack_bonus = caster.attack_bonus(WeaponSlot.MELEE_MAIN)
with patch("random.randint", side_effect=[12]):
    guidance_attack_roll, guidance_attack_event = caster.roll_d20_event(
        guidance_attack_bonus,
        RollType.ATTACK,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    )

assert guidance_attack_roll.total == guidance_attack_event.original_roll.total
assert guidance_attack_event.roll_modifications == []
assert "Guidance" in caster.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_015_bless_and_bane_rewrite_save_d20_results`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_016_guidance_rewrites_one_skill_check_then_cleans_up`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_024_d20_mutation_handlers_are_roll_type_scoped`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Repeat-Save Control

`HoldPerson` and `HoldMonster` are representative repeat-save control spells.
Both spells make an initial Wisdom saving throw. On failure, the target receives
a spell-specific parent condition (`Hold Person` or `Hold Monster`) and that
parent applies `Paralyzed` as a same-block sub-condition. `Paralyzed` then
applies its own `Incapacitated` sub-condition through the standard condition
tree.

The spell-specific parent condition also registers a `TURN_END` handler at
`EFFECT` phase. When the held target ends its turn, the handler makes another
Wisdom save against the original spell DC. A successful repeat save removes the
spell-specific parent condition; normal condition cleanup removes `Paralyzed`
and `Incapacitated`, and the reverse link to the caster's `Concentrating`
condition removes concentration when this was the last linked child.

Example EB-15-017 proves the Hold Person chain:

```python
event = HoldPerson(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    template=False,
).apply()

assert "Hold Person" in target.active_conditions
assert "Paralyzed" in target.active_conditions
hold_effect = target.active_conditions["Hold Person"]
paralyzed = target.active_conditions["Paralyzed"]
assert paralyzed.parent_condition == hold_effect.uuid

concentration = caster.active_conditions["Concentrating"]
assert (target.uuid, hold_effect.uuid) in concentration.linked_conditions

boost_save(target, "wisdom", value=200)
turn_end = target.on_turn_end(round_number=1, turn_index=0)

assert turn_end.phase == EventPhase.COMPLETION
assert "Hold Person" not in target.active_conditions
assert "Paralyzed" not in target.active_conditions
assert "Concentrating" not in caster.active_conditions
```

`HoldMonster` uses the same parent/sub-condition/repeat-save cleanup pattern,
but its target rule is different: it rejects undead instead of requiring a
humanoid.

Example EB-15-018 proves the undead exclusion and repeat-save cleanup:

```python
undead_event = HoldMonster(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=undead.uuid,
    template=False,
).apply()

assert undead_event.canceled
assert "Hold Monster" not in undead.active_conditions
assert caster.action_economy.spell_slot_5.normalized_score == 1

event = HoldMonster(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    template=False,
).apply()

assert "Hold Monster" in target.active_conditions
assert "Paralyzed" in target.active_conditions

boost_save(target, "wisdom", value=200)
target.on_turn_end(round_number=1, turn_index=0)

assert "Hold Monster" not in target.active_conditions
assert "Paralyzed" not in target.active_conditions
assert "Concentrating" not in caster.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_017_hold_person_failed_save_repeat_save_and_cleanup`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_018_hold_monster_excludes_undead_and_repeats_cleanup`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Zones And Spatial Handlers

Zone spells are not represented as loose map globals. A zone spell creates a
condition, usually on the caster, and the condition manages:

- affected positions;
- tile terrain or marker state;
- spatial entry handlers;
- normal turn handlers when needed;
- concentration linkage and cleanup.

`SpikeGrowth` is the representative in this chapter. It creates a
`Spike Growth Zone` condition, registers spatial entry handlers through
`ZoneControlCondition`, and links that zone condition to concentration.

Example EB-15-006:

```python
event = SpikeGrowth(
    source_entity_uuid=caster.uuid,
    end_position=(5, 3),
    template=False,
).apply()

zone = caster.active_conditions["Spike Growth Zone"]
concentration = caster.active_conditions["Concentrating"]

assert len(zone.affected_positions) > 0
assert len(zone.spatial_handler_uuids) > 0
assert (caster.uuid, zone.uuid) in concentration.linked_conditions

caster.remove_condition("Concentrating")
assert "Spike Growth Zone" not in caster.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_006_zone_spells_create_spatial_handlers_and_cleanup_links`
- `tests/engine_book/test_chapter_15_spell_families.py`

Example EB-15-021 broadens the zone-family coverage beyond `SpikeGrowth`.
These spells all use `ZoneControlCondition`, but their trigger surfaces differ:

- `Grease` creates difficult terrain, one spatial entry handler, and one
  turn-start handler. Current implementation treats it as concentration for
  cleanup convenience, although the SRD spell duration is not concentration.
- `Web` creates difficult terrain and light obscurement, restrains on entry,
  restrains on turn start, and grants `Escape Web` while `Web Restrained` is
  active.
- `Cloudkill` is not difficult terrain. It damages on entry and turn start, and
  adds a caster-turn handler that moves the cloud away from the caster.
- `SpiritGuardians` tracks both entry and exit spatial handlers. It damages
  enemies, ignores allies, applies a once-per-turn marker, applies a speed
  penalty while an enemy remains in the zone, and removes that speed penalty
  only when the enemy actually exits the zone.
- `FogCloud`, `Darkness`, and `Daylight` use the same zone base class with
  light modifiers instead of damage or restraint handlers. Fog Cloud applies
  normal darkness as obscurement, Darkness applies magical darkness, and
  Daylight applies very bright illumination.

Example EB-15-021 is shown as one excerpt for readability. The executable test
uses fresh setup between the Grease, Web, Cloudkill, and Spirit Guardians
scenarios so earlier zone state cannot leak into later assertions.

Example EB-15-021:

```python
with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    grease_event = Grease(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5),
        template=False,
    ).apply()

grease_zone = caster.active_conditions["Grease Zone"]
assert grease_zone.adds_difficult_terrain
assert len(grease_zone.spatial_handler_uuids) == 1
assert len(grease_zone.event_handlers_uuids) == 1

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    Entity.update_entity_position(target, (5, 5))
assert "Prone" in target.active_conditions

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    web_event = Web(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5),
        template=False,
    ).apply()

web_zone = caster.active_conditions["Web Zone"]
assert len(web_zone.spatial_handler_uuids) == 1
assert len(web_zone.event_handlers_uuids) == 2

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    target.on_turn_start(round_number=1, turn_index=0)
assert "Web Restrained" in target.active_conditions
assert "Restrained" in target.active_conditions

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    cloudkill_event = Cloudkill(
        source_entity_uuid=caster.uuid,
        end_position=(10, 10),
        template=False,
    ).apply()

cloudkill_zone = caster.active_conditions["Cloudkill Zone"]
assert not cloudkill_zone.adds_difficult_terrain
assert len(cloudkill_zone.spatial_handler_uuids) == 1
assert len(cloudkill_zone.event_handlers_uuids) == 2

hp_before_entry = get_hp(target)
with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    Entity.update_entity_position(target, (10, 10))
assert hp_before_entry - get_hp(target) == 15

old_center = cloudkill_zone.zone_center
with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    caster.on_turn_start(round_number=1, turn_index=0)
assert cloudkill_zone.zone_center != old_center

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    spirit_event = SpiritGuardians(
        source_entity_uuid=caster.uuid,
        template=False,
    ).apply()

spirit_zone = caster.active_conditions["Spirit Guardians Zone"]
assert len(spirit_zone.spatial_handler_uuids) == 2
assert len(spirit_zone.event_handlers_uuids) == 2

enemy_hp_before = get_hp(enemy)
ally_hp_before = get_hp(ally)
with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    Entity.update_entity_position(enemy, (6, 5))
    Entity.update_entity_position(ally, (6, 6))

assert enemy_hp_before - get_hp(enemy) == 9
assert get_hp(ally) == ally_hp_before
assert "Spirit Guardians Triggered" in enemy.active_conditions
assert "Spirit Guardians Slowed" in enemy.active_conditions

hp_after_entry = get_hp(enemy)
with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    Entity.update_entity_position(enemy, (7, 5))
assert get_hp(enemy) == hp_after_entry
assert "Spirit Guardians Slowed" in enemy.active_conditions

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    Entity.update_entity_position(enemy, (12, 12))
assert "Spirit Guardians Slowed" not in enemy.active_conditions

caster.remove_condition("Concentrating")
assert "Spirit Guardians Zone" not in caster.active_conditions
assert all(
    handler_uuid not in EventQueue._handler_positions
    for handler_uuid in spirit_zone.spatial_handler_uuids
)
```

Example EB-15-026 covers light-zone spells. Fog Cloud upcasts by increasing its
radius, applies `LightLevel.DARKNESS` as obscurement to affected tiles, and
cleans that light modifier when concentration ends. Darkness applies
`LightLevel.MAGICAL_DARKNESS`, blocks ordinary vision, and still blocks
darkvision. Daylight can target a magical-darkness point and removes overlapping
`Darkness Zone` conditions, matching the SRD clause that Daylight dispels
darkness from a spell of 3rd level or lower:

```python
fog_event = FogCloud(
    source_entity_uuid=caster.uuid,
    end_position=(16, 16),
    cast_at_level=2,
    template=False,
).apply()

fog_zone = caster.active_conditions["Fog Cloud Zone"]
assert fog_zone.zone_radius_feet == 40
assert get_map().get_tile(16, 16).resolved_light_level == LightLevel.DARKNESS
assert get_map().get_tile(24, 16).resolved_light_level == LightLevel.DARKNESS

caster.remove_condition("Concentrating")
assert "Fog Cloud Zone" not in caster.active_conditions
assert get_map().get_tile(16, 16).resolved_light_level == LightLevel.BRIGHT_LIGHT

darkness_event = Darkness(
    source_entity_uuid=dark_caster.uuid,
    end_position=(11, 10),
    template=False,
).apply()

center_tile = get_map().get_tile(11, 10)
assert center_tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS
assert center_tile.blocks_vision(light_caster.uuid)
assert (
    center_tile.get_effective_light_for(
        darkvision_observer.uuid,
        observer_position=darkvision_observer.position,
    )
    == LightLevel.MAGICAL_DARKNESS
)

daylight_event = Daylight(
    source_entity_uuid=light_caster.uuid,
    end_position=(11, 10),
    template=False,
).apply()

assert "Darkness Zone" not in dark_caster.active_conditions
assert "Concentrating" not in dark_caster.active_conditions
assert center_tile.resolved_light_level == LightLevel.VERY_BRIGHT
```

SRD relationship: Fog Cloud's radius upcast and heavy obscurement are modeled as
tile light/obscurement. Darkness blocks darkvision through magical darkness.
Daylight now dispels overlapping Darkness zones from the current engine spell.
Object anchoring, covering/uncovering an object source, wind dispersal, and the
mirror Darkness-dispels-lower-level-light clause remain outside this executable
example.

Example EB-15-027 covers damage-zone terrain, obscurement, upcast dice, and
moving light/obscurement cleanup. Insect Plague now follows the SRD area clauses
by applying difficult terrain and light obscurement in addition to piercing
damage. Incendiary Cloud applies heavy obscurement and moves its zone at the
caster's turn start, removing light modifiers from tiles that leave the cloud
and applying them to newly covered tiles:

```python
with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    plague_event = InsectPlague(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        cast_at_level=7,
        template=False,
    ).apply()

plague_zone = caster.active_conditions["Insect Plague Zone"]
plague_center_tile = get_map().get_tile(10, 5)

assert plague_zone.adds_difficult_terrain
assert plague_zone.sets_light_level == LightLevel.DIM_LIGHT
assert plague_center_tile.walking_cost.normalized_score == 2
assert plague_center_tile.resolved_light_level == LightLevel.DIM_LIGHT
assert target_hp_before - get_hp(target) == 18

caster.remove_condition("Concentrating")
assert plague_center_tile.walking_cost.normalized_score == 1
assert plague_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    cloud_event = IncendiaryCloud(
        source_entity_uuid=caster.uuid,
        end_position=(10, 10),
        template=False,
    ).apply()

cloud_zone = caster.active_conditions["Incendiary Cloud Zone"]
old_center = cloud_zone.zone_center
old_trailing_tile = get_map().get_tile(6, 10)

assert cloud_zone.sets_light_level == LightLevel.DARKNESS
assert old_trailing_tile.resolved_light_level == LightLevel.DARKNESS
assert target_hp_before - get_hp(target) == 30

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    caster.on_turn_start(round_number=1, turn_index=0)

new_center = cloud_zone.zone_center
new_leading_tile = get_map().get_tile(16, 10)

assert new_center != old_center
assert old_trailing_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
assert new_leading_tile.resolved_light_level == LightLevel.DARKNESS
```

SRD relationship: Insect Plague's upcast damage, difficult terrain, and lightly
obscured area are modeled. Incendiary Cloud's heavy obscurement, fire damage,
and automatic movement are modeled. Wind dispersal and the exact SRD
"enters for the first time on a turn or ends its turn there" timing remain
future edge-work for the wider zone matrix.

Example EB-15-028 covers gas and ice zone turn-start edges. Stinking Cloud uses
heavy obscurement, does not create difficult terrain, applies its failed-save
effect at turn start rather than on entry, spends only the target's action, and
lets poison-immune creatures automatically avoid nausea. Sleet Storm uses a
cylinder footprint, so its area is not wall-shadowed like a sphere; it applies
difficult terrain and heavy obscurement, knocks creatures prone on failed
Dexterity saves, and uses the caster's spell save DC for concentration
disruption:

```python
with patch("dnd.core.dice.random.randint", return_value=10):
    cloud_event = StinkingCloud(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),
        template=False,
    ).apply()

cloud_zone = caster.active_conditions["Stinking Cloud Zone"]
assert not cloud_zone.adds_difficult_terrain
assert cloud_zone.sets_light_level == LightLevel.DARKNESS
assert "Nauseated" not in retching_target.active_conditions

retching_target.on_turn_start(round_number=1, turn_index=0)
assert "Nauseated" in retching_target.active_conditions
assert retching_target.action_economy.actions.normalized_score == 0
assert retching_target.action_economy.bonus_actions.normalized_score == 1
assert retching_target.action_economy.reactions.normalized_score == 1

immune_target.on_turn_start(round_number=1, turn_index=1)
assert "Nauseated" not in immune_target.active_conditions

with patch("dnd.core.dice.random.randint", return_value=10):
    storm_event = SleetStorm(
        source_entity_uuid=caster.uuid,
        end_position=(10, 10),
        template=False,
    ).apply()

storm_zone = caster.active_conditions["Sleet Storm Zone"]
assert storm_zone.zone_shape == "cylinder"
assert concentrating_target.position in storm_zone.affected_positions
assert "Prone" in concentrating_target.active_conditions

concentrating_target.add_condition(
    Concentrating(
        source_entity_uuid=concentrating_target.uuid,
        target_entity_uuid=concentrating_target.uuid,
        spell_name="Book Probe",
    )
)
with patch("dnd.core.dice.random.randint", return_value=12):
    concentrating_target.on_turn_start(round_number=1, turn_index=0)
assert "Concentrating" not in concentrating_target.active_conditions
```

SRD relationship: Stinking Cloud's range, concentration, heavy obscurement,
turn-start Constitution save, action-spend effect, poison-immunity automatic
success, breathless-creature automatic success, and wind dispersal timing are
modeled. Sleet Storm's range, concentration, cylinder footprint, heavy
obscurement, difficult terrain, prone save, concentration disruption against
the caster's spell DC, and exposed flame dousing are modeled.

Example EB-15-041 isolates the breathless-creature clause. The entity trait is
`requires_breathing`; Stinking Cloud skips the saving throw and nausea effect
when that trait is false:

```python
breathless_target = create_family_target(
    name="Breathless Target",
    position=(10, 6),
    requires_breathing=False,
)
penalize_save(breathless_target, "constitution")

cloud_event = StinkingCloud(
    source_entity_uuid=caster.uuid,
    end_position=(10, 5),
    template=False,
).apply()

saving_throw_count = len(EventQueue.get_events_by_type(EventType.SAVING_THROW))
breathless_target.on_turn_start(round_number=1, turn_index=1)

assert "Nauseated" not in breathless_target.active_conditions
assert breathless_target.action_economy.actions.normalized_score == 1
assert len(EventQueue.get_events_by_type(EventType.SAVING_THROW)) == saving_throw_count
```

SRD relationship: `interactive_ruleset/Spells/Stinking Cloud.md` excludes
creatures that do not need to breathe or are immune to poison from the saving
throw/effect. The engine models the breathing half through `Entity.requires_breathing`.

Parity test: `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_041_stinking_cloud_skips_breathless_creatures`.

Example EB-15-044 covers Stinking Cloud's wind dispersal clause with the shared
environmental wind primitive. `WindExposureEvent` carries affected positions
and a wind speed in miles per hour. Stinking Cloud consumes that event and
starts the SRD countdown: moderate wind at 10 mph disperses the cloud after
four cloud-caster turn starts, while strong wind at 20 mph disperses it after
one. The existing `GustOfWindZone` emits a 20 mph wind exposure from its line:

```python
moderate_wind = WindExposureEvent(
    source_entity_uuid=caster.uuid,
    positions={(10, 5)},
    wind_speed_mph=10,
    source_description="Book moderate wind",
    phase=EventPhase.DECLARATION,
)
moderate_wind = moderate_wind.phase_to(EventPhase.EFFECT)
moderate_wind = moderate_wind.phase_to(EventPhase.COMPLETION)

for round_number in range(1, 4):
    caster.on_turn_start(round_number=round_number, turn_index=0)
    assert "Stinking Cloud Zone" in caster.active_conditions

caster.on_turn_start(round_number=4, turn_index=0)
assert "Stinking Cloud Zone" not in caster.active_conditions
assert "Concentrating" not in caster.active_conditions

gust_zone = GustOfWindZone(
    source_entity_uuid=wind_caster.uuid,
    target_entity_uuid=wind_caster.uuid,
    zone_center=wind_caster.position,
    zone_direction=(1, 0),
    caster_position=wind_caster.position,
    spell_dc=wind_caster.spell_save_dc(),
)
wind_caster.add_condition(gust_zone)

assert (8, 5) in gust_zone.affected_positions
cloud_caster.on_turn_start(round_number=1, turn_index=0)
assert "Stinking Cloud Zone" not in cloud_caster.active_conditions
```

SRD relationship: `interactive_ruleset/Spells/Stinking Cloud.md` says a
moderate wind of at least 10 mph disperses the cloud after 4 rounds, and a
strong wind of at least 20 mph disperses it after 1 round. The engine models
those thresholds through `WindExposureEvent.gas_dispersal_rounds()` and the
cloud caster's turn-start cadence.

Parity test: `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_044_stinking_cloud_wind_dispersal_uses_srd_rounds`.

Example EB-15-043 covers Sleet Storm's exposed-flame clause through the item
contract. `BaseItem.is_exposed_flame()` and
`BaseItem.douse_exposed_flame()` are no-ops by default; `Torch` and
`WallTorch` override them. Lighting a flame emits `ExposedFlameEvent` after the
item has stored its light-source UUID, so active Sleet Storm zones can douse it
without leaking the new light source:

```python
carried_torch = create_torch(torchbearer.uuid)
torchbearer.loot_item(carried_torch)
carried_torch.ignite(torchbearer.uuid)
wall_torch = create_wall_torch(position=(10, 6), owner_uuid=uuid4(), lit=True)
outside_torch = create_wall_torch(position=(1, 1), owner_uuid=uuid4(), lit=True)

storm_event = SleetStorm(
    source_entity_uuid=caster.uuid,
    end_position=(10, 5),
    template=False,
).apply()

storm_zone = caster.active_conditions["Sleet Storm Zone"]
assert torchbearer.position in storm_zone.affected_positions
assert (10, 6) in storm_zone.affected_positions
assert carried_torch.is_lit is False
assert carried_torch._light_source_uuid is None
assert wall_torch.is_lit is False
assert wall_torch._light_source_uuid is None
assert outside_torch.is_lit is True

carried_torch.ignite(torchbearer.uuid)
assert carried_torch.is_lit is False
assert carried_torch._light_source_uuid is None

wall_torch.light()
assert wall_torch.is_lit is False
assert wall_torch._light_source_uuid is None
```

SRD relationship: `interactive_ruleset/Spells/Sleet Storm.md` says exposed
flames in the area are doused. The engine models this for exposed carried
torches and placed wall torches at initial storm creation and when those flames
are lit inside an active storm.

Parity test: `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_043_sleet_storm_douses_exposed_flames`.

Example EB-15-029 returns to Web and tightens the SRD relationship for the zone
itself. The current 2D grid model treats Web casts on existing map tiles as
floor-layered, so the zone remains active at the caster's next turn start.
The example also proves Web now applies light obscurement through the standard
tile-light modifier path and cleans up the granted escape action when the
target breaks free:

```python
with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    web_event = Web(
        source_entity_uuid=caster.uuid,
        end_position=(5, 5),
        template=False,
    ).apply()

web_zone = caster.active_conditions["Web Zone"]
web_center_tile = get_map().get_tile(5, 5)

assert web_zone.zone_shape == "cube"
assert web_zone.adds_difficult_terrain
assert web_zone.sets_light_level == LightLevel.DIM_LIGHT
assert web_zone.light_is_obscurement
assert web_center_tile.walking_cost.normalized_score == 2
assert web_center_tile.resolved_light_level == LightLevel.DIM_LIGHT
assert "Web Restrained" in target.active_conditions
assert "Restrained" in target.active_conditions

caster.on_turn_start(round_number=1, turn_index=0)
assert "Web Zone" in caster.active_conditions

escape = next(action for action in target.registered_actions if action.name == "Escape Web").instantiate()
with patch("dnd.core.dice.random.randint", return_value=10):
    escape_event = escape.apply()

assert "Web Restrained" not in target.active_conditions
assert "Restrained" not in target.active_conditions
assert all(action.name != "Escape Web" for action in target.registered_actions)

caster.remove_condition("Concentrating")
assert web_center_tile.walking_cost.normalized_score == 1
assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
```

Example EB-15-037 covers the SRD collapse branch for webs that are not anchored
or layered across a surface. The default cast remains floor-layered, but an
explicit `anchored_or_layered=False` cast registers one extra condition-owned
turn-start handler. At the caster's next turn start, that handler removes the
zone by condition UUID, which also removes the final concentration child through
the existing linked-condition cleanup policy:

```python
web_event = Web(
    source_entity_uuid=caster.uuid,
    end_position=(5, 5),
    anchored_or_layered=False,
    template=False,
).apply()

web_zone = caster.active_conditions["Web Zone"]
assert not web_zone.anchored_or_layered
assert len(web_zone.event_handlers_uuids) == 3
assert "Concentrating" in caster.active_conditions
assert web_center_tile.walking_cost.normalized_score == 2
assert web_center_tile.resolved_light_level == LightLevel.DIM_LIGHT

caster.on_turn_start(round_number=2, turn_index=0)

assert "Web Zone" not in caster.active_conditions
assert "Concentrating" not in caster.active_conditions
assert web_center_tile.walking_cost.normalized_score == 1
assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
```

Example EB-15-042 adds the flammable-Web clause through a bottom-level
environmental event. `FireExposureEvent` says only that a grid position was
exposed to fire; `WebZone` owns the SRD consequences for its own cubes. The
exposed 5-foot cube leaves the Web zone, loses difficult terrain and
obscurement, removes the tile marker, frees creatures restrained by that Web,
and becomes a one-round burning cube that deals 2d4 fire to creatures starting
their turn there:

```python
fire_event = FireExposureEvent(
    source_entity_uuid=caster.uuid,
    position=(5, 5),
    phase=EventPhase.DECLARATION,
)
fire_event = fire_event.phase_to(EventPhase.EFFECT)
fire_event = fire_event.phase_to(EventPhase.COMPLETION)

assert (5, 5) not in web_zone.affected_positions
assert (6, 5) in web_zone.affected_positions
assert len(web_zone.event_handlers_uuids) == 3
assert web_center_tile.walking_cost.normalized_score == 1
assert web_center_tile.resolved_light_level == LightLevel.BRIGHT_LIGHT
assert "Web" not in web_center_tile.active_conditions
assert "Web Restrained" not in target.active_conditions
assert "Restrained" not in target.active_conditions

hp_before_fire = get_hp(target)
with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    target.on_turn_start(round_number=1, turn_index=0)

hp_after_fire = get_hp(target)
assert hp_before_fire - hp_after_fire == 6

with patch("dnd.core.dice.random.randint", side_effect=fixed_zone_randint):
    caster.on_turn_start(round_number=1, turn_index=1)
    target.on_turn_start(round_number=2, turn_index=0)

assert get_hp(target) == hp_after_fire
assert "Web Zone" in caster.active_conditions
```

SRD relationship: Web's range, concentration, cube footprint, difficult
terrain, light obscurement, start/entry Dexterity saves, restrained condition,
Strength-check escape, default floor-layered persistence, and explicit
unanchored collapse at the caster's next turn start are modeled. Web also
responds to `FireExposureEvent` by burning away the exposed cube for one round
and dealing the SRD 2d4 fire damage to creatures that start their turn in that
burning cube.

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_021_zone_spell_family_entry_turn_start_and_cleanup_edges`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_026_light_zone_spells_apply_obscurement_and_dispel_darkness`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_027_damage_zones_cover_upcast_obscurement_and_movement`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_028_gas_and_ice_zones_match_srd_turn_start_edges`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_029_web_models_obscurement_grounding_and_escape_cleanup`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_037_web_unanchored_cast_collapses_on_caster_turn_start`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_042_web_fire_exposure_burns_one_cube_for_one_round`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Transmutation Modifier Bundles

`Haste` and `Slow` are representative large modifier-bundle spells. They are
useful book examples because they touch several engine layers at once:

- entity action economy values;
- AC and saving throw `ModifiableValue`s;
- event handlers registered by conditions;
- concentration-linked cleanup;
- SRD-style secondary effects when a spell ends.

`Haste` applies a `Haste` condition to the target, links that condition to the
caster's `Concentrating` condition, doubles movement by adding the target's base
speed as a modifier, adds +2 AC, grants advantage on Dexterity saves, and adds
one action. When the condition is removed normally, it applies one round of
`Incapacitated` lethargy.

Example EB-15-011:

```python
event = Haste(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    template=False,
).apply()

assert "Haste" in target.active_conditions
assert "Concentrating" in caster.active_conditions
assert target.action_economy.movement.normalized_score == base_speed * 2
assert target.equipment.ac_bonus.normalized_score == base_ac_bonus + 2
assert target.action_economy.actions.normalized_score == base_actions + 1

caster.remove_condition("Concentrating")

assert "Haste" not in target.active_conditions
assert "Incapacitated" in target.active_conditions
assert target.action_economy.actions.normalized_score == 0
```

`Slow` is a position AoE concentration spell. Each target that fails its Wisdom
save receives its own `Slowed` condition. The condition halves base movement,
applies -2 AC, applies -2 to Dexterity saves, caps reactions at 0, and registers
handlers for action/bonus-action lockout, Extra Attack suppression, turn-start
lockout reset, and repeat Wisdom saves.

Example EB-15-012:

```python
penalize_save(target_one, "wisdom")
penalize_save(target_two, "wisdom")

event = Slow(
    source_entity_uuid=caster.uuid,
    end_position=(3, 1),
    template=False,
).apply()

assert "Slowed" in target_one.active_conditions
assert "Slowed" in target_two.active_conditions
assert target_one.action_economy.movement.normalized_score == base_speed // 2
assert target_one.equipment.ac_bonus.normalized_score == base_ac_bonus - 2
assert target_one.action_economy.reactions.normalized_score == 0

caster.remove_condition("Concentrating")

assert "Slowed" not in target_one.active_conditions
assert target_one.action_economy.movement.normalized_score == base_speed
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_011_haste_modifier_bundle_and_lethargy_cleanup`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_012_slow_multi_target_modifier_bundle_and_cleanup`
- `tests/engine_book/test_chapter_15_spell_families.py`

## HP-Pool Targeting

`Sleep` and `ColorSpray` are area spells, but they do not simply affect every
entity in their computed shape. Each spell builds its shape, gathers affected
entity UUIDs from the map, filters invalid candidates, sorts the remaining
candidates by current hit points, then spends a rolled HP pool from lowest HP
to highest HP.

This is a useful family because it sits between targeting, SRD spell text,
condition application, and action validation. The implementation includes more
rules than the executable excerpt proves; EB-15 pins ordering, skip, cache,
exact-pool, and cleanup behavior, while upcast and additional immunity matrices
remain backlog work.

- `Sleep` uses a 20-foot sphere at 90-foot range, skips undead in the example,
  and applies a `Sleep` condition with `Unconscious` as a sub-condition. Its
  wake handler listens for `TAKE_DAMAGE` at `EFFECT` and removes the parent
  `Sleep` condition, which also removes the sub-condition.
- `ColorSpray` uses a self-originating 15-foot cone, skips an already-blinded
  target in the example, and applies a `Color Spray` condition with `Blinded` as
  a sub-condition.

Example EB-15-013 proves the direct Sleep selector and the wake-on-damage
condition handler:

```python
selector = Sleep(
    source_entity_uuid=caster.uuid,
    end_position=(5, 3),
    template=False,
)
selector.hp_pool_rolled = 16
selector.hp_pool_remaining = 16

targets = selector.get_all_targets()

assert low.uuid in targets
assert mid.uuid in targets
assert high.uuid not in targets
assert undead.uuid not in targets
assert selector.hp_pool_remaining == 1

repeated_targets = selector.get_all_targets()
assert repeated_targets == targets
assert selector.hp_pool_remaining == 1

sleep = Sleep(
    source_entity_uuid=caster.uuid,
    end_position=(5, 3),
    template=False,
)
sleep.hp_pool_rolled = 5
sleep.hp_pool_remaining = 5

event = sleep.apply()

assert "Sleep" in low.active_conditions
assert "Unconscious" in low.active_conditions
assert sleep.hp_pool_remaining == 0

deal_damage_to(low, 1, source_uuid=caster.uuid)

assert "Sleep" not in low.active_conditions
assert "Unconscious" not in low.active_conditions
```

Example EB-15-014 proves the Color Spray cone selector, already-blinded skip,
condition tree application, and parent cleanup:

```python
selector = ColorSpray(
    source_entity_uuid=caster.uuid,
    end_position=(10, 5),
    template=False,
)
selector.hp_pool_rolled = 10
selector.hp_pool_remaining = 10

targets = selector.get_all_targets()

assert already_blinded.uuid not in targets
assert low.uuid in targets
assert high.uuid not in targets
assert selector.hp_pool_remaining == 2

repeated_targets = selector.get_all_targets()
assert repeated_targets == targets
assert selector.hp_pool_remaining == 2

color_spray = ColorSpray(
    source_entity_uuid=caster.uuid,
    end_position=(10, 5),
    template=False,
)
color_spray.hp_pool_rolled = 8
color_spray.hp_pool_remaining = 8

event = color_spray.apply()

assert "Color Spray" in low.active_conditions
assert "Blinded" in low.active_conditions
assert color_spray.hp_pool_remaining == 0

low.remove_condition("Color Spray")

assert "Blinded" not in low.active_conditions
```

Implementation note: `Sleep` and `ColorSpray` cache their selected HP-pool
target UUIDs on the spell instance. This keeps the selection stable when the
shared `BaseAction.apply()` pipeline asks for targets during validation and
again during convolution. The cache also makes exact-pool application work:
after validation spends a 5 HP Sleep pool on a 5 HP creature, application still
uses the same selected target instead of spending the pool a second time.

Example EB-15-030 expands the HP-pool matrix to upcasting and invalid-target
filters. Sleep at 3rd level rolls `9d8`, ignores unconscious creatures, undead,
and creatures immune to being charmed, then spends the pool only on valid
targets. Color Spray at 3rd level rolls `10d10`, ignores unconscious creatures,
already-blinded creatures, sightless creatures, and creatures immune to
`Blinded`, then spends its pool in current-HP order:

```python
sleep_selector = Sleep(
    source_entity_uuid=caster.uuid,
    end_position=(5, 3),
    cast_at_level=3,
    template=False,
)
assert sleep_selector.get_hp_pool_dice() == (9, 8)
sleep_selector.hp_pool_rolled = 20
sleep_selector.hp_pool_remaining = 20

sleep_targets = sleep_selector.get_all_targets()

assert unconscious.uuid not in sleep_targets
assert undead.uuid not in sleep_targets
assert charmed_immune.uuid not in sleep_targets
assert valid_sleep.uuid in sleep_targets
assert sleep_selector.hp_pool_remaining == 15

spray_sightless.has_ordinary_sight = False

color_selector = ColorSpray(
    source_entity_uuid=caster.uuid,
    end_position=(10, 7),
    cast_at_level=3,
    template=False,
)
assert color_selector.get_hp_pool_dice() == (10, 10)
color_selector.hp_pool_rolled = 20
color_selector.hp_pool_remaining = 20

color_targets = color_selector.get_all_targets()

assert spray_unconscious.uuid not in color_targets
assert spray_blinded.uuid not in color_targets
assert spray_immune.uuid not in color_targets
assert spray_sightless.uuid not in color_targets
assert spray_valid.uuid in color_targets
assert color_selector.hp_pool_remaining == 15
```

SRD relationship: Sleep's HP pool, upcast dice, lowest-current-HP ordering,
unconscious skip, undead immunity, and charmed-immunity skip are modeled.
Color Spray's cone, HP pool, upcast dice, lowest-current-HP ordering,
unconscious skip, already-blinded skip, condition-immunity skip, and
cannot-see skip are modeled. The cannot-see skip uses
`Entity.can_see_visual_effects()`, which preserves ordinary sight by default
while allowing sightless creatures to be represented explicitly.

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_013_sleep_hp_pool_selection_immunity_and_wake_on_damage`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_014_color_spray_hp_pool_skips_and_blinded_cleanup`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_030_hp_pool_spells_cover_upcast_and_immunity_edges`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Utility: Teleport And Senses

`SeeInvisibility` applies a non-concentration condition that adds a
`SEE_INVISIBLE` sense mode and notifies perceivability changes.

`MistyStep` is a bonus-action teleport spell. It validates that the destination
is visible, unoccupied, walkable, and within 30 feet, then moves the caster
directly through the entity/grid position API.

Example EB-15-007:

```python
see_event = SeeInvisibility(
    source_entity_uuid=caster.uuid,
    template=False,
).apply()

assert "See Invisibility" in caster.active_conditions
assert any(mode.sense_type == SensesType.SEE_INVISIBLE for mode in caster.senses.sense_modes)

misty_event = MistyStep(
    source_entity_uuid=caster.uuid,
    end_position=(4, 1),
    template=False,
).apply()

assert caster.position == (4, 1)
assert caster.action_economy.bonus_actions.normalized_score == 0
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_007_mobility_and_sense_utility_spells_change_state`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Defensive Illusion State

`MirrorImage` is implemented as a BG3-style defensive illusion, not as the SRD
tabletop targeting-redirection procedure. The spell applies a non-concentration
`Mirror Image` condition to the caster. That condition starts with three
duplicates, adds +9 to the caster's AC bonus, and registers an attack handler.

When an attack against the caster reaches `ATTACK` `EFFECT` phase with a miss
or critical miss outcome, the handler removes one duplicate and rewrites the AC
modifier to `remaining_duplicates * 3`. When the last duplicate is consumed,
normal condition cleanup removes the handler and AC modifier. A hit does not
consume a duplicate.

Example EB-15-019:

```python
event = MirrorImage(
    source_entity_uuid=caster.uuid,
    template=False,
).apply()

assert "Mirror Image" in caster.active_conditions
assert "Concentrating" not in caster.active_conditions
mirror = caster.active_conditions["Mirror Image"]
assert mirror.duplicates == 3
assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 9

miss_mod = force_attack_miss(attacker)
for expected_duplicates in (2, 1, 0):
    attacker.action_economy.reset_all_costs()
    attack_event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=caster.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

    assert attack_event.attack_outcome in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS)
    if expected_duplicates > 0:
        mirror = caster.active_conditions["Mirror Image"]
        assert mirror.duplicates == expected_duplicates
        assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + expected_duplicates * 3
    else:
        assert "Mirror Image" not in caster.active_conditions
        assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus

remove_attack_modifier(attacker, miss_mod)

caster.action_economy.reset_all_costs()
event = MirrorImage(
    source_entity_uuid=caster.uuid,
    template=False,
).apply()

hit_mod = force_attack_hit(attacker)
hp_before = get_hp(caster)
attacker.action_economy.reset_all_costs()
hit_event = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=caster.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
).apply()

assert hit_event.attack_outcome not in (AttackOutcome.MISS, AttackOutcome.CRIT_MISS)
assert get_hp(caster) < hp_before
mirror = caster.active_conditions["Mirror Image"]
assert mirror.duplicates == 3
assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 9
assert caster.action_economy.spell_slot_2.normalized_score == 0
remove_attack_modifier(attacker, hit_mod)
```

Example EB-15-035 covers recasting and duration. Recasting while a partially
depleted `Mirror Image` is active replaces the old condition by name, so the
new condition returns to three duplicates and +9 AC while keeping only one
evade handler. Advancing the condition duration ten times expires it and
restores AC:

```python
mirror = caster.active_conditions["Mirror Image"]
assert mirror.duplicates == 3
assert mirror.duration.duration_type == DurationType.ROUNDS
assert mirror.duration.duration == 10
assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 9
assert len(caster.get_event_handlers_by_name("Mirror Image: Evade")) == 1

miss_mod = force_attack_miss(attacker)
attacker.action_economy.reset_all_costs()
Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=caster.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
).apply()

mirror = caster.active_conditions["Mirror Image"]
assert mirror.duplicates == 2
assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 6

caster.action_economy.reset_all_costs()
MirrorImage(source_entity_uuid=caster.uuid, template=False).apply()

mirror = caster.active_conditions["Mirror Image"]
assert mirror.duplicates == 3
assert mirror.duration.duration == 10
assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus + 9
assert len(caster.get_event_handlers_by_name("Mirror Image: Evade")) == 1

for _ in range(9):
    assert not caster.advance_duration("Mirror Image")
    assert "Mirror Image" in caster.active_conditions

assert caster.advance_duration("Mirror Image")
assert "Mirror Image" not in caster.active_conditions
assert caster.equipment.ac_bonus.normalized_score == base_ac_bonus
assert len(caster.get_event_handlers_by_name("Mirror Image: Evade")) == 0
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_019_mirror_image_duplicates_absorb_missed_attacks`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_035_mirror_image_recast_replaces_and_duration_expires`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Illusion And Necromancy Self Effects

`FalseLife` is a necromancy self spell that grants temporary hit points through
the `Health` block. The temporary HP channel is a modifiable value; stronger
temporary HP replaces weaker temporary HP instead of stacking.

`Invisibility` is an illusion concentration spell that applies the standard
`Invisible` condition implemented by `InvisibilityEffect`. That effect sets the
entity's invisibility flag, adds unseen attacker/target modifiers, and registers
reveal handlers for attacks, spell casts, and revealing actions.

Example EB-15-008:

```python
false_life_event = FalseLife(
    source_entity_uuid=caster.uuid,
    template=False,
).apply()

assert caster.health.temporary_hit_points.normalized_score > 0

invisible_event = Invisibility(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=caster.uuid,
    template=False,
).apply()

assert "Invisible" in caster.active_conditions
assert caster.is_invisible
assert "Concentrating" in caster.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_008_illusion_and_necromancy_self_effects`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Eyebite Granted Action Lifecycle

`Eyebite` is a self-range concentration spell that grants the caster an
`Eyebite Strike` action template. The spell can immediately resolve one target
by creating a one-shot strike with no action cost; later turns use the
registered template, which spends the caster's action. Each failed strike links
the applied option condition to `Concentrating`, and the action marker is linked
to the same concentration tree so ending concentration removes both lingering
effects and the granted template.

Example EB-15-031 covers the Sickened option because it exposes the lowest-level
repeat-save contract. The initial strike applies `Sickened`; a second strike is
instantiated from the granted template and consumes the action. At the second
target's turn end, a boosted Wisdom save removes Sickened even while a penalized
Constitution save would fail, matching the local SRD text for Eyebite's
Sickened option.

```python
event = Eyebite(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=first.uuid,
    effect_choice="sickened",
    template=False,
    costs=[],
).apply()

assert "Concentrating" in caster.active_conditions
assert "Sickened" in first.active_conditions

strike_template = caster.get_action_template("Eyebite Strike")
repeat_event = strike_template.instantiate(target_entity_uuid=second.uuid).apply()

assert "Sickened" in second.active_conditions
assert caster.action_economy.actions.normalized_score == 0

boost_save(second, "wisdom", value=200)
penalize_save(second, "constitution", value=-200)
second.on_turn_end()

assert "Sickened" not in second.active_conditions

caster.remove_condition("Concentrating")

assert "Sickened" not in first.active_conditions
assert caster.get_action_template("Eyebite Strike") is None
```

Example EB-15-032 adds two targeting rules from the same SRD paragraph. The
caster's `Eyebite Casting` state records any creature that succeeds against
this casting. Later `Eyebite Strike` instances reject those UUIDs before costs
are applied, while fresh visible targets can still be struck. The repeat strike
also requires the target to be in `caster.senses.entities`, so an unseen or
currently imperceivable target cannot be chosen by direct execution.

```python
event = Eyebite(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=saved.uuid,
    effect_choice="sickened",
    template=False,
    costs=[],
).apply()

assert "Sickened" not in saved.active_conditions

retarget_event = strike_template.instantiate(target_entity_uuid=saved.uuid).apply()

assert retarget_event.canceled
assert caster.action_economy.actions.normalized_score == 1

fresh_event = strike_template.instantiate(target_entity_uuid=vulnerable.uuid).apply()

assert "Sickened" in vulnerable.active_conditions
assert caster.action_economy.actions.normalized_score == 0

unseen.set_invisible(True)
Entity.update_all_entities_senses(max_distance=80)
assert unseen.uuid not in caster.senses.entities

unseen_event = unseen_strike.instantiate(target_entity_uuid=unseen.uuid).apply()

assert unseen_event.canceled
assert "Sickened" not in unseen.active_conditions
```

Example EB-15-033 shares the wake-by-action SRD clause between `Sleep` and
Eyebite's Asleep option. `setup_standard_actions()` registers `Shake Awake` as
a normal entity-targeted action, but discovery only exposes it when an adjacent
target is affected by magical sleep. Applying it removes the parent sleep
condition, which also cleans up the `Unconscious` subcondition, and spends the
helper's action.

```python
setup_standard_actions(helper)

sleep_event = Sleep(
    source_entity_uuid=caster.uuid,
    end_position=sleeper.position,
    template=False,
).apply()

assert "Sleep" in sleeper.active_conditions
assert "Unconscious" in sleeper.active_conditions

available = helper.get_available_actions()
shake_targets = [
    target.target_uuid
    for action in available.entity_actions
    if action.template_name == "Shake Awake"
    for target in action.valid_targets
]

assert shake_targets == [sleeper.uuid]

shake_event = helper.get_action_template("Shake Awake").instantiate(
    target_entity_uuid=sleeper.uuid,
).apply()

assert not shake_event.canceled
assert "Sleep" not in sleeper.active_conditions
assert "Unconscious" not in sleeper.active_conditions
assert helper.action_economy.actions.normalized_score == 0

helper.action_economy.reset_all_costs()

eyebite_event = Eyebite(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=eyebite_sleeper.uuid,
    effect_choice="asleep",
    template=False,
    costs=[],
).apply()

assert "Eyebite Asleep" in eyebite_sleeper.active_conditions
assert "Unconscious" in eyebite_sleeper.active_conditions

eyebite_shake_event = helper.get_action_template("Shake Awake").instantiate(
    target_entity_uuid=eyebite_sleeper.uuid,
).apply()

assert not eyebite_shake_event.canceled
assert "Eyebite Asleep" not in eyebite_sleeper.active_conditions
assert "Unconscious" not in eyebite_sleeper.active_conditions
```

Example EB-15-034 covers the Panicked option. Unlike Sickened, Panicked does
not repeat a Wisdom save at turn end. On the target's turn, the condition
spends the target's action on Dash, moves it away from the caster through the
selected flee route, and then checks the SRD ending clause: the effect ends
only when the target is at least 60 feet away and can no longer see the caster.

```python
event = Eyebite(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=target.uuid,
    effect_choice="panicked",
    template=False,
    costs=[],
).apply()

assert "Eyebite Panicked" in target.active_conditions
assert "Frightened" in target.active_conditions

boost_save(target, "wisdom", value=200)
target.on_turn_end()

assert "Eyebite Panicked" in target.active_conditions

start_distance = caster.senses.get_feet_distance(target.position)
target.on_turn_start(round_number=1, turn_index=0)
Entity.update_all_entities_senses(max_distance=80)
moved_distance = caster.senses.get_feet_distance(target.position)

assert moved_distance > start_distance
assert target.action_economy.actions.normalized_score == 0
assert caster.uuid in target.senses.entities
assert "Eyebite Panicked" in target.active_conditions

caster.set_invisible(True)
target.on_turn_start(round_number=2, turn_index=0)
Entity.update_all_entities_senses(max_distance=80)

assert caster.uuid not in target.senses.entities
assert caster.senses.get_feet_distance(target.position) >= 60
assert "Eyebite Panicked" not in target.active_conditions
assert "Frightened" not in target.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_031_eyebite_granted_action_lifecycle_and_repeat_save`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_032_eyebite_blocks_successful_retargets_and_unseen_targets`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_033_shake_awake_action_ends_sleep_and_eyebite_asleep`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_034_eyebite_panicked_forces_dash_movement_and_distance_cleanup`
- `tests/engine_book/test_chapter_15_spell_families.py`

## Documentation Hygiene Notes

Chapter 15 spell-school hygiene is complete across the current
`dnd/spells/*.py` school files. The completed full-file passes normalized
every implemented school file:

- `dnd/spells/divination.py`;
- `dnd/spells/illusion.py`;
- `dnd/spells/necromancy.py`;
- `dnd/spells/enchantment.py`;
- `dnd/spells/transmutation.py`;
- `dnd/spells/abjuration.py`;
- `dnd/spells/conjuration.py`;
- `dnd/spells/evocation.py`.

Across those files:

- zero standalone comments and zero inline comment markers;
- descriptions on all Pydantic `Field(...)` declarations;
- no plain annotated public Pydantic fields without `Field(...)`;
- Google-style docstrings on spell/effect application helpers;
- behavior preservation checks are itemized by school below.

The necromancy pass now covers the full file:

- `FalseLife`, `NoHealing`, `ChillTouchEffect`, `ChillTouch`, `Blight`,
  `BlindnessDeafnessEffect`, `BlindnessDeafness`, `NecroticBless`,
  `SickenedCondition`, `EyebiteAsleepEffect`, `EyebitePanickedEffect`,
  `EyebiteCastingState`, `EyebiteStrike`, `Eyebite`, `FingerOfDeath`,
  `InflictWounds`, `Harm`, `AbilityCurseEffect`, `AttackCurseEffect`,
  `InactionCurseEffect`, `DamageCurseEffect`, and `BestowCurse` now have
  described Pydantic fields and no plain annotated public Pydantic fields;
- comments in the file were removed or folded into docstrings;
- `FalseLife`, `ChillTouch`, `Blight`, `BlindnessDeafness`, and
  `NecroticBless` behavior was rechecked through the legacy examples;
- `Eyebite` behavior was rechecked through the existing spell-batch example,
  EB-15-031 through EB-15-034, including Sickened, Asleep, Panicked,
  granted-action registration, repeat-action cost consumption, the Sickened
  Wisdom repeat save, successful-save retarget blocking, visible-target
  validation, shared Sleep/Eyebite shake-awake cleanup, Panicked Dash
  movement, Panicked distance/sight cleanup, and concentration cleanup.
- `FingerOfDeath`, `InflictWounds`, `Harm`, and `BestowCurse` behavior was
  rechecked through their existing spell and cleric-batch examples.

The enchantment pass now covers the full file:

- `CharmPerson`, `HoldPersonEffect`, `HoldPerson`, `HoldMonsterEffect`,
  `HoldMonster`, `PowerWordKill`, `TestBless`, `SleepEffect`, `Sleep`,
  `PowerWordStunEffect`, `PowerWordStun`, `BaneEffect`, `BlessEffect`,
  `Bane`, `Bless`, `CommandGrovelEffect`, `CommandHaltEffect`,
  `CommandFleeEffect`, and `Command` now have described Pydantic fields and no
  plain annotated public Pydantic fields;
- comments in the file were removed or folded into docstrings;
- `Bless`, `Bane`, `Sleep`, `HoldPerson`, `HoldMonster`, `PowerWordKill`,
  `PowerWordStun`, `TestBless`, and `Command` behavior was rechecked through
  their existing spell, concentration, cleric, and engine-book examples.

The transmutation pass now covers the full file:

- `SpikeGrowthZone`, `SpikeGrowth`, `SlowedEffect`, `Slow`, `HasteEffect`,
  `Haste`, `DarkvisionEffect`, `DarkvisionSpell`, `Disintegrate`,
  `JumpEffect`, `JumpSpell`, `BonusDash`, `ExpeditiousRetreatEffect`,
  `ExpeditiousRetreat`, `EnhanceAbilityEffect`, `EnhanceAbility`,
  `EnlargeReduceEffect`, `EnlargeReduce`, `TelekinesisRestrain`,
  `TelekinesisMove`, `TelekinesisGrab`, `Telekinesis`, `RegeneratingEffect`,
  and `Regenerate` now have described Pydantic fields and no plain annotated
  public Pydantic fields;
- comments in the file were removed or folded into docstrings;
- `SpikeGrowth`, `Slow`, `Haste`, `DarkvisionSpell`, `Disintegrate`,
  `JumpSpell`, `ExpeditiousRetreat`, `EnhanceAbility`, `EnlargeReduce`,
  `Telekinesis`, and `Regenerate` behavior is rechecked through the existing
  spell, concentration, sense-buff, antimagic, and engine-book examples.

The abjuration pass now covers the full file:

- `ShieldBuff`, `MageArmorCondition`, `MageArmor`,
  `ProtectionFromEnergyEffect`, `ProtectionFromEnergy`, `StoneskinEffect`,
  `Stoneskin`, `GlobeZone`, `GlobeOfInvulnerability`, `BanishedCondition`,
  `Banishment`, `LesserRestoration`, `GreaterRestoration`, `RemoveCurse`,
  `ProtectionFromPoisonEffect`, `ProtectionFromPoison`, `DeathWardEffect`,
  `DeathWard`, `FreedomOfMovementEffect`, `FreedomOfMovement`,
  `ResistanceEffect`, `Resistance`, `ShieldOfFaithEffect`, `ShieldOfFaith`,
  `AidEffect`, `Aid`, `SanctuaryEffect`, `Sanctuary`,
  `BeaconOfHopeEffect`, `BeaconOfHope`, `AntimagicSuppression`,
  `AntimagicFieldZone`, and `AntimagicField` now have described Pydantic fields
  and no plain annotated public Pydantic fields;
- comments in the file were removed or folded into docstrings;
- `Shield`, `MageArmor`, `ProtectionFromEnergy`, `Stoneskin`,
  `GlobeOfInvulnerability`, `Banishment`, restoration spells,
  `ProtectionFromPoison`, `DeathWard`, `FreedomOfMovement`, `Resistance`,
  `ShieldOfFaith`, `Aid`, `Sanctuary`, `BeaconOfHope`, and `AntimagicField`
  behavior is rechecked through the existing spell, cleric, antimagic,
  shield, and engine-book examples.

The conjuration pass now covers the full file:

- `CallLightningStrike`, `CallLightning`, `PoisonSpray`, `AcidSplash`,
  `MistyStep`, `GreaseZone`, `Grease`, `WebRestrained`,
  `EscapeWebAction`, `WebZone`, `Web`, `CloudkillZone`, `Cloudkill`,
  `SpiritGuardiansTriggered`, `SpiritGuardiansSlowed`,
  `SpiritGuardiansZone`, `SpiritGuardians`, `FogCloudZone`, `FogCloud`,
  `DarknessZone`, `Darkness`, `DaylightZone`, `Daylight`,
  `InsectPlagueZone`, `InsectPlague`, `IncendiaryCloudZone`,
  `IncendiaryCloud`, `NauseatedCondition`, `StinkingCloudZone`,
  `StinkingCloud`, `SleetStormZone`, `SleetStorm`, `DimensionDoor`,
  `GuardianWarded`, `GuardianOfFaithObject`, `GuardianOfFaith`,
  `HeroesFeastBuff`, `EatFromFeast`, `HeroesFeastObject`, and
  `HeroesFeast` now have described Pydantic fields and no plain annotated
  public Pydantic fields;
- comments in the file were removed or folded into class and method
  docstrings;
- `CallLightning`, `PoisonSpray`, `AcidSplash`, `MistyStep`, `Grease`,
  `Web`, `Cloudkill`, `SpiritGuardians`, `FogCloud`, `Darkness`,
  `Daylight`, `InsectPlague`, `IncendiaryCloud`, `StinkingCloud`,
  `SleetStorm`, `DimensionDoor`, `GuardianOfFaith`, and `HeroesFeast`
  behavior is rechecked through the existing spell, concentration, lighting,
  cleric, and engine-book examples.

The evocation pass now covers the full file:

- `FireBolt`, `RayOfFrostEffect`, `RayOfFrost`, `SacredFlame`,
  `MagicMissile`, `ScorchingRay`, `Fireball`, `BurningHands`,
  `LightningBolt`, `Thunderwave`, `Shatter`, `CircleOfDeath`,
  `ConeOfCold`, `SunburstBlindedEffect`, `Sunburst`, `ShockingGrasp`,
  `GuidingBoltMarked`, `GuidingBolt`, `EldritchBlast`, `GustOfWindZone`,
  `GustOfWind`, `IceStormTerrain`, `IceStorm`, `SunbeamStrike`,
  `Sunbeam`, `ChainLightning`, `PrismaticRestrained`, `PrismaticSpray`,
  `TrueStrike`, `FlameStrike`, `LightEffect`, `Light`,
  `ContinualFlameObject`, `ContinualFlame`, `CureWounds`, `HealingWord`,
  `PrayerOfHealing`, `MassHealingWord`, `MassCureWounds`, `HealSpell`,
  `MassHeal`, `DivineWordEffect`, and `DivineWord` now have described
  Pydantic fields and no plain annotated public Pydantic fields;
- comments in the file were removed or folded into class and method
  docstrings;
- the former healing `type: ignore` was replaced with an explicit
  `Literal[...]` cast so type checking stays clean without a comment marker;
- `FireBolt`, `RayOfFrost`, `SacredFlame`, `MagicMissile`,
  `ScorchingRay`, `Fireball`, `BurningHands`, `LightningBolt`,
  `Thunderwave`, `Shatter`, `CircleOfDeath`, `ConeOfCold`, `Sunburst`,
  `ShockingGrasp`, `GuidingBolt`, `EldritchBlast`, `GustOfWind`,
  `IceStorm`, `Sunbeam`, `ChainLightning`, `PrismaticSpray`,
  `TrueStrike`, `FlameStrike`, `Light`, `ContinualFlame`, `CureWounds`,
  `HealingWord`, `PrayerOfHealing`, `MassHealingWord`, `MassCureWounds`,
  `HealSpell`, `MassHeal`, and `DivineWord` behavior is rechecked through
  the existing spell-system, VFX/catalog, action override, cleric,
  healing, skeleton, antimagic/globe, and engine-book examples.

## Deep Coverage Backlog

Future Chapter 15 expansions should add per-spell parity rows and stronger
edge tests for:

- Additional once-per-turn matrices;
- `EnhanceAbility` and other large modifier bundles;
- additional `HoldPerson`, `HoldMonster`, and repeat-save control edge cases;
- Additional HP-pool environmental perception matrices;
- additional `Guidance`, `Bless`, and `Bane` attack/save/check edge matrices;
- `SeeInvisibility` and `TrueSeeing` reactive visibility against hidden or
  invisible actors;
- restoration spells preserving unrelated conditions while removing supported
  ones.
