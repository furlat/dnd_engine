"""Ordinary finite-charge use that teaches a scroll's authored base spell."""

from typing import Optional

from dnd.characters.spellbook import learn_scroll_spell, scroll_learning_error
from dnd.core.action_types import ActionSelection
from dnd.core.base_actions import BaseAction, ActionEvent, TargetType, Cost
from dnd.entity import Entity
from dnd.core.events import EventPhase
from dnd.types.discovery import ActorScan


class LearnSpellFromScroll(BaseAction):
    name: str = "Learn Spell"
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = []
    learned_spell_id: str

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> Optional[str]:
        actor = Entity.get(self.source_entity_uuid)
        return (
            scroll_learning_error(actor, self.learned_spell_id)
            if actor is not None
            else "Wizard is missing"
        )

    def _commit_item_charge(self, execution_event, prepared):
        actor = Entity.get(self.source_entity_uuid)
        error = (
            scroll_learning_error(actor, self.learned_spell_id)
            if actor is not None
            else "Wizard is missing"
        )
        if error:
            return execution_event.cancel(status_message=error)
        return super()._commit_item_charge(execution_event, prepared)

    def _apply(self, event: ActionEvent):
        # Native finite-charge commitment can retire the last scroll before here.
        actor = Entity.get(self.source_entity_uuid)
        effect = event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        learn_scroll_spell(actor, self.learned_spell_id, effect)
        return effect
