from pydantic import BaseModel, Field, computed_field, field_validator, PrivateAttr
from typing import List, Optional, Dict, Any, Callable, Protocol, TypeVar, ClassVar,Union
import uuid
from uuid import UUID, uuid4
from enum import Enum


T_co = TypeVar('T_co', covariant=True)

ContextAwareCallable = Callable[[UUID, Optional[UUID], Optional[Dict[str, Any]]], T_co]

class AdvantageStatus(str, Enum):
    NONE = "None"
    ADVANTAGE = "Advantage"
    DISADVANTAGE = "Disadvantage"

class AutoHitStatus(str, Enum):
    NONE = "None"
    AUTOHIT = "Autohit"
    AUTOMISS = "Automiss"

class CriticalStatus(str, Enum):
    NONE = "None"
    AUTOCRIT = "Autocrit"
    NOCRIT = "Critical Immune"


class NumericalModifier(BaseModel):
    name: Optional[str] = None
    value: int
    uuid: UUID = Field(default_factory=lambda: uuid4())
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None

class AdvantageModifier(BaseModel):
    name: Optional[str] = None
    value: AdvantageStatus
    uuid: UUID = Field(default_factory=lambda: str(uuid4()))
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None

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
    name: Optional[str] = None
    value: CriticalStatus
    uuid: UUID = Field(default_factory=lambda: str(uuid4()))
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None

class AutoHitModifier(BaseModel):
    name: Optional[str] = None
    value: AutoHitStatus
    uuid: UUID = Field(default_factory=lambda: str(uuid4()))
    source_entity_uuid: UUID
    source_entity_name: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None

ContextAwareCondition = ContextAwareCallable[bool]
ContextAwareAdvantage = ContextAwareCallable[AdvantageModifier]
ContextAwareCritical = ContextAwareCallable[CriticalModifier]
ContextAwareAutoHit = ContextAwareCallable[AutoHitModifier]
ContextAwareModifier = ContextAwareCallable[NumericalModifier]
score_normaliziation_method = Callable[[int],int]
naming_callable = Callable[[List[str]],str]


class BaseValue(BaseModel):
    # Using ClassVar to declare a class-level attribute
    _registry: ClassVar[Dict[UUID, 'BaseValue']] = {}

    name: str = Field(default="A Value")
    uuid: UUID = Field(default_factory=uuid4)
    source_entity_uuid: UUID = Field(default_factory=uuid4)
    source_entity_name: Optional[str] = None
    target_entity_uuid: Optional[UUID] = None
    target_entity_name: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    score_normalizer: Callable[[int], int] = Field(default=lambda x: x)
    generated_from: List[UUID] = Field(default_factory=list)


    def __init__(self, **data):
        super().__init__(**data)
        self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseValue']:
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, BaseValue):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a BaseValue, but {type(value)}")

    @classmethod
    def register(cls, value: 'BaseValue') -> None:
        cls._registry[value.uuid] = value

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        cls._registry.pop(uuid, None)

    def get_generation_chain(self) -> List['BaseValue']:
        chain = []
        for uuid in self.generated_from:
            value = self.get(uuid)
            if value:
                chain.append(value)
                chain.extend(value.get_generation_chain())
        return chain

    def validate_source_id(self, source_id: UUID) -> None:
        if self.source_entity_uuid != source_id:
            raise ValueError("Source entity UUIDs do not match")
    
    def validate_target_id(self, target_id: UUID) -> None:
        if self.target_entity_uuid != target_id:
            raise ValueError("Target entity UUIDs do not match")

class StaticValue(BaseValue):
    value_modifiers: List[NumericalModifier] = Field(default_factory=list)
    min_constraints: List[NumericalModifier] = Field(default_factory=list)
    max_constraints: List[NumericalModifier] = Field(default_factory=list)
    advantage_modifiers: List[AdvantageModifier] = Field(default_factory=list)
    critical_modifiers: List[CriticalModifier] = Field(default_factory=list)
    auto_hit_modifiers: List[AutoHitModifier] = Field(default_factory=list)

    @classmethod
    def get(cls, uuid: UUID) -> Optional['StaticValue']:
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, StaticValue):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a StaticValue, but {type(value)}")

    @computed_field
    @property
    def min(self) -> Optional[int]:
        "min of all the min constraints"
        if not self.min_constraints:
            return None
        return min(constraint.value for constraint in self.min_constraints)
    
    @computed_field
    @property
    def max(self) -> Optional[int]:
        "max of all the max constraints"
        if not self.max_constraints:
            return None
        return max(constraint.value for constraint in self.max_constraints)
    
    @computed_field
    @property
    def score(self) -> int:
        modifier_sum= sum(modifier.value for modifier in self.value_modifiers)
        if self.max is not None and self.min is not None:
            return max(self.min, min(modifier_sum, self.max))
        elif self.max is not None:
            return min(modifier_sum, self.max)
        elif self.min is not None:
            return max(self.min, modifier_sum)
        else:
            return modifier_sum
    
    @computed_field
    @property
    def normalized_score(self) -> int:
        return self.score_normalizer(self.score)
    
    @computed_field
    @property
    def advantage_sum(self) -> int:
        return sum(modifier.numerical_value for modifier in self.advantage_modifiers)
    
    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """ For advantage each advantage counts as +1 and each disadvantage counts as -1"""
        
        if self.advantage_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif self.advantage_sum < 0:
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
        
    def combine_values(self, others: List['StaticValue'], naming_callable: Optional[naming_callable] = None) -> 'StaticValue':
        """ Combines this StaticValue with a list of other StaticValues """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)
        
        for other in others:
            self.validate_source_id(other.source_entity_uuid)
        
        return StaticValue(
            name=naming_callable([self.name] + [other.name for other in others ]),
            value_modifiers=self.value_modifiers + [mod for other in others for mod in other.value_modifiers],
            min_constraints=self.min_constraints + [con for other in others for con in other.min_constraints],
            max_constraints=self.max_constraints + [con for other in others for con in other.max_constraints],
            advantage_modifiers=self.advantage_modifiers + [mod for other in others for mod in other.advantage_modifiers],
            critical_modifiers=self.critical_modifiers + [mod for other in others for mod in other.critical_modifiers],
            auto_hit_modifiers=self.auto_hit_modifiers + [mod for other in others for mod in other.auto_hit_modifiers],
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            score_normalizer=self.score_normalizer
        )

class ContextualValue(BaseValue):
    value_modifiers: Dict[UUID, ContextAwareModifier] = Field(default_factory=dict)
    min_constraints: Dict[UUID, ContextAwareModifier] = Field(default_factory=dict)
    max_constraints: Dict[UUID, ContextAwareModifier] = Field(default_factory=dict)
    advantage_modifiers: Dict[UUID, ContextAwareAdvantage] = Field(default_factory=dict)
    critical_modifiers: Dict[UUID, ContextAwareCritical] = Field(default_factory=dict)
    auto_hit_modifiers: Dict[UUID, ContextAwareAutoHit] = Field(default_factory=dict)

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualValue']:
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, ContextualValue):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a ContextualValue, but {type(value)}")

    

    @computed_field
    @property
    def min(self) -> Optional[int]:
        if not self.min_constraints:
            return None
        return min(constraint(self.source_entity_uuid, self.target_entity_uuid, self.context).value for constraint in self.min_constraints.values())
    
    @computed_field
    @property
    def max(self) -> Optional[int]:
        if not self.max_constraints:
            return None
        return max(constraint(self.source_entity_uuid, self.target_entity_uuid, self.context).value for constraint in self.max_constraints.values())

    @computed_field
    @property
    def score(self) -> int:
        modifier_sum= sum(context_aware_modifier(self.source_entity_uuid, self.target_entity_uuid, self.context).value for context_aware_modifier in self.value_modifiers.values())
        if self.max is not None and self.min is not None:
            return max(self.min, min(modifier_sum, self.max))
        elif self.max is not None:
            return min(modifier_sum, self.max)
        elif self.min is not None:
            return max(self.min, modifier_sum)
        else:
            return modifier_sum

    @computed_field
    @property
    def normalized_score(self) -> int:
        return self.score_normalizer(self.score)
    
    @computed_field
    @property
    def advantage_sum(self) -> int:
        return sum(modifier.numerical_value for modifier in self.advantage_modifiers.values())

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """ For advantage each advantage counts as +1 and each disadvantage counts as -1"""
        if self.advantage_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif self.advantage_sum < 0:
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
            uiid = uuid4()
        self.value_modifiers[uiid] = modifier
        return uiid
    
    def remove_value_modifier(self, uiid:UUID) -> None:
        if uiid in self.value_modifiers:
            del self.value_modifiers[uiid]

    def add_min_constraint(self, constraint: ContextAwareModifier,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid4()
        self.min_constraints[uiid] = constraint
        return uiid
    
    def remove_min_constraint(self, uiid:UUID) -> None:
        if uiid in self.min_constraints:
            del self.min_constraints[uiid]
    def add_max_constraint(self, constraint: ContextAwareModifier,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid4()
        self.max_constraints[uiid] = constraint
        return uiid
    
    def remove_max_constraint(self, uiid:UUID) -> None:
        if uiid in self.max_constraints:
            del self.max_constraints[uiid]
    
    def add_advantage_modifier(self, modifier: ContextAwareAdvantage,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid4()
        self.advantage_modifiers[uiid] = modifier
        return uiid
    
    def remove_advantage_modifier(self, uiid:UUID) -> None:
        if uiid in self.advantage_modifiers:
            del self.advantage_modifiers[uiid]
    
    def add_critical_modifier(self, modifier: ContextAwareCritical,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid4()
        self.critical_modifiers[uiid] = modifier
        return uiid
    
    def remove_critical_modifier(self, uiid:UUID) -> None:
        if uiid in self.critical_modifiers:
            del self.critical_modifiers[uiid]
    
    def add_auto_hit_modifier(self, modifier: ContextAwareAutoHit,uiid:Optional[UUID]=None) -> UUID:
        if uiid is None:
            uiid = uuid4()
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

    def combine_values(self, others: List['ContextualValue'], naming_callable: Optional[naming_callable] = None) -> 'ContextualValue':
        """ Combines this ContextualValue with a list of other ContextualValues """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)
        
        for other in others:
            self.validate_source_id(other.source_entity_uuid)
        
        def merge_dicts(*dicts):
            return {k: v for d in dicts for k, v in d.items()}

        return ContextualValue(
            name=naming_callable([self.name] + [other.name for other in others]),
            value_modifiers=merge_dicts(self.value_modifiers, *(other.value_modifiers for other in others)),
            min_constraints=merge_dicts(self.min_constraints, *(other.min_constraints for other in others)),
            max_constraints=merge_dicts(self.max_constraints, *(other.max_constraints for other in others)),
            advantage_modifiers=merge_dicts(self.advantage_modifiers, *(other.advantage_modifiers for other in others)),
            critical_modifiers=merge_dicts(self.critical_modifiers, *(other.critical_modifiers for other in others)),
            auto_hit_modifiers=merge_dicts(self.auto_hit_modifiers, *(other.auto_hit_modifiers for other in others)),
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            target_entity_uuid=self.target_entity_uuid,
            target_entity_name=self.target_entity_name,
            context=self.context,
            score_normalizer=self.score_normalizer
        )

class ModifiableValue(BaseValue):
    self_static: StaticValue = Field(default_factory=StaticValue)
    to_target_static: StaticValue = Field(default_factory=StaticValue)
    self_contextual: ContextualValue = Field(default_factory=ContextualValue)
    to_target_contextual: ContextualValue = Field(default_factory=ContextualValue)
    from_target_contextual: Optional[ContextualValue] = None
    from_target_static: Optional[StaticValue] = None

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ModifiableValue']:
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, ModifiableValue):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a ModifiableValue, but {type(value)}")
        
    
    @computed_field
    @property
    def min(self) -> Optional[int]:
        modifiers = [self.self_static, self.from_target_static, self.self_contextual, self.from_target_contextual]
        typed_modifiers: List[Union[StaticValue, ContextualValue]] = [modifier for modifier in modifiers if modifier is not None]
        modifiers_min = [modifier.min for modifier in typed_modifiers if modifier.min is not None]
        if len(modifiers_min) == 0:
            return None
        return min(modifiers_min)
    
    
    @computed_field
    @property
    def max(self) -> Optional[int]:
        modifiers = [self.self_static, self.from_target_static, self.self_contextual, self.from_target_contextual]
        typed_modifiers: List[Union[StaticValue, ContextualValue]] = [modifier for modifier in modifiers if modifier is not None]
        modifiers_max = [modifier.max for modifier in typed_modifiers if modifier.max is not None]
        if len(modifiers_max) == 0:
            return None
        return max(modifiers_max)
    

    @computed_field
    @property
    def score(self) -> int:
        modifiers = [self.self_contextual, self.self_static, self.from_target_static, self.from_target_contextual]
        typed_modifiers: List[Union[StaticValue, ContextualValue]] = [modifier for modifier in modifiers if modifier is not None]
        if self.max is not None and self.min is not None:
            return max(self.min, min(sum(modifier.score for modifier in typed_modifiers), self.max))
        elif self.max is not None:
            return min(sum(modifier.score for modifier in typed_modifiers), self.max)
        elif self.min is not None:
            return max(self.min, sum(modifier.score for modifier in typed_modifiers))
        else:
            return sum(modifier.score for modifier in typed_modifiers)
    
    @computed_field
    @property
    def normalized_score(self) -> int:
        return self.score_normalizer(self.score)
    
    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        total_sum = sum(adv.advantage_sum for adv in [self.self_static, self.from_target_static, self.self_contextual, self.from_target_contextual] if adv is not None)
        if total_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif total_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE
    
    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        modifiers = [self.self_static, self.from_target_static, self.self_contextual, self.from_target_contextual]
        typed_modifiers: List[Union[StaticValue, ContextualValue]] = [modifier for modifier in modifiers if modifier is not None]
        all_critical_modifiers = [modifier.critical for modifier in typed_modifiers]
        if CriticalStatus.NOCRIT in all_critical_modifiers:
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in all_critical_modifiers:
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE
    
    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        modifiers = [self.self_static, self.from_target_static, self.self_contextual, self.from_target_contextual]
        typed_modifiers: List[Union[StaticValue, ContextualValue]] = [modifier for modifier in modifiers if modifier is not None]
        all_auto_hit_modifiers = [modifier.auto_hit for modifier in typed_modifiers]
        if AutoHitStatus.AUTOMISS in all_auto_hit_modifiers:
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in all_auto_hit_modifiers:
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE

    def set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None:
        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name
        self.self_contextual.set_target_entity(target_entity_uuid, target_entity_name)
        self.to_target_contextual.set_target_entity(target_entity_uuid, target_entity_name)

    def clear_target_entity(self) -> None:
        self.target_entity_uuid = None
        self.target_entity_name = None
        self.self_contextual.clear_target_entity()
        self.to_target_contextual.clear_target_entity()
        self.from_target_contextual = None
        self.from_target_static = None

    def set_context(self, context: Dict[str,Any]) -> None:
        self.context = context
        self.to_target_contextual.set_context(context)
        self.self_contextual.set_context(context)

    def clear_context(self) -> None:
        self.context = None
        self.to_target_contextual.clear_context()
        self.self_contextual.clear_context()

    def set_from_target_contextual(self, contextual: ContextualValue) -> None:
        self.validate_target_id(contextual.source_entity_uuid)
        self.from_target_contextual = contextual.model_copy(update={"target_entity_uuid": self.source_entity_uuid, "target_entity_name": self.source_entity_name})

    def set_from_target_static(self, static: StaticValue) -> None:
        self.validate_target_id(static.source_entity_uuid)
        self.from_target_static = static.model_copy(update={"target_entity_uuid": self.source_entity_uuid, "target_entity_name": self.source_entity_name})

    def set_from_target(self, target_value: 'ModifiableValue') -> None:
        self.set_from_target_contextual(target_value.to_target_contextual)
        self.set_from_target_static(target_value.to_target_static)
    
    def combine_values(self, others: List['ModifiableValue'], naming_callable: Optional[naming_callable] = None) -> 'ModifiableValue':
        """ Combines this ModifiableValue with a list of other ModifiableValues """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)
        
        for other in others:
            self.validate_source_id(other.source_entity_uuid)
        
        return ModifiableValue(
            name=naming_callable([self.name] + [other.name for other in others]),
            self_static=self.self_static.combine_values([other.self_static for other in others]),
            to_target_static=self.to_target_static.combine_values([other.to_target_static for other in others]),
            self_contextual=self.self_contextual.combine_values([other.self_contextual for other in others]),
            to_target_contextual=self.to_target_contextual.combine_values([other.to_target_contextual for other in others]),
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            target_entity_uuid=self.target_entity_uuid,
            target_entity_name=self.target_entity_name,
            context=self.context,
            score_normalizer=self.score_normalizer
        )
    

        
            
