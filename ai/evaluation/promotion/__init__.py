"""Versioned AI promotion experiments over generic combat rosters."""

from ai.evaluation.promotion.contracts import (
    MatchupFamily,
    PromotionMatchupSpec,
    PromotionObservation,
    PromotionOutcome,
    PromotionPanel,
    PromotionSchedule,
    PromotionScheduleEntry,
)
from ai.evaluation.promotion.model import fit_policy_promotion
from ai.evaluation.promotion.catalog import (
    build_default_promotion_matchups,
    build_symmetric_promotion_deployments,
)
from ai.evaluation.promotion.schedule import build_promotion_schedule

__all__ = [
    "MatchupFamily",
    "PromotionMatchupSpec",
    "PromotionObservation",
    "PromotionOutcome",
    "PromotionPanel",
    "PromotionSchedule",
    "PromotionScheduleEntry",
    "build_promotion_schedule",
    "build_default_promotion_matchups",
    "build_symmetric_promotion_deployments",
    "fit_policy_promotion",
]
