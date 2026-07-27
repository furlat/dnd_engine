"""Action templates, cost models, execution events, and discovery DTOs."""

import time

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, computed_field, model_validator
from dnd.action_timing import action_timing_enabled, record_action_timing
from dnd.core.action_types import (
    ActionPresentationKind,
    RestrictedActionGrant,
    RestrictedActionGrantProvider,
    RestrictedActionKind,
)
from dnd.core.events import Event, EventType, EventPhase, EventProcessor, Range, EventQueue
from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.combat_log import ActionLogData, CombatLogEntry, CombatLogEntryType, MultiEntityLogData, md_color
from dnd.core.content.identities import ContentRef
from dnd.core.content.runtime import (
    AuthoredBehaviorAttribution,
    BehaviorBinding,
    active_runtime_behavior_binding,
    runtime_behavior_provider,
)
from dnd.core.aoe import AoEShape
from dnd.core.item_types import ItemPresentationProvider, ItemPresentationState
from dnd.core.modifiers import AdvantageStatus
from dnd.blocks.sensory import Senses
from typing import Any, Optional, Callable, ClassVar, OrderedDict, List, Dict, Literal, Sequence, Set, Tuple, cast
from uuid import UUID, uuid4, uuid5
from enum import Enum

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
    position = getattr(target, "position", None)
    has_position = (
        isinstance(position, tuple)
        and len(position) == 2
        and isinstance(position[0], int)
        and isinstance(position[1], int)
    )
    x, y = cast(Tuple[int, int], position) if has_position else (0, 0)
    target_name = target.name or "" if target is not None else ""
    return (not has_position, x, y, target_name, str(target_uuid))


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


class TargetType(str, Enum):
    """Target routing categories used by discovery and execution."""

    SELF = "self"
    ENTITY = "entity"
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


class AttackRollBaseline(BaseModel):
    """Read-only actor contribution to an attack-roll outcome model."""

    attack_bonus: int = Field(description="Actor-side bonus added to the d20 roll.")
    advantage: AdvantageStatus = Field(description="Actor-side advantage state before target modifiers.")
    critical_threshold: int = Field(ge=1, le=20, description="Natural d20 threshold for an actor-side critical hit.")
    critical_extra_dice: int = Field(ge=0, description="Actor-side extra damage dice added on a critical hit.")


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
    """Event emitted by the base action pipeline."""

    behavior_binding: Optional[BehaviorBinding] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Immutable authored behavior identity captured before this event "
            "version enters the queue."
        ),
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
    application_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Ordered target-application index for a convolution child event.",
    )
    application_id: Optional[UUID] = Field(
        default=None,
        description="Deterministic identity of one ordered target application.",
    )
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

    def model_post_init(self, __context: Any) -> None:
        """Freeze active authored identity before the event is registered."""
        if self.behavior_binding is None:
            self.behavior_binding = active_runtime_behavior_binding()
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
        if (self.application_index is None) != (self.application_id is None):
            raise ValueError("application_index and application_id must be set together")
        return self

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
            data=data.model_dump(),
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
            data=data.model_dump(),
            success=n_targets > 0
        )


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
        description="Optional stable semantic registry key overriding the action's class identity.",
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
    parent_event: Optional[Event] = Field(
        default=None,
        description="Optional parent event used to nest action-created events.",
    )
    costs: List[Cost] = Field(default_factory=list, description="Runtime costs required by this action.")
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Target category used by discovery and instantiation.",
    )
    template: bool = Field(
        default=False,
        description="True when this action is a reusable template instead of an executable instance.",
    )
    include_self: bool = Field(
        default=False,
        description="Whether the acting entity can be included in this action's target set.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ABILITY,
        description="Broad action classification used by discovery and UI layers.",
    )
    presentation_kind: ActionPresentationKind = Field(
        default=ActionPresentationKind.DEFAULT,
        description="Stable presentation meaning copied to every action event phase.",
    )
    allow_while_incapacitated: bool = Field(
        default=False,
        description="Whether this action can be used while the source cannot take actions.",
    )
    position_discovery: Optional[PositionDiscoveryContract] = Field(
        default=None,
        description="Typed subjective candidate contract for plain position actions.",
    )
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = (
        frozenset()
    )
    _restricted_action_grant: Optional[RestrictedActionGrant] = PrivateAttr(
        default=None,
    )

    @property
    def is_attack(self) -> bool:
        """Whether this action is categorized as an attack."""
        return self.action_category == ActionCategory.ATTACK

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

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return actor-known stochastic action data when the rule defines it.

        Args:
            actor: Entity discovering this action. The base layer intentionally
                accepts an opaque owner to preserve dependency direction.

        Returns:
            Actor-baseline outcome profile, or ``None`` when the action has not
            declared enough rule data for quantitative policy reasoning.
        """
        return None

    def get_fixed_healing(self, actor: Any) -> Optional[int]:
        """Return deterministic healing disclosed by this action rule.

        Args:
            actor: Entity discovering this action. The base contract remains
                owner-agnostic to preserve dependency direction.

        Returns:
            Fixed hit points restored per execution, or ``None`` when healing
            is absent or determined by another outcome model.
        """
        return None

    def get_self_setup_profile(self, actor: Any) -> Optional[ActionSelfSetupProfile]:
        """Return the action's dependency-neutral self-setup annotation.

        Args:
            actor: Entity discovering the action. The base contract keeps the
                owner opaque to preserve dependency direction.

        Returns:
            Logical setup profile, or ``None`` when the action declares no
            self-directed combat setup.
        """
        return None

    def get_target_effect_profile(self, actor: Any) -> Optional[ActionTargetEffectProfile]:
        """Return conditional effects the rule applies to selected targets.

        Args:
            actor: Entity discovering the action. The core action layer keeps
                the owner opaque to preserve dependency direction.

        Returns:
            Typed target-effect profile, or ``None`` when the action has not
            declared target-conditional rule effects.
        """
        return None

    def get_world_effect_profile(self, actor: Any) -> Optional[ActionWorldEffectProfile]:
        """Return information or topology effects declared by the action rule.

        Args:
            actor: Entity discovering the action. The core action layer keeps
                the owner opaque to preserve dependency direction.

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
        description="Whether action completion invokes the concentration cleanup hook.",
    )
    alt_cost_type: Optional[str] = Field(default=None, description="Temporary replacement for primary action cost type.")
    alt_extra_costs: List[Cost] = Field(default_factory=list, description="Temporary additional costs.")
    alt_target_type: Optional[TargetType] = Field(default=None, description="Temporary replacement target type.")
    alt_target_count: Optional[int] = Field(default=None, description="Temporary multi-target count override.")
    alt_skip_slot: bool = Field(default=False, description="Whether temporary overrides skip spell-slot costs.")

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
        if self.effective_target_type not in (TargetType.ENTITY, TargetType.MULTI_ENTITY, TargetType.OBJECT):
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

    def get_range(self) -> Optional[Range]:
        """Get the range of this action.

        Override in subclasses to provide dynamic range calculation.
        Returns Range object with type/normal/long, or None if unlimited.

        For actions with dynamic range (like Jump), override this method.
        """
        return None

    def get_valid_positions(self) -> List[Tuple[int, int]]:
        """Get valid target positions for POSITION_LOS and POSITION_AOE actions.

        Override in subclasses to provide custom position filtering.
        Default implementation uses senses.visible + get_range().

        Returns:
            List of valid positions this action can target.
        """
        if self.effective_target_type not in (TargetType.POSITION_LOS, TargetType.POSITION_AOE):
            return []

        entity = BaseBlock.get(self.source_entity_uuid)
        if entity is None:
            return []

        senses_block = entity.get_senses()
        if not isinstance(senses_block, Senses):
            return []

        action_range = self.get_range()
        max_range = action_range.normal if action_range else 0

        valid: List[Tuple[int, int]] = []
        visible = senses_block.visible
        position = senses_block.position

        if not visible:
            return []

        for pos, is_visible in visible.items():
            if not is_visible:
                continue
            if pos == position:
                continue
            if max_range > 0:
                distance = senses_block.get_feet_distance(pos)
                if distance > max_range:
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

    def get_all_targets(self) -> List[UUID]:
        """Get all target UUIDs for multi-target actions.

        Position AoE actions compute targets from their shape and end position.
        Multi-entity actions return the primary target followed by extra targets.
        Subclasses may override this to provide custom target resolution.

        Returns:
            Target UUIDs in processing order.
        """
        if self.effective_target_type == TargetType.POSITION_AOE:
            if self.aoe_shape and self.end_position:
                source_block = BaseBlock.get(self.source_entity_uuid)
                if source_block:
                    shape = self.aoe_shape.model_copy(update={'target': self.end_position})
                    shape.compute_objective(source_block.position)
                    targets = sorted(
                        shape.affected_entity_uuids,
                        key=target_resolution_sort_key,
                    )
                    if not self.include_self:
                        targets = [uid for uid in targets if uid != self.source_entity_uuid]
                    targets = self._filter_targets_by_faction(source_block, targets)
                    if not self.include_dead:
                        targets = [
                            uid for uid in targets
                            if (block := BaseBlock.get(uid)) and block.is_active
                        ]
                    return targets
            return []

        targets: List[UUID] = []
        if self.target_entity_uuid:
            targets.append(self.target_entity_uuid)
        targets.extend(self.extra_target_entity_uuids)
        return targets

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

    def _validate_target_filter(self, all_targets: List[UUID]) -> Optional[str]:
        """Validate that all targets match the valid_target_filter.

        Position-AoE targets are already filtered during target resolution.
        Explicit multi-entity targets are validated here.

        Args:
            all_targets: Target UUIDs to validate.

        Returns:
            Error message if validation fails, otherwise `None`.
        """
        if self.effective_target_type == TargetType.POSITION_AOE:
            return None

        source_block = BaseBlock.get(self.source_entity_uuid)
        if source_block is None:
            return "Source entity not found"

        senses: Optional[Senses] = getattr(source_block, 'senses', None)
        if senses is not None:
            for target_uuid in all_targets:
                if target_uuid == self.source_entity_uuid:
                    continue
                if target_uuid not in senses.entities:
                    target = BaseBlock.get(target_uuid)
                    target_name = target.name if target else str(target_uuid)
                    return f"{target_name} is not visible"

        source_faction = source_block.faction

        for target_uuid in all_targets:
            target = BaseBlock.get(target_uuid)
            if target is None:
                return f"Target {target_uuid} not found"

            same = target_uuid == self.source_entity_uuid
            ally = same or (source_faction is not None and target.faction is not None and source_faction == target.faction)
            enemy = not same and (source_faction is None or target.faction is None or source_faction != target.faction)

            if self.valid_target_filter == "enemies":
                if not enemy:
                    return f"{target.name} is not an enemy"
            elif self.valid_target_filter == "allies":
                if same or not ally:
                    return f"{target.name} is not an ally"
            elif self.valid_target_filter == "self_or_allies":
                if not ally:
                    return f"{target.name} is not self or an ally"

        return None

    def instantiate(self, **overrides) -> "BaseAction":
        """Create an executable instance from this template.

        Uses model_copy() to preserve object types (e.g., AoE shape subclasses).
        Instances are not registered (ephemeral, used once for apply()).

        Args:
            **overrides: Fields to override (target_entity_uuid, end_position, aoe_shape, etc.)

        Returns:
            BaseAction: A new instance that can be applied

        Raises:
            ValueError: If this is not a template
        """
        if not self.template:
            raise ValueError("Can only instantiate from a template")

        update_dict: dict = {
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
        }
        update_dict.update(overrides)

        return self.model_copy(deep=True, update=update_dict)

    def get_discovery_variants(self, entity: Any) -> List["BaseAction"]:
        """Return action forms that should appear in action discovery.

        Args:
            entity: Entity requesting available actions.

        Returns:
            Discovery actions for this template. Non-variant actions expose
            themselves.
        """
        variants: List["BaseAction"] = [self]
        eligible_kinds = set(self.restricted_action_kinds)
        if any(
            cost.cost_type == "actions"
            and cost.cost > 0
            and cost.resource_name is None
            and cost.resource_cost == 0
            for cost in self.target_independent_effective_costs
        ):
            eligible_kinds.add(RestrictedActionKind.STANDARD_ACTION)
        if not eligible_kinds:
            return variants
        if not isinstance(entity, RestrictedActionGrantProvider):
            return variants
        for grant in entity.get_restricted_action_grants():
            if eligible_kinds.isdisjoint(grant.allowed_kinds):
                continue
            if not any(
                cost.cost_type in grant.replaced_cost_types
                and cost.cost > 0
                and cost.resource_name is None
                and cost.resource_cost == 0
                for cost in self.target_independent_effective_costs
            ):
                continue
            variant = self.model_copy(
                deep=True,
                update={
                    "uuid": uuid4(),
                    "template": False,
                    "use_register": False,
                },
            )
            variant._restricted_action_grant = grant
            variants.append(variant)
        return variants

    def get_discovery_template_name(self) -> str:
        """Return the machine-facing action name used for execution."""
        base_name = self.name or "Unknown"
        grant = self._restricted_action_grant
        if grant is None:
            return base_name
        return (
            f"{base_name}{RESTRICTED_ACTION_TEMPLATE_SEPARATOR}"
            f"{grant.grant_id}"
        )

    def get_discovery_display_name(self) -> str:
        """Return the human-facing action name used by UIs."""
        grant = self._restricted_action_grant
        if grant is None:
            return self.get_discovery_template_name()
        return f"{grant.display_name}: {self.name or 'Unknown'}"

    def get_restricted_action_display_name(self) -> Optional[str]:
        """Return the explicit restricted-budget label for this variant."""
        grant = self._restricted_action_grant
        return grant.display_name if grant is not None else None

    def check_costs(self) -> bool:
        """Check whether the acting entity can afford all effective costs."""
        costs = self.effective_costs
        if self._source_cannot_take_actions(costs):
            return False
        return self._costs_are_affordable(costs)

    def check_target_independent_costs(self) -> bool:
        """Check source affordability without consulting selected-target state."""
        costs = self.target_independent_effective_costs
        if self._source_cannot_take_actions(costs):
            return False
        return self._costs_are_affordable(costs)

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
        if self.allow_while_incapacitated:
            return False
        source = BaseBlock.get(self.source_entity_uuid)
        if source is None:
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
        event.description = self.description
        source_block = BaseBlock.get(self.source_entity_uuid)
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
        """Validate whether this action can be performed.

        Multi-entity actions require explicit targets and may forbid duplicate
        targets. Multi-entity and position-AoE actions both apply the configured
        relationship target filter.

        Args:
            declaration_event: Declaration-phase event to advance or cancel.

        Returns:
            Execution event on success, canceled event on validation failure, or
            `None` if a subclass declines validation.
        """
        effective_tt = self.effective_target_type
        if effective_tt in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE):
            all_targets = self.get_all_targets()

            if not all_targets:
                if effective_tt == TargetType.MULTI_ENTITY:
                    return declaration_event.cancel(status_message="No targets specified")

            if effective_tt == TargetType.MULTI_ENTITY and not self.allow_same_target:
                if len(set(all_targets)) != len(all_targets):
                    return declaration_event.cancel(
                        status_message="This action cannot target the same entity multiple times"
                    )

            filter_error = self._validate_target_filter(all_targets)
            if filter_error:
                return declaration_event.cancel(status_message=filter_error)

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Succesfully validated action{self.name} for {declaration_event.source_entity_uuid}"
        )

    def validate_requirements_for_discovery(self) -> bool:
        """Validate non-cost execution requirements for action discovery.

        This surface deliberately excludes action-economy and resource
        affordability. Discovery uses it to calculate target legality while
        reporting affordability independently through ``check_costs()``.
        """
        declaration_event = self._create_declaration_event(parent_event=None, use_register=False)
        if declaration_event is None:
            return False
        if declaration_event.phase != EventPhase.DECLARATION:
            return False
        validation_event = self._validate(declaration_event)
        if validation_event is None or validation_event.canceled:
            return False
        return True

    def pre_validate(self) -> bool:
        """Validate affordability and non-cost requirements without execution."""
        return (
            self.check_costs()
            and self.validate_requirements_for_discovery()
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply the action's effects.

        Args:
            execution_event: Execution-phase event for this action.

        Returns:
            Completion event, canceled event, or `None`.
        """
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applying effect for {self.name}"
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Succesfully applied action {self.name} for {execution_event.source_entity_uuid}"
        )

    def _finalize_aoe(self, effect_event: ActionEvent) -> None:
        """Post-convolution hook for POSITION_AOE actions. Override for terrain/zone setup.

        Called after all per-target _apply() calls complete, before COMPLETION phase.
        Only called when target_type is POSITION_AOE.
        """
        pass

    def _cleanup_concentration(self, completion_event: ActionEvent) -> None:
        """Post-completion concentration cleanup hook. Override in SpellAction."""
        pass

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply action costs after successful completion.

        Subclasses that consume action economy override this method.
        """
        return completion_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Succesfully applied costs for {self.name} for {completion_event.source_entity_uuid}"
        )

    def _apply_execution_cancellation_costs(
        self,
        canceled_event: ActionEvent,
    ) -> Optional[ActionEvent]:
        """Apply costs committed before an execution-phase interruption.

        The dependency-neutral base action has no owner-specific resource
        consumer. Action families whose execution can be interrupted override
        this hook and preserve the canceled event as the terminal result.

        Args:
            canceled_event: Execution event canceled by a handler.

        Returns:
            The terminal canceled event after committed costs are applied.
        """
        return canceled_event

    def apply(self, parent_event: Optional[Event] = None) -> Optional[Event]:
        """Apply this action inside one passive causal-event batch.

        Args:
            parent_event: Optional parent event for nested actions.

        Returns:
            The terminal action event, or None when application cannot begin.
        """
        with runtime_behavior_provider(self):
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
        declaration_event = self._create_declaration_event(parent_event)
        record_phase("create_declaration_event", started)
        if declaration_event is None:
            record_total()
            return None
        elif declaration_event.canceled:
            record_total()
            return declaration_event

        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} can only be validated in the declaration phase")
        started = start_phase()
        execution_event = self._validate(declaration_event)
        record_phase("validate", started)
        if execution_event is None:
            record_total()
            return execution_event
        if execution_event.canceled:
            if execution_event.canceled_from_phase is EventPhase.EXECUTION:
                started = start_phase()
                execution_event = self._apply_execution_cancellation_costs(execution_event)
                record_phase("apply_execution_cancellation_costs", started)
            record_total()
            return execution_event
        if execution_event.phase not in [EventPhase.EXECUTION]:
            raise ValueError(f"Action {self.name} can only be applied in the execution phase")

        if self.effective_target_type in (TargetType.MULTI_ENTITY, TargetType.POSITION_AOE):
            started = start_phase()
            all_target_uuids = self.get_all_targets()
            record_phase("resolve_convolution_targets", started)
            original_target = self.target_entity_uuid
            total_damage = 0

            targets_started = start_phase()
            for application_index, target_uuid in enumerate(all_target_uuids):
                target_started = start_phase()
                self.target_entity_uuid = target_uuid

                target_block = BaseBlock.get(target_uuid)
                target_entity_name = target_block.name if target_block else None

                per_target_event = execution_event.model_copy(update={
                    'uuid': uuid4(),
                    'lineage_uuid': uuid4(),
                    'parent_event': execution_event.uuid,
                    'target_entity_uuid': target_uuid,
                    'target_entity_name': target_entity_name,
                    'children_events': [],
                    'lineage_children_events': [],
                    'application_index': application_index,
                    'application_id': uuid5(
                        execution_event.lineage_uuid,
                        f"target-application:{application_index}",
                    ),
                })
                per_target_event = cast(ActionEvent, EventQueue.register(per_target_event))

                if per_target_event.canceled:
                    record_phase("convolution_target_canceled", target_started)
                    continue

                result_event = self._apply(per_target_event)
                if result_event:
                    damage = result_event.total_damage or 0
                    total_damage += damage
                record_phase("convolution_target_apply", target_started)
            record_phase("convolution_apply_targets", targets_started)

            self.target_entity_uuid = original_target

            started = start_phase()
            effect_event = execution_event.phase_to(
                EventPhase.EFFECT,
                total_targets=len(all_target_uuids),
                total_damage=total_damage,
                aoe_position=self.end_position,
                status_message=f"{self.name} affected {len(all_target_uuids)} targets for {total_damage} total damage"
            )
            record_phase("convolution_effect_event", started)

            if self.effective_target_type == TargetType.POSITION_AOE:
                started = start_phase()
                self._finalize_aoe(effect_event)
                record_phase("finalize_aoe", started)

            started = start_phase()
            completion_event = effect_event.phase_to(
                EventPhase.COMPLETION,
                status_message=f"{self.name} completed"
            )
            record_phase("convolution_completion_event", started)
        else:
            started = start_phase()
            completion_event = self._apply(execution_event)
            record_phase("apply_effect", started)

        if completion_event is None or completion_event.canceled:
            record_total()
            return completion_event
        if completion_event.phase not in [EventPhase.COMPLETION]:
            raise ValueError(f"Action {self.name} can only be completed in the completion phase")
        if self.requires_concentration:
            started = start_phase()
            self._cleanup_concentration(completion_event)
            record_phase("cleanup_concentration", started)
        started = start_phase()
        cost_event = self._apply_costs(completion_event)
        record_phase("apply_costs", started)
        if cost_event is None or cost_event.canceled:
            record_total()
            return cost_event
        if cost_event.phase not in [EventPhase.COMPLETION]:
            raise ValueError(f"Action {self.name} can only be completed in the completion phase")
        record_total()
        return cost_event


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

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Run the prerequisite checking pipeline."""
        if declaration_event.phase != EventPhase.DECLARATION:
            raise ValueError(f"Action {self.name} prerequisites can only be checked in declaration phase")

        current_event = declaration_event
        for prerequisite_name, prerequisite_function in self.prerequisites.items():
            prerequisite_event = prerequisite_function(current_event, current_event.source_entity_uuid)
            if prerequisite_event is None:
                return current_event.cancel(status_message=f"Prerequisite {prerequisite_name} failed for {self.name}")
            if prerequisite_event.canceled:
                return prerequisite_event
            current_event = prerequisite_event

        return current_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Successfully validated structured action {self.name} for {current_event.source_entity_uuid}"
        )

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

        return current_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Successfully completed structured action {self.name} for {current_event.source_entity_uuid}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply costs through the configured processor when present."""
        if self.cost_applier is not None:
            return self.cost_applier(completion_event, self.source_entity_uuid)
        return completion_event


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


class AvailableActionInfo(BaseModel):
    """Information about an available action and its valid targets.

    This is returned by Entity.get_available_actions() and contains everything
    needed to display the action in UI and execute it.
    """
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
    behavior_attribution: AuthoredBehaviorAttribution = Field(
        description=(
            "Exact authored behavior identity used for catalog-backed "
            "presentation; execution and display names are not identity."
        ),
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
    availability_status: ActionAvailabilityStatus = Field(
        description=(
            "Closed reason this authored row is executable or unavailable; "
            "clients never infer the reason from an empty target list."
        ),
    )
    valid_targets: List[AvailableTarget] = Field(
        default_factory=list,
        description=(
            "Currently executable targets with stable indices. Target-bound "
            "costs are evaluated before a target enters this list."
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
    item_stack_count: Optional[int] = Field(default=None, description="Stack count of source item (for display, only set when > 1)")
    item_charge_cost: int = Field(
        default=0,
        ge=0,
        description="Finite source-item charges consumed by successful execution.",
    )
    fixed_healing: Optional[int] = Field(
        default=None,
        ge=0,
        description="Deterministic hit points restored when declared by the action rule.",
    )
    _execution_template: Optional[BaseAction] = PrivateAttr(default=None)

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
        if available != bool(self.valid_targets):
            raise ValueError(
                "available requires at least one executable target, while "
                "every unavailable status requires an empty target list"
            )
        return self

    @property
    def execution_template(self) -> Optional[BaseAction]:
        """Return the exact action object that produced this discovery row."""
        return self._execution_template

    def set_execution_template(self, template: BaseAction) -> None:
        """Bind this discovery row to its exact private execution source."""
        self._execution_template = template


class AvailableHandlerInfo(BaseModel):
    """Player-toggleable event handler exposed with available actions."""

    name: str = Field(description="Handler display name.")
    behavior_attribution: AuthoredBehaviorAttribution = Field(
        description=(
            "Exact authored behavior identity used for catalog-backed "
            "reaction presentation."
        ),
    )
    uuid: UUID = Field(description="Stable handler UUID.")
    enabled: bool = Field(description="Whether the handler is currently enabled.")
    trigger_event: str = Field(description="Primary trigger event type, when declared.")


class AvailableActionsResult(BaseModel):
    """Complete available actions query result.

    Returned by Entity.get_available_actions(). Groups actions by type for
    easy iteration and UI rendering.
    """
    entity_uuid: UUID = Field(description="UUID of the entity these actions are for")
    entity_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting entities (Attack)")
    position_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting positions (Move)")
    self_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Self-targeting actions (Dash, Dodge, etc.)")
    object_actions: List[AvailableActionInfo] = Field(default_factory=list, description="Actions targeting objects (Pick Up, Attack Object)")
    remaining_movement: int = Field(default=0, description="Remaining movement in feet")
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
    def all_actions(self) -> List[AvailableActionInfo]:
        """Get all available actions as a flat list."""
        return self.entity_actions + self.position_actions + self.self_actions + self.object_actions
