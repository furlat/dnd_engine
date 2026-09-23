"""Real attacks retire a ground fixture's mechanics while preserving its body."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from dnd.actions import AttackObject, Move
from dnd.actions_functional import get_available_actions, setup_standard_actions
from dnd.blocks.base_item import BaseItem
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_authored_door
from dnd.content.items.ground_hardware_builders import (
    GROUND_HARDWARE_PROFILES, materialize_ground_hardware,
)
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    Event, EventHandler, EventPhase, EventQueue, EventType, ItemDestructionEvent,
    MechanismActivationEvent, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spatial.environmental_conditions import (
    POISON_DAMAGE_SPIKE_CONTENT_REF, POISON_DAMAGE_SPIKE_PAYLOAD, SpikeTrap,
)
from dnd.spatial.gas_traps import GasCloud, GasCloudSpec, GasVent
from dnd.spatial.jaws import JawTrap
from dnd.spatial.mechanisms import AreaGeometry, FiniteTrap, materialize_finite_trap
from dnd.spatial.portals import PORTAL_HATCH_CONTENT_REF, Portal
from dnd.spatial.triggers import PressurePlate, Tripwire, materialize_pressure_plate
from dnd.types.controls import ActivationLink, ControlLink
from dnd.types.spatial_effects import SpatialEffectAnchorKind
from dnd.types.world import CardinalDirection


@pytest.fixture
def game() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 9))
    instance = Game()
    yield instance
    instance.close()
    reset_engine_runtime()


def actor(game: Game, position: tuple[int, int]) -> Entity:
    result = Entity.create(uuid4(), "Hardware tester", config=EntityConfig(
        position=position, faction="heroes", health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
    ))
    setup_standard_actions(result)
    result.install_initial_items(((build_authored_item("weapon.longsword", result.uuid),
                                   WeaponSlot.MELEE_MAIN),))
    result.compose_entity()
    game.deploy_entity(result, position)
    return result


def attack(attacker: Entity, item: BaseItem, damage: int = 8) -> Event:
    attacker.action_economy.reset_all_costs()
    with fixed_dice_faces(damage):
        event = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=item.uuid).apply()
    assert event is not None and not event.canceled
    return event


def move(walker: Entity, destination: tuple[int, int], *dice: int) -> Event:
    walker.action_economy.reset_all_costs()
    walker.update_entity_senses()
    with fixed_dice_faces(*dice):
        event = Move(source_entity_uuid=walker.uuid, path=[walker.position, destination],
                     end_position=destination, prefer_safe=False).apply()
    assert event is not None and not event.canceled
    return event


def owner(kind: str, position: tuple[int, int], peer_uuid: UUID) -> SpatialCondition:
    source = uuid4()
    common = dict(source_entity_uuid=source, position=position, affected_positions={position})
    if kind == "spikes":
        return SpikeTrap(**common)
    if kind == "dart_emitter":
        return FiniteTrap(**common, geometry=AreaGeometry())
    if kind == "jaw":
        return JawTrap(**common)
    if kind == "gas_vent":
        return GasVent(**common)
    if kind == "pressure_plate":
        return PressurePlate(**common, link=ActivationLink(target_condition_uuid=peer_uuid))
    if kind == "tripwire":
        return Tripwire(source_entity_uuid=source, position=position,
            affected_positions={position, (position[0] + 1, position[1])},
            across=(position[0] + 1, position[1]), link=ActivationLink(target_condition_uuid=peer_uuid))
    if kind == "portal_hatch":
        return Portal(**common, exit_position=(7, 7), content_ref=PORTAL_HATCH_CONTENT_REF)
    raise ValueError(kind)


@pytest.mark.parametrize("item_id", tuple(GROUND_HARDWARE_PROFILES))
def test_every_ground_profile_takes_real_damage_and_stops_its_attached_owner(game: Game, item_id: str):
    attacker = actor(game, (2, 3))
    walker = actor(game, (3, 2))
    peer = materialize_finite_trap((6, 6), geometry=AreaGeometry())
    mechanism = owner(item_id.rsplit(".", 1)[1], (3, 3), peer.uuid)
    item = materialize_ground_hardware(mechanism, item_id=item_id, hit_points=8)
    registered = build_authored_item(item_id, attacker.uuid)
    assert registered.get_hp() == GROUND_HARDWARE_PROFILES[item_id].hit_points
    assert mechanism.anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT
    assert mechanism.anchor_uuid == item.uuid
    assert any(target.target_uuid == item.uuid for action in get_available_actions(attacker).all_actions
               for target in action.valid_targets)
    attack(attacker, item, 4)
    assert item.get_hp() == 4 and mechanism.is_active_spatial_condition()
    cursor = EventQueue.event_cursor()
    attack(attacker, item, 4)
    assert BaseBlock.get(item.uuid) is item
    assert item.integrity is ItemIntegrity.DESTROYED and item.get_hp() == 0
    assert get_map().get_object_position(item.uuid) == (3, 3)
    assert not mechanism.is_active_spatial_condition() and peer.is_active_spatial_condition()
    assert not any(target.target_uuid == item.uuid for action in get_available_actions(attacker).all_actions
                   for target in action.valid_targets)
    breaks = [event for _, event in EventQueue.iter_events_since(cursor)
              if isinstance(event, ItemDestructionEvent) and event.phase is EventPhase.COMPLETION]
    assert len(breaks) == 1 and breaks[0].item_uuid == item.uuid
    before_hp = walker.get_hp()
    move(walker, (3, 3))
    move(walker, (4, 3))
    assert walker.position == (4, 3) and walker.get_hp() == before_hp
    assert "Restrained" not in walker.active_conditions
    assert not any(isinstance(event, MechanismActivationEvent) and event.committed
                   for _, event in EventQueue.iter_events_since(cursor))
    item.retire()
    assert BaseBlock.get(item.uuid) is None and get_map().get_object_position(item.uuid) is None


def test_breaking_capturing_jaw_releases_its_victim_and_future_crossing_is_safe(game: Game):
    attacker = actor(game, (2, 3))
    victim = actor(game, (3, 2))
    jaw = JawTrap(source_entity_uuid=uuid4(), position=(3, 3), affected_positions={(3, 3)})
    body = materialize_ground_hardware(jaw, item_id="environment.trap.jaw", hit_points=8)
    move(victim, (3, 3), 1, 3)
    assert "Restrained" in victim.active_conditions and victim.get_hp() < 80
    hp = victim.get_hp()
    attack(attacker, body)
    assert not jaw.linked_conditions and "Restrained" not in victim.active_conditions
    move(victim, (3, 2))
    move(victim, (3, 3))
    assert victim.get_hp() == hp


def test_destroyed_held_plate_releases_its_door_and_preserves_an_independent_plate(game: Game):
    attacker = actor(game, (2, 3))
    walker = actor(game, (3, 2))
    peer_walker = actor(game, (5, 4))
    door = build_authored_door("environment.door.fantasy_a1")
    door.place_on_grid((6, 2), boundary_direction=CardinalDirection.EAST)
    peer_door = build_authored_door("environment.door.fantasy_a1")
    peer_door.place_on_grid((6, 5), boundary_direction=CardinalDirection.EAST)
    plate = PressurePlate(source_entity_uuid=uuid4(), position=(3, 3), affected_positions={(3, 3)},
        link=ControlLink(target_kind="door", target_item_uuid=door.uuid, engaged_value=True))
    body = materialize_ground_hardware(plate, item_id="environment.trap.pressure_plate", hit_points=8)
    peer = materialize_pressure_plate({(5, 5)}, ControlLink(
        target_kind="door", target_item_uuid=peer_door.uuid, engaged_value=True))
    move(walker, (3, 3))
    move(peer_walker, (5, 5))
    assert door.is_open and peer_door.is_open and plate.pressed and peer.pressed
    attack(attacker, body)
    assert not door.is_open and peer_door.is_open and peer.is_active_spatial_condition()
    move(walker, (3, 2))
    move(walker, (3, 3))
    assert not door.is_open and peer_door.is_open


def test_destroyed_vent_cannot_fire_again_but_released_cloud_remains(game: Game):
    attacker = actor(game, (2, 3))
    walker = actor(game, (3, 1))
    vent = GasVent(source_entity_uuid=uuid4(), position=(3, 3), affected_positions={(3, 3)},
                   gas=GasCloudSpec(radius_feet=0))
    body = materialize_ground_hardware(vent, item_id="environment.trap.gas_vent", hit_points=8)
    plate = materialize_pressure_plate({(3, 2)}, ActivationLink(target_condition_uuid=vent.uuid))
    move(walker, (3, 2))
    clouds = [condition for condition in get_map().get_spatial_conditions() if isinstance(condition, GasCloud)]
    assert len(clouds) == 1
    cloud = clouds[0]
    attack(attacker, body)
    assert cloud.is_active_spatial_condition() and plate.is_active_spatial_condition()
    cursor = EventQueue.event_cursor()
    move(walker, (3, 1))
    move(walker, (3, 2))
    assert get_map().get_spatial_condition(cloud.uuid) is cloud
    assert not any(isinstance(event, MechanismActivationEvent) and event.committed
                   for _, event in EventQueue.iter_events_since(cursor))


def test_open_hatch_transports_before_breakage_and_stops_afterward(game: Game):
    attacker = actor(game, (2, 3))
    traveler = actor(game, (3, 2))
    hatch = Portal(source_entity_uuid=uuid4(), position=(3, 3), affected_positions={(3, 3)},
                   exit_position=(4, 3), content_ref=PORTAL_HATCH_CONTENT_REF)
    body = materialize_ground_hardware(hatch, item_id="environment.trap.portal_hatch", hit_points=8)
    move(traveler, (3, 3))
    assert traveler.position == (4, 3)
    attack(attacker, body)
    move(traveler, (3, 3))
    assert traveler.position == (3, 3) and not hatch.is_active_spatial_condition()


def test_spike_body_preserves_authored_poison_and_discovery(game: Game):
    attacker = actor(game, (2, 3))
    victim = actor(game, (3, 2))
    spikes = SpikeTrap(source_entity_uuid=uuid4(), position=(3, 3), affected_positions={(3, 3)},
        condition_stealth_dc=40, content_ref=POISON_DAMAGE_SPIKE_CONTENT_REF,
        payload=POISON_DAMAGE_SPIKE_PAYLOAD)
    body = materialize_ground_hardware(spikes, item_id="environment.trap.spikes", hit_points=8)
    Entity.update_all_entities_senses()
    assert body.uuid not in attacker.senses.objects and spikes.uuid not in attacker.senses.spatial_effects
    move(victim, (3, 3), 3, 2, 2)
    assert victim.get_hp() < 80 and spikes.content_ref == POISON_DAMAGE_SPIKE_CONTENT_REF
    assert body.uuid in attacker.senses.objects and spikes.uuid in attacker.senses.spatial_effects
    attack(attacker, body)
    Entity.update_all_entities_senses()
    assert body.uuid in attacker.senses.objects and spikes.uuid not in attacker.senses.spatial_effects


def test_canceled_mechanism_installation_disposes_body_without_destroying_it(game: Game):
    actor(game, (2, 3))
    mechanism = JawTrap(source_entity_uuid=uuid4(), position=(3, 3), affected_positions={(3, 3)})

    def reject(event: Event, _source: UUID) -> Event:
        return event.cancel(status_message="Installation rejected")

    EventQueue.add_event_handler(EventHandler(name="Reject installation", source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,
                                    event_phase=EventPhase.DECLARATION)], event_processor=reject))
    cursor = EventQueue.event_cursor()
    with pytest.raises(RuntimeError, match="installation failed"):
        materialize_ground_hardware(mechanism, item_id="environment.trap.jaw")
    assert get_map().get_objects_at((3, 3)) == set()
    assert not mechanism.is_active_spatial_condition()
    assert not any(isinstance(event, ItemDestructionEvent)
                   for _, event in EventQueue.iter_events_since(cursor))
