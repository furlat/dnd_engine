"""Executable contract for unified optics, illumination, and perception."""

from time import perf_counter
from uuid import UUID, uuid4

import pytest

from dnd.actions.standard import Move
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
from dnd.core.base_tiles import Tile
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.events.events_registry import Event, EventPhase, EventQueue, EventType
from dnd.core.events.world_events import (
    SensoryUpdateEvent,
    SensoryUpdateReason,
    SpatialChangeEvent,
)
from dnd.core.gridmap import get_map
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_interactables import CloseDoorAction, DoorObject, OpenDoorAction
from dnd.spells.conjuration import DarknessZone, FogCloudZone
from dnd.types.senses import OpticalObscurement, SenseMode, SensesType
from dnd.types.world import LightLevel
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
    grid.create_rectangle(0, 0, width, height)
    if default_light is not LightLevel.BRIGHT_LIGHT:
        for position in grid.get_all_tiles():
            grid.set_tile_base_light(position, default_light)
    grid.enable_events(flush_pending=False)


def completed_sensory_updates(observer_uuid: UUID) -> list[SensoryUpdateEvent]:
    """Return recorded completion deltas for one observer."""
    return [
        event
        for event in EventQueue._all_events
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
    door = DirectionalDoor(source_entity_uuid=uuid4())
    get_map().place_object(door.uuid, (1, 0))

    assert door.uuid not in observer.senses.objects


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
    grid.set_tile_directional_border((1, 0), "optical", "east", False)

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

    observer.materialize_navigation(max_distance=6)
    assert observer.senses._paths_dirty is False
    assert replay._paths_dirty is True
    assert perception_projection(replay) == perception_projection(observer.senses)


def test_center_door_changes_movement_optics_and_propagation_together() -> None:
    """Open/close publishes one complete state change across all physical channels."""
    reset_senses_state(width=5, height=1)
    grid = get_map()
    actor = create_test_monster(
        "monster.skeleton", name="Actor", position=(0, 0), darkvision=False,
    )
    door = DoorObject(source_entity_uuid=actor.uuid)
    grid.place_object(door.uuid, (2, 0))
    assert not grid.can_transition((1, 0), (2, 0), actor.uuid)
    assert (3, 0) not in grid.compute_fov((0, 0), 4)
    assert (3, 0) not in grid.compute_propagation_fov((0, 0), 4)

    opened = OpenDoorAction(
        source_entity_uuid=actor.uuid,
        source_item_uuid=door.uuid,
    ).apply()
    assert opened is not None and not opened.canceled
    assert grid.can_transition((1, 0), (2, 0), actor.uuid)
    assert (3, 0) in grid.compute_fov((0, 0), 4)
    assert (3, 0) in grid.compute_propagation_fov((0, 0), 4)

    closed = CloseDoorAction(
        source_entity_uuid=actor.uuid,
        source_item_uuid=door.uuid,
    ).apply()
    assert closed is not None and not closed.canceled
    assert not grid.can_transition((1, 0), (2, 0), actor.uuid)
    changed = [
        event for event in EventQueue._all_events
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_OBJECT_CHANGED
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == door.uuid
    ]
    assert len(changed) == 2
    assert changed[-1].object_blocks_optics is True
    assert changed[-1].object_blocks_propagation is True


def test_local_spatial_change_selects_only_subscribed_observers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    calls: list[UUID] = []
    original = spatial_senses_system.recompute_observer

    def track(observer_uuid: UUID, *, max_distance: int = 20) -> None:
        calls.append(observer_uuid)
        original(observer_uuid, max_distance=max_distance)

    monkeypatch.setattr(spatial_senses_system, "recompute_observer", track)
    mover.move((3, 0))

    assert local.uuid in calls
    assert mover.uuid in calls
    assert distant.uuid not in calls


def test_fixed_radius_optical_query_cost_is_independent_of_total_map_size() -> None:
    """Cold fixed-radius FOV scales with queried space, not total stored Tiles."""
    timings: list[float] = []
    result_sizes: list[int] = []
    for size in (41, 101):
        reset_senses_state(width=size, height=size)
        grid = get_map()
        origin = (size // 2, size // 2)
        samples: list[float] = []
        for _ in range(5):
            grid._fov_cache.clear()
            started = perf_counter()
            positions = grid.compute_fov(origin, max_distance=10)
            samples.append(perf_counter() - started)
        timings.append(min(samples))
        result_sizes.append(len(positions))

    assert result_sizes[0] == result_sizes[1]
    assert timings[1] <= timings[0] * 5 + 0.01


@pytest.mark.parametrize("size", [41, 101])
@pytest.mark.parametrize("distant_blockers", [0, 1, 20])
def test_cold_directional_preflight_is_bounded_to_the_query_region(
    size: int,
    distant_blockers: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Distant directional structure cannot add work to fixed-radius sight."""
    reset_senses_state(width=size, height=size)
    grid = get_map()
    origin = (size // 2, size // 2)
    for offset in range(distant_blockers):
        position = (offset % size, 0)
        grid.set_tile_directional_border(position, "optical", "east", False)

    calls = 0
    original = Tile.allows_direction

    def count_calls(self: Tile, direction: str, channel: str = "movement", *, include_derived: bool = True) -> bool:
        nonlocal calls
        calls += 1
        return original(
            self,
            direction,
            channel,
            include_derived=include_derived,
        )

    monkeypatch.setattr(Tile, "allows_direction", count_calls)
    grid._fov_cache.clear()
    grid.compute_fov(origin, max_distance=10)

    assert calls <= 4 * 441


def test_optical_change_recomputes_only_light_sources_within_radius(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The active-source scan does expensive FOV work only for local lights."""
    reset_senses_state(width=80, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    near_uuid = grid.add_light_source(
        (10, 0), bright_radius_feet=10, dim_radius_feet=0,
    )
    grid.add_light_source(
        (70, 0), bright_radius_feet=10, dim_radius_feet=0,
    )
    recomputed: list[UUID] = []
    original = grid._compute_light_tiles

    def track(source, position=None):
        recomputed.append(source.uuid)
        return original(source, position)

    monkeypatch.setattr(grid, "_compute_light_tiles", track)
    grid.set_tile_directional_border((11, 0), "optical", "east", False)

    assert recomputed == [near_uuid]


def test_optical_and_propagation_caches_invalidate_only_their_channels() -> None:
    """Lazy revision caches remain independent after the unification cut."""
    reset_senses_state(width=8, height=2)
    grid = get_map()
    first_optical = grid.compute_fov((0, 0), 7)
    first_propagation = grid.compute_propagation_fov((0, 0), 7)
    optical_revision = grid.optical_revision
    propagation_revision = grid.propagation_revision

    grid.set_tile_directional_border((3, 0), "optical", "east", False)
    assert grid.optical_revision > optical_revision
    assert grid.propagation_revision == propagation_revision
    assert grid.compute_fov((0, 0), 7) != first_optical
    assert grid.compute_propagation_fov((0, 0), 7) == first_propagation

    optical_revision = grid.optical_revision
    grid.set_tile_directional_border((3, 0), "propagation", "east", False)
    assert grid.optical_revision == optical_revision
    assert grid.propagation_revision > propagation_revision
    assert grid.compute_propagation_fov((0, 0), 7) != first_propagation
