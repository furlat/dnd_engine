from pydantic import BaseModel, Field, computed_field, field_validator, PrivateAttr,model_validator
from typing import List, Optional, Dict, Any, Callable, Protocol, TypeVar, ClassVar,Union, Tuple, Self
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

class BaseModifier(BaseModel):
    """
    Base class for all modifiers in the system.

    This class serves as the foundation for various types of modifiers that can be applied to values
    in the game system. It includes basic information about the modifier, such as its name, source,
    and target.

    Attributes:
        name (Optional[str]): The name of the modifier. Can be None if not specified.
        uuid (UUID): Unique identifier for the modifier. Automatically generated if not provided.
        source_entity_uuid (Optional[UUID]): UUID of the entity that is the source of this modifier. Can be None.
        source_entity_name (Optional[str]): Name of the entity that is the source of this modifier. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this modifier targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this modifier targets. Can be None.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['BaseModifier']:
            Retrieve a BaseModifier instance from the registry by its UUID.
        register(cls, modifier: 'BaseModifier') -> None:
            Register a BaseModifier instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseModifier instance from the class registry.
    """

    _registry: ClassVar[Dict[UUID, 'BaseModifier']] = {}

    name: Optional[str] = Field(
        default=None,
        description="The name of the modifier. Can be None if not specified."
    )
    uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the modifier. Automatically generated if not provided."
    )
    source_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the entity that is the source of this modifier. Can be None."
    )
    source_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that is the source of this modifier. Can be None."
    )
    target_entity_uuid: UUID = Field(
        ...,
        description="UUID of the entity that this modifier targets. Required."
    )
    target_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that this modifier targets. Can be None."
    )

    def __init__(self, **data):
        """
        Initialize the BaseModifier and register it in the class registry.

        Args:
            **data: Keyword arguments to initialize the BaseModifier attributes.
        """
        super().__init__(**data)
        self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseModifier']:
        """
        Retrieve a BaseModifier instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[BaseModifier]: The BaseModifier instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a BaseModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        elif isinstance(modifier, BaseModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a BaseModifier, but {type(modifier)}")

    @classmethod
    def register(cls, modifier: 'BaseModifier') -> None:
        """
        Register a BaseModifier instance in the class registry.

        Args:
            modifier (BaseModifier): The modifier instance to register.
        """
        cls._registry[modifier.uuid] = modifier

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        """
        Remove a BaseModifier instance from the class registry.

        Args:
            uuid (UUID): The UUID of the modifier to unregister.
        """
        cls._registry.pop(uuid, None)

class NumericalModifier(BaseModifier):
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

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseModifier']]): A class-level registry to store all instances.

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
        elif isinstance(modifier, NumericalModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a NumericalModifier, but {type(modifier)}")

class AdvantageModifier(BaseModifier):
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
        elif isinstance(modifier, AdvantageModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not an AdvantageModifier, but {type(modifier)}")

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

class CriticalModifier(BaseModifier):
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
        elif isinstance(modifier, CriticalModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a CriticalModifier, but {type(modifier)}")

class AutoHitModifier(BaseModifier):
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
        elif isinstance(modifier, AutoHitModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not an AutoHitModifier, but {type(modifier)}")

ContextAwareCondition = ContextAwareCallable[bool]
ContextAwareAdvantage = ContextAwareCallable[AdvantageModifier]
ContextAwareCritical = ContextAwareCallable[CriticalModifier]
ContextAwareAutoHit = ContextAwareCallable[AutoHitModifier]
ContextAwareNumerical = ContextAwareCallable[NumericalModifier]


score_normaliziation_method = Callable[[int],int]
naming_callable = Callable[[List[str]],str]

# class ContextAwareModifier
class ContextualModifier(BaseModifier):
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
        elif isinstance(modifier, ContextualModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a ContextualModifier, but {type(modifier)}")

    @model_validator(mode="after")
    def validate_callable_source_iid(self) -> Self:
        """
        Validate that the source entity UUID in callable_arguments matches the target entity UUID of the modifier.

        Returns:
            Self: The validated ContextualModifier instance.

        Raises:
            ValueError: If the source entity UUID in callable_arguments doesn't match the target entity UUID.
        """
        if self.callable_arguments is not None:
            source_entity_uuid, target_entity_uuid, context = self.callable_arguments
            if source_entity_uuid != self.target_entity_uuid:
                raise ValueError("Callable argument Source entity UUID does not match target entity UUID of the modifier")
        return self
    
    def setup_callable_arguments(self, source_entity_uuid: UUID, target_entity_uuid: Optional[UUID]=None, context: Optional[Dict[str,Any]]=None) -> None:
        """
        Set up the arguments for the callable function.

        Args:
            source_entity_uuid (UUID): The UUID of the source entity.
            target_entity_uuid (Optional[UUID]): The UUID of the target entity, if any.
            context (Optional[Dict[str, Any]]): Additional context information, if any.

        Raises:
            ValueError: If the setup fails validation.
        """
        self.callable_arguments = (source_entity_uuid, target_entity_uuid, context)
        self.model_validate(self)

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
        elif isinstance(modifier, ContextualAdvantageModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a ContextualAdvantageModifier, but {type(modifier)}")

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
        elif isinstance(modifier, ContextualCriticalModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a ContextualCriticalModifier, but {type(modifier)}")

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
        elif isinstance(modifier, ContextualAutoHitModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a ContextualAutoHitModifier, but {type(modifier)}")

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
        elif isinstance(modifier, ContextualNumericalModifier):
            return modifier
        else:
            raise ValueError(f"Modifier with UUID {uuid} is not a ContextualNumericalModifier, but {type(modifier)}")
