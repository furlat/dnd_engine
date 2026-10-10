# 03. Dice, Rolls, And Result Processors

## Purpose

Dice are the bridge between value modifiers and event-driven gameplay. `Dice` turns a `ModifiableValue` bonus into a `DiceRoll`; roll-result events then give handlers a controlled place to replace or audit the roll before the higher-level action consumes it.

This chapter documents current behavior in `dnd/core/dice.py`, `dnd/core/events.py`, `dnd/entity.py`, and `dnd/actions.py`.

## Source Files Studied

- `dnd/core/dice.py`
- `dnd/core/events.py`
- `dnd/entity.py`
- `dnd/actions.py`
- `dnd/classes/feats.py`
- `dnd/classes/fighter.py`
- `dnd/spells/spell_utils.py`
- `examples/test_dice_processors.py`
- `examples/test_lucky_feat.py`
- `examples/test_great_weapon_fighting.py`
- `examples/test_brutal_critical.py`
- `examples/test_spell_crit_dice.py`
- `examples/test_shield_spell.py`
- `tests/engine_book/test_chapter_03_dice_events.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: ability checks, saving throws, and attack rolls are d20 rolls plus modifiers against a DC or AC. See `interactive_ruleset/Gameplay/Abilities.md` and `interactive_ruleset/Gameplay/Combat.md`.
- `SRD-aligned`: advantage and disadvantage roll two d20s and use the higher or lower result.
- `SRD-aligned`: attack natural 20 and natural 1 are special for attack outcome. Ordinary saving throws and ability checks use total-vs-DC and do not treat natural faces as automatic success or failure. Death saving throws are a separate combat subsystem exception covered outside this primitive dice chapter.
- `SRD-aligned`: critical hits double damage dice and add flat modifiers once.
- `SRD-aligned, 2014 local text`: Great Weapon Fighting rerolls 1s and 2s on eligible two-handed melee weapon damage dice and must use the new roll. The local `feats_srd5_2.md` text uses a newer "treat as 3" wording; the implemented fighter feature follows the class markdown in `interactive_ruleset/Classes/Fighter.md`.
- `Engine extension`: roll-result events let features replace d20 or damage rolls through handlers before the result is consumed.
- `Engine extension`: `LuckyFeature` is a point-spending, low-total, keep-better d20 processor. It is not the Halfling Lucky racial trait, which triggers on a natural 1 and must use the reroll.

## Dice Models

`RollType` classifies dice usage:

- `ATTACK`
- `SAVE`
- `CHECK`
- `DAMAGE`
- `HEAL`

`Dice` stores the dice expression:

- `count`: number of dice.
- `value`: die sides, limited to d4, d6, d8, d10, d12, or d20.
- `bonus`: a `ModifiableValue`.
- `roll_type`: the roll family.
- `attack_outcome`: required for damage rolls.
- `crit_extra_dice`: additional damage dice used on critical hits.

`DiceRoll` stores one rolled result:

- `roll_uuid`: UUID of this roll result.
- `dice_uuid`: UUID of the `Dice` object that produced it.
- `results`: one selected roll for ordinary d20s, both d20s for advantage/disadvantage, or one entry per damage/heal die.
- `total`: selected dice plus `bonus`.
- `bonus`: the normalized score from the bonus value.
- `advantage_status`, `critical_status`, `auto_hit_status`: status snapshots from the bonus value.
- `source_entity_uuid`, `target_entity_uuid`.
- optional `attack_outcome`.

`Dice.roll` is a cached property. Reading `.roll` twice on the same `Dice` object returns the same `DiceRoll`; it does not reroll.

## D20 Selection

For ordinary d20 rolls, `results` contains the single d20 result. With advantage or disadvantage, `results` contains both raw d20s and `total` uses the selected die.

Example EB-03-001:

```python
normal_bonus = ModifiableValue.create(
    source_entity_uuid=source_uuid,
    target_entity_uuid=target_uuid,
    base_value=3,
)
normal_roll = Dice(
    count=1,
    value=20,
    bonus=normal_bonus,
    roll_type=RollType.ATTACK,
).roll
assert normal_roll.results == [12]
assert normal_roll.total == 15

advantage_bonus.self_static.add_advantage_modifier(
    AdvantageModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        value=AdvantageStatus.ADVANTAGE,
    )
)
advantage_roll = Dice(
    count=1,
    value=20,
    bonus=advantage_bonus,
    roll_type=RollType.ATTACK,
).roll
assert advantage_roll.results == [4, 17]
assert advantage_roll.total == 20
```

The executable test patches `random.randint` to make the rolls deterministic.

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_001_d20_advantage_and_disadvantage_select_rolls`.

## D20 Outcome Semantics

`determine_attack_outcome()` currently returns the engine's shared `AttackOutcome` enum for attack rolls, saving throws, and skill checks. The caller's `roll_type` decides how natural d20 faces are interpreted:

- `RollType.ATTACK`: natural 1 is `CRIT_MISS`; natural 20 is `CRIT` regardless of target AC; other natural rolls at or above the critical threshold become `CRIT` when the attack otherwise hits.
- `RollType.SAVE` and `RollType.CHECK`: the engine compares `DiceRoll.total` to the DC. Natural 1 and natural 20 have no automatic effect.

Example EB-03-007:

```python
attack_roll = DiceRoll(
    roll_type=RollType.ATTACK,
    results=[1],
    total=101,
    bonus=100,
    ...
)
save_roll = attack_roll.model_copy(
    update={"roll_uuid": uuid4(), "roll_type": RollType.SAVE}
)
natural_20_attack_roll = attack_roll.model_copy(
    update={
        "roll_uuid": uuid4(),
        "results": [20],
        "total": 20,
        "bonus": 0,
    }
)
check_roll = attack_roll.model_copy(
    update={
        "roll_uuid": uuid4(),
        "roll_type": RollType.CHECK,
        "results": [20],
        "total": 20,
        "bonus": 0,
    }
)

assert determine_attack_outcome(attack_roll, 15) == AttackOutcome.CRIT_MISS
assert determine_attack_outcome(natural_20_attack_roll, 120) == AttackOutcome.CRIT
assert determine_attack_outcome(save_roll, 15) == AttackOutcome.HIT
assert determine_attack_outcome(check_roll, 30) == AttackOutcome.MISS
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_007_natural_faces_are_special_only_for_attack_outcomes`.

Attack outcome also consumes the roll's auto-hit and critical statuses. The current precedence is:

- `AutoHitStatus.AUTOMISS` wins first and returns `MISS`, even on a natural 20.
- `AutoHitStatus.AUTOHIT` guarantees at least `HIT`, even on a natural 1.
- `CriticalStatus.NOCRIT` downgrades otherwise-critical hits to ordinary hits.
- `CriticalStatus.AUTOCRIT` upgrades a hit or auto-hit to `CRIT`, but does not make a missing non-auto-hit roll hit.
- Lowered critical thresholds upgrade only attacks that otherwise hit, unless paired with `AUTOHIT`.

Example EB-03-009:

```python
assert determine_attack_outcome(
    make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=20,
        total=20,
        auto_hit_status=AutoHitStatus.AUTOMISS,
    ),
    10,
) == AttackOutcome.MISS

assert determine_attack_outcome(
    make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=1,
        total=1,
        auto_hit_status=AutoHitStatus.AUTOHIT,
    ),
    30,
) == AttackOutcome.HIT

assert determine_attack_outcome(
    make_d20_roll(
        source_uuid,
        target_uuid,
        natural_roll=20,
        total=20,
        critical_status=CriticalStatus.NOCRIT,
    ),
    30,
) == AttackOutcome.HIT
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_009_attack_outcome_status_precedence_matrix`.

## Critical Damage

Damage and healing rolls use one entry in `results` per die. For critical damage, the engine doubles the base dice count and then adds `crit_extra_dice`. The flat bonus is added once.

Example EB-03-002:

```python
roll = Dice(
    count=2,
    value=6,
    bonus=damage_bonus,
    roll_type=RollType.DAMAGE,
    attack_outcome=AttackOutcome.CRIT,
    crit_extra_dice=1,
).roll

assert roll.results == [1, 2, 3, 4, 5]
assert roll.bonus == 4
assert roll.total == 19
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_002_critical_damage_doubles_dice_and_adds_bonus_once`.

## D20 Result Events

`Entity.roll_d20()` rolls first, then creates a roll-result event:

- `AttackD20RollResultEvent`
- `SavingThrowD20RollResultEvent`
- `SkillCheckD20RollResultEvent`
- or base `D20RollResultEvent` as a fallback

The event phases to `EFFECT`, where handlers may call `replace_roll()`. The method records `final_roll` and appends a modification entry. Consumers should use `get_effective_roll()` to read the final version.

When multiple d20 handlers replace the same roll, later handlers receive the
current effective roll. The audit entry records the previous effective total
and the new total. Queue discovery runs simple exact triggers for the event's
actual type and phase before filtered exact triggers; a broad
`D20_ROLL_RESULT` handler does not catch an `ATTACK_D20_ROLL_RESULT` event.

`Entity.roll_d20_event()` returns the same effective roll plus the `EFFECT`-phase event without completing it. That is useful when a caller needs to add child events before completion. The event subclass is specific only when the required context is present; save rolls without `ability_name` and check rolls without `skill_name` fall back to `D20RollResultEvent`.

Example EB-03-003:

```python
def replace_low_roll(event, source_uuid):
    replacement = original_roll.model_copy(
        update={"roll_uuid": uuid4(), "results": [18], "total": 20}
    )
    event.replace_roll(replacement, "Engine Book", "replace low d20")
    return event

handler = EventHandler(
    source_entity_uuid=source_uuid,
    trigger_conditions=[
        Trigger(
            event_type=EventType.D20_ROLL_RESULT,
            event_phase=EventPhase.EFFECT,
        )
    ],
    event_processor=replace_low_roll,
)
EventQueue.add_event_handler(handler)

event = D20RollResultEvent(
    source_entity_uuid=source_uuid,
    target_entity_uuid=target_uuid,
    roll_type=RollType.CHECK,
    roll=original_roll,
    original_roll=original_roll,
    bonus=bonus,
    phase=EventPhase.DECLARATION,
)
event = event.phase_to(EventPhase.EFFECT)

assert event.get_effective_roll().results == [18]
assert event.get_effective_roll().total == 20
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_003_d20_result_event_handlers_replace_effective_roll`.

Example EB-03-008:

```python
attack_roll, attack_event = actor.roll_d20_event(
    bonus,
    RollType.ATTACK,
    weapon_slot=WeaponSlot.MELEE_MAIN,
)
assert isinstance(attack_event, AttackD20RollResultEvent)
assert attack_event.event_type == EventType.ATTACK_D20_ROLL_RESULT

save_roll, save_event = actor.roll_d20_event(
    bonus,
    RollType.SAVE,
    ability_name="dexterity",
)
assert isinstance(save_event, SavingThrowD20RollResultEvent)

fallback_roll, fallback_event = actor.roll_d20_event(bonus, RollType.SAVE)
assert isinstance(fallback_event, D20RollResultEvent)
assert not isinstance(fallback_event, SavingThrowD20RollResultEvent)
```

The executable test also registers an `ATTACK_D20_ROLL_RESULT` handler and proves `Entity.roll_d20()` completes the event and returns the replacement effective roll.

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_008_entity_roll_d20_uses_specific_result_events`.

Example EB-03-019:

```python
def simple_exact_handler(event, source_uuid):
    assert event.get_effective_roll().total == 5
    event.replace_roll(replacement(event, 12), "Simple Exact Attack", "raise simple")
    return event

def filtered_source_handler(event, source_uuid):
    assert event.get_effective_roll().total == 12
    event.replace_roll(replacement(event, 15), "Filtered Source Attack", "raise source")
    return event

def filtered_target_handler(event, source_uuid):
    assert event.get_effective_roll().total == 15
    event.replace_roll(replacement(event, 18), "Filtered Target Attack", "raise target")
    return event

effect_event = attack_result_event.phase_to(EventPhase.EFFECT)
assert call_order == ["simple", "source", "target"]
assert effect_event.get_effective_roll().total == 18
assert effect_event.roll_modifications == [
    ("Simple Exact Attack", "raise simple (5 → 12)"),
    ("Filtered Source Attack", "raise source (12 → 15)"),
    ("Filtered Target Attack", "raise target (15 → 18)"),
]
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_019_d20_replacements_chain_after_simple_exact_handlers`.

## Damage Result Events

Attack damage rolls are collected in `DamageRollResultEvent` after damage dice are rolled and before damage is applied.

The event carries:

- `original_rolls`: immutable audit input.
- `final_rolls`: mutable list consumed by the attack after handlers run.
- `roll_modifications`: audit tuples with handler name, roll index, old total, new total, and reason.

Example EB-03-004:

```python
def replace_damage(event, source_uuid):
    event.replace_roll(0, replacement_roll, "Engine Book", "raise damage")
    return event

event = DamageRollResultEvent(
    source_entity_uuid=source_uuid,
    target_entity_uuid=target_uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    attack_outcome=AttackOutcome.HIT,
    damages=[],
    original_rolls=[original_roll],
    final_rolls=[original_roll],
    phase=EventPhase.DECLARATION,
)
event = event.phase_to(EventPhase.EFFECT)

assert event.original_rolls == [original_roll]
assert event.final_rolls == [replacement_roll]
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_004_damage_result_event_replaces_final_rolls_only`.

Multiple damage handlers chain through the same `final_rolls` list. When a
handler returns a modified event, the queue stores that new version and later
handlers see the replacement totals, while `original_rolls` remain unchanged.

Example EB-03-012:

```python
def first_handler(event, source_uuid):
    event.replace_roll(0, first_roll, "First Handler", "raise to three")
    return event.model_copy(update={"modified": True})

def second_handler(event, source_uuid):
    assert event.final_rolls[0].results == [3]
    event.replace_roll(0, second_roll, "Second Handler", "raise to five")
    return event.model_copy(update={"modified": True})

effect_event = event.phase_to(EventPhase.EFFECT)
assert effect_event.original_rolls == [original_roll]
assert effect_event.final_rolls == [second_roll]
assert effect_event.roll_modifications == [
    ("First Handler", 0, 1, 3, "raise to three"),
    ("Second Handler", 0, 3, 5, "raise to five"),
]
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_012_damage_result_handlers_chain_in_dispatch_order`.

The real `Attack` pipeline consumes `DamageRollResultEvent.final_rolls`, not
the original damage rolls. EB-03-014 forces a greatsword hit, rolls `[1, 2]`,
lets Great Weapon Fighting replace them with `[5, 1]`, and proves both
`AttackEvent.damage_rolls` and target HP loss use the final total.

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_014_real_attack_pipeline_applies_modified_damage_rolls`.

The attack d20 result event also carries the weapon slot used by the attack, so
roll-result features can distinguish main-hand, off-hand, melee, and ranged
contexts without reconstructing them from later damage events.

Example EB-03-016:

```python
attack_event = Attack(
    source_entity_uuid=attacker.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
).apply()

d20_event = completed_attack_d20_events[-1]
assert d20_event.weapon_slot == WeaponSlot.MELEE_MAIN
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_016_attack_d20_slot_and_gwf_extra_packet_boundaries`.

## Lucky-Style D20 Processors

`LuckyFeature` registers one handler with exact triggers for attack, save, and
check d20 result events. It grants three `luck_points`, spends one point when
the original d20 total is below 10, rerolls with the same `ModifiableValue`
bonus, and keeps the new roll only if it improves the total. A spent point with
a worse reroll is still spent, but the event has no replacement audit because
the effective roll did not change.

Example EB-03-011:

```python
actor.add_condition(LuckyFeature(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))

with fixed_randint(5, 18):
    improved_roll = actor.roll_d20(bonus, RollType.CHECK, skill_name="athletics")

assert improved_roll.total == 18
assert actor.action_economy.resources["luck_points"].current == 2
assert improved_event.original_roll.results == [5]
assert improved_event.get_effective_roll().results == [18]

with fixed_randint(4, 1):
    worse_reroll = actor.roll_d20(bonus, RollType.CHECK, skill_name="athletics")

assert worse_reroll.total == 4
assert actor.action_economy.resources["luck_points"].current == 1
assert worse_event.roll_modifications == []
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_011_lucky_processor_spends_and_replaces_d20_deterministically`.

## Great Weapon Fighting Processor

Great Weapon Fighting is implemented as a `DAMAGE_ROLL_RESULT` handler. It is
eligible only for the handler owner's attacks with melee weapons that are
wielded with two hands:

- `TWO_HANDED` melee weapons qualify.
- `VERSATILE` melee weapons qualify only from `MELEE_MAIN` while the melee off
  hand is empty.
- Ranged weapons, one-handed weapons, and versatile weapons used with a shield
  do not qualify.

When eligible, it rerolls only the primary weapon damage packet, preserving
later packets such as radiant bonus damage, smite-like dice, size dice, or
spell riders. Rerolled dice must use the new value, even if the new value is
also a 1 or 2.

Example EB-03-013:

```python
low_roll = make_damage_roll(fighter.uuid, target.uuid, [1, 2, 5], bonus=0)
eligible_event = DamageRollResultEvent(
    source_entity_uuid=fighter.uuid,
    target_entity_uuid=target.uuid,
    weapon_slot=WeaponSlot.MELEE_MAIN,
    attack_outcome=AttackOutcome.HIT,
    original_rolls=[low_roll],
    final_rolls=[low_roll],
).phase_to(EventPhase.EFFECT)

assert eligible_event.final_rolls[0].results == [1, 6, 5]
assert eligible_event.roll_modifications == [
    ("Great Weapon Fighting", 0, 8, 12, "Rerolled: 1→1, 2→6")
]
```

The same executable example asserts no modification for no-low-dice, ranged,
and one-handed cases.

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_013_great_weapon_fighting_filters_damage_result_events`.

Example EB-03-016 also proves a real attack with base `2d6` plus an extra `1d4`
damage packet rerolls the `[1, 2]` greatsword dice and leaves the extra `[1]`
d4 untouched.

Example EB-03-017 pins the versatile weapon boundary:

```python
attacker.equipment.equip(create_longsword(attacker.uuid), WeaponSlot.MELEE_MAIN)
attacker.equipment.equip(create_wooden_shield(attacker.uuid), WeaponSlot.MELEE_OFF)

shielded_event = DamageRollResultEvent(..., final_rolls=[shielded_low_roll]).phase_to(EventPhase.EFFECT)
assert shielded_event.roll_modifications == []

attacker.equipment.unequip(WeaponSlot.MELEE_OFF)
unshielded_event = DamageRollResultEvent(..., final_rolls=[unshielded_low_roll]).phase_to(EventPhase.EFFECT)
assert unshielded_event.final_rolls[0].results == [7]
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_017_gwf_requires_versatile_weapon_to_be_two_handed`.

## Heal Result Events

Healing dice use `HealRollResultEvent`, mirroring the damage-result pattern for healing effects that maximize or replace healing rolls. The utility `fire_heal_roll_result()` rolls the `Healing` packet, fires the `HEAL_ROLL_RESULT` event at `EFFECT`, completes it, and returns the completed event's `final_roll`.

Example EB-03-010:

```python
def maximize_healing(event, source_uuid):
    replacement = event.final_roll.model_copy(
        update={"roll_uuid": uuid4(), "results": [8, 8], "total": 19}
    )
    event.replace_roll(replacement, "Engine Book", "maximize healing")
    return event

EventQueue.add_event_handler(
    EventHandler(
        source_entity_uuid=caster_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.HEAL_ROLL_RESULT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=caster_uuid,
            )
        ],
        event_processor=maximize_healing,
    )
)

final_roll = fire_heal_roll_result(
    caster_uuid,
    target_uuid,
    healing,
    parent_event,
    "Engine Book Heal",
)
assert final_roll.results == [8, 8]
assert final_roll.total == 19
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_010_heal_roll_result_handlers_replace_final_roll`.

Example EB-03-015:

```python
final_roll = fire_heal_roll_result(
    caster_uuid,
    target_uuid,
    healing,
    parent_event,
    "Engine Book Heal Completion",
)

heal_events = EventQueue.get_events_by_type(EventType.HEAL_ROLL_RESULT)
assert [event.phase for event in heal_events] == [
    EventPhase.DECLARATION,
    EventPhase.EFFECT,
    EventPhase.COMPLETION,
]
assert heal_events[-1].final_roll is final_roll
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_015_heal_roll_result_events_complete_after_handlers`.

## Heal Application Events

`HealRollResultEvent` decides the rolled amount; `HealEvent` decides whether
that amount is actually applied to HP. `Entity.receive_healing()` sends the
`HealEvent` through `DECLARATION`, `EXECUTION`, and `EFFECT` before changing
HP. The processed `total_healing` on the EFFECT event is the amount consumed by
`Health.heal()`. If a handler cancels the `HealEvent`, no HP changes and the
completed event remains canceled with `actual_healing == 0`.

Example EB-03-018:

```python
def reduce_healing(event, source_uuid):
    return event.model_copy(
        update={
            "total_healing": 4,
            "modified": True,
            "status_message": "Engine Book reduced healing",
        }
    )

actual_healing = target.receive_healing(
    amount=9,
    source_entity_uuid=healer_uuid,
    source_description="Engine Book reduced heal",
)

assert actual_healing == 4
assert heal_completion.total_healing == 4
assert heal_completion.actual_healing == 4

def cancel_healing(event, source_uuid):
    return event.cancel(status_message="Engine Book canceled healing")

canceled_healing = blocked_target.receive_healing(
    amount=9,
    source_entity_uuid=blocking_healer_uuid,
)
assert canceled_healing == 0
assert canceled_completion.canceled is True
assert canceled_completion.actual_healing == 0
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_018_heal_event_effect_handlers_define_applied_healing`.

## Dice Registries

`Dice` and `DiceRoll` each maintain their own registry. A dice expression and the roll result it produced are separate objects with separate UUIDs.

Example EB-03-005:

```python
dice = Dice(count=1, value=20, bonus=bonus, roll_type=RollType.CHECK)
roll = dice.roll

assert Dice.get(dice.uuid) is dice
assert DiceRoll.get(roll.roll_uuid) is roll
assert Dice.get(roll.roll_uuid) is None
assert DiceRoll.get(dice.uuid) is None
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_005_dice_and_rolls_are_registered_by_uuid`.

## Cached Rolls And Exact Triggers

`Dice.roll` is cached. Use a new `Dice` instance for a new roll.

Event trigger matching is exact by `EventType`. A handler for `D20_ROLL_RESULT` does not catch `ATTACK_D20_ROLL_RESULT`; broad d20 features must register for the specific event types they want to observe.

Example EB-03-006:

```python
dice = Dice(count=1, value=20, bonus=bonus, roll_type=RollType.CHECK)
first_roll = dice.roll
second_roll = dice.roll
assert first_roll is second_roll

attack_event = AttackD20RollResultEvent(
    source_entity_uuid=source_uuid,
    target_entity_uuid=target_uuid,
    roll=first_roll,
    original_roll=first_roll,
    bonus=bonus,
    phase=EventPhase.DECLARATION,
)
attack_event.phase_to(EventPhase.EFFECT)

assert trigger_count == {"base": 0, "attack": 1}
```

Parity test: `tests/engine_book/test_chapter_03_dice_events.py::test_eb_03_006_dice_roll_is_cached_and_event_triggers_are_exact`.

## Current Edge Cases And Constraints

- `Dice.roll` is cached; repeated access does not reroll.
- Trigger matching is exact by `event_type`; base d20 handlers do not catch attack/save/check subclasses unless they register those types too.
- `Dice` validates that non-damage and non-heal rolls have only one die.
- Damage rolls require `attack_outcome`; non-damage rolls reject `attack_outcome`.
- Attack natural 1/20 outcome is determined by `determine_attack_outcome()`, not by `Dice`.
- `CriticalStatus.NOCRIT` is consumed by `determine_attack_outcome()` and suppresses critical outcomes without canceling the hit itself.
- `D20RollResultEvent.replace_roll()` stores one final roll and audits against the previous effective roll; `DamageRollResultEvent.replace_roll()` mutates one indexed final roll.
- Damage/heal result processors should preserve original rolls for audit and replace final rolls for consumption.
- `HealEvent` effect handlers can reduce or cancel the healing application before HP changes.

## Coverage Status

Existing baseline coverage touches this subsystem through higher-level features:

- `examples/test_dice_processors.py` tests damage-roll utility functions such as maximize, substitute, floor, ceiling, and reroll helpers.
- `examples/test_great_weapon_fighting.py` tests damage dice reroll behavior through a fighter feature.
- `examples/test_lucky_feat.py` tests d20 replacement behavior through Lucky.
- `examples/test_brutal_critical.py` tests extra critical damage dice.
- `examples/test_improved_critical.py` tests attack outcome behavior with advantage/disadvantage and critical thresholds.

The direct parity coverage for this chapter is:

- `tests/engine_book/test_chapter_03_dice_events.py`

Status: `covered` for EB-03-001 through EB-03-019.

## Hygiene Notes

The dice and roll-result hygiene pass reviewed `dnd/core/dice.py`, the
roll-result event tail in `dnd/core/events.py`, and the scoped call sites in
`dnd/entity.py` and `dnd/actions.py` where d20 result events, damage result
events, `TakeDamageEvent`, and `HealEvent` are created or consumed. The current
code now keeps those contracts in Google-style docstrings and Pydantic field
descriptions rather than section banners, step comments, or implementation
history comments.

Broader action/entity hygiene remains for later chapters, but it is no longer a
Chapter 03 roll-result blocker.
