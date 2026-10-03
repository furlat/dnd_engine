"""Three authored summon spells using native costs, selection and event dispatch."""

from typing import cast

from pydantic import Field

from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.core.base_actions import BaseAction, Cost, PositionDiscoveryContract, TargetType
from dnd.core.events import EventPhase, EventQueue, Range, RangeType, SummonAdmissionEvent
from dnd.entity import Entity
from dnd.summoning.forms import available_forms, selected_form
from dnd.types.summoning import SummonApplication, SummonFamily, SummonSelection


class SummonSpell(SpellAction):
    """One creature/position choice; the explicit world binding owns creation."""

    family: SummonFamily
    form_id: str | None = None
    spell_school: str = "conjuration"
    concentration: bool = True
    target_type: TargetType = TargetType.POSITION
    position_discovery: PositionDiscoveryContract = Field(default_factory=lambda:
        PositionDiscoveryContract(requires_subjective_walkable=True,
                                  requires_subjective_unoccupied=True))
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Summon",
        cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def selection(self) -> SummonSelection:
        if self.form_id is None or self.end_position is None:
            raise ValueError("Choose a creature and one destination")
        choice = SummonSelection(family=self.family, form_id=self.form_id,
            cast_at_level=self.cast_at_level, target_position=self.end_position)
        selected_form(choice)
        return choice

    def admission(self, *, subjective: bool) -> SummonAdmissionEvent:
        return EventQueue.preflight(SummonAdmissionEvent(source_entity_uuid=self.source_entity_uuid,
            selection=self.selection(), subjective=subjective))

    def position_placement_error(self, *, subjective: bool = False) -> str | None:
        try:
            proposal = self.admission(subjective=subjective)
        except ValueError as error:
            return str(error)
        if proposal.canceled:
            return proposal.status_message or "Summon destination is unavailable"
        if proposal.binding_uuid is None:
            return "Summoning is not bound to this encounter"
        return None

    def get_discovery_variants(self, entity: Entity) -> list[BaseAction]:
        return [slot.model_copy(update={"form_id": form.form_id})
            for slot in super().get_discovery_variants(entity)
            for form in available_forms(self.family, cast(SpellAction, slot).cast_at_level)]

    def get_discovery_template_name(self) -> str:
        return f"{super().get_discovery_template_name()}__summon_{self.form_id or 'choose'}"

    def get_discovery_display_name(self) -> str:
        form = next((form for form in available_forms(self.family, self.cast_at_level)
                     if form.form_id == self.form_id), None)
        return f"{super().get_discovery_display_name()} · {form.display_name if form else 'choose creature'}"

    def _apply(self, execution_event: SpellEvent) -> SpellEvent:
        admission = self.admission(subjective=False)
        if admission.canceled or admission.binding_uuid is None:
            return execution_event.cancel(status_message=admission.status_message or "Summon binding unavailable")
        application = SummonApplication(selection=admission.selection,
            binding_uuid=admission.binding_uuid, action_uuid=self.uuid)
        # A detached executable variant is addressable only during this native
        # effect dispatch. The retained record contains data, never the callable.
        temporary_registration = not self.use_register
        if temporary_registration:
            self.add_to_register()
        try:
            effect = execution_event.phase_to(EventPhase.EFFECT, summon_application=application,
                                             target_position=admission.selection.target_position)
            if effect.canceled:
                return effect
            # Ordinary effect vetoes finish before the explicitly bound owner
            # can commit a birth. Empty-trigger handlers support direct dispatch
            # through the existing native handler registry.
            return EventQueue.invoke_admitted_system_effect(application.binding_uuid, effect)
        finally:
            if temporary_registration:
                self.remove_from_register()


class ConjureAnimals(SummonSpell):
    name: str = "Conjure Animals"
    description: str = "Summon one beast. Higher slots unlock stronger available creatures."
    family: SummonFamily = SummonFamily.ANIMALS
    spell_level: int = 3


class ConjureFey(SummonSpell):
    name: str = "Conjure Fey"
    description: str = "Summon a beast-shaped Fey spirit. Losing concentration makes it hostile."
    family: SummonFamily = SummonFamily.FEY
    spell_level: int = 6


class ConjureFiend(SummonSpell):
    name: str = "Conjure Fiend"
    description: str = "Summon one fiend while concentration holds. Higher slots unlock stronger forms."
    family: SummonFamily = SummonFamily.FIEND
    spell_level: int = 3
