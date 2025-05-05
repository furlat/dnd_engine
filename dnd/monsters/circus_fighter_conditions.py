from uuid import UUID
from typing import Dict, Any, Optional, List, Tuple

from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase
from dnd.core.modifiers import (
    NumericalModifier, AdvantageModifier, AdvantageStatus,
    AutoHitModifier, AutoHitStatus, ResistanceModifier, ResistanceStatus, DamageType
)
from dnd.entity import Entity
from dnd.features.elemental_advantage import create_elemental_advantage_modifier
from dnd.features.dual_wielder import create_dual_wielder_ac_modifier

class DualWielder(BaseCondition):
    name: str = "Dual Wielder"
    description: str = "You gain a +1 bonus to AC while wielding a separate melee weapon in each hand."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            # Add the contextual AC bonus
            dual_wielder = create_dual_wielder_ac_modifier(self.target_entity_uuid, self.source_entity_uuid)
            modifier_uuid = target_entity.equipment.ac_bonus.self_contextual.add_value_modifier(dual_wielder)
            outs.append((target_entity.equipment.ac_bonus.uuid, modifier_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

class ElementalWeaponMastery(BaseCondition):
    name: str = "Elemental Weapon Mastery"
    description: str = "You have advantage on attack rolls made with weapons that deal acid, cold, fire, lightning, poison, or thunder damage."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            # Add the contextual advantage modifier
            elemental_adv = create_elemental_advantage_modifier(self.target_entity_uuid, self.source_entity_uuid)
            modifier_uuid = target_entity.equipment.attack_bonus.self_contextual.add_advantage_modifier(elemental_adv)
            outs.append((target_entity.equipment.attack_bonus.uuid, modifier_uuid))
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

class ElementalAffinity(BaseCondition):
    name: str = "Elemental Affinity"
    description: str = "Years of performing with enchanted weapons have attuned you to fire, but left you vulnerable to cold. You have resistance to fire damage but vulnerability to cold damage."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            fire_resistance = ResistanceModifier(
                name="Elemental Affinity",
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
                damage_type=DamageType.FIRE,
                value=ResistanceStatus.RESISTANCE
            )
            cold_vulnerability = ResistanceModifier(
                name="Elemental Affinity",
                source_entity_uuid=self.target_entity_uuid,
                target_entity_uuid=self.source_entity_uuid,
                damage_type=DamageType.COLD,
                value=ResistanceStatus.VULNERABILITY
            )
            fire_resistance_uuid = target_entity.health.damage_reduction.self_static.add_resistance_modifier(fire_resistance)
            cold_vulnerability_uuid = target_entity.health.damage_reduction.self_static.add_resistance_modifier(cold_vulnerability)
            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return [],[fire_resistance_uuid,cold_vulnerability_uuid],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}")

class CircusPerformer(BaseCondition):
    name: str = "Circus Performer"
    description: str = "Your past in the circus has granted you exceptional acrobatic abilities and combat training."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            
            # Acrobatics expertise (+7 and expertise)
            acrobatics = target_entity.skill_set.get_skill("acrobatics")
            acro_mod_uuid = acrobatics.skill_bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=7,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((acrobatics.skill_bonus.uuid, acro_mod_uuid))

            # History penalty (-2)
            history = target_entity.skill_set.get_skill("history")
            hist_mod_uuid = history.skill_bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=-2,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((history.skill_bonus.uuid, hist_mod_uuid))

            # Strength saving throw bonus (+1)
            str_save = target_entity.saving_throws.get_saving_throw("strength")
            str_mod_uuid = str_save.bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((str_save.bonus.uuid, str_mod_uuid))

            # Intelligence saving throw penalty (-1)
            int_save = target_entity.saving_throws.get_saving_throw("intelligence")
            int_mod_uuid = int_save.bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=-1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((int_save.bonus.uuid, int_mod_uuid))

            # Extra reactions (+2)
            reactions_mod_uuid = target_entity.action_economy.reactions.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=2,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((target_entity.action_economy.reactions.uuid, reactions_mod_uuid))

            # Movement penalty (-5)
            movement_mod_uuid = target_entity.action_economy.movement.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=-5,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((target_entity.action_economy.movement.uuid, movement_mod_uuid))

            # AC bonus (+1)
            ac_mod_uuid = target_entity.equipment.ac_bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((target_entity.equipment.ac_bonus.uuid, ac_mod_uuid))

            # Unarmed damage bonus (+1)
            unarmed_mod_uuid = target_entity.equipment.unarmed_damage_bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((target_entity.equipment.unarmed_damage_bonus.uuid, unarmed_mod_uuid))

            # Proficiency bonus penalty (-1)
            prof_mod_uuid = target_entity.proficiency_bonus.self_static.add_value_modifier(
                NumericalModifier(
                    name="Circus Training",
                    value=-1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((target_entity.proficiency_bonus.uuid, prof_mod_uuid))

            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}") 

class Tired(BaseCondition):
    name: str = "Tired"
    description: str = "You are exhausted from combat or travel, reducing your movement speed and reactions."

    def _apply(self, event: Event) -> Tuple[List[Tuple[UUID,UUID]],List[UUID],List[UUID],Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")
        elif isinstance(target_entity,Entity):
            outs = []
            
            # Movement penalty (-10 feet)
            movement_mod_uuid = target_entity.action_economy.movement.self_static.add_value_modifier(
                NumericalModifier(
                    name="Tired",
                    value=-10,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((target_entity.action_economy.movement.uuid, movement_mod_uuid))

            # Reaction penalty (-1)
            reactions_mod_uuid = target_entity.action_economy.reactions.self_static.add_value_modifier(
                NumericalModifier(
                    name="Tired",
                    value=-1,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((target_entity.action_economy.reactions.uuid, reactions_mod_uuid))

            # Add disadvantage on Strength and Dexterity saving throws
            str_save = target_entity.saving_throws.get_saving_throw("strength")
            str_adv_uuid = str_save.bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Tired",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((str_save.bonus.uuid, str_adv_uuid))

            dex_save = target_entity.saving_throws.get_saving_throw("dexterity")
            dex_adv_uuid = dex_save.bonus.self_static.add_advantage_modifier(
                AdvantageModifier(
                    name="Tired",
                    value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=self.target_entity_uuid,
                    target_entity_uuid=self.source_entity_uuid
                )
            )
            outs.append((dex_save.bonus.uuid, dex_adv_uuid))

            effect_event = event.phase_to(EventPhase.EFFECT, update={"condition":self})
            return outs,[],[],effect_event
        else:
            return [],[],[],event.cancel(status_message=f"Target entity {self.target_entity_uuid} is not an entity but {type(target_entity)}") 