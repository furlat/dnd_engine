"""Engine semantic tests for modifiers and ModifiableValue channels."""

from typing import cast
from uuid import UUID, uuid4

from dnd.core.base_object import BaseObject
from dnd.types.damage import DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    AutoHitModifier,
    ContextualDamageTypeModifier,
    ContextualNumericalModifier,
    ContextualResistanceModifier,
    CriticalModifier,
    DamageTypeModifier,
    NumericalModifier,
    ResistanceModifier,
)
from dnd.types.damage import ResistanceStatus
from dnd.types.rolls import AdvantageStatus, AutoHitStatus, CriticalStatus
from dnd.core.values import BaseValue, ModifiableValue


def reset_value_state() -> None:
    """Clear registries touched by these primitive value examples."""
    BaseObject._registry.clear()
    BaseValue._registry.clear()


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
    value = ModifiableValue.create(
        source_entity_uuid=source_uuid,
        value_name="Armor Bonus",
        base_value=10,
    )

    bonus_uuid = value.self_static.add_value_modifier(
        number_mod(source_uuid, 5, "Shield")
    )
    assert value.score == 15
    assert value.normalized_score == 15

    max_uuid = value.self_static.add_max_constraint(
        number_mod(source_uuid, 12, "Maximum")
    )
    assert value.score == 12

    value.self_static.remove_modifier(max_uuid)
    min_uuid = value.self_static.add_min_constraint(
        number_mod(source_uuid, 18, "Minimum")
    )
    assert value.score == 18

    value.self_static.remove_modifier(min_uuid)
    value.self_static.remove_modifier(bonus_uuid)
    assert value.score == 10


def test_eb_02_002_advantage_critical_and_auto_hit_precedence() -> None:
    """EB-02-002: enum-like modifiers aggregate by explicit precedence."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue.create(source_entity_uuid=source_uuid)

    value.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Helpful",
            value=AdvantageStatus.ADVANTAGE,
        )
    )
    assert value.advantage == AdvantageStatus.ADVANTAGE

    value.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Hindering",
            value=AdvantageStatus.DISADVANTAGE,
        )
    )
    assert value.advantage == AdvantageStatus.NONE

    value.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="More Hindering",
            value=AdvantageStatus.DISADVANTAGE,
        )
    )
    assert value.advantage == AdvantageStatus.DISADVANTAGE

    stacked = ModifiableValue.create(source_entity_uuid=source_uuid)
    for name, status in [
        ("First Advantage", AdvantageStatus.ADVANTAGE),
        ("Second Advantage", AdvantageStatus.ADVANTAGE),
        ("One Disadvantage", AdvantageStatus.DISADVANTAGE),
    ]:
        stacked.self_static.add_advantage_modifier(
            AdvantageModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=source_uuid,
                name=name,
                value=status,
            )
        )
    assert stacked.advantage == AdvantageStatus.ADVANTAGE

    value.self_static.add_critical_modifier(
        CriticalModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Auto Crit",
            value=CriticalStatus.AUTOCRIT,
        )
    )
    value.self_static.add_critical_modifier(
        CriticalModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="No Crit",
            value=CriticalStatus.NOCRIT,
        )
    )
    assert value.critical == CriticalStatus.NOCRIT

    value.self_static.add_auto_hit_modifier(
        AutoHitModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Auto Hit",
            value=AutoHitStatus.AUTOHIT,
        )
    )
    value.self_static.add_auto_hit_modifier(
        AutoHitModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Auto Miss",
            value=AutoHitStatus.AUTOMISS,
        )
    )
    assert value.auto_hit == AutoHitStatus.AUTOMISS


def test_eb_02_003_contextual_modifiers_are_evaluated_from_context() -> None:
    """EB-02-003: contextual modifiers contribute only when callable returns."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue.create(source_entity_uuid=source_uuid, base_value=1)

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


def test_eb_02_004_to_target_channels_require_explicit_propagation() -> None:
    """EB-02-004: outgoing target effects are imported via set_from_target."""
    reset_value_state()
    attacker_uuid = uuid4()
    defender_uuid = uuid4()
    attacker_attack = ModifiableValue.create(
        source_entity_uuid=attacker_uuid,
        target_entity_uuid=defender_uuid,
        value_name="Attack Bonus",
    )
    defender_ac = ModifiableValue.create(
        source_entity_uuid=defender_uuid,
        target_entity_uuid=attacker_uuid,
        value_name="Armor Class",
    )

    defender_ac.to_target_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=defender_uuid,
            target_entity_uuid=attacker_uuid,
            name="Hard To Hit",
            value=AdvantageStatus.DISADVANTAGE,
        )
    )

    assert defender_ac.outgoing_advantage == AdvantageStatus.DISADVANTAGE
    assert attacker_attack.advantage == AdvantageStatus.NONE

    attacker_attack.set_from_target(defender_ac)
    assert attacker_attack.from_target_static is not None
    assert attacker_attack.from_target_static.source_entity_uuid == defender_uuid
    assert attacker_attack.from_target_static.target_entity_uuid == attacker_uuid
    assert attacker_attack.advantage == AdvantageStatus.DISADVANTAGE

    attacker_attack.reset_from_target()
    assert attacker_attack.from_target_static is None
    assert attacker_attack.from_target_contextual is None
    assert attacker_attack.advantage == AdvantageStatus.NONE


def test_eb_02_005_resistance_vulnerability_and_immunity_aggregate() -> None:
    """EB-02-005: resistance statuses aggregate by damage type."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue.create(source_entity_uuid=source_uuid)

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

    value.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Cold Curse",
            value=ResistanceStatus.VULNERABILITY,
            damage_type=DamageType.COLD,
        )
    )
    assert value.resistance[DamageType.COLD] == ResistanceStatus.VULNERABILITY
    assert value.resistance[DamageType.LIGHTNING] == ResistanceStatus.NONE


def test_eb_02_006_contextual_target_channels_copy_into_from_target() -> None:
    """EB-02-006: contextual outgoing channels contribute only after import."""
    reset_value_state()
    attacker_uuid = uuid4()
    defender_uuid = uuid4()
    attacker_attack = ModifiableValue.create(
        source_entity_uuid=attacker_uuid,
        target_entity_uuid=defender_uuid,
        value_name="Attack Bonus",
        base_value=10,
    )
    defender_ac = ModifiableValue.create(
        source_entity_uuid=defender_uuid,
        target_entity_uuid=attacker_uuid,
        value_name="Armor Class",
    )

    attacker_attack.self_static.add_value_modifier(
        NumericalModifier(
            source_entity_uuid=attacker_uuid,
            target_entity_uuid=attacker_uuid,
            name="Weapon Bonus",
            value=1,
        )
    )

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

    attacker_attack.self_contextual.add_value_modifier(
        ContextualNumericalModifier(
            source_entity_uuid=attacker_uuid,
            target_entity_uuid=attacker_uuid,
            name="Focus Bonus",
            callable=focus_bonus,
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

    defender_ac.to_target_contextual.add_value_modifier(
        ContextualNumericalModifier(
            source_entity_uuid=defender_uuid,
            target_entity_uuid=attacker_uuid,
            name="Dim Light Penalty",
            callable=dim_light_penalty,
        )
    )
    defender_ac.set_context({"dim_light": True})

    assert attacker_attack.score == 13

    attacker_attack.set_from_target(defender_ac)
    assert attacker_attack.from_target_static is not None
    assert attacker_attack.from_target_contextual is not None
    assert attacker_attack.score == 6

    attacker_attack.reset_from_target()
    assert attacker_attack.score == 13


def test_eb_02_007_contextual_exceptions_are_not_cached_and_strict_calls_raise() -> None:
    """EB-02-007: fail-soft aggregation never memoizes evaluator failures."""
    reset_value_state()
    source_uuid = uuid4()
    target_uuid = uuid4()
    lineage_uuid = uuid4()
    value = ModifiableValue.create(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        base_value=3,
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
    value.self_contextual.add_value_modifier(broken_modifier)
    value.set_event_lineage(lineage_uuid)

    assert value.score == 3
    cache_key = f"{source_uuid}|{target_uuid}|{lineage_uuid}"
    assert cache_key not in broken_modifier.cached_results
    assert calls == 1

    assert value.score == 3
    assert cache_key not in broken_modifier.cached_results
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

    low_contextual = ModifiableValue.create(source_entity_uuid=source_uuid, base_value=6)
    for bound in [8, 12]:
        low_contextual.self_contextual.add_min_constraint(
            ContextualNumericalModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=source_uuid,
                name=f"Minimum {bound}",
                callable=contextual_bound(bound, f"Minimum {bound}"),
            )
        )
    low_contextual.set_context({"constraints_active": True})
    assert low_contextual.min == 8
    assert low_contextual.self_contextual.score == 8
    assert low_contextual.score == 14

    high_contextual = ModifiableValue.create(source_entity_uuid=source_uuid, base_value=20)
    for bound in [14, 9]:
        high_contextual.self_contextual.add_max_constraint(
            ContextualNumericalModifier(
                source_entity_uuid=source_uuid,
                target_entity_uuid=source_uuid,
                name=f"Maximum {bound}",
                callable=contextual_bound(bound, f"Maximum {bound}"),
            )
        )
    high_contextual.set_context({"constraints_active": True})
    assert high_contextual.max == 14
    assert high_contextual.score == 14


def test_eb_02_009_contextual_resistance_aggregates_and_executes_strictly() -> None:
    """EB-02-009: contextual resistance works in aggregation and strict execution."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue.create(source_entity_uuid=source_uuid)

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
    value.self_contextual.add_resistance_modifier(modifier)

    value.set_context({"fire_warded": False})
    assert value.resistance[DamageType.FIRE] == ResistanceStatus.NONE

    value.set_context({"fire_warded": True})
    assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE

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


def test_eb_02_010_imported_target_channels_share_live_modifier_buckets() -> None:
    """EB-02-010: set_from_target() creates a channel copy with shared buckets."""
    reset_value_state()
    attacker_uuid = uuid4()
    defender_uuid = uuid4()
    attacker_attack = ModifiableValue.create(
        source_entity_uuid=attacker_uuid,
        target_entity_uuid=defender_uuid,
        base_value=10,
    )
    defender_ac = ModifiableValue.create(
        source_entity_uuid=defender_uuid,
        target_entity_uuid=attacker_uuid,
    )

    cover_penalty = NumericalModifier(
        source_entity_uuid=defender_uuid,
        target_entity_uuid=attacker_uuid,
        name="Cover Penalty",
        value=-2,
    )
    defender_ac.to_target_static.add_value_modifier(cover_penalty)

    attacker_attack.set_from_target(defender_ac)
    assert attacker_attack.from_target_static is not None
    assert attacker_attack.from_target_static is not defender_ac.to_target_static
    assert attacker_attack.from_target_static.value_modifiers is defender_ac.to_target_static.value_modifiers
    assert attacker_attack.score == 8

    cover_penalty.value = -5
    assert attacker_attack.score == 5

    defender_ac.to_target_static.add_value_modifier(
        NumericalModifier(
            source_entity_uuid=defender_uuid,
            target_entity_uuid=attacker_uuid,
            name="Fresh Penalty",
            value=-1,
        )
    )
    assert attacker_attack.score == 4

    attacker_attack.reset_from_target()
    assert attacker_attack.score == 10


def test_eb_02_011_inactive_contextual_damage_types_are_empty() -> None:
    """EB-02-011: inactive contextual damage-type callables contribute no type."""
    reset_value_state()
    source_uuid = uuid4()
    value = ModifiableValue.create(source_entity_uuid=source_uuid)

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
    value.self_contextual.add_damage_type_modifier(modifier)

    value.set_context({"fire": False})
    assert value.self_contextual.damage_types == []
    assert value.damage_types == []
    assert value.damage_type is None

    value.set_context({"fire": True})
    assert value.self_contextual.damage_types == [DamageType.FIRE]
    assert value.damage_types == [DamageType.FIRE]
    assert value.damage_type == DamageType.FIRE


def test_damage_type_ties_are_deterministic_across_insertion_order() -> None:
    """Computed value reads must never choose a random tied damage type."""
    reset_value_state()
    source_uuid = uuid4()
    first = ModifiableValue.create(source_entity_uuid=source_uuid)
    second = ModifiableValue.create(source_entity_uuid=source_uuid)

    for value, damage_types in (
        (first, (DamageType.FIRE, DamageType.COLD)),
        (second, (DamageType.COLD, DamageType.FIRE)),
    ):
        for damage_type in damage_types:
            value.self_static.add_damage_type_modifier(
                DamageTypeModifier(
                    source_entity_uuid=source_uuid,
                    target_entity_uuid=source_uuid,
                    name=f"{damage_type.value} Type",
                    value=damage_type,
                )
            )

    assert first.damage_types == [DamageType.COLD, DamageType.FIRE]
    assert second.damage_types == [DamageType.COLD, DamageType.FIRE]
    assert [first.damage_type for _ in range(20)] == [DamageType.COLD] * 20
    assert [second.damage_type for _ in range(20)] == [DamageType.COLD] * 20


def test_modifier_lookup_inherits_the_single_base_object_registry_contract() -> None:
    """Modifier subclasses use BaseObject.get without private duplicate lookups."""
    reset_value_state()
    source_uuid = uuid4()
    numerical = NumericalModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Typed Lookup",
        value=2,
    )
    advantage = AdvantageModifier(
        source_entity_uuid=source_uuid,
        target_entity_uuid=source_uuid,
        name="Other Modifier Type",
        value=AdvantageStatus.ADVANTAGE,
    )

    assert NumericalModifier.get(numerical.uuid) is numerical
    assert NumericalModifier.get(uuid4()) is None

    try:
        NumericalModifier.get(advantage.uuid)
    except ValueError as exc:
        assert "is not a NumericalModifier" in str(exc)
    else:
        raise AssertionError("typed modifier lookup must reject another modifier type")
