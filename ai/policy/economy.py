"""Typed action-economy projections and opportunity costs for policy branches."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from server.agent_protocol.control import (
    ActionAffordance,
    ActionCapability,
    ActionCostProfile,
    ActionEconomyState,
)
from server.agent_protocol.semantics import (
    ActionSemantics,
    CapabilityAmountFormula,
    CapabilityAmountSource,
    CapabilityCostOperation,
    CapabilitySelector,
    CapabilityTransformation,
    ActionTag,
    TargetAllocation,
    TargetingSemantics,
)


@dataclass(frozen=True)
class ProjectedCapability:
    """Non-executable projection of one declared capability transformation."""

    capability: ActionCapability
    transformation_id: str
    cost: ActionCostProfile
    targeting: TargetingSemantics


CostValues = tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class _CanonicalCostProfile:
    """Decision-local canonical form of affordability-relevant costs."""

    cache_id: int
    values: CostValues
    movement_cost: int


@dataclass
class AffordabilityWorkspace:
    """Decision-scoped affordability cache over one immutable economy epoch."""

    economy: ActionEconomyState
    pair_evaluations: int = field(default=0, init=False)
    pair_cache_misses: int = field(default=0, init=False)
    _available: dict[str, int] = field(init=False, repr=False)
    _profiles_by_identity: dict[
        int,
        tuple[ActionCostProfile, _CanonicalCostProfile],
    ] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _profiles_by_values: dict[CostValues, _CanonicalCostProfile] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _pair_non_movement_affordable: dict[tuple[int, int], bool] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        """Flatten the authoritative economy exactly once for this decision."""
        self._available = _available_resource_values(self.economy)

    def combined_costs_affordable(
        self,
        first: ActionCostProfile,
        second: ActionCostProfile,
        *,
        first_movement_cost: Optional[int] = None,
        second_movement_cost: Optional[int] = None,
    ) -> bool:
        """Return pair affordability with optional allocation-specific movement."""
        self.pair_evaluations += 1
        first_profile = self._canonical_profile(first)
        second_profile = self._canonical_profile(second)
        pair_key = (first_profile.cache_id, second_profile.cache_id)
        non_movement_affordable = self._pair_non_movement_affordable.get(pair_key)
        if non_movement_affordable is None:
            self.pair_cache_misses += 1
            combined = dict(first_profile.values)
            for resource_id, amount in second_profile.values:
                combined[resource_id] = combined.get(resource_id, 0) + amount
            non_movement_affordable = all(
                resource_id == "action_economy.movement"
                or demand <= self._available.get(resource_id, 0)
                for resource_id, demand in combined.items()
            )
            self._pair_non_movement_affordable[pair_key] = non_movement_affordable
        if not non_movement_affordable:
            return False
        movement_demand = (
            first_profile.movement_cost
            if first_movement_cost is None
            else first_movement_cost
        ) + (
            second_profile.movement_cost
            if second_movement_cost is None
            else second_movement_cost
        )
        return movement_demand <= self._available.get("action_economy.movement", 0)

    def _canonical_profile(self, profile: ActionCostProfile) -> _CanonicalCostProfile:
        """Resolve one profile identity to an equal-value canonical record."""
        identity = id(profile)
        cached = self._profiles_by_identity.get(identity)
        if cached is not None and cached[0] is profile:
            return cached[1]
        values = tuple(sorted(_cost_values(profile).items()))
        canonical = self._profiles_by_values.get(values)
        if canonical is None:
            canonical = _CanonicalCostProfile(
                cache_id=len(self._profiles_by_values),
                values=values,
                movement_cost=profile.movement_cost,
            )
            self._profiles_by_values[values] = canonical
        self._profiles_by_identity[identity] = (profile, canonical)
        return canonical


def project_capability_transformation(
    capability: ActionCapability,
    semantics: ActionSemantics,
    transformation: CapabilityTransformation,
    economy: ActionEconomyState,
) -> Optional[ProjectedCapability]:
    """Project a declared rewrite without manufacturing an executable row.

    Args:
        capability: Actor-owned capability being considered.
        semantics: Typed meaning referenced by that capability.
        transformation: Structural rewrite declared by a legal setup action.
        economy: Current authoritative action-economy snapshot.

    Returns:
        Projected cost and targeting when the selector matches and every amount
        can be evaluated, otherwise None.
    """
    if not capability_matches_selector(capability, semantics, transformation.selector):
        return None

    cost_values = _cost_values(capability.cost)
    for rewrite in transformation.cost_rewrites:
        amount = _evaluate_amount(rewrite.amount, capability, cost_values, rewrite.source_resource_id)
        if amount is None:
            return None
        if rewrite.operation is CapabilityCostOperation.REPLACE:
            if rewrite.source_resource_id is None:
                return None
            cost_values[rewrite.source_resource_id] = 0
        cost_values[rewrite.target_resource_id] = (
            cost_values.get(rewrite.target_resource_id, 0) + amount
        )

    projected_cost = _cost_profile_from_values(capability.cost, cost_values, economy)
    targeting = semantics.targeting
    rewrite = transformation.targeting_rewrite
    if rewrite is not None:
        targeting = targeting.model_copy(update={
            "allocation": rewrite.allocation,
            "minimum_targets": rewrite.minimum_targets,
            "maximum_targets": rewrite.maximum_targets,
            "allows_repeated_targets": (
                targeting.allows_repeated_targets
                if rewrite.allows_repeated_targets is None
                else rewrite.allows_repeated_targets
            ),
        })
    return ProjectedCapability(
        capability=capability,
        transformation_id=transformation.transformation_id,
        cost=projected_cost,
        targeting=targeting,
    )


def capability_matches_selector(
    capability: ActionCapability,
    semantics: ActionSemantics,
    selector: CapabilitySelector,
) -> bool:
    """Return whether one owned capability satisfies a structural selector."""
    return action_shape_matches_selector(
        action_category=capability.action_category,
        target_allocation=semantics.targeting.allocation,
        semantic_tags=semantics.tags,
        positive_cost_resource_ids=positive_cost_resource_ids(capability.cost),
        weapon_slot=capability.weapon_slot,
        selector=selector,
    )


def affordance_matches_selector(
    affordance: ActionAffordance,
    semantics: ActionSemantics,
    selector: CapabilitySelector,
) -> bool:
    """Return whether one authoritative legal row matches a capability selector."""
    return action_shape_matches_selector(
        action_category=affordance.action_category,
        target_allocation=semantics.targeting.allocation,
        semantic_tags=semantics.tags,
        positive_cost_resource_ids=positive_cost_resource_ids(affordance.cost),
        weapon_slot=affordance.weapon_slot,
        selector=selector,
    )


def action_shape_matches_selector(
    *,
    action_category: str,
    target_allocation: TargetAllocation,
    semantic_tags: frozenset[ActionTag],
    positive_cost_resource_ids: frozenset[str],
    weapon_slot: Optional[str] = None,
    selector: CapabilitySelector,
) -> bool:
    """Match a legal row or owned capability against one structural selector."""
    if selector.action_categories and action_category not in selector.action_categories:
        return False
    if selector.target_allocations and target_allocation not in selector.target_allocations:
        return False
    if not selector.required_tags.issubset(semantic_tags):
        return False
    if selector.weapon_slots and weapon_slot not in selector.weapon_slots:
        return False
    return selector.required_cost_resource_ids.issubset(positive_cost_resource_ids)


def positive_cost_resource_ids(cost: ActionCostProfile) -> frozenset[str]:
    """Return stable identifiers for every positive cost in one profile."""
    return frozenset(
        resource_id
        for resource_id, amount in _cost_values(cost).items()
        if amount > 0
    )


def combined_costs_affordable(
    economy: ActionEconomyState,
    first: ActionCostProfile,
    second: ActionCostProfile,
) -> bool:
    """Return whether one economy snapshot can pay two sequential costs."""
    return AffordabilityWorkspace(economy).combined_costs_affordable(first, second)


def capability_is_turn_refreshable(
    economy: ActionEconomyState,
    capability: ActionCapability,
) -> bool:
    """Return whether replenishing per-turn economy would make a capability payable.

    Action, bonus-action, reaction, attack-slot, and movement depletion are turn
    local. Spell slots, named resources, item charges, and non-transient gates
    remain authoritative constraints and are never assumed to replenish.
    """
    if any(
        gate.active and gate.name != "no_meaningful_commands"
        for gate in economy.gates
    ):
        return False
    return not capability_persistent_affordability_reasons(economy, capability)


def capability_persistent_resource_requirements(
    economy: ActionEconomyState,
    capability: ActionCapability,
) -> tuple[tuple[str, int, int], ...]:
    """Return exact non-refreshing costs and disclosed current availability."""
    available = _available_resource_values(economy)
    return tuple(sorted(
        (
            resource_id,
            required,
            available.get(resource_id, 0),
        )
        for resource_id, required in _cost_values(capability.cost).items()
        if required > 0 and not resource_id.startswith("action_economy.")
    ))


def capability_persistent_affordability_reasons(
    economy: ActionEconomyState,
    capability: ActionCapability,
) -> tuple[str, ...]:
    """Return persistent resource identifiers that block future execution."""
    return tuple(
        resource_id
        for resource_id, required, available in capability_persistent_resource_requirements(
            economy,
            capability,
        )
        if required > available
    )


def _evaluate_amount(
    formula: CapabilityAmountFormula,
    capability: ActionCapability,
    cost_values: dict[str, int],
    source_resource_id: Optional[str],
) -> Optional[int]:
    """Evaluate one bounded transformation amount from typed capability data."""
    if formula.source is CapabilityAmountSource.FIXED:
        base = formula.fixed_amount
    elif formula.source is CapabilityAmountSource.SOURCE_RESOURCE:
        base = cost_values.get(source_resource_id or "")
    else:
        base = capability.base_spell_level
    if base is None:
        return None
    return max(formula.minimum, base + formula.offset)


def _cost_values(cost: ActionCostProfile) -> dict[str, int]:
    """Flatten one cost profile into stable semantic resource identifiers."""
    values = {
        "action_economy.actions": cost.action_cost,
        "action_economy.bonus_actions": cost.bonus_action_cost,
        "action_economy.reactions": cost.reaction_cost,
        "action_economy.movement": cost.movement_cost,
    }
    if cost.spell_slot_cost is not None:
        values[f"spell_slot.{cost.spell_slot_cost}"] = 1
    values.update({f"resource.{name}": amount for name, amount in cost.resource_costs.items()})
    values.update({f"item_charge.{item_uuid}": amount for item_uuid, amount in cost.item_charge_costs.items()})
    return values


def _cost_profile_from_values(
    original: ActionCostProfile,
    values: dict[str, int],
    economy: ActionEconomyState,
) -> ActionCostProfile:
    """Rebuild and re-evaluate a transformed cost profile."""
    spell_slots = {
        int(resource_id.removeprefix("spell_slot.")): amount
        for resource_id, amount in values.items()
        if resource_id.startswith("spell_slot.") and amount > 0
    }
    spell_slot_cost = next(iter(spell_slots), None) if len(spell_slots) <= 1 else original.spell_slot_cost
    resource_costs = {
        resource_id.removeprefix("resource."): amount
        for resource_id, amount in values.items()
        if resource_id.startswith("resource.") and amount > 0
    }
    item_charge_costs = {
        resource_id.removeprefix("item_charge."): amount
        for resource_id, amount in values.items()
        if resource_id.startswith("item_charge.") and amount > 0
    }
    reasons = _affordability_reasons(values, economy)
    return ActionCostProfile(
        action_cost=values.get("action_economy.actions", 0),
        bonus_action_cost=values.get("action_economy.bonus_actions", 0),
        reaction_cost=values.get("action_economy.reactions", 0),
        movement_cost=values.get("action_economy.movement", 0),
        consumes_attack_slot=original.consumes_attack_slot,
        spell_slot_cost=spell_slot_cost,
        resource_costs=resource_costs,
        item_charge_costs=item_charge_costs,
        affordability="affordable" if not reasons else "unaffordable",
        affordability_reasons=reasons,
    )


def _affordability_reasons(
    values: dict[str, int],
    economy: ActionEconomyState,
) -> tuple[str, ...]:
    """Return stable resource identifiers whose current pools cannot pay costs."""
    available = _available_resource_values(economy)
    return tuple(sorted(
        resource_id
        for resource_id, demand in values.items()
        if demand > available.get(resource_id, 0)
    ))


def _available_resource_values(economy: ActionEconomyState) -> dict[str, int]:
    """Flatten disclosed current economy into stable resource identifiers."""
    return {
        "action_economy.actions": economy.actions,
        "action_economy.bonus_actions": economy.bonus_actions,
        "action_economy.reactions": economy.reactions,
        "action_economy.movement": economy.movement_remaining,
        **{f"spell_slot.{level}": pool.current for level, pool in economy.spell_slots.items()},
        **{f"resource.{name}": pool.current for name, pool in economy.resources.items()},
        **{f"item_charge.{item_uuid}": pool.current for item_uuid, pool in economy.item_charges.items()},
    }


def action_economy_opportunity_cost(cost: ActionCostProfile) -> float:
    """Return normalized flexibility consumed by one legal command.

    A full action satisfies a broader future affordance set than a bonus action,
    reaction, or granted attack slot. The normalized values let utility and
    routine tie-breaking preserve flexible economy without inspecting action
    names or controller-specific row identifiers.

    Args:
        cost: Typed server-issued cost profile for one affordance.

    Returns:
        Non-negative opportunity cost in normalized action units.
    """
    return (
        float(cost.action_cost)
        + 0.75 * float(cost.bonus_action_cost)
        + 0.75 * float(cost.reaction_cost)
        + 0.25 * float(cost.consumes_attack_slot)
    )
