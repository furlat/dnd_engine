# 02. Modifiers And Value Channels

## Purpose

Modifiers and values are the engine's primitive stat machinery. They turn rules such as bonuses, penalties, advantage, critical immunity, automatic misses, damage types, and resistance into composable objects that higher-level systems can attach to entities, items, actions, conditions, and spells.

This chapter documents the implementation behavior in `dnd/core/modifiers.py` and `dnd/core/values.py`. Comments and older docs were treated as navigation only.

## Source Files Studied

- `dnd/core/modifiers.py`
- `dnd/core/values.py`
- `tests/engine_book/test_chapter_02_modifiable_values.py`
- `examples/test_dodging_attack.py`
- `examples/test_barbarian_rage.py`
- `examples/test_new_spells.py`
- `examples/test_serialization.py`
- `examples/test_protection.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: the engine models numerical bonuses/penalties on checks, saves, attacks, AC, and damage. See `interactive_ruleset/Gameplay/Abilities.md` and `interactive_ruleset/Gameplay/Combat.md`.
- `SRD-aligned`: advantage and disadvantage are represented as a final ternary roll state: advantage, disadvantage, or neither. See `interactive_ruleset/Gameplay/Abilities.md`.
- `Engine adaptation`: the engine computes advantage by summing `+1` and `-1` modifiers. This means multiple advantage sources can outvote one disadvantage source. The SRD generally treats any advantage plus any disadvantage as canceling to a normal roll.
- `SRD-aligned`: resistance and vulnerability are tracked by damage type. See `interactive_ruleset/Gameplay/Combat.md`.
- `Engine extension`: `CriticalModifier`, `AutoHitModifier`, size modifiers, damage type modifiers, and target-propagation channels are engine primitives used to represent multiple SRD and non-SRD effects.

## Modifier Classes

Concrete modifiers are `BaseObject` subclasses. They carry their own UUID, source entity, optional target entity, and a payload.

| Modifier | Payload | Aggregation |
|---|---|---|
| `NumericalModifier` | integer value | summed, then constrained |
| `AdvantageModifier` | `ADVANTAGE`, `DISADVANTAGE`, or `NONE` | converted to `+1`, `-1`, or `0` and summed |
| `CriticalModifier` | `AUTOCRIT`, `NOCRIT`, or `NONE` | `NOCRIT` wins over `AUTOCRIT` |
| `AutoHitModifier` | `AUTOHIT`, `AUTOMISS`, or `NONE` | `AUTOMISS` wins over `AUTOHIT` |
| `SizeModifier` | `Size` enum | largest or smallest by configured priority |
| `DamageTypeModifier` | `DamageType` enum | most common damage types |
| `ResistanceModifier` | resistance status and damage type | summed per damage type |

Each main modifier family has a contextual variant. Contextual modifiers hold a callable and are evaluated with:

```python
callable(source_entity_uuid, target_entity_uuid, context)
```

If the callable raises an exception during normal `evaluate()`, the modifier is treated as inactive for that evaluation. Results are cached by source, target, and event lineage.

## Value Containers

The value system has three container layers:

- `StaticValue`: holds always-on modifier dictionaries.
- `ContextualValue`: holds contextual modifier dictionaries and evaluates them when computed fields are read.
- `ModifiableValue`: combines static, contextual, outgoing, and imported target channels into the public value object used throughout entities and blocks.

`ModifiableValue.create()` creates a base `NumericalModifier` inside `self_static`, named with the `"_base_value"` suffix. `get_base_modifier()` finds that base modifier later.

## Six Channels

`ModifiableValue` has four primary channels and two copied target channels:

| Channel | Meaning | Included in own score/advantage |
|---|---|---|
| `self_static` | always-on modifiers affecting this value's owner | yes |
| `self_contextual` | situational modifiers affecting this value's owner | yes |
| `to_target_static` | always-on effects this value imposes on someone targeting its owner | no |
| `to_target_contextual` | situational effects this value imposes on someone targeting its owner | no |
| `from_target_static` | copied `to_target_static` from the current target | yes |
| `from_target_contextual` | copied `to_target_contextual` from the current target | yes |

The boundary is important: `to_target_*` is outgoing. It does not affect the owner until another value imports it with `set_from_target()`.

## Numerical Modifiers And Constraints

Numerical modifiers sum first. Constraints then clamp the sum.

Example EB-02-001:

```python
source_uuid = uuid4()
value = ModifiableValue.create(
    source_entity_uuid=source_uuid,
    value_name="Armor Bonus",
    base_value=10,
)

bonus_uuid = value.self_static.add_value_modifier(
    NumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Shield",
        value=5,
    )
)
assert value.score == 15

max_uuid = value.self_static.add_max_constraint(
    NumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Maximum",
        value=12,
    )
)
assert value.score == 12
```

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_001_static_numerical_modifiers_and_constraints`.

Current implementation detail: multiple minimum constraints choose the minimum listed constraint, and multiple maximum constraints choose the maximum listed constraint. This is permissive, not necessarily the most restrictive interpretation.

Example EB-02-008:

```python
low_static = ModifiableValue.create(source_entity_uuid=source_uuid, base_value=6)
low_static.self_static.add_min_constraint(number_mod(source_uuid, 8, "Minimum 8"))
low_static.self_static.add_min_constraint(number_mod(source_uuid, 12, "Minimum 12"))
assert low_static.min == 8
assert low_static.score == 8

high_static = ModifiableValue.create(source_entity_uuid=source_uuid, base_value=20)
high_static.self_static.add_max_constraint(number_mod(source_uuid, 14, "Maximum 14"))
high_static.self_static.add_max_constraint(number_mod(source_uuid, 9, "Maximum 9"))
assert high_static.max == 14
assert high_static.score == 14
```

The executable test also applies the same permissive bound selection to contextual constraints. One important engine detail falls out of that example: contextual constraints live inside their contextual channel first. If a base value is in `self_static` and a minimum constraint is in `self_contextual`, the contextual channel can contribute its own clamped score before the aggregate value is clamped.

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_008_multiple_constraints_are_permissive`.

## Advantage, Critical, And Auto-Hit

Advantage aggregation uses numeric signs:

- `ADVANTAGE` contributes `+1`.
- `DISADVANTAGE` contributes `-1`.
- final positive sum means advantage.
- final negative sum means disadvantage.
- zero means neither.

Example EB-02-002:

```python
value.self_static.add_advantage_modifier(
    AdvantageModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Helpful",
        value=AdvantageStatus.ADVANTAGE,
    )
)
value.self_static.add_advantage_modifier(
    AdvantageModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Hindering",
        value=AdvantageStatus.DISADVANTAGE,
    )
)
assert value.advantage == AdvantageStatus.NONE
```

The same parity test also asserts the engine adaptation where two advantages plus one disadvantage resolves to advantage.

Critical and auto-hit states are not summed:

- `CriticalStatus.NOCRIT` wins over `AUTOCRIT`.
- `AutoHitStatus.AUTOMISS` wins over `AUTOHIT`.

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_002_advantage_critical_and_auto_hit_precedence`.

## Contextual Modifiers

Contextual modifiers are active only when their callable returns a concrete modifier. Returning `None` makes the modifier inactive for that computation.

Example EB-02-003:

```python
def near_bonus(source_entity_uuid, target_entity_uuid, context):
    if context and context.get("near_target"):
        return NumericalModifier(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=target_entity_uuid,
            name="Near Target",
            value=4,
        )
    return None

value.self_contextual.add_value_modifier(
    ContextualNumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Near Target Bonus",
        callable=near_bonus,
    )
)

value.set_context({"near_target": True})
assert value.score == 5

value.set_context({"near_target": False})
assert value.score == 1
```

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_003_contextual_modifiers_are_evaluated_from_context`.

Contextual modifier evaluation has two paths:

- normal aggregation calls `evaluate()`, catches callable exceptions, and caches `None`;
- strict execution calls `execute_callable()`, requires `setup_callable_arguments()` first, and propagates callable errors.

Example EB-02-007:

```python
broken_modifier = ContextualNumericalModifier(
    source_entity_uuid=source_uuid,
    target_entity_uuid=source_uuid,
    name="Broken Bonus",
    callable=broken_bonus,
)
value.self_contextual.add_value_modifier(broken_modifier)
value.set_event_lineage(lineage_uuid)

assert value.score == 3
cache_key = f"{source_uuid}|{target_uuid}|{lineage_uuid}"
assert broken_modifier.cached_results[cache_key] is None

broken_modifier.setup_callable_arguments(source_uuid, target_uuid, {})
broken_modifier.execute_callable()
```

The final line raises the callable's own `RuntimeError`; the executable test asserts that strict behavior and also proves that a reliable callable raises `ValueError` until its arguments are configured. `evaluate()` stores a result in the cache, but it does not read from that cache as a memoization layer: calling the same contextual value again with the same lineage re-executes the callable and writes the same cache key again.

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_007_contextual_exceptions_cache_none_but_strict_execution_raises`.

## Target Propagation

Target-side effects live in `to_target_*` until imported by another value. This pattern models rules such as attacking a dodging, blinded, invisible, restrained, prone, paralyzed, stunned, or unconscious target.

Example EB-02-004:

```python
attacker_attack = ModifiableValue.create(
    source_entity_uuid=attacker_uuid,
    target_entity_uuid=defender_uuid,
)
defender_ac = ModifiableValue.create(
    source_entity_uuid=defender_uuid,
    target_entity_uuid=attacker_uuid,
)

defender_ac.to_target_static.add_advantage_modifier(
    AdvantageModifier(
        source_entity_uuid=defender_uuid,
        target_entity_uuid=attacker_uuid,
        name="Hard To Hit",
        value=AdvantageStatus.DISADVANTAGE,
    )
)

assert attacker_attack.advantage == AdvantageStatus.NONE

attacker_attack.set_from_target(defender_ac)
assert attacker_attack.advantage == AdvantageStatus.DISADVANTAGE

attacker_attack.reset_from_target()
assert attacker_attack.advantage == AdvantageStatus.NONE
```

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_004_to_target_channels_require_explicit_propagation`.

## Resistance

Resistance-like modifiers are keyed by damage type and converted to numbers:

- immunity: `2`
- resistance: `1`
- none: `0`
- vulnerability: `-1`

The final per-damage-type sum maps back to a status: values greater than `1` become immunity, `1` becomes resistance, `0` becomes none, and negative values become vulnerability.

Example EB-02-005:

```python
value.self_static.add_resistance_modifier(
    ResistanceModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Fire Ward",
        value=ResistanceStatus.RESISTANCE,
        damage_type=DamageType.FIRE,
    )
)
assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE

value.self_static.add_resistance_modifier(
    ResistanceModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Greater Fire Ward",
        value=ResistanceStatus.RESISTANCE,
        damage_type=DamageType.FIRE,
    )
)
assert value.resistance[DamageType.FIRE] == ResistanceStatus.IMMUNITY
```

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_005_resistance_vulnerability_and_immunity_aggregate`.

Contextual resistance modifiers use the same normal and strict contextual execution split described above. During normal aggregation, a callable that returns `None` contributes no resistance; a callable that returns a `ResistanceModifier` contributes by damage type. `execute_callable()` now accepts `ContextualResistanceModifier` and validates that the callable returned a `ResistanceModifier`.

Example EB-02-009:

```python
modifier = ContextualResistanceModifier(
    source_entity_uuid=source_uuid,
    target_entity_uuid=source_uuid,
    name="Contextual Fire Ward",
    callable=fire_ward,
)
value.self_contextual.add_resistance_modifier(modifier)

value.set_context({"fire_warded": False})
assert value.resistance[DamageType.FIRE] == ResistanceStatus.NONE

value.set_context({"fire_warded": True})
assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE

modifier.setup_callable_arguments(source_uuid, source_uuid, {"fire_warded": True})
strict_result = modifier.execute_callable()
assert isinstance(strict_result, ResistanceModifier)
```

The executable test also proves strict resistance execution rejects inactive callables returning `None` and callables returning the wrong modifier type.

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_009_contextual_resistance_aggregates_and_executes_strictly`.

## Damage Types

Damage-type modifiers track the effective damage type for values that need one, such as attacks or spell damage packets. Contextual damage-type callables follow the same active/inactive pattern as other contextual modifiers: returning `None` means no damage type contribution.

Example EB-02-011:

```python
modifier = ContextualDamageTypeModifier(
    source_entity_uuid=source_uuid,
    target_entity_uuid=source_uuid,
    name="Conditional Fire Type",
    callable=conditional_fire,
)
value.self_contextual.add_damage_type_modifier(modifier)

value.set_context({"fire": False})
assert value.self_contextual.damage_types == []
assert value.damage_types == []
assert value.damage_type is None

value.set_context({"fire": True})
assert value.self_contextual.damage_types == [DamageType.FIRE]
assert value.damage_types == [DamageType.FIRE]
assert value.damage_type == DamageType.FIRE
```

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_011_inactive_contextual_damage_types_are_empty`.

## Full Channel Boundary

Static and contextual self channels contribute immediately. Static and contextual outgoing target channels contribute only after the acting value imports them from the target.

Example EB-02-006:

```python
attacker_attack = ModifiableValue.create(
    source_entity_uuid=attacker_uuid,
    target_entity_uuid=defender_uuid,
    base_value=10,
)
defender_ac = ModifiableValue.create(
    source_entity_uuid=defender_uuid,
    target_entity_uuid=attacker_uuid,
)

attacker_attack.self_static.add_value_modifier(
    NumericalModifier(
        source_entity_uuid=attacker_uuid,
        target_entity_uuid=attacker_uuid,
        name="Weapon Bonus",
        value=1,
    )
)
attacker_attack.set_context({"focused": True})

defender_ac.to_target_static.add_value_modifier(
    NumericalModifier(
        source_entity_uuid=defender_uuid,
        target_entity_uuid=attacker_uuid,
        name="Cover Penalty",
        value=-5,
    )
)
defender_ac.set_context({"dim_light": True})

assert attacker_attack.score == 13

attacker_attack.set_from_target(defender_ac)
assert attacker_attack.score == 6

attacker_attack.reset_from_target()
assert attacker_attack.score == 13
```

The executable test includes the contextual callables omitted here for brevity.

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_006_contextual_target_channels_copy_into_from_target`.

`set_from_target()` is a live shallow import, not a snapshot. The imported channel object is distinct from the target's outgoing channel, but the modifier buckets inside it are shared. Mutating an already imported modifier or adding a new target-side modifier is therefore visible to the importing value until `reset_from_target()` clears the import.

Example EB-02-010:

```python
cover_penalty = NumericalModifier(
    source_entity_uuid=defender_uuid,
    target_entity_uuid=attacker_uuid,
    name="Cover Penalty",
    value=-2,
)
defender_ac.to_target_static.add_value_modifier(cover_penalty)

attacker_attack.set_from_target(defender_ac)
assert attacker_attack.from_target_static is not defender_ac.to_target_static
assert attacker_attack.from_target_static.value_modifiers is defender_ac.to_target_static.value_modifiers
assert attacker_attack.score == 8

cover_penalty.value = -5
assert attacker_attack.score == 5

attacker_attack.reset_from_target()
assert attacker_attack.score == 10
```

Parity test: `tests/engine_book/test_chapter_02_modifiable_values.py::test_eb_02_010_imported_target_channels_share_live_modifier_buckets`.

## Current Edge Cases And Constraints

- `to_target_*` channels are excluded from own score, advantage, critical, and auto-hit, but `ModifiableValue.damage_types` and `resistance_sum` currently include primary `to_target_*` channels.
- Contextual `evaluate()` catches all callable exceptions and caches `None`.
- `execute_callable()` is stricter than normal aggregation and now validates contextual numerical, advantage, critical, auto-hit, size, damage-type, and resistance modifiers.
- `set_from_target()` requires reciprocal targeting for contextual target channels.
- `set_from_target()` uses `model_copy()`, so copied channel objects share underlying modifier buckets.
- Contextual constraints are first applied inside their contextual channel, then the aggregate `ModifiableValue` score sums channel scores and applies aggregate min/max bounds.
- Inactive contextual damage-type modifiers produce no damage type rather than an exception.
- `set_context()` updates primary contextual channels, not already copied `from_target_contextual`.
- `damage_type` randomly selects one of the most common damage types when there is a tie. Prefer `damage_types` in deterministic tests.

## Coverage Status

Existing baseline coverage touches this subsystem through higher-level features:

- `examples/test_dodging_attack.py` verifies disadvantage from a target condition in an attack.
- `examples/test_barbarian_rage.py` verifies advantage and resistance from class conditions.
- `examples/test_new_spells.py` includes target propagation through `set_from_target()`.
- `examples/test_serialization.py` covers contextual modifier caching and condition serialization paths.
- `examples/test_protection.py` verifies target-side disadvantage from a reaction.

The direct parity coverage for this chapter is:

- `tests/engine_book/test_chapter_02_modifiable_values.py`

Status: `covered` for EB-02-001 through EB-02-011.

## Hygiene Notes

The Chapter 02 hygiene pass reviewed `dnd/core/values.py` and `dnd/core/modifiers.py`: base value contracts, value channels, concrete modifiers, contextual modifiers, and final modifier formatting. The reviewed surface now uses Google-style docstrings and Pydantic field descriptions for the value/modifier contracts documented by this chapter, keeps callable modifier fields serialization-excluded with explicit field descriptions, and has no remaining inline code comments in either primitive file.

Future edits in these files should still avoid trusting historical comments; new behavior belongs in parity examples first, then in the book.
