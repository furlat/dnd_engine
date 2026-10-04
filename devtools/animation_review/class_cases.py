"""Native direct-progression class actions recorded by the standard gallery."""
from typing import Literal
from pydantic import BaseModel,ConfigDict


class ClassFeatureCase(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    kind:Literal['class-feature']
    program:Literal['rage','frenzy','reckless','intimidate','relentless','mindless','native_martial',
        'second_wind','action_surge','protection','indomitable','survivor','font_gather','font_shape',
        'quickened','twinned','distant','affinity','wings','awe','draconic_fear']
    succeeded:bool=True
    hidden_owner:bool=False
    martial_route:Literal['frenzied','retaliation','extra']='frenzied'
    retire:bool=False
