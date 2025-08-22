from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, TypeVar, Generic, Union, Tuple, ClassVar, Dict, Any
from uuid import UUID, uuid4


class BaseObject(BaseModel):
    """
    Base class for all objects in the system.

    This class serves as the foundation for various types of objects that can be used in the game system. It includes basic information about the object, such as its name, source,
    in the game system. It includes basic information about the modifier, such as its name, source,
    and target.

    Attributes:
        name (Optional[str]): The name of the object. Can be None if not specified.
        uuid (UUID): Unique identifier for the object. Automatically generated if not provided.
        source_entity_uuid (UUID): UUID of the entity that is the source of this object.
        source_entity_name (Optional[str]): Name of the entity that is the source of this object. Can be None.
        target_entity_uuid (UUID): UUID of the entity that this object targets. Required.
        target_entity_name (Optional[str]): Name of the entity that this object targets. Can be None.
        use_register (bool): Whether to register this object in the class registry. Defaults to True.

    Class Attributes:
        _registry (ClassVar[Dict[UUID, 'BaseObject']]): A class-level registry to store all instances.

    Methods:
        get(cls, uuid: UUID) -> Optional['BaseObject']:
            Retrieve a BaseObject instance from the registry by its UUID.
        register(cls, object: 'BaseObject') -> None:
            Register a BaseObject instance in the class registry.
        unregister(cls, uuid: UUID) -> None:
            Remove a BaseObject instance from the class registry.
        add_to_register(self) -> None:
            Add this object to the class registry if it wasn't registered before.
        remove_from_register(self) -> None:
            Remove this object from the class registry.
        remove_objects(cls, uuids: List[UUID], permanent_delete: bool = False) -> None:
            Remove multiple objects from the registry with optional permanent deletion.
    """

    _registry: ClassVar[Dict[UUID, 'BaseObject']] = {}
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: Optional[str] = Field(
        default=None,
        description="The name of the object. Can be None if not specified."
    )
    uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the object. Automatically generated if not provided."
    )
    source_entity_uuid: UUID = Field(
       ...,
        description="UUID of the entity that is the source of this object."
    )
    source_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that is the source of this object. Can be None."
    )
    target_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the entity that this object targets. Required."
    )
    target_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that this object targets. Can be None."
    )
    context: Optional[Dict[str,Any]] = Field(
        default=None,
        description="Additional context information for this object."
    )
    use_register: bool = Field(
        default=True,
        description="Whether to register this object in the class registry."
    )

    def __init__(self, **data):
        """
        Initialize the BaseModifier and register it in the class registry if use_register is True.

        Args:
            **data: Keyword arguments to initialize the BaseModifier attributes.
        """
        super().__init__(**data)
        if self.use_register:
            self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseObject']:
        """
        Retrieve a BaseObject instance from the registry by its UUID.

        Args:
            uuid (UUID): The UUID of the modifier to retrieve.

        Returns:
            Optional[BaseObject]: The BaseObject instance if found, None otherwise.

        Raises:
            ValueError: If the retrieved object is not a BaseModifier instance.
        """
        modifier = cls._registry.get(uuid)
        if modifier is None:
            return None
        if not isinstance(modifier, cls):
            raise ValueError(f"Object with UUID {uuid} is not a {cls.__name__}, but {type(modifier).__name__}")
        return modifier

    @classmethod
    def register(cls, object: 'BaseObject') -> None:
        """
        Register a BaseModifier instance in the class registry.

        Args:               
            object (BaseObject): The object instance to register.
        """
        cls._registry[object.uuid] = object

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        """
        Remove a BaseObject instance from the class registry.

        Args:
            uuid (UUID): The UUID of the object to unregister.
        """
        cls._registry.pop(uuid, None)

    def add_to_register(self) -> None:
        """
        Add this object to the class registry if it wasn't registered before.
        
        Raises:
            ValueError: If the object is already registered or use_register is True.
        """
        if self.use_register:
            raise ValueError("Object is already set to use registry")
        if self.uuid in self.__class__._registry:
            raise ValueError("Object is already in registry")
        self.use_register = True
        self.__class__._registry[self.uuid] = self

    def remove_from_register(self) -> None:
        """
        Remove this object from the class registry and set use_register to False.
        """
        if self.uuid in self.__class__._registry:
            self.__class__._registry.pop(self.uuid)
        self.use_register = False

    @classmethod
    def remove_objects(cls, uuids: List[UUID], permanent_delete: bool = False) -> None:
        """
        Remove multiple objects from the registry with optional permanent deletion.
        If not permanently deleted, the objects will have their use_register set to False.

        Args:
            uuids (List[UUID]): List of UUIDs of objects to remove.
            permanent_delete (bool): Whether to permanently delete the objects. Defaults to False.
        """
        for uuid in uuids:
            obj = cls._registry.get(uuid)
            if obj is not None:
                if permanent_delete:
                    cls._registry.pop(uuid)
                    del obj
                else:
                    obj.remove_from_register()

    def set_source_entity(self, source_entity_uuid: UUID, source_entity_name: Optional[str]=None) -> None:
        """
        Set the source entity for this value and its components.
        """
        self.source_entity_uuid = source_entity_uuid
        self.source_entity_name = source_entity_name
    
    def validate_source_id(self, source_id: UUID) -> None:
        """
        Validate that the given source_id matches the source_entity_uuid of this value.

        Args:
            source_id (UUID): The source ID to validate.

        Raises:
            ValueError: If the source IDs do not match.
        """
        if self.source_entity_uuid != source_id:
            raise ValueError("Source entity UUIDs do not match")
    
    def validate_target_id(self, target_id: UUID) -> None:
        """
        Validate that the given target_id matches the target_entity_uuid of this value.

        Args:
            target_id (UUID): The target ID to validate.

        Raises:
            ValueError: If the target IDs do not match.
        """
        if self.target_entity_uuid != target_id:
            raise ValueError("Target entity UUIDs do not match")
    
    def set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str]=None) -> None:
        """
        Set the target entity for this contextual value.

        Args:
            target_entity_uuid (UUID): The UUID of the target entity.
            target_entity_name (Optional[str]): The name of the target entity, if available.
        """
        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name
    
    def clear_target_entity(self) -> None:
        """
        Clear the target entity information for this contextual value.
        """
        self.target_entity_uuid = None
        self.target_entity_name = None
    
    def set_context(self, context: Dict[str,Any]) -> None:
        """
        Set the context for this contextual value.

        Args:
            context (Dict[str,Any]): The context dictionary to set.
        """
        self.context = context
    
    def clear_context(self) -> None:
        """
        Clear the context for this contextual value.
        """
        self.context = None

