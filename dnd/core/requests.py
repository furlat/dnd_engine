from typing import Literal as TypeLiteral, Union, Optional, Dict, Any, Self
from dnd.core.values import ModifiableValue
from uuid import UUID, uuid4
from pydantic import BaseModel, model_validator 




AbilityName = TypeLiteral[
    'strength', 'dexterity', 'constitution', 
    'intelligence', 'wisdom', 'charisma'
]

SkillName = TypeLiteral[
    'acrobatics', 'animal_handling', 'arcana', 'athletics', 
    'deception', 'history', 'insight', 'intimidation', 
    'investigation', 'medicine', 'nature', 'perception', 
    'performance', 'persuasion', 'religion', 'sleight_of_hand', 
    'stealth', 'survival'
]

class BaseRequest(BaseModel):
    """ A base request for all requests """
    dc: Union[int,ModifiableValue]
    source_entity_uuid: UUID
    target_entity_uuid: UUID
    context: Optional[Dict[str,Any]] = None

    @model_validator(mode="after")
    def check_entities_uuid(self) -> Self:
        """ If dc is a modifiable value ensure that the source entity uuid is the same as the source entity uuid of the modifiable value """
        if isinstance(self.dc,ModifiableValue):
            if self.dc.source_entity_uuid != self.source_entity_uuid:
                raise ValueError("Source entity uuid does not match")
            if self.target_entity_uuid is not None and self.dc.target_entity_uuid != self.target_entity_uuid:
                raise ValueError("Target entity uuid does not match")
        return self

    def get_dc(self) -> int:
        """ Get the dc for the saving throw """
        if isinstance(self.dc,int):
            return self.dc
        else:
            return self.dc.normalized_score
        
class SavingThrowRequest(BaseRequest):
    """ A request to make a saving throw """
    ability_name: AbilityName
   

class SkillCheckRequest(BaseRequest):
    """ A request to make a skill check """
    skill_name: SkillName
   