"""Native attack components and caster-owned quarry state for Mark and Hex."""
from typing import Callable, ClassVar, Literal, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import Field, PrivateAttr

from dnd.actions import Attack, AttackEvent, SpellAction, SpellEvent, create_weapon_attack_declaration_event, entity_action_economy_cost_evaluator, entity_action_economy_cost_applier, grant_weapon_attack_batch, weapon_attack_error
from dnd.conditions import ConcentrationActionMarker
from dnd.core.action_types import ActionSelection, ActionVariantFacet, selection_facet
from dnd.core.base_block import BaseBlock, PreparedConditionApplication, PreparedConditionRemovals
from dnd.core.action_types import RestrictedActionKind
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType, spell_slot_cost_type
from dnd.core.base_conditions import BaseCondition, Duration, SpellProtectionRegistry
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, DamageRollResultEvent, Event, EventQueue, EventHandler, EventPhase, EventType, Range, RangeType, Trigger
from dnd.core.equipment_types import WeaponSlot
from dnd.core.life_types import LifeState
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spells.spell_utils import seen_recipients_error
from dnd.types.discovery import ActorScan, ScanRecord


def spell_component_allowed(owner: BaseCondition, target_uuid: UUID) -> bool:
    """Apply existing Globe/contact decisions to this component only."""
    caster=Entity.get(owner.source_entity_uuid)
    target=Entity.get(target_uuid)
    if caster is None or target is None or not owner.contributions_active():
        return False
    origin=owner.effect_origin
    level=origin.base_spell_level if origin is not None and origin.base_spell_level is not None else 1
    source_position=origin.source_position if origin is not None and origin.source_position is not None else caster.position
    return not SpellProtectionRegistry.is_protected(target.position,source_position,level)


def install_hit_rider(owner: BaseCondition,*,dice_count: int,die_size: Literal[4,6,8,10,12,20],
                      damage_type: DamageType | None,weapon_only: bool,
                      quarry: Callable[[], UUID | None] | None=None, recipient_uuid: UUID | None=None) -> EventHandler:
    """Append one exact-source component at native attack damage finalization."""
    caster=Entity.get(owner.source_entity_uuid)
    if caster is None:
        raise ValueError("Attack rider caster is absent")
    def append(event: Event,_: UUID) -> Event | None:
        if not isinstance(event,DamageRollResultEvent) or event.target_entity_uuid is None:
            return None
        if event.attack_outcome not in (AttackOutcome.HIT,AttackOutcome.CRIT):
            return None
        if recipient_uuid is not None and event.target_entity_uuid != recipient_uuid:
            return None
        if weapon_only and event.attack_kind!="weapon":
            return None
        if quarry is not None:
            if quarry()!=event.target_entity_uuid:
                return None
            target=Entity.get(event.target_entity_uuid)
            if target is None or not any(owner_uuid==target.uuid and
                    (child:=target.active_conditions_by_uuid.get(condition_uuid)) is not None and child.contributions_active()
                    for owner_uuid,condition_uuid in owner.linked_conditions):
                return None
        if not spell_component_allowed(owner,event.target_entity_uuid):
            return None
        component=Damage(name=owner.get_display_name(),source_entity_uuid=caster.uuid,
            target_entity_uuid=event.target_entity_uuid,damage_dice=die_size,dice_numbers=dice_count,
            damage_type=damage_type or event.damage_packets[0].damage.damage_type,effect_origin=owner.effect_origin,
            damage_bonus=ModifiableValue.create(source_entity_uuid=caster.uuid,base_value=0))
        roll=component.get_dice(event.attack_outcome).roll
        return event.append_damage_roll(component,roll,owner.get_display_name(),"Native attack-hit spell component")
    handler=EventHandler(name=owner.get_display_name(),source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.DAMAGE_ROLL_RESULT,event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=caster.uuid)],event_processor=append)
    caster.add_event_handler(handler)
    return handler


class QuarrySustain(ConcentrationActionMarker):
    """The surviving caster-owned root shared by the two authored mark spells."""
    quarry_uuid: UUID
    duration: Duration = Field(default_factory=lambda: Duration(duration=None,duration_type=DurationType.UNTIL_LONG_REST))
    tags: set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def reapply_available(self) -> bool:
        target=Entity.get(self.quarry_uuid)
        return target is None or target.health.life_state in (LifeState.DYING,LifeState.STABLE,LifeState.DEAD)

    def create_quarry_condition(self,target: Entity) -> BaseCondition:
        raise NotImplementedError

    def set_quarry(self,target: Entity,event: Event) -> bool:
        child=self.create_quarry_condition(target)
        child.effect_origin=self.effect_origin
        result=target.add_condition(child,parent_event=event)
        if result is None or result.canceled or not child.applied:
            return False
        for target_uuid,condition_uuid in tuple(self.linked_conditions):
            previous=Entity.get(target_uuid)
            if previous is not None and condition_uuid!=child.uuid:
                previous.remove_condition_by_uuid(condition_uuid,parent_event=event)
        self.linked_conditions=[]
        self.quarry_uuid=target.uuid
        self.add_linked_condition(target.uuid,child.uuid)
        return True


class ReapplyQuarry(BaseAction):
    sustain_uuid: UUID
    _quarry_application: PreparedConditionApplication | None = PrivateAttr(default=None)
    _old_removals: PreparedConditionRemovals | None = PrivateAttr(default=None)
    target_type: TargetType = TargetType.ENTITY
    valid_target_filter: str = "enemies"
    include_self: bool = False
    costs: list[Cost] = Field(default_factory=lambda:[Cost(name="Reapply mark",cost_type="bonus_actions",cost=1,
        evaluator=entity_action_economy_cost_evaluator)])

    def get_range(self) -> Range:
        return Range(type=RangeType.RANGE,normal=60)

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        sustain=BaseCondition.get(self.sustain_uuid)
        if not isinstance(sustain,QuarrySustain) or not sustain.applied or not sustain.contributions_active() or not sustain.reapply_available():
            return "The current quarry must first be defeated"
        return (seen_recipients_error(self,scan,selection.target_uuids)
            or self._target_filter_error(scan,list(selection.target_uuids)))

    def _cancel_quarry_admission(self) -> None:
        application=self._quarry_application
        if application is not None and not application.committed and not application.canceled:
            application.owner.cancel_condition_application(application,"Mark reapplication did not commit")
        if self._old_removals is not None and self._old_removals.committed_result is None:
            BaseBlock.cancel_owned_condition_removals(self._old_removals,"Mark reapplication did not commit")
        self._quarry_application=None
        self._old_removals=None

    def apply(self,parent_event: Event | None=None):
        try:
            return super().apply(parent_event)
        finally:
            self._cancel_quarry_admission()

    def _apply_costs(self,event: ActionEvent) -> ActionEvent:
        sustain=BaseCondition.get(self.sustain_uuid)
        target=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not isinstance(sustain,QuarrySustain) or target is None or not sustain.reapply_available():
            return event.cancel(status_message="Mark is no longer ready to reapply")
        child=sustain.create_quarry_condition(target)
        child.effect_origin=sustain.effect_origin
        application=target.prepare_condition_application(child,parent_event=event)
        if not isinstance(application,PreparedConditionApplication):
            return event.cancel(status_message="New quarry did not admit the mark")
        self._quarry_application=application
        prepared=PreparedConditionRemovals([])
        self._old_removals=prepared
        visited={sustain.uuid}
        for owner_uuid,condition_uuid in tuple(sustain.linked_conditions):
            owner=BaseBlock.get(owner_uuid)
            previous=owner.active_conditions_by_uuid.get(condition_uuid) if owner is not None else None
            if owner is not None and previous is not None and previous.applied:
                canceled=BaseBlock._prepare_condition_removal_tree(previous,condition_owner=owner,
                    expire=False,parent_event=event,prepared=prepared.entries,visited=visited)
                if canceled is not None:
                    self._cancel_quarry_admission()
                    return event.cancel(status_message="Previous quarry release was rejected")
        return entity_action_economy_cost_applier(event,self.source_entity_uuid)

    def _apply(self,event: ActionEvent) -> ActionEvent:
        sustain=BaseCondition.get(self.sustain_uuid)
        application=self._quarry_application
        prepared=self._old_removals
        if not isinstance(sustain,QuarrySustain) or application is None or prepared is None:
            return event.cancel(status_message="Mark admission is absent")
        effect=event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        if (BaseCondition.get(self.sustain_uuid) is not sustain or not sustain.applied
                or not sustain.contributions_active() or sustain.source_entity_uuid != self.source_entity_uuid):
            return effect.cancel(status_message="The mark's sustaining effect ended before reapplication")
        with BaseBlock.condition_removal_scope():
            BaseBlock.commit_owned_condition_removals(prepared)
            application.owner.commit_condition_application(application)
            sustain.quarry_uuid=application.owner.uuid
            sustain.linked_conditions=[]
            sustain.add_linked_condition(application.owner.uuid,application.condition.uuid)
            BaseBlock.publish_owned_condition_removals(prepared)
            application.owner.publish_condition_application(application)
        return effect


class AttackBackedSpell(SpellAction):
    """Three authored weapon-attempt spells with native, hit-only extra costs."""
    restricted_action_kinds: ClassVar[frozenset[RestrictedActionKind]] = frozenset({RestrictedActionKind.WEAPON_ATTACK})
    ranged_allowed: ClassVar[bool] = True
    weapon_slot: Literal[WeaponSlot.MELEE_MAIN,WeaponSlot.RANGED_MAIN] = WeaponSlot.MELEE_MAIN
    target_type: TargetType = TargetType.ENTITY
    harmful: bool = True
    selected_weapon_uuid: UUID | None = None

    def get_spell_weapon_attack_slot(self) -> WeaponSlot:
        return self.weapon_slot

    @property
    def performs_attack(self) -> bool:
        return True

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        self.costs=[cost for cost in self.costs if not cost.cost_type.startswith("spell_slot")]

    def _get_costs_for_level(self,level: int) -> list[Cost]:
        return [cost for cost in super()._get_costs_for_level(level) if not cost.cost_type.startswith("spell_slot")]

    def get_conditional_runtime_costs(self):
        return [Cost(name="Hit bonus action",cost_type="bonus_actions",cost=1,
                evaluator=entity_action_economy_cost_evaluator),
            Cost(name="Hit spell slot",cost_type=spell_slot_cost_type(self.cast_at_level),cost=1,
                evaluator=entity_action_economy_cost_evaluator)]

    def facet_domain(self, scan: ActorScan, level: Optional[int],
                     target: Optional[ScanRecord]) -> Tuple[Tuple[ActionVariantFacet, ...], ...]:
        return tuple((ActionVariantFacet(key="form", value=slot.value, label=slot.value.replace('_',' ').title()),)
                     for slot in ((WeaponSlot.MELEE_MAIN, WeaponSlot.RANGED_MAIN) if self.ranged_allowed else (WeaponSlot.MELEE_MAIN,)))

    def _selection_overrides(self, selection: ActionSelection) -> dict:
        return {**super()._selection_overrides(selection), "weapon_slot": WeaponSlot(selection_facet(selection, "form"))}

    def get_range(self) -> Range:
        caster=Entity.get(self.source_entity_uuid)
        return caster.get_weapon_range(self.weapon_slot) if caster is not None else self.spell_range

    def rule_error(self, scan: ActorScan, selection: ActionSelection) -> str | None:
        """An equipped weapon whose ordinary attack would be admitted against the target."""
        caster=Entity.get(self.source_entity_uuid)
        weapon=caster.equipment.get_weapon(self.weapon_slot) if caster is not None else None
        if caster is None or weapon is None or weapon.is_body_attack or weapon.spell_attack_profile is not None or (not self.ranged_allowed and self.weapon_slot is WeaponSlot.RANGED_MAIN):
            return "An equipped weapon is required"
        return weapon_attack_error(scan,caster,self.weapon_slot,None,
            selection.target_uuids[0] if selection.target_uuids else None,"Attack")

    def _create_declaration_event(self,parent_event: Event | None=None,use_register: bool=True):
        """Remember the exact weapon this declaration admits; the hit payload refuses a swapped one."""
        event=super()._create_declaration_event(parent_event,use_register)
        caster=Entity.get(self.source_entity_uuid)
        weapon=caster.equipment.get_weapon(self.weapon_slot) if caster is not None else None
        self.selected_weapon_uuid=weapon.uuid if weapon is not None else None
        return event

    def _on_costs_committed(self,declaration: ActionEvent,execution: ActionEvent) -> None:
        super()._on_costs_committed(declaration,execution)
        if any(cost.cost_type=="actions" and cost.cost>0 for cost in self.effective_costs):
            grant_weapon_attack_batch(self.source_entity_uuid,declaration,execution)

    def apply_hit_condition(self,event: SpellEvent,condition: BaseCondition) -> SpellEvent:
        """Optional hit riders have their own admission outcome, preserving the cast's terminal state."""
        if not hit_spell_payload_allowed(self,event):
            return event
        child=event.model_copy(update={"uuid":uuid4(),"lineage_uuid":uuid4(),"parent_event":event.uuid,
            "event_type":EventType.BASE_ACTION,"phase":EventPhase.EFFECT,"children_events":[],
            "lineage_children_events":[],"children_lineages":[],"retained_effect_origin":event.get_effect_origin()})
        registered=EventQueue.register(child)
        if not isinstance(registered,SpellEvent):
            return event.cancel(status_message="Hit rider declaration changed type")
        result=self.apply_owned_condition(registered,condition)
        return result if result.canceled else result.phase_to(EventPhase.COMPLETION)

    def apply_hit(self,event: SpellEvent,attack: AttackEvent) -> AttackEvent:
        raise NotImplementedError

    def _apply(self,event: SpellEvent) -> SpellEvent:
        effect=event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        caster=Entity.get(self.source_entity_uuid)
        if caster is None or (weapon:=caster.equipment.get_weapon(self.weapon_slot)) is None or weapon.uuid!=self.selected_weapon_uuid:
            return effect.cancel(status_message="Declared caster or exact weapon is absent")
        attack=create_weapon_attack_declaration_event(action_name=self.name or "Weapon spell",source_entity_uuid=caster.uuid,
            target_entity_uuid=event.target_entity_uuid,weapon_slot=self.weapon_slot,costs=[],parent_event=effect,use_register=False)
        attack=attack.phase_to(EventPhase.EXECUTION,use_register=True)
        def on_hit(hit: AttackEvent) -> AttackEvent:
            if not caster.action_economy.can_afford("bonus_actions",1) or not caster.action_economy.can_afford(spell_slot_cost_type(self.cast_at_level),1):
                return hit.cancel(status_message="Hit costs are no longer affordable")
            caster.action_economy.consume("bonus_actions",1)
            caster.action_economy.consume(spell_slot_cost_type(self.cast_at_level),1)
            return self.apply_hit(effect,hit)
        result=Attack.attack_consequences(attack,caster.uuid,on_hit=on_hit)
        if result is None or result.canceled:
            return effect.cancel(status_message="Weapon attack interrupted")
        return effect.with_updates(attack_outcome=result.attack_outcome,dice_roll=result.dice_roll,
            attack_bonus=result.attack_bonus,ac=result.ac,damages=result.damages,
            damage_rolls=result.damage_rolls,total_damage=result.total_damage)


def hit_spell_payload_allowed(spell: SpellAction,event: SpellEvent) -> bool:
    caster=Entity.get(spell.source_entity_uuid)
    target=Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
    if caster is None or target is None:
        return False
    origin=event.get_effect_origin()
    return not SpellProtectionRegistry.is_protected(target.position,origin.source_position or caster.position,spell.spell_level)
