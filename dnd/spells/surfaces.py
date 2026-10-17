"""Small authored acid/toxin surfaces composed from native area memberships."""
from typing import Tuple, TypedDict
from dnd.core.aoe import AoEShape, Sphere
from dnd.core.effect_types import EffectOrigin
from uuid import UUID

from pydantic import Field

from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, SpatialChangeEvent, Event, EventHandler, EventPhase, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from dnd.core.saving_throw_types import SavingThrowEffectTag
from dnd.core.values import ModifiableValue, Channel, Kind, add_modifier
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.environmental_conditions import IceSurface, FireSurface, ElectrifiedWater, DRY_TRANSITION
from dnd.spatial.transitions import bind_spatial_interactions
from dnd.spatial.ignition import apply_elemental_surface_contacts
from dnd.spatial.memberships import MembershipAreaCondition, SpatialConditionMembershipSource
from dnd.spells.content_metadata import srd_condition_identity
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy, SpatialEffectTriggerKind


class AcidSurfacePenalty(BaseCondition):
    name: str = "Acid Surface"
    description: str = "Armor Class is reduced by two while at least one acid patch remains."
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Acid recipient is absent")
        value=target.equipment.ac_bonus
        identity=add_modifier(value, Channel.SELF_STATIC, Kind.VALUE, NumericalModifier(name="Acid Surface",value=-2,
            source_entity_uuid=target.uuid,target_entity_uuid=self.source_entity_uuid))
        return [(value.uuid,identity)],[],[],[],event.phase_to(EventPhase.EFFECT)


class AcidSurfaceMembership(SpatialConditionMembershipSource):
    creates = (AcidSurfacePenalty,)
    name: str = "Acid Surface Membership"
    description: str = "One exact acid-patch lease for the shared AC penalty."

    def create_manifestation(self,target: Entity) -> BaseCondition:
        return AcidSurfacePenalty(source_entity_uuid=self.source_entity_uuid,target_entity_uuid=target.uuid)

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Acid recipient is absent")
        child=next((condition for condition in target.active_conditions_by_uuid.values()
            if isinstance(condition,AcidSurfacePenalty)),None)
        if child is None:
            child=self.create_manifestation(target)
            child.parent_condition=self.uuid
            admitted=target.add_condition(child,parent_event=event)
            if admitted is None or admitted.canceled or not child.applied:
                return [],[],[],[],event.cancel(status_message="Acid penalty was rejected")
        self.add_shared_subcondition(child)
        return [],[],[],[],event.phase_to(EventPhase.EFFECT)


@srd_condition_identity(content_id="spatial_effect.spell.acid_surface",display_name="Spell Acid Surface",
    description="Two-turn acid patch: nonstacking -2 Armor Class while inside.")
class SpellAcidSurface(MembershipAreaCondition):
    creates = (AcidSurfaceMembership,)
    name: str = "Spell Acid Surface"
    description: str = "Two-turn acid patch: nonstacking -2 Armor Class while inside."
    layer: SpatialEffectLayer = SpatialEffectLayer.GROUND_SURFACE
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    area: AoEShape = Sphere(radius_feet=7)
    has_visible_presence: bool = True
    duration: Duration = Field(default_factory=lambda:Duration(duration=2,duration_type=DurationType.ROUNDS))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.APPEAR,SpatialEffectTriggerKind.ENTER})
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.APPEAR,SpatialEffectTriggerKind.ENTER,SpatialEffectTriggerKind.LEAVE})

    def membership_source_class(self):
        return AcidSurfaceMembership


class SimpleToxinExposure(BaseCondition):
    name: str = "Simple Toxin"
    description: str = "One delayed 1d4 poison tick at the next turn end."
    duration: Duration = Field(default_factory=lambda:Duration(duration=None,duration_type=DurationType.PERMANENT))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL,ConditionTag.POISON})

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        self.name=f"Simple Toxin:{self.source_entity_uuid}"

    def get_display_name(self) -> str:
        return "Simple Toxin"

    def _apply(self,event: Event):
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [],[],[],[],event.cancel(status_message="Toxin recipient is absent")
        def tick(boundary: Event,_: UUID):
            if self.contributions_active():
                damage=Damage(name="Simple Toxin",source_entity_uuid=self.source_entity_uuid,target_entity_uuid=target.uuid,
                    damage_dice=4,dice_numbers=1,damage_type=DamageType.POISON,effect_origin=self.effect_origin,
                    damage_bonus=ModifiableValue.create(source_entity_uuid=self.source_entity_uuid,base_value=0))
                roll=damage.get_dice(AttackOutcome.HIT).roll
                target.receive_damage(roll.total,DamageType.POISON,self.source_entity_uuid,parent_event=boundary.uuid,
                    damages=[damage],damage_rolls=[roll],effect_origin=self.effect_origin,
                    independent_resolution=True,source_condition_uuid=self.uuid)
            target.remove_condition_by_uuid(self.uuid,parent_event=boundary)
            return None
        handler=EventHandler(name="Simple Toxin delayed damage",source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.TURN_END,event_phase=EventPhase.EFFECT,event_source_entity_uuid=target.uuid)],event_processor=tick)
        target.add_event_handler(handler)
        return [],[handler.uuid],[],[],event.phase_to(EventPhase.EFFECT)


@srd_condition_identity(content_id="spatial_effect.spell.simple_toxin",display_name="Simple Toxin Surface",
    description="Two-turn toxin patch: CON admission, then one delayed 1d4 poison tick.")
class SimpleToxinSurface(AreaCondition):
    creates = (SimpleToxinExposure,)
    name: str = "Simple Toxin Surface"
    description: str = "Two-turn toxin patch: CON admission, then one delayed 1d4 poison tick."
    layer: SpatialEffectLayer = SpatialEffectLayer.GROUND_SURFACE
    occupancy_policy: SpatialEffectOccupancyPolicy = SpatialEffectOccupancyPolicy.OVERLAPPING
    area: AoEShape = Sphere(radius_feet=7)
    has_visible_presence: bool = True
    spell_dc: int
    duration: Duration = Field(default_factory=lambda:Duration(duration=2,duration_type=DurationType.ROUNDS))
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset({SpatialEffectTriggerKind.APPEAR,SpatialEffectTriggerKind.ENTER})
    first_per_turn_trigger_kinds: frozenset[SpatialEffectTriggerKind] = trigger_kinds

    def _apply(self, event: Event):
        modifiers, handlers, children, spatial, effect = super()._apply(event)
        if effect is not None and not effect.canceled:
            handler = bind_spatial_interactions(condition=self, transitions=(DRY_TRANSITION,))
            spatial.append(handler.uuid)
        return modifiers, handlers, children, spatial, effect

    def expose(self,target: Entity,event: Event) -> None:
        caster=Entity.get(self.source_entity_uuid)
        if caster is None:
            return
        request=caster.create_saving_throw_request(target.uuid,"constitution",self.spell_dc,parent_event=event.uuid,
            saving_throw_context=self.saving_throw_context(effect_id="spell.simple_toxin.admission",effect_tags=(SavingThrowEffectTag.POISON,)))
        if not target.saving_throw(request)[2]:
            target.add_condition(SimpleToxinExposure(source_entity_uuid=caster.uuid,target_entity_uuid=target.uuid,
                effect_origin=self.effect_origin),parent_event=event)

    def _apply_appearance_effect(self,entity: Entity,*,parent_event: Event) -> None:
        self.expose(entity,parent_event)

    def _create_zone_entry_handler(self) -> EventHandler:
        def enter(event: Event,_: UUID):
            target=Entity.get(event.entity_uuid) if isinstance(event,SpatialChangeEvent) and event.entity_uuid else None
            if target is not None:
                self.expose(target,event)
            return None
        return EventHandler(name="Simple Toxin Entry",source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(event_type=EventType.SPATIAL_ENTITY_ENTERED,event_phase=EventPhase.EFFECT)],event_processor=enter)


class SurfaceParameters(TypedDict):
    source_entity_uuid: UUID
    position: Tuple[int,int]
    area: AoEShape
    duration: Duration


def place_spell_surface(element: str,*,source_uuid: UUID,position: Tuple[int,int],
                        parent_event: Event,spell_dc: int,origin: EffectOrigin | None) -> AreaCondition | None:
    """Choose one authored patch; elemental transitions stay with native surfaces."""
    if element=="thunder":
        return None
    kwargs: SurfaceParameters={"source_entity_uuid":source_uuid,"position":position,"area":Sphere(radius_feet=7),
        "duration":Duration(duration=2,duration_type=DurationType.ROUNDS)}
    if element=="acid":
        surface=SpellAcidSurface(**kwargs,effect_origin=origin,content_ref=get_content_declaration(SpellAcidSurface).ref)
    elif element=="poison":
        surface=SimpleToxinSurface(**kwargs,effect_origin=origin,spell_dc=spell_dc,content_ref=get_content_declaration(SimpleToxinSurface).ref)
    else:
        surface_type={"cold":IceSurface,"fire":FireSurface,"lightning":ElectrifiedWater}[element]
        surface=surface_type(**kwargs,effect_origin=origin)
    surface.activate(parent_event=parent_event)
    if element in ("fire","cold","lightning") and surface.applied:
        apply_elemental_surface_contacts(parent_event,surface.affected_positions,DamageType[element.upper()])
    return surface
