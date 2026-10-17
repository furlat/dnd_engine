"""Three authored summon spells using native costs, selection and event dispatch."""

from typing import Optional, Tuple, cast

from pydantic import Field

from dnd.actions import SpellAction, SpellEvent, entity_action_economy_cost_evaluator
from dnd.core.action_types import ActionSelection, ActionVariantFacet, selection_facet
from dnd.core.creature_types import DamageType
from dnd.core.base_actions import Cost, PositionDiscoveryContract, TargetType
from dnd.core.events import EventPhase, EventQueue, Range, RangeType, SummonAdmissionEvent
from dnd.summoning.forms import available_forms, selected_form
from dnd.types.discovery import ActorScan, ScanRecord
from dnd.types.summoning import SummonApplication, SummonFamily, SummonSelection


class SummonSpell(SpellAction):
    """One creature/position choice; the explicit world binding owns creation."""

    family: SummonFamily
    form_id: str | None = None
    breath_type: DamageType = DamageType.FIRE
    shared_resistance: DamageType = DamageType.FIRE
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
            cast_at_level=self.cast_at_level, target_position=self.end_position,breath_type=self.breath_type,shared_resistance=self.shared_resistance)
        selected_form(choice)
        return choice

    def admission(self, *, subjective: bool) -> SummonAdmissionEvent:
        return EventQueue.preflight(SummonAdmissionEvent(source_entity_uuid=self.source_entity_uuid,
            selection=self.selection(), subjective=subjective))

    def handler_admission_error(self, *, subjective: bool) -> str | None:
        try:
            proposal = self.admission(subjective=subjective)
        except ValueError as error:
            return str(error)
        if proposal.canceled:
            return proposal.status_message or "Summon destination is unavailable"
        if proposal.binding_uuid is None:
            return "Summoning is not bound to this encounter"
        return None

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        """One choice per creature form open at the cast level."""
        return tuple((ActionVariantFacet(key="form", value=form.form_id, label=form.display_name),)
                     for form in available_forms(self.family, level if level is not None else self.cast_at_level))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "form_id": selection_facet(selection, "form")}

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


class SpiritualWeapon(SummonSpell):
    name: str = "Spiritual Weapon"
    description: str = "Summon a ten-turn autonomous allied spectral weapon; bonus action, no concentration."
    family: SummonFamily = SummonFamily.SPIRITUAL_WEAPON
    form_id: str | None = "spiritual_weapon"
    spell_level: int = 2
    spell_school: str = "evocation"
    concentration: bool = False
    alt_cost_type: str | None = "bonus_actions"


class FlamingSphere(SummonSpell):
    name: str = "Flaming Sphere"
    description: str = "Summon a ten-turn autonomous allied sphere with saved Ram, enemy end-turn aura and native fire trail."
    family: SummonFamily = SummonFamily.FLAMING_SPHERE
    form_id: str | None = "flaming_sphere"
    spell_level: int = 2
    concentration: bool = True


class ConjureElemental(SummonSpell):
    name:str="Conjure Elemental"
    description:str="Summon an allied elemental until long rest; slot six unlocks Myrmidons."
    family:SummonFamily=SummonFamily.ELEMENTAL
    spell_level:int=5
    concentration:bool=False

class PlanarAlly(SummonSpell):
    name:str="Planar Ally"
    description:str="Summon an allied Deva, Djinni or Cambion until long rest."
    family:SummonFamily=SummonFamily.PLANAR_ALLY
    spell_level:int=6
    concentration:bool=False

class SummonDragon(SummonSpell):
    name:str="Summon Dragon"
    description:str="Summon a Draconic Spirit with independently chosen Breath and shared resistance."
    family:SummonFamily=SummonFamily.DRAGON
    form_id:str|None="draconic_spirit"
    spell_level:int=5
    def selection(self):
        choice=super().selection()
        elements=(DamageType.ACID,DamageType.COLD,DamageType.FIRE,DamageType.LIGHTNING,DamageType.POISON)
        if choice.breath_type not in elements or choice.shared_resistance not in elements:raise ValueError("Choose one of the five elemental types")
        return choice
    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        """Each form, with an independently chosen Breath and shared resistance."""
        elements=(DamageType.ACID,DamageType.COLD,DamageType.FIRE,DamageType.LIGHTNING,DamageType.POISON)
        return tuple((*form, ActionVariantFacet(key="damage_type", value=breath.value, label=breath.value+" Breath"),
                      ActionVariantFacet(key="resistance", value=shared.value, label=shared.value+" shared resistance"))
                     for form in super().facet_domain(scan, level, target) for breath in elements for shared in elements)
    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "breath_type": DamageType(selection_facet(selection, "damage_type")),
                "shared_resistance": DamageType(selection_facet(selection, "resistance"))}
