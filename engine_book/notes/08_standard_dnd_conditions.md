# 08. Standard D&D Conditions

## Purpose

This chapter documents the standard condition classes currently implemented in `dnd/conditions.py`. It builds on Chapter 07's condition lifecycle and records the exact modifiers, subconditions, flags, and current SRD gaps for each implemented condition.

The examples are executable in `tests/engine_book/test_chapter_08_standard_conditions.py`.

## Source Files Studied

- `dnd/conditions.py`
- `dnd/core/values.py`
- `dnd/core/modifiers.py`
- `dnd/blocks/skills.py`
- `dnd/entity.py`
- `examples/combat_conditions.py`
- `examples/test_available_actions.py`
- `examples/test_condition_removal_system.py`
- `examples/test_prone_auto_stand.py`
- `examples/test_invisible_targeting.py`
- `examples/test_stealth_system.py`
- `tests/engine_book/test_chapter_08_standard_conditions.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: implemented classes use the SRD condition names and most core roll effects from `interactive_ruleset/Gamemastering/Conditions.md`.
- `Engine extension`: condition effects are expressed as `ModifiableValue` channels, action-economy constraints, perceivability flags, and condition trees.
- `Engine adaptation`: `Incapacitated` also clamps movement and bonus actions.
- `Engine adaptation`: `Frightened` clamps movement to 0 while the frightener is sensed, rather than only blocking movement closer to the source.
- `Engine adaptation`: `Prone` uses BG3-style auto-stand behavior outside the condition class, and incoming attack advantage/disadvantage is distance-contextual.
- `SRD-aligned`: `Exhaustion` is implemented as one condition with a level
  field from 1 to 6 and cumulative effects.
- `SRD-aligned`: entity long rests and revival reduce `Exhaustion` by one level
  through the shared condition level-reduction cleanup path.
- `Current limitation`: `Petrified` implements the engine-expressible roll,
  action, resistance, and poison-immunity effects; weight multiplication,
  aging, awareness, and poison/disease suspension are not represented as
  engine state.

## Outgoing Target Modifiers

Several conditions affect entities attacking the conditioned creature. These modifiers live on the conditioned creature's `to_target_*` channels. They are not visible through the creature's normal `advantage` property.

Use:

```python
target.equipment.ac_bonus.outgoing_advantage
target.equipment.ac_bonus.outgoing_critical
```

or propagate the target's AC value into an attacker's attack value with `set_from_target()`.

Example EB-08-001 uses `outgoing_advantage` to read Blinded's attacker-facing effect.

## Blinded And Deafened

`Blinded` applies:

- `attack_bonus.self_static`: disadvantage on the blinded creature's attacks.
- `ac_bonus.to_target_static`: advantage for attackers.
- sight skills: `AutoHitStatus.AUTOMISS`.

Sight skills are:

- `perception`
- `investigation`
- `sleight_of_hand`
- `stealth`

`Deafened` applies `AutoHitStatus.AUTOMISS` to hearing skills:

- `perception`
- `insight`

Example EB-08-001:

```python
apply_to_target(Blinded, source, target)

assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
assert target.skill_set.perception.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS

target.remove_condition("Blinded")
assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE

apply_to_target(Deafened, source, target)
assert target.skill_set.insight.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_001_blinded_and_deafened_apply_sensory_failures`.

## Exhaustion

`Exhaustion` is a levelled standard condition tagged with
`ConditionTag.EXHAUSTION`. The active condition is named `"Exhaustion"` and has
a `level` field from 1 to 6.

The effects are cumulative:

- level 1: every skill's `skill_bonus.self_static` gets disadvantage, modelling
  disadvantage on ability checks.
- level 2: movement gets a maximum constraint equal to half base movement.
- level 3: `equipment.attack_bonus.self_static` and every saving throw bonus get
  disadvantage.
- level 4: `health.max_hit_points_bonus` gets a negative modifier that halves
  the current maximum hit points.
- level 5: movement gets a maximum constraint of 0.
- level 6: `Entity.receive_instant_death()` is called, so the existing
  `DeathEvent` and `Dead` condition path applies when the death handler is
  registered.

Exhaustion is reduced by replacement rather than mutation. `Entity.on_long_rest()`,
`Entity.revive()`, and `GreaterRestoration` remove the current condition through
normal cleanup, then apply a lower-level `Exhaustion` replacement when a level
remains.

Example EB-08-015:

```python
level_one = apply_to_target(lambda **kwargs: Exhaustion(level=1, **kwargs), source, target)
assert ConditionTag.EXHAUSTION in level_one.tags
assert target.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE

target.remove_condition("Exhaustion")
apply_to_target(lambda **kwargs: Exhaustion(level=3, **kwargs), source, target)
assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
assert target.saving_throws.get_saving_throw("wisdom").bonus.advantage == AdvantageStatus.DISADVANTAGE

target.remove_condition("Exhaustion")
apply_to_target(lambda **kwargs: Exhaustion(level=4, **kwargs), source, target)
assert get_max_hp(target) == base_max_hp // 2

target.remove_condition("Exhaustion")
apply_to_target(lambda **kwargs: Exhaustion(level=6, **kwargs), source, target)
assert "Dead" in target.active_conditions
```

Parity tests:

- `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_015_exhaustion_levels_are_cumulative_and_removable`
- `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_015_entity_long_rest_and_revival_reduce_exhaustion`
- `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_040_greater_restoration_reduces_exhaustion_one_level`

## Charmed

`Charmed` is contextual to the charmer.

It applies:

- `attack_bonus.self_contextual`: `AutoHitStatus.AUTOMISS` when the charmed creature targets the charmer.
- social skill `to_target_contextual`: advantage for the charmer's social checks against the charmed creature.

Social skills are:

- `deception`
- `intimidation`
- `performance`
- `persuasion`

Current edge: the engine blocks attacks against the charmer, but it does not generically block every harmful spell or ability target.

Example EB-08-002:

```python
apply_to_target(Charmed, charmer, target)

target.equipment.attack_bonus.set_target_entity(charmer.uuid)
assert target.equipment.attack_bonus.auto_hit == AutoHitStatus.AUTOMISS

persuasion = charmer.skill_bonus(target.uuid, "persuasion")
assert persuasion.advantage == AdvantageStatus.ADVANTAGE
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_002_charmed_blocks_attacks_and_helps_charmer_social_checks`.

## Poisoned And Frightened

`Poisoned` is static:

- `attack_bonus.self_static`: disadvantage.
- all skills: disadvantage.

`Frightened` is contextual to whether the frightener is in the target's sensed entities:

- `attack_bonus.self_contextual`: disadvantage.
- all skills: disadvantage.
- `movement.self_contextual`: max constraint 0.

Senses store visible entities as a UUID-to-position mapping. A target can sense a source when `source.uuid in target.senses.entities`.

Example EB-08-003:

```python
apply_to_target(Poisoned, source, target)
assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
assert target.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE

target.remove_condition("Poisoned")
apply_to_target(Frightened, source, target)
target.senses.entities.clear()
assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE

target.senses.entities[source.uuid] = source.position
assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
assert target.action_economy.movement.normalized_score == 0
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_003_poisoned_and_frightened_penalize_attacks_and_checks`.

## Grappled, Incapacitated, And Restrained

`Grappled` applies:

- `movement.self_static`: max constraint 0.

It does not block actions.

`Incapacitated` applies max constraint 0 to:

- actions
- bonus actions
- reactions
- movement

This is stricter than the SRD condition text because movement and bonus actions are also clamped.

`Restrained` applies:

- `movement.self_static`: max constraint 0.
- `attack_bonus.self_static`: disadvantage.
- Dexterity saving throw bonus: disadvantage.
- `ac_bonus.to_target_static`: attackers have advantage.

Example EB-08-004:

```python
apply_to_target(Grappled, source, target)
assert target.action_economy.movement.normalized_score == 0
assert target.action_economy.actions.normalized_score == 1

target.remove_condition("Grappled")
apply_to_target(Incapacitated, source, target)
assert target.action_economy.actions.normalized_score == 0
assert target.action_economy.movement.normalized_score == 0

target.remove_condition("Incapacitated")
apply_to_target(Restrained, source, target)
assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_004_grappled_incapacitated_and_restrained_limit_actions`.

## Prone

Normal `Prone` application adds:

- `attack_bonus.self_static`: disadvantage.
- `ac_bonus.to_target_contextual`: advantage for attackers within 5 feet, disadvantage for attackers beyond 5 feet.

The condition class also has a BG3-style immediate stand-up branch: if the target is currently taking its turn and has at least half movement available, it consumes half movement and cancels application.

The turn-start auto-stand handler is not registered by `Prone` itself. It is registered by the standard action setup.

Example EB-08-005:

```python
apply_to_target(Prone, source, target)
assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE

target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE

target.equipment.ac_bonus.set_target_entity(distant_attacker.uuid)
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.DISADVANTAGE
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_005_prone_uses_distance_context_for_incoming_attacks`.

Example EB-08-009:

```python
target.on_turn_start()
condition = Prone(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
result = target.add_condition(condition)

assert result.phase == EventPhase.COMPLETION
assert result.canceled is True
assert condition.applied is True
assert "Prone" not in target.active_conditions
assert target.action_economy.movement.normalized_score == 15
```

The canceled completion means the entity does not index the condition, but the condition object has already been marked applied by `BaseCondition.apply()`.

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_009_prone_immediate_stand_on_own_turn_cancels_indexing`.

Example EB-08-010:

```python
setup_standard_actions(target)
apply_to_target(Prone, source, target)

assert target.get_event_handler_by_name("Prone Auto-Stand") is not None
assert "Prone" in target.active_conditions

other.on_turn_start()

assert "Prone" in target.active_conditions
assert target.action_economy.movement.normalized_score == 30

target.on_turn_start()

assert "Prone" not in target.active_conditions
assert target.action_economy.movement.normalized_score == 15
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_010_prone_auto_stand_handler_is_standard_action_state`.

## Paralyzed, Stunned, And Unconscious

These severe conditions create an `Incapacitated` sub-condition and add saving throw failures.

`Paralyzed` applies:

- sub-condition: `Incapacitated`.
- Strength saving throw bonus: `AutoHitStatus.AUTOMISS`.
- Dexterity saving throw bonus: `AutoHitStatus.AUTOMISS`.
- `ac_bonus.to_target_static`: attackers have advantage.
- `ac_bonus.to_target_contextual`: `CriticalStatus.AUTOCRIT` for attackers within 5 feet.

`Stunned` applies:

- sub-condition: `Incapacitated`.
- Strength and Dexterity saving throw auto-failure.
- `ac_bonus.to_target_static`: attackers have advantage.

`Unconscious` applies:

- sub-condition: `Incapacitated`.
- Strength and Dexterity saving throw auto-failure.
- `ac_bonus.to_target_static`: attackers have advantage.
- `ac_bonus.to_target_contextual`: close-range auto-critical hits.
- `ac_bonus.to_target_contextual`: prone-like distance advantage/disadvantage.

For a distant attacker, Unconscious currently sums static advantage and prone-like contextual disadvantage to `AdvantageStatus.NONE`.

Example EB-08-006:

```python
paralyzed = apply_to_target(Paralyzed, source, target)
assert "Incapacitated" in target.active_conditions
assert target.saving_throws.get_saving_throw("strength").bonus.auto_hit == AutoHitStatus.AUTOMISS

target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.AUTOCRIT
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE

target.equipment.ac_bonus.set_target_entity(distant_attacker.uuid)
assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.NONE
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE

target.remove_condition("Paralyzed")
assert "Incapacitated" not in target.active_conditions
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_006_paralyzed_stunned_and_unconscious_add_incapacitated_trees`.

## Petrified

`Petrified` is a standard condition tagged with `ConditionTag.PETRIFICATION`.

It applies:

- sub-condition: `Incapacitated`.
- Strength and Dexterity saving throw auto-failure.
- `ac_bonus.to_target_static`: attackers have advantage.
- `health.damage_reduction`: `ResistanceStatus.RESISTANCE` for every
  `DamageType`.
- static condition immunity to `Poisoned`.

The poison immunity blocks new `Poisoned` applications while the target remains
petrified. The SRD clauses for multiplied weight, ceased aging, awareness, and
poison/disease suspension are not currently represented as mutable engine
state.

Example EB-08-014:

```python
petrified = apply_to_target(Petrified, source, target)

assert ConditionTag.PETRIFICATION in petrified.tags
assert "Incapacitated" in target.active_conditions
assert target.action_economy.actions.normalized_score == 0
assert target.saving_throws.get_saving_throw("strength").bonus.auto_hit == AutoHitStatus.AUTOMISS

target.equipment.ac_bonus.set_target_entity(attacker.uuid)
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE

for damage_type in DamageType:
    assert target.health.get_resistance(damage_type) == ResistanceStatus.RESISTANCE

assert target.check_condition_immunity("Poisoned")
target.remove_condition("Petrified")
assert "Incapacitated" not in target.active_conditions
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_014_petrified_composes_severe_control_and_all_damage_resistance`.

## Invisible

`Invisible` applies:

- target flag: `is_invisible=True`.
- `attack_bonus.self_contextual`: unseen attacker advantage when the target creature is not in the defender's senses.
- `ac_bonus.to_target_contextual`: incoming attack disadvantage when the invisible creature is not in the attacker's senses.

Removal calls `_remove()` and clears `is_invisible`.

Current edge: base `Invisible` does not install attack/cast reveal handlers. Spell-specific invisibility effects add those behaviors separately.

Example EB-08-007:

```python
apply_to_target(Invisible, source, target)
assert target.is_invisible is True

target.equipment.attack_bonus.set_target_entity(attacker.uuid)
assert target.equipment.attack_bonus.advantage == AdvantageStatus.ADVANTAGE

target.equipment.ac_bonus.set_target_entity(attacker.uuid)
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.DISADVANTAGE

attacker.senses.entities[target.uuid] = target.position
assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE

target.remove_condition("Invisible")
assert target.is_invisible is False
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_007_invisible_sets_perceivability_and_unseen_combat_modifiers`.

## Hidden And Spell Invisibility Reveal

`Hidden` sets `stealth_dc`, adds unseen-attacker advantage, and installs a reveal handler. The handler ignores explicitly non-revealing actions such as `Dash`, `Dodge`, and `Disengage`, but removes Hidden for revealing actions such as `Shove`.

`InvisibilityEffect` is the spell-style condition named `"Invisible"`. Unlike base `Invisible`, it installs an `"Invisibility: Reveal"` handler. It uses the same non-revealing-action allowlist and clears `is_invisible` on removal.

`GreaterInvisibilityEffect` is also named `"Invisible"`, but it installs `"Greater Invisibility: Stealth Check"` instead of the reveal handler. Revealing actions do not automatically remove it. They trigger an escalating Stealth check:

- DC starts at `base_dc`.
- each successful check increments `check_count` by 1;
- the next DC is `base_dc + check_count`;
- failure removes the condition and clears `is_invisible`.

Example EB-08-011:

```python
target.add_condition(Hidden(
    source_entity_uuid=target.uuid,
    target_entity_uuid=target.uuid,
    stealth_result=25,
))

ActionEvent(name="Dash", source_entity_uuid=target.uuid).phase_to(EventPhase.EFFECT)

assert "Hidden" in target.active_conditions
assert target.stealth_dc == 25

ActionEvent(name="Shove", source_entity_uuid=target.uuid).phase_to(EventPhase.EFFECT)

assert "Hidden" not in target.active_conditions
assert target.stealth_dc is None

target.add_condition(InvisibilityEffect(
    source_entity_uuid=target.uuid,
    target_entity_uuid=target.uuid,
))

ActionEvent(name="Dash", source_entity_uuid=target.uuid).phase_to(EventPhase.EFFECT)

assert "Invisible" in target.active_conditions
assert target.is_invisible is True

ActionEvent(name="Shove", source_entity_uuid=target.uuid).phase_to(EventPhase.EFFECT)

assert "Invisible" not in target.active_conditions
assert target.is_invisible is False
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_011_hidden_and_invisibility_reveal_handlers_filter_actions`.

Example EB-08-013:

```python
greater = GreaterInvisibilityEffect(
    source_entity_uuid=source.uuid,
    target_entity_uuid=target.uuid,
    base_dc=10,
)
target.add_condition(greater)

assert target.active_conditions["Invisible"] is greater
assert target.is_invisible is True

ActionEvent(name="Dash", source_entity_uuid=target.uuid).phase_to(EventPhase.EFFECT)
assert target.active_conditions["Invisible"] is greater
assert greater.check_count == 0

with fixed_d20(20):
    ActionEvent(name="Shove", source_entity_uuid=target.uuid).phase_to(EventPhase.EFFECT)

assert target.active_conditions["Invisible"] is greater
assert greater.check_count == 1

with fixed_d20(1):
    ActionEvent(name="Shove", source_entity_uuid=target.uuid).phase_to(EventPhase.EFFECT)

assert "Invisible" not in target.active_conditions
assert target.is_invisible is False
```

The executable test also proves Greater Invisibility uses the same unseen attacker/target combat modifiers as other invisible effects.

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_013_greater_invisibility_uses_stealth_checks_instead_of_reveal`.

## Removal Cleanup

Standard condition removal is driven by the `BaseBlock` cleanup path described in Chapter 07. For each implemented SRD-style condition, removing the condition must:

- Remove the condition from `active_conditions` and `active_conditions_by_uuid`.
- Leave only empty source index lists in `active_conditions_by_source`.
- Remove every owned modifier from action economy, attack bonus, AC bonus, skills, and saving throws.
- Recursively clean severe-condition subtrees such as `Paralyzed -> Incapacitated`.
- Clear condition-owned flags such as `is_invisible`.

Example EB-08-012:

```python
condition_types = [
    Blinded, Charmed, Deafened, Frightened, Grappled, Incapacitated,
    Exhaustion, Invisible, Paralyzed, Petrified, Poisoned, Prone, Restrained,
    Stunned, Unconscious,
]

for condition_type in condition_types:
    reset_condition_state()
    condition = apply_to_target(condition_type, source, target)

    target.equipment.attack_bonus.set_target_entity(source.uuid)
    target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
    _ = source.skill_bonus(target.uuid, "persuasion")

    target.remove_condition(condition.name)

    assert condition.applied is False
    assert target.active_conditions == {}
    assert target.active_conditions_by_uuid == {}
    assert target.action_economy.movement.normalized_score == 30
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.NONE
    assert source.skill_bonus(target.uuid, "persuasion").advantage == AdvantageStatus.NONE
    assert target.is_invisible is False
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_012_standard_condition_removal_cleans_owned_state`.

## Remaining Missing Condition Aliases

The local condition module defines `Exhaustion` and `Petrified`. It does not
define an `Exhausted` alias because the SRD condition name is `Exhaustion`.

- `Exhausted`

Example EB-08-008:

```python
assert hasattr(conditions_module, "Petrified")
assert hasattr(conditions_module, "Exhaustion")
assert not hasattr(conditions_module, "Exhausted")
```

Parity test: `tests/engine_book/test_chapter_08_standard_conditions.py::test_eb_08_008_srd_condition_gaps_are_explicit`.

## Deeper Coverage Still Needed

- Initial Chapter 08 edge backlog is covered; add new standard-condition rows only after further code study.
- Add a formal condition catalog table if future readers need a compact at-a-glance reference in addition to the behavior sections above.

## Documentation Hygiene Notes

- Chapter 08 hygiene reviewed `dnd/conditions.py` for the concrete standard-condition surface: combat-state markers, `Blinded`, `Charmed`, `Dashing`, `Deafened`, `Dodging`, `Disengaging`, `Frightened`, `Grappled`, `Incapacitated`, `Invisible`, `Paralyzed`, `Poisoned`, `Prone`, `Stunned`, `Restrained`, `Unconscious`, `Dead`, `Hidden`, `InvisibilityEffect`, and their immediate reveal/context helper callables.
- The pass removed old commented-out implementation blocks from the severe-condition classes, converted informal class/helper docstrings to Google-style contracts, and added `Field(..., description=...)` metadata to touched condition fields.
- `Petrified` is now a standard condition class with condition-owned resistance
  modifiers, `Poisoned` immunity, and normal subtree cleanup.
- Preserved behavior edges: `Prone` still uses the canceled-completion immediate stand-up edge, and base `Invisible` still has no reveal handler.
- Broader concentration behavior remains for the spellcasting/spell-family cleanup passes because it belongs to later chapters' behavior surfaces.
