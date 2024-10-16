from pydantic import BaseModel, Field, computed_field, field_validator
from typing import List, Optional, Dict, Any, Callable, Protocol, TypeVar
import uuid
from uuid import UUID
from dnd.dnd_enums import AdvantageStatus, CriticalStatus, AutoHitStatus

T_co = TypeVar('T_co', covariant=True)

class ContextAwareCallable(Protocol[T_co]):
    def __call__(self, 
                 source_entity_uuid: UUID, 
                 target_entity_uuid: Optional[UUID], 
                 context: Optional[Dict[str, Any]]
                ) -> T_co:
        ...

class NumericalBonus(BaseModel):
    name: str
    value: int
    uuid: UUID = Field(default_factory=lambda: uuid.uuid4())
    source_entity_uuid: UUID
    source_entity_name: str
    target_entity_uuid: UUID
    target_entity_name: str

class AdvantageBonus(BaseModel):
    name: str
    value: AdvantageStatus
    uuid: UUID = Field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_uuid: UUID
    source_entity_name: str
    target_entity_uuid: UUID
    target_entity_name: str

    @computed_field
    @property
    def numerical_value(self) -> int:
        if self.value == AutoHitStatus.AUTOHIT:
            return 1
        elif self.value == AutoHitStatus.AUTOMISS:
            return -1
        else:
            return 0

class CriticalBonus(BaseModel):
    name: str
    value: CriticalStatus
    uuid: UUID = Field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_uuid: UUID
    source_entity_name: str
    target_entity_uuid: UUID
    target_entity_name: str

class AutoHitBonus(BaseModel):
    name: str
    value: AutoHitStatus
    uuid: UUID = Field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_uuid: UUID
    source_entity_name: str
    target_entity_uuid: UUID
    target_entity_name: str

class ContextAwareCondition(ContextAwareCallable[bool]):
    ...

class ContextAwareAdvantage(ContextAwareCallable[AdvantageBonus]):
    ...

class ContextAwareCritical(ContextAwareCallable[CriticalBonus]):
    ...

class ContextAwareAutoHit(ContextAwareCallable[AutoHitBonus]):
    ...

class ContextAwareBonus(ContextAwareCallable[NumericalBonus]):
    ...

class Value(BaseModel):
    value_bonuses: List[NumericalBonus]
    min_constraints: List[NumericalBonus]
    max_constraints: List[NumericalBonus]
    advantage_statuses: List[AdvantageBonus]
    critical_statuses: List[CriticalBonus]
    auto_hit_statuses: List[AutoHitBonus]

   
    @computed_field
    @property
    def min(self) -> int:
        "min of all the min constraints"
        return min(constraint.value for constraint in self.min_constraints)
    
    @computed_field
    @property
    def max(self) -> int:
        "max of all the max constraints"
        return max(constraint.value for constraint in self.max_constraints)
    
    @computed_field
    @property
    def bonus(self) -> int:
        bonus_sum= sum(bonus.value for bonus in self.value_bonuses)
        return max(self.min, min(bonus_sum, self.max))
    
    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """ For advantage each advantage counts as +1 and each disadvantage counts as -1"""
        advantage_sum = sum(bonus.numerical_value for bonus in self.advantage_statuses)
        if advantage_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif advantage_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE
        
    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """ For critical NOCRIT takes precedence over AUTOCRIT """
        if CriticalStatus.NOCRIT in self.critical_statuses:
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in self.critical_statuses:
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE
        
    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """ For auto hit AUTOMISS takes precedence over AUTOHIT """
        if AutoHitStatus.AUTOMISS in self.auto_hit_statuses:
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in self.auto_hit_statuses:
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE
        

    def combine_values(self, other: 'Value') -> 'Value':
        """ Combines two values by adding their bonuses, constraints, and statuses """


        return Value(
            value_bonuses=self.value_bonuses + other.value_bonuses,
            min_constraints=self.min_constraints + other.min_constraints,
            max_constraints= self.max_constraints + other.max_constraints,
            advantage_statuses=self.advantage_statuses + other.advantage_statuses,
            critical_statuses=self.critical_statuses + other.critical_statuses,
            auto_hit_statuses=self.auto_hit_statuses + other.auto_hit_statuses
        )
    
 

