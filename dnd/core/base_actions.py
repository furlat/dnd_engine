"""Action templates, cost models, execution events, and discovery DTOs."""

import time
from dataclasses import replace
from math import hypot

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, computed_field, field_validator, model_validator
from dnd.action_timing import action_timing_enabled, record_action_timing
from dnd.core.attack_types import AttackSourceMetadata
from dnd.core.creature_types import DamageType
from dnd.core.action_types import (
    ActionSelection,
    CostSource,
    AvailableHandlerInfo,
    ActionPresentationKind,
    ActionAffordance,
    ActionVariantFacet,
    ActionEconomyCostType,
    EntityTargetPerception,
    PositionSelection,
    RestrictedActionGrant,
    RestrictedActionKind,
)
from dnd.core.effect_types import ApplicationMembership, ApplicationResolutionRef, EventResolutionRef, EffectPropagationLink, EffectOrigin, EffectOriginKind
from dnd.types.discovery import ActorScan, Relationship, ScanRecord, relationship
from dnd.types.event_facts import GroupEntryKind
from dnd.core.events import ActionApplicationCommittedEvent, ActionCostsCommittedEvent, Event, EventType, EventPhase, EventProcessor, Range, EventQueue
from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY, read_private_attribute
from dnd.types.world import MovementMode
from dnd.types.class_features import FontConversion
from dnd.core.base_block import BaseBlock, resolution_order_key
from dnd.core.combat_log import ActionLogData, CombatLogEntry, CombatLogEntryType, MultiEntityLogData, md_color
from dnd.core.content.identities import ContentRef, validate_namespaced_id
from dnd.core.content.runtime import (
    BehaviorBinding,
    active_runtime_behavior_binding,
    runtime_behavior_provider,
)
from dnd.core.aoe import AoEShape, objective_footprint
from dnd.core.traversal_connectors import ConnectorTraversalDiscovery
from dnd.core.presentation_geometry import AoEPresentationGeometry
from dnd.core.geometry import bresenham_line, grid_distance_feet
from dnd.core.gridmap import get_map
from dnd.types.physical_access import PhysicalAccess
from dnd.core.item_types import (
    ItemPresentationProvider,
    ItemPresentationState,
)
from dnd.core.modifiers import AdvantageStatus
from dnd.blocks.sensory import Senses
from typing import (
    Any,
    Optional,
    Callable,
    ClassVar,
    OrderedDict,
    List,
    Dict,
    Literal,
    Protocol,
    Sequence,
    Set,
    Tuple,
    cast,
    final,
    runtime_checkable,
)
from uuid import UUID, uuid4, uuid5
from enum import Enum


@runtime_checkable
class FiniteChargeProvider(Protocol):
    """Structural boundary for an item-backed finite action cost."""

    charges: int

    def use_admission_error(self, actor_uuid: UUID) -> Optional[str]:
        ...

    def prepare_charge_consumption(self, amount: int, source_entity_uuid: UUID, parent_event: Event) -> Event:
        ...

    def commit_prepared_charge(self, prepared: Event) -> Event:
        ...

    def consume_charge_with_event(
        self,
        amount: int,
        source_entity_uuid: UUID,
        parent_event: "Event",
    ) -> "Event":
        """Consume finite charges through the item's ordinary child event."""
        ...


CostType = Literal[
    "actions", "bonus_actions", "reactions", "movement",
    "spell_slot_1", "spell_slot_2", "spell_slot_3", "spell_slot_4",
    "spell_slot_5", "spell_slot_6", "spell_slot_7", "spell_slot_8", "spell_slot_9"
]

SPELL_SLOT_COST_TYPES: Dict[int, CostType] = {
    1: "spell_slot_1", 2: "spell_slot_2", 3: "spell_slot_3",
    4: "spell_slot_4", 5: "spell_slot_5", 6: "spell_slot_6",
    7: "spell_slot_7", 8: "spell_slot_8", 9: "spell_slot_9",
}
SPELL_SLOT_TEMPLATE_SEPARATOR = "__slot_"
RESTRICTED_ACTION_TEMPLATE_SEPARATOR = "__grant_"


def spell_slot_cost_type(level: int) -> CostType:
    """Convert a spell slot level to an action-economy cost type.

    Args:
        level: Spell slot level from 1 through 9.

    Returns:
        Cost type matching the requested spell slot level.

    Raises:
        ValueError: If `level` is outside the implemented spell-slot range.
    """
    result = SPELL_SLOT_COST_TYPES.get(level)
    if result is None:
        raise ValueError(f"Invalid spell slot level: {level}")
    return result


def target_resolution_sort_key(target_uuid: UUID) -> tuple[bool, int, int, str, str]:
    """Return a replay-stable ordering key for simultaneous target resolution.

    Args:
        target_uuid: Target block identity to order.

    Returns:
        Position and name ordering with UUID only as a final exact-tie fallback.
    """
    target = BaseBlock.get(target_uuid)
    if target is None:
        return (True, 0, 0, "", str(target_uuid))
    return resolution_order_key(target)


def lowest_hp_first(target_uuids: Sequence[UUID], limit: int) -> List[UUID]:
    """Keep at most `limit` targets, lowest current HP first (plan Q4).

    The fixed resolution order breaks HP ties and orders the kept targets.
    """
    def hp_key(target_uuid: UUID) -> tuple[int, tuple[bool, int, int, str, str]]:
        block = BaseBlock.get(target_uuid)
        return (block.get_hp() if block is not None else 0, target_resolution_sort_key(target_uuid))
    return sorted(sorted(target_uuids, key=hp_key)[:limit], key=target_resolution_sort_key)


class ActionCategory(str, Enum):
    """Classification of action types."""

    ABILITY = "ability"
    ATTACK = "attack"
    SPELL = "spell"
    MOVEMENT = "movement"


class ActionAvailabilityStatus(str, Enum):
    """Closed reason why one authored action row can or cannot execute."""

    AVAILABLE = "available"
    SOURCE_UNAFFORDABLE = "source_unaffordable"
    REQUIREMENTS_UNMET = "requirements_unmet"
    NO_VALID_TARGETS = "no_valid_targets"
    TARGET_COST_UNAFFORDABLE = "target_cost_unaffordable"


class PositionDiscoveryContract(BaseModel):
    """Subjective prerequisites for discovering position targets.

    This contract describes only what an observer may expose as a candidate.
    Action execution still performs authoritative validation, so an unseen
    blocker can reject a command without leaking through the affordance set.
    """

    candidate_source: Literal["visible", "reachable"] = Field(
        default="visible",
        description="Subjective cell set from which position candidates are drawn.",
    )
    requires_subjective_walkable: bool = Field(
        default=False,
        description="Whether the observer must currently know the cell as walkable.",
    )
    requires_subjective_unoccupied: bool = Field(
        default=False,
        description="Whether the observer must not perceive an occupant in the cell.",
    )
    requires_axis_or_diagonal_alignment: bool = Field(
        default=False,
        description=(
            "Whether the candidate must share an axis or exact diagonal with "
            "the source."
        ),
    )
    requires_subjective_traversable_path: bool = Field(
        default=False,
        description=(
            "Whether every disclosed traversal step must be subjectively "
            "walkable."
        ),
    )
    exclude_source_position: bool = Field(
        default=True,
        description="Whether the acting entity's current cell is excluded.",
    )
    bounded_by_remaining_movement: bool = Field(
        default=False,
        description=(
            "Whether target movement cost must fit current movement before the "
            "candidate becomes executable."
        ),
    )
    distance_is_movement_cost: bool = Field(
        default=False,
        description="Whether target distance is exposed as its movement cost.",
    )


class PositionRegion(BaseModel):
    """Where a position action may aim (plan §14.4 region descriptors).

    Discovery lists no cells for it: the client or the AI aims anywhere in the
    region and preview validates that one aim on demand.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    range_feet: Optional[int] = None
    candidate_source: Literal["visible", "reachable"] = "visible"
    requires_unoccupied: bool = False
    requires_walkable: bool = False
    requires_axis_or_diagonal_alignment: bool = False
    exclude_source_position: bool = True


class TargetType(str, Enum):
    """Target routing categories used by discovery and execution."""

    SELF = "self"
    ENTITY = "entity"
    CREATURE_OR_OBJECT = "creature_or_object"
    POSITION = "position"
    POSITION_PATH = "position_path"
    POSITION_LOS = "position_los"
    POSITION_AOE = "position_aoe"
    MULTI_ENTITY = "multi_entity"
    OBJECT = "object"


class OutcomeResolution(str, Enum):
    """Mechanism that determines whether a modeled damage application occurs."""

    AUTOMATIC = "automatic"
    ATTACK_ROLL = "attack_roll"
    SAVING_THROW = "saving_throw"
    UNKNOWN = "unknown"


class OutcomeApplicationScope(str, Enum):
    """How repeated outcome applications map onto selected or affected entities."""

    ALLOCATED_TARGETS = "allocated_targets"
    EACH_AFFECTED_ENTITY = "each_affected_entity"


class DamageRollProfile(BaseModel):
    """Actor-known dice formula for one damage component in an action."""

    model_config = ConfigDict(frozen=True)

    dice_count: int = Field(ge=0, description="Number of dice rolled per application.")
    die_size: int = Field(ge=1, description="Number of faces on each damage die.")
    flat_bonus: int = Field(default=0, description="Flat bonus added once per application.")
    damage_type: str = Field(description="Damage type applied to this component.")
    save_dc: int | None = Field(default=None, description="Optional on-hit save gating this packet.")
    save_ability: str | None = None
    double_on_critical: bool = True


class AttackRollBaseline(BaseModel):
    """Read-only actor contribution to an attack-roll outcome model."""

    attack_bonus: int = Field(description="Actor-side bonus added to the d20 roll.")
    advantage: AdvantageStatus = Field(description="Actor-side advantage state before target modifiers.")
    critical_threshold: int = Field(ge=1, le=20, description="Natural d20 threshold for an actor-side critical hit.")
    critical_extra_dice: int = Field(ge=0, description="Actor-side extra damage dice added on a critical hit.")


class ActionDiscoveryDescription(BaseModel):
    """Action-owned descriptive facts; existing profiles retain rules and outcomes."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    spell_level: int | None = None
    cast_at_level: int | None = None
    cast_levels: tuple[int, ...] = ()
    is_spell_variant: bool = False
    cast_cost_label: str | None = None
    damage_types: tuple[DamageType, ...] = ()
    loot_item_uuid: UUID | None = None
    fixed_facets: tuple[ActionVariantFacet, ...] = ()
    spellcasting_source_id: UUID | None = None
    spellcasting_provider_id: str | None = None
    spellcasting_ability: str | None = None


class ActionOutcomeProfile(BaseModel):
    """Actor-baseline stochastic model disclosed with an available action.

    The profile describes the action before target-private modifiers, temporary
    hit points, and undisclosed defenses. Policy consumers must combine it only
    with facts present in their subjective state and retain that scope in any
    derived estimate.
    """

    model_config = ConfigDict(frozen=True)

    effect_id: Optional[str] = Field(
        default=None,
        description="Stable identity of the modeled effect for typed interactions.",
    )
    resolution: OutcomeResolution = Field(description="Roll mechanism used by each application.")
    applications: int = Field(default=1, ge=1, description="Independent repeated applications such as rays or darts.")
    application_scope: OutcomeApplicationScope = Field(
        default=OutcomeApplicationScope.ALLOCATED_TARGETS,
        description="Whether applications are allocated among targets or applied to every affected entity.",
    )
    damage_rolls: Sequence[DamageRollProfile] = Field(
        default_factory=tuple,
        description="Damage components rolled per application.",
    )
    attack_bonus: Optional[int] = Field(default=None, description="Actor-baseline d20 attack bonus when applicable.")
    advantage: AdvantageStatus = Field(
        default=AdvantageStatus.NONE,
        description="Actor-baseline attack advantage state.",
    )
    critical_threshold: int = Field(default=20, ge=1, le=20, description="Natural d20 threshold for a critical hit.")
    critical_extra_dice: int = Field(default=0, ge=0, description="Extra critical dice beyond doubling base dice.")
    save_dc: Optional[int] = Field(default=None, description="Saving throw DC when the action uses a save.")
    save_ability: Optional[str] = Field(default=None, description="Saving throw ability when known.")
    half_damage_on_save: bool = Field(default=False, description="Whether a successful save retains half damage.")
    scope: Literal["actor_baseline"] = Field(
        default="actor_baseline",
        description="Explicit boundary of facts represented by this profile.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Freeze the disclosed damage-component sequence."""
        object.__setattr__(self, "damage_rolls", tuple(self.damage_rolls))


class ActionSetupDuration(str, Enum):
    """Lifetime class disclosed by a self-directed setup action."""

    CURRENT_TURN = "current_turn"
    UNTIL_NEXT_TURN = "until_next_turn"
    UNTIL_REMOVED = "until_removed"


class ActionSetupMaintenanceTrigger(str, Enum):
    """Actor behavior that requires a setup-retention check."""

    REVEALING_ACTION = "revealing_action"


class ActionSetupMaintenanceFailure(str, Enum):
    """Authoritative setup transition caused by a failed maintenance check."""

    REMOVE_SETUP = "remove_setup"


class ActionSetupMaintenanceProfile(BaseModel):
    """Engine-owned stochastic rule governing whether a setup persists."""

    model_config = ConfigDict(frozen=True)

    trigger: ActionSetupMaintenanceTrigger = Field(description="Behavior that triggers the maintenance check.")
    skill_name: str = Field(description="Actor skill rolled by the maintenance check.")
    initial_dc: int = Field(ge=0, description="Difficulty class of the first maintenance check.")
    dc_increment_per_success: int = Field(
        default=0,
        ge=0,
        description="Difficulty-class increase after each successful maintenance check.",
    )
    check_bonus: int = Field(description="Current actor bonus applied to the disclosed skill check.")
    check_advantage: AdvantageStatus = Field(
        default=AdvantageStatus.NONE,
        description="Current actor-baseline advantage state for the disclosed skill check.",
    )
    failure: ActionSetupMaintenanceFailure = Field(description="Setup transition caused by a failed check.")


class ActionSelfSetupProfile(BaseModel):
    """Engine-owned logical annotation for a self-directed combat setup."""

    model_config = ConfigDict(frozen=True)

    semantic_id: str = Field(description="Stable semantic family produced by the setup.")
    duration: ActionSetupDuration = Field(description="Expected lifetime class of the setup.")
    maximum_duration_rounds: Optional[int] = Field(
        default=None,
        gt=0,
        description="Known upper duration bound when the setup expires automatically.",
    )
    condition_fact_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Canonical actor condition facts guaranteed by successful execution.",
    )
    active_condition_semantic_keys: frozenset[str] = Field(
        default_factory=frozenset,
        description="Stable condition type keys that establish the setup is already active.",
    )
    increases_weapon_damage: bool = Field(default=False, description="Whether weapon damage increases.")
    resistance_damage_types: frozenset[str] = Field(
        default_factory=frozenset,
        description="Damage types resisted while the setup remains active.",
    )
    grants_bonus_action_attack: bool = Field(default=False, description="Whether a bonus-action attack is enabled.")
    grants_outgoing_attack_advantage: bool = Field(default=False, description="Whether actor attacks gain advantage.")
    grants_incoming_attack_advantage: bool = Field(default=False, description="Whether attacks against the actor gain advantage.")
    grants_incoming_attack_disadvantage: bool = Field(default=False, description="Whether attacks against the actor gain disadvantage.")
    armor_class_bonus: int = Field(default=0, ge=0, description="Known armor-class increase.")
    movement_speed_multiplier: float = Field(default=1.0, ge=1.0, description="Known movement-speed multiplier.")
    extra_actions_per_turn: int = Field(default=0, ge=0, description="Additional general actions supplied per turn.")
    grants_invisibility: bool = Field(default=False, description="Whether the setup makes the actor invisible.")
    incapacitates_on_removal: bool = Field(default=False, description="Whether ordinary removal applies incapacitation.")
    maintenance: Optional[ActionSetupMaintenanceProfile] = Field(
        default=None,
        description="Stochastic retention rule when the setup can end after actor behavior.",
    )


class TargetEffectDisposition(str, Enum):
    """Tactical direction of one target-specific rule effect."""

    BENEFICIAL = "beneficial"
    HARMFUL = "harmful"
    NEUTRAL = "neutral"


class ActionTargetEffectBranchProfile(BaseModel):
    """Engine-owned rule branch for an effect applied to one selected target."""

    model_config = ConfigDict(frozen=True)

    effect_id: str = Field(description="Stable semantic identity of the branch effect.")
    disposition: TargetEffectDisposition = Field(description="Whether the effect helps or harms its recipient.")
    included_creature_types: frozenset[str] = Field(
        default_factory=frozenset,
        description="Creature types eligible for this branch; empty accepts every type not excluded.",
    )
    excluded_creature_types: frozenset[str] = Field(
        default_factory=frozenset,
        description="Creature types ineligible for this branch.",
    )
    resolution: OutcomeResolution = Field(description="Rule mechanism that applies this branch.")
    save_dc: Optional[int] = Field(default=None, description="Saving throw DC when the branch permits a save.")
    save_ability: Optional[str] = Field(default=None, description="Saving throw ability when the branch permits a save.")
    condition_fact_ids: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Planning facts established when the branch applies.",
    )
    condition_semantic_keys: frozenset[str] = Field(
        default_factory=frozenset,
        description="Stable condition keys established when the branch applies.",
    )

    @model_validator(mode="after")
    def validate_branch(self) -> "ActionTargetEffectBranchProfile":
        """Reject contradictory applicability and incomplete save rules."""
        overlap = self.included_creature_types & self.excluded_creature_types
        if overlap:
            raise ValueError("included and excluded creature types cannot overlap")
        if self.resolution is OutcomeResolution.SAVING_THROW:
            if self.save_dc is None or self.save_ability is None:
                raise ValueError("saving-throw target effects require save_dc and save_ability")
        elif self.save_dc is not None or self.save_ability is not None:
            raise ValueError("save metadata is valid only for saving-throw target effects")
        return self


class ActionTargetEffectProfile(BaseModel):
    """Engine-owned conditional effects for the selected targets of an action."""

    model_config = ConfigDict(frozen=True)

    semantic_id: str = Field(description="Stable semantic family of the complete target effect.")
    branches: Tuple[ActionTargetEffectBranchProfile, ...] = Field(
        min_length=1,
        description="Mutually interpretable target-specific rule branches.",
    )

    @model_validator(mode="after")
    def validate_unique_effect_ids(self) -> "ActionTargetEffectProfile":
        """Require one unambiguous definition for each effect identity."""
        effect_ids = [branch.effect_id for branch in self.branches]
        if len(effect_ids) != len(set(effect_ids)):
            raise ValueError("target effect branch ids must be unique")
        return self


class ActionInformationOperation(str, Enum):
    """Dependency-neutral information transition declared by an action rule."""

    REVEAL_REGION = "reveal_region"
    CHANGE_LIGHT = "change_light"
    GRANT_SENSE = "grant_sense"
    CONCEAL_REGION = "conceal_region"


class ActionTopologyOperation(str, Enum):
    """Dependency-neutral topology transition declared by an action rule."""

    CREATE_BLOCKER = "create_blocker"
    REMOVE_BLOCKER = "remove_blocker"


class ActionWorldEffectCertainty(str, Enum):
    """Whether a declared world effect always occurs after successful execution."""

    GUARANTEED = "guaranteed"
    CONDITIONAL = "conditional"


class ActionWorldEffectAnchor(str, Enum):
    """Action-relative location anchoring a world effect."""

    ACTOR = "actor"
    SELECTED_TARGET = "selected_target"
    SELECTED_POSITION = "selected_position"
    SELECTED_OBJECT = "selected_object"


class ActionWorldEffectScope(str, Enum):
    """Typed subject or region changed by a world effect."""

    TARGET = "target"
    REGION = "region"
    FRONTIER = "frontier"
    MAGICAL_DARKNESS = "magical_darkness"
    HAZARD_REGION = "hazard_region"


class ActionWorldEffectShape(str, Enum):
    """Geometric shape used by an area-scoped world effect."""

    SPHERE = "sphere"


class InformationEffectProfile(BaseModel):
    """Engine-owned information transition produced by an action rule."""

    model_config = ConfigDict(frozen=True)

    operation: ActionInformationOperation = Field(description="Information operation performed by the rule.")
    certainty: ActionWorldEffectCertainty = Field(description="Whether the information transition is guaranteed or conditional.")
    anchor: ActionWorldEffectAnchor = Field(description="Action-relative location anchoring the transition.")
    scope: ActionWorldEffectScope = Field(description="Typed subject or region changed by the transition.")
    shape: Optional[ActionWorldEffectShape] = Field(default=None, description="Area shape when the transition has geometric extent.")
    radius_feet: Optional[int] = Field(default=None, ge=0, description="Area or sense radius in feet when known.")
    sense_type: Optional[str] = Field(default=None, description="Stable sense identifier granted by a grant-sense transition.")

    @model_validator(mode="after")
    def validate_information_effect(self) -> "InformationEffectProfile":
        """Require coherent geometry and sense metadata."""
        if (self.shape is None) != (self.radius_feet is None):
            raise ValueError("information effect shape and radius_feet must be declared together")
        if self.operation is ActionInformationOperation.GRANT_SENSE:
            if self.sense_type is None:
                raise ValueError("grant-sense information effects require sense_type")
        elif self.sense_type is not None:
            raise ValueError("sense_type is valid only for grant-sense information effects")
        return self


class TopologyEffectProfile(BaseModel):
    """Engine-owned traversability, visibility, or hazard topology transition."""

    model_config = ConfigDict(frozen=True)

    operation: ActionTopologyOperation = Field(description="Topology operation performed by the rule.")
    certainty: ActionWorldEffectCertainty = Field(description="Whether the topology transition is guaranteed or conditional.")
    anchor: ActionWorldEffectAnchor = Field(description="Action-relative location anchoring the transition.")
    scope: ActionWorldEffectScope = Field(description="Typed subject or region changed by the transition.")
    shape: Optional[ActionWorldEffectShape] = Field(default=None, description="Area shape when the transition has geometric extent.")
    radius_feet: Optional[int] = Field(default=None, ge=0, description="Affected radius in feet when known.")
    affects_movement: bool = Field(default=False, description="Whether traversability changes.")
    affects_vision: bool = Field(default=False, description="Whether line-of-sight topology changes.")
    affects_hazards: bool = Field(default=False, description="Whether route-hazard topology changes.")

    @model_validator(mode="after")
    def validate_topology_geometry(self) -> "TopologyEffectProfile":
        """Require shape and radius to describe one complete area contract."""
        if (self.shape is None) != (self.radius_feet is None):
            raise ValueError("topology effect shape and radius_feet must be declared together")
        return self


class ActionWorldEffectProfile(BaseModel):
    """Engine-owned information and topology effects produced by an action."""

    model_config = ConfigDict(frozen=True)

    semantic_id: str = Field(description="Stable semantic family of the complete world effect.")
    information_effects: Tuple[InformationEffectProfile, ...] = Field(
        default_factory=tuple,
        description="Information transitions produced by successful execution.",
    )
    topology_effects: Tuple[TopologyEffectProfile, ...] = Field(
        default_factory=tuple,
        description="Topology transitions produced by successful execution.",
    )

    @model_validator(mode="after")
    def validate_nonempty_world_effect(self) -> "ActionWorldEffectProfile":
        """Require at least one observable information or topology transition."""
        if not self.information_effects and not self.topology_effects:
            raise ValueError("world effect profiles require an information or topology effect")
        return self

CostEvaluator = Callable[[UUID, CostType, int], bool]
ResourceCostEvaluator = Callable[[UUID, str, int], bool]


def block_action_resource_cost_evaluator(
    owner_uuid: UUID,
    resource_name: str,
    resource_cost: int,
) -> bool:
    """Check a named resource through the neutral BaseBlock owner surface."""
    owner = BaseBlock.get(owner_uuid)
    if owner is None:
        return False
    return owner.can_afford_action_resource(resource_name, resource_cost)


class BaseCost(BaseModel):
    """Serializable action cost without executable callbacks."""

    name: str = Field(default="A Cost", description="Human-readable cost label.")
    cost_type: CostType = Field(description="Action economy bucket consumed by this cost.")
    cost: int = Field(description="Amount consumed from the action economy bucket.")
    resource_name: Optional[str] = Field(
        default=None,
        description="Optional named resource consumed in addition to the action economy bucket.",
    )
    resource_cost: int = Field(default=0, description="Amount consumed from the named resource.")


class ConditionalCost(BaseCost):
    """A published cost paid only when the declared trigger occurs."""
    trigger: Literal["hit"] = "hit"


class Cost(BaseCost):
    """Runtime action cost with optional affordability callbacks."""

    evaluator: Optional[CostEvaluator] = Field(
        default=None,
        exclude=True,
        description="Callback that checks action-economy affordability.",
    )
    resource_evaluator: Optional[ResourceCostEvaluator] = Field(
        default=None,
        exclude=True,
        description="Callback that checks named-resource affordability.",
    )


class ActionEvent(Event):
    def harmful_direct_recipients(self) -> tuple[UUID, ...]:
        """Direct hostile recipients, excluding incidental area contact."""
        origin = self.get_effect_origin()
        if (self.event_type is EventType.ATTACK or
                origin is not None and origin.harmful and not origin.area_application):
            primary = (self.target_entity_uuid,) if self.target_entity_uuid is not None else ()
            return tuple(dict.fromkeys((*primary, *self.declared_target_entity_uuids)))
        return ()

    effect_origin: EffectOrigin | None = None

    def get_effect_origin(self) -> EffectOrigin | None:
        return self.effect_origin

    font_conversion: FontConversion | None = None
    """Event emitted by the base action pipeline."""

    action_economy_spent: bool = Field(
        default=False,
        description="Whether this action committed a positive action-economy or named-resource cost.",
    )

    behavior_id: Optional[str] = Field(
        default=None,
        description=(
            "Primitive identity of the executable rule captured before queue "
            "admission."
        ),
    )
    provided_by_id: Optional[str] = Field(
        default=None,
        description="Primitive identity of the direct semantic provider.",
    )
    origin_root_id: Optional[str] = Field(
        default=None,
        description="Optional durable primitive root of the provider chain.",
    )
    costs: List[BaseCost] = Field(default_factory=list, description="Serializable action costs.")
    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="Usable item supplying this action when execution is item-bound.",
    )
    source_item_presentation: Optional[ItemPresentationState] = Field(
        default=None,
        description=(
            "Immutable source-item snapshot captured when the action was declared; "
            "later phases and replay never need the live item registry."
        ),
    )
    item_charge_cost: int = Field(
        default=0,
        ge=0,
        description="Finite item charges consumed before this action completes.",
    )
    item_charge_action_lineage_uuid: Optional[UUID] = Field(
        default=None,
        description="Root action lineage authorized to consume the item resource once.",
    )
    presentation_kind: ActionPresentationKind = Field(
        default=ActionPresentationKind.DEFAULT,
        description="Stable presentation meaning for clients rendering this action.",
    )
    declared_target_entity_uuids: List[UUID] = Field(
        default_factory=list,
        description="Complete entity target selection captured when the action is declared.",
    )
    application: ApplicationMembership | None = None
    application_intercepted_by: UUID | None = Field(
        default=None,
        description="An owned handler resolved this accepted application instead of its authored effect.",
    )
    propagation: EffectPropagationLink | None = None

    @property
    def application_id(self) -> UUID | None:
        return self.application.application_id if self.application is not None else None

    @property
    def application_index(self) -> int | None:
        return self.application.index if self.application is not None else None

    event_type: EventType = Field(default=EventType.BASE_ACTION, description="Base action event type.")
    description: str = Field(default="", description="Action description for combat log generation")
    total_targets: int = Field(
        default=0,
        description="Number of targets affected by a multi-target or AoE action.",
    )
    total_damage: int = Field(
        default=0,
        description="Total damage dealt across all per-target child events.",
    )
    aoe_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Grid position targeted by a position-AoE action.",
    )
    resolved_area_positions: Optional[Tuple[Tuple[int, int], ...]] = Field(
        default=None,
        description="Physical cells resolved by this area's execution; None means no recorded result.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Freeze active authored identity before the event is registered."""
        if (
            __context is not PASSIVE_EVENT_REPLAY
            and self.behavior_id is None
            and self.provided_by_id is None
        ):
            binding = active_runtime_behavior_binding()
            if binding is not None:
                self.behavior_id = binding.behavior_id
                self.provided_by_id = binding.provided_by_id
                self.origin_root_id = binding.origin_root_id
        if __context is not PASSIVE_EVENT_REPLAY:
            self.resolution_ref = (ApplicationResolutionRef(
                lineage_uuid=self.application.lineage_uuid, application_id=self.application.application_id)
                if self.application is not None else EventResolutionRef(lineage_uuid=self.lineage_uuid))
        super().model_post_init(__context)

    def add_cost(self, cost: Cost) -> None:
        """Append a serializable copy of a runtime action cost.

        Args:
            cost: Runtime cost to store without executable callbacks.
        """
        base_cost = BaseCost.model_validate(cost)
        self.costs.append(base_cost)

    @classmethod
    def from_costs(
        cls,
        costs: List[Cost],
        source_entity_uuid: UUID,
        target_entity_uuid: Optional[UUID] = None,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
        source_item_uuid: Optional[UUID] = None,
        source_item_presentation: Optional[ItemPresentationState] = None,
        item_charge_cost: int = 0,
        declared_target_entity_uuids: Optional[List[UUID]] = None,
        presentation_kind: ActionPresentationKind = ActionPresentationKind.DEFAULT,
    ) -> "ActionEvent":
        """Create an action event from runtime costs.

        Args:
            costs: Runtime costs to serialize on the event.
            source_entity_uuid: Acting entity UUID.
            target_entity_uuid: Optional primary target UUID.
            parent_event: Optional parent event for event-tree nesting.
            use_register: Whether the event should be registered immediately.
            source_item_uuid: Optional usable item supplying this action.
            source_item_presentation: Declaration-time cold item snapshot.
            item_charge_cost: Finite item charges consumed on completion.
            declared_target_entity_uuids: Complete entity target selection.
            presentation_kind: Stable presentation meaning for this action.

        Returns:
            Newly created action event.
        """
        base_costs = [BaseCost.model_validate(cost) for cost in costs]
        event = cls(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=target_entity_uuid,
            costs=base_costs,
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_item_uuid=source_item_uuid,
            source_item_presentation=source_item_presentation,
            item_charge_cost=item_charge_cost,
            declared_target_entity_uuids=declared_target_entity_uuids or [],
            presentation_kind=presentation_kind,
        )
        event.item_charge_action_lineage_uuid = event.lineage_uuid
        return event

    @model_validator(mode="after")
    def validate_cold_presentation_facts(self) -> "ActionEvent":
        """Keep item and target-application identities internally coherent."""
        if self.application is not None and self.application.lineage_uuid == self.lineage_uuid:
            raise ValueError("An application must name its separate owning action lineage")
        if (self.behavior_id is None) != (self.provided_by_id is None):
            raise ValueError(
                "behavior_id and provided_by_id must be present together"
            )
        if self.behavior_id is None and self.origin_root_id is not None:
            raise ValueError("origin_root_id requires a behavior identity")
        if self.source_item_presentation is not None:
            if self.source_item_uuid is None:
                raise ValueError("source item presentation requires source_item_uuid")
            if self.source_item_presentation.item_uuid != self.source_item_uuid:
                raise ValueError("source item presentation UUID must match source_item_uuid")
        if (
            self.presentation_kind is ActionPresentationKind.DRINK
            and self.source_item_presentation is None
        ):
            raise ValueError("drink action requires a declaration-time item presentation")
        return self

    @field_validator("behavior_id", "provided_by_id", "origin_root_id")
    @classmethod
    def _validate_behavior_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, "action event behavior identity")

    def get_participant_entity_uuids(self) -> Set[UUID]:
        """Return the actor and every entity selected by the action.

        Returns:
            Direct event participants plus the declaration-time target set.
        """
        return super().get_participant_entity_uuids() | set(
            self.declared_target_entity_uuids
        )

    def get_affected_positions(self) -> Set[Tuple[int, int]]:
        """Return positions that spatial handlers should inspect for this event."""
        positions: Set[Tuple[int, int]] = set()
        if self.aoe_position:
            positions.add(self.aoe_position)
        return positions

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate a combat log entry for generic actions.

        Uses self.name and self.description. Subclasses (AttackEvent,
        MovementEvent, SpellEvent) override with specific implementations.

        For multi-target actions (total_targets > 0), generates a summary log.
        Sub-entries come from _collect_child_combat_logs() via parent_event relationship.

        Returns:
            CombatLogEntry for self-targeting actions, or None for base events.
        """
        if self.total_targets > 0:
            return self._generate_multi_target_log()

        source_name = self.source_entity_name or "Unknown"
        action_name = self.name or "Action"
        effect_desc = self.description or ""

        compact = f"{{cyan:{source_name}}} uses {{bold:{action_name}}}"
        verbose = compact + (f"\n  {effect_desc}" if effect_desc else "")
        detailed = verbose

        target_name = self.target_entity_name
        target_uuid = str(self.target_entity_uuid) if self.target_entity_uuid else None
        data = ActionLogData(
            entity_name=source_name,
            entity_uuid=str(self.source_entity_uuid),
            action_name=action_name,
            effect_description=effect_desc,
            target_name=target_name,
            target_uuid=target_uuid,
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=target_uuid,
            compact=compact,
            verbose=verbose,
            detailed=detailed,
            data=data,
            success=True
        )

    def _generate_multi_target_log(self) -> CombatLogEntry:
        """Generate summary log for multi-target actions.

        Per-target details are child event logs collected into sub-entries by
        the completion phase.

        Returns:
            Multi-entity combat-log summary.
        """
        source_name = self.source_entity_name or "Unknown"
        n_targets = self.total_targets
        total_dmg = self.total_damage or 0

        action_name = self.name or 'Action'
        if self.aoe_position:
            location = f" at ({self.aoe_position[0]}, {self.aoe_position[1]})"
        else:
            location = ""
        summary = f"{md_color(source_name, 'cyan')} uses {md_color(action_name, 'yellow')}{location} → {n_targets} targets, {md_color(str(total_dmg), 'red')} total damage"

        data = MultiEntityLogData(
            action_name=self.name or "Action",
            caster_name=source_name,
            total_targets=n_targets,
            total_damage=total_dmg,
            aoe_center=self.aoe_position
        )

        return CombatLogEntry(
            entry_type=CombatLogEntryType.MULTI_ENTITY_ACTION,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid) if self.source_entity_uuid else "",
            compact=summary,
            verbose=summary,
            detailed=summary,
            data=data,
            success=n_targets > 0
        )


def cell_occupied(scan: ActorScan, cell: Tuple[int, int]) -> bool:
    """A creature stands on the cell, as the scan's knowledge has it: perceived in discovery, actual at execution."""
    if cell == scan.position:
        return True
    if scan.subjective:
        return any(record.position == cell for record in scan.creatures.values())
    return bool(get_map().get_entities_at(cell))


class BaseAction(BaseObject):
    """Base class for executable action templates and instances.

    Actions can be created as templates (template=True) which are bound to a source entity
    with fixed configuration (e.g., weapon_slot), but without a specific target. Templates
    support pre_validate() but cannot be applied directly - use instantiate() to create
    an executable instance with a specific target.
    """

    description: str = Field(default="", description="UI and combat-log description for this action.")
    semantic_key: Optional[str] = Field(
        default=None,
        description="Optional stable policy/grouping key; never behavior provenance.",
    )
    behavior_binding: Optional[BehaviorBinding] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Validated runtime content binding installed once before this "
            "action becomes observable."
        ),
    )
    configured_action_ref: Optional[ContentRef] = Field(
        default=None,
        description=(
            "Exact authored configuration specializing a reusable action "
            "behavior. When present, this is the catalog identity of the "
            "configured affordance; behavior_binding remains the engine "
            "implementation identity."
        ),
    )
    costs: List[Cost] = Field(default_factory=list, description="Runtime costs required by this action.")
    harmful: bool | None = False
    object_target_policy: Literal["damageable", "active"] = "damageable"
    include_owned_item_targets: bool = Field(default=False,
        description="Include the actor's inventory and equipment in object selection.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Target category used by discovery and instantiation.",
    )
    template: bool = Field(
        default=False,
        description="True when this action is a reusable template instead of an executable instance.",
    )
    registered_template_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
        frozen=True,
        description="Exact Entity-owned template that produced this execution.",
    )
    include_self: bool = Field(
        default=False,
        description="Whether the acting entity can be included in this action's target set.",
    )
    entity_target_perception: EntityTargetPerception = EntityTargetPerception.PERCEIVED
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="Broad action classification used by discovery and UI layers.",
    )
    effect_origin: EffectOrigin | None = Field(default=None, description="Authored nonspell effect provenance, captured per admitted action.")
    presentation_kind: ActionPresentationKind = Field(
        default=ActionPresentationKind.DEFAULT,
        description="Stable presentation meaning copied to every action event phase.",
    )
    allow_while_incapacitated: bool = Field(
        default=False,
        description="Whether this action can be used while the source cannot take actions.",
    )
    # Only an action whose costs depend on its selected target (Jump) needs
    # its costs checked per discovery candidate.
    target_dependent_costs: ClassVar[bool] = False
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default=None,
        description="Typed subjective candidate contract for plain position actions.",
    )
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset()
    )
    # Whether a restricted grant (Haste) may pay for this action's ordinary channel.
    restricted_budget_eligible: ClassVar[bool] = True
    _restricted_action_grant: Optional[RestrictedActionGrant] = PrivateAttr(
        default=None,
    )
    _source_item_controller_uuid: Optional[UUID] = PrivateAttr(default=None)
    _selected_facets: Tuple[ActionVariantFacet, ...] = PrivateAttr(default=())

    def get_attack_source_metadata(self) -> Optional[AttackSourceMetadata]:
        return None


    @property
    def is_attack(self) -> bool:
        """Whether this action is categorized as an attack."""
        return self.action_category == ActionCategory.ATTACK

    @property
    def performs_attack(self) -> bool:
        """Selection metadata only; does not grant costs or target permissions."""
        return self.is_attack

    @property
    def is_spell(self) -> bool:
        """Whether this action is categorized as a spell."""
        return self.action_category == ActionCategory.SPELL

    @property
    def is_movement(self) -> bool:
        """Whether this action is categorized as movement."""
        return self.action_category == ActionCategory.MOVEMENT

    def get_semantic_key(self) -> str:
        """Return the rules-family key used by mechanics and policy.

        Authored catalog identity is carried separately by
        ``behavior_binding``.  Keeping the two axes independent prevents
        content attribution from changing action dispatch or AI policy.
        """
        if self.semantic_key is not None:
            return self.semantic_key
        action_class = type(self)
        return f"{action_class.__module__}.{action_class.__qualname__}"

    def get_outcome_profile(self) -> Optional[ActionOutcomeProfile]:
        """Return actor-known stochastic action data when the rule defines it.

        Returns:
            Actor-baseline outcome profile, or ``None`` when the action has not
            declared enough rule data for quantitative policy reasoning.
        """
        return None

    def get_conditional_runtime_costs(self) -> list[Cost]:
        """Authored hit costs participate in native affordability, not upfront payment."""
        return []

    def get_conditional_costs(self) -> tuple[ConditionalCost,...]:
        return tuple(ConditionalCost.model_validate(cost.model_dump()) for cost in self.get_conditional_runtime_costs())

    def get_fixed_healing(self) -> Optional[int]:
        """Return deterministic healing disclosed by this action rule.

        Returns:
            Fixed hit points restored per execution, or ``None`` when healing
            is absent or determined by another outcome model.
        """
        return None

    def get_self_setup_profile(self) -> Optional[ActionSelfSetupProfile]:
        """Return the action's dependency-neutral self-setup annotation.

        Returns:
            Logical setup profile, or ``None`` when the action declares no
            self-directed combat setup.
        """
        return None

    def get_target_effect_profile(self) -> Optional[ActionTargetEffectProfile]:
        """Return conditional effects the rule applies to selected targets.

        Returns:
            Typed target-effect profile, or ``None`` when the action has not
            declared target-conditional rule effects.
        """
        return None

    def get_world_effect_profile(self) -> Optional[ActionWorldEffectProfile]:
        """Return information or topology effects declared by the action rule.

        Returns:
            Typed world-effect profile, or ``None`` when the action does not
            change information or topology.
        """
        return None

    source_item_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the item providing this action when it is an item-use action.",
    )
    source_item_presentation: Optional[ItemPresentationState] = Field(
        default=None,
        description="Cold source-item state bound before an item action is declared.",
    )
    charge_cost: int = Field(default=1, description="Charges consumed when this action is used from an item")
    end_position: Optional[Tuple[int, int]] = Field(
        default=None,
        description="Grid position selected for position-targeted actions.",
    )
    extra_target_positions: List[Tuple[int, int]] = Field(
        default_factory=list, description="Ordered additional positions for path selection.",
    )
    discovery_target_types: tuple[TargetType,...] = ()

    position_selection: Optional[PositionSelection] = Field(
        default=None, description="Authored position selection arity and span limit.",
    )
    interaction_affordance: ActionAffordance = Field(default_factory=ActionAffordance)
    aoe_shape: Optional[AoEShape] = Field(
        default=None,
        description="Shape template used to resolve affected cells and entities for AoE actions.",
    )
    extra_target_entity_uuids: List[UUID] = Field(
        default_factory=list,
        description="Additional target UUIDs beyond the primary target for multi-entity actions.",
    )
    allow_same_target: bool = Field(
        default=True,
        description="Whether a multi-entity action can target the same entity more than once.",
    )
    multi_target_objects: bool = False
    valid_target_filter: str = Field(
        default="enemies",
        description="Entity relationship filter: enemies, allies, self_or_allies, or all.",
    )
    include_dead: bool = Field(
        default=False,
        description="Whether dead entities remain eligible targets.",
    )
    aoe_require_targets: bool = Field(
        default=True,
        description="Whether AoE discovery requires at least one affected entity before exposing a position.",
    )
    requires_concentration: bool = Field(
        default=False,
        description="Whether preterminal action settlement invokes concentration cleanup.",
    )
    alt_cost_type: Optional[str] = Field(default=None, description="Temporary replacement for primary action cost type.")
    alt_extra_costs: List[Cost] = Field(default_factory=list, description="Temporary additional costs.")
    alt_target_type: Optional[TargetType] = Field(default=None, description="Temporary replacement target type.")
    alt_target_count: Optional[int] = Field(default=None, description="Temporary multi-target count override.")
    alt_skip_slot: bool = Field(default=False, description="Whether temporary overrides skip spell-slot costs.")

    # Compile a behavior's validation schema when it is first used, not merely
    # because the built-in catalog imports its definition.
    model_config = ConfigDict(arbitrary_types_allowed=True, defer_build=True)

    def model_post_init(self, __context: Any) -> None:
        """Capture an item source before the action can outlive that item."""
        if (
            self.source_item_uuid is not None
            and self.source_item_presentation is None
        ):
            source_item = BaseBlock.get(self.source_item_uuid)
            if isinstance(source_item, ItemPresentationProvider):
                self.source_item_presentation = (
                    source_item.to_item_presentation_state()
                )
        super().model_post_init(__context)

    @property
    def effective_target_type(self) -> TargetType:
        """Target type with alt override applied."""
        return self.alt_target_type if self.alt_target_type is not None else self.target_type

    def get_source_dynamic_costs(self) -> List["Cost"]:
        """Resolve source-state-dependent costs owned by this action.

        Static costs remain in ``costs``. Subclasses override this hook only
        when the exact typed cost depends on the acting entity but not on a
        selected target. These costs participate in authored-row affordability
        as well as execution.
        """
        return []

    def get_target_dynamic_costs(self) -> List["Cost"]:
        """Resolve costs that require an explicitly selected target.

        Discovery evaluates these costs only on a target-specialized copy.
        Target-independent authored-row affordability must never read this
        hook, because a reusable template may retain a prior selected target.
        """
        return []

    def _transform_costs(self, base_costs: Sequence["Cost"]) -> List["Cost"]:
        """Apply temporary overrides and restricted grants to one cost set."""
        costs = list(base_costs)
        if self.alt_cost_type is not None:
            costs = [
                cost.model_copy(update={"cost_type": self.alt_cost_type})
                if cost.cost_type == "actions"
                else cost
                for cost in costs
            ]
        if self.alt_skip_slot:
            costs = [
                cost
                for cost in costs
                if not cost.cost_type.startswith("spell_slot")
            ]
        costs.extend(self.alt_extra_costs)
        grant = self._restricted_action_grant
        if grant is None:
            return costs

        transformed_costs: List["Cost"] = []
        grant_bound = False
        for cost in costs:
            if (
                not grant_bound
                and cost.cost_type in grant.replaced_cost_types
                and cost.cost > 0
                and cost.resource_name is None
                and cost.resource_cost == 0
            ):
                transformed_costs.append(
                    cost.model_copy(
                        update={
                            "cost": 0,
                            "resource_name": grant.resource_name,
                            "resource_cost": 1,
                            "resource_evaluator": (
                                block_action_resource_cost_evaluator
                            ),
                        }
                    )
                )
                grant_bound = True
            else:
                transformed_costs.append(cost)
        if not grant_bound:
            raise ValueError(
                f"{self.name or 'action'} cannot bind restricted grant "
                f"{grant.grant_id!r}"
            )
        return transformed_costs

    @property
    def target_independent_effective_costs(self) -> List["Cost"]:
        """Return exact source-owned costs without selected-target costs."""
        return self._transform_costs(
            [*self.costs, *self.get_source_dynamic_costs()]
        )

    @property
    def effective_costs(self) -> List["Cost"]:
        """Build source and selected-target costs with all active transforms."""
        return self._transform_costs(
            [
                *self.costs,
                *self.get_source_dynamic_costs(),
                *self.get_target_dynamic_costs(),
            ]
        )

    def set_target_entity(self, target_uuid: UUID) -> None:
        """Set target entity for ENTITY, MULTI_ENTITY, or OBJECT type actions.

        Used with templates to set the target before pre_validate() or instantiate().
        For MULTI_ENTITY, this sets the primary target.
        For OBJECT, this sets the item UUID (items are BaseBlocks in _registry).
        """
        if self.effective_target_type not in (TargetType.ENTITY, TargetType.MULTI_ENTITY, TargetType.CREATURE_OR_OBJECT, TargetType.OBJECT):
            raise ValueError(f"Action {self.name} doesn't target entities (target_type={self.effective_target_type})")
        self.target_entity_uuid = target_uuid

    def set_target_position(self, position: Tuple[int, int]) -> None:
        """Set target position for POSITION type actions.

        Used with templates to set the target before pre_validate() or instantiate().
        Supports POSITION, POSITION_PATH, POSITION_LOS, and POSITION_AOE target types.
        """
        if self.effective_target_type not in (TargetType.POSITION, TargetType.POSITION_PATH, TargetType.POSITION_LOS, TargetType.POSITION_AOE):
            raise ValueError(f"Action {self.name} doesn't target positions (target_type={self.effective_target_type})")
        self.end_position = position

    def get_effect_origin_for_preview(self) -> EffectOrigin | None:
        """Factual authored provenance without constructing an execution event."""
        return self.effect_origin

    def get_range(self) -> Optional[Range]:
        """Get the range of this action.

        Override in subclasses to provide dynamic range calculation.
        Returns Range object with type/normal/long, or None if unlimited.

        For actions with dynamic range (like Jump), override this method.
        """
        return None

    def get_target_origin(self) -> Optional[Tuple[int, int]]:
        """Return the grid origin used to measure this action's target range."""
        source = BaseBlock.get(self.source_entity_uuid)
        return source.position if source is not None else None

    def get_target_distance(self, position: Tuple[int, int]) -> int:
        """Measure target distance using the same origin as target validation."""
        origin = self.get_target_origin()
        if origin is None:
            raise ValueError("Action has no placed targeting origin")
        return grid_distance_feet(origin, position)

    def target_position_error(self, position: Tuple[int, int]) -> Optional[str]:
        """Return a range error for one candidate, independently of perception."""
        if self.get_target_origin() is None:
            return "Action has no placed targeting origin"
        action_range = self.get_range()
        if action_range is not None and action_range.normal > 0:
            distance = self.get_target_distance(position)
            if distance > action_range.normal:
                return f"Target out of range ({distance}ft > {action_range.normal}ft)"
        return None

    def get_physical_access(self) -> Optional[PhysicalAccess]:
        """Physical delivery of primary targets; absent for remote/noncontact actions."""
        return None

    def target_access_error(self, target_uuid: UUID) -> Optional[str]:
        """Physical access to one target mid-resolution, after its position may have changed."""
        source = BaseBlock.get(self.source_entity_uuid)
        if source is None:
            return "Action origin is not placed"
        return self._physical_access_error(source.action_scan(subjective=False),
            replace(self.current_selection(), target_uuids=(target_uuid,)))

    def _physical_access_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        access = self.get_physical_access()
        if access is None:
            return None
        origin = self.get_target_origin()
        if origin is None:
            return "Action origin is not placed"
        grid = get_map()
        primary = selection.target_uuids[0] if selection.target_uuids else None
        if primary is not None and primary in scan.carried_items:
            return None  # An item the actor carries is always within its reach.
        if self.effective_target_type is TargetType.OBJECT:
            if primary is not None and grid.manual_object_contact(
                self.source_entity_uuid, primary,
                access=access, subjective=scan.subjective,
            ) is None:
                return "Object is out of physical reach"
            return None
        if self.effective_target_type is TargetType.CREATURE_OR_OBJECT:
            identity = primary
            if identity is not None and grid.get_object_placement(identity) is not None:
                action_range = self.get_range()
                limit = (action_range.long or action_range.normal) if action_range else 5
                if grid.attack_object_contact(self.source_entity_uuid, identity,
                        range_feet=limit, access=access, subjective=scan.subjective,
                        origin=origin) is None:
                    return "Object is out of physical reach"
                return None
        if self.effective_target_type in (TargetType.ENTITY, TargetType.MULTI_ENTITY, TargetType.CREATURE_OR_OBJECT):
            targets = [target for identity in self._selection_targets(selection)
                       if (target := BaseBlock.get(identity)) is not None]
            if not self.is_spell and any(target.uuid != self.source_entity_uuid and any(
                    condition.blocks_external_contact and condition.contributions_active()
                    for condition in target.active_conditions_by_uuid.values()) for target in targets):
                return "An active boundary prevents physical contact"
            positions = [target.position for target in targets]
        elif self.effective_target_type in (TargetType.POSITION, TargetType.POSITION_LOS,
                                           TargetType.POSITION_PATH, TargetType.POSITION_AOE):
            positions = list(selection.positions)
        else:
            positions = []
        for position in positions:
            if not grid.can_reach_between(origin, position, access,
                    self.source_entity_uuid, subjective=scan.subjective):
                return "A physical barrier blocks this action"
        return None

    def get_position_selection(self) -> Optional[PositionSelection]:
        """Selection requirements of this exact authored action variant."""
        return self.position_selection

    def get_selected_position_path(self) -> Optional[List[Tuple[int, int]]]:
        """Resolve explicit vertices, or one point measured from the targeting origin."""
        return self._selected_position_path(self.current_selection())

    def _selected_position_path(self, chosen: ActionSelection) -> Optional[List[Tuple[int, int]]]:
        selection = self.get_position_selection()
        if selection is None or selection.kind != "path" or not chosen.positions:
            return None
        end_position, *extra = chosen.positions
        if extra:
            return [end_position, *extra]
        origin = self.get_target_origin()
        if selection.allow_origin_start and origin is not None:
            ray = bresenham_line(origin, end_position)
            if len(ray) <= selection.origin_start_offset_cells:
                return None
            return [ray[selection.origin_start_offset_cells], end_position]
        return None

    def position_selection_error(self) -> Optional[str]:
        """Validate actual submitted positions before action-specific rules or costs."""
        return self._position_selection_error(self.current_selection())

    def _position_selection_error(self, chosen: ActionSelection) -> Optional[str]:
        selection = self.get_position_selection()
        extra_positions = chosen.positions[1:]
        if selection is None or selection.kind == "single":
            return "This action does not select additional positions" if extra_positions else None
        if selection.kind == "entity_destination":
            if self.effective_target_type is not TargetType.ENTITY:
                return "Creature and destination selection requires entity targeting"
            if not chosen.target_uuids or not chosen.positions:
                return "Choose a creature and a destination"
            if extra_positions:
                return "Choose exactly one destination"
            return self.target_position_error(chosen.positions[0])
        if self.effective_target_type != TargetType.POSITION_LOS:
            return "Path selection requires position targeting"
        path = self._selected_position_path(chosen)
        if path is None:
            return "Select the path endpoints"
        if len(path) - 1 > selection.max_segments:
            return f"This action permits at most {selection.max_segments} segments"
        lengths = [hypot(end[0] - start[0], end[1] - start[1]) * 5
                   for start, end in zip(path, path[1:])]
        if any(length == 0 for length in lengths) or sum(lengths) > selection.max_length_feet:
            return f"Path length must be positive and at most {selection.max_length_feet:g} feet"
        source = BaseBlock.get(self.source_entity_uuid)
        senses = source.get_senses() if source is not None else None
        for position in path:
            error = self.target_position_error(position)
            if error is not None:
                return error
            if senses is None or not senses.visible.get(position, False):
                return "Path position is not visible"
        return None

    def handler_admission_error(self, *, subjective: bool) -> Optional[str]:
        """Admission decided by handlers (a preflight event), after every requirement.

        Only the named handler-admission actions override it (plan §14.3b);
        discovery never runs it, preview and Command do.
        """
        return None

    def get_valid_extra_target_positions(
        self, start: Tuple[int, int], selected: Sequence[Tuple[int, int]] = (),
    ) -> List[Tuple[int, int]]:
        """The next vertex, or the destination for this instance's creature, the actor may add.

        Each candidate is checked by the one admission path on the actor's
        perceived scan (plan §14.3b), without a copy or an event.
        """
        selection = self.get_position_selection()
        source = BaseBlock.get(self.source_entity_uuid)
        if source is None or selection is None:
            return []
        scan = source.action_scan(subjective=True)
        base = self.current_selection()
        if selection.kind == "entity_destination":
            if selected or not base.target_uuids:
                return []
            candidates = [replace(base, positions=(position,)) for position in self.get_valid_positions()]
        elif selection.kind == "path" and len(selected) < selection.max_segments:
            candidates = [replace(base, positions=(start, *selected, position)) for position in self.get_valid_positions()]
        else:
            return []
        return [candidate.positions[-1] for candidate in candidates if self.requirements_error(scan, candidate) is None]

    def source_item_error(self, *, subjective: bool = False) -> Optional[str]:
        """Admission check; accepted last-charge effects may outlive their item."""
        if self.source_item_uuid is None:
            return None
        item = BaseBlock.get(self.source_item_uuid)
        if item is None or not item.is_active:
            return "Source item is no longer active"
        return self.source_item_contact_error(subjective=subjective)

    def source_item_contact_error(self, *, subjective: bool = False) -> Optional[str]:
        if self.source_item_uuid is None:
            return None
        source_item=BaseBlock.get(self.source_item_uuid)
        if source_item is None:
            return "Source item is no longer present"
        if isinstance(source_item, FiniteChargeProvider):
            if (error := source_item.use_admission_error(self.source_entity_uuid)) is not None:
                return error
        grid = get_map()
        contact_uuid = self.source_item_uuid
        if self._source_item_controller_uuid is not None:
            controller = BaseBlock.get(self._source_item_controller_uuid)
            link = controller.get_item_control_link() if controller is not None else None
            if (controller is None or not controller.is_active
                    or link is None or link.target_item_uuid != self.source_item_uuid
                    or grid.get_object_placement(controller.uuid) is None
                    or grid.get_object_placement(self.source_item_uuid) is None):
                return "Source item control link is unavailable"
            contact_uuid = controller.uuid
        if grid.get_object_placement(contact_uuid) is not None and grid.manual_object_contact(
            self.source_entity_uuid, contact_uuid, subjective=subjective,
        ) is None:
            return "Source item is out of physical reach"
        return None

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Get valid target positions for POSITION_LOS and POSITION_AOE actions.

        Override in subclasses to provide custom position filtering.
        Default implementation uses senses.visible + get_range().

        Returns:
            List of valid positions this action can target.
        """
        selection = self.get_position_selection()
        if (self.effective_target_type not in (TargetType.POSITION_LOS, TargetType.POSITION_AOE)
                and (selection is None or selection.kind != "entity_destination")):
            return []

        entity = BaseBlock.get(self.source_entity_uuid)
        if entity is None:
            return []

        senses_block = entity.get_senses()
        if not isinstance(senses_block, Senses):
            return []

        valid: List[Tuple[int, int]] = []
        visible = senses_block.visible
        position = senses_block.position
        selection = self.get_position_selection()

        if not visible:
            return []

        for pos, is_visible in visible.items():
            if not is_visible:
                continue
            if pos == position and (selection is None or selection.kind != "path"):
                continue
            if self.target_position_error(pos) is not None:
                continue
            valid.append(pos)
        return valid

    def get_disclosed_movement_path(
        self,
        start_position: Tuple[int, int],
        end_position: Tuple[int, int],
    ) -> Optional[List[Tuple[int, int]]]:
        """Return the subjectively knowable cells traversed by this action.

        Movement actions with deterministic traversal should override this
        method with the same route construction used during execution.
        Teleports and nonmovement actions return no traversed path.

        Args:
            start_position: Actor position before the action.
            end_position: Candidate destination exposed by discovery.

        Returns:
            Ordered inclusive traversal path, or `None` when the action does
            not disclose intermediate movement.
        """
        return None

    def get_movement_mode(self) -> MovementMode:
        return MovementMode.WALKING

    def get_allocation_completion(self) -> Literal["selected_only", "fill_primary"]:
        """How the native action resolves an incomplete recipient allocation."""
        return "selected_only"

    def get_connector_traversal_discovery(self) -> Optional[ConnectorTraversalDiscovery]:
        return None

    def get_selection_geometry(self) -> AoEPresentationGeometry | None:
        return None

    def get_multi_target_count(self) -> Optional[int]:
        """Get the number of targets/projectiles for MULTI_ENTITY actions.

        Returns None for non-MULTI_ENTITY actions.
        Returns 1 as default for MULTI_ENTITY actions.
        Alt override takes priority when set.
        Subclasses override to return their specific count.
        """
        if self.alt_target_count is not None:
            return self.alt_target_count
        if self.effective_target_type != TargetType.MULTI_ENTITY:
            return None
        return 1

    def get_application_propagation(self, target_uuid: UUID,
                                    membership: ApplicationMembership) -> EffectPropagationLink | None:
        return None

    def get_all_targets(self) -> List[UUID]:
        """Get all target UUIDs for multi-target actions.

        Position AoE actions compute targets from their shape and end position.
        Multi-entity actions return the primary target followed by extra targets.
        Subclasses may override this to provide custom target resolution.

        Returns:
            Target UUIDs in processing order.
        """
        if self.effective_target_type == TargetType.POSITION_AOE:
            targets, _ = self._resolve_area_targets()
            return targets

        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)
        return targets

    def _resolve_area_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        """Resolve one native area and its eligible occupants from the same shape."""
        if self.end_position is None:
            return [], None
        return self._area_targets_at(self.end_position)

    def _area_targets_at(self, aim: Tuple[int, int]) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        """The area's eligible occupants and footprint at one aim."""
        if self.aoe_shape is None:
            return [], None
        source_block = BaseBlock.get(self.source_entity_uuid)
        if source_block is None:
            return [], None
        footprint = objective_footprint(self.aoe_shape, aim, source_block.position)
        grid = get_map()
        targets = sorted({identity for cell in footprint for identity in grid.get_entities_at(cell)},
            key=target_resolution_sort_key)
        if not self.include_self:
            targets = [uid for uid in targets if uid != self.source_entity_uuid]
        targets = self._filter_targets_by_faction(source_block, targets)
        if not self.include_dead:
            targets = [uid for uid in targets if (block := BaseBlock.get(uid)) and block.is_active]
        return targets, tuple(sorted(footprint))

    def _resolve_execution_targets(self) -> Tuple[List[UUID], Optional[Tuple[Tuple[int, int], ...]]]:
        """Preserve authored target selection unless the action also records its area."""
        return self.get_all_targets(), None

    def _filter_targets_by_faction(self, source_block: BaseBlock, targets: List[UUID]) -> List[UUID]:
        """Filter targets based on valid_target_filter for AoE spells.

        Args:
            source_block: Block that owns the action.
            targets: Candidate target UUIDs.

        Returns:
            Candidate targets that match this action's relationship filter.
        """
        if self.valid_target_filter == "all":
            return targets

        source_faction = source_block.faction

        filtered: List[UUID] = []
        for target_uuid in targets:
            target = BaseBlock.get(target_uuid)
            if target is None:
                continue

            same = target_uuid == self.source_entity_uuid
            ally = same or (source_faction is not None and target.faction is not None and source_faction == target.faction)
            enemy = not same and (source_faction is None or target.faction is None or source_faction != target.faction)

            if self.valid_target_filter == "enemies":
                if enemy:
                    filtered.append(target_uuid)
            elif self.valid_target_filter == "allies":
                if not same and ally:
                    filtered.append(target_uuid)
            elif self.valid_target_filter == "self_or_allies":
                if ally:
                    filtered.append(target_uuid)
            else:
                filtered.append(target_uuid)

        return filtered

    def admits_touch_target(self, target_uuid: UUID) -> bool:
        """Admit nearby physical contact without granting sight or hidden identities.

        Contact is physical: the toucher feels a real barrier even when it is
        unseen, so barriers are read from the world in discovery too.
        """
        source = BaseBlock.get(self.source_entity_uuid)
        target = BaseBlock.get(target_uuid)
        grid = get_map()
        if source is None or target is None or not target.is_active:
            return False
        position = grid.get_entity_position(target_uuid)
        source_position = grid.get_entity_position(self.source_entity_uuid)
        origin = self.get_target_origin()
        if position is None or origin is None or source_position is None:
            return False
        if self.target_position_error(position) is not None:
            return False
        if source.get_occupancy_layer() != target.get_occupancy_layer():
            return False
        if not grid.can_reach_between(origin, position, PhysicalAccess.HAND, source.uuid):
            return False
        if target_uuid == source.uuid:
            return True
        if not target.is_observable_to(source.uuid):
            return False
        if target.stealth_dc is not None and target.stealth_dc >= source.get_passive_perception():
            return False
        senses = source.get_senses()
        if senses is not None and target_uuid in senses.entities:
            return True
        return (not target.is_invisible
                and grid_distance_feet(source_position, position) <= 5
                and grid.can_reach_between(source_position, position, PhysicalAccess.HAND, source.uuid))

    def get_additional_target_candidates(self) -> Dict[UUID, Tuple[int,int]]:
        """Explicit authored known recipients outside the ordinary contact pool."""
        return {}

    def get_touch_target_candidates(self) -> Dict[UUID, Tuple[int, int]]:
        """Enumerate only local contact candidates; leave perceived pools unchanged."""
        if self.entity_target_perception is not EntityTargetPerception.TOUCH_CONTACT:
            return {}
        grid = get_map()
        origin = grid.get_entity_position(self.source_entity_uuid)
        if origin is None:
            return {}
        candidates: Dict[UUID, Tuple[int, int]] = {}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                position = (origin[0] + dx, origin[1] + dy)
                for target_uuid in sorted(grid.get_entities_at(position), key=str):
                    if self.admits_touch_target(target_uuid):
                        candidates[target_uuid] = position
        return candidates

    def _target_filter_error(self, scan: ActorScan, targets: List[UUID]) -> Optional[str]:
        """Perception and the relationship filter, read from the actor scan."""
        if self.effective_target_type == TargetType.POSITION_AOE:
            return None
        admits_objects = (self.effective_target_type is TargetType.CREATURE_OR_OBJECT
                          or (self.effective_target_type is TargetType.MULTI_ENTITY and self.multi_target_objects))
        for target_uuid in targets:
            if (target_uuid != self.source_entity_uuid and target_uuid not in scan.creatures
                    and not (admits_objects and target_uuid in scan.objects)
                    and not (self.entity_target_perception is EntityTargetPerception.TOUCH_CONTACT
                             and self.admits_touch_target(target_uuid))):
                target = BaseBlock.get(target_uuid)
                return f"{target.name if target else target_uuid} is not visible"
        source = BaseBlock.get(self.source_entity_uuid)
        if source is None:
            return "Source entity not found"
        for target_uuid in targets:
            target = BaseBlock.get(target_uuid)
            if target is None:
                return f"Target {target_uuid} not found"
            kind = relationship(source.uuid, source.faction, target_uuid, target.faction)
            if self.valid_target_filter == "enemies" and kind is not Relationship.ENEMY:
                return f"{target.name} is not an enemy"
            if self.valid_target_filter == "allies" and kind is not Relationship.ALLY:
                return f"{target.name} is not an ally"
            if self.valid_target_filter == "self_or_allies" and kind is Relationship.ENEMY:
                return f"{target.name} is not self or an ally"
        return None

    def with_selection(self, selection: ActionSelection) -> "BaseAction":
        """The executable instance of this action for one exact selection (plan §14.4b).

        An executable instance is its own selection: given exactly that, it is
        itself. Otherwise a new instance, sharing nothing with this action,
        carries the selection's targets, positions, source item, payment,
        controller and authored choices.
        """
        if not self.template and selection == self.current_selection():
            return self
        return self._bound(selection, executable=True)

    def _bound(self, selection: ActionSelection, *, executable: bool) -> "BaseAction":
        """This action bound to one selection: an executable copy, or a read-only discovery form.

        A discovery form shares the definition graph with the registered
        action (only discovery reads it); executing it binds a deep copy.
        """
        if selection.template_uuid != (self.registered_template_uuid or self.uuid):
            raise ValueError(f"The selection names another action than {self.name}")
        grant = None
        if selection.cost_source.restricted_grant_id is not None:
            source = BaseBlock.get(self.source_entity_uuid)
            grant = next((grant for grant in source.get_restricted_action_grants()
                          if grant.grant_id == selection.cost_source.restricted_grant_id), None) if source else None
            if grant is None:
                raise ValueError("The selected restricted action grant is not available")
        overrides = self._selection_overrides(selection)
        instance = (self.instantiate(**overrides) if executable else self.model_copy(update={
            **overrides, "uuid": uuid4(), "template": False, "use_register": False,
            "registered_template_uuid": self.registered_template_uuid or self.uuid}))
        instance._restricted_action_grant = grant
        instance._selected_facets = selection.facets
        instance._source_item_controller_uuid = selection.controller_uuid
        return instance

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        """The executable fields one selection sets.

        Spells add their level and payment; an action with authored choices
        (`facet_domain`) adds the fields its facets name.
        """
        targets, positions = selection.target_uuids, selection.positions
        overrides: dict = {
            "target_entity_uuid": targets[0] if targets else None,
            "extra_target_entity_uuids": list(targets[1:]),
            "end_position": positions[0] if positions else None,
            "extra_target_positions": list(positions[1:]),
        }
        if selection.source_item_uuid is not None:
            overrides["source_item_uuid"] = selection.source_item_uuid
        return overrides

    @final
    def _admission_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """The checks every action shares, then the action's own rule (plan §14.3b).

        Targets and positions come only from ``selection``: discovery checks a
        candidate against the registered template itself, without a copy, and
        nothing here declares an event.
        """
        if not self.contributions_active():
            return "This granted action's owner is suppressed or absent"
        targets = self._selection_targets(selection)
        position = selection.positions[0] if selection.positions else None
        error = (self._family_admission_error(scan, selection)
            or self._source_condition_error(targets, position)
            or self._position_selection_error(selection)
            or self.source_item_error(subjective=scan.subjective)
            or self._recipient_error(scan, targets))
        return error if error is not None else self.rule_error(scan, selection)

    def _family_admission_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """A check one action family shares (a spell's entitlement, origin and firing sector).

        Only family base classes override it; a concrete action states its own
        rule in `rule_error`.
        """
        return None

    @final
    def discovery_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Discovery's admission of one candidate: the shared path plus physical access, without a copy or an event.

        A creature-and-destination action lists a creature when one of its
        destinations (plan §14.1) passes the rule; the first that does ends the
        check.
        """
        position_selection = self.get_position_selection()
        if (position_selection is not None and position_selection.kind == "entity_destination"
                and not selection.positions):
            error: Optional[str] = "No open destination"
            for destination in self.relocation_destinations(scan, selection):
                error = self.requirements_error(scan, replace(selection, positions=(destination,)))
                if error is None:
                    break
            return error
        return self.requirements_error(scan, selection)

    @final
    def requirements_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """Every non-cost requirement of one selection: shared admission, the action's rule, physical access.

        The scan's knowledge decides what is read: perception in discovery, the world at execution.
        """
        return self._admission_error(scan, selection) or self._physical_access_error(scan, selection)

    def relocation_destinations(self, scan: ActorScan, selection: ActionSelection) -> Tuple[Tuple[int, int], ...]:
        """Destinations a relocation may choose: seen, unoccupied and in range (plan §14.1).

        An action measuring its destination from somewhere else than its own
        origin (Telekinesis: from the moved creature) narrows this domain.
        """
        return tuple(sorted(cell for cell in scan.visible
                            if not cell_occupied(scan, cell) and self.target_position_error(cell) is None))

    def _selection_targets(self, selection: ActionSelection) -> List[UUID]:
        """The recipients a selection names; an area names none (its footprint resolves them at execution)."""
        if self.effective_target_type is TargetType.SELF:
            return [self.source_entity_uuid]
        if self.effective_target_type is TargetType.POSITION_AOE:
            return []
        return list(selection.target_uuids)

    def _recipient_error(self, scan: ActorScan, targets: Sequence[UUID]) -> Optional[str]:
        """Touch contact, duplicates, perception and the relationship filter for named recipients."""
        effective_tt = self.effective_target_type
        if self.entity_target_perception is EntityTargetPerception.TOUCH_CONTACT:
            if effective_tt not in (TargetType.SELF, TargetType.ENTITY, TargetType.MULTI_ENTITY) or not targets:
                return "Touch contact requires entity targets"
            if any(not self.admits_touch_target(target) for target in targets):
                return "Target is not within physical touch contact"
        elif effective_tt is TargetType.MULTI_ENTITY and not targets:
            return "No targets specified"
        if effective_tt is TargetType.MULTI_ENTITY and not self.allow_same_target and len(set(targets)) != len(targets):
            return "This action cannot target the same entity multiple times"
        if effective_tt in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE) or (
                self.entity_target_perception is EntityTargetPerception.TOUCH_CONTACT):
            return self._target_filter_error(scan, list(targets))
        return None

    def current_selection(self) -> ActionSelection:
        """This executable instance's own choice, read from the fields `with_selection` set."""
        targets = ((self.target_entity_uuid,) if self.target_entity_uuid is not None else ()) + tuple(
            self.extra_target_entity_uuids)
        positions = ((self.end_position,) if self.end_position is not None else ()) + tuple(self.extra_target_positions)
        grant = self._restricted_action_grant
        return ActionSelection(template_uuid=self.registered_template_uuid or self.uuid, target_uuids=targets,
            positions=positions, source_item_uuid=self.source_item_uuid, facets=self._selected_facets,
            controller_uuid=self._source_item_controller_uuid,
            cost_source=CostSource(restricted_grant_id=grant.grant_id if grant is not None else None))

    def position_region(self) -> Optional[PositionRegion]:
        """The free-aim region of a position action, from its discovery contract and range."""
        if self.effective_target_type not in (TargetType.POSITION, TargetType.POSITION_LOS, TargetType.POSITION_AOE):
            return None
        contract = self.position_discovery or PositionDiscoveryContract()
        action_range = self.get_range()
        return PositionRegion(
            range_feet=action_range.normal if action_range is not None and action_range.normal > 0 else None,
            candidate_source=contract.candidate_source,
            requires_unoccupied=contract.requires_subjective_unoccupied,
            requires_walkable=contract.requires_subjective_walkable,
            requires_axis_or_diagonal_alignment=contract.requires_axis_or_diagonal_alignment,
            exclude_source_position=contract.exclude_source_position,
        )

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        """This action's own admission rule, after the shared checks (plan §14.3b).

        Overrides read targets and positions only from ``selection`` and keep
        full world access; they never copy the action, declare an event or
        mutate anything, and they do not call ``super()``.
        """
        return None

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        """The authored choices open at one level, for one target when they depend on it (plan §14.4).

        Each entry is one complete choice; `((),)` is an action without
        choices and `()` an action with none open now. The facet values map
        to fields in `_selection_overrides`.
        """
        return ((),)

    def discovery_selections(self, scan: ActorScan) -> Tuple[ActionSelection, ...]:
        """The selections this registered action lists before its choices and restricted grants.

        Its own selection; a spell lists one per castable payment (plan D17),
        a per-item or per-connector action one per item or connector.
        """
        return (self.current_selection(),)

    @final
    def discovery_forms(self, scan: ActorScan) -> List["BaseAction"]:
        """This registered action's discovery rows, one read-only form each (plan §14.4).

        Each listed selection, with each authored choice, at the ordinary costs
        and then at each restricted grant that can pay for it. A form is the
        action itself when the row is its own selection; nothing is copied for
        a candidate target.
        """
        forms: List[BaseAction] = []
        for listed in self.discovery_selections(scan):
            domain = self.facet_domain(scan, listed.cast_at_level, None)
            ordinary = [self._discovery_form(replace(listed, facets=facets)) for facets in domain]
            forms.extend(ordinary)
            if not ordinary:
                continue
            for grant in ordinary[0]._eligible_restricted_grants(scan):
                paid = replace(listed.cost_source, restricted_grant_id=grant.grant_id)
                forms.extend(self._discovery_form(replace(listed, cost_source=paid, facets=facets))
                             for facets in domain)
        return forms

    def _discovery_form(self, selection: ActionSelection) -> "BaseAction":
        return self if selection == self.current_selection() else self._bound(selection, executable=False)

    def _eligible_restricted_grants(self, scan: ActorScan) -> Tuple[RestrictedActionGrant, ...]:
        """The actor's restricted grants that may pay for this form's ordinary action channel."""
        if self._restricted_action_grant is not None or not self.restricted_budget_eligible:
            return ()
        ordinary = [cost for cost in self.target_independent_effective_costs
                    if cost.cost > 0 and cost.resource_name is None and cost.resource_cost == 0]
        eligible_kinds = set(self.restricted_action_kinds)
        if any(cost.cost_type == "actions" for cost in ordinary):
            eligible_kinds.add(RestrictedActionKind.STANDARD_ACTION)
        return tuple(grant for grant in scan.restricted_grants
                     if not eligible_kinds.isdisjoint(grant.allowed_kinds)
                     and any(cost.cost_type in grant.replaced_cost_types for cost in ordinary))

    def instantiate(self, **overrides) -> "BaseAction":
        """A new executable copy of this action with fields overridden.

        Uses model_copy() to preserve object types (e.g., AoE shape subclasses).
        Instances are not registered (ephemeral, used once for apply()); they
        keep the registered action they come from.

        Args:
            **overrides: Fields to override (target_entity_uuid, end_position, aoe_shape, etc.)

        Returns:
            BaseAction: A new instance that can be applied
        """
        registered_template_uuid = self.registered_template_uuid or self.uuid
        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
        }
        update_dict.update(overrides)
        update_dict["registered_template_uuid"] = registered_template_uuid

        return self.model_copy(deep=True, update=update_dict)

    def describe_discovery(self) -> ActionDiscoveryDescription:
        return ActionDiscoveryDescription()

    @final
    def get_discovery_template_name(self) -> str:
        """The row's command token, by one rule for every action (plan §14.4).

        The name, a free cast's label, a slot spell's level, a loot child, the
        authored choices and a restricted grant; never parsed back.
        """
        description = self.describe_discovery()
        selection = self.current_selection()
        name = self.name or "Unknown"
        if description.cast_cost_label is not None:
            name += f" [{description.cast_cost_label}]"
        if description.is_spell_variant and description.spell_level:
            name += f"{SPELL_SLOT_TEMPLATE_SEPARATOR}{description.cast_at_level}"
        if description.loot_item_uuid is not None:
            name += f"__child_{description.loot_item_uuid}"
        name += "".join(f"__{facet.value}" for facet in selection.facets)
        if selection.cost_source.restricted_grant_id is not None:
            name += f"{RESTRICTED_ACTION_TEMPLATE_SEPARATOR}{selection.cost_source.restricted_grant_id}"
        return name

    def get_discovery_display_name(self) -> str:
        """Return the human-facing action name used by UIs."""
        grant = self._restricted_action_grant
        if grant is not None:
            return f"{grant.display_name}: {self.name or 'Unknown'}"
        labels = [facet.label for facet in self._selected_facets]
        return f"{self.name or 'Unknown'} ({', '.join(labels)})" if labels else (self.name or "Unknown")

    def row_facets(self) -> Tuple[ActionVariantFacet, ...]:
        """The facets a discovery row discloses: the action's fixed ones, then its chosen ones."""
        return (*self.describe_discovery().fixed_facets, *self._selected_facets)

    def get_restricted_action_display_name(self) -> Optional[str]:
        """Return the explicit restricted-budget label for this variant."""
        grant = self._restricted_action_grant
        return grant.display_name if grant is not None else None

    def check_costs(self) -> bool:
        """Check whether the acting entity can afford all effective costs."""
        costs = [*self.effective_costs,*self.get_conditional_runtime_costs()]
        if self._source_cannot_take_actions(costs) or not self._allows_original_action_channels():
            return False
        return self._costs_are_affordable(costs)

    def check_target_independent_costs(self) -> bool:
        """Check source affordability without consulting selected-target state."""
        costs = [*self.target_independent_effective_costs,*self.get_conditional_runtime_costs()]
        if self._source_cannot_take_actions(costs) or not self._allows_original_action_channels():
            return False
        return self._costs_are_affordable(costs)

    def _original_action_channels(self) -> frozenset[ActionEconomyCostType]:
        return frozenset(ActionEconomyCostType(cost.cost_type) for cost in self.costs
                         if cost.cost > 0 and cost.cost_type in ("actions", "bonus_actions"))

    def _allows_original_action_channels(self) -> bool:
        source = BaseBlock.get(self.source_entity_uuid)
        channels=self._original_action_channels() | frozenset(ActionEconomyCostType(cost.cost_type)
            for cost in self.get_conditional_runtime_costs() if cost.cost>0 and cost.cost_type in ("actions","bonus_actions"))
        return source is None or source.allows_action_channels(channels)

    def _on_costs_committed(self, declaration: ActionEvent, execution: ActionEvent) -> None:
        """Record commitment before cancelable execution handlers run."""
        source = BaseBlock.get(self.source_entity_uuid)
        if source is not None:
            source.record_action_channels(self._original_action_channels())
        committed = EventQueue.publish_committed_phase(ActionCostsCommittedEvent(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=self.source_entity_uuid,
            parent_event=declaration.uuid, action_lineage_uuid=declaration.lineage_uuid,
            named_resource_costs=tuple((cost.resource_name, cost.resource_cost) for cost in execution.costs
                if cost.resource_name is not None and cost.resource_cost > 0),
            effect_origin=execution.get_effect_origin(), phase=EventPhase.EFFECT, use_register=False))
        committed.phase_to(EventPhase.COMPLETION)

    def _costs_are_affordable(self, costs: Sequence["Cost"]) -> bool:
        """Evaluate one already-transformed cost sequence."""
        for cost in costs:
            if cost.evaluator is not None and not cost.evaluator(self.source_entity_uuid, cost.cost_type, cost.cost):
                return False
            if cost.resource_cost > 0 and cost.resource_name:
                if cost.resource_evaluator is not None:
                    if not cost.resource_evaluator(self.source_entity_uuid, cost.resource_name, cost.resource_cost):
                        return False
        return True

    def _source_cannot_take_actions(self, costs: Sequence["Cost"]) -> bool:
        """Return whether the source's neutral permission gate denies actions."""
        source = BaseBlock.get(self.source_entity_uuid)
        if source is None:
            return False
        if not source.has_runtime_agency():
            return True
        if self.allow_while_incapacitated:
            return False
        if source.can_take_actions():
            return False

        positive_costs = [
            cost
            for cost in costs
            if cost.cost > 0
        ]
        is_pure_reaction = (
            bool(positive_costs)
            and all(cost.cost_type == "reactions" for cost in positive_costs)
        )
        return not is_pure_reaction

    def _create_declaration_event(
        self,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
    ) -> Optional[ActionEvent]:
        """Create the declaration event for this action.

        Args:
            parent_event: Optional parent event for event-tree nesting.
            use_register: Whether to register the declaration event.

        Returns:
            Declaration event, or `None` if a subclass declines creation.
        """
        event = ActionEvent.from_costs(
            self.effective_costs,
            self.source_entity_uuid,
            self.target_entity_uuid,
            parent_event,
            use_register=use_register,
            source_item_uuid=self.source_item_uuid,
            source_item_presentation=self.source_item_presentation,
            item_charge_cost=self.charge_cost if self.source_item_uuid is not None else 0,
            declared_target_entity_uuids=self._declared_target_entity_uuids(),
            presentation_kind=self.presentation_kind,
        )
        event.name = self.name or "Action"
        source_block = BaseBlock.get(self.source_entity_uuid)
        if self.effect_origin is not None:
            event.effect_origin = self.effect_origin.model_copy(update={"source_event_lineage_uuid": str(event.lineage_uuid),
                "source_position":source_block.position if source_block is not None else None})
        elif self.harmful:
            event.effect_origin = EffectOrigin(kind=EffectOriginKind.ACTION,
                source_id=self.semantic_key, source_event_lineage_uuid=str(event.lineage_uuid),
                source_position=source_block.position if source_block is not None else None,
                harmful=True, area_application=self.effective_target_type in (
                    TargetType.POSITION, TargetType.POSITION_LOS, TargetType.POSITION_AOE))
        event.description = self.description
        if source_block is not None:
            event.source_entity_name = source_block.name
        return event

    def _declared_target_entity_uuids(self) -> List[UUID]:
        """Return entity targets fixed by this action declaration.

        Returns:
            All multi-target applications, or the primary entity target.
        """
        if self.effective_target_type in (
            TargetType.MULTI_ENTITY,
            TargetType.POSITION_AOE,
        ):
            return self.get_all_targets()
        return [self.target_entity_uuid] if self.target_entity_uuid is not None else []

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Admit this executable instance's own selection through the one shared path (plan §14.3b).

        Args:
            declaration_event: Declaration-phase event to advance or cancel.

        Returns:
            Execution event on success, canceled event on validation failure, or
            `None` if a subclass declines validation.
        """
        source = BaseBlock.get(self.source_entity_uuid)
        if source is None:
            return declaration_event.cancel(status_message="Source entity not found")
        return self._admit(declaration_event, source.action_scan(subjective=False))

    def _admit(self, declaration_event: ActionEvent, scan: ActorScan) -> ActionEvent:
        """Every requirement of this instance's own selection, then handler admission, on the action's one scan."""
        error = (self.requirements_error(scan, self.current_selection())
                 or self.handler_admission_error(subjective=scan.subjective))
        if error is not None:
            return declaration_event.cancel(status_message=error)
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Succesfully validated action{self.name} for {declaration_event.source_entity_uuid}"
        )

    def _source_condition_error(self, targets: Sequence[UUID], position: Optional[Tuple[int, int]]) -> str | None:
        source = BaseBlock.get(self.source_entity_uuid)
        if source is not None and not self.is_movement and any(condition.blocks_outward_actions
                and condition.contributions_active() for condition in source.active_conditions_by_uuid.values()):
            if self.is_attack or self.harmful or any(identity != source.uuid for identity in targets) or (
                    position is not None and self.effective_target_type != TargetType.SELF):
                return "An active boundary prevents outward actions"
        if self.is_spell and source is not None and source.is_spellcasting_blocked():
            return "Spellcasting is prevented by an active condition"
        return None

    def validate_source_requirements_for_discovery(self) -> bool:
        """Validate non-cost requirements that do not depend on a target.

        Entity-target discovery calls this before enumerating targets so the
        transport can distinguish an unavailable actor state from an actor
        that is ready but currently has no legal target. Concrete actions with
        source-owned prerequisites override this narrow hook; authoritative
        execution still repeats every requirement in ``_validate``.
        """
        return self._source_condition_error((), None) is None

    def pre_validate(self) -> bool:
        """Validate affordability and non-cost requirements without execution or events."""
        source = BaseBlock.get(self.source_entity_uuid)
        return (
            source is not None and self.contributions_active() and self.check_costs()
            and self.requirements_error(source.action_scan(subjective=False), self.current_selection()) is None
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[Event]:
        """Apply the action's effects.

        Args:
            execution_event: Execution-phase event for this action.

        Returns:
            Accepted ActionEvent effect, canceled child Event, or `None`.
        """
        return execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying effect for {self.name}"
        )

    def _finalize_aoe(self, effect_event: ActionEvent) -> None:
        """Post-convolution hook for POSITION_AOE actions. Override for terrain/zone setup.

        Called after all per-target _apply() calls complete, before COMPLETION phase.
        Only called when target_type is POSITION_AOE.
        A recorded execution footprint is available on effect_event.resolved_area_positions.
        """
        pass

    def _apply_target_batch(
        self, execution_event: ActionEvent, target_uuids: List[UUID], *,
        parent_event: Event, application_index_offset: int = 0,
    ) -> int:
        """Apply one ordered batch with the existing child-action lifecycle.

        The batch is one instant: inside an area it joins the area's group, and
        a nested batch (Turn Undead, Preserve Life) opens its own.
        """
        total_damage = 0
        with EventQueue.group(GroupEntryKind.NESTED_BATCH, root=parent_event,
                              shares_damage_rolls=not self.performs_attack):
            for application_index, target_uuid in enumerate(target_uuids, application_index_offset):
                result_event = self._apply_target_application(execution_event, target_uuid,
                    parent_event=parent_event, application_index=application_index)
                if result_event is not None:
                    total_damage += result_event.total_damage or 0
        return total_damage

    def _apply_target_application(
        self, execution_event: ActionEvent, target_uuid: UUID, *,
        parent_event: Event, application_index: int,
    ) -> Optional[ActionEvent]:
        """Resolve one target's application; None when it was vetoed or canceled.

        The target lives on the per-target event (plan §5.3 #6); per-cast pools stay on the cast.
        """
        target_block = BaseBlock.get(target_uuid)

        membership = ApplicationMembership(lineage_uuid=execution_event.lineage_uuid,
            application_id=uuid5(execution_event.lineage_uuid, f"target-application:{application_index}"),
            index=application_index)
        per_target_event = execution_event.model_copy(update={
            'uuid': uuid4(), 'lineage_uuid': uuid4(),
            'parent_event': parent_event.uuid,
            'parent_lineage': parent_event.lineage_uuid,
            'target_entity_uuid': target_uuid,
            'target_entity_name': target_block.name if target_block else None,
            'children_events': [], 'lineage_children_events': [], 'children_lineages': [],
            'application': membership,
            'propagation': self.get_application_propagation(target_uuid, membership),
            'resolution_ref': ApplicationResolutionRef(lineage_uuid=membership.lineage_uuid,
                application_id=membership.application_id),
        })
        per_target_event = cast(ActionEvent, EventQueue.register(per_target_event))
        if per_target_event.canceled:
            return None
        result_event = (per_target_event.phase_to(EventPhase.EFFECT)
                        if per_target_event.application_intercepted_by is not None else self._apply(per_target_event))
        if result_event is None or result_event.canceled:
            return None
        result_event = cast(ActionEvent, result_event)
        if result_event.phase is not EventPhase.EFFECT:
            raise ValueError(f"Action {self.name} target application must end at effect phase")
        self._publish_application_commit(result_event)
        result_event.phase_to(EventPhase.COMPLETION,
            status_message=result_event.status_message or f"{self.name} target application completed")
        return result_event

    def get_authored_spell_id(self) -> str | None:
        """Ordinary actions have no spell identity."""
        return None

    def _publish_application_commit(self, effect_event: ActionEvent) -> None:
        """Observe one admitted target application after effect vetoes finish."""
        if effect_event.canceled:
            return
        committed = EventQueue.publish_committed_phase(ActionApplicationCommittedEvent(
            source_entity_uuid=effect_event.source_entity_uuid,
            target_entity_uuid=effect_event.target_entity_uuid,
            action_id=effect_event.behavior_id, spell_id=self.get_authored_spell_id(),
            interception_provider_uuid=effect_event.application_intercepted_by,
            effect_origin=effect_event.get_effect_origin(), parent_event=effect_event.uuid,
            phase=EventPhase.EFFECT, use_register=False))
        committed.phase_to(EventPhase.COMPLETION)

    def _apply_target_applications(
        self, execution_event: ActionEvent, effect_event: ActionEvent,
        target_uuids: List[UUID],
    ) -> ActionEvent:
        """Resolve the usual single batch; finite native area stages may override."""
        total_damage = self._apply_target_batch(execution_event, target_uuids, parent_event=effect_event)
        return effect_event.with_updates(
            total_targets=len(target_uuids), total_damage=total_damage,
            aoe_position=self.end_position,
            status_message=f"{self.name} affected {len(target_uuids)} targets for {total_damage} total damage",
        )

    def _cleanup_concentration(self, effect_event: ActionEvent) -> None:
        """Close action-owned concentration work before the root terminal."""
        pass

    def _apply_costs(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Commit action costs before execution is published.

        Subclasses that consume action economy override this method.
        """
        return execution_event

    def _prepare_item_charge(
        self,
        execution_event: ActionEvent,
        declaration_event: ActionEvent,
    ) -> tuple[ActionEvent, Event | None]:
        """Admit an item-backed finite cost before committing action economy."""
        if (error := self.source_item_contact_error()) is not None:
            return execution_event.cancel(status_message=error), None
        if execution_event.item_charge_cost <= 0:
            return execution_event, None
        if execution_event.source_item_uuid is None:
            return execution_event.cancel(
                status_message="Finite item charge has no source item"
            ), None
        if (
            execution_event.item_charge_action_lineage_uuid
            != declaration_event.lineage_uuid
        ):
            return execution_event.cancel(
                status_message="Finite item charge is not authorized for this action"
            ), None
        item = BaseBlock.get(execution_event.source_item_uuid)
        if item is None:
            return execution_event.cancel(
                status_message="Finite item charge source is no longer available"
            ), None
        if not isinstance(item, FiniteChargeProvider):
            return execution_event.cancel(
                status_message="Action source item cannot provide finite charges"
            ), None
        if item.charges == -1:
            return execution_event, None
        try:
            result = item.prepare_charge_consumption(
                execution_event.item_charge_cost,
                execution_event.source_entity_uuid,
                declaration_event,
            )
        except RuntimeError:
            return execution_event.cancel(
                status_message="Finite item charge could not be consumed"
            ), None
        if result.canceled:
            return execution_event.cancel(
                status_message=(
                    "Item charge consumption was canceled before action execution"
                )
            ), None
        return execution_event, result

    def _commit_item_charge(self, execution_event: ActionEvent, prepared: Event | None) -> ActionEvent:
        if prepared is None:
            return execution_event
        item = BaseBlock.get(execution_event.source_item_uuid) if execution_event.source_item_uuid else None
        if item is None or not isinstance(item, FiniteChargeProvider):
            return execution_event.cancel(status_message="Finite item resource lost before commit")
        result = item.commit_prepared_charge(prepared)
        return execution_event.cancel(status_message="Finite item resource rejected") if result.canceled else execution_event


    @staticmethod
    def _publish_detached_cancellation(event: ActionEvent) -> ActionEvent:
        """Publish one cancellation produced by detached owner work."""
        if event.use_register or not event.canceled:
            raise ValueError("Expected an unregistered action cancellation")
        published = EventQueue.register(
            event.model_copy(update={"use_register": True})
        )
        if not isinstance(published, ActionEvent):
            raise TypeError(
                "Action cancellation dispatch returned "
                f"{type(published).__name__}, expected ActionEvent"
            )
        return published

    def apply(self, parent_event: Optional[Event] = None) -> Optional[Event]:
        """Apply this action inside one passive causal-event batch.

        Args:
            parent_event: Optional parent event for nested actions.

        Returns:
            The terminal action event, or None when application cannot begin.
        """
        with runtime_behavior_provider(self.behavior_binding):
            with EventQueue.batch_on_event_callbacks():
                return self._apply_action(parent_event)

    def _apply_action(self, parent_event: Optional[Event] = None) -> Optional[Event]:
        """Main entry point for applying an action. This method orchestrates the flow
        through declaration, validation, and application phases.

        For MULTI_ENTITY actions, this runs convolution: calls _apply() for each target
        in get_all_targets(), collecting results into a final completion event.

        Raises:
            ValueError: If this is a template (use instantiate() first)
        """
        timing_enabled = action_timing_enabled()
        total_started = time.perf_counter() if timing_enabled else 0.0

        def start_phase() -> float:
            return time.perf_counter() if timing_enabled else 0.0

        def record_phase(phase: str, started_at: float) -> None:
            if timing_enabled:
                record_action_timing(f"base_action.{phase}_ms", started_at)

        def record_total() -> None:
            if timing_enabled:
                record_action_timing("base_action.apply_total_ms", total_started)

        if self.template:
            raise ValueError(f"Cannot apply template action '{self.name}' - use instantiate() first")

        started = start_phase()
        if not self.check_costs():
            record_phase("check_costs", started)
            record_total()
            return None
        record_phase("check_costs", started)

        started = start_phase()
        declaration_event = self._create_declaration_event(
            parent_event,
            use_register=False,
        )
        record_phase("create_declaration_event", started)
        if declaration_event is None:
            record_total()
            return None
        published_declaration = EventQueue.register(
            declaration_event.model_copy(update={"use_register": True}),
        )
        if not isinstance(published_declaration, ActionEvent):
            raise TypeError(
                "Action declaration dispatch returned "
                f"{type(published_declaration).__name__}, expected ActionEvent"
            )
        declaration_event = published_declaration
        if not self.contributions_active():
            return declaration_event.cancel(status_message="The owning magical effect is suppressed or absent")
        if declaration_event.canceled:
            record_total()
            return declaration_event

        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} can only be validated in the declaration phase")
        detached_declaration = declaration_event.model_copy(
            deep=True,
            update={"use_register": False},
        )
        started = start_phase()
        source = BaseBlock.get(self.source_entity_uuid)
        if source is None:
            record_total()
            return self._publish_detached_cancellation(
                detached_declaration.cancel(status_message="Source entity not found"))
        scan = source.action_scan(subjective=False)
        execution_event = self._admit(detached_declaration, scan)
        record_phase("validate", started)
        if execution_event is None:
            record_total()
            return execution_event
        if type(execution_event) is not type(declaration_event):
            raise TypeError(
                f"Action validation returned {type(execution_event).__name__}; "
                f"expected {type(declaration_event).__name__}"
            )
        if execution_event.lineage_uuid != declaration_event.lineage_uuid:
            raise ValueError("Action validation cannot replace its declaration lineage")
        if execution_event.canceled:
            record_total()
            return self._publish_detached_cancellation(execution_event)
        if execution_event.phase not in [EventPhase.EXECUTION]:
            raise ValueError(f"Action {self.name} can only be applied in the execution phase")

        execution_event = execution_event.model_copy(
            update={"use_register": False}
        )
        execution_event, prepared_item_charge = self._prepare_item_charge(execution_event, declaration_event)
        try:
            if execution_event.canceled:
                record_total()
                return self._publish_detached_cancellation(execution_event)
            # Resource-admission handlers can change source ownership.
            if (error := self.source_item_contact_error()) is not None:
                return self._publish_detached_cancellation(execution_event.cancel(status_message=error))
            started = start_phase()
            execution_event = self._apply_costs(execution_event)
            record_phase("apply_costs", started)
            if execution_event is None:
                record_total()
                return None
            if execution_event.canceled:
                record_total()
                return self._publish_detached_cancellation(execution_event)
            if execution_event.phase is not EventPhase.EXECUTION:
                raise ValueError("Action cost commitment must preserve execution phase")

            self._on_costs_committed(declaration_event, execution_event)
            execution_event = execution_event.model_copy(update={
                "use_register": True,
                "lineage_children_events": list(
                    declaration_event.lineage_children_events
                ),
                "children_events": [],
            })
            published_execution = EventQueue.register(execution_event)
            if not isinstance(published_execution, ActionEvent):
                raise TypeError(
                    "Action execution dispatch returned "
                    f"{type(published_execution).__name__}, expected ActionEvent"
                )
            execution_event = published_execution
            if execution_event.canceled:
                record_total()
                return execution_event

            # Execution handlers may change the geometry after costs are committed.
            # Rejection here is an interruption, without refunding those costs.
            selection = self.current_selection()
            access_error = (self._source_condition_error(self._selection_targets(selection),
                                selection.positions[0] if selection.positions else None)
                            or self.source_item_contact_error() or self._position_selection_error(selection)
                            or self._physical_access_error(scan, selection))
            if access_error is not None:
                record_total()
                return execution_event.cancel(status_message=access_error)

            execution_event = self._commit_item_charge(execution_event, prepared_item_charge)
            if execution_event.canceled:
                return execution_event
            if self.effective_target_type in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE):
                # Every target's effect is one simultaneous group: observers settle
                # once when it closes, before the root completes (plan §5.1-5.4).
                # One shared damage roll for area effects and for multi-target
                # effects without attack rolls (PHB "same time"; human D6a).
                with EventQueue.group(GroupEntryKind.AREA_APPLICATION, root=execution_event,
                        shares_damage_rolls=(self.effective_target_type is TargetType.POSITION_AOE
                                             or not self.performs_attack)):
                    started = start_phase()
                    all_target_uuids, resolved_area_positions = self._resolve_execution_targets()
                    record_phase("resolve_convolution_targets", started)
                    started = start_phase()
                    effect_event = execution_event.phase_to(
                        EventPhase.EFFECT,
                        total_targets=len(all_target_uuids),
                        total_damage=0,
                        aoe_position=self.end_position,
                        resolved_area_positions=resolved_area_positions,
                        status_message=(
                            f"Applying {self.name} to {len(all_target_uuids)} targets"
                        ),
                    )
                    record_phase("convolution_effect_event", started)
                    if effect_event.canceled:
                        record_total()
                        return effect_event

                    targets_started = start_phase()
                    effect_event = self._apply_target_applications(
                        execution_event, effect_event, all_target_uuids)
                    record_phase("convolution_apply_targets", targets_started)
                    if effect_event.canceled:
                        record_total()
                        return effect_event

                    if self.effective_target_type == TargetType.POSITION_AOE:
                        started = start_phase()
                        self._finalize_aoe(effect_event)
                        record_phase("finalize_aoe", started)
            else:
                started = start_phase()
                effect_event = (execution_event.phase_to(EventPhase.EFFECT)
                                if execution_event.application_intercepted_by is not None else self._apply(execution_event))
                record_phase("apply_effect", started)

            if effect_event is None or effect_event.canceled:
                record_total()
                return effect_event
            # Canceled child Events propagate above; success retains ActionEvent.
            effect_event = cast(ActionEvent, effect_event)
            if effect_event.phase is not EventPhase.EFFECT:
                raise ValueError(
                    f"Action {self.name} must finish authored mechanics at effect phase"
                )
            if self.effective_target_type not in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE):
                self._publish_application_commit(effect_event)
            if self.requires_concentration:
                started = start_phase()
                self._cleanup_concentration(effect_event)
                record_phase("cleanup_concentration", started)
            started = start_phase()
            completion_event = effect_event.phase_to(
                EventPhase.COMPLETION,
                status_message=(
                    effect_event.status_message or f"{self.name} completed"
                ),
            )
            record_phase("completion_event", started)
            record_total()
            return completion_event
        finally:
            if prepared_item_charge is not None:
                history = EventQueue.get_event_history(prepared_item_charge.uuid)
                if history and not any(event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)
                        for event in history):
                    history[-1].cancel(status_message="Owning action ended before item release")



class StructuredAction(BaseAction):
    """Action implementation backed by prerequisite and consequence processors."""

    prerequisites: OrderedDict[str,EventProcessor] = Field(
        default_factory=OrderedDict,
        exclude=True,
        description="Ordered prerequisite processors keyed by prerequisite name.",
    )
    consequences: OrderedDict[str,EventProcessor] = Field(
        default_factory=OrderedDict,
        exclude=True,
        description="Ordered consequence processors keyed by consequence name.",
    )
    revalidate_prerequisites: bool = Field(
        default=True,
        description="Whether prerequisites are revalidated after each consequence.",
    )
    cost_applier: Optional[EventProcessor] = Field(
        default=None,
        exclude=True,
        description="Optional processor used to apply action costs.",
    )

    @computed_field
    @property
    def prerequisite_names(self) -> List[str]:
        """Serializable list of prerequisite names."""
        return list(self.prerequisites.keys())

    @computed_field
    @property
    def consequence_names(self) -> List[str]:
        """Serializable list of consequence names."""
        return list(self.consequences.keys())

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Run the consequence application pipeline."""
        if execution_event.phase != EventPhase.EXECUTION:
            raise ValueError(f"Action {self.name} consequences can only be applied in execution phase")

        current_event = execution_event
        effect_event = current_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying consequences for {self.name}"
        )
        if effect_event.canceled:
            return effect_event

        current_event = effect_event
        for consequence_name, consequence_function in self.consequences.items():
            consequence_event = consequence_function(current_event, current_event.source_entity_uuid)
            if consequence_event is None:
                return current_event.cancel(status_message=f"Consequence {consequence_name} failed for {self.name}")
            elif consequence_event.canceled:
                return consequence_event

            if self.revalidate_prerequisites:
                if consequence_event.phase not in [EventPhase.EXECUTION, EventPhase.EFFECT]:
                    raise ValueError(f"Consequence {consequence_name} returned event in invalid phase {consequence_event.phase}")
                validated_event = self._validate(consequence_event)
                if validated_event is None or validated_event.canceled:
                    return validated_event
                current_event = validated_event
            else:
                current_event = consequence_event

        if current_event.phase is EventPhase.EXECUTION:
            return current_event.phase_to(
                EventPhase.EFFECT,
                status_message=(
                    f"Applied structured action {self.name} for "
                    f"{current_event.source_entity_uuid}"
                ),
            )
        if current_event.phase is not EventPhase.EFFECT:
            raise ValueError(
                f"Structured action {self.name} ended in invalid phase "
                f"{current_event.phase}"
            )
        return current_event.with_updates(
            status_message=(
                f"Applied structured action {self.name} for "
                f"{current_event.source_entity_uuid}"
            ),
        )

    def _apply_costs(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply costs through the configured processor when present."""
        if self.cost_applier is not None:
            return self.cost_applier(execution_event, self.source_entity_uuid)
        return execution_event


class OpportunityAttackExposure(BaseModel):
    """Visible threat boundary crossed by one disclosed movement route."""

    reactor_uuid: UUID = Field(description="Visible hostile whose threatened area the route exits.")
    reactor_name: str = Field(description="Subjectively known display name of the potential reactor.")
    from_position: Tuple[int, int] = Field(description="Last route cell inside the hostile threat area.")
    to_position: Tuple[int, int] = Field(description="First route cell outside the hostile threat area.")


class AvailableTarget(BaseModel):
    """A valid target for an action, with index for selection.

    Used in CLI/UI patterns like 'attack 0' or 'move 3' to select targets.
    """

    target_kind: Literal["creature", "object"] = "creature"
    index: int = Field(description="Index for selection (e.g., 'attack 0')")
    target_uuid: Optional[UUID] = Field(default=None, description="For ENTITY actions")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Grid cell for POSITION targets and entity/object target cells")
    target_name: Optional[str] = Field(default=None, description="Entity name if ENTITY action")
    distance: Optional[int] = Field(default=None, description="Distance in feet")
    path_cost: Optional[int] = Field(
        default=None,
        description="Exact selected-target movement cost for a position action.",
    )
    extra_target_uuids: Optional[List[UUID]] = Field(default=None, description="Additional targets for MULTI_ENTITY actions")
    secondary_targets: Optional[List["AvailableTarget"]] = None
    is_path_hazardous: bool = Field(default=False, description="Whether shortest path crosses a hazardous tile")
    safe_path_cost: Optional[int] = Field(default=None, description="Movement cost of safe alternative path (None if no safe path)")
    path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Shortest path to this target")
    safe_path: Optional[List[Tuple[int, int]]] = Field(default=None, description="Safe alternative path avoiding hazards")
    opportunity_attack_exposures: List[OpportunityAttackExposure] = Field(
        default_factory=list,
        description="Visible hostile threat boundaries crossed by the shortest path.",
    )
    safe_path_opportunity_attack_exposures: List[OpportunityAttackExposure] = Field(
        default_factory=list,
        description="Visible hostile threat boundaries crossed by the safe alternative path.",
    )
    affected_entity_uuids: Optional[List[UUID]] = Field(default=None, description="UUIDs of entities affected by AoE")
    affected_entity_names: Optional[List[str]] = Field(default=None, description="Names of entities affected by AoE")
    affected_count: Optional[int] = Field(default=None, description="Number of entities affected by AoE")
    affected_positions: Optional[List[Tuple[int, int]]] = Field(default=None, description="All positions in AoE shape (for map preview)")


def prefers_safe_movement_path(target: AvailableTarget, movement_remaining: int, *, prefer_safe: bool = True) -> bool:
    """The native route preference shared by execution and disclosed previews."""
    return (prefer_safe and target.safe_path is not None and target.safe_path_cost is not None
            and target.safe_path_cost <= movement_remaining)


class AvailableActionMetadata(BaseModel):
    """Passive metadata shared by native choices and compact player choices."""

    __getattr__ = read_private_attribute
    discovery_generation: int = 0
    discovery_index: int = 0
    discovery_runtime: UUID | None = None
    discovery_actor_uuid: UUID | None = None
    spellcasting_source_id: UUID | None = None
    spellcasting_provider_id: str | None = None
    spellcasting_ability: str | None = None
    template_name: str = Field(
        description=(
            "Engine command token for execution; never authored presentation "
            "identity."
        ),
    )
    semantic_key: str = Field(
        default="action.unclassified",
        description=(
            "Rules/mechanics family key retained for policy and diagnosis; "
            "never authored presentation identity."
        ),
    )
    behavior_id: str = Field(description="Primitive executable-rule identity.")
    provided_by_id: str = Field(description="Primitive direct-provider identity.")
    origin_root_id: Optional[str] = Field(
        default=None,
        description="Optional durable primitive root of the provider chain.",
    )
    configured_action_ref: Optional[ContentRef] = Field(
        default=None,
        description=(
            "Exact authored configuration for a parameterized action. "
            "Clients resolve this catalog row instead of inferring a variant "
            "from execution tokens, display names, or outcome identifiers."
        ),
    )
    target_type: TargetType = Field(description="What kind of target this action needs")
    position_selection: Optional[PositionSelection] = Field(
        default=None, description="Position input required after choosing a discovery target.",
    )
    position_region: Optional[PositionRegion] = Field(
        default=None, description="Free-aim region of a position action; its aims are validated on demand.",
    )
    availability_status: ActionAvailabilityStatus = Field(
        description=(
            "Closed reason this authored row is executable or unavailable; "
            "clients never infer the reason from an empty target list."
        ),
    )
    can_afford: bool = Field(
        description=(
            "Whether the neutral source permission gate and all "
            "target-independent action-economy or named-resource costs permit "
            "execution. Consult availability_status for target-bound costs and "
            "requirements."
        ),
    )
    display_name: str = Field(description="Human-readable name (e.g., 'Scimitar')")
    description: str = Field(default="", description="Action description")
    cost_type: CostType = Field(description="Type of cost (actions, bonus_actions, etc.)")
    cost_amount: int = Field(default=1, description="Cost amount (usually 1)")
    restricted_action_budget: Optional[str] = Field(
        default=None, description="Restricted budget funding this otherwise ordinary action, e.g. Haste.",
    )
    costs: List[BaseCost] = Field(
        default_factory=list,
        description=(
            "Target-independent action-economy and named-resource costs for "
            "this row; selected movement cost is carried by target.path_cost."
        ),
    )
    weapon_slot: Optional[str] = Field(default=None, description="Weapon slot for attacks")
    weapon_name: Optional[str] = Field(default=None, description="Weapon name for display (e.g., 'Scimitar')")
    damage_types: List[str] = Field(default_factory=list, description="Damage type labels this action can deal when known.")
    outcome_profile: Optional[ActionOutcomeProfile] = Field(
        default=None,
        description="Actor-baseline stochastic outcome model when declared by the action rule.",
    )
    self_setup_profile: Optional[ActionSelfSetupProfile] = Field(
        default=None,
        description="Engine-declared logical self-setup outcome when available.",
    )
    target_effect_profile: Optional[ActionTargetEffectProfile] = Field(
        default=None,
        description="Engine-declared conditional effects over selected targets.",
    )
    world_effect_profile: Optional[ActionWorldEffectProfile] = Field(
        default=None,
        description="Engine-declared information and topology effects.",
    )
    performs_attack: bool = False
    action_category: ActionCategory = Field(default=ActionCategory.ABILITY, description="Classification of this action")
    base_template_name: Optional[str] = Field(
        default=None,
        description=(
            "Registered execution-token family when it differs from "
            "template_name; never authored presentation identity."
        ),
    )
    spell_level: Optional[int] = Field(default=None, description="Base spell level for spell actions.")
    cast_at_level: Optional[int] = Field(default=None, description="Spell slot level used by this action row.")
    cast_levels: Tuple[int, ...] = Field(default=(), description=(
        "Slot levels this spell can be cast at now; the selection names one (plan D17). "
        "The row's targets are those of cast_at_level, the lowest."))
    is_spell_variant: bool = Field(default=False, description="Whether this row represents a generated spell variant.")
    requires_concentration: bool = Field(default=False, description="Whether executing this action starts or maintains concentration.")

    @property
    def is_attack(self) -> bool:
        """Whether this available action is categorized as an attack."""
        return self.action_category == ActionCategory.ATTACK

    @property
    def is_spell(self) -> bool:
        """Whether this available action is categorized as a spell."""
        return self.action_category == ActionCategory.SPELL

    num_projectiles: Optional[int] = Field(default=None, description="Number of projectiles/targets for MULTI_ENTITY actions")
    allow_same_target: Optional[bool] = Field(default=None, description="Whether same target can be selected multiple times")
    is_item_use: bool = Field(default=False, description="True for use actions from items")
    source_item_uuid: Optional[UUID] = Field(default=None, description="Item providing this action")
    loot_item_uuid: UUID | None = Field(default=None, description="Exact contained item transferred by this discovered loot action.")
    item_stack_count: Optional[int] = Field(default=None, description="Stack count of source item (for display, only set when > 1)")
    item_charge_cost: int = Field(
        default=0,
        ge=0,
        description="Finite source-item charges consumed by successful execution.",
    )
    conditional_costs: tuple[ConditionalCost,...] = ()
    fixed_healing: Optional[int] = Field(
        default=None,
        ge=0,
        description="Deterministic hit points restored when declared by the action rule.",
    )
    allocation_completion: Literal["selected_only", "fill_primary"] = "selected_only"
    variant_facets: tuple[ActionVariantFacet, ...] = ()
    interaction_affordance: ActionAffordance = Field(default_factory=ActionAffordance)
    connector_traversal: Optional[ConnectorTraversalDiscovery] = None
    @field_validator("behavior_id", "provided_by_id", "origin_root_id")
    @classmethod
    def _validate_behavior_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_namespaced_id(value, "discovered behavior identity")



class AvailableActionInfo(AvailableActionMetadata):
    """Native admitted targets and their private execution template."""

    valid_targets: List[AvailableTarget] = Field(
        default_factory=list,
        description=(
            "Currently executable targets with stable indices. Target-bound "
            "costs are evaluated before a target enters this list."
        ),
    )
    _execution_template: Optional[BaseAction] = PrivateAttr(default=None)
    _aoe_include_dead: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def _validate_availability_status(self) -> "AvailableActionInfo":
        """Reject contradictory affordability and closed status facts."""
        source_unaffordable = (
            self.availability_status
            is ActionAvailabilityStatus.SOURCE_UNAFFORDABLE
        )
        if source_unaffordable == self.can_afford:
            raise ValueError(
                "source_unaffordable requires can_afford=false, while every "
                "other availability status requires can_afford=true"
            )
        available = (
            self.availability_status is ActionAvailabilityStatus.AVAILABLE
        )
        if not available and self.valid_targets:
            raise ValueError("every unavailable status requires an empty target list")
        if available and not self.valid_targets and self.position_region is None:
            raise ValueError("available requires an executable target or a free-aim region")
        return self

    @property
    def execution_template(self) -> Optional[BaseAction]:
        """Return the exact action object that produced this discovery row."""
        return self._execution_template

    def set_execution_template(self, template: BaseAction) -> None:
        """Bind this discovery row to its exact private execution source."""
        self._execution_template = template


class SelectedRoute(BaseModel):
    """The native route choice reused by preview and command execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    path: tuple[tuple[int, int], ...] = Field(min_length=1)
    cost_feet: float
    affordable_endpoint: tuple[int, int]
    policy: Literal["normal", "safe"]
    opportunity_attack_exposures: tuple[OpportunityAttackExposure, ...]
    is_hazardous: bool


class AvailableSelectionPreview(BaseModel):
    """Detached result of inspecting one admitted ordered selection prefix."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    can_confirm: bool
    reason: str | None = None
    effective_target_uuids: tuple[UUID, ...] = ()
    next_targets: tuple[AvailableTarget, ...] = ()
    next_positions: tuple[tuple[int, int], ...] = ()
    geometry: AoEPresentationGeometry | None = None
    affected_positions: tuple[tuple[int, int], ...] = ()
    area_preview: Literal["not_applicable", "deferred", "computed"] = "not_applicable"
    affected_entity_uuids: tuple[UUID, ...] = ()
    affected_entity_names: tuple[str, ...] = ()
    selected_route: SelectedRoute | None = None


class AvailableWorldInteraction(BaseModel):
    """Observed world verb; this descriptor alone is never executable."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    subject_uuid: UUID
    behavior_id: str
    label: str
    description: str = ""
    default_priority: int = 100
    contact_positions: tuple[tuple[int, int], ...] = ()
    connector_uuid: UUID | None = None
    template_name: str | None = None
    configured_action_ref: ContentRef | None = None
    variant_facets: tuple[ActionVariantFacet, ...] = ()
    reason: str | None = None


class AvailableActionsResult(BaseModel):
    """Complete available actions query result.

    Returned by Entity.get_available_actions(). Groups actions by type for
    easy iteration and UI rendering.
    """

    __getattr__ = read_private_attribute
    discovery_generation: int = 0
    entity_uuid: UUID = Field(description="UUID of the entity these actions are for")
    entity_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting entities (Attack)")
    position_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting positions (Move)")
    self_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Self-targeting actions (Dash, Dodge, etc.)")
    object_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting objects (Pick Up, interactions)")
    remaining_movement: int = Field(default=0, description="Remaining movement in feet")
    world_interactions: tuple[AvailableWorldInteraction, ...] = ()
    handler_details: List[AvailableHandlerInfo] = Field(
        default_factory=list,
        description="Player-toggleable event handlers and their current state.",
    )
    _inventory_use_action_sources: List[BaseAction] = PrivateAttr(default_factory=list)
    _registered_action_variants: List[BaseAction] = PrivateAttr(default_factory=list)
    _item_charge_pools: Dict[UUID, Tuple[int, int]] = PrivateAttr(default_factory=dict)

    @property
    def inventory_use_action_sources(self) -> Tuple[BaseAction, ...]:
        """Return item action instances captured by this exact discovery call."""
        return tuple(self._inventory_use_action_sources)

    def set_inventory_use_action_sources(self, actions: List[BaseAction]) -> None:
        """Retain already specialized item actions for downstream epoch metadata."""
        self._inventory_use_action_sources = list(actions)

    @property
    def registered_action_variants(self) -> Tuple[BaseAction, ...]:
        """Return registered action variants captured by this discovery call."""
        return tuple(self._registered_action_variants)

    def set_registered_action_variants(self, actions: List[BaseAction]) -> None:
        """Retain freshly expanded registered actions for this exact query."""
        self._registered_action_variants = list(actions)

    @property
    def item_charge_pools(self) -> Dict[UUID, Tuple[int, int]]:
        """Return finite item pools captured by this exact discovery call."""
        return dict(self._item_charge_pools)

    def set_item_charge_pool(
        self,
        item_uuid: UUID,
        current: int,
        maximum: int,
    ) -> None:
        """Capture one subjectively discovered finite item pool."""
        self._item_charge_pools[item_uuid] = (current, maximum)

    @property
    def attack_actions(self) -> List[AvailableActionInfo]:
        """Already-expanded registered and item-supplied attack choices."""
        return [action for action in self.all_actions if action.performs_attack]

    @property
    def all_actions(self) -> List[AvailableActionInfo]:
        """Get all available actions as a flat list."""
        return self.entity_actions + self.position_actions + self.self_actions + self.object_actions
