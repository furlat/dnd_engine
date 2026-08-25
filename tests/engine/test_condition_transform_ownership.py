"""Ownership checks for condition-applied neutral entity transforms."""

from __future__ import annotations

import pytest
from uuid import uuid4

from dnd.actions.standard import (
    Disengage,
    Move,
    entity_action_economy_cost_evaluator,
)
from dnd.core.base_actions import (
    BaseAction,
    Cost,
)
from dnd.core.events.events_registry import (
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.types.materials import Material, TileSurface
from dnd.types.damage import DamageType
from dnd.types.world import LightLevel
from dnd.entities.entity import Entity
from dnd.content.monsters.monster_builders import create_monster
from dnd.game import Game
from dnd.conditions import Blinded, Incapacitated, Paralyzed, Stunned, Unconscious
from tests.engine.support import create_test_monster
from dnd.actions.reactions import add_opportunity_attack_handler
from dnd.spells.abjuration import (
    BanishedCondition,
)
from dnd.spells.enchantment import SleepEffect
from dnd.spells.illusion import HypnoticPatternEffect
from dnd.spells.necromancy import EyebiteAsleepEffect
from dnd.spells.transmutation import HasteLethargyEffect
from tests.engine.support import force_attack_hit, remove_attack_modifier
from tests.engine.test_combat_actions import (
    reset_core_action_state,
    strong_entity,
)


def _apply_condition(condition_type, source: Entity, target: Entity):
    """Apply one concrete condition and return its exact owner instance."""
    condition = condition_type(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )
    result = target.add_condition(condition)

    assert result is not None
    assert result.canceled is False
    assert target.active_conditions_by_uuid[condition.uuid] is condition
    return condition


def _cost_free_action(
    source: Entity,
    *,
    allow_while_incapacitated: bool = False,
) -> BaseAction:
    """Build a zero-cost probe whose only gate is permission to act."""
    return BaseAction(
        name="Cost-Free Permission Probe",
        source_entity_uuid=source.uuid,
        costs=[],
        allow_while_incapacitated=allow_while_incapacitated,
        use_register=False,
    )


def _reaction_action(source: Entity) -> BaseAction:
    """Build one pure reaction-cost action governed by the reaction channel."""
    return BaseAction(
        name="Reaction Permission Probe",
        source_entity_uuid=source.uuid,
        costs=[
            Cost(
                name="Reaction Permission Cost",
                cost_type="reactions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ],
        use_register=False,
    )


@pytest.mark.parametrize("removed_first", ["Blinded", "Unconscious"])
def test_visual_access_remains_denied_until_every_owner_is_removed(
    removed_first: str,
) -> None:
    """Blinded and Unconscious own independent visual-access constraints."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")

    assert target.senses.visual_access.normalized_score == 1
    assert target.can_see_visual_effects() is True

    owners = {
        "Blinded": _apply_condition(Blinded, source, target),
        "Unconscious": _apply_condition(Unconscious, source, target),
    }

    assert target.senses.visual_access.normalized_score == 0
    assert target.can_see_visual_effects() is False

    target.remove_condition_by_uuid(owners[removed_first].uuid)

    remaining = "Unconscious" if removed_first == "Blinded" else "Blinded"
    assert owners[remaining].uuid in target.active_conditions_by_uuid
    assert target.senses.visual_access.normalized_score == 0
    assert target.can_see_visual_effects() is False

    target.remove_condition_by_uuid(owners[remaining].uuid)

    assert target.senses.visual_access.normalized_score == 1
    assert target.can_see_visual_effects() is True


@pytest.mark.parametrize("removed_first", ["Unconscious", "Paralyzed"])
def test_severe_conditions_own_independent_action_and_movement_denials(
    removed_first: str,
) -> None:
    """Removing one severe condition cannot release another owner's denial."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    owners = {
        "Unconscious": _apply_condition(Unconscious, source, target),
        "Paralyzed": _apply_condition(Paralyzed, source, target),
    }

    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert _cost_free_action(target).check_costs() is False

    target.remove_condition_by_uuid(owners[removed_first].uuid)

    remaining = "Paralyzed" if removed_first == "Unconscious" else "Unconscious"
    assert owners[remaining].uuid in target.active_conditions_by_uuid
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert _cost_free_action(target).check_costs() is False

    target.remove_condition_by_uuid(owners[remaining].uuid)

    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert _cost_free_action(target).check_costs() is True


@pytest.mark.parametrize("condition_type", [Incapacitated, Stunned])
def test_action_permission_blocks_zero_cost_and_reaction_actions_when_capped(
    condition_type,
) -> None:
    """Severe denials close both the neutral gate and reaction resource."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    incapacitated = _apply_condition(condition_type, source, target)
    ordinary = _cost_free_action(target)
    reaction = _reaction_action(target)
    permitted_exception = _cost_free_action(
        target,
        allow_while_incapacitated=True,
    )

    assert ordinary.effective_costs == []
    assert permitted_exception.effective_costs == []
    assert target.action_economy.action_permission.normalized_score == 0
    assert ordinary.check_costs() is False
    assert target.action_economy.reactions.normalized_score == 0
    assert reaction.check_costs() is False
    assert permitted_exception.check_costs() is True

    target.remove_condition_by_uuid(incapacitated.uuid)

    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert ordinary.check_costs() is True
    assert reaction.check_costs() is True


def test_disengaging_owns_opportunity_attack_provocation_constraint() -> None:
    """Disengaging toggles provenance and the opportunity-attack outcome together."""
    reset_core_action_state()
    watcher = create_test_monster("monster.skeleton", 
        name="Watcher",
        position=(5, 5),
        faction="monsters",
    )
    mover = strong_entity("Mover", (5, 6), "heroes")
    add_opportunity_attack_handler(watcher)
    Entity.materialize_all_navigation(max_distance=20)

    assert mover.action_economy.provokes_opportunity_attacks.normalized_score == 1

    disengage_event = Disengage(source_entity_uuid=mover.uuid).apply()
    disengaging = mover.active_conditions.get("Disengaging")

    assert disengage_event is not None
    assert disengaging is not None
    assert mover.action_economy.provokes_opportunity_attacks.normalized_score == 0

    hp_before = mover.get_hp()
    hit_modifier = force_attack_hit(watcher)
    try:
        protected_move = Move(
            source_entity_uuid=mover.uuid,
            end_position=(5, 10),
        ).apply()

        assert protected_move is not None
        assert mover.get_hp() == hp_before
        assert watcher.action_economy.reactions.normalized_score == 1
        assert not any(
            event.name == "Opportunity Attack"
            for event in EventQueue.get_events_by_type(EventType.ATTACK)
        )

        mover.remove_condition_by_uuid(disengaging.uuid)
        assert mover.action_economy.provokes_opportunity_attacks.normalized_score == 1

        Entity.update_entity_position(mover, (5, 6))
        mover.action_economy.reset_all_costs()
        Entity.materialize_all_navigation(max_distance=20)
        unprotected_move = Move(
            source_entity_uuid=mover.uuid,
            end_position=(5, 10),
        ).apply()

        assert unprotected_move is not None
        assert mover.get_hp() < hp_before
        assert watcher.action_economy.reactions.normalized_score == 0
        assert any(
            event.name == "Opportunity Attack"
            for event in EventQueue.get_events_by_type(EventType.ATTACK)
        )
    finally:
        remove_attack_modifier(watcher, hit_modifier)


def test_magical_sleep_remains_after_healing_removes_life_state_transform() -> None:
    """Sleep remains after healing removes only life-state-owned modifiers."""
    reset_core_action_state()
    source = create_test_monster("monster.skeleton", 
        name="Source",
        position=(1, 1),
        faction="monsters",
    )
    target = strong_entity(
        "Death-Save Target",
        (2, 1),
        "heroes",
        uses_death_saves=True,
    )

    damage = target.receive_damage(
        amount=target.get_normal_hp(),
        damage_type=DamageType.SLASHING,
        source_entity_uuid=source.uuid,
    )
    assert damage > 0
    assert target.health.life_state.value == "dying"
    assert "Dying" not in target.active_conditions
    assert target.senses.visual_access.normalized_score == 0
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.can_see_visual_effects() is False

    sleep = _apply_condition(SleepEffect, source, target)
    assert target.active_conditions_by_uuid[sleep.uuid] is sleep
    assert target.senses.visual_access.normalized_score == 0
    assert target.action_economy.action_permission.normalized_score == 0

    healed = target.receive_healing(1, source_entity_uuid=target.uuid)

    assert healed == 1
    assert target.health.life_state.value == "alive"
    assert target.active_conditions_by_uuid[sleep.uuid] is sleep
    assert target.senses.visual_access.normalized_score == 0
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert target.can_see_visual_effects() is False
    assert _cost_free_action(target).check_costs() is False
    assert _reaction_action(target).check_costs() is False

    target.remove_condition_by_uuid(sleep.uuid)

    assert target.senses.visual_access.normalized_score == 1
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert target.can_see_visual_effects() is True
    assert _cost_free_action(target).check_costs() is True


@pytest.mark.parametrize(
    ("effect_type", "denies_visual_access"),
    [
        (SleepEffect, True),
        (EyebiteAsleepEffect, True),
        (HasteLethargyEffect, False),
    ],
)
def test_spell_local_control_effects_own_transforms_without_global_children(
    effect_type,
    denies_visual_access: bool,
) -> None:
    """Spell-local controls clean only their own directly installed gates."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")

    effect = _apply_condition(effect_type, source, target)

    assert effect.sub_conditions == []
    assert "Incapacitated" not in target.active_conditions
    assert "Unconscious" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert target.senses.visual_access.normalized_score == (
        0 if denies_visual_access else 1
    )

    target.remove_condition_by_uuid(effect.uuid)

    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert target.senses.visual_access.normalized_score == 1


def test_hypnotic_pattern_keeps_only_its_real_charmed_child() -> None:
    """Hypnotic Pattern owns denial directly while retaining Charmed linkage."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")

    effect = _apply_condition(HypnoticPatternEffect, source, target)

    assert "Hypnotic Pattern" in target.active_conditions
    assert "Charmed" in target.active_conditions
    assert "Incapacitated" not in target.active_conditions
    assert len(effect.sub_conditions) == 1
    assert target.active_conditions["Charmed"].uuid == effect.sub_conditions[0]
    assert target.action_economy.action_permission.normalized_score == 0

    target.remove_condition_by_uuid(effect.uuid)

    assert "Charmed" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 1


def test_banishment_owns_denial_and_restores_spatial_registration() -> None:
    """Banishment's direct transform and spatial removal share one owner."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    original_position = target.position
    get_map().set_tile_base_light(original_position, LightLevel.DARKNESS)
    attached_light_uuid = get_map().add_light_source(
        original_position,
        bright_radius_feet=5,
        dim_radius_feet=0,
        anchor_uuid=target.uuid,
    )
    assert get_map().get_tile(*original_position).resolved_light_level is LightLevel.BRIGHT_LIGHT

    application_cursor = EventQueue.event_cursor()
    effect = _apply_condition(BanishedCondition, source, target)

    assert effect.sub_conditions == []
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.uuid not in get_map().get_entities_at(original_position)
    assert target.get_attached_light_sources() == {attached_light_uuid}
    assert get_map().get_tile(*original_position).resolved_light_level is LightLevel.DARKNESS

    application_events = [
        event
        for _, event in EventQueue.iter_events_since(application_cursor)
        if event.event_type in {
            EventType.CONDITION_APPLICATION,
            EventType.SPATIAL_ENTITY_LEFT,
        }
    ]
    application_execution = next(
        event
        for event in application_events
        if event.phase is EventPhase.EXECUTION
    )
    left_completion = next(
        event
        for event in application_events
        if event.event_type == EventType.SPATIAL_ENTITY_LEFT
        and event.phase is EventPhase.COMPLETION
    )
    assert left_completion.parent_event == application_execution.uuid

    removal_cursor = EventQueue.event_cursor()
    target.remove_condition_by_uuid(effect.uuid)

    assert target.action_economy.action_permission.normalized_score == 1
    assert target.uuid in get_map().get_entities_at(original_position)
    assert get_map().get_tile(*original_position).resolved_light_level is LightLevel.BRIGHT_LIGHT
    removal_events = [
        event
        for _, event in EventQueue.iter_events_since(removal_cursor)
        if event.event_type == EventType.CONDITION_REMOVAL
        or event.event_type == EventType.SPATIAL_ENTITY_ENTERED
    ]
    removal_execution = next(
        event
        for event in removal_events
        if event.event_type == EventType.CONDITION_REMOVAL
        and event.phase is EventPhase.EXECUTION
    )
    entered_completion = next(
        event
        for event in removal_events
        if event.event_type == EventType.SPATIAL_ENTITY_ENTERED
        and event.phase is EventPhase.COMPLETION
    )
    assert entered_completion.parent_event == removal_execution.uuid


def test_banishment_suspend_publication_failure_compensates_without_condition_or_denial() -> None:
    """A failed terminal LEFT is compensated through one ordinary restore."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    condition = BanishedCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    def fail_left(event, _source_uuid):
        raise RuntimeError("injected banishment LEFT publication failure")

    handler = EventHandler(
        name="Fail banishment LEFT publication",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target.uuid,
            ),
        ],
        event_processor=fail_left,
    )
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(PositionPublicationError):
            target.add_condition(condition)
    finally:
        EventQueue.remove_event_handler(handler)

    assert target.is_deployed
    assert not target.is_spatially_suspended
    assert target.uuid in get_map().get_entities_at(target.position)
    assert target.active_conditions_by_uuid.get(condition.uuid) is None
    assert condition.applied is False
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30


def test_banishment_compensation_failure_preserves_publication_chain_without_presence() -> None:
    """A removed destination cannot make failed Banishment appear present."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    condition = BanishedCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    def remove_empty_target_tile_and_fail(event, _source_uuid):
        del event
        get_map().remove_tile(*target.position)
        raise RuntimeError("injected banishment LEFT publication failure")

    handler = EventHandler(
        name="Remove target tile during banishment LEFT",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target.uuid,
            ),
        ],
        event_processor=remove_empty_target_tile_and_fail,
    )
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(
            RuntimeError,
            match="Banishment suspension compensation invariant failed",
        ) as error:
            target.add_condition(condition)
    finally:
        EventQueue.remove_event_handler(handler)

    exception_chain = []
    current_error = error.value
    seen_error_ids = set()
    while current_error is not None and id(current_error) not in seen_error_ids:
        seen_error_ids.add(id(current_error))
        exception_chain.append(current_error)
        current_error = current_error.__cause__ or current_error.__context__
    original_publication_error = next(
        item for item in exception_chain
        if isinstance(item, PositionPublicationError)
    )
    assert any(
        isinstance(item, PositionCommitError)
        for item in exception_chain
    )
    assert isinstance(original_publication_error.cause, RuntimeError)
    assert "injected banishment LEFT publication failure" in str(
        original_publication_error.cause,
    )
    assert condition.applied is False
    assert target.active_conditions_by_uuid.get(condition.uuid) is None
    assert not target.is_deployed
    assert target.is_spatially_suspended
    assert target.position == (2, 1)
    assert get_map().get_entity_position(target.uuid) is None
    assert get_map().get_tile(*target.position) is None
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30


def test_banishment_suspend_precommit_failure_is_publicly_atomic() -> None:
    """A detached target cannot enter Banishment or leak its denial transform."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = create_monster("creature.commoner", uuid4(), faction="monsters")
    game = Game()
    game.deploy_entity(target, (2, 1))
    assert game.remove_entity(target.uuid) is target
    retained_position = target.position
    grid = get_map()
    before_tile = grid.get_entities_at(retained_position)
    before_cursor = EventQueue.event_cursor()
    condition = BanishedCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    with pytest.raises(RuntimeError, match="only a present Entity can be suspended"):
        target.add_condition(condition)

    assert condition.applied is False
    assert target.active_conditions_by_uuid.get(condition.uuid) is None
    assert not target.is_deployed
    assert not target.is_spatially_suspended
    assert target.position == retained_position
    assert grid.get_entity_position(target.uuid) is None
    assert grid.get_entities_at(retained_position) == before_tile
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert EventQueue.event_cursor() >= before_cursor


def test_banishment_provisional_failure_releases_all_denial_ownership() -> None:
    """Failure after transform installation leaves no provisional denial rows."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    condition = BanishedCondition(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )

    def fail_effect(event, _source_uuid):
        raise RuntimeError("injected banishment EFFECT failure")

    handler = EventHandler(
        name="Fail banishment condition effect",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.CONDITION_APPLICATION,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid,
            ),
        ],
        event_processor=fail_effect,
    )
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(RuntimeError, match="injected banishment EFFECT"):
            target.add_condition(condition)
    finally:
        EventQueue.remove_event_handler(handler)

    assert target.is_deployed
    assert not target.is_spatially_suspended
    assert target.uuid in get_map().get_entities_at(target.position)
    assert target.active_conditions_by_uuid.get(condition.uuid) is None
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30


def test_banishment_restore_failure_keeps_condition_retryable_and_then_cleans_up() -> None:
    """Restore precommit failure retains Banished; a later retry is ordinary."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    condition = _apply_condition(BanishedCondition, source, target)
    retained_position = target.position
    get_map().remove_tile(*retained_position)

    with pytest.raises(PositionCommitError):
        target.remove_condition_by_uuid(condition.uuid)

    assert condition.applied
    assert target.is_spatially_suspended
    assert target.active_conditions_by_uuid[condition.uuid] is condition
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0

    get_map().set_tile(
        *retained_position,
        surface=TileSurface(base_material=Material.STONE),
    )
    assert target.remove_condition_by_uuid(condition.uuid)
    assert target.is_deployed
    assert not target.is_spatially_suspended
    assert target.uuid in get_map().get_entities_at(retained_position)
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30


def test_banishment_restore_publication_failure_keeps_presence_and_finishes_cleanup() -> None:
    """Committed restore publication failure does not trigger a second restore."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    condition = _apply_condition(BanishedCondition, source, target)

    def fail_entered(event, _source_uuid):
        raise RuntimeError("injected banishment ENTERED publication failure")

    handler = EventHandler(
        name="Fail banishment ENTERED publication",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT,
                event_source_entity_uuid=target.uuid,
            ),
        ],
        event_processor=fail_entered,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert target.remove_condition_by_uuid(condition.uuid)
    finally:
        EventQueue.remove_event_handler(handler)

    assert target.is_deployed
    assert not target.is_spatially_suspended
    assert target.uuid in get_map().get_entities_at(target.position)
    assert target.active_conditions_by_uuid.get(condition.uuid) is None
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
