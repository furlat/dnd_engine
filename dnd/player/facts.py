"""Passive player values: causal structure, permitted facts, and observed world.

Native event recordings remain private. These records deliberately have no
engine constructors, executable state, audience grant maps, or diagnostic rows.
"""

from dnd.core.content.descriptors import ContentDescriptor

from dataclasses import dataclass, field
from typing import Annotated, Generic, Literal, TypedDict, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.dataclasses import dataclass as packed_dataclass
from pydantic.config import JsonDict
from dnd.player.compatibility import upgrade_spell_fact
from dnd.player.audience import AudiencePerception, PlayerAudience, resolve_audience

from dnd.types.appearance import AppearanceConfig
from dnd.types.world import MovementProvocationPolicy
from dnd.core.action_types import AvailableHandlerInfo
from dnd.core.combat_log import CombatLogData, CombatLogEntryType
from dnd.core.content.identities import ContentRef, HandlerDispatchOutcome
from dnd.core.creature_types import DamageType, Size
from dnd.core.creature_types import AttackOutcome
from dnd.core.effect_types import ObjectSectionVolume, EffectPropagationLink
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.types.event_facts import EventPhase, EventType, LandingKind, MovementTrajectory, SpatialChangeType, WorldConnectorState, WorldTileState, WorldTileChanges
from dnd.core.item_types import (DoorMechanism, DoorSwing, EquippedVisualPolicy, ItemConcentrationSlot, ItemResourceChange, ItemEffectPresentationState,
    ItemIntegrity, ItemPresentationKind, ItemRarity, ItemRemnantState)
from dnd.core.life_types import LifeState, LifeStateChangeReason, RemainsDisposition
from dnd.core.presentation_geometry import AoEPresentationGeometry, WallAssemblyPresentationGeometry
from dnd.types.residues import BodyReleaseResult, ObjectResidueState, ResidueContribution
from dnd.types.materials import TileSurface
from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES, NO_ROWS, PACKED, CellMask, CellMaskField, CellValues, CellValuesField, RowBits, RowBitsField
from dnd.types.senses import PerceivedContact, SenseMode, SensesSnapshot, SensesType, VolumeSurfaceSight
from dnd.core.condition_types import ConditionDurationSummary
from dnd.types.class_features import DraconicPresenceMode
from dnd.types.material_deposits import MaterialDepositSource
from dnd.types.spatial_effects import AreaPropagation, SpatialDamageSource, SpatialEffectChangeOperation, SpatialEffectInteractionOperation
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.traps import TrapState
from dnd.types.physical_access import ContactPassage
from dnd.types.world import CardinalDirection, MovementMode, OccupancyLayer
from dnd.types.world_placement import BoundaryStructure, WorldObjectPlacement, WorldObjectSupport
from dnd.types.character_progression import PreparedSpellSelection
from dnd.types.abilities import AbilityName
from dnd.types.actor import TemporaryHitPointsGrant, SpatialDisposition
from dnd.types.actor_sheet import PlayerResource, PlayerResourceValue
from dnd.types.class_features import FontConversion, IndomitableReroll, RelentlessRageIntervention
from dnd.types.actor_facts import ConditionFact
from dnd.types.summoning import SummonManifestation, SummonDepartureCause
from dnd.types.character_progression import Species, SpeciesVariant, Background, AppliedOriginState, AppliedClassLevel


# A field holding its default (no rows, false, none) is left out of a dump and
# decodes to that default, as the packed cell fields do.
def _no_rows(rows: tuple | dict) -> bool:
    return not rows


def _unflagged(flag: bool) -> bool:
    return not flag


def _unset(value: object) -> bool:
    return value is None


def _zero(value: int) -> bool:
    return value == 0


def _neutral(appearance: str) -> bool:
    return appearance == "neutral"


RowIndex = Annotated[int, Field(ge=0)]
Revision = Annotated[int, Field(ge=0)]
# Indices into the group's `SensoryRows`.
RowIndices = Annotated[tuple[RowIndex, ...], Field(exclude_if=_no_rows)]
SensoryFlag = Annotated[bool, Field(exclude_if=_unflagged)]
SensoryNumber = Annotated[int | None, Field(exclude_if=_unset)]
Row = TypeVar("Row")
# A row list holding no rows is left out of a dump.
Rows = Annotated[tuple[Row, ...], Field(exclude_if=_no_rows)]


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerCharacterSheet:
    """Evaluated controlled-character data, without executable owners.

    The character's name, portrait and HP are its body's (`PlayerState.actors`), not restated here.
    """

    actor_uuid: UUID
    species: Species | None
    species_variant: SpeciesVariant | None
    background: Background | None
    origin: AppliedOriginState | None
    class_levels: tuple[AppliedClassLevel, ...]
    abilities: tuple[tuple[AbilityName, int], ...]
    skills: tuple[str, ...]
    expertise: tuple[str, ...]
    saves: tuple[str, ...]
    proficiency_bonus: int
    resources: tuple[PlayerResource, ...]
    compatible_item_slots: tuple[tuple[UUID, tuple[str, ...]], ...] = ()
    handler_details: tuple[AvailableHandlerInfo, ...] = ()
    scribed_spell_ids: tuple[str, ...] = ()
    permanent_feature_uses: tuple[str, ...] = ()
    prepared_spell_selections: tuple[PreparedSpellSelection, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerHUDSnapshot:
    """The client's folded display: its controlled sheets and the initiative it last received.

    The initiative it shows is that order's perceived part (`reduction.displayed_initiative`).
    """

    initiative: tuple[UUID, ...]
    sheets: tuple[PlayerCharacterSheet, ...]


class SheetChanges(TypedDict, total=False):
    """Present fields replace the seat's sheet values; against no sheet every field is present.

    `resources` is whole when its key sequence changed; otherwise its changed rows travel as the patch's
    `resource_values`.
    """

    __pydantic_config__ = ConfigDict(extra="forbid")

    species: Species | None
    species_variant: SpeciesVariant | None
    background: Background | None
    origin: AppliedOriginState | None
    class_levels: tuple[AppliedClassLevel, ...]
    abilities: tuple[tuple[AbilityName, int], ...]
    skills: tuple[str, ...]
    expertise: tuple[str, ...]
    saves: tuple[str, ...]
    proficiency_bonus: int
    resources: tuple[PlayerResource, ...]
    compatible_item_slots: tuple[tuple[UUID, tuple[str, ...]], ...]
    handler_details: tuple[AvailableHandlerInfo, ...]
    scribed_spell_ids: tuple[str, ...]
    permanent_feature_uses: tuple[str, ...]
    prepared_spell_selections: tuple[PreparedSpellSelection, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SheetPatch:
    """One sheet's change: its replaced fields and, by key, the new values of resource rows it holds."""

    actor_uuid: UUID
    changes: SheetChanges
    resource_values: Annotated[tuple[PlayerResourceValue, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerHUDPatch:
    """The projection of a group's sheet and initiative facts for the seat's controlled actors.

    `sheets`: one patch per changed sheet; a sheet the seat does not hold arrives whole, in the
    publication order. `initiative`: the order's part the seat perceives at the end of the group,
    sent at initialization, when an order change shows under its current perception, or when
    anything entered its perception; leaving perception sends nothing.
    """

    initiative: Annotated[tuple[UUID, ...] | None, Field(exclude_if=_unset)] = None
    sheets: Annotated[tuple[SheetPatch, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerLogEntry:
    """One disclosed combat-log entry, rendered for its seat, without nested copies.

    An entry's children are composed from its node's lineage: in
    `children_lineages` order, each child lineage's own entry, or, for a child
    without one, that child's children (the native collection rule). A
    multi-entity entry's `target_entry_indices` index those children.
    """

    entry_type: CombatLogEntryType
    source_name: str
    source_uuid: str
    target_name: str | None
    target_uuid: str | None
    compact: str
    verbose: str
    detailed: str
    data: CombatLogData
    success: bool | None


@dataclass(frozen=True, slots=True, kw_only=True)
class CombatLogAppend:
    generation: UUID
    observer_uuid: UUID
    encounter_log_index: int
    operation_end_cursor: int
    entry: PlayerLogEntry


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemLook:
    """What any viewer of an equipped item sees of it; `is_lit` travels in its layer."""

    item_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")]
    item_kind: ItemPresentationKind
    visual_item_name: str
    visual_variant_id: str | None
    equipped_visual_policy: EquippedVisualPolicy
    item_effects: tuple[ItemEffectPresentationState, ...]
    very_bright_radius_feet: Annotated[int, Field(ge=0)] | None
    bright_radius_feet: Annotated[int, Field(ge=0)] | None
    dim_radius_feet: Annotated[int, Field(ge=0)] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemProfile:
    """What a controlled item is: the fields its use does not change."""

    name: str
    description: str | None
    rarity: ItemRarity
    weight: float
    value: int
    tags: tuple[str, ...]
    is_pickable: bool
    is_equippable: bool
    is_usable: bool
    is_targetable: bool
    door_mechanism: DoorMechanism | None
    door_swing: DoorSwing | None
    stack_id: str | None
    damage_dice: str | None
    damage_type: str | None
    weapon_properties: tuple[str, ...]
    armor_type: str | None
    armor_ac: int | None
    shield_ac_bonus: int | None
    max_charges: Annotated[int, Field(ge=-1)] | None
    max_stack: Annotated[int, Field(ge=1)]
    is_consumable: bool
    map_char: str
    include_in_senses_objects: bool
    include_in_adjacent_senses_objects: bool
    include_in_available_object_actions: bool
    maximum_hit_points: Annotated[int, Field(ge=0)] | None
    concentration_capacity: Annotated[int, Field(ge=0)]
    boundary_structure: BoundaryStructure | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemState:
    """What a controlled item's use and the world change."""

    stack_count: Annotated[int, Field(ge=0)]
    charges: Annotated[int, Field(ge=-1)] | None
    integrity: ItemIntegrity
    destruction_outcome: str | None
    remnant_state: ItemRemnantState | None
    current_hit_points: Annotated[int, Field(ge=0)] | None
    concentration_slots: tuple[ItemConcentrationSlot, ...]
    construction_owner_uuid: UUID | None
    construction_geometry: AoEPresentationGeometry | None
    construction_suppressions: tuple[SpellSuppression, ...]
    known_to_creator: bool
    supported_by_uuid: UUID | None
    contact_passage: ContactPassage
    surface_residues: tuple[ObjectResidueState, ...]
    linked_spatial_condition_uuid: UUID | None
    is_open: bool | None
    is_engaged: bool | None
    blocks_movement: bool
    blocks_optics: bool
    blocks_propagation: bool
    is_lit: bool | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerItem:
    """What a seat knows of one item instance: its look and, once it controlled the item, its profile and state.

    The profile and state are current while the item is in a controlled inventory.
    """

    look: ItemLook
    profile: ItemProfile | None = None
    state: ItemState | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemPatch:
    """One item's components new to the seat: all it may know the first time, then the components that changed."""

    item_uuid: UUID
    look: ItemLook | None = None
    profile: ItemProfile | None = None
    state: ItemState | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class VisualItem:
    """One equipped layer; the item's look is in the seat's record of `item_uuid`."""

    slot: str
    item_uuid: UUID
    item_id: str
    is_lit: bool | None = None


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
    # A controlled actor's inventory, in order; its records are in `PlayerState.items`.
    controlled_items: tuple[UUID, ...] | None = None
    occupancy_layer: OccupancyLayer | None = None
    temporary_hp_grant: TemporaryHitPointsGrant | None = None
    resolved_size: Size | None = None
    structural_base_size: Size | None = None
    manifestation: SummonManifestation | None = None
    faction: str | None = None
    present: bool = True
    remains_disposition: RemainsDisposition = RemainsDisposition.INTACT
    spatial_disposition: SpatialDisposition = SpatialDisposition.PRESENT


class ActorChanges(TypedDict, total=False):
    """Present fields replace the seat's known body values; omitted fields are unchanged.

    Against an absent body (first acquisition) every field is present.
    """

    __pydantic_config__ = ConfigDict(extra="forbid")

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
    conditions: tuple[ConditionFact, ...]
    last_visual_position: tuple[int, int] | None
    controlled_items: tuple[UUID, ...] | None
    occupancy_layer: OccupancyLayer | None
    temporary_hp_grant: TemporaryHitPointsGrant | None
    resolved_size: Size | None
    structural_base_size: Size | None
    manifestation: SummonManifestation | None
    faction: str | None
    present: bool
    remains_disposition: RemainsDisposition
    spatial_disposition: SpatialDisposition


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerObservation:
    """One actor's observed body at an event, as a patch against what the seat holds,
    with the patches of the items that body discloses."""

    occurrence: int
    actor_uuid: UUID
    changes: Annotated[ActorChanges, Field(exclude_if=_no_rows)] = field(default_factory=ActorChanges)
    contact: Annotated[PerceivedContact | None, Field(exclude_if=_unset)] = None
    items: Annotated[tuple[ItemPatch, ...], Field(exclude_if=_no_rows)] = ()


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
    source_item_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    item_effects: Annotated[tuple[ItemEffectPresentationState, ...], Field(exclude_if=_no_rows)] = ()
    intercepted_by_condition_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    projectile_deflection_position: Annotated[tuple[float, float] | None, Field(exclude_if=_unset)] = None
    target_kind: Literal["creature", "object"] = "creature"
    target_position: Annotated[tuple[int, int] | None, Field(exclude_if=_unset)] = None
    target_base_height_steps: Annotated[int | None, Field(exclude_if=_unset)] = None
    attack_source_kind: Literal["equipped", "unarmed", "natural"] = "equipped"

    @property
    def weapon_set(self) -> WeaponSet:
        """The declared source selects gear independently of its authored VFX."""
        if self.attack_source_kind != "equipped":
            return WeaponSet.NONE
        return WeaponSet.RANGED if self.weapon_slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF) else WeaponSet.MELEE


@dataclass(frozen=True, slots=True, kw_only=True)
class SpellApplication:
    """A spell application's membership: its owning lineage (the seat's lineage index), identity and order."""

    lineage: int
    application_id: UUID
    index: Annotated[int, Field(ge=0)]


@dataclass(frozen=True, slots=True, kw_only=True)
class SpellFact:
    kind: Literal["spell"] = "spell"
    source_entity_uuid: UUID
    target_entity_uuid: UUID | None
    behavior_id: str | None
    name: str | None
    source_position: tuple[int, int] | None
    declared_target_entity_uuids: tuple[UUID, ...]
    application: SpellApplication | None
    propagation: Annotated[EffectPropagationLink | None, Field(exclude_if=_unset)] = None
    attack_outcome: Annotated[AttackOutcome | None, Field(exclude_if=_unset)] = None
    cast_origin: Literal["actor", "source_item"] = "actor"
    source_item_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    effect_id: Annotated[str | None, Field(exclude_if=_unset)] = None
    aoe_position: Annotated[tuple[int, int] | None, Field(exclude_if=_unset)] = None
    area_geometry: Annotated[AoEPresentationGeometry | None, Field(exclude_if=_unset)] = None
    # A disclosed subset of the native result, never a physical blast mask.
    # None means no recorded result; () is a resolved result with no granted cells.
    resolved_area_positions: Annotated[tuple[tuple[int, int], ...] | None, Field(exclude_if=_unset)] = None
    suppressions: Annotated[tuple[SpellSuppression, ...], Field(exclude_if=_no_rows)] = ()
    area_propagation: AreaPropagation = "line_of_effect"
    target_kind: Literal["creature", "object"] = "creature"
    target_position: Annotated[tuple[int, int] | None, Field(exclude_if=_unset)] = None
    target_base_height_steps: Annotated[int | None, Field(exclude_if=_unset)] = None

    @property
    def application_id(self) -> UUID | None:
        return self.application.application_id if self.application is not None else None

    @property
    def application_index(self) -> int | None:
        return self.application.index if self.application is not None else None

    @model_validator(mode="before")
    @classmethod
    def restore_recorded_area_policy(cls, value: object) -> object:
        return upgrade_spell_fact(value)


@dataclass(frozen=True, slots=True, kw_only=True)
class AreaReachFact:
    """One disclosed propagation stage, ordered by actual structural breaks."""

    kind: Literal["area_reach"] = "area_reach"
    stage_index: int
    newly_reached_positions: tuple[tuple[int, int], ...]
    previous_reach_lineage: int | None
    prerequisite_destruction_lineages: tuple[int, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MovementFact:
    kind: Literal["movement"] = "movement"
    source_entity_uuid: UUID
    trajectory: MovementTrajectory
    # Root geometry is present only for a fully permitted atomic trajectory.
    start_position: Annotated[tuple[int, int] | None, Field(exclude_if=_unset)] = None
    end_position: Annotated[tuple[int, int] | None, Field(exclude_if=_unset)] = None
    requested_end_position: Annotated[tuple[int, int] | None, Field(exclude_if=_unset)] = None
    path: Annotated[tuple[tuple[int, int], ...], Field(exclude_if=_no_rows)] = ()
    start_elevation_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    end_elevation_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    movement_mode: Annotated[MovementMode | None, Field(exclude_if=_unset)] = None
    start_layer: Annotated[OccupancyLayer | None, Field(exclude_if=_unset)] = None
    end_layer: Annotated[OccupancyLayer | None, Field(exclude_if=_unset)] = None
    connector_presentation_key: Annotated[str | None, Field(exclude_if=_unset)] = None


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
    resolved_speed_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    movement_mode: Annotated[MovementMode | None, Field(exclude_if=_unset)] = None
    from_layer: Annotated[OccupancyLayer | None, Field(exclude_if=_unset)] = None
    to_layer: Annotated[OccupancyLayer | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ForcedMovementFact:
    kind: Literal["forced_movement"] = "forced_movement"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    start_position: tuple[int, int]
    end_position: tuple[int, int]
    actual_distance: int
    disclosed_path: Annotated[tuple[tuple[int, int], ...], Field(exclude_if=_no_rows)] = ()
    start_elevation_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    end_elevation_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    drop_feet: int = 0
    landing_kind: LandingKind = LandingKind.GROUND


@dataclass(frozen=True, slots=True, kw_only=True)
class PortalTransferFact:
    kind: Literal["portal_transfer"] = "portal_transfer"
    target_entity_uuid: UUID
    portal_uuid: UUID | None
    start_position: tuple[int, int] | None
    end_position: tuple[int, int] | None
    committed: bool
    portal_content_id: Annotated[str | None, Field(exclude_if=_unset)] = None


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
class DamageRequestFact:
    kind: Literal["damage"] = "damage"
    stage: Literal["taken"] = "taken"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    intercepted_by_condition_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    source_condition_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    relentless_rage: Annotated[RelentlessRageIntervention | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DamageResultFact:
    kind: Literal["damage"] = "damage"
    stage: Literal["applied"] = "applied"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    applied_damage: int
    resulting_normal_hp: int
    resulting_temporary_hp: int
    damage_type: DamageType
    body_release: Annotated[BodyReleaseResult | None, Field(exclude_if=_unset)] = None
    effect_id: Annotated[str | None, Field(exclude_if=_unset)] = None
    spatial_source: Annotated[SpatialDamageSource | None, Field(exclude_if=_unset)] = None
    source_condition_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None


DamageFact = DamageRequestFact | DamageResultFact


@dataclass(frozen=True, slots=True, kw_only=True)
class SavingThrowFact:
    """The disclosed outcome of one native save, without private roll modifiers."""

    kind: Literal["saving_throw"] = "saving_throw"
    target_entity_uuid: UUID
    ability_name: AbilityName
    succeeded: bool
    effect_id: str | None
    indomitable_reroll: Annotated[IndomitableReroll | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class HealFact:
    kind: Literal["heal"] = "heal"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    actual_healing: int
    was_blocked: bool
    resulting_normal_hp: int | None
    resulting_temporary_hp: int | None
    source_condition_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TemporaryHitPointsFact:
    kind: Literal["temporary_hit_points"] = "temporary_hit_points"
    entity_uuid: UUID
    resulting_temporary_hp: int
    grant: Annotated[TemporaryHitPointsGrant | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class LifeFact:
    kind: Literal["life"] = "life"
    entity_uuid: UUID
    previous_state: LifeState
    new_state: LifeState
    reason: LifeStateChangeReason
    normal_hit_points: int
    remains_disposition: RemainsDisposition = RemainsDisposition.INTACT
    preserved_equipped_item_uuids: Annotated[tuple[UUID, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class DeathSaveFact:
    kind: Literal["death_save"] = "death_save"
    entity_uuid: UUID
    natural_roll: int | None
    succeeded: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class EquipmentFact:
    """A holder's equipment change: its body patch (loadout, armor class, inventory) and its items' patches."""

    kind: Literal["equipment"] = "equipment"
    source_entity_uuid: UUID
    changes: ActorChanges
    items: Annotated[tuple[ItemPatch, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionChangeFact:
    kind: Literal["condition"] = "condition"
    target_entity_uuid: UUID
    event_type: EventType
    condition: ConditionFact
    consumed: Annotated[bool, Field(exclude_if=_unflagged)] = False


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemEffectChangeFact:
    """Witnessed native item membership edge, without a creature condition."""

    kind: Literal["item_effect"] = "item_effect"
    item_uuid: UUID
    effect_uuid: UUID
    event_type: EventType


@dataclass(frozen=True, slots=True, kw_only=True)
class CreationWitness:
    """Observed first placement tied to its exact recorded native birth."""
    birth_occurrence: int
    manifestation: SummonManifestation


@dataclass(frozen=True, slots=True, kw_only=True)
class SpatialFact:
    kind: Literal["spatial"] = "spatial"
    change_type: SpatialChangeType
    entity_uuid: UUID | None
    position: tuple[int, int]
    object_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    commit_occurrence: Annotated[int | None, Field(exclude_if=_unset)] = None
    previous_occupancy_layer: Annotated[OccupancyLayer | None, Field(exclude_if=_unset)] = None
    occupancy_layer: Annotated[OccupancyLayer | None, Field(exclude_if=_unset)] = None
    terminal_departure: Annotated[bool, Field(exclude_if=_unflagged)] = False
    terminal_cause: Annotated[SummonDepartureCause | None, Field(exclude_if=_unset)] = None
    creation: Annotated[CreationWitness | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FactionFact:
    kind: Literal["faction"] = "faction"
    entity_uuid: UUID
    faction_after: str | None
    control_lost: Annotated[bool, Field(exclude_if=_unflagged)] = False


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
    # Older public packets retain after-values but did not disclose this label.
    resource_change: Annotated[ItemResourceChange | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionReaction:
    """Disclosed reaction result and its native triggering lineage."""

    triggered_lineage: int | None
    succeeded: bool
    automatic: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionFact:
    kind: Literal["action"] = "action"
    source_entity_uuid: UUID
    target_entity_uuid: UUID | None
    behavior_id: str | None
    name: str | None
    source_item_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    reaction: Annotated[ActionReaction | None, Field(exclude_if=_unset)] = None
    font_conversion: Annotated[FontConversion | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SpatialEffectContent:
    """A spatial effect's static content; a seat receives it once per effect."""

    content_ref: ContentRef
    name: str
    description: str


class SpatialEffectSighting(BaseModel):
    """One observation of a spatial effect without its static content (`PerceivedSpatialEffect`'s other fields).

    Its cell lists are sets of cells (`positions`, `visible_volume_positions`):
    a perceived effect's lists are sorted and hold each cell once, which is
    the order the client unpacks them in. A field holding its default is left out.
    """

    model_config = ConfigDict(frozen=True)
    duration: ConditionDurationSummary | None = Field(default=None, exclude_if=_unset)
    positions: CellMask
    owner_revision: int | None = Field(default=None, ge=0, exclude_if=_unset)
    apparent_presence: bool = Field(default=False, exclude_if=_unflagged)
    trap_state: TrapState | None = Field(default=None, exclude_if=_unset)
    pressed: bool | None = Field(default=None, exclude_if=_unset)
    direction: tuple[int, int] | None = Field(default=None, exclude_if=_unset)
    anchor_item_uuid: UUID | None = Field(default=None, exclude_if=_unset)
    anchor_entity_uuid: UUID | None = Field(default=None, exclude_if=_unset)
    energy_type: DamageType | None = Field(default=None, exclude_if=_unset)
    presence_mode: DraconicPresenceMode | None = Field(default=None, exclude_if=_unset)
    sustainer_item_uuid: UUID | None = Field(default=None, exclude_if=_unset)
    concentration_slot_uuid: UUID | None = Field(default=None, exclude_if=_unset)
    anchor_position: tuple[int, int] | None = Field(default=None, exclude_if=_unset)
    anchor_elevation_steps: int | None = Field(default=None, exclude_if=_unset)
    area_geometry: AoEPresentationGeometry | None = Field(default=None, exclude_if=_unset)
    construction_sections: tuple[WallAssemblyPresentationGeometry, ...] = Field(default=(), exclude_if=_no_rows)
    area_propagation: AreaPropagation | None = Field(default=None, exclude_if=_unset)
    deposit_source: MaterialDepositSource | None = Field(default=None, exclude_if=_unset)
    visible_volume_positions: CellMaskField = EMPTY_CELLS
    upper_volume_surfaces: tuple[VolumeSurfaceSight, ...] = Field(default=(), exclude_if=_no_rows)
    suppressions: tuple[SpellSuppression, ...] = Field(default=(), exclude_if=_no_rows)


@dataclass(frozen=True, slots=True, kw_only=True)
class LightRow:
    """A perceived light source (`PerceivedLightSource`) as a row of its group: its identities name the group's `uuids`.

    `affected_tiles` is its footprint as a level per cell; a field holding its
    default is left out.
    """

    source: RowIndex
    revision: Revision
    position: tuple[int, int]
    base_height_steps: Annotated[int, Field(exclude_if=_zero)] = 0
    very_bright_radius_feet: int
    bright_radius_feet: int
    dim_radius_feet: int
    appearance: Annotated[Literal["torch", "neutral"], Field(exclude_if=_neutral)] = "neutral"
    actor_anchored: SensoryFlag = False
    anchor_entity: Annotated[RowIndex | None, Field(exclude_if=_unset)] = None
    anchor_item: Annotated[RowIndex | None, Field(exclude_if=_unset)] = None
    affected_tiles: CellValuesField = EMPTY_VALUES


@dataclass(frozen=True, slots=True, kw_only=True)
class SensoryRows:
    """The distinct perceived values a group's sensory facts name, each once, as columns.

    Every identity an observer, a removed list or a row names is in `uuids`
    once. Contact row i is the entity or object `uuids[contact_uuid_index[i]]`
    perceived at `contact_positions[i]`, visually if row i is in
    `contact_visual`, with special senses `contact_special_senses[i]` (no
    row has any when that column is empty); sighting row i is the effect
    `uuids[sighting_uuid_index[i]]` seen as `sightings[i]`; light removal row i
    is the source `uuids[light_removal_uuid_index[i]]` gone at revision
    `light_removal_revisions[i]`; light source row i is `light_sources[i]`.

    Three row tables hold the cells the facts' cell lists name, each once:
    `cells` the rows of the visible and seen lists (its cells in cell order);
    `light_levels` the rows of the light lists and `hazards` those of the
    hazard lists, each table the distinct (cell, value) pairs by cell in cell
    order, then by value. Layer k of a table holds, for each cell with more
    than k values in the group, its (k+1)-th smallest.
    """

    uuids: Annotated[tuple[UUID, ...], Field(exclude_if=_no_rows)] = ()
    contact_uuid_index: RowIndices = ()
    contact_positions: Annotated[tuple[tuple[int, int], ...], Field(exclude_if=_no_rows)] = ()
    contact_visual: RowBitsField = NO_ROWS
    contact_special_senses: Annotated[tuple[tuple[SensesType, ...], ...], Field(exclude_if=_no_rows)] = ()
    sighting_uuid_index: RowIndices = ()
    sightings: Annotated[tuple[SpatialEffectSighting, ...], Field(exclude_if=_no_rows)] = ()
    light_sources: Annotated[tuple[LightRow, ...], Field(exclude_if=_no_rows)] = ()
    light_removal_uuid_index: RowIndices = ()
    light_removal_revisions: Annotated[tuple[Revision, ...], Field(exclude_if=_no_rows)] = ()
    cells: CellMaskField = EMPTY_CELLS
    light_levels: Annotated[tuple[CellValues, ...], Field(exclude_if=_no_rows)] = ()
    hazards: Annotated[tuple[CellValues, ...], Field(exclude_if=_no_rows)] = ()

    def __post_init__(self) -> None:
        if (len(self.contact_uuid_index) != len(self.contact_positions)
                or self.contact_special_senses and len(self.contact_special_senses) != len(self.contact_positions)
                or len(self.sighting_uuid_index) != len(self.sightings)
                or len(self.light_removal_uuid_index) != len(self.light_removal_revisions)
                or any(index >= len(self.uuids) for index in
                       (*self.contact_uuid_index, *self.sighting_uuid_index, *self.light_removal_uuid_index,
                        *(index for row in self.light_sources for index in (row.source, row.anchor_entity, row.anchor_item)
                          if index is not None)))):
            raise ValueError("Sensory rows pair equal-length columns and name only their own uuids")


NO_SENSORY_ROWS = SensoryRows()


def _no_sensory_rows(rows: SensoryRows) -> bool:
    # Every sensory fact names its observer in `uuids`, so rows without uuids are empty.
    return not rows.uuids


# A group's rows: none is the default and is left out of a dump.
SensoryRowsField = Annotated[SensoryRows, Field(exclude_if=_no_sensory_rows)]


@dataclass(frozen=True, slots=True, kw_only=True)
class SensoryFact:
    """One observer's sensory after-values; its observer, changed and removed values are rows of its group's `SensoryRows`.

    `observer` indexes `uuids`; `entity_contacts_changed` /
    `object_contacts_changed` index contact rows, `spatial_effect_sightings`
    sighting rows, `light_sources_changed` light sources,
    `light_sources_removed` light removal rows; the three other removed lists
    index `uuids`. A list never names two rows of one identity. The cell lists
    are subsets of the group's row tables: the visible and seen lists of
    `cells`, `effective_light_levels_changed` of `light_levels`,
    `hazardous_cells_changed` of `hazards`; a value list names one row per
    cell. (While projection builds a group, `observer` names the fact's
    `SensoryTable` row and the other indices that table's rows; the cell lists
    are set when the group's row tables are.)
    """

    kind: Literal["sensory"] = "sensory"
    observer: RowIndex
    initial: SensoryFlag = False
    observer_position: tuple[int, int]
    observer_position_changed: SensoryFlag = False
    effective_light_levels_changed: RowBitsField = NO_ROWS
    cause_occurrence: SensoryNumber = None
    visible_cells_added: RowBitsField = NO_ROWS
    visible_cells_removed: RowBitsField = NO_ROWS
    seen_cells_added: RowBitsField = NO_ROWS
    entity_contacts_changed: RowIndices = ()
    entity_contacts_removed: RowIndices = ()
    object_contacts_changed: RowIndices = ()
    object_contacts_removed: RowIndices = ()
    sense_modes_changed: SensoryFlag = False
    sense_modes: Annotated[tuple[SenseMode, ...] | None, Field(exclude_if=_unset)] = None
    passive_perception_changed: SensoryFlag = False
    passive_perception: SensoryNumber = None
    visual_access_changed: SensoryFlag = False
    visual_access: SensoryNumber = None
    paths_dirty: SensoryFlag = False
    hazardous_cells_changed: RowBitsField = NO_ROWS
    spatial_effect_sightings: RowIndices = ()
    # The content of each sighted effect the seat does not hold yet.
    spatial_effect_content: Annotated[dict[UUID, SpatialEffectContent], Field(exclude_if=_no_rows)] = field(
        default_factory=dict)
    spatial_effects_removed: RowIndices = ()
    light_sources_changed: RowIndices = ()
    light_sources_removed: RowIndices = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SpatialEffectStateFact:
    """A witnessed mechanical transition, restricted to disclosed fixture cells."""

    kind: Literal["spatial_effect_state"] = "spatial_effect_state"
    spatial_effect_uuid: UUID
    positions: tuple[tuple[int, int], ...]
    previous_state: TrapState | None
    state: TrapState | None
    previous_pressed: Annotated[bool | None, Field(exclude_if=_unset)] = None
    pressed: Annotated[bool | None, Field(exclude_if=_unset)] = None
    operation: SpatialEffectChangeOperation = SpatialEffectChangeOperation.STATE_CHANGED
    interaction_operation: Annotated[SpatialEffectInteractionOperation | None, Field(exclude_if=_unset)] = None
    removed_positions: Annotated[tuple[tuple[int, int], ...], Field(exclude_if=_no_rows)] = ()


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
    replacement_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    placement: WorldObjectPlacement
    item_id: str
    remnant_state: Annotated[ItemRemnantState | None, Field(exclude_if=_unset)] = None
    destruction_outcome: Annotated[str | None, Field(exclude_if=_unset)] = None
    remains_disposition: RemainsDisposition = RemainsDisposition.INTACT
    previous_item: Annotated["FloorItem | None", Field(exclude_if=_unset)] = None
    affected_volume: Annotated[ObjectSectionVolume | None, Field(exclude_if=_unset)] = None
    resulting_placement: Annotated[WorldObjectPlacement | None, Field(exclude_if=_unset)] = None


PlayerFact = Annotated[
    AttackFact | SpellFact | AreaReachFact | MovementFact | StepFact | ForcedMovementFact | PortalTransferFact | ShoveFact
    | Annotated[DamageFact, Field(discriminator="stage")] | HealFact | TemporaryHitPointsFact | LifeFact | DeathSaveFact | EquipmentFact
    | ConditionChangeFact | ItemEffectChangeFact | SpatialFact | FactionFact | TurnFact | ActionFact | SensoryFact | ItemChargeFact | SpatialEffectStateFact
    | ObjectDamageFact | ObjectDestroyedFact | MechanismActivationFact | SavingThrowFact,
    Field(discriminator="kind"),
]


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentAttribution:
    role: Literal["behavior", "source_item", "effective_handler"]
    behavior_id: str
    provided_by_id: Annotated[str | None, Field(exclude_if=_unset)] = None
    origin_root_id: Annotated[str | None, Field(exclude_if=_unset)] = None
    source_entity_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    triggering_occurrence: Annotated[int | None, Field(exclude_if=_unset)] = None
    triggering_lineage: Annotated[int | None, Field(exclude_if=_unset)] = None
    emitted_lineages: Annotated[tuple[int, ...], Field(exclude_if=_no_rows)] = ()
    handler_name: Annotated[str | None, Field(exclude_if=_unset)] = None
    dispatch_index: Annotated[int | None, Field(exclude_if=_unset)] = None
    outcome: Annotated[HandlerDispatchOutcome | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionCancellation:
    phase: EventPhase | None
    action_economy_spent: bool
    outcome_code: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerNode:
    """One disclosed event version.

    Versions are identified by the seat's occurrence index (an entry of its
    group's `version_rows.occurrences`), lineages by the occurrence index of their first
    version the seat received.
    """

    occurrence: int
    lineage: int
    parent_event: Annotated[int | None, Field(exclude_if=_unset)] = None
    parent_lineage: Annotated[int | None, Field(exclude_if=_unset)] = None
    children_lineages: Annotated[tuple[int, ...], Field(exclude_if=_no_rows)] = ()
    phase: EventPhase
    canceled: Annotated[bool, Field(exclude_if=_unflagged)] = False
    fact: Annotated[PlayerFact | None, Field(exclude_if=_unset)] = None
    # The resolution the node belongs to: an index into its group's `resolutions`.
    resolution: Annotated[int | None, Field(exclude_if=_unset)] = None
    cancellation: Annotated[ActionCancellation | None, Field(exclude_if=_unset)] = None
    combat_log: Annotated[PlayerLogEntry | None, Field(exclude_if=_unset)] = None
    turn_execution_id: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    content_attributions: Annotated[tuple[ContentAttribution, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerResolution:
    """A resolution nodes belong to: the resolved lineage (the seat's lineage index) and, for one application of it, its identity."""

    lineage: int
    application_id: Annotated[UUID | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class VersionRows:
    """A group's versions as columns: version i is occurrence `occurrences[i]` of lineage `lineages[i]`."""

    occurrences: tuple[int, ...] = ()
    lineages: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if len(self.occurrences) != len(self.lineages):
            raise ValueError("Version columns pair equal-length columns")


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
    very_bright_radius_feet: Annotated[int, Field(ge=0)] | None = None
    bright_radius_feet: Annotated[int, Field(ge=0)] | None = None
    dim_radius_feet: Annotated[int, Field(ge=0)] | None = None
    stack_count: int = 1
    is_pickable: bool = True
    item_effects: tuple[ItemEffectPresentationState, ...] = ()
    blocks_propagation: bool = False
    contact_passage: ContactPassage = ContactPassage.STRUCTURAL
    supported_by_uuid: UUID | None = None
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
    construction_owner_uuid: UUID | None = None
    construction_geometry: AoEPresentationGeometry | None = None
    construction_suppressions: tuple[SpellSuppression, ...] = ()
    known_to_creator: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerObject:
    placement: WorldObjectPlacement
    item: FloorItem
    # Current observed contents only; None never means an observed empty chest.
    contained_items: tuple[FloorItem, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class TileLook:
    """A tile's surface and name, sent once per seat under its content id (a digest of the value)."""

    look_id: str
    surface: TileSurface
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TileStatic:
    """A tile's fixed part, sent once per tile uuid: no writer changes it for one uuid (a replaced tile has a new
    uuid). `look` is its surface and name's `TileLook` content id."""

    position: tuple[int, int]
    tile_uuid: UUID
    look: str


@packed_dataclass(frozen=True, slots=True, kw_only=True, config=PACKED)
class TileColumns:
    """The changeable scalars of the entered cells that hold a tile, one byte per cell per column in `cells` order
    (x, then y: the `CellValues` order). `flags` holds blocks_optics (bit 0), blocks_propagation (bit 1), the
    surface kind (bits 2-3: ordinary, stairs, ramp) and the slope axis (bits 4-5: none, north-south, east-west).
    `elevation_steps` is empty when every cell is at 0."""

    cells: CellMask
    walking_cost: bytes
    flying_cost: bytes
    swimming_cost: bytes
    burrowing_cost: bytes
    flags: bytes
    default_light: bytes
    resolved_light: bytes
    elevation_steps: Annotated[tuple[int, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class TileFieldUpdate:
    """A perceived tile's changed scalars, each with its after-value; its conditions and residues change through
    their own rows and its static part never changes."""

    position: tuple[int, int]
    changes: WorldTileChanges


@dataclass(frozen=True, slots=True, kw_only=True)
class TileConditions:
    """A tile's own condition names after the occurrence (never its residues' names), in the tile's order."""

    position: tuple[int, int]
    names: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ResidueMaterial:
    """A residue material's fixed part, sent once per residue id."""

    residue_id: str
    name: str
    description: str
    max_amount: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ContributionRow:
    """One contribution of a residue, set at its index (the index after the last appends one)."""

    index: Annotated[int, Field(ge=0)]
    contribution: ResidueContribution


@dataclass(frozen=True, slots=True, kw_only=True)
class ResidueRow:
    """One material on one tile: whole for a key the client does not hold (its condition uuid present), else the
    occurrence's change (`amount` None: unchanged; the contributions it set)."""

    position: tuple[int, int]
    residue_id: str
    condition_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    amount: Annotated[int | None, Field(exclude_if=_unset)] = None
    contributions: Rows[ContributionRow] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ResidueKey:
    position: tuple[int, int]
    residue_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectLook:
    """A floor item's fixed part, sent once per item uuid: no writer changes these fields for one uuid
    (`test_object_look_static` and a census of every gallery case's world fold; a broken object's visual name and a
    cut construction's geometry change, so they are state)."""

    item_uuid: UUID
    item_id: str
    visual_variant_id: Annotated[str | None, Field(exclude_if=_unset)] = None
    contact_passage: ContactPassage = ContactPassage.STRUCTURAL
    supported_by_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    door_mechanism: Annotated[DoorMechanism | None, Field(exclude_if=_unset)] = None
    door_swing: Annotated[DoorSwing | None, Field(exclude_if=_unset)] = None
    maximum_hit_points: Annotated[int | None, Field(exclude_if=_unset)] = None
    concentration_capacity: Annotated[int, Field(exclude_if=_zero)] = 0
    construction_owner_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    known_to_creator: Annotated[bool, Field(exclude_if=_unflagged)] = False


def _one(count: int) -> bool:
    return count == 1


def _picked(flag: bool) -> bool:
    return flag


def _intact(integrity: ItemIntegrity) -> bool:
    return integrity is ItemIntegrity.INTACT


@dataclass(frozen=True, slots=True, kw_only=True)
class BoundaryStructureStatic:
    """A boundary structure's value, sent once per seat under its content id (a digest of the value, so a
    changed structure is another id)."""

    structure_id: str
    structure: BoundaryStructure


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectState:
    """A floor item's changeable part, its value at the occurrence; a field holding its default is left out.
    `visual_item_name` is left out when it is the `name`; `boundary_structure` is a `BoundaryStructureStatic`'s
    id."""

    name: str
    visual_item_name: Annotated[str | None, Field(exclude_if=_unset)] = None
    map_char: str
    boundary_structure: Annotated[str | None, Field(exclude_if=_unset)] = None
    is_open: Annotated[bool | None, Field(exclude_if=_unset)] = None
    is_lit: Annotated[bool | None, Field(exclude_if=_unset)] = None
    very_bright_radius_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    bright_radius_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    dim_radius_feet: Annotated[int | None, Field(exclude_if=_unset)] = None
    stack_count: Annotated[int, Field(exclude_if=_one)] = 1
    is_pickable: Annotated[bool, Field(exclude_if=_picked)] = True
    item_effects: Annotated[tuple[ItemEffectPresentationState, ...], Field(exclude_if=_no_rows)] = ()
    blocks_propagation: Annotated[bool, Field(exclude_if=_unflagged)] = False
    is_engaged: Annotated[bool | None, Field(exclude_if=_unset)] = None
    surface_residues: Annotated[tuple[ObjectResidueState, ...], Field(exclude_if=_no_rows)] = ()
    current_hit_points: Annotated[int | None, Field(exclude_if=_unset)] = None
    concentration_slots: Annotated[tuple[ItemConcentrationSlot, ...], Field(exclude_if=_no_rows)] = ()
    remnant_state: Annotated[ItemRemnantState | None, Field(exclude_if=_unset)] = None
    integrity: Annotated[ItemIntegrity, Field(exclude_if=_intact)] = ItemIntegrity.INTACT
    destruction_outcome: Annotated[str | None, Field(exclude_if=_unset)] = None
    construction_geometry: Annotated[AoEPresentationGeometry | None, Field(exclude_if=_unset)] = None
    construction_suppressions: Annotated[tuple[SpellSuppression, ...], Field(exclude_if=_no_rows)] = ()


def _single_anchor(supports: tuple[WorldObjectSupport, ...]) -> bool:
    return not supports


def _bands(occupies: bool) -> bool:
    return occupies


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectPlacement:
    """An object's placement on the wire: every field its `WorldObjectPlacement` holds that is neither derivable
    nor its default. The object is the row's `item_uuid`; its kind is a boundary exactly when it has a boundary
    direction; `tile_uuid`, left out, is the client's static tile row at `position`; `covered_supports`, left
    out, is that anchor support alone."""

    position: tuple[int, int]
    top_height_steps: int
    boundary_direction: Annotated[CardinalDirection | None, Field(exclude_if=_unset)] = None
    tile_uuid: Annotated[UUID | None, Field(exclude_if=_unset)] = None
    covered_supports: Annotated[tuple[WorldObjectSupport, ...], Field(exclude_if=_single_anchor)] = ()
    occupies_bands: Annotated[bool, Field(exclude_if=_bands)] = True
    base_height_steps: Annotated[int, Field(exclude_if=_zero)] = 0
    orientation: Annotated[CardinalDirection | None, Field(exclude_if=_unset)] = None
    removed_bands: Annotated[tuple[tuple[int, int, int], ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectRow:
    """A world object the seat observes, at an occurrence.

    An entering row carries its state, placement and the faces its residues are authoritative for (those whose
    viewing cell some member sees); a perceived object's change carries its state, and its placement when the
    occurrence wrote one. `members`: bit i is the audience's `observers[i]`, exact as of this row; a seat with one
    observer leaves it out.
    """

    item_uuid: UUID
    members: Annotated[int | None, Field(ge=1, exclude_if=_unset)] = None
    state: ObjectState
    placement: Annotated[ObjectPlacement | None, Field(exclude_if=_unset)] = None
    observed_faces: Annotated[tuple[CardinalDirection, ...], Field(exclude_if=_no_rows)] = ()


Value = TypeVar("Value")


def _named_by_its_definition(schema: JsonDict) -> None:
    """A column's schema is named by its definition (`Column_<value type>_`), not by a title every column
    shares (an SDK generator would number the columns by order)."""
    del schema["title"]


# The rows a group's column selects; left out, every row.
SelectedRows = Annotated[RowBits | None, Field(exclude_if=_unset)]


@dataclass(frozen=True, slots=True, kw_only=True)
class Column(Generic[Value]):
    """One field of a group of rows: the values of the rows `rows` selects, in row order. `rows` left out selects
    every row; a column with no value is left out of its group, and each row it skips holds the field's default."""

    __pydantic_config__ = ConfigDict(json_schema_extra=_named_by_its_definition)

    rows: SelectedRows = None
    values: tuple[Value, ...]


# A column of non-default values, left out when no row holds one.
Sparse = Annotated[Column[Value] | None, Field(exclude_if=_unset)]
# Value types named so the schema names their columns.
type ConstructionGeometry = AoEPresentationGeometry
type MemberBits = Annotated[int, Field(ge=1)]


@dataclass(frozen=True, slots=True, kw_only=True)
class PlacementColumns:
    """The `ObjectPlacement`s of an update's object rows, as columns over the rows `rows` selects (left out:
    every row)."""

    rows: SelectedRows = None
    position: tuple[tuple[int, int], ...]
    top_height_steps: tuple[int, ...]
    boundary_direction: Sparse[CardinalDirection] = None
    tile_uuid: Sparse[UUID] = None
    covered_supports: Sparse[tuple[WorldObjectSupport, ...]] = None
    occupies_bands: Sparse[bool] = None
    base_height_steps: Sparse[int] = None
    orientation: Sparse[CardinalDirection] = None
    removed_bands: Sparse[tuple[tuple[int, int, int], ...]] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ObjectColumns:
    """An update's `ObjectRow`s as columns, one entry per row in row order (field names once per update): the
    rows' uuids, members, observed faces, every `ObjectState` field and their placements. A sparse column holds
    the rows whose value is not the field's default."""

    item_uuids: tuple[UUID, ...]
    members: Sparse[MemberBits] = None
    observed_faces: Sparse[tuple[CardinalDirection, ...]] = None
    name: tuple[str, ...]
    visual_item_name: Sparse[str] = None
    map_char: tuple[str, ...]
    boundary_structure: Sparse[str] = None
    is_open: Sparse[bool] = None
    is_lit: Sparse[bool] = None
    very_bright_radius_feet: Sparse[int] = None
    bright_radius_feet: Sparse[int] = None
    dim_radius_feet: Sparse[int] = None
    stack_count: Sparse[int] = None
    is_pickable: Sparse[bool] = None
    item_effects: Sparse[tuple[ItemEffectPresentationState, ...]] = None
    blocks_propagation: Sparse[bool] = None
    is_engaged: Sparse[bool] = None
    surface_residues: Sparse[tuple[ObjectResidueState, ...]] = None
    current_hit_points: Sparse[int] = None
    concentration_slots: Sparse[tuple[ItemConcentrationSlot, ...]] = None
    remnant_state: Sparse[ItemRemnantState] = None
    integrity: Sparse[ItemIntegrity] = None
    destruction_outcome: Sparse[str] = None
    construction_geometry: Sparse[ConstructionGeometry] = None
    construction_suppressions: Sparse[tuple[SpellSuppression, ...]] = None
    placements: Annotated[PlacementColumns | None, Field(exclude_if=_unset)] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ContainedItem:
    item_uuid: UUID
    state: ObjectState


@dataclass(frozen=True, slots=True, kw_only=True)
class ContainerContents:
    """A container's whole contents, on gaining sight of them (looks once, through `object_looks`)."""

    container_uuid: UUID
    items: Rows[ContainedItem] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ContentsChange:
    """A seen container's contents changing while the seat sees them."""

    container_uuid: UUID
    upserted: Rows[ContainedItem] = ()
    removed: Rows[UUID] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class WorldUpdate:
    """The world a seat perceives change at one occurrence.

    `entered` is the update's authoritative scope: for those cells the client drops everything it holds and keeps
    only what this update carries, their tiles, every object touching them (`placement_support_cells`) and every
    connector with an endpoint there; no object or connector there means none. A record whose value is the one the
    seat holds is kept as the client holds it instead: the entered cells in `tiles_unchanged` (their tile, its
    condition names and residues) and the objects in `objects_unchanged`. Every other row is the keyed change of a
    record the seat perceived before and after the occurrence. Static rows come once per (kind, id) per seat.
    """

    occurrence: int
    entered: CellMaskField = EMPTY_CELLS
    tiles_unchanged: CellMaskField = EMPTY_CELLS
    tile_looks: Rows[TileLook] = ()
    tile_statics: Rows[TileStatic] = ()
    tile_columns: Annotated[TileColumns | None, Field(exclude_if=_unset)] = None
    tile_conditions: Rows[TileConditions] = ()
    tile_changes: Rows[TileFieldUpdate] = ()
    resolved_light: CellValuesField = EMPTY_VALUES
    residue_materials: Rows[ResidueMaterial] = ()
    boundary_structures: Rows[BoundaryStructureStatic] = ()
    residues: Rows[ResidueRow] = ()
    residues_removed: Rows[ResidueKey] = ()
    object_looks: Rows[ObjectLook] = ()
    objects: Annotated[ObjectColumns | None, Field(exclude_if=_unset)] = None
    objects_unchanged: Rows[UUID] = ()
    objects_removed: Rows[UUID] = ()
    contents: Rows[ContainerContents] = ()
    contents_changed: Rows[ContentsChange] = ()
    connectors: Rows[WorldConnectorState] = ()
    connectors_removed: Rows[UUID] = ()


@dataclass(slots=True, kw_only=True)
class StaticStore:
    """The static rows the client was sent, never pruned: tiles by cell (the latest uuid there), tile looks and
    boundary structures by content id, residue materials by id, object looks by item uuid."""

    tiles: dict[tuple[int, int], TileStatic] = field(default_factory=dict)
    tile_looks: dict[str, TileLook] = field(default_factory=dict)
    residues: dict[str, ResidueMaterial] = field(default_factory=dict)
    object_looks: dict[UUID, ObjectLook] = field(default_factory=dict)
    boundary_structures: dict[str, BoundaryStructure] = field(default_factory=dict)


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
    # The root's lineage, or for a group whose root is undisclosed the lineage of its first version.
    lineage: int
    # The root's index in `events`; None when the root itself is not disclosed.
    root: int | None
    events: tuple[PlayerNode, ...]
    version_rows: VersionRows
    start_cursor: int
    end_cursor: int
    observations: tuple[PlayerObservation, ...] = ()
    world_updates: tuple[WorldUpdate, ...] = ()
    audience: PlayerAudience | None = None
    # The perceived values its sensory facts name, each once.
    sensory_rows: SensoryRowsField = NO_SENSORY_ROWS
    # The resolutions its nodes belong to, each once.
    resolutions: Annotated[tuple[PlayerResolution, ...], Field(exclude_if=_no_rows)] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerInitialization:
    generation: UUID
    observer_uuid: UUID
    world: PlayerWorld
    nodes: tuple[PlayerNode, ...]
    version_rows: VersionRows
    end_cursor: int
    observations: tuple[PlayerObservation, ...]
    world_updates: tuple[WorldUpdate, ...]
    hud: PlayerHUDPatch | None = None
    audience: PlayerAudience | None = None
    # The perceived values its sensory facts name, each once.
    sensory_rows: SensoryRowsField = NO_SENSORY_ROWS
    # The resolutions its nodes belong to, each once.
    resolutions: Annotated[tuple[PlayerResolution, ...], Field(exclude_if=_no_rows)] = ()


class PlayerSequence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[9] = 9
    initialization: PlayerInitialization
    lineages: tuple[PlayerLineage, ...]
    combat_log_appends: tuple[CombatLogAppend, ...] = ()


class PlayerUpdate(BaseModel):
    """Atomic admitted after-values, independent of delivery/attachment metadata."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    audience: PlayerAudience
    lineages: tuple[PlayerLineage, ...]
    hud: PlayerHUDPatch | None
    combat_log_appends: tuple[CombatLogAppend, ...]
    content_additions: tuple[ContentDescriptor, ...]


@dataclass(slots=True, kw_only=True)
class PlayerState:
    generation: UUID
    observer_uuid: UUID
    world: PlayerWorld
    tiles: dict[tuple[int, int], WorldTileState] = field(default_factory=dict)
    objects: dict[UUID, PlayerObject] = field(default_factory=dict)
    # Which of the audience's observers observe each held object (bit i: `observers[i]`), as last sent.
    object_members: dict[UUID, int] = field(default_factory=dict)
    connectors: dict[UUID, WorldConnectorState] = field(default_factory=dict)
    static: StaticStore = field(default_factory=StaticStore)
    senses: SensesSnapshot | None = None
    reducer_cursor: int = 0
    # Local reduction bookkeeping, reconstructed from saved version rows.
    # Keep spatial commit order across separately timed presentation groups.
    spatial_commit_cursors: dict[UUID, int] = field(default_factory=dict)
    actors: dict[UUID, PlayerActor] = field(default_factory=dict)
    # The static content of every spatial effect the seat has seen, by effect uuid.
    spatial_content: dict[UUID, SpatialEffectContent] = field(default_factory=dict)
    # Every item instance the seat has seen, by uuid.
    items: dict[UUID, PlayerItem] = field(default_factory=dict)
    current_actor_uuid: UUID | None = None
    round_number: int = 0
    hud_snapshot: PlayerHUDSnapshot | None = None
    audience: PlayerAudience | None = None
    perception: AudiencePerception = field(default_factory=AudiencePerception)
    content: tuple[ContentDescriptor, ...] = ()
    combat_log_appends: tuple[CombatLogAppend, ...] = ()

    @property
    def viewing_audience(self) -> PlayerAudience:
        return resolve_audience(self.observer_uuid, self.audience)
