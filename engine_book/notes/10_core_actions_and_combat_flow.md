# 10. Core Actions And Combat Flow

## Purpose

This chapter documents the executable combat path above action discovery: once an
action instance exists, how the engine validates it, runs events, changes state,
and spends costs.

The examples are executable in both:

- `tests/engine_book/test_chapter_10_core_actions_combat.py`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

The pytest file calls the same example functions, so the book examples and the
proper test suite stay in 1:1 parity.

## Source Files Studied

- `dnd/core/base_actions.py`
- `dnd/actions.py`
- `dnd/reactions.py`
- `dnd/core/events.py`
- `dnd/items/test_reactions.py`
- `dnd/entity.py`
- `dnd/blocks/action_economy.py`
- `dnd/blocks/health.py`
- `dnd/blocks/sensory.py`
- `dnd/conditions.py`
- `dnd/utils/test_utils.py`
- `examples/test_available_actions.py`
- `examples/combat_ranged.py`
- `examples/test_directional_environment_items.py`
- `examples/test_handler_toggle.py`
- `examples/test_improved_critical.py`
- `examples/test_intercept_dodge_roll.py`
- `examples/test_jump.py`
- `examples/test_shove.py`
- `examples/test_protection.py`
- `examples/test_shield_spell.py`
- `examples/test_two_weapon_fighting.py`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: the engine represents one action, one bonus action, movement,
  and one reaction per turn as independent action-economy channels. See
  `interactive_ruleset/Gameplay/Combat.md`, sections "Your Turn", "Bonus
  Actions", and "Reactions".
- `SRD-aligned`: Attack validates reach or range, resolves an attack roll
  against AC, rolls damage on hit, doubles weapon damage dice on critical hits,
  and spends the action only after successful completion.
- `SRD-aligned`: natural 1 is a critical miss, and natural 20 is a critical hit
  regardless of AC after explicit engine auto-miss/auto-hit modifiers are
  resolved.
- `SRD-aligned`: mixed-damage weapon attacks roll separate damage components
  and apply resistance, vulnerability, and immunity per damage type before
  applying the final HP loss.
- `SRD-aligned`: movement spends movement as distance is traversed; leaving a
  hostile creature's reach can trigger an opportunity attack; Disengage prevents
  opportunity attacks for the turn.
- `SRD-aligned`: forced movement uses a separate event type and does not provoke
  opportunity attacks, matching the SRD statement that movement caused by
  someone or something else does not provoke.
- `Engine adaptation`: opportunity attacks are not automatically installed by
  `setup_standard_actions()`. A creature needs an opportunity-attack handler
  registered with `add_opportunity_attack_handler()`.
- `Engine adaptation`: normal attacks require the target to be visible in
  `source_entity.senses.entities`, so guessing unseen target positions is not
  modeled by the standard `Attack` action.
- `Engine adaptation`: `Shove` is a single videogame-style action. It spends a
  bonus action, uses passive target resistance, and applies Strength-scaled
  forced movement. The SRD shove text remains source reference material, not a
  second runtime action surface.
- `SRD-aligned`: entities with `uses_death_saves=True` fall unconscious at
  0 HP unless massive damage kills them, then roll death saving throws at turn
  start. Three successes stabilize, three failures kill, natural 1 adds two
  failures, natural 20 restores 1 HP, and damage at 0 HP adds failures.
- `Engine adaptation`: entities default to monster-style death. Without
  `uses_death_saves=True`, dropping to 0 HP applies `Dead` immediately.

## BaseAction Execution Spine

Every executable action enters through `BaseAction.apply()`:

1. reject templates;
2. check all effective costs;
3. create a declaration event;
4. validate into `EXECUTION`;
5. apply effects into `COMPLETION`;
6. apply costs after successful completion.

Costs are checked before validation but consumed after completion. That means a
failed range or line-of-sight validation does not spend an action.

Example EB-10-001:

```python
starting_actions = attacker.action_economy.actions.normalized_score
event = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
).apply()

assert event.canceled is True
assert attacker.action_economy.actions.normalized_score == starting_actions
```

Parity tests:

- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_001_invalid_attack_cancels_before_costs`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

## Attack Validation

`Attack._validate()` is a fixed pipeline:

1. `Attack.validate_range()` checks weapon reach, normal ranged range, and long
   ranged range;
2. `validate_line_of_sight()` requires the target UUID in the attacker's senses;
3. `Attack.check_ranged_conditions()` marks ranged attacks as threatened when a
   hostile creature is close enough to impose disadvantage;
4. the event phases to `EXECUTION`.

For ranged weapons, targets beyond normal range but inside long range are
allowed and marked as long range. Targets beyond long range cancel. For melee
weapons, targets farther than weapon reach cancel.

The standard attack path does not implement the full SRD "guess an unseen
target's location" flow. If the target is not visible to the attacker, the
validation cancels before the roll.

Melee reach example EB-10-015:

```python
adjacent_event = adjacent_attack._validate(adjacent_declaration)

assert adjacent_event.canceled is False
assert adjacent_event.phase == EventPhase.EXECUTION
assert adjacent_event.range.type == RangeType.REACH
assert adjacent_event.range.normal == 5

far_event = far_attack._validate(far_declaration)

assert far_event.canceled is True
assert "reach" in far_event.status_message.lower()
```

The current standard weapon factories use 5-foot melee reach. The validation
path reads that value from the equipped weapon range rather than from a separate
hard-coded melee constant.

Diagonal threat example EB-10-020:

```python
watcher = create_skeleton(position=(5, 5), faction="monsters")
diagonal_mover = create_goblin(position=(6, 6), faction="heroes")

assert watcher.senses.get_feet_distance(diagonal_mover.position) == 5
assert diagonal_mover.position in watcher.senses.get_threathened_positions()
assert diagonal_mover.is_threatened() is True

validated = diagonal_attack._validate(declaration)
assert validated.range.type == RangeType.REACH
assert validated.range.normal == 5

Move(source_entity_uuid=diagonal_mover.uuid, end_position=(8, 8)).apply()
assert watcher.action_economy.reactions.normalized_score == 0
```

`Senses.get_distance()` floors Euclidean grid distance before converting to
feet, so a one-cell diagonal has distance 1 grid unit and 5 feet. Threatened
positions include diagonals when propagation can cross that diagonal transition,
and leaving that diagonal threatened cell can trigger the same opportunity
attack path as orthogonal movement.

Example EB-10-011:

```python
archer = create_goblin_archer(position=(0, 0), faction="heroes")
normal_target = create_skeleton(position=(16, 0), faction="monsters")
long_target = create_skeleton(position=(17, 0), faction="monsters")
beyond_target = create_skeleton(position=(65, 0), faction="monsters")

normal_event = normal_attack._validate(normal_declaration)
assert normal_event.is_long_range is False
assert normal_event.range.normal == 80
assert normal_event.range.long == 320

beyond_event = Attack(..., target_entity_uuid=beyond_target.uuid).apply()
assert beyond_event.canceled is True

with fixed_dice(19, 2):
    long_event = Attack(..., target_entity_uuid=long_target.uuid).apply()

assert long_event.is_long_range is True
assert long_event.dice_roll.advantage_status == AdvantageStatus.DISADVANTAGE
```

Threatened ranged example EB-10-013:

```python
archer = create_goblin_archer(position=(5, 5), faction="heroes")
create_goblin(position=(5, 6), faction="monsters")
target = create_skeleton(position=(15, 5), faction="monsters")

with fixed_dice(18, 3):
    threatened_event = Attack(..., target_entity_uuid=target.uuid).apply()

assert threatened_event.is_long_range is False
assert threatened_event.is_threatened is True
assert threatened_event.dice_roll.results == [18, 3]
assert threatened_event.dice_roll.advantage_status == AdvantageStatus.DISADVANTAGE

target = create_skeleton(position=(22, 5), faction="monsters")
combined_event = Attack(..., target_entity_uuid=target.uuid).apply()

assert combined_event.is_long_range is True
assert combined_event.is_threatened is True
assert combined_event.dice_roll.advantage_status == AdvantageStatus.DISADVANTAGE
```

Multiple sources of disadvantage do not make the d20 roll worse than
disadvantage. The combined long-range-and-threatened case still rolls two d20s
and selects the lower one.

Parity tests:

- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_011_ranged_range_flags_and_disadvantage`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_013_threatened_ranged_attacks_roll_with_disadvantage`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_015_melee_reach_validation_uses_weapon_range`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_020_diagonal_adjacency_counts_as_five_foot_threat`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_020_diagonal_adjacency_counts_as_five_foot_threat`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

## Attack Roll, Damage Roll, And Damage Application

On execution, the engine temporarily sets source and target cross-context:

- the attacker targets the defender;
- the defender targets the attacker;
- `attack_bonus.set_from_target(ac)` and `ac.set_from_target(attack_bonus)` pull
  outgoing target modifiers into the roll context.

This temporary context must be cleaned whether the attack hits, misses, or is
canceled. EB-10-009 pins that invariant after a regression where missed attacks
left both entities targeting each other.

Attack then:

1. creates a d20 roll through `Entity.roll_d20()`;
2. computes `AttackOutcome`;
3. on miss, still phases through `EFFECT` and `COMPLETION`;
4. on hit, rolls each `Damage`, fires a `DAMAGE_ROLL_RESULT` event, applies
   handler-modified final rolls, then calls `target.receive_damage()`.

Example EB-10-002:

```python
hit_modifier = force_attack_hit(attacker)

with fixed_dice(10, 4):
    event = Attack(
        source_entity_uuid=attacker.uuid,
        target_entity_uuid=target.uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
    ).apply()

assert event.damage_rolls
assert EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
assert EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
```

Critical hit example EB-10-003:

```python
hit_modifier = force_attack_hit(attacker)
crit_modifier = force_attack_crit(attacker)

with fixed_dice(10, 3, 4):
    event = Attack(...).apply()

assert event.attack_outcome.value == "Crit"
assert event.damage_rolls[0].results == [3, 4]
```

Miss cleanup example EB-10-009:

```python
miss_modifier = force_attack_miss(attacker)

with fixed_dice(10):
    event = Attack(...).apply()

assert event.attack_outcome.value == "Miss"
assert attacker.target_entity_uuid is None
assert target.target_entity_uuid is None
```

Natural roll example EB-10-010:

```python
target.equipment.ac_bonus.self_static.add_value_modifier(
    NumericalModifier.create(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        name="Unreachable AC",
        value=100,
    )
)

with fixed_dice(20):
    high_ac_event = Attack(...).apply()

assert high_ac_event.dice_roll.results == [20]
assert high_ac_event.attack_outcome == AttackOutcome.CRIT
assert EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
```

EB-10-010 records both attack-roll natural-face boundaries: natural 20 produces
`CRIT` and deals damage even against unreachable AC, while natural 1 produces
`CRIT_MISS` and emits no damage.

Mixed damage examples EB-10-016 and EB-10-019:

```python
weapon.extra_damage_dices.append(6)
weapon.extra_damage_dices_numbers.append(1)
weapon.extra_damage_bonus.append(ModifiableValue.create(..., base_value=0))
weapon.extra_damage_type.append(DamageType.FIRE)

with fixed_dice(10, 4, 6):
    event = Attack(...).apply()

assert [roll.total for roll in event.damage_rolls] == [6, 6]
assert [damage.damage_type for damage in event.damages] == [
    DamageType.SLASHING,
    DamageType.FIRE,
]
assert hp_before - target.get_hp() == 9
```

The target in EB-10-016 resists slashing only. The attack rolls 6 slashing and
6 fire damage. The engine halves only the slashing component to 3 and leaves the
fire component at 6, for 9 total HP loss.

EB-10-019 applies the same mixed 6 slashing plus 6 fire attack to slashing
vulnerability and slashing immunity:

```python
vulnerable_damage = run_mixed_attack(vulnerabilities=[DamageType.SLASHING])
immune_damage = run_mixed_attack(immunities=[DamageType.SLASHING])

assert vulnerable_damage == 18
assert immune_damage == 6
```

Slashing vulnerability doubles only the slashing component, and slashing
immunity cancels only the slashing component.

Parity tests:

- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_002_attack_hit_rolls_damage_and_consumes_action`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_003_critical_hit_doubles_weapon_damage_dice`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_009_attack_target_context_is_temporary_on_miss`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_010_natural_rolls_drive_crit_and_crit_miss_outcomes`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_016_mixed_weapon_damage_applies_resistance_per_component`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_019_mixed_weapon_damage_applies_vulnerability_and_immunity_per_component`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

## Movement Is Stepwise

`Move` is not an atomic position update. It computes or receives a path, then
walks each cell transition:

1. verify the next transition is still legal;
2. compute the step's terrain movement cost;
3. check remaining movement;
4. fire a `StepMovementEvent` at `EFFECT`;
5. if not canceled, update the entity position;
6. complete the step event;
7. consume movement for the step.

The event queue stores both `EFFECT` and `COMPLETION` versions of each step. For
physical-step counting, use completed `STEP_MOVEMENT` events.

Example EB-10-004:

```python
event = Move(source_entity_uuid=mover.uuid, end_position=(5, 8)).apply()

completed_steps = [
    step
    for step in EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
    if step.source_entity_uuid == mover.uuid and step.phase == EventPhase.COMPLETION
]

assert mover.position == (5, 8)
assert len(completed_steps) == 3
```

Parity tests:

- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_004_move_consumes_movement_per_step_and_records_step_events`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

## Opportunity Attacks

Opportunity attacks are implemented by an `EventHandler` on
`EventType.STEP_MOVEMENT` at `EventPhase.EFFECT`.

`opportunity_attack_processor()` exits early when:

- either entity is missing;
- the mover and reaction source are the same entity;
- the mover is an ally;
- the mover has `Disengaging`.

Otherwise, it compares the step's `from_position` and `to_position` against the
reaction source's threatened positions. If the mover leaves the threatened set,
the handler creates an `Attack` named `"Opportunity Attack"` with a reaction cost
and applies it as a child of the step event.

Example EB-10-005:

```python
add_opportunity_attack_handler(attacker)

with fixed_dice(10, 4):
    move_event = Move(source_entity_uuid=mover.uuid, end_position=(5, 10)).apply()

assert mover.get_hp() < mover_hp_before
assert attacker.action_economy.reactions.normalized_score == 0
```

Lethal opportunity attack example EB-10-017:

```python
add_opportunity_attack_handler(watcher)

with fixed_dice(10, 6, 6):
    move_event = Move(source_entity_uuid=mover.uuid, end_position=(5, 10)).apply()

assert "Dead" in mover.active_conditions
assert mover.position == (5, 6)
assert move_event.end_position == (5, 6)
assert "partial" in move_event.status_message.lower()
assert len({step.uuid for step in effect_steps}) == 1
assert not completed_steps
```

The step event reaches `EFFECT`, giving the opportunity-attack handler a chance
to attack. If that attack kills or incapacitates the mover, `Move` interrupts
before `Entity.update_entity_position()` and does not complete the step event.
The mover remains in the origin cell it was leaving.

Disengage example EB-10-006:

```python
Disengage(source_entity_uuid=mover.uuid).apply()
Move(source_entity_uuid=mover.uuid, end_position=(5, 10)).apply()

assert mover.get_hp() == mover_hp_before
assert attacker.action_economy.reactions.normalized_score == 1
```

Repeat trigger example EB-10-014:

```python
add_opportunity_attack_handler(watcher)

with fixed_dice(10, 4, 10, 4):
    Move(source_entity_uuid=first_mover.uuid, end_position=(5, 10)).apply()
    Move(source_entity_uuid=second_mover.uuid, end_position=(10, 5)).apply()

completed_oas = [
    event
    for event in EventQueue.get_events_by_type(EventType.ATTACK)
    if event.name == "Opportunity Attack" and event.phase == EventPhase.COMPLETION
]

assert first_mover.get_hp() < first_hp_before
assert second_mover.get_hp() == second_hp_before
assert watcher.action_economy.reactions.normalized_score == 0
assert len(completed_oas) == 1
```

The second mover still creates `STEP_MOVEMENT` events, but
`opportunity_attack_processor()` only registers and applies a reaction attack
when `reaction_attack.pre_validate()` passes. With the watcher reaction already
spent, no second opportunity attack enters the event queue.

Parity tests:

- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_005_opportunity_attack_uses_reaction_on_step_movement`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_017_lethal_opportunity_attack_stops_before_leaving_reach`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_006_disengage_prevents_opportunity_attack`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_014_opportunity_attack_reaction_limits_repeat_triggers`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

## Jump And Opportunity Attacks

`Jump` uses `TargetType.POSITION_LOS` and validates the landing position by
visibility, jump range, available movement, walkability, and propagation
raycast. Once execution starts, it walks a straight-line cell path and emits
`STEP_MOVEMENT` events for each traversed cell.

Unlike normal `Move`, jump does not check intermediate cells for walkability;
the creature is airborne. The step events still give opportunity-attack handlers
the same reaction surface as normal movement. Disengage suppresses those
handlers because they check the moving entity's active conditions rather than
the concrete action class.

Example EB-10-012:

```python
add_opportunity_attack_handler(watcher)

with fixed_dice(10, 4):
    jump_event = Jump(source_entity_uuid=jumper.uuid, end_position=(5, 8)).apply()

assert jumper.position == (5, 8)
assert jumper.get_hp() < hp_before
assert watcher.action_economy.reactions.normalized_score == 0
assert len(completed_steps) == 3

Disengage(source_entity_uuid=jumper.uuid).apply()
Jump(source_entity_uuid=jumper.uuid, end_position=(5, 8)).apply()

assert jumper.get_hp() == hp_before
assert watcher.action_economy.reactions.normalized_score == 1
```

Lethal jump opportunity attack example EB-10-018:

```python
with fixed_dice(10, 6, 6):
    jump_event = Jump(source_entity_uuid=jumper.uuid, end_position=(5, 9)).apply()

assert jump_event.phase == EventPhase.COMPLETION
assert "Dead" in jumper.active_conditions
assert jumper.position == (5, 6)
assert jump_event.end_position == (5, 6)
assert len({step.uuid for step in effect_steps}) == 1
assert not completed_steps
```

`Jump` uses the same interrupt point as `Move`: the provoking step reaches
`EFFECT`, opportunity attacks can fire, and lethal results stop before the
position update. `Jump._apply_costs()` also leaves the completion event alone if
the jumper is already dead or incapacitated, avoiding a post-death bonus-action
cost error.

Parity tests:

- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_012_jump_uses_step_events_and_opportunity_attacks`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_018_lethal_jump_opportunity_attack_completes_without_cost_error`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

## Forced Movement And Shove

Forced movement uses `ForcedMovementEvent` with
`EventType.FORCED_MOVEMENT`. Opportunity attack handlers listen to
`STEP_MOVEMENT`, so they do not fire for a shove push.

`Shove` is the engine's single videogame shove action:

- target must be adjacent and visible;
- target weight must be no more than Strength score times 12;
- enemies resist with the better passive Athletics or Acrobatics DC;
- allies auto-succeed;
- success either knocks the target prone or pushes the target;
- push distance is 5 feet plus 5 feet per positive Strength modifier, capped at
  20 feet.

Example EB-10-007 uses an allied target to make the shove deterministic while
still proving forced movement does not trigger a nearby hostile watcher:

```python
add_opportunity_attack_handler(watcher)
event = Shove(source_entity_uuid=shover.uuid, target_entity_uuid=target.uuid).apply()

assert target.position != (3, 2)
assert target.get_hp() == target_hp_before
assert watcher.action_economy.reactions.normalized_score == 1
assert EventQueue.get_events_by_type(EventType.FORCED_MOVEMENT)
```

Forced terrain example EB-10-021:

```python
create_spike_zone({(7, 5), (10, 5)})
cursor = EventQueue.event_cursor()

with fixed_terrain_damage(2):
    shove_event = Shove(source_entity_uuid=shover.uuid, target_entity_uuid=target.uuid).apply()

indexed_events = EventQueue.iter_events_since(cursor)
new_events = [event for _, event in indexed_events]

assert shove_event.push_distance == 20
assert target.position == (10, 5)
assert target.action_economy.movement.normalized_score == target_movement_before
assert not any(event.event_type == EventType.STEP_MOVEMENT for event in new_events)
assert entered_effect_positions == [(7, 5), (8, 5), (9, 5), (10, 5)]
assert len(damage_completions) == 2
assert all(damage_event.parent_lineage == forced_event.lineage_uuid for damage_event in damage_completions)
assert len(forced_event.combat_log.sub_entries) == 2
assert target.get_hp() == hp_before - 8
```

This is cell-by-cell forced movement, not voluntary step movement. It ignores
the target's movement budget and does not emit `STEP_MOVEMENT`, so opportunity
attacks do not fire. Each 5-foot forced transition still updates the GridMap and
emits spatial entry events, so terrain and zone handlers see intermediate cells
such as `(7, 5)` as well as the final landing cell `(10, 5)`.

The forced movement event completes after those spatial effects resolve.
Damage caused by the traversed spike cells shares the forced movement lineage,
and the forced movement combat log collects the damage logs as sub-entries. This
matches the SRD rule that opportunity attacks do not trigger when another effect
moves a creature without using that creature's movement, action, or reaction,
while also matching hazard text such as Spike Growth's "moves into or within"
wording.

Parity tests:

- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_007_shove_forced_movement_does_not_trigger_opportunity_attack`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_021_forced_movement_traverses_terrain_without_step_costs`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

Videogame Shove example EB-10-022:

```python
actions_before = shover.action_economy.actions.normalized_score
bonus_actions_before = shover.action_economy.bonus_actions.normalized_score

with fixed_dice(15):
    event = Shove(source_entity_uuid=shover.uuid, target_entity_uuid=target.uuid).apply()

assert event.is_ally is False
assert event.dice_roll is not None
assert event.target_resistance_skill == "acrobatics"
assert event.push_distance == 20
assert event.end_position == (10, 5)
assert "Prone" not in target.active_conditions
assert shover.action_economy.actions.normalized_score == actions_before
assert shover.action_economy.bonus_actions.normalized_score == bonus_actions_before - 1
```

The local SRD text describes shove as a special melee attack made through the
Attack action, replacing one attack, using an active opposed Athletics contest,
and choosing between prone or a 5-foot push. The engine intentionally does not
expose that as a second action. EB-10-022 pins the chosen videogame behavior:
bonus-action cost, passive target resistance, and Strength-scaled forced
movement distance.

Parity test: `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_022_shove_uses_videogame_bonus_action_forced_movement`.

## Dash, Damage, Healing, And Death

Dash is implemented as a self-targeted action that applies `Dashing` for one
round, then consumes the action cost. The `Dashing` condition adds movement
through the action-economy value system rather than directly assigning a counter.

Damage and healing are event-backed:

- `Entity.receive_damage()` creates `TakeDamageEvent`, lets handlers intercept
  at `EFFECT`, applies effective damage through `Health.take_damage()`, then
  creates `DeathEvent` before the damage event completes when HP drops to 0 or
  below.
- `Entity.receive_healing()` creates `HealEvent`, applies healing unless blocked,
  caps through health state, and records actual healing.

Example EB-10-008:

```python
Dash(source_entity_uuid=hero.uuid).apply()
damage_taken = hero.receive_damage(7, DamageType.SLASHING, enemy.uuid)
healing_done = hero.receive_healing(3, source_entity_uuid=hero.uuid)
fatal_target.receive_damage(fatal_target.get_hp() + 5, DamageType.SLASHING, hero.uuid)

assert "Dashing" in hero.active_conditions
assert damage_taken == 7
assert healing_done == 3
assert "Dead" in fatal_target.active_conditions
assert EventQueue.get_events_by_type(EventType.DEATH)
```

Default monster-style death example EB-10-023:

```python
hp_before = monster_style.get_normal_hp()
damage_taken = monster_style.receive_damage(
    amount=hp_before,
    damage_type=DamageType.SLASHING,
    source_entity_uuid=enemy.uuid,
)

assert damage_taken == hp_before
assert monster_style.get_normal_hp() == 0
assert "Dead" in monster_style.active_conditions
assert "Incapacitated" in monster_style.active_conditions
assert "Unconscious" not in monster_style.active_conditions
assert not monster_style.uses_death_saves

with fixed_dice(20):
    turn_start = monster_style.on_turn_start()

assert turn_start.phase == EventPhase.COMPLETION
assert monster_style.get_normal_hp() == 0
assert "Dead" in monster_style.active_conditions
```

Player-style death-save example EB-10-025:

```python
hero = strong_entity("Dying Hero", (5, 5), "heroes", uses_death_saves=True)
hero.receive_damage(hero.get_normal_hp(), DamageType.SLASHING, enemy.uuid)

assert hero.get_normal_hp() == 0
assert hero.is_dying
assert "Dead" not in hero.active_conditions
assert "Unconscious" in hero.active_conditions

with fixed_dice(9):
    hero.on_turn_start(round_number=1, turn_index=0)
assert hero.death_save_failures == 1

with fixed_dice(10):
    hero.on_turn_start(round_number=2, turn_index=0)
assert hero.death_save_successes == 1

with fixed_dice(1):
    hero.on_turn_start(round_number=3, turn_index=0)
assert "Dead" in hero.active_conditions
```

Stabilization, natural 20, healing, damage-at-0, and massive damage are covered
by EB-10-026. It proves a natural 20 restores 1 normal HP and clears
`Unconscious`; three successes stabilize while keeping the creature
`Unconscious`; stable creatures skip later death saves; critical damage at
0 HP adds two failures and breaks stability; true healing clears counters and
`Unconscious`; and damage overflow equal to maximum HP still applies `Dead`.

Parity tests:

- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_008_dash_damage_healing_and_death_use_events`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_023_default_zero_hp_uses_monster_style_death`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_025_player_style_death_saves_roll_at_turn_start`
- `tests/engine_book/test_chapter_10_core_actions_combat.py::test_eb_10_026_player_style_stabilization_healing_and_massive_damage`
- `tests/engine_book/test_chapter_10_core_actions_combat.py`

## Findings And Follow-Up Coverage

The chapter tests now cover the minimum attack, movement, opportunity attack,
forced movement terrain traversal, HP, miss-cleanup, ranged range
bands, and natural d20 outcome flows. It also covers mixed-damage resistance
behavior, Jump's step-event and opportunity-attack behavior, videogame Shove,
default monster-style death, and opt-in player-style death saving
throws. Deeper coverage should still add:

- attacks against unseen guessed locations if that behavior is added;
- a concrete Medicine-check or healer's-kit action for stabilization.

## Documentation Hygiene Notes

- Chapter 10 hygiene reviewed `dnd/actions.py` core combat slices, `dnd/reactions.py`, and `dnd/items/test_reactions.py` from behavior, not inherited comments.
- The cleaned scope covers action-economy helper functions, `MovementEvent`/`Move`, `AttackEvent`/`Attack`, `Dash`, `Dodge`, `Disengage`, `JumpEvent`/`Jump`, `ShoveEvent`/`Shove`, opportunity-attack handler registration, and the Intercept/Dodge Roll reaction fixtures.
- Useful timing and routing intent was moved into Google-style docstrings and Pydantic field descriptions; inline narrative comments were removed from the cleaned Chapter 10 slices.
- Known behavior was preserved except for the now-fixed natural-20 attack outcome, mixed-damage resistance behavior, and lethal opportunity-attack interruption point.
- Hide, Stand Up/Drop Prone, SpellAction, and object/drop actions remain for their later domain chapters.
