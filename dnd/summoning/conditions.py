"""Temporary existence and Fey control on an otherwise ordinary creature."""

from uuid import UUID
from typing import Literal

from pydantic import Field

from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import (
    ConditionCategory, ConditionTag, DurationType,
    InvoluntarySustainLoss, SustainLossPolicy,
)
from dnd.types.summoning import SummonDepartureCause, SummonOrigin, TerminalOwnerRelease


class Summoned(BaseCondition):
    name: str = "Summoned"
    description: str = "Temporary creature existence, independent of its native abilities."
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    sustain_loss_policy: SustainLossPolicy = SustainLossPolicy.REQUIRED
    child_removal_policy: Literal["none", "any", "last"] = "none"
    origin: SummonOrigin
    last_progressed_interval: tuple[UUID, int] | None = None
    duration: Duration = Field(default_factory=lambda: Duration(
        duration=600, duration_type=DurationType.ROUNDS))

    def snapshot_summon_origin(self) -> SummonOrigin:
        return self.origin

    def terminal_release(self, cause: SummonDepartureCause,
                         parent_event_uuid: UUID | None = None) -> TerminalOwnerRelease:
        if self.target_entity_uuid is None:
            raise ValueError("Summoned existence requires a creature owner")
        return TerminalOwnerRelease(entity_uuid=self.target_entity_uuid,
            existence_condition_uuid=self.uuid, cause=cause,
            parent_event_uuid=parent_event_uuid)

    def terminal_release_for_expiration(self) -> TerminalOwnerRelease:
        return self.terminal_release(SummonDepartureCause.EXPIRED)

    def terminal_release_for_sustain_loss(self, loss: InvoluntarySustainLoss) -> TerminalOwnerRelease:
        return self.terminal_release(SummonDepartureCause.SUSTAIN_LOST, loss.parent_event_uuid)

    def progress_for_interval(self, interval: tuple[UUID, int] | None) -> bool:
        if interval is None or interval == self.last_progressed_interval:
            return self.duration.is_expired
        self.last_progressed_interval = interval
        return self.duration.progress()

class SummonControl(BaseCondition):
    name: str = "Summon Control"
    description: str = "Concentration sustains allegiance without sustaining existence."
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    sustain_loss_policy: SustainLossPolicy = SustainLossPolicy.REQUIRED
    original_controller_uuid: UUID

