"""Engine semantic tests for modifiers and ModifiableValue channels."""

from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter

from dnd.core.base_object import BaseObject
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    ArithmeticFactor,
    AdvantageModifier,
    AutoHitModifier,
    ContextualDamageTypeModifier,
    ContextualNumericalModifier,
    ContextualResistanceModifier,
    CriticalModifier,
    DamageTypeModifier,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.core.values import (
    AdvantageStatus,
    AutoHitStatus,
    ModifiableValue,
    CriticalStatus,
    ValueRead,
    outgoing_of,
    read_value,
    value_damage_types,
    value_resistance,
    value_score,
    Channel,
    Kind,
    add_modifier,
    remove_modifier,
    composed,
    modifiers_of,
    parts,
    remove_all_modifiers,
    value_breakdown,
    with_rows,
    Row,
)


def reset_value_state() -> None:
    """Clear registries touched by these primitive value examples."""
    BaseObject._registry.clear()
    ModifiableValue._registry.clear()


def number_mod(source_uuid: UUID, value: int, name: str = "number") -> NumericalModifier:
    """Build a numerical modifier owned by `source_uuid`."""
    return NumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name=name,
        value=value,
    )


def test_eb_02_001_static_numerical_modifiers_and_constraints() -> None:
    """EB-02-001: static numerical modifiers sum, then constraints clamp."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue(
        source_entity_uuid=source_uuid,
        name="Armor Bonus",
        base=10,
    )

    bonus_uuid = add_modifier(value, Channel.SELF_STATIC, Kind.VALUE, number_mod(source_uuid, 5, "Shield"))
    assert value.score == 15
    assert value.normalized_score == 15

    max_uuid = add_modifier(value, Channel.SELF_STATIC, Kind.MAX, number_mod(source_uuid, 12, "Maximum"))
    assert value.score == 12

    remove_modifier(value, max_uuid, Channel.SELF_STATIC)
    min_uuid = add_modifier(value, Channel.SELF_STATIC, Kind.MIN, number_mod(source_uuid, 18, "Minimum"))
    assert value.score == 18

    remove_modifier(value, min_uuid, Channel.SELF_STATIC)
    remove_modifier(value, bonus_uuid, Channel.SELF_STATIC)
    assert value.score == 10


def test_eb_02_002_advantage_critical_and_auto_hit_precedence() -> None:
    """EB-02-002: enum-like modifiers aggregate by explicit precedence."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue(source_entity_uuid=source_uuid)

    add_modifier(value, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Helpful",
            value=AdvantageStatus.ADVANTAGE,
        ))
    assert value.advantage == AdvantageStatus.ADVANTAGE

    add_modifier(value, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Hindering",
            value=AdvantageStatus.DISADVANTAGE,
        ))
    assert value.advantage == AdvantageStatus.NONE

    add_modifier(value, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="More Hindering",
            value=AdvantageStatus.DISADVANTAGE,
        ))
    assert value.advantage == AdvantageStatus.DISADVANTAGE

    stacked = ModifiableValue(source_entity_uuid=source_uuid)
    for name, status in [
        ("First Advantage", AdvantageStatus.ADVANTAGE),
        ("Second Advantage", AdvantageStatus.ADVANTAGE),
        ("One Disadvantage", AdvantageStatus.DISADVANTAGE),
    ]:
        add_modifier(stacked, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=source_uuid,
                name=name,
                value=status,
            ))
    assert stacked.advantage == AdvantageStatus.ADVANTAGE

    add_modifier(value, Channel.SELF_STATIC, Kind.CRITICAL, CriticalModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Auto Crit",
            value=CriticalStatus.AUTOCRIT,
        ))
    add_modifier(value, Channel.SELF_STATIC, Kind.CRITICAL, CriticalModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="No Crit",
            value=CriticalStatus.NOCRIT,
        ))
    assert value.critical == CriticalStatus.NOCRIT

    add_modifier(value, Channel.SELF_STATIC, Kind.AUTO_HIT, AutoHitModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Auto Hit",
            value=AutoHitStatus.AUTOHIT,
        ))
    add_modifier(value, Channel.SELF_STATIC, Kind.AUTO_HIT, AutoHitModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Auto Miss",
            value=AutoHitStatus.AUTOMISS,
        ))
    assert value.auto_hit == AutoHitStatus.AUTOMISS


def test_eb_02_003_contextual_modifiers_are_evaluated_from_context() -> None:
    """EB-02-003: contextual modifiers contribute only when callable returns."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue(source_entity_uuid=source_uuid, base=1)

    def near_bonus(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        context: dict | None,
    ) -> NumericalModifier | None:
        if context and context.get("near_target"):
            return NumericalModifier(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
                name="Near Target",
                value=4,
            )
        return None

    add_modifier(value, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Near Target Bonus",
            callable=near_bonus,
        ))

    assert read_value(parts(value), ValueRead(source_uuid, context={"near_target": True})).score == 5
    assert read_value(parts(value), ValueRead(source_uuid, context={"near_target": False})).score == 1
    assert value.score == 1


def test_eb_02_004_to_target_channels_apply_only_in_an_opposed_read() -> None:
    """EB-02-004: outgoing target effects apply when the read carries the opponent's outgoing channels."""
    reset_value_state()
    attacker_uuid = uuid4()
    defender_uuid = uuid4()
    attacker_attack = ModifiableValue(
        source_entity_uuid=attacker_uuid,
        name="Attack Bonus",
    )
    defender_ac = ModifiableValue(
        source_entity_uuid=defender_uuid,
        name="Armor Class",
    )

    add_modifier(defender_ac, Channel.TO_TARGET_STATIC, Kind.ADVANTAGE, AdvantageModifier(
            source_entity_uuid=defender_uuid,
            target_entity_uuid=attacker_uuid,
            name="Hard To Hit",
            value=AdvantageStatus.DISADVANTAGE,
        ))

    assert read_value(parts(attacker_attack), ValueRead(attacker_uuid, defender_uuid)).advantage == AdvantageStatus.NONE

    opposed = read_value(parts(attacker_attack), ValueRead(attacker_uuid, defender_uuid,
                                                    opponent=outgoing_of(parts(defender_ac), None)))
    assert opposed.advantage == AdvantageStatus.DISADVANTAGE
    assert [row.source for row in opposed.advantage_breakdown] == ["from_target"]
    assert attacker_attack.advantage == AdvantageStatus.NONE


def test_eb_02_005_resistance_vulnerability_and_immunity_aggregate() -> None:
    """EB-02-005: resistance statuses aggregate by damage type."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue(source_entity_uuid=source_uuid)

    add_modifier(value, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Fire Ward",
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.FIRE,
        ))
    assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE

    add_modifier(value, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Greater Fire Ward",
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.FIRE,
        ))
    assert value.resistance[DamageType.FIRE] == ResistanceStatus.IMMUNITY

    add_modifier(value, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Cold Curse",
            value=ResistanceStatus.VULNERABILITY,
            damage_type=DamageType.COLD,
        ))
    assert value.resistance[DamageType.COLD] == ResistanceStatus.VULNERABILITY
    assert value.resistance[DamageType.LIGHTNING] == ResistanceStatus.NONE


def test_eb_02_006_contextual_outgoing_channels_read_in_the_opponent_context() -> None:
    """EB-02-006: contextual outgoing channels contribute in an opposed read, in the opponent's context."""
    reset_value_state()
    attacker_uuid = uuid4()
    defender_uuid = uuid4()
    attacker_attack = ModifiableValue(
        source_entity_uuid=attacker_uuid,
        name="Attack Bonus",
        base=10,
    )
    defender_ac = ModifiableValue(
        source_entity_uuid=defender_uuid,
        name="Armor Class",
    )

    add_modifier(attacker_attack, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(
            source_entity_uuid=attacker_uuid,
            target_entity_uuid=attacker_uuid,
            name="Weapon Bonus",
            value=1,
        ))

    def focus_bonus(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        context: dict | None,
    ) -> NumericalModifier | None:
        if context and context.get("focused"):
            return NumericalModifier(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
                name="Focused",
                value=2,
            )
        return None

    add_modifier(attacker_attack, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
            source_entity_uuid=attacker_uuid,
            target_entity_uuid=attacker_uuid,
            name="Focus Bonus",
            callable=focus_bonus,
        ))
    add_modifier(defender_ac, Channel.TO_TARGET_STATIC, Kind.VALUE, NumericalModifier(
            source_entity_uuid=defender_uuid,
            target_entity_uuid=attacker_uuid,
            name="Cover Penalty",
            value=-5,
        ))

    def dim_light_penalty(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        context: dict | None,
    ) -> NumericalModifier | None:
        if context and context.get("dim_light"):
            return NumericalModifier(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
                name="Dim Light",
                value=-2,
            )
        return None

    add_modifier(defender_ac, Channel.TO_TARGET_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
            source_entity_uuid=defender_uuid,
            target_entity_uuid=attacker_uuid,
            name="Dim Light Penalty",
            callable=dim_light_penalty,
        ))
    own = ValueRead(attacker_uuid, defender_uuid, {"focused": True})
    assert read_value(parts(attacker_attack), own).score == 13

    opposed = ValueRead(attacker_uuid, defender_uuid, {"focused": True},
                        outgoing_of(parts(defender_ac), context={"dim_light": True}))
    assert read_value(parts(attacker_attack), opposed).score == 6
    unlit = ValueRead(attacker_uuid, defender_uuid, {"focused": True}, outgoing_of(parts(defender_ac), None))
    assert read_value(parts(attacker_attack), unlit).score == 8
    assert read_value(parts(attacker_attack), own).score == 13


def test_eb_02_007_contextual_exceptions_read_as_absent_but_strict_execution_raises() -> None:
    """EB-02-007: normal contextual aggregation is forgiving; strict calls are not."""
    reset_value_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    value = ModifiableValue(
        source_entity_uuid=source_uuid,
        base=3,
    )

    calls = 0

    def broken_bonus(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        context: dict | None,
    ) -> NumericalModifier | None:
        nonlocal calls
        calls += 1
        raise RuntimeError("context unavailable")

    broken_modifier = ContextualNumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Broken Bonus",
        callable=broken_bonus,
    )
    add_modifier(value, Channel.SELF_CONTEXTUAL, Kind.VALUE, broken_modifier)
    read = ValueRead(source_uuid, target_uuid)

    assert value_score(parts(value), read, normalized=False) == 3
    assert calls == 1

    reading = read_value(parts(value), read)
    assert reading.score == 3
    assert [row.name for row in reading.breakdown] == ["Prof"]
    assert calls == 2

    try:
        broken_modifier.setup_callable_arguments(source_uuid, target_uuid, {})
        broken_modifier.execute_callable()
    except RuntimeError as exc:
        assert str(exc) == "context unavailable"
    else:
        raise AssertionError("strict execute_callable() should propagate callable errors")

    def reliable_bonus(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        context: dict | None,
    ) -> NumericalModifier | None:
        if context and context.get("enabled"):
            return NumericalModifier(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
                name="Reliable Bonus",
                value=4,
            )
        return None

    reliable_modifier = ContextualNumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Reliable Bonus",
        callable=reliable_bonus,
    )

    try:
        reliable_modifier.execute_callable()
    except ValueError as exc:
        assert str(exc) == "Callable arguments not set"
    else:
        raise AssertionError("strict execute_callable() requires setup arguments")

    reliable_modifier.setup_callable_arguments(source_uuid, target_uuid, {"enabled": True})
    strict_result = reliable_modifier.execute_callable()
    assert isinstance(strict_result, NumericalModifier)
    assert strict_result.value == 4


def test_eb_02_008_multiple_constraints_are_permissive() -> None:
    """EB-02-008: stacked constraints choose the widest active clamp bounds."""
    reset_value_state()
    source_uuid = uuid4()

    low_static = ModifiableValue(source_entity_uuid=source_uuid, base=6)
    add_modifier(low_static, Channel.SELF_STATIC, Kind.MIN, number_mod(source_uuid, 8, "Minimum 8"))
    add_modifier(low_static, Channel.SELF_STATIC, Kind.MIN, number_mod(source_uuid, 12, "Minimum 12"))
    assert read_value(parts(low_static), ValueRead(source_uuid)).channels[0].minimum == 8
    assert low_static.score == 8

    high_static = ModifiableValue(source_entity_uuid=source_uuid, base=20)
    add_modifier(high_static, Channel.SELF_STATIC, Kind.MAX, number_mod(source_uuid, 14, "Maximum 14"))
    add_modifier(high_static, Channel.SELF_STATIC, Kind.MAX, number_mod(source_uuid, 9, "Maximum 9"))
    assert read_value(parts(high_static), ValueRead(source_uuid)).channels[0].maximum == 14
    assert high_static.score == 14

    def contextual_bound(bound: int, name: str):
        def callback(
            source_entity_uuid: UUID,
            target_entity_uuid: UUID | None,
            context: dict | None,
        ) -> NumericalModifier | None:
            if context and context.get("constraints_active"):
                return NumericalModifier(
                    source_entity_uuid=source_entity_uuid,
                    target_entity_uuid=target_entity_uuid,
                    name=name,
                    value=bound,
                )
            return None

        return callback

    low_contextual = ModifiableValue(source_entity_uuid=source_uuid, base=6)
    for bound in [8, 12]:
        add_modifier(low_contextual, Channel.SELF_CONTEXTUAL, Kind.MIN, ContextualNumericalModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=source_uuid,
                name=f"Minimum {bound}",
                callable=contextual_bound(bound, f"Minimum {bound}"),
            ))
    active = ValueRead(source_uuid, context={"constraints_active": True})
    contextual = read_value(parts(low_contextual), active).channels[1]
    assert (contextual.minimum, contextual.maximum) == (8, None)
    assert read_value(parts(low_contextual), ValueRead(source_uuid)).channels[1].minimum is None
    assert value_score(parts(low_contextual), active, normalized=False) == 14

    high_contextual = ModifiableValue(source_entity_uuid=source_uuid, base=20)
    for bound in [14, 9]:
        add_modifier(high_contextual, Channel.SELF_CONTEXTUAL, Kind.MAX, ContextualNumericalModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=source_uuid,
                name=f"Maximum {bound}",
                callable=contextual_bound(bound, f"Maximum {bound}"),
            ))
    contextual = read_value(parts(high_contextual), active).channels[1]
    assert (contextual.minimum, contextual.maximum) == (None, 14)
    assert value_score(parts(high_contextual), active, normalized=False) == 14


def test_eb_02_009_contextual_resistance_aggregates_and_executes_strictly() -> None:
    """EB-02-009: contextual resistance works in aggregation and strict execution."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue(source_entity_uuid=source_uuid)

    def fire_ward(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        context: dict | None,
    ) -> ResistanceModifier | None:
        if context and context.get("fire_warded"):
            return ResistanceModifier(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
                name="Fire Ward",
                value=ResistanceStatus.RESISTANCE,
                damage_type=DamageType.FIRE,
            )
        return None

    modifier = ContextualResistanceModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Contextual Fire Ward",
        callable=fire_ward,
    )
    add_modifier(value, Channel.SELF_CONTEXTUAL, Kind.RESISTANCE, modifier)

    assert value_resistance(parts(value), ValueRead(source_uuid, context={"fire_warded": False}))[DamageType.FIRE] == ResistanceStatus.NONE
    assert value_resistance(parts(value), ValueRead(source_uuid, context={"fire_warded": True}))[DamageType.FIRE] == ResistanceStatus.RESISTANCE

    modifier.setup_callable_arguments(source_uuid, source_uuid, {"fire_warded": True})
    strict_result = modifier.execute_callable()
    assert isinstance(strict_result, ResistanceModifier)
    assert strict_result.damage_type == DamageType.FIRE
    assert strict_result.value == ResistanceStatus.RESISTANCE

    modifier.setup_callable_arguments(source_uuid, source_uuid, {"fire_warded": False})
    try:
        modifier.execute_callable()
    except ValueError as exc:
        assert str(exc) == "Callable returned unexpected type. Expected ResistanceModifier, got NoneType"
    else:
        raise AssertionError("strict resistance execution should reject inactive callables")

    def wrong_fire_ward(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        context: dict | None,
    ) -> ResistanceModifier | None:
        return cast(
            ResistanceModifier,
            NumericalModifier(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
                name="Wrong Type",
                value=1,
            ),
        )

    wrong_modifier = ContextualResistanceModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Wrong Contextual Fire Ward",
        callable=wrong_fire_ward,
    )
    wrong_modifier.setup_callable_arguments(source_uuid, source_uuid, {})
    try:
        wrong_modifier.execute_callable()
    except ValueError as exc:
        assert str(exc) == "Callable returned unexpected type. Expected ResistanceModifier, got NumericalModifier"
    else:
        raise AssertionError("strict resistance execution should reject wrong return types")


def test_eb_02_010_opponent_outgoing_rows_are_read_live() -> None:
    """EB-02-010: an opposed read reads the opponent's live outgoing rows."""
    reset_value_state()
    attacker_uuid = uuid4()
    defender_uuid = uuid4()
    attacker_attack = ModifiableValue(
        source_entity_uuid=attacker_uuid,
        base=10,
    )
    defender_ac = ModifiableValue(
        source_entity_uuid=defender_uuid,
    )

    cover_penalty = NumericalModifier(
        source_entity_uuid=defender_uuid,
        target_entity_uuid=attacker_uuid,
        name="Cover Penalty",
        value=-2,
    )
    add_modifier(defender_ac, Channel.TO_TARGET_STATIC, Kind.VALUE, cover_penalty)

    opposed = ValueRead(attacker_uuid, defender_uuid, opponent=outgoing_of(parts(defender_ac), None))
    assert value_score(parts(attacker_attack), opposed, normalized=False) == 8

    cover_penalty.value = -5
    assert value_score(parts(attacker_attack), opposed, normalized=False) == 5

    add_modifier(defender_ac, Channel.TO_TARGET_STATIC, Kind.VALUE, NumericalModifier(
            source_entity_uuid=defender_uuid,
            target_entity_uuid=attacker_uuid,
            name="Fresh Penalty",
            value=-1,
        ))
    assert value_score(parts(attacker_attack), opposed, normalized=False) == 4
    assert attacker_attack.score == 10


def test_eb_02_011_inactive_contextual_damage_types_are_empty() -> None:
    """EB-02-011: inactive contextual damage-type callables contribute no type."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue(source_entity_uuid=source_uuid)

    def conditional_fire(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        context: dict | None,
    ) -> DamageTypeModifier | None:
        if context and context.get("fire"):
            return DamageTypeModifier(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
                name="Fire Type",
                value=DamageType.FIRE,
            )
        return None

    modifier = ContextualDamageTypeModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Conditional Fire Type",
        callable=conditional_fire,
    )
    add_modifier(value, Channel.SELF_CONTEXTUAL, Kind.DAMAGE_TYPE, modifier)

    assert value_damage_types(parts(value), ValueRead(source_uuid, context={"fire": False})) == []
    assert value.damage_type is None

    assert value_damage_types(parts(value), ValueRead(source_uuid, context={"fire": True})) == [DamageType.FIRE]


if __name__ == "__main__":
    test_eb_02_001_static_numerical_modifiers_and_constraints()
    test_eb_02_002_advantage_critical_and_auto_hit_precedence()
    test_eb_02_003_contextual_modifiers_are_evaluated_from_context()
    test_eb_02_004_to_target_channels_apply_only_in_an_opposed_read()
    test_eb_02_005_resistance_vulnerability_and_immunity_aggregate()
    test_eb_02_006_contextual_outgoing_channels_read_in_the_opponent_context()
    test_eb_02_007_contextual_exceptions_read_as_absent_but_strict_execution_raises()
    test_eb_02_008_multiple_constraints_are_permissive()
    test_eb_02_009_contextual_resistance_aggregates_and_executes_strictly()
    test_eb_02_010_opponent_outgoing_rows_are_read_live()
    test_eb_02_011_inactive_contextual_damage_types_are_empty()
    print("PASS: engine book modifiable value tests")


@pytest.mark.parametrize("kind", [Kind.VALUE, Kind.MIN, Kind.MAX, Kind.FACTOR])
def test_outgoing_numerical_rows_reject_their_own_source(kind: Kind) -> None:
    reset_value_state()
    owner_uuid, target_uuid = uuid4(), uuid4()
    own = (ArithmeticFactor(source_entity_uuid=owner_uuid, target_entity_uuid=owner_uuid, numerator=2)
           if kind is Kind.FACTOR else number_mod(owner_uuid, 1))
    incoming = ModifiableValue(source_entity_uuid=owner_uuid)
    add_modifier(incoming, Channel.SELF_STATIC, kind, own)
    assert composed(parts(incoming))
    outgoing = ModifiableValue(source_entity_uuid=owner_uuid)
    add_modifier(outgoing, Channel.TO_TARGET_STATIC, kind, own)
    with pytest.raises(ValueError, match="Outgoing modifier target"):
        composed(parts(outgoing))
    other = (ArithmeticFactor(source_entity_uuid=owner_uuid, target_entity_uuid=target_uuid, numerator=2)
             if kind is Kind.FACTOR else NumericalModifier(source_entity_uuid=owner_uuid, target_entity_uuid=target_uuid,
                                                           name="Other target", value=1))
    targeted = ModifiableValue(source_entity_uuid=owner_uuid)
    add_modifier(targeted, Channel.TO_TARGET_STATIC, kind, other)
    assert composed(parts(targeted))


def test_exact_factors_apply_after_all_channels_before_bounds_and_survive_composition():
    owner, target = uuid4(), uuid4()
    speed = ModifiableValue(source_entity_uuid=owner, base=31)
    bonus = ModifiableValue(source_entity_uuid=owner, base=4)
    add_modifier(speed, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
        source_entity_uuid=owner, callable=lambda *_: number_mod(owner, 5)))
    external = ModifiableValue(source_entity_uuid=target)
    add_modifier(external, Channel.TO_TARGET_STATIC, Kind.VALUE, NumericalModifier(
        source_entity_uuid=target, target_entity_uuid=owner, value=10))
    haste = ArithmeticFactor(source_entity_uuid=owner, numerator=2)
    slow = ArithmeticFactor(source_entity_uuid=owner, numerator=1, denominator=2)
    add_modifier(speed, Channel.SELF_STATIC, Kind.FACTOR, haste)
    add_modifier(external, Channel.TO_TARGET_STATIC, Kind.FACTOR, slow)
    combined = composed(parts(speed, bonus))
    read = ValueRead(owner, target, opponent=outgoing_of(parts(external), None))
    assert value_score(combined, read, normalized=True) == 50
    remove_modifier(external, slow.uuid)
    assert value_score(combined, read, normalized=True) == 100
    cap = number_mod(owner, 0)
    assert value_score(with_rows(combined, (Row(Channel.SELF_STATIC, Kind.MAX, cap),)), read, normalized=True) == 0
    assert haste in modifiers_of(speed, Channel.SELF_STATIC, Kind.FACTOR)
    assert any(row.operation == 'multiply' for row in value_breakdown(combined))
    remove_modifier(speed, haste.uuid)
    assert value_score(composed(parts(speed, bonus)), read, normalized=True) == 50
    assert not modifiers_of(speed, Channel.SELF_STATIC, Kind.FACTOR)


def test_fractional_factors_round_only_after_combining_and_serialize_exactly():
    owner = uuid4()
    value = ModifiableValue(source_entity_uuid=owner, base=31)
    half = ArithmeticFactor(source_entity_uuid=owner, numerator=1, denominator=2)
    double = ArithmeticFactor(source_entity_uuid=owner, numerator=2)
    add_modifier(value, Channel.SELF_STATIC, Kind.FACTOR, half)
    assert value.normalized_score == 15
    add_modifier(value, Channel.SELF_STATIC, Kind.FACTOR, double)
    assert value.normalized_score == 31
    snapshot = TypeAdapter(ModifiableValue).dump_python(value, mode='json')
    factors = [row[2] for row in snapshot['modifiers'] if row[1] == 'factor']
    assert factors[0]['uuid'] == str(half.uuid) and factors[0]['denominator'] == 2
    assert value_score(parts(value), ValueRead(owner), normalized=True, excluded=frozenset({double.uuid})) == 15
    remove_all_modifiers(value)
    assert value.normalized_score == 0
