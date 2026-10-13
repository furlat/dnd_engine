"""Rejected pack support edits cannot leak into the next native world."""

from uuid import uuid4

import pytest

from dnd.content_system.pack_loader import load_content_system
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.items.environment import DirectionalWall
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection, WorldEdgeChannel


@pytest.mark.parametrize("import_failure", [False, True])
def test_rejected_pack_tile_edits_roll_back_before_clean_world_retry(tmp_path, import_failure):
    reset_engine_runtime()
    GridMap.reset()
    EventQueue.reset()
    try:
        pack = tmp_path / "packs" / "grid_rollback"
        package = pack / "src" / "fixture_grid_rollback"
        package.mkdir(parents=True)
        (pack / "content-pack.toml").write_text(
            'schema_version = 1\npack_id = "fixture.grid_rollback"\n'
            'pack_version = "1.0.0"\nengine_content_api = 2\n'
            'python_root = "src"\npython_package = "fixture_grid_rollback"\n',
            encoding="utf-8")
        module = package / "__init__.py"
        module.write_text(
            "from dnd.core.gridmap import get_map\n"
            "grid = get_map()\n"
            "grid.set_tile(0, -17, fire_event=False)\n"
            "grid.create_rectangle(0, -17, 1, 3)\n"
            "grid.remove_tile(0, -16, fire_event=False)\n"
            + ("raise RuntimeError('fixture import failed')\n" if import_failure else ""),
            encoding="utf-8")
        expected = "fixture import failed" if import_failure else "mutated engine runtime state"
        with pytest.raises(RuntimeError, match=expected):
            load_content_system(pack_roots=(pack.parent,))
        module.write_text("PACK_READY = True\n", encoding="utf-8")
        loaded = load_content_system(pack_roots=(pack.parent,))
        assert tuple(row.manifest.pack_id for row in loaded.packs) == ("fixture.grid_rollback",)
        grid = get_map()
        assert grid.get_all_tiles() == {}
        grid.set_tile(0, 0)
        wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.rollback_wall",
            blocked_channels=(WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION))
        wall.place_on_grid((0, 0), boundary_direction=CardinalDirection.EAST)
        assert grid.compute_fov((0, 0), 20) == [(0, 0)]
        assert grid.compute_propagation_fov((0, 0), 20) == [(0, 0)]
    finally:
        reset_engine_runtime()
        GridMap.reset()
        EventQueue.reset()
