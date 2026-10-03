"""Explicit archived recipe inputs on the current admitted asset set."""

from dataclasses import replace

from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_types import AnimationData, StudioDraftFile
from game.authoring_conversion import explicit_attachments, explicit_composition
from game.world_binding_types import WorldBindingsSource, TerrainCliffSource, TerrainStairSource


def recorded_recipe_data() -> AnimationData:
    """Keep the offline oracle's input recipes, not an obsolete installation."""
    data = load_animation_data()
    source = StudioDraftFile.model_validate_json(
        (DATA_ROOT / "spell-studio-drafts.materialized.json").read_text())
    drafts = {
        row.definitionRef.content_id: explicit_composition(
            explicit_attachments(row, data.projectile_assets), data.projectile_storage)
        for row in source.spells
    }
    return replace(data, drafts={**data.drafts, **drafts})


def recipe_only_world() -> WorldBindingsSource:
    """An explicit empty scene for isolated file-version conversion tests."""
    return WorldBindingsSource(
        schema_version=1, terrain={},
        terrain_cliff=TerrainCliffSource(role="cliff", rise_steps=1, bed_material="stone",
            upper_support_offset=(0, 0), straight={}, corner={}, corner_faces={}),
        terrain_stairs=TerrainStairSource(role="stairs", rise_steps=1,
            support_offsets=(), poses={}, contacts_px={}),
        stone_wall_straight={}, stone_wall_corner={}, wood_wall_straight={},
        wood_wall_corner={}, stone_door_frame={}, wood_door_closed={},
        wood_door_open={}, props={}, treatments={},
    )
