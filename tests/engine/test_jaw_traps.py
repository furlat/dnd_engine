"""Ground contact, exact-source capture, escape and independent restraint cleanup."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions import Jump, Move
from dnd.actions_functional import execute_use_action, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.conditions import Restrained
from dnd.content.items.environment_item_builders import build_trap_lever
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.base_actions import ActionEvent
from dnd.core.condition_types import ConditionTag
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, MechanismActivationEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.jaws import ForceJawOpen, JawRestrained, SlipFreeOfJaw, materialize_jaw_trap
from dnd.spells.abjuration import AntimagicFieldZone, FreedomOfMovement, FreedomOfMovementEscape
from dnd.spatial.mechanisms import LaneGeometry, materialize_finite_trap
from dnd.spatial.gas_traps import materialize_gas_vent
from dnd.spells.conjuration import EscapeWebAction, WebRestrained
from dnd.types.traps import TrapState
from dnd.types.world import OccupancyLayer


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(8, 6))
    game = Game()
    try:
        yield game
    finally:
        game.close()
        reset_engine_runtime()


def actor(game: Game, position=(2, 3)) -> Entity:
    entity = Entity.create(uuid4(), "Traveler", config=EntityConfig(position=position,
        action_economy=ActionEconomyConfig(spell_slots={4: 1}),
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
    setup_standard_actions(entity)
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def control(trap) -> Event:
    return EventQueue.publish_declaration(Event(source_entity_uuid=trap.uuid, name="Trap control",
        event_type=EventType.BASE_ACTION, use_register=False)).phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)


def pulse(trap, *faces: int) -> MechanismActivationEvent:
    cause = control(trap)
    with fixed_dice_faces(*faces):
        event = trap.fire(parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    return event


def jaw_source(target: Entity) -> JawRestrained:
    return next(source for source in target.active_conditions_by_uuid.values() if isinstance(source, JawRestrained))


@pytest.mark.parametrize("saved", (False, True))
def test_failed_save_captures_success_leaves_sprung_empty(arena, saved):
    target = actor(arena)
    jaw = materialize_jaw_trap(target.position)
    cursor = EventQueue.event_cursor()
    result = pulse(jaw, *((20,) if saved else (1, 4)))
    assert result.committed and result.target_entity_uuid == target.uuid
    assert result.mechanism_content_ref == jaw.content_ref
    assert jaw.trap_state is TrapState.ACTIVATED
    assert target.get_hp() == (80 if saved else 76)
    assert ("Restrained" in target.active_conditions) is not saved
    assert target.action_economy.movement.normalized_score == (30 if saved else 0)
    assert pulse(jaw).canceled and target.get_hp() == (80 if saved else 76)
    if not saved:
        source = jaw_source(target)
        assert jaw.linked_conditions == [(target.uuid, source.uuid)]
        assert source.tags == set()
        assert {type(action) for action in target.registered_actions
                if isinstance(action, (ForceJawOpen, SlipFreeOfJaw))} == {ForceJawOpen, SlipFreeOfJaw}
        observed = next(event.condition_state for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ConditionApplicationEvent) and isinstance(event.condition, JawRestrained)
            and event.phase is EventPhase.COMPLETION)
        assert observed is not None and observed.name == "Jaw restraint"
        assert observed.semantic_key == "condition.environment.jaw_restrained"
        assert str(jaw.uuid) not in observed.model_dump_json()


def test_empty_activation_closes_without_harming_later_entry(arena):
    target = actor(arena, (1, 3))
    jaw = materialize_jaw_trap((2, 3))
    assert pulse(jaw).committed and jaw.trap_state is TrapState.ACTIVATED
    Entity.update_entity_position(target, (2, 3))
    assert target.get_hp() == 80 and not jaw.linked_conditions


@pytest.mark.parametrize("action_type", (ForceJawOpen, SlipFreeOfJaw))
def test_escape_uses_one_action_actual_check_and_leaves_jaw_closed(arena, action_type):
    target = actor(arena)
    jaw = materialize_jaw_trap(target.position)
    pulse(jaw, 1, 3)
    source = jaw_source(target)
    template = next(action for action in target.registered_actions if isinstance(action, action_type))
    with fixed_dice_faces(1):
        failed = template.instantiate().apply()
    assert failed is not None and not failed.canceled
    assert source.uuid in target.active_conditions_by_uuid
    assert target.action_economy.actions.normalized_score == 0
    target.action_economy.reset_all_costs()
    with fixed_dice_faces(20):
        escaped = template.instantiate().apply()
    assert escaped is not None and not escaped.canceled
    assert source.uuid not in target.active_conditions_by_uuid and "Restrained" not in target.active_conditions
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 30
    assert jaw.trap_state is TrapState.ACTIVATED and not jaw.linked_conditions
    assert not any(isinstance(action, (ForceJawOpen, SlipFreeOfJaw)) for action in target.registered_actions)


@pytest.mark.parametrize("state", (TrapState.READY, TrapState.DEACTIVATED))
def test_reset_or_disable_releases_exact_capture(arena, state):
    target = actor(arena)
    jaw = materialize_jaw_trap(target.position)
    pulse(jaw, 1, 3)
    cause = control(jaw)
    assert jaw.set_trap_state(state, parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    assert not jaw.linked_conditions and "Restrained" not in target.active_conditions
    Entity.update_entity_position(target, (1, 3))
    with fixed_dice_faces(*((1, 4) if state is TrapState.READY else ())):
        Entity.update_entity_position(target, (2, 3))
    assert target.get_hp() == (73 if state is TrapState.READY else 77)
    assert ("Restrained" in target.active_conditions) is (state is TrapState.READY)


@pytest.mark.parametrize("removal", ("leave", "owner"))
def test_capture_follows_real_departure_and_owner_lifecycle(arena, removal):
    target = actor(arena)
    jaw = materialize_jaw_trap(target.position)
    pulse(jaw, 1, 3)
    if removal == "leave":
        Entity.update_entity_position(target, (3, 3))
        assert jaw.applied
    else:
        assert jaw.deactivate() is not None
        assert get_map().get_spatial_condition(jaw.uuid) is None
    assert "Restrained" not in target.active_conditions and not jaw.linked_conditions
    assert not any(isinstance(action, (ForceJawOpen, SlipFreeOfJaw)) for action in target.registered_actions)


@pytest.mark.parametrize("mode,trap_position,captured", (("walk", (1, 3), True),
    ("jump", (1, 3), False), ("jump", (3, 3), True)))
def test_real_movement_only_ground_contact_closes_jaw(arena, mode, trap_position, captured):
    target = actor(arena, (0, 3))
    jaw = materialize_jaw_trap(trap_position)
    Entity.update_all_entities_senses()
    action = (Jump(source_entity_uuid=target.uuid, end_position=(3, 3)) if mode == "jump" else
        Move(source_entity_uuid=target.uuid, end_position=(3, 3), path=[(0, 3), (1, 3), (2, 3), (3, 3)], prefer_safe=False))
    with fixed_dice_faces(*((1, 4) if captured else ())):
        result = action.apply()
    assert result is not None and not result.canceled
    assert target.occupancy_layer is OccupancyLayer.GROUND
    assert target.get_hp() == (76 if captured else 80)
    assert ("Restrained" in target.active_conditions) is captured
    assert jaw.trap_state is (TrapState.ACTIVATED if captured else TrapState.READY)
    assert target.position == (trap_position if captured else (3, 3))


def web_source(target: Entity) -> WebRestrained:
    source = WebRestrained(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        source_spatial_condition_uuid=uuid4(), check_dc=12, tags={ConditionTag.MAGICAL})
    result = target.add_condition(source)
    assert result is not None and not result.canceled
    return source


@pytest.mark.parametrize("first", ("web", "jaw"))
@pytest.mark.parametrize("remove_first", ("web", "jaw"))
def test_web_and_jaw_independent_sources_in_both_orders(arena, first, remove_first):
    target = actor(arena)
    jaw = materialize_jaw_trap(target.position)
    if first == "web":
        web = web_source(target)
        pulse(jaw, 1, 1, 3)  # Existing Restrained gives disadvantage to this DEX save.
    else:
        pulse(jaw, 1, 3)
        web = web_source(target)
    source = jaw_source(target)
    manifestation = target.active_conditions["Restrained"]
    assert manifestation.tags == set()
    first_source, remaining = (web, source) if remove_first == "web" else (source, web)
    assert target.remove_condition_by_uuid(first_source.uuid)
    assert remaining.uuid in target.active_conditions_by_uuid and "Restrained" in target.active_conditions
    assert target.action_economy.movement.normalized_score == 0
    assert target.remove_condition_by_uuid(remaining.uuid)
    assert "Restrained" not in target.active_conditions and target.action_economy.movement.normalized_score == 30
    assert not jaw.linked_conditions


@pytest.mark.parametrize("magical", (False, True))
def test_two_leases_do_not_claim_or_remove_a_preexisting_standalone_restraint(arena, magical):
    target = actor(arena)
    standalone = Restrained(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL} if magical else set())
    target.add_condition(standalone)
    web = web_source(target)
    jaw = materialize_jaw_trap(target.position)
    pulse(jaw, 1, 1, 3)
    source = jaw_source(target)
    assert target.remove_condition_by_uuid(web.uuid)
    assert target.remove_condition_by_uuid(source.uuid)
    assert target.active_conditions["Restrained"].uuid == standalone.uuid
    assert not any(isinstance(condition, (JawRestrained, WebRestrained)) for condition in target.active_conditions_by_uuid.values())
    assert standalone.tags == ({ConditionTag.MAGICAL} if magical else set())
    assert target.action_economy.movement.normalized_score == 0


def test_freedom_of_movement_escapes_only_the_mundane_lease_for_five_feet(arena):
    target = actor(arena)
    jaw = materialize_jaw_trap(target.position)
    pulse(jaw, 1, 3)
    web = web_source(target)
    cast = FreedomOfMovement(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid).apply()
    assert cast is not None and not cast.canceled
    template = next(action for action in target.registered_actions if isinstance(action, FreedomOfMovementEscape))
    result = template.instantiate().apply()
    assert result is not None and not result.canceled
    assert web.uuid in target.active_conditions_by_uuid and "Restrained" in target.active_conditions
    assert not jaw.linked_conditions
    assert target.remove_condition_by_uuid(web.uuid)
    assert "Restrained" not in target.active_conditions
    assert target.action_economy.movement.normalized_score == 25


def test_antimagic_suppresses_web_but_preserves_jaw_mechanics(arena):
    target = actor(arena)
    jaw = materialize_jaw_trap(target.position)
    pulse(jaw, 1, 3)
    web = web_source(target)
    field = AntimagicFieldZone(source_entity_uuid=target.uuid, position=target.position,
        anchor_uuid=target.uuid, affected_positions={target.position})
    result = field.activate(parent_event=control(jaw))
    assert result is not None and not result.canceled
    assert web.uuid not in target.active_conditions_by_uuid
    assert jaw_source(target).applied and "Restrained" in target.active_conditions
    assert target.action_economy.movement.normalized_score == 0
    assert any(isinstance(action, ForceJawOpen) for action in target.registered_actions)
    assert not any(isinstance(action, EscapeWebAction) for action in target.registered_actions)
    field.deactivate()
    assert web.uuid in target.active_conditions_by_uuid
    assert jaw_source(target).applied and "Restrained" in target.active_conditions


def test_actual_lever_reset_releases_capture_then_disable_and_arm(arena):
    captive = actor(arena, (2, 3))
    operator = actor(arena, (1, 2))
    jaw = materialize_jaw_trap(captive.position)
    lever = build_trap_lever(jaw.uuid, allow_activation=True, charges=-1)
    lever.place_on_grid((2, 2))
    pulse(jaw, 1, 4)
    Entity.update_all_entities_senses()
    for action, expected in (("Reset Trap", TrapState.READY), ("Deactivate Trap", TrapState.DEACTIVATED),
                             ("Arm Trap", TrapState.READY)):
        assert action in {template.name for template in lever.get_use_actions(operator.uuid)}
        previous_handle = lever.is_engaged
        result = execute_use_action(operator, lever.uuid, action)
        assert isinstance(result, ActionEvent) and not result.canceled
        assert result.behavior_id == "action.environment.trap_lever.pull"
        assert jaw.trap_state is expected
        assert lever.is_engaged is not previous_handle, "Every successful physical pull moves the handle"
        assert "Restrained" not in captive.active_conditions and not jaw.linked_conditions
    Entity.update_entity_position(captive, (3, 3))
    with fixed_dice_faces(1, 4):
        Entity.update_entity_position(captive, (2, 3))
    assert "Restrained" in captive.active_conditions and captive.get_hp() == 72
    result = execute_use_action(operator, lever.uuid, "Reset Trap")
    assert result is not None and not result.canceled
    assert jaw.trap_state is TrapState.READY and not lever.is_engaged
    assert "Restrained" not in captive.active_conditions


@pytest.mark.parametrize("kind", ("finite", "gas"))
def test_actual_lever_supports_arm_and_reset_for_pulse_mechanisms(arena, kind):
    operator = actor(arena, (6, 3))
    mechanism = (materialize_finite_trap((0, 3), geometry=LaneGeometry(range_feet=5), rearm_after_activation=False)
                 if kind == "finite" else materialize_gas_vent((0, 3), rearm_after_activation=False))
    lever = build_trap_lever(mechanism.uuid, allow_activation=True, charges=-1)
    lever.place_on_grid((5, 3))
    Entity.update_all_entities_senses()
    assert pulse(mechanism).committed and mechanism.trap_state is TrapState.ACTIVATED
    for action, expected in (("Reset Trap", TrapState.READY), ("Deactivate Trap", TrapState.DEACTIVATED),
                             ("Arm Trap", TrapState.READY)):
        previous_handle = lever.is_engaged
        result = execute_use_action(operator, lever.uuid, action)
        assert result is not None and not result.canceled
        assert mechanism.trap_state is expected
        assert lever.is_engaged is not previous_handle, "Resetting a triggered mechanism is also a physical pull"
    assert pulse(mechanism).committed
    result = execute_use_action(operator, lever.uuid, "Reset Trap")
    assert result is not None and not result.canceled
    assert mechanism.trap_state is TrapState.READY and not lever.is_engaged


def test_removal_veto_keeps_capture_closed_and_escape_does_not_claim_success(arena):
    target = actor(arena)
    jaw = materialize_jaw_trap(target.position)
    pulse(jaw, 1, 3)
    source = jaw_source(target)

    def veto(event: Event, _source: UUID) -> Event | None:
        if isinstance(event, ConditionRemovalEvent) and event.condition.uuid == source.uuid:
            return event.cancel("Jaw removal veto")
        return None

    target.add_event_handler(EventHandler(name="Keep capture", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.DECLARATION)],
        event_processor=veto))
    cause = control(jaw)
    assert not jaw.set_trap_state(TrapState.READY, parent_event=cause)
    assert not jaw.set_trap_state(TrapState.DEACTIVATED, parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    operator = actor(arena, (1, 2))
    lever = build_trap_lever(jaw.uuid, allow_activation=True, charges=3)
    lever.place_on_grid((2, 2))
    Entity.update_all_entities_senses()
    refused = execute_use_action(operator, lever.uuid, "Reset Trap")
    assert refused is not None and refused.canceled
    assert not lever.is_engaged
    template = next(action for action in target.registered_actions if isinstance(action, ForceJawOpen))
    with fixed_dice_faces(20):
        result = template.instantiate().apply()
    assert result is not None and "fails to escape" in (result.status_message or "")
    assert jaw.trap_state is TrapState.ACTIVATED and source.uuid in target.active_conditions_by_uuid
    assert target.action_economy.movement.normalized_score == 0


@pytest.mark.parametrize("first", ("standalone", "jaw"))
def test_antimagic_of_independent_restraint_preserves_mundane_capture_in_both_orders(arena, first):
    target = actor(arena)
    standalone = Restrained(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        tags={ConditionTag.MAGICAL})
    jaw = materialize_jaw_trap(target.position)
    if first == "standalone":
        target.add_condition(standalone)
        pulse(jaw, 1, 1, 3)
    else:
        pulse(jaw, 1, 3)
        target.add_condition(standalone)
    field = AntimagicFieldZone(source_entity_uuid=target.uuid, position=target.position,
        anchor_uuid=target.uuid, affected_positions={target.position})
    cause = control(jaw)
    result = field.activate(parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    assert result is not None and not result.canceled
    assert standalone.uuid not in target.active_conditions_by_uuid
    assert jaw_source(target).applied and target.action_economy.movement.normalized_score == 0
    assert target.active_conditions["Restrained"].tags == set()
    field.deactivate()
    assert standalone.uuid in target.active_conditions_by_uuid and standalone.tags == {ConditionTag.MAGICAL}
    assert jaw_source(target).applied and target.action_economy.movement.normalized_score == 0
    cause = control(jaw)
    assert jaw.set_trap_state(TrapState.DEACTIVATED, parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    assert target.active_conditions["Restrained"].uuid == standalone.uuid
    assert target.remove_condition_by_uuid(standalone.uuid)
    assert "Restrained" not in target.active_conditions and target.action_economy.movement.normalized_score == 30
