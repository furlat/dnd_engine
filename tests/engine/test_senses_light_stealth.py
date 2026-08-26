"""Executable contract for unified optics, illumination, and perception."""
from dnd.types.materials import Material, TileSurface

from uuid import UUID, uuid4

import pytest

from dnd.actions.standard import Move
from dnd.actions.operations import execute_use_action
from dnd.blocks.base_item import BaseItem
from dnd.blocks.sensory import (
    Senses,
    capture_senses_snapshot,
    spatial_senses_system,
)
from dnd.conditions import Blinded, Hidden, Invisible
from dnd.content.spatial_effect_materialization import materialize_spatial_condition
from dnd.content.spatial_effect_recipes import (
    DARKNESS_FIELD_RECIPE,
    FOG_CLOUD_RECIPE,
)
from dnd.core.base_actions import BaseAction, TargetType
from dnd.core.base_block import BaseBlock
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events.events_registry import Event, EventPhase, EventQueue, EventType
from dnd.core.events.world_events import (
    SensoryUpdateEvent,
    SensoryUpdateReason,
    SpatialChangeEvent,
    SpatialChangeType,
)
from dnd.core.gridmap import get_map
from dnd.content.items.environment_item_builders import (
    build_directional_door,
    build_directional_wall,
)
from dnd.spells.conjuration import DarknessZone, FogCloudZone
from dnd.types.senses import PerceivedContact, OpticalObscurement, SenseMode, SensesType
from dnd.types.world import CardinalDirection, LightLevel, WorldEdgeChannel
from tests.engine.support import create_test_monster, reset_combat_state


class PerceptionLogEvent(Event):
    """Small loggable fact used to prove observer policy outside Encounter."""

    def generate_combat_log(self) -> CombatLogEntry:
        """Return one deterministic combat-log projection."""
        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=self.source_entity_name or "Source",
            source_uuid=str(self.source_entity_uuid),
            target_name=self.target_entity_name,
            target_uuid=(
                str(self.target_entity_uuid)
                if self.target_entity_uuid is not None
                else None
            ),
            compact="Observed action",
            verbose="Observed action",
            detailed="Observed action",
        )


def reset_senses_state(
    width: int = 8,
    height: int = 3,
    default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
) -> None:
    """Reset the engine and build one event-silent rectangular battlefield."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, width, height, surface=TileSurface(base_material=Material.STONE))
    if default_light is not LightLevel.BRIGHT_LIGHT:
        for position in grid.get_all_tiles():
            grid.set_tile_base_light(position, default_light)
    grid.enable_events(flush_pending=False)


def completed_sensory_updates(observer_uuid: UUID) -> list[SensoryUpdateEvent]:
    """Return recorded completion deltas for one observer."""
    return [
        event
        for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, SensoryUpdateEvent)
        and event.phase is EventPhase.COMPLETION
        and event.observer_uuid == observer_uuid
    ]


def perception_projection(senses: Senses) -> tuple[object, ...]:
    """Return exactly the replay-owned perception fields, excluding navigation."""
    snapshot = capture_senses_snapshot(senses)
    return (
        snapshot.position,
        snapshot.visible,
        snapshot.seen,
        snapshot.entities,
        snapshot.objects,
        snapshot.effective_light_levels,
        tuple(senses.get_sense_modes()),
        snapshot.passive_perception,
        snapshot.visual_access,
    )


def root_action(source_uuid: UUID) -> Event:
    """Publish one ordinary root fact for a spatial-condition lifecycle."""
    completed = EventQueue.publish_lifecycle(Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    assert completed is not None
    return completed


def set_modes(observer_uuid: UUID, modes: list[SenseMode]) -> None:
    """Set innate test senses and run the exact observer resolver."""
    senses = spatial_senses_system.senses_by_observer[observer_uuid]
    senses.sense_modes = modes
    spatial_senses_system.recompute_observer(observer_uuid)


def activate_fog(source_uuid: UUID, position: tuple[int, int]) -> FogCloudZone:
    """Create one exact authored heavy-fog condition."""
    fog = materialize_spatial_condition(
        FOG_CLOUD_RECIPE,
        source_uuid,
        position=position,
        faction="tests",
        condition_type=FogCloudZone,
        condition_fields={"zone_radius_feet": 0},
    )
    result = fog.activate(parent_event=root_action(source_uuid))
    assert result is not None and not result.canceled and fog.applied
    return fog


def activate_darkness(source_uuid: UUID, position: tuple[int, int]) -> DarknessZone:
    """Create one exact authored magical-darkness condition."""
    darkness = materialize_spatial_condition(
        DARKNESS_FIELD_RECIPE,
        source_uuid,
        position=position,
        faction="tests",
        condition_type=DarknessZone,
        condition_fields={"zone_radius_feet": 0},
    )
    result = darkness.activate(parent_event=root_action(source_uuid))
    assert result is not None and not result.canceled and darkness.applied
    return darkness


def test_ordinary_sight_filters_darkness_without_adjacent_promotion() -> None:
    """Physical FOV subscriptions survive even where illumination hides content."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(3, 0), darkvision=False,
    )

    assert (3, 0) in get_map().get_entity_subscriptions(observer.uuid)
    assert observer.senses.visible == {}
    assert observer.senses.effective_light_levels == {}
    assert target.uuid not in observer.senses.entities


def test_adjacent_directional_door_does_not_fabricate_visual_contact() -> None:
    """Interaction adjacency never bypasses objective optics or illumination."""
    reset_senses_state(width=3, height=1, default_light=LightLevel.DARKNESS)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    door = build_directional_door(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    get_map().place_object(
        door.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
    )

    assert door.uuid not in observer.senses.objects


def test_near_lit_tile_contacts_entry_boundary_without_far_tile_content() -> None:
    """A lit near Tile reveals an opaque entry boundary but not its far contents."""
    reset_senses_state(width=4, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    entry_wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(entry_wall.uuid, (1, 0), boundary_direction=CardinalDirection.WEST)
    grid.add_light_source((0, 0), bright_radius_feet=5, dim_radius_feet=0)
    assert grid.get_tile(0, 0).resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert grid.get_tile(1, 0).resolved_light_level is LightLevel.DARKNESS
    far_entity = create_test_monster(
        "monster.skeleton", name="Hidden far entity", position=(1, 0), darkvision=False,
    )
    observer = create_test_monster(
        "monster.skeleton", name="Near observer", position=(0, 0), darkvision=False,
    )

    assert entry_wall.uuid in observer.senses.objects
    assert observer.senses.objects[entry_wall.uuid] == PerceivedContact(
        position=(1, 0), visual=True, special_senses=(),
    )
    assert (1, 0) not in observer.senses.visible
    assert far_entity.uuid not in observer.senses.entities

    assert not grid.can_transition((0, 0), (1, 0))
    entry_wall.set_invisible(True)
    assert not grid.can_transition((0, 0), (1, 0))
    assert entry_wall.uuid not in observer.senses.objects
    entry_wall.set_invisible(False)
    assert not grid.can_transition((0, 0), (1, 0))
    assert observer.senses.objects[entry_wall.uuid] == PerceivedContact(
        position=(1, 0), visual=True, special_senses=(),
    )


def test_opaque_exit_hides_entry_boundary_and_far_contents() -> None:
    """An opaque exit layer stops ordered visual boundary exposure."""
    reset_senses_state(width=5, height=1)
    grid = get_map()
    exit_wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    entry_wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(exit_wall.uuid, (1, 0), boundary_direction=CardinalDirection.EAST)
    grid.place_object(entry_wall.uuid, (2, 0), boundary_direction=CardinalDirection.WEST)
    far_entity = create_test_monster(
        "monster.skeleton", name="Hidden beyond exit", position=(2, 0), darkvision=False,
    )
    observer = create_test_monster(
        "monster.skeleton", name="Exit observer", position=(0, 0), darkvision=False,
    )

    assert exit_wall.uuid in observer.senses.objects
    assert entry_wall.uuid not in observer.senses.objects
    assert far_entity.uuid not in observer.senses.entities


def test_open_exit_reaches_entry_boundary_but_not_blocked_far_center() -> None:
    """An open exit layer exposes the terminal entry boundary only."""
    reset_senses_state(width=5, height=1)
    grid = get_map()
    open_exit = build_directional_door(
        blocked_channels=tuple(WorldEdgeChannel),
        is_open=True,
    )
    entry_wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(open_exit.uuid, (1, 0), boundary_direction=CardinalDirection.EAST)
    grid.place_object(entry_wall.uuid, (2, 0), boundary_direction=CardinalDirection.WEST)
    far_entity = create_test_monster(
        "monster.skeleton", name="Hidden behind entry", position=(2, 0), darkvision=False,
    )
    observer = create_test_monster(
        "monster.skeleton", name="Open exit observer", position=(0, 0), darkvision=False,
    )

    assert open_exit.uuid in observer.senses.objects
    assert entry_wall.uuid in observer.senses.objects
    assert observer.senses.objects[entry_wall.uuid].visual is True
    assert (2, 0) not in observer.senses.visible
    assert far_entity.uuid not in observer.senses.entities


def test_reverse_observers_contact_their_near_terminal_boundary_only() -> None:
    """Opposite observers resolve reverse ordered terminal layers independently."""
    reset_senses_state(width=4, height=1)
    grid = get_map()
    left_boundary = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    right_boundary = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(left_boundary.uuid, (1, 0), boundary_direction=CardinalDirection.EAST)
    grid.place_object(right_boundary.uuid, (2, 0), boundary_direction=CardinalDirection.WEST)
    far_for_left = create_test_monster(
        "monster.skeleton", name="Far for left", position=(2, 0), darkvision=False,
    )
    far_for_right = create_test_monster(
        "monster.skeleton", name="Far for right", position=(1, 0), darkvision=False,
    )
    left_observer = create_test_monster(
        "monster.skeleton", name="Left observer", position=(0, 0), darkvision=False,
    )
    right_observer = create_test_monster(
        "monster.skeleton", name="Right observer", position=(3, 0), darkvision=False,
    )

    assert left_boundary.uuid in left_observer.senses.objects
    assert right_boundary.uuid not in left_observer.senses.objects
    assert far_for_left.uuid not in left_observer.senses.entities
    assert right_boundary.uuid in right_observer.senses.objects
    assert left_boundary.uuid not in right_observer.senses.objects
    assert far_for_right.uuid not in right_observer.senses.entities


def test_visible_incident_cells_contact_transparent_boundary_from_either_side() -> None:
    """A transparent boundary between visible cells is reached from both sides."""
    reset_senses_state(width=4, height=1)
    grid = get_map()
    boundary = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        boundary.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    left_observer = create_test_monster(
        "monster.skeleton", name="Left route observer", position=(0, 0), darkvision=False,
    )
    right_observer = create_test_monster(
        "monster.skeleton", name="Right route observer", position=(3, 0), darkvision=False,
    )

    assert (1, 0) in left_observer.senses.visible
    assert (2, 0) in left_observer.senses.visible
    assert (1, 0) in right_observer.senses.visible
    assert (2, 0) in right_observer.senses.visible
    assert left_observer.senses.objects[boundary.uuid] == PerceivedContact(
        position=(1, 0), visual=True, special_senses=(),
    )
    assert right_observer.senses.objects[boundary.uuid] == PerceivedContact(
        position=(1, 0), visual=True, special_senses=(),
    )


def test_visual_and_nonvisual_boundary_routes_merge_one_contact_deterministically() -> None:
    """One provider reached by visual and blindsight routes yields one merged contact."""
    reset_senses_state(width=4, height=1)
    grid = get_map()
    wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(wall.uuid, (1, 0), boundary_direction=CardinalDirection.EAST)
    observer = create_test_monster(
        "monster.skeleton", name="Dual-route observer", position=(0, 0), darkvision=False,
    )
    set_modes(observer.uuid, [SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=20)])

    contact = observer.senses.objects[wall.uuid]
    assert contact.position == (1, 0)
    assert contact.visual is True
    assert contact.special_senses == (SensesType.BLINDSIGHT,)
    assert list(observer.senses.objects).count(wall.uuid) == 1


@pytest.mark.parametrize("sense_type", [SensesType.BLINDSIGHT, SensesType.TREMORSENSE])
def test_nonvisual_boundary_route_contacts_without_visual_evidence(
    sense_type: SensesType,
) -> None:
    """Propagation-only route evidence establishes boundary contact by special sense."""
    reset_senses_state(width=4, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(wall.uuid, (1, 0), boundary_direction=CardinalDirection.EAST)
    observer = create_test_monster(
        "monster.skeleton", name="Nonvisual observer", position=(0, 0), darkvision=False,
    )
    set_modes(observer.uuid, [SenseMode(sense_type=sense_type, range_feet=20)])

    contact = observer.senses.objects[wall.uuid]
    assert contact.position == (1, 0)
    assert contact.visual is False
    assert contact.special_senses == (sense_type,)
    assert (1, 0) not in observer.senses.visible


def test_boundary_invisibility_and_stealth_change_contact_not_objective_transition() -> None:
    """Subjective boundary visibility never changes the objective edge answer."""
    reset_senses_state(width=4, height=1)
    grid = get_map()
    wall = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(wall.uuid, (1, 0), boundary_direction=CardinalDirection.EAST)
    observer = create_test_monster(
        "monster.skeleton", name="Boundary observer", position=(0, 0), darkvision=False,
    )
    assert not grid.can_transition((1, 0), (2, 0))
    assert wall.uuid in observer.senses.objects

    wall.set_invisible(True)
    assert not grid.can_transition((1, 0), (2, 0))
    assert wall.uuid not in observer.senses.objects

    wall.set_invisible(False)
    wall.set_stealth_dc(observer.get_passive_perception() + 1)
    assert not grid.can_transition((1, 0), (2, 0))
    assert wall.uuid not in observer.senses.objects

    wall.set_stealth_dc(None)
    assert not grid.can_transition((1, 0), (2, 0))
    assert wall.uuid in observer.senses.objects


def test_light_change_reveals_subscribed_dark_cell_reactively() -> None:
    """One objective light fact causes an observer-local typed-contact delta."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(3, 0), darkvision=False,
    )
    cursor = EventQueue.event_cursor()

    get_map().add_light_source(
        (3, 0), bright_radius_feet=5, dim_radius_feet=0,
    )

    contact = observer.senses.entities[target.uuid]
    assert contact.position == (3, 0)
    assert contact.visual is True
    assert contact.special_senses == ()
    assert observer.senses.effective_light_levels[(3, 0)] is LightLevel.BRIGHT_LIGHT
    updates = [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
    ]
    assert len(updates) == 1
    assert updates[0].update_reason is SensoryUpdateReason.LIGHT
    assert updates[0].entity_contacts_changed[target.uuid] == contact


def test_one_optical_boundary_blocks_sight_and_light_but_not_propagation() -> None:
    """Vision and light share optics while physical propagation remains distinct."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.OPTICAL,),
    )
    grid.place_object(
        wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )

    assert (2, 0) not in grid.compute_fov((0, 0), max_distance=5)
    assert (2, 0) in grid.compute_propagation_fov((0, 0), max_distance=5)
    light_uuid = grid.add_light_source(
        (0, 0), bright_radius_feet=5, dim_radius_feet=20,
    )
    assert (2, 0) not in grid._light_sources[light_uuid].affected_tiles
    tile = grid.get_tile(2, 0)
    assert tile is not None and tile.resolved_light_level is LightLevel.DARKNESS


def test_darkvision_has_exact_range_and_does_not_cross_fog_or_magic_darkness() -> None:
    """Darkvision upgrades natural darkness only inside its authored range."""
    reset_senses_state(width=15, height=1, default_light=LightLevel.DARKNESS)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=True,
    )
    at_range = create_test_monster(
        "monster.skeleton", name="At range", position=(12, 0), darkvision=False,
    )
    beyond = create_test_monster(
        "monster.skeleton", name="Beyond", position=(13, 0), darkvision=False,
    )

    assert observer.senses.entities[at_range.uuid].visual is True
    assert beyond.uuid not in observer.senses.entities

    fog = activate_fog(observer.uuid, (6, 0))
    assert at_range.uuid not in observer.senses.entities
    fog_tile = get_map().get_tile(6, 0)
    assert fog_tile is not None and fog_tile.resolved_light_level is LightLevel.DARKNESS
    assert get_map().get_optical_obscurements_at((6, 0)) == (
        OpticalObscurement.HEAVY,
    )
    fog.deactivate(parent_event=root_action(observer.uuid))

    darkness = activate_darkness(observer.uuid, (6, 0))
    assert at_range.uuid not in observer.senses.entities
    assert get_map().get_optical_obscurements_at((6, 0)) == (
        OpticalObscurement.MAGICAL_DARKNESS,
    )
    darkness.deactivate(parent_event=root_action(observer.uuid))
    assert observer.senses.entities[at_range.uuid].visual is True


@pytest.mark.parametrize(
    ("sense_type", "sees_magical_darkness"),
    [
        (SensesType.DEVILS_SIGHT, True),
        (SensesType.TRUESIGHT, True),
        (SensesType.DARKVISION, False),
    ],
)
def test_visual_special_senses_resolve_magic_darkness_but_not_heavy_fog(
    sense_type: SensesType,
    sees_magical_darkness: bool,
) -> None:
    """Visual special senses obey the explicit obscurement table."""
    reset_senses_state(width=8, height=1)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(6, 0), darkvision=False,
    )
    set_modes(observer.uuid, [SenseMode(sense_type=sense_type, range_feet=30)])
    darkness = activate_darkness(observer.uuid, (3, 0))

    assert (target.uuid in observer.senses.entities) is sees_magical_darkness
    if sees_magical_darkness:
        assert observer.senses.entities[target.uuid].visual is True
        assert sense_type in observer.senses.entities[target.uuid].special_senses
        assert (
            observer.senses.effective_light_levels[target.position]
            is LightLevel.BRIGHT_LIGHT
        )

    darkness.deactivate(parent_event=root_action(observer.uuid))
    fog = activate_fog(observer.uuid, (3, 0))
    assert target.uuid not in observer.senses.entities
    fog.deactivate(parent_event=root_action(observer.uuid))


@pytest.mark.parametrize("sense_type", [SensesType.BLINDSIGHT, SensesType.TREMORSENSE])
def test_nonvisual_senses_create_contacts_without_visual_cells(
    sense_type: SensesType,
) -> None:
    """Nonvisual senses identify contacts but never invent illumination or sight."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(3, 0), darkvision=False,
    )
    set_modes(observer.uuid, [SenseMode(sense_type=sense_type, range_feet=20)])

    contact = observer.senses.entities[target.uuid]
    assert contact.visual is False
    assert contact.special_senses == (sense_type,)
    assert (3, 0) not in observer.senses.visible
    assert (3, 0) not in observer.senses.effective_light_levels
    probe = BaseAction(
        name="Perceived Target Probe",
        source_entity_uuid=observer.uuid,
        target_entity_uuid=target.uuid,
        target_type=TargetType.ENTITY,
        valid_target_filter="all",
        use_register=False,
    )
    assert probe._validate_target_filter([target.uuid]) is None


def test_darkness_activation_and_removal_publish_only_complete_optical_state() -> None:
    """A darkness cap and its optical footprint reduce as one committed state."""
    reset_senses_state(width=7, height=1)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=True,
    )
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(6, 0), darkvision=False,
    )
    assert target.uuid in observer.senses.entities

    cursor = EventQueue.event_cursor()
    darkness = activate_darkness(observer.uuid, (3, 0))
    activation_updates = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
    ]
    assert len(activation_updates) == 1
    assert activation_updates[0].entity_contacts_removed == {target.uuid}
    assert target.uuid not in activation_updates[0].entity_contacts_changed

    cursor = EventQueue.event_cursor()
    darkness.deactivate(parent_event=root_action(observer.uuid))
    removal_updates = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
    ]
    assert len(removal_updates) == 1
    assert removal_updates[0].entity_contacts_changed[target.uuid].visual is True


def test_invisibility_requires_an_exact_bypass_and_preserves_surviving_owner() -> None:
    """Removing one Invisible source cannot clear another source's state."""
    reset_senses_state(width=6, height=1)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(3, 0), darkvision=False,
    )
    first = Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    second = Invisible(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=target.uuid,
        name="Invisible (second source)",
    )
    target.add_condition(first)
    target.add_condition(second)

    assert target.is_invisible is True
    assert target.uuid not in observer.senses.entities
    target.remove_condition_by_uuid(first.uuid)
    assert target.is_invisible is True
    assert target.uuid not in observer.senses.entities

    set_modes(observer.uuid, [
        SenseMode(sense_type=SensesType.SEE_INVISIBLE, range_feet=20),
    ])
    contact = observer.senses.entities[target.uuid]
    assert contact.visual is True
    assert contact.special_senses == ()

    target.remove_condition_by_uuid(second.uuid)
    assert target.is_invisible is False


def test_hidden_uses_surviving_source_dc_and_emits_typed_contact_changes() -> None:
    """Stacked stealth is source-owned and observer deltas carry after-values."""
    reset_senses_state(width=6, height=1)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(3, 0), darkvision=False,
    )
    low = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        name="Hidden (low)",
        stealth_result=observer.get_passive_perception() + 1,
    )
    high = Hidden(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=target.uuid,
        name="Hidden (high)",
        stealth_result=observer.get_passive_perception() + 5,
    )
    target.add_condition(low)
    target.add_condition(high)
    assert target.uuid not in observer.senses.entities

    target.remove_condition_by_uuid(high.uuid)
    assert target.stealth_dc == low.stealth_result
    assert target.uuid not in observer.senses.entities
    target.remove_condition_by_uuid(low.uuid)

    contact = observer.senses.entities[target.uuid]
    assert contact.visual is True
    assert any(
        event.entity_contacts_changed.get(target.uuid) == contact
        for event in completed_sensory_updates(observer.uuid)
    )


def test_entity_and_object_perceivability_share_the_same_contact_shape() -> None:
    """Objects react to invisibility through the same typed-contact reducer."""
    reset_senses_state(width=5, height=1)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    marker = BaseItem(
        source_entity_uuid=uuid4(),
        name="Marker",
        is_pickable=False,
        include_in_senses_objects=True,
    )
    get_map().place_object(marker.uuid, (2, 0))

    contact = observer.senses.objects[marker.uuid]
    assert contact.position == (2, 0) and contact.visual
    marker.set_invisible(True)
    assert marker.uuid not in observer.senses.objects
    marker.set_invisible(False)
    assert observer.senses.objects[marker.uuid] == contact


def test_opaque_endpoint_is_visible_while_cells_and_content_behind_are_not() -> None:
    """An opaque object remains observable from its near side without leaking beyond it."""
    reset_senses_state(width=5, height=1)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    behind = create_test_monster(
        "monster.skeleton", name="Behind", position=(3, 0), darkvision=False,
    )
    screen = BaseItem(
        source_entity_uuid=uuid4(),
        name="Opaque screen",
        is_pickable=False,
        include_in_senses_objects=True,
        blocks_optics_field=True,
        blocks_propagation_field=False,
    )
    get_map().place_object(screen.uuid, (1, 0))

    assert observer.senses.objects[screen.uuid].visual is True
    assert (1, 0) in observer.senses.visible
    assert (2, 0) not in observer.senses.visible
    assert behind.uuid not in observer.senses.entities
    assert (2, 0) in get_map().compute_propagation_fov((0, 0), 4)


def test_each_move_step_emits_objective_and_subjective_facts_before_step_completion() -> None:
    """Every committed edge updates FOV/contacts through its spatial event lifecycle."""
    reset_senses_state(width=7, height=1)
    mover = create_test_monster(
        "monster.skeleton", name="Mover", position=(0, 0), darkvision=False,
    )
    witness = create_test_monster(
        "monster.skeleton", name="Witness", position=(5, 0), darkvision=False,
    )
    mover.materialize_navigation(max_distance=6)
    cursor = EventQueue.event_cursor()

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(2, 0),
        use_movement_cost=False,
    ).apply()

    assert result is not None and not result.canceled
    assert mover.position == (2, 0)
    recorded = [event for _, event in EventQueue.iter_events_since(cursor)]
    entered = [
        event for event in recorded
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_ENTITY_ENTERED
        and event.phase is EventPhase.COMPLETION
        and event.entity_uuid == mover.uuid
    ]
    assert [event.position for event in entered] == [(1, 0), (2, 0)]
    self_updates = [
        event for event in recorded
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == mover.uuid
        and event.update_reason is SensoryUpdateReason.SELF_MOVEMENT
    ]
    assert [event.observer_position for event in self_updates] == [(1, 0), (2, 0)]
    assert all(event.observer_position_changed for event in self_updates)
    assert witness.uuid in mover.senses.entities
    for update in self_updates:
        cause = EventQueue.get_event_by_uuid(update.cause_event_uuid)
        assert isinstance(cause, SpatialChangeEvent)
        assert cause.event_type is EventType.SPATIAL_ENTITY_ENTERED
        assert update.uuid in cause.children_events


def test_attached_light_moves_and_reduces_observers_once_per_step() -> None:
    """A carried light follows each movement edge through objective light facts."""
    reset_senses_state(width=9, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    bearer = create_test_monster(
        "monster.skeleton", name="Bearer", position=(1, 0), darkvision=False,
    )
    witness = create_test_monster(
        "monster.skeleton", name="Witness", position=(6, 0), darkvision=False,
    )
    light_uuid = grid.add_light_source(
        bearer.position,
        bright_radius_feet=5,
        dim_radius_feet=5,
        anchor_uuid=bearer.uuid,
    )
    bearer.materialize_navigation(max_distance=8)
    cursor = EventQueue.event_cursor()

    result = Move(
        source_entity_uuid=bearer.uuid,
        end_position=(3, 0),
        use_movement_cost=False,
    ).apply()

    assert result is not None and not result.canceled
    assert grid._light_sources[light_uuid].position == (3, 0)
    recorded = [event for _, event in EventQueue.iter_events_since(cursor)]
    light_completions = [
        event for event in recorded
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(light_completions) == 2
    entered_completions = [
        event for event in recorded
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_ENTITY_ENTERED
        and event.phase is EventPhase.COMPLETION
        and event.entity_uuid == bearer.uuid
    ]
    assert len(entered_completions) == 2
    for entered in entered_completions:
        light_children = [
            EventQueue.get_event_by_uuid(child_uuid)
            for child_uuid in entered.children_events
        ]
        assert any(
            isinstance(child, SpatialChangeEvent)
            and child.event_type is EventType.SPATIAL_LIGHT_CHANGED
            and child.phase is EventPhase.COMPLETION
            for child in light_children
        )
    witness_updates = [
        event for event in recorded
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == witness.uuid
        and event.update_reason is SensoryUpdateReason.LIGHT
    ]
    assert len(witness_updates) <= len(light_completions)
    assert any(event.effective_light_levels_changed for event in witness_updates)


def test_supported_deployment_emits_one_empty_to_full_delta() -> None:
    """Observer registration itself is silent; the entry fact owns initialization."""
    reset_senses_state(width=6, height=1)
    cursor = EventQueue.event_cursor()
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(1, 0), darkvision=True,
    )

    updates = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SensoryUpdateEvent)
        and event.observer_uuid == observer.uuid
    ]
    assert len(updates) == 1
    update = updates[0]
    assert update.update_reason is SensoryUpdateReason.SELF_MOVEMENT
    assert update.visible_cells_added
    assert update.passive_perception_changed
    assert update.passive_perception == observer.get_passive_perception()
    assert update.sense_modes_changed
    assert update.sense_modes == observer.senses.get_sense_modes()

    replay = Senses.create(source_entity_uuid=observer.uuid)
    replay.apply_sensory_update(update)
    assert perception_projection(replay) == perception_projection(observer.senses)


def test_event_evidence_and_combat_log_work_without_an_encounter() -> None:
    """The sensory authority freezes observers without Encounter policy setup."""
    reset_senses_state(width=8, height=1)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    actor = create_test_monster(
        "monster.skeleton", name="Actor", position=(2, 0), darkvision=False,
    )

    completion = EventQueue.publish_lifecycle(PerceptionLogEvent(
        source_entity_uuid=actor.uuid,
        source_entity_name=actor.name,
        target_entity_uuid=observer.uuid,
        target_entity_name=observer.name,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))

    assert completion is not None and completion.combat_log is not None
    actor_key = str(actor.uuid)
    assert str(observer.uuid) in completion.identified_entity_observer_uuids[actor_key]
    assert str(observer.uuid) in completion.located_entity_observer_uuids[actor_key]
    assert str(observer.uuid) in completion.combat_log.perceiver_uuids
    wire = completion.model_dump(mode="json")
    assert "identified_entity_observer_uuids" not in wire
    assert "located_entity_observer_uuids" not in wire
    assert "located_position_observer_uuids" not in wire


def test_sensory_deltas_replay_projection_without_live_queries() -> None:
    """Recorded after-value deltas rebuild the complete replay-owned projection."""
    reset_senses_state(width=7, height=1, default_light=LightLevel.DARKNESS)
    observer = create_test_monster(
        "monster.skeleton", name="Observer", position=(0, 0), darkvision=False,
    )
    get_map().add_light_source((2, 0), bright_radius_feet=10, dim_radius_feet=0)
    target = create_test_monster(
        "monster.skeleton", name="Target", position=(3, 0), darkvision=False,
    )
    observer.materialize_navigation(max_distance=6)
    result = Move(
        source_entity_uuid=observer.uuid,
        end_position=(1, 0),
        use_movement_cost=False,
    ).apply()
    assert result is not None and not result.canceled
    target.set_invisible(True)
    blinded = Blinded(
        source_entity_uuid=target.uuid,
        target_entity_uuid=observer.uuid,
    )
    blinded_result = observer.add_condition(blinded)
    assert blinded_result is not None and not blinded_result.canceled
    assert observer.senses.visual_access.normalized_score == 0
    assert any(
        event.update_reason is SensoryUpdateReason.CONDITION
        and event.visual_access_changed
        and event.visual_access == 0
        for event in completed_sensory_updates(observer.uuid)
    )

    replay = Senses.create(source_entity_uuid=observer.uuid, position=(0, 0))
    for event in completed_sensory_updates(observer.uuid):
        replay.apply_sensory_update(event)

    observer_path_revision = observer.senses.path_revision
    observer.materialize_navigation(max_distance=6)
    assert observer.senses.path_revision > observer_path_revision
    assert perception_projection(replay) == perception_projection(observer.senses)


def test_center_door_changes_movement_optics_and_propagation_together() -> None:
    """Open/close publishes one complete state change across all physical channels."""
    reset_senses_state(width=5, height=1)
    grid = get_map()
    actor = create_test_monster(
        "monster.skeleton", name="Actor", position=(0, 0), darkvision=False,
    )
    door = build_directional_door(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(
        door.uuid,
        (2, 0),
        boundary_direction=CardinalDirection.WEST,
    )
    assert not grid.can_transition((1, 0), (2, 0), actor.uuid)
    assert (3, 0) not in grid.compute_fov((0, 0), 4)
    assert (3, 0) not in grid.compute_propagation_fov((0, 0), 4)

    revisions_before_open = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    )
    cursor = EventQueue.event_cursor()
    opened = execute_use_action(actor, door.uuid, "Open Door")
    assert opened is not None and not opened.canceled
    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    ) == tuple(revision + 1 for revision in revisions_before_open)
    assert grid.can_transition((1, 0), (2, 0), actor.uuid)
    assert (3, 0) in grid.compute_fov((0, 0), 4)
    assert (3, 0) in grid.compute_propagation_fov((0, 0), 4)

    revisions_before_close = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    )
    closed = execute_use_action(actor, door.uuid, "Close Door")
    assert closed is not None and not closed.canceled
    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    ) == tuple(revision + 1 for revision in revisions_before_close)
    assert not grid.can_transition((1, 0), (2, 0), actor.uuid)
    changed = [
        event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_OBJECT_CHANGED
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == door.uuid
    ]
    assert len(changed) == 2
    assert [event.object_is_open for event in changed] == [True, False]
    assert [
        event.object_boundary_structure.blocked_channels
        for event in changed
    ] == [(), tuple(WorldEdgeChannel)]
    assert changed[0].placement == changed[1].placement


def test_redundant_opposing_boundaries_preserve_answers_revisions_and_light() -> None:
    """Removing one of two opposing blockers retains aggregate topology."""
    reset_senses_state(width=4, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    first = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    second = build_directional_wall(
        blocked_channels=tuple(WorldEdgeChannel),
    )
    grid.place_object(first.uuid, (0, 0), boundary_direction=CardinalDirection.EAST)
    grid.place_object(second.uuid, (1, 0), boundary_direction=CardinalDirection.WEST)
    light_uuid = grid.add_light_source((0, 0), bright_radius_feet=15, dim_radius_feet=0)
    answers_before = (
        grid.can_transition((0, 0), (1, 0)),
        grid.can_optical_transition((0, 0), (1, 0)),
        grid.can_propagate_transition((0, 0), (1, 0)),
    )
    revisions_before = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    )
    light_before = tuple(
        grid.get_tile(*position).resolved_light_level
        for position in ((0, 0), (1, 0), (2, 0), (3, 0))
    )
    cursor = EventQueue.event_cursor()

    try:
        grid.remove_object(first.uuid)
        assert answers_before == (False, False, False)
        assert (
            grid.can_transition((0, 0), (1, 0)),
            grid.can_optical_transition((0, 0), (1, 0)),
            grid.can_propagate_transition((0, 0), (1, 0)),
        ) == answers_before
        assert (
            grid.movement_revision,
            grid.optical_revision,
            grid.propagation_revision,
        ) == revisions_before
        assert tuple(
            grid.get_tile(*position).resolved_light_level
            for position in ((0, 0), (1, 0), (2, 0), (3, 0))
        ) == light_before

        removals = [
            (index, event)
            for index, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SpatialChangeEvent)
            and event.phase is EventPhase.COMPLETION
            and event.object_uuid == first.uuid
        ]
        assert len(removals) == 1
        assert not any(
            isinstance(event, SpatialChangeEvent)
            and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
            for _index, event in EventQueue.iter_events_since(cursor)
        )
        _index, removal = removals[0]
        assert removal.change_type is SpatialChangeType.OBJECT_REMOVED
        assert removal.placement is None
        assert removal.object_boundary_structure is None
        assert removal.previous_placement is not None
        assert removal.senses_hint is not None
        assert removal.senses_hint.directional_positions == {(0, 0)}
        assert removal.senses_hint.directional_neighbors == {(1, 0)}
        assert removal.senses_hint.directional_channels_changed is None
        assert not removal.senses_hint.requires_fov
        assert not removal.senses_hint.requires_paths
        assert not removal.senses_hint.requires_light_recompute
        assert not removal.senses_hint.requires_propagation_recompute
    finally:
        grid.remove_object(second.uuid)
        grid.remove_light_source(light_uuid)


def test_boundary_optical_light_settlement_is_a_child_before_object_completion() -> None:
    """An optical boundary publishes causal light facts before its completion."""
    reset_senses_state(width=5, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    grid.add_light_source((0, 0), bright_radius_feet=15, dim_radius_feet=0)
    wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.OPTICAL,),
    )
    cursor = EventQueue.event_cursor()

    grid.place_object(
        wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )

    recorded = list(EventQueue.iter_events_since(cursor))
    object_completions = [
        (index, event)
        for index, event in recorded
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_OBJECT_PLACED
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == wall.uuid
    ]
    assert len(object_completions) == 1
    completion_index, completion = object_completions[0]
    light_children = [
        (index, event)
        for index, event in recorded
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
        and event.phase is EventPhase.COMPLETION
    ]
    child_uuids = set(completion.lineage_children_events)
    assert light_children
    assert any(
        event.uuid in child_uuids and index < completion_index
        for index, event in light_children
    )
    assert grid.get_tile(2, 0).resolved_light_level is LightLevel.DARKNESS


def test_local_spatial_change_selects_only_subscribed_observers() -> None:
    """A local event does not eagerly recompute distant registered observers."""
    reset_senses_state(width=60, height=1)
    local = create_test_monster(
        "monster.skeleton", name="Local", position=(0, 0), darkvision=False,
    )
    mover = create_test_monster(
        "monster.skeleton", name="Mover", position=(2, 0), darkvision=False,
    )
    distant = create_test_monster(
        "monster.skeleton", name="Distant", position=(50, 0), darkvision=False,
    )
    distant_before = capture_senses_snapshot(distant.senses)
    mover.move((3, 0))

    assert mover.get_position() == (3, 0)
    assert local.get_position() == (0, 0)
    assert capture_senses_snapshot(distant.senses) == distant_before


def test_fixed_radius_optical_query_is_independent_of_total_map_size() -> None:
    """Fixed-radius FOV returns the same local result on different map sizes."""
    results: list[tuple[tuple[int, int], ...]] = []
    for size in (41, 101):
        reset_senses_state(width=size, height=size)
        grid = get_map()
        origin = (size // 2, size // 2)
        first = tuple(sorted(grid.compute_fov(origin, max_distance=10)))
        second = tuple(sorted(grid.compute_fov(origin, max_distance=10)))
        assert first == second
        results.append(first)

    assert len(results[0]) == len(results[1])


@pytest.mark.parametrize("size", [41, 101])
@pytest.mark.parametrize("distant_blockers", [0, 1, 20])
def test_cold_directional_preflight_is_bounded_to_the_query_region(
    size: int,
    distant_blockers: int,
) -> None:
    """Distant boundary providers cannot change fixed-radius sight."""
    reset_senses_state(width=size, height=size)
    grid = get_map()
    origin = (size // 2, size // 2)
    baseline = set(grid.compute_fov(origin, max_distance=10))
    for offset in range(distant_blockers):
        position = (offset % size, 0)
        wall = build_directional_wall(
            blocked_channels=(WorldEdgeChannel.OPTICAL,),
        )
        grid.place_object(
            wall.uuid,
            position,
            boundary_direction=CardinalDirection.EAST,
        )

    assert set(grid.compute_fov(origin, max_distance=10)) == baseline


def test_optical_change_recomputes_only_light_sources_within_radius(
) -> None:
    """A local optical boundary changes nearby light, not a distant source."""
    reset_senses_state(width=80, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    grid.add_light_source(
        (10, 0), bright_radius_feet=10, dim_radius_feet=0,
    )
    grid.add_light_source(
        (70, 0), bright_radius_feet=10, dim_radius_feet=0,
    )
    near_tile = grid.get_tile(12, 0)
    far_tile = grid.get_tile(72, 0)
    assert near_tile is not None and far_tile is not None
    near_before = near_tile.resolved_light_level
    far_before = far_tile.resolved_light_level
    optical_revision = grid.optical_revision

    wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.OPTICAL,),
    )
    grid.place_object(
        wall.uuid,
        (11, 0),
        boundary_direction=CardinalDirection.EAST,
    )

    assert grid.optical_revision > optical_revision
    assert near_tile.resolved_light_level is not near_before
    assert far_tile.resolved_light_level is far_before


def test_single_boundary_removal_bumps_only_its_authored_channel_once() -> None:
    """Removing one optical boundary changes only the aggregate optical revision."""
    reset_senses_state(width=4, height=1)
    grid = get_map()
    wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.OPTICAL,),
    )
    grid.place_object(wall.uuid, (1, 0), boundary_direction=CardinalDirection.EAST)
    revisions_before_remove = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    )

    grid.remove_object(wall.uuid)

    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    ) == (
        revisions_before_remove[0],
        revisions_before_remove[1] + 1,
        revisions_before_remove[2],
    )


def test_optical_and_propagation_caches_invalidate_only_their_channels() -> None:
    """Lazy revision caches remain independent after the unification cut."""
    reset_senses_state(width=8, height=2)
    grid = get_map()
    first_optical = grid.compute_fov((0, 0), 7)
    first_propagation = grid.compute_propagation_fov((0, 0), 7)
    optical_revision = grid.optical_revision
    propagation_revision = grid.propagation_revision

    optical_wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.OPTICAL,),
    )
    grid.place_object(
        optical_wall.uuid,
        (3, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    assert grid.optical_revision == optical_revision + 1
    assert grid.propagation_revision == propagation_revision
    assert grid.compute_fov((0, 0), 7) != first_optical
    assert grid.compute_propagation_fov((0, 0), 7) == first_propagation

    optical_revision = grid.optical_revision
    propagation_wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.PROPAGATION,),
    )
    grid.place_object(
        propagation_wall.uuid,
        (3, 0),
        boundary_direction=CardinalDirection.NORTH,
    )
    assert grid.optical_revision == optical_revision
    assert grid.propagation_revision == propagation_revision + 1
    assert not grid.can_propagate_transition((3, 0), (3, 1))
