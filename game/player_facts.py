"""Passive player values: causal structure, permitted facts, and observed world.

Native event recordings remain private. These records deliberately have no
engine constructors, executable state, audience grant maps, or diagnostic rows.
"""

from dataclasses import dataclass, field
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, BeforeValidator
from game.recording_compat import upgrade_player_fact

from dnd.blocks.appearance import AppearanceConfig
from dnd.core.action_execution import MovementProvocationPolicy
from dnd.core.combat_log import CombatLogEntry
from dnd.core.content.runtime import HandlerDispatchOutcome
from dnd.core.creature_types import DamageType, Size
from dnd.core.dice import AttackOutcome
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import EventPhase, EventType, MovementTrajectory, SpatialChangeType, WorldConnectorState, WorldTileState
from dnd.core.item_types import (DoorMechanism, DoorSwing, EquippedVisualPolicy, ItemConcentrationSlot,
    ItemIntegrity, ItemPresentationKind, ItemPresentationState, ItemRemnantState)
from dnd.core.life_types import LifeState, LifeStateChangeReason
from dnd.core.presentation_geometry import AoEPresentationGeometry
from dnd.types.residues import BodyReleaseResult, ObjectResidueState
from dnd.types.senses import PerceivedContact, PerceivedSpatialEffect, SenseMode, SensesSnapshot
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.traps import TrapState
from dnd.types.world import MovementMode, OccupancyLayer
from dnd.types.world_placement import BoundaryStructure, WorldObjectPlacement
from dnd.types.abilities import AbilityName
from dnd.types.actor import TemporaryHitPointsGrant
from game.actor_facts import ConditionFact


@dataclass(frozen=True, slots=True, kw_only=True)
class VisualItem:
    slot: str
    item_uuid: UUID
    item_id: str
    item_kind: ItemPresentationKind
    visual_item_name: str
    visual_variant_id: str | None
    equipped_visual_policy: EquippedVisualPolicy


@dataclass(frozen=True, slots=True, kw_only=True)
class VisualLoadout:
    active_weapon_set: WeaponSet
    layers: tuple[VisualItem, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerActor:
    uuid: UUID
    name: str
    character_body_id: str | None
    creature_content_ref: str | None
    appearance: AppearanceConfig
    visual_loadout: VisualLoadout
    normal_hp: int
    maximum_hp: int
    temporary_hp: int
    life_state: LifeState
    armor_class: int
    conditions: tuple[ConditionFact, ...] = ()
    last_visual_position: tuple[int, int] | None = None
    controlled_items: tuple[ItemPresentationState, ...] | None = None
    occupancy_layer: OccupancyLayer | None = None
    temporary_hp_grant: TemporaryHitPointsGrant | None = None
    resolved_size: Size | None = None
    structural_base_size: Size | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerObservation:
    event_uuid: UUID
    actor: PlayerActor
    contact: PerceivedContact | None


@dataclass(frozen=True, slots=True, kw_only=True)
class AttackFact:
    kind: Literal["attack"] = "attack"
    source_entity_uuid: UUID
    target_entity_uuid: UUID
    behavior_id: str | None
    name: str | None
    weapon_slot: WeaponSlot
    attack_outcome: AttackOutcome | None
    damage_types: tuple[DamageType, ...]
    source_item_id: str | None
    intercepted_by_condition_uuid: UUID | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SpellFact:
    kind: Literal["spell"] = "spell"
    source_entity_uuid: UUID
    target_entity_uuid: UUID | None
    behavior_id: str | None
    name: str | None
    source_position: tuple[int, int] | None
    declared_target_entity_uuids: tuple[UUID, ...]
    application_id: UUID | None
    application_index: int | None
    attack_outcome: AttackOutcome | None = None
    cast_origin: Literal["actor", "source_item"] = "actor"
    source_item_uuid: UUID | None = None
    effect_id: str | None = None
    aoe_position: tuple[int, int] | None = None
    area_geometry: AoEPresentationGeometry | None = None
    # A disclosed subset of the native result, never a physical blast mask.
    # None means no recorded result; () is a resolved result with no granted cells.
    resolved_area_positions: tuple[tuple[int, int], ...] | None = None
    suppressions: tuple[SpellSuppression, ...] = ()
    area_propagation: Literal["line_of_effect", "connected"] = "line_of_effect"


@dataclass(frozen=True, slots=True, kw_only=True)
class MovementFact:
    kind: Literal["movement"] = "movement"
    source_entity_uuid: UUID
    trajectory: MovementTrajectory
    # Root geometry is present only for a fully permitted atomic trajectory.
    start_position: tuple[int, int] | None = None
    end_position: tuple[int, int] | None = None
    requested_end_position: tuple[int, int] | None = None
    path: tuple[tuple[int, int], ...] = ()
    start_elevation_feet: int | None = None
    end_elevation_feet: int | None = None
    movement_mode: MovementMode | None = None
    start_layer: OccupancyLayer | None = None
    end_layer: OccupancyLayer | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class StepFact:
    kind: Literal["step"] = "step"
    source_entity_uuid: UUID
    from_position: tuple[int, int]
    to_position: tuple[int, int]
    from_elevation_feet: int
    to_elevation_feet: int
    disclosed_path: tuple[tuple[int, int], ...]
    trajectory: MovementTrajectory
    provocation_policy: MovementProvocationPolicy
    committed: bool
    resolved_speed_feet: int | None = None
    movement_mode: MovementMode | None = None
    from_layer: OccupancyLayer | None = None
    to_layer: OccupancyLayer | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ForcedMovementFact:
    kind: Literal["forced_movement"] = "forced_movement"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    start_position: tuple[int, int]
    end_position: tuple[int, int]
    actual_distance: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PortalTransferFact:
    kind: Literal["portal_transfer"] = "portal_transfer"
    target_entity_uuid: UUID
    portal_uuid: UUID | None
    start_position: tuple[int, int] | None
    end_position: tuple[int, int] | None
    committed: bool
    portal_content_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ShoveFact:
    kind: Literal["shove"] = "shove"
    source_entity_uuid: UUID
    target_entity_uuid: UUID
    behavior_id: str | None
    contest_success: bool | None
    push_distance: int
    knocked_prone: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class DamageFact:
    kind: Literal["damage"] = "damage"
    stage: Literal["taken", "applied"]
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    applied_damage: int | None = None
    resulting_normal_hp: int | None = None
    resulting_temporary_hp: int | None = None
    damage_type: DamageType | None = None
    body_release: BodyReleaseResult | None = None
    intercepted_by_condition_uuid: UUID | None = None
    effect_id: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SavingThrowFact:
    """The disclosed outcome of one native save, without private roll modifiers."""

    kind: Literal["saving_throw"] = "saving_throw"
    target_entity_uuid: UUID
    ability_name: AbilityName
    succeeded: bool
    effect_id: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class HealFact:
    kind: Literal["heal"] = "heal"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    actual_healing: int
    was_blocked: bool
    resulting_normal_hp: int | None
    resulting_temporary_hp: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TemporaryHitPointsFact:
    kind: Literal["temporary_hit_points"] = "temporary_hit_points"
    entity_uuid: UUID
    resulting_temporary_hp: int
    grant: TemporaryHitPointsGrant | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class LifeFact:
    kind: Literal["life"] = "life"
    entity_uuid: UUID
    previous_state: LifeState
    new_state: LifeState
    reason: LifeStateChangeReason
    normal_hit_points: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DeathSaveFact:
    kind: Literal["death_save"] = "death_save"
    entity_uuid: UUID
    natural_roll: int | None
    succeeded: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class EquipmentFact:
    kind: Literal["equipment"] = "equipment"
    source_entity_uuid: UUID
    visual_loadout: VisualLoadout
    armor_class: int
    controlled_items: tuple[ItemPresentationState, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionChangeFact:
    kind: Literal["condition"] = "condition"
    target_entity_uuid: UUID
    event_type: EventType
    condition: ConditionFact


@dataclass(frozen=True, slots=True, kw_only=True)
class SpatialFact:
    kind: Literal["spatial"] = "spatial"
    change_type: SpatialChangeType
    entity_uuid: UUID | None
    position: tuple[int, int]
    previous_occupancy_layer: OccupancyLayer | None = None
    occupancy_layer: OccupancyLayer | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnFact:
    kind: Literal["turn"] = "turn"
    event_type: EventType
    entity_uuid: UUID | None
    round_number: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemChargeFact:
    kind: Literal["item_charge"] = "item_charge"
    source_entity_uuid: UUID
    item_uuid: UUID
    charges_after: int
    stack_count_after: int
    item_destroyed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionReaction:
    """Disclosed reaction result and its native triggering lineage."""

    triggered_lineage_uuid: UUID
    succeeded: bool
    automatic: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionFact:
    kind: Literal["action"] = "action"
    source_entity_uuid: UUID
    target_entity_uuid: UUID | None
    behavior_id: str | None
    name: str | None
    source_item_uuid: UUID | None = None
    reaction: ActionReaction | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SensoryFact:
    kind: Literal["sensory"] = "sensory"
    observer_uuid: UUID
    initial: bool
    observer_position: tuple[int, int]
    observer_position_changed: bool
    effective_light_levels_changed: dict[str, int]
    cause_event_uuid: UUID | None
    visible_cells_added: tuple[tuple[int, int], ...]
    visible_cells_removed: tuple[tuple[int, int], ...]
    seen_cells_added: tuple[tuple[int, int], ...]
    entity_contacts_changed: dict[UUID, PerceivedContact]
    entity_contacts_removed: frozenset[UUID]
    object_contacts_changed: dict[UUID, PerceivedContact]
    object_contacts_removed: frozenset[UUID]
    sense_modes_changed: bool
    sense_modes: tuple[SenseMode, ...] | None
    passive_perception_changed: bool
    passive_perception: int | None
    visual_access_changed: bool
    visual_access: int | None
    paths_dirty: bool
    hazardous_cells_changed: dict[str, bool] = field(default_factory=dict)
    spatial_effects_changed: dict[UUID, PerceivedSpatialEffect] = field(default_factory=dict)
    spatial_effects_removed: frozenset[UUID] = frozenset()


@dataclass(frozen=True, slots=True, kw_only=True)
class SpatialEffectStateFact:
    """A witnessed mechanical transition, restricted to disclosed fixture cells."""

    kind: Literal["spatial_effect_state"] = "spatial_effect_state"
    spatial_effect_uuid: UUID
    positions: tuple[tuple[int, int], ...]
    previous_state: TrapState | None
    state: TrapState | None
    previous_pressed: bool | None = None
    pressed: bool | None = None
    operation: SpatialEffectChangeOperation = SpatialEffectChangeOperation.STATE_CHANGED


@dataclass(frozen=True, slots=True, kw_only=True)
class MechanismActivationFact:
    """A witnessed discharge with independently disclosed origin and footprint."""

    kind: Literal["mechanism_activation"] = "mechanism_activation"
    mechanism_uuid: UUID | None
    mechanism_content_id: str
    target_entity_uuid: UUID | None
    origin_position: tuple[int, int] | None
    direction: tuple[int, int]
    affected_positions: tuple[tuple[int, int], ...]
    end_position: tuple[int, int] | None
    committed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectDamageFact:
    """The completed damage result for an observed item, not an actor."""

    kind: Literal["object_damage"] = "object_damage"
    object_uuid: UUID
    applied_damage: int
    resulting_hp: int
    damage_type: DamageType | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectDestroyedFact:
    """A witnessed break; replacement identity is retained only for old recordings."""

    kind: Literal["object_destroyed"] = "object_destroyed"
    object_uuid: UUID
    replacement_uuid: UUID | None = None
    placement: WorldObjectPlacement
    item_id: str
    remnant_state: ItemRemnantState | None = None
    destruction_outcome: str | None = None


PlayerFact = Annotated[
    AttackFact | SpellFact | MovementFact | StepFact | ForcedMovementFact | PortalTransferFact | ShoveFact
    | DamageFact | HealFact | TemporaryHitPointsFact | LifeFact | DeathSaveFact | EquipmentFact
    | ConditionChangeFact | SpatialFact | TurnFact | ActionFact | SensoryFact | ItemChargeFact | SpatialEffectStateFact
    | ObjectDamageFact | ObjectDestroyedFact | MechanismActivationFact | SavingThrowFact,
    Field(discriminator="kind"),
    BeforeValidator(upgrade_player_fact),
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentAttribution:
    role: Literal["behavior", "source_item", "effective_handler"]
    behavior_id: str
    provided_by_id: str | None = None
    origin_root_id: str | None = None
    source_entity_uuid: UUID | None = None
    triggering_event_uuid: UUID | None = None
    triggering_lineage_uuid: UUID | None = None
    emitted_lineage_uuids: tuple[UUID, ...] = ()
    handler_name: str | None = None
    dispatch_index: int | None = None
    outcome: HandlerDispatchOutcome | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionCancellation:
    phase: EventPhase | None
    action_economy_spent: bool
    outcome_code: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerNode:
    uuid: UUID
    lineage_uuid: UUID
    parent_event: UUID | None
    parent_lineage: UUID | None
    children_lineages: tuple[UUID, ...]
    phase: EventPhase
    canceled: bool
    fact: PlayerFact | None
    cancellation: ActionCancellation | None = None
    combat_log: CombatLogEntry | None = None
    content_attributions: tuple[ContentAttribution, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class VersionRow:
    source_index: int
    event_uuid: UUID
    lineage_uuid: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class FloorItem:
    item_uuid: UUID
    item_id: str
    name: str
    visual_item_name: str
    visual_variant_id: str | None
    map_char: str
    boundary_structure: BoundaryStructure | None
    is_open: bool | None
    is_lit: bool | None
    blocks_propagation: bool = False
    is_engaged: bool | None = None
    surface_residues: tuple[ObjectResidueState, ...] = ()
    current_hit_points: int | None = None
    maximum_hit_points: int | None = None
    concentration_capacity: int = 0
    concentration_slots: tuple[ItemConcentrationSlot, ...] = ()
    door_mechanism: DoorMechanism | None = None
    door_swing: DoorSwing | None = None
    remnant_state: ItemRemnantState | None = None
    integrity: ItemIntegrity = ItemIntegrity.INTACT
    destruction_outcome: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerObject:
    placement: WorldObjectPlacement
    item: FloorItem


@dataclass(frozen=True, slots=True, kw_only=True)
class WorldUpdate:
    event_uuid: UUID
    tiles: tuple[WorldTileState, ...]
    objects: tuple[PlayerObject, ...]
    objects_removed: tuple[UUID, ...]
    connectors: tuple[WorldConnectorState, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerWorld:
    battlefield_id: str
    battlefield_name: str
    bounds: tuple[int, int, int, int]
    width: int
    height: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerLineage:
    generation: UUID
    observer_uuid: UUID
    root: PlayerNode
    events: tuple[PlayerNode, ...]
    version_rows: tuple[VersionRow, ...]
    start_cursor: int
    end_cursor: int
    observations: tuple[PlayerObservation, ...] = ()
    world_updates: tuple[WorldUpdate, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerInitialization:
    generation: UUID
    observer_uuid: UUID
    world: PlayerWorld
    nodes: tuple[PlayerNode, ...]
    version_rows: tuple[VersionRow, ...]
    end_cursor: int
    observations: tuple[PlayerObservation, ...]
    world_updates: tuple[WorldUpdate, ...]


class PlayerSequence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    initialization: PlayerInitialization
    lineages: tuple[PlayerLineage, ...]


@dataclass(slots=True, kw_only=True)
class PlayerState:
    generation: UUID
    observer_uuid: UUID
    world: PlayerWorld
    tiles: dict[tuple[int, int], WorldTileState] = field(default_factory=dict)
    objects: dict[UUID, PlayerObject] = field(default_factory=dict)
    connectors: tuple[WorldConnectorState, ...] = ()
    senses: SensesSnapshot | None = None
    reducer_cursor: int = 0
    # Local reduction bookkeeping, reconstructed from saved version rows.
    # Keep spatial commit order across separately timed presentation groups.
    spatial_commit_cursors: dict[UUID, int] = field(default_factory=dict)
    actors: dict[UUID, PlayerActor] = field(default_factory=dict)
    current_actor_uuid: UUID | None = None
    round_number: int = 0
