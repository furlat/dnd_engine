from uuid import UUID, uuid4
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    computed_field,
    field_serializer,
    model_serializer,
    model_validator,
)
from typing import ClassVar, Dict, Any, Optional, Self, Union, List, Tuple, Literal, Set

from dnd.core.modifiers import ContextAwareCondition
from dnd.core.base_object import BaseObject
from dnd.core.values import ModifiableValue
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventType,
    EventHandler,
    EventQueue,
)
from dnd.core.events.check_events import (
    SavingThrowEvent,
)
from dnd.core.combat_log import (
    CombatLogEntry,
    CombatLogEntryType,
    ConditionLogData,
)
from dnd.core.behavior_context import active_behavior, behavior_scope
from dnd.types.behaviors import RuntimeBehaviorKind, validate_behavior_id
from dnd.types.effects import EffectOrigin
from dnd.types.conditions import (
    ConditionAgencyDenial,
    ConditionApplicationDisposition,
    ConditionApplicationPolicy,
    ConditionCategory,
    ConditionRemovalTrigger,
    ConditionTag,
    DurationType,
    HazardFilter,
)
from dnd.types.saving_throws import SavingThrowContext, SavingThrowEffectTag


class OutcomeProtection(BaseModel):
    """Condition-owned rule that blocks specifically identified effects."""

    model_config = ConfigDict(frozen=True)

    protection_id: str = Field(description="Stable identity of the protection rule.")
    blocked_effect_ids: frozenset[str] = Field(
        default_factory=frozenset,
        description="Stable effect identities fully blocked by this protection.",
        json_schema_extra={"uniqueItems": True},
    )

    @field_serializer("blocked_effect_ids", when_used="json")
    def serialize_blocked_effect_ids(self, value: frozenset[str]) -> List[str]:
        """Emit protection identities in canonical wire order."""
        return sorted(value)


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


# EVENT-MIGRATION BLOCKER: Move this class to the core event package only
# after the event-facing condition state no longer requires importing the
# runtime BaseCondition owner back into the event module.
class ConditionApplicationEvent(Event):
    """Event payload for a condition application lifecycle."""

    name: str = Field(default="Condition Application", description="Condition application event name.")
    condition: 'BaseCondition' = Field(description="Condition being applied.")
    event_type: EventType = Field(default=EventType.CONDITION_APPLICATION, description="Condition application event type.")
    source_entity_name: Optional[str] = Field(default=None, description="Display name of the source entity.")
    target_entity_name: Optional[str] = Field(default=None, description="Display name of the target entity.")
    resulting_ac: Optional[int] = Field(default=None, description="Entity AC after condition application for frontend reducers.")
    resulting_max_hp: Optional[int] = Field(default=None, description="Entity max HP after condition application for frontend reducers.")
    application_disposition: ConditionApplicationDisposition = Field(
        default=ConditionApplicationDisposition.APPLIED,
        description="Authoritative result of repeated-condition arbitration.",
    )
    condition_behavior_id: str = Field(
        default="condition.unclassified",
        min_length=1,
        description=(
            "Exact authored condition identity frozen when the declaration is "
            "created; absent only for legacy unbound diagnostic events."
        ),
    )

    @model_validator(mode="after")
    def validate_condition_behavior_id(self) -> Self:
        """Require the frozen scalar to match the live declaration binding."""
        expected_identity = self.condition.behavior_id
        if self.condition_behavior_id != expected_identity:
            raise ValueError(
                "condition identity must match its direct behavior ID",
            )
        return self

    def validate_handler_result(self, result: Event) -> Event:
        """Cancel before storage when a handler rewrites frozen identity."""
        if (
            type(result) is not ConditionApplicationEvent
            or not isinstance(result, ConditionApplicationEvent)
            or not self.handler_result_preserves_lifecycle(result)
            or type(result.condition) is not type(self.condition)
            or result.condition != self.condition
            or type(result.condition_behavior_id)
            is not type(self.condition_behavior_id)
            or result.condition_behavior_id
            != self.condition_behavior_id
            or type(result.application_disposition)
            is not type(self.application_disposition)
            or result.application_disposition
            is not self.application_disposition
        ):
            return self.invalid_handler_result_cancellation(
                result,
                status_message=(
                    "Condition application identity or lifecycle changed "
                    "after declaration."
                ),
            )
        return result.model_copy(update={"condition": self.condition})

    def get_effect_origin(self) -> Optional[EffectOrigin]:
        """Return the immutable origin inherited by the applied condition."""
        return self.condition.effect_origin

    def generate_combat_log(self) -> Optional[CombatLogEntry]:
        """Generate combat log for condition application."""
        cond = self.condition

        if cond.condition_category == ConditionCategory.INTERNAL:
            return None

        target_name = self.target_entity_name or "Unknown"
        source_name = self.source_entity_name or "Unknown"

        if self.application_disposition is ConditionApplicationDisposition.IMMUNE:
            compact = (
                f"{{cyan:{target_name}}} is immune to "
                f"**{cond.name or 'Unknown'}**"
            )
        elif self.application_disposition is (
            ConditionApplicationDisposition.RETAINED_STRONGER
        ):
            compact = (
                f"{{cyan:{target_name}}} remains under the stronger "
                f"**{cond.name or 'Unknown'}** effect"
            )
        elif self.application_disposition is (
            ConditionApplicationDisposition.REJECTED
        ):
            compact = (
                f"{{cyan:{target_name}}} rejects another "
                f"**{cond.name or 'Unknown'}** effect"
            )
        elif self.application_disposition is (
            ConditionApplicationDisposition.PROMOTED
        ):
            compact = (
                f"{{cyan:{target_name}}} remains under "
                f"**{cond.name or 'Unknown'}** from another source"
            )
        else:
            compact = cond.format_application_log(target_name)

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
            success=self.application_disposition not in {
                ConditionApplicationDisposition.REJECTED,
                ConditionApplicationDisposition.RETAINED_STRONGER,
                ConditionApplicationDisposition.IMMUNE,
            },
            data=ConditionLogData(
                condition_name=cond.name or "Unknown",
                condition_behavior_id=self.condition_behavior_id,
                application_disposition=self.application_disposition,
            ).model_dump(mode="json"),
        )


# EVENT-MIGRATION BLOCKER: Move this class to the core event package only
# after the event-facing condition state no longer requires importing the
# runtime BaseCondition owner back into the event module.
class ConditionRemovalEvent(Event):
    """Event payload for a condition removal lifecycle."""

    name: str = Field(default="Condition Removal", description="Condition removal event name.")
    condition: 'BaseCondition' = Field(description="Condition being removed.")
    expired: bool = Field(default=False, description="Whether expiration caused this removal.")
    event_type: EventType = Field(default=EventType.CONDITION_REMOVAL, description="Condition removal event type.")
    source_entity_name: Optional[str] = Field(default=None, description="Display name of the source entity.")
    target_entity_name: Optional[str] = Field(default=None, description="Display name of the target entity.")
    condition_behavior_id: str = Field(
        default="condition.unclassified",
        min_length=1,
        description=(
            "Exact authored condition identity frozen when the declaration is "
            "created; absent only for legacy unbound diagnostic events."
        ),
    )

    @model_validator(mode="after")
    def validate_condition_behavior_id(self) -> Self:
        """Require the frozen scalar to match the live declaration binding."""
        expected_identity = self.condition.behavior_id
        if self.condition_behavior_id != expected_identity:
            raise ValueError(
                "condition identity must match its direct behavior ID",
            )
        return self

    def validate_handler_result(self, result: Event) -> Event:
        """Cancel before storage when a handler rewrites frozen identity."""
        if (
            type(result) is not ConditionRemovalEvent
            or not isinstance(result, ConditionRemovalEvent)
            or not self.handler_result_preserves_lifecycle(result)
            or type(result.condition) is not type(self.condition)
            or result.condition != self.condition
            or type(result.condition_behavior_id)
            is not type(self.condition_behavior_id)
            or result.condition_behavior_id
            != self.condition_behavior_id
        ):
            return self.invalid_handler_result_cancellation(
                result,
                status_message=(
                    "Condition removal identity or lifecycle changed after "
                    "declaration."
                ),
            )
        return result.model_copy(update={"condition": self.condition})

    resulting_ac: Optional[int] = Field(default=None, description="Entity AC after condition removal for frontend reducers.")
    resulting_max_hp: Optional[int] = Field(default=None, description="Entity max HP after condition removal for frontend reducers.")

    def get_effect_origin(self) -> Optional[EffectOrigin]:
        """Return the immutable origin owned by the removed condition."""
        return self.condition.effect_origin

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
            data=ConditionLogData(
                condition_name=condition_name,
                condition_behavior_id=self.condition_behavior_id,
                reveals_target=cond.obscures_perceivability,
            ).model_dump(mode="json"),
        )


class BaseCondition(BaseObject):
    """Base state package for modifiers, handlers, subconditions, and cleanup."""

    description: str = Field(
        default="",
        description="Player-facing rules summary for this condition.",
    )
    semantic_key: Optional[str] = Field(
        default=None,
        description="Stable rules-content identity; defaults to the condition class identity.",
    )
    behavior_id: str = Field(
        default="condition.unclassified",
        description="Direct renderer-independent condition identity.",
    )
    provided_by_id: Optional[str] = Field(
        default=None,
        description="Direct semantic identity that installed this condition.",
    )
    origin_root_id: Optional[str] = Field(
        default=None,
        description="Optional durable semantic root of this condition.",
    )
    content_kind: RuntimeBehaviorKind = Field(
        default=RuntimeBehaviorKind.CONDITION,
        description="Rules-content family represented by this condition.",
    )
    effect_origin: Optional[EffectOrigin] = Field(
        default=None,
        description="Dependency-neutral provenance inherited from the applying effect.",
    )
    obscures_perceivability: bool = Field(
        default=False,
        description="Whether removing this condition may reveal its target.",
    )

    def saving_throw_context(
        self,
        *,
        effect_id: str,
        effect_tags: Tuple[SavingThrowEffectTag, ...] = (),
        is_magical: Optional[bool] = None,
    ) -> SavingThrowContext:
        """Build exact typed context for a save caused by this live condition."""
        return SavingThrowContext(
            cause_id=self.behavior_id,
            effect_id=effect_id,
            condition_id=self.behavior_id,
            is_magical=(
                ConditionTag.MAGICAL in self.tags
                if is_magical is None
                else is_magical
            ),
            effect_tags=effect_tags,
        )

    def format_application_log(self, target_name: str) -> str:
        """Return condition-owned compact presentation for application."""
        return f"{{cyan:{target_name}}} gains **{self.name or 'Unknown'}**"

    def get_semantic_key(self) -> str:
        """Return this condition's direct semantic behavior identity."""
        return self.behavior_id

    def bind_behavior_owner(self, *, origin_root_id: Optional[str] = None) -> None:
        """Finalize direct ownership without consulting a global gateway."""
        if self.semantic_key is not None:
            self.behavior_id = self.semantic_key
        validate_behavior_id(self.behavior_id)
        active = active_behavior()
        if self.provided_by_id is None:
            self.provided_by_id = (
                active.behavior_id if active is not None else self.behavior_id
            )
        validate_behavior_id(self.provided_by_id, "provided_by_id")
        if self.origin_root_id is None:
            self.origin_root_id = (
                active.origin_root_id if active is not None else origin_root_id
            )
        if self.origin_root_id is not None:
            validate_behavior_id(self.origin_root_id, "origin_root_id")

    def get_content_kind(self) -> RuntimeBehaviorKind:
        """Return the declared or source-domain-derived rules-content family."""
        if self.content_kind != RuntimeBehaviorKind.CONDITION:
            return self.content_kind
        module = type(self).__module__
        if module == "dnd.classes.feats":
            return RuntimeBehaviorKind.FEAT
        if module.startswith("dnd.monsters"):
            return RuntimeBehaviorKind.TRAIT
        if module.startswith("dnd.classes"):
            return RuntimeBehaviorKind.CLASS_FEATURE
        return RuntimeBehaviorKind.CONDITION

    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Broad category used by logs and condition consumers."
    )
    application_policy: ConditionApplicationPolicy = Field(
        default=ConditionApplicationPolicy.REPLACE_EXISTING,
        description=(
            "Authored policy for repeated applications of this exact "
            "condition family."
        ),
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
        description=(
            "Cross-owner child condition pairs as "
            "(runtime_owner_uuid, condition_uuid)."
        ),
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
        description="Condition tags such as MAGICAL, CURSE, DISEASE, POISON, EXHAUSTION, PETRIFICATION, ability-score reduction, and hit-point-maximum reduction.",
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
    _granted_action_uuids: List[UUID] = PrivateAttr(default_factory=list)

    def own_granted_action(self, action_uuid: UUID) -> None:
        """Track one exact action template granted by this condition."""
        if action_uuid not in self._granted_action_uuids:
            self._granted_action_uuids.append(action_uuid)

    def release_granted_actions(self) -> Tuple[UUID, ...]:
        """Release and clear the exact action identities owned by this condition."""
        owned = tuple(self._granted_action_uuids)
        self._granted_action_uuids.clear()
        return owned

    def has_granted_actions(self) -> bool:
        """Return whether this condition currently owns granted actions."""
        return bool(self._granted_action_uuids)

    @model_serializer(mode="wrap", when_used="json")
    def serialize_unordered_wire_fields(
        self,
        handler: SerializerFunctionWrapHandler,
    ):
        """Sort set-backed fields without replacing concrete subclass schemas."""
        payload = handler(self)
        if not isinstance(payload, dict):
            return payload
        for field_name in ("tags", "removal_triggers"):
            values = payload.get(field_name)
            if isinstance(values, list):
                payload[field_name] = sorted(values)
        return payload

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

    def declare_event(
        self,
        parent_event: Optional[Event] = None,
        *,
        application_disposition: ConditionApplicationDisposition = (
            ConditionApplicationDisposition.APPLIED
        ),
    ) -> ConditionApplicationEvent:
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
        if self.effect_origin is None and parent_event is not None:
            self.effect_origin = parent_event.get_effect_origin()
        return ConditionApplicationEvent(
            name=self.name,
            condition=self,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            phase=EventPhase.DECLARATION,
            parent_event=parent_event.uuid if parent_event else None,
            source_entity_name=self.source_entity_name,
            target_entity_name=self.target_entity_name,
            application_disposition=application_disposition,
            condition_behavior_id=self.behavior_id,
            use_register=False,
        )

    def _declare_removal_event(
        self,
        expired: bool = False,
        parent_event: Optional[Event] = None,
    ) -> ConditionRemovalEvent:
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
            target_entity_name=self.target_entity_name,
            condition_behavior_id=self.behavior_id,
            use_register=False,
        )

    def _apply(self, execution_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        """Apply subclass state and return owned runtime artifacts.

        Subclasses override this to add modifiers, handlers, spatial handlers,
        same-block subconditions, or linked conditions. The base implementation
        creates the effect event and returns no owned artifacts.

        Args:
            execution_event: Accepted execution event for this application.

        Returns:
            Tuple of modifier pairs, trigger-handler UUIDs, same-block
            subcondition UUIDs, spatial-handler UUIDs, and the effect event.
        """
        event = execution_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
        )
        return [], [], [], [], event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Run subclass removal behavior.

        Args:
            event: Removal declaration event to phase through removal work.

        Returns:
            Last removal event after subclass work, or None if no event was given.
        """
        if event:
            event = event.phase_to(EventPhase.EFFECT, update={"condition": self})
        return event

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release subclass-owned state not represented by returned UUIDs.

        This hook must be idempotent. It runs for both ordinary removal and
        rejected/exceptional application rollback, so implementations must not
        publish a second lifecycle or depend on ``applied`` already being true.

        Args:
            parent_event: Optional causal event for restoration work.
        """
        del parent_event

    def discard_uncommitted_runtime_state(self) -> None:
        """Release provisional state without publishing a removal lifecycle."""
        self._release_owned_runtime_state()
        self.applied = True
        try:
            self.remove_condition_modifiers()
            self.remove_event_handlers()
            self.remove_spatial_handlers()
        finally:
            self.applied = False
        self.modifers_uuids.clear()

    def _finalize_application(self, effect_event: Event) -> None:
        """Finalize subclass state before application completion is published."""
        del effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        """Return resulting stats to inject into the COMPLETION event after modifiers are removed.

        Override in conditions that modify AC or max_hp so canonical projection
        can publish the resulting reducer patch at the same causal boundary.
        Called after `remove_condition_modifiers()` in `cleanup_own_state()`.

        Returns:
            Field updates for the removal completion event.
        """
        return {}

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
        self.bind_behavior_owner()
        if declaration_event is None:
            declaration_event = self.declare_event(parent_event)
            declaration_event = EventQueue.publish_declaration(
                declaration_event
            )

        if declaration_event.canceled:
            return declaration_event

        execution_event = declaration_event.phase_to(
            EventPhase.EXECUTION,
            update={"condition": self},
            status_message=f"Applying {self.name}",
        )
        if execution_event.canceled:
            return execution_event

        try:
            assert self.provided_by_id is not None
            with behavior_scope(
                behavior_id=self.behavior_id,
                provided_by_id=self.provided_by_id,
                origin_root_id=self.origin_root_id,
            ):
                (
                    modifers_uuids,
                    event_handlers_uuids,
                    sub_conditions_uuids,
                    spatial_handler_uuids,
                    effect_event,
                ) = self._apply(execution_event)
        except BaseException:
            self.discard_uncommitted_runtime_state()
            raise

        for block_uuid, modifiers_uuids in modifers_uuids:
            if block_uuid not in self.modifers_uuids:
                self.modifers_uuids[block_uuid] = []
            self.modifers_uuids[block_uuid].append(modifiers_uuids)

        for event_handler_uuid in event_handlers_uuids:
            if event_handler_uuid not in self.event_handlers_uuids:
                self.event_handlers_uuids.append(event_handler_uuid)
        for sub_condition_uuid in sub_conditions_uuids:
            if sub_condition_uuid not in self.sub_conditions:
                self.sub_conditions.append(sub_condition_uuid)
        for spatial_handler_uuid in spatial_handler_uuids:
            if spatial_handler_uuid not in self.spatial_handler_uuids:
                self.spatial_handler_uuids.append(spatial_handler_uuid)

        self.applied = True
        if effect_event is None:
            canceled_event = execution_event.cancel(
                status_message=(
                    f"Condition {self.name} was not applied - "
                    "_apply() returned no effect event"
                ),
            )
            self.discard_uncommitted_runtime_state()
            return canceled_event
        if effect_event.canceled:
            self.discard_uncommitted_runtime_state()
            return effect_event

        try:
            self._finalize_application(effect_event)
        except BaseException:
            self.discard_uncommitted_runtime_state()
            raise

        completed_event = effect_event.phase_to(EventPhase.COMPLETION)
        self.applied_source_event_cursor = EventQueue.event_cursor()
        return completed_event

    def complete_unmanifested_application(
        self,
        declaration_event: Event,
        *,
        disposition: ConditionApplicationDisposition,
        status_message: str,
    ) -> Event:
        """Complete an admitted source lease that does not become effective.

        The application remains a causal fact, but `_apply()` is deliberately
        not called, so it cannot install modifiers, handlers, actions, or
        direct state before the condition arbiter selects it.
        """
        if disposition not in {
            ConditionApplicationDisposition.REJECTED,
            ConditionApplicationDisposition.RETAINED_STRONGER,
        }:
            raise ValueError(
                "Unmanifested applications require a non-effective disposition",
            )
        execution_event = declaration_event.phase_to(
            EventPhase.EXECUTION,
            condition=self,
            application_disposition=disposition,
            status_message=status_message,
        )
        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            condition=self,
            application_disposition=disposition,
            status_message=status_message,
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            condition=self,
            application_disposition=disposition,
            status_message=status_message,
        )

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

    def unlink_runtime_child(self, condition_uuid: UUID) -> None:
        """Forget one independently removed linked child.

        The child owns its own runtime removal.  This method only removes the
        reverse bookkeeping retained by its parent condition.
        """
        self.linked_conditions = [
            pair
            for pair in self.linked_conditions
            if pair[1] != condition_uuid
        ]

    def is_active_spatial_condition(self) -> bool:
        """Return whether this condition is an active independent map owner."""
        return False

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
        is handled by `BaseBlock._remove_condition_tree()`. Subclass `_remove()`
        hooks are preserved for custom cleanup behavior; the event's `expired`
        fact distinguishes expiration from explicit removal.

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
        event = EventQueue.publish_declaration(event)
        if event.canceled:
            return False

        execution_event = event.phase_to(
            EventPhase.EXECUTION,
            update={"condition": self},
        )
        if execution_event.canceled:
            return False

        removed_event = self._remove(execution_event)
        if removed_event and removed_event.canceled:
            return False

        self._release_owned_runtime_state(parent_event=parent_event)
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
        (removed_event or execution_event).phase_to(
            EventPhase.COMPLETION,
            **post_stats,
        )
        return True

    def remove_from_runtime_owner(
        self,
        *,
        expire: bool = False,
        parent_event: Optional[Event] = None,
    ) -> bool:
        """Remove an independently owned condition from its runtime owner.

        Ordinary conditions are removed by their BaseBlock and retain the
        existing BaseBlock tree path. Independently owned condition families
        override this narrow hook.
        """
        del expire, parent_event
        return False

    def discard_from_runtime_owner(self) -> bool:
        """Discard an uncommitted independently owned condition tree."""
        return False

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


class MostPotentCondition(BaseCondition):
    """Pure-artifact condition eligible for most-potent source arbitration.

    Instances of this class may be temporarily dormant while their source
    effect remains valid. Subclasses must express their manifested mechanics
    exclusively through the modifier and handler UUIDs returned from `_apply`.
    They may not own condition trees, cross-block links, granted actions, or
    direct untracked mutations that require an `_remove` side effect.
    """

    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description=(
            "The arbitration base is internal; concrete player-facing "
            "memberships must explicitly declare their public category."
        ),
    )
    application_policy: ConditionApplicationPolicy = Field(
        default=ConditionApplicationPolicy.MOST_POTENT_ACTIVE,
        frozen=True,
        description="Most-potent source arbitration is intrinsic to this base.",
    )
    potency_rank: Tuple[int, ...] = Field(
        min_length=1,
        description=(
            "Condition-authored lexicographic strength rank; higher values "
            "are more potent."
        ),
    )

    def suspend_for_arbitration(self) -> None:
        """Remove manifested artifacts without ending the source lease."""
        if not self.applied:
            raise ValueError("Only an applied condition can be suspended")
        if self.sub_conditions or self.linked_conditions:
            raise ValueError(
                "Most-potent conditions cannot own condition trees",
            )
        if self.has_granted_actions():
            raise ValueError(
                "Most-potent conditions cannot own granted actions",
            )
        if type(self)._remove is not BaseCondition._remove:
            raise ValueError(
                "Most-potent conditions cannot own custom removal side effects",
            )

        self.remove_condition_modifiers()
        self.modifers_uuids.clear()
        self.remove_event_handlers()
        self.remove_spatial_handlers()
        self.applied = False


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
