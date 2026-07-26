"""Canonical route-free transport values for subjective player replication.

This module is the player-facing boundary.  It deliberately carries neither
engine ``Event`` objects nor the AI/controller observation protocol.  Producers
project engine state into typed world patches and typed presentation cues before
constructing these values.

The three clocks are intentionally independent:

* ``source_event_cursor`` is only a causal watermark.  It may advance in an
  otherwise empty frame when the corresponding source slot is hidden.
* ``observation_cursor`` orders perspective-safe world mutations.
* ``presentation_cursor`` orders perspective-safe animation cues.

Combat-log cursors remain their exact source coordinates through the shared
timeline contract.  A nullable subjective log frame therefore cannot block on
an undisclosed event payload.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Annotated, Dict, Final, Literal, Optional, Tuple, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.equipment_types import VisualLoadoutSlot
from dnd.core.item_types import EquippedVisualPolicy, ItemPresentationKind
from dnd.core.life_types import LifeState, LifeStateChangeReason
from server.world_contracts import (
    APIEntitySummary,
    APIEntityVisibility,
    APIEquipmentOverview,
    APIGrid,
    APITile,
    APIVisibilityResponse,
    SafeContentPresentationRef,
)
from server.timeline_contracts import (
    CombatLogFrame,
    CombatLogFramesResponse,
    CombatLogProjection,
)


PLAYER_REPLICATION_CONTRACT_VERSION: Final[int] = 1
PLAYER_REPLICATION_CONTRACT_HASH: Final[str]
_PLAYER_REPLICATION_SEMANTICS: Final[dict[str, object]] = {
    "contract_version": PLAYER_REPLICATION_CONTRACT_VERSION,
    "projection": "subjective_only",
    "perspectives": [
        "controlled_knowledge_union",
        "spectator_knowledge_union",
    ],
    "world": [
        "projected_game_state",
        "typed_floor_object_projection",
        "privacy_safe_directional_structural_edges",
        "subjective_encounter_without_hidden_combatants_or_turn_index",
        "authorized_observer_visibility",
        "controlled_equipment_only",
        "safe_visual_loadout_for_every_projected_entity",
    ],
    "patches": [
        "entity_upsert",
        "entity_remove",
        "tile_upsert",
        "floor_object_upsert",
        "floor_object_remove",
        "encounter_replace",
        "observer_visibility_replace",
        "observer_visibility_remove",
        "controlled_equipment_replace",
        "visual_loadout_replace",
        "door_state",
    ],
    "presentation": [
        "movement",
        "forced_movement",
        "shove",
        "counterspell",
        "item_action",
        "attack",
        "spell",
        "damage",
        "heal",
        "lifecycle_cause",
        "life_state",
        "condition",
        "door",
        "light",
        "equipment",
        "encounter",
    ],
    "presentation_graph": (
        "closed per observation frame; partition-wide unique presentation IDs; ordered, "
        "bidirectionally validated child edges; no source-lineage references"
    ),
    "movement_perception_commit": (
        "visibility, explored cells, entity/object perception, and effective light "
        "commit atomically with the observation-frame patches after the complete "
        "causal movement batch; no per-step reveal is implied"
    ),
    "area_geometry": (
        "lossless declaration-time sphere/cone/line/cube/cylinder geometry; "
        "cone angle and cube centering/direction are explicit"
    ),
    "damage_projection": "total_applied_amount_plus_ordered_type_categories_without_allocation",
    "shove_outcomes": [
        "resisted",
        "succeeded_push",
        "succeeded_prone",
        "succeeded_blocked",
    ],
    "visual_active_set": "selection_hint_allows_hidden_or_unarmed_layers",
    "watermarks": [
        "source_event_cursor",
        "observation_cursor",
        "presentation_cursor",
        "combat_log_cursor",
    ],
    "raw_event_payload": "forbidden",
    "content_attribution": (
        "exact authenticated definition/provider/origin-root refs only; "
        "unbound residuals remain an empty attribution tuple"
    ),
}


Position: TypeAlias = Tuple[int, int]


class PlayerReplicationModel(BaseModel):
    """Immutable, closed base for player-replication values."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class FloorObjectProjectionKind(str, Enum):
    """Closed renderer/reducer family for a projected floor object."""

    ITEM = "item"
    INTERACTABLE = "interactable"
    CONTAINER = "container"
    HAZARD = "hazard"
    DOOR = "door"
    DIRECTIONAL_STRUCTURE = "directional_structure"
    LIGHT_SOURCE = "light_source"
    GENERIC = "generic"


class FloorObjectDirection(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class FloorObjectBlockingChannel(str, Enum):
    MOVEMENT = "movement"
    VISION = "vision"
    LIGHT = "light"
    PROPAGATION = "propagation"


class SubjectiveFloorObject(PlayerReplicationModel):
    """Closed player-facing floor-object projection with no arbitrary state map."""

    uuid: str = Field(min_length=1)
    name: str = Field(min_length=1)
    position: Position
    map_char: str = Field(min_length=1)
    object_kind: FloorObjectProjectionKind
    safe_presentation_ref: SafeContentPresentationRef = Field(
        description=(
            "Required mechanics-free identity in the authenticated content "
            "catalog; exact item and recipe identities are intentionally absent."
        ),
    )
    visual_item_name: str = Field(
        min_length=1,
        description="Explicit renderer catalog key; clients must not infer it from the name.",
    )
    visual_variant_id: Optional[str] = Field(
        default=None,
        description="Optional explicit renderer variant key.",
    )
    blocks_movement: bool = False
    blocks_vision: bool = False
    is_open: Optional[bool] = None
    blocked_directions: Tuple[FloorObjectDirection, ...] = Field(default_factory=tuple)
    blocked_channels: Tuple[FloorObjectBlockingChannel, ...] = Field(default_factory=tuple)
    is_lit: Optional[bool] = None
    very_bright_radius_feet: Optional[int] = Field(default=None, ge=0)
    bright_radius_feet: Optional[int] = Field(default=None, ge=0)
    dim_radius_feet: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_kind_state(self) -> "SubjectiveFloorObject":
        if len(set(self.blocked_directions)) != len(self.blocked_directions):
            raise ValueError("floor-object blocked directions must be unique")
        if len(set(self.blocked_channels)) != len(self.blocked_channels):
            raise ValueError("floor-object blocked channels must be unique")

        has_directional_state = bool(self.blocked_directions or self.blocked_channels)
        if bool(self.blocked_directions) != bool(self.blocked_channels):
            raise ValueError("directional floor-object state requires directions and channels together")
        if self.object_kind is FloorObjectProjectionKind.DIRECTIONAL_STRUCTURE:
            if not has_directional_state:
                raise ValueError("directional structure requires blocked directions and channels")
        elif self.object_kind is not FloorObjectProjectionKind.DOOR and has_directional_state:
            raise ValueError("directional blocking state is valid only for doors and structures")

        if self.object_kind is FloorObjectProjectionKind.DOOR:
            if self.is_open is None:
                raise ValueError("door projection requires explicit open state")
        elif self.is_open is not None:
            raise ValueError("open state is valid only for a door projection")

        light_radii = (
            self.very_bright_radius_feet,
            self.bright_radius_feet,
            self.dim_radius_feet,
        )
        if self.object_kind is FloorObjectProjectionKind.LIGHT_SOURCE:
            if self.is_lit is None or any(radius is None for radius in light_radii):
                raise ValueError("light-source projection requires lit state and all radii")
        elif self.is_lit is not None or any(radius is not None for radius in light_radii):
            raise ValueError("light state is valid only for a light-source projection")
        return self


class SubjectiveCombatant(PlayerReplicationModel):
    """One identified combatant safe to expose in subjective initiative state."""

    uuid: str = Field(min_length=1)
    name: str = Field(min_length=1)
    initiative: int
    life_state: Optional[LifeState] = None
    is_dead: bool


class SubjectiveEncounter(PlayerReplicationModel):
    """Encounter state filtered to combatants identified by this perspective."""

    uuid: str = Field(min_length=1)
    name: str = Field(min_length=1)
    state: str = Field(min_length=1)
    round_number: int = Field(ge=0)
    current_turn_index: Optional[int] = Field(default=None, ge=0)
    current_entity_uuid: Optional[str] = None
    initiative_order: Tuple[SubjectiveCombatant, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_current_turn(self) -> "SubjectiveEncounter":
        combatant_uuids = [combatant.uuid for combatant in self.initiative_order]
        if len(combatant_uuids) != len(set(combatant_uuids)):
            raise ValueError("subjective initiative combatants must be unique")
        if self.current_entity_uuid is None:
            if self.current_turn_index is not None:
                raise ValueError("hidden current combatant cannot expose a turn index")
        else:
            if self.current_entity_uuid not in combatant_uuids:
                raise ValueError("current subjective combatant must appear in initiative order")
            expected_index = combatant_uuids.index(self.current_entity_uuid)
            if self.current_turn_index != expected_index:
                raise ValueError("subjective turn index must address the current combatant")
        return self


class SubjectiveGameState(PlayerReplicationModel):
    """Player reducer seed whose floor-object surface is fully typed."""

    grid: APIGrid
    entities: Tuple[APIEntitySummary, ...]
    encounter: Optional[SubjectiveEncounter] = None
    floor_objects: Tuple[SubjectiveFloorObject, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_unique_objects(self) -> "SubjectiveGameState":
        entity_uuids = [entity.uuid for entity in self.entities]
        if len(entity_uuids) != len(set(entity_uuids)):
            raise ValueError("projected entity UUIDs must be unique")
        object_uuids = [obj.uuid for obj in self.floor_objects]
        if len(object_uuids) != len(set(object_uuids)):
            raise ValueError("projected floor-object UUIDs must be unique")
        return self


class PerspectiveKind(str, Enum):
    """How authorized observer knowledge is combined for one player view."""

    CONTROLLED_KNOWLEDGE_UNION = "controlled_knowledge_union"
    SPECTATOR_KNOWLEDGE_UNION = "spectator_knowledge_union"


class SubjectivePerspective(PlayerReplicationModel):
    """Explicit authority-free description of one already-authorized view.

    Authorization happens before this value is built.  Both policies combine
    only the knowledge of the listed observer entities.  In particular, a
    spectator with no controlled creature never falls back to objective state.
    """

    projection: Literal["subjective"] = Field(
        default="subjective",
        description="Player transport is subjective by construction.",
    )
    perspective_epoch_id: str = Field(
        min_length=1,
        description="Opaque epoch rotated whenever effective authority changes.",
    )
    kind: PerspectiveKind = Field(description="Observer-union policy for this epoch.")
    controlled_entity_uuids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Entities controlled by the receiving participant.",
    )
    observer_entity_uuids: Tuple[str, ...] = Field(
        min_length=1,
        description="Authorized observer knowledge combined by set union.",
    )
    active_observer_uuid: str = Field(
        min_length=1,
        description="Observer used for focus and observer-relative UI choices; it does not narrow the union.",
    )

    @model_validator(mode="after")
    def validate_union_policy(self) -> "SubjectivePerspective":
        controlled = set(self.controlled_entity_uuids)
        observers = set(self.observer_entity_uuids)
        if len(controlled) != len(self.controlled_entity_uuids):
            raise ValueError("controlled entity UUIDs must be unique")
        if len(observers) != len(self.observer_entity_uuids):
            raise ValueError("observer entity UUIDs must be unique")
        if self.active_observer_uuid not in observers:
            raise ValueError("active observer must belong to the authorized observer union")

        if self.kind is PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION:
            if not controlled:
                raise ValueError("controlled knowledge union requires controlled entities")
            if observers != controlled:
                raise ValueError(
                    "controlled knowledge union observers must exactly match controlled entities"
                )
        else:
            if controlled:
                raise ValueError("spectator knowledge union cannot control entities")
            if not observers:
                raise ValueError(
                    "spectator knowledge union requires authorized observers; objective fallback is forbidden"
                )
        return self


class ActiveWeaponSet(str, Enum):
    """Weapon layers the renderer should expose for the current actor stance."""

    NONE = "none"
    MELEE = "melee"
    RANGED = "ranged"


class VisualEquipmentLayer(PlayerReplicationModel):
    """Renderer-safe equipped item projection without rules or inventory data."""

    slot: VisualLoadoutSlot = Field(description="Canonical occupied visual slot.")
    item_kind: ItemPresentationKind = Field(description="Small renderer item family.")
    safe_presentation_ref: SafeContentPresentationRef = Field(
        description=(
            "Required mechanics-free identity in the authenticated content "
            "catalog; exact item and recipe identities are intentionally absent."
        ),
    )
    visual_item_name: str = Field(min_length=1, description="Renderer catalog key.")
    visual_variant_id: Optional[str] = Field(default=None, description="Renderer variant key.")
    equipped_visual_policy: EquippedVisualPolicy = Field(
        description="Whether this item contributes an actor layer.",
    )


class EntityVisualLoadout(PlayerReplicationModel):
    """Safe actor layers visible for one projected entity."""

    entity_uuid: str = Field(min_length=1)
    active_weapon_set: ActiveWeaponSet = Field(
        default=ActiveWeaponSet.NONE,
        description=(
            "Explicit melee/ranged selection hint; hidden gear and an unarmed empty layer set are valid."
        ),
    )
    layers: Tuple[VisualEquipmentLayer, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_unique_slots(self) -> "EntityVisualLoadout":
        slots = [layer.slot for layer in self.layers]
        if len(slots) != len(set(slots)):
            raise ValueError("visual loadout slots must be unique")
        return self


class SubjectiveReplicatedWorld(PlayerReplicationModel):
    """Renderer-complete projected world for first paint and resynchronization.

    ``state`` retains projected grid bounds, complete projected tile seeds,
    entity appearance/size/condition/life data, encounter state, and floor
    objects.  ``visibility`` retains each authorized observer's cells, senses,
    and backend-resolved effective light levels.  Full equipment remains in the
    ``equipment_by_entity`` map only for controlled entities; safe
    visual layers for every projected actor live here separately.
    """

    state: SubjectiveGameState
    visibility: APIVisibilityResponse
    equipment_by_entity: Dict[str, APIEquipmentOverview] = Field(default_factory=dict)

    visual_loadout_by_entity: Dict[str, EntityVisualLoadout] = Field(
        default_factory=dict,
        description="Safe actor-rendering loadouts keyed by every projected entity UUID.",
    )

    @model_validator(mode="after")
    def validate_renderer_seed(self) -> "SubjectiveReplicatedWorld":
        entity_uuids = {entity.uuid for entity in self.state.entities}
        unknown_equipment = sorted(set(self.equipment_by_entity) - entity_uuids)
        if unknown_equipment:
            raise ValueError(
                "equipment rows reference entities absent from projected state: "
                f"{unknown_equipment}"
            )
        if set(self.visual_loadout_by_entity) != entity_uuids:
            raise ValueError(
                "visual loadouts must exactly cover every entity in projected state"
            )
        for key, loadout in self.visual_loadout_by_entity.items():
            if loadout.entity_uuid != key:
                raise ValueError("visual loadout key must match its entity UUID")

        grid = self.state.grid
        if grid.min_x > grid.max_x or grid.min_y > grid.max_y:
            raise ValueError("projected grid bounds must be ordered")
        positions = [(tile.x, tile.y) for tile in grid.tiles]
        if len(positions) != len(set(positions)):
            raise ValueError("projected grid tile positions must be unique")
        if any(
            x < grid.min_x or x > grid.max_x or y < grid.min_y or y > grid.max_y
            for x, y in positions
        ):
            raise ValueError("projected grid tile lies outside declared bounds")

        for observer_uuid, visibility in self.visibility.root.items():
            visible_keys = {f"{x},{y}" for x, y in visibility.visible_cells}
            if set(visibility.effective_light_levels) != visible_keys:
                raise ValueError(
                    f"effective light levels must exactly cover visible cells for {observer_uuid}"
                )
        return self


class PlayerReplicationWatermarks(PlayerReplicationModel):
    """Independent reducer, presentation, source, and log boundaries."""

    source_event_cursor: int = Field(
        ge=0,
        description="Highest consumed source event slot; no event payload is implied.",
    )
    observation_cursor: int = Field(
        ge=0,
        description="Highest consumed perspective-safe world frame.",
    )
    presentation_cursor: int = Field(
        ge=0,
        description="Highest produced perspective-safe presentation cue.",
    )
    combat_log_cursor: int = Field(
        ge=0,
        description="Highest consumed exact combat-log source slot.",
    )

    def dominates(self, earlier: "PlayerReplicationWatermarks") -> bool:
        """Return whether every independent boundary is nondecreasing."""
        return (
            self.source_event_cursor >= earlier.source_event_cursor
            and self.observation_cursor >= earlier.observation_cursor
            and self.presentation_cursor >= earlier.presentation_cursor
            and self.combat_log_cursor >= earlier.combat_log_cursor
        )


class PlayerReplicationProtocolIdentity(PlayerReplicationModel):
    """Self-authenticating player decoder and hot source-generation identity."""

    player_replication_contract_version: int = Field(
        default=PLAYER_REPLICATION_CONTRACT_VERSION,
        ge=1,
    )
    player_replication_contract_hash: str = Field(
        default_factory=lambda: PLAYER_REPLICATION_CONTRACT_HASH,
        min_length=1,
    )
    source_stream_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decoder(self) -> "PlayerReplicationProtocolIdentity":
        if self.player_replication_contract_version != PLAYER_REPLICATION_CONTRACT_VERSION:
            raise ValueError("unsupported player replication contract version")
        if self.player_replication_contract_hash != PLAYER_REPLICATION_CONTRACT_HASH:
            raise ValueError("player replication contract hash mismatch")
        return self


class SubjectiveCombatLogFrame(CombatLogFrame):
    """Player-only nullable log slot; objective projection is unrepresentable."""

    projection: Literal[CombatLogProjection.SUBJECTIVE] = (
        CombatLogProjection.SUBJECTIVE
    )


class SubjectiveCombatLogFramesResponse(CombatLogFramesResponse):
    """Exact player log window whose frames are subjective at the type boundary."""

    projection: Literal[CombatLogProjection.SUBJECTIVE] = (
        CombatLogProjection.SUBJECTIVE
    )
    frames: Tuple[SubjectiveCombatLogFrame, ...] = Field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Typed reducer patches


class EntityUpsertPatch(PlayerReplicationModel):
    kind: Literal["entity_upsert"] = "entity_upsert"
    entity: APIEntitySummary


class EntityRemovePatch(PlayerReplicationModel):
    kind: Literal["entity_remove"] = "entity_remove"
    entity_uuid: str = Field(min_length=1)


class TileUpsertPatch(PlayerReplicationModel):
    kind: Literal["tile_upsert"] = "tile_upsert"
    tile: APITile


class FloorObjectUpsertPatch(PlayerReplicationModel):
    kind: Literal["floor_object_upsert"] = "floor_object_upsert"
    object: SubjectiveFloorObject


class FloorObjectRemovePatch(PlayerReplicationModel):
    kind: Literal["floor_object_remove"] = "floor_object_remove"
    object_uuid: str = Field(min_length=1)


class EncounterReplacePatch(PlayerReplicationModel):
    kind: Literal["encounter_replace"] = "encounter_replace"
    encounter: Optional[SubjectiveEncounter] = None


class ObserverVisibilityReplacePatch(PlayerReplicationModel):
    kind: Literal["observer_visibility_replace"] = "observer_visibility_replace"
    observer_uuid: str = Field(min_length=1)
    visibility: APIEntityVisibility

    @model_validator(mode="after")
    def validate_effective_light_rows(self) -> "ObserverVisibilityReplacePatch":
        visible = {f"{x},{y}" for x, y in self.visibility.visible_cells}
        if set(self.visibility.effective_light_levels) != visible:
            raise ValueError("observer visibility effective light must exactly cover visible cells")
        return self


class ObserverVisibilityRemovePatch(PlayerReplicationModel):
    kind: Literal["observer_visibility_remove"] = "observer_visibility_remove"
    observer_uuid: str = Field(min_length=1)


class ControlledEquipmentReplacePatch(PlayerReplicationModel):
    kind: Literal["controlled_equipment_replace"] = "controlled_equipment_replace"
    entity_uuid: str = Field(min_length=1)
    equipment: APIEquipmentOverview


class VisualLoadoutReplacePatch(PlayerReplicationModel):
    kind: Literal["visual_loadout_replace"] = "visual_loadout_replace"
    loadout: EntityVisualLoadout


class DoorStatePatch(PlayerReplicationModel):
    """Typed materialized door state; no object-specific dictionary parsing."""

    kind: Literal["door_state"] = "door_state"
    object_uuid: str = Field(min_length=1)
    position: Position
    is_open: bool
    blocks_movement: bool
    blocks_vision: bool


class EffectiveLightCell(PlayerReplicationModel):
    position: Position
    light_level: int = Field(ge=0)


SubjectiveWorldPatch: TypeAlias = Annotated[
    Union[
        EntityUpsertPatch,
        EntityRemovePatch,
        TileUpsertPatch,
        FloorObjectUpsertPatch,
        FloorObjectRemovePatch,
        EncounterReplacePatch,
        ObserverVisibilityReplacePatch,
        ObserverVisibilityRemovePatch,
        ControlledEquipmentReplacePatch,
        VisualLoadoutReplacePatch,
        DoorStatePatch,
    ],
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Typed safe presentation cues


class BehaviorPresentationRole(str, Enum):
    """Causal role played by one authenticated runtime behavior."""

    BEHAVIOR = "behavior"
    TRIGGER_BEHAVIOR = "trigger_behavior"


class UnrootedBehaviorPresentationAttribution(PlayerReplicationModel):
    """Exact behavior binding with no durable constructible origin root."""

    kind: Literal["unrooted_behavior"] = "unrooted_behavior"
    role: BehaviorPresentationRole
    definition_ref: ContentRef
    provided_by_ref: ContentRef


class RootedBehaviorPresentationAttribution(PlayerReplicationModel):
    """Exact behavior binding inherited from a durable authored root."""

    kind: Literal["rooted_behavior"] = "rooted_behavior"
    role: BehaviorPresentationRole
    definition_ref: ContentRef
    provided_by_ref: ContentRef
    origin_root_ref: ContentRef


class SourceItemPresentationAttribution(PlayerReplicationModel):
    """Exact authored item definition that supplied an item-bound action."""

    kind: Literal["source_item"] = "source_item"
    definition_ref: ContentRef

    @model_validator(mode="after")
    def validate_item_kind(self) -> "SourceItemPresentationAttribution":
        if self.definition_ref.definition_kind not in {
            ContentDefinitionKind.ITEM,
            ContentDefinitionKind.ENVIRONMENT_OBJECT,
        }:
            raise ValueError(
                "source-item attribution requires an item or environment-object definition"
            )
        return self


PresentationContentAttribution: TypeAlias = Annotated[
    Union[
        UnrootedBehaviorPresentationAttribution,
        RootedBehaviorPresentationAttribution,
        SourceItemPresentationAttribution,
    ],
    Field(discriminator="kind"),
]


class PresentationCueBase(PlayerReplicationModel):
    """One node in a projection-native, frame-closed presentation graph."""

    presentation_cursor: int = Field(ge=1)
    presentation_id: str = Field(min_length=1)
    parent_presentation_id: Optional[str] = None
    child_presentation_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Ordered delivered children after hidden nodes were removed or reparented.",
    )
    source_event_cursor: int = Field(ge=1)
    source_event_uuid: str = Field(min_length=1)
    content_attributions: Tuple[PresentationContentAttribution, ...] = Field(
        default_factory=tuple,
        description=(
            "Exact authenticated content identities available for this cue; "
            "an empty tuple is the honest state for an unmigrated residual."
        ),
    )

    @model_validator(mode="after")
    def validate_local_graph_identity(self) -> "PresentationCueBase":
        if len(set(self.child_presentation_ids)) != len(self.child_presentation_ids):
            raise ValueError("presentation child IDs must be unique and ordered")
        if self.presentation_id in self.child_presentation_ids:
            raise ValueError("presentation cue cannot be its own child")
        roles = tuple(
            attribution.role.value
            if isinstance(
                attribution,
                (
                    UnrootedBehaviorPresentationAttribution,
                    RootedBehaviorPresentationAttribution,
                ),
            )
            else attribution.kind
            for attribution in self.content_attributions
        )
        if len(roles) != len(set(roles)):
            raise ValueError("presentation content-attribution roles must be unique")
        return self


class MovementKind(str, Enum):
    WALK = "walk"
    JUMP = "jump"


class MovementPresentationCue(PresentationCueBase):
    kind: Literal["movement"] = "movement"
    entity_uuid: str = Field(min_length=1)
    movement_kind: MovementKind
    trajectory: Tuple[Position, ...] = Field(
        min_length=2,
        description="Ordered positions including the segment start and every committed destination.",
    )
    path_start_index: int = Field(default=0, ge=0)
    path_total_steps: int = Field(ge=1)
    perception_commit: Literal["observation_frame"] = Field(
        description=(
            "Perception changes commit atomically with this cue's containing "
            "observation frame, not at intermediate trajectory arrivals."
        )
    )

    @model_validator(mode="after")
    def validate_path_order(self) -> "MovementPresentationCue":
        represented_steps = len(self.trajectory) - 1
        if self.path_start_index + represented_steps > self.path_total_steps:
            raise ValueError("movement trajectory exceeds declared path order")
        return self


class PresentationProjectile(str, Enum):
    """Closed projectile dispatch categories supported by the renderer."""

    BOLT = "bolt"
    RAY = "ray"
    ORB = "orb"
    BEAM = "beam"
    DART = "dart"
    SPRAY = "spray"
    RADIANCE = "radiance"
    TOUCH = "touch"
    RAIN = "rain"


class PresentationWeaponSlot(str, Enum):
    """Closed attack recipe inputs after projection-time slot normalization."""

    MELEE_MAIN = "MELEE_MAIN"
    MELEE_OFF = "MELEE_OFF"
    RANGED_MAIN = "RANGED_MAIN"
    RANGED_OFF = "RANGED_OFF"


class PresentationDamageType(str, Enum):
    """Closed damage/VFX categories shared with the renderer."""

    SLASHING = "Slashing"
    PIERCING = "Piercing"
    BLUDGEONING = "Bludgeoning"
    FIRE = "Fire"
    COLD = "Cold"
    LIGHTNING = "Lightning"
    THUNDER = "Thunder"
    ACID = "Acid"
    POISON = "Poison"
    RADIANT = "Radiant"
    NECROTIC = "Necrotic"
    PSYCHIC = "Psychic"
    FORCE = "Force"


class PresentationSpellSchool(str, Enum):
    EVOCATION = "evocation"
    NECROMANCY = "necromancy"
    ABJURATION = "abjuration"
    ENCHANTMENT = "enchantment"
    CONJURATION = "conjuration"
    ILLUSION = "illusion"
    TRANSMUTATION = "transmutation"
    DIVINATION = "divination"


class AttackOutcome(str, Enum):
    HIT = "hit"
    MISS = "miss"
    CRITICAL = "critical"
    CRITICAL_MISS = "critical_miss"


class AttackDelivery(str, Enum):
    MELEE = "melee"
    PROJECTILE = "projectile"


class AttackPresentationCue(PresentationCueBase):
    kind: Literal["attack"] = "attack"
    actor_uuid: str = Field(min_length=1)
    target_uuid: str = Field(min_length=1)
    action_name: str = Field(min_length=1)
    outcome: AttackOutcome
    delivery: AttackDelivery
    weapon_slot: Optional[PresentationWeaponSlot] = None
    damage_types: Tuple[PresentationDamageType, ...] = Field(min_length=1)
    projectile_type: Optional[PresentationProjectile] = None
    impact_effect_presentation_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Ordered child effects attached to contact or projectile arrival.",
    )

    @model_validator(mode="after")
    def validate_delivery(self) -> "AttackPresentationCue":
        if len(set(self.damage_types)) != len(self.damage_types):
            raise ValueError("attack presentation damage types must be unique")
        if self.delivery is AttackDelivery.PROJECTILE and not self.projectile_type:
            raise ValueError("projectile attack requires a projectile type")
        if self.delivery is AttackDelivery.MELEE and self.projectile_type is not None:
            raise ValueError("melee attack cannot carry a projectile type")
        if self.impact_effect_presentation_ids != self.child_presentation_ids:
            raise ValueError("attack impact effects must exactly match ordered presentation children")
        return self


class SpellDelivery(str, Enum):
    SELF = "self"
    TOUCH = "touch"
    DIRECT = "direct"
    PROJECTILE = "projectile"
    MISSILE_VOLLEY = "missile_volley"
    AOE = "aoe"


class AreaShape(str, Enum):
    SPHERE = "sphere"
    CONE = "cone"
    LINE = "line"
    CUBE = "cube"
    CYLINDER = "cylinder"


class SphereAreaGeometry(PlayerReplicationModel):
    shape: Literal["sphere"] = "sphere"
    center: Position
    radius_feet: int = Field(gt=0)


class ConeAreaGeometry(PlayerReplicationModel):
    shape: Literal["cone"] = "cone"
    origin: Position
    direction: Position
    length_feet: int = Field(gt=0)
    angle_degrees: int = Field(gt=0, le=360)

    @model_validator(mode="after")
    def validate_direction(self) -> "ConeAreaGeometry":
        if self.direction == (0, 0):
            raise ValueError("cone direction must be nonzero")
        return self


class LineAreaGeometry(PlayerReplicationModel):
    shape: Literal["line"] = "line"
    origin: Position
    direction: Position
    length_feet: int = Field(gt=0)
    width_feet: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_direction(self) -> "LineAreaGeometry":
        if self.direction == (0, 0):
            raise ValueError("line direction must be nonzero")
        return self


class CubeAreaGeometry(PlayerReplicationModel):
    shape: Literal["cube"] = "cube"
    origin: Position
    direction: Optional[Position] = None
    size_feet: int = Field(gt=0)
    centered: bool

    @model_validator(mode="after")
    def validate_centering(self) -> "CubeAreaGeometry":
        if self.centered and self.direction is not None:
            raise ValueError("centered cube cannot carry a direction")
        if not self.centered and self.direction is None:
            raise ValueError("directional cube requires a direction")
        if self.direction == (0, 0):
            raise ValueError("cube direction must be nonzero")
        return self


class CylinderAreaGeometry(PlayerReplicationModel):
    shape: Literal["cylinder"] = "cylinder"
    center: Position
    radius_feet: int = Field(gt=0)
    height_feet: int = Field(gt=0)


AreaGeometry: TypeAlias = Annotated[
    Union[
        SphereAreaGeometry,
        ConeAreaGeometry,
        LineAreaGeometry,
        CubeAreaGeometry,
        CylinderAreaGeometry,
    ],
    Field(discriminator="shape"),
]


class SpellApplicationOutcome(str, Enum):
    """Explicit result of one ordered spell application."""

    AUTOMATIC = "automatic"
    HIT = "hit"
    MISS = "miss"
    CRITICAL = "critical"
    SAVE_SUCCEEDED = "save_succeeded"
    SAVE_FAILED = "save_failed"
    RESISTED = "resisted"
    IMMUNE = "immune"


class SpellTargetPresentation(PlayerReplicationModel):
    """One ordered application; duplicate target UUIDs are intentional."""

    application_index: int = Field(ge=0)
    application_id: str = Field(
        min_length=1,
        description="Projection-native identity for this target application.",
    )
    outcome: SpellApplicationOutcome
    target_uuid: Optional[str] = None
    position: Optional[Position] = None
    effect_presentation_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Ordered child effects dispatched at this application's impact.",
    )

    @model_validator(mode="after")
    def validate_target(self) -> "SpellTargetPresentation":
        if self.target_uuid is None and self.position is None:
            raise ValueError("spell target requires an entity UUID or a position")
        if self.effect_presentation_ids and self.target_uuid is None:
            raise ValueError(
                "spell applications with entity effects require an explicit target UUID"
            )
        if len(set(self.effect_presentation_ids)) != len(self.effect_presentation_ids):
            raise ValueError("spell application effect IDs must be unique")
        return self


class SpellPresentationCue(PresentationCueBase):
    kind: Literal["spell"] = "spell"
    actor_uuid: str = Field(min_length=1)
    spell_id: str = Field(
        min_length=1,
        description="Stable engine spell catalog key used for renderer dispatch.",
    )
    spell_name: str = Field(min_length=1)
    spell_school: PresentationSpellSchool
    spell_level: int = Field(ge=0, le=9)
    delivery: SpellDelivery
    targets: Tuple[SpellTargetPresentation, ...] = Field(default_factory=tuple)
    projectile_type: Optional[PresentationProjectile] = None
    area: Optional[AreaGeometry] = None

    @model_validator(mode="after")
    def validate_spell_route(self) -> "SpellPresentationCue":
        indexes = [target.application_index for target in self.targets]
        if indexes != list(range(len(indexes))):
            raise ValueError("spell applications must preserve contiguous target order")
        application_ids = [target.application_id for target in self.targets]
        if len(set(application_ids)) != len(application_ids):
            raise ValueError("spell application IDs must be unique")
        projectile_deliveries = {SpellDelivery.PROJECTILE, SpellDelivery.MISSILE_VOLLEY}
        if self.delivery in projectile_deliveries and not self.projectile_type:
            raise ValueError("projectile spell route requires a projectile type")
        if self.delivery is SpellDelivery.AOE and self.area is None:
            raise ValueError("AOE spell route requires typed area geometry")
        if self.delivery is not SpellDelivery.AOE and self.area is not None:
            raise ValueError("non-AOE spell route cannot carry area geometry")
        effects = tuple(
            effect_id
            for target in self.targets
            for effect_id in target.effect_presentation_ids
        )
        if len(set(effects)) != len(effects):
            raise ValueError("one spell effect cannot belong to multiple applications")
        if effects != self.child_presentation_ids:
            raise ValueError("spell application effects must exactly match ordered children")
        return self


class ItemActionKind(str, Enum):
    DRINK = "drink"


class ActorVisualSlot(str, Enum):
    WEAPON = "weapon"
    WEAPON_GLOW = "weaponGlow"
    OFFHAND = "offhand"


class ItemActionPresentationCue(PresentationCueBase):
    """Typed base-action presentation adequate for the potion UseItem clip."""

    kind: Literal["item_action"] = "item_action"
    actor_uuid: str = Field(min_length=1)
    item_uuid: str = Field(min_length=1)
    item_kind: ItemPresentationKind
    action_kind: ItemActionKind
    actor_clip: Literal["Taunt"] = "Taunt"
    effect_frame: int = Field(ge=0)
    playback_speed: float = Field(gt=0)
    hidden_slots: Tuple[ActorVisualSlot, ...] = Field(default_factory=tuple)
    effect_presentation_ids: Tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_item_effects(self) -> "ItemActionPresentationCue":
        if len(set(self.hidden_slots)) != len(self.hidden_slots):
            raise ValueError("item action hidden visual slots must be unique")
        if self.effect_presentation_ids != self.child_presentation_ids:
            raise ValueError("item effect-frame effects must exactly match ordered children")
        return self


class ForcedMovementCause(str, Enum):
    SHOVE = "shove"
    SPELL = "spell"
    RULE_EFFECT = "rule_effect"


class ForcedMovementPresentationCue(PresentationCueBase):
    kind: Literal["forced_movement"] = "forced_movement"
    entity_uuid: str = Field(min_length=1)
    source_uuid: str = Field(min_length=1)
    cause: ForcedMovementCause
    actor_action_presentation_id: str = Field(
        min_length=1,
        description="Delivered parent action controlling contact timing and facing.",
    )
    start_position: Position
    end_position: Position
    duration_ms: int = Field(gt=0)
    target_clip: Literal["TakeDamage"] = "TakeDamage"
    brace_frame: int = Field(ge=0)
    playback_speed: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_actor_action(self) -> "ForcedMovementPresentationCue":
        if self.parent_presentation_id != self.actor_action_presentation_id:
            raise ValueError("forced movement must be attached to its delivered actor action")
        if self.start_position == self.end_position:
            raise ValueError("forced movement must change position")
        if self.child_presentation_ids:
            raise ValueError("forced movement is a leaf presentation cue")
        return self


class ShoveOutcome(str, Enum):
    RESISTED = "resisted"
    SUCCEEDED_PUSH = "succeeded_push"
    SUCCEEDED_PRONE = "succeeded_prone"
    SUCCEEDED_BLOCKED = "succeeded_blocked"


class ShovePresentationCue(PresentationCueBase):
    kind: Literal["shove"] = "shove"
    actor_uuid: str = Field(min_length=1)
    target_uuid: str = Field(min_length=1)
    outcome: ShoveOutcome
    actor_clip: Literal["Kick"] = "Kick"
    contact_frame: int = Field(ge=0)
    playback_speed: float = Field(gt=0)
    forced_movement_presentation_id: Optional[str] = None
    prone_condition_presentation_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "ShovePresentationCue":
        if self.outcome is ShoveOutcome.SUCCEEDED_PUSH:
            if self.forced_movement_presentation_id is None:
                raise ValueError("successful push requires a forced-movement child")
            if self.prone_condition_presentation_id is not None:
                raise ValueError("successful push cannot carry a prone-condition child")
            if self.child_presentation_ids != (self.forced_movement_presentation_id,):
                raise ValueError("successful push child must be its forced movement")
        elif self.outcome is ShoveOutcome.SUCCEEDED_PRONE:
            if self.prone_condition_presentation_id is None:
                raise ValueError("successful prone shove requires a prone-condition child")
            if self.forced_movement_presentation_id is not None:
                raise ValueError("successful prone shove cannot carry forced movement")
            if self.child_presentation_ids != (self.prone_condition_presentation_id,):
                raise ValueError("successful prone shove child must be its condition application")
        elif (
            self.forced_movement_presentation_id is not None
            or self.prone_condition_presentation_id is not None
            or self.child_presentation_ids
        ):
            raise ValueError("resisted or blocked shove cannot carry an effect child")
        return self


class CounterspellAutomaticSuccess(PlayerReplicationModel):
    """A Counterspell slot at least as high as the incoming cast."""

    kind: Literal["automatic_success"] = "automatic_success"


class CounterspellCheckSuccess(PlayerReplicationModel):
    """A lower-slot Counterspell whose spellcasting check succeeded."""

    kind: Literal["check_success"] = "check_success"
    check_total: int
    check_dc: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_success(self) -> "CounterspellCheckSuccess":
        if self.check_total < self.check_dc:
            raise ValueError("successful Counterspell check must meet its DC")
        return self


class CounterspellCheckFailure(PlayerReplicationModel):
    """A lower-slot Counterspell whose spellcasting check failed."""

    kind: Literal["check_failure"] = "check_failure"
    check_total: int
    check_dc: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_failure(self) -> "CounterspellCheckFailure":
        if self.check_total >= self.check_dc:
            raise ValueError("failed Counterspell check must be below its DC")
        return self


CounterspellResolution: TypeAlias = Annotated[
    Union[
        CounterspellAutomaticSuccess,
        CounterspellCheckSuccess,
        CounterspellCheckFailure,
    ],
    Field(discriminator="kind"),
]


class CounterspellPresentationCue(PresentationCueBase):
    """Closed non-movement reaction presentation for one Counterspell."""

    kind: Literal["counterspell"] = "counterspell"
    reactor_uuid: str = Field(min_length=1)
    incoming_caster_uuid: str = Field(min_length=1)
    incoming_spell_level: int = Field(ge=0, le=9)
    counterspell_slot_level: int = Field(ge=3, le=9)
    resolution: CounterspellResolution

    @model_validator(mode="after")
    def validate_counterspell(self) -> "CounterspellPresentationCue":
        if self.child_presentation_ids:
            raise ValueError("Counterspell presentation is a leaf cue")
        roles = {
            attribution.role
            for attribution in self.content_attributions
            if isinstance(
                attribution,
                (
                    UnrootedBehaviorPresentationAttribution,
                    RootedBehaviorPresentationAttribution,
                ),
            )
        }
        if roles != {
            BehaviorPresentationRole.BEHAVIOR,
            BehaviorPresentationRole.TRIGGER_BEHAVIOR,
        }:
            raise ValueError(
                "Counterspell requires exact reaction and incoming-spell behavior attribution"
            )
        if any(
            isinstance(attribution, SourceItemPresentationAttribution)
            for attribution in self.content_attributions
        ):
            raise ValueError("Counterspell cannot carry source-item attribution")
        if isinstance(self.resolution, CounterspellAutomaticSuccess):
            if self.counterspell_slot_level < self.incoming_spell_level:
                raise ValueError(
                    "automatic Counterspell requires a slot at least as high as the incoming cast"
                )
        else:
            if self.counterspell_slot_level >= self.incoming_spell_level:
                raise ValueError(
                    "checked Counterspell requires a lower slot than the incoming cast"
                )
            if self.resolution.check_dc != 10 + self.incoming_spell_level:
                raise ValueError("Counterspell check DC must equal 10 + incoming spell level")
        return self


class DamagePresentationCue(PresentationCueBase):
    """Applied packet total plus ordered source categories; no invented allocation."""

    kind: Literal["damage"] = "damage"
    source_uuid: Optional[str] = None
    target_uuid: str = Field(min_length=1)
    applied_amount: int = Field(ge=0)
    resulting_hp: int
    damage_types: Tuple[PresentationDamageType, ...] = Field(
        min_length=1,
        description=(
            "Ordered packet categories before packet-level affinity, reduction, and HP-cap math; "
            "no per-type share of applied damage is asserted."
        ),
    )


class HealPresentationCue(PresentationCueBase):
    kind: Literal["heal"] = "heal"
    source_uuid: Optional[str] = None
    target_uuid: str = Field(min_length=1)
    amount: int = Field(ge=0)
    resulting_hp: int


class LifecycleCauseKind(str, Enum):
    """Non-damage/heal engine causes that can commit a life-state change."""

    DEATH_SAVE = "death_save"
    REVIVE = "revive"
    INSTANT_DEATH = "instant_death"
    DIRECT_STATE_CHECK = "direct_state_check"


class DeathSaveOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CRITICAL_SUCCESS = "critical_success"
    CRITICAL_FAILURE = "critical_failure"


class LifecycleCausePresentationCue(PresentationCueBase):
    """Typed safe impact for lifecycle changes with no damage/heal sibling."""

    kind: Literal["lifecycle_cause"] = "lifecycle_cause"
    entity_uuid: str = Field(min_length=1)
    cause_kind: LifecycleCauseKind
    source_uuid: Optional[str] = None
    death_save_outcome: Optional[DeathSaveOutcome] = None

    @model_validator(mode="after")
    def validate_cause_detail(self) -> "LifecycleCausePresentationCue":
        if self.cause_kind is LifecycleCauseKind.DEATH_SAVE:
            if self.death_save_outcome is None:
                raise ValueError("death-save lifecycle cause requires a typed outcome")
        elif self.death_save_outcome is not None:
            raise ValueError("death-save outcome is valid only for a death-save cause")
        if len(self.child_presentation_ids) != 1:
            raise ValueError("lifecycle cause must own exactly one life-state child")
        return self


class LifeStatePresentationCue(PresentationCueBase):
    kind: Literal["life_state"] = "life_state"
    entity_uuid: str = Field(min_length=1)
    previous: LifeState
    current: LifeState
    reason: LifeStateChangeReason
    causing_effect_presentation_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_transition(self) -> "LifeStatePresentationCue":
        if self.previous is self.current:
            raise ValueError("life-state presentation requires a real transition")
        if self.parent_presentation_id != self.causing_effect_presentation_id:
            raise ValueError("life-state transition must attach to its causing impact")
        if self.current is LifeState.STABLE and self.reason is not LifeStateChangeReason.STABILIZATION:
            raise ValueError("stable transition requires stabilization reason")
        if self.previous is LifeState.DEAD and self.current is LifeState.ALIVE:
            if self.reason is not LifeStateChangeReason.REVIVAL:
                raise ValueError("dead-to-alive transition requires revival reason")
        if self.current is LifeState.ALIVE and self.previous in {LifeState.DYING, LifeState.STABLE}:
            if self.reason not in {
                LifeStateChangeReason.HEALING,
                LifeStateChangeReason.DIRECT_STATE_CHECK,
            }:
                raise ValueError("recovery to alive requires healing or a direct-state correction")
        return self


class ConditionOperation(str, Enum):
    APPLIED = "applied"
    REMOVED = "removed"


class ConditionPresentationCue(PresentationCueBase):
    kind: Literal["condition"] = "condition"
    target_uuid: str = Field(min_length=1)
    condition_semantic_key: str = Field(
        min_length=1,
        description="Stable condition identity used for renderer dispatch.",
    )
    condition_name: str = Field(min_length=1)
    condition_category: Optional[str] = None
    operation: ConditionOperation


class DoorPresentationCue(PresentationCueBase):
    kind: Literal["door"] = "door"
    object_uuid: str = Field(min_length=1)
    position: Position
    is_open: bool


class LightPresentationCue(PresentationCueBase):
    """Complete observer-relative light replacement for one presentation tick."""

    kind: Literal["light"] = "light"
    observer_uuid: str = Field(min_length=1)
    mode: Literal["replacement"] = "replacement"
    cells: Tuple[EffectiveLightCell, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_light_projection(self) -> "LightPresentationCue":
        positions = [cell.position for cell in self.cells]
        if len(positions) != len(set(positions)):
            raise ValueError("light replacement positions must be unique")
        return self


class EquipmentPresentationCue(PresentationCueBase):
    kind: Literal["equipment"] = "equipment"
    entity_uuid: str = Field(min_length=1)
    visual_loadout: EntityVisualLoadout

    @model_validator(mode="after")
    def validate_loadout_owner(self) -> "EquipmentPresentationCue":
        if self.visual_loadout.entity_uuid != self.entity_uuid:
            raise ValueError("equipment cue loadout must belong to the presented entity")
        return self


class EncounterTransition(str, Enum):
    START = "start"
    ROUND_START = "round_start"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    ROUND_END = "round_end"
    END = "end"


class EncounterPresentationCue(PresentationCueBase):
    kind: Literal["encounter"] = "encounter"
    encounter_uuid: str = Field(min_length=1)
    transition: EncounterTransition
    round_number: int = Field(ge=0)
    acting_entity_uuid: Optional[str] = None
    reason: Optional[str] = None
    terminal_barrier: bool = False
    projected_combatant_uuids: Tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_terminal_boundary(self) -> "EncounterPresentationCue":
        if len(set(self.projected_combatant_uuids)) != len(self.projected_combatant_uuids):
            raise ValueError("projected terminal combatants must be unique")
        if self.transition is EncounterTransition.END:
            if not self.terminal_barrier:
                raise ValueError("encounter end requires an explicit safe terminal barrier")
        elif self.terminal_barrier or self.projected_combatant_uuids:
            raise ValueError("terminal metadata is valid only for encounter end")
        return self


SubjectivePresentationCue: TypeAlias = Annotated[
    Union[
        MovementPresentationCue,
        ForcedMovementPresentationCue,
        ShovePresentationCue,
        CounterspellPresentationCue,
        ItemActionPresentationCue,
        AttackPresentationCue,
        SpellPresentationCue,
        DamagePresentationCue,
        HealPresentationCue,
        LifecycleCausePresentationCue,
        LifeStatePresentationCue,
        ConditionPresentationCue,
        DoorPresentationCue,
        LightPresentationCue,
        EquipmentPresentationCue,
        EncounterPresentationCue,
    ],
    Field(discriminator="kind"),
]


class SubjectiveReplicationFrame(PlayerReplicationModel):
    """One ordered perspective-safe world/presentation transaction."""

    source_stream_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    perspective_epoch_id: str = Field(min_length=1)
    watermarks: PlayerReplicationWatermarks
    presentation_from_cursor: int = Field(
        ge=0,
        description="Presentation cursor consumed immediately before this frame.",
    )
    patches: Tuple[SubjectiveWorldPatch, ...] = Field(default_factory=tuple)
    presentation: Tuple[SubjectivePresentationCue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_presentation_window(self) -> "SubjectiveReplicationFrame":
        through = self.watermarks.presentation_cursor
        if self.presentation_from_cursor > through:
            raise ValueError("presentation_from_cursor exceeds frame watermark")
        if len(self.presentation) != through - self.presentation_from_cursor:
            raise ValueError("presentation cues must cover the exact local cursor window")
        by_id: dict[str, PresentationCueBase] = {}
        for expected, cue in enumerate(
            self.presentation,
            start=self.presentation_from_cursor + 1,
        ):
            if cue.presentation_cursor != expected:
                raise ValueError("presentation cues must be contiguous and ordered")
            if cue.source_event_cursor > self.watermarks.source_event_cursor:
                raise ValueError("presentation cue exceeds the source event watermark")
            if cue.presentation_id in by_id:
                raise ValueError("one presentation ID must identify exactly one cue")
            by_id[cue.presentation_id] = cue

        for cue in self.presentation:
            if cue.parent_presentation_id is not None:
                parent = by_id.get(cue.parent_presentation_id)
                if parent is None:
                    raise ValueError("presentation graph cannot reference a parent outside its frame")
                if cue.presentation_id not in parent.child_presentation_ids:
                    raise ValueError("presentation parent/child edges must be bidirectional")
                if parent.presentation_cursor >= cue.presentation_cursor:
                    raise ValueError("presentation parent must precede its child")
            for child_id in cue.child_presentation_ids:
                child = by_id.get(child_id)
                if child is None:
                    raise ValueError("presentation graph cannot contain a hidden or dangling child")
                if child.parent_presentation_id != cue.presentation_id:
                    raise ValueError("presentation child/parent edges must be bidirectional")
            child_cursors = [by_id[child_id].presentation_cursor for child_id in cue.child_presentation_ids]
            if child_cursors != sorted(child_cursors):
                raise ValueError("presentation child IDs must preserve delivery order")

        for cue in self.presentation:
            if isinstance(cue, MovementPresentationCue):
                for child_id in cue.child_presentation_ids:
                    child = by_id[child_id]
                    if not isinstance(
                        child,
                        (
                            AttackPresentationCue,
                            SpellPresentationCue,
                            ShovePresentationCue,
                        ),
                    ):
                        raise ValueError(
                            "movement children must be pre-motion attack, spell, or shove reactions"
                        )
                    if child.source_event_cursor >= cue.source_event_cursor:
                        raise ValueError(
                            "movement reactions must resolve before the owning segment commits"
                        )
            elif isinstance(cue, ShovePresentationCue):
                if cue.outcome is ShoveOutcome.SUCCEEDED_PUSH:
                    forced_id = cue.forced_movement_presentation_id
                    if forced_id is None:
                        raise ValueError("successful push requires its forced-movement ID")
                    forced = by_id.get(forced_id)
                    if not isinstance(forced, ForcedMovementPresentationCue):
                        raise ValueError("shove forced-movement ID must identify a forced movement cue")
                    if forced.cause is not ForcedMovementCause.SHOVE:
                        raise ValueError("shove child must declare shove as its cause")
                    if forced.source_uuid != cue.actor_uuid or forced.entity_uuid != cue.target_uuid:
                        raise ValueError("shove actor/target must match its forced movement")
                elif cue.outcome is ShoveOutcome.SUCCEEDED_PRONE:
                    condition_id = cue.prone_condition_presentation_id
                    if condition_id is None:
                        raise ValueError("successful prone shove requires its condition ID")
                    condition = by_id.get(condition_id)
                    if not isinstance(condition, ConditionPresentationCue):
                        raise ValueError("prone-condition ID must identify a condition cue")
                    if (
                        condition.target_uuid != cue.target_uuid
                        or condition.condition_name != "Prone"
                        or condition.operation is not ConditionOperation.APPLIED
                    ):
                        raise ValueError("prone shove must apply Prone to its target")
            elif isinstance(cue, ForcedMovementPresentationCue):
                parent = by_id[cue.actor_action_presentation_id]
                if cue.cause is ForcedMovementCause.SHOVE and not isinstance(parent, ShovePresentationCue):
                    raise ValueError("shove movement must attach to a shove action")
                if cue.cause is ForcedMovementCause.SPELL and not isinstance(parent, SpellPresentationCue):
                    raise ValueError("spell movement must attach to a spell action")
            elif isinstance(cue, AttackPresentationCue):
                for child_id in cue.child_presentation_ids:
                    child = by_id[child_id]
                    if not isinstance(
                        child,
                        (DamagePresentationCue, HealPresentationCue, ConditionPresentationCue),
                    ):
                        raise ValueError("action impact IDs must identify damage, heal, or condition cues")
                    if child.target_uuid != cue.target_uuid:
                        raise ValueError("attack impact target must match the attacked entity")
                    if (
                        isinstance(child, (DamagePresentationCue, HealPresentationCue))
                        and child.source_uuid != cue.actor_uuid
                    ):
                        raise ValueError("attack impact source must match the attacking actor")
            elif isinstance(cue, ItemActionPresentationCue):
                for child_id in cue.child_presentation_ids:
                    child = by_id[child_id]
                    if not isinstance(
                        child,
                        (DamagePresentationCue, HealPresentationCue, ConditionPresentationCue),
                    ):
                        raise ValueError("item impact IDs must identify damage, heal, or condition cues")
                    if child.target_uuid != cue.actor_uuid:
                        raise ValueError("drink-item impact target must match the acting entity")
                    if (
                        isinstance(child, (DamagePresentationCue, HealPresentationCue))
                        and child.source_uuid != cue.actor_uuid
                    ):
                        raise ValueError("drink-item impact source must match the acting entity")
            elif isinstance(cue, SpellPresentationCue):
                targets_by_effect = {
                    effect_id: target
                    for target in cue.targets
                    for effect_id in target.effect_presentation_ids
                }
                for effect_id, target in targets_by_effect.items():
                    effect = by_id[effect_id]
                    if not isinstance(
                        effect,
                        (
                            DamagePresentationCue,
                            HealPresentationCue,
                            ConditionPresentationCue,
                            ForcedMovementPresentationCue,
                        ),
                    ):
                        raise ValueError(
                            "spell impact IDs must identify damage, heal, condition, or forced-movement cues"
                        )
                    effect_target = (
                        effect.entity_uuid
                        if isinstance(effect, ForcedMovementPresentationCue)
                        else effect.target_uuid
                    )
                    if effect_target != target.target_uuid:
                        raise ValueError("spell impact effect target must match its application")
                    if isinstance(
                        effect,
                        (DamagePresentationCue, HealPresentationCue, ForcedMovementPresentationCue),
                    ) and effect.source_uuid != cue.actor_uuid:
                        raise ValueError("spell impact source must match the casting actor")
            elif isinstance(cue, LifecycleCausePresentationCue):
                child = by_id[cue.child_presentation_ids[0]]
                if not isinstance(child, LifeStatePresentationCue):
                    raise ValueError("lifecycle cause must own a life-state transition")
                if child.entity_uuid != cue.entity_uuid:
                    raise ValueError("lifecycle cause and life-state transition must affect the same entity")

                if cue.cause_kind is LifecycleCauseKind.DEATH_SAVE:
                    if child.reason not in {
                        LifeStateChangeReason.STABILIZATION,
                        LifeStateChangeReason.DEATH_SAVE_FAILURES,
                    }:
                        raise ValueError("death-save cause requires stabilization or death-save-failures reason")
                    if child.reason is LifeStateChangeReason.STABILIZATION:
                        if cue.death_save_outcome is not DeathSaveOutcome.SUCCESS:
                            raise ValueError("death-save stabilization requires a successful save outcome")
                    elif cue.death_save_outcome not in {
                        DeathSaveOutcome.FAILURE,
                        DeathSaveOutcome.CRITICAL_FAILURE,
                    }:
                        raise ValueError("death-save death requires a failed save outcome")
                elif cue.cause_kind is LifecycleCauseKind.REVIVE:
                    if child.reason is not LifeStateChangeReason.REVIVAL:
                        raise ValueError("revive cause requires revival reason")
                elif cue.cause_kind is LifecycleCauseKind.INSTANT_DEATH:
                    if child.reason is not LifeStateChangeReason.INSTANT_DEATH:
                        raise ValueError("instant-death cause requires instant-death reason")
                elif child.reason is not LifeStateChangeReason.DIRECT_STATE_CHECK:
                    raise ValueError("direct-state cause requires direct-state-check reason")
            elif isinstance(cue, LifeStatePresentationCue):
                cause = by_id[cue.causing_effect_presentation_id]
                if not isinstance(
                    cause,
                    (
                        DamagePresentationCue,
                        HealPresentationCue,
                        LifecycleCausePresentationCue,
                    ),
                ):
                    raise ValueError(
                        "life-state cause must be a delivered damage, heal, or lifecycle impact"
                    )
                cause_entity_uuid = (
                    cause.entity_uuid
                    if isinstance(cause, LifecycleCausePresentationCue)
                    else cause.target_uuid
                )
                if cause_entity_uuid != cue.entity_uuid:
                    raise ValueError("life-state cause must affect the transitioning entity")
                if isinstance(cause, DamagePresentationCue) and cue.reason not in {
                    LifeStateChangeReason.DAMAGE,
                    LifeStateChangeReason.MASSIVE_DAMAGE,
                }:
                    raise ValueError("damage impact requires a damage life-state reason")
                if isinstance(cause, HealPresentationCue) and cue.reason is not LifeStateChangeReason.HEALING:
                    raise ValueError("heal impact requires a healing life-state reason")
        return self


class SubjectiveFramesResponse(PlayerReplicationModel):
    """Exact observation page with independent through/captured watermarks."""

    source_stream_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    perspective_epoch_id: str = Field(min_length=1)
    retained_from_observation_cursor: int = Field(ge=0)
    from_watermarks: PlayerReplicationWatermarks
    through_watermarks: PlayerReplicationWatermarks
    captured_watermarks: PlayerReplicationWatermarks
    frames: Tuple[SubjectiveReplicationFrame, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_exact_page(self) -> "SubjectiveFramesResponse":
        if self.retained_from_observation_cursor > self.from_watermarks.observation_cursor:
            raise ValueError("requested observation cursor precedes retained history")
        if not self.through_watermarks.dominates(self.from_watermarks):
            raise ValueError("through watermarks must not move backwards")
        if not self.captured_watermarks.dominates(self.through_watermarks):
            raise ValueError("captured watermarks must cover returned history")
        if len(self.frames) != (
            self.through_watermarks.observation_cursor
            - self.from_watermarks.observation_cursor
        ):
            raise ValueError("frames must cover the exact observation cursor window")

        previous = self.from_watermarks
        presentation_ids: set[str] = set()
        for expected_observation_cursor, frame in enumerate(
            self.frames,
            start=self.from_watermarks.observation_cursor + 1,
        ):
            if frame.source_stream_id != self.source_stream_id:
                raise ValueError("frame source stream does not match response")
            if frame.generation_id != self.generation_id:
                raise ValueError("frame generation does not match response")
            if frame.perspective_epoch_id != self.perspective_epoch_id:
                raise ValueError("frame perspective epoch does not match response")
            if frame.watermarks.observation_cursor != expected_observation_cursor:
                raise ValueError("observation frames must be contiguous and ordered")
            if not frame.watermarks.dominates(previous):
                raise ValueError("frame watermarks must not move backwards")
            if frame.presentation_from_cursor != previous.presentation_cursor:
                raise ValueError("frame presentation windows must be contiguous")
            frame_ids = {cue.presentation_id for cue in frame.presentation}
            if presentation_ids & frame_ids:
                raise ValueError("presentation IDs must remain unique across response frames")
            presentation_ids.update(frame_ids)
            previous = frame.watermarks
        if previous != self.through_watermarks:
            raise ValueError("through watermarks must equal the last returned frame")
        return self


class SubjectiveReplicationBootstrap(PlayerReplicationModel):
    """Atomic player reducer seed, authority epoch, and exact log history."""

    protocol: PlayerReplicationProtocolIdentity
    perspective: SubjectivePerspective
    watermarks: PlayerReplicationWatermarks
    world: SubjectiveReplicatedWorld
    combat_log_frames: SubjectiveCombatLogFramesResponse

    @model_validator(mode="after")
    def validate_atomic_projection(self) -> "SubjectiveReplicationBootstrap":
        protocol = self.protocol
        perspective = self.perspective
        world = self.world
        controlled = set(perspective.controlled_entity_uuids)
        observers = set(perspective.observer_entity_uuids)
        entity_uuids = {entity.uuid for entity in world.state.entities}

        if not controlled <= entity_uuids:
            raise ValueError("controlled entities must exist in projected state")
        if not observers <= entity_uuids:
            raise ValueError("authorized observers must exist in projected state")
        if set(world.visibility.root) != observers:
            raise ValueError("visibility rows must exactly match the authorized observer union")
        if set(world.equipment_by_entity) != controlled:
            raise ValueError("full equipment must exist for controlled entities only")

        logs = self.combat_log_frames
        if logs.projection is not CombatLogProjection.SUBJECTIVE:
            raise ValueError("player combat logs must use subjective projection")
        if logs.source_stream_id != protocol.source_stream_id:
            raise ValueError("combat-log source stream does not match protocol")
        if logs.generation_id != protocol.generation_id:
            raise ValueError("combat-log generation does not match protocol")
        if logs.perspective_epoch_id != perspective.perspective_epoch_id:
            raise ValueError("combat-log perspective epoch does not match bootstrap")
        if logs.from_cursor != logs.retained_from_cursor:
            raise ValueError("bootstrap combat logs must start at the retained boundary")
        if logs.through_cursor != logs.total:
            raise ValueError("bootstrap combat logs must reach the captured boundary")
        if logs.total != self.watermarks.combat_log_cursor:
            raise ValueError("combat-log watermark does not match bootstrap history")
        if any(
            frame.event_cursor > self.watermarks.source_event_cursor
            for frame in logs.frames
        ):
            raise ValueError("combat-log barrier exceeds bootstrap source watermark")
        return self


# ---------------------------------------------------------------------------
# Route-neutral live delivery envelopes


class SubjectiveSyncDelivery(PlayerReplicationModel):
    kind: Literal["sync"] = "sync"
    protocol: PlayerReplicationProtocolIdentity
    perspective: SubjectivePerspective
    watermarks: PlayerReplicationWatermarks


class SubjectiveFrameDelivery(PlayerReplicationModel):
    kind: Literal["frame"] = "frame"
    frame: SubjectiveReplicationFrame


class SubjectiveCombatLogDelivery(PlayerReplicationModel):
    kind: Literal["combat_log"] = "combat_log"
    watermarks: PlayerReplicationWatermarks
    frame: SubjectiveCombatLogFrame

    @model_validator(mode="after")
    def validate_log_delivery(self) -> "SubjectiveCombatLogDelivery":
        if self.frame.projection is not CombatLogProjection.SUBJECTIVE:
            raise ValueError("player combat-log delivery must be subjective")
        if self.frame.combat_log_cursor > self.watermarks.combat_log_cursor:
            raise ValueError("combat-log frame exceeds delivery watermark")
        if self.frame.event_cursor > self.watermarks.source_event_cursor:
            raise ValueError("combat-log barrier exceeds source-event watermark")
        return self


SubjectiveStreamDelivery: TypeAlias = Annotated[
    Union[
        SubjectiveSyncDelivery,
        SubjectiveFrameDelivery,
        SubjectiveCombatLogDelivery,
    ],
    Field(discriminator="kind"),
]


def player_replication_wire_schema() -> dict[str, object]:
    """Return the complete transitive schema authenticated by the decoder hash."""
    return {
        "contract_version": PLAYER_REPLICATION_CONTRACT_VERSION,
        "canonical_routes": (
            "/replication/bootstrap",
            "/replication/frames",
            "/replication/combat-log",
            "/replication/subscribe",
        ),
        "semantics": _PLAYER_REPLICATION_SEMANTICS,
        "bootstrap": SubjectiveReplicationBootstrap.model_json_schema(mode="serialization"),
        "frames": SubjectiveFramesResponse.model_json_schema(mode="serialization"),
        "combat_log": SubjectiveCombatLogFramesResponse.model_json_schema(
            mode="serialization"
        ),
        "stream": TypeAdapter(SubjectiveStreamDelivery).json_schema(mode="serialization"),
    }


PLAYER_REPLICATION_CONTRACT_HASH = hashlib.sha256(
    json.dumps(
        player_replication_wire_schema(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def player_replication_contract_summary() -> dict[str, object]:
    """Return stable player decoder identity for generators and SDK checks."""
    return {
        "player_replication_contract_version": PLAYER_REPLICATION_CONTRACT_VERSION,
        "player_replication_contract_hash": PLAYER_REPLICATION_CONTRACT_HASH,
    }


__all__ = [
    "ActiveWeaponSet",
    "ActorVisualSlot",
    "AreaGeometry",
    "AreaShape",
    "AttackDelivery",
    "AttackOutcome",
    "AttackPresentationCue",
    "ConeAreaGeometry",
    "ConditionOperation",
    "ConditionPresentationCue",
    "ControlledEquipmentReplacePatch",
    "CubeAreaGeometry",
    "CylinderAreaGeometry",
    "BehaviorPresentationRole",
    "CounterspellAutomaticSuccess",
    "CounterspellCheckFailure",
    "CounterspellCheckSuccess",
    "CounterspellPresentationCue",
    "CounterspellResolution",
    "DamagePresentationCue",
    "DeathSaveOutcome",
    "DoorPresentationCue",
    "DoorStatePatch",
    "EffectiveLightCell",
    "EncounterPresentationCue",
    "EncounterReplacePatch",
    "EncounterTransition",
    "EntityRemovePatch",
    "EntityUpsertPatch",
    "EntityVisualLoadout",
    "EquipmentPresentationCue",
    "FloorObjectRemovePatch",
    "FloorObjectBlockingChannel",
    "FloorObjectDirection",
    "FloorObjectProjectionKind",
    "FloorObjectUpsertPatch",
    "ForcedMovementCause",
    "ForcedMovementPresentationCue",
    "HealPresentationCue",
    "ItemActionKind",
    "ItemActionPresentationCue",
    "LifecycleCauseKind",
    "LifecycleCausePresentationCue",
    "LifeStatePresentationCue",
    "LineAreaGeometry",
    "LightPresentationCue",
    "MovementKind",
    "MovementPresentationCue",
    "ObserverVisibilityRemovePatch",
    "ObserverVisibilityReplacePatch",
    "PLAYER_REPLICATION_CONTRACT_HASH",
    "PLAYER_REPLICATION_CONTRACT_VERSION",
    "PerspectiveKind",
    "PlayerReplicationProtocolIdentity",
    "PlayerReplicationWatermarks",
    "PresentationContentAttribution",
    "PresentationDamageType",
    "PresentationProjectile",
    "PresentationSpellSchool",
    "PresentationWeaponSlot",
    "ShoveOutcome",
    "ShovePresentationCue",
    "RootedBehaviorPresentationAttribution",
    "SourceItemPresentationAttribution",
    "SphereAreaGeometry",
    "SpellApplicationOutcome",
    "SpellDelivery",
    "SpellPresentationCue",
    "SpellTargetPresentation",
    "SubjectiveCombatLogDelivery",
    "SubjectiveCombatLogFrame",
    "SubjectiveCombatLogFramesResponse",
    "SubjectiveCombatant",
    "SubjectiveFrameDelivery",
    "SubjectiveFramesResponse",
    "SubjectiveFloorObject",
    "SubjectiveGameState",
    "SubjectiveEncounter",
    "SubjectivePerspective",
    "SubjectivePresentationCue",
    "SubjectiveReplicatedWorld",
    "SubjectiveReplicationBootstrap",
    "SubjectiveReplicationFrame",
    "SubjectiveStreamDelivery",
    "SubjectiveSyncDelivery",
    "SubjectiveWorldPatch",
    "TileUpsertPatch",
    "UnrootedBehaviorPresentationAttribution",
    "VisualEquipmentLayer",
    "VisualLoadoutSlot",
    "VisualLoadoutReplacePatch",
    "player_replication_contract_summary",
    "player_replication_wire_schema",
]
