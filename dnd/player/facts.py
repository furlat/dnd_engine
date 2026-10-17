"""Passive player values: causal structure, permitted facts, and observed world.

Native event recordings remain private. These records deliberately have no
engine constructors, executable state, audience grant maps, or diagnostic rows.
"""

from dnd.core.content.descriptors import ContentDescriptor

from dataclasses import dataclass, field
from typing import Annotated, Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from dnd.player.compatibility import upgrade_spell_fact
from dnd.player.audience import AudiencePerception, PlayerAudience, resolve_audience

from dnd.types.appearance import AppearanceConfig
from dnd.types.world import MovementProvocationPolicy
from dnd.core.action_types import AvailableHandlerInfo
from dnd.core.combat_log import CombatLogEntry
from dnd.core.content.identities import HandlerDispatchOutcome
from dnd.core.creature_types import DamageType, Size
from dnd.core.creature_types import AttackOutcome
from dnd.core.effect_types import ObjectSectionVolume, ApplicationMembership, ResolutionRef, EffectPropagationLink
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.types.event_facts import EventPhase, EventType, LandingKind, MovementTrajectory, SpatialChangeType, WorldConnectorState, WorldTileState, WorldTileChanges
from dnd.core.item_types import (DoorMechanism, DoorSwing, EquippedVisualPolicy, ItemConcentrationSlot, ItemResourceChange, ItemEffectPresentationState,
    ItemIntegrity, ItemPresentationKind, ItemRarity, ItemRemnantState)
from dnd.core.life_types import LifeState, LifeStateChangeReason, RemainsDisposition
from dnd.core.presentation_geometry import AoEPresentationGeometry
from dnd.types.residues import BodyReleaseResult, ObjectResidueState
from dnd.types.senses import (PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, SenseMode, SensesSnapshot,
    VolumeSurfaceSight)
from dnd.core.condition_types import ConditionDurationSummary
from dnd.core.content.identities import ContentRef
from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry
from dnd.types.class_features import DraconicPresenceMode
from dnd.types.material_deposits import MaterialDepositSource
from dnd.types.spatial_effects import AreaPropagation, SpatialDamageSource, SpatialEffectChangeOperation, SpatialEffectInteractionOperation
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.traps import TrapState
from dnd.types.physical_access import ContactPassage
from dnd.types.world import MovementMode, OccupancyLayer
from dnd.types.world_placement import BoundaryStructure, WorldObjectPlacement
from dnd.types.character_progression import PreparedSpellSelection
from dnd.types.abilities import AbilityName
from dnd.types.actor import TemporaryHitPointsGrant, SpatialDisposition
from dnd.types.class_features import FontConversion, IndomitableReroll, RelentlessRageIntervention
from dnd.types.actor_facts import ConditionFact
from dnd.types.summoning import SummonManifestation, SummonDepartureCause
from dnd.types.character_progression import Species, SpeciesVariant, Background, AppliedOriginState, AppliedClassLevel


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerResource:
    key: str
    label: str
    current: int
    maximum: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerCharacterSheet:
    """Evaluated controlled-character data, without executable owners."""

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
    name: str = ''
    portrait_key: str | None = None
    normal_hp: int = 0
    maximum_hp: int = 0
    compatible_item_slots: tuple[tuple[UUID, tuple[str, ...]], ...] = ()
    handler_details: tuple[AvailableHandlerInfo, ...] = ()
    scribed_spell_ids: tuple[str, ...] = ()
    permanent_feature_uses: tuple[str, ...] = ()
    prepared_spell_selections: tuple[PreparedSpellSelection, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerHUDSnapshot:
    """Authorized operation-end display; its revision is a conservative gate."""

    generation: UUID
    observer_uuid: UUID
    revision: int
    initiative: tuple[UUID, ...]
    sheets: tuple[PlayerCharacterSheet, ...]


class SheetChanges(TypedDict, total=False):
    """Present fields replace the seat's sheet values; against no sheet every field is present."""

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
    name: str
    portrait_key: str | None
    normal_hp: int
    maximum_hp: int
    compatible_item_slots: tuple[tuple[UUID, tuple[str, ...]], ...]
    handler_details: tuple[AvailableHandlerInfo, ...]
    scribed_spell_ids: tuple[str, ...]
    permanent_feature_uses: tuple[str, ...]
    prepared_spell_selections: tuple[PreparedSpellSelection, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SheetPatch:
    actor_uuid: UUID
    changes: SheetChanges


@dataclass(frozen=True, slots=True, kw_only=True)
class PlayerHUDPatch:
    """The seat's operation-end display as a patch against its last one.

    It always carries the revision; the initiative and the sheet order only
    when they changed, and the sheets that changed. Against no display it
    carries all of them.
    """

    generation: UUID
    observer_uuid: UUID
    revision: int
    initiative: tuple[UUID, ...] | None = None
    sheet_order: tuple[UUID, ...] | None = None
    sheets: tuple[SheetPatch, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class CombatLogAppend:
    generation: UUID
    observer_uuid: UUID
    encounter_log_index: int
    operation_end_cursor: int
    entry: CombatLogEntry


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

    event_uuid: UUID
    actor_uuid: UUID
    changes: ActorChanges
    contact: PerceivedContact | None
    items: tuple[ItemPatch, ...] = ()


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
    source_item_uuid: UUID | None = None
    item_effects: tuple[ItemEffectPresentationState, ...] = ()
    intercepted_by_condition_uuid: UUID | None = None
    projectile_deflection_position: tuple[float, float] | None = None
    target_kind: Literal["creature", "object"] = "creature"
    target_position: tuple[int, int] | None = None
    target_base_height_steps: int | None = None
    attack_source_kind: Literal["equipped", "unarmed", "natural"] = "equipped"

    @property
    def weapon_set(self) -> WeaponSet:
        """The declared source selects gear independently of its authored VFX."""
        if self.attack_source_kind != "equipped":
            return WeaponSet.NONE
        return WeaponSet.RANGED if self.weapon_slot in (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF) else WeaponSet.MELEE


@dataclass(frozen=True, slots=True, kw_only=True)
class SpellFact:
    kind: Literal["spell"] = "spell"
    source_entity_uuid: UUID
    target_entity_uuid: UUID | None
    behavior_id: str | None
    name: str | None
    source_position: tuple[int, int] | None
    declared_target_entity_uuids: tuple[UUID, ...]
    application: ApplicationMembership | None
    propagation: EffectPropagationLink | None = None
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
    area_propagation: AreaPropagation = "line_of_effect"
    target_kind: Literal["creature", "object"] = "creature"
    target_position: tuple[int, int] | None = None
    target_base_height_steps: int | None = None

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
    previous_reach_lineage_uuid: UUID | None
    prerequisite_destruction_lineages: tuple[UUID, ...]


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
    connector_presentation_key: str | None = None


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
    disclosed_path: tuple[tuple[int, int], ...] = ()
    start_elevation_feet: int | None = None
    end_elevation_feet: int | None = None
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
class DamageRequestFact:
    kind: Literal["damage"] = "damage"
    stage: Literal["taken"] = "taken"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    intercepted_by_condition_uuid: UUID | None = None
    source_condition_uuid: UUID | None = None
    relentless_rage: RelentlessRageIntervention | None = None


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
    body_release: BodyReleaseResult | None = None
    effect_id: str | None = None
    spatial_source: SpatialDamageSource | None = None
    source_condition_uuid: UUID | None = None


DamageFact = DamageRequestFact | DamageResultFact


@dataclass(frozen=True, slots=True, kw_only=True)
class SavingThrowFact:
    """The disclosed outcome of one native save, without private roll modifiers."""

    kind: Literal["saving_throw"] = "saving_throw"
    target_entity_uuid: UUID
    ability_name: AbilityName
    succeeded: bool
    effect_id: str | None
    indomitable_reroll: IndomitableReroll | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class HealFact:
    kind: Literal["heal"] = "heal"
    source_entity_uuid: UUID | None
    target_entity_uuid: UUID
    actual_healing: int
    was_blocked: bool
    resulting_normal_hp: int | None
    resulting_temporary_hp: int | None
    source_condition_uuid: UUID | None = None


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
    remains_disposition: RemainsDisposition = RemainsDisposition.INTACT
    preserved_equipped_item_uuids: tuple[UUID, ...] = ()


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
    items: tuple[ItemPatch, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ConditionChangeFact:
    kind: Literal["condition"] = "condition"
    target_entity_uuid: UUID
    event_type: EventType
    condition: ConditionFact
    consumed: bool = False


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
    birth_event_uuid: UUID
    manifestation: SummonManifestation


@dataclass(frozen=True, slots=True, kw_only=True)
class SpatialFact:
    kind: Literal["spatial"] = "spatial"
    change_type: SpatialChangeType
    entity_uuid: UUID | None
    position: tuple[int, int]
    object_uuid: UUID | None = None
    commit_event_uuid: UUID | None = None
    previous_occupancy_layer: OccupancyLayer | None = None
    occupancy_layer: OccupancyLayer | None = None
    terminal_departure: bool = False
    terminal_cause: SummonDepartureCause | None = None
    creation: CreationWitness | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class FactionFact:
    kind: Literal["faction"] = "faction"
    entity_uuid: UUID
    faction_after: str | None
    control_lost: bool = False


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
    resource_change: ItemResourceChange | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ActionReaction:
    """Disclosed reaction result and its native triggering lineage."""

    triggered_lineage_uuid: UUID | None
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
    font_conversion: FontConversion | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class SpatialEffectContent:
    """A spatial effect's static content; a seat receives it once per effect."""

    content_ref: ContentRef
    name: str
    description: str


class SpatialEffectSighting(BaseModel):
    """One observation of a spatial effect without its static content (`PerceivedSpatialEffect`'s other fields)."""

    model_config = ConfigDict(frozen=True)
    duration: ConditionDurationSummary | None = None
    positions: tuple[tuple[int, int], ...]
    owner_revision: int | None = Field(default=None, ge=0)
    apparent_presence: bool = False
    trap_state: TrapState | None = None
    pressed: bool | None = None
    direction: tuple[int, int] | None = None
    anchor_item_uuid: UUID | None = None
    anchor_entity_uuid: UUID | None = None
    energy_type: DamageType | None = None
    presence_mode: DraconicPresenceMode | None = None
    sustainer_item_uuid: UUID | None = None
    concentration_slot_uuid: UUID | None = None
    anchor_position: tuple[int, int] | None = None
    anchor_elevation_steps: int | None = None
    area_geometry: AoEPresentationGeometry | None = None
    construction_sections: tuple[WallAssemblyPresentationGeometry, ...] = ()
    area_propagation: AreaPropagation | None = None
    deposit_source: MaterialDepositSource | None = None
    visible_volume_positions: tuple[tuple[int, int], ...] = ()
    upper_volume_surfaces: tuple[VolumeSurfaceSight, ...] = ()
    suppressions: tuple[SpellSuppression, ...] = ()


def joined_effect(sighting: SpatialEffectSighting, content: SpatialEffectContent) -> PerceivedSpatialEffect:
    """The perceived effect of a sighting and its content (both already validated)."""
    return PerceivedSpatialEffect.model_construct(duration=sighting.duration, content_ref=content.content_ref,
        name=content.name, description=content.description, positions=sighting.positions,
        owner_revision=sighting.owner_revision, apparent_presence=sighting.apparent_presence,
        trap_state=sighting.trap_state, pressed=sighting.pressed, direction=sighting.direction,
        anchor_item_uuid=sighting.anchor_item_uuid, anchor_entity_uuid=sighting.anchor_entity_uuid,
        energy_type=sighting.energy_type, presence_mode=sighting.presence_mode,
        sustainer_item_uuid=sighting.sustainer_item_uuid, concentration_slot_uuid=sighting.concentration_slot_uuid,
        anchor_position=sighting.anchor_position, anchor_elevation_steps=sighting.anchor_elevation_steps,
        area_geometry=sighting.area_geometry, construction_sections=sighting.construction_sections,
        area_propagation=sighting.area_propagation, deposit_source=sighting.deposit_source,
        visible_volume_positions=sighting.visible_volume_positions,
        upper_volume_surfaces=sighting.upper_volume_surfaces, suppressions=sighting.suppressions)


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
    spatial_effect_sightings: dict[UUID, SpatialEffectSighting] = field(default_factory=dict)
    # The content of each sighted effect the seat does not hold yet; a folded fact holds every sighting's content.
    spatial_effect_content: dict[UUID, SpatialEffectContent] = field(default_factory=dict)
    spatial_effects_removed: frozenset[UUID] = frozenset()
    light_sources_changed: dict[UUID, PerceivedLightSource] = field(default_factory=dict)
    light_sources_removed: dict[UUID, int] = field(default_factory=dict)

    @property
    def spatial_effects_changed(self) -> dict[UUID, PerceivedSpatialEffect]:
        """The perceived effects the shared sensory reducer reads: each sighting with its content."""
        return {identity: joined_effect(row, self.spatial_effect_content[identity])
                for identity, row in self.spatial_effect_sightings.items()}


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
    interaction_operation: SpatialEffectInteractionOperation | None = None
    removed_positions: tuple[tuple[int, int], ...] = ()


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
    remains_disposition: RemainsDisposition = RemainsDisposition.INTACT
    previous_item: "FloorItem | None" = None
    affected_volume: ObjectSectionVolume | None = None
    resulting_placement: WorldObjectPlacement | None = None


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
    resolution_ref: ResolutionRef | None = None
    cancellation: ActionCancellation | None = None
    combat_log: CombatLogEntry | None = None
    turn_execution_id: UUID | None = None
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
class TileFieldUpdate:
    position: tuple[int, int]
    changes: WorldTileChanges


@dataclass(frozen=True, slots=True, kw_only=True)
class WorldUpdate:
    event_uuid: UUID
    tiles: tuple[WorldTileState, ...]
    objects: tuple[PlayerObject, ...]
    objects_removed: tuple[UUID, ...]
    connectors: tuple[WorldConnectorState, ...]
    tile_changes: tuple[TileFieldUpdate, ...] = ()


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
    lineage_uuid: UUID
    root: PlayerNode | None
    events: tuple[PlayerNode, ...]
    version_rows: tuple[VersionRow, ...]
    start_cursor: int
    end_cursor: int
    observations: tuple[PlayerObservation, ...] = ()
    world_updates: tuple[WorldUpdate, ...] = ()
    audience: PlayerAudience | None = None

    @property
    def group_uuid(self) -> UUID:
        """Stable local presentation key, including consequences of an unknown cause."""
        return self.root.uuid if self.root is not None else self.lineage_uuid


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
    hud: PlayerHUDPatch | None = None
    audience: PlayerAudience | None = None


class PlayerSequence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[6] = 6
    initialization: PlayerInitialization
    lineages: tuple[PlayerLineage, ...]
    combat_log_appends: tuple[CombatLogAppend, ...] = ()
    huds: tuple[PlayerHUDPatch, ...] = ()


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
    connectors: tuple[WorldConnectorState, ...] = ()
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
