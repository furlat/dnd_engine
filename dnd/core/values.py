from pydantic import BaseModel, Field, computed_field, field_validator, PrivateAttr, model_validator, ConfigDict
from typing import List, Optional, Dict, Any, Callable, Protocol, TypeVar, ClassVar, Union, Tuple, Self
import uuid
from uuid import UUID, uuid4
from enum import Enum
from dnd.core.modifiers import (
    BaseObject,
    naming_callable,
    NumericalModifier,
    AdvantageModifier,
    CriticalModifier,
    AutoHitModifier,
    AdvantageStatus,
    CriticalStatus,
    AutoHitStatus,
    Size,
    DamageType,
    SizeModifier,
    DamageTypeModifier,
    ContextualNumericalModifier,
    ContextualAdvantageModifier,
    ContextualCriticalModifier,
    ContextualAutoHitModifier,
    ContextualSizeModifier,
    ContextualDamageTypeModifier,
    ResistanceModifier,
    ContextualResistanceModifier,
    ResistanceStatus
)
import inspect
import random  # Add this import at the top of the file


def identity(x: int) -> int:
    return x

class BaseValue(BaseObject): 
    """
    Base class for all value types in the system.

    This class serves as the foundation for various types of values that can be used in the game system.
    It includes basic information about the value, such as its name, source, target, and context.

    Attributes:
        name (str): The name of the value. Defaults to 'A Value' if not specified.
        uuid (UUID): Unique identifier for the value. Automatically generated if not provided.
        source_entity_uuid (UUID): UUID of the entity that is the source of this value. Must be provided explicitly.
        source_entity_name (Optional[str]): Name of the entity that is the source of this value. Can be None.
        target_entity_uuid (Optional[UUID]): UUID of the entity that this value targets, if any. Can be None.
        target_entity_name (Optional[str]): Name of the entity that this value targets, if any. Can be None.
        context (Optional[Dict[str, Any]]): Additional context information for this value. Can be None.
        score_normalizer (Callable[[int], int]): A function to normalize the score. Defaults to identity function.
        generated_from (List[UUID]): List of UUIDs of values that this value was generated from.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseValue']]): A class-level registry to store all instances.

    Methods:
        __init__(**data): Initialize the BaseValue and register it in the class registry.
        get(cls, uuid: UUID) -> Optional['BaseValue']:
            Retrieve a BaseValue instance from the registry by its UUID.
        register(cls, value: 'BaseValue') -> None:
            Register a BaseValue instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseValue instance from the class registry.
        get_generation_chain(self) -> List['BaseValue']:
            Get the chain of values that this value was generated from.
        validate_source_id(self, source_id: UUID) -> None:
            Validate that the given source_id matches the source_entity_uuid of this value.
        validate_target_id(self, target_id: UUID) -> None:
            Validate that the given target_id matches the target_entity_uuid of this value.
    """

    _registry: ClassVar[Dict[UUID, 'BaseValue']] = {}

    name: str = Field(
        default="A Value",
        description="The name of the value. Defaults to 'A Value' if not specified."
    )
    uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the value. Automatically generated if not provided."
    )
    source_entity_uuid: UUID = Field(
        ...,  # This makes the field required
        description="UUID of the entity that is the source of this value. Must be provided explicitly."
    )
    source_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that is the source of this value. Can be None."
    )
    target_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the entity that this value targets, if any. Can be None."
    )
    target_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that this value targets, if any. Can be None."
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context information for this value. Can be None."
    )
    score_normalizer: Callable[[int], int] = Field(
        default=identity,
        description="A function to normalize the score. Defaults to identity function."
    )
    generated_from: List[UUID] = Field(
        default_factory=list,
        description="List of UUIDs of values that this value was generated from."
    )
    global_normalizer: bool = Field(
        default=True,
        description="Whether to apply the value's normalizer globally to all numerical modifiers"
    )


    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseValue']:
        """
        Retrieve a BaseValue instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the value to retrieve.

        Returns:
            Optional[BaseValue]: The BaseValue instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a BaseValue instance.
        """
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, BaseValue):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a BaseValue, but {type(value)}")

    
    def validate_modifier_target(self, modifier: Union[NumericalModifier, AdvantageModifier, CriticalModifier, AutoHitModifier, SizeModifier, DamageTypeModifier, ResistanceModifier, ContextualNumericalModifier, ContextualAdvantageModifier, ContextualCriticalModifier, ContextualAutoHitModifier, ContextualSizeModifier, ContextualDamageTypeModifier, ContextualResistanceModifier]) -> None:
        pass

    def get_generation_chain(self) -> List['BaseValue']:
        chain = []
        visited = set()
        def dfs(value):
            if value.uuid in visited:
                return
            visited.add(value.uuid)
            for uuid in value.generated_from:
                generated_value = self.get(uuid)
                if generated_value and generated_value.uuid not in visited:
                    chain.append(generated_value)
                    dfs(generated_value)
        dfs(self)
        return chain

    

class StaticValue(BaseValue):
    """
    A value type that represents a static (non-contextual) value with various modifiers.

    This class extends BaseValue to include static modifiers for numerical values,
    constraints, advantage, critical hits, auto-hits, size, damage type, and resistance.

    Attributes:
        name (str): The name of the value.
        uuid (UUID): Unique identifier for the value.
        source_entity_name (str): Name of the entity that is the source of this value.
        source_entity_uuid (UUID): UUID of the entity that is the source of this value. Must be provided explicitly.
        target_entity_uuid (Optional[UUID]): UUID of the entity that this value targets, if any.
        target_entity_name (Optional[str]): Name of the entity that this value targets, if any.
        context (Optional[Dict[str, Any]]): Additional context information for this value.
        score_normalizer (Callable[[int], int]): A function to normalize the score.
        generated_from (List[UUID]): List of UUIDs of values that this value was generated from.
        value_modifiers (Dict[UUID, NumericalModifier]): Dictionary of numerical modifiers applied to this value.
        min_constraints (Dict[UUID, NumericalModifier]): Dictionary of minimum value constraints.
        max_constraints (Dict[UUID, NumericalModifier]): Dictionary of maximum value constraints.
        advantage_modifiers (Dict[UUID, AdvantageModifier]): Dictionary of advantage modifiers.
        critical_modifiers (Dict[UUID, CriticalModifier]): Dictionary of critical hit modifiers.
        auto_hit_modifiers (Dict[UUID, AutoHitModifier]): Dictionary of auto-hit modifiers.
        is_outgoing_modifier (bool): Flag to indicate if this value represents outgoing modifiers (to others).
        size_modifiers (Dict[UUID, SizeModifier]): Dictionary of size modifiers.
        damage_type_modifiers (Dict[UUID, DamageTypeModifier]): Dictionary of damage type modifiers.
        resistance_modifiers (Dict[UUID, ResistanceModifier]): Dictionary of resistance modifiers.
        largest_size_priority (bool): Flag to indicate whether the largest size (True) or smallest size (False) has precedence.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseValue']]): A class-level registry to store all instances.

    Computed Attributes:
        min (Optional[int]): The minimum value based on all min constraints.
        max (Optional[int]): The maximum value based on all max constraints.
        score (int): The final calculated score, considering all modifiers and constraints.
        normalized_score (int): The score after applying the score normalizer function.
        advantage_sum (int): The sum of all advantage modifiers.
        advantage (AdvantageStatus): The final advantage status based on all advantage modifiers.
        critical (CriticalStatus): The final critical status based on all critical modifiers.
        auto_hit (AutoHitStatus): The final auto-hit status based on all auto-hit modifiers.
        size (Size): The final size based on all size modifiers.
        damage_types (List[DamageType]): The list of damage types with the highest occurrence.
        damage_type (Optional[DamageType]): A randomly selected damage type from the most common types.
        resistance_sum (Dict[DamageType, int]): The sum of resistance values for each damage type.
        resistance (Dict[DamageType, ResistanceStatus]): The final resistance status for each damage type.

    Methods:
        get(cls, uuid: UUID) -> Optional['StaticValue']:
            Retrieve a StaticValue instance from the registry by its UUID.
        combine_values(self, others: List['StaticValue'], naming_callable: Optional[naming_callable] = None) -> 'StaticValue':
            Combine this StaticValue with a list of other StaticValues.
        add_size_modifier(self, modifier: SizeModifier) -> UUID:
            Add a size modifier to this value.
        remove_size_modifier(self, uuid: UUID) -> None:
            Remove a size modifier from this value.
        add_damage_type_modifier(self, modifier: DamageTypeModifier) -> UUID:
            Add a damage type modifier to this value.
        remove_damage_type_modifier(self, uuid: UUID) -> None:
            Remove a damage type modifier from this value.
        add_resistance_modifier(self, modifier: ResistanceModifier) -> UUID:
            Add a resistance modifier to this value.
        remove_resistance_modifier(self, uuid: UUID) -> None:
            Remove a resistance modifier from this value.

    Validators:
        validate_value_source_corresponds_to_modifiers_target: Ensures that the source and target UUIDs are consistent
        with the is_outgoing_modifier flag.
    """

    value_modifiers: Dict[UUID, NumericalModifier] = Field(
        default_factory=dict,
        description="Dictionary of numerical modifiers applied to this value."
    )
    min_constraints: Dict[UUID, NumericalModifier] = Field(
        default_factory=dict,
        description="Dictionary of minimum value constraints."
    )
    max_constraints: Dict[UUID, NumericalModifier] = Field(
        default_factory=dict,
        description="Dictionary of maximum value constraints."
    )
    advantage_modifiers: Dict[UUID, AdvantageModifier] = Field(
        default_factory=dict,
        description="Dictionary of advantage modifiers."
    )
    critical_modifiers: Dict[UUID, CriticalModifier] = Field(
        default_factory=dict,
        description="Dictionary of critical hit modifiers."
    )
    auto_hit_modifiers: Dict[UUID, AutoHitModifier] = Field(
        default_factory=dict,
        description="Dictionary of auto-hit modifiers."
    )
    is_outgoing_modifier: bool = Field(
        default=False,
        description="Flag to indicate if this value represents outgoing modifiers (to others)."
    )
    size_modifiers: Dict[UUID, SizeModifier] = Field(
        default_factory=dict,
        description="Dictionary of size modifiers."
    )
    damage_type_modifiers: Dict[UUID, DamageTypeModifier] = Field(
        default_factory=dict,
        description="Dictionary of damage type modifiers."
    )
    resistance_modifiers: Dict[UUID, ResistanceModifier] = Field(
        default_factory=dict,
        description="Dictionary of resistance modifiers."
    )
    largest_size_priority: bool = Field(
        default=True,
        description="Flag to indicate whether the largest size (True) or smallest size (False) has precedence."
    )

    @model_validator(mode="after")
    def validate_value_source_corresponds_to_modifiers_target(self) -> Self:
        for modifier in list(self.value_modifiers.values()) + list(self.min_constraints.values()) + list(self.max_constraints.values()):
            if self.is_outgoing_modifier:
                if modifier.target_entity_uuid == self.source_entity_uuid:
                    raise ValueError(f"Outgoing modifier target ({modifier.target_entity_uuid}) should not be the same as the value source ({self.source_entity_uuid})")
           
        return self

    @classmethod
    def get(cls, uuid: UUID) -> 'StaticValue':
        value = cls._registry.get(uuid)
        if not isinstance(value, StaticValue):
            raise ValueError(f"Value with UUID {uuid} is not a StaticValue, but {type(value)}")
        return value

    def add_value_modifier(self, modifier: NumericalModifier) -> UUID:
        """
        Add a numerical modifier to this value.

        Args:
            modifier (NumericalModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.value_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_value_modifier(self, uuid: UUID) -> None:
        """
        Remove a numerical modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.value_modifiers.pop(uuid, None)

    def add_min_constraint(self, constraint: NumericalModifier) -> UUID:
        """
        Add a minimum constraint to this value.

        Args:
            constraint (NumericalModifier): The constraint to add.

        Returns:
            UUID: The UUID of the added constraint.
        """
        self.min_constraints[constraint.uuid] = constraint
        return constraint.uuid
    
    def remove_min_constraint(self, uuid: UUID) -> None:
        """
        Remove a minimum constraint from this value.

        Args:
            uuid (UUID): The UUID of the constraint to remove.
        """
        self.min_constraints.pop(uuid, None)

    def add_max_constraint(self, constraint: NumericalModifier) -> UUID:
        """
        Add a maximum constraint to this value.

        Args:
            constraint (NumericalModifier): The constraint to add.

        Returns:
            UUID: The UUID of the added constraint.
        """
        self.max_constraints[constraint.uuid] = constraint
        return constraint.uuid
    
    def remove_max_constraint(self, uuid: UUID) -> None:
        """
        Remove a maximum constraint from this value.

        Args:
            uuid (UUID): The UUID of the constraint to remove.
        """
        self.max_constraints.pop(uuid, None)
    
    def add_advantage_modifier(self, modifier: AdvantageModifier) -> UUID:
        """
        Add an advantage modifier to this value.

        Args:
            modifier (AdvantageModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.advantage_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_advantage_modifier(self, uuid: UUID) -> None:
        """
        Remove an advantage modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.advantage_modifiers.pop(uuid, None)
    
    def add_critical_modifier(self, modifier: CriticalModifier) -> UUID:
        """
        Add a critical modifier to this value.

        Args:
            modifier (CriticalModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.critical_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_critical_modifier(self, uuid: UUID) -> None:
        """
        Remove a critical modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.critical_modifiers.pop(uuid, None)
    
    def add_auto_hit_modifier(self, modifier: AutoHitModifier) -> UUID:
        """
        Add an auto-hit modifier to this value.

        Args:
            modifier (AutoHitModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.auto_hit_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_auto_hit_modifier(self, uuid: UUID) -> None:
        """
        Remove an auto-hit modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.auto_hit_modifiers.pop(uuid, None)

    def add_size_modifier(self, modifier: SizeModifier) -> UUID:
        """
        Add a size modifier to this value.

        Args:
            modifier (SizeModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.size_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_size_modifier(self, uuid: UUID) -> None:
        """
        Remove a size modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.size_modifiers.pop(uuid, None)

    def add_damage_type_modifier(self, modifier: DamageTypeModifier) -> UUID:
        """
        Add a damage type modifier to this value.

        Args:
            modifier (DamageTypeModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.damage_type_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_damage_type_modifier(self, uuid: UUID) -> None:
        """
        Remove a damage type modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.damage_type_modifiers.pop(uuid, None)

    def add_resistance_modifier(self, modifier: ResistanceModifier) -> UUID:
        """
        Add a resistance modifier to this value.

        Args:
            modifier (ResistanceModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.resistance_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_resistance_modifier(self, uuid: UUID) -> None:
        """
        Remove a resistance modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.resistance_modifiers.pop(uuid, None)

    def remove_modifier(self, uuid: UUID) -> None:
        """
        Remove a modifier from all modifier dictionaries of this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.remove_value_modifier(uuid)
        self.remove_min_constraint(uuid)
        self.remove_max_constraint(uuid)
        self.remove_advantage_modifier(uuid)
        self.remove_critical_modifier(uuid)
        self.remove_auto_hit_modifier(uuid)
        self.remove_size_modifier(uuid)
        self.remove_damage_type_modifier(uuid)
        self.remove_resistance_modifier(uuid)

    @computed_field
    @property
    def min(self) -> Optional[int]:
        """
        Calculate the minimum value based on all min constraints.

        Returns:
            Optional[int]: The minimum value if constraints exist, None otherwise.
        """
        if not self.min_constraints:
            return None
        return min(constraint.value for constraint in self.min_constraints.values())
    
    @computed_field
    @property
    def max(self) -> Optional[int]:
        """
        Calculate the maximum value based on all max constraints.

        Returns:
            Optional[int]: The maximum value if constraints exist, None otherwise.
        """
        if not self.max_constraints:
            return None
        return max(constraint.value for constraint in self.max_constraints.values())
    def _score(self,normalized=False) -> int:
        """
        Calculate the final score of the value, considering all modifiers and constraints.

        Returns:
            int: The final calculated score.
        """
        modifier_sum = sum(modifier.value if not normalized else modifier.normalized_value for modifier in self.value_modifiers.values())
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
    def score(self) -> int:
        """
        Calculate the final score of the value, considering all modifiers and constraints.

        Returns:
            int: The final calculated score.
        """
        return self._score()
        
    
    
    @computed_field
    @property
    def normalized_score(self) -> int:
        """
        Apply the score normalizer function to the calculated score.

        Returns:
            int: The normalized score.
        """
        return self._score(normalized=True)
    
    @computed_field
    @property
    def advantage_sum(self) -> int:
        """
        Calculate the sum of all advantage modifiers.

        Returns:
            int: The total advantage sum.
        """
        return sum(modifier.numerical_value for modifier in self.advantage_modifiers.values())
    
    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """
        Determine the final advantage status based on all advantage modifiers.

        Returns:
            AdvantageStatus: The final advantage status (ADVANTAGE, DISADVANTAGE, or NONE).
        """
        if self.advantage_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif self.advantage_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE
        
    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """
        Determine the final critical status based on all critical modifiers.

        Returns:
            CriticalStatus: The final critical status (NOCRIT, AUTOCRIT, or NONE).
        """
        if CriticalStatus.NOCRIT in (mod.value for mod in self.critical_modifiers.values()):
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in (mod.value for mod in self.critical_modifiers.values()):
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE
        
    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """
        Determine the final auto-hit status based on all auto-hit modifiers.

        Returns:
            AutoHitStatus: The final auto-hit status (AUTOMISS, AUTOHIT, or NONE).
        """
        if AutoHitStatus.AUTOMISS in (mod.value for mod in self.auto_hit_modifiers.values()):
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in (mod.value for mod in self.auto_hit_modifiers.values()):
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE
        
    @computed_field
    @property
    def size(self) -> Size:
        """
        Determine the final size based on all size modifiers.

        Returns:
            Size: The final size.
        """
        if not self.size_modifiers:
            return Size.MEDIUM  # Default size if no modifiers

        sizes = [modifier.value for modifier in self.size_modifiers.values()]
        if self.largest_size_priority:
            return max(sizes, key=lambda s: list(Size).index(s))
        else:
            return min(sizes, key=lambda s: list(Size).index(s))

    @computed_field
    @property
    def damage_types(self) -> List[DamageType]:
        """
        Determine the list of damage types based on damage type modifiers.

        Returns:
            List[DamageType]: The list of damage types with the highest occurrence.
        """
        if not self.damage_type_modifiers:
            return []
        
        type_counts = {}
        for modifier in self.damage_type_modifiers.values():
            type_counts[modifier.value] = type_counts.get(modifier.value, 0) + 1
        
        max_count = max(type_counts.values())
        if max_count == 0:
            return []
        most_common_types = [dt for dt, count in type_counts.items() if count == max_count]
        
        return most_common_types

    @computed_field
    @property
    def damage_type(self) -> Optional[DamageType]:
        """
        Determine a single damage type based on damage type modifiers.

        Returns:
            Optional[DamageType]: A randomly selected damage type from the most common types, or None if no modifiers.
        """
        most_common_types = self.damage_types
        if not most_common_types:
            return None
        return random.choice(most_common_types)

    @computed_field
    @property
    def resistance_sum(self) -> Dict[DamageType, int]:
        """
        Calculate the sum of resistance values for each damage type.

        Returns:
            Dict[DamageType, int]: A dictionary with damage types as keys and summed resistance values as values.
        """
        resistance_sum = {damage_type: 0 for damage_type in DamageType}
        for modifier in self.resistance_modifiers.values():
            resistance_sum[modifier.damage_type] += modifier.numerical_value
        return resistance_sum

    @computed_field
    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """
        Determine the final resistance status for each damage type based on the resistance sum.

        Returns:
            Dict[DamageType, ResistanceStatus]: A dictionary with damage types as keys and final resistance statuses as values.
        """
        resistance = {}
        for damage_type, sum_value in self.resistance_sum.items():
            if sum_value > 1:
                resistance[damage_type] = ResistanceStatus.IMMUNITY
            elif sum_value == 1:
                resistance[damage_type] = ResistanceStatus.RESISTANCE
            elif sum_value == 0:
                resistance[damage_type] = ResistanceStatus.NONE
            else:  # sum_value < 0
                resistance[damage_type] = ResistanceStatus.VULNERABILITY
        return resistance

    def combine_values(self, others: List['StaticValue'], naming_callable: Optional[naming_callable] = None) -> 'StaticValue':
        """
        Combine this StaticValue with a list of other StaticValues.

        Args:
            others (List[StaticValue]): List of other StaticValue instances to combine with.
            naming_callable (Optional[Callable[[List[str]], str]]): A function to generate the name of the combined value.

        Returns:
            StaticValue: A new StaticValue instance that combines all the input values.

        Raises:
            ValueError: If any of the other values have a different source entity UUID.
        """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)
        
        for other in others:
            self.validate_source_id(other.source_entity_uuid)
        
        return StaticValue(
            name=naming_callable([self.name] + [other.name for other in others]),
            value_modifiers={**self.value_modifiers, **{k: v for other in others for k, v in other.value_modifiers.items()}},
            min_constraints={**self.min_constraints, **{k: v for other in others for k, v in other.min_constraints.items()}},
            max_constraints={**self.max_constraints, **{k: v for other in others for k, v in other.max_constraints.items()}},
            advantage_modifiers={**self.advantage_modifiers, **{k: v for other in others for k, v in other.advantage_modifiers.items()}},
            critical_modifiers={**self.critical_modifiers, **{k: v for other in others for k, v in other.critical_modifiers.items()}},
            auto_hit_modifiers={**self.auto_hit_modifiers, **{k: v for other in others for k, v in other.auto_hit_modifiers.items()}},
            size_modifiers={**self.size_modifiers, **{k: v for other in others for k, v in other.size_modifiers.items()}},
            damage_type_modifiers={**self.damage_type_modifiers, **{k: v for other in others for k, v in other.damage_type_modifiers.items()}},
            resistance_modifiers={**self.resistance_modifiers, **{k: v for other in others for k, v in other.resistance_modifiers.items()}},
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            score_normalizer=self.score_normalizer,
            is_outgoing_modifier=self.is_outgoing_modifier,
            global_normalizer=False
        )

    def get_all_modifier_uuids(self) -> List[UUID]:
        """
        Get a list of UUIDs for all modifiers in this StaticValue.

        Returns:
            List[UUID]: A list of all modifier UUIDs.
        """
        return (list(self.value_modifiers.keys()) +
                list(self.min_constraints.keys()) +
                list(self.max_constraints.keys()) +
                list(self.advantage_modifiers.keys()) +
                list(self.critical_modifiers.keys()) +
                list(self.auto_hit_modifiers.keys()) +
                list(self.size_modifiers.keys()) +
                list(self.damage_type_modifiers.keys()) +
                list(self.resistance_modifiers.keys()))

    def remove_all_modifiers(self) -> None:
        """
        Remove all modifiers from this StaticValue.
        """
        self.value_modifiers.clear()
        self.min_constraints.clear()
        self.max_constraints.clear()
        self.advantage_modifiers.clear()
        self.critical_modifiers.clear()
        self.auto_hit_modifiers.clear()
        self.size_modifiers.clear()
        self.damage_type_modifiers.clear()
        self.resistance_modifiers.clear()

    def _set_normalizer_recursive(self, normalizer: Callable[[int], int]) -> None:
        """
        Recursively set the score normalizer for this value and all its components.
        
        Args:
            normalizer (Callable[[int], int]): The normalizer function to apply.
        """
        self.score_normalizer = normalizer
        
        # Apply to value modifiers
        for modifier in self.value_modifiers.values():
            modifier.score_normalizer = normalizer
        
        # Apply to min/max constraints if needed
        # for constraint in self.min_constraints.values():
        #     constraint.score_normalizer = normalizer
        # for constraint in self.max_constraints.values():
        #     constraint.score_normalizer = normalizer

    @model_validator(mode='after')
    def apply_global_normalizer(self) -> Self:
        """
        Apply the score normalizer to all numerical modifiers if global_normalizer is True.
        Only affects modifiers that don't already have a normalizer.
        """
        if self.global_normalizer and self.score_normalizer is not None:
            self._set_normalizer_recursive(self.score_normalizer)
        return self

class ContextualValue(BaseValue):
    """
    A value type that represents a context-dependent value with various modifiers.

    This class extends BaseValue to include contextual modifiers for numerical values,
    constraints, advantage, critical hits, auto-hits, size, damage type, and resistance.

    Attributes:
        name (str): The name of the value.
        uuid (UUID): Unique identifier for the value.
        source_entity_uuid (UUID): UUID of the entity that is the source of this value.
        source_entity_name (Optional[str]): Name of the entity that is the source of this value.
        target_entity_uuid (Optional[UUID]): UUID of the entity that this value targets, if any.
        target_entity_name (Optional[str]): Name of the entity that this value targets, if any.
        context (Optional[Dict[str, Any]]): Additional context information for this value.
        score_normalizer (Callable[[int], int]): A function to normalize the score.
        generated_from (List[UUID]): List of UUIDs of values that this value was generated from.
        value_modifiers (Dict[UUID, ContextualNumericalModifier]): Dictionary of contextual numerical modifiers.
        min_constraints (Dict[UUID, ContextualNumericalModifier]): Dictionary of contextual minimum value constraints.
        max_constraints (Dict[UUID, ContextualNumericalModifier]): Dictionary of contextual maximum value constraints.
        advantage_modifiers (Dict[UUID, ContextualAdvantageModifier]): Dictionary of contextual advantage modifiers.
        critical_modifiers (Dict[UUID, ContextualCriticalModifier]): Dictionary of contextual critical hit modifiers.
        auto_hit_modifiers (Dict[UUID, ContextualAutoHitModifier]): Dictionary of contextual auto-hit modifiers.
        is_outgoing_modifier (bool): Flag to indicate if this value represents outgoing modifiers (to others).
        size_modifiers (Dict[UUID, ContextualSizeModifier]): Dictionary of contextual size modifiers.
        damage_type_modifiers (Dict[UUID, ContextualDamageTypeModifier]): Dictionary of contextual damage type modifiers.
        resistance_modifiers (Dict[UUID, ContextualResistanceModifier]): Dictionary of contextual resistance modifiers.
        largest_size_priority (bool): Flag to indicate whether the largest size (True) or smallest size (False) has precedence.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseValue']]): A class-level registry to store all instances.

    Computed Attributes:
        min (Optional[int]): The minimum value based on all contextual min constraints.
        max (Optional[int]): The maximum value based on all contextual max constraints.
        score (int): The final calculated score, considering all contextual modifiers and constraints.
        normalized_score (int): The score after applying the score normalizer function.
        advantage_sum (int): The sum of all contextual advantage modifiers.
        advantage (AdvantageStatus): The final advantage status based on all contextual advantage modifiers.
        critical (CriticalStatus): The final critical status based on all contextual critical modifiers.
        auto_hit (AutoHitStatus): The final auto-hit status based on all contextual auto-hit modifiers.
        size (Size): The final size based on all contextual size modifiers.
        damage_types (List[DamageType]): The list of all damage types based on contextual damage type modifiers.
        damage_type (Optional[DamageType]): A randomly selected damage type from the most common types.
        resistance_sum (Dict[DamageType, int]): The sum of resistance values for each damage type.
        resistance (Dict[DamageType, ResistanceStatus]): The final resistance status for each damage type.

    Methods:
        get(cls, uuid: UUID) -> Optional['ContextualValue']:
            Retrieve a ContextualValue instance from the registry by its UUID.
        set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None:
            Set the target entity for this contextual value.
        clear_target_entity(self) -> None:
            Clear the target entity information for this contextual value.
        set_context(self, context: Dict[str,Any]) -> None:
            Set the context for this contextual value.
        clear_context(self) -> None:
            Clear the context for this contextual value.
        add_value_modifier(self, modifier: ContextualNumericalModifier) -> UUID:
            Add a contextual numerical modifier to this value.
        remove_value_modifier(self, uuid: UUID) -> None:
            Remove a contextual numerical modifier from this value.
        add_min_constraint(self, constraint: ContextualNumericalModifier) -> UUID:
            Add a contextual minimum constraint to this value.
        remove_min_constraint(self, uuid: UUID) -> None:
            Remove a contextual minimum constraint from this value.
        add_max_constraint(self, constraint: ContextualNumericalModifier) -> UUID:
            Add a contextual maximum constraint to this value.
        remove_max_constraint(self, uuid: UUID) -> None:
            Remove a contextual maximum constraint from this value.
        add_advantage_modifier(self, modifier: ContextualAdvantageModifier) -> UUID:
            Add a contextual advantage modifier to this value.
        remove_advantage_modifier(self, uuid: UUID) -> None:
            Remove a contextual advantage modifier from this value.
        add_critical_modifier(self, modifier: ContextualCriticalModifier) -> UUID:
            Add a contextual critical modifier to this value.
        remove_critical_modifier(self, uuid: UUID) -> None:
            Remove a contextual critical modifier from this value.
        add_auto_hit_modifier(self, modifier: ContextualAutoHitModifier) -> UUID:
            Add a contextual auto-hit modifier to this value.
        remove_auto_hit_modifier(self, uuid: UUID) -> None:
            Remove a contextual auto-hit modifier from this value.
        add_size_modifier(self, modifier: ContextualSizeModifier) -> UUID:
            Add a contextual size modifier to this value.
        remove_size_modifier(self, uuid: UUID) -> None:
            Remove a contextual size modifier from this value.
        add_damage_type_modifier(self, modifier: ContextualDamageTypeModifier) -> UUID:
            Add a contextual damage type modifier to this value.
        remove_damage_type_modifier(self, uuid: UUID) -> None:
            Remove a contextual damage type modifier from this value.
        add_resistance_modifier(self, modifier: ContextualResistanceModifier) -> UUID:
            Add a contextual resistance modifier to this value.
        remove_resistance_modifier(self, uuid: UUID) -> None:
            Remove a contextual resistance modifier from this value.
        remove_modifier(self, uuid: UUID) -> None:
            Remove a modifier from all modifier dictionaries of this value.
        combine_values(self, others: List['ContextualValue'], naming_callable: Optional[naming_callable] = None) -> 'ContextualValue':
            Combine this ContextualValue with a list of other ContextualValues.
        get_all_modifier_uuids(self) -> List[UUID]:
            Get a list of UUIDs for all modifiers in this ContextualValue.
        remove_all_modifiers(self) -> None:
            Remove all modifiers from this ContextualValue.

    Validators:
        validate_value_source_corresponds_to_modifiers_target: Ensures that the source and target UUIDs are consistent
        with the is_outgoing_modifier flag.
    """

    value_modifiers: Dict[UUID, ContextualNumericalModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual numerical modifiers, keyed by UUID."
    )
    min_constraints: Dict[UUID, ContextualNumericalModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual minimum value constraints, keyed by UUID."
    )
    max_constraints: Dict[UUID, ContextualNumericalModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual maximum value constraints, keyed by UUID."
    )
    advantage_modifiers: Dict[UUID, ContextualAdvantageModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual advantage modifiers, keyed by UUID."
    )
    critical_modifiers: Dict[UUID, ContextualCriticalModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual critical hit modifiers, keyed by UUID."
    )
    auto_hit_modifiers: Dict[UUID, ContextualAutoHitModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual auto-hit modifiers, keyed by UUID."
    )
    is_outgoing_modifier: bool = Field(
        default=False,
        description="Flag to indicate if this value represents outgoing modifiers (to others)."
    )
    size_modifiers: Dict[UUID, ContextualSizeModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual size modifiers."
    )
    damage_type_modifiers: Dict[UUID, ContextualDamageTypeModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual damage type modifiers."
    )
    resistance_modifiers: Dict[UUID, ContextualResistanceModifier] = Field(
        default_factory=dict,
        description="Dictionary of contextual resistance modifiers."
    )
    largest_size_priority: bool = Field(
        default=True,
        description="Flag to indicate whether the largest size (True) or smallest size (False) has precedence."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualValue']:
        """
        Retrieve a ContextualValue instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the value to retrieve.

        Returns:
            Optional[ContextualValue]: The ContextualValue instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualValue instance.
        """
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
        """
        Calculate the minimum value based on all contextual min constraints.

        Returns:
            Optional[int]: The minimum value if constraints exist, None otherwise.
        """
        if not self.min_constraints:
            return None
        return min(constraint.callable(self.source_entity_uuid, self.target_entity_uuid, self.context).value 
                   for constraint in self.min_constraints.values())
    
    @computed_field
    @property
    def max(self) -> Optional[int]:
        """
        Calculate the maximum value based on all contextual max constraints.

        Returns:
            Optional[int]: The maximum value if constraints exist, None otherwise.
        """
        if not self.max_constraints:
            return None
        return max(constraint.callable(self.source_entity_uuid, self.target_entity_uuid, self.context).value 
                   for constraint in self.max_constraints.values())

    def _score(self,normalized=False) -> int:
        """
        Calculate the final score of the value, considering all contextual modifiers and constraints.

        Returns:
            int: The final calculated score.
        """
        modifier_sum = 0
        for context_aware_modifier in self.value_modifiers.values():
            try:
                result = context_aware_modifier.callable(self.source_entity_uuid, self.target_entity_uuid, self.context)
                if not isinstance(result, NumericalModifier):
                    raise ValueError(f"Callable returned unexpected type. Expected NumericalModifier, got {type(result)}")
                modifier_sum += result.value if not normalized else result.normalized_value
            except Exception as e:
                raise ValueError(f"Error calculating score: {str(e)}")
        
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
    def score(self) -> int:
        """
        Calculate the final score of the value, considering all contextual modifiers and constraints.

        Returns:
            int: The final calculated score.
        """
        return self._score()


    @computed_field
    @property
    def normalized_score(self) -> int:
        """
        Apply the score normalizer function to the calculated score.

        Returns:
            int: The normalized score.
        """
        return self._score(normalized=True)
    
    @computed_field
    @property
    def advantage_sum(self) -> int:
        """
        Calculate the sum of all contextual advantage modifiers.

        Returns:
            int: The total advantage sum.
        """
        return sum(modifier.callable(self.source_entity_uuid, self.target_entity_uuid, self.context).numerical_value 
                   for modifier in self.advantage_modifiers.values())

    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """
        Determine the final advantage status based on all contextual advantage modifiers.

        Returns:
            AdvantageStatus: The final advantage status (ADVANTAGE, DISADVANTAGE, or NONE).
        """
        if self.advantage_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif self.advantage_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE
        
    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """
        Determine the final critical status based on all contextual critical modifiers.

        Returns:
            CriticalStatus: The final critical status (NOCRIT, AUTOCRIT, or NONE).
        """
        critical_modifiers = [modifier.callable(self.source_entity_uuid, self.target_entity_uuid, self.context) 
                              for modifier in self.critical_modifiers.values()]
        if CriticalStatus.NOCRIT in (mod.value for mod in critical_modifiers):
            return CriticalStatus.NOCRIT
        elif CriticalStatus.AUTOCRIT in (mod.value for mod in critical_modifiers):
            return CriticalStatus.AUTOCRIT
        else:
            return CriticalStatus.NONE
        
    @computed_field
    @property
    def auto_hit(self) -> AutoHitStatus:
        """
        Determine the final auto-hit status based on all contextual auto-hit modifiers.

        Returns:
            AutoHitStatus: The final auto-hit status (AUTOMISS, AUTOHIT, or NONE).
        """
        auto_hit_modifiers = [modifier.callable(self.source_entity_uuid, self.target_entity_uuid, self.context) 
                              for modifier in self.auto_hit_modifiers.values()]
        if AutoHitStatus.AUTOMISS in (mod.value for mod in auto_hit_modifiers):
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in (mod.value for mod in auto_hit_modifiers):
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE
    
    @computed_field
    @property
    def size(self) -> Size:
        """
        Determine the final size based on all contextual size modifiers.

        Returns:
            Size: The final size.
        """
        if not self.size_modifiers:
            return Size.MEDIUM  # Default size if no modifiers
        size_modifiers = [modifier.callable(self.source_entity_uuid, self.target_entity_uuid, self.context) 
                          for modifier in self.size_modifiers.values()]
        sizes = [modifier.value for modifier in size_modifiers]
        if self.largest_size_priority:
            return max(sizes, key=lambda s: list(Size).index(s))
        else:
            return min(sizes, key=lambda s: list(Size).index(s))
        

    @computed_field
    @property
    def damage_types(self) -> List[DamageType]:
        """
        Determine the list of damage types based on contextual damage type modifiers.

        Returns:
            List[DamageType]: The list of damage types with the highest occurrence.
        """
        if not self.damage_type_modifiers:
            return []
        
        type_counts = {}
        for modifier in self.damage_type_modifiers.values():
            result = modifier.callable(self.source_entity_uuid, self.target_entity_uuid, self.context)
            type_counts[result.value] = type_counts.get(result.value, 0) + 1
        
        max_count = max(type_counts.values())
        most_common_types = [dt for dt, count in type_counts.items() if count == max_count]
        
        return most_common_types

    @computed_field
    @property
    def damage_type(self) -> Optional[DamageType]:
        """
        Determine a single damage type based on contextual damage type modifiers.

        Returns:
            Optional[DamageType]: A randomly selected damage type from the most common types, or None if no modifiers.
        """
        most_common_types = self.damage_types
        if not most_common_types:
            return None
        return random.choice(most_common_types)

    @computed_field
    @property
    def resistance_sum(self) -> Dict[DamageType, int]:
        """
        Calculate the sum of resistance values for each damage type based on contextual modifiers.

        Returns:
            Dict[DamageType, int]: A dictionary with damage types as keys and summed resistance values as values.
        """
        resistance_sum = {damage_type: 0 for damage_type in DamageType}
        for modifier in self.resistance_modifiers.values():
            result = modifier.callable(self.source_entity_uuid, self.target_entity_uuid, self.context)
            resistance_sum[result.damage_type] += result.numerical_value
        return resistance_sum

    @computed_field
    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """
        Determine the final resistance status for each damage type based on the resistance sum.

        Returns:
            Dict[DamageType, ResistanceStatus]: A dictionary with damage types as keys and final resistance statuses as values.
        """
        resistance = {}
        for damage_type, sum_value in self.resistance_sum.items():
            if sum_value > 1:
                resistance[damage_type] = ResistanceStatus.IMMUNITY
            elif sum_value == 1:
                resistance[damage_type] = ResistanceStatus.RESISTANCE
            elif sum_value == 0:
                resistance[damage_type] = ResistanceStatus.NONE
            else:  # sum_value < 0
                resistance[damage_type] = ResistanceStatus.VULNERABILITY
        return resistance

    def add_value_modifier(self, modifier: ContextualNumericalModifier) -> UUID:
        """
        Add a contextual numerical modifier to this value.

        Args:
            modifier (ContextualNumericalModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        uuid = modifier.uuid
        self.value_modifiers[uuid] = modifier
        return uuid
    
    def remove_value_modifier(self, uuid: UUID) -> None:
        """
        Remove a contextual numerical modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        if uuid in self.value_modifiers:
            del self.value_modifiers[uuid]

    def add_min_constraint(self, constraint: ContextualNumericalModifier) -> UUID:
        """
        Add a contextual minimum constraint to this value.

        Args:
            constraint (ContextualNumericalModifier): The constraint to add.

        Returns:
            UUID: The UUID of the added constraint.
        """
        uuid = constraint.uuid
        self.min_constraints[uuid] = constraint
        return uuid
    
    def remove_min_constraint(self, uuid: UUID) -> None:
        """
        Remove a contextual minimum constraint from this value.

        Args:
            uuid (UUID): The UUID of the constraint to remove.
        """

        if uuid in self.min_constraints:
            del self.min_constraints[uuid]

    def add_max_constraint(self, constraint: ContextualNumericalModifier) -> UUID:
        """
        Add a contextual maximum constraint to this value.

        Args:
            constraint (ContextualNumericalModifier): The constraint to add.

        Returns:
            UUID: The UUID of the added constraint.
        """
        uuid = constraint.uuid
        self.max_constraints[uuid] = constraint
        return uuid
    
    def remove_max_constraint(self, uuid: UUID) -> None:
        """
        Remove a contextual maximum constraint from this value.

        Args:
            uuid (UUID): The UUID of the constraint to remove.
        """
        if uuid in self.max_constraints:
            del self.max_constraints[uuid]
    
    def add_advantage_modifier(self, modifier: ContextualAdvantageModifier) -> UUID:
        """
        Add a contextual advantage modifier to this value.

        Args:
            modifier (ContextualAdvantageModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        uuid = modifier.uuid
        self.advantage_modifiers[uuid] = modifier
        return uuid
    
    def remove_advantage_modifier(self, uuid: UUID) -> None:
        """
        Remove a contextual advantage modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        if uuid in self.advantage_modifiers:
            del self.advantage_modifiers[uuid]
    
    def add_critical_modifier(self, modifier: ContextualCriticalModifier) -> UUID:
        """
        Add a contextual critical modifier to this value.

        Args:
            modifier (ContextualCriticalModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        uuid = modifier.uuid
        self.critical_modifiers[uuid] = modifier
        return uuid
    
    def remove_critical_modifier(self, uuid: UUID) -> None:
        """
        Remove a contextual critical modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        if uuid in self.critical_modifiers:
            del self.critical_modifiers[uuid]
    
    def add_auto_hit_modifier(self, modifier: ContextualAutoHitModifier) -> UUID:
        """
        Add a contextual auto-hit modifier to this value.

        Args:
            modifier (ContextualAutoHitModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        uuid = modifier.uuid
        self.auto_hit_modifiers[uuid] = modifier
        return uuid
    
    def remove_auto_hit_modifier(self, uuid: UUID) -> None:
        """
        Remove a contextual auto-hit modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        if uuid in self.auto_hit_modifiers:
            del self.auto_hit_modifiers[uuid]

    def add_size_modifier(self, modifier: ContextualSizeModifier) -> UUID:
        """
        Add a contextual size modifier to this value.

        Args:
            modifier (ContextualSizeModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.size_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_size_modifier(self, uuid: UUID) -> None:
        """
        Remove a contextual size modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        if uuid in self.size_modifiers:
            del self.size_modifiers[uuid]

    def add_damage_type_modifier(self, modifier: ContextualDamageTypeModifier) -> UUID:
        """
        Add a contextual damage type modifier to this value.

        Args:
            modifier (ContextualDamageTypeModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.damage_type_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_damage_type_modifier(self, uuid: UUID) -> None:
        """
        Remove a contextual damage type modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        if uuid in self.damage_type_modifiers:
            del self.damage_type_modifiers[uuid]

    def add_resistance_modifier(self, modifier: ContextualResistanceModifier) -> UUID:
        """
        Add a contextual resistance modifier to this value.

        Args:
            modifier (ContextualResistanceModifier): The modifier to add.

        Returns:
            UUID: The UUID of the added modifier.
        """
        self.resistance_modifiers[modifier.uuid] = modifier
        return modifier.uuid
    
    def remove_resistance_modifier(self, uuid: UUID) -> None:
        """
        Remove a contextual resistance modifier from this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        if uuid in self.resistance_modifiers:
            del self.resistance_modifiers[uuid]

    def remove_modifier(self, uuid: UUID) -> None:
        """
        Remove a modifier from all modifier dictionaries of this value.

        Args:
            uuid (UUID): The UUID of the modifier to remove.
        """
        self.remove_value_modifier(uuid)
        self.remove_min_constraint(uuid)
        self.remove_max_constraint(uuid)
        self.remove_advantage_modifier(uuid)
        self.remove_critical_modifier(uuid)
        self.remove_auto_hit_modifier(uuid)
        self.remove_size_modifier(uuid)
        self.remove_damage_type_modifier(uuid)
        self.remove_resistance_modifier(uuid)

    def combine_values(self, others: List['ContextualValue'], naming_callable: Optional[naming_callable] = None) -> 'ContextualValue':
        """
        Combine this ContextualValue with a list of other ContextualValues.

        Args:
            others (List[ContextualValue]): List of other ContextualValue instances to combine with.
            naming_callable (Optional[Callable[[List[str]], str]]): A function to generate the name of the combined value.

        Returns:
            ContextualValue: A new ContextualValue instance that combines all the input values.

        Raises:
            ValueError: If any of the other values have a different source entity UUID.
        """
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
            size_modifiers=merge_dicts(self.size_modifiers, *(other.size_modifiers for other in others)),
            damage_type_modifiers=merge_dicts(self.damage_type_modifiers, *(other.damage_type_modifiers for other in others)),
            resistance_modifiers=merge_dicts(self.resistance_modifiers, *(other.resistance_modifiers for other in others)),
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            target_entity_uuid=self.target_entity_uuid,
            target_entity_name=self.target_entity_name,
            context=self.context,
            score_normalizer=self.score_normalizer,
            is_outgoing_modifier=self.is_outgoing_modifier,
            global_normalizer=False
        )

    def get_all_modifier_uuids(self) -> List[UUID]:
        """
        Get a list of UUIDs for all modifiers in this ContextualValue.

        Returns:
            List[UUID]: A list of all modifier UUIDs.
        """
        return (list(self.value_modifiers.keys()) +
                list(self.min_constraints.keys()) +
                list(self.max_constraints.keys()) +
                list(self.advantage_modifiers.keys()) +
                list(self.critical_modifiers.keys()) +
                list(self.auto_hit_modifiers.keys()) +
                list(self.size_modifiers.keys()) +
                list(self.damage_type_modifiers.keys()) +
                list(self.resistance_modifiers.keys()))

    def remove_all_modifiers(self) -> None:
        """
        Remove all modifiers from this ContextualValue.
        """
        self.value_modifiers.clear()
        self.min_constraints.clear()
        self.max_constraints.clear()
        self.advantage_modifiers.clear()
        self.critical_modifiers.clear()
        self.auto_hit_modifiers.clear()
        self.size_modifiers.clear()
        self.damage_type_modifiers.clear()
        self.resistance_modifiers.clear()

    def _set_normalizer_recursive(self, normalizer: Callable[[int], int]) -> None:
        """
        Recursively set the score normalizer for this value and all its components.
        
        Args:
            normalizer (Callable[[int], int]): The normalizer function to apply.
        """
        self.score_normalizer = normalizer
        
        # Apply to value modifiers
        for modifier in self.value_modifiers.values():
            modifier.callable.score_normalizer = normalizer
        
        # Apply to min/max constraints if needed
        # for constraint in self.min_constraints.values():
        #     constraint.callable.score_normalizer = normalizer
        # for constraint in self.max_constraints.values():
        #     constraint.callable.score_normalizer = normalizer

    @model_validator(mode='after')
    def apply_global_normalizer(self) -> Self:
        """
        Apply the score normalizer to all numerical modifiers if global        Only affects modifiers that don't already have a normalizer.
        """
        if self.global_normalizer and self.score_normalizer is not None:
            self._set_normalizer_recursive(self.score_normalizer)
        return self

class ModifiableValue(BaseValue):
    """
    A comprehensive value type that combines static and contextual modifiers for both self and target entities.

    This class represents a complex value that can be modified by various factors, including
    static and contextual modifiers that apply to the entity itself and to/from target entities.
    It provides a flexible structure for handling complex game mechanics where values can be
    influenced by multiple sources and contexts.

    Attributes:
        name (str): The name of the value.
        uuid (UUID): Unique identifier for the value.
        source_entity_uuid (UUID): UUID of the entity that is the source of this value.
        source_entity_name (Optional[str]): Name of the entity that is the source of this value.
        target_entity_uuid (Optional[UUID]): UUID of the entity that this value targets, if any.
        target_entity_name (Optional[str]): Name of the entity that this value targets, if any.
        context (Optional[Dict[str, Any]]): Additional context information for this value.
        score_normalizer (Callable[[int], int]): A function to normalize the score.
        generated_from (List[UUID]): List of UUIDs of values that this value was generated from.
        self_static (StaticValue): Static modifiers that apply to the entity itself.
        to_target_static (StaticValue): Static modifiers that the entity applies to a target.
        self_contextual (ContextualValue): Context-dependent modifiers that apply to the entity itself.
        to_target_contextual (ContextualValue): Context-dependent modifiers that the entity applies to a target.
        from_target_contextual (Optional[ContextualValue]): Context-dependent modifiers applied by a target to this entity.
        from_target_static (Optional[StaticValue]): Static modifiers applied by a target to this entity.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseValue']]): A class-level registry to store all instances.

    Methods:
        create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None) -> 'ModifiableValue':
            Create a new ModifiableValue instance with shared source UUID for all components.
        // ... (other methods remain the same)

    Computed Attributes:
        min (Optional[int]): The minimum value based on all modifiers.
        max (Optional[int]): The maximum value based on all modifiers.
        score (int): The final calculated score.
        normalized_score (int): The normalized score after applying the score normalizer.
        advantage (AdvantageStatus): The final advantage status.
        critical (CriticalStatus): The final critical status.
        auto_hit (AutoHitStatus): The final auto-hit status.
        size (Size): The final size based on all size modifiers.
        damage_types (List[DamageType]): The list of all damage types based on damage type modifiers.
        damage_type (Optional[DamageType]): A randomly selected damage type from the most common types.
        resistance_sum (Dict[DamageType, int]): The sum of resistance values for each damage type.
        resistance (Dict[DamageType, ResistanceStatus]): The final resistance status for each damage type.

    Validators:
        validate_outgoing_modifier_flags: Ensures that the is_outgoing_modifier flags are set correctly for all components.
        validate_source_and_target_consistency: Ensures that the source and target UUIDs are consistent across all components.
    """

    self_static: StaticValue = Field(default_factory=lambda: StaticValue(source_entity_uuid=uuid4()))
    to_target_static: StaticValue = Field(default_factory=lambda: StaticValue(source_entity_uuid=uuid4(), is_outgoing_modifier=True))
    self_contextual: ContextualValue = Field(default_factory=lambda: ContextualValue(source_entity_uuid=uuid4()))
    to_target_contextual: ContextualValue = Field(default_factory=lambda: ContextualValue(source_entity_uuid=uuid4(), is_outgoing_modifier=True))
    from_target_contextual: Optional[ContextualValue] = Field(default=None)
    from_target_static: Optional[StaticValue] = Field(default=None)
    global_normalizer: bool = Field(
        default=True,
        description="Whether to apply the value's normalizer globally to all numerical modifiers"
    )

    def get_base_modifier(self) -> Optional[NumericalModifier]:
        """returns the base modifier for the value that is contained inside self_static and contains "_base_value" in the name"""
        for modifier in self.self_static.value_modifiers.values():
            if  modifier.name and "_base_value" in modifier.name:
                return modifier
        return None

    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               base_value: int = 0, value_name: str = "Value", score_normalizer: Optional[Callable[[int], int]] = None, global_normalizer: bool = True) -> 'ModifiableValue':
        """
        Create a new ModifiableValue instance with shared source UUID for all components.
        """
        # Use identity function if normalizer is None
        normalizer = score_normalizer if score_normalizer is not None else lambda x: x
        
        base_modifier = NumericalModifier(
            source_entity_uuid=source_entity_uuid, 
            target_entity_uuid=source_entity_uuid, 
            value=base_value, 
            name=f"{value_name}_base_value",
            score_normalizer=normalizer
        )
        
        obj = cls(
            name=value_name,
            source_entity_uuid=source_entity_uuid,
            source_entity_name=source_entity_name,
            self_static=StaticValue(
                source_entity_uuid=source_entity_uuid, 
                source_entity_name=source_entity_name, 
                value_modifiers={base_modifier.uuid: base_modifier},
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            to_target_static=StaticValue(
                source_entity_uuid=source_entity_uuid, 
                source_entity_name=source_entity_name, 
                is_outgoing_modifier=True,
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            self_contextual=ContextualValue(
                source_entity_uuid=source_entity_uuid, 
                source_entity_name=source_entity_name,
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            to_target_contextual=ContextualValue(
                source_entity_uuid=source_entity_uuid, 
                source_entity_name=source_entity_name, 
                is_outgoing_modifier=True,
                score_normalizer=normalizer,
                global_normalizer=global_normalizer
            ),
            score_normalizer=normalizer,
            global_normalizer=global_normalizer
        )
        
        if target_entity_uuid is not None:
            obj.set_target_entity(target_entity_uuid, target_entity_name)
            
        return obj
    

    def get_typed_modifiers(self) -> List[Union[StaticValue, ContextualValue]]:
        """
        Get a list of all non-None modifiers associated with this ModifiableValue.

        Returns:
            List[Union[StaticValue, ContextualValue]]: A list of all non-None modifiers.
        """
        modifiers = [self.self_static, self.self_contextual, self.from_target_contextual, self.from_target_static]
        return [modifier for modifier in modifiers if modifier is not None]

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ModifiableValue']:
        """
        Retrieve a ModifiableValue instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the value to retrieve.

        Returns:
            Optional[ModifiableValue]: The ModifiableValue instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ModifiableValue instance.
        """
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
        """
        Calculate the minimum value based on all modifiers.

        Returns:
            Optional[int]: The minimum value if constraints exist, None otherwise.
        """
        typed_modifiers = self.get_typed_modifiers()
        modifiers_min = [modifier.min for modifier in typed_modifiers if modifier.min is not None]
        if len(modifiers_min) == 0:
            return None
        return min(modifiers_min)
    
    @computed_field
    @property
    def max(self) -> Optional[int]:
        """
        Calculate the maximum value based on all modifiers.

        Returns:
            Optional[int]: The maximum value if constraints exist, None otherwise.
        """
        typed_modifiers = self.get_typed_modifiers()
        modifiers_max = [modifier.max for modifier in typed_modifiers if modifier.max is not None]
        if len(modifiers_max) == 0:
            return None
        return max(modifiers_max)
    
    def _score(self,normalized=False) -> int:
        """
        Calculate the final score of the value, considering all modifiers and constraints.

        Returns:
            int: The final calculated score.
        """
        typed_modifiers = self.get_typed_modifiers()
        if self.max is not None and self.min is not None:
            return max(self.min, min(sum(modifier.score if not normalized else modifier.normalized_score for modifier in typed_modifiers), self.max))
        elif self.max is not None:
            return min(sum(modifier.score if not normalized else modifier.normalized_score for modifier in typed_modifiers), self.max)
        elif self.min is not None:
            return max(self.min, sum(modifier.score if not normalized else modifier.normalized_score for modifier in typed_modifiers))
        else:
            return sum(modifier.score if not normalized else modifier.normalized_score for modifier in typed_modifiers)
        
    @computed_field
    @property
    def score(self) -> int:
        """
        Calculate the final score of the value, considering all modifiers and constraints.

        Returns:
            int: The final calculated score.
        """
        return self._score(normalized=False)
    
    @computed_field
    @property
    def normalized_score(self) -> int:
        """
        Apply the score normalizer function to the calculated score.

        Returns:
            int: The normalized score.
        """
        return self._score(normalized=True)
    @computed_field
    @property
    def advantage_sum(self) -> int:
        """
        Calculate the sum of advantage values from all modifiers.
        """
        return sum(adv.advantage_sum for adv in [self.self_static, self.from_target_static, self.self_contextual, self.from_target_contextual] if adv is not None)
    
    @computed_field
    @property
    def advantage(self) -> AdvantageStatus:
        """
        Determine the final advantage status based on all advantage modifiers.

        Returns:
            AdvantageStatus: The final advantage status (ADVANTAGE, DISADVANTAGE, or NONE).
        """
        total_sum = self.advantage_sum
        if total_sum > 0:
            return AdvantageStatus.ADVANTAGE
        elif total_sum < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE
    
    @computed_field
    @property
    def critical(self) -> CriticalStatus:
        """
        Determine the final critical status based on all critical modifiers.

        Returns:
            CriticalStatus: The final critical status (NOCRIT, AUTOCRIT, or NONE).
        """
        typed_modifiers = self.get_typed_modifiers()
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
        """
        Determine the final auto-hit status based on all auto-hit modifiers.

        Returns:
            AutoHitStatus: The final auto-hit status (AUTOMISS, AUTOHIT, or NONE).
        """
        typed_modifiers = self.get_typed_modifiers()
        all_auto_hit_modifiers = [modifier.auto_hit for modifier in typed_modifiers]
        if AutoHitStatus.AUTOMISS in all_auto_hit_modifiers:
            return AutoHitStatus.AUTOMISS
        elif AutoHitStatus.AUTOHIT in all_auto_hit_modifiers:
            return AutoHitStatus.AUTOHIT
        else:
            return AutoHitStatus.NONE

    @computed_field
    @property
    def size(self) -> Size:
        """
        Determine the final size based on all size modifiers.

        Returns:
            Size: The final size.
        """
        sizes : List[Size] = []
        components = self.get_typed_modifiers()
        for component in components:
            if component.size != Size.MEDIUM:  # Only consider non-default sizes
                sizes.append(component.size)
        if self.from_target_static and self.from_target_static.size != Size.MEDIUM:
            sizes.append(self.from_target_static.size)
        if self.from_target_contextual and self.from_target_contextual.size != Size.MEDIUM:
            sizes.append(self.from_target_contextual.size)
        
        if not sizes:
            return Size.MEDIUM  # Default size if no modifiers
        
        largest_size_priority = self.self_static.largest_size_priority  # Use the priority from self_static
        
        if largest_size_priority:
            return max(sizes, key=lambda s: list(Size).index(s))
        else:
            return min(sizes, key=lambda s: list(Size).index(s))

    @computed_field
    @property
    def damage_types(self) -> List[DamageType]:
        """
        Determine the list of damage types based on all damage type modifiers.

        Returns:
            List[DamageType]: The list of damage types with the highest occurrence.
        """
        type_counts = {}
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            for dt in component.damage_types:
                type_counts[dt] = type_counts.get(dt, 0) + 1
        if self.from_target_static:
            for dt in self.from_target_static.damage_types:
                type_counts[dt] = type_counts.get(dt, 0) + 1
        if self.from_target_contextual:
            for dt in self.from_target_contextual.damage_types:
                type_counts[dt] = type_counts.get(dt, 0) + 1
        
        if not type_counts:
            return []
        
        max_count = max(type_counts.values())
        most_common_types = [dt for dt, count in type_counts.items() if count == max_count]
        
        return most_common_types

    @computed_field
    @property
    def damage_type(self) -> Optional[DamageType]:
        """
        Determine a single damage type based on all damage type modifiers.

        Returns:
            Optional[DamageType]: A randomly selected damage type from the most common types, or None if no modifiers.
        """
        most_common_types = self.damage_types
        if not most_common_types:
            return None
        return random.choice(most_common_types)

    @computed_field
    @property
    def resistance_sum(self) -> Dict[DamageType, int]:
        """
        Calculate the sum of resistance values for each damage type.

        Returns:
            Dict[DamageType, int]: A dictionary with damage types as keys and summed resistance values as values.
        """
        resistance_sum = {damage_type: 0 for damage_type in DamageType}
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            for damage_type, value in component.resistance_sum.items():
                resistance_sum[damage_type] += value
        if self.from_target_static:
            for damage_type, value in self.from_target_static.resistance_sum.items():
                resistance_sum[damage_type] += value
        if self.from_target_contextual:
            for damage_type, value in self.from_target_contextual.resistance_sum.items():
                resistance_sum[damage_type] += value
        return resistance_sum

    @computed_field
    @property
    def resistance(self) -> Dict[DamageType, ResistanceStatus]:
        """
        Determine the final resistance status for each damage type based on the resistance sum.

        Returns:
            Dict[DamageType, ResistanceStatus]: A dictionary with damage types as keys and final resistance statuses as values.
        """
        resistance = {}
        for damage_type, sum_value in self.resistance_sum.items():
            if sum_value > 1:
                resistance[damage_type] = ResistanceStatus.IMMUNITY
            elif sum_value == 1:
                resistance[damage_type] = ResistanceStatus.RESISTANCE
            elif sum_value == 0:
                resistance[damage_type] = ResistanceStatus.NONE
            else:  # sum_value < 0
                resistance[damage_type] = ResistanceStatus.VULNERABILITY
        return resistance
    
    def set_source_entity(self, source_entity_uuid: UUID, source_entity_name: Optional[str]=None) -> None:
        """
        Set the source entity for this modifiable value and its components.
        """
        self.source_entity_uuid = source_entity_uuid
        self.source_entity_name = source_entity_name
        self.self_static.set_source_entity(source_entity_uuid, source_entity_name)
        self.to_target_static.set_source_entity(source_entity_uuid, source_entity_name)
        self.self_contextual.set_source_entity(source_entity_uuid, source_entity_name)
        self.to_target_contextual.set_source_entity(source_entity_uuid, source_entity_name)

    def set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None:
        """
        Set the target entity for this modifiable value and its contextual components.

        Args:
            target_entity_uuid (UUID): The UUID of the target entity.
            target_entity_name (Optional[str]): The name of the target entity, if available.
        """
        if not isinstance(target_entity_uuid, UUID):
            raise ValueError("target_entity_uuid must be a UUID")
        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name
        self.self_contextual.set_target_entity(target_entity_uuid, target_entity_name)
        self.self_static.set_target_entity(target_entity_uuid, target_entity_name)
        self.to_target_static.set_target_entity(target_entity_uuid, target_entity_name)
        self.to_target_contextual.set_target_entity(target_entity_uuid, target_entity_name)

    def clear_target_entity(self) -> None:
        """
        Clear the target entity information for this modifiable value and its components.
        """
        self.target_entity_uuid = None
        self.target_entity_name = None
        self.self_contextual.clear_target_entity()
        self.self_static.clear_target_entity()
        self.to_target_contextual.clear_target_entity()
        self.to_target_static.clear_target_entity()
        self.from_target_contextual = None
        self.from_target_static = None

    def set_context(self, context: Dict[str,Any]) -> None:
        """
        Set the context for this modifiable value and its contextual components.

        Args:
            context (Dict[str,Any]): The context dictionary to set.
        """
        self.context = context
        self.to_target_contextual.set_context(context)
        self.self_contextual.set_context(context)

    def clear_context(self) -> None:
        """
        Clear the context for this modifiable value and its contextual components.
        """
        self.context = None
        self.to_target_contextual.clear_context()
        self.self_contextual.clear_context()

    def set_from_target_contextual(self, contextual: ContextualValue) -> None:
        """
        Set the contextual modifiers applied by a target entity to this entity.

        Args:
            contextual (ContextualValue): The contextual modifiers to set.

        Raises:
            ValueError: If the source entity UUID of the contextual value doesn't match the target entity UUID of this value.
        """
        self.validate_target_id(contextual.source_entity_uuid)
        if contextual.target_entity_uuid is None:
            raise ValueError("Contextual value target entity UUID cannot be None when being assigned to a ModifiableValue")
        self.validate_source_id(contextual.target_entity_uuid)
        self.from_target_contextual = contextual.model_copy(update={"target_entity_uuid": self.source_entity_uuid, "target_entity_name": self.source_entity_name})

    def set_from_target_static(self, static: StaticValue) -> None:
        """
        Set the static modifiers applied by a target entity to this entity.

        Args:
            static (StaticValue): The static modifiers to set.

        Raises:
            ValueError: If the source entity UUID of the static value doesn't match the target entity UUID of this value.
        """
        self.validate_target_id(static.source_entity_uuid)
        self.from_target_static = static.model_copy(update={"target_entity_uuid": self.source_entity_uuid, "target_entity_name": self.source_entity_name})

    def set_from_target(self, target_value: 'ModifiableValue') -> None:
        """
        Set both contextual and static modifiers applied by a target entity to this entity.

        Args:
            target_value (ModifiableValue): The target entity's ModifiableValue to set modifiers from.
        """
        self.set_from_target_contextual(target_value.to_target_contextual)
        self.set_from_target_static(target_value.to_target_static)
    
    def combine_values(self, others: List['ModifiableValue'], naming_callable: Optional[naming_callable] = None) -> 'ModifiableValue':
        """
        Combine this ModifiableValue with a list of other ModifiableValues.

        Args:
            others (List[ModifiableValue]): List of other ModifiableValue instances to combine with.
            naming_callable (Optional[Callable[[List[str]], str]]): A function to generate the name of the combined value.

        Returns:
            ModifiableValue: A new ModifiableValue instance that combines all the input values.

        Raises:
            ValueError: If any of the other values have a different source entity UUID.
        """
        if naming_callable is None:
            naming_callable = lambda names: "_".join(names)
        
        for other in others:
            print(f"Validating others source id {other.source_entity_uuid} against self source {self.source_entity_uuid} for modifer  with name {self.name} and uuid {self.uuid} and type {type(self)} against {type(other)} with name {other.name} and uuid {other.uuid}")
            self.validate_source_id(other.source_entity_uuid)

        other_from_target_static_values = [other.from_target_static for other in others if other.from_target_static is not None]
        other_from_target_contextual_values = [other.from_target_contextual for other in others if other.from_target_contextual is not None]
        if self.from_target_static is not None:
            new_from_target_static = self.from_target_static.combine_values(other_from_target_static_values)
        elif len(other_from_target_static_values) > 0:
            new_from_target_static = other_from_target_static_values[0].combine_values(other_from_target_static_values[1:])
        else:
            new_from_target_static = None
        
        if self.from_target_contextual is not None:
            new_from_target_contextual = self.from_target_contextual.combine_values(other_from_target_contextual_values)
        elif len(other_from_target_contextual_values) > 0:
            new_from_target_contextual = other_from_target_contextual_values[0].combine_values(other_from_target_contextual_values[1:])
        else:
            new_from_target_contextual = None
        if new_from_target_static is not None:
            new_from_target_static.set_target_entity(self.source_entity_uuid, self.source_entity_name)
        if new_from_target_contextual is not None:
            new_from_target_contextual.set_target_entity(self.source_entity_uuid, self.source_entity_name)
        
        new_value= ModifiableValue(
            name=naming_callable([self.name] + [other.name for other in others]),
            self_static=self.self_static.combine_values([other.self_static for other in others]),
            to_target_static=self.to_target_static.combine_values([other.to_target_static for other in others]),
            self_contextual=self.self_contextual.combine_values([other.self_contextual for other in others]),
            to_target_contextual=self.to_target_contextual.combine_values([other.to_target_contextual for other in others]),
            from_target_static=new_from_target_static,
            from_target_contextual=new_from_target_contextual,
            generated_from=[self.uuid] + [other.uuid for other in others],
            source_entity_uuid=self.source_entity_uuid,
            source_entity_name=self.source_entity_name,
            target_entity_uuid=self.target_entity_uuid,
            target_entity_name=self.target_entity_name,
            context=self.context,
            score_normalizer=self.score_normalizer,
            global_normalizer=False,
        )
        if self.target_entity_uuid is not None:
            new_value.set_target_entity(self.target_entity_uuid, self.target_entity_name)
        return new_value
    
    def get_generated_from(self) -> List['ModifiableValue']:
        """
        Get the list of ModifiableValues that generated this ModifiableValue.
        """
        generated_from = [ModifiableValue.get(uuid) for uuid in self.generated_from if uuid is not None]
        return [x for x in generated_from if x is not None]

    def remove_modifier(self, uuid: UUID) -> None:
        """
        Remove a modifier from this ModifiableValue.
        """
        self.self_static.remove_modifier(uuid)
        self.self_contextual.remove_modifier(uuid)
        self.to_target_static.remove_modifier(uuid)
        self.to_target_contextual.remove_modifier(uuid)
        if self.from_target_static is not None:
            self.from_target_static.remove_modifier(uuid)
        if self.from_target_contextual is not None:
            self.from_target_contextual.remove_modifier(uuid)
    
    def remove_all_modifiers(self) -> None:
        """
        Remove all modifiers from this ModifiableValue.
        """
        self.self_static.remove_all_modifiers()
        self.self_contextual.remove_all_modifiers()
        self.to_target_static.remove_all_modifiers()
        self.to_target_contextual.remove_all_modifiers()
        if self.from_target_static:
            self.from_target_static.remove_all_modifiers()
        if self.from_target_contextual:
            self.from_target_contextual.remove_all_modifiers()

    def get_all_modifier_uuids(self) -> List[UUID]:
        """
        Get a list of UUIDs for all modifiers in this ModifiableValue.

        Returns:
            List[UUID]: A list of all modifier UUIDs.
        """
        uuids = []
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            uuids.extend(component.get_all_modifier_uuids())
        if self.from_target_static:
            uuids.extend(self.from_target_static.get_all_modifier_uuids())
        if self.from_target_contextual:
            uuids.extend(self.from_target_contextual.get_all_modifier_uuids())
        return uuids

    def remove_modifiers(self, uuids: List[UUID]) -> None:
        """
        Remove multiple modifiers from this ModifiableValue.

        Args:
            uuids (List[UUID]): A list of UUIDs of modifiers to remove.
        """
        for uuid in uuids:
            self.remove_modifier(uuid)
            
    def update_normalizers(self, new_normalizer: Optional[Callable[[int], int]] = None) -> None:
        """
        Update all component values and their modifiers with this ModifiableValue's score normalizer.
        This propagates the normalizer down through all static and contextual values and their modifiers.

        Args:
            new_normalizer (Optional[Callable[[int], int]]): If provided, first updates this ModifiableValue's
                score_normalizer to this new function before propagating it.
        """
        # Update this ModifiableValue's normalizer if a new one is provided
        if new_normalizer is not None:
            self.score_normalizer = new_normalizer
        
        # Update self components
        self.self_static._set_normalizer_recursive(self.score_normalizer)
        self.self_contextual._set_normalizer_recursive(self.score_normalizer)
        
        # Update to_target components
        self.to_target_static._set_normalizer_recursive(self.score_normalizer)
        self.to_target_contextual._set_normalizer_recursive(self.score_normalizer)
        
        # Update from_target components if they exist
        if self.from_target_static is not None:
            self.from_target_static._set_normalizer_recursive(self.score_normalizer)
        if self.from_target_contextual is not None:
            self.from_target_contextual._set_normalizer_recursive(self.score_normalizer)

    @model_validator(mode="after")
    def validate_outgoing_modifier_flags(self) -> Self:
        # Check self_static and self_contextual
        if self.self_static.is_outgoing_modifier:
            raise ValueError("self_static should not have is_outgoing_modifier set to True")
        if self.self_contextual.is_outgoing_modifier:
            raise ValueError("self_contextual should not have is_outgoing_modifier set to True")
        
        # Check to_target_static and to_target_contextual
        if not self.to_target_static.is_outgoing_modifier:
            raise ValueError("to_target_static should have is_outgoing_modifier set to True")
        if not self.to_target_contextual.is_outgoing_modifier:
            raise ValueError("to_target_contextual should have is_outgoing_modifier set to True")
        
        # Check from_target_static and from_target_contextual if they exist
        if self.from_target_static is not None and not self.from_target_static.is_outgoing_modifier:
            raise ValueError("from_target_static should have is_outgoing_modifier set to True")
        if self.from_target_contextual is not None and not self.from_target_contextual.is_outgoing_modifier:
            raise ValueError("from_target_contextual should have is_outgoing_modifier set to True")
        
        return self

    @model_validator(mode="after")
    def validate_source_and_target_consistency(self) -> Self:
        # Check that self and to_target components have the same source as the ModifiableValue
        for component in [self.self_static, self.to_target_static, self.self_contextual, self.to_target_contextual]:
            if component.source_entity_uuid != self.source_entity_uuid:
                component.source_entity_uuid = self.source_entity_uuid
                #raise ValueError(f"{component.__class__.__name__} source UUID ({component.source_entity_uuid}) "
                #                 f"does not match ModifiableValue source UUID ({self.source_entity_uuid})")

        # Check from_target components if they exist
        if self.from_target_static is not None:
            if self.from_target_static.target_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"from_target_static target UUID ({self.from_target_static.target_entity_uuid}) "                                 f"should be the same as ModifiableValue source UUID ({self.source_entity_uuid})")
            if self.from_target_static.source_entity_uuid == self.source_entity_uuid:
                raise ValueError(f"from_target_static source UUID ({self.from_target_static.source_entity_uuid}) "
                                 f"should not be the same as ModifiableValue source UUID ({self.source_entity_uuid})")

        if self.from_target_contextual is not None:
            if self.from_target_contextual.target_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"from_target_contextual target UUID ({self.from_target_contextual.target_entity_uuid}) "
                                 f"should be the same as ModifiableValue source UUID ({self.source_entity_uuid})")
            if self.from_target_contextual.source_entity_uuid == self.source_entity_uuid:
                raise ValueError(f"from_target_contextual source UUID ({self.from_target_contextual.source_entity_uuid}) "
                                 f"should not be the same as ModifiableValue source UUID ({self.source_entity_uuid})")

        return self

        
            
