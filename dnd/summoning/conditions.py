"""Temporary existence and Fey control on an otherwise ordinary creature."""

from uuid import UUID
from typing import Literal

from pydantic import Field

from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import (
    ConditionCategory, ConditionTag, DurationType,
    InvoluntarySustainLoss, SustainLossPolicy,
)
from dnd.core.events import EventHandler, EventType, EventPhase, Trigger
from dnd.core.base_block import BaseBlock
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



class SpiritualWeaponOwner(BaseCondition):
    name: str = "Spiritual Weapon Owner"
    description: str = "Owns one independent spiritual weapon per caster without concentration."
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    child_removal_policy: Literal["none","any","last"] = "any"
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    duration: Duration = Field(default_factory=lambda:Duration(duration_type=DurationType.PERMANENT))


class IndependentSummonOwner(SpiritualWeaponOwner):
    name:str="Independent Summon Owner"
    family: str
    duration:Duration=Field(default_factory=lambda:Duration(duration_type=DurationType.UNTIL_LONG_REST))
    def model_post_init(self,context):
        super().model_post_init(context)
        self.name=f"Summon Owner:{self.family}"
    def _apply(self,event):
        owner=BaseBlock.get(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if owner is None:return [],[],[],[],event.cancel(status_message="Summon owner absent")
        def ending(boundary,_):
            owner.remove_condition_by_uuid(self.uuid,parent_event=boundary)
            return None
        handler=EventHandler(name="Independent summon caster death",source_entity_uuid=self.source_entity_uuid,
            runs_while_owner_inactive=True,trigger_conditions=[
                Trigger(event_type=EventType.DEATH,event_phase=EventPhase.EFFECT,event_target_entity_uuid=owner.uuid),
                Trigger(event_type=EventType.INSTANT_DEATH,event_phase=EventPhase.EFFECT,event_target_entity_uuid=owner.uuid)],event_processor=ending)
        owner.add_event_handler(handler)
        return [],[handler.uuid],[],[],event.phase_to(EventPhase.EFFECT)
