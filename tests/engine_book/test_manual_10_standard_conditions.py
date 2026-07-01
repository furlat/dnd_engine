"""Manual Chapter 10 checks for standard condition families."""

from uuid import uuid4

from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import (
    Blinded,
    Charmed,
    Deafened,
    Exhaustion,
    Frightened,
    Grappled,
    Incapacitated,
    Invisible,
    Paralyzed,
    Petrified,
    Poisoned,
    Prone,
    Restrained,
    Stunned,
    Unconscious,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionTag
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.core.modifiers import (
    AdvantageStatus,
    AutoHitStatus,
    CriticalStatus,
    DamageType,
    ResistanceStatus,
)
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.utils import reset_combat_state


def reset_standard_condition_state() -> None:
    """Clear global state touched by standard-condition examples."""
    reset_combat_state()
    EventQueue.set_combat_log_callback(None)
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    get_map().create_rectangle(0, 0, 20, 20)


def create_tutorial_actor(
    name: str,
    position: tuple[int, int],
    faction: str | None,
) -> Entity:
    """Create an actor with stable ability, health, and movement values."""
    actor_id = uuid4()
    return Entity.create(
        source_entity_uuid=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=14),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=14),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(hit_dice_value=8, hit_dice_count=2, mode="maximums")
                ],
            ),
            action_economy=ActionEconomyConfig(),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
    )


def apply_condition(condition_type, source: Entity, target: Entity, **kwargs) -> BaseCondition:
    """Apply a standard condition type from source to target."""
    condition = condition_type(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        **kwargs,
    )
    result = target.add_condition(condition)
    assert result is not None
    assert condition.name in target.active_conditions
    return condition


def test_sensory_conditions_change_attacks_incoming_attacks_and_skills() -> None:
    """Blinded and Deafened apply the expected sensory penalties."""
    reset_standard_condition_state()
    source = create_tutorial_actor("Source", (1, 1), "heroes")
    target = create_tutorial_actor("Target", (2, 1), "monsters")
    attacker = create_tutorial_actor("Attacker", (3, 1), "heroes")

    apply_condition(Blinded, source, target)

    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    target.equipment.ac_bonus.set_target_entity(attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    assert target.skill_set.perception.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS
    assert target.skill_set.investigation.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS
    assert target.skill_set.stealth.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS

    target.remove_condition("Blinded")
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    assert target.skill_set.perception.skill_bonus.auto_hit == AutoHitStatus.NONE

    apply_condition(Deafened, source, target)

    assert target.skill_set.perception.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS
    assert target.skill_set.insight.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS


def test_social_poison_and_fear_conditions_use_context_or_static_pressure() -> None:
    """Charmed, Poisoned, and Frightened cover social, static, and sensed pressure."""
    reset_standard_condition_state()
    charmer = create_tutorial_actor("Charmer", (1, 1), "heroes")
    target = create_tutorial_actor("Target", (2, 1), "monsters")
    bystander = create_tutorial_actor("Bystander", (4, 1), "heroes")

    apply_condition(Charmed, charmer, target)

    target.equipment.attack_bonus.set_target_entity(charmer.uuid)
    assert target.equipment.attack_bonus.auto_hit == AutoHitStatus.AUTOMISS

    target.equipment.attack_bonus.set_target_entity(bystander.uuid)
    assert target.equipment.attack_bonus.auto_hit == AutoHitStatus.NONE

    assert charmer.skill_bonus(target.uuid, "persuasion").advantage == AdvantageStatus.ADVANTAGE
    assert charmer.skill_bonus(bystander.uuid, "persuasion").advantage == AdvantageStatus.NONE

    target.remove_condition("Charmed")
    apply_condition(Poisoned, charmer, target)

    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.skill_set.perception.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE

    target.remove_condition("Poisoned")
    apply_condition(Frightened, charmer, target)

    target.senses.entities.clear()
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    assert target.action_economy.movement.normalized_score == 30

    target.senses.entities[charmer.uuid] = charmer.position
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.action_economy.movement.normalized_score == 0


def test_movement_and_control_conditions_clamp_action_economy_values() -> None:
    """Grappled, Incapacitated, and Restrained limit movement and action choices."""
    reset_standard_condition_state()
    source = create_tutorial_actor("Source", (1, 1), "heroes")
    target = create_tutorial_actor("Target", (2, 1), "monsters")

    apply_condition(Grappled, source, target)
    assert target.action_economy.movement.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 1

    target.remove_condition("Grappled")
    apply_condition(Incapacitated, source, target)
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0

    target.remove_condition("Incapacitated")
    apply_condition(Restrained, source, target)
    assert target.action_economy.movement.normalized_score == 0
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.advantage
        == AdvantageStatus.DISADVANTAGE
    )
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE


def test_posture_and_invisibility_use_attacker_context() -> None:
    """Prone and Invisible change combat math based on distance or senses."""
    reset_standard_condition_state()
    source = create_tutorial_actor("Source", (1, 1), "heroes")
    target = create_tutorial_actor("Target", (2, 1), "monsters")
    adjacent_attacker = create_tutorial_actor("Adjacent", (2, 2), "heroes")
    distant_attacker = create_tutorial_actor("Distant", (8, 8), "heroes")

    apply_condition(Prone, source, target)

    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    target.equipment.ac_bonus.set_target_entity(distant_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.DISADVANTAGE

    target.remove_condition("Prone")
    apply_condition(Invisible, source, target)

    assert target.is_invisible is True
    target.equipment.attack_bonus.set_target_entity(adjacent_attacker.uuid)
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.ADVANTAGE
    target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.DISADVANTAGE

    adjacent_attacker.senses.entities[target.uuid] = target.position
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE

    target.remove_condition("Invisible")
    assert target.is_invisible is False


def test_severe_conditions_create_incapacitated_subtrees() -> None:
    """Paralyzed, Stunned, and Unconscious add Incapacitated plus incoming penalties."""
    reset_standard_condition_state()
    source = create_tutorial_actor("Source", (1, 1), "heroes")
    target = create_tutorial_actor("Target", (2, 1), "monsters")
    adjacent_attacker = create_tutorial_actor("Adjacent", (2, 2), "heroes")
    distant_attacker = create_tutorial_actor("Distant", (8, 8), "heroes")

    paralyzed = apply_condition(Paralyzed, source, target)
    assert len(paralyzed.sub_conditions) == 1
    assert "Incapacitated" in target.active_conditions
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.AUTOCRIT
    target.equipment.ac_bonus.set_target_entity(distant_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.NONE

    target.remove_condition("Paralyzed")
    assert "Incapacitated" not in target.active_conditions

    stunned = apply_condition(Stunned, source, target)
    assert len(stunned.sub_conditions) == 1
    assert "Incapacitated" in target.active_conditions
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    target.remove_condition("Stunned")
    assert "Incapacitated" not in target.active_conditions

    unconscious = apply_condition(Unconscious, source, target)
    assert len(unconscious.sub_conditions) == 1
    assert "Incapacitated" in target.active_conditions
    target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.AUTOCRIT
    target.equipment.ac_bonus.set_target_entity(distant_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE


def test_exhaustion_and_petrified_are_heavyweight_condition_families() -> None:
    """Exhaustion is levelled; Petrified combines control, resistance, and immunity."""
    reset_standard_condition_state()
    source = create_tutorial_actor("Source", (1, 1), "heroes")
    target = create_tutorial_actor("Target", (2, 1), "monsters")
    attacker = create_tutorial_actor("Attacker", (3, 1), "heroes")
    base_max_hp = target.get_max_hp()

    exhaustion = apply_condition(Exhaustion, source, target, level=1)
    assert ConditionTag.EXHAUSTION in exhaustion.tags
    assert target.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE

    target.remove_condition("Exhaustion")
    apply_condition(Exhaustion, source, target, level=3)
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert (
        target.saving_throws.get_saving_throw("wisdom").bonus.advantage
        == AdvantageStatus.DISADVANTAGE
    )

    target.remove_condition("Exhaustion")
    apply_condition(Exhaustion, source, target, level=4)
    assert target.get_max_hp() == base_max_hp // 2

    target.remove_condition("Exhaustion")
    petrified = apply_condition(Petrified, source, target)
    assert ConditionTag.PETRIFICATION in petrified.tags
    assert "Incapacitated" in target.active_conditions
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    target.equipment.ac_bonus.set_target_entity(attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    assert target.health.get_resistance(DamageType.FIRE) == ResistanceStatus.RESISTANCE
    assert target.health.get_resistance(DamageType.SLASHING) == ResistanceStatus.RESISTANCE
    assert target.check_condition_immunity("Poisoned") is True

    target.remove_condition("Petrified")
    assert "Incapacitated" not in target.active_conditions
    assert target.check_condition_immunity("Poisoned") is False
