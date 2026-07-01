"""Tutorial tests for values, modifiers, context, and target propagation."""

from typing import Optional
from uuid import UUID, uuid4

from dnd.core.base_object import BaseObject
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    AutoHitModifier,
    AutoHitStatus,
    ContextualNumericalModifier,
    CriticalModifier,
    CriticalStatus,
    DamageType,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.core.values import BaseValue, ModifiableValue


def reset_value_state() -> None:
    """Clear global indexes touched by these value and modifier examples."""
    BaseObject._registry.clear()
    BaseValue._registry.clear()


def ability_score_normalizer(score: int) -> int:
    """Convert a D&D ability score into its ability modifier."""
    return (score - 10) // 2


def high_ground_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID],
    context: Optional[dict],
) -> Optional[NumericalModifier]:
    """Return a bonus only when the current context grants high ground."""
    if context is None or not context.get("has_high_ground", False):
        return None
    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid,
        name="High Ground",
        value=2,
    )


def test_first_value_example_prints_visible_breakdown(capsys) -> None:
    """One value ledger prints its final score and named rule contributions."""
    reset_value_state()

    hero_id = uuid4()
    armor_class = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Armor Class",
        base_value=10,
    )
    armor_class.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=hero_id,
            target_entity_uuid=hero_id,
            name="Shield",
            value=2,
        )
    )
    armor_class.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=hero_id,
            target_entity_uuid=hero_id,
            name="Defense Style",
            value=1,
        )
    )

    breakdown = armor_class.get_breakdown()
    breakdown_names = ", ".join(entry["name"] for entry in breakdown)
    modifier_text = (
        f"{breakdown[1]['name']} +{breakdown[1]['value']}, "
        f"{breakdown[2]['name']} +{breakdown[2]['value']}"
    )
    lookup_state = (
        "same live value"
        if BaseValue.get(armor_class.uuid) is armor_class
        else "different value"
    )
    readout_lines = [
        f"value: {armor_class.name}",
        f"base score: {breakdown[0]['value']}",
        f"rule modifiers: {modifier_text}",
        f"final score: {armor_class.score}",
        f"breakdown names: {breakdown_names}",
        f"lookup result: {lookup_state}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "value: Armor Class",
        "base score: 10",
        "rule modifiers: Shield +2, Defense Style +1",
        "final score: 13",
        "breakdown names: Armor, Shield, Defense Style",
        "lookup result: same live value",
    ]
    assert readout_lines == expected_lines
    assert armor_class.normalized_score == 13
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_base_values_modifiers_normalization_and_breakdown(capsys) -> None:
    """Numerical modifiers print raw, normalized, and breakdown state."""
    reset_value_state()
    hero_id = uuid4()

    strength_score = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="strength Ability Score",
        base_value=16,
        score_normalizer=ability_score_normalizer,
    )

    assert strength_score.score == 16
    assert strength_score.normalized_score == 3

    attack_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Attack Bonus",
        base_value=1,
    )
    attack_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=hero_id,
            name="Magic Weapon",
            value=1,
        )
    )

    combined_attack_bonus = strength_score.combine_values(
        [attack_bonus],
        naming_callable=lambda names: " + ".join(names),
    )

    assert combined_attack_bonus.name == "strength Ability Score + Attack Bonus"
    assert combined_attack_bonus.score == 18
    assert combined_attack_bonus.normalized_score == 5
    combined_breakdown = combined_attack_bonus.get_breakdown()
    assert combined_breakdown == [
        {"name": "STR", "value": 3, "source": "self"},
        {"name": "Base", "value": 1, "source": "self"},
        {"name": "Magic Weapon", "value": 1, "source": "self"},
    ]
    breakdown_parts = [
        f"{entry['name']}={entry['value']}"
        for entry in combined_breakdown
    ]

    score_lines = [
        (
            "strength score: "
            f"raw={strength_score.score}, normalized={strength_score.normalized_score}"
        ),
        (
            "attack bonus: "
            f"raw={attack_bonus.score}, normalized={attack_bonus.normalized_score}"
        ),
        f"combined value: {combined_attack_bonus.name}",
        (
            "combined score: "
            f"raw={combined_attack_bonus.score}, "
            f"normalized={combined_attack_bonus.normalized_score}"
        ),
        (
            "breakdown: "
            f"{', '.join(breakdown_parts)}"
        ),
    ]

    print("\n".join(score_lines))

    expected_score_lines = [
        "strength score: raw=16, normalized=3",
        "attack bonus: raw=2, normalized=2",
        "combined value: strength Ability Score + Attack Bonus",
        "combined score: raw=18, normalized=5",
        "breakdown: STR=3, Base=1, Magic Weapon=1",
    ]
    assert score_lines == expected_score_lines
    assert capsys.readouterr().out.splitlines() == expected_score_lines


def test_static_channels_print_constraints_roll_states_and_resistances(capsys) -> None:
    """Static modifier buckets print constraints and non-numerical states."""
    reset_value_state()
    hero_id = uuid4()

    movement = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Movement",
        base_value=30,
    )
    movement.self_static.add_max_constraint(
        NumericalModifier.create(
            source_entity_uuid=hero_id,
            name="Grappled",
            value=0,
        )
    )
    movement_after_grapple = movement.score
    assert movement_after_grapple == 0

    attack_roll_state = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Attack Roll State",
    )
    attack_roll_state.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=hero_id,
            name="Unseen Attacker",
            value=AdvantageStatus.ADVANTAGE,
        )
    )
    advantage_after_unseen = attack_roll_state.advantage
    assert advantage_after_unseen == AdvantageStatus.ADVANTAGE

    attack_roll_state.self_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=hero_id,
            name="Long Range",
            value=AdvantageStatus.DISADVANTAGE,
        )
    )
    advantage_after_long_range = attack_roll_state.advantage
    assert advantage_after_long_range == AdvantageStatus.NONE

    attack_roll_state.self_static.add_critical_modifier(
        CriticalModifier(
            source_entity_uuid=hero_id,
            name="Paralyzed Target",
            value=CriticalStatus.AUTOCRIT,
        )
    )
    attack_roll_state.self_static.add_critical_modifier(
        CriticalModifier(
            source_entity_uuid=hero_id,
            name="Critical Immunity",
            value=CriticalStatus.NOCRIT,
        )
    )
    critical_state = attack_roll_state.critical
    assert critical_state == CriticalStatus.NOCRIT

    attack_roll_state.self_static.add_auto_hit_modifier(
        AutoHitModifier(
            source_entity_uuid=hero_id,
            name="Guided Strike",
            value=AutoHitStatus.AUTOHIT,
        )
    )
    attack_roll_state.self_static.add_auto_hit_modifier(
        AutoHitModifier(
            source_entity_uuid=hero_id,
            name="Sanctuary",
            value=AutoHitStatus.AUTOMISS,
        )
    )
    auto_hit_state = attack_roll_state.auto_hit
    assert auto_hit_state == AutoHitStatus.AUTOMISS

    damage_response = ModifiableValue.create(
        source_entity_uuid=hero_id,
        value_name="Damage Response",
    )
    damage_response.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=hero_id,
            name="Fire Resistance",
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.FIRE,
        )
    )
    fire_after_resistance = damage_response.resistance[DamageType.FIRE]
    assert fire_after_resistance == ResistanceStatus.RESISTANCE

    damage_response.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=hero_id,
            name="Oil Vulnerability",
            value=ResistanceStatus.VULNERABILITY,
            damage_type=DamageType.FIRE,
        )
    )
    fire_after_vulnerability = damage_response.resistance[DamageType.FIRE]
    assert fire_after_vulnerability == ResistanceStatus.NONE

    damage_response.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=hero_id,
            name="Fire Immunity",
            value=ResistanceStatus.IMMUNITY,
            damage_type=DamageType.FIRE,
        )
    )
    fire_after_immunity = damage_response.resistance[DamageType.FIRE]
    assert fire_after_immunity == ResistanceStatus.IMMUNITY

    static_lines = [
        f"movement after grapple: {movement_after_grapple}",
        (
            "advantage states: "
            f"unseen={advantage_after_unseen.value}, "
            f"after long range={advantage_after_long_range.value}"
        ),
        f"critical state: {critical_state.value}",
        f"auto-hit state: {auto_hit_state.value}",
        (
            "fire response: "
            f"resistance={fire_after_resistance.value}, "
            f"after vulnerability={fire_after_vulnerability.value}, "
            f"after immunity={fire_after_immunity.value}"
        ),
    ]

    print("\n".join(static_lines))

    expected_static_lines = [
        "movement after grapple: 0",
        "advantage states: unseen=Advantage, after long range=None",
        "critical state: Critical Immune",
        "auto-hit state: Automiss",
        "fire response: resistance=Resistance, after vulnerability=None, after immunity=Immunity",
    ]
    assert static_lines == expected_static_lines
    assert capsys.readouterr().out.splitlines() == expected_static_lines


def test_contextual_modifiers_print_current_context_results(capsys) -> None:
    """Contextual modifiers print only when their callable returns a modifier."""
    reset_value_state()
    hero_id = uuid4()
    goblin_id = uuid4()

    ranged_attack_bonus = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=goblin_id,
        value_name="Ranged Attack Bonus",
        base_value=5,
    )
    ranged_attack_bonus.self_contextual.add_value_modifier(
        ContextualNumericalModifier(
            source_entity_uuid=hero_id,
            target_entity_uuid=goblin_id,
            name="High Ground",
            callable=high_ground_bonus,
        )
    )

    score_without_context = ranged_attack_bonus.score
    assert score_without_context == 5

    ranged_attack_bonus.set_context({"has_high_ground": True})
    score_with_high_ground = ranged_attack_bonus.score
    assert score_with_high_ground == 7
    assert {
        "name": "High Ground",
        "value": 2,
        "source": "self_contextual",
        "contextual": True,
    } in ranged_attack_bonus.get_full_breakdown()
    contextual_breakdown_has_high_ground = any(
        entry["name"] == "High Ground"
        for entry in ranged_attack_bonus.get_full_breakdown()
    )

    ranged_attack_bonus.set_context({"has_high_ground": False})
    score_after_context_cleared = ranged_attack_bonus.score
    assert score_after_context_cleared == 5

    context_lines = [
        f"score without context: {score_without_context}",
        f"score with high ground: {score_with_high_ground}",
        (
            "contextual breakdown contains High Ground: "
            f"{contextual_breakdown_has_high_ground}"
        ),
        f"score after clearing context: {score_after_context_cleared}",
    ]

    print("\n".join(context_lines))

    expected_context_lines = [
        "score without context: 5",
        "score with high ground: 7",
        "contextual breakdown contains High Ground: True",
        "score after clearing context: 5",
    ]
    assert context_lines == expected_context_lines
    assert capsys.readouterr().out.splitlines() == expected_context_lines


def test_target_propagation_prints_imported_modifiers_then_reset(capsys) -> None:
    """A value prints imported target modifiers and reset state."""
    reset_value_state()
    hero_id = uuid4()
    blinded_goblin_id = uuid4()

    hero_attack = ModifiableValue.create(
        source_entity_uuid=hero_id,
        target_entity_uuid=blinded_goblin_id,
        value_name="Attack Bonus",
        base_value=5,
    )
    goblin_defense = ModifiableValue.create(
        source_entity_uuid=blinded_goblin_id,
        target_entity_uuid=hero_id,
        value_name="Armor Class",
        base_value=13,
    )

    goblin_defense.to_target_static.add_advantage_modifier(
        AdvantageModifier(
            source_entity_uuid=blinded_goblin_id,
            target_entity_uuid=hero_id,
            name="Blinded",
            value=AdvantageStatus.ADVANTAGE,
        )
    )
    goblin_defense.to_target_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=blinded_goblin_id,
            target_entity_uuid=hero_id,
            name="Exposed Target",
            value=2,
        )
    )

    score_before_import = hero_attack.score
    advantage_before_import = hero_attack.advantage
    assert score_before_import == 5
    assert advantage_before_import == AdvantageStatus.NONE

    hero_attack.set_from_target(goblin_defense)

    score_during_import = hero_attack.score
    advantage_during_import = hero_attack.advantage
    assert score_during_import == 7
    assert advantage_during_import == AdvantageStatus.ADVANTAGE
    assert {
        "name": "Exposed Target",
        "value": 2,
        "source": "from_target",
    } in hero_attack.get_breakdown()
    imported_breakdown_has_exposed_target = any(
        entry["name"] == "Exposed Target"
        for entry in hero_attack.get_breakdown()
    )

    hero_attack.reset_from_target()

    score_after_reset = hero_attack.score
    advantage_after_reset = hero_attack.advantage
    assert score_after_reset == 5
    assert advantage_after_reset == AdvantageStatus.NONE

    target_lines = [
        (
            "before import: "
            f"score={score_before_import}, advantage={advantage_before_import.value}"
        ),
        (
            "during import: "
            f"score={score_during_import}, advantage={advantage_during_import.value}"
        ),
        (
            "imported breakdown contains Exposed Target: "
            f"{imported_breakdown_has_exposed_target}"
        ),
        (
            "after reset: "
            f"score={score_after_reset}, advantage={advantage_after_reset.value}"
        ),
    ]

    print("\n".join(target_lines))

    expected_target_lines = [
        "before import: score=5, advantage=None",
        "during import: score=7, advantage=Advantage",
        "imported breakdown contains Exposed Target: True",
        "after reset: score=5, advantage=None",
    ]
    assert target_lines == expected_target_lines
    assert capsys.readouterr().out.splitlines() == expected_target_lines
