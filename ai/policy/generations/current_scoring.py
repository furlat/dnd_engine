"""Generation-owned tactical value model for the current candidate policy."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ai.policy.contracts import (
    PolicyContext,
    PolicyProposal,
    UtilityComponent,
)
from dnd.ai.contracts.control import ActionAffordance
from dnd.ai.contracts.decision import ExecuteIntent
from dnd.ai.contracts.semantics import ActionSemantics, ActionTag, OutcomeKind

SETUP_VALUE_HORIZON_TURNS = 2.0

class CandidateValueModel(BaseModel):
    """Immutable base for current-generation value records."""

    model_config = ConfigDict(frozen=True)


class TacticalValueVector(CandidateValueModel):
    """Common tactical units used to compare every policy proposal."""

    legal_option: float = Field(default=1.0, description="Legality value shared by every executable proposal.")
    expected_enemy_hp_loss: float = Field(default=0.0, description="Expected visible-hostile hit points removed.")
    enemy_defeat_probability: float = Field(default=0.0, description="Expected number of visible-hostile defeats.")
    expected_ally_hp_preserved: float = Field(default=0.0, description="Expected controlled or allied hit points preserved.")
    expected_enemy_actions_denied: float = Field(default=0.0, description="Expected hostile turns or actions denied.")
    expected_actor_actions_preserved: float = Field(default=0.0, description="Expected future controlled-actor agency preserved.")
    information_gain: float = Field(default=0.0, description="Expected subjective information acquired.")
    positional_value: float = Field(default=0.0, description="Improvement in a typed tactical position or capability envelope.")
    resource_expenditure: float = Field(default=0.0, description="Finite spell, class, or item resources consumed.")
    action_opportunity_cost: float = Field(default=0.0, description="Flexible action-economy units consumed.")
    concentration_value_lost: float = Field(default=0.0, description="Retained concentration value replaced or abandoned.")
    friendly_harm: float = Field(default=0.0, description="Controlled or allied recipients adversely affected.")
    risk: float = Field(default=0.0, description="Known route, retaliation, or tactical risk accepted.")


class PolicyValueProfile(CandidateValueModel):
    """Scalarization weights owned by one executable policy generation."""

    legal_option_weight: float = Field(default=6.0, description="Weight for one legal executable choice.")
    enemy_hp_loss_weight: float = Field(default=8.0, description="Weight per expected hostile hit point removed.")
    enemy_defeat_weight: float = Field(default=45.0, description="Weight per expected hostile defeat.")
    ally_hp_preserved_weight: float = Field(default=7.0, description="Weight per expected allied hit point preserved.")
    enemy_action_denial_weight: float = Field(default=55.0, description="Weight per expected hostile action denied.")
    actor_action_preservation_weight: float = Field(default=35.0, description="Weight per expected controlled action preserved.")
    information_gain_weight: float = Field(default=2.0, description="Weight per unit of subjective information gain.")
    positional_value_weight: float = Field(default=5.0, description="Weight per typed positional-value unit.")
    resource_expenditure_weight: float = Field(default=-6.0, description="Penalty per finite resource unit spent.")
    action_opportunity_cost_weight: float = Field(default=-10.0, description="Penalty per flexible economy unit spent.")
    concentration_loss_weight: float = Field(default=-65.0, description="Penalty for replacing retained concentration value.")
    friendly_harm_weight: float = Field(default=-90.0, description="Penalty per allied recipient harmed.")
    risk_weight: float = Field(default=-25.0, description="Penalty per known tactical-risk unit.")
    undisclosed_outcome_prior: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Policy prior used when semantics disclose a stochastic mechanism but no probability.",
    )


CURRENT_VALUE_PROFILE = PolicyValueProfile()


_VALUE_COMPONENTS = (
    ("legal_option", "legal_option_weight", "server-issued executable option"),
    ("expected_enemy_hp_loss", "enemy_hp_loss_weight", "modeled hostile HP reduction"),
    ("enemy_defeat_probability", "enemy_defeat_weight", "modeled hostile defeat probability"),
    ("expected_ally_hp_preserved", "ally_hp_preserved_weight", "modeled allied HP preservation"),
    ("expected_enemy_actions_denied", "enemy_action_denial_weight", "typed hostile agency denial"),
    ("expected_actor_actions_preserved", "actor_action_preservation_weight", "controlled agency preservation"),
    ("information_gain", "information_gain_weight", "subjective knowledge gain"),
    ("positional_value", "positional_value_weight", "typed position or capability-envelope improvement"),
    ("resource_expenditure", "resource_expenditure_weight", "finite spell, class, and item expenditure"),
    ("action_opportunity_cost", "action_opportunity_cost_weight", "flexible action-economy opportunity cost"),
    ("concentration_value_lost", "concentration_loss_weight", "retained concentration replaced"),
    ("friendly_harm", "friendly_harm_weight", "controlled or allied recipients adversely affected"),
    ("risk", "risk_weight", "known route, retaliation, or tactical risk"),
)


def scalarize_tactical_value(
    vector: TacticalValueVector,
    profile: PolicyValueProfile = CURRENT_VALUE_PROFILE,
) -> tuple[float, tuple[UtilityComponent, ...]]:
    """Return one comparable score and its complete contribution trace."""
    components = tuple(
        UtilityComponent(
            name=field_name,
            raw_value=float(getattr(vector, field_name)),
            weight=float(getattr(profile, weight_name)),
            contribution=float(getattr(vector, field_name)) * float(getattr(profile, weight_name)),
            reason=reason,
        )
        for field_name, weight_name, reason in _VALUE_COMPONENTS
        if getattr(vector, field_name) != 0.0
    )
    return sum(component.contribution for component in components), components


def proposal_with_tactical_value(
    proposal: PolicyProposal,
    vector: TacticalValueVector,
    *,
    profile: PolicyValueProfile = CURRENT_VALUE_PROFILE,
) -> PolicyProposal:
    """Replace a proposal's branch-local score with the shared value profile."""
    score, components = scalarize_tactical_value(vector, profile)
    return proposal.model_copy(update={"score": score, "utility_components": components})


def tactical_value_for_proposal(
    context: PolicyContext,
    proposal: PolicyProposal,
    *,
    profile: PolicyValueProfile = CURRENT_VALUE_PROFILE,
) -> TacticalValueVector:
    """Reduce typed proposal evidence into common tactical value units."""
    row, semantics = _proposal_row_and_semantics(context, proposal)
    evidence = proposal.evidence
    enemy_hp_loss = sum(outcome.expected_hp_loss for outcome in evidence.damage_outcomes)
    enemy_defeats = sum(outcome.defeat_probability for outcome in evidence.damage_outcomes)
    ally_hp_preserved = evidence.healing.expected_hp_restored if evidence.healing is not None else 0.0
    enemy_actions_denied = 0.0
    actor_actions_preserved = 0.0
    information_gain = 0.0
    positional_value = 0.0
    friendly_harm = 0.0
    risk = sum(outcome.expected_enemy_agency_restored for outcome in evidence.damage_outcomes)

    target_plan = evidence.target_plan
    if target_plan is not None:
        friendly_harm += float(len(target_plan.controlled_entity_uuids) + len(target_plan.allied_entity_uuids))
        hostile_count = len(target_plan.hostile_entity_uuids)
        if ActionTag.CONTROL_HARD in proposal.semantic_tags:
            enemy_actions_denied += hostile_count * 0.8 * _semantic_success_probability(semantics, profile)
        elif ActionTag.CONTROL_SOFT in proposal.semantic_tags:
            enemy_actions_denied += hostile_count * 0.35 * _semantic_success_probability(semantics, profile)

    if evidence.target_effects:
        harmful = sum(effect.disposition.value == "harmful" for effect in evidence.target_effects)
        beneficial = sum(effect.disposition.value == "beneficial" for effect in evidence.target_effects)
        enemy_actions_denied += harmful * 0.3 * _semantic_success_probability(semantics, profile)
        actor_actions_preserved += beneficial * 0.2

    setup = evidence.self_setup
    if setup is not None:
        retention_probability = (
            setup.first_maintenance_success_probability
            if setup.first_maintenance_success_probability is not None
            else 1.0
        )
        horizon_turns = (
            min(SETUP_VALUE_HORIZON_TURNS, float(setup.maximum_duration_rounds))
            if setup.maximum_duration_rounds is not None
            else SETUP_VALUE_HORIZON_TURNS
        )
        actor_actions_preserved += (
            setup.armor_class_bonus * 0.10
            + setup.extra_actions_per_turn * horizon_turns
            + float(setup.grants_incoming_attack_disadvantage) * 0.65
            + float(setup.grants_invisibility) * 0.75
            + float(setup.grants_outgoing_attack_advantage) * 0.35
        ) * retention_probability
        semantic_setup = semantics.self_setup if semantics is not None else None
        if semantic_setup is not None:
            actor_actions_preserved += (
                float(semantic_setup.grants_bonus_action_attack) * horizon_turns
                + float(semantic_setup.increases_weapon_damage) * 0.25 * horizon_turns
            ) * retention_probability
            ally_hp_preserved += (
                float(bool(semantic_setup.resistance_damage_types))
                * max(1, len(context.facts.contacts.visible_hostile_uuids))
                * 0.5
                * horizon_turns
                * retention_probability
            )
            positional_value += (
                max(0.0, semantic_setup.movement_speed_multiplier - 1.0)
                * horizon_turns
                * retention_probability
            )
            risk += (
                float(semantic_setup.grants_incoming_attack_advantage)
                * 0.5
                * horizon_turns
                + float(semantic_setup.incapacitates_on_removal) * 0.5
            ) * retention_probability

    if ActionTag.DEFENSE_SELF in proposal.semantic_tags and ActionTag.SETUP_SELF not in proposal.semantic_tags:
        actor_actions_preserved += _defensive_survival_value(context)

    spacing = evidence.spacing
    if spacing is not None:
        positional_value += max(
            0.0,
            float((spacing.current_distance_cells or 0) - (spacing.selected_distance_cells or 0)),
        )
        projection = spacing.capability_target_projection
        if projection is not None and projection.pressure_value is not None:
            positional_value += projection.pressure_value * 0.4
        risk += 0.65 * len(spacing.opportunity_attack_exposures)

    exploration = evidence.exploration
    if exploration is not None:
        information_gain += min(12.0, float(exploration.unknown_frontier_count))
        information_gain += min(6.0, exploration.remembered_search_novelty_feet / 5.0)
        information_gain += 2.0 * len(exploration.information_operations)
        risk += float(exploration.hazardous_route) + exploration.slow_path_cells * 0.1

    resource_expenditure = _resource_expenditure(row)
    action_opportunity_cost = _action_opportunity_cost(row)
    concentration_lost = float(
        row is not None
        and context.facts.actor.is_concentrating
        and ActionTag.CONCENTRATION_START in proposal.semantic_tags
    )
    if row is not None:
        risk += _row_route_risk(row)

    return TacticalValueVector(
        expected_enemy_hp_loss=enemy_hp_loss,
        enemy_defeat_probability=enemy_defeats,
        expected_ally_hp_preserved=ally_hp_preserved,
        expected_enemy_actions_denied=enemy_actions_denied,
        expected_actor_actions_preserved=actor_actions_preserved,
        information_gain=information_gain,
        positional_value=positional_value,
        resource_expenditure=resource_expenditure,
        action_opportunity_cost=action_opportunity_cost,
        concentration_value_lost=concentration_lost,
        friendly_harm=friendly_harm,
        risk=risk,
    )


def _proposal_row_and_semantics(
    context: PolicyContext,
    proposal: PolicyProposal,
) -> tuple[Optional[ActionAffordance], Optional[ActionSemantics]]:
    """Resolve the authoritative row and typed contract for an execute proposal."""
    if not isinstance(proposal.intent, ExecuteIntent):
        return None, None
    row = context.facts.affordances.by_id.get(proposal.intent.row_id)
    semantics = context.facts.affordances.semantics_by_row_id.get(proposal.intent.row_id)
    return row, semantics


def _semantic_success_probability(
    semantics: Optional[ActionSemantics],
    profile: PolicyValueProfile,
) -> float:
    """Return disclosed probability or the generation's explicit uncertainty prior."""
    if semantics is None:
        return profile.undisclosed_outcome_prior
    probabilities = tuple(
        effect.probability
        for effect in semantics.stochastic_effects
        if effect.probability is not None
    )
    if probabilities:
        return sum(probabilities) / len(probabilities)
    outcome_kinds = {effect.outcome_kind for effect in semantics.target_effects}
    if not outcome_kinds or outcome_kinds == {OutcomeKind.GUARANTEED}:
        return 1.0
    return profile.undisclosed_outcome_prior


def _defensive_survival_value(context: PolicyContext) -> float:
    """Estimate defense only from disclosed adjacency, visibility, and actor HP."""
    visible_count = len(context.facts.contacts.visible_hostile_uuids)
    adjacent_count = len(context.facts.threat.adjacent_hostile_uuids)
    actor_hp = context.facts.actor.normal_hp
    if actor_hp is None:
        actor_hp = context.facts.actor.hp
    max_hp = context.facts.actor.max_hp
    missing_fraction = (
        max(0.0, min(1.0, 1.0 - actor_hp / max_hp))
        if actor_hp is not None and max_hp not in (None, 0)
        else 0.0
    )
    disclosed_pressure = adjacent_count + max(0, visible_count - adjacent_count) * 0.15
    return disclosed_pressure * (0.35 + 0.65 * missing_fraction)


def _resource_expenditure(row: Optional[ActionAffordance]) -> float:
    """Return finite-resource units consumed by a row."""
    if row is None:
        return 0.0
    return float(
        (row.cost.spell_slot_cost or 0)
        + sum(row.cost.resource_costs.values())
        + 1.5 * sum(row.cost.item_charge_costs.values())
    )


def _action_opportunity_cost(row: Optional[ActionAffordance]) -> float:
    """Return flexible action-economy units consumed by a row."""
    if row is None:
        return 0.0
    return float(
        row.cost.action_cost
        + row.cost.bonus_action_cost * 0.7
        + row.cost.reaction_cost * 0.5
        + int(row.cost.consumes_attack_slot) * 0.35
    )


def _row_route_risk(row: ActionAffordance) -> float:
    """Return known movement risk carried by one executable row."""
    risk = 0.0
    for target in row.targets:
        risk += float(target.is_path_hazardous and not target.safe_path)
        exposures = (
            target.safe_path_opportunity_attack_exposures
            if target.safe_path
            else target.opportunity_attack_exposures
        )
        risk += 0.65 * len(exposures)
    return risk
