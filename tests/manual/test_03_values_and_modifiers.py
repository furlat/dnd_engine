"""Tutorial tests for values, modifiers, context, and target propagation."""

from typing import Optional
from uuid import UUID, uuid4

from dnd.core.base_object import BaseObject
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    AutoHitModifier,
    AutoHitStatus,
    ContextualNumericalModifier,
    CriticalModifier,
    CriticalStatus,
    NumericalModifier,
    ResistanceModifier,
    ResistanceStatus,
)
from dnd.core.values import (
    ModifiableValue,
    ValueRead,
    outgoing_of,
    read_value,
    Channel,
    Kind,
    add_modifier,
    parts,
    composed,
    value_breakdown,
)


def reset_value_state() -> None:
    """Clear global indexes touched by these value and modifier examples."""
    BaseObject._registry.clear()
    ModifiableValue._registry.clear()


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
    armor_class = ModifiableValue(
        source_entity_uuid=hero_id,
        name="Armor Class",
        base=10,
    )
    add_modifier(armor_class, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier.create(
            source_entity_uuid=hero_id,
            target_entity_uuid=hero_id,
            name="Shield",
            value=2,
        ))
    add_modifier(armor_class, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier.create(
            source_entity_uuid=hero_id,
            target_entity_uuid=hero_id,
            name="Defense Style",
            value=1,
        ))

    breakdown = value_breakdown(parts(armor_class))
    breakdown_names = ", ".join(entry.name for entry in breakdown)
    modifier_text = (
        f"{breakdown[1].name} +{breakdown[1].value}, "
        f"{breakdown[2].name} +{breakdown[2].value}"
    )
    lookup_state = (
        "same live value"
        if ModifiableValue.get(armor_class.uuid) is armor_class
        else "different value"
    )
    readout_lines = [
        f"value: {armor_class.name}",
        f"base score: {breakdown[0].value}",
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

    strength_score = ModifiableValue(
        source_entity_uuid=hero_id,
        name="strength Ability Score",
        base=16,
        score_normalizer=ability_score_normalizer,
    )

    assert strength_score.score == 16
    assert strength_score.normalized_score == 3

    attack_bonus = ModifiableValue(
        source_entity_uuid=hero_id,
        name="Attack Bonus",
        base=1,
    )
    add_modifier(attack_bonus, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier.create(
            source_entity_uuid=hero_id,
            name="Magic Weapon",
            value=1,
        ))

    combined_attack_bonus = read_value(composed(parts(strength_score, attack_bonus)), ValueRead(hero_id))

    assert combined_attack_bonus.name == "strength Ability Score_Attack Bonus"
    assert combined_attack_bonus.score == 18
    assert combined_attack_bonus.normalized_score == 5
    combined_breakdown = combined_attack_bonus.breakdown
    assert [(entry.name, entry.value, entry.source) for entry in combined_breakdown] == [
        ("STR", 3, "self"),
        ("Base", 1, "self"),
        ("Magic Weapon", 1, "self"),
    ]
    breakdown_parts = [
        f"{entry.name}={entry.value}"
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
        "combined value: strength Ability Score_Attack Bonus",
        "combined score: raw=18, normalized=5",
        "breakdown: STR=3, Base=1, Magic Weapon=1",
    ]
    assert score_lines == expected_score_lines
    assert capsys.readouterr().out.splitlines() == expected_score_lines


def test_static_channels_print_constraints_roll_states_and_resistances(capsys) -> None:
    """Static modifier buckets print constraints and non-numerical states."""
    reset_value_state()
    hero_id = uuid4()

    movement = ModifiableValue(
        source_entity_uuid=hero_id,
        name="Movement",
        base=30,
    )
    add_modifier(movement, Channel.SELF_STATIC, Kind.MAX, NumericalModifier.create(
            source_entity_uuid=hero_id,
            name="Grappled",
            value=0,
        ))
    movement_after_grapple = movement.score
    assert movement_after_grapple == 0

    attack_roll_state = ModifiableValue(
        source_entity_uuid=hero_id,
        name="Attack Roll State",
    )
    add_modifier(attack_roll_state, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
            source_entity_uuid=hero_id,
            name="Unseen Attacker",
            value=AdvantageStatus.ADVANTAGE,
        ))
    advantage_after_unseen = attack_roll_state.advantage
    assert advantage_after_unseen == AdvantageStatus.ADVANTAGE

    add_modifier(attack_roll_state, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
            source_entity_uuid=hero_id,
            name="Long Range",
            value=AdvantageStatus.DISADVANTAGE,
        ))
    advantage_after_long_range = attack_roll_state.advantage
    assert advantage_after_long_range == AdvantageStatus.NONE

    add_modifier(attack_roll_state, Channel.SELF_STATIC, Kind.CRITICAL, CriticalModifier(
            source_entity_uuid=hero_id,
            name="Paralyzed Target",
            value=CriticalStatus.AUTOCRIT,
        ))
    add_modifier(attack_roll_state, Channel.SELF_STATIC, Kind.CRITICAL, CriticalModifier(
            source_entity_uuid=hero_id,
            name="Critical Immunity",
            value=CriticalStatus.NOCRIT,
        ))
    critical_state = attack_roll_state.critical
    assert critical_state == CriticalStatus.NOCRIT

    add_modifier(attack_roll_state, Channel.SELF_STATIC, Kind.AUTO_HIT, AutoHitModifier(
            source_entity_uuid=hero_id,
            name="Guided Strike",
            value=AutoHitStatus.AUTOHIT,
        ))
    add_modifier(attack_roll_state, Channel.SELF_STATIC, Kind.AUTO_HIT, AutoHitModifier(
            source_entity_uuid=hero_id,
            name="Sanctuary",
            value=AutoHitStatus.AUTOMISS,
        ))
    auto_hit_state = attack_roll_state.auto_hit
    assert auto_hit_state == AutoHitStatus.AUTOMISS

    damage_response = ModifiableValue(
        source_entity_uuid=hero_id,
        name="Damage Response",
    )
    add_modifier(damage_response, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(
            source_entity_uuid=hero_id,
            name="Fire Resistance",
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.FIRE,
        ))
    fire_after_resistance = damage_response.resistance[DamageType.FIRE]
    assert fire_after_resistance == ResistanceStatus.RESISTANCE

    add_modifier(damage_response, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(
            source_entity_uuid=hero_id,
            name="Oil Vulnerability",
            value=ResistanceStatus.VULNERABILITY,
            damage_type=DamageType.FIRE,
        ))
    fire_after_vulnerability = damage_response.resistance[DamageType.FIRE]
    assert fire_after_vulnerability == ResistanceStatus.NONE

    add_modifier(damage_response, Channel.SELF_STATIC, Kind.RESISTANCE, ResistanceModifier(
            source_entity_uuid=hero_id,
            name="Fire Immunity",
            value=ResistanceStatus.IMMUNITY,
            damage_type=DamageType.FIRE,
        ))
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

    ranged_attack_bonus = ModifiableValue(
        source_entity_uuid=hero_id,
        name="Ranged Attack Bonus",
        base=5,
    )
    add_modifier(ranged_attack_bonus, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
            source_entity_uuid=hero_id,
            target_entity_uuid=goblin_id,
            name="High Ground",
            callable=high_ground_bonus,
        ))

    score_without_context = ranged_attack_bonus.score
    assert score_without_context == 5

    high_ground = read_value(parts(ranged_attack_bonus), ValueRead(hero_id, goblin_id, {"has_high_ground": True}))
    score_with_high_ground = high_ground.score
    assert score_with_high_ground == 7
    static_breakdown_lists_high_ground = any(row.name == "High Ground" for row in high_ground.breakdown)

    level_ground = read_value(parts(ranged_attack_bonus), ValueRead(hero_id, goblin_id, {"has_high_ground": False}))
    score_after_context_cleared = level_ground.score
    assert score_after_context_cleared == 5

    context_lines = [
        f"score without context: {score_without_context}",
        f"score with high ground: {score_with_high_ground}",
        (
            "static breakdown lists High Ground: "
            f"{static_breakdown_lists_high_ground}"
        ),
        f"score in another context: {score_after_context_cleared}",
    ]

    print("\n".join(context_lines))

    expected_context_lines = [
        "score without context: 5",
        "score with high ground: 7",
        "static breakdown lists High Ground: False",
        "score in another context: 5",
    ]
    assert context_lines == expected_context_lines
    assert capsys.readouterr().out.splitlines() == expected_context_lines


def test_opposed_read_prints_the_opponent_outgoing_modifiers(capsys) -> None:
    """A value read against an opponent includes the opponent's outgoing modifiers; a plain read does not."""
    reset_value_state()
    hero_id = uuid4()
    blinded_goblin_id = uuid4()

    hero_attack = ModifiableValue(
        source_entity_uuid=hero_id,
        name="Attack Bonus",
        base=5,
    )
    goblin_defense = ModifiableValue(
        source_entity_uuid=blinded_goblin_id,
        name="Armor Class",
        base=13,
    )

    add_modifier(goblin_defense, Channel.TO_TARGET_STATIC, Kind.ADVANTAGE, AdvantageModifier(
            source_entity_uuid=blinded_goblin_id,
            target_entity_uuid=hero_id,
            name="Blinded",
            value=AdvantageStatus.ADVANTAGE,
        ))
    add_modifier(goblin_defense, Channel.TO_TARGET_STATIC, Kind.VALUE, NumericalModifier.create(
            source_entity_uuid=blinded_goblin_id,
            target_entity_uuid=hero_id,
            name="Exposed Target",
            value=2,
        ))

    score_before_import = hero_attack.score
    advantage_before_import = hero_attack.advantage
    assert score_before_import == 5
    assert advantage_before_import == AdvantageStatus.NONE

    opposed = read_value(parts(hero_attack), ValueRead(hero_id, blinded_goblin_id,
                                                opponent=outgoing_of(parts(goblin_defense), None)))
    score_during_import = opposed.score
    advantage_during_import = opposed.advantage
    assert score_during_import == 7
    assert advantage_during_import == AdvantageStatus.ADVANTAGE
    assert any(row.name == "Exposed Target" and row.value == 2 and row.source == "from_target"
               for row in opposed.breakdown)
    imported_breakdown_has_exposed_target = any(row.name == "Exposed Target" for row in opposed.breakdown)

    score_after_reset = hero_attack.score
    advantage_after_reset = hero_attack.advantage
    assert score_after_reset == 5
    assert advantage_after_reset == AdvantageStatus.NONE

    target_lines = [
        (
            "before the opposed read: "
            f"score={score_before_import}, advantage={advantage_before_import.value}"
        ),
        (
            "opposed read: "
            f"score={score_during_import}, advantage={advantage_during_import.value}"
        ),
        (
            "imported breakdown contains Exposed Target: "
            f"{imported_breakdown_has_exposed_target}"
        ),
        (
            "plain read: "
            f"score={score_after_reset}, advantage={advantage_after_reset.value}"
        ),
    ]

    print("\n".join(target_lines))

    expected_target_lines = [
        "before the opposed read: score=5, advantage=None",
        "opposed read: score=7, advantage=Advantage",
        "imported breakdown contains Exposed Target: True",
        "plain read: score=5, advantage=None",
    ]
    assert target_lines == expected_target_lines
    assert capsys.readouterr().out.splitlines() == expected_target_lines
