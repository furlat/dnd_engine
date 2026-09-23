"""Cold furniture records its initial body before ordinary owned dynamics."""

from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from dnd.actor_projection import condition_fact
from dnd.blocks.base_item import BaseItem
from dnd.content.items.world_prop_builders import WORLD_PROP_PROFILES, build_world_prop, settle_world_prop
from dnd.core.base_block import BaseBlock
from dnd.core.content.battlefields import BattlefieldDefinition
from dnd.core.creature_types import DamageType
from dnd.core.events import EventPhase, EventQueue, ItemDestructionEvent, SpatialChangeEvent, WorldInitializedEvent
from dnd.core.gridmap import GridMap, get_map
from dnd.core.item_types import ItemIntegrity
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios import battlefield_catalog
from dnd.types.actor_facts import ConditionFact
from dnd.types.world import MovementMode
from dnd.world_facts import WorldFacts, apply_world_fact
from game.event_record import RecordedEvent
from game.presentation import _retained_event


ROWS = TypeAdapter(list[tuple[RecordedEvent, ConditionFact | None]])


@pytest.mark.parametrize("initial", (ItemIntegrity.INTACT, ItemIntegrity.DESTROYED))
@pytest.mark.parametrize("item_id", ("environment.furniture.bed", "environment.furniture.wardrobe"))
def test_cold_furniture_publishes_birth_then_owned_dynamics_and_replays_after_reset(
    monkeypatch: pytest.MonkeyPatch, initial: ItemIntegrity, item_id: str,
) -> None:
    reset_engine_runtime()
    profile = WORLD_PROP_PROFILES[item_id]

    def authored_room(definition: BattlefieldDefinition, grid: GridMap) -> battlefield_catalog.BuiltBattlefield:
        grid.create_rectangle(0, 0, definition.width, definition.height)
        bed = build_world_prop(item_id, integrity=initial, defer_behaviors=True)
        bed.place_on_grid((3, 3))
        assert EventQueue.event_cursor() == 0
        assert not get_map().get_spatial_conditions()
        return battlefield_catalog.BuiltBattlefield(definition, None, {}, {"bed": bed.uuid})

    # Select one authored content fixture; all construction, settlement,
    # destruction and recording still run through the real engine.
    monkeypatch.setitem(battlefield_catalog._BUILDERS, "battlefield.open_floor_bright", authored_room)
    built = battlefield_catalog.build_battlefield("battlefield.open_floor_bright")
    bed = BaseBlock.get(built.object_uuids["bed"])
    assert isinstance(bed, BaseItem)
    bed_uuid = bed.uuid
    events = tuple(event for _, event in EventQueue.iter_events_since(0))
    world = events[0]
    assert isinstance(world, WorldInitializedEvent) and world.phase is EventPhase.COMPLETION
    assert sum(isinstance(event, WorldInitializedEvent) for event in events) == 1
    body, = world.objects
    assert body.item.item_uuid == bed_uuid and body.item.integrity is initial
    assert body.item.current_hit_points == (0 if initial is ItemIntegrity.DESTROYED else profile.hit_points)
    assert body.placement.positions == tuple((3 + x, 3 + y) for x, y in profile.footprint_offsets)
    assert body.placement.top_height_steps - body.placement.base_height_steps == (
        1 if initial is ItemIntegrity.DESTROYED else profile.vertical_extent_steps)
    assert all(tile.walking_cost == 1 for tile in world.tiles)
    assert not any(isinstance(event, (SpatialChangeEvent, ItemDestructionEvent))
                   and (isinstance(event, ItemDestructionEvent) or event.object_uuid == bed_uuid)
                   for event in events)
    by_uuid = {event.uuid: event for event in events}
    for event in events[1:]:
        parent = event.parent_event
        while parent is not None and parent != world.uuid:
            parent = by_uuid[parent].parent_event
        assert parent == world.uuid

    cursor = EventQueue.event_cursor()
    settle_world_prop(bed, world)
    assert EventQueue.event_cursor() == cursor  # Re-settling cannot double terrain.
    if initial is ItemIntegrity.INTACT:
        assert not get_map().get_spatial_conditions()
        bed.receive_damage(profile.hit_points, DamageType.BLUDGEONING, bed.uuid)
    assert bed.integrity is ItemIntegrity.DESTROYED and bed.get_hp() == 0
    assert len(get_map().get_spatial_conditions()) == 1
    assert all(tile.get_movement_cost(MovementMode.WALKING) == 2
               for point, tile in get_map().get_all_tiles().items() if point in body.placement.positions)

    observer = uuid4()
    snapshots: list[tuple[bytes, bool, int]] = []
    for dispose in (False, True):
        if dispose:
            bed.retire()
        snapshots.append((ROWS.dump_json([
            (_retained_event(event, observer), condition_fact(event, source_index=index))
            for index, event in EventQueue.iter_events_since(0)
        ]), not dispose, 1 if dispose else 2))

    reset_engine_runtime()
    for blob, retained, cost in snapshots:
        facts = WorldFacts()
        for event, condition in ROWS.validate_json(blob):
            if event.phase is EventPhase.COMPLETION and not event.canceled:
                apply_world_fact(facts, event, condition)
        assert (bed_uuid in facts.objects) is retained
        if retained:
            assert facts.objects[bed_uuid].item.integrity is ItemIntegrity.DESTROYED
            assert facts.objects[bed_uuid].item.current_hit_points == 0
        assert all(facts.tiles[point].walking_cost == cost for point in body.placement.positions)
    assert EventQueue.event_cursor() == 0 and not get_map().get_all_tiles()
