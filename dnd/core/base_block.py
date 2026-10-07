from dnd.core.action_types import ActionEconomyCostType
from typing import AbstractSet, Dict, Optional, Any, List, Self, Set, ClassVar, Callable, Tuple
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, PrivateAttr, model_validator, computed_field, ConfigDict
from dnd.core.values import ModifiableValue
from dnd.core.base_object import BaseObject
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.condition_types import (
    HazardFilter, InvoluntarySustainLoss, SustainLossPolicy, ConditionTag,
)
from dnd.core.item_types import ItemPresentationState, ItemReleaseReason
from dnd.core.content.runtime import (
    bind_runtime_behavior,
    bind_runtime_handler_before_admission,
)
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    Trigger,
    WorldTileState,
)
from dnd.core.item_properties import ItemWearerValues
from dnd.types.senses import (
    SenseMode as SenseMode,
    SensesType as SensesType,
    SensesView,
)
from dnd.types.world import LightLevel as LightLevel, MovementMode, OccupancyLayer
from dnd.types.actor import EntityStatsState
from dnd.types.physical_access import ContactPassage, PhysicalAccess
from dnd.types.controls import ControlLink
from dnd.core.effect_types import ObjectSectionVolume
from dnd.types.world_placement import (
    BoundaryStructure,
    WorldPlacementKind,
    WorldPlacementSpec,
    WorldObjectPlacement,
)

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Protocol
from dnd.types.actor import ConditionState
from dnd.types.summoning import TerminalOwnerRelease
from contextvars import ContextVar

ContextualConditionImmunity = Callable[['BaseBlock', Optional['BaseBlock'], Optional[dict]], bool]


@dataclass(frozen=True)
class ConditionRemovalReceipt:
    """One committed removal, delivered after its complete graph settles."""

    owner_uuid: UUID
    condition_uuid: UUID
    removal_event_uuid: UUID
    terminal_release: TerminalOwnerRelease | None = None
    involuntary_loss: InvoluntarySustainLoss | None = None


class ConditionRemovalParticipant(Protocol):
    """Explicit native owner admission around the existing condition graph."""

    def prepare_condition_removal(self, owner_uuid: UUID | None, condition_uuid: UUID,
                                  event: Event, terminal_release: TerminalOwnerRelease | None,
                                  involuntary_loss: InvoluntarySustainLoss | None) -> bool: ...

    def validate_condition_removal(self, condition_uuid: UUID) -> bool: ...

    def commit_condition_removal(self, owner_uuid: UUID, condition_uuid: UUID) -> None: ...

    def cancel_condition_removal(self, condition_uuid: UUID, reason: str) -> None: ...


@dataclass
class ConditionPublication:
    condition: BaseCondition
    effect: Event
    condition_state: ConditionState
    resulting_stats: EntityStatsState | None
    resulting_tile: WorldTileState | None
    resulting_item: ItemPresentationState | None
    post_removal_stats: dict[str, Any]
    independent_owner: bool = False


@dataclass
class CommittedConditionRemovals:
    removals: list[ConditionPublication] = field(default_factory=list)
    linked_owners: list[tuple[BaseCondition, "BaseBlock", ConditionState, EntityStatsState | None, Event]] = field(default_factory=list)
    published: bool = False


@dataclass
class PreparedConditionRemovals:
    entries: list[tuple["BaseBlock | None", BaseCondition, Event, bool]]
    terminal_release: TerminalOwnerRelease | None = None
    committed_result: CommittedConditionRemovals | None = None
    canceled: bool = False


@dataclass
class PreparedConditionApplication:
    owner: "BaseBlock"
    condition: BaseCondition
    effect: Event
    replacements: list[tuple["BaseBlock | None", BaseCondition, Event, bool]] = field(default_factory=list)
    required: "PreparedConditionApplication | None" = None
    removal_commit: CommittedConditionRemovals | None = None
    committed: bool = False
    published: bool = False
    canceled: bool = False
    completion: Event | None = None
    publication: ConditionPublication | None = None


@dataclass
class PreparedInitialConditions:
    owner_uuid: UUID
    applications: tuple[PreparedConditionApplication, ...]
    committed: bool = False
    published: bool = False


@dataclass
class _ConditionRemovalScope:
    receipts: list[ConditionRemovalReceipt] = field(default_factory=list)
    completions: list[ConditionPublication] = field(default_factory=list)


ConditionGraphSettledHook = Callable[[tuple[ConditionRemovalReceipt, ...]], None]


class BaseBlock(BaseModel):
    """UUID-addressable container for engine components.

    Blocks group child blocks, modifiable values, conditions, and local event
    handlers behind a shared source/target/context identity. Subclasses such as
    entities, items, tiles, equipment, and health blocks specialize the virtual
    spatial and gameplay hooks while retaining the same registry and cleanup
    contracts.
    """

    name: str = Field(
        default="A Block",
        description="The name of the block. Defaults to 'A Block' if not specified."
    )
    description: Optional[str] = Field(
        default=None,
        description="A description of the block. Can be None."
    )
    uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the block. Automatically generated if not provided."
    )
    source_entity_uuid: UUID = Field(
        ...,
        description="UUID of the entity that is the source of this block. Must be provided explicitly."
    )
    source_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that is the source of this block. Can be None."
    )
    target_entity_uuid: Optional[UUID] = Field(
        default=None,
        description="UUID of the entity that this block targets, if any. Can be None."
    )
    target_entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity that this block targets, if any. Can be None."
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context information for this block. Can be None."
    )
    blocks: Dict[UUID, 'BaseBlock'] = Field(
        default_factory=dict,
        description="Dictionary of all BaseBlock instances that are attributes of this class."
    )
    values: Dict[UUID, 'ModifiableValue'] = Field(
        default_factory=dict,
        description="Dictionary of all ModifiableValue instances that are attributes of this class."
    )

    position: Tuple[int, int] = Field(
        default_factory=lambda: (0, 0),
        description="Grid position used by spatial blocks and propagated to child blocks."
    )
    faction: Optional[str] = Field(default=None, description="Faction for ally/enemy detection. None = no faction.")
    stealth_dc: Optional[int] = Field(default=None, exclude=True,
        description="Stealth DC required to perceive. Set by Hidden condition.")
    intrinsic_invisibility: bool = Field(default=False, alias="is_invisible", exclude=True,
        description="Authored/manual invisibility independent of condition-owned contributions.")

    @property
    def is_invisible(self) -> bool:
        return self.intrinsic_invisibility or any(condition.grants_invisibility
            and condition.contributions_active() for condition in self.active_conditions_by_uuid.values())

    @is_invisible.setter
    def is_invisible(self, value: bool) -> None:
        self.intrinsic_invisibility = value

    _attached_light_sources: Set[UUID] = PrivateAttr(default_factory=set)

    active_conditions: Dict[str, BaseCondition] = Field(
        default_factory=dict,
        description="Active conditions keyed by condition name."
    )
    active_conditions_by_uuid: Dict[UUID, BaseCondition] = Field(
        default_factory=dict,
        exclude=True,
        description="Active conditions keyed by condition UUID."
    )
    condition_immunities: List[Tuple[str, Optional[str]]] = Field(
        default_factory=list,
        description="Static condition immunities as condition-name/source-name pairs."
    )
    contextual_condition_immunities: Dict[str, List[Tuple[str, ContextualConditionImmunity]]] = Field(
        default_factory=dict,
        exclude=True,
        description="Runtime condition immunity checks keyed by condition name."
    )
    active_conditions_by_source: Dict[UUID, List[str]] = Field(
        default_factory=lambda: defaultdict(list),
        exclude=True,
        description="Active condition names grouped by source entity UUID."
    )

    event_handlers: Dict[UUID, EventHandler] = Field(
        default_factory=dict,
        description="Local event handlers owned by this block."
    )
    event_handlers_by_trigger: Dict[Trigger, List[EventHandler]] = Field(
        default_factory=lambda: defaultdict(list),
        exclude=True,
        description="Local event handlers indexed by full trigger."
    )
    event_handlers_by_simple_trigger: Dict[Trigger, List[EventHandler]] = Field(
        default_factory=lambda: defaultdict(list),
        exclude=True,
        description="Local event handlers indexed by simplified trigger."
    )

    allow_events_conditions: bool = Field(default=False,description="If True, events and conditions will be allowed to be added to the block")

    @computed_field
    @property
    def contextual_immunity_names(self) -> Dict[str, List[str]]:
        """Serializable view of contextual condition immunities (names only)."""
        return {cond: [name for name, _ in imms] for cond, imms in self.contextual_condition_immunities.items()}

    _registry: ClassVar[Dict[UUID, 'BaseBlock']] = {}
    _accepted_condition_removals: ClassVar[ContextVar[Optional[Dict[
        UUID, Tuple[Optional['BaseBlock'], BaseCondition, Event, bool]
    ]]]] = ContextVar("accepted_condition_removals", default=None)


    _removal_scope: ClassVar[ContextVar[_ConditionRemovalScope | None]] = ContextVar("condition_removal_scope", default=None)
    _terminal_release: ClassVar[ContextVar[TerminalOwnerRelease | None]] = ContextVar("condition_terminal_release", default=None)
    _involuntary_loss: ClassVar[ContextVar[InvoluntarySustainLoss | None]] = ContextVar("condition_involuntary_loss", default=None)
    _graph_settled_hooks: ClassVar[dict[UUID, ConditionGraphSettledHook]] = {}
    _removal_participants: ClassVar[dict[UUID, ConditionRemovalParticipant]] = {}

    @classmethod
    def register_condition_removal_participant(cls, participant: ConditionRemovalParticipant) -> UUID:
        key = uuid4()
        cls._removal_participants[key] = participant
        return key

    @classmethod
    def remove_condition_removal_participant(cls, key: UUID) -> None:
        cls._removal_participants.pop(key, None)

    @classmethod
    def _cancel_native_condition_removal(cls, condition: BaseCondition, reason: str) -> None:
        errors: list[BaseException] = []
        for participant in tuple(cls._removal_participants.values()):
            try:
                participant.cancel_condition_removal(condition.uuid, reason)
            except BaseException as error:
                errors.append(error)
        try:
            condition.cancel_prepared_removal(reason)
        except BaseException as error:
            errors.append(error)
        if errors:
            raise BaseExceptionGroup("Native condition removal cancellation failed", errors)

    @classmethod
    def register_condition_graph_settled_hook(cls, callback: ConditionGraphSettledHook) -> UUID:
        key = uuid4()
        cls._graph_settled_hooks[key] = callback
        return key

    @classmethod
    def remove_condition_graph_settled_hook(cls, key: UUID) -> None:
        cls._graph_settled_hooks.pop(key, None)

    @classmethod
    @contextmanager
    def condition_removal_scope(cls, *, terminal_release: TerminalOwnerRelease | None = None) -> Iterator[None]:
        """Settle native owners before sealing their removal event lineages."""
        outer = cls._removal_scope.get() is None
        scope = cls._removal_scope.get() or _ConditionRemovalScope()
        token = cls._removal_scope.set(scope)
        admissions = cls._accepted_condition_removals.get()
        admission_token = cls._accepted_condition_removals.set(admissions if admissions is not None else {})
        release_token = cls._terminal_release.set(terminal_release or cls._terminal_release.get())
        failure: BaseException | None = None
        try:
            yield
        except BaseException as error:
            failure = error
        finally:
            cls._terminal_release.reset(release_token)
            cls._removal_scope.reset(token)
            cls._accepted_condition_removals.reset(admission_token)
        failures: list[BaseException] = []
        if failure is not None:
            failures.append(failure)
        if outer and scope.receipts:
            receipts = tuple(scope.receipts)
            for callback in tuple(cls._graph_settled_hooks.values()):
                try:
                    callback(receipts)
                except BaseException as error:
                    failures.append(error)
        if outer:
            for publication in scope.completions:
                try:
                    cls._complete_condition_removal(publication)
                except BaseException as error:
                    failures.append(error)
        if len(failures) == 1:
            raise failures[0]
        if failures:
            raise BaseExceptionGroup("Condition operation and settled cleanup failed", failures)

    model_config = ConfigDict(validate_assignment=False)

    def get_map_char(self) -> Optional[str]:
        """Map glyph for blocks that have one."""
        return None

    def get_spatial_open_state(self) -> Optional[bool]:
        """Open/closed state for spatial objects that expose one."""
        return None

    def should_include_in_senses_objects(self) -> bool:
        """Whether this block should appear in entity senses.objects."""
        return True

    def is_observable_to(self, observer_uuid: UUID) -> bool:
        """Admit ordinary contacts; composed objects can share an existing discovery owner."""
        return True

    def appears_in_entity_contacts(self) -> bool:
        """Whether a GridMap entity occupant belongs in perceived contacts."""
        return True

    def should_include_in_adjacent_senses_objects(self) -> bool:
        """Whether this block can be sensed from an adjacent tile even if its cell is not visible."""
        return False

    def should_include_in_available_object_actions(self) -> bool:
        """Whether this block should be considered by object/action discovery."""
        return True

    def _set_values_and_blocks_source(self, block: 'BaseBlock') -> None:
        """Propagate source, target, and context into a block tree.

        Args:
            block: Block whose immediate values and child blocks should inherit
                owner identity.
        """
        for value in block.values.values():
            value.set_source_entity(block.source_entity_uuid, block.source_entity_name)
            if block.context is not None:
                value.set_context(block.context)
            if block.target_entity_uuid is not None:
                value.set_target_entity(block.target_entity_uuid, block.target_entity_name)

        for sub_block in block.blocks.values():
            sub_block.source_entity_uuid = block.source_entity_uuid
            sub_block.source_entity_name = block.source_entity_name
            if block.context is not None:
                sub_block.set_context(block.context)
            if block.target_entity_uuid is not None:
                sub_block.set_target_entity(block.target_entity_uuid, block.target_entity_name)
            self._set_values_and_blocks_source(sub_block)

    def _populate_blocks_and_values(self) -> None:
        """Discover direct child blocks and modifiable values on this model."""
        for name, _ in self.__class__.model_fields.items():
            attr_value = getattr(self, name)
            if name in ['blocks', 'values']:
                continue
            if isinstance(attr_value, ModifiableValue):
                self.values[attr_value.uuid] = attr_value
            elif isinstance(attr_value, BaseBlock):
                self.blocks[attr_value.uuid] = attr_value

    @model_validator(mode='after')
    def set_values_and_blocks_source(self) -> 'Self':
        """Propagate this block's identity to discovered values and children.

        Returns:
            This block after propagation.
        """
        self._populate_blocks_and_values()
        self._set_values_and_blocks_source(self)
        return self

    @model_validator(mode='after')
    def validate_values_and_blocks_source_and_target(self) -> Self:
        """Validate discovered values and children share this block's source.

        Returns:
            This block after validation.

        Raises:
            ValueError: If a discovered value or child block has a mismatched
                source UUID.
        """
        for _, value in self.values.items():
            if value.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"ModifiableValue '{value.name}' has mismatched source UUID")

        for _, block in self.blocks.items():
            if block.source_entity_uuid != self.source_entity_uuid:
                raise ValueError(f"BaseBlock '{block.name}' has mismatched source UUID")

        return self


    def model_post_init(self, __context: Any) -> None:
        """Register this block in the block registry by UUID."""
        super().model_post_init(__context)
        self.__class__._registry[self.uuid] = self

    @classmethod
    def get(cls, uuid: UUID) -> Optional['BaseBlock']:
        """Retrieve a block from the block registry by UUID.

        Args:
            uuid: UUID of the block to retrieve.

        Returns:
            The registered block when found, otherwise `None`.

        Raises:
            ValueError: If the UUID resolves to a non-block object.
        """
        value = cls._registry.get(uuid)
        if value is None:
            return None
        elif isinstance(value, BaseBlock):
            return value
        else:
            raise ValueError(f"Value with UUID {uuid} is not a BaseBlock, but {type(value)}")

    @classmethod
    def register(cls, value: 'BaseBlock') -> None:
        """Register a block in the class registry.

        Args:
            value: Block instance to register.
        """
        cls._registry[value.uuid] = value

    @classmethod
    def unregister(cls, uuid: UUID) -> None:
        """Remove a block from the class registry.

        Args:
            uuid: UUID of the block to unregister.
        """
        cls._registry.pop(uuid, None)
        BaseObject.unregister(uuid)

    def get_blocks(self) -> List['BaseBlock']:
        """Return direct child blocks discovered on this block.

        Returns:
            Direct child blocks.
        """
        return list(self.blocks.values())

    def get_values(self, deep: bool = False) -> List['ModifiableValue']:
        """Return values discovered on this block.

        Args:
            deep: Whether to recurse into child blocks.

        Returns:
            Discovered modifiable values.
        """
        values = list(self.values.values())
        if deep:
            for block in self.blocks.values():
                values.extend(block.get_values(deep=True))
        return values

    def set_position(self, position: Tuple[int,int]) -> None:
        """
        Set the position of the block.
        """
        self.position = position
        for block in self.blocks.values():
            block.set_position(position)

    def blocks_walking(self, requesting_entity_uuid: Optional[UUID] = None,
                       mode: 'MovementMode' = MovementMode.WALKING) -> bool:
        """Whether this block prevents walking through its position.
        Non-spatial blocks (Equipment, Health, etc.) inherit this default."""
        return False

    def blocks_optics_at_center(self) -> bool:
        """Whether this block prevents ordinary optics through its cell center."""
        return False

    def get_contact_passage(self) -> ContactPassage:
        """Contact defaults to this provider's structural movement obstruction."""
        structure = self.get_boundary_structure()
        return structure.contact_passage if structure is not None else ContactPassage.STRUCTURAL

    def get_manual_contact_range(self) -> int:
        """Distance from an occupied support to this object's usable surface."""
        return 5

    def get_supporting_object_uuid(self) -> Optional[UUID]:
        """Physical attachment, independent of inventory ownership."""
        return None

    def get_melee_threat_access(self) -> tuple[PhysicalAccess, int]:
        """Neutral fallback; actors expose their actual reaction attack capability."""
        return PhysicalAccess.NATURAL, 5

    def blocks_propagation(self) -> bool:
        """Whether this block prevents physical propagation through its cell center."""
        return False

    def set_stealth_dc(self, value: Optional[int], parent_event: Optional[UUID] = None, *, publish: bool = True) -> bool:
        """Commit stealth; condition membership may defer its native observation."""
        if self.stealth_dc == value:
            return False
        self.stealth_dc = value
        if publish:
            self._notify_perceivability_changed(parent_event=parent_event)
        return True

    def set_invisible(self, value: bool, parent_event: Optional[UUID] = None, *, publish: bool = True) -> bool:
        """Commit invisibility; a condition may publish its change after membership."""
        if self.is_invisible is value:
            return False
        self.is_invisible = value
        if publish:
            self._notify_perceivability_changed(parent_event=parent_event)
        return True

    def _notify_perceivability_changed(self, parent_event: Optional[UUID] = None) -> None:
        """Fire a SPATIAL_PERCEIVABILITY_CHANGED event at this block's position.

        Candidate observers subscribed to this cell are re-evaluated by the
        spatial senses reducer. Does not trigger SpatialHandlers (zone effects).
        """
        event = SpatialChangeEvent.perceivability_changed(self.position, self.uuid, parent_event=parent_event)
        current = EventQueue.register(event)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.EXECUTION)
        current = EventQueue.register(current)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.EFFECT)
        current = EventQueue.register(current)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.COMPLETION)
        EventQueue.register(current)

    def get_passive_perception(self) -> int:
        """Return passive perception for this block as an observer."""
        return 0

    def has_ordinary_visual_sight(self) -> bool:
        """Return whether this block has ordinary visual sight."""
        return False

    def get_sense_modes(self) -> List[SenseMode]:
        """Return sense modes for this block as an observer."""
        return []

    def get_item_wearer_values(self) -> Optional[ItemWearerValues]:
        """Actors expose the accepted wearer property channels through this capability."""
        return None

    def get_senses(self) -> Optional[SensesView]:
        """Override in Entity to return Senses block for subjective perception."""
        return None

    def is_object_known_to(self, observer_uuid: UUID) -> bool:
        """Explicit authored knowledge; ordinary entities grant no object contact."""
        return False

    def get_item_control_link(self) -> Optional[ControlLink]:
        """Return a handle's valid authored item connection, if it owns one."""
        return None

    @property
    def is_active(self) -> bool:
        """Whether this block is active and should be included in interactions.
        Default True. Override in Entity/BaseItem for health-aware checks."""
        return True

    def can_take_actions(self) -> bool:
        """Return whether this block may originate ordinary actions.

        Non-entity blocks are permitted by default. Entity overrides this using
        its neutral action-permission capability.
        """
        return True

    def has_runtime_agency(self) -> bool:
        """Whether this live owner may initiate any action, including reactions."""
        return True

    def allows_action_channels(self, channels: AbstractSet[ActionEconomyCostType]) -> bool:
        return True

    def record_action_channels(self, channels: AbstractSet[ActionEconomyCostType]) -> None:
        """Non-actor blocks have no action economy to record."""

    def can_afford_action_resource(
        self,
        resource_name: str,
        amount: int,
    ) -> bool:
        """Return whether this block can pay a named action resource.

        Only owners with an action economy override this neutral boundary.
        """
        return False

    def get_hp(self) -> int:
        """Override in Entity/BaseItem to return current HP. Default: 0 (no health system)."""
        return 0

    def attach_light_source(self, light_source_uuid: UUID) -> None:
        """Track a light source attached to this block (for cleanup)."""
        self._attached_light_sources.add(light_source_uuid)

    def detach_light_source(self, light_source_uuid: UUID) -> None:
        """Stop tracking a light source."""
        self._attached_light_sources.discard(light_source_uuid)

    def get_attached_light_sources(self) -> Set[UUID]:
        """Get all light sources attached to this block."""
        return self._attached_light_sources.copy()

    def is_enemy_of(self, other_uuid: UUID) -> bool:
        """Whether this block considers other_uuid an enemy.
        Default: True (unknown blocks are enemies).
        Entity overrides with faction-based logic."""
        return True

    def is_hazardous_for(
        self, entity_uuid: Optional[UUID] = None, *,
        occupancy_layer: OccupancyLayer = OccupancyLayer.GROUND,
    ) -> bool:
        """Return whether active hazard conditions affect an optional entity."""
        for cond in self.active_conditions.values():
            if cond.hazard_filter is None or not cond.affects_occupancy_layer(occupancy_layer):
                continue

            if cond.condition_stealth_dc is not None and entity_uuid is not None:
                observer = BaseBlock.get(entity_uuid)
                if observer is not None and cond.condition_stealth_dc >= observer.get_passive_perception():
                    continue

            if cond.hazard_filter == HazardFilter.ALL:
                return True
            if cond.hazard_filter == HazardFilter.NON_SOURCE and entity_uuid != cond.source_entity_uuid:
                return True
            if cond.hazard_filter == HazardFilter.ENEMIES and entity_uuid is not None:
                observer = BaseBlock.get(entity_uuid)
                if observer is not None and observer.is_enemy_of(cond.source_entity_uuid):
                    return True

        return False

    def set_target_entity(self, target_entity_uuid: UUID, target_entity_name: Optional[str] = None) -> None:
        """Set target identity on this block, direct values, and child blocks.

        Args:
            target_entity_uuid: UUID of the target entity.
            target_entity_name: Optional display name for the target entity.

        Raises:
            ValueError: If `target_entity_uuid` is not a UUID.
        """
        if not isinstance(target_entity_uuid, UUID):
            raise ValueError("target_entity_uuid must be a UUID")

        self.target_entity_uuid = target_entity_uuid
        self.target_entity_name = target_entity_name

        for value in self.values.values():
            value.set_target_entity(target_entity_uuid, target_entity_name)

        for block in self.blocks.values():
            block.set_target_entity(target_entity_uuid, target_entity_name)

    def clear_target_entity(self) -> None:
        """Clear target identity on this block, direct values, and children."""
        for value in self.values.values():
            value.clear_target_entity()

        for block in self.blocks.values():
            block.clear_target_entity()

        self.target_entity_uuid = None
        self.target_entity_name = None

    def set_context(self, context: Dict[str, Any]) -> None:
        """Set runtime context on this block, direct values, and children.

        Args:
            context: Context dictionary to propagate.
        """
        self.context = context

        for value in self.values.values():
            value.set_context(context)

        for block in self.blocks.values():
            block.set_context(context)

    def clear_context(self) -> None:
        """Clear runtime context on this block, direct values, and children."""
        self.context = None

        for value in self.values.values():
            value.clear_context()

        for block in self.blocks.values():
            block.clear_context()

    def clear(self) -> None:
        """Clear target identity and context from this block tree."""
        self.clear_target_entity()
        self.clear_context()

    def remove_contained_item(self, item_uuid: UUID, *, parent_event: Event | None = None,
                              reason: ItemReleaseReason = ItemReleaseReason.TRANSFERRED) -> bool:
        """Remove a contained item by UUID.

        Args:
            item_uuid: UUID of the item to remove.

        The base implementation is a no-op. Inventory overrides this hook.
        """
        return False

    def owned_child_blocks(self) -> tuple['BaseBlock', ...]:
        """Return direct composition edges, including explicitly owned typed lists."""
        return tuple(self.blocks.values())

    @classmethod
    def prepared_condition_terminal_release(cls, condition_uuid: UUID) -> TerminalOwnerRelease | None:
        """Return the mandatory owner only for an already admitted condition."""
        release = cls._terminal_release.get()
        accepted = cls._accepted_condition_removals.get()
        if release is None or not release.mandatory or accepted is None or condition_uuid not in accepted:
            return None
        return release

    def permits_terminal_retirement(self, release: TerminalOwnerRelease) -> bool:
        """Ordinary world blocks are never implicitly owned by a departing actor."""
        return False

    def owned_values(self) -> tuple[ModifiableValue, ...]:
        """Return exact values whose local channels belong to this block."""
        return tuple(self.values.values())

    def owned_block_tree(self, *, excluded_uuids: frozenset[UUID] = frozenset()) -> tuple['BaseBlock', ...]:
        """Snapshot exact composition edges, never mutable source-identity matches."""
        pending: list[BaseBlock] = [self]
        result: dict[UUID, BaseBlock] = {}
        while pending:
            block = pending.pop()
            if block.uuid in result or block.uuid in excluded_uuids:
                continue
            result[block.uuid] = block
            pending.extend(block.owned_child_blocks())
        return tuple(result.values())

    def release_runtime_ownership(self) -> None:
        """Release this exact block after its conditions and possessions were settled."""
        if self.active_conditions_by_uuid:
            raise RuntimeError("Cannot release a block with active conditions")
        for handler in tuple(self.event_handlers.values()):
            self.remove_event_handler(handler)
            handler.remove_from_register()
        for value in {value.uuid: value for value in self.owned_values()}.values():
            value.retire_owned_state()
        BaseBlock.unregister(self.uuid)

    def on_owned_item_destroyed(
        self,
        item: 'BaseBlock',
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Allow a high-level owner to publish facts after item cleanup.

        BaseItem invokes this hook only after container membership, equipment
        hooks, and floor placement have been cleared. Entity overrides it to
        publish aggregate item/AC state without requiring BaseItem or Equipment
        to import upward. Other blocks return ``False`` so the item publishes a
        dependency-neutral destruction fact itself.

        Args:
            item: Destroyed item block, still available until its final registry
                removal.
            parent_event: Optional causal event that destroyed the item.

        Returns:
            True when the owner published the destruction fact.
        """
        return False

    def on_grid_object_placed(self, placement: WorldObjectPlacement) -> None:
        """Synchronize floor-aware provider data before spatial completion."""
        pass

    def on_grid_object_removed(self, position: Tuple[int, int], clear_location: bool = True, parent_event: Optional[Event] = None) -> None:
        """React after this block is removed from GridMap object indexes.

        Args:
            position: Grid position the object occupied before removal.
            clear_location: Whether the removal represents an authoritative
                location clear instead of an internal reindexing step.

        The base implementation is a no-op. Floor-aware subclasses override
        this hook to synchronize their own location fields.
        """
        pass

    def on_world_placement_committed(self, event: Event) -> None:
        """Let active condition owners settle inside the committed spatial cause."""
        for condition in tuple(self.active_conditions.values()):
            condition.on_owner_placement_committed(event)

    def get_position(self) -> Tuple[int, int]:
        """Return this block's current objective position value."""
        return self.position

    def get_occupancy_layer(self) -> OccupancyLayer:
        """Non-creature blocks occupy their authored support."""
        return OccupancyLayer.GROUND

    def snapshot_entity_stats(self) -> Optional[EntityStatsState]:
        """Non-actor components do not publish entity combat statistics."""
        return None

    def snapshot_world_tile(self) -> Optional[WorldTileState]:
        """Only a Tile publishes evaluated terrain after-values."""
        return None

    def snapshot_item_state(self) -> Optional[ItemPresentationState]:
        """Only an item publishes an item after-value for condition changes."""
        return None

    def on_object_section_removed(self, volume: ObjectSectionVolume, parent_event: Event) -> None:
        """An existing geometry owner may publish its now-cut physical shell."""

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        """Return the neutral one-band center placement capability."""
        return WorldPlacementSpec(
            kind=WorldPlacementKind.CENTER,
            occupies_bands=False,
            vertical_extent_steps=1,
        )

    def get_boundary_structure(self) -> Optional[BoundaryStructure]:
        """Return current boundary mechanics when this block provides them."""
        return None

    @classmethod
    def create(cls, source_entity_uuid: UUID, source_entity_name: Optional[str] = None,
                target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None,
                name: str = "Base Block") -> 'BaseBlock':
        """Create a base block with identity fields.

        Args:
            source_entity_uuid: UUID of the source entity.
            source_entity_name: Optional display name of the source entity.
            target_entity_uuid: Optional UUID of the target entity.
            target_entity_name: Optional display name of the target entity.
            name: Block name.

        Returns:
            Newly created block.
        """
        return cls(source_entity_uuid=source_entity_uuid, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, name=name)

    @computed_field
    @property
    def values_dict_uuid_name(self) -> Dict[UUID, str]:
        """Map direct value UUIDs to value names.

        Returns:
            Value names keyed by UUID.
        """
        return {value.uuid: value.name for value in self.get_values()}

    @computed_field
    @property
    def values_dict_name_uuid(self) -> Dict[str, UUID]:
        """Map direct value names to value UUIDs.

        Returns:
            Value UUIDs keyed by name.
        """
        return {value.name: value.uuid for value in self.get_values()}

    @computed_field
    @property
    def blocks_dict_uuid_name(self) -> Dict[UUID, str]:
        """Map direct child block UUIDs to block names.

        Returns:
            Child block names keyed by UUID.
        """
        return {block.uuid: block.name for block in self.get_blocks()}

    @computed_field
    @property
    def blocks_dict_name_uuid(self) -> Dict[str, UUID]:
        """Map direct child block names to block UUIDs.

        Returns:
            Child block UUIDs keyed by name.
        """
        return {block.name: block.uuid for block in self.get_blocks()}

    def get_value_from_uuid(self, uuid: UUID) -> Optional[ModifiableValue]:
        """Return a direct value by UUID.

        Args:
            uuid: UUID of the direct value to retrieve.

        Returns:
            Matching direct value, or `None`.
        """
        return self.values.get(uuid)

    def get_value_from_name(self, name: str) -> Optional[ModifiableValue]:
        """Return a direct value by name.

        Args:
            name: Name of the direct value to retrieve.

        Returns:
            Matching direct value, or `None`.
        """
        for value in self.values.values():
            if value.name == name:
                return value
        return None

    def get_block_from_uuid(self, uuid: UUID) -> Optional['BaseBlock']:
        """Return a direct child block by UUID.

        Args:
            uuid: UUID of the direct child block to retrieve.

        Returns:
            Matching direct child block, or `None`.
        """
        return self.blocks.get(uuid)

    def get_block_from_name(self, name: str) -> Optional['BaseBlock']:
        """Return a direct child block by name.

        Args:
            name: Name of the direct child block to retrieve.

        Returns:
            Matching direct child block, or `None`.
        """
        for block in self.blocks.values():
            if block.name == name:
                return block
        return None

    def add_event_handler(self, event_handler: EventHandler) -> None:
        """Own and register an event handler when lifecycle is enabled.

        Args:
            event_handler: Handler to add to this block and `EventQueue`.
        """
        if not self.allow_events_conditions:
            return None
        bind_runtime_handler_before_admission(
            event_handler,
            current_binding=event_handler.behavior_binding,
            runtime_owner_uuid=event_handler.source_entity_uuid,
        )
        event_handler.owner_block = self
        self.event_handlers[event_handler.uuid] = event_handler
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                self.event_handlers_by_simple_trigger[trigger].append(event_handler)
            self.event_handlers_by_trigger[trigger].append(event_handler)
        EventQueue.add_event_handler(event_handler)

    def remove_event_handler_from_dicts(self, event_handler: EventHandler) -> None:
        """Remove a handler from this block's local indexes.

        Args:
            event_handler: Handler to remove from block-local storage.
        """
        if not self.allow_events_conditions:
            return None
        self.event_handlers.pop(event_handler.uuid)
        for trigger in event_handler.trigger_conditions:
            if trigger.is_simple():
                self.event_handlers_by_simple_trigger[trigger].remove(event_handler)
            self.event_handlers_by_trigger[trigger].remove(event_handler)

    def remove_event_handler(self, event_handler: EventHandler) -> None:
        """Remove a handler from the queue and this block's local indexes.

        Args:
            event_handler: Handler to remove.
        """
        if not self.allow_events_conditions:
            return None
        EventQueue.remove_event_handler(event_handler)
        if event_handler.uuid in self.event_handlers:
            self.remove_event_handler_from_dicts(event_handler)

    def set_event_handler_order(self, ordered_uuids: Tuple[UUID, ...]) -> None:
        """Reorder this block's existing handlers without changing ownership."""
        if len(set(ordered_uuids)) != len(ordered_uuids):
            raise ValueError("block event handler order contains duplicate UUIDs")
        if set(ordered_uuids) != set(self.event_handlers):
            raise ValueError("block event handler order must name every handler")
        order = {handler_uuid: index for index, handler_uuid in enumerate(ordered_uuids)}
        handlers = dict(self.event_handlers)
        self.event_handlers.clear()
        self.event_handlers.update(
            (handler_uuid, handlers[handler_uuid])
            for handler_uuid in ordered_uuids
        )
        for index in (
            self.event_handlers_by_trigger,
            self.event_handlers_by_simple_trigger,
        ):
            for rows in index.values():
                rows.sort(key=lambda handler: order[handler.uuid])

    def get_event_handler_by_name(self, name: str) -> Optional[EventHandler]:
        """Find the first local event handler matching a name.

        Args:
            name: Handler name to match case-insensitively.

        Returns:
            First matching handler, or `None`.
        """
        name_lower = name.lower()
        for handler in self.event_handlers.values():
            if handler.name.lower() == name_lower:
                return handler
        return None

    def get_event_handlers_by_name(self, name: str) -> List[EventHandler]:
        """Find all local event handlers matching a name.

        Args:
            name: Handler name to match case-insensitively.

        Returns:
            Matching handlers in local storage order.
        """
        name_lower = name.lower()
        return [h for h in self.event_handlers.values() if h.name.lower() == name_lower]

    def set_handler_enabled(self, name: str, enabled: bool) -> bool:
        """Set enabled state on the first matching player-toggleable handler.

        Args:
            name: Handler name to match case-insensitively.
            enabled: New enabled state.

        Returns:
            True if a player-toggleable matching handler was updated.
        """
        handler = self.get_event_handler_by_name(name)
        if handler is not None and handler.player_toggleable:
            handler.enabled = enabled
            return True
        return False

    def set_handler_enabled_by_uuid(self, handler_uuid: UUID, enabled: bool) -> bool:
        """Set enabled state on a player-toggleable handler by UUID.

        Args:
            handler_uuid: UUID of the local handler to update.
            enabled: New enabled state.

        Returns:
            True if a player-toggleable handler was updated.
        """
        handler = self.event_handlers.get(handler_uuid)
        if handler is not None and handler.player_toggleable:
            handler.enabled = enabled
            return True
        return False

    def _discard_condition_indexes(self, condition: BaseCondition) -> None:
        """Remove one exact condition from this block's local indexes.

        Args:
            condition: Condition to remove from index dictionaries.
        """
        if not self.allow_events_conditions:
            return None
        condition_name = condition.name
        if (
            condition_name is not None
            and self.active_conditions.get(condition_name) is condition
        ):
            self.active_conditions.pop(condition_name)
        if self.active_conditions_by_uuid.get(condition.uuid) is condition:
            self.active_conditions_by_uuid.pop(condition.uuid)
        if condition_name is not None:
            source_rows = self.active_conditions_by_source.get(
                condition.source_entity_uuid,
            )
            if source_rows is not None and condition_name in source_rows:
                source_rows.remove(condition_name)

    def _discard_uncommitted_condition_tree(
        self,
        condition: BaseCondition,
    ) -> None:
        """Discard provisional condition mechanics without removal events."""
        for sub_uuid in list(condition.sub_conditions):
            sub_condition = BaseCondition.get(sub_uuid)
            if isinstance(sub_condition, BaseCondition):
                if sub_condition.has_surviving_parent({condition.uuid}):
                    continue
                self._discard_condition_indexes(sub_condition)
                self._discard_uncommitted_condition_tree(sub_condition)

        for target_uuid, child_uuid in list(condition.linked_conditions):
            target_block = BaseBlock.get(target_uuid)
            child_condition = BaseCondition.get(child_uuid)
            if (
                isinstance(target_block, BaseBlock)
                and isinstance(child_condition, BaseCondition)
            ):
                target_block._discard_condition_indexes(child_condition)
                target_block._discard_uncommitted_condition_tree(
                    child_condition,
                )
            elif isinstance(child_condition, BaseCondition):
                child_condition.discard_from_runtime_owner()

        condition.discard_uncommitted_runtime_state()
        self._discard_condition_indexes(condition)
        condition.remove_from_register()

    def remove_condition(self, condition_name: str, expire: bool = False,
                         parent_event: Optional[Event] = None, *, consumed: bool = False,
                         terminal_release: TerminalOwnerRelease | None = None) -> bool:
        """Remove a condition with full cross-block tree traversal.

        Handles sub-conditions (same block), linked_conditions (other blocks),
        and own state cleanup via _remove_condition_tree().

        Args:
            condition_name: Name of the condition to remove.
            expire: Whether this is an expiration removal.
            parent_event: Parent event for event-chain tracking.
            consumed: Whether the root condition was spent, excluding linked cleanup.
        """
        if not self.allow_events_conditions:
            return False
        if condition_name not in self.active_conditions:
            return False

        condition = self.active_conditions[condition_name]
        return self._remove_condition_tree(
            condition,
            expire=expire,
            parent_event=parent_event,
            consumed=consumed,
            terminal_release=terminal_release,
        )

    def remove_condition_by_uuid(self, condition_uuid: UUID,
                                 parent_event: Optional[Event] = None, *, consumed: bool = False,
                                 terminal_release: TerminalOwnerRelease | None = None) -> bool:
        """Remove a condition by UUID.

        Args:
            condition_uuid: UUID of the condition to remove.
            parent_event: Optional parent event for cleanup event lineage.
        """
        if not self.allow_events_conditions:
            return False
        condition = self.active_conditions_by_uuid.get(condition_uuid)
        if condition is None:
            return False
        if condition.name is not None:
            return self.remove_condition(
                condition.name,
                parent_event=parent_event,
                consumed=consumed,
                terminal_release=terminal_release,
            )
        return False

    @classmethod
    def prepare_owned_condition_removals(
        cls, owners: tuple["BaseBlock", ...], *, parent_event: Event | None,
        terminal_release: TerminalOwnerRelease | None = None,
        excluded_condition_uuids: frozenset[UUID] = frozenset(),
    ) -> PreparedConditionRemovals | None:
        """Prepare the exact ending aggregate's remaining condition memberships."""
        if terminal_release is not None and any(
            owner.uuid != terminal_release.entity_uuid
            and owner.source_entity_uuid != terminal_release.entity_uuid
            for owner in owners
        ):
            raise ValueError("Terminal release cannot remove an unrelated owner's conditions")
        prepared = PreparedConditionRemovals([], terminal_release)
        visited = set(excluded_condition_uuids)
        try:
            with cls.condition_removal_scope(terminal_release=terminal_release):
                for owner in owners:
                    for condition in tuple(owner.active_conditions_by_uuid.values()):
                        canceled = cls._prepare_condition_removal_tree(
                            condition, condition_owner=owner, expire=False,
                            parent_event=parent_event, prepared=prepared.entries, visited=visited,
                            mandatory=terminal_release is not None and terminal_release.mandatory,
                        )
                        if canceled is not None:
                            cls._cancel_prepared_condition_removals(prepared.entries, canceled)
                            return None
        except BaseException as failure:
            try:
                cls.cancel_owned_condition_removals(prepared, "Owned condition removal admission raised")
            except BaseException as cleanup:
                raise BaseExceptionGroup("Owned removal admission and cancellation failed", [failure, cleanup]) from failure
            raise
        return prepared

    @classmethod
    def commit_owned_condition_removals(cls, prepared: PreparedConditionRemovals) -> None:
        if prepared.canceled:
            raise ValueError("Canceled removals cannot commit")
        if prepared.committed_result is not None:
            return
        if cls._removal_scope.get() is None:
            raise RuntimeError("Prepared removal commitment requires condition_removal_scope")
        with cls.condition_removal_scope(terminal_release=prepared.terminal_release):
            prepared.committed_result = cls._commit_prepared_condition_removals(prepared.entries, publish=False)

    @classmethod
    def publish_owned_condition_removals(cls, prepared: PreparedConditionRemovals) -> None:
        if prepared.committed_result is None:
            raise ValueError("Condition removals were not committed")
        cls._publish_committed_condition_removals(prepared.committed_result)

    @classmethod
    def cancel_owned_condition_removals(cls, prepared: PreparedConditionRemovals, reason: str) -> None:
        if prepared.committed_result is not None:
            raise RuntimeError("Committed removals cannot be canceled")
        if prepared.canceled:
            return
        prepared.canceled = True
        errors: list[BaseException] = []
        for _, condition, effect, _ in reversed(prepared.entries):
            if condition.applied:
                try:
                    BaseBlock._cancel_native_condition_removal(condition, reason)
                except BaseException as error:
                    errors.append(error)
                try:
                    effect.cancel(status_message=reason)
                except BaseException as error:
                    errors.append(error)
        if errors:
            raise BaseExceptionGroup("Prepared removal cleanup failed", errors)

    def _remove_condition_tree(self, condition: BaseCondition, expire: bool = False,
                               parent_event: Optional[Event] = None, *, consumed: bool = False,
                               terminal_release: TerminalOwnerRelease | None = None) -> bool:
        """Admit and commit one complete graph, then settle its consequences."""
        if terminal_release is not None and (
            terminal_release.entity_uuid != self.uuid
            or terminal_release.existence_condition_uuid != condition.uuid
        ):
            raise ValueError("Terminal release does not identify this exact existence owner")
        with self.condition_removal_scope(terminal_release=terminal_release):
            prepared: list[tuple[BaseBlock | None, BaseCondition, Event, bool]] = []
            try:
                canceled = self._prepare_condition_removal_tree(
                    condition, condition_owner=self, expire=expire,
                    parent_event=parent_event, prepared=prepared, visited=set(),
                    consumed=consumed,
                    mandatory=terminal_release is not None and terminal_release.mandatory,
                )
                if canceled is not None:
                    self._cancel_prepared_condition_removals(prepared, canceled)
                    return False
                if not self.validate_prepared_condition_removals(prepared):
                    self.cancel_owned_condition_removals(PreparedConditionRemovals(prepared),
                        "Condition removal destinations conflict or changed")
                    return False
            except BaseException:
                self.cancel_owned_condition_removals(PreparedConditionRemovals(prepared), "Condition removal admission raised")
                raise
            self._commit_prepared_condition_removals(prepared)
            return True

    @staticmethod
    def _cancel_prepared_condition_removals(
        prepared: List[
            Tuple[Optional['BaseBlock'], BaseCondition, Event, bool]
        ],
        canceled: Event,
    ) -> None:
        """Close accepted removal effects without mutating condition state."""
        reason = canceled.status_message or "Dependent condition removal was canceled"
        errors: list[BaseException] = []
        for _, condition, effect, _ in reversed(prepared):
            if not condition.applied:
                continue
            try:
                BaseBlock._cancel_native_condition_removal(condition, reason)
            except BaseException as error:
                errors.append(error)
            parent = EventQueue.get_event_by_uuid(effect.parent_event) if effect.parent_event is not None else None
            for event in (effect, parent):
                if event is not effect and event is not None and event.event_type is not EventType.CONDITION_REMOVAL:
                    continue
                if event is not None and not event.canceled:
                    try:
                        event.cancel(status_message=reason)
                    except BaseException as error:
                        errors.append(error)
        if errors:
            raise BaseExceptionGroup("Prepared removal cleanup failed", errors)

    @classmethod
    def _commit_prepared_condition_removals(
        cls, prepared: list[tuple["BaseBlock | None", BaseCondition, Event, bool]],
        *, publish: bool = True,
    ) -> CommittedConditionRemovals:
        """Commit accepted children before parents; publication may follow birth."""
        if cls._removal_scope.get() is None:
            if not publish:
                raise RuntimeError("Unpublished removals require an outer condition_removal_scope")
            with cls.condition_removal_scope():
                return cls._commit_prepared_condition_removals(prepared, publish=True)
        if not cls.validate_prepared_condition_removals(prepared):
            raise RuntimeError("Prepared condition removal no longer matches native state")
        result = CommittedConditionRemovals()
        linked_owners: dict[UUID, tuple[BaseCondition, BaseBlock, ConditionState, EntityStatsState | None, Event]] = {}
        for _, condition, event, _ in prepared:
            if condition.parent_link is None:
                continue
            owner_uuid, parent_uuid = condition.parent_link
            parent = BaseCondition.get(parent_uuid)
            owner = BaseBlock.get(owner_uuid)
            if isinstance(parent, BaseCondition) and owner is not None:
                linked_owners.setdefault(parent_uuid, (parent, owner, parent.snapshot_state(),
                    owner.snapshot_entity_stats(), event))
        for owner, condition, removal_effect, expire in reversed(prepared):
            if not condition.applied:
                continue
            accepted = cls._accepted_condition_removals.get()
            if accepted is not None:
                accepted.pop(condition.uuid, None)
            if owner is None:
                if not condition.remove_from_runtime_owner(
                    expire=expire, parent_event=removal_effect,
                    prepared_removal_effect=removal_effect,
                    publish=False,
                ):
                    raise RuntimeError("Accepted independent condition removal failed")
                result.removals.append(ConditionPublication(condition, removal_effect,
                    condition.snapshot_state(), None, None, None, {}, independent_owner=True))
                continue
            removed = condition.cleanup_own_state(
                expire=expire, parent_event=removal_effect, removal_effect=removal_effect,
            )
            if removed is None or removed.canceled:
                raise RuntimeError("Accepted condition removal failed during owned-state cleanup")
            owner._discard_condition_indexes(condition)
            for participant in tuple(cls._removal_participants.values()):
                participant.commit_condition_removal(owner.uuid, condition.uuid)
            if condition.parent_link is not None:
                _, parent_condition_uuid = condition.parent_link
                parent_condition = BaseCondition.get(parent_condition_uuid)
                if isinstance(parent_condition, BaseCondition):
                    parent_condition.unlink_condition(condition.uuid, parent_event=removed)
            condition.remove_from_register()
            scope = cls._removal_scope.get()
            assert scope is not None
            scope.receipts.append(ConditionRemovalReceipt(
                owner_uuid=owner.uuid, condition_uuid=condition.uuid,
                removal_event_uuid=removed.uuid, terminal_release=cls._terminal_release.get(),
                involuntary_loss=cls._involuntary_loss.get(),
            ))
            result.removals.append(ConditionPublication(
                condition, removed, condition.snapshot_state(), owner.snapshot_entity_stats(),
                owner.snapshot_world_tile(), owner.snapshot_item_state(), condition._post_removal_stats(),
            ))
        result.linked_owners = list(linked_owners.values())
        if publish:
            cls._publish_committed_condition_removals(result)
        return result

    @classmethod
    def prepared_return_reservations(cls) -> frozenset[tuple[int, int]]:
        """Destinations already admitted in the current condition-removal graph."""
        accepted = cls._accepted_condition_removals.get()
        return frozenset(position for _, condition, _, _ in (accepted or {}).values()
                         for position in condition.prepared_removal_occupancies())

    @classmethod
    def validate_prepared_condition_removals(
        cls, prepared: list[tuple["BaseBlock | None", BaseCondition, Event, bool]],
    ) -> bool:
        """Reject conflicting native return destinations before any owner changes."""
        occupied: set[tuple[int, int]] = set()
        for _, condition, _, _ in prepared:
            if not condition.applied:
                continue
            if not condition.validate_prepared_removal():
                return False
            if any(not participant.validate_condition_removal(condition.uuid)
                   for participant in tuple(cls._removal_participants.values())):
                return False
            positions = set(condition.prepared_removal_occupancies())
            if occupied & positions:
                return False
            occupied.update(positions)
        return True

    @staticmethod
    def _complete_condition_removal(row: ConditionPublication) -> None:
        if row.independent_owner:
            row.condition.publish_runtime_owner_removal(row.effect)
            return
        row.effect.phase_to(EventPhase.COMPLETION, condition_state=row.condition_state,
            resulting_stats=row.resulting_stats, resulting_tile=row.resulting_tile,
            resulting_item=row.resulting_item, **row.post_removal_stats)

    @classmethod
    def _publish_committed_condition_removals(cls, committed: CommittedConditionRemovals) -> None:
        """Publish each committed removal once, attempting all despite an observer failure."""
        if committed.published:
            return
        committed.published = True
        errors: list[BaseException] = []
        for row in committed.removals:
            if row.independent_owner:
                try:
                    scope = cls._removal_scope.get()
                    if scope is None:
                        cls._complete_condition_removal(row)
                    else:
                        scope.completions.append(row)
                except BaseException as error:
                    errors.append(error)
                continue
            if not row.effect.use_register:
                try:
                    row.effect = EventQueue.publish_committed_phase(row.effect)
                except BaseException as error:
                    errors.append(error)
            try:
                row.condition.on_membership_changed(row.effect)
            except BaseException as error:
                errors.append(error)
            try:
                scope = cls._removal_scope.get()
                if scope is None:
                    cls._complete_condition_removal(row)
                else:
                    scope.completions.append(row)
            except BaseException as error:
                errors.append(error)
        for parent, owner, previous_state, previous_stats, event in committed.linked_owners:
            if (parent.applied and owner.active_conditions_by_uuid.get(parent.uuid) is parent
                    and (parent.snapshot_state() != previous_state
                         or owner.snapshot_entity_stats() != previous_stats)):
                try:
                    parent.publish_owner_state(event)
                except BaseException as error:
                    errors.append(error)
        if errors:
            raise BaseExceptionGroup("Committed condition removal publication failed", errors)

    @classmethod
    def _prepare_condition_removal_tree(
        cls,
        condition: BaseCondition,
        *,
        condition_owner: Optional['BaseBlock'],
        expire: bool,
        parent_event: Optional[Event],
        prepared: List[
            Tuple[Optional['BaseBlock'], BaseCondition, Event, bool]
        ],
        visited: Set[UUID],
        consumed: bool = False,
        mandatory: bool = False,
    ) -> Optional[Event]:
        """Accept one graph's removal phases without mutating mechanics."""
        if condition.uuid in visited:
            return None
        visited.add(condition.uuid)

        accepted = cls._accepted_condition_removals.get()
        reused = accepted.get(condition.uuid) if accepted is not None else None
        if reused is not None:
            effect = reused[2]
            prepared.append(reused)
        else:
            try:
                if mandatory:
                    effect = condition._declare_removal_event(
                        expired=expire, parent_event=parent_event, consumed=consumed,
                    ).model_copy(update={"phase": EventPhase.EFFECT})
                    effect = condition.prepare_removal_state(effect)
                else:
                    declaration = EventQueue.publish_declaration(
                        condition._declare_removal_event(
                            expired=expire, parent_event=parent_event, consumed=consumed,
                        ),
                    )
                    if declaration.canceled:
                        cls._cancel_native_condition_removal(condition, "Condition removal rejected")
                        return declaration
                    effect = condition.publish_removal_effect(declaration)
                if effect.canceled:
                    cls._cancel_native_condition_removal(condition, "Condition removal rejected")
                    return effect
                for participant in tuple(cls._removal_participants.values()):
                    if not participant.prepare_condition_removal(
                        condition_owner.uuid if condition_owner is not None else None,
                        condition.uuid, effect, cls._terminal_release.get(), cls._involuntary_loss.get(),
                    ):
                        cls._cancel_native_condition_removal(condition, "Native owner removal rejected")
                        if mandatory:
                            raise RuntimeError("Mandatory native owner retirement was not admitted")
                        return effect.cancel(status_message="Native owner removal rejected")
            except BaseException:
                cls._cancel_native_condition_removal(condition, "Condition removal admission raised")
                raise
            entry = (condition_owner, condition, effect, expire)
            prepared.append(entry)
            if accepted is not None:
                accepted[condition.uuid] = entry

        for child_uuid in list(condition.sub_conditions):
            child = BaseCondition.get(child_uuid)
            if isinstance(child, BaseCondition) and child.applied:
                if child.has_surviving_parent(visited):
                    continue
                if child.is_active_spatial_condition():
                    child_owner = None
                else:
                    resolved_owner = (
                        BaseBlock.get(child.target_entity_uuid)
                        if child.target_entity_uuid is not None else None
                    )
                    child_owner = (
                        resolved_owner
                        if isinstance(resolved_owner, BaseBlock)
                        else condition_owner
                    )
                canceled = cls._prepare_condition_removal_tree(
                    child,
                    condition_owner=child_owner,
                    expire=expire,
                    parent_event=effect,
                    prepared=prepared,
                    visited=visited,
                    mandatory=mandatory,
                )
                if canceled is not None:
                    return canceled

        for target_uuid, child_uuid in list(condition.linked_conditions):
            target = BaseBlock.get(target_uuid)
            child = BaseCondition.get(child_uuid)
            child_owner: Optional[BaseBlock] = None
            if isinstance(target, BaseBlock):
                indexed = target.active_conditions_by_uuid.get(child_uuid)
                child = indexed if isinstance(indexed, BaseCondition) else None
                child_owner = target
            elif not (
                isinstance(child, BaseCondition)
                and child.is_active_spatial_condition()
            ):
                child = None
            if isinstance(child, BaseCondition) and child.applied:
                canceled = cls._prepare_condition_removal_tree(
                    child,
                    condition_owner=child_owner,
                    expire=expire,
                    parent_event=effect,
                    prepared=prepared,
                    visited=visited,
                    mandatory=mandatory,
                )
                if canceled is not None:
                    return canceled

        if condition.parent_link is not None:
            parent_block_uuid, parent_condition_uuid = condition.parent_link
            parent_block = BaseBlock.get(parent_block_uuid)
            parent_condition = BaseCondition.get(parent_condition_uuid)
            parent_is_independent_spatial = (
                isinstance(parent_condition, BaseCondition)
                and parent_condition.is_active_spatial_condition()
                and parent_block_uuid == parent_condition.uuid
            )
            if (
                isinstance(parent_condition, BaseCondition)
                and (
                    isinstance(parent_block, BaseBlock)
                    or parent_is_independent_spatial
                )
                and parent_condition.applied
                and parent_condition.uuid not in visited
                and not mandatory
            ):
                policy = parent_condition.child_removal_policy
                remaining_children = sum(
                    1
                    for _, linked_uuid in parent_condition.linked_conditions
                    if linked_uuid not in visited
                    and (
                        linked := BaseCondition.get(linked_uuid)
                    ) is not None
                    and isinstance(linked, BaseCondition)
                    and linked.applied
                )
                if policy == "any" or (
                    policy == "last" and remaining_children == 0
                ):
                    canceled = cls._prepare_condition_removal_tree(
                        parent_condition,
                        condition_owner=(
                            parent_block
                            if isinstance(parent_block, BaseBlock)
                            else None
                        ),
                        expire=expire,
                        parent_event=effect,
                        prepared=prepared,
                        visited=visited,
                    )
                    if canceled is not None:
                        return canceled

        return None

    def advance_duration(self, condition_name: str, *,
                         interval: Optional[Tuple[UUID, int]] = None) -> bool:
        """Progress a block-owned condition duration without saving throws.

        Args:
            condition_name: Name of the condition to progress.

        Returns:
            True if the condition expired and was removed.
        """
        if not self.allow_events_conditions:
            return False
        condition = self.active_conditions.get(condition_name)
        if condition is None:
            return False
        expired = condition.progress_for_interval(interval)
        if expired:
            self.remove_condition(condition_name, expire=True)
        return expired

    def add_condition(self, condition: BaseCondition, context: Optional[Dict[str, Any]] = None, check_save_throw: bool = True, parent_event: Optional[Event] = None, *, required_condition: Optional[Tuple['BaseBlock', BaseCondition]] = None)  -> Optional[Event]:
        """Apply and index a condition when lifecycle is enabled.

        Args:
            condition: Condition to apply.
            context: Optional context to attach before applying.
            check_save_throw: Accepted for API symmetry; block-level condition
                application does not perform saving throws.
            parent_event: Optional causal parent for the application.
            required_condition: A sustainer that must succeed before replacement.

        Returns:
            Completion or cancellation event from condition application, or
            `None` when lifecycle is disabled.

        Raises:
            ValueError: If the condition has no name.
        """
        if required_condition is not None and required_condition[1].applied:
            raise ValueError("Required condition must be a fresh application")
        if not self.allow_events_conditions:
            return None
        if condition.name is None:
            raise ValueError("BaseCondition name is not set")
        if condition.target_entity_uuid is None:
            condition.target_entity_uuid = self.uuid
        bind_runtime_behavior(
            condition,
            current_binding=condition.behavior_binding,
            runtime_owner_uuid=self.uuid,
        )
        if context is not None:
            condition.set_context(context)

        declaration_event = EventQueue.publish_declaration(
            condition.declare_event(parent_event),
        )
        if declaration_event.canceled:
            self._discard_uncommitted_condition_tree(condition)
            return declaration_event

        return self._apply_declared_condition(condition, declaration_event, required_condition=required_condition)

    def _apply_declared_condition(self, condition: BaseCondition, declaration_event: Event, *,
                                  required_condition: Optional[Tuple['BaseBlock', BaseCondition]] = None) -> Optional[Event]:
        """Ordinary caller gates remain intact; all membership uses the shared seam."""
        with self.condition_removal_scope():
            prepared = self.prepare_condition_application(
                condition, declaration_event=declaration_event,
                required_condition=required_condition,
            )
            if not isinstance(prepared, PreparedConditionApplication):
                return prepared
            self.commit_condition_application(prepared)
            return self.publish_condition_application(prepared)

    def prepare_condition_application(
        self, condition: BaseCondition, *, declaration_event: Event | None = None,
        parent_event: Event | None = None,
        required_condition: tuple['BaseBlock', BaseCondition] | None = None,
    ) -> PreparedConditionApplication | Event | None:
        """Admit membership/replacement while retaining the previous live graph."""
        if not self.allow_events_conditions:
            return None
        if condition.name is None:
            raise ValueError("BaseCondition name is not set")
        if condition.applied:
            raise ValueError("Prepared applications require a fresh condition")
        prepared: PreparedConditionApplication | None = None
        try:
            if condition.target_entity_uuid is None:
                condition.set_target_entity(self.uuid)
            if declaration_event is None:
                bind_runtime_behavior(condition, current_binding=condition.behavior_binding,
                                      runtime_owner_uuid=self.uuid)
                declaration_event = EventQueue.publish_declaration(condition.declare_event(parent_event))
            if declaration_event.canceled:
                self._discard_uncommitted_condition_tree(condition)
                return declaration_event
            position = self.get_position()
            if (position is not None and condition.magical_origin and not condition.antimagic_exempt()
                    and ConditionTag.CONCENTRATION not in condition.tags):
                parent = BaseCondition.get(condition.parent_condition) if condition.parent_condition else None
                if not isinstance(parent, BaseCondition) or not parent.magical_origin:
                    condition.suppression_provider_uuids.update(row.provider_uuid for row in
                        SpellProtectionRegistry.get_antimagic_suppressions({position}))
            effect = condition.prepare_application(declaration_event=declaration_event)
            if effect is None or effect.canceled:
                self._discard_uncommitted_condition_tree(condition)
                return effect
            prepared = PreparedConditionApplication(self, condition, effect)
            previous = self.active_conditions.get(condition.name)
            if previous is not None and not condition.prepares_own_replacement():
                canceled = self._prepare_condition_removal_tree(previous, condition_owner=self,
                    expire=False, parent_event=effect, prepared=prepared.replacements, visited=set())
                if canceled is not None:
                    self.cancel_condition_application(prepared, canceled.status_message or "Replacement rejected")
                    return canceled
            if required_condition is not None:
                owner, requirement = required_condition
                accepted = dict(self._accepted_condition_removals.get() or {})
                accepted.update((entry[1].uuid, entry) for entry in prepared.replacements)
                token = self._accepted_condition_removals.set(accepted)
                try:
                    required = owner.prepare_condition_application(requirement, parent_event=effect)
                finally:
                    self._accepted_condition_removals.reset(token)
                if not isinstance(required, PreparedConditionApplication):
                    self.cancel_condition_application(prepared, "Required condition was not admitted")
                    return effect.cancel(status_message="Required condition was not admitted")
                prepared.required = required
            return prepared
        except BaseException as error:
            try:
                if prepared is None:
                    self._discard_uncommitted_condition_tree(condition)
                else:
                    self.cancel_condition_application(prepared, "Condition admission raised")
            except BaseException as cleanup_error:
                raise BaseExceptionGroup("Condition admission and cleanup failed", [error, cleanup_error]) from None
            raise

    def cancel_condition_application(self, prepared: PreparedConditionApplication, reason: str) -> None:
        if prepared.owner is not self:
            raise ValueError("Prepared application belongs to another owner")
        if prepared.committed:
            raise RuntimeError("Committed applications cannot be rolled back")
        if prepared.canceled:
            return
        prepared.canceled = True
        errors: list[BaseException] = []
        if prepared.required is not None:
            try:
                prepared.required.owner.cancel_condition_application(prepared.required, reason)
            except BaseException as error:
                errors.append(error)
        try:
            self._discard_uncommitted_condition_tree(prepared.condition)
        except BaseException as error:
            errors.append(error)
        try:
            self.cancel_owned_condition_removals(PreparedConditionRemovals(prepared.replacements), reason)
        except BaseException as error:
            errors.append(error)
        try:
            prepared.effect.cancel(status_message=reason)
        except BaseException as error:
            errors.append(error)
        if errors:
            raise BaseExceptionGroup("Condition admission cleanup failed", errors)

    def commit_condition_application(self, prepared: PreparedConditionApplication) -> None:
        """Commit already accepted state; caller's outer scope owns settlement."""
        if prepared.owner is not self or prepared.canceled:
            raise ValueError("Invalid prepared condition application")
        if prepared.committed:
            return
        if self._removal_scope.get() is None:
            raise RuntimeError("Prepared condition commitment requires condition_removal_scope")
        if (not prepared.condition.validate_prepared_removal()
                or not self.validate_prepared_condition_removals(prepared.replacements)):
            raise RuntimeError("Prepared condition replacement no longer matches native state")
        if prepared.required is not None:
            prepared.required.owner.commit_condition_application(prepared.required)
        remaining = [row for row in prepared.replacements if row[1].applied and (
            row[0] is None or row[0].active_conditions_by_uuid.get(row[1].uuid) is row[1])]
        prepared.removal_commit = self._commit_prepared_condition_removals(remaining, publish=False)
        prepared.condition.commit_prepared_application(prepared.effect)
        name = prepared.condition.name
        assert name is not None
        self.active_conditions[name] = prepared.condition
        self.active_conditions_by_uuid[prepared.condition.uuid] = prepared.condition
        self.active_conditions_by_source[prepared.condition.source_entity_uuid].append(name)
        prepared.publication = ConditionPublication(
            prepared.condition, prepared.effect, prepared.condition.snapshot_state(),
            self.snapshot_entity_stats(), self.snapshot_world_tile(), self.snapshot_item_state(), {},
        )
        prepared.committed = True

    def publish_condition_application(self, prepared: PreparedConditionApplication) -> Event:
        if prepared.owner is not self or not prepared.committed:
            raise ValueError("Only the committed owner may publish an application")
        if prepared.published:
            return prepared.completion or prepared.effect
        prepared.published = True
        errors: list[BaseException] = []
        if prepared.required is not None:
            try:
                prepared.required.owner.publish_condition_application(prepared.required)
            except BaseException as error:
                errors.append(error)
        if prepared.removal_commit is not None:
            try:
                self._publish_committed_condition_removals(prepared.removal_commit)
            except BaseException as error:
                errors.append(error)
        try:
            prepared.condition.publish_prepared_application()
        except BaseException as error:
            errors.append(error)
        try:
            prepared.condition.on_membership_changed(prepared.effect)
        except BaseException as error:
            errors.append(error)
        try:
            publication = prepared.publication
            assert publication is not None
            prepared.completion = prepared.effect.phase_to(
                EventPhase.COMPLETION, condition_state=publication.condition_state,
                resulting_stats=publication.resulting_stats, resulting_tile=publication.resulting_tile,
                resulting_item=publication.resulting_item,
            )
            prepared.condition.applied_source_event_cursor = EventQueue.event_cursor()
        except BaseException as error:
            errors.append(error)
        if errors:
            raise BaseExceptionGroup("Committed condition application publication failed", errors)
        return prepared.completion or prepared.effect

    def release_involuntary_sustain(self, loss: InvoluntarySustainLoss) -> bool:
        """Required links cannot retain authority after an actual involuntary loss."""
        sustainer = self.active_conditions_by_uuid.get(loss.sustaining_condition_uuid)
        parent = EventQueue.get_event_by_uuid(loss.parent_event_uuid)
        if sustainer is None or parent is None:
            return False
        links = sustainer.sustained_links_for_slot(loss.slot_uuid)
        with self.condition_removal_scope():
            loss_token = self._involuntary_loss.set(loss)
            try:
                for owner_uuid, condition_uuid in links:
                    owner = BaseBlock.get(owner_uuid)
                    condition = BaseCondition.get(condition_uuid)
                    if (owner is None or not isinstance(condition, BaseCondition)
                            or not condition.applied
                            or condition.sustain_loss_policy is not SustainLossPolicy.REQUIRED):
                        continue
                    terminal = condition.terminal_release_for_sustain_loss(loss)
                    with self.condition_removal_scope(terminal_release=terminal):
                        prepared: list[tuple[BaseBlock | None, BaseCondition, Event, bool]] = []
                        self._prepare_condition_removal_tree(condition, condition_owner=owner,
                            expire=False, parent_event=parent, prepared=prepared,
                            visited={sustainer.uuid}, mandatory=True)
                        self._commit_prepared_condition_removals(prepared)
                return sustainer.release_sustain_slot(loss.slot_uuid, parent_event=parent)
            finally:
                self._involuntary_loss.reset(loss_token)

    def add_static_condition_immunity(self, condition_name: str, immunity_name: Optional[str] = None) -> None:
        """Add a static condition immunity when lifecycle is enabled.

        Args:
            condition_name: Condition name being blocked.
            immunity_name: Optional named source of the immunity.
        """
        if not self.allow_events_conditions:
            return None
        self.condition_immunities.append((condition_name, immunity_name))

    def _remove_static_condition_immunity(self, condition_name: str, immunity_name: Optional[str] = None) -> None:
        """Remove matching static condition immunity rows.

        Args:
            condition_name: Condition name to remove.
            immunity_name: Optional immunity source name to match.
        """
        if not self.allow_events_conditions:
            return None
        for condition_tuple in self.condition_immunities:
            if condition_tuple[0] == condition_name:
                if immunity_name is None:
                    self.condition_immunities.remove(condition_tuple)
                else:
                    if condition_tuple[1] == immunity_name:
                        self.condition_immunities.remove(condition_tuple)
                        break
        return

    def add_contextual_condition_immunity(
        self,
        condition_name: str,
        immunity_name: str,
        immunity_check: ContextualConditionImmunity
    ) -> None:
        """Add a runtime condition immunity check when lifecycle is enabled.

        Args:
            condition_name: Condition name being blocked.
            immunity_name: Serializable name for the immunity source.
            immunity_check: Callable that evaluates the immunity at runtime.
        """
        if not self.allow_events_conditions:
            return None
        if condition_name not in self.contextual_condition_immunities:
            self.contextual_condition_immunities[condition_name] = []
        self.contextual_condition_immunities[condition_name].append((immunity_name, immunity_check))

    def add_condition_immunity(
        self,
        condition_name: str,
        immunity_name: Optional[str] = None,
        immunity_check: Optional[ContextualConditionImmunity] = None
    ) -> None:
        """Add a static or contextual condition immunity.

        Args:
            condition_name: Condition name being blocked.
            immunity_name: Optional named source of the immunity.
            immunity_check: Optional runtime immunity callable.

        Raises:
            ValueError: If `immunity_check` is provided without
                `immunity_name`.
        """
        if not self.allow_events_conditions:
            return None
        if immunity_check is not None:
            if immunity_name is None:
                raise ValueError("Immunity name is required when adding a contextual BaseCondition immunity")
            self.add_contextual_condition_immunity(condition_name, immunity_name, immunity_check)
        else:
            self.add_static_condition_immunity(condition_name, immunity_name)

    @staticmethod
    def _condition_immunity_source_name(source_id: UUID) -> str:
        """Encode one exact structural source without display-name identity."""
        source = BaseObject.get_contribution_owner(source_id)
        prefix = "condition-source" if isinstance(source, BaseCondition) else "structural-source"
        return f"{prefix}:{source_id}"

    @staticmethod
    def condition_immunity_contributes(source_name: str | None) -> bool:
        if source_name is None or not source_name.startswith("condition-source:"):
            return True
        source = BaseObject.get_contribution_owner(UUID(source_name.partition(":")[2]))
        return source is not None and source.contributions_active()

    def add_condition_immunity_source(
        self,
        condition_name: str,
        source_id: UUID,
        *,
        immunity_check: Optional[ContextualConditionImmunity] = None,
    ) -> None:
        """Install one exact source-owned static or contextual immunity."""
        source_name = self._condition_immunity_source_name(source_id)
        if any(
            name == source_name
            for name, _ in self.contextual_condition_immunities.get(
                condition_name,
                (),
            )
        ) or any(
            existing_condition == condition_name
            and existing_name == source_name
            for existing_condition, existing_name in self.condition_immunities
        ):
            raise ValueError(
                f"condition immunity source {source_id} is already installed "
                f"for {condition_name}",
            )
        self.add_condition_immunity(
            condition_name,
            immunity_name=source_name,
            immunity_check=immunity_check,
        )

    def remove_condition_immunity_source(
        self,
        condition_name: str,
        source_id: UUID,
    ) -> bool:
        """Remove exactly one source-owned immunity without touching siblings."""
        source_name = self._condition_immunity_source_name(source_id)
        removed = False
        for row in tuple(self.condition_immunities):
            if row == (condition_name, source_name):
                self.condition_immunities.remove(row)
                removed = True
        rows = self.contextual_condition_immunities.get(condition_name)
        if rows is not None:
            retained = [
                row
                for row in rows
                if row[0] != source_name
            ]
            removed = removed or len(retained) != len(rows)
            if retained:
                self.contextual_condition_immunities[condition_name] = retained
            else:
                self.contextual_condition_immunities.pop(
                    condition_name,
                    None,
                )
        return removed

    def _remove_contextual_condition_immunity(self, condition_name: str, immunity_name: Optional[str] = None) -> None:
        """Remove matching contextual condition immunity rows.

        Args:
            condition_name: Condition name to remove.
            immunity_name: Optional immunity source name to match.
        """
        if not self.allow_events_conditions:
            return None
        for self_condition_name in self.contextual_condition_immunities:
            if self_condition_name == condition_name:
                if immunity_name is None:
                    self.contextual_condition_immunities.pop(self_condition_name)
                    break
                else:
                    for immunity_tuple in self.contextual_condition_immunities[self_condition_name]:
                        if immunity_tuple[0] == immunity_name:
                            self.contextual_condition_immunities[self_condition_name].remove(immunity_tuple)
                            break

    def remove_condition_immunity(self, condition_name: str) -> None:
        """Remove static and contextual immunity rows for a condition.

        Args:
            condition_name: Condition name whose immunity rows should be removed.
        """
        if not self.allow_events_conditions:
            return None
        self._remove_static_condition_immunity(condition_name)
        self._remove_contextual_condition_immunity(condition_name)
        return
