"""Ordinary action for ending one's still-controlled temporary creature."""

from pydantic import Field

from dnd.actions import entity_action_economy_cost_applier, entity_action_economy_cost_evaluator
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.events import EventPhase
from dnd.entity import Entity
from dnd.summoning.conditions import SummonControl, Summoned
from dnd.types.summoning import SummonDepartureCause


class DismissSummon(BaseAction):
    name: str = "Dismiss Summon"
    description: str = "Use one action to dismiss a temporary creature you still control."
    target_type: TargetType = TargetType.ENTITY
    valid_target_filter: str = "all"
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Dismiss Summon",
        cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def _existence(self) -> Summoned | None:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None or not target.is_deployed or not target.has_runtime_agency():
            return None
        existence = target.active_conditions.get("Summoned")
        if not isinstance(existence, Summoned) or existence.origin.summoner_uuid != self.source_entity_uuid:
            return None
        control_uuid = existence.origin.control_condition_uuid
        if control_uuid is not None:
            control = target.active_conditions_by_uuid.get(control_uuid)
            if not isinstance(control, SummonControl) or not control.applied:
                return None
        return existence

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        if self._existence() is None:
            return declaration_event.cancel(status_message="This creature is not your controlled summon")
        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        existence = self._existence()
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if existence is None or target is None:
            return execution_event.cancel(status_message="Summon control has ended")
        release = existence.terminal_release(SummonDepartureCause.DISMISSED, execution_event.uuid)
        if not target.remove_condition_by_uuid(existence.uuid, parent_event=execution_event, terminal_release=release):
            return execution_event.cancel(status_message="Summon dismissal was rejected")
        return execution_event.phase_to(EventPhase.EFFECT)

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(execution_event, self.source_entity_uuid)
