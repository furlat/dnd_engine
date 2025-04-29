from dnd.core.base_conditions import BaseCondition, Duration, DurationType
from dnd.entity import Entity
from typing import Dict, Any, Optional, List, Tuple
from dnd.core.modifiers import ContextAwareCondition, BaseObject, AdvantageModifier, AutoHitModifier, AdvantageStatus, AutoHitStatus
from dnd.blocks.skills import skills_requiring_sight, skills_requiring_hearing, skills_requiring_speak
from uuid import UUID, uuid4
from pydantic import Field



class Blinded(BaseCondition):
    name: str = "Blinded"
    description: str = "A blinded creature can't see and automatically fails any ability check that requires sight. Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage."
    
    def _apply(self,context: Optional[Dict[str, Any]] = None) -> List[Tuple[UUID,UUID]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")
        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return []
        
        elif isinstance(target_entity,Entity):
            #the modifier is applied to the target entity henceh the source and target are switched
            outs = []
   
            self_static_condition_uuid = target_entity.equipment.attack_bonus.self_static.add_advantage_modifier(AdvantageModifier(name="Blinded",value=AdvantageStatus.DISADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            to_target_static_condition_uuid =target_entity.equipment.ac_bonus.to_target_static.add_advantage_modifier(AdvantageModifier(name="Blinded",value=AdvantageStatus.ADVANTAGE,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
            outs.append((target_entity.equipment.attack_bonus.uuid,self_static_condition_uuid))
            outs.append((target_entity.equipment.ac_bonus.uuid,to_target_static_condition_uuid))
            for skill in skills_requiring_sight:
                skill_obj = target_entity.skill_set.get_skill(skill)
               
                modifier_uuid=skill_obj.skill_bonus.self_static.add_auto_hit_modifier(AutoHitModifier(name="Blinded",value=AutoHitStatus.AUTOMISS,source_entity_uuid=self.target_entity_uuid,target_entity_uuid=self.source_entity_uuid))
                outs.append((skill_obj.skill_bonus.uuid,modifier_uuid))
            return outs
        else:
            return []   
        

        
