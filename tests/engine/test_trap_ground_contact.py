"""Floor spikes require contact, not merely horizontal cell occupancy.

Native actions preserve airborne crossings, real takeoff/landing facts, and
ground-contact damage. Saves and opportunity attacks exercise actual movement
interruptions without replacing the engine's handlers.
"""

from collections.abc import Iterator
from typing import Literal
from uuid import uuid4

import pytest

from dnd.actions import AttackEvent, Jump, JumpEvent, Move
from dnd.actions_functional import register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageAppliedEvent, Event, EventPhase, EventQueue, EventType, SpatialChangeEvent, SpatialChangeType
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import GhoulClawsParalysisFeature
from dnd.reactions import add_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.spells.conjuration import MistyStep, WebZone
from dnd.types.traps import TrapState
from dnd.types.world import MovementMode, OccupancyLayer


@pytest.fixture
def traveler() -> Iterator[Entity]:
    reset_engine_runtime(grid_size=(5, 3))
    game = Game()
    creature = Entity.create(uuid4(), "Ground contact traveler", config=EntityConfig(
        position=(0, 1),
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
        action_economy=ActionEconomyConfig(spell_slots={2: 1}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        health=HealthConfig(hit_dices=[
            HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums"),
        ]),
    ))
    setup_standard_actions(creature)
    register_spell(creature, MistyStep, caster_level=3)
    creature.compose_entity()
    game.deploy_entity(creature, (0, 1))
    try:
        yield creature
    finally:
        game.close()
        reset_engine_runtime()


@pytest.mark.parametrize("initial_state", (
    TrapState.READY, TrapState.ACTIVATED, TrapState.DEACTIVATED,
))
@pytest.mark.parametrize("movement,trap_position,ground_contact", (
    pytest.param("walk", (1, 1), True, id="walk-onto-spikes"),
    pytest.param("jump", (1, 1), False, id="jump-over-spikes"),
    pytest.param("jump", (3, 1), True, id="jump-lands-on-spikes"),
    pytest.param("misty_step", (1, 1), False, id="misty-step-crosses-no-intermediate-tiles"),
    pytest.param("misty_step", (3, 1), True, id="misty-step-arrives-on-spikes"),
))
def test_floor_spikes_require_ground_contact(
    traveler: Entity,
    initial_state: TrapState,
    movement: Literal["walk", "jump", "misty_step"],
    trap_position: tuple[int, int],
    ground_contact: bool,
) -> None:
    trap = materialize_spike_trap_condition({trap_position}, trap_state=initial_state)
    traveler.update_entity_senses()
    cursor = EventQueue.event_cursor()
    hp_before = traveler.get_hp()
    endpoint = (3, 1)

    with fixed_dice_faces(1, 1):
        if movement == "jump":
            result = Jump(source_entity_uuid=traveler.uuid, end_position=endpoint).apply()
        elif movement == "misty_step":
            result = MistyStep(source_entity_uuid=traveler.uuid, end_position=endpoint).apply()
        else:
            result = Move(
                source_entity_uuid=traveler.uuid,
                end_position=endpoint,
                path=[(0, 1), (1, 1), (2, 1), endpoint],
                prefer_safe=False,
                movement_mode=MovementMode.WALKING,
            ).apply()

    assert result is not None and not result.canceled
    assert result.phase is EventPhase.COMPLETION
    assert traveler.position == endpoint
    assert traveler.occupancy_layer is OccupancyLayer.GROUND

    damage = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent)
        and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == traveler.uuid
    ]
    for event in damage:
        ancestor = event
        while ancestor.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(ancestor.parent_event)
            assert parent is not None
            ancestor = parent
        assert ancestor.lineage_uuid == result.lineage_uuid
    triggers = ground_contact and initial_state is not TrapState.DEACTIVATED
    expected_state = TrapState.ACTIVATED if triggers else initial_state
    assert {
        "trap_state": trap.trap_state,
        "hp_loss": hp_before - traveler.get_hp(),
        "damage_applications": len(damage),
    } == {
        "trap_state": expected_state,
        "hp_loss": 2 if triggers else 0,
        "damage_applications": 1 if triggers else 0,
    }


def _has_ancestor(event: Event, ancestor: Event) -> bool:
    while event.parent_event is not None:
        parent = EventQueue.get_event_by_uuid(event.parent_event)
        assert parent is not None
        if parent.lineage_uuid == ancestor.lineage_uuid:
            return True
        event = parent
    return False


def test_one_cell_jump_records_takeoff_before_ground_contact(traveler: Entity) -> None:
    trap = materialize_spike_trap_condition({(1, 1)})
    traveler.update_entity_senses()
    cursor = EventQueue.event_cursor()
    hp_before = traveler.get_hp()
    with fixed_dice_faces(1, 1):
        result = Jump(source_entity_uuid=traveler.uuid, end_position=(1, 1)).apply()

    assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
    assert traveler.position == (1, 1) and traveler.occupancy_layer is OccupancyLayer.GROUND
    events = [event for _, event in EventQueue.iter_events_since(cursor)
              if event.phase is EventPhase.COMPLETION]
    entries = [event for event in events if isinstance(event, SpatialChangeEvent)
               and event.entity_uuid == traveler.uuid
               and event.change_type is SpatialChangeType.ENTITY_ENTERED]
    assert any(event.occupancy_layer is OccupancyLayer.AIR for event in entries)
    landing = entries[-1]
    assert (landing.position, landing.occupancy_layer) == ((1, 1), OccupancyLayer.GROUND)
    assert all(_has_ancestor(event, result) for event in entries)
    damage = [event for event in events if isinstance(event, DamageAppliedEvent)]
    assert len(damage) == 1 and _has_ancestor(damage[0], landing)
    assert hp_before - traveler.get_hp() == 2 and trap.trap_state is TrapState.ACTIVATED


def test_interrupted_jump_lands_on_its_reached_cell_after_real_opportunity_attack(
    traveler: Entity,
) -> None:
    """A real paralysis rider stops the third step after two airborne commits."""
    reactor = Entity.create(uuid4(), "Paralyzing sword wielder", config=EntityConfig(
        position=(1, 0), faction="enemies",
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
    ))
    reactor.install_initial_items(((
        build_authored_item("weapon.longsword", reactor.uuid), WeaponSlot.MELEE_MAIN,
    ),))
    setup_standard_actions(reactor)
    reactor.add_condition(GhoulClawsParalysisFeature(
        source_entity_uuid=reactor.uuid, target_entity_uuid=reactor.uuid,
        weapon_names=("Longsword",),
    ))
    add_opportunity_attack_handler(reactor)
    reactor.compose_entity()
    opposing_game = Game()
    try:
        opposing_game.deploy_entity(reactor, (1, 0))
        trap = materialize_spike_trap_condition({(2, 1)})
        Entity.update_all_entities_senses()
        cursor = EventQueue.event_cursor()
        with fixed_dice_faces(18, 2, 1, 1, 1):
            result = Jump(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply()

        assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
        assert traveler.position == (2, 1) and traveler.occupancy_layer is OccupancyLayer.GROUND
        assert "Paralyzed" in traveler.active_conditions
        events = [event for _, event in EventQueue.iter_events_since(cursor)
                  if event.phase is EventPhase.COMPLETION]
        attack, = (event for event in events if isinstance(event, AttackEvent))
        assert attack.source_entity_uuid == reactor.uuid and _has_ancestor(attack, result)
        entries = [event for event in events if isinstance(event, SpatialChangeEvent)
                   and event.entity_uuid == traveler.uuid
                   and event.change_type is SpatialChangeType.ENTITY_ENTERED]
        assert any(event.position == (2, 1) and event.occupancy_layer is OccupancyLayer.AIR
                   for event in entries)
        landing = entries[-1]
        assert (landing.position, landing.previous_occupancy_layer, landing.occupancy_layer) == (
            (2, 1), OccupancyLayer.AIR, OccupancyLayer.GROUND,
        )
        landing_damage = [event for event in events if isinstance(event, DamageAppliedEvent)
                          and _has_ancestor(event, landing)]
        assert len(landing_damage) == 1 and landing_damage[0].applied_damage == 2
        assert trap.trap_state is TrapState.ACTIVATED
    finally:
        opposing_game.close()


def test_web_restraint_on_jump_takeoff_prevents_horizontal_movement(
    traveler: Entity,
) -> None:
    """An overhead web's real failed save stops movement without incapacitation."""
    web = WebZone(source_entity_uuid=traveler.uuid, position=traveler.position,
        affected_positions={traveler.position},
        affected_occupancy_layers=frozenset({OccupancyLayer.AIR}))
    web.activate(parent_event=Event(name="Overhead web fixture", source_entity_uuid=traveler.uuid,
        event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT))
    assert "Restrained" not in traveler.active_conditions
    with fixed_dice_faces(1):
        result = Jump(source_entity_uuid=traveler.uuid, end_position=(1, 1)).apply()

    assert isinstance(result, JumpEvent)
    assert traveler.can_take_actions()
    assert traveler.position == (0, 1)
    assert traveler.occupancy_layer is OccupancyLayer.GROUND
    assert result.end_layer is traveler.occupancy_layer


def test_jump_pays_landing_cost_once_before_web_restraint(traveler: Entity) -> None:
    """Landing spends its step even when the entry save then locks movement."""
    web = WebZone(source_entity_uuid=traveler.uuid, position=(1, 1),
        affected_positions={(1, 1)},
        affected_occupancy_layers=frozenset({OccupancyLayer.GROUND}))
    web.activate(parent_event=Event(name="Landing web fixture", source_entity_uuid=traveler.uuid,
        event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT))
    movement_before = traveler.action_economy.movement.normalized_score
    with fixed_dice_faces(1):
        result = Jump(source_entity_uuid=traveler.uuid, end_position=(1, 1)).apply()

    assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
    assert traveler.position == (1, 1) and traveler.occupancy_layer is OccupancyLayer.GROUND
    assert "Restrained" in traveler.active_conditions and traveler.can_take_actions()
    assert traveler.action_economy.movement.normalized_score == 0
    assert web.deactivate(parent_event=result)
    assert "Restrained" not in traveler.active_conditions
    assert traveler.action_economy.movement.normalized_score == movement_before - 5 == 25
