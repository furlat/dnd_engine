"""The furnished gallery is reachable through native doors and public world state."""

from collections import deque

from dnd.core.events import EventQueue, WorldInitializedEvent
from dnd.core.gridmap import get_map
from dnd.items.environment import DirectionalDoor
from dnd.items.torches import WallTorch
from dnd.player.session import close_session, create_authored_session
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.scenarios.encounter_catalog import encounter_recipe


def test_gallery_publishes_supported_furniture_lights_and_connected_aisles() -> None:
    reset_engine_runtime()
    try:
        built = build_battlefield("battlefield.lantern_gallery")
        grid = get_map()
        world = next(event for _, event in EventQueue.iter_events_since(0)
                     if isinstance(event, WorldInitializedEvent))
        tiles = {tile.position: tile for tile in world.tiles}
        room = {(x, y) for x in range(24, 72) for y in range(2, 38)}
        assert room <= tiles.keys()
        assert (built.definition.width, built.definition.height) == (73, 39)
        assert all(0 <= x < built.definition.width and 0 <= y < built.definition.height
                   for x, y in tiles)
        for key, position in {"entry": (3, 5), "passage": (8, 6), "burial_hall": (12, 6),
                              "gallery_entry": (26, 6), "gallery_centre": (46, 20),
                              "gallery_far": (68, 20), "gallery_guardian": (68, 33)}.items():
            assert built.notable_positions[key] == position
        for row in world.objects:
            assert all(support.position in tiles and support.tile_uuid == tiles[support.position].tile_uuid
                       for support in row.placement.covered_supports)
        published = world.model_dump(mode="json")
        assert len(published["tiles"]) == len(tiles)
        assert len(published["objects"]) == len(grid.iter_object_placements())
        for key, identity in built.object_uuids.items():
            if key.startswith("gallery_torch_"):
                torch = WallTorch.get(identity)
                assert isinstance(torch, WallTorch) and torch.is_lit
                assert len(torch.get_attached_light_sources()) == 1
        for key, position in {"bed": (2, 7), "desk": (2, 4), "statue_north": (16, 3),
                              "statue_south": (16, 9), "hall_table": (19, 5)}.items():
            assert grid.get_object_placement(built.object_uuids[key]).position == position
        for source, destination in (((20, 6), (21, 6)), ((23, 6), (24, 6))):
            assert not grid.can_transition(source, destination)
        for key in ("passage_door", "hall_door", "gallery_passage_door", "gallery_door"):
            door = DirectionalDoor.get(built.object_uuids[key])
            assert isinstance(door, DirectionalDoor)
            door.open()
        visited = {(3, 5)}
        pending = deque(visited)
        while pending:
            source = pending.popleft()
            for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                destination = (source[0] + dx, source[1] + dy)
                if destination in tiles and destination not in visited and grid.can_transition(source, destination):
                    visited.add(destination)
                    pending.append(destination)
        assert {position for position in room if grid.is_walkable(*position)} <= visited
        assert all(built.notable_positions[key] in visited for key in
                   ("gallery_entry", "gallery_nave", "gallery_centre", "gallery_far", "gallery_guardian"))
    finally:
        reset_engine_runtime()


def test_gallery_encounter_retains_original_cast_and_one_distant_guardian() -> None:
    recipe = encounter_recipe("encounter.lantern_gallery")
    original = encounter_recipe("encounter.lantern_crypt")
    assert recipe.roster_slots[0] == original.roster_slots[0]
    assert recipe.roster_slots[1].roster.members[:2] == original.roster_slots[1].roster.members
    assert len(recipe.roster_slots[1].roster.members) == 3
    assert recipe.deployment.zones[0] == original.deployment.zones[0]
    assert recipe.deployment.zones[1].ordered_slots == ((16, 5), (18, 7), (68, 33))
    reset_engine_runtime()
    session = None
    try:
        session = create_authored_session(recipe)
        assert len(session.encounter.combatants) == 5
        assert {combatant.entity.position for combatant in session.encounter.combatants.values()} == {
            (3, 5), (4, 5), (16, 5), (18, 7), (68, 33)}
    finally:
        if session is not None:
            close_session(session)
        reset_engine_runtime()
