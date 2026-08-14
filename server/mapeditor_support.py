"""Mapeditor support functions.

This module keeps the experimental map editor API grounded in the existing
GridMap, Tile, BaseItem, and light-source contracts. It intentionally avoids
combat entities and subjective visibility.
"""

import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Tuple
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import (
    materialize_item,
    resolve_item_recipe,
)
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.base_actions import BaseAction
from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.base_object import BaseObject
from dnd.core.base_tiles import (
    Tile,
    difficult_terrain_factory,
    validate_elevation_surface_tuple,
    wall_factory,
    water_factory,
)
from dnd.core.content.descriptors import (
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.traversal_connectors import (
    TraversalConnector,
    TraversalConnectorChangeOperation,
)
from dnd.core.content.item_definitions import ItemPersistencePolicy
from dnd.core.content.recipe_presets import ContentRecipePresetRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration
from dnd.core.gridmap import get_map
from dnd.core.values import BaseValue
from dnd.core.world_edges import (
    ElevationSurfaceKind,
    contradictory_progressive_elevation_edge,
)
from dnd.environmental_effect_runtime import (
    extend_spike_trap_effect,
    materialize_spike_trap_effect,
)
from dnd.environmental_effects import SpikeTrapGroundEffect
from dnd.items.environment_content import TRAP_LEVER_DECLARATION
from dnd.items.environment import DirectionalDoor
from dnd.items.environment_interactables import (
    PullLeverAction,
    DoorObject,
    TrapLever,
)
from dnd.items.torches import WallTorch
from dnd.maps.arena_layout import build_standard_arena_environment
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial_effect_content import SPIKE_TRAP_EFFECT_DECLARATION
from dnd.spatial_effects import SpatialEffect
from server.api_models import (
    MapEditorCatalog,
    MapEditorCatalogEntry,
    MapEditorContentCatalogEntry,
    MapEditorCreateMapRequest,
    MapEditorConnectorDeleteRequest,
    MapEditorConnectorEnabledRequest,
    MapEditorConnectorMutationResponse,
    MapEditorConnectorUpsertRequest,
    MapEditorGridBounds,
    MapEditorLightCell,
    MapEditorLightResponse,
    MapEditorMapSnapshot,
    MapEditorObjectDeleteRequest,
    MapEditorObjectPlaceRequest,
    MapEditorObjectRuntimeState,
    MapEditorSaveMapRequest,
    MapEditorSavedMapDocument,
    MapEditorSavedMapList,
    MapEditorSavedMapMetadata,
    MapEditorSavedObjectPlacement,
    MapEditorTilePatch,
    MapEditorVisibilityCell,
    MapEditorVisibilityResponse,
    MapEditorWalkabilityCell,
    MapEditorWalkabilityResponse,
)
from server.event_stream import event_stream
from server.session import SessionManager
from server.world_contracts import (
    APIFloorObject,
    APISpatialEffectSummary,
    APITile,
)
from server.world_projection import project_grid

logger = logging.getLogger(__name__)

_BASE_BLOCK_FIELDS = set(BaseBlock.model_fields.keys()) | {
    "use_register",
    "blocks_dict_name_uuid",
    "blocks_dict_uuid_name",
    "values_dict_name_uuid",
    "values_dict_uuid_name",
}
_ALREADY_SERIALIZED = {"uuid", "name", "map_char"}
_SAVE_SCHEMA_VERSION = 3


def reset_editor_world() -> None:
    """Reset spatial/combat registries for an entity-free editor map."""
    reset_engine_runtime()
    SessionManager.reset()
    event_stream.ensure_attached()


def create_editor_map(request: MapEditorCreateMapRequest) -> MapEditorMapSnapshot:
    """Create an editor map from scratch or a named preset."""
    if request.include_entities:
        raise ValueError("mapeditor maps do not include entities")

    reset_editor_world()
    if request.source == "preset":
        preset_id = request.preset_id or "forgotten_crypt_arena"
        if preset_id != "forgotten_crypt_arena":
            raise ValueError(f"unknown mapeditor preset: {preset_id}")
        build_forgotten_crypt_arena_map()
    else:
        build_scratch_map(request)
    return get_editor_snapshot()


def build_scratch_map(request: MapEditorCreateMapRequest) -> None:
    """Build a simple rectangular editor map."""
    grid = get_map()
    x0, y0 = request.origin
    walkable, visible, name = _tile_properties(request.default_tile)
    grid.create_rectangle(x0, y0, request.width, request.height, walkable=walkable, visible=visible, name=name)
    for x in range(x0, x0 + request.width):
        for y in range(y0, y0 + request.height):
            tile = grid.get_tile(x, y)
            if tile is not None:
                tile.default_light = _light_level(request.default_light)


def build_forgotten_crypt_arena_map() -> None:
    """Build the current crypt arena environment without combat entities."""
    grid = get_map()
    build_standard_arena_environment(grid)


def get_editor_snapshot() -> MapEditorMapSnapshot:
    """Serialize current GridMap as an entity-free editor snapshot."""
    grid = get_map()
    bounds = grid.bounds
    api_grid = project_grid(grid)
    return MapEditorMapSnapshot(
        grid_bounds=MapEditorGridBounds(min_x=bounds[0], min_y=bounds[1], max_x=bounds[2], max_y=bounds[3]),
        tiles=api_grid.tiles,
        floor_objects=_floor_objects(grid),
        connectors=[
            connector.definition()
            for connector in grid.get_all_connectors()
        ],
    )


def _connector_mutation_response(
    operation: TraversalConnectorChangeOperation,
    connector: TraversalConnector,
    snapshot: MapEditorMapSnapshot,
    *,
    removed: bool = False,
) -> MapEditorConnectorMutationResponse:
    projected = None
    if not removed:
        projected = next(
            row
            for row in project_grid(get_map()).connectors
            if row.uuid == str(connector.uuid)
        )
    return MapEditorConnectorMutationResponse(
        operation=operation,
        connector_uuid=str(connector.uuid),
        authored_id=connector.authored_id,
        connector_revision=connector.revision,
        connector_digest=connector.objective_digest,
        connector=projected,
        snapshot=snapshot,
    )


def upsert_editor_connector(
    request: MapEditorConnectorUpsertRequest,
) -> MapEditorConnectorMutationResponse:
    """Create or replace one connector through GridMap's causal owner."""
    grid = get_map()
    existing = grid.get_connector_by_authored_id(request.definition.authored_id)
    if existing is None:
        connector = grid.register_connector(request.definition)
        operation = TraversalConnectorChangeOperation.REGISTER
    elif request.replace_existing:
        connector = grid.replace_connector(existing.uuid, request.definition)
        operation = TraversalConnectorChangeOperation.REPLACE
    else:
        raise ValueError(
            f"connector already exists: {request.definition.authored_id}"
        )
    if connector is None:
        raise ValueError("connector mutation was vetoed")
    return _connector_mutation_response(
        operation,
        connector,
        get_editor_snapshot(),
    )


def set_editor_connector_enabled(
    request: MapEditorConnectorEnabledRequest,
) -> MapEditorConnectorMutationResponse:
    """Change connector availability without changing path topology."""
    grid = get_map()
    connector = grid.get_connector_by_authored_id(request.authored_id)
    if connector is None:
        raise ValueError(f"unknown connector: {request.authored_id}")
    updated = grid.set_connector_enabled(connector.uuid, request.enabled)
    if updated is None:
        raise ValueError("connector enable mutation was vetoed")
    return _connector_mutation_response(
        (
            TraversalConnectorChangeOperation.ENABLE
            if request.enabled
            else TraversalConnectorChangeOperation.DISABLE
        ),
        updated,
        get_editor_snapshot(),
    )


def delete_editor_connector(
    request: MapEditorConnectorDeleteRequest,
) -> MapEditorConnectorMutationResponse:
    """Remove one authored connector and both endpoint-index entries."""
    grid = get_map()
    connector = grid.get_connector_by_authored_id(request.authored_id)
    if connector is None:
        raise ValueError(f"unknown connector: {request.authored_id}")
    if not grid.remove_connector(connector.uuid):
        raise ValueError("connector removal was vetoed")
    return _connector_mutation_response(
        TraversalConnectorChangeOperation.REMOVE,
        connector,
        get_editor_snapshot(),
        removed=True,
    )


def save_current_editor_map(request: MapEditorSaveMapRequest) -> MapEditorSavedMapMetadata:
    """Persist the current entity-free editor map snapshot to a local JSON file."""
    snapshot = get_editor_snapshot()
    object_placements = _saved_object_placements(snapshot.floor_objects)
    grid = get_map()
    durable_tiles = []
    for tile_snapshot in snapshot.tiles:
        tile = grid.get_tile(tile_snapshot.x, tile_snapshot.y)
        if tile is None:
            raise ValueError(
                "mapeditor snapshot contains a tile missing from GridMap",
            )
        durable_tiles.append(
            tile_snapshot.model_copy(
                update={"light_level": tile.default_light.value},
            ),
        )
    durable_snapshot = snapshot.model_copy(
        update={"tiles": durable_tiles, "floor_objects": []},
    )
    map_id = _save_id(request.id) if request.id else _unique_save_id(request.name)
    now = _utc_now()
    path = _save_path(map_id)
    created_at = now
    revision = 1
    if path.exists():
        if not request.overwrite:
            raise ValueError(f"saved map already exists: {map_id}")
        try:
            previous = MapEditorSavedMapDocument.model_validate_json(path.read_text(encoding="utf-8")).metadata
            created_at = previous.created_at
            revision = previous.revision + 1
        except Exception:
            logger.exception(
                "Replacing unreadable saved map document at %s",
                path,
            )
            created_at = now
    metadata = MapEditorSavedMapMetadata(
        id=map_id,
        name=request.name,
        created_at=created_at,
        updated_at=now,
        revision=revision,
        grid_bounds=snapshot.grid_bounds,
        tile_count=len(snapshot.tiles),
        floor_object_count=len(snapshot.floor_objects),
        connector_count=len(snapshot.connectors),
        connector_digest=canonical_content_sha256([
            connector.model_dump(mode="json")
            for connector in sorted(
                snapshot.connectors,
                key=lambda connector: connector.authored_id,
            )
        ]),
    )
    document = MapEditorSavedMapDocument(
        schema_version=_SAVE_SCHEMA_VERSION,
        content_set_digest=SERVER_CONTENT_SYSTEM_RUNTIME.require().content_set_digest,
        metadata=metadata,
        snapshot=durable_snapshot,
        object_placements=object_placements,
    )
    _preflight_saved_editor_map(document, validate_runtime_state=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
    return metadata


def list_saved_editor_maps() -> MapEditorSavedMapList:
    """List saved editor maps from the local JSON store."""
    maps = []
    for path in sorted(_save_dir().glob("*.json")):
        try:
            maps.append(MapEditorSavedMapDocument.model_validate_json(path.read_text(encoding="utf-8")).metadata)
        except Exception:
            logger.exception("Ignoring unreadable saved map document at %s", path)
            continue
    maps.sort(key=lambda metadata: metadata.updated_at, reverse=True)
    return MapEditorSavedMapList(maps=maps)


def get_saved_editor_map(map_id: str) -> MapEditorSavedMapDocument:
    """Read a saved editor map document without loading it into GridMap."""
    path = _save_path(map_id)
    if not path.exists():
        raise ValueError(f"saved map not found: {map_id}")
    document = MapEditorSavedMapDocument.model_validate_json(path.read_text(encoding="utf-8"))
    if document.schema_version != _SAVE_SCHEMA_VERSION:
        raise ValueError(f"unsupported saved map schema: {document.schema_version}")
    return document


def load_saved_editor_map(map_id: str) -> MapEditorMapSnapshot:
    """Load a saved editor map into GridMap, rebuilding map state only."""
    document = get_saved_editor_map(map_id)
    installed_digest = SERVER_CONTENT_SYSTEM_RUNTIME.require().content_set_digest
    if document.content_set_digest != installed_digest:
        raise ValueError(
            "saved map content set does not match the installed content set",
        )
    _preflight_saved_editor_map(document, validate_runtime_state=True)
    _load_editor_snapshot(
        document.snapshot,
        document.object_placements,
        document.content_set_digest,
    )
    return get_editor_snapshot()


def delete_saved_editor_map(map_id: str) -> None:
    """Delete a saved editor map document."""
    path = _save_path(map_id)
    if not path.exists():
        raise ValueError(f"saved map not found: {map_id}")
    path.unlink()


def build_catalog() -> MapEditorCatalog:
    """Discover the exact public mapeditor palette from the frozen registry."""
    loaded = SERVER_CONTENT_SYSTEM_RUNTIME.require()
    presets = [
        _entry(
            "scratch",
            "Blank Map",
            "presets",
            "map_preset",
            placement="map",
        ),
        _entry(
            "forgotten_crypt_arena",
            "Forgotten Crypt Arena",
            "presets",
            "map_preset",
            placement="map",
            default_state={"has_entities": False},
        ),
    ]
    tiles = [
        _entry(
            "floor",
            "Floor",
            "tiles",
            "tile",
            flags={"walkable": True, "blocks_vision": False},
        ),
        _entry(
            "wall",
            "Wall",
            "tiles",
            "tile",
            flags={"walkable": False, "blocks_vision": True},
        ),
        _entry(
            "water",
            "Water",
            "tiles",
            "tile",
            flags={"walkable": False, "blocks_vision": False},
        ),
        _entry(
            "difficult_terrain",
            "Difficult Terrain",
            "tiles",
            "tile",
            flags={"walkable": True, "walking_cost": 2},
        ),
        _entry(
            "spike_zone",
            "Spike Zone",
            "tiles",
            "hazard_zone",
            placement="zone",
            flags={"walkable": True, "hazardous": True},
        ),
    ]
    default_rows: list[MapEditorContentCatalogEntry] = []
    for declaration in loaded.registry.declarations.values():
        descriptor = declaration.descriptor
        item_definition = declaration.item_definition
        construction = declaration.construction
        if (
            descriptor.visibility is not ContentVisibility.PUBLIC
            or item_definition is None
            or construction is None
            or item_definition.persistence_policy
            not in {
                ItemPersistencePolicy.POSSESSION,
                ItemPersistencePolicy.ENVIRONMENT,
            }
        ):
            continue
        parameters = construction.parameter_model.model_validate(
            {},
        ).model_dump(mode="json")
        default_rows.append(
            _content_catalog_entry(
                recipe=ContentRecipe.create(
                    ref=declaration.ref,
                    parameters=parameters,
                ),
                content_set_digest=loaded.content_set_digest,
                display_name=descriptor.display_name,
                description=descriptor.description,
                tags=descriptor.tags,
                presentation=descriptor.presentation,
                ordering=descriptor.ordering,
            ),
        )

    objects = [
        row
        for row in default_rows
        if row.recipe.ref.definition_kind
        is ContentDefinitionKind.ENVIRONMENT_OBJECT
    ]
    loot = [
        row
        for row in default_rows
        if row.recipe.ref.definition_kind is ContentDefinitionKind.ITEM
    ]
    root_recipe_digests = {
        row.recipe.recipe_digest
        for row in loot
    }
    for preset in loaded.registry.recipe_presets.values():
        declaration = loaded.registry.resolve_factory(preset.recipe.ref)
        descriptor = preset.descriptor
        item_definition = declaration.item_definition
        if (
            descriptor.visibility is not ContentVisibility.PUBLIC
            or item_definition is None
            or item_definition.persistence_policy
            is not ItemPersistencePolicy.POSSESSION
            or preset.recipe.recipe_digest in root_recipe_digests
        ):
            continue
        loot.append(
            _content_catalog_entry(
                recipe=preset.recipe,
                content_set_digest=loaded.content_set_digest,
                recipe_preset_ref=preset.ref,
                display_name=descriptor.display_name,
                description=descriptor.description,
                tags=descriptor.tags,
                presentation=descriptor.presentation,
                ordering=descriptor.ordering,
            ),
        )

    def content_row_key(
        row: MapEditorContentCatalogEntry,
    ) -> tuple[str, int, str]:
        identity = (
            row.recipe_preset_ref.identity_key
            if row.recipe_preset_ref is not None
            else row.recipe.ref.identity_key
        )
        return (
            row.ordering.sort_group,
            row.ordering.sort_order,
            identity,
        )

    return MapEditorCatalog(
        content_set_digest=loaded.content_set_digest,
        presets=presets,
        tiles=tiles,
        objects=sorted(objects, key=content_row_key),
        loot=sorted(loot, key=content_row_key),
    )


def apply_tile_patches(patches: Iterable[MapEditorTilePatch]) -> MapEditorMapSnapshot:
    """Apply tile patches through GridMap/Tile factories."""
    grid = get_map()
    spike_positions = set()
    for patch in patches:
        original_tile = grid.get_tile(patch.x, patch.y)
        original_height = original_tile.height if original_tile is not None else 0
        original_kind = (
            original_tile.elevation_surface_kind
            if original_tile is not None
            else ElevationSurfaceKind.ORDINARY
        )
        original_axis = original_tile.slope_axis if original_tile is not None else None
        elevation_touched = bool(
            {"elevation_steps", "elevation_surface_kind", "slope_axis"}
            & patch.model_fields_set
        )
        if "elevation_steps" in patch.model_fields_set and patch.elevation_steps is None:
            raise ValueError("elevation_steps cannot be null when supplied")
        if (
            "elevation_surface_kind" in patch.model_fields_set
            and patch.elevation_surface_kind is None
        ):
            raise ValueError("elevation_surface_kind cannot be null when supplied")
        requested_elevation = (
            patch.elevation_steps
            if patch.elevation_steps is not None
            else original_height
        )
        requested_kind = (
            patch.elevation_surface_kind
            if patch.elevation_surface_kind is not None
            else original_kind
        )
        requested_axis = (
            patch.slope_axis
            if "slope_axis" in patch.model_fields_set
            else original_axis
        )
        assert requested_elevation is not None
        assert requested_kind is not None
        validate_elevation_surface_tuple(
            requested_elevation,
            requested_kind,
            requested_axis,
        )
        directional_parts = (
            patch.directional_channel,
            patch.direction,
            patch.passable,
        )
        if any(part is not None for part in directional_parts) and not all(
            part is not None for part in directional_parts
        ):
            raise ValueError(
                "directional_channel, direction, and passable are required together"
            )
        requested_light = (
            _light_level(patch.light_level)
            if patch.light_level is not None
            else None
        )
        elevation_changed = (
            requested_elevation,
            requested_kind,
            requested_axis,
        ) != (
            original_height,
            original_kind,
            original_axis,
        )
        if original_tile is not None and elevation_changed:
            if not grid.set_tile_elevation(
                (patch.x, patch.y),
                height=requested_elevation,
                surface_kind=requested_kind,
                slope_axis=requested_axis,
            ):
                raise ValueError("tile elevation change was rejected")
        tile_type = _normalize_id(patch.type) if patch.type else None
        if tile_type is None:
            if original_tile is None and elevation_touched:
                grid.set_tile(
                    patch.x,
                    patch.y,
                    walkable=True,
                    visible=True,
                    name="Floor",
                    height=requested_elevation,
                    elevation_surface_kind=requested_kind,
                    slope_axis=requested_axis,
                )
            _apply_directional_tile_patch(grid, patch)
            old = grid.get_tile(patch.x, patch.y)
            if old is not None and requested_light is not None:
                old.default_light = requested_light
            continue
        if tile_type in {"spike_trap", "spike_zone", "spikes"}:
            old = grid.get_tile(patch.x, patch.y)
            old_light = (
                old.default_light
                if old is not None
                else LightLevel.BRIGHT_LIGHT
            )
            tile = grid.set_tile(
                patch.x,
                patch.y,
                walkable=True,
                visible=True,
                name="Floor",
                height=requested_elevation,
                elevation_surface_kind=requested_kind,
                slope_axis=requested_axis,
            )
            tile.default_light = (
                requested_light
                if requested_light is not None
                else old_light
            )
            _apply_directional_tile_patch(grid, patch)
            spike_positions.add((patch.x, patch.y))
            continue
        old = grid.get_tile(patch.x, patch.y)
        old_light = old.default_light if old is not None else LightLevel.BRIGHT_LIGHT
        if tile_type == "difficult_terrain":
            tile = difficult_terrain_factory(
                (patch.x, patch.y),
                height=requested_elevation,
                elevation_surface_kind=requested_kind,
                slope_axis=requested_axis,
            )
            tile.default_light = requested_light if requested_light is not None else old_light
            grid.set_tile(patch.x, patch.y, tile=tile)
            _apply_directional_tile_patch(grid, patch)
            continue
        walkable, visible, name = _tile_properties(tile_type)
        tile = grid.set_tile(
            patch.x,
            patch.y,
            walkable=walkable,
            visible=visible,
            name=name,
            height=requested_elevation,
            elevation_surface_kind=requested_kind,
            slope_axis=requested_axis,
        )
        tile.default_light = requested_light if requested_light is not None else old_light
        _apply_directional_tile_patch(grid, patch)

    if spike_positions:
        existing = _active_spike_trap_effects()
        if len(existing) > 1:
            raise ValueError("mapeditor supports one linked spike-trap network")
        if existing:
            extend_spike_trap_effect(existing[0], spike_positions)
            spike_effect = existing[0]
        else:
            spike_effect = materialize_spike_trap_effect(spike_positions)
        _bind_unlinked_trap_levers(spike_effect.uuid)
    return get_editor_snapshot()


def _apply_directional_tile_patch(grid: Any, patch: MapEditorTilePatch) -> None:
    if patch.directional_channel is None and patch.direction is None and patch.passable is None:
        return
    if patch.directional_channel is None or patch.direction is None or patch.passable is None:
        raise ValueError("directional_channel, direction, and passable are required together")
    if grid.get_tile(patch.x, patch.y) is None:
        grid.set_tile(patch.x, patch.y, walkable=True, visible=True, name="Floor")
    grid.set_tile_directional_border(
        (patch.x, patch.y),
        patch.directional_channel,
        patch.direction,
        patch.passable,
    )


def place_catalog_object(request: MapEditorObjectPlaceRequest) -> APIFloorObject:
    """Validate and place one exact public item recipe on the grid."""
    loaded = SERVER_CONTENT_SYSTEM_RUNTIME.require()
    if request.content_set_digest != loaded.content_set_digest:
        raise ValueError(
            "requested content set does not match the installed content set",
        )
    grid = get_map()
    if grid.get_tile(request.position[0], request.position[1]) is None:
        raise ValueError(
            f"mapeditor placement requires an existing tile at {request.position}",
        )
    _declaration, origin = _resolve_placeable_editor_recipe(request.recipe)
    registry_snapshot = _capture_editor_materialization_state()
    try:
        item = materialize_item(
            request.recipe,
            uuid4(),
            origin=origin,
        )
        _validate_editor_runtime_state(
            item,
            request.runtime_state,
        )
        _apply_editor_runtime_state(
            item,
            request.position,
            request.runtime_state,
        )
    except Exception:
        _rollback_editor_materialization(registry_snapshot)
        raise
    obj_pos = grid.get_object_position(item.uuid)
    if obj_pos is None:
        _rollback_editor_materialization(registry_snapshot)
        raise ValueError("mapeditor item factory did not place its object")
    return _floor_object(item.uuid, obj_pos)


def _resolve_placeable_editor_recipe(
    recipe: ContentRecipe,
) -> tuple[ContentDeclaration, ItemRuntimeOrigin]:
    """Resolve and type-check a recipe before any runtime construction."""
    recipe.verify_integrity()
    try:
        declaration = resolve_item_recipe(recipe)
    except (KeyError, TypeError) as error:
        raise ValueError(str(error).strip("'")) from error
    definition = declaration.item_definition
    if (
        declaration.descriptor.visibility is not ContentVisibility.PUBLIC
        or definition is None
    ):
        raise ValueError(f"content {recipe.ref.identity_key} is not placeable")
    construction = declaration.construction
    if construction is None:
        raise ValueError(f"content {recipe.ref.identity_key} is not constructible")
    construction.parameter_model.model_validate(recipe.parameters)
    if (
        recipe.ref.definition_kind is ContentDefinitionKind.ITEM
        and definition.persistence_policy is ItemPersistencePolicy.POSSESSION
    ):
        return declaration, ItemRuntimeOrigin.LOOT
    if (
        recipe.ref.definition_kind is ContentDefinitionKind.ENVIRONMENT_OBJECT
        and definition.persistence_policy is ItemPersistencePolicy.ENVIRONMENT
    ):
        return declaration, ItemRuntimeOrigin.ENVIRONMENT
    raise ValueError(f"content {recipe.ref.identity_key} is not placeable")


def _capture_editor_materialization_state(
) -> tuple[
    frozenset[UUID],
    frozenset[UUID],
    frozenset[UUID],
    frozenset[UUID],
    frozenset[UUID],
]:
    """Capture registries that a provisional item construction may extend."""
    return (
        frozenset(BaseBlock._registry),
        frozenset(BaseObject._registry),
        frozenset(BaseValue._registry),
        frozenset(ITEM_RUNTIME_BINDINGS.bindings),
        frozenset(get_map().get_all_object_positions()),
    )


def _rollback_editor_materialization(
    snapshot: tuple[
        frozenset[UUID],
        frozenset[UUID],
        frozenset[UUID],
        frozenset[UUID],
        frozenset[UUID],
    ],
) -> None:
    """Remove every provisional block, value, binding, and grid placement."""
    (
        blocks_before,
        base_objects_before,
        values_before,
        bindings_before,
        objects_before,
    ) = snapshot
    grid = get_map()
    for object_uuid in set(grid.get_all_object_positions()) - set(
        objects_before
    ):
        grid.remove_object(object_uuid)
    for block_uuid in set(BaseBlock._registry) - set(blocks_before):
        grid.cleanup_block_light_sources(block_uuid)
        BaseBlock._registry.pop(block_uuid, None)
    for object_uuid in set(BaseObject._registry) - set(base_objects_before):
        BaseObject._registry.pop(object_uuid, None)
    for value_uuid in set(BaseValue._registry) - set(values_before):
        BaseValue._registry.pop(value_uuid, None)
    for binding_uuid in set(ITEM_RUNTIME_BINDINGS.bindings) - set(
        bindings_before,
    ):
        ITEM_RUNTIME_BINDINGS.discard(binding_uuid)


def _validate_editor_runtime_state(
    item: BaseItem,
    state: MapEditorObjectRuntimeState,
) -> None:
    """Validate every mutable fact before the item mutates the active grid."""
    if state.charges is not None:
        if not isinstance(item, UsableItem):
            raise ValueError("charges are only valid for usable items")
        if item.max_charges >= 0 and state.charges < 0:
            raise ValueError("finite-charge items cannot use charges=-1")
        if item.max_charges >= 0 and state.charges > item.max_charges:
            raise ValueError("current charges cannot exceed maximum charges")

    if state.is_open is not None and not isinstance(
        item,
        (DoorObject, DirectionalDoor),
    ):
        raise ValueError("is_open is only valid for door objects")
    if state.is_lit is not None and not isinstance(item, WallTorch):
        raise ValueError("is_lit is only valid for wall torches")

def _apply_editor_runtime_state(
    item: BaseItem,
    position: Tuple[int, int],
    state: MapEditorObjectRuntimeState,
) -> None:
    """Apply the narrow mutable state supported after generic construction."""
    if state.charges is not None:
        if not isinstance(item, UsableItem):
            raise AssertionError("runtime state was not validated")
        item.charges = state.charges

    if isinstance(item, DoorObject):
        if state.is_open is not None:
            item.is_open = state.is_open
            item.blocks_movement = not state.is_open
            item.blocks_vision_field = not state.is_open
    elif isinstance(item, DirectionalDoor):
        pass

    if isinstance(item, WallTorch):
        item.mount(
            position,
            lit=True if state.is_lit is None else state.is_lit,
        )
    else:
        item.place_on_grid(position)

    if isinstance(item, DirectionalDoor) and state.is_open is not None:
        if state.is_open:
            item.open()
        else:
            item.close()

    if isinstance(item, TrapLever):
        spike_effects = _active_spike_trap_effects()
        if len(spike_effects) > 1:
            raise ValueError("mapeditor supports one linked spike-trap network")
        if spike_effects:
            _bind_trap_link(item, spike_effects[0].uuid)


def _bind_trap_link(
    item: TrapLever,
    trap_effect_uuid: UUID,
) -> None:
    """Attach one exact trap-effect identity after item materialization."""
    action: BaseAction = PullLeverAction(
        source_entity_uuid=uuid4(),
        trap_effect_uuid=trap_effect_uuid,
        template=True,
    )
    SERVER_CONTENT_SYSTEM_RUNTIME.bind_child(
        action,
        provider=item,
        runtime_owner_uuid=item.uuid,
    )
    item.use_action_templates.append(action)


def _active_spike_trap_effects() -> list[SpikeTrapGroundEffect]:
    """Return exact active physical spike-trap effects in stable order."""
    expected_ref = SPIKE_TRAP_EFFECT_DECLARATION.ref
    return [
        effect
        for effect in SpatialEffect.active_effects()
        if (
            isinstance(effect, SpikeTrapGroundEffect)
            and effect.content_ref == expected_ref
        )
    ]


def _bind_unlinked_trap_levers(trap_effect_uuid: UUID) -> None:
    """Bind existing editor levers after their sole trap network is authored."""
    grid = get_map()
    for object_uuid in sorted(grid.get_all_object_positions(), key=str):
        item = BaseBlock.get(object_uuid)
        if not isinstance(item, TrapLever):
            continue
        linked_actions = [
            action
            for action in item.use_action_templates
            if isinstance(action, PullLeverAction)
        ]
        if linked_actions:
            if any(
                action.trap_effect_uuid != trap_effect_uuid
                for action in linked_actions
            ):
                raise ValueError("trap lever is already linked to another effect")
            continue
        _bind_trap_link(item, trap_effect_uuid)


def _is_spike_trap_effect_summary(
    effect: APISpatialEffectSummary,
) -> bool:
    """Match one exact authored spike-effect snapshot."""
    expected = SPIKE_TRAP_EFFECT_DECLARATION.ref
    return (
        effect.content_ref.pack_id == expected.pack_id
        and effect.content_ref.definition_kind == expected.definition_kind.value
        and effect.content_ref.content_id == expected.content_id
        and effect.content_ref.content_version == expected.content_version
        and (
            effect.content_ref.definition_contract_hash
            == expected.definition_contract_hash
        )
    )


def _tile_has_spike_trap_effect(tile: APITile) -> bool:
    """Return whether one projected tile belongs to the spike network."""
    return any(
        _is_spike_trap_effect_summary(effect)
        for effect in tile.spatial_effects
    )


def delete_catalog_object(request: MapEditorObjectDeleteRequest) -> MapEditorMapSnapshot:
    """Delete editor object(s) by UUID or by tile position."""
    grid = get_map()
    object_ids: List[UUID] = []
    if request.object_uuid:
        object_ids.append(UUID(request.object_uuid))
    elif request.position is not None:
        object_ids.extend(grid.get_objects_at(request.position))
    else:
        raise ValueError("object_uuid or position is required")

    if not object_ids:
        raise ValueError("no mapeditor object found to delete")
    for object_uuid in object_ids:
        if grid.get_object_position(object_uuid) is None:
            raise ValueError(f"mapeditor object not found: {object_uuid}")
        grid.remove_object(object_uuid)
    return get_editor_snapshot()


def get_walkability() -> MapEditorWalkabilityResponse:
    grid = get_map()
    cells = []
    for x, y, _tile in _iter_tiles():
        walkable = grid.is_walkable_for(x, y, requesting_entity_uuid=None)
        blocker = None if walkable else grid.identify_blocker_at((x, y))
        cells.append(MapEditorWalkabilityCell(x=x, y=y, walkable=walkable, blocker=blocker))
    return MapEditorWalkabilityResponse(cells=cells)


def get_visibility_blockers() -> MapEditorVisibilityResponse:
    cells = []
    for x, y, tile in _iter_tiles():
        blocker: Optional[str] = None
        if not tile.visible:
            blocker = tile.name
        else:
            for obj_uuid in get_map().get_objects_at((x, y)):
                block = BaseBlock.get(obj_uuid)
                if block is not None and block.blocks_vision(None):
                    blocker = block.name
                    break
        cells.append(MapEditorVisibilityCell(x=x, y=y, blocks_visibility=blocker is not None, blocker=blocker))
    return MapEditorVisibilityResponse(cells=cells)


def get_objective_light() -> MapEditorLightResponse:
    return MapEditorLightResponse(
        cells=[
            MapEditorLightCell(x=x, y=y, light_level=tile.resolved_light_level.value)
            for x, y, tile in _iter_tiles()
        ]
    )


def _preflight_saved_editor_map(
    document: MapEditorSavedMapDocument,
    *,
    validate_runtime_state: bool,
) -> None:
    """Validate the complete temporary save before replacing the active world."""
    tiles_by_position = {
        (tile.x, tile.y): tile
        for tile in document.snapshot.tiles
    }
    tile_positions = set(tiles_by_position)
    contradiction = contradictory_progressive_elevation_edge({
        position: (
            tile.elevation_steps,
            tile.elevation_surface_kind,
            tile.slope_axis,
        )
        for position, tile in tiles_by_position.items()
    })
    if contradiction is not None:
        raise ValueError(
            "saved map contains a contradictory progressive elevation "
            f"edge between {contradiction[0]} and {contradiction[1]}"
        )
    connector_ids = [
        connector.authored_id for connector in document.snapshot.connectors
    ]
    if len(connector_ids) != len(set(connector_ids)):
        raise ValueError("saved map connector authored IDs must be unique")
    for connector in document.snapshot.connectors:
        if any(
            endpoint not in tile_positions
            for endpoint in connector.endpoint_positions
        ):
            raise ValueError("saved map connector requires two support tiles")
        first, second = connector.endpoint_positions
        if (
            connector.kind.value != "passage"
            and tiles_by_position[first].elevation_steps
            == tiles_by_position[second].elevation_steps
        ):
            raise ValueError(
                "saved map vertical connector requires nonzero elevation delta"
            )
    trap_lever_count = 0
    for placement in document.object_placements:
        if placement.position not in tile_positions:
            raise ValueError(
                "saved map object placement requires an existing snapshot tile "
                f"at {placement.position}",
            )
        declaration, origin = _resolve_placeable_editor_recipe(
            placement.recipe,
        )
        if declaration.ref == TRAP_LEVER_DECLARATION.ref:
            trap_lever_count += 1
        if not validate_runtime_state:
            continue
        registry_snapshot = _capture_editor_materialization_state()
        try:
            item = materialize_item(
                placement.recipe,
                uuid4(),
                origin=origin,
            )
            _validate_editor_runtime_state(
                item,
                placement.runtime_state,
            )
        finally:
            _rollback_editor_materialization(registry_snapshot)
    if trap_lever_count > 1:
        raise ValueError(
            "temporary mapeditor saves support at most one trap lever "
            "for their one trap network",
        )
    spike_effect_uuids = {
        effect.uuid
        for tile in document.snapshot.tiles
        for effect in tile.spatial_effects
        if _is_spike_trap_effect_summary(effect)
    }
    if len(spike_effect_uuids) > 1:
        raise ValueError(
            "temporary mapeditor saves support one spike-trap effect network",
        )
    has_spike_network = bool(spike_effect_uuids)
    if trap_lever_count == 1 and not has_spike_network:
        raise ValueError(
            "temporary mapeditor trap lever requires one spike network",
        )


def _load_editor_snapshot(
    snapshot: MapEditorMapSnapshot,
    object_placements: List[MapEditorSavedObjectPlacement],
    content_set_digest: str,
) -> None:
    """Rebuild GridMap from a saved editor snapshot without entities."""
    reset_editor_world()
    grid = get_map()
    spike_light: Dict[Tuple[int, int], int] = {}
    spike_effect_uuid: Optional[UUID] = None
    for tile_data in snapshot.tiles:
        position = (tile_data.x, tile_data.y)
        if _tile_has_spike_trap_effect(tile_data):
            spike_light[position] = tile_data.light_level
        normalized_tile_name = _normalize_id(tile_data.name)
        if tile_data.walking_cost > 1 or normalized_tile_name == "difficult_terrain":
            tile = difficult_terrain_factory(position)
            tile.default_light = _light_level(tile_data.light_level)
            grid.set_tile(tile_data.x, tile_data.y, tile=tile, fire_event=False)
            grid.set_tile_elevation(
                position,
                height=tile_data.elevation_steps,
                surface_kind=tile_data.elevation_surface_kind,
                slope_axis=tile_data.slope_axis,
            )
            _restore_directional_tile_state(grid, tile_data)
            continue
        if normalized_tile_name == "water":
            tile = water_factory(position)
            tile.default_light = _light_level(tile_data.light_level)
            grid.set_tile(tile_data.x, tile_data.y, tile=tile, fire_event=False)
            grid.set_tile_elevation(
                position,
                height=tile_data.elevation_steps,
                surface_kind=tile_data.elevation_surface_kind,
                slope_axis=tile_data.slope_axis,
            )
            _restore_directional_tile_state(grid, tile_data)
            continue
        if normalized_tile_name == "wall":
            tile = wall_factory(position)
            tile.default_light = _light_level(tile_data.light_level)
            grid.set_tile(tile_data.x, tile_data.y, tile=tile, fire_event=False)
            grid.set_tile_elevation(
                position,
                height=tile_data.elevation_steps,
                surface_kind=tile_data.elevation_surface_kind,
                slope_axis=tile_data.slope_axis,
            )
            _restore_directional_tile_state(grid, tile_data)
            continue
        tile = grid.set_tile(
            tile_data.x,
            tile_data.y,
            walkable=tile_data.walkable,
            visible=tile_data.visible,
            name=tile_data.name,
            sprite_name=tile_data.visual_key,
            fire_event=False,
        )
        tile.default_light = _light_level(tile_data.light_level)
        grid.set_tile_elevation(
            position,
            height=tile_data.elevation_steps,
            surface_kind=tile_data.elevation_surface_kind,
            slope_axis=tile_data.slope_axis,
        )
        _restore_directional_tile_state(grid, tile_data)

    for connector_definition in sorted(
        snapshot.connectors,
        key=lambda connector: connector.authored_id,
    ):
        registered = grid.register_connector(connector_definition)
        if registered is None:
            raise ValueError(
                f"saved connector was vetoed: {connector_definition.authored_id}"
            )

    if spike_light:
        spike_effect = materialize_spike_trap_effect(set(spike_light))
        spike_effect_uuid = spike_effect.uuid

    for placement in object_placements:
        placed = place_catalog_object(
            MapEditorObjectPlaceRequest(
                recipe=placement.recipe,
                content_set_digest=content_set_digest,
                position=placement.position,
                runtime_state=placement.runtime_state,
            )
        )
        item = BaseBlock.get(UUID(placed.uuid))
        if isinstance(item, TrapLever) and spike_effect_uuid is not None:
            actions = [
                action
                for action in item.use_action_templates
                if isinstance(action, PullLeverAction)
            ]
            if not actions:
                _bind_trap_link(item, spike_effect_uuid)


def _restore_directional_tile_state(grid: Any, tile_data: APITile) -> None:
    position = (tile_data.x, tile_data.y)
    channel_maps = {
        "movement": tile_data.directional_blocks_movement,
        "vision": tile_data.directional_blocks_vision,
        "light": tile_data.directional_blocks_light,
        "propagation": tile_data.directional_blocks_propagation,
    }
    for channel, blocked_by_direction in channel_maps.items():
        for direction, blocked in blocked_by_direction.model_dump().items():
            grid.set_tile_directional_border(
                position,
                channel,
                direction,
                not blocked,
                fire_event=False,
            )


def _iter_tiles() -> Iterable[Tuple[int, int, Tile]]:
    grid = get_map()
    min_x, min_y, max_x, max_y = grid.bounds
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            tile = grid.get_tile(x, y)
            if tile is not None:
                yield x, y, tile


def _floor_objects(grid: Any) -> List[APIFloorObject]:
    result = []
    for obj_uuid, obj_pos in grid.get_all_object_positions().items():
        result.append(_floor_object(obj_uuid, obj_pos))
    return result


def _floor_object(obj_uuid: UUID, obj_pos: Tuple[int, int]) -> APIFloorObject:
    obj = BaseBlock.get(obj_uuid)
    if obj is None:
        return APIFloorObject(uuid=str(obj_uuid), name="Object", position=obj_pos, map_char="?", state={})
    return APIFloorObject(
        uuid=str(obj_uuid),
        name=obj.name or "Object",
        position=obj_pos,
        map_char=obj.get_map_char() or "?",
        state=_get_floor_object_state(obj),
    )


def _get_floor_object_state(obj: BaseBlock) -> Dict[str, Any]:
    all_fields = set(type(obj).model_fields.keys())
    state_fields = all_fields - _BASE_BLOCK_FIELDS - _ALREADY_SERIALIZED
    return obj.model_dump(mode="json", include=state_fields)


def _saved_object_placements(floor_objects: List[APIFloorObject]) -> List[MapEditorSavedObjectPlacement]:
    placements: list[MapEditorSavedObjectPlacement] = []
    installed_digest = SERVER_CONTENT_SYSTEM_RUNTIME.require().content_set_digest
    for obj in floor_objects:
        runtime_object = BaseBlock.get(UUID(obj.uuid))
        if not isinstance(runtime_object, BaseItem):
            raise ValueError(
                f"cannot save non-item mapeditor object: {obj.uuid}",
            )
        binding = ITEM_RUNTIME_BINDINGS.require(runtime_object.uuid)
        if runtime_object.content_ref != binding.recipe.ref:
            raise ValueError(
                "mapeditor object content identity differs from its runtime "
                f"binding: {obj.uuid}",
            )
        if binding.content_set_digest != installed_digest:
            raise ValueError(
                "mapeditor object binding belongs to a different content set",
            )
        runtime_state = MapEditorObjectRuntimeState(
            is_open=(
                runtime_object.is_open
                if isinstance(runtime_object, (DoorObject, DirectionalDoor))
                else None
            ),
            is_lit=(
                runtime_object.is_lit
                if isinstance(runtime_object, WallTorch)
                else None
            ),
            charges=(
                runtime_object.charges
                if isinstance(runtime_object, UsableItem)
                else None
            ),
        )
        placements.append(
            MapEditorSavedObjectPlacement(
                recipe=binding.recipe,
                position=(obj.position[0], obj.position[1]),
                runtime_state=runtime_state,
            ),
        )
    return placements


def _save_dir() -> Path:
    configured = os.environ.get("DND_MAPEDITOR_SAVE_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "mapeditor" / "maps"


def _save_path(map_id: str) -> Path:
    return _save_dir() / f"{_save_id(map_id)}.json"


def _unique_save_id(name: str) -> str:
    base = _save_id(name)
    candidate = base
    suffix = 2
    while _save_path(candidate).exists():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _save_id(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower()
    return slug or f"map_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tile_properties(tile_type: str) -> Tuple[bool, bool, str]:
    normalized = _normalize_id(tile_type)
    if normalized == "wall":
        return False, False, "Wall"
    if normalized == "water":
        return False, True, "Water"
    return True, True, "Floor"


def _light_level(value: int) -> LightLevel:
    if value < 0 or value > 4:
        raise ValueError("light level must be between 0 and 4")
    return LightLevel(value)


def _normalize_id(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _entry(
    id: str,
    name: str,
    group: str,
    category: str,
    *,
    stability: Literal["stable", "candidate", "demo"] = "stable",
    placement: str = "single_tile",
    map_char: Optional[str] = None,
    visual_item_name: Optional[str] = None,
    flags: Optional[Dict[str, Any]] = None,
    actions: Optional[List[str]] = None,
    default_state: Optional[Dict[str, Any]] = None,
) -> MapEditorCatalogEntry:
    return MapEditorCatalogEntry(
        id=id,
        name=name,
        group=group,
        category=category,
        stability=stability,
        placement=placement,
        map_char=map_char,
        visual_item_name=visual_item_name,
        flags=flags or {},
        actions=actions or [],
        default_state=default_state or {},
    )


def _content_catalog_entry(
    *,
    recipe: ContentRecipe,
    content_set_digest: str,
    display_name: str,
    description: str,
    tags: tuple[str, ...],
    presentation: ContentPresentation,
    ordering: ContentOrdering,
    recipe_preset_ref: ContentRecipePresetRef | None = None,
) -> MapEditorContentCatalogEntry:
    """Project one registry-owned recipe without Python implementation facts."""
    return MapEditorContentCatalogEntry(
        recipe=recipe,
        content_set_digest=content_set_digest,
        recipe_preset_ref=recipe_preset_ref,
        display_name=display_name,
        description=description,
        tags=tags,
        presentation=presentation,
        ordering=ordering,
    )
