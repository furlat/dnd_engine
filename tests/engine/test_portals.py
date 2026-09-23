"""Native commands cross one-way portals without stale movement or hidden costs."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Jump, JumpEvent, Move, MovementEvent, Shove
from dnd.actions_functional import execute_use_action, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.environment_item_builders import build_trap_lever
from dnd.conditions import Paralyzed
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    EventPhase, EventQueue, ForcedMovementEvent, PortalTransferEvent, SensoryUpdateEvent,
    SpatialEffectChangeEvent, StepMovementEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.residues import DREAD_RESIDUE, deposit_residue
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.environmental_conditions import materialize_spike_trap_condition
from dnd.spatial.portals import PORTAL_CONTENT_REF, PORTAL_HATCH_CONTENT_REF, materialize_portal
from dnd.spells.evocation import GustOfWind, Thunderwave
from dnd.types.traps import TrapState
from dnd.types.world import OccupancyLayer


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 4))
    instance = Game()
    yield instance
    instance.close()
    reset_engine_runtime()


def actor(game: Game, position: tuple[int, int], *, caster: bool = False) -> Entity:
    creature = Entity.create(uuid4(), "Traveler", config=EntityConfig(position=position, faction="heroes",
        ability_scores=AbilityScoresConfig(strength=AbilityConfig(ability_score=18)),
        action_economy=ActionEconomyConfig(spell_slots={1: 1, 2: 1} if caster else {}),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
    ))
    setup_standard_actions(creature)
    if caster:
        register_spell(creature, Thunderwave, caster_level=3)
        register_spell(creature, GustOfWind, caster_level=3)
    creature.compose_entity()
    game.deploy_entity(creature, position)
    return creature


def completed(cursor: int, model):
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, model) and event.phase is EventPhase.COMPLETION]


@pytest.mark.parametrize("command", ("walk", "jump"))
def test_opening_is_observed_before_transfer_and_both_remain_in_complete_lineage(game, command):
    traveler = actor(game, (0, 1))
    departure = actor(game, (2, 1))
    arrival = actor(game, (7, 3))
    for y in range(4):
        get_map().set_tile(4, y, name="Wall", walking_cost=0, blocks_optics=True)
    portal = materialize_portal({(1, 1)}, (7, 2), trap_state=TrapState.READY,
        content_ref=PORTAL_HATCH_CONTENT_REF, stealth_dc=40)
    Entity.update_all_entities_senses()
    assert all(portal.uuid not in observer.senses.spatial_effects
               for observer in (traveler, departure, arrival))
    cursor = EventQueue.event_cursor()
    action = (Jump(source_entity_uuid=traveler.uuid, end_position=(1, 1)) if command == "jump" else
              Move(source_entity_uuid=traveler.uuid, end_position=(1, 1),
                   path=[(0, 1), (1, 1)], prefer_safe=False))
    result = action.apply()
    assert result is not None and not result.canceled and traveler.position == (7, 2)
    records = tuple(EventQueue.iter_events_since(cursor))
    transfer_index, transfer = next((index, event) for index, event in records
        if isinstance(event, PortalTransferEvent) and event.phase is EventPhase.DECLARATION)
    opening_index, opening = next((index, event) for index, event in records
        if isinstance(event, SpatialEffectChangeEvent) and event.phase is EventPhase.COMPLETION
        and event.spatial_effect_uuid == portal.uuid and event.trap_state is TrapState.ACTIVATED)
    assert opening_index < transfer_index
    assert opening.parent_event == transfer.parent_event
    for observer in (traveler, departure):
        updates = [(index, event) for index, event in records if isinstance(event, SensoryUpdateEvent)
                   and event.observer_uuid == observer.uuid and portal.uuid in event.spatial_effects_changed]
        assert updates and updates[0][0] < transfer_index
        assert updates[0][1].spatial_effects_changed[portal.uuid].trap_state is TrapState.ACTIVATED
    assert not any(isinstance(event, SensoryUpdateEvent) and event.observer_uuid == arrival.uuid
                   and portal.uuid in event.spatial_effects_changed for _, event in records)
    pending, descendants = [result], set()
    while pending:
        event = pending.pop()
        assert event.phase is EventPhase.COMPLETION
        descendants.add(event.lineage_uuid)
        children = event.get_children_events()
        assert set(event.children_lineages) == {child.lineage_uuid for child in children}
        pending.extend(children)
    assert {opening.lineage_uuid, transfer.lineage_uuid} <= descendants


@pytest.mark.parametrize("content_ref", (PORTAL_CONTENT_REF, PORTAL_HATCH_CONTENT_REF))
@pytest.mark.parametrize("mode", tuple(TrapState))
@pytest.mark.parametrize("command,entrance,contact", (
    ("walk", (1, 1), True), ("jump", (1, 1), False), ("jump", (3, 1), True),
))
def test_real_movement_ground_contact_and_state(game, content_ref, mode, command, entrance, contact):
    traveler = actor(game, (0, 1))
    portal = materialize_portal({entrance}, (7, 2), trap_state=mode, content_ref=content_ref)
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    if command == "jump":
        result = Jump(source_entity_uuid=traveler.uuid, end_position=(3, 1)).apply()
    else:
        result = Move(source_entity_uuid=traveler.uuid, end_position=(3, 1),
            path=[(0, 1), (1, 1), (2, 1), (3, 1)], prefer_safe=False).apply()
    assert isinstance(result, (MovementEvent, JumpEvent)) and not result.canceled
    transferred = contact and mode is not TrapState.DEACTIVATED
    assert traveler.position == result.end_position == ((7, 2) if transferred else (3, 1))
    assert traveler.occupancy_layer is OccupancyLayer.GROUND
    cost = 5 if transferred and command == "walk" else 15
    assert traveler.action_economy.movement.normalized_score == 30 - cost
    assert result.path == ([(0, 1), (1, 1)] if cost == 5 else [(0, 1), (1, 1), (2, 1), (3, 1)])
    transfers = completed(cursor, PortalTransferEvent)
    assert len(transfers) == int(transferred)
    if transferred:
        transfer, = transfers
        assert transfer.committed and transfer.portal_uuid == portal.uuid
        assert transfer.portal_content_ref == content_ref
        assert (transfer.start_position, transfer.end_position) == (entrance, (7, 2))
        assert portal.trap_state is TrapState.ACTIVATED
        parent = transfer
        while parent.parent_event is not None:
            parent = EventQueue.get_event_by_uuid(parent.parent_event)
            assert parent is not None
        assert parent.lineage_uuid == result.lineage_uuid


@pytest.mark.parametrize("blocker", ("creature", "wall", "missing"))
def test_blocked_exit_leaves_actor_at_entrance(game, blocker):
    traveler = actor(game, (0, 1))
    destination = (99, 99) if blocker == "missing" else (7, 2)
    if blocker == "creature":
        actor(game, destination)
    elif blocker == "wall":
        get_map().set_tile(*destination, name="Wall", walking_cost=0, blocks_optics=True)
    materialize_portal({(1, 1)}, destination)
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    result = Move(source_entity_uuid=traveler.uuid, end_position=(1, 1),
                  path=[(0, 1), (1, 1)], prefer_safe=False).apply()
    assert result is not None and not result.canceled
    assert traveler.position == result.end_position == (1, 1)
    assert not any(event.committed for _, event in EventQueue.iter_events_since(cursor)
                   if isinstance(event, PortalTransferEvent))
    assert traveler.action_economy.movement.normalized_score == 25


def test_exit_need_not_be_visible_and_keeps_its_own_height(game):
    traveler = actor(game, (0, 1))
    for y in range(4):
        get_map().set_tile(4, y, name="Wall", walking_cost=0, blocks_optics=True)
    get_map().set_tile_elevation((7, 2), height=3, surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    materialize_portal({(1, 1)}, (7, 2))
    Entity.update_all_entities_senses()
    assert (7, 2) not in traveler.senses.visible
    result = Move(source_entity_uuid=traveler.uuid, end_position=(1, 1),
                  path=[(0, 1), (1, 1)], prefer_safe=False).apply()
    assert result is not None and not result.canceled
    assert result.end_position == traveler.position == (7, 2)
    assert get_map().get_support_elevation_feet(traveler.position) == 15


def test_exit_hazard_and_paid_retreat_are_children_not_extra_transfer_distance(game):
    traveler = actor(game, (0, 1))
    tile = get_map().get_tile(7, 2)
    assert tile is not None
    deposit_residue(tile, DREAD_RESIDUE)
    materialize_portal({(1, 1)}, (7, 2))
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        result = Move(source_entity_uuid=traveler.uuid, end_position=(3, 1),
            path=[(0, 1), (1, 1), (2, 1), (3, 1)], prefer_safe=False).apply()
    assert result is not None and not result.canceled
    transfer, = completed(cursor, PortalTransferEvent)
    assert transfer.end_position == (7, 2)
    assert traveler.position == result.end_position == (6, 2)
    assert traveler.action_economy.movement.normalized_score == 20
    assert "Frightened" not in traveler.active_conditions
    steps = completed(cursor, StepMovementEvent)
    assert {(step.from_position, step.to_position) for step in steps} == {
        ((0, 1), (1, 1)), ((7, 2), (6, 2))}
    retreat, = (event for event in completed(cursor, MovementEvent)
                if event.parent_lineage == transfer.lineage_uuid)
    assert retreat.lineage_uuid in transfer.children_lineages


def test_portal_arrival_activates_spikes(game):
    traveler = actor(game, (0, 1))
    materialize_spike_trap_condition({(7, 2)})
    materialize_portal({(1, 1)}, (7, 2))
    Entity.update_all_entities_senses()
    hp = traveler.get_hp()
    with fixed_dice_faces(2, 2):
        result = Move(source_entity_uuid=traveler.uuid, end_position=(1, 1),
            path=[(0, 1), (1, 1)], prefer_safe=False).apply()
    assert result is not None and not result.canceled and traveler.position == (7, 2)
    assert traveler.get_hp() < hp


def test_shove_stops_its_old_route_after_entry(game):
    shover = actor(game, (0, 1))
    traveler = actor(game, (1, 1))
    materialize_portal({(2, 1)}, (7, 2))
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(1):
        result = Shove(source_entity_uuid=shover.uuid, target_entity_uuid=traveler.uuid).apply()
    assert result is not None and not result.canceled
    assert traveler.position == result.end_position == (7, 2)
    assert result.push_distance == 5
    assert traveler.action_economy.movement.normalized_score == 30
    assert len(completed(cursor, PortalTransferEvent)) == 1
    push, = completed(cursor, ForcedMovementEvent)
    assert push.end_position == (2, 1), "The pushed leg ends at the entrance, not the portal exit"


@pytest.mark.parametrize("spell", (Thunderwave, GustOfWind))
def test_spell_push_contacts_intermediate_portal_and_stops(game, spell):
    caster = actor(game, (0, 1), caster=True)
    traveler = actor(game, (1, 1))
    materialize_portal({(2, 1)}, (7, 2))
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    faces = (1, 2, 2) if spell is Thunderwave else (1,)
    with fixed_dice_faces(*faces):
        result = spell(source_entity_uuid=caster.uuid, end_position=(3, 1),
            cast_at_level=1 if spell is Thunderwave else 2).apply()
    assert result is not None and not result.canceled
    assert traveler.position == (7, 2)
    push, = completed(cursor, ForcedMovementEvent)
    assert push.end_position == (2, 1) and push.actual_distance == 5
    assert len(completed(cursor, PortalTransferEvent)) == 1
    assert traveler.action_economy.movement.normalized_score == 30


@pytest.mark.parametrize("spell,distance", ((Thunderwave, 10), (GustOfWind, 15)))
def test_spell_push_does_not_require_the_targets_ability_to_act(game, spell, distance):
    caster = actor(game, (0, 1), caster=True)
    traveler = actor(game, (1, 1))
    traveler.add_condition(Paralyzed(source_entity_uuid=caster.uuid, target_entity_uuid=traveler.uuid))
    Entity.update_all_entities_senses()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*((1, 2, 2) if spell is Thunderwave else (1,))):
        result = spell(source_entity_uuid=caster.uuid, end_position=(3, 1),
            cast_at_level=1 if spell is Thunderwave else 2).apply()
    assert result is not None and not result.canceled
    assert traveler.position == (1 + distance // 5, 1)
    push, = completed(cursor, ForcedMovementEvent)
    assert push.actual_distance == distance


def test_attached_light_follows_actual_portal_destination(game):
    traveler = actor(game, (0, 1))
    grid = get_map()
    light = grid.add_light_source(traveler.position, bright_radius_feet=5,
                                  dim_radius_feet=5, anchor_uuid=traveler.uuid)
    materialize_portal({(1, 1)}, (7, 2))
    Entity.update_all_entities_senses()
    result = Move(source_entity_uuid=traveler.uuid, end_position=(1, 1),
        path=[(0, 1), (1, 1)], prefer_safe=False).apply()
    assert result is not None and not result.canceled
    assert grid.get_light_source_position(light) == traveler.position == (7, 2)


def test_lever_opens_under_occupant_and_closing_does_not_recall_them(game):
    traveler = actor(game, (1, 1))
    operator = actor(game, (0, 2))
    portal = materialize_portal({(1, 1)}, (7, 2), trap_state=TrapState.DEACTIVATED,
                               content_ref=PORTAL_HATCH_CONTENT_REF)
    lever = build_trap_lever(trap_condition_uuid=portal.uuid, allow_activation=True, charges=3)
    lever.place_on_grid((1, 2))
    Entity.update_all_entities_senses()
    # Existing lever begins disengaged; its first command disables, the next opens.
    for action in ("Deactivate Trap", "Activate Trap", "Deactivate Trap"):
        result = execute_use_action(operator, lever.uuid, action)
        assert result is not None and not result.canceled
    assert traveler.position == (7, 2) and portal.trap_state is TrapState.DEACTIVATED
    assert traveler.action_economy.movement.normalized_score == 30
