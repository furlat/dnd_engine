from uuid import UUID, uuid4
from pydantic import ConfigDict, Field, computed_field, BaseModel, field_serializer, model_validator
from typing import ClassVar, Dict, Any, Optional, Self, Union, List, Tuple, Literal, Set

from enum import Enum
from dnd.core.modifiers import ContextAwareCondition
from dnd.core.base_object import BaseObject
from dnd.core.values import ModifiableValue
from dnd.core.events import BaseHandler, Event, EventPhase, EventType, SavingThrowEvent, EventHandler, EventQueue
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.content import ContentKind


class HazardFilter(str, Enum):
    """Pathfinding hazard targeting policy for condition-bearing blocks."""

    ALL = "all"
    ENEMIES = "enemies"
    NON_SOURCE = "non_source"


class ConditionTag(str, Enum):
    """Tags used by spell and restoration effects to classify conditions."""

    MAGICAL = "magical"
    CURSE = "curse"
    DISEASE = "disease"
    POISON = "poison"
    EXHAUSTION = "exhaustion"
    PETRIFICATION = "petrification"
    ABILITY_SCORE_REDUCTION = "ability_score_reduction"
    HIT_POINT_MAXIMUM_REDUCTION = "hit_point_maximum_reduction"
    CONCENTRATION = "concentration"


class ConditionCategory(str, Enum):
    """Broad condition category used by logs, reducers, and cleanup policy."""

    CONDITION = "condition"
    STATUS = "status"
    INTERNAL = "internal"


class ConditionRemovalTrigger(str, Enum):
    """Observable state transition that removes a condition."""

    POSITIVE_DAMAGE_APPLIED = "positive_damage_applied"


class ConditionAgencyDenial(str, Enum):
    """Degree of turn agency denied while a condition remains active."""

    NONE = "none"
    FULL_TURN = "full_turn"


class DurationType(str, Enum):
    """Supported duration progression modes for conditions."""

    ROUNDS = "rounds"
    PERMANENT = "permanent"
    UNTIL_LONG_REST = "until_long_rest"
    ON_CONDITION = "on_condition"


class OutcomeProtection(BaseModel):
    """Condition-owned rule that blocks specifically identified effects."""

    model_config = ConfigDict(frozen=True)

    protection_id: str = Field(description="Stable identity of the protection rule.")
    blocked_effect_ids: frozenset[str] = Field(
        default_factory=frozenset,
        description="Stable effect identities fully blocked by this protection.",
    )


class Duration(BaseObject):
    """Duration state owned by a condition."""

    duration: Optional[Union[int, ContextAwareCondition]] = Field(
        default=None,
        description="Round count, contextual expiration callable, or None."
    )
    duration_type: DurationType = Field(
        default=DurationType.PERMANENT,
        description="Duration progression mode."
    )
    source_entity_uuid: UUID = Field(default_factory=uuid4, description="Source entity UUID for contextual duration checks.")
    target_entity_uuid: UUID = Field(default_factory=uuid4, description="Target entity UUID for contextual duration checks.")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Runtime context for contextual duration checks.")
    long_rested: bool = Field(default=False, description="Whether a long rest has occurred for UNTIL_LONG_REST duration.")
    owned_by_condition: Optional[UUID] = Field(default=None, description="UUID of the condition that owns this duration.")

    @field_serializer('duration')
    def serialize_duration(self, value: Optional[Union[int, ContextAwareCondition]], _info: Any) -> Optional[Union[int, str]]:
        """Serialize callable durations without exposing callables.

        Args:
            value: Stored duration value.
            _info: Pydantic serializer metadata.

        Returns:
            Integer duration, `"conditional"` for callables, or `None`.
        """
        if value is None:
            return None
        if callable(value):
            return "conditional"
        return value

    def set_owned_by_condition(self, condition_uuid: UUID) -> None:
        """Record the owning condition UUID.

        Args:
            condition_uuid: UUID of the owning condition.
        """
        self.owned_by_condition = condition_uuid

    @model_validator(mode="after")
    def check_duration_type_consistency(self) -> Self:
        """Validate that duration value matches duration type.

        Returns:
            This duration after validation.

        Raises:
            ValueError: If `duration` does not match `duration_type`.
        """
        if self.duration_type == DurationType.ROUNDS:
            if not isinstance(self.duration, int):
                raise ValueError(f"Duration must be an int when duration_type is ROUNDS instead of {type(self.duration)}")
        elif self.duration_type == DurationType.PERMANENT:
            if self.duration is not None:
                raise ValueError(f"Duration must be None when duration_type is PERMANENT instead of {self.duration}")
        elif self.duration_type == DurationType.UNTIL_LONG_REST:
            if self.duration is not None:
                raise ValueError(f"Duration must be None when duration_type is UNTIL_LONG_REST instead of {self.duration}")
        elif self.duration_type == DurationType.ON_CONDITION:
            if not callable(self.duration):
                raise ValueError(f"Duration must be a ContextAwareCondition (callable) when duration_type is ON_CONDITION instead of {type(self.duration)}")
        return self

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Whether this duration is currently expired."""
        if self.duration_type == DurationType.ROUNDS:
            assert isinstance(self.duration, int)
            return self.duration <= 0
        elif self.duration_type == DurationType.ON_CONDITION:
            assert callable(self.duration)
            duration = self.duration(self.source_entity_uuid, self.target_entity_uuid, self.context)
            if duration is None:
                return False
            return duration
        elif self.duration_type == DurationType.UNTIL_LONG_REST:
            return self.long_rested
        else:
            return False

    def progress(self) -> bool:
        """Progress a round-based duration by one tick.

        Returns:
            True if the duration is expired after progression.
        """
        if self.duration_type == DurationType.ROUNDS:
            assert isinstance(self.duration, int)
            self.duration -= 1
            if self.is_expired:
                return True
            return False
        else:
            return False

    def long_rest(self) -> None:
        """Mark UNTIL_LONG_REST duration as rested."""
        self.long_rested = True


class ConditionApplicationEvent(Event):
    """Event payload for a condition application lifecycle."""

    name: str = Field(default="Condition Application", description="Condition application event name.")
    condition: 'BaseCondition' = Field(description="Condition being applied.")
    event_type: EventType = Field(default=EventType.CONDITION_APPLICATION, description="Condition application event type.")
    source_entity_name: Optional[str] = Field(default=None, description="Display name of the source entity.")
    target_entity_name: Optional[str] = Field(default=None, description="Display name of the target entity.")
    resulting_ac: Optional[int] = Field(default=None, description="Entity AC after condition application for frontend reducers.")
    resulting_max_hp: Optional[int] = Field(default=None, description="Entity max HP after condition application for frontend reducers.")

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate combat log for condition application."""
        cond = self.condition
        condition_name = cond.name or "Unknown"

        if cond.condition_category == ConditionCategory.INTERNAL:
            return None

        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "Unknown"

        if condition_name == "Hidden":
            stealth_dc = getattr(cond, 'stealth_result', 0)
            compact = f"{{cyan:{target_name}}} gains **Hidden** (Stealth DC {stealth_dc})"
        elif condition_name == "Invisible":
            compact = f"{{cyan:{target_name}}} becomes **invisible**"
        else:
            compact = f"{{cyan:{target_name}}} gains **{condition_name}**"

        verbose = compact
        if self.source_entity_uuid != self.target_entity_uuid and source_name != target_name:
            verbose = compact + f" from {{yellow:{source_name}}}"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.CONDITION_APPLIED,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            success=True,
        )


class ConditionRemovalEvent(Event):
    """Event payload for a condition removal lifecycle."""

    name: str = Field(default="Condition Removal", description="Condition removal event name.")
    condition: 'BaseCondition' = Field(description="Condition being removed.")
    expired: bool = Field(default=False, description="Whether expiration caused this removal.")
    event_type: EventType = Field(default=EventType.CONDITION_REMOVAL, description="Condition removal event type.")
    source_entity_name: Optional[str] = Field(default=None, description="Display name of the source entity.")
    target_entity_name: Optional[str] = Field(default=None, description="Display name of the target entity.")

    resulting_ac: Optional[int] = Field(default=None, description="Entity AC after condition removal for frontend reducers.")
    resulting_max_hp: Optional[int] = Field(default=None, description="Entity max HP after condition removal for frontend reducers.")

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate combat log for condition removal."""
        cond = self.condition
        condition_name = cond.name or "Unknown"

        if cond.condition_category == ConditionCategory.INTERNAL:
            return None

        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "Unknown"

        compact = f"{{cyan:{target_name}}} is no longer **{condition_name}**"

        verbose = compact
        if self.expired:
            verbose = compact + " (expired)"

        return CombatLogEntry(
            entry_type=CombatLogEntryType.CONDITION_REMOVED,
            source_name=source_name,
            source_uuid=str(self.source_entity_uuid),
            target_name=target_name,
            target_uuid=str(self.target_entity_uuid) if self.target_entity_uuid else None,
            compact=compact,
            verbose=verbose,
            detailed=verbose,
            success=True,
            data={"condition_name": condition_name},
        )


class BaseCondition(BaseObject):
    """Base state package for modifiers, handlers, subconditions, and cleanup."""

    semantic_key: Optional[str] = Field(
        default=None,
        description="Stable rules-content identity; defaults to the condition class identity.",
    )
    content_kind: ContentKind = Field(
        default=ContentKind.CONDITION,
        description="Rules-content family represented by this condition.",
    )

    def get_semantic_key(self) -> str:
        """Return an explicit key or the stable condition class identity."""
        if self.semantic_key:
            return self.semantic_key
        return f"{type(self).__module__}.{type(self).__name__}"

    def get_content_kind(self) -> ContentKind:
        """Return the declared or source-domain-derived rules-content family."""
        if self.content_kind != ContentKind.CONDITION:
            return self.content_kind
        module = type(self).__module__
        if module == "dnd.classes.feats":
            return ContentKind.FEAT
        if module.startswith("dnd.monsters"):
            return ContentKind.TRAIT
        if module.startswith("dnd.classes"):
            return ContentKind.CLASS_FEATURE
        return ContentKind.CONDITION

    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Broad category used by logs and condition consumers."
    )
    duration: Duration = Field(default_factory=Duration, description="Duration state owned by this condition.")
    application_saving_throw: Optional[SavingThrowEvent] = Field(
        default=None,
        description="Optional saving throw requested before entity-level application."
    )
    removal_saving_throw: Optional[SavingThrowEvent] = Field(
        default=None,
        description="Optional saving throw requested before entity-level duration removal."
    )
    applied: bool = Field(default=False, description="Whether this condition has applied its own state.")
    source_entity_name: Optional[str] = Field(default=None, description="Name of the source entity (populated by Entity.add_condition)")
    target_entity_name: Optional[str] = Field(default=None, description="Name of the target entity (populated by Entity.add_condition)")
    modifers_uuids: Dict[UUID, List[UUID]] = Field(
        default_factory=dict,
        description="Owned modifier UUIDs grouped by ModifiableValue UUID."
    )
    parent_condition: Optional[UUID] = Field(
        default=None,
        description="Same-block parent condition UUID, if this is a subcondition."
    )
    sub_conditions: List[UUID] = Field(
        default_factory=list,
        description="Same-block child condition UUIDs removed with this condition."
    )
    event_handlers_uuids: List[UUID] = Field(
        default_factory=list,
        description="Owned trigger-handler UUIDs removed with this condition."
    )
    spatial_handler_uuids: List[UUID] = Field(
        default_factory=list,
        description="Owned spatial-handler UUIDs removed with this condition."
    )
    linked_conditions: List[Tuple[UUID, UUID]] = Field(
        default_factory=list,
        description="Cross-block child condition pairs as (target_block_uuid, condition_uuid)."
    )
    parent_link: Optional[Tuple[UUID, UUID]] = Field(
        default=None,
        description="Reverse cross-block parent link as (parent_block_uuid, parent_condition_uuid)."
    )
    child_removal_policy: Literal["none", "any", "last"] = Field(
        default="none",
        description="Reverse cleanup policy: none, any child removed, or last child removed."
    )
    hazard_filter: Optional[HazardFilter] = Field(
        default=None,
        description="Who this condition is hazardous to. None = not hazardous."
    )
    condition_stealth_dc: Optional[int] = Field(
        default=None,
        description="Perception DC to detect this condition on a tile. None = always visible."
    )
    tags: Set[ConditionTag] = Field(
        default_factory=set,
        description="Condition tags such as MAGICAL, CURSE, DISEASE, POISON, EXHAUSTION, PETRIFICATION, ability-score reduction, and hit-point-maximum reduction."
    )
    outcome_protections: Tuple[OutcomeProtection, ...] = Field(
        default_factory=tuple,
        description="Typed effect protections active while this condition is applied.",
    )
    removal_triggers: frozenset[ConditionRemovalTrigger] = Field(
        default_factory=frozenset,
        description="Typed state transitions that remove this condition.",
    )
    agency_denial: ConditionAgencyDenial = Field(
        default=ConditionAgencyDenial.NONE,
        description="Turn agency denied by this complete condition while active.",
    )
    applied_source_event_cursor: Optional[int] = Field(
        default=None,
        ge=0,
        description="Objective event cursor of the completed application boundary.",
    )

    def get_action_target_effect_profile(self, action: Any, actor: Any) -> Optional[Any]:
        """Return target-effect metadata this condition adds to an action.

        Args:
            action: Action template being discovered.
            actor: Entity discovering that action.

        Returns:
            A dependency-neutral target-effect profile, or `None` when this
            condition does not modify the discovered action.
        """
        return None

    def get_action_damage_roll_profiles(self, action: Any, actor: Any) -> Tuple[Any, ...]:
        """Return extra damage profiles this condition adds to an action.

        Args:
            action: Action template being discovered.
            actor: Entity discovering that action.

        Returns:
            Dependency-neutral damage-profile metadata. The action layer
            validates concrete model types before exposing them.
        """
        return ()

    @property
    def magical_origin(self) -> bool:
        """Whether this condition has a magical origin tag."""
        return ConditionTag.MAGICAL in self.tags

    @model_validator(mode="after")
    def check_duration_consistency(self) -> Self:
        """Stamp this condition as the owner of its duration.

        Returns:
            This condition after duration ownership is set.
        """
        self.duration.set_owned_by_condition(self.uuid)
        return self

    def set_context(self, context: Dict[str, Any]) -> None:
        """Set runtime context on the condition and duration.

        Args:
            context: Runtime context dictionary.
        """
        self.context = context
        self.duration.context = context

    def clear_context(self) -> None:
        """Clear runtime context from the condition and duration."""
        self.context = None
        self.duration.context = None

    def supports_level_reduction(self) -> bool:
        """Return whether this condition can be replaced by a lower level."""
        return False

    def get_reduced_level_condition(self, amount: int = 1) -> Optional["BaseCondition"]:
        """Return the replacement condition after reducing a level.

        Args:
            amount: Number of levels to reduce.

        Returns:
            Replacement condition, or `None` when reduction removes the
            condition entirely. Conditions that do not support level reduction
            should leave `supports_level_reduction()` as `False`.
        """
        return None

    def set_source_entity(self, source_entity_uuid: UUID) -> None:
        """Set source entity UUID on the condition and duration.

        Args:
            source_entity_uuid: Source entity UUID.
        """
        self.source_entity_uuid = source_entity_uuid
        self.duration.source_entity_uuid = source_entity_uuid

    def set_target_entity(self, target_entity_uuid: UUID) -> None:
        """Set target entity UUID on the condition and duration.

        Args:
            target_entity_uuid: Target entity UUID.
        """
        self.target_entity_uuid = target_entity_uuid
        self.duration.target_entity_uuid = target_entity_uuid

    def declare_event(self, parent_event: Optional[Event] = None) -> Event:
        """Create the condition application declaration event.

        Args:
            parent_event: Optional parent event for event-tree nesting.

        Returns:
            Declaration-phase application event.

        Raises:
            ValueError: If the condition has no name.
        """
        if not self.name:
            raise ValueError("Condition name is not set")
        return ConditionApplicationEvent(
            name=self.name,
            condition=self,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            phase=EventPhase.DECLARATION,
            parent_event=parent_event.uuid if parent_event else None,
            source_entity_name=self.source_entity_name,
            target_entity_name=self.target_entity_name
        )

    def _declare_removal_event(self, expired: bool = False, parent_event: Optional[Event] = None) -> Event:
        """Create the condition removal declaration event.

        Args:
            expired: Whether removal is caused by expiration.
            parent_event: Optional parent event for event-tree nesting.

        Returns:
            Declaration-phase removal event.
        """
        return ConditionRemovalEvent(
            name=self.name if self.name else "Condition Removal",
            condition=self,
            expired=expired,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            phase=EventPhase.DECLARATION,
            parent_event=parent_event.uuid if parent_event else None,
            source_entity_name=self.source_entity_name,
            target_entity_name=self.target_entity_name
        )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply subclass state and return owned runtime artifacts.

        Subclasses override this to add modifiers, handlers, spatial handlers,
        same-block subconditions, or linked conditions. The base implementation
        creates execution and effect events and returns no owned artifacts.

        Args:
            declaration_event: Declaration event created for this application.

        Returns:
            Tuple of modifier pairs, trigger-handler UUIDs, same-block
            subcondition UUIDs, spatial-handler UUIDs, and the effect event.
        """
        event = declaration_event.phase_to(EventPhase.EXECUTION, update={"condition": self})
        event = declaration_event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return [], [], [], [], event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Run subclass removal behavior.

        Args:
            event: Removal declaration event to phase through removal work.

        Returns:
            Last removal event after subclass work, or None if no event was given.
        """
        if event:
            event = event.phase_to(EventPhase.EXECUTION, update={"condition": self})
            event = event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return event

    def _post_removal_stats(self) -> Dict[str, Any]:
        """Return resulting stats to inject into the COMPLETION event after modifiers are removed.

        Override in conditions that modify AC or max_hp so the frontend reducer
        can update entity stats without waiting for the next /state resync.
        Called after `remove_condition_modifiers()` in `cleanup_own_state()`.

        Returns:
            Field updates for the removal completion event.
        """
        return {}

    def _expire(self, event: Optional[Event] = None) -> Optional[Event]:
        """Run subclass expiration behavior.

        Args:
            event: Removal declaration event to phase through expiration work.

        Returns:
            Last expiration event after subclass work, or None if no event was given.
        """
        if event:
            event = event.phase_to(EventPhase.EXECUTION, update={"condition": self})
            event = event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return event

    def apply(self, parent_event: Optional[Event] = None, declaration_event: Optional[Event] = None) -> Optional[Event]:
        """Apply condition state and complete the application event.

        Args:
            parent_event: Optional parent event for event-tree nesting.
            declaration_event: Existing declaration event from a caller that
                already performed declaration-time checks.

        Returns:
            Completed application event, cancellation event, or None if the
            condition is already applied, expired, or declaration-canceled.
        """
        if self.applied or self.duration.is_expired:
            return None
        if declaration_event is None:
            declaration_event = self.declare_event(parent_event)

        if declaration_event.canceled:
            return None

        modifers_uuids, event_handlers_uuids, sub_conditions_uuids, spatial_handler_uuids, effect_event = self._apply(declaration_event)

        if not effect_event:
            return declaration_event.cancel(status_message=f"Condition {self.name} was not applied - _apply() returned no effect event")

        for block_uuid, modifiers_uuids in modifers_uuids:
            if block_uuid not in self.modifers_uuids:
                self.modifers_uuids[block_uuid] = []
            self.modifers_uuids[block_uuid].append(modifiers_uuids)

        for event_handler_uuid in event_handlers_uuids:
            handler = BaseObject.get(event_handler_uuid)
            if isinstance(handler, BaseHandler):
                if handler.content_kind == ContentKind.UNCLASSIFIED:
                    handler.content_kind = self.get_content_kind()
                if handler.semantic_key is None:
                    handler_name = "_".join(
                        part for part in "".join(
                            character.lower() if character.isalnum() else "_"
                            for character in handler.name
                        ).split("_") if part
                    )
                    handler.semantic_key = f"{self.get_semantic_key()}.handler.{handler_name or 'effect'}"
            if event_handler_uuid not in self.event_handlers_uuids:
                self.event_handlers_uuids.append(event_handler_uuid)
        for sub_condition_uuid in sub_conditions_uuids:
            if sub_condition_uuid not in self.sub_conditions:
                self.sub_conditions.append(sub_condition_uuid)
        for spatial_handler_uuid in spatial_handler_uuids:
            if spatial_handler_uuid not in self.spatial_handler_uuids:
                self.spatial_handler_uuids.append(spatial_handler_uuid)

        self.applied = True
        completed_event = effect_event.phase_to(EventPhase.COMPLETION)
        self.applied_source_event_cursor = EventQueue.event_cursor()
        return completed_event

    def remove_condition_modifiers(self) -> bool:
        """Remove owned modifiers without changing applied state.

        Returns:
            True if modifiers were removed or no modifiers were owned, False if
            the condition was not applied.
        """
        if not self.applied:
            return False

        for value_uuid, modifiers_uuids in self.modifers_uuids.items():
            value = ModifiableValue.get(value_uuid)
            if value is None:
                raise ValueError(f"Trying to remove value with UUID {value_uuid} not found")
            for modifier_uuid in modifiers_uuids:
                value.remove_modifier(modifier_uuid)
        return True

    def add_linked_condition(self, target_block_uuid: UUID, condition_uuid: UUID) -> None:
        """Track a condition this condition placed on another BaseBlock.

        When this condition is removed, the linked condition will also be removed
        from the target block. Works for entities, tiles, and future items.

        Also sets the reverse link (parent_link) on the child condition so that
        when the child is removed, it can notify this parent based on child_removal_policy.

        Args:
            target_block_uuid: UUID of the BaseBlock that has the condition.
            condition_uuid: UUID of the condition on that block.
        """
        self.linked_conditions.append((target_block_uuid, condition_uuid))
        child = BaseCondition.get(condition_uuid)
        if child is not None and isinstance(child, BaseCondition) and self.target_entity_uuid is not None:
            child.parent_link = (self.target_entity_uuid, self.uuid)

    def remove_condition_from_parent(self, skip_parent_removal: bool = False) -> bool:
        """Detach this condition from its same-block parent condition.

        Args:
            skip_parent_removal: Whether to leave the parent child list intact.

        Returns:
            True after the parent link is handled.

        Raises:
            ValueError: If the parent condition UUID is set but cannot be found.
        """
        if self.parent_condition and not skip_parent_removal:
            parent_condition = BaseCondition.get(self.parent_condition)
            if parent_condition is None:
                raise ValueError(f"Trying to remove condition with UUID {self.uuid} from parent with UUID {self.parent_condition} not found, parent removal should remove children")
            elif isinstance(parent_condition, BaseCondition):
                parent_condition.sub_conditions.remove(self.uuid)

        return True

    def remove_event_handlers(self) -> bool:
        """Remove owned trigger-based event handlers from the EventQueue.

        Returns:
            True if handlers were removed or absent, False if the condition was
            not applied.
        """
        if not self.applied:
            return False
        for event_handler_uuid in self.event_handlers_uuids:
            event_handler = EventHandler.get(event_handler_uuid)
            if event_handler is None:
                continue
            elif isinstance(event_handler, EventHandler):
                event_handler.remove()
        self.event_handlers_uuids.clear()
        return True

    def remove_spatial_handlers(self) -> bool:
        """Remove all spatial handlers owned by this condition.

        Spatial handlers are position-indexed handlers registered via
        EventQueue.add_spatial_handler(). They are stored separately
        from trigger-based EventHandlers.
        """
        if not self.applied:
            return False
        for handler_uuid in self.spatial_handler_uuids:
            EventQueue.remove_spatial_handler(handler_uuid)
        self.spatial_handler_uuids.clear()
        return True

    def cleanup_own_state(self, expire: bool = False, parent_event: Optional[Event] = None) -> bool:
        """Clean this condition's own modifiers, handlers, and removal event.

        Cross-object cleanup for same-block subconditions and linked conditions
        is handled by `BaseBlock._remove_condition_tree()`. Subclass `_expire()`
        and `_remove()` hooks are preserved for custom cleanup behavior.

        Args:
            expire: Whether this is an expiration removal.
            parent_event: Optional parent event for event-tree nesting.

        Returns:
            True if cleanup succeeded, False if cleanup was canceled or the
            condition was not applied.
        """
        if not self.applied:
            return False

        event = self._declare_removal_event(expired=expire, parent_event=parent_event)
        if event.canceled:
            return False

        if expire:
            expired_event = self._expire(event)
            if expired_event and expired_event.canceled:
                return False

        removed_event = self._remove(event)
        if removed_event and removed_event.canceled:
            return False

        self.remove_condition_modifiers()
        self.remove_event_handlers()
        self.remove_spatial_handlers()

        if self.parent_condition:
            parent = BaseCondition.get(self.parent_condition)
            if parent is not None and isinstance(parent, BaseCondition):
                if self.uuid in parent.sub_conditions:
                    parent.sub_conditions.remove(self.uuid)

        self.applied = False

        post_stats = self._post_removal_stats()
        event.phase_to(EventPhase.COMPLETION, **post_stats)
        return True

    def progress(self) -> bool:
        """Progress condition duration without removing the condition.

        Removal is the caller's responsibility so block/entity cleanup can own
        tree traversal.

        Returns:
            True if the duration is expired after progression.
        """
        return self.duration.progress()

    def long_rest(self) -> None:
        """Mark this condition's duration as long-rested."""
        self.duration.long_rest()


class SpellProtection(BaseModel):
    """A spell protection zone (e.g. Globe of Invulnerability).

    Tracks positions that are protected from spells at or below a certain level,
    when the spell source is outside the protection zone.
    """
    uuid: UUID = Field(description="Protection UUID used for unregistering.")
    positions: Set[Tuple[int, int]] = Field(description="Grid positions protected by this spell effect.")
    max_blocked_level: int = Field(description="Highest spell level blocked by this protection.")

    model_config = {"arbitrary_types_allowed": True}


class SpellProtectionRegistry:
    """Tracks globe-like protections for zone spell position filtering.

    A position is protected if:
    1. It's inside a registered protection zone
    2. The spell source_position is OUTSIDE that zone
    3. The spell's base level <= max_blocked_level
    """
    _protections: ClassVar[List[SpellProtection]] = []

    @classmethod
    def register(cls, protection: SpellProtection) -> None:
        """Register a spell protection zone.

        Args:
            protection: Protection zone to register.
        """
        cls._protections.append(protection)

    @classmethod
    def unregister(cls, protection_uuid: UUID) -> None:
        """Remove a spell protection zone by UUID.

        Args:
            protection_uuid: UUID of the protection zone to remove.
        """
        cls._protections = [p for p in cls._protections if p.uuid != protection_uuid]

    @classmethod
    def is_protected(cls, position: Tuple[int, int], source_position: Tuple[int, int], spell_level: int) -> bool:
        """Check whether a position is protected from a spell.

        Args:
            position: Target position to check.
            source_position: Position the spell is cast from.
            spell_level: Base spell level being cast.

        Returns:
            True if the target position is protected from this spell.
        """
        for p in cls._protections:
            if position in p.positions and source_position not in p.positions and spell_level <= p.max_blocked_level:
                return True
        return False

    @classmethod
    def get_excluded_positions(cls, source_position: Tuple[int, int], spell_level: int) -> Set[Tuple[int, int]]:
        """Return protected positions excluded for a spell cast.

        Args:
            source_position: Position the spell is cast from.
            spell_level: Base spell level being cast.

        Returns:
            Positions protected from this spell.
        """
        excluded: Set[Tuple[int, int]] = set()
        for p in cls._protections:
            if source_position not in p.positions and spell_level <= p.max_blocked_level:
                excluded |= p.positions
        return excluded

    @classmethod
    def reset(cls) -> None:
        """Clear all registered spell protection zones."""
        cls._protections.clear()
