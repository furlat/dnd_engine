"""Ordinary finite-charge use that teaches a scroll's authored base spell."""

from dnd.characters.spellbook import learn_scroll_spell, scroll_learning_error
from dnd.core.base_actions import BaseAction, ActionEvent, TargetType, Cost
from dnd.entity import Entity
from dnd.core.events import EventPhase


class LearnSpellFromScroll(BaseAction):
    name: str = "Learn Spell"
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = []
    learned_spell_id: str

    def _validate(self, event: ActionEvent):
        actor = Entity.get(self.source_entity_uuid)
        error = (
            scroll_learning_error(actor, self.learned_spell_id)
            if actor is not None
            else "Wizard is missing"
        )
        return event.cancel(status_message=error) if error else super()._validate(event)

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
