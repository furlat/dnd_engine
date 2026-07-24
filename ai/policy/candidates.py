"""Semantic tactical candidate generation over session-subjective facts."""

from __future__ import annotations

from collections.abc import Iterable
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from ai.knowledge.models import TargetEffectBlockHypothesis
from server.agent_protocol.observation import (
    AdjacentOffset,
    ObservationEntityFact,
    SpatialDomainKnowledge,
)
from ai.policy.contracts import (
    CapabilityModelStatus,
    CapabilityProjectionScope,
    CapabilityRangeState,
    CapabilityResourceRequirement,
    CapabilityTargetProjection,
    ControlPreservationEvidence,
    ControlPreservationTargetEvidence,
    DamageBlockerEvidence,
    DamageOutcomeEvidence,
    EndTurnIntent,
    ExecuteIntent,
    ExplorationEvidence,
    HealingOutcomeEvidence,
    PolicyContext,
    PolicyEvidence,
    PolicyGoal,
    PolicyProposal,
    RememberedContactSearchState,
    SelfSetupOutcomeEvidence,
    SpacingEvidence,
    TargetApplicationEvidence,
    TargetEffectOutcomeEvidence,
    TargetPlanEvidence,
    UtilityComponent,
)
from dnd.core.condition_types import ConditionAgencyDenial, ConditionRemovalTrigger
from ai.policy.economy import (
    action_economy_opportunity_cost,
    capability_is_turn_refreshable,
    capability_persistent_affordability_reasons,
    capability_persistent_resource_requirements,
)
from ai.knowledge.topology import (
    KnownLineOfSightWorkspace,
    grid_distance_feet,
    known_line_of_sight,
)
from ai.policy.outcomes import (
    DamageOutcomeWorkspace,
    SubjectiveDamageEstimate,
    estimate_damage_outcome,
    outcome_application_key,
    outcome_profile_key,
)
from ai.knowledge.replay import entity_fact_replay_token, position_replay_token
from server.agent_protocol.control import (
    ActionAffordance,
    ActionCapability,
    ActionOutcomeProfile,
    ActionTarget,
    OpportunityAttackExposure,
    OutcomeApplicationScope,
    OutcomeResolution,
)
from server.agent_protocol.semantics import (
    ActionSemantics,
    ActionTag,
    AffectedRelationship,
    ConcentrationOperation,
    EffectCertainty,
    EffectDisposition,
    EffectOperation,
    InformationEffect,
    InformationOperation,
    OutcomeKind,
    ResourceOperation,
    D20CheckMode,
    SelfSetupDuration,
    SelfSetupSemantics,
    TargetAllocation,
    TargetEffectSemantics,
    TruthValue,
    WorldEffectAnchor,
    WorldEffectScope,
    evaluate_fact_expression,
)


DIRECT_DAMAGE_TAGS = frozenset(
    {
        ActionTag.DAMAGE_SINGLE_TARGET,
        ActionTag.DAMAGE_MULTI_TARGET,
        ActionTag.DAMAGE_AREA,
    }
)

AREA_DAMAGE_FRONTIER_TAGS = frozenset(
    {
        ActionTag.DAMAGE_AREA,
        ActionTag.ATTACK_SPELL,
        ActionTag.RESOURCE_SPEND,
    }
)

POSITIVE_INFORMATION_OPERATIONS = frozenset({
    InformationOperation.REVEAL_FRONTIER,
    InformationOperation.EXPLORE_REGION,
    InformationOperation.CHANGE_LIGHT,
    InformationOperation.REVEAL_REGION,
    InformationOperation.GRANT_SENSE,
})

_INFORMATION_CERTAINTY_WEIGHT = {
    EffectCertainty.GUARANTEED: 1.0,
    EffectCertainty.CONDITIONAL: 0.75,
    EffectCertainty.STOCHASTIC: 0.5,
    EffectCertainty.POTENTIAL: 0.25,
}


@dataclass(frozen=True)
class _InformationProjection:
    """Local subjective gain projected from one typed world-effect row."""

    anchor_position: tuple[int, int]
    operations: tuple[InformationOperation, ...]
    strongest_certainty: EffectCertainty
    effect_radius_feet: Optional[int]
    unknown_positions: frozenset[tuple[int, int]]
    obscured_positions: frozenset[tuple[int, int]]
    weighted_unknown_count: float
    weighted_obscured_count: float
    granted_sense_types: tuple[str, ...]
    recipient_uuid: Optional[str]


@dataclass(frozen=True)
class PolicyCandidateSet:
    """Reusable tactical candidates computed once for one policy context."""

    direct_damage: tuple[PolicyProposal, ...]
    healing: tuple[PolicyProposal, ...]
    control: tuple[PolicyProposal, ...]
    control_preservation: tuple[PolicyProposal, ...]
    target_effects: tuple[PolicyProposal, ...]
    self_setup: tuple[PolicyProposal, ...]
    spacing: tuple[PolicyProposal, ...]
    exploration: tuple[PolicyProposal, ...]


@dataclass(frozen=True)
class _DamageFeatures:
    """Lightweight score inputs used to group equivalent legal rows."""

    hostile_affected: tuple[str, ...]
    controlled_affected: tuple[str, ...]
    allied_affected: tuple[str, ...]
    additional_targets: tuple[str, ...]
    wounded_pressure: float
    expected_hp_loss: Optional[float]
    defeat_probability: Optional[float]
    expected_defeats: Optional[float]
    nonzero_probability: Optional[float]
    expected_waste: Optional[float]
    expected_enemy_agency_restored: float
    penalize_expected_waste: bool
    resource_cost: float
    concentration_replacement: bool
    replay_key: tuple[str, ...]
    target_plan: TargetPlanEvidence
    damage_outcomes: tuple[DamageOutcomeEvidence, ...]


@dataclass
class _DamageCandidateGroup:
    """One policy-distinct choice and its equivalent legal row count."""

    row: ActionAffordance
    semantic_tags: frozenset[ActionTag]
    features: _DamageFeatures
    equivalent_rows: int = 1


@dataclass
class _DamageCandidateSeed:
    """Decision-equivalent legal rows before outcome evidence is materialized."""

    row: ActionAffordance
    semantics: ActionSemantics
    semantic_tags: frozenset[ActionTag]
    affected_entity_uuids: tuple[str, ...]
    hostile_affected: tuple[str, ...]
    controlled_affected: tuple[str, ...]
    allied_affected: tuple[str, ...]
    additional_targets: tuple[str, ...]
    equivalent_rows: int = 1
    affected_entity_uuid_set: frozenset[str] = field(init=False, repr=False)
    hostile_affected_set: frozenset[str] = field(init=False, repr=False)
    controlled_affected_set: frozenset[str] = field(init=False, repr=False)
    allied_affected_set: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Materialize reusable set projections once per candidate seed."""
        self.affected_entity_uuid_set = frozenset(self.affected_entity_uuids)
        self.hostile_affected_set = frozenset(self.hostile_affected)
        self.controlled_affected_set = frozenset(self.controlled_affected)
        self.allied_affected_set = frozenset(self.allied_affected)


@dataclass
class _SpacingCandidateSeed:
    """Lightweight representative for one policy-distinct movement risk class."""

    row: ActionAffordance
    semantics: ActionSemantics
    projection: CapabilityTargetProjection
    reason: str
    next_enemy_distance: int
    next_ally_distance: Optional[int]
    next_enemy_deficit: int
    next_ally_deficit: Optional[int]
    hostile_deficit_reduction: int
    ally_deficit_reduction: int
    offensive_range_deficit: Optional[int]
    movement_cost: Optional[int]
    hazardous: bool
    opportunity_attack_exposures: tuple[OpportunityAttackExposure, ...]
    economy_opportunity_cost: float
    score: float
    represented_rows: int = 1

    @property
    def capability_id(self) -> str:
        """Return the selected capability identity."""
        return self.projection.capability_id

    @property
    def spacing_floor(self) -> int:
        """Return the selected preferred minimum in cells."""
        return self.projection.preferred_minimum_range_feet // 5

    @property
    def normal_attack_range(self) -> int:
        """Return the selected normal range in cells."""
        return self.projection.normal_range_feet // 5

    @property
    def future_pressure_value(self) -> float:
        """Return modeled pressure or no numeric contribution when unresolved."""
        return self.projection.pressure_value or 0.0


@dataclass(frozen=True)
class _ControlFeatures:
    """Subjective and semantic inputs for one control choice."""

    hostile_affected: tuple[str, ...]
    controlled_affected: tuple[str, ...]
    additional_targets: tuple[str, ...]
    healthy_target_value: float
    hard_control: bool
    soft_control: bool
    resource_cost: float
    concentration_replacement: bool
    replay_key: tuple[str, ...]
    target_plan: TargetPlanEvidence


@dataclass
class _ControlCandidateGroup:
    """One policy-distinct control choice and equivalent legal row count."""

    row: ActionAffordance
    semantic_tags: frozenset[ActionTag]
    features: _ControlFeatures
    representative_key: tuple[tuple[int, int, int], ...]
    equivalent_rows: int = 1


@dataclass
class _ControlCandidateSeed:
    """Lightweight control choice before evidence materialization."""

    row: ActionAffordance
    semantic_tags: frozenset[ActionTag]
    hostile_affected: tuple[str, ...]
    controlled_affected: tuple[str, ...]
    additional_targets: tuple[str, ...]
    healthy_target_value: float
    hard_control: bool
    soft_control: bool
    resource_cost: float
    concentration_replacement: bool
    representative_key: tuple[tuple[int, int, int], ...]
    dominance_scope: Optional[tuple[object, ...]]
    equivalent_rows: int = 1
    hostile_affected_set: frozenset[str] = field(init=False, repr=False)
    controlled_affected_set: frozenset[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Materialize reusable set projections once per control seed."""
        self.hostile_affected_set = frozenset(self.hostile_affected)
        self.controlled_affected_set = frozenset(self.controlled_affected)


@dataclass(frozen=True)
class _TargetEffectRecipient:
    """One subjectively valid recipient and the matching semantic branch."""

    entity_uuid: str
    effect: TargetEffectSemantics
    relationship: str
    replay_token: str


@dataclass(frozen=True)
class _TargetEffectFeatures:
    """Inspectable score inputs for one mixed target-effect allocation."""

    recipients: tuple[_TargetEffectRecipient, ...]
    hostile_affected: tuple[str, ...]
    controlled_affected: tuple[str, ...]
    allied_affected: tuple[str, ...]
    additional_targets: tuple[str, ...]
    resource_cost: float
    concentration_replacement: bool
    replay_key: tuple[str, ...]
    target_plan: TargetPlanEvidence


OutcomeCacheKey = tuple[object, ...]
AllocationCacheKey = tuple[object, ...]


@dataclass
class _OutcomeCache:
    """Decision-scoped estimates and their shared exact-distribution workspace."""

    values: dict[OutcomeCacheKey, Optional[SubjectiveDamageEstimate]] = field(default_factory=dict)
    workspace: DamageOutcomeWorkspace = field(
        default_factory=lambda: DamageOutcomeWorkspace(shared_value_cache=True),
    )


@dataclass(frozen=True)
class _OutcomeSummary:
    """Aggregate and per-target outcome evidence for one allocation."""

    expected_hp_loss: Optional[float]
    defeat_probability: Optional[float]
    expected_defeats: Optional[float]
    nonzero_probability: Optional[float]
    expected_waste: Optional[float]
    applications: tuple[TargetApplicationEvidence, ...]
    outcomes: tuple[DamageOutcomeEvidence, ...]


def build_policy_candidate_set(context: PolicyContext) -> PolicyCandidateSet:
    """Build shared tactical candidates once for one aligned epoch."""
    direct_damage = direct_damage_candidates(context)
    self_setup = (
        *self_setup_candidates(context),
        *defensive_action_candidates(context),
    )
    return PolicyCandidateSet(
        direct_damage=direct_damage,
        healing=fixed_healing_candidates(context),
        control=control_candidates(context),
        control_preservation=control_preservation_candidates(
            context,
            direct_damage,
        ),
        target_effects=target_effect_candidates(context),
        self_setup=tuple(sorted(self_setup, key=_proposal_replay_order_key)),
        spacing=spacing_candidates(
            context,
            has_immediate_pressure=bool(direct_damage),
        ),
        exploration=exploration_candidates(context),
    )


def control_preservation_candidates(
    context: PolicyContext,
    direct_damage: tuple[PolicyProposal, ...],
) -> tuple[PolicyProposal, ...]:
    """Yield after establishing fragile full control when damage would undo it."""
    context.validate_alignment()
    encounter = context.world.encounter
    if encounter is None or encounter.turn_started_source_event_cursor is None:
        return tuple()

    at_risk: dict[str, ControlPreservationTargetEvidence] = {}
    for proposal in direct_damage:
        for outcome in proposal.evidence.damage_outcomes:
            if outcome.expected_enemy_agency_restored <= 0:
                continue
            condition_keys = _newly_applied_damage_ending_condition_keys(
                context,
                outcome.entity_uuid,
                encounter.turn_started_source_event_cursor,
            )
            if not condition_keys:
                continue
            previous = at_risk.get(outcome.entity_uuid)
            expected = max(
                outcome.expected_enemy_agency_restored,
                previous.expected_enemy_agency_preserved if previous is not None else 0.0,
            )
            at_risk[outcome.entity_uuid] = ControlPreservationTargetEvidence(
                entity_uuid=outcome.entity_uuid,
                condition_semantic_keys=condition_keys,
                expected_enemy_agency_preserved=expected,
            )
    if not at_risk:
        return tuple()

    targets = tuple(
        at_risk[entity_uuid]
        for entity_uuid in sorted(
            at_risk,
            key=lambda value: _entity_uuid_replay_token(context, value),
        )
    )
    expected_preserved = sum(
        target.expected_enemy_agency_preserved
        for target in targets
    )
    components = (
        _component(
            "legal_control_preservation",
            1.0,
            100.0,
            "ending the turn is the legal protocol action that cannot break control",
        ),
        _component(
            "newly_established_enemy_agency_denial",
            expected_preserved,
            20.0,
            "future action denial retained by preserving control through the target's next turn",
        ),
    )
    return (PolicyProposal(
        intent=EndTurnIntent(),
        goal=PolicyGoal.CONTROL_PRESERVATION,
        source_node="Control/PreserveNewControl",
        reason="yield_after_establishing_damage_ending_control",
        score=sum(component.contribution for component in components),
        replay_key=(
            "control-preservation",
            *(
                _entity_uuid_replay_token(context, target.entity_uuid)
                for target in targets
            ),
        ),
        utility_components=components,
        semantic_tags=frozenset({ActionTag.TURN_END}),
        evidence=PolicyEvidence(
            control_preservation=ControlPreservationEvidence(targets=targets),
        ),
    ),)


def fixed_healing_candidates(context: PolicyContext) -> tuple[PolicyProposal, ...]:
    """Return deterministic healing proposals over known healable recipients."""
    context.validate_alignment()
    eligible_entities = (
        set(context.facts.contacts.controlled_entity_uuids)
        | set(context.facts.contacts.visible_ally_uuids)
    )
    proposals: list[PolicyProposal] = []
    row_ids = context.facts.affordances.row_ids_by_tag.get(
        ActionTag.SUPPORT_HEAL,
        tuple(),
    )
    for row_id in sorted(row_ids):
        row = context.facts.affordances.by_id.get(row_id)
        semantics = context.facts.affordances.semantics_by_row_id.get(row_id)
        if (
            row is None
            or semantics is None
            or not context.execution_constraints.allows(row)
            or not row.can_afford
            or row.cost.affordability == "unaffordable"
        ):
            continue
        healing = _literal_healing_effect(semantics)
        if healing is None:
            continue
        fact_id, raw_healing = healing
        target_uuid = _healing_target_uuid(context, row, fact_id)
        if target_uuid is None or target_uuid not in eligible_entities:
            continue
        entity = context.world.known_entities.get(target_uuid)
        if (
            entity is None
            or entity.normal_hp is None
            or entity.max_hp is None
            or entity.max_hp <= 0
            or entity.is_dead is True
            or entity.healing_blocked is not False
        ):
            continue
        missing_hp = max(0.0, float(entity.max_hp - entity.normal_hp))
        restored = min(raw_healing, missing_hp)
        if restored <= 0:
            continue
        waste = max(0.0, raw_healing - restored)
        health_fraction = max(
            0.0,
            min(1.0, float(entity.normal_hp) / float(entity.max_hp)),
        )
        critical_deficit = max(0.0, 0.5 - health_fraction)
        finite_item_cost = float(sum(row.cost.item_charge_costs.values()))
        limited_resource_cost = float(
            (row.cost.spell_slot_cost or 0)
            + sum(row.cost.resource_costs.values())
        )
        components = (
            _component(
                "legal_fixed_healing",
                1.0,
                100.0,
                "server-issued affordable healing affordance",
            ),
            _component(
                "expected_hp_restored",
                restored,
                2.0,
                "literal restoration capped by known missing normal hit points",
            ),
            _component(
                "critical_survival_value",
                critical_deficit,
                80.0,
                "known normal-HP deficit below half maximum",
            ),
            _component(
                "expected_healing_waste",
                waste,
                -1.0,
                "literal healing beyond known missing normal hit points",
            ),
            _component(
                "action_economy_opportunity_cost",
                action_economy_opportunity_cost(row.cost),
                -4.0,
                "typed loss of flexible turn economy",
            ),
            _component(
                "limited_resource_cost",
                limited_resource_cost,
                -2.0,
                "known spell-slot and named-resource expenditure",
            ),
            _component(
                "finite_item_charge_cost",
                finite_item_cost,
                -4.0,
                "known finite item units consumed",
            ),
        )
        evidence = HealingOutcomeEvidence(
            entity_uuid=target_uuid,
            current_normal_hp=entity.normal_hp,
            maximum_hp=entity.max_hp,
            expected_raw_healing=raw_healing,
            expected_hp_restored=restored,
            expected_waste=waste,
            model_scope="literal guaranteed healing plus visible recipient health and typed costs",
        )
        proposals.append(PolicyProposal(
            intent=ExecuteIntent(row_id=row.row_id),
            goal=PolicyGoal.SURVIVAL_RECOVERY,
            source_node="Recovery/FixedHealing",
            reason=(
                f"restore {restored:g} known normal HP with "
                f"{waste:g} expected waste"
            ),
            score=sum(component.contribution for component in components),
            replay_key=_action_replay_key(context, row, tuple()),
            utility_components=components,
            semantic_tags=semantics.tags,
            evidence=PolicyEvidence(healing=evidence),
        ))
    return tuple(sorted(proposals, key=_proposal_replay_order_key))


def _literal_healing_effect(
    semantics: ActionSemantics,
) -> Optional[tuple[str, float]]:
    """Return one positive literal HP increase from guaranteed semantics."""
    for effect in semantics.guaranteed_effects:
        if (
            effect.fact_id in {"actor.hp", "selected_target.hp"}
            and effect.operation is EffectOperation.INCREASE
            and isinstance(effect.value, (int, float))
            and not isinstance(effect.value, bool)
            and effect.value > 0
        ):
            return effect.fact_id, float(effect.value)
    return None


def _healing_target_uuid(
    context: PolicyContext,
    row: ActionAffordance,
    fact_id: str,
) -> Optional[str]:
    """Resolve the recipient from typed effect scope and executable targets."""
    if fact_id == "actor.hp":
        return context.facts.actor.actor_uuid
    return next(
        (
            target.target_uuid
            for target in row.targets
            if target.target_uuid is not None
        ),
        None,
    )


RANGED_SPACING_FLOOR_CELLS = 6
ALLY_SPACING_FLOOR_CELLS = 5
_FRONTIER_NEIGHBORS = tuple(
    (dx, dy)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    if (dx, dy) != (0, 0)
)


def self_setup_candidates(context: PolicyContext) -> tuple[PolicyProposal, ...]:
    """Return durable self-setup proposals grounded in typed effect dimensions."""
    context.validate_alignment()
    if not context.facts.contacts.visible_hostile_uuids:
        return tuple()

    proposals: list[PolicyProposal] = []
    row_ids = context.facts.affordances.row_ids_by_tag.get(ActionTag.SETUP_SELF, tuple())
    for row_id in row_ids:
        row = context.facts.affordances.by_id.get(row_id)
        semantics = context.facts.affordances.semantics_by_row_id.get(row_id)
        setup = semantics.self_setup if semantics is not None else None
        if (
            row is None
            or semantics is None
            or setup is None
            or setup.duration is not SelfSetupDuration.UNTIL_REMOVED
            or _self_setup_effect_may_already_be_active(context, semantics)
            or not row.can_afford
            or row.cost.affordability == "unaffordable"
            or not context.execution_constraints.allows(row)
        ):
            continue

        resource_cost = float(
            (row.cost.spell_slot_cost or row.cast_at_level or 0)
            + sum(row.cost.resource_costs.values())
        )
        finite_item_charge_cost = float(sum(row.cost.item_charge_costs.values()))
        retention_probability = _first_setup_maintenance_success_probability(setup)
        components = (
            _component(
                "legal_self_setup",
                1.0,
                80.0,
                "server-issued durable setup affordance during visible combat",
            ),
            _component(
                "durable_setup",
                retention_probability,
                15.0,
                "expected retention after the first disclosed maintenance boundary",
            ),
            _component(
                "weapon_damage_setup",
                float(setup.increases_weapon_damage) * retention_probability,
                15.0,
                "typed setup increases subsequent weapon damage",
            ),
            _component(
                "damage_resistance_setup",
                float(bool(setup.resistance_damage_types)) * retention_probability,
                20.0,
                "typed setup grants at least one damage resistance",
            ),
            _component(
                "bonus_attack_access",
                float(setup.grants_bonus_action_attack) * retention_probability,
                20.0,
                "typed setup unlocks a bonus-action attack capability",
            ),
            _component(
                "outgoing_attack_advantage",
                float(setup.grants_outgoing_attack_advantage) * retention_probability,
                15.0,
                "typed setup grants advantage on actor attacks",
            ),
            _component(
                "incoming_attack_disadvantage",
                float(setup.grants_incoming_attack_disadvantage) * retention_probability,
                20.0,
                "typed setup imposes disadvantage on attacks against the actor",
            ),
            _component(
                "incoming_attack_advantage_liability",
                float(setup.grants_incoming_attack_advantage) * retention_probability,
                -15.0,
                "typed setup grants attackers advantage against the actor",
            ),
            _component(
                "armor_class_setup",
                float(setup.armor_class_bonus) * retention_probability,
                5.0,
                "known armor-class bonus while the setup persists",
            ),
            _component(
                "movement_speed_setup",
                max(0.0, setup.movement_speed_multiplier - 1.0) * retention_probability,
                8.0,
                "known multiplicative movement increase",
            ),
            _component(
                "extra_action_access",
                float(setup.extra_actions_per_turn) * retention_probability,
                25.0,
                "typed setup grants additional flexible actions per turn",
            ),
            _component(
                "invisibility_setup",
                float(setup.grants_invisibility) * retention_probability,
                10.0,
                "typed setup establishes subjective invisibility",
            ),
            _component(
                "removal_incapacitation_liability",
                float(setup.incapacitates_on_removal) * retention_probability,
                -10.0,
                "typed setup carries an incapacitating removal liability",
            ),
            _component(
                "first_maintenance_retention_probability",
                retention_probability,
                0.0,
                "exact d20 probability of retaining the setup after its first disclosed trigger",
            ),
            _component(
                "action_economy_opportunity_cost",
                action_economy_opportunity_cost(row.cost),
                -4.0,
                "typed loss of flexible action, bonus-action, reaction, or granted-attack economy",
            ),
            _component(
                "limited_resource_cost",
                resource_cost,
                -2.0,
                "known spell-slot and named-resource expenditure",
            ),
            _component(
                "finite_item_charge_cost",
                finite_item_charge_cost,
                -4.0,
                "finite item charges consumed by the setup",
            ),
        )
        proposals.append(PolicyProposal(
            intent=ExecuteIntent(row_id=row.row_id),
            goal=PolicyGoal.SELF_SETUP,
            source_node="Preparation/DurableSelfSetup",
            reason="establish_durable_combat_setup",
            score=sum(component.contribution for component in components),
            replay_key=(row.semantic_key, semantics.semantic_id),
            utility_components=components,
            semantic_tags=semantics.tags,
            evidence=PolicyEvidence(
                self_setup=SelfSetupOutcomeEvidence(
                    semantic_id=semantics.semantic_id,
                    duration=setup.duration,
                    maximum_duration_rounds=setup.maximum_duration_rounds,
                    condition_fact_ids=tuple(sorted(
                        effect.fact_id
                        for effect in semantics.guaranteed_effects
                        if effect.fact_id.startswith("actor.condition.")
                    )),
                    active_condition_semantic_keys=tuple(sorted(
                        setup.active_condition_semantic_keys
                    )),
                    armor_class_bonus=setup.armor_class_bonus,
                    movement_speed_multiplier=setup.movement_speed_multiplier,
                    extra_actions_per_turn=setup.extra_actions_per_turn,
                    grants_outgoing_attack_advantage=setup.grants_outgoing_attack_advantage,
                    grants_incoming_attack_disadvantage=setup.grants_incoming_attack_disadvantage,
                    grants_invisibility=setup.grants_invisibility,
                    incapacitates_on_removal=setup.incapacitates_on_removal,
                    maintenance=setup.maintenance,
                    first_maintenance_success_probability=(
                        retention_probability
                        if setup.maintenance is not None
                        else None
                    ),
                )
            ),
        ))
    return tuple(sorted(proposals, key=_proposal_replay_order_key))


def defensive_action_candidates(context: PolicyContext) -> tuple[PolicyProposal, ...]:
    """Return immediate defensive proposals grounded in typed self-defense tags."""
    context.validate_alignment()
    facts = context.facts
    if not facts.contacts.visible_hostile_uuids:
        return tuple()

    actor_hp = facts.actor.normal_hp if facts.actor.normal_hp is not None else facts.actor.hp
    max_hp = facts.actor.max_hp
    missing_fraction = (
        max(0.0, min(1.0, 1.0 - (actor_hp / max_hp)))
        if actor_hp is not None and max_hp not in (None, 0)
        else 0.0
    )
    visible_hostile_pressure = min(3.0, float(len(facts.contacts.visible_hostile_uuids)))
    adjacent_hostile_pressure = _adjacent_visible_hostile_count(context)
    direct_damage_available = bool(facts.affordances.row_ids_by_tag.get(ActionTag.DAMAGE_SINGLE_TARGET, tuple()))
    proposals: list[PolicyProposal] = []
    for row_id in facts.affordances.row_ids_by_tag.get(ActionTag.DEFENSE_SELF, tuple()):
        row = facts.affordances.by_id.get(row_id)
        semantics = facts.affordances.semantics_by_row_id.get(row_id)
        if (
            row is None
            or semantics is None
            or ActionTag.SETUP_SELF in semantics.tags
            or not _has_immediate_defensive_condition(semantics)
            or not row.can_afford
            or row.cost.affordability == "unaffordable"
            or not context.execution_constraints.allows(row)
            or _defensive_effect_may_already_be_active(context, semantics)
        ):
            continue

        components = (
            _component(
                "legal_defensive_action",
                1.0,
                70.0,
                "server-issued self-defense affordance during visible combat",
            ),
            _component(
                "visible_hostile_pressure",
                visible_hostile_pressure,
                12.0,
                "visible hostile contacts that can exploit an undefended actor",
            ),
            _component(
                "low_hp_survival_urgency",
                missing_fraction,
                90.0,
                "known missing-hit-point fraction raises immediate defensive value",
            ),
            _component(
                "engaged_damage_opportunity_cost",
                adjacent_hostile_pressure if direct_damage_available else 0.0,
                -55.0,
                "adjacent visible hostile pressure should usually be reduced before spending an action on Dodge",
            ),
            _component(
                "action_economy_opportunity_cost",
                action_economy_opportunity_cost(row.cost),
                -4.0,
                "typed loss of flexible action, bonus-action, reaction, or granted-attack economy",
            ),
            _component(
                "limited_resource_cost",
                float((row.cost.spell_slot_cost or row.cast_at_level or 0) + sum(row.cost.resource_costs.values())),
                -2.0,
                "known spell-slot and named-resource expenditure",
            ),
            _component(
                "finite_item_charge_cost",
                float(sum(row.cost.item_charge_costs.values())),
                -4.0,
                "finite item charges consumed by the defense",
            ),
        )
        proposals.append(PolicyProposal(
            intent=ExecuteIntent(row_id=row.row_id),
            goal=PolicyGoal.SELF_SETUP,
            source_node="Preparation/ImmediateDefense",
            reason="take_immediate_self_defense",
            score=sum(component.contribution for component in components),
            replay_key=(row.semantic_key, semantics.semantic_id),
            utility_components=components,
            semantic_tags=semantics.tags,
        ))
    return tuple(sorted(proposals, key=_proposal_replay_order_key))


def _adjacent_visible_hostile_count(context: PolicyContext) -> float:
    """Return visible hostiles adjacent to the actor in subjective grid cells."""
    actor_position = context.facts.actor.position
    if actor_position is None:
        return 0.0
    count = 0
    for entity_uuid in context.facts.contacts.visible_hostile_uuids:
        entity = context.world.known_entities.get(entity_uuid)
        if entity is None or entity.position is None:
            continue
        distance = abs(actor_position[0] - entity.position[0]) + abs(actor_position[1] - entity.position[1])
        if distance <= 1:
            count += 1
    return float(count)


def _first_setup_maintenance_success_probability(setup: SelfSetupSemantics) -> float:
    """Return exact first-check retention probability for typed setup semantics."""
    maintenance = setup.maintenance
    if maintenance is None:
        return 1.0
    successful_faces = sum(
        1
        for natural in range(1, 21)
        if natural + maintenance.check_bonus >= maintenance.initial_dc
    )
    single_roll_probability = successful_faces / 20.0
    if maintenance.check_advantage is D20CheckMode.ADVANTAGE:
        return 1.0 - (1.0 - single_roll_probability) ** 2
    if maintenance.check_advantage is D20CheckMode.DISADVANTAGE:
        return single_roll_probability ** 2
    return single_roll_probability


def exploration_candidates(context: PolicyContext) -> tuple[PolicyProposal, ...]:
    """Return typed legal proposals that can change subjective knowledge.

    Exploration is considered only without a visible hostile or known closed
    door. Combat-enabling and door routines own those more specific states.
    Candidate geometry and effects come solely from server-issued rows, typed
    action semantics, retained subjective tiles, and remembered contacts.

    Args:
        context: Aligned subjective policy context for one decision epoch.

    Returns:
        Deterministically ordered frontier or investigation proposals.
    """
    context.validate_alignment()
    facts = context.facts
    actor_position = facts.actor.position
    economy = facts.actor.economy
    if (
        actor_position is None
        or economy is None
        or facts.contacts.visible_hostile_uuids
        or facts.objects.closed_door_uuids
    ):
        return tuple()
    known_positions = {
        tile.position
        for tile in context.world.known_tiles.values()
    }
    frontier_positions = _subjective_frontier_positions(
        context,
        known_positions,
    )
    obscured_positions = frozenset(
        tile.position
        for tile in context.world.known_tiles.values()
        if tile.light_level is not None and tile.light_level <= 2
    )
    remembered = tuple(
        entity
        for entity_uuid in facts.contacts.remembered_hostile_uuids
        for entity in [context.world.known_entities.get(entity_uuid)]
        if entity is not None and entity.position is not None and entity.is_dead is not True
    )
    remembered_searches = {
        state.entity_uuid: state
        for state in context.control_memory.remembered_contact_searches
    }
    proposals: list[PolicyProposal] = []
    information_row_ids = sorted(set(
        facts.affordances.row_ids_by_tag.get(ActionTag.INFORMATION_EXPLORE, tuple())
        + facts.affordances.row_ids_by_tag.get(ActionTag.INFORMATION_REVEAL, tuple())
    ))
    for row_id in information_row_ids:
        row = facts.affordances.by_id.get(row_id)
        semantics = facts.affordances.semantics_by_row_id.get(row_id)
        if (
            row is None
            or semantics is None
            or not context.execution_constraints.allows(row)
            or not row.can_afford
            or not semantics.tags & {
                ActionTag.INFORMATION_EXPLORE,
                ActionTag.INFORMATION_REVEAL,
            }
        ):
            continue

        if ActionTag.MOVEMENT_VOLUNTARY in semantics.tags:
            proposals.extend(_movement_exploration_candidates(
                row,
                semantics,
                actor_position,
                economy.movement_remaining,
                known_positions,
                frontier_positions,
                remembered,
                remembered_searches,
                facts.topology.slow_positions,
                facts.navigation.visited_positions,
            ))
            continue

        positive_effects = tuple(
            effect
            for effect in semantics.information_effects
            if effect.operation in POSITIVE_INFORMATION_OPERATIONS
        )
        if not positive_effects:
            continue
        targets: tuple[Optional[ActionTarget], ...] = tuple(row.targets) or (None,)
        for target in targets:
            projection = _project_information_gain(
                context,
                target,
                positive_effects,
                frontier_positions,
                obscured_positions,
            )
            if projection is None:
                continue
            limited_resource_cost = _limited_resource_cost(row)
            replaces_concentration = (
                facts.actor.is_concentrating and row.requires_concentration
            )
            components = (
                _component(
                    "information_gathering_action",
                    1.0,
                    30.0,
                    "server-issued semantics declare a positive subjective information change",
                ),
                _component(
                    "projected_unknown_positions",
                    projection.weighted_unknown_count,
                    5.0,
                    "typed effect geometry intersects positions outside accumulated subjective knowledge",
                ),
                _component(
                    "projected_obscured_positions",
                    projection.weighted_obscured_count,
                    2.0,
                    "typed illumination intersects known dark or dim positions",
                ),
                _component(
                    "new_sense_modes",
                    float(len(projection.granted_sense_types)),
                    12.0,
                    "typed sense grants add a mode absent from the controlled observer",
                ),
                _component(
                    "action_economy_opportunity_cost",
                    action_economy_opportunity_cost(row.cost),
                    -4.0,
                    "preserve flexible action economy for facts revealed by the effect",
                ),
                _component(
                    "limited_resource_cost",
                    limited_resource_cost,
                    -2.0,
                    "prefer the least finite resource expenditure for equivalent information",
                ),
                _component(
                    "concentration_replacement",
                    float(replaces_concentration),
                    -20.0,
                    "preserve an observed active concentration effect when information gain is equal",
                ),
            )
            proposals.append(PolicyProposal(
                intent=ExecuteIntent(row_id=row.row_id),
                goal=PolicyGoal.INFORMATION_GATHERING,
                source_node="InformationGathering/WorldEffect",
                reason="project_typed_information_gain",
                score=sum(component.contribution for component in components),
                replay_key=(
                    row.semantic_key,
                    position_replay_token(projection.anchor_position),
                    f"recipient={projection.recipient_uuid or 'none'}",
                    f"limited-resource={limited_resource_cost:g}",
                ),
                utility_components=components,
                semantic_tags=semantics.tags,
                evidence=PolicyEvidence(exploration=ExplorationEvidence(
                    anchor_position=projection.anchor_position,
                    movement_cost=0,
                    unknown_frontier_count=len(projection.unknown_positions),
                    hazardous_route=False,
                    slow_path_cells=0,
                    information_operations=projection.operations,
                    effect_certainty=projection.strongest_certainty,
                    effect_radius_feet=projection.effect_radius_feet,
                    projected_unknown_position_count=len(projection.unknown_positions),
                    projected_obscured_position_count=len(projection.obscured_positions),
                    granted_sense_types=projection.granted_sense_types,
                    recipient_uuid=projection.recipient_uuid,
                    limited_resource_cost=limited_resource_cost,
                    replaces_concentration=replaces_concentration,
                )),
            ))
    has_novel_frontier = any(
        proposal.reason == "reveal_subjective_frontier"
        and proposal.evidence.exploration is not None
        and not proposal.evidence.exploration.revisited_this_turn
        for proposal in proposals
    )
    if has_novel_frontier:
        proposals = [
            proposal
            for proposal in proposals
            if proposal.reason != "reveal_subjective_frontier"
            or proposal.evidence.exploration is None
            or not proposal.evidence.exploration.revisited_this_turn
        ]
    return tuple(sorted(proposals, key=_proposal_replay_order_key))


def _subjective_frontier_positions(
    context: PolicyContext,
    known_positions: set[tuple[int, int]],
) -> frozenset[tuple[int, int]]:
    """Return only adjacent coordinates explicitly retained as unknown."""
    frontier: set[tuple[int, int]] = set()
    for tile in context.world.known_tiles.values():
        for offset in AdjacentOffset:
            if (
                tile.adjacent_domain.get(offset)
                is not SpatialDomainKnowledge.UNKNOWN
            ):
                continue
            dx, dy = offset.delta
            neighbor = (tile.position[0] + dx, tile.position[1] + dy)
            if neighbor not in known_positions:
                frontier.add(neighbor)
    return frozenset(frontier)


def _movement_exploration_candidates(
    row: ActionAffordance,
    semantics: ActionSemantics,
    actor_position: tuple[int, int],
    movement_remaining: int,
    known_positions: set[tuple[int, int]],
    frontier_positions: frozenset[tuple[int, int]],
    remembered: tuple[ObservationEntityFact, ...],
    remembered_searches: dict[str, RememberedContactSearchState],
    slow_positions: frozenset[tuple[int, int]],
    visited_positions: frozenset[tuple[int, int]],
) -> tuple[PolicyProposal, ...]:
    """Preserve movement-frontier behavior inside the shared information branch."""
    proposals: list[PolicyProposal] = []
    for target in row.targets:
        if target.position is None or target.position == actor_position:
            continue
        movement_cost = (
            target.safe_path_cost
            if target.safe_path_cost is not None
            else target.path_cost
        )
        if movement_cost is None or movement_cost > movement_remaining:
            continue
        unknown_frontier = sum(
            (target.position[0] + dx, target.position[1] + dy)
            in frontier_positions
            for dx, dy in _FRONTIER_NEIGHBORS
        )
        remembered_geometry = (
            _remembered_investigation_geometry(
                actor_position,
                target.position,
                remembered,
                remembered_searches,
            )
        )
        remembered_target = (
            remembered_geometry.entity
            if remembered_geometry is not None
            else None
        )
        current_distance = (
            remembered_geometry.current_distance
            if remembered_geometry is not None
            else None
        )
        selected_distance = (
            remembered_geometry.selected_distance
            if remembered_geometry is not None
            else None
        )
        expanded_search = bool(
            remembered_geometry is not None
            and remembered_geometry.expanded_search
        )
        search_attempt = (
            remembered_geometry.completed_investigations
            if remembered_geometry is not None
            else 0
        )
        search_novelty = (
            remembered_geometry.novelty_feet
            if remembered_geometry is not None
            else 0
        )
        remembered_progress = (
            max(0, current_distance - selected_distance)
            if current_distance is not None and selected_distance is not None
            else 0
        )
        if unknown_frontier == 0 and remembered_progress == 0 and not expanded_search:
            continue
        route = target.safe_path if target.safe_path else target.path
        hazardous = target.is_path_hazardous and not target.safe_path
        slow_path_cells = len(set(route) & set(slow_positions))
        components = (
            _component(
                "information_gathering_action",
                1.0,
                30.0,
                "server-issued movement declares subjective information change",
            ),
            _component(
                "unknown_frontier_adjacency",
                float(unknown_frontier),
                5.0,
                "destination borders positions absent from accumulated subjective knowledge",
            ),
            _component(
                "remembered_contact_progress_cells",
                float(remembered_progress // 5),
                4.0,
                "destination approaches a remembered hostile last-known position",
            ),
            _component(
                "expanded_remembered_contact_search",
                float(expanded_search),
                18.0,
                "the last-known position was cleared and this destination expands the search",
            ),
            _component(
                "remembered_search_novelty_cells",
                float(search_novelty // 5),
                3.0,
                "prefer destinations separated from positions already inspected in this search episode",
            ),
            _component(
                "hazardous_route",
                float(hazardous),
                -40.0,
                "only the disclosed path crosses a known hazard",
            ),
            _component(
                "slow_path_cells",
                float(slow_path_cells),
                -2.0,
                "known slow terrain consumes route efficiency",
            ),
            _component(
                "action_economy_opportunity_cost",
                action_economy_opportunity_cost(row.cost),
                -4.0,
                "preserve flexible action economy for facts revealed after movement",
            ),
            _component(
                "movement_cost",
                float(movement_cost),
                -0.05,
                "prefer lower-cost routes for equal subjective information gain",
            ),
        )
        proposals.append(PolicyProposal(
            intent=ExecuteIntent(row_id=row.row_id, prefer_safe=True),
            goal=PolicyGoal.INFORMATION_GATHERING,
            source_node="InformationGathering/Explore",
            reason=(
                "expand_remembered_contact_search"
                if expanded_search
                else "investigate_remembered_contact"
                if remembered_target is not None and remembered_progress > 0
                else "reveal_subjective_frontier"
            ),
            score=sum(component.contribution for component in components),
            replay_key=(
                row.semantic_key,
                position_replay_token(target.position),
                (
                    entity_fact_replay_token(remembered_target)
                    if remembered_target is not None
                    else "no-remembered-contact"
                ),
            ),
            utility_components=components,
            semantic_tags=semantics.tags,
            evidence=PolicyEvidence(exploration=ExplorationEvidence(
                anchor_position=target.position,
                movement_cost=movement_cost,
                revisited_this_turn=target.position in visited_positions,
                unknown_frontier_count=unknown_frontier,
                hazardous_route=hazardous,
                slow_path_cells=slow_path_cells,
                remembered_target_uuid=(
                    remembered_target.uuid if remembered_target is not None else None
                ),
                current_remembered_distance=current_distance,
                selected_remembered_distance=selected_distance,
                expanded_remembered_search=expanded_search,
                remembered_search_attempt=search_attempt,
                remembered_search_novelty_feet=search_novelty,
                projected_unknown_position_count=unknown_frontier,
            )),
        ))
    return tuple(proposals)


def _project_information_gain(
    context: PolicyContext,
    target: Optional[ActionTarget],
    effects: tuple[InformationEffect, ...],
    frontier_positions: frozenset[tuple[int, int]],
    obscured_positions: frozenset[tuple[int, int]],
) -> Optional[_InformationProjection]:
    """Project one row's typed effects over accumulated subjective knowledge."""
    actor_uuid = context.facts.actor.actor_uuid
    actor_position = context.facts.actor.position
    if actor_uuid is None or actor_position is None:
        return None

    unknown_certainty: dict[tuple[int, int], float] = {}
    obscured_certainty: dict[tuple[int, int], float] = {}
    granted_senses: set[str] = set()
    recipient_uuid: Optional[str] = None
    anchors: list[tuple[int, int]] = []
    for effect in effects:
        anchor = _information_effect_anchor(
            context,
            target,
            effect.anchor,
            actor_position,
        )
        if anchor is None:
            continue
        anchors.append(anchor)
        certainty_weight = _INFORMATION_CERTAINTY_WEIGHT[effect.certainty]
        if effect.operation in {
            InformationOperation.REVEAL_FRONTIER,
            InformationOperation.EXPLORE_REGION,
            InformationOperation.REVEAL_REGION,
        }:
            for position in _positions_in_information_scope(
                frontier_positions,
                anchor,
                effect,
            ):
                unknown_certainty[position] = max(
                    certainty_weight,
                    unknown_certainty.get(position, 0.0),
                )
        elif effect.operation is InformationOperation.CHANGE_LIGHT:
            for position in _positions_in_information_scope(
                obscured_positions,
                anchor,
                effect,
            ):
                obscured_certainty[position] = max(
                    certainty_weight,
                    obscured_certainty.get(position, 0.0),
                )
        elif effect.operation is InformationOperation.GRANT_SENSE:
            candidate_recipient = _information_effect_recipient(
                actor_uuid,
                target,
                effect.anchor,
            )
            observer = (
                context.world.observers.get(candidate_recipient)
                if candidate_recipient is not None
                else None
            )
            normalized_sense = _normalized_sense_type(effect.sense_type)
            active_senses = {
                normalized
                for sense_mode in observer.sense_modes
                for normalized in [_normalized_sense_type(sense_mode.get("sense_type"))]
                if normalized is not None
            } if observer is not None else set()
            if (
                observer is not None
                and normalized_sense is not None
                and normalized_sense not in active_senses
            ):
                granted_senses.add(normalized_sense)
                recipient_uuid = candidate_recipient

    if not unknown_certainty and not obscured_certainty and not granted_senses:
        return None
    represented_effects = tuple(
        effect
        for effect in effects
        if effect.operation in POSITIVE_INFORMATION_OPERATIONS
    )
    return _InformationProjection(
        anchor_position=min(anchors) if anchors else actor_position,
        operations=tuple(sorted(
            {effect.operation for effect in represented_effects},
            key=lambda operation: operation.value,
        )),
        strongest_certainty=max(
            (effect.certainty for effect in represented_effects),
            key=_INFORMATION_CERTAINTY_WEIGHT.__getitem__,
        ),
        effect_radius_feet=max(
            (
                effect.radius_feet
                for effect in represented_effects
                if effect.radius_feet is not None
            ),
            default=None,
        ),
        unknown_positions=frozenset(unknown_certainty),
        obscured_positions=frozenset(obscured_certainty),
        weighted_unknown_count=sum(unknown_certainty.values()),
        weighted_obscured_count=sum(obscured_certainty.values()),
        granted_sense_types=tuple(sorted(granted_senses)),
        recipient_uuid=recipient_uuid,
    )


def _information_effect_anchor(
    context: PolicyContext,
    target: Optional[ActionTarget],
    anchor: WorldEffectAnchor,
    actor_position: tuple[int, int],
) -> Optional[tuple[int, int]]:
    """Resolve an action-relative anchor from subjective target facts only."""
    if anchor is WorldEffectAnchor.ACTOR:
        return actor_position
    if target is None:
        return None
    if target.position is not None:
        return target.position
    if target.target_uuid is None:
        return None
    if anchor is WorldEffectAnchor.SELECTED_OBJECT:
        known_object = context.world.known_objects.get(target.target_uuid)
        return known_object.position if known_object is not None else None
    known_entity = context.world.known_entities.get(target.target_uuid)
    return known_entity.position if known_entity is not None else None


def _positions_in_information_scope(
    candidates: frozenset[tuple[int, int]],
    anchor: tuple[int, int],
    effect: InformationEffect,
) -> frozenset[tuple[int, int]]:
    """Intersect known candidate positions with one declared effect geometry."""
    if effect.radius_feet is not None:
        return frozenset(
            position
            for position in candidates
            if grid_distance_feet(anchor, position) <= effect.radius_feet
        )
    if effect.scope is WorldEffectScope.FRONTIER:
        adjacent = {
            (anchor[0] + dx, anchor[1] + dy)
            for dx, dy in _FRONTIER_NEIGHBORS
        }
        return frozenset(candidates & adjacent)
    return frozenset()


def _information_effect_recipient(
    actor_uuid: str,
    target: Optional[ActionTarget],
    anchor: WorldEffectAnchor,
) -> Optional[str]:
    """Resolve a typed sense-grant recipient without inferring hidden targets."""
    if anchor is WorldEffectAnchor.ACTOR:
        return actor_uuid
    return target.target_uuid if target is not None else None


def _normalized_sense_type(value: object) -> Optional[str]:
    """Normalize an already typed sense identifier for exact set comparison."""
    if value is None:
        return None
    enum_value = getattr(value, "value", value)
    return str(enum_value).strip().lower().replace(" ", "_").replace("-", "_")


def _limited_resource_cost(row: ActionAffordance) -> float:
    """Return finite spell-slot, named-resource, and item-charge expenditure."""
    spell_slot_cost = row.cost.spell_slot_cost
    if spell_slot_cost is None and row.spell_level not in {None, 0}:
        spell_slot_cost = row.cast_at_level
    return float(
        (spell_slot_cost or 0)
        + sum(row.cost.resource_costs.values())
        + sum(row.cost.item_charge_costs.values())
    )


@dataclass(frozen=True)
class _RememberedInvestigationGeometry:
    """One subjective approach or expanded-search relation to a contact."""

    entity: ObservationEntityFact
    current_distance: int
    selected_distance: int
    expanded_search: bool = False
    completed_investigations: int = 0
    novelty_feet: int = 0


def _remembered_investigation_geometry(
    actor_position: tuple[int, int],
    target_position: tuple[int, int],
    remembered: tuple[ObservationEntityFact, ...],
    remembered_searches: dict[str, RememberedContactSearchState],
) -> Optional[_RememberedInvestigationGeometry]:
    """Return a last-known approach or an expanded negative-observation search."""
    approach_candidates = [
        (
            grid_distance_feet(actor_position, entity.position),
            grid_distance_feet(target_position, entity.position),
            entity_fact_replay_token(entity),
            entity,
        )
        for entity in remembered
        if entity.position is not None
        and (
            entity.uuid not in remembered_searches
            or remembered_searches[entity.uuid].completed_investigations == 0
        )
    ]
    progressing = [candidate for candidate in approach_candidates if candidate[1] < candidate[0]]
    if not progressing:
        search_candidates: list[tuple[int, int, str, ObservationEntityFact, RememberedContactSearchState]] = []
        for entity in remembered:
            state = remembered_searches.get(entity.uuid)
            if state is None or state.completed_investigations <= 0:
                continue
            investigated = set(state.investigated_positions)
            if target_position == actor_position or target_position in investigated:
                continue
            distance_from_anchor = grid_distance_feet(
                target_position,
                state.last_known_position,
            )
            search_radius_feet = min(20 + state.completed_investigations * 10, 80)
            if distance_from_anchor > search_radius_feet:
                continue
            novelty_feet = min(
                (
                    grid_distance_feet(target_position, position)
                    for position in investigated | {state.last_known_position}
                ),
                default=distance_from_anchor,
            )
            if novelty_feet <= 0:
                continue
            search_candidates.append((
                -novelty_feet,
                distance_from_anchor,
                entity_fact_replay_token(entity),
                entity,
                state,
            ))
        if not search_candidates:
            return None
        _negative_novelty, _anchor_distance, _token, entity, state = min(search_candidates)
        return _RememberedInvestigationGeometry(
            entity=entity,
            current_distance=grid_distance_feet(actor_position, state.last_known_position),
            selected_distance=grid_distance_feet(target_position, state.last_known_position),
            expanded_search=True,
            completed_investigations=state.completed_investigations,
            novelty_feet=-_negative_novelty,
        )
    current, selected, _replay_token, entity = min(
        progressing,
        key=lambda candidate: (candidate[1], -candidate[0], candidate[2]),
    )
    return _RememberedInvestigationGeometry(
        entity=entity,
        current_distance=current,
        selected_distance=selected,
    )


def end_turn_proposal() -> PolicyProposal:
    """Return the shared hierarchy's explicit legal terminal fallback."""
    return PolicyProposal(
        intent=EndTurnIntent(),
        goal=PolicyGoal.END_TURN,
        source_node="TurnLifecycle/EndTurn",
        reason="no_higher_value_legal_tactical_or_information_action",
        replay_key=("turn-end",),
        semantic_tags=frozenset({ActionTag.TURN_END}),
    )


def spacing_candidates(
    context: PolicyContext,
    *,
    has_immediate_pressure: Optional[bool] = None,
) -> tuple[PolicyProposal, ...]:
    """Return post-pressure movement toward a future capability envelope."""
    context.validate_alignment()
    actor = context.facts.actor
    economy = actor.economy
    immediate_pressure = (
        bool(direct_damage_candidates(context))
        if has_immediate_pressure is None
        else has_immediate_pressure
    )
    if (
        actor.actor_uuid is None
        or actor.position is None
        or economy is None
        or not economy.meaningful_commands_remaining
        or economy.actions > 0
        or economy.extra_attacks > 0
        or immediate_pressure
    ):
        return tuple()
    topology_workspace = KnownLineOfSightWorkspace.from_world(
        context.world,
        vision_blocker_positions=context.facts.topology.vision_blocker_positions,
    )
    all_projections = _future_capability_target_projections(
        context,
        topology_workspace=topology_workspace,
    )
    eligible_projections = tuple(
        projection for projection in all_projections if projection.eligible
    )
    if not eligible_projections:
        return tuple()
    non_dominated_projections = _non_dominated_distance_envelopes(
        eligible_projections,
    )
    selected_projection = _select_future_distance_envelope(
        non_dominated_projections,
    )
    reference = context.world.known_entities.get(
        selected_projection.target_entity_uuid
    )
    if reference is None or reference.position is None:
        return tuple()
    actor_position = actor.position
    assert actor_position is not None
    current_enemy_distance = selected_projection.distance_feet // 5
    current_ally_distance = _nearest_controlled_ally_distance(context, actor_position)
    current_ally_deficit = _optional_spacing_deficit(
        current_ally_distance,
        ALLY_SPACING_FLOOR_CELLS,
    )
    current_enemy_deficit = _distance_envelope_deficit(
        current_enemy_distance,
        selected_projection,
    )
    movement_row_ids = context.facts.affordances.row_ids_by_tag.get(
        ActionTag.MOVEMENT_VOLUNTARY,
        tuple(),
    )
    movement_rows_to_evaluate = (
        movement_row_ids
        if (
            current_enemy_deficit > 0
            or (
                current_ally_deficit is not None
                and current_ally_deficit > 0
            )
        )
        else tuple()
    )
    representative_seeds: dict[tuple[object, ...], _SpacingCandidateSeed] = {}
    endpoint_projections: dict[
        tuple[int, int],
        CapabilityTargetProjection,
    ] = {}
    applicable_movement_rows = 0
    for row_id in movement_rows_to_evaluate:
        row = context.facts.affordances.by_id.get(row_id)
        semantics = context.facts.affordances.semantics_by_row_id.get(row_id)
        if (
            row is None
            or semantics is None
            or not context.execution_constraints.allows(row)
            or not row.can_afford
        ):
            continue
        target = row.targets[0] if row.targets else None
        if target is None or target.position is None or target.position == actor_position:
            continue
        endpoint_projection = endpoint_projections.get(target.position)
        if endpoint_projection is None:
            endpoint_projection = _capability_projection_at_origin(
                context,
                selected_projection,
                target.position,
                topology_workspace=topology_workspace,
            )
            endpoint_projections[target.position] = endpoint_projection
        if not endpoint_projection.eligible:
            continue
        next_enemy_distance = endpoint_projection.distance_feet // 5
        next_ally_distance = _nearest_controlled_ally_distance(context, target.position)
        next_ally_deficit = _optional_spacing_deficit(
            next_ally_distance,
            ALLY_SPACING_FLOOR_CELLS,
        )
        for projection in (endpoint_projection,):
            next_enemy_deficit = _distance_envelope_deficit(
                next_enemy_distance,
                projection,
            )
            spreads = (
                current_ally_deficit is not None
                and next_ally_deficit is not None
                and next_ally_deficit < current_ally_deficit
                and next_enemy_deficit <= current_enemy_deficit
            )
            closes_future_range = next_enemy_deficit < current_enemy_deficit
            if not spreads and not closes_future_range:
                continue
            applicable_movement_rows += 1
            movement_cost = (
                target.safe_path_cost
                if target.safe_path_cost is not None
                else target.path_cost
            )
            hazardous = target.is_path_hazardous and target.safe_path_cost is None
            opportunity_attack_exposures = tuple(
                target.safe_path_opportunity_attack_exposures
                if target.safe_path_cost is not None
                else target.opportunity_attack_exposures
            )
            hostile_deficit_reduction = current_enemy_deficit - next_enemy_deficit
            ally_deficit_reduction = (
                current_ally_deficit - next_ally_deficit
                if current_ally_deficit is not None and next_ally_deficit is not None
                else 0
            )
            offensive_range_deficit = max(
                0,
                next_enemy_distance - projection.normal_range_feet // 5,
            )
            economy_opportunity_cost = action_economy_opportunity_cost(row.cost)
            line_uncertainty = projection.line_of_sight is TruthValue.UNKNOWN
            score = (
                60.0
                + float(hostile_deficit_reduction) * 5.0
                + float(next_enemy_deficit == 0) * 20.0
                + float(projection.pressure_value or 0.0) * 2.0
                + float(ally_deficit_reduction) * 3.0
                + float(
                    next_ally_deficit == 0
                    if next_ally_deficit is not None
                    else False
                ) * 5.0
                - float(offensive_range_deficit) * 10.0
                - float(hazardous) * 40.0
                - float(len(opportunity_attack_exposures)) * 60.0
                - float(line_uncertainty) * 10.0
                - float(projection.replaces_concentration) * 60.0
                - _projection_limited_resource_cost(projection) * 6.0
                - economy_opportunity_cost * 4.0
                - float(movement_cost or 0) * 0.05
            )
            seed = _SpacingCandidateSeed(
                row=row,
                semantics=semantics,
                projection=projection,
                reason=(
                    "spread_after_pressure"
                    if spreads and not closes_future_range
                    else "enter_future_tactical_envelope"
                ),
                next_enemy_distance=next_enemy_distance,
                next_ally_distance=next_ally_distance,
                next_enemy_deficit=next_enemy_deficit,
                next_ally_deficit=next_ally_deficit,
                hostile_deficit_reduction=hostile_deficit_reduction,
                ally_deficit_reduction=ally_deficit_reduction,
                offensive_range_deficit=offensive_range_deficit,
                movement_cost=movement_cost,
                hazardous=hazardous,
                opportunity_attack_exposures=opportunity_attack_exposures,
                economy_opportunity_cost=economy_opportunity_cost,
                score=score,
            )
            seed_key = _spacing_seed_class_key(seed)
            existing = representative_seeds.get(seed_key)
            if existing is None:
                representative_seeds[seed_key] = seed
            elif _spacing_seed_rank_key(seed) < _spacing_seed_rank_key(existing):
                seed.represented_rows = existing.represented_rows + 1
                representative_seeds[seed_key] = seed
            else:
                existing.represented_rows += 1

    movement_rows_evaluated = len(movement_rows_to_evaluate)
    movement_proposals = [
        _spacing_proposal(
            seed,
            reference=reference,
            current_enemy_distance=current_enemy_distance,
            current_ally_distance=current_ally_distance,
            movement_rows_evaluated=movement_rows_evaluated,
            applicable_movement_rows=applicable_movement_rows,
            capability_envelopes_evaluated=len(all_projections),
            capability_envelopes_retained=len(non_dominated_projections),
            projection_status_counts=_projection_status_counts(all_projections),
        )
        for seed in representative_seeds.values()
    ]
    hold_projection = selected_projection
    hold_deficit = _distance_envelope_deficit(
        current_enemy_distance,
        hold_projection,
    )
    hold_components = (
        _component("post_pressure_positioning", 1.0, 60.0, "primary attack economy is spent"),
        _component(
            "future_pressure_value",
            hold_projection.pressure_value or 0.0,
            2.0,
            "subjective expected HP pressure of the selected future capability",
        ),
        _component(
            "tactical_envelope_held",
            float(hold_deficit == 0),
            20.0,
            "actor already occupies a future-turn capability envelope",
        ),
        _component(
            "ally_spacing_floor_held",
            float(
                current_ally_distance is None
                or current_ally_distance >= ALLY_SPACING_FLOOR_CELLS
            ),
            5.0,
            "actor is not in a known controlled cluster",
        ),
        _component(
            "offensive_range_deficit",
            float(
                max(
                    0,
                    current_enemy_distance - hold_projection.normal_range_feet // 5,
                )
            ),
            -10.0,
            "current anchor exceeds the selected capability's normal range",
        ),
        _component(
            "line_of_sight_unknown",
            float(hold_projection.line_of_sight is TruthValue.UNKNOWN),
            -10.0,
            "subjective topology cannot prove the current line",
        ),
        _component(
            "concentration_replacement",
            float(hold_projection.replaces_concentration),
            -60.0,
            "selected future capability would replace active concentration",
        ),
        _component(
            "persistent_resource_cost",
            _projection_limited_resource_cost(hold_projection),
            -6.0,
            "selected future capability consumes a persistent resource",
        ),
        _component(
            "movement_rows_evaluated",
            float(movement_rows_evaluated),
            0.0,
            "server-issued movement rows evaluated as lightweight spacing seeds",
        ),
        _component(
            "applicable_movement_rows",
            float(applicable_movement_rows),
            0.0,
            "movement rows that improve a bounded spacing deficit",
        ),
        _component(
            "capability_envelopes_evaluated",
            float(len(all_projections)),
            0.0,
            "payable typed future capabilities considered before dominance",
        ),
        _component(
            "capability_envelopes_retained",
            float(len(non_dominated_projections)),
            0.0,
            "non-dominated future capabilities available to the selector",
        ),
        _component(
            "capability_envelopes_selected",
            1.0,
            0.0,
            "one future capability selected before evaluating movement geometry",
        ),
        *_projection_status_components(all_projections),
    )
    hold_proposal = PolicyProposal(
        intent=EndTurnIntent(),
        goal=PolicyGoal.POSITION_AND_SURVIVAL,
        source_node="PositionAndSurvival/CapabilityEnvelope",
        reason="hold_future_tactical_envelope",
        score=sum(component.contribution for component in hold_components),
        replay_key=(
            "spacing-hold",
            hold_projection.capability_id,
            position_replay_token(actor_position),
            entity_fact_replay_token(reference),
        ),
        utility_components=hold_components,
        semantic_tags=frozenset({ActionTag.TURN_END}),
        evidence=PolicyEvidence(spacing=SpacingEvidence(
            reference_entity_uuid=reference.uuid,
            reference_position=reference.position,
            current_distance_cells=current_enemy_distance,
            selected_distance_cells=current_enemy_distance,
            spacing_floor_cells=hold_projection.preferred_minimum_range_feet // 5,
            hostile_spacing_deficit_cells=hold_deficit,
            anchor_position=actor_position,
            nearest_controlled_ally_distance_cells=current_ally_distance,
            ally_spacing_floor_cells=ALLY_SPACING_FLOOR_CELLS,
            ally_spacing_deficit_cells=current_ally_deficit,
            normal_attack_range_cells=hold_projection.normal_range_feet // 5,
            offensive_range_deficit_cells=(
                max(
                    0,
                    current_enemy_distance - hold_projection.normal_range_feet // 5,
                )
            ),
            capability_target_projection=hold_projection,
        )),
    )
    return (
        *tuple(sorted(movement_proposals, key=_proposal_replay_order_key)),
        hold_proposal,
    )


def _spacing_seed_class_key(seed: _SpacingCandidateSeed) -> tuple[object, ...]:
    """Return the semantic, economy, and disclosed-risk class for one seed."""
    cost = seed.row.cost
    return (
        seed.row.semantic_key,
        seed.row.semantics_ref,
        seed.semantics.tags,
        seed.capability_id,
        seed.spacing_floor,
        seed.normal_attack_range,
        seed.future_pressure_value,
        seed.projection.model_status,
        seed.projection.line_of_sight,
        seed.projection.replaces_concentration,
        tuple(
            (requirement.resource_id, requirement.required, requirement.available)
            for requirement in seed.projection.persistent_requirements
        ),
        seed.reason,
        seed.hazardous,
        tuple(sorted(
            exposure.reactor_uuid
            for exposure in seed.opportunity_attack_exposures
        )),
        cost.action_cost,
        cost.bonus_action_cost,
        cost.reaction_cost,
        cost.consumes_attack_slot,
        cost.spell_slot_cost,
        tuple(sorted(cost.resource_costs.items())),
        tuple(sorted(cost.item_charge_costs.items())),
    )


def _spacing_seed_rank_key(seed: _SpacingCandidateSeed) -> tuple[float, str]:
    """Rank lightweight seeds exactly like the utility arbiter ranks proposals."""
    return (-seed.score, seed.row.row_id)


def _spacing_proposal(
    seed: _SpacingCandidateSeed,
    *,
    reference: ObservationEntityFact,
    current_enemy_distance: int,
    current_ally_distance: Optional[int],
    movement_rows_evaluated: int,
    applicable_movement_rows: int,
    capability_envelopes_evaluated: int,
    capability_envelopes_retained: int,
    projection_status_counts: dict[CapabilityModelStatus, int],
) -> PolicyProposal:
    """Materialize one bounded spacing representative with audit telemetry."""
    target = seed.row.targets[0]
    assert target.position is not None
    components = (
        _component("post_pressure_positioning", 1.0, 60.0, "primary attack economy is spent"),
        _component(
            "future_pressure_value",
            seed.future_pressure_value,
            2.0,
            "subjective expected HP pressure of the selected future capability",
        ),
        _component(
            "hostile_spacing_deficit_reduction",
            float(seed.hostile_deficit_reduction),
            5.0,
            "bounded progress toward the hostile spacing floor",
        ),
        _component(
            "reaches_tactical_envelope",
            float(seed.next_enemy_deficit == 0),
            20.0,
            "destination reaches the selected future capability envelope",
        ),
        _component(
            "ally_spacing_deficit_reduction",
            float(seed.ally_deficit_reduction),
            3.0,
            "bounded progress toward the controlled-ally spacing floor",
        ),
        _component(
            "reaches_ally_spacing_floor",
            float(
                seed.next_ally_deficit == 0
                if seed.next_ally_deficit is not None
                else False
            ),
            5.0,
            "destination resolves a known controlled cluster",
        ),
        _component(
            "offensive_range_deficit",
            float(seed.offensive_range_deficit or 0),
            -10.0,
            "destination exceeds the actor's longest typed normal tactical range",
        ),
        _component(
            "hazardous_route",
            float(seed.hazardous),
            -40.0,
            "known route crosses a hazard",
        ),
        _component(
            "opportunity_attack_exposure",
            float(len(seed.opportunity_attack_exposures)),
            -60.0,
            "selected route exits visible hostile threat areas",
        ),
        _component(
            "line_of_sight_unknown",
            float(seed.projection.line_of_sight is TruthValue.UNKNOWN),
            -10.0,
            "subjective topology cannot prove the endpoint line",
        ),
        _component(
            "concentration_replacement",
            float(seed.projection.replaces_concentration),
            -60.0,
            "selected future capability would replace active concentration",
        ),
        _component(
            "persistent_resource_cost",
            _projection_limited_resource_cost(seed.projection),
            -6.0,
            "selected future capability consumes a persistent resource",
        ),
        _component(
            "action_economy_opportunity_cost",
            seed.economy_opportunity_cost,
            -4.0,
            "preserve flexible economy when movement geometry is equivalent",
        ),
        _component(
            "movement_cost",
            float(seed.movement_cost or 0),
            -0.05,
            "known movement cost preserves remaining mobility",
        ),
        _component(
            "movement_rows_evaluated",
            float(movement_rows_evaluated),
            0.0,
            "server-issued movement rows evaluated as lightweight spacing seeds",
        ),
        _component(
            "applicable_movement_rows",
            float(applicable_movement_rows),
            0.0,
            "movement rows that improve a bounded spacing deficit",
        ),
        _component(
            "represented_movement_rows",
            float(seed.represented_rows),
            0.0,
            "rows represented by this semantic and disclosed-risk class",
        ),
        _component(
            "capability_envelopes_evaluated",
            float(capability_envelopes_evaluated),
            0.0,
            "payable typed future capabilities considered before dominance",
        ),
        _component(
            "capability_envelopes_retained",
            float(capability_envelopes_retained),
            0.0,
            "non-dominated future capabilities available to the selector",
        ),
        _component(
            "capability_envelopes_selected",
            1.0,
            0.0,
            "one future capability selected before evaluating movement geometry",
        ),
        *_projection_count_components(projection_status_counts),
    )
    return PolicyProposal(
        intent=ExecuteIntent(row_id=seed.row.row_id, prefer_safe=True),
        goal=PolicyGoal.POSITION_AND_SURVIVAL,
        source_node="PositionAndSurvival/CapabilityEnvelope",
        reason=seed.reason,
        score=seed.score,
        replay_key=(
            seed.row.semantic_key,
            seed.capability_id,
            position_replay_token(target.position),
            entity_fact_replay_token(reference),
        ),
        utility_components=components,
        semantic_tags=seed.semantics.tags,
        evidence=PolicyEvidence(spacing=SpacingEvidence(
            reference_entity_uuid=reference.uuid,
            reference_position=reference.position,
            current_distance_cells=current_enemy_distance,
            selected_distance_cells=seed.next_enemy_distance,
            spacing_floor_cells=seed.spacing_floor,
            hostile_spacing_deficit_cells=seed.next_enemy_deficit,
            anchor_position=target.position,
            nearest_controlled_ally_distance_cells=seed.next_ally_distance,
            ally_spacing_floor_cells=ALLY_SPACING_FLOOR_CELLS,
            ally_spacing_deficit_cells=seed.next_ally_deficit,
            normal_attack_range_cells=seed.normal_attack_range,
            offensive_range_deficit_cells=seed.offensive_range_deficit,
            opportunity_attack_exposures=seed.opportunity_attack_exposures,
            capability_target_projection=seed.projection,
        )),
    )


def target_effect_candidates(context: PolicyContext) -> tuple[PolicyProposal, ...]:
    """Return relationship-safe allocations for conditional target effects.

    The server supplies legal targets and the engine supplies target-effect
    branches. This reducer binds those contracts only to visible subjective
    facts, then allocates beneficial branches to known allies and harmful
    branches to visible hostiles.

    Args:
        context: Aligned subjective policy context for one decision epoch.

    Returns:
        One proposal per policy-distinct source action.
    """
    context.validate_alignment()
    epoch = context.world.current_epoch
    if epoch is None:
        return tuple()
    controlled = set(context.facts.contacts.controlled_entity_uuids)
    allies = set(context.facts.contacts.visible_ally_uuids)
    hostiles = set(context.facts.contacts.visible_hostile_uuids)
    families: dict[str, list[tuple[ActionAffordance, ActionSemantics]]] = {}
    affordance_facts = context.facts.affordances
    for row_id in affordance_facts.target_effect_row_ids:
        row = affordance_facts.by_id[row_id]
        semantics = context.facts.affordances.semantics_by_row_id.get(row.row_id)
        if (
            semantics is None
            or not context.execution_constraints.allows(row)
            or not row.can_afford
            or row.cost.affordability == "unaffordable"
        ):
            continue
        family_id = row.source_action_id or row.row_id
        families.setdefault(family_id, []).append((row, semantics))

    proposals: list[PolicyProposal] = []
    for family in families.values():
        family.sort(key=lambda item: _action_replay_key(context, item[0], tuple()))
        representative, semantics = family[0]
        options_by_uuid: dict[str, ActionTarget] = {}
        for row, row_semantics in family:
            if row_semantics != semantics:
                continue
            for target in (*row.target_options, *row.targets):
                if target.target_uuid is not None:
                    options_by_uuid.setdefault(target.target_uuid, target)
        recipients = _eligible_target_effect_recipients(
            context,
            semantics,
            options_by_uuid,
            controlled=controlled,
            allies=allies,
            hostiles=hostiles,
        )
        maximum_targets = semantics.targeting.maximum_targets or representative.num_projectiles or 1
        recipients = recipients[:maximum_targets]
        if not recipients:
            continue
        selected_uuids = tuple(recipient.entity_uuid for recipient in recipients)
        primary_uuid = selected_uuids[0]
        primary_row = next(
            (
                row
                for row, _row_semantics in family
                if any(target.target_uuid == primary_uuid for target in row.targets)
            ),
            None,
        )
        if primary_row is None:
            continue
        additional_targets = selected_uuids[1:]
        hostile_affected = _sorted_entity_uuids(
            context,
            (
                recipient.entity_uuid
                for recipient in recipients
                if recipient.relationship == "hostile"
            ),
        )
        controlled_affected = _sorted_entity_uuids(
            context,
            (
                recipient.entity_uuid
                for recipient in recipients
                if recipient.relationship == "controlled"
            ),
        )
        allied_affected = _sorted_entity_uuids(
            context,
            (
                recipient.entity_uuid
                for recipient in recipients
                if recipient.relationship == "ally"
            ),
        )
        resource_cost = float(
            (primary_row.cost.spell_slot_cost or primary_row.cast_at_level or 0)
            + sum(primary_row.cost.resource_costs.values())
        )
        features = _TargetEffectFeatures(
            recipients=recipients,
            hostile_affected=hostile_affected,
            controlled_affected=controlled_affected,
            allied_affected=allied_affected,
            additional_targets=additional_targets,
            resource_cost=resource_cost,
            concentration_replacement=(
                _actor_is_concentrating(context)
                and ActionTag.CONCENTRATION_START in semantics.tags
            ),
            replay_key=_action_replay_key(context, primary_row, additional_targets),
            target_plan=_target_plan_evidence(
                context,
                primary_row,
                additional_targets=additional_targets,
                hostile_affected=hostile_affected,
                controlled_affected=controlled_affected,
                allied_affected=allied_affected,
            ),
        )
        proposals.append(_target_effect_proposal(primary_row, semantics, features))
    return tuple(sorted(proposals, key=_proposal_replay_order_key))


def _eligible_target_effect_recipients(
    context: PolicyContext,
    semantics: ActionSemantics,
    options_by_uuid: dict[str, ActionTarget],
    *,
    controlled: set[str],
    allies: set[str],
    hostiles: set[str],
) -> tuple[_TargetEffectRecipient, ...]:
    """Bind semantic branches to visible targets without filling unknown facts."""
    recipients: list[_TargetEffectRecipient] = []
    for entity_uuid in _sorted_entity_uuids(context, options_by_uuid):
        entity = context.world.known_entities.get(entity_uuid)
        if entity is None or entity.is_dead is True:
            continue
        if entity_uuid in controlled:
            relationship = "controlled"
        elif entity_uuid in allies:
            relationship = "ally"
        elif entity_uuid in hostiles:
            relationship = "hostile"
        else:
            continue
        facts = {
            "selected_target.creature_type": entity.creature_type,
            "selected_target.relationship": relationship,
        }
        matching = [
            effect
            for effect in semantics.target_effects
            if evaluate_fact_expression(effect.applicability, facts) is TruthValue.TRUE
            and _target_effect_disposition_matches(effect.disposition, relationship)
            and not _target_effect_is_observed(entity, effect)
        ]
        if not matching:
            continue
        effect = sorted(matching, key=lambda value: value.effect_id)[0]
        recipients.append(_TargetEffectRecipient(
            entity_uuid=entity_uuid,
            effect=effect,
            relationship=relationship,
            replay_token=_entity_uuid_replay_token(context, entity_uuid),
        ))
    recipients.sort(key=lambda recipient: (
        0 if recipient.effect.disposition is EffectDisposition.HARMFUL else 1,
        recipient.replay_token,
        recipient.effect.effect_id,
    ))
    return tuple(recipients)


def _target_effect_disposition_matches(
    disposition: EffectDisposition,
    relationship: str,
) -> bool:
    """Return whether an effect direction is tactically safe for a recipient."""
    if disposition is EffectDisposition.BENEFICIAL:
        return relationship in {"controlled", "ally"}
    if disposition is EffectDisposition.HARMFUL:
        return relationship == "hostile"
    return True


def _target_effect_is_observed(
    entity: ObservationEntityFact,
    effect: TargetEffectSemantics,
) -> bool:
    """Return whether every stable condition effect is already visible."""
    if not effect.condition_semantic_keys or entity.condition_semantic_keys is None:
        return False
    return effect.condition_semantic_keys.issubset(entity.condition_semantic_keys)


def _target_effect_proposal(
    row: ActionAffordance,
    semantics: ActionSemantics,
    features: _TargetEffectFeatures,
) -> PolicyProposal:
    """Materialize one inspectable mixed target-effect proposal."""
    harmful_count = sum(
        recipient.effect.disposition is EffectDisposition.HARMFUL
        for recipient in features.recipients
    )
    beneficial_count = sum(
        recipient.effect.disposition is EffectDisposition.BENEFICIAL
        for recipient in features.recipients
    )
    guaranteed_count = sum(
        recipient.effect.outcome_kind is OutcomeKind.GUARANTEED
        for recipient in features.recipients
    )
    components = (
        _component("legal_target_effect", 1.0, 100.0, "server-issued conditional target-effect affordance"),
        _component("harmful_hostile_effects", float(harmful_count), 25.0, "harmful branches allocated only to visible hostiles"),
        _component("beneficial_ally_effects", float(beneficial_count), 20.0, "beneficial branches allocated only to controlled or allied targets"),
        _component("guaranteed_effects", float(guaranteed_count), 5.0, "branches that apply without an attack or saving throw"),
        _component("resource_cost", features.resource_cost, -5.0, "spell slots and named resources consumed"),
        _component("concentration_replacement", float(features.concentration_replacement), -60.0, "replaces an observed active concentration effect"),
    )
    return PolicyProposal(
        intent=ExecuteIntent(
            row_id=row.row_id,
            extra_target_uuids=features.additional_targets,
        ),
        goal=PolicyGoal.CONDITIONAL_TARGET_EFFECT,
        source_node="TargetEffects/ConditionalAllocation",
        reason="apply_typed_conditional_target_effects",
        score=sum(component.contribution for component in components),
        replay_key=features.replay_key,
        utility_components=components,
        semantic_tags=semantics.tags,
        evidence=PolicyEvidence(
            target_plan=features.target_plan,
            target_effects=tuple(
                TargetEffectOutcomeEvidence(
                    entity_uuid=recipient.entity_uuid,
                    effect_id=recipient.effect.effect_id,
                    disposition=recipient.effect.disposition,
                    outcome_kind=recipient.effect.outcome_kind,
                    condition_semantic_keys=tuple(sorted(
                        recipient.effect.condition_semantic_keys
                    )),
                )
                for recipient in features.recipients
            ),
        ),
    )


def control_candidates(context: PolicyContext) -> tuple[PolicyProposal, ...]:
    """Return semantic control proposals over visible hostile contacts.

    Control competes with damage at one utility choice point. The policy does
    not infer target legality, private saves, or spell identity: rows are
    server-issued, classification comes from typed semantics, and duplicate
    suppression uses declared condition effects plus observed target state.

    Args:
        context: Aligned subjective policy context for one decision epoch.

    Returns:
        Deterministically ordered hard- and soft-control proposals.
    """
    context.validate_alignment()
    visible_hostiles = set(context.facts.contacts.visible_hostile_uuids)
    controlled = set(context.facts.contacts.controlled_entity_uuids)
    row_ids = sorted({
        row_id
        for tag in (ActionTag.CONTROL_HARD, ActionTag.CONTROL_SOFT)
        for row_id in context.facts.affordances.row_ids_by_tag.get(tag, tuple())
    })
    groups: dict[tuple[object, ...], _ControlCandidateSeed] = {}
    eligible_rows = _collapse_equivalent_control_aim_rows(context, tuple(row_ids))
    for row, semantics, represented_row_count in eligible_rows:
        additional_targets = _additional_control_targets(context, row, semantics)
        affected = _affected_entity_uuids(context, row) | set(additional_targets)
        hostile_affected = _sorted_entity_uuids(
            context,
            (
                entity_uuid
                for entity_uuid in affected & visible_hostiles
                if not _control_effect_is_observed(context, entity_uuid, semantics)
            ),
        )
        if not hostile_affected:
            continue
        controlled_affected = _sorted_entity_uuids(context, affected & controlled)
        additional_hostile_targets = tuple(
            entity_uuid
            for entity_uuid in additional_targets
            if entity_uuid in hostile_affected
        )
        resource_cost = float(
            (row.cost.spell_slot_cost or row.cast_at_level or 0)
            + sum(row.cost.resource_costs.values())
        )
        healthy_target_value = max(
            (_known_healthy_fraction(context, entity_uuid) for entity_uuid in hostile_affected),
            default=0.0,
        )
        hard_control = ActionTag.CONTROL_HARD in semantics.tags
        soft_control = ActionTag.CONTROL_SOFT in semantics.tags
        concentration_replacement = (
            _actor_is_concentrating(context)
            and ActionTag.CONCENTRATION_START in semantics.tags
        )
        representative_key = _control_aim_representative_key(context, row)
        aim_rows_are_equivalent = _control_aim_rows_are_equivalent(semantics)
        dominance_scope = (
            _control_dominance_scope(row, semantics)
            if aim_rows_are_equivalent
            else None
        )
        equivalence_scope = (
            row.source_action_id or row.row_id
            if aim_rows_are_equivalent
            else row.row_id
        )
        key = (
            equivalence_scope,
            row.semantics_ref,
            semantics.tags,
            hostile_affected,
            controlled_affected,
            additional_hostile_targets,
            healthy_target_value,
            hard_control,
            soft_control,
            resource_cost,
            concentration_replacement,
        )
        existing = groups.get(key)
        if existing is not None:
            existing.equivalent_rows += represented_row_count
            if representative_key < existing.representative_key:
                existing.row = row
                existing.representative_key = representative_key
            continue
        groups[key] = _ControlCandidateSeed(
            row=row,
            semantic_tags=semantics.tags,
            hostile_affected=hostile_affected,
            controlled_affected=controlled_affected,
            additional_targets=additional_hostile_targets,
            healthy_target_value=healthy_target_value,
            hard_control=hard_control,
            soft_control=soft_control,
            resource_cost=resource_cost,
            concentration_replacement=concentration_replacement,
            representative_key=representative_key,
            dominance_scope=dominance_scope,
            equivalent_rows=represented_row_count,
        )

    proposals: list[PolicyProposal] = []
    for seed in _prune_dominated_control_seeds(tuple(groups.values())):
        features = _ControlFeatures(
            hostile_affected=seed.hostile_affected,
            controlled_affected=seed.controlled_affected,
            additional_targets=seed.additional_targets,
            healthy_target_value=seed.healthy_target_value,
            hard_control=seed.hard_control,
            soft_control=seed.soft_control,
            resource_cost=seed.resource_cost,
            concentration_replacement=seed.concentration_replacement,
            replay_key=_action_replay_key(
                context,
                seed.row,
                seed.additional_targets,
            ),
            target_plan=_target_plan_evidence(
                context,
                seed.row,
                additional_targets=seed.additional_targets,
                hostile_affected=seed.hostile_affected,
                controlled_affected=seed.controlled_affected,
            ),
        )
        proposals.append(_control_proposal(_ControlCandidateGroup(
            row=seed.row,
            semantic_tags=seed.semantic_tags,
            features=features,
            representative_key=seed.representative_key,
            equivalent_rows=seed.equivalent_rows,
        )))

    return tuple(sorted(proposals, key=_proposal_replay_order_key))


def _collapse_equivalent_control_aim_rows(
    context: PolicyContext,
    row_ids: tuple[str, ...],
) -> tuple[tuple[ActionAffordance, ActionSemantics, int], ...]:
    """Return legal control rows grouped by exact transient affected sets."""
    requested_row_ids = set(row_ids)
    group_indices = sorted({
        group_index
        for tag in (ActionTag.CONTROL_HARD, ActionTag.CONTROL_SOFT)
        for group_index in (
            context.facts.affordances.affected_set_group_indices_by_tag.get(
                tag,
                tuple(),
            )
        )
    })
    selected: list[tuple[ActionAffordance, ActionSemantics, int]] = []
    has_exact_row_exclusions = bool(
        context.execution_constraints.blocked_row_ids
    )
    for group_index in group_indices:
        group = context.facts.affordances.affected_set_groups[group_index]
        canonical = context.facts.affordances.by_id.get(group.canonical_row_id)
        canonical_semantics = (
            context.facts.affordances.semantics_by_row_id.get(
                group.canonical_row_id
            )
        )
        if (
            canonical is None
            or canonical_semantics is None
            or canonical_semantics.target_effects
        ):
            continue
        aims_are_equivalent = _control_aim_rows_are_equivalent(
            canonical_semantics
        )
        if aims_are_equivalent and not has_exact_row_exclusions:
            if (
                context.execution_constraints.allows(canonical)
                and canonical.can_afford
                and canonical.cost.affordability != "unaffordable"
            ):
                selected.append((
                    canonical,
                    canonical_semantics,
                    len(group.row_ids),
                ))
            continue
        eligible: list[tuple[ActionAffordance, ActionSemantics]] = []
        for row_id in group.row_ids:
            if row_id not in requested_row_ids:
                continue
            row = context.facts.affordances.by_id.get(row_id)
            semantics = context.facts.affordances.semantics_by_row_id.get(row_id)
            if (
                row is None
                or semantics is None
                or semantics.target_effects
                or not context.execution_constraints.allows(row)
                or not row.can_afford
                or row.cost.affordability == "unaffordable"
            ):
                continue
            eligible.append((row, semantics))
        if not eligible:
            continue
        if not aims_are_equivalent:
            selected.extend((row, semantics, 1) for row, semantics in eligible)
            continue
        selected.append((*eligible[0], len(eligible)))
    return tuple(selected)


def _prune_dominated_control_seeds(
    seeds: tuple[_ControlCandidateSeed, ...],
) -> tuple[_ControlCandidateSeed, ...]:
    """Keep the non-dominated transient control affected-set frontier."""
    comparable_by_scope: dict[tuple[object, ...], list[_ControlCandidateSeed]] = {}
    for seed in seeds:
        if seed.dominance_scope is not None:
            comparable_by_scope.setdefault(seed.dominance_scope, []).append(seed)
    dominated_ids: set[int] = set()
    for comparable in comparable_by_scope.values():
        if len(comparable) < 2:
            continue
        for seed in comparable:
            if any(
                candidate is not seed
                and _control_seed_dominates(candidate, seed)
                for candidate in comparable
            ):
                dominated_ids.add(id(seed))
    return tuple(seed for seed in seeds if id(seed) not in dominated_ids)


def _control_seed_dominates(
    candidate: _ControlCandidateSeed,
    other: _ControlCandidateSeed,
) -> bool:
    """Return whether one same-source transient aim is strictly no worse."""
    if (
        candidate.dominance_scope is None
        or candidate.dominance_scope != other.dominance_scope
    ):
        return False
    return (
        candidate.resource_cost <= other.resource_cost
        and candidate.hostile_affected_set.issuperset(other.hostile_affected_set)
        and candidate.controlled_affected_set.issubset(other.controlled_affected_set)
        and (
            candidate.resource_cost < other.resource_cost
            or candidate.hostile_affected_set != other.hostile_affected_set
            or candidate.controlled_affected_set != other.controlled_affected_set
        )
    )


def _control_dominance_scope(
    row: ActionAffordance,
    semantics: ActionSemantics,
) -> tuple[object, ...]:
    """Return the complete non-scarcity contract for transient control.

    Slot-scaled registrations content-address their consumed slot as part of
    ``resource_effects``. Removing only that field lets an otherwise identical
    lower-slot row dominate a higher-slot row, while every targeting, outcome,
    concentration, spatial, and logical effect remains part of the comparison.
    """
    return (
        row.semantic_key,
        semantics.model_copy(update={"resource_effects": tuple()}),
        row.cost.action_cost,
        row.cost.bonus_action_cost,
        row.cost.reaction_cost,
        row.cost.movement_cost,
        row.cost.consumes_attack_slot,
        row.cost.spell_slot_cost is not None,
        tuple(sorted(row.cost.resource_costs)),
        tuple(sorted(row.cost.item_charge_costs.items())),
        row.requires_concentration,
    )


def _control_aim_rows_are_equivalent(semantics: ActionSemantics) -> bool:
    """Return whether aim geometry has no declared persistent side effects."""
    return not (
        semantics.spatial is not None
        or semantics.topology_effects
        or semantics.information_effects
        or semantics.tags & {ActionTag.SUMMON, ActionTag.ZONE_PERSISTENT}
    )


def _control_aim_representative_key(
    context: PolicyContext,
    row: ActionAffordance,
) -> tuple[tuple[int, int, int], ...]:
    """Order equivalent control rows by disclosed target geometry."""
    indexed = context.evaluation_index.target_geometry_key_by_row_id.get(row.row_id)
    if indexed is not None:
        return indexed
    return tuple(
        (0, target.position[0], target.position[1])
        if target.position is not None
        else (1, 0, 0)
        for target in row.targets
    )


def direct_damage_candidates(context: PolicyContext) -> tuple[PolicyProposal, ...]:
    """Return affordable damage proposals affecting visible hostile contacts.

    Candidate generation consumes only the materialized subjective world and
    server-issued affordances. Unknown targets and remembered positions are not
    promoted into executable combat targets.

    Args:
        context: Aligned subjective policy context for one decision epoch.

    Returns:
        Deterministically ordered direct-pressure proposals.
    """
    context.validate_alignment()
    visible_hostiles = set(context.facts.contacts.visible_hostile_uuids)
    controlled = set(context.facts.contacts.controlled_entity_uuids)
    visible_allies = set(context.facts.contacts.visible_ally_uuids)
    outcome_cache = _OutcomeCache()
    allocation_cache: dict[AllocationCacheKey, Optional[tuple[tuple[str, int], ...]]] = {}
    collapsed_rows, area_represented_rows = _grouped_direct_damage_rows(
        context,
        visible_hostiles,
    )
    collapsed_rows, precomputed_allocations, repeat_represented_rows = (
        _collapse_repeatable_damage_families(
            context,
            collapsed_rows,
            outcome_cache=outcome_cache,
            allocation_cache=allocation_cache,
        )
    )
    represented_rows = dict(area_represented_rows)
    represented_rows.update(repeat_represented_rows)
    contract_key_cache: dict[str, tuple[object, ...]] = {}
    seeds: dict[tuple[object, ...], _DamageCandidateSeed] = {}
    for row, semantics in collapsed_rows:
        additional_targets = precomputed_allocations.get(row.row_id, tuple())
        if (
            not additional_targets
            and row.num_projectiles is not None
            and row.num_projectiles > 1
        ):
            additional_targets = _additional_targets(
                context,
                row,
                outcome_cache=outcome_cache,
                allocation_cache=allocation_cache,
            )
        affected = _affected_entity_uuids(context, row) | set(additional_targets)
        hostile_affected = _sorted_entity_uuids(context, affected & visible_hostiles)
        if not hostile_affected:
            continue
        controlled_affected = _sorted_entity_uuids(context, affected & controlled)
        allied_affected = _sorted_entity_uuids(context, affected & visible_allies)
        ordered_affected = _sorted_entity_uuids(context, affected)
        contract_cache_id = row.source_action_id or row.row_id
        contract_key = contract_key_cache.get(contract_cache_id)
        if contract_key is None:
            contract_key = _damage_contract_key(row, semantics.tags)
            contract_key_cache[contract_cache_id] = contract_key
        key = _damage_equivalence_key(
            row,
            semantics.tags,
            hostile_affected=hostile_affected,
            controlled_affected=controlled_affected,
            allied_affected=allied_affected,
            additional_targets=additional_targets,
            affected_entity_uuids=ordered_affected,
            primary_target_uuid=_primary_target_uuid(context, row),
            contract_key=contract_key,
        )
        existing = seeds.get(key)
        if existing is None:
            seeds[key] = _DamageCandidateSeed(
                row=row,
                semantics=semantics,
                semantic_tags=semantics.tags,
                affected_entity_uuids=ordered_affected,
                hostile_affected=hostile_affected,
                controlled_affected=controlled_affected,
                allied_affected=allied_affected,
                additional_targets=additional_targets,
                equivalent_rows=represented_rows.get(row.row_id, 1),
            )
        else:
            existing.equivalent_rows += represented_rows.get(row.row_id, 1)

    candidate_seeds = _prune_dominated_area_damage_seeds(
        tuple(seeds.values()),
        damage_ending_control_uuids=frozenset(
            entity_uuid
            for entity_uuid in context.facts.contacts.visible_hostile_uuids
            if _damage_ending_control_condition_keys(context, entity_uuid)
        ),
    )
    proposals: list[PolicyProposal] = []
    for seed in candidate_seeds:
        features = _direct_damage_features(
            context,
            seed.row,
            hostile_affected=seed.hostile_affected,
            controlled_affected=seed.controlled_affected,
            allied_affected=seed.allied_affected,
            additional_targets=seed.additional_targets,
            outcome_cache=outcome_cache,
        )
        if not features.hostile_affected:
            continue
        proposals.append(_damage_proposal(_DamageCandidateGroup(
            row=seed.row,
            semantic_tags=seed.semantic_tags,
            features=features,
            equivalent_rows=seed.equivalent_rows,
        )))
    return tuple(sorted(proposals, key=_proposal_replay_order_key))


def _grouped_direct_damage_rows(
    context: PolicyContext,
    visible_hostiles: set[str],
) -> tuple[
    tuple[tuple[ActionAffordance, ActionSemantics], ...],
    dict[str, int],
]:
    """Return direct rows from pre-derived source/semantics/affected groups."""
    group_indices = sorted({
        group_index
        for tag in DIRECT_DAMAGE_TAGS
        for group_index in (
            context.facts.affordances.affected_set_group_indices_by_tag.get(
                tag,
                tuple(),
            )
        )
    })
    support_by_source: dict[str, bool] = {}
    rows: list[tuple[ActionAffordance, ActionSemantics]] = []
    represented_rows: dict[str, int] = {}
    has_exact_row_exclusions = bool(
        context.execution_constraints.blocked_row_ids
    )
    for group_index in group_indices:
        group = context.facts.affordances.affected_set_groups[group_index]
        if not (group.affected_entity_uuids & visible_hostiles):
            continue
        canonical = context.facts.affordances.by_id.get(group.canonical_row_id)
        canonical_semantics = (
            context.facts.affordances.semantics_by_row_id.get(
                group.canonical_row_id
            )
        )
        if (
            canonical is None
            or canonical_semantics is None
            or not canonical_semantics.tags & DIRECT_DAMAGE_TAGS
        ):
            continue
        source_scope = group.source_action_id
        supports_collapse = support_by_source.get(source_scope)
        if supports_collapse is None:
            supports_collapse = _supports_transient_monotonic_area_damage(
                canonical,
                canonical_semantics,
                canonical_semantics.tags,
            )
            support_by_source[source_scope] = supports_collapse
        if supports_collapse and not has_exact_row_exclusions:
            if (
                context.execution_constraints.allows(canonical)
                and canonical.can_afford
                and canonical.cost.affordability != "unaffordable"
            ):
                rows.append((canonical, canonical_semantics))
                represented_rows[canonical.row_id] = len(group.row_ids)
            continue
        eligible: list[tuple[ActionAffordance, ActionSemantics]] = []
        for row_id in group.row_ids:
            row = context.facts.affordances.by_id.get(row_id)
            semantics = context.facts.affordances.semantics_by_row_id.get(row_id)
            if (
                row is None
                or semantics is None
                or not semantics.tags & DIRECT_DAMAGE_TAGS
                or not context.execution_constraints.allows(row)
                or not row.can_afford
                or row.cost.affordability == "unaffordable"
            ):
                continue
            eligible.append((row, semantics))
        if not eligible:
            continue
        if supports_collapse:
            selected = eligible[0]
            rows.append(selected)
            represented_rows[selected[0].row_id] = len(eligible)
        else:
            rows.extend(eligible)
            represented_rows.update({row.row_id: 1 for row, _semantics in eligible})
    return tuple(rows), represented_rows


def _damage_equivalence_key(
    row: ActionAffordance,
    semantic_tags: frozenset[ActionTag],
    *,
    hostile_affected: tuple[str, ...],
    controlled_affected: tuple[str, ...],
    allied_affected: tuple[str, ...],
    additional_targets: tuple[str, ...],
    affected_entity_uuids: tuple[str, ...],
    primary_target_uuid: Optional[str],
    contract_key: Optional[tuple[object, ...]] = None,
) -> tuple[object, ...]:
    """Return inputs that fully determine damage score and proposal evidence."""
    return (
        contract_key or _damage_contract_key(row, semantic_tags),
        primary_target_uuid,
        affected_entity_uuids,
        hostile_affected,
        controlled_affected,
        allied_affected,
        additional_targets,
    )


def _damage_contract_key(
    row: ActionAffordance,
    semantic_tags: frozenset[ActionTag],
) -> tuple[object, ...]:
    """Return target-independent policy inputs shared by one source action."""
    profile_key = (
        _outcome_profile_key(row.outcome_profile)
        if row.outcome_profile is not None
        else None
    )
    return (
        row.semantic_key,
        row.semantics_ref,
        semantic_tags,
        profile_key,
        _action_cost_profile_key(row),
        row.bucket,
        row.action_category,
        row.target_type,
        row.base_template_name,
        row.num_projectiles,
        row.allow_same_target,
        row.is_item_use,
        row.source_item_uuid,
        row.weapon_slot,
        row.damage_types,
        row.spell_level,
        row.cast_at_level,
        row.is_spell_variant,
        row.requires_concentration,
        row.tags,
    )


def _prune_dominated_area_damage_seeds(
    seeds: tuple[_DamageCandidateSeed, ...],
    *,
    damage_ending_control_uuids: frozenset[str],
) -> tuple[_DamageCandidateSeed, ...]:
    """Keep the typed Pareto frontier of comparable instantaneous area rows.

    A row dominates another only when both represent the same complete action
    contract and cost, affect a hostile superset, affect a known-friendly
    subset, and affect exactly the same remaining entities. Allocated attacks
    and actions carrying spatial, topology, information, control, summon, or
    persistent-zone meaning are intentionally outside this optimization.
    """
    families: dict[tuple[object, ...], list[_DamageCandidateSeed]] = {}
    for seed in seeds:
        if _supports_area_damage_frontier(seed):
            families.setdefault(_area_damage_frontier_family(seed), []).append(seed)

    dominated_row_ids: set[str] = set()
    for family in families.values():
        for candidate in family:
            if any(
                other is not candidate
                and _area_damage_seed_dominates(
                    other,
                    candidate,
                    damage_ending_control_uuids=damage_ending_control_uuids,
                )
                for other in family
            ):
                dominated_row_ids.add(candidate.row.row_id)
    return tuple(seed for seed in seeds if seed.row.row_id not in dominated_row_ids)


def _supports_area_damage_frontier(seed: _DamageCandidateSeed) -> bool:
    """Return whether one seed has monotonic instantaneous area semantics."""
    return _supports_transient_monotonic_area_damage(
        seed.row,
        seed.semantics,
        seed.semantic_tags,
    )


def _supports_transient_monotonic_area_damage(
    row: ActionAffordance,
    semantics: ActionSemantics,
    semantic_tags: frozenset[ActionTag],
) -> bool:
    """Return whether aim location matters only through the affected set."""
    profile = row.outcome_profile
    if (
        (
            profile is not None
            and profile.application_scope
            is not OutcomeApplicationScope.EACH_AFFECTED_ENTITY
        )
        or (
            profile is None
            and semantics.targeting.allocation is not TargetAllocation.AREA
        )
        or ActionTag.DAMAGE_AREA not in semantic_tags
        or not semantic_tags.issubset(AREA_DAMAGE_FRONTIER_TAGS)
        or semantics.concentration_effect is not None
        or semantics.spatial is not None
        or semantics.topology_effects
        or semantics.information_effects
        or not _area_damage_effects_are_monotonic(semantics)
        or not semantics.targeting.affected_relationships.issubset(
            {AffectedRelationship.HOSTILE}
        )
    ):
        return False
    return True


def _area_damage_effects_are_monotonic(semantics: ActionSemantics) -> bool:
    """Return whether declared effects are only target HP loss and consumption."""
    effects = [
        *semantics.guaranteed_effects,
        *(
            effect
            for conditional in semantics.conditional_effects
            for effect in conditional.effects
        ),
        *(
            effect
            for stochastic in semantics.stochastic_effects
            for effect in stochastic.effects
        ),
    ]
    if any(
        effect.fact_id != "selected_target.hp"
        or effect.operation is not EffectOperation.DECREASE
        for effect in effects
    ):
        return False
    return all(
        effect.operation is ResourceOperation.CONSUME
        for effect in semantics.resource_effects
    )


def _area_damage_frontier_family(seed: _DamageCandidateSeed) -> tuple[object, ...]:
    """Return exact invariant inputs required before comparing affected sets."""
    row = seed.row
    friendly = seed.controlled_affected_set | seed.allied_affected_set
    other_affected = frozenset(
        seed.affected_entity_uuid_set - seed.hostile_affected_set - friendly
    )
    return (
        row.semantic_key,
        row.semantics_ref,
        seed.semantic_tags,
        _outcome_profile_key(row.outcome_profile) if row.outcome_profile is not None else None,
        _action_cost_profile_key(row),
        row.bucket,
        row.action_category,
        row.target_type,
        row.base_template_name,
        row.num_projectiles,
        row.allow_same_target,
        row.is_item_use,
        row.source_item_uuid,
        row.weapon_slot,
        row.damage_types,
        row.spell_level,
        row.cast_at_level,
        row.is_spell_variant,
        row.requires_concentration,
        row.tags,
        other_affected,
    )


def _action_cost_profile_key(row: ActionAffordance) -> tuple[object, ...]:
    """Return every typed economy and resource input of an affordance row."""
    cost = row.cost
    return (
        cost.action_cost,
        cost.bonus_action_cost,
        cost.reaction_cost,
        cost.movement_cost,
        cost.consumes_attack_slot,
        cost.spell_slot_cost,
        tuple(sorted(cost.resource_costs.items())),
        tuple(sorted(cost.item_charge_costs.items())),
        cost.affordability,
        cost.affordability_reasons,
    )


def _area_damage_seed_dominates(
    candidate: _DamageCandidateSeed,
    other: _DamageCandidateSeed,
    *,
    damage_ending_control_uuids: frozenset[str],
) -> bool:
    """Return whether candidate is strictly no-worse by typed affected sets."""
    candidate_hostiles = candidate.hostile_affected_set
    other_hostiles = other.hostile_affected_set
    candidate_friendlies = (
        candidate.controlled_affected_set | candidate.allied_affected_set
    )
    other_friendlies = other.controlled_affected_set | other.allied_affected_set
    return (
        candidate_hostiles.issuperset(other_hostiles)
        and not (
            (candidate_hostiles - other_hostiles)
            & damage_ending_control_uuids
        )
        and candidate_friendlies.issubset(other_friendlies)
        and (
            candidate_hostiles != other_hostiles
            or candidate_friendlies != other_friendlies
        )
    )


def _affected_entity_uuids(
    context: PolicyContext,
    row: ActionAffordance,
) -> frozenset[str]:
    """Return indexed entities explicitly affected by one executable row."""
    indexed = context.evaluation_index.affected_entity_uuids_by_row_id.get(row.row_id)
    if indexed is not None:
        return indexed
    affected: set[str] = set()
    for target in row.targets:
        if target.target_uuid is not None:
            affected.add(target.target_uuid)
        affected.update(target.affected_entity_uuids)
    return frozenset(affected)


def _primary_target_uuid(
    context: PolicyContext,
    row: ActionAffordance,
) -> Optional[str]:
    """Return the indexed first explicit target of one legal row."""
    if row.row_id in context.evaluation_index.primary_target_uuid_by_row_id:
        return context.evaluation_index.primary_target_uuid_by_row_id[row.row_id]
    return next(
        (target.target_uuid for target in row.targets if target.target_uuid is not None),
        None,
    )


def _collapse_repeatable_damage_families(
    context: PolicyContext,
    rows: tuple[tuple[ActionAffordance, ActionSemantics], ...],
    *,
    outcome_cache: _OutcomeCache,
    allocation_cache: dict[AllocationCacheKey, Optional[tuple[tuple[str, int], ...]]],
) -> tuple[
    tuple[tuple[ActionAffordance, ActionSemantics], ...],
    dict[str, tuple[str, ...]],
    dict[str, int],
]:
    """Reduce one repeatable source action to one globally allocated command.

    The server flattens a multi-target action into one executable row per
    possible primary target. Those rows are command encodings, not independent
    tactical choices. Source-action identity lets policy optimize the complete
    allocation once, then retain the concrete row whose primary target appears
    in that allocation.
    """
    families: dict[str, list[tuple[ActionAffordance, ActionSemantics]]] = {}
    for row, semantics in rows:
        if (
            row.source_action_id is not None
            and row.allow_same_target is True
            and row.num_projectiles is not None
            and row.num_projectiles > 1
            and row.outcome_profile is not None
            and row.outcome_profile.application_scope
            is OutcomeApplicationScope.ALLOCATED_TARGETS
        ):
            families.setdefault(row.source_action_id, []).append((row, semantics))

    selected_by_source: dict[str, tuple[ActionAffordance, ActionSemantics]] = {}
    allocations: dict[str, tuple[str, ...]] = {}
    represented_rows: dict[str, int] = {}
    for source_action_id, family in families.items():
        if len(family) < 2 or not _repeatable_family_contracts_match(family):
            continue
        collapsed = _collapse_repeatable_damage_family(
            context,
            tuple(family),
            outcome_cache=outcome_cache,
            allocation_cache=allocation_cache,
        )
        if collapsed is None:
            continue
        selected, additional_targets = collapsed
        selected_by_source[source_action_id] = selected
        allocations[selected[0].row_id] = additional_targets
        represented_rows[selected[0].row_id] = len(family)

    collapsed_rows: list[tuple[ActionAffordance, ActionSemantics]] = []
    for row, semantics in rows:
        if row.source_action_id is None or row.source_action_id not in selected_by_source:
            collapsed_rows.append((row, semantics))
            continue
        selected = selected_by_source[row.source_action_id]
        if row.row_id == selected[0].row_id:
            collapsed_rows.append(selected)
    return tuple(collapsed_rows), allocations, represented_rows


def _repeatable_family_contracts_match(
    family: list[tuple[ActionAffordance, ActionSemantics]],
) -> bool:
    """Return whether one server family has one allocation contract."""
    first_row, first_semantics = family[0]
    first_contract = _damage_contract_key(first_row, first_semantics.tags)
    return all(
        semantics == first_semantics
        and _damage_contract_key(row, semantics.tags) == first_contract
        for row, semantics in family[1:]
    )


def _collapse_repeatable_damage_family(
    context: PolicyContext,
    family: tuple[tuple[ActionAffordance, ActionSemantics], ...],
    *,
    outcome_cache: _OutcomeCache,
    allocation_cache: dict[AllocationCacheKey, Optional[tuple[tuple[str, int], ...]]],
) -> Optional[tuple[tuple[ActionAffordance, ActionSemantics], tuple[str, ...]]]:
    """Choose one executable primary row for a globally optimized allocation."""
    first_row = family[0][0]
    profile = first_row.outcome_profile
    total_applications = first_row.num_projectiles
    if profile is None or total_applications is None:
        return None
    visible_hostiles = set(context.facts.contacts.visible_hostile_uuids)
    rows_by_primary: dict[str, tuple[ActionAffordance, ActionSemantics]] = {}
    legal_target_uuids: set[str] = set()
    for row, semantics in family:
        primary_uuid = _primary_target_uuid(context, row)
        if primary_uuid is not None and primary_uuid in visible_hostiles:
            prior = rows_by_primary.get(primary_uuid)
            if prior is None or row.row_id < prior[0].row_id:
                rows_by_primary[primary_uuid] = (row, semantics)
        legal_target_uuids.update(
            target.target_uuid
            for target in row.target_options
            if target.target_uuid is not None and target.target_uuid in visible_hostiles
        )
    legal_target_uuids.update(rows_by_primary)
    allocation = _optimize_repeat_allocation(
        context,
        profile,
        required_primary_uuid=None,
        legal_target_uuids=legal_target_uuids,
        total_applications=total_applications,
        outcome_cache=outcome_cache,
        allocation_cache=allocation_cache,
    )
    if allocation is None:
        return None
    counts = dict(allocation)
    possible_primaries = sorted(
        (entity_uuid for entity_uuid, count in allocation if count > 0 and entity_uuid in rows_by_primary),
        key=lambda entity_uuid: _entity_uuid_replay_token(context, entity_uuid),
    )
    if not possible_primaries:
        return None
    primary_uuid = possible_primaries[0]
    selected = rows_by_primary[primary_uuid]
    counts[primary_uuid] -= 1
    additional_targets = tuple(
        entity_uuid
        for entity_uuid in sorted(
            counts,
            key=lambda value: _entity_uuid_replay_token(context, value),
        )
        for _ in range(max(0, counts[entity_uuid]))
    )
    return selected, additional_targets


def _additional_targets(
    context: PolicyContext,
    row: ActionAffordance,
    *,
    outcome_cache: _OutcomeCache,
    allocation_cache: dict[AllocationCacheKey, Optional[tuple[tuple[str, int], ...]]],
) -> tuple[str, ...]:
    """Allocate remaining multi-target selections from visible legal options."""
    target_count = row.num_projectiles or 1
    remaining = max(0, target_count - 1)
    if remaining == 0:
        return tuple()

    visible_hostiles = set(context.facts.contacts.visible_hostile_uuids)
    legal_options = tuple(dict.fromkeys(
        target.target_uuid
        for target in row.target_options
        if target.target_uuid is not None and target.target_uuid in visible_hostiles
    ))
    if not legal_options:
        return tuple()
    ordered = sorted(
        legal_options,
        key=lambda entity_uuid: (
            _known_hp(context, entity_uuid),
            _entity_uuid_replay_token(context, entity_uuid),
        ),
    )
    primary_uuid = _primary_target_uuid(context, row)
    if (
        row.allow_same_target
        and primary_uuid is not None
        and row.outcome_profile is not None
        and row.outcome_profile.application_scope is OutcomeApplicationScope.ALLOCATED_TARGETS
    ):
        optimized = _optimize_repeat_allocation(
            context,
            row.outcome_profile,
            required_primary_uuid=primary_uuid,
            legal_target_uuids=(*legal_options, primary_uuid),
            total_applications=target_count,
            outcome_cache=outcome_cache,
            allocation_cache=allocation_cache,
        )
        if optimized is not None:
            remaining_counts = dict(optimized)
            remaining_counts[primary_uuid] -= 1
            return tuple(
                entity_uuid
                for entity_uuid in sorted(
                    remaining_counts,
                    key=lambda value: _entity_uuid_replay_token(context, value),
                )
                for _ in range(max(0, remaining_counts[entity_uuid]))
            )
    if row.allow_same_target:
        return tuple(ordered[0] for _ in range(remaining))
    return tuple(entity_uuid for entity_uuid in ordered if entity_uuid != primary_uuid)[:remaining]


def _optimize_repeat_allocation(
    context: PolicyContext,
    profile: ActionOutcomeProfile,
    *,
    required_primary_uuid: Optional[str],
    legal_target_uuids: Iterable[str],
    total_applications: int,
    outcome_cache: _OutcomeCache,
    allocation_cache: dict[AllocationCacheKey, Optional[tuple[tuple[str, int], ...]]],
) -> Optional[tuple[tuple[str, int], ...]]:
    """Allocate repeatable outcomes with bounded utility-aligned dynamic programming.

    An optional primary row target receives at least one application. The state
    score uses the same allocation-dependent terms exposed by the final damage
    proposal: visible coverage, expected HP loss, expected defeats, expected
    waste, wounded pressure, and reliability. Allocation therefore cannot
    silently optimize a different objective from the traced utility arbiter.
    """
    targets = tuple(sorted(
        dict.fromkeys(legal_target_uuids),
        key=lambda entity_uuid: _entity_uuid_replay_token(context, entity_uuid),
    ))
    if (
        total_applications <= 0
        or (
            required_primary_uuid is not None
            and required_primary_uuid not in targets
        )
    ):
        return None
    allocation_key: AllocationCacheKey = (
        _outcome_profile_key(profile),
        required_primary_uuid,
        targets,
        total_applications,
    )
    if allocation_key in allocation_cache:
        return allocation_cache[allocation_key]
    per_target: dict[tuple[str, int], SubjectiveDamageEstimate] = {}
    for entity_uuid in targets:
        entity = context.world.known_entities.get(entity_uuid)
        if entity is None:
            return None
        for count in range(1, total_applications + 1):
            estimate = _cached_damage_estimate(
                outcome_cache,
                profile,
                entity,
                applications=count,
                effect_block_hypothesis=(
                    context.facts.combat_memory.hypothesis_for(
                        entity_uuid,
                        profile.effect_id,
                    )
                    if profile.effect_id is not None
                    else None
                ),
            )
            if estimate is None:
                allocation_cache[allocation_key] = None
                return None
            per_target[(entity_uuid, count)] = estimate

    states: dict[
        tuple[int, float, float],
        tuple[float, tuple[int, ...]],
    ] = {(0, 0.0, 0.0): (0.0, tuple())}
    for entity_uuid in targets:
        next_states: dict[
            tuple[int, float, float],
            tuple[float, tuple[int, ...]],
        ] = {}
        minimum = 1 if entity_uuid == required_primary_uuid else 0
        wounded_fraction = _known_wounded_fraction(context, entity_uuid)
        for (used, peak_wounded, peak_nonzero), (score, counts) in states.items():
            for count in range(minimum, total_applications - used + 1):
                estimate = per_target.get((entity_uuid, count))
                contribution = 0.0
                next_peak_wounded = peak_wounded
                next_peak_nonzero = peak_nonzero
                if estimate is not None:
                    expected_waste = max(
                        0.0,
                        estimate.expected_raw_damage - estimate.expected_hp_loss,
                    )
                    _control_keys, expected_agency_restored = (
                        _expected_enemy_agency_restored(
                            context,
                            entity_uuid,
                            nonzero_probability=estimate.nonzero_probability,
                            defeat_probability=estimate.defeat_probability,
                        )
                    )
                    if not estimate.guaranteed_zero:
                        contribution = (
                            15.0
                            + estimate.expected_hp_loss
                            + 20.0 * estimate.defeat_probability
                            - 0.25 * expected_waste
                            - 55.0 * expected_agency_restored
                        )
                        next_peak_wounded = max(peak_wounded, wounded_fraction)
                        next_peak_nonzero = max(peak_nonzero, estimate.nonzero_probability)
                candidate = (score + contribution, (*counts, count))
                total = used + count
                state_key = (total, next_peak_wounded, next_peak_nonzero)
                prior = next_states.get(state_key)
                if prior is None or candidate[0] > prior[0] or (
                    candidate[0] == prior[0] and candidate[1] < prior[1]
                ):
                    next_states[state_key] = candidate
        states = next_states
    terminal_states = (
        (
            additive_score + 8.0 * peak_wounded + 3.0 * peak_nonzero,
            counts,
        )
        for (used, peak_wounded, peak_nonzero), (additive_score, counts) in states.items()
        if used == total_applications
    )
    selected = min(
        terminal_states,
        key=lambda candidate: (-candidate[0], candidate[1]),
        default=None,
    )
    if selected is None:
        allocation_cache[allocation_key] = None
        return None
    allocation = tuple(
        (entity_uuid, count)
        for entity_uuid, count in zip(targets, selected[1])
        if count > 0
    )
    allocation_cache[allocation_key] = allocation
    return allocation


def _additional_control_targets(
    context: PolicyContext,
    row: ActionAffordance,
    semantics: ActionSemantics,
) -> tuple[str, ...]:
    """Allocate distinct visible targets for multi-target control."""
    target_count = row.num_projectiles or 1
    remaining = max(0, target_count - 1)
    if remaining == 0:
        return tuple()
    visible_hostiles = set(context.facts.contacts.visible_hostile_uuids)
    primary_uuid = _primary_target_uuid(context, row)
    action_semantics = context.facts.affordances.semantics_by_row_id.get(row.row_id)
    if action_semantics is None or action_semantics is not semantics:
        return tuple()
    options = tuple(dict.fromkeys(
        target.target_uuid
        for target in row.target_options
        if target.target_uuid is not None
        and target.target_uuid in visible_hostiles
        and target.target_uuid != primary_uuid
        and not _control_effect_is_observed(context, target.target_uuid, action_semantics)
    ))
    ordered = sorted(
        options,
        key=lambda entity_uuid: (
            -_known_healthy_fraction(context, entity_uuid),
            _known_hp(context, entity_uuid),
            _entity_uuid_replay_token(context, entity_uuid),
        ),
    )
    return tuple(ordered[:remaining])


def _control_effect_is_observed(
    context: PolicyContext,
    entity_uuid: str,
    semantics: ActionSemantics,
) -> bool:
    """Return whether every declared condition effect is already observed."""
    condition_names = {
        effect.fact_id.removeprefix("selected_target.condition.").casefold()
        for stochastic in semantics.stochastic_effects
        for effect in stochastic.effects
        if effect.fact_id.startswith("selected_target.condition.")
    }
    condition_names.update(
        effect.fact_id.removeprefix("selected_target.condition.").casefold()
        for effect in semantics.guaranteed_effects
        if effect.fact_id.startswith("selected_target.condition.")
    )
    if not condition_names:
        return False
    entity = context.world.known_entities.get(entity_uuid)
    if entity is None:
        return False
    observed = {condition.casefold() for condition in entity.conditions}
    return condition_names.issubset(observed)


def _self_setup_effect_may_already_be_active(
    context: PolicyContext,
    semantics: ActionSemantics,
) -> bool:
    """Conservatively guard nonstacking setup when active-effect truth is unknown."""
    setup = semantics.self_setup
    if setup is None or not setup.active_condition_semantic_keys:
        return False
    observed = context.facts.actor.condition_semantic_keys
    if observed is None:
        return True
    return setup.active_condition_semantic_keys.issubset(observed)


def _defensive_effect_may_already_be_active(
    context: PolicyContext,
    semantics: ActionSemantics,
) -> bool:
    """Return whether a nonstacking defensive condition is already observed."""
    condition_names = {
        effect.fact_id.removeprefix("actor.condition.").casefold()
        for effect in semantics.guaranteed_effects
        if (
            effect.operation is EffectOperation.ADD
            and effect.fact_id.startswith("actor.condition.")
        )
    }
    if not condition_names:
        return False
    observed = {
        condition.casefold()
        for condition in context.facts.actor.conditions
    }
    return condition_names.issubset(observed)


def _has_immediate_defensive_condition(semantics: ActionSemantics) -> bool:
    """Return whether semantics establish a direct incoming-defense condition."""
    return any(
        effect.operation is EffectOperation.ADD
        and effect.fact_id == "actor.condition.dodging"
        for effect in semantics.guaranteed_effects
    )


def _direct_damage_features(
    context: PolicyContext,
    row: ActionAffordance,
    *,
    hostile_affected: tuple[str, ...],
    controlled_affected: tuple[str, ...],
    allied_affected: tuple[str, ...],
    additional_targets: tuple[str, ...],
    outcome_cache: _OutcomeCache,
) -> _DamageFeatures:
    """Collect observable score inputs without allocating trace models."""
    slot_level = row.cost.spell_slot_cost or row.cast_at_level or 0
    resource_cost = float(slot_level + sum(row.cost.resource_costs.values()))
    outcome = _outcome_summary(
        context,
        row,
        additional_targets,
        hostile_affected,
        outcome_cache,
    )
    modeled_outcomes = {item.entity_uuid: item for item in outcome.outcomes}
    effective_hostiles = tuple(
        entity_uuid
        for entity_uuid in hostile_affected
        if (
            entity_uuid not in modeled_outcomes
            or not modeled_outcomes[entity_uuid].guaranteed_zero
        )
    )
    wounded_pressure = max(
        (_known_wounded_fraction(context, entity_uuid) for entity_uuid in effective_hostiles),
        default=0.0,
    )
    return _DamageFeatures(
        hostile_affected=effective_hostiles,
        controlled_affected=controlled_affected,
        allied_affected=allied_affected,
        additional_targets=additional_targets,
        wounded_pressure=wounded_pressure,
        expected_hp_loss=outcome.expected_hp_loss,
        defeat_probability=outcome.defeat_probability,
        expected_defeats=outcome.expected_defeats,
        nonzero_probability=outcome.nonzero_probability,
        expected_waste=outcome.expected_waste,
        expected_enemy_agency_restored=sum(
            item.expected_enemy_agency_restored
            for item in outcome.outcomes
        ),
        penalize_expected_waste=(
            row.outcome_profile is None
            or row.outcome_profile.application_scope is OutcomeApplicationScope.ALLOCATED_TARGETS
        ),
        resource_cost=resource_cost,
        concentration_replacement=_actor_is_concentrating(context) and row.requires_concentration,
        replay_key=_action_replay_key(context, row, additional_targets),
        target_plan=_target_plan_evidence(
            context,
            row,
            additional_targets=additional_targets,
            hostile_affected=effective_hostiles,
            controlled_affected=controlled_affected,
            allied_affected=allied_affected,
            applications=outcome.applications,
        ),
        damage_outcomes=outcome.outcomes,
    )


def _damage_proposal(group: _DamageCandidateGroup) -> PolicyProposal:
    """Materialize one inspectable proposal for an equivalence class."""
    features = group.features
    components = [
        _component("legal_direct_pressure", 1.0, 100.0, "server-issued damage affordance"),
        _component(
            "visible_hostile_coverage",
            float(len(features.hostile_affected)),
            15.0,
            "visible hostile contacts explicitly affected",
        ),
        _component(
            "wounded_target_pressure",
            features.wounded_pressure,
            8.0,
            "known missing-hit-point fraction of the most wounded target",
        ),
    ]
    if features.expected_hp_loss is not None:
        components.extend([
            _component(
                "subjective_expected_hp_loss",
                features.expected_hp_loss,
                1.0,
                "exact dice distribution over actor-baseline rules and known target facts",
            ),
            _component(
                "subjective_expected_defeats",
                features.expected_defeats or 0.0,
                20.0,
                "sum of per-target modeled defeat probabilities",
            ),
            _component(
                "subjective_peak_defeat_probability",
                features.defeat_probability or 0.0,
                0.0,
                "highest per-target modeled defeat probability",
            ),
            _component(
                "subjective_damage_reliability",
                features.nonzero_probability or 0.0,
                3.0,
                "probability modeled damage is nonzero",
            ),
            _component(
                "subjective_expected_damage_waste",
                features.expected_waste or 0.0,
                -0.25 if features.penalize_expected_waste else 0.0,
                (
                    "finite allocated damage beyond subjectively known current HP"
                    if features.penalize_expected_waste
                    else "independent area damage does not consume another target's application"
                ),
            ),
        ])
    components.extend([
        _component(
            "expected_enemy_agency_restored",
            features.expected_enemy_agency_restored,
            -55.0,
            "positive nonlethal damage can remove visible full-turn control",
        ),
        _component(
            "action_economy_opportunity_cost",
            action_economy_opportunity_cost(group.row.cost),
            -4.0,
            "typed loss of flexible action, bonus-action, reaction, or granted-attack economy",
        ),
        _component(
            "limited_resource_cost",
            features.resource_cost,
            -2.0,
            "known spell-slot and named-resource expenditure",
        ),
        _component(
            "concentration_replacement",
            float(features.concentration_replacement),
            -20.0,
            "replaces an observed active concentration effect",
        ),
        _component(
            "known_friendly_fire",
            float(len(set(features.controlled_affected) | set(features.allied_affected))),
            -100.0,
            "controlled or visible allied entities explicitly affected",
        ),
        _component(
            "equivalent_legal_rows",
            float(group.equivalent_rows),
            0.0,
            "legal flattened rows with identical action-family and policy effects",
        ),
    ])
    component_tuple = tuple(components)
    return PolicyProposal(
        intent=ExecuteIntent(
            row_id=group.row.row_id,
            extra_target_uuids=features.additional_targets,
        ),
        goal=PolicyGoal.DIRECT_PRESSURE,
        source_node="Pressure/DirectDamage",
        reason=_damage_reason(group.semantic_tags),
        score=sum(component.contribution for component in component_tuple),
        replay_key=features.replay_key,
        utility_components=component_tuple,
        semantic_tags=group.semantic_tags,
        evidence=PolicyEvidence(
            target_plan=features.target_plan,
            damage_outcomes=features.damage_outcomes,
        ),
    )


def _damage_reason(semantic_tags: frozenset[ActionTag]) -> str:
    """Return a stable semantic rationale for one damage proposal."""
    if ActionTag.DAMAGE_AREA in semantic_tags:
        return "cast_visible_area_spell"
    if ActionTag.DAMAGE_MULTI_TARGET in semantic_tags:
        return "allocate_visible_multi_target_damage"
    return "legal semantic damage against a visible hostile"


def _control_proposal(group: _ControlCandidateGroup) -> PolicyProposal:
    """Materialize one inspectable control proposal."""
    features = group.features
    remaining_agency_value = (
        features.healthy_target_value
        if features.hard_control
        else 0.0
    )
    components = (
        _component("legal_control", 1.0, 100.0, "server-issued control affordance"),
        _component(
            "hard_control",
            remaining_agency_value,
            35.0,
            "hard control removes agency in proportion to known remaining target health",
        ),
        _component(
            "soft_control",
            float(features.soft_control),
            0.0,
            "soft-control classification requires typed effect value beyond legality",
        ),
        _component(
            "visible_hostile_coverage",
            float(len(features.hostile_affected)),
            15.0,
            "visible hostile contacts explicitly controlled",
        ),
        _component(
            "future_action_denial_value",
            remaining_agency_value,
            20.0,
            "known remaining-hit-point fraction whose future agency is denied",
        ),
        _component(
            "action_economy_opportunity_cost",
            action_economy_opportunity_cost(group.row.cost),
            -4.0,
            "typed loss of flexible action, bonus-action, reaction, or granted-attack economy",
        ),
        _component(
            "limited_resource_cost",
            features.resource_cost,
            -2.0,
            "known spell-slot and named-resource expenditure",
        ),
        _component(
            "concentration_replacement",
            float(features.concentration_replacement),
            -60.0,
            "replaces an observed active concentration effect",
        ),
        _component(
            "controlled_friendly_fire",
            float(len(features.controlled_affected)),
            -100.0,
            "controlled entities explicitly affected",
        ),
        _component(
            "equivalent_legal_rows",
            float(group.equivalent_rows),
            0.0,
            "legal flattened rows with identical control effects",
        ),
    )
    reason = (
        "establish_visible_hard_control"
        if features.hard_control
        else "establish_visible_soft_control"
    )
    return PolicyProposal(
        intent=ExecuteIntent(
            row_id=group.row.row_id,
            extra_target_uuids=features.additional_targets,
        ),
        goal=PolicyGoal.HOSTILE_CONTROL,
        source_node="Control/HostileControl",
        reason=reason,
        score=sum(component.contribution for component in components),
        replay_key=features.replay_key,
        utility_components=components,
        semantic_tags=group.semantic_tags,
        evidence=PolicyEvidence(target_plan=features.target_plan),
    )


def _outcome_summary(
    context: PolicyContext,
    row: ActionAffordance,
    additional_targets: tuple[str, ...],
    hostile_affected: tuple[str, ...],
    cache: _OutcomeCache,
) -> _OutcomeSummary:
    """Return cached outcome values when disclosed facts support them."""
    profile = row.outcome_profile
    primary_uuid = _primary_target_uuid(context, row)
    if profile is None:
        return _OutcomeSummary(None, None, None, None, None, tuple(), tuple())
    if profile.application_scope is OutcomeApplicationScope.EACH_AFFECTED_ENTITY:
        application_counts = Counter({
            entity_uuid: profile.applications
            for entity_uuid in hostile_affected
        })
    else:
        allocations = [primary_uuid, *additional_targets]
        allocations = [entity_uuid for entity_uuid in allocations if entity_uuid is not None]
        if primary_uuid is not None and profile.applications > len(allocations) and row.allow_same_target:
            allocations.extend(primary_uuid for _ in range(profile.applications - len(allocations)))
        application_counts = Counter(allocations)
    outcomes: list[DamageOutcomeEvidence] = []
    ordered_application_counts = sorted(
        application_counts.items(),
        key=lambda item: _entity_uuid_replay_token(context, item[0]),
    )
    for target_uuid, applications in ordered_application_counts:
        target = context.world.known_entities.get(target_uuid)
        if target is None:
            continue
        estimate = _cached_damage_estimate(
            cache,
            profile,
            target,
            applications=applications,
            effect_block_hypothesis=(
                context.facts.combat_memory.hypothesis_for(
                    target_uuid,
                    profile.effect_id,
                )
                if profile.effect_id is not None
                else None
            ),
        )
        if estimate is not None:
            control_keys, expected_agency_restored = (
                _expected_enemy_agency_restored(
                    context,
                    target_uuid,
                    nonzero_probability=estimate.nonzero_probability,
                    defeat_probability=estimate.defeat_probability,
                )
            )
            outcomes.append(DamageOutcomeEvidence(
                entity_uuid=target_uuid,
                applications=applications,
                expected_raw_damage=estimate.expected_raw_damage,
                expected_hp_loss=estimate.expected_hp_loss,
                expected_waste=max(0.0, estimate.expected_raw_damage - estimate.expected_hp_loss),
                defeat_probability=estimate.defeat_probability,
                nonzero_probability=estimate.nonzero_probability,
                guaranteed_zero=estimate.guaranteed_zero,
                released_control_condition_semantic_keys=control_keys,
                expected_enemy_agency_restored=expected_agency_restored,
                blocker_evidence=tuple(
                    DamageBlockerEvidence(
                        protection_id=blocker.protection_id,
                        effect_id=blocker.effect_id,
                        source_condition_semantic_key=(
                            blocker.source_condition_semantic_key
                        ),
                    )
                    for blocker in estimate.blocker_evidence
                ),
                effect_block_hypothesis=estimate.effect_block_hypothesis,
                model_scope=estimate.model_scope,
            ))
    applications = tuple(
        TargetApplicationEvidence(entity_uuid=entity_uuid, applications=count)
        for entity_uuid, count in ordered_application_counts
    )
    if not outcomes:
        return _OutcomeSummary(None, None, None, None, None, applications, tuple())
    return _OutcomeSummary(
        expected_hp_loss=sum(outcome.expected_hp_loss for outcome in outcomes),
        defeat_probability=max(outcome.defeat_probability for outcome in outcomes),
        expected_defeats=sum(outcome.defeat_probability for outcome in outcomes),
        nonzero_probability=max(outcome.nonzero_probability for outcome in outcomes),
        expected_waste=sum(outcome.expected_waste for outcome in outcomes),
        applications=applications,
        outcomes=tuple(outcomes),
    )


def _cached_damage_estimate(
    cache: _OutcomeCache,
    profile: ActionOutcomeProfile,
    target: ObservationEntityFact,
    *,
    applications: int,
    effect_block_hypothesis: Optional[TargetEffectBlockHypothesis],
) -> Optional[SubjectiveDamageEstimate]:
    """Return one decision-scoped damage estimate shared by all candidates."""
    key = (outcome_application_key(profile), target.uuid, applications)
    if key not in cache.values:
        cache.values[key] = estimate_damage_outcome(
            profile,
            target,
            applications=applications,
            workspace=cache.workspace,
            effect_block_hypothesis=effect_block_hypothesis,
        )
    return cache.values[key]


def _target_plan_evidence(
    context: PolicyContext,
    row: ActionAffordance,
    *,
    additional_targets: tuple[str, ...],
    hostile_affected: tuple[str, ...],
    controlled_affected: tuple[str, ...],
    allied_affected: tuple[str, ...] = tuple(),
    applications: tuple[TargetApplicationEvidence, ...] = tuple(),
) -> TargetPlanEvidence:
    """Build one immutable target plan from the executable row and allocation."""
    primary_uuid = _primary_target_uuid(context, row)
    selected = (
        *([primary_uuid] if primary_uuid is not None else []),
        *additional_targets,
    )
    affected = _sorted_entity_uuids(
        context,
        _affected_entity_uuids(context, row) | set(additional_targets),
    )
    return TargetPlanEvidence(
        primary_target_uuid=primary_uuid,
        selected_target_uuids=selected,
        affected_entity_uuids=affected,
        hostile_entity_uuids=hostile_affected,
        controlled_entity_uuids=controlled_affected,
        allied_entity_uuids=allied_affected,
        applications=applications,
    )


def _action_replay_key(
    context: PolicyContext,
    row: ActionAffordance,
    additional_targets: tuple[str, ...],
) -> tuple[str, ...]:
    """Return an opaque-identity-independent ordering key for one legal row."""
    return (
        row.semantic_key,
        str(row.cast_at_level or row.spell_level or 0),
        row.weapon_slot or "",
        *(_target_replay_token(context, target) for target in row.targets),
        "additional-targets",
        *(
            _entity_uuid_replay_token(context, entity_uuid)
            for entity_uuid in additional_targets
        ),
    )


def _target_replay_token(context: PolicyContext, target: ActionTarget) -> str:
    """Return the disclosed semantic identity of one executable target."""
    if target.target_uuid is not None:
        return _entity_uuid_replay_token(context, target.target_uuid)
    affected = _sorted_entity_uuids(context, target.affected_entity_uuids)
    return "|".join((
        "target-position",
        position_replay_token(target.position),
        *(_entity_uuid_replay_token(context, entity_uuid) for entity_uuid in affected),
    ))


def _sorted_entity_uuids(
    context: PolicyContext,
    entity_uuids: Iterable[str],
) -> tuple[str, ...]:
    """Order subjective entities by disclosed facts rather than opaque identity."""
    values = tuple(entity_uuids)
    if len(values) < 2:
        return values
    return tuple(sorted(
        values,
        key=lambda entity_uuid: _entity_uuid_replay_token(context, entity_uuid),
    ))


def _entity_uuid_replay_token(context: PolicyContext, entity_uuid: str) -> str:
    """Serialize one known entity's disclosed tactical identity without its UUID."""
    indexed = context.evaluation_index.entity_replay_tokens.get(entity_uuid)
    if indexed is not None:
        return indexed
    entity = context.world.known_entities.get(entity_uuid)
    if entity is None:
        return "entity|position=unknown|name=unknown"
    return entity_fact_replay_token(entity)


def _outcome_profile_key(profile: ActionOutcomeProfile) -> OutcomeCacheKey:
    """Return a hashable value key for one disclosed actor outcome model."""
    return outcome_profile_key(profile)


def _known_hp(context: PolicyContext, entity_uuid: str) -> tuple[bool, int]:
    """Sort known low HP first and explicitly place unknown HP last."""
    indexed = context.evaluation_index.known_hp_sort_keys.get(entity_uuid)
    if indexed is not None:
        return indexed
    entity = context.world.known_entities.get(entity_uuid)
    if entity is None or entity.hp is None:
        return (True, 0)
    return (False, entity.hp)


def _known_wounded_fraction(context: PolicyContext, entity_uuid: str) -> float:
    """Return known missing-HP fraction without assigning values to unknown HP."""
    indexed = context.evaluation_index.wounded_fractions.get(entity_uuid)
    if indexed is not None:
        return indexed
    entity = context.world.known_entities.get(entity_uuid)
    if entity is None or entity.hp is None or entity.max_hp is None or entity.max_hp <= 0:
        return 0.0
    return max(0.0, min(1.0, (entity.max_hp - entity.hp) / entity.max_hp))


def _known_healthy_fraction(context: PolicyContext, entity_uuid: str) -> float:
    """Return known remaining-HP fraction without filling unknown values."""
    indexed = context.evaluation_index.healthy_fractions.get(entity_uuid)
    if indexed is not None:
        return indexed
    entity = context.world.known_entities.get(entity_uuid)
    if entity is None or entity.hp is None or entity.max_hp is None or entity.max_hp <= 0:
        return 0.0
    return max(0.0, min(1.0, entity.hp / entity.max_hp))


def _damage_ending_control_condition_keys(
    context: PolicyContext,
    entity_uuid: str,
) -> tuple[str, ...]:
    """Return visible full-agency conditions removed by positive applied damage."""
    entity = context.world.known_entities.get(entity_uuid)
    if entity is None or entity.condition_facts is None:
        return tuple()
    return tuple(sorted(
        condition.semantic_key
        for condition in entity.condition_facts
        if (
            ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED
            in condition.removal_triggers
            and condition.agency_denial is ConditionAgencyDenial.FULL_TURN
        )
    ))


def _newly_applied_damage_ending_condition_keys(
    context: PolicyContext,
    entity_uuid: str,
    turn_started_source_event_cursor: int,
) -> tuple[str, ...]:
    """Return damage-ending full control established in the current turn."""
    entity = context.world.known_entities.get(entity_uuid)
    if entity is None or entity.condition_facts is None:
        return tuple()
    return tuple(sorted(
        condition.semantic_key
        for condition in entity.condition_facts
        if (
            ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED
            in condition.removal_triggers
            and condition.agency_denial is ConditionAgencyDenial.FULL_TURN
            and condition.applied_source_event_cursor is not None
            and condition.applied_source_event_cursor
            >= turn_started_source_event_cursor
        )
    ))


def _expected_enemy_agency_restored(
    context: PolicyContext,
    entity_uuid: str,
    *,
    nonzero_probability: float,
    defeat_probability: float,
) -> tuple[tuple[str, ...], float]:
    """Estimate surviving enemy agency restored when damage removes control."""
    condition_keys = _damage_ending_control_condition_keys(context, entity_uuid)
    if not condition_keys:
        return tuple(), 0.0
    release_and_survive_probability = max(
        0.0,
        nonzero_probability - defeat_probability,
    )
    return (
        condition_keys,
        _known_healthy_fraction(context, entity_uuid)
        * release_and_survive_probability,
    )


def _actor_is_concentrating(context: PolicyContext) -> bool:
    """Return whether the controlled actor is observed concentrating."""
    return context.facts.actor.is_concentrating


def _future_capability_target_projections(
    context: PolicyContext,
    *,
    topology_workspace: Optional[KnownLineOfSightWorkspace] = None,
) -> tuple[CapabilityTargetProjection, ...]:
    """Project actor capabilities against living visible subjective targets."""
    economy = context.facts.actor.economy
    actor_position = context.facts.actor.position
    if economy is None or actor_position is None:
        return tuple()
    line_workspace = topology_workspace or KnownLineOfSightWorkspace.from_world(
        context.world,
        vision_blocker_positions=context.facts.topology.vision_blocker_positions,
    )
    workspace = DamageOutcomeWorkspace()
    targets = tuple(
        target
        for entity_uuid in context.facts.contacts.visible_hostile_uuids
        for target in [context.world.known_entities.get(entity_uuid)]
        if target is not None
        and target.position is not None
        and target.is_dead is not True
    )
    line_cache: dict[tuple[tuple[int, int], tuple[int, int]], TruthValue] = {}
    projections: list[CapabilityTargetProjection] = []
    for capability in context.facts.capabilities.rows:
        semantics = context.facts.capabilities.semantics_by_capability_id.get(
            capability.capability_id
        )
        maximum = capability.normal_range_feet or 0
        if (
            semantics is None
            or not semantics.tags.intersection(DIRECT_DAMAGE_TAGS)
            or capability.valid_target_filter not in {"enemies", "all"}
            or maximum < 5
        ):
            continue
        ranged = (
            (capability.range_type or "").casefold() in {"range", "ranged"}
            or maximum >= RANGED_SPACING_FLOOR_CELLS * 5
        )
        preferred_minimum = (
            min(RANGED_SPACING_FLOOR_CELLS * 5, maximum)
            if ranged
            else min(5, maximum)
        )
        persistent_requirements = tuple(
            CapabilityResourceRequirement(
                resource_id=resource_id,
                required=required,
                available=available,
            )
            for resource_id, required, available
            in capability_persistent_resource_requirements(economy, capability)
        )
        affordability_reasons = tuple(sorted({
            *capability_persistent_affordability_reasons(economy, capability),
            *(
                f"gate.{gate.name}"
                for gate in economy.gates
                if gate.active and gate.name != "no_meaningful_commands"
            ),
        }))
        concentration_operation = (
            semantics.concentration_effect.operation
            if semantics.concentration_effect is not None
            else None
        )
        for target in targets:
            assert target.position is not None
            model_status, estimate = _future_capability_outcome(
                capability,
                target,
                workspace,
            )
            pressure_value = (
                estimate.expected_hp_loss + estimate.defeat_probability * 5.0
                if estimate is not None
                else None
            )
            line_key = (actor_position, target.position)
            line_of_sight = line_cache.get(line_key)
            if line_of_sight is None:
                line_of_sight = known_line_of_sight(
                    context.world,
                    actor_position,
                    target.position,
                    workspace=line_workspace,
                )
                line_cache[line_key] = line_of_sight
            rejection_reasons = [*affordability_reasons]
            if model_status is CapabilityModelStatus.UNMODELED:
                rejection_reasons.append("outcome.unmodeled")
            elif model_status is CapabilityModelStatus.GUARANTEED_ZERO:
                rejection_reasons.append("outcome.guaranteed_zero")
            if capability.requires_line_of_sight and line_of_sight is TruthValue.FALSE:
                rejection_reasons.append("line_of_sight.false")
            distance_feet = grid_distance_feet(actor_position, target.position)
            projections.append(CapabilityTargetProjection(
                projection_scope=CapabilityProjectionScope.FUTURE_TURN,
                capability_id=capability.capability_id,
                semantic_id=semantics.semantic_id,
                target_entity_uuid=target.uuid,
                origin_position=actor_position,
                target_position=target.position,
                distance_feet=distance_feet,
                normal_range_feet=maximum,
                preferred_minimum_range_feet=preferred_minimum,
                range_state=(
                    CapabilityRangeState.IN_RANGE
                    if distance_feet <= maximum
                    else CapabilityRangeState.OUT_OF_RANGE
                ),
                requires_line_of_sight=capability.requires_line_of_sight,
                line_of_sight=line_of_sight,
                turn_refresh_assumed=True,
                persistent_requirements=persistent_requirements,
                affordable_after_refresh=capability_is_turn_refreshable(
                    economy,
                    capability,
                ),
                affordability_reasons=affordability_reasons,
                concentration_operation=concentration_operation,
                actor_is_concentrating=context.facts.actor.is_concentrating,
                replaces_concentration=(
                    context.facts.actor.is_concentrating
                    and concentration_operation is ConcentrationOperation.START_OR_REPLACE
                ),
                model_status=model_status,
                expected_hp_loss=(
                    estimate.expected_hp_loss if estimate is not None else None
                ),
                defeat_probability=(
                    estimate.defeat_probability if estimate is not None else None
                ),
                nonzero_probability=(
                    estimate.nonzero_probability if estimate is not None else None
                ),
                pressure_value=pressure_value,
                model_scope=estimate.model_scope if estimate is not None else None,
                eligible=not rejection_reasons,
                rejection_reasons=tuple(sorted(rejection_reasons)),
            ))
    return tuple(sorted(
        projections,
        key=lambda projection: (
            projection.semantic_id,
            projection.target_position,
            projection.normal_range_feet,
            projection.capability_id,
        ),
    ))


def _future_capability_outcome(
    capability: ActionCapability,
    target: ObservationEntityFact,
    workspace: DamageOutcomeWorkspace,
) -> tuple[CapabilityModelStatus, Optional[SubjectiveDamageEstimate]]:
    """Classify one capability-target outcome without inventing missing facts."""
    profile = capability.outcome_profile
    if (
        profile is None
        or not profile.damage_rolls
        or profile.resolution is OutcomeResolution.UNKNOWN
    ):
        return CapabilityModelStatus.UNMODELED, None
    estimate = estimate_damage_outcome(profile, target, workspace=workspace)
    if estimate is None:
        return CapabilityModelStatus.INSUFFICIENT_FACTS, None
    if estimate.guaranteed_zero:
        return CapabilityModelStatus.GUARANTEED_ZERO, estimate
    return CapabilityModelStatus.MODELED, estimate


def _capability_projection_at_origin(
    context: PolicyContext,
    projection: CapabilityTargetProjection,
    origin: tuple[int, int],
    *,
    topology_workspace: Optional[KnownLineOfSightWorkspace] = None,
) -> CapabilityTargetProjection:
    """Reproject selected capability geometry at one subjective movement endpoint."""
    line_workspace = topology_workspace or KnownLineOfSightWorkspace.from_world(
        context.world,
        vision_blocker_positions=context.facts.topology.vision_blocker_positions,
    )
    line_of_sight = known_line_of_sight(
        context.world,
        origin,
        projection.target_position,
        workspace=line_workspace,
    )
    rejection_reasons = [
        reason
        for reason in projection.rejection_reasons
        if reason != "line_of_sight.false"
    ]
    if projection.requires_line_of_sight and line_of_sight is TruthValue.FALSE:
        rejection_reasons.append("line_of_sight.false")
    distance_feet = grid_distance_feet(origin, projection.target_position)
    return projection.model_copy(update={
        "projection_scope": CapabilityProjectionScope.MOVEMENT_ENDPOINT,
        "origin_position": origin,
        "distance_feet": distance_feet,
        "range_state": (
            CapabilityRangeState.IN_RANGE
            if distance_feet <= projection.normal_range_feet
            else CapabilityRangeState.OUT_OF_RANGE
        ),
        "line_of_sight": line_of_sight,
        "eligible": not rejection_reasons,
        "rejection_reasons": tuple(sorted(rejection_reasons)),
    })


def _projection_limited_resource_cost(
    projection: CapabilityTargetProjection,
) -> float:
    """Return disclosed persistent resource burden for one projection."""
    return float(sum(
        requirement.required
        for requirement in projection.persistent_requirements
    ))


def _non_dominated_distance_envelopes(
    envelopes: tuple[CapabilityTargetProjection, ...],
) -> tuple[CapabilityTargetProjection, ...]:
    """Remove future envelopes dominated at the current subjective geometry."""
    retained = [
        envelope
        for envelope in envelopes
        if not any(
            _distance_envelope_dominates(
                candidate,
                envelope,
            )
            for candidate in envelopes
            if candidate is not envelope
        )
    ]
    return tuple(sorted(
        retained,
        key=lambda envelope: (
            envelope.capability_id,
            envelope.target_position,
            envelope.preferred_minimum_range_feet,
            envelope.normal_range_feet,
        ),
    ))


def _distance_envelope_dominates(
    candidate: CapabilityTargetProjection,
    other: CapabilityTargetProjection,
) -> bool:
    """Return whether one typed future option is no worse on every axis."""
    candidate_deficit = _distance_envelope_deficit(
        candidate.distance_feet // 5,
        candidate,
    )
    other_deficit = _distance_envelope_deficit(
        other.distance_feet // 5,
        other,
    )
    pressure_comparable = candidate.model_status is other.model_status
    pressure_no_worse = (
        pressure_comparable
        and (candidate.pressure_value or 0.0) >= (other.pressure_value or 0.0)
    )
    pressure_better = (
        pressure_comparable
        and (candidate.pressure_value or 0.0) > (other.pressure_value or 0.0)
    )
    no_worse = (
        pressure_no_worse
        and candidate.replaces_concentration <= other.replaces_concentration
        and _projection_limited_resource_cost(candidate)
        <= _projection_limited_resource_cost(other)
        and candidate.normal_range_feet >= other.normal_range_feet
        and candidate_deficit <= other_deficit
        and _line_of_sight_rank(candidate.line_of_sight)
        <= _line_of_sight_rank(other.line_of_sight)
    )
    strictly_better = (
        pressure_better
        or candidate.replaces_concentration < other.replaces_concentration
        or _projection_limited_resource_cost(candidate)
        < _projection_limited_resource_cost(other)
        or candidate.normal_range_feet > other.normal_range_feet
        or candidate_deficit < other_deficit
        or _line_of_sight_rank(candidate.line_of_sight)
        < _line_of_sight_rank(other.line_of_sight)
    )
    return no_worse and strictly_better


def _select_future_distance_envelope(
    envelopes: tuple[CapabilityTargetProjection, ...],
) -> CapabilityTargetProjection:
    """Select one typed future capability before scoring position changes."""
    if not envelopes:
        raise ValueError("at least one future capability envelope is required")
    return min(envelopes, key=_future_capability_selection_key)


def _future_capability_selection_key(
    envelope: CapabilityTargetProjection,
) -> tuple[bool, float, int, int, float, int, int, int, int, str, tuple[int, int], str]:
    """Rank strategic future capability quality before positional convenience."""
    return (
        envelope.replaces_concentration,
        _projection_limited_resource_cost(envelope),
        _capability_model_rank(envelope.model_status),
        int(envelope.range_state is CapabilityRangeState.OUT_OF_RANGE),
        -(envelope.pressure_value or 0.0),
        _line_of_sight_rank(envelope.line_of_sight),
        _distance_envelope_deficit(envelope.distance_feet // 5, envelope),
        -envelope.preferred_minimum_range_feet,
        -envelope.normal_range_feet,
        envelope.semantic_id,
        envelope.target_position,
        envelope.capability_id,
    )


def _capability_model_rank(status: CapabilityModelStatus) -> int:
    """Return explicit selection preference for outcome knowledge states."""
    return {
        CapabilityModelStatus.MODELED: 0,
        CapabilityModelStatus.INSUFFICIENT_FACTS: 1,
        CapabilityModelStatus.UNMODELED: 2,
        CapabilityModelStatus.GUARANTEED_ZERO: 3,
    }[status]


def _line_of_sight_rank(value: TruthValue) -> int:
    """Prefer proven lines while retaining explicitly unknown topology."""
    return {
        TruthValue.TRUE: 0,
        TruthValue.UNKNOWN: 1,
        TruthValue.FALSE: 2,
    }[value]


def _projection_status_counts(
    projections: tuple[CapabilityTargetProjection, ...],
) -> dict[CapabilityModelStatus, int]:
    """Count outcome knowledge states for bounded observability."""
    counts = {status: 0 for status in CapabilityModelStatus}
    for projection in projections:
        counts[projection.model_status] += 1
    return counts


def _projection_count_components(
    counts: dict[CapabilityModelStatus, int],
) -> tuple[UtilityComponent, ...]:
    """Build zero-weight projection-status telemetry components."""
    return tuple(
        _component(
            f"capability_projection_{status.value}",
            float(counts.get(status, 0)),
            0.0,
            "capability-target pairs in this explicit outcome knowledge state",
        )
        for status in CapabilityModelStatus
    )


def _projection_status_components(
    projections: tuple[CapabilityTargetProjection, ...],
) -> tuple[UtilityComponent, ...]:
    """Build projection-status telemetry from evaluated pairs."""
    return _projection_count_components(_projection_status_counts(projections))


def _distance_envelope_deficit(
    distance: int,
    envelope: CapabilityTargetProjection,
) -> int:
    """Return cells outside a preferred capability distance interval."""
    preferred_minimum = envelope.preferred_minimum_range_feet // 5
    maximum = envelope.normal_range_feet // 5
    return max(0, preferred_minimum - distance) + max(
        0,
        distance - maximum,
    )


def _spacing_deficit(distance: int, floor: int) -> int:
    """Return bounded distance still needed to satisfy one spacing floor."""
    return max(0, floor - distance)


def _optional_spacing_deficit(
    distance: Optional[int],
    floor: int,
) -> Optional[int]:
    """Return a spacing deficit only when a reference distance is known."""
    return _spacing_deficit(distance, floor) if distance is not None else None


def _nearest_controlled_ally_distance(
    context: PolicyContext,
    position: tuple[int, int],
) -> Optional[int]:
    """Return nearest known living controlled ally distance from a position."""
    actor_uuid = context.facts.actor.actor_uuid
    distances = [
        _grid_distance(position, entity.position)
        for entity_uuid in context.facts.contacts.controlled_entity_uuids
        if entity_uuid != actor_uuid
        for entity in [context.world.known_entities.get(entity_uuid)]
        if entity is not None and entity.position is not None and entity.is_dead is not True
    ]
    return min(distances) if distances else None


def _grid_distance(left: tuple[int, int], right: tuple[int, int]) -> int:
    """Return the engine's floored Euclidean distance in grid cells."""
    return grid_distance_feet(left, right) // 5


def _spacing_reference_key(
    origin: tuple[int, int],
    entity: ObservationEntityFact,
) -> tuple[int, str]:
    """Return deterministic nearest-reference ordering for a known contact."""
    return (
        _grid_distance(origin, entity.position) if entity.position is not None else 2**31 - 1,
        entity_fact_replay_token(entity),
    )


def _component(name: str, raw: float, weight: float, reason: str) -> UtilityComponent:
    """Build one inspectable utility component."""
    return UtilityComponent(
        name=name,
        raw_value=raw,
        weight=weight,
        contribution=raw * weight,
        reason=reason,
    )


def _proposal_replay_order_key(
    proposal: PolicyProposal,
) -> tuple[tuple[str, ...], str]:
    """Order candidate discovery semantically with opaque identity as a last tie-breaker."""
    if isinstance(proposal.intent, ExecuteIntent):
        fallback = proposal.intent.row_id if not proposal.replay_key else ""
    else:
        fallback = proposal.intent.kind if not proposal.replay_key else ""
    return proposal.replay_key, fallback
