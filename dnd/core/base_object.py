import time
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, ClassVar, Dict, Final, List, Optional, Protocol
from uuid import UUID, uuid4


# Explicit Pydantic validation context for detached event values and their
# passive nested records. This does not restore executable engine graphs.
PASSIVE_EVENT_REPLAY: Final[object] = object()


class ContributionOwner(Protocol):
    """A retained native owner; blocks and conditions share only this gate."""
    uuid: UUID

    def contributions_active(self) -> bool: ...
    def allows_contribution_at(self, position: tuple[int, int] | None) -> bool: ...


class CreatesModels(Protocol):
    """A model class declaring the model classes its content can create in play."""

    creates: ClassVar[tuple[type['CreatesModels'], ...]]
    __pydantic_complete__: ClassVar[bool]

    @classmethod
    def model_rebuild(cls) -> bool | None: ...


# Default factories of models whose schema is built in play (`defer_build`, below)
# or that are made with `model_construct`. Pydantic reads a default factory's
# signature at each such build and construction, and CPython reads the signature
# of a C callable (`list`, `set`, `frozenset`, `tuple`, `time.time`) by defining
# a class: a reference cycle each time. A Python function's signature makes none.
def empty_list() -> list[Any]:
    return []


def empty_set() -> set[Any]:
    return set()


def empty_frozenset() -> frozenset[Any]:
    return frozenset()


def empty_tuple() -> tuple[Any, ...]:
    return ()


def wall_clock() -> float:
    return time.time()


# Classes whose creatable closure is built. A built schema stays built for the
# process, so creating another instance of one of them builds nothing.
_CLOSURES_BUILT: set[type] = set()


def build_creatable_models(model: type[CreatesModels]) -> None:
    """Build every model class `model`'s content can create, transitively.

    Conditions and actions defer their validation schema to first use
    (`defer_build`). Creating an object (a character, creature, item, placed
    object, action template or condition) builds the closure of its declared
    `creates` here, once per class, so the products it makes later in a
    gameplay operation are already built.
    """
    if model in _CLOSURES_BUILT:
        return
    pending = list(model.creates)
    seen: set[type[CreatesModels]] = set()
    while pending:
        product = pending.pop()
        if product in seen:
            continue
        seen.add(product)
        if not product.__pydantic_complete__:
            product.model_rebuild()
        pending.extend(product.creates)
    # Every product's own closure was walked here too.
    _CLOSURES_BUILT.update(seen)
    _CLOSURES_BUILT.add(model)


def read_private_attribute(model: BaseModel, item: str) -> Any:
    """Pydantic's private-attribute read without its per-read descriptor probe.

    Pydantic returns a private default's ``__get__`` result when the default is a
    descriptor and the stored value otherwise; no engine private default is a
    descriptor, so the stored value is read directly. Every other name keeps
    pydantic's own resolution.
    """
    try:
        return object.__getattribute__(model, '__pydantic_private__')[item]
    except (AttributeError, KeyError, TypeError):
        return BaseModel.__getattr__(model, item)  # type: ignore[attr-defined]


class BaseObject(BaseModel):
    """Base identity model for UUID-addressable engine objects.

    Subclasses use a class-level registry to make live objects recoverable by
    UUID. Registry participation is opt-out with `use_register=False`, which is
    useful for transient metadata objects and dry-run declarations.
    """

    _registry: ClassVar[Dict[UUID, ContributionOwner]] = {}
    # The model classes this object's content can create in play, by its own
    # rules or by the systems they trigger; a subclass extends its parent's.
    creates: ClassVar[tuple[type[CreatesModels], ...]] = ()
    model_config = ConfigDict(arbitrary_types_allowed=True)
    __getattr__ = read_private_attribute

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

    contribution_owner_uuid: UUID | None = Field(default=None, exclude=True,
        description="Existing runtime owner whose retained contributions gate this payload.")

    contribution_position: tuple[int, int] | None = Field(default=None, exclude=True)

    def allows_contribution_at(self, position: tuple[int, int] | None) -> bool:
        return self.contributions_active()

    def contributions_active(self) -> bool:
        """Read the existing owner graph; a missing bound owner cannot contribute."""
        if self.contribution_owner_uuid is None:
            return True
        owner = BaseObject.get_contribution_owner(self.contribution_owner_uuid)
        return owner is not None and owner.allows_contribution_at(self.contribution_position)

    @classmethod
    def get_contribution_owner(cls, uuid: UUID) -> ContributionOwner | None:
        return BaseObject._registry.get(uuid)

    def model_post_init(self, __context: Any) -> None:
        """Build what this object can create; register it by UUID when registry participation is enabled."""
        build_creatable_models(type(self))
        if __context is not PASSIVE_EVENT_REPLAY and self.use_register:
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
    def register(cls, obj: ContributionOwner) -> None:
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
            if isinstance(obj, BaseObject):
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

    def set_context(self, context: Dict[str, Any]) -> None:
        """Set runtime context for this object.

        Args:
            context: Context dictionary to attach.
        """
        self.context = context

