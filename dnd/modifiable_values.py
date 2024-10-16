from pydantic import BaseModel, Field, computed_field, field_validator
from typing import List, Optional, Dict, Any, Callable, Protocol, TypeVar
import uuid
from uuid import UUID
from dnd.dnd_enums import AdvantageStatus, CriticalStatus, AutoHitStatus

T_co = TypeVar('T_co', covariant=True)

ContextAwareCallable = Callable[[UUID, Optional[UUID], Optional[Dict[str, Any]]], T_co]

class NumericalModifier(BaseModel):
    name: str
    value: int
    uuid: UUID = Field(default_factory=lambda: uuid.uuid4())
    source_entity_uuid: UUID
    source_entity_name: str
    target_entity_uuid: UUID
    target_entity_name: str

class AdvantageModifier(BaseModel):
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

class CriticalModifier(BaseModel):
    name: str
    value: CriticalStatus
    uuid: UUID = Field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_uuid: UUID
    source_entity_name: str
    target_entity_uuid: UUID
    target_entity_name: str

class AutoHitModifier(BaseModel):
    name: str
    value: AutoHitStatus
    uuid: UUID = Field(default_factory=lambda: str(uuid.uuid4()))
    source_entity_uuid: UUID
    source_entity_name: str
    target_entity_uuid: UUID
    target_entity_name: str

ContextAwareCondition = ContextAwareCallable[bool]
ContextAwareAdvantage = ContextAwareCallable[AdvantageModifier]
ContextAwareCritical = ContextAwareCallable[CriticalModifier]
ContextAwareAutoHit = ContextAwareCallable[AutoHitModifier]
ContextAwareModifier = ContextAwareCallable[NumericalModifier]
score_normaliziation_method = Callable[[int],int]
naming_callable = Callable[[str,str],str]


class StaticValue(BaseModel):
    name:str
    uuid: UUID = Field(default_factory=lambda: uuid.uuid4())
    value_modifiers: List[NumericalModifier] = Field(default_factory=list)
    min_constraints: List[NumericalModifier] = Field(default_factory=list)
    max_constraints: List[NumericalModifier] = Field(default_factory=list)
    advantage_modifiers: List[AdvantageModifier] = Field(default_factory=list)
    critical_modifiers: List[CriticalModifier] = Field(default_factory=list)
    auto_hit_modifiers: List[AutoHitModifier] = Field(default_factory=list)
    generated_from: List[UUID] = Field(default_factory=list)
    score_normalizer: score_normaliziation_method = Field(default=lambda x: x)

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
    def score(self) -> int:
        modifier_sum= sum(modifier.value for modifier in self.value_modifiers)
        return max(self.min, min(modifier_sum, self.max))
    
    @computed_field
    @property
    def normalized_score(self) -> int:
        return self.score_normalizer(self.score)
    
    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """ For advantage each advantage counts as +1 and each disadvantage counts as -1"""
        advantage_sum = sum(modifier.numerical_value for modifier in self.advantage_modifiers)
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
        if CriticalStatus.NOCRIT in self.critical_modifiers:
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in self.critical_modifiers:
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE
        
    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """ For auto hit AUTOMISS takes precedence over AUTOHIT """
        if AutoHitStatus.AUTOMISS in self.auto_hit_modifiers:
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in self.auto_hit_modifiers:
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE
        

    def combine_values(self, other: 'StaticValue', naming_callable:Optional[naming_callable]=None) -> 'StaticValue':
        """ Combines two values by adding their modifiers, constraints, and modifiers """
        if naming_callable is None:
            naming_callable = lambda name, other_name: f"{name}_{other_name}"
        return StaticValue(
            name=naming_callable(self.name, other.name),
            value_modifiers=self.value_modifiers + other.value_modifiers,
            min_constraints=self.min_constraints + other.min_constraints,
            max_constraints= self.max_constraints + other.max_constraints,
            advantage_modifiers=self.advantage_modifiers + other.advantage_modifiers,
            critical_modifiers=self.critical_modifiers + other.critical_modifiers,
            auto_hit_modifiers=self.auto_hit_modifiers + other.auto_hit_modifiers,
            generated_from=[self.uuid, other.uuid]
        )
    

class ContextualValue(BaseModel):
    name:str
    uuid: UUID = Field(default_factory=lambda: uuid.uuid4())
    value_modifiers: Dict[UUID,ContextAwareModifier] = Field(default_factory=dict)
    min_constraints: Dict[UUID,ContextAwareModifier] = Field(default_factory=dict)
    max_constraints: Dict[UUID,ContextAwareModifier] = Field(default_factory=dict)
    advantage_modifiers: Dict[UUID,ContextAwareAdvantage] = Field(default_factory=dict)
    critical_modifiers: Dict[UUID,ContextAwareCritical] = Field(default_factory=dict)
    auto_hit_modifiers: Dict[UUID,ContextAwareAutoHit] = Field(default_factory=dict)
    generated_from: List[UUID] = Field(default_factory=list)
    source_entity_uuid: UUID
    source_entity_name: str
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None
    context: Optional[Dict[str,Any]] = None
    score_normalizer: score_normaliziation_method = Field(default=lambda x: x)

    def set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None:
        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name
    
    def clear_target_entity(self) -> None:
        self.target_entity_uuid = None
        self.target_entity_name = None
    
    def set_context(self, context: Dict[str,Any]) -> None:
        self.context = context
    
    def clear_context(self) -> None:
        self.context = None
    
    def add_value_modifier(self, modifier: ContextAwareModifier,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid.uuid4()
        self.value_modifiers[uiid] = modifier
        return uiid
    
    def remove_value_modifier(self, uiid:UUID) -> None:
        if uiid in self.value_modifiers:
            del self.value_modifiers[uiid]

    def add_min_constraint(self, constraint: ContextAwareModifier,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid.uuid4()
        self.min_constraints[uiid] = constraint
        return uiid
    
    def remove_min_constraint(self, uiid:UUID) -> None:
        if uiid in self.min_constraints:
            del self.min_constraints[uiid]
    def add_max_constraint(self, constraint: ContextAwareModifier,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid.uuid4()
        self.max_constraints[uiid] = constraint
        return uiid
    
    def remove_max_constraint(self, uiid:UUID) -> None:
        if uiid in self.max_constraints:
            del self.max_constraints[uiid]
    
    def add_advantage_modifier(self, modifier: ContextAwareAdvantage,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid.uuid4()
        self.advantage_modifiers[uiid] = modifier
        return uiid
    
    def remove_advantage_modifier(self, uiid:UUID) -> None:
        if uiid in self.advantage_modifiers:
            del self.advantage_modifiers[uiid]
    
    def add_critical_modifier(self, modifier: ContextAwareCritical,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid.uuid4()
        self.critical_modifiers[uiid] = modifier
        return uiid
    
    def remove_critical_modifier(self, uiid:UUID) -> None:
        if uiid in self.critical_modifiers:
            del self.critical_modifiers[uiid]
    
    def add_auto_hit_modifier(self, modifier: ContextAwareAutoHit,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid.uuid4()
        self.auto_hit_modifiers[uiid] = modifier
        return uiid
    
    def remove_auto_hit_modifier(self, uiid:UUID) -> None:
        if uiid in self.auto_hit_modifiers:
            del self.auto_hit_modifiers[uiid]
    
    def remove_modifier(self, uiid:UUID) -> None:
        self.remove_value_modifier(uiid)
        self.remove_min_constraint(uiid)
        self.remove_max_constraint(uiid)
        self.remove_advantage_modifier(uiid)
        self.remove_critical_modifier(uiid)
        self.remove_auto_hit_modifier(uiid)

    @computed_field
    @property
    def min(self) -> int:
        return min(constraint(self.source_entity_uuid, self.target_entity_uuid, self.context).value for constraint in self.min_constraints.values())
    
    @computed_field
    @property
    def max(self) -> int:
        return max(constraint(self.source_entity_uuid, self.target_entity_uuid, self.context).value for constraint in self.max_constraints.values())

    @computed_field
    @property
    def score(self) -> int:
        modifier_sum= sum(context_aware_modifier(self.source_entity_uuid, self.target_entity_uuid, self.context).value for context_aware_modifier in self.value_modifiers.values())
        return max(self.min, min(modifier_sum, self.max))

    @computed_field
    @property
    def normalized_score(self) -> int:
        return self.score_normalizer(self.score)

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """ For advantage each advantage counts as +1 and each disadvantage counts as -1"""
        advantage_sum = sum(modifier(self.source_entity_uuid, self.target_entity_uuid, self.context).numerical_value for modifier in self.advantage_modifiers.values())
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
        critical_modifiers = [modifier(self.source_entity_uuid, self.target_entity_uuid, self.context) for modifier in self.critical_modifiers.values()]
        if CriticalStatus.NOCRIT in critical_modifiers:
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in critical_modifiers:
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE
        
    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """ For auto hit AUTOMISS takes precedence over AUTOHIT """
        auto_hit_modifiers = [modifier(self.source_entity_uuid, self.target_entity_uuid, self.context) for modifier in self.auto_hit_modifiers.values()]
        if AutoHitStatus.AUTOMISS in auto_hit_modifiers:
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in auto_hit_modifiers:
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE
        
    

    def combine_values(self, other: 'ContextualValue', naming_callable: Optional[naming_callable] = None) -> 'ContextualValue':
        """ Combines two ContextualValues by merging their dictionaries of modifiers and constraints """
        if naming_callable is None:
            naming_callable = lambda name, other_name: f"{name}_{other_name}"

        def merge_dicts(d1, d2):
            return {**d1, **d2}

        return ContextualValue(
            name=naming_callable(self.name, other.name),
            value_modifiers=merge_dicts(self.value_modifiers, other.value_modifiers),
            min_constraints=merge_dicts(self.min_constraints, other.min_constraints),
            max_constraints=merge_dicts(self.max_constraints, other.max_constraints),
            advantage_modifiers=merge_dicts(self.advantage_modifiers, other.advantage_modifiers),
            critical_modifiers=merge_dicts(self.critical_modifiers, other.critical_modifiers),
            auto_hit_modifiers=merge_dicts(self.auto_hit_modifiers, other.auto_hit_modifiers),
            generated_from=[self.uuid, other.uuid],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            target_entity_uuid=self.target_entity_uuid,
            target_entity_name=self.target_entity_name,
            context=self.context,
            score_normalizer=self.score_normalizer
        )
