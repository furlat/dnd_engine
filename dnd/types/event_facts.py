"""Shared passive event vocabulary and world after-values."""

from enum import Enum
from typing import Tuple, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from dnd.types.materials import TileSurface
from dnd.types.world import LightLevel
from dnd.types.residues import TileResidueState
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.core.traversal_connectors import ConnectorActionCostType, ConnectorProvocationPolicy, TraversalConnectorKind


class EventType(str, Enum):
    """Kinds of state transitions that handlers and logs can subscribe to."""

    BASE_ACTION = "base_action"
    ATTACK = "attack"
    MOVEMENT = "movement"
    STEP_MOVEMENT = "step_movement"
    FORCED_MOVEMENT = "forced_movement"
    PORTAL_TRANSFER = "portal_transfer"
    MECHANISM_ACTIVATION = "mechanism_activation"
    ABILITY_CHECK = "ability_check"
    SAVING_THROW = "saving_throw"
    SKILL_CHECK = "skill_check"
    INFLICT_DAMAGE = "inflicted_damage"
    TAKE_DAMAGE = "take_damage"
    DAMAGE_APPLIED = "damage_applied"
    HEAL = "heal"
    TEMPORARY_HIT_POINTS_CHANGED = "temporary_hit_points_changed"
    CAST_SPELL = "cast_spell"
    ATTACK_MISS = "attack_miss"
    ATTACK_HIT = "attack_hit"
    ATTACK_CRITICAL = "attack_critical"
    CONDITION_APPLICATION = "condition_application"
    CONDITION_REMOVAL = "condition_removal"
    CONDITION_STATE_CHANGED = "condition_state_changed"
    WEAPON_EQUIP = "weapon_equip"
    WEAPON_UNEQUIP = "weapon_unequip"
    ARMOR_EQUIP = "armor_equip"
    ARMOR_UNEQUIP = "armor_unequip"
    SHIELD_EQUIP = "shield_equip"
    SHIELD_UNEQUIP = "shield_unequip"
    ITEM_LOCATION_STATE = "item_location_state"
    ITEM_HOLDINGS_RELEASED = "item_holdings_released"
    ITEM_DESTRUCTION = "item_destruction"
    ITEM_CHARGE_CONSUMPTION = "item_charge_consumption"
    WORLD_INITIALIZED = "world_initialized"
    WORLD_MODIFIED = "world_modified"
    ENTITY_CREATED = "entity_created"
    ENTITY_LEVEL_ADDED = "entity_level_added"
    ENTITY_LEVEL_REMOVED = "entity_level_removed"

    TRIGGER_EVENT = "trigger_event"

    DICE_ROLL = "dice_roll"
    D20_ROLL_RESULT = "d20_roll_result"
    ATTACK_D20_ROLL_RESULT = "attack_d20_roll"
    SAVE_D20_ROLL_RESULT = "save_d20_roll"
    CHECK_D20_ROLL_RESULT = "check_d20_roll"
    DAMAGE_ROLL_RESULT = "damage_roll_result"
    HEAL_ROLL_RESULT = "heal_roll_result"
    ENEMY_SPOTTED = "enemy_spotted"
    ENEMY_KILLED = "enemy_killed"
    ENEMY_ENGAGED = "enemy_engaged"

    SPATIAL_ENTITY_ENTERED = "spatial_entity_entered"
    SPATIAL_ENTITY_LEFT = "spatial_entity_left"
    SPATIAL_TILE_CHANGED = "spatial_tile_changed"
    SPATIAL_OBJECT_PLACED = "spatial_object_placed"
    SPATIAL_OBJECT_REMOVED = "spatial_object_removed"
    SPATIAL_PERCEIVABILITY_CHANGED = "spatial_perceivability_changed"
    SPATIAL_LIGHT_CHANGED = "spatial_light_changed"
    SPATIAL_OBJECT_CHANGED = "spatial_object_changed"
    TRAVERSAL_CONNECTOR_CHANGED = "traversal_connector_changed"
    MOVEMENT_COLLISION = "movement_collision"
    SENSORY_UPDATE = "sensory_update"
    SPATIAL_EFFECT_CHANGED = "spatial_effect_changed"
    SPATIAL_EFFECT_INTERACTION = "spatial_effect_interaction"
    AREA_REACHED = "area_reached"
    FIRE_EXPOSURE = "fire_exposure"
    EXPOSED_FLAME_IGNITED = "exposed_flame_ignited"
    WIND_EXPOSURE = "wind_exposure"

    ENCOUNTER_START = "encounter_start"
    ENCOUNTER_END = "encounter_end"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    LIFE_STATE_CHANGE = "life_state_change"
    REVIVE = "revive"
    DEATH_SAVE = "death_save"
    INSTANT_DEATH = "instant_death"
    DEATH = "death"



class MovementTrajectory(str, Enum):
    """Geometry used to present an ordered voluntary movement transition."""

    PATH = "path"
    DIRECT_ARC = "direct_arc"
    CONNECTOR_TRANSFER = "connector_transfer"



class SpatialChangeType(str, Enum):
    """Types of spatial changes that can occur."""
    ENTITY_ENTERED = "entity_entered"
    ENTITY_LEFT = "entity_left"
    TILE_CHANGED = "tile_changed"
    TILE_CREATED = "tile_created"
    TILE_REMOVED = "tile_removed"
    OBJECT_PLACED = "object_placed"
    OBJECT_REMOVED = "object_removed"
    PERCEIVABILITY_CHANGED = "perceivability_changed"
    LIGHT_CHANGED = "light_changed"
    OBJECT_CHANGED = "object_changed"
    MOVEMENT_COLLISION = "movement_collision"



class EventPhase(str, Enum):
    """Lifecycle phase for one logical event lineage.

    `DECLARATION`, `EXECUTION`, and `EFFECT` are handler-visible phases.
    `COMPLETION` stores final lineage and combat-log data but does not dispatch
    event handlers. `CANCEL` records an aborted lineage.
    """

    DECLARATION = "declaration"
    EXECUTION = "execution"
    EFFECT = "effect"
    COMPLETION = "completion"
    CANCEL = "cancel"



class WorldTileState(BaseModel):
    """Complete renderer-neutral state of one admitted support Tile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tile_uuid: UUID
    position: Tuple[int, int]
    surface: TileSurface
    name: str
    blocks_optics: bool
    blocks_propagation: bool
    walking_cost: StrictInt = Field(ge=0)
    flying_cost: StrictInt = Field(ge=0)
    swimming_cost: StrictInt = Field(ge=0)
    burrowing_cost: StrictInt = Field(ge=0)
    elevation_steps: StrictInt
    surface_kind: ElevationSurfaceKind
    slope_axis: Optional[SlopeAxis] = None
    default_light: LightLevel
    resolved_light: LightLevel
    condition_names: Tuple[str, ...] = ()
    residues: tuple[TileResidueState, ...] = ()



class WorldConnectorState(BaseModel):
    """Complete renderer-neutral state of one admitted connector."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connector_uuid: UUID
    authored_id: str
    kind: TraversalConnectorKind
    presentation_key: str
    endpoints: Tuple[Tuple[int, int], Tuple[int, int]]
    support_tile_uuids: Tuple[UUID, UUID]
    endpoint_elevations_feet: Tuple[int, int]
    movement_cost_feet: StrictInt = Field(ge=0)
    action_cost_type: Optional[ConnectorActionCostType] = None
    action_cost_amount: StrictInt = Field(default=0, ge=0)
    bidirectional: bool
    enabled: bool
    provocation_policy: ConnectorProvocationPolicy

