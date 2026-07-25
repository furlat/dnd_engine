"""Pydantic DTOs for REST API serialization."""

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union
from urllib.parse import urlsplit

from dnd.ai.policy import PolicyDescriptor
from dnd.core.base_actions import AvailableActionsResult, AvailableHandlerInfo
from dnd.scenarios.evaluation.compatibility import CompatibilityReport
from dnd.scenarios.evaluation.models import (
    BattlefieldSpec,
    DeploymentSpec,
    LegacyScenarioRecipe,
    SideConfigurationSpec,
)
from server import world_contracts


class ServerCapabilitiesResponse(BaseModel):
    """Describe the server topology available to a connecting game client."""

    server_mode: Literal["standalone", "gateway"] = Field(
        description="Active deployment topology exposed by this HTTP origin."
    )
    game_directory_enabled: bool = Field(
        description="Whether hosted-game discovery and attachment routes are available."
    )
    persistent_game_history: bool = Field(
        description="Whether completed game metadata and summaries persist across restarts."
    )
    isolated_game_workers: bool = Field(
        description="Whether each hosted game executes in an isolated hot worker process."
    )


class APIEquippableDisplacement(BaseModel):
    """One equipped item displaced by a proposed equipment footprint."""

    item_uuid: str = Field(description="Equipped item UUID.")
    item_name: str = Field(description="Equipped item display name.")
    slot: str = Field(description="Canonical storage slot currently holding the item.")


class APIEquippableEntry(BaseModel):
    """One inventory candidate and every equipped item it would displace."""

    item_uuid: str = Field(description="Inventory item UUID.")
    item_name: str = Field(description="Inventory item display name.")
    displaced_items: List[APIEquippableDisplacement] = Field(
        default_factory=list,
        description="Equipped items whose declared footprints overlap this proposal.",
    )


class APIEquippableItems(BaseModel):
    """Inventory equipment candidates grouped by canonical slot name."""

    entity_uuid: str = Field(description="Entity whose inventory was inspected.")
    equippable: Dict[str, List[APIEquippableEntry]] = Field(
        default_factory=dict,
        description="Equipment candidates grouped by canonical slot name.",
    )


class APIEntityHandlersResponse(BaseModel):
    """Player-toggleable handlers registered on one entity."""

    entity_uuid: str = Field(description="Entity whose handlers were inspected.")
    handlers: List[AvailableHandlerInfo] = Field(description="Player-toggleable handler summaries.")


class ToggleHandlerResponse(BaseModel):
    """Result of changing one player-toggleable handler."""

    success: bool = Field(description="Whether the handler state changed.")
    handler_name: str = Field(description="Handler display name.")
    enabled: bool = Field(description="Resulting enabled state.")


class EquipRequest(BaseModel):
    """Request to equip an item from inventory.

    Attributes:
        session_id: Acting player session UUID.
        item_uuid: Inventory item to equip.
        slot: Optional explicit target slot; omitted means auto-assign.
    """

    session_id: str = Field(description="Acting player session UUID.")
    item_uuid: str = Field(description="Inventory item to equip.")
    slot: Optional[str] = Field(default=None, description="Optional explicit target slot; omitted means auto-assign.")


class UnequipRequest(BaseModel):
    """Request to unequip an item from a slot.

    Attributes:
        session_id: Acting player session UUID.
        slot: Equipment slot to clear.
    """

    session_id: str = Field(description="Acting player session UUID.")
    slot: str = Field(description="Equipment slot to clear.")


class EquipmentMutationResult(BaseModel):
    """Minimal acknowledgement after an equipment mutation request.

    Attributes:
        success: Whether the equipment command succeeded.
        message: Human-readable result summary.
        event_cursor_after: Event-history cursor after side effects.
        combat_log_cursor_after: Combat-log cursor after side effects.
    """

    success: bool = Field(description="Whether the equipment command succeeded.")
    message: str = Field(description="Human-readable result summary.")
    event_cursor_after: Optional[int] = Field(default=None, description="Event-history cursor after side effects.")
    combat_log_cursor_after: Optional[int] = Field(default=None, description="Combat-log cursor after side effects.")


class MapEditorGridBounds(BaseModel):
    """Inclusive grid bounds.

    Attributes:
        min_x: Minimum x-coordinate included in the map.
        min_y: Minimum y-coordinate included in the map.
        max_x: Maximum x-coordinate included in the map.
        max_y: Maximum y-coordinate included in the map.
    """

    min_x: int = Field(description="Minimum x-coordinate included in the map.")
    min_y: int = Field(description="Minimum y-coordinate included in the map.")
    max_x: int = Field(description="Maximum x-coordinate included in the map.")
    max_y: int = Field(description="Maximum y-coordinate included in the map.")


class MapEditorMapSnapshot(BaseModel):
    """Entity-free map snapshot for editing and generation.

    Attributes:
        grid_bounds: Inclusive bounds for the serialized map.
        tiles: Serialized tile snapshots.
        floor_objects: Serialized floor objects placed on the map.
    """

    grid_bounds: MapEditorGridBounds = Field(description="Inclusive bounds for the serialized map.")
    tiles: List[world_contracts.APITile] = Field(description="Serialized tile snapshots.")
    floor_objects: List[world_contracts.APIFloorObject] = Field(
        default_factory=list,
        description="Serialized floor objects placed on the map.",
    )


class MapEditorSavedObjectPlacement(BaseModel):
    """Reloadable editor object placement without serializing entities.

    Attributes:
        catalog_id: Catalog identifier used to recreate the object.
        name: Object display name stored in the save document.
        position: Grid position where the object should be restored.
        state: Object-specific state to restore.
    """

    catalog_id: str = Field(description="Catalog identifier used to recreate the object.")
    name: str = Field(description="Object display name stored in the save document.")
    position: Tuple[int, int] = Field(description="Grid position where the object should be restored.")
    state: Dict[str, Any] = Field(default_factory=dict, description="Object-specific state to restore.")


class MapEditorSaveMapRequest(BaseModel):
    """Request to save the current entity-free editor map.

    Attributes:
        id: Optional save identifier to create or overwrite.
        name: Human-readable saved map name.
        overwrite: Whether an existing save with the same identifier may be replaced.
    """

    id: Optional[str] = Field(default=None, description="Optional save identifier to create or overwrite.")
    name: str = Field(default="Untitled Map", description="Human-readable saved map name.")
    overwrite: bool = Field(
        default=False,
        description="Whether an existing save with the same identifier may be replaced.",
    )


class MapEditorSavedMapMetadata(BaseModel):
    """Saved editor map metadata.

    Attributes:
        id: Stable saved map identifier.
        name: Human-readable saved map name.
        created_at: ISO timestamp for save creation.
        updated_at: ISO timestamp for the latest save update.
        revision: Save document revision number.
        grid_bounds: Inclusive saved map bounds.
        tile_count: Number of serialized tiles.
        floor_object_count: Number of serialized floor objects.
    """

    id: str = Field(description="Stable saved map identifier.")
    name: str = Field(description="Human-readable saved map name.")
    created_at: str = Field(description="ISO timestamp for save creation.")
    updated_at: str = Field(description="ISO timestamp for the latest save update.")
    revision: int = Field(default=1, description="Save document revision number.")
    grid_bounds: MapEditorGridBounds = Field(description="Inclusive saved map bounds.")
    tile_count: int = Field(description="Number of serialized tiles.")
    floor_object_count: int = Field(description="Number of serialized floor objects.")


class MapEditorSavedMapDocument(BaseModel):
    """Durable editor map document.

    Attributes:
        schema_version: Saved map schema version.
        metadata: Saved map metadata.
        snapshot: Entity-free map snapshot.
        object_placements: Reloadable object placement records.
    """

    schema_version: int = Field(default=1, description="Saved map schema version.")
    metadata: MapEditorSavedMapMetadata = Field(description="Saved map metadata.")
    snapshot: MapEditorMapSnapshot = Field(description="Entity-free map snapshot.")
    object_placements: List[MapEditorSavedObjectPlacement] = Field(
        default_factory=list,
        description="Reloadable object placement records.",
    )


class MapEditorSavedMapList(BaseModel):
    """List of saved editor maps.

    Attributes:
        maps: Saved map metadata entries.
    """

    maps: List[MapEditorSavedMapMetadata] = Field(description="Saved map metadata entries.")


class MapEditorCreateMapRequest(BaseModel):
    """Request to create or reset the editor map.

    Attributes:
        source: Whether to build from scratch or from a preset.
        width: Scratch-map width in tiles.
        height: Scratch-map height in tiles.
        origin: Scratch-map origin position.
        default_tile: Terrain name used for scratch-map tiles.
        default_light: Initial light level for scratch-map tiles.
        preset_id: Optional preset identifier when source is preset.
        include_entities: Whether preset creation should include entity fixtures.
    """

    source: Literal["scratch", "preset"] = Field(default="scratch", description="Whether to build from scratch or from a preset.")
    width: int = Field(default=16, description="Scratch-map width in tiles.")
    height: int = Field(default=16, description="Scratch-map height in tiles.")
    origin: Tuple[int, int] = Field(default=(0, 0), description="Scratch-map origin position.")
    default_tile: str = Field(default="Floor", description="Terrain name used for scratch-map tiles.")
    default_light: int = Field(default=1, description="Initial light level for scratch-map tiles.")
    preset_id: Optional[str] = Field(default=None, description="Optional preset identifier when source is preset.")
    include_entities: bool = Field(default=False, description="Whether preset creation should include entity fixtures.")


class MapEditorTilePatch(BaseModel):
    """Single editor tile update.

    Attributes:
        x: Tile x-coordinate to patch.
        y: Tile y-coordinate to patch.
        type: Optional replacement terrain type.
        light_level: Optional replacement light level.
        directional_channel: Directional blocking channel to patch.
        direction: Directional side to patch.
        passable: Whether the patched directional side is passable.
    """

    x: int = Field(description="Tile x-coordinate to patch.")
    y: int = Field(description="Tile y-coordinate to patch.")
    type: Optional[str] = Field(default=None, description="Optional replacement terrain type.")
    light_level: Optional[int] = Field(default=None, description="Optional replacement light level.")
    directional_channel: Optional[Literal["movement", "vision", "light", "propagation"]] = Field(
        default=None,
        description="Directional blocking channel to patch.",
    )
    direction: Optional[Literal["north", "south", "east", "west"]] = Field(
        default=None,
        description="Directional side to patch.",
    )
    passable: Optional[bool] = Field(default=None, description="Whether the patched directional side is passable.")


class MapEditorTilePatchRequest(BaseModel):
    """Batch tile update request.

    Attributes:
        tiles: Tile patches to apply.
    """

    tiles: List[MapEditorTilePatch] = Field(description="Tile patches to apply.")


class MapEditorObjectPlaceRequest(BaseModel):
    """Request to place a catalog object on the editor map.

    Attributes:
        catalog_id: Catalog identifier for the object to place.
        position: Grid position where the object should be placed.
        options: Object-specific placement options.
    """

    catalog_id: str = Field(description="Catalog identifier for the object to place.")
    position: Tuple[int, int] = Field(description="Grid position where the object should be placed.")
    options: Dict[str, Any] = Field(default_factory=dict, description="Object-specific placement options.")


class MapEditorObjectDeleteRequest(BaseModel):
    """Request to delete editor objects by UUID or tile position.

    Attributes:
        object_uuid: Optional object UUID to delete.
        position: Optional tile position whose objects should be deleted.
    """

    object_uuid: Optional[str] = Field(default=None, description="Optional object UUID to delete.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Optional tile position whose objects should be deleted.")

ProjectileCatalogType = Literal["bolt", "ray", "orb", "beam", "dart", "spray", "radiance", "touch", "rain"]
AoeCatalogShapeType = Literal["sphere", "cone", "line", "cube", "cylinder"]
SpellCatalogRangeType = Literal["self", "touch", "ranged"]
SpellCatalogRouteHint = Literal[
    "self", "touch", "single_projectile", "missile_volley", "aoe",
    "aoe_projectile", "beam", "ray", "none"
]


class SpellCatalogSavingThrow(BaseModel):
    """Saving throw metadata for a catalog spell.

    Attributes:
        ability: Short ability label used for the saving throw.
        dc_source: Source used to compute the save DC.
    """

    ability: str = Field(description="Short ability label used for the saving throw.")
    dc_source: Optional[str] = Field(default=None, description="Source used to compute the save DC.")


class SpellCatalogMultiTarget(BaseModel):
    """Multi-target and projectile semantics for a catalog spell.

    Attributes:
        min_targets: Minimum number of targets required by the spell.
        max_targets: Maximum number of targets the spell can affect.
        allow_same_target: Whether multiple projectiles may choose the same target.
        projectiles_per_cast: Number of projectiles created by one base cast.
    """

    min_targets: Optional[int] = Field(default=None, description="Minimum number of targets required by the spell.")
    max_targets: Optional[int] = Field(default=None, description="Maximum number of targets the spell can affect.")
    allow_same_target: Optional[bool] = Field(default=None, description="Whether multiple projectiles may choose the same target.")
    projectiles_per_cast: Optional[int] = Field(default=None, description="Number of projectiles created by one base cast.")


class SpellCatalogVfx(BaseModel):
    """Visual routing hints derived from spell rules metadata.

    Attributes:
        projectile_type: Normalized projectile style for visual routing.
        aoe_shape_type: Normalized area-of-effect shape for visual routing.
        route_hint: Recommended animation route category.
        recommended_asset_tags: Asset tags inferred from rules metadata.
    """

    projectile_type: Optional[ProjectileCatalogType] = Field(default=None, description="Normalized projectile style for visual routing.")
    aoe_shape_type: Optional[AoeCatalogShapeType] = Field(default=None, description="Normalized area-of-effect shape for visual routing.")
    route_hint: SpellCatalogRouteHint = Field(description="Recommended animation route category.")
    recommended_asset_tags: List[str] = Field(default_factory=list, description="Asset tags inferred from rules metadata.")


class SpellCatalogEntry(BaseModel):
    """Design-time spell metadata exposed by the backend catalog.

    Attributes:
        id: Stable normalized spell identifier.
        name: Display name for the spell.
        aliases: Alternate names accepted by tooling or clients.
        level: Spell level, with zero representing cantrips.
        school: Spell school name.
        description: Optional spell description text.
        action_category: Fixed action category for spell catalog entries.
        target_type: Engine target type used by the spell action.
        range_type: Normalized spell range category.
        range_ft: Spell range in feet when applicable.
        projectile_type: Normalized projectile style when present.
        aoe_shape_type: Normalized area-of-effect shape when present.
        aoe_radius_ft: Area radius in feet when applicable.
        aoe_length_ft: Area length in feet when applicable.
        aoe_width_ft: Area width in feet when applicable.
        damage_types: Damage type labels inferred from the spell.
        healing: Whether the spell restores hit points.
        attack_roll: Whether the spell uses a spell attack roll.
        saving_throw: Saving throw metadata when the spell prompts a save.
        concentration: Whether the spell requires concentration.
        ritual: Whether the spell can be cast as a ritual.
        verbal: Whether the spell has a verbal component.
        somatic: Whether the spell has a somatic component when known.
        material: Whether the spell has a material component when known.
        classes: Class names associated with the spell in catalog metadata.
        subclasses: Subclass names associated with the spell in catalog metadata.
        source: Source label for the catalog metadata.
        multi_target: Multi-target metadata when the spell supports it.
        vfx: Visual routing hints for the spell.
    """

    id: str = Field(description="Stable normalized spell identifier.")
    name: str = Field(description="Display name for the spell.")
    aliases: List[str] = Field(default_factory=list, description="Alternate names accepted by tooling or clients.")
    level: int = Field(description="Spell level, with zero representing cantrips.")
    school: str = Field(description="Spell school name.")
    description: Optional[str] = Field(default=None, description="Optional spell description text.")
    action_category: Literal["spell"] = Field(default="spell", description="Fixed action category for spell catalog entries.")
    target_type: str = Field(description="Engine target type used by the spell action.")
    range_type: Optional[SpellCatalogRangeType] = Field(default=None, description="Normalized spell range category.")
    range_ft: Optional[int] = Field(default=None, description="Spell range in feet when applicable.")
    projectile_type: Optional[ProjectileCatalogType] = Field(default=None, description="Normalized projectile style when present.")
    aoe_shape_type: Optional[AoeCatalogShapeType] = Field(default=None, description="Normalized area-of-effect shape when present.")
    aoe_radius_ft: Optional[int] = Field(default=None, description="Area radius in feet when applicable.")
    aoe_length_ft: Optional[int] = Field(default=None, description="Area length in feet when applicable.")
    aoe_width_ft: Optional[int] = Field(default=None, description="Area width in feet when applicable.")
    damage_types: List[str] = Field(default_factory=list, description="Damage type labels inferred from the spell.")
    healing: bool = Field(default=False, description="Whether the spell restores hit points.")
    attack_roll: bool = Field(default=False, description="Whether the spell uses a spell attack roll.")
    saving_throw: Optional[SpellCatalogSavingThrow] = Field(default=None, description="Saving throw metadata when the spell prompts a save.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    ritual: bool = Field(default=False, description="Whether the spell can be cast as a ritual.")
    verbal: bool = Field(default=True, description="Whether the spell has a verbal component.")
    somatic: Optional[bool] = Field(default=None, description="Whether the spell has a somatic component when known.")
    material: Optional[bool] = Field(default=None, description="Whether the spell has a material component when known.")
    classes: List[str] = Field(default_factory=list, description="Class names associated with the spell in catalog metadata.")
    subclasses: List[str] = Field(default_factory=list, description="Subclass names associated with the spell in catalog metadata.")
    source: Optional[str] = Field(default=None, description="Source label for the catalog metadata.")
    multi_target: Optional[SpellCatalogMultiTarget] = Field(default=None, description="Multi-target metadata when the spell supports it.")
    vfx: Optional[SpellCatalogVfx] = Field(default=None, description="Visual routing hints for the spell.")


class SpellCatalogResponse(BaseModel):
    """All backend spell templates known to the engine.

    Attributes:
        version: Catalog schema or generation version.
        generated_at: Optional generation timestamp.
        spells: Spell catalog entries known to the backend.
    """

    version: str = Field(description="Catalog schema or generation version.")
    generated_at: Optional[str] = Field(default=None, description="Optional generation timestamp.")
    spells: List[SpellCatalogEntry] = Field(description="Spell catalog entries known to the backend.")


class MapEditorCatalogEntry(BaseModel):
    """Normalized placeable editor catalog entry.

    Attributes:
        id: Stable catalog identifier.
        name: Display name shown in editor tools.
        group: High-level catalog group.
        category: Object, terrain, loot, or preset category.
        source_module: Runtime module that provides the catalog entry.
        stability: Whether the catalog entry is stable, candidate, or demo-only.
        placement: Placement mode used by the editor.
        map_char: Optional map glyph hint.
        visual_item_name: Optional renderer asset name.
        flags: Capability and behavior flags used by the editor.
        actions: Object actions exposed by the catalog entry.
        default_state: Default state applied when placing the entry.
    """

    id: str = Field(description="Stable catalog identifier.")
    name: str = Field(description="Display name shown in editor tools.")
    group: str = Field(description="High-level catalog group.")
    category: str = Field(description="Object, terrain, loot, or preset category.")
    source_module: str = Field(description="Runtime module that provides the catalog entry.")
    stability: Literal["stable", "candidate", "demo"] = Field(
        default="stable",
        description="Whether the catalog entry is stable, candidate, or demo-only.",
    )
    placement: str = Field(default="single_tile", description="Placement mode used by the editor.")
    map_char: Optional[str] = Field(default=None, description="Optional map glyph hint.")
    visual_item_name: Optional[str] = Field(default=None, description="Optional renderer asset name.")
    flags: Dict[str, Any] = Field(default_factory=dict, description="Capability and behavior flags used by the editor.")
    actions: List[str] = Field(default_factory=list, description="Object actions exposed by the catalog entry.")
    default_state: Dict[str, Any] = Field(default_factory=dict, description="Default state applied when placing the entry.")


class MapEditorCatalog(BaseModel):
    """All mapeditor presets, terrain, objects, and loot known to the backend.

    Attributes:
        presets: Map preset catalog entries.
        tiles: Terrain tile catalog entries.
        objects: Placeable object catalog entries.
        loot: Loot and item catalog entries.
    """

    presets: List[MapEditorCatalogEntry] = Field(description="Map preset catalog entries.")
    tiles: List[MapEditorCatalogEntry] = Field(description="Terrain tile catalog entries.")
    objects: List[MapEditorCatalogEntry] = Field(description="Placeable object catalog entries.")
    loot: List[MapEditorCatalogEntry] = Field(description="Loot and item catalog entries.")


class MapEditorWalkabilityCell(BaseModel):
    """Walkability status for one editor map cell.

    Attributes:
        x: Cell x-coordinate.
        y: Cell y-coordinate.
        walkable: Whether the cell can be entered.
        blocker: Optional blocker name when the cell is not walkable.
    """

    x: int = Field(description="Cell x-coordinate.")
    y: int = Field(description="Cell y-coordinate.")
    walkable: bool = Field(description="Whether the cell can be entered.")
    blocker: Optional[str] = Field(default=None, description="Optional blocker name when the cell is not walkable.")


class MapEditorWalkabilityResponse(BaseModel):
    """Walkability layer response.

    Attributes:
        cells: Walkability cells for the current editor map.
    """

    cells: List[MapEditorWalkabilityCell] = Field(description="Walkability cells for the current editor map.")


class MapEditorVisibilityCell(BaseModel):
    """Visibility-blocking status for one editor map cell.

    Attributes:
        x: Cell x-coordinate.
        y: Cell y-coordinate.
        blocks_visibility: Whether the cell blocks line of sight.
        blocker: Optional blocker name when visibility is blocked.
    """

    x: int = Field(description="Cell x-coordinate.")
    y: int = Field(description="Cell y-coordinate.")
    blocks_visibility: bool = Field(description="Whether the cell blocks line of sight.")
    blocker: Optional[str] = Field(default=None, description="Optional blocker name when visibility is blocked.")


class MapEditorVisibilityResponse(BaseModel):
    """Visibility layer response.

    Attributes:
        cells: Visibility cells for the current editor map.
    """

    cells: List[MapEditorVisibilityCell] = Field(description="Visibility cells for the current editor map.")


class MapEditorLightCell(BaseModel):
    """Objective light level for one editor map cell.

    Attributes:
        x: Cell x-coordinate.
        y: Cell y-coordinate.
        light_level: Resolved light level enum value.
    """

    x: int = Field(description="Cell x-coordinate.")
    y: int = Field(description="Cell y-coordinate.")
    light_level: int = Field(description="Resolved light level enum value.")


class MapEditorLightResponse(BaseModel):
    """Objective light layer response.

    Attributes:
        cells: Light-level cells for the current editor map.
    """

    cells: List[MapEditorLightCell] = Field(description="Light-level cells for the current editor map.")


class CreateSessionRequest(BaseModel):
    """Request to create a new player session.

    Attributes:
        player_type: Controller type for the session, such as human or codex.
        name: Optional display name for the session.
    """

    player_type: str = Field(description="Controller type for the session, such as human or codex.")
    name: Optional[str] = Field(default=None, description="Optional display name for the session.")


class CreateSessionResponse(BaseModel):
    """Response from creating a session.

    Attributes:
        session_id: Stable session identifier.
        player_type: Controller type assigned to the session.
        name: Display name assigned to the session.
    """

    session_id: str = Field(description="Stable session identifier.")
    player_type: str = Field(description="Controller type assigned to the session.")
    name: str = Field(description="Display name assigned to the session.")


class SessionPingResponse(BaseModel):
    """Response from session ping.

    Attributes:
        status: Ping result status.
        session_id: Stable session identifier.
        connection_status: Current connection status label.
        is_my_turn: Whether this session controls the acting entity.
        active_entity_uuid: UUID of the active entity, if any.
        active_entity_name: Name of the active entity, if any.
        controlled_entities: Entity UUIDs controlled by the session.
    """

    status: str = Field(description="Ping result status.")
    session_id: str = Field(description="Stable session identifier.")
    connection_status: str = Field(description="Current connection status label.")
    is_my_turn: bool = Field(description="Whether this session controls the acting entity.")
    active_entity_uuid: Optional[str] = Field(description="UUID of the active entity, if any.")
    active_entity_name: Optional[str] = Field(description="Name of the active entity, if any.")
    controlled_entities: List[str] = Field(description="Entity UUIDs controlled by the session.")


class JoinGameRequest(BaseModel):
    """Request to join a game with a session.

    Attributes:
        session_id: Session joining the game.
        entity_uuids: Optional entity UUIDs to control.
        entity_uuid: Optional single entity UUID convenience alias.
        faction: Optional faction whose entities should be controlled.
        observer_entity_uuids: Explicit observer union for a zero-control session.
        active_observer_uuid: Observer selected for focus within that union.
    """

    session_id: str = Field(description="Session joining the game.")
    entity_uuids: Optional[List[str]] = Field(default=None, description="Optional entity UUIDs to control.")
    entity_uuid: Optional[str] = Field(default=None, description="Optional single entity UUID to control.")
    faction: Optional[str] = Field(default=None, description="Optional faction whose entities should be controlled.")
    observer_entity_uuids: Optional[List[str]] = Field(
        default=None,
        description="Explicit subjective observer union for a zero-control observer session.",
    )
    active_observer_uuid: Optional[str] = Field(
        default=None,
        description="Observer selected for focus within the explicit observer union.",
    )

    def requested_entity_uuids(self) -> List[str]:
        """Return requested entity UUIDs from list and single-entity inputs.

        Returns:
            De-duplicated entity UUID strings in request order.
        """
        requested: List[str] = []
        for uuid_str in self.entity_uuids or []:
            if uuid_str not in requested:
                requested.append(uuid_str)
        if self.entity_uuid and self.entity_uuid not in requested:
            requested.append(self.entity_uuid)
        return requested

    def requested_observer_entity_uuids(self) -> List[str]:
        """Return the de-duplicated explicit observer UUID strings in request order."""
        requested: List[str] = []
        for uuid_str in self.observer_entity_uuids or []:
            if uuid_str not in requested:
                requested.append(uuid_str)
        return requested


class JoinGameResponse(BaseModel):
    """Response from joining a game.

    Attributes:
        success: Whether the join request succeeded.
        game_id: Game identifier joined by the session.
        session_id: Session that joined the game.
        controlled_entities: Entity UUIDs controlled after joining.
        observer_entities: Entity UUIDs authorized as subjective observers.
        active_observer_uuid: Observer selected for focus within that union.
        message: Human-readable join result.
    """

    success: bool = Field(description="Whether the join request succeeded.")
    game_id: str = Field(description="Game identifier joined by the session.")
    session_id: str = Field(description="Session that joined the game.")
    controlled_entities: List[str] = Field(description="Entity UUIDs controlled after joining.")
    observer_entities: List[str] = Field(
        default_factory=list,
        description="Entity senses contributing to this session's subjective perspective.",
    )
    active_observer_uuid: Optional[str] = Field(
        default=None,
        description="Observer selected for observer-relative presentation.",
    )
    message: str = Field(description="Human-readable join result.")


GameCreationControllerKind = Literal["human", "ai", "codex"]
GameCreationOpeningSide = Literal["initiative", "side_a", "side_b"]
AIExecutionKind = Literal["in_process", "registered_provider"]


class GameCreationAIPolicyOption(BaseModel):
    """One globally unique policy selectable through ``controller='ai'``."""

    descriptor: PolicyDescriptor = Field(
        description="Stable policy identity and player-facing description.",
    )
    execution: AIExecutionKind = Field(
        description="Whether policy logic runs in process or at a registered provider.",
    )
    provider_id: Optional[str] = Field(
        default=None,
        description="Owning provider for registered policies; absent for in-process policies.",
    )
    capacity: Optional[int] = Field(
        default=None,
        ge=1,
        description="Provider assignment capacity captured at catalog time.",
    )
    active_assignments: Optional[int] = Field(
        default=None,
        ge=0,
        description="Provider assignments known active at catalog time.",
    )
    available_capacity: Optional[int] = Field(
        default=None,
        ge=0,
        description="Advisory capacity remaining at catalog time.",
    )

    @model_validator(mode="after")
    def validate_execution_metadata(self) -> "GameCreationAIPolicyOption":
        provider_fields = (
            self.provider_id,
            self.capacity,
            self.active_assignments,
            self.available_capacity,
        )
        if self.execution == "in_process":
            if any(value is not None for value in provider_fields):
                raise ValueError(
                    "in-process policies cannot carry provider metadata"
                )
            return self
        if any(value is None for value in provider_fields):
            raise ValueError(
                "registered-provider policies require complete provider metadata"
            )
        assert self.capacity is not None
        assert self.active_assignments is not None
        assert self.available_capacity is not None
        if self.active_assignments > self.capacity:
            raise ValueError("active assignments exceed provider capacity")
        if self.available_capacity != self.capacity - self.active_assignments:
            raise ValueError("available provider capacity is inconsistent")
        return self


class GameCreationPreset(BaseModel):
    """Historical scenario recipe exposed as a quick game-creation preset.

    Attributes:
        arena_id: Stable historical scenario identifier.
        title: Human-readable scenario title.
        tags: Searchable mechanics and content labels.
        expected_pressure: Tactical behaviors the scenario exercises.
        map_notes: Important terrain and object facts.
        recipe: Canonical composition recipe used to reconstruct the scenario.
    """

    arena_id: str = Field(description="Stable historical scenario identifier.")
    title: str = Field(description="Human-readable scenario title.")
    tags: List[str] = Field(description="Searchable mechanics and content labels.")
    expected_pressure: List[str] = Field(description="Tactical behaviors exercised by the scenario.")
    map_notes: List[str] = Field(description="Important terrain and object facts.")
    recipe: LegacyScenarioRecipe = Field(description="Canonical composition recipe for the scenario.")


class GameCreationCatalogResponse(BaseModel):
    """Canonical content and controller choices for the game-creation UI."""

    schema_version: int = Field(default=1, description="Game-creation contract schema version.")
    controllers: List[GameCreationControllerKind] = Field(description="Supported side controller kinds.")
    ai_policies: List[GameCreationAIPolicyOption] = Field(
        description=(
            "All globally unique AI policies currently selectable by stable id, "
            "including in-process and registered-provider implementations."
        ),
    )
    opening_sides: List[GameCreationOpeningSide] = Field(description="Supported initiative-opening policies.")
    hero_configurations: List[SideConfigurationSpec] = Field(description="Canonical hero-side configurations.")
    monster_configurations: List[SideConfigurationSpec] = Field(description="Canonical monster-party configurations.")
    battlefields: List[BattlefieldSpec] = Field(description="Canonical battlefield definitions.")
    deployments: List[DeploymentSpec] = Field(description="Canonical spawn formations.")
    presets: List[GameCreationPreset] = Field(description="Historical scenario quick presets.")


class GameCreationPreflightRequest(BaseModel):
    """Four-part composed scenario selection checked without mutating game state."""

    hero_configuration_id: str = Field(description="Hero configuration catalog identifier.")
    monster_configuration_id: str = Field(description="Monster-party configuration catalog identifier.")
    battlefield_id: str = Field(description="Battlefield catalog identifier.")
    deployment_id: str = Field(description="Deployment catalog identifier.")


class GameCreationPresetScenario(BaseModel):
    """Historical scenario selected by stable preset identifier."""

    kind: Literal["preset"] = Field(default="preset", description="Scenario-selection discriminator.")
    arena_id: str = Field(description="Historical scenario preset identifier.")


class GameCreationComposedScenario(GameCreationPreflightRequest):
    """Custom scenario assembled from four canonical component identifiers."""

    kind: Literal["composed"] = Field(default="composed", description="Scenario-selection discriminator.")


GameCreationScenario = Annotated[
    Union[GameCreationPresetScenario, GameCreationComposedScenario],
    Field(discriminator="kind"),
]


class GameCreationSideRequest(BaseModel):
    """Requested controller assignment for one complete combat side."""

    controller: GameCreationControllerKind = Field(description="Controller kind assigned to every entity on the side.")
    name: str = Field(min_length=1, max_length=80, description="Participant display name.")
    policy_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=160,
        description=(
            "Globally unique policy used by an AI side or retained behind a "
            "Codex claim. Omit for the bundled in-process basic policy."
        ),
    )


class GameCreationStartRequest(BaseModel):
    """Atomic scenario and controller assignment request."""

    scenario: GameCreationScenario = Field(description="Preset or composed scenario selection.")
    side_a: GameCreationSideRequest = Field(description="Controller assignment for the hero side.")
    side_b: GameCreationSideRequest = Field(description="Controller assignment for the opposition side.")
    opening_side: GameCreationOpeningSide = Field(
        default="initiative",
        description="Whether rolled initiative, Side A, or Side B opens combat.",
    )
    codex_lease_seconds: float = Field(
        default=600.0,
        gt=0,
        le=86400,
        description="Takeover lease duration for configured Codex sides.",
    )


class GameCreationEntityAssignment(BaseModel):
    """Control-plane identity for one entity assigned to a created side."""

    entity_uuid: str = Field(description="Entity UUID assigned to the side.")
    entity_name: str = Field(description="Entity display label retained by the game directory.")
    faction: Optional[str] = Field(
        default=None,
        description="Faction identifier retained for directory assignment metadata.",
    )


class GameCreationSideResult(BaseModel):
    """Resolved control-plane assignments and attach data for one side."""

    side_id: Literal["side_a", "side_b"] = Field(description="Stable side identifier.")
    title: str = Field(description="Resolved side configuration title.")
    controller: GameCreationControllerKind = Field(description="Configured controller kind.")
    participant_name: str = Field(description="Configured participant display name.")
    entity_assignments: List[GameCreationEntityAssignment] = Field(
        description="Stable identity rows assigned to the side; gameplay facts arrive through replication.",
    )
    policy_id: Optional[str] = Field(
        default=None,
        description=(
            "Resolved policy assigned to this side, including the policy retained "
            "behind a Codex claim. Human sides have no policy."
        ),
    )
    policy_execution: Optional[AIExecutionKind] = Field(
        default=None,
        description="Resolved policy execution boundary; absent for human sides.",
    )
    provider_id: Optional[str] = Field(
        default=None,
        description="Registered provider owning the resolved policy, when external.",
    )
    codex_session_id: Optional[str] = Field(default=None, description="Configured Codex session UUID.")
    takeover_claim_id: Optional[str] = Field(default=None, description="Configured Codex takeover claim UUID.")
    takeover_expires_at: Optional[float] = Field(default=None, description="Codex claim expiry timestamp.")


class GameCreationStartResponse(BaseModel):
    """Resolved prepared game and side assignments.

    Creation never starts an encounter. A joined client first opens its
    canonical replication bootstrap, then explicitly activates this prepared
    game with the exact bootstrap identity.
    """

    schema_version: int = Field(default=1, description="Game-creation contract schema version.")
    scenario_kind: Literal["preset", "composed"] = Field(description="Scenario-selection kind used for the match.")
    preset_arena_id: Optional[str] = Field(default=None, description="Historical preset identifier when selected.")
    encounter_uuid: str = Field(description="Created encounter UUID.")
    game_id: str = Field(description="Created active game UUID.")
    encounter_name: str = Field(description="Created encounter display name.")
    opening_side: GameCreationOpeningSide = Field(description="Applied initiative-opening policy.")
    compatibility: CompatibilityReport = Field(description="Compatibility report used to admit the scenario.")
    side_a: GameCreationSideResult = Field(description="Resolved Side A assignment.")
    side_b: GameCreationSideResult = Field(description="Resolved Side B assignment.")
    status: Literal["prepared"] = Field(
        default="prepared",
        description="Prepared lifecycle boundary; no encounter event has run.",
    )


class GameCreationActivateRequest(BaseModel):
    """Release one prepared game using an exact joined replication identity."""

    session_id: str = Field(min_length=1, description="Joined runtime session authorizing activation.")
    expected_source_stream_id: str = Field(
        min_length=1,
        description="Encounter stream identity returned by replication bootstrap.",
    )
    expected_generation_id: str = Field(
        min_length=1,
        description="Engine generation identity returned by replication bootstrap.",
    )
    expected_perspective_epoch_id: str = Field(
        min_length=1,
        description="Subjective authority epoch returned by replication bootstrap.",
    )


class GameCreationActivateResponse(BaseModel):
    """Idempotent acknowledgement for the prepared-to-active transition."""

    status: Literal["activated", "already_active"] = Field(
        description="Whether this request crossed the activation boundary.",
    )
    game_id: str = Field(description="Activated engine game identity.")
    encounter_uuid: str = Field(description="Activated encounter identity.")


class AIProviderRegistrationRequest(BaseModel):
    """Deployment-admin request to authenticate one external policy provider."""

    provider_id: str = Field(
        min_length=1,
        pattern=r"^[a-z][a-z0-9_.-]*$",
        description="Expected provider identity; the handshake remains authority.",
    )
    base_url: str = Field(
        min_length=1,
        description="Root HTTP(S) endpoint exposing the provider protocol.",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError(
                "base_url must be a root HTTP(S) URL without credentials, "
                "query, fragment, or path"
            )
        return value.rstrip("/")


class AIProviderCatalogEntry(BaseModel):
    """Authenticated provider identity and current assignment capacity."""

    provider_id: str = Field(description="Handshake-authenticated provider identity.")
    base_url: str = Field(description="Registered provider root URL.")
    protocol_version: int = Field(ge=1, description="External AI protocol version.")
    protocol_hash: str = Field(
        min_length=64,
        max_length=64,
        description="Complete external AI wire-contract hash.",
    )
    policies: List[PolicyDescriptor] = Field(
        description="Handshake-advertised policies owned by this provider.",
    )
    capacity: int = Field(ge=1, description="Provider assignment capacity.")
    active_assignments: int = Field(
        ge=0,
        description="Assignments currently owned by this server connection.",
    )
    available_capacity: int = Field(
        ge=0,
        description="Current remaining assignment capacity.",
    )


class AIProviderCatalogResponse(BaseModel):
    """Current registered-provider catalog."""

    providers: List[AIProviderCatalogEntry] = Field(
        description="Providers ordered by stable provider identity.",
    )


class AIProviderDeleteResponse(BaseModel):
    """Acknowledgement after a provider and its idle client are removed."""

    status: Literal["unregistered"] = "unregistered"
    provider_id: str = Field(description="Removed provider identity.")


class StandaloneGameSessionSummary(BaseModel):
    """One reconnectable session exposed by a standalone game server."""

    session_id: str = Field(description="Runtime session identifier.")
    player_type: str = Field(description="Session controller type.")
    name: str = Field(description="Session display name.")
    connection_status: str = Field(description="Current session connection state.")
    controlled_entities: List[str] = Field(description="Entity UUIDs owned by the session.")
    is_their_turn: bool = Field(description="Whether this session owns the active turn.")


class StandaloneGameStatusResponse(BaseModel):
    """Typed directory row for the single hot game held by a standalone server."""

    active: bool = Field(description="Whether the server currently holds a game session.")
    game_id: Optional[str] = Field(default=None, description="Current engine game UUID.")
    encounter_active: bool = Field(description="Whether the current encounter remains active.")
    active_entity_uuid: Optional[str] = Field(
        default=None,
        description="Entity currently holding the turn.",
    )
    sessions: List[StandaloneGameSessionSummary] = Field(
        default_factory=list,
        description="Runtime sessions available for local reconnection.",
    )
    creation: Optional[GameCreationStartResponse] = Field(
        default=None,
        description="Resolved creation metadata needed to reconstruct the client scene.",
    )


class AgentSessionEntityRow(BaseModel):
    """Entity label owned by an AI-observable session.

    Attributes:
        entity_uuid: Controlled entity UUID.
        entity_name: Controlled entity display name.
        faction: Controlled entity faction, if any.
        controller_type: Encounter controller type assigned to the entity.
        is_active_actor: Whether this entity is currently the active actor.
    """

    entity_uuid: str = Field(description="Controlled entity UUID.")
    entity_name: str = Field(description="Controlled entity display name.")
    faction: Optional[str] = Field(default=None, description="Controlled entity faction, if any.")
    controller_type: Optional[str] = Field(default=None, description="Encounter controller type assigned to the entity.")
    is_active_actor: bool = Field(description="Whether this entity is currently the active actor.")


class AgentSessionRow(BaseModel):
    """Read-only AI session row for observer clients.

    Attributes:
        session_id: Stable session UUID.
        player_type: Session player type such as ai or codex.
        name: Session display name.
        connection_status: Current connection status.
        is_active_turn: Whether this session controls the active actor.
        active_controlled_entity_uuid: Active actor UUID when controlled by this session.
        active_controlled_entity_name: Active actor name when controlled by this session.
        controlled_entities: Controlled entity labels.
        agent_cursor: Current telemetry cursor for the session.
        earliest_agent_cursor: Earliest retained telemetry cursor.
        observation_cursor: Current subjective observation cursor when available.
        current_epoch_id: Cached active epoch id when available.
        takeover_claim_ids: Live takeover claims owned by this session.
    """

    session_id: str = Field(description="Stable session UUID.")
    player_type: str = Field(description="Session player type such as ai or codex.")
    name: str = Field(description="Session display name.")
    connection_status: str = Field(description="Current connection status.")
    is_active_turn: bool = Field(description="Whether this session controls the active actor.")
    active_controlled_entity_uuid: Optional[str] = Field(
        default=None,
        description="Active actor UUID when controlled by this session.",
    )
    active_controlled_entity_name: Optional[str] = Field(
        default=None,
        description="Active actor name when controlled by this session.",
    )
    controlled_entities: List[AgentSessionEntityRow] = Field(description="Controlled entity labels.")
    agent_cursor: int = Field(description="Current telemetry cursor for the session.")
    earliest_agent_cursor: int = Field(description="Earliest retained telemetry cursor.")
    observation_cursor: Optional[int] = Field(default=None, description="Current subjective observation cursor when available.")
    current_epoch_id: Optional[str] = Field(default=None, description="Cached active epoch id when available.")
    takeover_claim_ids: List[str] = Field(default_factory=list, description="Live takeover claims owned by this session.")


class AgentSessionListResponse(BaseModel):
    """Read-only AI session index for observer clients.

    Attributes:
        sessions: AI or Codex sessions that can expose agent telemetry.
        active_game_id: Active game UUID, if any.
        encounter_active: Whether the active game has an active encounter.
    """

    sessions: List[AgentSessionRow] = Field(description="AI or Codex sessions that can expose agent telemetry.")
    active_game_id: Optional[str] = Field(default=None, description="Active game UUID, if any.")
    encounter_active: bool = Field(description="Whether the active game has an active encounter.")


class AoEPreviewResult(BaseModel):
    """Result of an AoE position preview without execution.

    Attributes:
        success: Whether the preview request succeeded.
        message: Human-readable preview result.
        affected_positions: Grid positions affected by the preview.
        affected_entity_names: Names of entities affected by the preview.
        affected_count: Number of affected entities.
    """

    success: bool = Field(description="Whether the preview request succeeded.")
    message: str = Field(default="", description="Human-readable preview result.")
    affected_positions: List[Tuple[int, int]] = Field(default_factory=list, description="Grid positions affected by the preview.")
    affected_entity_names: List[str] = Field(default_factory=list, description="Names of entities affected by the preview.")
    affected_count: int = Field(default=0, description="Number of affected entities.")

class SimpleActionRequest(BaseModel):
    """Request body for simple session-gated actions.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity performing the action.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity performing the action.")


class PositionPreviewRequest(BaseModel):
    """Request for a non-mutating position-area preview.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity performing the action.
        action_name: Position-area action template name.
        position: Target grid position.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity performing the action.")
    action_name: str = Field(description="Action template name.")
    position: Tuple[int, int] = Field(description="Target grid position.")


class ExecuteByIndexRequest(BaseModel):
    """Request to execute action by template name + target index.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity performing the action.
        template_name: Action template name.
        target_index: Index from the action's valid target list.
        extra_target_uuids: Additional target UUIDs for multi-entity actions.
        prefer_safe: Whether movement should prefer safe paths when available.
        return_available_actions: Whether to include recomputed action rows in
            the response.
        include_timing: Whether to include server-side route timing.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity performing the action.")
    template_name: str = Field(description="Action template name.")
    target_index: int = Field(description="Index from the action's valid target list.")
    extra_target_uuids: Optional[List[str]] = Field(
        default=None,
        description="Additional target UUIDs for multi-entity actions.",
    )
    prefer_safe: bool = Field(default=True, description="Whether movement should prefer safe paths when available.")
    return_available_actions: bool = Field(
        default=True,
        description="Whether the response should include recomputed available actions.",
    )
    include_timing: bool = Field(
        default=False,
        description="Whether the response should include server-side route timing.",
    )


class ToggleHandlerRequest(BaseModel):
    """Request to toggle a handler's enabled state.

    Attributes:
        session_id: Session performing the toggle.
        enabled: Desired handler enabled state.
    """

    session_id: str = Field(description="Session performing the toggle.")
    enabled: bool = Field(description="Desired handler enabled state.")


class APIResourcePool(BaseModel):
    """Current and maximum values for a named finite resource."""

    current: int = Field(description="Current resource value.")
    max: int = Field(description="Maximum resource value.")


class APIAvailableActions(AvailableActionsResult):
    """Engine-discovered legal actions plus current resource summaries."""

    actions_remaining: int = Field(description="Actions currently available.")
    bonus_actions_remaining: int = Field(description="Bonus actions currently available.")
    reactions_remaining: int = Field(description="Reactions currently available.")
    extra_attacks_remaining: int = Field(description="Extra attacks currently available.")
    spell_slots: Dict[str, APIResourcePool] = Field(
        default_factory=dict,
        description="Spell-slot pools keyed by slot level.",
    )
    resources: Dict[str, APIResourcePool] = Field(
        default_factory=dict,
        description="Named custom action resources.",
    )


class APIServerTiming(BaseModel):
    """Server-side command phase timing returned on request."""

    command_type: str = Field(description="Command category being measured.")
    diagnostics_enabled: bool = Field(description="Whether detailed diagnostics were active.")
    total_ms: float = Field(description="Total command time in milliseconds.")
    phases: Dict[str, float] = Field(description="Accumulated phase durations in milliseconds.")
    phase_counts: Dict[str, int] = Field(description="Invocation count for each measured phase.")
    phase_max_ms: Dict[str, float] = Field(description="Maximum duration for each measured phase.")

class ActionResult(BaseModel):
    """Minimal acknowledgement of an action command.

    World state, presentation facts, and combat-log entries are delivered only
    by the canonical replication journal (or objective diagnostics for an
    authorized inspector). This response carries command outcome/control data
    and cursor barriers only.

    Attributes:
        success: Whether the action execution succeeded.
        message: Human-readable action result.
        event_type: Domain event type emitted by the action, if any.
        outcome_code: Stable machine-readable engine outcome, if any.
        turn_continues: Whether the acting entity's turn continues.
        encounter_ended: Whether the encounter ended because of the action.
        available_actions: Updated available actions after execution.
        server_timing: Optional server-side route timing.
        event_cursor_after: Event-history cursor after all side effects.
        combat_log_cursor_after: Combat-log cursor after all side effects.
    """

    success: bool = Field(description="Whether the action execution succeeded.")
    message: str = Field(description="Human-readable action result.")
    event_type: Optional[str] = Field(default=None, description="Domain event type emitted by the action, if any.")
    outcome_code: Optional[str] = Field(
        default=None,
        description="Stable machine-readable engine outcome, if any.",
    )
    turn_continues: bool = Field(default=True, description="Whether the acting entity's turn continues.")
    encounter_ended: bool = Field(default=False, description="Whether the encounter ended because of the action.")
    available_actions: Optional[APIAvailableActions] = Field(
        default=None,
        description="Updated available actions after execution.",
    )
    server_timing: Optional[APIServerTiming] = Field(
        default=None,
        description="Server-side route timing when requested.",
    )
    event_cursor_after: Optional[int] = Field(default=None, description="Event-history cursor after all side effects.")
    combat_log_cursor_after: Optional[int] = Field(default=None, description="Combat-log cursor after all side effects.")


class AdvanceEncounterResult(BaseModel):
    """Control acknowledgement after advancing to the next player boundary.

    Automated actions and their logs remain exclusively in canonical
    replication/diagnostics streams.

    Attributes:
        status: Advancement status label.
        entity_uuid: UUID of the next player-controlled entity, if any.
        entity_name: Name of the next player-controlled entity, if any.
        round: Current encounter round after advancing.
        turn_index: Current turn index after advancing.
        event_cursor_after: Event-history cursor after advancement.
        combat_log_cursor_after: Combat-log cursor after advancement.
    """

    status: str = Field(description="Advancement status label.")
    entity_uuid: Optional[str] = Field(default=None, description="UUID of the next player-controlled entity, if any.")
    entity_name: Optional[str] = Field(default=None, description="Name of the next player-controlled entity, if any.")
    round: Optional[int] = Field(default=None, description="Current encounter round after advancing.")
    turn_index: Optional[int] = Field(default=None, description="Current turn index after advancing.")
    event_cursor_after: Optional[int] = Field(default=None, description="Event-history cursor after advancement.")
    combat_log_cursor_after: Optional[int] = Field(default=None, description="Combat-log cursor after advancement.")


class TakeoverRequest(BaseModel):
    """Request to claim combatants for Codex control.

    Attributes:
        faction: Faction to claim when explicit entities are not provided.
        entity_uuids: Explicit entity UUIDs to claim.
        session_id: Existing Codex session to reuse.
        name: Display name for a newly created Codex session.
        force: Whether to replace an overlapping live takeover claim.
        lease_seconds: Number of seconds before the claim expires without a heartbeat.
    """

    faction: Optional[str] = Field(default="monsters", description="Faction to claim when explicit entities are not provided.")
    entity_uuids: Optional[List[str]] = Field(default=None, description="Explicit entity UUIDs to claim.")
    session_id: Optional[str] = Field(default=None, description="Existing Codex session to reuse.")
    name: str = Field(default="Codex Monsters", description="Display name for a newly created Codex session.")
    force: bool = Field(default=False, description="Whether to replace an overlapping live takeover claim.")
    lease_seconds: float = Field(default=120.0, gt=0, description="Seconds before claim expiry without heartbeat.")


class TakeoverEntityRow(BaseModel):
    """Entity row included in takeover claim responses."""

    entity_uuid: str = Field(description="Claimed entity UUID.")
    entity_name: str = Field(description="Claimed entity display name.")
    faction: Optional[str] = Field(default=None, description="Claimed entity faction.")
    previous_controller_uuid: str = Field(description="Controller UUID to restore on release.")
    previous_controller_type: Optional[str] = Field(default=None, description="Controller type to restore on release.")
    current_controller_type: Optional[str] = Field(default=None, description="Controller type currently assigned.")
    previous_owner_session_id: Optional[str] = Field(default=None, description="Previous owning session UUID.")


class TakeoverClaimResponse(BaseModel):
    """Serialized Codex takeover claim."""

    claim_id: str = Field(description="Takeover claim UUID.")
    session_id: str = Field(description="Codex session UUID controlling the claim.")
    name: str = Field(description="Claim display name.")
    faction: Optional[str] = Field(default=None, description="Faction claimed, when faction-based.")
    created_at: float = Field(description="Unix timestamp when the claim was created.")
    last_heartbeat_at: float = Field(description="Unix timestamp of the latest heartbeat.")
    lease_seconds: float = Field(description="Lease duration in seconds.")
    expires_at: float = Field(description="Unix timestamp when the claim expires.")
    is_expired: bool = Field(description="Whether the claim is expired at serialization time.")
    claimed_entities: List[TakeoverEntityRow] = Field(description="Entities controlled by the claim.")


class TakeoverListResponse(BaseModel):
    """List of active or known takeover claims."""

    claims: List[TakeoverClaimResponse] = Field(description="Takeover claim rows.")


class TakeoverHeartbeatResponse(BaseModel):
    """Response after refreshing a takeover claim."""

    status: str = Field(description="Heartbeat result status.")
    claim: TakeoverClaimResponse = Field(description="Refreshed claim.")


class TakeoverReleaseResponse(BaseModel):
    """Response after releasing a takeover claim."""

    status: str = Field(description="Release result status.")
    claim: Optional[TakeoverClaimResponse] = Field(default=None, description="Released claim, if found.")
    advance_result: Optional[AdvanceEncounterResult] = Field(default=None, description="Advancement result after release.")


class EventContractSummary(BaseModel):
    """Public identity and discriminators for the generated event contract."""

    contract_version: int = Field(description="Generated event-contract version.")
    contract_hash: str = Field(description="Generated event-contract content hash.")
    event_types: List[str] = Field(description="All semantic event type values.")
    wire_types: List[str] = Field(description="All concrete event wire discriminators.")
