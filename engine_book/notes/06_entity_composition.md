# 06. Entity Composition

## Purpose

`Entity` is the engine's main actor object. It composes the lower-level block systems into a playable creature: abilities, skills, saving throws, health, equipment, action economy, senses, inventory, appearance, spellcasting, conditions, handlers, faction identity, and action templates.

This chapter documents current behavior in `dnd/entity.py` and the composed block modules. The examples are executable in `tests/engine_book/test_chapter_06_entity_composition.py`.

## Source Files Studied

- `dnd/entity.py`
- `dnd/blocks/abilities.py`
- `dnd/blocks/skills.py`
- `dnd/blocks/saving_throws.py`
- `dnd/blocks/health.py`
- `dnd/blocks/action_economy.py`
- `dnd/blocks/spellcasting.py`
- `dnd/blocks/appearance.py`
- `dnd/blocks/appearance_catalog.py`
- `dnd/actions_functional.py`
- `dnd/core/base_actions.py`
- `examples/test_faction_system.py`
- `examples/test_spell_system.py`
- `examples/test_available_actions.py`
- `tests/engine_book/test_chapter_06_entity_composition.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: ability modifiers use `(score - 10) // 2`, matching `interactive_ruleset/Gameplay/Abilities.md`.
- `SRD-aligned`: proficiency bonus participates in ability checks, saving throws, attack rolls, and spell attacks. Skill expertise doubles proficiency for that skill.
- `SRD-aligned`: spell save DC is `8 + proficiency bonus + spellcasting ability modifier`, with engine modifiers allowed.
- `SRD-aligned`: actions such as Dash, Dodge, Disengage, Hide, Attack, movement, and spellcasting are represented as combat options, matching `interactive_ruleset/Gameplay/Combat.md`.
- `Engine extension`: entities are component containers with UUID registries and live GridMap registration.
- `Engine adaptation`: faction-based ally/enemy identity is an engine targeting policy, not an SRD primitive.
- `Current edge`: the configured `Entity.create(..., config=EntityConfig(...))` path reliably gives sub-blocks the entity UUID. The bare `config=None` path leaves many default sub-blocks with random source UUIDs and should not be used as the book's composition model.

## Creation And Registries

`Entity.create(source_entity_uuid=..., config=...)` builds the entity and all top-level blocks from an `EntityConfig`.

The configured creation path explicitly constructs:

- `AbilityScores`
- `SkillSet`
- `SavingThrowSet`
- `Health`
- `Equipment`
- `ActionEconomy`
- `Senses`
- `Inventory`
- `Appearance`
- `SpellcastingBlock`
- `proficiency_bonus`
- `initiative`

`Appearance` is renderer metadata rather than gameplay state. Its body, head,
hair, beard, and tint fields do not change checks, saves, attacks, movement, or
targeting; they give API consumers stable visual taxonomy keys while staying
inside the same entity-owned block graph.

The entity UUID is the same as `source_entity_uuid`. The entity registers in:

- `Entity._entity_registry`
- `Entity._entity_by_position`
- `BaseBlock._registry`
- `GridMap` entity position tracking

It also registers a pre-completion sensory callback through its senses block.

Example EB-06-001:

```python
entity = configured_entity(position=(2, 3))

assert entity.uuid == entity.source_entity_uuid
assert Entity.get(entity.uuid) is entity
assert BaseBlock.get(entity.uuid) is entity
assert entity in Entity.get_all_entities_at_position((2, 3))
assert get_map().get_entity_position(entity.uuid) == (2, 3)

assert entity.ability_scores.source_entity_uuid == entity.uuid
assert entity.skill_set.athletics.source_entity_uuid == entity.uuid
assert entity.senses.position == (2, 3)
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_001_entity_create_wires_identity_registries_and_blocks`.

The bare `config=None` creation path still registers the entity and uses the
supplied UUID for the entity itself. Default child blocks and direct values are
normalized during construction, so basic composition methods can operate without
source-mismatch errors even when no explicit `EntityConfig` is supplied.

Example EB-06-009:

```python
source_uuid = uuid4()
entity = Entity.create(source_entity_uuid=source_uuid, name="Bare Entity")

assert entity.uuid == source_uuid
assert Entity.get(source_uuid) is entity
assert get_map().get_entity_position(source_uuid) == (0, 0)
assert entity.appearance.source_entity_uuid == source_uuid
assert entity.ability_scores.source_entity_uuid == source_uuid
assert entity.health.source_entity_uuid == source_uuid
assert all(block.source_entity_uuid == source_uuid for block in entity.blocks.values())
assert all(value.source_entity_uuid == source_uuid for value in entity.values.values())
assert entity.proficiency_bonus.normalized_score == 2
assert entity.get_hp() == 6
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_009_bare_entity_creation_registers_and_normalizes_defaults`.

## Abilities

`AbilityScores` owns the six SRD abilities:

- strength
- dexterity
- constitution
- intelligence
- wisdom
- charisma

Each `Ability` has:

- `ability_score`: a `ModifiableValue` normalized by `(score - 10) // 2`.
- `modifier_bonus`: a separate `ModifiableValue` added after normalization.

`Ability.modifier` is:

```python
ability_score.normalized_score + modifier_bonus.score
```

This matches the SRD ability modifier table and formula in `interactive_ruleset/Gameplay/Abilities.md`.

## Skills

`SkillSet` owns all 18 skills. Each `Skill` records:

- skill name.
- associated ability through `SKILL_TO_ABILITY`.
- `skill_bonus`.
- `proficiency`.
- `expertise`.

A raw `Skill` can convert proficiency based on proficiency/expertise, but entity-level `Entity.skill_bonus()` is the complete check bonus builder. It combines:

- normalized proficiency bonus, after skill proficiency/expertise conversion.
- skill-specific bonus.
- associated ability score value.
- associated ability modifier bonus.
- target outgoing modifiers when a target entity is supplied.

`Entity.passive_skill(skill_name)` is:

```python
10 + skill_bonus.normalized_score
```

with `+5` for advantage and `-5` for disadvantage on that combined skill bonus. `get_passive_perception()` is passive `perception`.

Example EB-06-002:

```python
entity = configured_entity()

athletics = entity.skill_bonus(None, "athletics")
perception = entity.skill_bonus(None, "perception")
dex_save = entity.saving_throw_bonus(None, "dexterity")

assert athletics.normalized_score == 10
assert entity.passive_skill("athletics") == 20
assert perception.normalized_score == 6
assert entity.get_passive_perception() == 16
assert dex_save.normalized_score == 6
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_002_abilities_skills_saves_and_passives_compose`.

## Saving Throws

`SavingThrowSet` owns one saving throw per ability:

- strength
- dexterity
- constitution
- intelligence
- wisdom
- charisma

`Entity.saving_throw_bonus(target_entity_uuid, ability_name)` combines:

- proficiency bonus after the save's proficiency converter.
- save-specific bonus.
- ability score value.
- ability modifier bonus.
- target outgoing modifiers when a target entity is supplied and target is not self.

The full saving throw execution path is `Entity.saving_throw(request)`, which phases a `SavingThrowEvent`, rolls through `Entity.roll_d20()`, and lets handlers modify results at event boundaries.

`Entity.skill_check(request)` mirrors the same pattern for a `SkillCheckEvent`. Both entity-level executors create a request event history with `DECLARATION`, `EXECUTION`, `EFFECT`, and `COMPLETION`; the d20 roll itself is represented by a child roll-result event with `DECLARATION`, `EFFECT`, and `COMPLETION`.

Example EB-06-013:

```python
save_request = source.create_saving_throw_request(
    target_entity_uuid=target.uuid,
    ability_name="dexterity",
    dc=15,
)
with fixed_randint(9):
    save_outcome, save_roll, save_success = target.saving_throw(save_request)

save_history = EventQueue.get_event_history(save_request.uuid)
save_roll_events = EventQueue.get_events_by_type(EventType.SAVE_D20_ROLL_RESULT)

assert save_outcome == AttackOutcome.HIT
assert save_roll.results == [9]
assert save_roll.total == 15
assert save_success is True
assert [event.phase for event in save_history] == [
    EventPhase.DECLARATION,
    EventPhase.EXECUTION,
    EventPhase.EFFECT,
    EventPhase.COMPLETION,
]
assert save_history[1].bonus.normalized_score == 6
assert save_history[-1].dice_roll is save_roll
assert save_history[-1].result is True
assert [event.phase for event in save_roll_events] == [
    EventPhase.DECLARATION,
    EventPhase.EFFECT,
    EventPhase.COMPLETION,
]
assert all(event.parent_event == save_request.uuid for event in save_roll_events)
assert all(event.ability_name == "dexterity" for event in save_roll_events)

skill_request = source.create_skill_check_request(
    target_entity_uuid=target.uuid,
    skill_name="athletics",
    dc=15,
)
with fixed_randint(4):
    skill_outcome, skill_roll, skill_success = target.skill_check(skill_request)

assert skill_outcome == AttackOutcome.MISS
assert skill_roll.results == [4]
assert skill_roll.total == 14
assert skill_success is False
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_013_saving_throw_and_skill_check_execute_event_phases`.

## Health

`Entity.get_hp()` delegates to `Health.get_total_hit_points()` after computing the Constitution modifier from the entity's ability scores.
The health block exposes this state through explicit Pydantic field metadata:
hit dice, max-HP bonuses, temporary HP, damage taken, flat reduction, type
resistance channels, and healing blockers are all serializable model fields
with domain descriptions.

Current HP is:

```python
hit dice HP
+ constitution_modifier * total_hit_dice_count
+ max_hit_points_bonus
+ temporary_hit_points
- damage_taken
```

Example EB-06-003:

```python
entity = configured_entity()

assert entity.get_hp() == 37
```

In the test configuration, that is `3d8 maximums = 24`, Constitution modifier `+2` times 3 hit dice, max HP bonus `+2`, and temporary HP `+5`.

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_003_health_action_economy_and_spellcasting_compose`.

Configured entities use `HealthConfig()` exactly as supplied. The default health config has no hit dice and no bonus HP, so configured creation can produce a registered but inactive zero-HP entity. Bonus HP and temporary HP still contribute even without hit dice.

Example EB-06-010:

```python
no_hit_dice = Entity.create(
    source_entity_uuid=uuid4(),
    name="No Hit Dice",
    config=EntityConfig(),
)
bonus_only = Entity.create(
    source_entity_uuid=uuid4(),
    name="Bonus Only",
    config=EntityConfig(
        health=HealthConfig(max_hit_points_bonus=3, temporary_hit_points=2)
    ),
)

assert no_hit_dice.health.hit_dices == []
assert no_hit_dice.get_hp() == 0
assert no_hit_dice.has_hp is False
assert no_hit_dice.is_active is False

assert bonus_only.health.hit_dices == []
assert bonus_only.get_hp() == 5
assert bonus_only.has_hp is True
assert bonus_only.is_active is True
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_010_configured_entity_defaults_to_zero_hit_points`.

`Health` also tracks Hit Dice expenditure independently from maximum HP. A
`HitDice` block exposes:

- `spent_hit_dice`;
- `available_hit_dice`;
- `spend()`;
- `recover()`;
- `roll_spent_die()`.

At the entity layer, `Entity.spend_hit_dice()` is the short-rest healing entry
point. It spends dice one at a time, adds the entity's Constitution modifier to
each roll, then routes the requested healing through `Entity.receive_healing()`
so healing blockers, HP caps, and heal events remain authoritative.

## Action Economy

`ActionEconomy` owns turn costs and spell slot counters:

- actions
- bonus actions
- reactions
- movement
- spell slots 1 through 9
- named `Resource` objects

Costs are represented as negative numerical modifiers named with `"cost"`. `reset_all_costs()` removes turn-based costs for actions, bonus actions, reactions, and movement. Spell slots are not reset there; `reset_spell_slot_costs()` handles slot restoration.

Rest recharge is directional:

- `ActionEconomy.on_short_rest()` recharges `SHORT_REST` resources.
- `ActionEconomy.on_long_rest()` recharges both `SHORT_REST` and `LONG_REST`
  resources.

Named resources track `current`, `maximum`, and `recharge_type`:

- `SHORT_REST`
- `LONG_REST`
- `TURN_START`
- `NEVER`

Example EB-06-004:

```python
economy.add_resource("second_wind", maximum=1, recharge_type=RechargeType.SHORT_REST)
economy.add_resource("daily_power", maximum=1, recharge_type=RechargeType.LONG_REST)
economy.consume_resource("second_wind")
economy.consume_resource("daily_power")
assert economy.get_resource_current("second_wind") == 0
assert economy.get_resource_current("daily_power") == 0
economy.on_short_rest()
assert economy.get_resource_current("second_wind") == 1
assert economy.get_resource_current("daily_power") == 0

economy.consume_resource("second_wind")
economy.on_long_rest()
assert economy.get_resource_current("second_wind") == 1
assert economy.get_resource_current("daily_power") == 1
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_004_action_economy_resources_recharge_by_type`.

## Rest And Revival Lifecycle

`Entity.on_short_rest()` delegates to the action economy short-rest recharge.
Hit Dice healing is explicit through `Entity.spend_hit_dice()` because the
caller chooses how many dice to spend.

`Entity.on_long_rest()` currently:

- resets turn costs;
- restores spell slot costs;
- recharges rest-based resources through `ActionEconomy.on_long_rest()`;
- marks entity, equipped-item, and inventory-item `UNTIL_LONG_REST` condition
  durations as rested and removes the expired conditions;
- reduces the first active `ConditionTag.EXHAUSTION` levelled condition by one
  level;
- restores all normal hit point damage;
- clears remaining temporary hit points.
- recovers spent Hit Dice up to half the entity's total Hit Dice, with a
  minimum recovery of one when the entity has Hit Dice.

Long-rest benefits require the entity to have at least 1 HP and not have the
`Dead` condition at the start of the rest.

`Entity.revive(hit_points=1)` is the engine's current resurrection primitive. It
removes `Dead`, removes the `Incapacitated` subtree through normal condition
cleanup, marks the entity blocking again, sets the entity to at least the
requested HP, and reduces Exhaustion by one level by default.

Example EB-06-015:

```python
entity.action_economy.add_resource("daily_power", maximum=1, recharge_type=RechargeType.LONG_REST)
entity.action_economy.consume_resource("daily_power")
entity.action_economy.consume("spell_slot_1", 1)
entity.add_condition(
    BaseCondition(
        name="Long Rest Marker",
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
        duration=Duration(duration_type=DurationType.UNTIL_LONG_REST),
    )
)
entity.add_condition(Exhaustion(source_entity_uuid=source.uuid, target_entity_uuid=entity.uuid, level=3))

entity.on_long_rest()

assert entity.active_conditions["Exhaustion"].level == 2
assert entity.action_economy.get_resource_current("daily_power") == 1
assert entity.action_economy.spell_slot_1.normalized_score == 2
assert "Long Rest Marker" not in entity.active_conditions

entity.receive_damage(entity.get_hp(), DamageType.SLASHING, source.uuid)
assert "Dead" in entity.active_conditions

assert entity.revive(hit_points=1) is True

assert entity.active_conditions["Exhaustion"].level == 1
assert "Dead" not in entity.active_conditions
assert entity.get_hp() == 1
```

SRD relationship: the Exhaustion condition text in
`interactive_ruleset/Gamemastering/Conditions.md` says finishing a qualifying
long rest and being raised from the dead reduce exhaustion by 1. The engine now
models those reductions through `Entity.on_long_rest()` and `Entity.revive()`.

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_015_entity_long_rest_and_revival_reduce_exhaustion`.

Example EB-06-016:

```python
normal_max_hp = get_max_hp(entity)

entity.receive_damage(12, DamageType.SLASHING, source.uuid)
assert entity.health.temporary_hit_points.normalized_score == 0
assert entity.health.damage_taken == 7
assert entity.get_hp() == normal_max_hp - 7

entity.health.add_temporary_hit_points(4, source.uuid)
assert entity.get_hp() == normal_max_hp - 3

assert entity.on_long_rest() is True

assert entity.health.damage_taken == 0
assert entity.health.temporary_hit_points.normalized_score == 0
assert entity.get_hp() == normal_max_hp

dead_entity.receive_damage(dead_entity.get_hp(), DamageType.SLASHING, source.uuid)
assert "Dead" in dead_entity.active_conditions
assert dead_entity.on_long_rest() is False
assert dead_entity.action_economy.spell_slot_1.normalized_score == 1
```

SRD relationship: `interactive_ruleset/Gameplay/Adventuring.md` says a long rest
restores all lost hit points and requires at least 1 HP at the start to gain
benefits. `interactive_ruleset/Gameplay/Combat.md` says temporary HP lasts until
depleted or a long rest unless its source has a different duration. The current
engine implements those HP and temporary-HP pieces. Food/drink qualification,
24-hour rest cadence, and concrete resurrection spells remain separate
lifecycle/spell surfaces.

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_016_long_rest_restores_hp_and_expires_temporary_hp`.

Example EB-06-017:

```python
normal_max_hp = get_max_hp(entity)
hit_dice = entity.health.hit_dices[0]

assert hit_dice.hit_dice_count.normalized_score == 3
assert hit_dice.spent_hit_dice == 0
assert hit_dice.available_hit_dice == 3

entity.receive_damage(20, DamageType.SLASHING, source.uuid)
assert entity.health.damage_taken == 15

with patch("dnd.blocks.health.randint", side_effect=[5, 2]):
    first_results = entity.spend_hit_dice(count=2)

assert [result.roll for result in first_results] == [5, 2]
assert [result.constitution_modifier for result in first_results] == [2, 2]
assert [result.total_healing for result in first_results] == [7, 4]
assert [result.actual_healing for result in first_results] == [7, 4]
assert hit_dice.spent_hit_dice == 2
assert hit_dice.available_hit_dice == 1
assert entity.health.damage_taken == 4
assert entity.get_hp() == normal_max_hp - 4

with patch("dnd.blocks.health.randint", return_value=8):
    capped_result = entity.spend_hit_dice()[0]

assert capped_result.roll == 8
assert capped_result.total_healing == 10
assert capped_result.actual_healing == 4
assert hit_dice.spent_hit_dice == 3
assert hit_dice.available_hit_dice == 0
assert entity.health.damage_taken == 0
assert entity.get_hp() == normal_max_hp

try:
    entity.spend_hit_dice()
except ValueError as error:
    assert "Not enough hit dice" in str(error)
else:
    raise AssertionError("Expected spending unavailable Hit Dice to fail")

assert entity.on_long_rest() is True
assert hit_dice.spent_hit_dice == 2
assert hit_dice.available_hit_dice == 1

entity.on_long_rest()
assert hit_dice.spent_hit_dice == 1
assert hit_dice.available_hit_dice == 2
```

SRD relationship: `interactive_ruleset/Gameplay/Adventuring.md` says a
character can spend Hit Dice at the end of a short rest, adding the
Constitution modifier to each die, and recovers spent Hit Dice at the end of a
long rest up to half the total number of dice, minimum one die. The engine
models the spend as an explicit `Entity.spend_hit_dice()` call and the recovery
inside `Entity.on_long_rest()`.

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_017_hit_dice_spend_for_short_rest_and_recover_on_long_rest`.

## Spellcasting

Every entity has a `SpellcastingBlock`. For non-casters, defaults are harmless.

The spellcasting block stores spell-specific modifiers:

- spellcasting ability.
- spell attack bonus.
- spell damage bonus.
- spell save DC bonus.
- spell critical threshold bonus.
- spell critical extra dice.
- extra spell damage entries.

Spell slots live in `ActionEconomy`, not in `SpellcastingBlock`. Known spells live in action templates.

`Entity.spell_save_dc()` is:

```python
8 + proficiency_bonus + spellcasting_ability_modifier + spell_dc_bonus
```

`Entity.spell_attack_bonus()` combines:

- proficiency bonus.
- spellcasting ability score and modifier bonus.
- generic equipment attack bonus.
- spell-specific attack bonus.

`is_spellcaster` checks for either base spell slots or registered spell action
templates. A cantrip-only creature with a registered spell template is therefore
treated as a spellcaster even when it has no spell slots.

Example EB-06-003:

```python
assert entity.has_spell_slot(1) is True
assert entity.has_spell_slot(2) is False
assert entity.get_lowest_spell_slot(2) == 3
assert entity.is_spellcaster is True
assert entity.spell_save_dc() == 16
assert entity.spell_attack_bonus().normalized_score == 9
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_003_health_action_economy_and_spellcasting_compose`.

Example EB-06-008:

```python
entity = Entity.create(
    source_entity_uuid=uuid4(),
    name="Cantrip Only",
    config=EntityConfig(
        action_economy=ActionEconomyConfig(spell_slots={}),
        spellcasting=SpellcastingConfig(spellcasting_ability="charisma"),
    ),
)

assert entity.has_spell_slot(1) is False
assert entity.is_spellcaster is False

register_spell(entity, FireBolt, caster_level=5)
spell_template = entity.get_action_template("Fire Bolt")

assert spell_template is not None
assert spell_template.is_spell is True
assert entity.has_spell_slot(1) is False
assert entity.is_spellcaster is True
```

A registered `SpellAction` template is enough for action discovery and enough
for `Entity.is_spellcaster`.

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_008_registered_spell_action_defines_spellcaster_status`.

## Creature Traits

Entity-level traits describe creature identity and broad biological
capabilities that multiple subsystems may consult:

- `creature_type`: high-level type such as humanoid, undead, or fiend.
- `size`: grid and rules size band.
- `weight`: pounds, currently used by Shove-style movement rules.
- `has_ordinary_sight`: whether the entity can see visual effects without
  special senses.
- `requires_breathing`: whether inhaled hazards can affect the entity.

These are configured through `EntityConfig` and copied onto the created
`Entity`. Spell and action systems use the traits instead of hard-coding
spell-local exceptions; for example, Stinking Cloud reads
`requires_breathing` before asking for its turn-start saving throw.

Parity test: `tests/engine_book/test_chapter_15_spell_families.py::test_eb_15_041_stinking_cloud_skips_breathless_creatures`.

## Factions

Faction methods define targeting relationships:

- An entity is always its own ally.
- An entity is never its own enemy.
- Two different entities with the same non-`None` faction are allies.
- Any `None` faction means no ally relationship except self.
- Different factions are enemies.
- `None` faction is enemy to everyone else.

Example EB-06-005:

```python
hero = configured_entity("Hero", (0, 0), "heroes")
ally = configured_entity("Ally", (1, 0), "heroes")
enemy = configured_entity("Enemy", (2, 0), "monsters")
neutral = configured_entity("Neutral", (3, 0), None)

assert hero.is_ally(hero) is True
assert hero.is_ally(ally) is True
assert hero.is_enemy(enemy) is True
assert hero.is_enemy(neutral) is True
assert Entity.get_entities_by_faction("heroes") == [hero, ally]
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_005_factions_define_allies_and_enemies`.

Visible ally/enemy helpers are a second layer over senses. `Senses.entities` stores visible entity UUIDs and positions; `get_visible_allies()` and `get_visible_enemies()` filter that dictionary through faction relationships and remove dead entities unless requested. A factionless visible entity is treated as an enemy.

`get_available_actions(target_filter=...)` uses these same pools before validating each entity-targeted action template. The method-level target filter can therefore show an action such as `Shove` against enemies, allies, or all visible entities depending on the requested pool.

Example EB-06-011:

```python
Entity.update_all_entities_senses()
setup_standard_actions(hero)

assert hero.senses.entities == {
    enemy.uuid: (3, 2),
    neutral.uuid: (3, 3),
    ally.uuid: (2, 3),
}
assert hero.get_visible_allies() == {ally.uuid: (2, 3)}
assert hero.get_visible_enemies() == {
    enemy.uuid: (3, 2),
    neutral.uuid: (3, 3),
}

assert entity_action_target_uuids(hero, "Shove", "enemies") == {
    enemy.uuid,
    neutral.uuid,
}
assert entity_action_target_uuids(hero, "Shove", "allies") == {ally.uuid}
assert entity_action_target_uuids(hero, "Shove", "all") == {
    ally.uuid,
    enemy.uuid,
    neutral.uuid,
}
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_011_visible_entities_filter_into_allies_and_enemies`.

## Targeted Bonus Propagation

High-level entity methods for skills and saving throws do target propagation for callers.

For `Entity.skill_bonus(target_uuid, skill_name)`, the source entity:

1. Temporarily sets the target entity.
2. Builds source and target bonus components.
3. Copies target `to_target_*` channels into source `from_target_*` channels.
4. Combines the source values.
5. Clears temporary target state.

Example EB-06-006:

```python
target.skill_set.athletics.skill_bonus.to_target_static.add_value_modifier(
    NumericalModifier.create(
        source_entity_uuid=target.uuid,
        target_entity_uuid=actor.uuid,
        name="Slippery Target",
        value=-2,
    )
)

targeted_athletics = actor.skill_bonus(target.uuid, "athletics")

assert targeted_athletics.normalized_score == base_athletics - 2
assert actor.target_entity_uuid is None
assert actor.skill_set.athletics.skill_bonus.from_target_static is None
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_006_targeted_skill_bonus_imports_target_outgoing_modifiers`.

## Standard Actions

`setup_standard_actions(entity)` is the functional API that installs base action templates and core handlers.

It clears existing templates, then registers:

- `Move`
- `Jump`
- `Dash`
- `Dodge`
- `Disengage`
- `Hide`
- `Drop Concentration`
- `Shake Awake`
- `Shove`
- `Pick Up`
- `Attack Object`
- weapon attack templates for equipped weapons only

It also registers handlers for:

- weapon equip/unequip template updates.
- HasAttacked state.
- HasTakenDamage state.
- death condition application.
- prone auto-stand.

Action discovery returns an `AvailableActionsResult` grouped into self, entity, position, object, and item-use actions. It validates targets from senses, faction filters, costs, object visibility, inventory use actions, and environmental use actions.

Example EB-06-007:

```python
setup_standard_actions(entity)

template_names = {action.name for action in entity.registered_actions}
assert {"Move", "Jump", "Dash", "Dodge", "Disengage"}.issubset(template_names)
assert entity.get_event_handler_by_name("Prone Auto-Stand") is not None

available = entity.get_available_actions()
assert {"Dash", "Dodge", "Disengage"}.issubset(
    {action.template_name for action in available.self_actions}
)
assert available.remaining_movement == 35
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_007_standard_actions_register_templates_and_handlers`.

Weapon attack templates are not created for empty weapon slots. `setup_standard_actions()` registers weapon equip and unequip event handlers; when equipment fires `WEAPON_EQUIP` or `WEAPON_UNEQUIP` at effect phase, the corresponding `Attack_<slot>` template is added or removed.

Example EB-06-012:

```python
setup_standard_actions(entity)

assert entity.get_action_template("Attack_MELEE_MAIN") is None

sword = create_shortsword(entity.uuid)
assert entity.loot_item(sword) is True
assert sword.uuid in entity.inventory.items
assert entity.equip_item(sword.uuid, WeaponSlot.MELEE_MAIN) is True

template = entity.get_action_template("Attack_MELEE_MAIN")
assert template is not None
assert template.is_attack is True
assert template.weapon_slot == WeaponSlot.MELEE_MAIN
assert template.valid_target_filter == "enemies"
assert entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN) is sword
assert sword.uuid not in entity.inventory.items

unequipped = entity.unequip_item(WeaponSlot.MELEE_MAIN)

assert unequipped is sword
assert sword.uuid in entity.inventory.items
assert entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN) is None
assert entity.get_action_template("Attack_MELEE_MAIN") is None
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_012_equipped_weapons_create_and_remove_attack_templates`.

`setup_standard_actions()` clears and re-adds action templates and replaces the
standard handlers it owns for that entity. Calling it twice leaves one direct
weapon equip handler, one direct weapon unequip handler, and one each of the
entity-tracked combat-state handlers.

Example EB-06-014:

```python
setup_standard_actions(entity)
first_global_handlers = list(EventQueue._event_handlers_by_source_entity_uuid[entity.uuid])
first_local_handler_names = sorted(
    handler.name for handler in entity.event_handlers.values()
)
first_global_handler_names = sorted(handler.name for handler in first_global_handlers)

setup_standard_actions(entity)
second_global_handlers = list(EventQueue._event_handlers_by_source_entity_uuid[entity.uuid])
second_local_handler_names = sorted(
    handler.name for handler in entity.event_handlers.values()
)
second_global_handler_names = sorted(handler.name for handler in second_global_handlers)

assert len(first_global_handlers) == 6
assert len(first_local_handler_names) == 4
assert first_global_handler_names.count(f"WeaponEquipHandler_{entity.uuid}") == 1
assert first_global_handler_names.count(f"WeaponUnequipHandler_{entity.uuid}") == 1

assert len(second_global_handlers) == 6
assert len(second_local_handler_names) == 4
assert second_global_handler_names.count(f"WeaponEquipHandler_{entity.uuid}") == 1
assert second_global_handler_names.count(f"WeaponUnequipHandler_{entity.uuid}") == 1
assert second_local_handler_names.count("HasAttacked Tracker") == 1
assert second_local_handler_names.count("HasTakenDamage Tracker") == 1
assert second_local_handler_names.count("Death Condition Handler") == 1
assert second_local_handler_names.count("Prone Auto-Stand") == 1
assert second_global_handler_names == first_global_handler_names
assert second_local_handler_names == first_local_handler_names
```

Parity test: `tests/engine_book/test_chapter_06_entity_composition.py::test_eb_06_014_repeated_standard_action_setup_replaces_handlers`.

## Current Edges To Preserve

- Prefer configured `Entity.create(..., config=...)` for reliable source propagation across composed blocks.
- `HealthConfig()` defaults to no hit dice, so a configured entity with no hit dice has 0 base HP before bonuses.
- `setup_standard_actions()` does not register unarmed attack templates; weapon attacks are registered only for equipped `Weapon` objects.
- Weapon equip/unequip events synchronize the `Attack_<slot>` template for the changed slot.
- `setup_standard_actions()` is handler-idempotent for the standard handlers it
  installs; repeated setup replaces them before re-registering.
- `is_spellcaster` checks base spell slots and registered spell action templates.
- Faction `None` means no allies except self and enemy to all other entities.
- `get_available_actions(target_filter=...)` changes the candidate entity pool before per-template validation.
- Entity-level `skill_bonus()` and `saving_throw_bonus()` are the high-level methods that handle target propagation; low-level block methods do not.

## Hygiene Notes

The Chapter 06 hygiene pass reviewed the entity composition surface in
`dnd/entity.py`: `EntityConfig`, configured and bare creation paths, entity
registry helpers, target lookup, condition immunity checks, entity-level skill
and saving throw composition, weapon attack/AC/damage composition, HP access,
spell-slot and spellcasting helpers, and faction filtering helpers.

The pass converted scoped contracts to Google-style docstrings, added Pydantic
field descriptions where the composed entity configuration needed them, removed
stale or misleading comments, and corrected the `is_spellcaster` docstring to
match the slot-or-template implementation. EB-06-009 now documents normalized
bare-entity defaults after the BaseBlock constructor propagation fix, and
EB-06-014 documents idempotent standard-handler setup; EB-06-010 remains a
documented behavior edge.
