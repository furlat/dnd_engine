"""Passive player values: causal structure, permitted facts, and observed world.

Native event recordings remain private. These records deliberately have no
engine constructors, executable state, audience grant maps, or diagnostic rows.
"""

from dataclasses import dataclass, field
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.sensory import SensesSnapshot
from dnd.core.action_execution import MovementProvocationPolicy
from dnd.core.combat_log import CombatLogEntry
from dnd.core.content.runtime import HandlerDispatchOutcome
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import EventPhase, EventType, MovementTrajectory, SpatialChangeType, WorldConnectorState, WorldTileState
from dnd.core.item_types import EquippedVisualPolicy, ItemPresentationKind, ItemPresentationState
from dnd.core.life_types import LifeState, LifeStateChangeReason
from dnd.types.senses import PerceivedContact, SenseMode
from dnd.types.world_placement import BoundaryStructure, WorldObjectPlacement
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


@dataclass(frozen=True, slots=True, kw_only=True)
class ForcedMovementFact:
    kind: Literal["forced_movement"] = "forced_movement"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    start_position: tuple[int, int]
    end_position: tuple[int, int]
    actual_distance: int


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


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnFact:
    kind: Literal["turn"] = "turn"
    event_type: EventType
    entity_uuid: UUID | None
    round_number: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionFact:
    kind: Literal["action"] = "action"
    source_entity_uuid: UUID
    target_entity_uuid: UUID | None
    behavior_id: str | None
    name: str | None


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


PlayerFact = Annotated[
    AttackFact | SpellFact | MovementFact | StepFact | ForcedMovementFact | ShoveFact
    | DamageFact | HealFact | LifeFact | DeathSaveFact | EquipmentFact
    | ConditionChangeFact | SpatialFact | TurnFact | ActionFact | SensoryFact,
    Field(discriminator="kind"),
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
class PlayerNode:
    uuid: UUID
    lineage_uuid: UUID
    parent_event: UUID | None
    parent_lineage: UUID | None
    children_lineages: tuple[UUID, ...]
    phase: EventPhase
    canceled: bool
    fact: PlayerFact | None
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
    actors: dict[UUID, PlayerActor] = field(default_factory=dict)
    current_actor_uuid: UUID | None = None
    round_number: int = 0
