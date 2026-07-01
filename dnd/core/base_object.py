from pydantic import BaseModel, Field, ConfigDict
from typing import Any, ClassVar, Dict, List, Optional
from uuid import UUID, uuid4


class BaseObject(BaseModel):
    """Base identity model for UUID-addressable engine objects.

    Subclasses use a class-level registry to make live objects recoverable by
    UUID. Registry participation is opt-out with `use_register=False`, which is
    useful for transient metadata objects and dry-run declarations.
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
        description="UUID of the entity this object targets, if any."
    )
    target_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that this object targets. Can be None."
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context information for this object."
    )
    use_register: bool = Field(
        default=True,
        description="Whether to register this object in the class registry."
    )

    def model_post_init(self, __context: Any) -> None:
        """Register the object by UUID when registry participation is enabled."""
        if self.use_register:
            self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseObject']:
        """Retrieve an object from this class registry by UUID.

        Args:
            uuid: UUID of the object to retrieve.

        Returns:
            The registered object when found, otherwise `None`.

        Raises:
            ValueError: If the UUID resolves to an object of another type.
        """
        obj = cls._registry.get(uuid)
        if obj is None:
            return None
        if not isinstance(obj, cls):
            raise ValueError(f"Object with UUID {uuid} is not a {cls.__name__}, but {type(obj).__name__}")
        return obj

    @classmethod
    def register(cls, obj: 'BaseObject') -> None:
        """Register an object in this class registry.

        Args:
            obj: Object instance to register.
        """
        cls._registry[obj.uuid] = obj

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        """Remove an object from this class registry.

        Args:
            uuid: UUID of the object to unregister.
        """
        cls._registry.pop(uuid, None)

    def add_to_register(self) -> None:
        """Add this object to its class registry.

        Raises:
            ValueError: If the object is already configured to use the registry
                or an object with the same UUID is already registered.
        """
        if self.use_register:
            raise ValueError("Object is already set to use registry")
        if self.uuid in self.__class__._registry:
            raise ValueError("Object is already in registry")
        self.use_register = True
        self.__class__._registry[self.uuid] = self

    def remove_from_register(self) -> None:
        """Remove this object from the class registry and disable registration."""
        if self.uuid in self.__class__._registry:
            self.__class__._registry.pop(self.uuid)
        self.use_register = False

    @classmethod
    def remove_objects(cls, uuids: List[UUID], permanent_delete: bool = False) -> None:
        """Remove multiple objects from this class registry.

        Args:
            uuids: UUIDs of objects to remove.
            permanent_delete: If true, remove registry entries and delete the
                local references held by this method. If false, call
                `remove_from_register()` on each object.
        """
        for uuid in uuids:
            obj = cls._registry.get(uuid)
            if obj is not None:
                if permanent_delete:
                    cls._registry.pop(uuid)
                    del obj
                else:
                    obj.remove_from_register()

    def set_source_entity(self, source_entity_uuid: UUID, source_entity_name: Optional[str] = None) -> None:
        """Set the source entity identity for this object.

        Args:
            source_entity_uuid: UUID of the source entity.
            source_entity_name: Optional display name of the source entity.
        """
        self.source_entity_uuid = source_entity_uuid
        self.source_entity_name = source_entity_name

    def validate_source_id(self, source_id: UUID) -> None:
        """Validate that a UUID matches this object's source entity UUID.

        Args:
            source_id: Source UUID to validate.

        Raises:
            ValueError: If the UUIDs do not match.
        """
        if self.source_entity_uuid != source_id:
            raise ValueError("Source entity UUIDs do not match")

    def validate_target_id(self, target_id: UUID) -> None:
        """Validate that a UUID matches this object's target entity UUID.

        Args:
            target_id: Target UUID to validate.

        Raises:
            ValueError: If the UUIDs do not match.
        """
        if self.target_entity_uuid != target_id:
            raise ValueError("Target entity UUIDs do not match")

    def set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str] = None) -> None:
        """Set the target entity identity for this object.

        Args:
            target_entity_uuid: UUID of the target entity.
            target_entity_name: Optional display name of the target entity.
        """
        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name

    def clear_target_entity(self) -> None:
        """Clear target entity identity from this object."""
        self.target_entity_uuid = None
        self.target_entity_name = None

    def set_context(self, context: Dict[str, Any]) -> None:
        """Set runtime context for this object.

        Args:
            context: Context dictionary to attach.
        """
        self.context = context

    def clear_context(self) -> None:
        """Clear runtime context from this object."""
        self.context = None
