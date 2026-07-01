"""Utility-scoring primitives for tactical agents."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ai.models import ActionOption, TacticalState, TargetOption, action_ev


class ScoredOption(BaseModel):
    """One ranked action-target candidate."""

    action: ActionOption = Field(
        description="Action row being evaluated.",
    )
    target: Optional[TargetOption] = Field(
        default=None,
        description="Target row for the action, when the action uses one.",
    )
    score: float = Field(
        default=0.0,
        description="Total weighted utility score.",
    )
    breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Weighted contribution from each scorer keyed by scorer name.",
    )


class UtilityScorer(ABC):
    """Base class for one tactical utility scoring component."""

    def __init__(self, name: str, weight: float = 1.0):
        self.name = name
        self.weight = weight

    @abstractmethod
    def score(
        self,
        state: TacticalState,
        action: ActionOption,
        target: Optional[TargetOption],
    ) -> float:
        """Return an unweighted utility score for an action-target pair.

        Args:
            state: Current tactical snapshot.
            action: Candidate action row.
            target: Candidate target row, or `None` for targetless actions.

        Returns:
            Raw utility score before this scorer's weight is applied.
        """
        raise NotImplementedError


class DamageScorer(UtilityScorer):
    """Score candidates by expected damage pressure."""

    def __init__(self, weight: float = 1.0):
        super().__init__("damage", weight)

    def score(
        self,
        state: TacticalState,
        action: ActionOption,
        target: Optional[TargetOption],
    ) -> float:
        """Return the action's tactical expected-damage estimate."""
        if target is None:
            return 0.0
        return action_ev(action, target)


class FocusFireScorer(UtilityScorer):
    """Reward action rows that target the weakest visible enemy."""

    def __init__(self, weight: float = 0.5):
        super().__init__("focus_fire", weight)

    def score(
        self,
        state: TacticalState,
        action: ActionOption,
        target: Optional[TargetOption],
    ) -> float:
        """Return a bonus when the target is the lowest-HP enemy."""
        if target is None or target.target_uuid is None:
            return 0.0
        weakest = state.weakest_enemy()
        if weakest and target.target_uuid == weakest.uuid:
            return 10.0
        return 0.0


class ThreatAvoidanceScorer(UtilityScorer):
    """Penalize movement options that cross known hazardous paths."""

    def __init__(self, weight: float = 0.3):
        super().__init__("threat_avoidance", weight)

    def score(
        self,
        state: TacticalState,
        action: ActionOption,
        target: Optional[TargetOption],
    ) -> float:
        """Return a movement-path penalty for hazardous target rows."""
        if action.category != "movement" or target is None:
            return 0.0
        if target.is_path_hazardous:
            return -20.0
        return 0.0


class SelfPreservationScorer(UtilityScorer):
    """Reward defensive self-actions when the actor is low on health."""

    def __init__(self, hp_threshold: float = 0.3, weight: float = 1.0):
        super().__init__("self_preservation", weight)
        self.hp_threshold = hp_threshold

    def score(
        self,
        state: TacticalState,
        action: ActionOption,
        target: Optional[TargetOption],
    ) -> float:
        """Return a defensive-action bonus when the actor is vulnerable."""
        if state.me.hp_fraction > self.hp_threshold:
            return 0.0
        if "dodge" in action.display_name.lower():
            return 15.0
        if "disengage" in action.display_name.lower() and state.is_threatened:
            return 20.0
        return 0.0


class AoEScorer(UtilityScorer):
    """Reward area options by the number of affected entities."""

    def __init__(self, weight: float = 1.0):
        super().__init__("aoe", weight)

    def score(
        self,
        state: TacticalState,
        action: ActionOption,
        target: Optional[TargetOption],
    ) -> float:
        """Return a target-count score for area candidates."""
        if target is None or target.aoe_affected_count is None:
            return 0.0
        return target.aoe_affected_count * 5.0


class UtilityAI:
    """Evaluate affordable action-target pairs with weighted scorers."""

    def __init__(self, scorers: List[UtilityScorer]):
        self.scorers = scorers

    def evaluate_all(self, state: TacticalState) -> List[ScoredOption]:
        """Score every affordable action-target candidate.

        Args:
            state: Current tactical snapshot.

        Returns:
            Candidates sorted by descending total score.
        """
        options: List[ScoredOption] = []
        all_actions = (
            state.attacks
            + state.spells
            + state.self_actions
            + state.movements
        )

        for action in all_actions:
            if not action.can_afford:
                continue
            targets: List[Optional[TargetOption]] = (
                list(action.targets) if action.targets else [None]
            )
            for target in targets:
                breakdown: Dict[str, float] = {}
                total = 0.0
                for scorer in self.scorers:
                    score = scorer.score(state, action, target) * scorer.weight
                    breakdown[scorer.name] = score
                    total += score
                options.append(
                    ScoredOption(
                        action=action,
                        target=target,
                        score=total,
                        breakdown=breakdown,
                    )
                )

        return sorted(options, key=lambda option: -option.score)

    def pick_best(self, state: TacticalState) -> Optional[ScoredOption]:
        """Return the highest-scoring candidate, if one exists."""
        ranked = self.evaluate_all(state)
        return ranked[0] if ranked else None
