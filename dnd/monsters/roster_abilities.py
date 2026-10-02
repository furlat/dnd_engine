"""Selected creature capabilities, built from ordinary native actions/effects."""
from typing import cast, Literal
from uuid import UUID

from pydantic import Field

from dnd.actions import AttackEvent, entity_action_economy_cost_applier, entity_action_economy_cost_evaluator
from dnd.conditions import Concentrating, InvisibilityEffect
from dnd.core.base_actions import ActionEvent, BaseAction, Cost, TargetType
from dnd.core.base_conditions import BaseCondition, ConditionStateChangedEvent, Duration
from dnd.core.condition_types import ConditionTag, DurationType
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import Event, EventPhase
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, ContextualAdvantageModifier, NumericalModifier
from dnd.core.saving_throw_types import SAVING_THROW_CONTEXT_KEY, SavingThrowContext
from dnd.entity import Entity
from dnd.monsters.traits import MultiattackAction, NaturalAttack
from dnd.core.equipment_types import WeaponSlot
from dnd.spells.roster_support import FlyEffect


def magical_save_advantage(source_uuid: UUID, target_uuid: UUID | None, context: dict | None):
    cause = cast(SavingThrowContext | None, (context or {}).get(SAVING_THROW_CONTEXT_KEY))
    if cause is None or not cause.is_magical:
        return None
    return AdvantageModifier(name="Magic Resistance", value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=source_uuid, target_entity_uuid=target_uuid)


class MagicResistance(BaseCondition):
    name: str = "Magic Resistance"
    description: str = "Advantage on saves against spells and explicitly magical effects."

    def _apply(self, event: Event):
        owner = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if owner is None:
            return [], [], [], [], event.cancel(status_message="Trait owner missing")
        handles = []
        for saving_throw in (owner.saving_throws.strength_saving_throw,
                owner.saving_throws.dexterity_saving_throw, owner.saving_throws.constitution_saving_throw,
                owner.saving_throws.intelligence_saving_throw, owner.saving_throws.wisdom_saving_throw,
                owner.saving_throws.charisma_saving_throw):
            modifier = ContextualAdvantageModifier(name=self.name, source_entity_uuid=owner.uuid,
                target_entity_uuid=owner.uuid, callable=magical_save_advantage)
            handle = saving_throw.bonus.self_contextual.add_advantage_modifier(modifier)
            handles.append((saving_throw.bonus.uuid, handle))
        return handles, [], [], [], event.phase_to(EventPhase.EFFECT)


class InnateFlight(FlyEffect):
    """Same supported traversal grant, with authored speed and no concentration."""
    name: str = "Innate Flight"
    description: str = "Authored innate flying speed; supported movement without hovering."
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.PERMANENT))
    flying_speed: int = Field(default=40,gt=0)
    tags: set[ConditionTag] = Field(default_factory=set)


class InnateInvisibility(BaseAction):
    name: str = "Innate Invisibility"
    target_type: TargetType = TargetType.SELF
    costs: list[Cost] = Field(default_factory=lambda: [Cost(name="Innate Invisibility", cost_type="actions", cost=1, evaluator=entity_action_economy_cost_evaluator)])

    def _apply_costs(self, event: ActionEvent):
        return entity_action_economy_cost_applier(event, self.source_entity_uuid)

    def _apply(self, event: ActionEvent):
        owner = Entity.get(self.source_entity_uuid)
        if owner is None:
            return event.cancel(status_message="Trait owner missing")
        effect = event.phase_to(EventPhase.EFFECT)
        invisible = InvisibilityEffect(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid,
            duration=Duration(duration_type=DurationType.PERMANENT), reveal_on_spell=False,
            reveal_on_other_actions=False)
        applied = owner.add_condition(invisible, parent_event=effect)
        if applied is None or applied.canceled or not invisible.applied:
            return effect.cancel(status_message="Invisibility rejected")
        concentration = Concentrating(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid,
            spell_name=self.name, spell_id="action.monster.innate_invisibility")
        result = owner.add_condition(concentration, parent_event=effect)
        if result is None or result.canceled or not concentration.applied:
            owner.remove_condition_by_uuid(invisible.uuid, parent_event=effect)
            return effect.cancel(status_message="Concentration rejected")
        concentration.add_linked_condition(owner.uuid, invisible.uuid)
        return effect


class LifeDrainReduction(BaseCondition):
    name: str = "Life Drain"
    description: str = "Cumulative maximum hit points lost until long rest."
    duration: Duration = Field(default_factory=lambda: Duration(duration_type=DurationType.UNTIL_LONG_REST))
    amount: int = Field(gt=0)

    def _apply(self, event: Event):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is None:
            return [], [], [], [], event.cancel(status_message="Victim missing")
        current_hp = max(0, target.get_normal_hp())
        value = target.health.max_hit_points_bonus
        modifier = NumericalModifier(name=self.name, value=-self.amount,
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=target.uuid)
        value.self_static.add_value_modifier(modifier)
        target.health.damage_taken = max(0, target.get_max_hp()-min(current_hp, max(0,target.get_max_hp())))
        if target.get_max_hp() <= 0:
            target.receive_instant_death(self.source_entity_uuid, "Life Drain reduced maximum HP to zero", event.uuid)
        return [(value.uuid,modifier.uuid)], [], [], [], event.phase_to(EventPhase.EFFECT)

    def add_reduction(self, amount: int, event: Event) -> None:
        victim=Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if victim is None or amount <= 0:
            return
        hp=max(0,victim.get_normal_hp())
        value=victim.health.max_hit_points_bonus
        for handle in self.modifers_uuids.get(value.uuid,[]):
            value.self_static.value_modifiers[handle].value -= amount
        self.amount += amount
        victim.health.damage_taken=max(0,victim.get_max_hp()-min(hp,max(0,victim.get_max_hp())))
        ConditionStateChangedEvent(source_entity_uuid=event.source_entity_uuid,target_entity_uuid=victim.uuid,
            parent_event=event.uuid,phase=EventPhase.COMPLETION,condition_state=self.snapshot_state(),
            resulting_stats=victim.snapshot_entity_stats(),behavior_id=self.behavior_binding.behavior_id if self.behavior_binding else None)
        if victim.get_max_hp() <= 0:
            victim.receive_instant_death(event.source_entity_uuid,"Life Drain reduced maximum HP to zero",event.uuid)

    def _remove(self,event: Event | None = None):
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target is not None:
            hp = max(0,target.get_normal_hp())
            self.remove_condition_modifiers()
            target.health.damage_taken = max(0,target.get_max_hp()-hp)
        return super()._remove(event)


class WightLifeDrain(NaturalAttack):
    name: str = "Life Drain"
    description: str = "Melee +4, 1d6+2 necrotic; DC 13 Constitution gates lost maximum HP."
    natural_damage_dice: Literal[4,6,8,10,12,20] = 6
    natural_damage_type: DamageType = DamageType.NECROTIC
    fixed_attack_bonus: int | None = 4
    fixed_damage_bonus: int | None = 2

    def _apply(self, event: AttackEvent):
        victim = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
        result = super()._apply(event)
        if (victim is None or result is None or result.canceled
                or result.attack_outcome not in (AttackOutcome.HIT,AttackOutcome.CRIT)
                or not result.total_damage):
            return result
        owner = Entity.get(self.source_entity_uuid)
        if owner is None:
            return result
        request = owner.create_saving_throw_request(victim.uuid,"constitution",13,parent_event=result.uuid,
            saving_throw_context=SavingThrowContext(cause_id="action.monster.wight.life_drain",
                effect_id="trait.wight.life_drain.maximum_hp",is_magical=True))
        _,_,saved = victim.saving_throw(request)
        if not saved:
            previous = victim.active_conditions.get("Life Drain")
            if previous is not None:
                cast(LifeDrainReduction,previous).add_reduction(result.total_damage,result)
            else:
                victim.add_condition(LifeDrainReduction(source_entity_uuid=owner.uuid,
                    target_entity_uuid=victim.uuid,amount=result.total_damage),parent_event=result)
        return result


def wight_melee_multiattack(owner_uuid: UUID) -> MultiattackAction:
    """Author the SRD two-longsword action with its one Life Drain choice."""
    return MultiattackAction(source_entity_uuid=owner_uuid,
        attack_sequence=((WeaponSlot.MELEE_MAIN,2),), substitution_slot=WeaponSlot.MELEE_MAIN,
        substitution_item_id="weapon.longsword", attack_substitution=WightLifeDrain(source_entity_uuid=owner_uuid))
