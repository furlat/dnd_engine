"""Manual Chapter 04 checks for values, modifiers, and context."""

from uuid import uuid4

from dnd.core.base_object import BaseObject
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    ContextualNumericalModifier,
    DamageType,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.core.values import BaseValue, ModifiableValue


def reset_value_state() -> None:
    """Clear registries touched by primitive value examples."""
    BaseObject._registry.clear()
    BaseValue._registry.clear()


def test_static_numerical_modifiers_and_constraints() -> None:
    """A base value plus a modifier is clamped by a maximum constraint."""
    reset_value_state()
    hero_id = uuid4()

    armor_class = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Armor Class",
        base_value=10,
    )

    shield_bonus = NumericalModifier(
        source_entity_uuid=hero_id,
        target_entity_uuid=hero_id,
        name="Shield",
        value=2,
    )
    armor_class.self_static.add_value_modifier(shield_bonus)

    assert armor_class.score == 12

    maximum_armor = NumericalModifier(
        source_entity_uuid=hero_id,
        target_entity_uuid=hero_id,
        name="Maximum Armor Class",
        value=11,
    )
    armor_class.self_static.add_max_constraint(maximum_armor)

    assert armor_class.score == 11


def test_advantage_and_disadvantage_aggregate_to_one_roll_state() -> None:
    """Advantage and disadvantage contributions resolve to one final state."""
    reset_value_state()
    hero_id = uuid4()
    goblin_id = uuid4()

    attack_roll_state = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        value_name="Attack Roll State",
    )

    attack_roll_state.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=hero_id,
            target_entity_uuid=goblin_id,
            name="High Ground",
            value=AdvantageStatus.ADVANTAGE,
        )
    )

    assert attack_roll_state.advantage == AdvantageStatus.ADVANTAGE

    attack_roll_state.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=hero_id,
            target_entity_uuid=goblin_id,
            name="Dim Light",
            value=AdvantageStatus.DISADVANTAGE,
        )
    )

    assert attack_roll_state.advantage == AdvantageStatus.NONE


def test_contextual_numerical_modifier_uses_runtime_context() -> None:
    """Context controls whether a contextual numerical modifier contributes."""
    reset_value_state()
    hero_id = uuid4()

    skill_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Perception Bonus",
        base_value=1,
    )

    def nearby_torch_bonus(source_entity_uuid, target_entity_uuid, context):
        if context and context.get("torch_lit"):
            return NumericalModifier(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
                name="Nearby Torch",
                value=3,
            )
        return None

    skill_bonus.self_contextual.add_value_modifier(
        ContextualNumericalModifier(
            source_entity_uuid=hero_id,
            target_entity_uuid=hero_id,
            name="Nearby Torch Bonus",
            callable=nearby_torch_bonus,
        )
    )

    skill_bonus.set_context({"torch_lit": True})
    assert skill_bonus.score == 4

    skill_bonus.set_context({"torch_lit": False})
    assert skill_bonus.score == 1


def test_target_facing_modifiers_require_explicit_import() -> None:
    """A target's outgoing modifier affects the source only after import."""
    reset_value_state()
    hero_id = uuid4()
    goblin_id = uuid4()

    hero_attack = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        value_name="Hero Attack",
        base_value=5,
    )
    goblin_defense = ModifiableValue.create(
        source_entity_uuid=goblin_id,
        target_entity_uuid=hero_id,
        value_name="Goblin Defense",
    )

    goblin_defense.to_target_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=goblin_id,
            target_entity_uuid=hero_id,
            name="Goblin Is Prone Nearby",
            value=AdvantageStatus.ADVANTAGE,
        )
    )

    assert hero_attack.advantage == AdvantageStatus.NONE

    hero_attack.set_from_target(goblin_defense)
    assert hero_attack.advantage == AdvantageStatus.ADVANTAGE

    hero_attack.reset_from_target()
    assert hero_attack.advantage == AdvantageStatus.NONE


def test_resistance_modifiers_aggregate_by_damage_type() -> None:
    """Resistance states are accumulated by damage type."""
    reset_value_state()
    hero_id = uuid4()

    defensive_traits = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Defensive Traits",
    )

    defensive_traits.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=hero_id,
            target_entity_uuid=hero_id,
            name="Fire Ward",
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.FIRE,
        )
    )

    assert defensive_traits.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE

    defensive_traits.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=hero_id,
            target_entity_uuid=hero_id,
            name="Greater Fire Ward",
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.FIRE,
        )
    )

    assert defensive_traits.resistance[DamageType.FIRE] == ResistanceStatus.IMMUNITY
