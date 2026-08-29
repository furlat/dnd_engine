"""Engine semantic tests for implemented standard D&D conditions."""
from dnd.types.materials import Material, TileSurface

from contextlib import contextmanager
from uuid import UUID, uuid4

import dnd.core.dice as dice_module
import dnd.conditions as conditions_module
from dnd.actions.operations import setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, ConditionRemovalEvent
from dnd.types.conditions import ConditionTag, DurationType
from dnd.core.base_object import BaseObject
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.resolution_events import (
    SkillCheckD20RollResultEvent,
)
from dnd.core.events.check_events import (
    SkillCheckEvent,
)
from dnd.types.abilities import SkillName
from dnd.core.gridmap import get_map
from dnd.types.life import LifeState
from dnd.types.damage import DamageType
from dnd.types.rolls import AdvantageStatus, AutoHitStatus, CriticalStatus
from dnd.types.damage import ResistanceStatus
from dnd.types.senses import PerceivedContact
from dnd.core.values import BaseValue
from dnd.entities.entity import Entity, EntityConfig
from dnd.conditions import (
    Blinded,
    Charmed,
    Deafened,
    Exhaustion,
    Frightened,
    Grappled,
    GreaterInvisibilityEffect,
    Hidden,
    Incapacitated,
    Invisible,
    InvisibilityEffect,
    Paralyzed,
    Petrified,
    Poisoned,
    Prone,
    Restrained,
    Stunned,
    Unconscious,
)
from tests.engine.support import create_test_entity, get_max_hp, reset_combat_state


@contextmanager
def fixed_d20(*values: int):
    """Replace d20 random results with deterministic values."""
    if not values:
        raise ValueError("fixed_d20 requires at least one value")
    original_randint = dice_module.random.randint
    queued = list(values)

    def fake_randint(low: int, high: int) -> int:
        assert low <= queued[0] <= high
        if len(queued) > 1:
            return queued.pop(0)
        return queued[0]

    dice_module.random.randint = fake_randint
    try:
        yield
    finally:
        dice_module.random.randint = original_randint


def reset_condition_state() -> None:
    """Clear global state touched by these condition examples."""
    reset_combat_state()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseValue._registry.clear()
    get_map().create_rectangle(0, 0, 20, 20, surface=TileSurface(base_material=Material.STONE))


def configured_entity(
    name: str,
    position: tuple[int, int],
    faction: str | None,
) -> Entity:
    """Create a deterministic entity for standard-condition examples."""
    source_uuid = uuid4()
    config = EntityConfig(
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
            ]
        ),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    return create_test_entity(
        source_id=source_uuid,
        name=name,
        config=config,
        entity_kind_id="test.standard_condition_entity",
    )


def apply_to_target(condition_type, source: Entity, target: Entity):
    """Apply `condition_type` from source to target and return the condition."""
    condition = condition_type(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )
    result = target.add_condition(condition)
    assert result is not None
    assert condition.name in target.active_conditions
    return condition


def test_condition_application_dispatches_effect_handlers_once() -> None:
    """A compound condition publishes one completed effect boundary."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")
    effect_calls = 0

    def count_effect(event: Event, _: UUID) -> Event:
        nonlocal effect_calls
        effect_calls += 1
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=target.uuid,
            name="Count condition effect dispatches",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target.uuid,
                )
            ],
            event_processor=count_effect,
        )
    )

    apply_to_target(Frightened, source, target)

    assert effect_calls == 1


def test_base_condition_respects_execution_cancellation() -> None:
    """An execution interceptor can veto a condition before state is applied."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")

    def cancel_execution(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="Condition vetoed at execution")

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=target.uuid,
            name="Veto condition execution",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.EXECUTION,
                    event_target_entity_uuid=target.uuid,
                )
            ],
            event_processor=cancel_execution,
        )
    )
    condition = BaseCondition(
        name="Lifecycle Probe",
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    result = target.add_condition(condition)

    assert result is not None and result.canceled
    assert not condition.applied
    assert condition.name not in target.active_conditions


def test_base_condition_respects_declaration_cancellation() -> None:
    """A declaration interceptor can veto a condition before execution."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")

    def cancel_declaration(event: Event, _: UUID) -> Event:
        return event.cancel(status_message="Condition vetoed at declaration")

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=target.uuid,
            name="Veto condition declaration",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_APPLICATION,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=target.uuid,
                )
            ],
            event_processor=cancel_declaration,
        )
    )
    condition = BaseCondition(
        name="Declaration Probe",
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    result = target.add_condition(condition)

    assert result is not None and result.canceled
    assert not condition.applied
    assert condition.name not in target.active_conditions


def test_expired_condition_removal_dispatches_each_phase_once() -> None:
    """Expiration is one removal lifecycle, not expire plus remove replays."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")
    condition = BaseCondition(
        name="Expiring Probe",
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )
    result = target.add_condition(condition)
    assert result is not None and not result.canceled
    dispatches = {
        EventPhase.EXECUTION: 0,
        EventPhase.EFFECT: 0,
    }

    def count_removal(event: Event, _: UUID) -> Event:
        dispatches[event.phase] += 1
        return event

    EventQueue.add_event_handler(
        EventHandler(
            source_entity_uuid=target.uuid,
            name="Count expiration removal dispatches",
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CONDITION_REMOVAL,
                    event_phase=phase,
                    event_target_entity_uuid=target.uuid,
                )
                for phase in dispatches
            ],
            event_processor=count_removal,
        )
    )

    assert condition.name is not None
    target.remove_condition(condition.name, expire=True)

    assert dispatches == {
        EventPhase.EXECUTION: 1,
        EventPhase.EFFECT: 1,
    }


def test_eb_08_001_blinded_and_deafened_apply_sensory_failures() -> None:
    """EB-08-001: Blinded and Deafened attach sensory auto-fail modifiers."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")
    attacker = configured_entity("Attacker", (3, 1), "heroes")

    apply_to_target(Blinded, source, target)

    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    target.equipment.ac_bonus.set_target_entity(attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    assert target.skill_set.perception.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS
    assert target.skill_set.investigation.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS
    assert target.skill_set.stealth.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS

    target.remove_condition("Blinded")
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    assert target.skill_set.perception.skill_bonus.auto_hit == AutoHitStatus.NONE

    apply_to_target(Deafened, source, target)

    assert target.skill_set.perception.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS
    assert target.skill_set.insight.skill_bonus.auto_hit == AutoHitStatus.AUTOMISS


def test_eb_08_002_charmed_blocks_attacks_and_helps_charmer_social_checks() -> None:
    """EB-08-002: Charmed is contextual to the charmer and charmed target."""
    reset_condition_state()
    charmer = configured_entity("Charmer", (1, 1), "heroes")
    target = configured_entity("Charmed Target", (2, 1), "monsters")
    bystander = configured_entity("Bystander", (3, 1), "heroes")

    apply_to_target(Charmed, charmer, target)

    target.equipment.attack_bonus.set_target_entity(charmer.uuid)
    assert target.equipment.attack_bonus.auto_hit == AutoHitStatus.AUTOMISS

    target.equipment.attack_bonus.set_target_entity(bystander.uuid)
    assert target.equipment.attack_bonus.auto_hit == AutoHitStatus.NONE

    persuasion_against_target = charmer.skill_bonus(target.uuid, "persuasion")
    assert persuasion_against_target.advantage == AdvantageStatus.ADVANTAGE

    persuasion_against_bystander = charmer.skill_bonus(bystander.uuid, "persuasion")
    assert persuasion_against_bystander.advantage == AdvantageStatus.NONE


def test_eb_08_003_poisoned_and_frightened_penalize_attacks_and_checks() -> None:
    """EB-08-003: Poisoned is static; Frightened is sight-contextual."""
    reset_condition_state()
    source = configured_entity("Frightener", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")

    apply_to_target(Poisoned, source, target)

    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.skill_set.perception.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE

    target.remove_condition("Poisoned")
    frightened = apply_to_target(Frightened, source, target)
    assert frightened.modifers_uuids

    target.senses.entities.clear()
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    target.senses.entities[source.uuid] = PerceivedContact(
        position=source.position,
        visual=True,
    )
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.action_economy.movement.normalized_score == 0


def test_eb_08_004_grappled_incapacitated_and_restrained_limit_actions() -> None:
    """EB-08-004: movement/action limiting conditions clamp action economy values."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")

    apply_to_target(Grappled, source, target)
    assert target.action_economy.movement.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 1

    target.remove_condition("Grappled")
    apply_to_target(Incapacitated, source, target)
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0

    target.remove_condition("Incapacitated")
    apply_to_target(Restrained, source, target)
    assert target.action_economy.movement.normalized_score == 0
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.advantage
        == AdvantageStatus.DISADVANTAGE
    )
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE


def test_eb_08_005_prone_uses_distance_context_for_incoming_attacks() -> None:
    """EB-08-005: Prone gives own attack disadvantage and distance-based incoming rolls."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Prone Target", (2, 1), "monsters")
    adjacent_attacker = configured_entity("Adjacent", (2, 2), "heroes")
    distant_attacker = configured_entity("Distant", (8, 8), "heroes")

    apply_to_target(Prone, source, target)

    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE

    target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE

    target.equipment.ac_bonus.set_target_entity(distant_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.DISADVANTAGE


def test_eb_08_006_severe_conditions_own_direct_denial_transforms() -> None:
    """EB-08-006: severe conditions directly own denial and save transforms."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "monsters")
    adjacent_attacker = configured_entity("Adjacent", (2, 2), "heroes")
    distant_attacker = configured_entity("Distant", (8, 8), "heroes")

    paralyzed = apply_to_target(Paralyzed, source, target)
    assert paralyzed.sub_conditions == []
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.AUTOCRIT
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    target.equipment.ac_bonus.set_target_entity(distant_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.NONE
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE

    target.remove_condition("Paralyzed")
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30

    stunned = apply_to_target(Stunned, source, target)
    assert stunned.sub_conditions == []
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE

    target.remove_condition("Stunned")

    assert stunned.applied is False
    assert "Stunned" not in target.active_conditions
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.auto_hit
        == AutoHitStatus.NONE
    )
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.auto_hit
        == AutoHitStatus.NONE
    )
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE

    unconscious = apply_to_target(Unconscious, source, target)
    assert unconscious.sub_conditions == []
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert target.senses.visual_access.normalized_score == 0
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.AUTOCRIT
    target.equipment.ac_bonus.set_target_entity(distant_attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.NONE

    target.remove_condition("Unconscious")

    assert unconscious.applied is False
    assert "Unconscious" not in target.active_conditions
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert target.senses.visual_access.normalized_score == 1
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.auto_hit
        == AutoHitStatus.NONE
    )
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.auto_hit
        == AutoHitStatus.NONE
    )
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE
    assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.NONE


def test_eb_08_007_invisible_sets_perceivability_and_unseen_combat_modifiers() -> None:
    """EB-08-007: Invisible toggles perceivability and contextual combat modifiers."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Invisible Target", (2, 1), "monsters")
    attacker = configured_entity("Attacker", (3, 1), "heroes")

    apply_to_target(Invisible, source, target)

    assert target.is_invisible is True
    target.equipment.attack_bonus.set_target_entity(attacker.uuid)
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.ADVANTAGE
    target.equipment.ac_bonus.set_target_entity(attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.DISADVANTAGE

    attacker.senses.entities[target.uuid] = PerceivedContact(
        position=target.position,
        visual=True,
    )
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE

    target.remove_condition("Invisible")
    assert target.is_invisible is False


def test_eb_08_008_srd_condition_gaps_are_explicit() -> None:
    """EB-08-008: remaining SRD condition gaps stay visible as gaps."""
    assert hasattr(conditions_module, "Petrified")
    assert hasattr(conditions_module, "Exhaustion")
    assert not hasattr(conditions_module, "Exhausted")


def test_eb_08_009_prone_immediate_stand_on_own_turn_cancels_indexing() -> None:
    """EB-08-009: Prone cancels into immediate stand if applied mid-turn."""
    reset_condition_state()
    target = configured_entity("Target", (2, 1), "heroes")

    target.on_turn_start()
    condition = Prone(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    result = target.add_condition(condition)

    assert result is not None
    assert result.phase == EventPhase.CANCEL
    assert result.canceled is True
    assert not any(
        event.lineage_uuid == result.lineage_uuid
        and event.phase is EventPhase.COMPLETION
        for _, event in EventQueue.iter_events_since(0)
    )
    assert condition.applied is False
    assert "Prone" not in target.active_conditions
    assert condition.uuid not in target.active_conditions_by_uuid
    assert BaseCondition.get(condition.uuid) is None
    assert target.action_economy.movement.normalized_score == 15


def test_eb_08_010_prone_auto_stand_handler_is_standard_action_state() -> None:
    """EB-08-010: setup_standard_actions registers turn-start prone auto-stand."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Target", (2, 1), "heroes")
    other = configured_entity("Other", (3, 1), "monsters")
    setup_standard_actions(target)

    apply_to_target(Prone, source, target)

    assert target.get_event_handler_by_name("Prone Auto-Stand") is not None
    assert "Prone" in target.active_conditions
    assert target.action_economy.movement.normalized_score == 30

    other.on_turn_start()

    assert "Prone" in target.active_conditions
    assert target.action_economy.movement.normalized_score == 30

    target.on_turn_start()

    assert "Prone" not in target.active_conditions
    assert target.action_economy.movement.normalized_score == 15


def test_eb_08_011_hidden_and_invisibility_reveal_handlers_filter_actions() -> None:
    """EB-08-011: reveal handlers ignore Dash and remove on revealing actions."""
    reset_condition_state()
    target = configured_entity("Target", (2, 1), "heroes")
    hidden = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=25,
    )

    target.add_condition(hidden)

    assert "Hidden" in target.active_conditions
    assert target.stealth_dc == 25

    ActionEvent(
        name="Dash",
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EFFECT)

    assert "Hidden" in target.active_conditions
    assert target.stealth_dc == 25

    ActionEvent(
        name="Shove",
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EFFECT)

    assert "Hidden" not in target.active_conditions
    assert target.stealth_dc is None

    invisible = InvisibilityEffect(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(invisible)

    assert "Invisible" in target.active_conditions
    assert target.is_invisible is True

    ActionEvent(
        name="Dash",
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EFFECT)

    assert "Invisible" in target.active_conditions
    assert target.is_invisible is True

    ActionEvent(
        name="Shove",
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EFFECT)

    assert "Invisible" not in target.active_conditions
    assert target.is_invisible is False


def test_eb_08_012_standard_condition_removal_cleans_owned_state() -> None:
    """EB-08-012: standard condition removal clears modifiers, flags, and trees."""
    condition_types = [
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
    ]
    severe_conditions = {Paralyzed, Petrified, Stunned, Unconscious}

    for condition_type in condition_types:
        reset_condition_state()
        source = configured_entity("Source", (1, 1), "heroes")
        target = configured_entity("Target", (2, 1), "monsters")
        adjacent_attacker = configured_entity("Adjacent", (2, 2), "heroes")

        target.senses.entities[source.uuid] = PerceivedContact(
            position=source.position,
            visual=True,
        )
        condition = apply_to_target(condition_type, source, target)
        if condition_type in severe_conditions:
            assert condition.sub_conditions == []
            assert "Incapacitated" not in target.active_conditions
            assert target.action_economy.action_permission.normalized_score == 0

        target.equipment.attack_bonus.set_target_entity(source.uuid)
        target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
        _ = source.skill_bonus(target.uuid, "persuasion")

        target.remove_condition(condition.name)

        assert condition.applied is False
        for subcondition_uuid in condition.sub_conditions:
            subcondition = BaseCondition.get(subcondition_uuid)
            if subcondition is not None:
                assert isinstance(subcondition, BaseCondition)
                assert subcondition.applied is False

        assert target.active_conditions == {}
        assert target.active_conditions_by_uuid == {}
        assert all(
            names == [] for names in target.active_conditions_by_source.values()
        )

        assert target.action_economy.actions.normalized_score == 1
        assert target.action_economy.bonus_actions.normalized_score == 1
        assert target.action_economy.reactions.normalized_score == 1
        assert target.action_economy.movement.normalized_score == 30
        assert target.action_economy.action_permission.normalized_score == 1
        assert target.senses.visual_access.normalized_score == 1

        target.equipment.attack_bonus.set_target_entity(source.uuid)
        assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
        assert target.equipment.attack_bonus.auto_hit == AutoHitStatus.NONE

        target.equipment.ac_bonus.set_target_entity(adjacent_attacker.uuid)
        assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE
        assert target.equipment.ac_bonus.outgoing_critical == CriticalStatus.NONE

        skill_names: list[SkillName] = [
            "athletics",
            "insight",
            "investigation",
            "perception",
            "persuasion",
            "stealth",
        ]
        for skill_name in skill_names:
            skill_bonus = target.skill_set.get_skill(skill_name).skill_bonus
            assert skill_bonus.advantage == AdvantageStatus.NONE
            assert skill_bonus.auto_hit == AutoHitStatus.NONE

        assert source.skill_bonus(target.uuid, "persuasion").advantage == (
            AdvantageStatus.NONE
        )
        assert target.saving_throws.get_saving_throw("strength").bonus.auto_hit == (
            AutoHitStatus.NONE
        )
        assert target.saving_throws.get_saving_throw("dexterity").bonus.auto_hit == (
            AutoHitStatus.NONE
        )
        assert target.saving_throws.get_saving_throw("dexterity").bonus.advantage == (
            AdvantageStatus.NONE
        )
        assert target.is_invisible is False
        assert not target.check_condition_immunity("Poisoned")
        for damage_type in DamageType:
            assert target.health.get_resistance(damage_type) == ResistanceStatus.NONE


def test_eb_08_013_greater_invisibility_uses_stealth_checks_instead_of_reveal() -> None:
    """EB-08-013: Greater Invisibility persists or ends by stealth checks."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Invisible Target", (2, 1), "heroes")
    attacker = configured_entity("Attacker", (3, 1), "monsters")

    greater = GreaterInvisibilityEffect(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        base_dc=10,
    )
    target.add_condition(greater)

    assert target.active_conditions["Invisible"] is greater
    assert target.is_invisible is True
    assert target.get_event_handler_by_name("Greater Invisibility: Stealth Check") is not None

    target.equipment.attack_bonus.set_target_entity(attacker.uuid)
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.ADVANTAGE
    target.equipment.ac_bonus.set_target_entity(attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.DISADVANTAGE

    ActionEvent(
        name="Dash",
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        phase=EventPhase.DECLARATION,
    ).phase_to(EventPhase.EFFECT)

    assert target.active_conditions["Invisible"] is greater
    assert greater.check_count == 0

    with fixed_d20(20):
        ActionEvent(
            name="Shove",
            source_entity_uuid=target.uuid,
            target_entity_uuid=attacker.uuid,
            phase=EventPhase.DECLARATION,
        ).phase_to(EventPhase.EFFECT)

    assert target.active_conditions["Invisible"] is greater
    assert target.is_invisible is True
    assert greater.check_count == 1

    with fixed_d20(1):
        ActionEvent(
            name="Shove",
            source_entity_uuid=target.uuid,
            target_entity_uuid=attacker.uuid,
            phase=EventPhase.DECLARATION,
        ).phase_to(EventPhase.EFFECT)

    assert "Invisible" not in target.active_conditions
    assert target.is_invisible is False
    assert greater.applied is False
    assert target.get_event_handler_by_name("Greater Invisibility: Stealth Check") is None

    completed_checks = [
        row
        for row in EventQueue._all_events
        if isinstance(row, SkillCheckEvent)
        and row.phase is EventPhase.COMPLETION
    ]
    assert len(completed_checks) == 2
    failed_check = completed_checks[-1]
    failed_children = [
        EventQueue._events_by_lineage[lineage_uuid][-1]
        for lineage_uuid in failed_check.children_lineages
    ]
    assert any(
        isinstance(child, SkillCheckD20RollResultEvent)
        for child in failed_children
    )
    assert any(
        isinstance(child, ConditionRemovalEvent)
        for child in failed_children
    )
    assert failed_check.combat_log is not None
    assert failed_check.combat_log.data["skill"] == "stealth"
    assert failed_check.combat_log.data["success"] is False


def test_greater_invisibility_expires_after_ten_owner_turns() -> None:
    """Greater Invisibility's declared ten-round limit uses condition expiry."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Invisible Target", (2, 1), "heroes")
    greater = GreaterInvisibilityEffect(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    target.add_condition(greater)

    assert greater.duration.duration_type is DurationType.ROUNDS
    assert greater.duration.duration == 10
    for _ in range(9):
        assert target.advance_duration_condition("Invisible") is False
        assert target.is_invisible is True

    assert target.advance_duration_condition("Invisible") is True
    assert "Invisible" not in target.active_conditions
    assert target.is_invisible is False


def test_eb_08_014_petrified_composes_severe_control_and_all_damage_resistance() -> None:
    """EB-08-014: Petrified composes severe-control and resistance effects."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Petrified Target", (2, 1), "monsters")
    attacker = configured_entity("Attacker", (2, 2), "heroes")

    petrified = apply_to_target(Petrified, source, target)

    assert ConditionTag.PETRIFICATION in petrified.tags
    assert petrified.sub_conditions == []
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert (
        target.saving_throws.get_saving_throw("strength").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    assert (
        target.saving_throws.get_saving_throw("dexterity").bonus.auto_hit
        == AutoHitStatus.AUTOMISS
    )
    target.equipment.ac_bonus.set_target_entity(attacker.uuid)
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.ADVANTAGE
    for damage_type in DamageType:
        assert target.health.get_resistance(damage_type) == ResistanceStatus.RESISTANCE

    assert target.check_condition_immunity("Poisoned")
    poison_event = target.add_condition(
        Poisoned(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid)
    )
    assert poison_event is not None
    assert poison_event.canceled is True
    assert "Poisoned" not in target.active_conditions

    target.remove_condition("Petrified")

    assert "Petrified" not in target.active_conditions
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert not target.check_condition_immunity("Poisoned")
    assert target.equipment.ac_bonus.outgoing_advantage == AdvantageStatus.NONE
    for damage_type in DamageType:
        assert target.health.get_resistance(damage_type) == ResistanceStatus.NONE


def test_eb_08_015_exhaustion_levels_are_cumulative_and_removable() -> None:
    """EB-08-015: Exhaustion levels compose cumulative SRD effects."""
    reset_condition_state()
    source = configured_entity("Source", (1, 1), "heroes")
    target = configured_entity("Exhausted Target", (2, 1), "monsters")
    setup_standard_actions(target)
    base_movement = target.action_economy.movement.normalized_score
    base_max_hp = get_max_hp(target)

    level_one = apply_to_target(
        lambda **kwargs: Exhaustion(level=1, **kwargs),
        source,
        target,
    )
    assert ConditionTag.EXHAUSTION in level_one.tags
    assert target.skill_set.athletics.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.NONE
    target.remove_condition("Exhaustion")

    apply_to_target(lambda **kwargs: Exhaustion(level=2, **kwargs), source, target)
    assert target.skill_set.perception.skill_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert target.action_economy.movement.normalized_score == base_movement // 2
    target.remove_condition("Exhaustion")

    apply_to_target(lambda **kwargs: Exhaustion(level=3, **kwargs), source, target)
    assert target.equipment.attack_bonus.advantage == AdvantageStatus.DISADVANTAGE
    assert (
        target.saving_throws.get_saving_throw("wisdom").bonus.advantage
        == AdvantageStatus.DISADVANTAGE
    )
    target.remove_condition("Exhaustion")

    apply_to_target(lambda **kwargs: Exhaustion(level=4, **kwargs), source, target)
    assert get_max_hp(target) == base_max_hp // 2
    target.remove_condition("Exhaustion")
    assert get_max_hp(target) == base_max_hp

    apply_to_target(lambda **kwargs: Exhaustion(level=5, **kwargs), source, target)
    assert target.action_economy.movement.normalized_score == 0
    target.remove_condition("Exhaustion")

    apply_to_target(lambda **kwargs: Exhaustion(level=6, **kwargs), source, target)
    assert target.health.life_state is LifeState.DEAD
    assert not target.has_hp


if __name__ == "__main__":
    test_eb_08_001_blinded_and_deafened_apply_sensory_failures()
    test_eb_08_002_charmed_blocks_attacks_and_helps_charmer_social_checks()
    test_eb_08_003_poisoned_and_frightened_penalize_attacks_and_checks()
    test_eb_08_004_grappled_incapacitated_and_restrained_limit_actions()
    test_eb_08_005_prone_uses_distance_context_for_incoming_attacks()
    test_eb_08_006_severe_conditions_own_direct_denial_transforms()
    test_eb_08_007_invisible_sets_perceivability_and_unseen_combat_modifiers()
    test_eb_08_008_srd_condition_gaps_are_explicit()
    test_eb_08_009_prone_immediate_stand_on_own_turn_cancels_indexing()
    test_eb_08_010_prone_auto_stand_handler_is_standard_action_state()
    test_eb_08_011_hidden_and_invisibility_reveal_handlers_filter_actions()
    test_eb_08_012_standard_condition_removal_cleans_owned_state()
    test_eb_08_013_greater_invisibility_uses_stealth_checks_instead_of_reveal()
    test_eb_08_014_petrified_composes_severe_control_and_all_damage_resistance()
    test_eb_08_015_exhaustion_levels_are_cumulative_and_removable()
    print("Chapter 08 engine-book standard condition tests passed.")
