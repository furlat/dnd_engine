"""Tile-owned duration and encounter environment-step regressions."""
from dnd.types.materials import Material, TileSurface

from uuid import uuid4

from dnd.blocks.base_item import BaseItem
from dnd.content.spatial_effect_materialization import materialize_spatial_condition
from dnd.content.spatial_effect_recipes import DAYLIGHT_FIELD_RECIPE
from dnd.core.base_conditions import BaseCondition, ConditionRemovalEvent, Duration
from dnd.core.events.events_registry import Event, EventPhase, EventQueue, EventType
from dnd.types.conditions import DurationType
from dnd.core.gridmap import get_map
from dnd.entities.entity import Entity
from dnd.spatial.area_conditions import SpatialCondition
from tests.engine.support import create_test_monster
from tests.engine.support import reset_combat_state, setup_combat_arena


class TileDurationProbe(BaseCondition):
    name: str = "Tile Duration Probe"


class EntityDurationProbe(BaseCondition):
    name: str = "Entity Duration Probe"


def _duration(rounds: int, source_uuid, target_uuid) -> Duration:
    return Duration(
        duration=rounds,
        duration_type=DurationType.ROUNDS,
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
    )


def test_tile_duration_expiry_removes_owned_cross_block_effect() -> None:
    """Tiles use BaseBlock duration and linked-condition cleanup unchanged."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 8, 8, surface=TileSurface(base_material=Material.STONE))
    target = create_test_monster("monster.skeleton",
        name="Tile Duration Target",
        position=(3, 3),
    )
    tile = grid.get_tile(3, 3)
    assert tile is not None
    source_uuid = uuid4()
    tile_effect = TileDurationProbe(
        source_entity_uuid=source_uuid,
        target_entity_uuid=tile.uuid,
        duration=_duration(2, source_uuid, tile.uuid),
    )
    target_effect = EntityDurationProbe(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target.uuid,
    )
    tile.add_condition(tile_effect)
    target.add_condition(target_effect)
    tile_effect.add_linked_condition(target.uuid, target_effect.uuid)

    assert not tile.advance_duration(tile_effect.name)
    assert tile_effect.name in tile.active_conditions
    assert target_effect.name in target.active_conditions

    assert tile.advance_duration(tile_effect.name)
    assert tile_effect.name not in tile.active_conditions
    assert target_effect.name not in target.active_conditions


def test_encounter_round_boundary_advances_tile_durations() -> None:
    """RoundEnd owns environment expiry and closes after every removal child."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 8, 8, surface=TileSurface(base_material=Material.STONE))
    first = create_test_monster("monster.skeleton",
        name="Tile Duration First",
        position=(0, 0),
        faction="first",
    )
    second = create_test_monster("monster.skeleton",
        name="Tile Duration Second",
        position=(1, 0),
        faction="second",
    )
    Entity.materialize_all_navigation()
    encounter = setup_combat_arena(first, second)
    tile = grid.get_tile(5, 5)
    assert tile is not None
    source_uuid = uuid4()
    tile_effect = TileDurationProbe(
        source_entity_uuid=source_uuid,
        target_entity_uuid=tile.uuid,
        duration=_duration(2, source_uuid, tile.uuid),
    )
    target_effect = EntityDurationProbe(
        source_entity_uuid=source_uuid,
        target_entity_uuid=first.uuid,
    )
    placed_item = BaseItem(
        source_entity_uuid=source_uuid,
        name="Round Duration Placed Object",
    )
    placed_effect = EntityDurationProbe(
        name="Placed Object Duration Probe",
        source_entity_uuid=source_uuid,
        target_entity_uuid=placed_item.uuid,
        duration=_duration(2, source_uuid, placed_item.uuid),
    )
    tile.add_condition(tile_effect)
    first.add_condition(target_effect)
    tile_effect.add_linked_condition(first.uuid, target_effect.uuid)
    placed_item.add_condition(placed_effect)
    placed_item.place_on_grid((6, 6))

    spatial_effect = materialize_spatial_condition(
        DAYLIGHT_FIELD_RECIPE,
        source_uuid,
        position=(7, 7),
        faction="round-duration-test",
        condition_type=SpatialCondition,
        condition_fields={
            "affected_positions": {(7, 7)},
            "duration": _duration(2, source_uuid, source_uuid),
        },
    )
    activation = EventQueue.publish_declaration(Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    activation = activation.phase_to(EventPhase.EXECUTION)
    activation_effect = activation.phase_to(EventPhase.EFFECT)
    spatial_effect.activate(parent_event=activation_effect)
    activation_effect.phase_to(EventPhase.COMPLETION)
    encounter.start_encounter()

    encounter.start_turn()
    encounter.end_turn()
    encounter.next_turn()
    encounter.end_turn()
    encounter.next_turn()

    assert tile_effect.name in tile.active_conditions
    assert target_effect.name in first.active_conditions
    assert placed_effect.name in placed_item.active_conditions
    assert spatial_effect in grid.get_spatial_conditions()

    second_round_cursor = EventQueue.event_cursor()
    encounter.end_turn()
    encounter.next_turn()
    encounter.end_turn()
    encounter.next_turn()

    assert tile_effect.name not in tile.active_conditions
    assert target_effect.name not in first.active_conditions
    assert placed_effect.name not in placed_item.active_conditions
    assert spatial_effect not in grid.get_spatial_conditions()

    events = [
        event
        for _, event in EventQueue.iter_events_since(second_round_cursor)
    ]
    round_end_events = [
        event for event in events if event.event_type is EventType.ROUND_END
    ]
    assert [event.phase for event in round_end_events] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    round_effect = round_end_events[2]
    round_terminal = round_end_events[3]
    removals = [
        event for event in events if isinstance(event, ConditionRemovalEvent)
    ]
    assert removals
    completed_removal_owners = {
        event.condition.uuid
        for event in removals
        if event.phase is EventPhase.COMPLETION
    }
    assert {
        tile_effect.uuid,
        target_effect.uuid,
        placed_effect.uuid,
        spatial_effect.uuid,
    } <= completed_removal_owners

    def reaches_round_effect(event: Event) -> bool:
        current = event
        visited = set()
        while current.parent_event is not None:
            assert current.uuid not in visited
            visited.add(current.uuid)
            parent = EventQueue.get_event_by_uuid(current.parent_event)
            assert parent is not None
            if parent.uuid == round_effect.uuid:
                return True
            current = parent
        return False

    assert all(reaches_round_effect(event) for event in removals)
    terminal_index = EventQueue.get_event_index(round_terminal.uuid)
    assert terminal_index is not None
    assert all(
        EventQueue.get_event_index(event.uuid) < terminal_index
        for event in removals
    )
    next_round_start_index = next(
        index
        for index, event in enumerate(events)
        if event.event_type is EventType.ROUND_START
    )
    assert events.index(round_terminal) < next_round_start_index
