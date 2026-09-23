"""Real item attacks preserve boundary geometry and retire only owned mechanisms."""

from uuid import uuid4

import pytest

from dnd.actions import AttackObject, Move
from dnd.actions_functional import execute_use_action, get_available_actions, setup_standard_actions
from dnd.blocks.base_item import BaseItem, ItemLocationStateEvent
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.authored_item_definitions import CHEST_DEFINITIONS
from dnd.content.items.door_profiles import DOOR_PROFILES
from dnd.content.items.environment_item_builders import (
    build_authored_door, build_control_lever, build_directional_door, build_standing_torch,
    build_storage_chest, build_trap_lever, build_wall_torch,
)
from dnd.content.items.trap_hardware_builders import TRAP_HARDWARE_PROFILES, materialize_trap_hardware
from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import (
    Event, EventHandler, EventPhase, EventQueue, EventType, MechanismActivationEvent,
    SensoryUpdateEvent, SpatialChangeEvent, TakeDamageEvent, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.item_types import DoorMechanism, DoorSwing, ItemIntegrity, ItemLocation
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_interactables import DoorObject, StorageChest
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.mechanisms import AreaGeometry, TrapSave, materialize_finite_trap
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink, ControlLink
from dnd.types.materials import Material
from dnd.types.traps import TrapState
from dnd.types.world import CardinalDirection, WorldEdgeChannel


@pytest.fixture
def arena():
    reset_engine_runtime(grid_size=(9, 9))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(game, position, name="Attacker"):
    result = Entity.create(uuid4(), name, config=EntityConfig(position=position, faction="heroes",
        health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
    setup_standard_actions(result)
    result.install_initial_items(((build_authored_item("weapon.longsword", result.uuid), WeaponSlot.MELEE_MAIN),))
    result.compose_entity()
    game.deploy_entity(result, position)
    return result


def attack(attacker, item, amount):
    attacker.action_economy.reset_all_costs()
    with fixed_dice_faces(amount):
        result = AttackObject(source_entity_uuid=attacker.uuid, target_entity_uuid=item.uuid).apply()
    assert result is not None and not result.canceled
    return result


def move(entity, destination, *dice):
    entity.action_economy.reset_all_costs()
    entity.update_entity_senses()
    with fixed_dice_faces(*dice):
        result = Move(source_entity_uuid=entity.uuid, path=[entity.position, destination],
            end_position=destination, prefer_safe=False).apply()
    assert result is not None and not result.canceled, result.status_message if result else "No move"
    return result


def destroyed_since(cursor):
    return [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, ItemLocationStateEvent) and event.phase is EventPhase.COMPLETION
            and event.location is ItemLocation.FLOOR
            and event.item_state is not None and event.item_state.integrity is ItemIntegrity.DESTROYED]


@pytest.mark.parametrize("item_id", tuple(DOOR_PROFILES))
def test_registered_door_profiles_have_native_material_channels_and_independent_health(arena, item_id):
    first = build_authored_item(item_id, uuid4())
    second = build_authored_item(item_id, uuid4())
    first.place_on_grid((3, 3), boundary_direction=CardinalDirection.EAST, base_height_steps=2)
    state = first.to_item_presentation_state()
    profile = DOOR_PROFILES[item_id]
    assert first.uuid != second.uuid and first.health is not second.health
    assert state.item_id == item_id and state.boundary_structure.material == profile.material
    assert state.maximum_hit_points == (27 if profile.material is Material.METAL else 18)
    assert state.door_mechanism is profile.mechanism and state.door_swing is DoorSwing.OUTWARD
    placement = get_map().get_object_placement(first.uuid)
    assert (placement.base_height_steps, placement.top_height_steps) == (2, 4)
    expected = (WorldEdgeChannel.MOVEMENT,) if profile.mechanism is DoorMechanism.LIFT else tuple(WorldEdgeChannel)
    assert state.boundary_structure.blocked_channels == expected


@pytest.mark.parametrize("swing", tuple(DoorSwing))
@pytest.mark.parametrize("open_before_break", (False, True))
@pytest.mark.parametrize("item_id,outcome", [(item_id, outcome)
    for item_id, profile in DOOR_PROFILES.items()
    for outcome in (("clear", "jammed") if profile.supports_jammed_remnant else ("clear",))])
def test_real_door_attacks_preserve_swing_elevation_and_clear_or_jammed_remains(arena, swing, open_before_break, item_id, outcome):
    attacker = actor(arena, (2, 3))
    door = build_authored_door(item_id, swing=swing,
        destruction_outcome=outcome, hit_points=12)
    original = door.place_on_grid((3, 3), boundary_direction=CardinalDirection.EAST,
        orientation=CardinalDirection.SOUTH, base_height_steps=0)
    if open_before_break:
        opened = execute_use_action(attacker, door.uuid, "Open Door")
        assert not opened.canceled and door.is_open
    stale_action, = door.get_use_actions(attacker.uuid)
    stale_action = stale_action.instantiate()
    attack(attacker, door, 4)
    assert door.get_hp() == 8 and get_map().get_object_placement(door.uuid) == original
    cursor = EventQueue.event_cursor()
    lethal = attack(attacker, door, 8)
    destruction, = destroyed_since(cursor)
    assert BaseBlock.get(door.uuid) is door and door.integrity is ItemIntegrity.DESTROYED
    assert destruction.replacement_item_uuid is None
    state = door.to_item_presentation_state()
    assert state.item_id == item_id and state.destruction_outcome == outcome
    assert state.remnant_state.door_open is open_before_break and state.remnant_state.door_swing is swing
    assert destruction.item_state.remnant_state == state.remnant_state
    assert not any((state.is_targetable, state.is_usable, state.is_pickable))
    placement = get_map().get_object_placement(door.uuid)
    assert (placement.position, placement.boundary_direction, placement.orientation,
            placement.base_height_steps, placement.top_height_steps) == (
        original.position, original.boundary_direction, original.orientation,
        original.base_height_steps, original.top_height_steps)
    assert get_map().can_transition((3, 3), (4, 3)) is (outcome == "clear")
    completed = [event for _, event in EventQueue.iter_events_since(cursor) if event.phase is EventPhase.COMPLETION]
    damage, = [event for event in completed if isinstance(event, TakeDamageEvent)]
    assert damage.lineage_uuid in ancestor_lineages(destruction)
    assert damage.parent_lineage == lethal.lineage_uuid
    arriving = actor(arena, (4, 4), "Late witness")
    Entity.update_all_entities_senses()
    assert door.uuid in arriving.senses.objects
    assert door.get_use_actions(attacker.uuid) == []
    rejected = stale_action.apply()
    assert rejected is not None and rejected.canceled
    before_open = door.is_open
    door.open()
    door.close()
    assert door.is_open is before_open
    assert get_map().can_transition((3, 3), (4, 3)) is (outcome == "clear")


def test_door_close_still_rejects_an_occupied_opening_and_retains_swing(arena):
    operator = actor(arena, (2, 3))
    door = build_authored_door("environment.door.indoor_door_shabby", swing=DoorSwing.INWARD)
    door.place_on_grid((3, 3), boundary_direction=CardinalDirection.EAST)
    assert not execute_use_action(operator, door.uuid, "Open Door").canceled
    traveler = actor(arena, (3, 3))
    assert door.get_use_actions(operator.uuid) == [] and door.is_open
    move(traveler, (4, 3))
    assert not execute_use_action(operator, door.uuid, "Close Door").canceled
    assert not door.is_open and door.to_item_presentation_state().door_swing is DoorSwing.INWARD


@pytest.mark.parametrize("mode", (TrapState.READY, TrapState.ACTIVATED))
@pytest.mark.parametrize("item_id", tuple(TRAP_HARDWARE_PROFILES))
@pytest.mark.parametrize("direction,orientation", (((1, 0), CardinalDirection.EAST),
    ((-1, 0), CardinalDirection.WEST), ((0, 1), CardinalDirection.NORTH), ((0, -1), CardinalDirection.SOUTH)))
def test_hardware_destruction_leaves_plate_and_other_output_working(arena, item_id, mode, direction, orientation):
    attacker = actor(arena, (2, 3))
    traveler = actor(arena, (2, 2))
    item, mechanism = materialize_trap_hardware((3, 3),
        item_id=item_id, hit_points=12, trap_state=mode, direction=direction)
    peer = materialize_finite_trap((6, 6), geometry=AreaGeometry())
    plate = materialize_pressure_plate({(3, 2)}, (
        ActivationLink(target_condition_uuid=mechanism.uuid), ActivationLink(target_condition_uuid=peer.uuid)))
    attack(attacker, item, 4)
    assert mechanism.is_active_spatial_condition() and item.get_hp() == 8
    cursor = EventQueue.event_cursor()
    attack(attacker, item, 8)
    destruction, = destroyed_since(cursor)
    assert BaseBlock.get(item.uuid) is item and item.integrity is ItemIntegrity.DESTROYED
    assert destruction.replacement_item_uuid is None
    assert item.to_item_presentation_state().remnant_state.mechanism_state is mode
    assert get_map().get_object_placement(item.uuid).orientation is orientation
    assert not mechanism.is_active_spatial_condition() and plate.is_active_spatial_condition()
    assert get_map().can_transition((3, 2), (3, 3))
    cursor = EventQueue.event_cursor()
    move(traveler, (3, 2))
    assert plate.pressed
    move(traveler, (2, 2))
    assert not plate.pressed
    move(traveler, (3, 2))
    committed = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, MechanismActivationEvent) and event.phase is EventPhase.COMPLETION and event.committed]
    assert len(committed) == 2 and {event.mechanism_uuid for event in committed} == {peer.uuid}


def test_same_press_keeps_second_pulse_when_first_successful_save_retreats(arena):
    traveler = actor(arena, (2, 2))
    _, first = materialize_trap_hardware((3, 2), avoidance=TrapSave(dc=12, retreat_on_success=True))
    peer = materialize_finite_trap((6, 6), geometry=AreaGeometry())
    plate = materialize_pressure_plate({(3, 2)}, (
        ActivationLink(target_condition_uuid=first.uuid), ActivationLink(target_condition_uuid=peer.uuid)))
    cursor = EventQueue.event_cursor()
    move(traveler, (3, 2), 20)
    assert traveler.position == (2, 2) and not plate.pressed
    committed = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, MechanismActivationEvent) and event.phase is EventPhase.COMPLETION and event.committed]
    assert {event.mechanism_uuid for event in committed} == {first.uuid, peer.uuid}


def test_hidden_hardware_uses_existing_discovery_then_reveals_both_contacts_under_real_activation(arena):
    traveler = actor(arena, (2, 2))
    hardware, mechanism = materialize_trap_hardware((3, 2), stealth_dc=30)
    plate = materialize_pressure_plate({(3, 2)}, ActivationLink(target_condition_uuid=mechanism.uuid))
    Entity.update_all_entities_senses()
    assert mechanism.uuid not in traveler.senses.spatial_effects and hardware.uuid not in traveler.senses.objects
    assert not any(target.target_uuid == hardware.uuid for action in get_available_actions(traveler).all_actions
                   for target in action.valid_targets)
    cursor = EventQueue.event_cursor()
    move(traveler, (3, 2), 20)
    assert not plate.pressed and traveler.position == (2, 2)
    assert hardware.uuid in traveler.senses.objects
    observed = traveler.senses.spatial_effects[mechanism.uuid]
    assert observed.anchor_item_uuid == hardware.uuid
    changes = [event for _, event in EventQueue.iter_events_since(cursor)
               if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == traveler.uuid]
    assert any(event.spatial_effects_changed.get(mechanism.uuid) is not None
               and event.spatial_effects_changed[mechanism.uuid].anchor_item_uuid == hardware.uuid
               and hardware.uuid in event.object_contacts_changed for event in changes)


@pytest.mark.parametrize("dc_offset,expected", ((-1, True), (0, False), (1, False)))
def test_hardware_discovery_matches_mechanism_existing_passive_threshold(arena, dc_offset, expected):
    observer = actor(arena, (2, 2))
    hardware, mechanism = materialize_trap_hardware((3, 2),
        stealth_dc=observer.get_passive_perception() + dc_offset)
    observer.update_entity_senses()
    assert (hardware.uuid in observer.senses.objects) is expected
    assert (mechanism.uuid in observer.senses.spatial_effects) is expected
    if expected:
        assert observer.senses.spatial_effects[mechanism.uuid].anchor_item_uuid == hardware.uuid


@pytest.mark.parametrize("intercept", (EventType.MECHANISM_ACTIVATION, EventType.SAVING_THROW))
def test_destroyed_during_activation_cannot_apply_pending_payload_or_rearm(arena, intercept):
    target = actor(arena, (3, 3))
    item, mechanism = materialize_trap_hardware((3, 3), hit_points=8, rearm_after_activation=True)

    def break_before_payload(event, _source):
        if intercept is EventType.SAVING_THROW or event.source_entity_uuid == mechanism.uuid:
            item.receive_damage(8, DamageType.SLASHING, target.uuid, parent_event=event)

    EventQueue.add_event_handler(EventHandler(name="Break before strike", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=intercept, event_phase=EventPhase.EFFECT)],
        event_processor=break_before_payload))
    cause = EventQueue.publish_declaration(Event(name="Control pulse", source_entity_uuid=target.uuid,
        event_type=EventType.BASE_ACTION, use_register=False))
    cause = cause.phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
    with fixed_dice_faces(1):
        result = mechanism.fire(parent_event=cause)
    cause.phase_to(EventPhase.COMPLETION)
    if intercept is EventType.MECHANISM_ACTIVATION:
        assert result.canceled and not result.committed
    else:
        assert result.committed  # The activation/save happened; its damage did not.
    assert target.get_hp() == 80 and not mechanism.is_active_spatial_condition()
    assert BaseBlock.get(item.uuid) is item and item.integrity is ItemIntegrity.DESTROYED


def ancestor_lineages(event):
    result = set()
    while event.parent_event is not None:
        event = EventQueue.get_event_by_uuid(event.parent_event)
        assert event is not None
        result.add(event.lineage_uuid)
    return result


@pytest.mark.parametrize("item_id", (
    "environment.blocker.crate", "environment.blocker.boulder",
    "environment.blocker.barricade", "environment.blocker.oil_barrel",
    "environment.fireball_cannon", "environment.arcane_machine_gun",
))
def test_other_registered_breakables_keep_identity_and_only_explicit_removal_retires(arena, item_id):
    attacker = actor(arena, (2, 3))
    item = build_authored_item(item_id, attacker.uuid)
    item.place_on_grid((3, 3))
    original_uuid = item.uuid
    while item.get_hp() > 8:
        attack(attacker, item, 4)
    cursor = EventQueue.event_cursor()
    attack(attacker, item, 8)
    assert item.integrity is ItemIntegrity.DESTROYED
    assert BaseBlock.get(original_uuid) is item
    state = item.to_item_presentation_state()
    assert state.item_id == item_id and state.integrity is ItemIntegrity.DESTROYED
    assert get_map().get_object_position(item.uuid) == (3, 3)
    assert not state.is_targetable and not state.is_usable
    assert get_map().can_transition((3, 2), (3, 3))
    destruction, = destroyed_since(cursor)
    assert destruction.item_state.item_uuid == original_uuid and destruction.replacement_item_uuid is None
    retained_conditions = {condition.uuid for condition in get_map().get_spatial_conditions()}
    item.destroy()
    assert {condition.uuid for condition in get_map().get_spatial_conditions()} == retained_conditions
    item.retire()
    assert BaseBlock.get(original_uuid) is None
    assert get_map().get_object_position(original_uuid) is None
    # Destruction-created areas are independent aftermath, not intact-item effects.
    assert {condition.uuid for condition in get_map().get_spatial_conditions()} == retained_conditions


@pytest.mark.parametrize("kind", ("generic", "direct", "legacy"))
@pytest.mark.parametrize("opened", (False, True))
def test_generic_and_helper_doors_use_same_persistent_lifecycle(arena, kind, opened):
    attacker = actor(arena, (2, 3))
    if kind == "generic":
        door = build_directional_door(is_open=opened)
    elif kind == "direct":
        door = DirectionalDoor(source_entity_uuid=attacker.uuid, item_id="test.direct_door", is_open=opened)
    else:
        door = DoorObject(source_entity_uuid=attacker.uuid, item_id="test.legacy_door", is_open=opened)
    if isinstance(door, DirectionalDoor):
        door.place_on_grid((3, 3), boundary_direction=CardinalDirection.EAST)
    else:
        door.place_on_grid((3, 3))
    action, = door.get_use_actions(attacker.uuid)
    stale = action.instantiate()
    while door.get_hp() > 8:
        attack(attacker, door, 4)
    attack(attacker, door, 8)
    assert BaseBlock.get(door.uuid) is door
    assert door.integrity is ItemIntegrity.DESTROYED
    assert door.to_item_presentation_state().remnant_state.door_open is opened
    assert get_map().can_transition((3, 3), (4, 3))
    assert door.get_use_actions(attacker.uuid) == []
    result = stale.apply()
    assert result is not None and result.canceled
    assert door.is_open is opened


@pytest.mark.parametrize("build", (build_wall_torch, build_standing_torch))
def test_fixed_light_break_extinguishes_and_stale_use_cannot_relight(arena, build):
    attacker = actor(arena, (2, 3))
    get_map().set_tile_base_light((3, 3), LightLevel.DARKNESS)
    torch = build()
    torch.place_on_grid((3, 3))
    ignite, = torch.get_use_actions(attacker.uuid)
    stale_ignite = ignite.instantiate() if ignite.template else ignite
    assert torch.light() is not None and torch.is_lit
    tile = get_map().get_tile(3, 3)
    assert tile is not None and tile.resolved_light_level is not LightLevel.DARKNESS
    attack(attacker, torch, 8)
    assert BaseBlock.get(torch.uuid) is torch and not torch.is_lit
    assert torch.to_item_presentation_state().integrity is ItemIntegrity.DESTROYED
    assert tile.resolved_light_level is LightLevel.DARKNESS
    assert torch.get_use_actions(attacker.uuid) == []
    rejected = stale_ignite.apply()
    assert rejected is not None and rejected.canceled
    assert torch.light() is None and not torch.is_lit
    assert tile.resolved_light_level is LightLevel.DARKNESS


@pytest.mark.parametrize("kind", ("control", "trap"))
def test_destroyed_lever_cannot_change_its_surviving_target(arena, kind):
    attacker = actor(arena, (2, 3))
    if kind == "control":
        door = build_directional_door()
        door.place_on_grid((4, 3), boundary_direction=CardinalDirection.EAST)
        lever = build_control_lever(ControlLink(target_kind="door", target_item_uuid=door.uuid))
        target_before = door.to_item_presentation_state()
    else:
        _, mechanism = materialize_trap_hardware((5, 3))
        lever = build_trap_lever(mechanism.uuid, charges=-1, allow_activation=True)
        target_before = mechanism.trap_state
    lever.place_on_grid((3, 3))
    action, = lever.get_use_actions(attacker.uuid)
    stale = action.instantiate()
    attack(attacker, lever, 4)
    attack(attacker, lever, 8)
    assert BaseBlock.get(lever.uuid) is lever and lever.integrity is ItemIntegrity.DESTROYED
    assert lever.get_use_actions(attacker.uuid) == []
    rejected = stale.apply()
    assert rejected is not None and rejected.canceled
    if kind == "control":
        assert door.to_item_presentation_state() == target_before
    else:
        assert mechanism.applied and mechanism.trap_state is target_before


@pytest.mark.parametrize("item_id", ("environment.storage_chest", *CHEST_DEFINITIONS))
def test_breaking_container_spills_once_under_damage_cause_without_replacing_container(arena, item_id):
    attacker = actor(arena, (2, 3))
    chest = build_authored_item(item_id, attacker.uuid)
    assert isinstance(chest, StorageChest)
    gem = BaseItem(source_entity_uuid=attacker.uuid, item_id="test.spilled_gem", name="Gem")
    assert chest.chest_inventory.add_item(gem)
    gem.owner_uuid = chest.uuid
    gem.stored_in_uuid = chest.chest_inventory.uuid
    chest.place_on_grid((3, 3))
    opened = execute_use_action(attacker, chest.uuid, "Open Chest")
    assert opened is not None and not opened.canceled
    while chest.get_hp() > 8:
        attack(attacker, chest, 4)
    cursor = EventQueue.event_cursor()
    attack(attacker, chest, 8)
    completed = [event for _, event in EventQueue.iter_events_since(cursor)
                 if event.phase is EventPhase.COMPLETION]
    damage, = [event for event in completed if isinstance(event, TakeDamageEvent)]
    spill, = [event for event in completed if isinstance(event, SpatialChangeEvent)
              and event.object_uuid == gem.uuid and event.event_type is EventType.SPATIAL_OBJECT_PLACED]
    assert damage.lineage_uuid in ancestor_lineages(spill)
    assert BaseBlock.get(chest.uuid) is chest and chest.integrity is ItemIntegrity.DESTROYED
    assert get_map().get_object_position(chest.uuid) == (3, 3)
    assert get_map().get_object_position(gem.uuid) == (3, 3)
    assert not chest.chest_inventory.items
    assert gem.owner_uuid is None and gem.stored_in_uuid is None
    cursor = EventQueue.event_cursor()
    chest.destroy()
    assert not list(EventQueue.iter_events_since(cursor))
