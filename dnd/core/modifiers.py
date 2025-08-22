from pydantic import ConfigDict, BaseModel, Field, computed_field, field_validator, PrivateAttr,model_validator, ValidationError
from typing import List,Literal, Optional, Dict, Any, Callable, Protocol, TypeVar, ClassVar,Union, Tuple, Self
from uuid import UUID, uuid4
from enum import Enum

from dnd.core.base_object import BaseObject

T_co = TypeVar('T_co', covariant=True)

ContextAwareCallable = Callable[[UUID, Optional[UUID], Optional[Dict[str, Any]]], Optional[T_co]]

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
class ResistanceStatus(str,Enum):
    NONE = "None"
    RESISTANCE = "Resistance"
    IMMUNITY = "Immunity"
    VULNERABILITY = "Vulnerability"

class Size(str, Enum):
    TINY = "Tiny"
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"
    HUGE = "Huge"
    GARGANTUAN = "Gargantuan"

class DamageType(str, Enum):
    ACID = "Acid"
    BLUDGEONING = "Bludgeoning"
    COLD = "Cold"
    FIRE = "Fire"
    FORCE = "Force"
    LIGHTNING = "Lightning"
    NECROTIC = "Necrotic"
    PIERCING = "Piercing"
    POISON = "Poison"
    PSYCHIC = "Psychic"
    RADIANT = "Radiant"
    SLASHING = "Slashing"
    THUNDER = "Thunder"
saving_throws = Literal["strength_saving_throw", "dexterity_saving_throw", "constitution_saving_throw", "intelligence_saving_throw", "wisdom_saving_throw", "charisma_saving_throw"]



class NumericalModifier(BaseObject):
    """
    A modifier that applies a numerical value to a target.

    This class represents modifiers that have a direct numerical impact on the target,
    such as bonuses or penalties to attributes or scores.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        value (int): The numerical value of the modifier. Required.
        score_normalizer (Optional[Callable[[int], int]]): Optional function to normalize this modifier's value.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Computed Attributes:
        normalized_value (int): The normalized value of this modifier.

    Methods:
        get(cls, uuid: UUID) -> Optional['NumericalModifier']:
            Retrieve a NumericalModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
    """

    value: int = Field(
        ...,
        description="The numerical value of the modifier. Required."
    )
    score_normalizer: Optional[Callable[[int], int]] = Field(
        default=None,
        description="Optional function to normalize this modifier's value"
    )

    @computed_field
    @property
    def normalized_value(self) -> int:
        """Get the normalized value of this modifier."""
        if self.score_normalizer is None:
            return self.value
        return self.score_normalizer(self.value)

    @classmethod
    def get(cls, uuid: UUID) -> Optional['NumericalModifier']:
        """
        Retrieve a NumericalModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[NumericalModifier]: The NumericalModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a NumericalModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")
    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None, 
               target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, 
               name: str = "Numerical Modifier", value: int = 0, score_normalizer: Optional[Callable[[int], int]] = None) -> 'NumericalModifier':
        """
        Create a new NumericalModifier instance with the given parameters.

        Args:
            source_entity_uuid (UUID): The UUID of the source entity.
            source_entity_name (Optional[str]): The name of the source entity.
            target_entity_uuid (Optional[UUID]): The UUID of the target entity.
            target_entity_name (Optional[str]): The name of the target entity.
            name (str): The name of the modifier.
            value (int): The numerical value of the modifier.
            score_normalizer (Optional[Callable[[int], int]]): Optional function to normalize this modifier's value.

        Returns:
            NumericalModifier: The newly created NumericalModifier instance.
        """
        return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name=name, value=value, score_normalizer=score_normalizer)

class AdvantageModifier(BaseObject):
    """
    A modifier that applies advantage or disadvantage to a target.

    This class represents modifiers that affect the advantage status of an action or check,
    such as granting advantage or imposing disadvantage.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        value (AdvantageStatus): The advantage status applied by this modifier. Required.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Computed Attributes:
        numerical_value (int): Numerical representation of the advantage status (1 for ADVANTAGE, -1 for DISADVANTAGE, 0 for NONE).

    Methods:
        get(cls, uuid: UUID) -> Optional['AdvantageModifier']:
            Retrieve an AdvantageModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
    """

    value: AdvantageStatus = Field(
        ...,
        description="The advantage status (NONE, ADVANTAGE, or DISADVANTAGE) applied by this modifier. Required."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['AdvantageModifier']:
        """
        Retrieve an AdvantageModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[AdvantageModifier]: The AdvantageModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not an AdvantageModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

    @computed_field
    @property
    def numerical_value(self) -> int:
        """
        Convert the advantage status to a numerical representation.

        Returns:
            int: 1 for ADVANTAGE, -1 for DISADVANTAGE, 0 for NONE.
        """
        if self.value == AdvantageStatus.ADVANTAGE:
            return 1
        elif self.value == AdvantageStatus.DISADVANTAGE:
            return -1
        else:
            return 0

class CriticalModifier(BaseObject):
    """
    A modifier that affects the critical hit status of an attack.

    This class represents modifiers that can force a critical hit or prevent critical hits
    from occurring.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        value (CriticalStatus): The critical status applied by this modifier. Required.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['CriticalModifier']:
            Retrieve a CriticalModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
    """

    value: CriticalStatus = Field(
        ...,
        description="The critical status (NONE, AUTOCRIT, or NOCRIT) applied by this modifier. Required."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['CriticalModifier']:
        """
        Retrieve a CriticalModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[CriticalModifier]: The CriticalModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a CriticalModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

class AutoHitModifier(BaseObject):
    """
    A modifier that affects whether an attack automatically hits or misses.

    This class represents modifiers that can force an attack to automatically hit or miss,
    regardless of the attack roll.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        value (AutoHitStatus): The auto-hit status applied by this modifier. Required.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['AutoHitModifier']:
            Retrieve an AutoHitModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
    """

    value: AutoHitStatus = Field(
        ...,
        description="The auto-hit status (NONE, AUTOHIT, or AUTOMISS) applied by this modifier. Required."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['AutoHitModifier']:
        """
        Retrieve an AutoHitModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[AutoHitModifier]: The AutoHitModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not an AutoHitModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

ContextAwareCondition = ContextAwareCallable[bool]
ContextAwareAdvantage = ContextAwareCallable[AdvantageModifier]
ContextAwareCritical = ContextAwareCallable[CriticalModifier]
ContextAwareAutoHit = ContextAwareCallable[AutoHitModifier]
ContextAwareNumerical = ContextAwareCallable[NumericalModifier]


score_normaliziation_method = Callable[[int],int]
naming_callable = Callable[[List[str]],str]

# class ContextAwareModifier
class ContextualModifier(BaseObject):
    """
    A modifier that applies its effect based on context-aware callable functions.

    This class represents modifiers whose effects are determined dynamically based on the
    current game context, such as the source entity, target entity, and other situational factors.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        callable (Union[ContextAwareNumerical, ContextAwareAdvantage, ContextAwareCritical, ContextAwareAutoHit]):
            A callable function that determines the modifier's effect based on context.
        callable_arguments (Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]]): 
            The arguments to be passed to the callable function.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['ContextualModifier']:
            Retrieve a ContextualModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
        validate_callable_source_iid(self) -> Self:
            Validate that the source entity UUID in callable_arguments matches the target entity UUID of the modifier.
        setup_callable_arguments(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str,Any]]=None) -> None:
            Set up the arguments for the callable function.
    """

    callable: Union[ContextAwareNumerical, ContextAwareAdvantage, ContextAwareCritical, ContextAwareAutoHit] = Field(
        ...,
        description="A context-aware callable function that determines the modifier's effect."
    )
    callable_arguments: Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]] = Field(
        default=None,
        description="The arguments to be passed to the callable function: (source_uuid, target_uuid, context)."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualModifier']:
        """
        Retrieve a ContextualModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ContextualModifier]: The ContextualModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

    @model_validator(mode="after")
    def validate_callable_source_iid(self) -> Self:
        self.callable_validation_function()
        return self
    
    def callable_validation_function(self) -> None:
        if self.callable_arguments is not None:
            source_entity_uuid, target_entity_uuid, context = self.callable_arguments
            if source_entity_uuid != self.target_entity_uuid:
                raise ValueError("Callable argument Source entity UUID does not match target entity UUID of the modifier")
    
    def setup_callable_arguments(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str,Any]]=None) -> None:
        self.callable_arguments = (source_entity_uuid, target_entity_uuid, context)
        try:
            self.callable_validation_function()
        except ValueError as e:
            raise ValueError(str(e))

    def execute_callable(self) -> Union[NumericalModifier, AdvantageModifier, CriticalModifier, AutoHitModifier]:
        if self.callable_arguments is None:
            raise ValueError("Callable arguments not set")
        result = self.callable(*self.callable_arguments)
        expected_type = self._get_expected_return_type()
        if not isinstance(result, expected_type):
            raise ValueError(f"Callable returned unexpected type. Expected {expected_type.__name__}, got {type(result).__name__}")
        return result

    def _get_expected_return_type(self):
        if isinstance(self, ContextualNumericalModifier):
            return NumericalModifier
        elif isinstance(self, ContextualAdvantageModifier):
            return AdvantageModifier
        elif isinstance(self, ContextualCriticalModifier):
            return CriticalModifier
        elif isinstance(self, ContextualAutoHitModifier):
            return AutoHitModifier
        elif isinstance(self, ContextualSizeModifier):
            return SizeModifier
        elif isinstance(self, ContextualDamageTypeModifier):
            return DamageTypeModifier
        else:
            raise ValueError(f"Unknown ContextualModifier subclass: {self.__class__.__name__}")

class ContextualAdvantageModifier(ContextualModifier):
    """
    A contextual modifier that applies advantage or disadvantage based on the game context.

    This class represents modifiers that dynamically determine advantage or disadvantage
    status based on the current game state and entities involved.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        callable (ContextAwareAdvantage): A callable function that returns an AdvantageModifier based on context.
        callable_arguments (Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]]): 
            The arguments to be passed to the callable function.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['ContextualAdvantageModifier']:
            Retrieve a ContextualAdvantageModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
        validate_callable_source_iid(self) -> Self:
            Validate that the source entity UUID in callable_arguments matches the target entity UUID of the modifier.
        setup_callable_arguments(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str,Any]]=None) -> None:
            Set up the arguments for the callable function.
    """

    callable: ContextAwareAdvantage = Field(
        ...,
        description="A context-aware callable function that returns an AdvantageModifier."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualAdvantageModifier']:
        """
        Retrieve a ContextualAdvantageModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ContextualAdvantageModifier]: The ContextualAdvantageModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualAdvantageModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

class ContextualCriticalModifier(ContextualModifier):
    """
    A contextual modifier that affects critical hit status based on the game context.

    This class represents modifiers that dynamically determine critical hit status
    based on the current game state and entities involved.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        callable (ContextAwareCritical): A callable function that returns a CriticalModifier based on context.
        callable_arguments (Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]]): 
            The arguments to be passed to the callable function.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['ContextualCriticalModifier']:
            Retrieve a ContextualCriticalModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
        validate_callable_source_iid(self) -> Self:
            Validate that the source entity UUID in callable_arguments matches the target entity UUID of the modifier.
        setup_callable_arguments(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str,Any]]=None) -> None:
            Set up the arguments for the callable function.
    """

    callable: ContextAwareCritical = Field(
        ...,
        description="A context-aware callable function that returns a CriticalModifier."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualCriticalModifier']:
        """
        Retrieve a ContextualCriticalModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ContextualCriticalModifier]: The ContextualCriticalModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualCriticalModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

class ContextualAutoHitModifier(ContextualModifier):
    """
    A contextual modifier that determines auto-hit or auto-miss status based on the game context.

    This class represents modifiers that dynamically determine whether an attack automatically
    hits or misses based on the current game state and entities involved.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        callable (ContextAwareAutoHit): A callable function that returns an AutoHitModifier based on context.
        callable_arguments (Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]]): 
            The arguments to be passed to the callable function.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['ContextualAutoHitModifier']:
            Retrieve a ContextualAutoHitModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
        validate_callable_source_iid(self) -> Self:
            Validate that the source entity UUID in callable_arguments matches the target entity UUID of the modifier.
        setup_callable_arguments(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str,Any]]=None) -> None:
            Set up the arguments for the callable function.
    """

    callable: ContextAwareAutoHit = Field(
        ...,
        description="A context-aware callable function that returns an AutoHitModifier."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualAutoHitModifier']:
        """
        Retrieve a ContextualAutoHitModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ContextualAutoHitModifier]: The ContextualAutoHitModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualAutoHitModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

class ContextualNumericalModifier(ContextualModifier):
    """
    A contextual modifier that applies a numerical modification based on the game context.

    This class represents modifiers that dynamically determine a numerical value to be applied
    based on the current game state and entities involved.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        callable (ContextAwareNumerical): A callable function that returns a NumericalModifier based on context.
        callable_arguments (Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]]): 
            The arguments to be passed to the callable function.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['ContextualNumericalModifier']:
            Retrieve a ContextualNumericalModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
        validate_callable_source_iid(self) -> Self:
            Validate that the source entity UUID in callable_arguments matches the target entity UUID of the modifier.
        setup_callable_arguments(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str,Any]]=None) -> None:
            Set up the arguments for the callable function.
    """

    callable: ContextAwareNumerical = Field(
        ...,
        description="A context-aware callable function that returns a NumericalModifier."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualNumericalModifier']:
        """
        Retrieve a ContextualNumericalModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ContextualNumericalModifier]: The ContextualNumericalModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualNumericalModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

class SizeModifier(BaseObject):
    """
    A modifier that applies a size change to a target.

    This class represents modifiers that affect the size of an entity.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        value (Size): The size value applied by this modifier. Required.
    """

    value: Size = Field(
        ...,
        description="The size value applied by this modifier. Required."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['SizeModifier']:
        """
        Retrieve a SizeModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[SizeModifier]: The SizeModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a SizeModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

class DamageTypeModifier(BaseObject):
    """
    A modifier that applies a damage type change or addition to a target.

    This class represents modifiers that affect the damage type of an attack or ability.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        value (DamageType): The damage type applied by this modifier. Required.
    """

    value: DamageType = Field(
        ...,
        description="The damage type applied by this modifier. Required."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['DamageTypeModifier']:
        """
        Retrieve a DamageTypeModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[DamageTypeModifier]: The DamageTypeModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a DamageTypeModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

ContextAwareSize = ContextAwareCallable[SizeModifier]
ContextAwareDamageType = ContextAwareCallable[DamageTypeModifier]

class ContextualSizeModifier(ContextualModifier):
    """
    A contextual modifier that applies a size change based on the game context.

    This class represents modifiers that dynamically determine a size change
    based on the current game state and entities involved.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        callable (ContextAwareSize): A callable function that returns a SizeModifier based on context.
        callable_arguments (Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]]): 
            The arguments to be passed to the callable function.
    """

    callable: ContextAwareSize = Field(
        ...,
        description="A context-aware callable function that returns a SizeModifier."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualSizeModifier']:
        """
        Retrieve a ContextualSizeModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ContextualSizeModifier]: The ContextualSizeModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualSizeModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

class ContextualDamageTypeModifier(ContextualModifier):
    """
    A contextual modifier that applies a damage type change based on the game context.

    This class represents modifiers that dynamically determine a damage type change
    based on the current game state and entities involved.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        callable (ContextAwareDamageType): A callable function that returns a DamageTypeModifier based on context.
        callable_arguments (Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]]): 
            The arguments to be passed to the callable function.
    """

    callable: ContextAwareDamageType = Field(
        ...,
        description="A context-aware callable function that returns a DamageTypeModifier."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualDamageTypeModifier']:
        """
        Retrieve a ContextualDamageTypeModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ContextualDamageTypeModifier]: The ContextualDamageTypeModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualDamageTypeModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

class ResistanceModifier(BaseObject):
    """
    A modifier that applies resistance, immunity, or vulnerability to a damage type for a target.

    This class represents modifiers that affect how a target takes damage of a specific type.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        value (ResistanceStatus): The resistance status applied by this modifier. Required.
        damage_type (DamageType): The damage type this resistance applies to. Required.

    Computed Attributes:
        numerical_value (int): Numerical representation of the resistance status 
            (2 for IMMUNITY, 1 for RESISTANCE, 0 for NONE, -1 for VULNERABILITY).
    """

    value: ResistanceStatus = Field(
        ...,
        description="The resistance status (NONE, RESISTANCE, IMMUNITY, or VULNERABILITY) applied by this modifier. Required."
    )
    damage_type: DamageType = Field(
        ...,
        description="The damage type this resistance applies to. Required."
    )

    @computed_field
    @property
    def numerical_value(self) -> int:
        """
        Convert the resistance status to a numerical representation.

        Returns:
            int: 2 for IMMUNITY, 1 for RESISTANCE, 0 for NONE, -1 for VULNERABILITY.
        """
        if self.value == ResistanceStatus.IMMUNITY:
            return 2
        elif self.value == ResistanceStatus.RESISTANCE:
            return 1
        elif self.value == ResistanceStatus.VULNERABILITY:
            return -1
        else:  # ResistanceStatus.NONE
            return 0

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ResistanceModifier']:
        """
        Retrieve a ResistanceModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ResistanceModifier]: The ResistanceModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ResistanceModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")

ContextAwareResistance = ContextAwareCallable[ResistanceModifier]

class ContextualResistanceModifier(ContextualModifier):
    """
    A contextual modifier that applies resistance, immunity, or vulnerability based on the game context.

    This class represents modifiers that dynamically determine resistance status for a specific damage type
    based on the current game state and entities involved.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.
        callable (ContextAwareResistance): A callable function that returns a ResistanceModifier based on context.
        callable_arguments (Optional[Tuple[UUID, Optional[UUID], Optional[Dict[str, Any]]]]): 
            The arguments to be passed to the callable function.
    """

    callable: ContextAwareResistance = Field(
        ...,
        description="A context-aware callable function that returns a ResistanceModifier."
    )

    @classmethod
    def get(cls, uuid: UUID) -> Optional['ContextualResistanceModifier']:
        """
        Retrieve a ContextualResistanceModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[ContextualResistanceModifier]: The ContextualResistanceModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a ContextualResistanceModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, cls):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a {cls.__name__}, but {type(modifier)}")



