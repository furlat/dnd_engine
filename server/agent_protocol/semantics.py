"""Dependency-neutral contracts for subjective action meaning and planning facts."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from hashlib import sha256
import json
from typing import Hashable, Mapping, Optional, Tuple, Union, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator


FactValue = Union[str, int, float, bool, None]


class SemanticModel(BaseModel):
    """Immutable base for contracts shared across epochs and policy consumers."""

    model_config = ConfigDict(frozen=True)


class SemanticProvenanceKind(str, Enum):
    """How an action semantic contract was obtained."""

    EXACT = "exact"
    STRUCTURED_PROFILE = "structured_profile"
    CATEGORY_FALLBACK = "category_fallback"
    UNKNOWN = "unknown"


class ActionSemanticProvenance(SemanticModel):
    """Auditable derivation metadata for one action semantic contract."""

    kind: SemanticProvenanceKind = Field(
        default=SemanticProvenanceKind.EXACT,
        description="Resolution strength used to construct the semantic contract.",
    )
    semantic_key: Optional[str] = Field(
        default=None,
        description="Stable engine action key from which semantics were derived.",
    )
    derivation: str = Field(
        default="declared_contract",
        description="Stable description of the derivation mechanism.",
    )
    missing_inputs: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Structured semantic inputs absent when resolution remained unknown.",
    )


class TruthValue(str, Enum):
    """Three-valued truth used when subjective knowledge may be incomplete."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class FactOperator(str, Enum):
    """Composition operation for a planning fact expression."""

    CONSTANT = "constant"
    PREDICATE = "predicate"
    ALL = "all"
    ANY = "any"
    NOT = "not"


class ComparisonOperator(str, Enum):
    """Comparison applied by a fact predicate."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_THAN = "less_than"
    LESS_OR_EQUAL = "less_or_equal"
    EXISTS = "exists"


class FactPredicate(SemanticModel):
    """One typed lookup over the session-subjective fact store."""

    fact_id: str = Field(description="Stable fact identifier read from subjective knowledge.")
    comparison: ComparisonOperator = Field(
        default=ComparisonOperator.EQUALS,
        description="Comparison applied to the known fact value.",
    )
    expected_value: FactValue = Field(default=True, description="Value used by the comparison.")
    expected_fact_id: Optional[str] = Field(
        default=None,
        description="Optional subjective fact supplying the comparison value.",
    )


class FactExpression(SemanticModel):
    """Composable planning condition with explicit unknown propagation."""

    operator: FactOperator = Field(description="Expression operation.")
    constant: Optional[TruthValue] = Field(default=None, description="Value for a constant expression.")
    predicate: Optional[FactPredicate] = Field(default=None, description="Predicate for a predicate expression.")
    operands: Tuple["FactExpression", ...] = Field(
        default_factory=tuple,
        description="Child expressions for boolean composition.",
    )

    @model_validator(mode="after")
    def validate_shape(self) -> "FactExpression":
        """Reject ambiguous expression structures at the protocol boundary."""
        if self.operator is FactOperator.CONSTANT:
            if self.constant is None:
                raise ValueError("A constant fact expression requires a value")
            if self.predicate is not None or self.operands:
                raise ValueError("A constant fact expression cannot include a predicate or operands")
        elif self.operator is FactOperator.PREDICATE:
            if self.predicate is None:
                raise ValueError("A predicate fact expression requires a predicate")
            if self.constant is not None or self.operands:
                raise ValueError("A predicate fact expression cannot include a constant or operands")
        elif self.operator is FactOperator.NOT:
            if self.constant is not None or self.predicate is not None:
                raise ValueError("A NOT fact expression cannot include a constant or predicate")
            if len(self.operands) != 1:
                raise ValueError("A NOT fact expression requires exactly one operand")
        elif self.operator in {FactOperator.ALL, FactOperator.ANY}:
            if self.constant is not None or self.predicate is not None:
                raise ValueError(
                    f"A {self.operator.value.upper()} fact expression cannot include a constant or predicate"
                )
            if not self.operands:
                raise ValueError(f"A {self.operator.value.upper()} fact expression requires at least one operand")
        return self

    @classmethod
    def unknown(cls) -> "FactExpression":
        """Return an expression whose value is explicitly unknown."""
        return cls(operator=FactOperator.CONSTANT, constant=TruthValue.UNKNOWN)

    @classmethod
    def true(cls) -> "FactExpression":
        """Return an expression that is always true."""
        return cls(operator=FactOperator.CONSTANT, constant=TruthValue.TRUE)


def evaluate_fact_expression(
    expression: FactExpression,
    facts: Mapping[str, FactValue],
) -> TruthValue:
    """Evaluate a planning expression without collapsing missing facts to false.

    Args:
        expression: Expression to evaluate.
        facts: Subjective fact values keyed by stable fact identifier.

    Returns:
        Three-valued result preserving uncertainty.

    Raises:
        ValueError: If an expression is structurally invalid.
    """
    if expression.operator is FactOperator.CONSTANT:
        if expression.constant is None:
            raise ValueError("A constant fact expression requires a value")
        return expression.constant
    if expression.operator is FactOperator.PREDICATE:
        if expression.predicate is None:
            raise ValueError("A predicate fact expression requires a predicate")
        return _evaluate_predicate(expression.predicate, facts)
    if expression.operator is FactOperator.NOT:
        if len(expression.operands) != 1:
            raise ValueError("A NOT fact expression requires exactly one operand")
        value = evaluate_fact_expression(expression.operands[0], facts)
        if value is TruthValue.UNKNOWN:
            return TruthValue.UNKNOWN
        return TruthValue.FALSE if value is TruthValue.TRUE else TruthValue.TRUE
    if expression.operator is FactOperator.ALL:
        values = [evaluate_fact_expression(operand, facts) for operand in expression.operands]
        if any(value is TruthValue.FALSE for value in values):
            return TruthValue.FALSE
        if any(value is TruthValue.UNKNOWN for value in values):
            return TruthValue.UNKNOWN
        return TruthValue.TRUE
    if expression.operator is FactOperator.ANY:
        values = [evaluate_fact_expression(operand, facts) for operand in expression.operands]
        if any(value is TruthValue.TRUE for value in values):
            return TruthValue.TRUE
        if any(value is TruthValue.UNKNOWN for value in values):
            return TruthValue.UNKNOWN
        return TruthValue.FALSE
    raise ValueError(f"Unsupported fact operator: {expression.operator}")


def _evaluate_predicate(
    predicate: FactPredicate,
    facts: Mapping[str, FactValue],
) -> TruthValue:
    """Evaluate one predicate against known subjective facts."""
    if predicate.fact_id not in facts:
        return TruthValue.UNKNOWN
    actual = facts[predicate.fact_id]
    if predicate.expected_fact_id is not None:
        if predicate.expected_fact_id not in facts:
            return TruthValue.UNKNOWN
        expected = facts[predicate.expected_fact_id]
    else:
        expected = predicate.expected_value
    if predicate.comparison is ComparisonOperator.EXISTS:
        return TruthValue.TRUE
    if predicate.comparison is ComparisonOperator.EQUALS:
        return TruthValue.TRUE if actual == expected else TruthValue.FALSE
    if predicate.comparison is ComparisonOperator.NOT_EQUALS:
        return TruthValue.TRUE if actual != expected else TruthValue.FALSE
    if actual is None or expected is None:
        return TruthValue.UNKNOWN
    if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
        return TruthValue.UNKNOWN
    if predicate.comparison is ComparisonOperator.GREATER_THAN:
        outcome = actual > expected
    elif predicate.comparison is ComparisonOperator.GREATER_OR_EQUAL:
        outcome = actual >= expected
    elif predicate.comparison is ComparisonOperator.LESS_THAN:
        outcome = actual < expected
    elif predicate.comparison is ComparisonOperator.LESS_OR_EQUAL:
        outcome = actual <= expected
    else:
        raise ValueError(f"Unsupported comparison operator: {predicate.comparison}")
    return TruthValue.TRUE if outcome else TruthValue.FALSE


class ActionTag(str, Enum):
    """Stable semantic capabilities exposed by an action affordance."""

    DAMAGE_SINGLE_TARGET = "damage.single_target"
    DAMAGE_MULTI_TARGET = "damage.multi_target"
    DAMAGE_AREA = "damage.area"
    ATTACK_WEAPON = "attack.weapon"
    ATTACK_SPELL = "attack.spell"
    CONTROL_HARD = "control.hard"
    CONTROL_SOFT = "control.soft"
    SUPPORT_BUFF = "support.buff"
    SUPPORT_HEAL = "support.heal"
    DEFENSE_SELF = "defense.self"
    SUMMON = "summon"
    ZONE_PERSISTENT = "zone.persistent"
    MOVEMENT_VOLUNTARY = "movement.voluntary"
    MOVEMENT_FORCED = "movement.forced"
    MOVEMENT_TELEPORT = "movement.teleport"
    MOBILITY_EXTEND = "mobility.extend"
    INTERACTION_DOOR_OPEN = "interaction.door.open"
    INTERACTION_DOOR_CLOSE = "interaction.door.close"
    INTERACTION_HAZARD_DEACTIVATE = "interaction.hazard.deactivate"
    INTERACTION_OBJECT = "interaction.object"
    INFORMATION_REVEAL = "information.reveal"
    INFORMATION_EXPLORE = "information.explore"
    CONCENTRATION_START = "concentration.start"
    CONCENTRATION_END = "concentration.end"
    RESOURCE_ACQUIRE = "resource.acquire"
    RESOURCE_SPEND = "resource.spend"
    CAPABILITY_TRANSFORM = "capability.transform"
    SETUP_SELF = "setup.self"
    TARGET_MULTI = "target.multi"
    TARGET_REPEAT = "target.repeat"
    TURN_END = "turn.end"
    UNKNOWN = "unknown"


class EffectOperation(str, Enum):
    """Abstract state operation predicted by an action."""

    SET = "set"
    SET_FROM_TARGET = "set_from_target"
    INCREASE = "increase"
    DECREASE = "decrease"
    ADD = "add"
    REMOVE = "remove"
    INVALIDATE = "invalidate"


class EffectCertainty(str, Enum):
    """Confidence class for a semantic effect."""

    GUARANTEED = "guaranteed"
    CONDITIONAL = "conditional"
    STOCHASTIC = "stochastic"
    POTENTIAL = "potential"


class OutcomeKind(str, Enum):
    """Mechanism controlling whether an action outcome occurs."""

    GUARANTEED = "guaranteed"
    ATTACK_ROLL = "attack_roll"
    SAVING_THROW = "saving_throw"
    CONTESTED = "contested"
    UNKNOWN = "unknown"


class LogicalEffect(SemanticModel):
    """Abstract change to one planning fact."""

    fact_id: str = Field(description="Fact expected to change.")
    operation: EffectOperation = Field(description="Operation applied to the fact.")
    value: FactValue = Field(default=None, description="Literal effect value when known.")
    value_ref: Optional[str] = Field(default=None, description="Reference supplying the effect value when dynamic.")


class ConditionalEffect(SemanticModel):
    """Effects expected only when a typed condition holds."""

    condition: FactExpression = Field(description="Condition guarding the effects.")
    effects: Tuple[LogicalEffect, ...] = Field(default_factory=tuple, description="Guarded effects.")


class StochasticEffect(SemanticModel):
    """Effects controlled by a roll, contest, or otherwise uncertain outcome."""

    outcome_kind: OutcomeKind = Field(description="Mechanism controlling the outcome.")
    effects: Tuple[LogicalEffect, ...] = Field(default_factory=tuple, description="Effects on success.")
    probability: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Known success probability.")


class EffectDisposition(str, Enum):
    """Tactical direction of an effect for its selected recipient."""

    BENEFICIAL = "beneficial"
    HARMFUL = "harmful"
    NEUTRAL = "neutral"


class TargetEffectSemantics(SemanticModel):
    """Conditional outcome branch evaluated separately for each selected target."""

    effect_id: str = Field(description="Stable semantic identity of the branch effect.")
    disposition: EffectDisposition = Field(description="Whether the effect helps or harms its recipient.")
    applicability: FactExpression = Field(description="Subjective target facts required by this branch.")
    outcome_kind: OutcomeKind = Field(description="Mechanism controlling whether the branch applies.")
    save_dc: Optional[int] = Field(default=None, description="Saving throw DC when disclosed by the rule.")
    save_ability: Optional[str] = Field(default=None, description="Saving throw ability when disclosed by the rule.")
    effects: Tuple[LogicalEffect, ...] = Field(default_factory=tuple, description="Effects established on success.")
    condition_semantic_keys: frozenset[str] = Field(
        default_factory=frozenset,
        description="Stable condition keys established by the branch.",
    )

    @model_validator(mode="after")
    def validate_resolution_metadata(self) -> "TargetEffectSemantics":
        """Keep saving-throw metadata aligned with the declared outcome kind."""
        if self.outcome_kind is OutcomeKind.SAVING_THROW:
            if self.save_dc is None or self.save_ability is None:
                raise ValueError("saving-throw target effects require save_dc and save_ability")
        elif self.save_dc is not None or self.save_ability is not None:
            raise ValueError("save metadata is valid only for saving-throw target effects")
        return self


class ResourceOperation(str, Enum):
    """Direction of a semantic resource change."""

    CONSUME = "consume"
    RESTORE = "restore"
    ACQUIRE = "acquire"


class ResourceEffect(SemanticModel):
    """Expected change to action economy or another named resource."""

    resource_id: str = Field(description="Stable action-economy or resource identifier.")
    operation: ResourceOperation = Field(description="Resource change direction.")
    amount: int = Field(ge=0, description="Resource amount changed.")


class ConcentrationOperation(str, Enum):
    """Relationship between an action and spell concentration."""

    START_OR_REPLACE = "start_or_replace"
    PRESERVE = "preserve"
    END = "end"


class ConcentrationEffect(SemanticModel):
    """Concentration transition produced by an action."""

    operation: ConcentrationOperation = Field(description="Concentration transition.")
    spell_semantic_id: Optional[str] = Field(default=None, description="Semantic spell family started when known.")


class SelfSetupDuration(str, Enum):
    """Lifetime class for a self-directed combat setup effect."""

    CURRENT_TURN = "current_turn"
    UNTIL_NEXT_TURN = "until_next_turn"
    UNTIL_REMOVED = "until_removed"


class SetupMaintenanceTrigger(str, Enum):
    """Actor behavior that requires a setup-retention check."""

    REVEALING_ACTION = "revealing_action"


class SetupMaintenanceFailure(str, Enum):
    """Setup transition caused by a failed maintenance check."""

    REMOVE_SETUP = "remove_setup"


class D20CheckMode(str, Enum):
    """Actor-baseline d20 mode for one disclosed maintenance check."""

    NONE = "None"
    ADVANTAGE = "Advantage"
    DISADVANTAGE = "Disadvantage"


class SelfSetupMaintenanceSemantics(SemanticModel):
    """Typed stochastic rule governing whether a self setup persists."""

    trigger: SetupMaintenanceTrigger = Field(description="Behavior that triggers the maintenance check.")
    skill_name: str = Field(description="Actor skill rolled by the maintenance check.")
    initial_dc: int = Field(ge=0, description="Difficulty class of the first maintenance check.")
    dc_increment_per_success: int = Field(
        default=0,
        ge=0,
        description="Difficulty-class increase after each successful maintenance check.",
    )
    check_bonus: int = Field(description="Disclosed actor bonus applied to the skill check.")
    check_advantage: D20CheckMode = Field(
        default=D20CheckMode.NONE,
        description="Disclosed actor-baseline advantage state for the skill check.",
    )
    failure: SetupMaintenanceFailure = Field(description="Setup transition caused by a failed check.")


class SelfSetupSemantics(SemanticModel):
    """Typed combat consequences established on the acting entity."""

    duration: SelfSetupDuration = Field(description="How long the setup is expected to remain relevant.")
    active_condition_semantic_keys: frozenset[str] = Field(
        default_factory=frozenset,
        description="Stable condition type keys that prove the setup is already active.",
    )
    maximum_duration_rounds: Optional[int] = Field(
        default=None,
        gt=0,
        description="Known upper bound in rounds when the setup expires without earlier removal.",
    )
    increases_weapon_damage: bool = Field(
        default=False,
        description="Whether the setup increases outgoing weapon damage.",
    )
    resistance_damage_types: frozenset[str] = Field(
        default_factory=frozenset,
        description="Damage types resisted while the setup remains active.",
    )
    grants_bonus_action_attack: bool = Field(
        default=False,
        description="Whether the setup unlocks an attack paid from bonus-action economy.",
    )
    grants_outgoing_attack_advantage: bool = Field(
        default=False,
        description="Whether the setup grants advantage on the actor's attacks.",
    )
    grants_incoming_attack_advantage: bool = Field(
        default=False,
        description="Whether the setup grants attackers advantage against the actor.",
    )
    grants_incoming_attack_disadvantage: bool = Field(
        default=False,
        description="Whether the setup imposes disadvantage on attacks against the actor.",
    )
    armor_class_bonus: int = Field(
        default=0,
        ge=0,
        description="Known armor-class increase supplied by the setup.",
    )
    movement_speed_multiplier: float = Field(
        default=1.0,
        ge=1.0,
        description="Known multiplier applied to the actor's movement speed.",
    )
    extra_actions_per_turn: int = Field(
        default=0,
        ge=0,
        description="Additional general actions supplied on each affected turn.",
    )
    grants_invisibility: bool = Field(
        default=False,
        description="Whether the setup makes the actor subjectively invisible to observers.",
    )
    incapacitates_on_removal: bool = Field(
        default=False,
        description="Whether ordinary removal applies an incapacitating drawback.",
    )
    maintenance: Optional[SelfSetupMaintenanceSemantics] = Field(
        default=None,
        description="Stochastic retention rule when actor behavior can remove the setup.",
    )
    outcome_adjustments: Tuple["CapabilityOutcomeAdjustment", ...] = Field(
        default_factory=tuple,
        description=(
            "Typed temporary changes to stochastic outcome profiles for matching "
            "actor-owned capabilities."
        ),
    )


class MovementKind(str, Enum):
    """Causal movement classification relevant to reactions and planning."""

    NONE = "none"
    VOLUNTARY = "voluntary"
    FORCED = "forced"
    TELEPORT = "teleport"


class SpatialSemantics(SemanticModel):
    """Spatial transition meaning for an action."""

    movement_kind: MovementKind = Field(default=MovementKind.NONE, description="Movement causal class.")
    moves_actor: bool = Field(default=False, description="Whether the acting entity changes position.")
    moves_target: bool = Field(default=False, description="Whether a selected target changes position.")
    ignores_intermediate_cells: bool = Field(
        default=False,
        description="Whether movement changes position without traversing intermediate cells.",
    )


class TopologyOperation(str, Enum):
    """Abstract operation on known traversability or line-of-sight topology."""

    OPEN = "open"
    CLOSE = "close"
    TOGGLE = "toggle"
    CREATE_BLOCKER = "create_blocker"
    REMOVE_BLOCKER = "remove_blocker"
    CREATE_HAZARD = "create_hazard"
    DEACTIVATE_HAZARD = "deactivate_hazard"


class WorldEffectAnchor(str, Enum):
    """Action-relative location anchoring an information or topology effect."""

    ACTOR = "actor"
    SELECTED_TARGET = "selected_target"
    SELECTED_POSITION = "selected_position"
    SELECTED_OBJECT = "selected_object"


class WorldEffectScope(str, Enum):
    """Typed subject or region changed by an information or topology effect."""

    TARGET = "target"
    REGION = "region"
    FRONTIER = "frontier"
    MAGICAL_DARKNESS = "magical_darkness"
    HAZARD_REGION = "hazard_region"


class WorldEffectShape(str, Enum):
    """Geometric shape of an area-scoped world effect."""

    SPHERE = "sphere"


class TopologyEffect(SemanticModel):
    """Expected topology transition caused by an interaction or spell."""

    operation: TopologyOperation = Field(description="Topology operation.")
    certainty: EffectCertainty = Field(description="Whether the topology transition is guaranteed or conditional.")
    anchor: WorldEffectAnchor = Field(description="Action-relative location anchoring the transition.")
    scope: WorldEffectScope = Field(description="Typed subject or region changed by the transition.")
    subject_ref: str = Field(description="Semantic reference to the affected object or region.")
    shape: Optional[WorldEffectShape] = Field(default=None, description="Area shape when the transition has geometric extent.")
    radius_feet: Optional[int] = Field(default=None, ge=0, description="Affected radius in feet when known.")
    affects_movement: bool = Field(default=False, description="Whether traversability changes.")
    affects_vision: bool = Field(default=False, description="Whether line of sight changes.")
    affects_hazards: bool = Field(default=False, description="Whether known route-hazard costs change.")

    @model_validator(mode="after")
    def validate_topology_geometry(self) -> "TopologyEffect":
        """Require shape and radius to describe one complete area contract."""
        if (self.shape is None) != (self.radius_feet is None):
            raise ValueError("topology effect shape and radius_feet must be declared together")
        return self


class InformationOperation(str, Enum):
    """Kind of subjective information change an action may cause."""

    REVEAL_FRONTIER = "reveal_frontier"
    EXPLORE_REGION = "explore_region"
    CHANGE_LIGHT = "change_light"
    CHANGE_PERCEIVABILITY = "change_perceivability"
    REVEAL_REGION = "reveal_region"
    GRANT_SENSE = "grant_sense"
    CONCEAL_REGION = "conceal_region"


class InformationEffect(SemanticModel):
    """Expected subjective observation change caused by an action."""

    operation: InformationOperation = Field(description="Information transition.")
    certainty: EffectCertainty = Field(description="Whether new facts are guaranteed or merely possible.")
    anchor: WorldEffectAnchor = Field(description="Action-relative location anchoring the transition.")
    scope: WorldEffectScope = Field(description="Typed subject or region changed by the transition.")
    scope_ref: str = Field(description="Semantic reference to the affected frontier or region.")
    shape: Optional[WorldEffectShape] = Field(default=None, description="Area shape when the transition has geometric extent.")
    radius_feet: Optional[int] = Field(default=None, ge=0, description="Area or sense radius in feet when known.")
    sense_type: Optional[str] = Field(default=None, description="Stable sense identifier supplied by a grant-sense transition.")

    @model_validator(mode="after")
    def validate_information_effect(self) -> "InformationEffect":
        """Require coherent geometry and sense metadata."""
        if (self.shape is None) != (self.radius_feet is None):
            raise ValueError("information effect shape and radius_feet must be declared together")
        if self.operation is InformationOperation.GRANT_SENSE:
            if self.sense_type is None:
                raise ValueError("grant-sense information effects require sense_type")
        elif self.sense_type is not None:
            raise ValueError("sense_type is valid only for grant-sense information effects")
        return self


class TargetAllocation(str, Enum):
    """Target-selection shape exposed by an affordance."""

    NONE = "none"
    SELF = "self"
    SINGLE_ENTITY = "single_entity"
    MULTI_ENTITY = "multi_entity"
    OBJECT = "object"
    POSITION = "position"
    PATH = "path"
    AREA = "area"


class AffectedRelationship(str, Enum):
    """Subjective relationship classes that can receive an action's effects."""

    ACTOR = "actor"
    CONTROLLED_ALLY = "controlled_ally"
    HOSTILE = "hostile"
    NEUTRAL = "neutral"
    ANY_ENTITY = "any_entity"


class TargetingSemantics(SemanticModel):
    """Typed target-allocation meaning independent of UI row layout."""

    allocation: TargetAllocation = Field(default=TargetAllocation.NONE, description="Target-allocation shape.")
    minimum_targets: int = Field(default=0, ge=0, description="Minimum selected targets.")
    maximum_targets: Optional[int] = Field(default=None, ge=0, description="Maximum selected targets when bounded.")
    allows_repeated_targets: bool = Field(default=False, description="Whether one target may be selected repeatedly.")
    affected_relationships: frozenset[AffectedRelationship] = Field(
        default_factory=frozenset,
        description="Known relationship classes affected after target allocation; empty means unknown.",
    )
    effect_radius_feet: Optional[int] = Field(
        default=None,
        ge=0,
        description="Known radial effect distance from the selected position or entity.",
    )


class CapabilityAmountSource(str, Enum):
    """Source used to compute one transformed capability cost."""

    FIXED = "fixed"
    SOURCE_RESOURCE = "source_resource"
    BASE_SPELL_LEVEL = "base_spell_level"


class CapabilityCostOperation(str, Enum):
    """Operation applied to a capability's current resource costs."""

    REPLACE = "replace"
    ADD = "add"


class CapabilityAmountFormula(SemanticModel):
    """Small deterministic formula for a transformed resource amount."""

    source: CapabilityAmountSource = Field(description="Input used by the amount formula.")
    fixed_amount: Optional[int] = Field(
        default=None,
        ge=0,
        description="Literal amount required when the source is fixed.",
    )
    offset: int = Field(default=0, description="Signed adjustment applied after reading the source.")
    minimum: int = Field(default=0, ge=0, description="Lower bound applied to the computed amount.")

    @model_validator(mode="after")
    def validate_formula(self) -> "CapabilityAmountFormula":
        """Require a literal only for fixed formulas."""
        if self.source is CapabilityAmountSource.FIXED and self.fixed_amount is None:
            raise ValueError("A fixed capability amount requires fixed_amount")
        if self.source is not CapabilityAmountSource.FIXED and self.fixed_amount is not None:
            raise ValueError("Only a fixed capability amount can include fixed_amount")
        return self


class CapabilityCostRewrite(SemanticModel):
    """Typed rewrite over one capability resource cost."""

    operation: CapabilityCostOperation = Field(description="Cost rewrite operation.")
    source_resource_id: Optional[str] = Field(
        default=None,
        description="Existing cost consumed or read by this rewrite.",
    )
    target_resource_id: str = Field(description="Resource receiving the computed amount.")
    amount: CapabilityAmountFormula = Field(description="Formula producing the target amount.")

    @model_validator(mode="after")
    def validate_rewrite(self) -> "CapabilityCostRewrite":
        """Reject replacements without an existing source resource."""
        if self.operation is CapabilityCostOperation.REPLACE and self.source_resource_id is None:
            raise ValueError("A replacement cost rewrite requires source_resource_id")
        if (
            self.amount.source is CapabilityAmountSource.SOURCE_RESOURCE
            and self.source_resource_id is None
        ):
            raise ValueError("A source-resource formula requires source_resource_id")
        if (
            self.operation is CapabilityCostOperation.REPLACE
            and self.source_resource_id == self.target_resource_id
        ):
            raise ValueError("A replacement cost rewrite must change the resource id")
        return self


class CapabilitySelector(SemanticModel):
    """Structural predicate selecting actor-owned capabilities."""

    action_categories: frozenset[str] = Field(
        default_factory=frozenset,
        description="Action categories accepted by the selector; empty accepts any.",
    )
    target_allocations: frozenset[TargetAllocation] = Field(
        default_factory=frozenset,
        description="Target allocation shapes accepted by the selector; empty accepts any.",
    )
    required_tags: frozenset[ActionTag] = Field(
        default_factory=frozenset,
        description="Semantic tags every selected capability must expose.",
    )
    required_cost_resource_ids: frozenset[str] = Field(
        default_factory=frozenset,
        description="Positive base costs every selected capability must contain.",
    )
    weapon_slots: frozenset[str] = Field(
        default_factory=frozenset,
        description="Configured weapon slots accepted by the selector; empty accepts any.",
    )


class CapabilityOutcomeAdjustment(SemanticModel):
    """Temporary stochastic-profile adjustment over matching capabilities."""

    selector: CapabilitySelector = Field(description="Capabilities whose outcomes are adjusted.")
    advantage_step_delta: int = Field(
        ge=-1,
        le=1,
        description="Signed one-step change to actor-baseline attack advantage.",
    )

    @model_validator(mode="after")
    def validate_adjustment(self) -> "CapabilityOutcomeAdjustment":
        """Reject adjustments that declare no stochastic change."""
        if self.advantage_step_delta == 0:
            raise ValueError("A capability outcome adjustment requires a non-zero change")
        return self


SelfSetupSemantics.model_rebuild()


class CapabilityTargetingRewrite(SemanticModel):
    """Replacement targeting shape produced by a capability transformation."""

    allocation: TargetAllocation = Field(description="Transformed target-allocation shape.")
    minimum_targets: int = Field(default=0, ge=0, description="Minimum transformed target count.")
    maximum_targets: Optional[int] = Field(default=None, ge=0, description="Maximum transformed target count.")
    allows_repeated_targets: Optional[bool] = Field(
        default=None,
        description="Replacement repeat policy; None preserves the capability's existing rule.",
    )

    @model_validator(mode="after")
    def validate_target_count(self) -> "CapabilityTargetingRewrite":
        """Reject a maximum smaller than the required selection count."""
        if self.maximum_targets is not None and self.maximum_targets < self.minimum_targets:
            raise ValueError("maximum_targets cannot be smaller than minimum_targets")
        return self


class CapabilityTransformation(SemanticModel):
    """Temporary typed rewrite over actor-owned action capabilities."""

    transformation_id: str = Field(description="Stable identity for the transformation rule.")
    selector: CapabilitySelector = Field(description="Capabilities eligible for the rewrite.")
    cost_rewrites: Tuple[CapabilityCostRewrite, ...] = Field(
        default_factory=tuple,
        description="Cost changes applied to matching capabilities.",
    )
    targeting_rewrite: Optional[CapabilityTargetingRewrite] = Field(
        default=None,
        description="Optional transformed target-allocation shape.",
    )
    consumed_by: CapabilitySelector = Field(
        description="Executed capability class that consumes the temporary transformation.",
    )
    maximum_applications: int = Field(default=1, ge=1, description="Uses available before the transformation expires.")

    @model_validator(mode="after")
    def validate_transformation(self) -> "CapabilityTransformation":
        """Require at least one observable capability rewrite."""
        if not self.cost_rewrites and self.targeting_rewrite is None:
            raise ValueError("A capability transformation requires a cost or targeting rewrite")
        return self


class ActionSemantics(SemanticModel):
    """Typed description of what a legal action may do, separate from its utility."""

    semantic_id: str = Field(description="Stable action-family identifier.")
    semantic_version: int = Field(default=1, ge=1, description="Version of this semantic contract.")
    provenance: ActionSemanticProvenance = Field(
        default_factory=ActionSemanticProvenance,
        description="Auditable origin and resolution strength of this contract.",
    )
    tags: frozenset[ActionTag] = Field(default_factory=frozenset, description="Stable semantic capabilities.")
    planning_preconditions: FactExpression = Field(
        default_factory=FactExpression.unknown,
        description="Abstract future-step conditions with explicit unknown handling.",
    )
    guaranteed_effects: Tuple[LogicalEffect, ...] = Field(
        default_factory=tuple,
        description="State changes expected whenever execution succeeds.",
    )
    conditional_effects: Tuple[ConditionalEffect, ...] = Field(
        default_factory=tuple,
        description="State changes guarded by additional conditions.",
    )
    stochastic_effects: Tuple[StochasticEffect, ...] = Field(
        default_factory=tuple,
        description="Roll- or contest-controlled state changes.",
    )
    target_effects: Tuple[TargetEffectSemantics, ...] = Field(
        default_factory=tuple,
        description="Per-target conditional branches used by mixed-effect actions.",
    )
    resource_effects: Tuple[ResourceEffect, ...] = Field(
        default_factory=tuple,
        description="Action-economy and named-resource changes.",
    )
    concentration_effect: Optional[ConcentrationEffect] = Field(
        default=None,
        description="Concentration transition when relevant.",
    )
    self_setup: Optional[SelfSetupSemantics] = Field(
        default=None,
        description="Self-directed combat setup and its explicit benefits or liabilities.",
    )
    spatial: Optional[SpatialSemantics] = Field(default=None, description="Spatial transition meaning.")
    topology_effects: Tuple[TopologyEffect, ...] = Field(
        default_factory=tuple,
        description="Traversability or visibility topology changes.",
    )
    information_effects: Tuple[InformationEffect, ...] = Field(
        default_factory=tuple,
        description="Possible changes to subjective knowledge.",
    )
    targeting: TargetingSemantics = Field(
        default_factory=TargetingSemantics,
        description="Target selection and allocation meaning.",
    )
    capability_transformations: Tuple[CapabilityTransformation, ...] = Field(
        default_factory=tuple,
        description="Temporary rewrites this action applies to actor-owned capabilities.",
        exclude_if=lambda value: not value,
    )


def unknown_action_semantics() -> ActionSemantics:
    """Return the explicit fallback for actions without registered meaning."""
    return ActionSemantics(
        semantic_id="action.unknown",
        provenance=ActionSemanticProvenance(
            kind=SemanticProvenanceKind.UNKNOWN,
            derivation="no_registered_or_structured_semantics",
            missing_inputs=(
                "exact_builder",
                "world_effect_profile",
                "target_effect_profile",
                "self_setup_profile",
                "recognized_category_contract",
            ),
        ),
        tags=frozenset({ActionTag.UNKNOWN}),
    )


def action_semantics_ref(semantics: ActionSemantics) -> str:
    """Return a deterministic reference for one complete semantic contract.

    Args:
        semantics: Contract to address inside a decision-epoch semantic catalog.

    Returns:
        Stable family-and-digest reference suitable for affordance rows.
    """
    return _cached_action_semantics_ref(cast(Hashable, semantics))


@lru_cache(maxsize=2048)
def _cached_action_semantics_ref(semantics: Hashable) -> str:
    """Hash one immutable semantic value and reuse its content address."""
    typed_semantics = cast(ActionSemantics, semantics)
    return action_semantics_payload_ref(typed_semantics.model_dump(mode="json"))


def clear_action_semantics_ref_cache() -> None:
    """Clear interned semantic content addresses between runtime worlds."""
    _cached_action_semantics_ref.cache_clear()


def action_semantics_payload_ref(payload: Mapping[str, object]) -> str:
    """Return the content address for a serialized action semantic contract.

    Args:
        payload: JSON-compatible semantic contract payload.

    Returns:
        Stable family-and-digest reference without constructing another model.
    """
    canonical_payload = cast(
        dict[str, object],
        _canonicalize_semantic_payload(dict(payload)),
    )
    tags = canonical_payload.get("tags", [])
    if not isinstance(tags, (list, tuple, set, frozenset)):
        raise ValueError("Action semantic tags must be a collection")
    canonical_payload["tags"] = sorted(str(tag) for tag in tags)
    canonical = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = sha256(canonical.encode("ascii")).hexdigest()[:16]
    semantic_id = str(canonical_payload.get("semantic_id", "action.unknown"))
    semantic_version_value = canonical_payload.get("semantic_version", 1)
    if type(semantic_version_value) is not int:
        raise ValueError("Action semantic version must be an integer")
    semantic_version = semantic_version_value
    return f"{semantic_id}@v{semantic_version}:{digest}"


_UNORDERED_SEMANTIC_FIELDS = frozenset({
    "action_categories",
    "active_condition_semantic_keys",
    "affected_relationships",
    "condition_semantic_keys",
    "required_cost_resource_ids",
    "required_tags",
    "resistance_damage_types",
    "tags",
    "target_allocations",
    "weapon_slots",
})


def _canonicalize_semantic_payload(value: object, field_name: Optional[str] = None) -> object:
    """Normalize unordered semantic collections without reordering effect sequences.

    Pydantic serializes ``set`` and ``frozenset`` fields as JSON arrays. Their
    process-dependent iteration order must therefore be restored from the
    ActionSemantics schema before content addressing.
    """
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize_semantic_payload(item, str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_canonicalize_semantic_payload(item) for item in value]
        if field_name in _UNORDERED_SEMANTIC_FIELDS:
            return sorted(
                items,
                key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
            )
        return items
    return value
