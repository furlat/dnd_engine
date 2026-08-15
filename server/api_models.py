"""Pydantic DTOs for REST API serialization."""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union
from uuid import UUID

from dnd.core.base_actions import AvailableActionsResult, AvailableHandlerInfo
from dnd.core.content.battlefields import BattlefieldDefinition
from dnd.core.content.descriptors import ContentOrdering, ContentPresentation
from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.identities import ContentRef, validate_sha256
from dnd.core.content.encounters import (
    EncounterCompatibilityReport,
    EncounterDeploymentSpec,
    EncounterOpeningPolicy,
    EncounterRecipe,
    EncounterRosterRecipe,
)
from dnd.core.content.recipe_presets import ContentRecipePresetRef
from dnd.core.content.recipes import ContentRecipe
from dnd.core.events import AbilityName
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.core.traversal_connectors import (
    TraversalConnectorChangeOperation,
    TraversalConnectorDefinition,
)
from server.game_creation_preview_contracts import (
    GameCreationEncounterVisualPreviewResponse,
)
from server import world_contracts


class ServerCapabilitiesResponse(BaseModel):
    """Describe the only server topology supported by this process."""

    schema_version: Literal[1] = 1
    server_mode: Literal["single_game"] = Field(
        default="single_game",
        description="One process owns one current game.",
    )
    terminal_archive: Literal["filesystem"] = Field(
        default="filesystem",
        description="Terminal summaries and objective events use the local archive.",
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
    handler_uuid: UUID = Field(description="Exact handler identity.")
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
        connectors: Stable authored traversal connector definitions.
    """

    grid_bounds: MapEditorGridBounds = Field(description="Inclusive bounds for the serialized map.")
    tiles: List[world_contracts.APITile] = Field(description="Serialized tile snapshots.")
    floor_objects: List[world_contracts.APIFloorObject] = Field(
        default_factory=list,
        description="Serialized floor objects placed on the map.",
    )
    connectors: List[TraversalConnectorDefinition] = Field(
        default_factory=list,
        description="Stable authored connector definitions in authored-ID order.",
    )


class MapEditorSavedObjectPlacement(BaseModel):
    """Reloadable editor placement with exact construction and live state.

    Attributes:
        recipe: Self-authenticating construction recipe for the placed item.
        position: Grid position where the object should be restored.
        runtime_state: Mutable state restored after canonical materialization.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipe: ContentRecipe = Field(
        description="Self-authenticating construction recipe for the placed item.",
    )
    position: Tuple[int, int] = Field(description="Grid position where the object should be restored.")
    runtime_state: "MapEditorObjectRuntimeState" = Field(
        default_factory=lambda: MapEditorObjectRuntimeState(),
        description="Mutable state restored only after recipe materialization.",
    )


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
        connector_count: Number of serialized connector definitions.
        connector_digest: Digest of the ordered connector definitions.
    """

    id: str = Field(description="Stable saved map identifier.")
    name: str = Field(description="Human-readable saved map name.")
    created_at: str = Field(description="ISO timestamp for save creation.")
    updated_at: str = Field(description="ISO timestamp for the latest save update.")
    revision: int = Field(default=1, description="Save document revision number.")
    grid_bounds: MapEditorGridBounds = Field(description="Inclusive saved map bounds.")
    tile_count: int = Field(description="Number of serialized tiles.")
    floor_object_count: int = Field(description="Number of serialized floor objects.")
    connector_count: int = Field(
        default=0,
        description="Number of serialized authored connector definitions.",
    )
    connector_digest: str = Field(
        default=canonical_content_sha256([]),
        description="Digest of connector definitions in authored-ID order.",
    )

    @field_validator("connector_digest")
    @classmethod
    def _validate_connector_digest(cls, value: str) -> str:
        return validate_sha256(value, "connector_digest")


class MapEditorSavedMapDocument(BaseModel):
    """Durable editor map document.

    Attributes:
        schema_version: Saved map schema version.
        metadata: Saved map metadata.
        snapshot: Entity-free map snapshot.
        content_set_digest: Exact installed content set required for loading.
        object_placements: Reloadable exact-recipe object placement records.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[3] = Field(default=3, description="Saved map schema version.")
    content_set_digest: str = Field(
        description="Exact installed content set required for loading this map.",
    )
    metadata: MapEditorSavedMapMetadata = Field(description="Saved map metadata.")
    snapshot: MapEditorMapSnapshot = Field(description="Entity-free map snapshot.")
    object_placements: List[MapEditorSavedObjectPlacement] = Field(
        default_factory=list,
        description="Reloadable object placement records.",
    )

    @field_validator("content_set_digest")
    @classmethod
    def _validate_content_set_digest(cls, value: str) -> str:
        return validate_sha256(value, "content_set_digest")

    @model_validator(mode="after")
    def _validate_single_object_authority(self) -> "MapEditorSavedMapDocument":
        if self.snapshot.floor_objects:
            raise ValueError(
                "schema-3 snapshot.floor_objects must be empty; "
                "object_placements are the durable object authority",
            )
        if self.metadata.floor_object_count != len(self.object_placements):
            raise ValueError(
                "saved map floor_object_count must match object_placements",
            )
        if self.metadata.tile_count != len(self.snapshot.tiles):
            raise ValueError("saved map tile_count must match snapshot tiles")
        if self.metadata.connector_count != len(self.snapshot.connectors):
            raise ValueError("saved map connector_count must match snapshot connectors")
        connector_payload = [
            connector.model_dump(mode="json")
            for connector in sorted(
                self.snapshot.connectors,
                key=lambda connector: connector.authored_id,
            )
        ]
        if self.metadata.connector_digest != canonical_content_sha256(
            connector_payload
        ):
            raise ValueError("saved map connector_digest must match snapshot connectors")
        return self


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
        elevation_steps: Optional support elevation in five-foot steps.
        elevation_surface_kind: Optional replacement support-surface kind.
        slope_axis: Optional progressive support-surface axis.
        directional_channel: Directional blocking channel to patch.
        direction: Directional side to patch.
        passable: Whether the patched directional side is passable.
    """

    model_config = ConfigDict(extra="forbid")

    x: int = Field(description="Tile x-coordinate to patch.")
    y: int = Field(description="Tile y-coordinate to patch.")
    type: Optional[str] = Field(default=None, description="Optional replacement terrain type.")
    light_level: Optional[int] = Field(default=None, description="Optional replacement light level.")
    elevation_steps: Optional[StrictInt] = Field(
        default=None,
        description="Optional support elevation in five-foot steps.",
    )
    elevation_surface_kind: Optional[ElevationSurfaceKind] = Field(
        default=None,
        description="Optional replacement support-surface kind.",
    )
    slope_axis: Optional[SlopeAxis] = Field(
        default=None,
        description="Optional progressive surface axis; explicit null clears it.",
    )
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


class MapEditorConnectorUpsertRequest(BaseModel):
    """Create or replace one exact authored connector definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    definition: TraversalConnectorDefinition
    replace_existing: StrictBool = False


class MapEditorConnectorEnabledRequest(BaseModel):
    """Enable or disable one connector by stable authored identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    authored_id: str
    enabled: StrictBool


class MapEditorConnectorDeleteRequest(BaseModel):
    """Remove one connector by stable authored identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    authored_id: str


class MapEditorConnectorMutationResponse(BaseModel):
    """Authoritative connector mutation receipt plus the refreshed editor map."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    operation: TraversalConnectorChangeOperation
    connector_uuid: str
    authored_id: str
    connector_revision: StrictInt = Field(ge=1)
    connector_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    connector: Optional[world_contracts.APITraversalConnector] = None
    snapshot: MapEditorMapSnapshot


class MapEditorObjectRuntimeState(BaseModel):
    """Mutable placement facts kept outside authenticated construction.

    Attributes:
        is_open: Current door state after materialization.
        is_lit: Current fixed-light state after materialization.
        charges: Current finite-use budget after materialization.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_open: Optional[bool] = Field(
        default=None,
        description="Current door state applied after materialization.",
    )
    is_lit: Optional[bool] = Field(
        default=None,
        description="Current fixed-light state applied after materialization.",
    )
    charges: Optional[int] = Field(
        default=None,
        ge=-1,
        description="Current finite-use budget applied after materialization.",
    )


class MapEditorObjectPlaceRequest(BaseModel):
    """Request to place one exact content recipe on the editor map.

    Attributes:
        recipe: Self-authenticating item or environment construction recipe.
        content_set_digest: Installed content set expected by the author.
        position: Grid position where the object should be placed.
        runtime_state: Mutable state applied after construction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipe: ContentRecipe = Field(
        description="Self-authenticating item or environment construction recipe.",
    )
    content_set_digest: str = Field(
        description="Exact installed content set expected by the author.",
    )
    position: Tuple[int, int] = Field(description="Grid position where the object should be placed.")
    runtime_state: MapEditorObjectRuntimeState = Field(
        default_factory=MapEditorObjectRuntimeState,
        description="Mutable state applied only after recipe materialization.",
    )

    @field_validator("content_set_digest")
    @classmethod
    def _validate_content_set_digest(cls, value: str) -> str:
        return validate_sha256(value, "content_set_digest")


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
        ability: Full lowercase ability name used for the saving throw.
        dc_source: Source used to compute the save DC.
    """

    ability: AbilityName = Field(
        description="Full lowercase ability name used for the saving throw.",
    )
    dc_source: Literal["caster_spell_save_dc"] = Field(
        description="Source used to compute the save DC.",
    )


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
    """Authored visual routing hints for one spell.

    Attributes:
        projectile_type: Normalized projectile style for visual routing.
        aoe_shape_type: Normalized area-of-effect shape for visual routing.
        route_hint: Recommended animation route category.
        recommended_asset_tags: Reviewed asset search tags.
    """

    projectile_type: Optional[ProjectileCatalogType] = Field(default=None, description="Normalized projectile style for visual routing.")
    aoe_shape_type: Optional[AoeCatalogShapeType] = Field(default=None, description="Normalized area-of-effect shape for visual routing.")
    route_hint: SpellCatalogRouteHint = Field(description="Recommended animation route category.")
    recommended_asset_tags: List[str] = Field(default_factory=list, description="Reviewed asset search tags.")


class SpellCatalogEntry(BaseModel):
    """Design-time spell metadata exposed by the backend catalog.

    Attributes:
        id: Explicit catalog identifier; distinct from durable content identity.
        content_ref: Exact authored spell definition identity.
        name: Display name for the spell.
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
        aoe_height_ft: Area height in feet when applicable.
        damage_types: Authored damage type labels for the spell.
        healing: Whether the spell restores hit points.
        attack_roll: Whether the spell uses a spell attack roll.
        saving_throws: Ordered distinct saving throws used by the spell.
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

    id: str = Field(
        description=(
            "Explicit catalog identifier; distinct from durable content "
            "identity."
        ),
    )
    content_ref: ContentRef = Field(
        description="Exact authored spell definition identity.",
    )
    name: str = Field(description="Display name for the spell.")
    level: int = Field(description="Spell level, with zero representing cantrips.")
    school: str = Field(description="Spell school name.")
    description: str = Field(
        min_length=1,
        description="Authored spell description text.",
    )
    action_category: Literal["spell"] = Field(default="spell", description="Fixed action category for spell catalog entries.")
    target_type: str = Field(description="Engine target type used by the spell action.")
    range_type: SpellCatalogRangeType = Field(
        description="Authored normalized spell range category.",
    )
    range_ft: int = Field(
        ge=0,
        description="Authored spell range in feet; zero for self-range effects.",
    )
    projectile_type: Optional[ProjectileCatalogType] = Field(default=None, description="Normalized projectile style when present.")
    aoe_shape_type: Optional[AoeCatalogShapeType] = Field(default=None, description="Normalized area-of-effect shape when present.")
    aoe_radius_ft: Optional[int] = Field(default=None, description="Area radius in feet when applicable.")
    aoe_length_ft: Optional[int] = Field(default=None, description="Area length in feet when applicable.")
    aoe_width_ft: Optional[int] = Field(default=None, description="Area width in feet when applicable.")
    aoe_height_ft: Optional[int] = Field(default=None, description="Area height in feet when applicable.")
    damage_types: List[str] = Field(default_factory=list, description="Authored damage type labels for the spell.")
    healing: bool = Field(default=False, description="Whether the spell restores hit points.")
    attack_roll: bool = Field(default=False, description="Whether the spell uses a spell attack roll.")
    saving_throws: Tuple[SpellCatalogSavingThrow, ...] = Field(
        description="Ordered distinct saving throws used by the spell; empty when none.",
    )
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    ritual: bool = Field(default=False, description="Whether the spell can be cast as a ritual.")
    verbal: bool = Field(default=True, description="Whether the spell has a verbal component.")
    somatic: Optional[bool] = Field(default=None, description="Whether the spell has a somatic component when known.")
    material: Optional[bool] = Field(default=None, description="Whether the spell has a material component when known.")
    classes: List[str] = Field(default_factory=list, description="Class names associated with the spell in catalog metadata.")
    subclasses: List[str] = Field(default_factory=list, description="Subclass names associated with the spell in catalog metadata.")
    source: str = Field(
        min_length=1,
        description="Exact authored provenance source identifier.",
    )
    multi_target: Optional[SpellCatalogMultiTarget] = Field(default=None, description="Multi-target metadata when the spell supports it.")
    vfx: SpellCatalogVfx = Field(
        description="Required authored visual routing hints for the spell.",
    )


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
    """Non-content map preset or terrain palette entry.

    Attributes:
        id: Stable catalog identifier.
        name: Display name shown in editor tools.
        group: High-level catalog group.
        category: Object, terrain, loot, or preset category.
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


class MapEditorContentCatalogEntry(BaseModel):
    """One exact public placeable recipe discovered from the frozen registry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recipe: ContentRecipe = Field(
        description="Exact self-authenticating construction recipe.",
    )
    content_set_digest: str = Field(
        description="Installed content set that resolves this recipe.",
    )
    recipe_preset_ref: Optional[ContentRecipePresetRef] = Field(
        default=None,
        description="Exact named preset identity, absent for definition defaults.",
    )
    display_name: str = Field(description="Authored catalog display name.")
    description: str = Field(description="Authored catalog description.")
    tags: Tuple[str, ...] = Field(description="Authored searchable tags.")
    presentation: ContentPresentation = Field(
        description="Authored renderer presentation keys.",
    )
    ordering: ContentOrdering = Field(
        description="Authored stable group and sort order.",
    )

    @field_validator("content_set_digest")
    @classmethod
    def _validate_content_set_digest(cls, value: str) -> str:
        return validate_sha256(value, "content_set_digest")


class MapEditorCatalog(BaseModel):
    """All mapeditor presets, terrain, objects, and loot known to the backend.

    Attributes:
        presets: Map preset catalog entries.
        tiles: Terrain tile catalog entries.
        content_set_digest: Exact installed content-set identity.
        objects: Public environment-object recipes.
        loot: Public possession recipes and non-duplicate named presets.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    content_set_digest: str = Field(
        description="Exact installed content-set identity.",
    )
    presets: List[MapEditorCatalogEntry] = Field(description="Map preset catalog entries.")
    tiles: List[MapEditorCatalogEntry] = Field(description="Terrain tile catalog entries.")
    objects: List[MapEditorContentCatalogEntry] = Field(description="Public environment-object recipes.")
    loot: List[MapEditorContentCatalogEntry] = Field(description="Public possession recipes and named presets.")

    @field_validator("content_set_digest")
    @classmethod
    def _validate_content_set_digest(cls, value: str) -> str:
        return validate_sha256(value, "content_set_digest")

    @model_validator(mode="after")
    def _validate_content_rows(self) -> "MapEditorCatalog":
        rows = (*self.objects, *self.loot)
        if any(
            row.content_set_digest != self.content_set_digest
            for row in rows
        ):
            raise ValueError(
                "mapeditor content rows must match the catalog content set",
            )
        recipe_digests = [row.recipe.recipe_digest for row in rows]
        if len(recipe_digests) != len(set(recipe_digests)):
            raise ValueError("mapeditor content rows contain recipe aliases")
        return self


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
        player_type: Human participant or read-only observer session.
        name: Optional display name for the session.
    """

    player_type: Literal["human", "observer"] = Field(
        description="Human participant or read-only observer session.",
    )
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
        observer_entity_uuids: Explicit observer union for a zero-control session.
        active_observer_uuid: Observer selected for focus within that union.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(description="Session joining the game.")
    entity_uuids: Optional[List[str]] = Field(default=None, description="Optional entity UUIDs to control.")
    observer_entity_uuids: Optional[List[str]] = Field(
        default=None,
        description="Explicit subjective observer union for a zero-control observer session.",
    )
    active_observer_uuid: Optional[str] = Field(
        default=None,
        description="Observer selected for focus within the explicit observer union.",
    )

    def requested_entity_uuids(self) -> List[str]:
        """Return the exact requested controlled-entity sequence."""
        return list(self.entity_uuids or ())

    def requested_observer_entity_uuids(self) -> List[str]:
        """Return the exact requested observer sequence."""
        return list(self.observer_entity_uuids or ())

    @model_validator(mode="after")
    def validate_exact_entity_sets(self) -> "JoinGameRequest":
        """Reject ambiguous duplicate membership declarations."""
        for field_name, values in (
            ("entity_uuids", self.entity_uuids),
            ("observer_entity_uuids", self.observer_entity_uuids),
        ):
            if values is not None and len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicate UUIDs")
        return self


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


class GameCreationCatalogResponse(BaseModel):
    """Canonical roster, encounter, and formation catalog."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[4] = 4
    roster_recipes: tuple[EncounterRosterRecipe, ...] = Field(
        description="Reusable authored creature or champion rosters.",
    )
    encounter_recipes: tuple[EncounterRecipe, ...] = Field(
        description="Complete authored encounter recipes.",
    )
    battlefields: List[BattlefieldDefinition] = Field(
        description="Canonical battlefield definitions.",
    )
    deployments: tuple[EncounterDeploymentSpec, ...] = Field(
        description="Neutral ordered multi-roster spawn formations.",
    )


class GameCreationAuthoredRosterSelection(BaseModel):
    """Select one complete authored roster without copying its recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["authored_roster"] = "authored_roster"
    roster_id: str = Field(min_length=1)


class GameCreationRosterSlotSelection(BaseModel):
    """One requested human participant roster, faction, and formation zone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roster_slot_id: str = Field(min_length=1)
    roster: GameCreationAuthoredRosterSelection
    faction_id: str = Field(min_length=1)
    deployment_zone_id: str = Field(min_length=1)
    participant_name: str = Field(min_length=1, max_length=120)


class GameCreationComposeRequest(BaseModel):
    """Normalize authored catalog selections into one exact recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=120)
    roster_slots: tuple[GameCreationRosterSlotSelection, ...] = Field(
        min_length=2,
    )
    battlefield_id: str = Field(min_length=1)
    deployment_id: str = Field(min_length=1)
    opening_policy: EncounterOpeningPolicy

    @model_validator(mode="after")
    def _validate_roster_slot_ids(self) -> "GameCreationComposeRequest":
        slot_ids = [slot.roster_slot_id for slot in self.roster_slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("roster slot ids must be unique")
        return self


class GameCreationComposeResponse(BaseModel):
    """The sole normalized recipe accepted by preview and start."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    recipe: EncounterRecipe
    compatibility: EncounterCompatibilityReport
    preview: GameCreationEncounterVisualPreviewResponse

    @model_validator(mode="after")
    def _validate_exact_identity(self) -> "GameCreationComposeResponse":
        if (
            self.compatibility.encounter_recipe_digest
            != self.recipe.recipe_digest
            or self.preview.encounter_recipe_digest
            != self.recipe.recipe_digest
            or self.preview.content_set_digest != self.content_set_digest
            or self.preview.ruleset_digest != self.ruleset_digest
        ):
            raise ValueError(
                "Composition recipe, compatibility, and preview identities differ",
            )
        return self


class GameCreationPreviewRequest(BaseModel):
    """Request production projection of one already-normalized recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_content_set_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_ruleset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    recipe: EncounterRecipe


class GameCreationStartRequest(GameCreationPreviewRequest):
    """Start the exact recipe returned by composition without renormalizing."""

    pass


class GameCreationEntityAssignment(BaseModel):
    """One recipe member bound to its runtime entity and participant seat."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: str
    entity_uuid: str
    entity_name: str
    faction: Optional[str] = None
    participant_name: str


class GameCreationRosterResult(BaseModel):
    """Resolved member assignments for one recipe roster slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roster_slot_id: str
    roster_id: str
    roster_recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    title: str
    entity_assignments: tuple[GameCreationEntityAssignment, ...] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def _validate_member_identities(self) -> "GameCreationRosterResult":
        member_ids = tuple(
            assignment.member_id for assignment in self.entity_assignments
        )
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("Roster result repeats a member id")
        return self


class GameCreationStartResponse(BaseModel):
    """Resolved prepared game and ordered roster assignments.

    Creation never starts an encounter. A joined client first opens its
    canonical replication bootstrap, then explicitly activates this prepared
    game with the exact bootstrap identity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[3] = 3
    recipe_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    encounter_uuid: str = Field(description="Created encounter UUID.")
    game_id: str = Field(description="Created active game UUID.")
    encounter_name: str = Field(description="Created encounter display name.")
    compatibility: EncounterCompatibilityReport
    rosters: tuple[GameCreationRosterResult, ...] = Field(min_length=2)
    status: Literal["prepared"] = Field(
        default="prepared",
        description="Prepared lifecycle boundary; no encounter event has run.",
    )

    @model_validator(mode="after")
    def _validate_result_identity(self) -> "GameCreationStartResponse":
        if self.compatibility.encounter_recipe_digest != self.recipe_digest:
            raise ValueError(
                "Start compatibility belongs to another recipe",
            )
        roster_slot_ids = tuple(
            roster.roster_slot_id for roster in self.rosters
        )
        if len(roster_slot_ids) != len(set(roster_slot_ids)):
            raise ValueError("Start result repeats a roster slot")
        assignments = tuple(
            assignment
            for roster in self.rosters
            for assignment in roster.entity_assignments
        )
        entity_uuids = tuple(
            assignment.entity_uuid for assignment in assignments
        )
        if len(entity_uuids) != len(set(entity_uuids)):
            raise ValueError("Start result repeats a runtime entity")
        return self


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


class ActionExecutionAuthorization(str, Enum):
    """Session/turn authority applied on top of intrinsic action availability."""

    AUTHORIZED = "authorized"
    NOT_ACTIVE_TURN = "not_active_turn"
    TURN_NOT_IN_PROGRESS = "turn_not_in_progress"
    ENCOUNTER_INACTIVE = "encounter_inactive"


class APIAvailableActions(AvailableActionsResult):
    """Engine-discovered legal actions plus current resource summaries."""

    execution_authorization: ActionExecutionAuthorization = Field(
        description=(
            "Whether this session may currently execute rows for the inspected "
            "entity. Row availability remains the independent mechanical fact."
        ),
    )
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




class EventContractSummary(BaseModel):
    """Public identity and discriminators for the generated event contract."""

    contract_version: int = Field(description="Generated event-contract version.")
    contract_hash: str = Field(description="Generated event-contract content hash.")
    event_types: List[str] = Field(description="All semantic event type values.")
    wire_types: List[str] = Field(description="All concrete event wire discriminators.")
