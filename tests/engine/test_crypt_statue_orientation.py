"""Crypt statues disclose persistent facings toward the burial hall centre."""

from dnd.core.events import EventQueue, WorldInitializedEvent
from dnd.core.gridmap import get_map
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.world import CardinalDirection


def test_crypt_statues_publish_inward_world_facings() -> None:
    reset_engine_runtime()
    try:
        built = build_battlefield("battlefield.lantern_crypt")
        world = next(event for _, event in EventQueue.iter_events_since(0)
                     if isinstance(event, WorldInitializedEvent))
        disclosed = {row.placement.object_uuid: row.model_dump(mode="json")
                     for row in world.objects}
        for key, position, direction in (
            ("statue_north", (16, 3), CardinalDirection.NORTH),
            ("statue_south", (16, 9), CardinalDirection.SOUTH),
        ):
            identity = built.object_uuids[key]
            placement = get_map().get_object_placement(identity)
            assert placement is not None
            assert (placement.position, placement.orientation) == (position, direction)
            assert disclosed[identity]["placement"]["orientation"] == direction.value
    finally:
        reset_engine_runtime()
